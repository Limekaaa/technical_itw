"""Physiological bounds and sentinel cleaning (framework §2, item 2).

Covers:
- Continuous heart-rate clipping to the physiologically valid range
  ``[30, 220]`` bpm.
- Impossible stride lengths (e.g. the 11.3 cm running stride for p14 in
  ``participant-overview.xlsx``) mapped to NaN.
- Resting-heart-rate sentinels: ``0.0`` values paired with null dates
  (p03 carries 51/152, p05 9/95) mapped to NaN. This centralises the
  ``value > 0`` rule already applied inline in
  ``aggregator.aggregate_activity``.
"""

import math

HR_LO_BPM = 30
HR_HI_BPM = 220
# Strides below this are physically impossible for an adult walk/run and
# treated as instrument error (p14 run stride = 11.3 cm, see findings).
MIN_PLAUSIBLE_STRIDE_CM = 20.0


def clip_hr_bpm(hr_dict: dict, lo: int = HR_LO_BPM, hi: int = HR_HI_BPM) -> tuple:
    """Clip ``bpm`` values in an HR dict to ``[lo, hi]``.

    Args:
        hr_dict: ``{ts: {"bpm": ..., "confidence": ...}}`` (already
            confidence-filtered).
        lo: lower bound in bpm.
        hi: upper bound in bpm.

    Returns:
        ``(clipped_dict, n_clipped)``. Non-numeric bpm entries are kept
        as-is and not counted.
    """
    clipped = {}
    n_clipped = 0
    for ts, payload in (hr_dict or {}).items():
        payload = dict(payload or {})
        bpm = payload.get("bpm")
        if isinstance(bpm, (int, float)) and not (isinstance(bpm, float) and math.isnan(bpm)):
            bounded = min(max(float(bpm), lo), hi)
            if bounded != float(bpm):
                n_clipped += 1
            # Preserve int type when the input was int-like.
            payload["bpm"] = int(bounded) if isinstance(bpm, int) and float(bounded).is_integer() else bounded
        clipped[ts] = payload
    return clipped, n_clipped


def clean_stride_run(value) -> float:
    """Map implausible stride lengths to NaN.

    Args:
        value: raw stride length in cm (e.g. from overview).

    Returns:
        Float stride, or ``float("nan")`` when missing, non-numeric or
        below ``MIN_PLAUSIBLE_STRIDE_CM``.
    """
    try:
        v = float(value)
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(v) or v < MIN_PLAUSIBLE_STRIDE_CM:
        return float("nan")
    return v


def clean_resting_hr_value(value_dict: dict):
    """Extract a valid RHR measurement or return NaN.

    Sentinel rule: ``value <= 0`` or a null/empty ``date`` means the
    device had no measurement (not 0 bpm).

    Args:
        value_dict: raw ``{"date": ..., "value": ..., "error": ...}``.

    Returns:
        Float bpm or ``float("nan")``.
    """
    if not isinstance(value_dict, dict):
        return float("nan")
    date = value_dict.get("date")
    if date is None or (isinstance(date, float) and math.isnan(date)) or str(date).strip() == "":
        return float("nan")
    try:
        v = float(value_dict.get("value"))
    except (TypeError, ValueError):
        return float("nan")
    if math.isnan(v) or v <= 0:
        return float("nan")
    return v
