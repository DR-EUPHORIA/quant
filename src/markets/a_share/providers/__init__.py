"""A-share data provider interfaces."""

from .tushare import (
    END_DATE,
    EXCHANGE,
    INDEX_CODE,
    START_DATE,
    fetch_index_weight,
    fetch_latest_hs300_universe,
    fetch_trade_dates,
    init_tushare_client,
)

__all__ = [
    "START_DATE",
    "END_DATE",
    "INDEX_CODE",
    "EXCHANGE",
    "init_tushare_client",
    "fetch_trade_dates",
    "fetch_latest_hs300_universe",
    "fetch_index_weight",
]
