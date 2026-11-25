"""FastAPI app: serves /api/* and the built frontend (static files, SPA fallback).

One container, one process (uvicorn) — see Dockerfile. The app's lifespan does three
things on startup that a request path should never do lazily: resolve the Graph
credential once, run the configured search provider's self-test (fails loudly if hosted
web search isn't actually reachable rather than discovering that on the first real job),
and recover any job left in ``running`` state by a previous process (workflow/recovery.py).
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from should_cost.config import get_settings
from should_cost.graph.credentials import build_graph_credential
from should_cost.routes import health as health_routes
from should_cost.routes import jobs as jobs_routes
from should_cost.state.store import build_job_state_store
from should_cost.tools.model_client import build_chat_client
from should_cost.tools.research_agent import SearchSelfTestError, run_search_self_test
from should_cost.workflow.recovery import recover_interrupted_jobs

logger = structlog.get_logger(__name__)

FRONTEND_DIST = Path(os.environ.get("FRONTEND_DIST_DIR", "/app/frontend/dist"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    credential = build_graph_credential(settings)
    store = build_job_state_store(settings, credential)

    app.state.settings = settings
    app.state.credential = credential
    app.state.store = store

    chat_client = build_chat_client(settings)
    try:
        mode = await run_search_self_test(settings, chat_client)
        logger.info("search_self_test_ok", mode=mode)
    except SearchSelfTestError as exc:
        logger.error("search_self_test_failed", error=str(exc))
        raise

    await recover_interrupted_jobs(store=store, settings=settings, credential=credential)

    yield


def create_app() -> FastAPI:
    app = FastAPI(title="Hager Should-Cost Builder", lifespan=lifespan)
    app.include_router(health_routes.router, prefix="/api")
    app.include_router(jobs_routes.router, prefix="/api")

    if FRONTEND_DIST.exists():
        app.mount("/assets", StaticFiles(directory=FRONTEND_DIST / "assets"), name="assets")

        @app.get("/{full_path:path}")
        async def spa_fallback(full_path: str) -> FileResponse:
            candidate = FRONTEND_DIST / full_path
            if candidate.is_file():
                return FileResponse(candidate)
            return FileResponse(FRONTEND_DIST / "index.html")

    return app


app = create_app()
