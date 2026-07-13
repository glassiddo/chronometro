# Métro Express

Daily Paris route puzzle built as a static web app.

## Data source

The app uses the local `gouv_paris_gtfs-export` folder directly. This is the ITO World modified GTFS export derived from Ile-de-France Mobilites, with `feed_info.txt` reporting:

- version: `20260630_200738`
- valid from: `2026-06-27`
- valid to: `2026-07-29`

`scripts/build_data.py` inspects `routes.txt` and filters this export as follows:

- `route_type=0`: tram-like routes; keep labels beginning with `T`, exclude `ORLYVAL` and `CDG VAL`
- `route_type=1`: metro; keep all
- `route_type=2`: rail; keep RER `A`, `B`, `C`, `D`, and `E`
- `route_type=3`: bus; excluded for v1
- `route_type=6` / `7`: excluded for v1

The output schema still includes `mode` values so bus can be added later without changing the app model.

## Generated bundle

Run:

```powershell
& 'C:\Users\iddo2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' scripts\build_data.py
```

This writes `public/data/metro-express-data.json`.

The current bundle contains:

- 36 selected routes
- 114 line/direction patterns
- 762 playable stations
- 150 eligible puzzle pairs, each with one precomputed fastest route

Consecutive in-vehicle runtimes are averaged from `stop_times.txt`. Interchange times use raw child-stop `transfers.txt` route-pair minimums before station collapse, with documented mode-based fallbacks only for missing same-station transfers. `pathways.txt` is not used.

Expected waits are static and deterministic: the generator derives median scheduled headways from typical weekday 07:00-10:00 peak departures in `trips.txt` / `stop_times.txt`, then stores half-headway waits by direction and route with mode defaults as fallbacks. Routing does not use the actual current date/time, disruptions, or live data.

Each puzzle stores an `optimalRoute` object with the fastest route and `totalSec` optimal time. Scoring is based on the player's time delta against that fastest route.

Puzzle start/end stations are restricted to metro-served stations plus RER stations within central Paris bounds, while the full metro/RER/tram graph remains available for route legs. Pairs are filtered out if their fastest route has fewer than 4 transit edges or is under 1 km. RER direction labels are normalized to terminal station names, and duplicate skip-stop variants for the same RER terminal are removed in favor of the longest local-style stopping pattern. For branched metro lines, branch-specific patterns remain in the data, but the UI collapses duplicate terminal labels so players see each destination once.

## Play locally

```powershell
cd public
& 'C:\Users\iddo2\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m http.server 4173
```

Open `http://127.0.0.1:4173`.
