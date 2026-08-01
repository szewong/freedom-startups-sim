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


def perceived_signal(
    signal_effort: np.ndarray, true_rank: np.ndarray, discernment: float
) -> np.ndarray:
    """What the world *thinks* it sees when it looks at a team.

    `discernment` is how much of the observed signal is genuine quality rather
    than effort spent on appearances. At 0 the signal is pure theatre and can be
    bought outright; at 1 it tracks real strength and effort buys nothing.
    """
    return (1.0 - discernment) * signal_effort + discernment * true_rank


def blended_reward(
    margin: np.ndarray, threshold: int, signal_bonus: np.ndarray, signal_weight: float
) -> np.ndarray:
    """Score = mostly results, partly a proxy the team can buy directly."""
    result = reward_from_margin(margin, threshold)
    if signal_weight <= 0.0:
        return result
    return (1.0 - signal_weight) * result + signal_weight * signal_bonus
