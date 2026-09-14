const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const source = fs.readFileSync(path.join(__dirname, "../public/app.js"), "utf8");
const rendered = [];
const document = {
  querySelector: () => ({ addEventListener() {}, textContent: "" }),
  querySelectorAll: () => [],
};
const context = vm.createContext({
  URLSearchParams,
  console,
  document,
  window: { location: { search: "?city=washington-dc" } },
});
vm.runInContext(source.slice(0, source.lastIndexOf("init().catch(")), context);

vm.runInContext(`
  state.data = {
    stations: {
      start: { id: "start", name: "Start", services: { silver: ["same-slow", "same-fast", "branch"] } },
      shared: { id: "shared", name: "Shared", services: {} },
      finish: { id: "finish", name: "Finish", services: {} },
      branchStop: { id: "branchStop", name: "Branch stop", services: {} },
    },
    routes: { silver: { id: "silver", label: "Silver", mode: "metro", color: "#999", textColor: "#000" } },
    directions: {
      "same-slow": { id: "same-slow", routeId: "silver", label: "Slow terminus", stations: ["start", "shared", "finish"], runtimes: [100, 100] },
      "same-fast": { id: "same-fast", routeId: "silver", label: "Fast terminus", stations: ["start", "shared", "finish"], runtimes: [100, 100] },
      branch: { id: "branch", routeId: "silver", label: "Branch terminus", stations: ["start", "branchStop", "finish"], runtimes: [40, 40] },
    },
    metadata: {
      waitSecondsByDirection: { "same-slow": 150, "same-fast": 120, branch: 10 },
      waitSecondsByRoute: {},
      waitSecondsByMode: { metro: 180 },
      transferFallbackSeconds: { same_mode: 30, fallback: 30 },
    },
    transfers: {}, routeTransfers: {}, canonicalStationIds: {},
    sharedServiceGroups: [], combinePatternsWithinRoutes: [], routeContinuations: [],
  };
  state.daily = [{ end: "finish", optimalRoute: { totalSec: 320 } }];
  state.puzzleIndex = 0;
`, context);

const samePathScore = vm.runInContext(`scoreRoute(currentPuzzle(), 350, [{
  type: "ride", routeId: "silver", directionId: "same-slow", from: "start", to: "finish",
  rideSec: 200, waitSec: 150, transferSec: 0, elapsedSec: 350,
}])`, context);
assert.equal(samePathScore.score, 100,
  "Same-line patterns with an identical ridden station sequence must use the fastest compatible timing");

const differentBranchScore = vm.runInContext(`scoreRoute(
  { optimalRoute: { totalSec: 90 } },
  350,
  [{ type: "ride", routeId: "silver", directionId: "same-slow", from: "start", to: "finish", rideSec: 200, waitSec: 150, transferSec: 0, elapsedSec: 350 }],
)`, context);
assert.notEqual(differentBranchScore.score, 100,
  "A direction using a different intermediate-station path must not replace the selected branch timing");

const preservedTransferTiming = vm.runInContext(`fastestSamePathTiming({
  type: "ride", routeId: "silver", directionId: "same-slow", from: "start", to: "finish",
  rideSec: 200, waitSec: 150, transferSec: 90, elapsedSec: 440,
}, { routeId: "silver" })`, context);
assert.equal(preservedTransferTiming, 410,
  "Direction normalization must preserve the transfer time already recorded on the selected leg");

vm.runInContext(`
  state.mode = "easy";
  state.currentStation = "start";
  state.selected = { routeId: "silver", boards: [{
    routeId: "silver", boardStation: "start", walkSec: 0,
    directionIds: ["same-slow", "branch"],
  }] };
  boardShell = (markup) => { globalThis.renderedMarkup = markup; };
  bindPuzzleToolbar = () => {};
  renderDirectionStep();
`, context);
assert.match(context.renderedMarkup, /class="choice destination-choice"[^>]*data-direction-index="0"/,
  "Easy mode must highlight a direction option that reaches the destination");
assert.match(context.renderedMarkup, /class="choice destination-choice"[^>]*data-direction-index="1"/,
  "Easy mode must highlight every direction option that reaches the destination");

vm.runInContext(`state.mode = "hard"; renderDirectionStep();`, context);
assert.doesNotMatch(context.renderedMarkup, /destination-choice/,
  "Hard mode must not highlight destination-reaching directions");

console.log("Frontend route scoring and Easy direction guidance passed.");
