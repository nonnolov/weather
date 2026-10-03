import httpx
import pytest
from httpx import AsyncClient

from app.main import app
from app.services.geocoding import ReverseGeocoder, get_reverse_geocoder


ARCGIS_RESPONSE = {
    "address": {
        "City": "ตำบลแสนสุข",
        "Subregion": "อำเภอเมืองชลบุรี",
        "Region": "จังหวัดชลบุรี",
        "CountryCode": "THA",
    }
}


def _geocoder(
    response: httpx.Response,
    requests: list[httpx.Request] | None = None,
) -> ReverseGeocoder:
    def handler(request: httpx.Request) -> httpx.Response:
        if requests is not None:
            requests.append(request)
        return response

    return ReverseGeocoder(
        base_url="https://geocoder.test/arcgis/rest/services/World/GeocodeServer",
        user_agent="weather-tests/1.0",
        transport=httpx.MockTransport(handler),
        provider="arcgis",
    )


@pytest.mark.asyncio
async def test_reverse_geocoder_uses_arcgis_endpoint_and_normalizes_thai_admin_names() -> None:
    requests: list[httpx.Request] = []
    geocoder = _geocoder(httpx.Response(200, json=ARCGIS_RESPONSE), requests)

    area = await geocoder.reverse(13.264145062681225, 100.92640782280999)

    assert area.province == "ชลบุรี"
    assert area.district == "เมืองชลบุรี"
    assert area.subdistrict == "แสนสุข"
    assert area.country_code == "TH"
    assert str(requests[0].url) == (
        "https://geocoder.test/arcgis/rest/services/World/GeocodeServer/reverseGeocode"
        "?location=100.92640782280999%2C13.264145062681225&f=json&langCode=TH"
    )
    assert requests[0].headers["user-agent"] == "weather-tests/1.0"


@pytest.mark.asyncio
async def test_create_location_from_gps(client: AsyncClient) -> None:
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(200, json=ARCGIS_RESPONSE))
    )

    response = await client.post(
        "/api/v1/locations/from-gps",
        json={"latitude": 13.264145062681225, "longitude": 100.92640782280999},
    )

    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "แสนสุข, เมืองชลบุรี, ชลบุรี (13.264145, 100.926408)"
    assert data["province"] == "ชลบุรี"
    assert data["district"] == "เมืองชลบุรี"
    assert data["subdistrict"] == "แสนสุข"
    assert data["country_code"] == "TH"
    assert data["slug"].startswith("gps-location-")

    duplicate = await client.post(
        "/api/v1/locations/from-gps",
        json={"latitude": 13.264145062681225, "longitude": 100.92640782280999},
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
        json={"latitude": 13.264145062681225, "longitude": 100.92640782280999},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Reverse geocoding service request failed."
