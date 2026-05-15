from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd


def format_metrics(metrics: dict[str, float]) -> dict[str, str]:
    return {
        "ann_return": f"{metrics['ann_return']:.2%}",
        "max_drawdown": f"{metrics['max_drawdown']:.2%}",
        "ann_sharpe": f"{metrics['ann_sharpe']:.4f}",
        "ann_calmar": f"{metrics['ann_calmar']:.4f}",
    }


def save_nav_report(
    avg_nav: pd.Series,
    etf_nav: pd.Series,
    avg_metrics: dict[str, float],
    etf_metrics: dict[str, float],
    out_prefix: Path,
) -> tuple[Path, Path]:
    out_prefix.parent.mkdir(parents=True, exist_ok=True)

    merged = pd.concat([avg_nav.rename("avg_nav"), etf_nav.rename("etf_nav")], axis=1).sort_index()
    csv_path = out_prefix.with_suffix(".csv")
    merged.to_csv(csv_path, index_label="trade_date")

    plot_path = out_prefix.with_suffix(".jpg")
    fig, ax = plt.subplots(figsize=(12, 6))
    merged.plot(ax=ax)
    ax.set_title("Continuous Basket vs ETF Tracking NAV")
    ax.set_xlabel("Trade Date")
    ax.set_ylabel("NAV")

    metrics_lines = [
        f"avg: {format_metrics(avg_metrics)}",
        f"etf: {format_metrics(etf_metrics)}",
    ]
    ax.text(
        0.01,
        0.99,
        "\n".join(metrics_lines),
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=9,
        bbox={"facecolor": "white", "alpha": 0.8, "edgecolor": "none"},
    )
    fig.tight_layout()
    fig.savefig(plot_path, dpi=180)
    plt.close(fig)
    return csv_path, plot_path
