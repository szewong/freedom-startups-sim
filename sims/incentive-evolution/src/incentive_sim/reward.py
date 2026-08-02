"""Reward functions — the one and only difference between leagues.

    reward = 1 if (margin >= threshold) else 0

League A is threshold 1 ("a win is a win"), League B is threshold 5 ("only win
by 5+ counts"). Same code path, one parameter. Everything else in the simulation
is shared.
"""

from __future__ import annotations

import numpy as np


def reward_from_margin(
    margin: np.ndarray, threshold: int, graded: bool = False
) -> np.ndarray:
    """Reward for the team whose point margin this is.

    `graded` swaps the step for a ramp: partial credit for partial progress
    toward the same bar, capped at 1. Same bar, same maximum, same direction —
    the only difference is whether falling short scores nothing or scores
    something. This separates the *height* of a bar from its all-or-nothing
    *shape*, which are easy to conflate.
    """
    if not graded:
        return (margin >= threshold).astype(np.float64)
    return np.clip(margin / max(threshold, 1), 0.0, 1.0)


def pair_rewards(
    score_a: np.ndarray, score_b: np.ndarray, threshold: int, graded: bool = False
) -> tuple[np.ndarray, np.ndarray]:
    """Rewards for both sides of a batch of games."""
    margin = score_a - score_b
    return (
        reward_from_margin(margin, threshold, graded),
        reward_from_margin(-margin, threshold, graded),
    )
