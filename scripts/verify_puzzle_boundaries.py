#!/usr/bin/env python3
"""Audit endpoint geography and all committed Paris/London puzzle bundles."""

import argparse
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

import build_data as build
from puzzle_boundaries import covers_station, ring_location


def verify_geometry():
    outer = [[0, 0], [4, 0], [4, 4], [0, 4], [0, 0]]
    hole = [[1, 1], [2, 1], [2, 2], [1, 2], [1, 1]]
    island = [[6, 6], [7, 6], [7, 7], [6, 7], [6, 6]]
    assert ring_location(0, 2, outer) == 0
    assert ring_location(3, 3, outer) == 1
    assert ring_location(5, 5, outer) == -1
    with tempfile.TemporaryDirectory(prefix="boundary-test-", dir=build.ROOT) as directory:
        path = Path(directory) / "boundary.geojson"
        build.write_json(path, {"type": "Feature", "geometry": {
            "type": "MultiPolygon", "coordinates": [[outer, hole], [island]]}})
        for lon, lat, expected in [(3, 3, True), (1.5, 1.5, False), (1, 1.5, True),
                                   (6.5, 6.5, True), (5, 5, False), (0, 0, True)]:
            assert covers_station(path, {"lon": lon, "lat": lat}) == expected
        for station in [{}, {"lon": None, "lat": 2}, {"lon": float("nan"), "lat": 2},
                        {"lon": True, "lat": 2}]:
            assert not covers_station(path, station)


def audit_city(city, check_outputs):
    build.configure_city(city)
    network = json.loads(build.NETWORK_OUT.read_text(encoding="utf-8"))
    stations = network["stations"]
    config = build.CITY_CONFIG["puzzles"]
    boxes = {"paris": (48.815, 48.902, 2.25, 2.42), "london": (51.35, 51.65, -.52, .25)}
    south, north, west, east = boxes[city]
    unrestricted = set(config["endpointModes"])
    bounded = set(config["boundedEndpointModes"])
    before = {sid for sid, s in stations.items() if set(s["modes"]) & unrestricted or (
        set(s["modes"]) & bounded and south <= s["lat"] <= north and west <= s["lon"] <= east)}
    after = {sid for sid, s in stations.items() if build.is_puzzle_endpoint(s)}
    print(f"{city}: {len(stations)} station records; eligible endpoints {len(before)} -> {len(after)}")
    print("  removed:", [(sid, stations[sid]["name"]) for sid in sorted(before - after)])
    print("  added:", [(sid, stations[sid]["name"]) for sid in sorted(after - before)])
    assert all(sid in after for sid, s in stations.items() if set(s["modes"]) & unrestricted)
    assert all(isinstance(s.get("lat"), (int, float)) and isinstance(s.get("lon"), (int, float))
               for s in stations.values()), "Missing station coordinates"
    excluded = {"paris": ["Gentilly", "Issy", "Issy Val de Seine", "Pantin"], "london": ["Iver"]}
    for name in excluded[city]:
        matches = [s for s in stations.values() if s["name"] == name]
        assert matches, name
        assert all(not build.is_puzzle_endpoint(s) for s in matches), name
    included = {"paris": ["Cité Universitaire", "Rosa Parks"],
                "london": ["West Drayton", "Harold Wood", "Heathrow Terminal 5"]}
    for name in included[city]:
        matches = [s for s in stations.values() if s["name"] == name]
        assert matches and all(build.is_puzzle_endpoint(s) for s in matches), name
    # A synthetic old pool must be filtered, and an incomplete pool rejected.
    with tempfile.TemporaryDirectory(prefix="boundary-test-", dir=build.ROOT) as directory:
        cache = Path(directory) / "pairs.json"
        cached = [{"start": sid, "end": sid} for sid in stations]
        build.write_json(cache, {"puzzles": cached})
        with patch.object(build, "ALL_PAIRS_OUT", cache):
            pairs, _ = build.load_all_pairs()
            assert {p["start"] for p in pairs} == after
            build.write_json(cache, {"puzzles": []})
            assert build.load_all_pairs() is None
    if check_outputs:
        assert network["metadata"]["puzzleConstraints"] == config
        if city == "london":
            # A cross-platform hub optimization can turn two lines into a
            # repeated-line ride. Such a pair must not enter the daily pool.
            pair = {"id": "hub-regression", "start": "910GHTRWTM5", "end": "940GZZLUUXB",
                    "playable": True}
            optimized = build.optimize_daily_endpoint_hubs([pair])[0]
            assert not optimized["playable"] and "repeated_line" in optimized["unplayableReasons"]
        index = json.loads(build.DAILY_INDEX_OUT.read_text(encoding="utf-8"))
        assert len(index["dates"]) == len(set(index["dates"]))
        paths = [build.EXAMPLE_OUT, *sorted(build.DAILY_DIR.glob("*.json"))]
        count = 0
        for path in paths:
            if path.name == "index.json":
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            puzzles = data["puzzles"]
            expected = config["exampleCount"] if path == build.EXAMPLE_OUT else config["dailyCount"]
            assert len(puzzles) == expected, path
            assert len({p["id"] for p in puzzles}) == len(puzzles), path
            for p in puzzles:
                assert p["start"] in after and p["end"] in after, (path, p["id"])
            count += len(puzzles)
        assert all((build.DAILY_DIR / f"{day}.json").exists() for day in index["dates"])
        print(f"  verified {count} committed puzzles, unique IDs within each bundle")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit-only", action="store_true")
    args = parser.parse_args()
    verify_geometry()
    for city in ("paris", "london"):
        audit_city(city, not args.audit_only)
