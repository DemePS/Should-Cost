<!--
Shared, verbatim hard-rule block. Prepended by model_client.py to every structured call
and to the research agent's instructions (should_cost/tools/model_client.py,
should_cost/tools/research_agent.py). Do not paraphrase anything below — SKILL.md and
costing_accuracy_rules.md are the source of truth; these blocks are copied, not summarized.
-->

## Pitfall P1 — Factor cost benchmarks must be region- and context-specific (never inherit WEU defaults for non-WEU suppliers)

**The problem:** `references/benchmarks.md` contains Western European benchmarks as its default baseline (VDMA machine rates, Eurostat DE/FR wages, ZVO plating costs, etc.). When a supplier operates in Vietnam, China, India, or another low-cost region, applying WEU benchmarks overstates the should-cost by 3–10× on labor, machine, and surface treatment costs, and can triple-count conversion cost by embedding labor and energy inside a composite machine rate and then adding them again as separate line items.

**The structural double-count trap — Machine Rate within Conversion:** The benchmarks.md machine hourly rate (e.g. €22–42/h for a cold header) is a **Western EU all-in conversion rate** that includes depreciation + maintenance + tooling + facility overhead + implicitly weighted labor + energy. In the Conversion bucket, labor and energy must be added separately to machine-only cost — never use an all-in machine rate that already embeds labor and energy, or they get counted twice within Conversion. In the current 5-bucket model, Conversion covers all direct manufacturing cost including labor and energy — these sub-components (machine, labor, energy) all roll up into Conversion — they are not separate output buckets. The machine rate used within Conversion calculations must still be machine-only (depreciation, maintenance, tooling, space), with labor and energy added separately inside the Conversion formula, so the total Conversion cost is correct without double-counting.

**Mandatory checks before setting any factor cost:**

| Parameter | What to check | How |
|---|---|---|
| Labor rate | Supplier country actual manufacturing wage, not WEU table | Baker McKenzie, ILO ILOSTAT, Eurostat (EU only), General Statistics Office for VN/CN/IN |
| Machine rate | Must be MACHINE-ONLY cost — no labor, no energy embedded | Derive from equipment capex ÷ (dep. years × annual hours) + maintenance + tooling + space |
| Energy price | Supplier country industrial tariff, not EU rate | GlobalPetrolPrices.com, national utility regulator sites, IEA for non-EU |
| Surface treatment | Region-specific rate — ZVO is EU-only; Asia integrated barrel plating is 3–5× cheaper | ZVO for EU outsourced; for Asia in-house barrel Zn use €0.80–2.00/m² not €2.50–8.00/m² |
| Freight | FBX11 current rate for Asia→Europe; road groupage for intra-EU; re-check for each build | Freightos FBX index (published weekly); Transporeon/Upply for EU road |
| Raw material | CHQ wire rod, carbon/stainless steel: use current index, not cached figure | IMARC, Chemanalyst, MEPS, Destatis; verify within 30 days of build date |

**Regional multipliers for machine rate (apply to WEU base for rough cross-check only — derive from capex where possible):**
- Vietnam / SE Asia: × 0.15–0.35 on machine-only cost (cheap capex, Chinese OEM equipment)
- China coastal: × 0.20–0.40
- Eastern Europe: × 0.55–0.75
- Germany / France: × 1.0 (WEU base)

**When to web-search for live data:** For every build, run at least one live search per time-sensitive parameter (wages, energy, freight, raw material). Do not rely solely on benchmarks.md figures older than the current quarter for these parameters.

**Self-check rule before Step 3:** After drafting all Low/Base/High values, calculate the implied all-in Conversion cost (machine + labor + energy components) per part and compare to the industry rule-of-thumb for that process and country. If the per-unit Conversion cost exceeds 50% of the current purchase price for a commodity part, investigate before proceeding.

## Pitfall P2 — Multiple suppliers for the same material ID → always build separate models, never blend

**The problem:** The PPE spend file can return multiple rows for a single Material ID — different suppliers, often in different countries, at materially different prices. Blending these into a weighted average current price creates a fictitious reference point that obscures the real negotiation picture:
- A Vietnamese low-cost manufacturer at €0.013/EA and a German distributor at €0.018/EA blend to €0.014/EA — making the Vietnamese supplier look "at parity" when it is actually 40%+ above its own should-cost floor.
- The negotiation levers for a manufacturer and a distributor/trader are completely different; a single blended model cannot serve either negotiation.

