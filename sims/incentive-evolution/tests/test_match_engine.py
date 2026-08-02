"""Phase 1 exit criteria (PLAN.md §5, §7).

These four tests gate everything downstream. If the engine cannot express the
mean-variance tradeoff, or if it secretly knows about win thresholds, no result
produced on top of it means anything.
"""

from __future__ import annotations

import inspect
import io
import tokenize
from pathlib import Path

import numpy as np
import pytest

from conftest import make_population, play
from incentive_sim import match, population

N_GAMES = 40_000


# -- Criterion 1: skill matters ----------------------------------------------


def test_higher_offense_wins_more_than_chance(match_cfg, rng):
    pop = make_population([{"offense": 0.70}, {"offense": 0.40}])
    margins = play(pop, match_cfg, rng, 0, 1, N_GAMES)

    win_rate = float((margins > 0).mean())
    # Binomial standard error at n=40k is ~0.0025, so 0.55 is far outside noise.
    assert win_rate > 0.55, f"stronger offense won only {win_rate:.3f} of games"


def test_higher_defense_concedes_fewer_points(match_cfg, rng):
    weak = make_population([{"defense": 0.20}, {"offense": 0.5}])
    strong = make_population([{"defense": 0.80}, {"offense": 0.5}])

    conceded_vs_weak = -play(weak, match_cfg, rng, 0, 1, N_GAMES).mean()
    conceded_vs_strong = -play(strong, match_cfg, rng, 0, 1, N_GAMES).mean()

    assert conceded_vs_strong < conceded_vs_weak


# -- Criterion 2: aggression buys variance -----------------------------------


@pytest.mark.parametrize("risk_capacity", [0.5, 1.0])
def test_aggression_monotonically_increases_margin_variance(match_cfg, rng, risk_capacity):
    levels = [0.0, 0.25, 0.5, 0.75, 1.0]
    spreads = []
    for aggression in levels:
        pop = make_population(
            [
                {"aggression": aggression, "risk_capacity": risk_capacity},
                {"aggression": aggression, "risk_capacity": risk_capacity},
            ]
        )
        spreads.append(float(play(pop, match_cfg, rng, 0, 1, N_GAMES).std()))

    assert all(lo < hi for lo, hi in zip(spreads, spreads[1:])), (
        f"margin sd not monotonic in aggression: {spreads}"
    )
    assert spreads[-1] > 1.4 * spreads[0], (
        f"aggression is too weak a variance lever: {spreads[0]:.2f} -> {spreads[-1]:.2f}"
    )


# -- Criterion 3: a genuine mean-variance frontier ---------------------------


def test_variance_has_a_price_beyond_risk_capacity(match_cfg, rng):
    """Past its risk capacity, a team buys variance by giving up expected margin.

    This is the tradeoff the whole experiment turns on: if variance were free at
    all levels, every league would max out aggression and nothing would diverge.
    """
    capacity = 0.30
    levels = [0.30, 0.50, 0.70, 0.90]

    means, spreads = [], []
    for aggression in levels:
        pop = make_population(
            [
                {"aggression": aggression, "risk_capacity": capacity},
                {"aggression": capacity, "risk_capacity": capacity},
            ]
        )
        margins = play(pop, match_cfg, rng, 0, 1, N_GAMES)
        means.append(float(margins.mean()))
        spreads.append(float(margins.std()))

    assert all(hi < lo for lo, hi in zip(means, means[1:])), (
        f"expected margin should fall as aggression exceeds capacity: {means}"
    )
    assert all(lo < hi for lo, hi in zip(spreads, spreads[1:])), (
        f"margin sd should rise with aggression: {spreads}"
    )
    # No level dominates: the best mean has the worst spread and vice versa.
    assert np.argmax(means) == 0 and np.argmax(spreads) == len(levels) - 1


def test_variance_is_cheap_below_risk_capacity(match_cfg, rng):
    """Below capacity, aggression adds variance at no cost to the mean.

    So a low-threshold league has a reason to sit at low aggression and a
    high-threshold league has a free route to volatility — both directions of
    the experiment are reachable.
    """
    pop_low = make_population(
        [{"aggression": 0.10, "risk_capacity": 0.90}, {"aggression": 0.10, "risk_capacity": 0.90}]
    )
    pop_high = make_population(
        [{"aggression": 0.85, "risk_capacity": 0.90}, {"aggression": 0.10, "risk_capacity": 0.90}]
    )

    margin_low = play(pop_low, match_cfg, rng, 0, 1, N_GAMES)
    margin_high = play(pop_high, match_cfg, rng, 0, 1, N_GAMES)

    # Mean essentially unchanged (no overreach penalty), variance clearly up.
    assert abs(margin_high.mean() - margin_low.mean()) < 1.0
    assert margin_high.std() > 1.2 * margin_low.std()


