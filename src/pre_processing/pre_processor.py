"""Pre-processing orchestrator (framework §1-§3).

This module is the single entry point for building the training-ready
dataset. It owns:

- §1 Data Type Management: timestamp standardisation, sentinel handling,
  categorical encoding, unit conversions, ``lag_days`` / ``weekend_bin``.
- Orchestration of §2 (``outliers_handler``) and §3
  (``missing_values_handler``) plus the additive ``aggregator.py``
  helpers for anything that is directly an aggregation.

Grain: one row per participant x calendar day over 2019-11-01 ->
2020-03-31 (3 x 152 = 456 rows).

Label (user-confirmed): ``readiness_next_day`` — the *next-day* cleaned
wellness readiness (causal). The same-day cleaned readiness
(``readiness_same_day``, i.e. "the day before" relative to the label) is
the single allowed readiness-derived feature. All other subjective
wellness items (fatigue, mood, sleep_duration_h, sleep_quality,
soreness, stress, soreness_area) are *excluded* from the dataset
entirely (see ``BANNED_SUBJECTIVE``).

Causality: every rolling feature uses windows ending on day D (known
when predicting the D+1 label). Tier-1 forward-fill never backfills.
"""

import logging
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from src.data_handling import aggregator, fitbit_reader, pmsys_reader, reporting_reader, macro_estimator
from src.data_handling.aggregator import CANONICAL_ACTIVITIES
from src.pre_processing.outliers_handler import sensor_artifacts, physio_bounds, nonwear, meal_grouping
from src.pre_processing.missing_values_handler import forward_fill, indicators
from src.utils.date_handler import standardize_date, DATE_FORMAT

BASE_DIR = Path(__file__).resolve().parents[2]
OUTPUT_DIR = BASE_DIR / "output_dataset"

HORIZON_START = "2019-11-01"
HORIZON_END = "2020-03-31"
MEAL_THRESHOLD_S = meal_grouping.MEAL_THRESHOLD_S  # 15 s, data-derived

# Wellness Likert scales observed in pmsys/wellness.csv. Values outside
# the valid range (notably 0 sentinels, e.g. 44 % of p05 readiness rows)
# are instrument defaults -> NaN. These columns are BANNED from the
# training features (user constraint); only readiness is kept, lagged.
LIKERT_1_5 = ("fatigue", "mood", "sleep_quality", "soreness", "stress")
BANNED_SUBJECTIVE = ("fatigue", "mood", "sleep_duration_h", "sleep_quality",
                     "soreness", "stress")

SUBMISSION_DELAYED_HOUR = 12  # hour >= 12 flags a recall-delayed row

# Columns eligible for Tier-1 causal forward-fill (<= 2 days).
TIER1_FFILL_COLS = ["weight_7d_median", "rhr_7d_median"]

# ---------------------------------------------------------------------------
# §1.1 Timestamp standardisation + lag_days / weekend_bin
# ---------------------------------------------------------------------------

def day_range(start: str = HORIZON_START, end: str = HORIZON_END) -> list:
    """List of ``YYYY-MM-DD`` calendar days from start to end inclusive."""
    start_d = datetime.strptime(standardize_date(start)[:10], "%Y-%m-%d")
    end_d = datetime.strptime(standardize_date(end)[:10], "%Y-%m-%d")
    days, cur = [], start_d
    while cur <= end_d:
        days.append(cur.strftime("%Y-%m-%d"))
        cur += timedelta(days=1)
    return days


def add_temporal_features(df: pd.DataFrame, date_col: str = "date") -> pd.DataFrame:
    """Add ``dow`` (Mon=0) and ``weekend_bin`` (Fri/Sat/Sun=1).

    Captures temporal clustering (e.g. post-match weekend drinking, see
    phase2b §2B.6). Pure calendar derivation, no leakage.
    """
    out = df.copy()
    dts = pd.to_datetime(out[date_col])
    out["dow"] = dts.dt.dayofweek.astype(int)
    out["weekend_bin"] = dts.dt.dayofweek.isin([4, 5, 6]).astype(int)
    return out


def reporting_lag_for_day(reporting_day: pd.DataFrame):
    """Mean ``lag_days`` (submission minus log date) for one day's rows.

    Proxies recall bias (logs are batch-submitted days/weeks late, see
    phase2b §2B.1). Returns None when no reporting row exists.
    """
    if reporting_day is None or len(reporting_day) == 0:
        return None
    lags = [aggregator.reporting_lag_days(r.get("date"), r.get("timestamp"))
            for _, r in reporting_day.iterrows()]
    lags = [v for v in lags if v is not None]
    return round(float(sum(lags) / len(lags)), 2) if lags else None


# ---------------------------------------------------------------------------
# §1.2 Sentinel value handling
# ---------------------------------------------------------------------------

def clean_wellness_frame(wellness_df: pd.DataFrame) -> pd.DataFrame:
    """Map wellness sentinels to NaN (returns a copy).

    Rules: 1-5 Likert items outside [1, 5] -> NaN; ``readiness`` 0 (or
    outside [1, 10]) -> NaN; ``sleep_duration_h`` <= 0 -> NaN. Adds a
    ``readiness_clean`` column; banned subjective columns are kept here
    for audit but dropped before the dataset is written.
    """
    out = wellness_df.copy()
    if len(out) == 0:
        out["readiness_clean"] = pd.Series(dtype=float)
        return out
    for col in LIKERT_1_5:
        if col in out.columns:
            v = pd.to_numeric(out[col], errors="coerce")
            out[col] = v.where((v >= 1) & (v <= 5))
    if "readiness" in out.columns:
        v = pd.to_numeric(out["readiness"], errors="coerce")
        out["readiness_clean"] = v.where((v >= 1) & (v <= 10))
    else:
        out["readiness_clean"] = np.nan
    if "sleep_duration_h" in out.columns:
        v = pd.to_numeric(out["sleep_duration_h"], errors="coerce")
        out["sleep_duration_h"] = v.where(v > 0)
    return out


def submission_hour(std_ts: str):
    """Hour-of-day float from a standardized timestamp (None on failure)."""
    try:
        dt = datetime.strptime(std_ts, DATE_FORMAT)
        return round(dt.hour + dt.minute / 60.0 + dt.second / 3600.0, 2)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# §1.3 Categorical encoding (§1.4 unit conversions live in aggregator.py:
