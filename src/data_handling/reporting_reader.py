"""Reader and aggregator for the <player_id>/googledocs folder.

The daily self-reported nutrition log is tabular, so the reader returns
a ``pd.DataFrame`` filtered on the ``date`` column.

Every date comparison goes through ``standardize_date`` from
``src.utils.date_handler``. The reader takes ``(player_id, start_date,
end_date=None)``; when only ``start_date`` is given the whole calendar
day is returned.
"""

import re
from pathlib import Path

import pandas as pd

from src.utils.date_handler import standardize_date, _resolve_bounds, _is_date_only

_BASE_DIR = Path(__file__).resolve().parents[2]


def _matches(ts_std: str, lower: str, upper: str, upper_inclusive: bool) -> bool:
    if ts_std < lower:
        return False
    if upper_inclusive:
        return ts_std <= upper
    return ts_std < upper


def reporting_reader(player_id: str, start_date: str, end_date=None) -> pd.DataFrame:
    """Daily reporting rows whose ``date`` falls in the time span."""
    lower, upper, upper_inclusive = _resolve_bounds(start_date, end_date)
    path = _BASE_DIR / player_id / "googledocs" / "reporting.csv"
    if not path.is_file():
        return pd.DataFrame()
    df = pd.read_csv(path)
    if df.empty or "date" not in df.columns:
        return pd.DataFrame()
    std_dates = [standardize_date(str(v)) for v in df["date"]]
    mask = [bool(s) and _matches(s, lower, upper, upper_inclusive) for s in std_dates]
    return df.loc[mask].reset_index(drop=True)
