"""LOPO XGBoost training experiments for next-day readiness (regression).

Design: train on 2 players, test on the held-out one (no player
contamination; all features are causal by construction). Three fixed
hyperparameter configs (expressive -> robust, user-validated) crossed
with three feature sets (Tier-1 baseline, Tier-1+2, minimal robust) =
9 runs x 3 folds = 27 fits. Regression metrics + int-rounded
categorical metrics (accuracy, balanced accuracy, macro F1, quadratic
weighted kappa, confusion matrices) per fold, aggregated as mean +/- std.
"""
