# Mathematical & Statistical Methodology

This document outlines the theoretical, mathematical, and hydrological foundations implemented in `drainage-rec`.

---

## 1. Spatial Aggregation & Gridded Data Processing

### 1.1 Study Area & Land-Sea Masking
The India Meteorological Department (IMD) provides gridded daily rainfall across India on a regular $0.25^\circ \times 0.25^\circ$ latitude-longitude mesh. For Chennai, the study area spans:
$$\text{Latitude: } 12.75^\circ\text{N} \le \phi \le 13.25^\circ\text{N}, \quad \text{Longitude: } 80.0^\circ\text{E} \le \lambda \le 80.5^\circ\text{E}$$

This defines a $3 \times 3$ block of grid cells centered at multiples of $0.25^\circ$. Because Chennai is situated on the Coromandel Coast adjacent to the Bay of Bengal:
- The eastern grid column ($\lambda = 80.5^\circ\text{E}$) lies entirely over the ocean.
- The cell at $(13.0^\circ\text{N}, 80.25^\circ\text{E})$ is classified as maritime/missing in the IMD land mask.

The system filters out invalid/sea cells and computes the daily city-wide rainfall series $R_t$ as the spatial mean of the remaining valid land cells:
$$R_t = \frac{1}{|K_{\text{valid}}|} \sum_{k \in K_{\text{valid}}} r_{k, t}$$
where $r_{k, t}$ is the daily precipitation recorded at cell $k$ on day $t$. All negative values are clipped to $0.0\text{ mm}$.

---

## 2. Dual-Duration Feature Engineering

Urban flood risk in Chennai is driven by two distinct hydrological mechanisms:
1. **Acute High-Intensity Rain (Flash Flooding)**: Localized cloudbursts or intense convective downpours overwhelm stormwater drains, canal inlets, and road culverts within hours.
2. **Sustained Volumetric Accumulation (Regional Inundation & Reservoir Overflow)**: Multi-day rainfall saturates soil, raises the water table, fills major retention basins (Chembarambakkam, Puzhal, Cholavaram, Poondi), and causes canal spillovers (Cooum River, Adyar River, Buckingham Canal).

To account for both mechanisms simultaneously, the system evaluates:
- **1-Day Rainfall ($R_{1d, t}$)**:
  $$R_{1d, t} = R_t$$
- **Trailing 3-Day Accumulated Rainfall ($R_{3d, t}$)**:
  $$R_{3d, t} = \sum_{i=0}^{2} R_{t-i} = R_t + R_{t-1} + R_{t-2}$$

---

## 3. Extreme Value Theory (EVT) & Block Maxima

### 3.1 Annual Maxima Series (AMS)
Extreme precipitation modeling uses the **Block Maxima** approach. For each calendar year $y \in [1901, 2024]$ and for each accumulation duration $d \in \{1d, 3d\}$, the annual maximum is extracted:
$$M_{d, y} = \max_{t \in \text{Year } y} R_{d, t}$$

To avoid downward bias from incomplete years, any year with fewer than $330$ recorded daily observations is dropped from the fitting sample. For Chennai's 1901–2024 record, all 124 years have complete coverage ($N = 124$).

### 3.2 Generalized Extreme Value (GEV) Distribution
By the Fisher-Tippett-Gnedenko theorem, the normalized maximum of independent and identically distributed random variables converges to the GEV family:
$$F_{\text{GEV}}(x; \mu, \sigma, \xi) = \exp \left( - \left[ 1 + \xi \left( \frac{x - \mu}{\sigma} \right) \right]^{-1/\xi} \right)$$
defined on $\{x : 1 + \xi (x - \mu)/\sigma > 0\}$, where:
- $\mu \in \mathbb{R}$ is the location parameter,
- $\sigma > 0$ is the scale parameter,
- $\xi \in \mathbb{R}$ is the shape parameter.

*(Note: In `scipy.stats.genextreme`, the shape parameter is defined as $c = -\xi$. The codebase adheres to hydrological convention, reporting $\xi = -c$.)*

