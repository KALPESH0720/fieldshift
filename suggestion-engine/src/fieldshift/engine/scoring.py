"""Step 3: score each slot and each crop sequence on soil, pest, return and water/climate risk."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from ..common.units import clamp, to_inr_per_quintal
from ..store.models import CostItem, Preferences, RecommendRequest
from .filter import CropFit
from .rules import Crop, KnowledgeBase, RuleHit, soil_base

DIMS = ("soil", "return", "water_risk", "pest")


# ---------------------------------------------------------------- weights
def resolve_weights(prefs: Preferences) -> dict[str, float]:
    """Apply flags to the farmer's weights, then normalise to sum 1."""
    w = prefs.weights.as_dict()
    flags = set(prefs.flags)
    if "low_water" in flags or "low_risk" in flags:
        w["water_risk"] += 0.15
    if "needs_cash_soon" in flags:
        w["return"] += 0.15
    total = sum(w.values())
    if total <= 0:
        w = {"soil": 0.30, "return": 0.30, "water_risk": 0.25, "pest": 0.15}
        total = 1.0
    return {k: v / total for k, v in w.items()}


# ---------------------------------------------------------------- economics
@dataclass
class Econ:
    prices: dict[str, dict[str, float]] = field(default_factory=dict)  # crop -> {'market'|'msp': INR/quintal}
    costs: dict[str, CostItem] = field(default_factory=dict)
    fert_price: Optional[float] = None


def build_econ(req: RecommendRequest) -> Econ:
    econ = Econ(fert_price=req.fertilizer_n_price_per_kg)
    for p in req.prices:
        econ.prices.setdefault(p.crop, {})[p.source] = to_inr_per_quintal(p.price, p.unit)
    for c in req.costs:
        econ.costs[c.crop] = c
    return econ


# ---------------------------------------------------------------- slot
@dataclass
class SlotEval:
    season: str
    crop: str
    soil: float
    pest: float
    water: float
    water_dry: float
    revenue: Optional[float]
    cost: Optional[float]
    fert_saved_kg: float
    fert_saving_inr: float
    price_used: Optional[str]
    soft: list[RuleHit]
    missing: list[str]

    @property
    def net_return(self) -> Optional[float]:
        if self.revenue is None or self.cost is None:
            return None
        return self.revenue - self.cost + self.fert_saving_inr

    @property
    def yield_factor_dry(self) -> float:
        # Heuristic stand-in until simulation indicators (pipeline P2) arrive.
        return clamp(self.water_dry / max(self.water, 0.01), 0.3, 1.0)


def make_slot(
    kb: KnowledgeBase, crop: Crop, season: str, history: list[str], fit: CropFit, econ: Econ, soft: list[RuleHit]
) -> SlotEval:
    soil = clamp(soil_base(kb, crop) + sum(h.effect for h in soft if h.dimension == "soil"))
    pest = clamp(0.5 + sum(h.effect for h in soft if h.dimension == "pest"))

    prices = econ.prices.get(crop.id, {})
    price_used = "market" if "market" in prices else ("msp" if "msp" in prices else None)
    cost_item = econ.costs.get(crop.id)
    yield_q = (cost_item.expected_yield_q_per_acre if cost_item and cost_item.expected_yield_q_per_acre
               else crop.typical_yield_q_per_acre)
    revenue = yield_q * prices[price_used] if price_used else None
    cost = cost_item.cost_per_acre if cost_item else None

    missing = list(fit.missing)
    if price_used is None:
        missing.append(f"price:{crop.id}")
    if cost is None:
        missing.append(f"cost:{crop.id}")

    prev = kb.crop(history[0]) if history else None
    saved_kg = 0.0
    if prev and prev.n_effect == "fixes" and crop.n_requirement_kg_per_acre > 0:
        saved_kg = min(prev.n_credit_kg_per_acre, crop.n_requirement_kg_per_acre)
    saving_inr = saved_kg * econ.fert_price if econ.fert_price else 0.0

    return SlotEval(season, crop.id, soil, pest, fit.water_score, fit.water_score_dry, revenue, cost,
                    saved_kg, saving_inr, price_used, soft, missing)


# ---------------------------------------------------------------- sequence
@dataclass
class SeqEval:
    slots: list[SlotEval]
    ind_water: Optional[float] = None
    ind_water_dry: Optional[float] = None
    ind_yield_factor_dry: Optional[float] = None
    refined: bool = False
    return_score: float = 0.5
    return_score_dry: float = 0.5

    @property
    def crops(self) -> list[str]:
        return [s.crop for s in self.slots]

    @property
    def seasons(self) -> list[str]:
        return [s.season for s in self.slots]

    def _mean(self, attr: str) -> float:
        return sum(getattr(s, attr) for s in self.slots) / len(self.slots)

    @property
    def soil(self) -> float:
        return self._mean("soil")

    @property
    def pest(self) -> float:
        return self._mean("pest")

    @property
    def water(self) -> float:
        return self.ind_water if self.ind_water is not None else self._mean("water")

    @property
    def water_dry(self) -> float:
        return self.ind_water_dry if self.ind_water_dry is not None else self._mean("water_dry")

    @property
    def net_return(self) -> Optional[float]:
        vals = [s.net_return for s in self.slots]
        return None if any(v is None for v in vals) else sum(vals)

    @property
    def net_return_dry(self) -> Optional[float]:
        if self.net_return is None:
            return None
        total = 0.0
        for s in self.slots:
            yf = self.ind_yield_factor_dry if self.ind_yield_factor_dry is not None else s.yield_factor_dry
            total += s.revenue * yf - s.cost + s.fert_saving_inr
        return total

    @property
    def fert_saved_kg(self) -> float:
        return sum(s.fert_saved_kg for s in self.slots)

    @property
    def fert_saving_inr(self) -> float:
        return sum(s.fert_saving_inr for s in self.slots)

    def apply_indicator(self, ind) -> None:
        self.ind_water = ind.water_score_median
        self.ind_water_dry = ind.water_score_pessimistic
        self.ind_yield_factor_dry = ind.yield_factor_pessimistic
        self.refined = True


def normalize_returns(seqs: list[SeqEval]) -> None:
    """Min-max net return across candidates; median and dry-year share one scale. Unknown -> 0.5."""
    vals = [v for s in seqs for v in (s.net_return, s.net_return_dry) if v is not None]
    if not vals:
        return
    lo, hi = min(vals), max(vals)
    for s in seqs:
        if s.net_return is None:
            s.return_score = s.return_score_dry = 0.5
        elif hi > lo:
            s.return_score = (s.net_return - lo) / (hi - lo)
            s.return_score_dry = (s.net_return_dry - lo) / (hi - lo)
        else:
            s.return_score = s.return_score_dry = 0.5


def total_score(seq: SeqEval, weights: dict[str, float], dry: bool = False) -> float:
    return (
        weights["soil"] * seq.soil
        + weights["return"] * (seq.return_score_dry if dry else seq.return_score)
        + weights["water_risk"] * (seq.water_dry if dry else seq.water)
        + weights["pest"] * seq.pest
    )
