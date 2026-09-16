"""Daily/window aggregator for a given player.

Each ``aggregate_*`` function takes ``(player_id, start_date,
end_date=None)``; ``end_date=None`` means the whole ``start_date`` day.
Cumulative metrics are summed over the window, state metrics keep the
last non-empty value (sleep scores are averaged). All date handling goes
through ``standardize_date`` (parsed back with ``DATE_FORMAT``, the same
format ``standardize_date`` emits).

``aggregate_all`` returns a dict with descriptive keys; ``render`` turns
it into a Markdown report string.
"""

from datetime import datetime, timedelta

import pandas as pd

from src.data_handling import fitbit_reader, pmsys_reader, reporting_reader, food_reader
from src.utils.date_handler import standardize_date, DATE_FORMAT, _resolve_bounds, _matches


def _norm_day(value: str) -> str:
    return standardize_date(value)[:10]


def _window_bounds(start_date: str, end_date=None):
    return _resolve_bounds(start_date, end_date)


def format_distance(distance_cm: float) -> str:
    """Human-readable distance: cm below 100, m below 100 000, else km."""
    if distance_cm is None:
        return "n/a"
    value = float(distance_cm)
    if value < 100:
        return f"{value:g} cm"
    if value < 100_000:
        return f"{value / 100:g} m"
    return f"{value / 100_000:g} km"


def aggregate_activity(player_id: str, start_date: str, end_date=None) -> dict:
    """Totals and sessions of physical activity over the window."""
    steps = fitbit_reader.steps_reader(player_id, start_date, end_date)
    distance = fitbit_reader.distance_reader(player_id, start_date, end_date)
    calories = fitbit_reader.calories_reader(player_id, start_date, end_date)
    exercises = fitbit_reader.exercise_reader(player_id, start_date, end_date)
    resting = fitbit_reader.resting_heart_rate_reader(player_id, start_date, end_date)
    zones = fitbit_reader.time_in_heart_rate_zones_reader(player_id, start_date, end_date)

    exercise_list = list(exercises.values())
    durations_min = [e.get("activeDuration", e.get("duration", 0)) / 60000 for e in exercise_list]
    # A 0.0 resting value (usually paired with a null date) is the source's
    # missing-data sentinel, not a real measurement.
    resting_vals = [v.get("value") for v in resting.values()
                    if isinstance(v.get("value"), (int, float)) and v.get("value") > 0]
    zones_total = {}
    for day_zones in zones.values():
        for zone, minutes in day_zones.items():
            zones_total[zone] = zones_total.get(zone, 0.0) + float(minutes or 0.0)

    total_distance = float(distance.sum()) if len(distance) else 0.0
    return {
        "total_steps": float(steps.sum()) if len(steps) else 0.0,
        "peak_1min_steps": float(steps.max()) if len(steps) else 0.0,
        "total_distance": total_distance,
        "total_distance_display": format_distance(total_distance),
        "total_calories_burned": float(calories.sum()) if len(calories) else 0.0,
        "n_exercise_sessions": len(exercise_list),
        "exercise_minutes": round(sum(durations_min), 1),
        "activities": sorted({e.get("activityName") for e in exercise_list if e.get("activityName")}),
        "resting_hr_bpm": round(sum(resting_vals) / len(resting_vals), 2) if resting_vals else None,
        "hr_zones_min": zones_total,
    }


def aggregate_sleep(player_id: str, start_date: str, end_date=None) -> dict:
    """Nights ENDING in the window (morning-attribution).

    Sleep records start one evening and end the next morning, so the
    lookup starts one day earlier and keeps records whose standardized
    endTime falls inside the window.
    """
    lower, upper, upper_inclusive = _window_bounds(start_date, end_date)
    lookback = (datetime.strptime(standardize_date(start_date), DATE_FORMAT) - timedelta(days=1)).strftime("%Y-%m-%d")
    sleeps = fitbit_reader.sleep_reader(player_id, lookback, end_date or start_date)
    nights = []
    for record in sleeps.values():
        end_std = standardize_date(str(record.get("endTime", "")))
        if end_std and _matches(end_std, lower, upper, upper_inclusive):
            levels = (record.get("levels") or {}).get("summary", {})
            nights.append({
                "date_of_sleep": record.get("dateOfSleep"),
                "minutes_asleep": record.get("minutesAsleep"),
                "time_in_bed_min": record.get("timeInBed"),
                "efficiency_pct": record.get("efficiency"),
                "deep_min": (levels.get("deep") or {}).get("minutes"),
                "light_min": (levels.get("light") or {}).get("minutes"),
                "rem_min": (levels.get("rem") or {}).get("minutes"),
                "wake_min": (levels.get("wake") or {}).get("minutes"),
            })
    scores = fitbit_reader.sleep_score_reader(player_id, start_date, end_date)
    score_means = {}
    for col in ("overall_score", "composition_score", "revitalization_score",
                "duration_score", "deep_sleep_in_minutes", "restlessness"):
        if col in scores.columns and len(scores):
            score_means[f"mean_{col}"] = round(float(scores[col].mean()), 2)
        else:
            score_means[f"mean_{col}"] = None
    return {"n_nights": len(nights), "nights": nights, "has_sleep_record": bool(nights), **score_means}


