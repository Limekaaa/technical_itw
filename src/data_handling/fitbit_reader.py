"""Reader and aggregator for the <player_id>/fitbit folder.

Flat time-series files (calories, distance, steps) return a
``pd.Series``; the tabular sleep-score export returns a ``pd.DataFrame``;
nested JSON exports (heart rate, resting heart rate, heart-rate zones,
sleep, exercise) return a ``dict``.

Every date comparison goes through ``standardize_date`` from
``src.utils.date_handler``. Each reader takes ``(player_id, start_date,
end_date=None)``; when only ``start_date`` is given the whole calendar
day is returned.
"""

import json
import re
from pathlib import Path
import logging

import pandas as pd

from src.utils.date_handler import standardize_date, _resolve_bounds, _is_date_only, _matches

_BASE_DIR = Path(__file__).resolve().parents[2]
_DATA_DIR = _BASE_DIR / "data"

def _fitbit_file(player_id: str, filename: str):
    path = _DATA_DIR / player_id / "fitbit" / filename
    if not path.is_file():
        return None
    return path


def _flat_series(player_id: str, filename: str, start_date: str, end_date=None) -> pd.Series:
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _fitbit_file(player_id, filename)
    if path is None:
        return pd.Series(dtype=float)
    with open(path, "r") as fh:
        records = json.load(fh)
    stamps, values = [], []
    for entry in records:
        ts_std = standardize_date(entry.get("dateTime", ""))
        if not ts_std or not _matches(ts_std, lower, upper, upper_inclusive):
            continue
        try:
            values.append(float(entry["value"]))
        except (KeyError, TypeError, ValueError):
            logging.warning(f"Skipping entry with invalid value: {entry}")
            
        stamps.append(pd.Timestamp(ts_std))
    if not stamps:
        return pd.Series(dtype=float)
    series = pd.Series(values, index=pd.DatetimeIndex(stamps))
    return series.sort_index()


def calories_reader(player_id: str, start_date: str, end_date=None) -> pd.Series:
    """Minute-level calorie expenditure as a Series."""
    return _flat_series(player_id, "calories.json", start_date, end_date)


def distance_reader(player_id: str, start_date: str, end_date=None) -> pd.Series:
    """Minute-level distance as a Series."""
    return _flat_series(player_id, "distance.json", start_date, end_date)


def steps_reader(player_id: str, start_date: str, end_date=None) -> pd.Series:
    """Minute-level step counts as a Series."""
    return _flat_series(player_id, "steps.json", start_date, end_date)


def heart_rate_reader(player_id: str, start_date: str, end_date=None) -> dict:
    """High-frequency heart rate as {standardized_ts: {bpm, confidence}}."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _fitbit_file(player_id, "heart_rate.json")
    if path is None:
        return {}
    with open(path, "r") as fh:
        records = json.load(fh)
    out = {}
    for entry in records:
        ts_std = standardize_date(entry.get("dateTime", ""))
        if not ts_std or not _matches(ts_std, lower, upper, upper_inclusive):
            continue
        value = entry.get("value", {}) or {}
        out[ts_std] = {"bpm": value.get("bpm"), "confidence": value.get("confidence")}
    return out


def resting_heart_rate_reader(player_id: str, start_date: str, end_date=None) -> dict:
    """Daily resting heart rate as {standardized_ts: raw value dict}."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _fitbit_file(player_id, "resting_heart_rate.json")
    if path is None:
        return {}
    with open(path, "r") as fh:
        records = json.load(fh)
    out = {}
    for entry in records:
        ts_std = standardize_date(entry.get("dateTime", ""))
        if not ts_std or not _matches(ts_std, lower, upper, upper_inclusive):
            continue
        out[ts_std] = dict(entry.get("value", {}) or {})
    return out


def time_in_heart_rate_zones_reader(player_id: str, start_date: str, end_date=None) -> dict:
    """Daily time in HR zones as {standardized_ts: {zone: minutes}}."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _fitbit_file(player_id, "time_in_heart_rate_zones.json")
    if path is None:
        return {}
    with open(path, "r") as fh:
        records = json.load(fh)
    out = {}
    for entry in records:
        ts_std = standardize_date(entry.get("dateTime", ""))
        if not ts_std or not _matches(ts_std, lower, upper, upper_inclusive):
            continue
        value = entry.get("value", {}) or {}
        out[ts_std] = dict(value.get("valuesInZones", {}) or {})
    return out


def sleep_reader(player_id: str, start_date: str, end_date=None) -> dict:
    """Detailed sleep logs as {logId: full record}, filtered on startTime."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _fitbit_file(player_id, "sleep.json")
    if path is None:
        return {}
    with open(path, "r") as fh:
        records = json.load(fh)
    out = {}
    for entry in records:
        ts_std = standardize_date(entry.get("startTime", ""))
        if not ts_std or not _matches(ts_std, lower, upper, upper_inclusive):
            continue
        out[entry.get("logId")] = entry
    return out


def exercise_reader(player_id: str, start_date: str, end_date=None) -> dict:
    """Exercise logs as {logId: full record}, filtered on startTime."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _fitbit_file(player_id, "exercise.json")
    if path is None:
        return {}
    with open(path, "r") as fh:
        records = json.load(fh)
    out = {}
    for entry in records:
        ts_std = standardize_date(entry.get("startTime", ""))
        if not ts_std or not _matches(ts_std, lower, upper, upper_inclusive):
            continue
        out[entry.get("logId")] = entry
    return out


def sleep_score_reader(player_id: str, start_date: str, end_date=None) -> pd.DataFrame:
    """Daily sleep-score rows whose timestamp falls in the time span."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _fitbit_file(player_id, "sleep_score.csv")
    if path is None:
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty or "timestamp" not in df.columns:
        return pd.DataFrame()
    std_ts = [standardize_date(str(v)) for v in df["timestamp"]]
    mask = [bool(s) and _matches(s, lower, upper, upper_inclusive) for s in std_ts]
    return df.loc[mask].reset_index(drop=True)
