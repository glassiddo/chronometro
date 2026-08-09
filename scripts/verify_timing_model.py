#!/usr/bin/env python3
"""Verify key deterministic transfer/wait timing rules in the generated bundle."""

from __future__ import annotations

import json
import math
import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "public" / "data" / "metro-express-network.json"
DAILY_INDEX = ROOT / "public" / "data" / "daily" / "index.json"
DAILY_DIR = ROOT / "public" / "data" / "daily"
APP = ROOT / "public" / "app.js"
BUILD = ROOT / "scripts" / "build_data.py"
DAILY_PUZZLE_COUNT = 5
MIN_PUZZLE_ROUTE_DISTANCE_M = 1000
MIN_PUZZLE_ENDPOINT_DISTANCE_M = 1500


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def load_current_daily_bundle() -> dict:
    network = json.loads(NETWORK.read_text(encoding="utf-8"))
    daily_index = json.loads(DAILY_INDEX.read_text(encoding="utf-8"))
    puzzles = []
    for day in daily_index["dates"]:
        daily = json.loads((DAILY_DIR / f"{day}.json").read_text(encoding="utf-8"))
        require(
            len(daily["puzzles"]) == DAILY_PUZZLE_COUNT,
            f"{day} expected {DAILY_PUZZLE_COUNT} daily puzzles, got {len(daily['puzzles'])}",
        )
        puzzles.extend(daily["puzzles"])
    data = dict(network)
    data["puzzles"] = puzzles
    data["dailyDates"] = daily_index["dates"]
    return data


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


def station_distance_m(left: dict, right: dict) -> float:
    radius_m = 6_371_000
    phi1 = math.radians(left["lat"])
    phi2 = math.radians(right["lat"])
    d_phi = math.radians(right["lat"] - left["lat"])
    d_lambda = math.radians(right["lon"] - left["lon"])
    hav = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_m * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def station_public_lines(data: dict, station_id: str) -> set[tuple[str, str]]:
    return {
        (data["routes"][route_id]["mode"], data["routes"][route_id]["label"])
        for route_id in data["stations"][station_id].get("services", {})
        if route_id in data["routes"]
    }


def optimal_route_edge_count(data: dict, optimal_route: dict) -> int:
    edge_count = 0
    for leg in optimal_route["legs"]:
        for segment in leg.get("segments") or [leg]:
            stations = data["directions"][segment["directionId"]]["stations"]
            from_index = stations.index(segment["from"])
            to_index = stations.index(segment["to"])
            edge_count += to_index - from_index
    return edge_count


def optimal_route_distance_m(data: dict, optimal_route: dict) -> float:
    total = 0.0
    for leg in optimal_route["legs"]:
        for segment in leg.get("segments") or [leg]:
            direction_stations = data["directions"][segment["directionId"]]["stations"]
            from_index = direction_stations.index(segment["from"])
            to_index = direction_stations.index(segment["to"])
            for left_id, right_id in zip(
                direction_stations[from_index:to_index],
                direction_stations[from_index + 1 : to_index + 1],
            ):
                total += station_distance_m(data["stations"][left_id], data["stations"][right_id])
    return total


def verify_puzzle_pool_constraints(data: dict) -> None:
    expected_puzzle_count = len(data["dailyDates"]) * DAILY_PUZZLE_COUNT
    require(
        len(data["puzzles"]) == expected_puzzle_count,
        f"expected {expected_puzzle_count} puzzles, got {len(data['puzzles'])}",
    )
    for puzzle in data["puzzles"]:
        optimal = puzzle["optimalRoute"]
        endpoint_distance_m = station_distance_m(data["stations"][puzzle["start"]], data["stations"][puzzle["end"]])
        require(
            endpoint_distance_m >= MIN_PUZZLE_ENDPOINT_DISTANCE_M,
            f"{puzzle['id']} endpoints are only {endpoint_distance_m:.1f}m apart",
        )
        shared_lines = station_public_lines(data, puzzle["start"]) & station_public_lines(data, puzzle["end"])
        require(not shared_lines, f"{puzzle['id']} endpoints share public lines: {sorted(shared_lines)}")
        edge_count = optimal_route_edge_count(data, optimal)
        require(edge_count > 3, f"{puzzle['id']} optimal route has only {edge_count} edges")
        distance_m = optimal_route_distance_m(data, optimal)
        require(
            distance_m >= MIN_PUZZLE_ROUTE_DISTANCE_M,
            f"{puzzle['id']} optimal route is only {distance_m:.1f}m",
        )


