import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[1]
PYTHON = sys.executable


def make_trade_dates(n_days: int = 40) -> pd.DatetimeIndex:
    return pd.bdate_range("2024-01-02", periods=n_days)


def make_raw_inputs(base_dir: Path) -> tuple[Path, Path, Path]:
    raw_dir = base_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

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

    daily_path = raw_dir / "daily.parquet"
    basic_path = raw_dir / "daily_basic.parquet"
    universe_path = raw_dir / "universe.parquet"

    pd.DataFrame(daily_rows).to_parquet(daily_path, index=False)
    pd.DataFrame(basic_rows).to_parquet(basic_path, index=False)
    universe.to_parquet(universe_path, index=False)

    return daily_path, basic_path, universe_path


def make_panel(base_dir: Path) -> Path:
    daily_path, basic_path, universe_path = make_raw_inputs(base_dir)
    panel_path = base_dir / "processed" / "panel.parquet"
    panel_path.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        PYTHON,
        "scripts/a_stock/build_panel.py",
        "--daily-path",
        str(daily_path),
        "--basic-path",
        str(basic_path),
        "--universe-path",
        str(universe_path),
        "--output-path",
        str(panel_path),
    ]
    result = subprocess.run(
        cmd,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(result.stderr or result.stdout)
    return panel_path


class TestAStockScripts(unittest.TestCase):
    def test_build_panel_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            daily_path, basic_path, universe_path = make_raw_inputs(base_dir)
            output_path = base_dir / "processed" / "hs300_panel.parquet"

            result = subprocess.run(
                [
                    PYTHON,
                    "scripts/a_stock/build_panel.py",
                    "--daily-path",
                    str(daily_path),
                    "--basic-path",
                    str(basic_path),
                    "--universe-path",
                    str(universe_path),
                    "--output-path",
                    str(output_path),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue(output_path.exists())

            panel = pd.read_parquet(output_path)
            self.assertIn("pe_ttm", panel.columns)
            self.assertEqual(panel["ts_code"].nunique(), 6)
            self.assertGreaterEqual(panel["trade_date"].nunique(), 40)

    def test_backtest_ma_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            panel_path = make_panel(base_dir)
            output_dir = base_dir / "results" / "ma"

            result = subprocess.run(
                [
                    PYTHON,
                    "scripts/a_stock/backtest_ma.py",
                    "--panel-path",
                    str(panel_path),
                    "--start-date",
                    "2024-01-02",
                    "--end-date",
                    "2024-02-28",
                    "--fast",
                    "3",
                    "--slow",
                    "8",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue((output_dir / "nav.csv").exists())
            self.assertTrue((output_dir / "metrics.csv").exists())
            self.assertTrue((output_dir / "ma_3_8_nav.png").exists())

            metrics = pd.read_csv(output_dir / "metrics.csv")
            self.assertFalse(metrics.empty)

    def test_factor_test_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            panel_path = make_panel(base_dir)
            output_dir = base_dir / "results" / "factor"

            result = subprocess.run(
                [
                    PYTHON,
                    "scripts/a_stock/factor_test.py",
                    "--panel-path",
                    str(panel_path),
                    "--factor",
                    "pe_ttm",
                    "--groups",
                    "3",
                    "--rebalance",
                    "weekly",
                    "--start-date",
                    "2024-01-02",
                    "--end-date",
                    "2024-02-28",
                    "--output-dir",
                    str(output_dir),
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertTrue((output_dir / "pe_ttm_group_returns.csv").exists())
            self.assertTrue((output_dir / "pe_ttm_group_nav.csv").exists())
            self.assertTrue((output_dir / "pe_ttm_ic_summary.csv").exists())
            self.assertTrue((output_dir / "pe_ttm_ic.png").exists())

            ic_summary = pd.read_csv(output_dir / "pe_ttm_ic_summary.csv")
            self.assertIn("metric", ic_summary.columns)
            self.assertIn("value", ic_summary.columns)

    def test_data_quality_check_cli(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            base_dir = Path(tmp_dir)
            daily_path, basic_path, universe_path = make_raw_inputs(base_dir)
            panel_path = make_panel(base_dir)
            output_dir = base_dir / "results" / "data_quality"

            result = subprocess.run(
                [
                    PYTHON,
                    "scripts/a_stock/data_quality_check.py",
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
                ],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(result.returncode, 0, msg=result.stderr or result.stdout)
            self.assertIn("=== panel ===", result.stdout)
            self.assertTrue((output_dir / "coverage_by_date.csv").exists())
            self.assertTrue((output_dir / "history_by_code.csv").exists())
            self.assertTrue((output_dir / "missing_by_code.csv").exists())

            coverage = pd.read_csv(output_dir / "coverage_by_date.csv")
            self.assertIn("n_codes", coverage.columns)
            self.assertGreaterEqual(len(coverage), 30)


if __name__ == "__main__":
    unittest.main()
