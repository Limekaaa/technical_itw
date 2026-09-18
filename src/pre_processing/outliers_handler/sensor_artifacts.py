"""Sensor artifacts and deduplication (framework §2, item 1).

Covers:
- High-frequency heart-rate samples whose Fitbit ``confidence`` score is
  ``0`` (unreliable; 0.6-1.1 % of samples for p01/p05, see
  ``analysis/phase2a_fitbit.md §2A.1``). Dropped before any statistic.
- Exact timestamp duplicates in minute series (226 DST-duplicate zero
  rows in p01's steps/distance logs on 2020-03-29, see
  ``analysis/phase2a_fitbit.md §2A.1``). Keep-first after sort.

Both helpers are pure functions operating on the reader outputs so the
readers themselves stay unchanged.
"""

import pandas as pd


def filter_low_confidence_hr(hr_dict: dict) -> tuple:
    """Drop HR samples with ``confidence == 0``.

    Args:
        hr_dict: ``{standardized_ts: {"bpm": ..., "confidence": ...}}``
            as returned by ``fitbit_reader.heart_rate_reader``.

    Returns:
        ``(cleaned_dict, n_dropped, mean_conf)`` where ``mean_conf`` is
        the mean confidence of the kept samples (``None`` when empty).
    """
    cleaned = {}
    conf_sum, conf_n, n_dropped = 0.0, 0, 0
    for ts, payload in (hr_dict or {}).items():
        conf = (payload or {}).get("confidence")
        if conf == 0:
            n_dropped += 1
            continue
        cleaned[ts] = payload
        if isinstance(conf, (int, float)):
            conf_sum += float(conf)
            conf_n += 1
    mean_conf = round(conf_sum / conf_n, 3) if conf_n else None
    return cleaned, n_dropped, mean_conf


def dedupe_minute_series(series: pd.Series) -> tuple:
    """Sort a minute series and drop exact timestamp duplicates.

    Keeps the first occurrence (the DST duplicates are all value ``0``,
    so keep-first is equivalent to keep-any here, but first is the
    documented convention).

    Args:
        series: minute-level ``pd.Series`` with a ``DatetimeIndex``
            (steps / distance / calories).

    Returns:
        ``(deduped_series, n_dropped)``.
    """
    if series is None or len(series) == 0:
        return series, 0
    ordered = series.sort_index()
    before = len(ordered)
    deduped = ordered[~ordered.index.duplicated(keep="first")]
    return deduped, before - len(deduped)
