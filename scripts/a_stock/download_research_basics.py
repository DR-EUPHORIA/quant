import argparse
import calendar
import os
import sys
import time
from pathlib import Path

import pandas as pd
import tushare as ts


ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

from scripts.a_stock.build_panel import build_panel, resolve_output_path  # noqa: E402


DATA_ROOT = ROOT / "data" / "tushare"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"

INDEX_CODE = "000300.SH"
START_DATE = "20150101"
END_DATE = "20241231"

STK_LIMIT_PATH = RAW_DIR / f"stk_limit_hs300_{START_DATE}_{END_DATE}.parquet"
INDEX_WEIGHT_PATH = RAW_DIR / f"hs300_index_weight_{START_DATE}_{END_DATE}.parquet"
SUSPEND_PATH = RAW_DIR / f"suspend_d_hs300_{START_DATE}_{END_DATE}.parquet"
ST_PATH = RAW_DIR / f"stock_st_{max(START_DATE, '20160101')}_{END_DATE}.parquet"
STOCK_BASIC_PATH = RAW_DIR / "stock_basic_all_status.parquet"
INDEX_DAILY_PATH = RAW_DIR / f"index_daily_{INDEX_CODE.replace('.', '_')}_{START_DATE}_{END_DATE}.parquet"
FULL_PANEL_PATH = PROCESSED_DIR / f"hs300_panel_{START_DATE}_{END_DATE}_full.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="补齐量化研究基础数据并重建完整复权面板")
    parser.add_argument("--start-date", default=START_DATE, help="起始日期 YYYYMMDD")
    parser.add_argument("--end-date", default=END_DATE, help="结束日期 YYYYMMDD")
    parser.add_argument("--index-code", default=INDEX_CODE, help="基准指数代码，默认沪深300")
    parser.add_argument("--sleep-seconds", type=float, default=0.12, help="接口调用间隔")
    parser.add_argument("--force-refresh", action="store_true", help="忽略已有缓存并重新拉取")
    return parser.parse_args()


def init_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def init_tushare():
    token = os.getenv("TUSHARE_TOKEN", "")
    if not token:
        from config.config_tushare import TUSHARE_TOKEN

        token = TUSHARE_TOKEN
    if not token:
        raise RuntimeError("Missing TUSHARE_TOKEN")
    return ts.pro_api(token)


def call_with_retry(api_func, sleep_seconds: float, max_retries: int = 4, **kwargs) -> pd.DataFrame:
    for attempt in range(max_retries):
        try:
            return api_func(**kwargs)
        except Exception as exc:
            msg = str(exc)
            if "每分钟最多访问该接口" in msg and attempt < max_retries - 1:
                wait_seconds = max(65.0, sleep_seconds * 5)
                print(f"触发频控，等待 {wait_seconds:.0f} 秒后重试...")
                time.sleep(wait_seconds)
                continue
            raise
    return pd.DataFrame()


def load_existing(path: Path, force_refresh: bool) -> pd.DataFrame:
    if force_refresh or not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    print(f"发现已有缓存: {path.name}, 行数={len(df)}")
    return df


def save_deduped(df: pd.DataFrame, path: Path, key_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.drop_duplicates(subset=key_cols, keep="last").sort_values(key_cols).reset_index(drop=True)
    out.to_parquet(path, index=False)
    return out


def month_windows(start_date: str, end_date: str) -> list[tuple[str, str]]:
    start = pd.to_datetime(start_date, format="%Y%m%d")
    end = pd.to_datetime(end_date, format="%Y%m%d")
    cur = pd.Timestamp(year=start.year, month=start.month, day=1)
    windows: list[tuple[str, str]] = []
    while cur <= end:
        last_day = calendar.monthrange(cur.year, cur.month)[1]
        month_end = pd.Timestamp(year=cur.year, month=cur.month, day=last_day)
        win_start = max(cur, start)
        win_end = min(month_end, end)
        windows.append((win_start.strftime("%Y%m%d"), win_end.strftime("%Y%m%d")))
        if cur.month == 12:
            cur = pd.Timestamp(year=cur.year + 1, month=1, day=1)
        else:
            cur = pd.Timestamp(year=cur.year, month=cur.month + 1, day=1)
    return windows


def fetch_trade_dates(pro, start_date: str, end_date: str, exchange: str = "SSE") -> list[str]:
    cal = pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date)
    cal = cal[cal["is_open"] == 1].copy()
    if cal.empty:
        raise RuntimeError(f"未获取到交易日历: {start_date}-{end_date}")
    return sorted(cal["cal_date"].astype(str).tolist())


