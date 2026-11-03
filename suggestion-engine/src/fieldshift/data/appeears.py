"""AppEEARS (NASA Earthdata) point-sample client, used for SMAP L4 and MODIS NDVI.

Built from the AppEEARS API documentation (login, task, status, bundle). It has NOT been run
against the live service from the development sandbox; run `python scripts/check_live_access.py`
with your Earthdata credentials to confirm, and adjust product versions in smap.py / modis.py.
"""
from __future__ import annotations

import csv
import io as _io
import time
from datetime import date
from typing import Any, Callable, Optional

from ..common.http import HttpClient, HttpError

BASE_URL = "https://appeears.earthdatacloud.nasa.gov/api"


class AppeearsError(RuntimeError):
    pass


class AppeearsClient:
    def __init__(
        self,
        http: Optional[HttpClient] = None,
        base_url: str = BASE_URL,
        token: Optional[str] = None,
        poll_seconds: float = 30.0,
        timeout_seconds: float = 6 * 3600,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.http = http or HttpClient()
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.poll_seconds = poll_seconds
        self.timeout_seconds = timeout_seconds
        self._sleep = sleep
        self._clock = clock

    # -- auth ----------------------------------------------------------------
    def login(self, username: str, password: str) -> str:
        data = self.http.post_json(f"{self.base_url}/login", auth=(username, password))
        self.token = data["token"]
        return self.token

    def _headers(self) -> dict[str, str]:
        if not self.token:
            raise AppeearsError("not logged in: call login() or pass a token")
        return {"Authorization": f"Bearer {self.token}"}

    # -- tasks ---------------------------------------------------------------
    @staticmethod
    def task_payload(name: str, points: list[dict[str, Any]], layers: list[tuple[str, str]],
                     start: date, end: date) -> dict[str, Any]:
        return {
            "task_type": "point",
            "task_name": name,
            "params": {
                "dates": [{"startDate": start.strftime("%m-%d-%Y"), "endDate": end.strftime("%m-%d-%Y")}],
                "layers": [{"product": prod, "layer": lyr} for prod, lyr in layers],
                "coordinates": [
                    {"id": pt["id"], "longitude": pt["lon"], "latitude": pt["lat"], "category": "cell"}
                    for pt in points
                ],
            },
        }

    def submit_point_task(self, name, points, layers, start: date, end: date) -> str:
        payload = self.task_payload(name, points, layers, start, end)
        data = self.http.post_json(f"{self.base_url}/task", json=payload, headers=self._headers())
        return data["task_id"]

    def status(self, task_id: str) -> str:
        data = self.http.get_json(f"{self.base_url}/status/{task_id}", headers=self._headers())
        if isinstance(data, list):  # some deployments return a list of tasks
            data = next((t for t in data if t.get("task_id") == task_id), {})
        return str(data.get("status", "unknown")).lower()

    def wait(self, task_id: str) -> None:
        started = self._clock()
        while True:
            status = self.status(task_id)
            if status == "done":
                return
            if status in ("error", "failed", "deleted"):
                raise AppeearsError(f"task {task_id} ended with status '{status}'")
            if self._clock() - started > self.timeout_seconds:
                raise AppeearsError(f"task {task_id} still '{status}' after {self.timeout_seconds:.0f}s")
            self._sleep(self.poll_seconds)

    def bundle(self, task_id: str) -> list[dict[str, Any]]:
        data = self.http.get_json(f"{self.base_url}/bundle/{task_id}", headers=self._headers())
        return data["files"] if isinstance(data, dict) else data

    def download_text(self, task_id: str, file_id: str) -> str:
        return self.http.get_text(f"{self.base_url}/bundle/{task_id}/{file_id}", headers=self._headers())

    def run_point_task(self, name, points, layers, start: date, end: date) -> str:
        """Submit, wait and return the results CSV text."""
        task_id = self.submit_point_task(name, points, layers, start, end)
        self.wait(task_id)
        files = self.bundle(task_id)
        results = [f for f in files if f["file_name"].lower().endswith(".csv") and "results" in f["file_name"].lower()]
        if not results:
            raise AppeearsError(f"no results CSV in bundle for task {task_id}: {[f['file_name'] for f in files]}")
        return self.download_text(task_id, results[0]["file_id"])


def read_point_csv(text: str) -> list[dict[str, str]]:
    return list(csv.DictReader(_io.StringIO(text)))


def find_column(row: dict[str, str], needle: str) -> Optional[str]:
    for k in row:
        if needle.lower() in k.lower():
            return k
    return None


__all__ = ["AppeearsClient", "AppeearsError", "HttpError", "read_point_csv", "find_column"]
