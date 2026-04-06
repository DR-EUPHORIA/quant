import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT), str(ROOT / "src")])

from quantcrypto import CRYPTO_RAW_DIR, ensure_crypto_dirs, fetch_yahoo_ohlcv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch crypto OHLCV data from Yahoo Finance")
    parser.add_argument("--ticker", default="BTC-USD")
    parser.add_argument("--start", default="2022-01-01")
    parser.add_argument("--interval", default="1d")
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--no-plot", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data = fetch_yahoo_ohlcv(ticker=args.ticker, start=args.start, interval=args.interval)
    print(data.head())

    ensure_crypto_dirs()
    output_path = args.output_path or CRYPTO_RAW_DIR / f"yahoo_{args.ticker.lower().replace('-', '_')}_{args.interval}.csv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"数据已保存到 {output_path}")

    if not args.no_plot and not data.empty:
        plt.plot(data["timestamp"], data["close"])
        plt.title(f"{args.ticker} Close Price (Yahoo Finance)")
        plt.xlabel("Date")
        plt.ylabel("Close")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
