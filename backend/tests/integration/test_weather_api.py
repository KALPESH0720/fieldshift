import os
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from geoalchemy2.elements import WKTElement
from datetime import UTC, datetime, timedelta
from redis.asyncio import from_url
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import create_access_token
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models import CropRule, CropRuleReview, Farmer, Plot
from app.models.alert import Alert
from app.models.farmer_preferences import FarmerPreferences
from app.models.weather_snapshot import WeatherSnapshot
from app.redis.client import get_redis
from app.services import weather as weather_service
from app.schemas.weather import WeatherForecastPoint, WeatherForecastResponse
from app.workers.tasks import weather_alerts
from app.workers.tasks import reminders
from config.settings import settings

TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")
TEST_REDIS_URL = os.getenv("TEST_REDIS_URL", "redis://localhost:6379/15")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL must point to disposable PostGIS")


class CountingWeatherAdapter:
    def __init__(self):
        self.calls = 0

    async def forecast(self, latitude, longitude):
        self.calls += 1
        assert latitude == pytest.approx(12.9)
        assert longitude == pytest.approx(77.5)
        return {
            "units": {"rainfall": "in", "temperature": "F", "wind_speed": "km/h"},
            "current": {"at": "2026-10-30T10:00:00Z", "rainfall": 0.1, "temperature": 68, "wind_speed": 18},
            "forecast": [{"at": "2026-10-30T12:00:00Z", "rainfall": 0.25,
                          "sowing_window_days_remaining_by_crop": {"Ragi": 2}}],
        }


class FakeRedis:
    def __init__(self):
        self.data = {}

    async def get(self, key):
        return self.data.get(key)

    async def setex(self, key, _seconds, value):
        self.data[key] = value


@pytest_asyncio.fixture
async def weather_client(monkeypatch):
    engine = create_async_engine(TEST_DATABASE_URL)
    async with engine.begin() as connection:
        await connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    redis = FakeRedis()
    adapter = CountingWeatherAdapter()
    monkeypatch.setattr(weather_service, "WeatherAdapter", lambda: adapter)

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_redis] = lambda: redis
    suffix = uuid4().hex[:12]
    phone_a, phone_b = f"+1415{suffix}", f"+1617{suffix}"
    async with factory() as session:
        farmer_a, farmer_b = Farmer(phone=phone_a), Farmer(phone=phone_b)
        session.add_all([farmer_a, farmer_b])
        await session.flush()
        plot_a = Plot(farmer_id=farmer_a.id, name="Forecast plot", area_acres=1, district="Mysuru",
                      location=WKTElement("POINT(77.5 12.9)", srid=4326))
        plot_b = Plot(farmer_id=farmer_b.id, name="Other farmer plot", area_acres=1,
                      location=WKTElement("POINT(77.5 12.9)", srid=4326))
        session.add_all([plot_a, plot_b])
        await session.commit()
        ids = {"a": plot_a.id, "b": plot_b.id, "farmer_a": farmer_a.id}
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client, {"a": {"Authorization": f"Bearer {create_access_token(phone_a)}"},
                       "b": {"Authorization": f"Bearer {create_access_token(phone_b)}"}}, factory, redis, adapter, ids
    app.dependency_overrides.clear()
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.mark.asyncio
async def test_weather_is_owner_scoped_normalized_cached_and_persisted(weather_client):
    client, headers, factory, _, adapter, ids = weather_client
    first = await client.get(f"/api/v1/weather/plots/{ids['a']}/forecast", headers=headers["a"])
    assert first.status_code == 200, first.text
    payload = first.json()
    assert payload["cached"] is False
    assert payload["current"]["rainfall_mm"] == pytest.approx(2.54)
    assert payload["current"]["temperature_c"] == pytest.approx(20)
    assert payload["current"]["wind_speed_m_s"] == pytest.approx(5)
    assert payload["forecast"][0]["sowing_window_days_remaining_by_crop"]["Ragi"] == 2
    second = await client.get(f"/api/v1/weather/plots/{ids['a']}/forecast", headers=headers["a"])
    assert second.json()["cached"] is True
    assert adapter.calls == 1
    unauthorized = await client.get(f"/api/v1/weather/plots/{ids['a']}/forecast", headers=headers["b"])
    assert unauthorized.status_code == 404
    async with factory() as session:
        snapshot = await session.get(WeatherSnapshot, 1)
        assert snapshot.units == {"rainfall": "mm", "temperature": "C", "wind_speed": "m/s"}
        assert snapshot.forecast["forecast"][0]["rainfall_mm"] == pytest.approx(6.35)


