/*
 * Static API shim for the GitHub Pages build.
 *
 * GitHub Pages serves files only, so this script intercepts the frontend's
 * /api/* requests and reproduces the FastAPI endpoints in the browser using
 * precomputed JSON from scripts/export_static_site.py.
 *
 * It is only injected into the _site build; the Vercel deployment keeps the
 * real Python backend.
 */
(() => {
  "use strict";

  const nativeFetch = window.fetch.bind(window);
  const ENDPOINTS = new Set(["health", "bootstrap", "power-stations", "forecast", "population-priority"]);
  const WARNING_SEVERITY = { "No warning": 0, Yellow: 0.35, Orange: 0.7, Red: 1 };

  const cache = new Map();
  const load = (name) => {
    if (!cache.has(name)) {
      const url = new URL(`data/${name}.json`, document.baseURI).href;
      cache.set(name, nativeFetch(url).then((response) => {
        if (!response.ok) throw new Error(`Static data missing (${response.status}): ${url}`);
        return response.json();
      }).catch((error) => {
        cache.delete(name);
        throw error;
      }));
    }
    return cache.get(name);
  };

  const reply = (payload, status = 200) => new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  });
  const invalid = (detail) => reply({ detail }, 422);
  const finite = (value) => typeof value === "number" && Number.isFinite(value);

  /* ---------- rainfall statistics ---------- */

  // Percentage of historical wet days strictly below `value` (EmpiricalCDF).
  function percentile(sorted, value) {
    let low = 0;
    let high = sorted.length;
    while (low < high) {
      const mid = (low + high) >> 1;
      if (sorted[mid] < value) low = mid + 1;
      else high = mid;
    }
    return sorted.length ? (100 * low) / sorted.length : Number.NaN;
  }

  function distributionCdf(fit, value) {
    if (fit.dist === "gumbel") {
      const [loc, scale] = fit.params;
      return Math.exp(-Math.exp(-(value - loc) / scale));
    }
    // scipy.stats.genextreme, shape c = -xi: (c, loc, scale)
    const [shape, loc, scale] = fit.params;
    const t = 1 - shape * ((value - loc) / scale);
    if (t <= 0) return shape > 0 ? 1 : 0;
    return Math.exp(-Math.pow(t, 1 / shape));
  }

  function returnPeriod(fit, value) {
    const exceed = 1 - distributionCdf(fit, value);
    if (!(exceed > 0)) return Infinity;
    return 1 / Math.max(exceed, 1e-12);
  }

  function assess(model, rain1, rain3) {
    rain3 = Math.max(rain3, rain1); // a 3-day total cannot be below its last day
    const values = { rain_1d: rain1, rain_3d: rain3 };
    const detail = {};
    for (const key of Object.keys(values)) {
      detail[key] = {
        value_mm: values[key],
        percentile: percentile(model.wet_samples[key], values[key]),
        return_period: returnPeriod(model.fits[key], values[key]),
      };
    }
    let tierIndex = 0;
    model.tiers.forEach((rule, index) => {
      if (index === 0) return;
      let hit = false;
      if (rule.percentile != null) {
        hit = hit || Object.keys(detail).some((key) => detail[key].percentile >= rule.percentile);
      }
      if (rule.return_period != null) {
        hit = hit || Object.keys(detail).some((key) => detail[key].return_period >= rule.return_period);
      }
      // A dry day (both below the wet-day cut-off) never escalates.
      hit = hit && Object.keys(values).some((key) => values[key] >= model.wet_day_mm);
      if (hit) tierIndex = index;
    });
    // Python's max() keeps the first key on ties: rain_1d before rain_3d.
    let driver = "rain_1d";
    for (const key of ["rain_3d"]) {
      const candidate = detail[key];
      const best = detail[driver];
      if (candidate.return_period > best.return_period
        || (candidate.return_period === best.return_period && candidate.percentile > best.percentile)) {
        driver = key;
      }
    }
    return { tier: model.tiers[tierIndex].name, driver, ...detail };
  }

  const expit = (value) => (value >= 0
    ? 1 / (1 + Math.exp(-value))
    : Math.exp(value) / (1 + Math.exp(value)));

  function heavyRainProbability(logistic, rain3, month) {
    const angle = (2 * Math.PI * (month - 1)) / 12;
    const features = [Math.log1p(rain3), Math.sin(angle), Math.cos(angle)];
    let logit = logistic.coefficients[0];
    for (let i = 0; i < features.length; i += 1) {
      logit += ((features[i] - logistic.mean[i]) / logistic.scale[i]) * logistic.coefficients[i + 1];
    }
    return expit(logit);
  }

  /* ---------- population priority ---------- */

  function scale01(values) {
    const low = Math.min(...values);
    const high = Math.max(...values);
    if (high === low) return values.map(() => 1);
    return values.map((value) => (value - low) / (high - low));
  }

  function scoreZones(zones, probabilities, warning, forecastPercentiles) {
    const population = zones.map((zone) => zone.population);
    const vulnerability = zones.map((zone) => (
      0.5 * zone.children / zone.population + 1.5 * zone.seniors / zone.population
    ));
    const populationComponent = scale01(population);
    const vulnerabilityComponent = scale01(vulnerability);
    const severity = WARNING_SEVERITY[warning];
    return zones.map((zone, index) => {
      const forecastSeverity = forecastPercentiles[index] / 100;
      const riskIndex = Math.max(probabilities[index], forecastSeverity, severity);
      return {
        zone: zone.name,
        population: zone.population,
        children: zone.children,
        seniors: zone.seniors,
        model_probability: probabilities[index],
        forecast_percentile: forecastPercentiles[index],
        risk_index: riskIndex,
        priority_score: 100 * riskIndex * (0.65 * populationComponent[index] + 0.35 * vulnerabilityComponent[index]),
        risk_level: warning !== "No warning" && severity >= Math.max(probabilities[index], forecastSeverity)
          ? `IMD ${warning} warning`
          : riskIndex >= 0.5 ? "Elevated rainfall signal" : "Lower rainfall signal",
      };
    }).sort((a, b) => b.priority_score - a.priority_score);
  }

  function allocate(scored, units) {
    const weights = scored.map((zone) => zone.priority_score);
    const total = weights.reduce((sum, value) => sum + value, 0);
    const shares = total ? weights.map((value) => value / total) : weights.map(() => 1 / weights.length);
    const exact = shares.map((share) => share * units);
    const allocation = exact.map((value) => Math.floor(value));
    const remaining = units - allocation.reduce((sum, value) => sum + value, 0);
    exact
      .map((value, index) => ({ index, remainder: value - Math.floor(value) }))
      .sort((a, b) => b.remainder - a.remainder)
      .slice(0, Math.max(0, remaining))
      .forEach(({ index }) => { allocation[index] += 1; });
    return scored.map((zone, index) => ({
      ...zone,
      resource_share_pct: shares[index] * 100,
      recommended_resources: allocation[index],
    }));
  }

  async function populationPriority(body) {
    const [bootstrap, model] = await Promise.all([load("bootstrap"), load("static-model")]);
    const zones = bootstrap.zones;
    const names = new Set(zones.map((zone) => zone.name));
    if (!finite(body.month) || body.month < 1 || body.month > 12) return invalid("month must be 1-12");
    if (!(body.warning in WARNING_SEVERITY)) return invalid("unknown IMD warning level");
    if (!Number.isInteger(body.resource_units) || body.resource_units < 1 || body.resource_units > 500) {
      return invalid("resource_units must be an integer between 1 and 500");
    }
    const submitted = new Map((body.zones || []).map((row) => [row.zone, row]));
    const unknown = [...submitted.keys()].filter((name) => !names.has(name)).sort();
    if (unknown.length) return invalid(`Unknown Chennai zone(s): ${unknown.join(", ")}`);
    const missing = zones.map((zone) => zone.name).filter((name) => !submitted.has(name)).sort();
    if (missing.length) return invalid(`Rainfall inputs required for all zones: ${missing.join(", ")}`);
    for (const row of submitted.values()) {
      if (!finite(row.rain_1d) || row.rain_1d < 0 || row.rain_1d > 1000) return invalid(`rain_1d out of range for ${row.zone}`);
      if (!finite(row.rain_3d) || row.rain_3d < 0 || row.rain_3d > 2000) return invalid(`rain_3d out of range for ${row.zone}`);
    }

    const inputs = zones.map((zone) => submitted.get(zone.name));
    const probabilities = inputs.map((row) => heavyRainProbability(model.logistic, row.rain_3d, body.month));
    const qpf = inputs.map((row) => percentile(model.wet_samples.rain_1d, row.rain_1d));
    const scored = allocate(scoreZones(zones, probabilities, body.warning, qpf), body.resource_units);

    const results = scored.map((zone) => {
      const input = submitted.get(zone.zone);
      return {
        zone: zone.zone,
        rain_1d: input.rain_1d,
        rain_3d: Math.max(input.rain_3d, input.rain_1d),
        model_probability: zone.model_probability,
        forecast_percentile: zone.forecast_percentile,
        risk_index: zone.risk_index,
        population: zone.population,
        children: zone.children,
        seniors: zone.seniors,
        priority_score: zone.priority_score,
        risk_level: zone.risk_level,
        expected_heavy_rain_population: zone.population * zone.model_probability,
        resource_share_pct: zone.resource_share_pct,
        recommended_resources: zone.recommended_resources,
      };
    });

    const totalPopulation = scored.reduce((sum, zone) => sum + zone.population, 0);
    return reply({
      zones: results,
      population_weighted_probability: scored.reduce(
        (sum, zone) => sum + zone.model_probability * zone.population, 0,
      ) / totalPopulation,
    });
  }

  /* ---------- request routing ---------- */

  async function route(pathname, method, body) {
    const name = pathname.match(/\/api\/([a-z-]+)$/)?.[1];
    if (!ENDPOINTS.has(name)) return null;
    if (name === "health" && method === "GET") return reply({ status: "ok" });
    if (name === "bootstrap" && method === "GET") return reply(await load("bootstrap"));
    if (name === "power-stations" && method === "GET") return reply(await load("power-stations"));
    if (name === "forecast" && method === "POST") {
      if (!finite(body.rain_1d) || body.rain_1d < 0 || body.rain_1d > 1000) return invalid("rain_1d out of range");
      if (!finite(body.rain_3d) || body.rain_3d < 0 || body.rain_3d > 2000) return invalid("rain_3d out of range");
      if (!finite(body.month) || body.month < 1 || body.month > 12) return invalid("month must be 1-12");
      const model = await load("static-model");
      return reply({
        assessment: assess(model, body.rain_1d, body.rain_3d),
        heavy_rain_probability: heavyRainProbability(model.logistic, body.rain_3d, body.month),
        forecast_percentile: percentile(model.wet_samples.rain_1d, body.rain_1d),
      });
    }
    if (name === "population-priority" && method === "POST") return populationPriority(body);
    return reply({ detail: `Method ${method} not allowed for /api/${name}` }, 405);
  }

  window.fetch = async (input, init = {}) => {
    const raw = typeof input === "string" ? input : input instanceof Request ? input.url : String(input);
    let url;
    try {
      url = new URL(raw, window.location.href);
    } catch {
      return nativeFetch(input, init);
    }
    const name = url.pathname.match(/\/api\/([a-z-]+)$/)?.[1];
    if (!ENDPOINTS.has(name)) return nativeFetch(input, init);

    const method = (init.method || (input instanceof Request ? input.method : "GET")).toUpperCase();
    let body = {};
    if (method === "POST") {
      try {
        const source = init.body ?? (input instanceof Request ? await input.clone().text() : null);
        body = typeof source === "string" ? JSON.parse(source) : {};
      } catch {
        return invalid("Malformed JSON body");
      }
    }
    try {
      const response = await route(url.pathname, method, body);
      return response ?? nativeFetch(input, init);
    } catch (error) {
      return reply({ detail: error.message ?? "Static API error" }, 500);
    }
  };
})();