- If $\xi > 0$, the distribution is heavy-tailed (Type II / Fréchet).
- If $\xi < 0$, the distribution has a bounded upper tail (Type III / Weibull).
- As $\xi \to 0$, the distribution converges to the Type I Gumbel distribution.

### 3.3 Gumbel Distribution
The Gumbel (Type I Extreme Value) cumulative distribution function is:
$$F_{\text{Gumbel}}(x; \mu, \sigma) = \exp \left( - \exp \left( - \frac{x - \mu}{\sigma} \right) \right), \quad x \in \mathbb{R}$$

### 3.4 Model Selection: AIC & Likelihood Ratio Test
Both GEV and Gumbel models are fitted via Maximum Likelihood Estimation (MLE). To select the most parsimonious model without overfitting:

1. **Akaike Information Criterion (AIC)**:
   $$\text{AIC} = 2k - 2\ln(L)$$
   where $k$ is the number of estimated parameters ($k=2$ for Gumbel, $k=3$ for GEV) and $L$ is the maximized likelihood. GEV is only adopted if it improves upon Gumbel by more than 2 AIC units:
   $$\text{Select GEV} \iff \text{AIC}_{\text{GEV}} < \text{AIC}_{\text{Gumbel}} - 2$$

2. **Likelihood Ratio (LR) Test**:
   Because Gumbel is the nested sub-model of GEV constrained at $\xi = 0$, the test statistic:
   $$\Lambda = 2 \left( \ln L_{\text{GEV}} - \ln L_{\text{Gumbel}} \right)$$
   asymptotically follows a chi-squared distribution with 1 degree of freedom: $\Lambda \sim \chi^2(1)$.

#### Empirical Results for Chennai (1901–2024):
- **1-Day Rainfall**: $\Lambda = 0.262$, $p = 0.609$ ($p > 0.05$). GEV shape $\xi$ is not statistically distinguishable from 0. **Gumbel is selected**.
- **3-Day Rainfall**: $\Lambda = 0.846$, $p = 0.358$ ($p > 0.05$). **Gumbel is selected**.

Both series in Chennai are best characterized by the 2-parameter Gumbel distribution, avoiding unstable heavy-tail inflation during long return period extrapolations.

---

## 4. Return Periods, Return Levels & Bootstrap Confidence Bounds

### 4.1 Return Period ($T$) and Return Level ($z_T$)
The return period $T$ (in years) represents the average recurrence interval between exceedances of a threshold:
$$T = \frac{1}{1 - F(z_T)}$$

Inverting the distribution gives the return level $z_T$ (quantile function or percent point function $\text{PPF}$):
- For Gumbel:
  $$z_T = \mu - \sigma \ln \left( - \ln \left( 1 - \frac{1}{T} \right) \right)$$
- For GEV:
  $$z_T = \mu + \frac{\sigma}{\xi} \left[ \left( - \ln \left( 1 - \frac{1}{T} \right) \right)^{-\xi} - 1 \right]$$

### 4.2 Nonparametric Bootstrap Confidence Intervals
To quantify sampling uncertainty in extreme quantiles without relying on asymptotic normal approximations, the system implements a nonparametric bootstrap:
1. Resample $N = 124$ annual maxima with replacement: $\{M^{*(b)}_1, \dots, M^{*(b)}_N\}$ for $b = 1, \dots, B$ ($B = 500$).
2. Fit the chosen distribution to each bootstrap sample.
3. Compute the bootstrap return level $z_T^{*(b)}$ for standard return periods $T \in \{2, 5, 10, 25, 50, 100\}$.
4. Derive the $95\%$ confidence interval using empirical percentiles:
   $$\text{CI}_{95\%} = \left[ q_{0.025}(z_T^*), \; q_{0.975}(z_T^*) \right]$$

---

## 5. Climatology & Non-Parametric Trend Detection

