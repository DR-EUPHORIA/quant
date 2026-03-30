import sys
from pathlib import Path

# 将项目根目录加入 Python 路径
ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))

import argparse
import time

import pandas as pd
import tushare as ts

# === 基本参数 ===
DATA_ROOT = ROOT / "data" / "tushare"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"

START_DATE = "20150101"
END_DATE = "20241231"
INDEX_CODE = "000300.SH"  # 沪深300
EXCHANGE = "SSE"


def init_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def init_tushare():
    try:
        from config.config_tushare import TUSHARE_TOKEN
    except ImportError as exc:
        raise RuntimeError("请先在项目根目录下创建 config_tushare.py，并定义 TUSHARE_TOKEN") from exc
    ts.set_token(TUSHARE_TOKEN)
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


def build_hs300_panel(
    daily: pd.DataFrame,
    basic: pd.DataFrame,
    uni: pd.DataFrame,
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

    # 3) 合并为研究面板
    panel = build_hs300_panel(
        daily,
        basic,
        uni,
        start_date=args.start_date,
        end_date=args.end_date,
    )

    print(panel.head())
    print("数据下载与合并完成。")


if __name__ == "__main__":
    main()
