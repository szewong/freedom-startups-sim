"""Reward functions — the one and only difference between leagues.

    reward = 1 if (margin >= threshold) else 0

League A is threshold 1 ("a win is a win"), League B is threshold 5 ("only win
by 5+ counts"). Same code path, one parameter. Everything else in the simulation
is shared.
"""

from __future__ import annotations

import numpy as np


def reward_from_margin(margin: np.ndarray, threshold: int) -> np.ndarray:
    """Binary reward for the team whose point margin this is."""
    return (margin >= threshold).astype(np.float64)


def pair_rewards(
    score_a: np.ndarray, score_b: np.ndarray, threshold: int
) -> tuple[np.ndarray, np.ndarray]:
    """Rewards for both sides of a batch of games."""
    margin = score_a - score_b
    return (
        reward_from_margin(margin, threshold),
        reward_from_margin(-margin, threshold),
    )
