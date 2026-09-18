"""Tier-1 causal forward-fill (framework §3, Tier 1).

Method: forward-fill missing values up to a maximum of 2 days,
accompanied by a ``was_imputed_<col>`` binary flag. Applied to
slow-moving physiological metrics (7-day median body weight, RHR).

Justification: weight is hyper-stable (day-to-day |Δ| < 0.5 kg, CV <
1 %; see ``analysis/phase2b_subjective.md §2B.5``); RHR day-to-day sd
is 1.3-3.4 bpm. Forward-filling preserves the participant baseline
anchor without future leakage. No backfill: p05 has no RHR baseline
prior to late December, so early-window RHR stays NaN.
"""

import pandas as pd

FFILL_LIMIT_DAYS = 2


def causal_forward_fill(df: pd.DataFrame, cols: list,
                        limit: int = FFILL_LIMIT_DAYS,
                        group: str = "participant_id",
                        order: str = "date") -> pd.DataFrame:
    """Forward-fill ``cols`` causally within each participant.

    Args:
        df: daily master frame containing ``group`` + ``order`` columns.
        cols: columns to fill (only those present are processed).
        limit: max consecutive NaNs to fill (default 2 days).
        group: participant column for stratified filling.
        order: date column defining chronological order.

    Returns:
        Copy of ``df`` with filled columns plus ``was_imputed_<col>``
        flags (1 when the final value was forward-filled, else 0).
        Remaining NaNs (leading gaps, gaps > limit) are preserved.
    """
    out = df.copy()
    targets = [c for c in (cols or []) if c in out.columns]
    if not targets:
        return out
    out = out.sort_values([group, order]).reset_index(drop=True)
    for col in targets:
        flag = f"was_imputed_{col}"
        was_na = out[col].isna()
        filled = out.groupby(group, sort=False)[col].transform(
            lambda s: s.ffill(limit=limit))
        out[col] = filled
        out[flag] = ((was_na) & (filled.notna())).astype(int)
    return out
