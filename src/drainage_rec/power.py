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


def score_power_preparedness(zones: pd.DataFrame, probabilities, warning: str) -> pd.DataFrame:
    """Rank zones by logistic heavy-rain probability and normalized population components."""
    warning_severity = {"No warning": 0.0, "Yellow": 0.35, "Orange": 0.7, "Red": 1.0}
    out = zones.copy()
    out["model_probability"] = np.asarray(probabilities, dtype=float)
    out["effective_probability"] = np.maximum(out["model_probability"], warning_severity[warning])
    out["weighted_exposure"] = out["population"] + 0.5 * out["children"] + 1.5 * out["seniors"]
    out["population_component"] = _scale_01(out["population"])
    # Per-capita weighting keeps vulnerable age composition influential beyond total population size.
    out["vulnerability_index"] = 0.5 * out["children"] / out["population"] + 1.5 * out["seniors"] / out["population"]
    out["vulnerability_component"] = _scale_01(out["vulnerability_index"])
    out["priority_score"] = 100 * out["effective_probability"] * (
        0.65 * out["population_component"] + 0.35 * out["vulnerability_component"]
    )
    out["risk_level"] = np.where(
        warning_severity[warning] > out["model_probability"],
        f"IMD {warning} warning",
        np.where(out["model_probability"] >= 0.5, "Elevated model probability", "Lower model probability"),
    )
    return out.sort_values("priority_score", ascending=False).reset_index(drop=True)


def _numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series.astype(str).str.replace(",", "", regex=False), errors="coerce")


def load_station_priorities(demographics: pd.DataFrame | None = None,
                            zone_predictions: pd.DataFrame | None = None,
                            path: Path = POWER_DATA_PATH) -> pd.DataFrame:
    """Prepare Tamil Nadu station, prior-output, and rainfall-weighted population inputs."""
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

    zones = demographics if demographics is not None else load_zone_demographics()
    zones = zones.copy()
    zones["weighted_exposure"] = zones["population"] + 0.5 * zones["children"] + 1.5 * zones["seniors"]
    if zone_predictions is not None:
        zones = zones.merge(zone_predictions[["Zone Name", "effective_probability"]], on="Zone Name", how="left")
        zones["effective_probability"] = zones["effective_probability"].fillna(0)
    else:
        zones["effective_probability"] = 1.0
    expected_population = float((zones["population"] * zones["effective_probability"]).sum())
    expected_weighted_population = float((zones["weighted_exposure"] * zones["effective_probability"]).sum())
    previous_generation_share = stations["previous_actual_ytd"] / stations["previous_actual_ytd"].sum()
    stations["previous_generation_share"] = previous_generation_share
    stations["estimated_population_proxy"] = previous_generation_share * expected_population
    stations["weighted_prioritized_population"] = previous_generation_share * expected_weighted_population
    stations = stations.rename(columns={
        "Category": "station",
        "Sector Category": "sector",
        "Stations": "fuel_type",
        "Plant Load Factor (%) - January` 2024 - Actual - Col (14)": "january_plf_pct",
    })
    return stations.reset_index(drop=True)


def fit_station_generation_regression(stations: pd.DataFrame, seed: int = 42) -> tuple[pd.DataFrame, dict]:
    """Predict current generation, then propose resource shares from predicted station output."""
    feature_cols = ["capacity_mw", "previous_actual_ytd", "weighted_prioritized_population"]
    x = np.log1p(stations[feature_cols].clip(lower=0).to_numpy(dtype=float))
    y = stations["actual_ytd"].to_numpy(dtype=float)
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(stations))
    test_n = max(1, round(len(stations) * 0.2))
    test_idx, train_idx = order[:test_n], order[test_n:]
    mean, scale = x[train_idx].mean(axis=0), x[train_idx].std(axis=0)
    scale[scale == 0] = 1
    x_train = (x[train_idx] - mean) / scale
    x_test = (x[test_idx] - mean) / scale
    beta = np.linalg.lstsq(np.column_stack((np.ones(len(train_idx)), x_train)), y[train_idx], rcond=None)[0]
    test_prediction = np.maximum(0, beta[0] + x_test @ beta[1:])
    residual = y[test_idx] - test_prediction
    ss_total = np.sum((y[test_idx] - y[test_idx].mean()) ** 2)
    metrics = {
        "rmse": float(np.sqrt(np.mean(residual ** 2))),
        "mae": float(np.mean(np.abs(residual))),
        "r2": float(1 - np.sum(residual ** 2) / ss_total) if ss_total else float("nan"),
        "test_actual": y[test_idx],
        "test_predicted": test_prediction,
        "coefficients": pd.Series(beta[1:], index=feature_cols),
        "n_train": len(train_idx),
        "n_test": len(test_idx),
    }

    all_x = (x - mean) / scale
    out = stations.copy()
    out["predicted_actual_ytd"] = np.maximum(0, beta[0] + all_x @ beta[1:])
    total_predicted_generation = out["predicted_actual_ytd"].sum()
    out["predicted_generation_share"] = (
        out["predicted_actual_ytd"] / total_predicted_generation if total_predicted_generation else 0
    )
    expected_population = out["estimated_population_proxy"].sum()
    out["estimated_exposed_population"] = out["predicted_generation_share"] * expected_population
    out["relief_resource_share_pct"] = 100 * out["predicted_generation_share"]
    out["regression_priority_score"] = out["relief_resource_share_pct"]
    return out.sort_values("regression_priority_score", ascending=False).reset_index(drop=True), metrics
