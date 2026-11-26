"""Restart recovery — called once from should_cost/main.py's lifespan on startup.

SKILL... no, the task brief: "a job in running state at startup is either resumed from
its last saved step or marked failed with a 'restarted, please retry' reason." The
distinction is whether the job's current_step is in engine.NON_RESUMABLE_STEPS (only
Step 7, the external upload, today) — everything else is a pure function of already-
persisted inputs and safe to simply re-run from the top of run_job, which itself skips
any sub-step whose output is already attached to the job/unit (see engine._process_unit).
"""

from __future__ import annotations

import structlog
from azure.core.credentials_async import AsyncTokenCredential

from should_cost.config import Settings
from should_cost.models.job import JobStatus
from should_cost.state.store import JobStateStore
from should_cost.workflow.graph import NON_RESUMABLE_STEPS
from should_cost.workflow.runner import start_job

logger = structlog.get_logger(__name__)


async def recover_interrupted_jobs(*, store: JobStateStore, settings: Settings, credential: AsyncTokenCredential) -> None:
    running = await store.list_running()
    for job in running:
        if job.current_step in NON_RESUMABLE_STEPS:
            job.status = JobStatus.FAILED
            job.failure_reason = "restarted, please retry"
            await store.save(job)
            logger.warning("job_marked_failed_on_restart", job_id=job.job_id, step=job.current_step.value)
        else:
            logger.info("job_resumed_on_restart", job_id=job.job_id, step=job.current_step.value)
            start_job(job, store=store, settings=settings, credential=credential)
