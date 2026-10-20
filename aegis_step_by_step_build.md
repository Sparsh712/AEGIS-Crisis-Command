AEGIS Level-by-Level Development Playbook
Companion to the AEGIS build spec. Work through the levels in order and do not start a level until the previous gate passes.
1. How to use this playbook
• Every level has a goal, tasks, files touched, acceptance checks, a gate and common pitfalls.
• Keep PROGRESS.md at the repo root with one checkbox per task. Tick as you go and note blockers.
• Loop for every task: write a two-line plan, build the smallest working thing, run the check, commit as L<level>: <task>.
• Tag the repo at each gate with git tag level-N. If a later level breaks things, return to the last tag.
• Run the app after every task, not only at the end of a level.
• Time shares are percentages of the total time you have. A fast lane for very tight schedules is in section 12.
2. Level overview
• Level 0, 5%: foundations and contracts.
• Level 1, 15%: vertical slice with stubbed agents.
• Level 2, 12%: real data tools, evidence and fixtures.
• Level 3, 18%: real agents with LLM calls and fallbacks.
• Level 4, 12%: resource ledger, Auditor and revision loop.
• Level 5, 8%: replay engine and scenarios.
• Level 6, 15%: command center UI with map.
• Level 7, 5%: live mode and hardening.
• Level 8, 10%: deploy, demo video and submission.
3. Level 0: Foundations (5%)
Goal: both servers run, the data contracts exist, and a fake event stream appears in the browser.
Tasks
1. Create the repo layout from section 4 of the build spec. Add .gitignore, .env.example (LLM_PROVIDER, LLM_MODEL, LLM_API_KEY, FRONTEND_ORIGIN, FIXTURE_ONLY, FAKE_LLM), a README stub, PROGRESS.md and DECISIONS.md.
2. Backend: create a venv and install fastapi, uvicorn, pydantic, httpx, sse-starlette, python-dotenv, pytest.
3. models.py: paste the contracts from section 5 of the build spec unchanged.
4. bus.py: in-memory pub/sub with one asyncio.Queue per subscriber and a publish() function.
5. main.py: /api/health, CORS for the frontend origin, and /api/stream (SSE) that emits a fake TraceStep every 2 seconds.
6. llm.py: complete_json(system, user, schema, retries=1) returns a validated Pydantic object or raises LLMError. Provider and model come from env. When FAKE_LLM=1 it returns canned outputs so tests run without a key.
7. Frontend: create-next-app (TypeScript, Tailwind, App Router). Add lib/sse.ts, a hook that connects to /api/stream, and a page that lists incoming steps.
Acceptance checks
• curl -N http://localhost:8000/api/stream prints a step every 2 seconds.
• The browser page shows the same steps scrolling in.
• complete_json returns a valid object with FAKE_LLM=1 and with a real key on a trivial schema.
Gate: all three checks pass, then tag level-0.
Pitfalls: CORS errors, SSE responses being buffered (send Cache-Control: no-cache), forgetting to load .env.
4. Level 1: Vertical slice with stubs (15%)
Goal: one hardcoded Nepal earthquake travels through all five agents (stub logic) and a human can approve the resulting plan in the UI. This proves the architecture before any real data or prompts exist.
Tasks
1. store.py: in-memory dicts for events, incidents, evidence, plans, trace and audit log, persisted to SQLite as JSON rows. Keep it simple.
2. orchestrator.py: one async function per stage. Each agent is async def run(input, ctx) -> output and emits TraceStep records.
3. agents/*.py: stub versions that return plausible fixed output (two hospitals, one public alert, a placeholder Hindi string).
4. API: /api/state, /api/plans/{id}/approve, /api/plans/{id}/reject, /api/audit-log, and a dev-only POST /api/dev/inject-sample that starts the hardcoded event.
5. UI: incident queue on the left, activity feed on the right, plan panel with Approve and Reject. Plain styling, no map yet.
Acceptance checks
• Click Inject sample. Within about 3 seconds the feed shows steps from all five agents.
• The plan reaches awaiting_approval. Approve changes its status and adds an audit log entry.
• Refreshing the page keeps the state.
Gate: record a 30-second screen capture of the above for yourself, then tag level-1.
Pitfalls: polishing stubs, adding agent intelligence early, or styling the UI. Resist all three.
5. Level 2: Real data and evidence (12%)
Goal: tools return real data, everything is cached, and every fact is stored as Evidence.
Tasks
1. tools/geo.py: haversine distance, bounding box helper, and unit tests.
2. Disk cache for every HTTP tool, keyed by a hash of URL plus params, stored in backend/.cache. Add a FIXTURE_ONLY=1 mode that never touches the network.
3. tools/usgs.py: live feed and historical query, both returning list[Event]. Mind that GeoJSON coordinates are [lon, lat, depth] and time is epoch milliseconds.
4. tools/overpass.py: facilities(lat, lon, radius_km, types) and places_population(lat, lon, radius_km). Handle way elements via center, return a trimmed tag set, and mark bed counts as estimated.
5. Evidence helper: add_evidence(tool, summary, data) returns an Evidence with sequential ids (e1, e2). The summary string must contain the key numbers.
6. scripts/prefetch_fixtures.py: downloads the Nepal USGS window and Overpass responses for each scenario region into backend/fixtures/.
Acceptance checks
• pytest passes for geo helpers.
• Running the prefetch script produces fixture files.
• With FIXTURE_ONLY=1 and the network off, every tool still returns data.
• Sample evidence summaries read like facts, for example the distance and name of the nearest hospital.
Gate: tag level-2.
Pitfalls: swapped lat/lon, Overpass timeouts (retry once with a smaller radius), oversized responses (keep only the tags you use).
6. Level 3: Real agents (18%)
Goal: replace each stub with real logic and LLM calls. Everything is validated and has a deterministic fallback. Do the agents one at a time, in this order, and test each before the next.
Common setup
• Store prompts as files in backend/app/prompts/ so you can iterate without touching code.
• Cache LLM outputs on disk keyed by a hash of model, system and user text. This enables a cached-LLM demo mode.
• Pass compact evidence lists to the LLM, not raw JSON dumps.
Triage
1. Implement det_score exactly as in section 7.2 of the build spec and unit test every branch.
2. Fetch exposure with places_population and store it as evidence.
3. LLM returns {priority, rationale, evidence_ids}. Clamp priority to within 1 of det_score in code.
4. Fallback: priority equals det_score, rationale from a template.
Logistics
1. Fetch facilities, rank by distance, give the LLM the top candidates with their evidence ids.
2. Validate that every action target id exists in the tool results. Reject any that does not and retry once.
3. Fallback: stage resources at the two nearest hospitals and add one public alert action.
Comms
1. Prompt with the rules from section 7.4 of the build spec. Produce sms, social and bulletin in English and Hindi.
2. Enforce length limits in code and set needs_language_review = true.
3. Fallback: templates filled from evidence.
Acceptance checks (per agent, on the Nepal mainshock fixture)
• Triage priority is within the clamp of det_score.
• Every Logistics target appears in tool results.
• Every number in Comms text appears in the cited evidence.
• A deliberately malformed LLM output falls back correctly and logs a trace step.
• Each agent's steps appear in the activity feed.
Gate: the full pipeline runs offline on the Nepal fixture using cached LLM output, then tag level-3.
Pitfalls: the LLM inventing facilities, prompts that grow too long, Hindi SMS lengths, forgetting to log tool calls as trace steps.
7. Level 4: Ledger, Auditor and revision loop (12%)
Goal: plans cannot double-book resources, and a separate Auditor agent can send a plan back for revision.
Tasks
1. ledger.py: assignments map, reserve(facility_id, incident_id, priority), conflicts(plan), default capacities (hospital 100, clinic 10) flagged as estimates.
2. Logistics reads a ledger snapshot. When a facility is already taken by a higher-priority incident, emit a contention trace step and choose the next facility or request mutual aid.
3. agents/auditor.py: deterministic checks first (evidence ids exist, numbers in Comms match evidence, no double-booking), then the LLM critique. Returns pass, revise with flags, or escalate.
4. Revision loop in the orchestrator: at most 2 rounds, then escalate to the human with the flags visible.
5. Wrap ledger writes in an asyncio.Lock, or process incidents sequentially by priority.
Acceptance checks
• A test with two incidents sharing one hospital produces a contention step and a revised plan.
• A test where Comms includes a number absent from evidence is flagged.
• A test with a missing evidence id is flagged.
• Forcing the LLM to fail twice results in escalate and a plan that waits for the human.
Gate: tag level-4.
Pitfalls: the Auditor editing plans itself (it must only flag), endless revision loops, concurrent plans racing on the ledger.
8. Level 5: Replay and scenarios (8%)
Goal: a reliable demo mode that works with zero network access.
Tasks
1. replay.py: reads a scenario manifest, sorts events by time, and emits them on an accelerated clock (1x to 60x). Broadcast the replay clock over SSE.
2. Scenario manifests in backend/fixtures/scenarios/: nepal_2015.json (the 25 April 2015 M7.8 mainshock and the 12 May 2015 M7.3 aftershock) and compound_synthetic.json.
3. Build the synthetic scenario with a script. Mark every event synthetic: true. Place an earthquake and a flood event about 30 km apart near a region where one major hospital dominates the nearest-facility list, and confirm that against the fixtures.
4. Endpoints: POST /api/mode with {mode, scenario, speed} and POST /api/replay/stop. Starting a scenario clears the previous scenario's state.
Acceptance checks
• Scenario A at 30x with the network off emits the expected events at the expected times.
• Scenario B produces contention without any special-casing in code.
• Stop then restart leaves no stale incidents.
Gate: tag level-5.
Pitfalls: hardcoding the failure you want to demo (the contention must come from real tool output), forgetting to reset the ledger between runs.
9. Level 6: Command center UI (15%)
Goal: the screen you will demo. Build in this order so progress is visible at every step.
Frontend files: app/page.tsx, components/Map.tsx, IncidentQueue.tsx, ActivityFeed.tsx, PlanPanel.tsx, EvidenceDrawer.tsx, TopBar.tsx, lib/api.ts, lib/sse.ts, lib/types.ts (mirror the Pydantic models).
Tasks
1. Map.tsx: initialise MapLibre inside a client-only dynamic import (ssr: false), add a free basemap style, and handle resize.
2. Events layer: GeoJSON source, circles sized by magnitude and coloured by priority, with a one-time pulse and fly-to for new incidents.
3. Facilities layer plus dashed straight-line routes from event to each planned facility.
4. Incident queue sorted by priority with status chips. Selecting an incident syncs the map and the plan panel.
5. Activity feed with a colour per agent, auto-scroll that pauses on hover.
6. Plan panel: actions with evidence chips, the evidence drawer, the Auditor verdict badge and flags, comms tabs (sms, social, bulletin) with an EN/HI toggle and character counter, and Approve and Reject (reject asks for a note).
7. Top bar: mode toggle, scenario picker, speed slider, replay clock, SYNTHETIC badge. Footer: the honest-framing statement.
8. Polish: loading skeletons, empty states, error toasts, keyboard focus, and a dark high-contrast theme that reads on a projector.
Acceptance checks
• You can run Scenario A and Scenario B using only the UI.
• No console errors, and no layout shift when new steps arrive.
• Capture 4 to 6 screenshots for the README.
Gate: tag level-6.
Pitfalls: window is not defined from MapLibre during SSR, forgetting map.resize(), duplicate layer ids after hot reload, state updates from SSE causing re-render storms (batch them).
10. Level 7: Live mode and hardening (5%)
Tasks
1. Live polling loop for USGS with dedupe. Optional GDACS RSS.
2. A shared HTTP wrapper with timeout, one retry, and a cache fallback. Show a visible banner in the UI when cached data is in use.
3. Rate-limit Overpass calls and reuse cached results.
4. Error boundaries in the UI and structured logs in the backend.
5. Run the unit and smoke tests, run each scenario three times in a row, and replay 50 events quickly to check nothing leaks or deadlocks.
Acceptance checks
• Disconnect the network mid-run. The banner appears and the app continues from cache.
• Three consecutive runs of both scenarios complete without a crash.
Gate: tag level-7.
11. Level 8: Deploy, demo and submission (10%)
Tasks
1. Deploy the backend with env vars and a health check. Deploy the frontend with NEXT_PUBLIC_API_BASE. Fix CORS. Default the deployed app to Replay mode.
2. Finish the README using section 15 of the build spec: honest framing, architecture diagram, setup in 5 commands or fewer, screenshots, limitations, next steps.
3. Record the demo video following section 14 of the build spec. Rehearse twice. Record from a clean run.
4. Final check: fresh clone, follow the README exactly, run both scenarios.
5. Freeze features 30 to 60 minutes before the deadline. Only fix bugs after that. Submit with a buffer.
Acceptance checks
• A fresh clone runs in 5 commands or fewer.
• The deployed URL works from another network and from a phone.
• The video meets the length limit and the submission form is complete.
Gate: tag level-8, submit.
12. Fast lane (if time is very short)
Compress the levels like this and keep the order:
• L0 + L1 together. In-memory store only, no SQLite persistence.
• L2. USGS fixtures plus cached Overpass for one region.
• L3. Real Triage, Logistics and Comms. Use cached LLM output for the demo.
• L4. Deterministic Auditor checks only (evidence ids, numbers, double-booking). Skip the LLM critique.
• L5. Scenario A first. Add Scenario B if at all possible, because the contention-and-audit moment is the best part of the demo.
• L6. Map, incident queue and plan panel only. Skip the evidence drawer and extra tabs.
• L7. Skip live mode. Keep the timeout and cache wrapper.
• L8. Record the video locally if deployment is a risk.
Never drop: evidence ids on every claim, the Auditor checks, and the human approval step.
13. Definition of done
[ ] Scenario A and Scenario B run end to end in Replay with the network off.
[ ] Every action and every number in the UI traces back to an evidence item.
[ ] The Auditor catches a real contention case and a number mismatch in tests.
[ ] Nothing happens without a human approve or reject, and the audit log records it.
[ ] Hindi drafts are flagged for language review and SYNTHETIC data is labelled.
[ ] README, architecture diagram, screenshots and demo video are complete.
[ ] The deployed URL (or local recording) has been tested by someone other than the author.
14. Prompt templates for the coding agent
Starting a level
You are working on Level N of AEGIS. Read the build spec and Level N of this playbook. Implement only the tasks in Level N, in order, ticking them off in PROGRESS.md and committing after each. Run the acceptance checks and stop at the gate. Do not start Level N+1.
Status report format (ask the agent to end every session with this)
Done: what is finished and verified. Failing: checks that fail, with the error. Blocked: what you need from me. Next: the next 3 tasks.
When something breaks
Stop adding features. Reproduce the failure, write a failing test if practical, fix the smallest cause, rerun the level's acceptance checks, and note the cause in DECISIONS.md.
15. Troubleshooting quick reference
• SSE connects but nothing arrives: check the response headers, make sure no proxy buffers the stream, and confirm the publisher and subscriber use the same bus instance.
• Map renders blank: the container has zero height, or map.resize() was never called.
• Events land in the wrong country: lat and lon are swapped. GeoJSON order is lon, lat.
• Overpass returns 429 or times out: use the cache, reduce the radius, and rely on fixtures.
• LLM returns prose instead of JSON: tighten the system prompt, use the provider's JSON or schema mode, and rely on the retry and fallback path.
• Hindi text shows as boxes in the UI: load a font with Devanagari support.
• Plans stuck in auditing: a revision loop never terminates. Check the round counter and the escalate path.