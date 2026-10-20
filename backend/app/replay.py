"""Deterministic offline scenario replay primitives."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import inspect
import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Mapping

from .models import Event


SCENARIO_DIR = Path(__file__).resolve().parents[1] / "fixtures" / "scenarios"
MIN_SPEED = 1.0
MAX_SPEED = 60.0


@dataclass(frozen=True)
class Scenario:
    """Validated scenario data plus replay-only timing metadata."""

    name: str
    label: str
    synthetic: bool
    events: tuple[Event, ...]
    replay_offsets: tuple[float, ...]
    manifest: Mapping[str, Any]


@dataclass(frozen=True)
class ReplayItem:
    event: Event
    clock_at: datetime
    delay_seconds: float


def _scenario_path(source: str | Path) -> Path:
    path = Path(source)
    if path.exists():
        return path
    filename = path.name if path.suffix == ".json" else f"{path.name}.json"
    return SCENARIO_DIR / filename


def load_scenario(source: str | Path) -> Scenario:
    """Load, validate, and deterministically order a scenario manifest."""

    path = _scenario_path(source)
    with path.open("r", encoding="utf-8") as handle:
        manifest = json.load(handle)
    if not isinstance(manifest, Mapping):
        raise ValueError("scenario manifest must contain a JSON object")
    raw_events = manifest.get("events")
    if not isinstance(raw_events, list) or not raw_events:
        raise ValueError("scenario manifest must contain at least one event")

    indexed: list[tuple[Event, float | None]] = []
    for raw_event in raw_events:
        if not isinstance(raw_event, Mapping):
            raise ValueError("scenario events must be JSON objects")
        event = Event.model_validate(raw_event)
        raw_offset = raw_event.get("replay_after_seconds")
        offset = float(raw_offset) if raw_offset is not None else None
        indexed.append((event, offset))
    indexed.sort(key=lambda item: (item[0].occurred_at, item[0].id))

    offsets: list[float] = []
    previous_occurred: datetime | None = None
    previous_offset = 0.0
    for event, explicit_offset in indexed:
        if explicit_offset is not None:
            if explicit_offset < 0 or explicit_offset < previous_offset:
                raise ValueError("replay_after_seconds must be non-negative and ordered")
            current_offset = explicit_offset
        elif previous_occurred is None:
            current_offset = 0.0
        else:
            current_offset = previous_offset + max(
                0.0, (event.occurred_at - previous_occurred).total_seconds()
            )
        offsets.append(current_offset)
        previous_occurred = event.occurred_at
        previous_offset = current_offset

    return Scenario(
        name=str(manifest.get("name") or path.stem),
        label=str(manifest.get("label") or manifest.get("name") or path.stem),
        synthetic=bool(manifest.get("synthetic", any(event.synthetic for event, _ in indexed))),
        events=tuple(event for event, _ in indexed),
        replay_offsets=tuple(offsets),
        manifest=manifest,
    )


def load_events(source: str | Path) -> list[Event]:
    """Convenience loader returning a fresh ordered list of Event models."""

    return list(load_scenario(source).events)


def build_schedule(source: Scenario | str | Path, speed: float = 1.0) -> list[ReplayItem]:
    """Build a deterministic accelerated replay schedule without sleeping."""

    if not MIN_SPEED <= speed <= MAX_SPEED:
        raise ValueError(f"speed must be between {MIN_SPEED:g}x and {MAX_SPEED:g}x")
    scenario = source if isinstance(source, Scenario) else load_scenario(source)
    start = scenario.events[0].occurred_at
    return [
        ReplayItem(
            event=event,
            clock_at=start + timedelta(seconds=offset),
            delay_seconds=offset / speed - (scenario.replay_offsets[index - 1] / speed if index else 0.0),
        )
        for index, (event, offset) in enumerate(zip(scenario.events, scenario.replay_offsets))
    ]


async def _invoke(callback: Callable[..., Any], *args: Any) -> None:
    result = callback(*args)
    if inspect.isawaitable(result):
        await result


class ReplayEngine:
    """Run a scenario while keeping timing and callback behavior testable."""

    def __init__(self, source: Scenario | str | Path, speed: float = 1.0) -> None:
        self.scenario = source if isinstance(source, Scenario) else load_scenario(source)
        self.speed = speed
        self.schedule = build_schedule(self.scenario, speed)

    async def run(
        self,
        on_event: Callable[[Event], Any],
        on_clock: Callable[[datetime, Event], Any] | None = None,
        sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
    ) -> None:
        """Emit ordered events and optional replay-clock updates."""

        for item in self.schedule:
            if item.delay_seconds:
                await sleep(item.delay_seconds)
            if on_clock is not None:
                await _invoke(on_clock, item.clock_at, item.event)
            await _invoke(on_event, item.event)


async def iter_replay(
    source: Scenario | str | Path,
    speed: float = 1.0,
    sleep: Callable[[float], Awaitable[Any]] = asyncio.sleep,
):
    """Yield events in replay order using the scenario's accelerated clock."""

    engine = ReplayEngine(source, speed)
    for item in engine.schedule:
        if item.delay_seconds:
            await sleep(item.delay_seconds)
        yield item.event


replay = ReplayEngine
