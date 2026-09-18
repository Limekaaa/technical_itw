"""Feature sets S1 (Tier-1 baseline), S2 (Tier-1+2), S3 (minimal robust).

Grounded in analysis/correlation_analysis.md section 7. S1/S2 are defined
as drop lists applied to used_in_X (robust to upstream column additions);
S3 is the explicit minimal list from the analysis. resolve_feature_sets()
validates every name against the actual CSV columns and fails loudly.
"""

TIER1_DROP = [
    # Exact duplicates / deterministic derivations (r = 1.0).
    "total_distance_m",  # already excluded upstream; kept for documentation
    "nonwear_hours",
    "load_7d_sum",
    "has_zones",
    "has_sleep",
    "has_sleep_record",
    "nutrition_kcal_available",
    "time_ge85_min",
    "act_team",
    "mean_deep_sleep_in_minutes",
    "has_hr",
    "hr_n_samples",
    "has_nonwear",
    "has_wellness",
    "n_reporting_rows",
    # Constants / single-event / ultra-rare / meaningless encoding.
    "gender",
    "chronotype",
    "n_deduped_min",
    "n_clipped_hr",
    "nonwear_is_upper_bound",
    "is_classic",
    # Too sparse to generalize.
    "mean_rpe",  # n = 33
]

TIER2_DROP = [
    # One representative per redundancy group (|rho| >= 0.8).
    "total_distance_cm",  # keep total_steps + total_kcal
    "weight_raw",  # keep median + residual
    "rhr_raw",  # keep median + residual
    "monotony_7d",  # degenerate (NaN iff no sessions) + 59% missing
    "strain_7d",  # deterministic product of load x monotony
    "srpe_n_sessions",  # keep srpe_load
    "zone_min_BELOW_DEFAULT_ZONE_1",
    "zone_min_IN_DEFAULT_ZONE_1",
    "trimp_edwards",
    "mean_conf",
    "time_in_bed_min",  # keep asleep_min
    "onset_hour",
    "offset_hour",  # keep midsleep_hour
    "mean_composition_score",
    "mean_revitalization_score",
    "mean_duration_score",  # keep overall + restlessness
    "deep_pct",
    "light_pct",
    "rem_pct",
    "wake_pct",  # compositional with stage minutes
    "n_photos",
    "n_food_photos",  # keep n_photo_meals
    "protein_g",
    "carbs_g",
    "fat_g",  # keep estimated_kcal
    "total_steps_median_7d",  # keep mean_7d (+ std_7d)
    "exercise_min_median_7d",  # keep mean_7d (+ std_7d)
    "act_individual",
    "act_endurance",
    "act_strength",  # keep running/soccer/walk/bike
    "is_injured_day",
    "n_injury_reports",
    "inj_head_neck__minor",
    "inj_left_foot__minor",
    "inj_right_hand__minor",  # collapse to injured_last_7d
    "dow",  # cyclic; keep weekend_bin
    "lag_days",  # within-person r ~= 0 + negative-lag quirk
    "age",
    "height_cm",
    "max_hr",
    "stride_walk_cm",
    "stride_run_cm",  # participant constants -> fixed effects instead
]

# Explicit minimal robust set (correlation_analysis.md section 7).
MINIMAL_SET = [
    "readiness_same_day",
    "srpe_load",
    "load_7d_mean",
    "acwr_7_28",
    "missing_ratio_srpe_7d",
    "hr_mean",
    "hr_sd",
    "zone_min_IN_DEFAULT_ZONE_2",
    "zone_min_IN_DEFAULT_ZONE_3",
    "hr_cov_min",
    "rhr_7d_median",
    "rhr_residual",
    "nonwear_min",
    "total_steps",
    "peak_1min_steps",
    "exercise_min",
    "asleep_min",
    "efficiency_pct",
    "midsleep_hour",
    "mean_overall_score",
    "estimated_kcal",
    "n_photo_meals",
    "has_nutrition",
    "alcohol_bin",
    "weekend_bin",
    "injured_last_7d",
    "steps_cov_min",
    "has_wellness",
    "missing_ratio_wellness_7d",
    "missing_ratio_sleep_7d",
    "missing_ratio_zones_7d",
    "was_imputed_rhr_7d_median",
    "was_imputed_weight_7d_median",
]


def resolve_feature_sets(df, used_in_x):
    """Build {S1_..., S2_..., S3_...} validated against df columns.

    Raises ValueError listing any Tier-1/2 drop name missing from the
    frame (except total_distance_m, already excluded upstream) and any
    MINIMAL_SET name absent or not in used_in_X.
    """
    available = set(df.columns)
    missing_drops = [c for c in TIER1_DROP + TIER2_DROP
                     if c not in available and c != "total_distance_m"]
    if missing_drops:
        raise ValueError(f"Drop-list names absent from dataset: {missing_drops}")
    missing_keep = [c for c in MINIMAL_SET if c not in available]
    if missing_keep:
        raise ValueError(f"Minimal-set names absent from dataset: {missing_keep}")
    outside = [c for c in MINIMAL_SET if c not in set(used_in_x)]
    if outside:
        raise ValueError(f"Minimal-set names outside used_in_X: {outside}")
    base = [c for c in used_in_x if c in available]
    s1 = [c for c in base if c not in set(TIER1_DROP)]
    s2 = [c for c in s1 if c not in set(TIER2_DROP)]
    s3 = list(MINIMAL_SET)
    return {"S1_tier1": s1, "S2_tier1_2": s2, "S3_minimal": s3}


SET_ORDER = ["S1_tier1", "S2_tier1_2", "S3_minimal"]
