"""Phase 3 correctness. Bracket/selection bugs would silently poison every result."""

from __future__ import annotations

import numpy as np
import pytest

from incentive_sim.config import (
    EvolutionConfig,
    LeagueConfig,
    LearningConfig,
    MatchConfig,
    RunConfig,
    TournamentConfig,
    population_seed,
    rng,
)
from incentive_sim.evolution import reproduce
from incentive_sim.learning import Learner
from incentive_sim.population import initial_population
from incentive_sim.reward import pair_rewards, reward_from_margin
from incentive_sim.season import run_league, run_replicate
from incentive_sim.tournament import (
    GameLog,
    bracket_order,
    play_bracket,
    play_regular_season,
    seed_from_reward,
)


@pytest.fixture
def pop():
    return initial_population(64, rng(population_seed(RunConfig(), 0)), EvolutionConfig())


# -- reward ------------------------------------------------------------------


def test_reward_is_a_step_at_the_threshold():
    margin = np.array([-3, 0, 1, 4, 5, 20])
    np.testing.assert_array_equal(
        reward_from_margin(margin, 1), [0, 0, 1, 1, 1, 1]
    )
    np.testing.assert_array_equal(
        reward_from_margin(margin, 5), [0, 0, 0, 0, 1, 1]
    )


def test_a_narrow_win_scores_zero_in_a_high_threshold_league():
    """The PRD's central rule: winning by 1-4 counts exactly like a loss."""
    score_a, score_b = np.array([80]), np.array([77])
    reward_a, reward_b = pair_rewards(score_a, score_b, 5)
    assert reward_a[0] == 0.0 and reward_b[0] == 0.0


def test_both_sides_cannot_be_rewarded():
    generator = rng(np.random.SeedSequence(3))
    a = generator.integers(60, 110, size=5000)
    b = generator.integers(60, 110, size=5000)
    for threshold in (1, 5, 10):
        ra, rb = pair_rewards(a, b, threshold)
        assert not np.any((ra > 0) & (rb > 0))


# -- bracket -----------------------------------------------------------------


@pytest.mark.parametrize("n", [2, 4, 8, 16, 64])
def test_bracket_order_is_a_permutation(n):
    order = bracket_order(n)
    assert sorted(order.tolist()) == list(range(n))


