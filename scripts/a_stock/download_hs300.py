import os
import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT), str(ROOT / "src")])

import argparse
import time

import pandas as pd
import tushare as ts
from quanta_stock import DATA_ROOT, PROCESSED_DIR, RAW_DIR

START_DATE = "20150101"
END_DATE = "20241231"
INDEX_CODE = "000300.SH"  # 沪深300
EXCHANGE = "SSE"


def init_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def init_tushare():
    token = os.getenv("TUSHARE_TOKEN", "")
    if not token:
        try:
            from config.config_tushare import TUSHARE_TOKEN
        except ImportError as exc:
            raise RuntimeError("缺少 TUSHARE_TOKEN，请在 .env 环境变量或 config/config_tushare.py 中提供") from exc
        token = TUSHARE_TOKEN
    if not token:
        raise RuntimeError("缺少 TUSHARE_TOKEN，请在 .env 环境变量或 config/config_tushare.py 中提供")
    ts.set_token(token)
    pro = ts.pro_api()
    return pro


def parse_args():
    parser = argparse.ArgumentParser(description="按交易日拉取 HS300 研究数据")
    parser.add_argument("--start-date", default=START_DATE, help="起始日期，YYYYMMDD")
    parser.add_argument("--end-date", default=END_DATE, help="结束日期，YYYYMMDD")
    parser.add_argument("--exchange", default=EXCHANGE, help="交易所，默认 SSE")
    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.12,
        help="每次接口调用后的休眠秒数",
    )
    parser.add_argument(
        "--force-refresh",
        action="store_true",
        help="忽略已有缓存，重新拉取",
    )
    parser.add_argument("--with-adj-factor", action="store_true", default=True)
    parser.add_argument("--with-stk-limit", action="store_true", default=True)
    return parser.parse_args()


def get_trade_dates(pro, start_date: str, end_date: str, exchange: str = EXCHANGE) -> list[str]:
    cal = pro.trade_cal(exchange=exchange, start_date=start_date, end_date=end_date)
    cal = cal[cal["is_open"] == 1].copy()
    if cal.empty:
        raise ValueError(f"未获取到交易日历: {exchange} {start_date}-{end_date}")
    trade_dates = sorted(cal["cal_date"].astype(str).tolist())
    print(f"交易日数量: {len(trade_dates)} ({trade_dates[0]} -> {trade_dates[-1]})")
    return trade_dates


def get_hs300_universe(pro, end_date: str) -> pd.DataFrame:
    """
    获取沪深300成分股列表（按某个截止日期，例如最新成分）。
    入门阶段，先用“固定成分”做股票池即可。
    """
    print("获取沪深300成分股列表...")
    # trade_date 可以填 END_DATE，也可以填最近交易日
    w = pro.index_weight(index_code=INDEX_CODE, trade_date=end_date)
    w = w.drop_duplicates(subset=["con_code"]).reset_index(drop=True)
    w.to_parquet(RAW_DIR / "hs300_constituents_latest.parquet", index=False)
    print(f"成分股数量: {len(w)}")
    return w


def load_existing(path: Path, force_refresh: bool) -> pd.DataFrame:
    if force_refresh or not path.exists():
        return pd.DataFrame()
    df = pd.read_parquet(path)
    print(f"发现已有缓存: {path.name}, 行数={len(df)}")
    return df


def save_incremental(df: pd.DataFrame, path: Path, key_cols: list[str]) -> pd.DataFrame:
    if df.empty:
        return df
    deduped = df.drop_duplicates(subset=key_cols, keep="last").sort_values(key_cols).reset_index(drop=True)
    deduped.to_parquet(path, index=False)
    return deduped


def fetch_by_trade_dates(
    pro,
    api_func,
    trade_dates: list[str],
    output_path: Path,
    key_cols: list[str],
    fields=None,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
    save_every: int = 50,
    api_name: str = "dataset",
) -> pd.DataFrame:
    existing = load_existing(output_path, force_refresh=force_refresh)
    existing_dates = set()
    if not existing.empty and "trade_date" in existing.columns:
        existing_dates = set(existing["trade_date"].astype(str).unique().tolist())

    missing_dates = [d for d in trade_dates if d not in existing_dates]
    print(f"{api_name}: 已有 {len(existing_dates)} 个交易日，待拉取 {len(missing_dates)} 个交易日")

    frames = [existing] if not existing.empty else []
    fetched = 0
    for idx, trade_date in enumerate(missing_dates, start=1):
        kwargs = {"trade_date": trade_date}
        if fields is not None:
            kwargs["fields"] = fields
        df = api_func(**kwargs)
        if df is None or df.empty:
            time.sleep(sleep_seconds)
            continue

        frames.append(df)
        fetched += 1

        if idx % 20 == 0 or idx == len(missing_dates):
            print(f"{api_name}: {idx}/{len(missing_dates)} 交易日已处理")

        if fetched % save_every == 0:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_incremental(merged, output_path, key_cols)
            frames = [merged]

        time.sleep(sleep_seconds)

    if frames:
        merged = pd.concat(frames, ignore_index=True)
        merged = save_incremental(merged, output_path, key_cols)
    else:
        merged = existing

    if merged.empty:
        raise RuntimeError(f"{api_name} 拉取结果为空")

    print(f"{api_name}: 最终行数 {len(merged)}, 交易日数 {merged['trade_date'].astype(str).nunique()}")
    return merged


