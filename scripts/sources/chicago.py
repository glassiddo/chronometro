"""Chicago CTA static-GTFS selection and display rules."""

from pathlib import Path

L_ROUTE_IDS = {"Red", "Blue", "Brn", "G", "Org", "Pink", "P", "Y"}


def route_label(row: dict[str, str]) -> str:
    name = (row.get("route_long_name") or row.get("route_short_name") or "").strip()
    return name.removesuffix(" Line")


def canonical_mode(row: dict[str, str]) -> str | None:
    # CTA publishes buses and the ‘L’ together. The route ID allow-list is an
    # intentional second guard beyond route_type so this adapter cannot absorb
    # another rail operator or future non-‘L’ rail product accidentally.
    if row.get("route_type") == "1" and row.get("route_id") in L_ROUTE_IDS:
        return "l"
    return None


def direction_display_label(mode: str, headsign: str, terminal_name: str) -> str:
    return (headsign or terminal_name).strip()


def route_type_mapping_metadata() -> dict[str, str]:
    return {
        "1": "CTA rail; only Red, Blue, Brown, Green, Orange, Pink, Purple, and Yellow route IDs included",
        "3": "CTA bus; excluded",
        "other": "excluded (including any non-CTA/Metra service)",
    }


def augment_scheduled_directions(
    root: Path,
    config: dict,
    routes: dict[str, dict],
    directions: dict[str, dict],
    used_stations: set[str],
    station_meta: dict[str, dict],
) -> None:
    """Restore State/Lake from CTA's official 28 October 2025 GTFS archive.

    The current feed omits the station during its 2026-2029 reconstruction.
    Historical adjacent runtimes are route- and direction-specific means from
    mdb-389-202510280038, the final archived feed before the closure.
    """
    state_lake = "40260"
    clark_lake = "40380"
    washington_wabash = "41700"
    station_meta[state_lake] = {
        "id": state_lake,
        "name": "State/Lake",
        "lat": 41.88574,
        "lon": -87.627835,
    }
    used_stations.add(state_lake)
    historical_runtimes = {
        ("Brn", washington_wabash, clark_lake): (96, 57),
        ("G", clark_lake, washington_wabash): (60, 90),
        ("G", washington_wabash, clark_lake): (120, 36),
        ("Org", clark_lake, washington_wabash): (60, 90),
        ("P", clark_lake, washington_wabash): (61, 96),
        ("Pink", clark_lake, washington_wabash): (60, 90),
    }
    for direction in directions.values():
        stations = direction["stations"]
        runtimes = direction["runtimes"]
        for index, (left, right) in enumerate(zip(stations, stations[1:])):
            split = historical_runtimes.get((direction["routeId"], left, right))
            if not split:
                continue
            stations.insert(index + 1, state_lake)
            runtimes[index : index + 1] = list(split)
            break
