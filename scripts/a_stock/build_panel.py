import argparse
import sys
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.append(str(ROOT))


DATA_ROOT = ROOT / "data" / "tushare"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"

DEFAULT_DAILY = RAW_DIR / "daily_20150101_20241231.parquet"
DEFAULT_BASIC = RAW_DIR / "daily_basic_20150101_20241231.parquet"
DEFAULT_UNIVERSE = RAW_DIR / "hs300_constituents_latest.parquet"
DEFAULT_OUTPUT = PROCESSED_DIR / "hs300_panel_20150101_20241231.parquet"
FALLBACK_OUTPUT = ROOT / "results" / "a_stock" / "panels" / "hs300_panel_20150101_20241231.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="构建沪深300研究面板（行情 + daily_basic -> parquet）"
    )
    parser.add_argument("--daily-path", type=Path, default=DEFAULT_DAILY)
    parser.add_argument("--basic-path", type=Path, default=DEFAULT_BASIC)
    parser.add_argument("--universe-path", type=Path, default=DEFAULT_UNIVERSE)
    parser.add_argument("--output-path", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def load_parquet(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name} 文件不存在: {path}")
    df = pd.read_parquet(path)
    if df.empty:
        raise ValueError(f"{name} 为空: {path}")
    return df


def normalize_trade_date(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce")
    if out["trade_date"].isna().any():
        out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    if out["trade_date"].isna().any():
        raise ValueError("存在无法解析的 trade_date")
    return out


def validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{name} 缺少必要列: {missing}")


def build_panel(daily: pd.DataFrame, basic: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    validate_columns(daily, ["ts_code", "trade_date", "open", "high", "low", "close"], "daily")
    validate_columns(basic, ["ts_code", "trade_date"], "daily_basic")
    validate_columns(universe, ["con_code"], "universe")

    daily = normalize_trade_date(daily)
    basic = normalize_trade_date(basic)
    universe = normalize_trade_date(universe) if "trade_date" in universe.columns else universe.copy()

    daily = daily.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
    basic = basic.drop_duplicates(subset=["ts_code", "trade_date"], keep="last")

    hs300_codes = sorted(universe["con_code"].dropna().unique().tolist())
    if not hs300_codes:
        raise ValueError("成分股列表为空")

    daily = daily[daily["ts_code"].isin(hs300_codes)].copy()
    basic = basic[basic["ts_code"].isin(hs300_codes)].copy()

    panel = pd.merge(
        daily,
        basic,
        on=["ts_code", "trade_date"],
        how="left",
        suffixes=("", "_basic"),
    )

    panel = panel.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)

    duplicated = panel.duplicated(subset=["ts_code", "trade_date"]).sum()
    if duplicated:
        raise ValueError(f"面板主键重复: {duplicated}")

    return panel


def print_summary(panel: pd.DataFrame) -> None:
    start_date = panel["trade_date"].min().date()
    end_date = panel["trade_date"].max().date()
    n_codes = panel["ts_code"].nunique()
    n_rows = len(panel)
    print(f"面板行数: {n_rows:,}")
    print(f"股票数: {n_codes}")
    print(f"日期范围: {start_date} -> {end_date}")
    null_ratio = panel.isna().mean().sort_values(ascending=False).head(10)
    print("\n缺失率最高的字段（Top 10）:")
    print(null_ratio.to_string())


def resolve_output_path(desired_path: Path) -> Path:
    desired_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(desired_path, "ab"):
            pass
        desired_path.unlink(missing_ok=True)
        return desired_path
    except OSError:
        FALLBACK_OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        return FALLBACK_OUTPUT


def main() -> None:
    args = parse_args()
    output_path = resolve_output_path(args.output_path)

    daily = load_parquet(args.daily_path, "daily")
    basic = load_parquet(args.basic_path, "daily_basic")
    universe = load_parquet(args.universe_path, "universe")

    panel = build_panel(daily, basic, universe)
    panel.to_parquet(output_path, index=False)

    print(f"已写出面板: {output_path}")
    print_summary(panel)


if __name__ == "__main__":
    main()
