"""Focused checks for deterministic offline replay and tool foundations."""

import asyncio
from datetime import datetime, timezone

import pytest

from backend.app.replay import ReplayEngine, build_schedule, load_scenario
from backend.app.tools.geo import bounding_box, haversine_km
from backend.app.tools.overpass import facilities, places_population
from backend.app.tools.usgs import load_fixture_events


def test_haversine_and_bounding_box_are_stable() -> None:
    assert haversine_km(0, 0, 0, 1) == pytest.approx(111.195, abs=0.01)
    assert haversine_km(27.7172, 85.324, 27.7172, 85.324) == 0

    min_lat, min_lon, max_lat, max_lon = bounding_box(0, 0, 10)
    assert min_lat == pytest.approx(-0.08993, abs=0.0001)
    assert max_lat == pytest.approx(0.08993, abs=0.0001)
    assert min_lon == pytest.approx(-0.08993, abs=0.0001)
    assert max_lon == pytest.approx(0.08993, abs=0.0001)


def test_fixture_loading_is_deterministic_and_uses_event_contract() -> None:
    first = load_scenario("nepal_2015")
    second = load_scenario("nepal_2015")

    assert [event.id for event in first.events] == [event.id for event in second.events]
    assert [event.occurred_at for event in first.events] == sorted(
        event.occurred_at for event in first.events
    )
    assert first.events[0].occurred_at == datetime(2015, 4, 25, 6, 11, 25, tzinfo=timezone.utc)
    assert all(event.__class__.__name__ == "Event" for event in first.events)

    usgs_events = load_fixture_events("nepal_2015")
    assert [event.id for event in usgs_events] == [event.id for event in first.events]
    hospital_results = facilities(
        28.1473, 84.708, 40, types=("hospital",), fixture="nepal_2015"
    )
    assert hospital_results[0].name == "Gorkha District Hospital"
    assert places_population(28.1473, 84.708, 40, fixture="nepal_2015") == 620000


def test_replay_orders_events_and_scales_delays_without_network() -> None:
    scenario = load_scenario("nepal_2015")
    schedule = build_schedule(scenario, speed=2)

    assert [item.event.id for item in schedule] == [
        "usgs:2015-nepal-mainshock",
        "usgs:2015-nepal-aftershock",
    ]
    assert [item.delay_seconds for item in schedule] == [0, 2]
    assert schedule[1].clock_at > schedule[0].clock_at

    emitted: list[str] = []
    clocks: list[datetime] = []

    async def no_wait(_: float) -> None:
        return None

    async def scenario_run() -> None:
        await ReplayEngine(scenario, speed=60).run(
            lambda event: emitted.append(event.id),
            lambda clock_at, _: clocks.append(clock_at),
            sleep=no_wait,
        )

    asyncio.run(scenario_run())
    assert emitted == [event.id for event in scenario.events]
    assert clocks == [item.clock_at for item in build_schedule(scenario, speed=60)]
