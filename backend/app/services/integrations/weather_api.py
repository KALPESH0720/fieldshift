"""Numeric pilot forecasts plus a separate official IMD warning adapter."""

import httpx

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
        result = await request_json("GET", self.url, client=self.client, attempts=self.attempts,
                                    backoff=self.backoff, params={
                "latitude": latitude, "longitude": longitude,
                "current": "precipitation,temperature_2m,wind_speed_10m",
                "hourly": "precipitation,temperature_2m,wind_speed_10m",
                "forecast_days": 7, "timezone": "UTC", "wind_speed_unit": "ms",
            })
        if not isinstance(result, dict):
            raise IntegrationUnavailable("Open-Meteo returned an unsupported response")
        current = result.get("current") or {}
        hourly = result.get("hourly") or {}
        times = hourly.get("time") or []
        rain = hourly.get("precipitation") or []
        temperatures = hourly.get("temperature_2m") or []
        winds = hourly.get("wind_speed_10m") or []
        if not times or not (len(times) == len(rain) == len(temperatures) == len(winds)):
            raise IntegrationUnavailable("Open-Meteo response omitted aligned hourly forecast fields")
        return {
            "units": {"rainfall": "mm", "temperature": "C", "wind_speed": "m/s"},
            "current": {
                "at": _utc_timestamp(current.get("time")),
                "rainfall_mm": current.get("precipitation"),
                "temperature_c": current.get("temperature_2m"),
                "wind_speed_m_s": current.get("wind_speed_10m"),
            } if current.get("time") else None,
            "forecast": [{"at": _utc_timestamp(at), "rainfall_mm": rainfall,
                          "temperature_c": temperature, "wind_speed_m_s": wind}
                         for at, rainfall, temperature, wind in zip(times, rain, temperatures, winds)],
        }


class IMDAdapter:
    """Authenticated read-only access to IMD district warning records."""

    def __init__(self, *, client: httpx.AsyncClient | None = None, url: str | None = None,
                 api_key: str | None = None, api_key_header: str | None = None,
                 attempts: int = 3, backoff: float = 0.2):
        self.client = client
        self.url = url or settings.imd_district_warning_api_url
        self.api_key = api_key or (settings.imd_api_key.get_secret_value() if settings.imd_api_key else None)
        self.api_key_header = api_key_header or settings.imd_api_key_header
        self.attempts, self.backoff = attempts, backoff

    async def district_warnings(self, district: str) -> list[dict]:
        if not self.api_key:
            raise IntegrationUnavailable("IMD API key is not configured")
        if not district.strip():
            raise ValueError("district cannot be empty")
        result = await request_json("GET", self.url, client=self.client, attempts=self.attempts,
                                    backoff=self.backoff, headers={self.api_key_header: self.api_key})
        if isinstance(result, dict):
            rows = result.get("data", result.get("records", []))
        else:
            rows = result
        if not isinstance(rows, list) or not all(isinstance(row, dict) for row in rows):
            raise IntegrationUnavailable("IMD district warning endpoint returned an unsupported response")
        key = _district_key(district)
        return [row for row in rows if _district_key(str(row.get("District", row.get("district", "")))) == key]


class WeatherAdapter:
    """Configured numerical forecast provider; IMD warnings use IMDAdapter."""

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


def _district_key(value: str) -> str:
    return " ".join(value.casefold().replace("&", "and").split())


async def fetch_forecast(latitude: float, longitude: float) -> dict | list:
    return await WeatherAdapter().forecast(latitude, longitude)
