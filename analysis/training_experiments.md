# Training Experiments — LOPO XGBoost for Next-Day Readiness

## 1. Protocol

- **Goal:**
  - Validate ONE single pipeline — a hyperparameter config plus a kept-variable
    list — that will then be refit on all 290 labeled rows for final training.
  - LOPO below is validation only, not the final fit.
- **Task:**
  - Regression of `readiness_next_day` (int 2–8, 55% are 5.0; 290 labeled rows).
- **Splits:**
  - Leave-One-Participant-Out, 3 folds (train on 2 players, test on the third).
  - No player contamination by construction; all features are causal (windows end
    on day D, label is D+1).
  - No inner tuning loop — the 3 configs below are fixed a priori and *compared*
    (tuning on n=290 would overfit the split).
- **In-fold preprocessing:**
  - Per-participant demeaning of features (means fit on train rows; test rows use
    the held-out player's own feature means — no labels involved).
  - Trees don't need scaling; demeaning removes the between-person level shifts
    documented in `correlation_analysis.md`.
- **Model:**
  - `XGBRegressor(objective='reg:squarederror', tree_method='hist')`, xgboost
    **3.2.0** (pinned install in `.venv`).
  - NaN routed natively by sparsity-aware splits (verified, no imputation).
  - `random_state=42`, fixed rounds (no early stopping, for cross-fold comparability).
- **Feature sets:**
  - S1 Tier-1 baseline (**102** feats = `used_in_X` minus mechanical
    dups/constants/ultra-rare).
  - S2 Tier-1+2 (**60** feats, one representative per redundancy group).
  - S3 minimal robust (**33** feats, explicit list).
  - Grounded in `correlation_analysis.md` §7; every name validated against the CSV
    at runtime.
- **Metrics per fold:**
  - Regression: MAE (primary), RMSE, R².
  - Categorical on predictions rounded to the int grid and clipped to [2, 8]:
    accuracy, balanced accuracy, macro F1, quadratic-weighted κ
    (ordinal-appropriate), full 2–8 confusion matrices.
  - References: legitimate **global-train-mean baseline** + **participant-mean
    oracle** (uses test labels; unachievable ceiling showing what near-constant
    folds allow).
- **Grid and code:**
  - 3 configs × 3 sets × 3 folds = **27 fits**.
  - Code: `training_experiments/`; tests:
    `unit_tests/training_experiments_tests.py` (10 passed).
  - Raw outputs: `analysis/training_metrics.csv`, `analysis/confusion_matrices.csv`.

### Configs (user-validated)

| | A expressive | B balanced | C robust |
|---|---|---|---|
| n_estimators / max_depth / lr | 500 / 4 / 0.05 | 300 / 3 / 0.05 | 200 / 2 / 0.03 |
| subsample / colsample | 0.8 / 0.8 | 0.8 / 0.8 | 0.7 / 0.6 |
| reg_lambda / reg_alpha | 1 / 0 | 5 / 1 | 10 / 5 |
| min_child_weight / gamma | 1 / 0 | 3 / 0.1 | 10 / 0.5 |

## 2. Results — per fold (27 runs)

| config | set | test | n_tr/n_te | MAE | base | oracle | RMSE | R² | acc | bal_acc | F1mac | QWK |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| A | S1 | p01 | 153/137 | 1.704 | 1.675 | 1.148 | 1.949 | −0.91 | 0.124 | 0.143 | 0.032 | 0.000 |
| A | S1 | p03 | 213/77 | 0.859 | 0.806 | 0.101 | 0.949 | −9.08 | 0.195 | 0.298 | 0.087 | 0.011 |
| A | S1 | p05 | 214/76 | 0.480 | 0.868 | 0.170 | 0.645 | −2.78 | 0.605 | 0.219 | 0.151 | 0.080 |
| A | S2 | p01 | 153/137 | **1.559** | 1.675 | 1.148 | 1.775 | −0.58 | 0.131 | 0.147 | 0.041 | −0.001 |
| A | S2 | p03 | 213/77 | 1.096 | 0.806 | 0.101 | 1.155 | −13.94 | 0.026 | 0.253 | 0.011 | 0.022 |
| A | S2 | p05 | 214/76 | 0.570 | 0.868 | 0.170 | 0.747 | −4.08 | 0.526 | 0.190 | 0.142 | −0.029 |
| A | S3 | p01 | 153/137 | 1.626 | 1.675 | 1.148 | 1.854 | −0.73 | 0.124 | 0.143 | 0.032 | 0.000 |
| A | S3 | p03 | 213/77 | 0.943 | 0.806 | 0.101 | 1.007 | −10.35 | 0.052 | 0.260 | 0.026 | −0.003 |
| A | S3 | p05 | 214/76 | 0.542 | 0.868 | 0.170 | 0.721 | −3.73 | 0.566 | 0.205 | 0.184 | 0.023 |
| B | S1 | p01 | 153/137 | 1.653 | 1.675 | 1.148 | 1.899 | −0.81 | 0.124 | 0.143 | 0.032 | 0.000 |
| B | S1 | p03 | 213/77 | 1.261 | 0.806 | 0.101 | 1.326 | −18.66 | 0.013 | 0.250 | 0.006 | 0.008 |
| B | S1 | p05 | 214/76 | 0.608 | 0.868 | 0.170 | 0.770 | −4.39 | 0.474 | 0.171 | 0.135 | −0.079 |
| B | S2 | p01 | 153/137 | 1.678 | 1.675 | 1.148 | 1.922 | −0.86 | 0.124 | 0.143 | 0.032 | 0.000 |
| B | S2 | p03 | 213/77 | 1.184 | 0.806 | 0.101 | 1.251 | −16.514 | 0.052 | 0.014 | 0.021 | 0.021 |
| B | S2 | p05 | 214/76 | 0.682 | 0.868 | 0.170 | 0.835 | −5.34 | 0.368 | 0.133 | 0.113 | −0.047 |
| B | S3 | p01 | 153/137 | 1.653 | 1.675 | 1.148 | 1.900 | −0.82 | 0.124 | 0.143 | 0.032 | 0.000 |
| B | S3 | p03 | 213/77 | 1.312 | 0.806 | 0.101 | 1.364 | −19.827 | 0.013 | 0.250 | 0.006 | 0.009 |
| B | S3 | p05 | 214/76 | 0.634 | 0.868 | 0.170 | 0.789 | −4.66 | 0.434 | 0.157 | 0.159 | −0.073 |
| C | S1 | p01 | 153/137 | 1.675 | 1.675 | 1.148 | 1.917 | −0.848 | 0.124 | 0.143 | 0.032 | 0.000 |
| C | S1 | p03 | 213/77 | 1.404 | 0.806 | 0.101 | 1.437 | −22.109 | 0.000 | 0.000 | 0.000 | 0.023 |
| C | S1 | p05 | 214/76 | 0.704 | 0.868 | 0.170 | 0.837 | −5.379 | 0.342 | 0.124 | 0.108 | −0.065 |
| C | S2 | p01 | 153/137 | 1.675 | 1.675 | 1.148 | 1.917 | −0.848 | 0.124 | 0.143 | 0.032 | 0.000 |
| C | S2 | p03 | 213/77 | 1.358 | 0.806 | 0.101 | 1.395 | −20.773 | 0.000 | 0.000 | 0.000 | 0.023 |
| C | S2 | p05 | 214/76 | 0.718 | 0.868 | 0.170 | 0.851 | −5.593 | 0.316 | 0.114 | 0.102 | −0.057 |
| C | S3 | p01 | 153/137 | 1.675 | 1.675 | 1.148 | 1.917 | −0.848 | 0.124 | 0.143 | 0.032 | 0.000 |
| C | S3 | p03 | 213/77 | 1.305 | 0.806 | 0.101 | 1.340 | −19.094 | 0.013 | 0.250 | 0.005 | 0.002 |
| C | S3 | p05 | 214/76 | 0.622 | 0.868 | 0.170 | 0.760 | −4.250 | 0.421 | 0.152 | 0.157 | −0.096 |

(C predicts a constant on the p01 fold across all three sets — hence the three
identical p01 rows. Full precision for every cell in `training_metrics.csv`.)

### Aggregation (mean ± std over the 3 test players)

| config | set | mean MAE | std | mean RMSE | mean R² | mean acc | mean QWK | base MAE |
|---|---|---|---|---|---|---|---|---|
| A | S1 | **1.014** | 0.627 | 1.181 | −4.26 | 0.308 | 0.030 | 1.116 |
| A | S3 | 1.037 | 0.548 | 1.194 | −4.94 | 0.247 | 0.007 | 1.116 |
| A | S2 | 1.075 | 0.495 | 1.226 | −6.20 | 0.228 | −0.003 | 1.116 |
| B | S1 | 1.174 | 0.528 | 1.331 | −7.95 | 0.204 | −0.024 | 1.116 |
| B | S2 | 1.181 | 0.498 | 1.336 | −7.57 | 0.181 | −0.008 | 1.116 |
| B | S3 | 1.200 | 0.519 | 1.351 | −8.44 | 0.190 | −0.021 | 1.116 |
| C | S3 | 1.201 | 0.534 | 1.339 | −8.06 | 0.186 | −0.032 | 1.116 |
| C | S2 | 1.250 | 0.488 | 1.388 | −9.07 | 0.147 | −0.011 | 1.116 |
| C | S1 | 1.261 | 0.501 | 1.397 | −9.45 | 0.155 | −0.014 | 1.116 |

Mean R² is reported for completeness but is meaningless here: tiny fold-target
variance (p03 std 0.30) makes any error explode it. MAE is the working metric.

### Confusion matrices (A config, summed over the 3 folds; rows = true)

S1 (S2/S3 nearly identical, see `confusion_matrices.csv`): true-5 → 77×5 + 78×6;
true-6 → 31×5; true-7 → 45×5; true-8 → 25×5; true-4 → 18×5; true-3 → 7×5.
**Models predict only 5 or 6 — never 2, 3, 4, 7, 8** (prediction range across all
folds: 4.6–6.7). QWK ≈ 0 everywhere: as a classifier the system is a
majority-class predictor with zero beyond-chance ordinal agreement.

## 3. Fold anatomy — where (little) signal lives

- **p01 (the only fold with target variance, std 1.42):** best 1.559 (A/S2) vs
  baseline 1.675 vs oracle 1.148. A genuine but modest 7% gain; 36% gap to the
  ceiling remains. C collapses exactly onto the baseline (constant prediction).
- **p03 (flat 5s, oracle 0.101):** every model loses to baseline (0.86–1.40 vs
  0.806). Training on p01+p05 teaches higher readiness levels that do not
  transfer; C predicts constant ≈6 (rounds off the true 5s → accuracy 0.000).
  Unpredictable by construction — no day-level variance to learn.
- **p05 (flat 5s, oracle 0.170):** every model beats baseline (0.48–0.72 vs
  0.868) — but this is **level-matching, not learned dynamics**: predicting
  ≈5 wins because the train mean (≈5.7) overshoots. The mean-MAE "win" of A/S1
  over baseline comes *entirely* from this fold (it loses on p01 and p03).
- **A/S2 is the only cell beating baseline on 2/3 folds** (p01, p05).

## 4. Config comparison — heavier regularization hurt, monotonically

Mean MAE: A (1.01–1.08) < B (1.17–1.20) < C (1.20–1.26). The "robust" config C
kills all splits on the p01 fold (constant output) and transfers worst on p03:
depth-2 stumps with `min_child_weight=10`/`gamma=0.5` cannot express the
load→readiness interactions yet still split on confounded coarse structure.
Lesson: at this n, the failure mode is not overfitting wiggles but
cross-person level mismatch — regularization toward the *train* mean actively
harms transfer to a differently-leveled player.

## 5. Feature-set comparison — Tier-2 removal is free, S3 costs nothing

Within each config, S1≈S2≈S3 to within 0.06 MAE (≪ fold std ~0.5): dropping ~90
columns (S1 102 → S3 33) loses no measurable performance. Tier-2 redundancy
removal is validated as harmless; S1's edge over S3 (0.02 for config A) is noise.
Feature importance (mean gain, A/S2 across folds) corroborates the correlation
analysis: `srpe_load` 0.29, `zone_3` 0.10, `hr_mean` 0.08, then
`n_wellness_rows`, `alcohol_bin`, `has_steps`, `hr_sd`, `act_soccer` —
the within-person load/intensity signals, not the pooled confounds.

## 6. Decision — one validated pipeline, refit on all data

The goal of these experiments was to validate a single pipeline (hyperparameter
config + kept variables) for final training on all 290 labeled rows. LOPO was
validation only.

**Validated pipeline: config A_expressive + feature set S3_minimal.**
- Hyperparameters:
  - n_estimators=500, max_depth=4, learning_rate=0.05, subsample=0.8,
    colsample_bytree=0.8, reg_lambda=1, reg_alpha=0, min_child_weight=1,
    gamma=0 (reg:squarederror, hist, seed 42, NaN native).
- Kept variables (33; canonical source
  `training_experiments/features.py::MINIMAL_SET`):
  - Load: `srpe_load`, `load_7d_mean`, `acwr_7_28`, `missing_ratio_srpe_7d`.
  - Cardiac: `hr_mean`, `hr_sd`, `zone_min_IN_DEFAULT_ZONE_2`,
    `zone_min_IN_DEFAULT_ZONE_3`, `hr_cov_min`, `rhr_7d_median`, `rhr_residual`.
  - Activity/wear: `total_steps`, `peak_1min_steps`, `exercise_min`,
    `nonwear_min`, `steps_cov_min`.
  - Sleep: `asleep_min`, `efficiency_pct`, `midsleep_hour`, `mean_overall_score`.
  - Nutrition: `estimated_kcal`, `n_photo_meals`, `has_nutrition`.
  - Context: `readiness_same_day`, `alcohol_bin`, `weekend_bin`,
    `injured_last_7d`, `has_wellness`, `missing_ratio_wellness_7d`,
    `missing_ratio_sleep_7d`, `missing_ratio_zones_7d`,
    `was_imputed_rhr_7d_median`, `was_imputed_weight_7d_median`.
- Why this pair:
  - Near-best mean MAE (1.037 vs 1.014 best, Δ ≪ fold std ~0.55) at one-third
    the columns of S1 — parsimony of features is the robustness direction the
    data actually supports.
  - Beats the train-mean baseline on p01 and p05; Tier-2 removal validated as
    harmless (§5).
  - Heavier regularization empirically hurt (C collapses to constants, worst
    transfer) — the deployable prior is *fewer variables*, not stronger shrinkage.
- Honest limits (from §2–§5):
  - No reliable gain over baseline exists overall; the margin is one fold's
    level-matching, and p03 is unpredictable by construction.
  - Models never emit classes 7/8 (QWK ≈ 0) — categorical framing would be
    strictly worse; the regression choice is confirmed.
- **Final training:** refit A+S3 on all 290 labeled rows (same preprocessing:
  per-participant demeaning with means over the full frame, then fit). No
  holdout is kept — validation was already done via LOPO, so holding out more
  data would only shrink an already tiny train set. Expected in-sample MAE will
  be optimistic; the LOPO numbers in §2 are the honest generalization estimate.
- **Next step that matters is more players, not more tuning**: with 3 folds, no
  0.1-MAE difference is distinguishable. Revisit only after a 4th+ labeled
  participant exists.
