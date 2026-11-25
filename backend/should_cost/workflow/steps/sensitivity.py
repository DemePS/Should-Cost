"""compute_sensitivity — Step 5a/Block E: top-5 tornado drivers.

Re-runs the cost build with one parameter at Low/High while every other parameter stays
at Base (SKILL.md Step 5b Block E: "re-running model with one parameter at Low/High while
others at Base"), using the pure-Python evaluator in excel/formula_eval.py rather than
rebuilding/recalculating the Excel file once per scenario — mathematically identical,
and fast enough to run for every parameter on every job.
"""

from __future__ import annotations

from should_cost.excel.formula_eval import base_param_values, compute_cost_build
from should_cost.models.workflow import ProposedParameters


def compute_sensitivity(proposed: ProposedParameters) -> list[dict]:
    """Returns the top-5 drivers by (High SC - Low SC) range, each shaped for
    excel/slide_values.py's ``sensitivity_drivers`` argument: ``{"name", "rows": [...]}``
    with one row per Low/Mid/High scenario.
    """
    base_values = base_param_values(proposed)
    base_sc = compute_cost_build(proposed, base_values)["should_cost_eur"]

    all_params = {p.number: (p, bucket) for bucket, params in proposed.parameters.items() for p in params}

    scored: list[tuple[float, dict]] = []
    for number, (param, _bucket) in all_params.items():
        low_values = dict(base_values)
        low_values[number] = param.low
        high_values = dict(base_values)
        high_values[number] = param.high

        sc_low = compute_cost_build(proposed, low_values)["should_cost_eur"]
        sc_high = compute_cost_build(proposed, high_values)["should_cost_eur"]
        value_range = abs(sc_high - sc_low)

        driver = {
            "name": param.name,
            "rows": [
                {"scenario": "Low", "input_val": _format_input(param.low, param.unit), "sc_result": round(sc_low, 2)},
                {"scenario": "Mid", "input_val": _format_input(param.base, param.unit), "sc_result": round(base_sc, 2)},
                {"scenario": "High", "input_val": _format_input(param.high, param.unit), "sc_result": round(sc_high, 2)},
            ],
        }
        scored.append((value_range, driver))

    scored.sort(key=lambda t: t[0], reverse=True)
    return [driver for _range, driver in scored[:5]]


def _format_input(value: float, unit: str) -> str:
    if unit.strip() == "%":
        return f"{value:g}%"
    return f"{value:g}"
