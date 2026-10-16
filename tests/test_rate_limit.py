import pytest
import pytest_asyncio
from fastapi import HTTPException

from app.core.config import settings
from app.services.rate_limit import SlidingWindowRateLimiter, reset_rate_limits


@pytest_asyncio.fixture(autouse=True)
async def clean_rate_limits():
    await reset_rate_limits()
    yield
    await reset_rate_limits()


@pytest.mark.asyncio
async def test_sliding_window_rejects_after_limit():
    limiter = SlidingWindowRateLimiter()

    await limiter.check("test", "client-a", limit=2, window_seconds=60)
    await limiter.check("test", "client-a", limit=2, window_seconds=60)

    with pytest.raises(HTTPException) as exc:
        await limiter.check("test", "client-a", limit=2, window_seconds=60)

    assert exc.value.status_code == 429
    assert int(exc.value.headers["Retry-After"]) >= 1


@pytest.mark.asyncio
async def test_rate_limit_buckets_are_independent():
    limiter = SlidingWindowRateLimiter()

    await limiter.check("gps", "client-a", limit=1, window_seconds=60)
    await limiter.check("gps", "client-b", limit=1, window_seconds=60)
    await limiter.check("forecast", "client-a", limit=1, window_seconds=60)


@pytest.mark.asyncio
async def test_production_admin_endpoint_is_rate_limited_by_real_ip(client, monkeypatch):
    monkeypatch.setattr(settings, "APP_ENV", "production")
    monkeypatch.setattr(settings, "ADMIN_API_KEY", "test-admin-key-0123456789abcdef0123456789abcdef")

    headers = {
        "X-Admin-API-Key": "wrong-key",
        "X-Real-IP": "203.0.113.10",
    }
    for _ in range(30):
        response = await client.post("/api/v1/ingest/999999", headers=headers)
        assert response.status_code == 401

    limited = await client.post("/api/v1/ingest/999999", headers=headers)
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) >= 1

    other_ip = await client.post(
        "/api/v1/ingest/999999",
        headers={
            "X-Admin-API-Key": "wrong-key",
            "X-Real-IP": "203.0.113.11",
        },
    )
    assert other_ip.status_code == 401
