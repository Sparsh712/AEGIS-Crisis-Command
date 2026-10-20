"""Meaningful offline checks for the AEGIS Level 0 foundation."""

import asyncio
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from pydantic import BaseModel
import pytest

from backend.app.bus import TraceBus, publish, subscribe, trace_bus
from backend.app.config import get_settings
from backend.app.llm import complete_json
from backend.app.main import app
from backend.app.models import Event, Hazard, TraceStep


def test_contracts_validate_expected_event_and_trace_step() -> None:
    event = Event(
        id="synthetic:level0",
        source="synthetic",
        hazard=Hazard.earthquake,
        lat=27.7,
        lon=85.3,
        occurred_at=datetime.now(timezone.utc),
        synthetic=True,
    )
    step = TraceStep(
        ts=datetime.now(timezone.utc),
        agent="sensor",
        kind="observe",
        message="Event observed",
        refs={"event_id": event.id},
    )

    assert event.hazard is Hazard.earthquake
    assert step.refs["event_id"] == event.id


def test_trace_bus_fans_out_and_unsubscribes() -> None:
    async def scenario() -> None:
        bus = TraceBus()
        step = TraceStep(
            ts=datetime.now(timezone.utc),
            agent="system",
            kind="observe",
            message="test",
        )
        async with bus.subscribe() as first, bus.subscribe() as second:
            await bus.publish(step)
            assert await first.get() == step
            assert await second.get() == step
            assert bus.subscriber_count == 2
        assert bus.subscriber_count == 0

    asyncio.run(scenario())


def test_fake_llm_returns_validated_pydantic_output() -> None:
    class Answer(BaseModel):
        answer: str
        priority: int

    get_settings.cache_clear()
    result = asyncio.run(complete_json("system", "user", Answer))

    assert isinstance(result, Answer)
    assert result.answer == "FAKE_LLM response"
    assert result.priority == 3


def test_health_cors_and_sse_fake_trace() -> None:
    from backend.app import main

    original_interval = main.settings.trace_interval_seconds
    main.settings.trace_interval_seconds = 0.01
    try:
        with TestClient(app) as client:
            health = client.get(
                "/api/health", headers={"Origin": "http://localhost:3000"}
            )
            assert health.status_code == 200
            assert health.json()["status"] == "ok"
            assert health.headers["access-control-allow-origin"] == "http://localhost:3000"

        async def scenario() -> None:
            # The ticker is intentionally infinite, so consume one item from
            # the bus rather than waiting for an in-memory HTTP client to
            # finish an SSE response that never finishes.
            async with subscribe() as queue:
                ticker = asyncio.create_task(main._fake_trace_ticker())
                try:
                    step = await asyncio.wait_for(queue.get(), timeout=1)
                    assert step.agent == "system"
                    assert "Level 0 fake trace tick" in step.message
                finally:
                    ticker.cancel()
                    await asyncio.gather(ticker, return_exceptions=True)

            class ConnectedRequest:
                def __init__(self) -> None:
                    self.calls = 0

                async def is_disconnected(self) -> bool:
                    self.calls += 1
                    return self.calls > 1

            request = ConnectedRequest()
            response = await main.stream(request)
            assert response.headers["cache-control"] == "no-cache"
            assert response.headers["x-accel-buffering"] == "no"

            frame_task = asyncio.create_task(response.body_iterator.__anext__())
            while trace_bus.subscriber_count == 0:
                await asyncio.sleep(0)
            await publish(
                TraceStep(
                    ts=datetime.now(timezone.utc),
                    agent="system",
                    kind="observe",
                    message="SSE test frame",
                )
            )
            frame = await asyncio.wait_for(frame_task, timeout=1)
            assert frame["event"] == "trace"
            assert "SSE test frame" in frame["data"]
            with pytest.raises(StopAsyncIteration):
                await response.body_iterator.__anext__()

        asyncio.run(scenario())
    finally:
        main.settings.trace_interval_seconds = original_interval
