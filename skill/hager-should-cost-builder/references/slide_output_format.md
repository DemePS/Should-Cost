# Slide Output Format Specification — Graphics Handover Excel

**Reference file:** `1000126756_SlideValues.xlsx`
**Every new SlideValues build must match this reference exactly — cell by cell.**

---

## File naming

`{Material-ID}_SlideValues.xlsx`

---

## Tab structure — 4 tabs, exactly in this order

| Tab index | Tab name |
|---|---|
| 1 | `Slide 1 - Cover` |
| 2 | `Slide 2 - Cost Build` |
| 3 | `Slide 3 - Inputs` |
| 4 | `Slide 5 - Sensitivity` |

**Note:** The third tab is named `Slide 3 - Inputs` (NOT `Slide 4 - Inputs`). No Instructions tab.

---

## Universal formatting constants

| Element | Value |
|---|---|
| Font (all cells) | Arial |
| Tab title (A1) | size 14, bold, color `00003755` (dark navy), fill `00000000` |
| Column header row | fill `00003755`, font white `00FFFFFF`, bold, size 11 |
| Section header rows | fill `00D9E1F2` (light blue), font `00003755`, bold, size 11 — **merged across all columns of that tab** |
| Data rows — col A (slide ref) | size 10, not bold, fill `00000000` |
| Data rows — col B (element label) | size 10, not bold, fill `00000000` |
| Data rows — col C (value) | size 10, **bold**, fill `00000000` |
| Numeric cost values | numfmt `#,##0.00` |
| All other values | numfmt `General` |

---

## Tab 1: `Slide 1 - Cover`

**Columns used: A, B, C only. No columns D–F.**

**Column widths:** A=10, B=38, C=38

| Row | Col | Value | Formatting |
|---|---|---|---|
| 1 | A | `Slide 1 — Cover` | bold, sz=14, color=`00003755`, fill=`00000000` |
| 2 | — | *(blank)* | — |
| 3 | A | `Slide` | header row: fill=`00003755`, white, bold, sz=11 |
| 3 | B | `PPT element` | same |
| 3 | C | `Value` | same |
| 4 | A | `Slide 1` | not bold, sz=10 |
| 4 | B | `Title — Material name` | not bold, sz=10 |
| 4 | C | `{MATERIAL NAME IN CAPS}` | **bold**, sz=10 |
| 5 | A | `Slide 1` | not bold, sz=10 |
| 5 | B | `Subtitle — Date` | not bold, sz=10 |
| 5 | C | `{Month YYYY}` e.g. `May 2026` | **bold**, sz=10 |
| 6 | A | `Slide 1` | not bold, sz=10 |
| 6 | B | `Material ID` | not bold, sz=10 |
| 6 | C | `{Material-ID}` | **bold**, sz=10 |

---

## Tab 2: `Slide 2 - Cost Build`

**Columns used: A, B, C only. No columns D–F.**

**Column widths:** A=10, B=38, C=28

**Merged cells:** A14:C14 (waterfall section header), A27:C27 (key results section header)
**Blank rows:** row 13 (gap between info bar and waterfall), rows 24–26 (gap between waterfall end and key results)

### Row-by-row layout

| Row | Col A | Col B | Col C | Notes |
|---|---|---|---|---|
| 1 | `Slide 2 — Cost Build` | — | — | bold, sz=14, color=`00003755` |
| 2 | *(blank)* | | | |
| 3 | `Slide` | `PPT element` | `Value` | header: fill=`00003755`, white, bold, sz=11 |
| 4 | `Slide 2` | `Material name` | `{title case name}` | C bold |
| 5 | `Slide 2` | `Material number` | `{Material-ID}` | C bold |
| 6 | `Slide 2` | `Category` | `{top-level category}` | C bold |
| 7 | `Slide 2` | `Sub-category` | `{sub-category, no code}` | C bold |
| 8 | `Slide 2` | `Quantity p.a.` | `{integer}` | C bold |
| 9 | `Slide 2` | `Spend` | `€{X}k` or `€{X.X}M` | C bold, text string |
| 10 | `Slide 2` | `Avg price per unit` | `{price}` | C bold, numfmt `#,##0.00` |
| 11 | `Slide 2` | `Incumbent supplier` | `{name only}` | C bold |
| 12 | `Slide 2` | `Supplier location` | `{City, Country}` | C bold |
| 13 | *(blank)* | | | |
| 14 | `Cost Build Waterfall [€/unit]` | *(merged A14:C14)* | | fill=`00D9E1F2`, bold, sz=11, color=`00003755` |
| 15 | `Slide 2` | `Material` | `{value}` | C bold, numfmt `#,##0.00` |
| 16 | `Slide 2` | `Conversion` | `{value}` | C bold, numfmt `#,##0.00` |
| 17 | `Slide 2` | `Manufacturing Costs (subtotal)` | `{value}` | C bold, numfmt `#,##0.00` |
| 18 | `Slide 2` | `Packaging & Logistics` | `{value}` | C bold, numfmt `#,##0.00` |
| 19 | `Slide 2` | `Overheads (incl. SG&A)` | `{value}` | C bold, numfmt `#,##0.00` |
| 20 | `Slide 2` | `Margin` | `{value}` | C bold, numfmt `#,##0.00` |
| 21 | `Slide 2` | `Should Cost (subtotal)` | `{value}` | C bold, numfmt `#,##0.00` |
| 22 | `Slide 2` | `Impact Potential` | `{value}` | C bold, numfmt `#,##0.00` |
| 23 | `Slide 2` | `Current Price` | `{value}` | C bold, numfmt `#,##0.00` |
| 24 | *(blank)* | | | |
| 25 | *(blank)* | | | |
| 26 | *(blank)* | | | |
| 27 | `Key Result Tiles` | *(merged A27:C27)* | | fill=`00D9E1F2`, bold, sz=11, color=`00003755` |
| 28 | `Slide 2` | `Current Price tile` | `{price}` | C bold, numfmt `#,##0.00` |
| 29 | `Slide 2` | `Benchmark Price tile` | `{should cost}` | C bold, numfmt `#,##0.00` |
| 30 | `Slide 2` | `Impact potential tile` | `€{X}k p.a. ({X.X}%)` | C bold, text string |

