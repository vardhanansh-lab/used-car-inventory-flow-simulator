"""Used-car inventory and refurbishment flow simulator.

Run:  streamlit run app.py
All data is synthetic. See data/network.csv and the Assumptions tab.
"""
import json
import copy

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from flowsim import Params, run, ASSUMPTIONS
from flowsim.presets import PRESETS
from flowsim import insights as I
from flowsim.engine import STAGE_LABEL

PURPLE, RED, VIOLET, LILAC, PALE = "#2E054E", "#ED264F", "#6300A3", "#C9A7E8", "#F6EEFB"
STAGE_COLOR = {"lag": "#8E5BB5", "transit_out": "#B98AD6", "refurb_q": RED, "refurb": "#F58AA3",
               "transit_back": "#D7B8EC", "yard_wait": "#FF7A59", "xfer": "#9B6FC2", "listed": PURPLE}

st.set_page_config(page_title="Inventory Flow Simulator", page_icon="🚗", layout="wide")
st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700&display=swap');
html, body, [class*="css"], .stMarkdown, .stMetric, button, input {{ font-family: 'Poppins', sans-serif !important; color: {PURPLE}; }}
.block-container {{ padding-top: 1.4rem; max-width: 1400px; }}
h1, h2, h3 {{ color: {PURPLE}; font-weight: 700; letter-spacing: -0.01em; }}
.kpi {{ background: {PALE}; border-left: 6px solid {RED}; border-radius: 8px; padding: 12px 16px; }}
.kpi .l {{ font-size: 12px; font-weight: 600; color: {VIOLET}; text-transform: uppercase; letter-spacing: .04em; }}
.kpi .v {{ font-size: 28px; font-weight: 700; color: {PURPLE}; line-height: 1.15; }}
.kpi .d {{ font-size: 13px; font-weight: 600; }}
.good {{ color: #0B7A3E; }} .bad {{ color: {RED}; }} .flat {{ color: {PURPLE}; }}
.note {{ background: {PALE}; border-radius: 8px; padding: 10px 14px; font-size: 14px; }}
.tag {{ display:inline-block; padding:2px 10px; border-radius: 12px; font-size: 12px; font-weight:600; }}
[data-testid="stSidebar"] {{ background: {PALE}; }}
</style>
""", unsafe_allow_html=True)

REPS = 6


# ----------------------------------------------------------------- cached runs
@st.cache_data(show_spinner=False)
def cached_run(kwargs_json: str, reps: int):
    return run(Params(**json.loads(kwargs_json)), reps=reps)


@st.cache_data(show_spinner=False)
def cached_sens(kwargs_json: str, reps: int):
    return I.sensitivity(json.loads(kwargs_json), reps=reps)


@st.cache_data(show_spinner=False)
def cached_fill(kwargs_json: str, reps: int):
    return I.fill_curve(json.loads(kwargs_json), reps=reps)


def kj(d):
    return json.dumps(d, sort_keys=True)


# ----------------------------------------------------------------- sidebar levers
st.sidebar.markdown("### Scenario")
preset = st.sidebar.selectbox("Start from", list(PRESETS.keys()), index=0)
pv = copy.deepcopy(PRESETS[preset])
if st.sidebar.button("Reset levers to preset"):
    for k in list(st.session_state.keys()):
        if k.startswith("lv_"):
            del st.session_state[k]


def key(n):
    return f"lv_{preset}_{n}"


with st.sidebar.expander("Supply: leads and inspection", expanded=True):
    lead = st.slider("Seller leads vs baseline", 0.7, 1.4, float(pv.get("lead_mult", 1.0)), 0.05, key=key("lead"))
    insp = st.slider("Inspection capacity", 0.8, 1.4, float(pv.get("inspect_mult", 1.0)), 0.05, key=key("insp"))
    accept = st.slider("Leads that become purchases", 0.35, 0.75, 0.55, 0.01, key=key("acc"))
with st.sidebar.expander("Restoration and spares", expanded=True):
    b_a = st.slider("Extra bays, Metro-A", 0, 40, int(pv.get("bay_add", {}).get("Metro-A", 0)), key=key("ba"))
    b_b = st.slider("Extra bays, Metro-B", 0, 40, int(pv.get("bay_add", {}).get("Metro-B", 0)), key=key("bb"))
    b_c = st.slider("Extra bays, Metro-C", 0, 40, int(pv.get("bay_add", {}).get("Metro-C", 0)), key=key("bc"))
    loc = {}
    for sp, d in (("Spoke-1", 0), ("Spoke-2", 0), ("Spoke-3", 0)):
        n = st.slider(f"Local restoration bays, {sp}", 0, 40, int(pv.get("spoke_local_bays", {}).get(sp, d)), key=key("l" + sp))
        if n > 0:
            loc[sp] = n
    fill = st.slider("Parts line fill rate", 0.80, 0.995, float(pv.get("fill_rate", 0.95)), 0.005, key=key("fill"))
    lead_days = st.slider("Parts emergency lead time (days)", 1, 7, int(pv.get("spares_lead_days", 3)), key=key("sl"))
    rework = st.slider("Final QC rework rate", 0.0, 0.20, 0.08, 0.01, key=key("rw"))
with st.sidebar.expander("Hubs, demand and pricing"):
    yard = st.slider("Yard space vs baseline", 0.8, 1.4, float(pv.get("yard_mult", 1.0)), 0.05, key=key("yard"))
    dem = st.slider("Buyer demand vs baseline", 0.7, 1.3, float(pv.get("demand_mult", 1.0)), 0.05, key=key("dem"))
    rebal = st.checkbox("Rebalance stock between cities", bool(pv.get("rebalance", False)), key=key("rb"))
    md_on = st.checkbox("Markdown aged cars", True, key=key("mdon"))
    md_age = st.slider("Markdown after (days listed)", 20, 90, int(pv.get("md_age", 60)), key=key("mda"))
    md_pct = st.slider("Markdown size", 0.01, 0.08, float(pv.get("md_pct", 0.03)), 0.005, key=key("mdp"))
with st.sidebar.expander("Money"):
    cap_rate = st.slider("Cost of capital, per year", 0.08, 0.18, 0.12, 0.005, key=key("cr"))
    depn = st.slider("Market price erosion, per month", 0.0, 0.025, 0.010, 0.001, key=key("dp"))

kwargs = {
    "lead_mult": lead, "inspect_mult": insp, "accept_rate": accept,
    "bay_add": {k: v for k, v in (("Metro-A", b_a), ("Metro-B", b_b), ("Metro-C", b_c)) if v},
    "spoke_local_bays": loc, "fill_rate": fill, "spares_lead_days": lead_days, "rework_prob": rework,
    "yard_mult": yard, "demand_mult": dem, "rebalance": rebal,
    "md_age": md_age if md_on else 0, "md_pct": md_pct, "capital_rate": cap_rate, "depn_month": depn,
}
base_kwargs = {}
_defaults = Params().to_dict()
kwargs = {k: v for k, v in kwargs.items() if v != _defaults.get(k) and v not in ({}, None)}

with st.spinner("Running replications"):
    base = cached_run(kj(base_kwargs), REPS)
    scen = cached_run(kj(kwargs), REPS)
changed = kj(kwargs) != kj(base_kwargs)
show = scen if changed else base

# ----------------------------------------------------------------- header
st.markdown(f"<h1 style='margin-bottom:0'>Inventory and refurbishment flow simulator</h1>", unsafe_allow_html=True)
st.markdown(f"<div class='note'>A synthetic, assumption-based model of a hub-and-spoke used-car pipeline: "
            f"seller lead, inspection, purchase, restoration, yard, sale. Every input is an assumption, so read "
            f"the <b>direction and size of changes</b>, not the absolute numbers. "
            f"Scenario: <b>{'custom levers' if changed else 'baseline'}</b>, {REPS} replications of "
            f"{show['params']['sim_days'] - show['params']['warmup']} measured days.</div>", unsafe_allow_html=True)
st.write("")


def kpi(col, label, key_, fmt, higher_better=False, unit=""):
    b = base["kpi"][key_]
    s = show["kpi"][key_]
    d = s - b
    cls = "flat"
    if changed and abs(d) > 1e-9:
        cls = "good" if ((d > 0) == higher_better) else "bad"
    delta = f"{'+' if d >= 0 else '-'}{fmt.format(abs(d))}{unit} vs baseline" if changed else "baseline"
    col.markdown(f"<div class='kpi'><div class='l'>{label}</div><div class='v'>{fmt.format(s)}{unit}</div>"
                 f"<div class='d {cls}'>{delta}</div></div>", unsafe_allow_html=True)


c = st.columns(6)
kpi(c[0], "Days in inventory", "days_in_inventory", "{:.1f}")
kpi(c[1], "Capital locked", "capital_cr", "{:.0f}", unit=" Cr")
kpi(c[2], "Sold after 45+ days", "aged_45", "{:.0%}")
kpi(c[3], "Refurb turnaround", "refurb_tat", "{:.1f}", unit=" d")
kpi(c[4], "Contribution per car", "contrib_per_car", "{:,.0f}", higher_better=True, unit=" INR")
kpi(c[5], "Seller leads lost", "leads_lost", "{:,.0f}")
st.write("")

tabs = st.tabs(["Where the days go", "Network heat map", "Scenario compare", "What moves the needle", "Spares trade-off", "Assumptions"])

# ----------------------------------------------------------------- tab 1
with tabs[0]:
    l, r = st.columns([1.35, 1])
    with l:
        st.subheader("Average days per car, by stage")
        fig = go.Figure()
        for lab, res in (("Baseline", base), ("Scenario", show)) if changed else (("Baseline", base),):
            st_t = I.stage_table(res)
            for _, row in st_t.iterrows():
                fig.add_trace(go.Bar(y=[lab], x=[row.days], name=row.stage, orientation="h",
                                     marker_color=STAGE_COLOR[row.key], showlegend=(lab == "Baseline"),
                                     hovertemplate=f"{row.stage}: %{{x:.1f}} days<extra></extra>",
                                     text=[f"{row.days:.1f}" if row.days >= 1.2 else ""], textposition="inside"))
        fig.update_layout(barmode="stack", height=230 if changed else 170, margin=dict(l=0, r=0, t=0, b=0),
                          legend=dict(orientation="h", y=-0.35, font=dict(size=11)), plot_bgcolor="white",
                          xaxis_title="days from purchase to sale")
        st.plotly_chart(fig, width="stretch")
        st.subheader("Capital locked and cars in the pipeline")
        d = show["daily"]
        d = d[d.day >= show["params"]["warmup"] - 30]
        f2 = go.Figure()
        f2.add_trace(go.Scatter(x=d.day, y=d.capital / 1e7, name="Capital locked (INR Cr)", line=dict(color=RED, width=3)))
        f2.add_trace(go.Scatter(x=d.day, y=d.refurb_queue_len, name="Cars waiting for a bay", yaxis="y2", line=dict(color=VIOLET, width=2)))
        f2.update_layout(height=280, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white",
                         legend=dict(orientation="h", y=-0.25), xaxis_title="simulation day",
                         yaxis=dict(title="INR Cr"), yaxis2=dict(title="cars waiting", overlaying="y", side="right"))
        st.plotly_chart(f2, width="stretch")
    with r:
        st.subheader("Read-out")
        for line in I.findings(show):
            st.markdown(f"<div class='note' style='margin-bottom:8px'>{line}</div>", unsafe_allow_html=True)
        st.subheader("Days sold after listing")
        sold = show["sold"]
        h = go.Figure(go.Histogram(x=sold.days, nbinsx=40, marker_color=PURPLE, histnorm="percent"))
        h.add_vline(x=45, line_color=RED, line_dash="dash", annotation_text="45 days")
        h.update_layout(height=230, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white", xaxis_title="days in inventory", yaxis_title="% of cars sold")
        st.plotly_chart(h, width="stretch")

# ----------------------------------------------------------------- tab 2
with tabs[1]:
    st.subheader("Which resource runs hot")
    cf = I.city_flags(show)
    t = cf[["city", "role", "bays", "bay_util", "bay_wait_days", "insp_util", "lead_loss_pct", "yard_wait_avg", "avg_days", "flag"]].copy()
    for _c in ("bay_util", "bay_wait_days"):
        t[_c] = pd.to_numeric(t[_c], errors="coerce")
    t.columns = ["City", "Role", "Bays", "Bay use", "Wait for bay (d)", "Inspection use", "Leads lost", "Yard wait (d)", "Avg days", "Flag"]

    def shade(v, lo, hi):
        if pd.isna(v):
            return ""
        a = min(max((v - lo) / (hi - lo), 0), 1)
        return f"background-color: rgba(237,38,79,{0.10 + 0.55 * a}); color: {PURPLE}; font-weight:600"

    sty = (t.style.format({"Bay use": "{:.0%}", "Wait for bay (d)": "{:.1f}", "Inspection use": "{:.0%}",
                           "Leads lost": "{:.1%}", "Yard wait (d)": "{:.1f}", "Avg days": "{:.0f}"}, na_rep="n/a")
           .map(lambda v: shade(v, 0.80, 1.0), subset=["Bay use", "Inspection use"])
           .map(lambda v: shade(v, 0, 2.5), subset=["Wait for bay (d)", "Yard wait (d)"])
           .map(lambda v: shade(v, 0, 0.03), subset=["Leads lost"]))
    st.dataframe(sty, width="stretch", hide_index=True)
    st.markdown("<div class='note'>Spokes ship cars to their parent centre and back, so Spoke-2 and Spoke-3 add load to Metro-B. "
                "Bays needed for a spoke is roughly its jobs a day times bay-days (about 4.5), divided by 0.85 target use.</div>",
                unsafe_allow_html=True)
    st.subheader("Cars per city, sold in the window")
    bar = go.Figure(go.Bar(x=cf.city, y=cf["sold"], marker_color=[PURPLE if "centre" in r else RED for r in cf.role]))
    bar.update_layout(height=260, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white", yaxis_title="cars (mean per replication)")
    st.plotly_chart(bar, width="stretch")

# ----------------------------------------------------------------- tab 3
with tabs[2]:
    st.subheader("Baseline vs your scenario")
    if not changed:
        st.info("Pick a preset or move a lever in the sidebar to compare.")
    kt = I.kpi_table(base, show if changed else None)
    good = kt.pop("_good") if "_good" in kt else None
    sty = kt.style.hide(axis="index")
    if good is not None:
        def colour(col):
            return [("color:#0B7A3E;font-weight:700" if g is True else (f"color:{RED};font-weight:700" if g is False else "")) for g in good]
        sty = sty.apply(colour, subset=["Change"])
    st.dataframe(sty, width="stretch", hide_index=True)
    if changed:
        months = 1.0
        b, s = base["kpi"], show["kpi"]
        dm = s["sold_per_month"] * s["contrib_per_car"] - b["sold_per_month"] * b["contrib_per_car"]
        st.markdown(f"<div class='note'>Contribution after holding costs changes by <b>INR {dm / 1e7:+.2f} Cr a month</b> "
                    f"(INR {dm * 12 / 1e7:+.1f} Cr a year) on this scaled network, and capital locked changes by "
                    f"<b>INR {s['capital_cr'] - b['capital_cr']:+.1f} Cr</b>. Compare that with the cost of the levers you pulled: "
                    f"the spend you can justify is roughly three years of the annual change.</div>", unsafe_allow_html=True)
    st.download_button("Download this scenario (JSON)", json.dumps({"levers": kwargs, "kpi": show["kpi"]}, indent=2),
                       file_name="scenario.json", mime="application/json")

# ----------------------------------------------------------------- tab 4
with tabs[3]:
    st.subheader("One lever at a time, from the baseline")
    st.caption("Nine levers, 4 replications each. Takes about a minute the first time, then it is cached.")
    if st.button("Run sensitivity", type="primary"):
        st.session_state["sens"] = cached_sens(kj(base_kwargs), 4)
    if "sens" in st.session_state:
        s = st.session_state["sens"].sort_values("d_contrib")
        fig = go.Figure(go.Bar(y=s.Lever, x=s.d_contrib, orientation="h",
                               marker_color=[RED if v < 0 else PURPLE for v in s.d_contrib],
                               text=[f"{v:+,.0f}" for v in s.d_contrib], textposition="outside"))
        fig.update_layout(height=420, margin=dict(l=0, r=60, t=10, b=0), plot_bgcolor="white",
                          xaxis_title="change in contribution per car (INR)")
        st.plotly_chart(fig, width="stretch")
        show_t = s.sort_values("d_contrib", ascending=False).rename(columns={
            "d_days": "Days", "d_capital": "Capital (Cr)", "d_tat": "Refurb TAT (d)", "d_contrib": "Contribution (INR/car)", "d_lost": "Leads lost"})
        st.dataframe(show_t.style.format({"Days": "{:+.1f}", "Capital (Cr)": "{:+.1f}", "Refurb TAT (d)": "{:+.2f}",
                                          "Contribution (INR/car)": "{:+,.0f}", "Leads lost": "{:+,.0f}"}), width="stretch", hide_index=True)

# ----------------------------------------------------------------- tab 5
with tabs[4]:
    st.subheader("Parts availability: what a higher fill rate costs and saves")
    st.caption("Each job needs 4 to 9 part lines. If one line is out of stock, the car stays on the lift for the emergency lead time. 4 replications per point.")
    if st.button("Run fill-rate curve", type="primary"):
        st.session_state["fill"] = cached_fill(kj({k: v for k, v in kwargs.items() if k != "fill_rate"}), 4)
    if "fill" in st.session_state:
        f = st.session_state["fill"]
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=f.fill_rate * 100, y=f.tat, name="Refurb turnaround (days)", line=dict(color=RED, width=3), mode="lines+markers"))
        fig.add_trace(go.Scatter(x=f.fill_rate * 100, y=f.spares_lakh, name="Spares working capital (INR lakh)", yaxis="y2", line=dict(color=PURPLE, width=3), mode="lines+markers"))
        fig.update_layout(height=340, margin=dict(l=0, r=0, t=10, b=0), plot_bgcolor="white", legend=dict(orientation="h", y=-0.25),
                          xaxis_title="parts line fill rate (%)", yaxis=dict(title="days"), yaxis2=dict(title="INR lakh", overlaying="y", side="right"))
        st.plotly_chart(fig, width="stretch")
        t = f.rename(columns={"fill_rate": "Fill rate", "tat": "Turnaround (d)", "contrib": "Contribution (INR/car)", "spares_lakh": "Spares capital (lakh)", "days": "Days in inventory", "capital_cr": "Capital (Cr)"})
        st.dataframe(t.style.format({"Fill rate": "{:.0%}", "Turnaround (d)": "{:.1f}", "Contribution (INR/car)": "{:,.0f}", "Spares capital (lakh)": "{:.1f}", "Days in inventory": "{:.1f}", "Capital (Cr)": "{:.0f}"}), width="stretch", hide_index=True)
    sp = show["spares"].copy()
    sp[["daily_spend", "cycle", "safety", "total"]] = sp[["daily_spend", "cycle", "safety", "total"]] / 1e5
    sp.columns = ["Restoration centre", "Parts spend per day (lakh)", "Cycle stock (lakh)", "Safety stock (lakh)", "Total (lakh)"]
    st.markdown("**Spares working capital at the current fill rate**")
    st.dataframe(sp.style.format("{:.1f}", subset=sp.columns[1:]), width="stretch", hide_index=True)

# ----------------------------------------------------------------- tab 6
with tabs[5]:
    st.subheader("What is sourced, derived and assumed")
    a = pd.DataFrame(ASSUMPTIONS, columns=["key", "Item", "Value", "Unit", "Tag", "Basis"]).drop(columns="key")
    st.dataframe(a, width="stretch", hide_index=True)
    st.markdown("**Network file** (`data/network.csv`). Edit it and rerun to model a different footprint.")
    st.dataframe(pd.read_csv("data/network.csv"), width="stretch", hide_index=True)
    st.caption("Synthetic data. Not affiliated with any company. Public figures come from press and filings cited in the README.")
