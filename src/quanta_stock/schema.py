import pandas as pd


def normalize_trade_date(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["trade_date"] = pd.to_datetime(out["trade_date"], format="%Y%m%d", errors="coerce")
    if out["trade_date"].isna().any():
        out["trade_date"] = pd.to_datetime(out["trade_date"], errors="coerce")
    if out["trade_date"].isna().any():
        raise ValueError("存在无法解析的 trade_date")
    return out


def validate_columns(df: pd.DataFrame, required: list[str], name: str) -> None:
    missing = [col for col in required if col not in df.columns]
    if missing:
        raise ValueError(f"{name} 缺少必要列: {missing}")
