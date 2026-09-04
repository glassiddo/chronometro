# Puzzle endpoint boundaries

Updated 4 September 2026. This is an endpoint-selection rule, not a network clip.
The unit is the normalized station record keyed by its existing station ID.
Stations served by an unrestricted endpoint mode remain eligible independently
of geography: Métro in Paris, Underground/DLR in London, and U-Bahn in Berlin.
Paris trams do not qualify as endpoints on their own.

## Sources and geometry

- Paris: `config/paris-city-boundary.geojson`, unmodified response from
  <https://geo.api.gouv.fr/communes/75056?fields=nom,code,contour&format=geojson&geometry=contour>,
  retrieved 4 September 2026. Commune 75056, including the municipal woods;
  longitude/latitude WGS84. The response does not state a boundary vintage or
  generalization tolerance, so retrieval date is not claimed as a survey date.
  The API's [Contours administratifs dataset](https://www.data.gouv.fr/datasets/contours-administratifs)
  identifies IGN Admin Express among its sources and lists ODbL licensing.
  This saved source is distributed separately and unchanged under that license.
  SHA256: `3a2c58cf3c54104a6356dffae3ea5186ad6b3dde7fdb7ba53ef5b7906abc7860`.
- London: `config/london-city-boundary.geojson`, converted from the GLA's
  [Greater London boundary archive](https://data.london.gov.uk/download/20od9/114d1137-e339-4b50-b409-124c17f4b59a/gla.zip),
  retrieved 4 September 2026. The source feature's legacy name is “London Euro Region”;
  the publisher identifies the download as the Greater London boundary, not City of London.
  The [catalogue](https://data.london.gov.uk/dataset/statistical-gis-boundary-files-for-london-20od9)
  describes the statistical collection as including 2011 boundaries; no separate
  survey date is supplied for this individual polygon. Archive metadata lists a
  March 2025 upload, which is not a boundary vintage.
  `scripts/convert_london_boundary.py` converts EPSG:27700 to EPSG:4326, retaining all
  vertices and multipart geometry without further simplification. Normal builds
  do not require GIS packages. Licence: Open Government Licence v2.
  Contains National Statistics data © Crown copyright and database right 2015.
  Contains Ordnance Survey data © Crown copyright and database right 2015.
  SHA256: `bbf7f7b4ab5337458aeb30d62b1d4a6c04ff9d7a4a283dea2de8dabd32f15d40`.
- Berlin: unchanged ALKIS state polygon and source-adapter test; see `berlin-data.md`.

Paris/London checks use saved station coordinates, include polygon edges, retain
holes and islands, and reject missing/non-finite coordinates. No station-name
crosswalk, buffer, proximity matching, or station merging is introduced. The
source accuracy limits still apply to stations very close to a border.

## Audit and reproducibility

The custom point test matched Shapely `covers` for every one of the 775 Paris and
360 London station records; both saved geometries were valid. Coordinates were
present for every station. No station records, routes, connections or timing
values are removed or changed.

| City | Eligible station records before | After | Removed endpoint records |
|---|---:|---:|---|
| Paris | 344 | 340 | Gentilly, Issy, Issy Val de Seine, Pantin |
| London | 351 | 350 | Iver |

No endpoints were added. Of the regional-rail records specifically, 30 Paris RER
records and 33 London Elizabeth records fall inside their respective polygons.
The cached pool is filtered on load: Paris retains 115,256 of 117,988 pairs;
London retains 122,094 of 122,794. A cache missing newly eligible endpoints is
rejected so it can be rebuilt. Caches are not treated as an authority on eligibility.

Run `py scripts/refresh_puzzle_boundaries.py paris` and the same command for
`london` to update only network constraint metadata, examples, and the configured
daily ranges. Stored journeys remain based on the existing source snapshots.
London hub optimization now rechecks puzzle rules and replaces candidates that
become unplayable after choosing the best starting/finishing platform.

Verification: `py scripts/verify_puzzle_boundaries.py` checks synthetic geometry
edge/hole/island cases, missing coordinates, regression stations, cache handling,
endpoint eligibility for all saved daily/example files, counts and within-bundle
ID uniqueness. Also run schema and timing checks for both cities.
