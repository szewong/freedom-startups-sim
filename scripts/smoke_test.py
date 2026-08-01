"""Phase 2 go/no-go: does strategy actually respond to the reward function?

Deliberately exaggerated — threshold 1 vs threshold 10, not the baseline's 5 — so
that a null result means "the effect is absent" rather than "the learner was
under-powered". PLAN.md §11 warned this test needs a big lever to be readable.

If aggression does not diverge here, nothing downstream is worth running.
"""

from __future__ import annotations

import sys
import time

import numpy as np

from incentive_sim.config import LeagueConfig, RunConfig, TournamentConfig
from incentive_sim.season import run_replicate

SEASONS = 400
REPLICATES = 5

TRACKED = (
    "strat_aggression",
    "strat_margin_seeking",
    "strat_endgame_conservatism",
    "attr_offense",
    "margin_sd",
    "blowout_rate",
)


def main() -> int:
    cfg = RunConfig(
        name="smoke",
        seasons=SEASONS,
        leagues=(LeagueConfig("low", 1), LeagueConfig("high", 10)),
        tournament=TournamentConfig(n_teams=64, regular_season_games=12),
    )

    print(f"smoke test: threshold 1 vs 10, {SEASONS} seasons x {REPLICATES} replicates")
    start = time.perf_counter()

    final: dict[str, list[dict[str, float]]] = {lg.name: [] for lg in cfg.leagues}
    for replicate in range(REPLICATES):
        for history in run_replicate(cfg, replicate):
            tail = history.rows[-20:]  # average the last 20 seasons to damp noise
            final[history.league].append(
                {key: float(np.mean([r[key] for r in tail])) for key in TRACKED}
            )
        print(f"  replicate {replicate} done ({time.perf_counter() - start:.1f}s)")

    print(f"\n{'metric':<28} {'thr=1':>10} {'thr=10':>10} {'delta':>10}")
    print("-" * 62)
    columns = {}
    for key in TRACKED:
        low = np.array([r[key] for r in final["low"]])
        high = np.array([r[key] for r in final["high"]])
        columns[key] = (low, high)
        print(f"{key:<28} {low.mean():10.4f} {high.mean():10.4f} {high.mean() - low.mean():+10.4f}")

    # Paired across replicates: both leagues share a starting population per seed,
    # so the per-seed difference removes starting-population luck entirely.
    low, high = columns["strat_aggression"]
    paired = high - low
    se = paired.std(ddof=1) / np.sqrt(len(paired)) if len(paired) > 1 else float("inf")

    print(f"\naggression, paired by seed: {paired.mean():+.4f} +/- {1.96 * se:.4f} (95% CI)")
    print(f"per-seed deltas: {np.round(paired, 4)}")

    responds = paired.mean() > 1.96 * se
    print()
    print(
        "GO — strategy responds to the reward function"
        if responds
        else "NO-GO — no detectable response; do not build on this"
    )
    print(f"({time.perf_counter() - start:.1f}s)")
    return 0 if responds else 1


if __name__ == "__main__":
    sys.exit(main())
