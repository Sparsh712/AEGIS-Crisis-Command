import type { AegisState, Plan, RuntimeMode } from "./types";

const apiBase = (process.env.NEXT_PUBLIC_API_BASE ?? "").replace(/\/$/, "");

export class ApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${apiBase}${path}`, {
      ...init,
      headers: {
        Accept: "application/json",
        ...(init?.body ? { "Content-Type": "application/json" } : {}),
        ...init?.headers,
      },
      cache: "no-store",
    });
  } catch {
    throw new ApiError("API unavailable. Check the backend connection and try again.", 0);
  }

  if (!response.ok) {
    let message = `Request failed (${response.status}).`;
    try {
      const payload = (await response.json()) as { detail?: string };
      if (payload.detail) message = payload.detail;
    } catch {
      // Keep the status-based message when the server did not return JSON.
    }
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as T;
}

export function getState(): Promise<AegisState> {
  return requestJson<AegisState>("/api/state");
}

export function injectSample(): Promise<Plan> {
  return requestJson<Plan>("/api/dev/inject-sample", { method: "POST" });
}

export function decidePlan(
  planId: string,
  decision: "approve" | "reject",
  note: string,
): Promise<Plan> {
  return requestJson<Plan>(`/api/plans/${encodeURIComponent(planId)}/${decision}`, {
    method: "POST",
    body: JSON.stringify({ note: note.trim() || null }),
  });
}

export function setMode(
  mode: "live" | "replay",
  scenario = "nepal_2015",
  speed = 30,
): Promise<RuntimeMode> {
  return requestJson<RuntimeMode>("/api/mode", {
    method: "POST",
    body: JSON.stringify({ mode, scenario, speed }),
  });
}

export function stopReplay(): Promise<RuntimeMode> {
  return requestJson<RuntimeMode>("/api/replay/stop", { method: "POST" });
}
