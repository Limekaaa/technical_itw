"""Missing-values handling (framework §3).

- ``forward_fill``: Tier-1 causal forward-fill (<= 2 days) for
  slow-moving signals (7-day median weight, RHR) with ``was_imputed``
  flags. No backfill, no leakage from the future.
- ``indicators``: Tier-2 missingness indicators + causal rolling
  availability ratios for structural block-missingness.
"""
from src.pre_processing.missing_values_handler import (  # noqa: F401
    forward_fill,
    indicators,
)
