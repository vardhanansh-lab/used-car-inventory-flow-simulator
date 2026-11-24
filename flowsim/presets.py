"""Named scenarios. Each returns lever overrides applied on top of the baseline Params."""
PRESETS = {
    "Baseline": {},
    "Festive surge: +10% seller leads": {"lead_mult": 1.10},
    "Surge with resilience package": {
        "lead_mult": 1.10, "bay_add": {"Metro-B": 10}, "spoke_local_bays": {"Spoke-3": 18},
        "inspect_mult": 1.10, "fill_rate": 0.98, "rebalance": True, "yard_mult": 1.10},
    "Resilience package, normal load": {
        "bay_add": {"Metro-B": 10}, "spoke_local_bays": {"Spoke-3": 18},
        "inspect_mult": 1.10, "fill_rate": 0.98, "rebalance": True, "yard_mult": 1.10},
    "Parts shock: fill rate falls to 90%": {"fill_rate": 0.90},
    "Demand dip: -10% buyer demand": {"demand_mult": 0.90},
}
