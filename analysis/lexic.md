# Lexicon — variable definitions for the multimodal athletic monitoring analysis

One section per analysis file, in the same order as `analysis/00_INDEX.md`.
Words first, formula when the variable is computed. Common statistical
summaries shared by all files are defined once in §0.

Conventions: `d` = calendar day, `pXX` = participant, SD = standard deviation,
NaN = missing (never silently zero-filled, see Phase 3).

---

## 0. Shared statistical vocabulary (all Phase 2 tables)

| Variable | Definition |
|---|---|
| `n` | Number of non-missing observations used in the summary. |
| `mean` | Arithmetic mean, $\bar{x} = \frac{1}{n}\sum_{i=1}^{n} x_i$. |
| `median` | 50th percentile: middle value of the sorted sample (average of the two middle values if $n$ is even). Robust to outliers. |
| `sd` | Sample standard deviation, $s = \sqrt{\frac{1}{n-1}\sum (x_i-\bar{x})^2}$. Dispersion around the mean. |
| `q25`, `q75` | 25th / 75th percentiles (first / third quartiles). |
| `iqr` | Inter-quartile range, $\mathrm{IQR} = q_{75} - q_{25}$. Spread of the middle 50% of the data. |
| `skew` | Fisher skewness (mean-based, bias-adjusted). $\approx 0$ symmetric; $>0$ right tail (a few very active days); $<0$ left tail. |
| `p1`, `p99` | 1st / 99th percentiles. Empirical extremes robust to single-point artefacts (used instead of raw min/max for heavy-tailed sensor data). |
| `min`, `max` | Observed minimum / maximum. |
| `mode` | Most frequent value (for Likert scales: the dominant rating). |
| `mode_share` | Fraction of rows equal to the mode, $\max_k P(X=k)$. Values >0.9 flag "constant responder" behaviour. |
| `n_unique` | Number of distinct values taken ( scale usage width, e.g. 2 of 5 Likert levels). |
| `value_counts` | Per-level relative frequencies, e.g. `1:1%;2:41%;3:57%;4:1%`. |
| `cv_pct` | Coefficient of variation in percent, $100 \times \mathrm{sd}/\mathrm{mean}$. Scale-free stability index (weight stability). |
| `range` | $\max - \min$ over the observed window. |

---

## 1. `phase1_schema_audit.md` — database architecture & schema audit

### 1.1 Raw source variables (by dataset)

**`participant-overview.xlsx`** (root, 16 rows, PK = `Participant ID`):
| Variable | Definition |
|---|---|
| `Participant ID` | Study identifier (`p01`…`p16`). Only `p01/p03/p05` have sensor-grade data. |
| `Age` | Age in years. Feeds age-predicted max heart rate, $HR_{max} \approx 220 - \mathrm{age}$. |
| `Height` | Standing height in cm. |
| `Gender` | `male` / `female` (one row carries a trailing non-breaking space, stripped on ingest). |
| `A or B person` | Chronotype proxy: morning (`A`) vs evening (`B`) preference. |
| `Max heart rate` | Measured max HR in bpm (13/16 observed). Overrides $220-\mathrm{age}$ for zone cut-points when present. |
| `First 5km Run Date/Minutes/Seconds` | Date and duration of the first timed 5 km run. Mixed formats (`datetime`, literal `november`, `injured` → NaT). |
| `Stride walk` / `Stride run` | Fitbit stride length in cm. `11.3` cm (p14 run) is implausible → NaN. |

**`fitbit/calories.json`** (1 row/minute, PK = `dateTime`): `dateTime` (`YYYY-MM-DD HH:MM:SS`), `value` (kcal expended that minute, numeric string). Gap-filled export — cannot signal wear.

**`fitbit/distance.json`**, **`fitbit/steps.json`** (1 row/minute when synced, PK = `dateTime`): `dateTime` as above; `value` distance in cm (aggregator treats raw units as cm) resp. step count that minute (numeric strings). Sparse for p03/p05; p01 carries 226 DST-duplicate zero rows on 2020-03-29.

