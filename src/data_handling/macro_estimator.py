"""Day-level macro-nutrient estimation with a persistent disk cache.

The training dataset needs *daily* kcal/macro totals. Rather than one
Gemini call per 15 s meal burst (~596 calls), this module makes one call
per participant-day with food photos (158 days), sending the
representative photo of each 15 s meal group in chronological order with
a day-total prompt. Results are cached on disk
(``output_dataset/macro_cache.json``) keyed by participant + day + photo
set, so rebuilds and retries never pay twice and interrupted runs resume.

The API key is read from the environment by ``food_reader.client`` at
import time; it is never logged or printed here.
"""

import json
import logging
import time
from pathlib import Path

MACRO_KEYS = ("calories", "protein", "carbohydrates", "fats")
CACHE_FILENAME = "macro_cache.json"
RETRY_ATTEMPTS = 3
RETRY_BACKOFF_S = 5
THROTTLE_S = 2

_BASE_DIR = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_PATH = _BASE_DIR / "output_dataset" / CACHE_FILENAME

DAY_MACRO_PROMPT = (
    "These photos show the distinct meals, snacks and drinks one person "
    "consumed during a single calendar day, in chronological order. "
    "Near-duplicate burst shots were already removed, so each photo is a "
    "different meal or moment of the day. "
    "Estimate the TOTAL for the whole day: calories, protein (in grams), "
    "carbohydrates (in grams), and fats (in grams). Be realistic about "
    "portion sizes visible in the photos."
)


def cache_path(path=None) -> Path:
    """Resolve the macro-cache file path (default under output_dataset)."""
    return Path(path) if path else DEFAULT_CACHE_PATH


def load_cache(path=None) -> dict:
    """Load the macro cache (empty dict when absent/corrupt)."""
    p = cache_path(path)
    if not p.is_file():
        return {}
    try:
        data = json.loads(p.read_text())
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError) as exc:
        logging.warning(f"Macro cache unreadable ({exc}); starting fresh.")
        return {}


def save_cache(cache: dict, path=None) -> Path:
    """Persist the macro cache to disk. Returns the cache path."""
    p = cache_path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(cache, indent=1, sort_keys=True))
    return p


def cache_key(player_id: str, day: str, photo_paths: list) -> str:
    """Stable cache key: participant + day + sorted photo basenames."""
    names = sorted(Path(p).name for p in (photo_paths or []))
    return f"{player_id}|{day}|{','.join(names)}"


def _coerce_macros(payload) -> dict:
    """Validate/coerce a raw macro payload; {} when unusable."""
    if not isinstance(payload, dict):
        return {}
    out = {}
    for key in MACRO_KEYS:
        try:
            value = float(payload.get(key))
        except (TypeError, ValueError):
            return {}
        if value != value or value < 0:  # NaN or negative
            return {}
        out[key] = value
    return out


def estimate_day_macros(photo_paths: list, client=None) -> dict:
    """Estimate whole-day macros for representative meal photos.

    Args:
        photo_paths: representative image paths (one per 15 s meal
            group), chronological.
        client: optional ``food_reader.client`` override (tests).

    Returns:
        ``{calories, protein, carbohydrates, fats}`` floats, or {} when
        the call fails or the payload is invalid (never raises).
    """
    if not photo_paths:
        return {}
    try:
        from src.data_handling import food_reader
        active_client = client or food_reader.client
        parts = []
        for file_path in photo_paths:
            with open(file_path, "rb") as fh:
                parts.append(food_reader._image_part(file_path, fh.read()))
        interaction = active_client.interactions.create(
            model=food_reader.MODEL_NAME,
            input=[{"type": "text", "text": DAY_MACRO_PROMPT}, *parts],
            response_format=food_reader.MACRO_RESPONSE_FORMAT,
        )
        return _coerce_macros(json.loads(interaction.output_text.strip()))
    except (OSError, ValueError, AttributeError, KeyError) as exc:
        logging.warning(f"Day macro estimation failed ({len(photo_paths)} photos): {exc}")
        return {}
    except Exception as exc:  # API transport errors must not kill the build
        logging.warning(f"Day macro estimation failed ({len(photo_paths)} photos): {exc}")
        return {}


def get_day_macros(player_id: str, day: str, photo_paths: list,
                   cache: dict, throttle: bool = True) -> dict:
    """Cached day-macro lookup with retry; updates ``cache`` in place.

    Returns the macro dict, or {} when unavailable (caller emits NaN +
    ``nutrition_kcal_available = 0``).
    """
    if not photo_paths:
        return {}
    key = cache_key(player_id, day, photo_paths)
    if key in cache and _coerce_macros(cache[key]):
        return dict(cache[key])
    macros = {}
    for attempt in range(1, RETRY_ATTEMPTS + 1):
        macros = estimate_day_macros(photo_paths)
        if macros:
            break
        logging.warning(f"Macro retry {attempt}/{RETRY_ATTEMPTS} for {player_id} {day}.")
        time.sleep(RETRY_BACKOFF_S * attempt)
    if macros:
        cache[key] = dict(macros)
        logging.info(f"Macros {player_id} {day}: {macros} (cache size: {len(cache)}).")
        if throttle:
            time.sleep(THROTTLE_S)
    else:
        logging.warning(f"No macro estimate for {player_id} {day}; leaving NaN.")
    return macros
