# Phase 3 — Pre-processing Design & Modelling Specification

_Generated 2026-09-17 10:50. Grounded in Phase 1/2 tables in `analysis/tables/`._

## 3.1 Design principles (from audit evidence)

1. **Participant-stratified everything.** Baselines differ by ~10 bpm HR, 18 kg weight, disjoint chronotypes; pool only residuals/z-scores, never raw values.
2. **Missingness is structural, not MCAR.** p03 lacks HR entirely; p05 RHR starts 2019-12-28; p03 wellness 50%; sRPE sparse for p03/p05 — each feature needs a defined fallback (NaN + missingness indicator), never silent imputation.
3. **Timestamps are heterogeneous.** Minute `YYYY-MM-DD HH:MM:SS`, ISO-UTC with ms, DD/MM/YYYY dayfirst, EXIF `YYYY:MM:DD`, sleep morning-attribution (`dateOfSleep`) vs start-time filtering — all joins go through `standardize_date` + explicit day-attribution rules (§3.3).
4. **Sentinels ≠ measurements.** RHR `0.0`, readiness/soreness `0` on 1–5 scales, `soreness_area=[]`, injury `{}`, duplicate DST zeros — map to NaN/False before statistics.

## 3.2 Cleaning checklist per source (implement in `src/data_handling/`)

