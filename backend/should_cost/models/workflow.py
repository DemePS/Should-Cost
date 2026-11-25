"""Structured outputs of the three model calls, and the deterministic steps around them.

Each class here is the ``response_format`` passed to a model call (see
should_cost/tools/model_client.py) or the return type of a pure-code step. Field
constraints (``max_length``, custom validators) encode the skill's own "anti-bloat
discipline" limits (e.g. at most 3 critical assumptions, exactly 3 negotiation levers) so a
model that tries to return more is rejected at the schema level, not caught later by a
human reviewer.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, model_validator

from should_cost.models.common import (
    Bucket,
    Confidence,
    ParameterEstimate,
    SanityStatus,
    Source,
    WeightDerivation,
)


class AssemblyType(str, Enum):
    SINGLE_COMPONENT = "single_component"
    SUB_ASSEMBLY = "sub_assembly"


class BomLine(BaseModel):
    """Step SA-1 — one row of a sub-assembly BOM."""

    position: int
    part_code: str
    description: str
    material_description: str
    quantity: float


# ── Step 1: extract_part_facts ────────────────────────────────────────────────────────


class PartFacts(BaseModel):
    """Step 1 structured output. 'No guessing': every optional field left as None is a
    gap the workflow must list explicitly (SKILL.md: 'If a critical field is missing
    after reading all sources, list gaps explicitly before proceeding.').
    """

    assembly_type: AssemblyType
    bom: list[BomLine] = Field(default_factory=list)

    component_name: str
    drawing_number: str | None = None
    specification_reference: str | None = None

    weight: WeightDerivation | None = None
    dimensions_mm: str | None = Field(default=None, description="e.g. 'L120 x W45 x H12'")
    material_grade: str | None = None
    density_g_per_cm3: float | None = None

    manufacturing_process_clues: list[str] = Field(default_factory=list)
    tolerances: str | None = None
    surface_finish: str | None = None
    special_requirements: list[str] = Field(default_factory=list)

    missing_info: list[str] = Field(
        default_factory=list, description="Critical fields that could not be found in any source."
    )


# ── Step 1.5 / 2: propose_parameters ──────────────────────────────────────────────────


class ComplexityFlags(BaseModel):
    """SKILL.md Step 1.5 complexity assessment, criteria CF1-CF6. ``triggered_count``
    is derived, not model-supplied, so the >=2 gate in the workflow can't be gamed by the
    model under- or over-reporting it.
    """

    cf1_no_commodity_price: bool
    cf1_reason: str
    cf2_multi_step_transformation: bool
    cf2_reason: str
    cf3_captive_material_supply: bool
    cf3_reason: str
    cf4_low_confidence_dominant_input: bool
    cf4_reason: str
    cf5_unfamiliar_part_family: bool
    cf5_reason: str
    cf6_high_unit_price_simple_part: bool
    cf6_reason: str

    @property
    def triggered_count(self) -> int:
        return sum(
            [
                self.cf1_no_commodity_price,
                self.cf2_multi_step_transformation,
                self.cf3_captive_material_supply,
                self.cf4_low_confidence_dominant_input,
                self.cf5_unfamiliar_part_family,
                self.cf6_high_unit_price_simple_part,
            ]
        )

    @property
    def deep_dive_required(self) -> bool:
        return self.triggered_count >= 2


class ProcessAlternative(BaseModel):
    process: str
    why_not_chosen: str


class CriticalAssumption(BaseModel):
    assumption: str
    rationale: str


class CostDriverHypothesis(BaseModel):
    bucket: Bucket
    expected_share_pct: float
    reasoning: str


class PreBuildReasoning(BaseModel):
    """SKILL.md Step 1.5 — mandatory before any numeric estimates."""

    component_label: str = Field(description="Component code, or 'single component'")
    weight_derivation: WeightDerivation | None = None
    process_primary_hypothesis: str
    process_alternatives: list[ProcessAlternative] = Field(min_length=2)
    process_confidence: Confidence
    dominant_bucket: CostDriverHypothesis
    second_bucket: CostDriverHypothesis
    smallest_bucket: CostDriverHypothesis
    current_price_eur: float | None = None
    plausible_sc_low: float
    plausible_sc_high: float
    rationale: str
    critical_assumptions: list[CriticalAssumption] = Field(
        max_length=3, description="Max 3 per component — anti-bloat discipline."
    )
    open_questions: list[str] = Field(max_length=2)
    complexity: ComplexityFlags


class CalcLine(BaseModel):
    """One Calculation-tab (Step 4) line item, in one of three allowed shapes. The model
    supplies *which* parameters combine and *how* (it has read bucket_inputs_by_process.md
    and knows e.g. that a nesting-yield gross weight needs ``price / (yield/100)``, not a
    plain sum) — but it never writes a raw cross-sheet formula string itself. Code
    (``should_cost/excel/build.py``) resolves every ``{p<n>}`` placeholder to the exact
    ``'2. Inputs'!F{row}`` reference from the row map it just built, which is the only way
    to honor the skill's own FORMULA INTEGRITY rule ("never hardcode an offset — always
    derive from the row map").
    """

    id_code: str = Field(description="e.g. 'M1', 'C3' — matches SKILL.md's Calculation-tab id scheme")
    label: str
    unit: str
    kind: str = Field(description="'ref' (single parameter), 'sum' (sum of parameters), or 'expr'")
    param_refs: list[int] = Field(
        default_factory=list, description="Parameter numbers (ProposedParameters row numbers) this line uses"
    )
    line_refs: list[str] = Field(
        default_factory=list,
        description="id_codes of EARLIER lines in this same bucket's list that expr_template "
        "references via {<id_code>} (e.g. a gross-weight line referenced by a cost line that "
        "needs it) — forward references only, no referencing a line not yet defined.",
    )
    expr_template: str | None = Field(
        default=None,
        description="Only for kind='expr': an arithmetic expression using {p<n>} placeholders "
        "for each param_refs entry and {<id_code>} placeholders for each line_refs entry, e.g. "
        "'{M1}*{p1}-({M1}-{p2})*{p1}*({p4}/100)'. No sheet names, no cell addresses — those are "
        "substituted by code, never by the model.",
    )
    contributes_to_bucket_total: bool = Field(
        description="False for an intermediate/helper line whose unit is not the bucket's cost "
        "unit (e.g. a gross-weight line in kg, used only via line_refs by a later cost line) — "
        "excluding it from the bucket's Sigma sum is mandatory, not optional: the legacy "
        "reference script's own 'Sigma Material' formula skips exactly such a row. True for "
        "every line that is itself a genuine EUR/unit cost contribution."
    )

    @model_validator(mode="after")
    def _kind_matches_shape(self) -> "CalcLine":
        if self.kind == "expr" and not self.expr_template:
            raise ValueError(f"CalcLine {self.id_code!r}: kind='expr' requires expr_template")
        if self.kind in {"ref", "sum"} and not self.param_refs:
            raise ValueError(f"CalcLine {self.id_code!r}: kind={self.kind!r} requires param_refs")
        return self


class ProposedParameters(BaseModel):
    """Step 2 structured output: the actual Low/Base/High parameter set for one
    component, grouped by bucket, plus the process choice, the calculation lines that
    turn those parameters into each bucket's cost, and the calibration self-check.
    """

    component_label: str
    process: str
    parameters: dict[Bucket, list[ParameterEstimate]]
    calc_lines: dict[Bucket, list[CalcLine]] = Field(
        description="Step 4 Calculation-tab line items per bucket, in display order."
    )
    p1_conversion_selfcheck_note: str = Field(
        description="SKILL.md Pitfall P1 self-check: implied all-in Conversion cost vs. "
        "current price for a commodity part."
    )
    calibration_rules_applied: list[str] = Field(
        description="Which of C1-C6 were explicitly checked, e.g. "
        "['C1: cavities from volume', 'C6: machine rate is machine-only']"
    )

    @model_validator(mode="after")
    def _all_buckets_present(self) -> "ProposedParameters":
        missing = set(Bucket) - set(self.parameters)
        if missing:
            raise ValueError(f"ProposedParameters missing buckets: {sorted(b.value for b in missing)}")
        missing_calc = set(Bucket) - set(self.calc_lines)
        if missing_calc:
            raise ValueError(f"ProposedParameters missing calc_lines for buckets: {sorted(b.value for b in missing_calc)}")

        all_numbers = [p.number for params in self.parameters.values() for p in params]
        if len(all_numbers) != len(set(all_numbers)):
            raise ValueError(f"ParameterEstimate.number must be unique across all buckets, got: {all_numbers}")
        valid_numbers = set(all_numbers)

        all_id_codes = [line.id_code for lines in self.calc_lines.values() for line in lines]
        if len(all_id_codes) != len(set(all_id_codes)):
            raise ValueError(f"CalcLine.id_code must be unique across all buckets, got: {all_id_codes}")
        for bucket, lines in self.calc_lines.items():
            seen_ids: set[str] = set()
            for line in lines:
                unknown = [n for n in line.param_refs if n not in valid_numbers]
                if unknown:
                    raise ValueError(
                        f"CalcLine {line.id_code!r} in bucket {bucket.value!r} references "
                        f"unknown parameter number(s) {unknown}; valid numbers: {sorted(valid_numbers)}"
                    )
                unknown_lines = [ref for ref in line.line_refs if ref not in seen_ids]
                if unknown_lines:
                    raise ValueError(
                        f"CalcLine {line.id_code!r} in bucket {bucket.value!r} references "
                        f"line_refs {unknown_lines} that are not earlier lines in the same bucket "
                        f"(seen so far: {sorted(seen_ids)}) — forward references only."
                    )
                seen_ids.add(line.id_code)
        return self


# ── Step 2.5: Complex Component Deep-Dive ─────────────────────────────────────────────


class ConstituentPrice(BaseModel):
    element: str
    weight_pct: float
    unit_price_eur_per_kg: float
    source: Source


class DeepDiveResult(BaseModel):
    """Step 2.5e Deep-Dive Summary — only produced when ComplexityFlags.deep_dive_required."""

    alloy_family: str
    composition_confirmed: bool
    constituents: list[ConstituentPrice]
    dominant_driver_element: str
    rm_cost_eur_per_kg: float
    rm_cost_eur_per_unit: float
    process_chain: list[str]
    batch_or_continuous_note: str
    overall_yield_pct: float
    open_items: list[str]
    ready_for_step3: bool
    blocker: str | None = None


# ── Step 3: research agent output (one ParameterEstimate per time-sensitive input) ───


class ResearchedParameter(BaseModel):
    """What the research agent's ``submit_parameter`` tool call produces. Converted into
    a ``ParameterEstimate`` once validated (non-fabrication check: a Source with
    ``is_internal=False`` must carry a URL).
    """

    estimate: ParameterEstimate
    is_compound_constituent: bool = False
    marked_to_be_validated: bool = False


# ── Step 4.5: Sanity-Check Gate ────────────────────────────────────────────────────────


class BucketShareCheck(BaseModel):
    bucket: Bucket
    share_pct: float
    target_low_pct: float
    target_high_pct: float
    status: SanityStatus


class CalibrationCheck(BaseModel):
    rule_id: str = Field(description="C1, C2, C3, C6, P1, or P2")
    description: str
    status: SanityStatus
    note: str


class SanityGateResult(BaseModel):
    reasonability_status: SanityStatus
    reasonability_note: str
    impact_pct: float
    impact_status: SanityStatus
    bucket_checks: list[BucketShareCheck]
    calibration_checks: list[CalibrationCheck]
    historical_comparison_note: str
    hypothesis_match: bool
    hypothesis_note: str
    overall_status: SanityStatus
    action: str

    @property
    def blocks_slide_output(self) -> bool:
        return self.overall_status == SanityStatus.RED


# ── Step 5.5 / 6: write_insights ───────────────────────────────────────────────────────


class NegotiationLever(BaseModel):
    parameter: str
    current_value: str
    should_cost_value: str
    delta_eur_per_unit: float
    lever: str
    expected_supplier_response: str
    counter_argument: str


class SelfCritiquePoint(BaseModel):
    point: str
    why_uncertain: str
    how_to_harden: str


class Insights(BaseModel):
    """Step 5.5 self-critique + Step 6 negotiation levers. Counts are enforced at the
    schema level so neither step can silently drift from the skill's anti-bloat rules.
    """

    self_critique: list[SelfCritiquePoint] = Field(min_length=1, max_length=3)
    likely_supplier_counter_arguments: list[str]
    manufacturing_engineer_view: str

    negotiation_levers: list[NegotiationLever] = Field(min_length=3, max_length=3)
    non_negotiables: list[str] = Field(min_length=2)
    highest_information_gain_question: str = Field(
        description="Exactly one supplier question — the single highest information-gain ask."
    )

    language: str = Field(description="'en', 'fr', or 'de' — language of the originating request.")
