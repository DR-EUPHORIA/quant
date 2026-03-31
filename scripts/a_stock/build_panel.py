import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


DATA_ROOT = ROOT / "data" / "tushare"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"

DEFAULT_DAILY = RAW_DIR / "daily_20150101_20241231.parquet"
DEFAULT_BASIC = RAW_DIR / "daily_basic_20150101_20241231.parquet"
DEFAULT_UNIVERSE = RAW_DIR / "000300_sh_index_weight_20150101_20241231.parquet"
FALLBACK_UNIVERSE = RAW_DIR / "hs300_constituents_latest.parquet"
DEFAULT_ADJ_FACTOR = RAW_DIR / "adj_factor_hs300_20150101_20241231.parquet"
DEFAULT_STK_LIMIT = RAW_DIR / "stk_limit_hs300_20150101_20241231.parquet"
DEFAULT_SUSPEND_D = RAW_DIR / "suspend_d_hs300_20150101_20241231.parquet"
DEFAULT_STOCK_BASIC = RAW_DIR / "stock_basic_all_status.parquet"
DEFAULT_STOCK_ST = RAW_DIR / "stock_st_20160101_20241231.parquet"
DEFAULT_OUTPUT = PROCESSED_DIR / "hs300_panel_20150101_20241231.parquet"
FALLBACK_OUTPUT = ROOT / "results" / "a_stock" / "panels" / "hs300_panel_20150101_20241231.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="构建沪深300研究面板（行情 + daily_basic -> parquet）"
    )
    parser.add_argument("--daily-path", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--basic-path", type=Path, default=DEFAULT_BASIC)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--adj-factor-path", type=Path, default=DEFAULT_ADJ_FACTOR)
    parser.add_argument("--stk-limit-path", type=Path, default=DEFAULT_STK_LIMIT)
    parser.add_argument("--suspend-d-path", type=Path, default=DEFAULT_SUSPEND_D)
    parser.add_argument("--stock-basic-path", type=Path, default=DEFAULT_STOCK_BASIC)
    parser.add_argument("--stock-st-path", type=Path, default=DEFAULT_STOCK_ST)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_parquet(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name} 文件不存在: {path}")
    df = pd.read_parquet(path)
    if df.empty:
        raise ValueError(f"{name} 为空: {path}")
    return df


