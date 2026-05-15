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


def fetch_codes_from_universe(universe_path: Path | None = None) -> list[str]:
    universe_path = universe_path or (RAW_DIR / "hs300_constituents_latest.parquet")
    if not universe_path.exists():
        raise FileNotFoundError(f"universe file not found: {universe_path}")
    universe = pd.read_parquet(universe_path)
    codes = sorted(universe["con_code"].dropna().astype(str).unique().tolist())
    if not codes:
        raise RuntimeError(f"universe file is empty: {universe_path}")
    return codes


def fetch_by_trade_dates(
    pro,
    api_func: Callable[..., pd.DataFrame],
    trade_dates: list[str],
    output_path: Path,
    key_cols: list[str],
    fields: list[str] | None = None,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
    save_every: int = 50,
) -> pd.DataFrame:
    existing = load_existing(output_path, force_refresh=force_refresh)
    existing_dates = set()
    if not existing.empty and "trade_date" in existing.columns:
        existing_dates = set(existing["trade_date"].astype(str).unique().tolist())

    missing_dates = [trade_date for trade_date in trade_dates if trade_date not in existing_dates]
    frames = [existing] if not existing.empty else []
    fetched = 0

    for idx, trade_date in enumerate(missing_dates, start=1):
        kwargs: dict[str, Any] = {"trade_date": trade_date}
        if fields is not None:
            kwargs["fields"] = fields
        df = call_with_retry(api_func, sleep_seconds=sleep_seconds, **kwargs)
        if df is None or df.empty:
            time.sleep(sleep_seconds)
            continue

        frames.append(df)
        fetched += 1

        if fetched % save_every == 0:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_deduped(merged, output_path, key_cols)
            frames = [merged]

        time.sleep(sleep_seconds)

    merged = pd.concat(frames, ignore_index=True) if frames else existing
    merged = save_deduped(merged, output_path, key_cols)
    if merged.empty:
        raise RuntimeError(f"fetch result is empty: {output_path.name}")
    return merged


def fetch_by_codes(
    pro,
    api_func: Callable[..., pd.DataFrame],
    codes: list[str],
    output_path: Path,
    key_cols: list[str],
    start_date: str,
    end_date: str,
    fields: list[str] | None = None,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
    save_every: int = 50,
) -> pd.DataFrame:
    existing = load_existing(output_path, force_refresh=force_refresh)
    existing_codes = set()
    if not existing.empty and "ts_code" in existing.columns:
        existing_codes = set(existing["ts_code"].astype(str).unique().tolist())

    missing_codes = [code for code in codes if code not in existing_codes]
    frames = [existing] if not existing.empty else []
    fetched = 0

    for code in missing_codes:
        kwargs: dict[str, Any] = {"ts_code": code, "start_date": start_date, "end_date": end_date}
        if fields is not None:
            kwargs["fields"] = fields
        df = call_with_retry(api_func, sleep_seconds=sleep_seconds, **kwargs)
        if df is None or df.empty:
            time.sleep(sleep_seconds)
            continue

        frames.append(df)
        fetched += 1
        if fetched % save_every == 0:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_deduped(merged, output_path, key_cols)
            frames = [merged]

        time.sleep(sleep_seconds)

    merged = pd.concat(frames, ignore_index=True) if frames else existing
    merged = save_deduped(merged, output_path, key_cols)
    if merged.empty:
        raise RuntimeError(f"fetch result is empty: {output_path.name}")
    return merged


