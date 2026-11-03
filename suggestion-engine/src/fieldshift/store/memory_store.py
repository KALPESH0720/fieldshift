"""In-memory Store for development and tests. Replace with the shared database later."""
from __future__ import annotations

import threading
from pathlib import Path
from typing import Optional

from ..common import io
from .models import ActionLog, Alert, CellFeatures, Indicator, Job, RecommendRequest, utcnow


class MemoryStore:
    def __init__(self, cells: Optional[list[CellFeatures]] = None):
        self._lock = threading.Lock()
        self._cells = {c.cell_id: c for c in (cells or [])}
        self._indicators: dict[str, dict[str, Indicator]] = {}
        self._jobs: dict[str, Job] = {}
        self._job_by_key: dict[str, str] = {}
        self._alerts: list[Alert] = []
        self._actions: list[ActionLog] = []
        self._requests: dict[str, RecommendRequest] = {}

    @classmethod
    def from_cells_file(cls, path: "str | Path | None") -> "MemoryStore":
        """Load a cells.json (local path or gs:// URI). A missing file gives an empty store."""
        if path is None or not io.exists(str(path)):
            return cls()
        data = io.read_json(str(path))
        return cls([CellFeatures.model_validate(c) for c in data["cells"]])

    # layers
    def get_cell_features(self, cell_id: str) -> Optional[CellFeatures]:
        return self._cells.get(cell_id)

    def put_cell_features(self, cell: CellFeatures) -> None:
        self._cells[cell.cell_id] = cell

    # indicators
    def get_indicators(self, cache_key: str) -> dict[str, Indicator]:
        return dict(self._indicators.get(cache_key, {}))

    def put_indicators(self, cache_key: str, indicators: list[Indicator]) -> None:
        with self._lock:
            self._indicators.setdefault(cache_key, {}).update({i.sequence: i for i in indicators})

    # jobs
    def create_job_if_absent(self, job: Job) -> tuple[Job, bool]:
        with self._lock:
            existing = self._job_by_key.get(job.cache_key)
            if existing and self._jobs[existing].status in ("queued", "running"):
                return self._jobs[existing], False
            self._jobs[job.job_id] = job
            self._job_by_key[job.cache_key] = job.job_id
            return job, True

    def get_job(self, job_id: str) -> Optional[Job]:
        return self._jobs.get(job_id)

    def update_job(self, job_id: str, **fields) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            updated = job.model_copy(update={**fields, "updated_at": utcnow()})
            self._jobs[job_id] = updated
            return updated

    # alerts
    def list_alerts(self, cell_id: str) -> list[Alert]:
        return [a for a in self._alerts if a.cell_id == cell_id]

    def put_alert(self, alert: Alert) -> None:
        self._alerts.append(alert)

    # actions and requests
    def log_action(self, action: ActionLog) -> None:
        self._actions.append(action)

    def delete_actions(self, plot_id: str) -> int:
        with self._lock:
            before = len(self._actions)
            self._actions = [a for a in self._actions if a.plot_id != plot_id]
            return before - len(self._actions)

    def list_actions(self, plot_id: Optional[str] = None) -> list[ActionLog]:
        return [a for a in self._actions if plot_id is None or a.plot_id == plot_id]

    def save_request(self, request: RecommendRequest) -> None:
        self._requests[request.request_id] = request

    def get_request(self, request_id: str) -> Optional[RecommendRequest]:
        return self._requests.get(request_id)
