"""CRTM Madrid Metro selection and normal-network repairs."""

from __future__ import annotations

import unicodedata


ROUTES = {f"4__{line}___" for line in ["1", "2", "3", "4", "5", "6", "7", "8", "9", "10", "11", "12", "R"]}


def route_label(row):
    return (row.get("route_short_name") or "").strip()


def canonical_mode(row):
    return "metro" if row.get("route_id") in ROUTES and row.get("route_type") == "1" else None


def normalize_station_name(value):
    words = (value or "").strip().lower().split()
    return " ".join(word if word in {"de", "del", "la", "las", "los", "y"} else word.capitalize() for word in words)


def direction_display_label(mode, headsign, terminal_name):
    return normalize_station_name(terminal_name)


def route_type_mapping_metadata():
    return {"1": "Metro lines 1–12 and Ramal R only (explicit route-ID allowlist)", "other": "excluded"}


def _fold(value):
    return "".join(c for c in unicodedata.normalize("NFKD", value).casefold() if not unicodedata.combining(c)).replace("-", " ")


def augment_scheduled_directions(root, config, routes, directions, used_stations, station_meta):
    # CRTM's `par_4_*` records are platforms but omit parent_station even when
    # the corresponding explicit `est_4_*` station record exists. Collapse only
    # that documented ID pair; do not merge by proximity.
    platform_parent = {sid: f"est_4_{sid[6:]}" for sid in station_meta if sid.startswith("par_4_") and f"est_4_{sid[6:]}" in station_meta}
    for direction in directions.values():
        direction["stations"] = [platform_parent.get(sid, sid) for sid in direction["stations"]]
        direction["waitSeconds"] = 210
    used_stations.clear()
    used_stations.update(sid for direction in directions.values() for sid in direction["stations"])

    # The public 2025-05-27 snapshot contains Line 3 stations but omitted all L3
    # trips during works. Restore the documented normal line, including the now-
    # open El Casar extension. Segment times are explicitly labelled estimates.
    by_name = {_fold(meta["name"]): sid for sid, meta in station_meta.items() if not sid.startswith("par_4_")}
    names = ["El Casar", "Villaverde Alto", "San Cristobal", "Villaverde Bajo Cruce",
             "Ciudad de los Angeles", "San Fermin Orcasur", "Hospital 12 de Octubre",
             "Almendrales", "Legazpi", "Delicias", "Palos de la Frontera", "Embajadores",
             "Lavapies", "Puerta del Sol", "Callao", "Plaza de Espana", "Ventura Rodriguez",
             "Arguelles", "Moncloa"]
    ids = []
    for name in names:
        key = _fold(name)
        matches = [sid for folded, sid in by_name.items() if folded == key or key in folded or folded in key]
        if not matches:
            raise ValueError(f"Madrid Line 3 station not found: {name}")
        ids.append(matches[0])
    for reverse in range(2):
        stations = list(reversed(ids)) if reverse else ids[:]
        did = f"4__3___:normal:{reverse}"
        directions[did] = {"id": did, "routeId": "4__3___", "branchId": did,
            "label": station_meta[stations[-1]]["name"], "gtfsDirectionId": str(reverse),
            "tripPatternCount": 1, "stations": stations, "runtimes": [107] * (len(stations) - 1),
            "waitSeconds": 210, "stopPattern": {"kind": "documented-normal-restoration",
            "servesEveryListedStop": True, "topologySource": "CRTM Line 3 page and March 2026 network map",
            "runtimeSource": "estimated evenly from the published approximately 34-minute end-to-end time",
            "waitSource": "representative ordinary Metro weekday wait; estimate"}}
        used_stations.update(stations)

    # The feed serializes each ring at Laguna/Puerta del Sur. Unroll two laps so
    # either direction can cross that storage seam without a fictitious change.
    for direction in directions.values():
        if direction["routeId"] not in {"4__6___", "4__12___"}:
            continue
        ring = direction["stations"][:-1]
        runtimes = direction["runtimes"]
        direction.update(stations=ring + ring, runtimes=(runtimes * 2)[:-1],
                         circular=True, ringStationCount=len(ring))
        arrow = "↻" if direction.get("gtfsDirectionId") == "0" else "↺"
        via = "vía" + (" Moncloa" if direction["routeId"] == "4__6___" else " Leganés Central")
        direction["label"] = f"Circular {arrow} · {via}"
