"""Verify LINE-issued credentials; never trust a browser-supplied user ID."""
from dataclasses import dataclass
import httpx
import logging
import re
import math
logger = logging.getLogger(__name__)
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.core.config import settings
class _RedactAccessToken(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, tuple):
            record.args = tuple(re.sub(r"(access_token=)[^&\s]+", r"\1[REDACTED]", str(value)) if "access_token=" in str(value) else value for value in record.args)
        return True

logging.getLogger("httpx").addFilter(_RedactAccessToken())
bearer = HTTPBearer(auto_error=False)

@dataclass(frozen=True)
class LineIdentity:
    user_id: str
    access_token: str

async def _get(client, path, **kwargs):
    try:
        response = await client.get(path, **kwargs)
        if path == "/friendship/v1/status" and response.status_code == 400:
            raise HTTPException(503, "Weather friendship verification is not configured.")
        if response.status_code in (400, 401, 403):
            logger.warning("LINE credential rejected endpoint=%s status=%s", path, response.status_code)
            raise HTTPException(401, "LINE session expired or required permission missing.")
        if response.status_code != 200:
            raise HTTPException(502, "LINE verification is temporarily unavailable.")
        data = response.json()
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (httpx.HTTPError, ValueError) as exc:
        raise HTTPException(502, "LINE verification is temporarily unavailable.") from exc

async def verify_line_token(token: str) -> LineIdentity:
    if not settings.LINE_LOGIN_CHANNEL_ID:
        raise HTTPException(503, "LINE Login is not configured.")
    async with httpx.AsyncClient(base_url=settings.LINE_API_BASE_URL.rstrip("/"), timeout=10) as client:
        verified = await _get(client, "/oauth2/v2.1/verify", params={"access_token": token})
        scopes = set(str(verified.get("scope", "")).split())
        expiry = verified.get("expires_in")
        reason = None
        if str(verified.get("client_id")) != settings.LINE_LOGIN_CHANNEL_ID:
            reason = "channel_mismatch"
        elif type(expiry) not in (int, float) or not math.isfinite(expiry) or expiry <= 0:
            reason = "invalid_expiry"
        elif not {"openid", "profile"}.issubset(scopes):
            reason = "missing_scopes"
        if reason:
            logger.warning("LINE credential rejected reason=%s openid=%s profile=%s", reason, "openid" in scopes, "profile" in scopes)
            raise HTTPException(401, "LINE token channel or permissions do not match.")
        profile = await _get(client, "/oauth2/v2.1/userinfo", headers={"Authorization": "Bearer " + token})
    subject = profile.get("sub")
    if not isinstance(subject, str) or not re.fullmatch(r"U[0-9a-f]{32}", subject):
        raise HTTPException(502, "LINE verification returned invalid identity.")
    return LineIdentity(subject, token)

async def require_line_identity(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> LineIdentity:
    if credentials is None or credentials.scheme.lower() != "bearer" or len(credentials.credentials) > 4096:
        raise HTTPException(401, "Sign in with LINE first.")
    return await verify_line_token(credentials.credentials)

async def line_friendship(identity: LineIdentity) -> bool:
    async with httpx.AsyncClient(base_url=settings.LINE_API_BASE_URL.rstrip("/"), timeout=10) as client:
        data = await _get(client, "/friendship/v1/status", headers={"Authorization": "Bearer " + identity.access_token})
    if type(data.get("friendFlag")) is not bool:
        raise HTTPException(502, "LINE friendship could not be verified.")
    return data["friendFlag"]

async def protect_line_user_path(request: Request):
    user_id = request.path_params.get("external_user_id", "")
    if not settings.LINE_SUBSCRIPTIONS_ENABLED or not user_id.startswith("U"):
        return
    value = request.headers.get("authorization", "")
    scheme, _, token = value.partition(" ")
    if scheme.lower() != "bearer" or not token or len(token) > 4096:
        raise HTTPException(401, "Sign in with LINE first.")
    identity = await verify_line_token(token)
    if identity.user_id != user_id:
        raise HTTPException(403, "This LINE account cannot access another user's data.")
