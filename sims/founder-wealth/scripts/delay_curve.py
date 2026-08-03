"""How long should you wait before raising? The delay curve.

Bootstrapping is "delay forever". The standard startup-school path is "raise on
day one". Everything interesting is in between, so this varies only the trigger
and holds the ladder, the terms and the ambition fixed.

Two kinds of trigger, because they are different claims:

    a revenue number   first dollar, $5k, $10k, $100k, $1M of ARR
    profitability      raise only once the business covers a real founder
                       salary out of its own margin — the point at which the
                       runway stops being finite

The second is the Freedom Startup claim in its strongest form: not "raise less"
but "do not raise until the company can already survive without it". Growth at
all cost runs the tank down on purpose; this asks what happens if you refuse to.

    .venv/bin/python scripts/delay_curve.py --config configs/smallcap.yaml
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

TRIGGERS: list[tuple[str, dict]] = [
    ("day one", {}),
    ("first dollar", {"min_arr_to_raise": 1.0}),
    ("$5k ARR", {"min_arr_to_raise": 5e3}),
    ("$10k ARR", {"min_arr_to_raise": 10e3}),
    ("$100k ARR", {"min_arr_to_raise": 100e3}),
    ("$1M ARR", {"min_arr_to_raise": 1e6}),
    ("profitable", {"require_profitable": True}),
    ("profitable + $100k", {"require_profitable": True, "min_arr_to_raise": 100e3}),
    ("never (bootstrap)", None),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/smallcap.yaml")
    ap.add_argument("--founders", type=int, default=5000)
    ap.add_argument("--replicates", type=int, default=6)
    ap.add_argument("--profit-salary", type=float, default=None)
    ap.add_argument("--out", default="results/delay_curve.json")
    args = ap.parse_args()

    cfg = RunConfig.from_yaml(args.config).replace(n_founders=args.founders)
    if args.profit_salary:
        cfg = cfg.replace(ledger__profit_test_salary=args.profit_salary)
    salary = cfg.ledger.profit_test_salary
    print(f"config {cfg.hash()} | {args.founders} x {args.replicates}")
    print(f'"profitable" = covers a ${salary/1e3:.0f}k founder salary out of its own margin\n')

    never = Strategy("never", -1)
    keys = ("net", "own", "eq0", "ever", "died", "profit_share", "profit_year",
            "beats", "gap_own", "raised", "kept", "runway")
    rows = []

    for label, spec in TRIGGERS:
        strat = never if spec is None else Strategy("delay", 5, **spec)
        acc: dict[str, list[float]] = {k: [] for k in keys}

        for rep in range(args.replicates):
            lat, noise = draw_latents(cfg, rep), draw_noise(cfg, rep)
            base = build_ledger(cfg, run_arm(cfg, lat, noise, never))
            arm = run_arm(cfg, lat, noise, strat)
            w = build_ledger(cfg, arm)
            ever = arm.first_stage >= 0
            prof = arm.first_profit_year >= 0

            acc["net"].append(float(np.median(w.net)))
            acc["own"].append(float(np.median(w.ownership)))
            acc["eq0"].append(float(w.equity_zero.mean()))
            acc["ever"].append(float(ever.mean()))
            acc["died"].append(float(arm.died.mean()))
            acc["profit_share"].append(float(prof.mean()))
            acc["profit_year"].append(
                float(np.median(arm.first_profit_year[prof]) + 1) if prof.any() else 0.0
            )
            acc["beats"].append(float((w.net > base.net).mean()))
            acc["gap_own"].append(float(np.median(w.ownership - base.ownership)))
            acc["raised"].append(float(np.median(arm.raised[ever])) if ever.any() else 0.0)
            acc["kept"].append(float(np.median(arm.founder_pct[ever])) if ever.any() else 1.0)
            # The claim being tested: profitability is what stops you dying.
            acc["runway"].append(float(arm.died[prof].mean()) if prof.any() else 0.0)

        row = {"trigger": label} | {k: replicate_interval(v) for k, v in acc.items()}
        rows.append(row)
        g = lambda k: row[k]["mean"]  # noqa: E731
        print(
            f"  {label:20s} net {g('net')/1e6:+6.3f}M  own {g('own')/1e6:6.3f}M  "
            f"Δown {g('gap_own')/1e6:+6.3f}M  eq=0 {g('eq0'):5.1%}  "
            f"raised {g('ever'):5.1%}  died {g('died'):5.1%}  "
            f"| profitable {g('profit_share'):5.1%} by yr {g('profit_year'):.0f}, "
            f"and those die {g('runway'):5.1%}"
        )

    Path(args.out).write_text(json.dumps(
        {"config_hash": cfg.hash(), "profit_test_salary": salary, "rows": rows}, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