| Source | Clean step | Rule |
|---|---|---|
| steps/distance | DST dedupe | sort by ts, `drop_duplicates('dateTime', keep='first')`; assert 1440/d max |
| steps/distance | sparse-gaps | reindex to full minute grid 2019-11-01→2020-03-31; missing → NaN + `is_missing_min` flag; zero-fill only for sum features with companion missingness covariate |
| calories | pass-through | keep as-is (gap-filled export); do not use for wear detection |
| HR | confidence filter | drop `confidence==0` (0.6–1.1%); keep 1–3 with `mean_conf` covariate; clip bpm to [30, 220] |
| HR | flatline flag | per-minute std==0 with n≥2 → `hr_flat_min` (charger artifact) |
| RHR | sentinel | `value<=0 \| date is null` → NaN; require ≥5 valid nights for baseline; no back-fill before 2019-12-28 for p05 |
| zones | missing days | keep NaN (do not zero-fill p03's 35 missing days); renormalise observed days to 1440 min |
| sleep | type branch | `stages` → full 4-stage split; `classic` → {asleep, restless, awake} only + `is_classic` flag; exclude `mainSleep=False` naps from nightly features (separate nap covariate) |
| sleep_score | join | left-join on logId==sleep_log_entry_id; restlessness ∈ [0.03, 0.20] clip |
| exercise | durations | `activeDuration ?? duration` ms→min; drop 0.03-min artifact bouts; keep `logType` + `activityName` strata |
| wellness | hour filter | flag `hour>=12` as delayed; 0 on 1–5 scale → NaN (p05); `soreness_area` parse list, `[]`→no-pain |
| srpe | load | `load=RPE×duration`; missing RPE/duration → NaN load (p05 2020-02-13 row); daily-load reindex with 0 + `n_sessions` count |
| injury | parse | `ast.literal_eval`, non-dict → {}; event = len>0; location+severity one-hots; recurrent p05 left_foot → episode ID, not 10 i.i.d. rows |
| reporting | dates | `date` dayfirst, `timestamp` submission; `lag_days=timestamp−date` feature; weight → 7-day median + residual; alcohol {Yes,No}→{1,0} + weekend flag |
| food images | EXIF | key on `DateTime` tag; dateless → quarantine list; auto-rotate by Orientation; drop GPS as feature (p03/p05 0%) |
| food images | vision | run `is_photo_food` → `is_food`; `same_meal_preselector(15 s, derived §2C.2)` + `is_it_same_meal` confirm; `helper_get_macro_nutrients_from_photos` per meal |
| overview | quirks | strip `male\xa0` whitespace; `november`/`injured` dates → NaT; p14 stride-run 11.3 → NaN; use MaxHR else 220−age |

## 3.3 Temporal alignment (daily modelling grain)

- **Day key**: calendar date `YYYY-MM-DD` (local, device time). Sleep night ending on D attributes to D (`dateOfSleep`), matching `aggregator.aggregate_sleep` lookback logic.
- **Minute → day**: steps/distance/calories sum; HR → mean/resting/peak/TRIMP + `hr_coverage_min`; zones → min/zone; exercise → Σactive min + session count.
- **Wellness (morning D)** predicts day-D load/sleep-next-night; **sRPE (end-time D)** attributes to D; **reporting lag** kept as covariate, values attribute to log `date`.
- **Food (Feb–Mar only)**: meal events group within 15 s (derived §2C.2; production default still 1800 s — re-parameterise) + vision confirm; daily nutrients Σkcal/protein/carbs/fat; outside Feb–Mar → `has_nutrition=0` + NaNs (do not zero-fill as 'fasted').
- **Master table**: one row per participant×day (3×152=456 rows): `[participant, date, n_*_coverage, feat_*, target_*]`. Coverage columns (`steps_cov_min`, `hr_cov_min`, `has_wellness`, `has_nutrition`) gate every model — see §3.5 masking.

## 3.4 Feature catalogue (v1, daily grain)

**Activity/load**: total_steps, peak_1min_steps, total_distance_m, total_kcal, exercise_min, n_sessions, activity mix, Edwards-TRIMP from zones, sRPE load, 7-day rolling load, monotony (7 d), strain, ACWR (7:28 d, p01 only stable).
**Cardiac**: RHR_7d_median + residual, HR mean/sd/peak, zone min (4) + % , time ≥85% max, HR recovery proxy (post-exercise 1-min drop where resolvable).
**Sleep**: asleep_min, time_in_bed, efficiency, deep/light/rem/wake min + %, WASO, sleep_onset/offset hour, midsleep, social jetlag (weekend−weekday midsleep), overall/composition/revitalization/duration scores, deep_min, restlessness, classic_flag.
**Subjective**: fatigue/mood/readiness/sleep_h/sleep_q/soreness/stress (raw + within-person z), soreness_any + n_zones, submission_hour + delayed_flag, reporting lag_days, weight_7d_median + residual, fluids, alcohol_bin + weekend_bin.
**Nutrition (Feb–Mar)**: n_meals_logged, n_photos, n_photo_meals, kcal/protein/carbs/fat, eating_window_h, last-meal→sleep latency.
**Targets** (pick one per experiment): next-day readiness; next-night sleep efficiency/deep%; injury-event-day (rare-event); sRPE load (regression, p01); weight residual drift.

## 3.5 Modelling specification

### A. Descriptive / unsupervised (run first)
- Mixed-effects baselines: `y ~ 1 + (1|participant)` for every candidate target to quantify ICC; proceed only if within-person variance justifies personalisation.
- Changepoint/anomaly scan on RHR + load + sleep efficiency (PELT/CUSUM per participant) — p05 recurrent foot injury is the validation case.

### B. Supervised (daily-grain, participant-aware)
- **Validation**: leave-one-participant-out (LOPO) outer + time-series split inner (no shuffling); report per-participant + pooled metrics. With n=3 participants, LOPO is the only honest generalisation estimate.
- **Models**: (i) elastic-net / Ridge on within-person z-features (interpretable baseline); (ii) gradient boosting (LightGBM) with `participant` categorical + missingness indicators; (iii) hierarchical Bayesian (partial pooling) if inference on small-n effects is needed. No deep sequence models as primary (456 rows insufficient); minute-level CNN/LSTM only as feature extractors pre-trained per signal.
- **Missingness handling**: forward-fill ≤2 d for slow signals (RHR, weight median) with `was_imputed` flag; no fill for zones/sRPE/nutrition — use indicator + model-native NaN (LightGBM) or median+indicator (linear). Mask Feb–Mar-only nutrition models to Feb–Mar (n≈3×55 observed food-days) or use two-stage (base model all-days + nutrition uplift on Feb–Mar).
- **Imbalance (injury)**: do NOT train a balanced classifier. Use (a) survival/time-to-event (Cox PH with time-varying load/sleep covariates), or (b) unsupervised anomaly score → precision@k on event-days. Report PR-AUC + lead-time (days of early warning), not accuracy. Collapse p05 recurrent episodes into one episode with duration to avoid label leakage.
- **Metrics**: readiness/sleep → MAE + R² vs participant-mean baseline; load → MAPE; injury → PR-AUC, recall@fixed false-alarm rate, median lead-time.
- **Leakage guards**: all rolling features strictly causal (ending D−1 for predicting D); standardise using train-fold statistics only; group folds by participant; submission-lag features allowed only if available at prediction time.

### C. Nutrition-vision sub-pipeline
- Stage 1 `is_photo_food` (precision-oriented; quarantine NOs for audit, do not delete). Stage 2 time-preselect (15 s derived, §2C.2) → Stage 3 `is_it_same_meal` confirm → Stage 4 macro estimate per meal. Sensitivity runs at the 120 s valley-exit and legacy 1800 s. Report photo→meal precision/recall on a 50-meal hand-labelled sample before trusting kcal totals.

## 3.6 Risks & stop-rules

- p03/p05 sRPE sparsity → load models will be p01-only unless Fitbit-TRIMP substitution validates (corr(sRPE, TRIMP) on p01 overlapping days ≥0.6 required).
- 456 rows / ~40 features → regularise aggressively; pre-register feature list; report shrinkage.
- p01 abstinence (alcohol variance 0) + zero major injuries → drop those predictors/targets rather than modelling constants.
- Food window Feb–Mar only → nutrition effects are short-horizon; do not extrapolate to Nov/Dec/Jan.
- DST duplicate + RHR sentinel + classic-type pitfalls above must have unit tests (see `unit_tests/`) before any modelling run.
