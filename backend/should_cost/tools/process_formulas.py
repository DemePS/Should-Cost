"""Typed, hardcoded CalcLine builders — one tool per costing rule or per manufacturing
process family in references/bucket_inputs_by_process.md, each matching that process's
own parameter set and combination logic exactly. Exposed as tools to the
propose_parameters Agent (should_cost/tools/model_client.py) so the model calls these
for the cases they cover instead of hand-writing the CalcLine bookkeeping (id_code
uniqueness, forward-only line_refs, contributes_to_bucket_total) itself.

Each function is correct by construction: there is no formula for the model to get
wrong here, only parameter numbers to supply correctly — this directly prevents the bug
classes found by hand while building the generic CalcLine path (a helper line silently
double-counted into a bucket total; a cost line re-deriving an intermediate value
instead of referencing the line that already computed it; Rule 2's setup-cost formula
missing lot count from the numerator).

Coverage (one tool per row below; the shared cycle-time formula covers three process
families that share the identical "machine + labor + energy, OEE- and cavity-adjusted"
structure in bucket_inputs_by_process.md):

| Tool | Rule / process(es) |
|---|---|
| build_nesting_yield_material_calc_lines | Rule 1 — nested/laser-cut sheet metal material |
| build_lot_based_setup_cost_calc_line | Rule 2 — generic lot-count-in-numerator setup cost |
| build_cycle_time_machine_conversion_calc_line | Thermoforming / injection moulding / die casting Conversion |
| build_batch_setup_cost_calc_line | CNC machining — batch-size-based setup (Rule 2 variant) |
| build_cnc_machining_calc_line | CNC machining — machine+operator+tooling |
| build_stamping_conversion_calc_line | Stamping / sheet metal forming Conversion |
| build_extrusion_conversion_calc_lines | Extrusion Conversion (per-kg, then scaled by weight/yield) |
| build_forging_conversion_calc_line | Forging Conversion |
| build_electronics_assembly_calc_lines | Electronics / PCB assembly (BoM + process) |
| build_welded_assembly_calc_line | Welded subassemblies — Layer 2 (assembly operation) |

Any process or material not covered by a tool here still falls back to CalcLine's
generic ref/sum/expr construction — see propose_parameters.md. Welded-subassembly Layer 1
(the per-child sheet-metal component) is covered by the nesting-yield and stamping tools
above, applied per child component, per bucket_inputs_by_process.md's own two-layer split.
"""

from __future__ import annotations

from should_cost.models.workflow import CalcLine


def build_nesting_yield_material_calc_lines(
    price_param_number: int,
    net_weight_param_number: int,
    nesting_yield_param_number: int,
    scrap_recovery_param_number: int,
    id_prefix: str,
) -> list[dict]:
    """Rule 1 (costing_accuracy_rules.md): for a laser-cut / nested sheet-metal material,
    Gross weight = Net weight / (nesting yield / 100); Material cost = Gross weight x
    price - scrap credit, where scrap credit = (Gross weight - Net weight) x price x
    (scrap recovery / 100). Never omit the nesting yield — net weight x price alone
    underestimates material consumption.

    Args:
        price_param_number: Parameter number of the raw material price (EUR/kg).
        net_weight_param_number: Parameter number of the net part weight (kg).
        nesting_yield_param_number: Parameter number of the nesting yield (%).
        scrap_recovery_param_number: Parameter number of the scrap recovery rate (%).
        id_prefix: Bucket id-code prefix for the two generated lines, e.g. 'M' produces
            'M1' (gross weight) and 'M2' (material cost) — must not collide with any
            id_code you have already used in this bucket.

    Returns:
        Exactly two CalcLine objects (as dicts), in order: the gross-weight helper line
        (contributes_to_bucket_total=False — it is in kg, not EUR) and the material-cost
        line (contributes_to_bucket_total=True). Copy both, unmodified, into this
        bucket's calc_lines list.
    """
    gross_id = f"{id_prefix}1"
    cost_id = f"{id_prefix}2"
    gross = CalcLine(
        id_code=gross_id,
        label="Gross weight (net / nesting yield) — Rule 1",
        unit="kg",
        kind="expr",
        param_refs=[net_weight_param_number, nesting_yield_param_number],
        expr_template=f"{{p{net_weight_param_number}}}/({{p{nesting_yield_param_number}}}/100)",
        contributes_to_bucket_total=False,
    )
    cost = CalcLine(
        id_code=cost_id,
        label="Material cost net of scrap credit — Rule 1",
        unit="EUR/unit",
        kind="expr",
        param_refs=[price_param_number, net_weight_param_number, scrap_recovery_param_number],
        line_refs=[gross_id],
        expr_template=(
            f"{{{gross_id}}}*{{p{price_param_number}}}"
            f"-({{{gross_id}}}-{{p{net_weight_param_number}}})*{{p{price_param_number}}}*({{p{scrap_recovery_param_number}}}/100)"
        ),
        contributes_to_bucket_total=True,
    )
    return [gross.model_dump(), cost.model_dump()]


