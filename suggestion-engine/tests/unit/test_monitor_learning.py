from datetime import date, timedelta

import pytest

from fieldshift.learning.weight_tuning import adherence_summary, ready_for_tuning
from fieldshift.monitor.anomalies import classify_low, percentile_rank
from fieldshift.monitor.drift import drift_alerts, sowing_alert
from fieldshift.monitor.run_p3 import Baseline, Observation, run_p3
from fieldshift.monitor.sowing_window import find_onset, sowing_status
from fieldshift.simulation.crop_params import load_crop_sim
from fieldshift.store.memory_store import MemoryStore
from fieldshift.store.models import ActionLog

HIST = [0.20, 0.22, 0.24, 0.25, 0.26, 0.27, 0.28, 0.30, 0.31, 0.33]


# ---- anomalies ----
def test_percentile_rank_counts_ties_as_half():
    assert percentile_rank(0.25, HIST) == 35.0       # 3 below, 1 equal
    assert percentile_rank(0.10, HIST) == 0.0 and percentile_rank(0.99, HIST) == 100.0


def test_classify_low_levels_and_short_history():
    assert classify_low(0.10, HIST).level == "act"
    assert classify_low(0.215, HIST).level == "act"      # exactly the 10th percentile counts as 'act'
    assert classify_low(0.235, HIST).level == "watch"    # 20th percentile: in the watch band
    assert classify_low(0.29, HIST).level == "ok"
    assert classify_low(0.10, HIST[:5]) is None
    assert classify_low(0.10, HIST).median == pytest.approx(0.265)


# ---- sowing window ----
def test_find_onset_uses_accumulated_rain():
    rain = {date(2026, 6, 10): 20.0, date(2026, 6, 11): 25.0, date(2026, 6, 12): 10.0}
    assert find_onset(rain, date(2026, 6, 1), date(2026, 6, 30)) == date(2026, 6, 12)   # 20+25+10 = 55 within 3 days
    assert find_onset({date(2026, 6, 10): 40.0}, date(2026, 6, 1), date(2026, 6, 30)) is None


def test_sowing_status_states():
    planned = date(2026, 6, 25)                       # latest sowing = 16 July with 21 late days
    rain = {date(2026, 6, 20): 60.0}
    assert sowing_status(date(2026, 6, 22), rain, date(2026, 6, 1), planned).state == "open"
    assert sowing_status(date(2026, 6, 22), {}, date(2026, 6, 1), planned).state == "not_open"
    assert sowing_status(date(2026, 7, 10), rain, date(2026, 6, 1), planned).state == "closing"
    assert sowing_status(date(2026, 7, 10), {}, date(2026, 6, 1), planned).state == "closing"   # no onset and little time left
    closed = sowing_status(date(2026, 7, 20), {}, date(2026, 6, 1), planned)
    assert closed.state == "closed" and closed.latest_sowing == date(2026, 7, 16)


# ---- alerts ----
def test_drift_alerts_only_for_low_values():
    alerts = drift_alerts("c1", "soybean", "kharif-2026", {"soil_moisture": 0.10, "ndvi": 0.9},
                          {"soil_moisture": HIST, "ndvi": [0.4, 0.5, 0.6, 0.55, 0.45, 0.5, 0.52, 0.58, 0.6]})
    assert [(a.code, a.severity) for a in alerts] == [("MOISTURE_BELOW_EXPECTED", "act")]
    assert alerts[0].params["percentile"] == 0.0 and alerts[0].crop == "soybean"
    assert drift_alerts("c1", None, "kharif-2026", {"soil_moisture": 0.3}, {}) == []


def test_sowing_alert_maps_states():
    base = dict(onset=None, latest_sowing=date(2026, 7, 16))
    from fieldshift.monitor.sowing_window import SowingStatus
    assert sowing_alert("c", "maize", "kharif-2026", SowingStatus("open", **base, days_left=20)) is None
    a = sowing_alert("c", "maize", "kharif-2026", SowingStatus("closing", **base, days_left=5))
    assert (a.code, a.severity, a.valid_to, a.params["days_left"]) == ("SOWING_WINDOW_CLOSING", "watch", "2026-07-16", 5)
    c = sowing_alert("c", "maize", "kharif-2026", SowingStatus("closed", **base, days_left=-3))
    assert (c.code, c.severity, c.params["days_left"]) == ("SOWING_WINDOW_CLOSED", "act", 0)


# ---- P3 runner ----
class FakeSource:
    def __init__(self, obs, base):
        self.obs, self.base = obs, base

    def observation(self, cell_id, season, today):
        return self.obs.get(cell_id)

    def baseline(self, cell_id, season, today):
        return self.base


def test_run_p3_writes_alerts_once(settings):
    store = MemoryStore()
    for plot, cell, crop in (("p1", "cellA", "soybean"), ("p2", "cellB", "soybean"), ("p3", "cellA", "soybean")):
        store.log_action(ActionLog(plot_id=plot, cell_id=cell, season="kharif-2026", planted_crop=crop))
    store.log_action(ActionLog(plot_id="p4", cell_id="cellA", season="rabi-2026", planted_crop="wheat"))   # other season
    source = FakeSource({"cellA": Observation(rain={}, soil_moisture=0.10, ndvi=None)},
                        Baseline(soil_moisture=HIST, ndvi=[]))                                           # cellB: no observation
    sim = load_crop_sim(settings.knowledge_dir)
    today = date(2026, 7, 20)                                  # past the latest sowing date, no onset rain
    alerts = run_p3(store, source, sim, "kharif-2026", today)
    codes = sorted(a.code for a in alerts)
    assert codes == ["MOISTURE_BELOW_EXPECTED", "SOWING_WINDOW_CLOSED"] and {a.cell_id for a in alerts} == {"cellA"}
    assert len(store.list_alerts("cellA")) == 2
    assert run_p3(store, source, sim, "kharif-2026", today + timedelta(days=1)) == []    # no duplicates


# ---- learning ----
def test_adherence_summary_and_gate():
    actions = [ActionLog(plot_id=f"p{i}", season="kharif-2026", planted_crop="soybean",
                         followed_option_rank=(1 if i % 2 else None), yield_q_per_acre=(5.0 if i < 3 else None))
               for i in range(6)]
    s = adherence_summary(actions)
    assert s == {"n_actions": 6, "n_followed_a_recommendation": 3, "n_with_yield": 3, "followed_by_rank": {1: 3}}
    assert not ready_for_tuning(actions) and ready_for_tuning(actions, minimum=3)
