# Comprehensive Dataset Analysis Report

This report provides an in-depth analysis of all health, wellness, nutrition, and activity data present in the repository across all participants (`p01`, `p03`, `p05`) and the root-level participant overview.

## 1. Root-Level Participant Overview

**File:** `participant-overview.xlsx`

### Variable Definitions & Data Types

| Variable Name | Data Type | Description |
|---|---|---|
| `Participant ID` | String / Categorical | Unique identifier for each study participant (e.g., p01 to p16). |
| `Age` | Numeric (Integer) | Age of the participant in years. |
| `Height (cm)` | Numeric (Integer/Float) | Standing height of the participant in centimeters. |
| `Gender` | Categorical | Gender of the participant (male, female). |
| `Chronotype` | Categorical | Morning/Evening preference classification ('A person' or 'B person'). |
| `Max Heart Rate` | Numeric (Integer) | Maximum recorded heart rate (bpm) during testing/activities. |
| `First 5km Run Date` | Datetime / Text | Date when the participant completed their first timed 5km run. |
| `First 5km Run Minutes` | Numeric (Integer) | Minutes component of the 5km run completion time. |
| `First 5km Run Seconds` | Numeric (Integer) | Seconds component of the 5km run completion time. |
| `Stride Walk (cm)` | Numeric (Float) | Average walking stride length measured by Fitbit in centimeters. |
| `Stride Run (cm)` | Numeric (Float) | Average running stride length measured by Fitbit in centimeters.

### Basic Statistics (`participant-overview.xlsx`)

| Variable | Count | Mean | Std | Min | Median | Max | Missing |
|---|---|---|---|---|---|---|---|
| `Age` | 16 | 34.88 | 11.67 | 23.00 | 29.00 | 60.00 | 0 |
| `Height (cm)` | 16 | 179.62 | 6.78 | 163.00 | 180.00 | 195.00 | 0 |
| `Gender` | 16 | N/A (Categorical) | - | - | - | - | 0 |
| `Chronotype` | 16 | N/A (Categorical) | - | - | - | - | 0 |
| `Max Heart Rate` | 13 | 186.62 | 13.07 | 157.00 | 186.00 | 203.00 | 2 |
| `First 5km Run Date` | 16 | N/A (Categorical) | - | - | - | - | 0 |
| `First 5km Run Minutes` | 15 | 28.07 | 7.25 | 18.00 | 28.00 | 47.00 | 0 |
| `First 5km Run Seconds` | 15 | 25.13 | 14.01 | 6.00 | 22.00 | 51.00 | 0 |
| `Stride Walk (cm)` | 14 | 74.23 | 3.10 | 67.30 | 74.70 | 80.90 | 2 |
| `Stride Run (cm)` | 14 | 97.53 | 27.02 | 11.30 | 102.60 | 128.80 | 2 |


## 2. Participant-Level Data Files

Each participant folder (`p01`, `p03`, `p05`) contains `googledocs/`, `pmsys/`, and `fitbit/` subfolders with consistent schemas across participants.

### 2.1 Google Docs Reporting (`googledocs/reporting.csv`)

**Description:** Daily self-reported participant logs covering meals consumed, body weight, fluid intake, and alcohol consumption.

#### Variables & Data Types

| Variable Name | Data Type | Description |
|---|---|---|
| `date` | Datetime / String | Date of the reporting log entry (DD/MM/YYYY). |
| `timestamp` | Datetime / String | Exact timestamp when the log was submitted. |
| `meals` | Categorical / Text | Comma-separated list of meals logged (Breakfast, Lunch, Dinner, Evening). |
| `weight` | Numeric (Float) | Self-reported body weight (e.g., in kg or lbs). |
| `glasses_of_fluid` | Numeric (Integer) | Total glasses of fluid consumed during the day. |
| `alcohol_consumed` | Categorical (Yes/No) | Indicator of whether alcohol was consumed.

#### Combined Statistics (`reporting.csv` across participants)

