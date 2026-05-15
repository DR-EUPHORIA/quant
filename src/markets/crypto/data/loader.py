from __future__ import annotations

import pandas as pd


STANDARD_COLUMNS = [
    "ts_code",
    "trade_date",
    "open",
    "high",
    "low",
    "close",
    "volume",
    "source",
    "bar",
]


def normalize_crypto_ohlcv(df: pd.DataFrame, symbol: str | None = None, bar: str | None = None) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(columns=STANDARD_COLUMNS)

    out = df.copy()
    rename_map = {
        "symbol": "ts_code",
        "ticker": "ts_code",
        "inst_id": "ts_code",
        "timestamp": "trade_date",
        "Datetime": "trade_date",
        "Date": "trade_date",
        "interval": "bar",
    }
    out = out.rename(columns=rename_map)

    if "ts" in out.columns and "trade_date" not in out.columns:
        out = out.rename(columns={"ts": "trade_date"})

    if "ts_code" not in out.columns:
        out["ts_code"] = symbol if symbol is not None else "UNKNOWN"
    if "bar" not in out.columns:
        out["bar"] = bar if bar is not None else "1D"
    if "source" not in out.columns:
        out["source"] = "unknown"

    out["trade_date"] = pd.to_datetime(out["trade_date"])

    numeric_cols = ["open", "high", "low", "close", "volume"]
    for col in numeric_cols:
        if col not in out.columns:
            out[col] = pd.NA
        out[col] = pd.to_numeric(out[col], errors="coerce")

    keep_cols = [col for col in STANDARD_COLUMNS if col in out.columns]
    out = out[keep_cols].dropna(subset=["ts_code", "trade_date", "close"])
    out = out.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    return out
