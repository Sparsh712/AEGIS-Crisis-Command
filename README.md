# AEGIS: Multi-Agent Crisis Command Center

AEGIS is an offline-first decision-support prototype for crisis command workflows. A replayed hazard event moves through five deterministic agent stages—Sensor, Triage, Logistics, Comms, and Auditor—before a human approves or rejects the proposed plan. The command center shows the evidence behind each action, the replay clock, the streaming trace, and the human decision audit log.

## Honest framing

AEGIS is **not an operational emergency system**. It never sends real alerts, dispatches resources, contacts emergency services, or makes decisions without a human approval or rejection. Approved and rejected actions are written only to the local audit log. Hindi drafts are machine-generated and always require human language review. The compound disaster scenario is synthetic and is labelled `SYNTHETIC` in the UI.

## What the submission demonstrates

- **Grounded reasoning:** actions and message claims cite fixture-backed evidence IDs; the evidence drawer exposes the summary and raw JSON.
- **Independent review:** the Auditor checks evidence references, numeric claims, and facility contention before a plan reaches `awaiting_approval`.
- **Human control:** the decision panel requires an explicit approve/reject action, with an optional approval note and a visible audit record.
- **Reliable replay:** Nepal 2015 and the synthetic compound scenario run from local fixtures without network access, at 1×, 10×, 30×, or 60×.
- **Demo observability:** the UI exposes the replay clock and running/stopped state, agent TraceSteps, scenario labels, synthetic status, plan revisions, and the audit log.

## Two-minute demo path

Run the demo with the backend and frontend in separate terminals. The UI also includes this script under **DEMO / 02:00**.

1. **0:00–0:40 — Nepal replay:** choose `NEPAL 2015`, set `30×`, and let the Sensor/Triage trace populate the incident queue, map, priority, rationale, and evidence chips.
2. **0:40–1:00 — Traceability:** open `PLAN`, then click an evidence chip. Show that the action's number and facility choice open a stored evidence summary and raw JSON record.
3. **1:00–1:25 — Audit moment:** choose `SYNTHETIC`. Point out the `SYNTHETIC` badge, the two incidents, facility contention, Auditor flags, and plan revision.
4. **1:25–1:45 — Comms and control:** switch between `EN` and `HI`, note the language-review notice, and approve an `awaiting_approval` plan.
5. **1:45–2:00 — Close:** show the audit log entry and say: “AEGIS is grounded in evidence, reviewed by another agent, human-controlled, and replayable offline.”

Keyboard shortcuts in the demo UI: `R` starts the selected replay, `S` stops it, `A` approves an awaiting plan, `1` opens Activity, `2` opens Plan, and `Esc` closes the evidence drawer. All actions remain available through normal keyboard focus and native controls.

## Architecture

```text
local scenario fixtures
        |
      Sensor -> Triage -> Logistics -> Comms -> Auditor
        |          |          |          |          |
     Event    Incident     Plan    EN/HI drafts  pass/revise
                                                   |
                                      awaiting human approval
                                                   |
                                  approve/reject -> SQLite audit log
                                                   |
                           FastAPI REST + SSE -> Next.js command center
```

The backend owns typed contracts, replay orchestration, evidence, the resource ledger, Auditor checks, SQLite JSON-row persistence, REST endpoints, and the SSE TraceStep stream. The frontend is a static-export Next.js App Router application with an offline MapLibre canvas and a deterministic local SSE fallback when no API is reachable.

## Repository map

- `frontend/` — Next.js 15 App Router, TypeScript, static export, dark command-center UI, replay controls, map, evidence drawer, bilingual comms, plan controls, and audit log.
- `frontend/lib/sse.ts` — connects to `GET /api/stream` and provides a deterministic local activity fallback.
- `backend/app/` — FastAPI contracts, SQLite store, pub/sub bus, replay engine, offline tools, five agents, ledger, Auditor, orchestration, and SSE API.
- `backend/fixtures/` — Nepal 2015 and labelled synthetic compound-disaster scenario data. Replay does not require the network.
- `backend/tests/` — offline contract, agent, replay, API, evidence, and ledger tests.
- `server.py` — FastAPI host for the exported site and the backend API.
- `Dockerfile` — multi-stage Node export build followed by a Python FastAPI runtime.
- `Makefile` — portable install, test, build, dev, API, and Docker commands.

## Requirements

- Node.js `22.14.0` (see `.nvmrc`).
- Python `3.11.11` for the container/runtime (see `.python-version`).
- Docker is optional for the local Node/Python workflow.

## Setup and checks

From the repository root on a clean Linux machine:

```sh
cp .env.example .env
make install
make test
```

`make install` creates the project-local Python virtual environment, installs the pinned backend dependencies from `backend/requirements.lock`, and installs the exact frontend dependencies from `frontend/package-lock.json`. `make test` runs the offline backend pytest suite, the frontend TypeScript check, and the static export build. It does not contact external services. Live polling is opt-in with `AEGIS_LIVE_ENABLED=1` and is never required for Replay mode.

## Run locally

Use two terminals after setup:

```sh
make api
```

Then:

```sh
make dev
```

Open `http://localhost:3000`, choose a replay, and follow the two-minute path above. The frontend reads the backend from `NEXT_PUBLIC_API_BASE` (the example value is `http://localhost:8000`). To inspect the SSE stream directly:

```sh
curl -N http://localhost:8000/api/stream
```

## Docker

Build and run the complete exported frontend plus FastAPI host:

```sh
make docker-build
make docker-run
```

Open `http://localhost:8000`. Equivalent direct commands are:

```sh
docker build -t aegis:local .
docker run --rm -p 8000:8000 aegis:local
```

### Container deployment

The same image is deployable to any container host. The repository includes a minimal `render.yaml` blueprint for a replay-first Render web service with `/api/health` as its health check. For another provider, use:

```sh
docker build -t aegis:local .
docker run --rm -p 8000:8000 -e FRONTEND_ORIGIN=http://localhost:8000 -e FIXTURE_ONLY=1 -e FAKE_LLM=1 aegis:local
```

Keep `AEGIS_LIVE_ENABLED=0` for the repeatable offline demo. If a host assigns a public URL, set `FRONTEND_ORIGIN` to that exact origin and keep Replay as the default operating mode.

## Current limitations and next steps

- **Live mode is not the demo path:** the shipped `.env.example` is fixture-only, so the repeatable submission flow never needs a network. Any configured USGS polling is bounded, uses an 8-second timeout plus one retry, and falls back to disk cache or fixtures; this prototype is not an operational live feed.
- **Replay data is recorded fixture data:** Nepal is historical USGS-shaped data and the compound scenario is synthetic. Facility and population values are scenario fixtures, not current operational availability; capacity values are estimates.
- **The map is local:** it uses an offline vector style with no external basemap tile dependency. Routes are evidence-backed straight-line relationships in the fixture slice.
- **Language is not certified:** Hindi text is machine-generated and flagged for human review; the UI does not provide translation approval or linguistic validation.
- **No operational integrations:** there is no authentication, multi-tenancy, SMS/social dispatch, evacuation authority, emergency-service integration, mobile app, or model training.
- **Deployment configuration is included but not hosted from this workspace:** run locally, use the included Docker build, or apply `render.yaml`; a public URL and demo recording still require an external account and network.

The next useful work is Level 8 deployment, screenshots, and demo video. See `PROGRESS.md` for the checked boundary and `DECISIONS.md` for implementation choices.
