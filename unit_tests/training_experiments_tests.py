"""Tests for the LOPO XGBoost pipeline (fast; one tiny real-data load)."""

import unittest

import numpy as np
import pandas as pd

from training_experiments import config, data, features, metrics, model


class TestConfig(unittest.TestCase):
    def test_validated_configs_intact(self):
        self.assertEqual(list(config.CONFIGS), ["A_expressive", "B_balanced", "C_robust"])
        self.assertEqual(config.CONFIGS["A_expressive"]["max_depth"], 4)
        self.assertEqual(config.CONFIGS["C_robust"]["max_depth"], 2)
        self.assertEqual(config.CONFIGS["C_robust"]["reg_lambda"], 10.0)
        self.assertEqual(config.CONFIGS["C_robust"]["min_child_weight"], 10)
        for name in config.CONFIG_ORDER:
            self.assertEqual(config.CONFIGS[name]["random_state"], 42)
            self.assertEqual(config.CONFIGS[name]["objective"], "reg:squarederror")


class TestSplits(unittest.TestCase):
    def test_lopo_disjoint_and_complete(self):
        frame, _ = data.load_labeled_frame()
        folds = list(data.lopo_splits(frame))
        self.assertEqual(len(folds), 3)
        seen_test = set()
        for train_idx, test_idx, player in folds:
            self.assertEqual(len(set(train_idx) & set(test_idx)), 0)
            self.assertTrue((frame.loc[test_idx, "participant_id"] == player).all())
            self.assertFalse((frame.loc[train_idx, "participant_id"] == player).any())
            seen_test.update(test_idx)
        self.assertEqual(seen_test, set(frame.index))
        self.assertEqual(sorted(f[2] for f in folds), ["p01", "p03", "p05"])


class TestFeatures(unittest.TestCase):
    def test_sets_resolve_and_nest(self):
        frame, used_in_x = data.load_labeled_frame()
        sets = features.resolve_feature_sets(frame, used_in_x)
        self.assertEqual(sorted(sets), ["S1_tier1", "S2_tier1_2", "S3_minimal"])
        self.assertTrue(set(sets["S2_tier1_2"]) <= set(sets["S1_tier1"]))
        for dropped in ("nonwear_hours", "load_7d_sum", "gender", "mean_rpe",
                        "total_distance_cm", "weight_raw", "lag_days", "age"):
            self.assertNotIn(dropped, sets["S2_tier1_2"])
        for kept in ("srpe_load", "hr_mean", "zone_min_IN_DEFAULT_ZONE_2",
                     "estimated_kcal", "injured_last_7d"):
            self.assertIn(kept, sets["S3_minimal"])
        self.assertTrue(len(sets["S1_tier1"]) > len(sets["S2_tier1_2"]) >
                        len(sets["S3_minimal"]) > 0)

    def test_resolution_fails_loudly(self):
        frame, used_in_x = data.load_labeled_frame()
        # A Tier-1 drop name absent from the frame must raise.
        with self.assertRaises(ValueError):
            features.resolve_feature_sets(frame.drop(columns=["nonwear_hours"]),
                                          used_in_x)
        # A minimal-set name absent from the frame must raise.
        with self.assertRaises(ValueError):
            features.resolve_feature_sets(frame.drop(columns=["srpe_load"]),
                                          used_in_x)


class TestDemean(unittest.TestCase):
    def test_train_means_zero_and_nan_preserved(self):
        frame = pd.DataFrame({
            "participant_id": ["a", "a", "b", "b"],
            "x": [1.0, 3.0, 10.0, np.nan], "y": [5.0, 5.0, 5.0, 5.0]})
        params, fallback = model.fit_demean_params(frame, ["x", "y"])
        out = model.apply_demean(frame, ["x", "y"], params, fallback)
        self.assertAlmostEqual(out.loc[0, "x"], -1.0)
        self.assertAlmostEqual(out.loc[1, "x"], 1.0)
        self.assertTrue(np.isnan(out.loc[3, "x"]))
        # unseen participant falls back to global means
        other = pd.DataFrame({"participant_id": ["zzz"], "x": [7.0], "y": [5.0]})
        out2 = model.apply_demean(other, ["x", "y"], params, fallback)
        self.assertAlmostEqual(out2.loc[0, "x"], 7.0 - np.nanmean([1.0, 3.0, 10.0]))


class TestMetrics(unittest.TestCase):
    def test_regression_math(self):
        m = metrics.regression_metrics([2.0, 4.0, 6.0], [3.0, 4.0, 5.0])
        self.assertAlmostEqual(m["mae"], 2 / 3)
        self.assertAlmostEqual(m["rmse"], (2 / 3) ** 0.5)
        self.assertGreater(m["r2"], 0.7)
        m_const = metrics.regression_metrics([5.0, 5.0], [4.0, 6.0])
        self.assertTrue(np.isnan(m_const["r2"]))

    def test_to_class_rounds_and_clips(self):
        self.assertEqual(list(metrics.to_class([4.4, 4.5, 1.2, 9.9, 7.0])),
                         [4, 4, 2, 8, 7])

    def test_categorical_perfect(self):
        y = [3, 5, 5, 7]
        m = metrics.categorical_metrics(y, [3.1, 4.9, 5.2, 7.0])
        self.assertEqual(m["accuracy"], 1.0)
        self.assertEqual(m["balanced_accuracy"], 1.0)
        self.assertEqual(m["f1_macro"], 1.0)
        self.assertEqual(m["qwk"], 1.0)

    def test_confusion_frame_grid(self):
        cf = metrics.confusion_frame([5, 5, 6], [5.0, 4.0, 6.0])
        self.assertEqual(len(cf), 49)  # 7x7 fixed grid
        self.assertEqual(cf["count"].sum(), 3)
        hit = cf[(cf["true"] == 5) & (cf["pred"] == 5)]["count"].iloc[0]
        self.assertEqual(hit, 1)


class TestDeterminism(unittest.TestCase):
    def test_same_seed_same_predictions(self):
        rng = np.random.default_rng(0)
        X = rng.normal(size=(40, 5))
        y = X[:, 0] * 2 + rng.normal(size=40) * 0.1
        p1, _ = model.fit_predict({**config.CONFIGS["C_robust"], "n_estimators": 10}, X, y, X)
        p2, _ = model.fit_predict({**config.CONFIGS["C_robust"], "n_estimators": 10}, X, y, X)
        np.testing.assert_allclose(p1, p2)


if __name__ == "__main__":
    unittest.main()
