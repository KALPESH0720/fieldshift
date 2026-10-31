"""NASA AppEEARS point extraction for the SMAP Enhanced L3 soil-moisture product."""

import asyncio
import csv
import io
import re
import time
from datetime import date

import httpx

from app.services.integrations.http import IntegrationUnavailable, request_json
from config.settings import settings

PRODUCT_DOI = "10.5067/M20OXIZHY3RJ"
LAYERS = (
    "Soil_Moisture_Retrieval_Data_AM_soil_moisture",
    "Soil_Moisture_Retrieval_Data_AM_retrieval_qual_flag",
    "Soil_Moisture_Retrieval_Data_PM_soil_moisture_pm",
    "Soil_Moisture_Retrieval_Data_PM_retrieval_qual_flag_pm",
)


class NASASMAPAdapter:
    """Request AppEEARS point samples and normalize SMAP AM/PM retrievals.

    AppEEARS performs asynchronous processing. This adapter bounds its polling
    time and returns only the requested point series, never downloaded files.
    """

    def __init__(
        self,
        *,
        client: httpx.AsyncClient | None = None,
        url: str | None = None,
        username: str | None = None,
        password: str | None = None,
        product: str | None = None,
        attempts: int = 3,
        backoff: float = 0.2,
        poll_interval: int | None = None,
        max_wait_seconds: int | None = None,
        sleep=asyncio.sleep,
        monotonic=time.monotonic,
    ):
        self.client = client
        self.url = (url or settings.nasa_appeears_api_url).rstrip("/") + "/"
        self.username = username or settings.nasa_earthdata_username
        password_setting = settings.nasa_earthdata_password
        self.password = password or (password_setting.get_secret_value() if password_setting else None)
        self.product = product or settings.nasa_smap_product
        self.attempts, self.backoff = attempts, backoff
        self.poll_interval = poll_interval or settings.nasa_smap_poll_interval_seconds
        self.max_wait_seconds = max_wait_seconds or settings.nasa_smap_max_wait_seconds
        self.sleep, self.monotonic = sleep, monotonic

    async def fetch(self, *, bbox: tuple[float, float, float, float], start_date: str,
                    end_date: str, product: str | None = None) -> dict:
        """Legacy bbox-compatible entry point; samples its center coordinate."""
        west, south, east, north = bbox
        return await self.fetch_point(latitude=(south + north) / 2, longitude=(west + east) / 2,
                                      start_date=start_date, end_date=end_date, product=product)

    async def fetch_point(self, *, latitude: float, longitude: float, start_date: str,
                          end_date: str, plot_id: int | str = "plot", product: str | None = None) -> dict:
        if not self.username or not self.password:
            raise IntegrationUnavailable("NASA Earthdata Login credentials are not configured")
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("NASA SMAP point coordinates are outside WGS84 bounds")
        start, end = _validate_dates(start_date, end_date)
        if (end - start).days + 1 > settings.nasa_smap_max_range_days:
            raise ValueError(f"NASA SMAP date range cannot exceed {settings.nasa_smap_max_range_days} days")
        product_id = product or self.product

        if self.client is not None:
            return await self._fetch_with_client(self.client, latitude, longitude, start, end, plot_id, product_id)
        async with httpx.AsyncClient(timeout=30.0) as client:
            return await self._fetch_with_client(client, latitude, longitude, start, end, plot_id, product_id)

    async def _fetch_with_client(self, client: httpx.AsyncClient, latitude: float, longitude: float,
                                 start: date, end: date, plot_id: int | str, product: str) -> dict:
        login = await request_json(
            "POST", f"{self.url}login", client=client, attempts=self.attempts, backoff=self.backoff,
            data={"grant_type": "client_credentials"}, auth=(self.username, self.password),
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        token = login.get("token") if isinstance(login, dict) else None
        if not isinstance(token, str) or not token:
            raise IntegrationUnavailable("NASA AppEEARS authentication returned no access token")
        headers = {"Authorization": f"Bearer {token}"}
        task_payload = {
            "task_type": "point",
            "task_name": f"field-shift-{plot_id}-{start.isoformat()}-{end.isoformat()}",
            "params": {
                "dates": [{"startDate": start.strftime("%m-%d-%Y"), "endDate": end.strftime("%m-%d-%Y")}],
                "layers": [{"product": product, "layer": layer} for layer in LAYERS],
                "coordinates": [{"id": str(plot_id), "latitude": latitude, "longitude": longitude}],
            },
        }
        submitted = await request_json(
            "POST", f"{self.url}task", client=client, attempts=self.attempts,
            backoff=self.backoff, headers=headers, json=task_payload,
        )
        task_id = submitted.get("task_id") if isinstance(submitted, dict) else None
        if not isinstance(task_id, str) or not task_id:
            raise IntegrationUnavailable("NASA AppEEARS did not return a task identifier")

        await self._wait_until_done(client, task_id, headers)
        bundle = await request_json("GET", f"{self.url}bundle/{task_id}", client=client,
                                    attempts=self.attempts, backoff=self.backoff, headers=headers)
        files = bundle.get("files", []) if isinstance(bundle, dict) else []
        result_file = next((item for item in files if str(item.get("file_name", "")).endswith("-results.csv")), None)
        if result_file is None:
            raise IntegrationUnavailable("NASA AppEEARS task completed without its point result CSV")
        content = await self._download_csv(client, task_id, result_file.get("file_id"), headers)
        observations = _parse_results_csv(content, product, latitude, longitude)
        return {
            "provider": "NASA AppEEARS",
            "product": product,
            "product_doi": PRODUCT_DOI,
            "resolution_km": 9,
            "unit": "m3/m3",
            "provider_task_id": task_id,
            "observations": observations,
        }

    async def _wait_until_done(self, client: httpx.AsyncClient, task_id: str, headers: dict[str, str]) -> None:
        deadline = self.monotonic() + self.max_wait_seconds
        while self.monotonic() < deadline:
            task = await request_json("GET", f"{self.url}task/{task_id}", client=client,
                                      attempts=self.attempts, backoff=self.backoff, headers=headers)
            status = str(task.get("status", "")).casefold() if isinstance(task, dict) else ""
            if status == "done":
                return
            if status in {"error", "failed", "cancelled", "canceling"}:
                raise IntegrationUnavailable("NASA AppEEARS task did not complete successfully")
            await self.sleep(min(self.poll_interval, max(0, deadline - self.monotonic())))
        raise IntegrationUnavailable("NASA AppEEARS task exceeded its processing time limit")

    async def _download_csv(self, client: httpx.AsyncClient, task_id: str, file_id: str,
                            headers: dict[str, str]) -> str:
        if not isinstance(file_id, str) or not file_id:
            raise IntegrationUnavailable("NASA AppEEARS result bundle omitted a file identifier")
        try:
            response = await client.get(f"{self.url}bundle/{task_id}/{file_id}", headers=headers, follow_redirects=True)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise IntegrationUnavailable("NASA AppEEARS result download failed") from exc
        if len(response.content) > 25_000_000:
            raise IntegrationUnavailable("NASA AppEEARS result exceeded the permitted size")
        return response.text


async def fetch_soil_moisture(**kwargs) -> dict:
    return await NASASMAPAdapter().fetch(**kwargs)


def _validate_dates(start_date: str, end_date: str) -> tuple[date, date]:
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (TypeError, ValueError) as exc:
        raise ValueError("NASA SMAP dates must use YYYY-MM-DD format") from exc
    if end < start:
        raise ValueError("end_date must be on or after start_date")
    return start, end


def _parse_results_csv(content: str, product: str, latitude: float, longitude: float) -> list[dict]:
    try:
        rows = csv.DictReader(io.StringIO(content))
        if not rows.fieldnames:
            raise ValueError("missing CSV headers")
        columns = {_column_key(name): name for name in rows.fieldnames}
        names = {
            "date": _find_column(columns, "date"),
            "soil_moisture_am": _find_column(columns, "soil_moisture_retrieval_data_am_soil_moisture"),
            "retrieval_qual_flag_am": _find_column(columns, "soil_moisture_retrieval_data_am_retrieval_qual_flag"),
            "soil_moisture_pm": _find_column(columns, "soil_moisture_retrieval_data_pm_soil_moisture_pm"),
            "retrieval_qual_flag_pm": _find_column(columns, "soil_moisture_retrieval_data_pm_retrieval_qual_flag_pm"),
        }
        if not names["date"] or not names["soil_moisture_am"]:
            raise ValueError("result CSV omitted required SMAP layers")
        result = []
        for row in rows:
            sample_date = date.fromisoformat(row[names["date"]][:10])
            am = _number(row.get(names["soil_moisture_am"]))
            pm = _number(row.get(names["soil_moisture_pm"])) if names["soil_moisture_pm"] else None
            am_flag = _flag(row.get(names["retrieval_qual_flag_am"])) if names["retrieval_qual_flag_am"] else None
            pm_flag = _flag(row.get(names["retrieval_qual_flag_pm"])) if names["retrieval_qual_flag_pm"] else None
            result.append({
                "date": sample_date.isoformat(), "latitude": latitude, "longitude": longitude,
                "product": product, "product_doi": PRODUCT_DOI, "resolution_km": 9,
                "soil_moisture_am": am, "soil_moisture_pm": pm,
                "retrieval_qual_flag_am": am_flag, "retrieval_qual_flag_pm": pm_flag,
                "quality_am": _quality(am, am_flag), "quality_pm": _quality(pm, pm_flag),
                "unit": "m3/m3",
            })
        return result
    except (KeyError, TypeError, ValueError) as exc:
        raise IntegrationUnavailable("NASA AppEEARS returned an unsupported SMAP result CSV") from exc


def _column_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _find_column(columns: dict[str, str], suffix: str) -> str | None:
    wanted = _column_key(suffix)
    return next((original for normalized, original in columns.items() if normalized.endswith(wanted)), None)


def _number(value: str | None) -> float | None:
    if value is None or not value.strip():
        return None
    parsed = float(value)
    return None if parsed == -9999 or not 0 <= parsed <= 1 else parsed


def _flag(value: str | None) -> int | None:
    if value is None or not value.strip():
        return None
    parsed = int(float(value))
    return None if parsed == 65534 or parsed < 0 else parsed


def _quality(value: float | None, flag: int | None) -> str:
    if value is None or flag is None:
        return "unavailable"
    # NSIDC's retrieval recommended and retrieval attempted bits are bits 0 and 1.
    return "recommended" if flag & 0b11 == 0 else "not_recommended"