# activeDuration ms -> min, distance in cm; see exercise_minutes/TRIMP).
# ---------------------------------------------------------------------------

def srpe_day_flags(srpe_day: pd.DataFrame) -> dict:
    """One-hot flags over ``CANONICAL_ACTIVITIES`` for one day's sRPE rows."""
    names = []
    for _, row in (srpe_day if srpe_day is not None else pd.DataFrame()).iterrows():
        names.extend(aggregator.parse_activity_names(row.get("activity_names")))
    lowered = [n.lower() for n in names]
    return {f"act_{c}": int(any(c in item for item in lowered)) for c in CANONICAL_ACTIVITIES}


def injury_onehots(injuries: dict) -> dict:
    """One-hot ``{location__severity}`` flags for an injury payload dict."""
    flags = {}
    for loc, sev in (injuries or {}).items():
        key = f"inj_{str(loc).strip().lower()}__{str(sev).strip().lower()}"
        flags[key] = 1
    return flags


# ---------------------------------------------------------------------------
# Static participant covariates (participant-overview.xlsx)
# ---------------------------------------------------------------------------

def load_participant_static(player_id: str) -> dict:
    """Load static covariates for one participant.

    Cleans: strips ``male\\xa0`` whitespace, maps the p14-style
    implausible stride-run (11.3 cm) to NaN via
    ``physio_bounds.clean_stride_run``, coerces mixed 5 km date formats
    to NaT (unused downstream). Missing overview rows -> NaNs.
    """
    path = BASE_DIR / "data" / "participant-overview.xlsx"
    cols = {"age": None, "height_cm": None, "gender": None, "chronotype": None,
            "max_hr": None, "stride_walk_cm": None, "stride_run_cm": None}
    try:
        xls = pd.read_excel(path, header=1)
        xls.columns = [str(c).strip().lower().replace(" ", "_") for c in xls.columns]
        id_col = next((c for c in xls.columns if "participant" in c), None)
        row = xls[xls[id_col].astype(str).str.strip() == player_id] if id_col else pd.DataFrame()
        if len(row) == 0:
            return cols
        r = row.iloc[0]
        gender = str(r.get("gender", "")).replace("\xa0", " ").strip().lower() or None
        chrono = str(r.get("a_or_b_person", "")).strip().upper() or None
        cols.update({
            "age": _num(r.get("age")), "height_cm": _num(r.get("height")),
            "gender": gender, "chronotype": chrono,
            "max_hr": _num(r.get("max_heart_rate")),
            "stride_walk_cm": _num(r.get("stride_walk")),
            "stride_run_cm": physio_bounds.clean_stride_run(r.get("stride_run")),
        })
    except (OSError, ValueError) as exc:
        logging.warning(f"Static overview unavailable ({exc}); using NaNs.")
    return cols


def _num(value):
    try:
        v = float(value)
        return None if np.isnan(v) else v
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# Bulk preload (one file read per source per participant)
# ---------------------------------------------------------------------------

def _preload_participant(player_id: str, start: str, end: str,
                         macro_cache: dict = None) -> dict:
    """Load full-horizon data once per participant.

    Heavy minute/HR JSONs are read a single time and indexed by day;
    light sources go through the standard readers with full-horizon
    bounds and are sliced in memory per day. Applies §2 cleaning that
    is global (DST dedupe, HR confidence filter + clip). The shared
    day-macro cache (loaded once per build) is attached for the
    nutrition estimator; a fresh dict is used when None.
    """
    logging.info(f"[{player_id}] loading full-horizon sources ...")
    steps_raw = fitbit_reader.steps_reader(player_id, start, end)
    dist_raw = fitbit_reader.distance_reader(player_id, start, end)
    cal_raw = fitbit_reader.calories_reader(player_id, start, end)
    steps, n_dedup_steps = sensor_artifacts.dedupe_minute_series(steps_raw)
    dist, n_dedup_dist = sensor_artifacts.dedupe_minute_series(dist_raw)
    cal, _ = sensor_artifacts.dedupe_minute_series(cal_raw)

    # Per-day dedupe counts (DST audit trail).
    dedup_by_day = {}
    for label, raw, clean in (("s", steps_raw, steps), ("d", dist_raw, dist)):
        if raw is not None and len(raw):
            raw_c = raw.index.strftime("%Y-%m-%d").value_counts().to_dict()
            cln_c = clean.index.strftime("%Y-%m-%d").value_counts().to_dict() if len(clean) else {}
            for d, c in raw_c.items():
                dedup_by_day[d] = dedup_by_day.get(d, 0) + (c - cln_c.get(d, 0))

    hr_raw = fitbit_reader.heart_rate_reader(player_id, start, end)
    hr_conf, n_conf_dropped, _ = sensor_artifacts.filter_low_confidence_hr(hr_raw)
    hr_clean, n_clipped_total = physio_bounds.clip_hr_bpm(hr_conf)
    hr_by_day: dict = {}
    clip_by_day: dict = {}
    # NOTE: n_clipped is a global count; per-day attribution counts the
    # clipped values' days via a second pass over the pre-clip dict.
    clipped_keys = set()
    for ts, payload in hr_conf.items():
        bpm = payload.get("bpm") if isinstance(payload, dict) else None
        try:
            f = float(bpm)
            if f < physio_bounds.HR_LO_BPM or f > physio_bounds.HR_HI_BPM:
                clipped_keys.add(ts)
        except (TypeError, ValueError):
            pass
    for ts, payload in hr_clean.items():
        day = ts[:10]
        hr_by_day.setdefault(day, {})[ts] = payload
        if ts in clipped_keys:
            clip_by_day[day] = clip_by_day.get(day, 0) + 1
    hr_available = (BASE_DIR / "data" / player_id / "fitbit" / "heart_rate.json").is_file()

    rhr_raw = fitbit_reader.resting_heart_rate_reader(player_id, start, end)
    rhr_by_day = {}
    for ts, payload in (rhr_raw or {}).items():
        rhr_by_day[ts[:10]] = physio_bounds.clean_resting_hr_value(payload)

    zones_raw = fitbit_reader.time_in_heart_rate_zones_reader(player_id, start, end)
    zones_by_day = {ts[:10]: dict(v or {}) for ts, v in (zones_raw or {}).items()}

    exercise_raw = fitbit_reader.exercise_reader(player_id, start, end)
    exercise_by_day: dict = {}
    for rec in (exercise_raw or {}).values():
        std = standardize_date(str(rec.get("startTime", "")))
        if std:
            exercise_by_day.setdefault(std[:10], []).append(rec)

    wellness = clean_wellness_frame(pmsys_reader.wellness_reader(player_id, start, end))
    if len(wellness):
        wellness["_std"] = [standardize_date(str(v)) for v in wellness["effective_time_frame"]]
        wellness["_day"] = [s[:10] if s else "" for s in wellness["_std"]]
        wellness["_hour"] = [submission_hour(s) for s in wellness["_std"]]
    srpe = pmsys_reader.srpe_reader(player_id, start, end)
    if len(srpe):
        srpe["_std"] = [standardize_date(str(v)) for v in srpe["end_date_time"]]
        srpe["_day"] = [s[:10] if s else "" for s in srpe["_std"]]
        rpe = pd.to_numeric(srpe["perceived_exertion"], errors="coerce")
        dur = pd.to_numeric(srpe["duration_min"], errors="coerce")
        srpe["_load"] = (rpe * dur).where(rpe.notna() & dur.notna())
    injury = pmsys_reader.injury_reader(player_id, start, end) or {}
    injury_by_day: dict = {}
    for ts, payload in injury.items():
        injury_by_day.setdefault(ts[:10], []).append(payload)
    reporting = reporting_reader.reporting_reader(player_id, start, end)
    if len(reporting):
        reporting["_std_date"] = [standardize_date(str(v)) for v in reporting["date"]]
        reporting["_day"] = [s[:10] if s else "" for s in reporting["_std_date"]]
    sleep_score = fitbit_reader.sleep_score_reader(player_id, start, end)
    food_table = meal_grouping.load_food_datetime_table(player_id)
    static = load_participant_static(player_id)
    if macro_cache is None:
        macro_cache = macro_estimator.load_cache()
    logging.info(f"[{player_id}] loaded (dedup steps/dist: {n_dedup_steps}/{n_dedup_dist}; "
                 f"HR conf-0 dropped: {n_conf_dropped}; HR clipped: {n_clipped_total}).")
    return {"steps": steps, "distance": dist, "calories": cal, "dedup_by_day": dedup_by_day,
            "hr_by_day": hr_by_day, "clip_by_day": clip_by_day, "hr_available": hr_available,
            "n_conf_dropped": n_conf_dropped, "rhr_by_day": rhr_by_day,
            "zones_by_day": zones_by_day, "exercise_by_day": exercise_by_day,
            "wellness": wellness, "srpe": srpe, "injury_by_day": injury_by_day,
            "reporting": reporting, "sleep_score": sleep_score,
            "food_table": food_table, "static": static,
            "macro_cache": macro_cache}