**`fitbit/heart_rate.json`** (~1 row/5 s, PK = `dateTime` with seconds): `dateTime`; `value.bpm` (beats per minute, int 30–200); `value.confidence` (Fitbit signal quality 0–3; 0 = unreliable, dropped). Absent for p03.

**`fitbit/resting_heart_rate.json`** (1 row/day, PK = `dateTime` at midnight): `value.date` (`MM/DD/YY` or null when missing); `value.value` (RHR in bpm, float); `value.error` (algorithm uncertainty). Sentinel `value = 0.0` + null date + `error = 0.0` means *missing*, not 0 bpm.

**`fitbit/time_in_heart_rate_zones.json`** (1 row/day, PK = `dateTime`): `value.valuesInZones` — minutes per day in `BELOW_DEFAULT_ZONE_1` (<50% max), `IN_DEFAULT_ZONE_1` (fat-burn, 50–69% $HR_{max}$), `IN_DEFAULT_ZONE_2` (cardio, 70–84%), `IN_DEFAULT_ZONE_3` (peak, 85–100%). Bounds are participant-relative via $HR_{max}$.

**`fitbit/sleep.json`** (1 row/night, PK = `logId`): `dateOfSleep` (morning-attribution date: the night belongs to the day it ends on); `startTime` / `endTime` (sleep onset/offset); `minutesAsleep`, `minutesAwake`, `timeInBed`, `efficiency` (see §3); `type` ∈ {`stages` (full deep/light/REM/wake split), `classic` (only asleep/restless/awake — no stage split)}; `levels.summary` (minutes per stage); `levels.data[]` (event-level hypnogram); `mainSleep` (false = nap, excluded from nightly features).

**`fitbit/exercise.json`** (1 row/bout, PK = `logId`): `activityName` (Walk, Run, Sport, Outdoor Bike, …); `activityTypeId`; `activityLevel[]` (minutes sedentary/lightly/fairly/very active); `averageHeartRate` (bpm); `calories`; `duration` / `activeDuration` (ms; active duration used, → minutes by /60000); `steps`; `logType` ∈ {`auto_detected`, `tracker`}; `heartRateZones[]`; `startTime`; `elevationGain`; `hasGps`.

**`fitbit/sleep_score.csv`** (1 row/night, PK = `sleep_log_entry_id` = `sleep.json:logId`): `timestamp` (ISO UTC); `overall_score` (0–100); `composition_score`, `revitalization_score`, `duration_score` (sub-scores); `deep_sleep_in_minutes`; `resting_heart_rate` (bpm during sleep); `restlessness` (fraction of restless sleep, ~0.03–0.20).

**`pmsys/wellness.csv`** (1 row/submission, PK = `effective_time_frame`, ISO UTC): `fatigue`, `mood`, `sleep_quality`, `soreness`, `stress` (1–5 Likert; observed 0 = off-instrument sentinel → NaN); `readiness` (0–10 scale; p05 0-values are sentinels); `sleep_duration_h` (self-reported hours); `soreness_area` (JSON list of anatomical IDs, `[]` = no pain).

**`pmsys/srpe.csv`** (1 row/session, PK = `end_date_time`, ISO UTC): `activity_names` (JSON list, e.g. `['individual','running']`); `perceived_exertion` (RPE 1–10); `duration_min` (minutes). Load is derived (§4).

**`pmsys/injury.csv`** (1 row/report, PK = `effective_time_frame`): `injuries` (Python-dict string `{location: severity}`, `{}` = no injury; severity ∈ {minor, major} — only minor observed).

**`googledocs/reporting.csv`** (1 row/log-day, PK = `date` `DD/MM/YYYY` dayfirst): `timestamp` (submission time — lags `date` by days/weeks); `meals` (comma set among Breakfast/Lunch/Dinner/Evening); `weight` (kg, ~20–25% missing); `glasses_of_fluid` (count/day); `alcohol_consumed` (`Yes`/`No` binary — no unit volumes). `lag_days = timestamp − date` measures recall delay.

