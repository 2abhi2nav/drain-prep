"""Streamlit dashboard.

    streamlit run src/drainage_rec/dashboard/app.py
"""

import json

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from drainage_rec.dashboard.theme import (
    MUTED, SEQUENTIAL, SERIES, SERIES_LABEL, TIER_COLOR, TIER_ICON, style,
)
from drainage_rec.decision.ahp import ahp_weights
from drainage_rec.decision.matrix import contribution, score_actions
from drainage_rec.power import (
    fit_station_generation_regression, load_station_priorities, load_zone_demographics,
    score_power_preparedness,
)
from drainage_rec.recommend import MODEL_PATH, Recommender
from drainage_rec.stats.distributions import Fit
from drainage_rec.stats.predictive import fit_heavy_rain_model
from drainage_rec.utils.config import PROCESSED_DIR

st.set_page_config(page_title="Chennai Power Preparedness PoC", page_icon="🌧️", layout="wide")
st.markdown(
    "<style>[data-testid='stPlotlyChart'] { margin-top: 1rem; }</style>",
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- data

def _csv(name, **kw) -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / f"{name}.csv", **kw)


@st.cache_data
def load_all() -> dict:
    d = {
        "summary": json.loads((PROCESSED_DIR / "summary.json").read_text()),
        "classified": _csv("classified_days", parse_dates=["date"], index_col="date"),
        "thresholds": _csv("tier_thresholds_mm", index_col=0),
        "pairwise": _csv("ahp_pairwise", index_col=0),
        "oat": _csv("sensitivity_oat"),
        "mc": _csv("sensitivity_mc_summary", index_col=0),
        "rank_freq": _csv("sensitivity_rank_frequency", index_col=0),
        "tau": _csv("sensitivity_mc_tau"),
    }
    return d


@st.cache_resource
def load_recommender() -> Recommender:
    return Recommender.load()


@st.cache_resource
def load_predictive_model():
    return fit_heavy_rain_model()


if not MODEL_PATH.exists():
    st.title("Chennai Power Preparedness")
    st.error(
        "No processed data yet. Run `make data` (downloads IMD rainfall, slow) "
        "and then `make pipeline`, and reload this page."
    )
    st.stop()

D = load_all()
REC = load_recommender()
RAIN_MODEL = load_predictive_model()
ZONES = load_zone_demographics()
criteria = REC.criteria
ahp_default = dict(zip(criteria, REC.weights))


def tier_badge(tier: str, size: str = "1.6rem") -> str:
    c = TIER_COLOR[tier]
    return (
        f"<span style='display:inline-flex;align-items:center;gap:.5rem;padding:.35rem .9rem;"
        f"border-radius:999px;border:2px solid {c};font-size:{size};font-weight:600;color:inherit'>"
        f"<span style='color:{c}'>{TIER_ICON[tier]}</span>{tier}</span>"
    )


def fmt_rp(rp: float) -> str:
    if not np.isfinite(rp) or rp > 1000:
        return "> 1000 y"
    return f"{rp:.1f} y" if rp < 10 else f"{rp:.0f} y"


def fit_for(acc: str) -> Fit:
    return REC.model.fits[acc]


# --------------------------------------------------------------------------- sidebar

with st.sidebar:
    st.markdown("### Chennai Power Preparedness")
    s = D["summary"]
    st.caption(f"IMD rainfall · {s['period'][0][:4]}–{s['period'][1][:4]}")
    st.divider()
    st.markdown("**Decision weights**")
    custom = st.toggle("Override AHP weights", value=False)
    weights = {}
    for c in criteria:
        weights[c] = st.slider(c.replace("_", " ").title(), 0.0, 1.0, float(round(ahp_default[c], 3)),
                               0.01, disabled=not custom, key=f"w_{c}")
    w_vec = np.array([weights[c] for c in criteria]) if custom else REC.weights
    if w_vec.sum() == 0:
        w_vec = REC.weights
    w_vec = w_vec / w_vec.sum()
    if custom:
        st.caption("Normalised: " + ", ".join(f"{c} {w:.2f}" for c, w in zip(criteria, w_vec)))

rec = Recommender(REC.model, REC.actions, criteria, w_vec)

tabs = st.tabs(["Forecast", "Population priority", "Power stations", "Decision Matrix"])

# --------------------------------------------------------------------------- Recommend

