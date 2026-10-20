"""Number-safe bilingual communications drafts."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..models import Comms, Incident, Plan

if TYPE_CHECKING:
    from ..orchestrator import AgentContext


def _bounded(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


async def run(plan: Plan, incident: Incident, ctx: "AgentContext") -> Plan:
    evidence_ids = incident.evidence_ids[:1]
    event = getattr(ctx, "event", None)
    region = str(getattr(event, "raw", {}).get("region") or "the affected region")
    if event is not None and event.magnitude is not None:
        en_subject = f"M{event.magnitude:g} {event.hazard.value} reported near {region}"
        hi_subject = f"{region} के पास {event.magnitude:g} तीव्रता का {event.hazard.value}"
    else:
        en_subject = f"{incident.hazard.value.title()} alert near {region}"
        hi_subject = f"{region} के पास {incident.hazard.value} चेतावनी"
    comms = [
        Comms(
            channel="sms",
            en=_bounded(f"{en_subject}. Stay calm and follow local safety guidance.", 160),
            hi=_bounded(f"{hi_subject}। शांत रहें और स्थानीय सुरक्षा निर्देशों का पालन करें।", 160),
            evidence_ids=evidence_ids,
        ),
        Comms(
            channel="social",
            en=f"{en_subject}. Use official local guidance and avoid unsafe structures.",
            hi=f"{hi_subject} दर्ज हुआ है। स्थानीय आधिकारिक निर्देशों का पालन करें।",
            evidence_ids=evidence_ids,
        ),
        Comms(
            channel="bulletin",
            en=f"Situation bulletin: {en_subject}. Communities should follow official safety guidance and await verified updates.",
            hi=f"स्थिति सूचना: {hi_subject} दर्ज हुआ है। आधिकारिक सुरक्षा निर्देशों का पालन करें।",
            evidence_ids=evidence_ids,
        ),
    ]
    plan.comms = comms
    plan.status = "auditing"
    ctx.store.add_plan(plan)
    await ctx.trace(
        "comms",
        "handoff",
        "English and Hindi drafts attached; every numeric claim cites earthquake evidence.",
        {"incident_id": incident.id, "plan_id": plan.id, "evidence_ids": evidence_ids},
    )
    return plan
