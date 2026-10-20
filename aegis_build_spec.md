AEGIS: Multi-Agent Crisis Command Center
Build spec for the Omnirush Agentic Buildathon 2026. Hand this whole document to the coding agent.
1. Decision and pitch
I chose the crisis command center over the paper reproducer because:
• The demo is visual and lands in two minutes (events appear on a map, agents reason, routes get drawn).
• It needs only free public APIs. The paper reproducer needs sandbox compute, long runs and flaky third-party repos.
• Every external dependency has a recorded-data fallback, so the demo cannot die on a flaky API.
• It is judged on impact as well as engineering, and it fits the Agents & Automation and Human x AI tracks, with an audit and safety angle.
Pitch. AEGIS is a team of specialised AI agents that watches hazard feeds, ranks incidents, plans resource allocation from real map data, drafts English and Hindi alerts, audits its own plans against evidence, and sends every consequential action to a human for approval.
Honest framing (put this in the README and the UI footer). AEGIS is a decision-support prototype. It never sends real alerts and never dispatches anything. Approved actions are only written to an audit log. Hindi drafts are machine-generated and flagged for human language review. Synthetic scenarios are always labelled SYNTHETIC in the UI.
2. Rules for the coding agent
1. Vertical slice first. Get one hardcoded earthquake flowing end to end (event -> triage -> plan -> comms -> audit -> approve in UI) before adding real feeds or polish.
2. Numbers come from tools, never from the LLM. Distances, counts, magnitudes and capacities are computed or fetched in code and stored as Evidence. The LLM reasons over them and must cite evidence ids.
3. Structured output only. Every LLM call returns JSON validated by a Pydantic model. On validation failure retry once, then fall back to a deterministic default and log a TraceStep.
4. Never block on an external API. 8 second timeout, cache responses to disk, and fall back to fixtures. The app must run fully offline in Replay mode.
5. Stream everything. Every agent step is a TraceStep pushed over SSE. The UI is driven by this stream.
6. Keep it simple. No LangChain, CrewAI or similar. Plain asyncio, Pydantic, httpx. Fewer moving parts means fewer demo-day failures.
7. Keep main demoable. Commit after every working step. Never leave the main branch broken.
8. Secrets live in .env (provide .env.example). Never commit keys.
9. When the spec is silent, pick the simplest option and record it in DECISIONS.md in one line.
3. Scope tiers
MUST (demo-critical)
• Replay mode with one real scenario (Nepal 2015) and one synthetic compound scenario.
• Sensor, Triage, Logistics, Comms and Auditor agents working end to end.
• Map with events, facilities, routes; incident queue; agent activity feed.
• Plan card with evidence chips, auditor verdict, EN/HI drafts, approve and reject buttons.
• Audit log of human decisions.
SHOULD
• Live mode polling USGS (and GDACS if reachable).
• Resource ledger with contention detection and Auditor-triggered revision.
• Open-Meteo flood signal for the synthetic flood leg.
• Deployed frontend and backend.
COULD
• OSRM road routing instead of straight lines.
• Evidence drawer with raw JSON.
• A third language for local alerts.
• Export incident report as PDF.
WON'T
• Real SMS or alert sending, authentication, multi-tenancy, mobile app, model training.
4. Architecture
Feeds (USGS, GDACS, Open-Meteo)  or  Replay fixtures
        |
  [Sensor] --Event--> [Triage] --Incident--> [Logistics] --Plan--> [Comms]
                                                  ^                    |
                                                  +--critique-- [Auditor]<--+
                                                                   |
                                          Plan(status=awaiting_approval)
                                                                   v
                  FastAPI (REST + SSE)  <---->  Next.js + MapLibre command UI
                                                                   v
                                    Human approve / reject -> audit log
