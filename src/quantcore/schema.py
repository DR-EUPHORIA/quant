import pandas as pd


def normalize_trade_date(df: pd.DataFrame, column: str = "trade_date") -> pd.DataFrame:
    out = df.copy()
    out[column] = pd.to_datetime(out[column], format="%Y%m%d", errors="coerce")
    if out[column].isna().any():
        out[column] = pd.to_datetime(out[column], errors="coerce")
    if out[column].isna().any():
        raise ValueError(f"存在无法解析的 {column}")
    return out


def validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{name} 缺少必要列: {missing}")
