"""P2 as run inside a Vertex component: read the layer and weather from storage, simulate one job,
post the indicators (or the error) to the engine, which owns the store."""
from __future__ import annotations

import os
from typing import Optional

from ..common import io
from ..common.http import HttpClient
from ..common.paths import Layout
from ..data.weather_store import WeatherStore
from ..store.memory_store import MemoryStore
from ..store.models import CellFeatures, Job
from .crop_params import load_crop_sim
from .run_p2 import P2Config, process_job, publish_via_api


def read_secret(resource: str) -> str:
    """Latest version of a Secret Manager secret, e.g. projects/PROJECT/secrets/NAME. Untested here."""
    try:
        from google.cloud import secretmanager
    except ImportError as e:  # pragma: no cover
        raise RuntimeError("pip install google-cloud-secret-manager") from e
    name = resource if "/versions/" in resource else f"{resource}/versions/latest"
    return secretmanager.SecretManagerServiceClient().access_secret_version(name=name).payload.data.decode("utf-8")


def run_remote(job_json: str, region_id: str, data_root: str, layer_version: str, engine_url: str,
               api_key_secret: Optional[str] = None, knowledge_dir: Optional[str] = None,
               regions_dir: Optional[str] = None, http: Optional[HttpClient] = None) -> dict:
    from ..common.config import REPO_ROOT
    from ..features.p1_factory import load_region_by_id

    job = Job.model_validate_json(job_json)
    layout = Layout(data_root)
    region = load_region_by_id(region_id, regions_dir)
    cells = io.read_json(layout.cells_file(region_id, layer_version))["cells"]
    store = MemoryStore([CellFeatures.model_validate(c) for c in cells])
    kdir = knowledge_dir or str(REPO_ROOT / "knowledge")
    api_key = read_secret(api_key_secret) if api_key_secret else os.environ.get("FIELDSHIFT_API_KEY")
    cfg = P2Config(region=region)
    try:
        indicators, warnings = process_job(job, store, WeatherStore(layout, region_id), load_crop_sim(kdir), cfg)
        if not indicators:
            raise RuntimeError("no sequence could be simulated: " + "; ".join(warnings[:3]))
    except Exception as e:
        publish_via_api(engine_url, api_key, job, [], error=f"{type(e).__name__}: {e}", http=http)
        raise
    publish_via_api(engine_url, api_key, job, indicators, http=http)
    return {"job_id": job.job_id, "indicators": len(indicators), "warnings": warnings}
