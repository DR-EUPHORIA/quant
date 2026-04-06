from pathlib import Path

import pandas as pd

from .paths import PANELS_DIR


FALLBACK_OUTPUT = PANELS_DIR / "hs300_panel_20150101_20241231.parquet"


def load_parquet(path: Path, name: str) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"{name} 文件不存在: {path}")
    df = pd.read_parquet(path)
    if df.empty:
        raise ValueError(f"{name} 为空: {path}")
    return df


def load_optional_parquet(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_parquet(path)
    return pd.DataFrame()


def resolve_output_path(desired_path: Path) -> Path:
    desired_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(desired_path, "ab"):
            pass
        desired_path.unlink(missing_ok=True)
        return desired_path
    except OSError:
        fallback_path = FALLBACK_OUTPUT.parent / desired_path.name
        fallback_path.parent.mkdir(parents=True, exist_ok=True)
        return fallback_path
