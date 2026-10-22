import numpy as np
from scipy import stats

from drainage_rec.stats.distributions import fit
from drainage_rec.stats.return_period import bootstrap_return_levels, return_level, return_period


def test_return_level_and_period_are_inverse():
    x = stats.gumbel_r.rvs(loc=80, scale=25, size=100, random_state=0)
    f = fit(x, "gumbel")
    for T in (2, 10, 100):
        assert np.isclose(return_period(f, return_level(f, T)), T)


def test_two_year_level_is_median():
    x = stats.gumbel_r.rvs(loc=80, scale=25, size=100, random_state=0)
    f = fit(x, "gumbel")
    assert np.isclose(return_level(f, 2), f.ppf(0.5))


def test_bootstrap_ci_brackets_estimate():
    x = stats.gumbel_r.rvs(loc=80, scale=25, size=80, random_state=0)
    t = bootstrap_return_levels(x, "gumbel", n_boot=200)
    assert (t["ci_lower"] <= t["return_level"]).all()
    assert (t["return_level"] <= t["ci_upper"]).all()
    assert t["return_level"].is_monotonic_increasing
