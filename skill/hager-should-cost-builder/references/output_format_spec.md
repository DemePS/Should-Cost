# Output Format Specification — Calculation Model

**Reference file:** `Should_Cost_1000126756.xlsx` (structure) with new bucket schema.

This spec defines the exact structure, tab layout, formulas, formatting, and column widths for the calculated Excel model.

---

## File naming

`Should_Cost_{Material-ID}_{SupplierShortName}_{YYYYMMDD}_v{NN}.xlsx`

---

## Tab structure (4 tabs)

| Tab | Name | Purpose |
|---|---|---|
| 1 | `0. Introduction` | Static purpose/contents page |
| 2 | `1. Overview & Results` | General info + Cost Build summary + Key Results |
| 3 | `2. Inputs` | All parameters, Low/Base/High, sources |
| 4 | `3. Calculation` | Step-by-step formulas |

---

## Fixed cost bucket structure (DO NOT change)

The waterfall has **6 input buckets** plus 3 derived lines:

| # | Bucket | Code prefix | Notes |
|---|---|---|---|
| 1 | **Material** | M | Raw material cost |
| 2 | **Conversion** | C | All direct manufacturing operations |
| — | **Manufacturing Costs** | — | Subtotal = Material + Conversion |
| 3 | **Packaging & Logistics** | P | Packaging materials + all freight/logistics |
| 4 | **Overheads** | O | SG&A + manufacturing overheads combined |
| 5 | **Margin** | S | Supplier margin on (Manuf. Costs + P&L + Overheads) |
| — | **Should Cost** | — | = Manufacturing Costs + P&L + Overheads + Margin |
| — | **Impact Potential** | — | = Current Price − Should Cost |
| — | **Current Price** | — | From HAGER PPE 2025.xlsx |

**Critical: The 5 input buckets are: Material, Conversion, Packaging & Logistics, Overheads, Margin. There is NO COGS subtotal and NO separate Quality & Packaging, Logistics, or SG&A bucket.**

---

## Tab 1: `0. Introduction`

Content in column B from B2. Bold headings: Purpose, Output format, Contents, How to use this file.

Update B8 to read:
`-Cost build in five buckets: Material, Conversion, Packaging & Logistics, Overheads, Margin`

---

## Tab 2: `1. Overview & Results`

**Dimensions:** columns B–G, starting row 2.

### Title (row 2)
B2: `Should- Cost Analysis - {material name}` — bold, no fill

### General Information (rows 4–11)
B4: `General Information` — bold, no fill
Rows 5–11: label col B (bold, fill `00000000`), value col C (not bold, fill `00000000`)
- B5/C5: Material ID
- B6/C6: Material name
- B7/C7: Plant / Purchasing entity
- B8/C8: Incumbent supplier
- B9/C9: Category
- B10/C10: Process
- B11/C11: BOM size / notes

### Cost Build (rows 13–26)
B13: `Cost Build [€/unit, estimated values]` — bold, no fill
B15/C15: `Cost Element` / `Value [€/unit]` — both bold, fill `00000000`

**Cost build rows — new bucket structure:**

| Row | Col B label | Bold? | Fill | Col C formula |
|---|---|---|---|---|
| 16 | `Material` | No | `00000000` | `='3. Calculation'!E{Σ_Material_row}` |
| 17 | `Conversion` | No | `00000000` | `='3. Calculation'!E{Σ_Conversion_row}` |
| 18 | `Manufacturing Costs` | **Yes** | none | `=C16+C17` |
| 19 | `Packaging & Logistics` | No | `00000000` | `='3. Calculation'!E{Σ_PL_row}` |
| 20 | `Overheads` | No | `00000000` | `='3. Calculation'!E{Σ_OH_row}` |
| 21 | `Margin` | No | `00000000` | `='3. Calculation'!E{S1_row}` |
| 22 | `Should Cost` | **Yes** | none | `='3. Calculation'!E{SHOULD_COST_row}` |
| 23 | `Impact Potential` | **Yes** | `00000000` | `={current_price}-C22` |
| 24 | `Current Price` | **Yes** | `00000000` | hardcoded value from HAGER PPE |

**Number format for all cost values:**
`_-* #,##0.00\ "€"_-;\-* #,##0.00\ "€"_-;_-* "-"??\ "€"_-;_-@_-`

Note: no COGS subtotal row. The sequence goes: Manufacturing Costs (subtotal) → Packaging & Logistics → Overheads → Margin → Should Cost.

### Key Results (rows 26–33, adjust row numbers to follow cost build)
B{n}: `Key Results` — bold, no fill
Rows below:
- `Current price (weighted avg)` / hardcoded
- `Should-Cost (calculated)` / `='3. Calculation'!E{SHOULD_COST_row}`
- `Impact potential per unit` / `='3. Calculation'!E{impact_row}`
- `Impact %` / `='3. Calculation'!E{impact_pct_row}` / numfmt `0.0%`
- `Annual volume (units)` / hardcoded
- `Annual impact potential (€)` / `=C{vol_row}*C{impact_unit_row}` — bold label

