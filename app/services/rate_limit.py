"""Small in-process sliding-window rate limits for abuse-prone API actions."""
import asyncio
import math
import time
from collections import deque
from collections.abc import Awaitable, Callable

from fastapi import HTTPException, Request, status

from app.core.config import settings


class SlidingWindowRateLimiter:
    def __init__(self) -> None:
        self._events: dict[tuple[str, str], deque[float]] = {}
        self._lock = asyncio.Lock()
        self._last_cleanup = 0.0

    async def check(
        self,
        bucket: str,
        client_id: str,
        limit: int,
        window_seconds: int,
    ) -> None:
        now = time.monotonic()
        cutoff = now - window_seconds
        key = (bucket, client_id)

        async with self._lock:
            if now - self._last_cleanup >= 60:
                stale = [
                    stored_key
                    for stored_key, events in self._events.items()
                    if not events or events[-1] <= cutoff
                ]
                for stored_key in stale:
                    self._events.pop(stored_key, None)
                self._last_cleanup = now

            events = self._events.setdefault(key, deque())
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, math.ceil(window_seconds - (now - events[0])))
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please try again later.",
                    headers={"Retry-After": str(retry_after)},
                )

            events.append(now)

    async def reset(self) -> None:
        async with self._lock:
            self._events.clear()
            self._last_cleanup = 0.0


_limiter = SlidingWindowRateLimiter()


def _client_id(request: Request) -> str:
    # Railway public networking supplies X-Real-IP with the client's remote IP.
    real_ip = request.headers.get("x-real-ip")
    if real_ip:
        return real_ip.strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def rate_limit(
    bucket: str,
    limit: int,
    window_seconds: int = 60,
) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        # Keep local development/tests friction-free; production is protected.
        if settings.APP_ENV != "production":
            return
        await _limiter.check(
            bucket=bucket,
            client_id=_client_id(request),
            limit=limit,
            window_seconds=window_seconds,
        )

    return dependency


audience_visit_rate_limit = rate_limit("audience-visit", 60)
line_auth_rate_limit = rate_limit("line-auth", 20)
gps_rate_limit = rate_limit("gps", 12)
forecast_refresh_rate_limit = rate_limit("forecast-refresh", 6)
line_action_rate_limit = rate_limit("line-action", 20)
admin_maintenance_rate_limit = rate_limit("admin-maintenance", 30)


async def reset_rate_limits() -> None:
    """Test helper."""
    await _limiter.reset()
