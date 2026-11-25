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
docs/      design.md, deployment.md, sharepoint-access.md, auth-later.md
```

One container serves both the API (`/api/*`) and the built frontend (`/`, SPA fallback to
`index.html`) — see the root `Dockerfile`.

## Local development

Prerequisites: Python 3.11, [`uv`](https://github.com/astral-sh/uv) or pip, Node.js + `pnpm`,
LibreOffice (for legacy `.xls` conversion and formula recalculation — only needed to exercise
the Excel-build/sanity-gate paths end to end; most tests use fixtures that don't need it).

```bash
cp .env.example .env   # fill in local values; GRAPH_CREDENTIAL=client_secret for local dev
make install
make dev               # backend on :8000
make dev-frontend      # frontend on :5173, proxies /api to :8000
```

Run the test suites:

```bash
make test
```

## Deployment

One Azure App Service (Linux, single container), with a staging slot and system-assigned
managed identity. Azure DevOps pipelines in `pipelines/` build the image, push it to ACR, and
deploy via slot swap across `dev` → `test` → `prod`. See `docs/deployment.md` for one-time
setup (service connections, variable groups, managed identity role assignments, how to
register the pipelines) and `docs/sharepoint-access.md` for the Graph permission grant IT needs
to make.

**The App Service must not be publicly reachable** — there is no sign-in in v1. Access is
restricted to the Hager network (see `docs/deployment.md` and the Bicep access restrictions).
Authentication insertion points for a later Entra ID rollout are documented in
`docs/auth-later.md`.

## Configuration

All configuration is environment variables — see `.env.example` for the full list and
`docs/deployment.md` for how each one is set in Azure (no Key Vault; secrets are App Service
application settings injected by the CD pipeline from Azure DevOps variable groups).
