from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from quantbt import calculate_all_metrics, format_metrics_table


@dataclass
class FactorTestResult:
    group_returns: pd.DataFrame
    nav: pd.DataFrame
    memberships: pd.DataFrame
    metrics_table: pd.DataFrame
    ic_series: pd.Series
    ic_summary: pd.DataFrame
    price_col_used: str


def resolve_panel_path(default_path: Path, fallback_path: Path, panel_path: Path) -> Path:
    if panel_path.exists():
        return panel_path
    if panel_path == default_path and fallback_path.exists():
        return fallback_path
    return panel_path


def load_factor_panel(
    panel_path: Path,
    factor_col: str,
    price_col: str,
    start_date: str | None,
    end_date: str | None,
) -> tuple[pd.DataFrame, str]:
    if not panel_path.exists():
        raise FileNotFoundError(f"panel file does not exist: {panel_path}")

    cols = ["ts_code", "trade_date", "close", factor_col, "is_tradeable_buy", "is_tradeable_sell"]
    if price_col not in cols:
        cols.append(price_col)
    panel = pd.read_parquet(panel_path, columns=cols)
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    if start_date is not None:
        panel = panel.loc[panel["trade_date"] >= pd.to_datetime(start_date)]
    if end_date is not None:
        panel = panel.loc[panel["trade_date"] <= pd.to_datetime(end_date)]

    actual_price_col = price_col
    if actual_price_col not in panel.columns:
        if actual_price_col == "qfq_close" and "close" in panel.columns:
            actual_price_col = "close"
        else:
            raise ValueError(f"price column not found in panel: {actual_price_col}")

    panel = panel.dropna(subset=["ts_code", "trade_date", factor_col, actual_price_col]).copy()
    if panel.empty:
        raise ValueError("panel is empty after filtering")
    return panel.sort_values(["trade_date", "ts_code"]).reset_index(drop=True), actual_price_col


def get_rebalance_mask(dates: pd.DatetimeIndex, freq: str) -> pd.Series:
    series = pd.Series(dates, index=dates)
    if freq == "daily":
        return pd.Series(True, index=dates)
    if freq == "weekly":
        keys = series.dt.strftime("%Y-%W")
    else:
        keys = series.dt.to_period("M").astype(str)
    return keys.ne(keys.shift(1)).fillna(True)


def assign_groups(values: pd.Series, n_groups: int) -> pd.Series:
    valid = values.dropna()
    if valid.empty or valid.nunique() < n_groups:
        return pd.Series(index=values.index, dtype="float64")

    ranked = valid.rank(method="first", ascending=True)
    labels = pd.qcut(ranked, q=n_groups, labels=False) + 1
    out = pd.Series(index=values.index, dtype="float64")
    out.loc[labels.index] = labels.astype(float)
    return out


def build_group_memberships(factor_pivot: pd.DataFrame, rebalance_freq: str, n_groups: int) -> pd.DataFrame:
    memberships = pd.DataFrame(index=factor_pivot.index, columns=factor_pivot.columns, dtype="float64")
    rebalance_mask = get_rebalance_mask(factor_pivot.index, rebalance_freq)

    for trade_date in factor_pivot.index[rebalance_mask.values]:
        memberships.loc[trade_date] = assign_groups(factor_pivot.loc[trade_date], n_groups)

    return memberships.ffill().shift(1)


def build_group_returns(memberships: pd.DataFrame, asset_returns: pd.DataFrame, n_groups: int) -> pd.DataFrame:
    group_returns = pd.DataFrame(index=asset_returns.index)
    for group_id in range(1, n_groups + 1):
        mask = memberships.eq(group_id)
        counts = mask.sum(axis=1).replace(0, np.nan)
        weights = mask.div(counts, axis=0).fillna(0.0)
        group_returns[f"group_{group_id}"] = (weights * asset_returns).sum(axis=1)
    return group_returns.fillna(0.0)


