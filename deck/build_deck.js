// Builds Spinny_Inventory_Flow_Deck.pptx from results/. Run: node build_deck.js
const pptxgen = require("pptxgenjs");
const fs = require("fs");
const path = require("path");
const S = JSON.parse(fs.readFileSync(path.join(__dirname, "..", "results", "summary.json")));
const SENS = fs.readFileSync(path.join(__dirname, "..", "results", "sensitivity.csv"), "utf8").trim().split("\n").slice(1).map(r => r.split(","));

const P = "2E054E", R = "ED264F", V = "6300A3", PALE = "F6EEFB", LIL = "C9A7E8", W = "FFFFFF", MID = "9B6FC2", ROSE = "F58AA3";
const F = "Poppins";
const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE"; // 13.33 x 7.5
pres.title = "Used-car inventory and refurbishment flow simulator";
pres.author = "Ansh Vardhan";

const B = S["Baseline"], SU = S["Festive surge: +10% seller leads"], PK = S["Surge with resilience package"],
  PN = S["Resilience package, normal load"], PS = S["Parts shock: fill rate falls to 90%"], DD = S["Demand dip: -10% buyer demand"];
const k = (x) => x.kpi;
const st = (x, key) => x.stages.find(s => s.key === key).days;
const f1 = (v) => v.toFixed(1), f0 = (v) => Math.round(v).toLocaleString("en-IN");
const supplyDays = (x) => ["lag", "transit_out", "refurb_q", "refurb", "transit_back", "yard_wait", "xfer"].reduce((a, key) => a + st(x, key), 0);

// ---- grid: three equal columns, shared rows
const X0 = 0.45, GAP = 0.2, CW = (12.43 - 2 * GAP) / 3;
const CX = [X0, X0 + CW + GAP, X0 + 2 * (CW + GAP)];
const CHIP_Y = 1.62, CHIP_H = 0.34, TOP = 2.04, BOT = 6.84;
const NUDGE = -0.025; // Poppins sits low in a centred box; lift text slightly

function frame(slide, active, title) {
  slide.background = { color: W };
  ["1  Problem analysis", "2  Solution", "3  Implementation"].forEach((n, i) => {
    slide.addShape(pres.ShapeType.roundRect, { x: X0 + i * 2.3, y: 0.26, w: 2.2, h: 0.36, rectRadius: 0.18, fill: { color: i === active ? R : PALE }, line: { color: i === active ? R : PALE, width: 0 } });
    slide.addText(n, { x: X0 + i * 2.3, y: 0.26 + NUDGE, w: 2.2, h: 0.36, color: i === active ? W : P, fontFace: F, fontSize: 11, bold: true, align: "center", valign: "middle", margin: 0, isTextBox: true });
  });
  slide.addText("Inventory flow simulator  |  synthetic data", { x: 8.4, y: 0.26 + NUDGE, w: 4.48, h: 0.36, fontFace: F, fontSize: 10, color: V, bold: true, align: "right", valign: "middle", margin: 0, isTextBox: true });
  slide.addText(title, { x: X0, y: 0.76, w: 12.43, h: 0.76, fontFace: F, fontSize: 20, bold: true, color: P, valign: "top", margin: 0, isTextBox: true, objectName: "Title" });
}
function chip(slide, t, x, y, w) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h: CHIP_H, rectRadius: 0.06, fill: { color: P }, line: { color: P, width: 0 } });
  slide.addText(t, { x: x + 0.14, y: y + NUDGE, w: w - 0.28, h: CHIP_H, fontFace: F, fontSize: 11, bold: true, color: W, valign: "middle", margin: 0, isTextBox: true });
}
function box(slide, x, y, w, h, fill, r) {
  slide.addShape(pres.ShapeType.roundRect, { x, y, w, h, rectRadius: r || 0.08, fill: { color: fill || PALE }, line: { color: fill || PALE, width: 0 } });
}
// padded text on a card; runs may be a string or an array of runs
function cardText(slide, runs, x, y, w, h, o) {
  o = o || {};
  slide.addText(runs, Object.assign({ x: x + 0.14, y: y + NUDGE, w: w - 0.28, h, fontFace: F, fontSize: 10, color: P, valign: "middle", margin: 0, isTextBox: true }, o));
}
function source(slide, t) {
  slide.addText(t, { x: X0, y: 6.98, w: 12.43, h: 0.3, fontFace: F, fontSize: 9, color: V, margin: 0, valign: "middle", isTextBox: true });
}
function tile(slide, x, y, w, h, big, label, color) {
  box(slide, x, y, w, h);
  slide.addText(big, { x: x + 0.14, y: y + 0.06 + NUDGE, w: w - 0.28, h: 0.46, fontFace: F, fontSize: 20, bold: true, color: color || P, margin: 0, valign: "middle", isTextBox: true });
  slide.addText(label, { x: x + 0.14, y: y + 0.5, w: w - 0.28, h: h - 0.56, fontFace: F, fontSize: 10, color: P, margin: 0, valign: "top", isTextBox: true });
}
function dot(slide, n, x, y) {
  slide.addShape(pres.ShapeType.ellipse, { x, y, w: 0.26, h: 0.26, fill: { color: R }, line: { color: W, width: 1 } });
  slide.addText(String(n), { x, y: y + NUDGE, w: 0.26, h: 0.26, fontFace: F, fontSize: 10, bold: true, color: W, align: "center", valign: "middle", margin: 0, isTextBox: true });
}
const hdr = (t, al) => ({ text: t, options: { bold: true, color: W, fill: { color: P }, fontFace: F, fontSize: 10, align: al || "left", valign: "middle" } });
const cell = (t, o) => ({ text: String(t), options: Object.assign({ fontFace: F, fontSize: 10, color: P, valign: "middle", fill: { color: PALE } }, o || {}) });
const TBL = { border: { type: "solid", pt: 0.5, color: LIL }, margin: [0, 0.08, 0, 0.08] };

