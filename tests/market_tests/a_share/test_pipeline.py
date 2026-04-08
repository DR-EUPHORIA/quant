import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.extend([str(REPO_ROOT), str(REPO_ROOT / "src")])

from markets.a_share import build_panel
from markets.a_share.cli.backtest_ma import main as backtest_ma_main
from markets.a_share.cli.build_panel import main as build_panel_main
from markets.a_share.cli.data_quality_check import main as data_quality_check_main
from markets.a_share.cli.factor_test import main as factor_test_main
from quantbt import BacktestEngine, MASignalGenerator, ReturnCalculator


def make_trade_dates(n_days: int = 40) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=n_days)


def make_raw_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    dates = make_trade_dates()
    codes = [f"00000{i}.SZ" for i in range(1, 7)]

    daily_rows = []
    basic_rows = []
    for code_idx, code in enumerate(codes, start=1):
        base_price = 10 + code_idx
        for day_idx, trade_date in enumerate(dates):
            close = base_price + day_idx * 0.1 + code_idx * 0.05
            open_price = close - 0.05
            high = close + 0.1
            low = close - 0.1
            pre_close = close - 0.08
            daily_rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date.strftime("%Y%m%d"),
                    "open": round(open_price, 4),
                    "high": round(high, 4),
                    "low": round(low, 4),
                    "close": round(close, 4),
                    "pre_close": round(pre_close, 4),
                    "change": round(close - pre_close, 4),
                    "pct_chg": round((close / pre_close - 1) * 100, 4),
                    "vol": 100000 + day_idx * 100 + code_idx,
                    "amount": round(close * (100000 + day_idx * 100 + code_idx), 4),
                }
            )
            basic_rows.append(
                {
                    "ts_code": code,
                    "trade_date": trade_date.strftime("%Y%m%d"),
                    "turnover_rate": 1.0 + code_idx * 0.1,
                    "turnover_rate_f": 1.2 + code_idx * 0.1,
                    "pe": 8 + code_idx + day_idx * 0.02,
                    "pe_ttm": 10 + code_idx + day_idx * 0.03,
                    "pb": 1.5 + code_idx * 0.05,
                    "ps": 2.0 + code_idx * 0.05,
                    "ps_ttm": 2.1 + code_idx * 0.05,
                    "total_share": 1000000 + code_idx * 1000,
                    "float_share": 800000 + code_idx * 1000,
                    "free_share": 700000 + code_idx * 1000,
                    "total_mv": close * (1000000 + code_idx * 1000),
                    "circ_mv": close * (800000 + code_idx * 1000),
                }
            )

    universe = pd.DataFrame(
        {
            "index_code": ["000300.SH"] * len(codes),
            "con_code": codes,
            "trade_date": [dates[-1].strftime("%Y%m%d")] * len(codes),
            "weight": [round(100 / len(codes), 4)] * len(codes),
        }
    )

    return pd.DataFrame(daily_rows), pd.DataFrame(basic_rows), universe


def make_panel() -> pd.DataFrame:
    daily, basic, universe = make_raw_frames()
    return build_panel(daily, basic, universe)


