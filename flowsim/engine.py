"""Discrete-time simulation of a hub-and-spoke used-car pipeline.

Flow per car:
  seller lead -> inspection (capacity, rejects, lead drop-off) -> purchase (capital locks)
  -> paperwork lag -> transit to restoration centre (spokes only) -> refurb queue
  -> bay (service time, parts stock-outs, QC rework) -> transit back (spokes only)
  -> yard (capacity) -> listed (sells at a rate that depends on stock on hand)
  -> sold (capital released).  Optional inter-city rebalancing and markdowns.

Everything is synthetic. Parameters live in config.py and data/network.csv.
"""
from __future__ import annotations
import math
from collections import deque, defaultdict
import numpy as np
import pandas as pd

from .config import (Params, SEGMENTS, PRICE_MEAN, PRICE_SIGMA, REFURB_COST, REFURB_BAY_DAYS,
                     PARTS_LINES)
from .spares import spares_capital

STAGES = ["lag", "transit_out", "refurb_q", "refurb", "transit_back", "yard_wait", "listed", "xfer"]
STAGE_LABEL = {
    "lag": "Paperwork and pickup", "transit_out": "Transit to restoration", "refurb_q": "Waiting for a bay",
    "refurb": "In the bay", "transit_back": "Transit back to hub", "yard_wait": "Waiting for yard space",
    "listed": "Listed for sale", "xfer": "Inter-city transfer",
}


class Car:
    __slots__ = ("id", "city", "irc", "seg", "P", "R", "t0", "qd", "listed_day", "cap", "legs",
                 "xfers", "rework", "dur", "stage_t", "stage", "md", "attr")

    def __init__(self, cid, city, irc, seg, P, R, t0):
        self.id, self.city, self.irc, self.seg, self.P, self.R, self.t0 = cid, city, irc, seg, P, R, t0
        self.dur = dict.fromkeys(STAGES, 0.0)
        self.stage, self.stage_t = "lag", t0
        self.legs = self.xfers = 0
        self.rework = False
        self.listed_day = -1
        self.md = False
        self.attr = 1.0


def _season(t, p: Params, amp):
    doy = (p.start_doy + t) % 365
    return 1.0 + amp * math.cos(2 * math.pi * (doy - 305) / 365.0)


