"""Minimal LINE Messaging API client."""
from __future__ import annotations

import httpx


class LineApiError(RuntimeError):
    pass


class LineClient:
    def __init__(self, access_token: str, base_url: str = "https://api.line.me") -> None:
        if not access_token:
            raise ValueError("LINE channel access token is required")
        self._access_token = access_token
        self._base_url = base_url.rstrip("/")

    async def push_text(self, recipient_id: str, text: str) -> None:
        if not recipient_id:
            raise ValueError("LINE recipient ID is required")
        if not text:
            raise ValueError("LINE message text is required")
        if len(text) > 5000:
            raise ValueError("LINE text message exceeds 5000 characters")

        response = await self._request(recipient_id, text)
        if response.status_code >= 300:
            raise LineApiError(f"LINE push failed: {response.status_code} {response.text}")

    async def _request(self, recipient_id: str, text: str) -> httpx.Response:
        headers = {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
        }
        payload = {
            "to": recipient_id,
            "messages": [{"type": "text", "text": text}],
        }
        async with httpx.AsyncClient(timeout=15.0) as client:
            return await client.post(
                f"{self._base_url}/v2/bot/message/push",
                headers=headers,
                json=payload,
            )
