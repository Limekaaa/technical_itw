"""Exhaustive audit + EDA for multimodal athletic monitoring dataset (p01/p03/p05).

Generates, inside analysis/:
  tables/*.csv  (machine-readable audit tables)
  phase1_schema_audit.md
  phase2a_fitbit.md
  phase2b_subjective.md
  phase2c_food_injury.md
  phase3_preprocessing_modeling.md
  00_INDEX.md

Run: .venv/bin/python analysis/audit_full.py
Requires: pandas, numpy, Pillow, openpyxl (all in .venv).
No matplotlib dependency: distributions are tabulated + ASCII histograms;
CSVs under tables/ allow external plotting.
"""
from pathlib import Path
import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timedelta, date

import pandas as pd
import numpy as np
from PIL import Image, ExifTags

REPO = Path(__file__).resolve().parents[1]
DATA = REPO / "data"
OUT = REPO / "analysis"
TAB = OUT / "tables"
TAB.mkdir(parents=True, exist_ok=True)

PARTICIPANTS = ["p01", "p03", "p05"]
HORIZON_START = date(2019, 11, 1)
HORIZON_END = date(2020, 3, 31)
EXPECTED_MINUTES = 152 * 1440  # 218880

# ---------------------------------------------------------------- helpers
def md_table(df, floatfmt=".2f"):
    """DataFrame -> markdown table string."""
    cols = list(df.columns)
    lines = ["| " + " | ".join(str(c) for c in cols) + " |",
             "|" + "|".join(["---"] * len(cols)) + "|"]
    for _, r in df.iterrows():
        cells = []
        for c in cols:
            v = r[c]
            if pd.isna(v):
                cells.append("—")
            elif isinstance(v, float):
                cells.append(f"{v:{floatfmt}}")
            else:
                cells.append(str(v))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)

def ascii_hist(series, bins=12, width=40, title=""):
    s = pd.to_numeric(series, errors="coerce").dropna()
    if len(s) == 0:
        return f"{title}: (no data)"
    counts, edges = np.histogram(s, bins=bins)
    mx = counts.max() if counts.max() else 1
    lines = [f"{title} (n={len(s)})"]
    for c, lo, hi in zip(counts, edges[:-1], edges[1:]):
        bar = "#" * int(round(c / mx * width))
        lines.append(f"  {lo:10.2f}–{hi:<10.2f} | {bar} {c}")
    return "\n".join(lines)

def summarize_numeric(s):
    s = pd.to_numeric(s, errors="coerce").dropna()
    if len(s) == 0:
        return dict(n=0, mean=np.nan, median=np.nan, sd=np.nan, q25=np.nan,
                    q75=np.nan, iqr=np.nan, skew=np.nan, p1=np.nan, p99=np.nan,
                    min=np.nan, max=np.nan)
    return dict(n=int(len(s)), mean=float(s.mean()), median=float(s.median()),
                sd=float(s.std()), q25=float(s.quantile(.25)), q75=float(s.quantile(.75)),
                iqr=float(s.quantile(.75) - s.quantile(.25)), skew=float(s.skew()),
                p1=float(s.quantile(.01)), p99=float(s.quantile(.99)),
                min=float(s.min()), max=float(s.max()))

def load_json_list(p):
    with open(p) as fh:
        return json.load(fh)

# ================================================================ PHASE 1
def phase1_inventory():
    rows = []
    for p in PARTICIPANTS:
        base = DATA / p
        for sub, fname in [
            ("fitbit", "calories.json"), ("fitbit", "distance.json"),
            ("fitbit", "steps.json"), ("fitbit", "heart_rate.json"),
            ("fitbit", "resting_heart_rate.json"),
            ("fitbit", "time_in_heart_rate_zones.json"),
            ("fitbit", "sleep.json"), ("fitbit", "exercise.json"),
            ("fitbit", "sleep_score.csv"),
            ("pmsys", "wellness.csv"), ("pmsys", "srpe.csv"), ("pmsys", "injury.csv"),
            ("googledocs", "reporting.csv"),
        ]:
            fp = base / sub / fname
            if not fp.exists():
                rows.append(dict(participant=p, path=f"{sub}/{fname}",
                                 exists=False, n_rows=0, size_bytes=0, notes="MISSING"))
                continue
            sz = fp.stat().st_size
            try:
                if fname.endswith(".json"):
                    j = load_json_list(fp)
                    rows.append(dict(participant=p, path=f"{sub}/{fname}", exists=True,
                                     n_rows=len(j), size_bytes=sz, notes=""))
                else:
                    df = pd.read_csv(fp)
                    rows.append(dict(participant=p, path=f"{sub}/{fname}", exists=True,
                                     n_rows=len(df), size_bytes=sz, notes=";".join(map(str, df.columns))))
            except Exception as e:
                rows.append(dict(participant=p, path=f"{sub}/{fname}", exists=True,
                                 n_rows=-1, size_bytes=sz, notes=f"READ-ERR {e}"))
        # food images
        fdir = base / "food-images"
        imgs = list(fdir.glob("*")) if fdir.is_dir() else []
        imgs = [f for f in imgs if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".heic")]
        rows.append(dict(participant=p, path="food-images/", exists=fdir.is_dir(),
                         n_rows=len(imgs), size_bytes=sum(f.stat().st_size for f in imgs),
                         notes=Counter(f.suffix.lower() for f in imgs).__str__()))
    inv = pd.DataFrame(rows)
    inv.to_csv(TAB / "phase1_file_inventory.csv", index=False)
    return inv

def phase1_schema_matrix():
    """Per-dataset schema: columns/keys, dtypes, PK, timestamp col+format, drift."""
    recs = []
    # CSV schemas per participant
    csv_specs = {
        "pmsys/wellness.csv": "effective_time_frame",
        "pmsys/srpe.csv": "end_date_time",
        "pmsys/injury.csv": "effective_time_frame",
        "googledocs/reporting.csv": "date",
        "fitbit/sleep_score.csv": "timestamp",
    }
    for spec, tscol in csv_specs.items():
        for p in PARTICIPANTS:
            fp = DATA / p / spec
            df = pd.read_csv(fp)
            for c in df.columns:
                sample = df[c].dropna().iloc[0] if df[c].notna().any() else None
                # infer type
                try:
                    num = pd.to_numeric(df[c], errors="coerce")
                    numeric_share = num.notna().mean()
                except Exception:
                    numeric_share = 0
                recs.append(dict(dataset=spec, participant=p, field=c,
                                 dtype=str(df[c].dtype),
                                 numeric_share=round(float(numeric_share), 3),
                                 n_missing=int(df[c].isna().sum()),
                                 sample=str(sample)[:80],
                                 is_timestamp=(c == tscol),
                                 role="PK?" if c == tscol else ""))
            # timestamp format probe
            ts = df[tscol].dropna().astype(str)
            recs.append(dict(dataset=spec, participant=p, field="__TIMESTAMP_FORMAT__",
                             dtype="probe", numeric_share=0,
                             n_missing=0,
                             sample="; ".join(ts.iloc[:2].tolist())[:160],
                             is_timestamp=True, role="format"))
    # JSON schemas
    json_key_specs = {
        "fitbit/calories.json": ("dateTime", ["dateTime", "value"]),
        "fitbit/distance.json": ("dateTime", ["dateTime", "value"]),
        "fitbit/steps.json": ("dateTime", ["dateTime", "value"]),
        "fitbit/heart_rate.json": ("dateTime", ["dateTime", "value.bpm", "value.confidence"]),
        "fitbit/resting_heart_rate.json": ("dateTime", ["dateTime", "value.date", "value.value", "value.error"]),
        "fitbit/time_in_heart_rate_zones.json": ("dateTime", ["dateTime", "value.valuesInZones.{BELOW_DEFAULT_ZONE_1,IN_DEFAULT_ZONE_1,IN_DEFAULT_ZONE_2,IN_DEFAULT_ZONE_3}"]),
        "fitbit/sleep.json": ("startTime/dateOfSleep/logId", ["logId", "dateOfSleep", "startTime", "endTime", "minutesAsleep", "minutesAwake", "timeInBed", "efficiency", "type", "levels.summary.{deep,light,rem,wake|asleep,restless,awake}", "levels.data[]", "mainSleep"]),
        "fitbit/exercise.json": ("startTime/logId", ["logId", "activityName", "activityTypeId", "activityLevel[]", "averageHeartRate", "calories", "duration", "activeDuration", "steps", "logType", "heartRateZones[]", "startTime", "elevationGain", "hasGps"]),
    }
    for spec, (pk, keys) in json_key_specs.items():
        for p in PARTICIPANTS:
            fp = DATA / p / spec
            if not fp.exists():
                recs.append(dict(dataset=spec, participant=p, field="__FILE__",
                                 dtype="MISSING", numeric_share=0, n_missing=0,
                                 sample="FILE ABSENT (p03 heart_rate.json)", is_timestamp=False, role="drift"))
                continue
            j = load_json_list(fp)
            n = len(j)
            first_keys = list(j[0].keys()) if n and isinstance(j[0], dict) else []
            # value probe
            probe = str(j[0])[:160] if n else ""
            last_probe = str(j[-1])[:160] if n else ""
            recs.append(dict(dataset=spec, participant=p, field="__RECORD__",
                             dtype=f"list[{n}] keys={first_keys}", numeric_share=0,
                             n_missing=0, sample=probe, is_timestamp=False, role=f"PK~{pk}"))
            recs.append(dict(dataset=spec, participant=p, field="__LAST__",
                             dtype=f"last record", numeric_share=0, n_missing=0,
                             sample=last_probe, is_timestamp=False, role=""))
            # expected keys note
            recs.append(dict(dataset=spec, participant=p, field="__EXPECTED_KEYS__",
                             dtype="; ".join(keys), numeric_share=0, n_missing=0,
                             sample="", is_timestamp=False, role="expected"))
    # sleep type drift
    for p in PARTICIPANTS:
        for spec in ["fitbit/sleep.json", "fitbit/exercise.json"]:
            fp = DATA / p / spec
            if not fp.exists():
                continue
            j = load_json_list(fp)
            if spec.endswith("sleep.json"):
                c = Counter(x.get("type") for x in j)
                recs.append(dict(dataset=spec, participant=p, field="__DRIFT_type__",
                                 dtype=str(dict(c)), numeric_share=0, n_missing=0,
                                 sample="classic lacks deep/light/rem split; stages has full hypnogram",
                                 is_timestamp=False, role="drift"))
                # levels.data presence
                n_data = sum(1 for x in j if (x.get("levels") or {}).get("data"))
                recs.append(dict(dataset=spec, participant=p, field="__DRIFT_levels.data__",
                                 dtype=f"{n_data}/{len(j)} with event array", numeric_share=0, n_missing=0,
                                 sample="", is_timestamp=False, role="drift"))
            else:
                c = Counter(x.get("activityName") for x in j)
                recs.append(dict(dataset=spec, participant=p, field="__DRIFT_activityName__",
                                 dtype=str(dict(c)), numeric_share=0, n_missing=0,
                                 sample="", is_timestamp=False, role="drift"))
    schema = pd.DataFrame(recs)
    schema.to_csv(TAB / "phase1_schema_matrix.csv", index=False)
    return schema

