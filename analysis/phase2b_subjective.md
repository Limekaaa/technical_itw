# Phase 2B — Subjective & Periodic Logs (PMSYS + Google Docs)

_Generated 2026-09-17 10:50. Tables: `tables/phase2b_*.csv`._

## 2B.1 Response rates & submission-time cadence

| participant | n_rows | n_days_with_log | horizon_days | response_rate | first | last | median_hour | sd_hour | pct_before_09 | pct_after_12 |
|---|---|---|---|---|---|---|---|---|---|---|
| p01 | 138 | 138 | 152 | 0.91 | 2019-11-01 08:31:40.751000+00:00 | 2020-03-30 07:24:02.816000+00:00 | 8.00 | 4.11 | 60.90 | 16.70 |
| p03 | 82 | 78 | 152 | 0.51 | 2019-11-01 08:03:15.527000+00:00 | 2020-03-30 23:06:29.537000+00:00 | 11.00 | 6.40 | 42.70 | 43.90 |
| p05 | 137 | 134 | 152 | 0.88 | 2019-11-01 06:30:18.128000+00:00 | 2020-03-30 04:48:34.872000+00:00 | 6.00 | 3.85 | 83.90 | 8.80 |

Wellness submission hour (UTC) — counts per hour:

```
p01: 05h:7, 06h:12, 07h:21, 08h:44, 09h:16, 10h:8, 11h:7, 12h:3, 13h:1, 14h:2, 15h:1, 16h:1, 17h:2, 18h:2, 19h:1, 20h:5, 21h:2, 22h:3
p03: 00h:2, 01h:1, 03h:1, 05h:1, 06h:8, 07h:13, 08h:9, 09h:3, 10h:2, 11h:6, 12h:3, 13h:4, 14h:4, 15h:2, 17h:1, 18h:3, 19h:1, 20h:3, 21h:4, 22h:4, 23h:7
p05: 04h:2, 05h:38, 06h:49, 07h:11, 08h:15, 09h:3, 10h:3, 11h:4, 16h:2, 17h:2, 18h:1, 19h:2, 20h:3, 21h:1, 22h:1
```

- **Adherence**: p01 91%, p05 88% of horizon days; **p03 51%** — any longitudinal model must handle p03 block-missingness (not MCAR: gaps cluster).
- **Timing**: p05 is the compliant morning reporter (49×06h + 38×05h); p01 centres 07–08h with afternoon/evening tail (20h:5, 22h:3 — recall-delayed rows); **p03 is erratic** (reports at 23h×7, 00–03h×4, spread across all 24 h). Weight morning-vs-evening comparisons by submission hour; consider excluding post-12h wellness rows from 'morning readiness' features.
- **Reporting.csv lag**: `date` (log day, DD/MM/YYYY dayfirst) vs `timestamp` (submission) differ by days–weeks (e.g. p01 log 06/11 submitted 06/12; p03 logs 15–16/11 submitted 20/11). Lag itself is a compliance feature; weight/alcohol values are recalled, not measured same-day.

## 2B.2 Likert distributions & floor/ceiling effects

