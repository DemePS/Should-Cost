"""The deterministic workflow orchestrator — plain async code, not an agent loop or a
graph-workflow framework (see docs/design.md §3 and §6 for why).

``run_job`` drives one Job through Steps 0-7, persisting state after every transition so
a restart never loses more than the one in-flight step (``workflow/recovery.py`` handles
what happens to an interrupted job at startup). Model calls happen inside here only
through should_cost.tools.model_client / should_cost.tools.research_agent — this module
never talks to Azure AI Foundry directly, and it never decides *what* a model should
answer, only *when* to ask and what to do with a RED sanity gate, a complexity-flag count,
or a needs_input pause.
"""

from __future__ import annotations

import datetime as dt

from azure.core.credentials_async import AsyncTokenCredential

from should_cost.config import Settings
from should_cost.excel.build import build_calc_model_excel
from should_cost.excel.recalc import recalc_and_check
from should_cost.excel.slide_values import build_slide_values_excel
from should_cost.models.common import SupplierRow
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

# Steps safe to blindly re-run from scratch on restart recovery: every step up to and
# including the sanity gate is a pure function of already-persisted inputs (document
# text, PPE data, model responses already received aren't re-requested — see
# _process_unit, which skips sub-steps whose output is already attached to the unit).
# Only Step 7 (external uploads) is not — a partial upload must not be silently retried
# as if nothing happened.
NON_RESUMABLE_STEPS = {WorkflowStep.STEP_7_HANDOFF}


def _trace(job_or_unit: Job | JobUnit, step: WorkflowStep, status: StepEventStatus, detail: str | None = None) -> None:
    job_or_unit.trace.append(StepEvent(step=step, status=status, detail=detail))


async def _persist(store: JobStateStore, job: Job) -> None:
    job.updated_at = dt.datetime.now(dt.timezone.utc)
    await store.save(job)


async def run_job(
    job: Job,
    *,
    store: JobStateStore,
    settings: Settings,
    credential: AsyncTokenCredential,
    skip_upload: bool = False,
) -> None:
    """``skip_upload=True`` is for should_cost/cli.py's local runner only — it leaves
    Step 7's generated files on local disk (still builds the cross-supplier table) and
    never calls Graph, so a local run genuinely never needs a SharePoint site. The API
    path (should_cost/routes/jobs.py) never passes this — production jobs always upload.
    """
    job.status = JobStatus.RUNNING
    job.step_started_at = dt.datetime.now(dt.timezone.utc)
    await _persist(store, job)

    chat_client = model_client.build_chat_client(settings)
    try:
        if job.spend_lookup is None:
            await _run_step0(job, credential, settings, store)

        for unit in job.units:
            if unit.is_rollup or unit.status == JobStatus.DONE:
                continue
            await _process_unit(unit, job, chat_client=chat_client, credential=credential, settings=settings, store=store)

        for unit in job.units:
            if unit.is_rollup and unit.status != JobStatus.DONE:
                _process_rollup(unit, job)
                unit.status = JobStatus.DONE
                await _persist(store, job)

        job.current_step = WorkflowStep.STEP_7_HANDOFF
        if skip_upload:
            job.cross_supplier_table = build_cross_supplier_table(job.units)
        else:
            await _run_handoff(job, credential, settings)

        job.status = JobStatus.DONE
        job.current_step = WorkflowStep.DONE
        job.pending_question = None
        job.step_started_at = None
        await _persist(store, job)

    except NeedsInputSignal as signal:
        job.status = JobStatus.NEEDS_INPUT
        job.pending_question = PendingQuestion(reason=signal.reason, question=signal.question, context=signal.context)
        await _persist(store, job)

    except Exception as exc:  # noqa: BLE001 - a job-level failure must be captured, not raised into the background task runner
        job.status = JobStatus.FAILED
        job.failure_reason = f"{type(exc).__name__}: {exc}"
        await _persist(store, job)


