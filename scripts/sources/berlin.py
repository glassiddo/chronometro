"""Berlin U-Bahn selection and display rules for the VBB static GTFS feed."""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path


BVG_AGENCY_ID = "796"
U_BAHN_LINES = {f"U{number}" for number in range(1, 10)}


def feed_metadata(root: Path, config: dict) -> dict[str, str]:
    source = config["source"]
    return {
        "generatedFrom": f"{source['directory']} + {source['normalNetworkArchiveDirectory']} (U6 north)",
        "publisher": source["publisher"],
        "feedVersion": f"{source['fallbackVersion']} + {source['normalNetworkArchiveVersion']} U6 north",
        "feedValidFrom": source["fallbackValidFrom"],
        "feedValidTo": source["fallbackValidTo"],
    }


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


def _parse_time(value: str) -> int | None:
    try:
        hours, minutes, seconds = value.split(":")
        return int(hours) * 3600 + int(minutes) * 60 + int(seconds)
    except (AttributeError, ValueError):
        return None


def _historic_u6_patterns(
    archive: Path,
) -> tuple[dict[str, tuple[tuple[str, ...], list[int], int]], dict[str, dict]]:
    with (archive / "routes.txt").open(encoding="utf-8-sig", newline="") as handle:
        u6_route_ids = {
            row["route_id"]
            for row in csv.DictReader(handle)
            if row.get("agency_id") == BVG_AGENCY_ID
            and row.get("route_type") == "400"
            and route_label(row) == "U6"
        }
    with (archive / "trips.txt").open(encoding="utf-8-sig", newline="") as handle:
        trips = {
            row["trip_id"]: row.get("direction_id") or ""
            for row in csv.DictReader(handle)
            if row.get("route_id") in u6_route_ids
        }
    with (archive / "stops.txt").open(encoding="utf-8-sig", newline="") as handle:
        raw_stops = {row["stop_id"]: row for row in csv.DictReader(handle)}
    stop_to_station = {
        stop_id: row.get("parent_station") or stop_id for stop_id, row in raw_stops.items()
    }

    rows_by_trip: dict[str, list[tuple[int, str, int | None, int | None]]] = defaultdict(list)
    with (archive / "stop_times.txt").open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            trip_id = row.get("trip_id") or ""
            if trip_id not in trips:
                continue
            rows_by_trip[trip_id].append(
                (
                    int(row["stop_sequence"]),
                    stop_to_station.get(row["stop_id"], row["stop_id"]),
                    _parse_time(row.get("arrival_time") or ""),
                    _parse_time(row.get("departure_time") or ""),
                )
            )

    counts: Counter[tuple[str, tuple[str, ...]]] = Counter()
    runtime_samples: dict[tuple[str, tuple[str, ...]], list[list[int]]] = defaultdict(list)
    for trip_id, rows in rows_by_trip.items():
        rows.sort(key=lambda item: item[0])
        collapsed: list[tuple[str, int | None, int | None]] = []
        for _sequence, station_id, arrival, departure in rows:
            if collapsed and collapsed[-1][0] == station_id:
                old_station, old_arrival, _old_departure = collapsed[-1]
                collapsed[-1] = (old_station, old_arrival, departure)
            else:
                collapsed.append((station_id, arrival, departure))
        stations = tuple(item[0] for item in collapsed)
        runtimes = []
        for left, right in zip(collapsed, collapsed[1:]):
            runtime = right[1] - left[2] if right[1] is not None and left[2] is not None else 90
            runtimes.append(max(10, runtime))
        key = (trips[trip_id], stations)
        counts[key] += 1
        runtime_samples[key].append(runtimes)

    selected = {}
    for direction_id in set(trips.values()):
        candidates = [(count, key) for key, count in counts.items() if key[0] == direction_id]
        count, key = max(candidates, key=lambda item: (len(item[1][1]), item[0]))
        samples = runtime_samples[key]
        averaged = [round(sum(sample[index] for sample in samples) / len(samples)) for index in range(len(key[1]) - 1)]
        selected[direction_id] = (key[1], averaged, count)
    selected_station_ids = {station_id for stations, _runtimes, _count in selected.values() for station_id in stations}
    historic_station_meta = {}
    for station_id in selected_station_ids:
        row = raw_stops.get(station_id, {})
        child_rows = [item for item in raw_stops.values() if item.get("parent_station") == station_id]
        source = row or (child_rows[0] if child_rows else {})
        coords = []
        for item in ([row] if row else []) + child_rows:
            try:
                coords.append((float(item["stop_lat"]), float(item["stop_lon"])))
            except (KeyError, TypeError, ValueError):
                pass
        historic_station_meta[station_id] = {
            "id": station_id,
            "name": normalize_station_name(source.get("stop_name") or station_id),
            "lat": sum(item[0] for item in coords) / len(coords) if coords else None,
            "lon": sum(item[1] for item in coords) / len(coords) if coords else None,
        }
    return selected, historic_station_meta


def augment_scheduled_directions(
    root: Path,
    config: dict,
    routes: dict[str, dict],
    directions: dict[str, dict],
    used_stations: set[str],
    station_meta: dict[str, dict],
) -> None:
    """Restore the normally operating U6 north segment from VBB's pre-closure archive."""
    archive = root / config["source"]["normalNetworkArchiveDirectory"]
    if not archive.exists():
        raise FileNotFoundError(f"Berlin normal-network archive is required: {archive}")
    historic, historic_station_meta = _historic_u6_patterns(archive)
    u6_route_ids = {route_id for route_id, route in routes.items() if route["label"] == "U6"}
    u6_directions = [direction for direction in directions.values() if direction["routeId"] in u6_route_ids]
    for direction in u6_directions:
        direction_id = direction["gtfsDirectionId"]
        stations, runtimes, count = historic[direction_id]
        for station_id in stations:
            if station_id not in station_meta:
                station_meta[station_id] = historic_station_meta[station_id]
        direction["stations"] = list(stations)
        direction["runtimes"] = runtimes
        direction["tripPatternCount"] = count
        direction["label"] = normalize_station_name(station_meta[stations[-1]]["name"])
        direction["stopPattern"]["source"] = config["source"]["normalNetworkArchiveVersion"]
        direction["stopPattern"]["reason"] = "normal U6 north segment is temporarily closed in the current snapshot"
        used_stations.update(stations)


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "400": "BVG U-Bahn; only stable U1 through U9 line labels included",
        "700": "bus and replacement service; excluded",
        "900": "tram; excluded",
        "other": "excluded (including S-Bahn, regional rail, ferry, and temporary U12 service)",
    }
