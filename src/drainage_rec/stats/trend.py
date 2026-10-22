"""Trend tests on annual series: Mann-Kendall + Sen's slope, and OLS regression."""

import numpy as np
import pandas as pd
import pymannkendall as mk
import statsmodels.api as sm


def mann_kendall(series: pd.Series) -> dict:
    r = mk.original_test(series.to_numpy())
    return {
        "trend": r.trend,
        "pvalue": float(r.p),
        "tau": float(r.Tau),
        "z": float(r.z),
        "sen_slope_per_year": float(r.slope),
        "sen_intercept": float(r.intercept),
    }


def ols_trend(series: pd.Series, alpha: float = 0.05) -> dict:
    x = np.asarray(series.index, dtype=float)
    X = sm.add_constant(x - x[0])
    res = sm.OLS(series.to_numpy(), X).fit()
    lo, hi = res.conf_int(alpha)[1]
    return {
        "slope_per_year": float(res.params[1]),
        "slope_ci_lower": float(lo),
        "slope_ci_upper": float(hi),
        "intercept": float(res.params[0]),
        "pvalue": float(res.pvalues[1]),
        "r_squared": float(res.rsquared),
    }


def trend_summary(annual: pd.DataFrame) -> pd.DataFrame:
    rows = {}
    for col in annual.columns:
        s = annual[col].dropna()
        m, o = mann_kendall(s), ols_trend(s)
        rows[col] = {
            "mk_trend": m["trend"],
            "mk_tau": m["tau"],
            "mk_pvalue": m["pvalue"],
            "sen_slope_mm_per_decade": 10 * m["sen_slope_per_year"],
            "ols_slope_mm_per_decade": 10 * o["slope_per_year"],
            "ols_ci_lower": 10 * o["slope_ci_lower"],
            "ols_ci_upper": 10 * o["slope_ci_upper"],
            "ols_pvalue": o["pvalue"],
        }
    return pd.DataFrame(rows).T


def split_period_comparison(series: pd.Series, split_year: int = 1960) -> dict:
    """Welch t-test and Mann-Whitney U of the series before vs after ``split_year``."""
    from scipy import stats

    a, b = series[series.index < split_year], series[series.index >= split_year]
    t = stats.ttest_ind(b, a, equal_var=False)
    u = stats.mannwhitneyu(b, a, alternative="two-sided")
    return {
        "split_year": split_year,
        "mean_before": float(a.mean()),
        "mean_after": float(b.mean()),
        "welch_t": float(t.statistic),
        "welch_pvalue": float(t.pvalue),
        "mannwhitney_pvalue": float(u.pvalue),
    }