**`food-images/`** (1 file/photo, PK = EXIF datetime + filename): native camera JPEG (+1 PNG), RGB, EXIF `DateTime` (tag 0x0132, production selector key) / `DateTimeOriginal` (`YYYY:MM:DD HH:MM:SS`), `GPSInfo` (p01 only), `Orientation` (auto-rotate).

### 1.2 Audit-table variables

**`tables/phase1_file_inventory.csv`**: `participant`; `path` (repo-relative file); `exists`; `n_rows` (records/rows/images); `size_bytes`; `notes` (CSV columns or missing-file flag).

**`tables/phase1_schema_matrix.csv`** (full machine-readable contract): `dataset`; `participant`; `field` (column/key, or `__RECORD__`/`__LAST__` first/last-record probes, `__EXPECTED_KEYS__`, `__DRIFT_*` cross-participant drift notes, `__TIMESTAMP_FORMAT__`) ; `dtype`; `numeric_share` (fraction parseable as numeric); `n_missing`; `sample` (example value); `is_timestamp`; `role` (PK/format/drift/expected marker).

**`tables/phase1_temporal_horizon.csv`**: per participant, per modality `*_start` / `*_end` (coverage bounds), `*_n` (record counts: `steps_n`, `distance_n`, `hr_n`, `rhr_n`, `zones_n`, `sleep_n`, `exercise_n`, `sleep_score_n`, `wellness_n`, `srpe_n`, `injury_reports_n`, `reporting_n`, `food_n`), day counts (`steps_days`, `wellness_days`, `reporting_days`, `food_days`, `fitbit_days` = days with any Fitbit minute data). Reference horizon = 2019-11-01→2020-03-31, 152 days, 218880 minute slots ($152 \times 1440$).

---

## 2. `phase2a_fitbit.md` — high-frequency wearable data

### 2.1 Sampling regularity (`tables/phase2a_minute_missingness.csv`)

| Variable | Definition |
|---|---|
| `file` | Source JSON (`calories/distance/steps.json`). |
| `n_records` | Raw rows in the export. |
| `n_unique_ts` | Distinct `dateTime` values (deduplicated timeline). |
| `n_duplicates` | `n_records − n_unique_ts` (p01: 226 DST duplicates). |
| `expected_slots` | 218880 (full minute grid of the horizon). |
| `missing_slots` | `expected_slots − n_unique_ts`. |
| `missing_pct` | $100 \times \mathrm{missing\_slots}/\mathrm{expected\_slots}$. |
| `days_present` | Days with ≥1 row. |
| `days_full_1440` / `days_partial` | Days with exactly 1440 rows vs fewer (p01: 82/69; p03/p05: 0 full). |
| `min_daily`, `max_daily`, `mean_daily` | Min/max/mean rows per present day. |

HR sampling: median/mean/p90 of inter-sample gap $\Delta t$ ($5$ s median; means 8.3 s p01, 9.5 s p05); `confidence` mix (share of 0/1/2/3).

### 2.2 Non-wear (`tables/phase2a_nonwear_summary.csv`, `phase2a_nonwear_per_day.csv`)

Non-wear minute = zero steps **and** (no HR sample that minute **or** HR flatlined, i.e. per-minute $\mathrm{sd}=0$ with ≥2 samples). A non-wear run = ≥60 consecutive such minutes (missing minute-slots count as zero steps; p03 has no HR file → steps-only upper bound).

| Variable | Definition |
|---|---|
| `definition` | Rule applied (HR-gated, or steps-only for p03). |
| `n_long_runs` | Number of ≥60-min runs. |
| `total_nonwear_min` / `total_nonwear_hours` | Sum over runs (hours = minutes/60). |
| `mean_nonwear_min_per_day` / `median_nonwear_min_per_day` / `max_nonwear_min_one_day` | Per-day distribution of non-wear minutes. |
| `days_with_any_nonwear` | Days containing ≥1 long run. |
| `steps_missing_minutes` | Minute-slots with no steps row at all. |
| Per-day: `date`, `nonwear_min`, `nonwear_hours` | Daily non-wear load. |

### 2.3 Daily distributions (`tables/phase2a_daily_distributions.csv`, `phase2a_daily_values.csv`)

