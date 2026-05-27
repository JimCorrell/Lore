from fastapi import APIRouter, Response
from app.config import settings
from app.database import check_db_connection

router = APIRouter(tags=["health"])


@router.get("/health")
def health_check(response: Response) -> dict:
    """
    Service health check. Returns 200 when healthy, 503 when the database
    is unreachable. Used by load balancers and monitoring.
    """
    db_ok = check_db_connection()
    if not db_ok:
        response.status_code = 503

    return {
        "status": "ok" if db_ok else "degraded",
        "service": "lore",
        "version": settings.app_version,
        "environment": settings.app_env,
        "database": "ok" if db_ok else "error",
    }
