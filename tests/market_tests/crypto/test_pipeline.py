import sys
import tempfile
import unittest
from pathlib import Path

import pandas as pd


REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.extend([str(REPO_ROOT), str(REPO_ROOT / "src")])

from markets.crypto import build_crypto_panel, generate_ma_signals, normalize_crypto_ohlcv, save_crypto_panel


def make_okx_like_frame() -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=40, freq="D")
    rows = []
    for idx, trade_date in enumerate(dates):
        rows.append(
            {
                "ts": trade_date,
                "open": 100 + idx,
                "high": 101 + idx,
                "low": 99 + idx,
                "close": 100.5 + idx,
                "volume": 1000 + idx,
                "source": "okx_rest",
                "symbol": "BTC-USDT",
                "bar": "1D",
            }
        )
    return pd.DataFrame(rows)


class TestCryptoPipeline(unittest.TestCase):
    def test_loader_normalizes_columns(self) -> None:
        raw = make_okx_like_frame()
        normalized = normalize_crypto_ohlcv(raw)

        self.assertIn("ts_code", normalized.columns)
        self.assertIn("trade_date", normalized.columns)
        self.assertEqual(normalized["ts_code"].nunique(), 1)

    def test_build_crypto_panel_adds_research_fields(self) -> None:
        raw = make_okx_like_frame()
        panel = build_crypto_panel(raw)

        self.assertIn("ret_1d", panel.columns)
        self.assertIn("ret_5d", panel.columns)
        self.assertIn("volatility_20d", panel.columns)
        self.assertEqual(len(panel), 40)

    def test_generate_ma_signals_runs(self) -> None:
        raw = make_okx_like_frame()
        panel = build_crypto_panel(raw)
        signals = generate_ma_signals(panel, fast_period=3, slow_period=8)

        self.assertIn("signal", signals.columns)
        self.assertEqual(len(signals), len(panel))

    def test_panel_can_be_saved(self) -> None:
        raw = make_okx_like_frame()
        panel = build_crypto_panel(raw)

        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "crypto_panel.parquet"
            saved_path = save_crypto_panel(panel, output_path=output_path)
            self.assertTrue(saved_path.exists())
            reloaded = pd.read_parquet(saved_path)

        self.assertEqual(len(reloaded), len(panel))


if __name__ == "__main__":
    unittest.main()
