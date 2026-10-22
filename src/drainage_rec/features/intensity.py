"""Daily intensity categories (IMD heavy-rainfall classes, mm/day)."""

import numpy as np
import pandas as pd

# IMD classification for 24-h station rainfall.
IMD_CATEGORIES = [
    ("No rain", 0.0),
    ("Very light", 0.1),
    ("Light", 2.5),
    ("Moderate", 15.6),
    ("Heavy", 64.5),
    ("Very heavy", 115.6),
    ("Extremely heavy", 204.5),
]


def categorize(rain_mm: pd.Series) -> pd.Series:
    edges = [lo for _, lo in IMD_CATEGORIES[1:]]
    labels = [name for name, _ in IMD_CATEGORIES]
    idx = np.digitize(rain_mm.to_numpy(), edges)
    return pd.Series(pd.Categorical.from_codes(idx, labels, ordered=True), index=rain_mm.index)