Each supplier gets its own, fully independent Should-Cost build. Never aggregate volumes, blend prices, or produce a single combined model across suppliers.

## Critical calibration rules C1–C6 (apply before benchmarking any parameter)

**Rule C1 — Use annual volume as the primary signal for cavities, not drawing complexity.**
Drawing complexity (number of dimensions, tolerances) reflects precision requirements, not tool cavitation. Cavity count is driven by annual volume and part size:
- High volume (>100k units/yr) + small/medium part (<100×100mm): 8–16 cavities typical for IM; 4–8 for die casting; 4 or gang-tool for stamping
- Medium volume (20k–100k units/yr) + medium part: 4–8 cavities IM; 4 die casting; 1–4 stamping
- Low volume (<20k units/yr): 1–4 cavities IM; 1–2 die casting
- NEVER infer low cavities solely from drawing complexity.

**Rule C2 — Machine rate class must match part size and cavity count, not a generic bracket.**
For injection moulding: a 12-cavity tool for a medium-frame part runs on a 100–200t machine (EUR 50–75/h), not a 200–500t machine. For small precision stampings (<50mm, <1.5mm thick): progressive die on 25–60t press at EUR 40–60/h — NOT a 200–500t press at EUR 110/h. For small Zamak die castings (<10cm³): hot-chamber machine at EUR 40–60/h.

**Rule C3 — Check whether assembly labor is actually needed.**
Snap-fit/press-fit features → assembly labor negligible or zero. Screw fastening (standard torque) → simple jig op, 3–5s/screw, add only if drawing confirms manual assembly. Welded/bonded/heat-staked → real cost, estimate from joint count. No evidence of a separate assembly step → do NOT add assembly labor.

**Rule C4 — Standard fasteners are typically manufactured components, not purchased standard parts, when custom-spec or plated.**
A custom fastener (special head geometry, plating spec, tight tolerance) → treat as cold-headed manufactured part, not a commodity catalogue purchase. A fully standard fastener with no special spec → use market purchase price.

**Rule C5 — Match freight cost to actual shipment pattern at the given volume.**
<50k units/yr: parcel/LTL or groupage, EUR 0.008–0.020/unit intra-EU. 50k–200k units/yr: LTL/groupage, EUR 0.005–0.015/unit. >200k units/yr: may justify FTL, EUR 0.003–0.010/unit. Do NOT use FTL rates unless volume justifies dedicated truck loads.

**Rule C6 — Machine rate must be MACHINE-ONLY — never all-in.** (See Pitfall P1 for full detail.)
```
Machine rate (€/h) = [capex × (1/dep_years + interest_rate + maint_rate + space_rate) + annual_tooling] ÷ effective_annual_hours
```

## costing_accuracy_rules.md Rules 1–6 (mandatory for every model)

**Rule 1 — Nesting Efficiency and Scrap Credit (Material).** Never omit nesting yield. `Gross weight = Net weight / (Nesting yield / 100)`; `Sheet metal cost = Gross weight × Material price/kg − Scrap credit`, where `Scrap credit = (1 − nesting yield) × material price/kg × gross weight × scrap_recovery_pct`. Typical nesting yield 55–80% for laser-cut sheet-metal assemblies.

**Rule 2 — Setup Cost Amortisation Over Correct Batch Size.** `Setup cost per unit = Setup time h/lot × Setup rate €/h / Avg lot size`. Lot count per year MUST come from HAGER PPE order history, never assumed. Never divide setup cost by annual volume directly.

**Rule 3 — Feature-Based Costing.** Separate critical/precision features (full time) from standard (standard time) from non-critical/cosmetic (0.5–0.7× fast-pass factor). Read the title-block general tolerance; only explicitly tighter-toleranced features are "critical".

**Rule 4 — Regional Rate Lookup (not global averages).** Always look up operator and machine rates from the supplier's actual region (see benchmarks.md regional tables and costing_accuracy_rules.md regional rate tables), never a global average.

**Rule 5 — Multi-Tasking / Mill-Turn / Multi-Op Logic.** One setup per lot across ALL machines in a routing (not one per part, not one per machine per part). Surface treatment freight is a single job-lot operation, not doubled up with main freight.

**Rule 6 — Scrap Credit Calculation.** `Scrap credit = Scrap weight × Material price × Scrap recovery rate`, where `Scrap weight = Gross weight − Net weight`. Recovery rates: stainless 1.4301 15–25%, 1.4404 20–30%, aluminum 25–35%, carbon steel 10–18%, copper/brass 35–50%.
