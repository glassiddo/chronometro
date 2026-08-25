# Chronométro

<img width="900" alt="Chronométro daily route puzzle screen" src="https://github.com/user-attachments/assets/8b186ba1-e541-4f1f-91a7-4da5296fe549">

Chronométro is a static, multi-city daily transit-route puzzle. Paris is the
first configured city; London and New York can be added through source adapters
that produce the same normalized browser data contract.

The Paris game uses GTFS timetable data to model the Metro, RER A to E, and tram
lines T1 to T14 as a weighted graph, then uses Dijkstra's algorithm to find the
lowest estimated travel-time route between two stations.

Play at [chronometro.cc](https://chronometro.cc/).

Most of the work is in the data pipeline and route model:

- parsing and filtering GTFS public transport data
- representing stations, lines, transfers, and walking links as graph data
- shortest-path routing with estimated ride, wait, and transfer times
- scoring routes by comparing a player's travel time with the stored fastest route
- generating and validating static JSON puzzle data for a deployed daily site

## Multi-city architecture

The architecture separates city/source semantics from shared game logic:

- `config/cities/paris.json` declares metadata, paths, modes, timing defaults,
  exceptional continuation rules, puzzle bounds, constraints, and attribution.
- `scripts/sources/paris.py` interprets Paris-specific GTFS route types, labels,
  and direction names.
- `scripts/build_city.py` is the city-neutral command-line entry point.
- `scripts/build_data.py` contains shared GTFS normalization, routing, timing,
  transfer, station-complex, and deterministic puzzle-generation logic.
- `public/data/paris/network.json`, `daily/`, and `example/` contain the normalized
  Paris browser bundle.
- `public/app.js` is the shared front end. It reads city metadata, mode labels,
  timezone, timing defaults, and attribution from the network bundle.

The normalized network includes city metadata and attribution; transport modes;
stations with coordinates and station-equivalence complexes; lines and colours;
ordered direction/branch stop patterns and runtimes; derived waits and headways;
walking, transfer, and route-pair connections; exceptional route continuations;
and puzzle-generation constraints. A source adapter may emit multiple stop
patterns for branches, short turns, express services, or skipped-stop variants.

## Building and verification

The local raw Paris export must be available at `gouv_paris_gtfs-export/`.
Build all committed Paris outputs with:

```powershell
python scripts/build_city.py paris --mode release
```

Useful incremental modes are `network`, `all-pairs`, `example`, and
`daily-range`. The ignored all-pairs cache lives below
`public/data/paris/generated/`.

Validate the normalized schema and the timing/puzzle behavior with:

```powershell
python scripts/validate_city_schema.py paris
python scripts/verify_timing_model.py paris
python scripts/check_auteuil_route.py
```

`scripts/build_data.py` remains executable as a Paris-compatible entry point,
but new automation should use `scripts/build_city.py <city>`.

The original `/data/metro-express-network.json`, `/data/daily/`, and
`/data/example/metro-express-example-data.json` files remain committed as legacy
compatibility assets. The front end now loads the city-scoped Paris paths.

## Data

The current Paris data comes from an ITO World modified GTFS export based on
Île-de-France Mobilités data:

- version `20260630_200738`
- valid from 27 June to 29 July 2026

Buses, ORLYVAL, CDG VAL, and non-RER rail services are excluded by the Paris
source adapter. Raw source exports, `.env.local`, generated all-pairs caches, and
Python bytecode are ignored and must not be committed.

## London source and timing model

The London adapter currently includes the 11 Underground lines and the Elizabeth
line. DLR, London Overground, and trams remain excluded. Refresh the ignored TfL
Unified API snapshot with:

```powershell
python scripts/download_tfl_data.py --refresh
python scripts/build_city.py london --mode network
python scripts/validate_city_schema.py london
python scripts/verify_london_network.py
```

TfL's timetable endpoint supplies Tube departures and cumulative station
intervals. The downloader follows its direction-disambiguation responses. The
Elizabeth line timetable endpoint is unavailable, so adjacent Elizabeth ride
times come from saved-snapshot Journey Planner responses for a configured
representative weekday at 08:00. Tube runtimes use the median positive observed
segment interval; repeated station records are collapsed first. Expected waits
remain half the median weekday 07:00–10:00 departure gap, with configured mode
fallbacks. When a complete ride is served by both Circle and Hammersmith & City,
their frequencies are combined to model taking the first suitable train; the
combined wait is not used beyond the shared stop sequence.

Ordinary same-station Tube changes use a 120-second estimate. Separate records
sharing a TfL hub are joined by an explicit 180-second connection; optional
street walking links are not currently added. These are fixed modelling choices,
not live estimates. Colours use TfL's published digital RGB colour standard.

## Limitations

Travel times are approximate. Ride times, waits, and transfers depend on the GTFS
snapshot and the assumptions in the timing model, including half the median
scheduled gap between departures from 7:00 to 10:00 AM.

The site does not use live service data, disruptions, closures, fares,
accessibility constraints, or later network changes. It also does not include
time to enter the first station or reach the initial platform.

## Credits

Route data: Île-de-France Mobilités and ITO World.

Chronométro is not affiliated with or endorsed by RATP or Île-de-France Mobilités.
