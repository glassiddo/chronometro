# Berlin normal U-Bahn and S-Bahn network

The active release contains U1–U9 and S1, S15, S2, S25, S26, S3, S41, S42, S46, S47, S5, S7, S75, S8, S85, and S9. It has 316 distinct VBB parent stations: 175 with U-Bahn, 168 with S-Bahn, and 27 shared parents. There are 72 service/direction patterns and 280 eligible puzzle endpoints. All 36 stations outside Berlin remain routable.

## Sources and reproducibility

- [VBB official static data and archives](https://unternehmen.vbb.de/digitale-services/datensaetze/): September 2, 2026 snapshot in `gouv_berlin_vbb_gtfs-export/`; [2021 archive](https://unternehmen.vbb.de/fileadmin/user_upload/VBB/Dokumente/API-Datensaetze/gtfs-2021.zip) in `gouv_berlin_vbb_gtfs-archive-2021/`. Raw packages are ignored. VBB data is CC BY 4.0.
- [S-Bahn Berlin regular timetables](https://sbahn.berlin/fahren/fahrplanauskunft/linienfahrplaene/) and [official S+U map](https://sbahn.berlin/fileadmin/user_upload/Liniennetz/S_U-Bahn-Liniennetz.pdf), reviewed September 3, 2026. `config/berlin-sbahn-patterns.json` preserves the reviewed station sequences, independent service groups, regular wait assumptions, and source URLs. These are normal services, not every trip variant in the disruption-affected GTFS.
- [Geoportal Berlin ALKIS Landesgrenze](https://daten.berlin.de/datensaetze/alkis-berlin-landesgrenze-wfs-07b1347b), retrieved September 3, 2026, dl-de-zero-2.0. `config/berlin-state-boundary.geojson` preserves the full multipart polygon and holes in longitude/latitude EPSG:4326. Download query: `https://gdi.berlin.de/services/wfs/alkis_land?service=WFS&version=2.0.0&request=GetFeature&typeNames=alkis_land:landesgrenze&srsName=EPSG:4326&outputFormat=application/json`.

Run from the repository root:

```powershell
py -3 scripts/build_city.py berlin --mode release
py -3 scripts/validate_city_schema.py berlin
py -3 scripts/verify_berlin_network.py
py -3 scripts/verify_timing_model.py berlin
node scripts/verify_berlin_frontend.js
py -3 -m http.server 8765 --bind 127.0.0.1 --directory public
```

Open `http://127.0.0.1:8765/?city=berlin&date=2026-10-05` for the first regenerated day. Review the manifest against the operator's regular timetable whenever refreshing the source. A missing official segment runtime fails the build instead of silently inventing a duration.

## Selection, normalization, and repairs

The unit is a public line, a regular ordered service pattern, and an explicit GTFS parent station. S-Bahn requires agency `1`, route type `109`, and a regular-line allow-list; U-Bahn requires agency `796`, type `400`, and U1–U9. The current feed's 43 S-Bahn route IDs collapse to 16 public lines before segment aggregation. Temporary U12, withdrawn S45, replacement buses with S-Bahn labels, regional rail, diversions, and unlisted short turns cannot enter the manifest.

Current full scheduled patterns provide the network. The 2021 archive restores the 29-stop U6 through Alt-Tegel and the northbound Bornholmer Straße–Wollankstraße–Schönholz sequence and timings used by S1, S25, and S85. The old S85 route is not reinstated: its current airport and northern branches remain. `normalNetworkRepairs` and each pattern's `runtimeSources` record the S-Bahn repairs. Current parent IDs, station names, and coordinates are retained.

S15 serves Hauptbahnhof–Wedding–Gesundbrunnen. S26 reaches Blankenburg, S47 reaches Südkreuz, S8 includes Wildau and Grünau service, and S85 retains the Frohnau, Waidmannslust, and Pankow alternatives. The manifest also retains regular peak overlays on S1, S2, S3, S5, S46, and S75. S75's Ostbahnhof extension and Warschauer Straße trains are independent services. Alternative S8/S85 termini share their base frequency group and must not be counted as simultaneous extra trains on their common section.

S41 is clockwise and S42 counterclockwise. Each is stored as two copies of the 27-station ring, allowing every ride shorter than one lap to cross the serialization seam. This is one service per direction, not two trains or a reverse service. The UI offers each of the other 26 stations once. Geographic signed-area tests independently verify the direction.

## Geography and interchanges

The endpoint test uses the official polygon and the normalized station coordinate. The restriction applies to S-Bahn endpoints, not routing; existing U-Bahn endpoint eligibility is preserved. The 36 outside stations include BER, Potsdam, Hennigsdorf, Oranienburg, Teltow Stadt, Bernau, Erkner, and Brandenburg branch stops. Border stations such as Ahrensfelde, Heiligensee, Rahnsdorf, and Grünbergallee remain eligible. The source boundary is stored locally so refreshes cannot silently change the puzzle sample.

Shared VBB parents provide the ordinary U/S interchanges, including Alexanderplatz, Friedrichstraße, Gesundbrunnen, Hauptbahnhof, Wuhletal, and Warschauer Straße. Four interchange links shown on the official map join separate parents in both directions: Spandau–Rathaus Spandau, Charlottenburg–Wilmersdorfer Straße, Messe Nord/ZOB–Kaiserdamm, and Yorckstraße (Großgörschenstraße)–Yorckstraße. These are explicit five-minute modeled walks. They are not measured accessibility or platform walking times. Other same-parent changes use three minutes. No proximity-based mergers or free interchanges are introduced.

## Timing and route search

S-Bahn segment times average scheduled morning (07:00–10:00) departure-to-departure intervals, including dwell. This convention includes dwell at the alighting stop; it is a representative puzzle duration, not an exact arrival prediction. U-Bahn preserves the existing arrival-minus-departure convention. Ring laps model approximately 61 minutes, close to the operator's regular 59-minute circuit; averaging the snapshot across service variants accounts for the difference.

S-Bahn waits are half the published regular headway, with independent peak overlays represented separately. On any selected ride, frequencies combine only when the entire ordered station sequence matches. One frequency group counts once even if multiple alternative patterns match. The reciprocal-frequency model simplifies uneven gaps such as S46's 5/15-minute service and does not predict a departure. Alternative time-of-day services remain available at their regular frequency; the game is deliberately not a time-dependent journey planner.

Berlin's shortest-path search uses complete rides with shared waits and interchange costs included before choosing the route. This avoids choosing a slower route and only discounting its wait afterward. A journey can finish with a documented interchange walk without paying for another train. Origin trees are reused during all-pairs construction. Python uses the same positive half-up rounding as JavaScript, and the frontend test executes the actual game helpers against every generated ride and both ring seams.

## Puzzles and verification

The active index covers October 5–31, 2026: five puzzles per day, 135 total. Each day includes at least one U-Bahn-only, one mixed, and one S-Bahn-only fastest solution; remaining puzzles are seeded varied selections. Their order is shuffled so the puzzle number does not identify its solution type. Every puzzle retains the existing transfer, endpoint separation, route-distance, no shared endpoint line, and no repeated public line rules. September 5–October 4 files remain unchanged as historical artifacts outside this release's active index.

The release evaluates 78,120 ordered endpoint pairs. Tests verify unique public lines, raw parent-station identity, counts, normal termini, branches, archive repairs, ring orientation and seam runtimes, boundary edge cases, explicit walks, all 135 search/display/stored timing totals, and daily solution variety. The shared schema and timing checks also run against the regenerated bundle. A Berlin-specific data revision refreshes cached network and puzzle downloads for this release.
