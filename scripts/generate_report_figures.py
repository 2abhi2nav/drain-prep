"""Static PNG figures for the written report (reads data/processed/)."""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from drainage_rec.dashboard.theme import SERIES, SERIES_LABEL, TIER_COLOR
from drainage_rec.recommend import Recommender
from drainage_rec.stats.frequency import empirical_exceedance
from drainage_rec.utils.config import OUTPUT_DIR, PROCESSED_DIR

FIG = OUTPUT_DIR / "figures"
TABLES = OUTPUT_DIR / "tables"


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=200, bbox_inches="tight")
    plt.close(fig)


def main():
    plt.rcParams.update({"axes.spines.top": False, "axes.spines.right": False, "axes.grid": True,
                         "grid.color": "#e1e0d9", "font.size": 10})
    rec = Recommender.load()
    amax = pd.read_csv(PROCESSED_DIR / "annual_maxima.csv", index_col="year")
    rl = pd.read_csv(PROCESSED_DIR / "return_levels.csv")

    fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
    for ax, k in zip(axes, SERIES):
        f = rec.model.fits[k]
        t = rl[rl["accumulation"] == k]
        T = np.logspace(np.log10(1.05), np.log10(200), 200)
        ax.fill_between(t["return_period"], t["ci_lower"], t["ci_upper"], color=SERIES[k], alpha=0.15, label="95% CI")
        ax.plot(T, f.ppf(1 - 1 / T), color=SERIES[k], lw=2, label=f"{f.dist.upper()} fit")
        emp = empirical_exceedance(amax[k])
        ax.scatter(emp["return_period"], emp["value"], s=14, facecolor="white", edgecolor=SERIES[k], label="Observed")
        ax.set_xscale("log")
        ax.set_xlabel("Return period (years)")
        ax.set_title(SERIES_LABEL[k])
        ax.legend(frameon=False)
    axes[0].set_ylabel("Rainfall (mm)")
    save(fig, "return_levels")

    trends = pd.read_csv(PROCESSED_DIR / "trends.csv", index_col=0)
    fig, axes = plt.subplots(2, 1, figsize=(10, 6), sharex=True)
    for ax, k in zip(axes, SERIES):
        s = amax[k]
        ax.plot(s.index, s, color=SERIES[k], lw=1.2, marker="o", ms=3)
        slope = trends.loc[k, "sen_slope_mm_per_decade"] / 10
        x = np.array([s.index.min(), s.index.max()])
        ax.plot(x, s.median() + slope * (x - np.median(s.index)), "--", color="#52514e",
                label=f"Sen's slope {10 * slope:+.1f} mm/decade (MK p = {trends.loc[k, 'mk_pvalue']:.2f})")
        ax.set_ylabel(f"{SERIES_LABEL[k]} (mm)")
        ax.legend(frameon=False, loc="upper left")
    save(fig, "annual_maxima_trend")

    ty = pd.read_csv(PROCESSED_DIR / "tier_counts_by_year.csv", index_col="year")
    fig, ax = plt.subplots(figsize=(10, 3))
    bottom = np.zeros(len(ty))
    for t in ("Watch", "Alert", "Emergency"):
        ax.bar(ty.index, ty[t], bottom=bottom, color=TIER_COLOR[t], label=t, width=0.85)
        bottom += ty[t].to_numpy()
    ax.set_ylabel("Days")
    ax.legend(frameon=False, ncols=3)
    save(fig, "tier_days_per_year")

    TABLES.mkdir(parents=True, exist_ok=True)
    for name in ("return_levels", "distribution_fits", "trends", "known_events_validation", "action_scores",
                 "sensitivity_mc_summary", "tier_thresholds_mm", "frequency_summary"):
        pd.read_csv(PROCESSED_DIR / f"{name}.csv").to_csv(TABLES / f"{name}.csv", index=False)

    samples = {"watch": (40, 70), "alert": (110, 180), "emergency": (250, 400)}
    for label, (r1, r3) in samples.items():
        out = OUTPUT_DIR / "recommendations" / f"sample_{label}.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(rec.recommend(r1, r3).to_dict(), indent=2))
    print(f"Figures in {FIG}, tables in {TABLES}")


if __name__ == "__main__":
    main()
