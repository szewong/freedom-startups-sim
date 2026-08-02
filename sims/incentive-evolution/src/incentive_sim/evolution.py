"""Slow channel: between-season selection and reproduction.

The bottom ``replace_fraction`` of teams are replaced by mutated copies of the
top performers. Attributes and strategy are both inherited and both mutated;
attributes are re-normalised to the budget so evolution has to *allocate*
rather than accumulate.

**This is the primary driver of divergence.** A 3-percentage-point reward edge is
invisible to a single team over any realistic window, but as a selection
coefficient of s ~ 0.08 across a 64-team population it is very strong, and it
compounds over hundreds of seasons.
"""

from __future__ import annotations

import numpy as np

from .config import EvolutionConfig
from .learning import Learner
from .population import Population, renormalise_budget


def reproduce(
    pop: Population,
    learner: Learner,
    season_reward: np.ndarray,
    cfg: EvolutionConfig,
    rng: np.random.Generator,
    inherit: np.ndarray | None = None,
) -> np.ndarray:
    """Replace the worst teams with mutated offspring of the best.

    `inherit` is any per-team tag that offspring take from their parent — used to
    trace lineage through an invasion experiment. Mutated in place.

    Returns the indices that were replaced.
    """
    n = pop.n_teams
    n_replace = max(1, int(round(cfg.replace_fraction * n)))

    order = np.argsort(season_reward, kind="stable")
    losers = order[:n_replace]
    winners = order[-n_replace:]

    # Each open slot draws a parent from the top cohort, with replacement, so a
    # standout team can seed more than one offspring.
    parents = rng.choice(winners, size=n_replace, replace=True)

    child_attributes = pop.attributes[parents] + rng.normal(
        0.0, cfg.attr_mutation, size=(n_replace, pop.attributes.shape[1])
    )
    renormalise_budget(child_attributes, cfg, inplace=True)

    child_strategy = np.clip(
        learner.incumbent[parents]
        + rng.normal(0.0, cfg.strategy_mutation, size=(n_replace, pop.strategy.shape[1])),
        0.0,
        1.0,
    )

    pop.attributes[losers] = child_attributes
    learner.reset_teams(losers, child_strategy, pop)

    if inherit is not None:
        inherit[losers] = inherit[parents]

    return losers
