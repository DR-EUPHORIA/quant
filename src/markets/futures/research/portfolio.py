from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from ..data.io import find_contract_file, read_contract_csv


@dataclass(frozen=True)
class CommissionRule:
    fee_open: float
    fee_close: float


def _resolve_rule(row: pd.Series) -> CommissionRule:
    if str(row["commission_type"]).lower() == "rate":
        return CommissionRule(float(row["open_commission"]), float(row["close_commission"]))
    return CommissionRule(float(row["open_commission"]), float(row["close_commission"]))


def build_etf_nav(
    symbols: list[str],
    hots: pd.DataFrame,
    contract_maps: dict[str, pd.DataFrame],
    kline_root: Path,
    initial_nav: float = 1.0,
) -> pd.Series:
    holdings: list[pd.Series] = []

    for symbol in symbols:
        symbol_hots = hots.loc[hots["symbol"].str.upper() == symbol.upper()].copy()
        if symbol_hots.empty or symbol not in contract_maps:
            continue

        nav = initial_nav
        nav_points: list[dict[str, object]] = []

        for row in symbol_hots.itertuples(index=False):
            contract = str(row.order_id)
            rule = _resolve_rule(pd.Series(row._asdict()))
            frame = read_contract_csv(find_contract_file(kline_root, symbol.upper(), contract))
            segment = frame.loc[
                (frame["trade_date"] >= pd.Timestamp(row.hot_start_date))
                & (frame["trade_date"] <= pd.Timestamp(row.hot_end_date))
            ].copy()
            if segment.empty:
                continue

            entry_price = float(segment.iloc[0]["open"])
            exit_price = float(segment.iloc[-1]["close"])
            gross_return = exit_price / entry_price - 1.0
            commission = rule.fee_open + rule.fee_close
            nav *= 1.0 + gross_return - commission
            nav_points.append({"trade_date": segment.iloc[-1]["trade_date"], "nav": nav})

        if nav_points:
            series = pd.DataFrame(nav_points).drop_duplicates(subset=["trade_date"], keep="last")
            series = series.sort_values("trade_date").set_index("trade_date")["nav"]
            holdings.append(series.rename(symbol.upper()))

    if not holdings:
        raise ValueError("no ETF tracking series could be built")

    nav_df = pd.concat(holdings, axis=1).sort_index().ffill()
    etf_nav = nav_df.mean(axis=1).rename("etf_nav")
    return etf_nav
