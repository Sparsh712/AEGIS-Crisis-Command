# AEGIS: Multi-Agent Crisis Command Center

AEGIS is a decision-support prototype for crisis command workflows. This repository currently implements the Level 0 foundation: typed backend contracts, an offline structured-LLM boundary, a streaming TraceStep activity feed, a static-export Next.js App Router frontend, and a reproducible Docker build.

## Honest framing

AEGIS is not an operational emergency system. It never sends real alerts and never dispatches anything. Approved actions will be written to an audit log in later levels. Hindi drafts will be machine-generated and flagged for human language review. Synthetic scenarios will always be labelled `SYNTHETIC` in the UI.

## What is here

- `frontend/` — Next.js 15 App Router, TypeScript, static export, dark operations-room UI.
- `frontend/lib/sse.ts` — connects to `GET /api/stream` and provides an offline deterministic fallback.
- `backend/app/` — FastAPI contracts, configuration, pub/sub bus, structured LLM boundary, and SSE ticker.
- `backend/tests/` — offline backend contract and SSE tests.
- `server.py` — FastAPI host for the exported site and a fake TraceStep SSE ticker used by the Docker image.
- `Dockerfile` — multi-stage Node export build followed by a Python FastAPI runtime.
- `Makefile` — portable install, test, build, dev, API, and Docker commands.

## Requirements

- Node.js `22.14.0` (see `.nvmrc`).
- Python `3.11.11` for the container/runtime (see `.python-version`).
- Docker is optional for the local Node/Python workflow.

## Local setup

From the repository root on a clean Linux machine:

```sh
cp .env.example .env
make install
```

`make install` creates the project-local Python virtual environment, installs the pinned backend dependencies from `backend/requirements.lock`, and installs the exact frontend dependencies from `frontend/package-lock.json`.

## Test

Run the one project test command:

```sh
make test
```

This runs the offline backend pytest suite, the frontend TypeScript check, and the static export build. It does not contact external services.

## Run locally

Use two terminals after setup:

```sh
make api
```

Then:

```sh
make dev
```

Open `http://localhost:3000`. The frontend connects to the FastAPI SSE stream using `NEXT_PUBLIC_API_BASE`. If the API is unavailable, it shows a clearly local replay stream so the Level 0 screen remains inspectable.

To inspect the stream directly:

```sh
curl -N http://localhost:8000/api/stream
```

## Docker

Build and run the complete exported frontend plus FastAPI host:

```sh
make docker-build
make docker-run
```

Open `http://localhost:8000`. The container serves the static export and emits TraceStep events from the same FastAPI process.

Equivalent direct Docker commands are:

```sh
docker build -t aegis:local .
docker run --rm -p 8000:8000 aegis:local
```

The repository contains no machine-specific absolute paths or committed secrets. Copy `.env.example` to `.env` and provide provider credentials only for a future live LLM integration.

## Next level

Level 1 will add the backend vertical slice, in-memory state, the human approval endpoints, and the first end-to-end Nepal fixture flow. See `PROGRESS.md` and `DECISIONS.md` for the current boundary and recorded choices.