| Variable | Count | Mean | Std | Min | Median | Max | Missing |
|---|---|---|---|---|---|---|---|
| `weight` | 276 | 94.57 | 8.55 | 82.00 | 100.00 | 103.00 | 76 |
| `glasses_of_fluid` | 352 | 8.15 | 3.17 | 3.00 | 8.00 | 20.00 | 0 |


### 2.2 PMsys Wellness Log (`pmsys/wellness.csv`)

**Description:** Daily psychometric wellness questionnaire evaluating fatigue, mood, readiness, sleep duration/quality, soreness, and stress.

#### Variables & Data Types

| Variable Name | Data Type | Description |
|---|---|---|
| `effective_time_frame` | Datetime (ISO 8601) | Timestamp of the wellness assessment submission. |
| `fatigue` | Numeric (Integer) | Subjective fatigue rating (Likert scale). |
| `mood` | Numeric (Integer) | Subjective mood rating. |
| `readiness` | Numeric (Integer) | Physical/mental readiness to train. |
| `sleep_duration_h` | Numeric (Float/Int) | Subjectively reported sleep duration in hours. |
| `sleep_quality` | Numeric (Integer) | Subjective sleep quality rating. |
| `soreness` | Numeric (Integer) | Muscle soreness rating. |
| `soreness_area` | Text / JSON list | Body areas affected by soreness (anatomical IDs). |
| `stress` | Numeric (Integer) | Subjective stress level rating.

#### Combined Statistics (`wellness.csv` across participants)

| Variable | Count | Mean | Std | Min | Median | Max | Missing |
|---|---|---|---|---|---|---|---|
| `fatigue` | 357 | 2.69 | 0.58 | 0.00 | 3.00 | 4.00 | 0 |
| `mood` | 357 | 2.86 | 0.59 | 0.00 | 3.00 | 4.00 | 0 |
| `readiness` | 357 | 4.61 | 2.34 | 0.00 | 5.00 | 8.00 | 0 |
| `sleep_duration_h` | 357 | 5.76 | 1.22 | 0.00 | 6.00 | 9.00 | 0 |
| `sleep_quality` | 357 | 2.76 | 0.50 | 0.00 | 3.00 | 4.00 | 0 |
| `soreness` | 357 | 2.81 | 0.48 | 0.00 | 3.00 | 4.00 | 0 |
| `stress` | 357 | 2.77 | 0.63 | 0.00 | 3.00 | 4.00 | 0 |


### 2.3 PMsys Session RPE (`pmsys/srpe.csv`)

**Description:** Session Rating of Perceived Exertion logs recording training sessions, activity types, perceived exertion scores, and duration.

#### Variables & Data Types

| Variable Name | Data Type | Description |
|---|---|---|
| `end_date_time` | Datetime (ISO 8601) | Timestamp marking the end of the training session. |
| `activity_names` | Text / JSON list | Categories/types of activity performed (e.g., individual, running, team, soccer). |
| `perceived_exertion` | Numeric (Integer) | Borg CR10 or similar RPE scale rating of session intensity. |
| `duration_min` | Numeric (Integer) | Duration of the training session in minutes.

#### Combined Statistics (`srpe.csv` across participants)

| Variable | Count | Mean | Std | Min | Median | Max | Missing |
|---|---|---|---|---|---|---|---|
| `perceived_exertion` | 45 | 5.89 | 1.07 | 3.00 | 6.00 | 9.00 | 0 |
| `duration_min` | 45 | 43.33 | 18.22 | 20.00 | 30.00 | 90.00 | 0 |


### 2.4 PMsys Injury Log (`pmsys/injury.csv`)

**Description:** Weekly or periodic injury tracking logs indicating location and severity of injuries.

#### Variables & Data Types

| Variable Name | Data Type | Description |
|---|---|---|
| `effective_time_frame` | Datetime (ISO 8601) | Timestamp of the injury report. |
| `injuries` | Text / JSON dict | Dictionary mapping body part to severity (e.g., `{'right_hand': 'minor'}` or `{}`).

### 2.5 Fitbit Sleep Score (`fitbit/sleep_score.csv`)

**Description:** Daily Fitbit sleep quality scoring including composition, revitalization, duration scores, deep sleep minutes, resting heart rate during sleep, and restlessness index.

