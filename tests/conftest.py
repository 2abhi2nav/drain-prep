import numpy as np
import pandas as pd
import pytest


@pytest.fixture(scope="session")
def synthetic_daily() -> pd.Series:
    """80 years of gamma-distributed wet-season rain with occasional extremes."""
    rng = np.random.default_rng(0)
    idx = pd.date_range("1940-01-01", "2019-12-31", freq="D")
    wet = rng.random(len(idx)) < np.where(idx.month.isin([10, 11, 12]), 0.4, 0.08)
    rain = np.where(wet, rng.gamma(0.8, 15, len(idx)), 0.0)
    storms = rng.random(len(idx)) < 0.002
    rain = rain + np.where(storms, rng.gumbel(120, 40, len(idx)).clip(0), 0.0)
    return pd.Series(rain, index=idx, name="rain_mm")
