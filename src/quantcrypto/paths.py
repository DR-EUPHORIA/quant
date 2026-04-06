from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CRYPTO_DATA_ROOT = ROOT / "data" / "crypto"
CRYPTO_RAW_DIR = CRYPTO_DATA_ROOT / "raw"


def ensure_crypto_dirs() -> None:
    CRYPTO_RAW_DIR.mkdir(parents=True, exist_ok=True)
