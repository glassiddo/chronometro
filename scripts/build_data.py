#!/usr/bin/env python3
"""Build the static data bundle for Metro Express.

Source feed:
  gouv_paris_gtfs-export
  ITO World "Modified GTFS Dataset for IDFM Public Transport Services in Paris"
  feed_info.txt reports version 20260630_200738, valid 2026-06-27 to 2026-07-29.

Route filtering verified against this export:
  route_type 0: tram-like routes. Keep only labels beginning with "T"; exclude
                airport people movers such as ORLYVAL and CDG VAL.
  route_type 1: metro routes. Keep all.
  route_type 2: rail routes. Keep only RER labels A, B, C, D, E; exclude
                Transilien, TER, and other rail services.
  route_type 3: bus. Excluded for v1, but the output schema keeps a mode field.
"""

from __future__ import annotations

import argparse
import csv
import heapq
import json
import math
import random
import re
import sys
import unicodedata
from collections import Counter, defaultdict
from datetime import date, timedelta
from pathlib import Path
from statistics import median


ROOT = Path(__file__).resolve().parents[1]
GTFS = ROOT / "gouv_paris_gtfs-export"
DATA_DIR = ROOT / "public" / "data"
NETWORK_OUT = DATA_DIR / "metro-express-network.json"
ALL_PAIRS_OUT = DATA_DIR / "generated" / "metro-express-all-pairs.json"
EXAMPLE_OUT = DATA_DIR / "example" / "metro-express-example-data.json"
DAILY_DIR = DATA_DIR / "daily"
DAILY_INDEX_OUT = DAILY_DIR / "index.json"

MAX_DIRECTIONS_PER_ROUTE = 18
MIN_PUZZLE_ROUTE_DISTANCE_M = 1000
MIN_PUZZLE_ENDPOINT_DISTANCE_M = 1500
RER_LABELS = {"A", "B", "C", "D", "E"}
DEFAULT_START_DATE = "2026-07-28"
DEFAULT_DAYS = 365
DEFAULT_DAILY_COUNT = 5
DEFAULT_EXAMPLE_COUNT = 100
ALL_PAIRS_PROGRESS_INTERVAL = 1000

WAIT_BY_MODE = {
    "metro": 120,
    "rer": 240,
    "tram": 240,
    "bus": 300,
}

PEAK_START = 7 * 3600
PEAK_END = 10 * 3600
MIN_WAIT_SECONDS = 30
MAX_WAIT_BY_MODE = {
    "metro": 240,
    "rer": 600,
    "tram": 600,
    "bus": 600,
}

TRANSFER_DEFAULTS = {
    "same_mode": 180,
    "metro_rer": 360,
    "metro_tram": 240,
    "rer_tram": 360,
    "fallback": 300,
}

STATION_EQUIVALENCE_DISTANCE_M = 150
STATION_EQUIVALENCE_TRANSFER_SECONDS = 120

PARIS_CITY_BOUNDS = {
    "min_lat": 48.815,
    "max_lat": 48.902,
    "min_lon": 2.25,
    "max_lon": 2.42,
}


def log(message: str) -> None:
    print(message, flush=True)


def read_csv(name: str):
    path = GTFS / name
    return csv.DictReader(path.open("r", encoding="utf-8-sig", newline=""))


def write_json(path: Path, data: dict | list) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        encoding="utf-8",
    )


def file_size_mb(path: Path) -> float:
    return path.stat().st_size / (1024 * 1024)


def read_feed_metadata() -> dict[str, str]:
    def gtfs_date(value: str, fallback: str) -> str:
        if re.fullmatch(r"\d{8}", value or ""):
            return f"{value[:4]}-{value[4:6]}-{value[6:8]}"
        return value or fallback

    try:
        row = next(read_csv("feed_info.txt"))
    except (FileNotFoundError, StopIteration):
        row = {}
    return {
        "generatedFrom": "gouv_paris_gtfs-export",
        "publisher": "ITO World modified GTFS export derived from Ile-de-France Mobilites",
        "feedVersion": row.get("feed_version") or "20260630_200738",
        "feedValidFrom": gtfs_date(row.get("feed_start_date", ""), "2026-06-27"),
        "feedValidTo": gtfs_date(row.get("feed_end_date", ""), "2026-07-29"),
    }


def normalized_station_name(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "")
    ascii_text = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", re.sub(r"[^\w]+", " ", ascii_text.casefold())).strip()


def station_distance_m(left: dict, right: dict) -> float | None:
    lat1 = left.get("lat")
    lon1 = left.get("lon")
    lat2 = right.get("lat")
    lon2 = right.get("lon")
    if not all(isinstance(value, (int, float)) for value in [lat1, lon1, lat2, lon2]):
        return None
    radius_m = 6_371_000
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lon2 - lon1)
    hav = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * radius_m * math.atan2(math.sqrt(hav), math.sqrt(1 - hav))


def read_weekday_services() -> set[str]:
    services = set()
    for row in read_csv("calendar.txt"):
        if all(row.get(day) == "1" for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]):
            services.add(row["service_id"])
    if not services:
        for row in read_csv("calendar.txt"):
            if any(row.get(day) == "1" for day in ["monday", "tuesday", "wednesday", "thursday", "friday"]):
                services.add(row["service_id"])
    log(f"weekday service ids for peak headways: {len(services)}")
    return services


def route_label(row: dict[str, str]) -> str:
    return (row.get("route_short_name") or row.get("route_long_name") or "").strip()


def parse_time(value: str) -> int | None:
    if not value:
        return None
    try:
        h, m, s = value.split(":")
        return int(h) * 3600 + int(m) * 60 + int(s)
    except ValueError:
        return None


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


def read_routes() -> dict[str, dict]:
    routes = {}
    route_type_counts = Counter()
    kept_counts = Counter()
    for row in read_csv("routes.txt"):
        route_type_counts[row["route_type"]] += 1
        mode = canonical_mode(row)
        if not mode:
            continue
        label = route_label(row)
        routes[row["route_id"]] = {
            "id": row["route_id"],
            "label": label,
            "name": row.get("route_long_name") or label,
            "mode": mode,
            "color": f"#{(row.get('route_color') or '777777').strip()}",
            "textColor": f"#{(row.get('route_text_color') or 'FFFFFF').strip()}",
            "routeType": row.get("route_type", ""),
        }
        kept_counts[mode] += 1
    log(f"routes.txt route_type distribution: {dict(sorted(route_type_counts.items()))}")
    log(f"kept routes by mode: {dict(kept_counts)}")
    return routes


