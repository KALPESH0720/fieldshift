"""Runtime settings, read from FIELDSHIFT_* environment variables."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class Settings:
    knowledge_dir: Path
    cells_path: Path | None
    cell_size_deg: float = 0.1
    season_cycle: tuple[str, ...] = ("kharif", "rabi")
    horizon_seasons: int = 2
    top_n: int = 3
    scenario: str = "ssp245"
    api_key: str | None = None


def load_settings() -> Settings:
    env = os.environ.get
    knowledge = Path(env("FIELDSHIFT_KNOWLEDGE_DIR") or REPO_ROOT / "knowledge")
    cells_env = env("FIELDSHIFT_CELLS_PATH")
    default_cells = REPO_ROOT / "tests" / "fixtures" / "pilot_cells.json"
    cells = Path(cells_env) if cells_env else (default_cells if default_cells.exists() else None)
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
    )
