"""MTA New York City Subway weekday-daytime selection and display rules."""

from __future__ import annotations

import csv
from pathlib import Path


SUBWAY_ROUTE_IDS = {
    "1", "2", "3", "4", "5", "6", "6X", "7", "7X",
    "A", "B", "C", "D", "E", "F", "FX", "G", "J", "Z", "L", "M",
    "N", "Q", "R", "W", "GS", "FS", "H",
}
_DAYTIME_TRIP_IDS: set[str] | None = None


def route_label(row: dict[str, str]) -> str:
    route_id = row.get("route_id", "")
    labels = {
        "6X": "6", "7X": "7", "FX": "F",
        "GS": "42 St Shuttle", "FS": "Franklin Av Shuttle", "H": "Rockaway Shuttle",
    }
    return labels.get(route_id, row.get("route_short_name") or route_id)


def canonical_mode(row: dict[str, str]) -> str | None:
    if (
        row.get("agency_id") == "MTA NYCT"
        and row.get("route_type") == "1"
        and row.get("route_id") in SUBWAY_ROUTE_IDS
    ):
        return "subway"
    return None


def _parse_time(value: str) -> int | None:
    try:
        hours, minutes, seconds = value.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    except (AttributeError, ValueError):
        return None


def _daytime_trip_ids(gtfs: Path) -> set[str]:
    """Trips beginning 07:00-10:00 represent the normal weekday morning network."""
    global _DAYTIME_TRIP_IDS
    if _DAYTIME_TRIP_IDS is not None:
        return _DAYTIME_TRIP_IDS
    first_departure: dict[str, tuple[int, int]] = {}
    with (gtfs / "stop_times.txt").open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                sequence = int(row.get("stop_sequence") or 0)
            except ValueError:
                continue
            departure = _parse_time(row.get("departure_time", ""))
            if departure is None:
                departure = _parse_time(row.get("arrival_time", ""))
            if departure is None:
                continue
            trip_id = row.get("trip_id", "")
            previous = first_departure.get(trip_id)
            if previous is None or sequence < previous[0]:
                first_departure[trip_id] = (sequence, departure)
    _DAYTIME_TRIP_IDS = {
        trip_id for trip_id, (_sequence, departure) in first_departure.items()
        if 7 * 3600 <= departure < 10 * 3600
    }
    return _DAYTIME_TRIP_IDS


def include_trip(row: dict[str, str], gtfs: Path) -> bool:
    return row.get("trip_id", "") in _daytime_trip_ids(gtfs)


def normalize_station_name(value: str) -> str:
    return " ".join((value or "").split())


def direction_display_label(mode: str, headsign: str, terminal_name: str) -> str:
    return normalize_station_name(terminal_name)


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "1": "MTA NYC Subway only (explicit route-ID allowlist, including three shuttles)",
        "2": "Staten Island Railway excluded",
        "3": "all buses excluded",
        "other": "excluded",
    }


def station_equivalence_groups(
    root: Path, config: dict, stations: dict[str, dict]
) -> tuple[dict[str, str], list[list[str]]]:
    """Use MTA's official complexes for puzzle endpoints without erasing transfer walks."""
    source = root / config["source"]["directory"] / "station_complexes.csv"
    groups: list[list[str]] = []
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            ids = sorted(
                stop_id.strip()
                for stop_id in (row.get("gtfs_stop_ids") or "").split(";")
                if stop_id.strip() in stations
            )
            if not ids:
                continue
            canonical = ids[0]
            for station_id in ids:
                stations[station_id]["complexId"] = row.get("complex_id") or canonical
                stations[station_id]["complexName"] = row.get("stop_name") or stations[station_id]["name"]
            if len(ids) > 1:
                groups.append(ids)
    canonical_ids = {
        station_id: group[0]
        for group in groups
        for station_id in group
    }
    return canonical_ids, groups
