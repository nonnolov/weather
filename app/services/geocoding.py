"""Reverse geocoding backed by a Nominatim-compatible API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import settings


class ReverseGeocodingError(RuntimeError):
    """Raised when a reverse-geocoding request cannot produce an address."""


@dataclass(frozen=True)
class AdministrativeArea:
    province: str
    district: str
    subdistrict: str
    country_code: str | None


class ReverseGeocoder:
    def __init__(
        self,
        base_url: str | None = None,
        user_agent: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (base_url or settings.GEOCODER_BASE_URL).rstrip("/")
        self._user_agent = user_agent or settings.GEOCODER_USER_AGENT
        self._transport = transport

    async def reverse(self, latitude: float, longitude: float) -> AdministrativeArea:
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                response = await client.get(
                    f"{self._base_url}/reverse",
                    params={"lat": latitude, "lon": longitude, "format": "jsonv2", "addressdetails": 1},
                    headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                )
                response.raise_for_status()
                raw: dict[str, Any] = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ReverseGeocodingError("Reverse geocoding service request failed.") from exc

        if not isinstance(raw, dict):
            raise ReverseGeocodingError("Reverse geocoding service returned an invalid response.")
        address = raw.get("address")
        if not isinstance(address, dict):
            raise ReverseGeocodingError("Reverse geocoding service returned no address.")

        province = _first_text(address, "state", "province", "region")
        district = _first_text(address, "county", "state_district", "city_district")
        subdistrict = _first_text(address, "suburb", "municipality", "town", "village", "city")
        if not all((province, district, subdistrict)):
            raise ReverseGeocodingError("Reverse geocoding service returned incomplete administrative areas.")
        return AdministrativeArea(
            province=province,
            district=district,
            subdistrict=subdistrict,
            country_code=_first_text(address, "country_code"),
        )


def _first_text(address: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = address.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def get_reverse_geocoder() -> ReverseGeocoder:
    return ReverseGeocoder()
