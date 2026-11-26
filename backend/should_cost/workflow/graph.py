"""The workflow orchestrator — a LangGraph ``StateGraph``, one node per should-cost step
(SKILL.md Steps 0-7). Replaces the previous hand-rolled async engine.

State is ``should_cost.models.job.Job`` itself (confirmed LangGraph accepts a Pydantic
model directly as ``state_schema``) — nodes return partial-update dicts, same convention
as every LangGraph example; a node that needs to mutate one supplier's ``JobUnit`` copies
``state.units``, mutates the one at ``state.current_unit_index`` in place (JobUnit is a
plain mutable BaseModel, same as the old engine.py did), and returns the whole list.

Multiple suppliers (Pitfall P2) are processed **sequentially**, not fanned out with
LangGraph's ``Send`` — a loop over ``current_unit_index`` with a conditional edge back to
the first per-unit node. A ``Send``-based parallel fan-out is architecturally possible,
but interacts with interrupt/resume in ways that need careful, separately-verified
design (which specific parallel branch resumes on a given answer); sequential processing
is unambiguous and was not worth the added risk here.

Human-in-the-loop pauses use LangGraph's own primitive: a node calls ``interrupt(value)``,
which raises a resumable exception and halts the graph; the caller resumes with
``Command(resume=answer_text)``. Each pause point is a *dedicated*, otherwise-empty node
(``await_input``) rather than being inlined into the step that detected the gap — this
matters because interrupt()'s own contract is "the graph resumes from the start of the
node, re-executing all its logic": if extract_facts itself called interrupt(), every
resume would re-run the model call that already produced the (incomplete) result before
even reaching the interrupt. Kept separate, resuming only re-runs the cheap await_input
node, then routes back to redo the real step with the human's answer folded in.

``run_job``/``answer_job`` below are a thin compatibility facade so cli.py, routes/jobs.py,
runner.py and recovery.py — all written against the old engine.py's function signatures —
don't need to change: they build/compile the graph, invoke or resume it, and translate a
LangGraph interrupt (or a terminal state) back into the same Job.status/pending_question
contract the rest of the app already expects.

KNOWN GAP (pre-existing, not introduced by this rewrite): discovery's own two
confirmation pauses (UNCERTAIN_PREFIX_MATCH, MULTI_SUPPLIER_PLAN_CONFIRMATION) answer by
re-running discovery from scratch, same as the old engine.py — run_discovery's PPE
lookup recomputes the same ambiguous/multi-supplier result and raises the same pause
again. Fixing it means carrying the already-computed SpendLookupResult through the
pause instead of recomputing it, which NeedsInputSignal doesn't carry today. Flagged,
not fixed, in this pass — see the final assumptions list.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from azure.core.credentials_async import AsyncTokenCredential
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import Command, interrupt

from should_cost.config import Settings
from should_cost.excel.build import build_calc_model_excel
from should_cost.excel.recalc import recalc_and_check
from should_cost.excel.slide_values import build_slide_values_excel
from should_cost.models.common import MatchType, SpendLookupResult, SupplierRow, SupplierType
from should_cost.models.job import (
    DiscoveryDocument,
    GeneratedFile,
    Job,
    JobStatus,
    JobUnit,
    NeedsInputReason,
    PendingQuestion,
    StepEvent,
    StepEventStatus,
    WorkflowStep,
)
from should_cost.state.store import JobStateStore
from should_cost.tools import model_client
from should_cost.tools.research_agent import run_research
from should_cost.workflow.signals import NeedsInputSignal
from should_cost.workflow.steps.discovery import run_discovery
from should_cost.workflow.steps.handoff import (
    build_cross_supplier_table,
    calc_model_filename,
    run_id,
    slide_values_filename,
    upload_unit_files,
)
from should_cost.workflow.steps.insights import build_chat_blocks, run_write_insights
from should_cost.workflow.steps.research import merge_researched_parameters, select_research_targets
from should_cost.workflow.steps.rollup import compute_rollup
from should_cost.workflow.steps.sanity_gate import run_sanity_gate
from should_cost.workflow.steps.sensitivity import compute_sensitivity

# Same meaning as the old engine.py's NON_RESUMABLE_STEPS — re-exported for
# recovery.py, which decides whether a job interrupted mid-step is safe to just
# re-invoke (everything up to the sanity gate is a pure function of already-persisted
# inputs) or must be marked failed (Step 7's external upload is not).
NON_RESUMABLE_STEPS = {WorkflowStep.STEP_7_HANDOFF}

# LangGraph's msgpack checkpoint serializer (JsonPlusSerializer) warns, but still
# deserializes, any custom type it doesn't recognize by module+name *unless* it's given
# an explicit allowed_msgpack_modules list — in which case it switches to blocking
# (returning nothing / corrupting the field) anything not in that list. Confirmed live,
# the hard way: an earlier version of this file passed an explicit list containing only
# the str-Enums (JobStatus, WorkflowStep, ...) and not the many nested Pydantic
# BaseModels Job also carries (PendingQuestion, JobUnit, SpendLookupResult,
# DiscoveryDocument, PartFacts, ProposedParameters, ...) — every one of those got
# silently blocked on checkpoint reload, corrupting state across every resume. Given how
# large and easy to under-enumerate that set is, the checkpointer is left on its
# documented-safe default (warn, don't block) by not overriding serde at all, rather
# than risk the same mistake again; a stricter allowlist is a real future-langgraph-
# version follow-up (see LANGGRAPH_STRICT_MSGPACK in langgraph's own source), not done
# here.


@dataclass
class GraphContext:
    """Per-invocation dependencies that must never be persisted in a checkpoint (a chat
    client / credential aren't serializable, and shouldn't be — they're rebuilt fresh by
    run_job/answer_job on every call, same as the old engine.py rebuilt a chat_client
    once per run_job call). Injected via LangGraph's Runtime, not the Job state itself.
    """

    settings: Settings
    credential: AsyncTokenCredential
    chat_client: Any
    store: JobStateStore
    skip_upload: bool


def _trace_list(
    trace: list[StepEvent], step: WorkflowStep, status: StepEventStatus, detail: str | None = None
) -> list[StepEvent]:
    return [*trace, StepEvent(step=step, status=status, detail=detail)]


def _short_name(supplier_name: str) -> str:
    return "".join(ch for ch in supplier_name if ch.isalnum())[:12] or "Supplier"


def _read_reference(filename: str) -> str:
    # graph.py -> workflow -> should_cost -> backend -> repo root (parents[3])
    skill_dir = Path(__file__).resolve().parents[3] / "skill" / "hager-should-cost-builder" / "references"
    return (skill_dir / filename).read_text(encoding="utf-8")


async def _persist_snapshot(ctx: GraphContext, state: Job, update: dict[str, Any]) -> None:
    """Mirrors the old engine.py's _persist() calls — a human/API-readable Job snapshot
    in JobStateStore (Azure Table/Blob/InMemory), independent of LangGraph's own sqlite
    checkpoint (which backs resumability, not /api/jobs/{id} or job.json).
    """
    snapshot = state.model_copy(update=update)
    snapshot.updated_at = dt.datetime.now(dt.UTC)
    await ctx.store.save(snapshot)


def _current_unit(state: Job) -> JobUnit:
    return state.units[state.current_unit_index]


# ── Step 0 ──────────────────────────────────────────────────────────────────────────


async def discovery_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    trace = _trace_list(state.trace, WorkflowStep.STEP_0_DISCOVERY, StepEventStatus.STARTED)
    await _persist_snapshot(ctx, state, {"current_step": WorkflowStep.STEP_0_DISCOVERY, "trace": trace})

    try:
        discovery = await run_discovery(material_id=state.material_id, credential=ctx.credential, settings=ctx.settings)
    except NeedsInputSignal as signal:
        return {
            "trace": _trace_list(
                trace, WorkflowStep.STEP_0_DISCOVERY, StepEventStatus.FAILED, detail=signal.reason.value
            ),
            "pending_question": PendingQuestion(reason=signal.reason, question=signal.question, context=signal.context),
        }

    units = [JobUnit(label=s.supplier_name, supplier=s) for s in discovery.spend_lookup.suppliers]
    update = {
        "spend_lookup": discovery.spend_lookup,
        "discovery_documents": [DiscoveryDocument(filename=n, text=t) for n, t in discovery.material_documents],
        "historical_priors": discovery.historical_priors,
        "units": units,
        "trace": _trace_list(
            trace, WorkflowStep.STEP_0_DISCOVERY, StepEventStatus.COMPLETED, detail=f"{len(units)} supplier unit(s)"
        ),
    }
    await _persist_snapshot(ctx, state, update)
    return update


def route_from_start(state: Job) -> Literal["discovery", "extract_facts"]:
    # cli.py's local runner builds spend_lookup/units itself, bypassing Graph entirely —
    # same bypass the old engine.py's "if job.spend_lookup is None" guard provided.
    return "extract_facts" if state.spend_lookup is not None else "discovery"


def route_after_discovery(state: Job) -> Literal["await_input", "extract_facts"]:
    return "await_input" if state.pending_question is not None else "extract_facts"


# ── Per-unit steps (Pitfall P2 — sequential over state.units) ───────────────────────


async def extract_facts_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    units = list(state.units)
    unit = units[state.current_unit_index]
    if unit.part_facts is not None:
        return {}  # already done (resume after a later step's interrupt) — skip re-running

    unit.current_step = WorkflowStep.STEP_1_EXTRACT_FACTS
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_1_EXTRACT_FACTS, StepEventStatus.STARTED)
    await _persist_snapshot(ctx, state, {"units": units})

    document_text = "\n\n".join(doc.text for doc in state.discovery_documents)
    ppe_context = unit.supplier.model_dump_json() if unit.supplier else "{}"
    unit.part_facts = await model_client.extract_part_facts(
        ctx.chat_client, document_text=document_text, ppe_context=ppe_context, settings=ctx.settings
    )

    if unit.part_facts.missing_info:
        unit.trace = _trace_list(
            unit.trace, WorkflowStep.STEP_1_EXTRACT_FACTS, StepEventStatus.FAILED, detail="missing_info"
        )
        update = {
            "units": units,
            "pending_question": PendingQuestion(
                reason=NeedsInputReason.MISSING_CRITICAL_FIELD,
                question=f"[{unit.label}] Missing critical fields: {unit.part_facts.missing_info}",
            ),
        }
        await _persist_snapshot(ctx, state, update)
        return update

    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_1_EXTRACT_FACTS, StepEventStatus.COMPLETED)
    update = {"units": units}
    await _persist_snapshot(ctx, state, update)
    return update


def route_after_extract_facts(state: Job) -> Literal["await_input", "pre_build_reasoning"]:
    return "await_input" if state.pending_question is not None else "pre_build_reasoning"


async def pre_build_reasoning_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    units = list(state.units)
    unit = units[state.current_unit_index]
    if unit.pre_build_reasoning is not None:
        return {}
    assert unit.part_facts is not None

    unit.current_step = WorkflowStep.STEP_1_5_PRE_BUILD_REASONING
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_1_5_PRE_BUILD_REASONING, StepEventStatus.STARTED)
    bucket_ref = _read_reference("bucket_inputs_by_process.md")
    unit.pre_build_reasoning = await model_client.pre_build_reasoning(
        ctx.chat_client,
        component_label=unit.label,
        part_facts=unit.part_facts,
        bucket_inputs_reference=bucket_ref,
        settings=ctx.settings,
    )
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_1_5_PRE_BUILD_REASONING, StepEventStatus.COMPLETED)
    update = {"units": units}
    await _persist_snapshot(ctx, state, update)
    return update


async def propose_parameters_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    units = list(state.units)
    unit = units[state.current_unit_index]
    if unit.proposed_parameters is not None:
        return {}
    assert unit.part_facts is not None and unit.pre_build_reasoning is not None

    deep_dive_summary = None
    if unit.pre_build_reasoning.complexity.deep_dive_required and unit.deep_dive is None:
        unit.current_step = WorkflowStep.STEP_2_5_DEEP_DIVE
        unit.trace = _trace_list(
            unit.trace,
            WorkflowStep.STEP_2_5_DEEP_DIVE,
            StepEventStatus.SKIPPED,
            detail="not implemented in v1 — see assumptions",
        )

    unit.current_step = WorkflowStep.STEP_2_PROPOSE_PARAMETERS
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_2_PROPOSE_PARAMETERS, StepEventStatus.STARTED)
    bucket_ref = _read_reference("bucket_inputs_by_process.md")
    benchmarks_ref = _read_reference("benchmarks.md")
    unit.proposed_parameters = await model_client.propose_parameters(
        ctx.chat_client,
        component_label=unit.label,
        part_facts=unit.part_facts,
        pre_build=unit.pre_build_reasoning,
        bucket_inputs_reference=bucket_ref,
        benchmarks_reference=benchmarks_ref,
        deep_dive_summary=deep_dive_summary,
        settings=ctx.settings,
    )
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_2_PROPOSE_PARAMETERS, StepEventStatus.COMPLETED)
    update = {"units": units}
    await _persist_snapshot(ctx, state, update)
    return update


async def research_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    units = list(state.units)
    unit = units[state.current_unit_index]
    if unit.cost_build is not None:
        return {}  # Step 3 onward already done (resume case)
    assert unit.proposed_parameters is not None

    unit.current_step = WorkflowStep.STEP_3_RESEARCH
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_3_RESEARCH, StepEventStatus.STARTED)
    targets = select_research_targets(unit.proposed_parameters, unit.supplier.country if unit.supplier else None)
    if targets:
        researched = await run_research(ctx.settings, ctx.chat_client, targets)
        unit.proposed_parameters = merge_researched_parameters(unit.proposed_parameters, researched)
    unit.trace = _trace_list(
        unit.trace,
        WorkflowStep.STEP_3_RESEARCH,
        StepEventStatus.COMPLETED,
        detail=f"{len(targets)} parameter(s) researched",
    )
    update = {"units": units}
    await _persist_snapshot(ctx, state, update)
    return update


async def build_excel_and_sanity_gate_node(state: Job, runtime: Any) -> dict[str, Any]:
    """Steps 4 and 4.5 together, in one node — SKILL.md couples them tightly (4.5 checks
    the exact output 4 just built), and a prior two-node split rebuilt the same Excel
    file twice (once per node) since the row maps build_calc_model_excel returns aren't
    JSON-serializable Job state to pass between separate nodes. One node, one build.
    """
    ctx: GraphContext = runtime.context
    units = list(state.units)
    unit = units[state.current_unit_index]
    if unit.cost_build is not None:
        return {}
    assert (
        unit.part_facts is not None
        and unit.proposed_parameters is not None
        and unit.pre_build_reasoning is not None
        and unit.supplier is not None
    )

    unit.current_step = WorkflowStep.STEP_4_BUILD_EXCEL
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_4_BUILD_EXCEL, StepEventStatus.STARTED)
    today = dt.date.today()
    supplier_short = _short_name(unit.supplier.supplier_name if unit.supplier else unit.label)
    calc_path = f"/tmp/{calc_model_filename(state.material_id, supplier_short, today, 1)}"
    general_info_rows = [
        ("Material ID", state.material_id),
        ("Material name", unit.part_facts.component_name),
        ("Plant", unit.supplier.hager_entity if unit.supplier else "unknown"),
        ("Incumbent supplier", unit.supplier.supplier_name if unit.supplier else "unknown"),
        ("Process", unit.proposed_parameters.process),
        ("Run-ID", run_id(state.material_id, supplier_short, today, 1)),
    ]
    _out_path, param_row_map, calc_row_map = build_calc_model_excel(
        component_title=unit.part_facts.component_name,
        general_info_rows=general_info_rows,
        proposed=unit.proposed_parameters,
        supplier=unit.supplier,
        out_path=calc_path,
    )
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_4_BUILD_EXCEL, StepEventStatus.COMPLETED)

    unit.current_step = WorkflowStep.STEP_4_5_SANITY_GATE
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_4_5_SANITY_GATE, StepEventStatus.STARTED)
    recalc_result = recalc_and_check(
        calc_path, param_row_map=param_row_map, calc_row_map=calc_row_map, proposed=unit.proposed_parameters
    )
    unit.cost_build = recalc_result.calc_values_eur
    unit.sanity_gate = run_sanity_gate(
        proposed=unit.proposed_parameters,
        pre_build=unit.pre_build_reasoning,
        current_price_eur=unit.cost_build["current_price_eur"],
        historical_priors=state.historical_priors or None,
        supplier_count=len([u for u in state.units if not u.is_rollup]),
        unit_count=len([u for u in state.units if not u.is_rollup]),
    )

    if unit.sanity_gate.blocks_slide_output:
        unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_4_5_SANITY_GATE, StepEventStatus.FAILED, detail="RED")
        update = {
            "units": units,
            "pending_question": PendingQuestion(
                reason=NeedsInputReason.SANITY_GATE_RED,
                question=(
                    f"[{unit.label}] Sanity gate is RED: "
                    f"{unit.sanity_gate.reasonability_note} / {unit.sanity_gate.action}"
                ),
            ),
        }
        await _persist_snapshot(ctx, state, update)
        return update

    unit.trace = _trace_list(
        unit.trace,
        WorkflowStep.STEP_4_5_SANITY_GATE,
        StepEventStatus.COMPLETED,
        detail=unit.sanity_gate.overall_status.value,
    )
    unit.files = [
        *unit.files,
        GeneratedFile(
            name=calc_model_filename(state.material_id, supplier_short, today, 1),
            kind="calc_model",
            local_path=calc_path,
        ),
    ]
    update = {"units": units}
    await _persist_snapshot(ctx, state, update)
    return update


def route_after_sanity_gate(state: Job) -> Literal["await_input", "slide_values"]:
    return "await_input" if state.pending_question is not None else "slide_values"


async def slide_values_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    units = list(state.units)
    unit = units[state.current_unit_index]
    if unit.insights is not None:
        return {}
    assert (
        unit.part_facts is not None
        and unit.proposed_parameters is not None
        and unit.cost_build is not None
        and unit.supplier is not None
    )

    unit.current_step = WorkflowStep.STEP_5_SLIDE_VALUES
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_5_SLIDE_VALUES, StepEventStatus.STARTED)
    sensitivity_drivers = compute_sensitivity(unit.proposed_parameters)
    slide_path = f"/tmp/{slide_values_filename(state.material_id)}"
    build_slide_values_excel(
        material_id=state.material_id,
        material_name=unit.part_facts.component_name,
        category="",
        sub_category="",
        supplier=unit.supplier,
        cost_build=unit.cost_build,
        proposed=unit.proposed_parameters,
        sensitivity_drivers=sensitivity_drivers,
        date_str=dt.date.today().strftime("%B %Y"),
        out_path=slide_path,
    )
    unit.files = [
        *unit.files,
        GeneratedFile(name=slide_values_filename(state.material_id), kind="slide_values", local_path=slide_path),
    ]
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_5_SLIDE_VALUES, StepEventStatus.COMPLETED)
    update = {"units": units}
    await _persist_snapshot(ctx, state, update)
    return update


async def insights_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    units = list(state.units)
    unit = units[state.current_unit_index]
    if unit.insights is not None:
        return {}
    assert (
        unit.part_facts is not None
        and unit.proposed_parameters is not None
        and unit.cost_build is not None
        and unit.sanity_gate is not None
        and unit.supplier is not None
    )

    unit.current_step = WorkflowStep.STEP_5_5_6_INSIGHTS
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_5_5_6_INSIGHTS, StepEventStatus.STARTED)
    unit.insights = await run_write_insights(
        client=ctx.chat_client,
        component_label=unit.label,
        language=state.language,
        cost_build=unit.cost_build,
        sanity_gate=unit.sanity_gate,
        proposed=unit.proposed_parameters,
        settings=ctx.settings,
    )
    sensitivity_drivers = compute_sensitivity(unit.proposed_parameters)
    unit.chat_blocks = build_chat_blocks(
        material_id=state.material_id,
        material_description=unit.part_facts.component_name,
        supplier=unit.supplier,
        category_hierarchy={},
        cost_build=unit.cost_build,
        proposed=unit.proposed_parameters,
        sensitivity_drivers=sensitivity_drivers,
        insights=unit.insights,
    )
    unit.trace = _trace_list(unit.trace, WorkflowStep.STEP_5_5_6_INSIGHTS, StepEventStatus.COMPLETED)
    unit.status = JobStatus.DONE
    update = {"units": units}
    await _persist_snapshot(ctx, state, update)
    return update


async def advance_unit_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    update = {"current_unit_index": state.current_unit_index + 1}
    await _persist_snapshot(ctx, state, update)
    return update


def route_after_advance_unit(state: Job) -> Literal["extract_facts", "rollup_and_handoff"]:
    remaining = any(not u.is_rollup and u.status != JobStatus.DONE for u in state.units[state.current_unit_index :])
    return "extract_facts" if remaining else "rollup_and_handoff"


async def rollup_and_handoff_node(state: Job, runtime: Any) -> dict[str, Any]:
    ctx: GraphContext = runtime.context
    units = list(state.units)
    for i, unit in enumerate(units):
        if unit.is_rollup and unit.status != JobStatus.DONE:
            children = [(u, 1.0) for u in units if u.unit_id in unit.child_unit_ids]
            unit.cost_build = compute_rollup(children)
            unit.status = JobStatus.DONE
            units[i] = unit

    trace = _trace_list(state.trace, WorkflowStep.STEP_7_HANDOFF, StepEventStatus.STARTED)
    if ctx.skip_upload:
        cross_supplier_table = build_cross_supplier_table(units)
    else:
        for unit in units:
            for f in unit.files:
                if f.local_path and f.sharepoint_url is None:
                    uploaded = await upload_unit_files(
                        credential=ctx.credential,
                        settings=ctx.settings,
                        unit=unit,
                        calc_model_local_path=f.local_path if f.kind == "calc_model" else "",
                        calc_model_filename_=f.name if f.kind == "calc_model" else "",
                        slide_values_local_path=f.local_path if f.kind == "slide_values" else "",
                        slide_values_filename_=f.name if f.kind == "slide_values" else "",
                    )
                    for g in uploaded:
                        if g.kind == f.kind:
                            f.sharepoint_url = g.sharepoint_url
        cross_supplier_table = build_cross_supplier_table(units)

    update = {
        "units": units,
        "cross_supplier_table": cross_supplier_table,
        "current_step": WorkflowStep.DONE,
        "status": JobStatus.DONE,
        "pending_question": None,
        "step_started_at": None,
        "trace": _trace_list(trace, WorkflowStep.STEP_7_HANDOFF, StepEventStatus.COMPLETED),
    }
    await _persist_snapshot(ctx, state, update)
    return update


# ── Human-in-the-loop ─────────────────────────────────────────────────────────────


async def await_input_node(state: Job, runtime: Any) -> dict[str, Any]:
    """The only node that calls interrupt() — kept minimal and side-effect-free before
    the call so a resume (which re-executes this node from the top) never repeats a real
    model/API call. Mirrors the old engine.py's answer_job exactly for what each pause
    reason's answer means; see NeedsInputReason for the full enum.
    """
    ctx: GraphContext = runtime.context
    pending = state.pending_question
    assert pending is not None
    answer_text: str = interrupt(
        {"reason": pending.reason.value, "question": pending.question, "context": pending.context}
    )

    if pending.reason == NeedsInputReason.NO_SPEND_ROW:
        volume_s, spend_s, price_s = (part.strip() for part in answer_text.split(","))
        manual_supplier = SupplierRow(
            supplier_name="MANUAL OVERRIDE",
            hager_entity="unknown",
            unit_of_measure="EA",
            annual_volume=float(volume_s),
            annual_spend=float(spend_s),
            current_avg_price=float(price_s),
            supplier_type=SupplierType.UNKNOWN,
            is_manual_override=True,
        )
        update = {
            "spend_lookup": SpendLookupResult(
                match_type=MatchType.MANUAL_OVERRIDE, base_id=state.material_id, suppliers=[manual_supplier]
            ),
            "units": [JobUnit(label=manual_supplier.supplier_name, supplier=manual_supplier)],
            "pending_question": None,
        }
    else:
        # Informational answer (missing critical field, illegible BOM/drawing, a RED
        # sanity gate, an uncertain discovery-time match): fold it into the document
        # text, then reset whichever per-unit field is already set-but-incomplete so the
        # resume guards above ("if unit.X is not None: return {}") don't skip the step
        # that actually needs to redo its work with the human's answer in context.
        units = list(state.units)
        for i, unit in enumerate(units):
            if unit.part_facts is not None and unit.part_facts.missing_info:
                unit.part_facts = None
                units[i] = unit
            elif unit.sanity_gate is not None and unit.sanity_gate.blocks_slide_output:
                unit.cost_build = None
                unit.sanity_gate = None
                units[i] = unit
        update = {
            "discovery_documents": [
                *state.discovery_documents,
                DiscoveryDocument(filename="user_clarification.txt", text=answer_text),
            ],
            "units": units,
            "pending_question": None,
        }
    await _persist_snapshot(ctx, state, update)
    return update


def route_after_await_input(state: Job) -> Literal["discovery", "extract_facts"]:
    # A NO_SPEND_ROW answer builds spend_lookup itself with no prior discovery to retry;
    # everything else either still needs discovery re-run (the pre-existing gap noted in
    # the module docstring) or needs the current unit's extract_facts re-run.
    return "extract_facts" if state.spend_lookup is not None else "discovery"


# ── Graph assembly ───────────────────────────────────────────────────────────────


def build_graph() -> StateGraph[Job, GraphContext, Job, Job]:
    graph = StateGraph(Job, context_schema=GraphContext)
    graph.add_node("discovery", discovery_node)
    graph.add_node("extract_facts", extract_facts_node)
    graph.add_node("pre_build_reasoning", pre_build_reasoning_node)
    graph.add_node("propose_parameters", propose_parameters_node)
    graph.add_node("research", research_node)
    graph.add_node("build_excel_and_sanity_gate", build_excel_and_sanity_gate_node)
    graph.add_node("slide_values", slide_values_node)
    graph.add_node("insights", insights_node)
    graph.add_node("advance_unit", advance_unit_node)
    graph.add_node("rollup_and_handoff", rollup_and_handoff_node)
    graph.add_node("await_input", await_input_node)

    graph.add_conditional_edges(START, route_from_start, ["discovery", "extract_facts"])
    graph.add_conditional_edges("discovery", route_after_discovery, ["await_input", "extract_facts"])
    graph.add_conditional_edges("extract_facts", route_after_extract_facts, ["await_input", "pre_build_reasoning"])
    graph.add_edge("pre_build_reasoning", "propose_parameters")
    graph.add_edge("propose_parameters", "research")
    graph.add_edge("research", "build_excel_and_sanity_gate")
    graph.add_conditional_edges("build_excel_and_sanity_gate", route_after_sanity_gate, ["await_input", "slide_values"])
    graph.add_edge("slide_values", "insights")
    graph.add_edge("insights", "advance_unit")
    graph.add_conditional_edges("advance_unit", route_after_advance_unit, ["extract_facts", "rollup_and_handoff"])
    graph.add_conditional_edges("await_input", route_after_await_input, ["discovery", "extract_facts"])
    graph.add_edge("rollup_and_handoff", END)
    return graph


# ── run_job / answer_job compatibility facade ────────────────────────────────────
# cli.py, routes/jobs.py, runner.py and recovery.py call these with the exact same
# signatures the old engine.py exposed — they build/compile the graph fresh (cheap;
# LangGraph compilation isn't the expensive part, the model calls are), invoke or
# resume it for this one job's thread, and translate the result back into
# Job.status/pending_question so nothing downstream needs to know a graph is involved.


async def _apply_interrupt_or_terminal(job: Job, ctx: GraphContext, result: dict[str, Any]) -> None:
    interrupts = result.get("__interrupt__")
    if interrupts:
        payload = interrupts[0].value
        job.status = JobStatus.NEEDS_INPUT
        job.pending_question = PendingQuestion(
            reason=NeedsInputReason(payload["reason"]), question=payload["question"], context=payload.get("context")
        )
        await ctx.store.save(job)
        return
    for field, value in result.items():
        if field != "__interrupt__":
            setattr(job, field, value)
    await ctx.store.save(job)


async def run_job(
    job: Job,
    *,
    store: JobStateStore,
    settings: Settings,
    credential: AsyncTokenCredential,
    skip_upload: bool = False,
) -> None:
    job.status = JobStatus.RUNNING
    job.step_started_at = dt.datetime.now(dt.UTC)
    await store.save(job)

    chat_client = model_client.build_chat_client(settings)
    ctx = GraphContext(
        settings=settings, credential=credential, chat_client=chat_client, store=store, skip_upload=skip_upload
    )
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.langgraph_checkpoint_db_path) as checkpointer:
            compiled: CompiledStateGraph[Job, GraphContext, Job, Job] = build_graph().compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": job.job_id}}
            # langgraph's own ainvoke() overload stubs declare context: None on every
            # overload regardless of the compiled graph's actual ContextT — confirmed by
            # reading them; this works correctly at runtime (verified live, including
            # against a real DeepSeek job end to end).
            result = await compiled.ainvoke(job, config=config, context=ctx)  # type: ignore[call-overload]
            await _apply_interrupt_or_terminal(job, ctx, result)
    except Exception as exc:  # noqa: BLE001 - a job-level failure must be captured, not raised into the background task runner
        job.status = JobStatus.FAILED
        job.failure_reason = f"{type(exc).__name__}: {exc}"
        await store.save(job)


async def answer_job(
    job: Job,
    answer_text: str,
    *,
    store: JobStateStore,
    settings: Settings,
    credential: AsyncTokenCredential,
    skip_upload: bool = False,
) -> None:
    if job.pending_question is None:
        raise ValueError(f"Job {job.job_id} has no pending question to answer.")

    job.status = JobStatus.RUNNING
    await store.save(job)
    chat_client = model_client.build_chat_client(settings)
    ctx = GraphContext(
        settings=settings, credential=credential, chat_client=chat_client, store=store, skip_upload=skip_upload
    )
    try:
        async with AsyncSqliteSaver.from_conn_string(settings.langgraph_checkpoint_db_path) as checkpointer:
            compiled: CompiledStateGraph[Job, GraphContext, Job, Job] = build_graph().compile(checkpointer=checkpointer)
            config = {"configurable": {"thread_id": job.job_id}}
            result = await compiled.ainvoke(  # type: ignore[call-overload]
                Command(resume=answer_text), config=config, context=ctx
            )
            await _apply_interrupt_or_terminal(job, ctx, result)
    except Exception as exc:  # noqa: BLE001
        job.status = JobStatus.FAILED
        job.failure_reason = f"{type(exc).__name__}: {exc}"
        await store.save(job)
