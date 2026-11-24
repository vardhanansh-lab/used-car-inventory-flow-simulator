"""Regenerates every number quoted in the deck and README.

    python scripts/make_results.py            # about 3 minutes
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd

from flowsim import Params, run
from flowsim.presets import PRESETS
from flowsim import insights as I

REPS = 8
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "results")
os.makedirs(OUT, exist_ok=True)

rows, summary = [], {}
for name, kw in PRESETS.items():
    r = run(Params(**kw), reps=REPS)
    k = r["kpi"]
    sd = r["kpi_sd"]
    rows.append({"scenario": name, **{x: k[x] for x in (
        "days_in_inventory", "p90_days", "aged_45", "capital_cr", "refurb_tat", "contrib_per_car",
        "sold_per_month", "leads_lost", "spares_cr", "d_listed", "d_refurb_q", "d_refurb", "d_yard_wait", "xfers")},
        "days_sd": sd["days_in_inventory"]})
    summary[name] = {"kpi": k, "sd": sd, "city": r["city"].round(4).to_dict(orient="records"),
                     "stages": I.stage_table(r).round(3).to_dict(orient="records"), "flags": I.city_flags(r)[["city", "flag"]].to_dict(orient="records")}
pd.DataFrame(rows).round(3).to_csv(f"{OUT}/scenarios.csv", index=False)

sens = I.sensitivity({}, reps=6)
sens.round(3).to_csv(f"{OUT}/sensitivity.csv", index=False)
fill = I.fill_curve({}, reps=6)
fill.round(3).to_csv(f"{OUT}/fill_curve.csv", index=False)
open(f"{OUT}/summary.json", "w").write(json.dumps(summary, indent=1, default=float).replace("NaN", "null"))
print(pd.DataFrame(rows).round(2).to_string())
print(sens.round(2).to_string())
print(fill.round(2).to_string())