// ============================================================ SLIDE 1: PROBLEM
{
  const s = pres.addSlide();
  frame(s, 0, "The network is balanced on average and fragile at the edges: a 10% lead surge or a parts miss cuts margin per car by about a quarter");
  const kb = k(B);
  // col A
  chip(s, "The situation", CX[0], CHIP_Y, CW);
  s.addText("A hub-and-spoke network buys used cars from sellers in six cities. Three metro hubs restore cars on 349 bays. Three spokes inspect, buy and ship cars to a hub and back. A car earns nothing until it sells, so every day in the pipeline costs capital, yard space and price erosion.", { x: CX[0], y: TOP, w: CW, h: 1.2, fontFace: F, fontSize: 11, color: P, margin: 0, valign: "top", isTextBox: true });
  const tw = (CW - 0.1) / 2, th = 0.93;
  const tiles = [
    [f1(kb.days_in_inventory), "days from purchase to sale", P], [f1(st(B, "listed")) + " d", "of those spent listed for sale", R],
    ["Rs " + f0(kb.capital_cr) + " Cr", "capital locked in cars", P], [Math.round(kb.aged_45 * 100) + "%", "of cars sold after 45+ days", R],
    ["Rs " + f0(kb.holding_per_car), "holding cost per car", P], ["Rs " + f0(kb.contrib_per_car), "contribution per car, after holding", P]];
  tiles.forEach((t, i) => tile(s, CX[0] + (i % 2) * (tw + 0.1), 3.3 + Math.floor(i / 2) * (th + 0.08), tw, th, t[0], t[1], t[2]));
  // col B
  chip(s, "Supply-controlled days per car", CX[1], CHIP_Y, CW);
  const cats = ["Baseline", "+10% leads", "Parts fill 90%"];
  const mk = (name, fn) => ({ name, labels: cats, values: [fn(B), fn(SU), fn(PS)].map(v => +v.toFixed(2)) });
  s.addChart(pres.charts.BAR, [
    mk("Paperwork", x => st(x, "lag")), mk("Haul both ways", x => st(x, "transit_out") + st(x, "transit_back")),
    mk("Wait for bay", x => st(x, "refurb_q")), mk("In the bay", x => st(x, "refurb")), mk("Wait for yard", x => st(x, "yard_wait") + st(x, "xfer"))], {
    x: CX[1] - 0.05, y: 2.0, w: CW + 0.1, h: 2.5, barDir: "col", barGrouping: "stacked", chartColors: [LIL, MID, R, V, ROSE],
    showValue: true, dataLabelFontSize: 10, dataLabelColor: W, dataLabelFontFace: F, dataLabelFormatCode: "[>=1.6]0.0;;", dataLabelPosition: "ctr",
    catAxisLabelFontSize: 10, catAxisLabelColor: P, catAxisLabelFontFace: F, valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" },
    showLegend: true, legendPos: "b", legendFontSize: 10, legendColor: P, legendFontFace: F, barGapWidthPct: 45, valAxisMaxVal: 17 });
  const stw = (CW - 0.2) / 3;
  [[B, "Baseline"], [SU, "+10% leads"], [PS, "Parts fill 90%"]].forEach((a, i) => {
    const x = CX[1] + i * (stw + 0.1);
    box(s, x, 4.58, stw, 0.62);
    s.addText([{ text: f1(supplyDays(a[0])) + " days", options: { bold: true, fontSize: 12, breakLine: true } }, { text: a[1], options: { fontSize: 10 } }], { x, y: 4.58 + NUDGE, w: stw, h: 0.62, fontFace: F, color: i === 0 ? P : R, align: "center", valign: "middle", margin: 0, isTextBox: true });
  });
  box(s, CX[1], 5.28, CW, 0.97);
  cardText(s, "Time in the bay barely moves (4.2 to 4.8 days). Waiting for a bay goes from " + f1(st(B, "refurb_q")) + " days to " + f1(st(SU, "refurb_q")) + " in a surge and " + f1(st(PS, "refurb_q")) + " when parts fill drops. The damage is queueing, not work content.", CX[1], 5.28, CW, 0.97);
  // col C
  chip(s, "Where it breaks today", CX[2], CHIP_Y, CW);
  const cb = (n) => B.city.find(c => c.city === n);
  const bad = { color: R, bold: true };
  s.addTable([
    [hdr("City"), hdr("Binding limit"), hdr("Effect")],
    [cell("Metro-B", { bold: true }), cell("Bays " + Math.round(cb("Metro-B").bay_util * 100) + "% used"), cell("85 cars, " + f1(cb("Metro-B").refurb_queue / (cb("Metro-B").jobs / 210)) + " d wait", bad)],
    [cell("Spoke-2", { bold: true }), cell("Inspection " + Math.round(cb("Spoke-2").insp_util * 100) + "%"), cell(f1(cb("Spoke-2").leads_lost / cb("Spoke-2").leads_in * 100) + "% leads lost", bad)],
    [cell("Spoke-3", { bold: true }), cell("Inspection " + Math.round(cb("Spoke-3").insp_util * 100) + "%"), cell(f1(cb("Spoke-3").leads_lost / cb("Spoke-3").leads_in * 100) + "% leads lost", bad)],
    [cell("Spoke-1", { bold: true }), cell("Yard space"), cell(f1(cb("Spoke-1").yard_wait_avg) + " d yard wait", bad)],
    [cell("Metro-A", { bold: true }), cell("Bays " + Math.round(cb("Metro-A").bay_util * 100) + "%"), cell("No queue")],
    [cell("Metro-C", { bold: true }), cell("Bays " + Math.round(cb("Metro-C").bay_util * 100) + "%"), cell("No queue")]],
    Object.assign({ x: CX[2], y: TOP, w: CW, colW: [0.85, 1.4, CW - 2.25], rowH: 0.29 }, TBL));
  chip(s, "Stress tests, same network", CX[2], 4.26, CW);
  const row = (n, x) => [cell(n, { bold: true }), cell(f1(k(x).refurb_tat) + " d", { align: "right" }), cell(f0(k(x).leads_lost), { align: "right" }), cell(f0(k(x).contrib_per_car), { align: "right", bold: true })];
  s.addTable([
    [hdr("Condition"), hdr("TAT", "right"), hdr("Leads lost", "right"), hdr("Rs / car", "right")],
    row("Baseline", B), row("+10% leads", SU), row("Parts fill 90%", PS), row("Demand -10%", DD)],
    Object.assign({ x: CX[2], y: 4.66, w: CW, colW: [1.3, 0.7, 1.0, CW - 3.0], rowH: 0.312 }, TBL));
  // band
  const pct = (x) => Math.abs(Math.round((k(x).contrib_per_car / k(B).contrib_per_car - 1) * 100));
  box(s, X0, 6.36, 12.43, 0.48, P);
  s.addText([{ text: "Listing time (31 of 39 days) is sales-side. Supply chain owns the other 8 days, and a lead surge or parts miss cuts margin per car by " + pct(SU) + " to " + pct(PS) + "%.", options: { bold: true } }],
    { x: X0 + 0.15, y: 6.36 + NUDGE, w: 12.13, h: 0.48, fontFace: F, fontSize: 11, color: W, valign: "middle", margin: 0, isTextBox: true });
  source(s, "Source: simulator output, 8 seeded replications of 210 measured days after a 120-day warm-up. All volumes, costs and capacities are assumptions or derived.");
}

