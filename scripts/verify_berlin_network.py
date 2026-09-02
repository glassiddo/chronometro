#!/usr/bin/env python3
"""Verify Berlin U-Bahn-specific topology and normalization invariants."""

from __future__ import annotations

import csv
import json
import sys
from collections import defaultdict, deque
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_data  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    build_data.configure_city("berlin")
    network_path = ROOT / "public/data/berlin/network.json"
    network = json.loads(network_path.read_text(encoding="utf-8"))
    expected_labels = {f"U{number}" for number in range(1, 10)}
    labels = {route["label"] for route in network["routes"].values()}
    require(labels == expected_labels, "network must contain exactly U1 through U9")
    require(all(route["routeType"] == "400" for route in network["routes"].values()), "non-U-Bahn route included")

    raw_stops = {}
    for directory in ("gouv_berlin_vbb_gtfs-export", "gouv_berlin_vbb_gtfs-archive-2021"):
        raw_stops.update({
            row["stop_id"]: row
            for row in csv.DictReader((ROOT / directory / "stops.txt").open(encoding="utf-8-sig"))
        })
    require(len(network["stations"]) == 175, "unexpected playable parent-station count")
    require(all(raw_stops[sid].get("location_type") == "1" for sid in network["stations"]), "platform leaked into playable stations")
    require(all("(Berlin)" not in station["name"] for station in network["stations"].values()), "raw city suffix leaked into station name")

    adjacency: dict[str, set[str]] = defaultdict(set)
    for direction in network["directions"].values():
        for left, right in zip(direction["stations"], direction["stations"][1:]):
            adjacency[left].add(right)
            adjacency[right].add(left)
    start = next(iter(network["stations"]))
    seen = {start}
    queue = deque([start])
    while queue:
        for candidate in adjacency[queue.popleft()]:
            if candidate not in seen:
                seen.add(candidate)
                queue.append(candidate)
    require(seen == set(network["stations"]), "final U-Bahn graph is disconnected")

    by_label = defaultdict(list)
    for direction in network["directions"].values():
        by_label[network["routes"][direction["routeId"]]["label"]].append(direction)
    require(all(len(by_label[label]) == 2 for label in expected_labels), "each U-Bahn line must have two full directions")
    expected_termini = {
        "U1": {"Uhlandstr.", "Warschauer Str."},
        "U2": {"Pankow", "Ruhleben"},
        "U3": {"Krumme Lanke", "Warschauer Str."},
        "U4": {"Nollendorfplatz", "Innsbrucker Platz"},
        "U5": {"Hönow", "Berlin Hauptbahnhof"},
        "U6": {"Alt-Mariendorf", "Alt-Tegel"},
        "U7": {"Rathaus Spandau", "Rudow"},
        "U8": {"Wittenau", "Hermannstr."},
        "U9": {"Osloer Str.", "Rathaus Steglitz"},
    }
    for label, termini in expected_termini.items():
        actual = {network["stations"][direction["stations"][-1]]["name"] for direction in by_label[label]}
        require(actual == termini, f"unexpected {label} termini: {actual}")
    u6_patterns = by_label["U6"]
    require(all(len(direction["stations"]) == 29 for direction in u6_patterns), "full 29-station U6 was not restored")
    require(all(direction["stopPattern"].get("source") == "VBB 2021" for direction in u6_patterns), "U6 archive provenance missing")

    station_by_name = {station["name"]: sid for sid, station in network["stations"].items()}
    expected_interchanges = {
        "Alexanderplatz": {"U2", "U5", "U8"},
        "Nollendorfplatz": {"U1", "U2", "U3", "U4"},
        "Hermannplatz": {"U7", "U8"},
        "Unter den Linden": {"U5", "U6"},
    }
    for name, expected in expected_interchanges.items():
        services = network["stations"][station_by_name[name]]["services"]
        actual = {network["routes"][route_id]["label"] for route_id in services}
        require(expected <= actual, f"{name} missing expected services")

    router = build_data.Router(
        network["stations"], network["routes"], network["directions"], network["transfers"],
        network["routeTransfers"], network["metadata"]["waitSecondsByDirection"],
        network["metadata"]["waitSecondsByRoute"], network["canonicalStationIds"],
    )
    for left_name, right_name in [("Rathaus Spandau", "Hönow"), ("Pankow", "Rudow"), ("Krumme Lanke", "Wittenau")]:
        path = router.fastest_path(station_by_name[left_name], station_by_name[right_name])
        require(path, f"representative journey is unroutable: {left_name} to {right_name}")
        result = router.describe_path(path[0], path[1], station_by_name[left_name], station_by_name[right_name])
        require(result and result["totalSec"] > 0, f"journey description failed: {left_name} to {right_name}")
        print(f"journey {left_name} -> {right_name}: {round(result['totalSec'] / 60)} min, {len(result['legs'])} legs")
    print(f"Berlin U-Bahn valid: 9 lines, {len(network['stations'])} parent stations, {len(network['directions'])} scheduled patterns")


if __name__ == "__main__":
    main()
