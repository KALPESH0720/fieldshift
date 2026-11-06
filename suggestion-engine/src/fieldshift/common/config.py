"""Runtime settings, read from FIELDSHIFT_* environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    knowledge_dir: Path
    cells_path: str | None          # local file or gs:// URI of a cells.json written by pipeline P1
    cell_size_deg: float = 0.1
    season_cycle: tuple[str, ...] = ("kharif", "rabi")
    horizon_seasons: int = 2
    top_n: int = 3
    scenario: str = "ssp245"
    api_key: str | None = None
    launcher: str = "none"          # none | local | vertex: how the deep tier is started on a cache miss
    region_id: str | None = None    # region file in knowledge/regions/ (needed by the local and vertex launchers)


def load_settings() -> Settings:
    env = os.environ.get
    knowledge = Path(env("FIELDSHIFT_KNOWLEDGE_DIR") or REPO_ROOT / "knowledge")
    cells_env = env("FIELDSHIFT_CELLS_PATH")
    default_cells = REPO_ROOT / "tests" / "fixtures" / "pilot_cells.json"
    cells = cells_env or (str(default_cells) if default_cells.exists() else None)
    cycle = tuple(s.strip() for s in env("FIELDSHIFT_SEASON_CYCLE", "kharif,rabi").split(",") if s.strip())
    return Settings(
        knowledge_dir=knowledge,
        cells_path=cells,
        cell_size_deg=float(env("FIELDSHIFT_CELL_SIZE_DEG", "0.1")),
        season_cycle=cycle,
        horizon_seasons=int(env("FIELDSHIFT_HORIZON_SEASONS", "2")),
        top_n=int(env("FIELDSHIFT_TOP_N", "3")),
        scenario=env("FIELDSHIFT_SCENARIO", "ssp245"),
        api_key=env("FIELDSHIFT_API_KEY") or None,
        launcher=env("FIELDSHIFT_LAUNCHER", "none"),
        region_id=env("FIELDSHIFT_REGION") or None,
    )


@dataclass(frozen=True)
class PipelineSettings:
    """Settings for the batch side (pipelines P1-P4). Read from FIELDSHIFT_* environment variables."""
    data_root: str                      # local folder or gs:// URI (see common/paths.py)
    gcp_project: str | None = None
    gcp_region: str = "asia-south1"     # confirm Vertex Pipelines is offered in your region
    pipeline_root: str | None = None    # gs:// folder Vertex uses for pipeline artifacts
    service_account: str | None = None
    base_image: str | None = None       # container image with the fieldshift package installed
    engine_url: str | None = None       # where P2 posts finished indicators
    simulator: str = "water_balance"


def load_pipeline_settings() -> PipelineSettings:
    env = os.environ.get
    return PipelineSettings(
        data_root=env("FIELDSHIFT_DATA_ROOT") or str(REPO_ROOT / "data_local"),
        gcp_project=env("FIELDSHIFT_GCP_PROJECT") or None,
        gcp_region=env("FIELDSHIFT_GCP_REGION", "asia-south1"),
        pipeline_root=env("FIELDSHIFT_PIPELINE_ROOT") or None,
        service_account=env("FIELDSHIFT_SERVICE_ACCOUNT") or None,
        base_image=env("FIELDSHIFT_BASE_IMAGE") or None,
        engine_url=env("FIELDSHIFT_ENGINE_URL") or None,
        simulator=env("FIELDSHIFT_SIMULATOR", "water_balance"),
    )
