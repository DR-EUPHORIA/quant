import pandas as pd

from .schema import normalize_trade_date, validate_columns


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
    summary.loc[
        ~summary["has_live_status"] & ~summary["has_paused_status"] & summary["has_delisted_status"],
        "list_status",
    ] = "D"

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
