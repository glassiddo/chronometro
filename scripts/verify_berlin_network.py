#!/usr/bin/env python3
"""Verify Berlin regular U/S-Bahn topology, geography, service and routing."""

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
    daily_dir = ROOT / "public/data/berlin/daily"
    dates = json.loads((daily_dir / "index.json").read_text(encoding="utf-8"))["dates"]
    require(len(dates) == 27 and dates[0] == "2026-10-05" and dates[-1] == "2026-10-31", "Berlin active calendar must cover October 5–31")
    build_data.configure_city("berlin")
    network_path = ROOT / "public/data/berlin/network.json"
    network = json.loads(network_path.read_text(encoding="utf-8"))
    u_labels = {f"U{number}" for number in range(1, 10)}
    s_labels = {"S1", "S15", "S2", "S25", "S26", "S3", "S41", "S42", "S46", "S47", "S5", "S7", "S75", "S8", "S85", "S9"}
    expected_labels = u_labels | s_labels
    labels = {route["label"] for route in network["routes"].values()}
    require(labels == expected_labels and len(network["routes"]) == 25, "expected 9 U-Bahn and 16 regular S-Bahn lines without duplicate public routes")
    require(all(route["routeType"] == ("400" if route["mode"] == "ubahn" else "109") for route in network["routes"].values()), "unexpected route type")

    raw_stops = {}
    for directory in ("gouv_berlin_vbb_gtfs-export", "gouv_berlin_vbb_gtfs-archive-2021"):
        raw_stops.update({
            row["stop_id"]: row
            for row in csv.DictReader((ROOT / directory / "stops.txt").open(encoding="utf-8-sig"))
        })
    require(len(network["stations"]) == 316, "unexpected parent-station count")
    require(sum("ubahn" in s["modes"] for s in network["stations"].values()) == 175, "U-Bahn coverage changed")
    require(sum("sbahn" in s["modes"] for s in network["stations"].values()) == 168, "S-Bahn coverage incomplete")
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
    require(all(len(by_label[label]) == 2 for label in u_labels), "each U-Bahn line must have two full directions")
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
    def station(name):
        return station_by_name[name]

    for label, clockwise in [("S41", True), ("S42", False)]:
        require(len(by_label[label]) == 1, f"{label} must have only its real ring direction")
        direction = by_label[label][0]
        ring = direction["stations"][:27]
        require(len(set(ring)) == 27 and direction["stations"] == ring * 2, f"{label} loop coverage")
        # Independent geographic orientation check (longitude/latitude signed area).
        coords = [(network["stations"][sid]["lon"], network["stations"][sid]["lat"]) for sid in ring]
        area = sum(x1*y2-x2*y1 for (x1,y1),(x2,y2) in zip(coords,coords[1:]+coords[:1]))
        require((area < 0) == clockwise, f"{label} runs in the wrong direction")
        require(56*60 <= sum(direction["runtimes"][:27]) <= 63*60, f"{label} lap should be approximately 59 minutes including dwell")
        require(router.runtime_between(direction["id"], ring[-1], ring[1]) == sum(direction["runtimes"][26:28]), f"{label} seam adds a transfer or loses runtime")

    for line in ["S1", "S25", "S85"]:
        for direction in by_label[line]:
            ids = direction["stations"]
            for left, right in zip(ids, ids[1:]):
                require({left, right} != {station("Bornholmer Str."), station("Schönholz")}, f"{line} still skips Wollankstraße")
    require(any([station("Berlin Hauptbahnhof"), station("Wedding"), station("Gesundbrunnen")] == d["stations"] for d in by_label["S15"]), "S15 must run via Wedding")
    require(any(d["stations"][-1] == station("Blankenburg") for d in by_label["S26"]), "S26 north branch")
    require(any(d["stations"][-1] == station("Südkreuz") for d in by_label["S47"]), "S47 full extension")
    for terminal in ["Frohnau", "Pankow", "Waidmannslust"]:
        require(any(d["stations"][-1] == station(terminal) for d in by_label["S85"]), f"S85 missing {terminal} branch")

    for name in ["Flughafen BER", "Potsdam Hauptbahnhof", "Hennigsdorf", "Oranienburg", "Bernau", "Erkner", "Teltow Stadt", "Eichwalde", "Mahlow"]:
        require(not build_data.is_puzzle_endpoint(network["stations"][station(name)]), f"outside endpoint: {name}")
    for name in ["Ahrensfelde", "Heiligensee", "Frohnau", "Wannsee", "Rahnsdorf", "Grünbergallee"]:
        require(build_data.is_puzzle_endpoint(network["stations"][station(name)]), f"Berlin endpoint excluded: {name}")
    # Inside the former rectangle, outside the actual state: prevents bbox regressions.
    require(not build_data.SOURCE_ADAPTER.is_within_puzzle_boundary({"lat":52.40,"lon":13.10}), "boundary filter reverted to a bounding box")
    for left, right in [("Spandau","Rathaus Spandau"),("Charlottenburg","Wilmersdorfer Str."),("Messe Nord/ZOB","Kaiserdamm"),("Yorckstr. (Großgörschenstr.)","Yorckstr.")]:
        require(network["transfers"][station(left)][station(right)] == 300, f"missing interchange {left}")
        require(network["transfers"][station(right)][station(left)] == 300, f"missing reverse interchange {left}")
        require(network["canonicalStationIds"][station(left)] != network["canonicalStationIds"][station(right)], "walk improperly merged parent stations")

    def wait(line, start, end):
        left, right = station(start), station(end)
        values = [router.combined_wait_seconds(d["id"], d["routeId"], left, right)
            for d in by_label[line] if router.runtime_between(d["id"], left, right) is not None]
        require(bool(values), f"missing test ride: {line} {start} -> {end}")
        return min(values)
    require(wait("S25", "Bornholmer Str.", "Teltow Stadt") == 300, "S25/S26 whole-ride shared frequency")
    require(wait("S1", "Oranienburg", "Wannsee") == 600, "peak short turns must not inflate the full S1 frequency")
    require(wait("S1", "Frohnau", "Wannsee") == 300, "S1 regular peak trains should combine")
    require(wait("S1", "Zehlendorf", "Potsdamer Platz") == 150, "S1 central peak overlays")
    require(wait("S8", "Grünau", "Birkenwerder") == 600, "S8 alternative termini must not double frequency")
    require(wait("S85", "Flughafen BER", "Schönhauser Allee") == 600, "S85 alternatives must not triple frequency")
    require(wait("S85", "Flughafen BER", "Baumschulenweg") == 300, "S85/S9 shared service")
    finish_walk = router.fastest_path(station("Ruhleben"), station("Messe Nord/ZOB"))
    described_walk = router.describe_path(*finish_walk, start_station=station("Ruhleben"), end_station=station("Messe Nord/ZOB"))
    require(described_walk["steps"][-1]["type"] == "walk" and described_walk["steps"][-1]["elapsedSec"] == 300,
        "destination interchange must be reachable by walking without another train wait")
    require(described_walk["totalSec"] == finish_walk[0], "destination walk search/display mismatch")

    # A deliberately competing single-line route proves search uses the shared
    # wait before choosing, rather than only changing the displayed total.
    fixture_stations = {sid: {"id":sid,"name":sid} for sid in ["A","B","X"]}
    fixture_routes = {rid:{"id":rid,"label":rid,"mode":"sbahn"} for rid in ["S1","S2","S3"]}
    fixture_dirs = {rid:{"id":rid,"routeId":rid,"stations":["A","B"],"runtimes":[runtime]}
        for rid,runtime in [("S1",100),("S2",100),("S3",450)]}
    # S3 takes a different physical path, so it must not be frequency-combined.
    fixture_dirs["S3"]["stations"] = ["A","X","B"]
    fixture_dirs["S3"]["runtimes"] = [225,225]
    fixture = build_data.Router(fixture_stations, fixture_routes, fixture_dirs, {}, {},
        {"S1":600,"S2":600,"S3":30}, {}, {})
    result = fixture.fastest_path("A","B")
    require(result and result[0] == 400 and any(node.startswith(("S1|","S2|")) for node in result[1]), "search applied shared wait only after route choice")

    for day in dates:
        puzzles = json.loads((daily_dir / f"{day}.json").read_text(encoding="utf-8"))["puzzles"]
        modes = set()
        for puzzle in puzzles:
            for sid in [puzzle["start"],puzzle["end"]]:
                require(build_data.is_puzzle_endpoint(network["stations"][sid]), f"{day}: ineligible endpoint")
            require(puzzle["playable"] and puzzle["transferCount"] >= 1, f"{day}: transfer-required rule lost")
            mode_set = {leg["mode"] for leg in puzzle["optimalRoute"]["legs"]}
            modes.add(next(iter(mode_set)) if len(mode_set)==1 else "mixed")
            fastest = router.fastest_path(puzzle["start"],puzzle["end"])
            described = router.describe_path(*fastest, start_station=puzzle["start"], end_station=puzzle["end"])
            require(fastest[0] == described["totalSec"] == puzzle["optimalRoute"]["totalSec"], f"{day}: search/display/stored timing disagree")
        require(modes == {"ubahn","sbahn","mixed"}, f"{day}: missing solution variety")
    for left_name, right_name in [("Rathaus Spandau", "Hönow"), ("Pankow", "Rudow"), ("Krumme Lanke", "Wittenau")]:
        path = router.fastest_path(station_by_name[left_name], station_by_name[right_name])
        require(path, f"representative journey is unroutable: {left_name} to {right_name}")
        result = router.describe_path(path[0], path[1], station_by_name[left_name], station_by_name[right_name])
        require(result and result["totalSec"] > 0, f"journey description failed: {left_name} to {right_name}")
        print(f"journey {left_name} -> {right_name}: {round(result['totalSec'] / 60)} min, {len(result['legs'])} legs")
    print(f"Berlin U/S-Bahn valid: 25 lines, {len(network['stations'])} parent stations, {len(network['directions'])} scheduled patterns; 135 transfer-required puzzles verified")


if __name__ == "__main__":
    main()
