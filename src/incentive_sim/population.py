"""Team populations, stored struct-of-arrays for vectorised simulation.

A population is a pair of 2-D float arrays:

    attributes  (n_teams, N_ATTRIBUTES)   fixed for a team's lifetime
    strategy    (n_teams, N_STRATEGY)     evolves within a lifetime

Attributes obey a hard budget (``sum == attribute_budget``) so that evolution has
to *allocate* rather than accumulate — without it every attribute drifts to its
maximum and there is nothing to observe (PLAN.md D2).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import (
    ATTR_IX,
    ATTRIBUTES,
    N_ATTRIBUTES,
    N_STRATEGY,
    STRAT_IX,
    STRATEGY,
    EvolutionConfig,
)


@dataclass
class Population:
    """A league's teams. Mutated in place across seasons."""

    attributes: np.ndarray  # (n, N_ATTRIBUTES) float64
    strategy: np.ndarray  # (n, N_STRATEGY)  float64

    def __post_init__(self) -> None:
        if self.attributes.ndim != 2 or self.attributes.shape[1] != N_ATTRIBUTES:
            raise ValueError(f"attributes must be (n, {N_ATTRIBUTES}), got {self.attributes.shape}")
        if self.strategy.shape != (self.attributes.shape[0], N_STRATEGY):
            raise ValueError(f"strategy must be (n, {N_STRATEGY}), got {self.strategy.shape}")

    @property
    def n_teams(self) -> int:
        return self.attributes.shape[0]

    def attr(self, name: str) -> np.ndarray:
        return self.attributes[:, ATTR_IX[name]]

    def strat(self, name: str) -> np.ndarray:
        return self.strategy[:, STRAT_IX[name]]

    def copy(self) -> Population:
        return Population(self.attributes.copy(), self.strategy.copy())

    def summary(self) -> dict[str, float]:
        """Population means, for the per-season metrics table."""
        out = {f"attr_{n}": float(self.attributes[:, i].mean()) for i, n in enumerate(ATTRIBUTES)}
        out |= {f"strat_{n}": float(self.strategy[:, i].mean()) for i, n in enumerate(STRATEGY)}
        return out


def renormalise_budget(
    attributes: np.ndarray, cfg: EvolutionConfig, *, inplace: bool = False
) -> np.ndarray:
    """Scale each team's attributes to sum to the budget, respecting [min, max].

    A plain rescale can push values outside the bounds, and plain clipping breaks
    the budget. We alternate the two to a fixed point — the feasible set is
    non-empty because the config validator checks
    ``attr_min * N <= budget <= attr_max * N``.
    """
    a = attributes if inplace else attributes.copy()
    np.clip(a, cfg.attr_min, cfg.attr_max, out=a)

    for _ in range(64):
        total = a.sum(axis=1, keepdims=True)
        err = np.abs(total - cfg.attribute_budget).max()
        if err < 1e-9:
            break
        # Distribute the shortfall/excess over the attributes that still have
        # headroom in the required direction, so clipping cannot undo it.
        deficit = cfg.attribute_budget - total  # (n, 1)
        room = np.where(deficit > 0, cfg.attr_max - a, a - cfg.attr_min)
        room_total = room.sum(axis=1, keepdims=True)
        # Fully saturated rows cannot move; leave them (unreachable given the
        # config validator, but never divide by zero).
        share = np.divide(room, room_total, out=np.zeros_like(room), where=room_total > 1e-12)
        a += share * deficit
        np.clip(a, cfg.attr_min, cfg.attr_max, out=a)

    return a


def true_strength(pop: Population, base_points: float, skill_scale: float,
                   overreach_penalty: float, signal_cost: float) -> np.ndarray:
    """Each team's real per-possession scoring rate against a neutral opponent.

    This is the ground truth the reward function may or may not track. It is what
    a team is actually worth on the court, after paying for aggression it cannot
    carry and for effort diverted into looking good.
    """
    offense = pop.attr("offense")
    off_emphasis = pop.strat("off_emphasis")
    aggression = pop.strat("aggression")
    risk_capacity = pop.attr("risk_capacity")
    signal_effort = pop.strat("signal_effort")

    # Neutral reference defender: defense 0.5, emphasis 0.5.
    skill = offense * off_emphasis - 0.25
    mean = base_points * (1.0 + skill_scale * skill)
    mean = mean * (1.0 - overreach_penalty * np.maximum(0.0, aggression - risk_capacity) ** 2)
    mean = mean * (1.0 - signal_cost * signal_effort)
    return np.maximum(mean, 0.0)


def rank_normalised(values: np.ndarray) -> np.ndarray:
    """Percentile rank in [0, 1] — a scale-free view of who is actually best."""
    order = np.argsort(np.argsort(values))
    return order / max(1, values.size - 1)


def initial_population(
    n_teams: int, rng: np.random.Generator, cfg: EvolutionConfig
) -> Population:
    """Create a fresh, identically-distributed population.

    Both leagues call this with the same seed, so their t=0 populations are
    byte-identical (PLAN.md §8).
    """
    # Dirichlet gives a natural spread of allocations that already respects the
    # budget in expectation; renormalise_budget makes it exact.
    weights = rng.dirichlet(np.full(N_ATTRIBUTES, 12.0), size=n_teams)
    attributes = renormalise_budget(weights * cfg.attribute_budget, cfg, inplace=True)

    # Strategy starts mid-range with mild noise: no built-in bias toward
    # aggressive or conservative play in either league.
    strategy = np.clip(rng.normal(0.5, 0.08, size=(n_teams, N_STRATEGY)), 0.0, 1.0)

    return Population(attributes, strategy)
