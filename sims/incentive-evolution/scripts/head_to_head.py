"""Run the neutral inter-league tournament on saved evolved populations.

    python scripts/head_to_head.py results/baseline
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

from incentive_sim.config import load_run_config
from incentive_sim.headtohead import run_head_to_head
from incentive_sim.population import Population

TOURNAMENTS_PER_REPLICATE = 40


def main() -> int:
    out_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "results/baseline")
    manifest = json.loads((out_dir / "manifest.json").read_text())
    cfg = load_run_config(out_dir)

    data = np.load(out_dir / "final_populations.npz")
    populations = {}
    for league in (lg.name for lg in cfg.leagues):
        attributes = data[f"{league}_attributes"]
        strategy = data[f"{league}_strategy"]
        populations[league] = [
            Population(attributes[i], strategy[i]) for i in range(attributes.shape[0])
        ]

    names = list(populations)
    print(f"neutral head-to-head: {names[0]} vs {names[1]}")
    print(f"{len(populations[names[0]])} replicates x {TOURNAMENTS_PER_REPLICATE} tournaments")
    print("rule: plain win/loss, no threshold, no learning\n")

    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(777)))
    result = run_head_to_head(
        populations,
        TOURNAMENTS_PER_REPLICATE,
        cfg.tournament,
        cfg.match,
        rng,
    )

    print(f"{'metric':<26}" + "".join(f"{n:>12}" for n in names))
    print("-" * (26 + 12 * len(names)))
    print(
        f"{'championships':<26}"
        + "".join(f"{result.championships[n]:12,}" for n in names)
    )
    print(
        f"{'champion share':<26}"
        + "".join(f"{result.champion_share(n):11.1%} " for n in names)
    )
    print(
        f"{'final four berths':<26}"
        + "".join(f"{result.final_four[n]:12,}" for n in names)
    )
    print(
        f"{'avg elimination round':<26}"
        + "".join(f"{result.avg_elimination_round[n]:12.3f}" for n in names)
    )
    total_games = sum(result.head_to_head_wins.values())
    print(
        f"{'direct head-to-head wins':<26}"
        + "".join(f"{result.head_to_head_wins[n]:12,}" for n in names)
    )
    print(
        f"{'  as win rate':<26}"
        + "".join(f"{result.head_to_head_wins[n] / total_games:11.1%} " for n in names)
    )

    # Binomial 95% CI on the championship split -- is the gap real?
    n = result.tournaments
    share = result.championships[names[1]] / n
    se = np.sqrt(share * (1 - share) / n)
    print(f"\n{names[1]} championship share: {share:.1%} +/- {1.96 * se:.1%} (95% CI)")
    verdict = (
        "no significant difference"
        if abs(share - 0.5) < 1.96 * se
        else f"{names[1] if share > 0.5 else names[0]} wins more"
    )
    print(f"verdict: {verdict}")

    payload = {
        "tournaments": result.tournaments,
        "championships": result.championships,
        "final_four": result.final_four,
        "avg_elimination_round": result.avg_elimination_round,
        "head_to_head_wins": result.head_to_head_wins,
        "champion_share_ci": [share - 1.96 * se, share + 1.96 * se],
        "verdict": verdict,
        "config_hash": manifest["config_hash"],
    }
    (out_dir / "head_to_head.json").write_text(json.dumps(payload, indent=2))
    print(f"\nwrote {out_dir / 'head_to_head.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
