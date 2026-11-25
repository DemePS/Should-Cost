"""Job / JobUnit — the persisted state machine.

A ``Job`` is created by ``POST /api/jobs`` and is the unit the frontend polls
(``GET /api/jobs/{id}``). It owns one ``JobUnit`` per supplier (Pitfall P2: never
blended) and, for a sub-assembly, one further ``JobUnit`` per child component plus one
roll-up unit (Step SA-5) — see design.md section 6.

These models are also the serialization contract for ``state/store.py`` (Azure Table /
Blob) — keep them JSON-plain (no datetimes-as-objects across process boundaries without
``mode="json"``, no circular refs) since they are written out after every step.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from should_cost.models.common import SpendLookupResult, SupplierRow
from should_cost.models.workflow import (
    DeepDiveResult,
    Insights,
    PartFacts,
    PreBuildReasoning,
    ProposedParameters,
    SanityGateResult,
)


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    NEEDS_INPUT = "needs_input"
    DONE = "done"
    FAILED = "failed"


class WorkflowStep(str, Enum):
    """Mirrors the skill's own step numbering — used both for ``current_step`` and as
    the resume point. Steps not in ``RESUMABLE`` (engine.py) force a restart to ``failed``
    rather than silently re-entering a step that isn't safe to repeat (e.g. mid-upload).
    """

    STEP_0_DISCOVERY = "step_0_discovery"
    STEP_1_EXTRACT_FACTS = "step_1_extract_facts"
    STEP_1_5_PRE_BUILD_REASONING = "step_1_5_pre_build_reasoning"
    STEP_2_PROPOSE_PARAMETERS = "step_2_propose_parameters"
    STEP_2_5_DEEP_DIVE = "step_2_5_deep_dive"
    STEP_3_RESEARCH = "step_3_research"
    STEP_4_BUILD_EXCEL = "step_4_build_excel"
    STEP_4_5_SANITY_GATE = "step_4_5_sanity_gate"
    STEP_5_SLIDE_VALUES = "step_5_slide_values"
    STEP_5_5_6_INSIGHTS = "step_5_5_6_insights"
    STEP_7_HANDOFF = "step_7_handoff"
    DONE = "done"


class NeedsInputReason(str, Enum):
    NO_SPEND_ROW = "no_spend_row"
    UNCERTAIN_PREFIX_MATCH = "uncertain_prefix_match"
    MISSING_BOM = "missing_bom"
    ILLEGIBLE_DRAWING = "illegible_drawing"
    MULTI_SUPPLIER_PLAN_CONFIRMATION = "multi_supplier_plan_confirmation"
    MISSING_CRITICAL_FIELD = "missing_critical_field"
    SANITY_GATE_RED = "sanity_gate_red"


class PendingQuestion(BaseModel):
    reason: NeedsInputReason
    question: str
    context: str | None = None


class GeneratedFile(BaseModel):
    name: str
    kind: str = Field(description="'calc_model' or 'slide_values'")
    sharepoint_url: str | None = None
    local_path: str | None = Field(default=None, exclude=True, description="Never serialized to the API response.")


class ChatBlocks(BaseModel):
    """Step 5b — Block A-F, kept structured so the frontend can render them without
    re-parsing prose, while still matching the skill's own block definitions 1:1.
    """

    block_a_cost_build: dict[str, float]
    block_b_header_info: dict[str, str]
    block_c_key_results: dict[str, str]
    block_d_input_table: list[dict]
    block_e_sensitivity: list[dict]
    block_f_key_insights: list[str]


class JobUnit(BaseModel):
    """One supplier, or (for a sub-assembly) one child component / the roll-up unit."""

    unit_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    label: str = Field(description="Supplier short name, or child component code, or the assembly ID")
    supplier: SupplierRow | None = None
    is_rollup: bool = False
    child_unit_ids: list[str] = Field(default_factory=list, description="For a rollup unit: its component units")

    part_facts: PartFacts | None = None
    pre_build_reasoning: PreBuildReasoning | None = None
    proposed_parameters: ProposedParameters | None = None
    deep_dive: DeepDiveResult | None = None
    sanity_gate: SanityGateResult | None = None
    insights: Insights | None = None
    chat_blocks: ChatBlocks | None = None
    files: list[GeneratedFile] = Field(default_factory=list)

    status: JobStatus = JobStatus.QUEUED
    current_step: WorkflowStep = WorkflowStep.STEP_0_DISCOVERY


class Job(BaseModel):
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    material_id: str
    language: str = Field(default="en", description="'en', 'fr', or 'de'")
    requested_by: str

    status: JobStatus = JobStatus.QUEUED
    current_step: WorkflowStep = WorkflowStep.STEP_0_DISCOVERY
    pending_question: PendingQuestion | None = None
    failure_reason: str | None = None

    spend_lookup: SpendLookupResult | None = None
    units: list[JobUnit] = Field(default_factory=list)

    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Set by the engine right before a step starts, cleared on success. A restart that
    # finds this set for the job's current_step knows that step was interrupted mid-way
    # (see engine.RESUMABLE / recovery.py).
    step_started_at: datetime | None = None
