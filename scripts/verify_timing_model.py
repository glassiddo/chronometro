#!/usr/bin/env python3
"""Verify key deterministic transfer/wait timing rules in the generated bundle."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "public" / "data" / "metro-express-data.json"
APP = ROOT / "public" / "app.js"
BUILD = ROOT / "scripts" / "build_data.py"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def route_transfer(data: dict, from_station: str, to_station: str, from_route: str, to_route: str) -> int | None:
    return (
        data.get("routeTransfers", {})
        .get(from_station, {})
        .get(to_station, {})
        .get(from_route, {})
        .get(to_route)
    )


def canonical_station_id(data: dict, station_id: str) -> str:
    return data.get("canonicalStationIds", {}).get(station_id, station_id)


def same_station(data: dict, left_id: str, right_id: str) -> bool:
    return canonical_station_id(data, left_id) == canonical_station_id(data, right_id)


def verify_optimal_breakdowns(data: dict) -> None:
    for puzzle in data["puzzles"]:
        optimal = puzzle["optimalRoute"]
        route_total = optimal["rideSec"] + optimal["waitSec"] + optimal["transferSec"]
        require(
            optimal["totalSec"] == route_total,
            f"{puzzle['id']} optimal total mismatch: {optimal['totalSec']} != {route_total}",
        )
        for index, leg in enumerate(optimal["legs"], start=1):
            leg_total = leg["rideSec"] + leg["waitSec"] + leg["transferSec"]
            require(
                leg["elapsedSec"] == leg_total,
                f"{puzzle['id']} leg {index} elapsed mismatch: {leg['elapsedSec']} != {leg_total}",
            )


def verify_station_equivalents(data: dict) -> None:
    equivalents = data.get("stationEquivalents", [])
    canonical_ids = data.get("canonicalStationIds", {})
    require(equivalents, "missing station equivalence groups")
    require(canonical_ids, "missing canonical station id map")

    jules_joffrin_station = "PARIS166071"
    jules_joffrin_stop = "PARIS174244"
    require(
        same_station(data, jules_joffrin_station, jules_joffrin_stop),
        "Jules Joffrin near-duplicate ids should be station-equivalent",
    )

    metro_malesherbes = "PARIS9551"
    rer_malesherbes = "ITOAUTO77191"
    require(
        not same_station(data, metro_malesherbes, rer_malesherbes),
        "far-apart Malesherbes stations must not be station-equivalent",
    )


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    verify_optimal_breakdowns(data)
    verify_station_equivalents(data)

    chatelet = route_transfer(data, "PARIS208683", "PARIS208683", "8562", "15061")
    daumesnil = route_transfer(data, "ITOAUTO79148", "ITOAUTO79148", "15093", "15215")
    require(chatelet == 360, f"Chatelet Line 11 -> Line 4 should be 360s, got {chatelet!r}")
    require(daumesnil == 180, f"Daumesnil Line 8 -> Line 6 should be 180s, got {daumesnil!r}")

    metadata = data["metadata"]
    require(metadata.get("waitSecondsByDirection"), "missing direction-level waits")
    require(metadata.get("waitSecondsByRoute"), "missing route-level waits")
    require(metadata.get("waitSecondsByMode"), "missing mode-level wait fallbacks")

    app = APP.read_text(encoding="utf-8")
    build = BUILD.read_text(encoding="utf-8")
    require("waitSecondsByDirection" in app and "waitSecondsByRoute" in app, "frontend does not use derived waits")
    require("routeTransfers" in app and "transferFallback" in app, "frontend does not use route transfer fallback rules")
    require("routeTimingTotals" in app and "rideSec" in app, "frontend does not expose timing breakdowns")
    require("function canonicalStationId(" in app and "function sameStation(" in app, "frontend lacks canonical station helpers")
    require("sameStation(toStation, currentPuzzle().end)" in app, "frontend completion still uses raw station ids")
    require("sameStation(stationId, currentPuzzle().end)" in app, "frontend destination labels still use raw station ids")
    require("canonical_station_ids, station_equivalents = build_station_equivalents(" in build, "backend does not emit station equivalences")
    require("wait_by_direction.get(" in build and "wait_by_route.get(" in build, "backend wait fallback order changed")
    require("self.route_transfers.get(" in build and "fallback_transfer" in build, "backend transfer fallback order changed")
    require('"rideSec": totals["rideSec"]' in build, "backend does not emit timing breakdowns")

    print("timing model verification passed")
    print(f"verified timing breakdowns for {len(data['puzzles'])} puzzles")
    print(f"Chatelet Line 11 -> Line 4: {chatelet}s")
    print(f"Daumesnil Line 8 -> Line 6: {daumesnil}s")
    print(
        "wait tables:",
        f"{len(metadata['waitSecondsByDirection'])} directions,",
        f"{len(metadata['waitSecondsByRoute'])} routes",
    )


if __name__ == "__main__":
    main()
