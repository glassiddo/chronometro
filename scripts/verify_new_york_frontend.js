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
  window: { location: { search: "?city=new-york&mode=hard" } },
  console,
});
vm.runInContext(app.slice(0, app.lastIndexOf("init().catch(")), context);

context.testData = {
  canonicalStationIds: { platformA: "complex", platformB: "complex" },
  interchangeableDirectionRoutes: [],
  directions: {},
  routes: {
    A: { id: "A", mode: "subway" },
    "7": { id: "7", mode: "subway" },
    "7X": { id: "7X", mode: "subway" },
  },
  stations: {
    origin: { id: "origin", name: "Origin" },
    platformA: { id: "platformA", name: "Platform A" },
    platformB: { id: "platformB", name: "Platform B" },
    destination: { id: "destination", name: "Destination" },
  },
  transfers: { platformA: { platformB: 180 } },
  routeTransfers: {},
  metadata: { waitSecondsByDirection: {}, waitSecondsByRoute: {}, waitSecondsByMode: { subway: 240 } },
};
vm.runInContext("state.data = testData", context);

const visible = vm.runInContext(`reviewVisibleSteps([
  { type: "ride", routeId: "A", from: "origin", to: "platformA", transferSec: 0, elapsedSec: 300 },
  { type: "walk", from: "platformA", to: "platformB", transferSec: 180, elapsedSec: 180 },
  { type: "ride", routeId: "7", from: "platformB", to: "destination", transferSec: 60, elapsedSec: 360 },
], { foldWalks: true })`, context);
check(visible.length === 3, "Route summaries must show internal station-complex walks");
check(visible[1].type === "walk" && visible[1].transferSec === 180,
  "The visible walk must retain its transfer time");

const external = vm.runInContext(`reviewVisibleSteps([
  { type: "walk", from: "platformA", to: "streetTransfer", transferSec: 300, elapsedSec: 300 },
])`, context);
check(external.length === 1, "Genuine between-complex walks must remain visible");

vm.runInContext(`
  state.currentStation = "platformA";
  state.steps = [
    { type: "ride", routeId: "A", directionId: "a", from: "origin", to: "platformA", elapsedSec: 300 },
  ];
  state.totalSec = 300;
  state.undoHistory = [];
  state.daily = [{ end: "elsewhere" }];
  state.puzzleIndex = 0;
  state.selected = { routeId: "7", directionId: "local", boardStation: "platformB" };
  runtimeBetween = () => 120;
  legTiming = () => ({ rideSec: 120, waitSec: 30, transferSec: 0, elapsedSec: 150 });
  rideSegmentsBetween = () => [];
  rememberMove = () => {};
  renderLineStep = () => {};
  samePuzzleStation = () => false;
  addLeg("destination");
  internalTransferSteps = state.steps;
`, context);
check(context.internalTransferSteps.length === 3,
  "Boarding through another record in the same station complex must add a step");
check(context.internalTransferSteps[1].type === "walk"
  && context.internalTransferSteps[1].from === "platformA"
  && context.internalTransferSteps[1].to === "platformB"
  && context.internalTransferSteps[1].transferSec === 180,
"The added station-complex step must describe the actual transfer");

vm.runInContext(`
  state.currentStation = "platformA";
  state.steps = [];
  state.totalSec = 0;
  state.undoHistory = [];
  state.daily = [{ start: "platformA", end: "elsewhere" }];
  state.selected = { routeId: "7", directionId: "local", boardStation: "platformB" };
  samePuzzleStation = (_stationId, puzzleStationId) => puzzleStationId === "platformA";
  addLeg("destination");
  firstBoardingSteps = state.steps;
`, context);
check(context.firstBoardingSteps.length === 2
  && context.firstBoardingSteps[0].type === "walk"
  && context.firstBoardingSteps[0].elapsedSec === 0,
"A free first boarding through another station record must remain visible without changing the score");

const initialLabel = vm.runInContext(
  'typeof initialGameLabel === "function" ? initialGameLabel() : undefined',
  context,
);
check(initialLabel === "New York City · Hard",
  "The loading header must use the requested city and mode before network data loads");
check(!html.includes('<strong id="currentGameLabel">Paris · Easy</strong>'),
  "The initial HTML must not show a hard-coded city while the app starts");

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
check(config.puzzles.days === 78, "NYC daily calendar must extend through 30 November 2026");

console.log("New York frontend verification passed.");
