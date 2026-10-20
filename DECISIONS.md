# Decisions

- Level 0 uses plain CSS instead of Tailwind to keep the static frontend dependency-light and rebuildable offline after `npm ci`.
- The frontend consumes a named `trace` SSE event and falls back to a deterministic local stream when no API is reachable, so the exported UI remains demoable.
- Root `server.py` hosts `frontend/out` with FastAPI for the Docker image; `backend/app` owns the Level 0 typed contracts and backend SSE implementation.
- The Docker image uses Node 22.14.0 for the export build and Python 3.11.11 for the FastAPI runtime.
- The Level 0 stream is a fixture ticker and does not represent live emergency data or dispatch capability.
