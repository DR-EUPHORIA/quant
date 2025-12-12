# scripts/download_hs300.py
import os
from pathlib import Path
import time

import pandas as pd
import tushare as ts

# 从本地配置导入 token
try:
    from config_tushare import TUSHARE_TOKEN
except ImportError:
    raise RuntimeError("请先在项目根目录下创建 config_tushare.py，并定义 TUSHARE_TOKEN")


# === 基本参数 ===
DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "tushare"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"

START_DATE = "20150101"
END_DATE = "20241231"
INDEX_CODE = "000300.SH"  # 沪深300


def init_dirs():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def init_tushare():
    ts.set_token(TUSHARE_TOKEN)
    pro = ts.pro_api()
    return pro


def get_hs300_universe(pro: ts.pro_api, end_date: str) -> pd.DataFrame:
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


def get_daily_all(pro: ts.pro_api) -> pd.DataFrame:
    """
    从 TuShare 拉全市场日线行情，再按沪深300股票池筛选。
    这样调用次数少，逻辑简单。
    """
    daily_path = RAW_DIR / f"daily_{START_DATE}_{END_DATE}.parquet"
    if daily_path.exists():
        print("已发现缓存的日线行情文件，直接加载。")
        return pd.read_parquet(daily_path)

    print("下载全市场日线行情（可能稍慢，但只调用一次接口）...")
    df = pro.daily(start_date=START_DATE, end_date=END_DATE)
    df.to_parquet(daily_path, index=False)
    print(f"日线行情条数: {len(df)}")
    return df


def get_daily_basic_all(pro: ts.pro_api) -> pd.DataFrame:
    """
    拉全市场 daily_basic（市值、换手率、PE、PB 等）。
    TuShare 限制较松，一般一次可拉全区间。
    """
    basic_path = RAW_DIR / f"daily_basic_{START_DATE}_{END_DATE}.parquet"
    if basic_path.exists():
        print("已发现缓存的 daily_basic 文件，直接加载。")
        return pd.read_parquet(basic_path)

    print("下载全市场 daily_basic 数据...")
    # 注意：有些版本需要分段拉取，这里先试一把
    df_list = []
    # 简单按年份分段，避免一次调用过大
    for year in range(int(START_DATE[:4]), int(END_DATE[:4]) + 1):
        s = f"{year}0101"
        e = f"{year}1231"
        print(f"  拉取 {s} - {e}")
        tmp = pro.daily_basic(start_date=s, end_date=e, fields=[
            "ts_code", "trade_date", "turnover_rate", "turnover_rate_f",
            "pe", "pe_ttm", "pb", "ps", "ps_ttm", "total_share",
            "float_share", "free_share", "total_mv", "circ_mv"
        ])
        df_list.append(tmp)
        # 给接口一点喘息时间
        time.sleep(0.4)

    df = pd.concat(df_list, ignore_index=True)
    df.to_parquet(basic_path, index=False)
    print(f"daily_basic 条数: {len(df)}")
    return df


def build_hs300_panel(daily: pd.DataFrame, basic: pd.DataFrame, uni: pd.DataFrame) -> pd.DataFrame:
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
    panel.to_parquet(PROCESSED_DIR / f"hs300_panel_{START_DATE}_{END_DATE}.parquet", index=False)
    print(f"最终面板条数: {len(panel)}")
    return panel


def main():
    init_dirs()
    pro = init_tushare()

    # 1) 股票池
    uni = get_hs300_universe(pro, end_date=END_DATE)

    # 2) 行情 & basic
    daily = get_daily_all(pro)
    basic = get_daily_basic_all(pro)

    # 3) 合并为研究面板
    panel = build_hs300_panel(daily, basic, uni)

    print(panel.head())
    print("数据下载与合并完成。")


if __name__ == "__main__":
    main()
