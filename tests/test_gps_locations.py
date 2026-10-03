import httpx
import pytest
from httpx import AsyncClient

from app.main import app
from app.services.geocoding import ReverseGeocoder, get_reverse_geocoder


GEOCODER_RESPONSE = {
    "address": {
        "state": "Bangkok",
        "city_district": "Watthana",
        "suburb": "Khlong Toei Nuea",
        "country_code": "th",
    }
}


def _geocoder(response: httpx.Response, requests: list[httpx.Request] | None = None) -> ReverseGeocoder:
    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return response

    return ReverseGeocoder(
        base_url="https://geocoder.test",
        user_agent="weather-tests/1.0",
        transport=httpx.MockTransport(handler),
    )


@pytest.mark.asyncio
async def test_reverse_geocoder_uses_configured_endpoint_and_user_agent() -> None:
    requests: list[httpx.Request] = []
    geocoder = _geocoder(httpx.Response(200, json=GEOCODER_RESPONSE), requests)

    area = await geocoder.reverse(13.7563, 100.5018)

    assert area.province == "Bangkok"
    assert area.district == "Watthana"
    assert area.subdistrict == "Khlong Toei Nuea"
    assert area.country_code == "th"
    assert str(requests[0].url) == (
        "https://geocoder.test/reverse?lat=13.7563&lon=100.5018&format=jsonv2&addressdetails=1"
    )
    assert requests[0].headers["user-agent"] == "weather-tests/1.0"


@pytest.mark.asyncio
async def test_create_location_from_gps(client: AsyncClient) -> None:
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(200, json=GEOCODER_RESPONSE))
    )

    response = await client.post(
        "/api/v1/locations/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "Khlong Toei Nuea, Watthana, Bangkok (13.756300, 100.501800)"
    assert data["province"] == "Bangkok"
    assert data["district"] == "Watthana"
    assert data["subdistrict"] == "Khlong Toei Nuea"
    assert data["country_code"] == "TH"
    assert data["slug"].startswith("khlong-toei-nuea-watthana-bangkok-")

    duplicate = await client.post(
        "/api/v1/locations/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["detail"] == "Location for these resolved coordinates already exists."


@pytest.mark.asyncio
async def test_create_location_from_gps_rejects_invalid_coordinates(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/locations/from-gps",
        json={"latitude": 91, "longitude": 100.5018},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_location_from_gps_reports_geocoder_failure(client: AsyncClient) -> None:
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(503, json={"error": "unavailable"}))
    )

    response = await client.post(
        "/api/v1/locations/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Reverse geocoding service request failed."
