"""Rolling accumulations and wet-day flags."""

import pandas as pd

ACCUMULATION_WINDOWS = {"rain_1d": 1, "rain_3d": 3}


def accumulate(daily: pd.Series) -> pd.DataFrame:
    """1-day and trailing 3-day accumulated rainfall (mm), one row per day.

    The 3-day total on day t covers t-2..t, i.e. what has fallen up to and
    including the day being assessed.
    """
    daily = daily.asfreq("D").fillna(0.0)
    acc = pd.DataFrame(
        {name: daily.rolling(w, min_periods=1).sum() for name, w in ACCUMULATION_WINDOWS.items()}
    )
    acc.index.name = "date"
    return acc


def wet_days(daily: pd.Series, threshold_mm: float = 2.5) -> pd.Series:
    """IMD rainy-day definition: >= 2.5 mm."""
    return daily >= threshold_mm
