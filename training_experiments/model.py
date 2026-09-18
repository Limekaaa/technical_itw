"""Model fitting with leakage-safe per-participant demeaning.

Why demeaning: the correlation analysis showed pooled links are dominated
by between-person level shifts. Subtracting each participant's own mean
forces the trees to learn day-to-day effects. Demeaning uses FEATURE
values only (never labels): train rows use means over train rows of the
same participant; test rows use the held-out participant's own feature
means (transductive preprocessing, no label leakage). Unseen
participants fall back to global train means. NaNs are skipped by the
means and passed through to XGBoost, which routes them natively.
"""

import numpy as np
import pandas as pd
from xgboost import XGBRegressor


def fit_demean_params(train_frame, feature_cols, group="participant_id"):
    """Per-participant feature means over train rows (NaN-skipping)."""
    params = train_frame.groupby(group)[feature_cols].mean(numeric_only=True)
    fallback = train_frame[feature_cols].mean(numeric_only=True)
    return params, fallback


def apply_demean(frame, feature_cols, params, fallback, group="participant_id"):
    """Subtract the participant's mean vector (fallback: global means)."""
    out = frame.copy()
    means = frame[group].map(lambda p: _participant_mean(params, fallback, p))
    out[feature_cols] = frame[feature_cols].to_numpy() - np.vstack(means.to_numpy())
    return out


def _participant_mean(params, fallback, participant):
    if participant in params.index:
        return params.loc[participant].to_numpy()
    return fallback.to_numpy()


def fit_predict(params_dict, X_train, y_train, X_test):
    """Fit XGBRegressor on (NaN-carrying) train matrix, predict test."""
    model = XGBRegressor(**params_dict)
    model.fit(X_train, y_train)
    return model.predict(X_test), model


def to_matrix(frame, feature_cols):
    """Float matrix preserving NaNs for XGBoost's native handling."""
    return frame[feature_cols].to_numpy(dtype=float)
