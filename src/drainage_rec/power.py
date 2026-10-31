"""Population and power-station prioritization indicators for the Chennai PoC."""

from pathlib import Path

import numpy as np
import pandas as pd

from .utils.config import DATA_DIR

DEMOGRAPHICS_PATH = DATA_DIR / "additional" / "Demographic_Profile_Chennai2011.csv"
POWER_DATA_PATH = DATA_DIR / "additional" / "Sector_Wise_Power_National2024.csv"
POPULATION_COL = "Total Population (in thousands)"
CHILDREN_COL = "population - children aged 0-14 (in thousands)"
YOUTH_COL = "Population - youth aged 15-24 (in thousands)"
ADULTS_COL = "Population - adults aged 25-60 (in thousands)"
SENIORS_COL = "Population - Senior citizens aged 60+ (in thousands)"


def load_zone_demographics(path: Path = DEMOGRAPHICS_PATH) -> pd.DataFrame:
    """Aggregate the supplied ward demographics to its named zones."""
    wards = pd.read_csv(path)
    groups = wards.groupby("Zone Name", as_index=False).agg(
        population=(POPULATION_COL, "sum"),
        children=(CHILDREN_COL, "sum"),
        youth=(YOUTH_COL, "sum"),
        adults=(ADULTS_COL, "sum"),
        seniors=(SENIORS_COL, "sum"),
        wards=("Ward No.", "count"),
    )
    return groups


def _scale_01(values: pd.Series) -> pd.Series:
    low, high = values.min(), values.max()
    if high == low:
        return pd.Series(1.0, index=values.index)
    return (values - low) / (high - low)


def score_power_preparedness(zones: pd.DataFrame, probabilities, warning: str,
                             forecast_percentiles=None) -> pd.DataFrame:
    """Rank zones by next-day model risk, IMD rainfall signal, and population exposure."""
    warning_severity = {"No warning": 0.0, "Yellow": 0.35, "Orange": 0.7, "Red": 1.0}
    out = zones.copy()
    out["model_probability"] = np.asarray(probabilities, dtype=float)
    out["forecast_percentile"] = (
        np.asarray(forecast_percentiles, dtype=float) if forecast_percentiles is not None else 0.0
    )
    out["forecast_severity"] = (
        out["forecast_percentile"] / 100
    )
    out["risk_index"] = np.maximum.reduce((
        out["model_probability"].to_numpy(),
        np.broadcast_to(out["forecast_severity"], len(out)),
        np.full(len(out), warning_severity[warning]),
    ))
    out["weighted_exposure"] = out["population"] + 0.5 * out["children"] + 1.5 * out["seniors"]
    out["population_component"] = _scale_01(out["population"])
    # Per-capita weighting keeps vulnerable age composition influential beyond total population size.
    out["vulnerability_index"] = 0.5 * out["children"] / out["population"] + 1.5 * out["seniors"] / out["population"]
    out["vulnerability_component"] = _scale_01(out["vulnerability_index"])
    out["priority_score"] = 100 * out["risk_index"] * (
        0.65 * out["population_component"] + 0.35 * out["vulnerability_component"]
    )
    out["risk_level"] = np.where(
        (warning != "No warning") & (warning_severity[warning] >= np.maximum(out["model_probability"], out["forecast_severity"])),
        f"IMD {warning} warning",
        np.where(out["risk_index"] >= 0.5, "Elevated rainfall signal", "Lower rainfall signal"),
    )
    return out.sort_values("priority_score", ascending=False).reset_index(drop=True)


def allocate_resources(zones: pd.DataFrame, resource_units: int) -> pd.DataFrame:
    """Allocate a finite integer resource pool by zone priority using largest remainders."""
    out = zones.copy()
    weights = out["priority_score"].to_numpy(dtype=float)
    shares = weights / weights.sum() if weights.sum() else np.full(len(out), 1 / len(out))
    exact = shares * int(resource_units)
    allocation = np.floor(exact).astype(int)
    remaining = int(resource_units) - int(allocation.sum())
    if remaining:
        order = np.argsort(-(exact - allocation))
        allocation[order[:remaining]] += 1
    out["resource_share_pct"] = shares * 100
    out["recommended_resources"] = allocation
    return out


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def load_station_profiles(path: Path = POWER_DATA_PATH) -> pd.DataFrame:
    """Load observed Tamil Nadu generating-station capacity and output comparisons."""
    raw = pd.read_csv(path)
    stations = raw[
        raw["State"].astype(str).str.strip().eq("Tamil Nadu")
        & raw["Stations"].isna()
    ].copy()

    actual_col = "April` 2023 to January` 2024 - Actual - Col (9)"
    previous_actual_col = "April` 2023 to January` 2024 - Actual Same Month 2022-23 - Col (10)"
    capacity_col = "Monitored Capacity (MW) - Col (1)"
    stations["capacity_mw"] = _numeric(stations[capacity_col])
    stations["actual_ytd"] = _numeric(stations[actual_col]).fillna(0)
    stations["previous_actual_ytd"] = _numeric(stations[previous_actual_col]).fillna(0)
    stations = stations[stations["capacity_mw"].fillna(0) > 0].copy()
    stations["generation_change_pct"] = 100 * (
        stations["actual_ytd"] - stations["previous_actual_ytd"]
    ) / stations["previous_actual_ytd"].where(stations["previous_actual_ytd"] > 0)
    stations = stations.rename(columns={
        "Category": "station",
        "Sector Category": "sector",
        "Stations": "fuel_type",
        "Plant Load Factor (%) - January` 2024 - Actual - Col (14)": "january_plf_pct",
    })
    return stations.sort_values("actual_ytd", ascending=False).reset_index(drop=True)
