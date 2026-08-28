#!/usr/bin/env python3
"""Verify WMATA Metrorail topology, normalization, transfers, and journeys."""

from __future__ import annotations

import csv
import json
import re
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
    build_data.configure_city("washington-dc")
    network = json.loads((ROOT / "public/data/washington-dc/network.json").read_text(encoding="utf-8"))
    expected = {"RED", "BLUE", "ORANGE", "SILVER", "YELLOW", "GREEN"}
    require(set(network["routes"]) == expected, "network must contain exactly six Metrorail routes")
    require(all(route["routeType"] == "1" for route in network["routes"].values()), "non-Metrorail route included")

    raw_stops = {
        row["stop_id"]: row
        for row in csv.DictReader((ROOT / "gouv_washington_dc_gtfs-export/stops.txt").open(encoding="utf-8-sig"))
    }
    require(len(network["stations"]) == 98, "unexpected WMATA passenger-station count")
    require(all(raw_stops[sid].get("location_type") == "1" for sid in network["stations"]), "child/platform stop leaked into playable stations")
    require(all(not re.search(r"\b(?:north|south|east|west)bound\b|\bplatform\b|\btrack\s+\d+\b", station["name"], re.I) for station in network["stations"].values()), "direction/platform suffix leaked into a station name")

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
    require(seen == set(network["stations"]), "final playable Metrorail graph is disconnected")

    by_route = defaultdict(list)
    for direction in network["directions"].values():
        by_route[direction["routeId"]].append(direction)
    require(len(by_route["SILVER"]) == 2, "temporary/exceptional Silver pattern survived")
    require(all(item["stations"][-1] != "STN_D13" for item in by_route["SILVER"]), "Silver incorrectly terminates at New Carrollton")
    require(any("STN_N10" in item["stations"] and "STN_N12" in item["stations"] for item in by_route["SILVER"]), "Silver Phase 2/Dulles/Ashburn missing")
    require({item["stations"][-1] for item in by_route["YELLOW"]} == {"STN_E10", "STN_C15"}, "Yellow scheduled Greenbelt/Huntington pattern missing")

    def edges(route_id: str) -> set[frozenset[str]]:
        return {frozenset((a, b)) for item in by_route[route_id] for a, b in zip(item["stations"], item["stations"][1:])}

    require(len(edges("BLUE") & edges("ORANGE") & edges("SILVER")) >= 5, "Blue/Orange/Silver shared infrastructure missing")
    require(len(edges("BLUE") & edges("YELLOW")) >= 4, "Blue/Yellow shared infrastructure missing")
    require(len(edges("GREEN") & edges("YELLOW")) >= 5, "Green/Yellow shared infrastructure missing")
    for station_id in ["STN_A15", "STN_B11", "STN_J03", "STN_G05", "STN_K08", "STN_D13", "STN_C15", "STN_E10", "STN_F11", "STN_N12"]:
        require(station_id in seen and adjacency[station_id], f"terminal branch unreachable: {station_id}")

    require(network["transfers"] == {"STN_A02": {"STN_C03": 300}, "STN_C03": {"STN_A02": 300}}, "only documented Farragut Crossing should link distinct stations")

    router = build_data.Router(
        network["stations"], network["routes"], network["directions"], network["transfers"],
        network["routeTransfers"], network["metadata"]["waitSecondsByDirection"],
        network["metadata"]["waitSecondsByRoute"], network["canonicalStationIds"],
    )
    station_by_name = {station["name"]: sid for sid, station in network["stations"].items()}
    checks = [
        ("Shady Grove", "Glenmont"),
        ("Ashburn", "Downtown Largo"),
        ("Vienna", "New Carrollton"),
        ("Franconia-Springfield", "Downtown Largo"),
        ("Huntington", "Greenbelt"),
        ("Branch Av", "Greenbelt"),
        ("Washington Dulles International Airport", "Metro Center"),
        ("Rosslyn", "Stadium-Armory"),
        ("Pentagon", "L'Enfant Plaza"),
        ("Fort Totten", "Gallery Place"),
        ("Ashburn", "Branch Av"),
    ]
    for left_name, right_name in checks:
        left, right = station_by_name[left_name], station_by_name[right_name]
        path = router.fastest_path(left, right)
        require(path, f"representative journey is unroutable: {left_name} -> {right_name}")
        first = router.describe_path(path[0], path[1], left, right)
        second = router.describe_path(path[0], path[1], left, right)
        require(first == second and first and first["totalSec"] > 0, "stored route timing is not deterministic")
        require(first["totalSec"] == sum(step["elapsedSec"] for step in first["steps"]), "stored total does not equal replayed step total")
        route_names = "/".join(network["routes"][leg["routeId"]]["label"] for leg in first["legs"])
        print(f"journey {left_name} -> {right_name}: {round(first['totalSec'] / 60)} min via {route_names}")

    daily = json.loads((ROOT / "public/data/washington-dc/daily/index.json").read_text(encoding="utf-8"))
    require(daily["dates"][0] == "2026-08-29" and daily["dates"][-1] == "2026-12-31", "Washington daily range endpoints are wrong")
    require(len(daily["dates"]) == 125, "Washington daily range must contain exactly 125 dates")
    print(f"Washington network valid: 6 routes, {len(network['stations'])} parent stations, {len(network['directions'])} scheduled patterns")


if __name__ == "__main__":
    main()
