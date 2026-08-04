"""Is it the height of the bar, or its all-or-nothing shape? (PAPER.md §4.2c)

A step reward pays 1 for clearing the bar and 0 for missing it. A graded reward
pays `min(margin / bar, 1)` — same bar, same maximum, same direction, but partial
credit for partial progress.

Comparing the two at an identical bar separates two things that are easy to
conflate: how high a threshold is, and whether falling short scores nothing.

Both are measured against a baseline population evolved under "any win counts",
and head-to-head win rates are played on fresh legs so nothing is inherited from
the leagues' own scoring.
"""

from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np

from incentive_sim.config import (
    LeagueConfig,
    MatchConfig,
    RunConfig,
    population_seed,
    rng as make_rng,
)
from incentive_sim.match import simulate_games
from incentive_sim.population import Population, initial_population
from incentive_sim.season import run_league

SEASONS = 500
REPLICATES = 10
TAIL = 30
DIRECT_GAMES = 60_000

TRACKED = ("attr_offense", "attr_defense", "strat_aggression", "sd_aggression", "reward_rate")

ARMS = [
    ("step bar 50", 50, False),
    ("graded bar 50", 50, True),
    ("step bar 20", 20, False),
    ("graded bar 20", 20, True),
]


def evolve(name: str, threshold: int, graded: bool) -> tuple[dict[str, float], list]:
    league = LeagueConfig(name, threshold, graded=graded)
    cfg = RunConfig(name=name, seasons=SEASONS, replicates=REPLICATES, leagues=(league,))

    tails, pops = [], []
    for replicate in range(REPLICATES):
        pop = initial_population(
            cfg.tournament.n_teams, make_rng(population_seed(cfg, replicate)), cfg.evolution
        )
        history = run_league(
            cfg, league, pop, make_rng(np.random.SeedSequence([31, replicate]))
        )
        tail = history.rows[-TAIL:]
        tails.append({k: float(np.mean([row[k] for row in tail])) for k in TRACKED})
        pops.append(history.final_population)

    return {k: float(np.mean([t[k] for t in tails])) for k in TRACKED}, pops


def head_to_head(pops_x: list, pops_y: list) -> float:
    """Share of games the second population wins, fresh legs, plain win/loss."""
    gen = np.random.Generator(np.random.PCG64(np.random.SeedSequence(99)))
    cfg = MatchConfig()
    wins = total = 0
    for px, py in zip(pops_x, pops_y):
        merged = Population(
            np.concatenate([px.attributes, py.attributes]),
            np.concatenate([px.strategy, py.strategy]),
        )
        left = gen.integers(0, px.n_teams, size=DIRECT_GAMES)
        right = px.n_teams + gen.integers(0, py.n_teams, size=DIRECT_GAMES)
        fresh = np.zeros(DIRECT_GAMES)
        score_l, score_r = simulate_games(merged, left, right, fresh, fresh, cfg, gen)
        wins += int((score_r > score_l).sum())
        total += DIRECT_GAMES
    return wins / total


def main() -> int:
    print(f"step vs graded reward: {SEASONS} seasons x {REPLICATES} replicates\n")
    start = time.perf_counter()

    baseline, baseline_pops = evolve("baseline", 1, False)
    print(f"baseline (any win counts)      offense {baseline['attr_offense']:.4f}"
          f"   ({time.perf_counter() - start:.0f}s)\n")

    print(f"{'arm':<18}{'offense':>10}{'aggression':>13}{'spread':>9}"
          f"{'reward':>9}{'wins vs baseline':>19}")
    print("-" * 78)

    payload = {"baseline": baseline}
    for label, threshold, graded in ARMS:
        stats, pops = evolve(label, threshold, graded)
        stats["h2h_vs_baseline"] = head_to_head(baseline_pops, pops)
        payload[label] = stats
        print(f"{label:<18}{stats['attr_offense']:>10.4f}{stats['strat_aggression']:>13.4f}"
              f"{stats['sd_aggression']:>9.4f}{stats['reward_rate']:>9.3f}"
              f"{100 * stats['h2h_vs_baseline']:>18.1f}%   ({time.perf_counter() - start:.0f}s)")

    Path("results").mkdir(exist_ok=True)
    Path("results/graded_reward.json").write_text(json.dumps(payload, indent=2))

    step50, graded50 = payload["step bar 50"], payload["graded bar 50"]
    print(f"\nAt a bar of 50, identical in every way but the scoring shape:")
    print(f"  step   — offense {step50['attr_offense']:.4f}, "
          f"beats baseline {step50['h2h_vs_baseline']:.1%} of the time")
    print(f"  graded — offense {graded50['attr_offense']:.4f}, "
          f"beats baseline {graded50['h2h_vs_baseline']:.1%} of the time")
    print(f"  baseline offense for reference: {baseline['attr_offense']:.4f}")
    print("\nwrote results/graded_reward.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
