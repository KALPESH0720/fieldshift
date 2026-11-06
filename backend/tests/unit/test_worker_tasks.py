from datetime import datetime, timezone

import pytest

from app.workers.celery_app import celery_app
from types import SimpleNamespace

from app.schemas.weather import WeatherForecastPoint
from app.workers.tasks import price_ingestion, reminders, weather_alerts
from config.settings import Settings


@pytest.fixture
def celery_eager():
    original = celery_app.conf.task_always_eager, celery_app.conf.task_eager_propagates
    celery_app.conf.update(task_always_eager=True, task_eager_propagates=True)
    try:
        yield
    finally:
        celery_app.conf.update(task_always_eager=original[0], task_eager_propagates=original[1])


def test_price_row_normalization_supports_agmarknet_fields():
    row = price_ingestion.normalize_price_row({
        "Commodity": "Tomato", "Market": "Nashik", "Modal_Price": "2,500",
        "Arrival_Date": "28/10/2026",
    })
    assert row["crop_name"] == "Tomato"
    assert row["mandi_name"] == "Nashik"
    assert str(row["modal_price"]) == "2500"
    assert row["date"].isoformat() == "2026-10-28"
    assert row["price_unit"] == "unknown"


def test_price_row_converts_reported_rupees_per_quintal_to_rupees_per_kg():
    row = price_ingestion.normalize_price_row({
        "Commodity": "Ragi", "Market": "Mysuru", "District": "Mysuru",
        "Modal_Price": "2,500", "Arrival_Date": "28/10/2026", "Unit": "Rs/Quintal",
    })
    assert float(row["modal_price"]) == 25
    assert row["price_unit"] == "INR/kg"
    assert row["reported_unit"] == "Rs/Quintal"
    assert row["district"] == "Mysuru"


def test_normalizes_data_gov_in_lowercase_record_schema_without_inventing_unit():
    row = price_ingestion.normalize_price_row({
        "state": "Andhra Pradesh", "district": "Prakasam", "market": "Maddipadu APMC",
        "commodity": "Bajra(Pearl Millet/Cumbu)", "variety": "Bold", "grade": "FAQ",
        "arrival_date": "31/10/2026", "min_price": 2900, "max_price": 3100, "modal_price": 3000,
    })
    assert row["crop_name"] == "Bajra(Pearl Millet/Cumbu)"
    assert row["district"] == "Prakasam" and row["state"] == "Andhra Pradesh"
    assert row["mandi_name"] == "Maddipadu APMC" and row["variety"] == "Bold" and row["grade"] == "FAQ"
    assert row["date"].isoformat() == "2026-10-31"
    assert row["price_unit"] == "unknown" and row["quality_status"] == "unit_unverified"
    assert row["modal_price"] == 3000
    assert row["reported_min_price"] == 2900 and row["reported_max_price"] == 3100
    assert row["min_price"] is None and row["max_price"] is None


def test_normalizes_data_gov_in_price_range_when_default_unit_is_configured(monkeypatch):
    monkeypatch.setattr(price_ingestion, "settings", Settings(agmarknet_default_price_unit="INR/quintal"))
    row = price_ingestion.normalize_price_row({
        "state": "Andhra Pradesh", "district": "Prakasam", "market": "Maddipadu APMC",
        "commodity": "Bajra", "variety": "Bold", "grade": "FAQ", "arrival_date": "31/10/2026",
        "min_price": 2900, "max_price": 3100, "modal_price": 3000,
    })
    assert row["price_unit"] == "INR/kg"
    assert row["modal_price"] == 30 and row["min_price"] == 29 and row["max_price"] == 31
    assert row["reported_min_price"] == 2900 and row["reported_max_price"] == 3100


