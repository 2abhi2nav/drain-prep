"""Read IMD binary .grd files into xarray via imdlib."""

from pathlib import Path

import xarray as xr
import imdlib

from ..utils.config import RAW_DIR


def load_year(year: int, raw_dir: Path = RAW_DIR) -> xr.DataArray:
    """Daily rainfall grid (time, lat, lon) in mm for one year; sea cells are NaN."""
    data = imdlib.open_data("rain", year, year, fn_format="yearwise", file_dir=str(raw_dir))
    return data.get_xarray()["rain"]
