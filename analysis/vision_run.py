"""Gemini vision pass over all food-images: is_photo_food + same-meal validation.

STRICT variant: API/transport errors raise (never recorded as NO) with
429-aware backoff. Only model answers starting with YES/NO are accepted.

Resumable via analysis/tables/vision_cache.json. Run detached:
  setsid nohup .venv/bin/python -u analysis/vision_run.py > analysis/tables/vision_run.log 2>&1 < /dev/null &
"""
import json
import re
import sys
import time
import traceback
from pathlib import Path
from datetime import datetime

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))
DATA = REPO / "data"
TAB = REPO / "analysis" / "tables"
CACHE = TAB / "vision_cache.json"
TAB.mkdir(parents=True, exist_ok=True)

from src.data_handling import food_reader  # noqa: E402 (loads GEMINI_API_KEY via dotenv)
from PIL import Image, ExifTags  # noqa: E402

# Model string (changed by hand on 2026-09-17: gemini-3.5-flash-lite quota
# exhausted -> gemini-3.1-flash-lite for all subsequent labels; see §2C.4).
food_reader.MODEL_NAME = "gemini-3.1-flash-lite"

PARTICIPANTS = ["p01", "p03", "p05"]
# Data-derived threshold (by hand, 2026-09-17): aggregate inter-photo delta
# distribution (640 intervals) shows a dense left outlier cluster 0-15 s
# (n=43, burst shots) separated by a sparse valley (15-120 s, n=13) from the
# main inter-meal mass (rising again >=120 s). High limit of outlier = 15 s.
MEAL_TIMEDELTA = 15
PACE_SECONDS = 15          # delay between API calls to stay under rate limits
MAX_ATTEMPTS = 40         # per image/pair before giving up (cache saved; resume later)


def log(msg):
    print(f"[{datetime.now():%H:%M:%S}] {msg}", flush=True)


def load_cache():
    if CACHE.exists():
        return json.loads(CACHE.read_text())
    return {"is_food": {}, "same_meal": {}}


def save_cache(c):
    CACHE.write_text(json.dumps(c))


def retry_after_seconds(err_text, default=60):
    m = re.search(r"retry in ([\d.]+)s", err_text)
    if m:
        try:
            return min(float(m.group(1)) + 5, 300)
        except ValueError:
            pass
    return default


def strict_call(prompt, image_paths):
    """One Gemini call; returns 'yes'/'no'. Raises on any API/transport error
    or unexpected answer text (caller decides backoff)."""
    parts = [{"type": "text", "text": prompt}]
    for fp in image_paths:
        with open(fp, "rb") as fh:
            parts.append(food_reader._image_part(fp, fh.read()))
    response = food_reader.client.interactions.create(
        model=food_reader.MODEL_NAME, input=parts)
    answer = (response.output_text or "").strip().lower()
    if answer.startswith("yes"):
        return True
    if answer.startswith("no"):
        return False
    raise RuntimeError(f"Unexpected model answer: {answer[:200]!r}")


def strict_is_photo_food(fp):
    return strict_call(
        "Is this a photo of food or beverages meant for human consumption? "
        "Answer strictly 'YES' or 'NO'.", [fp])


def strict_is_same_meal(f1, d1, f2, d2):
    return strict_call(
        f"Look at these two photos. Photo 1 has been taken on {d1}. "
        f"Photo 2 has been taken on {d2}. Do they depict the same meal event? "
        "They might be different angles, slightly different plates from the same sitting, "
        "or a 'before and during' eating comparison. "
        "Answer strictly 'YES' or 'NO'.", [f1, f2])


def run_strict(kind, key, fn, *args):
    """Run fn strictly with 429-aware backoff. Returns (value, attempts)."""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            return fn(*args), attempt
        except Exception as e:  # noqa: BLE001
            text = repr(e)[:500]
            if "429" in text or "too_many_requests" in text.lower() or "quota" in text.lower():
                wait = retry_after_seconds(text)
                log(f"  429 ({kind} {key}) attempt {attempt}/{MAX_ATTEMPTS}: sleeping {wait:.0f}s")
                time.sleep(wait)
            else:
                log(f"  ERR ({kind} {key}) attempt {attempt}/{MAX_ATTEMPTS}: {text[:160]}")
                time.sleep(5 * attempt)
    raise RuntimeError(f"Gave up on {kind} {key} after {MAX_ATTEMPTS} attempts")


