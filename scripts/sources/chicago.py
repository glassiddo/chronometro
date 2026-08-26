"""Chicago CTA static-GTFS selection and display rules."""

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
