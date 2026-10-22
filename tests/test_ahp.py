import numpy as np

from drainage_rec.decision.ahp import ahp_weights, pairwise_matrix, weights_from_config
from drainage_rec.utils.config import load_config


def test_perfectly_consistent_matrix():
    w = np.array([0.5, 0.3, 0.2])
    A = w[:, None] / w[None, :]
    r = ahp_weights(A)
    assert np.allclose(r["weights"], w)
    assert abs(r["cr"]) < 1e-9


def test_reciprocal_fill_and_fractions():
    A = pairwise_matrix(["a", "b", "c"], {"a": {"b": 3, "c": "1/2"}})
    assert A[1, 0] == 1 / 3
    assert A[0, 2] == 0.5 and A[2, 0] == 2


def test_project_weights_are_consistent():
    criteria, A, r = weights_from_config(load_config("weights"))
    assert np.allclose(A * A.T, 1)
    assert np.isclose(r["weights"].sum(), 1)
    assert r["cr"] < 0.10
    assert criteria[int(np.argmax(r["weights"]))] == "impact"
