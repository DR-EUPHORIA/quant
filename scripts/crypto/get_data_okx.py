import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT), str(ROOT / "src")])

from quantcrypto import CRYPTO_RAW_DIR, ensure_crypto_dirs


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch crypto candles from OKX via ccxt")
    parser.add_argument("--symbol", default="BTC/USDT")
    parser.add_argument("--timeframe", default="1d")
    parser.add_argument("--limit", type=int, default=500)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--no-plot", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    import ccxt

    exchange = ccxt.okx(
        {
            "enableRateLimit": True,
            "timeout": 20000,
            "options": {"defaultType": "spot"},
        }
    )

    markets = exchange.load_markets()
    print("OKX markets loaded, total symbols:", len(markets))

    bars = exchange.fetch_ohlcv(args.symbol, timeframe=args.timeframe, limit=args.limit)
    df = pd.DataFrame(bars, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
    df["source"] = "okx_ccxt"
    df["symbol"] = args.symbol
    df["timeframe"] = args.timeframe
    print(df.head())

    ensure_crypto_dirs()
    output_path = args.output_path or CRYPTO_RAW_DIR / (
        f"okx_ccxt_{args.symbol.lower().replace('/', '_')}_{args.timeframe}.csv"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"数据已保存到 {output_path}")

    if not args.no_plot and not df.empty:
        plt.plot(df["timestamp"], df["close"])
        plt.title(f"OKX {args.symbol} Close Price ({args.timeframe})")
        plt.xlabel("Date")
        plt.ylabel("Close")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
