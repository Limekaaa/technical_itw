"""Fixed hyperparameter configurations (user-validated, expressive -> robust).

No tuning loop: with 290 labeled rows, tuning would overfit the
validation split. The experiment compares these three fixed configs.
Common to all: squared-error regression, hist tree method (CPU),
NaN handled natively by XGBoost (sparsity-aware splits), fixed seed.
"""

SEED = 42
XGBOOST_VERSION = "3.2.0"  # pinned install in .venv

COMMON = {
    "objective": "reg:squarederror",
    "tree_method": "hist",
    "random_state": SEED,
    "n_jobs": -1,
}

# A: expressive baseline. B: balanced. C: heavily regularized
# (depth-2 stumps + strong L1/L2 ~ regularized additive model).
CONFIGS = {
    "A_expressive": {
        **COMMON,
        "n_estimators": 500,
        "max_depth": 4,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 1.0,
        "reg_alpha": 0.0,
        "min_child_weight": 1,
        "gamma": 0.0,
    },
    "B_balanced": {
        **COMMON,
        "n_estimators": 300,
        "max_depth": 3,
        "learning_rate": 0.05,
        "subsample": 0.8,
        "colsample_bytree": 0.8,
        "reg_lambda": 5.0,
        "reg_alpha": 1.0,
        "min_child_weight": 3,
        "gamma": 0.1,
    },
    "C_robust": {
        **COMMON,
        "n_estimators": 200,
        "max_depth": 2,
        "learning_rate": 0.03,
        "subsample": 0.7,
        "colsample_bytree": 0.6,
        "reg_lambda": 10.0,
        "reg_alpha": 5.0,
        "min_child_weight": 10,
        "gamma": 0.5,
    },
}

CONFIG_ORDER = ["A_expressive", "B_balanced", "C_robust"]
