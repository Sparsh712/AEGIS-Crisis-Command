"use client";

import { useEffect, useMemo, useState } from "react";
import { connectToTrace } from "@/lib/sse";
import type { AgentName, TraceStep } from "@/lib/types";

const agentLabels: Record<string, string> = {
  sensor: "SENSOR",
  triage: "TRIAGE",
  logistics: "LOGISTICS",
  comms: "COMMS",
  auditor: "AUDITOR",
  human: "HUMAN",
  system: "SYSTEM",
};

const agentOrder: AgentName[] = ["sensor", "triage", "logistics", "comms", "auditor"];

function formatTime(timestamp: string) {
  return new Intl.DateTimeFormat("en", {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  }).format(new Date(timestamp));
}

function agentClass(agent: string) {
  return `agent-${agent.toLowerCase()}`;
}

export default function Home() {
  const [steps, setSteps] = useState<TraceStep[]>([]);
  const [status, setStatus] = useState<"connecting" | "connected" | "fallback" | "error">(
    "connecting",
  );

  useEffect(() => {
    const connection = connectToTrace(
      (step) => setSteps((current) => [...current.slice(-11), step]),
      setStatus,
    );
    return connection.close;
  }, []);

  const completedAgents = useMemo(
    () => new Set(steps.map((step) => step.agent.toLowerCase())),
    [steps],
  );

  return (
    <main className="shell">
      <header className="topbar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            A
          </div>
          <div>
            <p className="brand-name">AEGIS</p>
            <p className="brand-subtitle">CRISIS COMMAND CENTER</p>
          </div>
        </div>
        <div className="topbar-meta">
          <span className="level-tag">LEVEL 0 / FOUNDATIONS</span>
          <span className={`connection-state state-${status}`}>
            <span className="state-dot" aria-hidden="true" />
            {status === "connected" ? "SSE LINKED" : status === "fallback" ? "LOCAL REPLAY" : status}
          </span>
        </div>
      </header>

      <section className="command-strip" aria-label="Replay controls">
        <div className="strip-field">
          <span className="field-label">MODE</span>
          <strong>REPLAY</strong>
        </div>
        <div className="strip-divider" />
        <div className="strip-field scenario-field">
          <span className="field-label">SCENARIO</span>
          <strong>Nepal 2015 / Mainshock</strong>
          <span className="synthetic-badge">FIXTURE</span>
        </div>
        <div className="strip-divider" />
        <div className="strip-field">
          <span className="field-label">REPLAY CLOCK</span>
          <strong>00:00:12</strong>
        </div>
        <div className="strip-actions">
          <button type="button" className="ghost-button">
            1× SPEED
          </button>
          <button type="button" className="accent-button">
            START REPLAY
          </button>
        </div>
      </section>

      <div className="workspace">
        <aside className="panel incident-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-index">01 / QUEUE</span>
              <h1>Active incidents</h1>
            </div>
            <span className="count-badge">01</span>
          </div>

          <button type="button" className="incident-row selected-incident">
            <span className="incident-priority">P5</span>
            <span className="incident-copy">
              <strong>Nepal mainshock</strong>
              <span>Earthquake · 25 Apr 2015</span>
            </span>
            <span className="incident-status">ACTIVE</span>
          </button>

          <div className="incident-detail">
            <div className="detail-row">
              <span>MAGNITUDE</span>
              <strong>7.8 Mw</strong>
            </div>
            <div className="detail-row">
              <span>REGION</span>
              <strong>Gorkha, Nepal</strong>
            </div>
            <div className="detail-row">
              <span>PIPELINE</span>
              <strong>{steps.length ? `${Math.min(steps.length, 5)} / 5 agents` : "awaiting stream"}</strong>
            </div>
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
        </aside>

        <section className="panel canvas-panel" aria-label="Operational canvas">
          <div className="panel-heading canvas-heading">
            <div>
              <span className="panel-index">02 / OPERATIONS</span>
              <h1>Evidence path</h1>
            </div>
            <span className="live-indicator">
              <span className="live-pulse" aria-hidden="true" /> STREAMING
            </span>
          </div>

          <div className="canvas-grid">
            <div className="coordinate coordinate-top-left">27.7172° N / 85.3240° E</div>
            <div className="coordinate coordinate-bottom-right">REPLAY / OFFLINE-CAPABLE</div>
            <div className="crosshair crosshair-main" aria-hidden="true">
              <span />
              <span />
            </div>
            <div className="incident-orbit" aria-hidden="true">
              <span className="orbit-ring orbit-ring-large" />
              <span className="orbit-ring orbit-ring-small" />
              <span className="orbit-core" />
            </div>
            <div className="canvas-label label-event">
              <span className="label-kicker">EVENT / USGS FIXTURE</span>
              <strong>M7.8</strong>
              <span>GORKHA REGION</span>
            </div>
            <div className="route route-one" />
            <div className="route route-two" />
            <div className="facility facility-one">HOSPITAL / 01</div>
            <div className="facility facility-two">SHELTER / 02</div>
            <div className="canvas-legend">
              <span><i className="legend-dot legend-event" /> EVENT</span>
              <span><i className="legend-dot legend-facility" /> FACILITY</span>
              <span><i className="legend-line" /> ROUTE</span>
            </div>
          </div>

          <div className="canvas-footer">
            <span>NO LIVE DISPATCH</span>
            <span className="footer-separator">/</span>
            <span>HUMAN APPROVAL REQUIRED</span>
            <span className="footer-separator">/</span>
            <span>EVIDENCE IDS ENABLE AUDIT</span>
          </div>
        </section>

        <aside className="panel activity-panel">
          <div className="panel-heading">
            <div>
              <span className="panel-index">03 / TRACE BUS</span>
              <h1>Agent activity</h1>
            </div>
            <span className="count-badge">{String(steps.length).padStart(2, "0")}</span>
          </div>

          <div className="activity-feed" aria-live="polite">
            {steps.length === 0 ? (
              <div className="feed-empty">
                <span className="empty-scan" aria-hidden="true" />
                <p>Waiting for TraceStep events.</p>
                <small>The feed will hydrate from /api/stream.</small>
              </div>
            ) : (
              steps.map((step, index) => (
                <article className="activity-item" key={`${step.ts}-${index}`}>
                  <div className="activity-meta">
                    <span className={`agent-chip ${agentClass(step.agent)}`}>
                      {agentLabels[step.agent.toLowerCase()] ?? step.agent.toUpperCase()}
                    </span>
                    <time dateTime={step.ts}>{formatTime(step.ts)}</time>
                  </div>
                  <p>{step.message}</p>
                  <span className="activity-kind">{step.kind.replaceAll("_", " ")}</span>
                </article>
              ))
            )}
          </div>

          <div className="plan-preview">
            <div className="plan-preview-head">
              <span>PLAN STATUS</span>
              <strong>AWAITING APPROVAL</strong>
            </div>
            <p>Stage resources, attach bilingual drafts, then route to a human decision.</p>
            <button type="button" className="approval-button" disabled>
              APPROVAL UI / LEVEL 1
            </button>
          </div>
        </aside>
      </div>

      <footer className="honest-footer">
        <span>AEGIS / DECISION-SUPPORT PROTOTYPE</span>
        <span>It never sends real alerts or dispatches anything. Approved actions are written to an audit log.</span>
        <span>LEVEL 0 BUILD</span>
      </footer>
    </main>
  );
}