def read_stops() -> tuple[dict[str, str], dict[str, dict]]:
    raw = {}
    children = defaultdict(list)
    for row in read_csv("stops.txt"):
        raw[row["stop_id"]] = row
        parent = row.get("parent_station") or ""
        if parent:
            children[parent].append(row["stop_id"])

    stop_to_station = {}
    station_meta = {}
    for stop_id, row in raw.items():
        station_id = row.get("parent_station") or stop_id
        stop_to_station[stop_id] = station_id

    station_ids = set(stop_to_station.values())
    for station_id in station_ids:
        row = raw.get(station_id)
        child_rows = [raw[c] for c in children.get(station_id, []) if c in raw]
        source = row or (child_rows[0] if child_rows else raw.get(station_id, {}))
        coords = []
        for item in ([row] if row else []) + child_rows:
            if not item:
                continue
            try:
                coords.append((float(item["stop_lat"]), float(item["stop_lon"])))
            except (KeyError, TypeError, ValueError):
                pass
        lat = sum(c[0] for c in coords) / len(coords) if coords else None
        lon = sum(c[1] for c in coords) / len(coords) if coords else None
        station_meta[station_id] = {
            "id": station_id,
            "name": source.get("stop_name") or station_id,
            "lat": lat,
            "lon": lon,
        }
    log(f"loaded {len(raw)} stops; collapsed to {len(station_meta)} parent stations/stops")
    return stop_to_station, station_meta


def read_trips(routes: dict[str, dict]) -> dict[str, dict]:
    trips = {}
    by_route = Counter()
    for row in read_csv("trips.txt"):
        route_id = row["route_id"]
        if route_id not in routes:
            continue
        trips[row["trip_id"]] = {
            "routeId": route_id,
            "serviceId": row.get("service_id") or "",
            "directionId": row.get("direction_id") or "",
            "headsign": row.get("trip_headsign") or "",
        }
        by_route[route_id] += 1
    log(f"kept {len(trips)} trips across {len(by_route)} selected routes")
    return trips


def read_stop_times(
    trips: dict[str, dict], stop_to_station: dict[str, str], weekday_services: set[str]
) -> tuple[
    dict[tuple[str, str, str, str], list[int]],
    Counter,
    dict[tuple[str, str, tuple[str, ...]], Counter],
    dict[tuple[str, str, tuple[str, ...]], list[int]],
    dict[str, set[str]],
]:
    segment_stats = defaultdict(lambda: [0, 0])
    pattern_counts: Counter[tuple[str, str, tuple[str, ...]]] = Counter()
    pattern_headsigns: dict[tuple[str, str, tuple[str, ...]], Counter] = defaultdict(Counter)
    pattern_peak_departures: dict[tuple[str, str, tuple[str, ...]], list[int]] = defaultdict(list)
    raw_stop_routes: dict[str, set[str]] = defaultdict(set)

    path = GTFS / "stop_times.txt"
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        idx = {name: i for i, name in enumerate(header)}

        current_trip = None
        rows = []
        processed = 0
        selected_rows = 0

        def finalize(trip_id: str | None, trip_rows: list[tuple[int, str, int | None, int | None]]) -> None:
            if not trip_id or trip_id not in trips or not trip_rows:
                return
            trip = trips[trip_id]
            trip_rows.sort(key=lambda item: item[0])
            collapsed = []
            for _, stop_id, arrival, departure in trip_rows:
                station_id = stop_to_station.get(stop_id, stop_id)
                if collapsed and collapsed[-1][0] == station_id:
                    old_station, old_arrival, _old_departure = collapsed[-1]
                    collapsed[-1] = (old_station, old_arrival, departure)
                else:
                    collapsed.append((station_id, arrival, departure))

            stations = tuple(item[0] for item in collapsed)
            if len(stations) < 2:
                return

            route_id = trip["routeId"]
            direction_id = trip["directionId"]
            pattern_key = (route_id, direction_id, stations)
            pattern_counts[pattern_key] += 1
            if trip["headsign"]:
                pattern_headsigns[pattern_key][trip["headsign"]] += 1

            first_departure = collapsed[0][2]
            if (
                first_departure is not None
                and PEAK_START <= first_departure < PEAK_END
                and (not weekday_services or trip["serviceId"] in weekday_services)
            ):
                pattern_peak_departures[pattern_key].append(first_departure)

            for left, right in zip(collapsed, collapsed[1:]):
                from_station, _from_arrival, from_departure = left
                to_station, to_arrival, _to_departure = right
                if from_station == to_station or from_departure is None or to_arrival is None:
                    continue
                runtime = to_arrival - from_departure
                if 10 <= runtime <= 7200:
                    stats = segment_stats[(route_id, direction_id, from_station, to_station)]
                    stats[0] += runtime
                    stats[1] += 1

        for row in reader:
            processed += 1
            trip_id = row[idx["trip_id"]]
            if trip_id != current_trip:
                finalize(current_trip, rows)
                current_trip = trip_id
                rows = []
            if trip_id in trips:
                selected_rows += 1
                raw_stop_routes[row[idx["stop_id"]]].add(trips[trip_id]["routeId"])
                rows.append(
                    (
                        int(row[idx["stop_sequence"]]),
                        row[idx["stop_id"]],
                        parse_time(row[idx["arrival_time"]]),
                        parse_time(row[idx["departure_time"]]),
                    )
                )
            if processed % 5_000_000 == 0:
                log(f"processed {processed:,} stop_times rows ({selected_rows:,} selected)")

        finalize(current_trip, rows)

    log(f"built {len(segment_stats)} averaged consecutive station timings")
    log(f"found {len(pattern_counts)} selected trip patterns")
    return segment_stats, pattern_counts, pattern_headsigns, pattern_peak_departures, raw_stop_routes


def is_subsequence(candidate: tuple[str, ...], existing: tuple[str, ...]) -> bool:
    if len(candidate) >= len(existing):
        return False
    limit = len(existing) - len(candidate) + 1
    for start in range(limit):
        if existing[start : start + len(candidate)] == candidate:
            return True
    return False


def contiguous_subsequence_start(candidate: tuple[str, ...], existing: tuple[str, ...]) -> int | None:
    if len(candidate) >= len(existing):
        return None
    limit = len(existing) - len(candidate) + 1
    for start in range(limit):
        if existing[start : start + len(candidate)] == candidate:
            return start
    return None


def remove_rer_short_turns(
    items: list[tuple[int, tuple[str, str, tuple[str, ...]]]]
) -> list[tuple[int, tuple[str, str, tuple[str, ...]]]]:
    kept = []
    removed = 0
    for count, key in items:
        route_id, direction_id, stations = key
        is_short_turn = False
        for _other_count, other_key in items:
            other_route_id, other_direction_id, other_stations = other_key
            if route_id != other_route_id or direction_id != other_direction_id:
                continue
            start = contiguous_subsequence_start(stations, other_stations)
            if start is None:
                continue
            terminal_index = start + len(stations) - 1
            if terminal_index < len(other_stations) - 1:
                is_short_turn = True
                break
        if is_short_turn:
            removed += 1
            continue
        kept.append((count, key))
    if removed:
        log(f"removed {removed} RER short-turn trip patterns that are subsets of longer same-direction patterns")
    return kept


