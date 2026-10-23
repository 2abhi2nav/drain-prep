# Data Pipeline & Ingestion Specification

This document provides a comprehensive reference for the data ingestion, extraction, and analytical transformation pipeline within `drainage-rec`.

---

## 📥 1. IMD Archive Ingestion (`drainage_rec.data.download`)

### 1.1 Ingestion Characteristics
The India Meteorological Department (IMD) National Climate Center archives daily gridded rainfall as binary raster grids (`.grd`). Because the official server frequently exhibits high latency and dropped connections:
- **Direct HTTP Streaming**: Uses `requests.post()` with streaming chunks ($64\text{ KB}$) rather than un-monitored wrappers, enforcing strict connection timeouts ($30\text{ s}$) and read timeouts ($120\text{ s}$).
- **Concurrency**: Manages parallel downloads via `concurrent.futures.ThreadPoolExecutor` (default: 3 workers).
- **Exponential Backoff**: Retries failed years up to 4 times with escalating sleep intervals ($5, 10, 15, 20\text{ s}$).
- **File Integrity Verification**: Each file is verified against its exact expected byte size derived from the number of days in the year:
  $$\text{Expected Bytes} = \text{Grid Size} \times (366 \text{ if leap year else } 365)$$
  Any incomplete `.part` file is immediately purged and retried.

### 1.2 Disk Footprint Optimization
Raw `.grd` files require $\sim 25\text{ MB}$ per year ($> 3\text{ GB}$ for the full 124-year series). By default, as soon as a year is processed into its Chennai spatial extract, the temporary `.grd` file is unlinked unless `--keep-raw` is passed.

---

## ✂️ 2. Spatial Extraction (`drainage_rec.data.extract`)

### 2.1 Geographic Subsetting
Each yearly raster is loaded into an `xarray.DataArray` via `drainage_rec.data.load.load_year()`. The grid is clipped to the bounding box specified in `configs/study_area.yaml`:
- Latitude: $[12.75^\circ\text{N}, 13.25^\circ\text{N}]$
- Longitude: $[80.0^\circ\text{E}, 80.5^\circ\text{E}]$

### 2.2 Land Masking & City Aggregation
Grid points over the Bay of Bengal contain missing/fill values ($NaN$). The spatial aggregation (`mean` or `max`) skips $NaN$ entries. The resulting daily mean is clipped to $\ge 0.0\text{ mm}$ and stored in two locations:
1. **Per-Year Files (`data/interim/years/<year>.csv`)**: Wide format containing individual cell readings (e.g. `12.75N_80.00E`, `13.00N_80.00E`) alongside the city aggregate `rain_mm`.
2. **Consolidated City Series (`data/interim/chennai_daily.csv`)**: A continuous, sorted 124-year daily time series spanning `1901-01-01` to `2024-12-31` ($45,292$ daily observations).

---

## ⚙️ 3. Analytical Pipeline Execution (`drainage_rec.pipeline`)

The automated pipeline (`drainage-rec pipeline` or `make pipeline`) executes sequentially:

```
load_series()
   │
   ├──> accumulate() -> accumulations.csv
   │       │
   │       └──> annual_maxima() -> annual_maxima.csv
   │               │
   │               ├──> fit_all() + best_fit() -> distribution_fits.csv
   │               ├──> bootstrap_return_levels() -> return_levels.csv
   │               └──> trend_summary() + split_period -> trends.csv
   │
   ├──> frequency_summary(), exceedance_counts(), monthly_climatology()
   │
   ├──> RiskModel.fit() -> model.json & tier_thresholds_mm.csv
   │       │
   │       └──> classify_history() -> classified_days.csv
   │               ├──> tier_counts_by_year.csv
   │               ├──> tier_distribution.csv
   │               ├──> alert_episodes.csv
   │               └──> evaluate_events() -> known_events_validation.csv
   │
   └──> Decision Engine (AHP + SAW + Sensitivity)
           ├──> weights_from_config() -> ahp_pairwise.csv & ahp_weights.csv
           ├──> score_actions() -> action_scores.csv
           ├──> one_at_a_time() -> sensitivity_oat.csv
           └──> monte_carlo() -> sensitivity_mc_summary.csv, sensitivity_rank_frequency.csv, sensitivity_mc_tau.csv
```

---

## 📊 4. Processed Data File Dictionary (`data/processed/`)

Every table produced by the pipeline is documented below:

| File Name | Primary Keys / Index | Columns | Description |
| :--- | :--- | :--- | :--- |
| `accumulations.csv` | `date` | `rain_1d`, `rain_3d` | 1-day and trailing 3-day accumulated rainfall (mm) for every day in record. |
| `annual_maxima.csv` | `year` | `rain_1d`, `rain_3d`, `rain_1d_date`, `rain_3d_date` | Maximum 1-day and 3-day rainfall per calendar year and date of occurrence. |
| `distribution_fits.csv` | `accumulation`, `dist` | `params`, `n`, `log_likelihood`, `aic`, `ks_stat`, `ks_pvalue`, `xi`, `selected` | Parameter estimates, log-likelihood, AIC, and KS tests for GEV and Gumbel fits. |
| `return_levels.csv` | `return_period` | `return_level`, `ci_lower`, `ci_upper`, `accumulation`, `dist` | Quantiles and 95% bootstrap confidence bounds for $T \in \{2, 5, 10, 25, 50, 100\}$. |
| `tier_thresholds_mm.csv` | `Tier` | `rain_1d`, `rain_3d` | Minimum rainfall (mm) required to enter Watch, Alert, and Emergency tiers. |
| `classified_days.csv` | `date` | `rain_1d`, `rain_3d`, `rain_1d_pct`, `rain_3d_pct`, `rain_1d_rp`, `rain_3d_rp`, `tier`, `driver` | Comprehensive historical classification of all $45,292$ days. |
| `tier_counts_by_year.csv` | `year` | `Normal`, `Watch`, `Alert`, `Emergency` | Frequency count of days spent in each risk tier per calendar year. |
| `tier_distribution.csv` | `tier` | `days`, `fraction`, `days_per_year` | Overall historical days and percentage breakdown across tiers. |
| `alert_episodes.csv` | Integer Index | `start`, `end`, `duration_days`, `peak_date`, `peak_tier`, `max_rain_1d`, `max_rain_3d`, `max_rp` | Contiguous multi-day episodes where risk remained at $\ge \text{Alert}$. |
| `trends.csv` | Accumulation Key | `mk_trend`, `mk_tau`, `mk_pvalue`, `sen_slope_mm_per_decade`, `ols_slope_mm_per_decade`, `ols_ci_lower`, `ols_ci_upper`, `ols_pvalue` | Mann-Kendall, Sen's slope, and OLS regression trend statistics. |
| `monthly_climatology.csv` | `month` | `mean_monthly_mm`, `median_monthly_mm`, `p90_monthly_mm`, `wet_days_mean`, `heavy_rain_days_mean` | Baseline monthly climatological statistics. |
| `exceedance_counts.csv` | `year` | `gt_25mm`, `gt_50mm`, `gt_100mm`, `gt_150mm`, `gt_200mm` | Annual count of days exceeding fixed rainfall thresholds. |
| `frequency_summary.csv` | Threshold (mm) | `total_days`, `days_per_year`, `pct_of_wet_days` | City-wide recurrence frequency for rainfall cut-offs. |
| `ahp_pairwise.csv` | Criteria Name | `impact`, `urgency`, `lead_time`, `affordability`, `feasibility` | Full $5 \times 5$ reciprocal Saaty comparison matrix. |
| `ahp_weights.csv` | Criteria Name | `weight` | Derived eigenvector priority weights summing to 1.0. |
| `action_scores.csv` | `id` | `name`, `min_tier`, `impact`, `urgency`, `lead_time`, `affordability`, `feasibility`, `score`, `rank` | Prioritized municipal actions with computed SAW scores and rank order. |
| `sensitivity_oat.csv` | Integer Index | `criterion`, `change`, `kendall_tau`, `top3_overlap`, `top1_same` | One-At-A-Time $\pm 25\%$ criteria weight perturbation results. |
| `sensitivity_mc_summary.csv` | `id` | `base_rank`, `mean_rank`, `rank_ci_lower`, `rank_ci_upper`, `p_same_rank` | Monte Carlo ranking stability metrics across 2,000 Dirichlet draws. |
| `sensitivity_rank_frequency.csv`| `id` | `1`, `2`, `3`, ..., `9` | Empirical probability distribution of each action occupying ranks 1 to 9. |
| `sensitivity_mc_tau.csv` | Draw Index | `kendall_tau` | Distribution of Kendall's $\tau$ correlation coefficients across all draws. |
| `known_events_validation.csv`| `event` | `start`, `end`, `in_record`, `peak_date`, `peak_tier`, `max_rain_1d`, `max_rain_3d`, `max_return_period`, `severity_percentile`, `days_alert_or_above` | Empirical validation metrics against documented historical flood events. |
| `model.json` | Key-Value Root | Serialized `RiskModel` object | Compact JSON representation of fitted distributions, wet samples, and tier rules. |
| `summary.json` | Key-Value Root | Climatological, model selection, AHP, and validation metrics | Top-level summary loaded by dashboard and testing scripts. |