Metrics (one row per participant×metric; stats per §0): `daily_steps` ($\sum$ steps), `daily_distance` ($\sum$ distance, raw units treated as cm), `daily_calories` ($\sum$ kcal), `daily_exercise_active_min` ($\sum \mathrm{activeDuration}/60000$ over bouts starting that day; 0 = no bout). `phase2a_daily_values.csv` holds the day-indexed wide series (`p01_steps`, …).

### 2.4 Heart-rate distributions (`tables/phase2a_hr_zones.csv`, `phase2a_hr_confidence_{p01,p05}.csv`)

Modalities (`modality`): `RHR_valid_bpm` (sentinel zeros excluded); `HR_continuous_bpm` (all ~5 s samples); `HR_daily_peak_bpm` (per-day max); `zone_*_min_per_day` (daily minutes per HR zone).

| Variable | Definition |
|---|---|
| `n_valid` | Usable observations (valid RHR days / HR samples / days). |
| `n_sentinel_zero` | RHR rows with `value = 0.0` (missing-data sentinel). |
| `drift_2nd_minus_1st_half` | Baseline shift: mean(valid values, second half of window) − mean(first half), in bpm. |
| `rhr_mean … rhr_p99` | §0 stats under a fixed prefix (apply to whichever `modality` the row describes, despite the `rhr_` name). |
| `conf`, `n` (confidence tables) | Count of HR samples per `confidence` level 0–3. |

Zone physiology: with $HR_{max} = 220 - \mathrm{age}$ (or measured max), fat-burn = 50–69%, cardio = 70–84%, peak = 85–100% of max.

### 2.5 Sleep architecture (`tables/phase2a_sleep_distributions.csv`, `phase2a_sleep_nights_*.csv`, `phase2a_sleep_architecture_pct.csv`)

Night-level (`sleep_nights`): `logId`; `dateOfSleep`; `type`; `mainSleep`; `minutesAsleep`; `minutesAwake` (= WASO + latency wake); `timeInBed`; `efficiency` ($=100 \times \mathrm{minutesAsleep}/\mathrm{timeInBed}$, target ≥85%); `deep`, `light`, `rem`, `wake` (stage minutes; null for `classic` type).

Architecture shares (stages-type nights only): $\mathrm{deep\_pct} = 100 \times \mathrm{deep}/(\mathrm{deep}+\mathrm{light}+\mathrm{rem}+\mathrm{wake})$, analogously `light_pct`, `rem_pct`, `wake_pct`. Normative athletic bands: Deep 15–25%, REM 20–25%, Light ~50–60%, Wake <10–15%.

---

## 3. `phase2b_subjective.md` — PMSYS + Google Docs logs

### 3.1 Adherence & cadence (`tables/phase2b_wellness_response.csv`, `phase2b_wellness_hour.csv`)

| Variable | Definition |
|---|---|
| `n_rows` | Wellness submissions. |
| `n_days_with_log` | Distinct UTC dates with ≥1 submission. |
| `horizon_days` | 152. |
| `response_rate` | $n_{\mathrm{days\_with\_log}} / 152$. |
| `first` / `last` | Coverage bounds. |
| `median_hour`, `sd_hour` | Median/SD of submission hour (UTC). Morning compliance = low median (≈5–8h) + small SD. |
| `pct_before_09`, `pct_after_12` | % submissions before 09:00 (true mornings) resp. after 12:00 (recall-delayed; excluded from morning-readiness features). |
| Per-hour: `hour`, `n` | Submission counts per hour of day. |

`reporting.csv` lag: `lag_days = timestamp − date` (batch-logging delay; recall-bias proxy).

### 3.2 Likert distributions (`tables/phase2b_likert_distributions.csv`)

§0 stats + `mode`, `mode_share`, `n_unique`, `value_counts`, for metrics: `fatigue`, `mood`, `readiness`, `sleep_duration_h`, `sleep_quality`, `soreness`, `stress`. Floor/ceiling effect = mass piled at one scale end or unused levels (e.g. p03 readiness ∈ {3,…,6} only; p05 zeros = off-instrument sentinels).