async def answer_job(
    job: Job,
    answer_text: str,
    *,
    store: JobStateStore,
    settings: Settings,
    credential: AsyncTokenCredential,
    skip_upload: bool = False,
) -> None:
    """POST /api/jobs/{id}/answer — applies a free-text answer to the current pending
    question and resumes. What the answer *means* depends on the pause reason:
    - NO_SPEND_ROW: "<volume>,<spend>,<price>" manual override, applied as a synthetic
      single-supplier SpendLookupResult with is_manual_override on the SupplierRow.
    - MULTI_SUPPLIER_PLAN_CONFIRMATION / UNCERTAIN_PREFIX_MATCH: any non-empty answer is
      treated as confirmation to proceed with the plan already described in the question.
    - Anything else (missing BOM, illegible drawing, missing critical field, a RED sanity
      gate): the answer is appended as additional document text / context for the step
      that raised the question, and that step is re-entered.
    """
    if job.pending_question is None:
        raise ValueError(f"Job {job.job_id} has no pending question to answer.")

    reason = job.pending_question.reason
    if reason == NeedsInputReason.NO_SPEND_ROW:
        volume_s, spend_s, price_s = (part.strip() for part in answer_text.split(","))
        manual_supplier = SupplierRow(
            supplier_name="MANUAL OVERRIDE",
            hager_entity="unknown",
            unit_of_measure="EA",
            annual_volume=float(volume_s),
            annual_spend=float(spend_s),
            current_avg_price=float(price_s),
            supplier_type="unknown",  # type: ignore[arg-type]
            is_manual_override=True,
        )
        from should_cost.models.common import MatchType, SpendLookupResult

        job.spend_lookup = SpendLookupResult(match_type=MatchType.MANUAL_OVERRIDE, base_id=job.material_id, suppliers=[manual_supplier])
        # _run_step0 normally creates units from spend_lookup.suppliers; a manual override
        # bypasses _run_step0 entirely (job.spend_lookup is already set), so it must create
        # the unit itself or the job would reach Step 1 with no units to process.
        job.units = [JobUnit(label=manual_supplier.supplier_name, supplier=manual_supplier)]
    else:
        # Informational answer (missing critical field, illegible BOM/drawing, a RED
        # sanity gate, ...): fold it into the document text, then reset whichever
        # per-unit field is already set-but-incomplete so the step that raised the
        # question actually reruns — _process_unit's "if unit.X is None" resume guards
        # would otherwise treat that step as already done and silently skip it, since the
        # field was assigned before the missing_info/RED check that raised the signal.
        job.discovery_documents.append(DiscoveryDocument(filename="user_clarification.txt", text=answer_text))
        for unit in job.units:
            if unit.part_facts is not None and unit.part_facts.missing_info:
                unit.part_facts = None
            elif unit.sanity_gate is not None and unit.sanity_gate.blocks_slide_output:
                unit.cost_build = None
                unit.sanity_gate = None
    job.pending_question = None
    job.status = JobStatus.RUNNING
    await run_job(job, store=store, settings=settings, credential=credential, skip_upload=skip_upload)


async def _run_step0(job: Job, credential: AsyncTokenCredential, settings: Settings, store: JobStateStore) -> None:
    job.current_step = WorkflowStep.STEP_0_DISCOVERY
    _trace(job, WorkflowStep.STEP_0_DISCOVERY, StepEventStatus.STARTED)
    await _persist(store, job)

    discovery = await run_discovery(material_id=job.material_id, credential=credential, settings=settings)
    job.spend_lookup = discovery.spend_lookup
    job.discovery_documents = [DiscoveryDocument(filename=name, text=text) for name, text in discovery.material_documents]
    job.historical_priors = discovery.historical_priors

    job.units = [JobUnit(label=s.supplier_name, supplier=s) for s in discovery.spend_lookup.suppliers]
    _trace(job, WorkflowStep.STEP_0_DISCOVERY, StepEventStatus.COMPLETED, detail=f"{len(job.units)} supplier unit(s)")
    await _persist(store, job)