### 5.1 Mann-Kendall Test for Trend
To evaluate whether annual extreme rainfall in Chennai exhibits a statistically significant monotonic trend, the rank-based non-parametric Mann-Kendall test is applied:
$$S = \sum_{i=1}^{n-1} \sum_{j=i+1}^n \operatorname{sgn}(M_j - M_i)$$
The test statistic $Z$ and Kendall's rank correlation $\tau$ assess trend significance under $H_0: \text{no trend}$.

### 5.2 Sen's Slope Estimator
The magnitude of the trend is estimated using the robust, outlier-resistant Sen's slope:
$$\beta = \operatorname{median} \left\{ \frac{M_j - M_i}{j - i} : 1 \le i < j \le n \right\}$$
Reported as decadal rate ($10 \times \beta\text{ mm/decade}$).

### 5.3 Split-Period Analysis
The 124-year record is split into pre-1960 ($1901\text{--}1959$, $n=59$) and post-1960 ($1960\text{--}2024$, $n=65$) sub-periods to assess structural shifts:
- **Welch's t-test**: Tests difference in sub-period means without assuming equal variances.
- **Mann-Whitney U test**: Non-parametric test for difference in distribution locations.

#### Empirical Results:
- `rain_1d`: Mann-Kendall $p = 0.771$, Sen's slope $-0.36\text{ mm/decade}$ (no statistically significant trend).
- `rain_3d`: Mann-Kendall $p = 0.902$, Sen's slope $+0.26\text{ mm/decade}$ (no statistically significant trend).
- Stationary extreme value distributions remain statistically sound across the 124-year baseline.

---

## 6. Four-Tier Operational Flood Risk Architecture

### 6.1 Tier Definitions & Criteria
Urban drainage agencies require tiered operational alert levels that balance false alarms against missed emergencies:

| Tier | Hydrological Criterion | Physical Meaning & Civic Response |
| :--- | :--- | :--- |
| **Normal** | Default state (< 95th percentile) | Baseline city operations; routine silt maintenance. |
| **Watch** | $\ge 95\text{th}$ empirical percentile on wet days ($R \ge 2.5\text{ mm}$) | Unusually wet conditions; inspect culverts, clear grates, issue advisories. |
| **Alert** | $\ge 2\text{-year}$ return period on annual maxima | Exceeds median annual peak; pre-position dewatering pumps, activate 24x7 control room, coordinate reservoir gates. |
| **Emergency**| $\ge 10\text{-year}$ return period on annual maxima | Severe flood event; open relief shelters, deploy NDRF/SDRF rescue boats, isolate electrical feeders. |

### 6.2 Escalation & Dominant Driver Diagnosis
For any pair $(R_{1d}, R_{3d})$:
1. Wet days are defined by $R \ge 2.5\text{ mm}$ (IMD definition). If both $R_{1d} < 2.5\text{ mm}$ and $R_{3d} < 2.5\text{ mm}$, the tier is strictly **Normal**.
2. A day escalates to the highest tier for which **either** the 1-day or the 3-day accumulation meets or exceeds the tier's threshold:
   $$\text{Tier} = \max \left( \text{Tier}(R_{1d}), \; \text{Tier}(R_{3d}) \right)$$
3. **Driver Diagnosis**: The system identifies the driving factor based on whichever accumulation exhibits the higher return period / percentile severity:
   $$\text{Driver} = \operatorname{argmax}_{d \in \{1d, 3d\}} \left( T_d, P_d \right)$$

---

## 7. Multi-Criteria Decision Analysis (AHP + MCDA)

### 7.1 Operational Criteria
Preparedness actions are evaluated across 5 fundamental operational criteria:
1. **Impact ($C_1$)**: Degree of flood risk reduction and life/property protection.
2. **Urgency ($C_2$)**: Criticality of immediate mobilization before peak inundation.
3. **Lead Time ($C_3$)**: Feasibility of completing the action within available forecast windows.
4. **Affordability ($C_4$)**: Municipal resource efficiency and deployment cost.
5. **Feasibility ($C_5$)**: Logistical, technical, and inter-agency ease of execution.

All criteria are scored on a benefit scale ($1$ to $5$, where $5$ is most favorable).

