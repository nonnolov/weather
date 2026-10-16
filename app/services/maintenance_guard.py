"""Protect maintenance-only endpoints in production with an admin API key."""
import hashlib
import hmac

from fastapi import Header, HTTPException, status

from app.core.config import settings


def effective_admin_api_key() -> str:
    """Use an explicit admin key when configured, otherwise derive one safely."""
    if settings.ADMIN_API_KEY:
        return settings.ADMIN_API_KEY
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"),
        b"weather-admin-api-v1",
        hashlib.sha256,
    ).hexdigest()


async def require_nonproduction_maintenance(
    x_admin_api_key: str | None = Header(default=None, alias="X-Admin-API-Key"),
) -> None:
    if settings.APP_ENV != "production":
        return

    configured = effective_admin_api_key()
    if not x_admin_api_key or not hmac.compare_digest(x_admin_api_key, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Valid admin API key required.",
        )
