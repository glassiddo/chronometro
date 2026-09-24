// Run with node scripts/verify_loop_direction_frontend.js.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const root = path.resolve(__dirname, "..");
const source = fs.readFileSync(path.join(root, "public/app.js"), "utf8");
const context = vm.createContext({
  URLSearchParams,
  console,
  window: { location: { search: "?city=example" } },
  document: {
    querySelector: () => ({ addEventListener() {}, textContent: "", hidden: false }),
    querySelectorAll: () => [],
  },
  localStorage: { getItem: () => null, setItem() {} },
});

vm.runInContext(source.slice(0, source.lastIndexOf("init().catch(")), context);
vm.runInContext(`
  state.data = {
    directions: {
      "loop:0": {
        id: "loop:0",
        routeId: "loop",
        label: "Terminus",
        stations: ["terminus", "outbound", "board", "loop-a", "loop-b", "board", "outbound", "terminus"],
        runtimes: [60, 60, 60, 60, 60, 60, 60],
      },
    },
  };
  globalThis.api = { boardingDirectionCandidates };
`, context);

const candidates = context.api.boardingDirectionCandidates({
  routeId: "loop",
  boardStation: "board",
  walkSec: 0,
  directionIds: ["loop:0"],
}, "loop");

assert.deepEqual(
  candidates.map((candidate) => candidate.label).sort(),
  ["Loop", "Terminus"],
  "Repeated-terminal patterns must expose both physical boarding directions in every city",
);
assert.deepEqual(
  candidates.map((candidate) => candidate.boardIndex).sort((a, b) => a - b),
  [2, 5],
  "Each physical direction must preserve its boarding occurrence",
);

console.log("Generic repeated-terminal direction choices passed.");
