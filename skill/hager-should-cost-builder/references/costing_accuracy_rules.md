# Should-Cost Accuracy Rules
# These rules are MANDATORY for every model built by this skill.
# They exist to prevent systematic overestimation. Read before building any model.

---

## Rule 1 — Nesting Efficiency and Scrap Credit (Material)

**The problem:** Calculating material cost from net part weight alone ignores sheet utilisation.
A 9-part assembly cut from 1.5 mm stainless sheet does NOT consume one rectangle per part.
A nesting program packs parts together, leaving a skeleton of scrap.

**Mandatory inputs:**
- `Material utilization / nesting yield` (%) — what fraction of the purchased sheet ends up in finished parts.
  - Typical range: **55–80%** for laser-cut sheet-metal assemblies (complex geometry → lower end).
  - Derive from: CAD nesting simulation if available; otherwise use drawing geometry to estimate bounding box vs. part area ratio; default to 65% for complex multi-part assemblies.
- `Scrap recovery credit` (%) — the fraction of scrap material cost recovered by selling skeleton offcuts to a metal recycler.
  - Typical range: **10–25%** of raw material cost for stainless, carbon steel, aluminum.
  - Apply as: `Scrap credit = (1 − nesting yield) × material price/kg × gross weight × scrap_recovery_pct`

**Formula for gross material cost:**
```
Gross weight (kg/asm)     = Net weight / (Nesting yield / 100)
Sheet metal cost (€/asm)  = Gross weight × Material price/kg − Scrap credit
```

**Never omit the nesting yield.** Calculating `net weight × price` without a yield factor is wrong — it underestimates material consumption and ignores that the supplier buys and charges for the whole sheet.

---

## Rule 2 — Setup Cost Amortisation Over Correct Batch Size

**The problem:** Setup cost amortised over annual volume instead of batch (lot) size massively underestimates per-unit setup cost for low-volume materials.

**Mandatory formula:**
```
Setup cost per unit (€/asm) = (Setup time h/lot × Setup rate €/h × Lot count/yr) / Annual volume
```

Which simplifies to:
```
Setup cost per unit = Setup time h/lot × Setup rate €/h / Avg lot size
```

