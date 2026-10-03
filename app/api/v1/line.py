from typing import Any
import hashlib
import hmac
import logging

import httpx
from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.core.config import settings


logger = logging.getLogger(__name__)
router = APIRouter()


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
async def line_webhook(request: Request) -> dict[str, Any]:
    """Accept authenticated LINE webhook events for integration testing."""
    body = await request.body()
    if not _validate_signature(body, request.headers.get("x-line-signature")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid LINE signature",
        )

    payload = await request.json()
    user_ids: list[str] = []
    for event in payload.get("events", []):
        source = event.get("source") or {}
        user_id = source.get("userId")
        if user_id:
            user_ids.append(user_id)
            logger.info("LINE webhook userId=%s event=%s", user_id, event.get("type"))

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
