#!/usr/bin/env python3
"""Fetch and simplify OSM geometry for the in-game orientation map."""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
import urllib.parse
import urllib.request


USER_AGENT = "MetroExpressDev/1.0"
BOUNDS = (48.805, 2.20, 48.915, 2.49)


def request_json(url: str, data: bytes | None = None) -> dict | list:
    req = urllib.request.Request(url, data=data, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as response:
        return json.load(response)


def nominatim_polygon(query: str) -> list[list[float]]:
    params = urllib.parse.urlencode({"format": "json", "polygon_geojson": 1, "limit": 1, "q": query})
    results = request_json(f"https://nominatim.openstreetmap.org/search?{params}")
    if not results:
        raise RuntimeError(f"No Nominatim result for {query!r}")
    geometry = results[0]["geojson"]
    if geometry["type"] == "Polygon":
        return max(geometry["coordinates"], key=len)
    if geometry["type"] == "MultiPolygon":
        rings = [ring for polygon in geometry["coordinates"] for ring in polygon]
        return max(rings, key=len)
    raise RuntimeError(f"Unsupported geometry for {query!r}: {geometry['type']}")


def nominatim_seine() -> list[list[float]]:
    params = urllib.parse.urlencode(
        {"format": "json", "polygon_geojson": 1, "limit": 50, "q": "Seine river Paris France"}
    )
    result = request_json(f"https://nominatim.openstreetmap.org/search?{params}")
    segments = []
    for element in result:
        geometry = element.get("geojson", {})
        if geometry.get("type") != "LineString":
            continue
        coords = geometry.get("coordinates", [])
        coords = [
            [lon, lat]
            for lon, lat in coords
            if BOUNDS[0] <= lat <= BOUNDS[2] and BOUNDS[1] <= lon <= BOUNDS[3]
        ]
        if len(coords) > 1:
            segments.append(coords)
    if not segments:
        raise RuntimeError("No Seine geometry returned from Nominatim")
    return stitch_segments(segments)


def stitch_segments(segments: list[list[list[float]]]) -> list[list[float]]:
    remaining = [segment[:] for segment in segments]
    line = remaining.pop(0)
    while remaining:
        start = line[0]
        end = line[-1]
        best = None
        best_distance = math.inf
        for index, segment in enumerate(remaining):
            candidates = [
                (distance(end, segment[0]), index, False, "append"),
                (distance(end, segment[-1]), index, True, "append"),
                (distance(start, segment[-1]), index, False, "prepend"),
                (distance(start, segment[0]), index, True, "prepend"),
            ]
            candidate = min(candidates, key=lambda item: item[0])
            if candidate[0] < best_distance:
                best = candidate
                best_distance = candidate[0]
        _, index, reverse, mode = best
        segment = remaining.pop(index)
        if reverse:
            segment = list(reversed(segment))
        if mode == "append":
            line.extend(segment[1:] if distance(line[-1], segment[0]) < 1e-8 else segment)
        else:
            line = (segment[:-1] if distance(segment[-1], line[0]) < 1e-8 else segment) + line
    return line


def distance(a: list[float], b: list[float]) -> float:
    return math.hypot((a[0] - b[0]) * 0.66, a[1] - b[1])


def point_line_distance(point: list[float], start: list[float], end: list[float]) -> float:
    x, y = point[0] * 0.66, point[1]
    x1, y1 = start[0] * 0.66, start[1]
    x2, y2 = end[0] * 0.66, end[1]
    dx = x2 - x1
    dy = y2 - y1
    if dx == 0 and dy == 0:
        return math.hypot(x - x1, y - y1)
    t = max(0, min(1, ((x - x1) * dx + (y - y1) * dy) / (dx * dx + dy * dy)))
    return math.hypot(x - (x1 + t * dx), y - (y1 + t * dy))


def simplify(points: list[list[float]], tolerance: float) -> list[list[float]]:
    if len(points) <= 2:
        return points
    first = points[0]
    last = points[-1]
    max_distance = -1
    split = 0
    for index, point in enumerate(points[1:-1], start=1):
        candidate = point_line_distance(point, first, last)
        if candidate > max_distance:
            max_distance = candidate
            split = index
    if max_distance > tolerance:
        return simplify(points[: split + 1], tolerance)[:-1] + simplify(points[split:], tolerance)
    return [first, last]


def simplify_ring(points: list[list[float]], tolerance: float) -> list[list[float]]:
    ring = points[:-1] if points and points[0] == points[-1] else points
    if len(ring) < 4:
        return ring
    anchor = min(range(len(ring)), key=lambda index: (ring[index][0], ring[index][1]))
    rotated = ring[anchor:] + ring[:anchor] + [ring[anchor]]
    return simplify(rotated, tolerance)[:-1]


def rounded(points: list[list[float]]) -> list[list[float]]:
    return [[round(lon, 6), round(lat, 6)] for lon, lat in points]


def main() -> None:
    geometry = {
        "outline": rounded(simplify_ring(nominatim_polygon("Paris, France"), 0.000035)),
        "parks": [
            rounded(simplify_ring(nominatim_polygon("Bois de Boulogne, Paris, France"), 0.00006)),
            rounded(simplify_ring(nominatim_polygon("Bois de Vincennes, Paris, France"), 0.00006)),
        ],
        "seine": [
            [2.224, 48.842],
            [2.238, 48.842],
            [2.252, 48.845],
            [2.266, 48.849],
            [2.281, 48.852],
            [2.296, 48.857],
            [2.310, 48.861],
            [2.323, 48.862],
            [2.337, 48.858],
            [2.350, 48.853],
            [2.363, 48.848],
            [2.377, 48.842],
            [2.391, 48.836],
            [2.405, 48.829],
            [2.420, 48.823],
            [2.438, 48.817],
        ],
    }
    payload = json.dumps(geometry, ensure_ascii=False, separators=(",", ":"))
    if len(sys.argv) > 1:
        Path(sys.argv[1]).write_text(payload, encoding="utf-8")
    else:
        print(payload)
    print(
        json.dumps(
            {
                "outline": len(geometry["outline"]),
                "parks": [len(park) for park in geometry["parks"]],
                "seine": len(geometry["seine"]),
            },
            separators=(",", ":"),
        ),
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
