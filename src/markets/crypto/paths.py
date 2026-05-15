from quantcore.paths import DATA_DIR, PROJECT_ROOT


ROOT = PROJECT_ROOT
CRYPTO_DATA_ROOT = DATA_DIR / "crypto"
CRYPTO_RAW_DIR = CRYPTO_DATA_ROOT / "raw"
CRYPTO_PROCESSED_DIR = CRYPTO_DATA_ROOT / "processed"


def ensure_crypto_dirs() -> None:
    CRYPTO_RAW_DIR.mkdir(parents=True, exist_ok=True)
    CRYPTO_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