**Waterfall rows 15–23 — exact 9-row sequence, no COGS subtotal:**
```
15  Material
16  Conversion
17  Manufacturing Costs (subtotal)     ← = row 15 + row 16
18  Packaging & Logistics
19  Overheads (incl. SG&A)
20  Margin
21  Should Cost (subtotal)             ← = rows 17+18+19+20
22  Impact Potential                   ← = row 23 − row 21
23  Current Price                      ← from HAGER PPE
```

**Impact tile format:** `€{round(Vol × Impact / 1000)}k p.a. ({Impact/CurrentPrice×100 to 1dp}%)`
Example: `€18k p.a. (19.2%)`

**Spend format:** < €1M → `€{round(spend/1000)}k`; ≥ €1M → `€{spend/1e6 to 1dp}M`

---

## Tab 3: `Slide 3 - Inputs`

**Tab name is `Slide 3 - Inputs`** (matches the slide numbering in the PPT deck).

**Columns used: A–H. No column I.**

**Column widths:** A=10, B=8, C=50, D=12, E=10, F=10, G=10, H=20

**Merged cells:** bucket separator rows are merged across A:H (full row width)

### Header rows

| Row | Layout |
|---|---|
| 1 | A1=`Slide 3 — Inputs`, bold, sz=14, color=`00003755`, fill=`00000000` |
| 2 | *(blank)* |
| 3 | Headers: A=`Slide`, B=`Row#`, C=`Parameter`, D=`Unit`, E=`Low`, F=`Base`, G=`High`, H=`Bucket` — fill=`00003755`, white, bold, sz=11 |

### Bucket separator rows (merged A:H, fill `00D9E1F2`, bold, sz=11, color `00003755`)

Exactly these 6 labels, in this order:
1. `MATERIAL`
2. `CONVERSION`
3. `PACKAGING & LOGISTICS`
4. `OVERHEADS (INCL. SG&A)`
5. `MARGIN`
6. `REFERENCE DATA (FIXED)`

### Parameter rows

| Column | Content | Bold? | numfmt |
|---|---|---|---|
| A | `Slide 3` | No | General |
| B | sequential row number (1, 2, 3…) | No | General |
| C | parameter display name (≤50 chars) | No | General |
| D | unit | No | General |
| E | Low value | No | General |
| F | Base value | **Yes** | General |
| G | High value | No | General |
| H | bucket label (see below) | No | General |

**Bucket label values for col H:**
- Material params → `Material`
- Conversion params → `Conversion`
- Packaging & Logistics params → `Packaging & Logistics`
- Overheads params → `Overheads`
- Margin param → `Margin`
- Reference params → `Reference`

### Bucket content and source requirements

**MATERIAL**
Parameters: material price (€/kg or €/unit), sheet/part weight (kg or g), yield/nesting/scrap (%), purchased components (fasteners — consolidate multiples into one row).
Sources: LME spot prices, Fastmarkets, steel-index.com, material distributors (Klöckner, Service Center), supplier quotations.

**CONVERSION**
Parameters: machine/process rates (€/h), process times (min or h per unit/assembly), operator rate (€/h, fully loaded), lot size and setup (h/lot, €/h), surface treatment (€/unit — external supplier rate), energy (€/kWh and kWh/unit as sub-detail in H column as `Conversion — energy`), OEE (%).
The H column shows the top-level bucket (`Conversion`) for all conversion params. For sub-detail traceability, you may use `Conversion — machine`, `Conversion — labor`, `Conversion — energy`, `Conversion — setup`, `Conversion — surface treatment` as H values.
Sources: Eurostat lc_lci_lev (labor costs by country, current year), VDW / Maschinenmarkt machine investment databases, supplier-provided rates, Transporeon/Upply for benchmarking, BCG manufacturing databases.

