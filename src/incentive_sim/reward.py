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


def personal_bar(ambition: np.ndarray, max_bar: int) -> np.ndarray:
    """The margin a team must clear, set by its own ambition."""
    return np.maximum(1.0, np.rint(ambition * max_bar))


def endogenous_reward(
    margin: np.ndarray, ambition: np.ndarray, max_bar: int, prize_slope: float
) -> np.ndarray:
    """Score against a self-chosen bar, paying more for clearing a higher one.

    This is the founder's trade in one line: aim higher and the prize grows, but
    so does the margin below which you are paid nothing at all.
    """
    cleared = margin >= personal_bar(ambition, max_bar)
    return np.where(cleared, 1.0 + prize_slope * ambition, 0.0)
