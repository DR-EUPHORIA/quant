from quantcore.paths import DATA_DIR, PROJECT_ROOT


ROOT = PROJECT_ROOT
CRYPTO_DATA_ROOT = DATA_DIR / "crypto"
CRYPTO_RAW_DIR = CRYPTO_DATA_ROOT / "raw"


def ensure_crypto_dirs() -> None:
    CRYPTO_RAW_DIR.mkdir(parents=True, exist_ok=True)
