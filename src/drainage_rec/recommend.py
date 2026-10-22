"""Main entry point: (rain_1d, rain_3d) -> risk tier + prioritised action set."""

import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .decision.actions import actions_for_tier, load_actions
from .decision.ahp import weights_from_config
from .decision.matrix import score_actions
from .risk.tiers import RiskModel
from .utils.config import PROCESSED_DIR, load_config

MODEL_PATH = PROCESSED_DIR / "model.json"


@dataclass
class Recommendation:
    tier: str
    driver: str
    assessment: dict
    actions: list[dict]

    def to_dict(self) -> dict:
        return asdict(self)


class Recommender:
    def __init__(self, model: RiskModel, actions: pd.DataFrame | None = None,
                 criteria: list[str] | None = None, weights=None):
        self.model = model
        self.actions = load_actions() if actions is None else actions
        if criteria is None or weights is None:
            criteria, _, ahp = weights_from_config(load_config("weights"))
            weights = ahp["weights"]
        self.criteria = criteria
        self.weights = np.asarray(weights, dtype=float)

    @classmethod
    def load(cls, path: Path = MODEL_PATH, **kwargs) -> "Recommender":
        if not path.exists():
            raise FileNotFoundError(f"{path} not found; run `drainage-rec pipeline` first")
        with open(path) as f:
            return cls(RiskModel.from_dict(json.load(f)), **kwargs)

    def ranked_actions(self, tier: str) -> pd.DataFrame:
        triggered = actions_for_tier(self.actions, tier)
        if triggered.empty:
            return triggered.assign(score=[], rank=[])
        return score_actions(triggered, self.criteria, self.weights)

    def recommend(self, rain_1d: float, rain_3d: float) -> Recommendation:
        a = self.model.assess(rain_1d, rain_3d)
        ranked = self.ranked_actions(a["tier"])
        actions = [
            {"id": i, "name": r["name"], "min_tier": r["min_tier"], "score": float(r["score"]), "rank": int(r["rank"])}
            for i, r in ranked.iterrows()
        ]
        return Recommendation(
            tier=a["tier"],
            driver=a["driver"],
            assessment={k: a[k] for k in ("rain_1d", "rain_3d")},
            actions=actions,
        )


def recommend(rain_1d: float, rain_3d: float) -> Recommendation:
    return Recommender.load().recommend(rain_1d, rain_3d)
