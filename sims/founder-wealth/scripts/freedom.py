"""The Freedom Startup, against the alternatives, on one consistent basis.

Every number PAPER.md cites about the Freedom Startup comes from this script, so
that the claim and the evidence cannot drift apart. The scattered results in
results/delay_curve.json and results/raise_timing.json explored the space; this
one settles on a definition and measures it.

The definition, stated once:

    Bootstrap until the business is profitable while paying the founder a real
    salary AND has passed $100k of ARR. Then raise at every gate that clears,
    on the same ladder and the same terms as anyone else.

Two conditions, not one. "Wait for revenue" alone leaves you raising while still
burning; "wait for profitability" alone fires for companies too small to matter.
The conjunction is what the sweep in FINDINGS.md §11 picked out, and it is the
version this philosophy is actually claiming.

    .venv/bin/python scripts/freedom.py --config configs/smallcap.yaml
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
from foundersim.strategy import BY_NAME, Strategy

FREEDOM = Strategy(
    "freedom_startup", 5,
    label="Bootstrap to profitability and $100k ARR, then raise at every gate.",
    min_arr_to_raise=100e3, require_profitable=True,
)
# Three paths, and only three. Never raise; raise at day one on the best terms
# available to a company with no revenue; or wait until the business can already
# survive without the money. The other arms are still in strategy.py and the
# counterfactual script — they are not the argument.
ARMS: list[tuple[str, Strategy]] = [
    ("Bootstrap", Strategy("bootstrap", -1)),
    ("YC", BY_NAME["yc"]),
    ("Freedom Startup", FREEDOM),
]
BASELINE = "Bootstrap"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/smallcap.yaml")
    ap.add_argument("--founders", type=int, default=5000)
    ap.add_argument("--replicates", type=int, default=8)
    ap.add_argument("--out", default="results/freedom.json")
    args = ap.parse_args()

    cfg = RunConfig.from_yaml(args.config).replace(n_founders=args.founders)
    print(f"config {cfg.hash()} | {args.founders} founders x {args.replicates} replicates")
    print(f'"profitable" = covers a ${cfg.ledger.profit_test_salary/1e3:.0f}k founder salary\n')

    keys = ("net", "own", "eq0", "kept", "died", "prof", "ever",
            "gap_net", "gap_own", "beats", "gap_net_raised", "gap_own_raised", "beats_raised")
    acc = {name: {k: [] for k in keys} for name, _ in ARMS}
    quality: list[np.ndarray] = []
    pooled: dict[str, list[np.ndarray]] = {name: [] for name, _ in ARMS}

    for rep in range(args.replicates):
        lat, noise = draw_latents(cfg, rep), draw_noise(cfg, rep)
        base = build_ledger(cfg, run_arm(cfg, lat, noise, dict(ARMS)[BASELINE]))
        quality.append(lat.fit * lat.skill)

        for name, strat in ARMS:
            arm = run_arm(cfg, lat, noise, strat)
            w = build_ledger(cfg, arm)
            ev = arm.first_stage >= 0
            a = acc[name]
            pooled[name].append(w.ownership)

            a["net"].append(float(np.median(w.net)))
            a["own"].append(float(np.median(w.ownership)))
            a["eq0"].append(float(w.equity_zero.mean()))
            a["kept"].append(float(np.median(arm.founder_pct[ev])) if ev.any() else 1.0)
            a["died"].append(float(arm.died.mean()))
            a["prof"].append(float((arm.first_profit_year >= 0).mean()))
            a["ever"].append(float(ev.mean()))
            a["gap_net"].append(float(np.median(w.net - base.net)))
            a["gap_own"].append(float(np.median(w.ownership - base.ownership)))
            a["beats"].append(float((w.net > base.net).mean()))
            # Conditional on the strategy having actually fired. For an arm that
            # never raises this is the whole cohort, so it collapses to the same
            # number, which is the right behaviour.
            a["gap_net_raised"].append(
                float(np.median((w.net - base.net)[ev])) if ev.any() else 0.0)
            a["gap_own_raised"].append(
                float(np.median((w.ownership - base.ownership)[ev])) if ev.any() else 0.0)
            a["beats_raised"].append(
                float((w.net[ev] > base.net[ev]).mean()) if ev.any() else 0.0)

    out = {"config_hash": cfg.hash(), "profit_test_salary": cfg.ledger.profit_test_salary,
           "arms": {}}
    for name, _ in ARMS:
        out["arms"][name] = {k: replicate_interval(v) for k, v in acc[name].items()}

    # Where each strategy leads, by the founder quality nobody can observe.
    q = np.concatenate(quality)
    order = np.argsort(q)
    bins = np.array_split(order, 10)
    curve = []
    for i, ix in enumerate(bins):
        row = {"pct": (i + 1) * 10}
        for name, _ in ARMS:
            row[name] = float(np.median(np.concatenate(pooled[name])[ix]))
        curve.append(row)
    out["by_quality"] = curve

    Path(args.out).write_text(json.dumps(out, indent=2))

    g = lambda n, k: out["arms"][n][k]["mean"]  # noqa: E731
    print(f'{"strategy":18s}{"net":>8s}{"owned":>8s}{"eq=0":>7s}{"kept":>7s}'
          f'{"died":>7s}{"profit":>8s}{"raised":>8s}{"Δown":>8s}{"beats":>7s}')
    for name, _ in ARMS:
        print(f'{name:18s}{g(name,"net")/1e6:8.2f}{g(name,"own")/1e6:8.2f}{g(name,"eq0"):7.1%}'
              f'{g(name,"kept"):7.1%}{g(name,"died"):7.1%}{g(name,"prof"):8.1%}'
              f'{g(name,"ever"):8.1%}{g(name,"gap_own")/1e6:+8.2f}{g(name,"beats"):7.1%}')

    print("\namong founders for whom the strategy actually fired:")
    for name, _ in ARMS:
        if name == BASELINE:
            continue
        print(f'  {name:18s} Δnet {g(name,"gap_net_raised")/1e6:+6.2f}M  '
              f'Δown {g(name,"gap_own_raised")/1e6:+6.2f}M  '
              f'beats bootstrap {g(name,"beats_raised"):5.1%}')

    print("\nmedian ownership by decile of founder quality (unobservable to anyone):")
    print(f'  {"decile":>7s}' + "".join(f"{n:>18s}" for n, _ in ARMS))
    for row in curve:
        print(f'  {row["pct"]:>6d}%' + "".join(f'{row[n]/1e6:>17.2f}M' for n, _ in ARMS))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
