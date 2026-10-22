"""Frequency of extreme-rainfall days over the historical record."""

import numpy as np
import pandas as pd
from scipy import stats

HEAVY_THRESHOLDS = {"heavy_64_5": 64.5, "very_heavy_115_6": 115.6, "extreme_204_5": 204.5}


def exceedance_counts(daily: pd.Series, thresholds: dict = HEAVY_THRESHOLDS) -> pd.DataFrame:
    """Number of days per year at or above each threshold."""
    return pd.DataFrame(
        {name: (daily >= t).groupby(daily.index.year).sum() for name, t in thresholds.items()}
    ).rename_axis("year")


def poisson_rate_ci(counts: pd.Series, alpha: float = 0.05) -> dict:
    """Mean events/year with an exact (Garwood) Poisson confidence interval."""
    total, n = int(counts.sum()), len(counts)
    lo = stats.chi2.ppf(alpha / 2, 2 * total) / 2 if total > 0 else 0.0
    hi = stats.chi2.ppf(1 - alpha / 2, 2 * (total + 1)) / 2
    return {"rate_per_year": total / n, "ci_lower": lo / n, "ci_upper": hi / n, "years": n}


def decadal_frequency(counts: pd.DataFrame) -> pd.DataFrame:
    dec = (counts.index // 10) * 10
    return counts.groupby(dec).mean().rename_axis("decade")


def frequency_summary(daily: pd.Series) -> pd.DataFrame:
    counts = exceedance_counts(daily)
    return pd.DataFrame({c: poisson_rate_ci(counts[c]) for c in counts}).T


def monthly_climatology(daily: pd.Series) -> pd.DataFrame:
    """Mean monthly total and share of annual rainfall."""
    monthly = daily.resample("MS").sum()
    clim = monthly.groupby(monthly.index.month).agg(["mean", "std"])
    clim["share"] = clim["mean"] / clim["mean"].sum()
    clim.index.name = "month"
    return clim


def empirical_exceedance(annual_max: pd.Series) -> pd.DataFrame:
    """Weibull plotting positions for a return-level plot."""
    x = np.sort(annual_max.to_numpy())[::-1]
    rank = np.arange(1, len(x) + 1)
    return pd.DataFrame({"value": x, "return_period": (len(x) + 1) / rank})
