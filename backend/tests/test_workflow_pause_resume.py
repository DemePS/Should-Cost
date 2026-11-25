"""Job pause/resume: the full queued -> needs_input -> answer -> running -> done path
through the real workflow/engine.py orchestrator, with every model/Excel-layer function
stubbed (this file tests the state machine, not the business logic those layers already
have their own tests for).
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from should_cost.models.common import Bucket, Confidence, SanityStatus
from should_cost.models.job import Job, JobStatus, NeedsInputReason
from should_cost.models.workflow import AssemblyType, BucketShareCheck, CalibrationCheck, Insights, PartFacts, SanityGateResult
from should_cost.state.store import InMemoryJobStateStore
from should_cost.workflow import engine
from should_cost.workflow.signals import NeedsInputSignal

from tests.factories import make_insights, make_pre_build_reasoning, make_proposed_parameters

FAKE_FACTS = PartFacts(assembly_type=AssemblyType.SINGLE_COMPONENT, component_name="Test bracket")
FAKE_PRE_BUILD = make_pre_build_reasoning()
FAKE_PROPOSED = make_proposed_parameters()
FAKE_INSIGHTS: Insights = make_insights()
FAKE_SANITY_GATE = SanityGateResult(
    reasonability_status=SanityStatus.GREEN,
    reasonability_note="ok",
    impact_pct=10.0,
    impact_status=SanityStatus.GREEN,
    bucket_checks=[
        BucketShareCheck(bucket=b, share_pct=20, target_low_pct=10, target_high_pct=70, status=SanityStatus.GREEN) for b in Bucket
    ],
    calibration_checks=[CalibrationCheck(rule_id="C1", description="d", status=SanityStatus.GREEN, note="n")],
    historical_comparison_note="none",
    hypothesis_match=True,
    hypothesis_note="ok",
    overall_status=SanityStatus.GREEN,
    action="Proceed.",
)
FAKE_RECALC_RESULT = type(
    "FakeRecalcResult",
    (),
    {
        "calc_values_eur": {
            "material_eur": 0.02,
            "conversion_eur": 0.03,
            "manufacturing_costs_eur": 0.05,
            "pl_eur": 0.002,
            "should_cost_eur": 0.06,
            "current_price_eur": 0.08,
            "impact_eur": 0.02,
        },
        "warnings": [],
    },
)()


@pytest.fixture
def settings():
    from should_cost.config import get_settings

    get_settings.cache_clear()
    return get_settings()


def _patch_downstream():
    return (
        patch("should_cost.workflow.engine.model_client.build_chat_client", return_value=object()),
        patch("should_cost.workflow.engine.model_client.extract_part_facts", new=AsyncMock(return_value=FAKE_FACTS)),
        patch("should_cost.workflow.engine.model_client.pre_build_reasoning", new=AsyncMock(return_value=FAKE_PRE_BUILD)),
        patch("should_cost.workflow.engine.model_client.propose_parameters", new=AsyncMock(return_value=FAKE_PROPOSED)),
        patch("should_cost.workflow.engine.select_research_targets", return_value=[]),
        patch(
            "should_cost.workflow.engine.build_calc_model_excel",
            return_value=("/tmp/fake.xlsx", {n: n + 3 for n in range(1, 8)}, {}),
        ),
        patch("should_cost.workflow.engine.recalc_and_check", return_value=FAKE_RECALC_RESULT),
        patch("should_cost.workflow.engine.run_sanity_gate", return_value=FAKE_SANITY_GATE),
        patch("should_cost.workflow.engine.compute_sensitivity", return_value=[]),
        patch("should_cost.workflow.engine.build_slide_values_excel", return_value="/tmp/fake_slide.xlsx"),
        patch("should_cost.workflow.engine.run_write_insights", new=AsyncMock(return_value=FAKE_INSIGHTS)),
        patch("should_cost.workflow.engine.upload_unit_files", new=AsyncMock(return_value=[])),
    )


async def _run_with_patches(coro_factory):
    patchers = _patch_downstream()
    for p in patchers:
        p.start()
    try:
        await coro_factory()
    finally:
        for p in patchers:
            p.stop()


@pytest.mark.asyncio
async def test_needs_input_pauses_and_persists(settings) -> None:
    store = InMemoryJobStateStore()
    job = Job(material_id="TEST001", requested_by="test")
    await store.save(job)

    with patch(
        "should_cost.workflow.engine.run_discovery",
        new=AsyncMock(side_effect=NeedsInputSignal(NeedsInputReason.NO_SPEND_ROW, "no spend row found")),
    ):
        await engine.run_job(job, store=store, settings=settings, credential=object())

    reloaded = await store.load(job.job_id)
    assert reloaded.status == JobStatus.NEEDS_INPUT
    assert reloaded.pending_question is not None
    assert reloaded.pending_question.reason == NeedsInputReason.NO_SPEND_ROW


@pytest.mark.asyncio
async def test_answer_resumes_and_completes(settings) -> None:
    store = InMemoryJobStateStore()
    job = Job(material_id="TEST001", requested_by="test")
    await store.save(job)

    with patch(
        "should_cost.workflow.engine.run_discovery",
        new=AsyncMock(side_effect=NeedsInputSignal(NeedsInputReason.NO_SPEND_ROW, "no spend row found")),
    ):
        await engine.run_job(job, store=store, settings=settings, credential=object())
    job = await store.load(job.job_id)
    assert job.status == JobStatus.NEEDS_INPUT

    async def resume():
        await engine.answer_job(job, "100000,8000,0.08", store=store, settings=settings, credential=object())

    await _run_with_patches(resume)

    final = await store.load(job.job_id)
    assert final.status == JobStatus.DONE, final.failure_reason
    assert len(final.units) == 1
    unit = final.units[0]
    assert unit.cost_build is not None
    assert unit.insights is not None
    # Trace must show the full step sequence, started then completed, for the resumed unit.
    steps_seen = [e.step.value for e in unit.trace]
    assert steps_seen == sorted(steps_seen, key=steps_seen.index)  # no reordering surprises
    assert "step_5_5_6_insights" in steps_seen


@pytest.mark.asyncio
async def test_sanity_gate_red_pauses_instead_of_failing(settings) -> None:  # noqa: ARG001 - settings fixture ensures env vars are set
    store = InMemoryJobStateStore()
    job = Job(material_id="TEST001", requested_by="test")
    job.spend_lookup = None

    red_gate = FAKE_SANITY_GATE.model_copy(update={"overall_status": SanityStatus.RED, "action": "Do not produce slide output."})

    from should_cost.models.common import SpendLookupResult, SupplierRow, SupplierType, MatchType

    job.spend_lookup = SpendLookupResult(
        match_type=MatchType.EXACT,
        base_id="TEST001",
        suppliers=[
            SupplierRow(
                supplier_name="Test Supplier",
                hager_entity="Hager DE",
                unit_of_measure="EA",
                annual_volume=1000,
                annual_spend=100,
                current_avg_price=0.1,
                supplier_type=SupplierType.MANUFACTURER,
            )
        ],
    )
    from should_cost.models.job import JobUnit

    job.units = [JobUnit(label="Test Supplier", supplier=job.spend_lookup.suppliers[0])]
    await store.save(job)

    with patch("should_cost.workflow.engine.model_client.build_chat_client", return_value=object()), \
         patch("should_cost.workflow.engine.model_client.extract_part_facts", new=AsyncMock(return_value=FAKE_FACTS)), \
         patch("should_cost.workflow.engine.model_client.pre_build_reasoning", new=AsyncMock(return_value=FAKE_PRE_BUILD)), \
         patch("should_cost.workflow.engine.model_client.propose_parameters", new=AsyncMock(return_value=FAKE_PROPOSED)), \
         patch("should_cost.workflow.engine.select_research_targets", return_value=[]), \
         patch("should_cost.workflow.engine.build_calc_model_excel", return_value=("/tmp/fake.xlsx", {n: n + 3 for n in range(1, 8)}, {})), \
         patch("should_cost.workflow.engine.recalc_and_check", return_value=FAKE_RECALC_RESULT), \
         patch("should_cost.workflow.engine.run_sanity_gate", return_value=red_gate):
        await engine.run_job(job, store=store, settings=settings, credential=object())

    final = await store.load(job.job_id)
    assert final.status == JobStatus.NEEDS_INPUT
    assert final.pending_question.reason == NeedsInputReason.SANITY_GATE_RED
