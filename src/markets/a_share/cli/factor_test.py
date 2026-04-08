from __future__ import annotations

import argparse
from pathlib import Path

from ..paths import FACTOR_DIR, PANELS_DIR, PROCESSED_DIR, ensure_a_stock_dirs
from ..research.factor import (
    load_factor_panel,
    resolve_panel_path,
    run_factor_test,
    save_ic_plot,
    save_nav_plot,
)


DEFAULT_PANEL = PANELS_DIR / "hs300_panel_20150101_20241231_full.parquet"
FALLBACK_PANEL = PROCESSED_DIR / "hs300_panel_20150101_20241231.parquet"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run a cross-sectional factor group backtest.")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--factor", default="pe_ttm")
    parser.add_argument("--groups", type=int, default=5)
    parser.add_argument("--rebalance", choices=["daily", "weekly", "monthly"], default="monthly")
    parser.add_argument("--price-col", default="qfq_close")
    parser.add_argument("--start-date")
    parser.add_argument("--end-date")
    parser.add_argument("--higher-is-better", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=FACTOR_DIR)
    return parser


def run(args: argparse.Namespace) -> Path:
    ensure_a_stock_dirs()
    panel_path = resolve_panel_path(DEFAULT_PANEL, FALLBACK_PANEL, args.panel_path)
    panel, actual_price_col = load_factor_panel(
        panel_path=panel_path,
        factor_col=args.factor,
        price_col=args.price_col,
        start_date=args.start_date,
        end_date=args.end_date,
    )
    result = run_factor_test(
        panel=panel,
        factor_col=args.factor,
        n_groups=args.groups,
        rebalance_freq=args.rebalance,
        price_col=actual_price_col,
        higher_is_better=args.higher_is_better,
    )

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    result.group_returns.to_csv(output_dir / f"{args.factor}_group_returns.csv", encoding="utf-8-sig")
    result.nav.to_csv(output_dir / f"{args.factor}_group_nav.csv", encoding="utf-8-sig")
    result.memberships.to_csv(output_dir / f"{args.factor}_memberships.csv", encoding="utf-8-sig")
    result.metrics_table.to_csv(output_dir / f"{args.factor}_long_short_metrics.csv", index=False, encoding="utf-8-sig")
    result.ic_series.to_csv(output_dir / f"{args.factor}_ic_series.csv", encoding="utf-8-sig")
    result.ic_summary.to_csv(output_dir / f"{args.factor}_ic_summary.csv", index=False, encoding="utf-8-sig")

    save_nav_plot(result.nav, output_dir / f"{args.factor}_group_nav.png", f"{args.factor} Group NAV")
    save_ic_plot(result.ic_series, output_dir / f"{args.factor}_ic.png")

    print("factor test completed")
    print(f"factor: {args.factor}")
    print(f"rebalance: {args.rebalance}")
    print(f"price column: {actual_price_col}")
    print(f"output dir: {output_dir}")
    print(result.metrics_table.to_string(index=False))
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
