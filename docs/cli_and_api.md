# CLI & Python Developer API Reference

This document provides a comprehensive developer guide for interacting with `drainage-rec` via the Command Line Interface (CLI) and the Python programmatic API.

---

## 💻 1. Command-Line Interface (CLI)

The package installs a console script entry point: `drainage-rec` (also runnable via `python -m drainage_rec.cli`).

### 1.1 `drainage-rec download`
Fetches IMD gridded rainfall files and compiles the Chennai daily time series.

```bash
drainage-rec download [--start START_YEAR] [--end END_YEAR] [--workers WORKERS] [--keep-raw]
```

**Arguments:**
- `--start` *(int, default: 1901)*: Earliest year to download.
- `--end` *(int, default: 2024)*: Most recent year to download.
- `--workers` *(int, default: 3)*: Parallel HTTP download threads.
- `--keep-raw` *(flag, default: False)*: If omitted, temporary $\sim 25\text{ MB}$ raw `.grd` files are deleted after spatial extraction to save disk space.

**Example:**
```bash
drainage-rec download --start 2020 --end 2024 --workers 4
```

---

### 1.2 `drainage-rec pipeline`
Executes end-to-end data processing, feature calculation, distribution fitting, historical classification, AHP decision scoring, and validation.

```bash
drainage-rec pipeline
```

**Outputs:**
Writes processed tables to `data/processed/` and outputs a JSON summary of the run to stdout:

```json
{
  "period": ["1901-01-01", "2024-12-31"],
  "years": 124,
  "selected_distribution": {
    "rain_1d": "gumbel",
    "rain_3d": "gumbel"
  },
  "ahp": {
    "cr": 0.0098,
    "consistent": true
  },
  "known_event_hit_rate_alert_plus": 1.0,
  "known_event_hit_rate_emergency": 0.714
}
```

---

### 1.3 `drainage-rec recommend`
Evaluates a specific rainfall observation or quantitative forecast and outputs the assigned risk tier, dominant driver, return periods, and ranked municipal actions.

```bash
drainage-rec recommend --rain-1d FLOAT --rain-3d FLOAT [--json]
```

**Arguments:**
- `--rain-1d` *(float, required)*: 24-hour rainfall in millimeters.
- `--rain-3d` *(float, required)*: Trailing 72-hour accumulated rainfall in millimeters (must be $\ge \text{rain-1d}$).
- `--json` *(flag, optional)*: Emits formatted JSON instead of human-readable text.

**Example (Human-readable):**
```bash
drainage-rec recommend --rain-1d 120 --rain-3d 250
```

*Output:*
```text
Tier: Alert
  rain_1d: 120.0 mm  -> 99.2 pct (wet days), return period 2.3 y
  rain_3d: 250.0 mm  -> 99.3 pct (wet days), return period 3.3 y
Recommended actions (highest priority first):
  1. [0.877] Activate 24x7 flood control room and ward-level teams
  2. [0.840] Pre-position dewatering pumps at known low-lying subways
  3. [0.810] Coordinate staged releases from Chembarambakkam / Puzhal reservoirs
  4. [0.786] Issue public rainfall advisory via SMS / social media
  5. [0.707] Inspect and clear storm-drain inlets and culverts
  6. [0.561] Targeted desilting of major canals (Buckingham, Otteri Nullah, Cooum mouth)
```

**Example (JSON output):**
```bash
drainage-rec recommend --rain-1d 200 --rain-3d 350 --json
```

---

## 🐍 2. Python Programmatic API

### 2.1 Recommender Service (`drainage_rec.recommend`)

The primary entry point for programmatic inference:

```python
from drainage_rec.recommend import Recommender, recommend

# Method 1: Functional one-liner
rec = recommend(rain_1d=150.0, rain_3d=260.0)
print(f"Risk Tier: {rec.tier}")
print(f"Driver: {rec.driver}")

# Method 2: Reusable instance
engine = Recommender.load()
rec = engine.recommend(rain_1d=80.0, rain_3d=120.0)

for action in rec.actions:
    print(f"Rank {action['rank']}: {action['name']} (Score: {action['score']:.3f})")
```

#### Dataclass: `Recommendation`
```python
@dataclass
class Recommendation:
    tier: str           # "Normal" | "Watch" | "Alert" | "Emergency"
    driver: str         # "rain_1d" | "rain_3d"
    assessment: dict    # Detailed percentiles and return periods
    actions: list[dict] # Ranked list of municipal actions
```

---

### 2.2 Risk Model (`drainage_rec.risk.tiers`)

Manages distribution fits, wet-day percentiles, and threshold rules:

```python
from drainage_rec.risk.tiers import RiskModel
import pandas as pd

# Load serialized model
import json
with open("data/processed/model.json") as f:
    model = RiskModel.from_dict(json.load(f))

# Query thresholds
print(model.thresholds_mm())
# Output:
#               rain_1d     rain_3d
# Watch       57.666800  102.984200
# Alert      113.733410  202.776965
# Emergency  192.549660  336.053301

# Calculate return period of an arbitrary rainfall value
rp_1d = model.return_period("rain_1d", 150.0)  # ~4.1 years
```

---

### 2.3 Statistical Modeling (`drainage_rec.stats`)

#### Extreme Value Distribution Fitting:
```python
from drainage_rec.stats.distributions import fit, fit_all, best_fit

# Fits both GEV and Gumbel models to annual maxima
fits = fit_all(annual_maxima_series)

# Selects best distribution via AIC and LR tests
chosen = best_fit(fits)
print(f"Selected: {chosen.dist.upper()} (AIC: {chosen.aic:.2f})")
```

#### Return Levels with Bootstrap Confidence Intervals:
```python
from drainage_rec.stats.return_period import bootstrap_return_levels

rl_table = bootstrap_return_levels(
    sample=annual_maxima_series,
    dist="gumbel",
    periods=[2, 5, 10, 25, 50, 100],
    n_boot=500,
    alpha=0.05
)
print(rl_table)
```

#### Trend Analysis:
```python
from drainage_rec.stats.trend import mann_kendall, trend_summary

mk_result = mann_kendall(annual_maxima_series)
print(f"Trend: {mk_result['trend']}, p-val: {mk_result['pvalue']:.3f}, Sen's slope: {mk_result['sen_slope_per_year']:.3f} mm/yr")
```

---

### 2.4 Decision Analysis (`drainage_rec.decision`)

#### AHP Matrix & Weights:
```python
from drainage_rec.decision.ahp import ahp_weights, pairwise_matrix

criteria = ["impact", "urgency", "lead_time", "affordability", "feasibility"]
A = pairwise_matrix(criteria, upper_triangle_dict)
result = ahp_weights(A)

print(f"Weights: {result['weights']}")
print(f"Consistency Ratio (CR): {result['cr']:.4f}")
print(f"Is Consistent? {result['consistent']}")
```

#### Scoring Actions (SAW):
```python
from drainage_rec.decision.matrix import score_actions
from drainage_rec.decision.actions import load_actions

actions_df = load_actions()
scored = score_actions(actions_df, criteria, result['weights'])
print(scored[["name", "min_tier", "score", "rank"]])
```

---

## ⚙️ 3. Configuration File Reference (`configs/`)

All configuration parameters are stored as clean YAML documents:

### `configs/study_area.yaml`
```yaml
name: Chennai
lat_min: 12.75
lat_max: 13.25
lon_min: 80.0
lon_max: 80.5
aggregation: mean        # mean | max across valid land cells
start_year: 1901
end_year: 2024
```

### `configs/thresholds.yaml`
```yaml
wet_day_mm: 2.5          # Standard IMD wet-day cutoff
tiers:
  - name: Normal
  - name: Watch
    percentile: 95       # 95th percentile among historical wet days
  - name: Alert
    return_period: 2     # 2-year return period on annual maxima
  - name: Emergency
    return_period: 10    # 10-year return period on annual maxima
```

### `configs/weights.yaml`
```yaml
criteria: [impact, urgency, lead_time, affordability, feasibility]
pairwise:
  impact:        {urgency: 2, lead_time: 3, affordability: 5, feasibility: 3}
  urgency:       {lead_time: 2, affordability: 4, feasibility: 2}
  lead_time:     {affordability: 3, feasibility: 1}
  affordability: {feasibility: 1/2}
sensitivity:
  perturbation: 0.25
  n_samples: 2000
  dirichlet_concentration: 50
  seed: 42
```

### `configs/actions.yaml`
```yaml
actions:
  - id: control_room
    name: Activate 24x7 flood control room and ward-level teams
    min_tier: Alert
    scores: {impact: 4, urgency: 5, lead_time: 4, affordability: 4, feasibility: 5}
  # ... other actions
```

---

## 🛠️ 4. Extending the System

### Adding a New Preparedness Action
1. Open [`configs/actions.yaml`](file:///c:/Users/krish/Desktop/dev/drain-prep/configs/actions.yaml).
2. Append the new action under `actions`:
   ```yaml
     - id: sluice_gate_monitoring
       name: Deploy continuous telemetry teams at Otteri Nullah sluice gates
       min_tier: Watch
       scores: {impact: 3, urgency: 4, lead_time: 4, affordability: 4, feasibility: 4}
   ```
3. Re-run `make pipeline` to update all rankings, sensitivity statistics, and dashboard tables.

### Adapting to a Different City / Study Area
1. Update `configs/study_area.yaml` with the target region's latitude/longitude bounding box and start/end years.
2. If necessary, adjust `configs/thresholds.yaml` to match regional flood risk guidelines.
3. Download the regional grids using `drainage-rec download` and execute `drainage-rec pipeline`.
