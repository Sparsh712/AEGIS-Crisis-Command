"""Triage agent with deterministic scoring and evidence-grounded output."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..models import Event, Incident
from ..tools.overpass import places_population

if TYPE_CHECKING:
    from ..orchestrator import AgentContext


class TriageDecision(BaseModel):
    priority: int = Field(ge=1, le=5)
    rationale: str
    evidence_ids: list[str] = Field(default_factory=list)


def deterministic_score(event: Event, exposure_estimate: int | None = None) -> int:
    alert_scores = {"green": 1, "yellow": 2, "orange": 3, "red": 4}
    if event.alert_level in alert_scores:
        score = alert_scores[event.alert_level]
    elif event.magnitude is None:
        score = 1
    elif event.magnitude < 5:
        score = 1
    elif event.magnitude < 6:
        score = 2
    elif event.magnitude < 7:
        score = 3
    else:
        score = 4
    if event.raw.get("tsunami") or (exposure_estimate is not None and exposure_estimate >= 500_000):
        score += 1
    return min(score, 5)


def _clamp_priority(priority: int, det_score: int) -> int:
    return max(1, min(5, max(det_score - 1, min(det_score + 1, priority))))


async def run(event: Event, ctx: "AgentContext") -> Incident:
    fixture = "compound_synthetic" if event.synthetic else "nepal_2015"
    exposure = int(event.raw.get("exposure_estimate") or places_population(event.lat, event.lon, 40, fixture=fixture))
    magnitude_text = f"magnitude {event.magnitude:g}" if event.magnitude is not None else f"{event.hazard.value} alert"
    region = str(event.raw.get("region") or "the affected region")
    event_evidence = ctx.store.create_evidence(
        "usgs",
        f"{event.source.upper()} reports {magnitude_text} with {event.alert_level or 'unknown'} alert level near {region}.",
        {"event_id": event.id, "magnitude": event.magnitude, "hazard": event.hazard.value, "alert_level": event.alert_level, "lat": event.lat, "lon": event.lon},
        evidence_id="e1" if "e1" not in ctx.store.evidence else None,
    )
    exposure_evidence = ctx.store.create_evidence(
        "overpass.population",
        f"Nearby-place population lower bound is {exposure} people within the 40 km replay estimate.",
        {"event_id": event.id, "exposure_estimate": exposure, "radius_km": 30},
        evidence_id="e2" if "e2" not in ctx.store.evidence else None,
    )
    det_score = deterministic_score(event, exposure)
    decision = TriageDecision(
        priority=_clamp_priority(det_score, det_score),
        rationale=(
            f"The {event.alert_level or 'available'} alert and {magnitude_text} indicate urgency; "
            f"the {exposure}-person lower-bound exposure is included as evidence."
        ),
        evidence_ids=[event_evidence.id, exposure_evidence.id],
    )
    incident_id = getattr(ctx, "incident_id", None) or f"incident:{event.id}"
    previous = ctx.store.get_incident(incident_id)
    event_ids = list(previous.event_ids) if previous else []
    if event.id not in event_ids:
        event_ids.append(event.id)
    combined_evidence_ids = list(previous.evidence_ids) if previous else []
    for evidence_id in decision.evidence_ids:
        if evidence_id not in combined_evidence_ids:
            combined_evidence_ids.append(evidence_id)
    incident = Incident(
        id=incident_id,
        event_ids=event_ids,
        hazard=event.hazard,
        det_score=max(previous.det_score, det_score) if previous else det_score,
        priority=max(previous.priority, decision.priority) if previous else decision.priority,
        exposure_estimate=exposure,
        rationale=decision.rationale,
        evidence_ids=combined_evidence_ids,
    )
    ctx.store.add_incident(incident)
    await ctx.trace(
        "triage",
        "reason",
        f"Incident triaged at priority P{incident.priority}; deterministic score is {det_score}.",
        {"event_id": event.id, "incident_id": incident.id, "evidence_ids": incident.evidence_ids},
    )
    return incident


det_score = deterministic_score
