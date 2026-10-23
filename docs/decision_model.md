# Decision Model & Multi-Criteria Analysis (AHP)

This document provides a detailed breakdown of the decision-support system implemented in `drainage-rec`, explaining how rainfall-induced risk tiers trigger and prioritize municipal preparedness interventions.

---

## 🎯 1. Operational Decision Context

Municipal flood preparedness requires orchestrating diverse public agencies:
- **Greater Chennai Corporation (GCC)**: Drain desilting, culvert clearing, ward-level response teams, relief centers.
- **Water Resources Department (WRD)**: Canal regulators, reservoir sluice gates (Chembarambakkam, Puzhal, Poondi).
- **Tamil Nadu Generation and Distribution Corporation (TANGEDCO)**: Substation safety and pre-emptive power isolation.
- **Disaster Response Forces (SDRF / NDRF)**: Inundation zone rescue boats and evacuation logistics.

Civic managers cannot execute every action simultaneously due to budget constraints, physical equipment limits, and workforce fatigue. Furthermore, an action vital days before a cyclone (e.g. canal desilting) becomes futile or hazardous during peak downpour. The decision model provides an objective, transparent, and defensible prioritization engine.

---

## ⚖️ 2. The Five Operational Criteria

Actions are rated on a $1\text{--}5$ integer scale ($5$ being most favorable) across 5 criteria:

1. **Impact ($C_1$)**:
   - *Definition*: The capacity of the action to mitigate severe flooding, prevent loss of life, and protect critical urban infrastructure.
   - *High score ($5$)*: Directly prevents catastrophic flooding or saves lives (e.g. boat rescues, pump deployments).
   - *Low score ($1\text{--}2$)*: Indirect or localized benefit.

2. **Urgency ($C_2$)**:
   - *Definition*: The time sensitivity of initiating the action before peak rainfall commences.
   - *High score ($5$)*: Must be deployed immediately; delays cause compounding failure (e.g. control room activation, rescue deployments).
   - *Low score ($1\text{--}2$)*: Can be staged or delayed without immediate risk escalation.

3. **Lead Time ($C_3$)**:
   - *Definition*: How rapidly the intervention can be mobilized once ordered. (Inverted: scored as mobilization speed).
   - *High score ($5$)*: Near-instantaneous execution (< 1 hour; e.g. SMS advisories, power isolation).
   - *Low score ($1\text{--}2$)*: Requires extended multi-day mobilization (e.g. desilting major canals, opening physical shelters).

4. **Affordability ($C_4$)**:
   - *Definition*: Financial and resource efficiency (Inverted: scored as economic feasibility).
   - *High score ($5$)*: Minimal direct capital outlay (e.g. reservoir coordination, digital advisories, clearing surface grates).
   - *Low score ($1\text{--}2$)*: High capital, fuel, and personnel costs (e.g. desilting machinery, continuous shelter provisioning).

5. **Feasibility ($C_5$)**:
   - *Definition*: Operational, technical, and inter-agency ease of execution under monsoon conditions.
   - *High score ($5$)*: Standard operating procedure, within single-agency control (e.g. municipal control room, road inlet clearing).
   - *Low score ($1\text{--}2$)*: Complex multi-departmental coordination, perilous field conditions.

---

## 🧮 3. Analytic Hierarchy Process (AHP) Weighting

### 3.1 Pairwise Comparison Matrix
Criteria importance is established using Saaty's fundamental 9-point scale ($1 = \text{Equal}$, $3 = \text{Moderate}$, $5 = \text{Strong}$, $7 = \text{Very Strong}$, $9 = \text{Extreme}$). Judgments are specified in `configs/weights.yaml`:

| Criterion | Impact | Urgency | Lead Time | Affordability | Feasibility |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **Impact** | $1$ | $2$ | $3$ | $5$ | $3$ |
| **Urgency** | $1/2$ | $1$ | $2$ | $4$ | $2$ |
| **Lead Time** | $1/3$ | $1/2$ | $1$ | $3$ | $1$ |
| **Affordability** | $1/5$ | $1/4$ | $1/3$ | $1$ | $1/2$ |
| **Feasibility** | $1/3$ | $1/2$ | $1$ | $2$ | $1$ |

### 3.2 Principal Eigenvector & Weights
The weight vector $w$ corresponds to the principal eigenvector of matrix $A$:
$$\begin{aligned}
w_{\text{Impact}} &= 0.4085 \quad (40.85\%) \\
w_{\text{Urgency}} &= 0.2507 \quad (25.07\%) \\
w_{\text{Lead Time}} &= 0.1448 \quad (14.48\%) \\
w_{\text{Feasibility}} &= 0.1321 \quad (13.21\%) \\
w_{\text{Affordability}} &= 0.0640 \quad (6.40\%)
\end{aligned}$$

### 3.3 Consistency Verification
- Principal eigenvalue: $\lambda_{\max} = 5.0441$
- Consistency Index: $\text{CI} = \frac{5.0441 - 5}{5 - 1} = 0.0110$
- Random Index for $n = 5$: $\text{RI} = 1.12$
- **Consistency Ratio**:
  $$\text{CR} = \frac{0.0110}{1.12} = \mathbf{0.0098} \quad (< 0.10)$$
The matrix exhibits negligible internal contradiction ($\text{CR} < 1\%$).

---

## 📋 4. Preparedness Actions Catalog & Scores

