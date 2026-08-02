"""Vectorised possession-level match engine.

Every call simulates a whole *batch* of independent games at once — there is no
per-game Python loop anywhere, which is what makes ~40M games tractable
(PLAN.md §3).

The engine is deliberately **reward-blind**: nothing in this module knows what a
league's win threshold is. Divergence between leagues must emerge from the
learning loop acting on strategy, never from the physics of the game.

Three levers, deliberately non-aligned so no single strategy dominates
(PLAN.md §5):

* ``aggression``   raises per-possession variance always; raises efficiency only
                   up to the team's ``risk_capacity``, then costs mean. This is
                   the price of buying variance.
* ``tempo``        raises possession count, so total mean grows ∝ P while total
                   σ grows ∝ √P — higher tempo *reduces* relative variance.
                   Opposite sign to aggression.
* ``endgame_conservatism`` / ``margin_seeking`` act on a *leading* team in the
                   final segment, damping or inflating variance respectively.
"""

from __future__ import annotations

import numpy as np

from .config import ATTR_IX, STRAT_IX, MatchConfig
from .population import Population

_MIN_MEAN = 0.05
_OVERTIME_POSSESSIONS = 6.0
_MAX_OVERTIMES = 20


def _fatigue(pop: Population, idx: np.ndarray, games_played: np.ndarray, cfg: MatchConfig):
    """Performance decay from games already played in this tournament run."""
    aggression = pop.strategy[idx, STRAT_IX["aggression"]]
    stamina = pop.attributes[idx, ATTR_IX["stamina"]]
    f = (
        cfg.fatigue_per_game
        * games_played
        * (1.0 + cfg.fatigue_aggression_gain * aggression)
        * (1.0 - cfg.fatigue_stamina_damp * stamina)
    )
    return np.clip(f, 0.0, 0.6)


def _per_possession(
    pop: Population,
    attack: np.ndarray,
    defend: np.ndarray,
    fatigue: np.ndarray,
    cfg: MatchConfig,
) -> tuple[np.ndarray, np.ndarray]:
    """Per-possession expected points and variance for `attack` facing `defend`."""
    offense = pop.attributes[attack, ATTR_IX["offense"]]
    off_emphasis = pop.strategy[attack, STRAT_IX["off_emphasis"]]
    defense = pop.attributes[defend, ATTR_IX["defense"]]
    def_emphasis = pop.strategy[defend, STRAT_IX["def_emphasis"]]
    aggression = pop.strategy[attack, STRAT_IX["aggression"]]
    risk_capacity = pop.attributes[attack, ATTR_IX["risk_capacity"]]
    ambition = pop.strategy[attack, STRAT_IX["ambition"]]

    skill = offense * off_emphasis - defense * def_emphasis
    mean = cfg.base_points * (1.0 + cfg.skill_scale * skill)

    # Aggression beyond what the team can carry costs efficiency, quadratically.
    overreach = np.maximum(0.0, aggression - risk_capacity)
    mean = mean * (1.0 - cfg.overreach_penalty * overreach**2)
    # Capital funds the work.
    mean = mean * (1.0 + cfg.capital_gain * ambition)
    mean = np.maximum(mean * (1.0 - fatigue), _MIN_MEAN)

    variance = cfg.base_variance * (1.0 + cfg.variance_gain * aggression)
    return mean, variance


def _endgame_multipliers(
    pop: Population, idx: np.ndarray, leading: np.ndarray, cfg: MatchConfig
) -> tuple[np.ndarray, np.ndarray]:
    """Mean/variance multipliers applied to a *leading* team in the final segment.

    A team protecting a win wants variance down; a team chasing a margin wants it
    up. Both knobs are available to every team in every league — which one the
    population learns to use is the entire experiment.
    """
    conservatism = pop.strategy[idx, STRAT_IX["endgame_conservatism"]]
    margin_seeking = pop.strategy[idx, STRAT_IX["margin_seeking"]]

    var_mult = (1.0 - cfg.endgame_variance_damp * conservatism) * (
        1.0 + cfg.margin_seek_variance_gain * margin_seeking
    )
    mean_mult = 1.0 - cfg.endgame_mean_cost * conservatism

    return (
        np.where(leading, mean_mult, 1.0),
        np.where(leading, var_mult, 1.0),
    )


