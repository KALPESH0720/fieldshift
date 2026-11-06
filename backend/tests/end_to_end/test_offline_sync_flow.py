"""Full HTTP journey from passwordless signup through offline synchronization.

Set TEST_DATABASE_URL to a disposable PostgreSQL database with PostGIS installed.
"""

import os
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import CropRule, MarketPrice, Season
from app.redis.client import get_redis
from config.settings import settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="TEST_DATABASE_URL must point to a disposable PostGIS database",
)


class FakeRedis:
    """Small OTP-store fake for the HTTP registration journey."""

    def __init__(self):
        self.values = {}

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.values:
            return False
        self.values[key] = value
        return True

    async def getdel(self, key):
        return self.values.pop(key, None)

    async def get(self, key):
        return self.values.get(key)

    async def incr(self, key):
        self.values[key] = str(int(self.values.get(key, "0")) + 1)
        return int(self.values[key])

    async def expire(self, key, seconds):
        return key in self.values

    async def delete(self, *keys):
        for key in keys:
            self.values.pop(key, None)


@pytest_asyncio.fixture
async def journey_client(monkeypatch):
    """Disposable database and dependency overrides for the complete flow."""
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def override_get_db():
        async with session_factory() as session:
            yield session

    redis = FakeRedis()
    monkeypatch.setattr(settings, "environment", "test")
    monkeypatch.setattr(settings, "otp_provider", "development")
    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_redis] = lambda: redis
    async with session_factory() as session:
        season = Season(name="E2E Kharif", start_month=6, end_month=10)
        session.add_all(
            [
                season,
                CropRule(crop_name="Wheat", crop_family="Poaceae", root_depth="deep",
                         water_requirement="medium", nitrogen_effect=-1),
                CropRule(crop_name="Chickpea", crop_family="Fabaceae", root_depth="shallow",
                         water_requirement="low", nitrogen_effect=1),
                MarketPrice(crop_name="Chickpea", mandi_name="E2E Mandi", modal_price=75,
                            date=datetime.now(UTC).date()),
            ]
        )
        await session.commit()
        await session.refresh(season)
        season_id = season.id

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as test_client:
        yield test_client, season_id

    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_farmer_registration_to_offline_sync_journey(journey_client):
    api, season_id = journey_client
    phone = "9876543210"
    sent = await api.post("/api/v1/auth/otp/send", json={"phone": phone})
    assert sent.status_code == 202, sent.text
    assert sent.json().get("development_otp")

    verified = await api.post("/api/v1/auth/otp/verify", json={
        "phone": phone, "otp": sent.json()["development_otp"],
    })
    assert verified.status_code == 200, verified.text
    headers = {"Authorization": f"Bearer {verified.json()['access_token']}"}

    profile = await api.post("/api/v1/farmers/me", json={
        "name": "Journey Farmer", "language": "hi", "village": "Test Village",
    }, headers=headers)
    assert profile.status_code == 201, profile.text

    created_plot = await api.post("/api/v1/plots", json={
        "name": "Home field",
        "area_acres": 1.75,
        "location": {"type": "Point", "coordinates": [77.5946, 12.9716]},
        "irrigation_type": "rainfed",
    }, headers=headers)
    assert created_plot.status_code == 201, created_plot.text
    plot = created_plot.json()
    assert plot["location"]["type"] == "Point"

    history = await api.post(f"/api/v1/plots/{plot['id']}/history", json={
        "season_id": season_id,
        "crop_name": "Wheat",
        "crop_family": "Poaceae",
        "yield_kg": 800,
        "input_costs": 12000,
        "outcome_notes": "Previous season record",
    }, headers=headers)
    assert history.status_code == 201, history.text
    crop_record_id = history.json()["id"]

    recommendation = await api.post("/api/v1/recommendations", json={
        "plot_id": plot["id"], "season": "E2E Kharif", "available_water_mm": 500,
    }, headers=headers)
    assert recommendation.status_code == 200, recommendation.text
    recommendation_body = recommendation.json()
    assert recommendation_body["plot_id"] == plot["id"]
    assert recommendation_body["options"] == []
    assert recommendation_body["advisor_referral_required"] is True
    assert any("expert-approved" in note for note in recommendation_body["data_quality_notes"])

    offline_sync = await api.post("/api/v1/sync", json={
        "client_id": "e2e-phone",
        "operations": [{
            "operation_id": "e2e-crop-edit-1",
            "entity": "crop_record",
            "entity_id": str(crop_record_id),
            "action": "update",
            "updated_at": (datetime.now(UTC) + timedelta(seconds=10)).isoformat(),
            "data": {"crop_name": "Ragi", "outcome_notes": "Edited offline"},
        }],
    }, headers=headers)
    assert offline_sync.status_code == 200, offline_sync.text
    assert offline_sync.json()["accepted_operation_ids"] == ["e2e-crop-edit-1"]

    final_history = await api.get(f"/api/v1/plots/{plot['id']}/history", headers=headers)
    assert final_history.status_code == 200, final_history.text
    assert final_history.json()["items"][0]["crop_name"] == "Ragi"
