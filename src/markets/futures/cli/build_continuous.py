from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from ..data import build_continuous_kline, load_hots_table
from ..paths import (
    FUTURES_HOTS_PATH,
    FUTURES_KLINE_DIR,
    FUTURES_REPORTS_DIR,
    ensure_futures_dirs,
)
from ..research import build_etf_nav, calc_metrics, save_nav_report


DEFAULT_SYMBOLS = ["AL", "AO", "CU", "LC", "NI", "PB", "SI", "SN", "ZN"]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build futures continuous series and ETF tracking report.")
    parser.add_argument("--kline-root", type=Path, default=FUTURES_KLINE_DIR)
    parser.add_argument("--hots", type=Path, default=FUTURES_HOTS_PATH)
    parser.add_argument("--out-prefix", type=Path, default=FUTURES_REPORTS_DIR / "continuous_etf_report")
    parser.add_argument("--initial-nav", type=float, default=1.0)
    parser.add_argument("--symbols", nargs="*", default=DEFAULT_SYMBOLS)
    return parser


def build_average_nav(continuous_by_symbol: dict[str, pd.DataFrame], initial_nav: float) -> pd.Series:
    nav_frames: list[pd.Series] = []
    for symbol, frame in continuous_by_symbol.items():
        returns = frame.set_index("trade_date")["ret_1d"].fillna(0.0)
        nav = (1.0 + returns).cumprod() * initial_nav
        nav_frames.append(nav.rename(symbol))

    if not nav_frames:
        raise ValueError("no continuous series available to build average nav")

    nav_df = pd.concat(nav_frames, axis=1).sort_index().ffill()
    return nav_df.mean(axis=1).rename("avg_nav")


def run(args: argparse.Namespace) -> Path:
    ensure_futures_dirs()

    hots = load_hots_table(args.hots)
    symbols = [symbol.upper() for symbol in args.symbols]
    continuous_by_symbol: dict[str, pd.DataFrame] = {}
    contract_maps: dict[str, pd.DataFrame] = {}

    for symbol in symbols:
        symbol_hots = hots.loc[hots["symbol"] == symbol]
        if symbol_hots.empty:
            continue
        continuous, contract_map = build_continuous_kline(hots, args.kline_root, symbol)
        continuous_by_symbol[symbol] = continuous
        contract_maps[symbol] = contract_map

    if not continuous_by_symbol:
        raise ValueError("no continuous series were built for the requested symbols")

    avg_nav = build_average_nav(continuous_by_symbol, args.initial_nav)
    etf_nav = build_etf_nav(
        symbols=list(continuous_by_symbol),
        hots=hots,
        contract_maps=contract_maps,
        kline_root=args.kline_root,
        initial_nav=args.initial_nav,
    )

    avg_metrics = calc_metrics(avg_nav)
    etf_metrics = calc_metrics(etf_nav)
    csv_path, plot_path = save_nav_report(avg_nav, etf_nav, avg_metrics, etf_metrics, args.out_prefix)
    print(f"Saved futures report csv: {csv_path}")
    print(f"Saved futures report plot: {plot_path}")
    return args.out_prefix


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
