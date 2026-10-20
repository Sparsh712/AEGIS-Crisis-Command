"""Logistics agent and its deterministic facility fixture."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import Action, Facility, Incident, Plan
from ..tools.overpass import facilities as fixture_facilities

if TYPE_CHECKING:
    from ..orchestrator import AgentContext


FACILITY_FIXTURE = (
    {"id": "fac-gorkha-hospital", "name": "Gorkha District Hospital", "type": "hospital", "lat": 28.0000, "lon": 84.6330, "capacity": 100, "distance_km": 18.6},
    {"id": "fac-kathmandu-medical", "name": "Kathmandu Medical Center", "type": "hospital", "lat": 27.7172, "lon": 85.3240, "capacity": 100, "distance_km": 72.4},
    {"id": "fac-gorkha-clinic", "name": "Gorkha Community Clinic", "type": "clinic", "lat": 28.0005, "lon": 84.6300, "capacity": 10, "distance_km": 18.9},
)


def _ensure_facilities(ctx: "AgentContext") -> list[Facility]:
    event = getattr(ctx, "event", None)
    if event is not None:
        fixture = "compound_synthetic" if event.synthetic else "nepal_2015"
        found = fixture_facilities(event.lat, event.lon, 120, types=("hospital", "clinic"), fixture=fixture)
        if found:
            for facility in found:
                if facility.id not in ctx.store.facilities:
                    evidence = ctx.store.create_evidence(
                        "overpass.facilities",
                        f"{facility.name} is {facility.distance_km} km from the event with estimated capacity {facility.capacity}.",
                        {"facility_id": facility.id, "name": facility.name, "type": facility.type, "distance_km": facility.distance_km, "capacity": facility.capacity, "capacity_estimated": facility.capacity_estimated},
                    )
                    facility.evidence_ids = [evidence.id]
                    ctx.store.add_facility(facility)
            return [ctx.store.facilities[item.id] for item in found]
    facilities: list[Facility] = []
    for raw in FACILITY_FIXTURE:
        existing = ctx.store.facilities.get(raw["id"])
        if existing:
            facilities.append(existing)
            continue
        evidence = ctx.store.create_evidence(
            "overpass.facilities",
            f"{raw['name']} is {raw['distance_km']} km from the event with estimated capacity {raw['capacity']}.",
            {
                "facility_id": raw["id"],
                "name": raw["name"],
                "type": raw["type"],
                "distance_km": raw["distance_km"],
                "capacity": raw["capacity"],
                "capacity_estimated": True,
            },
        )
        facility = Facility(
            **raw,
            capacity_estimated=True,
            evidence_ids=[evidence.id],
        )
        ctx.store.add_facility(facility)
        facilities.append(facility)
    return facilities


async def run(
    incident: Incident, ctx: "AgentContext", existing_plan: Plan | None = None
) -> Plan:
    facilities = sorted(_ensure_facilities(ctx), key=lambda item: item.distance_km or 0)
    actions: list[Action] = []
    selected = 0
    for facility in facilities:
        if facility.type not in {"hospital", "clinic"} or selected >= 2:
            continue
        if not ctx.ledger.reserve(facility.id, incident.id, incident.priority):
            current = ctx.ledger.assignment_for(facility.id)
            await ctx.trace(
                "logistics",
                "critique",
                f"Contention: {facility.name} is reserved by a higher-priority incident; choosing the next facility.",
                {"incident_id": incident.id, "facility_id": facility.id, "existing": current.incident_id if current else None},
            )
            continue
        actions.append(
            Action(
                type="stage_resources",
                target=facility.id,
                detail=f"Stage emergency resources at {facility.name}; capacity is an estimate.",
                evidence_ids=facility.evidence_ids,
            )
        )
        selected += 1

    if not actions:
        actions.append(
            Action(
                type="request_mutual_aid",
                target="regional-coordination",
                detail="No unassigned nearby facility remains; request mutual aid.",
                evidence_ids=incident.evidence_ids,
            )
        )
    region = str(getattr(getattr(ctx, "event", None), "raw", {}).get("region") or "the affected zone")
    actions.append(
        Action(
            type="public_alert",
            target=region,
            detail="Prepare a calm public safety bulletin for the affected zone.",
            evidence_ids=incident.evidence_ids,
        )
    )
    plan = existing_plan or Plan(
        id=f"plan:{incident.id}",
        incident_id=incident.id,
        actions=[],
        status="drafting",
    )
    plan.actions = actions
    plan.status = "drafting"
    ctx.store.add_plan(plan)
    await ctx.trace(
        "logistics",
        "tool_call",
        f"Selected {selected} nearby resource location(s); public alert action added.",
        {"incident_id": incident.id, "plan_id": plan.id, "facility_ids": [a.target for a in actions if a.type == "stage_resources"]},
    )
    return plan
