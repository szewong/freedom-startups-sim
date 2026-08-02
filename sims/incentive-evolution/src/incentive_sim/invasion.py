"""Invasion analysis: put both upbringings in one league and see whose lineage wins.

This answers a different question from the payoff curve. Not "which population is
better" — that has no rule-independent answer — but **whose strategies take over
when they have to compete directly**.

The result depends entirely on the rule the combined league runs, which is the
point. So we run three:

* ``bar_1``   — League A's home rule
* ``bar_5``   — League B's home rule
* ``shifting`` — the bar is redrawn at random every season, and no team is told

The third is the one that matters for the thesis. It asks which upbringing
survives a world whose rules you do not know in advance. Teams cannot observe the
threshold; they only feel the reward, so nobody can adapt to a bar that keeps
moving.

Lineage is traced through reproduction: an offspring inherits its parent's tag,
so the share is a genuine measure of ancestry, not of who happens to be winning
this season.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import numpy as np

from .config import RunConfig
from .evolution import reproduce
from .learning import Learner
from .population import Population
from .tournament import play_bracket, play_regular_season, seed_from_reward

A_BRED, B_BRED = 0, 1

SHIFTING_BARS = (1, 2, 3, 4, 5, 6, 7, 8, 9, 10)


def fixed_rule(threshold: int) -> Callable[[np.random.Generator], int]:
    return lambda rng: threshold


def shifting_rule(rng: np.random.Generator) -> int:
    """A bar nobody can plan for."""
    return int(rng.choice(SHIFTING_BARS))


def build_rules(cfg: RunConfig) -> tuple[dict[str, Callable], dict[str, str]]:
    """The two leagues' home rules, plus a bar that will not sit still.

    Derived from the run's actual thresholds rather than hardcoded, so this works
    unchanged whether League B needs to win by 5 or by 10.
    """
    rules: dict[str, Callable[[np.random.Generator], int]] = {}
    labels: dict[str, str] = {}

    for league in cfg.leagues:
        key = f"bar_{league.win_threshold}"
        rules[key] = fixed_rule(league.win_threshold)
        labels[key] = (
            f"Judged at bar {league.win_threshold} — League {league.name}'s rule"
        )

    rules["shifting"] = shifting_rule
    labels["shifting"] = (
        f"Bar redrawn every season ({SHIFTING_BARS[0]}–{SHIFTING_BARS[-1]}) — nobody is told"
    )
    return rules, labels


@dataclass
class InvasionResult:
    rule: str
    share_b: list[float] = field(default_factory=list)
    mean_aggression: list[float] = field(default_factory=list)
    thresholds: list[int] = field(default_factory=list)

    @property
    def final_share_b(self) -> float:
        return self.share_b[-1]


def seed_combined_league(
    pop_a: Population, pop_b: Population, n_teams: int, rng: np.random.Generator
) -> tuple[Population, np.ndarray]:
    """Half the field from each league, drawn at random.

    Deliberately *not* "the best 32" — ranking them first would mean picking a
    metric, and the metric would decide the outcome before the league started.
    """
    half = n_teams // 2
    pick_a = rng.choice(pop_a.n_teams, size=half, replace=False)
    pick_b = rng.choice(pop_b.n_teams, size=half, replace=False)

    combined = Population(
        np.concatenate([pop_a.attributes[pick_a], pop_b.attributes[pick_b]]),
        np.concatenate([pop_a.strategy[pick_a], pop_b.strategy[pick_b]]),
    )
    lineage = np.concatenate(
        [np.full(half, A_BRED, dtype=np.int8), np.full(half, B_BRED, dtype=np.int8)]
    )
    return combined, lineage


def run_invasion(
    pop_a: Population,
    pop_b: Population,
    rule: str,
    seasons: int,
    cfg: RunConfig,
    rng: np.random.Generator,
) -> InvasionResult:
    """Run one combined league to convergence under `rule`."""
    draw_bar = build_rules(cfg)[0][rule]
    pop, lineage = seed_combined_league(pop_a, pop_b, cfg.tournament.n_teams, rng)
    learner = Learner(pop, cfg.learning, rng)

    result = InvasionResult(rule=rule)

    for _ in range(seasons):
        threshold = draw_bar(rng)

        reward, games = play_regular_season(
            pop, threshold, cfg.tournament, cfg.match, rng
        )
        seeds = seed_from_reward(reward, rng)
        play_bracket(pop, seeds, threshold, cfg.match, rng, reward, games)

        # The fast channel still runs, but it is a fine-tuner; ancestry is
        # decided by selection.
        learner.record(np.arange(pop.n_teams), reward / np.maximum(games, 1))
        learner.settle(pop)

        reproduce(pop, learner, reward, cfg.evolution, rng, inherit=lineage)

        result.share_b.append(float((lineage == B_BRED).mean()))
        result.mean_aggression.append(float(pop.strat("aggression").mean()))
        result.thresholds.append(threshold)

    return result
