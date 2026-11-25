---
name: hager-should-cost-builder
description: "Builds Should-Cost analyses for Hager Group procurement. Fixed 5-bucket structure (Material, Conversion, Packaging & Logistics, Overheads, Margin) with Low/Base/High sensitivity. Trigger with a SAP material ID; auto-retrieves specs from SharePoint; Volume, Spend, Price from HAGER PPE 2025.xlsx. Multiple suppliers: one model per supplier — never blended. Factor costs cross-checked against region-appropriate benchmarks — never WEU defaults for non-WEU suppliers. Compound raw materials always decomposed into constituents (unit price × weight%) — never aggregate catalogue prices. Produces calculation Excel + graphics-team slide-values handover per supplier. Use for: should-cost, cost build, cost teardown, clean-sheet cost, benchmark price, or any Hager material ID."
---

# Should-Cost Builder

Standardized workflow to produce Should-Cost analyses for procured materials for Hager Group procurement. Built for scaling across many materials with one consistent methodology.

## When to use

Trigger this skill when the user:
- Sends a SAP **material ID alone** (e.g. "1000126756", "Material 1000126756", "Should-Cost für 1000126756") — the skill retrieves all input data from OneDrive
- Uploads technical drawings, RFQs, supplier quotes, or material specs and asks for a should-cost
- Says "build a should-cost for [material]", "cost build for [component]", "should costing", "clean-sheet cost", "cost teardown", "benchmark price"
- Asks to apply the same should-cost methodology to a different Hager material
- Hands you a filled `Should_Cost_Input_Template_EMPTY.xlsx` and asks to calculate the model

## Output (always)

**When one supplier:** two files + one chat block set.
**When N suppliers:** N×2 files (one calculation model + one slide-values file per supplier) + N chat block sets, one per supplier. Never merge or average across suppliers. See **Pitfall P2** below.

Per supplier, in this order:

1. **Calculated Excel model** — 3 tabs (`1. Overview & Results`, `2. Inputs`, `3. Calculation`) — identical layout to the reference. Includes Run-ID, supplier name in filename and header, date, assumptions block. Named `Should_Cost_{Material-ID}_{SupplierShortName}_{YYYYMMDD}_v{NN}.xlsx`.
2. **Graphics-team handover Excel** — `{Material-ID}_SlideValues.xlsx` — 4 tabs: `Slide 1 - Cover`, `Slide 2 - Cost Build`, `Slide 4 - Inputs`, `Slide 5 - Sensitivity`. Every value the BCG graphics team needs to populate the standardized PowerPoint template, ready for row-by-row copy-paste. See `references/slide_output_format.md` for exact layout and formatting.
3. **Slide-ready content blocks in chat** — same content as deliverable 2, but formatted as chat-readable blocks for quick visual scan and review before handover to graphics.

After all per-supplier deliverables: one **cross-supplier comparison table** in chat showing Current Price, Should Cost (base), Impact/unit, and Annual Impact side-by-side for all suppliers.

Do NOT generate the PowerPoint file. The graphics team owns the PPT template and fills it from deliverable 2.

## Fixed structure (DO NOT change)

The cost build is fixed to 5 input buckets plus a subtotal and 3 derived lines. The waterfall always reads left to right:

| # | Bucket | Notes |
|---|---|---|
| 1 | **Material** | Raw material + purchased components |
| 2 | **Conversion** | All direct manufacturing operations |
| — | **Manufacturing Costs** | Subtotal = Material + Conversion |
| 3 | **Packaging & Logistics** | Packaging materials + all freight/logistics |
| 4 | **Overheads** | SG&A + manufacturing overheads combined |
| 5 | **Margin** | Supplier margin on (Manuf. Costs + P&L + Overheads) |
| — | **Should Cost** | = Manufacturing Costs + P&L + Overheads + Margin |
| — | **Impact Potential** | = Current Price − Should Cost |
| — | **Current Price** | From HAGER PPE 2025.xlsx |

**There is no COGS subtotal.**

**Quality costs are NOT modelled.** Do not include CoA/batch certificates, QA admin, FAI amortisation, or incoming inspection costs in any bucket. These are excluded by design — the model covers only manufacturing economics, packaging, and logistics. Quality & Packaging and Logistics are not separate buckets — they are merged into Packaging & Logistics. SG&A is not a separate bucket — it is merged into Overheads.

## Adaptive inputs

Bucket structure is fixed. **Input parameters within each bucket adapt to the manufacturing process.** Read `references/bucket_inputs_by_process.md` to pick the right parameter set.

Always provide Low / Base / High for every numeric input. Base is used in the main calculation; Low/High feed the sensitivity tornado.

---

## MANDATORY PITFALLS — read before every build

These two pitfalls were identified through live calibration work (0V0139 case, May 2026) and caused a 3–5× error in the first model. They are now hard constraints — not guidelines.

---

### Pitfall P1 — Factor cost benchmarks must be region- and context-specific (never inherit WEU defaults for non-WEU suppliers)

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

---

### Pitfall P2 — Multiple suppliers for the same material ID → always build separate models, never blend

**The problem:** The PPE spend file can return multiple rows for a single Material ID — different suppliers, often in different countries, at materially different prices. Blending these into a weighted average current price creates a fictitious reference point that obscures the real negotiation picture:
- A Vietnamese low-cost manufacturer at €0.013/EA and a German distributor at €0.018/EA blend to €0.014/EA — making the Vietnamese supplier look "at parity" when it is actually 40%+ above its own should-cost floor.
- The negotiation levers for a manufacturer and a distributor/trader are completely different; a single blended model cannot serve either negotiation.

**Mandatory decision tree at Step 0e — inventory output:**

```
IF the PPE spend file returns rows with the same Material ID BUT different Supplier Names:
  → COUNT the distinct suppliers
  → For EACH supplier:
      - Record: Supplier Name | Country | Volume | Spend | Avg Price | Hager Entity
  → DETERMINE supplier type for each:
      - MANUFACTURER: cold heading factory, moulding plant, stamping house, etc.
        → Model the full 5-bucket should-cost (Material, Conversion, Packaging & Logistics, Overheads, Margin) with region-appropriate factor costs
      - DISTRIBUTOR / TRADER: "Verbindungsteile", "Handel", "Trading", "Supply", "GmbH" reseller
        → Model underlying manufacturing cost (at the most likely source country) + trader overhead + trader margin
  → BUILD one separate Excel model per supplier
  → FILE naming: Should_Cost_{Material-ID}_{SupplierShortName}_{YYYYMMDD}_v{NN}.xlsx
  → DO NOT aggregate volumes, blend prices, or produce a single combined model
  → After all per-supplier models: produce one cross-supplier comparison table in chat
```

**Identifying distributor vs. manufacturer:**
- Company name contains: "Handel", "Verbindungsteile", "Supply", "Trading", "Distribution", "Supplies", "Parts" → likely trader
- Company name contains: factory location suffix, "GmbH & Co. KG" with technical name, "Manufacturing", "Forming", "Technik" → likely manufacturer
- Supplier country differs from Hager entity country with no obvious logistics reason → check if intermediary
- Price significantly higher (>20%) than a sister-supplier of the same part → trader premium likely

**Output discipline:** Each supplier's model is self-contained. The cross-supplier comparison in chat makes the price gap and impact opportunity visible per supplier. Never average the impacts.

---

## Workflow

### Step 0: Input discovery (ALWAYS run this first)

The user's data sources follow a fixed convention. Run discovery in this order **before asking the user for anything**.

**Data convention (Team SharePoint):**

All sources live in the same team SharePoint root folder: `https://bcgcloudeur.sharepoint.com/sites/195020-17/Shared Documents/04_Workstream folders/05 Procurement/04_analysis/15_Should Cost Analyses`

| Source | Location | Naming |
|---|---|---|
| Material-specific docs | `<SharePoint root>/{Material-ID}/` | Subfolder named **exactly** the Material ID (e.g. `1D0488`) |
| Cross-material reference drawings | `<SharePoint root>/{Material-ID}/` | Inside the same material subfolder; surface by content search if not immediately visible |
| Spend Data | `<SharePoint root>/HAGER PPE *.xlsx` | Filename contains "HAGER" and "PPE" — always fetch the **latest version** by last-modified timestamp |
| Historical Should-Cost models | `<SharePoint root>/` | Filename contains "Should Cost" or "Should-Cost"; exclude Spend Data file |

**0a — Identify the Material ID.** For Hager, Material IDs are alphanumeric strings of variable length and format (e.g. `620002000`, `0M5200`, `2M3322`, `1VF90018`, `1D0488`). They do **not** follow a single fixed pattern. If multiple IDs are mentioned, ask which is the target.

**0b — Retrieve all source files from team SharePoint via Microsoft 365 MCP:**

All file retrieval uses the same SharePoint root: `https://bcgcloudeur.sharepoint.com/sites/195020-17/Shared Documents/04_Workstream folders/05 Procurement/04_analysis/15_Should Cost Analyses`

1. **Find material subfolder:** `Microsoft 365:sharepoint_folder_search` with `name = {Material-ID}` scoped to the SharePoint root. The subfolder is named exactly after the Material ID (e.g. `1D0488`). Partial match is acceptable if only one result is returned; if multiple folders match, pick the exact match.
2. **List subfolder contents:** `Microsoft 365:read_resource` with the folder URI to list all files inside.
3. **Read each file in the subfolder:** `Microsoft 365:read_resource` with each file URI. This covers material specs, drawings, BOMs, RFQs, and any cross-reference docs. MCP extracts text from PDFs, Excel, Word, and PowerPoint. **Do not** use Filesystem MCP for binary files.
4. **Spend Data file — always fetch latest version from SharePoint root:**
   - **Step 1 — List root folder:** `Microsoft 365:sharepoint_folder_search` on the SharePoint root to retrieve all files at the top level.
   - **Step 2 — Identify latest Spend Data file:** Filter for files whose name contains both `"HAGER"` and `"PPE"`. Accept `.xlsx` or `.xlsb` extensions — note which format was found. If multiple matches exist, select the one with the **most recent last-modified timestamp**.
   - **Step 3 — Attempt to read via MCP:** `Microsoft 365:read_resource` on the selected file URI.
   - **Step 4 — Handle read failures gracefully:**
     - **If MCP returns 406 error** (file too large for direct extraction): The file cannot be read via MCP in this session. Do NOT retry — proceed immediately to the chat upload fallback below.
     - **If file is `.xlsb` format** (Excel Binary Workbook): MCP cannot extract xlsb content. Do NOT attempt — proceed immediately to the chat upload fallback below.
     - **If MCP succeeds**: proceed to sanity check.
   - **Step 5 — Sanity check (only if MCP read succeeded):** Confirm row count ≥ 39,000 data rows and that the 12 expected column headers are present (Hager Company Name, Purchasing Group, Purchasing Category, Product Family, Material Group, Material ID, Material Description, Supplier Name, Unit of Measure, Annual Volume, Annual Spend, Current Average Price). A mismatch signals a structural change — flag to user before proceeding.
   - **Chat upload fallback (triggered by 406 error, xlsb, or any MCP read failure):**
     - Check for a chat upload at `/mnt/user-data/uploads/` matching `HAGER*PPE*.xlsx` or `HAGER*PPE*.xlsb`.
     - If an `.xlsx` upload exists → read it using `openpyxl` via `bash_tool`: `python3 -c "import pandas as pd; df=pd.read_excel('/mnt/user-data/uploads/<filename>'); matches=df[df['Material ID'].astype(str)=='<ID>']; print(matches.to_string())"` — extract the matching row(s) directly.
     - If an `.xlsb` upload exists → read it using `pyxlsb`: `python3 -c "from pyxlsb import open_workbook; ..."` — same extraction logic.
     - If no upload exists → output the following message verbatim and pause: **"The HAGER PPE 2025 spend data could not be fetched from SharePoint (406 / unsupported format). Please upload the file directly to this chat, or provide the following values manually: Annual Volume, Annual Spend, Current Average Price for material ID [X]."** Do NOT proceed until one of these is provided.
   - Filter column `Material ID` (col F) for the target ID once the file is accessible.
   - **Always state in the inventory block**: how the spend data was retrieved (MCP / chat upload / manual) and the filename + last-modified date if available.
5. **Cross-references beyond the material subfolder:** `Microsoft 365:sharepoint_search` with `query = "{material name}"`, `fileType = pdf` scoped to the SharePoint root — surfaces drawings or specs filed outside the material subfolder. Cite as "Cross-reference: {filename}".

**Hager Spend Data — File Structure (`HAGER PPE 2025.xlsx`):**

Single sheet named `HAGER PPE 2025`. 39,273 data rows + 1 header row. Column mapping:

| Column | Header | Used for |
|---|---|---|
| A | Hager Company Name | **Purchasing entity / plant** — used to derive freight destination for logistics cost |
| B | Purchasing Group | Category (level 1) |
| C | Purchasing Category | Category (level 2) |
| D | Product Family | Category (level 3) |
| E | Material Group | Category (level 4) |
| F | Material ID | **Lookup key** — match against user-provided ID |
| G | Material Description | Part description |
| H | Supplier Name | Incumbent supplier |
| I | Unit of Measure | UoM context for cost unit (EA, KG, G, M, M2, ROL, L, etc.) |
| J | Annual Volume | **Volume** (in UoM units p.a.) |
| K | Annual Spend | **Spend** (EUR) |
| L | Current Average Price | **Price** (EUR per UoM unit) — if blank/zero, compute as Spend ÷ Volume |

**Navigation rules:**
- The file has a `Grand Total` row (Hager Company Name = "Grand Total") — **always exclude** this row from all lookups and calculations.
- **One Material ID can appear on multiple rows** — same part bought from different suppliers and/or by different Hager entities. Collect ALL matching rows. **Do NOT aggregate or blend supplier rows** — see Pitfall P2 above. Report each supplier row individually and confirm the per-supplier build plan before proceeding.
- **9,006 rows have zero Annual Volume and zero Current Average Price** — if the target material lands on one of these, flag it explicitly and pause for manual input.
- Material ID format is a plain string — do not zero-pad or strip leading zeros when matching (e.g. `0M5200` ≠ `M5200`).
- There are 36 distinct Hager purchasing entities spanning Europe, Asia, Middle East, and Australia — use the entity name to infer the destination country/region for logistics cost estimation (see supplier country note below).

**Material ID matching — three-tier lookup (apply in order):**

