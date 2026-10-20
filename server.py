"""Level 0 FastAPI host for the exported AEGIS frontend and trace demo stream."""

import asyncio
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles


ROOT = Path(__file__).resolve().parent
FRONTEND_OUT = ROOT / "frontend" / "out"

app = FastAPI(title="AEGIS Level 0")
frontend_origins = [
    origin.strip()
    for origin in os.getenv("FRONTEND_ORIGIN", "http://localhost:3000").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins or ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


TRACE_STEPS = [
    ("sensor", "observe", "Replay clock opened Nepal 2015 fixture window."),
    ("triage", "reason", "Mainshock normalised as earthquake; priority score set to 5."),
    ("logistics", "tool_call", "Facility lookup staged for the incident region."),
    ("comms", "handoff", "English and Hindi drafts attached for human review."),
    ("auditor", "critique", "Evidence references present; plan is awaiting approval."),
]


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "service": "aegis-level-0"}


async def trace_events():
    index = 0
    while True:
        agent, kind, message = TRACE_STEPS[index % len(TRACE_STEPS)]
        payload = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "kind": kind,
            "message": message,
            "refs": {"incident_id": "inc-nepal-2015", "plan_id": "plan-nepal-2015"},
        }
        yield f"event: trace\ndata: {json.dumps(payload)}\n\n"
        index += 1
        await asyncio.sleep(2)


@app.get("/api/stream")
async def stream():
    return StreamingResponse(
        trace_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if FRONTEND_OUT.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_OUT, html=True), name="frontend")
else:

    @app.get("/")
    async def missing_export():
        return FileResponse(ROOT / "README.md")
