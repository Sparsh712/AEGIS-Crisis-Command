"""FastAPI entry point for the AEGIS backend."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from typing import AsyncIterator

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .bus import publish, subscribe
from .config import settings
from .ledger import ledger
from .models import AuditEntry, DecisionRequest, Event, ModeRequest, TraceStep
from .orchestrator import process_event, run_sample
from .replay import ReplayEngine, load_scenario
from .store import store
from .tools.usgs import fetch_live_events


async def _fake_trace_ticker() -> None:
    tick = 0
    while True:
        await asyncio.sleep(settings.trace_interval_seconds)
        tick += 1
        await publish(
            TraceStep(
                ts=datetime.now(timezone.utc),
                agent="system",
                kind="observe",
                message=f"Level 0 fake trace tick {tick}",
                refs={"tick": tick},
            )
        )


replay_task: asyncio.Task[None] | None = None
runtime_mode: dict[str, object] = {
    "mode": "replay",
    "scenario": "nepal_2015",
    "speed": 30.0,
    "running": False,
    "clock": None,
    "poll_count": 0,
    "cache_status": None,
    "fallback": False,
    "deduped_count": 0,
    "last_poll_at": None,
    "network": False,
}


async def _emit_trace(step: TraceStep) -> None:
    """Persist and stream a trace step so status is visible through both APIs."""

    store.add_trace(step)
    await publish(step)


async def _run_replay(scenario_name: str, speed: float) -> None:
    scenario = load_scenario(scenario_name)
    runtime_mode.update({"scenario": scenario.name, "speed": speed, "running": True, "clock": None})
    await publish(
        TraceStep(
            ts=datetime.now(timezone.utc),
            agent="sensor",
            kind="observe",
            message=f"Replay started: {scenario.label}{' / SYNTHETIC' if scenario.synthetic else ''}.",
            refs={"scenario": scenario.name, "synthetic": scenario.synthetic},
        )
    )

    async def on_clock(clock_at: datetime, event: Event) -> None:
        runtime_mode["clock"] = clock_at.isoformat()
        await publish(
            TraceStep(
                ts=datetime.now(timezone.utc),
                agent="system",
                kind="observe",
                message=f"Replay clock {clock_at.isoformat()} reached {getattr(event, 'id', 'event')}.",
                refs={"scenario": scenario.name, "clock": clock_at.isoformat()},
            )
        )

    async def on_event(event: Event) -> None:
        await process_event(event, data_store=store, resource_ledger=ledger)

    try:
        await ReplayEngine(scenario, speed=speed).run(on_event, on_clock)
    finally:
        runtime_mode["running"] = False


async def _run_live() -> None:
    """Poll the USGS adapter a bounded number of times with event dedupe."""

    seen_event_ids: set[str] = set()
    runtime_mode.update(
        {
            "running": True,
            "poll_count": 0,
            "cache_status": None,
            "fallback": False,
            "deduped_count": 0,
            "last_poll_at": None,
            "network": settings.live_enabled and not settings.fixture_only,
        }
    )
    try:
        for poll_number in range(1, settings.live_max_polls + 1):
            if poll_number > 1:
                await asyncio.sleep(settings.live_poll_interval_seconds)
            feed = await fetch_live_events(
                url=settings.usgs_feed_url,
                fixture_only=settings.fixture_only,
            )
            metadata = dict(feed.metadata)
            poll_time = datetime.now(timezone.utc).isoformat()
            runtime_mode.update(
                {
                    "poll_count": poll_number,
                    "cache_status": metadata.get("cache_status"),
                    "fallback": bool(metadata.get("fallback", False)),
                    "last_poll_at": poll_time,
                    "network": bool(metadata.get("network_attempted", False)),
                }
            )
            await _emit_trace(
                TraceStep(
                    ts=datetime.now(timezone.utc),
                    agent="sensor",
                    kind="observe",
                    message=(
                        f"USGS live poll {poll_number}/{settings.live_max_polls}: "
                        f"{len(feed.events)} event(s), cache {metadata.get('cache_status', 'unknown')}."
                    ),
                    refs={
                        "mode": "live",
                        "poll": poll_number,
                        "event_count": len(feed.events),
                        "cache_status": metadata.get("cache_status"),
                        "fallback": metadata.get("fallback", False),
                        "fallback_source": metadata.get("fallback_source"),
                        "attempts": metadata.get("attempts", 0),
                    },
                )
            )
            for event in feed.events:
                if event.id in seen_event_ids or store.get_event(event.id) is not None:
                    current_deduped = runtime_mode.get("deduped_count", 0)
                    runtime_mode["deduped_count"] = (
                        (current_deduped if isinstance(current_deduped, int) else 0) + 1
                    )
                    await _emit_trace(
                        TraceStep(
                            ts=datetime.now(timezone.utc),
                            agent="sensor",
                            kind="dedupe",
                            message=f"USGS event {event.id} already processed; skipped.",
                            refs={"mode": "live", "event_id": event.id, "deduped": True},
                        )
                    )
                    continue
                seen_event_ids.add(event.id)
                await process_event(event, data_store=store, resource_ledger=ledger)
    finally:
        runtime_mode["running"] = False


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        global replay_task
        if replay_task is not None and not replay_task.done():
            replay_task.cancel()
            await asyncio.gather(replay_task, return_exceptions=True)


app = FastAPI(title="AEGIS Backend", version="0.2.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "aegis-backend",
        "fake_llm": settings.fake_llm,
    }


@app.get("/api/state")
async def state() -> dict[str, object]:
    return {
        "events": [item.model_dump(mode="json") for item in store.list_events()],
        "incidents": [item.model_dump(mode="json") for item in store.list_incidents()],
        "plans": [item.model_dump(mode="json") for item in store.list_plans()],
        "facilities": [item.model_dump(mode="json") for item in store.list_facilities()],
        "evidence": [item.model_dump(mode="json") for item in store.list_evidence()],
        "audit_log": [item.model_dump(mode="json") for item in store.list_audit()],
        "mode": dict(runtime_mode),
    }


@app.get("/api/incidents/{incident_id}")
async def incident_detail(incident_id: str) -> dict[str, object]:
    incident = store.get_incident(incident_id)
    if incident is None:
        raise HTTPException(status_code=404, detail="Incident not found")
    payload = incident.model_dump(mode="json")
    payload["events"] = [
        event.model_dump(mode="json")
        for event_id in incident.event_ids
        if (event := store.get_event(event_id)) is not None
    ]
    payload["evidence"] = [
        evidence.model_dump(mode="json")
        for evidence_id in incident.evidence_ids
        if (evidence := store.get_evidence(evidence_id)) is not None
    ]
    return payload


@app.get("/api/plans/{plan_id}")
async def plan_detail(plan_id: str) -> dict[str, object]:
    plan = store.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan.model_dump(mode="json")


async def _decide_plan(plan_id: str, decision: str, payload: DecisionRequest | None) -> dict[str, object]:
    plan = store.get_plan(plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    if plan.status != "awaiting_approval":
        raise HTTPException(status_code=409, detail="Plan is not awaiting approval")
    plan.status = decision
    store.add_plan(plan)
    entry = AuditEntry(
        id=f"audit:{plan.id}:{decision}",
        plan_id=plan.id,
        incident_id=plan.incident_id,
        decision=decision,
        note=payload.note if payload else None,
        decided_at=datetime.now(timezone.utc),
    )
    store.add_audit(entry)
    human_step = TraceStep(
        ts=entry.decided_at,
        agent="human",
        kind="human",
        message=f"Human {decision} plan {plan.id}.",
        refs={"incident_id": plan.incident_id, "plan_id": plan.id, "decision": decision},
    )
    store.add_trace(human_step)
    await publish(human_step)
    return plan.model_dump(mode="json")


@app.post("/api/plans/{plan_id}/approve")
async def approve_plan(plan_id: str, payload: DecisionRequest | None = None) -> dict[str, object]:
    return await _decide_plan(plan_id, "approved", payload)


@app.post("/api/plans/{plan_id}/reject")
async def reject_plan(plan_id: str, payload: DecisionRequest | None = None) -> dict[str, object]:
    return await _decide_plan(plan_id, "rejected", payload)


@app.get("/api/audit-log")
async def audit_log() -> list[dict[str, object]]:
    return [entry.model_dump(mode="json") for entry in store.list_audit()]


@app.post("/api/dev/inject-sample")
async def inject_sample() -> dict[str, object]:
    plan = await run_sample(data_store=store, resource_ledger=ledger)
    return plan.model_dump(mode="json")


@app.get("/api/scenarios")
async def scenarios() -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for name in ("nepal_2015", "compound_synthetic"):
        scenario = load_scenario(name)
        result.append(
            {
                "name": scenario.name,
                "label": scenario.label,
                "synthetic": scenario.synthetic,
                "event_count": len(scenario.events),
            }
        )
    return result


@app.post("/api/mode")
async def set_mode(payload: ModeRequest) -> dict[str, object]:
    global replay_task
    if replay_task is not None and not replay_task.done():
        replay_task.cancel()
        await asyncio.gather(replay_task, return_exceptions=True)
    store.clear()
    ledger.reset()
    runtime_mode.update(
        {
            "mode": payload.mode,
            "scenario": payload.scenario,
            "speed": payload.speed,
            "running": False,
            "clock": None,
            "poll_count": 0,
            "cache_status": None,
            "fallback": False,
            "deduped_count": 0,
            "last_poll_at": None,
            "network": False,
        }
    )
    if payload.mode == "replay":
        try:
            load_scenario(payload.scenario)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=400, detail=f"Invalid replay scenario: {exc}") from exc
        replay_task = asyncio.create_task(
            _run_replay(payload.scenario, payload.speed), name="aegis-replay"
        )
    else:
        if settings.live_enabled or settings.fixture_only:
            replay_task = asyncio.create_task(_run_live(), name="aegis-live")
        else:
            await _emit_trace(
                TraceStep(
                    ts=datetime.now(timezone.utc),
                    agent="sensor",
                    kind="observe",
                    message="Live mode selected; external polling is disabled by configuration.",
                    refs={
                        "mode": "live",
                        "cache_status": "disabled",
                        "fallback": True,
                        "fallback_source": "none",
                        "network": False,
                    },
                )
            )
    return dict(runtime_mode)


@app.post("/api/replay/stop")
async def stop_replay() -> dict[str, object]:
    global replay_task
    if replay_task is not None and not replay_task.done():
        replay_task.cancel()
        await asyncio.gather(replay_task, return_exceptions=True)
    runtime_mode["running"] = False
    return dict(runtime_mode)


@app.get("/api/trace")
async def trace(incident_id: str | None = None) -> list[dict[str, object]]:
    return [step.model_dump(mode="json") for step in store.list_trace(incident_id)]


async def _stream_trace(request: Request) -> AsyncIterator[dict[str, str]]:
    async with subscribe() as queue:
        while not await request.is_disconnected():
            try:
                step = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {
                "event": "trace",
                "data": json.dumps(step.model_dump(mode="json")),
            }


@app.get("/api/stream")
async def stream(request: Request) -> EventSourceResponse:
    return EventSourceResponse(
        _stream_trace(request),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
