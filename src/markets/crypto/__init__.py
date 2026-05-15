"""Crypto market package."""

from .data import build_crypto_panel, normalize_crypto_ohlcv, save_crypto_panel
from .paths import CRYPTO_DATA_ROOT, CRYPTO_PROCESSED_DIR, CRYPTO_RAW_DIR, ensure_crypto_dirs
from .research import generate_ma_signals


def fetch_okx_candles(*args, **kwargs):
    from .providers.okx import fetch_okx_candles as _fetch_okx_candles

    return _fetch_okx_candles(*args, **kwargs)


def save_okx_candles_csv(*args, **kwargs):
    from .providers.okx import save_okx_candles_csv as _save_okx_candles_csv

    return _save_okx_candles_csv(*args, **kwargs)


def fetch_yahoo_ohlcv(*args, **kwargs):
    from .providers.yahoo import fetch_yahoo_ohlcv as _fetch_yahoo_ohlcv

    return _fetch_yahoo_ohlcv(*args, **kwargs)


__all__ = [
    "CRYPTO_DATA_ROOT",
    "CRYPTO_RAW_DIR",
    "CRYPTO_PROCESSED_DIR",
    "ensure_crypto_dirs",
    "normalize_crypto_ohlcv",
    "build_crypto_panel",
    "save_crypto_panel",
    "generate_ma_signals",
    "fetch_okx_candles",
    "save_okx_candles_csv",
    "fetch_yahoo_ohlcv",
]