def choose_patterns(
    routes: dict[str, dict],
    station_meta: dict[str, dict],
    segment_stats: dict[tuple[str, str, str, str], list[int]],
    pattern_counts: Counter,
    pattern_headsigns: dict[tuple[str, str, tuple[str, ...]], Counter],
    pattern_peak_departures: dict[tuple[str, str, tuple[str, ...]], list[int]],
) -> tuple[dict[str, dict], set[str], dict[str, tuple[str, str, tuple[str, ...]]]]:
    by_route = defaultdict(list)
    for key, count in pattern_counts.items():
        route_id, _direction_id, stations = key
        if route_id in routes and len(stations) > 1:
            by_route[route_id].append((count, key))

    route_segment_fallback = defaultdict(lambda: [0, 0])
    for (route_id, _direction_id, from_station, to_station), stats in segment_stats.items():
        fallback = route_segment_fallback[(route_id, from_station, to_station)]
        fallback[0] += stats[0]
        fallback[1] += stats[1]

    directions = {}
    direction_pattern_keys = {}
    used_stations = set()
    for route_id, items in by_route.items():
        items.sort(reverse=True, key=lambda item: (item[0], len(item[1][2])))
        if routes[route_id]["mode"] == "rer":
            items = remove_rer_short_turns(items)
            by_terminal = defaultdict(list)
            for count, key in items:
                by_terminal[key[2][-1]].append((count, key))
            kept = []
            for terminal_items in by_terminal.values():
                terminal_items.sort(key=lambda item: (len(item[1][2]), item[0]), reverse=True)
                kept.append(terminal_items[0])
            kept.sort(key=lambda item: (-item[0], station_meta.get(item[1][2][-1], {}).get("name", "")))
            kept = kept[:MAX_DIRECTIONS_PER_ROUTE]
        else:
            kept: list[tuple[int, tuple[str, str, tuple[str, ...]]]] = []
            top_count = items[0][0] if items else 0
            minimum = max(2, math.ceil(top_count * 0.015))
            for count, key in items:
                stations = key[2]
                if count < minimum and len(kept) >= 2:
                    continue
                if any(is_subsequence(stations, existing[1][2]) for existing in kept):
                    continue
                kept.append((count, key))
                if len(kept) >= MAX_DIRECTIONS_PER_ROUTE:
                    break

        for index, (count, key) in enumerate(kept):
            route_id, direction_id, stations = key
            headsigns = pattern_headsigns.get(key, Counter())
            headsign = headsigns.most_common(1)[0][0] if headsigns else ""
            terminal_name = station_meta.get(stations[-1], {}).get("name", stations[-1])
            display_label = direction_display_label(routes[route_id]["mode"], headsign, terminal_name)

            runtimes = []
            for from_station, to_station in zip(stations, stations[1:]):
                stats = segment_stats.get((route_id, direction_id, from_station, to_station))
                if stats and stats[1]:
                    runtime = round(stats[0] / stats[1])
                else:
                    fallback = route_segment_fallback.get((route_id, from_station, to_station))
                    runtime = round(fallback[0] / fallback[1]) if fallback and fallback[1] else 90
                runtimes.append(max(10, runtime))

            dir_id = f"{route_id}:{index}"
            directions[dir_id] = {
                "id": dir_id,
                "routeId": route_id,
                "label": display_label,
                "gtfsDirectionId": direction_id,
                "tripPatternCount": count,
                "stations": list(stations),
                "runtimes": runtimes,
            }
            direction_pattern_keys[dir_id] = key
            used_stations.update(stations)

    log(f"kept {len(directions)} playable line/direction patterns")
    return directions, used_stations, direction_pattern_keys


def median_headway_seconds(departures: list[int]) -> int | None:
    times = sorted(set(departures))
    if len(times) < 2:
        return None
    headways = [right - left for left, right in zip(times, times[1:]) if 60 <= right - left <= 7200]
    if not headways:
        return None
    return round(median(headways))


def clamp_wait(seconds: int, mode: str) -> int:
    return max(MIN_WAIT_SECONDS, min(seconds, MAX_WAIT_BY_MODE.get(mode, WAIT_BY_MODE.get(mode, 300))))


def expected_wait_from_departures(departures: list[int], mode: str) -> int | None:
    headway = median_headway_seconds(departures)
    if headway is None:
        return None
    return clamp_wait(round(headway / 2), mode)


def build_waits(
    directions: dict[str, dict],
    routes: dict[str, dict],
    direction_pattern_keys: dict[str, tuple[str, str, tuple[str, ...]]],
    pattern_peak_departures: dict[tuple[str, str, tuple[str, ...]], list[int]],
) -> tuple[dict[str, int], dict[str, int]]:
    route_departures: dict[str, list[int]] = defaultdict(list)
    wait_by_direction: dict[str, int] = {}
    wait_by_route: dict[str, int] = {}

    for dir_id, direction in directions.items():
        route_id = direction["routeId"]
        departures = pattern_peak_departures.get(direction_pattern_keys[dir_id], [])
        route_departures[route_id].extend(departures)
        wait = expected_wait_from_departures(departures, routes[route_id]["mode"])
        if wait is not None:
            wait_by_direction[dir_id] = wait

    for route_id, departures in route_departures.items():
        wait = expected_wait_from_departures(departures, routes[route_id]["mode"])
        if wait is not None:
            wait_by_route[route_id] = wait

    for dir_id, direction in directions.items():
        route_id = direction["routeId"]
        if dir_id not in wait_by_direction and route_id in wait_by_route:
            wait_by_direction[dir_id] = wait_by_route[route_id]

    log(f"derived peak waits for {len(wait_by_direction)} directions and {len(wait_by_route)} routes")
    return wait_by_direction, wait_by_route


def read_transfers(stop_to_station: dict[str, str], used_stations: set[str]) -> dict[str, dict[str, int]]:
    transfer_samples: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for row in read_csv("transfers.txt"):
        from_station = stop_to_station.get(row.get("from_stop_id", ""), row.get("from_stop_id", ""))
        to_station = stop_to_station.get(row.get("to_stop_id", ""), row.get("to_stop_id", ""))
        if from_station not in used_stations or to_station not in used_stations:
            continue
        try:
            seconds = int(row.get("min_transfer_time") or 0)
        except ValueError:
            continue
        if seconds <= 0:
            continue
        transfer_samples[from_station][to_station].append(seconds)
    transfer_times = {
        from_station: {
            to_station: int(round(sum(samples) / len(samples)))
            for to_station, samples in to_stations.items()
        }
        for from_station, to_stations in transfer_samples.items()
    }
    pair_count = sum(len(to_stations) for to_stations in transfer_times.values())
    sample_count = sum(len(samples) for to_stations in transfer_samples.values() for samples in to_stations.values())
    log(f"averaged {sample_count} GTFS transfer rows into {pair_count} station transfer pairs")
    return transfer_times


def read_route_transfers(
    stop_to_station: dict[str, str],
    raw_stop_routes: dict[str, set[str]],
    routes: dict[str, dict],
    used_stations: set[str],
) -> dict[str, dict[str, dict[str, dict[str, int]]]]:
    route_transfers: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    count = 0
    for row in read_csv("transfers.txt"):
        from_stop = row.get("from_stop_id", "")
        to_stop = row.get("to_stop_id", "")
        from_station = stop_to_station.get(from_stop, from_stop)
        to_station = stop_to_station.get(to_stop, to_stop)
        if from_station not in used_stations or to_station not in used_stations:
            continue
        try:
            seconds = int(row.get("min_transfer_time") or 0)
        except ValueError:
            continue
        if seconds <= 0:
            continue

        from_routes = raw_stop_routes.get(from_stop, set()) & routes.keys()
        to_routes = raw_stop_routes.get(to_stop, set()) & routes.keys()
        if not from_routes or not to_routes:
            continue

        for from_route in from_routes:
            for to_route in to_routes:
                old = route_transfers[from_station][to_station][from_route].get(to_route)
                if old is None or seconds < old:
                    route_transfers[from_station][to_station][from_route][to_route] = seconds
                    count += 1

    log(f"kept {count} raw child-stop route-pair transfer minima")
    return {
        from_station: {
            to_station: {from_route: dict(to_routes) for from_route, to_routes in from_routes.items()}
            for to_station, from_routes in to_stations.items()
        }
        for from_station, to_stations in route_transfers.items()
    }


