// Run with node scripts/verify_frontend_walk_timing.js.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../public/app.js"), "utf8");
const context = vm.createContext({
  URLSearchParams, Date, console,
  window: { location: { search: "" } },
  document: { querySelector: () => ({ textContent: "" }) },
});
vm.runInContext(source.slice(0, source.lastIndexOf("init().catch(")) + `
  globalThis.testApi = { state, legTiming, normalizeWalkTimings };
`, context);

const { state, legTiming, normalizeWalkTimings } = context.testApi;
state.data = {
  routes: {
    previous: { id: "previous", mode: "metro", label: "Previous" },
    next: { id: "next", mode: "metro", label: "Next" },
  },
  directions: {
    nextDirection: { id: "nextDirection", routeId: "next", stations: ["walk-to", "destination"] },
  },
  metadata: {
    waitSecondsByDirection: { nextDirection: 35 },
    waitSecondsByRoute: {},
    waitSecondsByMode: { metro: 60 },
    transferFallbackSeconds: { same_mode: 180, fallback: 240 },
  },
  transfers: { "walk-from": { "walk-to": 332 } },
  routeTransfers: { "walk-from": { "walk-to": { previous: { next: 108 } } } },
  sharedServiceGroups: [],
  combinePatternsWithinRoutes: [],
};
state.steps = [
  { type: "ride", routeId: "previous", directionId: "previousDirection", from: "origin", to: "walk-from", elapsedSec: 100 },
  { type: "walk", from: "walk-from", to: "walk-to", transferSec: 332, elapsedSec: 332 },
];
state.totalSec = 432;

const timing = legTiming({ routeId: "next", directionId: "nextDirection", boardStation: "walk-to" }, "destination", 60);
assert.equal(state.steps[1].transferSec, 108, "The walk must use its route-pair-specific duration");
assert.equal(state.steps[1].elapsedSec, 108);
assert.equal(state.totalSec, 208, "The already-counted generic walk must be replaced");
assert.equal(timing.transferSec, 0, "Boarding after a walk must not add another interchange");
assert.equal(timing.elapsedSec, 95, "Only ride and wait remain on the following leg");

delete state.data.routeTransfers["walk-from"]["walk-to"].previous.next;
state.steps[1].transferSec = 332;
state.steps[1].elapsedSec = 332;
state.totalSec = 432;
const genericTiming = legTiming({ routeId: "next", directionId: "nextDirection", boardStation: "walk-to" }, "destination", 60);
assert.equal(state.steps[1].transferSec, 332, "Generic walks remain unchanged when no route-pair override exists");
assert.equal(genericTiming.transferSec, 0, "A generic walk also replaces the interchange charge");

state.data.routeTransfers["walk-from"]["walk-to"].previous.next = 108;
state.steps = [
  { type: "ride", routeId: "previous", from: "origin", to: "walk-from", elapsedSec: 100 },
  { type: "walk", from: "walk-from", to: "walk-to", transferSec: 332, elapsedSec: 332 },
  { type: "ride", routeId: "next", from: "walk-to", to: "destination", transferSec: 180, waitSec: 35, rideSec: 60, elapsedSec: 275 },
];
state.totalSec = 707;
normalizeWalkTimings();
assert.equal(state.steps[1].elapsedSec, 108, "Restored walks must be resolved against their adjacent routes");
assert.equal(state.steps[2].transferSec, 0, "Restored routes must lose the duplicate post-walk interchange");
assert.equal(state.steps[2].elapsedSec, 95);
assert.equal(state.totalSec, 303, "Restored total time must be rebuilt from normalized steps");

console.log("Frontend walk timing: route-specific and generic transfers passed.");
