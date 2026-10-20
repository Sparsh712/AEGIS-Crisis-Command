# AEGIS progress

Scope for this pass: **Level 0 foundations and rebuildability infrastructure.**

## Level 0

- [x] Create a portable Next.js App Router frontend under `frontend/`.
- [x] Configure TypeScript and static export output under `frontend/out/`.
- [x] Add an SSE client for `/api/stream` with an offline local replay fallback.
- [x] Add a command-center shell showing the incident, pipeline, evidence path, and activity feed.
- [x] Add a minimal FastAPI host for the exported frontend and a fake TraceStep SSE stream.
- [x] Add typed backend contracts, offline structured-LLM behavior, and backend tests.
- [x] Add pinned Node/Python runtime markers, dependency lockfiles, Docker build, and Make targets.
- [x] Document setup, checks, runtime behavior, and the honest prototype framing.

## Deferred levels

- [ ] Level 1 backend vertical slice and approval workflow.
- [ ] Level 2 real data tools and recorded fixtures.
- [ ] Level 3 validated LLM agents and deterministic fallbacks.
- [ ] Level 4 resource ledger, Auditor checks, and revision loop.
- [ ] Level 5 replay engine and compound synthetic scenario.
- [ ] Level 6 MapLibre command-center layers.
