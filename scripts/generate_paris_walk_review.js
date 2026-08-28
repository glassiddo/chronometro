const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const network = JSON.parse(fs.readFileSync(path.join(root, "public/data/paris/network.json"), "utf8"));
const cityConfig = JSON.parse(fs.readFileSync(path.join(root, "config/cities/paris.json"), "utf8"));

const pairKey = (left, right) => [left, right].sort().join("|");
const allowReasons = new Map([
  [pairKey("ITOAUTO112960", "ITOAUTO112996"), "Orly airport terminal connection"],
  [pairKey("PARIS16527", "PARIS9438"), "Auber–Opéra station complex"],
  [pairKey("ITOAUTO79135", "ITOAUTO80089"), "Bibliothèque François Mitterrand–Avenue de France interchange"],
  [pairKey("ITOAUTO69866", "PARIS137744"), "Boulainvilliers–La Muette out-of-station interchange"],
  [pairKey("ITOAUTO79860", "ITOAUTO80178"), "Champ de Mars–Bir-Hakeim interchange"],
  [pairKey("ITOAUTO135850", "PARIS208683"), "Châtelet station complex"],
  [pairKey("ITOAUTO135850", "PARIS166014"), "Châtelet–Les Halles station complex"],
  [pairKey("ITOAUTO79087", "PARIS16028"), "Gare du Nord–Gare de l’Est pedestrian interchange"],
  [pairKey("ITOAUTO79087", "PARIS9440"), "Gare du Nord–La Chapelle out-of-station interchange"],
  [pairKey("ITOAUTO79087", "PARIS16178"), "Gare du Nord–Magenta station complex"],
  [pairKey("ITOAUTO63174", "ITOAUTO97217"), "Montparnasse station complex"],
  [pairKey("ITOAUTO63174", "ITOAUTO97325"), "Montparnasse station complex"],
  [pairKey("ITOAUTO97217", "ITOAUTO97325"), "Duplicate Montparnasse Bienvenue records"],
  [pairKey("PARIS194562", "PARIS98644"), "Saint-Lazare–Saint-Augustin station complex"],
  [pairKey("ITOAUTO91269", "PARIS16527"), "Haussmann Saint-Lazare–Auber station complex"],
  [pairKey("ITOAUTO91269", "PARIS194562"), "Haussmann Saint-Lazare–Gare Saint-Lazare complex"],
  [pairKey("ITOAUTO91269", "ITOAUTO96919"), "Haussmann Saint-Lazare–Havre-Caumartin complex"],
  [pairKey("ITOAUTO96919", "PARIS16527"), "Havre-Caumartin–Auber station complex"],
  [pairKey("ITOAUTO96919", "PARIS194562"), "Havre-Caumartin–Gare Saint-Lazare complex"],
  [pairKey("PARIS166071", "PARIS174244"), "Duplicate Jules Joffrin records"],
  [pairKey("ITOAUTO79041", "PARIS166088"), "Musée d’Orsay–Solférino interchange"],
  [pairKey("ITOAUTO80181", "ITOAUTO90891"), "Porte Dauphine–Avenue Foch interchange"],
  [pairKey("ITO464", "PARIS16027"), "Duplicate Porte de Clichy records"],
  [pairKey("ITOAUTO79800", "ITOAUTO97123"), "Saint-Michel Notre-Dame–Cluny station complex"],
]);
const proposedAllows = new Set(
  cityConfig.network.walkingTransfers.allowedStationPairs.map(([left, right]) => pairKey(left, right)),
);

function distanceMetres(left, right) {
  const radians = Math.PI / 180;
  const lat1 = left.lat * radians;
  const lat2 = right.lat * radians;
  const deltaLat = (right.lat - left.lat) * radians;
  const deltaLon = (right.lon - left.lon) * radians;
  const h = Math.sin(deltaLat / 2) ** 2
    + Math.cos(lat1) * Math.cos(lat2) * Math.sin(deltaLon / 2) ** 2;
  return Math.round(6371000 * 2 * Math.atan2(Math.sqrt(h), Math.sqrt(1 - h)));
}

const pairs = new Map();
const transferSets = [network.transfers || {}, network.excludedTransfers || {}];
transferSets.forEach((transferSet) => Object.entries(transferSet).forEach(([from, destinations]) => {
  Object.entries(destinations).forEach(([to, seconds]) => {
    if (from === to) return;
    const key = pairKey(from, to);
    if (!pairs.has(key)) {
      const [left, right] = key.split("|");
      pairs.set(key, { key, left, right, leftToRight: null, rightToLeft: null });
    }
    const pair = pairs.get(key);
    if (from === pair.left) pair.leftToRight = seconds;
    else pair.rightToLeft = seconds;
  });
}));

const rows = [...pairs.values()].map((pair) => {
  const left = network.stations[pair.left];
  const right = network.stations[pair.right];
  return {
    ...pair,
    leftName: left.name,
    rightName: right.name,
    distance: distanceMetres(left, right),
    decision: proposedAllows.has(pair.key) ? "ALLOW" : "REJECT",
    reason: allowReasons.get(pair.key)
      || (proposedAllows.has(pair.key)
        ? "Approved station connection"
        : "Ordinary nearby stations; no recognized interchange identified"),
  };
}).sort((a, b) => a.decision.localeCompare(b.decision)
  || a.leftName.localeCompare(b.leftName, "fr")
  || a.rightName.localeCompare(b.rightName, "fr"));

const timing = (row) => {
  const forward = row.leftToRight == null ? "–" : row.leftToRight;
  const reverse = row.rightToLeft == null ? "–" : row.rightToLeft;
  return forward === reverse ? `${forward}s` : `${forward}/${reverse}s`;
};

const section = (decision) => rows.filter((row) => row.decision === decision).map((row) =>
  `| ${row.leftName} | ${row.rightName} | ${row.distance} m | ${timing(row)} | ${row.reason} |`,
).join("\n");

const allowCount = rows.filter((row) => row.decision === "ALLOW").length;
const rejectCount = rows.length - allowCount;
const markdown = `# Paris walking-transfer review

This is a decision draft only; it does not alter the network. It covers all ${rows.length} unique cross-station walk pairs currently present in \`network.json\`. Directional duplicates are combined, while same-station transfer records are excluded.

## Proposed allow (${allowCount})

| From | To | Straight-line distance | Feed time (forward/reverse) | Rationale |
|---|---|---:|---:|---|
${section("ALLOW")}

## Proposed reject (${rejectCount})

| From | To | Straight-line distance | Feed time (forward/reverse) | Rationale |
|---|---|---:|---:|---|
${section("REJECT")}
`;

fs.writeFileSync(path.join(root, "paris-walk-review.md"), markdown);
console.log(`Wrote paris-walk-review.md: ${allowCount} allow, ${rejectCount} reject.`);