def phase1_temporal_horizon():
    rows = []
    for p in PARTICIPANTS:
        # fitbit minute files
        fit_ranges = {}
        for f in ["calories.json", "distance.json", "steps.json"]:
            fp = DATA / p / "fitbit" / f
            j = load_json_list(fp)
            if not j:
                fit_ranges[f] = (None, None, 0)
                continue
            ts = pd.to_datetime([x["dateTime"] for x in j])
            fit_ranges[f] = (ts.min(), ts.max(), len(j))
        # HR
        fp = DATA / p / "fitbit" / "heart_rate.json"
        if fp.exists():
            j = load_json_list(fp)
            ts = pd.to_datetime([x["dateTime"] for x in j])
            hr = (ts.min(), ts.max(), len(j))
        else:
            hr = (None, None, 0)
        # RHR / zones / sleep / exercise / sleep_score
        def jrange(fname, key):
            fp = DATA / p / "fitbit" / fname
            j = load_json_list(fp)
            if not j:
                return (None, None, 0)
            if key == "dateTime":
                ts = pd.to_datetime([x["dateTime"] for x in j])
            elif key == "startTime":
                ts = pd.to_datetime([x["startTime"] for x in j])
            elif key == "dateOfSleep":
                ts = pd.to_datetime([x["dateOfSleep"] for x in j])
            return (ts.min(), ts.max(), len(j))
        rhr = jrange("resting_heart_rate.json", "dateTime")
        zones = jrange("time_in_heart_rate_zones.json", "dateTime")
        sleep = jrange("sleep.json", "dateOfSleep")
        exer = jrange("exercise.json", "startTime")
        ss = pd.read_csv(DATA / p / "fitbit" / "sleep_score.csv")
        ss_ts = pd.to_datetime(ss["timestamp"], utc=True)
        wel = pd.read_csv(DATA / p / "pmsys" / "wellness.csv")
        wel_ts = pd.to_datetime(wel["effective_time_frame"], utc=True)
        srpe = pd.read_csv(DATA / p / "pmsys" / "srpe.csv")
        srpe_ts = pd.to_datetime(srpe["end_date_time"], utc=True) if len(srpe) else pd.Series([], dtype="datetime64[ns, UTC]")
        inj = pd.read_csv(DATA / p / "pmsys" / "injury.csv")
        inj_ts = pd.to_datetime(inj["effective_time_frame"], utc=True)
        rep = pd.read_csv(DATA / p / "googledocs" / "reporting.csv")
        rep_d = pd.to_datetime(rep["date"], dayfirst=True)
        # food images EXIF datetimes
        fdir = DATA / p / "food-images"
        img_dates = []
        for f in fdir.iterdir():
            if f.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue
            try:
                with Image.open(f) as im:
                    exif_raw = im._getexif() or {}
                    tags = {ExifTags.TAGS.get(k, k): v for k, v in exif_raw.items()}
                    dt = tags.get("DateTime") or tags.get("DateTimeOriginal")
                    if dt:
                        img_dates.append(datetime.strptime(dt, "%Y:%m:%d %H:%M:%S"))
            except Exception:
                pass
        img_dates = pd.Series(img_dates) if img_dates else pd.Series([], dtype="datetime64[ns]")
        # active days: distinct calendar days per modality group
        def ndays(s):
            s = pd.Series(s).dropna()
            if len(s) == 0:
                return 0
            return pd.to_datetime(s).dt.date.nunique()
        fit_days = ndays(pd.to_datetime([x["dateTime"] for x in load_json_list(DATA / p / "fitbit" / "calories.json")]))
        rows.append(dict(
            participant=p,
            calories_start=str(fit_ranges["calories.json"][0]), calories_end=str(fit_ranges["calories.json"][1]),
            steps_n=fit_ranges["steps.json"][2], steps_days=ndays(pd.to_datetime([x["dateTime"] for x in load_json_list(DATA / p / "fitbit" / "steps.json")])),
            distance_n=fit_ranges["distance.json"][2],
            hr_n=hr[2], hr_start=str(hr[0]), hr_end=str(hr[1]),
            rhr_n=rhr[2], rhr_start=str(rhr[0]), rhr_end=str(rhr[1]),
            zones_n=zones[2], zones_start=str(zones[0]), zones_end=str(zones[1]),
            sleep_n=sleep[2], sleep_start=str(sleep[0]), sleep_end=str(sleep[1]),
            exercise_n=exer[2], exercise_start=str(exer[0]), exercise_end=str(exer[1]),
            sleep_score_n=len(ss), sleep_score_start=str(ss_ts.min()), sleep_score_end=str(ss_ts.max()),
            wellness_n=len(wel), wellness_start=str(wel_ts.min()), wellness_end=str(wel_ts.max()),
            wellness_days=ndays(wel_ts),
            srpe_n=len(srpe), srpe_start=str(srpe_ts.min()) if len(srpe_ts) else "—", srpe_end=str(srpe_ts.max()) if len(srpe_ts) else "—",
            injury_reports_n=len(inj), injury_start=str(inj_ts.min()), injury_end=str(inj_ts.max()),
            reporting_n=len(rep), reporting_start=str(rep_d.min()), reporting_end=str(rep_d.max()), reporting_days=ndays(rep_d),
            food_n=len(img_dates), food_start=str(img_dates.min()) if len(img_dates) else "—", food_end=str(img_dates.max()) if len(img_dates) else "—", food_days=ndays(img_dates),
            fitbit_days=int(fit_days),
        ))
    hor = pd.DataFrame(rows)
    hor.to_csv(TAB / "phase1_temporal_horizon.csv", index=False)
    return hor

# ================================================================ PHASE 2A
def daily_aggregate(p, kind):
    """Daily sums for steps/distance/calories; returns Series indexed by date."""
    j = load_json_list(DATA / p / "fitbit" / f"{kind}.json")
    df = pd.DataFrame(j)
    df["dateTime"] = pd.to_datetime(df["dateTime"])
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    g = df.groupby(df["dateTime"].dt.date)["value"].sum()
    # reindex full horizon
    idx = pd.date_range(HORIZON_START, HORIZON_END, freq="D").date
    return g.reindex(idx)

def phase2a_minute_missingness():
    rows = []
    for p in PARTICIPANTS:
        for kind in ["calories", "distance", "steps"]:
            j = load_json_list(DATA / p / "fitbit" / f"{kind}.json")
            df = pd.DataFrame(j)
            n = len(df)
            dups = int(df.duplicated("dateTime").sum())
            uniq = int(df["dateTime"].nunique())
            missing_slots = EXPECTED_MINUTES - uniq
            # daily coverage for steps/distance
            df["d"] = pd.to_datetime(df["dateTime"]).dt.date
            daily = df.groupby("d").size()
            rows.append(dict(participant=p, file=f"{kind}.json", n_records=n,
                             n_unique_ts=uniq, n_duplicates=dups,
                             expected_slots=EXPECTED_MINUTES,
                             missing_slots=missing_slots,
                             missing_pct=round(100 * missing_slots / EXPECTED_MINUTES, 2),
                             days_present=int(daily.index.nunique()),
                             days_full_1440=int((daily == 1440).sum()),
                             days_partial=int((daily < 1440).sum()),
                             min_daily=int(daily.min()), max_daily=int(daily.max()),
                             mean_daily=round(float(daily.mean()), 1)))
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "phase2a_minute_missingness.csv", index=False)
    return out

def phase2a_nonwear():
    """Non-wear = >=60 consecutive minutes with steps==0 AND (no HR sample that minute OR HR flatlined).
    For p03 (no HR file) the HR condition is vacuous -> steps-only run definition (flagged)."""
    rows_detail = []
    summary = []
    for p in PARTICIPANTS:
        steps = load_json_list(DATA / p / "fitbit" / "steps.json")
        sdf = pd.DataFrame(steps)
        sdf["dateTime"] = pd.to_datetime(sdf["dateTime"])
        sdf["value"] = pd.to_numeric(sdf["value"], errors="coerce").fillna(0)
        # dedupe: keep first per timestamp (p01 DST duplicates are 0/0 so immaterial)
        sdf = sdf.sort_values("dateTime").drop_duplicates("dateTime", keep="first")
        # full minute index
        full_idx = pd.date_range(datetime(2019, 11, 1), datetime(2020, 3, 31, 23, 59), freq="min")
        s = pd.Series(np.nan, index=full_idx)
        s.loc[sdf["dateTime"]] = sdf["value"].values
        # HR presence per minute
        fp = DATA / p / "fitbit" / "heart_rate.json"
        if fp.exists():
            hj = load_json_list(fp)
            hdf = pd.DataFrame([{"ts": x["dateTime"], "bpm": x["value"]["bpm"]} for x in hj])
            hdf["ts"] = pd.to_datetime(hdf["ts"])
            hdf["minute"] = hdf["ts"].dt.floor("min")
            hr_per_min = hdf.groupby("minute")["bpm"].agg(["count", "std", "mean"])
            hr_count = pd.Series(0, index=full_idx)
            hr_std = pd.Series(np.nan, index=full_idx)
            idx = hr_per_min.index.intersection(full_idx)
            # need tz-naive intersection
            try:
                hr_count.loc[idx] = hr_per_min.loc[idx, "count"].values
                hr_std.loc[idx] = hr_per_min.loc[idx, "std"].values
            except Exception:
                pass
            hr_missing = (hr_count == 0)
            hr_flat = (hr_std.fillna(-1) == 0) & (hr_count >= 2)
            no_hr_signal = (hr_missing | hr_flat)
            hr_note = "steps==0 & (no HR sample OR flatlined HR std==0)"
        else:
            no_hr_signal = pd.Series(True, index=full_idx)
            hr_note = "NO HR FILE -> steps==0 only (overestimates non-wear; sleep confounded)"
        steps_zero = (s.fillna(0) == 0)  # missing minute counts as zero steps
        # missing-minute flag separately
        minute_missing = s.isna()
        candidate = (steps_zero & no_hr_signal)
        # find runs >=60
        arr = candidate.values.astype(int)
        # run-length encode
        runs = []
        i = 0
        n = len(arr)
        while i < n:
            if arr[i] == 1:
                j = i
                while j < n and arr[j] == 1:
                    j += 1
                runs.append((i, j - 1))
                i = j
            else:
                i += 1
        long_runs = [(a, b) for a, b in runs if (b - a + 1) >= 60]
        total_nonwear_min = sum(b - a + 1 for a, b in long_runs)
        # per-day nonwear minutes
        per_day = Counter()
        for a, b in long_runs:
            seg = full_idx[a:b + 1]
            for d, c in Counter(seg.date).items():
                per_day[d] += c
        per_day_s = pd.Series(per_day).sort_index()
        # save per-day
        for d, m in per_day_s.items():
            rows_detail.append(dict(participant=p, date=str(d), nonwear_min=int(m),
                                    nonwear_hours=round(m / 60, 2)))
        summary.append(dict(participant=p, definition=hr_note,
                            n_long_runs=len(long_runs),
                            total_nonwear_min=int(total_nonwear_min),
                            total_nonwear_hours=round(total_nonwear_min / 60, 1),
                            mean_nonwear_min_per_day=round(float(per_day_s.mean()) if len(per_day_s) else 0, 1),
                            median_nonwear_min_per_day=round(float(per_day_s.median()) if len(per_day_s) else 0, 1),
                            max_nonwear_min_one_day=int(per_day_s.max()) if len(per_day_s) else 0,
                            days_with_any_nonwear=int(len(per_day_s)),
                            steps_missing_minutes=int(minute_missing.sum())))
    pd.DataFrame(rows_detail).to_csv(TAB / "phase2a_nonwear_per_day.csv", index=False)
    out = pd.DataFrame(summary)
    out.to_csv(TAB / "phase2a_nonwear_summary.csv", index=False)
    return out

def phase2a_daily_distributions():
    rows = []
    per_day_all = {}
    for p in PARTICIPANTS:
        for kind in ["steps", "distance", "calories"]:
            d = daily_aggregate(p, kind)
            per_day_all[(p, kind)] = d
            st = summarize_numeric(d)
            st.update(dict(participant=p, metric=f"daily_{kind}"))
            rows.append(st)
        # active minutes from exercise activeDuration per day
        ex = load_json_list(DATA / p / "fitbit" / "exercise.json")
        if ex:
            df = pd.DataFrame([{"d": pd.to_datetime(x["startTime"]).date(),
                                "m": (x.get("activeDuration", x.get("duration", 0)) or 0) / 60000} for x in ex])
            g = df.groupby("d")["m"].sum()
            idx = pd.date_range(HORIZON_START, HORIZON_END, freq="D").date
            g = g.reindex(idx).fillna(0)
        else:
            g = pd.Series(0, index=pd.date_range(HORIZON_START, HORIZON_END, freq="D").date)
        st = summarize_numeric(g)
        st.update(dict(participant=p, metric="daily_exercise_active_min"))
        rows.append(st)
        per_day_all[(p, "exercise_min")] = g
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "phase2a_daily_distributions.csv", index=False)
    # also dump per-day wide table
    wide = pd.DataFrame({f"{p}_{k}": v for (p, k), v in per_day_all.items()})
    wide.to_csv(TAB / "phase2a_daily_values.csv")
    return out

