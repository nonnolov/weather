"""Guard maintenance-only API endpoints from public production access."""
from fastapi import HTTPException, status

from app.core.config import settings


async def require_nonproduction_maintenance() -> None:
    if settings.APP_ENV == "production":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maintenance endpoint is disabled in production.",
        )
