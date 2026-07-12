#!/usr/bin/env python3
"""Print the targeted Église d'Auteuil -> Saint-Marcel route for manual QA."""

from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD = ROOT / "scripts" / "build_data.py"


def ascii_name(value: str) -> str:
    return value.encode("ascii", "backslashreplace").decode()


def main() -> None:
    spec = importlib.util.spec_from_file_location("build_data", BUILD)
    build_data = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(build_data)

    routes = build_data.read_routes()
    stop_to_station, all_station_meta = build_data.read_stops()
    weekday_services = build_data.read_weekday_services()
    trips = build_data.read_trips(routes)
    (
        segment_stats,
        pattern_counts,
        pattern_headsigns,
        pattern_peak_departures,
        raw_stop_routes,
    ) = build_data.read_stop_times(trips, stop_to_station, weekday_services)
    directions, used_stations, direction_pattern_keys = build_data.choose_patterns(
        routes, all_station_meta, segment_stats, pattern_counts, pattern_headsigns, pattern_peak_departures
    )
    stations = {station_id: all_station_meta[station_id] for station_id in sorted(used_stations)}
    build_data.build_station_services(stations, routes, directions)
    transfers = build_data.read_transfers(stop_to_station, set(stations))
    used_routes = sorted({direction["routeId"] for direction in directions.values()})
    routes = {route_id: routes[route_id] for route_id in used_routes}
    wait_by_direction, wait_by_route = build_data.build_waits(
        directions, routes, direction_pattern_keys, pattern_peak_departures
    )
    route_transfers = build_data.read_route_transfers(stop_to_station, raw_stop_routes, routes, set(stations))

    router = build_data.Router(stations, routes, directions, transfers, route_transfers, wait_by_direction, wait_by_route)
    start = next(station_id for station_id, station in stations.items() if station["name"] == "Église d'Auteuil")
    end = next(station_id for station_id, station in stations.items() if station["name"] == "Saint-Marcel")
    route = router.describe_path(*router.fastest_path(start, end))
    print(start, "->", end, route["totalSec"], route["signature"])
    for step in route["steps"]:
        print(
            step.get("type", "ride"),
            ascii_name(stations[step["from"]]["name"]),
            "->",
            ascii_name(stations[step["to"]]["name"]),
            "transfer",
            step["transferSec"],
            "wait",
            step["waitSec"],
            "ride",
            step["rideSec"],
            "elapsed",
            step["elapsedSec"],
        )


if __name__ == "__main__":
    main()
