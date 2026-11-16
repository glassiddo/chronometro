const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'public/app.js'), 'utf8');
const failures = [];
for (const file of fs.readdirSync(path.join(root, 'config/cities'))) {
  const city = file.replace('.json', '');
  const data = JSON.parse(fs.readFileSync(path.join(root, `public/data/${city}/network.json`)));
  const context = vm.createContext({ URLSearchParams, console, data,
    window: { location: { search: `?city=${city}` } },
    document: { querySelector: () => ({ addEventListener() {}, append() {} }), querySelectorAll: () => [] },
  });
  vm.runInContext(source.slice(0, source.lastIndexOf('init().catch(')), context);
  vm.runInContext('state.data = data; configureCityMap(); boardShell = html => { rendered = html; };', context);
  if (!vm.runInContext('CITY_MAP.parks.length > 0', context)) failures.push(`${city}: missing park orientation landmarks`);
  let missing = 0;
  for (const dir of Object.values(data.directions)) {
    if (dir.stations.length < 2) continue;
    context.dir = dir;
    const markup = vm.runInContext(`
      state.daily = [{ start: dir.stations[0], end: dir.stations.at(-1) }];
      state.currentStation = dir.stations[0];
      state.selected = { routeId: dir.routeId, directionId: dir.id, boardStation: dir.stations[0], boardIndex: 0 };
      state.selected.directionCandidates = [{ routeId: dir.routeId, dirId: dir.id, boardStation: dir.stations[0], boardIndex: 0, walkSec: 0 }];
      state.mode = 'easy'; renderAlightStep(); rendered;
    `, context);
    for (const match of markup.matchAll(/<button[^>]*data-alight="([^"]+)"[\s\S]*?<\/button>/g)) {
      context.stopId = match[1];
      const expected = vm.runInContext(`stationLineIds(stopId).filter(id =>
        routeDisplayName(route(id)) !== routeDisplayName(route(dir.routeId))).map(lineBadge)`, context);
      if (expected.some(badge => !match[0].includes(badge))) missing++;
    }
  }
  console.log(`${city}: ${missing} stop rows missing connecting lines`);
  if (missing) failures.push(`${city}: missing connections`);
  try {
    vm.runInContext('fitCityMapToPuzzle()', context);
    const ratio = vm.runInContext(`(() => {
      const b = CITY_MAP.viewBounds, lat = (b.minLat + b.maxLat) / 2, lon = (b.minLon + b.maxLon) / 2;
      const p = mapPoint({lat, lon}, false);
      const east = mapPoint({lat, lon: lon + .001 / Math.cos(lat * Math.PI / 180)}, false);
      const north = mapPoint({lat: lat + .001, lon}, false);
      return (east.x - p.x) / (p.y - north.y);
    })()`, context);
    assert.ok(Math.abs(ratio - 1) < .001, `${city}: map stretches geography (${ratio.toFixed(2)})`);
    assert.match(vm.runInContext('networkContextMapMarkup()', context), /<path class="map-network-context [^"]+" d="M /,
      `${city}: network must use the shared projected paths, including river crossings`);
    if (city === 'new-york' || city === 'boston') {
      const alignmentError = vm.runInContext(`(() => {
        const image = basemapMarkup();
        const attr = name => Number(image.match(new RegExp(' ' + name + '="([^"]+)"'))[1]);
        const b = CITY_MAP.bounds;
        const point = {lon: b.minLon + .37 * (b.maxLon - b.minLon), lat: b.maxLat - .61 * (b.maxLat - b.minLat)};
        const projected = mapPoint(point, false);
        const x = attr('x') + (12 + .37 * 296) / 320 * attr('width');
        const y = attr('y') + (12 + .61 * 196) / 220 * attr('height');
        if (!image.includes('preserveAspectRatio="none"')) return Infinity;
        return Math.hypot(x - projected.x, y - projected.y);
      })()`, context);
      assert.ok(alignmentError < 1e-8, `${city}: coastline and station projection must align`);
    }
    if (city === 'new-york') {
      const dates = JSON.parse(fs.readFileSync(path.join(root, `public/data/${city}/daily/index.json`))).dates;
      for (const day of dates) {
        context.puzzles = JSON.parse(fs.readFileSync(path.join(root, `public/data/${city}/daily/${day}.json`))).puzzles;
        assert.ok(vm.runInContext(`puzzles.every(puzzle => {
          state.daily = [puzzle]; state.puzzleIndex = 0; state.currentStation = puzzle.start;
          fitCityMapToPuzzle();
          const v = CITY_MAP.viewBounds, b = CITY_MAP.bounds;
          return v.minLat >= b.minLat && v.maxLat <= b.maxLat && v.minLon >= b.minLon && v.maxLon <= b.maxLon;
        })`, context), `${city} ${day}: journey must not expose the edge of the coastline image`);
      }
    }
  } catch (error) { failures.push(error.message); }
}
assert.deepEqual(failures, [], failures.join('\n'));
console.log('All eight cities passed connection and map checks.');
