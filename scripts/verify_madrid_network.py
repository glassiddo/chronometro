#!/usr/bin/env python3
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NETWORK = ROOT / "public/data/madrid/network.json"

def require(value, message):
    if not value: raise AssertionError(message)

def main():
    data = json.loads(NETWORK.read_text(encoding="utf-8"))
    require({r["label"] for r in data["routes"].values()} == {str(i) for i in range(1, 13)} | {"R"}, "line coverage")
    require(240 <= len(data["stations"]) <= 245, "unexpected station-complex count")
    require(all(r["mode"] == "metro" for r in data["routes"].values()), "excluded mode present")
    by_line = {label: [d for d in data["directions"].values() if data["routes"][d["routeId"]]["label"] == label] for label in {"6","7","9","10","12"}}
    for line in ("6", "12"):
        require(len(by_line[line]) == 2 and all(d.get("circular") and d.get("ringStationCount") for d in by_line[line]), f"Line {line} ring directions")
        require(all(len(d["stations"]) == 2*d["ringStationCount"] for d in by_line[line]), f"Line {line} seam unroll")
    for line, station in (("7", "Estadio Metropolitano"), ("9", "Puerta de Arganda"), ("10", "Tres Olivos")):
        dirs = by_line[line]
        require(sum(station in [data["stations"][s]["name"] for s in d["stations"]] for d in dirs) >= 4, f"Line {line} mandatory change patterns")
    names = {s["name"] for s in data["stations"].values()}
    for outer in ("Hospital del Henares", "Arganda del Rey", "Hospital Infanta Sofia", "El Casar"):
        require(any(outer.casefold() == name.casefold() for name in names), f"missing outer endpoint {outer}")
    require(data["metadata"]["city"]["timezone"] == "Europe/Madrid", "timezone")
    require(len(data["canonicalStationIds"]) == 0 and not data["transfers"], "invented proximity transfer")
    daily_dir = ROOT / "public/data/madrid/daily"
    mandatory_ids = {"est_4_182", "est_4_274", "est_4_286"}
    checked_changes = set()
    for path in daily_dir.glob("2026-*.json"):
        for puzzle in json.loads(path.read_text(encoding="utf-8"))["puzzles"]:
            legs = puzzle["optimalRoute"]["legs"]
            for left, right in zip(legs, legs[1:]):
                if left.get("line") == right.get("line") and left.get("to") == right.get("from") in mandatory_ids:
                    require(right["transferSec"] == 180, "same-line change must charge three-minute interchange")
                    require(right["waitSec"] > 0, "same-line change must charge a new wait")
                    checked_changes.add(right["from"])
    require(checked_changes == mandatory_ids, f"daily routes did not exercise mandatory changes: {mandatory_ids - checked_changes}")
    print("madrid network verification passed")

if __name__ == "__main__": main()