with tabs[0]:
    st.subheader("Chennai rainfall forecast")

    cls = D["classified"]
    mode = st.radio("Input", ["Enter rainfall", "Replay a historical day"], horizontal=True,
                    label_visibility="collapsed")
    if mode == "Enter rainfall":
        c1, c2, c3 = st.columns(3)
        r1 = c1.number_input("1-day rainfall (mm)", 0.0, 1000.0, 80.0, 5.0)
        r3 = c2.number_input("3-day accumulated rainfall (mm)", 0.0, 2000.0, 160.0, 10.0,
                             help="Total over the assessed day and the two days before it.")
        forecast_month = c3.selectbox("Forecast month", range(1, 13),
                                      format_func=lambda m: pd.Timestamp(year=2000, month=m, day=1).strftime("%B"))
    else:
        default = pd.Timestamp("2015-12-02")
        if default not in cls.index:
            default = cls["rain_3d"].idxmax()
        day = st.date_input("Date", default.date(), min_value=cls.index.min().date(),
                            max_value=cls.index.max().date())
        row = cls.loc[pd.Timestamp(day)]
        r1, r3 = float(row["rain_1d"]), float(row["rain_3d"])
        forecast_month = day.month
        st.caption(f"Observed: {r1:.1f} mm on the day, {r3:.1f} mm over 3 days.")

    out = rec.recommend(r1, r3)
    heavy_probability = float(RAIN_MODEL.predict_probability(r1, r3, forecast_month)[0])
    left, right = st.columns([1, 1.5], gap="large")
    with left:
        st.markdown(tier_badge(out.tier), unsafe_allow_html=True)
        st.metric("Logistic heavy-rain probability", f"{heavy_probability:.1%}",
                  help="Estimated probability of at least 64.5 mm in 24 hours, based on historical Chennai rainfall patterns.")
        st.write("")
        driver_label = SERIES_LABEL[out.driver]
        st.caption(f"Driven by the **{driver_label.lower()}**.")
        for k in ("rain_1d", "rain_3d"):
            a = out.assessment[k]
            m1, m2 = st.columns(2)
            m1.metric(f"{SERIES_LABEL[k]}", f"{a['value_mm']:.0f} mm",
                      help="Value assessed (3-day total is at least the 1-day value).")
            m2.metric("Return period", fmt_rp(a["return_period"]),
                      delta=f"{a['percentile']:.1f} pct of wet days", delta_color="off")
        th = D["thresholds"]
        st.markdown("**Tier thresholds (mm)**")
        st.dataframe(
            th.rename(columns=SERIES_LABEL).style.format("{:.0f}"),
            width="stretch",
        )

    with right:
        fig = go.Figure()
        T = np.logspace(np.log10(1.01), 3, 200)
        for k in ("rain_1d", "rain_3d"):
            f = fit_for(k)
            fig.add_scatter(x=T, y=f.ppf(1 - 1 / T), mode="lines", name=SERIES_LABEL[k],
                            line=dict(color=SERIES[k], width=2),
                            hovertemplate="%{x:.0f}-year level: %{y:.0f} mm<extra>" + SERIES_LABEL[k] + "</extra>")
            a = out.assessment[k]
            rp = min(a["return_period"], 1000)
            fig.add_scatter(x=[max(rp, 1.01)], y=[a["value_mm"]], mode="markers", showlegend=False,
                            marker=dict(size=12, color=SERIES[k], line=dict(color="#fcfcfb", width=2)),
                            hovertemplate=f"Input {SERIES_LABEL[k].lower()}: %{{y:.0f}} mm ≈ {fmt_rp(a['return_period'])}<extra></extra>")
        for rule in REC.model.tiers:
            if "return_period" in rule:
                fig.add_vline(x=rule["return_period"], line=dict(color=TIER_COLOR[rule["name"]], width=1, dash="dot"),
                              annotation_text=f"{TIER_ICON[rule['name']]} {rule['name']}",
                              annotation_font_color=MUTED, annotation_position="top left")
        fig.update_xaxes(type="log", title="Return period (years)")
        fig.update_yaxes(title="Rainfall (mm)")
        st.plotly_chart(style(fig, 340, title="Where today's rainfall sits on the fitted extremes"),
                        width="stretch")

    st.markdown("#### Logistic model diagnostics")
    metrics = RAIN_MODEL.metrics
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Holdout ROC AUC", f"{metrics['auc']:.3f}")
    m2.metric("Average precision", f"{metrics['average_precision']:.3f}")
    m3.metric("Brier score", f"{metrics['brier']:.3f}")
    m4.metric("Precision @ 0.5", f"{metrics['precision']:.1%}")
    m5.metric("Recall @ 0.5", f"{metrics['recall']:.1%}")
    st.caption(f"Heavy rain: ≥64.5 mm/24h · Train before 2015 · Holdout {metrics['test_start']}–{metrics['test_end']}. Observed rainfall stands in for archived forecasts.")
    c1, c2 = st.columns(2)
    with c1:
        roc = metrics["roc"]
        fig = go.Figure()
        fig.add_scatter(x=roc["false_positive_rate"], y=roc["true_positive_rate"], mode="lines",
                        name="Logistic model", line=dict(color=SERIES["rain_1d"], width=2))
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Chance", line=dict(color=MUTED, dash="dot"))
        fig.update_xaxes(title="False positive rate")
        fig.update_yaxes(title="True positive rate")
        st.plotly_chart(style(fig, 300, title="ROC curve"), width="stretch")
    with c2:
        pr = metrics["precision_recall"]
        fig = go.Figure(go.Scatter(x=pr["recall"], y=pr["precision"], mode="lines",
                                   line=dict(color=SERIES["rain_3d"], width=2), name="Logistic model"))
        fig.update_xaxes(title="Recall", range=[0, 1])
        fig.update_yaxes(title="Precision", range=[0, 1])
        st.plotly_chart(style(fig, 300, title="Precision-recall curve"), width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        calibration = metrics["calibration"]
        fig = go.Figure()
        fig.add_scatter(x=calibration["predicted"], y=calibration["observed"], mode="lines+markers",
                        name="Observed by probability decile", line=dict(color=SERIES["rain_3d"], width=2))
        fig.add_scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration",
                        line=dict(color=MUTED, dash="dot"))
        fig.update_xaxes(title="Mean predicted probability")
        fig.update_yaxes(title="Observed heavy-rain fraction", range=[0, 1])
        st.plotly_chart(style(fig, 300, title="Probability calibration"), width="stretch")
        matrix = metrics["confusion"]
        fig = go.Figure(go.Heatmap(z=matrix, x=["Predicted no", "Predicted heavy"],
                                   y=["Actual no", "Actual heavy"], text=matrix,
                                   texttemplate="%{text}", colorscale="Blues", showscale=False))
        st.plotly_chart(style(fig, 300, title="Confusion matrix · threshold 0.5"), width="stretch")
    with c2:
        coefficients = metrics["coefficients"].rename({
            "log_1d_rain": "Log 1-day rainfall", "log_3d_rain": "Log 3-day rainfall",
            "month_sin": "Season sine", "month_cos": "Season cosine",
        })
        fig = go.Figure(go.Bar(x=coefficients.values, y=coefficients.index, orientation="h",
                               marker_color=SERIES["rain_1d"]))
        fig.update_xaxes(title="Standardized coefficient (log-odds)")
        st.plotly_chart(style(fig, 300, title="Logistic model coefficients"), width="stretch")

