"""Poll weather forecasts and deliver sowing-window compression alerts."""

from datetime import UTC, datetime

from celery.utils.log import get_task_logger
from redis.asyncio import from_url
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError

from app.models.alert import Alert
from app.models.crop_rule import CropRule
from app.models.farmer import Farmer
from app.models.farmer_preferences import FarmerPreferences
from app.models.plot import Plot
from app.services.integrations.http import IntegrationUnavailable
from app.services.weather import forecast_for_plot
from app.workers.celery_app import celery_app
from app.workers.tasks.common import WorkerSession, run_async
from config.settings import settings

logger = get_task_logger(__name__)


def sowing_window_is_compressed(forecast: dict | list, threshold_days: int | None = None) -> bool:
    """Read an explicit window signal emitted by the configured forecast adapter."""
    threshold = settings.sowing_window_alert_threshold_days if threshold_days is None else threshold_days
    entries = forecast if isinstance(forecast, list) else [forecast]
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        nested = entry.get("forecast") or entry.get("data")
        if isinstance(nested, (dict, list)):
            if sowing_window_is_compressed(nested, threshold):
                return True
        if entry.get("sowing_window_compressed") is True:
            return True
        days = entry.get("sowing_window_days_remaining", entry.get("days_until_sowing_window_closes"))
        if days is not None:
            try:
                if int(days) <= threshold:
                    return True
            except (TypeError, ValueError):
                continue
    return False


def _coordinates(value) -> tuple[float, float] | None:
    if value is None:
        return None
    try:
        latitude, longitude = float(value[0]), float(value[1])
        if -90 <= latitude <= 90 and -180 <= longitude <= 180:
            return latitude, longitude
    except (TypeError, ValueError, IndexError):
        return None
    return None


def approved_sowing_alert_candidates(planned_crops, active_region_rules, forecast_points):
    """Select opt-in crops only when an active reviewed regional rule sets the trigger."""
    rule_map = {
        rule.crop_name.casefold(): rule for rule in active_region_rules
        if (rule.knowledge_data or {}).get("sowing_alert_enabled") is True
        and (rule.knowledge_data or {}).get("sowing_alert_threshold_days") is not None
    }
    remaining_by_crop: dict[str, list[int]] = {}
    for point in forecast_points:
        for crop_name, days in point.sowing_window_days_remaining_by_crop.items():
            remaining_by_crop.setdefault(crop_name.casefold(), []).append(days)
    candidates = []
    for crop in planned_crops:
        rule = rule_map.get(crop.casefold())
        days = remaining_by_crop.get(crop.casefold())
        if rule is None or not days:
            continue
        remaining = min(days)
        threshold = int(rule.knowledge_data["sowing_alert_threshold_days"])
        if remaining <= threshold:
            candidates.append({"rule": rule, "crop_name": rule.crop_name,
                               "days_remaining": remaining, "threshold_days": threshold})
    return candidates


def sowing_alert_dedupe_key(plot_id: int, crop_name: str, rule_id: int, year: int) -> str:
    return f"sowing-window:{plot_id}:{crop_name.casefold()}:{rule_id}:{year}"


async def _poll_and_alert() -> dict:
    created = skipped = failed = snapshots = 0
    redis = from_url(settings.redis_url, encoding="utf-8", decode_responses=True)
    try:
        async with WorkerSession() as session:
            rows = (await session.scalars(select(Plot).where(
                Plot.location.is_not(None), Plot.is_archived.is_(False),
            ).order_by(Plot.id))).all()
            for plot in rows:
                farmer = await session.get(Farmer, plot.farmer_id)
                if farmer is None:
                    skipped += 1
                    continue
                try:
                    forecast = await forecast_for_plot(session, farmer, plot, redis)
                    snapshots += 1
                except Exception as exc:
                    logger.warning("Weather snapshot failed plot_id=%s error_type=%s", plot.id, type(exc).__name__)
                    failed += 1
                    continue
                preferences = await session.get(FarmerPreferences, farmer.id)
                if not preferences or not preferences.weather_alerts_enabled or not preferences.planned_crops or not plot.district:
                    skipped += 1
                    continue
                crop_rules = (await session.scalars(select(CropRule).where(
                    CropRule.status == "active", CropRule.effective_region.ilike(plot.district),
                ))).all()
                candidates = approved_sowing_alert_candidates(preferences.planned_crops, crop_rules, forecast.forecast)
                if not candidates:
                    skipped += 1
                for candidate in candidates:
                    rule = candidate["rule"]
                    dedupe = sowing_alert_dedupe_key(plot.id, candidate["crop_name"], rule.id, datetime.now(UTC).year)
                    exists = await session.scalar(select(Alert.id).where(Alert.dedupe_key == dedupe))
                    if exists:
                        skipped += 1
                        continue
                    session.add(Alert(
                        farmer_id=farmer.id, plot_id=plot.id, alert_type="sowing_window_compressed",
                        status="pending", dedupe_key=dedupe, next_attempt_at=datetime.now(UTC),
                        payload={"template_key": "sowing_window_compressed", "crop_name": candidate["crop_name"],
                                 "days_remaining": candidate["days_remaining"], "threshold_days": candidate["threshold_days"],
                                 "crop_rule_id": rule.id, "crop_rule_version": rule.rule_version,
                                 "forecast_fetched_at": forecast.fetched_at.isoformat(),
                                 "provider": forecast.provider, "district": plot.district},
                    ))
                    try:
                        await session.commit()
                        created += 1
                    except SQLAlchemyError:
                        await session.rollback()
                        skipped += 1
    finally:
        await redis.aclose()
    return {"snapshots": snapshots, "alerts_created": created, "skipped": skipped, "failed": failed}


@celery_app.task(name="field_shift.poll_weather_alerts", autoretry_for=(IntegrationUnavailable, SQLAlchemyError),
                 retry_backoff=True, retry_kwargs={"max_retries": 3})
def poll_weather_alerts() -> dict:
    return run_async(_poll_and_alert())
