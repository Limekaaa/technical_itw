"""Tests for the pre-processing framework (fast, offline, no API calls)."""

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

import numpy as np
import pandas as pd

from src.data_handling import aggregator, macro_estimator
from src.pre_processing.outliers_handler import (
    sensor_artifacts, physio_bounds, nonwear, meal_grouping)
from src.pre_processing.missing_values_handler import forward_fill, indicators
from src.pre_processing import pre_processor


class TestSensorArtifacts(unittest.TestCase):
    def test_confidence_zero_dropped(self):
        hr = {"t1": {"bpm": 60, "confidence": 0},
              "t2": {"bpm": 70, "confidence": 2}}
        cleaned, n_dropped, mean_conf = sensor_artifacts.filter_low_confidence_hr(hr)
        self.assertEqual(n_dropped, 1)
        self.assertEqual(list(cleaned), ["t2"])
        self.assertAlmostEqual(mean_conf, 2.0)

    def test_dedupe_keep_first(self):
        idx = pd.DatetimeIndex(["2020-03-29 01:00:00", "2020-03-29 01:00:00",
                                "2020-03-29 01:01:00"])
        s = pd.Series([0.0, 0.0, 5.0], index=idx)
        deduped, n = sensor_artifacts.dedupe_minute_series(s)
        self.assertEqual(n, 1)
        self.assertEqual(len(deduped), 2)


class TestPhysioBounds(unittest.TestCase):
    def test_hr_clip(self):
        hr = {"a": {"bpm": 25, "confidence": 3}, "b": {"bpm": 250, "confidence": 3},
              "c": {"bpm": 70, "confidence": 3}}
        clipped, n = physio_bounds.clip_hr_bpm(hr)
        self.assertEqual(n, 2)
        self.assertEqual(clipped["a"]["bpm"], 30)
        self.assertEqual(clipped["b"]["bpm"], 220)
        self.assertEqual(clipped["c"]["bpm"], 70)

    def test_stride_sentinel(self):
        self.assertTrue(np.isnan(physio_bounds.clean_stride_run(11.3)))
        self.assertAlmostEqual(physio_bounds.clean_stride_run(102.9), 102.9)

    def test_rhr_sentinel(self):
        self.assertTrue(np.isnan(physio_bounds.clean_resting_hr_value({"date": None, "value": 0.0})))
        self.assertTrue(np.isnan(physio_bounds.clean_resting_hr_value({"date": "11/01/19", "value": 0.0})))
        self.assertAlmostEqual(
            physio_bounds.clean_resting_hr_value({"date": "11/01/19", "value": 53.7}), 53.7)


class TestNonWear(unittest.TestCase):
    def _steps(self, day, zeros):
        grid = pd.date_range(f"{day} 00:00:00", f"{day} 23:59:00", freq="min")
        vals = np.ones(len(grid))
        vals[zeros] = 0.0
        return pd.Series(vals, index=grid)

    def test_sixty_min_run_flagged(self):
        day = "2020-01-01"
        steps = self._steps(day, slice(60, 120))
        out = nonwear.compute_nonwear_day(steps, {}, hr_available=True, day=day)
        self.assertEqual(out["nonwear_min"], 60)
        self.assertTrue(out["has_nonwear"])

    def test_fifty_nine_min_run_ignored(self):
        day = "2020-01-01"
        steps = self._steps(day, slice(60, 119))
        out = nonwear.compute_nonwear_day(steps, {}, hr_available=True, day=day)
        self.assertEqual(out["nonwear_min"], 0)

    def test_active_hr_cancels_nonwear(self):
        day = "2020-01-01"
        steps = self._steps(day, slice(60, 120))
        hr = {f"{day} 01:{m:02d}:05.000": {"bpm": 70 + (m % 5), "confidence": 3}
              for m in range(60)}
        out = nonwear.compute_nonwear_day(steps, hr, hr_available=True, day=day)
        self.assertEqual(out["nonwear_min"], 0)


