import pytest
from httpx import AsyncClient


LOCATION_PAYLOAD = {
    "name": "Tokyo",
    "slug": "tokyo",
    "latitude": 35.6762,
    "longitude": 139.6503,
    "timezone": "Asia/Tokyo",
    "country_code": "JP",
    "provider": "open_meteo",
}


@pytest.mark.asyncio
async def test_create_location(client: AsyncClient) -> None:
    response = await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "tokyo"
    assert data["latitude"] == 35.6762
    assert "id" in data


@pytest.mark.asyncio
async def test_create_location_duplicate_slug(client: AsyncClient) -> None:
    await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    response = await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_list_locations(client: AsyncClient) -> None:
    await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    response = await client.get("/api/v1/locations")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
    assert len(response.json()) >= 1


@pytest.mark.asyncio
async def test_get_location(client: AsyncClient) -> None:
    create_resp = await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    location_id = create_resp.json()["id"]
    response = await client.get(f"/api/v1/locations/{location_id}")
    assert response.status_code == 200
    assert response.json()["id"] == location_id


@pytest.mark.asyncio
async def test_get_location_not_found(client: AsyncClient) -> None:
    response = await client.get("/api/v1/locations/999999")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_location(client: AsyncClient) -> None:
    create_resp = await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    location_id = create_resp.json()["id"]
    response = await client.patch(
        f"/api/v1/locations/{location_id}",
        json={"name": "Tokyo Updated"},
    )
    assert response.status_code == 200
    assert response.json()["name"] == "Tokyo Updated"


@pytest.mark.asyncio
async def test_delete_location(client: AsyncClient) -> None:
    create_resp = await client.post("/api/v1/locations", json=LOCATION_PAYLOAD)
    location_id = create_resp.json()["id"]
    del_resp = await client.delete(f"/api/v1/locations/{location_id}")
    assert del_resp.status_code == 204
    get_resp = await client.get(f"/api/v1/locations/{location_id}")
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_location_invalid_slug(client: AsyncClient) -> None:
    bad_payload = {**LOCATION_PAYLOAD, "slug": "INVALID SLUG!", "name": "Bad"}
    response = await client.post("/api/v1/locations", json=bad_payload)
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_location_invalid_latitude(client: AsyncClient) -> None:
    bad_payload = {**LOCATION_PAYLOAD, "slug": "bad-lat", "latitude": 999.0}
    response = await client.post("/api/v1/locations", json=bad_payload)
    assert response.status_code == 422
