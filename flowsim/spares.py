"""Spares working capital for refurbishment, using a standard safety-stock formula.

Stock-outs delay jobs inside the simulation. This module prices the other side of the
trade-off: how much cash a higher fill rate ties up in parts.
"""
from __future__ import annotations
from statistics import NormalDist
from .config import PARTS_SHARE, REFURB_COST, SEGMENTS

DEMAND_CV = 0.60          # day-to-day variation of parts demand (assumption)
REVIEW_DAYS = 7           # replenishment review period (assumption)


def z_for(fill_rate: float) -> float:
    fill_rate = min(max(fill_rate, 0.50), 0.999)
    return NormalDist().inv_cdf(fill_rate)


def spares_capital(jobs_per_day: float, mix: list[float], fill_rate: float, lead_days: int) -> dict:
    """Return cycle stock, safety stock and total in INR for one restoration centre."""
    parts_per_job = sum(m * REFURB_COST[s] * PARTS_SHARE for m, s in zip(mix, SEGMENTS))
    daily_spend = jobs_per_day * parts_per_job
    cycle = daily_spend * REVIEW_DAYS / 2
    safety = max(z_for(fill_rate), 0.0) * DEMAND_CV * daily_spend * (lead_days + REVIEW_DAYS) ** 0.5
    return {"daily_spend": daily_spend, "cycle": cycle, "safety": safety, "total": cycle + safety}
