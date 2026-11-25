# Industry-Typical Benchmarks

Reference ranges for common Should-Cost inputs. Use as starting points; always document source AND vintage. Adjust based on specific industry, region, and supplier evidence.

## How to use this file

Every benchmark block carries five metadata fields:

- **Vintage** — year(s) the figures represent
- **Source** — origin of the data (BLS, Eurostat, BCG project repository, industry estimate, etc.)
- **Region scope** — geographic validity
- **Industry scope** — sector validity
- **Confidence** — high (multiple independent sources, recent) / medium (single credible source or moderately old) / low (estimate or pre-2022)

**Rule for use in Should-Cost models:**
- Cite source AND vintage in column H of the Inputs tab (e.g. "Eurostat 2024 — wage CZ manufacturing")
- If vintage is > 24 months and the parameter is sensitive to time (labor, energy, commodities) → apply a documented escalation OR flag as "to be refreshed"
- If a benchmark has confidence = low → mark "To be validated" in column H
- Never present a low-confidence benchmark as authoritative

## Disclaimer

These ranges are starting heuristics drawn from typical industry benchmarks and BCG project experience. They are not validated industry studies. Always:
- Cross-check with supplier RFQ data when available
- Prefer official statistical sources (BLS, Eurostat, OECD), industry indices, or trade-association studies over these defaults
- Update region-specific labor and energy figures with current data — they change year-on-year

---

## OEE (Overall Equipment Effectiveness)

- **Vintage**: 2022–2024 industry estimates
- **Source**: BCG project repository (Industrial Goods practice) + manufacturing-engineering rules of thumb
- **Region scope**: Global (Western manufacturing standards)
- **Industry scope**: Discrete manufacturing
- **Confidence**: medium — direction reliable, exact band depends on plant maturity

| Process | Low | Base | High |
|---|---|---|---|
| Thermoforming | 65% | 75% | 85% |
| Injection moulding (high-volume) | 70% | 80% | 90% |
| Injection moulding (low-volume) | 55% | 65% | 75% |
| CNC machining | 50% | 65% | 80% |
| Stamping (high-volume) | 75% | 85% | 92% |
| Die casting | 65% | 75% | 85% |
| SMT line | 70% | 80% | 90% |
| TIG/MIG welding cell (manual or robotic) | 50% | 65% | 78% |

---

## Scrap / Yield

- **Vintage**: 2022–2024 industry estimates
- **Source**: BCG cost-engineering practice + supplier RFQ patterns
- **Region scope**: Global
- **Industry scope**: Discrete manufacturing
- **Confidence**: medium

| Process | Scrap (Low/Base/High) | Note |
|---|---|---|
| Thermoforming | 30% / 40% / 50% | Skeleton + offcut, regrind recovery 50–90% |
| Injection moulding | 1% / 3% / 5% | Runner regrind recovery 80–100% (cold runner) |
| Hot-runner injection moulding | 0.5% / 1% / 2% | Minimal sprue waste |
| CNC machining | 2% / 5% / 10% | Setup parts + rework |
| Stamping (material utilization) | 50% / 65% / 80% | Blanking yield — material lost is critical |
| Die casting | 3% / 5% / 10% | Sprue/gate, porosity rejects |
| SMT first-pass yield | 95% / 98% / 99.5% | |
| Laser cutting (sheet metal) | 55% / 70% / 85% | Nesting-dependent |

---

## SG&A on COGS (supplier overhead)

- **Vintage**: 2022–2024 estimates from supplier financial filings (DACH/EU mid-size manufacturers) + industry reports
- **Source**: BCG benchmarking database, Bundesanzeiger filings, S&P CapIQ
- **Region scope**: Western Europe (DE/FR/IT primarily), US directional
- **Industry scope**: Per row
- **Confidence**: medium

| Industry | Low | Base | High |
|---|---|---|---|
| Commodity plastics (high-volume) | 5% | 8% | 11% |
| Medical / pharma plastics | 8% | 10% | 13% |
| Precision machining | 10% | 13% | 17% |
| Electronics EMS | 5% | 8% | 12% |
| Stamping / sheet metal | 7% | 10% | 13% |
| Welded subassemblies (DACH SME) | 9% | 12% | 15% |
| Specialty / low-volume | 12% | 17% | 22% |

