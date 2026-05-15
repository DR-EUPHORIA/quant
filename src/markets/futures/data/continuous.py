from __future__ import annotations

from pathlib import Path

import pandas as pd

from .io import find_contract_file, read_contract_csv


def safe_get(df: pd.DataFrame, trade_date: pd.Timestamp, column: str) -> float | None:
    row = df.loc[df["trade_date"] == trade_date, column]
    if row.empty:
        return None
    value = row.iloc[0]
    if pd.isna(value):
        return None
    return float(value)


def build_continuous_kline(
    hots: pd.DataFrame,
    kline_root: Path,
    symbol: str,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    symbol_hots = hots.loc[hots["symbol"].str.upper() == symbol.upper()].copy()
    if symbol_hots.empty:
        raise ValueError(f"no hots records found for {symbol}")

    symbol_hots = symbol_hots.sort_values(["hot_start_date", "hot_end_date"]).reset_index(drop=True)

    contract_frames: dict[str, pd.DataFrame] = {}
    for contract in symbol_hots["order_id"].unique():
        path = find_contract_file(kline_root, symbol.upper(), contract)
        contract_frames[contract] = read_contract_csv(path)

    adjusted_segments: list[pd.DataFrame] = []
    contract_map_rows: list[dict[str, object]] = []
    cumulative_shift = 0.0
    previous_contract: str | None = None
    previous_end_date: pd.Timestamp | None = None

    for row in symbol_hots.itertuples(index=False):
        contract = str(row.order_id)
        start_date = pd.Timestamp(row.hot_start_date)
        end_date = pd.Timestamp(row.hot_end_date)
        frame = contract_frames[contract]
        segment = frame.loc[
            (frame["trade_date"] >= start_date) & (frame["trade_date"] <= end_date)
        ].copy()
        if segment.empty:
            continue

        if previous_contract is not None and previous_end_date is not None:
            prev_frame = contract_frames[previous_contract]
            prev_close = safe_get(prev_frame, previous_end_date, "close")
            next_open = safe_get(frame, start_date, "open")
            if prev_close is not None and next_open is not None:
                cumulative_shift += prev_close - next_open

        for column in ("open", "high", "low", "close"):
            segment[f"adj_{column}"] = segment[column] + cumulative_shift

        segment["symbol"] = symbol.upper()
        segment["contract"] = contract
        adjusted_segments.append(segment)

        contract_map_rows.append(
            {
                "symbol": symbol.upper(),
                "contract": contract,
                "hot_start_date": start_date,
                "hot_end_date": end_date,
                "contract_multiplier": row.contract_multiplier,
                "commission_type": row.commission_type,
                "open_commission": row.open_commission,
                "close_commission": row.close_commission,
            }
        )

        previous_contract = contract
        previous_end_date = end_date

    if not adjusted_segments:
        raise ValueError(f"no kline records matched hots schedule for {symbol}")

    continuous = (
        pd.concat(adjusted_segments, ignore_index=True)
        .sort_values("trade_date")
        .drop_duplicates(subset=["trade_date"], keep="last")
        .reset_index(drop=True)
    )
    continuous["ret_1d"] = continuous["adj_close"].pct_change(fill_method=None)
    contract_map = pd.DataFrame(contract_map_rows)
    return continuous, contract_map