class TestMealGrouping(unittest.TestCase):
    def test_burst_groups_transitively(self):
        base = datetime(2020, 2, 1, 12, 0, 0)
        files = [(f"p{i}.jpg", base.replace(second=i * 10)) for i in range(3)]
        files.append(("late.jpg", base.replace(hour=15)))
        meals = meal_grouping.group_photos_to_meals(files, 15)
        self.assertEqual(len(meals), 2)
        self.assertEqual(len(meals[0]), 3)


class TestMissingValues(unittest.TestCase):
    def test_ffill_limit_and_flag_no_backfill(self):
        df = pd.DataFrame({
            "participant_id": ["p01"] * 6,
            "date": [f"2020-01-0{d}" for d in range(1, 7)],
            "weight_7d_median": [100.0, np.nan, np.nan, np.nan, np.nan, 101.0]})
        out = forward_fill.causal_forward_fill(df, ["weight_7d_median"], limit=2)
        self.assertEqual(list(out["weight_7d_median"][:3]), [100.0, 100.0, 100.0])
        self.assertTrue(np.isnan(out["weight_7d_median"].iloc[3]))
        self.assertEqual(list(out["was_imputed_weight_7d_median"][:4]), [0, 1, 1, 0])

    def test_rolling_missing_ratio_causal(self):
        df = pd.DataFrame({
            "participant_id": ["p01"] * 7,
            "date": [f"2020-01-0{d}" for d in range(1, 8)],
            "n_wellness_rows": [1, 1, 0, 0, 1, 1, 1]})
        out = indicators.add_rolling_missing_ratios(df, window=7)
        self.assertAlmostEqual(out["missing_ratio_wellness_7d"].iloc[3], 0.5)
        self.assertAlmostEqual(out["missing_ratio_wellness_7d"].iloc[6], 2 / 7)


class TestMacroEstimator(unittest.TestCase):
    def test_coerce_valid(self):
        out = macro_estimator._coerce_macros(
            {"calories": 500, "protein": 20, "carbohydrates": 60, "fats": 15})
        self.assertEqual(out, {"calories": 500.0, "protein": 20.0,
                               "carbohydrates": 60.0, "fats": 15.0})

    def test_coerce_rejects_bad(self):
        self.assertEqual(macro_estimator._coerce_macros({"calories": 1}), {})
        self.assertEqual(macro_estimator._coerce_macros(
            {"calories": 1, "protein": 2, "carbohydrates": 3, "fats": -1}), {})
        self.assertEqual(macro_estimator._coerce_macros("nope"), {})

    def test_cache_key_stable_regardless_of_order(self):
        k1 = macro_estimator.cache_key("p01", "2020-02-01", ["b.jpg", "a.jpg"])
        k2 = macro_estimator.cache_key("p01", "2020-02-01", ["a.jpg", "b.jpg"])
        self.assertEqual(k1, k2)

    def test_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "cache.json")
            macro_estimator.save_cache({"k": {"calories": 1.0}}, path)
            self.assertEqual(macro_estimator.load_cache(path),
                             {"k": {"calories": 1.0}})

    def test_cache_hit_makes_no_api_call(self):
        cache = {"p01|2020-02-01|a.jpg":
                 {"calories": 500.0, "protein": 20.0,
                  "carbohydrates": 60.0, "fats": 15.0}}
        with mock.patch.object(macro_estimator, "estimate_day_macros",
                               side_effect=AssertionError("must not call API")):
            out = macro_estimator.get_day_macros(
                "p01", "2020-02-01", ["a.jpg"], cache, throttle=False)
        self.assertEqual(out["calories"], 500.0)

    def test_api_failure_returns_empty(self):
        with mock.patch.object(macro_estimator, "estimate_day_macros", return_value={}):
            with mock.patch("time.sleep", return_value=None):
                out = macro_estimator.get_day_macros(
                    "p01", "2020-02-01", ["a.jpg"], {}, throttle=False)
        self.assertEqual(out, {})

    def test_list_photo_meals_chronological(self):
        meals = meal_grouping.list_photo_meals_for_day("p03", "2020-02-07")
        self.assertTrue(len(meals) >= 1)
        flat = [p for meal in meals for p in meal]
        self.assertTrue(all(Path(p).is_file() for p in flat))


