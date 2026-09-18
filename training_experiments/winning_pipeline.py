"""Winning pipeline (A_expressive + S3_minimal), refit on ALL labeled rows.

LOPO validation (analysis/training_experiments.md) selected config
A_expressive with the 33 S3_minimal features. This module reproduces that
exact pipeline end to end and persists every artifact needed to reuse it:

- final_training_dataset.csv : all 456 rows, keys + per-participant
  DEMEANED S3 features (the exact model input) + label + label_available.
- final_data_dictionary.csv  : explicit per-column documentation.
- winning_pipeline_model.ubj : XGBRegressor fitted on the 290 labeled rows.
- winning_pipeline_features.json : S3 column order + config name/params
  (required to align new data with the booster).
- winning_pipeline_demean_params.csv : per-participant feature means used
  for demeaning, plus a GLOBAL fallback row for unseen participants.

Demeaning uses feature values only (never labels): means are fit on the
290 labeled rows and applied to the full 456-row frame, mirroring the
in-fold procedure. NaNs pass through untouched for XGBoost's native
missing-value handling.

Usage: .venv/bin/python -m training_experiments.winning_pipeline
       [--out-dir output_dataset]
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from xgboost import XGBRegressor

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from training_experiments import config, data, features, metrics, model  # noqa: E402
from training_experiments.config import CONFIG_ORDER  # noqa: E402

WINNING_CONFIG = "A_expressive"
WINNING_SET = "S3_minimal"
KEY_COLS = ["participant_id", "date"]
LABEL_COLS = [data.LABEL, "label_available"]

# Explicit, plain-language documentation per output column: unit, source
# and preprocessing. Coverage counts are computed from the frame at write
# time (see write_final_dictionary).
COLUMN_DOCS = {
    "participant_id": ("str", "—", "study identifier",
                       "Row key. Three levels in this build (p01/p03/p05). "
                       "Used for LOPO splitting and per-participant demeaning; "
                       "never a model input.", "none", "key"),
    "date": ("str", "calendar day", "daily grid",
             "Row key. One row per participant × calendar day over the full "
             "horizon (2019-11-01 → 2020-03-31, 456 rows).", "none", "key"),
    "readiness_next_day": ("float", "0–10 readiness points", "wellness questionnaire",
                           "LABEL (not a feature). Next-day cleaned readiness: the "
                           "same-day cleaned value shifted by −1 within participant, "
                           "so features on day D predict day D+1. NaN on 166 rows "
                           "without a next-day questionnaire answer.", "sentinel 0→NaN; causal shift", "label"),
    "label_available": ("int", "0/1 flag", "derived from the label",
                        "1 when readiness_next_day is known (290 rows); 0 otherwise. "
                        "Use it to select trainable rows.", "none", "flag"),
    "readiness_same_day": ("float", "0–10 readiness points", "wellness questionnaire",
                           "Same-day cleaned readiness. The single allowed "
                           "readiness-derived feature: relative to the D+1 label it "
                           "is strictly lagged ('the day before'), hence causal. "
                           "NaN when no questionnaire was submitted that day.",
                           "sentinel 0→NaN; per-participant demeaned", "feature"),
    "srpe_load": ("float", "RPE × minutes", "sRPE training log",
                  "Session load (perceived exertion times duration) summed over "
                  "sessions ending that day. 0.0 = no session logged; NaN = sessions "
                  "exist but RPE or duration is missing. Strongest within-person "
                  "signal in validation (higher load → lower next-day readiness).",
                  "per-participant demeaned", "feature"),
    "load_7d_mean": ("float", "load units/day", "derived from srpe_load",
                     "Trailing-7-day mean of daily sRPE load, window ending on day D "
                     "(causal). Chronic-load level; pairs with srpe_load (acute) and "
                     "acwr_7_28 (relative).", "causal rolling; demeaned", "feature"),
    "acwr_7_28": ("float", "ratio", "derived from srpe_load",
                  "Acute:chronic workload ratio = 7-day mean ÷ 28-day mean load. "
                  "Values >~1.5 flag load spikes. Needs 28 days of history: early "
                  "horizon rows use a truncated chronic window (min_periods=1); NaN "
                  "when the 28-day mean is 0.", "causal rolling; demeaned", "feature"),
    "missing_ratio_srpe_7d": ("float", "0–1 share", "sRPE log presence",
                              "Share of the trailing 7 days (ending D) with zero sRPE "
                              "sessions. Structural-missingness indicator: distinguishes "
                              "'rest day' from 'did not log'. High when monotony_7d is "
                              "NaN (dropped as degenerate).", "causal rolling; demeaned", "feature"),
    "hr_mean": ("float", "beats per minute", "Fitbit continuous heart rate",
                "Mean of cleaned high-frequency HR samples that day. Cleaning: "
                "confidence-0 samples dropped, physiologically clipped to [30, 220] "
                "bpm. Absent for p03 (no HR file) → NaN handled natively by the trees.",
                "conf-0 drop; clip; demeaned", "feature"),
    "hr_sd": ("float", "beats per minute", "Fitbit continuous heart rate",
              "Standard deviation of the day's cleaned HR samples (same cleaning as "
              "hr_mean). Captures cardiac variability across the day; 0.0 with a "
              "single sample, NaN with none.", "conf-0 drop; clip; demeaned", "feature"),
    "zone_min_IN_DEFAULT_ZONE_2": ("float", "minutes/day", "Fitbit HR zones",
                                   "Minutes in the cardio zone (70–84% of max HR). "
                                   "Strongest zone-level within-person signal (more "
                                   "cardio minutes → lower next-day readiness). NaN on "
                                   "days without a zones row (never zero-filled).",
                                   "NaN preserved; demeaned", "feature"),
    "zone_min_IN_DEFAULT_ZONE_3": ("float", "minutes/day", "Fitbit HR zones",
                                   "Minutes in the peak zone (≥85% of max HR). "
                                   "Zero-inflated; identical twin time_ge85_min dropped.",
                                   "NaN preserved; demeaned", "feature"),
    "hr_cov_min": ("float", "minutes (0–1440)", "Fitbit HR coverage",
                   "Distinct minutes with ≥1 kept HR sample. Doubles as a wear-time "
                   "gate: low coverage means the device was off or syncing failed.",
                   "conf-0 drop; demeaned", "feature"),
    "rhr_7d_median": ("float", "beats per minute", "Fitbit resting heart rate",
                      "Causal trailing-7-day median of cleaned RHR (0.0/null-date "
                      "sentinels → NaN), forward-filled max 2 days with a "
                      "was_imputed flag. Slow baseline anchor; no backfill (p05 has "
                      "no baseline before late December).", "rolling median; ffill≤2d; demeaned", "feature"),
    "rhr_residual": ("float", "beats per minute", "derived from RHR",
                     "rhr_raw minus its 7-day median: the acute deviation from the "
                     "slow baseline. NaN when either side is missing.",
                     "causal residual; demeaned", "feature"),
    "nonwear_min": ("float", "minutes (0–1440)", "steps + HR non-wear detector",
                    "Minutes inside ≥60-minute runs of zero steps combined with "
                    "missing or flatlined HR (charger/clipped-sensor artifact). "
                    "Missing minute-slots count as zero steps. For p03 (no HR file) "
                    "the rule is steps-only and overestimates (upper bound).",
                    "non-wear masking; demeaned", "feature"),
    "total_steps": ("float", "steps/day", "Fitbit minute steps",
                    "Daily step sum after keep-first dedupe of the 226 DST-duplicate "
                    "zero rows (p01, 2020-03-29). Missing minutes contribute 0; gate "
                    "sums with steps_cov_min.", "DST dedupe; demeaned", "feature"),
    "peak_1min_steps": ("float", "steps/minute", "Fitbit minute steps",
                        "Peak single-minute step count: intensity proxy complementary "
                        "to the daily total.", "DST dedupe; demeaned", "feature"),
    "exercise_min": ("float", "minutes/day", "Fitbit exercise bouts",
                     "Active minutes summed over bouts starting that day "
                     "(activeDuration ?? duration, ms→min; ≤0.03-min artifacts "
                     "dropped). 0.0 = no bout (true zero, not missing).",
                     "unit conversion; artifact drop; demeaned", "feature"),
    "asleep_min": ("float", "minutes/night", "Fitbit sleep log",
                   "Minutes asleep for the night ending that morning "
                   "(morning-attributed). NaN when no main-sleep night exists; "
                   "mainSleep=False naps are excluded (counted in n_naps upstream).",
                   "morning attribution; demeaned", "feature"),
    "efficiency_pct": ("float", "percent", "Fitbit sleep log",
                       "100 × asleep ÷ in-bed (athletic target ≥85%). Complements "
                       "asleep_min with a quality dimension.", "demeaned", "feature"),
    "midsleep_hour": ("float", "hour of day 0–24", "Fitbit sleep times",
                      "Circular mid-point of onset→offset: chronotype/schedule proxy. "
                      "Kept instead of onset/offset hours (redundant pair). NaN "
                      "without a night.", "circular mean; demeaned", "feature"),
    "mean_overall_score": ("float", "0–100 score", "Fitbit sleep score",
                           "Mean overall sleep score joined on logId. Kept instead of "
                           "the composition/revitalization/duration subscores "
                           "(redundant). NaN without a scored night.", "logId join; demeaned", "feature"),
    "estimated_kcal": ("float", "kilocalories/day", "food photos + Gemini",
                       "Whole-day macro estimate from the representative photo of each "
                       "15-second meal burst (cached vision calls, one per food-day). "
                       "NaN outside the Feb–Mar photo window or when estimation failed "
                       "(see has_nutrition). Protein/carbs/fats dropped as redundant "
                       "meal scalings.", "cached day-total vision; demeaned", "feature"),
    "n_photo_meals": ("float", "meals/day", "food photos, deterministic",
                      "15-second shutter-burst meal events among food captures "
                      "(union-find, transitive). Offline count needing no vision call; "
                      "pairs with estimated_kcal (amount) as count vs amount.",
                      "15 s grouping; demeaned", "feature"),
    "has_nutrition": ("float", "0/1 flag", "food-photo presence",
                      "1 when ≥1 food photo exists that day (Feb–Mar only). Gating "
                      "flag for estimated_kcal; identical twin "
                      "nutrition_kcal_available dropped.", "presence flag; demeaned", "feature"),
    "alcohol_bin": ("float", "0/1 flag", "self-reported log",
                    "1 if any 'Yes' that day (no unit volumes are logged, so no "
                    "dose-response is identifiable). NaN with no reporting row; "
                    "p01 is all-No (zero variance within p01).", "Yes/No→1/0; demeaned", "feature"),
    "weekend_bin": ("float", "0/1 flag", "calendar",
                    "1 on Fri/Sat/Sun: captures post-match weekend clustering. Kept "
                    "instead of raw day-of-week (cyclic, dropped).", "calendar derivation; demeaned", "feature"),
    "injured_last_7d": ("float", "0/1 flag", "injury log",
                        "1 when any injury event falls in the trailing 7 days (rolling "
                        "max, causal). The recurrent p05 left-foot complaint is one "
                        "episode state, not independent traumas; rare same-day dummies "
                        "collapsed into this flag.", "rolling max; demeaned", "feature"),
    "steps_cov_min": ("float", "minutes (0–1440)", "Fitbit steps coverage",
                      "Minutes with a steps row after dedupe. Companion gate for "
                      "total_steps sums (missing minutes are zeros). p01 ≈1440, "
                      "p03/p05 much lower.", "dedupe; demeaned", "feature"),
    "has_wellness": ("float", "0/1 flag", "questionnaire presence",
                     "1 when a wellness row exists that day (response-rate gate; p03 "
                     "≈51%). Count twin n_wellness_rows dropped as near-identical.",
                     "presence flag; demeaned", "feature"),
    "missing_ratio_wellness_7d": ("float", "0–1 share", "questionnaire presence",
                                  "Share of trailing-7-day missing wellness days. "
                                  "Compliance signal: block-missingness marks p03's "
                                  "sparse periods.", "causal rolling; demeaned", "feature"),
    "missing_ratio_sleep_7d": ("float", "0–1 share", "sleep-log presence",
                               "Share of the trailing 7 days (ending D) with no main-sleep "
                               "night. Compliance/wear signal complementing the sleep "
                               "features (p03 contributes most missing nights).",
                               "causal rolling; demeaned", "feature"),
    "missing_ratio_zones_7d": ("float", "0–1 share", "HR-zones presence",
                               "Share of the trailing 7 days (ending D) with no HR-zone "
                               "row. Marks device-off or sync-failure stretches; pairs "
                               "with hr_cov_min as the cardiac-coverage gate.",
                               "causal rolling; demeaned", "feature"),
    "was_imputed_rhr_7d_median": ("float", "0/1 flag", "Tier-1 imputation audit",
                                  "1 when rhr_7d_median was forward-filled (≤2 days). "
                                  "Honesty flag so the model can discount imputed "
                                  "baselines.", "ffill≤2d flag; demeaned", "feature"),
    "was_imputed_weight_7d_median": ("float", "0/1 flag", "Tier-1 imputation audit",
                                     "1 when the weight median was forward-filled "
                                     "(≤2 days). Weight itself is hyper-stable "
                                     "(CV<1%) so fills are baseline anchors, not signal.",
                                     "ffill≤2d flag; demeaned", "feature"),
}


def build_final_dataset(frame_full, frame_labeled, feature_cols):
    """Select S3 columns and demean (means fit on labeled rows, applied to all).

    Returns (final_df, demean_params, fallback) where final_df holds keys +
    demeaned features + label columns for the ENTIRE frame (456 rows).
    """
    from training_experiments import model as model_mod
    means, fallback = model_mod.fit_demean_params(frame_labeled, feature_cols)
    demeaned = model_mod.apply_demean(frame_full, feature_cols, means, fallback)
    keep = [c for c in KEY_COLS + feature_cols + LABEL_COLS if c in demeaned.columns]
    return demeaned[keep].copy(), means, fallback


def write_final_dictionary(final_df, path):
    """Explicit data dictionary for final_training_dataset.csv."""
    import pandas as pd

    rows = []
    for col in final_df.columns:
        dtype, unit, source, desc, prep, role = COLUMN_DOCS.get(
            col, (str(final_df[col].dtype), "", "", "", "", "feature"))
        non_missing = int(final_df[col].notna().sum())
        rows.append({
            "column": col,
            "dtype": str(final_df[col].dtype),
            "unit": unit,
            "source": source,
            "description": desc,
            "preprocessing": prep,
            "non_missing_rows": non_missing,
            "role": role,
        })
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def main(out_dir=None):
    """Refit the winning pipeline on all labeled rows; persist artifacts."""
    import pandas as pd
    from xgboost import XGBRegressor

    from training_experiments import config as config_mod
    from training_experiments import data as data_mod
    from training_experiments import features as features_mod
    from training_experiments import metrics as metrics_mod
    from training_experiments import model as model_mod

    out_dir = Path(out_dir) if out_dir else BASE_DIR / "output_dataset"
    out_dir.mkdir(parents=True, exist_ok=True)

    from src.pre_processing.pre_processor import get_feature_columns

    full = pd.read_csv(data_mod.DATASET_PATH)
    labeled = full[full[data_mod.LABEL].notna()].reset_index(drop=True)
    sets = features_mod.resolve_feature_sets(full, get_feature_columns(full))
    cols = sets["S3_minimal"]

    final_df, means, fallback = build_final_dataset(full, labeled, cols)
    final_df.to_csv(out_dir / "final_training_dataset.csv", index=False)
    write_final_dictionary(final_df, out_dir / "final_data_dictionary.csv")

    # Demean params: one row per participant + GLOBAL fallback for new players.
    params_df = means[cols].copy()
    params_df.loc["GLOBAL"] = fallback[cols].to_numpy()
    params_df.to_csv(out_dir / "winning_pipeline_demean_params.csv")

    with open(out_dir / "winning_pipeline_features.json", "w") as fh:
        json.dump({"config": WINNING_CONFIG, "feature_set": "S3_minimal",
                   "features": cols,
                   "params": config_mod.CONFIGS[WINNING_CONFIG]}, fh, indent=1)

    X = model_mod.to_matrix(final_df[final_df["label_available"] == 1], cols)
    y = final_df.loc[final_df["label_available"] == 1, data_mod.LABEL].to_numpy(dtype=float)
    fitted = XGBRegressor(**config_mod.CONFIGS[WINNING_CONFIG])
    fitted.fit(X, y)
    fitted.save_model(out_dir / "winning_pipeline_model.ubj")

    pred = fitted.predict(X)
    m = metrics_mod.regression_metrics(y, pred)
    print(f"rows: {len(final_df)} (labeled {len(y)}), features: {len(cols)}")
    print(f"in-sample MAE={m['mae']:.3f} RMSE={m['rmse']:.3f} "
          f"(optimistic; LOPO estimate is the honest one)")
    print(f"wrote artifacts to {out_dir}")
    return final_df, fitted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Refit the winning pipeline on all data.")
    parser.add_argument("--out-dir", default=None)
    args = parser.parse_args()
    main(args.out_dir)
