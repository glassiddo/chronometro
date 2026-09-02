"""Berlin U-Bahn selection and display rules for the VBB static GTFS feed."""

from __future__ import annotations

import re


BVG_AGENCY_ID = "796"
U_BAHN_LINES = {f"U{number}" for number in range(1, 10)}


def route_label(row: dict[str, str]) -> str:
    return (row.get("route_short_name") or row.get("route_long_name") or "").strip()


def canonical_mode(row: dict[str, str]) -> str | None:
    # VBB uses the extended GTFS/NeTEx route type 400 for urban rail and also
    # publishes buses, trams, replacement buses, and temporary services in the
    # same regional feed. Require BVG, route type 400, and the stable U1-U9 set.
    label = route_label(row)
    if row.get("agency_id") == BVG_AGENCY_ID and row.get("route_type") == "400" and label in U_BAHN_LINES:
        return "ubahn"
    return None


def normalize_station_name(value: str) -> str:
    value = re.sub(r"\s*\(Berlin\)\s*$", "", value or "", flags=re.I)
    value = re.sub(r"^(?:S\+U|U)\s+", "", value, flags=re.I)
    value = re.sub(r"\s+Bhf\.?$", "", value, flags=re.I)
    return re.sub(r"\s+", " ", value).strip()


def direction_display_label(mode: str, headsign: str, terminal_name: str) -> str:
    return normalize_station_name(headsign or terminal_name)


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "400": "BVG U-Bahn; only stable U1 through U9 line labels included",
        "700": "bus and replacement service; excluded",
        "900": "tram; excluded",
        "other": "excluded (including S-Bahn, regional rail, ferry, and temporary U12 service)",
    }
