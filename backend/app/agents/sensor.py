"""Sensor agent: normalises the hardcoded replay event."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ..models import Event, Hazard

if TYPE_CHECKING:
    from ..orchestrator import AgentContext


def sample_event() -> Event:
    """Return the stable Nepal 2015 mainshock used by the vertical slice."""

    return Event(
        id="usgs:2015-04-25-nepal-mainshock",
        source="usgs",
        hazard=Hazard.earthquake,
        lat=28.1473,
        lon=84.7080,
        magnitude=7.8,
        alert_level="red",
        occurred_at=datetime(2015, 4, 25, 6, 11, 25, tzinfo=timezone.utc),
        raw={"pager_alert": "red", "tsunami": 0, "region": "Gorkha, Nepal"},
        synthetic=False,
    )


async def run(event: Event, ctx: "AgentContext") -> Event:
    ctx.store.add_event(event)
    await ctx.trace(
        "sensor",
        "observe",
        "USGS replay event normalised: M7.8 Nepal mainshock.",
        {"event_id": event.id},
    )
    return event