def build_lot_based_setup_cost_calc_line(
    setup_time_param_number: int,
    setup_rate_param_number: int,
    lot_count_param_number: int,
    annual_volume_param_number: int,
    id_code: str,
) -> dict:
    """Rule 2 (costing_accuracy_rules.md): Setup cost per unit = (setup time h/lot x
    setup rate EUR/h x lot count per year) / annual volume. The lot count MUST be in the
    numerator — dividing setup time x rate by annual volume directly (omitting lot count)
    is exactly the mistake this rule exists to prevent, and silently produces a setup
    cost far too low for a low-volume material.

    Args:
        setup_time_param_number: Parameter number of setup time per lot (h/lot).
        setup_rate_param_number: Parameter number of the setup hourly rate (EUR/h).
        lot_count_param_number: Parameter number of lot count per year (#/yr) — from
            HAGER PPE order history, never assumed.
        annual_volume_param_number: Parameter number of annual volume (units/yr).
        id_code: This line's id_code, e.g. 'C6' — must not collide with any id_code you
            have already used in this bucket.

    Returns:
        One CalcLine object (as a dict), contributes_to_bucket_total=True. Copy it,
        unmodified, into this bucket's calc_lines list.
    """
    line = CalcLine(
        id_code=id_code,
        label="Setup cost per unit (lot-based) — Rule 2",
        unit="EUR/unit",
        kind="expr",
        param_refs=[
            setup_time_param_number,
            setup_rate_param_number,
            lot_count_param_number,
            annual_volume_param_number,
        ],
        expr_template=(
            f"({{p{setup_time_param_number}}}*{{p{setup_rate_param_number}}}*{{p{lot_count_param_number}}})"
            f"/{{p{annual_volume_param_number}}}"
        ),
        contributes_to_bucket_total=True,
    )
    return line.model_dump()


def build_cycle_time_machine_conversion_calc_line(
    machine_rate_eur_h: int,
    operator_rate_eur_h: int,
    operators_per_machine: int,
    energy_eur_h: int,
    cycle_time_s: int,
    oee_pct: int,
    cavities: int,
    id_code: str,
) -> dict:
    """Thermoforming / injection moulding / die casting Conversion — these three process
    families share the identical structure in bucket_inputs_by_process.md: a machine-only
    rate (Pitfall P1 — never all-in) plus labor plus energy, summed and then divided by
    OEE and the number of cavities, scaled by the cycle time. All five arguments are
    PARAMETER NUMBERS, not raw values.

    Formula: (machine_rate + operator_rate*operators_per_machine + energy_rate) x
    (cycle_time_s / 3600) / (oee_pct/100) / cavities.

    Args:
        machine_rate_eur_h: Parameter number of the machine-only hourly rate (EUR/h) —
            depreciation + maintenance + tooling + space only, per Pitfall P1.
        operator_rate_eur_h: Parameter number of the fully-loaded operator rate (EUR/h).
        operators_per_machine: Parameter number of operators per machine (#, often <1
            for automated cells).
        energy_eur_h: Parameter number of the energy cost per machine hour (EUR/h).
        cycle_time_s: Parameter number of the cycle time (seconds).
        oee_pct: Parameter number of Overall Equipment Effectiveness (%).
        cavities: Parameter number of cavities per tool (#) — derived from annual volume
            and part size per Rule C1, never from drawing complexity alone.
        id_code: This line's id_code, e.g. 'C1'.

    Returns:
        One CalcLine object (as a dict), contributes_to_bucket_total=True.
    """
    line = CalcLine(
        id_code=id_code,
        label="Machine + labor + energy conversion cost (cycle-time process)",
        unit="EUR/unit",
        kind="expr",
        param_refs=[machine_rate_eur_h, operator_rate_eur_h, operators_per_machine, energy_eur_h, cycle_time_s, oee_pct, cavities],
        expr_template=(
            f"({{p{machine_rate_eur_h}}}+{{p{operator_rate_eur_h}}}*{{p{operators_per_machine}}}+{{p{energy_eur_h}}})"
            f"*({{p{cycle_time_s}}}/3600)/({{p{oee_pct}}}/100)/{{p{cavities}}}"
        ),
        contributes_to_bucket_total=True,
    )
    return line.model_dump()


