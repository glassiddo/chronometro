# Orientation-map rivers

River centerlines come from OpenStreetMap contributors under the Open Database License (ODbL 1.0): https://www.openstreetmap.org/copyright. Each map displays a linked attribution notice. The derived coordinate files retain the source credit, license, snapshot timestamp, way IDs, and river names.

`python scripts/build_river_maps.py` queries named rivers in six expanded envelopes and writes `public/data/<city>/rivers.json`. Use `--save-source <file>` to retain the raw Overpass response, or `--source <file>` to rebuild from it without a download. The checked-in JSON is the browser's source; no live mapping requests are needed.

Coverage: Seine and Marne (Paris); Thames and Lea/Lee (London); Chicago River branches, Calumet River, North Shore Channel, and Chicago Sanitary and Ship Canal (Chicago); Potomac and Anacostia (Washington); Charles, Mystic, Neponset, and Chelsea Creek (Boston); Spree, Havel, and Landwehrkanal (Berlin).

The build includes named ways and linked main-stream and side-stream members of river relations, including unnamed segments. It simplifies each way with a 0.00008-degree tolerance and retains its endpoints. SVG uses straight segments between the sampled coordinates, avoiding spline overshoot. Whole ways extend beyond the map's padded geographic bounds and the viewport clips them. River mouths end at their mapped locations; no artificial lines extend across the sea. The map bounds and puzzle zoom rules are independent of the river geometry.

These are orientation cues, not riverbank polygons. Width is symbolic and constant within each city's map style. Boston's separate MassGIS shoreline remains in place. The river assets load in parallel with network data; a missing river file does not prevent playing.