Stack
• Backend: Python 3.11, FastAPI, Pydantic v2, httpx, sse-starlette, SQLite.
• Frontend: Next.js (App Router), TypeScript, Tailwind, MapLibre GL JS. Free basemap style (for example a Carto GL style URL, or OpenFreeMap).
• LLM: one wrapper llm.py with a provider switch from env (Claude or Gemini), model name from env, JSON-schema output. All agents call only this wrapper.
• Hosting: frontend on Vercel, backend on Render, Railway or Fly. If deployment eats time, run locally and record the demo video.
Repo layout
aegis/
  backend/app/
    main.py  config.py  llm.py  models.py  store.py  bus.py
    orchestrator.py  replay.py
    agents/  sensor.py triage.py logistics.py comms.py auditor.py
    tools/   usgs.py gdacs.py openmeteo.py overpass.py geo.py
  backend/fixtures/   (recorded feeds + cached Overpass responses)
  backend/tests/
  frontend/            (Next.js app)
  README.md  DECISIONS.md  .env.example
5. Data contracts (Pydantic, backend/app/models.py)
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class Hazard(str, Enum):
    earthquake = 'earthquake'; flood = 'flood'; cyclone = 'cyclone'; other = 'other'

class Event(BaseModel):
    id: str                      # f'{source}:{source_id}'
    source: str                  # usgs | gdacs | openmeteo | synthetic
    hazard: Hazard
    lat: float; lon: float
    magnitude: float | None = None
    alert_level: str | None = None   # green|yellow|orange|red when the source gives it
    occurred_at: datetime
    raw: dict = {}
    synthetic: bool = False

class Evidence(BaseModel):
    id: str                      # e1, e2, ...
    tool: str
    summary: str                 # human-readable fact that includes the number
    data: dict
    fetched_at: datetime

class Incident(BaseModel):
    id: str
    event_ids: list[str]
    hazard: Hazard
    det_score: int               # deterministic score 1-5
    priority: int = Field(ge=1, le=5)   # final, 5 = most urgent
    exposure_estimate: int | None = None   # lower-bound estimate, may be None
    rationale: str
    evidence_ids: list[str]

class Action(BaseModel):
    type: str    # stage_resources | dispatch | public_alert | evacuation_advisory | request_mutual_aid
    target: str  # facility id or zone name
    detail: str
    evidence_ids: list[str]

class Comms(BaseModel):
    channel: str  # sms | social | bulletin
    en: str
    hi: str
    needs_language_review: bool = True

class Plan(BaseModel):
    id: str
    incident_id: str
    actions: list[Action]
    comms: list[Comms] = []
    status: str   # drafting | auditing | awaiting_approval | approved | rejected | escalated
    auditor_verdict: str | None = None   # pass | revise | escalate
    auditor_flags: list[str] = []
    revision: int = 0

class TraceStep(BaseModel):
    ts: datetime
    agent: str    # sensor | triage | logistics | comms | auditor | human | system
    kind: str     # observe | tool_call | reason | handoff | critique | decision | human
    message: str
    refs: dict = {}   # event_id, incident_id, plan_id, evidence_ids
