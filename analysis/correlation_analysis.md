# Correlation & Redundancy Analysis — training_dataset.csv

**Objective.** Understand how the numeric variables link to each other in order to
select and drop variables for a more robust readiness estimator.
**Data snapshot.** 456 rows (3 participants × 152 days, 2019-11-01 → 2020-03-31),
120 numeric modeling features (+ label `readiness_next_day`, 290 labeled rows).
Script: `analysis/correlation_analysis.py` (run: `.venv/bin/python
analysis/correlation_analysis.py`). Artifacts (§7) are CSVs in `analysis/`
(no plotting library is installed, so everything is tabular).

**Headline result.** The dataset has two dominant structures that must drive every
modeling decision: **(1) massive deterministic redundancy** (24 exact/near-exact
duplicate groups — VIF is literally infinite for 15+ columns), and **(2) severe
participant confounding** — most pooled correlations are between-person level
shifts (p01: high steps/coverage/readiness, low RHR; p03/p05 the reverse), not
day-to-day effects. Within participants, the coherent signal is: **high load /
high intensity → lower next-day readiness** (sRPE load −0.63, HR-zone-2 −0.55,
HR mean −0.45 within-person).

---

## 1. Methods (brief)

- **Pearson r** — linear association between two variables (−1…1). Computed
  pairwise-complete (each pair uses only rows where both are observed).
- **Spearman ρ** — Pearson on ranks; captures any monotonic link and resists
  outliers. Pearson≫Spearman gaps flag outlier-driven links.
- **Pairwise-N + p-values** — every r is reported with its N, because coverage
  varies enormously here (macros N=158, HR N≈297, steps N=456). A p-value on
  N=456 means little next to one on N=115; with ~7,140 tested pairs, expect
  false positives — judge by |r| + N + mechanism, not p.
- **Hierarchical clustering on 1−|ρ|** — groups variables that move together
  (average linkage, flat cuts at |ρ|≥0.8/0.9). Unknown pairs (NaN) treated as
  uncorrelated.
- **VIF (variance inflation factor)** — VIFⱼ = 1/(1−R²ⱼ): factor by which the
  variance of coefficient j is inflated by collinearity with the rest. >10 =
  severe, >5 = moderate. Requires complete data → computed on high-coverage
  complete-case subsets (documented limitation, §3).
- **Label relevance** — Pearson/Spearman of each feature vs `readiness_next_day`
  (290 labeled rows) + **mutual information** (kNN-based, captures nonlinear
  dependence; needs complete data → median-imputed, approximation flagged).
- **Pooled vs within-participant r** — the same Pearson after subtracting each
  participant's mean. Large gaps = participant confounding (between-person
  level differences masquerading as day-level effects).
- **Variance/missingness screens** — zero-variance columns break Pearson and
  carry no signal; ultra-rare flags memorize single participants.

**Caveats.** Daily time series ⇒ autocorrelation inflates rolling-vs-base links
by construction. Binary columns use point-biserial r (= Pearson, fine). `dow`
is cyclic (0…6 linear coding is meaningless — §5). MI was computed on pooled,
median-imputed data, so it inherits participant confounding.

---

## 2. Exact duplicates — drop one side, no information lost (|r| = 1.0, N = 456)

| Pair / group | r | Mechanism |
|---|---|---|
| `nonwear_min` / `nonwear_hours` | 1.00 | deterministic ÷60 |
| `load_7d_sum` / `load_7d_mean` | 1.00 | deterministic ÷7 |
| `zones_available` / `has_zones` | 1.00 | same flag, two names |
| `has_sleep_record` / `has_sleep` / `n_nights` | 1.00 | max 1 night/day ⇒ count ≡ flags |
| `has_nutrition` / `nutrition_kcal_available` | 1.00 | estimate exists ⟺ food photo exists |
| `act_team` / `act_soccer` | 1.00 | same 11 p01 days |
| `zone_min_IN_DEFAULT_ZONE_3` / `time_ge85_min` | 1.00 | same quantity, two names |
| `total_distance_cm` / `total_distance_m` | 1.00 | ÷100 (`_m` already `used_in_X=0`) |
| statics `age/height_cm/max_hr/stride_*` | ±1.00 | participant constants (3 people ⇒ any two statics are perfectly linear; N=304 for strides — p03 missing) |