### 3.3 Intra- vs inter-individual variance (`tables/phase2b_intra_vs_inter.csv`)

| Variable | Definition |
|---|---|
| `grand_mean` | Mean over all participants/rows. |
| `within_participant_mean_sd` | Mean of the three per-participant SDs (typical day-to-day wobble of one person). |
| `between_participant_sd_of_means` | SD of the three participant means (how far apart personal baselines sit). |
| `ratio_between_within` | Between/within. <0.5 → personal baselines dominate → standardise within participant ($z = (x-\mu_p)/\sigma_p$) before pooling. |

### 3.4 sRPE load (`tables/phase2b_srpe_summary.csv`, `phase2b_srpe_daily_load_*.csv`)

| Variable | Definition |
|---|---|
| `load` (daily series `d`, `load`) | Session load $\mathrm{sRPE} = \mathrm{RPE} \times \mathrm{duration\_min}$, summed per day (days without sessions = 0). |
| `n_sessions` | Logged training sessions. |
| `mean_RPE`, `mean_duration` | Mean perceived exertion (1–10) / session minutes. |
| `total_load` | $\sum$ daily loads over the horizon. |
| `mean_daily_load`, `sd_daily_load` | Mean/SD of the 152-day daily-load series (zero-inflated for p03/p05). |
| `monotony` | Foster monotony $= \mathrm{mean(daily\ load)} / \mathrm{SD(daily\ load)}$. High values (>2 weekly) flag unvarying, potentially overtraining load. Degenerate when sessions are near-absent. |
| `strain` | $= (\sum \mathrm{load}) \times \mathrm{monotony}$. |
| `n_spike_days` | Days with load $> \mathrm{mean} + 2\,\mathrm{SD}$ (acute spikes). |
| `max_daily_load` | Peak single-day load. |
| `activity_types` | Distinct `activity_names` observed. |

### 3.5 Weight (`tables/phase2b_weight.csv`)

| Variable | Definition |
|---|---|
| `n_weight_obs` / `n_missing_weight` | Observed vs missing weigh-ins. |
| `mean`, `sd`, `cv_pct`, `min`, `max`, `range` | §0 stats + $100\cdot\mathrm{sd}/\mathrm{mean}$ and max−min (all hyper-stable: CV <1%). |
| `mean_abs_day_to_day` | Mean $|w_t - w_{t-1}|$ over consecutive observations (scale noise + hydration vs true drift). |
| `max_abs_day_to_day` | Largest single jump. |
| `n_changes_gt2kg` | Jumps >2 kg (0 everywhere → no true mass-change events; model 7-day median + residual instead). |

### 3.6 Alcohol (`tables/phase2b_alcohol.csv`)

| Variable | Definition |
|---|---|
| `n_days` | Reporting-log days. |
| `n_alcohol_yes`, `pct_yes` | Days flagged Yes; $100 \times \mathrm{yes}/n_{\mathrm{days}}$. p01 = 0 (zero-variance predictor, dropped). No unit volumes logged → binary only, dose-response unidentifiable. |
| `pct_weekend_Fri_Sat_Sun` | Share of Yes-days falling Fri/Sat/Sun (post-match-weekend clustering test). |
| `by_weekday` | Yes-counts per weekday. |
| `glasses_mean` | Mean daily fluid glasses (hydration context, not alcohol volume). |

---

## 4. `phase2c_food_injury.md` — food images, EXIF, same-meal grouping, injuries

### 4.1 Image files (`tables/phase2c_food_files_*.csv`)