def simulate_once(p: Params, seed: int = 0) -> dict:
    rng = np.random.default_rng(seed)
    net = p.effective_network()
    nC = len(net)
    idx = {c["city"]: i for i, c in enumerate(net)}
    T, W = p.sim_days, p.warmup

    # ---- derived per-city constants
    lead_day = [c["leads_week"] / 7.0 for c in net]
    is_irc = [c["role"] == "metro" for c in net]
    irc_of = [i if is_irc[i] else idx[net[i]["parent"]] for i in range(nC)]
    transit = [0 if is_irc[i] else net[i]["transit_days"] for i in range(nC)]
    bays = [net[i]["bays"] if is_irc[i] else 0 for i in range(nC)]
    # demand per day by segment, anchored on expected purchases (see assumptions: 1.25x)
    dem = []
    for i, c in enumerate(net):
        base = p.network[i]["leads_week"] / 7.0 * 0.55         # purchases/day at default settings
        m0 = p.network[i]["mix"]                                # demand is anchored on the network file mix
        dem.append([1.25 * base * m0[s] * c["dem_factor"][s] * p.demand_mult for s in range(3)])
    stockout_p = {s: 1 - p.fill_rate ** PARTS_LINES[s] for s in SEGMENTS}

    # ---- state
    insp_q = [deque() for _ in range(nC)]              # lead arrival days
    refq = [deque() for _ in range(nC)]                # cars waiting for a bay (by restoration centre)
    busy = [0] * nC
    yardq = [deque() for _ in range(nC)]
    listed = [[[] for _ in range(3)] for _ in range(nC)]
    n_listed = [0] * nC
    events = defaultdict(list)
    stage_count = dict.fromkeys(STAGES, 0)
    cap_locked = 0.0
    next_id = 0

    # ---- records
    sold_rows = []
    daily = []
    util_bay = [0.0] * nC
    insp_served = [0] * nC
    insp_cap_tot = [0.0] * nC
    leads_in = [0] * nC
    leads_lost = [0] * nC
    leads_rej = [0] * nC
    bought = [0] * nC
    jobs_started = [0] * nC
    stockouts = [0] * nC
    reworks = [0] * nC
    yard_blocked_days = [0] * nC
    queue_sum = [0.0] * nC
    cars_started_in_window = [0] * nC
    wait_sum = [0.0] * nC
    wait_n = [0] * nC
    xfer_count = 0

    def enter(car: Car, stage: str, t: int):
        nonlocal stage_count
        if car.stage:
            car.dur[car.stage] += t - car.stage_t
            stage_count[car.stage] -= 1
        car.stage, car.stage_t = stage, t
        stage_count[stage] += 1

    live = []          # events firing today (same-day follow-ups are appended here)
    today = [0]

    def schedule(day, kind, car, extra=None):
        if day <= today[0]:
            live.append((kind, car, extra))
        else:
            events[day].append((kind, car, extra))

    def list_car(car: Car, city: int, t: int):
        nonlocal cap_locked
        enter(car, "listed", t)
        car.city = city
        car.listed_day = t
        listed[city][SEGMENTS.index(car.seg)].append(car)
        n_listed[city] += 1

    for t in range(T):
        # ---------------- events scheduled for today
        today[0] = t
        live[:] = events.pop(t, [])
        while live:
            kind, car, extra = live.pop(0)
            if kind == "to_move":
                i = car.city
                if is_irc[i]:
                    car.irc = i
                    enter(car, "refurb_q", t)
                    refq[i].append(car)
                else:
                    car.irc = irc_of[i]
                    car.legs += 1
                    enter(car, "transit_out", t)
                    schedule(t + transit[i], "to_irc", car)
            elif kind == "to_irc":
                enter(car, "refurb_q", t)
                refq[car.irc].append(car)
            elif kind == "bay_done":
                irc = car.irc
                busy[irc] -= 1
                cap_locked += car.R
                home = car.city
                if home != irc:
                    car.legs += 1
                    enter(car, "transit_back", t)
                    schedule(t + transit[home], "at_hub", car)
                else:
                    schedule(t, "at_hub", car)
            elif kind == "at_hub":
                home = car.city
                if n_listed[home] < net[home]["yard_cap"]:
                    list_car(car, home, t)
                else:
                    enter(car, "yard_wait", t)
                    yardq[home].append(car)
            elif kind == "xfer_arrive":
                dest = extra
                if n_listed[dest] < net[dest]["yard_cap"]:
                    list_car(car, dest, t)
                else:
                    car.city = dest
                    enter(car, "yard_wait", t)
                    yardq[dest].append(car)

        # ---------------- leads and inspection
        season = _season(t, p, p.season_amp * 0.5)
        for i in range(nC):
            n = rng.poisson(lead_day[i] * season)
            leads_in[i] += n
            insp_q[i].extend([t] * n)
            capx = net[i]["insp_cap_day"]
            cap = int(capx) + (1 if rng.random() < capx - int(capx) else 0)
            served = 0
            while insp_q[i] and served < cap:
                insp_q[i].popleft()
                served += 1
                if rng.random() < p.accept_rate:
                    seg_i = rng.choice(3, p=net[i]["mix"])
                    seg = SEGMENTS[seg_i]
                    P = PRICE_MEAN[seg] * float(rng.lognormal(-0.5 * PRICE_SIGMA ** 2, PRICE_SIGMA))
                    R = REFURB_COST[seg] * float(rng.lognormal(-0.02, 0.20))
                    car = Car(next_id, i, irc_of[i], seg, P, R, t)
                    car.attr = float(rng.lognormal(-0.125, 0.5))   # some cars are simply harder to sell
                    next_id += 1
                    stage_count["lag"] += 1
                    cap_locked += P
                    bought[i] += 1
                    schedule(t + int(rng.integers(1, 3)), "to_move", car)
                else:
                    leads_rej[i] += 1
            if t >= W:
                insp_served[i] += served
                insp_cap_tot[i] += cap
            # unserved leads may walk away
            if insp_q[i]:
                keep = deque()
                for a in insp_q[i]:
                    if t - a >= 1 and rng.random() < p.abandon_prob:
                        if t >= W:
                            leads_lost[i] += 1
                    else:
                        keep.append(a)
                insp_q[i] = keep

        # ---------------- restoration bays
        for i in range(nC):
            if not is_irc[i]:
                continue
            while busy[i] < bays[i] and refq[i]:
                car = refq[i].popleft()
                enter(car, "refurb", t)
                svc = REFURB_BAY_DAYS[car.seg]
                days = max(1.0, float(rng.gamma(4.0, svc / 4.0)))
                if rng.random() < stockout_p[car.seg]:
                    days += int(rng.integers(1, 2 * p.spares_lead_days))
                    if t >= W:
                        stockouts[i] += 1
                if rng.random() < p.rework_prob:
                    days += float(rng.uniform(1, 2))
                    car.rework = True
                    car.R *= 1.15
                    if t >= W:
                        reworks[i] += 1
                busy[i] += 1
                if t >= W:
                    jobs_started[i] += 1
                schedule(t + max(1, int(round(days))), "bay_done", car)
            if t >= W:
                util_bay[i] += busy[i]
                queue_sum[i] += len(refq[i])

        # ---------------- yard release
        for i in range(nC):
            while yardq[i] and n_listed[i] < net[i]["yard_cap"]:
                list_car(yardq[i].popleft(), i, t)
            if yardq[i] and t >= W:
                yard_blocked_days[i] += 1

        # ---------------- sales
        dem_season = _season(t, p, p.season_amp)
        for i in range(nC):
            for s in range(3):
                lst = listed[i][s]
                d = dem[i][s] * dem_season
                if d <= 0:
                    continue
                lam = d * (1.0 - math.exp(-len(lst) / (p.selection_days * d)))
                k = min(int(rng.poisson(lam)), len(lst))
                if k <= 0:
                    continue
                md_on = p.md_age > 0 and p.md_pct > 0
                w = np.array([c.attr * (1.0 + (p.md_elasticity * p.md_pct * 100.0 if (md_on and t - c.listed_day >= p.md_age) else 0.0))
                              for c in lst])
                pick = rng.choice(len(lst), size=k, replace=False, p=w / w.sum())
                pick_set = set(int(x) for x in pick)
                keep = []
                for j, c in enumerate(lst):
                    if j in pick_set:
                        c.dur["listed"] += t - c.stage_t     # close the listed stage
                        stage_count["listed"] -= 1
                        n_listed[i] -= 1
                        cap_locked -= (c.P + c.R)
                        c.md = md_on and (t - c.listed_day >= p.md_age)
                        if t >= W:
                            sold_rows.append(_row(c, t, i, p))
                    else:
                        keep.append(c)
                listed[i][s] = keep

        # ---------------- inter-city rebalancing
        if p.rebalance:
            for s in range(3):
                dos = [len(listed[i][s]) / max(dem[i][s] * dem_season, 1e-6) for i in range(nC)]
                order_src = sorted(range(nC), key=lambda i: -dos[i])
                order_dst = sorted(range(nC), key=lambda i: dos[i])
                moved = 0
                for src in order_src:
                    if dos[src] < p.rb_dos_hi or moved >= p.rb_max_per_day:
                        break
                    cand = [c for c in listed[src][s] if t - c.listed_day >= p.rb_age]
                    for dst in order_dst:
                        if dst == src or dos[dst] > p.rb_dos_lo or not cand or moved >= p.rb_max_per_day:
                            continue
                        c = cand.pop(0)
                        listed[src][s].remove(c)
                        n_listed[src] -= 1
                        enter(c, "xfer", t)
                        c.xfers += 1
                        schedule(t + p.xfer_days, "xfer_arrive", c, dst)
                        moved += 1
                        xfer_count += 1
                        dos[src] -= 1 / max(dem[src][s] * dem_season, 1e-6)
                        dos[dst] += 1 / max(dem[dst][s] * dem_season, 1e-6)

        daily.append((t, sum(stage_count.values()), cap_locked, *[stage_count[s] for s in STAGES],
                      sum(len(q) for q in refq), sum(len(q) for q in insp_q)))

    # ---------------- aggregate
    sold = pd.DataFrame(sold_rows, columns=SOLD_COLS) if sold_rows else pd.DataFrame(columns=SOLD_COLS)
    ddf = pd.DataFrame(daily, columns=["day", "cars", "capital", *STAGES, "refurb_queue_len", "insp_queue_len"])
    days = max(T - W, 1)
    city = []
    for i, c in enumerate(net):
        sc = sold[sold.city_idx == i] if len(sold) else sold
        city.append({
            "city": c["city"], "role": "restoration centre" if is_irc[i] else f"spoke via {net[irc_of[i]]['city']}",
            "bays": bays[i], "bay_util": util_bay[i] / (bays[i] * days) if bays[i] else np.nan,
            "refurb_queue": queue_sum[i] / days if is_irc[i] else np.nan,
            "insp_util": insp_served[i] / insp_cap_tot[i] if insp_cap_tot[i] else np.nan,
            "leads_lost": leads_lost[i], "leads_in": leads_in[i],
            "stockout_jobs": stockouts[i], "jobs": jobs_started[i],
            "yard_full_days": yard_blocked_days[i], "sold": len(sc),
            "avg_days": float(sc.days.mean()) if len(sc) else np.nan,
            "yard_wait_avg": float(sc.yard_wait.mean()) if len(sc) else np.nan,
        })
    return {"sold": sold, "daily": ddf, "city": pd.DataFrame(city), "xfers": xfer_count,
            "jobs_per_day": [jobs_started[i] / days for i in range(nC)], "net": net, "irc": is_irc}