class TestAggregatorExtensions(unittest.TestCase):
    def test_old_signatures_unchanged(self):
        import inspect
        self.assertEqual(list(inspect.signature(aggregator.aggregate_all).parameters),
                         ["player_id", "start_date", "end_date", "meal_timedelta"])

    def test_trimp_weights(self):
        self.assertAlmostEqual(aggregator.trimp_edwards(
            {"BELOW_DEFAULT_ZONE_1": 100.0, "IN_DEFAULT_ZONE_1": 10.0,
             "IN_DEFAULT_ZONE_2": 5.0, "IN_DEFAULT_ZONE_3": 2.0}), 143.0)

    def test_exercise_artifact_drop(self):
        out = aggregator.exercise_minutes(
            [{"activeDuration": 1000, "activityName": "X"},
             {"activeDuration": 1331000, "activityName": "Walk"}])
        self.assertEqual(out["n_exercise_sessions"], 1)
        self.assertAlmostEqual(out["exercise_min"], 22.2, places=1)

    def test_parsers(self):
        self.assertEqual(aggregator.parse_activity_names("['individual', 'running']"),
                         ["individual", "running"])
        self.assertEqual(aggregator.parse_soreness_area("[]"), ([], False, 0))
        self.assertEqual(aggregator.alcohol_to_bin("Yes"), 1)
        self.assertIsNone(aggregator.alcohol_to_bin("maybe"))
        self.assertAlmostEqual(
            aggregator.reporting_lag_days("06/11/2019", "06/12/2019 21:58:30"), 30.92, places=1)


class TestPreProcessor(unittest.TestCase):
    def test_horizon_is_152_days(self):
        self.assertEqual(len(pre_processor.day_range()), 152)

    def test_wellness_sentinels(self):
        df = pd.DataFrame({"fatigue": [0, 3], "readiness": [0, 7],
                           "sleep_duration_h": [0, 6]})
        out = pre_processor.clean_wellness_frame(df)
        self.assertTrue(np.isnan(out["fatigue"].iloc[0]))
        self.assertTrue(np.isnan(out["readiness_clean"].iloc[0]))
        self.assertEqual(out["readiness_clean"].iloc[1], 7)

    def test_label_is_next_day_causal(self):
        df = pd.DataFrame({
            "participant_id": ["p01"] * 3,
            "date": ["2020-01-01", "2020-01-02", "2020-01-03"],
            "readiness_same_day": [5.0, 6.0, 7.0]})
        out = pre_processor.add_causal_label(df)
        self.assertEqual(list(out["readiness_next_day"][:2]), [6.0, 7.0])
        self.assertTrue(np.isnan(out["readiness_next_day"].iloc[2]))
        self.assertEqual(list(out["label_available"]), [1, 1, 0])

    def test_feature_columns_exclude_label_and_duplicates(self):
        df = pd.DataFrame(columns=["participant_id", "date", "readiness_next_day",
                                   "label_available", "readiness_same_day",
                                   "estimated_kcal", "total_steps",
                                   "total_distance_cm", "total_distance_m"])
        feats = pre_processor.get_feature_columns(df)
        self.assertIn("readiness_same_day", feats)  # allowed lagged feature
        self.assertIn("total_steps", feats)
        self.assertIn("total_distance_cm", feats)
        self.assertIn("estimated_kcal", feats)  # filled day macros are features
        self.assertNotIn("readiness_next_day", feats)
        self.assertNotIn("total_distance_m", feats)  # exact duplicate of cm


if __name__ == "__main__":
    unittest.main()
