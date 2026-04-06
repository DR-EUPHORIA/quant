import argparse
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT), str(ROOT / "src")])

from quanta_stock import (
    build_panel,
    load_optional_parquet,
    load_parquet,
    resolve_output_path,
    resolve_universe_path,
)
from quanta_stock.panel import (
    DEFAULT_ADJ_FACTOR,
    DEFAULT_BASIC,
    DEFAULT_DAILY,
    DEFAULT_OUTPUT,
    DEFAULT_STK_LIMIT,
    DEFAULT_STOCK_BASIC,
    DEFAULT_STOCK_ST,
    DEFAULT_SUSPEND_D,
    DEFAULT_UNIVERSE,
    print_summary,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="构建沪深300研究面板（行情 + daily_basic -> parquet）")
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
