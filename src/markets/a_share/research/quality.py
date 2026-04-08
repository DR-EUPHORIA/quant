from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd


@dataclass
class DataQualityReport:
    latest_gap: pd.DataFrame
    missing_summary: pd.DataFrame
    coverage_by_date: pd.DataFrame
    history_by_code: pd.DataFrame
    bool_coverage: pd.DataFrame
    tradeability_by_date: pd.DataFrame
    tradeability_by_code: pd.DataFrame


def resolve_panel_path(default_path: Path, fallback_path: Path, panel_path: Path) -> Path:
    if panel_path.exists():
        return panel_path
    if panel_path == default_path and fallback_path.exists():
        return fallback_path
    return panel_path


def normalize_trade_date(df: pd.DataFrame) -> pd.Series:
    if "trade_date" not in df.columns:
        return pd.Series(dtype="datetime64[ns]")
    out = pd.to_datetime(df["trade_date"].astype(str), format="%Y%m%d", errors="coerce")
    return out.fillna(pd.to_datetime(df["trade_date"], errors="coerce"))


def print_dataset_summary(name: str, df: pd.DataFrame, key_cols: list[str]) -> None:
    print(f"\n=== {name} ===")
    print(f"shape: {df.shape}")
    if "trade_date" in df.columns:
        trade_dates = normalize_trade_date(df)
        print(f"date_range: {trade_dates.min()} -> {trade_dates.max()} (n_dates={trade_dates.nunique()})")
    if all(col in df.columns for col in key_cols):
        print(f"duplicate {tuple(key_cols)}: {df.duplicated(key_cols).sum()}")
    if "ts_code" in df.columns:
        print(f"n_ts_code: {df['ts_code'].nunique()}")
    if "con_code" in df.columns:
        print(f"n_con_code: {df['con_code'].nunique()}")
    print("top missing ratios:")
    print(df.isna().mean().sort_values(ascending=False).head(8).to_string())


def latest_universe_gap(panel: pd.DataFrame, universe: pd.DataFrame, daily: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["trade_date"] = normalize_trade_date(panel)
    daily = daily.copy()
    daily["trade_date"] = normalize_trade_date(daily)

    latest_date = panel["trade_date"].max()
    latest_codes = set(panel.loc[panel["trade_date"] == latest_date, "ts_code"])

    if "trade_date" in universe.columns:
        universe = universe.copy()
        universe["trade_date"] = normalize_trade_date(universe)
        if universe["trade_date"].nunique() > 1:
            universe_codes = set(universe.loc[universe["trade_date"] == latest_date, "con_code"])
        else:
            universe_codes = set(universe["con_code"])
    else:
        universe_codes = set(universe["con_code"])

    missing_codes = sorted(universe_codes - latest_codes)
    rows: list[dict[str, object]] = []
    for code in missing_codes:
        code_daily = daily.loc[daily["ts_code"] == code, "trade_date"]
        rows.append(
            {
                "ts_code": code,
                "panel_latest_date": latest_date,
                "daily_last_date": code_daily.max() if not code_daily.empty else pd.NaT,
            }
        )
    return pd.DataFrame(rows)


def per_code_missing(panel: pd.DataFrame) -> pd.DataFrame:
    fields = [
        "close", "turnover_rate", "turnover_rate_f", "pe", "pe_ttm", "pb", "ps", "ps_ttm",
        "total_mv", "circ_mv", "free_share", "adj_factor", "qfq_close", "limit_up", "limit_down",
    ]
    rows: list[dict[str, object]] = []
    for code, group in panel.groupby("ts_code"):
        row: dict[str, object] = {"ts_code": code, "rows": len(group)}
        for field in fields:
            if field in group.columns:
                row[f"miss_{field}"] = float(group[field].isna().mean())
        rows.append(row)
    return pd.DataFrame(rows).sort_values("rows")


def coverage_by_date(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["trade_date"] = normalize_trade_date(panel)
    counts = panel.groupby("trade_date")["ts_code"].nunique().rename("n_codes")
    return counts.reset_index().sort_values("trade_date")


def history_by_code(panel: pd.DataFrame) -> pd.DataFrame:
    panel = panel.copy()
    panel["trade_date"] = normalize_trade_date(panel)
    history = panel.groupby("ts_code").agg(
        rows=("trade_date", "size"),
        start_date=("trade_date", "min"),
        end_date=("trade_date", "max"),
    )
    return history.reset_index().sort_values(["rows", "ts_code"])


def bool_coverage_summary(panel: pd.DataFrame) -> pd.DataFrame:
    fields = ["is_suspended", "is_st", "is_paused_listing", "is_tradeable_buy", "is_tradeable_sell"]
    rows: list[dict[str, object]] = []
    for field in fields:
        if field not in panel.columns:
            continue
        series = panel[field]
        bool_series = series.fillna(False).astype(bool)
        rows.append(
            {
                "field": field,
                "coverage_ratio": float(series.notna().mean()),
                "true_ratio": float(bool_series.mean()),
                "false_ratio": float((~bool_series).mean()),
                "missing_ratio": float(series.isna().mean()),
            }
        )
    return pd.DataFrame(rows)


def tradeability_by_date(panel: pd.DataFrame) -> pd.DataFrame:
    fields = ["is_suspended", "is_st", "is_paused_listing", "is_tradeable_buy", "is_tradeable_sell"]
    available = [field for field in fields if field in panel.columns]
    if not available:
        return pd.DataFrame()

    panel = panel.copy()
    panel["trade_date"] = normalize_trade_date(panel)
    for field in available:
        panel[field] = panel[field].fillna(False).astype(bool)

    grouped = panel.groupby("trade_date")
    summary = grouped["ts_code"].nunique().rename("n_codes").to_frame()
    for field in available:
        summary[f"{field}_count"] = grouped[field].sum()
        summary[f"{field}_ratio"] = grouped[field].mean()
    return summary.reset_index().sort_values("trade_date")


def tradeability_by_code(panel: pd.DataFrame) -> pd.DataFrame:
    fields = ["is_suspended", "is_st", "is_paused_listing", "is_tradeable_buy", "is_tradeable_sell"]
    available = [field for field in fields if field in panel.columns]
    if not available:
        return pd.DataFrame()

    panel = panel.copy()
    for field in available:
        panel[field] = panel[field].fillna(False).astype(bool)

    grouped = panel.groupby("ts_code")
    summary = grouped.size().rename("rows").to_frame()
    for field in available:
        summary[f"{field}_count"] = grouped[field].sum()
        summary[f"{field}_ratio"] = grouped[field].mean()
    return summary.reset_index().sort_values(["rows", "ts_code"])


def build_quality_report(panel: pd.DataFrame, universe: pd.DataFrame, daily: pd.DataFrame) -> DataQualityReport:
    return DataQualityReport(
        latest_gap=latest_universe_gap(panel, universe, daily),
        missing_summary=per_code_missing(panel),
        coverage_by_date=coverage_by_date(panel),
        history_by_code=history_by_code(panel),
        bool_coverage=bool_coverage_summary(panel),
        tradeability_by_date=tradeability_by_date(panel),
        tradeability_by_code=tradeability_by_code(panel),
    )


def save_csv(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8-sig")
