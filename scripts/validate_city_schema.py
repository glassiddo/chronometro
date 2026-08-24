#!/usr/bin/env python3
"""Validate the normalized browser data contract for one configured city."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("city", nargs="?", default="paris")
    args = parser.parse_args()
    config = json.loads((ROOT / "config" / "cities" / f"{args.city}.json").read_text(encoding="utf-8"))
    network = json.loads((ROOT / config["paths"]["network"]).read_text(encoding="utf-8"))
    metadata = network.get("metadata", {})
    require(metadata.get("schemaVersion") == 1, "unsupported or missing schemaVersion")
    require(metadata.get("city", {}).get("id") == args.city, "city id mismatch")
    require(metadata.get("city", {}).get("timezone"), "missing city timezone")
    require(metadata.get("city", {}).get("attribution"), "missing attribution")
    require(metadata.get("modes"), "missing mode definitions")
    for route_id, route in network.get("routes", {}).items():
        require(route.get("mode") in metadata["modes"], f"{route_id} references unknown mode")
        require(route.get("color") and route.get("textColor"), f"{route_id} missing colours")
        require(route.get("branches"), f"{route_id} missing branch/direction references")
    for direction_id, direction in network.get("directions", {}).items():
        require(direction.get("routeId") in network["routes"], f"{direction_id} references unknown route")
        require(len(direction.get("stations", [])) >= 2, f"{direction_id} has fewer than two stops")
        require(len(direction["runtimes"]) == len(direction["stations"]) - 1, f"{direction_id} runtime count mismatch")
        require(direction.get("branchId") and direction.get("stopPattern"), f"{direction_id} missing stop-pattern data")
        require(all(station_id in network["stations"] for station_id in direction["stations"]), f"{direction_id} has unknown station")
    for station_id, station in network.get("stations", {}).items():
        require(station.get("id") == station_id and station.get("name"), f"invalid station {station_id}")
        require(station.get("complexId"), f"{station_id} missing station-complex id")
    require(network.get("transfers") is not None, "missing walking/transfer connections")
    require(network.get("stationEquivalents") is not None, "missing station complexes")
    print(
        f"{args.city} schema valid: {len(network['stations'])} stations, "
        f"{len(network['routes'])} lines, {len(network['directions'])} stop patterns"
    )


if __name__ == "__main__":
    main()
