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


class Incident(BaseModel):
    id: str
    event_ids: list[str]
    hazard: Hazard
    det_score: int
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