def exif_dt(path):
    try:
        with Image.open(path) as im:
            ex = im._getexif() or {}
            tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
            raw = tags.get("DateTime") or tags.get("DateTimeOriginal") or ""
            if raw:
                return datetime.strptime(raw, "%Y:%m:%d %H:%M:%S")
    except Exception:
        pass
    return None


def main():
    cache = load_cache()
    # Invalidate previously cached NOs recorded by the lenient pass (429s
    # were swallowed as False). Keep YES (a YES can only come from a real answer).
    dropped = [k for k, v in cache["is_food"].items() if not v.get("is_food")]
    for k in dropped:
        del cache["is_food"][k]
    if dropped:
        log(f"Invalidated {len(dropped)} lenient-pass NOs for strict re-check")
        save_cache(cache)

    # ---- Stage 1: strict is_photo_food for every image
    all_files = []
    for p in PARTICIPANTS:
        d = DATA / p / "food-images"
        all_files += sorted(str(f) for f in d.iterdir()
                            if f.suffix.lower() in (".jpg", ".jpeg", ".png"))
    todo = [fp for fp in all_files if fp not in cache["is_food"]]
    log(f"Stage 1: {len(all_files)} images, {len(all_files) - len(todo)} cached YES, {len(todo)} to do")
    for i, fp in enumerate(todo):
        val, _ = run_strict("is_food", Path(fp).name, strict_is_photo_food, fp)
        cache["is_food"][fp] = {"is_food": bool(val), "strict": True,
                                "model": food_reader.MODEL_NAME}
        time.sleep(PACE_SECONDS)
        if (i + 1) % 10 == 0:
            save_cache(cache)
            log(f"  ...{i + 1}/{len(todo)}")
    save_cache(cache)
    n_yes = sum(1 for v in cache["is_food"].values() if v["is_food"])
    log(f"Stage 1 done: {n_yes}/{len(all_files)} food")

    # ---- Stage 2: same-meal pairs (<=1800 s) among FOOD images with datetimes
    dated = {}
    for p in PARTICIPANTS:
        items = []
        for fp in sorted(str(f) for f in (DATA / p / "food-images").iterdir()
                         if f.suffix.lower() in (".jpg", ".jpeg", ".png")):
            if not cache["is_food"].get(fp, {}).get("is_food"):
                continue
            dt = exif_dt(fp)
            if dt:
                items.append((fp, dt))
        dated[p] = sorted(items, key=lambda x: x[1])
    pairs = []
    for p, items in dated.items():
        for i in range(len(items)):
            for j in range(i + 1, len(items)):
                if abs((items[i][1] - items[j][1]).total_seconds()) <= MEAL_TIMEDELTA:
                    pairs.append((p, items[i][0], str(items[i][1]),
                                  items[j][0], str(items[j][1])))
                else:
                    break
    todo_pairs = [(p, f1, d1, f2, d2) for (p, f1, d1, f2, d2) in pairs
                  if f"{f1}||{f2}" not in cache["same_meal"]]
    log(f"Stage 2: {len(pairs)} candidate pairs, {len(pairs) - len(todo_pairs)} cached, {len(todo_pairs)} to do")
    for k, (p, f1, d1, f2, d2) in enumerate(todo_pairs):
        val, _ = run_strict("same_meal", f"{Path(f1).name}+{Path(f2).name}",
                            strict_is_same_meal, f1, d1, f2, d2)
        cache["same_meal"][f"{f1}||{f2}"] = {"same_meal": bool(val), "p": p,
                                              "strict": True, "model": food_reader.MODEL_NAME}
        time.sleep(PACE_SECONDS)
        if (k + 1) % 10 == 0:
            save_cache(cache)
            log(f"  ...{k + 1}/{len(todo_pairs)}")
    save_cache(cache)
    n_same = sum(1 for v in cache["same_meal"].values() if v["same_meal"])
    log(f"Stage 2 done: {n_same}/{len(pairs)} same-meal")
    log("ALL DONE")


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001
        traceback.print_exc()
