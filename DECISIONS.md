# Decisions

- Level 0 uses plain CSS instead of Tailwind to keep the static frontend dependency-light and rebuildable offline after `npm ci`.
- The frontend consumes a named `trace` SSE event and falls back to a deterministic local stream when no API is reachable, so the exported UI remains demoable.
- Root `server.py` hosts `frontend/out` with FastAPI for the Docker image; `backend/app` owns the Level 0 typed contracts and backend SSE implementation.
- The Docker image uses Node 22.14.0 for the export build and Python 3.11.11 for the FastAPI runtime.
- The Level 0 stream is a fixture ticker and does not represent live emergency data or dispatch capability.
- Replay mode is the default and clears the SQLite-backed in-process state before each scenario so demos are repeatable.
- The two supplied scenarios use deterministic local fixtures; Live mode is opt-in and bounded, while Replay never makes network calls.
- Live polling is opt-in and bounded by environment settings; transport failures become visible cache/fallback TraceSteps rather than blocking Replay or crashing the app.
- The frontend polls the existing `/api/state` endpoint once per second so the replay clock and running/stopped status remain visible while the backend replay task advances; no backend contract or behavior changes were needed.
- The full human audit log is rendered in reverse chronological order below the decision bus so an approval remains visible after the selected plan changes.
- Keyboard support uses native buttons, selects, textareas, visible `:focus-visible` outlines, and small shortcuts (`R`, `S`, `A`, `1`, `2`, `Esc`) documented in the UI and README.
- Submission claims are limited to the checked offline fixture slice; live feeds, hosted deployment, external dispatch, and certified translation are explicitly documented as limitations.
- A single-container deployment is the default production shape for this prototype because the exported frontend and FastAPI API share one origin and avoid CORS drift; `render.yaml` remains replay-first and keyless.
- `make test` has an environment preflight: it validates Python 3.11 and Node 22.14.0, repairs a missing/incomplete local environment, then runs the actual checks instead of failing with an opaque missing-venv error.
