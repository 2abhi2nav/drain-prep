"""Weighted decision matrix (simple additive weighting)."""

import numpy as np
import pandas as pd


def normalise(scores: pd.DataFrame) -> pd.DataFrame:
    """Linear max normalisation; every criterion is benefit-type."""
    return scores / scores.max()


def score_actions(actions: pd.DataFrame, criteria: list[str], weights) -> pd.DataFrame:
    """Add ``score`` (0-1) and ``rank`` (1 = highest priority) columns."""
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()
    norm = normalise(actions[criteria].astype(float))
    out = actions.copy()
    out["score"] = norm.to_numpy() @ w
    out = out.sort_values("score", ascending=False)
    out["rank"] = np.arange(1, len(out) + 1)
    return out


def contribution(actions: pd.DataFrame, criteria: list[str], weights) -> pd.DataFrame:
    """Per-criterion contribution to each action's score (for stacked bar charts)."""
    w = np.asarray(weights, dtype=float)
    w = w / w.sum()
    return normalise(actions[criteria].astype(float)) * w
