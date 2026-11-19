import json
import re
import requests
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from starlette.concurrency import run_in_threadpool
from typing import Annotated, Literal
from .config import (
    argo_token,
    ARGO_SERVER,
    parse_argo_error,
    s3_client,
    caller_s3_client,
    s3_access_key_header,
    s3_secret_key_header,
    verify_request,
    VERIFY_TLS,
)
from .form_upload import FormFileReader
from .s3_client import S3Client, check_object_size, stream_memory, upload_memory

# S3 bucket naming rules: 3-63 characters, lowercase letters, numbers, dots and hyphens
BUCKET_PATTERN = r"^[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]$"
Bucket = Annotated[str, Path(pattern=BUCKET_PATTERN)]

router = APIRouter(tags=["s3"])


def s3_credentials(
    s3_access_key: Annotated[str | None, Depends(s3_access_key_header)] = None,
    s3_secret_key: Annotated[str | None, Depends(s3_secret_key_header)] = None,
) -> tuple[str | None, str | None]:
    """The caller's own S3 credentials, if supplied."""
    return s3_access_key, s3_secret_key


def s3_for_bucket(bucket: str, credentials: tuple[str | None, str | None]) -> S3Client:
    """
    Use the caller's own S3 credentials if they supplied them, so that S3 enforces what they
    may do (e.g. that only the owner can use a user-specific bucket). Otherwise use the API's
    generic credentials, whose reach is whatever its S3 identity allows (by default the
    shared buckets only).
    """
    access_key, secret_key = credentials
    if access_key is None and secret_key is None:
        return s3_client
    return caller_s3_client(access_key, secret_key)


def check_key(key: str | None) -> str:
    if not key:
        raise HTTPException(status_code=422, detail="The file must have a name.")
    if key.startswith("/") or ".." in key.split("/"):
        raise HTTPException(
            status_code=422,
            detail="Object names must be relative and must not contain '..'.",
        )
    return key


def content_length(request: Request) -> int:
    """
    The size of the request body. Uploads must give it, so that the size limit can be checked
    and memory reserved before any of the body is read.
    """
    value = request.headers.get("content-length")
    if not (value and value.isdigit()):
        raise HTTPException(
            status_code=411, detail="Uploads must have a Content-Length header."
        )
    return int(value)


# The file is read from the request body as it arrives and sent on to S3, rather than through
# an UploadFile parameter, which would save the whole body to disk first. The request body is
# described here so that it still appears in the OpenAPI docs.
@router.post(
    "/object/{bucket}/upload",
    tags=["s3"],
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {"file": {"type": "string", "format": "binary"}},
                        "required": ["file"],
                    }
                }
            },
        }
    },
)
async def upload_object(
    bucket: Bucket,
    request: Request,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
):
    """
    Upload a file of up to 1TiB, e.g. `curl -F file=@data.csv .../object/ingress/upload`.
    The object is named after the file; to name it something else, give the name in the form,
    e.g. `-F "file=@data.csv;filename=project/other-name.csv"`.
    """
    # The size of the whole form, a little more than the file, which is close enough for
    # checking the size limit and choosing the part size
    size = content_length(request)
    check_object_size(size)
    s3 = s3_for_bucket(bucket, credentials)
    form = FormFileReader(request)
    # Reserved before any of the body is read, so that an upload is never refused partway through
    with upload_memory.reserve(stream_memory(size)):
        await run_in_threadpool(form.open)
        return await run_in_threadpool(
            s3.put_object,
            bucket,
            check_key(form.filename),
            form.content_type,
            form,
            size,
        )


@router.get("/object/{bucket}/{file_name:path}", tags=["s3"])
def get_object(
    bucket: Bucket,
    file_name: str,
    target_file: str | None = None,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
):
    return s3_for_bucket(bucket, credentials).get_object(bucket, file_name, target_file)


@router.get("/object/list", tags=["s3"])
def list_objects(
    bucket: Annotated[str, Query(pattern=BUCKET_PATTERN)] = "ingress",
    prefix: str | None = None,
    recursive: bool = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
):
    return s3_for_bucket(bucket, credentials).list_objects(bucket, prefix, recursive)


# Trigger Argo workflow
@router.post("/object/move", tags=["s3"])
def move_object(
    files: Annotated[
        str, "The name of files to move (Separate with ; for multiple files)"
    ],
    direction: Literal["ingress", "egress"] = "ingress",
    bucket: Annotated[
        str | None,
        "Bucket to copy from when direction is ingress (defaults to 'ingress'). "
        "Must be 'egress' (the default) when direction is egress.",
    ] = None,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
) -> dict:
    bucket = bucket or direction
    if not re.fullmatch(BUCKET_PATTERN, bucket):
        raise HTTPException(status_code=422, detail=f"Invalid bucket name: {bucket}")
    if direction == "egress" and bucket != "egress":
        raise HTTPException(
            status_code=422, detail="Files can only be moved to the 'egress' bucket."
        )

    file_names = [name for name in files.split(";") if name]
    if not file_names:
        raise HTTPException(status_code=422, detail="No file names provided.")
    if any(name.startswith("/") or ".." in name.split("/") for name in file_names):
        raise HTTPException(
            status_code=422,
            detail="File names must be relative and must not contain '..'.",
        )

    if direction == "ingress":
        # The copy workflow runs with its own S3 identity, so check here, using the caller's
        # credentials if supplied, that they can read the files. This also fails
        # early if a file is missing rather than after the workflow has started.
        source_s3 = s3_for_bucket(bucket, credentials)
        for name in file_names:
            if not source_s3.check_object_exists(bucket, name):
                raise HTTPException(
                    status_code=404, detail=f"{name} not found in bucket {bucket}"
                )

    r = requests.post(
        f"{ARGO_SERVER}/api/v1/workflows/argo-workflows/submit",
        verify=VERIFY_TLS,
        headers={"Authorization": f"Bearer {argo_token()}"},
        data=json.dumps(
            {
                "resourceKind": "WorkflowTemplate",
                "resourceName": "data-copy",
                "submitOptions": {
                    "generateName": "data-copy-",
                    "parameters": [
                        f"direction={direction}",
                        f"bucket={bucket}",
                        f"files={';'.join(file_names)}",
                    ],
                },
            }
        ),
    )

    if r.status_code != 200:
        raise HTTPException(
            status_code=r.status_code, detail=parse_argo_error(r.json())
        )
    return {
        "status": r.status_code,
        "direction": direction,
        "bucket": bucket,
        "files": file_names,
        "workflow": r.json()["metadata"]["name"],
    }


@router.post("/object/bucket", tags=["s3"])
def create_bucket(
    bucket_name: Annotated[str, Query(pattern=BUCKET_PATTERN)],
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    caller_s3: S3Client = Depends(caller_s3_client),
):
    # Needs S3 admin rights, so uses the credentials supplied by the caller (the admin)
    return caller_s3.create_bucket(bucket_name)


@router.delete("/object/{bucket}/{file_name:path}", tags=["s3"])
def delete_object(
    bucket: Bucket,
    file_name: str,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
):
    return s3_for_bucket(bucket, credentials).delete_object(bucket, file_name)
