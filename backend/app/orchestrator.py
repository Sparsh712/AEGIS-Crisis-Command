"""End-to-end deterministic orchestration for the AEGIS vertical slice."""

from __future__ import annotations

from datetime import datetime, timezone
from math import asin, cos, radians, sin, sqrt

from .agents import auditor, comms, logistics, sensor, triage
from .bus import publish
from .ledger import ResourceLedger, ledger
from .models import Event, Plan, TraceStep
from .store import AegisStore, store


class AgentContext:
    def __init__(self, data_store: AegisStore, resource_ledger: ResourceLedger) -> None:
        self.store = data_store
        self.ledger = resource_ledger
        self.incident_id: str | None = None
        self.event: Event | None = None

    async def trace(self, agent: str, kind: str, message: str, refs: dict[str, object]) -> None:
        step = TraceStep(
            ts=datetime.now(timezone.utc), agent=agent, kind=kind, message=message, refs=refs
        )
        self.store.add_trace(step)
        await publish(step)


def _distance_km(first: Event, second: Event) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (first.lat, first.lon, second.lat, second.lon))
    value = sin((lat2 - lat1) / 2) ** 2 + cos(lat1) * cos(lat2) * sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * asin(sqrt(value))


def _existing_incident(data_store: AegisStore, event: Event) -> str | None:
    for incident in data_store.list_incidents():
        if incident.hazard != event.hazard:
            continue
        for event_id in incident.event_ids:
            prior = data_store.get_event(event_id)
            if prior and abs((event.occurred_at - prior.occurred_at).total_seconds()) <= 86_400:
                if _distance_km(event, prior) <= 100:
                    return incident.id
    return None


async def process_event(
    event: Event,
    *,
    data_store: AegisStore | None = None,
    resource_ledger: ResourceLedger | None = None,
) -> Plan:
    data_store = data_store or store
    resource_ledger = resource_ledger or ledger
    existing_plan = None
    for candidate in data_store.list_plans():
        candidate_incident = data_store.get_incident(candidate.incident_id)
        if candidate_incident is not None and event.id in candidate_incident.event_ids:
            existing_plan = candidate
            break
    if existing_plan:
        return existing_plan

    context = AgentContext(data_store, resource_ledger)
    context.event = event
    await sensor.run(event, context)
    context.incident_id = _existing_incident(data_store, event) or f"incident:{event.id}"
    incident = await triage.run(event, context)
    plan = await logistics.run(incident, context)
    plan = await comms.run(plan, incident, context)

    for attempt in range(3):
        result = await auditor.run(plan, incident, context)
        plan.auditor_verdict = result.verdict
        plan.auditor_flags = result.flags
        if result.verdict == "pass":
            plan.status = "awaiting_approval"
            data_store.add_plan(plan)
            await context.trace(
                "auditor",
                "decision",
                "Audit passed; plan is awaiting human approval.",
                {"incident_id": incident.id, "plan_id": plan.id},
            )
            return plan
        if attempt == 2:
            plan.status = "escalated"
            data_store.add_plan(plan)
            await context.trace(
                "auditor",
                "decision",
                "Two revision rounds were exhausted; plan escalated to a human.",
                {"incident_id": incident.id, "plan_id": plan.id, "flags": result.flags},
            )
            return plan
        plan.revision = attempt + 1
        plan = await logistics.run(incident, context, existing_plan=plan)
        plan = await comms.run(plan, incident, context)

    raise RuntimeError("unreachable orchestration state")


async def run_sample(
    *, data_store: AegisStore | None = None, resource_ledger: ResourceLedger | None = None
) -> Plan:
    return await process_event(
        sensor.sample_event(), data_store=data_store, resource_ledger=resource_ledger
    )
