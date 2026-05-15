from __future__ import annotations

import numpy as np
import pandas as pd


def calc_metrics(nav: pd.Series, periods_per_year: int = 252) -> dict[str, float]:
    nav = nav.dropna().astype(float)
    if nav.empty or len(nav) < 2:
        return {
            "ann_return": 0.0,
            "max_drawdown": 0.0,
            "ann_sharpe": 0.0,
            "ann_calmar": 0.0,
        }

    returns = nav.pct_change().dropna()
    if returns.empty:
        return {
            "ann_return": 0.0,
            "max_drawdown": 0.0,
            "ann_sharpe": 0.0,
            "ann_calmar": 0.0,
        }

    cumulative = float(nav.iloc[-1] / nav.iloc[0])
    ann_return = cumulative ** (periods_per_year / len(returns)) - 1.0
    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0
    max_drawdown = float(drawdown.min())
    ann_vol = float(returns.std(ddof=1) * np.sqrt(periods_per_year)) if len(returns) > 1 else 0.0
    ann_sharpe = ann_return / ann_vol if ann_vol else 0.0
    ann_calmar = ann_return / abs(max_drawdown) if max_drawdown else 0.0
    return {
        "ann_return": float(ann_return),
        "max_drawdown": max_drawdown,
        "ann_sharpe": float(ann_sharpe),
        "ann_calmar": float(ann_calmar),
    }
