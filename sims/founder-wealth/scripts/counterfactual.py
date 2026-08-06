"""Phases 5 and 6: the paired counterfactual, and the null control (PRD §5).

Run only against a frozen config. The parameters are not to be touched after
this has been looked at (METHOD §4); if they are, that goes in FINDINGS.md as a
p-hacking exposure.

    .venv/bin/python scripts/counterfactual.py --config configs/frozen.yaml
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
from foundersim.metrics import (
    calibration,
    luck_crossing,
    paired_difference,
    replicate_interval,
    summarise,
)
from foundersim.strategy import STRATEGIES

BASELINE = "bootstrap"  # every paired difference is measured against this


def run_world(cfg: RunConfig, replicate: int) -> dict[str, object]:
    """One replicate: every strategy over one set of draws."""
    lat = draw_latents(cfg, replicate)
    noise = draw_noise(cfg, replicate)
    arms = {s.name: run_arm(cfg, lat, noise, s) for s in STRATEGIES}
    return {
        "latents": lat,
        "arms": arms,
        "wealth": {name: build_ledger(cfg, arm) for name, arm in arms.items()},
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/frozen.yaml")
    ap.add_argument("--founders", type=int, default=None)
    ap.add_argument("--replicates", type=int, default=None)
    ap.add_argument("--out", default="results/counterfactual.json")
    args = ap.parse_args()

    cfg = RunConfig.from_yaml(args.config)
    if args.founders:
        cfg = cfg.replace(n_founders=args.founders)
    if args.replicates:
        cfg = cfg.replace(n_replicates=args.replicates)
    control_cfg = cfg.replace(capital__null_control=True)

    print(f"config {Path(args.config).name}  hash {cfg.hash()}")
    print(f"{cfg.n_founders} founders x {cfg.n_replicates} replicates x {len(STRATEGIES)} arms")

    per_replicate: dict[str, list[dict[str, float]]] = {s.name: [] for s in STRATEGIES}
    paired: dict[str, list[dict[str, float]]] = {s.name: [] for s in STRATEGIES}
    paired_own: dict[str, list[dict[str, float]]] = {s.name: [] for s in STRATEGIES}
    paired_labour: dict[str, list[dict[str, float]]] = {s.name: [] for s in STRATEGIES}
    did: dict[str, list[float]] = {s.name: [] for s in STRATEGIES}
    pooled_net: dict[str, list[np.ndarray]] = {s.name: [] for s in STRATEGIES}
    pooled_market: list[np.ndarray] = []
    pooled_quality: list[np.ndarray] = []
    calib: dict[str, list[dict[str, float]]] = {s.name: [] for s in STRATEGIES}

    for rep in range(cfg.n_replicates):
        world = run_world(cfg, rep)
        control = run_world(control_cfg, rep)
        base = world["wealth"][BASELINE].net
        base_control = control["wealth"][BASELINE].net

        for name, records in per_replicate.items():
            w = world["wealth"][name]
            records.append(summarise(w))
            calib[name].append(calibration(world["arms"][name], cfg.exit.horizon_years))
            paired[name].append(paired_difference(w.net, base))
            # The same paired comparison run on each half separately. Medians of
            # the halves do not add up to the median of the total — that is a
            # property of medians, not a bug — so all three are reported.
            paired_own[name].append(
                paired_difference(w.ownership, world["wealth"][BASELINE].ownership)
            )
            paired_labour[name].append(
                paired_difference(w.labour_pl, world["wealth"][BASELINE].labour_pl)
            )
            # Difference in differences: what is left of the gap once the same
            # machinery is run with dilution and preferences removed (METHOD §2).
            treated_gap = float(np.median(w.net - base))
            control_gap = float(np.median(control["wealth"][name].net - base_control))
            did[name].append(treated_gap - control_gap)
            pooled_net[name].append(w.net)

        pooled_market.append(world["latents"].market_size)
        pooled_quality.append(world["latents"].fit * world["latents"].skill)
        print(f"  replicate {rep} done")

    def across(name: str, key: str) -> dict[str, float]:
        return replicate_interval([r[key] for r in per_replicate[name]])

    report = {
        "config_hash": cfg.hash(),
        "config": cfg.to_dict(),
        "baseline": BASELINE,
        "arms": {},
        "crossing": {},
    }

    for s in STRATEGIES:
        name = s.name
        report["arms"][name] = {
            "label": s.label,
            "net_median": across(name, "net_p50"),
            "net_p10": across(name, "net_p10"),
            "net_p90": across(name, "net_p90"),
            "net_p99": across(name, "net_p99"),
            "p_gt_1m": across(name, "net_p_gt_1m"),
            "p_gt_10m": across(name, "net_p_gt_10m"),
            "p_gt_100m": across(name, "net_p_gt_100m"),
            "p_equity_zero": across(name, "p_equity_zero"),
            "p_died": across(name, "p_died"),
            "p_worse_than_a_job": across(name, "net_p_negative"),
            "years_to_million": across(name, "years_to_million_median"),
            "ownership_median": across(name, "own_p50"),
            "ownership_p90": across(name, "own_p90"),
            "ownership_p99": across(name, "own_p99"),
            "p_own_gt_1m": across(name, "p_own_gt_1m"),
            "labour_median": across(name, "labour_p50"),
            "median_from_salary": across(name, "median_from_salary"),
            "median_from_distributions": across(name, "median_from_distributions"),
            "median_from_exit": across(name, "median_from_exit"),
            "paired_ownership_vs_baseline": {
                k: replicate_interval([r[k] for r in paired_own[name]])
                for k in paired_own[name][0]
            },
            "paired_labour_vs_baseline": {
                k: replicate_interval([r[k] for r in paired_labour[name]])
                for k in paired_labour[name][0]
            },
            "paired_vs_baseline": {
                k: replicate_interval([r[k] for r in paired[name]])
                for k in paired[name][0]
            },
            "null_controlled_gap": replicate_interval(did[name]),
            "calibration": {
                k: replicate_interval([r[k] for r in calib[name]]) for k in calib[name][0]
            },
        }

    # "At what percentile of luck does raising overtake bootstrapping?" needs an
    # index of luck, and which one is chosen changes the answer. Market size is
    # the luck the PRD has in mind; latent quality is the founder's own hand; and
    # the bootstrapped outcome is the most directly interpretable of the three —
    # it asks how venture does for founders who would have done this well alone.
    indices = {
        "market_size": np.concatenate(pooled_market),
        "latent_quality": np.concatenate(pooled_quality),
        "bootstrapped_outcome": np.concatenate(pooled_net[BASELINE]),
    }
    base_net = np.concatenate(pooled_net[BASELINE])
    for s in STRATEGIES:
        if s.name == BASELINE:
            continue
        report["crossing"][s.name] = {
            key: luck_crossing(np.concatenate(pooled_net[s.name]), base_net, index)
            for key, index in indices.items()
        }

    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"\nwrote {args.out}\n")
    print_summary(report)


def print_summary(report: dict) -> None:
    money = lambda x: f"${x/1e6:,.2f}M"
    print(f"{'strategy':18s} {'median net':>12s} {'p90':>12s} {'P(>$1M)':>9s} "
          f"{'P(equity=0)':>12s} {'P(<job)':>9s} {'vs boot':>12s}")
    for name, row in report["arms"].items():
        print(
            f"{name:18s} {money(row['net_median']['mean']):>12s} "
            f"{money(row['net_p90']['mean']):>12s} "
            f"{row['p_gt_1m']['mean']:>9.3f} {row['p_equity_zero']['mean']:>12.3f} "
            f"{row['p_worse_than_a_job']['mean']:>9.3f} "
            f"{money(row['paired_vs_baseline']['median_diff']['mean']):>12s}"
        )

    print("\nsalary taken out: what the shares alone returned, and what the wage alone did")
    print(f"{'strategy':18s} {'ownership med':>14s} {'own p90':>12s} {'P(own>$1M)':>11s} "
          f"{'own vs boot':>12s} {'labour med':>12s} {'labour vs boot':>15s}")
    for name, row in report["arms"].items():
        print(
            f"{name:18s} {money(row['ownership_median']['mean']):>14s} "
            f"{money(row['ownership_p90']['mean']):>12s} "
            f"{row['p_own_gt_1m']['mean']:>11.3f} "
            f"{money(row['paired_ownership_vs_baseline']['median_diff']['mean']):>12s} "
            f"{money(row['labour_median']['mean']):>12s} "
            f"{money(row['paired_labour_vs_baseline']['median_diff']['mean']):>15s}"
        )

    print("\nnull-controlled gap vs bootstrap (median paired difference, "
          "minus the same gap with dilution and preferences removed):")
    for name, row in report["arms"].items():
        g = row["null_controlled_gap"]
        print(f"  {name:18s} {money(g['mean'])}  [{money(g['lo'])}, {money(g['hi'])}]")


if __name__ == "__main__":
    main()