def fetch_by_codes(
    api_func,
    codes: list[str],
    output_path: Path,
    key_cols: list[str],
    start_date: str,
    end_date: str,
    fields=None,
    sleep_seconds: float = 0.12,
    force_refresh: bool = False,
    save_every: int = 50,
    api_name: str = "dataset",
) -> pd.DataFrame:
    existing = load_existing(output_path, force_refresh=force_refresh)
    existing_codes = set()
    if not existing.empty and "ts_code" in existing.columns:
        existing_codes = set(existing["ts_code"].astype(str).unique().tolist())

    missing_codes = [code for code in codes if code not in existing_codes]
    print(f"{api_name}: 已有 {len(existing_codes)} 只股票，待拉取 {len(missing_codes)} 只股票")

    frames = [existing] if not existing.empty else []
    fetched = 0
    for idx, code in enumerate(missing_codes, start=1):
        kwargs = {"ts_code": code, "start_date": start_date, "end_date": end_date}
        if fields is not None:
            kwargs["fields"] = fields
        df = api_func(**kwargs)
        if df is None or df.empty:
            time.sleep(sleep_seconds)
            continue

        frames.append(df)
        fetched += 1
        if idx % 20 == 0 or idx == len(missing_codes):
            print(f"{api_name}: {idx}/{len(missing_codes)} 股票已处理")

        if fetched % save_every == 0:
            merged = pd.concat(frames, ignore_index=True)
            merged = save_incremental(merged, output_path, key_cols)
            frames = [merged]

        time.sleep(sleep_seconds)

    if frames:
        merged = pd.concat(frames, ignore_index=True)
        merged = save_incremental(merged, output_path, key_cols)
    else:
        merged = existing

    if merged.empty:
        raise RuntimeError(f"{api_name} 拉取结果为空")

    print(f"{api_name}: 最终行数 {len(merged)}")
    return merged


def get_daily_all(
    pro,
    trade_dates: list[str],
    start_date: str,
    end_date: str,
    sleep_seconds: float,
    force_refresh: bool,
) -> pd.DataFrame:
    daily_path = RAW_DIR / f"daily_{start_date}_{end_date}.parquet"
    print("按交易日拉取全市场日线行情...")
    return fetch_by_trade_dates(
        pro=pro,
        api_func=pro.daily,
        trade_dates=trade_dates,
        output_path=daily_path,
        key_cols=["ts_code", "trade_date"],
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
        api_name="daily",
    )


def get_daily_basic_all(
    pro,
    trade_dates: list[str],
    start_date: str,
    end_date: str,
    sleep_seconds: float,
    force_refresh: bool,
) -> pd.DataFrame:
    basic_path = RAW_DIR / f"daily_basic_{start_date}_{end_date}.parquet"
    print("按交易日拉取全市场 daily_basic 数据...")
    return fetch_by_trade_dates(
        pro=pro,
        api_func=pro.daily_basic,
        trade_dates=trade_dates,
        output_path=basic_path,
        key_cols=["ts_code", "trade_date"],
        fields=[
            "ts_code", "trade_date", "turnover_rate", "turnover_rate_f",
            "pe", "pe_ttm", "pb", "ps", "ps_ttm", "total_share",
            "float_share", "free_share", "total_mv", "circ_mv"
        ],
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
        api_name="daily_basic",
    )


def get_adj_factor_all(
    pro,
    codes: list[str],
    start_date: str,
    end_date: str,
    sleep_seconds: float,
    force_refresh: bool,
) -> pd.DataFrame:
    adj_path = RAW_DIR / f"adj_factor_hs300_{start_date}_{end_date}.parquet"
    print("按股票拉取复权因子 adj_factor...")
    return fetch_by_codes(
        api_func=pro.adj_factor,
        codes=codes,
        output_path=adj_path,
        key_cols=["ts_code", "trade_date"],
        start_date=start_date,
        end_date=end_date,
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
        api_name="adj_factor",
    )


def get_stk_limit_all(
    pro,
    codes: list[str],
    start_date: str,
    end_date: str,
    sleep_seconds: float,
    force_refresh: bool,
) -> pd.DataFrame:
    limit_path = RAW_DIR / f"stk_limit_hs300_{start_date}_{end_date}.parquet"
    print("按股票拉取涨跌停价格 stk_limit...")
    return fetch_by_codes(
        api_func=pro.stk_limit,
        codes=codes,
        output_path=limit_path,
        key_cols=["ts_code", "trade_date"],
        start_date=start_date,
        end_date=end_date,
        sleep_seconds=sleep_seconds,
        force_refresh=force_refresh,
        api_name="stk_limit",
    )


