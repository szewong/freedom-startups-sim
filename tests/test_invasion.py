"""Invasion analysis correctness.

Lineage bookkeeping is the whole measurement here — if ancestry is traced wrong,
the fixation numbers are meaningless while still looking plausible.
"""

from __future__ import annotations

import numpy as np
import pytest

from incentive_sim.config import (
    EvolutionConfig,
    LearningConfig,
    RunConfig,
    population_seed,
    rng,
)
from incentive_sim.evolution import reproduce
from incentive_sim.invasion import (
    A_BRED,
    B_BRED,
    build_rules,
    run_invasion,
    seed_combined_league,
)
from incentive_sim.learning import Learner
from incentive_sim.population import initial_population


@pytest.fixture
def two_populations():
    cfg = RunConfig()
    return (
        initial_population(64, rng(population_seed(cfg, 0)), cfg.evolution),
        initial_population(64, rng(population_seed(cfg, 1)), cfg.evolution),
    )


def test_combined_league_is_an_even_split(two_populations):
    pop_a, pop_b = two_populations
    combined, lineage = seed_combined_league(pop_a, pop_b, 64, rng(np.random.SeedSequence(1)))

    assert combined.n_teams == 64
    assert (lineage == A_BRED).sum() == 32
    assert (lineage == B_BRED).sum() == 32


def test_combined_league_teams_come_from_the_right_parents(two_populations):
    """Each seat must actually hold a team from the league its tag claims."""
    pop_a, pop_b = two_populations
    combined, lineage = seed_combined_league(pop_a, pop_b, 64, rng(np.random.SeedSequence(2)))

    for team in range(combined.n_teams):
        source = pop_a if lineage[team] == A_BRED else pop_b
        assert np.any(np.all(np.isclose(source.attributes, combined.attributes[team]), axis=1))


def test_reproduction_propagates_lineage(two_populations):
    """Offspring must inherit the parent's tag, not keep the dead team's."""
    pop_a, pop_b = two_populations
    cfg = RunConfig()
    generator = rng(np.random.SeedSequence(3))
    combined, lineage = seed_combined_league(pop_a, pop_b, 64, generator)
    learner = Learner(combined, LearningConfig(), generator)

    # Reward exactly tracks lineage: every B-bred team beats every A-bred team.
    season_reward = np.where(lineage == B_BRED, 1.0, 0.0)
    before = (lineage == B_BRED).sum()

    reproduce(combined, learner, season_reward, cfg.evolution, generator, inherit=lineage)

    assert (lineage == B_BRED).sum() > before, "winning lineage failed to spread"
    assert lineage.size == 64


def test_lineage_share_is_conserved_without_selection(two_populations):
    """With flat reward, replacement is drift — the tag array stays well-formed."""
    pop_a, pop_b = two_populations
    cfg = RunConfig()
    generator = rng(np.random.SeedSequence(4))
    combined, lineage = seed_combined_league(pop_a, pop_b, 64, generator)
    learner = Learner(combined, LearningConfig(), generator)

    for _ in range(20):
        reproduce(
            combined, learner, generator.random(64), cfg.evolution, generator, inherit=lineage
        )

    assert lineage.size == 64
    assert set(np.unique(lineage)).issubset({A_BRED, B_BRED})


def test_rules_derive_from_the_configured_thresholds():
    cfg = RunConfig()
    rules, labels = build_rules(cfg)

    assert set(rules) == {"bar_1", "bar_5", "shifting"}
    assert "League A's rule" in labels["bar_1"]
    assert "League B's rule" in labels["bar_5"]


def test_fixed_rule_is_constant_and_shifting_rule_is_not():
    cfg = RunConfig()
    rules, _ = build_rules(cfg)
    generator = rng(np.random.SeedSequence(5))

    assert {rules["bar_5"](generator) for _ in range(50)} == {5}
    assert len({rules["shifting"](generator) for _ in range(200)}) > 1


def test_invasion_runs_and_reports_a_share_per_season(two_populations):
    pop_a, pop_b = two_populations
    cfg = RunConfig(seasons=10)

    result = run_invasion(pop_a, pop_b, "bar_5", 10, cfg, rng(np.random.SeedSequence(6)))

    assert len(result.share_b) == 10
    assert all(0.0 <= share <= 1.0 for share in result.share_b)
    assert all(bar == 5 for bar in result.thresholds)


def test_shifting_rule_actually_varies_the_bar_across_seasons(two_populations):
    pop_a, pop_b = two_populations
    cfg = RunConfig(seasons=40)

    result = run_invasion(pop_a, pop_b, "shifting", 40, cfg, rng(np.random.SeedSequence(7)))

    assert len(set(result.thresholds)) > 1


def test_invasion_is_reproducible(two_populations):
    pop_a, pop_b = two_populations
    cfg = RunConfig(seasons=15)

    def run():
        return run_invasion(
            pop_a.copy(), pop_b.copy(), "bar_1", 15, cfg, rng(np.random.SeedSequence(8))
        ).share_b

    assert run() == run()
