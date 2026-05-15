"""Futures market package."""

from .data import build_continuous_kline, load_hots_table
from .paths import (
    FUTURES_DATA_ROOT,
    FUTURES_HOTS_PATH,
    FUTURES_KLINE_DIR,
    FUTURES_PROCESSED_DIR,
    FUTURES_RAW_DIR,
    FUTURES_REPORTS_DIR,
    FUTURES_RESULTS_DIR,
    ensure_futures_dirs,
)
from .research import build_etf_nav, calc_metrics

__all__ = [
    "FUTURES_DATA_ROOT",
    "FUTURES_HOTS_PATH",
    "FUTURES_KLINE_DIR",
    "FUTURES_PROCESSED_DIR",
    "FUTURES_RAW_DIR",
    "FUTURES_REPORTS_DIR",
    "FUTURES_RESULTS_DIR",
    "build_continuous_kline",
    "build_etf_nav",
    "calc_metrics",
    "ensure_futures_dirs",
    "load_hots_table",
]