| Variable | Definition |
|---|---|
| `file`, `suffix` | Filename / extension (`.jpg`/`.jpeg`/`.png`; 3 UUID names in p05 = app exports). |
| `format` | Decoded container (`JPEG`/`PNG`; no HEIC present). |
| `width`, `height` | Pixel dimensions (e.g. 4032×3024 ≈ 12 MP). |
| `mode` | Colour mode (all `RGB`, one `RGBA` screenshot). |
| `size_bytes` | File size (native exports ≈1–2 MB mean). |
| `datetime` | EXIF shutter time (`DateTime` tag, else `DateTimeOriginal` fallback). |
| `has_datetime` / `has_gps` / `has_orientation` | EXIF completeness flags (GPS: p01 99.4% vs p03/p05 0% — unusable as join key). |
| `orientation` | EXIF rotation tag (auto-rotate on load). |
| `is_food` | Gemini `is_photo_food` verdict (`YES` = food/beverage for human consumption; `NO` = screenshots, documents, toys, supplements under the strict reading). |
| `is_food_error` | Transport/API error text, if any (strict pass raises instead of labelling). |
| `is_food_model` | Labelling model per image (`gemini-3.5-flash-lite` for the first 426, `gemini-3.1-flash-lite` after the hand swap — not strictly comparable, see §4.4). |

### 4.2 Food summary & meal cadence (`tables/phase2c_food_summary.csv`, `phase2c_meal_intervals_sec_*.csv`)

| Variable | Definition |
|---|---|
| `n_images` | Photos per participant (321/136/186). |
| `formats`, `color_modes`, `top_resolutions` | Distributions of container / colour mode / top-3 resolutions. |
| `mean_kb`, `min_kb`, `max_kb` | File-size stats in kilobytes. |
| `pct_datetime`, `pct_gps`, `pct_orientation` | $100 \times$ share with each EXIF tag. |
| `n_corrupt_or_unreadable`, `corrupt_list` | PIL-decode failures (0; exact-duplicate timestamps and <50 KB files are separately flagged as pocket candidates). |
| `median_interval_h`, `p25_interval_h`, `p75_interval_h` | Quartiles of inter-photo gaps in hours. |
| `pct_intervals_le_30min`, `pct_intervals_le_60min` | Share of consecutive-photo gaps ≤30/60 min (legacy-1800 s view: 22.2% ≤30 min). |
| `pct_intervals_gt_6h` | Share of overnight-scale gaps. |
| `screenshot_or_uuid_names` | Filenames of app-export/screenshot suspects (e.g. `IMG_9111.png`). |
| Interval files | Seconds between consecutive EXIF datetimes (sorted), one value per gap (n = photos − 1). |

**Derived threshold**: aggregate deltas (n=640) show a dense left outlier cluster 0–15 s (n=43, shutter bursts) → sparse valley 15–120 s (n=13) → inter-meal mass ≥120 s. Rule (high limit of the outlier cluster; 3rd-centile = 3 s fallback unused) gives **meal_timedelta = 15 s** (legacy production default 1800 s). Cumulative: ≤15 s 6.7%, ≤60 s 8.1%, ≤300 s 12.8%, ≤1800 s 22.2%.

### 4.3 Vision same-meal validation (`tables/vision_summary.csv`, `tables/vision_same_meal_pairs.csv`, `tables/vision_cache.json`)

| Variable | Definition |
|---|---|
| `n_food_YES` / `n_food_NO` / `n_pending` | Images per verdict (pending = 0 at completion: 638/5/0). |
| `models` | Count of labels per model, e.g. `gemini-3.1-flash-lite:29; gemini-3.5-flash-lite:107`. |
| `non_food_files` | Filenames with `is_food = NO`. |
| Pair rows: `file1`, `file2` | Candidate pair (gap ≤1800 s at preselection; evaluated offline at all cut-offs). |
| `same_meal` | Gemini verdict: both photos depict one meal event (angles / before-during shots). |
| `model` (pairs) | `gemini-3.1-flash-lite` for all 193 pairs. |
| `gap_s` | EXIF time gap in seconds. |
| `threshold_s`, `n_pairs`, `n_confirmed`, `confirm_rate_pct` (sweep table) | For cut-off $t$: pairs with `gap_s ≤ t`, confirmations among them, $100 \times \mathrm{confirmed}/\mathrm{pairs}$. Flat ~72–73% for $t \le 300$ s, 63.7% at 1800 s. |
| `n_pairs_le15s`, `n_confirmed_le15s`, `confirm_rate` (per-participant @15 s) | Derived-operating-point precision per participant. |

