"""Sanity check without flood labels: known floods should land in the top tiers."""

import pandas as pd

from ..risk.tiers import tier_rank


def evaluate_events(classified: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """Peak tier, rainfall and return period reached inside each event window.

    ``severity_percentile`` is where the event's worst day sits among all
    historical days ranked by (tier, max return period) - 99.9 means it beats
    99.9% of all days on record.
    """
    rp = classified[["rain_1d_rp", "rain_3d_rp"]].max(axis=1)
    severity = classified["tier_idx"] * 1e6 + rp.clip(upper=1e5)
    sev_pct = severity.rank(pct=True) * 100
    rows = []
    for ev in events.itertuples():
        win = classified.loc[ev.start: ev.end]
        if win.empty:
            rows.append({"event": ev.event, "start": ev.start, "end": ev.end, "in_record": False})
            continue
        peak = severity.loc[win.index].idxmax()
        rows.append({
            "event": ev.event,
            "start": ev.start.date(),
            "end": ev.end.date(),
            "in_record": True,
            "peak_date": peak.date(),
            "peak_tier": str(win.loc[peak, "tier"]),
            "max_rain_1d": win["rain_1d"].max(),
            "max_rain_3d": win["rain_3d"].max(),
            "max_return_period": rp.loc[win.index].max(),
            "severity_percentile": sev_pct.loc[peak],
            "days_alert_or_above": int((win["tier_idx"] >= tier_rank("Alert")).sum()),
        })
    return pd.DataFrame(rows)


def hit_rate(event_table: pd.DataFrame, min_tier: str = "Alert") -> float:
    t = event_table[event_table["in_record"]]
    if t.empty:
        return float("nan")
    return float((t["peak_tier"].map(tier_rank) >= tier_rank(min_tier)).mean())