---

## Supplier margin on COGS+SG&A

- **Vintage**: 2022–2024 industry estimates
- **Source**: BCG benchmarking, public-company filings, supplier negotiations
- **Region scope**: Western markets (DE, FR, IT, US)
- **Industry scope**: Per row
- **Confidence**: medium — margins vary widely by supplier strategy

| Industry | Low | Base | High |
|---|---|---|---|
| Commodity plastics | 5% | 8% | 12% |
| Medical / pharma plastics | 8% | 12% | 18% |
| Precision machining | 10% | 15% | 22% |
| Electronics EMS | 4% | 7% | 12% |
| Welded subassemblies (DACH SME) | 8% | 13% | 20% |
| Specialty / sole-source | 15% | 20% | 30% |

---

## Tool useful life

- **Vintage**: Long-stable industry conventions
- **Source**: Tooling supplier standards (Husky, Milacron, Schuler, etc.) + BCG manufacturing engineering experience
- **Region scope**: Global
- **Industry scope**: Tool-dependent processes
- **Confidence**: high — well-established

| Process | Typical |
|---|---|
| Thermoforming (aluminum tool) | 3–7 years |
| Injection moulding (steel hardened) | 500k–1M+ cycles (~5–10 years) |
| Stamping die (high-volume) | 1–5M strokes |
| Die casting | 50k–150k shots |
| Laser cutting (no tool) | n/a |
| Welding fixtures | 5–10 years (refurb interval 2–3 years) |

---

## Manufacturing wage benchmarks (fully loaded €/h)

- **Vintage**: 2024 base figures, escalation 3–5% p.a. for 2026 use
- **Source**: Eurostat Labor Cost Survey 2024, BLS US 2024, ILO 2023 for emerging markets
- **Region scope**: Per row
- **Industry scope**: Manufacturing operator (excl. R&D, engineering)
- **Confidence**: medium for EU/US (statistical sources), low for emerging markets (older or estimate)

**Important**: Always escalate 3–5% p.a. for current-year use OR cite a more recent source. The figures below are 2024 base.

| Region | Operator (low/base/high) € 2024 base |
|---|---|
| US (manufacturing avg) | 25 / 35 / 45 |
| US (medical / healthcare states like MA, MN, CT) | 30 / 38 / 48 |
| Western Europe (DE, FR) | 35 / 45 / 60 |
| Western Europe (IT, ES) | 25 / 32 / 42 |
| Eastern Europe (PL, CZ, RO) | 12 / 18 / 25 |
| North Africa (Tunisia, Morocco) | 4 / 6 / 10 |
| China (coastal — Shanghai, Guangdong) | 6 / 9 / 14 |
| China (interior) | 4 / 6 / 9 |
| Mexico | 5 / 8 / 12 |
| India | 3 / 5 / 8 |
| Vietnam | 3 / 5 / 8 |

For 2026 use: apply +6–10% over 2024 base (DE/FR cumulative inflation 2024–26), +4–8% (EM).

---

## Machine hourly rates (€/h)

- **Vintage**: 2024 industry estimates
- **Source**: BCG cost-engineering models + machine OEM list prices (depreciated)
- **Region scope**: Western Europe / US baseline
- **Industry scope**: Per row
- **Confidence**: medium — rate strongly depends on machine class, age, utilization

| Machine class | €/h (low/base/high) |
|---|---|
| Small thermoformer / IM (<200t) | 50 / 75 / 110 |
| Mid-size IM (200–500t) | 70 / 100 / 140 |
| Large IM (500t+) | 100 / 140 / 200 |
| Healthcare cleanroom thermoforming | 90 / 120 / 160 |
| 3-axis CNC mill | 60 / 90 / 130 |
| 5-axis CNC mill | 100 / 140 / 200 |
| SMT line (mid-volume) | 80 / 110 / 150 |
| Laser cutting (2D fiber, 4–6 kW) | 70 / 100 / 140 |
| Press brake (CNC, 100–200t) | 50 / 75 / 110 |
| Stamping press (200–500t) | 80 / 110 / 150 |
| TIG welding manual cell | 35 / 50 / 70 |
| Robotic welding cell | 70 / 100 / 140 |

