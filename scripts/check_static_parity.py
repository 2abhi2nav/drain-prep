"""Check that web/static-api.js reproduces the Python API exactly.

Usage (after ``python scripts/export_static_site.py``)::

    python scripts/check_static_parity.py

Builds a small reference set with the real endpoint functions, then runs
``scripts/static_parity_check.js`` under Node against the built ``_site/``.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from drainage_rec.web_api import (  # noqa: E402
    RainfallRequest,
    ZoneRainfall,
    ZoneRequest,
    bootstrap,
    forecast,
    population_priority,
)


def _cases() -> dict:
    zones = [zone["name"] for zone in bootstrap()["zones"]]
    rain = [0, 12, 34.5, 64.5, 80, 119.9, 160, 199, 250, 420]
    forecast_requests = [
        {"rain_1d": 80, "rain_3d": 160, "month": 11},
        {"rain_1d": 120, "rain_3d": 250, "month": 11},
        {"rain_1d": 0, "rain_3d": 0, "month": 1},
        {"rain_1d": 250, "rain_3d": 100, "month": 7},
        {"rain_1d": 64.5, "rain_3d": 64.5, "month": 10},
    ]
    population_requests = [
        {
            "month": 11,
            "warning": "Orange",
            "resource_units": 24,
            "zones": [
                {"zone": name, "rain_1d": rain[i % len(rain)], "rain_3d": rain[(i * 3) % len(rain)]}
                for i, name in enumerate(zones)
            ],
        },
        {
            "month": 1,
            "warning": "No warning",
            "resource_units": 7,
            "zones": [{"zone": name, "rain_1d": 0, "rain_3d": 0} for name in zones],
        },
    ]
    return {
        "forecast": [
            {"request": request, "expected": forecast(RainfallRequest(**request))}
            for request in forecast_requests
        ],
        "population": [
            {
                "request": request,
                "expected": population_priority(
                    ZoneRequest(
                        month=request["month"],
                        warning=request["warning"],
                        resource_units=request["resource_units"],
                        zones=[ZoneRainfall(**row) for row in request["zones"]],
                    )
                ),
            }
            for request in population_requests
        ],
    }


def main() -> int:
    site = ROOT / "_site"
    if not site.is_dir():
        print("_site/ is missing; run scripts/export_static_site.py first", file=sys.stderr)
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        reference = Path(tmp) / "reference.json"
        reference.write_text(json.dumps(_cases()), encoding="utf-8")
        result = subprocess.run(
            ["node", str(ROOT / "scripts" / "static_parity_check.js"), str(reference)],
            cwd=ROOT,
            check=False,
        )
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
