"""Deterministic resource allocation ledger used by Logistics and Auditor."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from .models import Action, Plan


@dataclass(frozen=True)
class LedgerAssignment:
    facility_id: str
    incident_id: str
    priority: int


class ResourceLedger:
    """Greedy, process-local ledger with idempotent reservations."""

    DEFAULT_CAPACITIES = {"hospital": 100, "clinic": 10, "shelter": 250}

    def __init__(self) -> None:
        self.assignments: dict[str, LedgerAssignment] = {}
        self._lock = RLock()

    def reset(self) -> None:
        with self._lock:
            self.assignments.clear()

    def reserve(self, facility_id: str, incident_id: str, priority: int) -> bool:
        """Reserve a facility, allowing the same incident to reserve it again.

        A higher-priority incident can displace a lower-priority reservation;
        callers process incidents in priority order so the normal path is
        simply a rejection for a lower-priority contention.
        """

        with self._lock:
            current = self.assignments.get(facility_id)
            if current is None or current.incident_id == incident_id:
                self.assignments[facility_id] = LedgerAssignment(
                    facility_id, incident_id, priority
                )
                return True
            if priority > current.priority:
                self.assignments[facility_id] = LedgerAssignment(
                    facility_id, incident_id, priority
                )
                return True
            return False

    def release_incident(self, incident_id: str) -> None:
        with self._lock:
            for facility_id, assignment in tuple(self.assignments.items()):
                if assignment.incident_id == incident_id:
                    del self.assignments[facility_id]

    def assignment_for(self, facility_id: str) -> LedgerAssignment | None:
        return self.assignments.get(facility_id)

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [assignment.__dict__.copy() for assignment in self.assignments.values()]

    def conflicts(self, plan: Plan) -> list[str]:
        """Return facility ids that are assigned to another active incident."""

        conflicts: list[str] = []
        seen: set[str] = set()
        with self._lock:
            for action in plan.actions:
                if action.type != "stage_resources":
                    continue
                if action.target in seen:
                    conflicts.append(action.target)
                    continue
                seen.add(action.target)
                assignment = self.assignments.get(action.target)
                if assignment and assignment.incident_id != plan.incident_id:
                    conflicts.append(action.target)
        return conflicts


ledger = ResourceLedger()


Ledger = ResourceLedger
