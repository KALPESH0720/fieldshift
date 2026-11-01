import pytest

from fieldshift.engine.filter import screen_crop, trapezoid
from fieldshift.engine.ranking import rank_sequences
from fieldshift.engine.rules import hard_violations, soft_hits
from fieldshift.engine.scoring import SeqEval, normalize_returns, resolve_weights
from fieldshift.store.models import Preferences, Soil, Weights


def codes(hits):
    return [h.code for h in hits]


# ---- hard rules ----
def test_same_crop_and_family_blocked(kb):
    assert "SAME_CROP_GAP" in codes(hard_violations(kb, kb.crop("tomato"), ["tomato"]))
    assert "FAMILY_GAP" in codes(hard_violations(kb, kb.crop("groundnut"), ["wheat", "soybean"]))


def test_cereal_after_cereal_allowed_but_not_same_crop(kb):
    assert hard_violations(kb, kb.crop("wheat"), ["maize"]) == []
    assert codes(hard_violations(kb, kb.crop("maize"), ["maize"])) == ["SAME_CROP_GAP"]


def test_long_gap_crops_need_more_seasons(kb):
    # tomato (Solanaceae) has a 3-season gap: a Solanaceae crop 3 seasons ago still blocks it
    assert hard_violations(kb, kb.crop("tomato"), ["wheat", "maize", "tomato"]) != []
    assert hard_violations(kb, kb.crop("tomato"), ["wheat", "maize", "sorghum", "tomato"]) == []


# ---- soft rules ----
def test_legume_after_cereal_and_family_break(kb):
    c = codes(soft_hits(kb, kb.crop("chickpea"), ["maize"]))
    assert "LEGUME_AFTER_CEREAL" in c and "FAMILY_BREAK" in c


def test_cereal_after_cereal_has_pest_carryover(kb):
    assert "FAMILY_CARRYOVER" in codes(soft_hits(kb, kb.crop("wheat"), ["maize"]))


def test_no_history_triggers_no_soft_rules(kb):
    assert soft_hits(kb, kb.crop("soybean"), []) == []


# ---- filter ----
def test_trapezoid_shape():
    lim = [10, 20, 30, 40]
    assert trapezoid(5, lim) == 0 and trapezoid(45, lim) == 0
    assert trapezoid(25, lim) == 1
    assert trapezoid(15, lim) == pytest.approx(0.5)
    assert trapezoid(35, lim) == pytest.approx(0.5)


def test_rainfed_rabi_wheat_excluded_but_irrigated_ok(kb, store):
    cell = store.get_cell_features("g0.1_185_738")
    wheat = kb.crop("wheat")
    assert screen_crop(wheat, "rabi-2027", cell, Soil(), "rainfed", "ssp245").excluded == "UNSUITABLE_RAINFALL"
    assert screen_crop(wheat, "rabi-2027", cell, Soil(), "full", "ssp245").excluded is None


def test_bad_ph_excludes_and_season_mismatch(kb, store):
    cell = store.get_cell_features("g0.1_185_738")
    assert screen_crop(kb.crop("soybean"), "kharif-2027", cell, Soil(ph=3.0), "rainfed", "ssp245").excluded == "UNSUITABLE_PH"
    assert screen_crop(kb.crop("wheat"), "kharif-2027", cell, Soil(), "full", "ssp245").excluded == "SEASON_MISMATCH"


def test_missing_cell_data_is_neutral_and_reported(kb):
    fit = screen_crop(kb.crop("soybean"), "kharif-2027", None, Soil(), "rainfed", "ssp245")
    assert fit.excluded is None and fit.suitability == 0.5
    assert "climate:tmean" in fit.missing


def test_dry_year_never_scores_better_than_median(kb, store):
    cell = store.get_cell_features("g0.1_181_745")
    for crop in kb.crops.values():
        fit = screen_crop(crop, "kharif-2027", cell, Soil(), "rainfed", "ssp245")
        if not fit.excluded:
            assert fit.water_score_dry <= fit.water_score + 1e-9


# ---- weights ----
def test_weights_normalised_and_flags_shift_them():
    base = resolve_weights(Preferences())
    assert sum(base.values()) == pytest.approx(1.0)
    dry = resolve_weights(Preferences(flags=["low_water"]))
    cash = resolve_weights(Preferences(flags=["needs_cash_soon"]))
    assert dry["water_risk"] > base["water_risk"]
    assert cash["return"] > base["return"]
    assert sum(dry.values()) == pytest.approx(1.0)


def test_zero_weights_fall_back_to_defaults():
    w = resolve_weights(Preferences(weights=Weights(soil=0, **{"return": 0}, water_risk=0, pest=0)))
    assert sum(w.values()) == pytest.approx(1.0)


# ---- ranking ----
def _seq(crops_scores):
    from fieldshift.engine.scoring import SlotEval
    slots = [SlotEval("kharif-2027", c, soil, pest, w, w, rev, cost, 0.0, 0.0, "market", [], [])
             for c, soil, pest, w, rev, cost in crops_scores]
    return SeqEval(slots)


def test_normalize_returns_and_rank_order():
    a = _seq([("a", 0.8, 0.5, 0.8, 30000, 10000)])
    b = _seq([("b", 0.4, 0.5, 0.4, 20000, 10000)])
    normalize_returns([a, b])
    assert a.return_score == 1.0 and b.return_score < 1.0
    ranked = rank_sequences([a, b], resolve_weights(Preferences()), seed=1)
    assert [r.seq.crops[0] for r in ranked] == ["a", "b"]
    assert all(0 <= r.stability <= 1 for r in ranked)
    assert ranked[0].pessimistic_total <= ranked[0].total + 1e-9


def test_ranking_is_deterministic_for_a_seed():
    a = _seq([("a", 0.8, 0.5, 0.8, 30000, 10000)])
    b = _seq([("b", 0.7, 0.5, 0.7, 29000, 10000)])
    normalize_returns([a, b])
    w = resolve_weights(Preferences())
    assert [r.stability for r in rank_sequences([a, b], w, 7)] == [r.stability for r in rank_sequences([a, b], w, 7)]
