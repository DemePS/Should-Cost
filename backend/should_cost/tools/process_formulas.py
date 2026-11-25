"""Typed, hardcoded CalcLine builders for the costing_accuracy_rules.md rules that state
an exact, literal formula — Rule 1 (nesting yield + scrap credit) and Rule 2 (lot-based
setup cost). Exposed as tools to the propose_parameters Agent
(should_cost/tools/model_client.py) so the model calls these for the cases they cover
instead of hand-writing the CalcLine bookkeeping (id_code uniqueness, forward-only
line_refs, contributes_to_bucket_total) itself.

Each function is correct by construction: there is no formula for the model to get
wrong here, only parameter numbers to supply correctly. This directly prevents the two
bug classes found by hand while building the generic CalcLine path (a helper line
silently double-counted into a bucket total; a cost line re-deriving an intermediate
value instead of referencing the line that already computed it).

Any process or material not covered by a tool here still falls back to CalcLine's
generic ref/sum/expr construction — see propose_parameters.md.
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
