"""Dataset loading + LOPO split generation."""

from pathlib import Path

import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATASET_PATH = BASE_DIR / "output_dataset" / "training_dataset.csv"
LABEL = "readiness_next_day"
PLAYER = "participant_id"

import sys
sys.path.insert(0, str(BASE_DIR))
from src.pre_processing.pre_processor import get_feature_columns  # noqa: E402


def load_labeled_frame(path=None):
    """Load the training CSV, keep labeled rows only.

    Returns (frame, used_in_x). Only rows with a known next-day
    readiness can train/evaluate the estimator (290 rows expected).
    """
    df = pd.read_csv(path or DATASET_PATH)
    used_in_x = get_feature_columns(df)
    frame = df[df[LABEL].notna()].reset_index(drop=True)
    return frame, used_in_x


def lopo_splits(frame, player_col=PLAYER):
    """Yield (train_idx, test_idx, test_player) Leave-One-Participant-Out.

    With 3 participants this is 3 folds. The test player's rows never
    appear in train: no player contamination by construction.
    """
    players = sorted(frame[player_col].unique())
    if len(players) < 2:
        raise ValueError("LOPO needs >= 2 participants.")
    for player in players:
        test_mask = frame[player_col] == player
        test_idx = frame.index[test_mask].to_numpy()
        train_idx = frame.index[~test_mask].to_numpy()
        assert len(set(train_idx) & set(test_idx)) == 0
        assert (frame.loc[test_idx, player_col] == player).all()
        yield train_idx, test_idx, player