class TestASharePipeline(unittest.TestCase):
    def test_build_panel_module(self) -> None:
        panel = make_panel()

        self.assertIn("pe_ttm", panel.columns)
        self.assertIn("is_tradeable_buy", panel.columns)
        self.assertIn("is_tradeable_sell", panel.columns)
        self.assertEqual(panel["ts_code"].nunique(), 6)
        self.assertGreaterEqual(panel["trade_date"].nunique(), 40)

    def test_panel_can_be_written_to_parquet(self) -> None:
        panel = make_panel()

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "panel.parquet"
            panel.to_parquet(output_path, index=False)
            reloaded = pd.read_parquet(output_path)

        self.assertEqual(len(reloaded), len(panel))
        self.assertIn("pe_ttm", reloaded.columns)

    def test_backtest_engine_runs_with_a_share_panel(self) -> None:
        panel = make_panel()
        engine = BacktestEngine(
            data=panel,
            signal_generator=MASignalGenerator(fast_period=3, slow_period=8, price_col="close"),
            return_calculator=ReturnCalculator(price_col="close"),
        )

        result = engine.run()

        self.assertEqual(len(result.nav), panel["trade_date"].nunique())
        self.assertTrue((result.positions.columns == sorted(panel["ts_code"].unique())).all())
        self.assertIn("annual_return", result.metrics)
        self.assertFalse(result.summary().empty)

    def test_panel_supports_factor_research_fields(self) -> None:
        panel = make_panel()

        required_cols = {
            "pe_ttm",
            "ret_1d",
            "ret_5d",
            "ret_20d",
            "volatility_20d",
            "listed_days",
            "is_new_listing_60d",
        }
        self.assertTrue(required_cols.issubset(panel.columns))

        factor_slice = panel.dropna(subset=["pe_ttm"]).copy()
        coverage = factor_slice.groupby("trade_date")["ts_code"].nunique()
        self.assertGreaterEqual(int(coverage.min()), 6)

    def test_build_panel_cli_runs(self) -> None:
        daily, basic, universe = make_raw_frames()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            daily_path = tmp_path / "daily.parquet"
            basic_path = tmp_path / "basic.parquet"
            universe_path = tmp_path / "universe.parquet"
            output_path = tmp_path / "panel.parquet"

            daily.to_parquet(daily_path, index=False)
            basic.to_parquet(basic_path, index=False)
            universe.to_parquet(universe_path, index=False)

            exit_code = build_panel_main(
                [
                    "--daily-path",
                    str(daily_path),
                    "--basic-path",
                    str(basic_path),
                    "--universe-path",
                    str(universe_path),
                    "--output-path",
                    str(output_path),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue(output_path.exists())

    def test_backtest_ma_cli_runs(self) -> None:
        panel = make_panel()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            panel_path = tmp_path / "panel.parquet"
            output_dir = tmp_path / "backtest"
            panel.to_parquet(panel_path, index=False)

            exit_code = backtest_ma_main(
                [
                    "--panel-path",
                    str(panel_path),
                    "--output-dir",
                    str(output_dir),
                    "--price-col",
                    "close",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "ma_backtest_nav.csv").exists())
            self.assertTrue((output_dir / "ma_backtest_metrics.json").exists())
            self.assertTrue((output_dir / "ma_backtest_summary.csv").exists())

    def test_factor_test_cli_runs(self) -> None:
        panel = make_panel()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            panel_path = tmp_path / "panel.parquet"
            output_dir = tmp_path / "factor"
            panel.to_parquet(panel_path, index=False)

            exit_code = factor_test_main(
                [
                    "--panel-path",
                    str(panel_path),
                    "--factor",
                    "pe_ttm",
                    "--groups",
                    "3",
                    "--rebalance",
                    "weekly",
                    "--price-col",
                    "close",
                    "--output-dir",
                    str(output_dir),
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "pe_ttm_group_nav.csv").exists())
            self.assertTrue((output_dir / "pe_ttm_long_short_metrics.csv").exists())
            self.assertTrue((output_dir / "pe_ttm_ic_series.csv").exists())

    def test_data_quality_check_cli_runs(self) -> None:
        daily, basic, universe = make_raw_frames()
        panel = make_panel()

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)
            daily_path = tmp_path / "daily.parquet"
            basic_path = tmp_path / "basic.parquet"
            universe_path = tmp_path / "universe.parquet"
            panel_path = tmp_path / "panel.parquet"
            output_dir = tmp_path / "quality"

            daily.to_parquet(daily_path, index=False)
            basic.to_parquet(basic_path, index=False)
            universe.to_parquet(universe_path, index=False)
            panel.to_parquet(panel_path, index=False)

            exit_code = data_quality_check_main(
                [
                    "--daily-path",
                    str(daily_path),
                    "--basic-path",
                    str(basic_path),
                    "--universe-path",
                    str(universe_path),
                    "--panel-path",
                    str(panel_path),
                    "--output-dir",
                    str(output_dir),
                    "--save-csv",
                ]
            )

            self.assertEqual(exit_code, 0)
            self.assertTrue((output_dir / "coverage_by_date.csv").exists())
            self.assertTrue((output_dir / "history_by_code.csv").exists())
            self.assertTrue((output_dir / "missing_by_code.csv").exists())


if __name__ == "__main__":
    unittest.main()
