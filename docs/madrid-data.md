# Madrid data snapshot

Madrid uses CRTM's official public Metro GTFS, downloaded from the agency's
ArcGIS open-data item on 6 September 2026. The file identifies itself as version
`20250527`; its calendar covers 27 May 2025 through 27 May 2026. It contains all
13 public Metro routes, station parents, platform records, geometry, stop times,
and frequency blocks. It contains no `transfers.txt` or `pathways.txt`.

## Coverage and normal-network treatment

The adapter allowlists Metro lines 1–12 and Ramal R. Metro Ligero, Cercanías,
buses, replacement services, and unopened works are excluded. Every one of the
included Metro station complexes is eligible as an endpoint, without a
municipal boundary.

The snapshot omitted Line 3 trips during works, although it retained the route
and stations. The normal line is restored from CRTM's current Line 3 listing and
March 2026 official network map, from El Casar to Moncloa. Its approximately
34-minute published end-to-end journey is distributed evenly across segments;
these 107-second segment values and the 3½-minute expected wait are explicit
estimates. Other rides come from GTFS stop times and frequency fallbacks.

Lines 7, 9 and 10 retain the separate public train patterns at Estadio
Metropolitano, Puerta de Arganda and Tres Olivos. Routing therefore charges the
ordinary three-minute interchange and a fresh wait at each mandatory same-line
change. Lines 6 and 12 are stored as two-lap rings in both directions, allowing
rides across the serialization seam without a fictitious transfer.

## Sources and licence

- CRTM Metro GTFS: <https://crtm.maps.arcgis.com/sharing/rest/content/items/5c7f2951962540d69ffe8f640d94c246/data>
- CRTM open-data licence: <https://www.crtm.es/licencia-de-uso>
- Current Line 3 listing: <https://www.crtm.es/tu-transporte-publico/metro/4__3___/>
- March 2026 official network map: <https://crtm.es/media/cdmlk0gq/serie_1a_planometro_mar2026.pdf>

Attribution: Powered by CRTM · Consorcio Regional de Transportes de Madrid.
This is a fixed normal-network game model, not live journey-planning data.
