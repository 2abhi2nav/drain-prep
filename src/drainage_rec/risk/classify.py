"""Classify every historical day into a risk tier."""

import pandas as pd

from ..features.accumulation import accumulate
from .tiers import TIER_ORDER, RiskModel


def classify_history(daily: pd.Series, model: RiskModel) -> pd.DataFrame:
    acc = accumulate(daily)
    out = acc.copy()
    for k in acc.columns:
        out[f"{k}_pct"] = model.percentile(k, acc[k].to_numpy())
        out[f"{k}_rp"] = model.return_period(k, acc[k].to_numpy())
    idx = model.tier_index({k: acc[k].to_numpy() for k in acc.columns})
    out["tier_idx"] = idx
    out["tier"] = pd.Categorical.from_codes(idx, [t["name"] for t in model.tiers], ordered=True)
    return out


def tier_counts_by_year(classified: pd.DataFrame) -> pd.DataFrame:
    return (
        classified.groupby([classified.index.year, "tier"], observed=False)
        .size()
        .unstack(fill_value=0)
        .reindex(columns=TIER_ORDER, fill_value=0)
        .rename_axis("year")
    )
