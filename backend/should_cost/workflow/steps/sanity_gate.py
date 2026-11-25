"""run_sanity_gate — Step 4.5: the mandatory gate between Excel build and slide output.

SKILL.md: "If overall = RED -> do not produce slide output." The workflow engine enforces
that by checking ``SanityGateResult.blocks_slide_output`` (models/workflow.py), not by
anything in this module — this module only computes the result.

Bucket-share thresholds below encode SKILL.md Step 4.5[3]'s stated GREEN target ranges
exactly (Material 10-70%, Conversion 10-60%, Manufacturing Costs 50-85%, Packaging &
Logistics 1-10%, Overheads 5-20%, Margin 5-20%). The skill gives a green target range and
says "status green/yellow/red" for each without stating the yellow/red cutoffs explicitly
— ASSUMPTION (flagged in the final assumptions list): a share within the stated range is
GREEN, within the range extended by 10 percentage points on either side is YELLOW, and
anything further out is RED. This is the one place in the sanity gate where a numeric
boundary was not given in the source document and had to be chosen.
"""

from __future__ import annotations

from should_cost.excel.formula_eval import base_param_values, compute_cost_build
from should_cost.models.common import Bucket, SanityStatus
from should_cost.models.workflow import (
    BucketShareCheck,
    CalibrationCheck,
    PreBuildReasoning,
    ProposedParameters,
    SanityGateResult,
)

_BUCKET_TARGETS: dict[Bucket, tuple[float, float]] = {
    Bucket.MATERIAL: (10.0, 70.0),
    Bucket.CONVERSION: (10.0, 60.0),
    Bucket.PACKAGING_LOGISTICS: (1.0, 10.0),
    Bucket.OVERHEADS: (5.0, 20.0),
    Bucket.MARGIN: (5.0, 20.0),
}
_MFG_COSTS_TARGET = (50.0, 85.0)
_YELLOW_MARGIN_PP = 10.0

_SEVERITY = {SanityStatus.GREEN: 0, SanityStatus.YELLOW: 1, SanityStatus.RED: 2}


def _share_status(share_pct: float, low: float, high: float) -> SanityStatus:
    if low <= share_pct <= high:
        return SanityStatus.GREEN
    if (low - _YELLOW_MARGIN_PP) <= share_pct <= (high + _YELLOW_MARGIN_PP):
        return SanityStatus.YELLOW
    return SanityStatus.RED


def _worst(*statuses: SanityStatus) -> SanityStatus:
    return max(statuses, key=lambda s: _SEVERITY[s])


