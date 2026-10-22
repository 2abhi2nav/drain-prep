"""Clip the IMD grid to Chennai and build the daily city-level series."""

from pathlib import Path

import pandas as pd
import xarray as xr

from ..utils.config import INTERIM_DIR, load_config
from ..utils.io import read_city_series, write_city_series
from .load import load_year

YEAR_DIR = INTERIM_DIR / "years"


def clip_to_study_area(grid: xr.DataArray, area: dict | None = None) -> xr.DataArray:
    area = area or load_config("study_area")
    return grid.sel(
        lat=slice(area["lat_min"], area["lat_max"]),
        lon=slice(area["lon_min"], area["lon_max"]),
    )


def city_series(grid: xr.DataArray, area: dict | None = None) -> pd.Series:
    """Aggregate valid (land) cells inside the study area into one daily series."""
    area = area or load_config("study_area")
    cells = clip_to_study_area(grid, area)
    how = area.get("aggregation", "mean")
    agg = cells.mean(dim=("lat", "lon"), skipna=True) if how == "mean" else cells.max(dim=("lat", "lon"), skipna=True)
    s = agg.to_series()
    s.index = pd.to_datetime(s.index).normalize()
    s.index.name = "date"
    return s.clip(lower=0).rename("rain_mm")


def cell_table(grid: xr.DataArray, area: dict | None = None) -> pd.DataFrame:
    """Per-cell daily values (wide), kept so the dashboard can show the grid."""
    cells = clip_to_study_area(grid, area).to_dataframe().reset_index()
    cells = cells.dropna(subset=["rain"])
    cells["cell"] = cells["lat"].map("{:.2f}".format) + "N_" + cells["lon"].map("{:.2f}".format) + "E"
    return cells.pivot(index="time", columns="cell", values="rain")


def year_file(year: int) -> Path:
    return YEAR_DIR / f"{year}.csv"


def extract_year(year: int, raw_path: Path | None = None) -> Path:
    """Reduce one raw year file to the Chennai series + per-cell values."""
    grid = load_year(year) if raw_path is None else load_year(year, raw_path.parent.parent)
    out = cell_table(grid)
    out.insert(0, "rain_mm", city_series(grid))
    out.index.name = "date"
    YEAR_DIR.mkdir(parents=True, exist_ok=True)
    path = year_file(year)
    out.to_csv(path, float_format="%.3f")
    return path


def extracted_years() -> set[int]:
    return {int(p.stem) for p in YEAR_DIR.glob("*.csv")} if YEAR_DIR.exists() else set()


def combine_years() -> pd.Series:
    """Concatenate per-year extracts into data/interim/chennai_daily.csv."""
    frames = [pd.read_csv(p, parse_dates=["date"], index_col="date") for p in sorted(YEAR_DIR.glob("*.csv"))]
    if not frames:
        raise FileNotFoundError(f"No extracted years in {YEAR_DIR}; run `drainage-rec download` first")
    s = pd.concat(frames)["rain_mm"].sort_index()
    s = s[~s.index.duplicated()]
    write_city_series(s)
    return s


def combined_cells() -> pd.DataFrame:
    frames = [pd.read_csv(p, parse_dates=["date"], index_col="date") for p in sorted(YEAR_DIR.glob("*.csv"))]
    return pd.concat(frames).drop(columns="rain_mm").sort_index()


__all__ = ["city_series", "extract_year", "combine_years", "read_city_series", "extracted_years"]
