"""Crypto market package."""

from .paths import CRYPTO_DATA_ROOT, CRYPTO_RAW_DIR, ensure_crypto_dirs


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
    "ensure_crypto_dirs",
    "fetch_okx_candles",
    "save_okx_candles_csv",
    "fetch_yahoo_ohlcv",
]
