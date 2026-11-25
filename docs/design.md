# Design: Hager Should-Cost Builder app

## 1. Purpose

Turn the `hager-should-cost-builder` Claude skill (`skill/hager-should-cost-builder/`) into a
standing, multi-user web application:

- A material ID (and optional language) goes in.
- SharePoint/Graph is read for the material folder, the latest `HAGER*PPE*` spend file, and
  historical should-cost models.
- A deterministic, code-driven workflow (not one big agent loop) runs the same methodology the
  skill document describes: fact extraction → parameter proposal → optional deep-dive → live
  price research → Excel build → sanity gate → slide values → insights.
- Two Excel files per supplier (+ chat-style blocks) come out the other end, written back to a
  SharePoint output folder, with a job record the frontend can poll.

The skill's `SKILL.md` and `references/*.md` are the methodology's source of truth. This document
says how that methodology is mapped onto services, data models and API routes — it does not
restate the methodology itself.

## 2. Non-goals / v1 boundaries

- No sign-in (see `docs/auth-later.md` for the stub and insertion points).
- No PowerPoint generation — ever. The skill is explicit that the graphics team owns the PPT
  template; the app's job stops at the two Excel deliverables.
- No on-behalf-of SharePoint access — the app identity only (`docs/sharepoint-access.md`).
- No Key Vault — secrets are App Service application settings injected by the pipeline
  (`docs/deployment.md`).
- No merged/blended supplier models — Pitfall P2 is enforced in code (one job-tree branch per
  supplier, never averaged).

## 3. Why a deterministic workflow instead of one agent loop

An autonomous agent re-deriving "what step am I on" from conversation history cannot guarantee:

- the mandatory ordering (Pre-Build Reasoning → complexity flags → conditional deep-dive →
  benchmarking → Excel build → sanity gate → slide output),
- that a RED sanity gate actually blocks slide output,
- that pause/resume survives a process restart,
- that exactly 3 negotiation levers / 3 self-critique points / ≤3 critical assumptions come out
  every time.

So the workflow is plain async Python code (`backend/app/workflow/engine.py`) that calls three
*structured* model requests and hands only the live-research sub-task to a tool-using agent. The
model never decides what happens next; the code does.

## 4. Workflow steps → code

| Skill step | Module | Notes |
|---|---|---|
| Step 0 (discovery) | `should_cost/graph/*`, `should_cost/data/spend.py`, `should_cost/workflow/steps/discovery.py` | Material folder, latest PPE file, 3-tier ID match, P2 supplier split, historical models as priors |
| Step 1 (`extract_part_facts`) | `should_cost/workflow/steps/extract_facts.py`, `should_cost/tools/model_client.py` | Structured call #1; `PartFacts` Pydantic model; weight-derivation tiers |
| Step 1.5 / 2 (`propose_parameters`) | `should_cost/workflow/steps/propose_parameters.py` | Structured call #2; `ProposedParameters` with CF1–CF6, Low/Base/High+source per parameter |
| Step 2.5 (deep-dive) | `should_cost/workflow/steps/deep_dive.py` | Only runs when `complexity.triggered_count >= 2`; reuses call #2's tool access for constituent research |
| Step 3 (research agent) | `should_cost/tools/research_agent.py` | Tool-using agent: `web_search`, `fetch_page`, `submit_parameter` |
| Step 4 (Excel build) | `should_cost/excel/build.py` (wraps `should_cost/excel/legacy_builder.py`, the ported script) | |
| Step 4.5 (sanity gate) | `should_cost/workflow/steps/sanity_gate.py` | Thresholds from `references/costing_accuracy_rules.md` + SKILL.md Step 4.5; RED blocks slide output |
| Step 5 (slide values + chat blocks) | `should_cost/excel/slide_values.py`, `should_cost/workflow/steps/insights.py` (blocks A–F) | |
| Step 5.5 / 6 (`write_insights`) | `should_cost/workflow/steps/insights.py`, `should_cost/tools/model_client.py` | Structured call #3: self-critique (≤3), levers (exactly 3) |
| Step 7 (hand-off) | `should_cost/workflow/steps/handoff.py`, `should_cost/graph/upload.py` | Upload to output folder, cross-supplier table |

Per-supplier and per-child-component loops are modelled as a tree of `JobUnit` records under one
`Job` (see §6); Step SA-5 roll-up is `app/workflow/steps/rollup.py`.

## 5. Why three structured calls and one agent, and nothing else gets tools

