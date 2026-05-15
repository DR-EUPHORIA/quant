import pandas as pd

from .enrich import (
    enrich_with_st_flags,
    enrich_with_stock_basic_flags,
    enrich_with_suspend_flags,
)


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
    panel["volatility_20d"] = grouped["ret_1d"].transform(lambda x: x.rolling(20, min_periods=10).std())

    if "amount" in panel.columns:
        amount_ma20 = grouped["amount"].transform(lambda x: x.rolling(20, min_periods=10).mean())
        panel["amount_ma20_ratio"] = panel["amount"] / amount_ma20

    if "turnover_rate" in panel.columns:
        turnover_ma20 = grouped["turnover_rate"].transform(lambda x: x.rolling(20, min_periods=10).mean())
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
