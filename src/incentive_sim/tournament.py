"""Regular season + single-elimination bracket.

The regular season exists to remove a confound: in a pure knockout, the champion
plays 6 games and half the field plays 1, so winners would accumulate far more
learning signal than losers and "the winners learned more" would compete with
the reward function as an explanation for divergence (PLAN.md D3). Here every
team plays the same number of regular-season games.

Fatigue applies **only inside the bracket** — that is what the PRD means by
stamina, "the ability to maintain performance through a tournament". Regular
season games are played on fresh legs.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .config import STRAT_IX, MatchConfig, TournamentConfig
from .match import simulate_games
from .population import Population
from .reward import endogenous_reward, pair_rewards


@dataclass
class GameLog:
    """Flat record of every game played, for metrics and the web trace."""

    team_a: list[np.ndarray] = field(default_factory=list)
    team_b: list[np.ndarray] = field(default_factory=list)
    score_a: list[np.ndarray] = field(default_factory=list)
    score_b: list[np.ndarray] = field(default_factory=list)
    stage: list[np.ndarray] = field(default_factory=list)  # -1 regular, else bracket round

    def add(self, a, b, sa, sb, stage: int) -> None:
        self.team_a.append(np.asarray(a))
        self.team_b.append(np.asarray(b))
        self.score_a.append(np.asarray(sa))
        self.score_b.append(np.asarray(sb))
        self.stage.append(np.full(np.asarray(a).shape, stage, dtype=np.int8))

    def stacked(self) -> dict[str, np.ndarray]:
        return {
            "team_a": np.concatenate(self.team_a),
            "team_b": np.concatenate(self.team_b),
            "score_a": np.concatenate(self.score_a),
            "score_b": np.concatenate(self.score_b),
            "stage": np.concatenate(self.stage),
        }


def bracket_order(n: int) -> np.ndarray:
    """Standard seeding order: adjacent pairs are 1v64, 2v63 (by position), ...

    Pairing adjacent entries of this array reproduces a real bracket tree, so
    the top seeds can only meet late.
    """
    order = [0]
    size = 1
    while size < n:
        nxt = []
        for seed in order:
            nxt.append(seed)
            nxt.append(2 * size - 1 - seed)
        order = nxt
        size *= 2
    return np.asarray(order, dtype=np.int64)


def play_regular_season(
    pop: Population,
    threshold: int,
    tcfg: TournamentConfig,
    mcfg: MatchConfig,
    rng: np.random.Generator,
    log: GameLog | None = None,
    graded: bool = False,
    endogenous: tuple[int, float] | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Every team plays `regular_season_games` games against random opponents.

    Returns (season_reward, games_played) — reward is the league's own metric,
    which is also what seeds the bracket.
    """
    n = pop.n_teams
    reward_total = np.zeros(n)
    games_total = np.zeros(n, dtype=np.int64)
    fresh = np.zeros(n // 2)

    for _ in range(tcfg.regular_season_games):
        shuffled = rng.permutation(n)
        left, right = shuffled[: n // 2], shuffled[n // 2 :]

        score_a, score_b = simulate_games(pop, left, right, fresh, fresh, mcfg, rng)
        if endogenous is None:
            reward_a, reward_b = pair_rewards(score_a, score_b, threshold, graded)
        else:
            max_bar, prize_slope = endogenous
            amb = pop.strategy[:, STRAT_IX["ambition"]]
            margin = score_a - score_b
            reward_a = endogenous_reward(margin, amb[left], max_bar, prize_slope)
            reward_b = endogenous_reward(-margin, amb[right], max_bar, prize_slope)

        np.add.at(reward_total, left, reward_a)
        np.add.at(reward_total, right, reward_b)
        np.add.at(games_total, left, 1)
        np.add.at(games_total, right, 1)

        if log is not None:
            log.add(left, right, score_a, score_b, -1)

    return reward_total, games_total


@dataclass
class BracketResult:
    champion: int
    seeds: np.ndarray  # team index by seed position (0 = top seed)
    elimination_round: np.ndarray  # per team: round they lost in; n_rounds if champion
    upsets: int
    games: int


def play_bracket(
    pop: Population,
    seeds: np.ndarray,
    threshold: int,
    mcfg: MatchConfig,
    rng: np.random.Generator,
    reward_total: np.ndarray,
    games_total: np.ndarray,
    log: GameLog | None = None,
    graded: bool = False,
    endogenous: tuple[int, float] | None = None,
) -> BracketResult:
    """Single elimination. `seeds[0]` is the top seed.

    Fatigue accumulates: a team in round r has already played r bracket games.
    """
    n = seeds.size
    n_rounds = int(np.log2(n))

    seed_of_team = np.empty(pop.n_teams, dtype=np.int64)
    seed_of_team[seeds] = np.arange(n)

    alive = seeds[bracket_order(n)]
    elimination = np.zeros(pop.n_teams, dtype=np.int64)
    upsets = 0
    total_games = 0

    for rnd in range(n_rounds):
        left, right = alive[0::2], alive[1::2]
        played = np.full(left.shape, float(rnd))

        score_a, score_b = simulate_games(pop, left, right, played, played, mcfg, rng)
        if endogenous is None:
            reward_a, reward_b = pair_rewards(score_a, score_b, threshold, graded)
        else:
            max_bar, prize_slope = endogenous
            amb = pop.strategy[:, STRAT_IX["ambition"]]
            margin = score_a - score_b
            reward_a = endogenous_reward(margin, amb[left], max_bar, prize_slope)
            reward_b = endogenous_reward(-margin, amb[right], max_bar, prize_slope)

        np.add.at(reward_total, left, reward_a)
        np.add.at(reward_total, right, reward_b)
        np.add.at(games_total, left, 1)
        np.add.at(games_total, right, 1)

        if log is not None:
            log.add(left, right, score_a, score_b, rnd)

        left_won = score_a > score_b
        winners = np.where(left_won, left, right)
        losers = np.where(left_won, right, left)

        elimination[losers] = rnd
        # An upset is the worse-seeded team advancing.
        upsets += int((seed_of_team[winners] > seed_of_team[losers]).sum())

        total_games += left.size
        alive = winners

    champion = int(alive[0])
    elimination[champion] = n_rounds

    return BracketResult(
        champion=champion,
        seeds=seeds,
        elimination_round=elimination,
        upsets=upsets,
        games=total_games,
    )


def seed_from_reward(reward: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    """Rank teams best-first by the league's own success metric.

    Seeding by each league's own definition of success is deliberate: a league
    that only counts blowouts also *ranks* by blowouts. Ties are broken randomly
    so seeding carries no hidden dependence on team index.
    """
    jitter = rng.random(reward.size) * 1e-6
    return np.argsort(-(reward + jitter), kind="stable")
