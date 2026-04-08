from __future__ import annotations

import calendar
import os
import time
from pathlib import Path
from typing import Any, Callable

import pandas as pd

from ..paths import RAW_DIR, ensure_a_stock_dirs


START_DATE = "20150101"
END_DATE = "20241231"
INDEX_CODE = "000300.SH"
EXCHANGE = "SSE"


def init_tushare_client():
    token = os.getenv("TUSHARE_TOKEN", "")
    if not token:
        try:
            from config.config_tushare import TUSHARE_TOKEN  # type: ignore
        except ImportError as exc:
            raise RuntimeError("missing TUSHARE_TOKEN in env or config/config_tushare.py") from exc
        token = TUSHARE_TOKEN
    if not token:
        raise RuntimeError("missing TUSHARE_TOKEN in env or config/config_tushare.py")

    try:
        import tushare as ts
    except ImportError as exc:
        raise RuntimeError("tushare is not installed") from exc

    ts.set_token(token)
    return ts.pro_api()


def call_with_retry(api_func: Callable[..., pd.DataFrame], sleep_seconds: float, max_retries: int = 4, **kwargs: Any) -> pd.DataFrame:
    for attempt in range(max_retries):
        try:
            return api_func(**kwargs)
        except Exception as exc:
            message = str(exc)
            if "每分钟最多访问该接口" in message and attempt < max_retries - 1:
                wait_seconds = max(65.0, sleep_seconds * 5)
                time.sleep(wait_seconds)
                continue
            raise
    return pd.DataFrame()


def load_existing(path: Path, force_refresh: bool) -> pd.DataFrame:
    if force_refresh or not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def save_deduped(df: pd.DataFrame, path: Path, key_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.drop_duplicates(subset=key_cols, keep="last").sort_values(key_cols).reset_index(drop=True)
    path.parent.mkdir(parents=True, exist_ok=True)
    out.to_parquet(path, index=False)
    return out


def month_windows(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start = pd.to_datetime(start_date, format="%Y%m%d")
    end = pd.to_datetime(end_date, format="%Y%m%d")
    current = pd.Timestamp(year=start.year, month=start.month, day=1)
    windows: list[tuple[str, str]] = []
    while current <= end:
        last_day = calendar.monthrange(current.year, current.month)[1]
        month_end = pd.Timestamp(year=current.year, month=current.month, day=last_day)
        win_start = max(current, start)
        win_end = min(month_end, end)
        windows.append((win_start.strftime("%Y%m%d"), win_end.strftime("%Y%m%d")))
        current = (
            pd.Timestamp(year=current.year + 1, month=1, day=1)
            if current.month == 12
            else pd.Timestamp(year=current.year, month=current.month + 1, day=1)
        )
    return windows


def fetch_trade_dates(pro, start_date: str = START_DATE, end_date: str = END_DATE, exchange: str = EXCHANGE) -> list[str]:
    cal = pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date)
    cal = cal.loc[cal["is_open"] == 1].copy()
    if cal.empty:
        raise RuntimeError(f"failed to fetch trade calendar: {exchange} {start_date}-{end_date}")
    return sorted(cal["cal_date"].astype(str).tolist())


def fetch_latest_hs300_universe(pro, end_date: str = END_DATE, output_path: Path | None = None) -> pd.DataFrame:
    ensure_a_stock_dirs()
    output_path = output_path or (RAW_DIR / "hs300_constituents_latest.parquet")
    weights = pro.index_weight(index_code=INDEX_CODE, trade_date=end_date)
    weights = weights.drop_duplicates(subset=["con_code"]).reset_index(drop=True)
    weights.to_parquet(output_path, index=False)
    return weights


def fetch_index_weight(
    pro,
    index_code: str = INDEX_CODE,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    path = RAW_DIR / f"{index_code.lower().replace('.', '_')}_index_weight_{start_date}_{end_date}.parquet"
    existing = load_existing(path, force_refresh=force_refresh)
    existing_months = set()
    if not existing.empty and "trade_date" in existing.columns:
        existing_months = set(pd.to_datetime(existing["trade_date"].astype(str)).dt.strftime("%Y%m").unique().tolist())

    frames = [existing] if not existing.empty else []
    windows = month_windows(start_date, end_date)
    for win_start, win_end in windows:
        if win_start[:6] in existing_months:
            continue
        df = call_with_retry(
            pro.index_weight,
            sleep_seconds=sleep_seconds,
            index_code=index_code,
            start_date=win_start,
            end_date=win_end,
        )
        if df is not None and not df.empty:
            frames.append(df)
        time.sleep(sleep_seconds)
    merged = pd.concat(frames, ignore_index=True) if frames else existing
    return save_deduped(merged, path, ["index_code", "con_code", "trade_date"])
