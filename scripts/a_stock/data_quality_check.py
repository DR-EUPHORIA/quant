import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


DATA_ROOT = ROOT / "data" / "tushare"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"
RESULTS_DIR = ROOT / "results" / "a_stock" / "data_quality"

DEFAULT_DAILY = RAW_DIR / "daily_20150101_20241231.parquet"
DEFAULT_BASIC = RAW_DIR / "daily_basic_20150101_20241231.parquet"
DEFAULT_UNIVERSE = RAW_DIR / "000300_sh_index_weight_20150101_20241231.parquet"
FALLBACK_UNIVERSE = RAW_DIR / "hs300_constituents_latest.parquet"
DEFAULT_PANEL = PROCESSED_DIR / "hs300_panel_20150101_20241231_full.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A 股研究数据质量检查")
    parser.add_argument("--daily-path", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--basic-path", type=Path, default=DEFAULT_BASIC)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR)
    parser.add_argument("--save-csv", action="store_true", help="将明细结果保存为 CSV")
    return parser.parse_args()


def load_parquet(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name} 文件不存在: {path}")
    return pd.read_parquet(path)


def resolve_universe_path(path: Path) -> Path:
    if path.exists():
        return path
    if path == DEFAULT_UNIVERSE and FALLBACK_UNIVERSE.exists():
        return FALLBACK_UNIVERSE
    return path


def normalize_trade_date(df: pd.DataFrame) -> pd.Series:
    if "trade_date" not in df.columns:
        return pd.Series(dtype="datetime64[ns]")
    out = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    return out.fillna(pd.to_datetime(df["trade_date"], errors="coerce"))


def print_dataset_summary(name: str, df: pd.DataFrame, key_cols: list[str]) -> None:
    print(f"\n=== {name} ===")
    print(f"shape: {df.shape}")
    if "trade_date" in df.columns:
        td = normalize_trade_date(df)
        print(f"date_range: {td.min()} -> {td.max()} (n_dates={td.nunique()})")
    if all(col in df.columns for col in key_cols):
        print(f"duplicate {tuple(key_cols)}: {df.duplicated(key_cols).sum()}")
    if "ts_code" in df.columns:
        print(f"n_ts_code: {df['ts_code'].nunique()}")
    if "con_code" in df.columns:
        print(f"n_con_code: {df['con_code'].nunique()}")
    print("top missing ratios:")
    print(df.isna().mean().sort_values(ascending=False).head(8).to_string())


def latest_universe_gap(panel: pd.DataFrame, universe: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["trade_date"] = normalize_trade_date(panel)
    daily = daily.copy()
    daily["trade_date"] = normalize_trade_date(daily)

    latest_date = panel["trade_date"].max()
    latest_codes = set(panel.loc[panel["trade_date"] == latest_date, "ts_code"])

    if "trade_date" in universe.columns:
        universe = universe.copy()
        universe["trade_date"] = normalize_trade_date(universe)
        if universe["trade_date"].nunique() > 1:
            universe_codes = set(universe.loc[universe["trade_date"] == latest_date, "con_code"])
        else:
            universe_codes = set(universe["con_code"])
    else:
        universe_codes = set(universe["con_code"])

    missing_codes = sorted(universe_codes - latest_codes)

    rows = []
    for code in missing_codes:
        code_daily = daily.loc[daily["ts_code"] == code, "trade_date"]
        rows.append(
            {
                "ts_code": code,
                "panel_latest_date": latest_date,
                "daily_last_date": code_daily.max() if not code_daily.empty else pd.NaT,
            }
        )
    return pd.DataFrame(rows)


def per_code_missing(panel: pd.DataFrame) -> pd.DataFrame:
    fields = [
        "close", "turnover_rate", "turnover_rate_f", "pe", "pe_ttm",
        "pb", "ps", "ps_ttm", "total_mv", "circ_mv", "free_share",
        "adj_factor", "qfq_close", "limit_up", "limit_down",
    ]
    rows = []
    for code, group in panel.groupby("ts_code"):
        row = {"ts_code": code, "rows": len(group)}
        for field in fields:
            if field in group.columns:
                row[f"miss_{field}"] = group[field].isna().mean()
        rows.append(row)
    return pd.DataFrame(rows).sort_values("rows")


def coverage_by_date(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["trade_date"] = normalize_trade_date(panel)
    counts = panel.groupby("trade_date")["ts_code"].nunique().rename("n_codes")
    return counts.reset_index().sort_values("trade_date")


def history_by_code(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["trade_date"] = normalize_trade_date(panel)
    history = panel.groupby("ts_code").agg(
        rows=("trade_date", "size"),
        start_date=("trade_date", "min"),
        end_date=("trade_date", "max"),
    )
    return history.reset_index().sort_values(["rows", "ts_code"])


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")


def main() -> None:
    args = parse_args()
    universe_path = resolve_universe_path(args.universe_path)
    daily = load_parquet(args.daily_path, "daily")
    basic = load_parquet(args.basic_path, "daily_basic")
    universe = load_parquet(universe_path, "universe")
    panel = load_parquet(args.panel_path, "panel")

    print_dataset_summary("daily", daily, ["ts_code", "trade_date"])
    print_dataset_summary("daily_basic", basic, ["ts_code", "trade_date"])
    print_dataset_summary("universe", universe, ["con_code", "trade_date"])
    print_dataset_summary("panel", panel, ["ts_code", "trade_date"])

    latest_gap = latest_universe_gap(panel, universe, daily)
    missing_summary = per_code_missing(panel)
    coverage = coverage_by_date(panel)
    history = history_by_code(panel)

    print("\n=== Latest Universe Gap ===")
    if latest_gap.empty:
        print("latest panel coverage matches universe")
    else:
        print(latest_gap.to_string(index=False))

    print("\n=== Lowest Coverage Dates ===")
    print(coverage.nsmallest(10, "n_codes").to_string(index=False))

    print("\n=== Highest Coverage Dates ===")
    print(coverage.nlargest(10, "n_codes").sort_values("trade_date").to_string(index=False))

    print("\n=== Shortest Histories ===")
    print(history.head(15).to_string(index=False))

    print("\n=== Worst Missing PE_TTM ===")
    cols = ["ts_code", "rows", "miss_pe_ttm", "miss_pe"]
    print(missing_summary.sort_values("miss_pe_ttm", ascending=False).head(10)[cols].to_string(index=False))

    print("\n=== Worst Missing Total_MV ===")
    cols = ["ts_code", "rows", "miss_total_mv", "miss_turnover_rate"]
    print(missing_summary.sort_values("miss_total_mv", ascending=False).head(10)[cols].to_string(index=False))

    derived_fields = [
        "adj_factor", "qfq_close", "qfq_open", "qfq_high", "qfq_low",
        "limit_up", "limit_down", "is_limit_up", "is_limit_down",
        "listed_days", "is_new_listing_60d", "is_tradeable_buy", "is_tradeable_sell",
        "ret_1d", "ret_5d", "ret_20d", "volatility_20d",
        "amount_ma20_ratio", "turnover_rate_ma20_ratio",
    ]
    available = [field for field in derived_fields if field in panel.columns]
    if available:
        print("\n=== Derived Field Missing Ratios ===")
        print(panel[available].isna().mean().sort_values(ascending=False).to_string())

    if args.save_csv:
        save_csv(latest_gap, args.output_dir / "latest_universe_gap.csv")
        save_csv(coverage, args.output_dir / "coverage_by_date.csv")
        save_csv(history, args.output_dir / "history_by_code.csv")
        save_csv(missing_summary, args.output_dir / "missing_by_code.csv")
        print(f"\nCSV 已写出到: {args.output_dir}")


if __name__ == "__main__":
    main()