def build_batch_setup_cost_calc_line(
    setup_time_min_per_batch: int,
    setup_rate_eur_h: int,
    batch_size: int,
    id_code: str,
) -> dict:
    """CNC machining — a Rule 2 variant keyed on batch size (the parameter
    bucket_inputs_by_process.md actually gives for CNC) rather than lot count per year:
    Setup cost per unit = (setup time min/batch / 60 x setup rate EUR/h) / batch size.

    Args:
        setup_time_min_per_batch: Parameter number of setup time per batch (minutes).
        setup_rate_eur_h: Parameter number of the setup hourly rate (EUR/h).
        batch_size: Parameter number of the batch size (#).
        id_code: This line's id_code, e.g. 'C2'.

    Returns:
        One CalcLine object (as a dict), contributes_to_bucket_total=True.
    """
    line = CalcLine(
        id_code=id_code,
        label="Setup cost per unit (batch-based)",
        unit="EUR/unit",
        kind="expr",
        param_refs=[setup_time_min_per_batch, setup_rate_eur_h, batch_size],
        expr_template=f"(({{p{setup_time_min_per_batch}}}/60)*{{p{setup_rate_eur_h}}})/{{p{batch_size}}}",
        contributes_to_bucket_total=True,
    )
    return line.model_dump()


def build_cnc_machining_calc_line(
    machine_rate_eur_h: int,
    operator_rate_eur_h: int,
    cycle_time_min: int,
    oee_pct: int,
    tooling_consumption_eur_unit: int,
    id_code: str,
) -> dict:
    """CNC machining (turning/milling) — machine + operator time plus per-unit tooling
    consumption (inserts, drills, taps — already expressed as EUR/unit, so it is added
    directly rather than divided by OEE). Call build_batch_setup_cost_calc_line
    separately for the setup-cost line.

    Formula: (machine_rate + operator_rate) x (cycle_time_min/60) / (oee_pct/100) +
    tooling_consumption.

    Args:
        machine_rate_eur_h: Parameter number of the machine hourly rate (EUR/h).
        operator_rate_eur_h: Parameter number of the fully-loaded operator rate (EUR/h).
        cycle_time_min: Parameter number of the cycle time per unit (minutes).
        oee_pct: Parameter number of spindle/OEE utilization (%).
        tooling_consumption_eur_unit: Parameter number of tooling consumption (EUR/unit).
        id_code: This line's id_code, e.g. 'C1'.

    Returns:
        One CalcLine object (as a dict), contributes_to_bucket_total=True.
    """
    line = CalcLine(
        id_code=id_code,
        label="CNC machine + operator time plus tooling consumption",
        unit="EUR/unit",
        kind="expr",
        param_refs=[machine_rate_eur_h, operator_rate_eur_h, cycle_time_min, oee_pct, tooling_consumption_eur_unit],
        expr_template=(
            f"({{p{machine_rate_eur_h}}}+{{p{operator_rate_eur_h}}})*({{p{cycle_time_min}}}/60)/({{p{oee_pct}}}/100)"
            f"+{{p{tooling_consumption_eur_unit}}}"
        ),
        contributes_to_bucket_total=True,
    )
    return line.model_dump()


