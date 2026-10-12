from typing import Any
import hashlib
import hmac
import logging

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.v1.line_onboarding import router as onboarding_router, apply_friend_events
from pydantic import BaseModel

from app.core.config import settings


logger = logging.getLogger(__name__)
router = APIRouter()
router.include_router(onboarding_router)


class LineAuthRequest(BaseModel):
    id_token: str


class LineAuthResponse(BaseModel):
    external_user_id: str


def _validate_signature(body: bytes, signature: str | None) -> bool:
    if not signature or not settings.LINE_CHANNEL_SECRET:
        return False
    digest = hmac.new(
        settings.LINE_CHANNEL_SECRET.encode("utf-8"),
        body,
        hashlib.sha256,
    ).digest()
    import base64
    expected = base64.b64encode(digest).decode("ascii")
    return hmac.compare_digest(expected, signature)


@router.post("/webhook")
async def line_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict[str, Any]:
    """Accept authenticated LINE webhook events for integration testing."""
    body = await request.body()
    if not _validate_signature(body, request.headers.get("x-line-signature")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LINE signature",
        )

    try:
        payload = await request.json()
    except ValueError as exc:
        raise HTTPException(400, 'Invalid LINE event payload') from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("events", []), list):
        raise HTTPException(400, "Invalid LINE event payload")
    if settings.LINE_SUBSCRIPTIONS_ENABLED:
        await apply_friend_events(db, payload.get("events", []))
    user_ids: list[str] = []
    for event in payload.get("events", []):
        if not isinstance(event, dict):
            raise HTTPException(400, "Invalid LINE event payload")
        source = event.get("source") or {}
        if not isinstance(source, dict):
            raise HTTPException(400, "Invalid LINE event payload")
        user_id = source.get("userId")
        if user_id:
            user_ids.append(user_id)
            logger.info("LINE webhook event=%s", event.get("type"))

    return {"status": "ok", "user_ids": user_ids}


@router.post("/auth", response_model=LineAuthResponse)
async def authenticate_line(request: LineAuthRequest) -> LineAuthResponse:
    """Verify a LIFF ID token with LINE and return the verified LINE user ID."""
    if not settings.LINE_LOGIN_CHANNEL_ID:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="LINE Login channel is not configured.",
        )

    try:
        async with httpx.AsyncClient(
            base_url=settings.LINE_API_BASE_URL.rstrip("/"),
            timeout=10.0,
        ) as client:
            response = await client.post(
                "/oauth2/v2.1/verify",
                data={
                    "id_token": request.id_token,
                    "client_id": settings.LINE_LOGIN_CHANNEL_ID,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LINE token verification service is unavailable.",
        ) from exc

    if response.status_code != 200:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid LINE ID token.",
        )

    try:
        payload: dict[str, Any] = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LINE token verification returned invalid data.",
        ) from exc

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="LINE token verification returned no user ID.",
        )

    return LineAuthResponse(external_user_id=user_id)
