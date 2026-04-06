import argparse
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]
sys.path.extend([str(ROOT), str(ROOT / "src")])

from quanta_stock import DATA_ROOT, PROCESSED_DIR, RESULTS_DIR
from quantbt import format_metrics_table
from quantbt.metrics import calculate_all_metrics

DEFAULT_PANEL = PROCESSED_DIR / "hs300_panel_20150101_20241231_full.parquet"
FALLBACK_PANEL = RESULTS_DIR / "panels" / "hs300_panel_20150101_20241231_full.parquet"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="运行横截面因子分组回测")
    parser.add_argument("--panel-path", type=Path, default=DEFAULT_PANEL)
    parser.add_argument("--factor", type=str, default="pe_ttm")
    parser.add_argument("--groups", type=int, default=5)
    parser.add_argument("--rebalance", choices=["daily", "weekly", "monthly"], default="monthly")
    parser.add_argument("--price-col", type=str, default="qfq_close")
    parser.add_argument("--start-date", type=str, default=None)
    parser.add_argument("--end-date", type=str, default=None)
    parser.add_argument("--higher-is-better", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=RESULTS_DIR / "factor")
    return parser.parse_args()


def resolve_panel_path(panel_path: Path) -> Path:
    if panel_path == DEFAULT_PANEL and FALLBACK_PANEL.exists():
        if not panel_path.exists():
            return FALLBACK_PANEL
        if FALLBACK_PANEL.stat().st_mtime >= panel_path.stat().st_mtime:
            return FALLBACK_PANEL
    return panel_path


def load_panel(
    panel_path: Path,
    factor_col: str,
    price_col: str,
    start_date: str | None,
    end_date: str | None,
) -> pd.DataFrame:
    panel_path = resolve_panel_path(panel_path)
    if not panel_path.exists():
        raise FileNotFoundError(f"面板文件不存在: {panel_path}")

    cols = ["ts_code", "trade_date", "close", factor_col, "is_tradeable_buy", "is_tradeable_sell"]
    if price_col not in cols:
        cols.append(price_col)
    panel = pd.read_parquet(panel_path, columns=cols)
    panel["trade_date"] = pd.to_datetime(panel["trade_date"])

    if start_date:
        panel = panel[panel["trade_date"] >= pd.to_datetime(start_date)]
    if end_date:
        panel = panel[panel["trade_date"] <= pd.to_datetime(end_date)]

    if price_col not in panel.columns:
        if price_col == "qfq_close" and "close" in panel.columns:
            print("警告: 面板缺少 qfq_close，已回退到 close")
            price_col = "close"
        else:
            raise ValueError(f"面板中不存在价格列: {price_col}")

    panel = panel.dropna(subset=["ts_code", "trade_date", price_col, factor_col])
    panel = panel.sort_values(["trade_date", "ts_code"]).reset_index(drop=True)

    if panel.empty:
        raise ValueError("过滤后面板为空")

    return panel


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


def build_group_memberships(
    factor_pivot: pd.DataFrame,
    rebalance_freq: str,
    n_groups: int,
) -> pd.DataFrame:
    memberships = pd.DataFrame(index=factor_pivot.index, columns=factor_pivot.columns, dtype="float64")
    rebalance_mask = get_rebalance_mask(factor_pivot.index, rebalance_freq)

    for date in factor_pivot.index[rebalance_mask.values]:
        memberships.loc[date] = assign_groups(factor_pivot.loc[date], n_groups)

    memberships = memberships.ffill().shift(1)
    return memberships


def build_group_returns(
    memberships: pd.DataFrame,
    asset_returns: pd.DataFrame,
    n_groups: int,
) -> pd.DataFrame:
    group_returns = pd.DataFrame(index=asset_returns.index)
    for group_id in range(1, n_groups + 1):
        mask = memberships.eq(group_id)
        counts = mask.sum(axis=1).replace(0, np.nan)
        weights = mask.div(counts, axis=0).fillna(0.0)
        group_returns[f"group_{group_id}"] = (weights * asset_returns).sum(axis=1)
    return group_returns.fillna(0.0)


