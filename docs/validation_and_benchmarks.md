# Empirical Validation & Historical Benchmarks

This document details the validation methodology, historical flood event benchmarks, and empirical hit rates that establish the reliability of `drainage-rec`.

---

## 🎯 1. Validation Philosophy

Unlike riverine catchments with continuous stream gauges, urban drainage systems in developing metropolises rarely possess dense, long-term flood depth sensor networks. To evaluate the model without circular reasoning or uncalibrated hydrodynamic simulations, `drainage-rec` evaluates **hydrometeorological consistency against documented historical flood disasters**.

If the statistical model and tier boundaries are sound:
1. Every documented major disaster in Chennai's modern history must trigger an **Alert** or **Emergency** tier (**zero missed disasters**).
2. The peak dates identified by the multi-duration model must align precisely with recorded civic inundation peaks.
3. Catastrophic events (e.g. December 2015, Cyclone Michaung 2023) should reflect multi-decadal return periods ($T \ge 10\text{ years}$) and rank above the $99.9\text{th}$ percentile of historical severity.

---

## 📜 2. Ground Truth Historical Flood Events

The benchmark catalog [`data/external/known_flood_events.csv`](file:///c:/Users/krish/Desktop/dev/drain-prep/data/external/known_flood_events.csv) compiles 7 major flood episodes documented by the National Disaster Management Authority (NDMA), Tamil Nadu State Disaster Management Authority (TNSDMA), and IMD meteorological monographs:

```csv
event,start,end,source
Chennai floods (Nov 2015),2015-11-08,2015-11-24,"NDMA / Tamil Nadu govt reports"
Chennai floods (Dec 2015),2015-11-30,2015-12-05,"NDMA / IMD 2015 NE monsoon report"
Chennai floods (Nov 2021),2021-11-06,2021-11-12,"IMD NE monsoon 2021 report"
Cyclone Michaung (Dec 2023),2023-12-02,2023-12-05,"IMD cyclone Michaung report"
Cyclone Vardah (Dec 2016),2016-12-11,2016-12-13,"IMD cyclone Vardah report"
Chennai floods (Oct 2005),2005-10-26,2005-10-28,"Tamil Nadu govt / literature"
Chennai floods (Dec 2005),2005-12-01,2005-12-04,"Tamil Nadu govt / literature"
```

---

## 📊 3. Empirical Scorecard & Results

Running [`drainage_rec.validation.known_events.evaluate_events()`](file:///c:/Users/krish/Desktop/dev/drain-prep/src/drainage_rec/validation/known_events.py) yields the following empirical validation scorecard:

| Documented Event | Window | In Record? | Model Peak Date | Peak Tier | Max 1-Day Rain | Max 3-Day Rain | Max Return Period | Severity Percentile | Alert+ Days |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| **Chennai Floods (Nov 2015)** | 08–24 Nov 2015 | Yes | 16 Nov 2015 | **Emergency** | 289.4 mm | 323.3 mm | **96.5 y** | 99.99% | 6 |
| **Chennai Floods (Dec 2015)** | 30 Nov – 05 Dec 2015 | Yes | 02 Dec 2015 | **Emergency** | 348.5 mm | 449.5 mm | **394.6 y** | 100.00% | 3 |
| **Chennai Floods (Nov 2021)** | 06–12 Nov 2021 | Yes | 11 Nov 2021 | **Alert** | 153.9 mm | 233.8 mm | **4.3 y** | 99.82% | 2 |
| **Cyclone Michaung (Dec 2023)**| 02–05 Dec 2023 | Yes | 05 Dec 2023 | **Emergency** | 195.5 mm | 384.7 mm | **19.4 y** | 99.96% | 2 |
| **Cyclone Vardah (Dec 2016)** | 11–13 Dec 2016 | Yes | 13 Dec 2016 | **Alert** | 114.1 mm | 154.2 mm | **2.0 y** | 99.52% | 1 |
| **Chennai Floods (Oct 2005)** | 26–28 Oct 2005 | Yes | 28 Oct 2005 | **Emergency** | 217.3 mm | 386.5 mm | **19.9 y** | 99.96% | 2 |
| **Chennai Floods (Dec 2005)** | 01–04 Dec 2005 | Yes | 03 Dec 2005 | **Emergency** | 250.6 mm | 278.8 mm | **38.5 y** | 99.97% | 2 |

### 3.1 Empirical Hit Rates
- **Alert or Above Hit Rate ($\ge \text{Alert}$)**:
  $$\text{Hit Rate}_{\text{Alert+}} = \frac{7}{7} = \mathbf{100.0\%}$$
  Every historical flood reached at least Alert status, confirming zero false negatives on major flood events.
- **Emergency Hit Rate ($\ge \text{Emergency}$)**:
  $$\text{Hit Rate}_{\text{Emergency}} = \frac{5}{7} = \mathbf{71.4\%}$$
  Only Cyclone Vardah (a high-wind cyclone with moderate rain) and November 2021 (widespread moderate inundation) peaked at Alert; all true catastrophic inundations reached Emergency.

---

## 🔍 4. Case Studies & Hydrological Insights

### 4.1 The December 2015 Catastrophe
- **Observed Precipitation**: $348.5\text{ mm}$ on December 1–2, with $449.5\text{ mm}$ over 3 days.
- **Model Output**: **Emergency Tier** driven by both 1-day and 3-day rainfall, with an estimated return period of $\mathbf{394.6\text{ years}}$ and historical severity percentile of $\mathbf{100.0\%}$ (the single most extreme event in the 124-year IMD dataset).
- **Operational Reality**: Chembarambakkam reservoir reached capacity, forcing massive uncontrolled releases into the Adyar river. The model's Emergency ranking places `control_room`, `rescue_teams`, and `reservoir_release` at top priority.

### 4.2 Cyclone Michaung (December 2023)
- **Observed Precipitation**: $195.5\text{ mm}$ 1-day, but an enormous $384.7\text{ mm}$ 3-day accumulation.
- **Model Output**: **Emergency Tier** with return period $\mathbf{19.4\text{ years}}$.
- **Driver**: The model accurately flagged **`rain_3d`** as the dominant driver ($T_{\text{3d}} = 19.4\text{ y}$ vs $T_{\text{1d}} = 10.4\text{ y}$). This demonstrates the power of dual-duration tracking: evaluating 1-day rainfall alone would have severely underestimated the multi-day volumetric buildup that inundated North and South Chennai.

### 4.3 Cyclone Vardah (December 2016)
- **Observed Precipitation**: $114.1\text{ mm}$ 1-day, $154.2\text{ mm}$ 3-day.
- **Model Output**: **Alert Tier** ($T = 2.0\text{ years}$, severity percentile $99.52\%$).
- **Insight**: Vardah was primarily an intense Category 3 equivalent wind disaster ($130\text{ km/h}$) rather than a record deluge. The model properly classified it as Alert rather than escalating to a false Emergency, reserving Emergency mobilization for true hydrological overload.

---

## ⏱️ 5. Alert Episodes Analysis

Across the 124-year historical record ($1901\text{--}2024$):
- **Alert or Emergency Days**: Total of $169\text{ days}$ out of $45,292$ ($\sim 0.37\%$ of all days, or $\sim 1.36\text{ days per year}$).
- **Alert Episodes**: Contiguous periods of $\ge \text{Alert}$ status occur as distinct episodes:
  - 1-day isolated spikes: $\sim 68\%$ of episodes.
  - Multi-day prolonged episodes (2 to 6 consecutive days): $\sim 32\%$ of episodes.
- **Seasonality**: $> 88\%$ of all Alert and Emergency days occur during the Northeast Monsoon months of October, November, and December.
