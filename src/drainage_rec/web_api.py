"""JSON API exposing the existing rainfall and power-priority models."""

from typing import Literal
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from pydantic import BaseModel, Field
from fastapi.staticfiles import StaticFiles
from plotly.offline import get_plotlyjs

from drainage_rec.power import (
    allocate_resources,
    load_zone_demographics,
    load_station_profiles,
    score_power_preparedness,
)
from drainage_rec.recommend import Recommender
from drainage_rec.stats.predictive import fit_heavy_rain_model

app = FastAPI(title="Chennai Power Preparedness API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

RECOMMENDER = Recommender.load()
RAIN_MODEL = fit_heavy_rain_model()
ZONES = load_zone_demographics()
ZONE_NAMES = set(ZONES["Zone Name"])
IMD_PRODUCTS = [
    {"label": "Chennai 7-day forecast", "url": "https://mausam.imd.gov.in/chennai/mcdata/chn_fcst_mng.pdf"},
    {"label": "24-hour district rainfall forecast", "url": "https://mausam.imd.gov.in/chennai/mcdata/distfcst.pdf"},
    {"label": "Chennai district warnings / nowcast", "url": "https://mausam.imd.gov.in/imd_latest/contents/districtwisewarnings_mc.php?id=26"},
    {"label": "7-day regional forecast and warnings", "url": "https://mausam.imd.gov.in/chennai/mcdata/chennaiinf.pdf"},
]


class RainfallRequest(BaseModel):
    rain_1d: float = Field(ge=0, le=1000)
    rain_3d: float = Field(ge=0, le=2000)
    month: int = Field(ge=1, le=12)


class ZoneRainfall(BaseModel):
    zone: str
    rain_1d: float = Field(ge=0, le=1000)
    rain_3d: float = Field(ge=0, le=2000)


class ZoneRequest(BaseModel):
    month: int = Field(ge=1, le=12)
    warning: Literal["No warning", "Yellow", "Orange", "Red"] = "No warning"
    resource_units: int = Field(default=10, ge=1, le=500)
    zones: list[ZoneRainfall]


def _zone_analysis(request: ZoneRequest):
    submitted = {row.zone: row for row in request.zones}
    unknown = set(submitted) - ZONE_NAMES
    if unknown:
        raise HTTPException(422, f"Unknown Chennai zone(s): {', '.join(sorted(unknown))}")
    missing = ZONE_NAMES - set(submitted)
    if missing:
        raise HTTPException(422, f"Rainfall inputs required for all zones: {', '.join(sorted(missing))}")

    inputs = [submitted[name] for name in ZONES["Zone Name"]]
    rainfall_1d = np.array([row.rain_1d for row in inputs], dtype=float)
    rainfall_3d = np.array([row.rain_3d for row in inputs], dtype=float)
    probability = RAIN_MODEL.predict_probability(rainfall_3d, np.full(len(inputs), request.month))
    qpf_percentile = np.asarray(RECOMMENDER.model.percentile("rain_1d", rainfall_1d), dtype=float)
    scored = score_power_preparedness(ZONES, probability, request.warning, qpf_percentile)
    by_name = {row.zone: row for row in inputs}
    scored["rain_1d"] = scored["Zone Name"].map(lambda name: by_name[name].rain_1d)
    scored["rain_3d"] = scored["Zone Name"].map(lambda name: max(by_name[name].rain_3d, by_name[name].rain_1d))
    scored["expected_heavy_rain_population"] = scored["population"] * scored["model_probability"]
    return scored


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/bootstrap")
def bootstrap():
    metrics = RAIN_MODEL.metrics
    return {
        "zones": ZONES[["Zone Name", "population", "children", "seniors"]].rename(
            columns={"Zone Name": "name"},
        ).to_dict("records"),
        "imd_products": IMD_PRODUCTS,
        "forecast_model": {
            "target": "Next-day heavy rain: at least 64.5 mm in 24 hours",
            "features": ["previous 3-day rainfall", "seasonal month"],
            "train_period": "1901–2014",
            "holdout_period": [metrics["test_start"], metrics["test_end"]],
            "metrics": {key: metrics[key] for key in ("auc", "average_precision", "brier", "precision", "recall")},
            "confusion": metrics["confusion"].tolist(),
            "roc": metrics["roc"].to_dict("records"),
            "precision_recall": metrics["precision_recall"].to_dict("records"),
            "calibration": metrics["calibration"].to_dict("records"),
            "coefficients": [{"feature": key, "value": float(value)}
                             for key, value in metrics["coefficients"].items()],
        },
    }


@app.post("/api/forecast")
def forecast(request: RainfallRequest):
    assessment = RECOMMENDER.model.assess(request.rain_1d, request.rain_1d)
    probability = float(RAIN_MODEL.predict_probability(request.rain_3d, request.month)[0])
    forecast_percentile = float(RECOMMENDER.model.percentile("rain_1d", request.rain_1d))
    return {
        "assessment": assessment,
        "heavy_rain_probability": probability,
        "forecast_percentile": forecast_percentile,
    }


@app.post("/api/population-priority")
def population_priority(request: ZoneRequest):
    scored = _zone_analysis(request)
    scored = allocate_resources(scored, request.resource_units)
    return {
        "zones": scored[[
            "Zone Name", "rain_1d", "rain_3d", "model_probability", "forecast_percentile", "risk_index",
            "population", "children", "seniors", "priority_score", "risk_level", "expected_heavy_rain_population",
            "resource_share_pct", "recommended_resources",
        ]].rename(columns={"Zone Name": "zone"}).to_dict("records"),
        "population_weighted_probability": float(np.average(
            scored["model_probability"], weights=scored["population"],
        )),
    }


@app.get("/api/power-stations")
def power_stations():
    stations = load_station_profiles()
    sector = stations.groupby("sector", as_index=False).agg(
        capacity_mw=("capacity_mw", "sum"),
        actual_ytd=("actual_ytd", "sum"),
        previous_actual_ytd=("previous_actual_ytd", "sum"),
    )
    station_rows = stations[["station", "sector", "capacity_mw", "actual_ytd", "previous_actual_ytd", "generation_change_pct"]]
    return {
        "stations": station_rows.astype(object).where(station_rows.notna(), None).to_dict("records"),
        "sectors": sector.to_dict("records"),
        "period": "April 2023–January 2024 vs prior-year period",
    }


@app.get("/plotly.js")
def plotly_bundle():
    return Response(get_plotlyjs(), media_type="application/javascript")


WEB_DIR = Path(__file__).resolve().parents[2] / "web"
app.mount("/", StaticFiles(directory=WEB_DIR, html=True), name="web")
