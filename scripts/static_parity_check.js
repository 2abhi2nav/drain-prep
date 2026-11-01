/*
 * Compare web/static-api.js against Python reference payloads.
 *
 * Run through scripts/check_static_parity.py, which writes the reference file:
 *   node scripts/static_parity_check.js <reference.json>
 */
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const SITE_DATA = path.join(ROOT, "_site", "data");
const reference = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
const TOLERANCE = 1e-9;

const wrap = (payload, status = 200) => new Response(JSON.stringify(payload), {
  status,
  headers: { "Content-Type": "application/json" },
});

// Minimal browser surface for the shim: window.fetch reads the built JSON files.
global.document = { baseURI: "http://static.local/" };
global.window = {
  location: { href: "http://static.local/", origin: "http://static.local" },
  fetch: async (url) => {
    const name = path.basename(new URL(typeof url === "string" ? url : url.url, document.baseURI).pathname);
    const file = path.join(SITE_DATA, name);
    if (!fs.existsSync(file)) return wrap({ detail: `missing ${name}` }, 404);
    return wrap(JSON.parse(fs.readFileSync(file, "utf8")));
  },
};
globalThis.fetch = global.window.fetch;

eval(fs.readFileSync(path.join(ROOT, "web", "static-api.js"), "utf8"));
const api = window.fetch;

const differences = [];
function compare(where, actual, expected) {
  if (typeof expected === "number") {
    if (typeof actual !== "number" || Math.abs(actual - expected) > TOLERANCE) {
      differences.push({ where, actual, expected });
    }
    return;
  }
  if (Array.isArray(expected)) {
    if (!Array.isArray(actual) || actual.length !== expected.length) {
      differences.push({ where, actual, expected });
      return;
    }
    expected.forEach((value, index) => compare(`${where}[${index}]`, actual[index], value));
    return;
  }
  if (expected && typeof expected === "object") {
    for (const key of Object.keys(expected)) compare(`${where}.${key}`, actual?.[key], expected[key]);
    return;
  }
  if (actual !== expected) differences.push({ where, actual, expected });
}

async function post(route, body) {
  const response = await api(`http://static.local${route}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: response.status, data: await response.json() };
}

(async () => {
  for (const [index, testCase] of reference.forecast.entries()) {
    const { status, data } = await post("/api/forecast", testCase.request);
    if (status !== 200) differences.push({ where: `forecast[${index}].status`, actual: status, expected: 200 });
    compare(`forecast[${index}]`, data, testCase.expected);
  }
  for (const [index, testCase] of reference.population.entries()) {
    const { status, data } = await post("/api/population-priority", testCase.request);
    if (status !== 200) differences.push({ where: `population[${index}].status`, actual: status, expected: 200 });
    compare(`population[${index}]`, data, testCase.expected);
  }

  const rejected = await post("/api/forecast", { rain_1d: -1, rain_3d: 10, month: 2 });
  if (rejected.status !== 422) differences.push({ where: "validation.status", actual: rejected.status, expected: 422 });

  const cases = reference.forecast.length + reference.population.length;
  if (differences.length) {
    console.error(JSON.stringify({ differences: differences.slice(0, 20), total: differences.length }, null, 1));
    process.exit(1);
  }
  console.log(`static API matches Python on ${cases} cases`);
})();
