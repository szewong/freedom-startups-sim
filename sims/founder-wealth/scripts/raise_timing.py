"""When should a founder raise their first round? (the Freedom Startup question)

Every venture arm in the main study raises on day one, because that is what the
pre-seed gate allows and what founders on that path do. This asks a different
question: hold the ladder, the terms and the ambition fixed, and vary only *when*
the founder first takes money.

    threshold $0        raise as soon as anyone will fund you
    threshold $100k     bootstrap to first real revenue, then raise
    threshold $1M       bootstrap to a Series A story, then raise
    threshold infinite  never raise

The mechanism being tested is not "raise less". It is that a company arriving at
the ladder with revenue skips the rounds it has outgrown — and the earliest
rounds are the most expensive per dollar, costing ~19% of the company for $1M.
Against that sits the cost of waiting: slower growth, a founder paying themselves
out of revenue, a market whose unclaimed share is decaying, and the risk of
giving up before ever reaching the bar.

    .venv/bin/python scripts/raise_timing.py --config configs/smallcap.yaml
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from foundersim.cohort import run_arm
from foundersim.config import RunConfig
from foundersim.latents import draw_latents, draw_noise
from foundersim.ledger import build_ledger
from foundersim.metrics import replicate_interval
from foundersim.strategy import Strategy

THRESHOLDS = [0.0, 50e3, 100e3, 250e3, 500e3, 1e6, 2e6, 5e6, np.inf]


def label(threshold: float) -> str:
    if threshold == 0:
        return "raise on day one"
    if not np.isfinite(threshold):
        return "never raise"
    return f"wait for ${threshold/1e3:,.0f}k ARR".replace("$1,000k", "$1M")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/smallcap.yaml")
    ap.add_argument("--founders", type=int, default=5000)
    ap.add_argument("--replicates", type=int, default=6)
    ap.add_argument("--raise-multiple", type=float, default=1.0)
    ap.add_argument("--out", default="results/raise_timing.json")
    args = ap.parse_args()

    cfg = RunConfig.from_yaml(args.config).replace(n_founders=args.founders)
    print(f"config hash {cfg.hash()}  |  {args.founders} x {args.replicates} replicates")

    never = Strategy("never", -1)
    rows: list[dict] = []

    for threshold in THRESHOLDS:
        arms: dict[str, list] = {k: [] for k in (
            "net", "own", "gap_net", "gap_own", "equity_zero", "died", "gave_up",
            "ran_dry", "raised", "ever_raised", "entry_stage", "founder_pct", "beats",
        )}
        for rep in range(args.replicates):
            lat, noise = draw_latents(cfg, rep), draw_noise(cfg, rep)
            base = build_ledger(cfg, run_arm(cfg, lat, noise, never))

            strat = Strategy(
                "freedom", 5, args.raise_multiple,
                min_arr_to_raise=(0.0 if not np.isfinite(threshold) else threshold),
            )
            if not np.isfinite(threshold):
                strat = never
            arm = run_arm(cfg, lat, noise, strat)
            w = build_ledger(cfg, arm)

            ever = arm.max_stage >= 0
            # Conditional on having raised at all: the unconditional medians jump
            # around as the share who raise crosses 50%, which says nothing about
            # the strategy and everything about where the median founder sits.
            arms.setdefault("entry_stage_raised", []).append(
                float(np.median(arm.first_stage[ever])) if ever.any() else -1.0
            )
            arms.setdefault("kept_if_raised", []).append(
                float(np.median(arm.founder_pct[ever])) if ever.any() else 1.0
            )
            arms.setdefault("raised_if_raised", []).append(
                float(np.median(arm.raised[ever])) if ever.any() else 0.0
            )
            arms.setdefault("equity_zero_if_raised", []).append(
                float(w.equity_zero[ever].mean()) if ever.any() else 0.0
            )
            arms["net"].append(float(np.median(w.net)))
            arms["own"].append(float(np.median(w.ownership)))
            arms["gap_net"].append(float(np.median(w.net - base.net)))
            arms["gap_own"].append(float(np.median(w.ownership - base.ownership)))
            arms["equity_zero"].append(float(w.equity_zero.mean()))
            arms["died"].append(float(arm.died.mean()))
            arms["gave_up"].append(float(arm.abandoned.mean()))
            arms["ran_dry"].append(float((arm.died & ~arm.abandoned).mean()))
            arms["raised"].append(float(arm.raised.mean()))
            arms["ever_raised"].append(float(ever.mean()))
            arms["entry_stage"].append(
                float(np.median(arm.max_stage[ever])) if ever.any() else -1.0
            )
            arms["founder_pct"].append(float(np.median(arm.founder_pct)))
            arms["beats"].append(float((w.net > base.net).mean()))

        row = {"threshold": None if not np.isfinite(threshold) else threshold,
               "label": label(threshold)}
        row |= {k: replicate_interval(v) for k, v in arms.items()}
        rows.append(row)

        print(
            f"  {row['label']:22s} net {row['net']['mean']/1e6:+6.3f}M  "
            f"own {row['own']['mean']/1e6:6.3f}M  "
            f"vs never {row['gap_net']['mean']/1e6:+6.3f}M  "
            f"equity=0 {row['equity_zero']['mean']:5.1%}  "
            f"raised {row['ever_raised']['mean']:5.1%} of them, "
            f"${row['raised']['mean']/1e6:5.2f}M avg  "
            f"| of those: entered at stage {row['entry_stage_raised']['mean']:.1f}, "
            f"took ${row['raised_if_raised']['mean']/1e6:5.2f}M, "
            f"kept {row['kept_if_raised']['mean']:5.1%}, "
            f"equity=0 {row['equity_zero_if_raised']['mean']:5.1%}"
        )

    Path(args.out).write_text(json.dumps(
        {"config_hash": cfg.hash(), "raise_multiple": args.raise_multiple, "rows": rows}, indent=2
    ))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
