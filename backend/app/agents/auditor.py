"""Auditor checks that block unsupported or conflicting plans."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field

from ..models import Evidence, Incident, Plan

if TYPE_CHECKING:
    from ..orchestrator import AgentContext


class AuditResult(BaseModel):
    verdict: str
    flags: list[str] = Field(default_factory=list)


NUMBER_RE = re.compile(r"\d+(?:[.,]\d+)?")


def extract_numbers(text: str) -> set[str]:
    return {match.replace(",", "") for match in NUMBER_RE.findall(text)}


def _evidence_numbers(evidence: Evidence) -> set[str]:
    values = extract_numbers(evidence.summary)

    def visit(value: object) -> None:
        if isinstance(value, bool):
            return
        if isinstance(value, (int, float)):
            values.update(extract_numbers(str(value)))
        elif isinstance(value, dict):
            for item in value.values():
                visit(item)
        elif isinstance(value, list):
            for item in value:
                visit(item)

    visit(evidence.data)
    return values


def number_claims_are_grounded(plan: Plan, evidence: dict[str, Evidence]) -> list[str]:
    flags: list[str] = []
    for comm in plan.comms:
        cited_numbers: set[str] = set()
        for evidence_id in comm.evidence_ids:
            item = evidence.get(evidence_id)
            if item:
                cited_numbers.update(_evidence_numbers(item))
        for language, text in (("English", comm.en), ("Hindi", comm.hi)):
            unsupported = extract_numbers(text) - cited_numbers
            if unsupported:
                flags.append(
                    f"{comm.channel} {language} contains unsupported number(s): {', '.join(sorted(unsupported))}."
                )
    return flags


numbers_match_evidence = number_claims_are_grounded


async def run(plan: Plan, incident: Incident, ctx: "AgentContext") -> AuditResult:
    flags: list[str] = []
    evidence = ctx.store.evidence
    cited_ids = set(incident.evidence_ids)
    for action in plan.actions:
        cited_ids.update(action.evidence_ids)
    for comm in plan.comms:
        cited_ids.update(comm.evidence_ids)
    missing = sorted(evidence_id for evidence_id in cited_ids if evidence_id not in evidence)
    if missing:
        flags.append(f"Missing evidence id(s): {', '.join(missing)}.")
    flags.extend(number_claims_are_grounded(plan, evidence))
    conflicts = ctx.ledger.conflicts(plan)
    if conflicts:
        flags.append(f"Facility is double-booked: {', '.join(sorted(set(conflicts)))}.")
    if any(term in f"{plan.comms}".lower() for term in ("panic", "guaranteed", "immediately evacuate")):
        flags.append("Use calm language and remove unsupported urgency.")
    result = AuditResult(verdict="revise" if flags else "pass", flags=flags)
    await ctx.trace(
        "auditor",
        "critique",
        "Plan passed deterministic evidence, number, and ledger checks."
        if result.verdict == "pass"
        else f"Plan requires revision: {len(flags)} auditor flag(s).",
        {"incident_id": incident.id, "plan_id": plan.id, "verdict": result.verdict, "flags": flags},
    )
    return result