The catalog comprises 9 municipal interventions configured in `configs/actions.yaml`. Each action specifies a **minimum trigger tier**:

| Action ID | Action Name | Min Tier | Impact | Urgency | Lead Time | Affordability | Feasibility | SAW Score | Overall Rank |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `control_room` | Activate 24x7 flood control room and ward-level teams | Alert | 4 | 5 | 4 | 4 | 5 | **0.8766** | 1 |
| `rescue_teams` | Pre-deploy NDRF/SDRF boats and rescue teams | Emergency | 5 | 5 | 3 | 2 | 3 | **0.8509** | 2 |
| `pump_deployment` | Pre-position dewatering pumps at known low-lying subways | Alert | 5 | 4 | 3 | 3 | 4 | **0.8399** | 3 |
| `power_isolation` | Pre-emptive power isolation in inundation-prone feeders | Emergency | 4 | 4 | 5 | 4 | 4 | **0.8290** | 4 |
| `shelter_readiness` | Open relief shelters and stock food, water, medicines | Emergency | 5 | 5 | 2 | 2 | 3 | **0.8219** | 5 |
| `reservoir_release` | Coordinate staged releases from Chembarambakkam / Puzhal | Alert | 5 | 4 | 2 | 5 | 3 | **0.8102** | 6 |
| `public_advisory` | Issue public rainfall advisory via SMS / social media | Watch | 3 | 4 | 5 | 5 | 5 | **0.7865** | 7 |
| `drain_inspection` | Inspect and clear storm-drain inlets and culverts | Watch | 3 | 3 | 4 | 5 | 5 | **0.7074** | 8 |
| `desilting` | Targeted desilting of major canals (Buckingham, Cooum) | Watch | 4 | 2 | 1 | 2 | 3 | **0.5608** | 9 |

---

## 🔄 5. Dynamic Tier Filtering & Escalation

Actions trigger cumulatively: **any action triggered at a lower tier remains active in all higher tiers**.

### 5.1 Watch Tier (Early Mobilization)
Triggered when either 1-day or 3-day rainfall reaches the 95th percentile ($R_{1d} \ge 57.7\text{ mm}$ or $R_{3d} \ge 103.0\text{ mm}$):
1. **`public_advisory`** (Score: 0.786, Rank: 1 in tier): Alert residents and field crews.
2. **`drain_inspection`** (Score: 0.707, Rank: 2 in tier): Clear debris from street grates and culverts.
3. **`desilting`** (Score: 0.561, Rank: 3 in tier): Target choke points in primary drainage arteries.

### 5.2 Alert Tier (Active Response)
Triggered at a 2-year return period ($R_{1d} \ge 113.7\text{ mm}$ or $R_{3d} \ge 202.8\text{ mm}$). Includes all Watch actions plus:
1. **`control_room`** (Score: 0.877, Rank: 1 in tier)
2. **`pump_deployment`** (Score: 0.840, Rank: 2 in tier)
3. **`reservoir_release`** (Score: 0.810, Rank: 3 in tier)
4. *Followed by Watch actions (`public_advisory`, `drain_inspection`, `desilting`).*

### 5.3 Emergency Tier (Disaster Mitigation)
Triggered at a 10-year return period ($R_{1d} \ge 192.5\text{ mm}$ or $R_{3d} \ge 336.1\text{ mm}$). Unlocks all 9 actions:
1. **`control_room`** (Score: 0.877, Rank: 1)
2. **`rescue_teams`** (Score: 0.851, Rank: 2)
3. **`pump_deployment`** (Score: 0.840, Rank: 3)
4. **`power_isolation`** (Score: 0.829, Rank: 4)
5. **`shelter_readiness`** (Score: 0.822, Rank: 5)
6. **`reservoir_release`** (Score: 0.810, Rank: 6)
7. **`public_advisory`** (Score: 0.786, Rank: 7)
8. **`drain_inspection`** (Score: 0.707, Rank: 8)
9. **`desilting`** (Score: 0.561, Rank: 9)

---

## 🔬 6. Sensitivity & Robustness Evaluation

### 6.1 One-At-A-Time (OAT) Perturbations ($\pm 25\%$)
Every criterion weight is altered by $\pm 25\%$ while re-normalizing remaining weights. Across all 10 perturbations (5 criteria $\times$ 2 directions):
- **Top-1 Action (`control_room`)**: Stays #1 in **100%** of cases.
- **Top-3 Action Overlap**: **100% overlap** across all perturbations.
- **Kendall's $\tau$**: Ranges between **0.944 and 1.000**, confirming that minor subjective shifts do not alter decision outcomes.

### 6.2 Dirichlet Monte Carlo (2,000 Draws)
Weight vectors were randomly generated from $\operatorname{Dirichlet}(50 \cdot w_{\text{AHP}})$:
- **`control_room`**: Mean rank $= 1.34$, $95\%\text{ CI} = [1, 3]$, Probability of rank 1 $= 73.4\%$.
- **`rescue_teams`**: Mean rank $= 2.21$, $95\%\text{ CI} = [1, 4]$, Probability of rank 2 $= 51.2\%$.
- **`pump_deployment`**: Mean rank $= 2.85$, $95\%\text{ CI} = [1, 4]$.
- **Mean Kendall's $\tau$ across 2,000 runs**: $\mathbf{0.7984}$, establishing high systemic stability.
