from __future__ import annotations

import argparse
from pathlib import Path

from ..data import load_parquet
from ..data.panel import DEFAULT_BASIC, DEFAULT_DAILY
from ..paths import DATA_QUALITY_DIR, PANELS_DIR, RAW_DIR, ensure_a_stock_dirs
from ..research.quality import build_quality_report, print_dataset_summary, resolve_panel_path, save_csv
from ..universe import DEFAULT_UNIVERSE, FALLBACK_UNIVERSE


DEFAULT_PANEL = PANELS_DIR / "hs300_panel_20150101_20241231_full.parquet"
FALLBACK_PANEL = RAW_DIR.parent / "processed" / "hs300_panel_20150101_20241231.parquet"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run A-share data quality checks.")
    parser.add_argument("--daily-path", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--basic-path", type=Path, default=DEFAULT_BASIC)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--output-dir", type=Path, default=DATA_QUALITY_DIR)
    parser.add_argument("--save-csv", action="store_true")
    return parser


def resolve_universe_path(path: Path) -> Path:
    if path.exists():
        return path
    if path == DEFAULT_UNIVERSE and FALLBACK_UNIVERSE.exists():
        return FALLBACK_UNIVERSE
    return path


def run(args: argparse.Namespace) -> Path:
    ensure_a_stock_dirs()
    universe_path = resolve_universe_path(args.universe_path)
    panel_path = resolve_panel_path(DEFAULT_PANEL, FALLBACK_PANEL, args.panel_path)

    daily = load_parquet(args.daily_path, "daily")
    basic = load_parquet(args.basic_path, "daily_basic")
    universe = load_parquet(universe_path, "universe")
    panel = load_parquet(panel_path, "panel")

    print_dataset_summary("daily", daily, ["ts_code", "trade_date"])
    print_dataset_summary("daily_basic", basic, ["ts_code", "trade_date"])
    print_dataset_summary("universe", universe, ["con_code", "trade_date"])
    print_dataset_summary("panel", panel, ["ts_code", "trade_date"])

    report = build_quality_report(panel=panel, universe=universe, daily=daily)

    print("\n=== Latest Universe Gap ===")
    print("latest panel coverage matches universe" if report.latest_gap.empty else report.latest_gap.to_string(index=False))

    print("\n=== Lowest Coverage Dates ===")
    print(report.coverage_by_date.nsmallest(min(10, len(report.coverage_by_date)), "n_codes").to_string(index=False))

    print("\n=== Shortest Histories ===")
    print(report.history_by_code.head(15).to_string(index=False))

    if not report.missing_summary.empty:
        miss_pe_cols = [col for col in ["ts_code", "rows", "miss_pe_ttm", "miss_pe"] if col in report.missing_summary.columns]
        print("\n=== Worst Missing PE_TTM ===")
        print(report.missing_summary.sort_values("miss_pe_ttm", ascending=False).head(10)[miss_pe_cols].to_string(index=False))

    if not report.bool_coverage.empty:
        print("\n=== Tradeability Field Coverage ===")
        print(report.bool_coverage.to_string(index=False))

    output_dir = args.output_dir
    if args.save_csv:
        save_csv(report.latest_gap, output_dir / "latest_universe_gap.csv")
        save_csv(report.coverage_by_date, output_dir / "coverage_by_date.csv")
        save_csv(report.history_by_code, output_dir / "history_by_code.csv")
        save_csv(report.missing_summary, output_dir / "missing_by_code.csv")
        if not report.bool_coverage.empty:
            save_csv(report.bool_coverage, output_dir / "tradeability_field_coverage.csv")
        if not report.tradeability_by_date.empty:
            save_csv(report.tradeability_by_date, output_dir / "tradeability_by_date.csv")
        if not report.tradeability_by_code.empty:
            save_csv(report.tradeability_by_code, output_dir / "tradeability_by_code.csv")
        print(f"\nCSV written to: {output_dir}")
    return output_dir


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    run(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
