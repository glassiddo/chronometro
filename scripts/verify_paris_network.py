#!/usr/bin/env python3
"""Verify restored normal Paris topology omitted by the summer 2026 feed."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> None:
    network = json.loads((ROOT / "public/data/paris/network.json").read_text(encoding="utf-8"))
    by_route: dict[str, list[dict]] = {}
    for direction in network["directions"].values():
        by_route.setdefault(direction["routeId"], []).append(direction)

    t1 = by_route["9241"]
    require(len(t1) == 2, "T1 must have exactly two normal full-line directions")
    require(all(len(item["stations"]) == 37 for item in t1), "T1 must contain all 37 normal stations")
    require(
        {(item["stations"][0], item["stations"][-1]) for item in t1}
        == {("ITOAUTO96071", "ITOAUTO79290"), ("ITOAUTO79290", "ITOAUTO96071")},
        "T1 normal Asnières-Gare de Noisy-le-Sec termini are missing",
    )

    rer_a = by_route["15323"]
    require(all("PARIS16509" in item["stations"] for item in rer_a), "a closure-era RER A pattern still skips Nation")
    require(
        all(
            ("ITOAUTO79160", "PARIS16509", "ITOAUTO79805") in list(zip(item["stations"], item["stations"][1:], item["stations"][2:]))
            or ("ITOAUTO79805", "PARIS16509", "ITOAUTO79160") in list(zip(item["stations"], item["stations"][1:], item["stations"][2:]))
            for item in rer_a
            if "ITOAUTO79160" in item["stations"] and "ITOAUTO79805" in item["stations"]
        ),
        "Nation is not in the normal Vincennes-Gare de Lyon sequence",
    )
    print(f"Paris network valid: restored 37-stop T1 and Nation on {len(rer_a)} RER A patterns")


if __name__ == "__main__":
    main()
