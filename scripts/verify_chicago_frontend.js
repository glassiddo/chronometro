// Run with node scripts/verify_chicago_frontend.js.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "public/app.js"), "utf8");
const network = JSON.parse(fs.readFileSync(path.join(root, "public/data/chicago/network.json"), "utf8"));
const storage = new Map();
let markup = "";
let buttons = [];
const context = vm.createContext({
  URLSearchParams, console,
  window: { location: { search: "?city=chicago" } },
  document: {
    querySelector: () => ({ addEventListener() {}, textContent: "", hidden: false }),
    querySelectorAll: (selector) => buttons.filter((button) => button.attributes.includes(selector.slice(1, -1))),
  },
  localStorage: {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  },
  capture(html) {
    markup = html;
    buttons = [...html.matchAll(/<button\b([^>]*)>([\s\S]*?)<\/button>/g)].map((match) => ({
      attributes: match[1],
      text: match[2].replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim(),
      dataset: Object.fromEntries([...match[1].matchAll(/data-([\w-]+)="([^"]*)"/g)]
        .map((attribute) => [attribute[1].replace(/-([a-z])/g, (_, letter) => letter.toUpperCase()), attribute[2]])),
      addEventListener(event, callback) { if (event === "click") this.click = callback; },
    }));
  },
});
vm.runInContext(source.slice(0, source.lastIndexOf("init().catch(")), context);
context.network = network;
vm.runInContext(`
  state.data = network;
  state.dailyDate = "2026-09-21";
  state.dailyKind = "daily-puzzles";
  boardShell = capture;
  bindPuzzleToolbar = () => {};
  renderLineStep = () => {};
  renderResult = () => {};
  globalThis.api = { state, renderDirectionStep, renderAlightStep, renderRouteList,
    ridePathStationIds, saveProgress, restoreProgress, scoreRoute };
`, context);
const { api } = context;
const stationId = (name) => Object.values(network.stations).find((station) => station.name === name).id;
function start(routeId, from, to) {
  const fromId = stationId(from);
  Object.assign(api.state, {
    currentStation: fromId, steps: [], totalSec: 0, results: [], undoHistory: [], puzzleIndex: 0,
    daily: [{ start: fromId, end: stationId(to), optimalRoute: { totalSec: 1 } }],
    selected: { routeId, boards: [{ routeId, boardStation: fromId, walkSec: 0,
      directionIds: network.stations[fromId].services[routeId] }] },
  });
  api.renderDirectionStep();
}
function selectDirection(label) {
  const button = buttons.find((item) => item.dataset.directionIndex !== undefined && item.text === label);
  assert.ok(button, `Missing direction ${label}: ${buttons.map((item) => item.text).join(", ")}`);
  button.click();
}
function selectStop(name) {
  const id = stationId(name);
  const button = buttons.find((item) => item.dataset.alight === id);
  assert.ok(button, `Missing stop ${name}`);
  button.click();
  return api.state.steps.at(-1);
}

// Each round-trip pattern must offer its two physical boarding directions.
for (const [routeId, from, terminus] of [
  ["Brn", "Kedzie (Brown)", "Kimball"],
  ["Org", "Pulaski (Orange)", "Midway"],
  ["Pink", "Cicero (Pink)", "54th/Cermak"],
  ["P", "Central (Purple)", "Linden"],
]) {
  start(routeId, from, terminus);
  assert.ok(buttons.some((button) => button.text === "Loop"), `${routeId} must offer Loop-bound travel`);
  selectDirection(terminus);
  assert.ok(!buttons.some((button) => button.dataset.alight === stationId("Washington/Wabash")),
    `${routeId} outbound stop list must not contain Loop stops`);
  const leg = selectStop(terminus);
  assert.equal(api.ridePathStationIds(leg).length, 2, `${routeId} must ride directly to its terminus`);
}

start("Brn", "Kedzie (Brown)", "Belmont (Red/Brown/Purple)");
assert.ok(buttons.find((button) => button.text === "Loop").attributes.includes("destination-choice"));
assert.ok(!buttons.find((button) => button.text === "Kimball").attributes.includes("destination-choice"),
  "The outbound direction must not claim it reaches Belmont");
selectDirection("Loop");
const kedzieLeg = selectStop("Belmont (Red/Brown/Purple)");
assert.equal(kedzieLeg.rideSec, 913, "Kedzie to Belmont must retain the stored ride time");
assert.match(api.renderRouteList([kedzieLeg]), /Direction Loop/);

// Choosing the long way round must not silently switch to the outbound occurrence.
start("Brn", "Belmont (Red/Brown/Purple)", "Kimball");
selectDirection("Loop");
api.saveProgress();
api.state.selected = {};
assert.equal(api.restoreProgress(), true);
api.renderAlightStep();
const loopLeg = selectStop("Kimball");
assert.ok(api.ridePathStationIds(loopLeg).includes(stationId("Washington/Wabash")),
  "A saved Loop-bound choice must retain its path through downtown");
assert.equal(loopLeg.rideSec, 3860, "Loop-bound travel must charge the full circuit");
assert.notEqual(api.scoreRoute({ optimalRoute: { totalSec: 1200 } }, api.state.totalSec, api.state.steps).score, 100,
  "Scoring must not replace a Loop detour with a direct outbound journey");

// Old saves lacked an occurrence: keep progress but ask for the direction again.
start("Brn", "Kedzie (Brown)", "Kimball");
Object.assign(api.state.selected, {
  directionId: "Brn:0", boardStation: stationId("Kedzie (Brown)"), directionLabel: "Kimball",
  directionCandidates: [{ dirId: "Brn:0", boardStation: stationId("Kedzie (Brown)"), walkSec: 0, label: "Kimball" }],
});
api.renderAlightStep();
assert.equal(api.state.stage, "direction", "Legacy ambiguous stop selections must reopen the direction picker");

// Boarding inside the Loop and non-loop Purple local service retain their terminal labels.
start("Brn", "Washington/Wabash", "Kimball");
assert.ok(buttons.some((button) => button.text === "Kimball"));
assert.ok(!buttons.some((button) => button.text === "Loop"));
start("P", "Central (Purple)", "Howard");
selectDirection("Howard");
assert.ok(buttons.some((button) => button.dataset.alight === stationId("Howard")));

console.log("Chicago direction choices, stop lists, paths, timings, scoring and saved progress passed.");