# --------------------------------------------------------------------------- Power preparedness

with tabs[1]:
    st.subheader("Population priority by Chennai zone")

    c1, c2, c3 = st.columns([1, 1, 1])
    with c1:
        st.markdown("**IMD forecast products**")
        st.link_button("Chennai 7-day forecast and warnings", "https://mausam.imd.gov.in/chennai/mcdata/chn_fcst_mng.pdf")
        st.link_button("24-hour district rainfall forecast", "https://mausam.imd.gov.in/chennai/mcdata/distfcst.pdf")
    with c2:
        st.markdown("**IMD warning products**")
        st.link_button("Chennai district warnings / nowcast", "https://mausam.imd.gov.in/imd_latest/contents/districtwisewarnings_mc.php?id=26")
        st.link_button("7-day regional forecast and warnings", "https://mausam.imd.gov.in/chennai/mcdata/chennaiinf.pdf")
    with c3:
        st.info("Enter values from the linked IMD products.")

    input_cols = ["Zone Name", "Next 24h rainfall (mm)", "Observed 3-day total (mm)"]
    zone_inputs = ZONES[["Zone Name"]].copy()
    zone_inputs["Next 24h rainfall (mm)"] = 0.0
    zone_inputs["Observed 3-day total (mm)"] = 0.0
    input1, input2 = st.columns([1, 3])
    with input1:
        forecast_month = st.selectbox("Forecast month", range(1, 13),
                                      format_func=lambda m: pd.Timestamp(year=2000, month=m, day=1).strftime("%B"),
                                      key="zones_forecast_month")
        imd_warning = st.selectbox("IMD warning level", ["No warning", "Yellow", "Orange", "Red"],
                                   key="zones_imd_warning")
    with input2:
        edited_inputs = st.data_editor(
            zone_inputs[input_cols], hide_index=True, width="stretch", key="zone_rain_inputs",
            column_config={
                "Zone Name": st.column_config.TextColumn(disabled=True),
                "Next 24h rainfall (mm)": st.column_config.NumberColumn(min_value=0, max_value=1000, step=5),
                "Observed 3-day total (mm)": st.column_config.NumberColumn(min_value=0, max_value=2000, step=10),
            },
        )

    probabilities = RAIN_MODEL.predict_probability(
        edited_inputs["Next 24h rainfall (mm)"].to_numpy(),
        edited_inputs["Observed 3-day total (mm)"].to_numpy(),
        np.full(len(edited_inputs), forecast_month),
    )
    zone_scores = score_power_preparedness(ZONES, probabilities, imd_warning)
    zone_scores = zone_scores.merge(edited_inputs, on="Zone Name", how="left")
    zone_scores["expected_heavy_rain_population"] = zone_scores["population"] * zone_scores["effective_probability"]
    mean_probability = float(np.average(zone_scores["effective_probability"], weights=zone_scores["population"]))
    m1, m2, m3 = st.columns(3)
    m1.metric("Population-weighted heavy-rain probability", f"{mean_probability:.1%}")
    m2.metric("Highest-priority zone", str(zone_scores.iloc[0]["Zone Name"]))
    m3.metric("Residents weighted by rain probability",
              f"{zone_scores['expected_heavy_rain_population'].sum():,.0f}")

    st.markdown("#### Zone priority")
    fig = go.Figure(go.Bar(
        x=zone_scores["priority_score"], y=zone_scores["Zone Name"], orientation="h",
        marker_color=SERIES["rain_1d"],
        customdata=zone_scores[["population", "children", "seniors", "effective_probability"]],
        hovertemplate=("%{y}<br>Priority: %{x:.1f}/100<br>Population: %{customdata[0]:,.0f}"
                       "<br>Children (0-14): %{customdata[1]:,.0f}"
                       "<br>Older residents (60+): %{customdata[2]:,.0f}"
                       "<br>Heavy-rain probability: %{customdata[3]:.1%}<extra></extra>"),
    ))
    fig.update_xaxes(title="Relative preparedness priority (0-100)")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, max(340, 28 * len(zone_scores)), title="Population-weighted zone ranking"),
                    width="stretch")
    st.dataframe(
        zone_scores[["Zone Name", "Next 24h rainfall (mm)", "Observed 3-day total (mm)",
                     "model_probability", "effective_probability", "wards", "population", "children", "youth",
                     "adults", "seniors", "priority_score"]].rename(columns={
                         "model_probability": "Model probability",
                         "effective_probability": "Probability incl. IMD warning",
                         "wards": "Ward count", "population": "Population (2011)",
                         "children": "Children (0-14)", "youth": "Youth (15-24)",
                         "adults": "Adults (25-60)", "seniors": "Older residents (60+)",
                         "priority_score": "Priority / 100",
                     }).style.format({"Next 24h rainfall (mm)": "{:.1f}", "Observed 3-day total (mm)": "{:.1f}",
                                      "Model probability": "{:.1%}", "Probability incl. IMD warning": "{:.1%}",
                                      "Population (2011)": "{:,.0f}", "Children (0-14)": "{:,.0f}",
                                      "Youth (15-24)": "{:,.0f}", "Adults (25-60)": "{:,.0f}",
                                      "Older residents (60+)": "{:,.0f}", "Priority / 100": "{:.1f}"}),
        hide_index=True, width="stretch",
    )

