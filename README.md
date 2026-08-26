# Chronométro

Chronométro is a daily transit-route puzzle for Paris, London, and Chicago. Players build a route between two stations and score up to 100 points according to its modeled journey time relative to the fastest stored route.

Play at [chronometro.cc](https://chronometro.cc/).

The site is static: the browser loads a normalized city network and five pre-generated puzzles for the selected date. Journey times combine scheduled or derived ride times, expected waits, and modeled interchanges. They are not live journey-planning estimates.

## Current coverage

### Paris

- Metro, RER A–E, and tram T1–T14
- Daily puzzles from 28 July 2026 through 27 July 2027
- Excludes buses, ORLYVAL, CDG VAL, and non-RER rail

### London

- All 11 Underground lines and the Elizabeth line
- Preliminary daily puzzles from 25 August through 15 September 2026
- Excludes London Overground, DLR, trams, buses, and National Rail

London branch paths are modeled separately. Circle and H&C frequencies are combined only when either service can complete the entire selected ride. Metropolitan fast and semi-fast service distinctions are not currently modeled.

### Chicago

- All eight CTA ‘L’ routes: Red, Blue, Brown, Green, Orange, Pink, Purple, and Yellow
- 143 playable CTA parent stations; platform/direction stops are retained while parsing schedules and normalized through GTFS `parent_station`
- Excludes CTA buses and Metra
- Daily puzzles from 26 August 2026 through 25 August 2027

The Loop and Green branches come from complete scheduled GTFS trip patterns. Purple local and weekday Loop Express patterns remain distinct.

## Data sources

### Paris

Paris uses an ITO World modified GTFS export derived from Île-de-France Mobilités data:

- snapshot version `20260630_200738`
- source validity: 27 June through 29 July 2026
- weekday 07:00–10:00 departures supply expected waits where available

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

CTA publishes buses and the ‘L’ in one feed. The adapter requires GTFS rail type `1` and one of the eight known ‘L’ route IDs. Playable stations use explicit CTA parent stations and normal same-station changes use a three-minute model; no geographic-proximity transfers are added.

No city uses live service status, disruptions, closures, fares, accessibility, crowding, or real-time departure information.

## Repository layout

- `public/` — static site, information pages, and city-scoped browser data
- `public/data/paris/` — Paris network, examples, and daily puzzles
- `public/data/london/` — London network, examples, and daily puzzles
- `public/data/chicago/` — Chicago network, examples, and daily puzzles
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
```

Useful incremental build modes include `network`, `all-pairs`, `example`, and `daily-range`.

```powershell
python scripts/validate_city_schema.py paris
python scripts/validate_city_schema.py london
python scripts/validate_city_schema.py chicago
python scripts/verify_timing_model.py paris
python scripts/verify_timing_model.py london
python scripts/verify_timing_model.py chicago
python scripts/verify_london_network.py
python scripts/verify_chicago_network.py
python scripts/check_auteuil_route.py
```

To refresh the ignored London source snapshot before rebuilding:

```powershell
python scripts/download_tfl_data.py --refresh
```

The downloader supports anonymous TfL access and reads `TFL_APP_KEY` from `.env.local` when configured.

To refresh Chicago, download and extract CTA's current `google_transit.zip` into the ignored `gouv_chicago_gtfs-export/` directory, then run the Chicago release command. The Chicago verification script also reads that raw snapshot to confirm parent-station normalization.

## Timing limitations

The model estimates a representative journey rather than predicting a particular departure. It does not include entering the first station or reaching the initial platform. Branch-specific wait variation, route-pair-specific interchange times, and some service-pattern differences remain simplified. Chicago does not vary by time of day, day of week, construction reroutes, or Purple Express operating hours. Puzzles after 31 October 2026 continue to use the fixed representative snapshot even though its source calendar has expired.

## Attribution

Paris data: Île-de-France Mobilités and ITO World. London data: Transport for London. Chicago: Data provided by Chicago Transit Authority, subject to CTA's Developer License Agreement and trademark guidelines.

Chronométro is independent and is not affiliated with or endorsed by RATP, Île-de-France Mobilités, Transport for London, the Chicago Transit Authority, or the other operators and data providers represented in the game. It is neither made nor endorsed by the CTA. No CTA logos or official maps are used; official route names and colors identify service.