VIF confirms: `inf` for `act_team`, `act_soccer`, `zones_available`, `has_zones`,
`has_sleep_record`, `n_nights`, `has_sleep`, `has_nutrition`,
`nutrition_kcal_available`, all three `inj_*` dummies, `is_injured_day`,
`load_7d_sum/mean`, `nonwear_min/hours`, plus all statics.

## 3. Redundancy groups (|Spearman| ≥ 0.9, average linkage)

Each group needs at most one or two survivors (§6):

- **Activity volume:** `total_steps / total_distance_cm / total_kcal` (0.99/0.96).
  Steps and distance are the same sensor; kcal is gap-filled but captures
  non-step expenditure (bike).
- **sRPE:** `srpe_load / srpe_n_sessions` (joins at 0.8) + `load_7d_sum/mean/strain`
  + `missing_ratio_srpe_7d/monotony_7d` (−0.98! monotony is NaN exactly when no
  sessions exist — mechanical, and 59% missing).
- **HR coverage:** `hr_n_samples / hr_cov_min` (0.996); `has_hr` joins at 0.8.
- **Wear:** `nonwear_min/hours` (+ `has_nonwear`, + `has_hr`/`nonwear_is_upper_bound`
  at 0.8 — wear variables are entangled with *who* (p03) and *whether HR exists*).
- **Zones:** `trimp_edwards / zone_min_IN_DEFAULT_ZONE_1` (0.8); zone-3 ≡ time≥85%.
- **RHR:** `rhr_raw / rhr_7d_median` (0.96) — and `height_cm` joins at 0.9
  (between-person RHR baselines: 52/56/64 bpm).
- **Weight:** `weight_raw / weight_7d_median` (0.998).
- **Sleep architecture:** `asleep_min / time_in_bed_min` (0.99);
  `deep_min / deep_pct / mean_deep_sleep_in_minutes` (0.999 — same Fitbit source twice);
  `rem_min / rem_pct / mean_composition_score` (0.8).
- **Photos:** `n_photos / n_food_photos / n_photo_meals` (0.99+ — only 5 non-food
  captures in 643); **macros** `estimated_kcal / fat_g / protein_g` (0.9, carbs
  joins at 0.8 — photographed meals scale together).
- **Rolling twins:** `total_steps_mean_7d / median_7d` (0.96),
  `exercise_min_mean_7d / median_7d`; `exercise_min / n_exercise_sessions` (0.9).
- **Counts ≡ flags:** `n_wellness_rows / has_wellness` (0.96);
  `n_meals_logged / n_reporting_rows` (0.8); `inj_left_foot__minor / is_injured_day`.
- **Clock:** `midsleep_hour / offset_hour` (0.8); `dow / weekend_bin` (0.8, mechanical).

## 4. Participant confounding — the central warning

Pooled correlations are dominated by *who*, not by *day*. Participant means:

| | p01 | p03 | p05 |
|---|---|---|---|
| label readiness | **6.23** | 4.96 | 4.91 |
| total_steps | 12,607 | 4,301 | 10,790 |
| steps_cov_min | 1,438 | 349 | 732 |
| hr_mean | 64.2 | — | 74.3 |
| rhr | 52.3 | 56.4 | 64.3 |
| estimated_kcal | 1,768 | 862 | 963 |
| nonwear_min | 22 | 1,038 | 144 |

Consequences (pooled → within-participant Pearson):

| Variable | pooled r | within r | Reading |
|---|---|---|---|
| `steps_cov_min` | +0.49 | +0.05 | pure p01-has-full-coverage proxy |
| `rhr_7d_median` / `rhr_raw` | −0.44/−0.43 | −0.03/−0.04 | between-person baselines only |
| `height_cm`, `age`, strides | +0.48…+0.55 | undefined/0 | participant IDs in disguise |
| `nonwear_min`, `has_hr`, `missing_ratio_sleep_7d` | −0.32…+0.32 | ≈0 | p03-missingness proxies |
| `estimated_kcal`, macros | +0.24…+0.30 | −0.10…−0.12 | p01 eats more *and* reports higher |
| `light_pct`, `deep_min` | +0.28/−0.23 | −0.04/+0.06 | sleep-architecture ≠ readiness signal here |
| `zone_min_IN_DEFAULT_ZONE_2` | −0.32 (ρ≈0!) | **−0.55** | sign-flip Simpson case: p01 trains hardest *and* reports highest, hiding a real within-person fatigue effect |
| `srpe_load`, `srpe_n_sessions` | −0.35/−0.32 | **−0.63/−0.58** | within effect nearly 2× the pooled one |
| `load_7d_mean/sum` | +0.16 (!) | −0.33 | sign flip: chronic-load level marks p01 (fit, high readiness); day-to-day load depresses readiness |
| `total_steps`, `total_kcal`, `total_distance` | ≈0 | −0.25…−0.29 | pooled null hides a mild within-person fatigue effect |
| `readiness_same_day` | +0.39 | **+0.16** | day-to-day persistence is real but modest; pooled value is mostly "p01 answers 6–7, others answer 5" |

