# Hager Should-Cost Builder

A web application that runs the `hager-should-cost-builder` methodology (see
`skill/hager-should-cost-builder/SKILL.md`) as a repeatable service: submit a SAP material ID,
the app reads the material's SharePoint folder and the latest `HAGER*PPE*` spend file via
Microsoft Graph, runs a deterministic multi-step workflow (fact extraction → parameter
proposal → optional deep-dive → live price research → Excel build → sanity gate → slide
values → insights), and writes the two per-supplier Excel deliverables back to SharePoint.

See `docs/design.md` for the architecture and how each skill step maps to code.

## Repository layout

```
backend/   FastAPI + Microsoft Agent Framework (Python 3.11, package `should_cost`)
frontend/  React + TypeScript + Vite
skill/     The hager-should-cost-builder skill, shipped read-only — source of truth
infra/     Bicep
pipelines/ Azure DevOps YAML (ci.yml, cd.yml, infra.yml) + variables.yml placeholders
docs/      design.md, sharepoint-access.md, auth-later.md
```

In production this is one container serving both the API (`/api/*`) and the built frontend
(`/`, SPA fallback to `index.html`) — see the root `Dockerfile`. **None of that is needed to
run this on your own machine** — see below.

## Local development

Prerequisites: Python 3.11, [`uv`](https://github.com/astral-sh/uv) (the backend's package
manager — see `backend/pyproject.toml` / `backend/uv.lock`), Node.js + `pnpm`, and LibreOffice
(`libreoffice-calc` — only needed to exercise the Excel-build/sanity-gate/recalculation paths
end to end; most backend tests use fixtures and don't need it).

No Docker, no Azure App Service, no SharePoint access required for any of this — the
Dockerfile only matters when building the image that actually gets deployed.

```bash
cp .env.example .env   # fill in local values; GRAPH_CREDENTIAL=client_secret for local dev
make install           # uv sync (backend) + pnpm install (frontend)
make dev               # backend on :8000 — uv run uvicorn, auto-reload
make dev-frontend      # frontend on :5173, Vite's dev server proxies /api to :8000
```

Run the test suites:

```bash
make test               # backend (uv run pytest) + frontend (pnpm test)
```

### Running a should-cost analysis with no SharePoint at all

`should_cost/cli.py` runs the same workflow engine the API uses, but reads a PPE spreadsheet
and a material-folder directory from local disk instead of Microsoft Graph — useful for
testing the actual should-cost logic against real files without SharePoint access, an App
Service, or anything else deployed. It still calls Azure AI Foundry for the model calls and
research step, so the `AZURE_AI_FOUNDRY_*` / `SEARCH_PROVIDER` variables in `.env` still need
real values; the `SHAREPOINT_*` variables are required by `Settings`' schema but are never
read on this path, so any placeholder value works for them.

```bash
make cli ARGS="--material-id 0T0001 \
  --ppe-file ./local_input/HAGER_PPE_2025.xlsx \
  --material-folder ./local_input/0T0001 \
  --output-dir ./local_output"
```

If the job pauses (`needs_input` — a missing spend row, an uncertain prefix match, multiple
suppliers to confirm, a RED sanity gate, ...), it prints the question and reads your answer
from the terminal, then continues — looping until the job is `done` or `failed`. On success,
the two generated Excel files and a `job.json` (the full job state, for inspection) land in
`--output-dir`.

## Deployment

Deployment (the Azure DevOps pipelines, the Bicep in `infra/`, how the App Service is
provisioned) is being handled separately and isn't covered here. `pipelines/ci.yml` runs the
backend/frontend/infra checks and tests on every PR and push to `main`; `pipelines/cd.yml` is
an incomplete starting point only (see its own comments) — nothing in this repo deploys
anything on its own.

**The App Service must not be publicly reachable once it is deployed** — there is no sign-in
in v1 (`should_cost/auth.py`); access needs to be restricted to the Hager network by whatever
provisions it. Authentication insertion points for a later Entra ID rollout are documented in
`docs/auth-later.md`.

## Configuration

All configuration is environment variables — see `.env.example` for the full list. There is no
Key Vault; in a deployed environment, secrets are expected to arrive as App Service
application settings (how they get set is part of the deployment work above, not this repo).
