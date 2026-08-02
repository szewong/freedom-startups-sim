"""Test each reported effect against the null control, not against zero.

A confidence interval that excludes zero only says the two leagues ended up
different. It does not say the *reward function* caused it: two identically
rewarded populations also drift apart, and some traits drift a great deal.

This runs Welch's t-test comparing the treatment's per-replicate B-A differences
against the null control's, so the question becomes the right one — is this gap
bigger than what identical rewards already produce?
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

TAIL = 30


def treatment_deltas(parquet: Path, metric: str) -> np.ndarray:
    table = pq.read_table(parquet).to_pydict()
    n = len(table["season"])
    cutoff = max(table["season"]) - TAIL + 1
    replicates = sorted(set(table["replicate"]))

    per_league = {}
    for league in ("A", "B"):
        per_league[league] = np.array([
            np.mean([
                table[metric][i] for i in range(n)
                if table["league"][i] == league
                and table["replicate"][i] == r
                and table["season"][i] >= cutoff
            ])
            for r in replicates
        ])
    return per_league["B"] - per_league["A"]


def welch(a: np.ndarray, b: np.ndarray) -> tuple[float, float, float]:
    """Difference of means, standard error, and t statistic."""
    diff = a.mean() - b.mean()
    se = np.sqrt(a.var(ddof=1) / a.size + b.var(ddof=1) / b.size)
    return float(diff), float(se), float(diff / se) if se > 0 else float("inf")


def main() -> int:
    run_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "results/threshold10")
    null = json.loads(Path("results/null_control/null_control.json").read_text())

    print(f"{run_dir.name} vs null control (identical rewards)\n")
    print(f"{'metric':<24}{'effect':>10}{'drift':>10}{'net':>10}{'t':>8}  verdict")
    print("-" * 72)

    rows = {}
    for metric, info in null.items():
        if "deltas" not in info:
            print("null control has no per-replicate deltas — re-run scripts/null_control.py")
            return 1

        treatment = treatment_deltas(run_dir / "seasons.parquet", metric)
        drift = np.array(info["deltas"])
        diff, se, t = welch(treatment, drift)

        # Two-sided, ~30 df; 2.04 is the 5% critical value.
        survives = abs(t) > 2.04
        verdict = "survives" if survives else "NOT distinguishable from drift"
        rows[metric] = {
            "treatment_gap": float(treatment.mean()),
            "drift_gap": float(drift.mean()),
            "net_effect": diff,
            "se": se,
            "t": t,
            "survives_null_control": bool(survives),
        }
        print(f"{metric:<24}{treatment.mean():>10.4f}{drift.mean():>10.4f}"
              f"{diff:>10.4f}{t:>8.2f}  {verdict}")

    survivors = sum(1 for v in rows.values() if v["survives_null_control"])
    print(f"\n{survivors}/{len(rows)} effects survive the null control")

    (run_dir / "vs_null.json").write_text(json.dumps(rows, indent=2))
    print(f"wrote {run_dir / 'vs_null.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
