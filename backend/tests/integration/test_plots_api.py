import os

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import Farmer, Season
from app.redis.client import get_redis
from config.settings import settings
from pydantic import SecretStr

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostGIS database",
)


@pytest_asyncio.fixture
async def client():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: TestRedis()
    phone = "+919876543210"
    async with session_factory() as session:
        session.add_all(
            [
                Farmer(phone=phone, name="API test farmer"),
                Farmer(phone="+14155552671", name="Other farmer"),
                Season(name="API Test Season", start_month=6, end_month=10),
            ]
        )
        await session.commit()

    headers = {"Authorization": f"Bearer {create_access_token(phone)}"}
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client, headers

    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


class TestRedis:
    async def get(self, key):
        return None


@pytest.mark.asyncio
async def test_plot_and_history_workflow_requires_jwt(client):
    api, headers = client
    payload = {
        "name": "North field",
        "area_acres": 2.75,
        "location": {"type": "Point", "coordinates": [77.5946, 12.9716]},
        "irrigation_type": "drip",
    }

    unauthenticated = await api.get("/api/v1/plots")
    assert unauthenticated.status_code == 401

    created = await api.post("/api/v1/plots", json=payload, headers=headers)
    assert created.status_code == 201, created.text
    plot = created.json()
    plot_id = plot["id"]
    assert plot["location"]["type"] == "Point"

    listed = await api.get("/api/v1/plots", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()["items"]] == [plot_id]
    assert listed.json()["total"] == 1

    updated = await api.put(
        f"/api/v1/plots/{plot_id}",
        json={"area_acres": 3.5, "location": {"type": "Point", "coordinates": [78.0, 13.0]}},
        headers=headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["area_acres"] == 3.5
    assert updated.json()["location"]["coordinates"] == [78.0, 13.0]

    history_created = await api.post(
        f"/api/v1/plots/{plot_id}/history",
        json={
            "season_id": 1,
            "crop_name": "Rice",
            "crop_family": "Poaceae",
            "yield_kg": 1200,
            "input_costs": 7500,
        },
        headers=headers,
    )
    assert history_created.status_code == 201, history_created.text
    history = await api.get(f"/api/v1/plots/{plot_id}/history", headers=headers)
    assert history.status_code == 200
    assert history.json()["items"][0]["crop_name"] == "Rice"


@pytest.mark.asyncio
async def test_plot_area_conversion_geometry_validation_and_geojson_round_trip(client):
    api, headers = client
    polygon = {
        "type": "Polygon",
        "coordinates": [[[77.5946, 12.9716], [77.5952, 12.9716], [77.5952, 12.9722],
                         [77.5946, 12.9722], [77.5946, 12.9716]]],
    }
    created = await api.post("/api/v1/plots", json={
        "name": "Hectare field", "area_value": 0.44, "area_unit": "hectare", "location": polygon,
    }, headers=headers)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["area_unit"] == "hectare"
    assert body["area_value"] == pytest.approx(0.44)
    assert body["area_acres"] == pytest.approx(0.44 * 2.4710538147, rel=1e-4)
    fetched = await api.get(f"/api/v1/plots/{body['id']}", headers=headers)
    assert fetched.json()["location"] == polygon

    bad_order = await api.post("/api/v1/plots", json={
        "name": "Bad coordinates", "area_acres": 1,
        "location": {"type": "Point", "coordinates": [12.5, 100]},
    }, headers=headers)
    assert bad_order.status_code == 422
    invalid_polygon = await api.post("/api/v1/plots", json={
        "name": "Self intersection", "area_acres": 1,
        "location": {"type": "Polygon", "coordinates": [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]},
    }, headers=headers)
    assert invalid_polygon.status_code == 422
    inconsistent = await api.post("/api/v1/plots", json={
        "name": "Wrong area", "area_acres": 10, "location": polygon,
    }, headers=headers)
    assert inconsistent.status_code == 422


@pytest.mark.asyncio
async def test_plot_pagination_archive_restore_and_history_survival(client):
    api, headers = client
    ids = []
    for name in ("Field A", "Field B"):
        response = await api.post("/api/v1/plots", json={"name": name, "area_acres": 1}, headers=headers)
        assert response.status_code == 201, response.text
        ids.append(response.json()["id"])
    season = await api.post(f"/api/v1/plots/{ids[0]}/history", json={"season_id": 1, "crop_name": "Rice"}, headers=headers)
    assert season.status_code == 201

    first_page = await api.get("/api/v1/plots?limit=1&offset=0", headers=headers)
    assert first_page.json()["total"] == 2
    assert len(first_page.json()["items"]) == 1
    second_page = await api.get("/api/v1/plots?limit=1&offset=1", headers=headers)
    assert second_page.json()["items"][0]["id"] != first_page.json()["items"][0]["id"]

    archived = await api.delete(f"/api/v1/plots/{ids[0]}", headers=headers)
    assert archived.status_code == 204
    assert (await api.get(f"/api/v1/plots/{ids[0]}", headers=headers)).status_code == 404
    assert (await api.get(f"/api/v1/plots/{ids[0]}/history", headers=headers)).status_code == 404
    restored = await api.post(f"/api/v1/plots/{ids[0]}/restore", headers=headers)
    assert restored.status_code == 200 and restored.json()["is_archived"] is False
    history = await api.get(f"/api/v1/plots/{ids[0]}/history", headers=headers)
    assert history.json()["total"] == 1


@pytest.mark.asyncio
async def test_crop_history_duplicate_policy_crud_and_plot_ownership(client):
    api, headers = client
    plot = await api.post("/api/v1/plots", json={"name": "Owned field", "area_acres": 1}, headers=headers)
    plot_id = plot.json()["id"]
    record = await api.post(f"/api/v1/plots/{plot_id}/history", json={"season_id": 1, "crop_name": "Rice"}, headers=headers)
    assert record.status_code == 201
    duplicate = await api.post(f"/api/v1/plots/{plot_id}/history", json={"season_id": 1, "crop_name": "Rice"}, headers=headers)
    assert duplicate.status_code == 409
    updated = await api.put(f"/api/v1/plots/{plot_id}/history/{record.json()['id']}",
                            json={"crop_name": "Ragi", "yield_kg": 400}, headers=headers)
    assert updated.status_code == 200 and updated.json()["crop_name"] == "Ragi"
    history = await api.get(f"/api/v1/plots/{plot_id}/history?limit=1", headers=headers)
    assert history.json()["total"] == 1 and history.json()["items"][0]["yield_kg"] == 400

    other_headers = {"Authorization": f"Bearer {create_access_token('+14155552671')}"}
    assert (await api.get(f"/api/v1/plots/{plot_id}", headers=other_headers)).status_code == 404
    assert (await api.get(f"/api/v1/plots/{plot_id}/history", headers=other_headers)).status_code == 404
    assert (await api.delete(f"/api/v1/plots/{plot_id}/history/{record.json()['id']}", headers=other_headers)).status_code == 404
    deleted = await api.delete(f"/api/v1/plots/{plot_id}/history/{record.json()['id']}", headers=headers)
    assert deleted.status_code == 204
    assert (await api.get(f"/api/v1/plots/{plot_id}/history", headers=headers)).json()["total"] == 0


@pytest.mark.asyncio
async def test_admin_season_seed_is_idempotent_and_history_can_reference_it(client, monkeypatch):
    monkeypatch.setattr(settings, "admin_api_key", SecretStr("integration-admin-key"))
    api, headers = client
    payload = {"district": "Mysuru", "year": 2026}
    unauthorized = await api.put("/api/v1/seasons/seed", json=payload)
    assert unauthorized.status_code == 401
    first = await api.put("/api/v1/seasons/seed", json=payload, headers={"X-Admin-Key": "integration-admin-key"})
    second = await api.put("/api/v1/seasons/seed", json=payload, headers={"X-Admin-Key": "integration-admin-key"})
    assert first.status_code == 200 and len(first.json()["seasons"]) == 3
    assert [item["id"] for item in first.json()["seasons"]] == [item["id"] for item in second.json()["seasons"]]
    season_id = first.json()["seasons"][0]["id"]
    plot = await api.post("/api/v1/plots", json={"name": "Season field", "area_acres": 1}, headers=headers)
    created = await api.post(f"/api/v1/plots/{plot.json()['id']}/history",
                             json={"season_id": season_id, "crop_name": "Maize"}, headers=headers)
    assert created.status_code == 201
    admin_headers = {"X-Admin-Key": "integration-admin-key"}
    protected = await api.delete(f"/api/v1/seasons/{season_id}", headers=admin_headers)
    assert protected.status_code == 409
    custom = await api.post("/api/v1/seasons", json={
        "district": "Mysuru", "year": 2026, "season_code": "summer", "name": "Summer 2026",
        "start_month": 4, "end_month": 6,
    }, headers=admin_headers)
    assert custom.status_code == 201, custom.text
    changed = await api.put(f"/api/v1/seasons/{custom.json()['id']}", json={"end_month": 7}, headers=admin_headers)
    assert changed.status_code == 200 and changed.json()["end_month"] == 7
    removed = await api.delete(f"/api/v1/seasons/{custom.json()['id']}", headers=admin_headers)
    assert removed.status_code == 204