### 7.2 Analytic Hierarchy Process (AHP)
Criteria weights are derived using Saaty’s pairwise comparison matrix $A \in \mathbb{R}^{5 \times 5}$ on the standard $1\text{--}9$ fundamental scale:
$$A = \begin{pmatrix} 1 & a_{12} & a_{13} & a_{14} & a_{15} \\ 1/a_{12} & 1 & a_{23} & a_{24} & a_{25} \\ \vdots & \vdots & \ddots & \vdots & \vdots \\ 1/a_{15} & 1/a_{25} & \dots & 1/a_{45} & 1 \end{pmatrix}$$

The priority weight vector $w$ corresponds to the normalized principal eigenvector of $A$:
$$A w = \lambda_{\max} w, \quad \sum_{i=1}^n w_i = 1$$

### 7.3 Consistency Ratio Verification
To verify transitivity and consistency in human judgments:
1. **Consistency Index (CI)**:
   $$\text{CI} = \frac{\lambda_{\max} - n}{n - 1}, \quad n = 5$$
2. **Consistency Ratio (CR)**:
   $$\text{CR} = \frac{\text{CI}}{\text{RI}_n}$$
   where $\text{RI}_5 = 1.12$ is Saaty's Random Consistency Index for $n=5$. A matrix is deemed acceptable if $\text{CR} < 0.10$.

#### Project AHP Parameters:
- Derived weights:
  - $\text{Impact}: 0.4085$ ($40.8\%$)
  - $\text{Urgency}: 0.2507$ ($25.1\%$)
  - $\text{Lead Time}: 0.1448$ ($14.5\%$)
  - $\text{Feasibility}: 0.1321$ ($13.2\%$)
  - $\text{Affordability}: 0.0640$ ($6.4\%$)
- $\lambda_{\max} = 5.0441$, $\text{CI} = 0.0110$, $\mathbf{CR = 0.0098} \ll 0.10$ (exceptionally consistent).

### 7.4 Simple Additive Weighting (SAW)
For a set of triggered actions $\mathcal{A}_{\text{tier}}$, performance ratings $x_{ij}$ ($i \in \text{actions}, j \in \text{criteria}$) are normalized:
$$r_{ij} = \frac{x_{ij}}{\max_k x_{kj}}$$
The composite utility score $S_i$ is computed via additive synthesis:
$$S_i = \sum_{j=1}^5 w_j \, r_{ij}, \quad S_i \in [0, 1]$$
Actions are ranked in descending order of $S_i$ ($\text{Rank } 1 = \text{highest priority}$).

---

## 8. Sensitivity & Robustness Analysis

To guarantee that municipal action rankings are not brittle to subjective AHP weighting, two sensitivity analyses are executed:

### 8.1 One-At-A-Time (OAT) Perturbation
Each criterion weight $w_k$ is individually perturbed by $\pm 25\%$:
$$w'_k = w_k (1 \pm 0.25), \quad w'_j = w_j \frac{1 - w'_k}{1 - w_k} \quad (\forall j \ne k)$$
For every perturbation, the system records:
- **Top-1 Preservation**: Does the #1 ranked action remain unchanged?
- **Top-3 Overlap**: Proportion of original top-3 actions that remain in the top 3.
- **Kendall's $\tau$**: Rank correlation coefficient between base ranking and perturbed ranking.

### 8.2 Dirichlet Monte Carlo Simulation
To test joint parameter variations, $N = 2,000$ weight vectors are sampled from a Dirichlet distribution centered on the AHP weights:
$$w^{(s)} \sim \operatorname{Dirichlet}(\alpha_0 w_1, \alpha_0 w_2, \dots, \alpha_0 w_5)$$
with concentration parameter $\alpha_0 = 50$.
For each draw, actions are rescored and reranked. The system outputs:
- Empirical probability that action $i$ retains its base rank ($P(\text{Rank} = r_{\text{base}})$).
- $95\%$ empirical confidence bounds for action rank $[r_{2.5\%}, r_{97.5\%}]$.
- Overall mean Kendall's $\tau = 0.7984$, demonstrating robust stability under substantial parameter variance.