def _day_slice_series(series: pd.Series, day: str) -> pd.Series:
    """Slice a DatetimeIndex series to one calendar day (empty if none)."""
    if series is None or len(series) == 0:
        return pd.Series(dtype=float)
    try:
        out = series.loc[day]
        return out if isinstance(out, pd.Series) else pd.Series(dtype=float)
    except KeyError:
        return pd.Series(dtype=float)


# ---------------------------------------------------------------------------
# Daily row builder
# ---------------------------------------------------------------------------

ZONE_KEYS = ("BELOW_DEFAULT_ZONE_1", "IN_DEFAULT_ZONE_1",
             "IN_DEFAULT_ZONE_2", "IN_DEFAULT_ZONE_3")


def build_daily_row(player_id: str, day: str, pre: dict,
                    meal_timedelta: int = MEAL_THRESHOLD_S) -> dict:
    """Build the base (pre-rolling) feature dict for one participant-day.

    Applies §1 type handling + §2 outlier handling, then aggregates via
    the ``aggregator.py`` helpers and the readers' day slices. Rolling
    features, Tier-1/2 missingness and the causal label are added later
    at frame level (they need neighbouring days).
    """
    row = {"participant_id": player_id, "date": day}

    # --- Activity (Fitbit minute series, deduped at preload) ---
    steps_day = _day_slice_series(pre["steps"], day)
    dist_day = _day_slice_series(pre["distance"], day)
    cal_day = _day_slice_series(pre["calories"], day)
    row["total_steps"] = float(steps_day.sum()) if len(steps_day) else 0.0
    row["peak_1min_steps"] = float(steps_day.max()) if len(steps_day) else 0.0
    row["steps_cov_min"] = int(len(steps_day))
    row["n_deduped_min"] = int(pre["dedup_by_day"].get(day, 0))
    row["total_distance_cm"] = float(dist_day.sum()) if len(dist_day) else 0.0
    row["total_distance_m"] = round(row["total_distance_cm"] / 100.0, 2)
    row["total_kcal"] = float(cal_day.sum()) if len(cal_day) else 0.0

    # --- Exercise bouts (ms -> min, artifact drop) + activity one-hots ---
    ex_list = pre["exercise_by_day"].get(day, [])
    ex = aggregator.exercise_minutes(ex_list)
    row["exercise_min"] = ex["exercise_min"]
    row["n_exercise_sessions"] = ex["n_exercise_sessions"]

    # --- Heart rate (confidence-filtered + clipped at preload) ---
    hr_day = pre["hr_by_day"].get(day, {})
    stats = aggregator.aggregate_hr_stats(hr_day)
    row.update(stats)
    row["n_clipped_hr"] = int(pre["clip_by_day"].get(day, 0))

    # --- Non-wear masking (§2) ---
    nw = nonwear.compute_nonwear_day(steps_day, hr_day,
                                     hr_available=pre["hr_available"], day=day)
    row["nonwear_min"] = nw["nonwear_min"]
    row["nonwear_hours"] = nw["nonwear_hours"]
    row["has_nonwear"] = int(nw["has_nonwear"])
    row["nonwear_is_upper_bound"] = int(not pre["hr_available"])

    # --- RHR sentinel-cleaned (§1.2/§2) ---
    row["rhr_raw"] = pre["rhr_by_day"].get(day, np.nan)

    # --- HR zones + Edwards TRIMP ---
    zones = pre["zones_by_day"].get(day)
    if zones is None:
        row["zones_available"] = 0
        for z in ZONE_KEYS:
            row[f"zone_min_{z}"] = np.nan
        row["trimp_edwards"] = np.nan
        row["time_ge85_min"] = np.nan
    else:
        row["zones_available"] = 1
        for z in ZONE_KEYS:
            row[f"zone_min_{z}"] = float(zones.get(z, 0.0) or 0.0)
        row["trimp_edwards"] = aggregator.trimp_edwards(zones)
        row["time_ge85_min"] = float(zones.get("IN_DEFAULT_ZONE_3", 0.0) or 0.0)

    # --- Sleep (extended aggregator; morning-attributed, classic-aware) ---
    sleep = aggregator.aggregate_sleep_daily(player_id, day)
    row["n_nights"] = sleep["n_nights"]
    row["n_naps"] = sleep["n_naps"]
    row["has_sleep_record"] = int(sleep["has_sleep_record"])
    row["is_classic"] = (int(sleep["is_classic"]) if sleep["is_classic"] is not None else np.nan)
    for key in ("asleep_min", "time_in_bed_min", "efficiency_pct", "deep_min",
                "light_min", "rem_min", "wake_min", "deep_pct", "light_pct",
                "rem_pct", "wake_pct", "onset_hour", "offset_hour", "midsleep_hour",
                "mean_overall_score", "mean_composition_score",
                "mean_revitalization_score", "mean_duration_score",
                "mean_deep_sleep_in_minutes", "mean_restlessness"):
        row[key] = sleep.get(key)

    # --- Wellness: counts + allowed lagged readiness only ---
    wellness = pre["wellness"]
    wday = wellness[wellness["_day"] == day] if len(wellness) else wellness
    row["n_wellness_rows"] = int(len(wday))
    if len(wday):
        last = wday.iloc[-1]
        row["readiness_same_day"] = _num_or_nan(last.get("readiness_clean"))
        hour = last.get("_hour")
        row["submission_hour"] = hour
        row["delayed_flag_ge12"] = (int(hour >= SUBMISSION_DELAYED_HOUR)
                                    if hour is not None else 0)
    else:
        row["readiness_same_day"] = np.nan
        row["submission_hour"] = np.nan
        row["delayed_flag_ge12"] = 0

    # --- sRPE training load ---
    srpe = pre["srpe"]
    sday = srpe[srpe["_day"] == day] if len(srpe) else srpe
    row["srpe_n_sessions"] = int(len(sday))
    if len(sday):
        valid_loads = pd.to_numeric(sday["_load"], errors="coerce").dropna()
        row["srpe_load"] = round(float(valid_loads.sum()), 1) if len(valid_loads) else np.nan
        rpes = pd.to_numeric(sday["perceived_exertion"], errors="coerce").dropna()
        row["mean_rpe"] = round(float(rpes.mean()), 2) if len(rpes) else np.nan
    else:
        row["srpe_load"] = 0.0
        row["mean_rpe"] = np.nan

    # --- Activity one-hots: exercise ∪ sRPE names (OR semantics) ---
    ex_flags = aggregator.canonical_activity_flags(ex["activities"])
    sr_flags = srpe_day_flags(sday)
    for c in CANONICAL_ACTIVITIES:
        row[f"act_{c}"] = int(ex_flags[f"act_{c}"] or sr_flags[f"act_{c}"])

    # --- Injury (events; same-day + history for lagged flag later) ---
    reports = pre["injury_by_day"].get(day, [])
    row["is_injured_day"] = int(any(bool(v) for v in reports))
    row["n_injury_reports"] = int(len(reports))
    merged: dict = {}
    for payload in reports:
        merged.update(payload or {})
    row.update(injury_onehots(merged))

    # --- Reporting (objective quantities + recall lag) ---
    reporting = pre["reporting"]
    rday = reporting[reporting["_day"] == day] if len(reporting) else reporting
    row["n_reporting_rows"] = int(len(rday))
    if len(rday):
        w = pd.to_numeric(rday["weight"], errors="coerce").dropna()
        row["weight_raw"] = float(w.iloc[-1]) if len(w) else np.nan
        row["fluids_glasses"] = float(pd.to_numeric(
            rday["glasses_of_fluid"], errors="coerce").fillna(0).sum())
        bins = [aggregator.alcohol_to_bin(v) for v in rday["alcohol_consumed"]]
        bins = [b for b in bins if b is not None]
        row["alcohol_bin"] = int(max(bins)) if bins else np.nan
        meals_logged = []
        if "meals" in rday.columns:
            for cell in rday["meals"].dropna():
                meals_logged.extend([m.strip() for m in str(cell).split(",") if m.strip()])
        row["n_meals_logged"] = int(len(meals_logged))
        row["lag_days"] = reporting_lag_for_day(rday)
    else:
        row["weight_raw"] = np.nan
        row["fluids_glasses"] = np.nan
        row["alcohol_bin"] = np.nan
        row["n_meals_logged"] = 0
        row["lag_days"] = np.nan

    # --- Nutrition: deterministic 15 s photo-meal counts + day macros ---
    # Counts are offline (audited EXIF + is_food labels). Day macros come
    # from one cached Gemini call per food-day over the representative
    # photo of each 15 s meal group (chronological); failures stay NaN
    # with nutrition_kcal_available = 0 (Tier-2 style, never zero-filled).
    food = meal_grouping.count_photo_meals_for_day(
        player_id, day, meal_timedelta, pre["food_table"])
    row["n_photos"] = food["n_photos"]
    row["n_food_photos"] = food["n_food_photos"]
    row["n_photo_meals"] = food["n_photo_meals"]
    row["has_nutrition"] = int(food["has_nutrition"])
    row["estimated_kcal"] = np.nan
    row["protein_g"] = np.nan
    row["carbs_g"] = np.nan
    row["fat_g"] = np.nan
    row["nutrition_kcal_available"] = 0
    if food["has_nutrition"]:
        meals = meal_grouping.list_photo_meals_for_day(
            player_id, day, meal_timedelta, pre["food_table"])
        representatives = [meal[0] for meal in meals if meal]
        cache = pre.get("macro_cache")
        if not isinstance(cache, dict):
            cache = {}
            pre["macro_cache"] = cache
        macros = macro_estimator.get_day_macros(player_id, day, representatives, cache)
        if macros:
            row["estimated_kcal"] = float(macros["calories"])
            row["protein_g"] = float(macros["protein"])
            row["carbs_g"] = float(macros["carbohydrates"])
            row["fat_g"] = float(macros["fats"])
            row["nutrition_kcal_available"] = 1

    # --- Static covariates (with overfit caveat, n=3 participants) ---
    row.update(pre["static"])
    return row


