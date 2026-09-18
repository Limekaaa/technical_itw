"""Non-wear masking (framework §2, item 3).

Definition (from ``analysis/phase2a_fitbit.md §2A.2``): non-wear time is
a run of **>= 60 consecutive minutes** with zero steps alongside either
completely missing heart-rate data or flatlined heart rate
(per-minute std == 0 with >= 2 samples, i.e. charger/clipped-sensor
artifact).

Notes:
- Missing minute-slots in steps/distance count as zero steps.
- For p03 (no ``heart_rate.json``) the HR clause is vacuous, so the
  steps-only estimate is an upper bound conflating sleep with non-wear;
  callers must set ``hr_available=False`` and surface the
  ``nonwear_is_upper_bound`` flag.
- Output minute flag ``is_non_wear`` is 1 only inside qualifying long
  runs (isolated zero-HR minutes are *not* flagged).
"""

import numpy as np
import pandas as pd

NONWEAR_MIN_RUN = 60


def _runs_mask(flag: np.ndarray, min_run: int = NONWEAR_MIN_RUN) -> np.ndarray:
    """Keep only positions belonging to True-runs of length >= min_run."""
    out = np.zeros(len(flag), dtype=bool)
    if len(flag) == 0:
        return out
    start = None
    padded = np.concatenate([flag, [False]])
    for i, v in enumerate(padded):
        if v and start is None:
            start = i
        elif not v and start is not None:
            if i - start >= min_run:
                out[start:i] = True
            start = None
    return out


def compute_nonwear_day(steps_day: pd.Series, hr_day: dict,
                        hr_available: bool = True,
                        day: str = "") -> dict:
    """Compute non-wear minutes for a single calendar day.

    Args:
        steps_day: minute steps for the day (NaN-able ``pd.Series``
            with DatetimeIndex; may be empty when the device was off).
        hr_day: ``{ts: {"bpm": ...}}`` samples of that day (already
            confidence-filtered + clipped). Empty dict when missing.
        hr_available: False for p03 (no HR file) -> steps-only rule.
        day: ``YYYY-MM-DD`` string; used to build the full 1440-minute
            grid. When empty, the grid is inferred from ``steps_day``.

    Returns:
        Dict with ``nonwear_min`` (int), ``nonwear_hours`` (float),
        ``has_nonwear`` (bool) and ``is_non_wear_minute_index`` (the
        boolean minute mask, for debugging; not stored in the dataset).
    """
    if day:
        grid = pd.date_range(f"{day} 00:00:00", f"{day} 23:59:00", freq="min")
    elif steps_day is not None and len(steps_day):
        base = steps_day.index.normalize()[0]
        grid = pd.date_range(base, base + pd.Timedelta(days=1) - pd.Timedelta(minutes=1), freq="min")
    else:
        return {"nonwear_min": 0, "nonwear_hours": 0.0, "has_nonwear": False,
                "is_non_wear_minute_index": np.zeros(0, dtype=bool)}

    steps_full = pd.Series(0.0, index=grid)
    if steps_day is not None and len(steps_day):
        s = steps_day[~steps_day.index.duplicated(keep="first")].sort_index()
        steps_full.loc[s.index.intersection(grid)] = pd.to_numeric(s, errors="coerce").fillna(0.0)

    if hr_available and hr_day:
        hr_frame = pd.DataFrame(
            {"ts": list(hr_day.keys()),
             "bpm": [float((v or {}).get("bpm")) if (v or {}).get("bpm") is not None else np.nan
                     for v in hr_day.values()]})
        hr_frame["ts"] = pd.to_datetime(hr_frame["ts"], errors="coerce")
        hr_frame = hr_frame.dropna(subset=["ts", "bpm"])
        hr_frame["minute"] = hr_frame["ts"].dt.floor("min")
        grouped = hr_frame.groupby("minute")["bpm"]
        counts = grouped.size()
        stds = grouped.std(ddof=1).fillna(0.0)
        # A single sample has undefined std -> not flatlined (needs >= 2).
        stds[counts < 2] = np.nan
        no_hr = pd.Series(True, index=grid)
        no_hr.loc[counts.index.intersection(grid)] = False
        flat = pd.Series(False, index=grid)
        flat_minutes = stds[(counts >= 2) & (stds == 0.0)].index
        flat.loc[flat_minutes.intersection(grid)] = True
        hr_bad = (no_hr | flat).to_numpy()
    elif hr_available:
        # HR file exists but no sample that day -> all minutes lack HR.
        hr_bad = np.ones(len(grid), dtype=bool)
    else:
        # p03: steps-only upper bound.
        hr_bad = np.ones(len(grid), dtype=bool)

    zero_steps = (steps_full.to_numpy() == 0)
    candidate = zero_steps & hr_bad
    is_non_wear = _runs_mask(candidate, NONWEAR_MIN_RUN)
    n_min = int(is_non_wear.sum())
    return {"nonwear_min": n_min,
            "nonwear_hours": round(n_min / 60.0, 2),
            "has_nonwear": bool(n_min > 0),
            "is_non_wear_minute_index": is_non_wear}
