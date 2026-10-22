"""Historical behaviour of the tiering: how often each tier fires."""

import pandas as pd

from ..risk.classify import tier_counts_by_year
from ..risk.tiers import TIER_ORDER


def tier_distribution(classified: pd.DataFrame) -> pd.DataFrame:
    counts = classified["tier"].value_counts().reindex(TIER_ORDER, fill_value=0)
    years = classified.index.year.nunique()
    return pd.DataFrame({
        "days": counts,
        "share_pct": 100 * counts / counts.sum(),
        "days_per_year": counts / years,
    })


def episodes(classified: pd.DataFrame, min_tier_idx: int, gap_days: int = 2) -> pd.DataFrame:
    """Merge consecutive elevated days (allowing short gaps) into episodes."""
    days = classified.index[classified["tier_idx"] >= min_tier_idx]
    if len(days) == 0:
        return pd.DataFrame(columns=["start", "end", "days", "peak_tier", "max_rain_3d"])
    groups = (pd.Series(days).diff().dt.days > gap_days + 1).cumsum()
    rows = []
    for _, g in pd.Series(days).groupby(groups.to_numpy()):
        win = classified.loc[g.iloc[0]: g.iloc[-1]]
        rows.append({
            "start": g.iloc[0].date(),
            "end": g.iloc[-1].date(),
            "days": len(g),
            "peak_tier": TIER_ORDER[int(win["tier_idx"].max())],
            "max_rain_1d": win["rain_1d"].max(),
            "max_rain_3d": win["rain_3d"].max(),
            "max_return_period": win[["rain_1d_rp", "rain_3d_rp"]].max().max(),
        })
    return pd.DataFrame(rows).sort_values("max_return_period", ascending=False).reset_index(drop=True)


def alert_rate_by_year(classified: pd.DataFrame) -> pd.DataFrame:
    return tier_counts_by_year(classified)
