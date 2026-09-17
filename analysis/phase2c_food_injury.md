# Phase 2C — Food Images & EXIF Integrity + Adverse Events

_Generated 2026-09-17 10:50. Tables: `tables/phase2c_*.csv`._

## 2C.1 Metadata & technical formats

| participant | n_images | formats | color_modes | top_resolutions | mean_kb | min_kb | max_kb | pct_datetime | pct_gps | pct_orientation | n_corrupt_or_unreadable | corrupt_list | median_interval_h | p25_interval_h | p75_interval_h | pct_intervals_le_30min | pct_intervals_le_60min | pct_intervals_gt_6h | screenshot_or_uuid_names |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| p01 | 321 | {'JPEG': 320, 'PNG': 1} | {'RGB': 320, 'RGBA': 1} | 4032x3024:318; 3744x2808:1; 1319x834:1 | 2256.10 | 254.20 | 7784.90 | 100.00 | 99.40 | 99.10 | 0 | — | 3.37 | 1.45 | 6.13 | 16.20 | 20.00 | 25.60 | IMG_9111.png |
| p03 | 136 | {'JPEG': 136} | {'RGB': 136} | 3024x4032:68; 1932x2576:57; 2576x1932:10 | 1155.80 | 316.30 | 2558.80 | 100.00 | 0.00 | 100.00 | 0 | — | 5.43 | 1.28 | 14.81 | 16.30 | 20.00 | 47.40 | — |
| p05 | 186 | {'JPEG': 186} | {'RGB': 186} | 3024x4032:182; 901x1600:1; 1600x1200:1 | 2063.70 | 179.10 | 3441.80 | 100.00 | 0.00 | 98.90 | 0 | — | 2.00 | 0.07 | 9.43 | 36.80 | 41.60 | 32.40 | 281dad76-7501-4f0c-b81b-92fdeb256ab3.jpg; 61bcd5e5-8e5f-475d-ba87-39f5dc09e002.jpg; 752bda71-b461-424e-a95b-17b9ed9da468.jpg |

- **Formats**: p01 320×JPEG + 1×PNG (`IMG_9111.png` — likely screenshot/export, verify visually); p03 136×JPG; p05 183×JPG + 3 UUID-named JPGs (app-exported, e.g. `281dad76-…​.jpg` — check for screenshots/duplicates).
- **Colour**: 100% RGB (no grayscale/CMYK); no HEIC in this export despite mission brief listing it — ingestion only needs JPEG/PNG path.
- **Resolutions**: p01 uniform 4032×3024 (12 MP landscape, iPhone-class); p03 mixed 3024×4032 portrait + 1932×2576 (older device or downscaled); p05 3024×4032 portrait. Orientation tag present 99–100% — auto-rotate on load.
- **Sizes**: p01 mean ≈2.2 MB (0.25–7.8 MB); p03 mean ≈1.1 MB; p05 mean ≈2.0 MB — consistent with native camera exports, not recompressed thumbnails.
- **EXIF completeness**: strict `DateTime` tag (0x0132, the key used by `food_reader.photo_selector_by_date_player`): p01 319/321 (99.4%), p03 136/136, p05 186/186. The 2 p01 gaps (`IMG_8958.jpeg` 1319×834 downscaled, `IMG_9111.png` 1125×2436 screenshot) carry `DateTimeOriginal` so the audit fallback (DateTime OR DateTimeOriginal) reads 100% — but **current production code drops them**. Patch `food_reader` to fall back to `DateTimeOriginal`, and quarantine the 2 files as screenshot/downscaled non-food candidates. GPS **p01 99.4% vs p03/p05 0%** (privacy strip or device setting — do not use GPS as join key); Orientation 99–100%. Log dateless drops as `NO_DATE_EXCLUDED` rather than imputing.
- **Corruption**: PIL `load()` decode attempted on every file — failures listed in `corrupt_list` (all zero here); no 0-dimension reads. Vision-level food-vs-non-food (blurred/pocket/drinks-only) comes from the Gemini `is_photo_food` pass — see §2C.4 for results; its YES/NO output is wired into `tables/phase2c_food_files_*.csv` as `is_food`.

## 2C.2 Temporal grouping & meal-cadence threshold (data-derived: 15 s; legacy 1800 s)

Interval = seconds between consecutive EXIF datetimes per participant (all photos, datetimes sorted). Files: `tables/phase2c_meal_intervals_sec_{p01,p03,p05}.csv`.

