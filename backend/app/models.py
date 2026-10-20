"""Pydantic data contracts shared by the AEGIS backend and frontend."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class Hazard(str, Enum):
    earthquake = "earthquake"
    flood = "flood"
    cyclone = "cyclone"
    other = "other"


class Event(BaseModel):
    id: str
    source: str
    hazard: Hazard
    lat: float
    lon: float
    magnitude: float | None = None
    alert_level: str | None = None
    occurred_at: datetime
    raw: dict[str, Any] = Field(default_factory=dict)
    synthetic: bool = False


class Evidence(BaseModel):
    id: str
    tool: str
    summary: str
    data: dict[str, Any]
    fetched_at: datetime


class Facility(BaseModel):
    id: str
    name: str
    type: str
    lat: float
    lon: float
    capacity: int = Field(ge=0)
    capacity_estimated: bool = True
    distance_km: float | None = Field(default=None, ge=0)
    evidence_ids: list[str] = Field(default_factory=list)


class Incident(BaseModel):
    id: str
    event_ids: list[str]
    hazard: Hazard
    det_score: int = Field(ge=1, le=5)
    priority: int = Field(ge=1, le=5)
    exposure_estimate: int | None = None
    rationale: str
    evidence_ids: list[str]


class Action(BaseModel):
    type: str
    target: str
    detail: str
    evidence_ids: list[str]


class Comms(BaseModel):
    channel: str
    en: str
    hi: str
    needs_language_review: bool = True
    evidence_ids: list[str] = Field(default_factory=list)


class Plan(BaseModel):
    id: str
    incident_id: str
    actions: list[Action]
    comms: list[Comms] = Field(default_factory=list)
    status: str
    auditor_verdict: str | None = None
    auditor_flags: list[str] = Field(default_factory=list)
    revision: int = 0


class TraceStep(BaseModel):
    ts: datetime
    agent: str
    kind: str
    message: str
    refs: dict[str, Any] = Field(default_factory=dict)


class AuditEntry(BaseModel):
    id: str
    plan_id: str
    incident_id: str
    decision: str
    note: str | None = None
    actor: str = "human"
    decided_at: datetime


class DecisionRequest(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class ModeRequest(BaseModel):
    mode: str = Field(pattern="^(live|replay)$")
    scenario: str = "nepal_2015"
    speed: float = Field(default=30.0, ge=1, le=60)
