"""The main loop: run one league for N seasons.

Each season is:

    regular season  ->  seed bracket  ->  play bracket  ->  learn  ->  reproduce

Two leagues run this identical code with a different ``win_threshold``. Nothing
else differs, which is what makes the comparison mean anything.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import numpy as np

from .config import ATTRIBUTES, STRATEGY, LeagueConfig, RunConfig
from .evolution import reproduce
from .learning import Learner
from .population import Population, initial_population
from .tournament import GameLog, play_bracket, play_regular_season, seed_from_reward

BLOWOUT = 10
CLOSE_GAME = 3


@dataclass
class SeasonTrace:
    """Full detail for one season, captured only at checkpoints (it is large)."""

    season: int
    seeds: list[int]
    champion: int
    games: list[dict[str, int]]
    aggression: list[float]
    offense: list[float]


@dataclass
class LeagueHistory:
    league: str
    threshold: int
    rows: list[dict[str, Any]] = field(default_factory=list)
    traces: list[SeasonTrace] = field(default_factory=list)
    margin_samples: list[np.ndarray] = field(default_factory=list)
    final_population: Population | None = None


def _season_metrics(
    games: dict[str, np.ndarray], bracket, pop: Population, n_rounds: int
) -> dict[str, float]:
    margin = games["score_a"] - games["score_b"]
    abs_margin = np.abs(margin)
    is_bracket = games["stage"] >= 0

    metrics = {
        "avg_score": float(0.5 * (games["score_a"].mean() + games["score_b"].mean())),
        "avg_abs_margin": float(abs_margin.mean()),
        "margin_sd": float(margin.std()),
        "blowout_rate": float((abs_margin >= BLOWOUT).mean()),
        "close_rate": float((abs_margin <= CLOSE_GAME).mean()),
        "upset_rate": float(bracket.upsets / max(1, is_bracket.sum())),
        "champion_aggression": float(pop.strat("aggression")[bracket.champion]),
        "champion_offense": float(pop.attr("offense")[bracket.champion]),
        "champion_seed": int(np.flatnonzero(bracket.seeds == bracket.champion)[0]),
    }

    # Spread of a population tells us whether it converged or stayed diverse (H2).
    for name in ("aggression", "margin_seeking", "endgame_conservatism", "tempo"):
        metrics[f"sd_{name}"] = float(pop.strat(name).std())
    metrics["sd_offense"] = float(pop.attr("offense").std())

    return metrics


def run_league(
    cfg: RunConfig,
    league: LeagueConfig,
    pop: Population,
    rng: np.random.Generator,
    checkpoints: set[int] | None = None,
    progress: Any | None = None,
) -> LeagueHistory:
    """Simulate one league for ``cfg.seasons`` seasons."""
    checkpoints = checkpoints or set()
    history = LeagueHistory(league=league.name, threshold=league.win_threshold)
    learner = Learner(pop, cfg.learning, rng)
    n_rounds = int(np.log2(cfg.tournament.n_teams))

    championships = np.zeros(pop.n_teams, dtype=np.int64)

    endogenous = (
        (league.max_bar, league.prize_slope) if league.endogenous else None
    )

    for season in range(cfg.seasons):
        capture = season in checkpoints
        log = GameLog()

        reward, games_played = play_regular_season(
            pop, league.win_threshold, cfg.tournament, cfg.match, rng, log, league.graded,
            endogenous,
        )
        seeds = seed_from_reward(reward, rng)
        bracket = play_bracket(
            pop, seeds, league.win_threshold, cfg.match, rng, reward, games_played, log,
            league.graded, endogenous,
        )
        championships[bracket.champion] += 1

        stacked = log.stacked()
        margin = stacked["score_a"] - stacked["score_b"]

        row = {
            "season": season,
            "league": league.name,
            "threshold": league.win_threshold,
            "reward_rate": float((reward / games_played).mean()),
            "win_rate_all": float((margin > 0).mean()),
        }
        row["ambition"] = float(pop.strat("ambition").mean())
        row["sd_ambition"] = float(pop.strat("ambition").std())
        row["personal_bar"] = float(
            np.maximum(1.0, np.rint(pop.strat("ambition") * league.max_bar)).mean()
        )
        row |= pop.summary()
        row |= _season_metrics(stacked, bracket, pop, n_rounds)
        history.rows.append(row)

        if capture:
            history.traces.append(
                SeasonTrace(
                    season=season,
                    seeds=[int(s) for s in seeds],
                    champion=bracket.champion,
                    games=[
                        {
                            "a": int(a),
                            "b": int(b),
                            "sa": int(sa),
                            "sb": int(sb),
                            "stage": int(st),
                        }
                        for a, b, sa, sb, st in zip(
                            stacked["team_a"],
                            stacked["team_b"],
                            stacked["score_a"],
                            stacked["score_b"],
                            stacked["stage"],
                        )
                        if st >= 0  # bracket games only; the regular season is 384 rows
                    ],
                    aggression=[round(float(v), 4) for v in pop.strat("aggression")],
                    offense=[round(float(v), 4) for v in pop.attr("offense")],
                )
            )
            history.margin_samples.append(margin.copy())

        # Learn, then select. Order matters: reproduction copies the incumbent
        # strategy, so the season's learning is inherited.
        learner.record(stacked["team_a"], (margin >= league.win_threshold).astype(float))
        learner.record(stacked["team_b"], (-margin >= league.win_threshold).astype(float))
        learner.settle(pop)

        reproduce(pop, learner, reward, cfg.evolution, rng)

        if progress is not None and season % max(1, cfg.seasons // 20) == 0:
            progress(league.name, season, row)

    history.final_population = pop.copy()
    return history


def run_replicate(
    cfg: RunConfig,
    replicate: int,
    checkpoints: set[int] | None = None,
    progress: Any | None = None,
) -> list[LeagueHistory]:
    """Run every league on a byte-identical starting population."""
    from .config import league_seed, population_seed, rng as make_rng

    histories = []
    for index, league in enumerate(cfg.leagues):
        pop = initial_population(
            cfg.tournament.n_teams, make_rng(population_seed(cfg, replicate)), cfg.evolution
        )
        histories.append(
            run_league(
                cfg,
                league,
                pop,
                make_rng(league_seed(cfg, replicate, index)),
                checkpoints=checkpoints,
                progress=progress,
            )
        )
    return histories