async def _process_unit(unit: JobUnit, job: Job, *, chat_client, credential, settings, store: JobStateStore) -> None:
    document_text = "\n\n".join(doc.text for doc in job.discovery_documents)
    ppe_context = unit.supplier.model_dump_json() if unit.supplier else "{}"

    if unit.part_facts is None:
        unit.current_step = WorkflowStep.STEP_1_EXTRACT_FACTS
        _trace(unit, WorkflowStep.STEP_1_EXTRACT_FACTS, StepEventStatus.STARTED)
        unit.part_facts = await model_client.extract_part_facts(
            chat_client, document_text=document_text, ppe_context=ppe_context, settings=settings
        )
        if unit.part_facts.missing_info:
            _trace(unit, WorkflowStep.STEP_1_EXTRACT_FACTS, StepEventStatus.FAILED, detail="missing_info")
            await _persist(store, job)
            raise NeedsInputSignal(
                NeedsInputReason.MISSING_CRITICAL_FIELD,
                f"[{unit.label}] Missing critical fields: {unit.part_facts.missing_info}",
            )
        _trace(unit, WorkflowStep.STEP_1_EXTRACT_FACTS, StepEventStatus.COMPLETED)
        await _persist(store, job)

    if unit.pre_build_reasoning is None:
        unit.current_step = WorkflowStep.STEP_1_5_PRE_BUILD_REASONING
        _trace(unit, WorkflowStep.STEP_1_5_PRE_BUILD_REASONING, StepEventStatus.STARTED)
        bucket_ref = _read_reference("bucket_inputs_by_process.md")
        unit.pre_build_reasoning = await model_client.pre_build_reasoning(
            chat_client,
            component_label=unit.label,
            part_facts=unit.part_facts,
            bucket_inputs_reference=bucket_ref,
            settings=settings,
        )
        _trace(unit, WorkflowStep.STEP_1_5_PRE_BUILD_REASONING, StepEventStatus.COMPLETED)
        await _persist(store, job)

    if unit.proposed_parameters is None:
        deep_dive_summary = None
        if unit.pre_build_reasoning.complexity.deep_dive_required and unit.deep_dive is None:
            unit.current_step = WorkflowStep.STEP_2_5_DEEP_DIVE
            _trace(unit, WorkflowStep.STEP_2_5_DEEP_DIVE, StepEventStatus.STARTED)
            # Step 2.5 reuses the propose_parameters call with a deep-dive-only instruction
            # folded into the same structured-output contract is out of scope for a first
            # cut; see the final assumptions list — deep_dive is left None here and the
            # complexity flags still reach propose_parameters as context either way.
            _trace(unit, WorkflowStep.STEP_2_5_DEEP_DIVE, StepEventStatus.SKIPPED, detail="not implemented in v1 — see assumptions")

        unit.current_step = WorkflowStep.STEP_2_PROPOSE_PARAMETERS
        _trace(unit, WorkflowStep.STEP_2_PROPOSE_PARAMETERS, StepEventStatus.STARTED)
        bucket_ref = _read_reference("bucket_inputs_by_process.md")
        benchmarks_ref = _read_reference("benchmarks.md")
        unit.proposed_parameters = await model_client.propose_parameters(
            chat_client,
            component_label=unit.label,
            part_facts=unit.part_facts,
            pre_build=unit.pre_build_reasoning,
            bucket_inputs_reference=bucket_ref,
            benchmarks_reference=benchmarks_ref,
            deep_dive_summary=deep_dive_summary,
            settings=settings,
        )
        _trace(unit, WorkflowStep.STEP_2_PROPOSE_PARAMETERS, StepEventStatus.COMPLETED)
        await _persist(store, job)

    if unit.cost_build is None:
        unit.current_step = WorkflowStep.STEP_3_RESEARCH
        _trace(unit, WorkflowStep.STEP_3_RESEARCH, StepEventStatus.STARTED)
        targets = select_research_targets(unit.proposed_parameters, unit.supplier.country if unit.supplier else None)
        if targets:
            researched = await run_research(settings, chat_client, targets)
            unit.proposed_parameters = merge_researched_parameters(unit.proposed_parameters, researched)
        _trace(unit, WorkflowStep.STEP_3_RESEARCH, StepEventStatus.COMPLETED, detail=f"{len(targets)} parameter(s) researched")
        await _persist(store, job)

        unit.current_step = WorkflowStep.STEP_4_BUILD_EXCEL
        _trace(unit, WorkflowStep.STEP_4_BUILD_EXCEL, StepEventStatus.STARTED)
        today = dt.date.today()
        supplier_short = _short_name(unit.supplier.supplier_name if unit.supplier else unit.label)
        calc_path = f"/tmp/{calc_model_filename(job.material_id, supplier_short, today, 1)}"
        general_info_rows = [
            ("Material ID", job.material_id),
            ("Material name", unit.part_facts.component_name),
            ("Plant", unit.supplier.hager_entity if unit.supplier else "unknown"),
            ("Incumbent supplier", unit.supplier.supplier_name if unit.supplier else "unknown"),
            ("Process", unit.proposed_parameters.process),
            ("Run-ID", run_id(job.material_id, supplier_short, today, 1)),
        ]
        _out_path, param_row_map, calc_row_map = build_calc_model_excel(
            component_title=unit.part_facts.component_name,
            general_info_rows=general_info_rows,
            proposed=unit.proposed_parameters,
            supplier=unit.supplier,
            out_path=calc_path,
        )
        _trace(unit, WorkflowStep.STEP_4_BUILD_EXCEL, StepEventStatus.COMPLETED)
        await _persist(store, job)

        unit.current_step = WorkflowStep.STEP_4_5_SANITY_GATE
        _trace(unit, WorkflowStep.STEP_4_5_SANITY_GATE, StepEventStatus.STARTED)
        recalc_result = recalc_and_check(
            calc_path, param_row_map=param_row_map, calc_row_map=calc_row_map, proposed=unit.proposed_parameters
        )
        unit.cost_build = recalc_result.calc_values_eur
        unit.sanity_gate = run_sanity_gate(
            proposed=unit.proposed_parameters,
            pre_build=unit.pre_build_reasoning,
            current_price_eur=unit.cost_build["current_price_eur"],
            historical_priors=job.historical_priors or None,
            supplier_count=len([u for u in job.units if not u.is_rollup]),
            unit_count=len([u for u in job.units if not u.is_rollup]),
        )
        if unit.sanity_gate.blocks_slide_output:
            _trace(unit, WorkflowStep.STEP_4_5_SANITY_GATE, StepEventStatus.FAILED, detail="RED")
            await _persist(store, job)
            raise NeedsInputSignal(
                NeedsInputReason.SANITY_GATE_RED,
                f"[{unit.label}] Sanity gate is RED: {unit.sanity_gate.reasonability_note} / {unit.sanity_gate.action}",
            )
        _trace(unit, WorkflowStep.STEP_4_5_SANITY_GATE, StepEventStatus.COMPLETED, detail=unit.sanity_gate.overall_status.value)
        unit.files.append(GeneratedFile(name=calc_model_filename(job.material_id, supplier_short, today, 1), kind="calc_model", local_path=calc_path))
        await _persist(store, job)

    if unit.insights is None:
        unit.current_step = WorkflowStep.STEP_5_SLIDE_VALUES
        _trace(unit, WorkflowStep.STEP_5_SLIDE_VALUES, StepEventStatus.STARTED)
        sensitivity_drivers = compute_sensitivity(unit.proposed_parameters)
        supplier_short = _short_name(unit.supplier.supplier_name if unit.supplier else unit.label)
        slide_path = f"/tmp/{slide_values_filename(job.material_id)}"
        build_slide_values_excel(
            material_id=job.material_id,
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
        unit.files.append(GeneratedFile(name=slide_values_filename(job.material_id), kind="slide_values", local_path=slide_path))
        _trace(unit, WorkflowStep.STEP_5_SLIDE_VALUES, StepEventStatus.COMPLETED)
        await _persist(store, job)

        unit.current_step = WorkflowStep.STEP_5_5_6_INSIGHTS
        _trace(unit, WorkflowStep.STEP_5_5_6_INSIGHTS, StepEventStatus.STARTED)
        unit.insights = await run_write_insights(
            client=chat_client,
            component_label=unit.label,
            language=job.language,
            cost_build=unit.cost_build,
            sanity_gate=unit.sanity_gate,
            proposed=unit.proposed_parameters,
            settings=settings,
        )
        unit.chat_blocks = build_chat_blocks(
            material_id=job.material_id,
            material_description=unit.part_facts.component_name,
            supplier=unit.supplier,
            category_hierarchy={},
            cost_build=unit.cost_build,
            proposed=unit.proposed_parameters,
            sensitivity_drivers=sensitivity_drivers,
            insights=unit.insights,
        )
        _trace(unit, WorkflowStep.STEP_5_5_6_INSIGHTS, StepEventStatus.COMPLETED)
        unit.status = JobStatus.DONE
        await _persist(store, job)


def _process_rollup(rollup_unit: JobUnit, job: Job) -> None:
    children = [(u, 1.0) for u in job.units if u.unit_id in rollup_unit.child_unit_ids]
    rollup_unit.cost_build = compute_rollup(children)


async def _run_handoff(job: Job, credential: AsyncTokenCredential, settings: Settings) -> None:
    _trace(job, WorkflowStep.STEP_7_HANDOFF, StepEventStatus.STARTED)
    for unit in job.units:
        for f in unit.files:
            if f.local_path and f.sharepoint_url is None:
                uploaded = await upload_unit_files(
                    credential=credential,
                    settings=settings,
                    unit=unit,
                    calc_model_local_path=f.local_path if f.kind == "calc_model" else "",
                    calc_model_filename_=f.name if f.kind == "calc_model" else "",
                    slide_values_local_path=f.local_path if f.kind == "slide_values" else "",
                    slide_values_filename_=f.name if f.kind == "slide_values" else "",
                )
                for g in uploaded:
                    if g.kind == f.kind:
                        f.sharepoint_url = g.sharepoint_url
    job.cross_supplier_table = build_cross_supplier_table(job.units)
    _trace(job, WorkflowStep.STEP_7_HANDOFF, StepEventStatus.COMPLETED)


def _short_name(supplier_name: str) -> str:
    return "".join(ch for ch in supplier_name if ch.isalnum())[:12] or "Supplier"


def _read_reference(filename: str) -> str:
    from pathlib import Path

    # engine.py -> workflow -> should_cost -> backend -> repo root (parents[3])
    skill_dir = Path(__file__).resolve().parents[3] / "skill" / "hager-should-cost-builder" / "references"
    return (skill_dir / filename).read_text(encoding="utf-8")
