"""Rainfall -> percentile / return period -> risk tier."""

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from ..features.accumulation import ACCUMULATION_WINDOWS, accumulate
from ..features.annual_max import annual_maxima
from ..stats.distributions import Fit, best_fit, fit_all
from ..stats.percentiles import EmpiricalCDF
from ..stats.return_period import return_period
from ..utils.config import load_config

TIER_ORDER = ["Normal", "Watch", "Alert", "Emergency"]


def tier_rank(name: str) -> int:
    return TIER_ORDER.index(name)


@dataclass
class RiskModel:
    """Fitted per-accumulation distributions and tier rules."""

    fits: dict[str, Fit]                       # best fit per accumulation
    wet_samples: dict[str, np.ndarray]         # historical wet-day values per accumulation
    tiers: list[dict] = field(default_factory=lambda: load_config("thresholds")["tiers"])
    wet_day_mm: float = 2.5

    def __post_init__(self):
        self._ecdf = {k: EmpiricalCDF(v) for k, v in self.wet_samples.items()}

    @classmethod
    def fit(cls, daily: pd.Series, thresholds: dict | None = None) -> "RiskModel":
        thresholds = thresholds or load_config("thresholds")
        acc = accumulate(daily)
        amax = annual_maxima(acc)
        wet = thresholds.get("wet_day_mm", 2.5)
        return cls(
            fits={k: best_fit(fit_all(amax[k])) for k in ACCUMULATION_WINDOWS},
            wet_samples={k: acc[k][acc[k] >= wet].to_numpy() for k in ACCUMULATION_WINDOWS},
            tiers=thresholds["tiers"],
            wet_day_mm=wet,
        )

    def percentile(self, key: str, value):
        return self._ecdf[key].percentile(value)

    def return_period(self, key: str, value):
        return return_period(self.fits[key], value)

    def tier_index(self, values: dict) -> np.ndarray:
        """Vectorised tier index for arrays of rain_1d / rain_3d."""
        pct = {k: np.asarray(self.percentile(k, v)) for k, v in values.items()}
        rp = {k: np.asarray(self.return_period(k, v)) for k, v in values.items()}
        shape = np.broadcast(*pct.values()).shape
        idx = np.zeros(shape, dtype=int)
        for i, rule in enumerate(self.tiers):
            hit = np.zeros(shape, dtype=bool)
            if "percentile" in rule:
                hit |= np.any([p >= rule["percentile"] for p in pct.values()], axis=0)
            if "return_period" in rule:
                hit |= np.any([r >= rule["return_period"] for r in rp.values()], axis=0)
            # A dry day (both below the wet-day cut-off) never escalates.
            if i > 0:
                hit &= np.any([np.asarray(v) >= self.wet_day_mm for v in values.values()], axis=0)
                idx = np.where(hit, i, idx)
        return idx

    def assess(self, rain_1d: float, rain_3d: float) -> dict:
        rain_3d = max(rain_3d, rain_1d)  # a 3-day total cannot be below its last day
        values = {"rain_1d": rain_1d, "rain_3d": rain_3d}
        tier = self.tiers[int(self.tier_index(values))]["name"]
        detail = {
            k: {
                "value_mm": float(v),
                "percentile": float(self.percentile(k, v)),
                "return_period": float(self.return_period(k, v)),
            }
            for k, v in values.items()
        }
        driver = max(detail, key=lambda k: (detail[k]["return_period"], detail[k]["percentile"]))
        return {"tier": tier, "driver": driver, **detail}

    def thresholds_mm(self) -> pd.DataFrame:
        """Rainfall (mm) at which each tier begins, per accumulation."""
        rows = {}
        for rule in self.tiers[1:]:
            row = {}
            for k in self.fits:
                cands = []
                if "percentile" in rule:
                    cands.append(float(self._ecdf[k].quantile(rule["percentile"])))
                if "return_period" in rule:
                    cands.append(float(self.fits[k].ppf(1 - 1 / rule["return_period"])))
                row[k] = min(cands)
            rows[rule["name"]] = row
        return pd.DataFrame(rows).T

    def to_dict(self) -> dict:
        return {
            "fits": {k: f.to_dict() for k, f in self.fits.items()},
            "wet_samples": {k: np.round(v, 3).tolist() for k, v in self.wet_samples.items()},
            "tiers": self.tiers,
            "wet_day_mm": self.wet_day_mm,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "RiskModel":
        return cls(
            fits={k: Fit.from_dict(f) for k, f in d["fits"].items()},
            wet_samples={k: np.asarray(v) for k, v in d["wet_samples"].items()},
            tiers=d["tiers"],
            wet_day_mm=d["wet_day_mm"],
        )
