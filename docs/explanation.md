# Complete Developer & Student Guide: Building the Chennai Drainage Recommender

> **Target Audience**: Computer Science & Engineering (CSE) students, software engineers, and data engineers.  
> **Objective**: Explain the intuition, mathematics, algorithms, and software architecture so thoroughly that you can rebuild this entire project from scratch in Python without referencing any other documentation.

---

## 📑 Table of Contents
1. [The Real-World Problem & Why Naive CS Solutions Fail](#1-the-real-world-problem--why-naive-cs-solutions-fail)
2. [End-to-End System Mental Model](#2-end-to-end-system-mental-model)
3. [Hydrological & Gridded Data Foundations](#3-hydrological--gridded-data-foundations)
4. [Extreme Value Statistics & Climatology (Math for CS Students)](#4-extreme-value-statistics--climatology-math-for-cs-students)
5. [The 4-Tier Operational Flood Architecture](#5-the-4-tier-operational-flood-architecture)
6. [Decision Science: Analytic Hierarchy Process (AHP) & MCDA](#6-decision-science-analytic-hierarchy-process-ahp--mcda)
7. [Sensitivity & Robustness Engineering](#7-sensitivity--robustness-engineering)
8. [Step-by-Step Implementation Blueprint (Code Architecture)](#8-step-by-step-implementation-blueprint-code-architecture)
9. [Validation & Historical Backtesting](#9-validation--historical-backtesting)
10. [Engineering Gotchas & Edge Cases](#10-engineering-gotchas--edge-cases)

---

## 1. The Real-World Problem & Why Naive CS Solutions Fail

### 1.1 The Context: Chennai's Flood Dynamics
Chennai is a flat, coastal metropolis located on the Bay of Bengal in Tamil Nadu, India. Unlike cities with steep hills where water drains quickly by gravity, Chennai has a shallow slope towards the sea. More importantly, Chennai receives most of its annual rainfall during the **Northeast Monsoon** (October to December) through intense cyclonic storms and deep depressions.

When catastrophic rain hits (such as the December 2015 deluge or Cyclone Michaung in December 2023), three crises occur simultaneously:
1. **Local Stormwater Choke**: Localized cloudbursts overwhelm roadside stormwater drains and road underpasses within 1 to 2 hours.
2. **Major Catchment & Reservoir Overload**: Sustained multi-day rain over upstream catchments fills reservoirs (Chembarambakkam, Puzhal, Poondi). Once storage capacity is reached, massive volumes of water must be released into urban rivers (Adyar, Cooum), causing widespread riverine flooding.
3. **High Tide & Tidal Lock**: High astronomical tides in the Bay of Bengal push sea water inland, preventing urban canals (such as the Buckingham Canal) from discharging water into the sea.

### 1.2 Why Naive CS Approaches Fail
As a software engineer, your first instinct might be:
- *"Let's train a Deep Neural Network (LSTM / XGBoost) on flood sensor data!"*  
  **Why it fails**: Chennai does not have continuous, 100-year historical flood-depth sensor readings across every street corner. You have rainfall records, but very sparse ground-truth inundation labels. Supervised learning suffers from severe label scarcity and high spatial overfitting.
- *"Let's just use hardcoded `if rainfall > 100 mm: trigger_alarm()` rules!"*  
  **Why it fails**: Is $100\text{ mm}$ in 24 hours dangerous? What if $100\text{ mm}$ fell after 10 days of dry heat (soil absorbs it) versus after 3 days of relentless $80\text{ mm}$ downpours (soil saturated, reservoirs at $98\%$ capacity)? A single threshold ignores **duration dynamics** and **extreme value probability**.
- *"Let's just execute all disaster response actions at once!"*  
  **Why it fails**: Municipal resources are finite. You have limited dewatering pumps, limited National Disaster Response Force (NDRF) boats, and limited power isolation crews. If you send canal desilting excavators during a peak cyclone downpour, you waste manpower when you should have prioritized boat deployments and opening emergency shelters.

### 1.3 The Solution: Coupling Extreme Value Theory with Multi-Criteria Decision Analysis
`drainage-rec` solves this by decoupling the problem into two rigorous layers:
1. **Hydrological Risk Inference**: Uses 124 years of daily rainfall data (1901–2024) to fit **Extreme Value Distributions** (GEV / Gumbel) to 1-day and trailing 3-day rainfall totals. This answers: *What is the statistical rarity (return period) of this event?*
2. **Operational Decision Matrix**: Uses **Saaty's Analytic Hierarchy Process (AHP)** and **Simple Additive Weighting (SAW)** to rank actions dynamically based on 5 operational criteria (Impact, Urgency, Lead Time, Affordability, Feasibility). This answers: *Given this rarity tier, exactly which actions should civic teams execute in order of priority?*

---

## 2. End-to-End System Mental Model

The entire project operates as a directional, acyclic processing pipeline:

```
[Raw IMD Binary Grids (1901-2024)]
              │
              ▼  (Spatial mask over Chennai: 12.75N-13.25N, 80.0E-80.5E)
[Clean Daily City Series (45,292 days)]
              │
              ▼  (Rolling sums: 1-day and trailing 3-day)
[Accumulation Table (rain_1d, rain_3d)]
              │
              ├──> [Annual Block Maxima Extraction (124 sample points)]
              │           │
              │           ▼  (MLE Fitting, AIC Model Selection)
              │      [EVT Distributions: Gumbel selected]
              │           │
              │           ▼  (Bootstrap resampling, n=500)
              │      [Return Levels & 95% Confidence Intervals]
              │
              └──> [Empirical CDF of Historical Wet Days (>= 2.5 mm)]
                          │
                          ▼
              [4-Tier Risk Model (Normal, Watch, Alert, Emergency)]
                          │
                          ▼  (Evaluates any incoming (rain_1d, rain_3d))
              [Risk Tier Assignment + Escalation Driver Diagnosis]
                          │
                          ▼
              [AHP Multi-Criteria Decision Matrix (5 criteria, 9 actions)]
                          │
                          ▼
              [Ranked Action Output + Streamlit Dashboard / CLI]
```

---

## 3. Hydrological & Gridded Data Foundations

### 3.1 Understanding Gridded Binary Weather Files (`.grd`)
Meteorological agencies do not give you clean CSV files; they store global and regional observations as gridded rasters.
- The **India Meteorological Department (IMD)** provides daily precipitation on a regular $0.25^\circ \times 0.25^\circ$ latitude-longitude spatial grid covering India.
- Each year's data is stored in a single binary `.grd` file.
- **Inside the binary file**:
  - For a non-leap year ($365$ days), there are $365$ consecutive 2D floating-point matrices.
  - For a leap year ($366$ days), there are $366$ 2D floating-point matrices.
  - Each matrix has dimension $129 \times 135$ (Latitude rows $\times$ Longitude columns spanning India from $6.5^\circ\text{N}$ to $38.5^\circ\text{N}$ and $66.5^\circ\text{E}$ to $100.0^\circ\text{E}$).
  - Each cell is a 32-bit IEEE float (`float32`, 4 bytes).
  - Missing/sea values are encoded with a sentinel flag (e.g. `-999.0` or `NaN`).

### 3.2 The Chennai Bounding Box & Spatial Land Masking
Chennai's metropolitan area falls inside the geographic rectangle:
$$\text{Latitude: } [12.75^\circ\text{N}, 13.25^\circ\text{N}], \quad \text{Longitude: } [80.00^\circ\text{E}, 80.50^\circ\text{E}]$$

On a $0.25^\circ$ grid, this produces a $3 \times 3$ matrix of 9 grid cells:
- Longitudes: $80.00^\circ\text{E}$, $80.25^\circ\text{E}$, $80.50^\circ\text{E}$
- Latitudes: $12.75^\circ\text{N}$, $13.00^\circ\text{N}$, $13.25^\circ\text{N}$

```
       80.00°E       80.25°E       80.50°E
13.25°N [ Land ]     [ Land ]     [ SEA / NaN ]
13.00°N [ Land ]     [ SEA / NaN] [ SEA / NaN ]
12.75°N [ Land ]     [ Land ]     [ SEA / NaN ]
```

> **Critical CS Insight**: Because Chennai borders the Bay of Bengal on the east, the eastern column ($80.50^\circ\text{E}$) and the coastal offshore cell at $(13.00^\circ\text{N}, 80.25^\circ\text{E})$ are ocean cells!
> If you take a naive average of all 9 cells, the ocean `NaN` values will propagate and corrupt the entire city time series to `NaN`.
> You **must** mask out ocean cells and compute the mean across only valid land cells:
> $$R_t = \frac{1}{|K_{\text{valid}}|} \sum_{k \in K_{\text{valid}}} r_{k, t}$$

### 3.3 Trailing Accumulations (Rolling Windows)
Given daily precipitation $R_t$, we compute two time series:
1. **1-Day Rainfall ($R_{1d, t}$)**: Simply $R_t$. Captures acute, high-intensity cloudbursts that cause flash flooding.
2. **Trailing 3-Day Rainfall ($R_{3d, t}$)**:
   $$R_{3d, t} = R_t + R_{t-1} + R_{t-2}$$
   Captures cumulative soil saturation and reservoir catchment inflow. In Pandas:
   ```python
   rain_3d = daily_series.rolling(window=3, min_periods=1).sum()
   ```

---

## 4. Extreme Value Statistics & Climatology (Math for CS Students)

In CS machine learning courses, you are taught that everything follows a Gaussian (Normal) distribution because of the **Central Limit Theorem (CLT)**.
**CLT states**: The *sum* or *average* of many independent random variables approaches a Normal distribution.

**However, we do not care about the average rainfall!** We care about the **maximum** rainfall. The maximum of a random variable does **not** follow a Gaussian distribution. It follows the **Fisher-Tippett-Gnedenko Theorem**.

### 4.1 The Block Maxima Method & GEV Distribution
Instead of modeling every dry or light rain day, we divide the 124-year record into 1-year blocks. From each year $y \in [1901, 2024]$, we extract the **Annual Maximum**:
$$M_y = \max_{t \in \text{Year } y} R_t$$
This gives us a sample of $N = 124$ independent extreme events.

By the Fisher-Tippett theorem, the distribution of block maxima asymptotically converges to the **Generalized Extreme Value (GEV)** distribution:
$$F(x; \mu, \sigma, \xi) = \exp \left( - \left[ 1 + \xi \left( \frac{x - \mu}{\sigma} \right) \right]^{-1/\xi} \right)$$
where:
- $\mu \in \mathbb{R}$ is the **location** parameter (where the peak of extremes sits).
- $\sigma > 0$ is the **scale** parameter (how spread out the extremes are).
- $\xi \in \mathbb{R}$ is the **shape** parameter:
  - $\xi > 0$: Fréchet (heavy-tailed, extreme outliers are common).
  - $\xi < 0$: Weibull (bounded upper limit).
  - $\xi = 0$: **Gumbel** (exponential tail).

*(Note: `scipy.stats.genextreme` uses $c = -\xi$.)*

### 4.2 The Gumbel Distribution (Type I Extreme Value)
When $\xi = 0$, taking the limit $\xi \to 0$ transforms the GEV into the Gumbel distribution:
$$F(x; \mu, \sigma) = \exp \left( - \exp \left( - \frac{x - \mu}{\sigma} \right) \right)$$
The Gumbel distribution has only 2 parameters ($\mu, \sigma$). It is computationally simpler and far more stable than GEV when sample sizes are modest ($N \approx 100$).

### 4.3 Maximum Likelihood Estimation (MLE)
We fit the parameters $(\mu, \sigma)$ to our 124 annual maxima $\{M_1, M_2, \dots, M_{124}\}$ by maximizing the log-likelihood:
$$\ln L(\mu, \sigma) = -N \ln \sigma - \sum_{i=1}^N \left( \frac{M_i - \mu}{\sigma} \right) - \sum_{i=1}^N \exp \left( - \frac{M_i - \mu}{\sigma} \right)$$
In Python, this is solved via `scipy.stats.gumbel_r.fit(data)`.

### 4.4 Model Selection: GEV vs. Gumbel (AIC & Likelihood Ratio Test)
Should we use 3-parameter GEV or 2-parameter Gumbel?
In computer science, adding parameters always improves training loss, but risks overfitting. We use two statistical safeguards:
1. **Akaike Information Criterion (AIC)**:
   $$\text{AIC} = 2k - 2\ln L$$
   where $k$ is the number of parameters ($k=3$ for GEV, $k=2$ for Gumbel). We enforce Occam's razor: **Only select GEV if $\text{AIC}_{\text{GEV}} < \text{AIC}_{\text{Gumbel}} - 2$**.
2. **Likelihood Ratio (LR) Test**:
   Because Gumbel is a nested subset of GEV (constrained at $\xi = 0$), the test statistic:
   $$\Lambda = 2 \left( \ln L_{\text{GEV}} - \ln L_{\text{Gumbel}} \right) \sim \chi^2(1)$$
   If the $p$-value $> 0.05$, the extra shape parameter $\xi$ is not statistically significant.

#### The Result for Chennai:
- For 1-day rainfall: LR $p = 0.609$ ($> 0.05$).
- For 3-day rainfall: LR $p = 0.358$ ($> 0.05$).
- **Conclusion**: **Gumbel is selected for both series.** This prevents wild, unstable probability predictions for rare events.

### 4.5 Return Periods ($T$) and Return Levels ($z_T$)
- **Return Period ($T$)**: The average number of years between occurrences of a rainfall event exceeding a given threshold.
  $$T = \frac{1}{1 - F(z_T)}$$
  For example, a **10-year storm** has a probability of exceedance $P(X \ge z_{10}) = \frac{1}{10} = 0.10$ in any given year.
- **Return Level ($z_T$)**: The actual rainfall amount in millimeters corresponding to return period $T$. Inverting the Gumbel CDF gives:
  $$z_T = \mu - \sigma \ln \left( - \ln \left( 1 - \frac{1}{T} \right) \right)$$

### 4.6 Nonparametric Bootstrap Confidence Intervals
How confident are we in our 50-year return level estimate?
Instead of assuming asymptotic normality, we use the **Bootstrap Method**:
1. Take our 124 annual maxima observations.
2. Sample 124 values *with replacement* (Monte Carlo bootstrap) $B = 500$ times.
3. Fit the Gumbel distribution to each bootstrap replicate and calculate $z_T^{(b)}$.
4. Sort the 500 estimates and extract the $2.5\text{th}$ and $97.5\text{th}$ percentiles to establish empirical $95\%$ confidence bounds:
   $$\text{CI}_{95\%} = [z_{T, 0.025}^*, \; z_{T, 0.975}^*]$$

### 4.7 Climate Trend Analysis: Mann-Kendall & Sen's Slope
Is extreme rainfall in Chennai increasing over time due to climate change?
1. **Mann-Kendall Test**: A non-parametric rank test checking for monotonic upward or downward trends without assuming linearity.
   - For Chennai annual maxima: $p = 0.771$ (1-day) and $p = 0.902$ (3-day).
2. **Sen's Slope**: The median of slopes between all pairs of sample points:
   $$\text{Slope} = \operatorname{median} \left\{ \frac{M_j - M_i}{j - i} \right\}$$
   - Result: $-0.36\text{ mm/decade}$ (1-day) and $+0.26\text{ mm/decade}$ (3-day).
- **Takeaway**: Extreme rainfall events in Chennai have remained statistically stationary over the 124-year record. Therefore, fitting a stationary Gumbel distribution is methodologically valid.

---

## 5. The 4-Tier Operational Flood Architecture

Instead of arbitrary numbers, risk tiers are grounded in physical frequency:

```
+---------------+-------------------------------------------------------------+
| TIER          | SCIENTIFIC CRITERION                                        |
+---------------+-------------------------------------------------------------+
| Normal        | Default baseline state (< 95th percentile of wet days)      |
+---------------+-------------------------------------------------------------+
| Watch         | >= 95th empirical percentile of historical wet days         |
|               | (rain_1d >= 57.7 mm OR rain_3d >= 103.0 mm)                 |
+---------------+-------------------------------------------------------------+
| Alert         | >= 2-year return period on annual maxima                    |
|               | (rain_1d >= 113.7 mm OR rain_3d >= 202.8 mm)                |
+---------------+-------------------------------------------------------------+
| Emergency     | >= 10-year return period on annual maxima                   |
|               | (rain_1d >= 192.5 mm OR rain_3d >= 336.1 mm)                |
+---------------+-------------------------------------------------------------+
```

### 5.1 Escalation & Driver Diagnosis Algorithm
When an incoming observation $(R_{1d}, R_{3d})$ is received:
1. **Wet-Day Safeguard**: In India, IMD defines a wet day as $R \ge 2.5\text{ mm}$. If both $R_{1d} < 2.5$ and $R_{3d} < 2.5$, the tier is locked to **Normal**.
2. **Physical Invariant**: A 3-day sum can never be less than its last day: $R_{3d} = \max(R_{3d}, R_{1d})$.
3. **Escalation Logic**: The day escalates to the highest tier satisfied by **either** $R_{1d}$ or $R_{3d}$:
   $$\text{Tier} = \max(\text{Tier}(R_{1d}), \; \text{Tier}(R_{3d}))$$
4. **Dominant Driver Diagnosis**: Whichever accumulation window exhibits the higher return period / percentile severity is flagged as the driver (`"rain_1d"` for flash floods, `"rain_3d"` for volume buildup).

---

## 6. Decision Science: Analytic Hierarchy Process (AHP) & MCDA

Once a risk tier is identified, which actions should the civic commissioner authorize first?

### 6.1 The 5 Operational Criteria
We define 5 criteria evaluated on a $1\text{--}5$ benefit scale ($5 = \text{most favorable}$):
1. **Impact ($C_1$)**: Prevents severe loss of life or property damage.
2. **Urgency ($C_2$)**: Must be initiated immediately; delay causes compounding failure.
3. **Lead Time ($C_3$)**: Rapid deployment speed (Inverted: scored as mobilization agility).
4. **Affordability ($C_4$)**: Low resource cost (Inverted: scored as economic ease).
5. **Feasibility ($C_5$)**: Logistical simplicity and inter-agency coordination ease.

### 6.2 The Analytic Hierarchy Process (AHP) Algorithm
How do we calculate mathematically sound weights for these 5 criteria?
Invented by Thomas Saaty, AHP uses pairwise comparisons on a $1\text{--}9$ scale:

| Scale Value | Definition |
| :---: | :--- |
| **1** | Equal importance |
| **3** | Moderate importance of one over another |
| **5** | Strong importance |
| **7** | Very strong importance |
| **9** | Extreme importance |

We construct a reciprocal matrix $A \in \mathbb{R}^{5 \times 5}$ where $A_{ji} = \frac{1}{A_{ij}}$ and $A_{ii} = 1$:

$$A = \begin{pmatrix}
1 & 2 & 3 & 5 & 3 \\
1/2 & 1 & 2 & 4 & 2 \\
1/3 & 1/2 & 1 & 3 & 1 \\
1/5 & 1/4 & 1/3 & 1 & 1/2 \\
1/3 & 1/2 & 1 & 2 & 1
\end{pmatrix}$$

#### Computing Priority Weights (Eigenvector Method)
The weights vector $w$ is the normalized principal eigenvector of $A$:
$$A w = \lambda_{\max} w, \quad \text{subject to } \sum_{i=1}^5 w_i = 1$$

In Python:
```python
vals, vecs = np.linalg.eig(A)
k = int(np.argmax(vals.real))
w = np.abs(vecs[:, k].real)
w = w / w.sum()
```
This produces the exact weights:
- $\text{Impact}: \mathbf{40.85\%}$
- $\text{Urgency}: \mathbf{25.07\%}$
- $\text{Lead Time}: \mathbf{14.48\%}$
- $\text{Feasibility}: \mathbf{13.21\%}$
- $\text{Affordability}: \mathbf{6.40\%}$

#### Checking Matrix Consistency (CR)
Human judgment can be contradictory ($A > B$ and $B > C$ but $C > A$). Saaty proved that consistency can be measured using the maximum eigenvalue $\lambda_{\max}$:
1. **Consistency Index (CI)**:
   $$\text{CI} = \frac{\lambda_{\max} - n}{n - 1}$$
   Here $n=5$, $\lambda_{\max} = 5.0441 \implies \text{CI} = 0.0110$.
2. **Consistency Ratio (CR)**:
   $$\text{CR} = \frac{\text{CI}}{\text{RI}_n}$$
   where $\text{RI}_5 = 1.12$ is the empirical Random Index for a $5 \times 5$ random matrix.
   $$\mathbf{CR = \frac{0.0110}{1.12} = 0.0098}$$
   **Rule**: If $\text{CR} < 0.10$ ($10\%$), the matrix is statistically consistent and accepted. Here $\text{CR} < 1\%$, demonstrating near-perfect transitivity.

### 6.3 Simple Additive Weighting (SAW) Scoring
For any set of eligible actions, each action has ratings $x_{ij}$ for criterion $j$.
1. **Linear Max-Normalization**:
   $$r_{ij} = \frac{x_{ij}}{\max_k x_{kj}}$$
2. **Composite Score**:
   $$S_i = \sum_{j=1}^5 w_j \, r_{ij} = r_i \cdot w$$
3. **Sorting**: Sort actions in descending order of $S_i$. Rank 1 is top priority.

---

## 7. Sensitivity & Robustness Engineering

A critical requirement in computational engineering is verifying that your algorithm does not produce radically different rankings if weights change slightly.

### 7.1 One-At-A-Time (OAT) Perturbation
Each weight is shifted by $\pm 25\%$, re-normalizing the others. We measure **Kendall's rank correlation ($\tau$)** against the baseline.
- **Result**: Kendall's $\tau$ remains between $0.944$ and $1.000$. The top action (`control_room`) never changes rank.

### 7.2 Dirichlet Monte Carlo Simulation
The Dirichlet distribution is a probability distribution over probability simplexes (vectors that sum to 1).
We sample $N = 2,000$ weight vectors from:
$$w \sim \operatorname{Dirichlet}(\alpha = 50 \cdot w_{\text{base}})$$
For every draw, we re-rank all 9 actions and compute Kendall's $\tau$.
- **Result**: Mean Kendall's $\tau = \mathbf{0.7984}$, proving that action rankings are robust against random noise and subjective variance.

---

## 8. Step-by-Step Implementation Blueprint (Code Architecture)

If you are rebuilding this from scratch, implement these 8 modular files in order:

### Module 1: `drainage_rec/data/download.py`
- Connects to IMD archive endpoint via `requests.post(ARCHIVE_URL, data={'rain': year}, stream=True)`.
- Validates downloaded file size against $(365 \text{ or } 366) \times \text{Grid Bytes}$.
- Uses `ThreadPoolExecutor(max_workers=3)` to fetch years in parallel.

### Module 2: `drainage_rec/data/extract.py`
- Loads `.grd` via `xarray`.
- Slices latitude $[12.75, 13.25]$ and longitude $[80.0, 80.5]$.
- Drops ocean cells where rainfall is `NaN`.
- Computes daily mean $\implies$ saves `data/interim/chennai_daily.csv`.

### Module 3: `drainage_rec/features/accumulation.py` & `annual_max.py`
- Computes `rain_1d` and `rain_3d` rolling sums.
- Extracts calendar year maximums, filtering out any year with $< 330$ days of data.

### Module 4: `drainage_rec/stats/distributions.py` & `return_period.py`
- Fits GEV and Gumbel distributions via `scipy.stats`.
- Computes log-likelihood, AIC, and LR $\chi^2$ test. Selects Gumbel.
- Computes return levels for $T \in [2, 5, 10, 25, 50, 100]$ with 500 bootstrap replicates for $95\%$ CIs.

### Module 5: `drainage_rec/risk/tiers.py`
- Builds `RiskModel` containing fitted distribution parameters and empirical wet-day CDF.
- Implements `assess(rain_1d, rain_3d) \implies {'tier': ..., 'driver': ..., 'assessment': ...}`.

### Module 6: `drainage_rec/decision/ahp.py` & `matrix.py`
- Implements `pairwise_matrix` and solves for principal eigenvector and consistency ratio $\text{CR}$.
- Implements `score_actions` with max-normalization and dot-product weighting.

### Module 7: `drainage_rec/pipeline.py`
- Coordinates execution: reads daily series $\implies$ features $\implies$ fits $\implies$ classifies $\implies$ scores actions $\implies$ writes CSV and JSON artifacts to `data/processed/`.

### Module 8: `drainage_rec/cli.py` & `dashboard/app.py`
- Implements CLI subcommands (`download`, `pipeline`, `recommend`).
- Implements Streamlit web interface with interactive Plotly return level curves and what-if sliders.

---

## 9. Validation & Historical Backtesting

To prove that the model works in the real world, test it against Chennai's major disaster dates:

```
+------------------------------------+------------+-------------+----------------+
| Historical Event                   | Peak Date  | Peak Tier   | Inferred T (y) |
+------------------------------------+------------+-------------+----------------+
| Chennai Floods (Nov 2015)          | 2015-11-16 | Emergency   | 96.5 years     |
| Chennai Floods (Dec 2015 Deluge)   | 2015-12-02 | Emergency   | 394.6 years    |
| Cyclone Michaung (Dec 2023)        | 2023-12-05 | Emergency   | 19.4 years     |
| Chennai Floods (Nov 2021)          | 2021-11-11 | Alert       | 4.3 years      |
| Cyclone Vardah (Dec 2016)          | 2016-12-13 | Alert       | 2.0 years      |
| Chennai Floods (Oct 2005)          | 2005-10-28 | Emergency   | 19.9 years     |
| Chennai Floods (Dec 2005)          | 2005-12-03 | Emergency   | 38.5 years     |
+------------------------------------+------------+-------------+----------------+
```

### Benchmarks:
- **Hit Rate on Alert+**: **100% (7/7 events)**
- **Hit Rate on Emergency**: **71.4% (5/7 events)**
- **Zero Missed Catastrophes**: Every major historical flood event triggered an operational Alert or Emergency.

---

## 10. Engineering Gotchas & Edge Cases

When coding this system yourself, beware of these specific bugs:

1. **Leap Year Byte Offsets**:
   A common bug when reading raw `.grd` files is hardcoding $365$ days. Leap years have $366$ days ($1$ extra float matrix = $129 \times 135 \times 4 = 69,660$ extra bytes). Always check `calendar.isleap(year)`!
2. **Incomplete Downloads**:
   The IMD server frequently drops HTTP connections halfway through a file. Always download to a temporary `.part` file, verify `file_size == expected_size`, and only then rename to `.grd`.
3. **Rolling Window NaN Warmup**:
   `daily.rolling(3).sum()` produces `NaN` for the first 2 days unless you pass `min_periods=1`.
4. **Physical Invariant Enforcement**:
   A 3-day accumulated sum cannot physically be less than its last 1-day reading. In `assess(rain_1d, rain_3d)`, always enforce `rain_3d = max(rain_3d, rain_1d)`.
5. **Dry Day Tier Bleed**:
   If an algorithm checks only return periods, a 0 mm day might theoretically match a low mathematical percentile if dry days are included. Always gate escalation behind the wet-day threshold ($R \ge 2.5\text{ mm}$).
6. **Eigensolver Imaginary Components**:
   Numerical solvers (`np.linalg.eig`) return complex numbers (`complex128`) due to floating point precision. Always take `.real` and `np.abs()` when extracting the principal eigenvector!