def build_station_equivalents(
    stations: dict[str, dict],
    transfers: dict[str, dict[str, int]],
) -> tuple[dict[str, str], list[list[str]]]:
    parents = {station_id: station_id for station_id in stations}

    def find(station_id: str) -> str:
        parent = parents[station_id]
        if parent != station_id:
            parents[station_id] = find(parent)
        return parents[station_id]

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root == right_root:
            return
        canonical = min(left_root, right_root)
        other = right_root if canonical == left_root else left_root
        parents[other] = canonical

    by_name: dict[str, list[str]] = defaultdict(list)
    for station_id, meta in stations.items():
        normalized = normalized_station_name(meta.get("name", ""))
        if normalized:
            by_name[normalized].append(station_id)

    for ids in by_name.values():
        if len(ids) < 2:
            continue
        sorted_ids = sorted(ids)
        for index, left in enumerate(sorted_ids):
            for right in sorted_ids[index + 1 :]:
                distance = station_distance_m(stations[left], stations[right])
                short_transfer = min(
                    transfers.get(left, {}).get(right, sys.maxsize),
                    transfers.get(right, {}).get(left, sys.maxsize),
                )
                close_enough = distance is not None and distance <= STATION_EQUIVALENCE_DISTANCE_M
                short_enough = short_transfer <= STATION_EQUIVALENCE_TRANSFER_SECONDS
                if close_enough or short_enough:
                    union(left, right)

    grouped: dict[str, list[str]] = defaultdict(list)
    for station_id in sorted(stations):
        grouped[find(station_id)].append(station_id)

    station_equivalents = [ids for ids in grouped.values() if len(ids) > 1]
    canonical_station_ids = {
        station_id: min(ids)
        for ids in station_equivalents
        for station_id in ids
    }
    log(f"built {len(station_equivalents)} station equivalence groups")
    return canonical_station_ids, station_equivalents


