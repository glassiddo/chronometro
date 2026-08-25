const SUPPORTED_CITY_IDS = new Set(["paris", "london"]);
const requestedCityId = new URLSearchParams(window.location.search).get("city");
const CITY_ID = SUPPORTED_CITY_IDS.has(requestedCityId) ? requestedCityId : "paris";
const CITY_DATA_URL = `./data/${CITY_ID}`;
const NETWORK_URL = `${CITY_DATA_URL}/network.json`;
const DAILY_INDEX_URL = `${CITY_DATA_URL}/daily/index.json`;
const DAILY_BASE_URL = `${CITY_DATA_URL}/daily`;
const EXAMPLE_URL = `${CITY_DATA_URL}/example/puzzles.json`;
const FALLBACK_DAILY_COUNT = 5;
const STATION_EQUIVALENCE_TRANSFER_SECONDS = 120;
const DATA_REVISION = "20260825-london-preview-2";

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
};

const $ = (selector) => document.querySelector(selector);

function station(id) {
  return state.data.stations[id] || { id, name: id };
}

function stationDisplayName(stationId) {
  const name = station(stationId).name;
  if (CITY_ID !== "london") return name;
  return name
    .replace(/\s*\([^)]*Line[^)]*\)/gi, "")
    .replace(/-Underground$/i, "")
    .replace(/^London (?=(?:Paddington|Liverpool Street)$)/i, "")
    .trim();
}

function canonicalStationId(stationId) {
  return state.data.canonicalStationIds?.[stationId] || stationId;
}

function sameStation(leftId, rightId) {
  return canonicalStationId(leftId) === canonicalStationId(rightId);
}

function sameLondonHub(leftId, rightId) {
  if (CITY_ID !== "london" || !leftId || !rightId) return false;
  return (state.data?.stationEquivalents || []).some((group) => group.includes(leftId) && group.includes(rightId));
}

function samePuzzleStation(leftId, rightId) {
  return sameStation(leftId, rightId) || sameLondonHub(leftId, rightId);
}

function isFreeStartHubBoarding(boardStationId) {
  return state.steps.length === 0 && samePuzzleStation(state.currentStation, currentPuzzle().start) && samePuzzleStation(boardStationId, currentPuzzle().start);
}

function route(id) {
  return state.data.routes[id];
}

function direction(id) {
  return state.data.directions[id];
}

