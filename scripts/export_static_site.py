"""Build the GitHub Pages site: a static copy of ``web/`` plus precomputed JSON.

GitHub Pages cannot run the FastAPI service, so this script:

* reuses the real Python models (``web_api.RAIN_MODEL`` / ``RECOMMENDER``) and the
  existing endpoint functions to emit exactly the payloads the frontend expects;
* exports the fitted distribution parameters, wet-day climatology, and logistic
  coefficients so ``web/static-api.js`` can reproduce ``/api/forecast`` and
  ``/api/population-priority`` in the browser;
* copies ``web/`` into ``_site/`` and injects the static API shim.

Usage::

    python scripts/export_static_site.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drainage_rec.web_api import (  # noqa: E402  (path setup must run first)
    RAIN_MODEL,
    RECOMMENDER,
    bootstrap,
    power_stations,
)

WEB_DIR = ROOT / "web"
OUT_DIR = ROOT / "_site"
SHIM = '<script src="./static-api.js"></script>\n  '


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        # allow_nan=False keeps the output valid JSON for JSON.parse.
        json.dump(payload, handle, separators=(",", ":"), allow_nan=False)


def static_model() -> dict:
    """Everything the browser needs to evaluate the Python models."""
    model = RECOMMENDER.model
    return {
        "wet_day_mm": model.wet_day_mm,
        "tiers": model.tiers,
        "fits": {
            key: {"dist": fit.dist, "params": [float(p) for p in fit.params]}
            for key, fit in model.fits.items()
        },
        # Sorted so the client can binary-search, matching EmpiricalCDF.
        "wet_samples": {
            key: sorted(float(v) for v in values)
            for key, values in model.wet_samples.items()
        },
        "logistic": {
            "mean": [float(v) for v in RAIN_MODEL.mean],
            "scale": [float(v) for v in RAIN_MODEL.scale],
            "coefficients": [float(v) for v in RAIN_MODEL.coefficients],
            "heavy_rain_threshold_mm": float(RAIN_MODEL.heavy_rain_threshold_mm),
        },
    }


def build() -> Path:
    if OUT_DIR.exists():
        shutil.rmtree(OUT_DIR)
    shutil.copytree(WEB_DIR, OUT_DIR)
    (OUT_DIR / ".nojekyll").write_text("", encoding="utf-8")

    _write_json(OUT_DIR / "data" / "bootstrap.json", bootstrap())
    _write_json(OUT_DIR / "data" / "power-stations.json", power_stations())
    _write_json(OUT_DIR / "data" / "static-model.json", static_model())

    index = (OUT_DIR / "index.html").read_text(encoding="utf-8")
    anchor = '<script src="./app.js'
    if anchor not in index:
        raise SystemExit("index.html is missing the app.js script tag")
    index = index.replace(anchor, SHIM + anchor, 1)
    (OUT_DIR / "index.html").write_text(index, encoding="utf-8")
    return OUT_DIR


if __name__ == "__main__":
    site = build()
    files = sorted(p.relative_to(site).as_posix() for p in site.rglob("*") if p.is_file())
    total = sum((site / name).stat().st_size for name in files)
    print(f"built {site} ({len(files)} files, {total / 1024:.0f} KiB)")
