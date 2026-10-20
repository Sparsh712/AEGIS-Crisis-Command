"""FastAPI entry point for the AEGIS Level 0 backend."""

import asyncio
from contextlib import asynccontextmanager
from datetime import datetime, timezone
import json
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from .bus import publish, subscribe
from .config import settings
from .models import TraceStep


async def _fake_trace_ticker() -> None:
    tick = 0
    while True:
        await asyncio.sleep(settings.trace_interval_seconds)
        tick += 1
        await publish(
            TraceStep(
                ts=datetime.now(timezone.utc),
                agent="system",
                kind="observe",
                message=f"Level 0 fake trace tick {tick}",
                refs={"tick": tick},
            )
        )


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    ticker = asyncio.create_task(_fake_trace_ticker(), name="aegis-fake-trace-ticker")
    try:
        yield
    finally:
        ticker.cancel()
        await asyncio.gather(ticker, return_exceptions=True)


app = FastAPI(title="AEGIS Backend", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict[str, object]:
    return {
        "status": "ok",
        "service": "aegis-backend",
        "fake_llm": settings.fake_llm,
    }


async def _stream_trace(request: Request) -> AsyncIterator[dict[str, str]]:
    async with subscribe() as queue:
        while not await request.is_disconnected():
            try:
                step = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            yield {
                "event": "trace",
                "data": json.dumps(step.model_dump(mode="json")),
            }


@app.get("/api/stream")
async def stream(request: Request) -> EventSourceResponse:
    return EventSourceResponse(
        _stream_trace(request),
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
