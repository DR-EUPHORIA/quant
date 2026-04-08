from __future__ import annotations

import argparse
from pathlib import Path

from ..data import build_panel, load_optional_parquet, load_parquet, resolve_output_path
from ..data.panel import (
    DEFAULT_ADJ_FACTOR,
    DEFAULT_BASIC,
    DEFAULT_DAILY,
    DEFAULT_OUTPUT,
    DEFAULT_STK_LIMIT,
    DEFAULT_STOCK_BASIC,
    DEFAULT_STOCK_ST,
    DEFAULT_SUSPEND_D,
    print_summary,
)
from ..paths import ensure_a_stock_dirs
from ..universe import DEFAULT_UNIVERSE, resolve_universe_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build the A-share research panel.")
    parser.add_argument("--daily-path", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--basic-path", type=Path, default=DEFAULT_BASIC)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--adj-factor-path", type=Path, default=DEFAULT_ADJ_FACTOR)
    parser.add_argument("--stk-limit-path", type=Path, default=DEFAULT_STK_LIMIT)
    parser.add_argument("--suspend-path", type=Path, default=DEFAULT_SUSPEND_D)
    parser.add_argument("--stock-basic-path", type=Path, default=DEFAULT_STOCK_BASIC)
    parser.add_argument("--stock-st-path", type=Path, default=DEFAULT_STOCK_ST)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT)
    return parser


def run(args: argparse.Namespace) -> Path:
    ensure_a_stock_dirs()

    universe_path = resolve_universe_path(args.universe_path)
    output_path = resolve_output_path(args.output_path)

    daily = load_parquet(args.daily_path, "daily")
    basic = load_parquet(args.basic_path, "daily_basic")
    universe = load_parquet(universe_path, "universe")
    adj_factor = load_optional_parquet(args.adj_factor_path)
    stk_limit = load_optional_parquet(args.stk_limit_path)
    suspend_d = load_optional_parquet(args.suspend_path)
    stock_basic = load_optional_parquet(args.stock_basic_path)
    stock_st = load_optional_parquet(args.stock_st_path)

    panel = build_panel(
        daily=daily,
        basic=basic,
        universe=universe,
        adj_factor=adj_factor,
        stk_limit=stk_limit,
        suspend_d=suspend_d,
        stock_basic=stock_basic,
        stock_st=stock_st,
    )
    panel.to_parquet(output_path, index=False)
    print_summary(panel)
    print(f"\nSaved panel to: {output_path}")
    return output_path


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