def simulate_games(
    pop: Population,
    idx_a: np.ndarray,
    idx_b: np.ndarray,
    games_played_a: np.ndarray,
    games_played_b: np.ndarray,
    cfg: MatchConfig,
    rng: np.random.Generator,
) -> tuple[np.ndarray, np.ndarray]:
    """Simulate ``len(idx_a)`` independent games. Returns integer (score_a, score_b).

    Games are guaranteed to have a winner: ties go to overtime.
    """
    idx_a = np.asarray(idx_a)
    idx_b = np.asarray(idx_b)
    if idx_a.shape != idx_b.shape:
        raise ValueError(f"pairing shape mismatch: {idx_a.shape} vs {idx_b.shape}")

    fatigue_a = _fatigue(pop, idx_a, np.asarray(games_played_a, dtype=float), cfg)
    fatigue_b = _fatigue(pop, idx_b, np.asarray(games_played_b, dtype=float), cfg)

    mean_a, var_a = _per_possession(pop, idx_a, idx_b, fatigue_a, cfg)
    mean_b, var_b = _per_possession(pop, idx_b, idx_a, fatigue_b, cfg)

    # Both teams get the same number of possessions; tempo is a joint decision.
    tempo = 0.5 * (
        pop.strategy[idx_a, STRAT_IX["tempo"]] + pop.strategy[idx_b, STRAT_IX["tempo"]]
    )
    possessions = cfg.base_possessions + cfg.tempo_scale * tempo
    per_segment = possessions / cfg.n_segments

    score_a = np.zeros(idx_a.shape, dtype=float)
    score_b = np.zeros(idx_b.shape, dtype=float)

    for segment in range(cfg.n_segments):
        mean_mult_a = mean_mult_b = var_mult_a = var_mult_b = 1.0

        if segment == cfg.n_segments - 1:
            margin = score_a - score_b
            mean_mult_a, var_mult_a = _endgame_multipliers(pop, idx_a, margin > 0, cfg)
            mean_mult_b, var_mult_b = _endgame_multipliers(pop, idx_b, margin < 0, cfg)

        score_a += np.maximum(
            rng.normal(
                per_segment * mean_a * mean_mult_a,
                np.sqrt(per_segment * var_a * var_mult_a),
            ),
            0.0,
        )
        score_b += np.maximum(
            rng.normal(
                per_segment * mean_b * mean_mult_b,
                np.sqrt(per_segment * var_b * var_mult_b),
            ),
            0.0,
        )

    final_a = np.rint(score_a).astype(np.int64)
    final_b = np.rint(score_b).astype(np.int64)

    # Overtime for ties. Brackets need a winner, and a tie is not a meaningful
    # outcome for either reward function.
    for _ in range(_MAX_OVERTIMES):
        tied = np.flatnonzero(final_a == final_b)
        if tied.size == 0:
            break
        ot_a = rng.normal(
            _OVERTIME_POSSESSIONS * mean_a[tied],
            np.sqrt(_OVERTIME_POSSESSIONS * var_a[tied]),
        )
        ot_b = rng.normal(
            _OVERTIME_POSSESSIONS * mean_b[tied],
            np.sqrt(_OVERTIME_POSSESSIONS * var_b[tied]),
        )
        final_a[tied] += np.rint(np.maximum(ot_a, 0.0)).astype(np.int64)
        final_b[tied] += np.rint(np.maximum(ot_b, 0.0)).astype(np.int64)
    else:
        # Astronomically unlikely; break the deadlock rather than loop forever.
        tied = np.flatnonzero(final_a == final_b)
        final_a[tied] += 1

    return final_a, final_b
