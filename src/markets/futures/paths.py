from quantcore.paths import DATA_DIR, PROJECT_ROOT, RESULTS_DIR as PROJECT_RESULTS_DIR


ROOT = PROJECT_ROOT
FUTURES_DATA_ROOT = DATA_DIR / "futures"
FUTURES_RAW_DIR = FUTURES_DATA_ROOT / "raw"
FUTURES_KLINE_DIR = FUTURES_RAW_DIR / "kline"
FUTURES_REFERENCE_DIR = FUTURES_DATA_ROOT / "reference"
FUTURES_HOTS_PATH = FUTURES_REFERENCE_DIR / "hots.xlsx"
FUTURES_PROCESSED_DIR = FUTURES_DATA_ROOT / "processed"
FUTURES_RESULTS_DIR = PROJECT_RESULTS_DIR / "futures"
FUTURES_REPORTS_DIR = FUTURES_RESULTS_DIR / "reports"


def ensure_futures_dirs() -> None:
    FUTURES_DATA_ROOT.mkdir(parents=True, exist_ok=True)
    FUTURES_RAW_DIR.mkdir(parents=True, exist_ok=True)
    FUTURES_KLINE_DIR.mkdir(parents=True, exist_ok=True)
    FUTURES_REFERENCE_DIR.mkdir(parents=True, exist_ok=True)
    FUTURES_PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    FUTURES_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    FUTURES_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