**Tier 1 — Exact match:** Search for rows where `Material ID == user_provided_ID` (case-insensitive, trimmed). If one or more exact matches are found → use them. Stop here.

**Tier 2 — Prefix / variant match:** If no exact match, search for rows where `Material ID starts with user_provided_ID` (e.g. user provides "WXA455" → matches "WXA455X1", "WXA455X2", "WXA455_A", etc.). This handles the Hager convention where variant suffixes (X1, X2, _A, _B, etc.) are appended to a base ID to distinguish transaction-year variants of the same material.
- Collect ALL prefix-matching rows.
- Before using them, apply a **plausibility check**: do the Material Description, Purchasing Category, and Supplier Name of the matches look consistent with the user-provided material? If yes → proceed, stating which variant(s) were found and why they are considered the same material.
- If the matches look like a different material (e.g. different description or purchasing category that doesn't align) → **do not proceed silently**. Output: *"I found rows matching the prefix [ID] but they may represent a different material: [description]. Please confirm these rows correspond to [user material] before I use them."*

**Tier 3 — No match at all:** Output the standard "Spend Data: not found" message and pause for manual input.

**Variant aggregation rule:** When multiple variant rows are found (e.g. WXA455X1 and WXA455X2), aggregate their volumes and spends to represent the full material spend:
- Total Annual Volume = Σ all variant rows' Annual Volume (col J)
- Total Annual Spend = Σ all variant rows' Annual Spend (col K)
- Current Average Price = Total Annual Spend ÷ Total Annual Volume (weighted average across variants)
- List each variant row individually in the inventory block, then show the aggregated totals clearly labelled as "Aggregated across variants"

**Code pattern for prefix matching (use in bash_tool when file is uploaded):**
```python
import pandas as pd
df = pd.read_excel('/mnt/user-data/uploads/HAGER_PPE_2025.xlsx')
df = df[df['Hager Company Name'] != 'Grand Total'].dropna(subset=['Hager Company Name'])
base_id = 'WXA455'  # user-provided ID
# Tier 1: exact
exact = df[df['Material ID'].astype(str).str.strip().str.upper() == base_id.upper()]
# Tier 2: prefix (only if exact is empty)
if exact.empty:
    prefix = df[df['Material ID'].astype(str).str.strip().str.upper().str.startswith(base_id.upper())]
matches = exact if not exact.empty else prefix
print(matches[['Material ID','Material Description','Hager Company Name','Supplier Name','Annual Volume','Annual Spend','Current Average Price']])
```

**Supplier country — important note:**
The file contains **Supplier Name only — no supplier country column.** This creates a real risk during logistics cost estimation (Packaging and Logistics bucket): without knowing the supplier's country, origin-to-destination freight lane cannot be determined precisely.

Mitigation approach — apply in this priority order:
1. **Infer from supplier name** — many names contain a country signal (e.g. "TQ SYSTEM SHANGHAI CO. LTD" → China, "SMARTER LIVING BV" → Netherlands, "WESTMETALL GMBH & CO KG" → Germany). Document the inference explicitly in column H of the Inputs tab.
2. **Cross-reference with OneDrive docs** — purchase orders, RFQs, or tech specs often carry supplier address. Cite the document.
3. **Flag as assumption** — if inference is uncertain, mark as "Supplier country: assumed [country] — to be confirmed with purchasing team" in the Assumptions Block (Tab 2) with confidence = low.
4. **Never fabricate** — if inference is not possible, leave the logistics lane as "TBD" and note it as a blocking open item in Step 7.

Always state the assumed freight lane explicitly: "Supplier: [inferred country] → Hager entity: [country derived from company name]".

For these three values, the Hager Spend Data file is the **only** acceptable source:
- **Annual Volume** (col I)
- **Annual Spend** (col H)
- **Current Average Price** (col J — or H÷I if col J is blank/zero)

Additional fields used (less strict — can be supplemented if missing): Supplier Name, Purchasing Group/Category/Product Family/Material Group.

If the spend data row exists:
- Use those values as-is. **Never override with project-team estimates, chat-message claims, or document-derived numbers** for Volume / Spend / Current Price.
- If documents (e.g. RFQ, quote) mention different volumes or prices, flag the discrepancy in chat as a side note but proceed with spend data values for the build.

If the Material ID is NOT found in the file:
- Output `Spend Data: not found` in the inventory block.
- Pause and ask the user to manually provide Volume, Spend, Current Price inline.
- When manual values are entered, label them prominently in the model:
  - In `2. Inputs` Reference Data section: Source column reads `MANUAL OVERRIDE — Spend Data had no entry; values provided by user on <date>`
  - In `1. Overview & Results` General Information: Row "Inputs source" reads `OneDrive folder {ID} + MANUAL Spend/Volume/Price (no Spend Data entry)`
  - In `Slide Values` Excel Tab 2 (Cost Build): rows for Volume/Spend/Avg Price get yellow fill on column C plus a note in column F: `Manual override — verify with project lead before slide handover`
- Apply the same override formatting consistently across both Excel files.

**0c — Search for historical Should-Cost models:**

Run `Microsoft 365:sharepoint_search` with `query = "Should Cost"` and separately `query = "Should-Cost"`, scoped to the SharePoint root folder. Exclude files matching "HAGER PPE" (those are Spend Data, not models). If matches exist:
- Read 2–3 most-recent models with comparable process or material grade
- Extract their Should-Cost €/unit, cost-bucket %-split, and any sensitivity findings
- Note them as **priors** for use in Step 4.5 (sanity-check gate)
- If no matches exist (first should-cost): note "No historical priors available" — do not invent comparisons

**0d — Check chat uploads.** If files exist in `/mnt/user-data/uploads/`, read in addition. Uploads **override** OneDrive when conflicting (newer info wins) — **except for Volume, Spend, Current Price**, where the strict Hager Spend Data rule above applies. Parse Excel with `openpyxl` (data_only=True; read_only=True for >5 MB), PDFs with `pdfplumber`, Word with `python-docx`, PowerPoint with `python-pptx`.

**0e — Inventory output to user.** Before extraction, output a short inventory:

```
Material-ID: <ID>
Material Description: <description>
SharePoint subfolder (<Material-ID>/): found — <N> files
  - <filenames>
Spend Data: <filename used> (last modified: <date>) — fetched from team SharePoint root
  Match type: Exact / Prefix-variant (base ID <X>, variants found: <list>)
  Plausibility check: <description of why variants are accepted as same material, or clarification request>

  [For each distinct supplier row:]
  Supplier <N>: <Supplier Name> | Country: <inferred country> | Entity: <Hager Company Name>
                UoM: <X> | Vol: <J> EA/yr | Spend: €<K> | Price: €<L>/unit
                Type: MANUFACTURER / DISTRIBUTOR-TRADER / UNKNOWN

  ─────────────────────────────────────────────────
  Total across all suppliers: Vol <Σ J> | Spend €<Σ K>
  Note: prices NOT blended — see per-supplier models below.

  [If single supplier:]
  Build plan: 1 model — <Supplier Name> (<country>)

  [If multiple suppliers:]
  Build plan: <N> separate models — one per supplier:
    Model 1: <Supplier A> (<country A>) — Vol <X> | Price €<Y>/unit | Type: <mfr/trader>
    Model 2: <Supplier B> (<country B>) — Vol <X> | Price €<Y>/unit | Type: <mfr/trader>
    ...
  Proceeding unless user objects.

Additional cross-references found in SharePoint: <N> drawings, <N> historical Should-Cost models
Chat uploads: <none / N files>
```

**⚠ PITFALL P2 CHECKPOINT:** If multiple distinct supplier rows exist — STOP before building any model and confirm the per-supplier build plan with the user. Do not proceed with a blended or single-supplier-only model unless user explicitly instructs otherwise.

If Spend Data is missing, **pause here** until user provides values. Don't proceed to extraction.

**Failure cases:**

| Situation | Action |
|---|---|
| Material subfolder not found in SharePoint | Tell user, offer chat upload fallback. Do not invent. |
| Material subfolder empty | Ask for upload of Drawing + BOM at minimum. |
| Spend Data file not found in SharePoint root | Check chat upload fallback. If also absent, pause and ask user to manually provide Volume, Spend, Current Price. Mark as MANUAL OVERRIDE in both output files. |
| Spend Data row for Material ID not found (exact) | Try Tier 2 prefix match before giving up. Only report "not found" if both exact and prefix searches return nothing. |
| Prefix match found but description looks like a different material | Do NOT proceed silently. Present the matches with their descriptions and ask user to confirm before using. |
| Prefix match found and plausibility check passes | Proceed. State match type as "Prefix-variant" in inventory block. Aggregate volumes and spends across all variant rows. |
| Spend Data row present but document data contradicts | Use Spend Data. Flag discrepancy in chat as side note. Do not override. |
| Spend Data column structure changed (sanity check fails) | Flag structural mismatch to user before proceeding. Do not assume column positions. |
| PDF returns empty text (scanned) | Ask for OCR or screenshot. |
| Drawing lacks readable dimensions | Ask user to confirm weight / key dimensions or upload screenshot. |
| Multiple drawings uploaded but relationship unclear | State what was found, hypothesise sub-assembly, ask user to confirm before proceeding. |
| Sub-assembly confirmed but BOM absent or illegible | Ask user to provide: child component codes, quantities, and raw material per component. Do NOT proceed. |
| Sub-assembly confirmed but drawing for a child component is missing | Flag the gap, attempt to derive dimensions from assembly drawing, state confidence level. Ask user to confirm before proceeding with that component. |

### Step 1: Extract from documents — including sub-assembly detection

Read every retrieved document. For each document, first determine whether the material ID is a **single component** or a **sub-assembly** (see detection protocol below), then extract accordingly.

**Always extract regardless of assembly type:**
- Material identification: name, SAP number, drawing number, specification reference
- Physical properties: weight (g or kg/part), dimensions (L × W × H or diameter × height, in mm), material grade, density (g/cm³) if stated
- Manufacturing process clues: thermoformed, injection moulded, CNC machined, stamped, PCB assembly
- Volume, spend, current price (HAGER PPE 2025.xlsx)
- Incumbent supplier (HAGER PPE 2025.xlsx — Supplier Name column H)
- Purchasing entity / plant (HAGER PPE 2025.xlsx — Hager Company Name column A)
- Unit of measure (HAGER PPE 2025.xlsx — column I)
- Category hierarchy: Purchasing Group / Purchasing Category / Product Family / Material Group (HAGER PPE 2025.xlsx columns B–E)
- Tolerances, surface finish, special requirements

If a critical field is missing after reading all sources, list gaps explicitly before proceeding. **Do not guess weights, volumes, prices, or supplier identities.**

---

**Sub-Assembly Detection Protocol (mandatory when multiple drawings are present):**

**Step 1A — Detect sub-assembly:**

Apply the following checks when processing documents:
- More than one drawing is uploaded or found in the SharePoint folder → immediately investigate sub-assembly
- Drawing title block contains a BOM table (columns: Pos / Part Code / Part Description / Material Description / Qty) → this is an assembly drawing
- Drawing header says "ASSEMBLY", "SUBASSEMBLY", "FRAME WITH INSERT", or similar → sub-assembly confirmed
- Part description in HAGER PPE 2025 contains words like "FRAME", "ASSEMBLY", "MODULE", "KIT" → investigate further
- Multiple part codes referenced in a single drawing (e.g. W1B0162_00 + W1B0163_00 inside W2B0032_02) → sub-assembly confirmed

**If sub-assembly confirmed → follow the Sub-Assembly Workflow below.**
**If single component confirmed → follow the existing single-component workflow (Steps 1.5 onwards).**
**If uncertain → state findings, ask user to confirm before proceeding.**

---

**Sub-Assembly Workflow (replaces Steps 1.5–5 for assemblies):**

**Step SA-1 — Read the BOM from the assembly drawing.**

The BOM is typically found in the bottom-right title block of the assembly drawing. Extract:

| Field | What to capture |
|---|---|
| Pos | Position number in the assembly |
| Part Code | Child component SAP/drawing code (e.g. W1B0162_00, W1B0163_00) |
| Part Description | Description of the child component |
| Material Description | Raw material for that child component (e.g. PA66-GF50, Steel W0L0020_00) |
| Qty | How many of this component are in one assembly |

**If BOM is present and readable** → proceed with all child components listed.
**If BOM is absent or illegible** → output: *"I can see this is a sub-assembly but I cannot read the BOM from the drawing. Please confirm: (1) the child component part codes and quantities, and (2) the raw material for each component."* Do NOT proceed until confirmed.

**Step SA-2 — Identify each child component's drawing.**

For each child component in the BOM:
1. Check if a separate drawing was uploaded in this chat (match by part code in filename or drawing header)
2. Search SharePoint subfolder for a file matching the part code
3. If no drawing found for a child component → flag it explicitly: *"No drawing found for [part code] — weight and dimensions will need to be derived from the assembly drawing or user input"*

Note: The assembly drawing often contains all the dimensional and weight information needed for child components directly (as seen in W2B0032 which lists mass and volume for both W1B0162 and W1B0163 in its title block). Always check the assembly drawing first before concluding a child drawing is missing.

**Step SA-3 — Extract spec parameters for each child component.**

For each child component, extract from its own drawing OR from the assembly drawing title block:
- Weight (g) or Volume (cm³) + Density (g/cm³) → apply Weight Derivation Protocol (Tiers 1/2/3 below) per component
- Dimensions: L × W × H (mm)
- Material grade
- Manufacturing process
- Machine parameters (cycle time, cavities/tooling layout, parts/hour, press force/stroke rate)
- Ribs + bosses factor (if applicable)
- Scrap rate

**Step SA-4 — Build a separate Should-Cost for each child component.**

Run the full 5-bucket should-cost calculation independently for each child component:
- Each component gets its own full parameter set (process-appropriate benchmarks, correct material price, correct machine type)
- Each component gets its own weight derivation (Tier 1/2/3 per component)
- Mixed processes are expected and correct (e.g. plastic frame = injection moulding; metal insert = stamping)
- Each component's should-cost is expressed as EUR/pcs for **one unit of that component**
- Bucket mapping per component: Material | Conversion | Packaging & Logistics | Overheads | Margin

**Step SA-5 — Roll up to the assembly level.**

Assembly Should Cost = Σ (component Should Cost per pcs × quantity in BOM)

For each cost bucket at the assembly level:
```
[Bucket] assembly = (Component 1 [bucket] × qty1) + (Component 2 [bucket] × qty2) + ...
```

Example for WXA450:
```
Material (WXA450)              = Material (W1B0162) × 1 + Material (W1B0163) × 4
Conversion (WXA450)            = Conversion (W1B0162) × 1 + Conversion (W1B0163) × 4
Manufacturing Costs (WXA450)   = Material (WXA450) + Conversion (WXA450)
Packaging & Logistics (WXA450) = P&L (W1B0162) × 1 + P&L (W1B0163) × 4
Overheads (WXA450)             = Overheads (W1B0162) × 1 + Overheads (W1B0163) × 4
Margin (WXA450)                = Margin (W1B0162) × 1 + Margin (W1B0163) × 4
Should Cost (WXA450)           = Should Cost (W1B0162) × 1 + Should Cost (W1B0163) × 4
```

Note: Unless the assembly drawing or supplier documentation explicitly shows a separate assembly operation cost (e.g. press-fitting, welding, fastening labour), do NOT add a separate assembly cost bucket. The sub-components' costs already embed the labour for their own production.

**Step SA-6 — Excel output structure for sub-assemblies.**

The output Excel must follow the reference structure (WXA450_Should_Cost_Example.xlsx):
- **One tab per child component** — full 5-bucket should-cost (Material, Conversion, Packaging & Logistics, Overheads, Margin) in the same layout as a single-component model. Tab named after the child part code (e.g. "W1B0162", "W1B0163").
- **One assembly rollup tab** — named after the assembly material ID (e.g. "WXA450"). Contains:
  - Header: Part category = "Assembly", Ref no = [assembly ID], Material Description, Raw material = combined list
  - Column headers: Cost Component | [Component 1 code] | [Component 2 code] | ... | Assembly [ID]
  - Rows: one per cost bucket (Material, Conversion, Manufacturing Costs (subtotal), Packaging & Logistics, Overheads, Margin, Should Cost, Total)
  - Quantity row showing qty of each component in the assembly
  - Each cell = component tab value × quantity (formula linking to component tabs)
  - Assembly Total = sum of all component totals (weighted by qty)
  - Percentage column showing each bucket's % of assembly total
  - Actual price, Difference (= Actual − Should Cost), Savings % rows at the bottom
- **Tab order**: component tabs first (in BOM order), assembly rollup tab last
- **Slide Values file**: updated to reflect assembly-level numbers in all slides

**Step SA-7 — Inventory block for sub-assemblies.**

Replace the standard inventory block with:
```
Material-ID: <assembly ID>
Assembly type: Sub-assembly — <N> child components
BOM:
  Pos 1: [part code] — [description] — [material] — qty [X] — drawing: [found / not found]
  Pos 2: [part code] — [description] — [material] — qty [X] — drawing: [found / not found]
Spend Data: [as normal]
Build plan: Should-Cost for each child component separately, then roll up to assembly total.
Proceeding unless user objects.
```

---

**Weight Derivation Protocol (mandatory — follow in this exact priority order):**

Weight is the single most critical input for the Material bucket. Never use volume directly as a substitute for weight without conversion. Apply the following three-tier logic and document which tier was used in the Assumptions Block (Tab 2, column "Justification"):

**Tier 1 — Explicit weight in documents (preferred):**
- If the drawing, datasheet, or BOM explicitly states a part weight (e.g. "Weight: 9.11 g", "Masse: 0.045 kg") → use that value directly.
- Record as: `Weight: X.XX g/part | Source: [document name] | Tier 1 — explicit | Confidence: High`
- Cross-check sanity: weight ÷ density should approximate the geometric volume. If ratio is off by >30%, flag for review.

**Tier 2 — Volume given, weight not given:**
- If the document states a geometric or calculated volume (e.g. "Volume: 5.36 cm³") but no weight → convert using density.
- **Density source priority:**
  1. Density explicitly stated in drawing or datasheet (e.g. "Density: 1.7 g/cm³") → use directly. Source: document name.
  2. Density not stated → research the typical density for the identified material grade:
     - Search the material name + "density g/cm3" (e.g. "AMPAL MPV 7500 S density g/cm3", "BMC thermoset density")
     - Cross-check against published material data sources: Matweb (https://www.matweb.com), Campus Plastics (https://www.campusplastics.com), MatBase (https://www.matbase.com), or manufacturer TDS (Technical Data Sheet)
     - Use the value found and cite the source + URL
- Weight = Volume (cm³) × Density (g/cm³)
- Account for ribs, bosses, and geometric complexity: if the drawing shows ribs/bosses, apply a rib/boss factor (typically +10–30% of nominal wall volume) OR extract the total volume including all features.
- Record as: `Weight: X.XX g/part | Derived from volume X.XX cm³ × density X.XX g/cm³ | Density source: [name + URL] | Tier 2 — volume × density | Confidence: Medium`

**Tier 3 — Neither weight nor volume given; dimensions available:**
- If no weight and no volume are stated, but part dimensions (L × W × H, or diameter × height, or wall thickness + surface area) are available → calculate volume geometrically.
- **Geometric volume calculation approach:**
  - Simple prismatic part (box, plate, disc): V = L × W × H (adjust for hollow sections)
  - Injection-moulded shell part: V ≈ Surface Area × average wall thickness. Average wall thickness typically 1.5–3.5 mm for injection moulded parts; use thickness from drawing if stated.
  - Stamped flat part: V = blank area × sheet thickness (adjust for blanking yield)
  - Turned part (cylinder/shaft): V = π × r² × length (sum all cylindrical features)
  - For complex geometries: decompose into simple sub-shapes, sum volumes
  - Always add ribs + bosses correction if present: multiply base volume by (1 + rib/boss fraction, typically 0.15–0.25 for standard IM parts)
- Then apply density conversion exactly as in Tier 2 above.
- Record as: `Weight: X.XX g/part | Calculated: V = [formula] = X.XX cm³ × density X.XX g/cm³ | Geometry source: drawing [name] | Density source: [name + URL] | Tier 3 — calculated | Confidence: Low — verify with supplier`

**Weight derivation — error prevention rules:**
- **NEVER pass a volume figure (cm³ or mm³) directly into the Material cost formula as if it were a weight (g or kg).** Units must be explicit. If the model shows kg/part and the drawing states cm³, a conversion step must exist and be documented.
- If volume is in mm³ → convert to cm³ first: divide by 1,000 (1 cm³ = 1,000 mm³)
- If weight is in g → convert to kg for the EUR/kg price calculation: divide by 1,000
- Always state the unit at each step in the Assumptions Block to make the conversion chain auditable
- After deriving weight, state it explicitly in the Pre-Build Reasoning Block (Step 1.5) with its tier and confidence level

### Step 1.5: PRE-BUILD REASONING BLOCK (mandatory)

**For single components:** produce the block below in chat before any numeric estimates.
**For sub-assemblies:** produce one block PER child component, clearly labelled (e.g. "=== PRE-BUILD REASONING — W1B0162 ===").

```
=== PRE-BUILD REASONING — [component code or "single component"] ===

[FOR SUB-ASSEMBLIES ONLY — include at top of first component block:]
Assembly structure:
- Assembly ID: [e.g. WXA450]
- Child components: [e.g. W1B0162 (qty 1, PA66-GF50, injection moulded) + W1B0163 (qty 4, Steel, stamped)]
- BOM source: [drawing name + where BOM was found]
- Build plan: Should-Cost each component separately, then roll up

Weight Derivation:
- Part weight used: <X.XX> g/part
- Derivation tier: Tier 1 (explicit) / Tier 2 (volume × density) / Tier 3 (calculated geometry × density)
- Density used: <X.XX> g/cm³ | Source: <name + URL>
- Unit conversion chain: <e.g. "8.04 cm³ × 2.03 g/cm³ × (1 + 0.25 rib factor) = 20.42 g = 0.02042 kg/part">
- Confidence: High / Medium / Low

Process Identification Rationale:
- Primary hypothesis: <process>
- Why this and not <alternative process 1>: <reason>
- Why this and not <alternative process 2>: <reason>
- Confidence: high / medium / low

Cost-Driver Hypothesis (BEFORE running the model):
- Expected dominant bucket #1: <bucket> at ~<X>% of Should Cost — reasoning: <...>
- Expected dominant bucket #2: <bucket> at ~<X>% — reasoning: <...>
- Expected smallest bucket: <bucket> at ~<X>% — reasoning: <...>
- Note: within the Conversion bucket, verify that machine + labor + energy sub-components sum correctly and no element is double-counted.

Reasonability Window for Should Cost:
- Current Price: <X> €/unit [assembly level] or <estimated component share> €/unit [component level]
- Plausible Should Cost range (before modelling): <low> – <high> €/unit
- Rationale: <country, process, volume, material grade>

Critical Assumptions (low confidence — please confirm):
1. <assumption with rationale>
2. <assumption with rationale>
(max 3 per component)

Open Questions (only if blocking):
- <question>
```

**Rules:**
- For sub-assemblies: present all component reasoning blocks together before asking for user OK — don't ask after each component individually
- Min 2 alternative process routes per component
- Weight tier rule: Tier 2 or Tier 3 weight MUST appear as a Critical Assumption with full conversion chain
- Max 3 critical assumptions; max 2 open questions per component — anti-bloat discipline

**⚠ COMPLEXITY FLAG — triggers Step 2.5 (mandatory evaluation after every Pre-Build Reasoning block):**

After completing Step 1.5, evaluate ALL of the following criteria. If **two or more** are true, **Step 2.5 is mandatory** before proceeding to Step 3 benchmarking:

| Criterion | Signal | Examples |
|---|---|---|
| **CF1 — No commodity price exists** | Raw material has no LME / index price; price is captive or proprietary | Nanocrystalline alloy ribbon, specialty resin blend, proprietary magnetic compound |
| **CF2 — Multi-step transformation** | Part cannot be priced from raw material alone; requires 3+ manufacturing steps with different cost structures | Melt-spin → wind → anneal → test chain; BMC compound → mould → cure → machine |
| **CF3 — Supplier has captive material supply** | Supplier makes its own raw material internally (no arm's-length price) | VAC makes VITROPERM ribbon; MAGNETEC makes NANOPERM ribbon |
| **CF4 — Confidence on dominant input is LOW** | The largest single cost driver (>25% of estimated SC) is Tier 3 or lower; no verifiable market reference | Core dimensions unknown; alloy composition unconfirmed; proprietary process yields |
| **CF5 — Part family is unfamiliar to the model** | Component falls outside the fastener / stamped metal / injection moulded plastic families covered by benchmarks.md | Wound coil, transformer, electromechanical actuator, PCB assembly, specialty ceramic |
| **CF6 — High unit price relative to apparent simplicity** | Unit price >€0.20 for a small component with unclear cost structure signals specialty premium or multi-layer supply chain | Toroidal sensor coil €0.67, specialty magnet assembly, ASIC chip |

Flag which criteria triggered in the Pre-Build Reasoning block under a new subsection:

```
Complexity Assessment:
  CF1 — No commodity price:    YES / NO — <brief reason>
  CF2 — Multi-step transform:  YES / NO — <brief reason>
  CF3 — Captive material:      YES / NO — <brief reason>
  CF4 — Low-conf dominant:     YES / NO — <brief reason>
  CF5 — Unfamiliar family:     YES / NO — <brief reason>
  CF6 — High unit price:       YES / NO — <brief reason>
  → Criteria triggered: <N of 6>
  → Step 2.5 required: YES (≥2 criteria) / NO (0–1 criteria)
```

If Step 2.5 is required, announce it before starting Step 2: *"This component triggers the Complex Component Deep-Dive (Step 2.5) due to [criteria]. Running deep-dive before benchmarking."*

### Step 2: Determine manufacturing process and pick input parameters

Read `references/bucket_inputs_by_process.md` and pick the relevant parameter set.

**For sub-assemblies:** each child component gets its own process classification independently. Mixed processes are expected and correct (e.g. plastic frame = injection moulding parameters; metal insert = stamping parameters). Do NOT apply the same process parameters to all components — use the material grade and machine parameters from each component's drawing section.

Use the category mapping table at the bottom of `references/bucket_inputs_by_process.md` to map Hager category → process for each component if the process is not explicitly stated in the drawing.

**Critical calibration rules (mandatory — applied before Step 3):**

These rules are derived from real calibration analysis (WXA450G case and 0V0139 case) where the skill over-estimated by 3.6× and 4–5× due to systematic errors. Apply all six checks before benchmarking:

**Rule C1 — Use annual volume as the primary signal for cavities, not drawing complexity.**
Drawing complexity (number of dimensions, tolerances) reflects precision requirements, not tool cavitation. Cavity count is driven by annual volume and part size:
- High volume (>100k units/yr) + small/medium part (<100×100mm): 8–16 cavities typical for IM; 4–8 for die casting; 4 or gang-tool for stamping
- Medium volume (20k–100k units/yr) + medium part: 4–8 cavities IM; 4 die casting; 1–4 stamping
- Low volume (<20k units/yr): 1–4 cavities IM; 1–2 die casting
- If the drawing states a cavities number explicitly → use it. If not, derive from volume first, then cross-check machine parameter section in drawing if available.
- NEVER infer low cavities solely from drawing complexity. A 73.8×73.8mm electrical frame at 46k+ units/yr in a high-volume Italian moulding shop is a 12-cavity tool — not 4.

**Rule C2 — Machine rate class must match part size and cavity count, not a generic bracket.**
For injection moulding: a 12-cavity tool for a medium-frame part runs on a 100–200t machine (EUR 50–75/h), not a 200–500t machine. The clamping force required = cavity count × projected area × material fill pressure. For small precision stampings (<50mm, <1.5mm thick): progressive die on 25–60t press at EUR 40–60/h — NOT a 200–500t press at EUR 110/h. For small Zamak die castings (<10cm³): hot-chamber machine at EUR 40–60/h.

**Rule C3 — Check whether assembly labor is actually needed.**
Before adding any assembly cost bucket, verify from the drawing whether assembly is a genuine separate operation:
- Snap-fit or press-fit features on the drawing → parts self-assemble; assembly labor = negligible or zero
- Screw fastening (standard torque) → simple jig operation; 3–5s per screw; add only if drawing confirms manual assembly
- Welded, bonded, or heat-staked subassemblies → assembly cost is real; estimate time from joint count
- If no evidence of a separate assembly step → do NOT add assembly labor. Flag as zero with a note.

**Rule C4 — Standard fasteners (screws, bolts, rivets) are typically manufactured components, not purchased standard parts, when they are custom-spec or plated.**
If the drawing shows a custom fastener (e.g. "Screw M3 For Claws PZ1+Slot" with 5µm Zn electrodeposition, special head geometry, LQA 100ppm) → treat as cold-headed manufactured part, NOT a commodity Würth/Bossard purchase. Cold-heading benchmark for M3 custom screw: EUR 0.015–0.025/pcs at 9,000 pcs/hr.
If the drawing shows a fully standard fastener with no special spec → use market purchase price.

**Rule C5 — Match freight cost to actual shipment pattern at the given volume.**
At volumes below ~150k units/yr, dedicated FTL freight is unrealistic. Use consolidated/groupage freight rates:
- <50k units/yr: parcel/LTL or groupage; EUR 0.008–0.020/unit for intra-EU medium-distance
- 50k–200k units/yr: LTL/groupage; EUR 0.005–0.015/unit
- >200k units/yr: may justify FTL lanes; EUR 0.003–0.010/unit
Default for Hager electrical parts from Italy/Europe at typical volumes: EUR 0.010–0.020/unit consolidated. Do NOT use FTL rates unless volume justifies dedicated truck loads.

**Rule C6 — Machine rate must be MACHINE-ONLY — never all-in. (See Pitfall P1 for full detail.)**
Within the Conversion bucket, the machine rate sub-component must be **machine-only** (depreciation + maintenance + tooling + space cost). Labor and energy are always added separately inside the Conversion formula. Never use a composite "all-in conversion rate" (such as the WEU benchmarks in benchmarks.md) as the machine rate — that causes double-counting within Conversion. Derive machine rate bottom-up from equipment capex:
```
Machine rate (€/h) = [capex × (1/dep_years + interest_rate + maint_rate + space_rate) + annual_tooling] ÷ effective_annual_hours
```
For a Vietnamese cold header (Chinese OEM ~$80k, 10yr dep, 6,000h/yr): ~€2–4/h machine-only.
For a Western EU Sacma cold header (~€300k, 8yr dep, 5,500h/yr): ~€10–14/h machine-only.
Cross-check: machine-only rate × cycle/OEE + labor sub-cost + energy sub-cost should yield a plausible total Conversion cost per part for the process and country.


### Step 2.5: Complex Component Deep-Dive (conditional — only when Step 1.5 triggers ≥2 complexity criteria)

**Purpose:** When a component has no commodity price reference, uses captive or proprietary materials, or involves a manufacturing chain that is unfamiliar to benchmarks.md, a standard benchmark lookup will produce unreliable inputs. This step replaces benchmark lookup with a systematic research-and-verify protocol that builds the raw material and process cost from first principles — before any values are fed into the model.

**Scope:** Applies to the entire component. For sub-assemblies, apply per child component that triggers ≥2 criteria independently.

**This step does NOT change the 5-bucket output structure (Material, Conversion, Packaging & Logistics, Overheads, Margin).** It changes HOW the inputs to those buckets are derived — replacing "look up benchmarks.md" with "derive from constituent research."

---

#### Step 2.5a — Identify and decompose all raw materials

For each material in the component's bill of materials:

**1. Establish the material family and alloy/compound class.**
- If proprietary brand name: identify the generic family (e.g. VITROPERM → Fe-Si-B-Nb-Cu FINEMET-type nanocrystalline; NANOPERM → Fe-Zr-B-Cu type)
- Search: `"[brand name] composition atomic percent"` and `"[brand name] alloy family"` to confirm
- If multiple sub-grades exist (e.g. VITROPERM 500F vs 550HF), confirm which grade applies to this specific application
- Document: alloy family, confirmed composition (at%), key sources

**2. Convert atomic% composition to weight%.**
- Use atomic masses: Fe=55.85, Cu=63.55, Si=28.09, B=10.81, Nb=92.91, Zr=91.22, Mo=95.96, Co=58.93
- Formula: wt%(element) = [at%(element) × atomic_mass(element)] / Σ[at%(i) × atomic_mass(i)] × 100
- Document the full conversion table — this is the foundation of the RM cost calculation

**3. Price each constituent from authoritative sources.**

For each constituent representing ≥5% by weight:

| Element | Primary price source | Quoted unit | Conversion to €/kg element |
|---|---|---|---|
| Fe | Pig iron / scrap: Destatis, IMARC | €/kg | Direct |
| Cu | LME spot | $/t | ÷1000, ÷EUR/USD rate |
| Si | ChemAnalyst / Roskill metallurgical grade | €/kg | Direct |
| B | Ferroboron alloy price ÷ B content (20–22%) | $/kg FeB | ÷ B content, ÷EUR/USD |
| Nb | **USGS MCS current year** $/kg FeNb alloy ÷ 0.65 | $/kg FeNb | ÷ 0.65, ÷EUR/USD |
| Zr | FeZr ferroalloy (AMG Advanced Metallurgy) — NOT Zr metal | $/kg FeZr | ÷ Zr content, ÷EUR/USD |
| Mo | Fastmarkets / Platts European ferromolybdenum | $/kg FeMo | ÷ Mo content, ÷EUR/USD |

**Critical pricing discipline — unit basis errors are the leading cause of RM overstatement:**
- Ferroniobium prices are quoted as $/kg of **alloy** (e.g. $26/kg FeNb containing 65% Nb) — NOT $/kg of pure Nb metal. The 2C1385 calibration case found a 1.84× overstatement from conflating these two units.
- FeZr is typically 70–80% Zr by weight. Using zirconium sponge/metal price instead of FeZr alloy price overstates Zr cost by 3–5×.
- For each price used: state the source name, URL, publication date, quoted unit, and conversion applied explicitly. If two sources conflict >20%, prefer the government/statistical authority (USGS MCS, Eurostat) over market intelligence reports.

**4. Calculate alloy raw material cost per kg.**

```
Alloy RM cost (€/kg) = Σ [ wt%(element) × price(€/kg element) ]
```

Identify the dominant cost driver (element with highest % contribution to alloy RM cost) — this is where model error is most consequential. Compute ±20% sensitivity on the dominant element to define the RM cost range.

---

#### Step 2.5b — Map the full manufacturing process chain

For components where CF2 (multi-step transformation) is triggered:

**1. Enumerate all process steps in sequence.** For each step, capture:
- Step name and description
- Equipment type (batch vs. continuous; automated vs. semi-manual)
- Approximate throughput (units/h or kg/h at production volume)
- Whether captive (done by supplier in-house) or outsourced

Example — nanocrystalline wound coil (2C1385):
```
Step 1  Alloy melting         Vacuum induction furnace; batch; captive
Step 2  Melt-spinning         Chill wheel; ribbon 15–20µm; high-throughput continuous; captive
Step 3  Ribbon slitting       Precision blade; inline with Step 2
Step 4  Core winding          Automated mandrel; spot-weld; captive
Step 5  Crystallisation anneal  Continuous belt furnace; 540–570°C; captive
Step 6  Housing               Plastic carcasse + foam ring; press-fit
Step 7  Electrical test       100% BH measurement; automated
```

**2. Identify batch vs. continuous process — this is the most common source of 4–10× processing cost errors:**
- Continuous furnaces (annealing, plating lines) process hundreds of kg/h → amortization per unit is far lower than batch assumptions
- Melt-spinning lines at industrial scale run at 300–600 kg/h ribbon throughput — amortization per kg of ribbon is €0.05–0.15, not €0.20–0.50 as a batch assumption would produce
- Always verify: at the production volume on the PPE file, is the process batch or continuous? Volume >500k units/yr almost always implies continuous or high-throughput automated

**3. Derive process cost per unit for each step** using Rule C6 (machine-only, with labor and energy separate).

**4. Compound overall yield across all steps.** At high volume with automation, realistic overall yield is 93–97%. Flag if an assumed yield seems inconsistent with production volume.

---

#### Step 2.5c — Verify key physical parameters

When CF4 (low-confidence dominant input) is triggered:

**Mass / dimensions:**
- If drawing states an **assembly** volume → core-alone is smaller. Estimate by subtracting approximate volumes of bobbins, winding, and housing.
- Build a sensitivity table across plausible dimension ranges and show the SC impact per dimension scenario.
- This becomes the explicit dimension uncertainty disclosure in the model.

**Alloy composition:**
- If exact grade is unconfirmed, use the canonical composition for that alloy family and state it explicitly.
- Compute sensitivity: ±20% on the most expensive constituent weight fraction.

---

#### Step 2.5d — Verification checklist before proceeding to Step 3

```
=== STEP 2.5 VERIFICATION CHECKLIST ===

Material decomposition:
  [ ] Each constituent ≥5wt% has a price from a named, dated source
  [ ] Price unit basis confirmed: alloy vs. pure metal; $/kg vs. $/t
  [ ] Dominant cost driver identified; ±20% sensitivity range computed
  [ ] Alloy family confirmed from primary source, not assumed from brand name

Process chain:
  [ ] All steps from raw material to finished component enumerated
  [ ] Captive vs. outsourced identified for each step
  [ ] Batch vs. continuous identified for each energy-intensive or capital-intensive step
  [ ] Yield at production volume (not lab yield) used

Physical parameters:
  [ ] If assembly volume used: core-alone volume estimated separately
  [ ] Dimension sensitivity table built if geometry uncertain
  [ ] Weight confidence tier stated

Pricing cross-checks:
  [ ] If comparable open-market products exist (Chinese commodity equivalents):
      gap between their price/unit and the model RM cost explained

Open items requiring supplier confirmation:
  [ ] List each uncertain dimension / composition / yield with its €/unit and % SC impact
```

Any unchecked item becomes a named open item in Step 4.5 Sanity Gate and Step 5.5 Self-Critique.

---

#### Step 2.5e — Deep-Dive Summary block (output in chat before Step 3)

```
=== STEP 2.5 DEEP-DIVE SUMMARY — [component ID] ===

Alloy / Material:
  Family:         <e.g. FINEMET Fe-Si-B-Nb-Cu | NANOPERM Fe-Zr-B-Cu>
  Composition:    <at% — confirmed from [source] / assumed from canonical spec>
  wt% breakdown:  Fe X% | Nb/Zr Y% | Si Z% | B W% | Cu V%
  RM cost/kg:     €X.XX/kg alloy
  Dominant driver: [element] = X% of alloy RM cost
  RM cost/unit:   €X.XX (base mass X.Xg, yield-adjusted at X%)
  Price unit basis confirmed: YES — <source, date, unit, conversion>

Process chain:
  Steps:          <numbered list>
  Captive:        <which steps>
  Key insight:    <e.g. "Step 5 annealing is continuous not batch → 4× lower unit cost">
  Overall yield:  X% at [volume] units/yr — basis: <automated / assumed>

Physical parameters:
  Mass:           X.Xg — Tier <1/2/3>
  Key uncertainty: <dimension / composition / yield>
  Sensitivity:    ±Xg = ±€X.XX/unit SC (X% of SC estimate)

Bottom-up RM cost (per unit, base case):
  [element | wt% | €/kg | €/unit contribution | % of RM]
  Total alloy RM/unit: €X.XX

Corrections applied (vs. any prior assumption):
  <old value → new value — reason>

Ready for Step 3: YES / NO (if NO: [blocker])
```

---

### Step 3: Benchmark each input (Low / Base / High)

**⚠ PITFALL P1 CHECKPOINT — Region-appropriate factor costs (mandatory before any benchmarking):**

Before reading benchmarks.md, determine the supplier's country from the PPE file (Supplier Country column) and run live web searches for the following time-sensitive parameters. Do NOT copy WEU benchmarks to non-WEU suppliers without verification.

**Mandatory live searches (run at least one per parameter per build):**

| Parameter | Supplier in EU/DE/FR | Supplier in Vietnam/SE Asia | Supplier in China | Search query template |
|---|---|---|---|---|
| Labor rate fully loaded (€/h) | Eurostat lc_lci_lev current year | Baker McKenzie VN wages current year; ILO ILOSTAT VN | ILO ILOSTAT CN coastal/interior | `"[country] manufacturing operator wage [year] fully loaded EUR"` |
| Electricity price (€/kWh) | Eurostat nrg_pc_205 H1 latest | GlobalPetrolPrices.com VN industrial; EVN tariff decision | IEA China industrial electricity | `"[country] industrial electricity price kWh [year]"` |
| Ocean freight (€/unit) | N/A (road) | Freightos FBX11 current week | FBX11 current week | `"FBX11 Asia Northern Europe freight rate [month year]"` |
| Road freight (€/unit) | Transporeon/Upply Road Index | N/A | N/A | `"intra-EU road freight groupage rate [year]"` |
| Steel / wire rod price | Destatis, IMARC, Chemanalyst | Same sources, Asian mill discount | Same sources, CN mill | `"CHQ wire rod price EUR per kg [year]"` |
| Surface treatment | ZVO EU rates | Vietnam/Asia integrated barrel rate | China barrel plating rate | `"zinc barrel plating cost per m2 [country] [year]"` |

**Machine rate derivation — always bottom-up, never from benchmarks.md directly:**

```
Machine rate (machine-only, €/h) =
  [Capex × (1/depreciation_years)] ÷ effective_annual_hours   ← depreciation
  + [Capex × 0.05] ÷ effective_annual_hours                   ← interest (5%)
  + [Capex × 0.02] ÷ effective_annual_hours                   ← maintenance (2%)
  + [floor_area_m2 × rent_€_per_m2_yr] ÷ effective_annual_hours  ← space
  + [annual_tooling_€] ÷ effective_annual_hours               ← tooling

Reference capex values by equipment class and region:
  Cold header (Chinese OEM, M3–M12):  $50–100k USD → VN/CN base: €2–5/h machine-only
  Cold header (Sacma/Nedschroef EU):  €150–400k   → WEU base: €8–16/h machine-only
  Injection moulder <200t (Engel/Arburg): €80–200k → WEU: €10–20/h; VN/CN: €3–8/h
  Stamping press 200–500t (Schuler):  €300–800k   → WEU: €15–30/h; VN/CN: €5–12/h
```

Benchmarks.md machine hourly rates are retained as **cross-check ranges only** — use them to validate the bottom-up derivation, not as primary inputs.

**After deriving all parameters, run the P1 self-check:**
```
P1 Self-check — Conversion sanity:
  Conversion cost per part = (machine sub-cost + labor sub-cost + energy sub-cost) per unit
                           = (machine_rate × cycle_h) + (labor_rate × ops × cycle_h) + (energy_kWh × price)
  Compare to: rule-of-thumb for this process and country (look up or estimate)
  If Conversion cost > 60% of current purchase price for a commodity part → INVESTIGATE before proceeding
```

For each parameter, derive Low / Base / High values:

- **Material prices** → apply the compound decomposition protocol below, then cite source per constituent element.

**Raw Material — Compound Decomposition Protocol (MANDATORY — applied on EVERY should-cost run, no exceptions):**

**⚠ THIS PROTOCOL IS NOT OPTIONAL.** It applies to every material that is a compound, blend, alloy, resin system, or proprietary formulation — even when the analysis is not flagged as complex. Failure to decompose compound materials is the leading cause of RM cost errors across all should-cost runs.

**Decision gate — apply before every Material bucket build:**

1. **Is the raw material a pure commodity with a direct exchange or index price?** (e.g. copper cathode on LME, virgin steel coil on MEPS, aluminium ingot on LME) → Use the index price directly. No decomposition needed.
2. **Is the raw material a compound, blend, formulation, grade, or proprietary material?** (e.g. a specific resin grade, coated/plated metal strip, BMC/SMC compound, adhesive, alloy ribbon, PVC formulation, or any material with a trade name rather than a commodity designation) → **Decomposition is mandatory.** Execute the full protocol below.

If in doubt, treat the material as a compound and decompose. It is always safer to decompose and find a single dominant constituent than to skip decomposition and use an unverifiable aggregate price.

**Full decomposition protocol — execute in sequence:**

**Sub-step 1 — Identify if the material is a compound and break it into constituent elements.**
- Determine whether the material is composed of multiple elements or components (e.g. a resin + filler + glass fiber; a metal alloy with multiple elements; a compound with base resin + additive package).
- If it is a compound: list ALL constituent elements or fractions, with their material type (e.g. "polyester resin", "calcium carbonate filler", "glass fiber reinforcement").
- Document this identification explicitly in the Pre-Build Reasoning Block and in the Inputs tab Source column.

**Sub-step 2 — Break each constituent down to the most granular element or commodity whose price can be traced through an authoritative, publicly-available price database.**
- Go as granular as needed: if a constituent is itself a blend, decompose it further.
- For each identified constituent, show:
  - (a) **Unit price (EUR/kg or appropriate unit)** — from a named, dated, publicly-accessible source (LME, ICIS, ChemAnalyst, BusinessAnalytiq, USGS MCS, Eurostat, etc.)
  - (b) **Formulation weight % (or volume %)** — from the material datasheet, supplier TDS, academic literature, or industry specification. Cite the source.
- Write one row per constituent in the Inputs tab decomposition sub-block (see Required Excel sub-block layout below for exact format). Each constituent gets its OWN row with its OWN source citation.

**Sub-step 3 — Calculate compound price via SUMPRODUCT of unit price × weight %.**
```
Compound base price (EUR/kg) = Σ [ weight%(constituent_i) × unit_price(constituent_i, EUR/kg) ]
```
Show the weighted average explicitly as "Total" in the decomposition sub-block (Row H in the layout below).

**Sub-step 4 — Factor in conversion cost where applicable (investigate and justify).**
- After computing the raw material sumproduct, determine whether there is a documented conversion cost (i.e., a manufacturing step required to transform the constituent blend into the final compound form — e.g. compounding/extrusion for thermosets, ribbon casting for nanocrystalline alloys, alloying/smelting for specialty metals).
- **Not all compounds have a significant conversion cost.** Before including one:
  - Research whether the conversion is typically integrated into the raw material price (i.e., the market price of the compound already reflects conversion) or charged separately.
  - If conversion is already embedded in market price → do NOT add it again (would be double-counting).
  - If conversion is a genuine additional cost charged separately to the buyer → add it as a % uplift or EUR/kg add-on, with source and justification.
  - Document the decision explicitly: "Conversion cost: [included in market price / €X/kg — source: Y / not applicable — reason: Z]"
- Final compound price = Sumproduct (Sub-step 3) + Conversion cost (if applicable and not already embedded).

**Sub-step 5 — Verify this logic is applied consistently across ALL material inputs in the model.**
- If the model has multiple raw material parameters (e.g. multiple components each with their own material), each one must be individually assessed against this decision gate.
- Do NOT apply decomposition to the first RM parameter and then silently use an aggregate price for subsequent ones.
- Include a one-line decomposition status for each RM parameter in the Sanity-Check Gate output (Step 4.5): "RM1 — decomposed (3 constituents) / RM2 — direct commodity price (LME Cu) / RM3 — decomposed (2 constituents)"

When the raw material is a named compound, blend, alloy, resin system, or proprietary formulation (rather than a pure commodity directly traceable to an exchange price), do NOT use the bulk/aggregated catalogue price directly. Instead:

**Step A — Check for a verifiable direct price first.**
Search for the exact material name (e.g. "AMPAL MPV 7500 S 7035.00 ML 4.1 price EUR/kg") in:
- Supplier published price lists or datasheets (from OneDrive docs or chat uploads)
- Material distributor catalogues (e.g. Brenntag, Univar, Trinseo, BASF)
- Price index databases (BusinessAnalytiq, ChemAnalyst, ICIS, PIE/Plasteurope)

If a verifiable source is found that explicitly states the unit price for that exact compound → use it directly and cite source + URL in column H. Stop here.

**Step B — If no verifiable direct price exists → decompose the compound.**

Decompose the material into its constituent elements down to the most granular level whose price can be traced to a public database or price index.

**Decomposition rules:**
1. **5% threshold**: Only include constituents contributing ≥5% by composition/weight. Constituents below 5% are treated as negligible — assume their cost is diluted/distributed across the key elements and do not model them separately.
2. **Identify each constituent's commodity benchmark price** from public sources (LME, LBMA, ICIS, ChemAnalyst, BusinessAnalytiq, PIE/Plasteurope). Each constituent price must have a source name + URL in the Inputs tab.
3. **Calculate weighted average raw material cost** = Σ (constituent price × composition fraction).
4. **Apply material contribution factor**: The weighted average of raw ingredients is typically only a fraction of the final compound price — the remainder covers the compounding process (mixing, extrusion, additives, process overhead). Use a published industry reference for the material contribution % (typically 35–55% for SMC/BMC thermosets, 45–65% for engineering plastic compounds). Cite the source. Total compound price = weighted ingredient cost ÷ material contribution %.
5. **The calculated compound price IS the unit price used in the model.** This is non-negotiable — the decomposition calculation is the source of truth for the compound price, not any external benchmark.
6. **Cross-check against benchmark** (optional but recommended): After deriving the compound price via decomposition, compare it against a published benchmark (PIE/Plasteurope, ICIS) as a sanity check. If the decomposition result differs from the benchmark by >30%, flag the discrepancy and investigate which constituent price or contribution % is driving it before proceeding. The benchmark is a cross-check only — it does NOT override the decomposition result.
7. **Document the full breakdown** in Tab 2 of the Excel model, in a sub-block directly below the Raw Material line item. The layout must match the reference screenshot exactly — **one row per constituent, each with its own dedicated Source cell**. Never consolidate multiple constituent sources into a single cell.

**CRITICAL — Linking rule (the most common failure mode):**
The "Unit price *" row in the sub-block header (Row B) and the corresponding parameter row that feeds the Calculation tab (RM2) **must both equal the result of the decomposition formula** (= Total weighted avg ÷ Material contribution %). They must NOT be populated from an external benchmark directly. The formula chain must be unbroken:

```
Constituent prices → Weighted avg → ÷ Contribution % → Compound price (Row J)
                                                              ↓
                                          Param row (e.g. Param 1) = same value
                                                              ↓
                                          Calculation tab RM2 = same value
```

If using Excel formulas: Row J "Total raw material price" cell should contain the formula `= weighted_avg_cell / contribution_pct_cell`. Param row Base column should contain `= Row_J_cell`. RM2 in the Calculation tab should reference `= Inputs!Param_row_Base_cell`. No hardcoded values anywhere in this chain.

**Required Excel sub-block layout (enforce this structure row by row):**

```
Row A  | Assumption: "Weightage"     | Item: [material name] | Value: X.XX | Unit: Kg/part | Justification: "As per datasheet"            | Source: [document name]
Row B  | Assumption: "Unit price *"  | Item: [material name] | Value: X.XX | Unit: EUR/kg  | Justification: "As per unit price breakdown below" | Source: —

[blank row]

Row C  | "* Unit price breakdown:" [merged label row]

Row D  [column headers]
       | Material Formulation | Composition | Price | Unit   | Justification                          | Source

Row E  | [Constituent 1 name] | XX%         | X.XX  | EUR/kg | [e.g. "2025 price benchmark in Europe: €X.XX/kg"] | [URL — single URL for this constituent only]
Row F  | [Constituent 2 name] | XX%         | X.XX  | EUR/kg | [e.g. "2025 price benchmark in Europe: €X.XX/kg"] | [URL — single URL for this constituent only]
Row G  | [Constituent 3 name] | XX%         | X.XX  | EUR/kg | [e.g. "2025 price benchmark in Europe: €X.XX/kg"] | [URL — single URL for this constituent only]

Row H  | "Total"              |             | X.XX  | EUR/kg | [weighted avg = Σ(composition × price)]    | —

Row I  | "Material % of total price" |       | XX%   |        | "Typical % of the material portion to the final compound price" | [URL 1 — e.g. renecorp.com/smc.php]
       |                      |             |       |        |                                                                 | [URL 2 — e.g. pieweb.plasteurope.com/...]
       [Note: if two sources for the contribution %, use two separate URL cells stacked in the Source column]

Row J  | "Total raw material price" |        | X.XX  | EUR/kg | [= Total ÷ Material %]                   | —
```

**Critical formatting rules (based on reference screenshot):**
- Row A (Weightage) → Value cell: light green fill
- Row B (Unit price) → Value cell: light pink/rose fill
- Row J (Total raw material price) → Value cell: light pink/rose fill
- Constituent price cells (rows E/F/G) → no special fill (white)
- Total row (H) → no fill, bold label
- Source column: each constituent row has its OWN dedicated URL in the Source cell — never combine URLs from different constituents into one cell
- Composition column: show as percentage (e.g. "30%") not decimal
- The "Material % of total price" row may show two source URLs stacked in the Source cell if two references are used (as shown in the screenshot)
- Column widths: Assumption ~20, Item/Material Formulation ~35, Composition ~12, Price/Value ~10, Unit ~10, Justification ~45, Source ~50

**Which Hager categories require this protocol:**
- PLASTICS/CHEMICALS & PVC | PLASTIC PARTS | THERMOSET PROCESS — BMC, SMC, phenolic, epoxy compounds → always decompose
- PLASTICS/CHEMICALS & PVC | PVC | PVC — PVC compounds → always decompose (resin + plasticiser + stabiliser + filler)
- PLASTICS/CHEMICALS & PVC | PLASTIC RAW MATERIAL | ENGINEERING PLASTICS — filled/compounded grades (GF, GF30, etc.) → decompose if no direct price found
- PLASTICS/CHEMICALS & PVC | CHEMICALS — chemical blends, adhesives, coatings → always decompose
- METALS | COMBINED MATERIAL | BIMETALS — multi-layer strip → decompose by metal layer weights
- Any other category where the material name is a trade name or proprietary grade rather than a standard commodity designation

**Key public sources for constituent prices (Step B):**
- Polyester/melamine/epoxy resins: BusinessAnalytiq (https://businessanalytiq.com/procurementanalytics/index/) 
- Calcium carbonate, silica, talc fillers: ChemAnalyst (https://www.chemanalyst.com/Pricing-data/)
- PVC resin, plasticisers, ABS, PP, PA: ICIS (https://www.icis.com/explore/commodities/chemicals/) or PIE/Plasteurope (https://www.plasteurope.com/)
- Material contribution % for thermosets: Renecorp SMC guide (https://renecorp.com/smc.php), PlastEurope (https://pieweb.plasteurope.com/)
- Metals / copper / silver: LME (https://www.lme.com/en/market-data), LBMA (https://www.lbma.org.uk/prices-and-data/precious-metal-prices)
- **Labor and machine rates** → country-specific manufacturing wage benchmarks (BLS US, Eurostat EU, etc.). Mention basis.
- **Yields, scrap, OEE, cycle times** → process-typical benchmarks from `references/benchmarks.md`.
- **Logistics** → origin–destination lanes; differentiate sea vs. air vs. land.
- **Overheads and Margin** → industry-typical ranges from `references/benchmarks.md`.

**Source every input in column H of the Inputs tab.** For full traceability, column H must contain ALL four elements: (1) source name, (2) source URL, (3) vintage/date, (4) confidence level. Example: `Eurostat lc_lci_lev 2025 | https://ec.europa.eu/eurostat/statistics-explained/index.php?title=Hourly_labour_costs | 2025 est. | High`. For commodity-linked inputs (Cu, Ag, Zn), add: `Live price — verify at [URL] on date of analysis`. If a value is a user or project-team estimate, write: `Project team estimate (Hager procurement team, [date]) | No URL | Confidence: Low — to be validated`. Never fabricate a citation or URL.

**Benchmark vintage discipline (NEW, Punkt 5):**
- Every benchmark used must carry a source AND a date or year in column H
- If `benchmarks.md` lists a value older than 24 months and inflation/market movement matters (labor, energy, commodities), apply a documented adjustment (e.g. "Eurostat 2023 wage + 4%/year escalation = 2026 figure") OR flag as "to be refreshed"
- If a benchmark has no source/date in `benchmarks.md`, mark it "To be validated" in column H — do not pretend it's authoritative

Mark uncertain parameters with "CRITICAL: to be clarified with supplier" in column H.

### Step 4: Build the calculated Excel model

Use the script `scripts/build_should_cost_model.py` as the reference.

**For single components:** standard 3-tab layout (1. Overview & Results, 2. Inputs, 3. Calculation).

**For sub-assemblies:** extended multi-tab layout — one tab per child component + one assembly rollup tab (see Sub-Assembly Workflow Step SA-6). Tab structure:
- One component tab per child (e.g. "W1B0162", "W1B0163") — each is a full 3-section layout (header, spec parameters, should-cost inputs + assumptions) matching the reference WXA450 component tab structure
- Assembly rollup tab (named after the assembly ID, e.g. "WXA450") — rollup grid with cross-tab formulas
- File named: `Should_Cost_{Assembly-ID}_{YYYYMMDD}_v{NN}.xlsx`

**Component tab layout (per child component):**
- Header rows: Should-Cost Model, Part category (Sub-components), Ref no, Material Description, Raw material, Note
- Summary grid (Cost Component | EUR/pcs | % | Details | Spec parameters | Machine parameters)
  - Rows: Material, Conversion, Manufacturing Costs (subtotal), Packaging & Logistics, Overheads, Margin, Should Cost, Total
  - Spec parameter columns: Density, Length, Width, Height, Thickness, Volume, Weight, Ribs+bosses, Scrap, Total (kg/part)
  - Machine parameter columns: Cycle time / Stroke rate, Cavities / Tooling layout, Parts/hour, Press force / etc.
- Full should-cost inputs and assumptions section below the summary grid (same structure as single-component model)

**Assembly rollup tab layout:**
- Header rows: Should-Cost Model, Part category (Assembly), Ref no, Material Description, Raw material (combined)
- Column headers: Cost Component | [Component 1 code] | [Component 2 code] | ... | Assembly [ID] | Percentage
- Quantity row: Qty | [qty1] | [qty2] | ... | 1
- Bucket rows: each cell = component tab value × qty (cross-tab formula)
- Total row: sum of all component totals × respective qty
- Below total: Actual price | Difference (Actual − Should Cost) | Savings %

**Run-ID and Version Discipline:**
- Every Excel model must include in the first component tab header:
  - **Run-ID**: `SC-{Material-ID}-{SupplierShortName}-{YYYYMMDD}-{NN}`
  - **Date**: ISO date `YYYY-MM-DD`
  - **Skill version**: "hager-should-cost-builder v3.21-2026-06"
  - Note: v3.21 adds formula integrity checklist (Σ range discipline), formatting integrity checklist (bucket header vs. data row), dynamic row height for Source/Logic column, and strengthened mandatory compound decomposition protocol (Sub-steps 1–5)
  - **Inputs source**: brief note
- File name: `Should_Cost_{Material-ID}_{SupplierShortName}_{YYYYMMDD}_v{NN}.xlsx`
- On rerun with different inputs, increment NN

**Assumptions Block in each component tab:**
At the top of each component's inputs section, insert the assumptions block before the parameter list.

**Critical rules for the model:**
- Every value in the assembly rollup tab MUST be a cross-tab formula linking to component tabs
- Every value in each component summary grid MUST link to the inputs/calculation section below
- No hardcoded calculated values anywhere
- Font: Arial. Color: blue = hardcoded inputs, black = formulas, green = cross-sheet links

---

### FORMULA INTEGRITY — MANDATORY PRE-SAVE CHECKLIST (enforced on every build)

Formula errors are the most damaging output quality failure — they silently corrupt every downstream result. Before saving any Excel file, verify ALL of the following:

**3. Calculation tab — Σ sum range discipline:**

The single most common formula error is a shifted SUM range — the Σ subtotal row for a bucket accidentally includes its own header row or the Σ row itself, instead of summing only the data rows of that bucket.

**Rule:** For every `_SIGMA_C` row (Σ subtotal), the SUM range MUST start at the first DATA ROW of that bucket and end at the last DATA ROW of that bucket. It must NEVER include the bucket header row or the Σ row itself.

Verification pattern (apply to every bucket):
```
Bucket header row:    N   ← grey bar, no formula here
Data row first:       N+1
Data row ...          ...
Data row last:        N+k
Σ subtotal row:       N+k+1  ← formula must be =E(N+1)+E(N+2)+...+E(N+k)  OR  =SUM(E(N+1):E(N+k))
                               NEVER =SUM(E(N):E(N+k))  — row N is the header, NOT a data row
```

Apply this check to all four buckets: Material, Conversion, Packaging & Logistics — verify start/end row numbers explicitly against the `param_row_map` produced by `build_calc_model()`.

**Cross-sheet formula integrity:**

After building the model, perform a cell-by-cell trace for every formula that references another sheet:
- `3. Calculation` E-column cells: each must reference `'2. Inputs'!F{row}` where `row` matches the exact Excel row the parameter was written to (from `param_row_map`). Never hardcode an offset — always derive from the row map.
- `1. Overview & Results` C-column cost-build rows: each must reference `'3. Calculation'!E{row}` where `row` matches the exact row of the calc item (from `calc_row_map`). Never guess a row number.
- Subtotal formulas in Calculation (e.g. `Manufacturing Costs = E{mat_sigma_row} + E{conv_sigma_row}`): verify both addend rows exist in `calc_row_map` before writing the formula.

**Python enforcement pattern (add to build script after writing all rows):**

```python
# After build_calc_model() returns param_row_map and calc_row_map:
# Spot-check: print the Σ row formula for each bucket and verify range
for key in ['Σ Material', 'Σ Conversion', 'Σ Packaging & Logistics']:
    sigma_row = calc_row_map.get(key)
    if sigma_row:
        cell = ws3.cell(sigma_row, 5)
        print(f"  {key} @ row {sigma_row}: formula = {cell.value}")
```

If the printed formula includes the bucket header row → the range is wrong. Fix by incrementing the start row by 1.

---

### FORMATTING INTEGRITY — MANDATORY PRE-SAVE CHECKLIST (enforced on every build)

Formatting errors make the model look unreviewed and confuse the reader about the cost structure.

**2. Inputs tab — bucket header vs. data row distinction:**

Every row in the Inputs tab is EITHER a bucket header OR a data row. The classification is binary — no exceptions.

| Row type | Trigger condition | Required formatting |
|---|---|---|
| **Bucket header** | The item is a STRING (bucket name) in the `inputs` list | Grey fill across cols B–H; bold font; NO Low/Base/High values |
| **Data row (parameter)** | The item is a TUPLE `(num, param, unit, low, base, high, source)` | NO fill (white); col B = number (bold); col C = parameter name; Low/Base/High in E/F/G |

**The three most common misclassification errors observed in production:**

1. **Data row formatted as header (grey + bold):** Happens when a parameter tuple is accidentally processed through the header path. Fix: in `build_calc_model()`, the `isinstance(item, str)` branch is the ONLY branch that applies grey fill. If the item is a tuple, grey fill must NEVER be applied regardless of the parameter name.

2. **Bucket header formatted as data row (no grey, no bold):** Happens when a bucket name string is not recognized by `BUCKET_DISPLAY` and falls through to the data-row path. Fix: every valid bucket name must exist in `BUCKET_DISPLAY`. If an unrecognized string appears in `inputs`, raise a ValueError rather than silently writing it as a data row.

3. **Section header row in Calculation tab misclassified:** Section header strings (e.g. `'  1. Material'`, `'  2. Conversion'`) must always receive `apply_sect()` grey fill and bold font. Data rows (tuples) must always receive `NO_FILL`. The `isinstance(item, str) and item != '_BLANK'` check is the gate — do not modify this gate.

**Validation guard (add to build script):**
```python
for item in inputs:
    if isinstance(item, str):
        assert item in BUCKET_DISPLAY or item == 'Reference Data (fixed)', \
            f"Unrecognized bucket name '{item}' — add to BUCKET_DISPLAY or fix the inputs list"
```

**2. Inputs tab — Source/Logic column (col H) row height:**

The Source/Logic column (col H) frequently contains long citation strings (URLs, benchmark descriptions, full sourcing logic). These must NOT overflow the row or be clipped. Apply dynamic row height to ALL data rows in the Inputs tab:

```python
# After writing all parameter rows in build_calc_model():
ws2.sheet_format.defaultRowHeight = None   # remove fixed default
for r_idx in range(3, ws2.max_row + 1):
    ws2.row_dimensions[r_idx].height = None   # auto-fit — Excel will expand as needed
# Also enable wrap text on col H to ensure text wraps rather than overflows into adjacent cells:
for r_idx in range(3, ws2.max_row + 1):
    ws2.cell(r_idx, 8).alignment = Alignment(wrap_text=True, vertical='top')
```

This must be applied AFTER all row content is written, not before (writing content after setting row height overrides the setting in some openpyxl versions).

---

### Step 4.5: SANITY-CHECK GATE (mandatory, NEW)

**After** the Excel is built and recalculated, **before** producing slide-ready content, run this gate. Output as a clearly-labelled chat block AND embed in Tab 1 as a "Sanity Check" section.

```
=== SANITY-CHECK GATE ===

[1] Reasonability Window (vs. Step 1.5 pre-build estimate)
    Pre-build expected range: <low> – <high> €/unit
    Model Should Cost: <X> €/unit
    Status: green (within range) / yellow (within 20% of range) / red (outside)
    If yellow/red: <root-cause hypothesis and which input to inspect>

[2] Impact Potential
    Current Price: <X> €/unit
    Should Cost: <Y> €/unit
    Impact: <Z>% of current price
    Threshold check:
      < 5%   → red flag (likely model under-estimating cost or supplier already lean)
      5–15%  → green
      15–40% → yellow (high impact — verify Material and Conversion are not understated)
      > 40%  → red flag (impact unrealistic for established supplier — investigate)
    If Should Cost EXCEEDS current price → red flag: model is likely OVER-estimating. Trigger Rule C1–C5 audit below.

[3] Bucket Split Sanity
    Material:               <X>% of Should Cost — target 10–70%, status green/yellow/red
    Conversion:             <X>% of Should Cost — target 10–60%, status green/yellow/red
    → Manufacturing Costs (Material + Conversion): <X>% — target 50–85%, status green/yellow/red
    Packaging & Logistics:  <X>% of Should Cost — target 1–10%, status green/yellow/red
    Overheads:              <X>% of Should Cost — target 5–20%, status green/yellow/red
    Margin:                 <X>% of Should Cost — target 5–20%, status green/yellow/red
    If any red: <which assumption or benchmark drives it>

[4] Calibration Rule Checks (mandatory — answer all five)
    C1 — Cavities derived from volume (not drawing complexity)?
         Annual volume: <X> units/yr → Expected cavities: <Y> | Assumed: <Z> | Status: OK / FLAG
    C2 — Machine rate matches part size and cavity count?
         Process: <X> | Part size: <Y> | Cavities: <Z> | Rate used: <EUR/h> | Expected class: <range> | Status: OK / FLAG
    C3 — Assembly labor justified by drawing evidence?
         Evidence of separate assembly step: YES (describe) / NO → Assembly labor: <EUR/unit> | Status: OK / FLAG
    C6 — Machine rate is machine-only (not all-in) within Conversion?
         Machine sub-rate used: €<X>/h | Labor sub-cost: €<Y>/h | Energy sub-cost: €<Z>/h
         Total Conversion/h: €<sum>/h | Expected for process+country: €<range>/h
         Double-count check: machine rate contains NO embedded labor or energy? YES / NO | Status: OK / FLAG

    P1 — Factor costs region-appropriate (Pitfall P1 check)?
         Supplier country: <X>
         Labor rate source: <name, vintage> | WEU proxy used? YES → FLAG / NO → OK
         Machine rate: bottom-up derived? YES / NO | WEU benchmarks.md direct copy? YES → FLAG
         Energy price: country-specific source? YES / NO | Status: OK / FLAG
         Surface treatment: region-appropriate rate? YES / NO | Status: OK / FLAG

    P2 — Per-supplier models (Pitfall P2 check)?
         Number of distinct suppliers found: <N>
         Number of separate models built: <N>
         Match: YES → OK / NO → FLAG (explain why single model was built instead)
```

[4] Historical Comparison (from Step 0c priors, if available)
    Prior model: <ID or name> — Should Cost <X> €/unit, Material share <Y>%
    Current model: Should Cost <X> €/unit, Material share <Y>%
    Consistency: yes / no / mixed
    If no: <why the difference is justified>
    If no priors: "No comparable historical model available — sanity check based on benchmarks only"

[5] Pre-Build Hypothesis Validation
    Cost-driver hypothesis from Step 1.5: <bucket X dominant, bucket Y second>
    Actual result: <bucket A dominant, bucket B second>
    Match: yes / no
    If no: <was hypothesis wrong, or is model off?>

Overall Sanity Status: GREEN / YELLOW / RED
Action: <proceed / re-check input X / hold for user clarification>
```

**Rules:**
- If overall = RED → do not produce slide output. Report findings to user and pause for fix.
- If overall = YELLOW → produce slide output BUT flag the issue prominently in Block F (Key Insights).
- If overall = GREEN → proceed.

### Step 5: Produce slide-ready content (Excel handover + chat blocks)

After sanity gate passes, produce **both** the Slide Values Excel file AND the chat blocks. The Excel file is for the graphics team; the chat blocks are for case-team review.

#### Step 5a — Build Slide Values Excel (mandatory)

Create: `{Material-ID}_SlideValues.xlsx`

Read `references/slide_output_format.md` for the complete specification. Key rules:

**File structure — 4 tabs only (NO Instructions tab):**
- `Slide 1 - Cover`
- `Slide 2 - Cost Build`
- `Slide 3 - Inputs` (third tab — note: named Slide 3, not Slide 4)
- `Slide 5 - Sensitivity`

**Critical formatting rules (must match reference exactly):**
- Tab title in A1: bold, format `Slide N — Description` (em-dash, not hyphen)
- Column headers: fill `00003755` (navy blue), white bold font
- Section headers (waterfall label, key results label): fill `00D9E1F2` (light blue), bold
- Bucket separator rows in Slide 4: fill `00D9E1F2`, bold, col A only, ALL CAPS
- ALL values in col C are bold
- In Slide 4, Base (col F) is bold; Low (col E) and High (col G) are not bold
- Sensitivity SC values (col E): bold, numfmt `#,##0.00`
- Waterfall values and price values: numfmt `#,##0.00`

**Slide 2 impact potential tile format:** `€{Xk} p.a. ({X.X}%)` as a plain string (not a number).

**Slide 4 — parameter consolidation rule:** If the Inputs tab has multiple rows for the same conceptual parameter (e.g. separate fastener cost rows), consolidate into ONE slide row with summed Low/Base/High. Use shortened display names (max ~50 chars).

**Slide 4 bucket separator labels — exactly these, in this order (ALL CAPS, fill `00D9E1F2`):**
`MATERIAL` → `CONVERSION` → `PACKAGING & LOGISTICS` → `OVERHEADS` → `MARGIN` → `REFERENCE DATA (FIXED)`

**NEVER use these old labels:** `QUALITY AND PACKAGING` / `QUALITY & PACKAGING` / `LOGISTICS` / `SG&A AND MARGIN` / `SG&A` / `COGS`

See `references/slide_output_format.md` Tab 3 for a concrete row-by-row example.

**Slide 5 — no Key Insights section.** Key Insights go in the chat blocks (Step 5b) only — not in the Excel.

**Verification (mandatory):**
- Material + Conversion + Packaging & Logistics + Overheads (incl. SG&A) + Margin = Should Cost (±€0.01)
- Should Cost + Impact Potential = Current Price (±€0.01)
- Impact tile string matches Volume × Impact / 1000 and Impact% calculation

#### Step 5b — Produce chat blocks (review summary)

After the Slide Values Excel is built, output the same content as readable chat blocks for the case team to scan and sanity-check before handover to graphics:

**Block A — Cost Build (waterfall values)**
Rounded €/unit values in waterfall order, 2 decimals:
Material → Conversion → Manufacturing Costs (subtotal) → Packaging & Logistics → Overheads (incl. SG&A) → Margin → Should Cost (subtotal) → Impact Potential → Current Price

**Block B — Header info bar**
Hager Company Name (purchasing entity), Material ID, Material Description, Unit of Measure, Annual Volume, Annual Spend, Current Average Price, Supplier Name, Purchasing Group, Purchasing Category, Product Family, Material Group — formatted for the top bar of the slide. Always state the assumed freight lane alongside the entity name.

**Block C — Key result tiles**
Current Price | Benchmark Price (= Should Cost) | Impact potential (annual € k).

**Block D — Input table**
Numbered list grouped by bucket, formatted Low / Base / High with units. Standard formatting (€/kg with 2 decimals, percentages as "10.0%", currency with thousand separators).

**Block E — Sensitivity tornado**
Top 5 input parameters by impact range on Should Cost. For each: parameter name, Low / Mid / High €/unit Should Cost values. Compute by re-running model with one parameter at Low/High while others at Base.

**Block F — Key Insights**
2–4 bullets: dominant variance driver, binary inputs (resolvable without analysis), inputs needing supplier validation. **If sanity gate was yellow, the yellow finding goes here.**

### Step 5.5: SELF-CRITIQUE BLOCK (mandatory, NEW)

Before handing off, output a self-critique block. Max 3 items. This is the structural anti-overconfidence check.

```
=== SCHWACHSTELLEN-SELBSTEINSCHÄTZUNG ===

Die 3 angreifbarsten Punkte in diesem Modell:

1. <Punkt> — <warum unsicher> — <wie zu härten> (e.g. "Material-Anteil 47% basiert auf 1.4301 Annahme; falls 1.4404, +6% Material → kompletter Material-Block bewegt sich um 8%; härten durch Drawing-Validierung")
2. <Punkt>
3. <Punkt>

Likely supplier counter-arguments:
- <what would the incumbent supplier likely argue in a negotiation conversation>
- <which two inputs would they flag as too aggressive>

Manufacturing-Engineer view:
- <was würde ein erfahrener Fertigungsingenieur am Cost-Build kritisieren>
```

**Rules:**
- Max 3 weak points — forces prioritisation
- Must name a concrete value (€/% impact), not a vague concern
- "All assumptions are validated" is not allowed as an output — there is always SOMETHING to critique

### Step 6: NEGOTIATION LEVERS BLOCK (mandatory, NEW)

The actual purpose of the Should-Cost is the supplier negotiation. Output this block as the final slide-ready content piece.

```
=== NEGOTIATION LEVERS ===

Top 3 Verhandlungs-Hebel (operativ angreifbar):
1. <Parameter> — aktueller Wert <X>, Should-Cost-Wert <Y>, Delta <Z €/Stk>
   Verhandlungshebel: <e.g. "Material-Yield 65% statt 50% — Lieferant kann Nesting-Optimierung zeigen">
   Erwartete Lieferanten-Antwort: <typischer Einwand>
   Gegenargument: <how BCG/Hager team would argue the point>

2. <Parameter> — …
3. <Parameter> — …

Nicht verhandelbar (Markt/Floor):
- <Parameter>: <warum nicht verhandelbar — z.B. Edelstahl 1.4301 globale Marktnotierung>
- <Parameter>: <warum nicht — z.B. Mindestmarge für DE-Mittelständler>

Höchster Information-Gain durch Lieferanten-Frage:
- Eine einzige Frage an den Lieferanten, die das Modell am stärksten schärft:
  "<konkrete Frage>"
  Warum: <welcher Input würde aufgeklärt, welche Range würde sich verengen>
```

**Rules:**
- Genau 3 Hebel — nicht mehr, nicht weniger
- Jeder Hebel mit konkretem €-Impact pro Stück
- Mindestens 2 nicht-verhandelbare Items aufzeigen (Realitäts-Disziplin)
- Genau 1 Lieferantenfrage mit höchstem Information-Gain

### Step 7: Hand off

End with:
- File link(s) to **calculated model(s)** — one per supplier: `Should_Cost_{Material-ID}_{SupplierShortName}_{YYYYMMDD}_v{NN}.xlsx`
- File link(s) to **slide values Excel(s)** — one per supplier: `{Material-ID}_SlideValues.xlsx`
- **Cross-supplier comparison table** (if multiple suppliers):

| Supplier | Country | Volume | Current Price | Should Cost (base) | Impact/unit | Annual Impact | Sanity |
|---|---|---|---|---|---|---|---|
| [Supplier A] | [country] | [vol] EA/yr | €X.XX | €Y.YY | €Z.ZZ (+X%) | €Nk | GREEN/YELLOW/RED |
| [Supplier B] | [country] | [vol] EA/yr | €X.XX | €Y.YY | €Z.ZZ (+X%) | €Nk | GREEN/YELLOW/RED |

- Open items / assumptions per supplier that need supplier or project-team validation

## Reference files

- `references/bucket_inputs_by_process.md` — Input parameter sets per process. Read in Step 2.
- `references/benchmarks.md` — Industry-typical ranges with source/vintage per benchmark. Read in Step 3.
- `references/output_format_spec.md` — Exact calculation model layout. Read in Step 4.
- `references/slide_output_format.md` — Slide values Excel layout (per PPT slide). Read in Step 5a.

## Assets

- `assets/input_template_empty.xlsx` — Legacy empty input template (v1 layout). Use only as fallback when the user has no OneDrive folder and no chat uploads. The v2 layout (Run-ID block, Assumptions block, Sanity section) is generated fresh by the build script — the empty template is not used in the standard Material-ID-First workflow.
- `assets/reference_model_plate.xlsx` — Hager reference model (v1 layout). Use as structural reference for the 3-tab pattern (Overview / Inputs / Calculation), formulas, and color coding. Do not modify the reference file.

## Scripts

- `scripts/build_should_cost_model.py` — Reference implementation. Adapt input parameter list per material; keep layout and formula structure intact.

## Style and tone (BCG context)

- German or English per user preference. Default to language of current message.
- Top-down: lead with Should Cost, Impact %, annual impact, Sanity status. Detail follows.
- Source every number with vintage/date. Flag uncertain values with "To be clarified", "Assumption:", or "Unsicherheit:".
- No fabricated citations. Project-team estimate → say so.
- No emojis. Dense structured bullets over prose. Tables for comparisons.

## Failure modes to avoid

- Skipping Step 1.5 (Pre-Build Reasoning) or Step 4.5 (Sanity Gate) or Step 5.5 (Self-Critique) — these are mandatory structural anti-overconfidence checks.
- Producing slide output when sanity gate is RED.
- Inventing weights, volumes, prices, or supplier identities not in source documents.
- Proceeding when OneDrive material folder is empty or missing.
- **Proceeding when Spend Data row is missing without explicit user-provided manual override values** — and without marking those values as MANUAL OVERRIDE in both Excel files.
- **Overriding Hager Spend Data Volume/Spend/Current Price with values from documents, chat messages, or estimates** — these three fields come only from HAGER PPE 2025.xlsx. Discrepancies are noted in chat but never override.
- Skipping the second Excel file (slide values handover for graphics team) — produces TWO Excel files per supplier, not one.
- Using Filesystem MCP to read binary files (PDF, XLSX) — it returns raw bytes. Use M365 MCP for OneDrive; chat-upload + Python for local parsing.
- Using a benchmark from `benchmarks.md` without checking its vintage/source.
- Generating more than 3 critical assumptions, more than 3 self-critique points, more or fewer than 3 negotiation levers — discipline guards against bloat.
- Changing the 5-bucket structure (Material, Conversion, Packaging & Logistics, Overheads, Margin) or waterfall order.
- Hardcoding calculated values in Excel instead of formulas.
- Skipping the source column or Run-ID in the Excel model.
- Mismatched Run-ID between calculation model and slide values Excel — the two files are siblings.
- Producing the PowerPoint file — graphics team owns the PPT.
- Using a parameter set that doesn't fit the manufacturing process.
- **[PITFALL P1] Copying WEU machine rate, labor rate, energy price, or surface treatment rate from benchmarks.md directly to a non-WEU supplier without live research and regional adjustment.** The WEU benchmarks are starting points for EU suppliers; for Asian suppliers they systematically overstate conversion cost by 3–10×. Always run live searches; always derive machine rate bottom-up.
- **[PITFALL P1] Using an all-in machine rate that embeds labor and energy, then adding labor and energy again as separate Conversion sub-components.** The machine rate must be machine-only. Violation causes double-counting within Conversion.
- **[PITFALL P2] Blending multiple suppliers into a weighted average current price and building a single model.** If the PPE file returns rows with different supplier names, build one model per supplier. The blended average is a fiction that hides the real impact opportunity on each supplier individually.
- **[PITFALL P2] Naming the output file without the supplier short name when multiple suppliers exist.** Without supplier name in the filename, files from different suppliers will overwrite each other.
- **[STEP 2.5] Skipping the Complex Component Deep-Dive when ≥2 complexity criteria are triggered.** For components with captive materials, multi-step transformation, or no commodity price reference, benchmark lookup alone produces systematic errors of 2–5×. The 2C1385 toroidal coil calibration case identified a 1.84× Nb price error, wrong alloy family for MAGNETEC, and 4–6× annealing cost overstatement — all of which would have been caught by Step 2.5 before any model was built.

## Version history

- **v3.20 (2026-05-29):** Added 6 mandatory costing accuracy rules (see costing_accuracy_rules.md). No bucket changes. Changes to parameter derivation only: (1) Rule 1: Nesting yield (65% base) + scrap credit (20% base) are now separate explicit inputs; M2 formula subtracts scrap credit `=E4×price−(E4−net_wt)×price×recovery%`; (2) Rule 2: Setup formula uses lot count in numerator divided by annual volume — clearly documented in Inputs col H; (3) Rule 3: Feature-based cycle times — critical vs. non-critical features separated in source notes; welding time sanity check (weld length ÷ speed) documented; (4) Rule 4: All rates from regional rate table (DE supplier = DE rates) — operator base corrected to €62/h (Eurostat 2024+burden), welding cell €108/h, laser €90/h, brake €65/h; (5) Rule 5: Setup = ONE per lot across all machines; surface treatment not double-counted; (6) Rule 6: Scrap recovery rates by metal type documented. New file: costing_accuracy_rules.md with diagnostic checklist.

- **v3.19 (2026-05-29):** Fixed Overview rows 5-11 (general info now written correctly). Fixed cost build to confirmed 9-row structure everywhere it appears — Calculation tab, Overview, Slide 2 waterfall, Slide 3 separators: Material → Conversion → Manufacturing Costs (green) → Packaging & Logistics → Manufacturing Overheads → COGS (green) → SG&A → Margin → Should Cost (green). All Overview C-column cells are live linked formulas. Key Results rows 30-35 all linked. No duplicate rows.

- **v3.22 (2026-06-09):** Three categories of production errors corrected based on DS Smith 5T025500 output review. **(1) Formula integrity:** Added mandatory FORMULA INTEGRITY pre-save checklist (Step 4) documenting the Σ sum-range discipline — the Σ subtotal row for each bucket must start at the first DATA ROW, never the bucket header row (which causes a one-row upward shift producing wrong subtotals). Cross-sheet formula trace rules now explicit: Calculation E-column formulas must derive row numbers from `param_row_map`, never hardcoded offsets; Overview C-column formulas must derive from `calc_row_map`. Python spot-check pattern added. **(2) Formatting integrity:** Added mandatory FORMATTING INTEGRITY pre-save checklist (Step 4) with explicit binary classification rule (bucket header = string → grey fill; data row = tuple → no fill). Three most common misclassification errors documented with root causes. Validation guard code snippet added. **Dynamic row height** added for Inputs tab Source/Logic column (col H): `row_dimensions[r].height = None` + `wrap_text=True` applied after all content is written — prevents cramped/clipped text in long sourcing cells. **(3) Compound decomposition protocol:** Strengthened "Raw Material — Compound Decomposition Protocol" from optional/conditional to **MANDATORY on every build**. Added decision gate (pure commodity vs. compound) and five explicit sub-steps: (Sub-step 1) identify if compound and break into constituents; (Sub-step 2) trace each constituent to granular publicly-available price database with unit price + weight% cited per constituent; (Sub-step 3) SUMPRODUCT of unit price × weight% to derive compound price; (Sub-step 4) factor in conversion cost only if documented and not already embedded in market price; (Sub-step 5) verify protocol applied to ALL RM parameters in model, with per-parameter status in Sanity Gate.

- **v3.21 (2026-06-03) ✓ CONFIRMED:** Three bug fixes applied to `build_should_cost_model.py`. (1) **Formula errors in Calculation tab**: `EXAMPLE_CALCULATIONS` was using a 7-bucket structure with a COGS subtotal and stale row references for Packaging & Logistics (F25/F26 → correct F26/F27), Overheads (wrong base row), Margin (referenced COGS base instead of Mfg Costs + P&L + Overheads), and SHOULD COST formula. Rewrote to correct 5-bucket structure: Material → Conversion → Manufacturing Costs (subtotal) → P&L → Overheads → Margin → SHOULD COST = E20+E25+E28+E31. COGS subtotal fully removed. (2) **Formatting inconsistencies in Calculation tab**: `_SIGMA_C` formula cells were `sz=11` while all other cells were `sz=10`, causing uneven row heights. `_SUBTOTAL_B` label boldness was conditioned on name == 'SHOULD COST' instead of always bold. `_SIGMA_B` Impact % was `sz=11`. Fixed: all Calculation content cells normalized to `sz=10`; subtotal labels always bold; left alignment explicitly set on all label cells. (3) **SlideValues waterfall mismatch**: Slide 2 waterfall contained 11 rows with COGS, Manufacturing Overheads, and SG&A as separate rows, contradicting the fixed 5-bucket structure. Fixed to 9-row waterfall: Material / Conversion / Manufacturing Costs / Packaging & Logistics / Overheads / Margin / Should Cost / Impact Potential / Current Price. `EXAMPLE_SV_DATA` keys updated (`pl_eur`, `overheads_eur`) with backward-compat fallback to old keys. `EXAMPLE_INPUTS` merged Manufacturing Overheads + SG&A into single `Overheads` bucket (row 28–29). BUCKET_SEP/BUCKET_H maps updated: `Overheads` is now the canonical name; legacy names map to it. Key Result Tiles row adjusted from 28→26 to follow the shorter waterfall.

- **v3.18 (2026-05-29):** New 6-bucket structure with COGS subtotal. Bucket order: Material → Conversion → Manufacturing Costs (subtotal) → Packaging & Logistics → Manufacturing Overheads → COGS (subtotal) → SG&A → Margin → SHOULD COST → Impact Potential → Current Price. All Calculation E-column cells are live Excel formulas referencing '2. Inputs'!F{row} — changing any Base value propagates automatically. New Inputs param 22 = Manufacturing overhead rate on conversion base. SG&A now separate bucket from Margin. COGS = Mfg Costs + P&L + Mfg OH. SHOULD COST = COGS + SG&A + Margin. Slide 2 waterfall and Slide 3 separators updated to match new structure.

- **v3.17 (2026-05-29) ✓ CONFIRMED:** Fixed stale post-processing loop that was overwriting correct fills with grey. 3.Calculation tab now verified cell-by-cell against uploaded reference: section headers (grey, theme=0/tint=-0.15), subtotals (light green, theme=6/tint=0.8), blank separator rows (fill_type=None), data rows (fill_type=None). Fills grabbed from template BEFORE the clear loop to preserve theme colors.

- **v3.16 (2026-05-29):** Rewrote 3.Calculation tab writer to match uploaded Calculation.xlsx exactly. Layout: (1) Σ subtotals (Σ Material, Σ Conversion, Σ P&L) have label in col C / col B empty; (2) blank separator rows between sections; (3) major subtotals (Manufacturing Costs, COGS, SHOULD COST) in col B with theme=6 fill; (4) post-SHOULD COST rows (Σ CURRENT PRICE, Impact Potential, Impact %, Annual saving potential) in col B bold; (5) section headers in col B bold with theme=0 fill; (6) regular rows: id in col B bold, element in col C. New item types in EXAMPLE_CALCULATIONS: _SIGMA_C, _SUBTOTAL_B, _SIGMA_B, _BLANK. FMT_EUR/FMT_PCT moved to module level. Template updated to use uploaded Calculation.xlsx.

- **v3.15 (2026-05-29):** Updated all example data to correct 5-bucket structure. Inputs: Material | Conversion | Packaging & Logistics | Overheads | Margin | Reference Data (no Quality & Packaging bucket, no Logistics bucket, no SG&A and Margin bucket — quality costs excluded). Calculations: P1/P2 rows for packaging+freight, O1 for combined overheads, S1 for margin, SHOULD COST = Mfg Costs + P&L + Overheads + Margin. Overview cost build rows 16-24 now show 5-bucket waterfall. Slide 2 waterfall: Material, Conversion, Manufacturing Costs (subtotal), Packaging & Logistics, Overheads (incl. SG&A), Margin, Should Cost (subtotal), Impact Potential, Current Price. Slide 3 separators: MATERIAL / CONVERSION / PACKAGING & LOGISTICS / OVERHEADS (INCL. SG&A) / MARGIN / REFERENCE DATA (FIXED).

- **v3.14 (2026-05-29):** Template-based build — the calculation model is now built by loading the reference file as a template, then replacing cell values/formulas. This preserves all theme fills (theme=4 blue tint on input cells, theme=6 green tint on subtotals, theme=0 grey on section headers), exact font styles, row heights (19.5pt), column widths, and merged cells. Subtotal rows (Manufacturing Costs, COGS, SHOULD COST) in Calculation tab correctly receive theme=6 green fill. Overview subtotal rows receive theme fill from reference. SlideValues always built from scratch (no template needed — uses explicit hex fills). All Calculation E-column cells remain live Excel formulas referencing '2. Inputs'!F{row}.

- **v3.13 (2026-05-29):** Fully linked model — all Calculation and Overview cells now contain live Excel formulas. Architecture: (1) '2. Inputs' F-column holds Base values (hardcoded numbers); (2) '3. Calculation' E-column formulas reference '2. Inputs'!F{row} — changing any Base value propagates immediately; (3) '1. Overview & Results' C-column formulas reference '3. Calculation'!E{row} — the whole chain updates automatically. No hardcoded values in Calculation or Overview tabs. Formula patterns match reference file exactly: M1='2.Inputs'!F5/('2.Inputs'!F6/100), C6=(setup_time×setup_rate×lot_count)/volume, SGA=COGS×rate/100, SHOULD COST=E32+E35+E36. Overview also builds its own subtotals (Mfg Costs=C16+C17, COGS=C18+C19+C20) rather than double-linking to Calculation. Updated Introduction tab text to state the file is completely linked.

- **v3.12 (2026-05-29):** Full rewrite of build script from cell-by-cell read of new reference files (1000126756_SlideValues__003_.xlsx and Should_Cost_1000126756__004_.xlsx). Changes: (1) SlideValues tab names: Slide 1-Cover / Slide 2-Cost Build / Slide 3-Inputs / Slide 4-Sensitivity; (2) Slide 3 A1="Slide 4 — Inputs", col A data="Slide 4" (matches reference); (3) Slide 4 A1="Slide 5 — Sensitivity"; (4) Slide 2 waterfall: 11 rows — Material, Conversion, Manufacturing Costs (subtotal), Quality & Packaging, Logistics, COGS (subtotal), +SG&A, +Margin, Should Cost (subtotal), Impact Potential, Current Price; (5) Slide 3 separators: MATERIAL/CONVERSION/QUALITY AND PACKAGING/LOGISTICS/SG&A AND MARGIN/REFERENCE DATA (FIXED); (6) CalcModel Overview: rows 13/14/16 deleted (no "Cost Build" header row, no blank before headers, no blank before data); (7) CalcModel Inputs: Low/Base/High fill=THEME_FILL_HEX, bucket headers fill=THEME_FILL_HEX; (8) category=Purchasing Category column, sub-category=Product Family column from HAGER PPE 2025; (9) no black fills anywhere; (10) no explicit black font colors.

- **v3.11 (2026-05-29):** Eliminated all black fill occurrences. Three sources found and fixed: (1) calc model table header used fill('000000') → replaced with fill(NAVY); (2) cost build subtotal rows used fill(W_FILL) where W_FILL='00000000' → replaced with NO_FILL; (3) W_FILL constant removed from codebase entirely — '00000000' passed to PatternFill('solid') always renders as black in Excel. Rule encoded in script: only NAVY and LBLUE are valid solid fills; all data rows use NO_FILL (fill_type=None). Verified by scanning every solid-fill cell in both output files.

- **v3.10 (2026-05-29):** Fixed black font color bug. Root cause: Font(color='000000') sets font_color_type='rgb' which renders as explicit black in some Excel themes. Reference uses font_color_type='none' (no color specified) for all data cells — Excel then uses its default theme color. Fix: data_cell() and all data row font calls omit the color argument entirely. Only explicitly-colored cells are: tab titles (navy 00003755), column headers (white 00FFFFFF), and section headers (navy 00003755). Verified by font_color_type comparison against reference for all 4 tabs.

- **v3.9 (2026-05-29):** Fixed critical rendering bug: data cells were written with PatternFill(solid, 00000000) which Excel renders as solid black. Root cause: fill_type="solid" with color 00000000 is opaque black, not white. Fix: data_cell() now uses PatternFill(fill_type=None) — exactly matching reference file. Only section headers (navy/light-blue) retain solid fills. Verified by fill_type comparison against reference.

- **v3.8 (2026-05-29):** Fixed Slide 2 blank rows: row 13 between info bar and waterfall, rows 24–26 between waterfall and key results. Verified by cell-by-cell comparison with reference. Build script tested and produces identical structure.

- **v3.7 (2026-05-29):** Full layout/formatting rewrite derived from cell-by-cell read of reference files. Changes: (1) Slides 1 and 2 use only cols A–C, no D–F; (2) third tab is `Slide 3 - Inputs` not `Slide 4`; (3) Slide 3 has no col I; (4) waterfall is exact 9-row sequence: Material, Conversion, Manufacturing Costs (subtotal), Packaging & Logistics, Overheads (incl. SG&A), Margin, Should Cost (subtotal), Impact Potential, Current Price — no COGS; (5) Slide 3 separator `OVERHEADS (INCL. SG&A)` and `PACKAGING & LOGISTICS`; (6) Slide 3 separators merged A:H; (7) H column supports sub-detail labels e.g. `Conversion — energy`; (8) source column added to every input parameter with real verifiable citations (Eurostat, LME, VDW, Transporeon, Maschinenmarkt, etc.); (9) build script produces testable valid Excel output; (10) exact column widths and merged cell ranges documented.

- **v3.6 (2026-05-29)**: Fixed build script and Slide 4 spec to use correct bucket separators throughout. Added explicit FORBIDDEN separator list (QUALITY AND PACKAGING, LOGISTICS, SG&A AND MARGIN). Added concrete row-by-row Slide 4 example in slide_output_format.md. Rewrote build_should_cost_model.py: EXAMPLE_INPUTS now uses correct bucket headers (Packaging & Logistics, Overheads, Margin), EXAMPLE_CALCULATIONS has correct section headers (3. Packaging & Logistics, 4. Overheads, no COGS), cost_build table in Overview tab matches 5-bucket waterfall, validation guard in build_model() now rejects invalid bucket names at build time.

- **v3.5 (2026-05-29)**: Propagated new 5-bucket structure throughout entire skill document. Updated: Pitfall P1 triple-count language (no separate Machine/Labor/Energy buckets — all inside Conversion); sub-assembly SA-4/SA-5/SA-6 rollup example and component tab rows; pre-build reasoning cost-driver note; Step 2.5 output structure reference; Step 3 benchmarks label; Step 4 component tab row list; sanity gate impact threshold; all C6 rule language. Old "7-bucket" and "Raw Materials / Machine Cost / Labor Cost / Energy Cost / Profit" terminology replaced with "5-bucket" and "Material / Conversion / Packaging & Logistics / Overheads / Margin" throughout.

- **v3.4 (2026-05-29)**: Removed quality costs from model. QA, CoA/certs, batch certificates, FAI amortisation, and incoming inspection are NOT modelled. The Packaging & Logistics bucket contains only packaging materials and freight/logistics. This is a hard constraint — do not add quality cost parameters even if the supplier invoices them separately.

- **v3.3 (2026-05-29)**: Changed fixed cost bucket structure from 6 buckets to 5 input buckets. Old: Material | Conversion | Quality & Packaging | Logistics | SG&A | Margin. New: Material | Conversion | Packaging & Logistics | Overheads | Margin. Key changes: (1) Quality & Packaging and Logistics merged into single "Packaging & Logistics" bucket; (2) SG&A renamed and broadened to "Overheads" covering both SG&A and manufacturing overheads; (3) COGS subtotal removed — waterfall now: Material → Conversion → Manufacturing Costs (subtotal) → Packaging & Logistics → Overheads → Margin → Should Cost; (4) Sanity gate bucket thresholds updated; (5) Slide 4 separator labels updated to PACKAGING & LOGISTICS and OVERHEADS; (6) Introduction tab bucket count updated to 5. All formatting rules from v3.2 preserved.

- **v3.2 (2026-05-29)**: Rewrote output format specs to match exact reference files `Should_Cost_1000126756.xlsx` and `1000126756_SlideValues.xlsx`. Key changes: SlideValues file named `{Material-ID}_SlideValues.xlsx` (no date/version suffix); 4 tabs only (no Instructions tab); tab titles use em-dash; column header fill `00003755`; section header fill `00D9E1F2`; all C-column values bold; Slide 4 Base bold / Low+High not bold; Slide 5 no Key Insights section (chat only); fastener rows consolidated in Slide 4; spend formatted as `€Xk`/`€X.XM`; impact tile as pre-formatted string `€Xk p.a. (X.X%)`. Calculation model: 4 tabs including `0. Introduction`; cost build row labels match reference exactly (incl. `Maufacturing Costs` typo preserved); number format `#,##0.00;[Red]\(#,##0.00\);\–` for Inputs Low/Base/High.

- **v3 (2026-05-28)**: Added Step 2.5 Complex Component Deep-Dive (conditional on ≥2 complexity criteria). Added 6-criterion Complexity Flag assessment to Step 1.5 Pre-Build Reasoning. Triggered by: no commodity price (CF1), multi-step transformation (CF2), captive material supply (CF3), low-confidence dominant input (CF4), unfamiliar part family (CF5), high unit price (CF6). Step 2.5 comprises 5 sub-steps: raw material decomposition (2.5a), process chain mapping (2.5b), physical parameter verification (2.5c), verification checklist (2.5d), and deep-dive summary block (2.5e). Calibrated against 2C1385 toroidal coil case which found: Nb price 1.84× overstated due to unit confusion ($/kg FeNb alloy vs $/kg Nb metal), wrong alloy family for MAGNETEC (NANOPERM not VITROPERM), annealing 4–6× overstated (batch vs. continuous), and core dimensions from assembly volume not core volume. Skill version string updated to `hager-should-cost-builder v3.20-2026-05`.
- **v2 (2026-05-28)**: Added Pitfall P1 (region-appropriate factor costs, machine-rate triple-count fix) and Pitfall P2 (per-supplier models, no blending). Updated Step 0 navigation rules, Step 2 calibration rules (C6), Step 3 mandatory live-research protocol, Step 4.5 sanity gate (C6, P1, P2 checks), Step 7 handoff (cross-supplier table), and Failure modes. Skill version string updated to `hager-should-cost-builder v2-2026-05`.
- **v1 (2026-05)**: Original 7-bucket layout (Raw Materials, Machine Cost, Labor Cost, Energy Cost, Overheads, Packaging and Logistics, Profit). Sub-assembly workflow. Sanity gate, pre-build reasoning, self-critique, negotiation levers blocks.
