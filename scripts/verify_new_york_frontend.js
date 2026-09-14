const fs = require("fs");
const path = require("path");
const vm = require("vm");

const root = path.resolve(__dirname, "..");
const app = fs.readFileSync(path.join(root, "public", "app.js"), "utf8");
const css = fs.readFileSync(path.join(root, "public", "styles.css"), "utf8");
const html = fs.readFileSync(path.join(root, "public", "index.html"), "utf8");
const mapBuilder = fs.readFileSync(path.join(root, "scripts", "build_new_york_basemap.py"), "utf8");
const config = JSON.parse(fs.readFileSync(path.join(root, "config", "cities", "new-york.json"), "utf8"));

function check(condition, message) {
  if (!condition) throw new Error(message);
}

const context = vm.createContext({
  URLSearchParams,
  window: { location: { search: "?city=new-york" } },
  console,
});
vm.runInContext(app.slice(0, app.lastIndexOf("init().catch(")), context);

context.testData = {
  canonicalStationIds: { platformA: "complex", platformB: "complex" },
  interchangeableDirectionRoutes: [],
  directions: {},
  routes: {
    "7": { id: "7", mode: "subway" },
    "7X": { id: "7X", mode: "subway" },
  },
  metadata: { waitSecondsByDirection: {}, waitSecondsByRoute: {}, waitSecondsByMode: { subway: 240 } },
};
vm.runInContext("state.data = testData", context);

const folded = vm.runInContext(`reviewVisibleSteps([
  { type: "ride", routeId: "A", from: "origin", to: "platformA", transferSec: 0, elapsedSec: 300 },
  { type: "walk", from: "platformA", to: "platformB", transferSec: 180, elapsedSec: 180 },
  { type: "ride", routeId: "7", from: "platformB", to: "destination", transferSec: 60, elapsedSec: 360 },
], { foldWalks: true })`, context);
check(folded.length === 2, "Fastest-route display must hide internal station-complex walks");
check(folded[1].transferSec === 240 && folded[1].elapsedSec === 540,
  "Internal station-complex walk time must be folded into the following ride");
context.foldedRide = folded[1];
const foldedBreakdown = vm.runInContext("formatLegBreakdown(foldedRide)", context);
check(foldedBreakdown.includes("transfer+walk"),
  "A folded internal walk must still be identified in the timing breakdown");

const external = vm.runInContext(`reviewVisibleSteps([
  { type: "walk", from: "platformA", to: "streetTransfer", transferSec: 300, elapsedSec: 300 },
])`, context);
check(external.length === 1, "Genuine between-complex walks must remain visible");

vm.runInContext(`
  runtimeBetween = (directionId) => directionId === "local" ? 300 : 200;
  combinedWaitSeconds = (_directionId, routeId) => routeId === "7" ? 30 : 300;
  testSelection = {
    routeId: "7",
    boardStation: "start",
    directionCandidates: [
      { routeId: "7", dirId: "local", boardStation: "start", walkSec: 0 },
      { routeId: "7X", dirId: "express", boardStation: "start", walkSec: 0 },
    ],
  };
  testBest = bestEquivalentDirectionCandidate(testSelection, "finish");
`, context);
check(context.testBest.routeId === "7" && context.testBest.dirId === "local",
  "Grouped local/express choices must calculate each candidate with its own route wait");

vm.runInContext(`
  state.currentStation = "start";
  state.steps = [];
  state.totalSec = 0;
  state.undoHistory = [];
  state.daily = [{ end: "elsewhere" }];
  state.puzzleIndex = 0;
  state.selected = {
    routeId: "7",
    directionId: "local",
    boardStation: "start",
    directionCandidates: [
      { routeId: "7", dirId: "local", boardStation: "start", walkSec: 0 },
      { routeId: "7X", dirId: "express", boardStation: "start", walkSec: 0 },
    ],
  };
  runtimeBetween = (directionId) => directionId === "local" ? 300 : 200;
  combinedWaitSeconds = (_directionId, routeId) => routeId === "7" ? 300 : 30;
  legTiming = (selected, _to, rideSec) => ({ rideSec, waitSec: 0, transferSec: 0, elapsedSec: rideSec });
  rideSegmentsBetween = () => [];
  rememberMove = () => {};
  renderLineStep = () => {};
  samePuzzleStation = () => false;
  addLeg("finish");
  addedVariantLeg = state.steps[0];
`, context);
check(context.addedVariantLeg.routeId === "7X" && context.addedVariantLeg.directionId === "express",
  "Choosing an express candidate must update the route and direction together");

check(app.includes('if (CITY_ID === "new-york") return `Line ${routeDisplayName(r)}`'), "NYC boarding choices must use public line names");
check(app.includes('const groupKey = CITY_ID === "new-york" ? routeDisplayName(r) : routeId;'), "NYC local and express variants must share one boarding choice");
check(app.includes('state.selected.routeId = option.candidates[0].routeId'), "Grouped NYC services must preserve their underlying route when selected");
check(app.includes('uniqueRouteDisplayIds(') && app.includes('CITY_ID === "new-york"'), "NYC station bullets must be deduplicated");
check(!app.includes('"berlin", "new-york"].includes(CITY_ID)'), "NYC must not use badge-only boarding choices");
check(app.includes('$("#beginGame").textContent = verb;'), "Setup action must say only Start or Resume");
check(!html.includes('<span>Playing</span>'), "The game switcher must not include a Playing eyebrow");
check(html.includes('class="game-change"'), "Change must be a distinct button label");
check(app.includes('isNewYork ? NEW_YORK_BASEMAP_URL'), "NYC map must use the official borough coastline basemap");
check(app.includes('{ minLat: 40.49, maxLat: 40.94, minLon: -74.26, maxLon: -73.68 }'), "NYC app and generated basemap must use identical bounds");
check(app.includes('return mapImageMarkup(NEW_YORK_NETWORK_MAP_URL);'), "NYC must draw a land-clipped network overlay");
check(!app.includes('if (CITY_ID === "new-york") {\n    CITY_MAP.viewBounds = CITY_MAP.bounds;'), "NYC must retain journey-focused map zoom");
check(mapBuilder.includes('clipPath id="land"'), "NYC network overlay must be clipped to borough land");
check(mapBuilder.includes('stroke-width="0.65"') && mapBuilder.includes('opacity="0.22"'), "NYC network context must remain visually restrained");
check(mapBuilder.includes('fill="#78c4e4"'), "NYC water must remain visibly blue against surrounding land");
check(mapBuilder.includes("surrounding-land.geojson"), "NYC basemap must include surrounding regional land");
check(mapBuilder.includes("PAD = 12") && mapBuilder.includes("WIDTH - PAD * 2"), "NYC coastline and subway network must share the same padded projection");
check(css.includes(".city-option span {\n  height: 52px;"), "All city tiles must have an equal fixed height");
check(css.includes('.toolbar .danger-action'), "Destructive route control must have button styling");
check(!css.includes('[data-city="new-york"] .waterway'), "NYC must not add schematic river strokes over its coastline geometry");
check(app.includes("const internalTransfer = sameStation(state.currentStation, selected.boardStation)"), "Internal NYC station changes must be folded into the ride");
check(app.includes("timing.transferSec += internalTransferSec;"), "Internal station transfer time must still be counted");
check(config.puzzles.days === 48, "NYC daily calendar must end with GTFS validity on 31 October 2026");

console.log("New York frontend verification passed.");
