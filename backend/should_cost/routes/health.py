"""GET /api/health — open, no auth, used by the CD pipeline's post-deploy smoke test."""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter()


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
