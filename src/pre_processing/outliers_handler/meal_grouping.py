"""Food-photo event grouping (framework §2, item 4).

Data-derived threshold: 15 s (dense 0-15 s shutter-burst cluster
separated from the inter-meal mass, see
``analysis/phase2c_food_injury.md §2C.2``). The legacy production
default (1800 s) over-merges (vision confirm rate 63.7 % vs ~73 % at
<= 300 s).

This module is deterministic and offline: it reuses the audited
per-image EXIF datetimes + ``is_food`` labels in
``analysis/tables/phase2c_food_files_*.csv`` when present, falling back
to live EXIF reads via ``food_reader``. No Gemini API calls are made
here; macro-nutrient estimation stays out of the training-dataset build
(the kcal/macro columns are emitted as NaN with an availability flag
until the vision macro step runs).
"""

import logging
import os
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.utils.date_handler import DATE_FORMAT

MEAL_THRESHOLD_S = 15
_BASE_DIR = Path(__file__).resolve().parents[3]
_TABLES_DIR = _BASE_DIR / "analysis" / "tables"
_DATA_DIR = _BASE_DIR / "data"

# Audited non-food captures (vision verdict NO) — excluded before grouping.
NON_FOOD_FILES = {
    "p01": {"IMG_9111.png", "IMG_9157.jpeg"},
    "p03": set(),
    "p05": {"IMG_2215.jpg", "IMG_2216.jpg", "IMG_2235.jpg"},
}