SOLD_COLS = ["id", "city_idx", "seg", "days", "lag", "transit_out", "refurb_q", "refurb", "transit_back",
             "yard_wait", "listed", "xfer", "rework", "md", "xfers", "legs", "P", "R", "contrib", "holding", "t_sold"]


def _row(c: Car, t: int, i: int, p: Params):
    days = t - c.t0
    capital_cost = p.capital_rate / 365.0 * (c.P + 0.5 * c.R) * days
    holding = capital_cost + p.yard_cost_day * days + (p.depn_month / 30.0) * c.P * days
    price = (c.P * (1 + p.margin_pct) + c.R + p.lw_cost)
    if c.md:
        price *= (1 - p.md_pct)
    costs = c.P + c.R + p.lw_cost + c.legs * p.leg_cost + c.xfers * p.xfer_cost + holding
    d = c.dur
    return (c.id, i, c.seg, days, d["lag"], d["transit_out"], d["refurb_q"], d["refurb"], d["transit_back"],
            d["yard_wait"], d["listed"], d["xfer"], c.rework, c.md, c.xfers, c.legs, c.P, c.R, price - costs, holding, t)


# ------------------------------------------------------------------ aggregation across replications
def _summ(df: pd.DataFrame, daily: pd.DataFrame, city: pd.DataFrame, p: Params, res: dict) -> dict:
    W = p.warmup
    d = daily[daily.day >= W]
    months = max(len(d), 1) / 30.0
    n = len(df)
    out = {
        "sold_per_month": n / months,
        "days_in_inventory": float(df.days.mean()) if n else np.nan,
        "p90_days": float(df.days.quantile(0.9)) if n else np.nan,
        "aged_45": float((df.days > 45).mean()) if n else np.nan,
        "aged_60": float((df.days > 60).mean()) if n else np.nan,
        "refurb_tat": float((df.refurb_q + df.refurb).mean()) if n else np.nan,
        "capital_cr": float(d.capital.mean() / 1e7),
        "cars_in_pipeline": float(d.cars.mean()),
        "contrib_per_car": float(df.contrib.mean()) if n else np.nan,
        "holding_per_car": float(df.holding.mean()) if n else np.nan,
        "contrib_total_cr": float(df.contrib.sum() / 1e7 / months) if n else np.nan,
        "rework_share": float(df.rework.mean()) if n else np.nan,
        "md_share": float(df.md.mean()) if n else np.nan,
        "leads_lost": int(city.leads_lost.sum()),
        "lost_share": float(city.leads_lost.sum() / max(city.leads_in.sum(), 1)),
        "xfers": res["xfers"],
    }
    for s in ["lag", "transit_out", "refurb_q", "refurb", "transit_back", "yard_wait", "listed", "xfer"]:
        out["d_" + s] = float(df[s].mean()) if n else np.nan
    return out


