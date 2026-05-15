from __future__ import annotations

import pandas as pd

from quantbt import MASignalGenerator


def generate_ma_signals(
    panel: pd.DataFrame,
    fast_period: int = 5,
    slow_period: int = 20,
    price_col: str = "close",
) -> pd.DataFrame:
    required_cols = {"trade_date", "ts_code", price_col}
    missing = required_cols.difference(panel.columns)
    if missing:
        raise ValueError(f"crypto panel missing columns: {sorted(missing)}")

    generator = MASignalGenerator(
        fast_period=fast_period,
        slow_period=slow_period,
        price_col=price_col,
    )
    return generator.generate(panel)