@pytest.mark.asyncio
async def test_ogd_feed_uses_resource_api_key_and_bounded_offset_pagination(monkeypatch):
    import httpx
    from pydantic import SecretStr

    monkeypatch.setattr(price_ingestion, "settings", Settings(
        agmarknet_api_url="https://data.gov.in/resource/{resource_id}",
        agmarknet_resource_id="resource-123", agmarknet_api_key=SecretStr("ogd-secret"),
        agmarknet_page_size=2, agmarknet_max_pages=3,
    ))
    requests = []

    def handler(request):
        requests.append(request)
        assert request.headers["user-agent"] == "FieldShiftBackend/1.0"
        assert request.headers["accept"] == "application/json"
        if request.url.params["offset"] == "0":
            return httpx.Response(200, json={"records": [{"Commodity": "Ragi"}, {"Commodity": "Maize"}]})
        return httpx.Response(200, json={"records": [{"Commodity": "Chickpea"}]})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        rows = await price_ingestion._fetch_rows(client=client)
    assert [request.url.params["offset"] for request in requests] == ["0", "2"]
    assert all(request.url.params["api-key"] == "ogd-secret" for request in requests)
    assert [row["Commodity"] for row in rows] == ["Ragi", "Maize", "Chickpea"]


def test_price_task_executes_in_celery_eager_mode(celery_eager, monkeypatch):
    async def fake_ingest():
        return {"inserted": 2, "updated": 1, "skipped": 0}

    monkeypatch.setattr(price_ingestion, "_ingest", fake_ingest)
    result = price_ingestion.ingest_daily_prices.apply_async()
    assert result.get() == {"inserted": 2, "updated": 1, "skipped": 0}


def test_weather_alert_task_executes_in_celery_eager_mode(celery_eager, monkeypatch):
    async def fake_poll():
        return {"sent": 1, "skipped": 3, "failed": 0}

    monkeypatch.setattr(weather_alerts, "_poll_and_alert", fake_poll)
    result = weather_alerts.poll_weather_alerts.apply_async()
    assert result.get() == {"sent": 1, "skipped": 3, "failed": 0}


def test_reminder_task_executes_in_celery_eager_mode(celery_eager, monkeypatch):
    async def fake_dispatch():
        return {"sent": 4, "failed": 1, "skipped": 2}

    monkeypatch.setattr(reminders, "_dispatch_due_reminders", fake_dispatch)
    result = reminders.dispatch_reminders.apply_async()
    assert result.get() == {"sent": 4, "failed": 1, "skipped": 2}


def test_sowing_window_compression_signal_and_threshold():
    assert weather_alerts.sowing_window_is_compressed({"forecast": {"sowing_window_days_remaining": 2}}, 3)
    assert weather_alerts.sowing_window_is_compressed([{"sowing_window_compressed": True}], 0)
    assert not weather_alerts.sowing_window_is_compressed({"sowing_window_days_remaining": 4}, 3)


def test_sowing_alert_requires_planned_crop_active_reviewed_region_rule_and_rule_threshold():
    approved = SimpleNamespace(crop_name="Ragi", id=19,
                               knowledge_data={"sowing_alert_enabled": True, "sowing_alert_threshold_days": 3})
    draft_policy = SimpleNamespace(crop_name="Maize", id=20,
                                   knowledge_data={"sowing_alert_enabled": False, "sowing_alert_threshold_days": 3})
    points = [WeatherForecastPoint(at="2026-10-30T10:00:00Z",
                                   sowing_window_days_remaining_by_crop={"Ragi": 2, "Maize": 1})]
    candidates = weather_alerts.approved_sowing_alert_candidates(["Ragi", "Maize", "Bean"], [approved, draft_policy], points)
    assert [(item["crop_name"], item["days_remaining"]) for item in candidates] == [("Ragi", 2)]
    key1 = weather_alerts.sowing_alert_dedupe_key(8, "Ragi", 19, 2026)
    key2 = weather_alerts.sowing_alert_dedupe_key(8, "Ragi", 19, 2026)
    assert key1 == key2


def test_reminders_require_and_respect_due_timestamp():
    now = datetime(2026, 10, 30, 7, 0, tzinfo=timezone.utc)
    assert reminders.is_due({"due_at": "2026-10-30T06:00:00Z"}, now)
    assert not reminders.is_due({"due_at": "2026-10-30T08:00:00Z"}, now)
    assert not reminders.is_due({}, now)


def test_periodic_schedules_are_registered():
    schedule = celery_app.conf.beat_schedule
    assert schedule["daily-agmarknet-price-ingestion"]["task"] == "field_shift.ingest_daily_prices"
    assert schedule["hourly-weather-sowing-window-alerts"]["task"] == "field_shift.poll_weather_alerts"
    assert schedule["hourly-sowing-and-fertilizer-reminders"]["task"] == "field_shift.dispatch_reminders"
