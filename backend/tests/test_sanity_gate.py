"""Step 4.5 sanity-gate thresholds: reasonability window, impact-% bands (including the
over-estimation flag), bucket-share bands, and the overall RED/YELLOW/GREEN rollup.
"""

from __future__ import annotations

from should_cost.models.common import Bucket, SanityStatus
from should_cost.workflow.steps.sanity_gate import run_sanity_gate

from tests.factories import make_pre_build_reasoning, make_proposed_parameters


def _gate(**overrides):
    proposed = overrides.pop("proposed", None) or make_proposed_parameters()
    pre_build = overrides.pop("pre_build", None) or make_pre_build_reasoning()
    current_price_eur = overrides.pop("current_price_eur", 0.0114)  # ~10% impact vs. the factory's ~0.0103 should_cost
    return run_sanity_gate(
        proposed=proposed,
        pre_build=pre_build,
        current_price_eur=current_price_eur,
        historical_priors=overrides.pop("historical_priors", None),
        supplier_count=overrides.pop("supplier_count", 1),
        unit_count=overrides.pop("unit_count", 1),
    )


def test_realistic_commodity_part_passes_the_gate() -> None:
    """The factory models a real-shaped scenario (a cheap, high-volume cold-headed
    fastener): reasonability and impact% are both comfortably GREEN. Conversion (5.4%)
    and Packaging & Logistics (19.5%) land just outside their GREEN bands — genuinely
    realistic for a part this cheap and this high-volume, not a bug — so they come back
    YELLOW, which is correct per SKILL.md Step 4.5 ("produce slide output BUT flag the
    issue"), not RED. The contract this test actually checks is that a merely-YELLOW
    bucket share does not block slide output — only a RED overall status does.
    """
    result = _gate()
    assert result.reasonability_status == SanityStatus.GREEN
    assert result.impact_status == SanityStatus.GREEN
    assert result.overall_status == SanityStatus.YELLOW
    assert result.blocks_slide_output is False


def test_over_estimation_is_red() -> None:
    # Should Cost > current price must always be RED, regardless of everything else.
    result = _gate(current_price_eur=0.001)
    assert result.impact_status == SanityStatus.RED
    assert result.overall_status == SanityStatus.RED
    assert result.blocks_slide_output is True


def test_impact_below_5_pct_is_red() -> None:
    # Current price only marginally above should cost -> impact% too small -> RED
    # ("likely model under-estimating cost or supplier already lean").
    from should_cost.excel.formula_eval import base_param_values, compute_cost_build

    proposed = make_proposed_parameters()
    should_cost = compute_cost_build(proposed, base_param_values(proposed))["should_cost_eur"]
    result = _gate(current_price_eur=should_cost * 1.01)  # ~1% impact
    assert result.impact_status == SanityStatus.RED


def test_impact_15_to_40_pct_is_yellow() -> None:
    from should_cost.excel.formula_eval import base_param_values, compute_cost_build

    proposed = make_proposed_parameters()
    should_cost = compute_cost_build(proposed, base_param_values(proposed))["should_cost_eur"]
    result = _gate(current_price_eur=should_cost / (1 - 0.25))  # 25% impact
    assert result.impact_status == SanityStatus.YELLOW


def test_p2_check_green_when_structurally_enforced() -> None:
    result = _gate(supplier_count=2, unit_count=2)
    p2 = next(c for c in result.calibration_checks if c.rule_id == "P2")
    assert p2.status == SanityStatus.GREEN


def test_p2_check_red_when_models_dont_match_suppliers() -> None:
    result = _gate(supplier_count=2, unit_count=1)
    p2 = next(c for c in result.calibration_checks if c.rule_id == "P2")
    assert p2.status == SanityStatus.RED
    assert result.overall_status == SanityStatus.RED


def test_c6_check_red_when_not_applied() -> None:
    proposed = make_proposed_parameters(calibration_rules_applied=["P1: DE regional rate used"])
    result = _gate(proposed=proposed)
    c6 = next(c for c in result.calibration_checks if c.rule_id == "C6")
    assert c6.status == SanityStatus.RED


def test_hypothesis_match_detected() -> None:
    result = _gate()
    assert result.hypothesis_match is True  # factory's dominant bucket is Conversion, matches computed


def test_no_historical_priors_note() -> None:
    result = _gate(historical_priors=None)
    assert "No comparable historical model available" in result.historical_comparison_note


def test_historical_priors_included_in_note() -> None:
    result = _gate(historical_priors=["Should_Cost_0T0005_v01.xlsx"])
    assert "Should_Cost_0T0005_v01.xlsx" in result.historical_comparison_note


def test_bucket_shares_sum_to_should_cost_pct() -> None:
    result = _gate()
    total_share = sum(bc.share_pct for bc in result.bucket_checks)
    assert abs(total_share - 100.0) < 0.01
