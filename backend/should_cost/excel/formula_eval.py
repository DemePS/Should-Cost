"""Pure-Python evaluator for CalcLine expressions.

Used by compute_sensitivity (should_cost/workflow/steps/sensitivity.py) to recompute the
should-cost result for a parameter set many times without shelling out to LibreOffice for
every tornado scenario — the actual Excel file's formulas (built by excel/build.py) encode
the exact same ref/sum/expr semantics, so evaluating them here and recalculating the real
workbook via LibreOffice (excel/recalc.py) are two independent implementations of the same
arithmetic, which is also a useful cross-check: should_cost/tests/test_sanity_gate.py
compares this evaluator's result against a LibreOffice-recalculated value for the same
inputs.

``expr_template`` originates from a model response (should_cost/models/workflow.py
CalcLine), so it is parsed and evaluated through a restricted AST — never ``eval()`` — to
rule out anything beyond numbers and ``+ - * / ( )`` even though the schema and prompt
already constrain it to that.
"""

from __future__ import annotations

import ast
import operator

from should_cost.models.common import Bucket
from should_cost.models.workflow import CalcLine, ProposedParameters

_ALLOWED_BINOPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
}
_ALLOWED_UNARYOPS = {ast.UAdd: operator.pos, ast.USub: operator.neg}


class UnsafeExpressionError(ValueError):
    pass


def _eval_node(node: ast.AST) -> float:
    if isinstance(node, ast.Expression):
        return _eval_node(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp) and type(node.op) in _ALLOWED_BINOPS:
        return _ALLOWED_BINOPS[type(node.op)](_eval_node(node.left), _eval_node(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _ALLOWED_UNARYOPS:
        return _ALLOWED_UNARYOPS[type(node.op)](_eval_node(node.operand))
    raise UnsafeExpressionError(f"Disallowed expression node: {ast.dump(node)}")


def eval_arithmetic(expression: str) -> float:
    """Evaluate a '+','-','*','/','(',')'-only arithmetic expression safely."""
    try:
        tree = ast.parse(expression, mode="eval")
    except SyntaxError as exc:
        raise UnsafeExpressionError(f"Could not parse expression {expression!r}: {exc}") from exc
    return _eval_node(tree)


def eval_calc_line(line: CalcLine, param_values: dict[int, float], line_values: dict[str, float] | None = None) -> float:
    """``line_values`` must already contain every id_code in ``line.line_refs`` — the
    caller (compute_cost_build) guarantees this by evaluating each bucket's lines in
    order, same as excel/build.py resolves them in order.
    """
    line_values = line_values or {}
    if line.kind == "ref":
        return param_values[line.param_refs[0]]
    if line.kind == "sum":
        return sum(param_values[n] for n in line.param_refs)
    assert line.kind == "expr" and line.expr_template
    expr = line.expr_template
    for n in line.param_refs:
        expr = expr.replace(f"{{p{n}}}", f"({param_values[n]})")
    for ref_id in line.line_refs:
        expr = expr.replace(f"{{{ref_id}}}", f"({line_values[ref_id]})")
    return eval_arithmetic(expr)


def compute_cost_build(proposed: ProposedParameters, param_values: dict[int, float]) -> dict[str, float]:
    """Evaluate every CalcLine bucket-by-bucket and roll up to Should Cost, mirroring
    excel/build.py's subtotal wiring exactly (Manufacturing Costs = Material + Conversion;
    Should Cost = Manufacturing Costs + Packaging & Logistics + Overheads + Margin).
    """

    def bucket_total(bucket: Bucket) -> float:
        line_values: dict[str, float] = {}
        total = 0.0
        for line in proposed.calc_lines[bucket]:
            value = eval_calc_line(line, param_values, line_values)
            line_values[line.id_code] = value
            # A helper/intermediate line (e.g. gross weight in kg) is cached for later
            # line_refs lookups but must not itself be added to the EUR total — see
            # CalcLine.contributes_to_bucket_total.
            if line.contributes_to_bucket_total:
                total += value
        return total

    material = bucket_total(Bucket.MATERIAL)
    conversion = bucket_total(Bucket.CONVERSION)
    manufacturing_costs = material + conversion
    packaging_logistics = bucket_total(Bucket.PACKAGING_LOGISTICS)
    # Overheads/Margin are always "rate% x running subtotal" (see CALC_LINE_BUCKETS'
    # docstring) — computed directly here, mirroring excel/build.py's O1/S1 formulas,
    # not via proposed.calc_lines (which no longer includes these two buckets).
    overhead_rate_pct = param_values[proposed.overhead_rate_param_number]
    overheads = manufacturing_costs * overhead_rate_pct / 100
    margin_rate_pct = param_values[proposed.margin_rate_param_number]
    margin = (manufacturing_costs + packaging_logistics + overheads) * margin_rate_pct / 100
    should_cost = manufacturing_costs + packaging_logistics + overheads + margin

    return {
        "material_eur": material,
        "conversion_eur": conversion,
        "manufacturing_costs_eur": manufacturing_costs,
        "pl_eur": packaging_logistics,
        "overheads_eur": overheads,
        "margin_eur": margin,
        "should_cost_eur": should_cost,
    }


def base_param_values(proposed: ProposedParameters) -> dict[int, float]:
    return {p.number: p.base for params in proposed.parameters.values() for p in params}
