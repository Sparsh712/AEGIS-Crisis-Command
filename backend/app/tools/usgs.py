"""Offline USGS-shaped earthquake tools.

The production boundary can later add an HTTP adapter around these parsers.
For now every public function reads a local scenario fixture so replay and
tests never depend on network access, wall-clock time, or a remote API.
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any, Mapping

from ..models import Event, Hazard


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "nepal_2015.json"


def _read_fixture(fixture: str | Path | Mapping[str, Any] | None) -> Mapping[str, Any]:
    if fixture is None:
        fixture = FIXTURE_PATH
    if isinstance(fixture, Mapping):
        return fixture
    path = Path(fixture)
    if not path.exists() and path.suffix != ".json":
        path = FIXTURE_PATH.parent / f"{path.name}.json"
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, Mapping):
        raise ValueError("USGS fixture must contain a JSON object")
    return value


def _utc_from_epoch_ms(value: Any) -> datetime:
    if not isinstance(value, (int, float)):
        raise ValueError("USGS properties.time must be epoch milliseconds")
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def events_from_geojson(payload: Mapping[str, Any]) -> list[Event]:
    """Convert a USGS GeoJSON FeatureCollection into validated Events."""

    features = payload.get("features", [])
    if not isinstance(features, list):
        raise ValueError("USGS GeoJSON features must be a list")

    events: list[Event] = []
    for feature in features:
        if not isinstance(feature, Mapping):
            continue
        properties = feature.get("properties") or {}
        geometry = feature.get("geometry") or {}
        coordinates = geometry.get("coordinates") or []
        if len(coordinates) < 2:
            raise ValueError("USGS feature geometry must contain [lon, lat]")
        feature_id = str(feature.get("id") or properties.get("code") or "unknown")
        raw = {
            "title": properties.get("title"),
            "pager_alert": properties.get("alert"),
            "sig": properties.get("sig"),
            "tsunami": properties.get("tsunami", 0),
            "depth_km": coordinates[2] if len(coordinates) > 2 else None,
        }
        events.append(
            Event(
                id=f"usgs:{feature_id}",
                source="usgs",
                hazard=Hazard.earthquake,
                lat=float(coordinates[1]),
                lon=float(coordinates[0]),
                magnitude=float(properties["mag"]) if properties.get("mag") is not None else None,
                alert_level=properties.get("alert"),
                occurred_at=_utc_from_epoch_ms(properties["time"]),
                raw=raw,
                synthetic=False,
            )
        )
    return sorted(events, key=lambda event: (event.occurred_at, event.id))


def _events_from_manifest(payload: Mapping[str, Any]) -> list[Event]:
    raw_events = payload.get("events", [])
    if not isinstance(raw_events, list):
        raise ValueError("scenario events must be a list")
    return sorted(
        [Event.model_validate(item) for item in raw_events if isinstance(item, Mapping)],
        key=lambda event: (event.occurred_at, event.id),
    )


def load_fixture_events(fixture: str | Path | Mapping[str, Any] | None = None) -> list[Event]:
    """Load events from either a scenario manifest or a GeoJSON fixture."""

    payload = _read_fixture(fixture)
    if payload.get("type") == "FeatureCollection":
        return events_from_geojson(payload)
    usgs_payload = payload.get("usgs")
    if isinstance(usgs_payload, Mapping) and usgs_payload.get("type") == "FeatureCollection":
        return events_from_geojson(usgs_payload)
    return _events_from_manifest(payload)


def live_feed(fixture: str | Path | Mapping[str, Any] | None = None) -> list[Event]:
    """Return the deterministic local equivalent of the USGS live feed."""

    return load_fixture_events(fixture)


def historical_query(
    starttime: datetime | None = None,
    endtime: datetime | None = None,
    minmagnitude: float | None = None,
    fixture: str | Path | Mapping[str, Any] | None = None,
) -> list[Event]:
    """Return fixture events matching the usual USGS historical filters."""

    events = load_fixture_events(fixture)
    if starttime is not None:
        events = [event for event in events if event.occurred_at >= starttime]
    if endtime is not None:
        events = [event for event in events if event.occurred_at <= endtime]
    if minmagnitude is not None:
        events = [
            event
            for event in events
            if event.magnitude is not None and event.magnitude >= minmagnitude
        ]
    return events


# Names that read naturally at call sites.
fetch_live = live_feed
query_historical = historical_query
