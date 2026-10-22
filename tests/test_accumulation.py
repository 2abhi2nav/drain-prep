import pandas as pd

from drainage_rec.features.accumulation import accumulate
from drainage_rec.features.annual_max import annual_maxima


def test_three_day_is_trailing_sum():
    s = pd.Series([1.0, 2.0, 3.0, 4.0], index=pd.date_range("2020-01-01", periods=4))
    acc = accumulate(s)
    assert acc["rain_1d"].tolist() == [1, 2, 3, 4]
    assert acc["rain_3d"].tolist() == [1, 3, 6, 9]


def test_missing_days_filled_with_zero():
    s = pd.Series([5.0, 5.0], index=pd.to_datetime(["2020-01-01", "2020-01-03"]))
    acc = accumulate(s)
    assert len(acc) == 3
    assert acc["rain_3d"].iloc[-1] == 10


def test_annual_maxima_drops_partial_years(synthetic_daily):
    acc = accumulate(synthetic_daily)
    amax = annual_maxima(acc)
    assert len(amax) == 80
    assert (amax["rain_3d"] >= amax["rain_1d"]).all()
    assert annual_maxima(acc.iloc[:100]).empty
