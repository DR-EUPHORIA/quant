"""
quanta_stock - A-share research pipeline package.
"""

from .io import load_optional_parquet, load_parquet, resolve_output_path
from .panel import build_panel
from .paths import (
    ROOT,
    DATA_ROOT,
    RAW_DIR,
    PROCESSED_DIR,
    RESULTS_DIR,
    PANELS_DIR,
    DATA_QUALITY_DIR,
    ensure_a_stock_dirs,
)
from .universe import resolve_universe_path

__all__ = [
    "ROOT",
    "DATA_ROOT",
    "RAW_DIR",
    "PROCESSED_DIR",
    "RESULTS_DIR",
    "PANELS_DIR",
    "DATA_QUALITY_DIR",
    "ensure_a_stock_dirs",
    "load_parquet",
    "load_optional_parquet",
    "build_panel",
    "resolve_output_path",
    "resolve_universe_path",
]
