"""Small geographic helpers with no network or third-party dependencies."""

from __future__ import annotations

import math


EARTH_RADIUS_KM = 6_371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Return the great-circle distance between two WGS84-ish coordinates.

    The calculation deliberately uses a fixed mean earth radius so fixture
    results stay stable across machines and Python versions.
    """

    for value in (lat1, lon1, lat2, lon2):
        if not math.isfinite(value):
            raise ValueError("coordinates must be finite numbers")
    if not -90 <= lat1 <= 90 or not -90 <= lat2 <= 90:
        raise ValueError("latitude must be between -90 and 90 degrees")

    lat1_rad, lat2_rad = math.radians(lat1), math.radians(lat2)
    delta_lat = lat2_rad - lat1_rad
    delta_lon = math.radians(lon2 - lon1)
    hav = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(min(1.0, hav)))


def bounding_box(lat: float, lon: float, radius_km: float) -> tuple[float, float, float, float]:
    """Return ``(min_lat, min_lon, max_lat, max_lon)`` around a point.

    This is intended for coarse source filtering, not geodesic containment.
    Longitude is clamped at the poles and to the ordinary ``[-180, 180]``
    range because all current AEGIS fixtures are away from the antimeridian.
    """

    if not math.isfinite(radius_km) or radius_km < 0:
        raise ValueError("radius_km must be a finite non-negative number")
    if not -90 <= lat <= 90 or not -180 <= lon <= 180:
        raise ValueError("coordinates are outside their valid ranges")

    lat_delta = math.degrees(radius_km / EARTH_RADIUS_KM)
    cos_lat = max(math.cos(math.radians(lat)), 1e-12)
    lon_delta = math.degrees(radius_km / (EARTH_RADIUS_KM * cos_lat))
    return (
        max(-90.0, lat - lat_delta),
        max(-180.0, lon - lon_delta),
        min(90.0, lat + lat_delta),
        min(180.0, lon + lon_delta),
    )


# Short aliases make the helper convenient for tool call sites and preserve a
# compact public surface for future agents.
distance_km = haversine_km
bbox = bounding_box
