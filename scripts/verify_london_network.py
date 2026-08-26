#!/usr/bin/env python3
"""London integrity, source-timing, branch and representative-route checks."""

from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import build_data  # noqa: E402


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    build_data.configure_city("london")
    network = json.loads((ROOT / "public" / "data" / "london" / "network.json").read_text(encoding="utf-8"))
    audit = network["metadata"]["sourceAudit"]
    require(len(network["routes"]) == 12, "expected 11 Tube lines plus Elizabeth line")
    require(len(network["stations"]) == 315, "London station count changed")
    require(audit["runtimeSources"].get("fallback", 0) == 0, "ride-time fallbacks remain")
    require(audit["elizabethJourneySegments"] == 84, "Elizabeth segment coverage changed")
    require("940GZZLUWIG" not in network["routes"]["metropolitan"]["branches"], "invalid branch reference")
    for direction_id in network["routes"]["metropolitan"]["branches"]:
        require("940GZZLUWIG" not in network["directions"][direction_id]["stations"], "Metropolitan must not stop at Willesden Green")
    require(network["routes"]["elizabeth"]["color"] == "#60399E", "Elizabeth colour changed")
    require(network["transfers"].get("940GZZLUPAC", {}).get("910GPADTLL") == 180, "Paddington interchange missing")

    hatton_cross = "940GZZLUHNX"
    piccadilly_labels = {
        "Heathrow" if network["directions"][direction_id]["label"] in {"Heathrow Terminal 4", "Heathrow Terminal 5"}
        else network["directions"][direction_id]["label"]
        for direction_id in network["stations"][hatton_cross]["services"]["piccadilly"]
        if network["directions"][direction_id]["stations"].index(hatton_cross)
        < len(network["directions"][direction_id]["stations"]) - 1
    }
    require(piccadilly_labels == {"Cockfosters", "Heathrow"}, f"Hatton Cross direction groups changed: {piccadilly_labels}")

    equivalent_pairs = {
        frozenset((left, right))
        for group in network["stationEquivalents"]
        for left in group for right in group if left != right
    }
    name_coordinates: dict[tuple[str, float, float], list[str]] = defaultdict(list)
    for station_id, station in network["stations"].items():
        name_coordinates[(station["name"].casefold(), round(station["lat"], 5), round(station["lon"], 5))].append(station_id)
    for key, station_ids in name_coordinates.items():
        if len(station_ids) > 1:
            require(all(frozenset((left, right)) in equivalent_pairs for left in station_ids for right in station_ids if left != right), f"unlinked duplicate {key[0]}: {station_ids}")

    waits = network["metadata"]["waitSecondsByRoute"]
    for route_id, expected in {"victoria": 60, "central": 75, "circle": 300, "metropolitan": 135}.items():
        require(waits[route_id] == expected, f"{route_id} expected wait changed: {waits[route_id]}s")
    require(len(set(waits[r] for r in network["routes"] if r != "elizabeth")) > 3, "Tube waits look over-collapsed")

    router = build_data.Router(network["stations"], network["routes"], network["directions"], network["transfers"], network["routeTransfers"], network["metadata"]["waitSecondsByDirection"], network["metadata"]["waitSecondsByRoute"], network["canonicalStationIds"])
    require(
        router.combined_wait_seconds("circle:1", "circle", "940GZZLUHSC", "940GZZLULVT") == 150,
        "Circle/H&C shared corridor should combine two 10-minute headways into a 150s expected wait",
    )
    require(
        router.combined_wait_seconds("circle:1", "circle", "940GZZLUHSC", "940GZZLUALD") == 300,
        "Circle-only travel beyond Liverpool Street must keep the Circle wait",
    )
    checked = []

    def check_route(label: str, start: str, end: str, expected_lines: list[str], expected_seconds: int | None = None) -> dict:
        fastest = router.fastest_path(start, end)
        require(fastest is not None, f"{label} is not routable")
        route = router.describe_path(*fastest, start_station=start, end_station=end)
        lines = [step["line"] for step in route["steps"] if step["type"] == "ride"]
        require(lines == expected_lines, f"{label} chose {lines}, expected {expected_lines}")
        if expected_seconds is not None:
            require(route["totalSec"] == expected_seconds, f"{label} changed: {route['totalSec']}s")
        for step in route["steps"]:
            if step["type"] == "ride":
                direction = network["directions"][step["directionId"]]
                require(step["direction"] == direction["label"], f"{label} direction label mismatch")
                require(step["direction"] == network["stations"][direction["stations"][-1]]["name"], f"{label} direction is not the terminus")
        checked.append((label, route["totalSec"], lines))
        return route

    cases = [
        ("Bakerloo termini", "940GZZLUHAW", "940GZZLUEAC", ["Bakerloo"]),
        ("Central termini", "940GZZLUEPG", "940GZZLUWRP", ["Central"]),
        ("Circle routing", "940GZZLUERC", "940GZZLUBST", ["Circle"]),
        ("District Richmond branch", "940GZZLURMD", "940GZZLUTNG", ["District"]),
        ("District Wimbledon branch", "940GZZLUWIM", "940GZZLUECT", ["District"]),
        ("District Ealing branch", "940GZZLUEBY", "940GZZLUTNG", ["District"]),
        ("District Olympia branch", "940GZZLUKOY", "940GZZLUECT", ["District"]),
        ("District Upminster branch", "940GZZLUUPM", "940GZZLUTWH", ["District"]),
        ("Hammersmith shared service", "940GZZLUHSC", "940GZZLUGHK", ["Circle"]),
        ("Jubilee termini", "940GZZLUSTM", "940GZZLUSTD", ["Jubilee", "Elizabeth line"]),
        ("Metropolitan Amersham", "940GZZLUAMS", "940GZZLUBST", ["Metropolitan"]),
        ("Metropolitan Chesham", "940GZZLUCSM", "940GZZLUBST", ["Metropolitan"]),
        ("Metropolitan Watford", "940GZZLUWAF", "940GZZLUBST", ["Metropolitan"]),
        ("Metropolitan Uxbridge", "940GZZLUUXB", "940GZZLUBST", ["Metropolitan"]),
        ("Northern Edgware branch", "940GZZLUEGW", "940GZZLUCTN", ["Northern"]),
        ("Northern High Barnet branch", "940GZZLUHBT", "940GZZLUCTN", ["Northern"]),
        ("Northern Mill Hill East", "940GZZLUMHL", "940GZZLUFYC", ["Northern"]),
        ("Northern Charing Cross", "940GZZLUCHX", "940GZZBPSUST", ["Northern"]),
        ("Northern Bank", "940GZZLUBNK", "940GZZLUMDN", ["Northern"]),
        ("Piccadilly core", "940GZZLUCKS", "940GZZLUHSD", ["Piccadilly"]),
        ("Piccadilly Heathrow 4", "940GZZLUHR4", "940GZZLUHNX", ["Piccadilly"]),
        ("Piccadilly Heathrow 5", "940GZZLUHR5", "940GZZLUHNX", ["Piccadilly"]),
        ("Victoria termini", "940GZZLUBXN", "940GZZLUWWL", ["Victoria"]),
        ("Waterloo & City", "940GZZLUWLO", "940GZZLUBNK", ["Waterloo & City"], 330),
        ("Elizabeth Reading", "910GRDNGSTN", "910GPADTON", ["Elizabeth line"]),
        ("Elizabeth Shenfield", "910GSHENFLD", "910GLIVST", ["Elizabeth line"]),
        ("Elizabeth Abbey Wood", "910GABWDXR", "910GPADTLL", ["Elizabeth line"]),
        ("Elizabeth Heathrow 4", "910GHTRWTM4", "910GPADTON", ["Elizabeth line"]),
        ("Elizabeth Heathrow 5", "910GHTRWTM5", "910GPADTON", ["Elizabeth line"]),
    ]
    for case in cases:
        check_route(*case)

    # Circle and H&C publish the same Hammersmith-to-Edgware Road track. Circle
    # wins equal-cost ties in the router, so verify H&C's shared section at the
    # pattern/runtime level instead of pretending a transfer is required.
    circle = network["directions"]["circle:1"]
    hammersmith_city = network["directions"]["hammersmith-city:1"]
    shared_end = circle["stations"].index("940GZZLUERC")
    require(circle["stations"][: shared_end + 1] == hammersmith_city["stations"][: shared_end + 1], "Circle/H&C shared stations diverged")
    circle_shared = circle["runtimes"][:shared_end]
    hammersmith_shared = hammersmith_city["runtimes"][:shared_end]
    require(max(abs(a - b) for a, b in zip(circle_shared, hammersmith_shared)) <= 30, "Circle/H&C shared segment runtimes diverged")
    require(abs(sum(circle_shared) - sum(hammersmith_shared)) <= 30, "Circle/H&C shared total runtime diverged")

    paddington_bond = check_route("Paddington Tube to Bond Street Elizabeth", "940GZZLUPAC", "910GBONDST", ["Elizabeth line"], 510)
    require(paddington_bond["steps"][0]["type"] == "walk" and paddington_bond["steps"][0]["transferSec"] == 180, "Paddington hub transfer changed")
    check_route("Liverpool Street Tube to Canary Wharf Elizabeth", "940GZZLULVT", "910GCANWHRF", ["Elizabeth line"])
    check_route("Whitechapel Tube to Abbey Wood Elizabeth", "940GZZLUWPL", "910GABWDXR", ["Elizabeth line"])
    check_route("Canary Wharf Tube to Heathrow Elizabeth", "940GZZLUCYF", "910GHTRWTM5", ["Elizabeth line"])

    line_counts = Counter(line for _, _, lines in checked for line in lines)
    covered_lines = set(line_counts) | {"Hammersmith & City"}
    require(covered_lines == {route["label"] for route in network["routes"].values()}, "line QA coverage gap")
    print(f"London network verification passed: {len(checked)} representative routes")
    for label, seconds, lines in checked:
        print(f"{label}: {seconds}s via {' -> '.join(lines)}")
    print("route case counts:", dict(sorted(line_counts.items())))
    print("waits by route:", waits)
    print("runtime sources:", audit["runtimeSources"])


if __name__ == "__main__":
    main()