| n | mean | median | sd | q25 | q75 | iqr | skew | p1 | p99 | min | max | participant | metric | mode | mode_share | n_unique | value_counts |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 138 | 2.57 | 3.00 | 0.54 | 2.00 | 3.00 | 1.00 | -0.40 | 1.37 | 3.00 | 1.00 | 4.00 | p01 | fatigue | 3 | 0.56 | 4 | 1:1%;2:41%;3:57%;4:1% |
| 138 | 2.96 | 3.00 | 0.28 | 3.00 | 3.00 | 0.00 | -3.28 | 2.00 | 3.63 | 1.00 | 4.00 | p01 | mood | 3 | 0.94 | 4 | 1:1%;2:4%;3:94%;4:1% |
| 138 | 6.22 | 7.00 | 1.41 | 5.00 | 7.00 | 2.00 | -0.74 | 3.00 | 8.00 | 2.00 | 8.00 | p01 | readiness | 7 | 0.33 | 7 | 2:1%;3:4%;4:9%;5:13%;6:22%;7:33%;8:18% |
| 138 | 5.50 | 5.00 | 0.74 | 5.00 | 6.00 | 1.00 | 0.55 | 4.00 | 7.00 | 4.00 | 8.00 | p01 | sleep_duration_h | 5 | 0.51 | 5 | 4:4%;5:51%;6:36%;7:8%;8:1% |
| 138 | 2.72 | 3.00 | 0.48 | 2.00 | 3.00 | 1.00 | -1.01 | 2.00 | 3.00 | 1.00 | 4.00 | p01 | sleep_quality | 3 | 0.72 | 4 | 1:1%;2:27%;3:72%;4:1% |
| 138 | 2.54 | 3.00 | 0.53 | 2.00 | 3.00 | 1.00 | -0.48 | 1.37 | 3.00 | 1.00 | 3.00 | p01 | soreness | 3 | 0.56 | 3 | 1:1%;2:43%;3:56% |
| 138 | 2.88 | 3.00 | 0.33 | 3.00 | 3.00 | 0.00 | -2.32 | 2.00 | 3.00 | 2.00 | 3.00 | p01 | stress | 3 | 0.88 | 2 | 2:12%;3:88% |
| 82 | 2.94 | 3.00 | 0.29 | 3.00 | 3.00 | 0.00 | -2.00 | 2.00 | 3.19 | 2.00 | 4.00 | p03 | fatigue | 3 | 0.92 | 3 | 2:7%;3:91%;4:1% |
| 82 | 2.96 | 3.00 | 0.29 | 3.00 | 3.00 | 0.00 | -4.20 | 1.81 | 3.19 | 1.00 | 4.00 | p03 | mood | 3 | 0.95 | 4 | 1:1%;2:2%;3:95%;4:1% |
| 82 | 4.96 | 5.00 | 0.29 | 5.00 | 5.00 | 0.00 | -4.20 | 3.81 | 5.19 | 3.00 | 6.00 | p03 | readiness | 5 | 0.95 | 4 | 3:1%;4:2%;5:95%;6:1% |
| 82 | 6.63 | 7.00 | 1.13 | 6.00 | 7.00 | 1.00 | -1.93 | 2.81 | 8.00 | 2.00 | 8.00 | p03 | sleep_duration_h | 7 | 0.57 | 7 | 2:1%;3:2%;4:2%;5:4%;6:20%;7:57%;8:13% |
| 82 | 2.99 | 3.00 | 0.25 | 3.00 | 3.00 | 0.00 | -0.68 | 2.00 | 4.00 | 2.00 | 4.00 | p03 | sleep_quality | 3 | 0.94 | 3 | 2:4%;3:94%;4:2% |
| 82 | 2.96 | 3.00 | 0.19 | 3.00 | 3.00 | 0.00 | -5.03 | 2.00 | 3.00 | 2.00 | 3.00 | p03 | soreness | 3 | 0.96 | 2 | 2:4%;3:96% |
| 82 | 2.95 | 3.00 | 0.27 | 3.00 | 3.00 | 0.00 | -2.07 | 2.00 | 3.19 | 2.00 | 4.00 | p03 | stress | 3 | 0.93 | 3 | 2:6%;3:93%;4:1% |
| 137 | 2.66 | 3.00 | 0.69 | 3.00 | 3.00 | 0.00 | -1.91 | 0.36 | 3.00 | 0.00 | 4.00 | p05 | fatigue | 3 | 0.75 | 5 | 0:1%;1:7%;2:15%;3:75%;4:1% |
| 137 | 2.69 | 3.00 | 0.86 | 2.00 | 3.00 | 1.00 | -0.78 | 0.36 | 4.00 | 0.00 | 4.00 | p05 | mood | 3 | 0.56 | 5 | 0:1%;1:9%;2:22%;3:55%;4:12% |
| 137 | 2.78 | 5.00 | 2.49 | 0.00 | 5.00 | 5.00 | -0.18 | 0.00 | 5.00 | 0.00 | 8.00 | p05 | readiness | 5 | 0.51 | 5 | 0:44%;3:1%;4:4%;5:51%;8:1% |
| 137 | 5.49 | 5.00 | 1.40 | 5.00 | 7.00 | 2.00 | -0.66 | 1.08 | 8.00 | 0.00 | 9.00 | p05 | sleep_duration_h | 5 | 0.34 | 8 | 0:1%;3:3%;4:16%;5:34%;6:17%;7:25%;8:3%;9:1% |
| 137 | 2.67 | 3.00 | 0.60 | 2.00 | 3.00 | 1.00 | -1.65 | 0.36 | 3.64 | 0.00 | 4.00 | p05 | sleep_quality | 3 | 0.68 | 5 | 0:1%;1:1%;2:28%;3:68%;4:1% |
| 137 | 2.98 | 3.00 | 0.43 | 3.00 | 3.00 | 0.00 | -4.69 | 0.72 | 4.00 | 0.00 | 4.00 | p05 | soreness | 3 | 0.93 | 4 | 0:1%;2:1%;3:93%;4:4% |
| 137 | 2.55 | 3.00 | 0.89 | 2.00 | 3.00 | 1.00 | -0.62 | 0.36 | 4.00 | 0.00 | 4.00 | p05 | stress | 3 | 0.52 | 5 | 0:1%;1:13%;2:24%;3:52%;4:9% |

