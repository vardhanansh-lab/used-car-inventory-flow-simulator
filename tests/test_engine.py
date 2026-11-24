import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flowsim import Params, run, simulate_once, load_network
from flowsim.spares import spares_capital, z_for


def test_network_loads():
    net = load_network()
    assert len(net) == 6
    assert sum(1 for c in net if c["role"] == "metro") == 3
    for c in net:
        assert abs(sum(c["mix"]) - 1.0) < 1e-6


def test_same_seed_same_result():
    a = simulate_once(Params(), seed=5)["sold"]
    b = simulate_once(Params(), seed=5)["sold"]
    assert len(a) == len(b) and abs(a.days.sum() - b.days.sum()) < 1e-9


def test_littles_law_holds():
    """Average cars in the pipeline should equal throughput times average days in the system."""
    r = run(Params(), reps=3)
    k = r["kpi"]
    per_day = k["sold_per_month"] / 30.0
    est = per_day * k["days_in_inventory"]
    assert abs(est - k["cars_in_pipeline"]) / k["cars_in_pipeline"] < 0.10


def test_stage_days_add_up():
    k = run(Params(), reps=2)["kpi"]
    parts = sum(k[x] for x in ("d_lag", "d_transit_out", "d_refurb_q", "d_refurb", "d_transit_back",
                               "d_yard_wait", "d_listed", "d_xfer"))
    assert abs(parts - k["days_in_inventory"]) < 0.05


def test_more_bays_cut_queue():
    base = run(Params(), reps=3)["kpi"]["d_refurb_q"]
    more = run(Params(bay_add={"Metro-B": 10}), reps=3)["kpi"]["d_refurb_q"]
    assert more < base


def test_higher_fill_rate_cuts_turnaround_and_costs_more_spares():
    lo = run(Params(fill_rate=0.90), reps=3)["kpi"]
    hi = run(Params(fill_rate=0.98), reps=3)["kpi"]
    assert hi["refurb_tat"] < lo["refurb_tat"]
    assert hi["spares_cr"] > lo["spares_cr"]


def test_surge_locks_more_capital_and_loses_more_leads():
    base = run(Params(), reps=3)["kpi"]
    surge = run(Params(lead_mult=1.10), reps=3)["kpi"]
    assert surge["capital_cr"] > base["capital_cr"]
    assert surge["leads_lost"] > base["leads_lost"]


def test_local_restoration_removes_transit_for_that_spoke():
    p = Params(spoke_local_bays={"Spoke-3": 18})
    net = {c["city"]: c for c in p.effective_network()}
    assert net["Spoke-3"]["role"] == "metro" and net["Spoke-3"]["transit_days"] == 0


def test_rebalance_moves_cars():
    assert run(Params(rebalance=True), reps=2)["kpi"]["xfers"] > 0


def test_spares_formula():
    assert abs(z_for(0.975) - 1.96) < 0.01
    a = spares_capital(30, [0.34, 0.56, 0.10], 0.95, 3)
    b = spares_capital(30, [0.34, 0.56, 0.10], 0.99, 3)
    assert b["total"] > a["total"] > 0 and math.isclose(a["cycle"], b["cycle"])