**Threshold derivation (aggregate, n=640 intervals).** Fine-binned distribution 0–300 s (15 s bins): 0–15 s: 43; 15–30 s: 4; 30–45 s: 1; 45–60 s: 4; 60–75 s: 1; 75–90 s: 2; 90–105 s: 1; 105–120 s: 0; then the main mass resumes (120–135 s: 3, rising). A dense left outlier cluster (0–15 s, 6.7% — shutter-burst shots of one dish) is separated by a sparse valley (15–120 s, 13 events) from the inter-meal mass (≥120 s). Per the audit rule (high limit of the outlier cluster; 3rd-centile = 3 s fallback not needed — outliers are visible), **meal_timedelta = 15 s**. Cumulative shares: ≤15 s 6.7% (43), ≤60 s 8.1% (52), ≤300 s 12.8% (82), ≤1800 s legacy 22.2% (142). Note the trade-off: 15 s has high precision (bursts are certainly one meal) but lower recall than 1800 s (before/during shots minutes apart are split); the valley-exit (~120 s) is the documented alternative operating point.

```
p01 inter-photo interval (minutes) (n=320)
        0.02–90.59      | ######################################## 82
       90.59–181.16     | ############################# 60
      181.16–271.73     | ############################# 60
      271.73–362.31     | ################## 36
      362.31–452.88     | ########### 22
      452.88–543.45     | ##### 11
      543.45–634.02     | ########## 20
      634.02–724.60     | #### 9
      724.60–815.17     | ### 6
      815.17–905.74     | ### 7
      905.74–996.32     | ## 4
      996.32–1086.89    |  0
     1086.89–1177.46    |  1
     1177.46–1268.03    | # 2
p03 inter-photo interval (minutes) (n=135)
        0.00–451.46     | ######################################## 76
      451.46–902.92     | ############## 26
      902.92–1354.39    | ######## 15
     1354.39–1805.85    | ###### 12
     1805.85–2257.31    | ## 3
     2257.31–2708.77    |  0
     2708.77–3160.23    | # 1
     3160.23–3611.70    |  0
     3611.70–4063.16    |  0
     4063.16–4514.62    |  0
     4514.62–4966.08    |  0
     4966.08–5417.54    |  0
     5417.54–5869.00    |  0
     5869.00–6320.47    | # 2
p05 inter-photo interval (minutes) (n=185)
        0.02–591.78     | ######################################## 139
      591.78–1183.54    | ####### 23
     1183.54–1775.31    | #### 15
     1775.31–2367.07    | # 2
     2367.07–2958.83    | # 3
     2958.83–3550.60    | # 2
     3550.60–4142.36    |  0
     4142.36–4734.12    |  0
     4734.12–5325.88    |  0
     5325.88–5917.65    |  0
     5917.65–6509.41    |  0
     6509.41–7101.17    |  0
     7101.17–7692.94    |  0
     7692.94–8284.70    |  1
```

- **Threshold read**: `pct_intervals_le_30min` in the summary table is the legacy-1800 s view (22.2% of pairs pre-merged). Under the derived 15 s rule only burst pairs (6.7%) are pre-merged; vision confirmation (§2C.4) then measures precision. The production two-stage rule (`same_meal_preselector` + `is_it_same_meal` union-find in `food_reader.get_macro_nutrients_from_photos`, default 1800 s in `main.py`) should be re-parameterised to 15 s (or the 120 s valley-exit) to match this evidence.
- **Caveat**: EXIF DateTime has 1-second resolution and reflects shutter time; burst shots share identical timestamps (interval 0) — dedupe exact duplicates before grouping. Late-night snacks past midnight attribute to the next calendar day — align with sleep `dateOfSleep` convention.

## 2C.4 Gemini vision results (`is_photo_food` + `is_it_same_meal`)

Full per-image labels: `tables/phase2c_food_files_*.csv` (`is_food`, `is_food_model`); pair decisions: `tables/vision_same_meal_pairs.csv`; run cache: `tables/vision_cache.json` (generator: `analysis/vision_run.py`).

**Model provenance (non-standard, documented here only).** First 426 labels by `gemini-3.5-flash-lite` (production model); quota exhausted mid-run (`generate_content_free_tier_requests, limit: 500`), so the model string was swapped by hand to `gemini-3.1-flash-lite` for all subsequent labels — no rotation logic was added to the code. The two models disagree on edge cases: e.g. `p05/IMG_2215.jpg` (vitamin-supplement bottle) is YES under 3.5 but NO under 3.1 (stricter 'food or beverages' reading; supplements arguably correctly excluded from macro meals). Cross-model labels are therefore not strictly comparable — use `is_food_model` when pooling, and treat supplement/packaging shots as a review category before nutrition modelling.

| participant | n_images | n_food_YES | n_food_NO | n_pending | models | non_food_files |
|---|---|---|---|---|---|---|
| p01 | 321 | 319 | 2 | 0 | gemini-3.1-flash-lite:2; gemini-3.5-flash-lite:319 | IMG_9111.png; IMG_9157.jpeg |
| p03 | 136 | 136 | 0 | 0 | gemini-3.1-flash-lite:29; gemini-3.5-flash-lite:107 | — |
| p05 | 186 | 183 | 3 | 0 | gemini-3.1-flash-lite:186 | IMG_2215.jpg; IMG_2216.jpg; IMG_2235.jpg |