# --------------------------------------------------------------------------- Power stations

with tabs[2]:
    st.subheader("Power station relief priority")
    station_data = load_station_priorities(ZONES, zone_scores)
    station_priorities, generation_metrics = fit_station_generation_regression(station_data)
    st.markdown("#### Multiple regression")
    st.caption("OLS predicts station output from capacity, prior-year output, and rainfall-weighted population. Predicted output shares prescribe the relief split.")
    m1, m2, m3 = st.columns(3)
    m1.metric("Holdout MAE", f"{generation_metrics['mae']:,.0f}")
    m2.metric("Holdout RMSE", f"{generation_metrics['rmse']:,.0f}")
    m3.metric("Holdout R²", f"{generation_metrics['r2']:.2f}")
    st.caption(f"Random station holdout · {generation_metrics['n_train']} train / {generation_metrics['n_test']} test · 54 Tamil Nadu stations.")

    st.markdown("#### Proposed relief split")
    st.caption("Each station's share is its predicted output divided by total predicted output. Population reliance is proxied by prior-year output share; no customer map is available.")

    top = station_priorities.head(15).copy()
    fig = go.Figure(go.Bar(
        x=top["relief_resource_share_pct"], y=top["station"], orientation="h",
        marker_color=SERIES["rain_1d"],
        customdata=top[["estimated_exposed_population", "capacity_mw", "predicted_actual_ytd"]],
        hovertemplate=("%{y}<br>Resource share: %{x:.1f}%<br>Exposed population proxy: %{customdata[0]:,.0f}"
                       "<br>Capacity: %{customdata[1]:,.0f} MW"
                       "<br>Predicted output: %{customdata[2]:,.0f}<extra></extra>"),
    ))
    fig.update_xaxes(title="Proposed relief-resource share (%)")
    fig.update_yaxes(autorange="reversed")
    st.plotly_chart(style(fig, 460, title="Top 15 proposed station allocations"), width="stretch")

    station_table = station_priorities[["station", "sector", "capacity_mw", "previous_actual_ytd",
                                        "predicted_actual_ytd", "weighted_prioritized_population",
                                        "estimated_exposed_population", "relief_resource_share_pct"]].rename(columns={
        "station": "Station", "sector": "Sector", "capacity_mw": "Capacity (MW)",
        "previous_actual_ytd": "Prior-year output, Apr-Jan", "predicted_actual_ytd": "Predicted output, Apr-Jan",
        "weighted_prioritized_population": "Weighted prioritized population",
        "estimated_exposed_population": "Exposed population proxy",
        "relief_resource_share_pct": "Relief share (%)",
    })
    st.dataframe(station_table.style.format({
        "Capacity (MW)": "{:,.1f}", "Predicted output, Apr-Jan": "{:,.1f}",
        "Prior-year output, Apr-Jan": "{:,.1f}", "Weighted prioritized population": "{:,.0f}",
        "Exposed population proxy": "{:,.0f}", "Relief share (%)": "{:.1f}",
    }, na_rep="Not reported"), hide_index=True, width="stretch")
    c1, c2 = st.columns(2)
    with c1:
        actual = generation_metrics["test_actual"]
        predicted = generation_metrics["test_predicted"]
        fig = go.Figure(go.Scatter(x=actual, y=predicted, mode="markers", marker_color=SERIES["rain_1d"]))
        bounds = [min(actual.min(), predicted.min()), max(actual.max(), predicted.max())]
        fig.add_scatter(x=bounds, y=bounds, mode="lines", line=dict(color=MUTED, dash="dot"), name="Perfect fit")
        fig.update_xaxes(title="Observed generation")
        fig.update_yaxes(title="Predicted generation")
        st.plotly_chart(style(fig, 320, title="Holdout: actual vs predicted generation"), width="stretch")
    with c2:
        coeff = generation_metrics["coefficients"].rename({
            "capacity_mw": "Capacity", "previous_actual_ytd": "Prior-year generation",
            "weighted_prioritized_population": "Weighted prioritized population",
        })
        fig = go.Figure(go.Bar(x=coeff.values, y=coeff.index, orientation="h", marker_color=SERIES["rain_3d"]))
        fig.update_xaxes(title="Standardized regression coefficient")
        st.plotly_chart(style(fig, 320, title="Regression predictors"), width="stretch")