**Rule: never trust a pooled correlation in this dataset.** Model on
within-participant deviations (per-person z-scoring) or with participant
fixed effects, and validate leave-one-participant-out. Raw statics
(`age/height_cm/max_hr/strides`, plus `gender/chronotype` which are
constant male/A and already unusable, and `nonwear_is_upper_bound` which
*is* the p03 indicator) contribute zero within-person information — a model
can only use them to memorize participants.

## 5. Label relevance (within-person ranking, n in parentheses)

Strongest day-level signals, all physiologically coherent (load → fatigue):

1. `srpe_load` −0.63 (290), `srpe_n_sessions` −0.58 (290)
2. `zone_min_IN_DEFAULT_ZONE_2` −0.55, `zone_3`/`time_ge85` −0.51 (271)
3. `hr_sd` −0.50, `act_soccer`/`act_team` −0.49 (11 p01 match days), `hr_mean` −0.45 (209)
4. `act_running` −0.44, `act_individual` −0.42, `hr_peak` −0.40
5. `load_7d_mean/sum` −0.33, `readiness_same_day` +0.16 (229, weak persistence)

Notable non-findings: sleep stages/efficiency/onset (≈0 within), RHR residual
≈0, alcohol −0.07, macros ≈−0.10, `trimp_edwards` −0.11 (the zone detail beats
the single-number TRIMP), `mean_rpe` (n=33 — unusable), `dow`/`weekend_bin` ≈0
(Thursday dips to 4.93 pooled, noise-level).

Nonlinearity notes: `lag_days` Pearson −0.04 vs Spearman −0.37 pooled, but
within ≈0 — an outlier artifact (lags range −12.8…+31 days; **negative lags**,
submission *before* the log date, are a data-quality quirk worth a pipeline
assertion), not a real effect. `total_kcal` has high MI (0.22) with ~0 linear r
— MI was computed pooled/median-imputed, so treat as confounded, not as proof
of nonlinearity.

## 6. Coverage, variance & encoding notes

- **Structural missingness** (pairwise N is the real sample size): macros 158,
  HR ≈297 (p03: 0 days), RHR 339, weight 261, `mean_rpe` 33, `monotony/strain`
  146, `acwr` 216, `lag_days`/`alcohol`/`fluids` 217, sleep stages ~233–236.
  Complete-case modeling on the full set is impossible — keep Tier-2
  indicators and NaN-native models.
- **Zero variance:** `n_clipped_hr` (already dropped from modeling), `gender`,
  `chronotype` (constants — drop). **Single-event:** `n_deduped_min` (455 zeros,
  one DST day = 452 — audit flag, not a feature, drop).
- **Ultra-rare:** `inj_*` dummies (1/9/1 events), `is_injured_day` (11 days, 10
 × p05), `act_endurance` (4 d), `act_strength` (2 d), `is_classic` (5 nights),
  `n_naps` (13) — memorize participants/days; drop or collapse.
- **`dow` raw is meaningless** (cyclic) — drop it, keep `weekend_bin` (or add
  sin/cos encoding if weekday effects are pursued).
- `n_nights` maxes at 1 ⇒ count ≡ flag (drop the two `has_sleep*` flags).

## 7. Recommendations

### Tier 1 — drop always (mechanical; zero information loss)

`total_distance_m` (done), `nonwear_hours`, `load_7d_sum`, `has_zones`,
`has_sleep`, `has_sleep_record`, `nutrition_kcal_available` (≡ `has_nutrition`),
`time_ge85_min`, `act_team` (≡ soccer days), `gender`, `chronotype`,
`n_deduped_min`, `n_clipped_hr`, `mean_deep_sleep_in_minutes` (≡ `deep_min`),
`has_hr` (≡ coverage>0), `hr_n_samples` (≡ `hr_cov_min`), `nonwear_is_upper_bound`
(p03 indicator), `has_nonwear` (≡ `nonwear_min`>0), `has_wellness` (≡ row count),
`n_reporting_rows` (≡ meals logged), `is_classic` (5 nights — keep as audit flag
only), `mean_rpe` (n=33).

