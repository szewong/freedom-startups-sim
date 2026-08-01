"""Null control (PLAN.md D5): how far apart do two *identically* rewarded leagues drift?

Every reported effect is a difference between two populations that were seeded
identically and then evolved under different rewards. Some of that difference is
selection; some is drift and RNG-stream luck. This runs the same machinery with
the reward held *equal* in both leagues, so the resulting gaps are pure noise.

A claimed effect only counts if it clears this band.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

from incentive_sim.config import LeagueConfig, RunConfig
from incentive_sim.season import run_replicate

SEASONS = 600
REPLICATES = 16
TAIL = 30

TRACKED = (
    "strat_aggression", "attr_offense", "attr_defense", "attr_risk_capacity",
    "strat_tempo", "margin_sd", "blowout_rate", "close_rate", "sd_aggression",
)


def main() -> int:
    # Both leagues run League A's rule. Same seeds, same start, same reward —
    # only the RNG stream differs, exactly as it does in the real experiment.
    cfg = RunConfig(
        name="null_control",
        seasons=SEASONS,
        replicates=REPLICATES,
        leagues=(LeagueConfig("A", 1), LeagueConfig("B", 1)),
    )

    print(f"null control: both leagues at threshold 1, "
          f"{SEASONS} seasons x {REPLICATES} replicates\n")

    per_league: dict[str, list[dict[str, float]]] = {"A": [], "B": []}
    for replicate in range(REPLICATES):
        for history in run_replicate(cfg, replicate):
            tail = history.rows[-TAIL:]
            per_league[history.league].append(
                {key: float(np.mean([row[key] for row in tail])) for key in TRACKED}
            )

    print(f"{'metric':<26}{'drift gap':>12}{'95% CI half-width':>20}{'':>6}")
    print("-" * 64)

    payload = {}
    for key in TRACKED:
        a = np.array([r[key] for r in per_league["A"]])
        b = np.array([r[key] for r in per_league["B"]])
        delta = b - a
        se = delta.std(ddof=1) / np.sqrt(delta.size)
        ci = 1.96 * se
        spurious = abs(delta.mean()) > ci
        payload[key] = {
            "drift_gap": float(delta.mean()),
            "ci": float(ci),
            "band": float(abs(delta.mean()) + ci),
            "spurious_signal": bool(spurious),
            # Per-replicate deltas, so a treatment effect can be tested against
            # this distribution rather than merely against zero.
            "deltas": [float(v) for v in delta],
        }
        flag = "  <-- SPURIOUS" if spurious else ""
        print(f"{key:<26}{delta.mean():+12.5f}{ci:>20.5f}{flag}")

    out_dir = Path("results/null_control")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "null_control.json").write_text(json.dumps(payload, indent=2))

    spurious = sum(1 for v in payload.values() if v["spurious_signal"])
    print(f"\n{spurious}/{len(TRACKED)} measures show a spurious 'effect' from drift alone")
    print(f"wrote {out_dir / 'null_control.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