### 4.4 Adverse events (`tables/phase2c_injury_*.csv`)

| Variable | Definition |
|---|---|
| `n_injury_reports` | Rows in `injury.csv` (24/11/10). |
| `n_reports_with_event` | Reports with non-empty dict (1/0/10). p05's repeats = one recurrent episode, not 10 independent traumas. |
| `events` | `timestamp {location: severity}` list. |
| `location`, `n` | Counts per anatomical site (left_foot 9, head_neck 1, right_hand 1). |
| `severity`, `n` | Counts per severity (11 minor, 0 major). |
| `srpe_hours` | $\sum \mathrm{duration\_min}/60$ from sRPE logs. |
| `exercise_hours` | $\sum \mathrm{activeDuration}/3600000$ from Fitbit bouts. |
| `total_exposure_h` | `srpe_hours + exercise_hours` (pooled 227.9 h). |
| Incidence | $1000 \times n_{\mathrm{events}} / \mathrm{total\_exposure\_h}$ = **48.3 per 1,000 h** (sRPE-only: 338.5 — inflated by p03/p05 under-logging). |
| `injury_event_days` / `non_event_days` / `horizon_days` | Days with ≥1 event vs without, over 152. |
| `imbalance_ratio` | Event-days : non-event-days (`1:151` p01, `0 events` p03, `1:14` p05; pooled ≈1:45–55). |
| `event_day_rate_pct` | $100 \times \mathrm{event\_days}/152$. Extreme imbalance → time-to-event/anomaly framing, never balanced classification. |

---

## 5. `phase3_preprocessing_modeling.md` — preprocessing design & modelling spec

Cleaning rules reuse the §1–§4 variables (sentinels → NaN: RHR `0.0`, Likert/readiness `0`, DST duplicates, `classic` sleep branch, `DateTime`-only EXIF gap, `lag_days` recall flag). Day-grain master table: one row per participant×day (3×152 = 456 rows) with coverage gates (`steps_cov_min`, `hr_cov_min`, `has_wellness`, `has_nutrition`).

Feature catalogue (all defined via §2–§4 primitives):

- **Activity/load**: `total_steps`, `peak_1min_steps`, `total_distance_m`, `total_kcal`, `exercise_min`, `n_sessions`, activity mix, Edwards TRIMP ($\sum_{\mathrm{zones}} \mathrm{minutes}_z \times w_z$ with zone weights), sRPE `load`, 7-day rolling load, `monotony`/`strain` (7 d), ACWR = 7-day load / 28-day load (p01 only — needs dense logs).
- **Cardiac**: `RHR_7d_median` + residual ($x - \mathrm{median}_{7d}$), HR mean/sd/peak, zone minutes + shares, time ≥85% max, post-exercise 1-min HR drop (recovery proxy).
- **Sleep**: `asleep_min`, `time_in_bed`, `efficiency`, stage minutes + `*_pct`, WASO (`wake` min), onset/offset hour, midsleep, social jetlag (weekend − weekday midsleep), sleep scores, `deep_min`, `restlessness`, `classic_flag`.
- **Subjective**: raw + within-person $z$-scores of all wellness items, `soreness_any` ($[soreness\_area] \ne []$), `n_zones`, `submission_hour` + `delayed_flag` (hour ≥12), `lag_days`, `weight_7d_median` + residual, fluids, `alcohol_bin` + `weekend_bin`.
- **Nutrition (Feb–Mar only)**: `n_meals_logged`, `n_photos`, `n_photo_meals`, kcal/protein/carbs/fat, `eating_window_h`, last-meal→sleep latency; otherwise `has_nutrition = 0` + NaNs.
- **Targets**: next-day readiness; next-night efficiency/deep%; injury-event-day; sRPE load (p01); weight-residual drift.
- **Validation**: leave-one-participant-out outer + causal time splits inner; metrics MAE/R² vs participant-mean baseline (regression), PR-AUC + recall@fixed-false-alarm + median lead-time in days (injury); leakage guards (rolling features end at D−1, train-fold standardisation, participant-grouped folds).
