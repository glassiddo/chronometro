"""Berlin regular U/S-Bahn normalization, historical repairs, and geography."""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from functools import lru_cache


BVG_AGENCY_ID = "796"
U_BAHN_LINES = {f"U{number}" for number in range(1, 10)}
S_BAHN_LINES = {"S1", "S15", "S2", "S25", "S26", "S3", "S41", "S42", "S46", "S47", "S5", "S7", "S75", "S8", "S85", "S9"}


def segment_arrival(route_id, arrival, departure):
    # Departure-to-departure includes station dwell, material on a full ring.
    # Preserve the existing U-Bahn timing convention.
    return departure if route_id in S_BAHN_LINES and departure is not None else arrival


def include_segment_timing(route_id, departure):
    return route_id not in S_BAHN_LINES or departure is not None and 7 * 3600 <= departure < 10 * 3600


def feed_metadata(root: Path, config: dict) -> dict[str, str]:
    source = config["source"]
    return {
        "generatedFrom": f"{source['directory']} + {source['normalNetworkArchiveDirectory']} (U6 north, Wollankstraße) + regular S-Bahn timetable",
        "publisher": source["publisher"],
        "feedVersion": f"{source['fallbackVersion']} + {source['normalNetworkArchiveVersion']} normal-network repairs + S-Bahn regular service 2026",
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
    if row.get("agency_id") == "1" and row.get("route_type") == "109" and label in S_BAHN_LINES:
        return "sbahn"
    return None


def normalize_station_name(value: str) -> str:
    value = re.sub(r"\s*\(Berlin\)\s*$", "", value or "", flags=re.I)
    value = re.sub(r"^(?:S\+U|U|S)\s+", "", value, flags=re.I)
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
        "109": "S-Bahn Berlin GmbH; regular S-Bahn lines only, including S15; discontinued S45 excluded",
        "700": "bus and replacement service; excluded",
        "900": "tram; excluded",
        "other": "excluded (including regional rail, ferry, and temporary U12 service)",
    }


@lru_cache(maxsize=1)
def _state_polygons():
    path = Path(__file__).resolve().parents[2] / "config/berlin-state-boundary.geojson"
    features = json.loads(path.read_text(encoding="utf-8"))["features"]
    return [polygon for feature in features for polygon in feature["geometry"]["coordinates"]]


def is_within_puzzle_boundary(station: dict) -> bool:
    """ALKIS state polygon, EPSG:4326, longitude first; preserve holes/islands."""
    x, y = station.get("lon"), station.get("lat")
    if not isinstance(x, (float, int)) or not isinstance(y, (float, int)):
        return False

    def inside(ring):
        result = False
        for (ax, ay), (bx, by) in zip(ring, ring[1:]):
            if (ay > y) != (by > y) and x < (bx - ax) * (y - ay) / (by - ay) + ax:
                result = not result
        return result

    return any(inside(polygon[0]) and not any(inside(hole) for hole in polygon[1:]) for polygon in _state_polygons())