class Router:
    def __init__(
        self,
        stations: dict[str, dict],
        routes: dict[str, dict],
        directions: dict[str, dict],
        transfers: dict[str, dict[str, int]],
        route_transfers: dict[str, dict[str, dict[str, dict[str, int]]]],
        wait_by_direction: dict[str, int],
        wait_by_route: dict[str, int],
    ) -> None:
        self.stations = stations
        self.routes = routes
        self.directions = directions
        self.transfers = transfers
        self.route_transfers = route_transfers
        self.wait_by_direction = wait_by_direction
        self.wait_by_route = wait_by_route
        self.nodes: dict[str, dict] = {}
        self.station_nodes: dict[str, list[str]] = defaultdict(list)
        self.adj: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self._build()

    def fallback_transfer(self, from_mode: str, to_mode: str) -> int:
        if from_mode == to_mode:
            return TRANSFER_DEFAULTS["same_mode"]
        pair = {from_mode, to_mode}
        if pair == {"metro", "rer"}:
            return TRANSFER_DEFAULTS["metro_rer"]
        if pair == {"metro", "tram"}:
            return TRANSFER_DEFAULTS["metro_tram"]
        if pair == {"rer", "tram"}:
            return TRANSFER_DEFAULTS["rer_tram"]
        return TRANSFER_DEFAULTS["fallback"]

    def wait_seconds(self, direction_id: str, route_id: str, mode: str) -> int:
        return self.wait_by_direction.get(
            direction_id,
            self.wait_by_route.get(route_id, WAIT_BY_MODE.get(mode, WAIT_BY_MODE["bus"])),
        )

    def transfer_walk(
        self,
        from_station: str,
        to_station: str,
        from_route_id: str,
        to_route_id: str,
        from_mode: str,
        to_mode: str,
    ) -> int | None:
        route_pair = (
            self.route_transfers.get(from_station, {})
            .get(to_station, {})
            .get(from_route_id, {})
            .get(to_route_id)
        )
        if route_pair is not None:
            return route_pair
        if from_station == to_station:
            return self.fallback_transfer(from_mode, to_mode)
        explicit = self.transfers.get(from_station, {}).get(to_station)
        if explicit is not None:
            return explicit
        return None

    def _add_edge(self, left: str, right: str, weight: int) -> None:
        self.adj[left].append((right, weight))

    def _build(self) -> None:
        for direction in self.directions.values():
            route = self.routes[direction["routeId"]]
            for index, station_id in enumerate(direction["stations"]):
                node_id = f"{direction['id']}|{index}"
                self.nodes[node_id] = {
                    "id": node_id,
                    "dirId": direction["id"],
                    "routeId": direction["routeId"],
                    "stationId": station_id,
                    "mode": route["mode"],
                    "index": index,
                }
                self.station_nodes[station_id].append(node_id)
            for index, runtime in enumerate(direction["runtimes"]):
                self._add_edge(f"{direction['id']}|{index}", f"{direction['id']}|{index + 1}", runtime)

        for from_node, node in self.nodes.items():
            from_station = node["stationId"]
            targets = {from_station}
            targets.update(self.transfers.get(from_station, {}).keys())
            targets.update(self.route_transfers.get(from_station, {}).keys())
            for to_station in targets:
                for to_node in self.station_nodes.get(to_station, []):
                    target = self.nodes[to_node]
                    if target["dirId"] == node["dirId"]:
                        continue
                    walk = self.transfer_walk(
                        from_station,
                        to_station,
                        node["routeId"],
                        target["routeId"],
                        node["mode"],
                        target["mode"],
                    )
                    if walk is None:
                        continue
                    self._add_edge(
                        from_node,
                        to_node,
                        walk + self.wait_seconds(target["dirId"], target["routeId"], target["mode"]),
                    )
        edge_count = sum(len(v) for v in self.adj.values())
        log(f"routing graph: {len(self.nodes)} nodes, {edge_count} directed edges")

    def neighbors(self, node_id: str, extra_edges: dict[str, list[tuple[str, int]]]):
        if node_id in extra_edges:
            yield from extra_edges[node_id]
        yield from self.adj.get(node_id, [])

    def dijkstra(
        self,
        source: str,
        target: str,
        extra_edges: dict[str, list[tuple[str, int]]],
    ) -> tuple[int, list[str]] | None:
        queue = [(0, source)]
        best = {source: 0}
        previous: dict[str, str] = {}
        while queue:
            cost, node = heapq.heappop(queue)
            if node == target:
                path = [target]
                while path[-1] != source:
                    path.append(previous[path[-1]])
                path.reverse()
                return cost, path
            if cost != best.get(node):
                continue
            for next_node, weight in self.neighbors(node, extra_edges):
                new_cost = cost + weight
                if new_cost < best.get(next_node, sys.maxsize):
                    best[next_node] = new_cost
                    previous[next_node] = node
                    heapq.heappush(queue, (new_cost, next_node))
        return None

    def fastest_path(self, start_station: str, end_station: str) -> tuple[int, list[str]] | None:
        source = "__start__"
        target = "__end__"
        extra_edges: dict[str, list[tuple[str, int]]] = defaultdict(list)
        for node_id in self.station_nodes.get(start_station, []):
            node = self.nodes[node_id]
            extra_edges[source].append((node_id, self.wait_seconds(node["dirId"], node["routeId"], node["mode"])))
        for node_id in self.station_nodes.get(end_station, []):
            extra_edges[node_id].append((target, 0))

        return self.dijkstra(source, target, extra_edges)

    def runtime_between(self, direction_id: str, from_station: str, to_station: str) -> int | None:
        direction = self.directions[direction_id]
        try:
            from_index = direction["stations"].index(from_station)
            to_index = direction["stations"].index(to_station)
        except ValueError:
            return None
        if to_index <= from_index:
            return None
        return sum(direction["runtimes"][from_index:to_index])

    def add_timing_breakdown(
        self,
        legs: list[dict],
        route_nodes: list[str] | None = None,
        leg_start_indices: list[int] | None = None,
        leg_end_indices: list[int] | None = None,
    ) -> dict[str, int]:
        totals = {"rideSec": 0, "waitSec": 0, "transferSec": 0}
        previous = None
        for leg_index, leg in enumerate(legs):
            route = self.routes[leg["routeId"]]
            ride_sec = self.runtime_between(leg["directionId"], leg["from"], leg["to"])
            if ride_sec is None:
                ride_sec = 0
            wait_sec = 0
            transfer_sec = 0
            if route_nodes is not None and leg_start_indices is not None and leg_end_indices is not None:
                start_index = leg_start_indices[leg_index]
                previous_end_index = leg_end_indices[leg_index - 1] if leg_index > 0 else None
                if previous_end_index is None:
                    first_node = self.nodes[route_nodes[0]]
                    wait_sec += self.wait_seconds(first_node["dirId"], first_node["routeId"], first_node["mode"])
                    transition_start = 1
                else:
                    transition_start = previous_end_index + 1
                for route_node_index in range(transition_start, start_index + 1):
                    from_node = self.nodes[route_nodes[route_node_index - 1]]
                    to_node = self.nodes[route_nodes[route_node_index]]
                    if from_node["dirId"] == to_node["dirId"]:
                        hidden_ride = self.runtime_between(
                            from_node["dirId"],
                            from_node["stationId"],
                            to_node["stationId"],
                        )
                        ride_sec += hidden_ride if hidden_ride is not None else 0
                        continue
                    to_route = self.routes[to_node["routeId"]]
                    transfer = self.transfer_walk(
                        from_node["stationId"],
                        to_node["stationId"],
                        from_node["routeId"],
                        to_node["routeId"],
                        from_node["mode"],
                        to_node["mode"],
                    )
                    transfer_sec += transfer if transfer is not None else 0
                    wait_sec += self.wait_seconds(to_node["dirId"], to_node["routeId"], to_route["mode"])
            elif previous is not None:
                wait_sec = self.wait_seconds(leg["directionId"], leg["routeId"], route["mode"])
                previous_route = self.routes[previous["routeId"]]
                transfer = self.transfer_walk(
                    previous["to"],
                    leg["from"],
                    previous["routeId"],
                    leg["routeId"],
                    previous_route["mode"],
                    route["mode"],
                )
                transfer_sec = transfer if transfer is not None else 0
            else:
                wait_sec = self.wait_seconds(leg["directionId"], leg["routeId"], route["mode"])
            leg["rideSec"] = int(ride_sec)
            leg["waitSec"] = int(wait_sec)
            leg["transferSec"] = int(transfer_sec)
            leg["elapsedSec"] = leg["rideSec"] + leg["waitSec"] + leg["transferSec"]
            totals["rideSec"] += leg["rideSec"]
            totals["waitSec"] += leg["waitSec"]
            totals["transferSec"] += leg["transferSec"]
            previous = leg
        return totals

    def connection_breakdown(self, route_nodes: list[str], from_index: int, to_index: int) -> dict[str, int]:
        totals = {"rideSec": 0, "waitSec": 0, "transferSec": 0}
        for route_node_index in range(from_index + 1, to_index + 1):
            from_node = self.nodes[route_nodes[route_node_index - 1]]
            to_node = self.nodes[route_nodes[route_node_index]]
            if from_node["dirId"] == to_node["dirId"]:
                ride_sec = self.runtime_between(
                    from_node["dirId"],
                    from_node["stationId"],
                    to_node["stationId"],
                )
                totals["rideSec"] += ride_sec if ride_sec is not None else 0
                continue
            to_route = self.routes[to_node["routeId"]]
            transfer = self.transfer_walk(
                from_node["stationId"],
                to_node["stationId"],
                from_node["routeId"],
                to_node["routeId"],
                from_node["mode"],
                to_node["mode"],
            )
            totals["transferSec"] += transfer if transfer is not None else 0
            totals["waitSec"] += self.wait_seconds(to_node["dirId"], to_node["routeId"], to_route["mode"])
        return totals

    def describe_path(self, cost: int, path: list[str]) -> dict | None:
        route_nodes = [node for node in path if node in self.nodes]
        if not route_nodes:
            return None
        steps = []
        legs = []
        totals = {"rideSec": 0, "waitSec": 0, "transferSec": 0}
        pending_wait = self.wait_seconds(
            self.nodes[route_nodes[0]]["dirId"],
            self.nodes[route_nodes[0]]["routeId"],
            self.nodes[route_nodes[0]]["mode"],
        )
        pending_transfer = 0
        current_ride = None

        def flush_ride() -> None:
            nonlocal current_ride
            if current_ride is None:
                return
            current_ride["rideSec"] = int(current_ride["rideSec"])
            current_ride["waitSec"] = int(current_ride["waitSec"])
            current_ride["transferSec"] = int(current_ride["transferSec"])
            current_ride["elapsedSec"] = (
                current_ride["rideSec"] + current_ride["waitSec"] + current_ride["transferSec"]
            )
            steps.append(current_ride)
            legs.append(current_ride)
            totals["rideSec"] += current_ride["rideSec"]
            totals["waitSec"] += current_ride["waitSec"]
            totals["transferSec"] += current_ride["transferSec"]
            current_ride = None

        for route_node_index in range(1, len(route_nodes)):
            from_node = self.nodes[route_nodes[route_node_index - 1]]
            to_node = self.nodes[route_nodes[route_node_index]]
            if from_node["dirId"] == to_node["dirId"]:
                if current_ride is None:
                    direction = self.directions[from_node["dirId"]]
                    route = self.routes[direction["routeId"]]
                    current_ride = {
                        "type": "ride",
                        "routeId": route["id"],
                        "line": route["label"],
                        "mode": route["mode"],
                        "color": route["color"],
                        "textColor": route["textColor"],
                        "directionId": direction["id"],
                        "direction": direction["label"],
                        "from": from_node["stationId"],
                        "to": from_node["stationId"],
                        "rideSec": 0,
                        "waitSec": pending_wait,
                        "transferSec": pending_transfer,
                    }
                    pending_wait = 0
                    pending_transfer = 0
                hidden_ride = self.runtime_between(
                    from_node["dirId"],
                    from_node["stationId"],
                    to_node["stationId"],
                )
                current_ride["rideSec"] += hidden_ride if hidden_ride is not None else 0
                current_ride["to"] = to_node["stationId"]
                continue

            flush_ride()
            to_route = self.routes[to_node["routeId"]]
            transfer = self.transfer_walk(
                from_node["stationId"],
                to_node["stationId"],
                from_node["routeId"],
                to_node["routeId"],
                from_node["mode"],
                to_node["mode"],
            )
            pending_transfer += transfer if transfer is not None else 0
            pending_wait += self.wait_seconds(to_node["dirId"], to_node["routeId"], to_route["mode"])
            if from_node["stationId"] != to_node["stationId"] and transfer is not None:
                walk_step = {
                    "type": "walk",
                    "from": from_node["stationId"],
                    "to": to_node["stationId"],
                    "rideSec": 0,
                    "waitSec": 0,
                    "transferSec": int(transfer),
                    "elapsedSec": int(transfer),
                }
                steps.append(walk_step)
                totals["transferSec"] += walk_step["transferSec"]
                pending_transfer -= transfer

        flush_ride()
        if pending_wait or pending_transfer:
            # A route may end after a transfer edge into the destination station.
            # Keep the graph cost visible without inventing a zero-length ride.
            if steps:
                steps[-1]["transferSec"] += int(pending_transfer + pending_wait)
                steps[-1]["elapsedSec"] += int(pending_transfer + pending_wait)
                totals["transferSec"] += int(pending_transfer + pending_wait)
            pending_wait = 0
            pending_transfer = 0

        if not legs:
            return None

        total_from_steps = sum(step["elapsedSec"] for step in steps)
        if total_from_steps != int(cost) and steps:
            delta = int(cost) - total_from_steps
            steps[-1]["transferSec"] += delta
            steps[-1]["elapsedSec"] += delta
            totals["transferSec"] += delta
        return {
            "totalSec": int(cost),
            "rideSec": totals["rideSec"],
            "waitSec": totals["waitSec"],
            "transferSec": totals["transferSec"],
            "transferCount": max(0, len(legs) - 1),
            "signature": "|".join(
                (
                    f"walk:{step['from']}:{step['to']}"
                    if step.get("type") == "walk"
                    else f"ride:{step['routeId']}:{step['directionId']}:{step['from']}:{step['to']}"
                )
                for step in steps
            ),
            "legs": legs,
            "steps": steps,
        }


