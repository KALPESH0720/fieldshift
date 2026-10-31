import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from redis.asyncio import from_url
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import CropRecord, Farmer, Plot, Season
from app.models.sync import SyncChange
from app.redis.client import get_redis

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must point to a disposable PostGIS database",
)


@pytest_asyncio.fixture
async def sync_clients():
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = from_url(TEST_REDIS_URL, encoding="utf-8", decode_responses=True)
    await redis.ping()

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: redis
    suffix = str(int(uuid4().hex[:8], 16) % 10**7).zfill(7)
    phone_a, phone_b = f"+1415{suffix}", f"+1617{suffix}"
    async with factory() as session:
        farmer_a = Farmer(phone=phone_a)
        farmer_b = Farmer(phone=phone_b)
        season = Season(name="Sync contract season", district="Mysuru", year=2026,
                        season_code="kharif", start_month=6, end_month=10)
        session.add_all([farmer_a, farmer_b, season])
        await session.flush()
        plot_a = Plot(farmer_id=farmer_a.id, name="A field", area_acres=1,
                      updated_at=datetime.now(UTC) - timedelta(minutes=3))
        plot_b = Plot(farmer_id=farmer_b.id, name="B field", area_acres=1)
        session.add_all([plot_a, plot_b])
        await session.flush()
        crop_a = CropRecord(plot_id=plot_a.id, season_id=season.id, crop_name="Wheat",
                            updated_at=datetime.now(UTC) - timedelta(minutes=3))
        session.add(crop_a)
        await session.commit()
        ids = {"farmer_a": farmer_a.id, "farmer_b": farmer_b.id, "season": season.id,
               "plot_a": plot_a.id, "plot_b": plot_b.id, "crop_a": crop_a.id}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, {"a": {"Authorization": f"Bearer {create_access_token(phone_a)}"},
                       "b": {"Authorization": f"Bearer {create_access_token(phone_b)}"}}, factory, ids
    app.dependency_overrides.clear()
    await redis.aclose()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def op(operation_id, entity, entity_id, action, data, updated_at=None):
    timestamp = updated_at or datetime.now(UTC) - timedelta(seconds=10)
    return {
        "operation_id": operation_id,
        "entity": entity,
        "entity_id": entity_id,
        "action": action,
        "updated_at": timestamp.isoformat() if isinstance(timestamp, datetime) else timestamp,
        "data": data,
    }


@pytest.mark.asyncio
async def test_sync_create_remap_retry_and_cursor_paging(sync_clients):
    client, headers, factory, ids = sync_clients
    response = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "limit": 1, "operations": [
            op("create-plot", "plot", "local:plot:1", "create", {
                "name": "Offline plot", "area_value": 2, "area_unit": "acre",
                "location": {"type": "Point", "coordinates": [76.6, 12.3]},
            }),
            op("create-history", "crop_record", "local:history:1", "create", {
                "plot_id": "local:plot:1", "season_id": ids["season"], "crop_name": "Ragi",
            }),
        ],
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accepted_operation_ids"] == ["create-plot", "create-history"]
    assert body["operation_results"][1]["entity_id"].isdigit()
    plot_server_id = int(body["operation_results"][0]["entity_id"])
    history_server_id = int(body["operation_results"][1]["entity_id"])
    assert body["has_more"] is True
    page2 = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "cursor": body["next_cursor"], "limit": 1, "operations": [],
    })
    assert page2.status_code == 200
    assert page2.json()["server_changes"][0]["entity_id"] == str(history_server_id)
    assert page2.json()["has_more"] is False

    retry = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "operations": [op("create-plot", "plot", "local:plot:1", "create", {"name": "Changed retry", "area_acres": 9})],
    })
    assert retry.status_code == 200
    assert retry.json()["operation_results"][0]["status"] == "duplicate"
    async with factory() as session:
        assert await session.scalar(select(func.count(Plot.id)).where(Plot.id == plot_server_id)) == 1
        assert await session.scalar(select(func.count(CropRecord.id)).where(CropRecord.id == history_server_id)) == 1


@pytest.mark.asyncio
async def test_two_devices_resolve_conflict_and_other_farmer_cannot_mutate(sync_clients):
    client, headers, factory, ids = sync_clients
    first_time = datetime.now(UTC) + timedelta(minutes=1)
    first = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "operations": [op("same-op-id", "crop_record", str(ids["crop_a"]),
            "update", {"crop_name": "Finger millet"}, first_time)],
    })
    assert first.json()["operation_results"][0]["status"] == "applied"
    second = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-b", "operations": [op("same-op-id", "crop_record", str(ids["crop_a"]),
            "update", {"crop_name": "Barley"}, first_time - timedelta(seconds=20))],
    })
    assert second.json()["operation_results"][0]["status"] == "conflict"
    assert second.json()["conflicts"][0]["winner"] == "server"
    second_device_pull = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-c", "cursor": "0", "operations": [],
    })
    assert second_device_pull.status_code == 200
    assert any(row["data"].get("crop_name") == "Finger millet"
               for row in second_device_pull.json()["server_changes"])
    async with factory() as session:
        assert (await session.get(CropRecord, ids["crop_a"])).crop_name == "Finger millet"

    forbidden = await client.post("/api/v1/sync", headers=headers["b"], json={
        "client_id": "device-b", "operations": [op("cross-farmer", "plot", str(ids["plot_a"]),
            "update", {"name": "stolen"}, datetime.now(UTC) + timedelta(minutes=1))],
    })
    assert forbidden.json()["operation_results"][0]["status"] == "rejected"
    async with factory() as session:
        assert (await session.get(Plot, ids["plot_a"])).name == "A field"


@pytest.mark.asyncio
async def test_sync_partial_failures_future_bad_timestamp_and_delete_tombstone(sync_clients):
    client, headers, _, ids = sync_clients
    response = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "operations": [
            op("bad-action", "plot", "local:bad", "merge", {"name": "x"}),
            op("bad-entity", "weather", "local:bad-weather", "create", {}),
            op("bad-time", "plot", "local:bad-time", "create", {"name": "x", "area_acres": 1}, "yesterday"),
            op("bad-time-shape", "plot", "local:bad-time-shape", "create", {"name": "x", "area_acres": 1}, {"date": "yesterday"}),
            op("future-time", "plot", "local:future", "create", {"name": "x", "area_acres": 1},
               datetime.now(UTC) + timedelta(minutes=10)),
            op("good-create", "plot", "local:good", "create", {"name": "Good plot", "area_acres": 1}),
        ],
    })
    assert response.status_code == 200
    results = response.json()["operation_results"]
    assert [row["status"] for row in results] == ["rejected"] * 5 + ["applied"]
    assert "timezone" in results[2]["error"]["message"]
    plot_id = results[5]["entity_id"]
    deleted = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "operations": [op("delete-good", "plot", plot_id, "delete", {},
            datetime.now(UTC) + timedelta(seconds=10))],
    })
    assert deleted.status_code == 200
    tombstones = [row for row in deleted.json()["server_changes"] if row["action"] == "delete"]
    assert tombstones and tombstones[-1]["entity_id"] == plot_id
    duplicate_delete = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "operations": [op("delete-good", "plot", plot_id, "delete", {})],
    })
    assert duplicate_delete.json()["operation_results"][0]["status"] == "duplicate"
    invalid_cursor = await client.post("/api/v1/sync", headers=headers["a"], json={
        "client_id": "device-a", "cursor": "999999999999", "operations": [],
    })
    assert invalid_cursor.status_code == 422
    assert "cursor=null" in invalid_cursor.json()["detail"]

