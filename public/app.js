const NETWORK_URL = "./data/metro-express-network.json";
const DAILY_INDEX_URL = "./data/daily/index.json";
const DAILY_BASE_URL = "./data/daily";
const EXAMPLE_URL = "./data/example/metro-express-example-data.json";
const FALLBACK_DAILY_COUNT = 5;

const state = {
  data: null,
  daily: [],
  dailyDate: "",
  dailyKind: "",
  puzzleIndex: 0,
  currentStation: null,
  steps: [],
  totalSec: 0,
  stage: "line",
  selected: {},
  results: [],
  hintText: "",
  showConnectingLines: true,
};

const $ = (selector) => document.querySelector(selector);

function station(id) {
  return state.data.stations[id] || { id, name: id };
}

function canonicalStationId(stationId) {
  return state.data.canonicalStationIds?.[stationId] || stationId;
}

function sameStation(leftId, rightId) {
  return canonicalStationId(leftId) === canonicalStationId(rightId);
}

function route(id) {
  return state.data.routes[id];
}

function direction(id) {
  return state.data.directions[id];
}

function modeName(mode) {
  return { metro: "Metro", rer: "RER", tram: "Tram", bus: "Bus" }[mode] || mode;
}

function compareText(left, right) {
  const sortParts = (value) => {
    const text = String(value).trim();
    const suffix = text.match(/\s+\((\d+)\)$/);
    return {
      base: text.replace(/\s+\(\d+\)$/, ""),
      suffix: suffix ? Number(suffix[1]) : 0,
      full: text,
    };
  };
  const a = sortParts(left);
  const b = sortParts(right);
  return (
    a.base.localeCompare(b.base, "fr", { sensitivity: "base", numeric: true }) ||
    a.suffix - b.suffix ||
    a.full.localeCompare(b.full, "fr", { sensitivity: "base", numeric: true })
  );
}

function formatTime(sec) {
  const min = Math.floor(sec / 60);
  const rem = Math.round(sec % 60);
  const minuteText = `${min} ${min === 1 ? "min" : "mins"}`;
  return rem ? `${minuteText} ${rem}s` : minuteText;
}

function formatCompactTime(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return "";
  if (sec < 60) return `${Math.round(sec)}s`;
  const min = Math.round(sec / 60);
  return `${min} ${min === 1 ? "min" : "mins"}`;
}

function formatSignedTime(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return "Matched fastest time";
  return `+${formatTime(sec)} vs fastest`;
}

function formatLegBreakdown(leg) {
  const parts = [
    ["Transfer", leg.transferSec],
    ["Wait", leg.waitSec],
    ["Ride", leg.rideSec],
  ]
    .filter(([, sec]) => Number.isFinite(sec) && sec > 0)
    .map(([label, sec]) => `${label} ${formatCompactTime(sec)}`);
  return parts.length ? parts.join(" · ") : "";
}

function stepType(step) {
  return step.type || "ride";
}

function parisDateString(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: "Europe/Paris",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(date);
  const get = (type) => parts.find((part) => part.type === type).value;
  return `${get("year")}-${get("month")}-${get("day")}`;
}

function hashString(input) {
  let hash = 2166136261;
  for (let i = 0; i < input.length; i += 1) {
    hash ^= input.charCodeAt(i);
    hash = Math.imul(hash, 16777619);
  }
  return hash >>> 0;
}

