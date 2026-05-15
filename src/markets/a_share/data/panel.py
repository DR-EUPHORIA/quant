from pathlib import Path

import pandas as pd

from ..paths import DATA_ROOT, PROCESSED_DIR, RAW_DIR, ROOT
from ..schema import normalize_trade_date, validate_columns
from ..universe import (
    DEFAULT_UNIVERSE,
    FALLBACK_UNIVERSE,
    apply_universe_filter,
    resolve_universe_path,
)
from .enrich import enrich_with_adjustment, enrich_with_limits
from .features import add_research_features
from .io import load_optional_parquet, load_parquet, resolve_output_path


DEFAULT_DAILY = RAW_DIR / "daily_20150101_20241231.parquet"
DEFAULT_BASIC = RAW_DIR / "daily_basic_20150101_20241231.parquet"
DEFAULT_ADJ_FACTOR = RAW_DIR / "adj_factor_hs300_20150101_20241231.parquet"
DEFAULT_STK_LIMIT = RAW_DIR / "stk_limit_hs300_20150101_20241231.parquet"
DEFAULT_SUSPEND_D = RAW_DIR / "suspend_d_hs300_20150101_20241231.parquet"
DEFAULT_STOCK_BASIC = RAW_DIR / "stock_basic_all_status.parquet"
DEFAULT_STOCK_ST = RAW_DIR / "stock_st_20160101_20241231.parquet"
DEFAULT_OUTPUT = PROCESSED_DIR / "hs300_panel_20150101_20241231.parquet"


def build_panel(
    daily: pd.DataFrame,
    basic: pd.DataFrame,
    universe: pd.DataFrame,
    adj_factor: pd.DataFrame | None = None,
    stk_limit: pd.DataFrame | None = None,
    suspend_d: pd.DataFrame | None = None,
    stock_basic: pd.DataFrame | None = None,
    stock_st: pd.DataFrame | None = None,
) -> pd.DataFrame:
    validate_columns(daily, ["ts_code", "trade_date", "open", "high", "low", "close"], "daily")
    validate_columns(basic, ["ts_code", "trade_date"], "daily_basic")
    validate_columns(universe, ["con_code"], "universe")

    daily = normalize_trade_date(daily)
    basic = normalize_trade_date(basic)
    universe = universe.copy()

    daily = daily.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
    basic = basic.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")

    panel = pd.merge(daily, basic, on=["ts_code", "trade_date"], how="left", suffixes=("", "_basic"))
    panel = apply_universe_filter(panel, universe)
    panel = enrich_with_adjustment(panel, adj_factor if adj_factor is not None else pd.DataFrame())
    panel = enrich_with_limits(panel, stk_limit if stk_limit is not None else pd.DataFrame())
    panel = add_research_features(panel, suspend_d=suspend_d, stock_basic=stock_basic, stock_st=stock_st)
    panel = panel.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)

    duplicated = panel.duplicated(subset=["ts_code", "trade_date"]).sum()
    if duplicated:
        raise ValueError(f"面板主键重复: {duplicated}")

    return panel


def print_summary(panel: pd.DataFrame) -> None:
    start_date = panel["trade_date"].min().date()
    end_date = panel["trade_date"].max().date()
    n_codes = panel["ts_code"].nunique()
    n_rows = len(panel)
    print(f"面板行数: {n_rows:,}")
    print(f"股票数: {n_codes}")
    print(f"日期范围: {start_date} -> {end_date}")
    null_ratio = panel.isna().mean().sort_values(ascending=False).head(10)
    print("\n缺失率最高的字段（Top 10）:")
    print(null_ratio.to_string())