def _parse_std(value):
    """Parse a standardize_date string (or datetime) to datetime."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        return datetime.strptime(str(value), DATE_FORMAT)
    except (ValueError, TypeError):
        try:
            return datetime.strptime(str(value), "%Y-%m-%d %H:%M:%S")
        except (ValueError, TypeError):
            return None


def group_photos_to_meals(dated_files: list, threshold_s: int = MEAL_THRESHOLD_S) -> list:
    """Group (path, datetime) photo events into meal bursts.

    Union-find over consecutive sorted datetimes: photos <= threshold_s
    apart belong to one meal event (transitive closure).

    Args:
        dated_files: list of ``(path, datetime|std-string)`` tuples.
        threshold_s: gap threshold in seconds (default 15, derived).

    Returns:
        List of meals; each meal is a sorted list of file paths.
    """
    dated = []
    for path, stamp in dated_files or []:
        dt = _parse_std(stamp)
        if dt is None:
            logging.warning(f"No date info for photo, skipping: {path}")
            continue
        dated.append((path, dt))
    dated.sort(key=lambda kv: kv[1])
    if not dated:
        return []
    parent = list(range(len(dated)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(1, len(dated)):
        if abs((dated[i][1] - dated[i - 1][1]).total_seconds()) <= threshold_s:
            ri, rj = find(i - 1), find(i)
            if ri != rj:
                parent[max(ri, rj)] = min(ri, rj)
    groups = {}
    for i, (path, _) in enumerate(dated):
        groups.setdefault(find(i), []).append(path)
    return [sorted(paths) for paths in groups.values()]


def load_food_datetime_table(player_id: str) -> pd.DataFrame:
    """Load audited per-image datetimes + is_food labels for a player.

    Prefers ``analysis/tables/phase2c_food_files_<pid>.csv`` (complete
    audit, 100 % datetime coverage). Falls back to live EXIF reads.

    Returns:
        DataFrame with ``file, datetime, is_food`` columns.
    """
    path = _TABLES_DIR / f"phase2c_food_files_{player_id}.csv"
    if path.is_file():
        df = pd.read_csv(path)
        out = pd.DataFrame({
            "file": df["file"].astype(str),
            "datetime": pd.to_datetime(df["datetime"], errors="coerce"),
            "is_food": df["is_food"].astype(str).str.upper(),
        }).dropna(subset=["datetime"])
        return out.reset_index(drop=True)
    # Fallback: live EXIF scan (DateTime OR DateTimeOriginal).
    from src.data_handling import food_reader
    folder = _DATA_DIR / player_id / "food-images"
    rows = []
    if folder.is_dir():
        for name in sorted(os.listdir(folder)):
            if not name.lower().endswith((".jpg", ".jpeg", ".png")):
                continue
            meta = food_reader._read_image_metadata(str(folder / name))
            stamp = meta.get("DateTime") or meta.get("DateTimeOriginal") or ""
            dt = _parse_std(__import__("src.utils.date_handler", fromlist=["standardize_date"]).standardize_date(str(stamp)))
            if dt is None:
                continue
            rows.append({"file": name, "datetime": dt,
                         "is_food": "NO" if name in NON_FOOD_FILES.get(player_id, set()) else "YES"})
    return pd.DataFrame(rows, columns=["file", "datetime", "is_food"])


def list_photo_meals_for_day(player_id: str, day: str,
                               threshold_s: int = MEAL_THRESHOLD_S,
                               food_table: pd.DataFrame = None) -> list:
    """List 15 s meal events for one day as full image paths.

    Only ``is_food == YES`` captures are grouped (non-food quarantined).
    Each meal is a chronologically sorted list of absolute file paths;
    missing files are skipped with a warning.

    Args:
        player_id: e.g. ``"p01"``. day: ``YYYY-MM-DD`` string.
        threshold_s: burst threshold in seconds.
        food_table: optional pre-loaded ``load_food_datetime_table`` output.

    Returns:
        List of meals (each a list of absolute path strings).
    """
    table = food_table if food_table is not None else load_food_datetime_table(player_id)
    if table is None or len(table) == 0:
        return []
    mask = table["datetime"].dt.strftime("%Y-%m-%d") == day
    day_rows = table.loc[mask]
    food_rows = day_rows[day_rows["is_food"] == "YES"]
    if len(food_rows) == 0:
        return []
    folder = _DATA_DIR / player_id / "food-images"
    dated = []
    for _, row in food_rows.iterrows():
        full = str(folder / row["file"])
        if not Path(full).is_file():
            logging.warning(f"Food image missing on disk, skipping: {full}")
            continue
        stamp = row["datetime"]
        dt = stamp.to_pydatetime() if hasattr(stamp, "to_pydatetime") else stamp
        dated.append((full, dt))
    meals = group_photos_to_meals(dated, threshold_s)
    # Chronological order: members by shutter time, meals by first photo.
    order = {path: dt for path, dt in dated}
    meals = [sorted(meal, key=lambda p: order[p]) for meal in meals]
    meals.sort(key=lambda meal: order[meal[0]])
    return meals


def count_photo_meals_for_day(player_id: str, day: str,
                              threshold_s: int = MEAL_THRESHOLD_S,
                              food_table: pd.DataFrame = None) -> dict:
    """Count food photos and 15 s meal events for one calendar day.

    Args:
        player_id: e.g. ``"p01"``.
        day: ``YYYY-MM-DD`` string.
        threshold_s: burst threshold in seconds.
        food_table: optional pre-loaded ``load_food_datetime_table``
            output (avoids re-reading the CSV per day).

    Returns:
        Dict with ``n_photos`` (all captures that day),
        ``n_food_photos`` (``is_food == YES``), ``n_photo_meals``
        (15 s groups over food photos) and ``has_nutrition`` (bool,
        True when at least one food photo exists that day).
    """
    table = food_table if food_table is not None else load_food_datetime_table(player_id)
    if table is None or len(table) == 0:
        return {"n_photos": 0, "n_food_photos": 0, "n_photo_meals": 0, "has_nutrition": False}
    mask = table["datetime"].dt.strftime("%Y-%m-%d") == day
    day_rows = table.loc[mask]
    n_photos = int(len(day_rows))
    food_rows = day_rows[day_rows["is_food"] == "YES"]
    n_food = int(len(food_rows))
    meals = group_photos_to_meals(
        list(zip(food_rows["file"].tolist(), food_rows["datetime"].tolist())), threshold_s)
    return {"n_photos": n_photos, "n_food_photos": n_food,
            "n_photo_meals": len(meals), "has_nutrition": bool(n_food > 0)}
