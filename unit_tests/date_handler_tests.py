import unittest
from src.utils.date_handler import standardize_date

class TestDateHandler(unittest.TestCase):

    def test_standardize_date_with_time(self):
        # 11/01/19 03:10:00 (Infers DD/MM/YY via slash heuristic)
        self.assertEqual(
            standardize_date("11/01/19 03:10:00"), 
            "2019-01-11 03:10:00.000"
        )
        
        # 11/01/2019 03:10:00 (Infers DD/MM/YYYY via slash heuristic)
        self.assertEqual(
            standardize_date("11/01/2019 03:10:00"), 
            "2019-01-11 03:10:00.000"
        )
        
        # 2019-11-01 03:10:00 (with input format given)
        self.assertEqual(
            standardize_date("2019-11-01 03:10:00", "%Y-%d-%m %H:%M:%S"), 
            "2019-01-11 03:10:00.000"
        )
        
        # 2019-11-01T03:10:00Z (Input format given to interpret 11 as the day)
        self.assertEqual(
            standardize_date("2019-11-01T03:10:00Z", "%Y-%d-%mT%H:%M:%SZ"), 
            "2019-01-11 03:10:00.000"
        )
        
        # 2019-11-01T03:10:00.000 (Input format given to interpret 11 as the day)
        self.assertEqual(
            standardize_date("2019-11-01T03:10:00.000", "%Y-%d-%mT%H:%M:%S.%f"), 
            "2019-01-11 03:10:00.000"
        )
        
        # 2019-01-11T03:10:00.000Z (Standard ISO8601 automatically inferred)
        self.assertEqual(
            standardize_date("2019-01-11T03:10:00.000Z"), 
            "2019-01-11 03:10:00.000"
        )
        # exif format
        self.assertEqual(
            standardize_date("2020:02:01 10:03:41"), 
            "2020-02-01 10:03:41.000"
        )

    def test_standardize_date_without_time(self):
        # 11/01/19
        self.assertEqual(
            standardize_date("11/01/19"), 
            "2019-01-11 00:00:00.000"
        )
        
        # 2019-11-01 (Input format given to interpret 11 as the day)
        self.assertEqual(
            standardize_date("2019-11-01", "%Y-%d-%m"), 
            "2019-01-11 00:00:00.000"
        )

if __name__ == '__main__':
    unittest.main()