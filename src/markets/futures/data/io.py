from __future__ import annotations

from pathlib import Path

import pandas as pd


REQUIRED_HOTS_COLUMNS = [
    "symbol",
    "order_id",
    "contract_multiplier",
    "hot_start_date",
    "hot_end_date",
    "commission_type",
    "open_commission",
    "close_commission",
]

REQUIRED_KLINE_COLUMNS = ["open", "high", "low", "close"]


def parse_date_series(series: pd.Series) -> pd.Series:
    return pd.to_datetime(series, errors="coerce").dt.normalize()


def find_contract_file(kline_root: Path, symbol: str, contract: str) -> Path:
    candidates = [
        kline_root / symbol / f"{contract}.csv",
        kline_root / f"{contract}.csv",
        kline_root / symbol.lower() / f"{contract}.csv",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"contract file not found for {symbol} {contract} under {kline_root}")


def read_contract_csv(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)

    if "trade_date" not in df.columns:
        if "date" in df.columns:
            df = df.rename(columns={"date": "trade_date"})
        else:
            raise ValueError(f"missing trade_date/date column in {path}")

    missing = [col for col in REQUIRED_KLINE_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"missing columns {missing} in {path}")

    df["trade_date"] = parse_date_series(df["trade_date"])
    df = df.dropna(subset=["trade_date"]).sort_values("trade_date").reset_index(drop=True)
    return df


def load_hots_table(hots_path: Path) -> pd.DataFrame:
    suffix = hots_path.suffix.lower()
    if suffix == ".csv":
        hots = pd.read_csv(hots_path)
    elif suffix == ".parquet":
        hots = pd.read_parquet(hots_path)
    else:
        hots = pd.read_excel(hots_path)

    missing = [col for col in REQUIRED_HOTS_COLUMNS if col not in hots.columns]
    if missing:
        raise ValueError(f"hots table missing columns: {missing}")

    hots = hots.copy()
    hots["symbol"] = hots["symbol"].astype(str).str.upper()
    hots["order_id"] = hots["order_id"].astype(str)
    hots["hot_start_date"] = parse_date_series(hots["hot_start_date"])
    hots["hot_end_date"] = parse_date_series(hots["hot_end_date"])
    hots = hots.dropna(subset=["hot_start_date", "hot_end_date"])
    hots = hots.sort_values(["symbol", "hot_start_date", "hot_end_date"]).reset_index(drop=True)
    return hots
