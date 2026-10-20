export type AgentName =
  | "sensor"
  | "triage"
  | "logistics"
  | "comms"
  | "auditor"
  | "human"
  | "system";

export type TraceKind =
  | "observe"
  | "tool_call"
  | "reason"
  | "handoff"
  | "critique"
  | "decision"
  | "human";

export type TraceStep = {
  ts: string;
  agent: AgentName | string;
  kind: TraceKind | string;
  message: string;
  refs?: Record<string, unknown>;
};

export type Hazard = "earthquake" | "flood" | "cyclone" | "other" | string;

export type EventRecord = {
  id: string;
  source: string;
  hazard: Hazard;
  lat: number;
  lon: number;
  magnitude?: number | null;
  alert_level?: string | null;
  occurred_at: string;
  raw: Record<string, unknown>;
  synthetic: boolean;
};

export type Evidence = {
  id: string;
  tool: string;
  summary: string;
  data: Record<string, unknown>;
  fetched_at: string;
};

export type Facility = {
  id: string;
  name: string;
  type: string;
  lat: number;
  lon: number;
  capacity: number;
  capacity_estimated: boolean;
  distance_km?: number | null;
  evidence_ids: string[];
};

export type Incident = {
  id: string;
  event_ids: string[];
  hazard: Hazard;
  det_score: number;
  priority: number;
  exposure_estimate?: number | null;
  rationale: string;
  evidence_ids: string[];
};

export type Action = {
  type: string;
  target: string;
  detail: string;
  evidence_ids: string[];
};

export type Comms = {
  channel: string;
  en: string;
  hi: string;
  needs_language_review: boolean;
  evidence_ids: string[];
};

export type Plan = {
  id: string;
  incident_id: string;
  actions: Action[];
  comms: Comms[];
  status: string;
  auditor_verdict?: string | null;
  auditor_flags: string[];
  revision: number;
};

export type AuditEntry = {
  id: string;
  plan_id: string;
  incident_id: string;
  decision: string;
  note?: string | null;
  actor: string;
  decided_at: string;
};

export type AegisState = {
  events: EventRecord[];
  incidents: Incident[];
  plans: Plan[];
  facilities: Facility[];
  evidence: Evidence[];
  audit_log: AuditEntry[];
  mode?: RuntimeMode;
};

export type RuntimeMode = {
  mode: "live" | "replay";
  scenario: string;
  speed: number;
  running: boolean;
  clock?: string | null;
};
