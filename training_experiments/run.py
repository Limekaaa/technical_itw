"""Orchestrator: 3 configs x 3 feature sets x 3 LOPO folds = 27 fits.

Per fold it fits the demeaning on train rows, trains XGBRegressor, scores
regression + categorical metrics, and scores two references: a legitimate
global-train-mean baseline and a participant-mean oracle (uses test
labels; unachievable reference showing the near-constant-fold ceiling).
Writes analysis/training_metrics.csv (27 rows) and
analysis/confusion_matrices.csv (long form), prints the summary table.

Usage: .venv/bin/python -m training_experiments.run
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE_DIR))

from training_experiments import config, data, features, metrics, model  # noqa: E402
from training_experiments.config import CONFIG_ORDER  # noqa: E402
from training_experiments.features import SET_ORDER  # noqa: E402

METRICS_PATH = BASE_DIR / "analysis" / "training_metrics.csv"
CONFUSION_PATH = BASE_DIR / "analysis" / "confusion_matrices.csv"


def run_fold(frame, feature_cols, params_dict, train_idx, test_idx):
    """Demean (train-fit), fit, predict, score one fold. Returns dicts."""
    train = frame.loc[train_idx].reset_index(drop=True)
    test = frame.loc[test_idx].reset_index(drop=True)
    means, fallback = model.fit_demean_params(train, feature_cols)
    train_dm = model.apply_demean(train, feature_cols, means, fallback)
    test_dm = model.apply_demean(test, feature_cols, means, fallback)
    y_train = train[data.LABEL].to_numpy(dtype=float)
    y_test = test[data.LABEL].to_numpy(dtype=float)
    y_pred, _ = model.fit_predict(
        params_dict,
        model.to_matrix(train_dm, feature_cols), y_train,
        model.to_matrix(test_dm, feature_cols))
    out = {"n_train": len(train), "n_test": len(test),
           **metrics.regression_metrics(y_test, y_pred),
           **metrics.categorical_metrics(y_test, y_pred)}
    # Legitimate baseline: global train mean, scored both ways.
    base_pred = np.full_like(y_test, np.nanmean(y_train))
    out.update({f"base_{k}": v for k, v in
                {**metrics.regression_metrics(y_test, base_pred),
                 **{kk: vv for kk, vv in
                     metrics.categorical_metrics(y_test, base_pred).items()
                     if kk != "n_classes_true"}}.items()})
    # Oracle reference (uses test labels): participant-mean predictor.
    oracle_pred = np.full_like(y_test, np.nanmean(y_test))
    out.update({f"oracle_{k}": v for k, v in
                metrics.regression_metrics(y_test, oracle_pred).items()})
    conf = metrics.confusion_frame(y_test, y_pred)
    return out, conf


def main():
    frame, used_in_x = data.load_labeled_frame()
    sets = features.resolve_feature_sets(frame, used_in_x)
    print(f"labeled rows: {len(frame)}; " +
          ", ".join(f"{k}={len(v)}" for k, v in sets.items()))
    metric_rows, conf_rows = [], []
    for cfg_name in CONFIG_ORDER:
        for set_name in SET_ORDER:
            cols = sets[set_name]
            for train_idx, test_idx, player in data.lopo_splits(frame):
                res, conf = run_fold(frame, cols, config.CONFIGS[cfg_name],
                                     train_idx, test_idx)
                res.update({"config": cfg_name, "feature_set": set_name,
                            "test_player": player})
                metric_rows.append(res)
                conf["config"] = cfg_name
                conf["feature_set"] = set_name
                conf["test_player"] = player
                conf_rows.append(conf)
                print(f"{cfg_name} {set_name} test={player}: "
                      f"MAE={res['mae']:.3f} (base {res['base_mae']:.3f}) "
                      f"R2={res['r2']:.3f} acc={res['accuracy']:.3f} "
                      f"QWK={res['qwk']:.3f}", flush=True)
    metrics_df = pd.DataFrame(metric_rows)
    metrics_df.to_csv(METRICS_PATH, index=False)
    pd.concat(conf_rows, ignore_index=True).to_csv(CONFUSION_PATH, index=False)
    summary = (metrics_df.groupby(["config", "feature_set"])
               .agg(mean_mae=("mae", "mean"), std_mae=("mae", "std"),
                    mean_rmse=("rmse", "mean"), mean_r2=("r2", "mean"),
                    mean_acc=("accuracy", "mean"),
                    mean_qwk=("qwk", "mean"),
                    mean_base_mae=("base_mae", "mean"))
               .reset_index().sort_values("mean_mae"))
    print("\nSummary (mean +- std over 3 test players):")
    print(summary.round(3).to_string(index=False))
    print(f"\nwrote {METRICS_PATH} ({len(metrics_df)} runs)")
    return metrics_df


if __name__ == "__main__":
    main()
