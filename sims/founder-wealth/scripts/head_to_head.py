"""VC-funded against bootstrapped, head to head.

The counterfactual script reports all five strategies against each other. This
one narrows to the comparison the question is actually about and reports it in
the shapes a reader needs: the whole distribution rather than a few percentiles,
the outcome bands, where the money came from, and where the two curves cross.

Every number is paired — the same founder, the same idea, the same luck, run
down each path — so a difference here is financing and nothing else.

    .venv/bin/python scripts/head_to_head.py --config configs/frozen.yaml
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
from foundersim.metrics import luck_crossing, paired_difference, replicate_interval
from foundersim.strategy import BY_NAME

ARMS = ("bootstrap", "standard_venture", "max_venture")
BASELINE = "bootstrap"

# Wealth bands for the outcome mix. The first band is the one nobody advertises.
BANDS = (
    ("worse than a job", -np.inf, 0.0),
    ("$0 - $1M", 0.0, 1e6),
    ("$1M - $10M", 1e6, 10e6),
    ("$10M - $100M", 10e6, 100e6),
    ("over $100M", 100e6, np.inf),
)

CURVE_PERCENTILES = tuple(range(1, 100))


def band_mix(values: np.ndarray) -> dict[str, float]:
    return {name: float(((values >= lo) & (values < hi)).mean()) for name, lo, hi in BANDS}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/frozen.yaml")
    ap.add_argument("--founders", type=int, default=5000)
    ap.add_argument("--replicates", type=int, default=8)
    ap.add_argument("--out", default="results/head_to_head.json")
    args = ap.parse_args()

    cfg = RunConfig.from_yaml(args.config).replace(
        n_founders=args.founders, n_replicates=args.replicates
    )
    print(f"config hash {cfg.hash()}  |  {args.founders} x {args.replicates}  |  {len(ARMS)} arms")

    pooled: dict[str, dict[str, list[np.ndarray]]] = {
        a: {k: [] for k in ("net", "ownership", "labour", "salary", "dist", "exitpv")} for a in ARMS
    }
    scalars: dict[str, dict[str, list[float]]] = {a: {} for a in ARMS}
    paired: dict[str, list[dict[str, float]]] = {a: [] for a in ARMS}
    paired_own: dict[str, list[dict[str, float]]] = {a: [] for a in ARMS}
    paired_lab: dict[str, list[dict[str, float]]] = {a: [] for a in ARMS}
    quality: list[np.ndarray] = []

    def note(arm: str, key: str, value: float) -> None:
        scalars[arm].setdefault(key, []).append(float(value))

    for rep in range(args.replicates):
        lat, noise = draw_latents(cfg, rep), draw_noise(cfg, rep)
        results = {a: run_arm(cfg, lat, noise, BY_NAME[a]) for a in ARMS}
        wealth = {a: build_ledger(cfg, r) for a, r in results.items()}
        base = wealth[BASELINE]

        for a in ARMS:
            w, r = wealth[a], results[a]
            pooled[a]["net"].append(w.net)
            pooled[a]["ownership"].append(w.ownership)
            pooled[a]["labour"].append(w.labour_pl)
            pooled[a]["salary"].append(w.from_salary)
            pooled[a]["dist"].append(w.from_distributions)
            pooled[a]["exitpv"].append(w.from_exit)

            note(a, "p_died", r.died.mean())
            note(a, "p_equity_zero", w.equity_zero.mean())
            note(a, "p_worse_than_job", (w.net < 0).mean())
            note(a, "median_years_active", np.median(w.years_active))
            note(a, "median_exit_year", np.median(r.exit_year))
            note(a, "median_founder_pct", np.median(r.founder_pct))
            note(a, "mean_raised", r.raised.mean())
            note(a, "median_company_value", np.median(r.exit_value))
            note(a, "p90_company_value", np.percentile(r.exit_value, 90))
            note(a, "median_final_arr", np.median(r.final_arr))
            note(a, "years_to_million", np.median(w.years_to_million))
            for name, value in band_mix(w.net).items():
                note(a, f"band::{name}", value)

            paired[a].append(paired_difference(w.net, base.net))
            paired_own[a].append(paired_difference(w.ownership, base.ownership))
            paired_lab[a].append(paired_difference(w.labour_pl, base.labour_pl))

        quality.append(lat.fit * lat.skill)
        print(f"  replicate {rep} done")

    def curve(arm: str, key: str) -> list[float]:
        v = np.concatenate(pooled[arm][key])
        return [float(x) for x in np.percentile(v, CURVE_PERCENTILES)]

    report = {
        "config_hash": cfg.hash(),
        "n_founders": args.founders,
        "n_replicates": args.replicates,
        "horizon_years": cfg.exit.horizon_years,
        "opportunity_cost": cfg.ledger.opportunity_cost,
        "percentiles": list(CURVE_PERCENTILES),
        "bands": [name for name, _, _ in BANDS],
        "arms": {},
        "crossing": {},
    }

    for a in ARMS:
        report["arms"][a] = {
            "curve_net": curve(a, "net"),
            "curve_ownership": curve(a, "ownership"),
            "curve_labour": curve(a, "labour"),
            "median_sources": {
                "salary": float(np.median(np.concatenate(pooled[a]["salary"]))),
                "distributions": float(np.median(np.concatenate(pooled[a]["dist"]))),
                "exit_and_secondary": float(np.median(np.concatenate(pooled[a]["exitpv"]))),
            },
            "stats": {k: replicate_interval(v) for k, v in scalars[a].items()},
            "paired_net": {k: replicate_interval([r[k] for r in paired[a]]) for k in paired[a][0]},
            "paired_ownership": {
                k: replicate_interval([r[k] for r in paired_own[a]]) for k in paired_own[a][0]
            },
            "paired_labour": {
                k: replicate_interval([r[k] for r in paired_lab[a]]) for k in paired_lab[a][0]
            },
        }

    q = np.concatenate(quality)
    base_net = np.concatenate(pooled[BASELINE]["net"])
    base_own = np.concatenate(pooled[BASELINE]["ownership"])
    for a in ARMS:
        if a == BASELINE:
            continue
        report["crossing"][a] = {
            "net": luck_crossing(np.concatenate(pooled[a]["net"]), base_net, q),
            "ownership": luck_crossing(np.concatenate(pooled[a]["ownership"]), base_own, q),
        }

    Path(args.out).write_text(json.dumps(report, indent=2))
    print(f"\nwrote {args.out}")

    for a in ARMS:
        s = report["arms"][a]["stats"]
        p = report["arms"][a]["paired_net"]["median_diff"]["mean"]
        print(
            f"  {a:18s} median net ${report['arms'][a]['curve_net'][49]/1e6:+7.2f}M  "
            f"vs boot ${p/1e6:+6.2f}M  died {s['p_died']['mean']:.3f}  "
            f"equity zero {s['p_equity_zero']['mean']:.3f}"
        )


if __name__ == "__main__":
    main()
