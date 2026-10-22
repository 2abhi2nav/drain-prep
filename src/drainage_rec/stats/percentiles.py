"""Empirical percentile of a day's rainfall within the historical wet-day climatology."""

import numpy as np


class EmpiricalCDF:
    def __init__(self, sample):
        self.sorted = np.sort(np.asarray(sample, dtype=float))

    def percentile(self, value) -> np.ndarray:
        """Percentage of historical values strictly below ``value`` (0-100)."""
        if len(self.sorted) == 0:
            return np.full(np.shape(value), np.nan)
        return 100 * np.searchsorted(self.sorted, value, side="left") / len(self.sorted)

    def quantile(self, q):
        return np.quantile(self.sorted, np.asarray(q) / 100)


def percentile_table(sample, qs=(50, 75, 90, 95, 99, 99.9)) -> dict:
    x = np.asarray(sample, dtype=float)
    return {f"p{q:g}": float(np.quantile(x, q / 100)) for q in qs}


def mean_ci(sample, alpha: float = 0.05) -> tuple[float, float, float]:
    """Mean with a t-based confidence interval."""
    from scipy import stats

    x = np.asarray(sample, dtype=float)
    m = x.mean()
    half = stats.t.ppf(1 - alpha / 2, len(x) - 1) * x.std(ddof=1) / np.sqrt(len(x))
    return float(m), float(m - half), float(m + half)
