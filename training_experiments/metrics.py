"""Regression + int-rounded categorical metrics and confusion matrices.

The label takes integer values 2..8. Primary evaluation is regression
(MAE/RMSE/R2), complemented by categorical metrics on predictions rounded
to the nearest int and clipped to the observed [2, 8] range: accuracy,
balanced accuracy, macro F1 and quadratic-weighted kappa (appropriate for
an ordinal scale). Confusion matrices use the fixed 2..8 label grid.
"""

import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, balanced_accuracy_score,
                             cohen_kappa_score, confusion_matrix, f1_score,
                             mean_absolute_error, mean_squared_error, r2_score)

CLASS_GRID = [2, 3, 4, 5, 6, 7, 8]
LO, HI = min(CLASS_GRID), max(CLASS_GRID)


def to_class(y_pred):
    """Round continuous predictions to the observed int grid."""
    return np.clip(np.rint(np.asarray(y_pred, dtype=float)), LO, HI).astype(int)


def regression_metrics(y_true, y_pred):
    """MAE / RMSE / R2. R2 is NaN when the fold target is constant."""
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    if np.nanstd(y_true) == 0:
        r2 = float("nan")
    else:
        with np.errstate(all="ignore"):
            r2 = float(r2_score(y_true, y_pred))
    return {"mae": float(mean_absolute_error(y_true, y_pred)),
            "rmse": rmse, "r2": r2}


def categorical_metrics(y_true, y_pred):
    """Accuracy / balanced accuracy / macro F1 / QWK on rounded preds."""
    yt = np.asarray(y_true, dtype=int)
    yp = to_class(y_pred)
    try:
        qwk = float(cohen_kappa_score(yt, yp, weights="quadratic"))
    except (ValueError, ZeroDivisionError, RuntimeWarning):
        qwk = float("nan")
    return {"accuracy": float(accuracy_score(yt, yp)),
            "balanced_accuracy": float(balanced_accuracy_score(yt, yp)),
            "f1_macro": float(f1_score(yt, yp, average="macro", zero_division=0)),
            "qwk": qwk,
            "n_classes_true": int(len(np.unique(yt)))}


def confusion_frame(y_true, y_pred):
    """Long-form confusion matrix over the fixed 2..8 grid."""
    cm = confusion_matrix(np.asarray(y_true, dtype=int), to_class(y_pred),
                          labels=CLASS_GRID)
    rows = []
    for i, true in enumerate(CLASS_GRID):
        for j, pred in enumerate(CLASS_GRID):
            rows.append({"true": true, "pred": pred, "count": int(cm[i, j])})
    return pd.DataFrame(rows)