def run_sanity_gate(
    *,
    proposed: ProposedParameters,
    pre_build: PreBuildReasoning,
    current_price_eur: float,
    historical_priors: list[str] | None,
    supplier_count: int,
    unit_count: int,
) -> SanityGateResult:
    param_values = base_param_values(proposed)
    cost = compute_cost_build(proposed, param_values)
    should_cost = cost["should_cost_eur"]

    # [1] Reasonability window vs. the Step 1.5 pre-build estimate.
    low, high = pre_build.plausible_sc_low, pre_build.plausible_sc_high
    span = max(high - low, 1e-9)
    if low <= should_cost <= high:
        reasonability_status = SanityStatus.GREEN
        reasonability_note = f"Should Cost {should_cost:.2f} is within the pre-build range [{low:.2f}, {high:.2f}]."
    else:
        distance = min(abs(should_cost - low), abs(should_cost - high))
        if distance <= 0.2 * span:
            reasonability_status = SanityStatus.YELLOW
            reasonability_note = (
                f"Should Cost {should_cost:.2f} is outside [{low:.2f}, {high:.2f}] but within 20% of it."
            )
        else:
            reasonability_status = SanityStatus.RED
            reasonability_note = f"Should Cost {should_cost:.2f} is far outside [{low:.2f}, {high:.2f}]."

    # [2] Impact potential thresholds.
    impact_eur = current_price_eur - should_cost
    impact_pct = (impact_eur / current_price_eur * 100) if current_price_eur else 0.0
    if should_cost > current_price_eur:
        impact_status = SanityStatus.RED
    elif impact_pct < 5:
        impact_status = SanityStatus.RED
    elif impact_pct <= 15:
        impact_status = SanityStatus.GREEN
    elif impact_pct <= 40:
        impact_status = SanityStatus.YELLOW
    else:
        impact_status = SanityStatus.RED

    # [3] Bucket split sanity.
    bucket_checks: list[BucketShareCheck] = []
    for bucket, (t_low, t_high) in _BUCKET_TARGETS.items():
        bucket_eur = {
            Bucket.MATERIAL: cost["material_eur"],
            Bucket.CONVERSION: cost["conversion_eur"],
            Bucket.PACKAGING_LOGISTICS: cost["pl_eur"],
            Bucket.OVERHEADS: cost["overheads_eur"],
            Bucket.MARGIN: cost["margin_eur"],
        }[bucket]
        share_pct = (bucket_eur / should_cost * 100) if should_cost else 0.0
        bucket_checks.append(
            BucketShareCheck(
                bucket=bucket,
                share_pct=share_pct,
                target_low_pct=t_low,
                target_high_pct=t_high,
                status=_share_status(share_pct, t_low, t_high),
            )
        )
    mfg_share_pct = (cost["manufacturing_costs_eur"] / should_cost * 100) if should_cost else 0.0
    mfg_status = _share_status(mfg_share_pct, *_MFG_COSTS_TARGET)

    # [4] Calibration checks C1, C2, C3, C6, P1, P2.
    applied = {rule.split(":")[0].strip().upper() for rule in proposed.calibration_rules_applied}
    calibration_checks = [
        CalibrationCheck(
            rule_id="C1",
            description="Cavities derived from volume, not drawing complexity",
            status=SanityStatus.GREEN if "C1" in applied else SanityStatus.YELLOW,
            note="Confirmed by propose_parameters" if "C1" in applied else "Not explicitly confirmed — verify manually",
        ),
        CalibrationCheck(
            rule_id="C2",
            description="Machine rate class matches part size and cavity count",
            status=SanityStatus.GREEN if "C2" in applied else SanityStatus.YELLOW,
            note="Confirmed by propose_parameters" if "C2" in applied else "Not explicitly confirmed — verify manually",
        ),
        CalibrationCheck(
            rule_id="C3",
            description="Assembly labor justified by drawing evidence",
            status=SanityStatus.GREEN if "C3" in applied else SanityStatus.YELLOW,
            note="Confirmed by propose_parameters" if "C3" in applied else "Not explicitly confirmed — verify manually",
        ),
        CalibrationCheck(
            rule_id="C6",
            description="Machine rate is machine-only within Conversion (Pitfall P1 double-count check)",
            status=SanityStatus.GREEN if "C6" in applied else SanityStatus.RED,
            note=proposed.p1_conversion_selfcheck_note,
        ),
        CalibrationCheck(
            rule_id="P1",
            description="Factor costs are region-appropriate (not a WEU default applied to a non-WEU supplier)",
            status=SanityStatus.GREEN if "P1" in applied else SanityStatus.YELLOW,
            note="Confirmed by propose_parameters" if "P1" in applied else "Not explicitly confirmed — verify manually",
        ),
        CalibrationCheck(
            rule_id="P2",
            description="One model per supplier, never blended",
            status=SanityStatus.GREEN if supplier_count == unit_count else SanityStatus.RED,
            note=f"{unit_count} model(s) built for {supplier_count} distinct supplier(s) — enforced structurally "
            "by the workflow engine (one JobUnit per supplier).",
        ),
    ]

    # [5] Historical comparison.
    if historical_priors:
        historical_note = "Priors available: " + "; ".join(historical_priors)
    else:
        historical_note = "No comparable historical model available — sanity check based on benchmarks only."

    # [Hypothesis validation]
    actual_shares = {bc.bucket: bc.share_pct for bc in bucket_checks}
    actual_dominant = max(actual_shares, key=lambda b: actual_shares[b])
    hypothesis_match = actual_dominant == pre_build.dominant_bucket.bucket
    hypothesis_note = (
        f"Pre-build hypothesis: {pre_build.dominant_bucket.bucket.value} dominant. "
        f"Actual: {actual_dominant.value} dominant ({actual_shares[actual_dominant]:.1f}%)."
    )

    overall = _worst(
        reasonability_status,
        impact_status,
        mfg_status,
        *(bc.status for bc in bucket_checks),
        *(cc.status for cc in calibration_checks),
    )
    if overall == SanityStatus.RED:
        action = "Do not produce slide output. Report findings to the user and pause for fix."
    elif overall == SanityStatus.YELLOW:
        action = "Produce slide output but flag the issue prominently in the Key Insights block."
    else:
        action = "Proceed."

    return SanityGateResult(
        reasonability_status=reasonability_status,
        reasonability_note=reasonability_note,
        impact_pct=impact_pct,
        impact_status=impact_status,
        bucket_checks=bucket_checks,
        calibration_checks=calibration_checks,
        historical_comparison_note=historical_note,
        hypothesis_match=hypothesis_match,
        hypothesis_note=hypothesis_note,
        overall_status=overall,
        action=action,
    )