# --------------------------------------------------------------------------- Decision matrix

with tabs[3]:
    st.subheader("Decision Matrix")
    st.markdown("#### Actions for the current forecast")
    if not out.actions:
        st.info("No actions triggered for this rainfall tier.")
    else:
        st.dataframe(
            pd.DataFrame(out.actions)[["rank", "name", "min_tier", "score"]],
            hide_index=True, width="stretch",
            column_config={
                "rank": st.column_config.NumberColumn("#", width="small"),
                "name": st.column_config.TextColumn("Action", width="large"),
                "min_tier": st.column_config.TextColumn("Triggered from"),
                "score": st.column_config.ProgressColumn("Priority score", min_value=0, max_value=1,
                                                         format="%.3f"),
            },
        )
    st.divider()
    ahp = ahp_weights(D["pairwise"].to_numpy())
    c1, c2 = st.columns([3, 2], gap="large")
    with c1:
        pw = D["pairwise"]
        fig = go.Figure(go.Heatmap(
            z=np.log(pw.to_numpy()), x=pw.columns, y=pw.index, colorscale=[[0, "#d03b3b"], [0.5, "#f0efec"], [1, "#2a78d6"]],
            zmid=0, showscale=False, text=pw.map(lambda v: f"{v:.2f}" if v < 1 else f"{v:.0f}").to_numpy(),
            texttemplate="%{text}", hovertemplate="%{y} vs %{x}: %{text}<extra></extra>", xgap=2, ygap=2,
        ))
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style(fig, 320, title="AHP pairwise comparisons (row vs column, Saaty scale)"),
                        width="stretch")
    with c2:
        wdf = pd.DataFrame({"AHP": ahp["weights"], "In use": w_vec}, index=criteria)
        fig = go.Figure()
        fig.add_bar(y=criteria, x=wdf["AHP"], orientation="h", name="AHP", marker_color=SERIES["rain_1d"],
                    hovertemplate="%{y}: %{x:.3f}<extra>AHP</extra>")
        if custom:
            fig.add_bar(y=criteria, x=wdf["In use"], orientation="h", name="Custom", marker_color=SERIES["rain_3d"],
                        hovertemplate="%{y}: %{x:.3f}<extra>Custom</extra>")
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style(fig, 260, title="Criterion weights", barmode="group", bargap=0.3,
                              showlegend=custom), width="stretch")
        m1, m2 = st.columns(2)
        m1.metric("Consistency ratio", f"{ahp['cr']:.3f}", help="Saaty: CR < 0.10 is acceptably consistent.")
        m2.metric("λ max", f"{ahp['lambda_max']:.3f}")

    scored = score_actions(REC.actions, criteria, w_vec)
    contrib = contribution(scored, criteria, w_vec)
    fig = go.Figure()
    for i, c in enumerate(criteria):
        fig.add_bar(y=scored["name"], x=contrib[c], orientation="h", name=c, marker_color=SEQUENTIAL[1 + i],
                    marker_line=dict(color="#fcfcfb", width=2),
                    hovertemplate="%{y}<br>" + c + ": %{x:.3f}<extra></extra>")
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(title="Weighted score")
    st.plotly_chart(style(fig, 420, title="All actions: score contribution by criterion", barmode="stack", bargap=0.35),
                    width="stretch")
    st.dataframe(scored[["name", "min_tier", *criteria, "score", "rank"]], hide_index=True, width="stretch",
                 column_config={"score": st.column_config.NumberColumn(format="%.3f")})

    st.markdown("#### Sensitivity of the ranking to the weights")
    c1, c2 = st.columns(2, gap="large")
    with c1:
        rf = D["rank_freq"].loc[D["mc"].index]
        names = REC.actions.loc[rf.index, "name"].str.slice(0, 38)
        fig = go.Figure(go.Heatmap(
            z=rf.to_numpy(), x=[f"#{c}" for c in rf.columns], y=names, colorscale=[[0, "#fcfcfb"]] + [
                [(i + 1) / len(SEQUENTIAL), c] for i, c in enumerate(SEQUENTIAL)],
            zmin=0, zmax=1, xgap=2, ygap=2, colorbar=dict(title="P(rank)", thickness=10),
            hovertemplate="%{y}<br>rank %{x}: %{z:.1%}<extra></extra>",
        ))
        fig.update_yaxes(autorange="reversed")
        st.plotly_chart(style(fig, 380, title="Monte Carlo rank probabilities (Dirichlet weights)"),
                        width="stretch")
    with c2:
        tau = D["tau"]["kendall_tau"]
        fig = go.Figure(go.Histogram(x=tau, nbinsx=30, marker_color=SERIES["rain_1d"],
                                     marker_line=dict(color="#fcfcfb", width=2),
                                     hovertemplate="τ %{x}: %{y} draws<extra></extra>"))
        fig.update_xaxes(title="Kendall τ vs. AHP ranking")
        fig.update_yaxes(title="Draws")
        st.plotly_chart(style(fig, 380, title=f"Rank agreement across draws (mean τ = {tau.mean():.2f})"),
                        width="stretch")
    st.markdown("**One-at-a-time ±25% weight perturbation**")
    st.dataframe(D["oat"].style.format({"kendall_tau": "{:.3f}", "top3_overlap": "{:.0%}"}),
                 hide_index=True, width="stretch")
