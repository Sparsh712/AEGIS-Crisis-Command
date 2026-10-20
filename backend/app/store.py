"""Deterministic SQLite JSON-row persistence for the AEGIS backend."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, TypeVar

from pydantic import BaseModel

from .models import AuditEntry, Event, Evidence, Facility, Incident, Plan, TraceStep


ModelT = TypeVar("ModelT", bound=BaseModel)


def _default_path() -> Path:
    configured = os.getenv("AEGIS_DB_PATH")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[1] / "aegis.sqlite3"


class AegisStore:
    """Small typed facade over SQLite tables whose payloads are JSON rows.

    The dictionaries are the fast in-process view while every mutation is also
    written to SQLite.  This keeps the Level 1 flow simple and makes a process
    restart recover the incident, plan, trace, and audit history.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = str(path or _default_path())
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(self.path, check_same_thread=False)
        self._connection.row_factory = sqlite3.Row
        self._lock = RLock()
        self.events: dict[str, Event] = {}
        self.evidence: dict[str, Evidence] = {}
        self.incidents: dict[str, Incident] = {}
        self.plans: dict[str, Plan] = {}
        self.facilities: dict[str, Facility] = {}
        self.trace: list[TraceStep] = []
        self.audit_log: list[AuditEntry] = []
        self._create_schema()
        self._load()

    def _create_schema(self) -> None:
        with self._connection:
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS json_rows (
                    kind TEXT NOT NULL,
                    item_id TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    PRIMARY KEY (kind, item_id)
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS trace_rows (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    payload TEXT NOT NULL
                )
                """
            )
            self._connection.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_rows (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    item_id TEXT NOT NULL UNIQUE,
                    payload TEXT NOT NULL
                )
                """
            )

    @staticmethod
    def _dump(model: BaseModel) -> str:
        return json.dumps(model.model_dump(mode="json"), sort_keys=True)

    @staticmethod
    def _load_payload(payload: str, model_type: type[ModelT]) -> ModelT:
        return model_type.model_validate(json.loads(payload))

    def _load(self) -> None:
        with self._lock:
            rows = self._connection.execute(
                "SELECT kind, item_id, payload FROM json_rows ORDER BY item_id"
            ).fetchall()
            loaders: dict[str, tuple[type[BaseModel], dict[str, BaseModel]]] = {
                "event": (Event, self.events),
                "evidence": (Evidence, self.evidence),
                "incident": (Incident, self.incidents),
                "plan": (Plan, self.plans),
                "facility": (Facility, self.facilities),
            }
            for row in rows:
                loader = loaders.get(row["kind"])
                if loader:
                    model_type, target = loader
                    target[row["item_id"]] = self._load_payload(row["payload"], model_type)

            self.trace = [
                self._load_payload(row["payload"], TraceStep)
                for row in self._connection.execute(
                    "SELECT payload FROM trace_rows ORDER BY seq"
                ).fetchall()
            ]
            self.audit_log = [
                self._load_payload(row["payload"], AuditEntry)
                for row in self._connection.execute(
                    "SELECT payload FROM audit_rows ORDER BY seq"
                ).fetchall()
            ]

    def _put(self, kind: str, item_id: str, model: BaseModel) -> None:
        payload = self._dump(model)
        timestamp = datetime.now(timezone.utc).isoformat()
        with self._lock, self._connection:
            self._connection.execute(
                """
                INSERT INTO json_rows(kind, item_id, payload, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(kind, item_id) DO UPDATE SET
                    payload = excluded.payload,
                    updated_at = excluded.updated_at
                """,
                (kind, item_id, payload, timestamp),
            )

    def add_event(self, event: Event) -> Event:
        self.events[event.id] = event
        self._put("event", event.id, event)
        return event

    def add_evidence(self, evidence: Evidence) -> Evidence:
        self.evidence[evidence.id] = evidence
        self._put("evidence", evidence.id, evidence)
        return evidence

    def add_incident(self, incident: Incident) -> Incident:
        self.incidents[incident.id] = incident
        self._put("incident", incident.id, incident)
        return incident

    def add_plan(self, plan: Plan) -> Plan:
        self.plans[plan.id] = plan
        self._put("plan", plan.id, plan)
        return plan

    def add_facility(self, facility: Facility) -> Facility:
        self.facilities[facility.id] = facility
        self._put("facility", facility.id, facility)
        return facility

    def get_event(self, event_id: str) -> Event | None:
        return self.events.get(event_id)

    def get_incident(self, incident_id: str) -> Incident | None:
        return self.incidents.get(incident_id)

    def get_plan(self, plan_id: str) -> Plan | None:
        return self.plans.get(plan_id)

    def get_evidence(self, evidence_id: str) -> Evidence | None:
        return self.evidence.get(evidence_id)

    def list_events(self) -> list[Event]:
        return list(self.events.values())

    def list_incidents(self) -> list[Incident]:
        return list(self.incidents.values())

    def list_plans(self) -> list[Plan]:
        return list(self.plans.values())

    def list_evidence(self) -> list[Evidence]:
        return list(self.evidence.values())

    def list_facilities(self) -> list[Facility]:
        return list(self.facilities.values())

    def next_evidence_id(self) -> str:
        numeric_ids = [
            int(item_id[1:])
            for item_id in self.evidence
            if item_id.startswith("e") and item_id[1:].isdigit()
        ]
        return f"e{max(numeric_ids, default=0) + 1}"

    def create_evidence(
        self, tool: str, summary: str, data: dict[str, Any], *, evidence_id: str | None = None
    ) -> Evidence:
        evidence = Evidence(
            id=evidence_id or self.next_evidence_id(),
            tool=tool,
            summary=summary,
            data=data,
            fetched_at=datetime.now(timezone.utc),
        )
        return self.add_evidence(evidence)

    def add_trace(self, step: TraceStep) -> TraceStep:
        payload = self._dump(step)
        with self._lock, self._connection:
            self._connection.execute("INSERT INTO trace_rows(payload) VALUES (?)", (payload,))
        self.trace.append(step)
        return step

    def list_trace(self, incident_id: str | None = None) -> list[TraceStep]:
        if incident_id is None:
            return list(self.trace)
        return [step for step in self.trace if step.refs.get("incident_id") == incident_id]

    def add_audit(self, entry: AuditEntry) -> AuditEntry:
        payload = self._dump(entry)
        with self._lock, self._connection:
            self._connection.execute(
                "INSERT OR REPLACE INTO audit_rows(item_id, payload) VALUES (?, ?)",
                (entry.id, payload),
            )
        self.audit_log = [item for item in self.audit_log if item.id != entry.id]
        self.audit_log.append(entry)
        return entry

    def list_audit(self) -> list[AuditEntry]:
        return list(self.audit_log)

    def clear(self) -> None:
        with self._lock, self._connection:
            self._connection.execute("DELETE FROM json_rows")
            self._connection.execute("DELETE FROM trace_rows")
            self._connection.execute("DELETE FROM audit_rows")
        self.events.clear()
        self.evidence.clear()
        self.incidents.clear()
        self.plans.clear()
        self.facilities.clear()
        self.trace.clear()
        self.audit_log.clear()

    reset = clear

    def close(self) -> None:
        self._connection.close()


Store = AegisStore
SQLiteStore = AegisStore


store = AegisStore()
