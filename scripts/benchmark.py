"""Phase 1 benchmark gate (PLAN.md §3, §7).

Target: >= 1M games/minute, so the full design (~40M games) runs in minutes.
Batch size matters: the engine is vectorised, so tiny batches pay fixed NumPy
overhead per call. Real usage batches a whole bracket round across all
concurrent replicate runs.
"""

from __future__ import annotations

import time

import numpy as np

from incentive_sim.config import EvolutionConfig, MatchConfig, rng
from incentive_sim.match import simulate_games
from incentive_sim.population import initial_population

TARGET_GAMES_PER_MIN = 1_000_000


def bench(batch: int, repeats: int = 20) -> float:
    """Returns games per second for a given batch size."""
    generator = rng(np.random.SeedSequence(1))
    pop = initial_population(64, generator, EvolutionConfig())
    cfg = MatchConfig()

    idx_a = generator.integers(0, 64, size=batch)
    idx_b = (idx_a + 1 + generator.integers(0, 63, size=batch)) % 64
    played = np.zeros(batch)

    # Warm up, so we time steady state rather than first-call allocation.
    simulate_games(pop, idx_a, idx_b, played, played, cfg, generator)

    start = time.perf_counter()
    for _ in range(repeats):
        simulate_games(pop, idx_a, idx_b, played, played, cfg, generator)
    elapsed = time.perf_counter() - start

    return batch * repeats / elapsed


def main() -> int:
    print(f"{'batch':>10} {'games/sec':>14} {'games/min':>16}")
    print("-" * 42)

    best = 0.0
    for batch in (32, 256, 2_048, 16_384, 131_072):
        rate = bench(batch)
        best = max(best, rate)
        print(f"{batch:10,} {rate:14,.0f} {rate * 60:16,.0f}")

    per_min = best * 60
    print()
    print(f"peak: {per_min:,.0f} games/min  (gate: {TARGET_GAMES_PER_MIN:,})")

    # ~40M games for the full design: baseline + sweeps x 30 replicates.
    print(f"projected wall-clock for 40M games: {40e6 / best / 60:.1f} min")

    ok = per_min >= TARGET_GAMES_PER_MIN
    print("GATE PASSED" if ok else "GATE FAILED — consider numba (PLAN.md §3)")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