function modeName(mode) {
  return state.data?.metadata?.modes?.[mode]?.label || mode;
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

function formatPanelTime(sec) {
  const min = Math.floor(sec / 60);
  const rem = Math.round(sec % 60);
  if (!min) return `${rem}s`;
  return rem ? `${min}m ${rem}s` : `${min}m`;
}

function formatCompactTime(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return "";
  if (sec < 60) return `${Math.round(sec)}s`;
  const min = Math.round(sec / 60);
  return `${min} ${min === 1 ? "min" : "mins"}`;
}

function formatLegBreakdown(leg) {
  const totalSec =
    Number.isFinite(leg.elapsedSec)
      ? leg.elapsedSec
      : [leg.transferSec, leg.waitSec, leg.rideSec].reduce((sum, sec) => sum + (Number.isFinite(sec) ? sec : 0), 0);
  if (stepType(leg) === "walk") return `${formatPanelTime(totalSec)} walk`;

  const waitTransferSec = (Number.isFinite(leg.transferSec) ? leg.transferSec : 0) + (Number.isFinite(leg.waitSec) ? leg.waitSec : 0);
  const parts = [
    Number.isFinite(totalSec) && totalSec > 0 ? formatPanelTime(totalSec) : "",
    Number.isFinite(leg.rideSec) && leg.rideSec > 0 ? `${formatPanelTime(leg.rideSec)} ride` : "",
    waitTransferSec > 0 ? `${formatPanelTime(waitTransferSec)} wait+transfer` : "",
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : "";
}

function stepType(step) {
  return step.type || "ride";
}

function cityDateString(date = new Date()) {
  const parts = new Intl.DateTimeFormat("en-CA", {
    timeZone: state.data?.metadata?.city?.timezone || "UTC",
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
  return `<span class="line-badge" style="background:${r.color};color:${r.textColor}">${escapeHtml(routeDisplayName(r))}</span>`;
}

function lineChoiceMarker(routeId) {
  const r = route(routeId);
  if (CITY_ID !== "london") return lineBadge(routeId);
  return `<span class="line-swatch" style="background:${r.color}" aria-hidden="true"></span>`;
}

function routeDisplayName(r) {
  const label = r?.label || "";
  if (CITY_ID !== "london") return label;
  if (label === "Hammersmith & City") return "H&C";
  return label.replace(/\s+line$/i, "");
}

function routeChoiceLabel(r) {
  return CITY_ID === "london" ? routeDisplayName(r) : `${modeName(r.mode)} ${r.label}`;
}

function directionGroupLabel(label) {
  if (CITY_ID === "london" && /^Heathrow Terminal [45]$/i.test(label)) return "Heathrow";
  return CITY_ID === "london" ? label.replace(/\s+\((?:Circle|H\s*&\s*C) Line\)$/i, "") : label;
}

function directionOptionKey(candidate) {
  if (CITY_ID !== "london") return `label:${candidate.label}`;
  const dir = direction(candidate.dirId);
  const boardIndex = dir.stations.indexOf(candidate.boardStation);
  const nextStationId = dir.stations[boardIndex + 1];
  return nextStationId ? `next:${stationDisplayName(nextStationId)}` : `label:${candidate.label}`;
}

function directionOptionLabel(candidates) {
  if (CITY_ID !== "london" || candidates.length === 1) return candidates[0].label;
  const dir = direction(candidates[0].dirId);
  const boardIndex = dir.stations.indexOf(candidates[0].boardStation);
  const nextStationId = dir.stations[boardIndex + 1];
  return nextStationId ? stationDisplayName(nextStationId) : candidates[0].label;
}

function escapeHtml(value) {
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function setRoundLabel() {
  $("#todayLabel").textContent = state.dailyDate || cityDateString();
  $("#roundLabel").textContent =
    state.stage === "summary" ? "Done" : `${state.puzzleIndex + 1} / ${puzzleCount()}`;
}

function currentPuzzle() {
  return state.daily[state.puzzleIndex];
}

function renderRouteList(steps, { showDirection = true, showDetail = true, showElapsed = true, compactElapsed = false } = {}) {
  if (!steps.length) return `<p class="muted">No steps yet.</p>`;
  return steps
    .map(
      (step) => {
        const detail = showDetail ? formatLegBreakdown(step) : "";
        const elapsedText = compactElapsed ? formatPanelTime(step.elapsedSec) : formatTime(step.elapsedSec);
        const elapsed =
          showElapsed && Number.isFinite(step.elapsedSec) && step.elapsedSec > 0
            ? `<small class="leg-elapsed">${elapsedText}</small>`
            : "";
        if (stepType(step) === "walk") {
          return `
        <div class="leg-chip walk-chip">
          <span class="walk-badge">Walk</span>
          <p>
            <strong>Walk to ${escapeHtml(stationDisplayName(step.to))}</strong>
            ${detail ? `<small class="leg-detail">${escapeHtml(detail)}</small>` : ""}
          </p>
          ${elapsed}
        </div>
      `;
        }
        return `
        <div class="leg-chip">
          ${lineBadge(step.routeId)}
          <p>
            <strong>${escapeHtml(stationDisplayName(step.from))} → ${escapeHtml(stationDisplayName(step.to))}</strong>
            ${showDirection ? `<small>Direction ${escapeHtml(directionGroupLabel(direction(step.directionId).label))}</small>` : ""}
            ${detail ? `<small class="leg-detail">${escapeHtml(detail)}</small>` : ""}
          </p>
          ${elapsed}
        </div>
      `;
      },
    )
    .join("");
}

function stationLineIds(stationId) {
  const lines = new Map();
  Object.values(state.data.directions).forEach((dir) => {
    if (!dir.stations.some((candidateId) => sameStation(candidateId, stationId))) return;
    const r = route(dir.routeId);
    if (r) lines.set(dir.routeId, `${modeName(r.mode)} ${r.label}`);
  });
  return [...lines.keys()].sort((a, b) => {
    const ar = route(a);
    const br = route(b);
    return compareText(`${modeName(ar.mode)} ${ar.label}`, `${modeName(br.mode)} ${br.label}`);
  });
}

function stationInterchangeRouteIds(stationId) {
  if (CITY_ID !== "london") return [];
  const ownRouteIds = new Set(stationLineIds(stationId));
  const connectedStationIds = new Set(Object.keys(state.data.transfers?.[stationId] || {}));
  Object.entries(state.data.transfers || {}).forEach(([connectedId, destinations]) => {
    if (Number.isFinite(destinations?.[stationId])) connectedStationIds.add(connectedId);
  });
  const connectedRouteIds = new Set();
  connectedStationIds.forEach((connectedId) => {
    stationLineIds(connectedId).forEach((routeId) => {
      if (!ownRouteIds.has(routeId)) connectedRouteIds.add(routeId);
    });
  });
  return [...connectedRouteIds].sort((a, b) => compareText(routeDisplayName(route(a)), routeDisplayName(route(b))));
}

function stationLineBadges(stationId) {
  const badges = stationLineIds(stationId).map(lineBadge).join("");
  if (CITY_ID !== "london") return badges ? `<span class="station-lines" aria-label="Connecting lines">${badges}</span>` : "";
  const allRouteIds = new Set([...stationLineIds(stationId), ...stationInterchangeRouteIds(stationId)]);
  const sortedRouteIds = [...allRouteIds].sort((a, b) => compareText(routeDisplayName(route(a)), routeDisplayName(route(b))));
  return sortedRouteIds.length
    ? `<span class="station-lines" aria-label="Lines at this station hub">${sortedRouteIds.map(lineBadge).join("")}</span>`
    : "";
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
  "waterway": [
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

let CITY_MAP = PARIS_MAP;

function configureCityMap() {
  if (CITY_ID === "paris") {
    CITY_MAP = PARIS_MAP;
    return;
  }
  CITY_MAP = {
    width: 320,
    height: 220,
    bounds: { minLat: 51.35, maxLat: 51.65, minLon: -0.52, maxLon: 0.25 },
    outline: [],
    parks: [],
    airport: null,
    waterway: [[-0.52,51.462],[-0.45,51.470],[-0.38,51.482],[-0.31,51.475],[-0.25,51.470],[-0.20,51.480],[-0.16,51.494],[-0.12,51.503],[-0.08,51.505],[-0.04,51.493],[0.01,51.486],[0.07,51.491],[0.14,51.501],[0.25,51.500]],
  };
}

function fitLondonMapToPuzzle() {
  if (CITY_ID !== "london") {
    CITY_MAP.viewBounds = CITY_MAP.bounds;
    return;
  }
  const puzzle = currentPuzzle();
  const start = station(puzzle.start);
  const end = station(puzzle.end);
  const points = [start, end];
  const lats = points.map((point) => point.lat).filter(Number.isFinite);
  const lons = points.map((point) => point.lon).filter(Number.isFinite);
  if (!lats.length || !lons.length) {
    CITY_MAP.viewBounds = CITY_MAP.bounds;
    return;
  }
  const centralBounds = { minLat: 51.47, maxLat: 51.56, minLon: -0.25, maxLon: 0.12 };
  const inside = (point, bounds) =>
    point.lat >= bounds.minLat && point.lat <= bounds.maxLat && point.lon >= bounds.minLon && point.lon <= bounds.maxLon;
  if (inside(start, centralBounds) && inside(end, centralBounds)) {
    CITY_MAP.viewBounds = centralBounds;
    return;
  }
  const rawLatSpan = Math.max(...lats) - Math.min(...lats);
  const rawLonSpan = Math.max(...lons) - Math.min(...lons);
  if (rawLatSpan > 0.13 || rawLonSpan > 0.3) {
    CITY_MAP.viewBounds = CITY_MAP.bounds;
    return;
  }
  const latMid = (Math.min(...lats) + Math.max(...lats)) / 2;
  const lonMid = (Math.min(...lons) + Math.max(...lons)) / 2;
  const latSpan = Math.max(0.09, rawLatSpan * 1.8);
  const lonSpan = Math.max(0.18, rawLonSpan * 1.8);
  const clampRange = (mid, span, minimum, maximum) => {
    let low = mid - span / 2;
    let high = mid + span / 2;
    if (low < minimum) { high += minimum - low; low = minimum; }
    if (high > maximum) { low -= high - maximum; high = maximum; }
    return [Math.max(minimum, low), Math.min(maximum, high)];
  };
  const [minLat, maxLat] = clampRange(latMid, latSpan, CITY_MAP.bounds.minLat, CITY_MAP.bounds.maxLat);
  const [minLon, maxLon] = clampRange(lonMid, lonSpan, CITY_MAP.bounds.minLon, CITY_MAP.bounds.maxLon);
  CITY_MAP.viewBounds = { minLat, maxLat, minLon, maxLon };
}

function mapPoint({ lat, lon }, clamp = true) {
  const bounds = CITY_MAP.viewBounds || CITY_MAP.bounds;
  const { width, height } = CITY_MAP;
  const pad = 12;
  const x = pad + ((lon - bounds.minLon) / (bounds.maxLon - bounds.minLon)) * (width - pad * 2);
  const y = pad + ((bounds.maxLat - lat) / (bounds.maxLat - bounds.minLat)) * (height - pad * 2);
  if (!clamp) return { x, y };
  return {
    x: Math.max(pad, Math.min(width - pad, x)),
    y: Math.max(pad, Math.min(height - pad, y)),
  };
}

function mapCurvePath(points, close = false) {
  const projected = points.map(([lon, lat]) => mapPoint({ lat, lon }, false));
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

function networkContextMapMarkup() {
  const seen = new Set();
  const segments = [];
  Object.values(state.data.directions).forEach((dir) => {
    if (CITY_ID === "paris" && route(dir.routeId)?.mode !== "metro") return;
    dir.stations.slice(0, -1).forEach((leftId, index) => {
      const rightId = dir.stations[index + 1];
      const key = [leftId, rightId].sort().join(":");
      if (seen.has(key)) return;
      const left = station(leftId);
      const right = station(rightId);
      if (![left.lat, left.lon, right.lat, right.lon].every(Number.isFinite)) return;
      seen.add(key);
      const from = mapPoint(left, false);
      const to = mapPoint(right, false);
      segments.push(`M ${from.x.toFixed(1)} ${from.y.toFixed(1)} L ${to.x.toFixed(1)} ${to.y.toFixed(1)}`);
    });
  });
  return `<path class="map-network-context map-network-context--${CITY_ID}" d="${segments.join(" ")}"></path>`;
}

function orientationMapMarkup() {
  const puzzle = currentPuzzle();
  fitLondonMapToPuzzle();
  const current =
    state.currentStation && !samePuzzleStation(state.currentStation, puzzle.start) && !samePuzzleStation(state.currentStation, puzzle.end)
      ? mapMarker(state.currentStation, "Current", "current-marker")
      : "";
  return `
    <figure class="orientation-map" aria-label="${escapeHtml(state.data.metadata.city.name)} orientation map showing start and destination stations">
      <svg viewBox="0 0 ${CITY_MAP.width} ${CITY_MAP.height}" role="img" aria-labelledby="orientationMapTitle orientationMapDesc">
        <title id="orientationMapTitle">${escapeHtml(state.data.metadata.city.name)} orientation map</title>
        <desc id="orientationMapDesc">A simplified city map with the start station and destination station.</desc>
        <rect class="map-bg" width="${CITY_MAP.width}" height="${CITY_MAP.height}" rx="6"></rect>
        ${CITY_MAP.parks.map((park) => `<path class="map-park" d="${mapCurvePath(park, true)}"></path>`).join("")}
        ${CITY_MAP.airport ? `<path class="map-airport" d="${mapCurvePath(CITY_MAP.airport, true)}"></path>` : ""}
        ${CITY_MAP.outline.length ? `<path class="city-outline" d="${mapCurvePath(CITY_MAP.outline, true)}"></path>` : ""}
        ${networkContextMapMarkup()}
        <path class="waterway" d="${mapCurvePath(CITY_MAP.waterway)}"></path>
        ${mapMarker(puzzle.start, "Start", "start-marker")}
        ${mapMarker(puzzle.end, "End", "end-marker")}
        ${current}
      </svg>
    </figure>
  `;
}

function toolbarMarkup({ backId = "", backLabel = "" } = {}) {
  return `
    <div class="toolbar">
      ${backId ? `<button class="action secondary" id="${backId}">${escapeHtml(backLabel)}</button>` : ""}
      <button class="action secondary" id="resetRoute">Reset route</button>
      <button class="action secondary" id="giveUp">Give up</button>
    </div>
  `;
}

function bindPuzzleToolbar() {
  $("#resetRoute").addEventListener("click", startPuzzle);
  $("#giveUp").addEventListener("click", giveUp);
}

function boardShell(content, { showRouteSummary = true } = {}) {
  const puzzle = currentPuzzle();
  const hasRouteSummary = showRouteSummary && state.steps.length > 0;
  const boardClass = showRouteSummary ? "board" : "board board--result";
  $("#game").innerHTML = `
    <div class="${boardClass}">
      <aside class="side">
        <div class="station-pair">
          <div class="station">
            <span>Depart</span>
            <strong>${escapeHtml(stationDisplayName(puzzle.start))}</strong>
            ${stationLineBadges(puzzle.start)}
          </div>
          <div class="station">
            <span>Arrive</span>
            <strong>${escapeHtml(stationDisplayName(puzzle.end))}</strong>
            ${stationLineBadges(puzzle.end)}
          </div>
        </div>
        ${orientationMapMarkup()}
        ${
          hasRouteSummary
            ? `<section class="route-summary" aria-labelledby="routeSummaryTitle">
                <h3 id="routeSummaryTitle">Your route</h3>
                <div class="route-list">${renderRouteList(state.steps, { showDirection: false, showDetail: false })}</div>
              </section>`
            : ""
        }
      </aside>
      <section class="workspace">${content}</section>
    </div>
  `;
}

function transferFallback(fromMode, toMode) {
  const defaults = state.data.metadata.transferFallbackSeconds;
  if (fromMode === toMode) return defaults.same_mode;
  const pairKey = [fromMode, toMode].sort().join("_");
  if (Number.isFinite(defaults[pairKey])) return defaults[pairKey];
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

function combinedWaitSeconds(directionId, routeId, fromStation, toStation, baseWait = null) {
  const r = route(routeId);
  const wait = baseWait ?? waitSeconds(directionId, routeId, r.mode);
  const group = (state.data.sharedServiceGroups || []).find((item) => item.routeIds?.includes(routeId));
  if (!group) return wait;
  const dir = direction(directionId);
  const startIndex = dir.stations.indexOf(fromStation);
  const endIndex = dir.stations.indexOf(toStation, startIndex + 1);
  if (startIndex < 0 || endIndex <= startIndex) return wait;
  const rideStations = dir.stations.slice(startIndex, endIndex + 1);
  const waitsByRoute = new Map([[routeId, wait]]);
  Object.values(state.data.directions).forEach((candidate) => {
    if (candidate.routeId === routeId || !group.routeIds.includes(candidate.routeId)) return;
    const width = rideStations.length;
    const matches = candidate.stations.some((_, index) =>
      index + width <= candidate.stations.length &&
      candidate.stations.slice(index, index + width).every((stationId, offset) => stationId === rideStations[offset]),
    );
    if (!matches) return;
    const candidateRoute = route(candidate.routeId);
    const candidateWait = waitSeconds(candidate.id, candidate.routeId, candidateRoute.mode);
    waitsByRoute.set(candidate.routeId, Math.min(candidateWait, waitsByRoute.get(candidate.routeId) ?? candidateWait));
  });
  if (waitsByRoute.size === 1) return wait;
  return Math.round(1 / [...waitsByRoute.values()].reduce((sum, candidateWait) => sum + 1 / candidateWait, 0));
}

function routeContinuation(fromDirectionId) {
  return (state.data.routeContinuations || []).find((item) => item.fromDirectionId === fromDirectionId) || null;
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
  if (Number.isFinite(explicit)) return explicit;
  const equivalent = equivalentWalkSeconds(fromStation, toStation);
  return Number.isFinite(equivalent) ? equivalent : null;
}

function equivalentWalkSeconds(fromStation, toStation) {
  if (fromStation === toStation) return 0;
  if (canonicalStationId(fromStation) !== canonicalStationId(toStation)) return null;
  const direct = state.data.transfers[fromStation]?.[toStation];
  if (Number.isFinite(direct)) return direct;
  const reverse = state.data.transfers[toStation]?.[fromStation];
  if (Number.isFinite(reverse)) return reverse;
  return STATION_EQUIVALENCE_TRANSFER_SECONDS;
}

function walkOptions() {
  const currentCanonical = canonicalStationId(state.currentStation);
  const currentRouteIds = new Set(boardingOptions().map((option) => option.routeId));
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

function boardableDirectionIds(stationId, routeId) {
  const directionIds = station(stationId).services?.[routeId] || [];
  return directionIds.filter((dirId) => {
    const dir = direction(dirId);
    const index = dir.stations.indexOf(stationId);
    return index >= 0 && index < dir.stations.length - 1;
  });
}

function boardableRouteIds(stationId) {
  const services = station(stationId).services || {};
  return Object.entries(services)
    .filter(([routeId]) => boardableDirectionIds(stationId, routeId).length)
    .map(([routeId]) => routeId)
    .filter((routeId) => route(routeId))
    .sort((a, b) => {
      const ar = route(a);
      const br = route(b);
      return compareText(`${modeName(ar.mode)} ${ar.label}`, `${modeName(br.mode)} ${br.label}`);
    });
}

function walkLineBadges(stationId) {
  const badges = boardableRouteIds(stationId).map(lineBadge).join("");
  return badges ? `<span class="walk-lines" aria-label="Lines at ${escapeHtml(station(stationId).name)}">${badges}</span>` : "";
}

function equivalentBoardingLocations(stationId) {
  const currentCanonical = canonicalStationId(stationId);
  const locations = [{ stationId, walkSec: 0 }];
  if (CITY_ID === "london") {
    const linkedIds = new Set(Object.keys(state.data.transfers?.[stationId] || {}));
    Object.entries(state.data.transfers || {}).forEach(([linkedId, destinations]) => {
      if (Number.isFinite(destinations?.[stationId])) linkedIds.add(linkedId);
    });
    linkedIds.forEach((linkedId) => {
      const walkSec = explicitWalkSeconds(stationId, linkedId);
      if (Number.isFinite(walkSec) && walkSec >= 0) locations.push({ stationId: linkedId, walkSec });
    });
    return locations.sort((a, b) => a.walkSec - b.walkSec || compareText(stationDisplayName(a.stationId), stationDisplayName(b.stationId)));
  }
  Object.keys(state.data.stations || {}).forEach((transferStationId) => {
    const walkSec = equivalentWalkSeconds(stationId, transferStationId);
    if (!Number.isFinite(walkSec) || walkSec < 0) return;
    if (transferStationId === stationId) return;
    if (canonicalStationId(transferStationId) !== currentCanonical) return;
    locations.push({ stationId: transferStationId, walkSec });
  });
  return locations.sort(
    (a, b) => a.walkSec - b.walkSec || compareText(station(a.stationId).name, station(b.stationId).name),
  );
}

function boardingOptions() {
  const byRoute = new Map();
  const seen = new Set();
  equivalentBoardingLocations(state.currentStation).forEach((location) => {
    const services = station(location.stationId).services || {};
    Object.keys(services).forEach((routeId) => {
      if (!route(routeId)) return;
      const usable = boardableDirectionIds(location.stationId, routeId);
      if (!usable.length) return;
      const key = `${location.stationId}:${routeId}`;
      if (seen.has(key)) return;
      seen.add(key);
      if (!byRoute.has(routeId)) byRoute.set(routeId, { routeId, boards: [] });
      byRoute.get(routeId).boards.push({
        boardStation: location.stationId,
        walkSec: location.walkSec,
        directionIds: usable,
      });
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
      <span>From ${escapeHtml(stationDisplayName(state.currentStation))}</span>
    </div>
    ${
      options.length
        ? `<section class="choice-section">
            <h3>Board here</h3>
            <div class="choice-grid">
              ${options
                .map((option, index) => {
                  const r = route(option.routeId);
                  return `
                    <button class="choice line-choice" data-line-index="${index}">
                      ${lineChoiceMarker(option.routeId)}
                      <span>
                        <strong>${escapeHtml(routeChoiceLabel(r))}</strong>
                      </span>
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
        ? `<section class="choice-section walk-section">
            <h3>Walk first</h3>
            <div class="choice-grid">
              ${walks
                .map(
                  (option, index) => `
                    <button class="choice walk-choice" data-walk-index="${index}">
                      <span class="walk-copy">
                        <strong>Walk to ${escapeHtml(stationDisplayName(option.stationId))}</strong>
                        <span class="walk-meta">
                          <small>${formatCompactTime(option.walkSec)} transfer</small>
                          ${walkLineBadges(option.stationId)}
                        </span>
                      </span>
                    </button>
                  `,
                )
                .join("")}
            </div>
          </section>`
        : ""
    }
    ${message ? `<p class="notice">${escapeHtml(message)}</p>` : ""}
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
  const groupedDirections = new Map();
  selected.boards.forEach((board) => {
    board.directionIds.forEach((dirId) => {
      const label = directionGroupLabel(direction(dirId).label);
      const candidate = { dirId, boardStation: board.boardStation, walkSec: board.walkSec, label };
      const key = directionOptionKey(candidate);
      if (!groupedDirections.has(key)) groupedDirections.set(key, { candidates: [] });
      groupedDirections.get(key).candidates.push(candidate);
    });
  });
  groupedDirections.forEach((option) => {
    option.label = directionOptionLabel(option.candidates);
    directionOptions.push(option);
  });
  directionOptions.sort((a, b) => compareText(a.label, b.label));
  boardShell(`
    <div class="step-title">
      <h2>Choose direction</h2>
      <span>${escapeHtml(routeChoiceLabel(r))}</span>
    </div>
    <div class="choice-grid">
      ${directionOptions
        .map((option, index) => {
          const candidate = option.candidates[0];
          const directionLabel = candidate.boardStation === state.currentStation || isFreeStartHubBoarding(candidate.boardStation)
            ? ""
            : `${formatCompactTime(candidate.walkSec)} walk`;
          return `
            <button class="choice" data-direction-index="${index}">
              <strong>${escapeHtml(option.label)}</strong>
              ${directionLabel ? `<small>${directionLabel}</small>` : ""}
            </button>
          `;
        })
        .join("")}
    </div>
    ${toolbarMarkup({ backId: "backToLines", backLabel: "Back" })}
  `);
  document.querySelectorAll("[data-direction-index]").forEach((button) => {
    button.addEventListener("click", () => {
      const option = directionOptions[Number(button.dataset.directionIndex)];
      state.selected.directionCandidates = option.candidates;
      state.selected.directionId = option.candidates[0].dirId;
      state.selected.boardStation = option.candidates[0].boardStation;
      state.selected.directionLabel = option.label;
      renderAlightStep();
    });
  });
  $("#backToLines").addEventListener("click", () => renderLineStep());
  bindPuzzleToolbar();
}

function renderAlightStep() {
  state.stage = "alight";
  const selected = state.selected;
  const directionCandidates = selected.directionCandidates || [{
    dirId: selected.directionId,
    boardStation: selected.boardStation,
    walkSec: 0,
    label: direction(selected.directionId).label,
  }];
  const choiceMap = new Map();
  directionCandidates.forEach((candidate) => {
    const candidateDir = direction(candidate.dirId);
    const boardIndex = candidateDir.stations.indexOf(candidate.boardStation);
    const downstream = candidateDir.stations.slice(boardIndex + 1);
    const continuation = routeContinuation(candidate.dirId);
    if (continuation && candidateDir.stations[candidateDir.stations.length - 1] === continuation.stationId) {
      downstream.push(...direction(continuation.toDirectionId).stations.slice(1));
    }
    downstream.forEach((stationId) => {
      const runSec = runtimeBetween(candidate.dirId, candidate.boardStation, stationId);
      const choiceKey = CITY_ID === "london" ? stationDisplayName(stationId) : stationId;
      const existing = choiceMap.get(choiceKey);
      if (!existing || runSec < existing.runSec) choiceMap.set(choiceKey, { stationId, runSec, ...candidate });
    });
  });
  const choices = [...choiceMap.values()];
  const dir = direction(selected.directionId);
  const r = route(selected.routeId);
  const transferSignal = (choice) => {
    const stationId = choice.stationId;
    const runSec = choice.runSec;
    const services = station(stationId).services || {};
    const availableRouteIds = new Set(Object.keys(services));
    stationInterchangeRouteIds(stationId).forEach((routeId) => availableRouteIds.add(routeId));
    const transferBadges = [...availableRouteIds]
      .filter((routeId) => routeId !== selected.routeId && route(routeId))
      .sort((a, b) => compareText(route(a).label, route(b).label))
      .map(lineBadge)
      .join("");
    return `
      ${transferBadges ? `<span class="transfer-lines" aria-label="Transfer lines">${transferBadges}</span>` : ""}
      <span class="stop-meta"><small class="stop-time">${formatCompactTime(runSec)}</small></span>
    `;
  };
  boardShell(`
    <div class="stop-selection">
    <div class="step-title">
      <h2>Choose your stop</h2>
      <span>${escapeHtml(routeDisplayName(r))} · ${escapeHtml(selected.directionLabel || directionGroupLabel(dir.label))}</span>
    </div>
    <div class="stop-strip" aria-label="${escapeHtml(routeDisplayName(r))} ${escapeHtml(selected.directionLabel || directionGroupLabel(dir.label))}">
      ${choices
        .map(
          (choice) => `
            <button class="choice stop-choice${samePuzzleStation(choice.stationId, currentPuzzle().end) ? " destination-choice" : ""}" data-alight="${escapeHtml(choice.stationId)}" data-direction-id="${escapeHtml(choice.dirId)}" data-board-station="${escapeHtml(choice.boardStation)}">
              <span class="stop-node" aria-hidden="true"></span>
              <span class="stop-main">
                <strong>${escapeHtml(stationDisplayName(choice.stationId))}</strong>
                ${transferSignal(choice)}
              </span>
            </button>
          `,
        )
        .join("")}
    </div>
    ${toolbarMarkup({ backId: "backToDirections", backLabel: "Back" })}
    </div>
  `);
  document.querySelectorAll("[data-alight]").forEach((button) => {
    button.addEventListener("click", () => {
      state.selected.directionId = button.dataset.directionId;
      state.selected.boardStation = button.dataset.boardStation;
      addLeg(button.dataset.alight);
    });
  });
  $("#backToDirections").addEventListener("click", renderDirectionStep);
  bindPuzzleToolbar();
}

function runtimeBetween(dirId, fromStation, toStation) {
  const dir = direction(dirId);
  const fromIndex = dir.stations.indexOf(fromStation);
  const toIndex = dir.stations.indexOf(toStation);
  if (fromIndex < 0) return null;
  if (toIndex > fromIndex) return dir.runtimes.slice(fromIndex, toIndex).reduce((sum, sec) => sum + sec, 0);

  const continuation = routeContinuation(dirId);
  if (!continuation || dir.stations[dir.stations.length - 1] !== continuation.stationId) return null;
  const nextDir = direction(continuation.toDirectionId);
  const nextToIndex = nextDir.stations.indexOf(toStation);
  if (nextToIndex <= 0) return null;
  const firstPart = dir.runtimes.slice(fromIndex).reduce((sum, sec) => sum + sec, 0);
  const secondPart = nextDir.runtimes.slice(0, nextToIndex).reduce((sum, sec) => sum + sec, 0);
  return firstPart + secondPart;
}

function rideSegmentsBetween(dirId, fromStation, toStation) {
  const dir = direction(dirId);
  const fromIndex = dir.stations.indexOf(fromStation);
  const toIndex = dir.stations.indexOf(toStation);
  if (fromIndex >= 0 && toIndex > fromIndex) return [{ directionId: dirId, from: fromStation, to: toStation }];

  const continuation = routeContinuation(dirId);
  if (!continuation || fromIndex < 0 || dir.stations[dir.stations.length - 1] !== continuation.stationId) return [];
  const nextDir = direction(continuation.toDirectionId);
  const nextToIndex = nextDir.stations.indexOf(toStation);
  if (nextToIndex <= 0) return [];
  return [
    { directionId: dirId, from: fromStation, to: continuation.stationId },
    { directionId: continuation.toDirectionId, from: continuation.stationId, to: toStation },
  ];
}

function legTiming(selected, toStation, rideSec) {
  const r = route(selected.routeId);
  const waitSec = combinedWaitSeconds(
    selected.directionId,
    selected.routeId,
    selected.boardStation,
    toStation,
  );
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
  if (samePuzzleStation(toStation, currentPuzzle().end)) {
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

  if (selected.boardStation !== state.currentStation && !isFreeStartHubBoarding(selected.boardStation)) {
    const walked = addWalkStep(selected.boardStation, selected.routeId, { renderAfter: false });
    if (!walked) return;
  }

  const leg = {
    type: "ride",
    routeId: selected.routeId,
    directionId: selected.directionId,
    from: selected.boardStation,
    to: toStation,
    segments: rideSegmentsBetween(selected.directionId, selected.boardStation, toStation),
    ...timing,
  };
  state.steps.push(leg);
  state.totalSec += timing.elapsedSec;
  state.currentStation = toStation;
  state.selected = {};

  if (samePuzzleStation(toStation, currentPuzzle().end)) {
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

function fastestRideTimingForLeg(step, previousRide) {
  const r = route(step.routeId);
  if (!r) return null;
  const candidates = boardableDirectionIds(step.from, step.routeId)
    .map((directionId) => {
      const rideSec = runtimeBetween(directionId, step.from, step.to);
      if (!Number.isFinite(rideSec)) return null;
      const transferSec = previousRide
        ? transferSeconds(
            step.from,
            step.from,
            previousRide.routeId,
            step.routeId,
            route(previousRide.routeId).mode,
            r.mode,
          )
        : Number(step.transferSec) || 0;
      if (!Number.isFinite(transferSec)) return null;
      const waitSec = combinedWaitSeconds(directionId, step.routeId, step.from, step.to);
      return { rideSec, waitSec, transferSec, elapsedSec: rideSec + waitSec + transferSec };
    })
    .filter(Boolean);
  return candidates.reduce((best, candidate) => (!best || candidate.elapsedSec < best.elapsedSec ? candidate : best), null);
}

function bestComparableTotalSec(steps, fallbackTotalSec) {
  let totalSec = 0;
  let previousRide = null;
  for (const step of steps) {
    if (stepType(step) === "walk") {
      totalSec += Number.isFinite(step.elapsedSec) ? step.elapsedSec : Number(step.transferSec) || 0;
      previousRide = null;
      continue;
    }
    const bestTiming = fastestRideTimingForLeg(step, previousRide);
    totalSec += bestTiming?.elapsedSec ?? step.elapsedSec ?? 0;
    previousRide = step;
  }
  return Number.isFinite(totalSec) && totalSec > 0 ? totalSec : fallbackTotalSec;
}

function scoreRoute(puzzle, signature, totalSec, steps = []) {
  const optimal = puzzle.optimalRoute;
  const exact = signature === optimal.signature;
  const comparableTotalSec = Math.min(totalSec, bestComparableTotalSec(steps, totalSec));
  const perfect = exact || Math.max(0, comparableTotalSec - optimal.totalSec) <= 1;
  if (perfect) return { score: 100, label: "Perfect" };

  const deltaSec = Math.max(0, comparableTotalSec - optimal.totalSec);
  const deltaMin = deltaSec / 60;
  const slowPct = (deltaSec / optimal.totalSec) * 100;
  const rawScore = 100 - deltaMin - slowPct * 0.8;
  const score = Math.max(10, Math.min(99, Math.round(rawScore)));

  if (score >= 90) return { score, label: "Excellent route" };
  if (score >= 80) return { score, label: "Very close route" };
  if (score >= 65) return { score, label: "Good route" };
  if (score >= 45) return { score, label: "Valid route" };
  return { score, label: "Slow route" };
}

function reviewVisibleSteps(steps) {
  return steps.filter((step, index) => {
    if (stepType(step) !== "walk") return true;
    const adjacentRides = [steps[index - 1], steps[index + 1]].filter(
      (candidate) => candidate && stepType(candidate) === "ride",
    );
    return !adjacentRides.some((candidate) => route(candidate.routeId)?.mode === "elizabeth");
  });
}

function routePanel(title, steps) {
  const visibleSteps = reviewVisibleSteps(steps);
  return `
    <div class="route-panel">
      <h3>${escapeHtml(title)}</h3>
      <div class="route-list">${renderRouteList(visibleSteps, { showDirection: false, showElapsed: false, compactElapsed: true })}</div>
    </div>
  `;
}

function routeComparisonMarkup(userSteps, optimalSteps) {
  return `
    <div class="comparison">
      ${routePanel("Your route", userSteps)}
      ${routePanel("Fastest route", optimalSteps)}
    </div>
    <div class="comparison-tabs" data-comparison-tabs>
      <div class="comparison-tablist" role="tablist" aria-label="Route comparison">
        <button type="button" class="comparison-tab is-active" data-route-tab="user" aria-selected="true">Your route</button>
        <button type="button" class="comparison-tab" data-route-tab="fastest" aria-selected="false">Fastest route</button>
      </div>
      <div class="comparison-tabpanel is-active" data-route-panel="user">
        ${routePanel("Your route", userSteps)}
      </div>
      <div class="comparison-tabpanel" data-route-panel="fastest" hidden>
        ${routePanel("Fastest route", optimalSteps)}
      </div>
    </div>
  `;
}

function bindComparisonTabs() {
  const root = document.querySelector("[data-comparison-tabs]");
  if (!root) return;
  const tabs = [...root.querySelectorAll("[data-route-tab]")];
  const panels = [...root.querySelectorAll("[data-route-panel]")];
  tabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const target = tab.dataset.routeTab;
      tabs.forEach((item) => {
        const selected = item === tab;
        item.classList.toggle("is-active", selected);
        item.setAttribute("aria-selected", String(selected));
      });
      panels.forEach((panel) => {
        const selected = panel.dataset.routePanel === target;
        panel.classList.toggle("is-active", selected);
        panel.hidden = !selected;
      });
    });
  });
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
  const scored = scoreRoute(puzzle, signature, state.totalSec, state.steps);
  const optimal = puzzle.optimalRoute;
  const optimalSteps = precomputedSteps(optimal);
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
      </div>
      <div class="scoreboard">
        <div class="scorebox"><span>Score</span><strong>${scored.score}</strong></div>
        <div class="scorebox"><span>Your time</span><strong>${formatTime(state.totalSec)}</strong></div>
        <div class="scorebox"><span>Fastest time</span><strong>${formatTime(optimal.totalSec)}</strong></div>
      </div>
      ${routeComparisonMarkup(state.steps, optimalSteps)}
      <div class="toolbar">
        <button class="action" id="nextPuzzle">${state.puzzleIndex + 1 === puzzleCount() ? "Summary" : "Next puzzle"}</button>
      </div>
    </div>
  `, { showRouteSummary: false });
  bindComparisonTabs();
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
      </div>
      <div class="scoreboard">
        <div class="scorebox"><span>Score</span><strong>0</strong></div>
        <div class="scorebox"><span>Fastest time</span><strong>${formatTime(optimal.totalSec)}</strong></div>
      </div>
      ${routePanel("Fastest route", optimalSteps)}
      <div class="toolbar">
        <button class="action" id="nextPuzzle">${state.puzzleIndex + 1 === puzzleCount() ? "Summary" : "Next puzzle"}</button>
      </div>
    </div>
  `, { showRouteSummary: false });
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
  return `chronometro.cc ${state.dailyDate || cityDateString()}\n${total}/${puzzleCount() * 100}\nScores: ${shareScores()}`;
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
      <p class="source-note">Route data: ${escapeHtml(state.data.metadata.city.attribution.display)}.</p>
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
  setRoundLabel();
  renderLineStep();
}

async function fetchJson(url) {
  try {
    const separator = url.includes("?") ? "&" : "?";
    const response = await fetch(`${url}${separator}v=${DATA_REVISION}`);
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

function puzzleSetFromDailyData(dailyData, dailyDate) {
  const dailyPuzzles = playablePuzzles(dailyData);
  if (dailyPuzzles.length) {
    return {
      date: dailyData?.metadata?.date || dailyDate,
      kind: dailyData?.metadata?.kind || "daily-puzzles",
      puzzles: dailyPuzzles,
    };
  }
  return null;
}

async function loadExamplePuzzleSet(today) {
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

async function loadPuzzleSet(today = cityDateString()) {
  const todayData = await fetchJson(`${DAILY_BASE_URL}/${today}.json`);
  const todayPuzzleSet = puzzleSetFromDailyData(todayData, today);
  if (todayPuzzleSet) return todayPuzzleSet;

  const index = await fetchJson(DAILY_INDEX_URL);
  const dailyDate = nearestDailyDate(index?.dates, today);
  if (dailyDate && dailyDate !== today) {
    const dailyData = await fetchJson(`${DAILY_BASE_URL}/${dailyDate}.json`);
    const dailyPuzzleSet = puzzleSetFromDailyData(dailyData, dailyDate);
    if (dailyPuzzleSet) return dailyPuzzleSet;
  }

  return loadExamplePuzzleSet(today);
}

function showLoadingState() {
  $("#game").innerHTML = `<section class="summary"><p class="muted">Loading today's route...</p></section>`;
}

function updateCityChrome() {
  const city = state.data.metadata.city;
  $("#citySelector").value = CITY_ID;
  $("#cityKicker").textContent = `${city.name} daily route puzzle`;
  $("#cityDisclaimer").textContent = city.attribution.disclaimer;
  document.title = `Chronométro — ${city.name}`;
  document.documentElement.dataset.city = CITY_ID;
  document.querySelectorAll(".site-footer nav a").forEach((link) => {
    const url = new URL(link.href);
    if (CITY_ID === "london") url.searchParams.set("city", "london");
    else url.searchParams.delete("city");
    link.href = url;
  });
}

function bindCitySelector() {
  $("#citySelector").value = CITY_ID;
  $("#citySelector").addEventListener("change", (event) => {
    const url = new URL(window.location.href);
    if (event.target.value === "paris") url.searchParams.delete("city");
    else url.searchParams.set("city", event.target.value);
    window.location.assign(url);
  });
}

async function init() {
  showLoadingState();
  bindCitySelector();
  $("#homeButton").addEventListener("click", () => {
    if (state.data) restartDay();
  });
  state.data = await fetchJson(NETWORK_URL);
  if (!state.data) throw new Error("Network load failed");
  configureCityMap();
  updateCityChrome();
  const today = cityDateString();
  const puzzleSet = await loadPuzzleSet(today);
  state.daily = puzzleSet.puzzles;
  state.dailyDate = puzzleSet.date;
  state.dailyKind = puzzleSet.kind;
  startPuzzle();
}

init().catch(() => {
  $("#game").innerHTML = `<section class="summary"><h2>Could not load</h2><p>Could not load today’s puzzle data. Try refreshing the page.</p></section>`;
});
