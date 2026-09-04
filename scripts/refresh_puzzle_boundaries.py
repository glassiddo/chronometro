#!/usr/bin/env python3
"""Refresh endpoint metadata and puzzles without changing network topology/timing.

Requires the existing normalized network and ignored all-pairs cache. An expanded
endpoint pool requires a full all-pairs rebuild instead of this narrow refresh.
"""

import argparse
import copy
import json

import build_data as build


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("city", choices=["paris", "london"])
    args = parser.parse_args()
    build.configure_city(args.city)
    network = json.loads(build.NETWORK_OUT.read_text(encoding="utf-8"))
    original = copy.deepcopy(network)
    loaded = build.load_all_pairs()
    if loaded is None:
        raise RuntimeError("Missing/incomplete candidate cache; run build_city.py --mode all-pairs first")
    pairs, _ = loaded
    network["metadata"]["puzzleConstraints"] = copy.deepcopy(build.CITY_CONFIG["puzzles"])
    # Only the constraints metadata may change; all station/route/timing data stay fixed.
    check = copy.deepcopy(network)
    check["metadata"]["puzzleConstraints"] = original["metadata"]["puzzleConstraints"]
    assert check == original
    build.write_json(build.NETWORK_OUT, network)
    build.write_example(pairs, build.DEFAULT_EXAMPLE_COUNT)
    build.write_daily_range(pairs, build.DEFAULT_START_DATE, build.DEFAULT_DAYS, build.DEFAULT_DAILY_COUNT)


if __name__ == "__main__":
    main()