Only the Step 3 research agent is given `web_search` / `fetch_page` / `submit_parameter`. The
three structured calls (`extract_part_facts`, `propose_parameters`, `write_insights`) are plain
"read this context, return this Pydantic schema" requests with no tool loop, so their behaviour
(and token cost) is bounded and testable with a stub model client. This mirrors the skill's own
split between "reasoning about documents" and "go find a dated price".

## 6. Job state machine

```
queued → running → needs_input → running → ... → done
                 → running → failed
```

`Job` (top-level, one per `POST /api/jobs` call) owns:
- `material_id`, `language`, `requested_by` (auth stub field)
- a list of `JobUnit`s — one per supplier (Pitfall P2), and for sub-assemblies one per child
  component plus one roll-up unit (Step SA-5)
- `status`, `current_step`, `pending_question` (when `needs_input`)
- links to produced files

State is persisted after every step transition (`app/state/store.py`), not just on pause, so a
restart never loses more than the in-flight step. Two backends implement the same
`JobStateStore` protocol: Azure Table (default) and Blob (JSON blobs), chosen by
`STATE_BACKEND`.

**Restart recovery**: on startup, `app/workflow/recovery.py` scans for jobs in `running` state.
Each is either resumed from its last saved step (if the step is idempotent / safely re-enterable)
or moved to `failed` with reason `"restarted, please retry"` (if it was mid-write to an external
system, e.g. mid-upload). The per-step code marks itself resumable or not via a `RESUMABLE` set in
`engine.py`.

**Background execution**: jobs run as `asyncio.create_task` inside the same uvicorn process
(`app/workflow/runner.py`). There is no separate worker process/queue in v1 — acceptable because
the workload is "a few analyses a day", not high-throughput, and it keeps the one-App-Service
constraint simple. This is called out in `docs/deployment.md` as a scaling limit.

## 7. SharePoint access

Only `app/graph/*` talks to Graph, and only through a `GraphCredential` passed in explicitly
(never a module-level/global client — see `SharePoint access` in the task brief). Every function
resolves the configured root/output folder first and rejects any resolved path (via item path or
drive id) that falls outside them — this is the path-traversal guard tested in
`backend/tests/test_graph_path_restriction.py`.

`Sites.Selected` with role `write` is the only Graph permission requested; see
`docs/sharepoint-access.md` for the IT-side grant.

## 8. Excel generation

`should_cost/legacy_builder.py` is the skill's `scripts/build_should_cost_model.py`, copied
verbatim except for import adjustments (it becomes an importable module instead of a
`__main__` script; the example/demo data at the bottom is left for tests and local
experimentation, not called from the app). All formula/structure logic described in
`references/output_format_spec.md` and `references/slide_output_format.md` stays untouched —
the app only supplies real `general_info` / `inputs` / `calculations` / `slide3_params` /
`slide5_data` built by the workflow steps instead of the `EXAMPLE_*` constants.

`app/excel/recalc.py` shells out to `libreoffice --headless --convert-to xlsx --calculate` (or
the macro-based recalculation approach) to force formula recalculation before the integrity
checks run, because openpyxl never evaluates formulas itself.

## 9. Frontend

Vite + React + TS, TanStack Query against a typed client generated from the backend's OpenAPI
schema (`frontend/src/api/generated/`, regenerated by `make openapi-client`). Five screens per the
task brief, routed with a minimal router; polling every 3s on the job-progress screen via
`useQuery({ refetchInterval: 3000 })`. The backend serves the Vite build as static files with an
SPA fallback to `index.html` for any non-`/api` path.

## 10. Deployment shape

One Linux App Service (+ staging slot), one container, built by the multi-stage Dockerfile.
Bicep, pipelines and all Azure DevOps-specific names are placeholders resolved from
`pipelines/variables.yml` — see `docs/deployment.md`.

## 11. Task breakdown

Tracked in the session task list (not duplicated here to avoid drift); the phases are: scaffold →
backend (config/auth → Graph → data/parsing → models → prompts → agent framework integration →
Excel port → sanity/recalc → workflow engine → API → tests) → frontend (scaffold/client →
screens/tests) → Dockerfile → pipelines → infra → docs, with tests run after each stage.

## 12. Known simplifications (see also the final assumptions list delivered at the end of the build)

- The Microsoft Agent Framework's hosted web-search support is inconsistently documented for
  Foundry; the app does a startup self-test and logs which of (hosted, Tavily) actually works,
  per the task brief, rather than assuming one.
- Document parsing for legacy `.xls` and recalculation both shell out to LibreOffice headless;
  this is the documented reason the runtime image needs LibreOffice installed.
- No message queue / durable functions — background jobs are asyncio tasks in-process, which caps
  concurrency to what one App Service instance can hold in memory. Flagged in
  `docs/deployment.md` as a scale-out limitation, not solved in v1.
