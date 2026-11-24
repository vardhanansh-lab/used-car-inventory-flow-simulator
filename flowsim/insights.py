"""Scenario comparison, sensitivity and plain-language findings built from simulation output."""
from __future__ import annotations
import copy
import pandas as pd

from .config import Params
from .engine import run, STAGE_LABEL

KPI_ROWS = [
    ("days_in_inventory", "Days in inventory (purchase to sale)", "{:.1f}", False),
    ("p90_days", "90th percentile days", "{:.0f}", False),
    ("aged_45", "Cars sold after 45+ days", "{:.0%}", False),
    ("capital_cr", "Average capital locked (INR Cr)", "{:.1f}", False),
    ("refurb_tat", "Refurbishment turnaround (days)", "{:.2f}", False),
    ("contrib_per_car", "Contribution per car (INR)", "{:,.0f}", True),
    ("sold_per_month", "Cars sold per month", "{:,.0f}", True),
    ("leads_lost", "Seller leads lost to slow inspection", "{:,.0f}", False),
    ("spares_cr", "Spares working capital (INR Cr)", "{:.2f}", False),
]


def kpi_table(base: dict, scen: dict | None = None) -> pd.DataFrame:
    rows = []
    for key, label, fmt, higher_better in KPI_ROWS:
        b = base["kpi"][key]
        row = {"Metric": label, "Baseline": fmt.format(b)}
        if scen is not None:
            s = scen["kpi"][key]
            row["Scenario"] = fmt.format(s)
            d = s - b
            row["Change"] = (("+" if d >= 0 else "-") + fmt.format(abs(d)).lstrip("+"))
            good = (d > 0) == higher_better if abs(d) > 1e-9 else None
            row["_good"] = good
        rows.append(row)
    return pd.DataFrame(rows)


def stage_table(res: dict) -> pd.DataFrame:
    k = res["kpi"]
    order = ["lag", "transit_out", "refurb_q", "refurb", "transit_back", "yard_wait", "xfer", "listed"]
    return pd.DataFrame([{"stage": STAGE_LABEL[s], "key": s, "days": k["d_" + s]} for s in order])


def city_flags(res: dict) -> pd.DataFrame:
    c = res["city"].copy()
    c["throughput_day"] = c["jobs"] / 210.0
    c["bay_wait_days"] = c["refurb_queue"] / c["throughput_day"].replace(0, float("nan"))
    c["lead_loss_pct"] = c["leads_lost"] / c["leads_in"]
    flags = []
    for _, r in c.iterrows():
        f = []
        if pd.notna(r.bay_util) and r.bay_util >= 0.95:
            f.append("bays near full")
        if pd.notna(r.insp_util) and r.insp_util >= 0.93:
            f.append("inspection near full")
        if r.lead_loss_pct >= 0.015:
            f.append("losing leads")
        if r.yard_wait_avg >= 1.0:
            f.append("yard full")
        if pd.notna(r.bay_wait_days) and r.bay_wait_days >= 1.5:
            f.append("queue for bays")
        flags.append(", ".join(f) if f else "ok")
    c["flag"] = flags
    return c


def findings(res: dict) -> list[str]:
    k = res["kpi"]
    st = stage_table(res)
    sell = float(st.loc[st.key == "listed", "days"].iloc[0])
    ops = float(st.loc[st.key != "listed", "days"].sum())
    out = [f"{sell:.0f} of {k['days_in_inventory']:.0f} days sit in the listed stage. The supply chain controls about {ops:.0f} days before a car reaches the yard."]
    c = city_flags(res)
    hot = c[c.flag != "ok"]
    for _, r in hot.iterrows():
        out.append(f"{r.city}: {r.flag}.")
    if not len(hot):
        out.append("No city is running hot. Try the festive surge preset to see where the network breaks first.")
    out.append(f"Holding cost is INR {k['holding_per_car']:,.0f} per car, against INR {k['contrib_per_car']:,.0f} contribution. Every day removed is worth about INR {k['holding_per_car'] / max(k['days_in_inventory'], 1):,.0f} per car.")
    return out


SENS_LEVERS = [
    ("Add 10 bays at Metro-B", {"bay_add": {"Metro-B": 10}}),
    ("Parts fill rate 98% (from 95%)", {"fill_rate": 0.98}),
    ("Local restoration at Spoke-3 (18 bays)", {"spoke_local_bays": {"Spoke-3": 18}}),
    ("Inspection capacity +10%", {"inspect_mult": 1.10}),
    ("Rebalance stock between cities", {"rebalance": True}),
    ("Yard space +15%", {"yard_mult": 1.15}),
    ("Markdown at 45 days (3%)", {"md_age": 45, "md_pct": 0.03}),
    ("Seller leads +10%", {"lead_mult": 1.10}),
    ("Buyer demand -10%", {"demand_mult": 0.90}),
]


def sensitivity(base_kwargs: dict, reps: int = 4, seed: int = 11, progress=None) -> pd.DataFrame:
    base = run(Params(**base_kwargs), reps=reps, seed=seed)
    rows = []
    for i, (name, kw) in enumerate(SENS_LEVERS):
        merged = {**copy.deepcopy(base_kwargs), **copy.deepcopy(kw)}
        r = run(Params(**merged), reps=reps, seed=seed)
        rows.append({"Lever": name,
                     "d_days": r["kpi"]["days_in_inventory"] - base["kpi"]["days_in_inventory"],
                     "d_capital": r["kpi"]["capital_cr"] - base["kpi"]["capital_cr"],
                     "d_tat": r["kpi"]["refurb_tat"] - base["kpi"]["refurb_tat"],
                     "d_contrib": r["kpi"]["contrib_per_car"] - base["kpi"]["contrib_per_car"],
                     "d_lost": r["kpi"]["leads_lost"] - base["kpi"]["leads_lost"]})
        if progress:
            progress((i + 1) / len(SENS_LEVERS))
    return pd.DataFrame(rows)


def fill_curve(base_kwargs: dict, rates=(0.85, 0.90, 0.95, 0.98, 0.99), reps: int = 4, seed: int = 11) -> pd.DataFrame:
    rows = []
    for fr in rates:
        r = run(Params(**{**base_kwargs, "fill_rate": fr}), reps=reps, seed=seed)
        k = r["kpi"]
        rows.append({"fill_rate": fr, "tat": k["refurb_tat"], "contrib": k["contrib_per_car"],
                     "spares_lakh": k["spares_cr"] * 100.0, "days": k["days_in_inventory"], "capital_cr": k["capital_cr"]})
    return pd.DataFrame(rows)
