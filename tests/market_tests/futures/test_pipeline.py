from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.extend([str(REPO_ROOT), str(REPO_ROOT / "src")])

from src.markets.futures.cli.build_continuous import main as build_continuous_main
from src.markets.futures.data import build_continuous_kline, load_hots_table
from src.markets.futures.research import build_etf_nav, calc_metrics


def make_hots_table(path: Path) -> Path:
    hots = pd.DataFrame(
        [
            {
                "symbol": "AL",
                "order_id": "AL2401",
                "contract_multiplier": 5,
                "hot_start_date": "2024-01-02",
                "hot_end_date": "2024-01-03",
                "commission_type": "fixed",
                "open_commission": 0.001,
                "close_commission": 0.001,
            },
            {
                "symbol": "AL",
                "order_id": "AL2402",
                "contract_multiplier": 5,
                "hot_start_date": "2024-01-04",
                "hot_end_date": "2024-01-05",
                "commission_type": "fixed",
                "open_commission": 0.001,
                "close_commission": 0.001,
            },
        ]
    )
    hots.to_csv(path, index=False)
    return path


def write_contract_csv(path: Path, dates: list[str], base_price: float) -> None:
    frame = pd.DataFrame(
        {
            "trade_date": dates,
            "open": [base_price + i for i in range(len(dates))],
            "high": [base_price + i + 0.8 for i in range(len(dates))],
            "low": [base_price + i - 0.5 for i in range(len(dates))],
            "close": [base_price + i + 0.3 for i in range(len(dates))],
            "volume": [1000 + i * 10 for i in range(len(dates))],
        }
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


class FuturesPipelineTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmpdir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmpdir.name)
        self.kline_root = self.root / "kline"
        self.hots_path = make_hots_table(self.root / "hots.csv")
        write_contract_csv(
            self.kline_root / "AL" / "AL2401.csv",
            ["2024-01-02", "2024-01-03"],
            100.0,
        )
        write_contract_csv(
            self.kline_root / "AL" / "AL2402.csv",
            ["2024-01-04", "2024-01-05"],
            103.0,
        )

    def tearDown(self) -> None:
        self.tmpdir.cleanup()

    def test_load_hots_and_build_continuous(self) -> None:
        hots = load_hots_table(self.hots_path)
        continuous, contract_map = build_continuous_kline(hots, self.kline_root, "AL")

        self.assertEqual(len(continuous), 4)
        self.assertIn("adj_close", continuous.columns)
        self.assertIn("ret_1d", continuous.columns)
        self.assertEqual(contract_map["contract"].tolist(), ["AL2401", "AL2402"])

    def test_build_etf_nav_and_metrics(self) -> None:
        hots = load_hots_table(self.hots_path)
        continuous, contract_map = build_continuous_kline(hots, self.kline_root, "AL")
        etf_nav = build_etf_nav(
            symbols=["AL"],
            hots=hots,
            contract_maps={"AL": contract_map},
            kline_root=self.kline_root,
        )
        metrics = calc_metrics(etf_nav)

        self.assertFalse(etf_nav.empty)
        self.assertIn("ann_return", metrics)
        self.assertIn("max_drawdown", metrics)
        self.assertGreater(etf_nav.iloc[-1], 0)
        self.assertEqual(len(continuous["contract"].unique()), 2)

    def test_cli_builds_report_files(self) -> None:
        out_prefix = self.root / "reports" / "al_report"
        code = build_continuous_main(
            [
                "--kline-root",
                str(self.kline_root),
                "--hots",
                str(self.hots_path),
                "--out-prefix",
                str(out_prefix),
                "--symbols",
                "AL",
            ]
        )

        self.assertEqual(code, 0)
        self.assertTrue(out_prefix.with_suffix(".csv").exists())
        self.assertTrue(out_prefix.with_suffix(".jpg").exists())
