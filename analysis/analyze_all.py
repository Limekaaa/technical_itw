import os
import json
import pandas as pd
import numpy as np

def run_full_analysis():
    report_lines = []
    
    report_lines.append("# Comprehensive Dataset Analysis Report\n")
    report_lines.append("This report provides an in-depth analysis of all health, wellness, nutrition, and activity data present in the repository across all participants (`p01`, `p03`, `p05`) and the root-level participant overview.\n")
    
    # 1. Root-level Participant Overview
    report_lines.append("## 1. Root-Level Participant Overview\n")
    report_lines.append("**File:** `participant-overview.xlsx`\n")
    overview_path = "participant-overview.xlsx"
    if os.path.exists(overview_path):
        df_ov = pd.read_excel(overview_path)
        # Headers from row 0
        headers = ["Participant ID", "Age", "Height (cm)", "Gender", "Chronotype", "Max Heart Rate", "First 5km Run Date", "First 5km Run Minutes", "First 5km Run Seconds", "Stride Walk (cm)", "Stride Run (cm)"]
        data_ov = df_ov.iloc[1:].copy()
        data_ov.columns = headers
        
        report_lines.append("### Variable Definitions & Data Types\n")
        report_lines.append("| Variable Name | Data Type | Description |")
        report_lines.append("|---|---|---|")
        report_lines.append("| `Participant ID` | String / Categorical | Unique identifier for each study participant (e.g., p01 to p16). |")
        report_lines.append("| `Age` | Numeric (Integer) | Age of the participant in years. |")
        report_lines.append("| `Height (cm)` | Numeric (Integer/Float) | Standing height of the participant in centimeters. |")
        report_lines.append("| `Gender` | Categorical | Gender of the participant (male, female). |")
        report_lines.append("| `Chronotype` | Categorical | Morning/Evening preference classification ('A person' or 'B person'). |")
        report_lines.append("| `Max Heart Rate` | Numeric (Integer) | Maximum recorded heart rate (bpm) during testing/activities. |")
        report_lines.append("| `First 5km Run Date` | Datetime / Text | Date when the participant completed their first timed 5km run. |")
        report_lines.append("| `First 5km Run Minutes` | Numeric (Integer) | Minutes component of the 5km run completion time. |")
        report_lines.append("| `First 5km Run Seconds` | Numeric (Integer) | Seconds component of the 5km run completion time. |")
        report_lines.append("| `Stride Walk (cm)` | Numeric (Float) | Average walking stride length measured by Fitbit in centimeters. |")
        report_lines.append("| `Stride Run (cm)` | Numeric (Float) | Average running stride length measured by Fitbit in centimeters.\n")
        
        report_lines.append("### Basic Statistics (`participant-overview.xlsx`)\n")
        report_lines.append("| Variable | Count | Mean | Std | Min | Median | Max | Missing |")
        report_lines.append("|---|---|---|---|---|---|---|---|")
        
        for col in data_ov.columns[1:]:
            s = pd.to_numeric(data_ov[col], errors='coerce')
            if s.notna().sum() > 0:
                std_val = f"{s.std():.2f}" if s.count() > 1 else "0.00"
                report_lines.append(f"| `{col}` | {s.count()} | {s.mean():.2f} | {std_val} | {s.min():.2f} | {s.median():.2f} | {s.max():.2f} | {data_ov[col].isna().sum()} |")
            else:
                report_lines.append(f"| `{col}` | {data_ov[col].count()} | N/A (Categorical) | - | - | - | - | {data_ov[col].isna().sum()} |")
        report_lines.append("\n")

    # 2. Participant Level Files
    participants = ["p01", "p03", "p05"]
    
    report_lines.append("## 2. Participant-Level Data Files\n")
    report_lines.append("Each participant folder (`p01`, `p03`, `p05`) contains `googledocs/`, `pmsys/`, and `fitbit/` subfolders with consistent schemas across participants.\n")
    
    # 2.1 Google Docs Reporting CSV
    report_lines.append("### 2.1 Google Docs Reporting (`googledocs/reporting.csv`)\n")
    report_lines.append("**Description:** Daily self-reported participant logs covering meals consumed, body weight, fluid intake, and alcohol consumption.\n")
    report_lines.append("#### Variables & Data Types\n")
    report_lines.append("| Variable Name | Data Type | Description |")
    report_lines.append("|---|---|---|")
    report_lines.append("| `date` | Datetime / String | Date of the reporting log entry (DD/MM/YYYY). |")
    report_lines.append("| `timestamp` | Datetime / String | Exact timestamp when the log was submitted. |")
    report_lines.append("| `meals` | Categorical / Text | Comma-separated list of meals logged (Breakfast, Lunch, Dinner, Evening). |")
    report_lines.append("| `weight` | Numeric (Float) | Self-reported body weight (e.g., in kg or lbs). |")
    report_lines.append("| `glasses_of_fluid` | Numeric (Integer) | Total glasses of fluid consumed during the day. |")
    report_lines.append("| `alcohol_consumed` | Categorical (Yes/No) | Indicator of whether alcohol was consumed.\n")
    
    # Aggregate stats across participants for reporting.csv
    rep_dfs = []
    for p in participants:
        p_path = f"{p}/googledocs/reporting.csv"
        if os.path.exists(p_path):
            df = pd.read_csv(p_path)
            df['participant'] = p
            rep_dfs.append(df)
    if rep_dfs:
        rep_all = pd.concat(rep_dfs, ignore_index=True)
        report_lines.append("#### Combined Statistics (`reporting.csv` across participants)\n")
        report_lines.append("| Variable | Count | Mean | Std | Min | Median | Max | Missing |")
        report_lines.append("|---|---|---|---|---|---|---|---|")
        for col in ['weight', 'glasses_of_fluid']:
            s = pd.to_numeric(rep_all[col], errors='coerce')
            report_lines.append(f"| `{col}` | {s.count()} | {s.mean():.2f} | {s.std():.2f} | {s.min():.2f} | {s.median():.2f} | {s.max():.2f} | {rep_all[col].isna().sum()} |")
        report_lines.append("\n")

    # 2.2 PMsys Wellness CSV
    report_lines.append("### 2.2 PMsys Wellness Log (`pmsys/wellness.csv`)\n")
    report_lines.append("**Description:** Daily psychometric wellness questionnaire evaluating fatigue, mood, readiness, sleep duration/quality, soreness, and stress.\n")
    report_lines.append("#### Variables & Data Types\n")
    report_lines.append("| Variable Name | Data Type | Description |")
    report_lines.append("|---|---|---|")
    report_lines.append("| `effective_time_frame` | Datetime (ISO 8601) | Timestamp of the wellness assessment submission. |")
    report_lines.append("| `fatigue` | Numeric (Integer) | Subjective fatigue rating (Likert scale). |")
    report_lines.append("| `mood` | Numeric (Integer) | Subjective mood rating. |")
    report_lines.append("| `readiness` | Numeric (Integer) | Physical/mental readiness to train. |")
    report_lines.append("| `sleep_duration_h` | Numeric (Float/Int) | Subjectively reported sleep duration in hours. |")
    report_lines.append("| `sleep_quality` | Numeric (Integer) | Subjective sleep quality rating. |")
    report_lines.append("| `soreness` | Numeric (Integer) | Muscle soreness rating. |")
    report_lines.append("| `soreness_area` | Text / JSON list | Body areas affected by soreness (anatomical IDs). |")
    report_lines.append("| `stress` | Numeric (Integer) | Subjective stress level rating.\n")
    
    wel_dfs = []
    for p in participants:
        p_path = f"{p}/pmsys/wellness.csv"
        if os.path.exists(p_path):
            df = pd.read_csv(p_path)
            wel_dfs.append(df)
    if wel_dfs:
        wel_all = pd.concat(wel_dfs, ignore_index=True)
        report_lines.append("#### Combined Statistics (`wellness.csv` across participants)\n")
        report_lines.append("| Variable | Count | Mean | Std | Min | Median | Max | Missing |")
        report_lines.append("|---|---|---|---|---|---|---|---|")
        wel_cols = ['fatigue', 'mood', 'readiness', 'sleep_duration_h', 'sleep_quality', 'soreness', 'stress']
        for col in wel_cols:
            s = pd.to_numeric(wel_all[col], errors='coerce')
            report_lines.append(f"| `{col}` | {s.count()} | {s.mean():.2f} | {s.std():.2f} | {s.min():.2f} | {s.median():.2f} | {s.max():.2f} | {wel_all[col].isna().sum()} |")
        report_lines.append("\n")

    # 2.3 PMsys SRPE CSV
    report_lines.append("### 2.3 PMsys Session RPE (`pmsys/srpe.csv`)\n")
    report_lines.append("**Description:** Session Rating of Perceived Exertion logs recording training sessions, activity types, perceived exertion scores, and duration.\n")
    report_lines.append("#### Variables & Data Types\n")
    report_lines.append("| Variable Name | Data Type | Description |")
    report_lines.append("|---|---|---|")
    report_lines.append("| `end_date_time` | Datetime (ISO 8601) | Timestamp marking the end of the training session. |")
    report_lines.append("| `activity_names` | Text / JSON list | Categories/types of activity performed (e.g., individual, running, team, soccer). |")
    report_lines.append("| `perceived_exertion` | Numeric (Integer) | Borg CR10 or similar RPE scale rating of session intensity. |")
    report_lines.append("| `duration_min` | Numeric (Integer) | Duration of the training session in minutes.\n")
    
    srpe_dfs = []
    for p in participants:
        p_path = f"{p}/pmsys/srpe.csv"
        if os.path.exists(p_path):
            df = pd.read_csv(p_path)
            srpe_dfs.append(df)
    if srpe_dfs:
        srpe_all = pd.concat(srpe_dfs, ignore_index=True)
        report_lines.append("#### Combined Statistics (`srpe.csv` across participants)\n")
        report_lines.append("| Variable | Count | Mean | Std | Min | Median | Max | Missing |")
        report_lines.append("|---|---|---|---|---|---|---|---|")
        for col in ['perceived_exertion', 'duration_min']:
            s = pd.to_numeric(srpe_all[col], errors='coerce')
            report_lines.append(f"| `{col}` | {s.count()} | {s.mean():.2f} | {s.std():.2f} | {s.min():.2f} | {s.median():.2f} | {s.max():.2f} | {srpe_all[col].isna().sum()} |")
        report_lines.append("\n")

    # 2.4 PMsys Injury CSV
    report_lines.append("### 2.4 PMsys Injury Log (`pmsys/injury.csv`)\n")
    report_lines.append("**Description:** Weekly or periodic injury tracking logs indicating location and severity of injuries.\n")
    report_lines.append("#### Variables & Data Types\n")
    report_lines.append("| Variable Name | Data Type | Description |")
    report_lines.append("|---|---|---|")
    report_lines.append("| `effective_time_frame` | Datetime (ISO 8601) | Timestamp of the injury report. |")
    report_lines.append("| `injuries` | Text / JSON dict | Dictionary mapping body part to severity (e.g., `{'right_hand': 'minor'}` or `{}`).\n")

    # 2.5 Fitbit Sleep Score CSV
    report_lines.append("### 2.5 Fitbit Sleep Score (`fitbit/sleep_score.csv`)\n")
    report_lines.append("**Description:** Daily Fitbit sleep quality scoring including composition, revitalization, duration scores, deep sleep minutes, resting heart rate during sleep, and restlessness index.\n")
    report_lines.append("#### Variables & Data Types\n")
    report_lines.append("| Variable Name | Data Type | Description |")
    report_lines.append("|---|---|---|")
    report_lines.append("| `timestamp` | Datetime / String | Timestamp of the sleep log record. |")
    report_lines.append("| `sleep_log_entry_id` | Numeric (Int64) | Unique Fitbit sleep log identifier. |")
    report_lines.append("| `overall_score` | Numeric (Integer) | Overall Fitbit sleep score (0-100). |")
    report_lines.append("| `composition_score` | Numeric (Integer) | Score evaluating sleep duration and depth proportion. |")
    report_lines.append("| `revitalization_score` | Numeric (Integer) | Score evaluating sleeping heart rate and restlessness. |")
    report_lines.append("| `duration_score` | Numeric (Integer) | Score evaluating total sleep duration against targets. |")
    report_lines.append("| `deep_sleep_in_minutes` | Numeric (Integer) | Total duration spent in deep sleep stages (minutes). |")
    report_lines.append("| `resting_heart_rate` | Numeric (Integer) | Resting heart rate measured during sleep (bpm). |")
    report_lines.append("| `restlessness` | Numeric (Float) | Calculated restlessness ratio during sleep.\n")

    ss_dfs = []
    for p in participants:
        p_path = f"{p}/fitbit/sleep_score.csv"
        if os.path.exists(p_path):
            df = pd.read_csv(p_path)
            ss_dfs.append(df)
    if ss_dfs:
        ss_all = pd.concat(ss_dfs, ignore_index=True)
        report_lines.append("#### Combined Statistics (`sleep_score.csv` across participants)\n")
        report_lines.append("| Variable | Count | Mean | Std | Min | Median | Max | Missing |")
        report_lines.append("|---|---|---|---|---|---|---|---|")
        ss_cols = ['overall_score', 'composition_score', 'revitalization_score', 'duration_score', 'deep_sleep_in_minutes', 'resting_heart_rate', 'restlessness']
        for col in ss_cols:
            s = pd.to_numeric(ss_all[col], errors='coerce')
            report_lines.append(f"| `{col}` | {s.count()} | {s.mean():.2f} | {s.std():.2f} | {s.min():.2f} | {s.median():.2f} | {s.max():.2f} | {ss_all[col].isna().sum()} |")
        report_lines.append("\n")

    # 2.6 Fitbit JSON Exports
    report_lines.append("### 2.6 Fitbit JSON Exports (High-Frequency & Daily Summaries)\n")
    report_lines.append("The `fitbit/` directory contains several JSON exports tracking movement, biometrics, and sleep stages across participants:\n")
    report_lines.append("1. **`calories.json`**: Minute-level or aggregated active calorie expenditure (`dateTime`, `value`).")
    report_lines.append("2. **`distance.json`**: Minute-level or daily distance traveled in centimeters (`dateTime`, `value`).")
    report_lines.append("3. **`steps.json`**: Minute-level step counts (`dateTime`, `value`).")
    report_lines.append("4. **`heart_rate.json`**: High-frequency heart rate recordings (`dateTime`, `value.bpm`, `value.confidence`). Note: Absent for participant `p03`.")
    report_lines.append("5. **`resting_heart_rate.json`**: Daily resting heart rate with algorithm error estimates (`dateTime`, `value.date`, `value.value`, `value.error`).")
    report_lines.append("6. **`time_in_heart_rate_zones.json`**: Daily duration spent in various heart rate zones (`BELOW_DEFAULT_ZONE_1`, `IN_DEFAULT_ZONE_1`, `IN_DEFAULT_ZONE_2`, `IN_DEFAULT_ZONE_3`).")
    report_lines.append("7. **`sleep.json`**: Detailed sleep stage logs including deep, light, REM, and wake minutes, efficiency, and start/end timestamps.")
    report_lines.append("8. **`exercise.json`**: Logged workout sessions including duration, calories, average heart rate, elevation gain, and activity levels.\n")

    # Summary and conclusion
    report_lines.append("## 3. Key Findings & Summary\n")
    report_lines.append("- **Multi-Modal Data Integration:** The dataset successfully combines subjective self-reports (wellness, nutrition, SRPE, injury logs) with objective biometric tracking from Fitbit (steps, calories, distance, heart rate, sleep architecture).")
    report_lines.append("- **Data Completeness & Observations:** Participant overview data covers 16 participants, whereas detailed raw sensor and CSV logs (`p01`, `p03`, `p05`) are present for active study participants. Note that participant `p03` lacks `heart_rate.json`, which should be accounted for in advanced cardiovascular analyses.")
    report_lines.append("- **Consistency:** Naming conventions and schemas across `p01`, `p03`, and `p05` are highly standardized, making ingestion and comparative longitudinal analysis straightforward using Python/Pandas.\n")

    report_path = "/home/maxime/PersoProj/MAUNA/Test technique/Test technique/analysis/findings.md"
    with open(report_path, "w") as f:
        f.write("\n".join(report_lines))
    print(f"Findings report successfully written to {report_path}")

if __name__ == "__main__":
    run_full_analysis()
