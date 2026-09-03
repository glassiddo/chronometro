"""Paris GTFS selection and display rules.

This module contains source-feed semantics only. The normalized network,
routing, timing and puzzle generation remain in the shared builder.
"""

import re
from pathlib import Path

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


def _restore_rer_a_nation(directions: dict[str, dict], used_stations: set[str]) -> None:
    """Undo the 29 June-30 August 2026 construction skip at Nation."""
    rer_a = "15323"
    vincennes = "ITOAUTO79160"
    nation = "PARIS16509"
    gare_de_lyon = "ITOAUTO79805"
    # Exact adjacent runtimes from the one pre-closure pattern retained in the
    # source snapshot. Reverse service uses the corresponding reverse values.
    split_by_pair = {
        (vincennes, gare_de_lyon): (161, 127),
        (gare_de_lyon, vincennes): (127, 161),
    }
    for direction in directions.values():
        if direction["routeId"] != rer_a or nation in direction["stations"]:
            continue
        for index, pair in enumerate(zip(direction["stations"], direction["stations"][1:])):
            split = split_by_pair.get(pair)
            if not split:
                continue
            direction["stations"].insert(index + 1, nation)
            direction["runtimes"][index : index + 1] = list(split)
            used_stations.add(nation)
            break


def _restore_t1(directions: dict[str, dict], used_stations: set[str]) -> None:
    """Restore the normal 37-stop T1 shown on RATP's December 2023 line plan.

    The 2026 feed contains only Gare de Saint-Denis-Bobigny because of the
    damaged Ile-Saint-Denis bridge and summer works east of Bobigny. Eastern
    runtimes come from IDFM archive mdb-1026-202512090057. The unavailable
    pre-bridge western segment uses a transparent 120-second representative
    runtime, consistent with the retained T1 segment median.
    """
    t1 = "9241"
    west = [
        "ITOAUTO96071", "ITOAUTO135846", "PARIS9731", "PARIS9730",
        "ITOAUTO79402", "ITOAUTO79397", "PARIS9728", "PARIS13440",
        "PARIS9726", "ITOAUTO74716", "ITOAUTO96072", "ITOAUTO79407",
    ]
    east = [
        "PARIS206145", "PARIS9390", "PARIS9391", "PARIS11624",
        "PARIS9389", "ITOAUTO79290",
    ]
    east_runtimes = [240, 60, 180, 240, 240]
    west_runtimes = [120] * (len(west) - 1)
    for direction in directions.values():
        if direction["routeId"] != t1:
            continue
        stations = direction["stations"]
        if stations[0] == east[0] and stations[-1] == west[-1]:
            direction["stations"] = list(reversed(east[1:])) + stations + list(reversed(west[:-1]))
            direction["runtimes"] = list(reversed(east_runtimes)) + direction["runtimes"] + list(reversed(west_runtimes))
            direction["label"] = "Asnières - Quatre Routes"
        elif stations[0] == west[-1] and stations[-1] == east[0]:
            direction["stations"] = west[:-1] + stations + east[1:]
            direction["runtimes"] = west_runtimes + direction["runtimes"] + east_runtimes
            direction["label"] = "Gare de Noisy-le-Sec"
        used_stations.update(direction["stations"])


def augment_scheduled_directions(
    root: Path,
    config: dict,
    routes: dict[str, dict],
    directions: dict[str, dict],
    used_stations: set[str],
    station_meta: dict[str, dict],
) -> None:
    _restore_rer_a_nation(directions, used_stations)
    _restore_t1(directions, used_stations)