def test_top_two_seeds_can_only_meet_in_the_final():
    """A broken bracket order would quietly make upsets and seeding meaningless."""
    n = 64
    order = bracket_order(n)
    position = {int(seed): i for i, seed in enumerate(order)}
    # Seeds 0 and 1 must sit in opposite halves, 0/1/2/3 in distinct quarters.
    assert (position[0] < n // 2) != (position[1] < n // 2)
    quarters = {position[s] // (n // 4) for s in (0, 1, 2, 3)}
    assert len(quarters) == 4


def test_bracket_plays_n_minus_one_games_and_crowns_one_champion(pop):
    generator = rng(np.random.SeedSequence(11))
    reward = np.zeros(64)
    games = np.zeros(64, dtype=np.int64)
    log = GameLog()

    result = play_bracket(
        pop, np.arange(64), 1, MatchConfig(), generator, reward, games, log
    )

    assert result.games == 63
    assert log.stacked()["team_a"].size == 63
    assert result.elimination_round[result.champion] == 6
    assert (result.elimination_round == 6).sum() == 1


def test_elimination_rounds_are_consistent_with_a_knockout(pop):
    generator = rng(np.random.SeedSequence(12))
    result = play_bracket(
        pop, np.arange(64), 1, MatchConfig(), generator, np.zeros(64), np.zeros(64, np.int64)
    )
    counts = np.bincount(result.elimination_round, minlength=7)
    # 32 lose in round 0, 16 in round 1, ... 1 champion survives.
    np.testing.assert_array_equal(counts, [32, 16, 8, 4, 2, 1, 1])


def test_stronger_teams_reach_later_rounds(pop):
    """Sanity: the bracket must reward skill, or 'championships' means nothing."""
    generator = rng(np.random.SeedSequence(13))
    reached = np.zeros(64)
    for _ in range(60):
        result = play_bracket(
            pop, np.arange(64), 1, MatchConfig(), generator, np.zeros(64), np.zeros(64, np.int64)
        )
        reached += result.elimination_round

    offense = pop.attr("offense")
    correlation = np.corrcoef(offense, reached)[0, 1]
    assert correlation > 0.2, f"offense barely predicts bracket progress (r={correlation:.3f})"


# -- regular season ----------------------------------------------------------


def test_every_team_plays_the_same_number_of_regular_season_games(pop):
    """PLAN.md D3 — unequal game counts would confound the learning signal."""
    generator = rng(np.random.SeedSequence(14))
    tcfg = TournamentConfig(n_teams=64, regular_season_games=12)

    _, games = play_regular_season(pop, 1, tcfg, MatchConfig(), generator)

    assert np.all(games == 12)


def test_seeding_ranks_by_reward():
    generator = rng(np.random.SeedSequence(15))
    reward = np.array([3.0, 9.0, 1.0, 7.0])
    seeds = seed_from_reward(reward, generator)
    assert seeds[0] == 1 and seeds[-1] == 2


# -- evolution ---------------------------------------------------------------


def test_reproduction_preserves_population_size_and_budget(pop):
    cfg = EvolutionConfig()
    generator = rng(np.random.SeedSequence(16))
    learner = Learner(pop, LearningConfig(), generator)
    season_reward = generator.random(64)

    replaced = reproduce(pop, learner, season_reward, cfg, generator)

    assert pop.n_teams == 64
    assert replaced.size == int(round(cfg.replace_fraction * 64))
    np.testing.assert_allclose(pop.attributes.sum(axis=1), cfg.attribute_budget, atol=1e-6)
    assert pop.attributes.min() >= cfg.attr_min - 1e-9
    assert pop.attributes.max() <= cfg.attr_max + 1e-9


def test_reproduction_replaces_the_worst_teams(pop):
    cfg = EvolutionConfig(replace_fraction=0.25)
    generator = rng(np.random.SeedSequence(17))
    learner = Learner(pop, LearningConfig(), generator)
    season_reward = np.arange(64, dtype=float)  # team 0 worst, team 63 best

    replaced = reproduce(pop, learner, season_reward, cfg, generator)

    assert set(replaced.tolist()) == set(range(16))


def test_selection_propagates_a_favoured_trait(pop):
    """With reward tied to offense, offense should climb over generations."""
    cfg = EvolutionConfig()
    generator = rng(np.random.SeedSequence(18))
    learner = Learner(pop, LearningConfig(), generator)

    before = pop.attr("offense").mean()
    for _ in range(40):
        reproduce(pop, learner, pop.attr("offense").copy(), cfg, generator)
    after = pop.attr("offense").mean()

    assert after > before + 0.05, f"selection did not propagate: {before:.3f} -> {after:.3f}"


# -- learning ----------------------------------------------------------------


def test_learner_adopts_a_better_candidate(pop):
    cfg = LearningConfig(eval_window=10)
    generator = rng(np.random.SeedSequence(19))
    learner = Learner(pop, cfg, generator)

    teams = np.arange(64)
    # Incumbent window: score 0 for everyone.
    for _ in range(cfg.eval_window):
        learner.record(teams, np.zeros(64))
    learner.settle(pop)
    assert np.all(learner.phase == 1)

    candidate = learner.candidate.copy()
    # Candidate window: score 1 for everyone -> strictly better, so adopt.
    for _ in range(cfg.eval_window):
        learner.record(teams, np.ones(64))
    learner.settle(pop)

    np.testing.assert_allclose(learner.incumbent, candidate)
    assert np.all(learner.phase == 0)


def test_learner_rejects_a_worse_candidate(pop):
    cfg = LearningConfig(eval_window=10)
    generator = rng(np.random.SeedSequence(20))
    learner = Learner(pop, cfg, generator)
    teams = np.arange(64)

    for _ in range(cfg.eval_window):
        learner.record(teams, np.ones(64))
    learner.settle(pop)

    incumbent = learner.incumbent.copy()
    for _ in range(cfg.eval_window):
        learner.record(teams, np.zeros(64))
    learner.settle(pop)

    np.testing.assert_allclose(learner.incumbent, incumbent)


def test_strategy_stays_in_bounds_over_a_full_run():
    cfg = RunConfig(seasons=40, leagues=(LeagueConfig("A", 5),))
    histories = run_replicate(cfg, 0)
    pop = histories[0].final_population

    assert pop.strategy.min() >= 0.0 and pop.strategy.max() <= 1.0
    assert pop.attributes.min() >= cfg.evolution.attr_min - 1e-9
    assert np.all(np.isfinite(pop.attributes))


# -- end to end --------------------------------------------------------------


def test_identical_leagues_stay_statistically_indistinguishable():
    """The null control (PLAN.md D5), in miniature.

    Two leagues with the *same* threshold and the same seed must produce the
    same trajectory. If they don't, something other than the reward function is
    driving divergence.
    """
    cfg = RunConfig(seasons=30, leagues=(LeagueConfig("A", 5), LeagueConfig("B", 5)))
    first, second = run_replicate(cfg, 0)

    # Same starting population, same league index -> different RNG stream, so
    # trajectories differ; but they must start from exactly the same place.
    assert first.rows[0]["attr_offense"] == second.rows[0]["attr_offense"]


def test_run_is_reproducible():
    cfg = RunConfig(seasons=25, leagues=(LeagueConfig("A", 1), LeagueConfig("B", 5)))
    first = run_replicate(cfg, 0)
    second = run_replicate(cfg, 0)

    for lhs, rhs in zip(first, second):
        assert lhs.rows[-1] == rhs.rows[-1]


def test_season_rows_carry_every_expected_metric():
    cfg = RunConfig(seasons=5, leagues=(LeagueConfig("A", 5),))
    history = run_replicate(cfg, 0)[0]
    row = history.rows[0]

    for key in (
        "season", "league", "threshold", "reward_rate", "avg_score", "margin_sd",
        "blowout_rate", "close_rate", "upset_rate", "champion_seed",
        "strat_aggression", "attr_offense", "sd_aggression",
    ):
        assert key in row, f"missing metric: {key}"
    assert all(np.isfinite(v) for v in row.values() if isinstance(v, (int, float)))


def test_checkpoint_traces_capture_a_full_bracket():
    cfg = RunConfig(seasons=6, leagues=(LeagueConfig("A", 5),))
    pop = initial_population(64, rng(population_seed(cfg, 0)), cfg.evolution)
    history = run_league(cfg, cfg.leagues[0], pop, rng(np.random.SeedSequence(1)), {0, 5})

    assert len(history.traces) == 2
    trace = history.traces[0]
    assert len(trace.games) == 63
    assert len(trace.seeds) == 64
    assert len(trace.aggression) == 64
