# Chronométro

<img width="900" alt="Chronométro daily route puzzle screen" src="https://github.com/user-attachments/assets/8b186ba1-e541-4f1f-91a7-4da5296fe549">

Chronométro is a static daily route puzzle built from Paris public transport data.
It uses GTFS timetable data to model the Metro, RER A to E, and tram lines T1 to
T14 as a weighted graph, then uses Dijkstra's algorithm to find the lowest
estimated travel-time route between two stations.

Play at [chronometro.cc](https://chronometro.cc/).

Most of the work is in the data pipeline and route model:

- parsing and filtering GTFS public transport data
- representing stations, lines, transfers, and walking links as graph data
- shortest-path routing with estimated ride, wait, and transfer times
- scoring routes by comparing a player's travel time with the stored fastest route
- generating and validating static JSON puzzle data for a deployed daily site

## Technical overview

`scripts/build_data.py` reads the local GTFS export in `gouv_paris_gtfs-export/`,
keeps Metro, RER A to E, and tram services, collapses stops to stations, derives
ride times, wait estimates, transfers, and station equivalences, then writes the
network and puzzle JSON under `public/data/`.

The generated daily puzzles live in `public/data/daily/`. The static site in
`public/` loads the network and daily puzzle files in the browser. `public/app.js`
handles route building, timing, scoring, and result display. `scripts/verify_timing_model.py`
checks the generated bundle against timing and puzzle-pool constraints.

## Data

The current data comes from an ITO World modified GTFS export based on
Île-de-France Mobilités data:

- version `20260630_200738`
- valid from 27 June to 29 July 2026

Buses, ORLYVAL, CDG VAL, and non-RER rail services are excluded.

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
