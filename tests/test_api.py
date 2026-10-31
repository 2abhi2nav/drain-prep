import pytest

pytest.importorskip("fastapi")

from drainage_rec.web_api import (
    RainfallRequest, ZoneRainfall, ZoneRequest, bootstrap, forecast, population_priority, power_stations,
)


def _scenario():
    data = bootstrap()
    return ZoneRequest(
        month=11,
        warning="No warning",
        resource_units=24,
        zones=[ZoneRainfall(zone=z["name"], rain_1d=80, rain_3d=160) for z in data["zones"]],
    )


def test_forecast_api_returns_logistic_and_tier_outputs():
    response = forecast(RainfallRequest(rain_1d=80, rain_3d=160, month=11))
    assert 0 <= response["heavy_rain_probability"] <= 1
    assert response["assessment"]["tier"] in {"Normal", "Watch", "Alert", "Emergency"}


def test_population_api_returns_all_zones():
    request = _scenario()
    response = population_priority(request)
    assert len(response["zones"]) == len(request.zones)
    assert all(0 <= zone["model_probability"] <= 1 for zone in response["zones"])


def test_station_api_predicts_generation_and_prescribes_full_resource_split():
    allocation = population_priority(_scenario())
    response = power_stations()
    assert sum(zone["recommended_resources"] for zone in allocation["zones"]) == 24
    assert len(response["stations"]) > 40
    assert abs(sum(row["capacity_mw"] for row in response["stations"]) - 19_946.08) < 0.01
