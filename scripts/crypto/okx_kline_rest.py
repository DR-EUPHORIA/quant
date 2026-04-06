import argparse
import sys
from pathlib import Path

import matplotlib.pyplot as plt


ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT), str(ROOT / "src")])

from quantcrypto import fetch_okx_candles, save_okx_candles_csv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch crypto candles from OKX REST API")
    parser.add_argument("--inst-id", default="BTC-USDT")
    parser.add_argument("--bar", default="1D")
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--output-path", type=Path, default=None)
    parser.add_argument("--no-plot", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    df = fetch_okx_candles(inst_id=args.inst_id, bar=args.bar, limit=args.limit)
    print(df.head())

    output_path = save_okx_candles_csv(df, inst_id=args.inst_id, bar=args.bar, output_path=args.output_path)
    print(f"数据已保存到 {output_path}")

    if not args.no_plot and not df.empty:
        plt.plot(df["ts"], df["close"])
        plt.title(f"OKX {args.inst_id} {args.bar} Candles")
        plt.xlabel("Time")
        plt.ylabel("Close Price")
        plt.tight_layout()
        plt.show()


if __name__ == "__main__":
    main()
