import requests
from fastapi import APIRouter
from minio import S3Error
from urllib3.exceptions import HTTPError
from .config import ARGO_SERVER, argo_token, minio_client, VERIFY_TLS

router = APIRouter(tags=["Health"])


@router.get("/healthz", include_in_schema=False)
async def liveness() -> dict:
    """
    Liveness probe endpoint.
    Returns a simple JSON response indicating that the service is alive.
    """
    return {"status": "alive"}


@router.get("/readyz", include_in_schema=False)
async def readiness() -> dict:
    """
    Readiness probe endpoint.
    Confirms Argo and MinIO are reachable and returns a JSON indicating when ready.
    """
    checks = {"argo": _check_argo(), "minio": _check_minio()}
    healthy = all(checks[service]["status"] == "ok" for service in checks)
    return {"status": "ready"}


def _check_argo() -> dict:
    """
    Check if Argo Workflows is reachable.
    Returns a JSON indicating the status of the Argo service.
    """
    try:
        response = requests.get(
            f"{ARGO_SERVER}/api/v1/workflows/argo-workflows/submit",
            verify=VERIFY_TLS,
            headers={"Authorization": f"Bearer {argo_token()}"},
            timeout=3,
        )
        return (
            {"status": "ok"}
            if response.status_code == 200
            else {"status": "unreachable", "error": f"HTTP {response.status_code}"}
        )
    except requests.exceptions.RequestException as e:
        return {"status": "unreachable", "error": str(e)}


def _check_minio() -> dict:
    """
    Check if MinIO is reachable.
    Returns a JSON indicating the status of the MinIO service.
    """
    try:
        minio_client.client.list_buckets()
        return {"status": "ok"}
    except (S3Error, HTTPError, OSError) as e:
        return {"status": "unreachable", "error": str(e)}
