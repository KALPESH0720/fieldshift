"""Knowledge base (crops + rules) and rule application.

Hard rules exclude an option. Soft rules adjust the soil and pest scores.
History lists are ordered most recent first: history[0] was grown one season ago.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, field_validator

from ..common.units import clamp
from ..common.versions import hash_files


class Crop(BaseModel):
    id: str
    name: str
    family: str
    seasons: list[str]
    duration_days: int
    root_depth: Literal["shallow", "medium", "deep"]
    n_effect: Literal["fixes", "neutral", "demands"]
    n_credit_kg_per_acre: float = 0.0
    n_requirement_kg_per_acre: float = 0.0
    residue: Literal["low", "medium", "high"]
    water_need_mm: float
    temp_c: list[float]
    rain_mm: list[float]
    ph: list[float]
    heat_stress_days_tolerance: float = 20.0
    min_gap_same_family_seasons: Optional[int] = None
    typical_yield_q_per_acre: float
    pests: list[str] = []
    source: str = ""
    reviewed_by: Optional[str] = None

    @field_validator("temp_c", "rain_mm", "ph")
    @classmethod
    def _four_limits(cls, v: list[float]) -> list[float]:
        if len(v) != 4 or sorted(v) != list(v):
            raise ValueError("limits must be 4 ascending values [abs_min, opt_min, opt_max, abs_max]")
        return v


@dataclass(frozen=True)
class RuleHit:
    code: str
    params: dict = field(default_factory=dict)
    effect: float = 0.0
    dimension: str = ""


class KnowledgeBase:
    def __init__(self, crops: dict[str, Crop], hard: dict, soft: dict, params_version: str, rules_version: str):
        self.crops = crops
        self.hard = hard
        self.soft = soft
        self.params_version = params_version
        self.rules_version = rules_version

    @classmethod
    def load(cls, directory: Path) -> "KnowledgeBase":
        directory = Path(directory)
        crop_files = sorted((directory / "crops").glob("*.yaml"))
        if not crop_files:
            raise FileNotFoundError(f"no crop files in {directory / 'crops'}")
        crops = {}
        for f in crop_files:
            c = Crop.model_validate(yaml.safe_load(f.read_text(encoding="utf-8")))
            crops[c.id] = c
        hard_f, soft_f = directory / "rules" / "hard_rules.yaml", directory / "rules" / "soft_rules.yaml"
        hard = yaml.safe_load(hard_f.read_text(encoding="utf-8"))["rules"]
        soft = yaml.safe_load(soft_f.read_text(encoding="utf-8"))
        return cls(crops, hard, soft, hash_files(crop_files), hash_files([hard_f, soft_f]))

    def crop(self, crop_id: str) -> Optional[Crop]:
        return self.crops.get(crop_id)

    def name(self, crop_id: str) -> str:
        c = self.crops.get(crop_id)
        return c.name if c else crop_id

    @property
    def reviewed(self) -> bool:
        return all(c.reviewed_by for c in self.crops.values())


# ---------------------------------------------------------------------
def hard_violations(kb: KnowledgeBase, crop: Crop, history: list[str]) -> list[RuleHit]:
    hits: list[RuleHit] = []

    cfg = kb.hard.get("SAME_CROP_GAP")
    if cfg:
        gap = cfg["min_gap_seasons"]
        for i, prev in enumerate(history[:gap]):
            if prev == crop.id:
                hits.append(RuleHit("SAME_CROP_GAP", {"required_gap_seasons": gap, "seasons_since": i + 1}))
                break

    cfg = kb.hard.get("FAMILY_GAP")
    if cfg and crop.family not in cfg.get("exempt_families", []):
        gap = crop.min_gap_same_family_seasons or cfg["default_gap_seasons"]
        for i, prev_id in enumerate(history[:gap]):
            prev = kb.crop(prev_id)
            if prev and prev.family == crop.family:
                hits.append(
                    RuleHit(
                        "FAMILY_GAP",
                        {
                            "family": crop.family,
                            "required_gap_seasons": gap,
                            "seasons_since": i + 1,
                            "previous_crop": prev.id,
                        },
                    )
                )
                break
    return hits


def soft_hits(kb: KnowledgeBase, crop: Crop, history: list[str]) -> list[RuleHit]:
    cfg = kb.soft["rules"]
    hits: list[RuleHit] = []

    def add(code: str, **params) -> None:
        if code in cfg:
            hits.append(RuleHit(code, params, cfg[code]["effect"], cfg[code]["dimension"]))

    prev = kb.crop(history[0]) if history else None
    if prev:
        if crop.n_effect == "fixes" and prev.family == "Poaceae":
            add("LEGUME_AFTER_CEREAL", crop=crop.id, previous_crop=prev.id)
        if crop.n_effect == "demands" and prev.n_effect == "fixes":
            add("N_DEMANDING_AFTER_LEGUME", crop=crop.id, previous_crop=prev.id)
        if crop.n_effect == "demands" and prev.n_effect == "demands":
            add("N_DEMANDING_AFTER_N_DEMANDING", crop=crop.id, previous_crop=prev.id)
        if crop.root_depth != prev.root_depth:
            add("ALTERNATE_ROOT_DEPTH", crop=crop.id, previous_crop=prev.id)
        else:
            add("SAME_ROOT_DEPTH", crop=crop.id, previous_crop=prev.id)

    if history and "FAMILY_BREAK" in cfg:
        window = cfg["FAMILY_BREAK"].get("window_seasons", 3)
        recent = [kb.crop(h) for h in history[:window]]
        same = [p for p in recent if p and p.family == crop.family]
        if same:
            add("FAMILY_CARRYOVER", crop=crop.id, family=crop.family, previous_crop=same[0].id)
        elif all(p is not None for p in recent):
            add("FAMILY_BREAK", crop=crop.id, family=crop.family, window_seasons=window)
    return hits


def soil_base(kb: KnowledgeBase, crop: Crop) -> float:
    b = kb.soft["soil_base"]
    return clamp(0.5 + b["n_effect"][crop.n_effect] + b["residue"][crop.residue] + b["root_depth"][crop.root_depth])
