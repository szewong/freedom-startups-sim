"""Raise $250k at first revenue, to hire — does it pay, and how good must the hires be?

The scenario is specific and common: a founder doing a few thousand a month who
believes the thing stopping them is that they cannot hire anyone. They want a
small round — $250k, not $1M — to put two or three people on for a year.

The model as calibrated cannot answer this, and it is worth being blunt about
why. It has exactly one channel through which money buys growth: sales spend.
Employees only add capacity to *serve* customers already won, so a company with
four customers needs none of them, and hiring cannot make it grow faster. The
founder's belief is not modelled — it is not even expressible.

So this adds the channel and refuses to guess its strength:

    growth_hire_share            how much of the money goes to people
    team_acquisition_efficiency  what a dollar of payroll buys, as a fraction of
                                 what a dollar of marketing buys

and sweeps the second. The output is not "hiring pays". It is the efficiency at
which hiring *starts* to pay — a number the founder can check against their own
experience, which is the only place that number can honestly come from.

    .venv/bin/python scripts/hiring.py --config configs/smallcap.yaml
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

# What a dollar of payroll buys, relative to a dollar of marketing.
EFFICIENCIES = [0.0, 0.25, 0.5, 0.75, 1.0, 1.5]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/smallcap.yaml")
    ap.add_argument("--founders", type=int, default=5000)
    ap.add_argument("--replicates", type=int, default=6)
    ap.add_argument("--amount", type=float, default=250e3)
    ap.add_argument("--pre-money", type=float, default=2.5e6)
    ap.add_argument("--trigger-arr", type=float, default=48e3, help="a few thousand a month")
    ap.add_argument("--hire-share", type=float, default=0.70)
    ap.add_argument("--out", default="results/hiring.json")
    args = ap.parse_args()

    base_cfg = RunConfig.from_yaml(args.config).replace(n_founders=args.founders)
    print(
        f"config {base_cfg.hash()} | ${args.amount/1e3:.0f}k on ${args.pre_money/1e6:.1f}M pre, "
        f"triggered at ${args.trigger_arr/1e3:.0f}k ARR | {args.hire_share:.0%} of money to people"
    )
    dilution = args.amount / (args.pre_money + args.amount)
    print(f"  that round costs the founder {dilution:.1%} plus the option pool\n")

    never = Strategy("never", -1)
    # One small round and then self-funded, versus keeping the ladder open.
    once = Strategy(
        "hire_once", 0, min_arr_to_raise=args.trigger_arr,
        entry_amount=args.amount, entry_pre_money=args.pre_money,
    )
    ladder = Strategy(
        "hire_then_ladder", 5, min_arr_to_raise=args.trigger_arr,
        entry_amount=args.amount, entry_pre_money=args.pre_money,
    )

    rows = []
    for eff in EFFICIENCIES:
        cfg = base_cfg.replace(
            business__growth_hire_share=args.hire_share,
            business__team_acquisition_efficiency=eff,
        )
        acc = {k: {m: [] for m in ("dnet", "down", "beats", "eq0", "ever", "arr")}
               for k in ("hire_once", "hire_then_ladder")}

        for rep in range(args.replicates):
            lat, noise = draw_latents(cfg, rep), draw_noise(cfg, rep)
            base = build_ledger(cfg, run_arm(cfg, lat, noise, never))
            for strat in (once, ladder):
                arm = run_arm(cfg, lat, noise, strat)
                w = build_ledger(cfg, arm)
                ev = arm.first_stage >= 0
                a = acc[strat.name]
                a["ever"].append(float(ev.mean()))
                a["eq0"].append(float(w.equity_zero[ev].mean()) if ev.any() else 0.0)
                a["dnet"].append(float(np.median((w.net - base.net)[ev])) if ev.any() else 0.0)
                a["down"].append(
                    float(np.median((w.ownership - base.ownership)[ev])) if ev.any() else 0.0
                )
                a["beats"].append(
                    float((w.net[ev] > base.net[ev]).mean()) if ev.any() else 0.0
                )
                a["arr"].append(
                    float(np.median(arm.final_arr[ev])) if ev.any() else 0.0
                )

        row = {"efficiency": eff}
        for name, a in acc.items():
            row[name] = {k: replicate_interval(v) for k, v in a.items()}
        rows.append(row)

        o, l = row["hire_once"], row["hire_then_ladder"]
        print(
            f"  payroll worth {eff:4.2f}x marketing | "
            f"raise once: Δnet {o['dnet']['mean']/1e6:+6.3f}M Δown {o['down']['mean']/1e6:+6.3f}M "
            f"beats {o['beats']['mean']:5.1%} | "
            f"keep raising: Δnet {l['dnet']['mean']/1e6:+6.3f}M Δown {l['down']['mean']/1e6:+6.3f}M "
            f"beats {l['beats']['mean']:5.1%}"
        )

    # Where does it cross zero?
    for name in ("hire_once", "hire_then_ladder"):
        xs = [r["efficiency"] for r in rows]
        ys = [r[name]["dnet"]["mean"] for r in rows]
        cross = None
        for i in range(1, len(ys)):
            if ys[i - 1] < 0 <= ys[i]:
                t = -ys[i - 1] / (ys[i] - ys[i - 1])
                cross = xs[i - 1] + t * (xs[i] - xs[i - 1])
                break
        label = f"{cross:.2f}x" if cross is not None else ("never" if ys[-1] < 0 else "always")
        print(f"\n  {name}: pays once payroll is worth {label} of marketing")

    Path(args.out).write_text(json.dumps({
        "config_hash": base_cfg.hash(), "amount": args.amount, "pre_money": args.pre_money,
        "trigger_arr": args.trigger_arr, "hire_share": args.hire_share, "rows": rows,
    }, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
