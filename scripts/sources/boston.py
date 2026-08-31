"""MBTA scheduled rapid-transit/light-rail selection and normalization rules."""

from __future__ import annotations

import csv
import re
from pathlib import Path


ROUTE_IDS = {"Red", "Orange", "Blue", "Green-B", "Green-C", "Green-D", "Green-E", "Mattapan"}
GREEN_IDS = {"Green-B", "Green-C", "Green-D", "Green-E", "Mattapan"}
_TYPICAL_PATTERN_IDS: set[str] | None = None


def route_label(row: dict[str, str]) -> str:
    labels = {
        "Green-B": "Green B", "Green-C": "Green C", "Green-D": "Green D", "Green-E": "Green E",
        "Mattapan": "Mattapan",
    }
    return labels.get(row.get("route_id", ""), (row.get("route_long_name") or "").removesuffix(" Line"))


def canonical_mode(row: dict[str, str]) -> str | None:
    if row.get("agency_id") != "1" or row.get("route_id") not in ROUTE_IDS:
        return None
    return "light_rail" if row["route_id"] in GREEN_IDS else "rapid_transit"


def include_trip(row: dict[str, str], gtfs: Path) -> bool:
    """Keep only MBTA route patterns marked typical in the current snapshot."""
    global _TYPICAL_PATTERN_IDS
    if _TYPICAL_PATTERN_IDS is None:
        with (gtfs / "route_patterns.txt").open("r", encoding="utf-8-sig", newline="") as fh:
            _TYPICAL_PATTERN_IDS = {
                item["route_pattern_id"] for item in csv.DictReader(fh)
                if item.get("route_id") in ROUTE_IDS and item.get("route_pattern_typicality") == "1"
            }
    return row.get("route_pattern_id") in _TYPICAL_PATTERN_IDS


def normalize_station_name(value: str) -> str:
    value = re.sub(r"\s+(?:Inbound|Outbound|Northbound|Southbound|Eastbound|Westbound)\s*$", "", value or "", flags=re.I)
    value = re.sub(r"\s+(?:Platform|Track)\s*[A-Z0-9-]*\s*$", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def direction_display_label(mode: str, headsign: str, terminal_name: str) -> str:
    return normalize_station_name(terminal_name)


def augment_transfers(transfers: dict[str, dict[str, int]], stations: dict[str, dict]) -> None:
    # Winter Street Concourse is a documented pedestrian connection. Five minutes
    # is a conservative fixed walk for the roughly 800-foot passage and station circulation.
    park, downtown = "place-pktrm", "place-dwnxg"
    if park in stations and downtown in stations:
        transfers.setdefault(park, {})[downtown] = 300
        transfers.setdefault(downtown, {})[park] = 300


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "0": "Green B/C/D/E and Mattapan only (explicit route-ID allowlist)",
        "1": "Red, Orange, and Blue only (explicit route-ID allowlist)",
        "2": "Commuter Rail and CapeFLYER excluded",
        "3": "all buses excluded, including Silver Line and replacement shuttles",
        "4": "ferries excluded",
        "other": "excluded",
    }
