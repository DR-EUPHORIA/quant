import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.extend([str(REPO_ROOT), str(REPO_ROOT / "src")])

from markets.a_share import build_panel
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


if __name__ == "__main__":
    unittest.main()
