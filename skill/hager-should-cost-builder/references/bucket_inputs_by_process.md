# Bucket Inputs by Manufacturing Process

Bucket structure is fixed (Material, Conversion, Packaging & Logistics, Overheads, Margin). Parameters inside each bucket adapt to the manufacturing process. Pick the right column for the material's process.

## Universal parameters (always include)

| Bucket | Parameter | Unit |
|---|---|---|
| Material | Raw material price | €/kg or €/unit |
| Material | Unit weight or units per part | g or # |
| Material | Scrap rate / yield | % |
| Material | Purchased components (fasteners, inserts, etc.) | €/unit |
| Conversion | Machine/process rate | €/h |
| Conversion | Cycle time / process time | s or min |
| Packaging & Logistics | Packaging cost per unit | €/unit |
| Packaging & Logistics | Freight per receiving lane | €/unit |
| Overheads | SG&A rate on manufacturing base | % |
| Overheads | Manufacturing overhead rate (if separate) | % |
| Margin | Supplier margin | % |
| Reference (fixed) | Annual volume | units/yr |
| Reference (fixed) | Current price (weighted avg) | €/unit |

## Process-specific Conversion parameters

### Thermoforming (reference case: Plate 12L)

- Machine hourly rate (€/h)
- Operator rate fully loaded (€/h)
- Cavities per tool (#)
- Cycle time (s)
- Overall Equipment Effectiveness (%)
- Operators per machine (#)
- Energy cost per machine hour (€/h)
- Tool investment (€)
- Tool useful life (years)
- Tool ownership (1=supplier, 0=customer)
- Setup & maintenance per year (€/year)
- Cleanroom premium on Material+Conversion (%) — only if GMP/ISO clean environment required
- Cleanroom toggle (0/1)

### Injection moulding

- Machine hourly rate (€/h) — by clamping tonnage class
- Operator rate fully loaded (€/h)
- Cavities per tool (#)
- Cycle time (s)
- OEE (%)
- Operators per machine (#) — often 0.25–0.5 for highly automated
- Energy cost per machine hour (€/h)
- Tool investment (€) — higher than thermoforming for hot-runner multi-cavity
- Tool useful life (cycles or years)
- Tool ownership (0/1)
- Setup & maintenance per year (€/year)
- Drying / pre-treatment cost (€/unit) — for hygroscopic resins
- Cleanroom premium and toggle (if applicable)

### CNC machining (turning / milling)

- Machine hourly rate (€/h) — depends on machine class (3-axis, 5-axis)
- Operator rate fully loaded (€/h)
- Cycle time per unit (min)
- Setup time per batch (min)
- Batch size (#)
- OEE / spindle utilization (%)
- Operators per machine (#) — often <1 for multi-machine operation
- Tooling consumption (€/unit) — inserts, drills, taps
- Energy cost per machine hour (€/h)
- Programming / NC-prep amortisation (€/unit)
- Surface treatment / deburring (€/unit)
- Heat treatment (€/unit) — if specified

### Stamping / sheet metal forming

- Press hourly rate (€/h)
- Operator rate (€/h)
- Strokes per minute / cycle time
- OEE (%)
- Tool / die investment (€)
- Tool useful life (strokes)
- Tool ownership (0/1)
- Material utilization / blanking yield (%) — critical, often 50–80%
- Secondary operations cost (€/unit) — bending, welding, finishing
- Surface treatment (e.g. zinc plating, e-coating) (€/unit)

### Casting (die casting / investment casting)

- Furnace + machine hourly rate (€/h)
- Operator rate (€/h)
- Cavities per tool (#)
- Cycle time (s)
- Yield / scrap (often higher than moulding) (%)
- OEE (%)
- Tool / die investment (€)
- Tool useful life (shots)
- Tool ownership (0/1)
- Post-processing (€/unit) — trimming, deburring, machining of cast features
- Heat treatment / surface finish (€/unit)

### Electronics / PCB assembly

- SMT line hourly rate (€/h)
- Operator rate (€/h)
- Cycle time per board (s)
- Component placement count (#) — drives time
- First-pass yield (%)
- Rework cost (€/unit)
- Test / functional test cost (€/unit)
- BoM cost (€/unit) — bill of materials value, often dominant
- BoM markup by EMS (%) — typically 5–15%
- Assembly overhead per unit (€/unit)

### Extrusion (plastic profiles, films, tubes)

- Extruder hourly rate (€/h)
- Operator rate (€/h)
- Line speed (m/min or kg/h)
- OEE (%)
- Operators per line (#)
- Energy cost per kg (€/kg)
- Die investment (€) — usually low vs. moulding
- Die useful life (years)
- Yield (%) — startup scrap, profile yield

### Forging

- Press / hammer hourly rate (€/h)
- Operator rate (€/h)
- Cycle time per part (s)
- Strokes / heats per unit (#)
- OEE (%)
- Die investment (€)
- Die useful life (strokes)
- Heating energy (€/unit)
- Trimming and post-machining (€/unit)
- Heat treatment (€/unit)

### Welded subassemblies (sheet-metal assemblies)

Hybrid process — combines per-component sheet-metal manufacturing (laser cutting + bending + stamping) with assembly operations (welding, joining, fastening). Build the cost in two layers:

**Layer 1 — Per-component cost (apply for each child part in the BOM):**

For each sheet-metal child component:
- Material grade and €/kg (e.g. stainless 1.4301, 1.4404, aluminum 5052)
- Sheet thickness (mm) and blank size (mm × mm)
- Material utilization / nesting yield (%) — critical, typically 55–80%
- Laser cutting hourly rate (€/h)
- Cutting time per part (s) — drives by perimeter + piercing
- Bending: press brake hourly rate (€/h), bends per part (#), setup amortisation
- Deburring / edge finish (€/unit)
- Surface treatment if applied (electropolishing, passivation) (€/unit or €/m²)

For each fastener / hardware item in the BOM:
- Unit cost (€/PC)
- Quantity per assembly

**Layer 2 — Assembly cost:**

- Welding method: TIG / MIG / spot / laser — affects rate
- Welding cell hourly rate (€/h) — manual TIG €35–70/h, robotic €70–140/h DE
- Total weld length per assembly (mm) or weld points (#)
- Weld speed (mm/min) — manual TIG ~150 mm/min, robotic 300–600 mm/min
- Operator rate fully loaded (€/h)
- Fixture / jig amortisation (€/unit) — typically minor for low-volume
- Rivet-nut / blind-rivet press-in operation (€/unit) — count fasteners × time
- Post-weld cleaning / pickling / passivation (€/unit) — relevant for stainless food/pharma
- Final inspection / leak test if applicable (€/unit)

**Rollup approach in Calculation tab:**
- Material bucket = Σ (child component material costs) + Σ (fastener costs)
- Conversion bucket = Σ (child component conversion: cutting + bending + finishing) + assembly cost (welding + fastener insertion + cleaning)
- Document each child component as a sub-block in Tab 3 for traceability

## How to use this list

1. Identify the process from the technical documents (drawings often state "thermoformed", "moulded", surface marks like sprue/parting line indicate moulding, machined features indicate CNC). For Sartorius materials: "welded", "geschweißt", "Schweißbaugruppe" + a multi-component BOM = welded subassembly.
2. Pick the matching parameter set above.
3. Add universal parameters.
4. If the material involves multiple processes (e.g. machined casting, or welded subassembly with multiple sheet-metal children), include parameters from both with a comment. For welded subassemblies always use Layer 1 + Layer 2.
5. If the process is not listed, default to the closest analog and flag the assumption explicitly in the Source column of the Inputs tab.

## Special cost positions (add when relevant)

- **GMP / FDA / ISO 13485 validation overhead** — applies to medical, pharma, food contact. Either as % premium on Material+Conversion or as €/unit. Toggle 0/1.
- **R&D / Engineering amortisation** — for highly customised parts, NRE costs amortised over volume.
- **Working capital cost** — usually subsumed in SG&A; separate only if explicitly relevant.
- **End-of-life / recycling fees** — relevant in regulated markets (EU WEEE, RoHS).
