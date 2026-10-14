import json
import re
import requests
from fastapi import APIRouter, Depends, HTTPException, Path, Query, UploadFile
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
from .s3_client import S3Client

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


@router.post("/object/{bucket}/upload", tags=["s3"])
async def upload_object(
    bucket: Bucket,
    file: UploadFile,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
):
    return await s3_for_bucket(bucket, credentials).put_object(bucket, file)


@router.get("/object/{bucket}/{file_name:path}", tags=["s3"])
async def get_object(
    bucket: Bucket,
    file_name: str,
    target_file: str | None = None,
    version: str | None = None,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
):
    return s3_for_bucket(bucket, credentials).get_object(
        bucket, file_name, target_file, version
    )


@router.get("/object/list", tags=["s3"])
async def list_objects(
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
async def move_object(
    files: Annotated[
        str, "The name of files to move (Separate with ; for multiple files)"
    ],
    direction: Literal["ingress", "egress"] = "ingress",
    bucket: Annotated[
        str | None,
        "Bucket to copy from when direction is ingress (defaults to 'ingress'). "
        "Must be 'egress' (the default) when direction is egress.",
    ] = None,
    version: str | None = None,
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
            if not source_s3.check_object_exists(bucket, name, version):
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
async def create_bucket(
    bucket_name: Annotated[str, Query(pattern=BUCKET_PATTERN)],
    versioning: bool = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    caller_s3: S3Client = Depends(caller_s3_client),
):
    # Needs S3 admin rights, so uses the credentials supplied by the caller (the admin)
    return caller_s3.create_bucket(bucket_name)


@router.delete("/object/{bucket}/{file_name:path}", tags=["s3"])
async def delete_object(
    bucket: Bucket,
    file_name: str,
    version: str | None = None,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
    credentials: tuple = Depends(s3_credentials),
):
    return s3_for_bucket(bucket, credentials).delete_object(bucket, file_name, version)
