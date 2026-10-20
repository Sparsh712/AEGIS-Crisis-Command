"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { decidePlan, getState, injectSample, setMode, stopReplay } from "@/lib/api";
import MapView from "@/components/MapView";
import { connectToTrace } from "@/lib/sse";
import type {
  AegisState,
  EventRecord,
  Incident,
  Plan,
  TraceStep,
} from "@/lib/types";

const emptyState: AegisState = {
  events: [],
  incidents: [],
  plans: [],
  facilities: [],
  evidence: [],
  audit_log: [],
};

const agentLabels: Record<string, string> = {
  sensor: "SENSOR",
  triage: "TRIAGE",
  logistics: "LOGISTICS",
  comms: "COMMS",
  auditor: "AUDITOR",
  human: "HUMAN",
  system: "SYSTEM",
};

const agentOrder = ["sensor", "triage", "logistics", "comms", "auditor"];
const commsChannels = ["sms", "social", "bulletin"];

function formatTime(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "--:--:--";
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(date);
}

function formatDate(timestamp: string) {
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "Unknown time";
  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(date);
}

function formatReplayClock(timestamp?: string | null) {
  if (!timestamp) return "CLOCK STANDBY";
  const date = new Date(timestamp);
  if (Number.isNaN(date.valueOf())) return "CLOCK UNKNOWN";
  return `${new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
    timeZone: "UTC",
  }).format(date).toUpperCase()} UTC`;
}

function scenarioLabel(name?: string) {
  if (name === "compound_synthetic") return "COMPOUND DISASTER";
  if (name === "nepal_2015") return "NEPAL 2015";
  return name?.replaceAll("_", " ").toUpperCase() ?? "REPLAY SCENARIO";
}

function auditDecisionLabel(decision: string) {
  return decision.replaceAll("_", " ").toUpperCase();
}

function agentClass(agent: string) {
  return `agent-${agent.toLowerCase()}`;
}

function hazardLabel(hazard: string) {
  return hazard.replaceAll("_", " ").toUpperCase();
}

function planForIncident(incident: Incident, plans: Plan[]) {
  return plans.find((plan) => plan.incident_id === incident.id);
}

function incidentStatus(incident: Incident, plans: Plan[]) {
  const status = planForIncident(incident, plans)?.status;
  if (!status) return "QUEUED";
  return status.replaceAll("_", " ").toUpperCase();
}

function eventForIncident(incident: Incident, events: EventRecord[]) {
  return events.find((event) => incident.event_ids.includes(event.id));
}

function readableActionType(type: string) {
  return type.replaceAll("_", " ");
}

function uniqueIds(ids: string[]) {
  return [...new Set(ids)];
}

function ErrorState({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="state-card state-error-card">
      <span className="state-symbol">!</span>
      <strong>CONNECTION FAULT</strong>
      <p>{message}</p>
      <button type="button" className="ghost-button" onClick={onRetry}>
        RETRY STATE LOAD
      </button>
    </div>
  );
}

function EmptyState({ message, detail }: { message: string; detail: string }) {
  return (
    <div className="state-card">
      <span className="state-symbol state-symbol-muted">+</span>
      <strong>{message}</strong>
      <p>{detail}</p>
    </div>
  );
}

function EvidenceChip({ id, onOpen }: { id: string; onOpen: (id: string) => void }) {
  return (
    <button type="button" className="evidence-chip" onClick={() => onOpen(id)} aria-label={`Open evidence ${id}`}>
      {id}
    </button>
  );
}