def calculate_ic_series(factor_pivot: pd.DataFrame, next_day_returns: pd.DataFrame) -> pd.Series:
    ic_values: list[float] = []
    for trade_date in factor_pivot.index:
        merged = pd.DataFrame(
            {"factor": factor_pivot.loc[trade_date], "fwd_ret": next_day_returns.loc[trade_date]}
        ).dropna()
        if len(merged) < 5:
            ic_values.append(np.nan)
            continue
        factor_rank = merged["factor"].rank(method="average")
        return_rank = merged["fwd_ret"].rank(method="average")
        ic_values.append(float(factor_rank.corr(return_rank, method="pearson")))
    return pd.Series(ic_values, index=factor_pivot.index, name="ic")


def build_investable_mask(panel: pd.DataFrame) -> pd.DataFrame:
    buyable = pd.Series(True, index=panel.index)
    if "is_tradeable_buy" in panel.columns:
        buyable &= panel["is_tradeable_buy"].fillna(False)
    return (
        panel.assign(is_investable=buyable)
        .pivot(index="trade_date", columns="ts_code", values="is_investable")
        .fillna(False)
        .astype(bool)
    )


def run_factor_test(
    panel: pd.DataFrame,
    factor_col: str,
    n_groups: int,
    rebalance_freq: str,
    price_col: str,
    higher_is_better: bool = False,
) -> FactorTestResult:
    factor_pivot = panel.pivot(index="trade_date", columns="ts_code", values=factor_col)
    price_pivot = panel.pivot(index="trade_date", columns="ts_code", values=price_col)
    investable_mask = build_investable_mask(panel).reindex(
        index=factor_pivot.index, columns=factor_pivot.columns
    ).fillna(False)
    factor_pivot = factor_pivot.where(investable_mask)

    asset_returns = price_pivot.pct_change().fillna(0.0)
    next_day_returns = asset_returns.shift(-1)

    memberships = build_group_memberships(factor_pivot, rebalance_freq, n_groups)
    group_returns = build_group_returns(memberships, asset_returns, n_groups)

    low_col = "group_1"
    high_col = f"group_{n_groups}"
    group_returns["long_short"] = (
        group_returns[high_col] - group_returns[low_col]
        if higher_is_better
        else group_returns[low_col] - group_returns[high_col]
    )
    nav = (1 + group_returns).cumprod()

    metrics = calculate_all_metrics(group_returns["long_short"])
    metrics_table = format_metrics_table(metrics)

    ic_series = calculate_ic_series(factor_pivot, next_day_returns)
    ic_std = ic_series.std()
    ic_summary = pd.DataFrame(
        [
            {"metric": "ic_mean", "value": ic_series.mean()},
            {"metric": "ic_std", "value": ic_std},
            {"metric": "ic_ir", "value": ic_series.mean() / ic_std if pd.notna(ic_std) and ic_std != 0 else np.nan},
            {"metric": "ic_positive_rate", "value": float((ic_series > 0).mean())},
        ]
    )

    return FactorTestResult(
        group_returns=group_returns,
        nav=nav,
        memberships=memberships,
        metrics_table=metrics_table,
        ic_series=ic_series,
        ic_summary=ic_summary,
        price_col_used=price_col,
    )


def save_nav_plot(nav_df: pd.DataFrame, output_path: Path, title: str) -> None:
    fig, ax = plt.subplots(figsize=(12, 6))
    for column in nav_df.columns:
        ax.plot(nav_df.index, nav_df[column], label=column, linewidth=1.4)
    ax.set_title(title)
    ax.set_xlabel("Date")
    ax.set_ylabel("NAV")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)


def save_ic_plot(ic_series: pd.Series, output_path: Path) -> None:
    rolling_ic = ic_series.rolling(20).mean()
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.plot(ic_series.index, ic_series, label="Daily IC", alpha=0.4, linewidth=1.0)
    ax.plot(rolling_ic.index, rolling_ic, label="20D Rolling IC", linewidth=1.5)
    ax.axhline(0, color="gray", linestyle="--", linewidth=1)
    ax.set_title("Factor IC")
    ax.set_xlabel("Date")
    ax.set_ylabel("IC")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="best")
    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
