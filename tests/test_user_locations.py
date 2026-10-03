import httpx
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.location import Location
from app.models.user import User
from app.services.geocoding import ReverseGeocoder, get_reverse_geocoder


FIRST_AREA = {
    "address": {
        "City": "ตำบลคลองเตยเหนือ",
        "Subregion": "เขตวัฒนา",
        "Region": "กรุงเทพมหานคร",
        "CountryCode": "THA",
    }
}
SECOND_AREA = {
    "address": {
        "City": "ตำบลแสนสุข",
        "Subregion": "อำเภอเมืองชลบุรี",
        "Region": "จังหวัดชลบุรี",
        "CountryCode": "THA",
    }
}


def _geocoder(response: httpx.Response) -> ReverseGeocoder:
    return ReverseGeocoder(
        base_url="https://geocoder.test/arcgis/rest/services/World/GeocodeServer",
        user_agent="weather-tests/1.0",
        transport=httpx.MockTransport(lambda _: response),
        provider="arcgis",
    )


@pytest.mark.asyncio
async def test_create_user_and_location_from_gps(client: AsyncClient) -> None:
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(200, json=FIRST_AREA))
    )

    response = await client.post(
        "/api/v1/users/line-user-123/location/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["external_user_id"] == "line-user-123"
    assert data["location"]["latitude"] == 13.7563
    assert data["location"]["province"] == "กรุงเทพมหานคร"


@pytest.mark.asyncio
async def test_existing_user_location_update_keeps_old_location(
    client: AsyncClient, db_session
) -> None:
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(200, json=FIRST_AREA))
    )
    first = await client.post(
        "/api/v1/users/external-1/location/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(200, json=SECOND_AREA))
    )
    second = await client.post(
        "/api/v1/users/external-1/location/from-gps",
        json={"latitude": 13.2759, "longitude": 100.9286},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["location"]["id"] != first.json()["location"]["id"]
    user = (
        await db_session.execute(select(User).where(User.external_id == "external-1"))
    ).scalar_one()
    locations = list((await db_session.execute(select(Location))).scalars())
    assert user.current_location_id == second.json()["location"]["id"]
    assert len(locations) == 2


@pytest.mark.asyncio
async def test_user_gps_location_reuse(client: AsyncClient, db_session) -> None:
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(200, json=FIRST_AREA))
    )
    first = await client.post(
        "/api/v1/users/external-1/location/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )
    second = await client.post(
        "/api/v1/users/external-2/location/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["location"]["id"] == first.json()["location"]["id"]
    locations = list((await db_session.execute(select(Location))).scalars())
    assert len(locations) == 1


@pytest.mark.asyncio
async def test_user_gps_location_rejects_invalid_coordinates(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/users/external-1/location/from-gps",
        json={"latitude": 91, "longitude": 100.5018},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_user_gps_location_reports_geocoder_failure(client: AsyncClient) -> None:
    app.dependency_overrides[get_reverse_geocoder] = (
        lambda: _geocoder(httpx.Response(503, json={"error": "unavailable"}))
    )

    response = await client.post(
        "/api/v1/users/external-1/location/from-gps",
        json={"latitude": 13.7563, "longitude": 100.5018},
    )

    assert response.status_code == 502
    assert response.json()["detail"] == "Reverse geocoding service request failed."
