# Phase 1 — Database Architecture & Exhaustive Schema Audit

_Generated 2026-09-17 10:50 from `data/` (p01/p03/p05). Machine-readable tables in `analysis/tables/phase1_*.csv`._

## 1.1 File & directory inventory

Expected layout per participant: `fitbit/` (8 JSON + `sleep_score.csv`), `pmsys/` (3 CSV), `googledocs/reporting.csv`, `food-images/` (loose JPG/JPEG/PNG, mission text mentions `food-images.zip` but on disk images are already unzipped per-participant folders).

| participant | path | exists | n_rows | size_bytes | notes |
|---|---|---|---|---|---|
| p01 | fitbit/calories.json | True | 218880 | 11813913 | — |
| p01 | fitbit/distance.json | True | 218836 | 11292968 | — |
| p01 | fitbit/steps.json | True | 218836 | 11203988 | — |
| p01 | fitbit/heart_rate.json | True | 1573165 | 119634842 | — |
| p01 | fitbit/resting_heart_rate.json | True | 152 | 18890 | — |
| p01 | fitbit/time_in_heart_rate_zones.json | True | 152 | 27170 | — |
| p01 | fitbit/sleep.json | True | 155 | 544294 | — |
| p01 | fitbit/exercise.json | True | 190 | 181733 | — |
| p01 | fitbit/sleep_score.csv | True | 150 | 10939 | timestamp;sleep_log_entry_id;overall_score;composition_score;revitalization_score;duration_score;deep_sleep_in_minutes;resting_heart_rate;restlessness |
| p01 | pmsys/wellness.csv | True | 138 | 7244 | effective_time_frame;fatigue;mood;readiness;sleep_duration_h;sleep_quality;soreness;soreness_area;stress |
| p01 | pmsys/srpe.csv | True | 34 | 1993 | end_date_time;activity_names;perceived_exertion;duration_min |
| p01 | pmsys/injury.csv | True | 24 | 748 | effective_time_frame;injuries |
| p01 | googledocs/reporting.csv | True | 109 | 7212 | date;timestamp;meals;weight;glasses_of_fluid;alcohol_consumed |
| p01 | food-images/ | True | 321 | 741595990 | Counter({'.jpeg': 320, '.png': 1}) |
| p03 | fitbit/calories.json | True | 218880 | 11817358 | — |
| p03 | fitbit/distance.json | True | 53042 | 2750053 | — |
| p03 | fitbit/steps.json | True | 53042 | 2720044 | — |
| p03 | fitbit/heart_rate.json | False | 0 | 0 | MISSING |
| p03 | fitbit/resting_heart_rate.json | True | 152 | 17165 | — |
| p03 | fitbit/time_in_heart_rate_zones.json | True | 117 | 20730 | — |
| p03 | fitbit/sleep.json | True | 84 | 317602 | — |
| p03 | fitbit/exercise.json | True | 57 | 52898 | — |
| p03 | fitbit/sleep_score.csv | True | 74 | 5440 | timestamp;sleep_log_entry_id;overall_score;composition_score;revitalization_score;duration_score;deep_sleep_in_minutes;resting_heart_rate;restlessness |
| p03 | pmsys/wellness.csv | True | 82 | 3692 | effective_time_frame;fatigue;mood;readiness;sleep_duration_h;sleep_quality;soreness;soreness_area;stress |
| p03 | pmsys/srpe.csv | True | 2 | 180 | end_date_time;activity_names;perceived_exertion;duration_min |
| p03 | pmsys/injury.csv | True | 11 | 350 | effective_time_frame;injuries |
| p03 | googledocs/reporting.csv | True | 117 | 7351 | date;timestamp;meals;weight;glasses_of_fluid;alcohol_consumed |
| p03 | food-images/ | True | 136 | 160960492 | Counter({'.jpg': 136}) |
| p05 | fitbit/calories.json | True | 218880 | 11811776 | — |
| p05 | fitbit/distance.json | True | 111231 | 5793154 | — |
| p05 | fitbit/steps.json | True | 111231 | 5711633 | — |
| p05 | fitbit/heart_rate.json | True | 1370967 | 104292322 | — |
| p05 | fitbit/resting_heart_rate.json | True | 95 | 11502 | — |
| p05 | fitbit/time_in_heart_rate_zones.json | True | 145 | 25914 | — |
| p05 | fitbit/sleep.json | True | 133 | 441897 | — |
| p05 | fitbit/exercise.json | True | 145 | 134987 | — |
| p05 | fitbit/sleep_score.csv | True | 117 | 8587 | timestamp;sleep_log_entry_id;overall_score;composition_score;revitalization_score;duration_score;deep_sleep_in_minutes;resting_heart_rate;restlessness |
| p05 | pmsys/wellness.csv | True | 137 | 6025 | effective_time_frame;fatigue;mood;readiness;sleep_duration_h;sleep_quality;soreness;soreness_area;stress |
| p05 | pmsys/srpe.csv | True | 9 | 614 | end_date_time;activity_names;perceived_exertion;duration_min |
| p05 | pmsys/injury.csv | True | 10 | 521 | effective_time_frame;injuries |
| p05 | googledocs/reporting.csv | True | 126 | 8801 | date;timestamp;meals;weight;glasses_of_fluid;alcohol_consumed |
| p05 | food-images/ | True | 186 | 393061888 | Counter({'.jpg': 186}) |