def build_station_services(stations: dict[str, dict], routes: dict[str, dict], directions: dict[str, dict]) -> None:
    for station in stations.values():
        station["services"] = {}
    for direction in directions.values():
        route_id = direction["routeId"]
        for index, station_id in enumerate(direction["stations"][:-1]):
            stations[station_id]["services"].setdefault(route_id, set()).add(direction["id"])
    for station in stations.values():
        station["services"] = {route_id: sorted(values) for route_id, values in station["services"].items()}
        station["modes"] = sorted({routes[route_id]["mode"] for route_id in station["services"]})


def is_central_rer_station(station: dict) -> bool:
    lat = station.get("lat")
    lon = station.get("lon")
    return (
        isinstance(lat, (int, float))
        and isinstance(lon, (int, float))
        and PARIS_CITY_BOUNDS["min_lat"] <= lat <= PARIS_CITY_BOUNDS["max_lat"]
        and PARIS_CITY_BOUNDS["min_lon"] <= lon <= PARIS_CITY_BOUNDS["max_lon"]
    )


def is_puzzle_endpoint(station: dict) -> bool:
    modes = set(station.get("modes", []))
    return "metro" in modes or ("rer" in modes and is_central_rer_station(station))


def optimal_route_edge_count(optimal_route: dict, directions: dict[str, dict]) -> int:
    edge_count = 0
    for leg in optimal_route["legs"]:
        stations = directions[leg["directionId"]]["stations"]
        from_index = stations.index(leg["from"])
        to_index = stations.index(leg["to"])
        edge_count += to_index - from_index
    return edge_count


def optimal_route_distance_m(optimal_route: dict, directions: dict[str, dict], stations: dict[str, dict]) -> float | None:
    total = 0.0
    for leg in optimal_route["legs"]:
        direction_stations = directions[leg["directionId"]]["stations"]
        from_index = direction_stations.index(leg["from"])
        to_index = direction_stations.index(leg["to"])
        for left_id, right_id in zip(
            direction_stations[from_index:to_index],
            direction_stations[from_index + 1 : to_index + 1],
        ):
            distance = station_distance_m(stations[left_id], stations[right_id])
            if distance is None:
                return None
            total += distance
    return total


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "0": "tram-like; kept labels beginning T only",
        "1": "metro; kept all",
        "2": "rail; kept RER A-E only",
        "3": "bus; excluded for v1",
        "6": "aerial lift/funicular-like; excluded",
        "7": "funicular-like; excluded",
    }


def network_metadata(
    wait_by_direction: dict[str, int],
    wait_by_route: dict[str, int],
    extra: dict | None = None,
) -> dict:
    metadata = {
        "title": "MÃ©tro Express",
        **read_feed_metadata(),
        "routeTypeMappingVerified": route_type_mapping_metadata(),
        "transferFallbackSeconds": TRANSFER_DEFAULTS,
        "waitSecondsByMode": WAIT_BY_MODE,
        "waitSecondsByDirection": wait_by_direction,
        "waitSecondsByRoute": wait_by_route,
        "peakHeadwayWindow": {
            "days": "typical weekday service from calendar.txt",
            "start": "07:00:00",
            "end": "10:00:00",
            "expectedWait": "round(median_peak_headway / 2), clamped by mode",
        },
        "notes": [
            "Consecutive in-vehicle runtimes are averaged from stop_times.txt across selected trips.",
            "Station-pair transfer times average raw transfers.txt child-stop rows after station collapse.",
            "Route-pair transfer times use raw transfers.txt child-stop route-pair minimums before station collapse.",
            "Waits use half of derived median scheduled peak headway, with direction, route, then mode fallbacks.",
            "No pathways.txt, disruptions, live data, or time-of-day routing are used.",
            "Puzzle endpoints are restricted to metro-served stations plus RER stations within Paris city bounds.",
            "Candidate pairs are ordered: A -> B and B -> A are distinct.",
            "Bus routes are excluded for v1.",
        ],
    }
    if extra:
        metadata.update(extra)
    return metadata


