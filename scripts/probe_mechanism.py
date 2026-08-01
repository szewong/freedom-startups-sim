"""Phase 1 probe: does the engine expose the opposite-sign reward gradient?

This is *not* a learning experiment — no strategy is updated here. It asks a
narrower question about the engine's physics: for a moderate favourite, does
buying variance move P(margin >= 1) and P(margin >= 5) in opposite directions?

If it does not, the learning loop in Phase 2 has nothing to find and the
constants in MatchConfig need retuning before anything is built on top.
"""

from __future__ import annotations

import sys

import numpy as np

sys.path.insert(0, "tests")
from conftest import make_population, play  # noqa: E402

from incentive_sim.config import MatchConfig  # noqa: E402

N_GAMES = 200_000
CAPACITY = 0.95  # variance is free in this range, isolating the pure effect


def main() -> int:
    cfg = MatchConfig()
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(4242)))

    print(f"{'aggr':>6} {'mean':>8} {'sd':>8} {'P(m>=1)':>9} {'P(m>=5)':>9} {'P(m>=10)':>9}")
    print("-" * 56)

    rows = []
    for aggression in (0.05, 0.25, 0.45, 0.65, 0.85):
        pop = make_population(
            [
                {"offense": 0.585, "risk_capacity": CAPACITY, "aggression": aggression},
                {"risk_capacity": CAPACITY, "aggression": 0.05},
            ]
        )
        margins = play(pop, cfg, rng, 0, 1, N_GAMES)
        row = (
            aggression,
            float(margins.mean()),
            float(margins.std()),
            float((margins >= 1).mean()),
            float((margins >= 5).mean()),
            float((margins >= 10).mean()),
        )
        rows.append(row)
        print(f"{row[0]:6.2f} {row[1]:8.2f} {row[2]:8.2f} {row[3]:9.4f} {row[4]:9.4f} {row[5]:9.4f}")

    mean_margin = np.mean([r[1] for r in rows])
    p1 = [r[3] for r in rows]
    p5 = [r[4] for r in rows]

    print()
    print(f"mean margin across sweep: {mean_margin:+.2f}  (want strictly between 1 and 5)")
    print(f"P(m>=1): {p1[0]:.4f} -> {p1[-1]:.4f}   delta {p1[-1] - p1[0]:+.4f}  (want negative)")
    print(f"P(m>=5): {p5[0]:.4f} -> {p5[-1]:.4f}   delta {p5[-1] - p5[0]:+.4f}  (want positive)")

    # How much evidence does a learner need to see this? Binary reward has
    # per-game sd ~0.5, so a few-percentage-point edge is deep in the noise.
    # This number decides whether the fast (per-team) or slow (population
    # selection) channel can realistically do the work -- see PLAN.md §5.
    for label, series in (("threshold 1", p1), ("threshold 5", p5)):
        effect = abs(series[-1] - series[0])
        p_bar = 0.5 * (series[0] + series[-1])
        sd = np.sqrt(p_bar * (1.0 - p_bar))
        n_per_arm = 2.0 * (2.0 * sd / effect) ** 2 if effect > 0 else float("inf")
        print(
            f"{label}: effect {effect:.4f}, games per arm for a 2-sigma read: {n_per_arm:,.0f}"
        )

    ok = 1.0 < mean_margin < 5.0 and p1[-1] < p1[0] and p5[-1] > p5[0]
    print()
    print("MECHANISM PRESENT" if ok else "MECHANISM ABSENT — retune MatchConfig")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