def build_stamping_conversion_calc_line(
    press_rate_eur_h: int,
    operator_rate_eur_h: int,
    cycle_time_s: int,
    oee_pct: int,
    secondary_ops_eur_unit: int,
    surface_treatment_eur_unit: int,
    id_code: str,
) -> dict:
    """Stamping / sheet metal forming Conversion — press + operator time (OEE-adjusted)
    plus secondary operations (bending, welding, finishing) and surface treatment,
    already expressed as EUR/unit. Pair with build_nesting_yield_material_calc_lines for
    the Material bucket's blanking-yield cost (the same Rule 1 formula applies — the
    skill's "Material utilization / blanking yield" parameter for stamping IS the
    nesting-yield concept, just named differently for this process).

    Formula: (press_rate + operator_rate) x (cycle_time_s/3600) / (oee_pct/100) +
    secondary_ops + surface_treatment.

    Args:
        press_rate_eur_h: Parameter number of the press hourly rate (EUR/h).
        operator_rate_eur_h: Parameter number of the operator rate (EUR/h).
        cycle_time_s: Parameter number of the stroke cycle time (seconds).
        oee_pct: Parameter number of OEE (%).
        secondary_ops_eur_unit: Parameter number of secondary operations cost (EUR/unit).
        surface_treatment_eur_unit: Parameter number of surface treatment cost (EUR/unit).
        id_code: This line's id_code, e.g. 'C1'.

    Returns:
        One CalcLine object (as a dict), contributes_to_bucket_total=True.
    """
    line = CalcLine(
        id_code=id_code,
        label="Press + operator conversion cost plus secondary ops and surface treatment",
        unit="EUR/unit",
        kind="expr",
        param_refs=[press_rate_eur_h, operator_rate_eur_h, cycle_time_s, oee_pct, secondary_ops_eur_unit, surface_treatment_eur_unit],
        expr_template=(
            f"({{p{press_rate_eur_h}}}+{{p{operator_rate_eur_h}}})*({{p{cycle_time_s}}}/3600)/({{p{oee_pct}}}/100)"
            f"+{{p{secondary_ops_eur_unit}}}+{{p{surface_treatment_eur_unit}}}"
        ),
        contributes_to_bucket_total=True,
    )
    return line.model_dump()


def build_extrusion_conversion_calc_lines(
    extruder_rate_eur_h: int,
    operator_rate_eur_h: int,
    operators_per_line: int,
    line_speed_kg_h: int,
    part_weight_kg: int,
    yield_pct: int,
    id_prefix: str,
) -> list[dict]:
    """Extrusion Conversion — a per-kg process rate (extruder + operators, scaled by line
    speed), then applied to this part's weight and corrected for yield (startup scrap,
    profile yield). Two lines: a per-kg helper (does not itself contribute — it is in
    EUR/kg, not EUR/unit) and the per-part cost that references it.

    Formula: cost_per_kg = (extruder_rate + operator_rate*operators_per_line) /
    line_speed_kg_h; cost_per_part = cost_per_kg x part_weight_kg / (yield_pct/100).

    Args:
        extruder_rate_eur_h: Parameter number of the extruder hourly rate (EUR/h).
        operator_rate_eur_h: Parameter number of the operator rate (EUR/h).
        operators_per_line: Parameter number of operators per line (#).
        line_speed_kg_h: Parameter number of line speed (kg/h).
        part_weight_kg: Parameter number of this part's weight (kg).
        yield_pct: Parameter number of yield — startup scrap / profile yield (%).
        id_prefix: Bucket id-code prefix, e.g. 'C' produces 'C1' (per-kg helper) and
            'C2' (per-part cost).

    Returns:
        Exactly two CalcLine objects (as dicts): the per-kg helper
        (contributes_to_bucket_total=False) and the per-part cost
        (contributes_to_bucket_total=True). Copy both into this bucket's calc_lines.
    """
    per_kg_id = f"{id_prefix}1"
    per_part_id = f"{id_prefix}2"
    per_kg = CalcLine(
        id_code=per_kg_id,
        label="Extrusion conversion cost per kg",
        unit="EUR/kg",
        kind="expr",
        param_refs=[extruder_rate_eur_h, operator_rate_eur_h, operators_per_line, line_speed_kg_h],
        expr_template=f"({{p{extruder_rate_eur_h}}}+{{p{operator_rate_eur_h}}}*{{p{operators_per_line}}})/{{p{line_speed_kg_h}}}",
        contributes_to_bucket_total=False,
    )
    per_part = CalcLine(
        id_code=per_part_id,
        label="Extrusion conversion cost per part",
        unit="EUR/unit",
        kind="expr",
        param_refs=[part_weight_kg, yield_pct],
        line_refs=[per_kg_id],
        expr_template=f"{{{per_kg_id}}}*{{p{part_weight_kg}}}/({{p{yield_pct}}}/100)",
        contributes_to_bucket_total=True,
    )
    return [per_kg.model_dump(), per_part.model_dump()]


