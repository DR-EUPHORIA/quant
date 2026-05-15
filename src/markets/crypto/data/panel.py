from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..paths import CRYPTO_PROCESSED_DIR, ensure_crypto_dirs
from .loader import normalize_crypto_ohlcv


DEFAULT_OUTPUT = CRYPTO_PROCESSED_DIR / "crypto_panel.parquet"


def build_crypto_panel(df: pd.DataFrame) -> pd.DataFrame:
    panel = normalize_crypto_ohlcv(df)
    if panel.empty:
        raise ValueError("crypto panel input is empty")

    panel = panel.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
    panel = panel.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

    grouped = panel.groupby("ts_code", group_keys=False)
    panel["ret_1d"] = grouped["close"].pct_change(fill_method=None)
    panel["ret_5d"] = grouped["close"].pct_change(5, fill_method=None)
    panel["ret_20d"] = grouped["close"].pct_change(20, fill_method=None)
    panel["volatility_20d"] = grouped["ret_1d"].transform(lambda x: x.rolling(20, min_periods=10).std())
    return panel


def save_crypto_panel(panel: pd.DataFrame, output_path: Path | None = None) -> Path:
    ensure_crypto_dirs()
    target = output_path or DEFAULT_OUTPUT
    target.parent.mkdir(parents=True, exist_ok=True)
    panel.to_parquet(target, index=False)
    return target
