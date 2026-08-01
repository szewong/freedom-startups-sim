from __future__ import annotations

import numpy as np
import pytest

from incentive_sim.config import (
    N_ATTRIBUTES,
    N_STRATEGY,
    EvolutionConfig,
    LeagueConfig,
    RunConfig,
    TournamentConfig,
    dump_config,
    league_seed,
    load_config,
    population_seed,
    rng,
    run_config_from_dict,
)
from incentive_sim.population import initial_population, renormalise_budget


def test_config_roundtrips_through_yaml(tmp_path):
    cfg = RunConfig(name="rt", seasons=7, leagues=(LeagueConfig("A", 1), LeagueConfig("B", 5)))
    path = tmp_path / "cfg.yaml"
    dump_config(cfg, path)
    assert load_config(path) == cfg


def test_unknown_keys_are_rejected():
    """A typo in a swept parameter must fail loudly, not silently do nothing."""
    with pytest.raises(ValueError, match="unknown key"):
        run_config_from_dict({"seasons": 10, "seesons": 20})
    with pytest.raises(ValueError, match="unknown key"):
        run_config_from_dict({"match": {"base_posessions": 60}})


def test_non_power_of_two_bracket_is_rejected():
    with pytest.raises(ValueError, match="power of two"):
        RunConfig(tournament=TournamentConfig(n_teams=48))


def test_unreachable_attribute_budget_is_rejected():
    with pytest.raises(ValueError, match="unreachable"):
        RunConfig(evolution=EvolutionConfig(attribute_budget=4.9, attr_max=0.95))


def test_duplicate_league_names_are_rejected():
    with pytest.raises(ValueError, match="unique"):
        RunConfig(leagues=(LeagueConfig("A", 1), LeagueConfig("A", 5)))


def test_config_hash_is_stable_and_sensitive():
    a = RunConfig(name="x")
    assert a.hash() == RunConfig(name="x").hash()
    assert a.hash() != RunConfig(name="x", seasons=a.seasons + 1).hash()


# -- seeding -----------------------------------------------------------------


def test_both_leagues_start_from_identical_populations():
    """The claim 'the reward function is the only difference' has to be literal.

    Both leagues are seeded from the same population stream, so at t=0 their
    arrays are byte-identical rather than merely drawn from the same distribution.
    """
    cfg = RunConfig()
    pop_a = initial_population(64, rng(population_seed(cfg, 3)), cfg.evolution)
    pop_b = initial_population(64, rng(population_seed(cfg, 3)), cfg.evolution)

    np.testing.assert_array_equal(pop_a.attributes, pop_b.attributes)
    np.testing.assert_array_equal(pop_a.strategy, pop_b.strategy)


def test_replicates_get_different_populations():
    cfg = RunConfig()
    pop_a = initial_population(64, rng(population_seed(cfg, 1)), cfg.evolution)
    pop_b = initial_population(64, rng(population_seed(cfg, 2)), cfg.evolution)
    assert not np.array_equal(pop_a.attributes, pop_b.attributes)


def test_league_streams_are_distinct():
    cfg = RunConfig()
    first = rng(league_seed(cfg, 0, 0)).normal(size=64)
    second = rng(league_seed(cfg, 0, 1)).normal(size=64)
    assert not np.array_equal(first, second)


# -- attribute budget --------------------------------------------------------


def test_initial_population_respects_the_budget():
    cfg = RunConfig()
    pop = initial_population(256, rng(population_seed(cfg, 0)), cfg.evolution)
    totals = pop.attributes.sum(axis=1)

    np.testing.assert_allclose(totals, cfg.evolution.attribute_budget, atol=1e-8)
    assert pop.attributes.min() >= cfg.evolution.attr_min - 1e-9
    assert pop.attributes.max() <= cfg.evolution.attr_max + 1e-9


def test_renormalise_handles_extreme_inputs():
    """Mutation can push attributes anywhere; the budget must survive it."""
    cfg = EvolutionConfig()
    generator = rng(np.random.SeedSequence(7))
    raw = generator.normal(0.5, 1.5, size=(500, N_ATTRIBUTES))

    fixed = renormalise_budget(raw, cfg)

    np.testing.assert_allclose(fixed.sum(axis=1), cfg.attribute_budget, atol=1e-6)
    assert fixed.min() >= cfg.attr_min - 1e-9
    assert fixed.max() <= cfg.attr_max + 1e-9


def test_renormalise_preserves_relative_ordering_within_a_team():
    cfg = EvolutionConfig()
    raw = np.array([[0.9, 0.7, 0.5, 0.3, 0.1]])
    fixed = renormalise_budget(raw, cfg)
    assert list(np.argsort(fixed[0])) == list(np.argsort(raw[0]))


def test_population_summary_reports_every_field():
    cfg = RunConfig()
    pop = initial_population(32, rng(population_seed(cfg, 0)), cfg.evolution)
    summary = pop.summary()
    assert len(summary) == N_ATTRIBUTES + N_STRATEGY
    assert all(np.isfinite(v) for v in summary.values())
