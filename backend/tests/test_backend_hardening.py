"""Focused checks for the live HTTP/cache hardening slice."""

import asyncio
from datetime import datetime, timezone

from backend.app import main
from backend.app.models import Event, Hazard
from backend.app.tools.http import fetch_json
from backend.app.tools.usgs import USGSFeed


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self.payload


class _Client:
    calls = 0
    payload = {"ok": True}
    error: BaseException | None = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_args):
        return None

    async def get(self, *_args, **_kwargs):
        type(self).calls += 1
        if self.error is not None:
            raise self.error
        return _Response(type(self).payload)


def test_http_cache_hit_avoids_second_network_request(tmp_path) -> None:
    _Client.calls = 0
    _Client.error = None

    async def scenario():
        first = await fetch_json(
            "https://example.test/feed",
            cache_dir=tmp_path,
            cache_key="test-feed",
            client_factory=_Client,
        )
        second = await fetch_json(
            "https://example.test/feed",
            cache_dir=tmp_path,
            cache_key="test-feed",
            client_factory=_Client,
        )
        return first, second

    first, second = asyncio.run(scenario())

    assert first.data == {"ok": True}
    assert first.metadata["cache_status"] == "miss"
    assert second.data == first.data
    assert second.metadata["cache_status"] == "hit"
    assert _Client.calls == 1


def test_fixture_only_never_constructs_or_calls_network(tmp_path) -> None:
    class _ForbiddenClient:
        def __init__(self, **_kwargs):
            raise AssertionError("fixture-only mode attempted network access")

    result = asyncio.run(
        fetch_json(
            "https://example.test/fixture",
            cache_dir=tmp_path,
            fixture={"source": "fixture"},
            fixture_only=True,
            client_factory=_ForbiddenClient,
        )
    )

    assert result.data == {"source": "fixture"}
    assert result.metadata["cache_status"] == "fixture"
    assert result.metadata["network_attempted"] is False


def test_timeout_retries_once_then_uses_fixture_fallback(tmp_path) -> None:
    _Client.calls = 0
    _Client.error = TimeoutError("simulated timeout")

    result = asyncio.run(
        fetch_json(
            "https://example.test/slow",
            cache_dir=tmp_path,
            fixture={"source": "fallback"},
            client_factory=_Client,
        )
    )

    assert result.data == {"source": "fallback"}
    assert result.metadata["cache_status"] == "fallback"
    assert result.metadata["fallback"] is True
    assert result.metadata["fallback_source"] == "fixture"
    assert result.metadata["attempts"] == 2
    assert _Client.calls == 2


def test_live_poll_dedupes_repeated_event_and_exposes_cache_trace(monkeypatch) -> None:
    event = Event(
        id="usgs:test-live-event",
        source="usgs",
        hazard=Hazard.earthquake,
        lat=1.0,
        lon=2.0,
        magnitude=5.0,
        occurred_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    feeds = iter(
        [
            USGSFeed(
                [event],
                {
                    "cache_status": "miss",
                    "fallback": False,
                    "fallback_source": None,
                    "network_attempted": True,
                    "attempts": 1,
                },
            ),
            USGSFeed(
                [event],
                {
                    "cache_status": "hit",
                    "fallback": False,
                    "fallback_source": "cache",
                    "network_attempted": False,
                    "attempts": 0,
                },
            ),
        ]
    )
    processed: list[str] = []

    async def fake_process_event(incoming, *, data_store, resource_ledger):
        processed.append(incoming.id)
        return None

    async def fake_fetch_live_events(**_kwargs):
        return next(feeds)

    monkeypatch.setattr(main, "fetch_live_events", fake_fetch_live_events)
    monkeypatch.setattr(main, "process_event", fake_process_event)
    monkeypatch.setattr(main.settings, "live_enabled", True)
    monkeypatch.setattr(main.settings, "fixture_only", False)
    monkeypatch.setattr(main.settings, "live_max_polls", 2)
    monkeypatch.setattr(main.settings, "live_poll_interval_seconds", 0.001)
    main.store.clear()
    main.ledger.reset()

    asyncio.run(main._run_live())

    assert processed == [event.id]
    assert main.runtime_mode["deduped_count"] == 1
    assert any(step.refs.get("cache_status") == "hit" for step in main.store.trace)
    assert any(step.kind == "dedupe" for step in main.store.trace)
