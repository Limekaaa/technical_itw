"""Tier-2 missing-indicators with algorithm-native handling (§3, Tier 2).

Structural block-missingness (p03's ~49 % missing wellness records,
absent HR zones, sparse sRPE across p03/p05) is informative: it may
signal lack of compliance or a true rest day. Zero-filling would
artificially depress features, so absent logs stay NaN alongside
explicit indicators; tree models consume NaN natively, linear models
use median + indicator.

All rolling ratios are strictly causal: computed over windows ending on
day D (data known when predicting the D+1 label).
"""

import numpy as np
import pandas as pd


def add_presence_flags(df: pd.DataFrame) -> pd.DataFrame:
    """Add day-level ``has_*`` presence flags from raw day columns.

    Expects (when present): ``n_wellness_rows``, ``n_nights``,
    ``n_food_photos``/``has_nutrition``, ``steps_cov_min``,
    ``hr_cov_min``, ``zones_available``. Missing inputs yield NaN-safe
    defaults (0 / False) without raising.
    """
    out = df.copy()
    if "n_wellness_rows" in out.columns:
        out["has_wellness"] = (pd.to_numeric(out["n_wellness_rows"], errors="coerce").fillna(0) > 0).astype(int)
    if "n_nights" in out.columns:
        out["has_sleep"] = (pd.to_numeric(out["n_nights"], errors="coerce").fillna(0) > 0).astype(int)
    if "has_nutrition" in out.columns:
        out["has_nutrition"] = pd.to_numeric(out["has_nutrition"], errors="coerce").fillna(0).astype(int)
    else:
        out["has_nutrition"] = 0
    if "steps_cov_min" in out.columns:
        out["has_steps"] = (pd.to_numeric(out["steps_cov_min"], errors="coerce").fillna(0) > 0).astype(int)
    if "hr_cov_min" in out.columns:
        out["has_hr"] = (pd.to_numeric(out["hr_cov_min"], errors="coerce").fillna(0) > 0).astype(int)
    if "zones_available" in out.columns:
        out["has_zones"] = pd.to_numeric(out["zones_available"], errors="coerce").fillna(0).astype(int)
    return out


def add_rolling_missing_ratios(df: pd.DataFrame, window: int = 7,
                               group: str = "participant_id",
                               order: str = "date") -> pd.DataFrame:
    """Add causal ``missing_ratio_<var>_<window>d`` availability ratios.

    Ratios use day-level missingness of: wellness rows, weight, zones,
    sleep nights, sRPE sessions. Each ratio = fraction of missing days
    in the trailing ``window`` ending on D (min_periods=1).

    Args:
        df: daily frame (must contain the raw day columns when
            available; absent columns are skipped).
        window: trailing window length in days (default 7).
        group: participant column. order: date column.
    """
    out = df.sort_values([group, order]).reset_index(drop=True)
    specs = {
        "wellness": "n_wellness_rows",
        "weight": "weight_raw",
        "zones": "zones_available",
        "sleep": "n_nights",
        "srpe": "srpe_n_sessions",
    }
    for name, col in specs.items():
        if col not in out.columns:
            continue
        if col == "zones_available":
            miss = (pd.to_numeric(out[col], errors="coerce").fillna(0) == 0).astype(float)
        elif col in ("n_wellness_rows", "n_nights", "srpe_n_sessions"):
            miss = (pd.to_numeric(out[col], errors="coerce").fillna(0) == 0).astype(float)
        else:
            miss = out[col].isna().astype(float)
        out[f"missing_ratio_{name}_{window}d"] = (
            miss.groupby(out[group]).transform(
                lambda s: s.rolling(window, min_periods=1).mean()))
    return out


def add_window_stats(df: pd.DataFrame, cols: list, window: int = 7,
                     group: str = "participant_id",
                     order: str = "date") -> pd.DataFrame:
    """Add causal rolling mean/median/std over day-level columns.

    Used for the "statistics aggregated over different time windows
    (day, week, month)" requirement. Windows end on D (causal). NaNs
    propagate honestly (min_periods=1, skipna=True).

    Args:
        df: daily frame. cols: numeric day columns. window: days.
    """
    out = df.sort_values([group, order]).reset_index(drop=True)
    for col in cols or []:
        if col not in out.columns:
            continue
        s = pd.to_numeric(out[col], errors="coerce")
        g = s.groupby(out[group])
        out[f"{col}_mean_{window}d"] = g.transform(lambda x: x.rolling(window, min_periods=1).mean())
        out[f"{col}_median_{window}d"] = g.transform(lambda x: x.rolling(window, min_periods=1).median())
        out[f"{col}_std_{window}d"] = g.transform(lambda x: x.rolling(window, min_periods=1).std())
    return out
