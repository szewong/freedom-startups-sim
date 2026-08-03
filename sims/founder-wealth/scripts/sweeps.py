"""Phase 6: report the sweeps, because any single setting is an illustration.

METHOD §9: effects are usually monotone in the parameter you chose, so if the
effect grows with a knob you can pick the setting that makes any claim look as
strong as you like. Every uncertain parameter in this model is swept here and
reported as a curve.

Two of these sweeps are load-bearing rather than decorative:

* ``capital_upside`` is the honesty check demanded by METHOD §3. Capital is
  allowed to create real value, and the amount is a knob. If the conclusion only
  survives at zero upside, the conclusion is an artefact of the setup.
* ``payoff_shape`` is the direct test of the v1.0 result the PRD carries over:
  the preference multiple is the *height* of the founder's bar and the carve-out
  is its *shape*. If shape matters more than height here too, that result
  survived translation into a completely different domain.

    .venv/bin/python scripts/sweeps.py --config configs/frozen.yaml
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from foundersim.cohort import run_arm
from foundersim.config import RunConfig
from foundersim.latents import draw_latents, draw_noise
from foundersim.ledger import build_ledger
from foundersim.metrics import replicate_interval
from foundersim.strategy import STRATEGIES

BASELINE = "bootstrap"


@dataclass(frozen=True)
class Point:
    label: str
    overrides: dict[str, float | bool]


@dataclass(frozen=True)
class Sweep:
    name: str
    question: str
    points: tuple[Point, ...]


SWEEPS: tuple[Sweep, ...] = (
    Sweep(
        "preference_height",
        "How much of the founder's downside is the term sheet rather than the business?",
        (
            Point("1.0x", {"capital__pref_multiple": 1.0}),
            Point("1.5x", {"capital__pref_multiple": 1.5}),
            Point("2.0x", {"capital__pref_multiple": 2.0}),
            Point("3.0x", {"capital__pref_multiple": 3.0}),
            Point("1x participating", {"capital__participating": True}),
        ),
    ),
    Sweep(
        "payoff_shape",
        "Does replacing the step with a ramp matter more than lowering the step?",
        (
            Point("no carve-out", {"capital__carve_out": 0.0}),
            Point("5%", {"capital__carve_out": 0.05}),
            Point("10%", {"capital__carve_out": 0.10}),
            Point("20%", {"capital__carve_out": 0.20}),
        ),
    ),
    Sweep(
        "capital_upside",
        "Does the answer survive letting capital genuinely improve the business?",
        (
            Point("none", {"business__capital_execution_boost": 0.0}),
            Point("0.15", {"business__capital_execution_boost": 0.15}),
            Point("0.40", {"business__capital_execution_boost": 0.40}),
            Point("0.80", {"business__capital_execution_boost": 0.80}),
        ),
    ),
    Sweep(
        "speed_premium",
        "How much does the market punish being slow?",
        (
            Point("no decay", {"business__market_decay": 0.0}),
            Point("6%/yr", {"business__market_decay": 0.06}),
            Point("15%/yr", {"business__market_decay": 0.15}),
            Point("30%/yr", {"business__market_decay": 0.30}),
        ),
    ),
    Sweep(
        "market_tail",
        "Does raising only pay for founders in genuinely huge markets?",
        (
            Point("sigma 1.2", {"latents__market_sigma": 1.2}),
            Point("sigma 1.6", {"latents__market_sigma": 1.6}),
            Point("sigma 2.0", {"latents__market_sigma": 2.0}),
            Point("sigma 2.4", {"latents__market_sigma": 2.4}),
        ),
    ),
    Sweep(
        "exit_regime",
        "Is the answer regime-dependent? Almost certainly.",
        (
            Point("deep bear 0.5x", {"exit__regime": 0.5}),
            Point("bear 0.75x", {"exit__regime": 0.75}),
            Point("neutral", {"exit__regime": 1.0}),
            Point("bull 1.5x", {"exit__regime": 1.5}),
            Point("bubble 2.5x", {"exit__regime": 2.5}),
        ),
    ),
    Sweep(
        "opportunity_cost",
        "How much of the bootstrapper's advantage is simply being paid?",
        (
            Point("$150k", {"ledger__opportunity_cost": 150_000.0}),
            Point("$250k", {"ledger__opportunity_cost": 250_000.0}),
            Point("$300k", {"ledger__opportunity_cost": 300_000.0}),
            Point("$400k", {"ledger__opportunity_cost": 400_000.0}),
        ),
    ),
    Sweep(
        "secondary",
        "Does partial liquidity change the calculus materially?",
        (
            Point("none", {"capital__secondary_prob": 0.0}),
            Point("35%", {"capital__secondary_prob": 0.35}),
            Point("80%", {"capital__secondary_prob": 0.80}),
            Point("80%, $25M cap", {"capital__secondary_prob": 0.80, "capital__secondary_cap": 25e6}),
        ),
    ),
    Sweep(
        "bootstrapper_ceiling",
        "The self-funded growth ceiling is a modelling choice (PRD §8) — sweep it.",
        (
            Point("organic 1.8", {"business__organic_scale": 1.8}),
            Point("organic 2.6", {"business__organic_scale": 2.6}),
            Point("organic 3.4", {"business__organic_scale": 3.4}),
            Point("staffing pain 0", {"business__understaffing_churn": 0.0}),
            Point("staffing pain 0.5", {"business__understaffing_churn": 0.5}),
        ),
    ),
    Sweep(
        "investor_noise",
        "Gates encode a theory of investors (PRD §8). Is the conclusion sensitive to it?",
        (
            Point("hard threshold", {"capital__gate_noise_sigma": 0.0}),
            Point("sigma 0.35", {"capital__gate_noise_sigma": 0.35}),
            Point("sigma 0.70", {"capital__gate_noise_sigma": 0.70}),
        ),
    ),
    Sweep(
        "founder_patience",
        "When founders give up drives the bootstrapped failure rate — sweep it.",
        (
            Point("quit after 2y", {"exit__abandon_years": 2}),
            Point("quit after 4y", {"exit__abandon_years": 4}),
            Point("quit after 6y", {"exit__abandon_years": 6}),
        ),
    ),
)


def evaluate(cfg: RunConfig, n_replicates: int) -> dict[str, dict[str, dict[str, float]]]:
    """Median net wealth per arm, and the paired gap against the baseline."""
    per_arm: dict[str, list[float]] = {s.name: [] for s in STRATEGIES}
    gap: dict[str, list[float]] = {s.name: [] for s in STRATEGIES}
    zero: dict[str, list[float]] = {s.name: [] for s in STRATEGIES}
    better: dict[str, list[float]] = {s.name: [] for s in STRATEGIES}

    for rep in range(n_replicates):
        lat, noise = draw_latents(cfg, rep), draw_noise(cfg, rep)
        wealth = {s.name: build_ledger(cfg, run_arm(cfg, lat, noise, s)) for s in STRATEGIES}
        base = wealth[BASELINE].net
        for name, w in wealth.items():
            per_arm[name].append(float(np.median(w.net)))
            gap[name].append(float(np.median(w.net - base)))
            zero[name].append(float(w.equity_zero.mean()))
            better[name].append(float((w.net > base).mean()))

    return {
        name: {
            "median_net": replicate_interval(per_arm[name]),
            "paired_gap_vs_bootstrap": replicate_interval(gap[name]),
            "p_equity_zero": replicate_interval(zero[name]),
            "p_beats_bootstrap": replicate_interval(better[name]),
        }
        for name in per_arm
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/frozen.yaml")
    ap.add_argument("--founders", type=int, default=3000)
    ap.add_argument("--replicates", type=int, default=4)
    ap.add_argument("--only", default=None, help="run a single sweep by name")
    ap.add_argument("--out", default="results/sweeps.json")
    args = ap.parse_args()

    base = RunConfig.from_yaml(args.config).replace(n_founders=args.founders)
    sweeps = [s for s in SWEEPS if args.only in (None, s.name)]
    print(f"config hash {base.hash()}  |  {len(sweeps)} sweeps  |  "
          f"{args.founders} founders x {args.replicates} replicates")

    out: dict[str, object] = {"config_hash": base.hash(), "sweeps": {}}
    for sweep in sweeps:
        print(f"\n{sweep.name}: {sweep.question}")
        rows = []
        for point in sweep.points:
            cfg = base.replace(**point.overrides)
            stats = evaluate(cfg, args.replicates)
            rows.append({"label": point.label, "overrides": point.overrides, "arms": stats})
            venture = stats["standard_venture"]["paired_gap_vs_bootstrap"]["mean"]
            maxv = stats["max_venture"]["paired_gap_vs_bootstrap"]["mean"]
            print(
                f"  {point.label:18s} median net: boot "
                f"${stats['bootstrap']['median_net']['mean']/1e6:6.2f}M  "
                f"venture ${stats['standard_venture']['median_net']['mean']/1e6:6.2f}M  "
                f"| paired gap: standard ${venture/1e6:+6.2f}M  max ${maxv/1e6:+6.2f}M"
            )
        out["sweeps"][sweep.name] = {"question": sweep.question, "points": rows}

    Path(args.out).write_text(json.dumps(out, indent=2))
    print(f"\nwrote {args.out}")


if __name__ == "__main__":
    main()
