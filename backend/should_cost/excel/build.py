"""Converts workflow Pydantic models into legacy_builder's plain-tuple inputs.

``legacy_builder.py`` (the ported skill script) is kept verbatim — this module is the
real "app" layer: it turns a ``ProposedParameters`` + ``SupplierRow`` into the
``general_info`` / ``inputs`` / ``calculations`` shapes the ported script expects, and
resolves every ``CalcLine`` formula into a real ``'2. Inputs'!F{row}`` / Calculation-tab
``E{row}`` reference *before* calling it — never inside it — so the row numbers always
come from an actual row map, matching the skill's own FORMULA INTEGRITY rule.

Row-position bookkeeping (``_plan_input_rows`` / ``_plan_calc_rows``) mirrors
``legacy_builder.build_calc_model``'s internal row-increment loop exactly (same branches,
same order) — it has to, since that function doesn't expose its row maps until after it
has already written the file. Keeping both copies short and side by side is the safest
way to avoid the two silently diverging; a mismatch here is exactly the "shifted SUM
range" failure mode the skill's own FORMULA INTEGRITY checklist warns about.
"""

from __future__ import annotations

from should_cost.excel import legacy_builder
from should_cost.models.common import Bucket, ParameterEstimate, Source, SupplierRow
from should_cost.models.workflow import CalcLine, ProposedParameters

_REF_VOLUME_SUFFIX = "(Annual Volume, Annual Spend, Current Avg Price)"


def _format_source(source: Source) -> str:
    parts = [source.name]
    if source.url:
        parts.append(source.url)
    parts.append(source.vintage)
    parts.append(f"Confidence: {source.confidence.value}")
    text = " | ".join(parts)
    return "To be validated — " + text if source.to_be_validated else text


def _reference_parameters(supplier: SupplierRow, start_number: int) -> list[ParameterEstimate]:
    internal_source = Source(
        name="HAGER PPE spend file",
        url=None,
        vintage="current",
        confidence="high",  # type: ignore[arg-type]
        is_internal=True,
    )
    return [
        ParameterEstimate(
            number=start_number,
            name="Annual Volume",
            unit=f"{supplier.unit_of_measure}/yr",
            low=supplier.annual_volume,
            base=supplier.annual_volume,
            high=supplier.annual_volume,
            source=internal_source,
        ),
        ParameterEstimate(
            number=start_number + 1,
            name="Annual Spend",
            unit="EUR/yr",
            low=supplier.annual_spend,
            base=supplier.annual_spend,
            high=supplier.annual_spend,
            source=internal_source,
        ),
        ParameterEstimate(
            number=start_number + 2,
            name="Current Avg Price",
            unit=f"EUR/{supplier.unit_of_measure}",
            low=supplier.current_avg_price,
            base=supplier.current_avg_price,
            high=supplier.current_avg_price,
            source=internal_source,
        ),
    ]


def _build_inputs(proposed: ProposedParameters, supplier: SupplierRow) -> tuple[list, dict[str, int]]:
    inputs: list = []
    for bucket in Bucket:
        inputs.append(bucket.value)
        for p in sorted(proposed.parameters[bucket], key=lambda p: p.number):
            inputs.append((p.number, p.name, p.unit, p.low, p.base, p.high, _format_source(p.source)))

    all_numbers = [p.number for params in proposed.parameters.values() for p in params]
    ref_params = _reference_parameters(supplier, start_number=max(all_numbers) + 1)
    inputs.append("Reference Data (fixed)")
    for p in ref_params:
        inputs.append((p.number, p.name, p.unit, p.low, p.base, p.high, _format_source(p.source)))
    ref_numbers = {"volume": ref_params[0].number, "spend": ref_params[1].number, "price": ref_params[2].number}
    return inputs, ref_numbers


def _plan_input_rows(inputs: list) -> dict[int, int]:
    row_map: dict[int, int] = {}
    r = 3
    for item in inputs:
        if isinstance(item, str):
            r += 1
        else:
            row_map[item[0]] = r
            r += 1
    return row_map


