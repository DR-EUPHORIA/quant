from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd

from quantbt import BacktestEngine, MASignalGenerator, PositionBuilder, ReturnCalculator, save_results

from ..data.panel import DEFAULT_OUTPUT
from ..paths import BACKTESTS_DIR, ensure_a_stock_dirs


DEFAULT_PANEL = DEFAULT_OUTPUT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a moving-average backtest on an A-share panel.")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--output-dir", type=Path, default=BACKTESTS_DIR / "ma_strategy")
    parser.add_argument("--price-col", default="qfq_close")
    parser.add_argument("--fast-period", type=int, default=5)
    parser.add_argument("--slow-period", type=int, default=20)
    parser.add_argument("--rebalance-freq", choices=["daily", "weekly", "monthly"], default="daily")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--apply-cost", action="store_true")
    return parser


def _load_panel(panel_path: Path, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    if not panel_path.exists():
        raise FileNotFoundError(f"panel file does not exist: {panel_path}")

    panel = pd.read_parquet(panel_path)
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    if start_date is not None:
        panel = panel.loc[panel["trade_date"] >= pd.to_datetime(start_date)]
    if end_date is not None:
        panel = panel.loc[panel["trade_date"] <= pd.to_datetime(end_date)]

    if panel.empty:
        raise ValueError("panel is empty after date filtering")

    return panel


def run(args: argparse.Namespace) -> Path:
    ensure_a_stock_dirs()
    panel = _load_panel(args.panel_path, args.start_date, args.end_date)

    if args.price_col not in panel.columns:
        raise ValueError(f"price column not found in panel: {args.price_col}")

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    engine = BacktestEngine(
        data=panel,
        signal_generator=MASignalGenerator(
            fast_period=args.fast_period,
            slow_period=args.slow_period,
            price_col=args.price_col,
        ),
        position_builder=PositionBuilder(rebalance_freq=args.rebalance_freq),
        return_calculator=ReturnCalculator(price_col=args.price_col),
    )
    result = engine.run(apply_cost=args.apply_cost)

    save_results(
        {
            "nav": result.nav.rename("nav").to_frame(),
            "returns": result.returns.rename("returns").to_frame(),
            "positions": result.positions,
            "turnover": result.turnover.rename("turnover").to_frame(),
            "metrics": result.metrics,
        },
        output_dir=output_dir,
        name="ma_backtest",
        format="csv",
    )

    summary_path = output_dir / "ma_backtest_summary.csv"
    result.summary().to_csv(summary_path, index=False, encoding="utf-8-sig")

    print(result.summary().to_string(index=False))
    print(f"\nSaved backtest outputs to: {output_dir}")
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