// ============================================================ SLIDE 2: SOLUTION
{
  const s = pres.addSlide();
  frame(s, 1, "A sequenced package cuts surge turnaround from " + f1(k(SU).refurb_tat) + " to " + f1(k(PK).refurb_tat) + " days and recovers Rs " + f0(k(PK).contrib_per_car - k(SU).contrib_per_car) + " a car; most levers alone add little or backfire");
  // col A
  chip(s, "Each lever alone: Rs per car", CX[0], CHIP_Y, CW);
  const lev = SENS.filter(r => !/Seller leads|Buyer demand/.test(r[0])).map(r => ({ n: r[0], d: +r[4] })).sort((a, b) => a.d - b.d);
  const short = { "Local restoration at Spoke-3 (18 bays)": "Local restoration, Spoke-3", "Rebalance stock between cities": "Rebalance stock", "Parts fill rate 98% (from 95%)": "Parts fill 98%", "Yard space +15%": "Yard space +15%", "Add 10 bays at Metro-B": "+10 bays, Metro-B", "Inspection capacity +10%": "Inspection +10%", "Markdown at 45 days (3%)": "Markdown at 45 days" };
  s.addChart(pres.charts.BAR, [{ name: "Change in Rs per car", labels: lev.map(l => short[l.n] || l.n), values: lev.map(l => Math.round(l.d)) }],
    { x: CX[0] - 0.05, y: 2.0, w: CW + 0.1, h: 2.55, barDir: "bar", chartColors: lev.map(l => l.d >= 0 ? V : R), showValue: true, dataLabelFormatCode: "+#,##0;-#,##0", dataLabelFontSize: 10, dataLabelColor: P, dataLabelFontFace: F, dataLabelPosition: "outEnd",
      catAxisLabelFontSize: 10, catAxisLabelColor: P, catAxisLabelFontFace: F, catAxisLabelPos: "low", valAxisHidden: true, valGridLine: { style: "none" }, catGridLine: { style: "none" }, showLegend: false, barGapWidthPct: 35, valAxisMinVal: -3000, valAxisMaxVal: 1500 });
  box(s, CX[0], 4.65, CW, 1.05);
  cardText(s, [{ text: "Inspection alone hurts. ", options: { bold: true, color: R } }, { text: "It feeds more cars into bays that are already full, so the queue grows. Capacity has to be added downstream first.", options: {} }], CX[0], 4.65, CW, 1.05);
  box(s, CX[0], 5.79, CW, 1.05);
  cardText(s, [{ text: "Markdown at 45 days costs Rs 1,853 a car. ", options: { bold: true, color: R } }, { text: "The price given up exceeds the holding cost saved, so ageing is better fixed upstream.", options: {} }], CX[0], 5.79, CW, 1.05);
  // col B
  chip(s, "Recommended package, in order", CX[1], CHIP_Y, CW);
  const items = [
    ["Parts fill 95% to 98%", "Rs 4 lakh more safety stock removes about 1.4 days of repair delay."],
    ["Rebalance aged stock", "Move cars 25+ days old from cities above 32 days of supply to those below 22."],
    ["Restore locally at Spoke-3", "18 bays remove a 3-day haul each way and unload Metro-B."],
    ["+10 bays at Metro-B", "Takes the hub off 99% use so a surge has headroom."],
    ["Inspection +10%, then yard +10%", "Only after bays, so extra cars have somewhere to go."]];
  const ih = 0.88, ig = (BOT - TOP - 5 * ih) / 4;
  items.forEach((it, i) => {
    const y = TOP + i * (ih + ig);
    box(s, CX[1], y, CW, ih);
    s.addShape(pres.ShapeType.ellipse, { x: CX[1] + 0.14, y: y + (ih - 0.46) / 2, w: 0.46, h: 0.46, fill: { color: R }, line: { color: R, width: 0 } });
    s.addText(String(i + 1), { x: CX[1] + 0.14, y: y + (ih - 0.46) / 2 + NUDGE, w: 0.46, h: 0.46, fontFace: F, fontSize: 13, bold: true, color: W, align: "center", valign: "middle", margin: 0, isTextBox: true });
    s.addText([{ text: it[0], options: { bold: true, fontSize: 11, breakLine: true } }, { text: it[1], options: { fontSize: 10 } }], { x: CX[1] + 0.76, y: y + NUDGE, w: CW - 0.9, h: ih, fontFace: F, color: P, margin: 0, valign: "middle", isTextBox: true });
  });
  // col C
  chip(s, "What the simulator shows", CX[2], CHIP_Y, CW);
  const r = (label, fn, fmt) => [cell(label, { bold: true }), ...[B, SU, PK, PN].map((x, i) => cell(fmt(fn(x)), { align: "right", bold: i >= 2, color: i >= 2 ? V : P }))];
  s.addTable([
    [hdr("Metric"), hdr("Base", "right"), hdr("Surge", "right"), hdr("Surge\n+ pkg", "right"), hdr("Normal\n+ pkg", "right")],
    r("Days in stock", x => k(x).days_in_inventory, f1),
    r("Refurb TAT (d)", x => k(x).refurb_tat, f1),
    r("Bay wait (d)", x => st(x, "refurb_q"), v => v < 0.1 ? "0.0" : f1(v)),
    r("Leads lost", x => k(x).leads_lost, f0),
    r("Capital (Cr)", x => k(x).capital_cr, f0),
    r("Rs per car", x => k(x).contrib_per_car, f0),
    r("Cars a month", x => k(x).sold_per_month, f0)],
    Object.assign({ x: CX[2], y: TOP, w: CW, colW: [1.25, 0.55, 0.6, 0.75, CW - 3.15], rowH: [0.5, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3, 0.3] }, TBL));
  const mB = k(B).sold_per_month * k(B).contrib_per_car, mN = k(PN).sold_per_month * k(PN).contrib_per_car, mS = k(SU).sold_per_month * k(SU).contrib_per_car, mP = k(PK).sold_per_month * k(PK).contrib_per_car;
  const yr = (mN - mB) * 12 / 1e7, sm = (mP - mS) / 1e7;
  box(s, CX[2], 4.74, CW, 1.0);
  cardText(s, "Surge plus package beats the unmitigated surge on every line: " + f0(k(SU).leads_lost - k(PK).leads_lost) + " fewer leads lost, Rs " + f0(k(SU).capital_cr - k(PK).capital_cr) + " Cr less capital, 4.6 fewer repair days. At normal load it also gives " + f1(k(B).days_in_inventory - k(PN).days_in_inventory) + " fewer days and Rs " + f0(k(PN).contrib_per_car - k(B).contrib_per_car) + " more per car.", CX[2], 4.74, CW, 1.0);
  box(s, CX[2], 5.84, CW, 1.0, P);
  cardText(s, [{ text: "Illustrative economics. ", options: { bold: true, color: ROSE } }, { text: "+Rs " + yr.toFixed(1) + " Cr a year at normal load and +Rs " + sm.toFixed(2) + " Cr a month in a surge, plus Rs 9.6 Cr of capital released. Assumed cost for 28 bays: Rs 1.1 Cr once and Rs 1.7 Cr a year.", options: { color: W } }], CX[2], 5.84, CW, 1.0);
  source(s, "Source: simulator output, 8 seeded replications (one-lever sensitivity: 6). Rs = Indian rupees. Bay costs are assumptions, not company data.");
}

