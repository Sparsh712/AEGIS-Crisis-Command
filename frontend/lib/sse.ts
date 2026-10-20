import type { TraceStep } from "./types";

const fallbackSteps: TraceStep[] = [
  {
    ts: "2026-04-25T06:11:04.000Z",
    agent: "sensor",
    kind: "observe",
    message: "Replay clock opened Nepal 2015 fixture window.",
    refs: { event_id: "synthetic:nepal-2015-mainshock" },
  },
  {
    ts: "2026-04-25T06:11:06.000Z",
    agent: "triage",
    kind: "reason",
    message: "Mainshock normalised as earthquake; priority score set to 5.",
    refs: { incident_id: "inc-nepal-2015", evidence_ids: ["e1"] },
  },
  {
    ts: "2026-04-25T06:11:08.000Z",
    agent: "logistics",
    kind: "tool_call",
    message: "Facility lookup staged for the incident region.",
    refs: { incident_id: "inc-nepal-2015", evidence_ids: ["e2"] },
  },
  {
    ts: "2026-04-25T06:11:10.000Z",
    agent: "comms",
    kind: "handoff",
    message: "English and Hindi drafts attached for human review.",
    refs: { incident_id: "inc-nepal-2015", plan_id: "plan-nepal-2015" },
  },
  {
    ts: "2026-04-25T06:11:12.000Z",
    agent: "auditor",
    kind: "critique",
    message: "Evidence references present; plan is awaiting approval.",
    refs: { plan_id: "plan-nepal-2015" },
  },
];

export type SseConnection = {
  close: () => void;
};

export function connectToTrace(
  onStep: (step: TraceStep) => void,
  onStatus: (status: "connecting" | "connected" | "fallback" | "error") => void,
): SseConnection {
  const apiBase = process.env.NEXT_PUBLIC_API_BASE ?? "";
  const url = `${apiBase.replace(/\/$/, "")}/api/stream`;
  let source: EventSource | undefined;
  let fallbackTimer: ReturnType<typeof setInterval> | undefined;
  let fallbackIndex = 0;
  let settled = false;

  const startFallback = () => {
    if (settled) return;
    settled = true;
    source?.close();
    onStatus("fallback");
    fallbackTimer = setInterval(() => {
      const step = fallbackSteps[fallbackIndex % fallbackSteps.length];
      fallbackIndex += 1;
      onStep({ ...step, ts: new Date().toISOString() });
    }, 2200);
  };

  onStatus("connecting");

  if (typeof window === "undefined" || typeof EventSource === "undefined") {
    startFallback();
  } else {
    source = new EventSource(url);
    source.onopen = () => {
      settled = true;
      onStatus("connected");
    };
    source.addEventListener("trace", (event) => {
      settled = true;
      onStatus("connected");
      try {
        onStep(JSON.parse((event as MessageEvent).data) as TraceStep);
      } catch {
        onStatus("error");
      }
    });
    source.onerror = () => {
      if (settled) {
        onStatus("error");
      } else {
        startFallback();
      }
    };
  }

  return {
    close: () => {
      source?.close();
      if (fallbackTimer) clearInterval(fallbackTimer);
    },
  };
}