6. Orchestration flow (backend/app/orchestrator.py)
1. Sensor emits an Event (from live polling or the replay clock). Dedupe by Event.id.
2. Triage builds or updates an Incident. Events of the same hazard within 100 km and 24 hours merge into one incident.
3. Logistics creates a Plan with actions, consulting the resource ledger.
4. Comms attaches drafts to the plan.
5. Auditor reviews. Verdict pass moves the plan to awaiting_approval. Verdict revise sends flags back to Logistics or Comms. Maximum 2 revision rounds, then escalate to the human with flags visible.
6. Human approves or rejects in the UI. The decision is written to the audit log with timestamp and optional note.
Use an asyncio queue per stage and one global TraceStep bus that feeds SSE. Process incidents in priority order. Keep handlers idempotent so replays and restarts are safe.
Resource ledger (deterministic code, not LLM). Tracks facilities already assigned. OSM beds tags are often missing, so use rough defaults (hospital 100, clinic 10) and label them estimates in the UI. Allocation is greedy by incident priority, then distance, with no double-booking. If two incidents want the same facility, emit a contention TraceStep and give the facility to the higher-priority incident. The lower-priority plan must pick the next facility or request mutual aid.
7. Agent specifications
All agents share: system prompt plus structured output model, a list of tools it may call, and a fallback behaviour. Prompts below are skeletons; tighten them while testing.
7.1 Sensor (mostly deterministic)
• Role: poll feeds every 60 seconds in Live mode, or read the replay clock, and normalise to Event.
• Tools: usgs, gdacs, openmeteo.
• LLM use: none required. It still shows up as an agent in the UI because it acts autonomously on a schedule and logs observe steps.
• Failure: source timeout -> log and keep the last cached data.
7.2 Triage
• Inputs: an Event.
• Tools: overpass.places_population(lat, lon, radius_km) to get an exposure lower bound by summing OSM population tags of nearby places; geo.haversine.
• Deterministic score (det_score):
    ◦ Base from the USGS PAGER alert: green 1, yellow 2, orange 3, red 4. If absent: magnitude below 5 -> 1, 5 to 5.9 -> 2, 6 to 6.9 -> 3, 7 or above -> 4.
    ◦ Add 1 (cap 5) if the tsunami flag is set or exposure_estimate is 500,000 or more.
