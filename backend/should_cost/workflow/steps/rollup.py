"""Step SA-5 — assembly roll-up. Pure arithmetic, no model call.

Assembly Should Cost = Σ (component Should Cost per pcs × quantity in BOM), applied
bucket-by-bucket, exactly as SKILL.md's Step SA-5 example shows. Each child JobUnit's
``cost_build`` (set by the engine right after that child's recalc_and_check step) is the
single source of truth this reads from — never re-derived from the child's raw parameters,
so the roll-up can never drift from what that child's own Excel file actually says.
"""

from __future__ import annotations

from should_cost.models.job import JobUnit

_BUCKET_KEYS = ("material_eur", "conversion_eur", "pl_eur", "overheads_eur", "margin_eur")


def compute_rollup(children: list[tuple[JobUnit, float]]) -> dict[str, float]:
    """``children``: (child JobUnit, quantity in the BOM) pairs. Every child must already
    have ``cost_build`` set (i.e. have passed its own Step 4.5 sanity gate and recalc) —
    the engine enforces this ordering, not this function.
    """
    missing = [c.label for c, _ in children if c.cost_build is None]
    if missing:
        raise ValueError(f"Cannot roll up — these child components have no cost_build yet: {missing}")

    totals = {key: 0.0 for key in _BUCKET_KEYS}
    for child, qty in children:
        for key in _BUCKET_KEYS:
            totals[key] += child.cost_build[key] * qty  # type: ignore[index]

    totals["should_cost_eur"] = sum(totals[key] for key in _BUCKET_KEYS)
    totals["current_price_eur"] = sum(
        (child.supplier.current_avg_price if child.supplier else 0.0) * qty for child, qty in children
    )
    totals["impact_eur"] = totals["current_price_eur"] - totals["should_cost_eur"]
    return totals
