#!/usr/bin/env node
// Execute the browser timing helpers against every stored daily answer.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const cities = ["paris", "london", "chicago", "washington-dc", "boston", "berlin", "madrid", "new-york"];
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));
const app = fs.readFileSync(path.join(root, "public/app.js"), "utf8");

for (const city of cities) {
  const network = read(`public/data/${city}/network.json`);
  const context = vm.createContext({ URLSearchParams, window: { location: { search: `?city=${city}` } }, console });
  vm.runInContext(app.slice(0, app.lastIndexOf("init().catch(")), context);
  context.network = network;
  vm.runInContext("state.data = network", context);
  const evaluate = (expression) => vm.runInContext(expression, context);
  let puzzles = 0;
  let rides = 0;
  for (const day of read(`public/data/${city}/daily/index.json`).dates) {
    for (const puzzle of read(`public/data/${city}/daily/${day}.json`).puzzles) {
      puzzles++;
      let previous = null;
      for (const step of puzzle.optimalRoute.steps) {
        if (step.type === "walk") {
          previous = null;
          continue;
        }
        context.step = step;
        assert.equal(evaluate("runtimeBetween(step.directionId, step.from, step.to)"), step.rideSec, `${city} ${day}: ride runtime`);
        assert.equal(evaluate("combinedWaitSeconds(step.directionId, step.routeId, step.from, step.to)"), step.waitSec, `${city} ${day}: wait`);
        assert.equal(evaluate("ridePathStationIds(step).at(-1)"), step.to, `${city} ${day}: rendered endpoint`);
        if (previous && previous.to === step.from) {
          context.previous = previous;
          assert.equal(evaluate("transferSeconds(previous.to, step.from, previous.routeId, step.routeId, previous.mode, step.mode)"), step.transferSec, `${city} ${day}: interchange`);
        }
        previous = step;
        rides++;
      }
    }
  }
  console.log(`${city}: ${rides} rides across ${puzzles} puzzles match frontend timing`);
}