export default function Home() {
  const [data, setData] = useState<AegisState | null>(null);
  const [selectedIncidentId, setSelectedIncidentId] = useState<string | null>(null);
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [connectionStatus, setConnectionStatus] = useState<
    "connecting" | "connected" | "fallback" | "error"
  >("connecting");
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [activityTab, setActivityTab] = useState<"activity" | "plan">("activity");
  const [note, setNote] = useState("");
  const [actionError, setActionError] = useState<string | null>(null);
  const [mutating, setMutating] = useState<"inject" | "approve" | "reject" | null>(null);
  const [selectedEvidenceId, setSelectedEvidenceId] = useState<string | null>(null);
  const [commsChannel, setCommsChannel] = useState("sms");
  const [commsLanguage, setCommsLanguage] = useState<"en" | "hi">("en");
  const [scenario, setScenario] = useState("nepal_2015");
  const [speed, setSpeed] = useState(30);

  const loadState = useCallback(async (initial = false) => {
    if (initial) setLoading(true);
    else setRefreshing(true);
    setError(null);
    try {
      setData(await getState());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to load AEGIS state.");
    } finally {
      if (initial) setLoading(false);
      else setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void loadState(true);
    const connection = connectToTrace(
      (step) => {
        setSteps((current) => [...current.filter((item) => item.ts !== step.ts || item.message !== step.message), step].slice(-40));
        if (step.agent === "human") void loadState(false);
      },
      setConnectionStatus,
    );
    return connection.close;
  }, [loadState]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      void getState().then(setData).catch(() => undefined);
    }, 1000);
    return () => window.clearInterval(timer);
  }, []);

  const incidents = useMemo(
    () => [...(data?.incidents ?? [])].sort((left, right) => right.priority - left.priority),
    [data?.incidents],
  );

  useEffect(() => {
    if (!selectedIncidentId || !incidents.some((incident) => incident.id === selectedIncidentId)) {
      setSelectedIncidentId(incidents[0]?.id ?? null);
    }
  }, [incidents, selectedIncidentId]);

  const safeData = data ?? emptyState;
  const selectedIncident = incidents.find((incident) => incident.id === selectedIncidentId);
  const selectedPlan = selectedIncident ? planForIncident(selectedIncident, safeData.plans) : undefined;
  const selectedEvent = selectedIncident ? eventForIncident(selectedIncident, safeData.events) : undefined;
  const selectedEvidence = safeData.evidence.find((item) => item.id === selectedEvidenceId);
  const selectedAudit = selectedPlan
    ? safeData.audit_log.find((entry) => entry.plan_id === selectedPlan.id)
    : undefined;
  const auditEntries = [...safeData.audit_log].reverse();
  const completedAgents = useMemo(
    () => new Set(steps.flatMap((step) => [step.agent.toLowerCase()])),
    [steps],
  );
  const selectedComms = selectedPlan?.comms.find((item) => item.channel === commsChannel) ?? selectedPlan?.comms[0];
  const displayedComms = selectedComms?.[commsLanguage] ?? "No communication draft is attached.";
  const canDecide = selectedPlan?.status === "awaiting_approval";
  const busy = mutating !== null;
  const runtimeMode = safeData.mode;
  const replayStatus = runtimeMode?.running ? "RUNNING" : "STOPPED";

  async function handleInject() {
    setMutating("inject");
    setActionError(null);
    setNotice(null);
    try {
      await injectSample();
      await loadState(false);
      setNotice("Sample event injected. Plan state refreshed from the backend.");
      setActivityTab("plan");
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Sample injection failed.");
    } finally {
      setMutating(null);
    }
  }

  async function handleReplay(nextScenario: string) {
    setMutating("inject");
    setActionError(null);
    setScenario(nextScenario);
    try {
      await setMode("replay", nextScenario, speed);
      await loadState(false);
      setNotice(`${nextScenario === "compound_synthetic" ? "Synthetic compound" : "Nepal 2015"} replay started.`);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Replay could not start.");
    } finally {
      setMutating(null);
    }
  }

  async function handleDecision(decision: "approve" | "reject") {
    if (!selectedPlan) return;
    if (decision === "reject" && !note.trim()) {
      setActionError("A short note is required when rejecting a plan.");
      return;
    }
    setMutating(decision);
    setActionError(null);
    setNotice(null);
    try {
      await decidePlan(selectedPlan.id, decision, note);
      await loadState(false);
      setNote("");
      setNotice(`Plan ${decision === "approve" ? "approved" : "rejected"}. Audit log updated.`);
    } catch (caught) {
      setActionError(caught instanceof Error ? caught.message : "Decision could not be recorded.");
    } finally {
      setMutating(null);
    }
  }

  useEffect(() => {
    function handleKeyboardShortcut(event: KeyboardEvent) {
      const target = event.target as HTMLElement | null;
      if (
        target?.isContentEditable ||
        target?.tagName === "INPUT" ||
        target?.tagName === "TEXTAREA" ||
        target?.tagName === "SELECT"
      ) {
        return;
      }

      if (event.key === "Escape" && selectedEvidenceId) {
        event.preventDefault();
        setSelectedEvidenceId(null);
      } else if (event.key === "1") {
        setActivityTab("activity");
      } else if (event.key === "2") {
        setActivityTab("plan");
      } else if (event.key.toLowerCase() === "r" && !busy) {
        event.preventDefault();
        void handleReplay(scenario);
      } else if (event.key.toLowerCase() === "s" && !busy) {
        event.preventDefault();
        void stopReplay().then(() => getState().then(setData).catch(() => undefined));
      } else if (event.key.toLowerCase() === "a" && canDecide && !busy) {
        event.preventDefault();
        void handleDecision("approve");
      }
    }

    window.addEventListener("keydown", handleKeyboardShortcut);
    return () => window.removeEventListener("keydown", handleKeyboardShortcut);
  }, [busy, canDecide, handleDecision, handleReplay, scenario, selectedEvidenceId]);

  const statusText =
    connectionStatus === "connected"
      ? "SSE LINKED"
      : connectionStatus === "fallback"
        ? "LOCAL REPLAY"
        : connectionStatus === "error"
          ? "SSE ERROR"
          : "CONNECTING";

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">A</div>
          <div>
            <p className="brand-name">AEGIS</p>
            <p className="brand-subtitle">CRISIS COMMAND CENTER</p>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="level-tag">LEVEL 1 / HUMAN CONTROL</span>
           <span className={`connection-state state-${connectionStatus}`}>
            <span className="state-dot" aria-hidden="true" />
            {statusText}
          </span>
        </div>
      </header>

      <details className="demo-guide" open>
        <summary>
          <span><span className="field-label">DEMO / 02:00</span> Run the evidence-to-approval story</span>
          <span className="guide-shortcuts"><kbd>R</kbd> replay <kbd>A</kbd> approve <kbd>1</kbd>/<kbd>2</kbd> views</span>
        </summary>
        <ol className="demo-steps">
          <li><time>00:00–00:40</time><span>Start <strong>NEPAL 2015</strong> at <strong>30×</strong>. Watch Sensor and Triage populate the queue, map, priority, and evidence chips.</span></li>
          <li><time>00:40–01:00</time><span>Open <strong>PLAN</strong>. Click an evidence chip to show the source summary and raw JSON behind a proposed action.</span></li>
          <li><time>01:00–01:25</time><span>Start <strong>COMPOUND DISASTER</strong>. Point out the <strong>SYNTHETIC</strong> badge, facility contention, Auditor flags, and bounded revision.</span></li>
          <li><time>01:25–01:45</time><span>Switch the comms draft between <strong>EN</strong> and <strong>HI</strong>, note the language-review flag, then approve the plan.</span></li>
          <li><time>01:45–02:00</time><span>Close on the visible audit entry: evidence-grounded, audited, human-controlled, and offline from recorded data.</span></li>
        </ol>
      </details>

      <section className="command-strip" aria-label="Command controls">
        <div className="strip-field">
          <span className="field-label">MODE</span>
          <strong>{runtimeMode?.mode?.toUpperCase() ?? "REPLAY"}</strong>
          <span className={`replay-status replay-${runtimeMode?.running ? "running" : "stopped"}`}>{replayStatus}</span>
        </div>
        <div className="strip-divider" />
        <div className="strip-field replay-clock-field">
          <span className="field-label">REPLAY CLOCK</span>
          <strong>{formatReplayClock(runtimeMode?.clock)}</strong>
        </div>
        <div className="strip-divider" />
        <div className="strip-field scenario-field">
          <span className="field-label">SCENARIO</span>
          <strong>{scenarioLabel(runtimeMode?.scenario ?? scenario)}</strong>
          {(runtimeMode?.scenario === "compound_synthetic" || selectedEvent?.synthetic) && <span className="synthetic-badge">SYNTHETIC</span>}
        </div>
        <div className="strip-divider" />
        <div className="strip-field">
          <span className="field-label">QUEUE</span>
          <strong>{String(incidents.length).padStart(2, "0")} INCIDENTS</strong>
        </div>
         <div className="strip-actions replay-actions">
            <label className="speed-control"><span className="field-label">SPEED</span><select aria-label="Replay speed" value={speed} onChange={(event) => setSpeed(Number(event.target.value))}><option value={1}>1×</option><option value={10}>10×</option><option value={30}>30×</option><option value={60}>60×</option></select></label>
            <button type="button" className={`ghost-button ${scenario === "nepal_2015" ? "selected-control" : ""}`} onClick={() => void handleReplay("nepal_2015")} disabled={busy} aria-label="Start Nepal 2015 replay">NEPAL 2015</button>
            <button type="button" className={`ghost-button ${scenario === "compound_synthetic" ? "selected-control" : ""}`} onClick={() => void handleReplay("compound_synthetic")} disabled={busy} aria-label="Start synthetic compound replay">SYNTHETIC</button>
            <button type="button" className="ghost-button" onClick={() => void stopReplay().then(() => loadState(false))} disabled={busy} aria-keyshortcuts="S" aria-label="Stop replay">STOP</button>
            <button type="button" className="ghost-button" onClick={() => void loadState(false)} disabled={refreshing || busy} aria-label="Refresh AEGIS state">
            {refreshing ? "REFRESHING" : "REFRESH STATE"}
          </button>
           <button type="button" className="accent-button" onClick={() => void handleInject()} disabled={busy} aria-label="Inject sample event">
            {mutating === "inject" ? "INJECTING…" : "INJECT SAMPLE"}
          </button>
        </div>
      </section>

      {notice && <div className="toast toast-success" role="status">{notice}</div>}
      {error && data && <div className="toast toast-error" role="alert">State refresh failed: {error}</div>}
      {actionError && <div className="toast toast-error" role="alert">{actionError}</div>}

      <div className="workspace">
        <aside className="panel incident-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-index">01 / QUEUE</span>
              <h1>Active incidents</h1>
            </div>
            <span className="count-badge">{String(incidents.length).padStart(2, "0")}</span>
          </div>

          {loading ? (
            <div className="queue-skeleton" aria-label="Loading incidents">
              <span /><span /><span />
            </div>
          ) : error && !data ? (
            <ErrorState message={error} onRetry={() => void loadState(true)} />
          ) : incidents.length === 0 ? (
            <EmptyState message="QUEUE CLEAR" detail="Inject a sample event to start the reviewed response flow." />
          ) : (
            incidents.map((incident) => {
              const event = eventForIncident(incident, safeData.events);
              const isSelected = incident.id === selectedIncidentId;
              return (
                <button
                  type="button"
                  className={`incident-row ${isSelected ? "selected-incident" : ""}`}
                  key={incident.id}
                  onClick={() => {
                    setSelectedIncidentId(incident.id);
                    setActivityTab("plan");
                    setActionError(null);
                  }}
                >
                  <span className="hazard-icon" aria-hidden="true">{incident.hazard === "earthquake" ? "⌁" : "◇"}</span>
                  <span className="incident-copy">
                    <strong>{event?.raw.region as string | undefined ?? incident.id}</strong>
                    <span>{hazardLabel(incident.hazard)} · {event?.magnitude ? `M${event.magnitude}` : "magnitude n/a"}</span>
                  </span>
                  <span className={`priority-chip priority-${incident.priority}`}>P{incident.priority}</span>
                  <span className="incident-status">{incidentStatus(incident, safeData.plans)}</span>
                </button>
              );
            })
          )}

          {selectedIncident && (
            <>
              <div className="incident-detail">
                <div className="detail-row"><span>DETECTION SCORE</span><strong>{selectedIncident.det_score} / 5</strong></div>
                <div className="detail-row"><span>EXPOSURE</span><strong>{selectedIncident.exposure_estimate ?? "—"}</strong></div>
                <div className="detail-row"><span>PIPELINE</span><strong>{steps.length ? `${Math.min(completedAgents.size, 5)} / 5 agents` : "awaiting stream"}</strong></div>
              </div>
              <div className="pipeline-list" aria-label="Agent pipeline">
                {agentOrder.map((agent, index) => (
                  <div className="pipeline-step" key={agent}>
                    <span className={`pipeline-node ${completedAgents.has(agent) ? "node-complete" : ""}`}>
                      {completedAgents.has(agent) ? "✓" : `0${index + 1}`}
                    </span>
                    <span>{agentLabels[agent]}</span>
                    <span className="pipeline-line" />
                    <span className="pipeline-state">{completedAgents.has(agent) ? "DONE" : "WAIT"}</span>
                  </div>
                ))}
              </div>
            </>
          )}
        </aside>

        <section className="panel canvas-panel" aria-label="Operational canvas">
          <div className="panel-heading canvas-heading">
            <div>
              <span className="panel-index">02 / OPERATIONS</span>
              <h1>{selectedIncident ? "Incident overview" : "Operational canvas"}</h1>
            </div>
            <span className="live-indicator"><span className="live-pulse" aria-hidden="true" /> LIVE ACTIVITY</span>
          </div>

          {loading ? (
            <div className="canvas-loading"><span className="loading-orbit" /><p>Hydrating command state…</p></div>
          ) : (
            <>
              {selectedIncident && <div className="overview-strip">
                <div><span>INCIDENT</span><strong>{selectedIncident.id}</strong></div>
                <div><span>HAZARD</span><strong>{hazardLabel(selectedIncident.hazard)}</strong></div>
                <div><span>PRIORITY</span><strong className="accent-text">P{selectedIncident.priority}</strong></div>
                <div><span>PLAN</span><strong>{selectedPlan?.status.replaceAll("_", " ").toUpperCase() ?? "NOT GENERATED"}</strong></div>
              </div>}
               <div className="map-frame"><MapView events={safeData.events} incidents={safeData.incidents} facilities={safeData.facilities} selectedEvent={selectedEvent} selectedPlan={selectedPlan} /><div className="map-overlay map-overlay-top">{selectedEvent ? `${selectedEvent.lat.toFixed(4)}° N / ${selectedEvent.lon.toFixed(4)}° E` : "COORDINATES PENDING"}</div><div className="map-overlay map-overlay-bottom">OFFLINE VECTOR / EVIDENCE-GROUNDED / HUMAN GATE</div><div className="map-legend"><span><i className="legend-dot legend-event" /> EVENT</span><span><i className="legend-dot legend-facility" /> FACILITY</span><span><i className="legend-line" /> ROUTE</span></div></div>
               <div className="rationale-block"><span className="field-label">{selectedIncident ? "TRIAGE RATIONALE" : "MAP STATUS"}</span><p>{selectedIncident?.rationale ?? "Offline vector canvas ready. Start a replay to populate event, facility, and route evidence."}</p></div>
            </>
          )}
        </section>

        <aside className="panel detail-panel">
          <div className="panel-heading detail-heading">
            <div><span className="panel-index">03 / DECISION BUS</span><h1>{activityTab === "activity" ? "Agent activity" : "Selected plan"}</h1></div>
            <span className="count-badge">{activityTab === "activity" ? String(steps.length).padStart(2, "0") : selectedPlan ? "01" : "00"}</span>
          </div>
          <div className="tab-bar" role="tablist" aria-label="Decision bus views">
             <button type="button" role="tab" aria-selected={activityTab === "activity"} className={activityTab === "activity" ? "tab-active" : ""} onClick={() => setActivityTab("activity")} aria-keyshortcuts="1">ACTIVITY</button>
             <button type="button" role="tab" aria-selected={activityTab === "plan"} className={activityTab === "plan" ? "tab-active" : ""} onClick={() => setActivityTab("plan")} aria-keyshortcuts="2">PLAN {selectedPlan ? "· READY" : ""}</button>
          </div>

          {activityTab === "activity" ? (
            <div className="activity-feed" aria-live="polite">
              {steps.length === 0 ? (
                <div className="feed-empty"><span className="empty-scan" aria-hidden="true" /><p>Waiting for TraceStep events.</p><small>Live updates arrive from /api/stream.</small></div>
              ) : steps.map((step, index) => (
                <article className="activity-item" key={`${step.ts}-${step.message}-${index}`}>
                  <div className="activity-meta"><span className={`agent-chip ${agentClass(step.agent)}`}>{agentLabels[step.agent.toLowerCase()] ?? step.agent.toUpperCase()}</span><time dateTime={step.ts}>{formatTime(step.ts)}</time></div>
                  <p>{step.message}</p>
                  <div className="activity-foot"><span className="activity-kind">{step.kind.replaceAll("_", " ")}</span>{Array.isArray(step.refs?.evidence_ids) && <span className="activity-ref">{step.refs.evidence_ids.length} EVIDENCE IDS</span>}</div>
                </article>
              ))}
            </div>
          ) : (
            <div className="plan-panel">
              {!selectedPlan ? (
                <EmptyState message="NO PLAN SELECTED" detail="Run the sample flow or select an incident with a generated plan." />
              ) : (
                <>
                  <div className="plan-status-row"><span className={`verdict-badge verdict-${selectedPlan.auditor_verdict ?? "pending"}`}>{(selectedPlan.auditor_verdict ?? "pending").toUpperCase()}</span><span className="plan-revision">REV {selectedPlan.revision}</span></div>
                  <section className="plan-section"><div className="section-label"><span>ACTIONS</span><strong>{selectedPlan.actions.length}</strong></div>
                    <div className="action-list">{selectedPlan.actions.map((action) => <article className="action-item" key={`${action.type}-${action.target}`}><div className="action-title"><strong>{readableActionType(action.type)}</strong><span>{action.target}</span></div><p>{action.detail}</p><div className="evidence-row"><span className="micro-label">EVIDENCE</span>{uniqueIds(action.evidence_ids).length ? uniqueIds(action.evidence_ids).map((id) => <EvidenceChip key={id} id={id} onOpen={setSelectedEvidenceId} />) : <span className="no-evidence">none cited</span>}</div></article>)}</div>
                  </section>
                  <section className="plan-section"><div className="section-label"><span>COMMS DRAFTS</span><strong>{selectedPlan.comms.length}</strong></div>
                    {selectedPlan.comms.length > 0 && <><div className="comms-controls"><div className="subtabs">{commsChannels.filter((channel) => selectedPlan.comms.some((item) => item.channel === channel)).map((channel) => <button type="button" className={commsChannel === channel ? "subtab-active" : ""} key={channel} onClick={() => setCommsChannel(channel)}>{channel.toUpperCase()}</button>)}</div><div className="language-toggle"><button type="button" className={commsLanguage === "en" ? "language-active" : ""} onClick={() => setCommsLanguage("en")}>EN</button><button type="button" className={commsLanguage === "hi" ? "language-active" : ""} onClick={() => setCommsLanguage("hi")}>HI</button></div></div><div className="comms-copy"><p lang={commsLanguage}>{displayedComms}</p><div className="comms-meta"><span>{displayedComms.length} / 160 CHARS</span>{selectedComms?.needs_language_review && <span className="review-notice">LANGUAGE REVIEW</span>}</div></div><div className="evidence-row comms-evidence"><span className="micro-label">CITES</span>{uniqueIds(selectedComms?.evidence_ids ?? []).map((id) => <EvidenceChip key={id} id={id} onOpen={setSelectedEvidenceId} />)}</div></>}
                  </section>
                  <section className="plan-section auditor-section"><div className="section-label"><span>AUDITOR</span><strong>{selectedPlan.auditor_flags.length} FLAGS</strong></div><p className="auditor-verdict">{selectedPlan.auditor_verdict === "pass" ? "Evidence, numeric claims, and resource assignments passed review." : "Review required before human decision."}</p>{selectedPlan.auditor_flags.length > 0 && <ul className="flag-list">{selectedPlan.auditor_flags.map((flag) => <li key={flag}>{flag}</li>)}</ul>}</section>
                   <section className="decision-section"><div className="section-label"><span>HUMAN DECISION</span><strong>{selectedPlan.status.replaceAll("_", " ").toUpperCase()}</strong></div><label className="sr-only" htmlFor="decision-note">Decision note</label><textarea id="decision-note" value={note} onChange={(event) => setNote(event.target.value)} maxLength={2000} placeholder="Optional approval note; required for rejection." disabled={busy || !canDecide} /><div className="decision-actions"><button type="button" className="reject-button" disabled={busy || !canDecide} onClick={() => void handleDecision("reject")}>{mutating === "reject" ? "REJECTING…" : "REJECT"}</button><button type="button" className="approve-button" disabled={busy || !canDecide} onClick={() => void handleDecision("approve")} aria-keyshortcuts="A">{mutating === "approve" ? "APPROVING…" : "APPROVE PLAN"}</button></div>{selectedAudit && <div className="audit-result"><span>RECORDED BY {selectedAudit.actor.toUpperCase()} · {formatDate(selectedAudit.decided_at)}</span>{selectedAudit.note && <p>“{selectedAudit.note}”</p>}</div>}</section>
                 </>
               )}
             </div>
           )}

          <section className="audit-log-panel" aria-labelledby="audit-log-heading">
            <div className="section-label"><span id="audit-log-heading">AUDIT LOG</span><strong>{String(auditEntries.length).padStart(2, "0")} DECISIONS</strong></div>
            {auditEntries.length === 0 ? (
              <p className="audit-empty">No human decision recorded yet. Approve or reject an awaiting plan to create the first entry.</p>
            ) : (
              <div className="audit-log-list">
                {auditEntries.map((entry) => (
                  <article className="audit-log-entry" key={entry.id}>
                    <div className="audit-log-meta"><span className={`audit-decision audit-${entry.decision}`}>{auditDecisionLabel(entry.decision)}</span><time dateTime={entry.decided_at}>{formatDate(entry.decided_at)}</time></div>
                    <strong>{entry.actor.toUpperCase()} · {entry.plan_id}</strong>
                    {entry.note && <p>{entry.note}</p>}
                  </article>
                ))}
              </div>
            )}
          </section>
           </aside>
      </div>

      {selectedEvidence && <div className="drawer-backdrop" role="presentation" onClick={() => setSelectedEvidenceId(null)}><aside className="evidence-drawer" role="dialog" aria-modal="true" aria-label={`Evidence ${selectedEvidence.id}`} onClick={(event) => event.stopPropagation()}><div className="drawer-heading"><div><span className="panel-index">EVIDENCE RECORD</span><h2>{selectedEvidence.id}</h2></div><button type="button" className="close-button" onClick={() => setSelectedEvidenceId(null)} aria-label="Close evidence drawer">×</button></div><div className="drawer-meta"><span>{selectedEvidence.tool}</span><time>{formatDate(selectedEvidence.fetched_at)}</time></div><p className="evidence-summary">{selectedEvidence.summary}</p><pre>{JSON.stringify(selectedEvidence.data, null, 2)}</pre></aside></div>}

      <footer className="honest-footer"><span>AEGIS / DECISION-SUPPORT PROTOTYPE</span><span>Offline recorded fixtures only. It never sends real alerts or dispatches anything; approved actions are audit records. Hindi drafts need human language review.</span><span>REPLAY-FIRST BUILD</span></footer>
    </main>
  );
}