def calculate_ic_series(factor_pivot: pd.DataFrame, next_day_returns: pd.DataFrame) -> pd.Series:
    ic_values = []
    for date in factor_pivot.index:
        merged = pd.DataFrame(
            {"factor": factor_pivot.loc[date], "fwd_ret": next_day_returns.loc[date]}
        ).dropna()
        if len(merged) < 5:
            ic_values.append(np.nan)
            continue
        factor_rank = merged["factor"].rank(method="average")
        return_rank = merged["fwd_ret"].rank(method="average")
        ic_values.append(factor_rank.corr(return_rank, method="pearson"))
    return pd.Series(ic_values, index=factor_pivot.index, name="ic")


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


def print_data_summary(panel: pd.DataFrame) -> None:
    n_dates = panel["trade_date"].nunique()
    n_codes = panel["ts_code"].nunique()
    start_date = panel["trade_date"].min().date()
    end_date = panel["trade_date"].max().date()
    print(f"样本区间: {start_date} -> {end_date}")
    print(f"交易日数: {n_dates}")
    print(f"股票数: {n_codes}")
    if n_dates < 30:
        print("警告: 交易日样本过少，分组回测与 IC 统计会退化。")


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


def main() -> None:
    args = parse_args()
    panel = load_panel(args.panel_path, args.factor, args.price_col, args.start_date, args.end_date)
    print_data_summary(panel)

    actual_price_col = args.price_col if args.price_col in panel.columns else "close"
    factor_pivot = panel.pivot(index="trade_date", columns="ts_code", values=args.factor)
    price_pivot = panel.pivot(index="trade_date", columns="ts_code", values=actual_price_col)
    investable_mask = (
        build_investable_mask(panel)
        .reindex(index=factor_pivot.index, columns=factor_pivot.columns)
        .fillna(False)
    )
    factor_pivot = factor_pivot.where(investable_mask)
    asset_returns = price_pivot.pct_change().fillna(0.0)
    next_day_returns = asset_returns.shift(-1)

    memberships = build_group_memberships(
        factor_pivot=factor_pivot,
        rebalance_freq=args.rebalance,
        n_groups=args.groups,
    )
    group_returns = build_group_returns(memberships, asset_returns, args.groups)

    low_col = "group_1"
    high_col = f"group_{args.groups}"
    long_short = (
        group_returns[high_col] - group_returns[low_col]
        if args.higher_is_better
        else group_returns[low_col] - group_returns[high_col]
    )
    group_returns["long_short"] = long_short

    nav = (1 + group_returns).cumprod()
    metrics = calculate_all_metrics(group_returns["long_short"])
    metrics_table = format_metrics_table(metrics)

    ic_series = calculate_ic_series(factor_pivot, next_day_returns)
    ic_summary = pd.DataFrame(
        [
            {"metric": "ic_mean", "value": ic_series.mean()},
            {"metric": "ic_std", "value": ic_series.std()},
            {"metric": "ic_ir", "value": ic_series.mean() / ic_series.std() if ic_series.std() else np.nan},
            {"metric": "ic_positive_rate", "value": (ic_series > 0).mean()},
        ]
    )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    group_returns.to_csv(args.output_dir / f"{args.factor}_group_returns.csv", encoding="utf-8-sig")
    nav.to_csv(args.output_dir / f"{args.factor}_group_nav.csv", encoding="utf-8-sig")
    memberships.to_csv(args.output_dir / f"{args.factor}_memberships.csv", encoding="utf-8-sig")
    metrics_table.to_csv(args.output_dir / f"{args.factor}_long_short_metrics.csv", index=False, encoding="utf-8-sig")
    ic_series.to_csv(args.output_dir / f"{args.factor}_ic_series.csv", encoding="utf-8-sig")
    ic_summary.to_csv(args.output_dir / f"{args.factor}_ic_summary.csv", index=False, encoding="utf-8-sig")

    save_nav_plot(nav, args.output_dir / f"{args.factor}_group_nav.png", f"{args.factor} Group NAV")
    save_ic_plot(ic_series, args.output_dir / f"{args.factor}_ic.png")

    print("因子分组回测完成")
    print(f"因子: {args.factor}")
    print(f"调仓频率: {args.rebalance}")
    print(f"价格列: {actual_price_col}")
    print(f"输出目录: {args.output_dir}")
    print(metrics_table.to_string(index=False))
    print("\nIC Summary:")
    print(ic_summary.to_string(index=False))


if __name__ == "__main__":
    main()
