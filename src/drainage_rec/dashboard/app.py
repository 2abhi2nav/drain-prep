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
from drainage_rec.recommend import MODEL_PATH, Recommender
from drainage_rec.risk.tiers import TIER_ORDER
from drainage_rec.stats.distributions import Fit
from drainage_rec.stats.frequency import empirical_exceedance
from drainage_rec.utils.config import PROCESSED_DIR

st.set_page_config(page_title="Chennai Drainage Preparedness", page_icon="🌧️", layout="wide")


# --------------------------------------------------------------------------- data

def _csv(name, **kw) -> pd.DataFrame:
    return pd.read_csv(PROCESSED_DIR / f"{name}.csv", **kw)


@st.cache_data
def load_all() -> dict:
    d = {
        "summary": json.loads((PROCESSED_DIR / "summary.json").read_text()),
        "classified": _csv("classified_days", parse_dates=["date"], index_col="date"),
        "amax": _csv("annual_maxima", index_col="year"),
        "fits": _csv("distribution_fits"),
        "return_levels": _csv("return_levels"),
        "trends": _csv("trends", index_col=0),
        "freq": _csv("frequency_summary", index_col=0),
        "exceed": _csv("exceedance_counts", index_col="year"),
        "monthly": _csv("monthly_climatology", index_col="month"),
        "thresholds": _csv("tier_thresholds_mm", index_col=0),
        "tier_dist": _csv("tier_distribution", index_col=0),
        "tier_year": _csv("tier_counts_by_year", index_col="year"),
        "episodes": _csv("alert_episodes"),
        "pairwise": _csv("ahp_pairwise", index_col=0),
        "oat": _csv("sensitivity_oat"),
        "mc": _csv("sensitivity_mc_summary", index_col=0),
        "rank_freq": _csv("sensitivity_rank_frequency", index_col=0),
        "tau": _csv("sensitivity_mc_tau"),
        "events": _csv("known_events_validation"),
    }
    return d


@st.cache_resource
def load_recommender() -> Recommender:
    return Recommender.load()


if not MODEL_PATH.exists():
    st.title("Chennai Drainage Preparedness Recommender")
    st.error(
        "No processed data yet. Run `make data` (downloads IMD rainfall, slow) "
        "and then `make pipeline`, and reload this page."
    )
    st.stop()

D = load_all()
REC = load_recommender()
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
    st.markdown("### Chennai drainage preparedness")
    s = D["summary"]
    st.caption(
        f"IMD 0.25° gridded rainfall, {s['period'][0][:4]}–{s['period'][1][:4]} "
        f"({s['years']} years), city-mean of the land grid cells over Chennai."
    )
    st.divider()
    st.markdown("**Decision weights**")
    custom = st.toggle("Override AHP weights", value=False,
                       help="Try your own weights; the recommendation and decision matrix update live.")
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

tabs = st.tabs(["Recommend", "Rainfall record", "Extreme values", "Decision matrix", "Validation", "About"])

# --------------------------------------------------------------------------- Recommend

