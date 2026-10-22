"""Action catalogue: which preparedness actions each tier triggers."""

import pandas as pd

from ..risk.tiers import tier_rank
from ..utils.config import load_config


def load_actions(cfg: dict | None = None) -> pd.DataFrame:
    """One row per action: name, min_tier, and a column per criterion score."""
    cfg = cfg or load_config("actions")
    rows = [{"id": a["id"], "name": a["name"], "min_tier": a["min_tier"], **a["scores"]} for a in cfg["actions"]]
    return pd.DataFrame(rows).set_index("id")


def actions_for_tier(actions: pd.DataFrame, tier: str) -> pd.DataFrame:
    """Actions triggered at ``tier`` (an action's trigger carries forward to higher tiers)."""
    r = tier_rank(tier)
    return actions[actions["min_tier"].map(tier_rank) <= r]
