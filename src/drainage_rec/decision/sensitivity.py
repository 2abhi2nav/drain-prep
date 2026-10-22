"""Robustness of the action ranking to the AHP weights."""

import numpy as np
import pandas as pd
from scipy import stats

from .matrix import score_actions


def _ranks(actions, criteria, w) -> pd.Series:
    return score_actions(actions, criteria, w)["rank"].reindex(actions.index)


def one_at_a_time(actions: pd.DataFrame, criteria: list[str], weights, perturbation: float = 0.25) -> pd.DataFrame:
    """Scale each weight by (1 +/- perturbation), renormalise, compare rankings."""
    base = _ranks(actions, criteria, weights)
    top3 = set(base.nsmallest(3).index)
    rows = []
    for i, c in enumerate(criteria):
        for sign in (-1, 1):
            w = np.array(weights, dtype=float)
            w[i] *= 1 + sign * perturbation
            r = _ranks(actions, criteria, w / w.sum())
            rows.append({
                "criterion": c,
                "change": f"{sign * perturbation:+.0%}",
                "kendall_tau": stats.kendalltau(base, r).statistic,
                "top3_overlap": len(top3 & set(r.nsmallest(3).index)) / 3,
                "top1_same": r.idxmin() == base.idxmin(),
            })
    return pd.DataFrame(rows)


def monte_carlo(
    actions: pd.DataFrame, criteria: list[str], weights, n_samples: int = 2000,
    concentration: float = 50, seed: int = 42,
) -> dict:
    """Draw weight vectors from Dirichlet(concentration * w) and record rank stability."""
    rng = np.random.default_rng(seed)
    w0 = np.asarray(weights, dtype=float)
    base = _ranks(actions, criteria, w0)
    draws = rng.dirichlet(concentration * w0 / w0.sum(), size=n_samples)
    ranks = np.empty((n_samples, len(actions)), dtype=int)
    taus = np.empty(n_samples)
    for i, w in enumerate(draws):
        r = _ranks(actions, criteria, w)
        ranks[i] = r.to_numpy()
        taus[i] = stats.kendalltau(base, r).statistic
    rank_freq = pd.DataFrame(
        {k: (ranks == k).mean(axis=0) for k in range(1, len(actions) + 1)}, index=actions.index
    )
    summary = pd.DataFrame({
        "base_rank": base,
        "mean_rank": ranks.mean(axis=0),
        "rank_ci_lower": np.percentile(ranks, 2.5, axis=0),
        "rank_ci_upper": np.percentile(ranks, 97.5, axis=0),
        "p_same_rank": (ranks == base.to_numpy()).mean(axis=0),
    }, index=actions.index).sort_values("base_rank")
    return {
        "rank_frequency": rank_freq,
        "summary": summary,
        "kendall_tau": taus,
        "weights": pd.DataFrame(draws, columns=criteria),
    }
