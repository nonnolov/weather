"""Reverse geocoding backed by a configurable provider."""
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
        provider: str | None = None,
    ) -> None:
        self._provider = (provider or settings.GEOCODER_PROVIDER).lower()
        self._base_url = (base_url or settings.GEOCODER_BASE_URL).rstrip("/")
        self._user_agent = user_agent or settings.GEOCODER_USER_AGENT
        self._transport = transport

    async def reverse(self, latitude: float, longitude: float) -> AdministrativeArea:
        try:
            async with httpx.AsyncClient(timeout=10.0, transport=self._transport) as client:
                if self._provider == "arcgis":
                    response = await client.get(
                        f"{self._base_url}/reverseGeocode",
                        params={
                            "location": f"{longitude},{latitude}",
                            "f": "json",
                            "langCode": "TH",
                        },
                        headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                    )
                elif self._provider == "nominatim":
                    response = await client.get(
                        f"{self._base_url}/reverse",
                        params={
                            "lat": latitude,
                            "lon": longitude,
                            "format": "jsonv2",
                            "addressdetails": 1,
                        },
                        headers={"User-Agent": self._user_agent, "Accept": "application/json"},
                    )
                else:
                    raise ReverseGeocodingError(
                        f"Unsupported reverse geocoding provider: {self._provider}"
                    )

                response.raise_for_status()
                raw: dict[str, Any] = response.json()
        except ReverseGeocodingError:
            raise
        except (httpx.HTTPError, ValueError) as exc:
            raise ReverseGeocodingError("Reverse geocoding service request failed.") from exc

        if not isinstance(raw, dict):
            raise ReverseGeocodingError("Reverse geocoding service returned an invalid response.")

        address = raw.get("address")
        if not isinstance(address, dict):
            raise ReverseGeocodingError("Reverse geocoding service returned no address.")

        if self._provider == "arcgis":
            province = _first_text(address, "Region")
            district = _first_text(address, "Subregion")
            subdistrict = _first_text(address, "City")
            country_code = _first_text(address, "CountryCode")
            if country_code:
                country_code = country_code.upper()
                if country_code == "THA":
                    country_code = "TH"
        else:
            province = _first_text(address, "state", "province", "region")
            district = _first_text(address, "county", "state_district", "city_district")
            subdistrict = _first_text(
                address, "municipality", "town", "village", "suburb", "city"
            )
            country_code = _first_text(address, "country_code")

        province = _strip_thai_admin_prefix(province, "จังหวัด")
        district = _strip_thai_admin_prefix(district, "อำเภอ", "เขต")
        subdistrict = _strip_thai_admin_prefix(subdistrict, "ตำบล", "แขวง")

        if not all((province, district, subdistrict)):
            raise ReverseGeocodingError(
                "Reverse geocoding service returned incomplete administrative areas."
            )

        return AdministrativeArea(
            province=province,
            district=district,
            subdistrict=subdistrict,
            country_code=country_code,
        )


def _first_text(address: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = address.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _strip_thai_admin_prefix(value: str | None, *prefixes: str) -> str | None:
    if value is None:
        return None
    result = value.strip()
    for prefix in prefixes:
        if result.startswith(prefix):
            return result[len(prefix) :].strip()
    return result


def get_reverse_geocoder() -> ReverseGeocoder:
    return ReverseGeocoder()
