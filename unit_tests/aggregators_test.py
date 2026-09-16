import unittest
from pathlib import Path
from unittest import mock
from src.data_handling import fitbit_reader, pmsys_reader, reporting_reader, food_reader, aggregator
import pandas as pd

_DATA_DIR = Path(__file__).resolve().parents[1] / "data"


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


CANNED_MACROS_JSON = '{"calories": 500, "protein": 20, "carbohydrates": 60, "fats": 15}'
CANNED_MACROS = {"calories": 500, "protein": 20, "carbohydrates": 60, "fats": 15}


def _mock_client(answer):
    client = mock.MagicMock()
    client.interactions.create.return_value.output_text = answer
    return client


class TestFoodReader(unittest.TestCase):
    def test_helper_parses_macro_json(self):
        photo = str(_DATA_DIR / "p01" / "food-images" / "IMG_8916.jpeg")
        with mock.patch.object(food_reader, "client", _mock_client(CANNED_MACROS_JSON)):
            self.assertEqual(
                food_reader.helper_get_macro_nutrients_from_photos([photo]),
                CANNED_MACROS,
            )

    def test_helper_no_json_returns_empty(self):
        photo = str(_DATA_DIR / "p01" / "food-images" / "IMG_8916.jpeg")
        with mock.patch.object(food_reader, "client", _mock_client("not food")):
            self.assertEqual(
                food_reader.helper_get_macro_nutrients_from_photos([photo]), {}
            )

    def test_is_photo_food_yes_no(self):
        photo = str(_DATA_DIR / "p01" / "food-images" / "IMG_8916.jpeg")
        with mock.patch.object(food_reader, "client", _mock_client("YES")):
            self.assertTrue(food_reader.is_photo_food(photo))
        with mock.patch.object(food_reader, "client", _mock_client("NO")):
            self.assertFalse(food_reader.is_photo_food(photo))

    def test_image_part_uses_data_key(self):
        photo = str(_DATA_DIR / "p01" / "food-images" / "IMG_8916.jpeg")
        client = _mock_client("YES")
        with mock.patch.object(food_reader, "client", client):
            food_reader.is_photo_food(photo)
        text_part, img_part = client.interactions.create.call_args.kwargs["input"]
        self.assertEqual(text_part["type"], "text")
        self.assertEqual(img_part["type"], "image")
        self.assertIn("data", img_part)
        self.assertNotIn("image_data", img_part)
        self.assertEqual(img_part["mime_type"], "image/jpeg")

    def test_helper_sends_response_format_schema(self):
        photo = str(_DATA_DIR / "p01" / "food-images" / "IMG_8916.jpeg")
        client = _mock_client(CANNED_MACROS_JSON)
        with mock.patch.object(food_reader, "client", client):
            food_reader.helper_get_macro_nutrients_from_photos([photo])
        kwargs = client.interactions.create.call_args.kwargs
        self.assertEqual(
            kwargs["response_format"]["schema"]["required"],
            ["calories", "protein", "carbohydrates", "fats"],
        )

    def test_is_it_same_meal_yes(self):
        folder = _DATA_DIR / "p01" / "food-images"
        pair = (
            (str(folder / "IMG_8916.jpeg"), "2019-11-02 12:00:00.000"),
            (str(folder / "IMG_8917.jpeg"), "2019-11-02 12:05:00.000"),
        )
        with mock.patch.object(food_reader, "client", _mock_client("YES")):
            self.assertTrue(food_reader.is_it_same_meal(*pair))

    def test_preselector_with_dated_tuples(self):
        from datetime import datetime

        files = [
            ("a.jpg", datetime(2020, 1, 1, 12, 0, 0)),
            ("b.jpg", datetime(2020, 1, 1, 12, 10, 0)),
        ]
        self.assertEqual(
            food_reader.same_meal_preselector(files, 1800),
            {"a.jpg": ["b.jpg"], "b.jpg": ["a.jpg"]},
        )

    def test_pipeline_single_real_photo(self):
        photo = str(_DATA_DIR / "p01" / "food-images" / "IMG_8916.jpeg")
        with mock.patch.object(food_reader, "is_photo_food", return_value=True), \
             mock.patch.object(food_reader, "client", _mock_client(CANNED_MACROS_JSON)):
            result = food_reader.get_macro_nutrients_from_photos([photo])
        self.assertEqual(result, {(photo,): CANNED_MACROS})

    def test_pipeline_empty_input(self):
        self.assertEqual(food_reader.get_macro_nutrients_from_photos([]), {})

    def test_photo_selector_unknown_player(self):
        self.assertEqual(food_reader.photo_selector_by_date_player("p99", "2019-11-01"), [])

    def test_photo_selector_returns_list(self):
        result = food_reader.photo_selector_by_date_player("p01", "2019-11-01", "2020-03-31")
        self.assertIsInstance(result, list)


class TestAggregator(unittest.TestCase):
    def test_aggregate_all_keys(self):
        result = aggregator.aggregate_all("p01", "2019-11-02")
        self.assertEqual(
            sorted(result),
            ["activity", "end_date", "injury", "nutrition", "player_id", "questionnaire", "sleep", "start_date"],
        )
        self.assertEqual(result["start_date"], "2019-11-02")
        self.assertEqual(result["end_date"], "2019-11-02")

    def test_sleep_morning_attribution(self):
        result = aggregator.aggregate_sleep("p01", "2019-11-02")
        self.assertTrue(result["has_sleep_record"])
        nights = {n["date_of_sleep"] for n in result["nights"]}
        self.assertIn("2019-11-02", nights)
        night = next(n for n in result["nights"] if n["date_of_sleep"] == "2019-11-02")
        self.assertEqual(night["minutes_asleep"], 378)

    def test_activity_window_sums(self):
        result = aggregator.aggregate_activity("p01", "2019-11-01", "2019-11-02")
        expected = float(
            fitbit_reader.steps_reader("p01", "2019-11-01", "2019-11-02").sum()
        )
        self.assertAlmostEqual(result["total_steps"], expected)

    def test_nutrition_meal_count(self):
        result = aggregator.aggregate_nutrition("p01", "06/11/2019")
        self.assertEqual(result["n_meals_logged"], 2)
        self.assertEqual(result["meal_names"], ["Breakfast", "Dinner"])

    def test_injury_flag(self):
        result = aggregator.aggregate_injury("p01", "2020-01-07")
        self.assertTrue(result["is_injured"])
        self.assertIn("right_hand", next(iter(result["injuries"].values())))

    def test_render_markdown(self):
        report = aggregator.render(aggregator.aggregate_all("p01", "2019-11-02"))
        self.assertIn("# Daily report — p01 — 2019-11-02", report)
        self.assertIn("## Nutrition", report)
        self.assertNotIn("placeholder", report)

    def test_format_distance_units(self):
        self.assertEqual(aggregator.format_distance(45), "45 cm")
        self.assertEqual(aggregator.format_distance(2500), "25 m")
        self.assertEqual(aggregator.format_distance(750000), "7.5 km")
        self.assertEqual(aggregator.format_distance(None), "n/a")

    def test_activity_distance_display(self):
        result = aggregator.aggregate_activity("p01", "2019-11-01")
        self.assertIn("total_distance_display", result)
        self.assertTrue(
            result["total_distance_display"].endswith(("cm", "m", "km"))
        )

    def test_render_missing_data_shows_na(self):
        report = aggregator.render(aggregator.aggregate_all("p99", "2019-11-02"))
        self.assertIn("n/a", report)


if __name__ == "__main__":
    unittest.main()
