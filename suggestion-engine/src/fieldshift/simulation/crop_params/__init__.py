"""Crop parameters for the water-balance simulator, loaded from knowledge/simulation/."""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml
from pydantic import BaseModel, field_validator


class CropSim(BaseModel):
    id: str
    kc: list[float]                 # [initial, mid, end]
    stage_days: list[int]           # [initial, development, mid, late]
    root_depth_m: float
    depletion_fraction: float
    ky: float
    sowing: dict[str, tuple[int, int]]   # season name -> (month, day)

    @field_validator("kc")
    @classmethod
    def _kc(cls, v):
        if len(v) != 3 or any(x < 0 for x in v):
            raise ValueError("kc needs 3 non-negative values")
        return v

    @field_validator("stage_days")
    @classmethod
    def _stages(cls, v):
        if len(v) != 4 or any(x <= 0 for x in v):
            raise ValueError("stage_days needs 4 positive values")
        return v

    @property
    def season_days(self) -> int:
        return sum(self.stage_days)

    def kc_on(self, t: int) -> float:
        """Crop coefficient on day t after sowing (FAO-56 piecewise-linear curve)."""
        ini, dev, mid, late = self.stage_days
        kc_ini, kc_mid, kc_end = self.kc
        if t < ini:
            return kc_ini
        if t < ini + dev:
            return kc_ini + (kc_mid - kc_ini) * (t - ini) / dev
        if t < ini + dev + mid:
            return kc_mid
        if t < ini + dev + mid + late:
            return kc_mid + (kc_end - kc_mid) * (t - ini - dev - mid) / late
        return kc_end

    def root_depth_on(self, t: int) -> float:
        """Root depth grows linearly from 0.3 m (or the maximum, if smaller) to the maximum by the end of development."""
        zmin = min(0.3, self.root_depth_m)
        grow = self.stage_days[0] + self.stage_days[1]
        return zmin + (self.root_depth_m - zmin) * min(1.0, t / grow)


def load_crop_sim(directory: Path | str) -> dict[str, CropSim]:
    path = Path(directory) / "simulation" / "crop_sim_params.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {cid: CropSim.model_validate({"id": cid, **p}) for cid, p in raw["crops"].items()}


def get(params: dict[str, CropSim], crop_id: str) -> Optional[CropSim]:
    return params.get(crop_id)