#### Variables & Data Types

| Variable Name | Data Type | Description |
|---|---|---|
| `timestamp` | Datetime / String | Timestamp of the sleep log record. |
| `sleep_log_entry_id` | Numeric (Int64) | Unique Fitbit sleep log identifier. |
| `overall_score` | Numeric (Integer) | Overall Fitbit sleep score (0-100). |
| `composition_score` | Numeric (Integer) | Score evaluating sleep duration and depth proportion. |
| `revitalization_score` | Numeric (Integer) | Score evaluating sleeping heart rate and restlessness. |
| `duration_score` | Numeric (Integer) | Score evaluating total sleep duration against targets. |
| `deep_sleep_in_minutes` | Numeric (Integer) | Total duration spent in deep sleep stages (minutes). |
| `resting_heart_rate` | Numeric (Integer) | Resting heart rate measured during sleep (bpm). |
| `restlessness` | Numeric (Float) | Calculated restlessness ratio during sleep.

#### Combined Statistics (`sleep_score.csv` across participants)

| Variable | Count | Mean | Std | Min | Median | Max | Missing |
|---|---|---|---|---|---|---|---|
| `overall_score` | 341 | 75.29 | 6.98 | 53.00 | 76.00 | 92.00 | 0 |
| `composition_score` | 341 | 18.63 | 2.42 | 12.00 | 19.00 | 24.00 | 0 |
| `revitalization_score` | 341 | 19.61 | 3.33 | 10.00 | 20.00 | 25.00 | 0 |
| `duration_score` | 341 | 37.05 | 4.17 | 20.00 | 37.00 | 47.00 | 0 |
| `deep_sleep_in_minutes` | 341 | 54.62 | 24.27 | 0.00 | 54.00 | 131.00 | 0 |
| `resting_heart_rate` | 341 | 57.05 | 5.84 | 49.00 | 55.00 | 70.00 | 0 |
| `restlessness` | 341 | 0.08 | 0.03 | 0.03 | 0.07 | 0.20 | 0 |


### 2.6 Fitbit JSON Exports (High-Frequency & Daily Summaries)

The `fitbit/` directory contains several JSON exports tracking movement, biometrics, and sleep stages across participants:

1. **`calories.json`**: Minute-level or aggregated active calorie expenditure (`dateTime`, `value`).
2. **`distance.json`**: Minute-level or daily distance traveled in centimeters (`dateTime`, `value`).
3. **`steps.json`**: Minute-level step counts (`dateTime`, `value`).
4. **`heart_rate.json`**: High-frequency heart rate recordings (`dateTime`, `value.bpm`, `value.confidence`). Note: Absent for participant `p03`.
5. **`resting_heart_rate.json`**: Daily resting heart rate with algorithm error estimates (`dateTime`, `value.date`, `value.value`, `value.error`).
6. **`time_in_heart_rate_zones.json`**: Daily duration spent in various heart rate zones (`BELOW_DEFAULT_ZONE_1`, `IN_DEFAULT_ZONE_1`, `IN_DEFAULT_ZONE_2`, `IN_DEFAULT_ZONE_3`).
7. **`sleep.json`**: Detailed sleep stage logs including deep, light, REM, and wake minutes, efficiency, and start/end timestamps.
8. **`exercise.json`**: Logged workout sessions including duration, calories, average heart rate, elevation gain, and activity levels.

## 3. Key Findings & Summary

- **Multi-Modal Data Integration:** The dataset successfully combines subjective self-reports (wellness, nutrition, SRPE, injury logs) with objective biometric tracking from Fitbit (steps, calories, distance, heart rate, sleep architecture).
- **Data Completeness & Observations:** Participant overview data covers 16 participants, whereas detailed raw sensor and CSV logs (`p01`, `p03`, `p05`) are present for active study participants. Note that participant `p03` lacks `heart_rate.json`, which should be accounted for in advanced cardiovascular analyses.
- **Consistency:** Naming conventions and schemas across `p01`, `p03`, and `p05` are highly standardized, making ingestion and comparative longitudinal analysis straightforward using Python/Pandas.