def aggregate_questionnaire(player_id: str, start_date: str, end_date=None) -> dict:
    """Wellness answers, session-RPE load and self-reported nutrition log."""
    wellness = pmsys_reader.wellness_reader(player_id, start_date, end_date)
    srpe = pmsys_reader.srpe_reader(player_id, start_date, end_date)
    reporting = reporting_reader.reporting_reader(player_id, start_date, end_date)

    latest_wellness = {}
    if len(wellness):
        last = wellness.iloc[-1]
        latest_wellness = {
            "fatigue": last.get("fatigue"), "mood": last.get("mood"),
            "readiness": last.get("readiness"),
            "sleep_duration_h": last.get("sleep_duration_h"),
            "sleep_quality": last.get("sleep_quality"),
            "soreness": last.get("soreness"),
            "soreness_area": last.get("soreness_area"),
            "stress": last.get("stress"),
        }
    load = 0.0
    if len(srpe):
        load = float((pd.to_numeric(srpe["perceived_exertion"], errors="coerce").fillna(0)
                      * pd.to_numeric(srpe["duration_min"], errors="coerce").fillna(0)).sum())
    weight = None
    if len(reporting) and "weight" in reporting.columns:
        w = pd.to_numeric(reporting["weight"], errors="coerce").dropna()
        weight = float(w.iloc[-1]) if len(w) else None
    fluids = None
    if len(reporting) and "glasses_of_fluid" in reporting.columns:
        fluids = float(pd.to_numeric(reporting["glasses_of_fluid"], errors="coerce").fillna(0).sum())
    alcohol = None
    if len(reporting) and "alcohol_consumed" in reporting.columns:
        alcohol = bool((reporting["alcohol_consumed"].astype(str).str.lower() == "yes").any())

    return {
        "n_wellness_rows": len(wellness),
        "latest_wellness": latest_wellness or None,
        "n_srpe_sessions": len(srpe),
        "mean_rpe": round(float(pd.to_numeric(srpe["perceived_exertion"], errors="coerce").mean()), 2) if len(srpe) else None,
        "srpe_total_duration_min": int(pd.to_numeric(srpe["duration_min"], errors="coerce").fillna(0).sum()) if len(srpe) else 0,
        "training_load": round(load, 1),
        "weight_kg": weight,
        "total_glasses_of_fluid": fluids,
        "alcohol_consumed": alcohol,
    }


def aggregate_injury(player_id: str, start_date: str, end_date=None) -> dict:
    """Injury state: reports in the window plus last known status."""
    reports = pmsys_reader.injury_reader(player_id, start_date, end_date)
    end_day = _norm_day(end_date or start_date)
    history = pmsys_reader.injury_reader(player_id, "2019-01-01", end_date or start_date)
    past_keys = [k for k in history if k[:10] <= end_day]
    last_key = max(past_keys) if past_keys else None
    injured = any(bool(v) for v in reports.values())
    return {
        "reports_in_window": len(reports),
        "is_injured": injured,
        "injuries": {k: v for k, v in reports.items() if v},
        "has_report_in_window": bool(reports),
        "last_report_date": last_key,
        "last_known_injuries": history.get(last_key) if last_key else None,
    }


def aggregate_nutrition(player_id: str, start_date: str, end_date=None, meal_timedelta: int = 1800) -> dict:
    """Meal count from the reporting log + photo-based macro estimates."""
    reporting = reporting_reader.reporting_reader(player_id, start_date, end_date)
    meal_names = []
    if len(reporting) and "meals" in reporting.columns:
        for cell in reporting["meals"].dropna():
            meal_names.extend([m.strip() for m in str(cell).split(",") if m.strip()])
    photos = food_reader.photo_selector_by_date_player(player_id, start_date, end_date)
    macros = food_reader.get_macro_nutrients_from_photos(photos, meal_timedelta)
    totals = {"calories": 0.0, "protein": 0.0, "carbohydrates": 0.0, "fats": 0.0}
    for nutrients in macros.values():
        for key in totals:
            totals[key] += float(nutrients.get(key, 0) or 0)
    return {
        "n_reporting_rows": len(reporting),
        "n_meals_logged": len(meal_names),
        "meal_names": sorted(set(meal_names)),
        "n_food_photos": len(photos),
        "photo_files": sorted({p.split("/")[-1] for p in photos}),
        "meals_from_photos": len(macros),
        "estimated_calories_kcal": round(totals["calories"], 1),
        "estimated_macros_g": {k: round(v, 1) for k, v in totals.items() if k != "calories"},
        "is_estimate_placeholder": False,
    }


def aggregate_all(player_id: str, start_date: str, end_date=None, meal_timedelta: int = 1800) -> dict:
    """Aggregate everything for a player over a window (single day by default)."""
    start_day = _norm_day(start_date)
    end_day = _norm_day(end_date) if end_date is not None else start_day
    return {
        "player_id": player_id,
        "start_date": start_day,
        "end_date": end_day,
        "activity": aggregate_activity(player_id, start_date, end_date),
        "sleep": aggregate_sleep(player_id, start_date, end_date),
        "questionnaire": aggregate_questionnaire(player_id, start_date, end_date),
        "injury": aggregate_injury(player_id, start_date, end_date),
        "nutrition": aggregate_nutrition(player_id, start_date, end_date, meal_timedelta),
    }


