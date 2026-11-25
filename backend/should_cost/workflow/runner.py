"""Background execution — asyncio tasks inside the same uvicorn process (design.md §6:
no separate worker/queue in v1; this caps concurrency to what one App Service instance
can hold in memory, which is an accepted v1 limitation, not solved here).
"""

from __future__ import annotations

import asyncio

from azure.core.credentials_async import AsyncTokenCredential

from should_cost.config import Settings
from should_cost.models.job import Job
from should_cost.state.store import JobStateStore
from should_cost.workflow.engine import run_job

_background_tasks: set[asyncio.Task] = set()


def start_job(job: Job, *, store: JobStateStore, settings: Settings, credential: AsyncTokenCredential) -> None:
    task = asyncio.create_task(run_job(job, store=store, settings=settings, credential=credential))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)


def start_resume(job: Job, answer_text: str, *, store: JobStateStore, settings: Settings, credential: AsyncTokenCredential) -> None:
    from should_cost.workflow.engine import answer_job

    task = asyncio.create_task(answer_job(job, answer_text, store=store, settings=settings, credential=credential))
    _background_tasks.add(task)
    task.add_done_callback(_background_tasks.discard)
