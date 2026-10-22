"""Gumbel and GEV fits to annual maxima, with goodness-of-fit.

scipy's ``genextreme`` uses shape ``c = -xi`` (xi is the usual GEV shape in
hydrology). We store ``c`` as scipy has it and report ``xi`` alongside.
"""

from dataclasses import asdict, dataclass

import numpy as np
from scipy import stats

DISTRIBUTIONS = {"gev": stats.genextreme, "gumbel": stats.gumbel_r}


@dataclass
class Fit:
    dist: str
    params: tuple  # scipy order: (shape?, loc, scale)
    n: int
    log_likelihood: float
    aic: float
    ks_stat: float
    ks_pvalue: float

    @property
    def frozen(self):
        return DISTRIBUTIONS[self.dist](*self.params)

    @property
    def xi(self) -> float | None:
        return -self.params[0] if self.dist == "gev" else None

    def cdf(self, x):
        return self.frozen.cdf(x)

    def ppf(self, q):
        return self.frozen.ppf(q)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["params"] = [float(p) for p in self.params]
        d["xi"] = self.xi
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "Fit":
        d = {k: v for k, v in d.items() if k != "xi"}
        d["params"] = tuple(d["params"])
        return cls(**d)


def fit(sample, dist: str = "gev") -> Fit:
    x = np.asarray(sample, dtype=float)
    x = x[np.isfinite(x)]
    family = DISTRIBUTIONS[dist]
    if dist == "gev":
        # Start from the Gumbel solution; the default start often lands on a
        # degenerate heavy-tailed optimum for short records.
        loc0, scale0 = stats.gumbel_r.fit(x)
        params = family.fit(x, 0.0, loc=loc0, scale=scale0)
    else:
        params = family.fit(x)
    ll = float(np.sum(family.logpdf(x, *params)))
    ks = stats.kstest(x, family.cdf, args=params)
    return Fit(
        dist=dist,
        params=tuple(float(p) for p in params),
        n=len(x),
        log_likelihood=ll,
        aic=2 * len(params) - 2 * ll,
        ks_stat=float(ks.statistic),
        ks_pvalue=float(ks.pvalue),
    )


def fit_all(sample) -> dict[str, Fit]:
    return {name: fit(sample, name) for name in DISTRIBUTIONS}


def best_fit(fits: dict[str, Fit]) -> Fit:
    """Lowest AIC; GEV must beat Gumbel by > 2 AIC units to justify its extra parameter."""
    gev, gum = fits["gev"], fits["gumbel"]
    return gev if gev.aic < gum.aic - 2 else gum


def likelihood_ratio_test(fits: dict[str, Fit]) -> dict:
    """Gumbel is GEV with xi = 0; LR statistic ~ chi2(1)."""
    lr = 2 * (fits["gev"].log_likelihood - fits["gumbel"].log_likelihood)
    lr = max(lr, 0.0)
    return {"statistic": lr, "pvalue": float(stats.chi2.sf(lr, df=1))}
