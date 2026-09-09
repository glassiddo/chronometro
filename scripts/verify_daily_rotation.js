#!/usr/bin/env node
// Check active calendar continuity, bundle size, and day-to-day puzzle rotation.
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const cities = ["paris", "london", "chicago", "washington-dc", "boston", "berlin", "madrid"];
const read = (file) => JSON.parse(fs.readFileSync(path.join(root, file), "utf8"));

for (const city of cities) {
  const index = read(`public/data/${city}/daily/index.json`);
  assert.equal(index.dates.length, new Set(index.dates).size, `${city}: duplicate indexed date`);
  assert.equal(index.metadata.dayCount, index.dates.length, `${city}: dayCount mismatch`);
  assert.equal(index.metadata.startDate, index.dates[0], `${city}: startDate mismatch`);
  assert.equal(index.metadata.endDate, index.dates.at(-1), `${city}: endDate mismatch`);
  const sets = new Set();
  index.dates.forEach((day, position) => {
    if (position) {
      const previous = new Date(`${index.dates[position - 1]}T00:00:00Z`);
      previous.setUTCDate(previous.getUTCDate() + 1);
      assert.equal(day, previous.toISOString().slice(0, 10), `${city}: calendar gap before ${day}`);
    }
    const daily = read(`public/data/${city}/daily/${day}.json`);
    assert.equal(daily.puzzles.length, 5, `${city} ${day}: expected five puzzles`);
    const ids = daily.puzzles.map((puzzle) => puzzle.id);
    assert.equal(new Set(ids).size, 5, `${city} ${day}: duplicate puzzle`);
    const signature = ids.slice().sort().join("|");
    assert(!sets.has(signature), `${city} ${day}: repeated daily puzzle set`);
    sets.add(signature);
  });
  console.log(`${city}: ${index.dates.length} continuous dates with unique five-puzzle sets`);
}
