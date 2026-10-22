import pandas as pd

from drainage_rec.decision.actions import actions_for_tier, load_actions
from drainage_rec.decision.matrix import score_actions
from drainage_rec.decision.sensitivity import monte_carlo, one_at_a_time

CRITERIA = ["a", "b"]


def _actions():
    return pd.DataFrame({"name": ["x", "y", "z"], "a": [5, 1, 3], "b": [1, 5, 3]}, index=["x", "y", "z"])


def test_weights_drive_ranking():
    acts = _actions()
    assert score_actions(acts, CRITERIA, [0.9, 0.1]).index[0] == "x"
    assert score_actions(acts, CRITERIA, [0.1, 0.9]).index[0] == "y"
    s = score_actions(acts, CRITERIA, [0.5, 0.5])
    assert s["rank"].tolist() == [1, 2, 3]


def test_tier_actions_carry_forward():
    acts = load_actions()
    watch, alert, emerg = (set(actions_for_tier(acts, t).index) for t in ("Watch", "Alert", "Emergency"))
    assert watch < alert < emerg
    assert actions_for_tier(acts, "Normal").empty
    assert "shelter_readiness" in emerg and "shelter_readiness" not in alert


def test_sensitivity_outputs():
    acts = _actions()
    oat = one_at_a_time(acts, CRITERIA, [0.7, 0.3], 0.25)
    assert len(oat) == 4
    mc = monte_carlo(acts, CRITERIA, [0.7, 0.3], n_samples=200)
    assert mc["rank_frequency"].sum(axis=1).round(6).eq(1).all()
    assert -1 <= mc["kendall_tau"].min() <= mc["kendall_tau"].max() <= 1
