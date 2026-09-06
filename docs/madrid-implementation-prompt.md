# Prompt: add Madrid to Chronométro

Add Madrid as a fully working seventh city in this repository. Implement and
verify the result; do not just write a plan. Preserve existing user changes and
other cities' behavior. Do not deploy or push unless asked.

## Agreed scope and design

- Include Metro lines 1–12 and Ramal R, with their full suburban sections,
  including MetroSur and the outer sections of lines 7, 9 and 10. Exclude Metro
  Ligero, Cercanías, buses, replacement services, and unopened extensions.
- Every included Metro station may qualify as a puzzle endpoint, regardless of
  municipality. No geographic cutoff or bias against suburban endpoints.
- Model a documented normal-network snapshot, not live disruptions. Restore
  temporarily closed stations/sections only from reliable official sources;
  do not invent topology, opening dates, timings or service patterns. Flag
  unresolved long-term closures and missing evidence before deciding their treatment.
- Keep the existing UI, scoring and five-puzzle daily format. Use Spanish station
  names with accents, accent-insensitive search, official line numbers/colours,
  Europe/Madrid timezone, and the existing map style. No general redesign.
- Preserve actual required train changes within the same public line, including
  the arrangements at Tres Olivos, Estadio Metropolitano and Puerta de Arganda
  after checking official sources. Show a clear “Change trains · Line N” step
  and charge the appropriate interchange and new wait. Do not model these as
  uninterrupted rides or misclassify a legitimate same-line change as a repeated
  line detour. Keep any routing-rule exception narrowly scoped and tested.
- Support both directions around circular lines 6 and 12, including rides across
  the internal ring seam. Use understandable direction/via labels.
- Derive ride times and representative weekday 07:00–10:00 waits from official
  schedules/frequencies where possible. Start with the established three-minute
  ordinary interchange model; use documented exceptions and explicitly label
  unavoidable estimates. Do not combine frequencies unless trains can complete
  the entire chosen ride. Ignore fares and airport supplements.
- Normalize platforms through explicit parent stations or documented complexes.
  Only add documented connecting passages between distinct stations; no
  proximity-invented transfers. Keep puzzle-quality rules consistent with the
  existing game, including meaningful transfers and minimum distances.

## Implementation and verification

Inspect the current city adapters, normalized schema, generation pipeline,
frontend selectors, FAQ, Rules, About, and verification scripts before editing.
Prefer official CRTM/Metro data; check availability, completeness and reuse terms.
Record source URLs, snapshot dates, coverage, attribution, restorations and timing
assumptions. Do not silently accept account terms or send registration messages.

Implement the city config/adapter, complete normalized network, orientation-map
water features, city selection, examples and daily puzzles. Use the project's
current release convention for dates; if none is clear, generate from the
implementation date through year-end, without claiming future live accuracy.
Keep large raw feeds and all-pairs caches ignored.

Add targeted tests for complete line/station coverage, both circular directions,
mandatory same-line train changes, interchange costs, outer endpoints, absence
of excluded modes, cache eligibility, frontend/backend timing consistency, and
stored optimal routes. Revalidate puzzle rules after any endpoint-hub optimization.
Run schema/timing checks and relevant cross-city regression tests; inspect the
Madrid UI, station search, map, route choices and results in a browser. Update
README/FAQ/Rules/About, then report coverage, verification results and any genuine
remaining limitations. Make routine implementation decisions yourself; ask only
if evidence or permissions leave a materially different choice unresolved.
