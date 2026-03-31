import argparse
import sys
from pathlib import Path

import matplotlib
import pandas as pd


matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT), str(ROOT / "src")])

from quantbt import (
    BacktestEngine,
    MASignalGenerator,
    ReturnCalculator,
    create_simple_cost_model,
    generate_report,
)


DATA_ROOT = ROOT / "data" / "tushare"
PROCESSED_DIR = DATA_ROOT / "processed"
RESULTS_DIR = ROOT / "results" / "a_stock"
DEFAULT_PANEL = PROCESSED_DIR / "hs300_panel_20150101_20241231_full.parquet"
FALLBACK_PANEL = RESULTS_DIR / "panels" / "hs300_panel_20150101_20241231_full.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行沪深300 MA 策略回测")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--fast", type=int, default=5)
    parser.add_argument("--slow", type=int, default=20)
    parser.add_argument("--price-col", type=str, default="qfq_close")
    parser.add_argument("--cost-bps", type=float, default=20.0)
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR / "ma")
    return parser.parse_args()


def resolve_panel_path(panel_path: Path) -> Path:
    if panel_path == DEFAULT_PANEL and FALLBACK_PANEL.exists():
        if not panel_path.exists():
            return FALLBACK_PANEL
        if FALLBACK_PANEL.stat().st_mtime >= panel_path.stat().st_mtime:
            return FALLBACK_PANEL
    return panel_path


def load_panel(panel_path: Path, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    return load_panel_with_price(panel_path, start_date, end_date, price_col="close")


def load_panel_with_price(
    panel_path: Path,
    start_date: str | None,
    end_date: str | None,
    price_col: str,
) -> pd.DataFrame:
    panel_path = resolve_panel_path(panel_path)
    if not panel_path.exists():
        raise FileNotFoundError(f"面板文件不存在: {panel_path}")

    cols = [
        "ts_code",
        "trade_date",
        "close",
        "open",
        "high",
        "low",
        "vol",
        "amount",
        "is_tradeable_buy",
        "is_tradeable_sell",
    ]
    if price_col not in cols:
        cols.append(price_col)
    panel = pd.read_parquet(panel_path, columns=cols)
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    if start_date:
        panel = panel[panel["trade_date"] >= pd.to_datetime(start_date)]
    if end_date:
        panel = panel[panel["trade_date"] <= pd.to_datetime(end_date)]

    if price_col not in panel.columns:
        if price_col == "qfq_close" and "close" in panel.columns:
            print("警告: 面板缺少 qfq_close，已回退到 close")
            price_col = "close"
        else:
            raise ValueError(f"面板中不存在价格列: {price_col}")

    panel = panel.dropna(subset=["ts_code", "trade_date", price_col])
    panel = panel.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)

    if panel.empty:
        raise ValueError("过滤后面板为空")

    return panel


def save_tabular_outputs(result, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    result.nav.rename("nav").to_csv(output_dir / "nav.csv", encoding="utf-8-sig")
    result.returns.rename("returns").to_csv(output_dir / "returns.csv", encoding="utf-8-sig")
    result.positions.to_csv(output_dir / "positions.csv", encoding="utf-8-sig")
    result.summary().to_csv(output_dir / "metrics.csv", index=False, encoding="utf-8-sig")


def print_data_summary(panel: pd.DataFrame) -> None:
    n_dates = panel["trade_date"].nunique()
    n_codes = panel["ts_code"].nunique()
    start_date = panel["trade_date"].min().date()
    end_date = panel["trade_date"].max().date()
    print(f"样本区间: {start_date} -> {end_date}")
    print(f"交易日数: {n_dates}")
    print(f"股票数: {n_codes}")
    if n_dates < 30:
        print("警告: 交易日样本过少，绩效指标参考意义有限。")


def main() -> None:
    args = parse_args()
    panel = load_panel_with_price(args.panel_path, args.start_date, args.end_date, args.price_col)
    print_data_summary(panel)

    actual_price_col = args.price_col if args.price_col in panel.columns else "close"

    signal_gen = MASignalGenerator(
        fast_period=args.fast,
        slow_period=args.slow,
        price_col=actual_price_col,
    )
    return_calculator = ReturnCalculator(price_col=actual_price_col)
    cost_model = create_simple_cost_model(
        commission_bps=args.cost_bps / 4,
        stamp_duty_bps=args.cost_bps / 4,
        slippage_bps=args.cost_bps / 2,
    )

    engine = BacktestEngine(
        data=panel,
        signal_generator=signal_gen,
        return_calculator=return_calculator,
        cost_model=cost_model,
    )
    result = engine.run()

    save_tabular_outputs(result, args.output_dir)
    generate_report(
        nav=result.nav,
        returns=result.returns,
        metrics=result.metrics,
        output_dir=args.output_dir,
        name=f"ma_{args.fast}_{args.slow}",
        positions=result.positions,
    )

    print("MA 回测完成")
    print(f"输出目录: {args.output_dir}")
    print(f"价格列: {actual_price_col}")
    print(result.summary().to_string(index=False))
    print(f"交易次数: {result.trade_count}")
    annualized_turnover = result.annualized_turnover
    if pd.isna(annualized_turnover):
        print("年化换手率: NaN (样本不足)")
    else:
        print(f"年化换手率: {annualized_turnover:.4f}")


if __name__ == "__main__":
    main()