---

## Tab 3: `2. Inputs`

**Header row:** `#` | `Parameter` | `Unit` | `Low` | `Base` | `High` | `Source / Logic` — all bold, no fill

**Bucket header rows** (col C only, bold, no fill):
- `Material`
- `Conversion`
- `Packaging & Logistics`
- `Overheads`
- `Margin`
- `Reference Data (fixed)`

**Parameter rows formatting:**
- Col B: row number — bold, fill `00000000`
- Col C: parameter name — not bold, fill `00000000`
- Col D: unit — not bold, fill `00000000`
- Col E/F/G: Low/Base/High — not bold, **no fill**, numfmt `#,##0.00;[Red]\(#,##0.00\);\–`
- Col H: source — not bold, fill `00000000`

**Bucket content — what goes where:**

| Bucket header | Parameters included |
|---|---|
| **Material** | Raw material price, weight, yield/utilization, purchased components (fasteners, bought parts) |
| **Conversion** | All direct manufacturing operations: machine rates, times, setup, tooling amort., direct labor, surface treatment, marking, OEE |
| **Packaging & Logistics** | Packaging materials, freight (all legs), customs, import duties |
| **Overheads** | SG&A % on manufacturing base, manufacturing overhead %, any facility/admin overhead — expressed as % of (Manufacturing Costs + P&L) or as fixed €/unit |
| **Margin** | Supplier margin % on (Manufacturing Costs + P&L + Overheads) |
| **Reference Data (fixed)** | Annual Volume, Annual Spend, Current Avg Price, Lot count, Avg lot size, Risk Score, Uplift % |



---

## Tab 4: `3. Calculation`

**Header row:** `#` | `Cost element` | `Units` | `Value` — bold, no fill

**Bucket section headers in col B** (bold, no fill, two leading spaces):
- `  1. Material`
- `  2. Conversion`
- `  3. Packaging & Logistics`
- `  4. Overheads`

**Calculation rows** (col B code, bold, fill `00000000`; col C–E, fill `00000000`):

**Material (M rows):**
- M1: Gross material weight = `='2. Inputs'!F{weight} / ('2. Inputs'!F{yield}/100)`
- M2: Material cost = `=E{M1} * '2. Inputs'!F{price}`
- M3+ : Purchased components / fasteners (one row per line item) = `='2. Inputs'!F{row}` or sum
- Σ Material: `=SUM(E{M2}:E{M_last})`

**Conversion (C rows):** process-dependent, adapt per material:
- Laser, bending, welding, machining, stamping, surface treatment, marking, setup, QC, etc.
- Σ Conversion: `=SUM(E{C1}:E{C_last})`

**Manufacturing Costs subtotal** (col B bold, no fill):
`=E{Σ_Material} + E{Σ_Conversion}`

**Packaging & Logistics (P rows):**
- P1: Packaging materials = `='2. Inputs'!F{row}`
- P2: Freight (primary lane) = `='2. Inputs'!F{row}`
- P3: Additional freight legs / customs / duties (if applicable) = `='2. Inputs'!F{row}`
- (add/remove P rows as needed for the material)
- Σ Packaging & Logistics: `=SUM(E{P1}:E{P_last})`

**Overheads (O rows):**
- O1: SG&A = `=(E{ManufCosts} + E{Σ_PL}) * '2. Inputs'!F{sga_pct_row}/100`
- O2: Manufacturing overhead (if separately modelled) = formula or `='2. Inputs'!F{row}`
- Σ Overheads: `=SUM(E{O1}:E{O_last})`
  *(If overheads are a single combined % parameter, only O1 row needed)*

**Margin (S row):**
- S1: Margin = `=(E{ManufCosts} + E{Σ_PL} + E{Σ_OH}) * '2. Inputs'!F{margin_pct_row}/100`

**SHOULD COST** (col B bold, no fill):
`= E{ManufCosts} + E{Σ_PL} + E{Σ_OH} + E{S1}`

**Final lines** (col C bold, fill `00000000`):
- `Σ CURRENT PRICE`: `='2. Inputs'!F{current_price_row}`
- `Impact Potential`: `=E{CURRENT_PRICE} - E{SHOULD_COST}`
- `Impact %`: `=E{impact} / E{CURRENT_PRICE}` — numfmt `0.0%`
- `Annual saving potential`: `='2. Inputs'!F{volume_row} * E{impact}`

---

## Formatting summary

**Font:** Arial. Size 10 data, 11 headers.
**Color coding:** Blue `0000FF` = hardcoded inputs; Black `000000` = formulas; Green `008000` = cross-sheet links.
**Bold:** section headers, row numbers (Inputs col B), subtotal labels+values.
**Fill:** `none` = subtotal/section rows; `00000000` = regular data rows.
**Number formats:** cost `_-* #,##0.00 "€"...`; inputs `#,##0.00;[Red]\(#,##0.00\);\–`; % `0.0%`.
