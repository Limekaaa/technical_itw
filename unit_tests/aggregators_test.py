import unittest
from src.data_handling import fitbit_reader, pmsys_reader, reporting_reader
import pandas as pd


class TestFitbitReader(unittest.TestCase):
    def test_calories_reader_range(self):
        result = fitbit_reader.calories_reader("p01", "2019-11-01 00:00:00", "2019-11-01 00:05:00")
        expected = pd.Series(
            [1.39, 1.39, 1.39, 1.39, 1.39],
            index=pd.date_range("2019-11-01 00:00:00", "2019-11-01 00:04:00", freq="min"),
        )
        pd.testing.assert_series_equal(result, expected, check_freq=False)

    def test_distance_reader_range(self):
        result = fitbit_reader.distance_reader("p01", "2019-11-01 00:00:00", "2019-11-01 00:05:00")
        expected = pd.Series(
            [0.0, 0.0, 0.0, 0.0, 0.0],
            index=pd.date_range("2019-11-01 00:00:00", "2019-11-01 00:04:00", freq="min"),
        )
        pd.testing.assert_series_equal(result, expected, check_freq=False)

    def test_steps_reader_range(self):
        result = fitbit_reader.steps_reader("p01", "2019-11-01 00:00:00", "2019-11-01 00:05:00")
        expected = pd.Series(
            [0.0, 0.0, 0.0, 0.0, 0.0],
            index=pd.date_range("2019-11-01 00:00:00", "2019-11-01 00:04:00", freq="min"),
        )
        pd.testing.assert_series_equal(result, expected, check_freq=False)

    def test_flat_series_single_date_means_full_day(self):
        result = fitbit_reader.calories_reader("p01", "2019-11-01")
        self.assertIsInstance(result, pd.Series)
        self.assertGreater(len(result), 0)
        # every timestamp must fall on the requested calendar day
        self.assertTrue((result.index.normalize() == pd.Timestamp("2019-11-01")).all())

    def test_heart_rate_reader_nested_dict(self):
        result = fitbit_reader.heart_rate_reader("p01", "2019-11-01 00:00:00", "2019-11-01 00:01:00")
        self.assertIsInstance(result, dict)
        self.assertIn("2019-11-01 00:00:05.000", result)
        self.assertEqual(result["2019-11-01 00:00:05.000"], {"bpm": 54, "confidence": 3})

    def test_heart_rate_reader_missing_file(self):
        # p03 has no heart_rate.json -> empty dict
        result = fitbit_reader.heart_rate_reader("p03", "2019-11-01", "2019-11-02")
        self.assertEqual(result, {})

    def test_resting_heart_rate_reader_nested_dict(self):
        result = fitbit_reader.resting_heart_rate_reader("p01", "2019-11-01", "2019-11-01")
        self.assertIsInstance(result, dict)
        self.assertIn("2019-11-01 00:00:00.000", result)
        self.assertAlmostEqual(result["2019-11-01 00:00:00.000"]["value"], 53.74107360839844)

    def test_time_in_heart_rate_zones_reader_nested_dict(self):
        result = fitbit_reader.time_in_heart_rate_zones_reader("p01", "2019-11-01", "2019-11-01")
        self.assertIsInstance(result, dict)
        self.assertIn("2019-11-01 00:00:00.000", result)
        self.assertAlmostEqual(result["2019-11-01 00:00:00.000"]["BELOW_DEFAULT_ZONE_1"], 1254.0)

    def test_sleep_reader_nested_dict(self):
        result = fitbit_reader.sleep_reader("p01", "2019-11-02", "2019-11-02")
        self.assertIsInstance(result, dict)
        self.assertIn(24486013387, result)
        self.assertEqual(result[24486013387]["dateOfSleep"], "2019-11-02")

    def test_exercise_reader_nested_dict(self):
        result = fitbit_reader.exercise_reader("p01", "2019-11-01", "2019-11-01")
        self.assertIsInstance(result, dict)
        self.assertIn(26451905128, result)
        self.assertEqual(result[26451905128]["activityName"], "Walk")

    def test_sleep_score_reader_dataframe(self):
        result = fitbit_reader.sleep_score_reader("p01", "2019-11-01", "2019-11-02")
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertEqual(int(result.iloc[0]["overall_score"]), 76)

    def test_unknown_player_returns_empty(self):
        self.assertEqual(len(fitbit_reader.calories_reader("p99", "2019-11-01", "2019-11-02")), 0)
        self.assertEqual(fitbit_reader.sleep_reader("p99", "2019-11-01", "2019-11-02"), {})

    def test_out_of_range_returns_empty(self):
        self.assertEqual(len(fitbit_reader.calories_reader("p01", "2000-01-01", "2000-01-02")), 0)
        self.assertEqual(fitbit_reader.sleep_reader("p01", "2000-01-01", "2000-01-02"), {})


class TestPmsysReader(unittest.TestCase):
    def test_wellness_reader_dataframe(self):
        result = pmsys_reader.wellness_reader("p01", "2019-11-01", "2019-11-02")
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 2)
        self.assertEqual(int(result.iloc[0]["fatigue"]), 2)

    def test_wellness_reader_single_date_means_full_day(self):
        result = pmsys_reader.wellness_reader("p01", "2019-11-01")
        self.assertEqual(len(result), 1)
        self.assertEqual(int(result.iloc[0]["mood"]), 3)

    def test_srpe_reader_dataframe(self):
        result = pmsys_reader.srpe_reader("p01", "2019-11-05", "2019-11-05")
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1)
        self.assertEqual(int(result.iloc[0]["perceived_exertion"]), 7)
        self.assertEqual(int(result.iloc[0]["duration_min"]), 30)

    def test_injury_reader_nested_dict(self):
        result = pmsys_reader.injury_reader("p01", "2020-01-07", "2020-01-07")
        self.assertIsInstance(result, dict)
        self.assertEqual(len(result), 1)
        key = next(iter(result))
        self.assertIn("2020-01-07", key)
        self.assertEqual(result[key], {"right_hand": "minor"})

    def test_injury_reader_empty_injury_preserved(self):
        result = pmsys_reader.injury_reader("p01", "2019-11-07", "2019-11-07")
        self.assertEqual(len(result), 1)
        self.assertEqual(next(iter(result.values())), {})

    def test_unknown_player_returns_empty(self):
        self.assertEqual(len(pmsys_reader.wellness_reader("p99", "2019-11-01", "2019-11-02")), 0)
        self.assertEqual(pmsys_reader.injury_reader("p99", "2019-11-01", "2019-11-02"), {})


class TestReportingReader(unittest.TestCase):
    def test_reporting_reader_single_date_means_full_day(self):
        result = reporting_reader.reporting_reader("p01", "06/11/2019")
        self.assertIsInstance(result, pd.DataFrame)
        self.assertEqual(len(result), 1)
        self.assertAlmostEqual(float(result.iloc[0]["weight"]), 100.0)
        self.assertEqual(int(result.iloc[0]["glasses_of_fluid"]), 7)

    def test_reporting_reader_range(self):
        result = reporting_reader.reporting_reader("p01", "06/11/2019", "10/11/2019")
        self.assertGreaterEqual(len(result), 3)

    def test_unknown_player_returns_empty(self):
        self.assertEqual(len(reporting_reader.reporting_reader("p99", "06/11/2019", "10/11/2019")), 0)


if __name__ == "__main__":
    unittest.main()
