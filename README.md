# Chronométro

<img width="935" height="622" alt="image" src="https://github.com/user-attachments/assets/b7decbbe-b953-4313-adb7-9672a4e81325" />

Chronométro is a daily transit-route puzzle for Paris, London, Chicago, and Washington, DC. Players build a route between two stations and score up to 100 points according to its modeled journey time relative to the fastest stored route.

Play at [chronometro.cc](https://chronometro.cc/).

The browser loads a normalized city network and five puzzles for the selected date. Journey times combine scheduled or derived ride times, expected waits, and modeled interchanges. They are not live journey-planning estimates.

## Current coverage

### Paris

- Metro, RER A–E, and tram T1–T14
- Daily puzzles from 28 July through 31 December 2026
- Excludes buses, ORLYVAL, CDG VAL, and non-RER rail

### London

- All 11 Underground lines, the Elizabeth line, and the complete DLR network
- Daily puzzles from 25 August through 31 December 2026
- Excludes London Overground, trams, buses, and National Rail

London branch paths are modeled separately. Circle and H&C frequencies are combined only when either service can complete the entire selected ride. DLR's five regular terminal-to-terminal service patterns remain distinct, with timetable-derived runtimes and expected waits. Metropolitan fast and semi-fast service distinctions are not currently modeled.

### Chicago

- All eight CTA ‘L’ routes: Red, Blue, Brown, Green, Orange, Pink, Purple, and Yellow
- 143 playable CTA parent stations; platform/direction stops are retained while parsing schedules and normalized through GTFS `parent_station`
- Excludes CTA buses and Metra
- Daily puzzles from 26 August through 31 December 2026

The Loop and Green branches come from complete scheduled GTFS trip patterns. Purple local and weekday Loop Express patterns remain distinct.

### Washington, DC

- All six Metrorail lines: Red, Blue, Orange, Silver, Yellow, and Green
- 98 playable WMATA parent stations; platform and direction records normalize only through GTFS `parent_station`
- Excludes Metrobus, DC Circulator, MARC, VRE, Amtrak, commuter buses, and other non-Metrorail service
- Daily puzzles from 29 August through 31 December 2026

Complete scheduled `stop_times.txt` patterns preserve the terminal branches, shared Blue/Orange/Silver, Blue/Yellow, and Green/Yellow infrastructure, and Silver Line Phase 2 through Dulles Airport to Ashburn. A temporary Silver-to-New-Carrollton pattern in this snapshot is excluded from playable topology.

## Data sources

### Paris

Paris uses an ITO World modified GTFS export derived from Île-de-France Mobilités data:

- snapshot version `20260630_200738`
- source validity: 27 June through 29 July 2026
- weekday 07:00–10:00 departures supply expected waits where available

### London

London uses a saved Transport for London Unified API snapshot:

- Underground and DLR routes, stopping patterns, departures, and cumulative timetable intervals come from TfL line and timetable endpoints
- Elizabeth line runtimes come from saved Journey Planner responses because timetable data was unavailable for that line
- expected Underground and DLR waits use half the median weekday 07:00–10:00 departure gap where the timetable payload supports it; Elizabeth uses a 2½-minute fallback
- ordinary same-mode changes use two minutes; DLR–Underground hub changes use three minutes and DLR–Elizabeth hub changes use four minutes

### Chicago

Chicago uses the official CTA static GTFS package:

- feed: `https://www.transitchicago.com/downloads/sch_data/google_transit.zip`
- downloaded/feed version: 6 August 2026
- calendar validity represented by the package: 5 August through 31 October 2026
- weekday 07:00–10:00 departures supply expected waits
- scheduled `stop_times.txt` patterns and runtimes supply topology and ride times; no live Train Tracker data is used

CTA publishes buses and the ‘L’ in one feed. The adapter requires GTFS rail type `1` and one of the eight known ‘L’ route IDs. Playable stations use explicit CTA parent stations and normal same-station changes use a three-minute model; no geographic-proximity transfers are added.

### Washington, DC

Washington uses WMATA's official rail-only static GTFS package:

- official feed: `https://api.wmata.com/gtfs/rail-gtfs-static.zip`
- snapshot downloaded 28 August 2026 (captured by the archive on 27 August as `mdb-1847-202608270118` after WMATA's public demo key reached its quota)
- `feed_info.txt` validity: 26 August through 4 September 2026; calendar records extend through 2 January 2027
- weekday 07:00–10:00 scheduled departures supply expected waits; fallbacks are four minutes by mode, capped at 15 minutes
- consecutive `stop_times.txt` values supply ride times; ordinary same-station changes use three minutes

Station IDs are WMATA parent-station IDs, so child platforms, entrances, direction records, and pathways never become playable stations or proximity-based equivalences. Metro Center, Gallery Place, L'Enfant Plaza, Fort Totten, Rosslyn, Pentagon, Stadium–Armory, East Falls Church, and King St–Old Town interchange through their shared parent station and scheduled services. Farragut North and Farragut West remain distinct stations but have WMATA's documented Farragut Crossing in both directions, modeled as a five-minute walk; no other nearby stations are joined. Later puzzles use this deterministic fixed snapshot and do not represent future service changes.

No city uses live service status, disruptions, closures, fares, accessibility, crowding, or real-time departure information.

## Repository layout

- `public/` — static site, information pages, and city-scoped browser data
- `public/data/paris/` — Paris network, examples, and daily puzzles
- `public/data/london/` — London network, examples, and daily puzzles
- `public/data/chicago/` — Chicago network, examples, and daily puzzles
- `public/data/washington-dc/` — Washington network, examples, and daily puzzles
- `config/cities/` — city coverage, timing assumptions, output paths, and attribution
- `scripts/build_city.py` — city-neutral build entry point
- `scripts/build_data.py` — shared normalization, routing, timing, and puzzle generation
- `scripts/sources/` — Paris GTFS and London TfL source adapters
- `scripts/validate_city_schema.py` — normalized-data validation
- `scripts/verify_timing_model.py` — timing and puzzle verification
- `scripts/download_tfl_data.py` — reproducible TfL snapshot downloader

Raw source snapshots (`gouv_paris_gtfs-export/`, `gouv_london_tfl-export/`, and `gouv_chicago_gtfs-export/`) and generated all-pairs routing caches are intentionally ignored.

## Build and verify

Use Python 3 from the repository root.

```powershell
python scripts/build_city.py paris --mode release
python scripts/build_city.py london --mode release
python scripts/build_city.py chicago --mode release
python scripts/build_city.py washington-dc --mode release
```

Useful incremental build modes include `network`, `all-pairs`, `example`, and `daily-range`.

```powershell
python scripts/validate_city_schema.py paris
python scripts/validate_city_schema.py london
python scripts/validate_city_schema.py chicago
python scripts/validate_city_schema.py washington-dc
python scripts/verify_timing_model.py paris
python scripts/verify_timing_model.py london
python scripts/verify_timing_model.py chicago
python scripts/verify_timing_model.py washington-dc
python scripts/verify_london_network.py
python scripts/verify_chicago_network.py
python scripts/verify_washington_network.py
python scripts/check_auteuil_route.py
```

To refresh the ignored London source snapshot before rebuilding:

```powershell
python scripts/download_tfl_data.py --refresh
```

The downloader supports anonymous TfL access and reads `TFL_APP_KEY` from `.env.local` when configured.

To refresh Chicago, download and extract CTA's current `google_transit.zip` into the ignored `gouv_chicago_gtfs-export/` directory, then run the Chicago release command. The Chicago verification script also reads that raw snapshot to confirm parent-station normalization.

To refresh Washington, register for a WMATA developer key, download and extract the official `rail-gtfs-static.zip` into ignored `gouv_washington_dc_gtfs-export/`, and run the Washington release and verification commands.

## Timing limitations

The model estimates a representative journey rather than predicting a particular departure. It does not include entering the first station or reaching the initial platform. Some branch-specific wait variation, route-pair-specific interchange times, and service-pattern differences remain simplified. Chicago does not vary by time of day, day of week, construction reroutes, or Purple Express operating hours. November and December puzzles continue to use the fixed representative snapshot even though its source calendar expires on 31 October 2026.

## Attribution

Paris data: Île-de-France Mobilités and ITO World. London data: Transport for London. Chicago: Data provided by Chicago Transit Authority, subject to CTA's Developer License Agreement and trademark guidelines. Washington: Schedule data provided by WMATA, subject to the [WMATA Transit Data Terms of Use](https://developer.wmata.com/license).

Chronométro is independent and is not affiliated with or endorsed by RATP, Île-de-France Mobilités, Transport for London, the Chicago Transit Authority, WMATA, or the other operators and data providers represented in the game. It is neither made nor endorsed by the CTA or WMATA. No CTA or WMATA logos, branding, or official maps are used; official route names and colors identify service.
