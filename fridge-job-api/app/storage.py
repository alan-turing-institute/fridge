import json
import requests
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from typing import Annotated
from .config import (
    argo_token,
    ARGO_SERVER,
    minio_client,
    parse_argo_error,
    verify_request,
    VERIFY_TLS,
)

router = APIRouter(tags=["s3"])


@router.post("/object/{bucket}/upload", tags=["s3"])
async def upload_object(
    bucket: str,
    file: UploadFile = File(...),
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    return await minio_client.put_object(bucket, file)


@router.get("/object/{bucket}/{file_name}", tags=["s3"])
async def get_object(
    bucket: str,
    file_name: str,
    target_file: str | None = None,
    version: str | None = None,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    return minio_client.get_object(bucket, file_name, target_file, version)


# Trigger Argo workflow
@router.post("/object/move", tags=["s3"])
async def move_object(
    files: Annotated[
        str, "The name of files to move (Separate with ; for multiple files)"
    ],
    version: str | None = None,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
) -> dict:
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
                        "bucket=ingress",
                        f"files={files}",
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
        "files": files.split(";"),
        "workflow": r.json()["metadata"]["name"],
    }


@router.post("/object/bucket", tags=["s3"])
async def create_bucket(
    bucket_name: str,
    versioning: bool = False,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    return minio_client.create_bucket(bucket_name, versioning)


@router.delete("/object/{bucket}/{file_name}", tags=["s3"])
async def delete_object(
    bucket: str,
    file_name: str,
    version: str | None = None,
    verified: Annotated[bool, "Verify the request with basic auth"] = Depends(
        verify_request
    ),
):
    return minio_client.delete_object(bucket, file_name, version)
