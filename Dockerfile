# syntax=docker/dockerfile:1

# ── Stage 1: build the frontend ──────────────────────────────────────────────
FROM node:22-slim AS frontend-build
RUN corepack enable && corepack prepare pnpm@10 --activate
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

# ── Stage 2: backend + LibreOffice + the built frontend ──────────────────────
FROM python:3.11-slim AS runtime

# LibreOffice: legacy .xls conversion and formula recalculation (should_cost/data/
# documents.py, should_cost/excel/recalc.py). curl: container healthcheck.
RUN apt-get update && apt-get install -y --no-install-recommends \
    libreoffice-calc \
    curl \
    && rm -rf /var/lib/apt/lists/*

# uv: installs from the committed uv.lock (exact pinned versions — not the pyproject.toml
# ranges) so the image a deploy runs is the same set of versions CI tested against.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /usr/local/bin/uv

WORKDIR /app/backend
COPY backend/pyproject.toml backend/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY backend/ .
RUN uv sync --frozen --no-dev

WORKDIR /app
COPY skill/ skill/
COPY --from=frontend-build /app/frontend/dist frontend/dist

ENV FRONTEND_DIST_DIR=/app/frontend/dist \
    PYTHONUNBUFFERED=1 \
    PORT=8000 \
    PATH="/app/backend/.venv/bin:$PATH"

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD curl -f "http://localhost:${PORT}/api/health" || exit 1

WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn should_cost.main:app --host 0.0.0.0 --port ${PORT}"]