def build_hs300_panel(
    daily: pd.DataFrame,
    basic: pd.DataFrame,
    uni: pd.DataFrame,
    adj_factor: pd.DataFrame | None,
    stk_limit: pd.DataFrame | None,
    start_date: str,
    end_date: str,
) -> pd.DataFrame:
    """
    合并日线 + daily_basic，并按沪深300成分过滤，生成最终研究面板。
    """
    hs300_codes = set(uni["con_code"])
    print(f"按沪深300成分筛选数据，股票数: {len(hs300_codes)}")

    daily_hs300 = daily[daily["ts_code"].isin(hs300_codes)].copy()
    basic_hs300 = basic[basic["ts_code"].isin(hs300_codes)].copy()

    # 统一日期格式
    for df in (daily_hs300, basic_hs300):
        df["trade_date"] = pd.to_datetime(df["trade_date"], format="%Y%m%d")

    # 合并
    panel = pd.merge(
        daily_hs300,
        basic_hs300,
        on=["ts_code", "trade_date"],
        how="left",
        suffixes=("", "_basic")
    )

    if adj_factor is not None and not adj_factor.empty:
        adj_factor = adj_factor.copy()
        adj_factor["trade_date"] = pd.to_datetime(adj_factor["trade_date"], format="%Y%m%d")
        panel = pd.merge(
            panel,
            adj_factor[["ts_code", "trade_date", "adj_factor"]],
            on=["ts_code", "trade_date"],
            how="left",
        )
        latest_adj = panel.groupby("ts_code")["adj_factor"].transform("last")
        for col in ["open", "high", "low", "close", "pre_close"]:
            panel[f"qfq_{col}"] = panel[col] * panel["adj_factor"] / latest_adj

    if stk_limit is not None and not stk_limit.empty:
        stk_limit = stk_limit.copy().rename(columns={"up_limit": "limit_up", "down_limit": "limit_down"})
        stk_limit["trade_date"] = pd.to_datetime(stk_limit["trade_date"], format="%Y%m%d")
        panel = pd.merge(
            panel,
            stk_limit[["ts_code", "trade_date", "limit_up", "limit_down"]],
            on=["ts_code", "trade_date"],
            how="left",
        )
        panel["is_limit_up"] = (panel["close"] >= panel["limit_up"] - 1e-6).fillna(False)
        panel["is_limit_down"] = (panel["close"] <= panel["limit_down"] + 1e-6).fillna(False)

    panel["listed_days"] = panel.groupby("ts_code").cumcount() + 1
    panel["is_new_listing_60d"] = panel["listed_days"] < 60
    panel["is_tradeable_buy"] = True
    panel["is_tradeable_sell"] = True
    if "vol" in panel.columns:
        panel["is_tradeable_buy"] &= panel["vol"].fillna(0) > 0
        panel["is_tradeable_sell"] &= panel["vol"].fillna(0) > 0
    if "is_limit_up" in panel.columns:
        panel["is_tradeable_buy"] &= ~panel["is_limit_up"]
    if "is_limit_down" in panel.columns:
        panel["is_tradeable_sell"] &= ~panel["is_limit_down"]

    panel.sort_values(["ts_code", "trade_date"], inplace=True)
    panel.to_parquet(PROCESSED_DIR / f"hs300_panel_{start_date}_{end_date}.parquet", index=False)
    print(f"最终面板条数: {len(panel)}")
    return panel


def main():
    args = parse_args()
    init_dirs()
    pro = init_tushare()
    trade_dates = get_trade_dates(
        pro,
        start_date=args.start_date,
        end_date=args.end_date,
        exchange=args.exchange,
    )

    # 1) 股票池
    uni = get_hs300_universe(pro, end_date=args.end_date)
    hs300_codes = sorted(uni["con_code"].dropna().unique().tolist())

    # 2) 行情 & basic
    daily = get_daily_all(
        pro,
        trade_dates=trade_dates,
        start_date=args.start_date,
        end_date=args.end_date,
        sleep_seconds=args.sleep_seconds,
        force_refresh=args.force_refresh,
    )
    basic = get_daily_basic_all(
        pro,
        trade_dates=trade_dates,
        start_date=args.start_date,
        end_date=args.end_date,
        sleep_seconds=args.sleep_seconds,
        force_refresh=args.force_refresh,
    )

    adj_factor = pd.DataFrame()
    stk_limit = pd.DataFrame()
    if args.with_adj_factor:
        adj_factor = get_adj_factor_all(
            pro,
            codes=hs300_codes,
            start_date=args.start_date,
            end_date=args.end_date,
            sleep_seconds=args.sleep_seconds,
            force_refresh=args.force_refresh,
        )
    if args.with_stk_limit:
        stk_limit = get_stk_limit_all(
            pro,
            codes=hs300_codes,
            start_date=args.start_date,
            end_date=args.end_date,
            sleep_seconds=args.sleep_seconds,
            force_refresh=args.force_refresh,
        )

    # 3) 合并为研究面板
    panel = build_hs300_panel(
        daily,
        basic,
        uni,
        adj_factor=adj_factor,
        stk_limit=stk_limit,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    print(panel.head())
    print("数据下载与合并完成。")


if __name__ == "__main__":
    main()