def normalize_trade_date(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce")
    if out["trade_date"].isna().any():
        out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    if out["trade_date"].isna().any():
        raise ValueError("存在无法解析的 trade_date")
    return out


def validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{name} 缺少必要列: {missing}")


def load_optional_parquet(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def resolve_universe_path(path: Path) -> Path:
    if path.exists():
        return path
    if path == DEFAULT_UNIVERSE and FALLBACK_UNIVERSE.exists():
        return FALLBACK_UNIVERSE
    return path


def enrich_with_adjustment(panel: pd.DataFrame, adj_factor: pd.DataFrame) -> pd.DataFrame:
    if adj_factor.empty:
        return panel

    validate_columns(adj_factor, ["ts_code", "trade_date", "adj_factor"], "adj_factor")
    adj_factor = normalize_trade_date(adj_factor)
    adj_factor = adj_factor.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")

    panel = panel.merge(
        adj_factor[["ts_code", "trade_date", "adj_factor"]],
        on=["ts_code", "trade_date"],
        how="left",
    )

    latest_adj = panel.groupby("ts_code")["adj_factor"].transform("last")
    first_adj = panel.groupby("ts_code")["adj_factor"].transform("first")
    price_cols = ["open", "high", "low", "close", "pre_close"]
    for col in price_cols:
        if col in panel.columns:
            panel[f"qfq_{col}"] = panel[col] * panel["adj_factor"] / latest_adj
            panel[f"hfq_{col}"] = panel[col] * panel["adj_factor"] / first_adj

    return panel


def enrich_with_limits(panel: pd.DataFrame, stk_limit: pd.DataFrame) -> pd.DataFrame:
    if stk_limit.empty:
        return panel

    rename_map = {"up_limit": "limit_up", "down_limit": "limit_down"}
    stk_limit = stk_limit.rename(columns=rename_map)
    validate_columns(stk_limit, ["ts_code", "trade_date", "limit_up", "limit_down"], "stk_limit")
    stk_limit = normalize_trade_date(stk_limit)
    stk_limit = stk_limit.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")

    panel = panel.merge(
        stk_limit[["ts_code", "trade_date", "limit_up", "limit_down"]],
        on=["ts_code", "trade_date"],
        how="left",
    )

    tolerance = 1e-6
    panel["is_limit_up"] = (panel["close"] >= panel["limit_up"] - tolerance).fillna(False)
    panel["is_limit_down"] = (panel["close"] <= panel["limit_down"] + tolerance).fillna(False)
    panel["is_one_word_limit_up"] = (
        panel["is_limit_up"]
        & (panel["open"] == panel["high"])
        & (panel["high"] == panel["low"])
        & (panel["low"] == panel["close"])
    )
    panel["is_one_word_limit_down"] = (
        panel["is_limit_down"]
        & (panel["open"] == panel["high"])
        & (panel["high"] == panel["low"])
        & (panel["low"] == panel["close"])
    )
    return panel


def enrich_with_suspend_flags(panel: pd.DataFrame, suspend_d: pd.DataFrame) -> pd.DataFrame:
    if suspend_d.empty:
        panel["is_suspended"] = False
        return panel

    validate_columns(suspend_d, ["ts_code", "trade_date"], "suspend_d")
    suspend_d = normalize_trade_date(suspend_d)
    suspend_flags = (
        suspend_d[["ts_code", "trade_date"]]
        .drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        .assign(is_suspended=True)
    )
    panel = panel.merge(suspend_flags, on=["ts_code", "trade_date"], how="left")
    panel["is_suspended"] = panel["is_suspended"].fillna(False).astype(bool)
    return panel


def enrich_with_stock_basic_flags(panel: pd.DataFrame, stock_basic: pd.DataFrame) -> pd.DataFrame:
    if stock_basic.empty:
        panel["list_status"] = pd.NA
        panel["list_date"] = pd.NaT
        panel["delist_date"] = pd.NaT
        panel["is_listed_from_stock_basic"] = True
        panel["is_paused_listing"] = False
        return panel

    validate_columns(stock_basic, ["ts_code", "list_status", "list_date"], "stock_basic")
    stock_basic = stock_basic.copy()
    stock_basic["list_date"] = pd.to_datetime(stock_basic["list_date"], format="%Y%m%d", errors="coerce")
    if "delist_date" in stock_basic.columns:
        stock_basic["delist_date"] = pd.to_datetime(stock_basic["delist_date"], format="%Y%m%d", errors="coerce")
    else:
        stock_basic["delist_date"] = pd.NaT

    summary = (
        stock_basic.groupby("ts_code", as_index=False)
        .agg(
            list_date=("list_date", "min"),
            delist_date=("delist_date", "max"),
            has_live_status=("list_status", lambda s: (s == "L").any()),
            has_paused_status=("list_status", lambda s: (s == "P").any()),
            has_delisted_status=("list_status", lambda s: (s == "D").any()),
        )
    )

    summary["list_status"] = "L"
    summary.loc[~summary["has_live_status"] & summary["has_paused_status"], "list_status"] = "P"
    summary.loc[~summary["has_live_status"] & ~summary["has_paused_status"] & summary["has_delisted_status"], "list_status"] = "D"

    panel = panel.merge(
        summary[["ts_code", "list_status", "list_date", "delist_date", "has_live_status", "has_paused_status"]],
        on="ts_code",
        how="left",
    )

    is_listed = True
    if "list_date" in panel.columns:
        is_listed = panel["list_date"].isna() | (panel["trade_date"] >= panel["list_date"])
    if "delist_date" in panel.columns:
        is_listed &= panel["delist_date"].isna() | (panel["trade_date"] <= panel["delist_date"])
    panel["is_listed_from_stock_basic"] = is_listed.fillna(True)
    panel["is_paused_listing"] = (
        panel["has_paused_status"].fillna(False) & ~panel["has_live_status"].fillna(False)
    )
    panel["is_listed_from_stock_basic"] = panel["is_listed_from_stock_basic"].astype(bool)
    panel["is_paused_listing"] = panel["is_paused_listing"].astype(bool)

    panel = panel.drop(columns=["has_live_status", "has_paused_status"], errors="ignore")
    return panel


def enrich_with_st_flags(panel: pd.DataFrame, stock_st: pd.DataFrame) -> pd.DataFrame:
    if stock_st.empty:
        panel["is_st"] = False
        return panel

    validate_columns(stock_st, ["ts_code", "trade_date"], "stock_st")
    stock_st = normalize_trade_date(stock_st)
    st_flags = (
        stock_st[["ts_code", "trade_date"]]
        .drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        .assign(is_st=True)
    )
    panel = panel.merge(st_flags, on=["ts_code", "trade_date"], how="left")
    panel["is_st"] = panel["is_st"].fillna(False).astype(bool)
    return panel


def add_research_features(
    panel: pd.DataFrame,
    suspend_d: pd.DataFrame | None = None,
    stock_basic: pd.DataFrame | None = None,
    stock_st: pd.DataFrame | None = None,
) -> pd.DataFrame:
    panel = panel.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
    panel["listed_days"] = panel.groupby("ts_code").cumcount() + 1
    panel["is_new_listing_60d"] = panel["listed_days"] < 60

    base_price_col = "qfq_close" if "qfq_close" in panel.columns else "close"
    grouped = panel.groupby("ts_code", group_keys=False)

    panel["ret_1d"] = grouped[base_price_col].pct_change(fill_method=None)
    panel["ret_5d"] = grouped[base_price_col].pct_change(5, fill_method=None)
    panel["ret_20d"] = grouped[base_price_col].pct_change(20, fill_method=None)
    panel["volatility_20d"] = grouped["ret_1d"].transform(
        lambda x: x.rolling(20, min_periods=10).std()
    )

    if "amount" in panel.columns:
        amount_ma20 = grouped["amount"].transform(lambda x: x.rolling(20, min_periods=10).mean())
        panel["amount_ma20_ratio"] = panel["amount"] / amount_ma20

    if "turnover_rate" in panel.columns:
        turnover_ma20 = grouped["turnover_rate"].transform(
            lambda x: x.rolling(20, min_periods=10).mean()
        )
        panel["turnover_rate_ma20_ratio"] = panel["turnover_rate"] / turnover_ma20

    panel = enrich_with_suspend_flags(panel, suspend_d if suspend_d is not None else pd.DataFrame())
    panel = enrich_with_stock_basic_flags(panel, stock_basic if stock_basic is not None else pd.DataFrame())
    panel = enrich_with_st_flags(panel, stock_st if stock_st is not None else pd.DataFrame())

    panel["is_tradeable_buy"] = True
    panel["is_tradeable_sell"] = True
    if "vol" in panel.columns:
        panel["is_tradeable_buy"] &= panel["vol"].fillna(0) > 0
        panel["is_tradeable_sell"] &= panel["vol"].fillna(0) > 0
    if "is_limit_up" in panel.columns:
        panel["is_tradeable_buy"] &= ~panel["is_limit_up"].fillna(False)
    if "is_limit_down" in panel.columns:
        panel["is_tradeable_sell"] &= ~panel["is_limit_down"].fillna(False)
    if "is_suspended" in panel.columns:
        panel["is_tradeable_buy"] &= ~panel["is_suspended"].fillna(False)
        panel["is_tradeable_sell"] &= ~panel["is_suspended"].fillna(False)
    if "is_listed_from_stock_basic" in panel.columns:
        panel["is_tradeable_buy"] &= panel["is_listed_from_stock_basic"].fillna(True)
        panel["is_tradeable_sell"] &= panel["is_listed_from_stock_basic"].fillna(True)
    if "is_paused_listing" in panel.columns:
        panel["is_tradeable_buy"] &= ~panel["is_paused_listing"].fillna(False)
        panel["is_tradeable_sell"] &= ~panel["is_paused_listing"].fillna(False)
    if "is_st" in panel.columns:
        panel["is_tradeable_buy"] &= ~panel["is_st"].fillna(False)

    return panel


def apply_universe_filter(panel: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    universe = universe.copy()
    validate_columns(universe, ["con_code"], "universe")

    if "trade_date" in universe.columns:
        universe = normalize_trade_date(universe)

    if "trade_date" in universe.columns and universe["trade_date"].nunique() > 1:
        universe = universe.rename(columns={"con_code": "ts_code"})
        if "weight" in universe.columns:
            universe = universe.rename(columns={"weight": "universe_weight"})
        keep_cols = [col for col in ["ts_code", "trade_date", "universe_weight"] if col in universe.columns]
        universe = universe[keep_cols].drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        panel = panel.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
        universe = universe.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

        merged_groups = []
        for ts_code, panel_group in panel.groupby("ts_code", sort=False):
            universe_group = universe.loc[universe["ts_code"] == ts_code]
            if universe_group.empty:
                continue
            merged_group = pd.merge_asof(
                panel_group.sort_values("trade_date"),
                universe_group.sort_values("trade_date"),
                on="trade_date",
                by="ts_code",
                direction="backward",
            )
            merged_groups.append(merged_group)
        if not merged_groups:
            raise ValueError("动态成分过滤后面板为空")
        filtered = pd.concat(merged_groups, ignore_index=True)
        filtered = filtered.dropna(subset=["universe_weight"]) if "universe_weight" in filtered.columns else filtered
        filtered["is_dynamic_universe"] = True
        return filtered

    hs300_codes = sorted(universe["con_code"].dropna().unique().tolist())
    if not hs300_codes:
        raise ValueError("成分股列表为空")
    filtered = panel[panel["ts_code"].isin(hs300_codes)].copy()
    filtered["is_dynamic_universe"] = False
    return filtered


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

    panel = pd.merge(
        daily,
        basic,
        on=["ts_code", "trade_date"],
        how="left",
        suffixes=("", "_basic"),
    )
    panel = apply_universe_filter(panel, universe)

    panel = enrich_with_adjustment(panel, adj_factor if adj_factor is not None else pd.DataFrame())
    panel = enrich_with_limits(panel, stk_limit if stk_limit is not None else pd.DataFrame())
    panel = add_research_features(
        panel,
        suspend_d=suspend_d,
        stock_basic=stock_basic,
        stock_st=stock_st,
    )
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


def resolve_output_path(desired_path: Path) -> Path:
    desired_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(desired_path, "ab"):
            pass
        desired_path.unlink(missing_ok=True)
        return desired_path
    except OSError:
        fallback_path = FALLBACK_OUTPUT.parent / desired_path.name
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        return fallback_path


def main() -> None:
    args = parse_args()
    output_path = resolve_output_path(args.output_path)
    universe_path = resolve_universe_path(args.universe_path)

    daily = load_parquet(args.daily_path, "daily")
    basic = load_parquet(args.basic_path, "daily_basic")
    universe = load_parquet(universe_path, "universe")
    adj_factor = load_optional_parquet(args.adj_factor_path)
    stk_limit = load_optional_parquet(args.stk_limit_path)
    suspend_d = load_optional_parquet(args.suspend_d_path)
    stock_basic = load_optional_parquet(args.stock_basic_path)
    stock_st = load_optional_parquet(args.stock_st_path)

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

    print(f"已写出面板: {output_path}")
    print(f"使用股票池文件: {universe_path}")
    print_summary(panel)


if __name__ == "__main__":
    main()