def run(p: Params, reps: int = 8, seed: int = 11) -> dict:
    """Run replications and return mean KPIs, spread, stage breakdown and city tables."""
    summaries, solds, cities, dailies, jobs = [], [], [], [], []
    for r in range(reps):
        res = simulate_once(p, seed + 101 * r)
        summaries.append(_summ(res["sold"], res["daily"], res["city"], p, res))
        solds.append(res["sold"]); cities.append(res["city"]); dailies.append(res["daily"]); jobs.append(res["jobs_per_day"])
        net, irc = res["net"], res["irc"]
    S = pd.DataFrame(summaries)
    mean, sd = S.mean(), S.std(ddof=1) if reps > 1 else S.mean() * 0
    kpi = {k: float(mean[k]) for k in S.columns}
    kpi_sd = {k: float(sd[k]) for k in S.columns}
    city = pd.concat(cities).groupby("city", sort=False).agg(
        role=("role", "first"), bays=("bays", "first"), bay_util=("bay_util", "mean"),
        refurb_queue=("refurb_queue", "mean"), insp_util=("insp_util", "mean"),
        leads_lost=("leads_lost", "mean"), leads_in=("leads_in", "mean"), stockout_jobs=("stockout_jobs", "mean"),
        jobs=("jobs", "mean"), yard_full_days=("yard_full_days", "mean"), sold=("sold", "mean"),
        avg_days=("avg_days", "mean"), yard_wait_avg=("yard_wait_avg", "mean")).reset_index()
    # spares capital per restoration centre, from simulated job flow
    jmean = np.mean(np.array(jobs), axis=0)
    sp = []
    for i, c in enumerate(net):
        if irc[i]:
            own_mix = c["mix"]
            sp.append({"centre": c["city"], **spares_capital(jmean[i], own_mix, p.fill_rate, p.spares_lead_days)})
    spares = pd.DataFrame(sp)
    kpi["spares_cr"] = float(spares.total.sum() / 1e7)
    daily = pd.concat(dailies).groupby("day").mean().reset_index()
    sold_all = pd.concat(solds, keys=range(reps), names=["rep"]).reset_index(level=0)
    return {"kpi": kpi, "kpi_sd": kpi_sd, "city": city, "spares": spares, "daily": daily, "sold": sold_all,
            "reps": reps, "params": p.to_dict()}