def build_forging_conversion_calc_line(
    press_rate_eur_h: int,
    operator_rate_eur_h: int,
    cycle_time_s: int,
    oee_pct: int,
    heating_energy_eur_unit: int,
    post_processing_eur_unit: int,
    heat_treatment_eur_unit: int,
    id_code: str,
) -> dict:
    """Forging Conversion — press + operator time (OEE-adjusted) plus heating energy,
    trimming/post-machining, and heat treatment, each already expressed as EUR/unit.

    Formula: (press_rate + operator_rate) x (cycle_time_s/3600) / (oee_pct/100) +
    heating_energy + post_processing + heat_treatment.

    Args:
        press_rate_eur_h: Parameter number of the press/hammer hourly rate (EUR/h).
        operator_rate_eur_h: Parameter number of the operator rate (EUR/h).
        cycle_time_s: Parameter number of the cycle time per part (seconds).
        oee_pct: Parameter number of OEE (%).
        heating_energy_eur_unit: Parameter number of heating energy cost (EUR/unit).
        post_processing_eur_unit: Parameter number of trimming/post-machining (EUR/unit).
        heat_treatment_eur_unit: Parameter number of heat treatment cost (EUR/unit).
        id_code: This line's id_code, e.g. 'C1'.

    Returns:
        One CalcLine object (as a dict), contributes_to_bucket_total=True.
    """
    line = CalcLine(
        id_code=id_code,
        label="Press + operator conversion cost plus heating, post-processing and heat treatment",
        unit="EUR/unit",
        kind="expr",
        param_refs=[
            press_rate_eur_h, operator_rate_eur_h, cycle_time_s, oee_pct,
            heating_energy_eur_unit, post_processing_eur_unit, heat_treatment_eur_unit,
        ],
        expr_template=(
            f"({{p{press_rate_eur_h}}}+{{p{operator_rate_eur_h}}})*({{p{cycle_time_s}}}/3600)/({{p{oee_pct}}}/100)"
            f"+{{p{heating_energy_eur_unit}}}+{{p{post_processing_eur_unit}}}+{{p{heat_treatment_eur_unit}}}"
        ),
        contributes_to_bucket_total=True,
    )
    return line.model_dump()