def _fmt(value) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, float):
        return f"{value:.1f}"
    if isinstance(value, bool):
        return "Yes" if value else "No"
    if isinstance(value, (list, tuple)):
        return ", ".join(str(v) for v in value) if value else "n/a"
    if isinstance(value, dict):
        return ", ".join(f"{k}: {_fmt(v)}" for k, v in value.items()) if value else "n/a"
    return str(value)


def render(daily: dict) -> str:
    """Render an aggregate_all dict as a Markdown daily report."""
    if daily["start_date"] == daily["end_date"]:
        title = f"# Daily report — {daily['player_id']} — {daily['start_date']}"
    else:
        title = f"# Daily report — {daily['player_id']} — {daily['start_date']} to {daily['end_date']}"
    lines = [title, ""]
    activity = daily.get("activity", {})
    lines += ["## Activity",
              f"- **Total steps**: {_fmt(activity.get('total_steps'))}",
              f"- **Peak 1-min steps**: {_fmt(activity.get('peak_1min_steps'))}",
              f"- **Total distance**: {activity.get('total_distance_display', 'n/a')}",
              f"- **Calories burned**: {_fmt(activity.get('total_calories_burned'))}",
              f"- **Exercise sessions**: {_fmt(activity.get('n_exercise_sessions'))} "
              f"({_fmt(activity.get('exercise_minutes'))} min, {_fmt(activity.get('activities'))})",
              f"- **Resting HR**: {_fmt(activity.get('resting_hr_bpm'))} bpm",
              f"- **HR zones (min)**: {_fmt(activity.get('hr_zones_min'))}", ""]
    sleep = daily.get("sleep", {})
    lines += ["## Sleep",
              f"- **Nights recorded**: {_fmt(sleep.get('n_nights'))}",
              f"- **Mean overall score**: {_fmt(sleep.get('mean_overall_score'))}"]
    for night in sleep.get("nights", []):
        lines.append(f"- **Night {night.get('date_of_sleep')}**:")
        lines.append(f"  - Asleep: {_fmt(night.get('minutes_asleep'))} min "
                     f"(in bed {_fmt(night.get('time_in_bed_min'))} min, "
                     f"efficiency {_fmt(night.get('efficiency_pct'))}%)")
        lines.append("  - **Sleep phases**:")
        lines.append(f"    - Deep: {_fmt(night.get('deep_min'))} min")
        lines.append(f"    - Light: {_fmt(night.get('light_min'))} min")
        lines.append(f"    - REM: {_fmt(night.get('rem_min'))} min")
        lines.append(f"    - Wake: {_fmt(night.get('wake_min'))} min")
    lines += [""]
    quest = daily.get("questionnaire", {})
    lines += ["## Questionnaire",
              f"- **Wellness rows**: {_fmt(quest.get('n_wellness_rows'))}",
              f"- **Latest wellness**: {_fmt(quest.get('latest_wellness'))}",
              f"- **Training sessions**: {_fmt(quest.get('n_srpe_sessions'))}, "
              f"mean RPE {_fmt(quest.get('mean_rpe'))}, load {_fmt(quest.get('training_load'))}",
              f"- **Weight**: {_fmt(quest.get('weight_kg'))} kg",
              f"- **Fluids**: {_fmt(quest.get('total_glasses_of_fluid'))} glasses",
              f"- **Alcohol**: {_fmt(quest.get('alcohol_consumed'))}", ""]
    injury = daily.get("injury", {})
    injury_flag = " ⚠ **INJURED**" if injury.get("is_injured") else ""
    lines += ["## Injury status" + injury_flag,
              f"- **Injured in window**: {_fmt(injury.get('is_injured'))}",
              f"- **Injuries**: {_fmt(injury.get('injuries'))}",
              f"- **Last report**: {_fmt(injury.get('last_report_date'))} "
              f"({_fmt(injury.get('last_known_injuries'))})", ""]
    nutrition = daily.get("nutrition", {})
    lines += ["## Nutrition",
              f"- **Meals logged**: {_fmt(nutrition.get('n_meals_logged'))} ({_fmt(nutrition.get('meal_names'))})",
              f"- **Food photos**: {_fmt(nutrition.get('n_food_photos'))} "
              f"→ {_fmt(nutrition.get('meals_from_photos'))} photo-meals",
              f"- **Estimated calories**: {_fmt(nutrition.get('estimated_calories_kcal'))} kcal",
              f"- **Estimated macros (g)**: {_fmt(nutrition.get('estimated_macros_g'))}"]
    if nutrition.get("is_estimate_placeholder"):
        lines += ["", "_Calories/macros are placeholder estimates (model pending)._"]
    elif nutrition.get("n_food_photos"):
        lines += ["", "_Calories/macros estimated from meal photos by Gemini._"]
    return "\n".join(lines) + "\n"
