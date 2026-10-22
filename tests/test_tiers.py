import numpy as np
import pytest

from drainage_rec.risk.classify import classify_history
from drainage_rec.risk.tiers import RiskModel

THRESHOLDS = {
    "wet_day_mm": 2.5,
    "tiers": [
        {"name": "Normal"},
        {"name": "Watch", "percentile": 95},
        {"name": "Alert", "return_period": 2},
        {"name": "Emergency", "return_period": 10},
    ],
}


@pytest.fixture(scope="module")
def model(synthetic_daily):
    return RiskModel.fit(synthetic_daily, THRESHOLDS)


def test_tiers_are_monotonic_in_rainfall(model):
    tiers = [model.assess(r, r)["tier"] for r in (0, 5, 60, 150, 400)]
    order = ["Normal", "Watch", "Alert", "Emergency"]
    idx = [order.index(t) for t in tiers]
    assert idx == sorted(idx)
    assert tiers[0] == "Normal" and tiers[-1] == "Emergency"


def test_dry_day_is_normal(model):
    assert model.assess(0, 0)["tier"] == "Normal"


def test_three_day_can_drive_tier(model):
    low = model.assess(1, 1)["tier"]
    high = model.assess(1, 500)
    assert low == "Normal"
    assert high["tier"] == "Emergency" and high["driver"] == "rain_3d"


def test_thresholds_increase(model):
    th = model.thresholds_mm()
    assert th["rain_1d"].is_monotonic_increasing


def test_roundtrip_and_classify(model, synthetic_daily):
    m2 = RiskModel.from_dict(model.to_dict())
    assert m2.assess(150, 200)["tier"] == model.assess(150, 200)["tier"]
    c = classify_history(synthetic_daily, model)
    assert set(c["tier"].unique()) <= {"Normal", "Watch", "Alert", "Emergency"}
    # About one Alert-or-worse day per year is expected by construction (T = 2 y on two series)
    per_year = (c["tier_idx"] >= 2).sum() / 80
    assert 0.3 < per_year < 5
    assert np.all(c["rain_1d_rp"] >= 1)