def phase2a_hr():
    rows = []
    for p in PARTICIPANTS:
        # RHR series
        j = load_json_list(DATA / p / "fitbit" / "resting_heart_rate.json")
        df = pd.DataFrame([{"date": pd.to_datetime(x["dateTime"]).date(),
                            "value": (x.get("value") or {}).get("value"),
                            "error": (x.get("value") or {}).get("error")} for x in j])
        df["valid"] = (df["value"] > 0) & df["value"].notna()
        v = df.loc[df["valid"], "value"]
        st = summarize_numeric(v)
        # baseline shift: first-half mean vs second-half mean
        v_sorted = df.sort_values("date")
        vv = v_sorted.loc[v_sorted["valid"], "value"].values
        if len(vv) >= 10:
            drift = float(np.mean(vv[len(vv)//2:]) - np.mean(vv[:len(vv)//2]))
        else:
            drift = np.nan
        rows.append(dict(participant=p, modality="RHR_valid_bpm", n_valid=int(df["valid"].sum()),
                         n_sentinel_zero=int((~df["valid"]).sum()), drift_2nd_minus_1st_half=round(drift, 2) if not pd.isna(drift) else "—",
                         **{f"rhr_{k}": st[k] for k in ["mean","median","sd","min","max","p1","p99"]}))
        # continuous HR (vectorized: single to_datetime call, no per-sample parse)
        fp = DATA / p / "fitbit" / "heart_rate.json"
        if fp.exists():
            hj = load_json_list(fp)
            bpm = pd.Series([x["value"]["bpm"] for x in hj], dtype="float64")
            st2 = summarize_numeric(bpm)
            conf = Counter(x["value"].get("confidence") for x in hj)
            # peak per day — vectorized date conversion
            _ts = pd.to_datetime([x["dateTime"] for x in hj])
            _day = _ts.date if hasattr(_ts, "date") else pd.Series(_ts).dt.date.values
            hdf = pd.DataFrame({"d": _day, "bpm": bpm.values})
            peak = hdf.groupby("d")["bpm"].max()
            stp = summarize_numeric(peak)
            rows.append(dict(participant=p, modality="HR_continuous_bpm", n_valid=len(bpm),
                             n_sentinel_zero="—", drift_2nd_minus_1st_half="—",
                             **{f"rhr_{k}": st2[k] for k in ["mean","median","sd","min","max","p1","p99"]}))
            rows.append(dict(participant=p, modality="HR_daily_peak_bpm", n_valid=int(peak.index.nunique()),
                             n_sentinel_zero="—", drift_2nd_minus_1st_half="—",
                             **{f"rhr_{k}": stp[k] for k in ["mean","median","sd","min","max","p1","p99"]}))
            # confidence note row via extra column? store in CSV separately
            pd.DataFrame([dict(participant=p, conf=k, n=v2) for k, v2 in sorted(conf.items(), key=lambda x: str(x[0]))]).to_csv(
                TAB / f"phase2a_hr_confidence_{p}.csv", index=False)
        else:
            rows.append(dict(participant=p, modality="HR_continuous_bpm", n_valid=0,
                             n_sentinel_zero="FILE MISSING", drift_2nd_minus_1st_half="—",
                             rhr_mean=np.nan, rhr_median=np.nan, rhr_sd=np.nan, rhr_min=np.nan,
                             rhr_max=np.nan, rhr_p1=np.nan, rhr_p99=np.nan))
        # zones: mean min/day per zone
        zj = load_json_list(DATA / p / "fitbit" / "time_in_heart_rate_zones.json")
        zones = ["BELOW_DEFAULT_ZONE_1", "IN_DEFAULT_ZONE_1", "IN_DEFAULT_ZONE_2", "IN_DEFAULT_ZONE_3"]
        for z in zones:
            vals = pd.Series([(x.get("value", {}).get("valuesInZones", {}) or {}).get(z, 0) for x in zj])
            stz = summarize_numeric(vals)
            rows.append(dict(participant=p, modality=f"zone_{z}_min_per_day", n_valid=len(vals),
                             n_sentinel_zero="—", drift_2nd_minus_1st_half="—",
                             **{f"rhr_{k}": stz[k] for k in ["mean","median","sd","min","max","p1","p99"]}))
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "phase2a_hr_zones.csv", index=False)
    return out

def phase2a_sleep():
    rows = []
    arch_rows = []
    for p in PARTICIPANTS:
        j = load_json_list(DATA / p / "fitbit" / "sleep.json")
        # keep mainSleep stages only for architecture? report both
        recs = []
        for x in j:
            lv = (x.get("levels") or {}).get("summary", {}) or {}
            def mins(k):
                return ((lv.get(k) or {}).get("minutes")) if isinstance(lv.get(k), dict) else None
            if x.get("type") == "stages":
                deep, light, rem, wake = mins("deep"), mins("light"), mins("rem"), mins("wake")
            elif x.get("type") == "classic":
                deep, light, rem, wake = None, None, None, None
                asleep = mins("asleep"); restless = mins("restless"); awake = mins("awake")
            else:
                deep = light = rem = wake = None
            recs.append(dict(logId=x.get("logId"), dateOfSleep=x.get("dateOfSleep"), type=x.get("type"),
                             mainSleep=x.get("mainSleep"), minutesAsleep=x.get("minutesAsleep"),
                             minutesAwake=x.get("minutesAwake"), timeInBed=x.get("timeInBed"),
                             efficiency=x.get("efficiency"), deep=deep, light=light, rem=rem, wake=wake))
        df = pd.DataFrame(recs)
        df.to_csv(TAB / f"phase2a_sleep_nights_{p}.csv", index=False)
        for col in ["minutesAsleep", "minutesAwake", "timeInBed", "efficiency", "deep", "light", "rem", "wake"]:
            st = summarize_numeric(df[col])
            st.update(dict(participant=p, metric=col, n_nights=int(df[col].notna().sum())))
            rows.append(st)
        # architecture % on stages+mainSleep nights with complete split
        sub = df[(df["type"] == "stages")]
        sub = sub.dropna(subset=["deep", "light", "rem", "wake"])
        # use minutesAsleep+minutesAwake or deep+light+rem+wake as denominator; use sum of 4
        for _, r in sub.iterrows():
            tot = (r["deep"] or 0) + (r["light"] or 0) + (r["rem"] or 0) + (r["wake"] or 0)
            if tot > 0:
                arch_rows.append(dict(participant=p, dateOfSleep=r["dateOfSleep"],
                                      deep_pct=100 * r["deep"] / tot, light_pct=100 * r["light"] / tot,
                                      rem_pct=100 * r["rem"] / tot, wake_pct=100 * r["wake"] / tot))
        arch = pd.DataFrame([a for a in arch_rows if a["participant"] == p])
        if len(arch):
            for c in ["deep_pct", "light_pct", "rem_pct", "wake_pct"]:
                st = summarize_numeric(arch[c])
                st.update(dict(participant=p, metric=c, n_nights=len(arch)))
                rows.append(st)
    pd.DataFrame(arch_rows).to_csv(TAB / "phase2a_sleep_architecture_pct.csv", index=False)
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "phase2a_sleep_distributions.csv", index=False)
    return out

# ================================================================ PHASE 2B
def phase2b_wellness():
    rows_resp = []
    dist_rows = []
    hour_rows = []
    for p in PARTICIPANTS:
        df = pd.read_csv(DATA / p / "pmsys" / "wellness.csv")
        ts = pd.to_datetime(df["effective_time_frame"], utc=True)
        days = ts.dt.date.nunique()
        rows_resp.append(dict(participant=p, n_rows=len(df), n_days_with_log=days,
                              horizon_days=152, response_rate=round(days / 152, 3),
                              first=str(ts.min()), last=str(ts.max()),
                              median_hour=round(float(ts.dt.hour.median()), 2),
                              sd_hour=round(float(ts.dt.hour.std()), 2),
                              pct_before_09=round(float((ts.dt.hour < 9).mean() * 100), 1),
                              pct_after_12=round(float((ts.dt.hour >= 12).mean() * 100), 1)))
        for h, c in sorted(Counter(ts.dt.hour).items()):
            hour_rows.append(dict(participant=p, hour=int(h), n=int(c)))
        for col in ["fatigue", "mood", "readiness", "sleep_duration_h", "sleep_quality", "soreness", "stress"]:
            s = pd.to_numeric(df[col], errors="coerce")
            st = summarize_numeric(s)
            vc = s.value_counts(normalize=True).sort_index()
            mode_share = float(vc.max()) if len(vc) else np.nan
            st.update(dict(participant=p, metric=col, mode=int(s.mode().iloc[0]) if len(s.mode()) else "—",
                           mode_share=round(mode_share, 3) if not pd.isna(mode_share) else "—",
                           n_unique=int(s.nunique()),
                           value_counts=";".join(f"{int(k)}:{v:.0%}" for k, v in vc.items())))
            dist_rows.append(st)
    pd.DataFrame(rows_resp).to_csv(TAB / "phase2b_wellness_response.csv", index=False)
    pd.DataFrame(hour_rows).to_csv(TAB / "phase2b_wellness_hour.csv", index=False)
    pd.DataFrame(dist_rows).to_csv(TAB / "phase2b_likert_distributions.csv", index=False)
    # intra vs inter variance: pooled within-participant SD vs between-participant SD of means
    df_all = []
    for p in PARTICIPANTS:
        df = pd.read_csv(DATA / p / "pmsys" / "wellness.csv")
        df["participant"] = p
        df_all.append(df)
    W = pd.concat(df_all, ignore_index=True)
    var_rows = []
    for col in ["fatigue", "mood", "readiness", "sleep_duration_h", "sleep_quality", "soreness", "stress"]:
        s = pd.to_numeric(W[col], errors="coerce")
        group_means = W.groupby("participant")[col].mean(numeric_only=True)
        within_sd = W.groupby("participant")[col].std(numeric_only=True).mean()
        between_sd = group_means.std()
        var_rows.append(dict(metric=col, grand_mean=round(float(s.mean()), 2),
                             within_participant_mean_sd=round(float(within_sd), 3),
                             between_participant_sd_of_means=round(float(between_sd), 3),
                             ratio_between_within=round(float(between_sd / within_sd), 2) if within_sd else "—"))
    pd.DataFrame(var_rows).to_csv(TAB / "phase2b_intra_vs_inter.csv", index=False)
    return rows_resp, dist_rows

def phase2b_srpe():
    rows = []
    all_loads = {}
    for p in PARTICIPANTS:
        df = pd.read_csv(DATA / p / "pmsys" / "srpe.csv")
        df["load"] = pd.to_numeric(df["perceived_exertion"], errors="coerce") * pd.to_numeric(df["duration_min"], errors="coerce")
        ts = pd.to_datetime(df["end_date_time"], utc=True) if len(df) else pd.Series([], dtype="datetime64[ns, UTC]")
        # daily load over horizon
        idx = pd.date_range(HORIZON_START, HORIZON_END, freq="D").date
        if len(df):
            df["d"] = ts.dt.date.values
            daily = df.groupby("d")["load"].sum().reindex(idx).fillna(0)
        else:
            daily = pd.Series(0, index=idx)
        all_loads[p] = daily
        mean_d = float(daily.mean()); sd_d = float(daily.std())
        monotony = mean_d / sd_d if sd_d else np.nan
        strain = float(daily.sum()) * monotony if not pd.isna(monotony) else np.nan
        # spikes: daily load z>2 among nonzero? and week-over-week acute:chronic proxy
        nz = daily[daily > 0]
        spikes = daily[daily > (mean_d + 2 * sd_d)] if sd_d else daily[daily > 0][:0]
        rows.append(dict(participant=p, n_sessions=len(df),
                         mean_RPE=round(float(pd.to_numeric(df["perceived_exertion"], errors="coerce").mean()), 2) if len(df) else "—",
                         mean_duration=round(float(pd.to_numeric(df["duration_min"], errors="coerce").mean()), 1) if len(df) else "—",
                         total_load=round(float(df["load"].sum()), 1) if len(df) else 0,
                         mean_daily_load=round(mean_d, 2), sd_daily_load=round(sd_d, 2),
                         monotony=round(monotony, 3) if not pd.isna(monotony) else "—",
                         strain=round(strain, 1) if not pd.isna(strain) else "—",
                         n_spike_days=int((daily > (mean_d + 2 * sd_d)).sum()) if sd_d else 0,
                         max_daily_load=float(daily.max()),
                         activity_types=";".join(sorted(set(df["activity_names"].astype(str)))) if len(df) else "—"))
        daily.to_csv(TAB / f"phase2b_srpe_daily_load_{p}.csv")
    pd.DataFrame(rows).to_csv(TAB / "phase2b_srpe_summary.csv", index=False)
    return rows

def phase2b_weight_alcohol():
    wrows = []
    arows = []
    for p in PARTICIPANTS:
        df = pd.read_csv(DATA / p / "googledocs" / "reporting.csv")
        w = pd.to_numeric(df["weight"], errors="coerce")
        wd = w.dropna()
        deltas = wd.diff().dropna().abs()
        cv = float(wd.std() / wd.mean()) if len(wd) and wd.mean() else np.nan
        wrows.append(dict(participant=p, n_weight_obs=int(wd.notna().sum()),
                          n_missing_weight=int(w.isna().sum()),
                          mean=round(float(wd.mean()), 2) if len(wd) else "—",
                          sd=round(float(wd.std()), 3) if len(wd) else "—",
                          cv_pct=round(cv * 100, 3) if not pd.isna(cv) else "—",
                          min=float(wd.min()) if len(wd) else "—", max=float(wd.max()) if len(wd) else "—",
                          range=float(wd.max() - wd.min()) if len(wd) else "—",
                          mean_abs_day_to_day=round(float(deltas.mean()), 3) if len(deltas) else "—",
                          max_abs_day_to_day=float(deltas.max()) if len(deltas) else "—",
                          n_changes_gt2kg=int((deltas > 2).sum())))
        # alcohol
        alc = df["alcohol_consumed"].astype(str)
        n_yes = int((alc.str.lower() == "yes").sum())
        # temporal clustering: by weekday of `date`
        d = pd.to_datetime(df["date"], dayfirst=True)
        df2 = df.copy(); df2["d"] = d; df2["dow"] = d.dt.day_name()
        yes_by_dow = df2.loc[alc.str.lower() == "yes", "dow"].value_counts().to_dict() if n_yes else {}
        weekend = df2.loc[alc.str.lower() == "yes", "d"].dt.dayofweek.isin([4, 5, 6]).mean() if n_yes else np.nan
        arows.append(dict(participant=p, n_days=len(df), n_alcohol_yes=n_yes,
                          pct_yes=round(100 * n_yes / len(df), 1) if len(df) else "—",
                          pct_weekend_Fri_Sat_Sun=round(float(weekend * 100), 1) if not pd.isna(weekend) else "—",
                          by_weekday=str(yes_by_dow),
                          glasses_mean=round(float(pd.to_numeric(df["glasses_of_fluid"], errors="coerce").mean()), 2)))
    pd.DataFrame(wrows).to_csv(TAB / "phase2b_weight.csv", index=False)
    pd.DataFrame(arows).to_csv(TAB / "phase2b_alcohol.csv", index=False)
    return wrows, arows

# ================================================================ PHASE 2C
def phase2c_food():
    rows = []
    all_intervals = {}
    for p in PARTICIPANTS:
        fdir = DATA / p / "food-images"
        files = [f for f in fdir.iterdir() if f.suffix.lower() in (".jpg", ".jpeg", ".png")]
        recs = []
        corrupt = []
        for f in files:
            try:
                sz = f.stat().st_size
                with Image.open(f) as im:
                    im.load()  # force decode -> catches corruption
                    fmt, size, mode = im.format, im.size, im.mode
                    ex = im._getexif() or {}
                    tags = {ExifTags.TAGS.get(k, k): v for k, v in ex.items()}
                    dt_raw = tags.get("DateTime") or tags.get("DateTimeOriginal") or ""
                    gps = tags.get("GPSInfo")
                    ori = tags.get("Orientation")
                    try:
                        dt = datetime.strptime(dt_raw, "%Y:%m:%d %H:%M:%S") if dt_raw else None
                    except Exception:
                        dt = None
                        corrupt.append((f.name, f"bad DateTime {dt_raw}"))
                    recs.append(dict(file=f.name, suffix=f.suffix.lower(), format=fmt,
                                     width=size[0], height=size[1], mode=mode, size_bytes=sz,
                                     datetime=str(dt) if dt else "", has_datetime=bool(dt),
                                     has_gps=bool(gps), has_orientation=ori is not None,
                                     orientation=str(ori)))
            except Exception as e:
                corrupt.append((f.name, str(e)[:120]))
                recs.append(dict(file=f.name, suffix=f.suffix.lower(), format="UNREADABLE",
                                 width=0, height=0, mode="", size_bytes=f.stat().st_size if f.exists() else 0,
                                 datetime="", has_datetime=False, has_gps=False,
                                 has_orientation=False, orientation=""))
        df = pd.DataFrame(recs)
        df.to_csv(TAB / f"phase2c_food_files_{p}.csv", index=False)
        # resolutions / modes / sizes
        res = Counter(zip(df["width"], df["height"]))
        modes = Counter(df["mode"])
        fmts = Counter(df["format"])
        n = len(df)
        rows.append(dict(participant=p, n_images=n,
                         formats=str(dict(fmts)),
                         color_modes=str(dict(modes)),
                         top_resolutions="; ".join(f"{w}x{h}:{c}" for (w, h), c in res.most_common(3)),
                         mean_kb=round(df["size_bytes"].mean() / 1024, 1),
                         min_kb=round(df["size_bytes"].min() / 1024, 1),
                         max_kb=round(df["size_bytes"].max() / 1024, 1),
                         pct_datetime=round(100 * df["has_datetime"].mean(), 1),
                         pct_gps=round(100 * df["has_gps"].mean(), 1),
                         pct_orientation=round(100 * df["has_orientation"].mean(), 1),
                         n_corrupt_or_unreadable=len(corrupt),
                         corrupt_list="; ".join(f"{a}({b})" for a, b in corrupt[:10])))
        # meal cadence intervals
        dts = sorted(pd.to_datetime(df.loc[df["has_datetime"], "datetime"]).tolist())
        iv = pd.Series([(b - a).total_seconds() for a, b in zip(dts, dts[1:])]) if len(dts) > 1 else pd.Series([], dtype=float)
        all_intervals[p] = iv
        if len(iv):
            st = summarize_numeric(iv / 3600)  # hours
            iv.to_csv(TAB / f"phase2c_meal_intervals_sec_{p}.csv", index=False)
            rows[-1].update(dict(
                median_interval_h=round(float(iv.median() / 3600), 2),
                p25_interval_h=round(float(iv.quantile(.25) / 3600), 2),
                p75_interval_h=round(float(iv.quantile(.75) / 3600), 2),
                pct_intervals_le_30min=round(100 * float((iv <= 1800).mean()), 1),
                pct_intervals_le_60min=round(100 * float((iv <= 3600).mean()), 1),
                pct_intervals_gt_6h=round(100 * float((iv > 21600).mean()), 1)))
        else:
            rows[-1].update(dict(median_interval_h="—", p25_interval_h="—", p75_interval_h="—",
                                 pct_intervals_le_30min="—", pct_intervals_le_60min="—", pct_intervals_gt_6h="—"))
        # uuid/screenshot heuristic: p05 has 3 uuid names; p01 has 1 png
        weird = [r["file"] for r in recs if re.match(r"^[0-9a-f-]{30,}", r["file"]) or r["suffix"] == ".png"]
        rows[-1]["screenshot_or_uuid_names"] = "; ".join(weird) if weird else "—"
    out = pd.DataFrame(rows)
    out.to_csv(TAB / "phase2c_food_summary.csv", index=False)
    return out, all_intervals

def phase2c_injury():
    import ast
    rows = []
    total_events = 0
    loc_counter = Counter(); sev_counter = Counter()
    exposure_hours = {}
    for p in PARTICIPANTS:
        df = pd.read_csv(DATA / p / "pmsys" / "injury.csv")
        events = []
        for _, r in df.iterrows():
            raw = r["injuries"]
            try:
                d = ast.literal_eval(str(raw)) if pd.notna(raw) else {}
            except Exception:
                d = {}
            if isinstance(d, dict) and len(d):
                events.append((r["effective_time_frame"], d))
                for k, v in d.items():
                    loc_counter[(p, k)] += 1
                    sev_counter[(p, v)] += 1
        total_events += len(events)
        # exposure: srpe duration + exercise activeDuration
        srpe = pd.read_csv(DATA / p / "pmsys" / "srpe.csv")
        srpe_min = float(pd.to_numeric(srpe["duration_min"], errors="coerce").sum()) if len(srpe) else 0
        ex = load_json_list(DATA / p / "fitbit" / "exercise.json")
        ex_min = sum((x.get("activeDuration", x.get("duration", 0)) or 0) / 60000 for x in ex)
        exposure_hours[p] = dict(srpe_min=srpe_min, exercise_min=ex_min,
                                 total_min=srpe_min + ex_min,
                                 total_h=(srpe_min + ex_min) / 60)
        rows.append(dict(participant=p, n_injury_reports=len(df),
                         n_reports_with_event=len(events),
                         events="; ".join(f"{t} {d}" for t, d in events) if events else "—",
                         srpe_hours=round(srpe_min / 60, 2), exercise_hours=round(ex_min / 60, 2),
                         total_exposure_h=round((srpe_min + ex_min) / 60, 2)))
    out = pd.DataFrame(rows)
    # incidence per 1000h
    tot_h = sum(v["total_h"] for v in exposure_hours.values())
    tot_h_srpe_only = sum(v["srpe_min"] / 60 for v in exposure_hours.values())
    out.to_csv(TAB / "phase2c_injury_summary.csv", index=False)
    pd.DataFrame([dict(participant=p, location=loc, n=c) for (p, loc), c in loc_counter.items()]).to_csv(
        TAB / "phase2c_injury_locations.csv", index=False)
    pd.DataFrame([dict(participant=p, severity=sev, n=c) for (p, sev), c in sev_counter.items()]).to_csv(
        TAB / "phase2c_injury_severity.csv", index=False)
    # class imbalance: injury-event days vs non-injury days over horizon
    imb = []
    for p in PARTICIPANTS:
        df = pd.read_csv(DATA / p / "pmsys" / "injury.csv")
        import ast as _ast
        event_days = set()
        for _, r in df.iterrows():
            try:
                d = _ast.literal_eval(str(r["injuries"])) if pd.notna(r["injuries"]) else {}
            except Exception:
                d = {}
            if isinstance(d, dict) and len(d):
                event_days.add(pd.to_datetime(r["effective_time_frame"], utc=True).date())
        imb.append(dict(participant=p, injury_event_days=len(event_days),
                        horizon_days=152, non_event_days=152 - len(event_days),
                        imbalance_ratio=f"1:{(152 - len(event_days)) // max(len(event_days), 1)}" if len(event_days) else "0 events",
                        event_day_rate_pct=round(100 * len(event_days) / 152, 2)))
    pd.DataFrame(imb).to_csv(TAB / "phase2c_class_imbalance.csv", index=False)
    return out, tot_h, tot_h_srpe_only, total_events

# ================================================================ RENDER
def main():
    print("Phase 1: inventory ...")
    inv = phase1_inventory()
    print("Phase 1: schema matrix ...")
    schema = phase1_schema_matrix()
    print("Phase 1: temporal horizon ...")
    hor = phase1_temporal_horizon()
    print("Phase 2a: missingness ...")
    miss = phase2a_minute_missingness()
    print("Phase 2a: nonwear (slow: HR resample) ...")
    nonwear = phase2a_nonwear()
    print("Phase 2a: daily distributions ...")
    daily = phase2a_daily_distributions()
    print("Phase 2a: HR ...")
    hr = phase2a_hr()
    print("Phase 2a: sleep ...")
    sleepd = phase2a_sleep()
    print("Phase 2b: wellness ...")
    phase2b_wellness()
    print("Phase 2b: srpe ...")
    phase2b_srpe()
    print("Phase 2b: weight/alcohol ...")
    phase2b_weight_alcohol()
    print("Phase 2c: food ...")
    phase2c_food()
    print("Phase 2c: injury ...")
    phase2c_injury()
    print("Rendering markdown reports ...")
    render_all()
    print("Done. Outputs in analysis/ + analysis/tables/")

def render_all():
    inv = pd.read_csv(TAB / "phase1_file_inventory.csv")
    hor = pd.read_csv(TAB / "phase1_temporal_horizon.csv")
    miss = pd.read_csv(TAB / "phase2a_minute_missingness.csv")
    nonwear = pd.read_csv(TAB / "phase2a_nonwear_summary.csv")
    daily = pd.read_csv(TAB / "phase2a_daily_distributions.csv")
    hr = pd.read_csv(TAB / "phase2a_hr_zones.csv")
    sleepd = pd.read_csv(TAB / "phase2a_sleep_distributions.csv")
    # ---- phase1
    with open(OUT / "phase1_schema_audit.md", "w") as f:
        f.write("# Phase 1 — Database Architecture & Exhaustive Schema Audit\n\n")
        f.write(f"_Generated {datetime.now():%Y-%m-%d %H:%M} from `data/` (p01/p03/p05). "
                "Machine-readable tables in `analysis/tables/phase1_*.csv`._\n\n")
        f.write("## 1.1 File & directory inventory\n\n")
        f.write("Expected layout per participant: `fitbit/` (8 JSON + `sleep_score.csv`), "
                "`pmsys/` (3 CSV), `googledocs/reporting.csv`, `food-images/` (loose JPG/JPEG/PNG, "
                "mission text mentions `food-images.zip` but on disk images are already unzipped per-participant folders).\n\n")
        f.write(md_table(inv) + "\n\n")
        f.write("**Key completeness findings**\n\n")
        f.write("- `heart_rate.json` **absent for p03 only** (p01 1,573,165 rows; p05 1,370,967 rows). "
                "All downstream HR-dependent features are structurally missing for p03.\n")
        f.write("- All other JSON/CSV files present for all 3 participants. No `food-images.zip`; "
                "counts are p01=321, p03=136, p05=186 loose images.\n")
        f.write("- `participant-overview.xlsx` at root covers **16 participants (p01–p16)** "
                "while sensor-grade data exists only for p01/p03/p05 (subset design).\n\n")
        f.write("## 1.2 Schema Integrity Matrix (condensed)\n\n")
        f.write("Full matrix: `tables/phase1_schema_matrix.csv` "
                "(one row per dataset×participant×field + `__RECORD__/__LAST__/__DRIFT__` probes). "
                "Condensed contract below; **PK = primary key / join key**, TS = timestamp.\n\n")
        f.write("| Dataset | Grain / PK | Timestamp col + observed format | Fields & types | Drift / caveats |\n")
        f.write("|---|---|---|---|\n")
        f.write("| `fitbit/calories.json` | 1 min; PK=`dateTime` | `dateTime`: `YYYY-MM-DD HH:MM:SS` (e.g. `2019-11-01 00:00:00`) | `value`: numeric string (kcal/min, e.g. `1.39`) | p01/p03/p05 identical; full 218,880 rows each |\n")
        f.write("| `fitbit/distance.json` | 1 min (sparse); PK=`dateTime` | same minute format | `value`: numeric string (cm/min per aggregator; e.g. `0`, `1090`) | **p01 218,836 rows with 226 DST-duplicate `2020-03-29` zero rows**; p03 53,042 rows / 122 days; p05 111,231 rows / 144 days |\n")
        f.write("| `fitbit/steps.json` | 1 min (sparse); PK=`dateTime` | same minute format | `value`: numeric string (steps/min) | identical row counts to distance per participant (co-emitted); same p01 DST duplicates |\n")
        f.write("| `fitbit/heart_rate.json` | ~5 s; PK=`dateTime` (sec precision) | `dateTime`: `YYYY-MM-DD HH:MM:SS` (e.g. `2019-11-01 00:00:05`) | `value.bpm`: int 30–200; `value.confidence`: int {0,1,2,3} | **MISSING for p03**; p01 median Δt=5 s mean 8.3 s; p05 median 5 s mean 9.5 s; long gaps (p01 max 10.5 h, p05 max 7.6 d) |\n")
        f.write("| `fitbit/resting_heart_rate.json` | 1 day; PK=`dateTime` | `dateTime`: midnight `YYYY-MM-DD 00:00:00` | `value.date`: `MM/DD/YY` or null; `value.value`: float bpm; `value.error`: float | **Sentinel `value=0.0 + date=null + error=0.0`** = missing: p03 51/152, p05 9/95; p05 coverage starts 2019-12-28 (95 rows vs 152) |\n")
        f.write("| `fitbit/time_in_heart_rate_zones.json` | 1 day; PK=`dateTime` | midnight daily | `value.valuesInZones`: {BELOW_DEFAULT_ZONE_1, IN_DEFAULT_ZONE_1 (fat-burn 50–69%), IN_DEFAULT_ZONE_2 (cardio 70–84%), IN_DEFAULT_ZONE_3 (peak 85–100%)} float min | p01 152 rows; **p03 117 rows (35 missing days)**; p05 145 rows; zone HR bounds depend on `220−age` / measured maxHR (see overview) |\n")
        f.write("| `fitbit/sleep.json` | 1 night; PK=`logId` (+`dateOfSleep`) | `startTime`: `YYYY-MM-DD HH:MM:SS`; `endTime`: ISO `YYYY-MM-DDT HH:MM:SS.000`; `dateOfSleep`: `YYYY-MM-DD` (morning-attribution) | `minutesAsleep/minutesAwake/timeInBed/efficiency/type∈{stages,classic}/levels.summary/levels.data[]/mainSleep` | **Type drift**: p01 155/155 stages; p03 78 stages + 6 classic; p05 122 stages + 11 classic. `classic` has only {asleep,restless,awake} — no deep/light/REM split. `mainSleep=False` naps: p03 3, p05 10 |\n")
        f.write("| `fitbit/exercise.json` | 1 bout; PK=`logId` | `startTime`: `YYYY-MM-DD HH:MM:SS` | `activityName/activityTypeId/activityLevel[]/averageHeartRate/calories/duration+activeDuration (ms)/steps/logType∈{auto_detected,tracker}/heartRateZones[]/elevationGain/hasGps` | p01 190 (Walk 150/Sport 15/Run 14/Treadmill 11); p03 57 (Walk 54); p05 145 (Walk 80/Bike 54+2/Run 4/…) — sparse, auto-detected heavy |\n")
        f.write("| `fitbit/sleep_score.csv` | 1 night; PK=`sleep_log_entry_id` | `timestamp`: ISO `YYYY-MM-DDTHH:MM:SSZ` | `overall_score 0–100/composition_score/revitalization_score/duration_score/deep_sleep_in_minutes/resting_heart_rate/restlessness` all numeric | p01 150, p03 74, p05 117 rows; join to sleep.json on logId↔sleep_log_entry_id |\n")
        f.write("| `pmsys/wellness.csv` | 1 morning row; PK=`effective_time_frame` | ISO `YYYY-MM-DDTHH:MM:SS.sssZ` | `fatigue/mood/readiness/sleep_duration_h/sleep_quality/soreness/stress` ints; `soreness_area` JSON-list of anatomical IDs | 9 cols stable; scales observed 0–4/0–8 (see Phase 2B); soreness_area `[]` dominant |\n")
        f.write("| `pmsys/srpe.csv` | 1 session; PK=`end_date_time` | ISO with ms + `Z` | `activity_names` JSON-list; `perceived_exertion` int 1–10; `duration_min` int | p01 34, p03 2, p05 9 rows — extremely sparse for p03/p05 |\n")
        f.write("| `pmsys/injury.csv` | 1 report; PK=`effective_time_frame` | ISO with ms + `Z` | `injuries`: Python-dict string `{location: minor|major}` or `{}` | p01 24 reports/1 event; p03 11/0 events; p05 10/10 events (recurrent left_foot) |\n")
        f.write("| `googledocs/reporting.csv` | 1 day; PK=`date` | `date`: `DD/MM/YYYY`; `timestamp`: `DD/MM/YYYY HH:MM:SS` (**submission lags log date by days–month**, e.g. log 06/11 submitted 06/12) | `meals` comma-set {Breakfast,Lunch,Dinner,Evening}; `weight` float; `glasses_of_fluid` int; `alcohol_consumed` {Yes,No} | 6 cols stable; weight missing 27/109 p01, 24/117 p03, 25/126 p05 |\n")
        f.write("| `food-images/` | 1 photo; PK=EXIF DateTime + filename | EXIF `DateTime`/`DateTimeOriginal` `YYYY:MM:DD HH:MM:SS` | JPEG (+1 PNG p01); RGB; EXIF GPS/Orientation | p01 GPS 99.4% vs p03/p05 0% (device/settings split); strict `DateTime`-tag gaps: p01 2/321 (`IMG_8958.jpeg`, `IMG_9111.png` — both have DateTimeOriginal; dropped by current `food_reader`), p03/p05 0 |\n")
        f.write("| `participant-overview.xlsx` | 1 row/participant; PK=`Participant ID` | `First 5km Run Date` mixed (datetimes + literal `november`/`injured`) | `Age/Height/Gender/A-or-B-person/MaxHR/5km Date+Min+Sec/Stride walk+run` | 16 rows p01–p16; MaxHR missing p07/p12/p15; strides missing p03/p12; p14 run stride 11.3 cm implausible; p16 5km date 2020-11-16 out of window |\n\n")
        f.write("**Ingestion implications (also see Phase 3):** strip p01 DST-duplicate timestamps (keep first); "
                "treat RHR `0.0` as NaN, not 0 bpm; branch sleep logic on `type` (classic ≠ stages); "
                "never inner-join on HR for p03; parse `reporting.csv:date` dayfirst and keep `timestamp` as submission-time feature "
                "(lag = recall bias proxy); patch `food_reader` EXIF key to `DateTime OR DateTimeOriginal` (2 p01 files currently invisible).\n\n")
        f.write("## 1.3 Temporal Alignment & Horizon Table\n\n")
        f.write("Reference horizon = Fitbit export window **2019-11-01 → 2020-03-31 (152 days)**. "
                "Table: `tables/phase1_temporal_horizon.csv`.\n\n")
        f.write(md_table(hor, floatfmt=".1f") + "\n\n")
        f.write("**Overlap reading**\n\n")
        f.write("- **Fitbit backbone is complete** for calories (152/152 days, all participants) but steps/distance are thinned for p03 (122 d) and p05 (144 d, truncated 2020-03-31 05:27).\n")
        f.write("- **RHR**: p01 full 152 d; p03 152 rows but only 101 valid (51 sentinel zeros); p05 starts 2019-12-28 (95 rows, 86 valid) — "
                "no usable RHR baseline for p05 in Nov–Dec 2019.\n")
        f.write("- **HR zones**: p01 152 d; p05 145 d; p03 117 d (23% missing) — zone-based load features have participant-specific missingness.\n")
        f.write("- **Sleep**: p01 155 logs ≈ full coverage; p05 133; p03 84 (≈55%) with 6 classic-type low-resolution nights.\n")
        f.write("- **Wellness**: p01 138 rows/138 d (91%), p05 137 rows/134 d (88%), p03 82 rows/78 d (51%) — p03 subjective state is half-missing.\n")
        f.write("- **sRPE**: p01 34 sessions vs p03 2 vs p05 9 — training-load modelling is p01-driven; p03/p05 loads must fall back to Fitbit exercise bouts.\n")
        f.write("- **Reporting**: 109/117/126 logged rows (100/113/117 distinct log days; 66–77% of horizon) but submission timestamps lag by up to a month (batch logging).\n")
        f.write("- **Food images**: EXIF datetimes span **February–March** (p01 2020-02-01→03-31, 60 d; p03 2020-02-01→03-31, 51 d; p05 2020-02-01→03-29, 47 d) — "
                "a 2-month nutrition sub-study (Feb–Mar) inside the 5-month monitoring window. Overlap with other modalities is Feb–Mar only.\n")
        f.write("- **Injury reports**: sporadic weekly cadence Nov→Mar; events: p01 1, p03 0, p05 10 (recurrent).\n")

    # ---- phase2a
    with open(OUT / "phase2a_fitbit.md", "w") as f:
        f.write("# Phase 2A — High-Frequency Wearable Data (Fitbit)\n\n")
        f.write(f"_Generated {datetime.now():%Y-%m-%d %H:%M}. Tables: `tables/phase2a_*.csv`._\n\n")
        f.write("## 2A.1 Sampling regularity & dropouts (minute level)\n\n")
        f.write(md_table(miss) + "\n\n")
        f.write("- **Calories**: perfect 218,880/218,880 minute slots per participant — export is gap-filled (likely imputed zeros), "
                "so calories alone cannot signal wear.\n")
        f.write("- **Steps/distance p01**: 218,836 rows = 44 short of full, but 226 duplicated timestamps on **2020-03-29** "
                "(DST transition; all duplicates value `0`). Net unique = 218,610 → **270 missing minute-slots (0.12%)**. "
                "69/152 days show 1,439 rows; one day shows 1,465 (duplicates). Action: dedupe keep-first before any resampling.\n")
        f.write("- **Steps/distance p03**: only 53,042 rows over 122 days (mean 435 min/d, min 1 min/d). "
                "30/152 days have zero step/distance rows. This is **structural sparsity** (device off / sync failure), not random missingness.\n")
        f.write("- **Steps/distance p05**: 111,231 rows over 144 days (mean 772 min/d); stream ends 2020-03-31 05:27. "
                "Every present day is partial (<1,049 rows). Missingness is diurnal (nights pruned) — see non-wear table.\n")
        f.write("- **Heart rate**: p01 1.57M samples (median Δt 5 s, mean 8.3 s, p90 15 s, max gap 10.5 h); "
                "p05 1.37M (median 5 s, mean 9.5 s, max gap 7.6 days — late-March dropout); **p03 file absent**. "
                "Confidence mix p01 {1:31.6%, 2:38.8%, 3:29.1%, 0:0.6%}, p05 similar — weight or filter `confidence==0`.\n\n")
        f.write("## 2A.2 Non-wear time (≥60 consecutive min of zero steps AND missing/flatlined HR)\n\n")
        f.write(md_table(nonwear) + "\n\n")
        f.write("Per-day series: `tables/phase2a_nonwear_per_day.csv`. Definition caveats: missing minute-slots count as zero steps; "
                "HR-flatlined = per-minute std==0 with ≥2 samples (charging/clipped sensor). "
                "For **p03 the HR clause is vacuous** (no HR file) so the estimate is steps-only and conflates sleep with non-wear — "
                "interpret p03 non-wear as an upper bound. Night-time 6–9 h runs are expected (sleep + charging); "
                "daytime runs >2 h are the actionable off-wrist/battery signal (join with charging gaps in HR Δt).\n\n")
        f.write("## 2A.3 Distributional profiles — daily steps / distance / calories / active minutes\n\n")
        f.write(md_table(daily) + "\n\n")
        f.write("Full per-day values: `tables/phase2a_daily_values.csv`. Columns: n, mean, median, sd, q25, q75, iqr, skew, p1, p99, min, max.\n\n")
        dailyp = pd.read_csv(TAB / "phase2a_daily_values.csv")
        for col in [c for c in dailyp.columns if c.startswith("p0")]:
            try:
                f.write("```\n" + ascii_hist(dailyp[col].dropna(), bins=10, title=col) + "\n```\n\n")
            except Exception:
                pass
        f.write("Read the skew/p1/p99 columns for zero-inflation (p03 steps) and heavy right tails (long-run days). "
                "Active minutes derive from `exercise.json:activeDuration`; days without bouts are true zeros, not missing.\n\n")
        f.write("## 2A.4 Heart-rate distributions: RHR baseline, peak HR, cardiac zones\n\n")
        f.write(md_table(hr) + "\n\n")
        f.write("- **RHR**: p01 fully observed (drift 2nd-half − 1st-half ≈ small; see table); "
                "p03 51 sentinel zeros must be excluded (code in `aggregator.aggregate_activity` already filters `value>0`); "
                "p05 baseline starts late Dec — early-window RHR features must be NaN, not carried back.\n")
        f.write("- **Continuous HR**: p01 mean 64.5 bpm (median 59, p99 ≈ high, max 191); p05 mean 74.7 (median 73, max 200). "
                "p05 runs ~10 bpm hotter — age/maxHR context (overview: p01 maxHR 182 @48 y; p05 184 @35 y) does not explain it; "
                "treat as individual baseline, always z-score within participant.\n")
        f.write("- **Daily peak HR** row quantifies workout reach; cross-check against `exercise.averageHeartRate` max "
                "(p01 163, p03 167, p05 144 bpm) and age-predicted max (220−age: p01 172, p03 195, p05 185).\n")
        f.write("- **Zones** (min/day): BELOW_ZONE dominates (~1,200 min/d ≈ sleep+sedentary); "
                "fat-burn/cardio/peak minutes are zero-inflated — model as hurdle/zero-inflated features. "
                "Zone cut-points are participant-relative (50–69/70–84/85–100% of max) so cross-participant minute comparisons need maxHR normalisation.\n\n")
        f.write("## 2A.5 Sleep architecture vs normative athletic ranges\n\n")
        f.write("Normative refs: Deep 15–25%, REM 20–25% of total sleep; Light ~50–60%; Wake (WASO + latency) <10–15%; "
                "efficiency ≥85%; duration 7–9 h (athletes 8–10 h).\n\n")
        f.write(md_table(sleepd) + "\n\n")
        f.write("Night-level file: `tables/phase2a_sleep_nights_{p01,p03,p05}.csv`; "
                "stage percentages: `tables/phase2a_sleep_architecture_pct.csv` (stages-type nights only; classic nights excluded from % computation).\n\n")
        arch = pd.read_csv(TAB / "phase2a_sleep_architecture_pct.csv")
        if len(arch):
            f.write("```\n")
            for c in ["deep_pct", "light_pct", "rem_pct", "wake_pct"]:
                f.write(ascii_hist(arch[c], bins=12, title=f"all-participants {c}") + "\n")
            f.write("```\n\n")
        f.write("Interpretation verdict (median stage % vs bands Deep 15–25 / REM 20–25): "
                "**p01 deep 9.4% (LOW) / REM 14.1% (LOW)** — fragmented or light-dominated sleep despite 97% efficiency; "
                "**p03 deep 15.3% (OK-low) / REM 17.5% (borderline)**; **p05 deep 17.1% (OK) / REM 21.3% (OK)**. "
                "p01's low deep+REM with high light share (65.3%) is the outlier to investigate (age 48, latest chronotype-A, RHR 52 bpm). "
                "Flag systematic low-deep (<13%) as possible fragmented sleep or classic-type under-resolution for p03/p05; "
                "join `sleep_score.csv:restlessness` + WASO (`wake` min) for agitation signal.\n")

    # ---- phase2b
    wresp = pd.read_csv(TAB / "phase2b_wellness_response.csv")
    lik = pd.read_csv(TAB / "phase2b_likert_distributions.csv")
    intra = pd.read_csv(TAB / "phase2b_intra_vs_inter.csv")
    srpe = pd.read_csv(TAB / "phase2b_srpe_summary.csv")
    weight = pd.read_csv(TAB / "phase2b_weight.csv")
    alcohol = pd.read_csv(TAB / "phase2b_alcohol.csv")
    whour = pd.read_csv(TAB / "phase2b_wellness_hour.csv")
    with open(OUT / "phase2b_subjective.md", "w") as f:
        f.write("# Phase 2B — Subjective & Periodic Logs (PMSYS + Google Docs)\n\n")
        f.write(f"_Generated {datetime.now():%Y-%m-%d %H:%M}. Tables: `tables/phase2b_*.csv`._\n\n")
        f.write("## 2B.1 Response rates & submission-time cadence\n\n")
        f.write(md_table(wresp) + "\n\n")
        f.write("Wellness submission hour (UTC) — counts per hour:\n\n")
        f.write("```\n")
        for p in PARTICIPANTS:
            sub = whour[whour["participant"] == p].sort_values("hour")
            f.write(f"{p}: " + ", ".join(f"{int(r['hour']):02d}h:{int(r['n'])}" for _, r in sub.iterrows()) + "\n")
        f.write("```\n\n")
        f.write("- **Adherence**: p01 91%, p05 88% of horizon days; **p03 51%** — any longitudinal model must handle p03 block-missingness (not MCAR: gaps cluster).\n")
        f.write("- **Timing**: p05 is the compliant morning reporter (49×06h + 38×05h); p01 centres 07–08h with afternoon/evening tail "
                "(20h:5, 22h:3 — recall-delayed rows); **p03 is erratic** (reports at 23h×7, 00–03h×4, spread across all 24 h). "
                "Weight morning-vs-evening comparisons by submission hour; consider excluding post-12h wellness rows from 'morning readiness' features.\n")
        f.write("- **Reporting.csv lag**: `date` (log day, DD/MM/YYYY dayfirst) vs `timestamp` (submission) differ by days–weeks "
                "(e.g. p01 log 06/11 submitted 06/12; p03 logs 15–16/11 submitted 20/11). Lag itself is a compliance feature; "
                "weight/alcohol values are recalled, not measured same-day.\n\n")
        f.write("## 2B.2 Likert distributions & floor/ceiling effects\n\n")
        f.write(md_table(lik) + "\n\n")
        for _, r in lik.iterrows():
            f.write(f"- {r['participant']}/{r['metric']}: mode={r['mode']} ({r['mode_share']} of rows), "
                    f"unique={r['n_unique']}, range [{r['min']},{r['max']}], counts {{{r['value_counts']}}}\n")
        f.write("\n- **Floor/ceiling**: 1–5 scales never use the full span per participant "
                "(p03 readiness ∈ {3,4,5,6} only; p05 readiness ∈ {0,3,4,5,8} with 0s = likely missed-question sentinel). "
                "p05 0-values on fatigue/mood/readiness/sleep_duration_h/sleep_quality/soreness/stress need sentinel audit before modelling "
                "(0 outside the 1–5 instrument = missing, not 'no fatigue').\n")
        f.write("- **Constant-3s check**: no participant is a pure constant responder, but `soreness_area=[]` dominates "
                "(p01 78/138, p03 79/82, p05 135/137) and p03 wellness SDs are the smallest — low-signal subject.\n\n")
        f.write("## 2B.3 Intra- vs inter-individual variance\n\n")
        f.write(md_table(intra) + "\n\n")
        f.write("Rule of thumb: ratio between/within <0.5 → personal baselines dominate; standardise within participant "
                "(z-score / median-centre) before any pooled model. Readiness shows the largest between-subject spread (scale 0–10 vs 1–5).\n\n")
        f.write("## 2B.4 sRPE load, spikes, monotony & strain\n\n")
        f.write("sRPE load = RPE × duration_min. Monotony = mean(daily load)/sd(daily load); Strain = Σload × monotony "
                "(Foster). Daily-load series: `tables/phase2b_srpe_daily_load_{p01,p03,p05}.csv`.\n\n")
        f.write(md_table(srpe) + "\n\n")
        f.write("- **Sparsity warning**: p03 has 2 sessions, p05 has 9 (one with missing RPE/duration → load NaN) — "
                "monotony/strain are degenerate for p03/p05 (sd≈0-inflated by 150 zero days). Report them but do not model on sRPE alone; "
                "fuse with Fitbit exercise minutes + HR-zone load (Edwards TRIMP) for exposure.\n")
        f.write("- **p01** (34 sessions, total load ≈ high): spike days = daily load > mean+2sd; inspect weekly monotony >2.0 as overtraining flag. "
                "Activity mix: individual/running + team/soccer + endurance — load should be stratified by type.\n\n")
        f.write("## 2B.5 Weight stability: noise vs true mass change\n\n")
        f.write(md_table(weight) + "\n\n")
        f.write("- All participants are **hyper-stable**: range 3 kg (p01 99–102), 2 kg (p03 82–84), 4 kg (p05 99–103); "
                "CV <1%; mean |day-to-day| <0.5 kg (scale noise + hydration). No >2 kg jumps observed → no true mass-change events; "
                "treat weight as slow drift (7-day median) + hydration residual, not a daily feature.\n")
        f.write("- Missingness 20–25% per participant; p01 weight fixed at 100.0 for long stretches (rounding/heaping) — "
                " Bland-Altman vs bioimpedance unavailable; assume ±0.5 kg instrument noise.\n\n")
        f.write("## 2B.6 Alcohol: frequency, volume proxy, temporal clustering\n\n")
        f.write(md_table(alcohol) + "\n\n")
        f.write("- **Frequency**: p01 0/109 (complete abstinence — zero-variance predictor, drop from models); "
                "p03 48/117 (41%); p05 27/126 (21%). Unit volumes are NOT logged (binary Yes/No only) — dose-response is unidentifiable; "
                "use binary + previous-day + weekend-binge flags.\n")
        f.write("- **Clustering**: check `by_weekday` + Fri–Sun share columns for post-match weekend pattern; "
                "p03's 41% rate with `Lunch, Evening` meal pattern suggests evening social drinking — join with wellness-next-day "
                "(sleep_quality/readiness dip) for effect estimation.\n")

    # ---- phase2c
    food = pd.read_csv(TAB / "phase2c_food_summary.csv")
    inj = pd.read_csv(TAB / "phase2c_injury_summary.csv")
    imb = pd.read_csv(TAB / "phase2c_class_imbalance.csv")
    try:
        loc = pd.read_csv(TAB / "phase2c_injury_locations.csv")
    except Exception:
        loc = pd.DataFrame()
    try:
        sev = pd.read_csv(TAB / "phase2c_injury_severity.csv")
    except Exception:
        sev = pd.DataFrame()
    with open(OUT / "phase2c_food_injury.md", "w") as f:
        f.write("# Phase 2C — Food Images & EXIF Integrity + Adverse Events\n\n")
        f.write(f"_Generated {datetime.now():%Y-%m-%d %H:%M}. Tables: `tables/phase2c_*.csv`._\n\n")
        f.write("## 2C.1 Metadata & technical formats\n\n")
        f.write(md_table(food) + "\n\n")
        f.write("- **Formats**: p01 320×JPEG + 1×PNG (`IMG_9111.png` — likely screenshot/export, verify visually); "
                "p03 136×JPG; p05 183×JPG + 3 UUID-named JPGs (app-exported, e.g. `281dad76-…​.jpg` — check for screenshots/duplicates).\n")
        f.write("- **Colour**: 100% RGB (no grayscale/CMYK); no HEIC in this export despite mission brief listing it — ingestion only needs JPEG/PNG path.\n")
        f.write("- **Resolutions**: p01 uniform 4032×3024 (12 MP landscape, iPhone-class); p03 mixed 3024×4032 portrait + 1932×2576 (older device or downscaled); "
                "p05 3024×4032 portrait. Orientation tag present 99–100% — auto-rotate on load.\n")
        f.write("- **Sizes**: p01 mean ≈2.2 MB (0.25–7.8 MB); p03 mean ≈1.1 MB; p05 mean ≈2.0 MB — consistent with native camera exports, not recompressed thumbnails.\n")
        f.write("- **EXIF completeness**: strict `DateTime` tag (0x0132, the key used by `food_reader.photo_selector_by_date_player`): "
                "p01 319/321 (99.4%), p03 136/136, p05 186/186. The 2 p01 gaps (`IMG_8958.jpeg` 1319×834 downscaled, `IMG_9111.png` 1125×2436 screenshot) "
                "carry `DateTimeOriginal` so the audit fallback (DateTime OR DateTimeOriginal) reads 100% — but **current production code drops them**. "
                "Patch `food_reader` to fall back to `DateTimeOriginal`, and quarantine the 2 files as screenshot/downscaled non-food candidates. "
                "GPS **p01 99.4% vs p03/p05 0%** (privacy strip or device setting — do not use GPS as join key); "
                "Orientation 99–100%. Log dateless drops as `NO_DATE_EXCLUDED` rather than imputing.\n")
        f.write("- **Corruption**: PIL `load()` decode attempted on every file — failures listed in `corrupt_list` (all zero here); "
                "no 0-dimension reads. "
                "Vision-level food-vs-non-food (blurred/pocket/drinks-only) comes from the Gemini `is_photo_food` pass — "
                "see §2C.4 for results; its YES/NO output is wired into `tables/phase2c_food_files_*.csv` as `is_food`.\n\n")
        f.write("## 2C.2 Temporal grouping & meal-cadence threshold (data-derived: 15 s; legacy 1800 s)\n\n")
        f.write("Interval = seconds between consecutive EXIF datetimes per participant (all photos, datetimes sorted). "
                "Files: `tables/phase2c_meal_intervals_sec_{p01,p03,p05}.csv`.\n\n")
        f.write("**Threshold derivation (aggregate, n=640 intervals).** "
                "Fine-binned distribution 0–300 s (15 s bins): 0–15 s: 43; 15–30 s: 4; 30–45 s: 1; 45–60 s: 4; "
                "60–75 s: 1; 75–90 s: 2; 90–105 s: 1; 105–120 s: 0; then the main mass resumes (120–135 s: 3, rising). "
                "A dense left outlier cluster (0–15 s, 6.7% — shutter-burst shots of one dish) is separated by a sparse "
                "valley (15–120 s, 13 events) from the inter-meal mass (≥120 s). "
                "Per the audit rule (high limit of the outlier cluster; 3rd-centile = 3 s fallback not needed — outliers are visible), "
                "**meal_timedelta = 15 s**. "
                "Cumulative shares: ≤15 s 6.7% (43), ≤60 s 8.1% (52), ≤300 s 12.8% (82), ≤1800 s legacy 22.2% (142). "
                "Note the trade-off: 15 s has high precision (bursts are certainly one meal) but lower recall than 1800 s "
                "(before/during shots minutes apart are split); the valley-exit (~120 s) is the documented alternative operating point.\n\n")
        f.write("```\n")
        for p in PARTICIPANTS:
            fp = TAB / f"phase2c_meal_intervals_sec_{p}.csv"
            try:
                _iv = pd.read_csv(fp, header=0).iloc[:, 0] if fp.exists() else pd.Series([], dtype=float)
                iv = pd.to_numeric(_iv, errors="coerce").dropna()
                if len(iv):
                    f.write(ascii_hist(iv / 60, bins=14, title=f"{p} inter-photo interval (minutes)") + "\n")
            except Exception as e:
                f.write(f"{p}: (interval read err {e})\n")
        f.write("```\n\n")
        f.write("- **Threshold read**: `pct_intervals_le_30min` in the summary table is the legacy-1800 s view (22.2% of pairs pre-merged). "
                "Under the derived 15 s rule only burst pairs (6.7%) are pre-merged; vision confirmation (§2C.4) then measures precision. "
                "The production two-stage rule (`same_meal_preselector` + `is_it_same_meal` union-find in "
                "`food_reader.get_macro_nutrients_from_photos`, default 1800 s in `main.py`) should be re-parameterised to 15 s "
                "(or the 120 s valley-exit) to match this evidence.\n")
        f.write("- **Caveat**: EXIF DateTime has 1-second resolution and reflects shutter time; burst shots share identical timestamps (interval 0) — "
                "dedupe exact duplicates before grouping. Late-night snacks past midnight attribute to the next calendar day — align with sleep `dateOfSleep` convention.\n\n")
        _vsum = TAB / "vision_summary.csv"
        _vpairs = TAB / "vision_same_meal_pairs.csv"
        if _vsum.exists():
            vsum = pd.read_csv(_vsum)
            f.write("## 2C.4 Gemini vision results (`is_photo_food` + `is_it_same_meal`)\n\n")
            f.write("Full per-image labels: `tables/phase2c_food_files_*.csv` (`is_food`, `is_food_model`); "
                    "pair decisions: `tables/vision_same_meal_pairs.csv`; run cache: `tables/vision_cache.json` "
                    "(generator: `analysis/vision_run.py`).\n\n")
            f.write("**Model provenance (non-standard, documented here only).** "
                    "First 426 labels by `gemini-3.5-flash-lite` (production model); quota exhausted mid-run "
                    "(`generate_content_free_tier_requests, limit: 500`), so the model string was swapped by hand to "
                    "`gemini-3.1-flash-lite` for all subsequent labels — no rotation logic was added to the code. "
                    "The two models disagree on edge cases: e.g. `p05/IMG_2215.jpg` (vitamin-supplement bottle) is YES under 3.5 "
                    "but NO under 3.1 (stricter 'food or beverages' reading; supplements arguably correctly excluded from macro meals). "
                    "Cross-model labels are therefore not strictly comparable — use `is_food_model` when pooling, and treat "
                    "supplement/packaging shots as a review category before nutrition modelling.\n\n")
            f.write(md_table(vsum) + "\n\n")
            if _vpairs.exists():
                vp = pd.read_csv(_vpairs)
                if len(vp):
                    vp["same_meal"] = vp["same_meal"].astype(bool)
                    sweep = pd.DataFrame([
                        dict(threshold_s=t, n_pairs=int((vp["gap_s"] <= t).sum()),
                             n_confirmed=int(vp.loc[vp["gap_s"] <= t, "same_meal"].sum()),
                             confirm_rate_pct=round(100 * float(vp.loc[vp["gap_s"] <= t, "same_meal"].mean()), 1))
                        for t in (15, 60, 120, 300, 1800)])
                    f.write("Vision confirmation rate by gap cut-off (pairs preselected ≤1800 s, evaluated offline):\n\n")
                    f.write(md_table(sweep) + "\n\n")
                    by15 = vp[vp["gap_s"] <= 15].groupby("participant")["same_meal"].agg(["size", "sum", "mean"]).reset_index()
                    by15.columns = ["participant", "n_pairs_le15s", "n_confirmed_le15s", "confirm_rate"]
                    by15["confirm_rate"] = (by15["confirm_rate"] * 100).round(1)
                    f.write("Derived-15 s operating point, per participant:\n\n")
                    f.write(md_table(by15) + "\n\n")
                    med_c = float(vp.loc[vp["same_meal"], "gap_s"].median())
                    med_r = float(vp.loc[~vp["same_meal"], "gap_s"].median())
                    f.write(f"**Threshold verdict**: confirmation is flat ~72–73% for all cut-offs ≤300 s "
                            f"(15 s: 73.3%, 300 s: 72.2%) and falls to 63.7% at the legacy 1800 s — i.e. gap discriminates "
                            f"mainly through the long tail (confirmed-pair median gap {med_c:.0f} s vs rejected {med_r:.0f} s). "
                            f"The distribution-derived 15 s rule is therefore the conservative high-precision operating point, "
                            f"but vision evidence does not separate it from 120–300 s; the costly over-merging happens between 300 s and 1800 s. "
                            f"Recommendation: re-parameterise production `meal_timedelta` to the 15–120 s range (default 15 s), "
                            f"never 1800 s. "
                            f"Note on provenance: the pair calls were preselected at ≤1800 s because the running process had imported "
                            f"the legacy constant before the hand edit to 15 s took effect — the 15 s evaluation above is the exact offline subset, "
                            f"so no extra API calls were needed. "
                            f"Non-food images (`is_food=NO`) are excluded before grouping, so pocket/blurred/screenshot captures "
                            f"cannot create spurious meals.\n\n")
        f.write("## 2C.3 Adverse events — epidemiology & class balance\n\n")
        f.write(md_table(inj) + "\n\n")
        if len(loc):
            f.write("Locations:\n\n" + md_table(loc) + "\n\n")
        if len(sev):
            f.write("Severity:\n\n" + md_table(sev) + "\n\n")
        f.write(md_table(imb) + "\n\n")
        # incidence
        tot_min_srpe = 0; tot_min_ex = 0
        for _, r in inj.iterrows():
            tot_min_srpe += float(r["srpe_hours"]) * 60 if pd.notna(r["srpe_hours"]) else 0
            tot_min_ex += float(r["exercise_hours"]) * 60 if pd.notna(r["exercise_hours"]) else 0
        tot_h_all = (tot_min_srpe + tot_min_ex) / 60
        # count events
        import ast as _ast
        n_events = 0
        for p in PARTICIPANTS:
            df = pd.read_csv(DATA / p / "pmsys" / "injury.csv")
            for _, r in df.iterrows():
                try:
                    d = _ast.literal_eval(str(r["injuries"])) if pd.notna(r["injuries"]) else {}
                except Exception:
                    d = {}
                if isinstance(d, dict) and len(d):
                    n_events += 1
        f.write(f"- **Totals**: {n_events} injury events in {len(imb)} participants over 152 days "
                f"(p01 1× right_hand minor; p03 0; p05 10× — 9 left_foot minor + 1 head_neck minor; **zero major**). "
                "p05's left_foot repeats 2020-01-30→03-17 = recurrent/chronic complaint, not 10 independent traumas.\n")
        f.write(f"- **Exposure**: sRPE-logged {tot_min_srpe/60:.1f} h + Fitbit-exercise {tot_min_ex/60:.1f} h = **{tot_h_all:.1f} h total**. "
                f"Incidence = {n_events}/{tot_h_all:.1f} h = **{1000*n_events/tot_h_all:.1f} per 1,000 h** (all-source exposure). "
                f"sRPE-only exposure gives {1000*n_events/(tot_min_srpe/60):.1f}/1,000 h — inflated by p03/p05 under-logging; "
                "report both, model on the fused exposure.\n")
        f.write("- **Class imbalance** (event-days vs horizon days): p01 1:151 (0.7%), p03 0:152 (0%), p05 ≈7–10:152 (~5%). "
                "Pooled ≈ 8–11 event-days / 456 participant-days ≈ **1:45–1:55**. Any injury classifier is extreme-imbalanced: "
                "use time-to-event / anomaly-detection framing, not balanced classification; stratify by participant; "
                "never SMOTE across participants.\n")

    # ---- phase3
    with open(OUT / "phase3_preprocessing_modeling.md", "w") as f:
        f.write("# Phase 3 — Pre-processing Design & Modelling Specification\n\n")
        f.write(f"_Generated {datetime.now():%Y-%m-%d %H:%M}. Grounded in Phase 1/2 tables in `analysis/tables/`._\n\n")
        f.write("## 3.1 Design principles (from audit evidence)\n\n")
        f.write("1. **Participant-stratified everything.** Baselines differ by ~10 bpm HR, 18 kg weight, disjoint chronotypes; "
                "pool only residuals/z-scores, never raw values.\n")
        f.write("2. **Missingness is structural, not MCAR.** p03 lacks HR entirely; p05 RHR starts 2019-12-28; p03 wellness 50%; "
                "sRPE sparse for p03/p05 — each feature needs a defined fallback (NaN + missingness indicator), never silent imputation.\n")
        f.write("3. **Timestamps are heterogeneous.** Minute `YYYY-MM-DD HH:MM:SS`, ISO-UTC with ms, DD/MM/YYYY dayfirst, EXIF `YYYY:MM:DD`, "
                "sleep morning-attribution (`dateOfSleep`) vs start-time filtering — all joins go through `standardize_date` + explicit day-attribution rules (§3.3).\n")
        f.write("4. **Sentinels ≠ measurements.** RHR `0.0`, readiness/soreness `0` on 1–5 scales, `soreness_area=[]`, injury `{}`, "
                "duplicate DST zeros — map to NaN/False before statistics.\n\n")
        f.write("## 3.2 Cleaning checklist per source (implement in `src/data_handling/`)\n\n")
        f.write("| Source | Clean step | Rule |\n|---|---|---|\n")
        f.write("| steps/distance | DST dedupe | sort by ts, `drop_duplicates('dateTime', keep='first')`; assert 1440/d max |\n")
        f.write("| steps/distance | sparse-gaps | reindex to full minute grid 2019-11-01→2020-03-31; missing → NaN + `is_missing_min` flag; zero-fill only for sum features with companion missingness covariate |\n")
        f.write("| calories | pass-through | keep as-is (gap-filled export); do not use for wear detection |\n")
        f.write("| HR | confidence filter | drop `confidence==0` (0.6–1.1%); keep 1–3 with `mean_conf` covariate; clip bpm to [30, 220] |\n")
        f.write("| HR | flatline flag | per-minute std==0 with n≥2 → `hr_flat_min` (charger artifact) |\n")
        f.write("| RHR | sentinel | `value<=0 \\| date is null` → NaN; require ≥5 valid nights for baseline; no back-fill before 2019-12-28 for p05 |\n")
        f.write("| zones | missing days | keep NaN (do not zero-fill p03's 35 missing days); renormalise observed days to 1440 min |\n")
        f.write("| sleep | type branch | `stages` → full 4-stage split; `classic` → {asleep, restless, awake} only + `is_classic` flag; exclude `mainSleep=False` naps from nightly features (separate nap covariate) |\n")
        f.write("| sleep_score | join | left-join on logId==sleep_log_entry_id; restlessness ∈ [0.03, 0.20] clip |\n")
        f.write("| exercise | durations | `activeDuration ?? duration` ms→min; drop 0.03-min artifact bouts; keep `logType` + `activityName` strata |\n")
        f.write("| wellness | hour filter | flag `hour>=12` as delayed; 0 on 1–5 scale → NaN (p05); `soreness_area` parse list, `[]`→no-pain |\n")
        f.write("| srpe | load | `load=RPE×duration`; missing RPE/duration → NaN load (p05 2020-02-13 row); daily-load reindex with 0 + `n_sessions` count |\n")
        f.write("| injury | parse | `ast.literal_eval`, non-dict → {}; event = len>0; location+severity one-hots; recurrent p05 left_foot → episode ID, not 10 i.i.d. rows |\n")
        f.write("| reporting | dates | `date` dayfirst, `timestamp` submission; `lag_days=timestamp−date` feature; weight → 7-day median + residual; alcohol {Yes,No}→{1,0} + weekend flag |\n")
        f.write("| food images | EXIF | key on `DateTime` tag; dateless → quarantine list; auto-rotate by Orientation; drop GPS as feature (p03/p05 0%) |\n")
        f.write("| food images | vision | run `is_photo_food` → `is_food`; `same_meal_preselector(15 s, derived §2C.2)` + `is_it_same_meal` confirm; `helper_get_macro_nutrients_from_photos` per meal |\n")
        f.write("| overview | quirks | strip `male\\xa0` whitespace; `november`/`injured` dates → NaT; p14 stride-run 11.3 → NaN; use MaxHR else 220−age |\n\n")
        f.write("## 3.3 Temporal alignment (daily modelling grain)\n\n")
        f.write("- **Day key**: calendar date `YYYY-MM-DD` (local, device time). Sleep night ending on D attributes to D (`dateOfSleep`), matching `aggregator.aggregate_sleep` lookback logic.\n")
        f.write("- **Minute → day**: steps/distance/calories sum; HR → mean/resting/peak/TRIMP + `hr_coverage_min`; zones → min/zone; exercise → Σactive min + session count.\n")
        f.write("- **Wellness (morning D)** predicts day-D load/sleep-next-night; **sRPE (end-time D)** attributes to D; **reporting lag** kept as covariate, values attribute to log `date`.\n")
        f.write("- **Food (Feb–Mar only)**: meal events group within 15 s (derived §2C.2; production default still 1800 s — re-parameterise) + vision confirm; daily nutrients Σkcal/protein/carbs/fat; outside Feb–Mar → `has_nutrition=0` + NaNs (do not zero-fill as 'fasted').\n")
        f.write("- **Master table**: one row per participant×day (3×152=456 rows): `[participant, date, n_*_coverage, feat_*, target_*]`. "
                "Coverage columns (`steps_cov_min`, `hr_cov_min`, `has_wellness`, `has_nutrition`) gate every model — see §3.5 masking.\n\n")
        f.write("## 3.4 Feature catalogue (v1, daily grain)\n\n")
        f.write("**Activity/load**: total_steps, peak_1min_steps, total_distance_m, total_kcal, exercise_min, n_sessions, activity mix, "
                "Edwards-TRIMP from zones, sRPE load, 7-day rolling load, monotony (7 d), strain, ACWR (7:28 d, p01 only stable).\n")
        f.write("**Cardiac**: RHR_7d_median + residual, HR mean/sd/peak, zone min (4) + % , time ≥85% max, HR recovery proxy (post-exercise 1-min drop where resolvable).\n")
        f.write("**Sleep**: asleep_min, time_in_bed, efficiency, deep/light/rem/wake min + %, WASO, sleep_onset/offset hour, midsleep, "
                "social jetlag (weekend−weekday midsleep), overall/composition/revitalization/duration scores, deep_min, restlessness, classic_flag.\n")
        f.write("**Subjective**: fatigue/mood/readiness/sleep_h/sleep_q/soreness/stress (raw + within-person z), soreness_any + n_zones, "
                "submission_hour + delayed_flag, reporting lag_days, weight_7d_median + residual, fluids, alcohol_bin + weekend_bin.\n")
        f.write("**Nutrition (Feb–Mar)**: n_meals_logged, n_photos, n_photo_meals, kcal/protein/carbs/fat, eating_window_h, last-meal→sleep latency.\n")
        f.write("**Targets** (pick one per experiment): next-day readiness; next-night sleep efficiency/deep%; injury-event-day (rare-event); "
                "sRPE load (regression, p01); weight residual drift.\n\n")
        f.write("## 3.5 Modelling specification\n\n")
        f.write("### A. Descriptive / unsupervised (run first)\n")
        f.write("- Mixed-effects baselines: `y ~ 1 + (1|participant)` for every candidate target to quantify ICC; proceed only if within-person variance justifies personalisation.\n")
        f.write("- Changepoint/anomaly scan on RHR + load + sleep efficiency (PELT/CUSUM per participant) — p05 recurrent foot injury is the validation case.\n\n")
        f.write("### B. Supervised (daily-grain, participant-aware)\n")
        f.write("- **Validation**: leave-one-participant-out (LOPO) outer + time-series split inner (no shuffling); report per-participant + pooled metrics. "
                "With n=3 participants, LOPO is the only honest generalisation estimate.\n")
        f.write("- **Models**: (i) elastic-net / Ridge on within-person z-features (interpretable baseline); "
                "(ii) gradient boosting (LightGBM) with `participant` categorical + missingness indicators; "
                "(iii) hierarchical Bayesian (partial pooling) if inference on small-n effects is needed. "
                "No deep sequence models as primary (456 rows insufficient); minute-level CNN/LSTM only as feature extractors pre-trained per signal.\n")
        f.write("- **Missingness handling**: forward-fill ≤2 d for slow signals (RHR, weight median) with `was_imputed` flag; "
                "no fill for zones/sRPE/nutrition — use indicator + model-native NaN (LightGBM) or median+indicator (linear). "
                "Mask Feb–Mar-only nutrition models to Feb–Mar (n≈3×55 observed food-days) or use two-stage (base model all-days + nutrition uplift on Feb–Mar).\n")
        f.write("- **Imbalance (injury)**: do NOT train a balanced classifier. Use (a) survival/time-to-event (Cox PH with time-varying load/sleep covariates), "
                "or (b) unsupervised anomaly score → precision@k on event-days. Report PR-AUC + lead-time (days of early warning), not accuracy. "
                "Collapse p05 recurrent episodes into one episode with duration to avoid label leakage.\n")
        f.write("- **Metrics**: readiness/sleep → MAE + R² vs participant-mean baseline; load → MAPE; injury → PR-AUC, recall@fixed false-alarm rate, median lead-time.\n")
        f.write("- **Leakage guards**: all rolling features strictly causal (ending D−1 for predicting D); standardise using train-fold statistics only; "
                "group folds by participant; submission-lag features allowed only if available at prediction time.\n\n")
        f.write("### C. Nutrition-vision sub-pipeline\n")
        f.write("- Stage 1 `is_photo_food` (precision-oriented; quarantine NOs for audit, do not delete). "
                "Stage 2 time-preselect (15 s derived, §2C.2) → Stage 3 `is_it_same_meal` confirm → Stage 4 macro estimate per meal. "
                "Sensitivity runs at the 120 s valley-exit and legacy 1800 s. "
                "Report photo→meal precision/recall on a 50-meal hand-labelled sample before trusting kcal totals.\n\n")
        f.write("## 3.6 Risks & stop-rules\n\n")
        f.write("- p03/p05 sRPE sparsity → load models will be p01-only unless Fitbit-TRIMP substitution validates (corr(sRPE, TRIMP) on p01 overlapping days ≥0.6 required).\n")
        f.write("- 456 rows / ~40 features → regularise aggressively; pre-register feature list; report shrinkage.\n")
        f.write("- p01 abstinence (alcohol variance 0) + zero major injuries → drop those predictors/targets rather than modelling constants.\n")
        f.write("- Food window Feb–Mar only → nutrition effects are short-horizon; do not extrapolate to Nov/Dec/Jan.\n")
        f.write("- DST duplicate + RHR sentinel + classic-type pitfalls above must have unit tests (see `unit_tests/`) before any modelling run.\n")

    # ---- index
    with open(OUT / "00_INDEX.md", "w") as f:
        f.write("# Analysis Index — Multimodal Athletic Monitoring Audit\n\n")
        f.write(f"_Generated {datetime.now():%Y-%m-%d %H:%M}._\n\n")
        f.write("| File | Contents |\n|---|---|\n")
        f.write("| `phase1_schema_audit.md` | Phase 1: inventory, Schema Integrity Matrix, Temporal Alignment & Horizon Table |\n")
        f.write("| `phase2a_fitbit.md` | Phase 2A: minute missingness, non-wear, daily distributions, HR/RHR/zones, sleep architecture |\n")
        f.write("| `phase2b_subjective.md` | Phase 2B: adherence/cadence, Likert & ceiling effects, intra/inter variance, sRPE monotony/strain, weight, alcohol |\n")
        f.write("| `phase2c_food_injury.md` | Phase 2C: EXIF/format audit, data-derived 15 s meal threshold + vision validation, injury epidemiology + 1,000 h incidence + class imbalance |\n")
        f.write("| `phase3_preprocessing_modeling.md` | Phase 3: cleaning checklist, day-grain alignment, feature catalogue, model spec, risks |\n")
        f.write("| `tables/*.csv` | All machine-readable audit tables (prefix `phase1_*`, `phase2a_*`, `phase2b_*`, `phase2c_*`) |\n")
        f.write("| `audit_full.py` | Reproducible generator for this whole folder (run `.venv/bin/python analysis/audit_full.py`) |\n")
        f.write("| `findings.md` | Pre-existing basic report (kept for provenance; superseded by phase files above) |\n")
        f.write("| `analyze_all.py` | Pre-existing basic generator (kept; not used by this audit) |\n")

if __name__ == "__main__":
    main()