For Eastern Europe / Mexico: multiply by 0.6–0.8. For China coastal: 0.5–0.7. For India / SE Asia: 0.4–0.6.

---

## Cleanroom / GMP premium

- **Vintage**: Long-stable rule of thumb
- **Source**: BCG medical/pharma practice
- **Region scope**: Global
- **Industry scope**: Medical, pharma, food, biotech
- **Confidence**: medium

Premium on Material+Conversion when produced in qualified environment:
- ISO 7 / ISO 8 cleanroom: **10–30%** typical
- "Controlled environment" (less stringent): **5–15%**
- Validation overhead (one-off): often booked separately as NRE — confirm with supplier

Toggle on/off depending on actual requirement (drawing spec / Cosmetic Spec vs. nice-to-have).

---

## Energy (industrial electricity, €/kWh)

- **Vintage**: 2025 actuals, 2026 forward estimates
- **Source**: Eurostat industrial electricity prices H2 2024, EIA US, IEA forecast 2025–2026
- **Region scope**: Per row
- **Industry scope**: Industrial tariff
- **Confidence**: high for 2024 actuals, medium for 2026 forecast (volatile post-2022)

| Region | €/kWh industrial (2025 estimate) |
|---|---|
| US | 0.07 – 0.10 |
| DE | 0.15 – 0.22 (post-2024 normalisation) |
| FR | 0.10 – 0.14 |
| IT | 0.18 – 0.25 |
| Eastern EU (PL, CZ) | 0.12 – 0.18 |
| China | 0.07 – 0.10 |
| India | 0.08 – 0.12 |

Machine-hour energy cost depends on power rating × load factor × electricity price. Indicative:
- Small machine (<30 kW): €3–6/h (DE), €1.5–3/h (CN)
- Mid (30–80 kW): €6–14/h (DE), €3–6/h (CN)
- Large (80+ kW): €14–25/h (DE), €6–12/h (CN)

---

## Material price references (€/kg, typical commercial grades)

- **Vintage**: 2024–2025 indicative
- **Source**: Plastics Information Europe (PIE), Eastman/Sabic published lists, LME for metals, BCG project data
- **Region scope**: EU base, US similar ±10%
- **Industry scope**: Standard commercial purchase, not engineered grade
- **Confidence**: medium — commodity prices volatile

| Material | €/kg (low/base/high, 2024–25) |
|---|---|
| PP (homopolymer, commodity) | 1.10 / 1.40 / 1.75 |
| PE-HD | 1.20 / 1.50 / 1.85 |
| ABS | 1.80 / 2.30 / 2.80 |
| PC (general purpose) | 3.00 / 3.80 / 4.80 |
| PA66 (unfilled) | 3.50 / 4.50 / 5.80 |
| PA66-GF30 | 4.20 / 5.30 / 6.50 |
| Tritan / co-polyester (medical grade) | 7.00 / 9.00 / 12.00 |
| Stainless 1.4301 / 304 (sheet, < 5 mm) | 3.20 / 4.00 / 5.20 |
| Stainless 1.4404 / 316L (sheet, < 5 mm) | 4.50 / 5.50 / 7.00 |
| Aluminum 6061 / 6082 (sheet) | 3.80 / 4.80 / 6.20 |
| Carbon steel S235 / S355 (sheet) | 0.80 / 1.10 / 1.60 |

For pharma/medical grades or small-quantity buys: apply +20–50% over commodity. Always confirm with supplier or material distributor for >100 k€ spend.

---

## Notes on usage

- Cross-check with actual supplier RFQ data when available — benchmarks are a starting point, not a substitute.
- For very specific industries (semiconductors, aerospace, defense), these defaults likely underestimate complexity — flag as "to be refined" and seek industry-specific sources.
- Region-specific labor figures must be updated with current data — wages change year-on-year, especially in Eastern Europe and emerging markets.
- Energy prices in DE/EU remain volatile post-2022 — refresh quarterly if Material+Conversion energy is >5% of Should Cost.
- This file should be refreshed **annually** at minimum. Last refresh date: 2026-05.
