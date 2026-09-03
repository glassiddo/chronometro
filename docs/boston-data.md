# Boston data snapshot

The orientation map uses the MassGIS generalized municipal coastline, simplified to 0.25 SVG pixels. Source: [MassGIS municipal boundaries](https://services1.arcgis.com/hGdibHYSPO59RG1h/ArcGIS/rest/services/Massachusetts_Municipalities_Hosted/FeatureServer/0). Credit: MassGIS (Bureau of Geographic Information), Commonwealth of Massachusetts EOTSS. `scripts/build_boston_basemap.py` generates the static SVG from a GeoJSON export. River paths come from OpenStreetMap; see [river-maps.md](river-maps.md). Map bounds preserve approximately equal geographic scale in both directions.

Chronométro uses the MBTA scheduled static GTFS at `https://cdn.mbta.com/MBTA_GTFS.zip`, confirmed by MBTA's current GTFS reference. Downloaded 2026-08-31, `feed_info.txt` identifies feed `mbta-ma-us`, publisher MBTA, version `Fall 2026, 2026-08-28T13:45:01+00:00, version D`, valid 2026-08-21–2026-12-12. Agency `1` is MBTA; agency `3` is Cape Cod RTA and is excluded.

The build uses services active Wednesday 2026-09-02, 07:00–10:00, and only patterns MBTA marks `route_pattern_typicality=1`. It explicitly allows Red, Orange, Blue, Green B/C/D/E, and Mattapan. Silver Line and all other buses, shuttles, Commuter Rail, ferries, CapeFLYER, Amtrak, and non-MBTA operators are excluded. Red's Ashmont and Braintree patterns remain one route. Typical Green allocations are B/C–Government Center, D–Union Square, and E–Medford/Tufts; non-typical extension and short-turn patterns do not become topology.

Platforms collapse only through explicit `parent_station`; stable `place-*` IDs are retained. Longwood/Longwood Medical Area, Chestnut Hill/Chestnut Hill Avenue, and distinct surface stops remain separate. No proximity equivalences are enabled.

The feed records Park Street–Downtown Crossing platform transfers through the Winter Street Concourse (180–222 seconds walking plus 105 seconds buffer). The game uses a conservative five-minute walk each way. All other inter-station walks are excluded.

The daily puzzle calendar runs from 2026-08-30 through 2026-10-31 (63 days). Expected waits are half the median scheduled pattern gap, with direction, route, then mode fallback (four minutes rapid transit; five minutes light rail). A Green branch uses its own departures, not combined trunk frequency. Puzzles after feed expiry remain a deterministic snapshot and do not claim future service changes.

The MassDOT Developers License Agreement permits derived/commercial products but requires clear MassDOT acknowledgement and its warranty/liability disclaimer; it does not grant endorsement or general mark use. Chronométro credits MassDOT/MBTA, disclaims affiliation/endorsement, and uses no MBTA logo or official map.

Rebuild: `python scripts/build_city.py boston --mode release`. Validate with `validate_city_schema.py boston`, `verify_timing_model.py boston`, and `verify_boston_network.py`.
