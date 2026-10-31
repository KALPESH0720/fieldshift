"""Canonical units, cache keys, freshness, and persistence for plot forecasts."""

import json
from datetime import UTC, datetime, timedelta

from fastapi import HTTPException
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.farmer import Farmer
from app.models.plot import Plot
from app.models.weather_snapshot import WeatherSnapshot
from app.schemas.weather import WeatherForecastPoint, WeatherForecastResponse, WeatherUnits
from app.services.integrations.http import IntegrationUnavailable
from app.services.integrations.weather_api import WeatherAdapter
from config.settings import settings

WEATHER_PROVIDER = settings.weather_provider


def normalize_forecast(raw: dict | list) -> tuple[dict, dict]:
    if isinstance(raw, list):
        payload = {"forecast": raw, "units": {}}
    elif isinstance(raw, dict):
        payload = raw
    else:
        raise IntegrationUnavailable("Weather provider returned an unsupported payload")
    try:
        units = WeatherUnits.model_validate(payload.get("units") or {})
    except Exception as exc:
        raise IntegrationUnavailable("Weather provider units must identify rainfall, temperature, and wind speed") from exc
    raw_points = payload.get("forecast")
    if raw_points is None and isinstance(payload.get("data"), list):
        raw_points = payload["data"]
    if not isinstance(raw_points, list):
        raise IntegrationUnavailable("Weather provider response omitted forecast points")
    normalized = []
    for point in raw_points:
        if not isinstance(point, dict):
            raise IntegrationUnavailable("Weather forecast point must be an object")
        try:
            timestamp = point.get("at", point.get("timestamp", point.get("time")))
            if timestamp is None:
                raise ValueError("missing timestamp")
            timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00")) if isinstance(timestamp, str) else timestamp
            if timestamp.tzinfo is None or timestamp.utcoffset() is None:
                raise ValueError("timestamp requires a timezone")
            rainfall = point.get("rainfall_mm", point.get("rainfall"))
            temp = point.get("temperature_c", point.get("temperature"))
            wind = point.get("wind_speed_m_s", point.get("wind_speed"))
            if rainfall is not None and "rainfall_mm" not in point:
                if units.rainfall is None:
                    raise ValueError("provider omitted rainfall units")
                rainfall = float(rainfall) * (25.4 if units.rainfall == "in" else 1)
            if temp is not None and "temperature_c" not in point:
                if units.temperature is None:
                    raise ValueError("provider omitted temperature units")
                temp = (float(temp) - 32) * 5 / 9 if units.temperature == "F" else float(temp)
            if wind is not None and "wind_speed_m_s" not in point:
                if units.wind_speed is None:
                    raise ValueError("provider omitted wind-speed units")
                wind = float(wind) / 3.6 if units.wind_speed == "km/h" else float(wind)
            crops = point.get("sowing_window_days_remaining_by_crop", {})
            if not isinstance(crops, dict):
                raise ValueError("crop sowing-window values must be an object")
            crop_days = {str(key): int(value) for key, value in crops.items()}
            if any(value < 0 for value in crop_days.values()):
                raise ValueError("sowing-window days cannot be negative")
            normalized.append(WeatherForecastPoint(
                at=timestamp, rainfall_mm=rainfall, temperature_c=temp, wind_speed_m_s=wind,
                sowing_window_days_remaining_by_crop=crop_days,
            ).model_dump(mode="json"))
        except Exception as exc:
            raise IntegrationUnavailable("Weather provider returned an invalid forecast point") from exc
    current_raw = payload.get("current")
    current = None
    if current_raw is not None:
        current_data, _ = normalize_forecast({"forecast": [current_raw], "units": payload.get("units", {})})
        current = current_data["forecast"][0]
    return {"current": current, "forecast": normalized}, {
        "rainfall": "mm", "temperature": "C", "wind_speed": "m/s",
    }


def location_key(latitude: float, longitude: float) -> str:
    return f"{latitude:.3f}:{longitude:.3f}"


def cache_key(location: str) -> str:
    return f"weather:v1:{WEATHER_PROVIDER}:{location}"


def _response(snapshot: WeatherSnapshot, plot_id: int, cached: bool) -> WeatherForecastResponse:
    return WeatherForecastResponse(
        plot_id=plot_id, provider=snapshot.provider, latitude=snapshot.latitude,
        longitude=snapshot.longitude, location_key=snapshot.location_key, units=snapshot.units,
        fetched_at=snapshot.fetched_at, expires_at=snapshot.expires_at,
        current=snapshot.forecast.get("current"),
        forecast=snapshot.forecast.get("forecast", []), cached=cached,
    )