- p01/fatigue: mode=3 (0.565 of rows), unique=4, range [1.0,4.0], counts {1:1%;2:41%;3:57%;4:1%}
- p01/mood: mode=3 (0.942 of rows), unique=4, range [1.0,4.0], counts {1:1%;2:4%;3:94%;4:1%}
- p01/readiness: mode=7 (0.326 of rows), unique=7, range [2.0,8.0], counts {2:1%;3:4%;4:9%;5:13%;6:22%;7:33%;8:18%}
- p01/sleep_duration_h: mode=5 (0.507 of rows), unique=5, range [4.0,8.0], counts {4:4%;5:51%;6:36%;7:8%;8:1%}
- p01/sleep_quality: mode=3 (0.717 of rows), unique=4, range [1.0,4.0], counts {1:1%;2:27%;3:72%;4:1%}
- p01/soreness: mode=3 (0.558 of rows), unique=3, range [1.0,3.0], counts {1:1%;2:43%;3:56%}
- p01/stress: mode=3 (0.877 of rows), unique=2, range [2.0,3.0], counts {2:12%;3:88%}
- p03/fatigue: mode=3 (0.915 of rows), unique=3, range [2.0,4.0], counts {2:7%;3:91%;4:1%}
- p03/mood: mode=3 (0.951 of rows), unique=4, range [1.0,4.0], counts {1:1%;2:2%;3:95%;4:1%}
- p03/readiness: mode=5 (0.951 of rows), unique=4, range [3.0,6.0], counts {3:1%;4:2%;5:95%;6:1%}
- p03/sleep_duration_h: mode=7 (0.573 of rows), unique=7, range [2.0,8.0], counts {2:1%;3:2%;4:2%;5:4%;6:20%;7:57%;8:13%}
- p03/sleep_quality: mode=3 (0.939 of rows), unique=3, range [2.0,4.0], counts {2:4%;3:94%;4:2%}
- p03/soreness: mode=3 (0.963 of rows), unique=2, range [2.0,3.0], counts {2:4%;3:96%}
- p03/stress: mode=3 (0.927 of rows), unique=3, range [2.0,4.0], counts {2:6%;3:93%;4:1%}
- p05/fatigue: mode=3 (0.752 of rows), unique=5, range [0.0,4.0], counts {0:1%;1:7%;2:15%;3:75%;4:1%}
- p05/mood: mode=3 (0.555 of rows), unique=5, range [0.0,4.0], counts {0:1%;1:9%;2:22%;3:55%;4:12%}
- p05/readiness: mode=5 (0.511 of rows), unique=5, range [0.0,8.0], counts {0:44%;3:1%;4:4%;5:51%;8:1%}
- p05/sleep_duration_h: mode=5 (0.343 of rows), unique=8, range [0.0,9.0], counts {0:1%;3:3%;4:16%;5:34%;6:17%;7:25%;8:3%;9:1%}
- p05/sleep_quality: mode=3 (0.679 of rows), unique=5, range [0.0,4.0], counts {0:1%;1:1%;2:28%;3:68%;4:1%}
- p05/soreness: mode=3 (0.934 of rows), unique=4, range [0.0,4.0], counts {0:1%;2:1%;3:93%;4:4%}
- p05/stress: mode=3 (0.518 of rows), unique=5, range [0.0,4.0], counts {0:1%;1:13%;2:24%;3:52%;4:9%}

- **Floor/ceiling**: 1–5 scales never use the full span per participant (p03 readiness ∈ {3,4,5,6} only; p05 readiness ∈ {0,3,4,5,8} with 0s = likely missed-question sentinel). p05 0-values on fatigue/mood/readiness/sleep_duration_h/sleep_quality/soreness/stress need sentinel audit before modelling (0 outside the 1–5 instrument = missing, not 'no fatigue').
- **Constant-3s check**: no participant is a pure constant responder, but `soreness_area=[]` dominates (p01 78/138, p03 79/82, p05 135/137) and p03 wellness SDs are the smallest — low-signal subject.

## 2B.3 Intra- vs inter-individual variance

| metric | grand_mean | within_participant_mean_sd | between_participant_sd_of_means | ratio_between_within |
|---|---|---|---|---|
| fatigue | 2.69 | 0.51 | 0.19 | 0.38 |
| mood | 2.86 | 0.48 | 0.16 | 0.34 |
| readiness | 4.61 | 1.40 | 1.74 | 1.25 |
| sleep_duration_h | 5.76 | 1.09 | 0.66 | 0.60 |
| sleep_quality | 2.76 | 0.44 | 0.17 | 0.38 |
| soreness | 2.81 | 0.38 | 0.25 | 0.65 |
| stress | 2.77 | 0.50 | 0.21 | 0.43 |

