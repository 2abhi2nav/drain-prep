"""Regularized logistic model for historical heavy-rainfall probability."""

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.special import expit
from scipy.stats import rankdata

from ..utils.io import read_city_series

FEATURES = ["log_1d_rain", "log_3d_rain", "month_sin", "month_cos"]
HEAVY_RAIN_MM = 64.5
HOLDOUT_YEAR = 2015


def _feature_matrix(rain_1d, rain_3d, month) -> np.ndarray:
    r1, r3, m = np.broadcast_arrays(rain_1d, rain_3d, month)
    angle = 2 * np.pi * (m.astype(float) - 1) / 12
    return np.column_stack((np.log1p(r1.ravel()), np.log1p(r3.ravel()), np.sin(angle).ravel(), np.cos(angle).ravel()))


def _auc(y: np.ndarray, probability: np.ndarray) -> float:
    ranks = rankdata(probability)
    positive = y == 1
    n_pos, n_neg = positive.sum(), (~positive).sum()
    if not n_pos or not n_neg:
        return float("nan")
    return float((ranks[positive].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg))


@dataclass
class HeavyRainLogisticModel:
    mean: np.ndarray
    scale: np.ndarray
    coefficients: np.ndarray
    metrics: dict
    test_data: pd.DataFrame

    def predict_probability(self, rain_1d, rain_3d, month) -> np.ndarray:
        x = (_feature_matrix(rain_1d, rain_3d, month) - self.mean) / self.scale
        return expit(self.coefficients[0] + x @ self.coefficients[1:])


def fit_heavy_rain_model(daily: pd.Series | None = None) -> HeavyRainLogisticModel:
    """Fit on pre-2015 observations and evaluate chronologically on 2015 onward."""
    daily = read_city_series() if daily is None else daily.sort_index()
    frame = pd.DataFrame({"rain_1d": daily, "rain_3d": daily.rolling(3, min_periods=1).sum()})
    frame["month"] = frame.index.month
    frame["heavy_rain"] = (frame["rain_1d"] >= HEAVY_RAIN_MM).astype(int)
    x = _feature_matrix(frame["rain_1d"].to_numpy(), frame["rain_3d"].to_numpy(), frame["month"].to_numpy())
    y = frame["heavy_rain"].to_numpy(dtype=float)
    train = frame.index.year < HOLDOUT_YEAR
    x_train, y_train = x[train], y[train]
    x_test, y_test = x[~train], y[~train].astype(int)
    mean = x_train.mean(axis=0)
    scale = x_train.std(axis=0)
    scale[scale == 0] = 1
    x_train = (x_train - mean) / scale
    x_test_scaled = (x_test - mean) / scale
    design = np.column_stack((np.ones(len(x_train)), x_train))

    def objective(beta):
        logits = design @ beta
        return np.mean(np.logaddexp(0, logits) - y_train * logits) + 0.005 * np.dot(beta[1:], beta[1:]) / 2

    result = minimize(objective, np.zeros(design.shape[1]), method="L-BFGS-B")
    if not result.success:
        raise RuntimeError(f"Heavy-rain logistic fit failed: {result.message}")
    beta = result.x
    probabilities = expit(beta[0] + x_test_scaled @ beta[1:])
    predicted = probabilities >= 0.5
    tn = int(((~predicted) & (y_test == 0)).sum())
    fp = int((predicted & (y_test == 0)).sum())
    fn = int(((~predicted) & (y_test == 1)).sum())
    tp = int((predicted & (y_test == 1)).sum())
    test = frame.loc[~train, ["rain_1d", "rain_3d", "heavy_rain"]].copy()
    test["probability"] = probabilities
    calibration = []
    for indices in np.array_split(np.argsort(probabilities), 10):
        if len(indices):
            calibration.append({
                "predicted": float(probabilities[indices].mean()),
                "observed": float(y_test[indices].mean()),
                "n": len(indices),
            })
    order = np.argsort(-probabilities)
    sorted_y = y_test[order]
    tpr = np.r_[0, np.cumsum(sorted_y) / max(1, (y_test == 1).sum())]
    fpr = np.r_[0, np.cumsum(1 - sorted_y) / max(1, (y_test == 0).sum())]
    precision_curve = np.cumsum(sorted_y) / np.arange(1, len(sorted_y) + 1)
    recall_curve = np.cumsum(sorted_y) / max(1, (y_test == 1).sum())
    average_precision = float(np.sum(np.diff(np.r_[0, recall_curve]) * precision_curve))
    metrics = {
        "auc": _auc(y_test, probabilities),
        "average_precision": average_precision,
        "brier": float(np.mean((probabilities - y_test) ** 2)),
        "accuracy": float((tp + tn) / len(y_test)),
        "precision": float(tp / (tp + fp)) if tp + fp else 0.0,
        "recall": float(tp / (tp + fn)) if tp + fn else 0.0,
        "confusion": np.array([[tn, fp], [fn, tp]]),
        "calibration": pd.DataFrame(calibration),
        "roc": pd.DataFrame({"false_positive_rate": fpr, "true_positive_rate": tpr}),
        "precision_recall": pd.DataFrame({"recall": recall_curve, "precision": precision_curve}),
        "coefficients": pd.Series(beta[1:], index=FEATURES),
        "test_start": str(test.index.min().date()),
        "test_end": str(test.index.max().date()),
    }
    return HeavyRainLogisticModel(mean, scale, beta, metrics, test)
