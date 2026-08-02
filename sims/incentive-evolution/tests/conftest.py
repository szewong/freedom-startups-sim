from __future__ import annotations

import numpy as np
import pytest

from incentive_sim.config import ATTR_IX, N_ATTRIBUTES, N_STRATEGY, STRAT_IX, MatchConfig
from incentive_sim.population import Population


@pytest.fixture
def match_cfg() -> MatchConfig:
    return MatchConfig()


def make_population(specs: list[dict[str, float]]) -> Population:
    """Build a population from explicit overrides on a neutral 0.5 baseline.

    Intentionally bypasses the attribute budget: these are engine probes, not
    evolved teams, and holding everything but one attribute fixed is the point.
    """
    n = len(specs)
    attributes = np.full((n, N_ATTRIBUTES), 0.5)
    strategy = np.full((n, N_STRATEGY), 0.5)
    for row, spec in enumerate(specs):
        for key, value in spec.items():
            if key in ATTR_IX:
                attributes[row, ATTR_IX[key]] = value
            elif key in STRAT_IX:
                strategy[row, STRAT_IX[key]] = value
            else:
                raise KeyError(f"unknown attribute/strategy field: {key}")
    return Population(attributes, strategy)


def play(pop, cfg, rng, a: int, b: int, n_games: int):
    """Run `n_games` between team `a` and team `b`, fresh legs. Returns margins."""
    from incentive_sim.match import simulate_games

    idx_a = np.full(n_games, a)
    idx_b = np.full(n_games, b)
    zeros = np.zeros(n_games)
    score_a, score_b = simulate_games(pop, idx_a, idx_b, zeros, zeros, cfg, rng)
    return score_a - score_b


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(np.random.SeedSequence(12345)))
