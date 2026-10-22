"""End-to-end analysis: city series -> fits -> tiers -> decision matrix -> validation.

All outputs are written to data/processed/ and read back by the dashboard.
"""

import json
import logging

import pandas as pd

from .data.extract import combine_years, extracted_years
from .decision.actions import load_actions
from .decision.ahp import weights_from_config
from .decision.matrix import score_actions
from .decision.sensitivity import monte_carlo, one_at_a_time
from .features.accumulation import ACCUMULATION_WINDOWS, accumulate
from .features.annual_max import annual_max_dates, annual_maxima
from .risk.classify import classify_history, tier_counts_by_year
from .risk.tiers import RiskModel
from .stats.distributions import best_fit, fit_all, likelihood_ratio_test
from .stats.frequency import exceedance_counts, frequency_summary, monthly_climatology
from .stats.return_period import bootstrap_return_levels
from .stats.trend import split_period_comparison, trend_summary
from .utils.config import PROCESSED_DIR, load_config
from .utils.io import CITY_SERIES, read_city_series, read_known_events, write_json, write_table
from .validation.backtest import episodes, tier_distribution
from .validation.known_events import evaluate_events, hit_rate

log = logging.getLogger(__name__)


def load_series() -> pd.Series:
    if extracted_years():
        return combine_years()
    return read_city_series(CITY_SERIES)


def run_pipeline(n_boot: int = 500) -> dict:
    daily = load_series()
    acc = accumulate(daily)
    amax = annual_maxima(acc)
    write_table(acc, "accumulations")
    write_table(amax.join(annual_max_dates(acc), rsuffix="_date"), "annual_maxima")

    # Extreme-value fits and return levels
    fit_rows, rl_tables, lr = [], [], {}
    for k in ACCUMULATION_WINDOWS:
        fits = fit_all(amax[k])
        chosen = best_fit(fits)
        lr[k] = likelihood_ratio_test(fits)
        for f in fits.values():
            fit_rows.append({"accumulation": k, **f.to_dict(), "selected": f.dist == chosen.dist})
        rl = bootstrap_return_levels(amax[k], chosen.dist, n_boot=n_boot)
        rl_tables.append(rl.assign(accumulation=k, dist=chosen.dist))
    write_table(pd.DataFrame(fit_rows).set_index(["accumulation", "dist"]), "distribution_fits")
    write_table(pd.concat(rl_tables), "return_levels")

    # Trends and frequency
    trends = trend_summary(amax)
    write_table(trends, "trends")
    split = {k: split_period_comparison(amax[k]) for k in amax}
    write_table(exceedance_counts(daily), "exceedance_counts")
    write_table(frequency_summary(daily), "frequency_summary")
    write_table(monthly_climatology(daily), "monthly_climatology")

    # Risk model + historical classification
    model = RiskModel.fit(daily)
    write_json(model.to_dict(), PROCESSED_DIR / "model.json")
    write_table(model.thresholds_mm(), "tier_thresholds_mm")
    classified = classify_history(daily, model)
    write_table(classified.drop(columns=["tier_idx"]), "classified_days")
    write_table(tier_counts_by_year(classified), "tier_counts_by_year")
    write_table(tier_distribution(classified), "tier_distribution")
    write_table(episodes(classified, min_tier_idx=2), "alert_episodes")

    # Decision matrix: AHP weights, scores, sensitivity
    wcfg = load_config("weights")
    criteria, A, ahp = weights_from_config(wcfg)
    write_table(pd.DataFrame(A, index=criteria, columns=criteria), "ahp_pairwise")
    write_table(pd.DataFrame({"weight": ahp["weights"]}, index=criteria), "ahp_weights")
    actions = load_actions()
    write_table(score_actions(actions, criteria, ahp["weights"]), "action_scores")
    s = wcfg["sensitivity"]
    write_table(one_at_a_time(actions, criteria, ahp["weights"], s["perturbation"]), "sensitivity_oat")
    mc = monte_carlo(actions, criteria, ahp["weights"], s["n_samples"], s["dirichlet_concentration"], s["seed"])
    write_table(mc["summary"], "sensitivity_mc_summary")
    write_table(mc["rank_frequency"], "sensitivity_rank_frequency")
    write_table(pd.DataFrame({"kendall_tau": mc["kendall_tau"]}), "sensitivity_mc_tau")

    # Validation
    events = evaluate_events(classified, read_known_events())
    write_table(events.set_index("event"), "known_events_validation")

    summary = {
        "period": [str(daily.index.min().date()), str(daily.index.max().date())],
        "years": int(amax.shape[0]),
        "selected_distribution": {k: model.fits[k].dist for k in model.fits},
        "gev_vs_gumbel_lr_test": lr,
        "ahp": {"weights": dict(zip(criteria, map(float, ahp["weights"]))),
                "cr": ahp["cr"], "consistent": bool(ahp["consistent"])},
        "mann_kendall": trends[["mk_trend", "mk_pvalue", "sen_slope_mm_per_decade"]].to_dict("index"),
        "split_period": split,
        "mc_mean_kendall_tau": float(mc["kendall_tau"].mean()),
        "known_event_hit_rate_alert_plus": hit_rate(events, "Alert"),
        "known_event_hit_rate_emergency": hit_rate(events, "Emergency"),
    }
    write_json(summary, PROCESSED_DIR / "summary.json")
    return summary