**Key completeness findings**

- `heart_rate.json` **absent for p03 only** (p01 1,573,165 rows; p05 1,370,967 rows). All downstream HR-dependent features are structurally missing for p03.
- All other JSON/CSV files present for all 3 participants. No `food-images.zip`; counts are p01=321, p03=136, p05=186 loose images.
- `participant-overview.xlsx` at root covers **16 participants (p01–p16)** while sensor-grade data exists only for p01/p03/p05 (subset design).

## 1.2 Schema Integrity Matrix (condensed)

Full matrix: `tables/phase1_schema_matrix.csv` (one row per dataset×participant×field + `__RECORD__/__LAST__/__DRIFT__` probes). Condensed contract below; **PK = primary key / join key**, TS = timestamp.

| Dataset | Grain / PK | Timestamp col + observed format | Fields & types | Drift / caveats |
|---|---|---|---|---|
| `fitbit/calories.json` | 1 min; PK=`dateTime` | `dateTime`: `YYYY-MM-DD HH:MM:SS` (e.g. `2019-11-01 00:00:00`) | `value`: numeric string (kcal/min, e.g. `1.39`) | p01/p03/p05 identical; full 218,880 rows each |
| `fitbit/distance.json` | 1 min (sparse); PK=`dateTime` | same minute format | `value`: numeric string (cm/min per aggregator; e.g. `0`, `1090`) | **p01 218,836 rows with 226 DST-duplicate `2020-03-29` zero rows**; p03 53,042 rows / 122 days; p05 111,231 rows / 144 days |
| `fitbit/steps.json` | 1 min (sparse); PK=`dateTime` | same minute format | `value`: numeric string (steps/min) | identical row counts to distance per participant (co-emitted); same p01 DST duplicates |
| `fitbit/heart_rate.json` | ~5 s; PK=`dateTime` (sec precision) | `dateTime`: `YYYY-MM-DD HH:MM:SS` (e.g. `2019-11-01 00:00:05`) | `value.bpm`: int 30–200; `value.confidence`: int {0,1,2,3} | **MISSING for p03**; p01 median Δt=5 s mean 8.3 s; p05 median 5 s mean 9.5 s; long gaps (p01 max 10.5 h, p05 max 7.6 d) |
| `fitbit/resting_heart_rate.json` | 1 day; PK=`dateTime` | `dateTime`: midnight `YYYY-MM-DD 00:00:00` | `value.date`: `MM/DD/YY` or null; `value.value`: float bpm; `value.error`: float | **Sentinel `value=0.0 + date=null + error=0.0`** = missing: p03 51/152, p05 9/95; p05 coverage starts 2019-12-28 (95 rows vs 152) |
| `fitbit/time_in_heart_rate_zones.json` | 1 day; PK=`dateTime` | midnight daily | `value.valuesInZones`: {BELOW_DEFAULT_ZONE_1, IN_DEFAULT_ZONE_1 (fat-burn 50–69%), IN_DEFAULT_ZONE_2 (cardio 70–84%), IN_DEFAULT_ZONE_3 (peak 85–100%)} float min | p01 152 rows; **p03 117 rows (35 missing days)**; p05 145 rows; zone HR bounds depend on `220−age` / measured maxHR (see overview) |
| `fitbit/sleep.json` | 1 night; PK=`logId` (+`dateOfSleep`) | `startTime`: `YYYY-MM-DD HH:MM:SS`; `endTime`: ISO `YYYY-MM-DDT HH:MM:SS.000`; `dateOfSleep`: `YYYY-MM-DD` (morning-attribution) | `minutesAsleep/minutesAwake/timeInBed/efficiency/type∈{stages,classic}/levels.summary/levels.data[]/mainSleep` | **Type drift**: p01 155/155 stages; p03 78 stages + 6 classic; p05 122 stages + 11 classic. `classic` has only {asleep,restless,awake} — no deep/light/REM split. `mainSleep=False` naps: p03 3, p05 10 |
| `fitbit/exercise.json` | 1 bout; PK=`logId` | `startTime`: `YYYY-MM-DD HH:MM:SS` | `activityName/activityTypeId/activityLevel[]/averageHeartRate/calories/duration+activeDuration (ms)/steps/logType∈{auto_detected,tracker}/heartRateZones[]/elevationGain/hasGps` | p01 190 (Walk 150/Sport 15/Run 14/Treadmill 11); p03 57 (Walk 54); p05 145 (Walk 80/Bike 54+2/Run 4/…) — sparse, auto-detected heavy |
| `fitbit/sleep_score.csv` | 1 night; PK=`sleep_log_entry_id` | `timestamp`: ISO `YYYY-MM-DDTHH:MM:SSZ` | `overall_score 0–100/composition_score/revitalization_score/duration_score/deep_sleep_in_minutes/resting_heart_rate/restlessness` all numeric | p01 150, p03 74, p05 117 rows; join to sleep.json on logId↔sleep_log_entry_id |
| `pmsys/wellness.csv` | 1 morning row; PK=`effective_time_frame` | ISO `YYYY-MM-DDTHH:MM:SS.sssZ` | `fatigue/mood/readiness/sleep_duration_h/sleep_quality/soreness/stress` ints; `soreness_area` JSON-list of anatomical IDs | 9 cols stable; scales observed 0–4/0–8 (see Phase 2B); soreness_area `[]` dominant |
| `pmsys/srpe.csv` | 1 session; PK=`end_date_time` | ISO with ms + `Z` | `activity_names` JSON-list; `perceived_exertion` int 1–10; `duration_min` int | p01 34, p03 2, p05 9 rows — extremely sparse for p03/p05 |
| `pmsys/injury.csv` | 1 report; PK=`effective_time_frame` | ISO with ms + `Z` | `injuries`: Python-dict string `{location: minor\|major}` or `{}` | p01 24 reports/1 event; p03 11/0 events; p05 10/10 events (recurrent left_foot) |
| `googledocs/reporting.csv` | 1 day; PK=`date` | `date`: `DD/MM/YYYY`; `timestamp`: `DD/MM/YYYY HH:MM:SS` (**submission lags log date by days–month**, e.g. log 06/11 submitted 06/12) | `meals` comma-set {Breakfast,Lunch,Dinner,Evening}; `weight` float; `glasses_of_fluid` int; `alcohol_consumed` {Yes,No} | 6 cols stable; weight missing 27/109 p01, 24/117 p03, 25/126 p05 |
| `food-images/` | 1 photo; PK=EXIF DateTime + filename | EXIF `DateTime`/`DateTimeOriginal` `YYYY:MM:DD HH:MM:SS` | JPEG (+1 PNG p01); RGB; EXIF GPS/Orientation | p01 GPS 99.4% vs p03/p05 0% (device/settings split); strict `DateTime`-tag gaps: p01 2/321 (`IMG_8958.jpeg`, `IMG_9111.png` — both have DateTimeOriginal; dropped by current `food_reader`), p03/p05 0 |
| `participant-overview.xlsx` | 1 row/participant; PK=`Participant ID` | `First 5km Run Date` mixed (datetimes + literal `november`/`injured`) | `Age/Height/Gender/A-or-B-person/MaxHR/5km Date+Min+Sec/Stride walk+run` | 16 rows p01–p16; MaxHR missing p07/p12/p15; strides missing p03/p12; p14 run stride 11.3 cm implausible; p16 5km date 2020-11-16 out of window |