def build_network() -> tuple[dict, Router, list[str], dict[str, int]]:
    routes = read_routes()
    stop_to_station, all_station_meta = read_stops()
    weekday_services = read_weekday_services()
    trips = read_trips(routes)
    segment_stats, pattern_counts, pattern_headsigns, pattern_peak_departures, raw_stop_routes = read_stop_times(
        trips, stop_to_station, weekday_services
    )
    directions, used_stations, direction_pattern_keys = choose_patterns(
        routes, all_station_meta, segment_stats, pattern_counts, pattern_headsigns, pattern_peak_departures
    )

    stations = {station_id: all_station_meta[station_id] for station_id in sorted(used_stations)}
    build_station_services(stations, routes, directions)
    transfers = read_transfers(stop_to_station, set(stations))
    canonical_station_ids, station_equivalents = build_station_equivalents(stations, transfers)

    used_routes = sorted({direction["routeId"] for direction in directions.values()})
    routes = {route_id: routes[route_id] for route_id in used_routes}
    wait_by_direction, wait_by_route = build_waits(directions, routes, direction_pattern_keys, pattern_peak_departures)
    route_transfers = read_route_transfers(stop_to_station, raw_stop_routes, routes, set(stations))

    router = Router(stations, routes, directions, transfers, route_transfers, wait_by_direction, wait_by_route)
    endpoint_ids = sorted(
        station_id
        for station_id, station in stations.items()
        if station.get("services") and is_puzzle_endpoint(station)
    )
    total_ordered_pairs = sum(
        1
        for start in endpoint_ids
        for end in endpoint_ids
        if start != end and stations[start]["name"] != stations[end]["name"]
    )
    log(f"candidate puzzle endpoints after central filter: {len(endpoint_ids)}")
    log(f"ordered candidate pairs after same-name exclusion: {total_ordered_pairs:,}")

    data = {
        "metadata": network_metadata(wait_by_direction, wait_by_route, {"kind": "network"}),
        "routes": routes,
        "directions": directions,
        "stations": stations,
        "canonicalStationIds": canonical_station_ids,
        "stationEquivalents": station_equivalents,
        "transfers": transfers,
        "routeTransfers": route_transfers,
    }
    summary = {
        "selectedRouteCount": len(routes),
        "directionCount": len(directions),
        "stationCount": len(stations),
        "candidateEndpointCount": len(endpoint_ids),
        "orderedCandidatePairsConsidered": total_ordered_pairs,
    }
    return data, router, endpoint_ids, summary


def playable_reasons(
    fastest: tuple[int, list[str]] | None,
    optimal_route: dict | None,
    endpoint_distance_m: float | None,
    route_distance_m: float | None,
    transit_edge_count: int,
) -> list[str]:
    reasons = []
    if not fastest or not optimal_route:
        reasons.append("unroutable")
    if endpoint_distance_m is None or endpoint_distance_m < MIN_PUZZLE_ENDPOINT_DISTANCE_M:
        reasons.append("endpoint_distance_under_1500m")
    if route_distance_m is None or route_distance_m < MIN_PUZZLE_ROUTE_DISTANCE_M:
        reasons.append("route_distance_under_1000m")
    if transit_edge_count <= 3:
        reasons.append("fewer_than_4_transit_edges")
    if not optimal_route or optimal_route.get("transferCount", 0) < 1:
        reasons.append("no_transfer_required")
    return reasons


def build_candidate_pair(router: Router, stations: dict[str, dict], start: str, end: str) -> dict:
    endpoint_distance_m = station_distance_m(stations[start], stations[end])
    fastest = router.fastest_path(start, end)
    optimal_route = router.describe_path(*fastest) if fastest else None
    transit_edge_count = optimal_route_edge_count(optimal_route, router.directions) if optimal_route else 0
    route_distance_m = optimal_route_distance_m(optimal_route, router.directions, stations) if optimal_route else None
    reasons = playable_reasons(fastest, optimal_route, endpoint_distance_m, route_distance_m, transit_edge_count)
    return {
        "id": f"pair:{start}:{end}",
        "start": start,
        "end": end,
        "endpointDistanceM": round(endpoint_distance_m) if endpoint_distance_m is not None else None,
        "routeDistanceM": round(route_distance_m) if route_distance_m is not None else None,
        "transitEdgeCount": transit_edge_count,
        "transferCount": optimal_route.get("transferCount", 0) if optimal_route else 0,
        "routable": bool(optimal_route),
        "playable": not reasons,
        "unplayableReasons": reasons,
        "optimalRoute": optimal_route or {},
    }


def build_all_pairs(router: Router, stations: dict[str, dict], endpoint_ids: list[str]) -> tuple[list[dict], Counter]:
    pairs = []
    reason_counts: Counter[str] = Counter()
    considered = 0
    for start in endpoint_ids:
        for end in endpoint_ids:
            if start == end or stations[start]["name"] == stations[end]["name"]:
                continue
            considered += 1
            pair = build_candidate_pair(router, stations, start, end)
            pairs.append(pair)
            reason_counts.update(pair["unplayableReasons"])
            if considered % ALL_PAIRS_PROGRESS_INTERVAL == 0:
                log(f"computed {considered:,} ordered candidate pairs")
    return pairs, reason_counts


def pair_line_ids(pair: dict) -> set[str]:
    return {leg["routeId"] for leg in pair.get("optimalRoute", {}).get("legs", []) if leg.get("routeId")}


