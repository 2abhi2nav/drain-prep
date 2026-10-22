"""Annual maxima series for extreme-value fitting."""

import pandas as pd


def annual_maxima(acc: pd.DataFrame, min_days: int = 330) -> pd.DataFrame:
    """Calendar-year maxima of each accumulation column.

    Years with fewer than ``min_days`` observations are dropped so that a
    partially downloaded year cannot bias the fit downward.
    """
    grouped = acc.groupby(acc.index.year)
    out = grouped.max()[grouped.size() >= min_days]
    out.index.name = "year"
    return out


def annual_max_dates(acc: pd.DataFrame) -> pd.DataFrame:
    return acc.groupby(acc.index.year).idxmax().rename_axis("year")
