"""Start the deep tier for a job. The engine calls `launcher(job)` once per new cache key.

  LocalLauncher  - runs P2 in a background thread inside the API process (development, tests).
  VertexLauncher - submits the compiled P2 pipeline to Vertex AI. NOT run against Google Cloud from
                   the development sandbox: test it in your project (see docs/runbook.md).
"""
from __future__ import annotations

import threading
from typing import Callable, Optional

from ..common.config import PipelineSettings, Settings
from ..common.logging import get_logger
from ..common.paths import Layout
from ..common.region import find_region
from ..common.vertex import submit_pipeline
from ..data.weather_store import WeatherStore
from ..store.base import Store
from ..store.models import Job
from .crop_params import load_crop_sim
from .run_p2 import P2Config, run_job

log = get_logger("fieldshift.launcher")


class LocalLauncher:
    def __init__(self, store: Store, weather_store: WeatherStore, crop_sim: dict, cfg: P2Config):
        self.store, self.weather_store, self.crop_sim, self.cfg = store, weather_store, crop_sim, cfg
        self.threads: list[threading.Thread] = []

    def __call__(self, job: Job) -> None:
        t = threading.Thread(target=run_job, args=(job.job_id, self.store, self.weather_store, self.crop_sim, self.cfg),
                             daemon=True, name=f"p2-{job.job_id[:8]}")
        self.threads.append(t)
        t.start()

    def join(self, timeout: float = 60.0) -> None:
        for t in self.threads:
            t.join(timeout)


class VertexLauncher:
    def __init__(self, project: str, location: str, template_path: str, pipeline_root: str,
                 service_account: Optional[str], engine_url: str, data_root: str, region_id: str):
        self.project, self.location = project, location
        self.template_path, self.pipeline_root = template_path, pipeline_root
        self.service_account, self.engine_url = service_account, engine_url
        self.data_root, self.region_id = data_root, region_id

    def __call__(self, job: Job) -> None:
        submit_pipeline(
            self.project, self.location, self.template_path, self.pipeline_root,
            {"job_json": job.model_dump_json(), "region_id": self.region_id,
             "data_root": self.data_root, "engine_url": self.engine_url},
            display_name=f"fieldshift-p2-{job.job_id[:8]}", service_account=self.service_account,
        )
        log.info("submitted Vertex pipeline for job %s", job.job_id)


def build_launcher(settings: Settings, pipe: PipelineSettings, store: Store) -> Optional[Callable[[Job], None]]:
    kind = settings.launcher
    if kind == "none":
        return None
    if not settings.region_id:
        raise ValueError("FIELDSHIFT_REGION must be set when FIELDSHIFT_LAUNCHER is 'local' or 'vertex'")
    if kind == "local":
        region = find_region(settings.knowledge_dir / "regions", settings.region_id)
        if region is None:
            raise ValueError(f"no region file for '{settings.region_id}'")
        cfg = P2Config(region=region, cycle=settings.season_cycle)
        return LocalLauncher(store, WeatherStore(Layout(pipe.data_root), region.id),
                             load_crop_sim(settings.knowledge_dir), cfg)
    if kind == "vertex":
        import os
        missing = [n for n, v in {"FIELDSHIFT_GCP_PROJECT": pipe.gcp_project, "FIELDSHIFT_PIPELINE_ROOT": pipe.pipeline_root,
                                  "FIELDSHIFT_ENGINE_URL": pipe.engine_url,
                                  "FIELDSHIFT_P2_TEMPLATE": os.environ.get("FIELDSHIFT_P2_TEMPLATE")}.items() if not v]
        if missing:
            raise ValueError(f"vertex launcher needs: {', '.join(missing)}")
        return VertexLauncher(pipe.gcp_project, pipe.gcp_region, os.environ["FIELDSHIFT_P2_TEMPLATE"],
                              pipe.pipeline_root, pipe.service_account, pipe.engine_url, pipe.data_root, settings.region_id)
    raise ValueError(f"unknown launcher '{kind}' (use none, local or vertex)")