def verify_optimal_breakdowns(data: dict) -> None:
    for puzzle in data["puzzles"]:
        optimal = puzzle["optimalRoute"]
        steps = optimal.get("steps")
        require(steps, f"{puzzle['id']} missing optimalRoute.steps")
        public_lines = [
            (step.get("mode"), step.get("line"))
            for step in optimal.get("legs", [])
            if step.get("type", "ride") == "ride"
        ]
        require(
            len(public_lines) == len(set(public_lines)),
            f"{puzzle['id']} repeats a public line in optimal route: {public_lines}",
        )
        route_total = optimal["rideSec"] + optimal["waitSec"] + optimal["transferSec"]
        require(
            optimal["totalSec"] == route_total,
            f"{puzzle['id']} optimal total mismatch: {optimal['totalSec']} != {route_total}",
        )
        step_elapsed = sum(step["elapsedSec"] for step in steps)
        require(
            optimal["totalSec"] == step_elapsed,
            f"{puzzle['id']} step total mismatch: {optimal['totalSec']} != {step_elapsed}",
        )
        for key in ("rideSec", "waitSec", "transferSec"):
            step_total = sum(step[key] for step in steps)
            require(
                optimal[key] == step_total,
                f"{puzzle['id']} {key} step mismatch: {optimal[key]} != {step_total}",
            )
        require(steps[0]["from"] == puzzle["start"], f"{puzzle['id']} first step does not start at puzzle start")
        require(
            steps[-1]["to"] == puzzle["end"] or same_station(data, steps[-1]["to"], puzzle["end"]),
            f"{puzzle['id']} last step does not end at destination or equivalent station",
        )
        if steps[-1].get("type") == "walk":
            require(
                not same_station(data, steps[-1]["from"], steps[-1]["to"]),
                f"{puzzle['id']} ends with a walk between equivalent stations",
            )
        first_ride = next((step for step in steps if step.get("type", "ride") == "ride"), None)
        require(first_ride is not None, f"{puzzle['id']} has no ride step")
        if first_ride["from"] != puzzle["start"]:
            require(
                steps[0].get("type") == "walk" and steps[0]["to"] == first_ride["from"],
                f"{puzzle['id']} first ride starts away from puzzle start without explicit walk",
            )
        last_ride = next((step for step in reversed(steps) if step.get("type", "ride") == "ride"), None)
        if last_ride["to"] != puzzle["end"] and not same_station(data, last_ride["to"], puzzle["end"]):
            require(
                steps[-1].get("type") == "walk" and steps[-1]["from"] == last_ride["to"],
                f"{puzzle['id']} final ride ends away from puzzle end without explicit walk",
            )
        for index, step in enumerate(steps, start=1):
            step_total = step["rideSec"] + step["waitSec"] + step["transferSec"]
            require(
                step["elapsedSec"] == step_total,
                f"{puzzle['id']} step {index} elapsed mismatch: {step['elapsedSec']} != {step_total}",
            )
            if step.get("type") == "walk" and step["from"] != step["to"]:
                require(step["rideSec"] == 0 and step["waitSec"] == 0, f"{puzzle['id']} walk step {index} has ride/wait time")


def verify_auteuil_case_if_present(data: dict) -> None:
    for puzzle in data["puzzles"]:
        start_name = data["stations"][puzzle["start"]]["name"]
        end_name = data["stations"][puzzle["end"]]["name"]
        if start_name != "Église d'Auteuil" or end_name != "Saint-Marcel":
            continue
        steps = puzzle["optimalRoute"]["steps"]
        first = steps[0]
        require(first.get("type") == "walk", "Église d'Auteuil -> Saint-Marcel must start with an explicit walk")
        require(data["stations"][first["to"]]["name"] == "Mirabeau", "initial walk should go to Mirabeau")
        require(330 <= first["transferSec"] <= 410, f"Mirabeau walk should be around 368s, got {first['transferSec']}")
        return


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


def verify_route_continuations(data: dict) -> None:
    continuations = data.get("routeContinuations", [])
    expected = {
        "routeId": "8567",
        "stationId": "PARIS166100",
        "fromDirectionId": "8567:0",
        "toDirectionId": "8567:1",
    }
    require(expected in continuations, f"missing 7bis route continuation: {expected}")

    segment_route = {
        "legs": [
            {
                "routeId": "8567",
                "line": "7bis",
                "mode": "metro",
                "directionId": "8567:0",
                "from": "PARIS9701",
                "to": "PARIS166033",
                "segments": [
                    {"directionId": "8567:0", "from": "PARIS9701", "to": "PARIS166100"},
                    {"directionId": "8567:1", "from": "PARIS166100", "to": "PARIS166033"},
                ],
            }
        ]
    }
    require(optimal_route_edge_count(data, segment_route) == 2, "7bis loop continuation should count two ride edges")

    spec = importlib.util.spec_from_file_location("build_data", BUILD)
    build_data = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(build_data)
    router = build_data.Router(
        data["stations"],
        data["routes"],
        data["directions"],
        data["transfers"],
        data["routeTransfers"],
        data["metadata"].get("waitSecondsByDirection", {}),
        data["metadata"].get("waitSecondsByRoute", {}),
        data.get("canonicalStationIds", {}),
    )
    fastest = router.fastest_path("PARIS9701", "PARIS166033")
    route = router.describe_path(*fastest, start_station="PARIS9701", end_station="PARIS166033") if fastest else None
    require(route is not None, "Place des Fêtes -> Danube should be routable")
    require(len(route["legs"]) == 1, f"Place des Fêtes -> Danube should be one 7bis ride, got {route['legs']}")
    leg = route["legs"][0]
    require(leg["line"] == "7bis", f"Place des Fêtes -> Danube should use 7bis, got {leg['line']}")
    require(leg["from"] == "PARIS9701" and leg["to"] == "PARIS166033", "7bis continuation endpoints changed")
    require(leg["rideSec"] == 165, f"7bis continuation ride should be 165s, got {leg['rideSec']}")
    require(leg["transferSec"] == 0, f"7bis continuation must not charge transfer, got {leg['transferSec']}")
    require(route["transferSec"] == 0, f"Place des Fêtes -> Danube total transfer should be 0, got {route['transferSec']}")


def main() -> None:
    data = load_current_daily_bundle()
    verify_puzzle_pool_constraints(data)
    verify_optimal_breakdowns(data)
    verify_auteuil_case_if_present(data)
    verify_station_equivalents(data)
    verify_route_continuations(data)

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
    require("function addWalkStep(" in app and "walk:" in app, "frontend does not expose explicit walk steps")
    require('"steps": steps' in build, "backend does not emit route steps")
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
