"""Fetch IMD 0.25 deg gridded rainfall (.grd) files year by year.

The IMD archive is slow (minutes per year), so downloads run in parallel and
skip years already on disk. Each completed year is immediately reduced to the
Chennai series by :mod:`drainage_rec.data.extract`, so raw files can be
discarded to save space (~25 MB per year).
"""

import calendar
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from imdlib.core import ARCHIVE_GRID, ARCHIVE_URLS, GRIDS

from ..utils.config import RAW_DIR

log = logging.getLogger(__name__)

ARCHIVE_URL = ARCHIVE_URLS["rain"][0]
# imdlib's own downloader has no timeout and hangs on stalled connections, so we
# POST to the same archive endpoint ourselves, streaming with a read timeout.
CONNECT_TIMEOUT, READ_TIMEOUT = 30, 120
RETRIES = 4


def expected_size(year: int) -> int:
    return GRIDS[ARCHIVE_GRID["rain"]].file_size(366 if calendar.isleap(year) else 365)


def raw_path(year: int, raw_dir: Path = RAW_DIR) -> Path:
    return raw_dir / "rain" / f"{year}.grd"


def download_year(year: int, raw_dir: Path = RAW_DIR) -> Path:
    path = raw_path(year, raw_dir)
    size = expected_size(year)
    if path.exists() and path.stat().st_size == size:
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    part = path.with_suffix(".part")
    for attempt in range(1, RETRIES + 1):
        try:
            with requests.post(ARCHIVE_URL, data={"rain": year}, stream=True,
                               timeout=(CONNECT_TIMEOUT, READ_TIMEOUT)) as r:
                r.raise_for_status()
                with open(part, "wb") as f:
                    for chunk in r.iter_content(1 << 16):
                        f.write(chunk)
            got = part.stat().st_size
            if got != size:
                raise RuntimeError(f"got {got} bytes, expected {size}")
            part.replace(path)
            return path
        except (requests.RequestException, RuntimeError) as exc:
            log.warning("year %s attempt %d/%d: %s", year, attempt, RETRIES, exc)
            part.unlink(missing_ok=True)
            time.sleep(5 * attempt)
    raise RuntimeError(f"IMD download for {year} failed after {RETRIES} attempts")


def download_years(years, raw_dir: Path = RAW_DIR, workers: int = 3, on_done=None) -> list[int]:
    """Download several years concurrently. Calls ``on_done(year, path)`` as each lands.

    Returns the list of years that failed.
    """
    failed = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(download_year, y, raw_dir): y for y in years}
        for fut in as_completed(futures):
            year = futures[fut]
            try:
                path = fut.result()
            except Exception as exc:  # network errors are common on the IMD server
                log.warning("year %s: %s", year, exc)
                failed.append(year)
                continue
            if on_done is not None:
                on_done(year, path)
    return sorted(failed)
