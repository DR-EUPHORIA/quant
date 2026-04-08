"""A-share CLI entry points."""

from .backtest_ma import main as backtest_ma_main
from .build_panel import main as build_panel_main
from .data_quality_check import main as data_quality_check_main
from .factor_test import main as factor_test_main

__all__ = [
    "build_panel_main",
    "backtest_ma_main",
    "factor_test_main",
    "data_quality_check_main",
]