def build_electronics_assembly_calc_lines(
    bom_cost_eur_unit: int,
    ems_markup_pct: int,
    smt_rate_eur_h: int,
    operator_rate_eur_h: int,
    cycle_time_s: int,
    first_pass_yield_pct: int,
    rework_eur_unit: int,
    test_eur_unit: int,
    assembly_overhead_eur_unit: int,
    id_prefix: str,
) -> list[dict]:
    """Electronics / PCB assembly — the BoM (often the dominant cost) marked up by the
    EMS, plus the SMT process cost yield-corrected, plus rework/test/overhead already
    expressed as EUR/unit. Two independent lines (no line_refs needed — the BoM line
    does not feed the process line).

    Formula: bom_line = bom_cost x (1 + ems_markup_pct/100); process_line = (smt_rate +
    operator_rate) x (cycle_time_s/3600) / (first_pass_yield_pct/100) + rework + test +
    assembly_overhead.

    Args:
        bom_cost_eur_unit: Parameter number of the bill-of-materials cost (EUR/unit).
        ems_markup_pct: Parameter number of the EMS markup on BoM (%).
        smt_rate_eur_h: Parameter number of the SMT line hourly rate (EUR/h).
        operator_rate_eur_h: Parameter number of the operator rate (EUR/h).
        cycle_time_s: Parameter number of the cycle time per board (seconds).
        first_pass_yield_pct: Parameter number of first-pass yield (%).
        rework_eur_unit: Parameter number of rework cost (EUR/unit).
        test_eur_unit: Parameter number of test/functional test cost (EUR/unit).
        assembly_overhead_eur_unit: Parameter number of assembly overhead (EUR/unit).
        id_prefix: Bucket id-code prefix, e.g. 'M' produces 'M1' (BoM) or 'C' produces
            'C1' (process) — call this once per bucket with that bucket's own prefix and
            only keep the line(s) relevant to that bucket (BoM is usually Material;
            SMT/rework/test/overhead is usually Conversion).

    Returns:
        Exactly two CalcLine objects (as dicts): the BoM line and the process line, both
        contributes_to_bucket_total=True. Place each in the bucket it actually belongs
        to (they do not have to go in the same bucket).
    """
    bom_id = f"{id_prefix}1"
    process_id = f"{id_prefix}2"
    bom_line = CalcLine(
        id_code=bom_id,
        label="BoM cost marked up by EMS",
        unit="EUR/unit",
        kind="expr",
        param_refs=[bom_cost_eur_unit, ems_markup_pct],
        expr_template=f"{{p{bom_cost_eur_unit}}}*(1+{{p{ems_markup_pct}}}/100)",
        contributes_to_bucket_total=True,
    )
    process_line = CalcLine(
        id_code=process_id,
        label="SMT process cost (yield-corrected) plus rework, test, assembly overhead",
        unit="EUR/unit",
        kind="expr",
        param_refs=[smt_rate_eur_h, operator_rate_eur_h, cycle_time_s, first_pass_yield_pct, rework_eur_unit, test_eur_unit, assembly_overhead_eur_unit],
        expr_template=(
            f"({{p{smt_rate_eur_h}}}+{{p{operator_rate_eur_h}}})*({{p{cycle_time_s}}}/3600)/({{p{first_pass_yield_pct}}}/100)"
            f"+{{p{rework_eur_unit}}}+{{p{test_eur_unit}}}+{{p{assembly_overhead_eur_unit}}}"
        ),
        contributes_to_bucket_total=True,
    )
    return [bom_line.model_dump(), process_line.model_dump()]


def build_welded_assembly_calc_line(
    weld_time_h: int,
    weld_rate_eur_h: int,
    fixture_amortization_eur_unit: int,
    fastener_press_eur_unit: int,
    post_weld_cleaning_eur_unit: int,
    inspection_eur_unit: int,
    id_code: str,
) -> dict:
    """Welded subassemblies — Layer 2 (the assembly operation itself, on top of each
    child component's own Layer 1 sheet-metal cost, which is covered by
    build_nesting_yield_material_calc_lines + build_stamping_conversion_calc_line applied
    per child). Weld time x weld rate, plus fixture amortization, fastener press-in, post-
    weld cleaning/passivation, and final inspection — each already EUR/unit.

    Formula: weld_time_h x weld_rate_eur_h + fixture_amortization + fastener_press +
    post_weld_cleaning + inspection.

    Args:
        weld_time_h: Parameter number of total welding time per assembly (hours).
        weld_rate_eur_h: Parameter number of the welding cell hourly rate (EUR/h).
        fixture_amortization_eur_unit: Parameter number of fixture/jig amortization (EUR/unit).
        fastener_press_eur_unit: Parameter number of rivet-nut/blind-rivet press-in cost (EUR/unit).
        post_weld_cleaning_eur_unit: Parameter number of post-weld cleaning/passivation (EUR/unit).
        inspection_eur_unit: Parameter number of final inspection/leak test cost (EUR/unit).
        id_code: This line's id_code, e.g. 'C5'.

    Returns:
        One CalcLine object (as a dict), contributes_to_bucket_total=True.
    """
    line = CalcLine(
        id_code=id_code,
        label="Welded assembly operation (Layer 2)",
        unit="EUR/unit",
        kind="expr",
        param_refs=[
            weld_time_h, weld_rate_eur_h, fixture_amortization_eur_unit,
            fastener_press_eur_unit, post_weld_cleaning_eur_unit, inspection_eur_unit,
        ],
        expr_template=(
            f"{{p{weld_time_h}}}*{{p{weld_rate_eur_h}}}+{{p{fixture_amortization_eur_unit}}}"
            f"+{{p{fastener_press_eur_unit}}}+{{p{post_weld_cleaning_eur_unit}}}+{{p{inspection_eur_unit}}}"
        ),
        contributes_to_bucket_total=True,
    )
    return line.model_dump()
