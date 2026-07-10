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


def main() -> None:
    data = json.loads(DATA.read_text(encoding="utf-8"))
    verify_optimal_breakdowns(data)

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