Rule of thumb: ratio between/within <0.5 → personal baselines dominate; standardise within participant (z-score / median-centre) before any pooled model. Readiness shows the largest between-subject spread (scale 0–10 vs 1–5).

## 2B.4 sRPE load, spikes, monotony & strain

sRPE load = RPE × duration_min. Monotony = mean(daily load)/sd(daily load); Strain = Σload × monotony (Foster). Daily-load series: `tables/phase2b_srpe_daily_load_{p01,p03,p05}.csv`.

| participant | n_sessions | mean_RPE | mean_duration | total_load | mean_daily_load | sd_daily_load | monotony | strain | n_spike_days | max_daily_load | activity_types |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p01 | 34 | 6.09 | 45.90 | 9510.00 | 62.57 | 138.09 | 0.45 | 4308.90 | 11 | 660.00 | ['individual', 'endurance'];['individual', 'running'];['team', 'soccer'] |
| p03 | 2 | 6.00 | 30.00 | 360.00 | 2.37 | 20.87 | 0.11 | 40.90 | 2 | 210.00 | ['individual', 'running'] |
| p05 | 9 | 5.11 | 36.70 | 1660.00 | 10.92 | 50.93 | 0.21 | 356.00 | 7 | 380.00 | ['individual', 'endurance'];['individual', 'running'];['individual', 'strength', 'endurance'];['individual', 'strength'] |

- **Sparsity warning**: p03 has 2 sessions, p05 has 9 (one with missing RPE/duration → load NaN) — monotony/strain are degenerate for p03/p05 (sd≈0-inflated by 150 zero days). Report them but do not model on sRPE alone; fuse with Fitbit exercise minutes + HR-zone load (Edwards TRIMP) for exposure.
- **p01** (34 sessions, total load ≈ high): spike days = daily load > mean+2sd; inspect weekly monotony >2.0 as overtraining flag. Activity mix: individual/running + team/soccer + endurance — load should be stratified by type.

## 2B.5 Weight stability: noise vs true mass change

| participant | n_weight_obs | n_missing_weight | mean | sd | cv_pct | min | max | range | mean_abs_day_to_day | max_abs_day_to_day | n_changes_gt2kg |
|---|---|---|---|---|---|---|---|---|---|---|---|
| p01 | 82 | 27 | 100.36 | 0.67 | 0.67 | 99.00 | 102.00 | 3.00 | 0.50 | 2.00 | 0 |
| p03 | 93 | 24 | 82.66 | 0.76 | 0.92 | 82.00 | 84.00 | 2.00 | 0.12 | 1.00 | 0 |
| p05 | 101 | 25 | 100.85 | 1.00 | 0.99 | 99.00 | 103.00 | 4.00 | 0.32 | 2.00 | 0 |

- All participants are **hyper-stable**: range 3 kg (p01 99–102), 2 kg (p03 82–84), 4 kg (p05 99–103); CV <1%; mean |day-to-day| <0.5 kg (scale noise + hydration). No >2 kg jumps observed → no true mass-change events; treat weight as slow drift (7-day median) + hydration residual, not a daily feature.
- Missingness 20–25% per participant; p01 weight fixed at 100.0 for long stretches (rounding/heaping) —  Bland-Altman vs bioimpedance unavailable; assume ±0.5 kg instrument noise.

## 2B.6 Alcohol: frequency, volume proxy, temporal clustering

| participant | n_days | n_alcohol_yes | pct_yes | pct_weekend_Fri_Sat_Sun | by_weekday | glasses_mean |
|---|---|---|---|---|---|---|
| p01 | 109 | 0 | 0.00 | — | {} | 8.11 |
| p03 | 117 | 48 | 41.00 | 47.9 | {'Friday': 8, 'Sunday': 8, 'Wednesday': 7, 'Saturday': 7, 'Thursday': 7, 'Monday': 6, 'Tuesday': 5} | 6.21 |
| p05 | 126 | 27 | 21.40 | 63.0 | {'Friday': 10, 'Saturday': 4, 'Thursday': 4, 'Monday': 3, 'Sunday': 3, 'Tuesday': 2, 'Wednesday': 1} | 9.98 |

- **Frequency**: p01 0/109 (complete abstinence — zero-variance predictor, drop from models); p03 48/117 (41%); p05 27/126 (21%). Unit volumes are NOT logged (binary Yes/No only) — dose-response is unidentifiable; use binary + previous-day + weekend-binge flags.
- **Clustering**: check `by_weekday` + Fri–Sun share columns for post-match weekend pattern; p03's 41% rate with `Lunch, Evening` meal pattern suggests evening social drinking — join with wellness-next-day (sleep_quality/readiness dip) for effect estimation.