def _num_or_nan(value):
    try:
        v = float(value)
        return v if not np.isnan(v) else np.nan
    except (TypeError, ValueError):
        return np.nan


# ---------------------------------------------------------------------------
# Frame-level: rolling features (causal), missingness, label
# ---------------------------------------------------------------------------

def add_rolling_load_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add causal trailing-7d/28d load features (Foster + ACWR).

    ``load_7d_sum/mean``, ``monotony_7d = mean/sd`` (NaN when sd == 0 —
    degenerate for p03/p05 sparse logs), ``strain_7d = sum * monotony``,
    ``acwr_7_28 = 7d_mean / 28d_mean`` (NaN when denominator is 0/NaN).
    Windows end on D: causal for the D+1 label.
    """
    out = df.sort_values(["participant_id", "date"]).reset_index(drop=True)
    g = out.groupby("participant_id", sort=False)["srpe_load"]
    roll7 = g.transform(lambda s: s.rolling(7, min_periods=1).sum())
    mean7 = g.transform(lambda s: s.rolling(7, min_periods=1).mean())
    sd7 = g.transform(lambda s: s.rolling(7, min_periods=1).std())
    mean28 = g.transform(lambda s: s.rolling(28, min_periods=1).mean())
    out["load_7d_sum"] = roll7.round(1)
    out["load_7d_mean"] = mean7.round(1)
    monotony = (mean7 / sd7).where(sd7.fillna(0) != 0)
    out["monotony_7d"] = monotony.round(2)
    out["strain_7d"] = (roll7 * monotony).round(1)
    out["acwr_7_28"] = (mean7 / mean28).where(mean28.fillna(0) != 0).round(2)
    # Lagged injury exposure flag (recurrent-episode safe).
    inj = pd.to_numeric(out["is_injured_day"], errors="coerce").fillna(0)
    out["injured_last_7d"] = inj.groupby(out["participant_id"]).transform(
        lambda s: s.rolling(7, min_periods=1).max()).astype(int)
    return out


def add_slow_median_features(df: pd.DataFrame) -> pd.DataFrame:
    """Add causal 7-day medians + residuals for weight and RHR."""
    out = df.sort_values(["participant_id", "date"]).reset_index(drop=True)
    for col, med in (("weight_raw", "weight_7d_median"), ("rhr_raw", "rhr_7d_median")):
        if col not in out.columns:
            continue
        s = pd.to_numeric(out[col], errors="coerce")
        median = s.groupby(out["participant_id"]).transform(
            lambda x: x.rolling(7, min_periods=1).median())
        out[med] = median.round(2)
        out[f"{med.replace('_7d_median', '')}_residual"] = (s - median).round(2)
    return out


def add_causal_label(df: pd.DataFrame) -> pd.DataFrame:
    """Add the causal label ``readiness_next_day`` (+ availability flag).

    Label(D) = cleaned readiness(D+1) within participant. The feature
    ``readiness_same_day``(D) is "the day before" relative to the label
    and therefore causal (user-confirmed revision).
    """
    out = df.sort_values(["participant_id", "date"]).reset_index(drop=True)
    out["readiness_next_day"] = out.groupby("participant_id", sort=False)[
        "readiness_same_day"].shift(-1)
    out["label_available"] = out["readiness_next_day"].notna().astype(int)
    return out


def build_participant_frame(player_id: str, start: str = HORIZON_START,
                            end: str = HORIZON_END,
                            meal_timedelta: int = MEAL_THRESHOLD_S,
                            macro_cache: dict = None) -> pd.DataFrame:
    """Build the base daily frame (one row/day) for one participant.

    Args:
        macro_cache: shared day-macro cache (loaded once per build and
            persisted progressively; a fresh dict when None).
    """
    pre = _preload_participant(player_id, start, end, macro_cache)
    rows = [build_daily_row(player_id, d, pre, meal_timedelta) for d in day_range(start, end)]
    frame = pd.DataFrame(rows)
    frame = add_rolling_load_features(frame)
    frame = add_slow_median_features(frame)
    return frame


def build_training_dataset(players: list = None, start: str = HORIZON_START,
                           end: str = HORIZON_END,
                           meal_timedelta: int = MEAL_THRESHOLD_S) -> pd.DataFrame:
    """Build the full training-ready dataset for all players.

    Pipeline: bulk load + clean (§2) -> daily aggregation (aggregator
    helpers + cached Gemini day macros) -> causal rolling -> Tier-1 ffill
    (<= 2d, no backfill) -> Tier-2 indicators -> temporal features ->
    causal label. Returns the final frame with stable column order. The
    macro cache is saved after each participant so interrupted runs resume.
    """
    players = players or ["p01", "p03", "p05"]
    macro_cache = macro_estimator.load_cache()
    frames = []
    for pid in players:
        logging.info(f"Building daily frame for {pid} ...")
        frames.append(build_participant_frame(pid, start, end, meal_timedelta, macro_cache))
        macro_estimator.save_cache(macro_cache)
    # Align sparse one-hot columns pre-concat so absent flags are 0, not
    # NaN (e.g. p03 has no injury events; avoids all-NA concat warnings).
    all_cols: list = []
    for frame in frames:
        for col in frame.columns:
            if col not in all_cols:
                all_cols.append(col)
    inj_union = sorted({c for c in all_cols if c.startswith("inj_")})
    aligned = []
    for frame in frames:
        frame = frame.copy()
        for col in inj_union:
            if col not in frame.columns:
                frame[col] = 0
        aligned.append(frame)
    df = pd.concat(aligned, ignore_index=True)
    for col in inj_union:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)
    df = forward_fill.causal_forward_fill(df, TIER1_FFILL_COLS)
    df = indicators.add_presence_flags(df)
    df = indicators.add_rolling_missing_ratios(df, window=7)
    df = indicators.add_window_stats(df, ["total_steps", "exercise_min"], window=7)
    df = add_temporal_features(df)
    df = add_causal_label(df)
    return df[ordered_columns(df)]


def ordered_columns(df: pd.DataFrame) -> list:
    """Stable column order: keys, label, features. Keeps any extras last."""
    preferred = [
        "participant_id", "date", "dow", "weekend_bin",
        "readiness_next_day", "label_available", "readiness_same_day",
        "age", "height_cm", "gender", "chronotype", "max_hr",
        "stride_walk_cm", "stride_run_cm",
        "total_steps", "peak_1min_steps", "steps_cov_min", "n_deduped_min",
        "total_distance_cm", "total_distance_m", "total_kcal",
        "exercise_min", "n_exercise_sessions",
        "act_individual", "act_running", "act_endurance", "act_strength",
        "act_team", "act_soccer", "act_walk", "act_bike",
        "srpe_n_sessions", "srpe_load", "mean_rpe",
        "load_7d_sum", "load_7d_mean", "monotony_7d", "strain_7d", "acwr_7_28",
        "trimp_edwards",
        "hr_mean", "hr_sd", "hr_peak", "hr_n_samples", "mean_conf", "hr_cov_min",
        "n_clipped_hr", "nonwear_min", "nonwear_hours", "has_nonwear",
        "nonwear_is_upper_bound",
        "rhr_raw", "rhr_7d_median", "rhr_residual", "was_imputed_rhr_7d_median",
        "zone_min_BELOW_DEFAULT_ZONE_1", "zone_min_IN_DEFAULT_ZONE_1",
        "zone_min_IN_DEFAULT_ZONE_2", "zone_min_IN_DEFAULT_ZONE_3",
        "zones_available", "time_ge85_min",
        "n_nights", "n_naps", "has_sleep_record", "is_classic",
        "asleep_min", "time_in_bed_min", "efficiency_pct",
        "deep_min", "light_min", "rem_min", "wake_min",
        "deep_pct", "light_pct", "rem_pct", "wake_pct",
        "onset_hour", "offset_hour", "midsleep_hour",
        "mean_overall_score", "mean_composition_score",
        "mean_revitalization_score", "mean_duration_score",
        "mean_deep_sleep_in_minutes", "mean_restlessness",
        "n_wellness_rows", "has_wellness", "submission_hour", "delayed_flag_ge12",
        "n_reporting_rows", "weight_raw", "weight_7d_median", "weight_residual",
        "was_imputed_weight_7d_median", "fluids_glasses", "alcohol_bin",
        "lag_days", "n_meals_logged",
        "n_photos", "n_food_photos", "n_photo_meals", "has_nutrition",
        "estimated_kcal", "protein_g", "carbs_g", "fat_g",
        "nutrition_kcal_available",
        "is_injured_day", "n_injury_reports", "injured_last_7d",
        "missing_ratio_wellness_7d", "missing_ratio_weight_7d",
        "missing_ratio_zones_7d", "missing_ratio_sleep_7d", "missing_ratio_srpe_7d",
        "has_steps", "has_hr", "has_zones", "has_sleep",
        "total_steps_mean_7d", "total_steps_median_7d", "total_steps_std_7d",
        "exercise_min_mean_7d", "exercise_min_median_7d", "exercise_min_std_7d",
    ]
    # Injury one-hot columns (sparse, participant-specific) go after the core.
    inj_cols = sorted([c for c in df.columns if c.startswith("inj_")])
    ordered = [c for c in preferred if c in df.columns] + inj_cols
    ordered += [c for c in df.columns if c not in ordered]
    return ordered


# Columns kept in the CSV but excluded from the modelling features X
# (used_in_X = 0 in the data dictionary): keys, label/audit helpers, and
# exact-duplicate derivations (total_distance_m duplicates
# total_distance_cm; the /100 conversion was added only for this dataset).
# Day macros ARE features: they are estimated with Gemini (cached) during
# the build (see macro_estimator).
EXCLUDED_FROM_X = {"participant_id", "date", "readiness_next_day", "label_available",
                   "total_distance_m"}


def get_feature_columns(df: pd.DataFrame) -> list:
    """Return the modelling feature columns (X): everything except
    ``EXCLUDED_FROM_X``. ``readiness_same_day`` IS included (causal
    lagged feature, confirmed).
    """
    return [c for c in df.columns if c not in EXCLUDED_FROM_X]


# ---------------------------------------------------------------------------
# Output + data dictionary
# ---------------------------------------------------------------------------

COLUMN_DOCS = {
    "participant_id": ("key", "Participant identifier (p01/p03/p05).", "as-is", 0),
    "date": ("key", "Calendar day YYYY-MM-DD (device-local).", "daily grid", 0),
    "dow": ("temporal", "Day of week Mon=0..Sun=6.", "calendar derivation", 1),
    "weekend_bin": ("temporal", "1 when Fri/Sat/Sun (temporal clustering).", "calendar derivation", 1),
    "readiness_next_day": ("label", "LABEL: next-day cleaned readiness (0 sentinel -> NaN, shifted -1).", "sentinel 0->NaN; causal shift", 0),
    "label_available": ("audit", "1 when the label is known.", "label non-null", 0),
    "readiness_same_day": ("wellness", "Cleaned same-day readiness; causal lagged feature for the D+1 label.", "sentinel 0->NaN", 1),
    "total_steps": ("activity", "Daily step sum (missing minutes = 0 with steps_cov_min gate).", "DST dedupe keep-first", 1),
    "peak_1min_steps": ("activity", "Peak 1-minute step count.", "DST dedupe", 1),
    "steps_cov_min": ("coverage", "Minutes with a steps row (<=1440).", "dedupe; missing=0 steps", 1),
    "n_deduped_min": ("qc", "Duplicate minute rows dropped that day (DST audit).", "keep-first", 1),
    "total_distance_cm": ("activity", "Daily distance sum, centimetres.", "standardised to cm", 1),
    "total_distance_m": ("activity", "Daily distance in metres (exact duplicate of total_distance_cm; unused).", "/100", 0),
    "total_kcal": ("activity", "Daily calorie sum (gap-filled export; not a wear signal).", "pass-through", 1),
    "exercise_min": ("activity", "Exercise minutes (activeDuration ?? duration ms->min /60000; <=0.03 min dropped).", "unit conversion + artifact drop", 1),
    "n_exercise_sessions": ("activity", "Exercise bouts that day.", "artifact drop", 1),
    "srpe_n_sessions": ("load", "sRPE-logged sessions ending that day.", "end-time attribution", 1),
    "srpe_load": ("load", "sRPE load = RPE x duration summed (0 = no session; NaN = sessions without valid RPE/duration).", "NaN load when RPE/duration missing", 1),
    "mean_rpe": ("load", "Mean session RPE that day.", "valid-only mean", 1),
    "load_7d_sum": ("load", "Trailing-7d sRPE load sum (causal).", "rolling ending D", 1),
    "load_7d_mean": ("load", "Trailing-7d sRPE load mean (causal).", "rolling ending D", 1),
    "monotony_7d": ("load", "Foster monotony mean/sd over 7d (NaN when sd=0; degenerate for p03/p05).", "rolling ending D", 1),
    "strain_7d": ("load", "Strain = 7d sum x monotony.", "rolling ending D", 1),
    "acwr_7_28": ("load", "ACWR = 7d mean / 28d mean (p01 only stable).", "rolling ending D", 1),
    "trimp_edwards": ("load", "Edwards TRIMP from HR zones (weights 1/2/3/4).", "zone renormalisation", 1),
    "hr_mean": ("cardiac", "Mean of cleaned continuous HR samples.", "conf-0 drop; clip [30,220]", 1),
    "hr_sd": ("cardiac", "SD of cleaned continuous HR samples.", "conf-0 drop; clip [30,220]", 1),
    "hr_peak": ("cardiac", "Daily peak HR.", "conf-0 drop; clip [30,220]", 1),
    "hr_n_samples": ("coverage", "Kept HR samples that day.", "conf-0 drop", 1),
    "mean_conf": ("coverage", "Mean Fitbit confidence of kept HR samples.", "conf-0 drop", 1),
    "hr_cov_min": ("coverage", "Distinct minutes with >=1 HR sample.", "conf-0 drop", 1),
    "n_clipped_hr": ("qc", "HR samples clipped to [30,220] that day.", "physio clip", 1),
    "nonwear_min": ("wear", "Non-wear minutes (>=60-min runs of zero steps + missing/flat HR).", "non-wear masking", 1),
    "nonwear_hours": ("wear", "Non-wear hours.", "non-wear masking", 1),
    "has_nonwear": ("wear", "1 when any long non-wear run exists that day.", "non-wear masking", 1),
    "nonwear_is_upper_bound": ("wear", "1 for p03 (no HR file; steps-only upper bound).", "structural flag", 1),
    "rhr_raw": ("cardiac", "Cleaned resting HR (0.0/null-date sentinel -> NaN).", "sentinel -> NaN", 1),
    "rhr_7d_median": ("cardiac", "Causal 7d median RHR + Tier-1 ffill <=2d.", "rolling median; ffill limit 2, no backfill", 1),
    "rhr_residual": ("cardiac", "rhr_raw minus 7d median.", "causal residual", 1),
    "zones_available": ("coverage", "1 when a zones row exists that day.", "NaN preserved, not zero-filled", 1),
    "time_ge85_min": ("cardiac", "Minutes >=85% max (IN_DEFAULT_ZONE_3).", "zone mapping", 1),
    "n_nights": ("sleep", "Main-sleep nights ending that day (morning attribution).", "endTime filter; naps excluded", 1),
    "n_naps": ("sleep", "mainSleep==False naps ending that day.", "nap split", 1),
    "has_sleep_record": ("coverage", "1 when a main-sleep night exists.", "morning attribution", 1),
    "is_classic": ("sleep", "1 when the night is classic-type (no stage split).", "type branch", 1),
    "asleep_min": ("sleep", "Minutes asleep.", "as-is", 1),
    "time_in_bed_min": ("sleep", "Minutes in bed.", "as-is", 1),
    "efficiency_pct": ("sleep", "100 x asleep/in-bed (target >=85%).", "as-is", 1),
    "deep_min": ("sleep", "Deep minutes (NaN for classic).", "type branch", 1),
    "light_min": ("sleep", "Light minutes (NaN for classic).", "type branch", 1),
    "rem_min": ("sleep", "REM minutes (NaN for classic).", "type branch", 1),
    "wake_min": ("sleep", "Wake minutes incl. WASO.", "as-is", 1),
    "deep_pct": ("sleep", "Deep share of stage sum (athletic band 15-25%).", "stages-only", 1),
    "light_pct": ("sleep", "Light share (~50-60%).", "stages-only", 1),
    "rem_pct": ("sleep", "REM share (20-25%).", "stages-only", 1),
    "wake_pct": ("sleep", "Wake share (<10-15%).", "stages-only", 1),
    "onset_hour": ("sleep", "Sleep onset hour-of-day.", "startTime parse", 1),
    "offset_hour": ("sleep", "Sleep offset hour-of-day.", "endTime parse", 1),
    "midsleep_hour": ("sleep", "Midsleep hour (social-jetlag base).", "circular mean", 1),
    "mean_overall_score": ("sleep", "Mean Fitbit overall sleep score.", "logId join", 1),
    "mean_restlessness": ("sleep", "Mean restlessness (clipped 0.03-0.20).", "clip", 1),
    "n_wellness_rows": ("coverage", "Wellness submissions that day.", "count", 1),
    "has_wellness": ("coverage", "1 when a wellness row exists.", "presence flag", 1),
    "submission_hour": ("process", "Hour of last wellness submission.", "standardised TS", 1),
    "delayed_flag_ge12": ("process", "1 when submission hour >= 12 (recall-delayed).", "hour filter", 1),
    "weight_raw": ("reporting", "Last self-reported weight kg that day.", "as-is", 1),
    "weight_7d_median": ("reporting", "Causal 7d median weight + Tier-1 ffill <=2d (CV<1% stable).", "rolling median; ffill limit 2", 1),
    "weight_residual": ("reporting", "weight_raw minus 7d median (hydration/noise).", "causal residual", 1),
    "fluids_glasses": ("reporting", "Glasses of fluid summed that day.", "sum", 1),
    "alcohol_bin": ("reporting", "1 if any Yes that day (no unit volumes logged).", "Yes/No -> 1/0", 1),
    "lag_days": ("process", "Mean submission-minus-log lag in days (recall proxy).", "timestamp - date", 1),
    "n_meals_logged": ("nutrition", "Meals logged in reporting.csv that day.", "comma-split count", 1),
    "n_photos": ("nutrition", "Food-image captures that day (all).", "EXIF datetime", 1),
    "n_food_photos": ("nutrition", "Captures with is_food==YES.", "vision audit label", 1),
    "n_photo_meals": ("nutrition", "15 s shutter-burst meal events (food photos).", "15 s union-find", 1),
    "has_nutrition": ("coverage", "1 when >=1 food photo exists (Feb-Mar only).", "presence flag", 1),
    "estimated_kcal": ("nutrition", "Day macro kcal from food photos (NaN when no estimate).", "cached Gemini day-total; 15 s groups", 1),
    "protein_g": ("nutrition", "Day protein g from food photos.", "cached Gemini day-total; 15 s groups", 1),
    "carbs_g": ("nutrition", "Day carbs g from food photos.", "cached Gemini day-total; 15 s groups", 1),
    "fat_g": ("nutrition", "Day fat g from food photos.", "cached Gemini day-total; 15 s groups", 1),
    "nutrition_kcal_available": ("coverage", "1 when a day macro estimate exists.", "cache hit + valid payload", 1),
    "is_injured_day": ("injury", "1 when an injury event is reported that day.", "dict parse; rare-event", 1),
    "injured_last_7d": ("injury", "1 when any event in trailing 7d (recurrent-safe).", "rolling max", 1),
}


def write_data_dictionary(df: pd.DataFrame, path: Path = None) -> Path:
    """Write ``data_dictionary.csv`` next to the dataset.

    Columns: column, dtype, source, description, cleaning_rule,
    used_in_X. Covers every dataset column; banned subjective items and
    otherwise-unused raw fields are documented in the UNUSED section
    below (not as columns).
    """
    path = path or (OUTPUT_DIR / "data_dictionary.csv")
    features = set(get_feature_columns(df))
    rows = []
    for col in df.columns:
        dtype = str(df[col].dtype)
        if col in COLUMN_DOCS:
            source, desc, rule, _ = COLUMN_DOCS[col]
        elif col.startswith("act_"):
            source, desc, rule = ("activity", "One-hot activity flag (exercise bouts u sRPE names).", "canonical substring match")
        elif col.startswith("inj_"):
            source, desc, rule = ("injury", "One-hot injury location__severity flag.", "dict parse")
        elif col.startswith("zone_min_"):
            source, desc, rule = ("cardiac", "Daily minutes in HR zone (NaN when day missing).", "no zero-fill")
        elif col.startswith("missing_ratio_"):
            source, desc, rule = ("missingness", "Causal trailing-7d missing-day ratio.", "Tier-2 indicator")
        elif col.startswith("was_imputed_"):
            source, desc, rule = ("missingness", "1 when the value was Tier-1 forward-filled.", "ffill limit 2")
        elif col.endswith(("_mean_7d", "_median_7d", "_std_7d")):
            source, desc, rule = ("window", "Causal trailing-7d stat.", "rolling ending D")
        elif col in ("age", "height_cm", "gender", "chronotype", "max_hr",
                     "stride_walk_cm", "stride_run_cm"):
            source, desc, rule = ("static", "Overview covariate (overfit caveat, n=3).", "whitespace strip; stride sentinel->NaN")
        else:
            source, desc, rule = ("derived", "", "")
        rows.append({"column": col, "dtype": dtype, "source": source,
                     "description": desc, "cleaning_rule": rule,
                     "used_in_X": int(col in features)})
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


# UNUSED raw fields (present in source data, intentionally not columns):
# - Wellness subjective values: fatigue, mood, sleep_duration_h,
#   sleep_quality, soreness, stress (+ z-scores) and soreness_area raw
#   lists -> banned from X by user constraint (only lagged readiness kept).
# - readiness contemporaneous with the label (leakage; only D-1 used).
# - Injury raw dict strings / last_known_injuries text (replaced by flags).
# - total_distance_display strings, meal_names/activity raw strings,
#   photo filenames (replaced by numerics/one-hots/counts).
# - sleep levels.data[] hypnogram, exercise elevationGain/hasGps/
#   activityLevel[]/averageHeartRate raw, per-bout heartRateZones
#   (aggregated to daily TRIMP/exercise_min instead).
# - EXIF GPSInfo/Orientation raw, image dims/mode/size (identifiers).
# - Non-food captures (quarantined via is_food==NO).
# - sleep_score.resting_heart_rate duplicate of RHR source.
# - Calories as a wear signal (gap-filled export, uninformative).
# - Classic-night stage splits (null by design) and nap minutes folded
#   into nightly means (kept as n_naps instead).
# - Overview 5 km run fields, p04-p16 rows, mixed-format dates
#   ('november'/'injured' -> NaT), p14 11.3 cm stride (-> NaN example).
# - Raw join keys (logIds, sleep_log_entry_id, raw timestamp strings).


def save_dataset(df: pd.DataFrame, out_path: Path = None) -> Path:
    """Save the final dataset CSV (+ data dictionary). Returns CSV path."""
    out_path = out_path or (OUTPUT_DIR / "training_dataset.csv")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    write_data_dictionary(df, out_path.parent / "data_dictionary.csv")
    logging.info(f"Saved dataset {df.shape} -> {out_path}")
    return out_path


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    frame = build_training_dataset()
    save_dataset(frame)