def fetch_hs300_codes_from_latest_universe() -> list[str]:
    universe_path = RAW_DIR / "hs300_constituents_latest.parquet"
    if not universe_path.exists():
        raise FileNotFoundError(f"缺少股票池文件: {universe_path}")
    uni = pd.read_parquet(universe_path)
    codes = sorted(uni["con_code"].dropna().astype(str).unique().tolist())
    if not codes:
        raise RuntimeError("hs300_constituents_latest.parquet 为空")
    return codes


def fetch_stk_limit(pro, codes: list[str], start_date: str, end_date: str, sleep_seconds: float, force_refresh: bool) -> pd.DataFrame:
    path = RAW_DIR / f"stk_limit_hs300_{start_date}_{end_date}.parquet"
    existing = load_existing(path, force_refresh=force_refresh)
    existing_codes = set(existing["ts_code"].astype(str).unique().tolist()) if not existing.empty and "ts_code" in existing.columns else set()
    missing_codes = [code for code in codes if code not in existing_codes]
    print(f"stk_limit: 已有 {len(existing_codes)} 只股票，待拉取 {len(missing_codes)} 只股票")
    frames = [existing] if not existing.empty else []
    for idx, code in enumerate(missing_codes, start=1):
        df = call_with_retry(
            pro.stk_limit,
            sleep_seconds=sleep_seconds,
            ts_code=code,
            start_date=start_date,
            end_date=end_date,
        )
        if df is not None and not df.empty:
            frames.append(df)
        if idx % 20 == 0 or idx == len(missing_codes):
            print(f"stk_limit: {idx}/{len(missing_codes)}")
        if idx % 50 == 0 and frames:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_deduped(merged, path, ["ts_code", "trade_date"])
            frames = [merged]
        time.sleep(sleep_seconds)
    merged = pd.concat(frames, ignore_index=True) if frames else existing
    merged = save_deduped(merged, path, ["ts_code", "trade_date"])
    return merged


def fetch_index_weight(pro, index_code: str, start_date: str, end_date: str, sleep_seconds: float, force_refresh: bool) -> pd.DataFrame:
    path = RAW_DIR / f"{index_code.lower().replace('.', '_')}_index_weight_{start_date}_{end_date}.parquet"
    existing = load_existing(path, force_refresh=force_refresh)
    existing_months = set()
    if not existing.empty and "trade_date" in existing.columns:
        existing_months = set(pd.to_datetime(existing["trade_date"].astype(str)).dt.strftime("%Y%m").unique().tolist())

    frames = [existing] if not existing.empty else []
    windows = month_windows(start_date, end_date)
    for idx, (win_start, win_end) in enumerate(windows, start=1):
        month_key = win_start[:6]
        if month_key in existing_months:
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
        if idx % 12 == 0 or idx == len(windows):
            print(f"index_weight: {idx}/{len(windows)} 月窗口")
        time.sleep(sleep_seconds)
    merged = pd.concat(frames, ignore_index=True) if frames else existing
    merged = save_deduped(merged, path, ["index_code", "con_code", "trade_date"])
    return merged


def fetch_suspend_d(pro, codes: list[str], start_date: str, end_date: str, sleep_seconds: float, force_refresh: bool) -> pd.DataFrame:
    path = RAW_DIR / f"suspend_d_hs300_{start_date}_{end_date}.parquet"
    existing = load_existing(path, force_refresh=force_refresh)
    existing_codes = set(existing["ts_code"].astype(str).unique().tolist()) if not existing.empty and "ts_code" in existing.columns else set()
    missing_codes = [code for code in codes if code not in existing_codes]
    print(f"suspend_d: 已有 {len(existing_codes)} 只股票，待拉取 {len(missing_codes)} 只股票")
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
        if idx % 20 == 0 or idx == len(missing_codes):
            print(f"suspend_d: {idx}/{len(missing_codes)}")
        if idx % 50 == 0 and frames:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_deduped(merged, path, ["ts_code", "trade_date", "suspend_type", "suspend_timing"])
            frames = [merged]
        time.sleep(sleep_seconds)
    merged = pd.concat(frames, ignore_index=True) if frames else existing
    if merged.empty:
        merged = pd.DataFrame(columns=["ts_code", "trade_date", "suspend_timing", "suspend_type"])
    merged = save_deduped(merged, path, ["ts_code", "trade_date", "suspend_type", "suspend_timing"])
    return merged


