from pathlib import Path

import pandas as pd

from .paths import RAW_DIR
from .schema import normalize_trade_date, validate_columns


DEFAULT_UNIVERSE = RAW_DIR / "000300_sh_index_weight_20150101_20241231.parquet"
FALLBACK_UNIVERSE = RAW_DIR / "hs300_constituents_latest.parquet"


def resolve_universe_path(path: Path) -> Path:
    if path.exists():
        return path
    if path == DEFAULT_UNIVERSE and FALLBACK_UNIVERSE.exists():
        return FALLBACK_UNIVERSE
    return path


def apply_universe_filter(panel: pd.DataFrame, universe: pd.DataFrame) -> pd.DataFrame:
    universe = universe.copy()
    validate_columns(universe, ["con_code"], "universe")

    if "trade_date" in universe.columns:
        universe = normalize_trade_date(universe)

    if "trade_date" in universe.columns and universe["trade_date"].nunique() > 1:
        universe = universe.rename(columns={"con_code": "ts_code"})
        if "weight" in universe.columns:
            universe = universe.rename(columns={"weight": "universe_weight"})
        keep_cols = [col for col in ["ts_code", "trade_date", "universe_weight"] if col in universe.columns]
        universe = universe[keep_cols].drop_duplicates(subset=["ts_code", "trade_date"], keep="last")
        panel = panel.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)
        universe = universe.sort_values(["ts_code", "trade_date"]).reset_index(drop=True)

        merged_groups = []
        for ts_code, panel_group in panel.groupby("ts_code", sort=False):
            universe_group = universe.loc[universe["ts_code"] == ts_code]
            if universe_group.empty:
                continue
            merged_group = pd.merge_asof(
                panel_group.sort_values("trade_date"),
                universe_group.sort_values("trade_date"),
                on="trade_date",
                by="ts_code",
                direction="backward",
            )
            merged_groups.append(merged_group)
        if not merged_groups:
            raise ValueError("动态成分过滤后面板为空")
        filtered = pd.concat(merged_groups, ignore_index=True)
        filtered = filtered.dropna(subset=["universe_weight"]) if "universe_weight" in filtered.columns else filtered
        filtered["is_dynamic_universe"] = True
        return filtered

    hs300_codes = sorted(universe["con_code"].dropna().unique().tolist())
    if not hs300_codes:
        raise ValueError("成分股列表为空")
    filtered = panel[panel["ts_code"].isin(hs300_codes)].copy()
    filtered["is_dynamic_universe"] = False
    return filtered
