"""Project paths and YAML config loading."""

from functools import lru_cache
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[3]
CONFIG_DIR = ROOT / "configs"
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
INTERIM_DIR = DATA_DIR / "interim"
PROCESSED_DIR = DATA_DIR / "processed"
EXTERNAL_DIR = DATA_DIR / "external"
OUTPUT_DIR = ROOT / "outputs"


@lru_cache(maxsize=None)
def load_config(name: str) -> dict:
    """Load configs/<name>.yaml."""
    with open(CONFIG_DIR / f"{name}.yaml") as f:
        return yaml.safe_load(f)