**Ingestion implications (also see Phase 3):** strip p01 DST-duplicate timestamps (keep first); treat RHR `0.0` as NaN, not 0 bpm; branch sleep logic on `type` (classic ≠ stages); never inner-join on HR for p03; parse `reporting.csv:date` dayfirst and keep `timestamp` as submission-time feature (lag = recall bias proxy); patch `food_reader` EXIF key to `DateTime OR DateTimeOriginal` (2 p01 files currently invisible).

## 1.3 Temporal Alignment & Horizon Table

Reference horizon = Fitbit export window **2019-11-01 → 2020-03-31 (152 days)**. Table: `tables/phase1_temporal_horizon.csv`.

| participant | calories_start | calories_end | steps_n | steps_days | distance_n | hr_n | hr_start | hr_end | rhr_n | rhr_start | rhr_end | zones_n | zones_start | zones_end | sleep_n | sleep_start | sleep_end | exercise_n | exercise_start | exercise_end | sleep_score_n | sleep_score_start | sleep_score_end | wellness_n | wellness_start | wellness_end | wellness_days | srpe_n | srpe_start | srpe_end | injury_reports_n | injury_start | injury_end | reporting_n | reporting_start | reporting_end | reporting_days | food_n | food_start | food_end | food_days | fitbit_days |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p01 | 2019-11-01 00:00:00 | 2020-03-31 23:59:00 | 218836 | 152 | 218836 | 1573165 | 2019-11-01 00:00:05 | 2020-03-31 23:59:58 | 152 | 2019-11-01 00:00:00 | 2020-03-31 00:00:00 | 152 | 2019-11-01 00:00:00 | 2020-03-31 00:00:00 | 155 | 2019-11-02 00:00:00 | 2020-03-31 00:00:00 | 190 | 2019-11-01 14:56:32 | 2020-03-31 16:51:36 | 150 | 2019-11-01 06:29:30+00:00 | 2020-03-30 07:20:00+00:00 | 138 | 2019-11-01 08:31:40.751000+00:00 | 2020-03-30 07:24:02.816000+00:00 | 138 | 34 | 2019-11-05 22:51:54.710000+00:00 | 2020-03-14 08:45:18.557000+00:00 | 24 | 2019-11-07 06:39:48.428000+00:00 | 2020-03-24 17:03:33.413000+00:00 | 109 | 2019-11-06 00:00:00 | 2020-03-30 00:00:00 | 100 | 321 | 2020-02-01 10:03:41 | 2020-03-31 23:19:04 | 60 | 152 |
| p03 | 2019-11-01 00:00:00 | 2020-03-31 23:59:00 | 53042 | 122 | 53042 | 0 | — | — | 152 | 2019-11-01 00:00:00 | 2020-03-31 00:00:00 | 117 | 2019-11-01 00:00:00 | 2020-03-31 00:00:00 | 84 | 2019-11-01 00:00:00 | 2020-03-31 00:00:00 | 57 | 2019-11-01 11:45:06 | 2020-03-09 15:08:15 | 74 | 2019-11-02 07:40:00+00:00 | 2020-03-30 07:52:30+00:00 | 82 | 2019-11-01 08:03:15.527000+00:00 | 2020-03-30 23:06:29.537000+00:00 | 78 | 2 | 2019-12-24 10:10:35+00:00 | 2019-12-30 14:06:48.392000+00:00 | 11 | 2019-11-19 08:06:01.393000+00:00 | 2020-03-24 18:50:06.613000+00:00 | 117 | 2019-11-06 00:00:00 | 2020-03-27 00:00:00 | 113 | 136 | 2020-02-01 10:36:10 | 2020-03-31 14:47:33 | 51 | 152 |
| p05 | 2019-11-01 00:00:00 | 2020-03-31 23:59:00 | 111231 | 144 | 111231 | 1370967 | 2019-11-01 00:00:02 | 2020-03-31 05:24:02 | 95 | 2019-12-28 00:00:00 | 2020-03-31 00:00:00 | 145 | 2019-11-01 00:00:00 | 2020-03-31 00:00:00 | 133 | 2019-11-02 00:00:00 | 2020-03-31 00:00:00 | 145 | 2019-11-01 18:56:06 | 2020-03-29 13:26:24 | 117 | 2019-11-01 06:48:00+00:00 | 2020-03-30 06:29:00+00:00 | 137 | 2019-11-01 06:30:18.128000+00:00 | 2020-03-30 04:48:34.872000+00:00 | 134 | 9 | 2019-11-07 15:00:23+00:00 | 2020-02-13 06:00:29+00:00 | 10 | 2019-11-01 06:30:35.565000+00:00 | 2020-03-17 19:47:51.329000+00:00 | 126 | 2019-11-15 00:00:00 | 2020-03-30 00:00:00 | 117 | 186 | 2020-02-01 06:55:04 | 2020-03-29 17:07:31 | 47 | 152 |