with tabs[0]:
    st.subheader("What should the city prepare for?")
    st.caption("Enter observed or forecast rainfall for Chennai, or replay a historical day.")

    cls = D["classified"]
    mode = st.radio("Input", ["Enter rainfall", "Replay a historical day"], horizontal=True,
                    label_visibility="collapsed")
    if mode == "Enter rainfall":
        c1, c2 = st.columns(2)
        r1 = c1.number_input("1-day rainfall (mm)", 0.0, 1000.0, 80.0, 5.0)
        r3 = c2.number_input("3-day accumulated rainfall (mm)", 0.0, 2000.0, 160.0, 10.0,
                             help="Total over the assessed day and the two days before it.")
    else:
        default = pd.Timestamp("2015-12-02")
        if default not in cls.index:
            default = cls["rain_3d"].idxmax()
        day = st.date_input("Date", default.date(), min_value=cls.index.min().date(),
                            max_value=cls.index.max().date())
        row = cls.loc[pd.Timestamp(day)]
        r1, r3 = float(row["rain_1d"]), float(row["rain_3d"])
        st.caption(f"Observed: {r1:.1f} mm on the day, {r3:.1f} mm over 3 days.")

    out = rec.recommend(r1, r3)
    left, right = st.columns([1, 2], gap="large")
    with left:
        st.markdown(tier_badge(out.tier), unsafe_allow_html=True)
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
        if not out.actions:
            st.success("No preparedness actions triggered. Routine monitoring only.")
        else:
            st.markdown(f"**{len(out.actions)} actions, highest priority first**")
            tbl = pd.DataFrame(out.actions)[["rank", "name", "min_tier", "score"]]
            st.dataframe(
                tbl,
                hide_index=True,
                width="stretch",
                column_config={
                    "rank": st.column_config.NumberColumn("#", width="small"),
                    "name": st.column_config.TextColumn("Action", width="large"),
                    "min_tier": st.column_config.TextColumn("Triggered from"),
                    "score": st.column_config.ProgressColumn("Priority score", min_value=0, max_value=1,
                                                             format="%.3f"),
                },
            )

        # Where the input sits on each fitted return-level curve
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

# --------------------------------------------------------------------------- Rainfall record

