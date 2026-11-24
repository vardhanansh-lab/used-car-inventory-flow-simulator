"""Parameters, defaults and the assumption register.

Every number that is not a published fact is an ASSUMPTION and is tagged as such in
ASSUMPTIONS, so the app and the docs can show what is sourced, derived or assumed.
"""
from __future__ import annotations
import copy
import csv
import os
from dataclasses import dataclass, field, asdict

SEGMENTS = ["Budget", "Assured", "Premium"]
HERE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(os.path.dirname(HERE), "data")

PRICE_MEAN = {"Budget": 320_000, "Assured": 600_000, "Premium": 1_400_000}   # purchase price, INR
PRICE_SIGMA = 0.18
REFURB_COST = {"Budget": 8_000, "Assured": 12_000, "Premium": 28_000}        # INR per car
REFURB_BAY_DAYS = {"Budget": 2.5, "Assured": 3.5, "Premium": 5.5}            # mean bay-days (gamma, k=4)
PARTS_LINES = {"Budget": 4, "Assured": 6, "Premium": 9}                      # parts lines per job
PARTS_SHARE = 0.55                                                           # parts as share of refurb cost


def load_network(path: str | None = None) -> list[dict]:
    path = path or os.path.join(DATA_DIR, "network.csv")
    rows = []
    with open(path, newline="") as f:
        for r in csv.DictReader(f):
            rows.append({
                "city": r["city"], "role": r["role"], "parent": r["parent"] or None,
                "transit_days": int(r["transit_days"]), "bays": int(r["bays"]),
                "insp_cap_day": float(r["insp_cap_day"]), "yard_cap": int(r["yard_cap"]),
                "leads_week": float(r["leads_week"]),
                "mix": [float(r["mix_budget"]), float(r["mix_assured"]), float(r["mix_premium"])],
                "dem_factor": [float(r["dem_budget"]), float(r["dem_assured"]), float(r["dem_premium"])],
            })
    return rows


@dataclass
class Params:
    """Scenario levers. Multipliers are relative to data/network.csv."""
    # supply side
    lead_mult: float = 1.0            # seller leads per week
    inspect_mult: float = 1.0         # inspection capacity per city
    accept_rate: float = 0.55         # leads that pass inspection and price agreement
    abandon_prob: float = 0.25        # per day a lead waits past day 1
    # restoration
    bay_add: dict = field(default_factory=dict)        # extra bays by city, e.g. {"Metro-B": 20}
    spoke_local_bays: dict = field(default_factory=dict)  # local restoration at a spoke, e.g. {"Spoke-3": 18}
    fill_rate: float = 0.95           # parts line fill rate at the store
    spares_lead_days: int = 3         # emergency replenishment lead time
    rework_prob: float = 0.08         # final QC failures
    # hub and demand
    yard_mult: float = 1.0
    demand_mult: float = 1.0
    season_amp: float = 0.10          # demand swing around the festive peak
    selection_days: float = 18.0      # days of demand a hub must stock to convert ~63% of visits
    # pricing and balancing
    md_age: int = 60                  # days listed before markdown (0 = off)
    md_pct: float = 0.03
    md_elasticity: float = 0.15       # pick-weight uplift per 1 percent cut
    rebalance: bool = False
    rb_age: int = 25                  # earliest listed age to move
    rb_dos_hi: float = 32.0           # source city days-of-supply trigger
    rb_dos_lo: float = 22.0           # destination city days-of-supply ceiling
    rb_max_per_day: int = 6
    xfer_days: int = 2
    xfer_cost: float = 4_500.0
    # money
    capital_rate: float = 0.12        # annual cost of capital
    yard_cost_day: float = 55.0
    depn_month: float = 0.010         # market price erosion per month
    margin_pct: float = 0.055         # gross margin on purchase price at list
    lw_cost: float = 5_500.0          # warranty and local logistics per car
    leg_cost: float = 2_800.0         # spoke to restoration leg, per leg
    # simulation
    sim_days: int = 330
    warmup: int = 120
    start_doy: int = 182
    network: list = field(default_factory=load_network)

    def city_names(self):
        return [c["city"] for c in self.network]

    def effective_network(self) -> list[dict]:
        net = copy.deepcopy(self.network)
        for c in net:
            c["leads_week"] *= self.lead_mult
            c["insp_cap_day"] *= self.inspect_mult
            c["yard_cap"] = int(round(c["yard_cap"] * self.yard_mult))
            if c["role"] == "metro":
                c["bays"] += int(self.bay_add.get(c["city"], 0))
        for c in net:
            nb = int(self.spoke_local_bays.get(c["city"], 0))
            if c["role"] == "spoke" and nb > 0:
                c["role"], c["bays"], c["parent"], c["transit_days"] = "metro", nb, None, 0
        return net

    def to_dict(self):
        d = asdict(self)
        d.pop("network", None)
        return d


# (key, label, value, unit, tag, basis)  tag: Sourced | Derived | Assumption
ASSUMPTIONS = [
    ("rev", "FY25 operating revenue", "4,657", "INR Cr", "Sourced", "Reported FY25 figures, Inventiva / Inc42"),
    ("proc", "FY25 procurement cost", "4,304", "INR Cr", "Sourced", "About 92-93% of customer revenue, Inc42 / Capital Insider"),
    ("direct", "FY25 direct costs (refurb, logistics, warranty)", "136.8", "INR Cr", "Sourced", "Capital Insider on Spinny FY25"),
    ("footprint", "Network", "57+ hubs, 17 Parks, 15+ restoration centres", "", "Sourced", "Inventiva; Spinny press releases"),
    ("direct_car", "Direct cost per car", "about 18,000", "INR", "Derived", "136.8 Cr / about 76k cars (4,550 Cr car revenue / 6 lakh avg price, our estimate)"),
    ("spread", "Spread after procurement and direct costs", "about 4.5%", "of revenue", "Derived", "Capital Insider calculation on FY25 figures"),
    ("price", "Purchase price mix", "3.2L / 6.0L / 14L", "INR", "Assumption", "Budget / Assured / Premium; sets capital per car"),
    ("refurb", "Refurb cost", "8k / 12k / 28k", "INR", "Assumption", "Calibrated so refurb plus logistics and warranty is near the derived 18k"),
    ("baydays", "Bay-days per job", "2.5 / 3.5 / 5.5", "days", "Assumption", "Gamma distributed, before parts delays and rework"),
    ("lines", "Parts lines per job", "4 / 6 / 9", "lines", "Assumption", "Job is delayed if any line is out of stock"),
    ("fill", "Parts line fill rate", "95%", "", "Assumption", "Store-level service level, a lever in the app"),
    ("accept", "Leads that become purchases", "55%", "", "Assumption", "Inspection fail plus price disagreement"),
    ("cap", "Cost of capital", "12%", "per year", "Assumption", "Short-term borrowing, typical range 10-14%"),
    ("depn", "Market price erosion", "1.0%", "per month", "Assumption", "Used-car prices drift down while a car waits"),
    ("yard", "Yard cost", "55", "INR per car per day", "Assumption", "Space and upkeep"),
    ("margin", "Gross margin at list", "5.5%", "of purchase price", "Assumption", "Set so the baseline sits near the derived spread"),
    ("rework", "Final QC rework", "8%", "of cars", "Assumption", "Adds 1 to 2 bay-days"),
    ("demand", "Buyer demand", "1.25x purchases before city and segment factors", "", "Assumption", "Imbalances are deliberate so rebalancing has something to fix"),
    ("scale", "Network size", "about 2,250 cars a month", "", "Assumption", "A scaled replica, not Spinny's actual volume"),
]