def test_tempo_reduces_relative_variance(match_cfg, rng):
    """Tempo is the counter-lever: more possessions means mean grows faster than sd."""
    slow = make_population([{"tempo": 0.0}, {"tempo": 0.0, "offense": 0.35}])
    fast = make_population([{"tempo": 1.0}, {"tempo": 1.0, "offense": 0.35}])

    margin_slow = play(slow, match_cfg, rng, 0, 1, N_GAMES)
    margin_fast = play(fast, match_cfg, rng, 0, 1, N_GAMES)

    # The favourite's edge is more reliable at high tempo.
    assert margin_fast.mean() > margin_slow.mean()
    assert (margin_fast.mean() / margin_fast.std()) > (margin_slow.mean() / margin_slow.std())


def test_endgame_knobs_move_variance_in_opposite_directions(match_cfg, rng):
    """A leading team can protect the win or chase the margin — both must work."""
    favourite = {"offense": 0.75}

    protect = make_population(
        [favourite | {"endgame_conservatism": 1.0, "margin_seeking": 0.0}, {}]
    )
    chase = make_population([favourite | {"endgame_conservatism": 0.0, "margin_seeking": 1.0}, {}])

    margin_protect = play(protect, match_cfg, rng, 0, 1, N_GAMES)
    margin_chase = play(chase, match_cfg, rng, 0, 1, N_GAMES)

    assert margin_chase.std() > margin_protect.std()
    # The point of the two knobs: they trade win probability against blowout rate.
    assert (margin_protect > 0).mean() > (margin_chase > 0).mean()
    assert (margin_chase >= 10).mean() > (margin_protect >= 10).mean()


# -- Criterion 4: the engine is reward-blind ----------------------------------


def test_engine_never_references_rewards_or_thresholds():
    """Structural guard on the experiment's core claim.

    If the match engine could see the win threshold, any divergence we measure
    would be an artefact we built in rather than a result we found.
    """
    forbidden = ("threshold", "reward", "league", "margin_target")
    for module in (match, population):
        source = Path(inspect.getfile(module)).read_text()

        # Check executable tokens only. Comments and docstrings are free to
        # discuss the experimental design; the *code* must not know about it.
        code_tokens = [
            tok.string.lower()
            for tok in tokenize.generate_tokens(io.StringIO(source).readline)
            if tok.type not in (tokenize.COMMENT, tokenize.STRING, tokenize.NL, tokenize.NEWLINE)
        ]
        for token in code_tokens:
            for word in forbidden:
                assert word not in token, (
                    f"{module.__name__} references '{word}' in code ({token!r}) — "
                    "the engine must be reward-blind"
                )


def test_games_always_have_a_winner(match_cfg, rng):
    pop = make_population([{}, {}])
    margins = play(pop, match_cfg, rng, 0, 1, N_GAMES)
    assert not np.any(margins == 0)


def test_simulation_is_reproducible_under_a_fixed_seed(match_cfg):
    pop = make_population([{"offense": 0.6}, {"defense": 0.6}])

    def run():
        gen = np.random.Generator(np.random.PCG64(np.random.SeedSequence(99)))
        return play(pop, match_cfg, gen, 0, 1, 2_000)

    np.testing.assert_array_equal(run(), run())


def test_scores_stay_in_a_believable_range(match_cfg, rng):
    pop = make_population([{}, {}])
    from incentive_sim.match import simulate_games

    n = 20_000
    zeros = np.zeros(n)
    score_a, score_b = simulate_games(
        pop, np.zeros(n, int), np.ones(n, int), zeros, zeros, match_cfg, rng
    )
    assert score_a.min() >= 0
    assert 60 < score_a.mean() < 120, f"mean score {score_a.mean():.1f} is not believable"
    assert score_b.max() < 250


def test_fatigue_degrades_a_tired_team(match_cfg, rng):
    from incentive_sim.match import simulate_games

    pop = make_population([{"stamina": 0.1}, {"stamina": 0.1}])
    n = 40_000
    fresh = np.zeros(n)
    tired = np.full(n, 6.0)

    score_fresh, score_tired = simulate_games(
        pop, np.zeros(n, int), np.ones(n, int), fresh, tired, match_cfg, rng
    )
    assert (score_fresh - score_tired).mean() > 2.0


def test_stamina_attribute_damps_fatigue(match_cfg, rng):
    from incentive_sim.match import simulate_games

    n = 40_000
    played = np.full(n, 6.0)

    def deficit(stamina: float) -> float:
        pop = make_population([{"stamina": stamina}, {"stamina": stamina}])
        rested, worn = simulate_games(
            pop, np.zeros(n, int), np.ones(n, int), np.zeros(n), played, match_cfg, rng
        )
        return float((rested - worn).mean())

    assert deficit(0.9) < deficit(0.1)
