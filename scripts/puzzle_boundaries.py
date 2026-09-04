"""Dependency-free endpoint checks against saved WGS84 administrative polygons."""

import json
import math
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=None)
def load_polygons(path: Path) -> list:
    data = json.loads(path.read_text(encoding="utf-8"))
    features = data["features"] if data["type"] == "FeatureCollection" else [data]
    polygons = []
    for feature in features:
        geometry = feature["geometry"]
        if geometry["type"] == "Polygon":
            polygons.append(geometry["coordinates"])
        elif geometry["type"] == "MultiPolygon":
            polygons.extend(geometry["coordinates"])
        else:
            raise ValueError(f"Expected Polygon/MultiPolygon in {path}")
    if not polygons:
        raise ValueError(f"Empty boundary: {path}")
    return polygons


def ring_location(x: float, y: float, ring: list) -> int:
    """Return -1 outside, 0 on the boundary, 1 inside a closed ring."""
    inside = False
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        cross = (x - ax) * (by - ay) - (y - ay) * (bx - ax)
        if (abs(cross) <= 1e-12 and min(ax, bx) - 1e-12 <= x <= max(ax, bx) + 1e-12
                and min(ay, by) - 1e-12 <= y <= max(ay, by) + 1e-12):
            return 0
        if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
            inside = not inside
    return 1 if inside else -1


def covers_station(path: Path, station: dict) -> bool:
    x, y = station.get("lon"), station.get("lat")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
           for v in (x, y)):
        return False
    for polygon in load_polygons(path):
        outer = ring_location(x, y, polygon[0])
        if outer == 0:
            return True
        if outer == 1:
            holes = [ring_location(x, y, hole) for hole in polygon[1:]]
            if 0 in holes or 1 not in holes:
                return True
    return False