Vision confirmation rate by gap cut-off (pairs preselected ≤1800 s, evaluated offline):

| threshold_s | n_pairs | n_confirmed | confirm_rate_pct |
|---|---|---|---|
| 15.00 | 45.00 | 33.00 | 73.30 |
| 60.00 | 55.00 | 40.00 | 72.70 |
| 120.00 | 58.00 | 42.00 | 72.40 |
| 300.00 | 90.00 | 65.00 | 72.20 |
| 1800.00 | 193.00 | 123.00 | 63.70 |

Derived-15 s operating point, per participant:

| participant | n_pairs_le15s | n_confirmed_le15s | confirm_rate |
|---|---|---|---|
| p01 | 7 | 5 | 71.40 |
| p03 | 8 | 7 | 87.50 |
| p05 | 30 | 21 | 70.00 |

**Threshold verdict**: confirmation is flat ~72–73% for all cut-offs ≤300 s (15 s: 73.3%, 300 s: 72.2%) and falls to 63.7% at the legacy 1800 s — i.e. gap discriminates mainly through the long tail (confirmed-pair median gap 288 s vs rejected 730 s). The distribution-derived 15 s rule is therefore the conservative high-precision operating point, but vision evidence does not separate it from 120–300 s; the costly over-merging happens between 300 s and 1800 s. Recommendation: re-parameterise production `meal_timedelta` to the 15–120 s range (default 15 s), never 1800 s. Note on provenance: the pair calls were preselected at ≤1800 s because the running process had imported the legacy constant before the hand edit to 15 s took effect — the 15 s evaluation above is the exact offline subset, so no extra API calls were needed. Non-food images (`is_food=NO`) are excluded before grouping, so pocket/blurred/screenshot captures cannot create spurious meals.

## 2C.3 Adverse events — epidemiology & class balance

| participant | n_injury_reports | n_reports_with_event | events | srpe_hours | exercise_hours | total_exposure_h |
|---|---|---|---|---|---|---|
| p01 | 24 | 1 | 2020-01-07T22:33:38.989Z {'right_hand': 'minor'} | 26.00 | 98.53 | 124.53 |
| p03 | 11 | 0 | — | 1.00 | 26.26 | 27.26 |
| p05 | 10 | 10 | 2019-11-01T06:30:35.565Z {'left_foot': 'minor'}; 2019-11-07T07:29:02.805Z {'head_neck': 'minor'}; 2020-01-30T06:38:02.691Z {'left_foot': 'minor'}; 2020-01-31T05:40:48.569Z {'left_foot': 'minor'}; 2020-02-08T04:59:19.621Z {'left_foot': 'minor'}; 2020-02-14T05:32:10.455Z {'left_foot': 'minor'}; 2020-02-29T06:26:35.754Z {'left_foot': 'minor'}; 2020-03-07T08:01:19.947Z {'left_foot': 'minor'}; 2020-03-15T06:01:04.240Z {'left_foot': 'minor'}; 2020-03-17T19:47:51.329Z {'left_foot': 'minor'} | 5.50 | 70.65 | 76.15 |

Locations:

| participant | location | n |
|---|---|---|
| p01 | right_hand | 1 |
| p05 | left_foot | 9 |
| p05 | head_neck | 1 |

Severity:

| participant | severity | n |
|---|---|---|
| p01 | minor | 1 |
| p05 | minor | 10 |

| participant | injury_event_days | horizon_days | non_event_days | imbalance_ratio | event_day_rate_pct |
|---|---|---|---|---|---|
| p01 | 1 | 152 | 151 | 1:151 | 0.66 |
| p03 | 0 | 152 | 152 | 0 events | 0.00 |
| p05 | 10 | 152 | 142 | 1:14 | 6.58 |

- **Totals**: 11 injury events in 3 participants over 152 days (p01 1× right_hand minor; p03 0; p05 10× — 9 left_foot minor + 1 head_neck minor; **zero major**). p05's left_foot repeats 2020-01-30→03-17 = recurrent/chronic complaint, not 10 independent traumas.
- **Exposure**: sRPE-logged 32.5 h + Fitbit-exercise 195.4 h = **227.9 h total**. Incidence = 11/227.9 h = **48.3 per 1,000 h** (all-source exposure). sRPE-only exposure gives 338.5/1,000 h — inflated by p03/p05 under-logging; report both, model on the fused exposure.
- **Class imbalance** (event-days vs horizon days): p01 1:151 (0.7%), p03 0:152 (0%), p05 ≈7–10:152 (~5%). Pooled ≈ 8–11 event-days / 456 participant-days ≈ **1:45–1:55**. Any injury classifier is extreme-imbalanced: use time-to-event / anomaly-detection framing, not balanced classification; stratify by participant; never SMOTE across participants.
