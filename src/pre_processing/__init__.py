"""Pre-processing package: training-ready dataset builders.

Subpackages:
- ``outliers_handler``: sensor-artifact, physiological-bound, non-wear
  and meal-grouping cleaners (framework §2).
- ``missing_values_handler``: Tier-1 causal forward-fill and Tier-2
  missingness indicators (framework §3).

The orchestrator lives in ``pre_processor.py``. Type-management
helpers (§1: timestamps, sentinels, categorical encoding, unit
conversions) live there as well, since they are not aggregations.
"""
