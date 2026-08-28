"""WMATA static-rail GTFS selection, normalization, and transfer rules."""

from __future__ import annotations

import re


METRORAIL_ROUTE_IDS = {"RED", "BLUE", "ORANGE", "SILVER", "YELLOW", "GREEN"}


def route_label(row: dict[str, str]) -> str:
    return (row.get("route_long_name") or row.get("route_short_name") or "").strip()


def canonical_mode(row: dict[str, str]) -> str | None:
    # The rail-only endpoint currently contains six route_type=1 records. Keep
    # an explicit ID allow-list as a second guard against accidental expansion.
    if row.get("route_type") == "1" and row.get("route_id") in METRORAIL_ROUTE_IDS:
        return "metrorail"
    return None


def normalize_station_name(value: str) -> str:
    """Clean non-passenger annotations without merging distinct stations."""
    value = re.sub(r"\s*\((?:Red|Blue|Orange|Silver|Yellow|Green)(?:\s*(?:,|/|and)\s*(?:Red|Blue|Orange|Silver|Yellow|Green))*\s+Lines?\)\s*$", "", value or "", flags=re.I)
    value = re.sub(r"\s+(?:Northbound|Southbound|Eastbound|Westbound)\s+(?:Platform|Track)\s*$", "", value, flags=re.I)
    value = re.sub(r"\s+(?:Platform|Track)\s+\d+\s*$", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def direction_display_label(mode: str, headsign: str, terminal_name: str) -> str:
    # WMATA headsigns occasionally contain operational text; the scheduled
    # pattern's passenger-station terminus is stable and sufficient in the UI.
    return normalize_station_name(terminal_name)


def augment_transfers(transfers: dict[str, dict[str, int]], stations: dict[str, dict]) -> None:
    """Add WMATA's documented out-of-system Farragut Crossing only."""
    north = "STN_A02"
    west = "STN_C03"
    if north in stations and west in stations:
        transfers.setdefault(north, {})[west] = 300
        transfers.setdefault(west, {})[north] = 300


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "1": "Metrorail; only RED, BLUE, ORANGE, SILVER, YELLOW, and GREEN included",
        "3": "bus; excluded",
        "other": "excluded (including MARC, VRE, Amtrak, Circulator, and commuter services)",
    }
