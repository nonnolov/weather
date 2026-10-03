from unittest.mock import AsyncMock, patch

import httpx
import pytest

from app.core.config import settings


class FakeLineClient:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def post(self, *args, **kwargs):
        return self.response


@pytest.mark.asyncio
async def test_line_auth_verifies_id_token_and_returns_subject(client):
    response = httpx.Response(
        200,
        json={"sub": "U_verified", "aud": "1234567890"},
        request=httpx.Request("POST", "https://api.line.test/oauth2/v2.1/verify"),
    )
    original_channel_id = settings.LINE_LOGIN_CHANNEL_ID
    settings.LINE_LOGIN_CHANNEL_ID = "1234567890"
    try:
        with patch("app.api.v1.line.httpx.AsyncClient", return_value=FakeLineClient(response)):
            result = await client.post(
                "/api/v1/line/auth",
                json={"id_token": "test-token"},
            )
    finally:
        settings.LINE_LOGIN_CHANNEL_ID = original_channel_id

    assert result.status_code == 200
    assert result.json() == {"external_user_id": "U_verified"}


@pytest.mark.asyncio
async def test_line_auth_rejects_invalid_token(client):
    response = httpx.Response(
        400,
        json={"error": "invalid_request"},
        request=httpx.Request("POST", "https://api.line.test/oauth2/v2.1/verify"),
    )
    original_channel_id = settings.LINE_LOGIN_CHANNEL_ID
    settings.LINE_LOGIN_CHANNEL_ID = "1234567890"
    try:
        with patch("app.api.v1.line.httpx.AsyncClient", return_value=FakeLineClient(response)):
            result = await client.post(
                "/api/v1/line/auth",
                json={"id_token": "invalid-token"},
            )
    finally:
        settings.LINE_LOGIN_CHANNEL_ID = original_channel_id

    assert result.status_code == 401


@pytest.mark.asyncio
async def test_line_auth_requires_configuration(client):
    original_channel_id = settings.LINE_LOGIN_CHANNEL_ID
    settings.LINE_LOGIN_CHANNEL_ID = None
    try:
        result = await client.post(
            "/api/v1/line/auth",
            json={"id_token": "test-token"},
        )
    finally:
        settings.LINE_LOGIN_CHANNEL_ID = original_channel_id

    assert result.status_code == 503
