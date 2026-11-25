"""POST /api/jobs, GET /api/jobs, GET /api/jobs/{id}, POST /api/jobs/{id}/answer,
GET /api/jobs/{id}/files/{name}.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from azure.core.credentials_async import AsyncTokenCredential
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel

from should_cost.auth import CurrentUser, current_user
from should_cost.config import Settings
from should_cost.graph import client as graph
from should_cost.models.job import Job, JobStatus
from should_cost.state.store import JobNotFoundError, JobStateStore
from should_cost.workflow.runner import start_job, start_resume

router = APIRouter(tags=["jobs"])


def get_store(request: Request) -> JobStateStore:
    return request.app.state.store


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings


def get_credential(request: Request) -> AsyncTokenCredential:
    return request.app.state.credential


class CreateJobRequest(BaseModel):
    material_id: str
    language: str = "en"


class CreateJobResponse(BaseModel):
    job_id: str


class AnswerRequest(BaseModel):
    answer: str


@router.post("/jobs", response_model=CreateJobResponse)
async def create_job(
    body: CreateJobRequest,
    store: JobStateStore = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
    credential: AsyncTokenCredential = Depends(get_credential),
    user: CurrentUser = Depends(current_user),
) -> CreateJobResponse:
    job = Job(material_id=body.material_id, language=body.language, requested_by=user.id)
    await store.save(job)
    start_job(job, store=store, settings=settings, credential=credential)
    return CreateJobResponse(job_id=job.job_id)


@router.get("/jobs")
async def list_jobs(store: JobStateStore = Depends(get_store)) -> list[dict]:
    jobs = await store.list_recent()
    return [
        {
            "job_id": j.job_id,
            "material_id": j.material_id,
            "status": j.status.value,
            "current_step": j.current_step.value,
            "updated_at": j.updated_at.isoformat(),
        }
        for j in jobs
    ]


@router.get("/jobs/{job_id}", response_model=Job)
async def get_job(job_id: str, store: JobStateStore = Depends(get_store)) -> Job:
    try:
        return await store.load(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found") from None


@router.post("/jobs/{job_id}/answer")
async def answer_job_route(
    job_id: str,
    body: AnswerRequest,
    store: JobStateStore = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
    credential: AsyncTokenCredential = Depends(get_credential),
) -> dict[str, str]:
    try:
        job = await store.load(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found") from None
    if job.status != JobStatus.NEEDS_INPUT:
        raise HTTPException(status_code=409, detail=f"Job {job_id!r} is not waiting for input (status={job.status.value})")
    start_resume(job, body.answer, store=store, settings=settings, credential=credential)
    return {"status": "resuming"}


@router.get("/jobs/{job_id}/files/{name}")
async def get_job_file(
    job_id: str,
    name: str,
    store: JobStateStore = Depends(get_store),
    settings: Settings = Depends(get_settings_dep),
    credential: AsyncTokenCredential = Depends(get_credential),
) -> FileResponse:
    try:
        job = await store.load(job_id)
    except JobNotFoundError:
        raise HTTPException(status_code=404, detail=f"Job {job_id!r} not found") from None

    matched = next((f for unit in job.units for f in unit.files if f.name == name), None)
    if matched is None:
        raise HTTPException(status_code=404, detail=f"No file named {name!r} on job {job_id!r}")

    if matched.local_path and os.path.exists(matched.local_path):
        return FileResponse(matched.local_path, filename=matched.name)

    if not matched.sharepoint_url:
        raise HTTPException(status_code=410, detail=f"File {name!r} is no longer available (not yet uploaded, and the local copy is gone)")

    # Local copy gone (e.g. container restarted since the job ran) — re-fetch from
    # SharePoint on demand rather than failing; the output folder is where Step 7 put it.
    tmp_dir = tempfile.mkdtemp(prefix="should-cost-dl-")
    all_files = await graph.graph_list_files(credential, settings, settings.sharepoint_output_folder)
    item = next((f for f in all_files if f.name == name), None)
    if item is None:
        raise HTTPException(status_code=404, detail=f"File {name!r} not found in the SharePoint output folder")
    local_path = await graph.graph_download(credential, settings, item, tmp_dir)
    return FileResponse(local_path, filename=name)
