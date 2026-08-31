"""Normalize the TfL Unified API snapshot into Chronométro's shared schema."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import median


LINE_COLOURS = {
    "bakerloo": ("#B26300", "#FFFFFF"),
    "central": ("#DC241F", "#FFFFFF"),
    "circle": ("#FFC80A", "#000000"),
    "district": ("#007D32", "#FFFFFF"),
    "dlr": ("#00A4A7", "#000000"),
    "elizabeth": ("#60399E", "#FFFFFF"),
    "hammersmith-city": ("#F589A6", "#000000"),
    "jubilee": ("#838D93", "#000000"),
    "metropolitan": ("#9B0058", "#FFFFFF"),
    "northern": ("#000000", "#FFFFFF"),
    "piccadilly": ("#0019A8", "#FFFFFF"),
    "victoria": ("#039BE5", "#000000"),
    "waterloo-city": ("#76D0BD", "#000000"),
}


def route_label(row: dict[str, str]) -> str:
    return row.get("name") or row.get("id") or ""


def canonical_mode(row: dict[str, str]) -> str | None:
    return {"tube": "tube", "elizabeth-line": "elizabeth", "dlr": "dlr"}.get(row.get("modeName"))


def direction_display_label(mode: str, headsign: str, terminal_name: str) -> str:
    return terminal_name


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "tube": "included",
        "elizabeth-line": "included",
        "dlr": "included",
        "overground/tram": "excluded",
    }


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def clean_station_name(value: str) -> str:
    value = re.sub(r"\s+(Underground|Rail|DLR) Station$", "", value or "")
    value = re.sub(r"\s*\((?:H\s*&\s*C|Circle) Line\)(?:-Underground)?$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*\(London\)$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"-Underground$", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^London (?=(?:Paddington|Liverpool Street)$)", "", value, flags=re.IGNORECASE)
    return value.strip()


def feed_metadata(root: Path, config: dict) -> dict[str, str]:
    metadata = load_json(root / config["source"]["directory"] / "metadata.json")
    completed = metadata.get("snapshotCompletedAt", "")
    snapshot_date = completed[:10] if completed else "unknown"
    return {
        "generatedFrom": config["source"]["directory"],
        "publisher": config["source"]["publisher"],
        "feedVersion": completed or "unknown",
        "feedValidFrom": snapshot_date,
        "feedValidTo": snapshot_date,
    }


def schedule_departures(schedules: list[dict], interval_id: int | None = None) -> list[int]:
    departures = []
    for schedule in schedules:
        name = (schedule.get("name") or "").casefold()
        if "monday" not in name and name != "friday":
            continue
        for journey in schedule.get("knownJourneys", []):
            if interval_id is not None and journey.get("intervalId") != interval_id:
                continue
            try:
                departures.append(int(journey["hour"]) * 3600 + int(journey["minute"]) * 60)
            except (KeyError, TypeError, ValueError):
                continue
    return departures


def weekday_departures(payload: dict) -> list[int]:
    return [
        departure
        for route in payload.get("timetable", {}).get("routes", [])
        for departure in schedule_departures(route.get("schedules", []))
    ]


def peak_headways(departures: list[int], config: dict) -> list[int]:
    """Return headways from one timetable without mixing clocks at different stops."""
    timing = config["timing"]
    peak = sorted(
        set(value for value in departures if timing["peakStartSeconds"] <= value < timing["peakEndSeconds"])
    )
    return [right - left for left, right in zip(peak, peak[1:]) if right > left]


def wait_from_headways(headways: list[int], mode: str, config: dict) -> int | None:
    if not headways:
        return None
    timing = config["timing"]
    mode_config = config["modes"][mode]
    return max(
        timing["minimumWaitSeconds"],
        min(mode_config["maximumWaitSeconds"], round(median(headways) / 2)),
    )


def scheduled_timing(source: Path, line_modes: dict[str, str], config: dict):
    segments: dict[tuple[str, str, str, str], set[int]] = defaultdict(set)
    headways: dict[tuple[str, str], list[int]] = defaultdict(list)
    pattern_headways: dict[tuple[str, str, tuple[str, ...]], list[int]] = defaultdict(list)
    usable_files = 0
    for path in source.glob("lines/*/timetables/*.json"):
        line_id = path.parent.parent.name
        if line_modes.get(line_id) not in {"tube", "dlr"}:
            continue
        payload = load_json(path)
        routes = payload.get("timetable", {}).get("routes", [])
        direction = payload.get("direction")
        departure_id = payload.get("timetable", {}).get("departureStopId")
        if not routes or not direction or not departure_id:
            continue
        usable_files += 1
        # A timetable is anchored at one departure stop. Pooling absolute clock
        # times across stops makes departures appear one minute apart even when
        # each stop has a normal multi-minute service interval.
        headways[(line_id, direction)].extend(peak_headways(weekday_departures(payload), config))
        for route in routes:
            for interval_set in route.get("stationIntervals", []):
                route_headways = peak_headways(
                    schedule_departures(route.get("schedules", []), interval_set.get("id")), config
                )
                ids = [departure_id] + [item.get("stopId") for item in interval_set.get("intervals", [])]
                minutes = [0.0] + [item.get("timeToArrival") for item in interval_set.get("intervals", [])]
                collapsed = []
                for station_id, minute in zip(ids, minutes):
                    if not station_id or not isinstance(minute, (int, float)):
                        continue
                    if collapsed and collapsed[-1][0] == station_id:
                        collapsed[-1] = (station_id, max(collapsed[-1][1], minute))
                    else:
                        collapsed.append((station_id, minute))
                for (left, left_minute), (right, right_minute) in zip(collapsed, collapsed[1:]):
                    runtime = round((right_minute - left_minute) * 60)
                    if runtime > 0:
                        segments[(line_id, direction, left, right)].add(runtime)
                if len(collapsed) >= 2 and route_headways:
                    path = tuple(station_id for station_id, _ in collapsed)
                    pattern_headways[(line_id, direction, path)].extend(route_headways)
    return segments, headways, pattern_headways, usable_files


def elizabeth_timing(source: Path) -> dict[tuple[str, str], int]:
    result = {}
    for path in source.glob("lines/elizabeth/journeys/*.json"):
        from_id, to_id = path.stem.split("--", 1)
        durations = []
        for journey in load_json(path).get("journeys", []):
            legs = journey.get("legs", [])
            transit = [leg for leg in legs if leg.get("mode", {}).get("id") == "elizabeth-line"]
            if len(legs) == 1 and len(transit) == 1 and transit[0].get("duration", 0) > 0:
                durations.append(int(transit[0]["duration"]) * 60)
        if durations:
            result[(from_id, to_id)] = round(median(durations))
    return result


def source_station_records(source: Path, line_ids: list[str]) -> tuple[dict[str, dict], dict[str, str]]:
    stations = {}
    hubs = {}
    for line_id in line_ids:
        for item in load_json(source / "lines" / line_id / "stop-points.json"):
            station_id = item.get("id")
            if not station_id:
                continue
            record = stations.setdefault(
                station_id,
                {
                    "id": station_id,
                    "name": clean_station_name(item.get("commonName") or station_id),
                    "lat": item.get("lat"),
                    "lon": item.get("lon"),
                },
            )
            hubs.setdefault(station_id, station_id)
    for line_id in line_ids:
        for direction_name in ("inbound", "outbound"):
            payload = load_json(source / "lines" / line_id / f"sequence-{direction_name}.json")
            for sequence in payload.get("stopPointSequences", []):
                for item in sequence.get("stopPoint", []):
                    station_id = item.get("id")
                    if station_id not in stations:
                        continue
                    hub_id = item.get("topMostParentId") or item.get("parentId") or station_id
                    hubs[station_id] = hub_id
    for station_id, hub_id in hubs.items():
        stations[station_id]["complexId"] = hub_id
    return stations, hubs


def build_normalized_source(root: Path, config: dict) -> dict:
    source = root / config["source"]["directory"]
    line_rows = load_json(source / "lines.json")
    line_modes = {row["id"]: canonical_mode(row) for row in line_rows}
    line_rows = [row for row in line_rows if line_modes[row["id"]]]
    line_ids = [row["id"] for row in line_rows]
    stations, hubs = source_station_records(source, line_ids)
    scheduled_segments, headways, pattern_headways, usable_timetable_files = scheduled_timing(
        source, line_modes, config
    )
    elizabeth_segments = elizabeth_timing(source)

    routes = {}
    for row in line_rows:
        line_id = row["id"]
        color, text_color = LINE_COLOURS[line_id]
        routes[line_id] = {
            "id": line_id,
            "label": row.get("name") or line_id,
            "name": row.get("name") or line_id,
            "mode": line_modes[line_id],
            "color": color,
            "textColor": text_color,
            "routeType": row.get("modeName"),
        }

    directions = {}
    direction_pattern_headways: dict[str, list[int]] = {}
    runtime_sources = defaultdict(int)
    skipped_by_line = config["network"].get("skippedStopsByLine", {})
    for row in line_rows:
        line_id = row["id"]
        mode = line_modes[line_id]
        seen = set()
        index = 0
        for direction_name in ("inbound", "outbound"):
            payload = load_json(source / "lines" / line_id / f"sequence-{direction_name}.json")
            for pattern in payload.get("orderedLineRoutes", []):
                station_ids = tuple(
                    station_id
                    for station_id in pattern.get("naptanIds", [])
                    if station_id not in skipped_by_line.get(line_id, [])
                )
                if len(station_ids) < 2 or station_ids in seen:
                    continue
                seen.add(station_ids)
                runtimes = []
                for left, right in zip(station_ids, station_ids[1:]):
                    if mode == "elizabeth":
                        runtime = elizabeth_segments.get((left, right))
                        source_kind = "journey-planner" if runtime else "fallback"
                    else:
                        values = scheduled_segments.get((line_id, direction_name, left, right), set())
                        source_kind = "direct-timetable"
                        if not values:
                            opposite = "outbound" if direction_name == "inbound" else "inbound"
                            values = scheduled_segments.get((line_id, opposite, right, left), set())
                            source_kind = "reverse-timetable"
                        runtime = round(median(values)) if values else None
                        if runtime is None:
                            source_kind = "fallback"
                    runtimes.append(runtime or 120)
                    runtime_sources[source_kind] += 1
                direction_id = f"{line_id}:{index}"
                terminal = clean_station_name(stations[station_ids[-1]]["name"])
                directions[direction_id] = {
                    "id": direction_id,
                    "routeId": line_id,
                    "branchId": direction_id,
                    "label": terminal,
                    "gtfsDirectionId": direction_name,
                    "tripPatternCount": 1,
                    "stations": list(station_ids),
                    "runtimes": runtimes,
                    "stopPattern": {"kind": "scheduled", "servesEveryListedStop": True},
                }
                if mode == "dlr":
                    direction_pattern_headways[direction_id] = pattern_headways.get(
                        (line_id, direction_name, station_ids), []
                    )
                index += 1

    grouped = defaultdict(list)
    for station_id, hub_id in hubs.items():
        grouped[hub_id].append(station_id)
    station_equivalents = [sorted(ids) for ids in grouped.values() if len(ids) > 1]
    # Hub members are connected by explicit timed transfers. They are not zero-cost
    # aliases: Paddington, Liverpool Street and Heathrow can require real walking.
    canonical_station_ids: dict[str, str] = {}
    transfers: dict[str, dict[str, int]] = defaultdict(dict)
    hub_transfer = config["timing"]["hubTransferSeconds"]
    for ids in station_equivalents:
        for left in ids:
            for right in ids:
                if left != right:
                    transfers[left][right] = hub_transfer

    # Preserve the established three-minute London hub default, while giving
    # DLR changes the agreed mode-pair timings. These overrides apply only to
    # station records that TfL explicitly groups into the same hub.
    station_routes: dict[str, set[str]] = defaultdict(set)
    for direction in directions.values():
        for station_id in direction["stations"]:
            station_routes[station_id].add(direction["routeId"])
    route_transfers: dict[str, dict[str, dict[str, dict[str, int]]]] = defaultdict(
        lambda: defaultdict(lambda: defaultdict(dict))
    )
    transfer_defaults = config["timing"]["transferDefaultsSeconds"]
    for ids in station_equivalents:
        for left in ids:
            for right in ids:
                if left == right:
                    continue
                for from_route in station_routes[left]:
                    for to_route in station_routes[right]:
                        from_mode = routes[from_route]["mode"]
                        to_mode = routes[to_route]["mode"]
                        if "dlr" not in {from_mode, to_mode}:
                            continue
                        pair_key = "_".join(sorted((from_mode, to_mode)))
                        seconds = transfer_defaults.get(
                            "same_mode" if from_mode == to_mode else pair_key,
                            transfer_defaults["fallback"],
                        )
                        route_transfers[left][right][from_route][to_route] = seconds

    wait_by_direction = {}
    wait_by_route = {}
    for direction_id, direction in directions.items():
        route_id = direction["routeId"]
        mode = routes[route_id]["mode"]
        wait_inputs = direction_pattern_headways.get(direction_id) or headways.get(
            (route_id, direction["gtfsDirectionId"]), []
        )
        wait = wait_from_headways(wait_inputs, mode, config)
        if wait is not None:
            wait_by_direction[direction_id] = wait
    for route_id, route in routes.items():
        values = [wait for direction_id, wait in wait_by_direction.items() if directions[direction_id]["routeId"] == route_id]
        if values:
            wait_by_route[route_id] = round(median(values))
        else:
            wait_by_route[route_id] = config["modes"][route["mode"]]["defaultWaitSeconds"]

    metadata = {
        "sourceAudit": {
            "lineCount": len(routes),
            "stationCount": len(stations),
            "patternCount": len(directions),
            "usableTimetableFiles": usable_timetable_files,
            "elizabethJourneySegments": len(elizabeth_segments),
            "runtimeSources": dict(sorted(runtime_sources.items())),
            "hubComplexCount": len(station_equivalents),
            "hubTransferSeconds": hub_transfer,
        }
    }
    return {
        "routes": routes,
        "directions": directions,
        "stations": stations,
        "transfers": {left: dict(rights) for left, rights in transfers.items()},
        "routeTransfers": {
            left: {
                right: {from_route: dict(to_routes) for from_route, to_routes in from_routes.items()}
                for right, from_routes in destinations.items()
            }
            for left, destinations in route_transfers.items()
        },
        "canonicalStationIds": canonical_station_ids,
        "stationEquivalents": station_equivalents,
        "waitSecondsByDirection": wait_by_direction,
        "waitSecondsByRoute": wait_by_route,
        "metadata": metadata,
    }