def _resolve_calc_line(line: CalcLine, input_row_map: dict[int, int], calc_row_map: dict[str, int]) -> str:
    """``calc_row_map`` must already contain every id_code in ``line.line_refs`` — the
    caller only calls this once the full calc_row_map is known (see _build_calculations),
    which is guaranteed by the ProposedParameters validator requiring line_refs to be
    forward-only references to earlier lines in the same bucket.
    """

    def param_ref(num: int) -> str:
        return f"'2. Inputs'!F{input_row_map[num]}"

    def line_ref(id_code: str) -> str:
        return f"E{calc_row_map[id_code]}"

    if line.kind == "ref":
        return f"={param_ref(line.param_refs[0])}"
    if line.kind == "sum":
        return "=" + "+".join(param_ref(n) for n in line.param_refs)
    assert line.kind == "expr" and line.expr_template
    expr = line.expr_template
    for n in line.param_refs:
        expr = expr.replace(f"{{p{n}}}", param_ref(n))
    for ref_id in line.line_refs:
        expr = expr.replace(f"{{{ref_id}}}", line_ref(ref_id))
    return f"={expr}"


_BUCKET_SECTION_LABEL = {
    Bucket.MATERIAL: "  1. Material",
    Bucket.CONVERSION: "  2. Conversion",
    Bucket.PACKAGING_LOGISTICS: "  3. Packaging & Logistics",
    Bucket.OVERHEADS: "  4. Overheads",
    Bucket.MARGIN: "  5. Margin",
}
_BUCKET_SIGMA_LABEL = {
    Bucket.MATERIAL: "Σ Material",
    Bucket.CONVERSION: "Σ Conversion",
    Bucket.PACKAGING_LOGISTICS: "Σ Packaging & Logistics",
}


def _build_calculations(
    proposed: ProposedParameters, input_row_map: dict[int, int], ref_numbers: dict[str, int]
) -> list:
    calc_items: list = []
    pending_lines: dict[str, CalcLine] = {}

    def add_bucket(bucket: Bucket, *, with_sigma: bool) -> None:
        calc_items.append(_BUCKET_SECTION_LABEL[bucket])
        bucket_lines = proposed.calc_lines[bucket]
        for line in bucket_lines:
            pending_lines[line.id_code] = line
            # Placeholder — resolved below once calc_row_map (incl. this line's own row,
            # and any earlier line it references via line_refs) is known.
            calc_items.append((line.id_code, line.label, line.unit, ""))
        if with_sigma:
            sigma_unit = bucket_lines[-1].unit if bucket_lines else "€/unit"
            # Placeholder formula — overwritten below once calc-tab row numbers are known.
            calc_items.append(("_SIGMA_C", _BUCKET_SIGMA_LABEL[bucket], sigma_unit, ""))
        calc_items.append("_BLANK")

    add_bucket(Bucket.MATERIAL, with_sigma=True)
    add_bucket(Bucket.CONVERSION, with_sigma=True)
    calc_items.append(("_SUBTOTAL_B", "Manufacturing Costs", "€/unit", ""))
    calc_items.append("_BLANK")
    add_bucket(Bucket.PACKAGING_LOGISTICS, with_sigma=True)
    add_bucket(Bucket.OVERHEADS, with_sigma=False)
    add_bucket(Bucket.MARGIN, with_sigma=False)
    calc_items.append(("_SUBTOTAL_B", "SHOULD COST", "€/unit", ""))
    calc_items.append(("_SIGMA_B", "Σ CURRENT PRICE", "€/unit", ""))
    calc_items.append(("_SIGMA_B", "Impact Potential", "€/unit", ""))
    calc_items.append(("_SIGMA_B", "Impact %", "%", ""))
    calc_items.append(("_SIGMA_B", "Annual saving potential", "€", ""))

    calc_row_map = legacy_builder_plan_calc_rows(calc_items)

    def calc_ref(key: str) -> str:
        return f"E{calc_row_map[key]}"

    # Only lines marked contributes_to_bucket_total=True are summed — a helper line (e.g.
    # a gross-weight intermediate in kg, used only via line_refs) must NOT be added into
    # the bucket's EUR total, matching the legacy script's own 'Sigma Material' formula
    # (which sums only the final cost rows, not the gross-weight row before them).
    def contributing_ids(bucket: Bucket) -> list[str]:
        return [ln.id_code for ln in proposed.calc_lines[bucket] if ln.contributes_to_bucket_total]

    material_ids = contributing_ids(Bucket.MATERIAL)
    conversion_ids = contributing_ids(Bucket.CONVERSION)
    pl_ids = contributing_ids(Bucket.PACKAGING_LOGISTICS)
    overheads_ids = contributing_ids(Bucket.OVERHEADS)
    margin_ids = contributing_ids(Bucket.MARGIN)

    sigma_formula = lambda ids: "=" + "+".join(calc_ref(i) for i in ids)  # noqa: E731

    resolved: list = []
    for item in calc_items:
        if isinstance(item, tuple) and item[0] in pending_lines:
            line = pending_lines[item[0]]
            resolved.append((item[0], item[1], item[2], _resolve_calc_line(line, input_row_map, calc_row_map)))
        elif isinstance(item, tuple) and item[0] == "_SIGMA_C":
            label = item[1]
            source_ids = {
                _BUCKET_SIGMA_LABEL[Bucket.MATERIAL]: material_ids,
                _BUCKET_SIGMA_LABEL[Bucket.CONVERSION]: conversion_ids,
                _BUCKET_SIGMA_LABEL[Bucket.PACKAGING_LOGISTICS]: pl_ids,
            }[label]
            resolved.append((item[0], item[1], item[2], sigma_formula(source_ids)))
        elif isinstance(item, tuple) and item[0] == "_SUBTOTAL_B" and item[1] == "Manufacturing Costs":
            resolved.append((item[0], item[1], item[2], f"={calc_ref(_BUCKET_SIGMA_LABEL[Bucket.MATERIAL])}+{calc_ref(_BUCKET_SIGMA_LABEL[Bucket.CONVERSION])}"))
        elif isinstance(item, tuple) and item[0] == "_SUBTOTAL_B" and item[1] == "SHOULD COST":
            overheads_sum = "+".join(calc_ref(i) for i in overheads_ids) if overheads_ids else "0"
            margin_sum = "+".join(calc_ref(i) for i in margin_ids) if margin_ids else "0"
            resolved.append(
                (
                    item[0],
                    item[1],
                    item[2],
                    f"={calc_ref('Manufacturing Costs')}+{calc_ref(_BUCKET_SIGMA_LABEL[Bucket.PACKAGING_LOGISTICS])}+{overheads_sum}+{margin_sum}",
                )
            )
        elif isinstance(item, tuple) and item[0] == "_SIGMA_B" and item[1] == "Σ CURRENT PRICE":
            price_row = input_row_map[ref_numbers["price"]]
            resolved.append((item[0], item[1], item[2], f"='2. Inputs'!F{price_row}"))
        elif isinstance(item, tuple) and item[0] == "_SIGMA_B" and item[1] == "Impact Potential":
            resolved.append((item[0], item[1], item[2], f"={calc_ref('Σ CURRENT PRICE')}-{calc_ref('SHOULD COST')}"))
        elif isinstance(item, tuple) and item[0] == "_SIGMA_B" and item[1] == "Impact %":
            resolved.append((item[0], item[1], item[2], f"={calc_ref('Impact Potential')}/{calc_ref('Σ CURRENT PRICE')}"))
        elif isinstance(item, tuple) and item[0] == "_SIGMA_B" and item[1] == "Annual saving potential":
            volume_row = input_row_map[ref_numbers["volume"]]
            resolved.append((item[0], item[1], item[2], f"={calc_ref('Impact Potential')}*'2. Inputs'!F{volume_row}"))
        else:
            resolved.append(item)
    return resolved


