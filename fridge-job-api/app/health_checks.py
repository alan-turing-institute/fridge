from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/healthz", include_in_schema=False)
async def liveness() -> dict:
    """
    Liveness probe endpoint.
    Returns a simple JSON response indicating that the service is alive.
    """
    return {"status": "alive"}
