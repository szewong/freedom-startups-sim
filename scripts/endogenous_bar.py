"""What bar does a population choose for itself — and is it the right one?

Everywhere else in this work the threshold is imposed. That is not the founder's
situation. A founder sets their own bar every time they raise: capital funds the
work, and the preference stack it creates is a floor below which the outcome pays
nothing. Both effects come from the same decision.

Here `ambition` is an evolvable strategy parameter. It does two things at once:

    performance  x (1 + capital_gain * ambition)     capital funds the work
    bar          = ambition * max_bar                 and sets the floor
    payout       = 1 + prize_slope * ambition         clearing a higher bar pays more

The sweep is over `capital_gain` — how much aiming higher genuinely helps. The
question is not only what ambition the population settles on, but whether that
choice leaves it *better at the game* than a population that was never given the
choice. An individually rational bar can still be a collectively bad one.
"""

from __future__ import annotations

import json
import sys
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

CAPITAL_GAINS = [0.0, 0.05, 0.10, 0.20, 0.40]
MAX_BAR = 30
SEASONS = 500
REPLICATES = 8
TAIL = 30

TRACK = ("ambition", "sd_ambition", "personal_bar", "attr_offense",
         "strat_aggression", "margin_sd", "reward_rate")


def evolve(league: LeagueConfig, capital_gain: float) -> tuple[dict[str, float], list]:
    cfg = RunConfig(
        name="endo", seasons=SEASONS, replicates=REPLICATES, leagues=(league,),
        match=MatchConfig(capital_gain=capital_gain),
    )
    tails, pops = [], []
    for r in range(REPLICATES):
        pop = initial_population(64, make_rng(population_seed(cfg, r)), cfg.evolution)
        history = run_league(cfg, league, pop, make_rng(np.random.SeedSequence([77, r])))
        tail = history.rows[-TAIL:]
        tails.append({k: float(np.mean([row[k] for row in tail])) for k in TRACK})
        pops.append(history.final_population)
    summary = {k: float(np.mean([t[k] for t in tails])) for k in TRACK}
    summary["_per_replicate_offense"] = [t["attr_offense"] for t in tails]
    return summary, pops


def head_to_head(pops_x: list, pops_y: list, capital_gain: float, n: int = 40_000) -> float:
    """Share of games the second population wins, on fresh legs.

    Played with capital_gain = 0 so nobody's ambition subsidy applies: this asks
    what the teams are worth, not what their funding buys them.
    """
    gen = np.random.Generator(np.random.PCG64(np.random.SeedSequence(4242)))
    cfg = MatchConfig(capital_gain=0.0)
    wins = total = 0
    for px, py in zip(pops_x, pops_y):
        merged = Population(
            np.concatenate([px.attributes, py.attributes]),
            np.concatenate([px.strategy, py.strategy]),
        )
        left = gen.integers(0, px.n_teams, size=n)
        right = px.n_teams + gen.integers(0, py.n_teams, size=n)
        fresh = np.zeros(n)
        sa, sb = simulate_games(merged, left, right, fresh, fresh, cfg, gen)
        wins += int((sb > sa).sum())
        total += n
    return wins / total


def main() -> int:
    print(f"endogenous bar: max {MAX_BAR} points, {SEASONS} seasons x {REPLICATES} replicates\n")
    start = time.time()

    # Reference: a population never given the choice, scored on any win.
    baseline_league = LeagueConfig("baseline", 1)
    baseline, baseline_pops = evolve(baseline_league, 0.0)
    print(f"baseline (any win, no choice)   offense {baseline['attr_offense']:.4f}"
          f"   ({time.time() - start:.0f}s)\n")

    print(f"{'capital':>8}{'chosen ambition':>18}{'bar picked':>13}{'spread':>9}"
          f"{'offense':>10}{'wins vs baseline':>19}")
    print("-" * 78)

    results = {}
    for gain in CAPITAL_GAINS:
        league = LeagueConfig("endo", 1, endogenous=True, max_bar=MAX_BAR, prize_slope=1.0)
        summary, pops = evolve(league, gain)
        summary["h2h_vs_baseline"] = head_to_head(baseline_pops, pops, gain)
        results[gain] = summary
        print(f"{gain:>8.2f}{summary['ambition']:>18.3f}{summary['personal_bar']:>13.1f}"
              f"{summary['sd_ambition']:>9.3f}{summary['attr_offense']:>10.4f}"
              f"{100 * summary['h2h_vs_baseline']:>18.1f}%   ({time.time() - start:.0f}s)")

    out = Path("results/endogenous_bar")
    out.mkdir(parents=True, exist_ok=True)
    (out / "endogenous_bar.json").write_text(json.dumps({
        "capital_gains": CAPITAL_GAINS, "max_bar": MAX_BAR,
        "seasons": SEASONS, "replicates": REPLICATES,
        "baseline": baseline, "results": {str(k): v for k, v in results.items()},
    }, indent=2))

    print()
    for gain, r in results.items():
        chosen = r["ambition"]
        verdict = ("aims high" if chosen > 0.5 else "aims low" if chosen < 0.25 else "aims middling")
        cost = r["attr_offense"] - baseline["attr_offense"]
        print(f"  capital {gain:.2f}: {verdict} (bar {r['personal_bar']:.0f}), "
              f"skill vs baseline {cost:+.4f}, "
              f"{'beats' if r['h2h_vs_baseline'] > 0.5 else 'loses to'} baseline")
    print(f"\nwrote {out / 'endogenous_bar.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