**Key inputs to always include:**
- `Lot count per year` (#/yr) — how many separate production runs per year. **From HAGER PPE order history — mandatory for reference materials.**
- `Avg lot size` (PC/lot) = Annual volume / Lot count
- `Setup time per lot` (h/lot) — total setup across ALL machines in the routing (laser program load + brake tool change + weld fixture change). For multi-machine routings, sum them.

**Validation check:** If `Avg lot size < 20` and `Setup time > 4h/lot`, setup will be a major cost driver. Flag this explicitly and verify lot count with the buyer.

**Never divide setup cost by annual volume directly.** The formula must use lot count per year in the numerator.

---

## Rule 3 — Feature-Based Costing: Separate Critical from Non-Critical Features

**The problem:** Applying one uniform cycle time to all features over-charges for operations that only apply to tight-tolerance or critical surfaces.

**Mandatory classification when deriving cycle times:**

| Feature type | Definition | Time factor |
|---|---|---|
| Critical / precision | Mating surfaces, datum holes, thread features, GD&T callouts, sealing faces | Full time, no reduction |
| Standard / functional | Structural welds, punched holes without tolerance, bends within ±1° | Standard time |
| Non-critical / cosmetic | Outer profile, weight-reduction cutouts, cosmetic slots | Apply fast-pass factor (0.5–0.7×) |

**For welded subassemblies specifically:**
- Not every weld joint requires the same weld quality. Root-forming + passivation applies only to fluid-contact seams on pharma/food parts.
- Separate: (a) structural/tack welds (fast, lower cost), (b) full-penetration seam welds (slower, higher cost), (c) cosmetic/cap welds (fastest).
- State in column H of Inputs tab which standard each weld type is held to and cite the drawing or MAI spec.

**General tolerance audit before building the model:**
1. Read the title block tolerance (e.g. ±0.5mm general).
2. Identify features with **tighter** tolerances called out explicitly — these are the critical features.
3. All other features carry the title block tolerance, NOT a tighter precision-machining time.
4. Document this in the `Source / Logic` column.

---

## Rule 4 — Regional Rate Lookup (not global averages)

**The problem:** Using Western European premium rates for a supplier in a lower-cost region systematically overestimates conversion costs.

**Mandatory: always look up rates from the regional rate table below, not global averages.**

### Operator rates (fully loaded, €/h, 2025–2026)

| Region | Low | Base | High | Source |
|---|---|---|---|---|
| DE / AT / CH | 45 | 58 | 75 | Eurostat lc_lci_lev 2024 + 2026 escalation |
| FR / Benelux | 38 | 50 | 65 | Eurostat 2024 |
| IT / ES / PT | 25 | 34 | 46 | Eurostat 2024 |
| PL / CZ / SK | 14 | 20 | 28 | Eurostat 2024 + IGM equivalent |
| RO / BG / BA | 9 | 14 | 20 | Eurostat 2024 |
| TR | 7 | 11 | 17 | TÜİK 2024 |
| CN coastal (SH/GD) | 8 | 12 | 18 | NBS China 2023 + 2026 escalation |
| CN interior | 6 | 9 | 13 | NBS China 2023 |
| MX | 6 | 9 | 14 | INEGI 2023 |
| IN | 3 | 6 | 10 | ILO 2023 |

### Machine rates — laser cutting (€/h, machine-only, 2025)

| Machine class | DE | IT/ES | PL/CZ | CN |
|---|---|---|---|---|
| Fiber laser 2–4 kW (≤1.5m bed) | 65–90 | 50–70 | 40–60 | 25–40 |
| Fiber laser 4–8 kW (≥2m bed) | 85–120 | 65–90 | 55–80 | 35–55 |
| Tube laser | 90–130 | 70–100 | 60–85 | 40–60 |

### Machine rates — press brake (€/h, machine-only, 2025)

| Class | DE | IT/ES | PL/CZ | CN |
|---|---|---|---|---|
| CNC press brake 80–160t | 45–70 | 35–55 | 28–45 | 18–30 |
| CNC press brake 160–320t | 60–90 | 48–70 | 38–60 | 25–40 |

### Machine rates — TIG welding cell (€/h, 2025)

| Type | DE | IT/ES | PL/CZ | CN |
|---|---|---|---|---|
| Manual TIG (single operator) | 80–120 | 60–90 | 45–70 | 25–45 |
| Semi-auto TIG | 90–130 | 70–100 | 55–80 | 30–50 |
| Robotic TIG | 100–150 | 80–120 | 65–95 | 40–65 |

**Rule:** When the supplier location is known, always use the regional rate. Add ±10% for wage inflation if 2025 data is uncertain. Document the source in column H.

**Rate for Sedlbauer AG (Grafenau, DE):** Use DE rates. Sedlbauer is a DE SME with certified welders — manual TIG cell base €100–115/h is appropriate. Do NOT use global-average rates of €50–70/h.

---

## Rule 5 — Multi-Tasking / Mill-Turn / Multi-Op Logic

**The problem:** Sequential single-operation routing (laser → brake → weld) overcounts total elapsed time and may add phantom setups.

**Logic rules for welded subassemblies:**

1. **Laser cutting of all child parts is a SINGLE setup** (all programs loaded in one batch), NOT one setup per part. Setup time = program-load time + first-article check, amortised over the full kit quantity per lot.

2. **Press brake bending:** If the assembly has parts requiring different tooling (V-dies, radius tooling), count ONE setup for the batch, not one per part. Estimate number of distinct tooling changes from drawing.

3. **Welding:** If a welding cell has a fixture/rotary table (common for pharmaceutical assemblies), tack-and-full-weld is ONE setup per lot, NOT one per seam.

4. **Surface treatment (external):** This is a single job-lot operation. Freight to/from treatment supplier is included in the surface treatment rate or as a separate logistics sub-line — NOT doubled up with the main freight parameter.

5. **If total machining cycle time > 60 min/unit at a single station:** Consider whether a multi-op machine (e.g. 5-axis mill with pallet changer) would combine ops. For welded subassemblies this is less relevant but apply to any turned/milled sub-components.

**Cycle time sanity check (run for every model):**
- Manual TIG weld speed: ~100–200 mm/min for pharma-quality root + cap pass on stainless.
- Total weld length for a typical biotech bagholder-class assembly (5–30L): 500–2000 mm.
- Implied welding time: **5–20 min for weld-only**; add tack + fixture + inspect: total **1.5–4.0 h/asm** for a well-tooled cell.
- If derived welding time is > 8h/asm, challenge the weld-length assumption or check whether a robotic cell is feasible.

---

## Rule 6 — Scrap Credit Calculation (supplement to Rule 1)

For stainless and aluminium sheet-metal assemblies, scrap metal has significant recovery value.

**Formula:**
```
Scrap weight (kg) = Gross weight − Net weight
Scrap credit (€)  = Scrap weight × Material price × Scrap recovery rate
Net material cost  = (Gross weight × Material price) − Scrap credit
```

**Scrap recovery rates by metal (2025):**

| Material | Recovery rate (% of buy price) |
|---|---|
| Stainless 1.4301 / 304 | 15–25% |
| Stainless 1.4404 / 316L | 20–30% |
| Aluminum 5xxx / 6xxx | 25–35% |
| Carbon steel | 10–18% |
| Copper / brass | 35–50% |

**Include this as a separate input row** (`Scrap recovery rate, %`) in the Material bucket. Label it clearly in col C. Default to 20% for stainless unless supplier data is available.

---

## Diagnostic Checklist (run before finalising any model)

Before presenting results, verify ALL of the following:

- [ ] **Nesting yield** is explicitly modelled as a separate parameter (not assumed as 100%)
- [ ] **Scrap credit** is subtracted from material cost
- [ ] **Setup cost formula** uses lot count/yr in numerator and lot size in denominator — NOT annual volume
- [ ] **Lot size** is sourced from HAGER PPE order history, not assumed
- [ ] **Cycle time** has been broken into feature categories — critical vs. non-critical features separated
- [ ] **Machine and operator rates** match the supplier's actual region (from regional rate table above)
- [ ] **Weld time** passes the sanity check (see Rule 5) — total weld length ÷ weld speed
- [ ] **Surface treatment** is not double-counted in both Conversion and P&L
- [ ] **Each input in column H** has a cited source with vintage (e.g. "Eurostat lc_lci_lev 2024 DE")
- [ ] **Low-confidence parameters** are flagged "To be validated" in column H
- [ ] **Sensitivity top drivers** (welding time, material price, setup) are identified and listed