def fetch_stock_st(pro, start_date: str, end_date: str, sleep_seconds: float, force_refresh: bool) -> pd.DataFrame:
    effective_start = max(start_date, "20160101")
    path = RAW_DIR / f"stock_st_{effective_start}_{end_date}.parquet"
    existing = load_existing(path, force_refresh=force_refresh)
    existing_months = set()
    if not existing.empty and "trade_date" in existing.columns:
        existing_months = set(pd.to_datetime(existing["trade_date"].astype(str)).dt.strftime("%Y%m").unique().tolist())
    windows = month_windows(effective_start, end_date)
    missing_windows = [(s, e) for s, e in windows if s[:6] not in existing_months]
    print(f"stock_st: 已有 {len(existing_months)} 个月份窗口，待拉取 {len(missing_windows)} 个月份窗口")
    frames = [existing] if not existing.empty else []
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
                print("stock_st: 当前 TuShare 账号无权限，跳过 ST 股票列表下载")
                merged = existing if not existing.empty else pd.DataFrame(
                    columns=["ts_code", "name", "trade_date", "type", "type_name"]
                )
                merged.to_parquet(path, index=False)
                return merged
            raise
        if df is not None and not df.empty:
            frames.append(df)
        if idx % 12 == 0 or idx == len(missing_windows):
            print(f"stock_st: {idx}/{len(missing_windows)}")
        if idx % 24 == 0 and frames:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_deduped(merged, path, ["ts_code", "trade_date", "type"])
            frames = [merged]
        time.sleep(sleep_seconds)
    merged = pd.concat(frames, ignore_index=True) if frames else existing
    if merged.empty:
        merged = pd.DataFrame(columns=["ts_code", "name", "trade_date", "type", "type_name"])
    merged = save_deduped(merged, path, ["ts_code", "trade_date", "type"])
    return merged


def fetch_stock_basic(pro, force_refresh: bool) -> pd.DataFrame:
    path = STOCK_BASIC_PATH
    if path.exists() and not force_refresh:
        df = pd.read_parquet(path)
        print(f"发现已有缓存: {path.name}, 行数={len(df)}")
        return df

    frames = []
    for status in ["L", "D", "P"]:
        df = call_with_retry(
            pro.stock_basic,
            sleep_seconds=0.2,
            exchange="",
            list_status=status,
            fields="ts_code,symbol,name,area,industry,market,list_status,list_date,delist_date,is_hs"
        )
        if df is not None and not df.empty:
            frames.append(df)
    merged = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    merged = save_deduped(merged, path, ["ts_code", "list_status"])
    return merged


def fetch_index_daily(pro, index_code: str, start_date: str, end_date: str, force_refresh: bool) -> pd.DataFrame:
    path = RAW_DIR / f"index_daily_{index_code.replace('.', '_')}_{start_date}_{end_date}.parquet"
    if path.exists() and not force_refresh:
        df = pd.read_parquet(path)
        print(f"发现已有缓存: {path.name}, 行数={len(df)}")
        return df
    df = call_with_retry(
        pro.index_daily,
        sleep_seconds=0.2,
        ts_code=index_code,
        start_date=start_date,
        end_date=end_date,
    )
    if df is None or df.empty:
        raise RuntimeError(f"index_daily 结果为空: {index_code}")
    df = save_deduped(df, path, ["ts_code", "trade_date"])
    return df


