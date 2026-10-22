"""Return levels, return periods, and bootstrap confidence intervals."""

import numpy as np
import pandas as pd

from .distributions import Fit, fit

DEFAULT_PERIODS = (2, 5, 10, 25, 50, 100)


def return_level(f: Fit, period) -> np.ndarray:
    """Rainfall exceeded on average once every ``period`` years."""
    return f.ppf(1 - 1 / np.asarray(period, dtype=float))


def return_period(f: Fit, value) -> np.ndarray:
    """Average recurrence interval (years) of an annual maximum >= value."""
    exceed = 1 - f.cdf(np.asarray(value, dtype=float))
    with np.errstate(divide="ignore"):
        return np.where(exceed > 0, 1 / np.clip(exceed, 1e-12, None), np.inf)


def bootstrap_return_levels(
    sample, dist: str, periods=DEFAULT_PERIODS, n_boot: int = 500, alpha: float = 0.05, seed: int = 0
) -> pd.DataFrame:
    """Return levels with nonparametric bootstrap (percentile) confidence intervals."""
    x = np.asarray(sample, dtype=float)
    rng = np.random.default_rng(seed)
    base = return_level(fit(x, dist), periods)
    boot = np.empty((n_boot, len(periods)))
    for i in range(n_boot):
        boot[i] = return_level(fit(rng.choice(x, size=len(x), replace=True), dist), periods)
    lo, hi = np.nanpercentile(boot, [100 * alpha / 2, 100 * (1 - alpha / 2)], axis=0)
    return pd.DataFrame(
        {"return_level": base, "ci_lower": lo, "ci_upper": hi},
        index=pd.Index(periods, name="return_period"),
    )
