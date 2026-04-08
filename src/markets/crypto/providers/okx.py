from pathlib import Path
from typing import Optional

import pandas as pd
import requests

from ..paths import CRYPTO_RAW_DIR, ensure_crypto_dirs


BASE_URL = "https://www.okx.com"


def fetch_okx_candles(
    inst_id: str = "BTC-USDT",
    bar: str = "1D",
    limit: int = 200,
    timeout: int = 20,
) -> pd.DataFrame:
    """
    Fetch OHLCV candles from the OKX REST API.
    """
    url = f"{BASE_URL}/api/v5/market/candles"
    params = {"instId": inst_id, "bar": bar, "limit": str(limit)}
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()

    raw = resp.json()
    if "data" not in raw:
        raise ValueError(f"OKX response missing data field: {raw}")

    df = pd.DataFrame(
        raw["data"],
        columns=[
            "ts",
            "open",
            "high",
            "low",
            "close",
            "volume",
            "vol_ccy",
            "vol_ccy_quote",
            "confirm",
        ],
    )
    if df.empty:
        return df

    df["ts"] = pd.to_datetime(df["ts"].astype("int64"), unit="ms")
    df = df.sort_values("ts").reset_index(drop=True)
    for col in ["open", "high", "low", "close", "volume", "vol_ccy", "vol_ccy_quote"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["source"] = "okx_rest"
    df["symbol"] = inst_id
    df["bar"] = bar
    return df


def save_okx_candles_csv(
    df: pd.DataFrame,
    inst_id: str,
    bar: str,
    output_path: Optional[Path] = None,
) -> Path:
    ensure_crypto_dirs()
    filename = f"okx_{inst_id.lower().replace('-', '_')}_{bar.lower()}.csv"
    target = output_path or (CRYPTO_RAW_DIR / filename)
    target.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(target, index=False, encoding="utf-8-sig")
    return target
