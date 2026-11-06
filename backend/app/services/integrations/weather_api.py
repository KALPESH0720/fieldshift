"""Open-Meteo forecast client with agricultural hourly and daily variables."""

import httpx
from urllib.parse import urlencode

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings


class OpenMeteoAdapter:
    """Open-Meteo's non-commercial API, normalized without inferring crop advice."""

    def __init__(self, *, client: httpx.AsyncClient | None = None, url: str | None = None,
                 attempts: int = 3, backoff: float = 0.2):
        self.client = client
        self.url = url or settings.open_meteo_api_url
        self.attempts, self.backoff = attempts, backoff

    async def forecast(self, latitude: float, longitude: float) -> dict | list:
        if not self.url:
            raise IntegrationUnavailable("Open-Meteo forecast URL is not configured")
        hourly_variables = (
            "temperature_2m,relative_humidity_2m,dew_point_2m,apparent_temperature,"
            "precipitation_probability,precipitation,rain,showers,snowfall,weather_code,"
            "pressure_msl,surface_pressure,cloud_cover,evapotranspiration,et0_fao_evapotranspiration,"
            "vapour_pressure_deficit,wind_speed_10m,wind_direction_10m,wind_gusts_10m,"
            "soil_temperature_0cm,soil_temperature_6cm,soil_temperature_18cm,soil_temperature_54cm,"
            "soil_moisture_0_to_1cm,soil_moisture_1_to_3cm,soil_moisture_3_to_9cm,"
            "soil_moisture_9_to_27cm,soil_moisture_27_to_81cm"
        )
        current_variables = (
            "temperature_2m,relative_humidity_2m,apparent_temperature,precipitation,rain,showers,"
            "snowfall,weather_code,cloud_cover,pressure_msl,surface_pressure,wind_speed_10m,"
            "wind_direction_10m,wind_gusts_10m"
        )
        daily_variables = (
            "weather_code,temperature_2m_max,temperature_2m_min,apparent_temperature_max,"
            "apparent_temperature_min,uv_index_max,sunrise,sunset,daylight_duration,sunshine_duration,"
            "rain_sum,showers_sum,snowfall_sum,precipitation_sum,precipitation_hours,"
            "precipitation_probability_max,wind_speed_10m_max,wind_gusts_10m_max,"
            "wind_direction_10m_dominant,shortwave_radiation_sum,et0_fao_evapotranspiration,"
            "temperature_2m_mean,relative_humidity_2m_mean,relative_humidity_2m_max,"
            "relative_humidity_2m_min,dew_point_2m_mean,vapour_pressure_deficit_max,"
            "growing_degree_days_base_0_limit_50"
        )
        query = urlencode({
                "latitude": latitude, "longitude": longitude,
                "current": current_variables,
                "hourly": hourly_variables,
                "daily": daily_variables,
                "forecast_days": 7, "timezone": "UTC", "wind_speed_unit": "ms",
            }, safe=",")
        separator = "&" if "?" in self.url else "?"
        result = await request_json("GET", f"{self.url}{separator}{query}", client=self.client,
                                    attempts=self.attempts, backoff=self.backoff)
        if not isinstance(result, dict):
            raise IntegrationUnavailable("Open-Meteo returned an unsupported response")
        current = result.get("current") or {}
        hourly = result.get("hourly") or {}
        times = hourly.get("time") or []
        if not times:
            raise IntegrationUnavailable("Open-Meteo response omitted hourly forecast times")
        hourly_units = result.get("hourly_units") or {}
        hourly_rows = _rows_by_time(hourly, "hourly")
        daily_rows = _rows_by_time(result.get("daily") or {}, "daily")
        current_units = result.get("current_units") or {}
        daily_units = result.get("daily_units") or {}
        canonical_current = _canonical_point(current)
        canonical_forecast = [_canonical_point(row) for row in hourly_rows]
        return {
            "units": {"rainfall": "mm", "temperature": "C", "wind_speed": "m/s"},
            "current": canonical_current,
            "forecast": canonical_forecast,
            "hourly_data": hourly_rows,
            "daily_data": daily_rows,
            "variable_units": {"current": current_units, "hourly": hourly_units, "daily": daily_units},
        }


def _rows_by_time(data: dict, period: str) -> list[dict]:
    times = data.get("time")
    if not isinstance(times, list) or not times:
        if period == "daily" and not data:
            return []
        raise IntegrationUnavailable(f"Open-Meteo response omitted {period} times")
    fields = {name: values for name, values in data.items() if name != "time"}
    if any(not isinstance(values, list) or len(values) != len(times) for values in fields.values()):
        raise IntegrationUnavailable(f"Open-Meteo returned misaligned {period} fields")
    rows = []
    for index, timestamp in enumerate(times):
        time_field = {"date": timestamp} if period == "daily" else {"at": _utc_timestamp(timestamp)}
        rows.append({**time_field, **{name: values[index] for name, values in fields.items()}})
    return rows


def _canonical_point(point: dict) -> dict | None:
    timestamp = point.get("time", point.get("at"))
    if not timestamp:
        return None
    return {
        "at": _utc_timestamp(timestamp),
        "rainfall_mm": point.get("precipitation"),
        "temperature_c": point.get("temperature_2m"),
        "wind_speed_m_s": point.get("wind_speed_10m"),
    }


class WeatherAdapter:
    """Configured numerical forecast provider."""

    def __init__(self, *, client: httpx.AsyncClient | None = None, url: str | None = None,
                 attempts: int = 3, backoff: float = 0.2):
        self.client, self.url = client, url
        self.attempts, self.backoff = attempts, backoff
        self.provider = settings.weather_provider

    async def forecast(self, latitude: float, longitude: float) -> dict | list:
        if self.provider == "open_meteo":
            return await OpenMeteoAdapter(client=self.client, url=self.url,
                                          attempts=self.attempts, backoff=self.backoff).forecast(latitude, longitude)
        raise IntegrationUnavailable("Unsupported weather provider")


def _utc_timestamp(value: str | None) -> str:
    if not isinstance(value, str) or not value:
        raise IntegrationUnavailable("Weather provider omitted a timestamp")
    return value if value.endswith("Z") or "+" in value else value + "Z"


async def fetch_forecast(latitude: float, longitude: float) -> dict | list:
    return await WeatherAdapter().forecast(latitude, longitude)
