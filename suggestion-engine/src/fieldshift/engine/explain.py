"""Step 4b: turn scores and rule hits into reason codes and a trade-off code.

The engine returns codes + parameters. The frontend renders local-language sentences;
`text_en` is an English rendering for testing only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

import yaml

from ..common.config import REPO_ROOT
from ..store.models import ReasonCodeOut
from .ranking import Ranked
from .rules import KnowledgeBase

CATALOG_PATH = REPO_ROOT / "contracts" / "reason_codes.yaml"
GAP = 0.05          # a dimension is a trade-off when it trails the best option by more than this
MAX_REASONS = 3


def load_catalog(path: Path = CATALOG_PATH) -> dict:
    return yaml.safe_load(Path(path).read_text(encoding="utf-8"))["codes"]


def render_en(catalog: dict, kb: KnowledgeBase, code: str, params: dict) -> Optional[str]:
    entry = catalog.get(code)
    if not entry:
        return None
    shown = {k: (kb.name(v) if k in ("crop", "previous_crop") and isinstance(v, str) else v)
             for k, v in params.items()}
    try:
        return entry["text_en"].format(**shown)
    except KeyError:
        return entry["text_en"]


def _out(catalog, kb, code: str, params: Optional[dict] = None) -> ReasonCodeOut:
    params = params or {}
    return ReasonCodeOut(code=code, params=params, text_en=render_en(catalog, kb, code, params))


def explain_option(catalog: dict, kb: KnowledgeBase, item: Ranked, shown: list[Ranked]):
    """Return (reason_codes, trade_off_code) for one ranked option, judged against the others shown."""
    seq = item.seq
    candidates: list[tuple[float, str, dict]] = []

    for slot in seq.slots:
        for h in slot.soft:
            if h.effect > 0 and h.code in catalog:
                candidates.append((h.effect, h.code, dict(h.params)))
        if slot.fert_saved_kg > 0:
            candidates.append((0.09, "FERTILIZER_SAVING", {"crop": slot.crop, "saved_kg": round(slot.fert_saved_kg, 1)}))

    best_return = max(r.seq.return_score for r in shown)
    if seq.net_return is not None and len(shown) > 1 and seq.return_score >= best_return - 1e-9 and best_return > 0.5:
        candidates.append((0.08, "HIGHEST_NET_RETURN", {}))
    if seq.water >= 0.75:
        candidates.append((0.07, "LOW_WATER_RISK", {}))
    if any(s.crop and kb.crop(s.crop) and kb.crop(s.crop).n_effect == "fixes" for s in seq.slots):
        candidates.append((0.01, "SOIL_BUILDING", {}))

    candidates.sort(key=lambda t: -t[0])
    seen, reasons = set(), []
    for _, code, params in candidates:
        key = (code, tuple(sorted(params.items())))
        if key in seen:
            continue
        seen.add(key)
        reasons.append(_out(catalog, kb, code, params))
        if len(reasons) == MAX_REASONS:
            break

    return reasons, _trade_off(catalog, kb, item, shown)


def _trade_off(catalog, kb, item: Ranked, shown: list[Ranked]) -> ReasonCodeOut:
    s = item.seq
    best = {
        "soil": max(r.seq.soil for r in shown),
        "return": max(r.seq.return_score for r in shown),
        "water_risk": max(r.seq.water for r in shown),
        "pest": max(r.seq.pest for r in shown),
    }
    mine = {"soil": s.soil, "return": s.return_score, "water_risk": s.water, "pest": s.pest}
    gaps = {k: best[k] - mine[k] for k in best}
    dim = max(gaps, key=lambda k: gaps[k])
    if gaps[dim] > GAP:
        if dim == "return":
            if mine["soil"] >= best["soil"] - 0.02 and mine["soil"] > 0.5:
                return _out(catalog, kb, "LOWER_RETURN_BETTER_SOIL")
            return _out(catalog, kb, "LOWER_RETURN")
        return _out(catalog, kb, {"soil": "LOWER_SOIL_BENEFIT", "water_risk": "HIGHER_WATER_RISK",
                                  "pest": "HIGHER_PEST_RISK"}[dim])
    if item.total - item.pessimistic_total > 0.15:
        return _out(catalog, kb, "LESS_RELIABLE_IN_DRY_YEAR")
    return _out(catalog, kb, "NO_MAJOR_TRADE_OFF")
