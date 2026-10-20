"""Offline Overpass-shaped facility and population helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..models import Facility
from .geo import haversine_km


FIXTURE_PATH = Path(__file__).resolve().parents[2] / "fixtures" / "scenarios" / "nepal_2015.json"
DEFAULT_CAPACITY = {"hospital": 100, "clinic": 10, "shelter": 50}
TRIMMED_TAGS = {"amenity", "beds", "capacity", "name", "place", "population", "shelter_type"}


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
        raise ValueError("Overpass fixture must contain a JSON object")
    return value


def _elements(fixture: str | Path | Mapping[str, Any] | None) -> list[Mapping[str, Any]]:
    payload = _read_fixture(fixture)
    overpass = payload.get("overpass", payload)
    if isinstance(overpass, Mapping):
        elements = overpass.get("elements", [])
    else:
        elements = []
    if not isinstance(elements, list):
        raise ValueError("Overpass elements must be a list")
    return [element for element in elements if isinstance(element, Mapping)]


def _coordinates(element: Mapping[str, Any]) -> tuple[float, float] | None:
    if element.get("type") == "node" and element.get("lat") is not None and element.get("lon") is not None:
        return float(element["lat"]), float(element["lon"])
    center = element.get("center")
    if isinstance(center, Mapping) and center.get("lat") is not None and center.get("lon") is not None:
        return float(center["lat"]), float(center["lon"])
    return None


def _tags(element: Mapping[str, Any]) -> dict[str, Any]:
    raw_tags = element.get("tags") or {}
    if not isinstance(raw_tags, Mapping):
        return {}
    return {str(key): value for key, value in raw_tags.items() if key in TRIMMED_TAGS}


def _capacity(tags: Mapping[str, Any], facility_type: str) -> tuple[int, bool]:
    for key in ("beds", "capacity"):
        value = tags.get(key)
        if value is not None:
            try:
                return max(0, int(float(str(value).replace(",", "")))), False
            except (TypeError, ValueError):
                pass
    return DEFAULT_CAPACITY.get(facility_type, 10), True


def facilities(
    lat: float,
    lon: float,
    radius_km: float,
    types: Iterable[str] = ("hospital", "clinic", "shelter"),
    fixture: str | Path | Mapping[str, Any] | None = None,
) -> list[Facility]:
    """Return nearby facilities from cached Overpass-shaped elements."""

    wanted = {str(item) for item in types}
    results: list[Facility] = []
    for element in _elements(fixture):
        tags = _tags(element)
        facility_type = str(tags.get("amenity", ""))
        if facility_type not in wanted:
            continue
        coordinates = _coordinates(element)
        if coordinates is None:
            continue
        item_lat, item_lon = coordinates
        distance = haversine_km(lat, lon, item_lat, item_lon)
        if distance > radius_km:
            continue
        capacity, estimated = _capacity(tags, facility_type)
        element_id = f"osm:{element.get('type', 'element')}/{element.get('id', 'unknown')}"
        results.append(
            Facility(
                id=element_id,
                name=str(tags.get("name") or element_id),
                type=facility_type,
                lat=item_lat,
                lon=item_lon,
                capacity=capacity,
                capacity_estimated=estimated,
                distance_km=round(distance, 3),
                evidence_ids=[],
            )
        )
    return sorted(results, key=lambda item: (item.distance_km or 0, item.id))


def places_population(
    lat: float,
    lon: float,
    radius_km: float,
    fixture: str | Path | Mapping[str, Any] | None = None,
) -> int:
    """Return the lower-bound sum of nearby OSM place populations."""

    total = 0
    for element in _elements(fixture):
        tags = _tags(element)
        if "place" not in tags or "population" not in tags:
            continue
        coordinates = _coordinates(element)
        if coordinates is None or haversine_km(lat, lon, *coordinates) > radius_km:
            continue
        try:
            total += max(0, int(float(str(tags["population"]).replace(",", ""))))
        except (TypeError, ValueError):
            continue
    return total


# Explicit aliases keep the tool vocabulary close to the build specification.
nearby_facilities = facilities
