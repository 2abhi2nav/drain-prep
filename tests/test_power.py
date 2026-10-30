import pandas as pd

from drainage_rec.power import (
    fit_station_generation_regression, load_station_priorities, load_zone_demographics,
    score_power_preparedness,
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

    scored = score_power_preparedness(zones, [0.6, 0.6], "No warning").set_index("Zone Name")
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


def test_station_relief_ranking_uses_tamil_nadu_plant_data():
    stations = load_station_priorities()

    assert len(stations) > 40
    assert abs(stations["capacity_mw"].sum() - 19_946.08) < 0.01
    assert abs(stations["actual_ytd"].sum() - 77_136.36) < 0.01
    assert abs(stations["estimated_population_proxy"].sum() - 4_646_732) < 1
    assert abs(stations["previous_generation_share"].sum() - 1) < 1e-9
    assert "program_ytd" not in stations


def test_heavy_rain_logistic_is_trained_and_predicts_higher_probability_for_heavier_rain():
    from drainage_rec.stats.predictive import fit_heavy_rain_model

    model = fit_heavy_rain_model()
    probability = model.predict_probability([10, 150], [30, 300], [11, 11])
    assert probability[1] > probability[0]
    assert 0 <= probability.min() <= probability.max() <= 1
    assert model.metrics["auc"] > 0.5


def test_station_priorities_respond_to_zone_rainfall_probabilities():
    zones = load_zone_demographics()
    dry = score_power_preparedness(zones, [0.01] * len(zones), "No warning")
    wet = score_power_preparedness(zones, [0.8] * len(zones), "No warning")

    dry_stations = load_station_priorities(zones, dry)
    wet_stations = load_station_priorities(zones, wet)
    assert wet_stations["estimated_population_proxy"].sum() > dry_stations["estimated_population_proxy"].sum()
    assert wet_stations["weighted_prioritized_population"].sum() > dry_stations["weighted_prioritized_population"].sum()


def test_station_generation_regression_uses_prioritized_population():
    zones = load_zone_demographics()
    predictions = score_power_preparedness(zones, [0.15 + i * 0.06 for i in range(len(zones))], "No warning")
    base = load_station_priorities(zones, predictions)
    ranked, metrics = fit_station_generation_regression(base)

    assert "weighted_prioritized_population" in metrics["coefficients"].index
    assert ranked["predicted_actual_ytd"].ge(0).all()
    assert ranked["relief_resource_share_pct"].between(0, 100).all()
    assert abs(ranked["relief_resource_share_pct"].sum() - 100) < 1e-9
    assert metrics["n_train"] + metrics["n_test"] == len(base)
