"""Analytic Hierarchy Process: weights from a pairwise comparison matrix."""

from fractions import Fraction

import numpy as np

# Saaty's random consistency index by matrix order.
RANDOM_INDEX = {1: 0.0, 2: 0.0, 3: 0.58, 4: 0.90, 5: 1.12, 6: 1.24, 7: 1.32, 8: 1.41, 9: 1.45, 10: 1.49}


def _num(v) -> float:
    return float(Fraction(str(v)))


def pairwise_matrix(criteria: list[str], upper: dict) -> np.ndarray:
    """Build a reciprocal matrix from the upper-triangle judgements in weights.yaml."""
    n = len(criteria)
    A = np.ones((n, n))
    pos = {c: i for i, c in enumerate(criteria)}
    for a, row in (upper or {}).items():
        for b, v in row.items():
            i, j = pos[a], pos[b]
            A[i, j] = _num(v)
            A[j, i] = 1 / A[i, j]
    return A


def ahp_weights(A: np.ndarray) -> dict:
    """Principal-eigenvector weights and Saaty consistency ratio (CR < 0.10 is acceptable)."""
    vals, vecs = np.linalg.eig(A)
    k = int(np.argmax(vals.real))
    w = np.abs(vecs[:, k].real)
    w /= w.sum()
    n = A.shape[0]
    lam = float(vals[k].real)
    ci = (lam - n) / (n - 1) if n > 1 else 0.0
    ri = RANDOM_INDEX.get(n, 1.49)
    cr = ci / ri if ri else 0.0
    return {"weights": w, "lambda_max": lam, "ci": ci, "cr": cr, "consistent": cr < 0.10}


def weights_from_config(cfg: dict) -> tuple[list[str], np.ndarray, dict]:
    criteria = cfg["criteria"]
    A = pairwise_matrix(criteria, cfg["pairwise"])
    return criteria, A, ahp_weights(A)
