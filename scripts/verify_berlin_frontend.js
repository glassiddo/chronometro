#!/usr/bin/env node
// Execute the actual browser timing helpers against every regenerated answer.
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const assert = require("node:assert/strict");
const root = path.resolve(__dirname, "..");
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
const network = read("public/data/berlin/network.json");
const context = vm.createContext({ URLSearchParams, window: { location: { search: "?city=berlin" } }, console });
const app = fs.readFileSync(path.join(root, "public/app.js"), "utf8");
vm.runInContext(app.slice(0, app.lastIndexOf("init().catch(")), context);
context.network = network;
vm.runInContext("state.data = network", context);
const evaluate = (expression) => vm.runInContext(expression, context);
let rides = 0;
for (const day of read("public/data/berlin/daily/index.json").dates) {
  for (const puzzle of read(`public/data/berlin/daily/${day}.json`).puzzles) {
    let previous = null;
    for (const step of puzzle.optimalRoute.steps) {
      context.step = step;
      if (step.type === "walk") { previous = null; continue; }
      assert.equal(evaluate("runtimeBetween(step.directionId, step.from, step.to)"), step.rideSec, `${day}: ride runtime`);
      assert.equal(evaluate("combinedWaitSeconds(step.directionId, step.routeId, step.from, step.to)"), step.waitSec, `${day}: shared wait`);
      assert.equal(evaluate("ridePathStationIds(step).at(-1)"), step.to, `${day}: rendered route endpoint`);
      if (previous && previous.to === step.from) {
        context.previous = previous;
        assert.equal(evaluate("transferSeconds(previous.to, step.from, previous.routeId, step.routeId, previous.mode, step.mode)"), step.transferSec, `${day}: interchange`);
      }
      previous = step;
      rides++;
    }
  }
}
for (const direction of Object.values(network.directions).filter(d => d.circular)) {
  context.ring = direction;
  const actual = evaluate("runtimeBetween(ring.id, ring.stations[26], ring.stations[1])");
  assert.equal(actual, direction.runtimes[26] + direction.runtimes[27]);
  assert.equal(new Set(direction.stations.slice(27, 53)).size, 26);
}
console.log(`Berlin frontend timing parity passed: ${rides} rides across 135 puzzles, both ring seams`);