def build_normalized_source(root: Path, config: dict) -> dict:
    """Regular service manifest, with current timings and explicit archive repairs.

    VBB route IDs distinguish timetable variants, not public lines. Collapse
    S-Bahn IDs before aggregation; never count those IDs as extra frequencies.
    """
    import build_data as b

    raw_routes = b.read_routes()
    stop_to_station, station_meta = b.read_stops()
    services = b.read_weekday_services()
    trips = b.read_trips(raw_routes, services)
    routes = {}
    route_map = {}
    for raw_id, route in raw_routes.items():
        route_id = route["label"] if route["mode"] == "sbahn" else raw_id
        route_map[raw_id] = route_id
        if route_id not in routes or route["color"] != "#777777":
            routes[route_id] = {**route, "id": route_id}
    for trip in trips.values():
        trip["routeId"] = route_map[trip["routeId"]]
    stats, counts, headsigns, departures, raw_stop_routes = b.read_stop_times(trips, stop_to_station, services)
    u_routes = {rid: r for rid, r in routes.items() if r["mode"] == "ubahn"}
    directions, used, keys = b.choose_patterns(u_routes, station_meta, stats, counts, headsigns, departures)
    augment_scheduled_directions(root, config, routes, directions, used, station_meta)
    waits, route_waits = b.build_waits(directions, u_routes, keys, departures)

    # Scan historical S-Bahn edges only. Keep stable VBB parent IDs and use
    # the current station metadata even where archived runtimes are required.
    archive = root / config["source"]["normalNetworkArchiveDirectory"]
    def read(name):
        return csv.DictReader((archive / f"{name}.txt").open(encoding="utf-8-sig", newline=""))
    old_routes = {r["route_id"]: route_label(r) for r in read("routes") if r["agency_id"] == "1" and r["route_type"] == "109"}
    old_trips = {t["trip_id"] for t in read("trips") if t["route_id"] in old_routes}
    old_stops = {s["stop_id"]: s for s in read("stops")}
    old_rows = defaultdict(list)
    with (archive / "stop_times.txt").open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        ix = {name: i for i, name in enumerate(next(reader))}
        for row in reader:
            if row[ix["trip_id"]] in old_trips:
                sid = row[ix["stop_id"]]
                old_rows[row[ix["trip_id"]]].append((int(row[ix["stop_sequence"]]), old_stops[sid].get("parent_station") or sid,
                    _parse_time(row[ix["arrival_time"]]), _parse_time(row[ix["departure_time"]])))
    historic_edges = defaultdict(list)
    for rows in old_rows.values():
        rows.sort()
        for left, right in zip(rows, rows[1:]):
            if left[3] is not None and 7 * 3600 <= left[3] < 10 * 3600 and right[3] is not None and 10 <= right[3] - left[3] <= 7200:
                historic_edges[(left[1], right[1])].append(right[3] - left[3])
    current_edges = defaultdict(lambda: [0, 0])
    for (rid, _di, left, right), (total, count) in stats.items():
        current_edges[(rid, left, right)][0] += total
        current_edges[(rid, left, right)][1] += count
    manifest = json.loads((root / "config/berlin-sbahn-patterns.json").read_text(encoding="utf-8"))
    repairs = []
    for pattern_index, pattern in enumerate(manifest["patterns"]):
        line = pattern["line"]
        sequence = pattern["stations"]
        # Northbound trains temporarily skip Wollankstraße in September 2026.
        sequence = list(sequence)
        for i in range(len(sequence) - 1, 0, -1):
            if {sequence[i - 1], sequence[i]} == {"de:11000:900110011", "de:11000:900085201"}:
                sequence.insert(i, "de:11000:900130003")
        for reverse in range(1 if pattern.get("circular") else 2):
            ids = sequence[::-1] if reverse else sequence[:]
            runtimes, provenance = [], []
            for left, right in zip(ids, ids[1:]):
                edge = (line, left, right)
                samples = current_edges.get(edge)
                restore = right == "de:11000:900130003" and left == "de:11000:900110011" or left == "de:11000:900130003" and right == "de:11000:900085201"
                if samples and samples[1] and not restore:
                    runtime = round(samples[0] / samples[1])
                    provenance.append("VBB 2026-09-02")
                else:
                    samples = historic_edges.get((left, right))
                    if not samples:
                        raise ValueError(f"No official runtime for {line}: {left} -> {right}")
                    runtime = round(sum(samples) / len(samples))
                    provenance.append("VBB 2021")
                    repairs.append({"line": line, "from": left, "to": right, "seconds": runtime})
                runtimes.append(runtime)
            did = f"{line}:{pattern_index}:{reverse}"
            direction = {"id": did, "branchId": did, "routeId": line,
                "label": station_meta[ids[-1]]["name"], "gtfsDirectionId": str(reverse),
                "stations": ids, "runtimes": runtimes, "frequencyGroup": pattern["frequencyGroup"],
                "stopPattern": {"kind": "scheduled", "servesEveryListedStop": True,
                    "source": pattern["topologySource"], "runtimeSources": provenance,
                    "waitSource": manifest["sources"]["regularTimetable"]}}
            if pattern.get("circular"):
                # Two unrolled laps allow any boarding station to cross the
                # serialization seam without a fictitious transfer or reverse.
                ring = ids[:-1]
                direction.update(stations=ring + ring, runtimes=(runtimes * 2)[:-1],
                    circular=True, ringStationCount=len(ring),
                    label="Ringbahn clockwise ↻" if line == "S41" else "Ringbahn counterclockwise ↺")
                direction["stopPattern"]["runtimeSources"] = (provenance * 2)[:-1]
            directions[did] = direction
            waits[did] = pattern["waitSeconds"]
            route_waits[line] = max(route_waits.get(line, 0), pattern["waitSeconds"])
            used.update(ids)
    stations = {sid: station_meta[sid] for sid in sorted(used)}
    for station in stations.values():
        station["withinBerlinState"] = is_within_puzzle_boundary(station)
    transfers = b.read_transfers(stop_to_station, used)
    # Explicit interchanges drawn on the official S+U map. Their GTFS parents
    # remain distinct; these are modeled walks, never proximity equivalences.
    for left, right, seconds in [
        ("de:11000:900029101", "de:11000:900029302", 300),  # Spandau / Rathaus
        ("de:11000:900024101", "de:11000:900024202", 300),  # Charlottenburg / Wilmersdorfer
        ("de:11000:900024106", "de:11000:900026202", 300),  # Messe Nord/ZOB / Kaiserdamm
        ("de:11000:900057102", "de:11000:900058103", 300),  # Yorckstraße S1 / U7, S2/25/26
    ]:
        transfers.setdefault(left, {})[right] = seconds
        transfers.setdefault(right, {})[left] = seconds
    route_transfers = b.read_route_transfers(stop_to_station, raw_stop_routes, routes, used)
    return {"stations": stations, "routes": routes, "directions": directions,
        "transfers": transfers, "routeTransfers": route_transfers,
        "waitSecondsByDirection": waits, "waitSecondsByRoute": route_waits,
        "canonicalStationIds": {sid: sid for sid in stations}, "stationEquivalents": [],
        "metadata": {"normalNetworkRepairs": repairs, "regularServiceSources": manifest["sources"],
            "endpointBoundary": "ALKIS Berlin Landesgrenze, EPSG:4326, retrieved 2026-09-03",
            "frequencyModel": "Regular weekday service frequencies; alternative termini share a frequency group; independent peak trains add frequency only over the entire matching ride."}}
