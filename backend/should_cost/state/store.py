"""Job state persistence — Azure Table (default) or Blob, chosen by STATE_BACKEND.

Persisted after *every* step transition, not only on pause (design.md §6), so a restart
never loses more than the one in-flight step. Both backends use the storage account's
managed identity (data roles) — never a connection string, per the task brief's secrets
minimization rule.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Protocol

from azure.core.credentials_async import AsyncTokenCredential
from azure.data.tables.aio import TableClient
from azure.storage.blob.aio import ContainerClient

from should_cost.config import Settings, StateBackend
from should_cost.models.job import Job

_TABLE_NAME = "shouldcostjobs"
_CONTAINER_NAME = "should-cost-jobs"
_PARTITION_KEY = "job"  # single partition: job volume is low (a few analyses/day, per design.md)


class JobNotFoundError(KeyError):
    pass


class JobStateStore(Protocol):
    async def save(self, job: Job) -> None: ...
    async def load(self, job_id: str) -> Job: ...
    async def list_recent(self, limit: int = 50) -> list[Job]: ...
    async def list_running(self) -> list[Job]:
        """Used by workflow/recovery.py at startup to find interrupted jobs."""
        ...
    async def delete_older_than(self, retention_days: int) -> int:
        """Returns the number of jobs deleted. Called by a periodic cleanup, not by the
        request path — see docs/deployment.md for how JOB_RETENTION_DAYS is applied.
        """
        ...


def build_job_state_store(settings: Settings, credential: AsyncTokenCredential) -> JobStateStore:
    if settings.state_backend == StateBackend.AZURE_BLOB:
        return AzureBlobJobStateStore(settings.state_storage_account_name, credential)
    return AzureTableJobStateStore(settings.state_storage_account_name, credential)


class AzureTableJobStateStore:
    def __init__(self, account_name: str, credential: AsyncTokenCredential) -> None:
        self._endpoint = f"https://{account_name}.table.core.windows.net"
        self._credential = credential

    def _client(self) -> TableClient:
        return TableClient(endpoint=self._endpoint, table_name=_TABLE_NAME, credential=self._credential)

    async def save(self, job: Job) -> None:
        async with self._client() as client:
            entity = {
                "PartitionKey": _PARTITION_KEY,
                "RowKey": job.job_id,
                "status": job.status.value,
                "updated_at": job.updated_at.isoformat(),
                "payload": job.model_dump_json(),
            }
            await client.upsert_entity(entity)

    async def load(self, job_id: str) -> Job:
        async with self._client() as client:
            try:
                entity = await client.get_entity(partition_key=_PARTITION_KEY, row_key=job_id)
            except Exception as exc:  # azure.core.exceptions.ResourceNotFoundError
                raise JobNotFoundError(job_id) from exc
            return Job.model_validate_json(entity["payload"])

    async def list_recent(self, limit: int = 50) -> list[Job]:
        async with self._client() as client:
            jobs = []
            async for entity in client.query_entities(f"PartitionKey eq '{_PARTITION_KEY}'"):
                jobs.append(Job.model_validate_json(entity["payload"]))
            jobs.sort(key=lambda j: j.updated_at, reverse=True)
            return jobs[:limit]

    async def list_running(self) -> list[Job]:
        async with self._client() as client:
            jobs = []
            async for entity in client.query_entities(
                f"PartitionKey eq '{_PARTITION_KEY}' and status eq 'running'"
            ):
                jobs.append(Job.model_validate_json(entity["payload"]))
            return jobs

    async def delete_older_than(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = 0
        async with self._client() as client:
            async for entity in client.query_entities(f"PartitionKey eq '{_PARTITION_KEY}'"):
                if datetime.fromisoformat(entity["updated_at"]) < cutoff:
                    await client.delete_entity(partition_key=_PARTITION_KEY, row_key=entity["RowKey"])
                    deleted += 1
        return deleted


class AzureBlobJobStateStore:
    def __init__(self, account_name: str, credential: AsyncTokenCredential) -> None:
        self._endpoint = f"https://{account_name}.blob.core.windows.net"
        self._credential = credential

    def _container(self) -> ContainerClient:
        return ContainerClient(account_url=self._endpoint, container_name=_CONTAINER_NAME, credential=self._credential)

    async def save(self, job: Job) -> None:
        async with self._container() as container:
            await container.upload_blob(name=f"{job.job_id}.json", data=job.model_dump_json(), overwrite=True)

    async def load(self, job_id: str) -> Job:
        async with self._container() as container:
            try:
                stream = await container.download_blob(f"{job_id}.json")
                data = await stream.readall()
            except Exception as exc:  # azure.core.exceptions.ResourceNotFoundError
                raise JobNotFoundError(job_id) from exc
            return Job.model_validate_json(data)

    async def list_recent(self, limit: int = 50) -> list[Job]:
        jobs = await self._load_all()
        jobs.sort(key=lambda j: j.updated_at, reverse=True)
        return jobs[:limit]

    async def list_running(self) -> list[Job]:
        jobs = await self._load_all()
        return [j for j in jobs if j.status.value == "running"]

    async def delete_older_than(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        deleted = 0
        async with self._container() as container:
            async for blob in container.list_blobs():
                if blob.last_modified and blob.last_modified < cutoff:
                    await container.delete_blob(blob.name)
                    deleted += 1
        return deleted

    async def _load_all(self) -> list[Job]:
        jobs = []
        async with self._container() as container:
            async for blob in container.list_blobs():
                stream = await container.download_blob(blob.name)
                data = await stream.readall()
                jobs.append(Job.model_validate_json(data))
        return jobs


class InMemoryJobStateStore:
    """For tests and local development without Azure Storage."""

    def __init__(self) -> None:
        self._jobs: dict[str, str] = {}

    async def save(self, job: Job) -> None:
        self._jobs[job.job_id] = job.model_dump_json()

    async def load(self, job_id: str) -> Job:
        if job_id not in self._jobs:
            raise JobNotFoundError(job_id)
        return Job.model_validate_json(self._jobs[job_id])

    async def list_recent(self, limit: int = 50) -> list[Job]:
        jobs = [Job.model_validate_json(v) for v in self._jobs.values()]
        jobs.sort(key=lambda j: j.updated_at, reverse=True)
        return jobs[:limit]

    async def list_running(self) -> list[Job]:
        jobs = [Job.model_validate_json(v) for v in self._jobs.values()]
        return [j for j in jobs if j.status.value == "running"]

    async def delete_older_than(self, retention_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=retention_days)
        to_delete = [
            job_id
            for job_id, payload in self._jobs.items()
            if Job.model_validate_json(payload).updated_at < cutoff
        ]
        for job_id in to_delete:
            del self._jobs[job_id]
        return len(to_delete)
