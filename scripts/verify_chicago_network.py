#!/usr/bin/env python3
"""Verify CTA ‘L’-specific topology and normalization invariants."""

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
    build_data.configure_city("chicago")
    network_path = ROOT / "public/data/chicago/network.json"
    network = json.loads(network_path.read_text(encoding="utf-8"))
    expected = {"Red", "Blue", "Brn", "G", "Org", "Pink", "P", "Y"}
    require(set(network["routes"]) == expected, "network must contain exactly the eight CTA ‘L’ routes")
    require(all(route["routeType"] == "1" for route in network["routes"].values()), "non-rail route included")

    raw_stops = {
        row["stop_id"]: row
        for row in csv.DictReader((ROOT / "gouv_chicago_gtfs-export/stops.txt").open(encoding="utf-8-sig"))
    }
    require(len(network["stations"]) == 143, "unexpected playable parent-station count")
    require(all(raw_stops[sid].get("location_type") == "1" for sid in network["stations"]), "platform leaked into playable stations")

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
    require(seen == set(network["stations"]), "final station graph is disconnected")

    by_route = defaultdict(list)
    for direction in network["directions"].values():
        by_route[direction["routeId"]].append(direction)
    require(len(by_route["G"]) == 4, "Green branches/directions were not preserved")
    require(len(by_route["P"]) == 3, "Purple local and Loop Express patterns were not preserved")
    purple_lengths = sorted(len(item["stations"]) for item in by_route["P"])
    require(purple_lengths == [9, 9, 43], "unexpected Purple local/express topology")
    require(all(len(item["stations"]) >= 3 for items in by_route.values() for item in items), "exceptional one-stop branch survived")

    station_by_name = {item["name"]: sid for sid, item in network["stations"].items()}
    shared = [station_by_name[name] for name in ("Ashland (Green/Pink)", "Morgan (Green/Pink)", "Clinton (Green/Pink)")]
    for sid in shared:
        services = network["stations"][sid]["services"]
        require({"G", "Pink"} <= set(services), f"Green/Pink shared station missing both services: {sid}")
    loop_routes = {rid for rid in ("Brn", "Org", "Pink", "P") if any(d["stations"][0] == d["stations"][-1] for d in by_route[rid])}
    require(loop_routes == {"Brn", "Org", "Pink", "P"}, "Loop patterns are incomplete")

    router = build_data.Router(
        network["stations"], network["routes"], network["directions"], network["transfers"],
        network["routeTransfers"], network["metadata"]["waitSecondsByDirection"],
        network["metadata"]["waitSecondsByRoute"], network["canonicalStationIds"],
    )
    checks = [("O'Hare", "95th/Dan Ryan"), ("Dempster-Skokie", "Midway"), ("Linden", "Cottage Grove")]
    for left_name, right_name in checks:
        left = station_by_name[left_name]
        right = station_by_name[right_name]
        path = router.fastest_path(left, right)
        require(path, f"representative journey is unroutable: {left_name} to {right_name}")
        result = router.describe_path(path[0], path[1], left, right)
        require(result and result["totalSec"] > 0, f"journey description failed: {left_name} to {right_name}")
        print(f"journey {left_name} -> {right_name}: {round(result['totalSec'] / 60)} min, {len(result['legs'])} legs")
    print(f"Chicago network valid: 8 routes, {len(network['stations'])} parent stations, {len(network['directions'])} scheduled patterns")


if __name__ == "__main__":
    main()