**PACKAGING & LOGISTICS**
Parameters: packaging cost per unit (€/unit — spec-designated materials), freight lane(s) (€/unit — per origin-destination pair), customs/import duties if applicable.
Sources: Transporeon/Upply current year, freight forwarder quotes, supplier-confirmed packaging cost.

**OVERHEADS (INCL. SG&A)**
Parameters: overhead + SG&A rate (% on manufacturing base — combined in 1–2 rows). May split into manufacturing overhead % and SG&A % if separately known.
Sources: benchmarks.md specialty/sole-source ranges, industry benchmark databases (KPMG, PwC manufacturing cost studies), BCG should-cost benchmarks.

**MARGIN**
Parameters: supplier margin % (single row — on manufacturing base + P&L + overheads).
Sources: benchmarks.md specialty ranges, BCG negotiation databases.

**REFERENCE DATA (FIXED)**
Parameters: Annual volume (units/yr), Current avg price (€/unit), Spec-Premium Risk Score (score 1–5), Lower-End Uplift % (tied to risk score).
Sources: HAGER PPE 2025.xlsx (volume and price — mark as FIXED), BCG risk scoring methodology.

### Parameter consolidation rules
- Multiple fastener rows → consolidate into ONE row: `Fasteners total ({types})` with summed Low/Base/High
- Display names max 50 characters
- Row# is sequential across all buckets (does not restart per bucket)

---

## Tab 4: `Slide 5 - Sensitivity`

**Column widths:** A=10, B=30, C=12, D=14, E=22

**Merged cells:** A3:E3 (tornado section header)

### Row-by-row layout

| Row | Layout |
|---|---|
| 1 | A1=`Slide 5 — Sensitivity`, bold, sz=14, color=`00003755`, fill=`00000000` |
| 2 | *(blank)* |
| 3 | A3=`Tornado — Top 5 sensitivity drivers (Base SC = {base_sc} €/unit)` — merged A3:E3, fill=`00D9E1F2`, bold, sz=11, color=`00003755` |
| 4 | Headers: A=`Slide`, B=`Driver`, C=`Scenario`, D=`Input value`, E=`Should Cost [€/unit]` — fill=`00003755`, white, bold, sz=11 |
| 5–19 | 5 drivers × 3 rows each (Low / Mid / High) |

### Data rows (rows 5–19)

| Col | Content | Bold? | numfmt |
|---|---|---|---|
| A | `Slide 5` | No | General |
| B | driver name — repeated for all 3 rows | No | General |
| C | `Low` / `Mid` / `High` | No | General |
| D | input value as string with unit (e.g. `4.5`, `90`, `10%`) | No | General |
| E | Should Cost result €/unit | **Yes** | `#,##0.00` |

**Mid row:** E = Base SC for all drivers.
**Ranking:** Top 5 drivers by impact range (High SC − Low SC) descending.
**No Key Insights section** in this tab. Key Insights go in chat blocks only.

---

## Verification checklist (run before delivering)

1. Material + Conversion + P&L + Overheads + Margin = Should Cost (±€0.01)
2. Should Cost + Impact Potential = Current Price (±€0.01)
3. Impact tile string matches Vol × Impact / 1000 and Impact / Current Price
4. Slide 3 tab name is `Slide 3 - Inputs` (not `Slide 4`)
5. Slide 3 has no column I
6. Slides 1 and 2 have only columns A, B, C (no D–F)
7. All section headers in Slide 3 are merged A:H
8. Sensitivity Mid rows all equal Base SC

---

## Version history

- **v3.8 (2026-05-29):** Fixed Slide 2 row positions to match reference exactly: blank row 13 between info bar and waterfall section header; blank rows 24–26 between last waterfall row and Key Result Tiles header; Key Result Tiles merged at A27:C27 (not A25:C25); tiles at rows 28–30.

- **v3.7 (2026-05-29):** Complete rewrite derived from cell-by-cell read of `1000126756_SlideValues.xlsx`. Changes: (1) third tab renamed `Slide 3 - Inputs`; (2) Slides 1 and 2 use only cols A–C; (3) waterfall updated to exact 9-row new structure: Material, Conversion, Manufacturing Costs (subtotal), Packaging & Logistics, Overheads (incl. SG&A), Margin, Should Cost (subtotal), Impact Potential, Current Price — no COGS subtotal; (4) Slide 3 col I removed; (5) Slide 3 bucket separators updated to new names including `OVERHEADS (INCL. SG&A)` and `PACKAGING & LOGISTICS`; (6) H column bucket labels `Overheads` and `Packaging & Logistics`; (7) sub-detail traceability in H column for Conversion sub-components; (8) source requirements added per bucket; (9) merged cell ranges documented precisely; (10) column widths documented from reference.