def distance_bucket(pair: dict) -> int:
    return min(5, int((pair.get("routeDistanceM") or 0) // 2500))


def select_varied_playable(pairs: list[dict], count: int, seed: str) -> list[dict]:
    playable = [pair for pair in pairs if pair.get("playable")]
    rng = random.Random(seed)
    shuffled = playable[:]
    rng.shuffle(shuffled)
    selected = []
    used_station_ids: set[str] = set()
    used_unordered: set[tuple[str, str]] = set()

    def take(require_unused_stations: bool) -> None:
        for pair in playable:
            if pair in selected:
                continue
            unordered = tuple(sorted([pair["start"], pair["end"]]))
            if unordered in used_unordered:
                continue
            if require_unused_stations and (pair["start"] in used_station_ids or pair["end"] in used_station_ids):
                continue
            selected.append(pair)
            used_station_ids.update([pair["start"], pair["end"]])
            used_unordered.add(unordered)
            if len(selected) >= count:
                return

    playable = shuffled
    take(require_unused_stations=True)
    if len(selected) < count:
        take(require_unused_stations=False)

    if len(selected) < count:
        raise RuntimeError(f"only selected {len(selected)} playable pairs; need {count}")
    return selected


def select_example_pairs(pairs: list[dict], count: int) -> list[dict]:
    playable_count = min(count, max(0, count - 10))
    selected = select_varied_playable(pairs, playable_count, "metro-express-example-v1")
    selected_ids = {pair["id"] for pair in selected}
    non_playable = [
        pair
        for pair in sorted(pairs, key=lambda item: item["id"])
        if not pair.get("playable") and pair["id"] not in selected_ids
    ]
    selected.extend(non_playable[: max(0, count - len(selected))])
    selected_ids = {pair["id"] for pair in selected}
    selected.extend(pair for pair in sorted(pairs, key=lambda item: item["id"]) if pair["id"] not in selected_ids)
    return selected[:count]


def daily_metadata(day: date, count: int) -> dict:
    return {
        "title": "MÃ©tro Express",
        "kind": "daily-puzzles",
        "date": day.isoformat(),
        "pairCount": count,
        **read_feed_metadata(),
    }


def example_metadata(count: int) -> dict:
    return {
        "title": "MÃ©tro Express",
        "kind": "example-dev-puzzles",
        "pairCount": count,
        "description": "Committed example/dev dataset for schema checks and local fallback; not the daily puzzle pool.",
        **read_feed_metadata(),
    }


def all_pairs_metadata(pairs: list[dict], reason_counts: Counter) -> dict:
    routable_count = sum(1 for pair in pairs if pair.get("routable"))
    playable_count = sum(1 for pair in pairs if pair.get("playable"))
    return {
        "title": "MÃ©tro Express",
        "kind": "all-candidate-pairs",
        "ordered": True,
        "pairCount": len(pairs),
        "routablePairs": routable_count,
        "playablePairs": playable_count,
        "nonPlayablePairs": len(pairs) - playable_count,
        "unplayableReasonCounts": dict(sorted(reason_counts.items())),
        **read_feed_metadata(),
    }


def write_network(data: dict) -> None:
    write_json(NETWORK_OUT, data)
    log(f"wrote {NETWORK_OUT} ({file_size_mb(NETWORK_OUT):.2f} MB)")


def write_all_pairs(pairs: list[dict], reason_counts: Counter) -> None:
    data = {"metadata": all_pairs_metadata(pairs, reason_counts), "puzzles": pairs}
    write_json(ALL_PAIRS_OUT, data)
    log(f"wrote {ALL_PAIRS_OUT} ({file_size_mb(ALL_PAIRS_OUT):.2f} MB)")


def write_example(pairs: list[dict], count: int) -> None:
    selected = select_example_pairs(pairs, count)
    data = {"metadata": example_metadata(len(selected)), "puzzles": selected}
    write_json(EXAMPLE_OUT, data)
    log(f"wrote {EXAMPLE_OUT} ({file_size_mb(EXAMPLE_OUT):.2f} MB)")


def write_daily_range(pairs: list[dict], start_date: str, days: int, count: int) -> None:
    start = date.fromisoformat(start_date)
    dates = []
    for offset in range(days):
        day = start + timedelta(days=offset)
        dates.append(day.isoformat())
        selected = select_varied_playable(pairs, count, f"metro-express-daily:{day.isoformat()}")
        data = {"metadata": daily_metadata(day, len(selected)), "puzzles": selected}
        write_json(DAILY_DIR / f"{day.isoformat()}.json", data)
    index = {
        "metadata": {
            "title": "MÃ©tro Express",
            "kind": "daily-puzzle-index",
            "startDate": dates[0] if dates else None,
            "endDate": dates[-1] if dates else None,
            "dayCount": len(dates),
            **read_feed_metadata(),
        },
        "dates": dates,
    }
    write_json(DAILY_INDEX_OUT, index)
    total_bytes = sum(path.stat().st_size for path in DAILY_DIR.glob("*.json"))
    log(f"wrote {days} daily files and index to {DAILY_DIR} ({total_bytes / (1024 * 1024):.2f} MB total)")


def load_all_pairs() -> tuple[list[dict], Counter] | None:
    if not ALL_PAIRS_OUT.exists():
        return None
    data = json.loads(ALL_PAIRS_OUT.read_text(encoding="utf-8"))
    pairs = data.get("puzzles", [])
    reason_counts: Counter[str] = Counter()
    for pair in pairs:
        reason_counts.update(pair.get("unplayableReasons", []))
    log(f"loaded {len(pairs):,} candidate pairs from {ALL_PAIRS_OUT}")
    return pairs, reason_counts


def load_network_summary() -> dict[str, int]:
    if not NETWORK_OUT.exists():
        return {}
    data = json.loads(NETWORK_OUT.read_text(encoding="utf-8"))
    stations = data.get("stations", {})
    endpoint_count = sum(1 for station in stations.values() if station.get("services") and is_puzzle_endpoint(station))
    return {
        "selectedRouteCount": len(data.get("routes", {})),
        "directionCount": len(data.get("directions", {})),
        "stationCount": len(stations),
        "candidateEndpointCount": endpoint_count,
        "orderedCandidatePairsConsidered": 0,
    }


def summarize(summary: dict[str, int], pairs: list[dict] | None = None, reason_counts: Counter | None = None) -> None:
    log("summary:")
    log(f"  selected routes: {summary.get('selectedRouteCount', 0):,}")
    log(f"  directions: {summary.get('directionCount', 0):,}")
    log(f"  stations: {summary.get('stationCount', 0):,}")
    log(f"  candidate endpoints: {summary.get('candidateEndpointCount', 0):,}")
    ordered_count = summary.get("orderedCandidatePairsConsidered", 0) or (len(pairs) if pairs is not None else 0)
    log(f"  ordered candidate pairs considered: {ordered_count:,}")
    if pairs is None:
        return
    routable_count = sum(1 for pair in pairs if pair.get("routable"))
    playable_count = sum(1 for pair in pairs if pair.get("playable"))
    log(f"  routable pairs: {routable_count:,}")
    log(f"  playable pairs: {playable_count:,}")
    log(f"  non-playable pairs: {len(pairs) - playable_count:,}")
    if reason_counts:
        log(f"  unplayable reason counts: {dict(sorted(reason_counts.items()))}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build Metro Express static data from local GTFS.")
    parser.add_argument(
        "--mode",
        choices=["network", "all-pairs", "example", "daily-range", "release"],
        default="release",
        help="Output mode. release writes network, ignored all-pairs, example, and daily files.",
    )
    parser.add_argument("--start-date", default=DEFAULT_START_DATE)
    parser.add_argument("--days", type=int, default=DEFAULT_DAYS)
    parser.add_argument("--count", type=int, default=None, help="Pair count for example or daily-range modes.")
    parser.add_argument("--daily-count", type=int, default=DEFAULT_DAILY_COUNT)
    parser.add_argument("--example-count", type=int, default=DEFAULT_EXAMPLE_COUNT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.mode in {"example", "daily-range"} and NETWORK_OUT.exists():
        loaded = load_all_pairs()
        if loaded:
            pairs, reason_counts = loaded
            if args.mode == "example":
                write_example(pairs, args.count or DEFAULT_EXAMPLE_COUNT)
            else:
                write_daily_range(pairs, args.start_date, args.days, args.count or DEFAULT_DAILY_COUNT)
            summarize(load_network_summary(), pairs, reason_counts)
            return

    network, router, endpoint_ids, summary = build_network()
    write_network(network)

    pairs: list[dict] | None = None
    reason_counts: Counter[str] | None = None
    if args.mode in {"all-pairs", "example", "daily-range", "release"}:
        loaded = None if args.mode in {"all-pairs", "release"} else load_all_pairs()
        if loaded:
            pairs, reason_counts = loaded
        else:
            pairs, reason_counts = build_all_pairs(router, network["stations"], endpoint_ids)
            write_all_pairs(pairs, reason_counts)

    if args.mode == "example":
        write_example(pairs or [], args.count or DEFAULT_EXAMPLE_COUNT)
    elif args.mode == "daily-range":
        write_daily_range(pairs or [], args.start_date, args.days, args.count or DEFAULT_DAILY_COUNT)
    elif args.mode == "release":
        write_example(pairs or [], args.example_count)
        write_daily_range(pairs or [], args.start_date, args.days, args.daily_count)

    summarize(summary, pairs, reason_counts)


if __name__ == "__main__":
    main()