**Overlap reading**

- **Fitbit backbone is complete** for calories (152/152 days, all participants) but steps/distance are thinned for p03 (122 d) and p05 (144 d, truncated 2020-03-31 05:27).
- **RHR**: p01 full 152 d; p03 152 rows but only 101 valid (51 sentinel zeros); p05 starts 2019-12-28 (95 rows, 86 valid) — no usable RHR baseline for p05 in Nov–Dec 2019.
- **HR zones**: p01 152 d; p05 145 d; p03 117 d (23% missing) — zone-based load features have participant-specific missingness.
- **Sleep**: p01 155 logs ≈ full coverage; p05 133; p03 84 (≈55%) with 6 classic-type low-resolution nights.
- **Wellness**: p01 138 rows/138 d (91%), p05 137 rows/134 d (88%), p03 82 rows/78 d (51%) — p03 subjective state is half-missing.
- **sRPE**: p01 34 sessions vs p03 2 vs p05 9 — training-load modelling is p01-driven; p03/p05 loads must fall back to Fitbit exercise bouts.
- **Reporting**: 109/117/126 logged rows (100/113/117 distinct log days; 66–77% of horizon) but submission timestamps lag by up to a month (batch logging).
- **Food images**: EXIF datetimes span **February–March** (p01 2020-02-01→03-31, 60 d; p03 2020-02-01→03-31, 51 d; p05 2020-02-01→03-29, 47 d) — a 2-month nutrition sub-study (Feb–Mar) inside the 5-month monitoring window. Overlap with other modalities is Feb–Mar only.
- **Injury reports**: sporadic weekly cadence Nov→Mar; events: p01 1, p03 0, p05 10 (recurrent).
