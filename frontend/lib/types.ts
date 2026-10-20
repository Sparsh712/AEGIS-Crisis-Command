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