def rebuild_full_panel(start_date: str, end_date: str) -> Path:
    daily_path = RAW_DIR / f"daily_{start_date}_{end_date}.parquet"
    basic_path = RAW_DIR / f"daily_basic_{start_date}_{end_date}.parquet"
    universe_path = RAW_DIR / f"{INDEX_CODE.lower().replace('.', '_')}_index_weight_{start_date}_{end_date}.parquet"
    adj_path = RAW_DIR / f"adj_factor_hs300_{start_date}_{end_date}.parquet"
    limit_path = RAW_DIR / f"stk_limit_hs300_{start_date}_{end_date}.parquet"
    suspend_path = RAW_DIR / f"suspend_d_hs300_{start_date}_{end_date}.parquet"
    stock_st_path = RAW_DIR / f"stock_st_{max(start_date, '20160101')}_{end_date}.parquet"
    stock_basic_path = STOCK_BASIC_PATH
    desired_output = PROCESSED_DIR / f"hs300_panel_{start_date}_{end_date}_full.parquet"
    output_path = resolve_output_path(desired_output)

    daily = pd.read_parquet(daily_path)
    basic = pd.read_parquet(basic_path)
    universe = pd.read_parquet(universe_path)
    adj_factor = pd.read_parquet(adj_path) if adj_path.exists() else pd.DataFrame()
    stk_limit = pd.read_parquet(limit_path) if limit_path.exists() else pd.DataFrame()
    suspend_d = pd.read_parquet(suspend_path) if suspend_path.exists() else pd.DataFrame()
    stock_st = pd.read_parquet(stock_st_path) if stock_st_path.exists() else pd.DataFrame()
    stock_basic = pd.read_parquet(stock_basic_path) if stock_basic_path.exists() else pd.DataFrame()

    panel = build_panel(
        daily,
        basic,
        universe,
        adj_factor=adj_factor,
        stk_limit=stk_limit,
        suspend_d=suspend_d,
        stock_basic=stock_basic,
        stock_st=stock_st,
    )
    panel.to_parquet(output_path, index=False)
    return output_path


def print_dataset_status(name: str, df: pd.DataFrame, path: Path) -> None:
    print(f"{name}: rows={len(df):,}, cols={len(df.columns)}, path={path}")


def main() -> None:
    args = parse_args()
    init_dirs()
    pro = init_tushare()

    codes = fetch_hs300_codes_from_latest_universe()

    stk_limit = fetch_stk_limit(
        pro,
        codes=codes,
        start_date=args.start_date,
        end_date=args.end_date,
        sleep_seconds=args.sleep_seconds,
        force_refresh=args.force_refresh,
    )
    index_weight = fetch_index_weight(
        pro,
        index_code=args.index_code,
        start_date=args.start_date,
        end_date=args.end_date,
        sleep_seconds=args.sleep_seconds,
        force_refresh=args.force_refresh,
    )
    suspend_d = fetch_suspend_d(
        pro,
        codes=codes,
        start_date=args.start_date,
        end_date=args.end_date,
        sleep_seconds=args.sleep_seconds,
        force_refresh=args.force_refresh,
    )
    stock_st = fetch_stock_st(
        pro,
        start_date=args.start_date,
        end_date=args.end_date,
        sleep_seconds=args.sleep_seconds,
        force_refresh=args.force_refresh,
    )
    stock_basic = fetch_stock_basic(pro, force_refresh=args.force_refresh)
    index_daily = fetch_index_daily(
        pro,
        index_code=args.index_code,
        start_date=args.start_date,
        end_date=args.end_date,
        force_refresh=args.force_refresh,
    )
    full_panel_path = rebuild_full_panel(args.start_date, args.end_date)

    print_dataset_status("stk_limit", stk_limit, RAW_DIR / f"stk_limit_hs300_{args.start_date}_{args.end_date}.parquet")
    print_dataset_status("index_weight", index_weight, RAW_DIR / f"{args.index_code.lower().replace('.', '_')}_index_weight_{args.start_date}_{args.end_date}.parquet")
    print_dataset_status("suspend_d", suspend_d, RAW_DIR / f"suspend_d_hs300_{args.start_date}_{args.end_date}.parquet")
    print_dataset_status("stock_st", stock_st, RAW_DIR / f"stock_st_{max(args.start_date, '20160101')}_{args.end_date}.parquet")
    print_dataset_status("stock_basic", stock_basic, STOCK_BASIC_PATH)
    print_dataset_status("index_daily", index_daily, RAW_DIR / f"index_daily_{args.index_code.replace('.', '_')}_{args.start_date}_{args.end_date}.parquet")
    print(f"full_panel: path={full_panel_path}")


if __name__ == "__main__":
    main()
