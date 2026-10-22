"""Reading and writing of intermediate tables."""

import json
from pathlib import Path

import pandas as pd

from .config import EXTERNAL_DIR, INTERIM_DIR, PROCESSED_DIR

CITY_SERIES = INTERIM_DIR / "chennai_daily.csv"


def read_city_series(path: Path = CITY_SERIES) -> pd.Series:
    """Daily city-mean rainfall (mm) indexed by date."""
    df = pd.read_csv(path, parse_dates=["date"], index_col="date")
    return df["rain_mm"].sort_index()


def write_city_series(series: pd.Series, path: Path = CITY_SERIES) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    series.rename("rain_mm").rename_axis("date").to_csv(path, float_format="%.3f")


def read_known_events(path: Path = EXTERNAL_DIR / "known_flood_events.csv") -> pd.DataFrame:
    return pd.read_csv(path, parse_dates=["start", "end"])


def write_table(df: pd.DataFrame, name: str, directory: Path = PROCESSED_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{name}.csv"
    df.to_csv(path)
    return path


def write_json(obj, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, default=str)
