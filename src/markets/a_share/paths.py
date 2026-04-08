from quantcore.paths import DATA_DIR, PROJECT_ROOT, RESULTS_DIR as PROJECT_RESULTS_DIR


ROOT = PROJECT_ROOT
DATA_ROOT = DATA_DIR / "tushare"
RAW_DIR = DATA_ROOT / "raw"
PROCESSED_DIR = DATA_ROOT / "processed"
RESULTS_DIR = PROJECT_RESULTS_DIR / "a_stock"
PANELS_DIR = RESULTS_DIR / "panels"
DATA_QUALITY_DIR = RESULTS_DIR / "data_quality"


def ensure_a_stock_dirs() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    PANELS_DIR.mkdir(parents=True, exist_ok=True)
    DATA_QUALITY_DIR.mkdir(parents=True, exist_ok=True)
