# Chennai Rainfall-Based Urban Drainage Preparedness Recommender

City-level preparedness-ranking model built on IMD 0.25° gridded daily rainfall (1901–2024). Maps a day's 1-day and 3-day accumulated rainfall to a return period/percentile, assigns a risk tier (Watch / Alert / Emergency), and recommends a prioritized action set via a weighted decision matrix. Not a validated flood predictor: no flood labels, no road/ward resolution.

## Directory Structure

```
chennai-drainage-recommender/
├── README.md
├── pyproject.toml
├── requirements.txt
├── .gitignore
├── Makefile
│
├── configs/
│   ├── study_area.yaml          # Chennai grid cell(s), lat/lon bounds, aggregation method
│   ├── thresholds.yaml          # tier cutoffs (percentile / return period) for Watch, Alert, Emergency
│   ├── actions.yaml             # action catalogue per tier: pump deployment, desilting, shelter readiness, ...
│   └── weights.yaml             # criteria weights (AHP-derived), plus sensitivity ranges
│
├── data/
│   ├── raw/                     # IMD .GRD files, one per year (gitignored)
│   ├── interim/                 # Chennai-extracted daily series
│   ├── processed/               # 1-day / 3-day accumulations, annual maxima, tier assignments
│   └── external/                # known flood episodes list (Nov–Dec 2015, Nov 2021, Dec 2023)
│
├── src/
│   └── drainage_rec/
│       ├── __init__.py
│       ├── data/
│       │   ├── download.py      # fetch IMD GRD files by year range
│       │   ├── load.py          # imdlib reader -> xarray/DataFrame
│       │   └── extract.py       # clip to Chennai grid cell(s), build daily city series
│       ├── features/
│       │   ├── accumulation.py  # rolling 1-day / 3-day totals
│       │   ├── intensity.py     # daily intensity metrics
│       │   └── annual_max.py    # annual maxima series (1-day, 3-day)
│       ├── stats/
│       │   ├── distributions.py # Gumbel / GEV fitting, goodness-of-fit (KS, AIC)
│       │   ├── return_period.py # return levels + confidence intervals (bootstrap / profile likelihood)
│       │   ├── percentiles.py   # empirical percentile / exceedance of a given day
│       │   ├── trend.py         # Mann-Kendall, Sen's slope, OLS on annual maxima
│       │   └── frequency.py     # historical extreme-rainfall event frequency
│       ├── risk/
│       │   ├── tiers.py         # rainfall -> return period/percentile -> Watch / Alert / Emergency
│       │   └── classify.py      # batch classification of historical days
│       ├── decision/
│       │   ├── actions.py       # load action catalogue per tier
│       │   ├── criteria.py      # scoring criteria (impact, urgency, lead time, cost, feasibility)
│       │   ├── ahp.py           # pairwise comparison matrix, eigenvector weights, consistency ratio
│       │   ├── matrix.py        # weighted decision matrix scoring and ranking
│       │   └── sensitivity.py   # weight perturbation, rank stability (Kendall tau, top-k overlap)
│       ├── validation/
│       │   ├── known_events.py  # check 2015 / 2021 / 2023 episodes land in top tiers
│       │   └── backtest.py      # tier distribution over history, false-alarm rate sanity check
│       ├── recommend.py         # main entry: (rain_1d, rain_3d) -> tier + ranked actions
│       ├── cli.py               # CLI wrapper around recommend.py
│       └── utils/
│           ├── config.py
│           ├── io.py
│           └── plotting.py
│
├── notebooks/
│   ├── 01_data_exploration.ipynb
│   ├── 02_extreme_value_fitting.ipynb
│   ├── 03_trend_analysis.ipynb
│   ├── 04_tier_calibration.ipynb
│   ├── 05_ahp_and_sensitivity.ipynb
│   └── 06_validation_known_events.ipynb
│
├── scripts/
│   ├── run_pipeline.py          # end-to-end: download -> extract -> fit -> classify -> report
│   └── generate_report_figures.py
│
├── tests/
│   ├── test_accumulation.py
│   ├── test_distributions.py
│   ├── test_return_period.py
│   ├── test_trend.py
│   ├── test_tiers.py
│   ├── test_ahp.py
│   └── test_matrix.py
│
├── outputs/
│   ├── figures/
│   ├── tables/
│   └── recommendations/         # sample recommendation outputs (JSON / markdown)
│
└── report/
    ├── main.md
    ├── sections/
    │   ├── 01_introduction.md
    │   ├── 02_data_and_study_area.md
    │   ├── 03_methodology.md
    │   ├── 04_results.md
    │   ├── 05_validation.md
    │   └── 06_limitations.md
    └── references.bib
```

## Mapping Gaps to Modules

| Gap | Addressed in |
|---|---|
| Recommendation is only descriptive | `risk/tiers.py`, `decision/actions.py`, `recommend.py` |
| Coarse spatial resolution | `data/extract.py`, `configs/study_area.yaml`, `report/sections/06_limitations.md` |
| Arbitrary weights | `decision/ahp.py`, `decision/sensitivity.py`, `configs/weights.yaml` |
| No flood labels for validation | `validation/known_events.py`, `data/external/` |
| Weak statistical core | `stats/distributions.py`, `stats/return_period.py`, `stats/trend.py` |

## Core Dependencies

```
imdlib
numpy
pandas
xarray
scipy
scikit-extremes
pymannkendall
statsmodels
matplotlib
pyyaml
pytest
```

## Pipeline Flow

1. `download.py` -> IMD GRD files into `data/raw/`
2. `load.py` + `extract.py` -> Chennai daily rainfall series
3. `accumulation.py` + `annual_max.py` -> 1-day / 3-day totals, annual maxima
4. `distributions.py` + `return_period.py` + `trend.py` -> GEV/Gumbel fit, return levels with CIs, trend tests
5. `tiers.py` + `classify.py` -> Watch / Alert / Emergency per day
6. `ahp.py` -> weights; `matrix.py` -> action scores per tier; `sensitivity.py` -> ranking stability
7. `known_events.py` -> verify 2015 / 2021 / 2023 episodes rank in top tiers
8. `recommend.py` -> `(rain_1d, rain_3d)` in, tier + prioritized actions out

## Suggested Build Order

1. `configs/study_area.yaml`, `data/download.py`, `data/load.py`, `data/extract.py`
2. `features/*`
3. `stats/*` with matching tests
4. `risk/tiers.py` calibrated against percentile / return-period thresholds
5. `validation/known_events.py` early, as a calibration check on thresholds
6. `decision/*`
7. `recommend.py` and `cli.py`
8. Notebooks and report