@pytest.mark.asyncio
async def test_farmer_can_opt_in_preferences_and_only_read_own_alerts(weather_client):
    client, headers, factory, _, _, ids = weather_client
    preferences = await client.put("/api/v1/weather/preferences", headers=headers["a"], json={
        "weather_alerts_enabled": True, "reminders_enabled": True, "sms_enabled": True,
        "quiet_hours_start": "21:00:00", "quiet_hours_end": "08:00:00",
        "timezone": "Asia/Kolkata", "language": "kn", "planned_crops": ["Ragi"],
    })
    assert preferences.status_code == 200, preferences.text
    assert preferences.json()["weather_alerts_enabled"] is True
    bad_timezone = await client.put("/api/v1/weather/preferences", headers=headers["a"], json={
        "timezone": "Not/AZone",
    })
    assert bad_timezone.status_code == 422
    async with factory() as session:
        from app.models.alert import Alert
        session.add(Alert(farmer_id=ids["farmer_a"], plot_id=ids["a"],
                          alert_type="sowing_reminder", payload={"due_at": "2026-10-30T00:00:00Z"}, status="pending"))
        await session.commit()
    own_alerts = await client.get("/api/v1/weather/alerts", headers=headers["a"])
    other_alerts = await client.get("/api/v1/weather/alerts", headers=headers["b"])
    assert own_alerts.status_code == 200 and len(own_alerts.json()) == 1
    assert other_alerts.status_code == 200 and other_alerts.json() == []


@pytest.mark.asyncio
async def test_weather_provider_failure_is_recorded_and_can_be_retried(weather_client, monkeypatch):
    client, headers, factory, _, _, ids = weather_client

    class BrokenAdapter:
        async def forecast(self, _latitude, _longitude):
            return {"units": {}, "forecast": [{"at": "not-a-time", "rainfall": 1}]}

    monkeypatch.setattr(weather_service, "WeatherAdapter", BrokenAdapter)
    failed = await client.get(f"/api/v1/weather/plots/{ids['a']}/forecast", headers=headers["a"])
    assert failed.status_code == 503
    history = await client.get(f"/api/v1/weather/plots/{ids['a']}/snapshots", headers=headers["a"])
    assert history.status_code == 200
    assert history.json()[0]["status"] == "failed"
    assert history.json()[0]["error_code"] == "IntegrationUnavailable"
    assert history.json()[0]["forecast"] == {}
    async with factory() as session:
        assert await session.scalar(select(func.count(WeatherSnapshot.id))) == 1