def legacy_builder_plan_calc_rows(calc_items: list) -> dict[str, int]:
    """Mirrors legacy_builder.build_calc_model's internal calc_row bookkeeping exactly —
    see this module's docstring for why this duplication is the safe choice here.
    """
    row_map: dict[str, int] = {}
    r = 3
    for item in calc_items:
        if isinstance(item, str) and item != "_BLANK":
            r += 1
        elif item == "_BLANK":
            r += 1
        else:
            tag = item[0]
            element = item[1] if len(item) > 1 else None
            if tag in ("_SIGMA_C", "_SUBTOTAL_B", "_SIGMA_B"):
                row_map[element] = r
            else:
                row_map[tag] = r
            r += 1
    return row_map


def build_calc_model_excel(
    *,
    component_title: str,
    general_info_rows: list[tuple[str, str]],
    proposed: ProposedParameters,
    supplier: SupplierRow,
    out_path: str,
) -> tuple[str, dict[int, int], dict[str, int]]:
    """Step 4 — build the calculated Excel model for one component/supplier."""
    inputs, ref_numbers = _build_inputs(proposed, supplier)
    input_row_map = _plan_input_rows(inputs)
    calculations = _build_calculations(proposed, input_row_map, ref_numbers)
    general_info = {"title": component_title, "rows": general_info_rows}
    _, param_row_map, calc_row_map = legacy_builder.build_calc_model(general_info, inputs, calculations, out_path)
    return out_path, param_row_map, calc_row_map
