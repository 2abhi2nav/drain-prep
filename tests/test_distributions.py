import numpy as np
from scipy import stats

from drainage_rec.stats.distributions import best_fit, fit, fit_all, likelihood_ratio_test


def test_gumbel_recovers_parameters():
    x = stats.gumbel_r.rvs(loc=100, scale=30, size=2000, random_state=1)
    f = fit(x, "gumbel")
    assert abs(f.params[0] - 100) < 3
    assert abs(f.params[1] - 30) < 3
    assert f.ks_pvalue > 0.05


def test_gumbel_preferred_for_gumbel_data():
    x = stats.gumbel_r.rvs(loc=100, scale=30, size=120, random_state=2)
    fits = fit_all(x)
    assert best_fit(fits).dist == "gumbel"
    assert likelihood_ratio_test(fits)["pvalue"] > 0.01


def test_gev_detects_heavy_tail():
    x = stats.genextreme.rvs(-0.3, loc=100, scale=30, size=1000, random_state=3)
    fits = fit_all(x)
    assert best_fit(fits).dist == "gev"
    assert fits["gev"].xi > 0.1


def test_roundtrip_dict():
    f = fit(np.arange(1, 50, dtype=float), "gev")
    from drainage_rec.stats.distributions import Fit

    g = Fit.from_dict(f.to_dict())
    assert np.allclose(g.cdf([10, 20]), f.cdf([10, 20]))
