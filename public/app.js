const DATA_URL = "./data/metro-express-data.json";
const DAILY_COUNT = 5;

const state = {
  data: null,
  daily: [],
  puzzleIndex: 0,
  currentStation: null,
  legs: [],
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
  return rem ? `${min} min ${rem}s` : `${min} min`;
}

function formatCompactTime(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return "";
  if (sec < 60) return `${Math.round(sec)}s`;
  return `${Math.round(sec / 60)} min`;
}

function formatSignedTime(sec) {
  if (!Number.isFinite(sec) || sec <= 0) return "Matched fastest time";
  return `+${formatTime(sec)} vs fastest`;
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

function dailyPuzzles(data) {
  const random = rng(hashString(`metro-express:${parisDateString()}`));
  const indices = data.puzzles.map((_, index) => index);
  for (let i = indices.length - 1; i > 0; i -= 1) {
    const j = Math.floor(random() * (i + 1));
    [indices[i], indices[j]] = [indices[j], indices[i]];
  }
  return indices.slice(0, DAILY_COUNT).map((index) => data.puzzles[index]);
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
  $("#todayLabel").textContent = parisDateString();
  $("#roundLabel").textContent =
    state.stage === "summary" ? "Done" : `${state.puzzleIndex + 1} / ${DAILY_COUNT}`;
}

function currentPuzzle() {
  return state.daily[state.puzzleIndex];
}

function renderRouteList(legs) {
  if (!legs.length) return `<p class="muted">No legs yet.</p>`;
  return legs
    .map(
      (leg) => `
        <div class="leg-chip">
          ${lineBadge(leg.routeId)}
          <p>
            <strong>${escapeHtml(station(leg.from).name)} -> ${escapeHtml(station(leg.to).name)}</strong>
            <small>Direction ${escapeHtml(direction(leg.directionId).label)}</small>
          </p>
          <small>${Number.isFinite(leg.elapsedSec) && leg.elapsedSec > 0 ? formatTime(leg.elapsedSec) : ""}</small>
        </div>
      `,
    )
    .join("");
}

function finalStationLineHint() {
  const puzzle = currentPuzzle();
  const lines = new Map();
  Object.values(state.data.directions).forEach((dir) => {
    if (!dir.stations.includes(puzzle.end)) return;
    const r = route(dir.routeId);
    lines.set(dir.routeId, `${modeName(r.mode)} ${r.label}`);
  });
  return [...lines.values()].sort(compareText).join(", ");
}

function hintMarkup() {
  return state.hintText ? `<p class="hint">${escapeHtml(state.hintText)}</p>` : "";
}

function toolbarMarkup({ backId = "", backLabel = "" } = {}) {
  const destinationLinesLabel = state.hintText ? "Hide destination lines" : "Show destination lines";
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
        <p class="intro-prompt">Build the fastest route from Départ to Arrivée. Choose a line, direction, and stop; transfers and waits count.</p>
        <div>
          <h3>Your route</h3>
          <div class="route-list">${renderRouteList(state.legs)}</div>
        </div>
      </aside>
      <section class="workspace">${content}</section>
    </div>
  `;
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

function boardingOptions() {
  const origins = [{ stationId: state.currentStation, walkSec: 0 }];
  if (state.legs.length) {
    const transfers = state.data.transfers[state.currentStation] || {};
    Object.entries(transfers).forEach(([stationId, walkSec]) => {
      if (state.data.stations[stationId]?.services) origins.push({ stationId, walkSec });
    });
  }

  const byRoute = new Map();
  const seen = new Set();
  origins.forEach((origin) => {
    const services = station(origin.stationId).services || {};
    Object.entries(services).forEach(([routeId, directionIds]) => {
      const usable = directionIds.filter((dirId) => {
        const dir = direction(dirId);
        const index = dir.stations.indexOf(origin.stationId);
        return index >= 0 && index < dir.stations.length - 1;
      });
      if (!usable.length) return;
      const key = `${origin.stationId}:${routeId}`;
      if (seen.has(key)) return;
      seen.add(key);
      if (!byRoute.has(routeId)) byRoute.set(routeId, { routeId, boards: [] });
      byRoute.get(routeId).boards.push({
        boardStation: origin.stationId,
        walkSec: origin.walkSec,
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
  boardShell(`
    <div class="step-title">
      <h2>Choose a line</h2>
      <span>From ${escapeHtml(station(state.currentStation).name)}</span>
    </div>
    <div class="choice-grid">
      ${options
        .map((option, index) => {
          const r = route(option.routeId);
          const bestBoard = option.boards[0];
          const boardsHere = bestBoard.boardStation === state.currentStation;
          const walk =
            boardsHere
              ? state.legs.length
                ? "Transfer here"
                : "Board here"
              : `Walk about ${formatCompactTime(bestBoard.walkSec)} to ${escapeHtml(station(bestBoard.boardStation).name)}`;
          return `
            <button class="choice line-choice" data-line-index="${index}">
              ${lineBadge(option.routeId)}
              <span><strong>${escapeHtml(modeName(r.mode))} ${escapeHtml(r.label)}</strong> <small>${walk}</small></span>
            </button>
          `;
        })
        .join("")}
    </div>
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
                  ? state.legs.length
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
        <small>${formatCompactTime(runSec)} ride</small>
        ${transferBadges ? `<span class="transfer-lines" aria-label="Transfer lines">${transferBadges}</span>` : ""}
      </span>
    `;
  };
  boardShell(`
    <div class="step-title">
      <h2>Choose your stop</h2>
      <span>${escapeHtml(r.label)} toward ${escapeHtml(dir.label)}</span>
    </div>
    <div class="choice-grid">
      ${choices
        .map(
          (stationId) => `
            <button class="choice stop-choice${stationId === currentPuzzle().end ? " destination-choice" : ""}" data-alight="${escapeHtml(stationId)}">
              <strong>${escapeHtml(station(stationId).name)}</strong>
              <small>${stationId === currentPuzzle().end ? "Destination" : "Get off here"}</small>
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

function addLeg(toStation) {
  const selected = state.selected;
  const r = route(selected.routeId);
  const runSec = runtimeBetween(selected.directionId, selected.boardStation, toStation);
  if (!Number.isFinite(runSec)) {
    renderLineStep("That leg is not connected in the selected direction.");
    return;
  }

  let connectSec = waitSeconds(selected.directionId, selected.routeId, r.mode);
  if (state.legs.length) {
    const previous = state.legs[state.legs.length - 1];
    const previousMode = route(previous.routeId).mode;
    const walk = transferSeconds(
      state.currentStation,
      selected.boardStation,
      previous.routeId,
      selected.routeId,
      previousMode,
      r.mode,
    );
    if (!Number.isFinite(walk)) {
      renderLineStep("There is no transfer link between those stations in the feed.");
      return;
    }
    connectSec += walk;
  }

  const elapsedSec = connectSec + runSec;
  const leg = {
    routeId: selected.routeId,
    directionId: selected.directionId,
    from: selected.boardStation,
    to: toStation,
    elapsedSec,
  };
  state.legs.push(leg);
  state.totalSec += elapsedSec;
  state.currentStation = toStation;
  state.selected = {};

  if (toStation === currentPuzzle().end) {
    renderResult();
  } else {
    renderLineStep();
  }
}

function routeSignature(legs) {
  return legs.map((leg) => `${leg.routeId}:${leg.directionId}:${leg.from}:${leg.to}`).join("|");
}

function scoreRoute(puzzle, signature, totalSec) {
  const optimal = puzzle.optimalRoute;
  const exact = signature === optimal.signature;
  if (exact) return { score: 100, label: "Fastest route" };

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

function routePanel(title, legs, totalSec) {
  return `
    <div class="route-panel">
      <h3>${escapeHtml(title)} <small>${formatTime(totalSec)}</small></h3>
      <div class="route-list">${renderRouteList(legs)}</div>
    </div>
  `;
}

function precomputedLegs(routeInfo) {
  return routeInfo.legs.map((leg) => ({
    routeId: leg.routeId,
    directionId: leg.directionId,
    from: leg.from,
    to: leg.to,
    elapsedSec: null,
  }));
}

function renderResult() {
  const puzzle = currentPuzzle();
  const signature = routeSignature(state.legs);
  const scored = scoreRoute(puzzle, signature, state.totalSec);
  const optimal = puzzle.optimalRoute;
  const deltaSec = Math.max(0, state.totalSec - optimal.totalSec);
  const slowPct = optimal.totalSec ? Math.round((deltaSec / optimal.totalSec) * 100) : 0;
  const transferCount = Math.max(0, state.legs.length - 1);
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
        ${routePanel("Your route", state.legs, state.totalSec)}
        ${routePanel("Fastest route", precomputedLegs(optimal), optimal.totalSec)}
      </div>
      <div class="toolbar">
        <button class="action" id="nextPuzzle">${state.puzzleIndex + 1 === DAILY_COUNT ? "Summary" : "Next puzzle"}</button>
      </div>
    </div>
  `);
  $("#nextPuzzle").addEventListener("click", goNextPuzzle);
}

function giveUp() {
  const puzzle = currentPuzzle();
  const optimal = puzzle.optimalRoute;
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
      ${routePanel("Fastest route", precomputedLegs(optimal), optimal.totalSec)}
      <div class="toolbar">
        <button class="action" id="nextPuzzle">${state.puzzleIndex + 1 === DAILY_COUNT ? "Summary" : "Next puzzle"}</button>
      </div>
    </div>
  `);
  $("#nextPuzzle").addEventListener("click", goNextPuzzle);
}

function goNextPuzzle() {
  if (state.puzzleIndex + 1 === DAILY_COUNT) {
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
  return `Métro Express ${parisDateString()}\n${total}/500\nScores: ${shareScores()}`;
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
        <div class="scorebox"><span>Puzzles</span><strong>${DAILY_COUNT}</strong></div>
        <div class="scorebox"><span>Max score</span><strong>500</strong></div>
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
  state.legs = [];
  state.totalSec = 0;
  state.selected = {};
  state.hintText = "";
  setRoundLabel();
  renderLineStep();
}

async function init() {
  $("#game").innerHTML = `<section class="summary"><h2>Loading</h2><p>Preparing the July 2026 Paris network.</p></section>`;
  $("#homeButton").addEventListener("click", () => {
    if (state.data) restartDay();
  });
  const response = await fetch(DATA_URL);
  if (!response.ok) throw new Error("Data load failed");
  state.data = await response.json();
  state.daily = dailyPuzzles(state.data);
  startPuzzle();
}

init().catch(() => {
  $("#game").innerHTML = `<section class="summary"><h2>Could not load</h2><p>Could not load today’s puzzle data. Try refreshing the page.</p></section>`;
});
