# Chronométro

<img width="935" height="622" alt="image" src="https://github.com/user-attachments/assets/b7decbbe-b953-4313-adb7-9672a4e81325" />

Chronométro is a daily transit-route puzzle for Paris, London, Chicago, Washington, DC, and Berlin. Players build a route between two stations and score up to 100 points according to its modeled journey time relative to the fastest stored route.

Play at [chronometro.cc](https://chronometro.cc/).

The browser loads a normalized city network and five puzzles for the selected date. Journey times combine scheduled or derived ride times, expected waits, and modeled interchanges. They are not live journey-planning estimates.

## Current coverage

### Paris

- Metro, RER A–E, and tram T1–T14
- Daily puzzles from 28 July through 31 December 2026
- Excludes buses, ORLYVAL, CDG VAL, and non-RER rail

The normal 37-stop T1 is restored from RATP's official full-line plan and an archived IDFM timetable because the 2026 snapshot reflects temporary closures on both sides of the retained central section. Normal RER A service at Nation is likewise restored from the pre-closure records within the snapshot. Replacement buses are excluded.

### London

- All 11 Underground lines and the Elizabeth line
- Daily puzzles from 25 August through 31 December 2026
- Excludes London Overground, DLR, trams, buses, and National Rail

London branch paths are modeled separately. Circle and H&C frequencies are combined only when either service can complete the entire selected ride. Metropolitan fast and semi-fast service distinctions are not currently modeled.

### Chicago

- All eight CTA ‘L’ routes: Red, Blue, Brown, Green, Orange, Pink, Purple, and Yellow
- 144 playable CTA parent stations, including temporarily closed State/Lake; platform/direction stops are retained while parsing schedules and normalized through GTFS `parent_station`
- Excludes CTA buses and Metra
- Daily puzzles from 26 August through 31 December 2026

The Loop and Green branches come from complete scheduled GTFS trip patterns. State/Lake and its adjacent runtimes are restored from CTA's official 28 October 2025 GTFS archive; temporary construction reroutes remain excluded. Purple local and weekday Loop Express patterns remain distinct.

### Washington, DC

- All six Metrorail lines: Red, Blue, Orange, Silver, Yellow, and Green
- 98 playable WMATA parent stations; platform and direction records normalize only through GTFS `parent_station`
- Excludes Metrobus, DC Circulator, MARC, VRE, Amtrak, commuter buses, and other non-Metrorail service
- Daily puzzles from 29 August through 31 December 2026

Complete scheduled `stop_times.txt` patterns preserve the terminal branches, shared Blue/Orange/Silver, Blue/Yellow, and Green/Yellow infrastructure, and Silver Line Phase 2 through Dulles Airport to Ashburn. The normal FY2026 split service is retained: Silver serves both Downtown Largo and New Carrollton, while Yellow serves both Greenbelt and Mount Vernon Square. Construction-only Red Line split patterns are excluded.

### Berlin

- All nine regular U-Bahn lines: U1–U9
- 175 playable VBB parent stations in the representative full network
- Excludes temporary U12 service, S-Bahn, trams, buses, ferries, regional rail, and long-distance rail
- Daily puzzles from 5 through 30 September 2026

Complete scheduled GTFS trip patterns supply the regular U1–U9 topology. Because the current U6 is temporarily closed north of Kurt-Schumacher-Platz, its normal five-station extension to Alt-Tegel is restored from VBB's official 2021 GTFS archive. Replacement buses and temporary U12 service are excluded.

## Data sources

### Paris

Paris uses an ITO World modified GTFS export derived from Île-de-France Mobilités data:

- snapshot version `20260630_200738`
- source validity: 27 June through 29 July 2026
- weekday 07:00–10:00 departures supply expected waits where available
- RATP's December 2023 full-line plan supplies the normal T1 station order; archived IDFM snapshot `mdb-1026-202512090057` supplies the eastern extension timings
- the eleven western T1 segments missing from available post-bridge feeds use an explicit two-minute representative runtime pending a recoverable pre-May-2025 official timetable

### London

London uses a saved Transport for London Unified API snapshot:

- Underground routes, stopping patterns, departures, and cumulative timetable intervals come from TfL line and timetable endpoints
- Elizabeth line runtimes come from saved Journey Planner responses because timetable data was unavailable for that line
- expected Underground waits use half the median weekday 07:00–10:00 departure gap; Elizabeth uses a 2½-minute fallback
- ordinary same-station Underground changes use two minutes; linked records within a larger TfL hub use three minutes

### Chicago

Chicago uses the official CTA static GTFS package:

- feed: `https://www.transitchicago.com/downloads/sch_data/google_transit.zip`
- downloaded/feed version: 6 August 2026
- calendar validity represented by the package: 5 August through 31 October 2026
- weekday 07:00–10:00 departures supply expected waits
- scheduled `stop_times.txt` patterns and runtimes supply topology and ride times; no live Train Tracker data is used
- State/Lake station metadata and adjacent Loop runtimes come from official archived CTA snapshot `mdb-389-202510280038`

CTA publishes buses and the ‘L’ in one feed. The adapter requires GTFS rail type `1` and one of the eight known ‘L’ route IDs. Playable stations use explicit CTA parent stations and normal same-station changes use a three-minute model; no geographic-proximity transfers are added.

### Washington, DC

Washington uses WMATA's official rail-only static GTFS package:

- official feed: `https://api.wmata.com/gtfs/rail-gtfs-static.zip`
- snapshot downloaded 28 August 2026 (captured by the archive on 27 August as `mdb-1847-202608270118` after WMATA's public demo key reached its quota)
- `feed_info.txt` validity: 26 August through 4 September 2026; calendar records extend through 2 January 2027
- weekday 07:00–10:00 scheduled departures supply expected waits; fallbacks are four minutes by mode, capped at 15 minutes
- consecutive `stop_times.txt` values supply ride times; ordinary same-station changes use three minutes

Station IDs are WMATA parent-station IDs, so child platforms, entrances, direction records, and pathways never become playable stations or proximity-based equivalences. Metro Center, Gallery Place, L'Enfant Plaza, Fort Totten, Rosslyn, Pentagon, Stadium–Armory, East Falls Church, and King St–Old Town interchange through their shared parent station and scheduled services. Farragut North and Farragut West remain distinct stations but have WMATA's documented Farragut Crossing in both directions, modeled as a five-minute walk; no other nearby stations are joined. Later puzzles use this deterministic fixed snapshot and do not represent future service changes.

### Berlin

Berlin uses the official VBB static GTFS package:

- feed: `https://unternehmen.vbb.de/gtfs`
- primary snapshot downloaded 2 September 2026; the normally operating U6 north segment comes from VBB's official 2021 archive
- calendar validity represented by the selected records: 1 September through 12 December 2026
- weekday 07:00–10:00 departures supply expected waits
- consecutive `stop_times.txt` values supply ride times; ordinary same-station changes use three minutes

VBB publishes all Berlin and Brandenburg transport in one feed. The adapter requires BVG agency ID `796`, extended route type `400`, and one of the exact U1–U9 labels. Temporary U12 and every non-U-Bahn mode are excluded. Playable stations normalize through explicit GTFS `parent_station`; no geographic-proximity transfers are added. The resulting bundle models the normal full infrastructure rather than disruptions on one date.

No city uses live service status, disruptions, closures, fares, accessibility, crowding, or real-time departure information.

## Repository layout

- `public/` — static site, information pages, and city-scoped browser data
- `public/data/paris/` — Paris network, examples, and daily puzzles
- `public/data/london/` — London network, examples, and daily puzzles
- `public/data/chicago/` — Chicago network, examples, and daily puzzles
- `public/data/washington-dc/` — Washington network, examples, and daily puzzles
- `public/data/berlin/` — Berlin network, examples, and September daily puzzles
- `config/cities/` — city coverage, timing assumptions, output paths, and attribution
- `scripts/build_city.py` — city-neutral build entry point
- `scripts/build_data.py` — shared normalization, routing, timing, and puzzle generation
- `scripts/sources/` — Paris GTFS and London TfL source adapters
- `scripts/validate_city_schema.py` — normalized-data validation
- `scripts/verify_timing_model.py` — timing and puzzle verification
- `scripts/download_tfl_data.py` — reproducible TfL snapshot downloader

Raw source snapshots (`gouv_paris_gtfs-export/`, `gouv_london_tfl-export/`, `gouv_chicago_gtfs-export/`, `gouv_washington_dc_gtfs-export/`, and `gouv_berlin_vbb_gtfs-export/`) and generated all-pairs routing caches are intentionally ignored.

## Build and verify

Use Python 3 from the repository root.

```powershell
python scripts/build_city.py paris --mode release
python scripts/build_city.py london --mode release
python scripts/build_city.py chicago --mode release
python scripts/build_city.py washington-dc --mode release
python scripts/build_city.py berlin --mode release
```

Useful incremental build modes include `network`, `all-pairs`, `example`, and `daily-range`.

```powershell
python scripts/validate_city_schema.py paris
python scripts/validate_city_schema.py london
python scripts/validate_city_schema.py chicago
python scripts/validate_city_schema.py washington-dc
python scripts/validate_city_schema.py berlin
python scripts/verify_timing_model.py paris
python scripts/verify_timing_model.py london
python scripts/verify_timing_model.py chicago
python scripts/verify_timing_model.py washington-dc
python scripts/verify_timing_model.py berlin
python scripts/verify_london_network.py
python scripts/verify_chicago_network.py
python scripts/verify_washington_network.py
python scripts/verify_berlin_network.py
python scripts/check_auteuil_route.py
```

To refresh the ignored London source snapshot before rebuilding:

```powershell
python scripts/download_tfl_data.py --refresh
```

The downloader supports anonymous TfL access and reads `TFL_APP_KEY` from `.env.local` when configured.

To refresh Chicago, download and extract CTA's current `google_transit.zip` into the ignored `gouv_chicago_gtfs-export/` directory, then run the Chicago release command. The Chicago verification script also reads that raw snapshot to confirm parent-station normalization.

To refresh Washington, register for a WMATA developer key, download and extract the official `rail-gtfs-static.zip` into ignored `gouv_washington_dc_gtfs-export/`, and run the Washington release and verification commands.

To refresh Berlin, download and extract VBB's official GTFS package into the ignored `gouv_berlin_vbb_gtfs-export/` directory and VBB's 2021 archive into `gouv_berlin_vbb_gtfs-archive-2021/`, then run the Berlin release and verification commands. Review route labels, termini, station count, temporary services, archive compatibility, and calendar validity before accepting a refreshed bundle.

## Timing limitations

The model estimates a representative journey rather than predicting a particular departure. It does not include entering the first station or reaching the initial platform. Branch-specific wait variation, route-pair-specific interchange times, and some service-pattern differences remain simplified. Chicago does not vary by time of day, day of week, construction reroutes, or Purple Express operating hours. November and December puzzles continue to use the fixed representative snapshot even though its source calendar expires on 31 October 2026. Berlin models the normal full U-Bahn infrastructure: the closed U6 north segment uses archived scheduled runtimes, while current replacement buses and temporary U12 service are excluded.

## Attribution

Paris data: Île-de-France Mobilités and ITO World. London data: Transport for London. Chicago: Data provided by Chicago Transit Authority, subject to CTA's Developer License Agreement and trademark guidelines. Washington: Schedule data provided by WMATA, subject to the [WMATA Transit Data Terms of Use](https://developer.wmata.com/license). Berlin: Schedule data provided by Verkehrsverbund Berlin-Brandenburg (VBB) under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/).

Chronométro is independent and is not affiliated with or endorsed by RATP, Île-de-France Mobilités, Transport for London, the Chicago Transit Authority, WMATA, VBB, BVG, or the other operators and data providers represented in the game. It is neither made nor endorsed by the CTA, WMATA, VBB, or BVG. No operator logos, branding, or official maps are used; official route names and colors identify service.
