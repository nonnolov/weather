from datetime import datetime, timezone as dt_timezone
from unittest.mock import patch

import pytest
from httpx import AsyncClient

from app.main import app
from app.providers.base import ProviderForecastResult
from app.services.geocoding import AdministrativeArea, get_reverse_geocoder


BANGKOK_LATITUDE = 13.7563
BANGKOK_LONGITUDE = 100.5018


class CapturingGeocoder:
    def __init__(self) -> None:
        self.coordinates: tuple[float, float] | None = None

    async def reverse(self, latitude: float, longitude: float) -> AdministrativeArea:
        self.coordinates = (latitude, longitude)
        return AdministrativeArea(
            province="Bangkok",
            district="Phra Nakhon",
            subdistrict="Chana Songkhram",
            country_code="TH",
        )


class CapturingOpenMeteoProvider:
    name = "open_meteo"

    def __init__(self) -> None:
        self.coordinates: tuple[float, float] | None = None

    async def fetch_forecast(
        self,
        latitude: float,
        longitude: float,
        forecast_days: int = 7,
        timezone: str = "UTC",
    ) -> ProviderForecastResult:
        self.coordinates = (latitude, longitude)
        return ProviderForecastResult(
            provider=self.name,
            retrieved_at=datetime.now(dt_timezone.utc),
            model_run_time=None,
            metadata={"timezone": "Asia/Bangkok"},
        )


@pytest.mark.asyncio
async def test_bangkok_gps_coordinates_are_forwarded_unchanged_to_geocoder_and_open_meteo(
    client: AsyncClient,
) -> None:
    geocoder = CapturingGeocoder()
    provider = CapturingOpenMeteoProvider()
    app.dependency_overrides[get_reverse_geocoder] = lambda: geocoder

    try:
        location_response = await client.post(
            "/api/v1/users/bangkok-e2e/location/from-gps",
            json={"latitude": BANGKOK_LATITUDE, "longitude": BANGKOK_LONGITUDE},
        )
        assert location_response.status_code == 200

        with patch("app.ingestion.service.get_provider", return_value=provider):
            refresh_response = await client.post(
                "/api/v1/users/bangkok-e2e/forecast/refresh",
                params={"forecast_days": 7},
            )

        assert refresh_response.status_code == 201
        assert geocoder.coordinates == (BANGKOK_LATITUDE, BANGKOK_LONGITUDE)
        assert provider.coordinates == (BANGKOK_LATITUDE, BANGKOK_LONGITUDE)
        assert provider.coordinates == geocoder.coordinates
    finally:
        app.dependency_overrides.pop(get_reverse_geocoder, None)
