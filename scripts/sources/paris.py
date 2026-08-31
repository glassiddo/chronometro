"""Paris GTFS selection and display rules.

This module contains source-feed semantics only. The normalized network,
routing, timing and puzzle generation remain in the shared builder.
"""

import re

RER_LABELS = {"A", "B", "C", "D", "E"}


def normalize_station_name(value: str) -> str:
    """Keep the two CDG RER B terminal names parallel and unambiguous."""
    name = (value or "").strip()
    name = re.sub(
        r"^Aéroport CDG\s*\(Terminal 2\)\s*-\s*TGV$",
        "Aéroport CDG 2 (Terminal 2, TGV)",
        name,
        flags=re.IGNORECASE,
    )
    return name


def route_label(row: dict[str, str]) -> str:
    return (row.get("route_short_name") or row.get("route_long_name") or "").strip()


def canonical_mode(row: dict[str, str]) -> str | None:
    label = route_label(row).upper()
    route_type = row.get("route_type")
    if route_type == "1":
        return "metro"
    if route_type == "0" and label.startswith("T"):
        return "tram"
    if route_type == "2" and label in RER_LABELS:
        return "rer"
    return None


def direction_display_label(mode: str, headsign: str, terminal_name: str) -> str:
    clean_headsign = (headsign or "").strip()
    if mode == "rer":
        return terminal_name
    if not clean_headsign:
        return terminal_name
    letters = [char for char in clean_headsign if char.isalpha()]
    if 1 <= len(clean_headsign) <= 5 and letters and all(char.isupper() for char in letters):
        return terminal_name
    return clean_headsign


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "0": "tram-like; kept labels beginning T only",
        "1": "metro; kept all",
        "2": "rail; kept RER A-E only",
        "3": "bus; excluded for v1",
        "6": "aerial lift/funicular-like; excluded",
        "7": "funicular-like; excluded",
    }