async def forecast_for_plot(
    session: AsyncSession, farmer: Farmer, plot: Plot, redis: Redis,
    *, adapter: WeatherAdapter | None = None,
) -> WeatherForecastResponse:
    if plot.location is None:
        raise HTTPException(status_code=422, detail="Plot needs a Point or Polygon location before weather lookup")
    latitude, longitude = (await session.execute(select(
        func.ST_Y(func.ST_Centroid(Plot.location)),
        func.ST_X(func.ST_Centroid(Plot.location)),
    ).where(Plot.id == plot.id))).one()
    latitude, longitude = float(latitude), float(longitude)
    key = location_key(latitude, longitude)
    redis_key = cache_key(key)
    try:
        cached_json = await redis.get(redis_key)
        if cached_json:
            cached = json.loads(cached_json)
            if cached.get("status") == "failed" and datetime.fromisoformat(cached["expires_at"]) > datetime.now(UTC):
                raise IntegrationUnavailable("Recent weather provider failure; retry after the cache window")
            if datetime.fromisoformat(cached["expires_at"]) > datetime.now(UTC):
                return WeatherForecastResponse.model_validate({**cached, "plot_id": plot.id, "cached": True})
    except IntegrationUnavailable:
        raise
    except Exception:
        pass  # Database snapshot/provider remain available during cache outages.
    now = datetime.now(UTC)
    snapshot = await session.scalar(select(WeatherSnapshot).where(
        WeatherSnapshot.provider == WEATHER_PROVIDER, WeatherSnapshot.location_key == key,
        WeatherSnapshot.expires_at > now, WeatherSnapshot.status == "available",
    ).order_by(WeatherSnapshot.fetched_at.desc()).limit(1))
    if snapshot is not None:
        result = _response(snapshot, plot.id, True)
        try:
            await redis.setex(redis_key, settings.weather_cache_seconds, result.model_dump_json())
        except Exception:
            pass
        return result
    recent_failure = await session.scalar(select(WeatherSnapshot).where(
        WeatherSnapshot.provider == WEATHER_PROVIDER, WeatherSnapshot.location_key == key,
        WeatherSnapshot.status == "failed", WeatherSnapshot.expires_at > now,
    ).order_by(WeatherSnapshot.fetched_at.desc()).limit(1))
    if recent_failure is not None:
        raise IntegrationUnavailable("Recent weather provider failure; retry after the failure cooldown")
    try:
        raw = await (adapter or WeatherAdapter()).forecast(latitude, longitude)
        normalized, units = normalize_forecast(raw)
        if not normalized["forecast"] and normalized["current"] is None:
            raise IntegrationUnavailable("Weather provider returned no current or forecast data")
    except Exception as exc:
        session.add(WeatherSnapshot(
            farmer_id=farmer.id, plot_id=plot.id, provider=WEATHER_PROVIDER, location_key=key,
            latitude=latitude, longitude=longitude, units={"rainfall": "mm", "temperature": "C", "wind_speed": "m/s"},
            forecast={}, status="failed", error_code=type(exc).__name__[:64], fetched_at=now,
            expires_at=now + timedelta(minutes=5),
        ))
        await session.commit()
        try:
            await redis.setex(redis_key, 300, json.dumps({"status": "failed",
                "expires_at": (now + timedelta(minutes=5)).isoformat()}))
        except Exception:
            pass
        raise IntegrationUnavailable("Weather provider failed; snapshot recorded for retry") from exc
    expires_at = now + timedelta(seconds=min(settings.weather_cache_seconds, settings.weather_freshness_seconds))
    snapshot = WeatherSnapshot(
        farmer_id=farmer.id, plot_id=plot.id, provider=WEATHER_PROVIDER, location_key=key,
        latitude=latitude, longitude=longitude, units=units, forecast=normalized, fetched_at=now,
        expires_at=expires_at, status="available",
    )
    session.add(snapshot)
    await session.commit()
    await session.refresh(snapshot)
    result = _response(snapshot, plot.id, False)
    try:
        await redis.setex(redis_key, settings.weather_cache_seconds, result.model_dump_json())
    except Exception:
        pass
    return result