@pytest.mark.asyncio
async def test_weather_worker_creates_only_approved_planned_crop_alert_and_deduplicates(weather_client, monkeypatch):
    _, _, factory, _, _, ids = weather_client
    async with factory() as session:
        plot = await session.get(Plot, ids["a"])
        plot.location = WKTElement("POINT(77.5 12.9)", srid=4326)
        session.add(FarmerPreferences(farmer_id=ids["farmer_a"], weather_alerts_enabled=True,
                                      planned_crops=["Ragi"], reminders_enabled=True))
        rule = CropRule(crop_name="Ragi", rule_version=1, schema_version="1.0", status="active",
                        approved_at=datetime.now(UTC), activated_at=datetime.now(UTC),
                        source_title="Reviewed district sowing calendar", source_url="https://example.test/ragi",
                        source_version="1", effective_region="Mysuru", effective_seasons=["Kharif"],
                        knowledge_data={"sowing_alert_enabled": True, "sowing_alert_threshold_days": 3})
        session.add(rule)
        await session.flush()
        session.add_all([CropRuleReview(crop_rule_id=rule.id, reviewer_id="agro-1", decision="approve"),
                         CropRuleReview(crop_rule_id=rule.id, reviewer_id="agro-2", decision="approve")])
        await session.commit()

    @asynccontextmanager
    async def worker_session():
        async with factory() as session:
            yield session

    class WorkerRedis:
        async def aclose(self):
            return None

    async def fake_forecast(_session, farmer, plot, _redis):
        return WeatherForecastResponse(
            plot_id=plot.id, provider="test", latitude=12.9, longitude=77.5,
            location_key="12.900:77.500", units={"rainfall": "mm", "temperature": "C", "wind_speed": "m/s"},
            fetched_at=datetime.now(UTC), expires_at=datetime.now(UTC), forecast=[
                WeatherForecastPoint(at="2026-10-30T12:00:00Z",
                                     sowing_window_days_remaining_by_crop={"Ragi": 2})],
        )

    monkeypatch.setattr(weather_alerts, "WorkerSession", worker_session)
    monkeypatch.setattr(weather_alerts, "from_url", lambda *_args, **_kwargs: WorkerRedis())
    monkeypatch.setattr(weather_alerts, "forecast_for_plot", fake_forecast)
    first = await weather_alerts._poll_and_alert()
    second = await weather_alerts._poll_and_alert()
    assert first["alerts_created"] == 1
    assert second["alerts_created"] == 0
    async with factory() as session:
        rows = (await session.scalars(select(Alert).where(Alert.alert_type == "sowing_window_compressed"))).all()
        assert len(rows) == 1
        assert rows[0].payload["crop_name"] == "Ragi"
        assert rows[0].payload["days_remaining"] == 2


@pytest.mark.asyncio
async def test_alert_delivery_respects_preferences_records_receipts_retries_and_replays(weather_client, monkeypatch):
    client, headers, factory, _, _, ids = weather_client
    due_at = datetime.now(UTC).isoformat()
    async with factory() as session:
        session.add(FarmerPreferences(farmer_id=ids["farmer_a"], reminders_enabled=True,
                                      sms_enabled=True, timezone="Asia/Kolkata"))
        session.add_all([
            Alert(farmer_id=ids["farmer_a"], plot_id=ids["a"], alert_type="sowing_reminder", status="pending",
                  payload={"due_at": due_at}),
            Alert(farmer_id=ids["farmer_a"], plot_id=ids["a"], alert_type="fertilizer_reminder", status="pending",
                  payload={"due_at": due_at}),
        ])
        await session.commit()

    @asynccontextmanager
    async def worker_session():
        async with factory() as session:
            yield session

    calls = []

    async def fake_sms(_phone, message):
        calls.append(message)
        if message.startswith("A planned fertilizer"):
            raise RuntimeError("offline")

    monkeypatch.setattr(reminders, "WorkerSession", worker_session)
    monkeypatch.setattr(reminders, "send_sms_message", fake_sms)
    monkeypatch.setattr(settings, "alert_max_attempts", 2)
    monkeypatch.setattr(settings, "alert_retry_base_seconds", 30)
    now = datetime.now(UTC)
    first = await reminders._dispatch_due_reminders(now)
    assert first["sent"] == 1 and first["failed"] == 1
    second = await reminders._dispatch_due_reminders(now + timedelta(seconds=31))
    assert second["dead_lettered"] == 1
    async with factory() as session:
        rows = (await session.scalars(select(Alert).order_by(Alert.id))).all()
        assert rows[0].status == "sent"
        assert rows[0].delivery_receipts["sms"]["attempts"][0]["status"] == "sent"
        assert rows[1].status == "dead_letter"
        assert rows[1].attempt_count == 2
    dead = rows[1]
    replay = await client.post(f"/api/v1/weather/alerts/{dead.id}/replay", headers=headers["a"])
    assert replay.status_code == 200
    assert replay.json()["status"] == "pending"
