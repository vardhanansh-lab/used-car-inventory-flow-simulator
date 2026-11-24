# Strategy memo: making the used-car pipeline resilient

Synthetic network, assumption-based inputs. Numbers are means of 8 seeded replications of 210 measured days. Size and direction matter, absolute levels do not.

## 1. Recommendation

Do not buy capacity first. Fix parts availability and stock balance, pilot local restoration at the farthest spoke, and only then add bays and inspection. Each step has a measured gate (section 5).

## 2. Problem

A car earns nothing until it sells. In the baseline a car takes 39.0 days from purchase to sale, locks about Rs 176 Cr of capital across the network and earns Rs 9,979 after holding costs, against Rs 16,836 of holding cost per car.

| Stage | Days |
|---|---|
| Paperwork and pickup | 1.5 |
| Haul to hub and back | 0.8 |
| Wait for a bay | 1.1 |
| In the bay | 4.2 |
| Wait for yard space | 0.4 |
| Listed for sale | 31.0 |

The supply chain controls about 8 days. The fragility sits there, in queues:

| Condition | Refurb turnaround | Bay wait | Leads lost | Rs per car |
|---|---|---|---|---|
| Baseline | 5.3 d | 1.1 d | 97 | 9,979 |
| +10% seller leads | 8.4 d | 4.2 d | 387 | 7,438 (-25%) |
| Parts fill 95% to 90% | 13.3 d | 8.5 d | 84 | 7,148 (-28%) |
| Buyer demand -10% | 4.9 d | 0.7 d | 88 | 7,890 (-21%) |

Time in the bay barely moves across conditions. The damage is waiting.

Where it breaks at baseline: Metro-B bays at 99% use with an 85-car queue, since it carries Spoke-2 and Spoke-3. Spoke-2 and Spoke-3 inspection at 96% and 93%, losing about 1.8% and 1.4% of leads. Spoke-1 yard wait of 2.8 days. A demand dip is not fixable by supply levers: it lengthens listed time instead.

## 3. Solution

One lever at a time, from the baseline (change in contribution per car, Rs):

| Lever | Change |
|---|---|
| Local restoration at Spoke-3 (18 bays) | +556 |
| Rebalance aged stock between cities | +479 |
| Parts fill rate 95% to 98% | +226 |
| Yard space +15% | +128 |
| +10 bays at Metro-B | +109 |
| Inspection capacity +10% | -198 |
| Markdown 3% at 45 days | -1,853 |

Two lessons. Inspection alone hurts because it feeds more cars into bays that are already full. Markdown destroys more margin than the holding cost it saves.

Parts fill rate has sharply diminishing returns. From 95% to 98% costs about Rs 4 lakh of safety stock and removes about 1.4 days of repair delay. Beyond 98% the curve flattens.

| Fill rate | Refurb turnaround | Rs per car | Spares capital |
|---|---|---|---|
| 85% | 25.5 d | 3,252 | Rs 24.7 lakh |
| 90% | 13.3 d | 7,088 | Rs 28.7 lakh |
| 95% | 5.2 d | 10,007 | Rs 32.9 lakh |
| 98% | 3.8 d | 10,233 | Rs 36.9 lakh |
| 99% | 3.6 d | 10,187 | Rs 39.4 lakh |

**The package, in order:** parts fill 98%, stock rebalancing (cars 25+ days old, from cities above 32 days of supply to cities below 22, max 6 a day), local restoration at Spoke-3 (18 bays), +10 bays at Metro-B, then inspection +10% and yard +10%.

| | Baseline | +10% leads | Surge with package | Normal with package |
|---|---|---|---|---|
| Days in stock | 39.0 | 44.7 | 40.2 | 37.1 |
| Refurb turnaround | 5.3 | 8.4 | 3.8 | 3.8 |
| Bay wait | 1.1 | 4.2 | 0.05 | 0.02 |
| Leads lost | 97 | 387 | 77 | 12 |
| Capital, Rs Cr | 176 | 227 | 203 | 167 |
| Rs per car | 9,979 | 7,438 | 9,563 | 11,339 |
| Cars a month | 2,144 | 2,208 | 2,334 | 2,184 |

### Illustrative economics

At normal load the package adds about Rs 4.0 Cr a year of contribution on this scaled network and releases about Rs 9.6 Cr of capital. In a surge it adds about Rs 0.59 Cr a month. Assumed cost for the 28 extra bays is Rs 1.1 Cr once (Rs 4 lakh fit-out each) and Rs 1.7 Cr a year (Rs 6 lakh staffing each). These cost inputs are placeholders, so validate them before relying on the net figure.

## 4. Implementation

The simulator (`app.py`) is the testing ground: change a lever, see turnaround, queues, capital and contribution against baseline before spending anything. Phase 1 replaces assumptions with actuals, so the model is only trusted once it matches reality.

## 5. Rollout and gates

| Phase | Weeks | Actions | Gate to proceed |
|---|---|---|---|
| Measure | 0 to 4 | Timestamp every stage from lead to sale. Log parts fill by line and utilisation by city. Recalibrate the model. | Model within 10% of actual days at each stage |
| Fix without capex | 4 to 12 | Parts fill to 98% on fast lines. Start the rebalancing rule. Alert on cars aged 25+ days. | Refurb turnaround under 4.5 days and 45+ day share falling |
| Add capacity in order | 12 to 26 | Pilot Spoke-3 local restoration, then +10 bays at Metro-B, then inspection and yard. | Metro-B bay use under 92% and queue under 0.5 days in a surge test |

Optional: an aged-inventory alert bot on the same data that flags cars approaching the rebalancing threshold.

## 6. Risks

| Risk | Mitigation |
|---|---|
| Inputs are assumptions | Phase 1 recalibration, every input tagged in the register |
| Bay staffing lags fit-out | Hire ahead of the festive peak |
| Local restoration quality varies | QC audit, track rework (modelled at 8%) by site |
| Transfers dent demand fit | Cap at 6 a day, aged cars only |

## 7. What is sourced, derived and assumed

See `data/assumptions.csv`. Sourced items are public FY25 figures and network footprint. Derived items include direct cost per car and bay sizing to about 85% use. Everything else, including prices, refurb costs, lead volumes, fill rate, parts lines, margin and cost of capital, is an assumption.

## 8. Reproduce

`python scripts/make_results.py` regenerates `results/` and every table above. Seeds are fixed.
