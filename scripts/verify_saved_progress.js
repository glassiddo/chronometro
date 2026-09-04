// Run with node scripts/verify_saved_progress.js.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../public/app.js"), "utf8");
const storage = new Map();
const context = vm.createContext({
  URLSearchParams, Date, console,
  window: { location: { search: "" } },
  document: { querySelector: () => ({ textContent: "" }) },
  localStorage: {
    getItem: (key) => storage.get(key) ?? null,
    setItem: (key, value) => storage.set(key, value),
  },
});
vm.runInContext(source.slice(0, source.lastIndexOf("init().catch(")) + `
  globalThis.testApi = { state, saveProgress, restoreProgress, progressKey };
`, context);
const { state, saveProgress, restoreProgress, progressKey } = context.testApi;
state.data = { stations: { a: {}, b: {} }, directions: { d: {} }, routes: { r: {} } };
state.daily = [{ start: "a", end: "b", optimalRoute: { totalSec: 20 } }];
state.dailyDate = "2026-09-04";
state.dailyKind = "daily-puzzles";
state.currentStation = "b";
state.steps = [{ type: "ride", from: "a", to: "b", directionId: "d", elapsedSec: 30 }];
state.totalSec = 30;
state.undoHistory = [{ stepCount: 0, totalSec: 0, currentStation: "a" }];
state.changesOnly = true;
saveProgress();
const saved = storage.get(progressKey());
state.steps = [];
state.totalSec = 0;
state.currentStation = "a";
assert.equal(restoreProgress(), true);
assert.equal(state.currentStation, "b");
assert.equal(state.totalSec, 30);
assert.equal(state.steps.length, 1);
assert.equal(state.undoHistory.length, 1);
assert.equal(state.changesOnly, true);

state.dailyDate = "2026-09-05";
assert.equal(restoreProgress(), false, "A different date must not restore yesterday's game");
state.dailyDate = "2026-09-04";
state.daily[0].optimalRoute.totalSec = 21;
assert.equal(restoreProgress(), false, "Changed puzzles invalidate old saves");
state.daily[0].optimalRoute.totalSec = 20;
for (const stage of ["result", "gave-up", "summary"]) {
  state.stage = stage;
  state.results = [{ score: 80 }];
  saveProgress();
  state.stage = "line";
  assert.equal(restoreProgress(), true);
  assert.equal(state.stage, stage);
}
storage.set(progressKey(), "not JSON");
assert.equal(restoreProgress(), false);
storage.set(progressKey(), saved);
context.localStorage.getItem = () => { throw new Error("Storage blocked"); };
context.localStorage.setItem = () => { throw new Error("Storage full"); };
assert.equal(restoreProgress(), false);
assert.doesNotThrow(saveProgress);
console.log("Saved progress: round-trip, dates, puzzle changes, results, invalid and unavailable storage passed.");