// ============================================================ SLIDE 3: IMPLEMENTATION
{
  const s = pres.addSlide();
  frame(s, 2, "Implementation: test every lever in the simulator first, then roll out over 26 weeks with a measured gate before each phase spends money");
  // col A
  chip(s, "The tool (Streamlit, runs locally)", CX[0], CHIP_Y, CW);
  const sh = CW * 0.625;
  s.addImage({ path: path.join(__dirname, "..", "assets", "app_scenario.png"), x: CX[0], y: TOP, w: CW, h: sh, objectName: "App screenshot" });
  s.addShape(pres.ShapeType.rect, { x: CX[0], y: TOP, w: CW, h: sh, fill: { color: W, transparency: 100 }, line: { color: P, width: 1 } });
  const px = (a, b) => [CX[0] + a * CW / 1600 - 0.13, TOP + b * CW / 1600 - 0.13];
  [[285, 173], [1500, 190], [1015, 470], [1500, 395]].forEach((d, i) => { const p = px(d[0], d[1]); dot(s, i + 1, p[0], p[1]); });
  s.addText([
    { text: "1 ", options: { bold: true, color: R } }, { text: "Pick a preset or move 20+ levers. " },
    { text: "2 ", options: { bold: true, color: R } }, { text: "Six KPIs vs baseline. " },
    { text: "3 ", options: { bold: true, color: R } }, { text: "Days by stage. " },
    { text: "4 ", options: { bold: true, color: R } }, { text: "Plain-language read-out. More tabs: city heat map, compare, sensitivity, spares." }],
    { x: CX[0], y: 4.66, w: CW, h: 0.6, fontFace: F, fontSize: 10, color: P, margin: 0, valign: "top", isTextBox: true });
  chip(s, "How the model moves a car", CX[0], 5.42, CW);
  const flow = ["Lead", "Insp.", "Buy", "Haul", "Bay", "QC", "Yard", "Sell"];
  const fg = 0.07, fw = (CW - 7 * fg) / 8;
  flow.forEach((t, i) => {
    const x = CX[0] + i * (fw + fg);
    s.addShape(pres.ShapeType.roundRect, { x, y: 5.86, w: fw, h: 0.4, rectRadius: 0.05, fill: { color: i === 4 ? R : PALE }, line: { color: i === 4 ? R : PALE, width: 0 } });
    s.addText(t, { x, y: 5.86 + NUDGE, w: fw, h: 0.4, fontFace: F, fontSize: 10, bold: true, color: i === 4 ? W : P, align: "center", valign: "middle", margin: 0, isTextBox: true });
  });
  s.addText("Daily steps, Poisson demand, queues for inspection and bays, parts stock-outs, QC rework and yard limits.", { x: CX[0], y: 6.38, w: CW, h: 0.46, fontFace: F, fontSize: 10, color: P, margin: 0, valign: "top", isTextBox: true });
  // col B
  chip(s, "26-week rollout with gates", CX[1], CHIP_Y, CW);
  const ph = [
    ["Weeks 0 to 4: Measure", "Timestamp every stage from lead to sale, log parts fill by line, then recalibrate the model to actuals.", "Gate: model within 10% of actual days at each stage"],
    ["Weeks 4 to 12: Fix without capex", "Parts fill to 98% on fast lines. Start the rebalancing rule and alerts on cars aged 25+ days.", "Gate: refurb TAT under 4.5 days, 45+ day share falling"],
    ["Weeks 12 to 26: Add capacity in order", "Pilot Spoke-3 local restoration, then +10 bays at Metro-B, then inspection and yard.", "Gate: Metro-B bays under 92% and queue under 0.5 days in a surge test"]];
  const pg = 0.1, phh = (BOT - TOP - 2 * pg) / 3;
  ph.forEach((p, i) => {
    const y = TOP + i * (phh + pg);
    box(s, CX[1], y, CW, phh);
    s.addText(p[0], { x: CX[1] + 0.14, y: y + 0.08 + NUDGE, w: CW - 0.28, h: 0.3, fontFace: F, fontSize: 11, bold: true, color: P, margin: 0, valign: "middle", isTextBox: true });
    s.addText(p[1], { x: CX[1] + 0.14, y: y + 0.42, w: CW - 0.28, h: 0.62, fontFace: F, fontSize: 10, color: P, margin: 0, valign: "top", isTextBox: true });
    box(s, CX[1] + 0.1, y + phh - 0.54, CW - 0.2, 0.44, P, 0.06);
    s.addText(p[2], { x: CX[1] + 0.2, y: y + phh - 0.54 + NUDGE, w: CW - 0.4, h: 0.44, fontFace: F, fontSize: 10, bold: true, color: W, margin: 0, valign: "middle", isTextBox: true });
  });
  // col C
  chip(s, "Risks and mitigations", CX[2], CHIP_Y, CW);
  const rk = (a, b) => [cell(a, { bold: true }), cell(b)];
  s.addTable([
    [hdr("Risk"), hdr("Mitigation")],
    rk("Inputs are assumptions", "Phase 1 recalibration; every input tagged in the register"),
    rk("Bay staffing lags fit-out", "Hire ahead of the festive peak"),
    rk("Local restoration quality", "QC audit; track the 8% rework rate by site"),
    rk("Transfers dent demand fit", "Cap at 6 a day, aged cars only")],
    Object.assign({ x: CX[2], y: TOP, w: CW, colW: [1.45, CW - 1.45], rowH: [0.3, 0.54, 0.44, 0.54, 0.44] }, TBL));
  chip(s, "Sourced, derived, assumed", CX[2], 4.4, CW);
  const tg = (t, c) => ({ text: t + "  ", options: { bold: true, color: c } });
  s.addText([
    tg("Sourced", V), { text: "public network shape: hubs, restoration centres, spares and inventory duties", options: { breakLine: true } },
    tg("Derived", V), { text: "bays sized to about 85% use; spares as cycle plus safety stock", options: { breakLine: true } },
    tg("Assumed", R), { text: "prices, refurb cost, leads, fill rate, parts lines, margin, capital cost", options: {} }],
    { x: CX[2], y: 4.84, w: CW, h: 1.2, fontFace: F, fontSize: 10, color: P, margin: 0, valign: "top", paraSpaceAfter: 5, isTextBox: true });
  box(s, CX[2], 6.14, CW, 0.7, P);
  s.addText([{ text: "streamlit run app.py", options: { breakLine: true } }, { text: "pytest tests", options: { breakLine: true } }, { text: "python scripts/make_results.py", options: {} }], { x: CX[2] + 0.14, y: 6.14 + NUDGE, w: CW - 0.28, h: 0.7, fontFace: "Courier New", fontSize: 10, bold: true, color: W, margin: 0, valign: "middle", isTextBox: true });
  source(s, "Source: README and data/assumptions.csv in the repository. No company data was used; the network file is synthetic and editable.");
}

pres.writeFile({ fileName: path.join(__dirname, "Spinny_Inventory_Flow_Deck.pptx") }).then(() => console.log("written"));