def fetch_daily_all(
    pro,
    trade_dates: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    output_path = RAW_DIR / f"daily_{start_date}_{end_date}.parquet"
    return fetch_by_trade_dates(
        pro=pro,
        api_func=pro.daily,
        trade_dates=trade_dates,
        output_path=output_path,
        key_cols=["ts_code", "trade_date"],
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
    )


def fetch_daily_basic_all(
    pro,
    trade_dates: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    output_path = RAW_DIR / f"daily_basic_{start_date}_{end_date}.parquet"
    return fetch_by_trade_dates(
        pro=pro,
        api_func=pro.daily_basic,
        trade_dates=trade_dates,
        output_path=output_path,
        key_cols=["ts_code", "trade_date"],
        fields=[
            "ts_code",
            "trade_date",
            "turnover_rate",
            "turnover_rate_f",
            "pe",
            "pe_ttm",
            "pb",
            "ps",
            "ps_ttm",
            "total_share",
            "float_share",
            "free_share",
            "total_mv",
            "circ_mv",
        ],
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
    )


def fetch_adj_factor_all(
    pro,
    codes: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    output_path = RAW_DIR / f"adj_factor_hs300_{start_date}_{end_date}.parquet"
    return fetch_by_codes(
        pro=pro,
        api_func=pro.adj_factor,
        codes=codes,
        output_path=output_path,
        key_cols=["ts_code", "trade_date"],
        start_date=start_date,
        end_date=end_date,
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
    )


def fetch_stk_limit(
    pro,
    codes: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    output_path = RAW_DIR / f"stk_limit_hs300_{start_date}_{end_date}.parquet"
    return fetch_by_codes(
        pro=pro,
        api_func=pro.stk_limit,
        codes=codes,
        output_path=output_path,
        key_cols=["ts_code", "trade_date"],
        start_date=start_date,
        end_date=end_date,
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
    )


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


def fetch_suspend_d(
    pro,
    codes: list[str],
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    path = RAW_DIR / f"suspend_d_hs300_{start_date}_{end_date}.parquet"
    existing = load_existing(path, force_refresh=force_refresh)
    existing_codes = set(existing["ts_code"].astype(str).unique().tolist()) if not existing.empty and "ts_code" in existing.columns else set()
    missing_codes = [code for code in codes if code not in existing_codes]
    frames = [existing] if not existing.empty else []

    for idx, code in enumerate(missing_codes, start=1):
        df = call_with_retry(
            pro.suspend_d,
            sleep_seconds=sleep_seconds,
            ts_code=code,
            start_date=start_date,
            end_date=end_date,
        )
        if df is not None and not df.empty:
            frames.append(df)
        if idx % 50 == 0 and frames:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_deduped(merged, path, ["ts_code", "trade_date", "suspend_type", "suspend_timing"])
            frames = [merged]
        time.sleep(sleep_seconds)

    merged = pd.concat(frames, ignore_index=True) if frames else existing
    if merged.empty:
        merged = pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"])
    return save_deduped(merged, path, ["ts_code", "trade_date", "suspend_type", "suspend_timing"])


def fetch_stock_st(
    pro,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    effective_start = max(start_date, "20160101")
    path = RAW_DIR / f"stock_st_{effective_start}_{end_date}.parquet"
    existing = load_existing(path, force_refresh=force_refresh)
    existing_months = set()
    if not existing.empty and "trade_date" in existing.columns:
        existing_months = set(pd.to_datetime(existing["trade_date"].astype(str)).dt.strftime("%Y%m").unique().tolist())

    frames = [existing] if not existing.empty else []
    missing_windows = [(win_start, win_end) for win_start, win_end in month_windows(effective_start, end_date) if win_start[:6] not in existing_months]

    for idx, (win_start, win_end) in enumerate(missing_windows, start=1):
        try:
            df = call_with_retry(
                pro.stock_st,
                sleep_seconds=sleep_seconds,
                start_date=win_start,
                end_date=win_end,
            )
        except Exception as exc:
            if "没有接口访问权限" in str(exc):
                merged = existing if not existing.empty else pd.DataFrame(
                    columns=["ts_code", "name", "trade_date", "type", "type_name"]
                )
                merged.to_parquet(path, index=False)
                return merged
            raise

        if df is not None and not df.empty:
            frames.append(df)
        if idx % 24 == 0 and frames:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_deduped(merged, path, ["ts_code", "trade_date", "type"])
            frames = [merged]
        time.sleep(sleep_seconds)

    merged = pd.concat(frames, ignore_index=True) if frames else existing
    if merged.empty:
        merged = pd.DataFrame(columns=["ts_code", "name", "trade_date", "type", "type_name"])
    return save_deduped(merged, path, ["ts_code", "trade_date", "type"])


def fetch_stock_basic(
    pro,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    path = RAW_DIR / "stock_basic_all_status.parquet"
    if path.exists() and not force_refresh:
        return pd.read_parquet(path)

    frames = []
    for status in ["L", "D", "P"]:
        df = call_with_retry(
            pro.stock_basic,
            sleep_seconds=0.2,
            exchange="",
            list_status=status,
            fields="ts_code,symbol,name,area,industry,market,list_status,list_date,delist_date,is_hs",
        )
        if df is not None and not df.empty:
            frames.append(df)

    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    return save_deduped(merged, path, ["ts_code", "list_status"])


def fetch_index_daily(
    pro,
    index_code: str = INDEX_CODE,
    start_date: str = START_DATE,
    end_date: str = END_DATE,
    force_refresh: bool = False,
) -> pd.DataFrame:
    ensure_a_stock_dirs()
    path = RAW_DIR / f"index_daily_{index_code.replace('.', '_')}_{start_date}_{end_date}.parquet"
    if path.exists() and not force_refresh:
        return pd.read_parquet(path)
    df = call_with_retry(
        pro.index_daily,
        sleep_seconds=0.2,
        ts_code=index_code,
        start_date=start_date,
        end_date=end_date,
    )
    if df is None or df.empty:
        raise RuntimeError(f"index_daily result is empty: {index_code}")
    return save_deduped(df, path, ["ts_code", "trade_date"])
