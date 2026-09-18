"""Outlier detection and processing (framework §2).

Modules:
- ``sensor_artifacts``: Fitbit confidence filter + minute-series DST dedupe.
- ``physio_bounds``: HR clipping [30, 220], stride/RHR sentinel cleaning.
- ``nonwear``: non-wear minute detection + daily rollup (``is_non_wear``).
- ``meal_grouping``: deterministic 15 s shutter-burst grouping for food
  photos (no vision API calls; counts only).
"""
from src.pre_processing.outliers_handler import (  # noqa: F401
    sensor_artifacts,
    physio_bounds,
    nonwear,
    meal_grouping,
)
