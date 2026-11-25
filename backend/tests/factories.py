"""Shared builders for synthetic workflow-model instances, used across several test
files. Not a pytest fixture module itself (plain functions, imported directly) since
most tests need slightly different field overrides.
"""

from __future__ import annotations

from should_cost.models.common import Bucket, Confidence, ParameterEstimate, Source, SupplierRow, SupplierType
from should_cost.models.workflow import (
    CalcLine,
    ComplexityFlags,
    CostDriverHypothesis,
    Insights,
    NegotiationLever,
    PreBuildReasoning,
    ProcessAlternative,
    ProposedParameters,
    SelfCritiquePoint,
)


def make_source(**overrides) -> Source:
    defaults = dict(name="Test Source", url="https://example.com/x", vintage="2026", confidence=Confidence.MEDIUM)
    defaults.update(overrides)
    return Source(**defaults)


def make_supplier(**overrides) -> SupplierRow:
    defaults = dict(
        supplier_name="Fastener Fabrik GmbH",
        country="Germany",
        hager_entity="Hager DE",
        unit_of_measure="EA",
        annual_volume=500000.0,
        annual_spend=25000.0,
        current_avg_price=0.05,
        supplier_type=SupplierType.MANUFACTURER,
    )
    defaults.update(overrides)
    return SupplierRow(**defaults)


def make_complexity_flags(**overrides) -> ComplexityFlags:
    defaults = dict(
        cf1_no_commodity_price=False, cf1_reason="n/a",
        cf2_multi_step_transformation=False, cf2_reason="n/a",
        cf3_captive_material_supply=False, cf3_reason="n/a",
        cf4_low_confidence_dominant_input=False, cf4_reason="n/a",
        cf5_unfamiliar_part_family=False, cf5_reason="n/a",
        cf6_high_unit_price_simple_part=False, cf6_reason="n/a",
    )
    defaults.update(overrides)
    return ComplexityFlags(**defaults)


def make_pre_build_reasoning(**overrides) -> PreBuildReasoning:
    defaults = dict(
        component_label="Hex Head Screw M6x20",
        process_primary_hypothesis="cold heading",
        process_alternatives=[
            ProcessAlternative(process="CNC turning", why_not_chosen="too slow for this volume"),
            ProcessAlternative(process="casting", why_not_chosen="not applicable to fasteners"),
        ],
        process_confidence=Confidence.MEDIUM,
        # Matches what make_proposed_parameters() actually computes (should_cost ~0.0103
        # EUR/unit: Material 56.9%, Packaging & Logistics 19.5%, Conversion 5.4%) — kept
        # in sync by hand; test_sanity_gate.py::test_green_within_everything is what
        # would catch the two drifting apart.
        dominant_bucket=CostDriverHypothesis(bucket=Bucket.MATERIAL, expected_share_pct=57, reasoning="steel wire rod dominates at this volume"),
        second_bucket=CostDriverHypothesis(bucket=Bucket.PACKAGING_LOGISTICS, expected_share_pct=20, reasoning="small, light part but fixed packaging floor"),
        smallest_bucket=CostDriverHypothesis(bucket=Bucket.CONVERSION, expected_share_pct=5, reasoning="high-throughput cold heading, negligible per-part time"),
        plausible_sc_low=0.008,
        plausible_sc_high=0.013,
        rationale="DE manufacturer, high volume fastener",
        critical_assumptions=[],
        open_questions=[],
        complexity=make_complexity_flags(),
    )
    defaults.update(overrides)
    return PreBuildReasoning(**defaults)


def make_proposed_parameters(**overrides) -> ProposedParameters:
    src = make_source()
    defaults = dict(
        component_label="Hex Head Screw M6x20",
        process="cold heading",
        parameters={
            Bucket.MATERIAL: [
                ParameterEstimate(number=1, name="Wire rod price", unit="EUR/kg", low=0.7, base=0.9, high=1.2, source=src),
                ParameterEstimate(number=2, name="Part weight", unit="kg", low=0.006, base=0.0065, high=0.007, source=src),
            ],
            Bucket.CONVERSION: [
                ParameterEstimate(number=3, name="Cold header machine rate", unit="EUR/h", low=3, base=5, high=8, source=src),
                ParameterEstimate(number=4, name="Parts per hour", unit="#/h", low=7000, base=9000, high=11000, source=src),
            ],
            Bucket.PACKAGING_LOGISTICS: [
                ParameterEstimate(number=5, name="Packaging + freight", unit="EUR/unit", low=0.001, base=0.002, high=0.004, source=src),
            ],
            Bucket.OVERHEADS: [
                ParameterEstimate(number=6, name="Overheads rate", unit="%", low=8, base=12, high=18, source=src),
            ],
            Bucket.MARGIN: [
                ParameterEstimate(number=7, name="Margin rate", unit="%", low=8, base=12, high=18, source=src),
            ],
        },
        calc_lines={
            Bucket.MATERIAL: [
                CalcLine(id_code="M1", label="Material cost", unit="EUR/unit", kind="expr",
                         param_refs=[1, 2], expr_template="{p1}*{p2}", contributes_to_bucket_total=True),
            ],
            Bucket.CONVERSION: [
                CalcLine(id_code="C1", label="Conversion cost", unit="EUR/unit", kind="expr",
                         param_refs=[3, 4], expr_template="{p3}/{p4}", contributes_to_bucket_total=True),
            ],
            Bucket.PACKAGING_LOGISTICS: [
                CalcLine(id_code="P1", label="Packaging & freight", unit="EUR/unit", kind="ref",
                         param_refs=[5], contributes_to_bucket_total=True),
            ],
        },
        overhead_rate_param_number=6,
        margin_rate_param_number=7,
        p1_conversion_selfcheck_note="Machine-only rate; labor/energy separate.",
        calibration_rules_applied=["C1: cavities n/a (cold heading)", "C6: machine rate is machine-only", "P1: DE regional rate used"],
    )
    defaults.update(overrides)
    return ProposedParameters(**defaults)


def make_insights(**overrides) -> Insights:
    defaults = dict(
        self_critique=[SelfCritiquePoint(point="Wire rod price assumption", why_uncertain="spot price volatility", how_to_harden="confirm with supplier RFQ")],
        likely_supplier_counter_arguments=["Margin is already thin"],
        manufacturing_engineer_view="Parts-per-hour assumption looks aggressive for this tool class.",
        negotiation_levers=[
            NegotiationLever(parameter="Machine rate", current_value="n/a", should_cost_value="5 EUR/h",
                              delta_eur_per_unit=0.001, lever="show machine-only derivation", expected_supplier_response="cites higher all-in rate",
                              counter_argument="labor/energy counted separately")
            for _ in range(3)
        ],
        non_negotiables=["Steel wire rod index price", "DE minimum viable margin"],
        highest_information_gain_question="What is your actual cold-header cycle rate for this part?",
        language="en",
    )
    defaults.update(overrides)
    return Insights(**defaults)
