"""Reader and aggregator for the <player_id>/pmsys folder.

Tabular wellness and sRPE logs return a ``pd.DataFrame``; the injury
log (nested ``{body_part: severity}`` payloads) returns a ``dict``.

Every date comparison goes through ``standardize_date`` from
``src.utils.date_handler``. Each reader takes ``(player_id, start_date,
end_date=None)``; when only ``start_date`` is given the whole calendar
day is returned.
"""

import ast
import re
from pathlib import Path

import pandas as pd

from src.utils.date_handler import standardize_date, _resolve_bounds, _is_date_only, _matches

_BASE_DIR = Path(__file__).resolve().parents[2]
_DATA_DIR = _BASE_DIR / "data"




def _pmsys_file(player_id: str, filename: str):
    path = _DATA_DIR / player_id / "pmsys" / filename
    if not path.is_file():
        return None
    return path


def _filtered_frame(player_id: str, filename: str, date_column: str, start_date: str, end_date=None) -> pd.DataFrame:
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _pmsys_file(player_id, filename)
    if path is None:
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty or date_column not in df.columns:
        return pd.DataFrame()
    std_ts = [standardize_date(str(v)) for v in df[date_column]]
    mask = [bool(s) and _matches(s, lower, upper, upper_inclusive) for s in std_ts]
    return df.loc[mask].reset_index(drop=True)


def wellness_reader(player_id: str, start_date: str, end_date=None) -> pd.DataFrame:
    """Daily wellness questionnaire rows in the time span."""
    return _filtered_frame(player_id, "wellness.csv", "effective_time_frame", start_date, end_date)


def srpe_reader(player_id: str, start_date: str, end_date=None) -> pd.DataFrame:
    """Session-RPE training rows whose end time falls in the time span."""
    return _filtered_frame(player_id, "srpe.csv", "end_date_time", start_date, end_date)


def _parse_injuries(raw) -> dict:
    if isinstance(raw, dict):
        return raw
    if raw is None or (isinstance(raw, float) and pd.isna(raw)):
        return {}
    text = str(raw).strip()
    if not text:
        return {}
    try:
        parsed = ast.literal_eval(text)
    except (SyntaxError, ValueError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def injury_reader(player_id: str, start_date: str, end_date=None) -> dict:
    """Injury reports as {standardized_ts: {body_part: severity}}."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _pmsys_file(player_id, "injury.csv")
    if path is None:
        return {}
    df = pd.read_csv(path)
    if df.empty or "effective_time_frame" not in df.columns:
        return {}
    out = {}
    for _, row in df.iterrows():
        ts_std = standardize_date(str(row["effective_time_frame"]))
        if not ts_std or not _matches(ts_std, lower, upper, upper_inclusive):
            continue
        out[ts_std] = _parse_injuries(row.get("injuries"))
    return out