### Tier 2 — drop for linear/unregularized models (keep one representative per group)

- Activity: keep `total_steps` + `total_kcal`, drop `total_distance_cm`.
- Slow signals: keep `weight_7d_median` + `weight_residual`, drop `weight_raw`;
  same for RHR (`rhr_7d_median` + `rhr_residual`, drop `rhr_raw`).
- Load: keep `srpe_load` + `load_7d_mean` + `acwr_7_28` +
  `missing_ratio_srpe_7d`; drop `monotony_7d`, `strain_7d`, `srpe_n_sessions`.
- HR/zones: keep `hr_mean`, `hr_sd`, `hr_peak`, `zone_2`, `zone_3`; drop
  `zone_below`, `zone_1`, `trimp_edwards`, `mean_conf`.
- Sleep: keep `asleep_min` (drop `time_in_bed_min`), `efficiency_pct`,
  `midsleep_hour` (drop `onset/offset_hour`), `mean_overall_score` +
  `mean_restlessness` (drop subscores), `n_naps`; drop all four `*_pct`
  (compositional with minutes).
- Photos/macros: keep `n_photo_meals` + `estimated_kcal` (+`has_nutrition`);
  drop `n_photos`, `n_food_photos`, `protein/carbs/fat_g`.
- Rolling twins: keep `*_mean_7d`, drop `*_median_7d`; keep `*_std_7d`.
- Activities: keep `act_running`, `act_soccer`, `act_walk`, `act_bike`; drop
  `act_individual`, `act_endurance`, `act_strength`.
- Injury: collapse to `injured_last_7d` only (drop `is_injured_day`,
  `n_injury_reports`, all `inj_*`).
- Time: drop raw `dow`, keep `weekend_bin`. Drop `lag_days` (within ≈ 0 +
  negative-lag quirk — fix pipeline assertion instead).
- Statics: drop `age/height_cm/max_hr/strides` from X (use participant
  fixed effects instead — §8).

### Tier 3 — keep, with eyes open

`readiness_same_day` (weak but legitimate lagged feature), `peak_1min_steps`,
`exercise_min` + `exercise_min_std_7d`, `submission_hour`/`delayed_flag`,
`fluids_glasses`, `alcohol_bin`, `weight/fluid` + all five `missing_ratio_*`,
both `was_imputed_*` flags, `steps_cov_min` + `hr_cov_min` (coverage gates).

### Suggested minimal robust set (~20 features)

`readiness_same_day`, `srpe_load`, `load_7d_mean`, `acwr_7_28`,
`missing_ratio_srpe_7d`, `hr_mean`, `hr_sd`, `zone_2`, `zone_3`, `hr_cov_min`,
`rhr_7d_median`, `rhr_residual`, `nonwear_min`, `total_steps`, `peak_1min_steps`,
`exercise_min`, `asleep_min`, `efficiency_pct`, `midsleep_hour`,
`mean_overall_score`, `estimated_kcal`, `n_photo_meals`, `has_nutrition`,
`alcohol_bin`, `weekend_bin`, `injured_last_7d`, coverage gates
(`steps_cov_min`, `has_wellness`, `missing_ratio_wellness_7d`,
`missing_ratio_sleep_7d`, `missing_ratio_zones_7d`) + `was_imputed_*` —
all within-participant standardized.

## 8. Modeling protocol notes

With 290 labeled rows and ~120 raw features, reduction is mandatory, not
optional. Baseline against the participant-mean predictor (most pooled
"signal" is just that); use participant-aware validation
(leave-one-participant-out outer, temporal inner, no shuffling); prefer
within-person z-features + Ridge/Lasso (which performs selection itself) or
gradient boosting with native NaN + missingness indicators. Do not train the
injury target as a balanced classifier (11 events, p05-clustered).

## 9. Artifacts (all in `analysis/`)

`correlation_analysis.py` (re-runnable), `correlation_matrix_pearson.csv`,
`correlation_matrix_spearman.csv`, `correlation_pvalues.csv`,
`correlation_pair_n.csv`, `within_participant_pearson.csv`, `strong_pairs.csv`
(|r|≥0.6, 381 pairs), `redundancy_groups.csv` (24 @0.9, 27 @0.8),
`vif_core_cov100.csv`, `vif_core_cov95.csv`, `label_relevance.csv` (pooled +
MI), `label_relevance_within.csv` (pooled vs within per feature).
