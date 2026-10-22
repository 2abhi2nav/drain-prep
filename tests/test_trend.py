import numpy as np
import pandas as pd

from drainage_rec.stats.trend import mann_kendall, ols_trend


def test_detects_increasing_trend():
    rng = np.random.default_rng(0)
    s = pd.Series(np.arange(100) * 0.5 + rng.normal(0, 5, 100), index=range(1920, 2020))
    mk = mann_kendall(s)
    assert mk["trend"] == "increasing"
    assert mk["pvalue"] < 0.01
    assert 0.4 < mk["sen_slope_per_year"] < 0.6
    o = ols_trend(s)
    assert o["slope_ci_lower"] < 0.5 < o["slope_ci_upper"]


def test_no_trend_in_noise():
    rng = np.random.default_rng(1)
    s = pd.Series(rng.normal(100, 20, 100), index=range(1920, 2020))
    assert mann_kendall(s)["trend"] == "no trend"