• LLM output: {priority, rationale, evidence_ids}. Guardrail: clamp priority to within 1 of det_score in code.
• Prompt skeleton: You are the Triage agent in a disaster decision-support system. Use only the facts in the evidence list. Cite evidence ids for every claim. If exposure is unknown say so plainly. Do not exaggerate.
• Failure: LLM invalid twice -> priority = det_score, rationale = templated text.
7.3 Logistics
• Inputs: Incident, resource ledger snapshot, auditor flags (on revision).
• Tools: overpass.facilities(lat, lon, radius_km, types) for hospitals and shelters, geo.haversine, optional osrm.route. Each result is stored as Evidence.
• Output: list of Action (types in the enum above), each with evidence ids. Typical plan: stage resources at the 2 to 3 nearest hospitals, a public alert for the affected zone, and an evacuation advisory when the hazard is flood or aftershock risk is high.
• Prompt skeleton: You plan resource allocation. Choose only facilities returned by tools. Respect the ledger. Every action needs evidence ids. Prefer fewer, well-justified actions. If an auditor flag is present, fix exactly what it names.
• Failure: no facilities found -> action request_mutual_aid with a clear explanation.
7.4 Comms
• Inputs: Plan, Incident, evidence.
• Output: three drafts (sms, social, bulletin), each with English and Hindi text.
• Rules (put in the prompt): calm tone, no panic language, no invented numbers (only numbers present in evidence), include what happened, where, what to do, and the source. SMS in English under 160 characters. Hindi SMS is Unicode, so keep it short (aim under 70 characters per segment and let the UI show the segment count). Always set needs_language_review = true.
• Failure: invalid output -> a template with placeholders filled from evidence.
7.5 Auditor
Runs checks in this order. Checks 1 to 3 are deterministic code; 4 is LLM.
1. Every cited evidence_id exists in the evidence store.
2. Every number appearing in Comms text matches a number in the cited evidence (regex extract and compare).
3. No facility is assigned twice across active plans (ledger check).
4. LLM critique for overreach, alarming tone, and claims not supported by evidence.
Verdicts: pass, revise with specific flags, or escalate after 2 failed revisions. Flags must be short, actionable sentences. The Auditor never edits plans itself.
8. Data sources
Verify each endpoint with a quick curl before relying on it, cache every response, and keep fixtures for all of them.
• USGS earthquakes (live): https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson (also all_day, 4.5_week). Useful fields: properties.mag, alert (PAGER level), sig, tsunami, time, geometry.coordinates (lon, lat, depth).
• USGS historical (for fixtures): https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&starttime=2015-04-25&endtime=2015-04-27&minlatitude=26&maxlatitude=31&minlongitude=80&maxlongitude=89&minmagnitude=4.5
• GDACS (multi-hazard alerts): RSS at https://www.gdacs.org/xml/rss.xml. Check their API docs for the current event-list endpoint. If it is awkward, parse the RSS.
• Open-Meteo weather: https://api.open-meteo.com/v1/forecast with latitude, longitude, hourly=precipitation.
• Open-Meteo flood: https://flood-api.open-meteo.com/v1/flood with daily=river_discharge. Use for the flood leg of the synthetic scenario.
• OpenStreetMap via Overpass: https://overpass-api.de/api/interpreter, POST a query such as [out:json][timeout:25];(node[amenity=hospital](around:30000,LAT,LON);way[amenity=hospital](around:30000,LAT,LON););out center tags;. Population places: node[place~'city|town|village'](around:R,LAT,LON);out tags;. Overpass is rate-limited and sometimes slow: cache aggressively and pre-fetch fixtures for both scenarios.
• OSRM (optional): the public demo server is for light use only. Fall back to haversine lines.
9. Replay engine and scenarios (backend/app/replay.py)
Replay reads fixture events sorted by time and emits them on an accelerated clock (1x to 60x). The UI shows the replay clock. Replay must work with zero network access: store Overpass responses for each scenario region in fixtures.
• Scenario A, Nepal 2015 (real data): the M7.8 mainshock of 25 April 2015 and the M7.3 aftershock of 12 May 2015, fetched from USGS and stored. Strong India relevance, which makes the Hindi comms meaningful. Note in the UI that facility data is current OSM, not 2015.
• Scenario B, compound disaster (SYNTHETIC, labelled): an earthquake and a flood alert in neighbouring districts, placed about 30 km apart so both incidents naturally want the same major hospital. This exercises the ledger, contention handling and the Auditor revision loop. Do not hardcode a fake failure: build the scenario so the contention arises from real tool output.
10. API (FastAPI)
• GET /api/state returns events, incidents, plans, facilities in view.
• GET /api/incidents/{id} returns incident with evidence list.
• GET /api/plans/{id} returns a plan.
• POST /api/plans/{id}/approve and /reject with optional {note}.
• GET /api/trace?incident_id= returns the TraceStep history.
• GET /api/stream is SSE and emits trace, event, incident, plan messages.
• POST /api/mode with {mode: live|replay, scenario?, speed?}; POST /api/replay/stop.
• GET /api/audit-log returns human decisions.
CORS must allow the frontend origin. The frontend should hydrate from /api/state and then apply SSE updates.
11. Frontend specification
Layout (desktop first, one-screen command center)
• Top bar: mode toggle (Live / Replay), scenario picker, speed slider, replay clock, SYNTHETIC badge when relevant.
• Left: incident queue sorted by priority, each with hazard icon, priority chip, status.
• Center: MapLibre map. Layers: events (circle size by magnitude, colour by priority), facilities (icons), planned routes (lines), affected radius (translucent circle). New events pulse once.
• Right: tabs. Activity shows the streaming agent feed with coloured agent chips. Plan shows the selected incident's plan.
Plan panel
• Action list; each action has evidence chips. Clicking a chip opens an evidence drawer showing the summary and raw data.
• Auditor verdict badge with flags listed.
• Comms drafts with tabs for sms / social / bulletin and EN / HI toggle, plus a character or segment counter and a language-review notice.
• Approve and Reject buttons (reject asks for a short note). After a decision, show who and when.
Quality bar
• Dark operations-room look, high contrast, one accent colour, readable at projector distance.
• Loading skeletons, empty states, error toasts, no layout jumps.
• Footer: the honest-framing statement from section 1.
12. Build plan (proportions of the time you have)
• Phase 0, 5%: setup. Repo, .env, models.py, the LLM wrapper, FastAPI skeleton with /api/stream and a fake TraceStep ticker, Next.js app showing it. Exit: the UI shows live fake steps.
• Phase 1, 20%: vertical slice. One hardcoded Nepal event through all five agents with stub or real LLM calls, plan visible in the UI, approve works. Exit: end-to-end demo of one incident.
• Phase 2, 15%: real data. USGS fetch plus cached Overpass facilities and populations, Evidence objects, fixtures saved. Exit: slice runs on real data offline.
• Phase 3, 25%: agent quality. Real prompts, schema validation and fallbacks, det_score and clamp, ledger, Auditor checks, revision loop, Hindi comms. Exit: Scenario B shows contention, audit and revision.
• Phase 4, 20%: UI polish. Map layers, evidence drawer, activity feed styling, approval flow, audit log, skeletons. Exit: the demo looks finished.
• Phase 5, 10%: replay and live. Replay clock and speed, live USGS polling toggle, deployment. Exit: both modes work.
• Phase 6, 5%: submission. README, architecture diagram, demo video, screenshots, final test run.
If time runs short, cut in this order: OSRM routing, extra language, PDF export, live mode, deployment (record locally). Never cut the Auditor or the human approval step, because they are the point of the project.
13. Tests (keep small, run before every demo)
• Unit: det_score mapping, priority clamp, ledger contention, number-matching in the Auditor.
• Contract: every agent output validates against its Pydantic model, including malformed LLM outputs falling back correctly.
• Smoke: run Scenario A and Scenario B in Replay with the network disabled; assert plans reach awaiting_approval and the audit log records an approve.
14. Demo script (2 minutes)
1. 0:00 to 0:15 The problem: during disasters, information arrives faster than humans can triage it. One line on what AEGIS is.
2. 0:15 to 0:40 Start Scenario A at 30x. The Nepal quake appears on the map, Sensor and Triage steps stream in, priority and exposure shown with evidence chips.
3. 0:40 to 1:00 Logistics proposes facilities and routes drawn on the map. Click an evidence chip to show every number is traceable.
4. 1:00 to 1:25 Switch to Scenario B (labelled SYNTHETIC). Two incidents collide on one hospital, contention is logged, the Auditor flags it, Logistics revises. Say plainly that the check is real code.
5. 1:25 to 1:45 Hindi and English alert drafts, then the human approves. The audit log updates.
6. 1:45 to 2:00 Close: grounded in evidence, audited by another agent, humans stay in control, runs offline from recorded data, open source.
Record the video from a clean run, and keep the live demo as a bonus rather than a dependency.
15. Submission checklist
• Public GitHub repo with README: what it is, honest framing, architecture diagram, setup in under 5 commands, screenshots, limitations, and what you would build next.
• Demo video link and, if deployed, a live URL with Replay mode as the default.
• A short write-up covering: why multi-agent, how grounding works, how the Auditor works, the human-in-the-loop design, and the benchmark of your own tests (for example, contention and number-mismatch cases caught in tests).
• Check the Unstop page for required format, deadline, team rules and judging criteria, and whether code must be written during the event. Adjust this spec to match.
16. Risks and mitigations
• Overpass slow or down: pre-fetched fixtures and disk cache; Replay never touches the network.
• LLM returns invalid JSON: schema validation, one retry, deterministic fallback.
• LLM latency during the demo: cache LLM outputs per event in fixtures and make Replay use them; keep a --cached-llm flag.
• Hallucinated numbers: numbers come only from tools, and the Auditor's regex check blocks mismatches.
• Scope creep: the tiers in section 3 are binding; anything outside them goes in a NEXT.md file.
• Overclaiming: never describe the system as operational or as sending alerts. Use the honest framing everywhere.
17. Kickoff prompt to paste to the coding agent
Read this entire spec. Build AEGIS exactly as specified, following the rules in section 2 and the phases in section 12. Start with Phase 0 and Phase 1 and stop for review after the vertical slice works end to end. Keep DECISIONS.md updated, commit after each working step, and tell me before changing scope, data contracts or the stack.