# AEGIS progress

Checked boundary for this submission pass: **offline vertical slice through replay, audit, human approval, and demo-ready command-center UX.**

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
- [x] Document setup, checks, runtime behavior, the two-minute demo path, and the honest prototype framing.

## Deferred levels

- [x] Level 1 backend vertical slice and approval workflow.
- [x] Level 2 offline-shaped data tools and recorded fixtures.
- [x] Level 3 deterministic agent outputs and fallbacks.
- [x] Level 4 resource ledger, Auditor checks, and bounded revision loop.
- [x] Level 5 replay engine and compound synthetic scenario.
- [x] Level 6 offline MapLibre event, facility, and route layers.
- [x] Submission UX support: visible replay clock/status, full audit log, keyboard-accessible controls, and in-product demo guide.
- [x] Level 7 bounded USGS live polling, timeout/retry/cache fallback, dedupe, and hardening tests.
- [x] Level 8 container deployment blueprint, health check, and final demo instructions.
- [ ] External hosted URL, screenshots, and demo video (requires an external account/network).

## Demo readiness checklist

- [x] Scenario A and Scenario B run end to end in Replay with the network off.
- [x] Evidence chips open the supporting summary and raw JSON record.
- [x] The Auditor catches the fixture contention case and the backend tests cover number mismatch and missing evidence.
- [x] Approve/reject decisions are written to SQLite and displayed in reverse-chronological order in the UI.
- [x] Hindi drafts carry a visible language-review notice and synthetic data carries a visible `SYNTHETIC` label.
- [x] The UI has an in-product 2-minute script and keyboard shortcuts for the main demo actions.
- [x] Container deployment instructions and health check.
- [ ] Hosted URL, screenshots, and demo video.
