import pandas as pd

from drainage_rec.power import (
    allocate_resources, load_station_profiles, load_zone_demographics, score_power_preparedness,
)


def test_population_and_vulnerable_groups_raise_priority():
    zones = pd.DataFrame({
        "Zone Name": ["A", "B"],
        "population": [1000, 1000],
        "children": [100, 300],
        "youth": [200, 200],
        "adults": [600, 400],
        "seniors": [100, 100],
        "wards": [10, 10],
    })

    scored = score_power_preparedness(zones, [0.6, 0.6], "No warning", [0, 0]).set_index("Zone Name")
    assert scored.loc["B", "priority_score"] > scored.loc["A", "priority_score"]
    assert scored["priority_score"].max() > 0
    assert scored["population_component"].between(0, 1).all()
    assert scored["vulnerability_component"].between(0, 1).all()


def test_zone_demographic_source_age_bands_reconcile():
    zones = load_zone_demographics()
    assert zones["population"].sum() == 4_646_732
    assert zones["children"].sum() + zones["youth"].sum() + zones["adults"].sum() + zones["seniors"].sum() == 4_646_732


def test_warning_can_raise_preparedness_severity():
    zones = pd.DataFrame({
        "Zone Name": ["A"], "population": [1000], "children": [250],
        "youth": [180], "adults": [450], "seniors": [120], "wards": [10],
    })

    probability = [0.2]
    alert = score_power_preparedness(zones, probability, "No warning").iloc[0]
    red = score_power_preparedness(zones, probability, "Red").iloc[0]
    assert red["priority_score"] > alert["priority_score"]


def test_station_profile_uses_tamil_nadu_plant_data():
    stations = load_station_profiles()

    assert len(stations) > 40
    assert abs(stations["capacity_mw"].sum() - 19_946.08) < 0.01
    assert abs(stations["actual_ytd"].sum() - 77_136.36) < 0.01
    assert stations["previous_actual_ytd"].sum() > 0


def test_heavy_rain_logistic_is_trained_and_predicts_higher_probability_for_heavier_rain():
    from drainage_rec.stats.predictive import fit_heavy_rain_model

    model = fit_heavy_rain_model()
    probability = model.predict_probability([10, 300], [11, 11])
    assert probability[1] > probability[0]
    assert 0 <= probability.min() <= probability.max() <= 1
    assert model.metrics["auc"] > 0.5
    assert "rain_1d" not in model.metrics["coefficients"].index
    assert "log_3d_rain_prior" in model.metrics["coefficients"].index


def test_zone_rainfall_signal_responds_to_zone_inputs():
    zones = load_zone_demographics()
    dry = score_power_preparedness(zones, [0.2] * len(zones), "No warning", [5] * len(zones))
    wet = score_power_preparedness(zones, [0.2] * len(zones), "No warning", [95] * len(zones))
    assert wet["priority_score"].sum() > dry["priority_score"].sum()


def test_resource_allocation_respects_requested_integer_total():
    zones = load_zone_demographics()
    scored = score_power_preparedness(zones, [0.35] * len(zones), "No warning", [70] * len(zones))
    allocation = allocate_resources(scored, 24)
    assert allocation["recommended_resources"].sum() == 24
    assert abs(allocation["resource_share_pct"].sum() - 100) < 1e-9
