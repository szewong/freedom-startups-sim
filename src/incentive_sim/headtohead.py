"""Neutral inter-league tournament (PLAN.md D4).

"Which system wins more tournaments?" cannot be answered inside a league — each
league grades itself on its own scale, so their reward rates are not comparable.
The only fair test is to put the evolved populations in the same bracket under a
**neutral** rule: plain win/loss, no threshold, no further learning.

This is where H3 is decided. If League B's threshold pressure produced genuinely
stronger competitors it should win here. If it only produced more volatile ones,
it should not.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import MatchConfig, TournamentConfig
from .population import Population
from .tournament import play_bracket, play_regular_season, seed_from_reward

NEUTRAL_THRESHOLD = 1  # a win is a win
DIRECT_GAMES_PER_REPLICATE = 40_000


@dataclass
class HeadToHead:
    tournaments: int
    championships: dict[str, int]
    final_four: dict[str, int]
    avg_elimination_round: dict[str, float]
    head_to_head_wins: dict[str, int]
    entrants: dict[str, int]

    def champion_share(self, league: str) -> float:
        return self.championships[league] / max(1, self.tournaments)


def _mixed_population(
    pop_a: Population, pop_b: Population, half: int, rng: np.random.Generator
) -> tuple[Population, np.ndarray]:
    """Draw `half` teams from each league into one bracket field.

    Returns the merged population and an origin mask (0 = league A, 1 = B).
    """
    pick_a = rng.choice(pop_a.n_teams, size=half, replace=False)
    pick_b = rng.choice(pop_b.n_teams, size=half, replace=False)

    merged = Population(
        np.concatenate([pop_a.attributes[pick_a], pop_b.attributes[pick_b]]),
        np.concatenate([pop_a.strategy[pick_a], pop_b.strategy[pick_b]]),
    )
    origin = np.concatenate([np.zeros(half, dtype=np.int8), np.ones(half, dtype=np.int8)])
    return merged, origin


def run_head_to_head(
    populations: dict[str, list[Population]],
    tournaments_per_replicate: int,
    tcfg: TournamentConfig,
    mcfg: MatchConfig,
    rng: np.random.Generator,
) -> HeadToHead:
    """Run neutral tournaments across every replicate's evolved populations."""
    names = list(populations)
    if len(names) != 2:
        raise ValueError(f"head-to-head needs exactly two leagues, got {names}")
    league_a, league_b = names

    n_teams = tcfg.n_teams
    half = n_teams // 2
    n_rounds = int(np.log2(n_teams))

    championships = dict.fromkeys(names, 0)
    final_four = dict.fromkeys(names, 0)
    elimination_sum = dict.fromkeys(names, 0.0)
    wins = dict.fromkeys(names, 0)
    entrants = dict.fromkeys(names, 0)
    total = 0

    for pop_a, pop_b in zip(populations[league_a], populations[league_b]):
        for _ in range(tournaments_per_replicate):
            merged, origin = _mixed_population(pop_a, pop_b, half, rng)
            by_index = {0: league_a, 1: league_b}

            # Neutral seeding: a regular season under plain win/loss, so neither
            # league's home metric decides the bracket.
            reward, games = play_regular_season(
                merged, NEUTRAL_THRESHOLD, tcfg, mcfg, rng
            )
            seeds = seed_from_reward(reward, rng)
            result = play_bracket(
                merged, seeds, NEUTRAL_THRESHOLD, mcfg, rng, reward, games
            )

            championships[by_index[int(origin[result.champion])]] += 1
            for team in np.flatnonzero(result.elimination_round >= n_rounds - 2):
                final_four[by_index[int(origin[team])]] += 1
            for index, name in by_index.items():
                mask = origin == index
                elimination_sum[name] += float(result.elimination_round[mask].mean())
                entrants[name] += int(mask.sum())

            # Direct cross-league record: every game where the two leagues met.
            total += 1

        # Head-to-head win counts on fresh legs. Sampled heavily: the effect here
        # is a couple of percentage points, and one game per team per replicate
        # is nowhere near enough to resolve it.
        from .match import simulate_games

        merged = Population(
            np.concatenate([pop_a.attributes, pop_b.attributes]),
            np.concatenate([pop_a.strategy, pop_b.strategy]),
        )
        size = pop_a.n_teams
        left = rng.integers(0, size, size=DIRECT_GAMES_PER_REPLICATE)
        right = size + rng.integers(0, pop_b.n_teams, size=DIRECT_GAMES_PER_REPLICATE)
        fresh = np.zeros(DIRECT_GAMES_PER_REPLICATE)
        score_left, score_right = simulate_games(
            merged, left, right, fresh, fresh, mcfg, rng
        )
        wins[league_a] += int((score_left > score_right).sum())
        wins[league_b] += int((score_right > score_left).sum())

    return HeadToHead(
        tournaments=total,
        championships=championships,
        final_four=final_four,
        avg_elimination_round={
            name: elimination_sum[name] / max(1, total) for name in names
        },
        head_to_head_wins=wins,
        entrants=entrants,
    )
