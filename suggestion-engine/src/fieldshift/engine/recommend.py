"""Orchestrates one request: snap -> filter -> rules -> score -> rank -> explain.

The live path never waits on Vertex. On a cache miss it answers from the fast tier,
records one job per cache key and (optionally) asks a launcher to start the deep tier.
"""
from __future__ import annotations

import hashlib
from typing import Callable, Optional

from ..common.config import Settings
from ..common.logging import get_logger
from ..common.seasons import next_seasons, season_key
from ..common.versions import MODEL_VERSION
from ..grid.cache_key import build_cache_key, sequence_key
from ..grid.snap import snap
from ..store.base import Store
from ..store.models import (
    Economics, Excluded, Job, Option, PriceBasis, RecommendRequest, RecommendResponse,
    ScoreSet, Uncertainty, Versions,
)
from .confidence import assess, downgrade
from .explain import explain_option, load_catalog
from .filter import CropFit, screen_crop
from .ranking import Ranked, rank_sequences
from .rules import KnowledgeBase, hard_violations, soft_hits
from .scoring import Econ, SeqEval, build_econ, make_slot, normalize_returns, resolve_weights

log = get_logger("fieldshift.engine")
MAX_CANDIDATES = 5000


class Engine:
    def __init__(self, kb: KnowledgeBase, store: Store, settings: Settings,
                 launcher: Optional[Callable[[Job], None]] = None):
        self.kb = kb
        self.store = store
        self.settings = settings
        self.launcher = launcher
        self.catalog = load_catalog()
        if not kb.reviewed:
            log.warning("knowledge base is not agronomist-reviewed; do not release to farmers")

    # ------------------------------------------------------------------
    def recommend(self, req: RecommendRequest) -> RecommendResponse:
        s = self.settings
        cell = snap(req.location.lat, req.location.lon, s.cell_size_deg)
        features = self.store.get_cell_features(cell.cell_id)
        notes: list[str] = []
        missing: list[str] = []
        if features is None:
            missing.append("climate_layer")
        if not self.kb.reviewed:
            notes.append("KNOWLEDGE_NOT_REVIEWED")
        if features is not None and features.synthetic:
            notes.append("SYNTHETIC_CELL_DATA")

        horizon = req.horizon_seasons or s.horizon_seasons
        all_seasons = next_seasons(req.season, horizon, s.season_cycle)
        history = self._history(req, notes, missing)
        econ = build_econ(req)
        weights = resolve_weights(req.preferences)

        soil_class = req.soil.texture or (features.soil_class if features else None) or "unknown"
        cache_key = build_cache_key(cell.cell_id, soil_class, s.scenario, MODEL_VERSION,
                                    self.kb.params_version, self.kb.rules_version, req.irrigation)

        fits: dict[tuple[str, str], CropFit] = {}

        def fit_for(season: str, crop) -> CropFit:
            k = (season, crop.id)
            if k not in fits:
                fits[k] = screen_crop(crop, season, features, req.soil, req.irrigation, s.scenario)
            return fits[k]

        seqs: list[SeqEval] = []
        used = horizon
        for used in range(horizon, 0, -1):
            seqs = self._enumerate(all_seasons[:used], history, econ, fit_for)
            if seqs:
                break
        if seqs and used < horizon:
            notes.append("HORIZON_REDUCED")

        indicators = self.store.get_indicators(cache_key)
        for sq in seqs:
            ind = indicators.get(sequence_key(sq.crops))
            if ind:
                sq.apply_indicator(ind)
        normalize_returns(seqs)

        seed = int(hashlib.sha256((cache_key + repr(sorted(weights.items()))).encode()).hexdigest()[:8], 16)
        ranked = rank_sequences(seqs, weights, seed)
        top = ranked[: s.top_n]

        excluded = self._excluded_first(history, fit_for, all_seasons[0])
        status = "refined" if top and all(r.seq.refined for r in top) else "fast"

        job_id = None
        if status == "fast" and top:
            job, created = self.store.create_job_if_absent(
                Job(cache_key=cache_key, request_id=req.request_id, cell_id=cell.cell_id,
                    sequences=[sequence_key(r.seq.crops) for r in ranked[:10]]))
            job_id = job.job_id
            if created and self.launcher:
                self.launcher(job)

        for r in top:
            for slot in r.seq.slots:
                for m in slot.missing:
                    if m not in missing:
                        missing.append(m)
        gap = (top[0].total - top[1].total) if len(top) > 1 else None
        conf = assess(missing, notes, len(top), gap)
        if not top:
            notes.append("NO_FEASIBLE_OPTION")

        options = [self._option(i + 1, r, top, conf.level, features, req) for i, r in enumerate(top)]
        self.store.save_request(req)
        return RecommendResponse(
            request_id=req.request_id,
            status=status,
            grid_cell_id=cell.cell_id,
            versions=Versions(model=MODEL_VERSION, rules=self.kb.rules_version, params=self.kb.params_version,
                              layer=features.layer_version if features else None),
            options=options,
            excluded_first_season=excluded,
            confidence=conf.level,
            needs_human_review=conf.needs_human_review,
            missing_inputs=missing,
            notes=notes,
            job_id=job_id,
        )

    # ------------------------------------------------------------------
    def _history(self, req: RecommendRequest, notes: list[str], missing: list[str]) -> list[str]:
        past = [h for h in req.crop_history if season_key(h.season) < season_key(req.season)]
        past.sort(key=lambda h: season_key(h.season), reverse=True)
        ids = []
        for h in past:
            if self.kb.crop(h.crop) is None:
                notes.append(f"UNKNOWN_HISTORY_CROP:{h.crop}")
            ids.append(h.crop)
        if not ids:
            missing.append("crop_history")
        return ids

    def _enumerate(self, seasons: list[str], history: list[str], econ: Econ, fit_for) -> list[SeqEval]:
        out: list[SeqEval] = []

        def rec(idx: int, hist: list[str], slots: list) -> None:
            if len(out) >= MAX_CANDIDATES:
                return
            if idx == len(seasons):
                out.append(SeqEval(slots))
                return
            for crop in self.kb.crops.values():
                fit = fit_for(seasons[idx], crop)
                if fit.excluded or hard_violations(self.kb, crop, hist):
                    continue
                slot = make_slot(self.kb, crop, seasons[idx], hist, fit, econ, soft_hits(self.kb, crop, hist))
                rec(idx + 1, [crop.id] + hist, slots + [slot])

        rec(0, history, [])
        return out

    def _excluded_first(self, history: list[str], fit_for, season: str) -> list[Excluded]:
        out = []
        for crop in self.kb.crops.values():
            fit = fit_for(season, crop)
            if fit.excluded:
                if fit.excluded != "SEASON_MISMATCH":  # out-of-season crops are not interesting to show
                    out.append(Excluded(crop=crop.id, code=fit.excluded, params=fit.excluded_params))
                continue
            hits = hard_violations(self.kb, crop, history)
            if hits:
                out.append(Excluded(crop=crop.id, code=hits[0].code, params=hits[0].params))
        return out

    def _option(self, rank: int, r: Ranked, shown: list[Ranked], level: str, features, req) -> Option:
        seq = r.seq
        reasons, trade_off = explain_option(self.catalog, self.kb, r, shown)
        own_missing = any(m.startswith(("price:", "cost:")) for sl in seq.slots for m in sl.missing)
        conf = downgrade(level) if own_missing else level

        sources = [f"knowledge:{self.kb.rules_version}"]
        sources.append(f"layer:{features.layer_version}" if features else "layer:none")
        sources += sorted({f"rule:{h.code}" for sl in seq.slots for h in sl.soft})
        basis = []
        for sl in seq.slots:
            p = self._prices(req, sl.crop)
            basis.append(PriceBasis(crop=sl.crop, used=sl.price_used, market=p.get("market"), msp=p.get("msp")))
            if sl.price_used:
                sources.append(f"price:{sl.price_used}")

        return Option(
            rank=rank,
            crop_sequence=seq.crops,
            seasons=seq.seasons,
            scores=ScoreSet(soil=round(seq.soil, 4), **{"return": round(seq.return_score, 4)},
                            water_risk=round(seq.water, 4), pest=round(seq.pest, 4), total=r.total),
            uncertainty=Uncertainty(pessimistic_total=r.pessimistic_total, top3_stability=r.stability),
            economics=Economics(
                net_return_per_acre=_r(seq.net_return),
                net_return_pessimistic_per_acre=_r(seq.net_return_dry),
                fertilizer_saved_kg_per_acre=round(seq.fert_saved_kg, 1),
                fertilizer_saving_inr_per_acre=_r(seq.fert_saving_inr) if req.fertilizer_n_price_per_kg else None,
                price_basis=basis,
            ),
            reason_codes=reasons,
            trade_off_code=trade_off,
            confidence=conf,
            sources=sorted(set(sources)),
        )

    @staticmethod
    def _prices(req: RecommendRequest, crop: str) -> dict[str, float]:
        from ..common.units import to_inr_per_quintal
        return {p.source: to_inr_per_quintal(p.price, p.unit) for p in req.prices if p.crop == crop}


def _r(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(x, 2)
