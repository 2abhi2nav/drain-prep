const API = window.location.origin;
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const esc = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
const num = (value, digits = 0) => new Intl.NumberFormat("en-IN", { maximumFractionDigits: digits, minimumFractionDigits: digits }).format(value ?? 0);
const percent = (value) => `${((value ?? 0) * 100).toFixed(1)}%`;

const state = {
  section: "Forecast",
  bootstrap: null,
  error: "",
  month: new Date().getMonth() + 1,
  warning: "No warning",
  rain1: 80,
  rain3: 160,
  forecast: null,
  zoneInputs: [],
  resourceUnits: 10,
  zoneResults: [],
  populationWeightedProbability: null,
  powerProfile: null,
  busy: "",
};

async function api(path, body) {
  const response = await fetch(`${API}${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.detail ?? response.statusText ?? "Request failed");
  return data;
}

const chartLayout = {
  paper_bgcolor: "#171919", plot_bgcolor: "#171919", font: { color: "#ffffff", family: "monospace", size: 10 },
  margin: { l: 55, r: 20, t: 14, b: 48 }, height: 310, showlegend: true,
  legend: { orientation: "h", y: 1.15 }, hovermode: "closest",
  xaxis: { gridcolor: "rgba(255,255,255,0.25)", zerolinecolor: "rgba(255,255,255,0.45)", linecolor: "rgba(255,255,255,0.55)" },
  yaxis: { gridcolor: "rgba(255,255,255,0.25)", zerolinecolor: "rgba(255,255,255,0.45)", linecolor: "rgba(255,255,255,0.55)" },
};
const chartConfig = { responsive: true, displaylogo: false, modeBarButtonsToRemove: ["lasso2d", "select2d"] };

function drawPlot(id, traces, layout = {}) {
  const target = document.getElementById(id);
  if (target && window.Plotly) Plotly.newPlot(target, traces, { ...chartLayout, ...layout }, chartConfig);
}

function drawZeroCenteredBar(id, rows, name) {
  const max = Math.max(.01, ...rows.map((row) => Math.abs(row.value))) * 1.15;
  drawPlot(id, [{ type: "bar", orientation: "h", x: rows.map((row) => row.value), y: rows.map((row) => row.label),
    base: 0, marker: { color: "#f5a742" }, hovertemplate: "%{y}<br>%{x:.3f}<extra></extra>", name }], {
    xaxis: { ...chartLayout.xaxis, range: [-max, max], title: "Effect on log-odds", zeroline: false },
    yaxis: { ...chartLayout.yaxis, autorange: "reversed" },
    shapes: [{ type: "line", x0: 0, x1: 0, y0: -0.5, y1: rows.length - 0.5,
      line: { color: "#e7e0d5", width: 1, dash: "dot" } }],
  });
}

function drawForecastCharts() {
  const model = state.bootstrap.forecast_model;
  drawPlot("roc-chart", [
    { type: "scatter", mode: "lines", x: model.roc.map((row) => row.false_positive_rate), y: model.roc.map((row) => row.true_positive_rate), name: "Model", line: { color: "#f5a742", width: 2.5 } },
    { type: "scatter", mode: "lines", x: [0, 1], y: [0, 1], name: "Chance", line: { color: "#68716d", dash: "dot" } },
  ], { xaxis: { ...chartLayout.xaxis, title: "False positive rate", range: [0, 1] }, yaxis: { ...chartLayout.yaxis, title: "True positive rate", range: [0, 1] } });
  drawPlot("pr-chart", [{ type: "scatter", mode: "lines", x: model.precision_recall.map((row) => row.recall), y: model.precision_recall.map((row) => row.precision), name: "Model", line: { color: "#f5a742", width: 2.5 } }], {
    xaxis: { ...chartLayout.xaxis, title: "Recall", range: [0, 1] }, yaxis: { ...chartLayout.yaxis, title: "Precision", range: [0, 1] },
  });
  drawPlot("calibration-chart", [
    { type: "scatter", mode: "markers", x: model.calibration.map((row) => row.predicted), y: model.calibration.map((row) => row.observed),
      error_y: { type: "data", symmetric: false, array: model.calibration.map((row) => row.ci_upper - row.observed), arrayminus: model.calibration.map((row) => row.observed - row.ci_lower), color: "#f5a742", thickness: 1 },
      marker: { size: 9, color: "#f5a742", line: { color: "#101111", width: 1 } }, name: "Observed bins", hovertemplate: "Predicted %{x:.1%}<br>Observed %{y:.1%}<extra></extra>" },
    { type: "scatter", mode: "lines", x: [0, 1], y: [0, 1], name: "Ideal", line: { color: "#68716d", dash: "dot" } },
  ], { xaxis: { ...chartLayout.xaxis, title: "Mean predicted probability", range: [0, 1] }, yaxis: { ...chartLayout.yaxis, title: "Observed heavy-rain fraction", range: [0, 1] } });
  drawZeroCenteredBar("logistic-coefficients", model.coefficients.map((row) => ({ label: row.feature.replaceAll("_", " "), value: row.value })), "Logistic");
}

function drawPopulationChart() {
  if (!state.zoneResults.length) return;
  const rows = [...state.zoneResults].sort((a, b) => a.priority_score - b.priority_score);
  drawPlot("zone-priority-chart", [{ type: "bar", orientation: "h", y: rows.map((row) => row.zone), x: rows.map((row) => row.priority_score),
    marker: { color: "#f5a742" }, customdata: rows.map((row) => [row.model_probability, row.forecast_percentile]),
    hovertemplate: "%{y}<br>Priority %{x:.1f}<br>Model P %{customdata[0]:.1%}<br>IMD QPF percentile %{customdata[1]:.1f}<extra></extra>" }], {
    margin: { l: 125, r: 20, t: 30, b: 42 }, height: 360,
    xaxis: { ...chartLayout.xaxis, title: "Priority index", rangemode: "tozero" }, yaxis: { ...chartLayout.yaxis, autorange: "reversed" }, showlegend: false,
  });
}

function drawPowerCharts() {
  if (!state.powerProfile) return;
  const sectors = state.powerProfile.sectors;
  drawPlot("sector-generation-chart", [
    { type: "bar", x: sectors.map((row) => row.sector), y: sectors.map((row) => row.previous_actual_ytd), name: "Prior-year output", marker: { color: "#626b67" } },
    { type: "bar", x: sectors.map((row) => row.sector), y: sectors.map((row) => row.actual_ytd), name: "2023–24 output", marker: { color: "#f5a742" } },
  ], { barmode: "group", xaxis: { ...chartLayout.xaxis, title: "" }, yaxis: { ...chartLayout.yaxis, title: "Reported generation" } });
  const rows = [...state.powerProfile.stations].filter((row) => Number.isFinite(row.generation_change_pct)).sort((a, b) => a.generation_change_pct - b.generation_change_pct).slice(0, 18);
  const max = Math.max(10, ...rows.map((row) => Math.abs(row.generation_change_pct))) * 1.15;
  drawPlot("station-change-chart", [{ type: "bar", orientation: "h", x: rows.map((row) => row.generation_change_pct), y: rows.map((row) => row.station),
    marker: { color: rows.map((row) => row.generation_change_pct < 0 ? "#7c8581" : "#f5a742") },
    hovertemplate: "%{y}<br>Change %{x:.1f}%<extra></extra>" }], {
    margin: { l: 150, r: 20, t: 30, b: 42 }, height: 440,
    xaxis: { ...chartLayout.xaxis, title: "Change (%)", range: [-max, max], zeroline: false },
    yaxis: { ...chartLayout.yaxis, autorange: "reversed" }, showlegend: false,
    shapes: [{ type: "line", x0: 0, x1: 0, y0: -0.5, y1: rows.length - 0.5, line: { color: "#e7e0d5", dash: "dot", width: 1 } }],
  });
}

function metric(label, value) {
  return `<div class="metric-card"><span>${esc(label)}</span><b>${esc(value)}</b></div>`;
}

function sectionHeader(index, label, title, note = "") {
  return `<div class="section-heading"><div><span class="section-kicker">${index} / ${esc(label)}</span><h2>${esc(title)}</h2></div>${note ? `<span class="section-note">${note}</span>` : ""}</div>`;
}

function forecastView() {
  const result = state.forecast;
  const model = state.bootstrap.forecast_model;
  const links = state.bootstrap.imd_products.slice(0, 2);
  return `<section class="content-section">
    ${sectionHeader("01", "RAINFALL OUTLOOK", "Forecast desk", `<span class="orange-dot"></span> Chennai`)}
    <div class="forecast-grid">
      <form id="forecast-form" class="panel forecast-form">
        <div class="panel-top"><span class="panel-title">Scenario inputs</span><span class="panel-code">IN / MM</span></div>
        <div class="field-row">
          <label class="field"><span>Forecast rainfall (next 24h)</span><div class="input-wrap"><input name="rain1" type="number" min="0" max="1000" value="${state.rain1}" /><b>mm</b></div></label>
          <label class="field"><span>Prior 3-day total</span><div class="input-wrap"><input name="rain3" type="number" min="0" max="2000" value="${state.rain3}" /><b>mm</b></div></label>
        </div>
        <label class="field month-field"><span>Forecast month</span><select name="month">${MONTHS.map((name, i) => `<option value="${i + 1}" ${state.month === i + 1 ? "selected" : ""}>${name}</option>`).join("")}</select></label>
        <button class="primary-button" ${state.busy === "forecast" ? "disabled" : ""}>${state.busy === "forecast" ? "Calculating…" : "Run forecast"}<span aria-hidden="true">↗</span></button>
        <div class="imd-links">${links.map((link) => `<a href="${link.url}" target="_blank" rel="noreferrer">${esc(link.label)}<span>↗</span></a>`).join("")}</div>
      </form>
      <div class="panel forecast-result"><div class="panel-top"><span class="panel-title">Heavy-rain likelihood</span><span class="panel-code">LOGISTIC / 24H</span></div>
        ${result ? `<div class="forecast-reading"><span>${percent(result.heavy_rain_probability)}</span><small>next-day probability given the prior 3-day total</small></div>
          <div class="reading-rule"><i style="width:${Math.max(2, result.heavy_rain_probability * 100)}%"></i></div>
          <div class="reading-bottom"><span>≥ 64.5 mm / 24h</span><span class="tier-chip tier-${result.assessment.tier.toLowerCase()}">${esc(result.assessment.tier)}</span></div>
          <div class="result-metrics"><div class="result-metric"><span>FORECAST NEXT 24H</span><b>${num(state.rain1)} <i>mm</i></b><small>${result.forecast_percentile.toFixed(1)}th historical percentile</small></div><div class="result-metric"><span>PRIOR 3-DAY TOTAL</span><b>${num(state.rain3)} <i>mm</i></b><small>Logistic model input</small></div></div>
          <div class="scenario-note">${state.rain1 >= 64.5 ? "The scenario forecast itself exceeds the 64.5 mm heavy-rain threshold; the model probability is a separate antecedent-conditions estimate." : "The scenario forecast is below the heavy-rain threshold; the probability estimates next-day risk from antecedent conditions."}</div>` : `<div class="empty-result"><span class="empty-cloud">⌁</span><span>Enter a rainfall scenario to view its historical risk.</span></div>`}
      </div>
    </div>
    <div class="model-strip"><span class="model-strip-title">● NEXT-DAY HEAVY-RAIN LOGISTIC</span><span>Features: prior 3-day rain + season</span><span>Holdout: ${esc(model.holdout_period[0])} — ${esc(model.holdout_period[1])}</span><span>Threshold: 64.5 mm</span></div>
    <div class="model-metrics">${metric("ROC AUC", model.metrics.auc.toFixed(3))}${metric("Average precision", model.metrics.average_precision.toFixed(3))}${metric("Brier score", model.metrics.brier.toFixed(3))}${metric("Precision / recall", `${percent(model.metrics.precision)} / ${percent(model.metrics.recall)}`)}</div>
    <div class="chart-grid two-col">
      <div class="chart-card"><div class="chart-heading"><span>ROC curve</span><span class="chart-unit">Zoom · hover</span></div><div id="roc-chart" class="plotly-chart"></div></div>
      <div class="chart-card"><div class="chart-heading"><span>Precision–recall</span><span class="chart-unit">Zoom · hover</span></div><div id="pr-chart" class="plotly-chart"></div></div>
      <div class="chart-card"><div class="chart-heading"><span>Calibration deciles</span><span class="chart-unit">95% intervals</span></div><div id="calibration-chart" class="plotly-chart"></div></div>
      <div class="chart-card"><div class="chart-heading"><span>Model coefficients</span><span class="chart-unit">Zero centered</span></div><div id="logistic-coefficients" class="plotly-chart"></div></div>
    </div>
    <div class="model-footnote">Observed rainfall stands in for unavailable archived forecasts; holdout metrics are not live IMD forecast skill.</div>
  </section>`;
}

function populationView() {
  const results = new Map(state.zoneResults.map((row) => [row.zone, row]));
  const zoneMeta = new Map(state.bootstrap.zones.map((row) => [row.name, row]));
  const rows = state.zoneInputs.map((input) => {
    const base = zoneMeta.get(input.zone);
    const result = results.get(input.zone);
    return `<tr><td class="zone-name">${esc(input.zone)}</td><td>${num(base.population)}</td><td>${num(base.children)}</td><td>${num(base.seniors)}</td>
      <td><input class="table-input" aria-label="${esc(input.zone)} next 24 hour rainfall" type="number" min="0" max="1000" data-zone="${esc(input.zone)}" data-field="rain_1d" value="${input.rain_1d}" /></td>
      <td><input class="table-input" aria-label="${esc(input.zone)} three day rainfall" type="number" min="0" max="2000" data-zone="${esc(input.zone)}" data-field="rain_3d" value="${input.rain_3d}" /></td>
      <td>${result ? percent(result.model_probability) : '<span class="muted-value">—</span>'}</td>
      <td>${result ? `${result.forecast_percentile.toFixed(1)}th` : '<span class="muted-value">—</span>'}</td>
      <td>${result ? `<div class="inline-priority"><span>${result.priority_score.toFixed(1)}</span><i><b style="width:${Math.max(0, Math.min(100, result.priority_score))}%"></b></i></div>` : '<span class="muted-value">—</span>'}</td>
      <td>${result ? `<b class="text-orange">${result.recommended_resources}</b>` : '<span class="muted-value">—</span>'}</td></tr>`;
  }).join("");
  const sorted = [...state.zoneResults].sort((a, b) => b.priority_score - a.priority_score);
  return `<section class="content-section">
    ${sectionHeader("02", "PEOPLE-FIRST PRIORITY", "Population exposure", `${state.zoneInputs.length} Chennai zones`)}
    <div class="imd-inline-links">${state.bootstrap.imd_products.map((item) => `<a href="${item.url}" target="_blank" rel="noreferrer">${esc(item.label)} ↗</a>`).join("")}</div>
    <form id="population-form"><div class="panel zone-panel">
      <div class="table-toolbar"><span class="panel-title">Zone rainfall scenarios</span><div class="toolbar-controls">
        <label class="compact-select"><span>Month</span><select name="month">${monthOptions(state.month)}</select></label>
        <label class="compact-select"><span>IMD warning</span><select name="warning">${["No warning", "Yellow", "Orange", "Red"].map((value) => `<option ${state.warning === value ? "selected" : ""}>${value}</option>`).join("")}</select></label>
        <label class="compact-select"><span>Crews available</span><input class="resource-input" name="resource_units" type="number" min="1" max="500" value="${state.resourceUnits}" /></label>
      </div></div>
      <div class="zone-table-wrap"><table class="data-table zone-table"><thead><tr><th>Zone</th><th>Residents</th><th>Children</th><th>Older residents</th><th>Next 24h <i>mm</i></th><th>Prior 3-day <i>mm</i></th><th>Model P</th><th>IMD QPF</th><th>Priority</th><th>Crews</th></tr></thead><tbody>${rows}</tbody></table></div>
      <div class="table-footer"><span>Priority = max(model probability, IMD QPF percentile, warning) × population vulnerability.</span><button class="primary-button compact-button" ${state.busy === "population" ? "disabled" : ""}>${state.busy === "population" ? "Updating…" : "Allocate crews"}<span>↗</span></button></div>
    </div></form>
    ${state.zoneResults.length ? `<div class="population-outcomes">
      <div class="outcome-card"><span class="outcome-label">MODEL-WEIGHTED RISK</span><b>${percent(state.populationWeightedProbability)}</b><span>Across all zones</span></div>
      <div class="outcome-card"><span class="outcome-label">HIGHEST PRIORITY</span><b class="text-orange">${esc(sorted[0]?.zone ?? "—")}</b><span>${num(sorted[0]?.population ?? 0)} residents</span></div>
      <div class="outcome-card"><span class="outcome-label">EXPECTED EXPOSURE</span><b>${num(state.zoneResults.reduce((sum, row) => sum + row.expected_heavy_rain_population, 0))}</b><span>Residents weighted by model probability</span></div>
       <div class="panel priority-chart"><div class="chart-heading"><span>Zone response priority</span><span class="chart-unit">${state.resourceUnits} crews distributed</span></div><div id="zone-priority-chart" class="plotly-chart"></div></div>
    </div>` : ""}
  </section>`;
}

function powerView() {
  const profile = state.powerProfile;
  if (!profile) return `<section class="content-section">${sectionHeader("03", "GENERATION NETWORK", "Power stations", "Tamil Nadu")}<div class="panel empty-panel">Loading station data…</div></section>`;
  const rows = profile.stations.slice(0, 30).map((station) => `<tr><td class="zone-name">${esc(station.station)}</td><td>${esc(station.sector)}</td><td>${num(station.capacity_mw, 1)}</td><td>${num(station.previous_actual_ytd, 1)}</td><td>${num(station.actual_ytd, 1)}</td><td class="${station.generation_change_pct < 0 ? "muted-value" : "text-orange"}">${station.generation_change_pct == null ? "—" : `${station.generation_change_pct.toFixed(1)}%`}</td></tr>`).join("");
  return `<section class="content-section">
    ${sectionHeader("03", "GENERATION NETWORK", "Power stations", "Tamil Nadu")}
    <div class="model-strip"><span class="model-strip-title">● GENERATION PROFILE</span><span>${esc(profile.period)}</span><span>54 monitored stations</span></div>
    <div class="chart-grid two-col station-charts">
      <div class="chart-card"><div class="chart-heading"><span>Generation by ownership sector</span><span class="chart-unit">Dataset units</span></div><div id="sector-generation-chart" class="plotly-chart"></div></div>
      <div class="chart-card"><div class="chart-heading"><span>Station output change</span><span class="chart-unit">Prior-year comparison</span></div><div id="station-change-chart" class="plotly-chart"></div></div>
    </div>
    <div class="panel station-table-panel"><div class="chart-heading"><span>Station output and capacity</span><span class="chart-unit">Top 30 by current output</span></div><div class="zone-table-wrap"><table class="data-table"><thead><tr><th>Station</th><th>Sector</th><th>Capacity MW</th><th>Prior output</th><th>Current output</th><th>Change</th></tr></thead><tbody>${rows}</tbody></table></div></div>
    <div class="model-footnote">No feeder-to-zone or outage map is available; station data is operational context, not an outage-risk prediction.</div>
  </section>`;
}

function monthOptions(value = state.month) {
  return MONTHS.map((name, index) => `<option value="${index + 1}" ${value === index + 1 ? "selected" : ""}>${name}</option>`).join("");
}

function render() {
  const body = state.section === "Forecast" ? forecastView() : state.section === "Population" ? populationView() : powerView();
  const nav = ["Forecast", "Population", "Power Stations"].map((tab, index) => `<button class="nav-tab ${state.section === tab ? "active" : ""}" data-tab="${tab}"><span class="nav-index">0${index + 1}</span>${tab}${state.section === tab ? '<span class="nav-active-mark"></span>' : ""}</button>`).join("");
  document.querySelector("#app").innerHTML = `<main class="app-shell">
    <div class="topline"><div class="brand"><span class="brand-mark">ϟ</span><span>CHENNAI <b>/</b> POWER RESILIENCE</span></div><nav class="section-nav" aria-label="Dashboard sections">${nav}</nav></div>
    <header class="hero"><div class="hero-copy"><h1>The Chennai Rainfall<br /><em>Power Resilience Platform</em></h1></div></header>
    ${state.error ? `<div class="error-banner">! <span>${esc(state.error)}</span></div>` : ""}
    ${body}
    <footer class="app-footer"><span>CHENNAI POWER RESILIENCE</span><span>Decision support · not outage prediction</span><span class="footer-pip"></span></footer>
  </main>`;
  if (state.section === "Forecast" && state.bootstrap) drawForecastCharts();
  if (state.section === "Population") drawPopulationChart();
  if (state.section === "Power Stations") drawPowerCharts();
}

async function run(action, callback) {
  state.error = "";
  state.busy = action;
  render();
  try { await callback(); }
  catch (error) { state.error = error.message ?? "Request failed"; }
  state.busy = "";
  render();
}

document.addEventListener("click", (event) => {
  const tab = event.target.closest("[data-tab]");
  if (tab) { state.section = tab.dataset.tab; render(); return; }
});

document.addEventListener("input", (event) => {
  const target = event.target;
  if (target.matches("#forecast-form [name=rain1]")) state.rain1 = Number(target.value);
  if (target.matches("#forecast-form [name=rain3]")) state.rain3 = Number(target.value);
  if (target.matches("[name=resource_units]")) state.resourceUnits = Math.max(1, Number(target.value));
  if (target.matches("[data-zone][data-field]")) {
    const zone = state.zoneInputs.find((row) => row.zone === target.dataset.zone);
    if (zone) zone[target.dataset.field] = Number(target.value);
  }
});

document.addEventListener("change", (event) => {
  const target = event.target;
  if (target.matches("[name=month]")) state.month = Number(target.value);
  if (target.matches("[name=warning]")) state.warning = target.value;
});

document.addEventListener("submit", async (event) => {
  if (event.target.id === "forecast-form") {
    event.preventDefault();
    state.rain1 = Number(event.target.elements.rain1.value);
    state.rain3 = Number(event.target.elements.rain3.value);
    state.month = Number(event.target.elements.month.value);
    await run("forecast", async () => {
      state.forecast = await api("/api/forecast", { rain_1d: state.rain1, rain_3d: state.rain3, month: state.month });
    });
  }
  if (event.target.id === "population-form") {
    event.preventDefault();
    state.month = Number(event.target.elements.month.value);
    state.warning = event.target.elements.warning.value;
    state.resourceUnits = Number(event.target.elements.resource_units.value);
    await run("population", async () => {
      const result = await api("/api/population-priority", payload());
      state.zoneResults = result.zones;
      state.populationWeightedProbability = result.population_weighted_probability;
    });
  }
});

function payload() {
  return { month: state.month, warning: state.warning, resource_units: state.resourceUnits, zones: state.zoneInputs };
}

async function init() {
  try {
    [state.bootstrap, state.powerProfile] = await Promise.all([api("/api/bootstrap"), api("/api/power-stations")]);
    state.zoneInputs = state.bootstrap.zones.map((zone) => ({ zone: zone.name, rain_1d: 0, rain_3d: 0 }));
  } catch (error) {
    state.error = `API unavailable. Start FastAPI, then reload. ${error.message ?? ""}`;
  }
  if (state.bootstrap) render();
  else document.querySelector("#app").innerHTML = `<main class="app-shell"><div class="error-banner">${esc(state.error)}</div></main>`;
}

init();
