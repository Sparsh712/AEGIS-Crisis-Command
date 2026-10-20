# AEGIS progress

Scope for this pass: **offline vertical slice through replay, audit, and human approval.**

## Level 0

- [x] Create a portable Next.js App Router frontend under `frontend/`.
- [x] Configure TypeScript and static export output under `frontend/out/`.
- [x] Add an SSE client for `/api/stream` with an offline local replay fallback.
- [x] Add a command-center shell showing the incident, pipeline, evidence path, and activity feed.
- [x] Add a minimal FastAPI host for the exported frontend and a fake TraceStep SSE stream.
- [x] Add typed backend contracts, offline structured-LLM behavior, and backend tests.
- [x] Add SQLite JSON-row persistence and five deterministic agent stages.
- [x] Add evidence-grounded triage, facility allocation, bilingual communications, and Auditor checks.
- [x] Add Nepal and labelled synthetic replay fixtures with accelerated offline replay.
- [x] Add replay controls, incident queue, plan/evidence panel, and human approval UI.
- [x] Add pinned Node/Python runtime markers, dependency lockfiles, Docker build, and Make targets.
- [x] Document setup, checks, runtime behavior, and the honest prototype framing.

## Deferred levels

- [x] Level 1 backend vertical slice and approval workflow.
- [x] Level 2 offline-shaped data tools and recorded fixtures.
- [x] Level 3 deterministic agent outputs and fallbacks.
- [x] Level 4 resource ledger, Auditor checks, and bounded revision loop.
- [x] Level 5 replay engine and compound synthetic scenario.
- [ ] Level 6 MapLibre command-center layers.
- [ ] Level 7 live polling and deployment hardening.
- [ ] Level 8 hosted deployment, screenshots, and demo video.