with tabs[1]:
    cls = D["classified"]
    years = sorted(cls.index.year.unique())
    yr = st.select_slider("Year", options=years, value=2015 if 2015 in years else years[-1])
    y = cls[cls.index.year == yr]
    fig = go.Figure()
    for k in ("rain_1d", "rain_3d"):
        fig.add_scatter(x=y.index, y=y[k], name=SERIES_LABEL[k], mode="lines",
                        line=dict(color=SERIES[k], width=2 if k == "rain_1d" else 1.5),
                        hovertemplate="%{y:.1f} mm")
    elevated = y[y["tier"].isin(["Alert", "Emergency"])]
    for t in ("Alert", "Emergency"):
        e = elevated[elevated["tier"] == t]
        if len(e):
            fig.add_scatter(x=e.index, y=e["rain_3d"], mode="markers", name=f"{TIER_ICON[t]} {t} day",
                            marker=dict(size=10, color=TIER_COLOR[t], symbol="triangle-up" if t == "Alert" else "hexagon",
                                        line=dict(color="#fcfcfb", width=2)),
                            hovertemplate=f"{t}: %{{y:.0f}} mm (3-day)<extra></extra>")
    fig.update_layout(hovermode="x unified")
    fig.update_yaxes(title="mm")
    st.plotly_chart(style(fig, 340, title=f"Daily rainfall over Chennai, {yr}"), width="stretch")

    c1, c2 = st.columns(2)
    amax = D["amax"]
    tr = D["trends"]
    with c1:
        acc = st.radio("Annual maximum of", ["rain_1d", "rain_3d"], format_func=SERIES_LABEL.get, horizontal=True)
        s_ = amax[acc]
        fig = go.Figure()
        fig.add_scatter(x=s_.index, y=s_, mode="lines+markers", name=SERIES_LABEL[acc],
                        line=dict(color=SERIES[acc], width=1.5), marker=dict(size=5),
                        hovertemplate="%{x}: %{y:.0f} mm<extra></extra>")
        slope = tr.loc[acc, "sen_slope_mm_per_decade"] / 10
        med_x, med_y = np.median(s_.index), np.median(s_)
        xs = np.array([s_.index.min(), s_.index.max()])
        fig.add_scatter(x=xs, y=med_y + slope * (xs - med_x), mode="lines", name="Sen's slope",
                        line=dict(color="#52514e", width=2, dash="dash"), hoverinfo="skip")
        fig.update_yaxes(title="mm")
        st.plotly_chart(style(fig, 320, title="Annual maxima and trend"), width="stretch")
        r = tr.loc[acc]
        st.caption(
            f"Mann-Kendall: **{r['mk_trend']}** (τ = {float(r['mk_tau']):.3f}, p = {float(r['mk_pvalue']):.3f}). "
            f"Sen's slope {float(r['sen_slope_mm_per_decade']):+.1f} mm/decade; OLS {float(r['ols_slope_mm_per_decade']):+.1f} "
            f"mm/decade (95% CI {float(r['ols_ci_lower']):+.1f} to {float(r['ols_ci_upper']):+.1f})."
        )
    with c2:
        mon = D["monthly"]
        names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        fig = go.Figure(go.Bar(x=names, y=mon["mean"], marker_color=SERIES["rain_1d"],
                               error_y=dict(type="data", array=mon["std"], color=MUTED, thickness=1),
                               customdata=mon["share"] * 100,
                               hovertemplate="%{x}: %{y:.0f} mm (±%{error_y.array:.0f} sd), %{customdata:.0f}% of annual<extra></extra>"))
        fig.update_yaxes(title="Mean monthly total (mm)")
        st.plotly_chart(style(fig, 320, title="Monthly climatology (NE monsoon dominates)", bargap=0.25),
                        width="stretch")

    ex = D["exceed"]
    dec = ex.groupby((ex.index // 10) * 10).mean()
    fig = go.Figure()
    labels = {"heavy_64_5": "Heavy (≥ 64.5 mm)", "very_heavy_115_6": "Very heavy (≥ 115.6 mm)",
              "extreme_204_5": "Extremely heavy (≥ 204.5 mm)"}
    for i, (col, lab) in enumerate(labels.items()):
        fig.add_bar(x=dec.index.astype(str) + "s", y=dec[col], name=lab, marker_color=SEQUENTIAL[2 + 2 * i],
                    hovertemplate="%{x}: %{y:.2f} days/yr<extra>" + lab + "</extra>")
    fig.update_yaxes(title="Days per year (decade mean)")
    st.plotly_chart(style(fig, 320, title="Frequency of heavy-rain days by decade", barmode="group", bargap=0.2,
                          bargroupgap=0.08), width="stretch")
    fq = D["freq"].rename(index=labels)
    st.dataframe(fq.style.format({"rate_per_year": "{:.2f}", "ci_lower": "{:.2f}", "ci_upper": "{:.2f}",
                                  "years": "{:.0f}"}), width="stretch")
    st.caption("Mean days per year with exact Poisson 95% confidence intervals.")

# --------------------------------------------------------------------------- Extremes

with tabs[2]:
    st.subheader("Extreme-value analysis of annual maxima")
    rl = D["return_levels"]
    cols = st.columns(2)
    for col, k in zip(cols, ("rain_1d", "rain_3d")):
        with col:
            f = fit_for(k)
            emp = empirical_exceedance(D["amax"][k])
            t = rl[rl["accumulation"] == k]
            T = np.logspace(np.log10(1.05), np.log10(200), 200)
            fig = go.Figure()
            fig.add_scatter(x=t["return_period"], y=t["ci_upper"], mode="lines", line=dict(width=0),
                            showlegend=False, hoverinfo="skip")
            fig.add_scatter(x=t["return_period"], y=t["ci_lower"], mode="lines", line=dict(width=0),
                            fill="tonexty", fillcolor="rgba(42,120,214,0.15)", name="95% bootstrap CI",
                            hoverinfo="skip")
            fig.add_scatter(x=T, y=f.ppf(1 - 1 / T), mode="lines", name=f"{f.dist.upper()} fit",
                            line=dict(color=SERIES[k], width=2),
                            hovertemplate="%{x:.0f}-year: %{y:.0f} mm<extra></extra>")
            fig.add_scatter(x=emp["return_period"], y=emp["value"], mode="markers", name="Observed (Weibull)",
                            marker=dict(size=8, color="#fcfcfb", line=dict(color=SERIES[k], width=1.5)),
                            hovertemplate="%{y:.0f} mm, plotted at %{x:.1f} y<extra></extra>")
            fig.update_xaxes(type="log", title="Return period (years)")
            fig.update_yaxes(title="mm")
            st.plotly_chart(style(fig, 360, title=SERIES_LABEL[k]), width="stretch")
            st.dataframe(
                t.set_index("return_period")[["return_level", "ci_lower", "ci_upper"]]
                .rename(columns={"return_level": "Return level (mm)", "ci_lower": "95% CI low", "ci_upper": "95% CI high"})
                .style.format("{:.0f}"),
                width="stretch",
            )
    st.markdown("**Goodness of fit**")
    fits = D["fits"].copy()
    fits["selected"] = fits["selected"].map({True: "✓", False: ""})
    st.dataframe(
        fits[["accumulation", "dist", "selected", "xi", "aic", "ks_stat", "ks_pvalue", "log_likelihood"]]
        .style.format({"xi": "{:.3f}", "aic": "{:.1f}", "ks_stat": "{:.3f}", "ks_pvalue": "{:.3f}",
                       "log_likelihood": "{:.1f}"}, na_rep="–"),
        hide_index=True, width="stretch",
    )
    lr = s["gev_vs_gumbel_lr_test"]
    st.caption(
        "GEV is selected only if it beats Gumbel by more than 2 AIC units. Likelihood-ratio test of ξ = 0: "
        + "; ".join(f"{SERIES_LABEL[k]} p = {v['pvalue']:.3f}" for k, v in lr.items()) + "."
    )

# --------------------------------------------------------------------------- Decision matrix

with tabs[3]:
    st.subheader("Weighted decision matrix")
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

# --------------------------------------------------------------------------- Validation

with tabs[4]:
    st.subheader("Do known Chennai floods land in the top tiers?")
    st.caption("No flood labels exist at this resolution, so the check is whether documented flood "
               "episodes are ranked as Alert or Emergency.")
    ev = D["events"]
    hit = s.get("known_event_hit_rate_alert_plus")
    m1, m2, m3 = st.columns(3)
    m1.metric("Events reaching Alert or above", f"{hit:.0%}" if hit == hit else "–")
    he = s.get("known_event_hit_rate_emergency")
    m2.metric("Events reaching Emergency", f"{he:.0%}" if he == he else "–")
    td = D["tier_dist"]
    m3.metric("Alert-or-above days per year", f"{td.loc[['Alert', 'Emergency'], 'days_per_year'].sum():.1f}")

    show = ev[ev["in_record"]].copy()
    show["peak_tier"] = show["peak_tier"].map(lambda t: f"{TIER_ICON[t]} {t}")
    st.dataframe(
        show[["event", "peak_date", "peak_tier", "max_rain_1d", "max_rain_3d", "max_return_period",
              "severity_percentile", "days_alert_or_above"]],
        hide_index=True, width="stretch",
        column_config={
            "max_rain_1d": st.column_config.NumberColumn("Max 1-day (mm)", format="%.0f"),
            "max_rain_3d": st.column_config.NumberColumn("Max 3-day (mm)", format="%.0f"),
            "max_return_period": st.column_config.NumberColumn("Max return period (y)", format="%.1f"),
            "severity_percentile": st.column_config.NumberColumn("Severity pct of all days", format="%.3f"),
        },
    )

    if len(show):
        pick = st.selectbox("Inspect event", show["event"])
        e = show[show["event"] == pick].iloc[0]
        cls = D["classified"]
        win = cls.loc[pd.Timestamp(e["start"]) - pd.Timedelta(days=10): pd.Timestamp(e["end"]) + pd.Timedelta(days=10)]
        fig = go.Figure()
        fig.add_vrect(x0=pd.Timestamp(e["start"]), x1=pd.Timestamp(e["end"]) + pd.Timedelta(hours=23), fillcolor="#e1e0d9",
                      opacity=0.5, line_width=0, annotation_text="documented flood", annotation_font_color=MUTED)
        fig.add_bar(x=win.index, y=win["rain_1d"], name=SERIES_LABEL["rain_1d"], marker_color=SERIES["rain_1d"],
                    hovertemplate="%{x|%d %b}: %{y:.0f} mm<extra></extra>")
        fig.add_scatter(x=win.index, y=win["rain_3d"], name=SERIES_LABEL["rain_3d"], mode="lines",
                        line=dict(color=SERIES["rain_3d"], width=2),
                        hovertemplate="%{x|%d %b}: %{y:.0f} mm<extra></extra>")
        th = D["thresholds"]
        for t in ("Alert", "Emergency"):
            fig.add_hline(y=th.loc[t, "rain_3d"], line=dict(color=TIER_COLOR[t], dash="dot", width=1),
                          annotation_text=f"{TIER_ICON[t]} {t} (3-day)", annotation_font_color=MUTED,
                          annotation_position="top left")
        fig.update_yaxes(title="mm")
        st.plotly_chart(style(fig, 360, title=pick, bargap=0.3), width="stretch")

    c1, c2 = st.columns(2, gap="large")
    with c1:
        st.markdown("**How often each tier fires (all history)**")
        st.dataframe(td.style.format({"days": "{:.0f}", "share_pct": "{:.2f}%", "days_per_year": "{:.2f}"}),
                     width="stretch")
    with c2:
        st.markdown("**Top 15 Alert-or-above episodes on record**")
        ep = D["episodes"].head(15).copy()
        ep["peak_tier"] = ep["peak_tier"].map(lambda t: f"{TIER_ICON[t]} {t}")
        st.dataframe(ep, hide_index=True, width="stretch",
                     column_config={c: st.column_config.NumberColumn(format="%.0f")
                                    for c in ("max_rain_1d", "max_rain_3d", "max_return_period")})

    ty = D["tier_year"]
    fig = go.Figure()
    for t in ("Watch", "Alert", "Emergency"):
        fig.add_bar(x=ty.index, y=ty[t], name=f"{TIER_ICON[t]} {t}", marker_color=TIER_COLOR[t],
                    hovertemplate="%{x}: %{y} days<extra>" + t + "</extra>")
    fig.update_yaxes(title="Days")
    st.plotly_chart(style(fig, 300, title="Elevated-tier days per year", barmode="stack", bargap=0.15),
                    width="stretch")

# --------------------------------------------------------------------------- About

with tabs[5]:
    st.markdown(
        """
#### Method
1. **Data**: IMD daily gridded rainfall (0.25°, 1901–2024), read with `imdlib`. The Chennai series is
   the mean of the valid land cells covering the city.
2. **Features**: 1-day rainfall and trailing 3-day accumulation; calendar-year maxima of each.
3. **Extremes**: Gumbel and GEV fitted by maximum likelihood to the annual maxima; selection by AIC and a
   likelihood-ratio test; return levels with bootstrap 95% confidence intervals.
4. **Tiers**: a day is *Watch* if either accumulation is above the 95th percentile of wet days, *Alert* at a
   2-year return period, *Emergency* at 10 years (see `configs/thresholds.yaml`).
5. **Actions**: each tier triggers a set of actions (`configs/actions.yaml`), scored on five criteria.
   Weights come from an AHP pairwise matrix (consistency ratio < 0.10) and the ranking is stress-tested
   with one-at-a-time and Monte Carlo weight perturbation.
6. **Trend**: Mann-Kendall with Sen's slope, and OLS with a confidence interval, on annual maxima.
7. **Validation**: documented flood episodes (2005, 2015, 2016, 2021, 2023) should rank in the top tiers.

#### Limitations
* Rainfall alone cannot show whether a particular road or ward will flood. The 25 km grid supports
  **city-level** statements only.
* With no historical flood labels, this is a **preparedness-ranking model**, not a validated flood predictor.
* Criterion scores for actions are expert judgements and should be reviewed with the Greater Chennai Corporation.
* Coastal grid cells are masked in the IMD product, so the city mean leans on the inland cells.
"""
    )
