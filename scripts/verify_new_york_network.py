#!/usr/bin/env python3
"""Verify NYC Subway scope, topology, complexes, and transfer-time precedence."""

from __future__ import annotations

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
    build_data.configure_city("new-york")
    network = json.loads((ROOT / "public/data/new-york/network.json").read_text(encoding="utf-8"))
    expected = {
        "1", "2", "3", "4", "5", "6", "6X", "7", "7X",
        "A", "B", "C", "D", "E", "F", "FX", "G", "J", "Z", "L", "M",
        "N", "Q", "R", "W", "GS", "FS", "H",
    }
    require(set(network["routes"]) == expected, "NYC route allowlist mismatch")
    require("SI" not in network["routes"], "Staten Island Railway must remain excluded")
    require(len(network["stations"]) == 475, "unexpected subway constituent-station count")

    by_route: dict[str, list[dict]] = defaultdict(list)
    adjacency: dict[str, set[str]] = defaultdict(set)
    for direction in network["directions"].values():
        by_route[direction["routeId"]].append(direction)
        for left, right in zip(direction["stations"], direction["stations"][1:]):
            adjacency[left].add(right)
            adjacency[right].add(left)
    for left, destinations in network["transfers"].items():
        for right in destinations:
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
    require(seen == set(network["stations"]), "subway graph is disconnected")

    for route_id, station_count in {"GS": 2, "FS": 4, "H": 5}.items():
        require(len(by_route[route_id]) == 2, f"{route_id} must have two directions")
        require({len(item["stations"]) for item in by_route[route_id]} == {station_count}, f"{route_id} station pattern changed")
    require({item["stations"][-1] for item in by_route["A"]} >= {"A02", "A65", "H11"}, "A branches missing")
    require(all(network["routes"][rid]["label"] == base for rid, base in {"6X": "6", "7X": "7", "FX": "F"}.items()), "express public labels changed")

    canonical = network["canonicalStationIds"]
    require(canonical.get("R16") == canonical.get("127"), "Times Square complex was not normalized")
    require(canonical.get("A38") == canonical.get("229"), "Fulton Street complex was not normalized")
    metadata = network["metadata"]
    router = build_data.Router(
        network["stations"], network["routes"], network["directions"], network["transfers"],
        network["routeTransfers"], metadata["waitSecondsByDirection"],
        metadata["waitSecondsByRoute"], canonical,
    )
    require(router.transfer_walk("128", "128", "1", "2", "subway", "subway") == 300, "GTFS same-station time did not override fallback")
    require(router.transfer_walk("127", "A27", "1", "A", "subway", "subway") == 300, "GTFS complex transfer time missing")
    print(f"New York network valid: {len(network['routes'])} services, {len(network['stations'])} constituent stations, {len(network['stationEquivalents'])} official multi-station complexes")


if __name__ == "__main__":
    main()
