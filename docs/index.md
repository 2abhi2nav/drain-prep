# Chennai Urban Drainage Preparedness Recommender

Welcome to the technical and developer documentation for **`drainage-rec`** (`drain-prep`), an operational decision-support system designed to translate historical and incoming rainfall forecasts into actionable, risk-tiered municipal preparedness workflows for Chennai, India.

---

## 🌧️ System Purpose & Overview

Urban flooding in coastal metropolises like Chennai is shaped by intense, localized precipitation during the Northeast Monsoon (October–December), flat coastal topography, high soil saturation, and constrained drainage outlets into the Bay of Bengal. During severe hydrometeorological events, civic authorities (Greater Chennai Corporation - GCC, Tamil Nadu Disaster Management Authority - TNDMA, Water Resources Department - WRD) face two critical questions under strict time constraints:

1. **What is the true severity of the rainfall event?** Is it driven by short-duration acute intensity (1-day flash flooding) or sustained multi-day volume (3-day cumulative runoff and reservoir pressure)?
2. **Which municipal interventions should be executed first?** With limited resources (crews, pumps, shelters, heavy desilting machinery), how can actions be prioritized objectively across operational criteria like impact, urgency, lead time, affordability, and feasibility?

`drainage-rec` bridges extreme value statistics and operational decision science:
- **124-Year Rainfall Climatology (1901–2024)**: Ingests 0.25° gridded daily precipitation from the India Meteorological Department (IMD) over Chennai, masking maritime grid cells and aggregating valid land cells.
- **Dual-Duration Feature Engineering**: Simultaneously computes 1-day acute rainfall and trailing 3-day accumulated rainfall.
- **Extreme Value Modeling**: Fits Generalized Extreme Value (GEV) and Gumbel distributions to block maxima, using Akaike Information Criterion (AIC) and Likelihood Ratio tests to model return periods ($T$) and return levels with bootstrap confidence intervals.
- **4-Tier Operational Flood Risk Architecture**: Classifies risk into **Normal**, **Watch**, **Alert**, and **Emergency** tiers using empirical percentiles and return periods.
- **Multi-Criteria Decision Analysis (AHP + MCDA)**: Prioritizes 9 critical municipal actions using Saaty’s Analytic Hierarchy Process (AHP) and Simple Additive Weighting (SAW), evaluated against Dirichlet Monte Carlo and One-At-A-Time sensitivity analyses.
- **Interactive Decision Dashboard**: A FastAPI + Plotly web interface with real-time what-if scenario testing, rainfall-model diagnostics, and zone-level crew allocation.

---

## 📚 Documentation Index

Explore the detailed architecture, mathematical methodologies, data specifications, and developer guides:

| Document | Description |
| :--- | :--- |
| [**CSE Student & Developer Guide**](file:///c:/Users/krish/Desktop/dev/drain-prep/docs/explanation.md) | **Complete blueprint for Computer Science students**: In-depth theoretical walkthrough, math intuition (EVT, AHP, Dirichlet Monte Carlo), step-by-step modular code architecture, and engineering edge cases needed to rebuild this system from scratch. |
| [**Architecture & Design**](file:///c:/Users/krish/Desktop/dev/drain-prep/docs/architecture.md) | High-level system architecture, module layout, data flow through ingestion, transformation, risk classification, decision modeling, and the FastAPI web presentation layer. |
| [**Mathematical & Statistical Methodology**](file:///c:/Users/krish/Desktop/dev/drain-prep/docs/methodology.md) | Mathematical theory covering Block Maxima, GEV vs. Gumbel fitting, AIC model selection, Return Periods, Bootstrap CIs, Mann-Kendall & Sen's slope trends, ECDF, AHP, and Dirichlet Monte Carlo. |
| [**Data Pipeline & Ingestion**](file:///c:/Users/krish/Desktop/dev/drain-prep/docs/data_pipeline.md) | IMD gridded binary extraction, spatial masking, rolling accumulations, pipeline stages, and file schemas for raw, interim, and processed data. |
| [**Decision Model & AHP**](file:///c:/Users/krish/Desktop/dev/drain-prep/docs/decision_model.md) | Operational criteria, Saaty pairwise comparison matrix, consistency ratio verification, municipal actions catalog, dynamic tier filtering, and sensitivity analysis. |
| [**Validation & Benchmarks**](file:///c:/Users/krish/Desktop/dev/drain-prep/docs/validation_and_benchmarks.md) | Empirical validation against historical flood events (2005, 2015, 2016, 2021, 2023), hit-rate analysis, alert episode extraction, and ranking stability benchmarks. |
| [**CLI & Developer API**](file:///c:/Users/krish/Desktop/dev/drain-prep/docs/cli_and_api.md) | Complete CLI usage guide, Python API reference (`Recommender`, `RiskModel`, pipeline routines), configuration schemas, and instructions for extending the system. |

---

## ⚡ Quick Navigation

- **Source Code**: [`src/drainage_rec/`](file:///c:/Users/krish/Desktop/dev/drain-prep/src/drainage_rec/)
- **Configuration Files**: [`configs/`](file:///c:/Users/krish/Desktop/dev/drain-prep/configs/)
- **FastAPI App Entrypoint**: [`src/drainage_rec/web_api.py`](../src/drainage_rec/web_api.py)
- **Web Client**: [`web/`](../web/)
- **CLI Entrypoint**: [`src/drainage_rec/cli.py`](file:///c:/Users/krish/Desktop/dev/drain-prep/src/drainage_rec/cli.py)
- **Pipeline Runner**: [`scripts/run_pipeline.py`](file:///c:/Users/krish/Desktop/dev/drain-prep/scripts/run_pipeline.py)