function rng(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let t = value;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function puzzleCount() {
  return state.daily.length || FALLBACK_DAILY_COUNT;
}

function lineBadge(routeId) {
  const r = route(routeId);
  return `<span class="line-badge" style="background:${r.color};color:${r.textColor}">${r.label}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setRoundLabel() {
  $("#todayLabel").textContent = state.dailyDate || parisDateString();
  $("#roundLabel").textContent =
    state.stage === "summary" ? "Done" : `${state.puzzleIndex + 1} / ${puzzleCount()}`;
}

function currentPuzzle() {
  return state.daily[state.puzzleIndex];
}

function renderRouteList(steps, { showDirection = true, showDetail = true } = {}) {
  if (!steps.length) return `<p class="muted">No steps yet.</p>`;
  return steps
    .map(
      (step) => {
        const detail = showDetail ? formatLegBreakdown(step) : "";
        if (stepType(step) === "walk") {
          return `
        <div class="leg-chip walk-chip">
          <span class="walk-badge">Walk</span>
          <p>
            <strong>Walk to ${escapeHtml(station(step.to).name)}</strong>
            ${detail ? `<small class="leg-detail">${escapeHtml(detail)}</small>` : ""}
          </p>
          <small>${Number.isFinite(step.elapsedSec) && step.elapsedSec > 0 ? formatTime(step.elapsedSec) : ""}</small>
        </div>
      `;
        }
        return `
        <div class="leg-chip">
          ${lineBadge(step.routeId)}
          <p>
            <strong>${escapeHtml(station(step.from).name)} -> ${escapeHtml(station(step.to).name)}</strong>
            ${showDirection ? `<small>Direction ${escapeHtml(direction(step.directionId).label)}</small>` : ""}
            ${detail ? `<small class="leg-detail">${escapeHtml(detail)}</small>` : ""}
          </p>
          <small>${Number.isFinite(step.elapsedSec) && step.elapsedSec > 0 ? formatTime(step.elapsedSec) : ""}</small>
        </div>
      `;
      },
    )
    .join("");
}

function finalStationLineHint() {
  const puzzle = currentPuzzle();
  const lines = new Map();
  Object.values(state.data.directions).forEach((dir) => {
    if (!dir.stations.some((stationId) => sameStation(stationId, puzzle.end))) return;
    const r = route(dir.routeId);
    lines.set(dir.routeId, `${modeName(r.mode)} ${r.label}`);
  });
  return [...lines.values()].sort(compareText).join(", ");
}

function hintMarkup() {
  return state.hintText ? `<p class="hint">${escapeHtml(state.hintText)}</p>` : "";
}

const PARIS_MAP = {
  "width": 320,
  "height": 220,
  "bounds": {
    "minLat": 48.805,
    "maxLat": 48.915,
    "minLon": 2.2,
    "maxLon": 2.49
  },
  "outline": [
    [
      2.224122,
      48.854199
    ],
    [
      2.224169,
      48.853442
    ],
    [
      2.239558,
      48.850038
    ],
    [
      2.24031,
      48.8496
    ],
    [
      2.242467,
      48.847731
    ],
    [
      2.250676,
      48.845627
    ],
    [
      2.252535,
      48.845569
    ],
    [
      2.251222,
      48.842863
    ],
    [
      2.251649,
      48.838906
    ],
    [
      2.255154,
      48.834805
    ],
    [
      2.26296,
      48.833899
    ],
    [
      2.266178,
      48.834452
    ],
    [
      2.266925,
      48.834517
    ],
    [
      2.267469,
      48.834627
    ],
    [
      2.267948,
      48.834576
    ],
    [
      2.268878,
      48.833815
    ],
    [
      2.27003,
      48.833008
    ],
    [
      2.2673,
      48.831559
    ],
    [
      2.267605,
      48.827967
    ],
    [
      2.267806,
      48.82785
    ],
    [
      2.272744,
      48.827933
    ],
    [
      2.275791,
      48.829704
    ],
    [
      2.279054,
      48.832445
    ],
    [
      2.283363,
      48.830862
    ],
    [
      2.292221,
      48.827138
    ],
    [
      2.332372,
      48.818207
    ],
    [
      2.331741,
      48.817026
    ],
    [
      2.33382,
      48.816756
    ],
    [
      2.341667,
      48.816344
    ],
    [
      2.343054,
      48.816066
    ],
    [
      2.344497,
      48.815576
    ],
    [
      2.344432,
      48.816106
    ],
    [
      2.34692,
      48.815865
    ],
    [
      2.352399,
      48.818534
    ],
    [
      2.355917,
      48.815972
    ],
    [
      2.363408,
      48.816059
    ],
    [
      2.366168,
      48.816914
    ],
    [
      2.380745,
      48.821688
    ],
    [
      2.381514,
      48.822413
    ],
    [
      2.388812,
      48.825006
    ],
    [
      2.389778,
      48.82552
    ],
    [
      2.394352,
      48.827513
    ],
    [
      2.395746,
      48.827732
    ],
    [
      2.402488,
      48.829647
    ],
    [
      2.403919,
      48.82907
    ],
    [
      2.404584,
      48.828725
    ],
    [
      2.405453,
      48.828147
    ],
    [
      2.407283,
      48.826765
    ],
    [
      2.408771,
      48.825828
    ],
    [
      2.409904,
      48.825307
    ],
    [
      2.410804,
      48.825052
    ],
    [
      2.412617,
      48.824816
    ],
    [
      2.413848,
      48.824796
    ],
    [
      2.415661,
      48.824858
    ],
    [
      2.416708,
      48.824794
    ],
    [
      2.417815,
      48.824607
    ],
    [
      2.419327,
      48.824249
    ],
    [
      2.419322,
      48.824212
    ],
    [
      2.420228,
      48.824121
    ],
    [
      2.421691,
      48.824126
    ],
    [
      2.424475,
      48.82427
    ],
    [
      2.425957,
      48.824229
    ],
    [
      2.427833,
      48.824011
    ],
    [
      2.429751,
      48.823565
    ],
    [
      2.430691,
      48.823234
    ],
    [
      2.430386,
      48.82288
    ],
    [
      2.43219,
      48.821618
    ],
    [
      2.432624,
      48.821902
    ],
    [
      2.432889,
      48.82169
    ],
    [
      2.432474,
      48.82142
    ],
    [
      2.434302,
      48.820156
    ],
    [
      2.43418,
      48.819281
    ],
    [
      2.434323,
      48.819385
    ],
    [
      2.4345,
      48.819373
    ],
    [
      2.435165,
      48.819649
    ],
    [
      2.436266,
      48.81956
    ],
    [
      2.436968,
      48.819363
    ],
    [
      2.43747,
      48.819105
    ],
    [
      2.43735,
      48.818219
    ],
    [
      2.439751,
      48.818366
    ],
    [
      2.442159,
      48.817976
    ],
    [
      2.444983,
      48.81795
    ],
    [
      2.447613,
      48.818027
    ],
    [
      2.449638,
      48.817962
    ],
    [
      2.450826,
      48.817809
    ],
    [
      2.453317,
      48.817294
    ],
    [
      2.454549,
      48.817137
    ],
    [
      2.457215,
      48.817018
    ],
    [
      2.458633,
      48.817012
    ],
    [
      2.459249,
      48.817245
    ],
    [
      2.459197,
      48.817334
    ],
    [
      2.459755,
      48.81754
    ],
    [
      2.462803,
      48.819028
    ],
    [
      2.462524,
      48.819267
    ],
    [
      2.462639,
      48.819344
    ],
    [
      2.462906,
      48.820203
    ],
    [
      2.464717,
      48.823278
    ],
    [
      2.465247,
      48.824496
    ],
    [
      2.465101,
      48.824986
    ],
    [
      2.465359,
      48.825004
    ],
    [
      2.466178,
      48.827333
    ],
    [
      2.46523,
      48.82767
    ],
    [
      2.465087,
      48.82754
    ],
    [
      2.46461,
      48.827627
    ],
    [
      2.464514,
      48.82861
    ],
    [
      2.464642,
      48.829365
    ],
    [
      2.46523,
      48.831151
    ],
    [
      2.465721,
      48.831887
    ],
    [
      2.466427,
      48.832522
    ],
    [
      2.468375,
      48.833537
    ],
    [
      2.468938,
      48.833991
    ],
    [
      2.469389,
      48.834615
    ],
    [
      2.469704,
      48.835556
    ],
    [
      2.469758,
      48.836446
    ],
    [
      2.469505,
      48.836891
    ],
    [
      2.467232,
      48.839094
    ],
    [
      2.466378,
      48.840114
    ],
    [
      2.465663,
      48.840734
    ],
    [
      2.464555,
      48.841523
    ],
    [
      2.46384,
      48.841913
    ],
    [
      2.462733,
      48.842368
    ],
    [
      2.460839,
      48.842922
    ],
    [
      2.458064,
      48.843456
    ],
    [
      2.449392,
      48.844637
    ],
    [
      2.44641,
      48.844932
    ],
    [
      2.446526,
      48.84575
    ],
    [
      2.440766,
      48.845917
    ],
    [
      2.440695,
      48.845208
    ],
    [
      2.440874,
      48.84521
    ],
    [
      2.440809,
      48.844872
    ],
    [
      2.440616,
      48.844888
    ],
    [
      2.440512,
      48.844346
    ],
    [
      2.437941,
      48.844569
    ],
    [
      2.437192,
      48.840891
    ],
    [
      2.433679,
      48.841193
    ],
    [
      2.433638,
      48.840986
    ],
    [
      2.424761,
      48.84177
    ],
    [
      2.424816,
      48.8419
    ],
    [
      2.424567,
      48.841947
    ],
    [
      2.424062,
      48.842335
    ],
    [
      2.4237,
      48.842686
    ],
    [
      2.422758,
      48.844006
    ],
    [
      2.422455,
      48.844296
    ],
    [
      2.422106,
      48.844498
    ],
    [
      2.419982,
      48.843467
    ],
    [
      2.419873,
      48.843032
    ],
    [
      2.419424,
      48.842487
    ],
    [
      2.41957,
      48.841536
    ],
    [
      2.419858,
      48.841068
    ],
    [
      2.420384,
      48.840554
    ],
    [
      2.420856,
      48.839653
    ],
    [
      2.421223,
      48.838555
    ],
    [
      2.421638,
      48.83681
    ],
    [
      2.422178,
      48.835814
    ],
    [
      2.418869,
      48.834518
    ],
    [
      2.417116,
      48.833985
    ],
    [
      2.416111,
      48.833761
    ],
    [
      2.415122,
      48.833626
    ],
    [
      2.413906,
      48.833571
    ],
    [
      2.412794,
      48.833631
    ],
    [
      2.411228,
      48.833867
    ],
    [
      2.412276,
      48.834548
    ],
    [
      2.413513,
      48.837884
    ],
    [
      2.415693,
      48.845106
    ],
    [
      2.416437,
      48.84879
    ],
    [
      2.415267,
      48.855263
    ],
    [
      2.41386,
      48.864071
    ],
    [
      2.414004,
      48.868925
    ],
    [
      2.413646,
      48.872405
    ],
    [
      2.4125,
      48.876379
    ],
    [
      2.409293,
      48.880278
    ],
    [
      2.407139,
      48.880514
    ],
    [
      2.403717,
      48.881485
    ],
    [
      2.401469,
      48.882611
    ],
    [
      2.400092,
      48.883817
    ],
    [
      2.399217,
      48.885421
    ],
    [
      2.39919,
      48.888234
    ],
    [
      2.398624,
      48.891343
    ],
    [
      2.397762,
      48.894592
    ],
    [
      2.395527,
      48.898262
    ],
    [
      2.39069,
      48.900981
    ],
    [
      2.384429,
      48.902156
    ],
    [
      2.32588,
      48.900953
    ],
    [
      2.320358,
      48.900757
    ],
    [
      2.318532,
      48.899633
    ],
    [
      2.312342,
      48.89776
    ],
    [
      2.307555,
      48.89596
    ],
    [
      2.298561,
      48.891708
    ],
    [
      2.295047,
      48.889869
    ],
    [
      2.291504,
      48.889459
    ],
    [
      2.285661,
      48.886571
    ],
    [
      2.280993,
      48.882946
    ],
    [
      2.280898,
      48.882795
    ],
    [
      2.279964,
      48.878703
    ],
    [
      2.27749,
      48.877963
    ],
    [
      2.258888,
      48.880281
    ],
    [
      2.258407,
      48.880097
    ],
    [
      2.255411,
      48.874264
    ],
    [
      2.254815,
      48.874081
    ],
    [
      2.245623,
      48.876364
    ],
    [
      2.24336,
      48.874127
    ],
    [
      2.241048,
      48.872277
    ],
    [
      2.240463,
      48.871888
    ],
    [
      2.239672,
      48.871576
    ],
    [
      2.237373,
      48.871013
    ],
    [
      2.232076,
      48.869507
    ],
    [
      2.229475,
      48.866727
    ],
    [
      2.228652,
      48.865766
    ],
    [
      2.228244,
      48.865144
    ],
    [
      2.227292,
      48.862573
    ],
    [
      2.226405,
      48.860958
    ],
    [
      2.225001,
      48.85798
    ],
    [
      2.224466,
      48.856232
    ]
  ],
  "parks": [
    [
      [
        2.22521,
        48.854588
      ],
      [
        2.225365,
        48.853461
      ],
      [
        2.22556,
        48.853136
      ],
      [
        2.239314,
        48.850098
      ],
      [
        2.239944,
        48.849896
      ],
      [
        2.241595,
        48.84849
      ],
      [
        2.243691,
        48.848563
      ],
      [
        2.249158,
        48.848486
      ],
      [
        2.249148,
        48.84807
      ],
      [
        2.25281,
        48.848115
      ],
      [
        2.252874,
        48.848221
      ],
      [
        2.252247,
        48.849037
      ],
      [
        2.252069,
        48.84961
      ],
      [
        2.251305,
        48.849753
      ],
      [
        2.251633,
        48.851298
      ],
      [
        2.252783,
        48.851222
      ],
      [
        2.252804,
        48.849738
      ],
      [
        2.253113,
        48.849206
      ],
      [
        2.253615,
        48.848818
      ],
      [
        2.254256,
        48.848528
      ],
      [
        2.255766,
        48.848107
      ],
      [
        2.2572,
        48.848038
      ],
      [
        2.257197,
        48.848451
      ],
      [
        2.258062,
        48.848991
      ],
      [
        2.258483,
        48.849898
      ],
      [
        2.265564,
        48.860926
      ],
      [
        2.266268,
        48.86275
      ],
      [
        2.267184,
        48.862839
      ],
      [
        2.267529,
        48.862998
      ],
      [
        2.267599,
        48.86328
      ],
      [
        2.26718,
        48.863772
      ],
      [
        2.268371,
        48.864969
      ],
      [
        2.269956,
        48.867113
      ],
      [
        2.272149,
        48.869675
      ],
      [
        2.273326,
        48.870697
      ],
      [
        2.271342,
        48.869348
      ],
      [
        2.270778,
        48.869668
      ],
      [
        2.272429,
        48.871334
      ],
      [
        2.27333,
        48.871503
      ],
      [
        2.273703,
        48.871732
      ],
      [
        2.273859,
        48.872065
      ],
      [
        2.273575,
        48.872608
      ],
      [
        2.276472,
        48.87566
      ],
      [
        2.276931,
        48.875935
      ],
      [
        2.277116,
        48.875866
      ],
      [
        2.277275,
        48.875965
      ],
      [
        2.277285,
        48.876475
      ],
      [
        2.278002,
        48.876882
      ],
      [
        2.278572,
        48.877041
      ],
      [
        2.278656,
        48.876964
      ],
      [
        2.278937,
        48.877191
      ],
      [
        2.278808,
        48.877414
      ],
      [
        2.279131,
        48.877498
      ],
      [
        2.279141,
        48.877668
      ],
      [
        2.274335,
        48.878396
      ],
      [
        2.258954,
        48.880318
      ],
      [
        2.258296,
        48.880037
      ],
      [
        2.255384,
        48.874286
      ],
      [
        2.255495,
        48.874159
      ],
      [
        2.255012,
        48.873973
      ],
      [
        2.249935,
        48.875251
      ],
      [
        2.24972,
        48.875385
      ],
      [
        2.249042,
        48.875456
      ],
      [
        2.246128,
        48.876181
      ],
      [
        2.245557,
        48.87543
      ],
      [
        2.245389,
        48.875457
      ],
      [
        2.243612,
        48.873669
      ],
      [
        2.241026,
        48.871947
      ],
      [
        2.23928,
        48.871226
      ],
      [
        2.235863,
        48.87031
      ],
      [
        2.235095,
        48.870004
      ],
      [
        2.233169,
        48.868971
      ],
      [
        2.231702,
        48.867887
      ],
      [
        2.229643,
        48.86548
      ],
      [
        2.229284,
        48.864869
      ],
      [
        2.228299,
        48.862116
      ],
      [
        2.225842,
        48.857203
      ],
      [
        2.22541,
        48.855943
      ]
    ],
    [
      [
        2.399757,
        48.830666
      ],
      [
        2.401026,
        48.829852
      ],
      [
        2.401424,
        48.829873
      ],
      [
        2.402488,
        48.829647
      ],
      [
        2.404267,
        48.828904
      ],
      [
        2.408308,
        48.826091
      ],
      [
        2.409622,
        48.825419
      ],
      [
        2.410518,
        48.825116
      ],
      [
        2.412617,
        48.824816
      ],
      [
        2.416708,
        48.824794
      ],
      [
        2.419322,
        48.824212
      ],
      [
        2.420228,
        48.824121
      ],
      [
        2.424475,
        48.82427
      ],
      [
        2.425957,
        48.824229
      ],
      [
        2.427833,
        48.824011
      ],
      [
        2.429751,
        48.823565
      ],
      [
        2.430691,
        48.823234
      ],
      [
        2.430375,
        48.822883
      ],
      [
        2.43219,
        48.821618
      ],
      [
        2.432624,
        48.821902
      ],
      [
        2.432889,
        48.82169
      ],
      [
        2.432474,
        48.82142
      ],
      [
        2.434302,
        48.820156
      ],
      [
        2.43418,
        48.819281
      ],
      [
        2.435165,
        48.819649
      ],
      [
        2.436266,
        48.81956
      ],
      [
        2.436968,
        48.819363
      ],
      [
        2.43747,
        48.819105
      ],
      [
        2.43735,
        48.818219
      ],
      [
        2.439751,
        48.818366
      ],
      [
        2.442159,
        48.817976
      ],
      [
        2.447613,
        48.818027
      ],
      [
        2.449638,
        48.817962
      ],
      [
        2.450826,
        48.817809
      ],
      [
        2.453317,
        48.817294
      ],
      [
        2.455646,
        48.817259
      ],
      [
        2.458166,
        48.817093
      ],
      [
        2.458773,
        48.817234
      ],
      [
        2.458778,
        48.817343
      ],
      [
        2.462705,
        48.819279
      ],
      [
        2.462615,
        48.819434
      ],
      [
        2.462793,
        48.8196
      ],
      [
        2.462595,
        48.819758
      ],
      [
        2.462784,
        48.82025
      ],
      [
        2.464008,
        48.82257
      ],
      [
        2.464984,
        48.823921
      ],
      [
        2.465851,
        48.826135
      ],
      [
        2.464619,
        48.825464
      ],
      [
        2.463937,
        48.824843
      ],
      [
        2.463488,
        48.824134
      ],
      [
        2.462811,
        48.821958
      ],
      [
        2.461473,
        48.820623
      ],
      [
        2.46091,
        48.820964
      ],
      [
        2.461549,
        48.821426
      ],
      [
        2.462097,
        48.822077
      ],
      [
        2.462783,
        48.825732
      ],
      [
        2.462996,
        48.825669
      ],
      [
        2.463601,
        48.825775
      ],
      [
        2.464589,
        48.826153
      ],
      [
        2.464344,
        48.826912
      ],
      [
        2.464445,
        48.828729
      ],
      [
        2.464854,
        48.830359
      ],
      [
        2.465336,
        48.831449
      ],
      [
        2.466371,
        48.832562
      ],
      [
        2.468367,
        48.833601
      ],
      [
        2.468861,
        48.833968
      ],
      [
        2.469165,
        48.834358
      ],
      [
        2.46966,
        48.835599
      ],
      [
        2.469674,
        48.836263
      ],
      [
        2.469413,
        48.836923
      ],
      [
        2.467194,
        48.839057
      ],
      [
        2.46629,
        48.840127
      ],
      [
        2.464269,
        48.841645
      ],
      [
        2.46276,
        48.842304
      ],
      [
        2.461168,
        48.842829
      ],
      [
        2.459374,
        48.843176
      ],
      [
        2.449389,
        48.844621
      ],
      [
        2.44641,
        48.844932
      ],
      [
        2.446545,
        48.845744
      ],
      [
        2.440766,
        48.845917
      ],
      [
        2.440695,
        48.845208
      ],
      [
        2.440874,
        48.84521
      ],
      [
        2.440809,
        48.844872
      ],
      [
        2.440616,
        48.844888
      ],
      [
        2.440512,
        48.844346
      ],
      [
        2.437941,
        48.844569
      ],
      [
        2.437192,
        48.840891
      ],
      [
        2.433679,
        48.841193
      ],
      [
        2.433638,
        48.840986
      ],
      [
        2.424733,
        48.841763
      ],
      [
        2.424154,
        48.841967
      ],
      [
        2.423795,
        48.84223
      ],
      [
        2.422476,
        48.843904
      ],
      [
        2.422062,
        48.844243
      ],
      [
        2.421734,
        48.844311
      ],
      [
        2.420175,
        48.843568
      ],
      [
        2.419497,
        48.842589
      ],
      [
        2.419476,
        48.842307
      ],
      [
        2.419676,
        48.841325
      ],
      [
        2.420352,
        48.840579
      ],
      [
        2.420806,
        48.839711
      ],
      [
        2.421584,
        48.836885
      ],
      [
        2.42221,
        48.83576
      ],
      [
        2.420807,
        48.835164
      ],
      [
        2.416708,
        48.833846
      ],
      [
        2.414586,
        48.833562
      ],
      [
        2.413051,
        48.833569
      ],
      [
        2.410359,
        48.83399
      ],
      [
        2.40833,
        48.834759
      ],
      [
        2.408023,
        48.834673
      ],
      [
        2.407686,
        48.834308
      ],
      [
        2.405744,
        48.833267
      ],
      [
        2.40451,
        48.832903
      ],
      [
        2.404184,
        48.832434
      ],
      [
        2.402579,
        48.831361
      ],
      [
        2.401824,
        48.831095
      ],
      [
        2.399903,
        48.830811
      ]
    ]
  ],
  "seine": [
    [
      2.224,
      48.842
    ],
    [
      2.238,
      48.842
    ],
    [
      2.252,
      48.845
    ],
    [
      2.266,
      48.849
    ],
    [
      2.281,
      48.852
    ],
    [
      2.296,
      48.857
    ],
    [
      2.31,
      48.861
    ],
    [
      2.323,
      48.862
    ],
    [
      2.337,
      48.858
    ],
    [
      2.35,
      48.853
    ],
    [
      2.363,
      48.848
    ],
    [
      2.377,
      48.842
    ],
    [
      2.391,
      48.836
    ],
    [
      2.405,
      48.829
    ],
    [
      2.42,
      48.823
    ],
    [
      2.438,
      48.817
    ]
  ]
};

function mapPoint({ lat, lon }) {
  const { bounds, width, height } = PARIS_MAP;
  const pad = 18;
  const x = pad + ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * (width - pad * 2);
  const y = pad + ((bounds.maxLat - lat) / (bounds.maxLat - bounds.minLat)) * (height - pad * 2);
  return {
    x: Math.max(pad, Math.min(width - pad, x)),
    y: Math.max(pad, Math.min(height - pad, y)),
  };
}

function mapCurvePath(points, close = false) {
  const projected = points.map(([lon, lat]) => mapPoint({ lat, lon }));
  if (projected.length < 2) return "";
  const path = [`M ${projected[0].x.toFixed(1)} ${projected[0].y.toFixed(1)}`];
  const total = projected.length;
  for (let i = 0; i < total - (close ? 0 : 1); i += 1) {
    const current = projected[i];
    const next = projected[(i + 1) % total];
    const previous = projected[(i - 1 + total) % total];
    const afterNext = projected[(i + 2) % total];
    const c1 = {
      x: current.x + (next.x - previous.x) / 6,
      y: current.y + (next.y - previous.y) / 6,
    };
    const c2 = {
      x: next.x - (afterNext.x - current.x) / 6,
      y: next.y - (afterNext.y - current.y) / 6,
    };
    path.push(
      `C ${c1.x.toFixed(1)} ${c1.y.toFixed(1)}, ${c2.x.toFixed(1)} ${c2.y.toFixed(1)}, ${next.x.toFixed(1)} ${next.y.toFixed(1)}`,
    );
  }
  return `${path.join(" ")}${close ? " Z" : ""}`;
}

function mapMarker(stationId, label, className) {
  const place = station(stationId);
  if (!Number.isFinite(place.lat) || !Number.isFinite(place.lon)) return "";
  const { x, y } = mapPoint(place);
  return `
    <g class="map-marker ${className}" transform="translate(${x.toFixed(1)} ${y.toFixed(1)})">
      <circle r="6"></circle>
      <text y="-10">${escapeHtml(label)}</text>
    </g>
  `;
}

function orientationMapMarkup() {
  const puzzle = currentPuzzle();
  const current =
    state.currentStation && !sameStation(state.currentStation, puzzle.start) && !sameStation(state.currentStation, puzzle.end)
      ? mapMarker(state.currentStation, "Current", "current-marker")
      : "";
  return `
    <details class="map-toggle" open>
      <summary>Map</summary>
      <figure class="orientation-map" aria-label="Paris orientation map showing start and destination stations">
        <svg viewBox="0 0 ${PARIS_MAP.width} ${PARIS_MAP.height}" role="img" aria-labelledby="orientationMapTitle orientationMapDesc">
          <title id="orientationMapTitle">Paris orientation map</title>
          <desc id="orientationMapDesc">A simplified map of Paris with the Seine, the start station, and the destination station.</desc>
          <rect class="map-bg" width="${PARIS_MAP.width}" height="${PARIS_MAP.height}" rx="6"></rect>
          ${PARIS_MAP.parks.map((park) => `<path class="map-park" d="${mapCurvePath(park, true)}"></path>`).join("")}
          <path class="paris-outline" d="${mapCurvePath(PARIS_MAP.outline, true)}"></path>
          <path class="seine" d="${mapCurvePath(PARIS_MAP.seine)}"></path>
          ${mapMarker(puzzle.start, "Start", "start-marker")}
          ${mapMarker(puzzle.end, "End", "end-marker")}
          ${current}
        </svg>
      </figure>
    </details>
  `;
}

function toolbarMarkup({ backId = "", backLabel = "" } = {}) {
  const destinationLinesLabel = state.hintText ? "Hide destination's lines" : "Show destination's lines";
  const connectingLinesLabel = state.showConnectingLines ? "Hide connecting lines" : "Show connecting lines";
  return `
    <div class="toolbar">
      ${backId ? `<button class="action secondary" id="${backId}">${escapeHtml(backLabel)}</button>` : ""}
      <button class="action secondary" id="hintButton">${destinationLinesLabel}</button>
      <button class="action secondary" id="connectingLinesButton" type="button" aria-pressed="${state.showConnectingLines}">${connectingLinesLabel}</button>
      <button class="action secondary" id="resetRoute">Reset route</button>
      <button class="action secondary" id="giveUp">Give up</button>
    </div>
  `;
}

function bindPuzzleToolbar() {
  const hintButton = $("#hintButton");
  if (hintButton) {
    hintButton.addEventListener("click", () => {
      if (state.hintText) {
        state.hintText = "";
      } else {
        const lines = finalStationLineHint();
        state.hintText = lines ? `Final station is served by: ${lines}` : "No line hint is available for this station.";
      }
      if (state.stage === "direction") renderDirectionStep();
      else if (state.stage === "alight") renderAlightStep();
      else renderLineStep();
    });
  }
  const connectingLinesButton = $("#connectingLinesButton");
  if (connectingLinesButton) {
    connectingLinesButton.addEventListener("click", () => {
      state.showConnectingLines = !state.showConnectingLines;
      if (state.stage === "direction") renderDirectionStep();
      else if (state.stage === "alight") renderAlightStep();
      else renderLineStep();
    });
  }
  $("#resetRoute").addEventListener("click", startPuzzle);
  $("#giveUp").addEventListener("click", giveUp);
}

function boardShell(content) {
  const puzzle = currentPuzzle();
  $("#game").innerHTML = `
    <div class="board">
      <aside class="side">
        <div class="station-pair">
          <div class="station"><span>Départ</span><strong>${escapeHtml(station(puzzle.start).name)}</strong></div>
          <div class="station"><span>Arrivée</span><strong>${escapeHtml(station(puzzle.end).name)}</strong></div>
        </div>
        ${orientationMapMarkup()}
        <details class="route-summary" ${state.steps.length ? "open" : ""}>
          <summary>Your route</summary>
          <div class="route-list">${renderRouteList(state.steps, { showDirection: false, showDetail: false })}</div>
        </details>
      </aside>
      <section class="workspace">${content}</section>
    </div>
  `;
  bindResponsivePanels();
}

function bindResponsivePanels() {
  const isMobile = () => window.matchMedia("(max-width: 820px)").matches;
  document.querySelectorAll(".map-toggle, .route-summary").forEach((panel) => {
    const summary = panel.querySelector("summary");
    const keepDesktopOpen = (event) => {
      if (isMobile()) return;
      event.preventDefault();
      panel.open = true;
    };
    if (!isMobile()) {
      panel.open = true;
    }
    summary.addEventListener("click", keepDesktopOpen);
    summary.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") keepDesktopOpen(event);
    });
  });
}

function transferFallback(fromMode, toMode) {
  const defaults = state.data.metadata.transferFallbackSeconds;
  if (fromMode === toMode) return defaults.same_mode;
  const pair = new Set([fromMode, toMode]);
  if (pair.has("metro") && pair.has("rer")) return defaults.metro_rer;
  if (pair.has("metro") && pair.has("tram")) return defaults.metro_tram;
  if (pair.has("rer") && pair.has("tram")) return defaults.rer_tram;
  return defaults.fallback;
}

function waitSeconds(directionId, routeId, mode) {
  const byDirection = state.data.metadata.waitSecondsByDirection || {};
  const byRoute = state.data.metadata.waitSecondsByRoute || {};
  return byDirection[directionId] ?? byRoute[routeId] ?? state.data.metadata.waitSecondsByMode[mode] ?? 180;
}

function transferSeconds(fromStation, toStation, fromRouteId, toRouteId, fromMode, toMode) {
  const routePair = state.data.routeTransfers?.[fromStation]?.[toStation]?.[fromRouteId]?.[toRouteId];
  if (Number.isFinite(routePair)) return routePair;
  if (fromStation === toStation) return transferFallback(fromMode, toMode);
  const explicit = state.data.transfers[fromStation]?.[toStation];
  if (Number.isFinite(explicit)) return explicit;
  return null;
}

function lastRideStep() {
  for (let index = state.steps.length - 1; index >= 0; index -= 1) {
    if (stepType(state.steps[index]) === "ride") return state.steps[index];
  }
  return null;
}

function explicitWalkSeconds(fromStation, toStation, nextRouteId = null) {
  if (fromStation === toStation) return 0;
  const previous = lastRideStep();
  if (previous && nextRouteId) {
    const previousRoute = route(previous.routeId);
    const nextRoute = route(nextRouteId);
    const routeSpecific = transferSeconds(
      fromStation,
      toStation,
      previous.routeId,
      nextRouteId,
      previousRoute.mode,
      nextRoute.mode,
    );
    if (Number.isFinite(routeSpecific)) return routeSpecific;
  }
  const explicit = state.data.transfers[fromStation]?.[toStation];
  return Number.isFinite(explicit) ? explicit : null;
}

function walkOptions() {
  const currentCanonical = canonicalStationId(state.currentStation);
  const currentRouteIds = new Set(boardableRouteIds(state.currentStation));
  const byCanonical = new Map();
  Object.entries(state.data.transfers[state.currentStation] || {}).forEach(([stationId, walkSec]) => {
    if (!Number.isFinite(walkSec)) return;
    const canonicalId = canonicalStationId(stationId);
    if (canonicalId === currentCanonical) return;
    if (!boardableRouteIds(stationId).some((routeId) => !currentRouteIds.has(routeId))) return;
    const option = { stationId, walkSec };
    const existing = byCanonical.get(canonicalId);
    if (
      !existing ||
      option.walkSec < existing.walkSec ||
      (option.walkSec === existing.walkSec && compareText(station(option.stationId).name, station(existing.stationId).name) < 0)
    ) {
      byCanonical.set(canonicalId, option);
    }
  });
  return [...byCanonical.values()].sort(
    (a, b) => a.walkSec - b.walkSec || compareText(station(a.stationId).name, station(b.stationId).name),
  );
}

function boardableRouteIds(stationId) {
  const services = station(stationId).services || {};
  return Object.entries(services)
    .filter(([, directionIds]) =>
      directionIds.some((dirId) => {
        const dir = direction(dirId);
        const index = dir.stations.indexOf(stationId);
        return index >= 0 && index < dir.stations.length - 1;
      }),
    )
    .map(([routeId]) => routeId)
    .filter((routeId) => route(routeId))
    .sort((a, b) => {
      const ar = route(a);
      const br = route(b);
      return compareText(`${modeName(ar.mode)} ${ar.label}`, `${modeName(br.mode)} ${br.label}`);
    });
}

function walkLineBadges(stationId) {
  if (!state.showConnectingLines) return "";
  const badges = boardableRouteIds(stationId).map(lineBadge).join("");
  return badges ? `<span class="walk-lines" aria-label="Lines at ${escapeHtml(station(stationId).name)}">${badges}</span>` : "";
}

function boardingOptions() {
  const byRoute = new Map();
  const seen = new Set();
  const services = station(state.currentStation).services || {};
  Object.entries(services).forEach(([routeId, directionIds]) => {
    const usable = directionIds.filter((dirId) => {
      const dir = direction(dirId);
      const index = dir.stations.indexOf(state.currentStation);
      return index >= 0 && index < dir.stations.length - 1;
    });
    if (!usable.length) return;
    const key = `${state.currentStation}:${routeId}`;
    if (seen.has(key)) return;
    seen.add(key);
    if (!byRoute.has(routeId)) byRoute.set(routeId, { routeId, boards: [] });
    byRoute.get(routeId).boards.push({
      boardStation: state.currentStation,
      walkSec: 0,
      directionIds: usable,
    });
  });

  const options = [...byRoute.values()].map((option) => {
    option.boards.sort((a, b) => a.walkSec - b.walkSec || compareText(station(a.boardStation).name, station(b.boardStation).name));
    return option;
  });
  return options.sort((a, b) => {
    const ar = route(a.routeId);
    const br = route(b.routeId);
    const left = `${modeName(ar.mode)} ${ar.label}`;
    const right = `${modeName(br.mode)} ${br.label}`;
    return compareText(left, right);
  });
}

function renderLineStep(message = "") {
  state.stage = "line";
  const options = boardingOptions();
  const walks = walkOptions();
  boardShell(`
    <div class="step-title">
      <h2>Choose your next move</h2>
      <span>From ${escapeHtml(station(state.currentStation).name)}</span>
    </div>
    ${
      options.length
        ? `<section class="choice-section">
      <h3>Board here</h3>
      <div class="choice-grid">
        ${options
          .map((option, index) => {
            const r = route(option.routeId);
            const transferLabel = state.steps.length ? "Transfer here" : "Board here";
            return `
              <button class="choice line-choice" data-line-index="${index}">
                ${lineBadge(option.routeId)}
                <span><strong>${escapeHtml(modeName(r.mode))} ${escapeHtml(r.label)}</strong> <small>${transferLabel}</small></span>
              </button>
            `;
          })
          .join("")}
      </div>
    </section>`
        : ""
    }
    ${
      walks.length
        ? `<section class="choice-section">
      <h3>Walk first</h3>
      <div class="choice-grid">
        ${walks
          .map(
            (option, index) => `
              <button class="choice walk-choice" data-walk-index="${index}">
                <span>
                  <strong>Walk to ${escapeHtml(station(option.stationId).name)}</strong>
                  <small>${formatCompactTime(option.walkSec)} transfer</small>
                </span>
                ${walkLineBadges(option.stationId)}
              </button>
            `,
          )
          .join("")}
      </div>
    </section>`
        : ""
    }
    ${message ? `<p class="notice">${escapeHtml(message)}</p>` : ""}
    ${hintMarkup()}
    ${toolbarMarkup()}
  `);

  document.querySelectorAll("[data-line-index]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selected = options[Number(button.dataset.lineIndex)];
      renderDirectionStep();
    });
  });
  document.querySelectorAll("[data-walk-index]").forEach((button) => {
    button.addEventListener("click", () => {
      addWalkStep(walks[Number(button.dataset.walkIndex)].stationId);
    });
  });
  bindPuzzleToolbar();
}

function renderDirectionStep() {
  state.stage = "direction";
  const selected = state.selected;
  const r = route(selected.routeId);
  const directionOptions = [];
  const bestByLabel = new Map();
  selected.boards.forEach((board) => {
    board.directionIds.forEach((dirId) => {
      const label = direction(dirId).label;
      const candidate = { dirId, boardStation: board.boardStation, walkSec: board.walkSec, label };
      const existing = bestByLabel.get(label);
      if (
        !existing ||
        candidate.walkSec < existing.walkSec ||
        (candidate.walkSec === existing.walkSec && compareText(station(candidate.boardStation).name, station(existing.boardStation).name) < 0)
      ) {
        bestByLabel.set(label, candidate);
      }
    });
  });
  directionOptions.push(...bestByLabel.values());
  directionOptions.sort((a, b) => compareText(a.label, b.label));
  boardShell(`
    <div class="step-title">
      <h2>Choose direction</h2>
      <span>${escapeHtml(modeName(r.mode))} ${escapeHtml(r.label)}</span>
    </div>
    <div class="choice-grid">
      ${directionOptions
        .map((option, index) => {
          const dir = direction(option.dirId);
          return `
            <button class="choice" data-direction-index="${index}">
              <strong>${escapeHtml(dir.label)}</strong>
              <small>${
                option.boardStation === state.currentStation
                  ? state.steps.length
                    ? "Transfer here"
                    : "Board here"
                  : `After ${formatCompactTime(option.walkSec)} walk from ${escapeHtml(station(state.currentStation).name)}`
              }</small>
            </button>
          `;
        })
        .join("")}
    </div>
    ${hintMarkup()}
    ${toolbarMarkup({ backId: "backToLines", backLabel: "Back" })}
  `);
  document.querySelectorAll("[data-direction-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const option = directionOptions[Number(button.dataset.directionIndex)];
      state.selected.directionId = option.dirId;
      state.selected.boardStation = option.boardStation;
      renderAlightStep();
    });
  });
  $("#backToLines").addEventListener("click", () => renderLineStep());
  bindPuzzleToolbar();
}

function renderAlightStep() {
  state.stage = "alight";
  const selected = state.selected;
  const dir = direction(selected.directionId);
  const boardIndex = dir.stations.indexOf(selected.boardStation);
  const choices = dir.stations.slice(boardIndex + 1);
  const r = route(selected.routeId);
  const stopSignals = (stationId) => {
    const runSec = runtimeBetween(selected.directionId, selected.boardStation, stationId);
    const services = station(stationId).services || {};
    const transferBadges = state.showConnectingLines
      ? Object.keys(services)
          .filter((routeId) => routeId !== selected.routeId && route(routeId))
          .sort((a, b) => compareText(route(a).label, route(b).label))
          .map(lineBadge)
          .join("")
      : "";
    return `
      <span class="stop-meta">
        ${transferBadges ? `<span class="transfer-lines" aria-label="Transfer lines">${transferBadges}</span>` : ""}
        <small class="stop-time">${formatCompactTime(runSec)}</small>
      </span>
    `;
  };
  boardShell(`
    <div class="step-title">
      <h2>Choose your stop</h2>
      <span>${escapeHtml(r.label)} toward ${escapeHtml(dir.label)}</span>
    </div>
    <div class="stop-strip" aria-label="${escapeHtml(r.label)} stops toward ${escapeHtml(dir.label)}">
      ${choices
        .map(
          (stationId) => `
            <button class="choice stop-choice${sameStation(stationId, currentPuzzle().end) ? " destination-choice" : ""}" data-alight="${escapeHtml(stationId)}">
              <span class="stop-node" aria-hidden="true"></span>
              <span class="stop-main">
                <strong>${escapeHtml(station(stationId).name)}</strong>
                ${sameStation(stationId, currentPuzzle().end) ? "<small>Destination</small>" : ""}
              </span>
              ${stopSignals(stationId)}
            </button>
          `,
        )
        .join("")}
    </div>
    ${hintMarkup()}
    ${toolbarMarkup({ backId: "backToDirections", backLabel: "Back" })}
  `);
  document.querySelectorAll("[data-alight]").forEach((button) => {
    button.addEventListener("click", () => addLeg(button.dataset.alight));
  });
  $("#backToDirections").addEventListener("click", renderDirectionStep);
  bindPuzzleToolbar();
}

function runtimeBetween(dirId, fromStation, toStation) {
  const dir = direction(dirId);
  const fromIndex = dir.stations.indexOf(fromStation);
  const toIndex = dir.stations.indexOf(toStation);
  if (fromIndex < 0 || toIndex <= fromIndex) return null;
  return dir.runtimes.slice(fromIndex, toIndex).reduce((sum, sec) => sum + sec, 0);
}

function legTiming(selected, toStation, rideSec) {
  const r = route(selected.routeId);
  const waitSec = waitSeconds(selected.directionId, selected.routeId, r.mode);
  let transferSec = 0;
  const previous = lastRideStep();
  if (previous && selected.boardStation === state.currentStation) {
    const previousMode = route(previous.routeId).mode;
    const transfer = transferSeconds(
      state.currentStation,
      selected.boardStation,
      previous.routeId,
      selected.routeId,
      previousMode,
      r.mode,
    );
    if (!Number.isFinite(transfer)) return null;
    transferSec = transfer;
  }
  return {
    rideSec,
    waitSec,
    transferSec,
    elapsedSec: rideSec + waitSec + transferSec,
  };
}

function addWalkStep(toStation, nextRouteId = null, { renderAfter = true } = {}) {
  const fromStation = state.currentStation;
  const transferSec = explicitWalkSeconds(fromStation, toStation, nextRouteId);
  if (!Number.isFinite(transferSec) || transferSec <= 0) {
    renderLineStep("There is no walking transfer link between those stations in the feed.");
    return false;
  }
  const step = {
    type: "walk",
    from: fromStation,
    to: toStation,
    rideSec: 0,
    waitSec: 0,
    transferSec,
    elapsedSec: transferSec,
  };
  state.steps.push(step);
  state.totalSec += transferSec;
  state.currentStation = toStation;
  state.selected = {};
  if (!renderAfter) return true;
  if (sameStation(toStation, currentPuzzle().end)) {
    renderResult();
  } else {
    renderLineStep();
  }
  return true;
}

function addLeg(toStation) {
  const selected = state.selected;
  const runSec = runtimeBetween(selected.directionId, selected.boardStation, toStation);
  if (!Number.isFinite(runSec)) {
    renderLineStep("That leg is not connected in the selected direction.");
    return;
  }

  const timing = legTiming(selected, toStation, runSec);
  if (!timing) {
    renderLineStep("There is no transfer link between those stations in the feed.");
    return;
  }

  if (selected.boardStation !== state.currentStation) {
    const walked = addWalkStep(selected.boardStation, selected.routeId, { renderAfter: false });
    if (!walked) return;
  }

  const leg = {
    type: "ride",
    routeId: selected.routeId,
    directionId: selected.directionId,
    from: selected.boardStation,
    to: toStation,
    ...timing,
  };
  state.steps.push(leg);
  state.totalSec += timing.elapsedSec;
  state.currentStation = toStation;
  state.selected = {};

  if (sameStation(toStation, currentPuzzle().end)) {
    renderResult();
  } else {
    renderLineStep();
  }
}

function routeSignature(steps) {
  return steps
    .map((step) =>
      stepType(step) === "walk"
        ? `walk:${step.from}:${step.to}`
        : `ride:${step.routeId}:${step.directionId}:${step.from}:${step.to}`,
    )
    .join("|");
}

function scoreRoute(puzzle, signature, totalSec) {
  const optimal = puzzle.optimalRoute;
  const exact = signature === optimal.signature;
  if (exact) return { score: 100, label: "Perfect" };

  const deltaSec = Math.max(0, totalSec - optimal.totalSec);
  if (deltaSec <= 30) return { score: 100, label: "Equally fast route" };

  const deltaMin = deltaSec / 60;
  const slowPct = (deltaSec / optimal.totalSec) * 100;
  const rawScore = 100 - deltaMin * 3 - slowPct * 0.6;
  const score = Math.max(10, Math.min(99, Math.round(rawScore)));

  if (score >= 90) return { score, label: "Excellent route" };
  if (score >= 80) return { score, label: "Very close route" };
  if (score >= 65) return { score, label: "Good route" };
  if (score >= 45) return { score, label: "Valid route" };
  return { score, label: "Slow route" };
}

function routeTimingTotals(steps, totalSec = null) {
  const totals = steps.reduce(
    (sum, step) => ({
      rideSec: sum.rideSec + (Number.isFinite(step.rideSec) ? step.rideSec : 0),
      waitSec: sum.waitSec + (Number.isFinite(step.waitSec) ? step.waitSec : 0),
      transferSec: sum.transferSec + (Number.isFinite(step.transferSec) ? step.transferSec : 0),
      totalSec: sum.totalSec + (Number.isFinite(step.elapsedSec) ? step.elapsedSec : 0),
    }),
    { rideSec: 0, waitSec: 0, transferSec: 0, totalSec: 0 },
  );
  if (Number.isFinite(totalSec)) totals.totalSec = totalSec;
  return totals;
}

function routeBreakdownMarkup(totals) {
  return `
    <div class="time-breakdown">
      <span><small>Ride</small><strong>${formatTime(totals.rideSec)}</strong></span>
      <span><small>Wait</small><strong>${formatTime(totals.waitSec)}</strong></span>
      <span><small>Transfers</small><strong>${formatTime(totals.transferSec)}</strong></span>
      <span><small>Total</small><strong>${formatTime(totals.totalSec)}</strong></span>
    </div>
  `;
}

function routePanel(title, steps, totalSec, timing = null) {
  const totals = timing || routeTimingTotals(steps, totalSec);
  return `
    <div class="route-panel">
      <h3>${escapeHtml(title)} <small>${formatTime(totalSec)}</small></h3>
      ${routeBreakdownMarkup(totals)}
      <div class="route-list">${renderRouteList(steps, { showDirection: false })}</div>
    </div>
  `;
}

function precomputedSteps(routeInfo) {
  return (routeInfo.steps || routeInfo.legs).map((step) => ({
    type: step.type || "ride",
    routeId: step.routeId,
    directionId: step.directionId,
    from: step.from,
    to: step.to,
    rideSec: step.rideSec,
    waitSec: step.waitSec,
    transferSec: step.transferSec,
    elapsedSec: step.elapsedSec,
  }));
}

function renderResult() {
  const puzzle = currentPuzzle();
  const signature = routeSignature(state.steps);
  const scored = scoreRoute(puzzle, signature, state.totalSec);
  const optimal = puzzle.optimalRoute;
  const optimalSteps = precomputedSteps(optimal);
  const deltaSec = Math.max(0, state.totalSec - optimal.totalSec);
  const slowPct = optimal.totalSec ? Math.round((deltaSec / optimal.totalSec) * 100) : 0;
  const transferCount = Math.max(0, state.steps.filter((step) => stepType(step) === "ride").length - 1);
  state.results[state.puzzleIndex] = {
    score: scored.score,
    totalSec: state.totalSec,
    optimalSec: optimal.totalSec,
    label: scored.label,
  };

  boardShell(`
    <div class="result">
      <div class="step-title">
        <h2>${scored.label}</h2>
        <span>Puzzle ${state.puzzleIndex + 1}</span>
      </div>
      <div class="scoreboard">
        <div class="scorebox"><span>Score</span><strong>${scored.score}</strong></div>
        <div class="scorebox"><span>Your time</span><strong>${formatTime(state.totalSec)}</strong></div>
        <div class="scorebox"><span>Transfers</span><strong>${transferCount}</strong></div>
      </div>
      <p class="result-note">${escapeHtml(formatSignedTime(deltaSec))}${slowPct ? ` (${slowPct}% slower)` : ""}</p>
      <div class="comparison">
        ${routePanel("Your route", state.steps, state.totalSec)}
        ${routePanel("Fastest route", optimalSteps, optimal.totalSec, optimal)}
      </div>
      <div class="toolbar">
        <button class="action" id="nextPuzzle">${state.puzzleIndex + 1 === puzzleCount() ? "Summary" : "Next puzzle"}</button>
      </div>
    </div>
  `);
  $("#nextPuzzle").addEventListener("click", goNextPuzzle);
}

function giveUp() {
  const puzzle = currentPuzzle();
  const optimal = puzzle.optimalRoute;
  const optimalSteps = precomputedSteps(optimal);
  state.results[state.puzzleIndex] = {
    score: 0,
    totalSec: null,
    optimalSec: optimal.totalSec,
    label: "Gave up",
  };

  boardShell(`
    <div class="result">
      <div class="step-title">
        <h2>Gave up</h2>
        <span>Puzzle ${state.puzzleIndex + 1}</span>
      </div>
      <div class="scoreboard">
        <div class="scorebox"><span>Score</span><strong>0</strong></div>
        <div class="scorebox"><span>Fastest time</span><strong>${formatTime(optimal.totalSec)}</strong></div>
        <div class="scorebox"><span>Transfers</span><strong>${optimal.transferCount}</strong></div>
      </div>
      ${routePanel("Fastest route", optimalSteps, optimal.totalSec, optimal)}
      <div class="toolbar">
        <button class="action" id="nextPuzzle">${state.puzzleIndex + 1 === puzzleCount() ? "Summary" : "Next puzzle"}</button>
      </div>
    </div>
  `);
  $("#nextPuzzle").addEventListener("click", goNextPuzzle);
}

function goNextPuzzle() {
  if (state.puzzleIndex + 1 === puzzleCount()) {
    renderSummary();
  } else {
    state.puzzleIndex += 1;
    startPuzzle();
  }
}

function shareScores() {
  return state.results.map((result) => result.score).join(" ");
}

function shareText(total) {
  return `Métro Express ${state.dailyDate || parisDateString()}\n${total}/${puzzleCount() * 100}\nScores: ${shareScores()}`;
}

async function copyText(text) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(text);
      return;
    } catch {
      // Fall through to the textarea fallback for local/file contexts.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "fixed";
  textarea.style.top = "-1000px";
  document.body.appendChild(textarea);
  textarea.select();
  document.execCommand("copy");
  textarea.remove();
}

function renderSummary() {
  state.stage = "summary";
  setRoundLabel();
  const total = state.results.reduce((sum, result) => sum + result.score, 0);
  const share = shareText(total);
  $("#game").innerHTML = `
    <section class="summary">
      <h2>Terminus</h2>
      <div class="scoreboard">
        <div class="scorebox"><span>Total score</span><strong>${total}</strong></div>
        <div class="scorebox"><span>Puzzles</span><strong>${puzzleCount()}</strong></div>
        <div class="scorebox"><span>Max score</span><strong>${puzzleCount() * 100}</strong></div>
      </div>
      <div class="share">${escapeHtml(share)}</div>
      <div class="toolbar">
        <button class="action" id="copyResults">Copy results</button>
        <button class="action secondary" id="restartDay">Replay today</button>
        <span class="copy-status" id="copyStatus" role="status" aria-live="polite"></span>
      </div>
      <p class="source-note">Route data: Île-de-France Mobilités / ITO World GTFS export.</p>
    </section>
  `;
  $("#copyResults").addEventListener("click", async () => {
    await copyText(share);
    $("#copyStatus").textContent = "Copied";
  });
  $("#restartDay").addEventListener("click", () => {
    restartDay();
  });
}

function restartDay() {
  state.puzzleIndex = 0;
  state.results = [];
  startPuzzle();
}

function startPuzzle() {
  state.stage = "line";
  state.currentStation = currentPuzzle().start;
  state.steps = [];
  state.totalSec = 0;
  state.selected = {};
  state.hintText = "";
  setRoundLabel();
  renderLineStep();
}

async function fetchJson(url) {
  try {
    const response = await fetch(url);
    if (!response.ok) return null;
    return await response.json();
  } catch {
    return null;
  }
}

function playablePuzzles(data, limit = null) {
  const puzzles = (data?.puzzles || []).filter(
    (puzzle) => puzzle.playable !== false && Number.isFinite(puzzle.optimalRoute?.totalSec),
  );
  return limit ? puzzles.slice(0, limit) : puzzles;
}

function nearestDailyDate(dates, target) {
  if (!dates?.length) return null;
  if (dates.includes(target)) return target;
  const targetMs = Date.parse(`${target}T00:00:00Z`);
  return dates
    .slice()
    .sort((left, right) => {
      const leftDelta = Math.abs(Date.parse(`${left}T00:00:00Z`) - targetMs);
      const rightDelta = Math.abs(Date.parse(`${right}T00:00:00Z`) - targetMs);
      return leftDelta - rightDelta || left.localeCompare(right);
    })[0];
}

async function loadPuzzleSet() {
  const today = parisDateString();
  const index = await fetchJson(DAILY_INDEX_URL);
  const dailyDate = nearestDailyDate(index?.dates, today) || today;
  const dailyData = await fetchJson(`${DAILY_BASE_URL}/${dailyDate}.json`);
  const dailyPuzzles = playablePuzzles(dailyData);
  if (dailyPuzzles.length) {
    return {
      date: dailyData?.metadata?.date || dailyDate,
      kind: dailyData?.metadata?.kind || "daily-puzzles",
      puzzles: dailyPuzzles,
    };
  }

  const exampleData = await fetchJson(EXAMPLE_URL);
  const examplePuzzles = playablePuzzles(exampleData, FALLBACK_DAILY_COUNT);
  if (examplePuzzles.length) {
    return {
      date: today,
      kind: exampleData?.metadata?.kind || "example-dev-puzzles",
      puzzles: examplePuzzles,
    };
  }
  throw new Error("Puzzle load failed");
}

async function init() {
  $("#game").innerHTML = "";
  $("#homeButton").addEventListener("click", () => {
    if (state.data) restartDay();
  });
  state.data = await fetchJson(NETWORK_URL);
  if (!state.data) throw new Error("Network load failed");
  const puzzleSet = await loadPuzzleSet();
  state.daily = puzzleSet.puzzles;
  state.dailyDate = puzzleSet.date;
  state.dailyKind = puzzleSet.kind;
  startPuzzle();
}

init().catch(() => {
  $("#game").innerHTML = `<section class="summary"><h2>Could not load</h2><p>Could not load today’s puzzle data. Try refreshing the page.</p></section>`;
});
