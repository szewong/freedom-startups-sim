"""Fit the model to the world before asking it anything (PRD §4, METHOD §4).

Phase 4 is the gate. A model that cannot reproduce the aggregate statistics it
claims to describe has no standing to make claims about them, so the funded arm
is fitted to published cohort outcomes *first*, the parameters are frozen, and
only then is a counterfactual run.

What is fitted here is deliberately small: five parameters of the growth engine
and the market. Everything from the PRD's tables — round sizes, dilution,
preferences, margins, cost per head — is left alone, because those are observed
quantities and not ours to tune.

Any parameter touched after a counterfactual has been seen is a p-hacking
exposure and must be recorded as one in FINDINGS.md.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .cohort import run_arm
from .config import RunConfig, rng_for
from .latents import draw_latents, draw_noise
from .metrics import calibration
from .strategy import BY_NAME


@dataclass(frozen=True)
class Target:
    """One published statistic the model has to reproduce."""

    key: str
    arm: str
    value: float
    weight: float = 1.0
    tolerance: float = 0.35  # relative; a fit inside this is "hit"
    note: str = ""


# PRD §4. Sources are published cohort analyses; the values are the central
# figures those analyses converge on, not precise measurements. The tolerance
# reflects that — this is calibration to an order of magnitude and a shape, and
# claiming more would be false precision.
TARGETS: tuple[Target, ...] = (
    Target("p_exit_gt_1b", "standard_venture", 0.010, 1.0, 0.60, "VC-backed reaching $1B+"),
    Target("p_exit_gt_100m", "standard_venture", 0.100, 1.5, 0.40, "VC-backed reaching $100M+"),
    Target("seed_to_a_graduation", "standard_venture", 0.220, 1.5, 0.35, "Seed -> Series A"),
    Target("p_below_1x_capital", "standard_venture", 0.700, 2.0, 0.15, "Returning < 1x capital"),
    Target("median_exit_year_big", "standard_venture", 8.0, 1.0, 0.30, "Time to a real exit"),
    Target("p_survive_5y", "bootstrap", 0.600, 1.0, 0.30, "Bootstrapped 5-year survival"),
)

# The search space. Each entry is (path, lo, hi) and is sampled log-uniformly.
SEARCH_SPACE: tuple[tuple[str, float, float], ...] = (
    ("business__growth_scale", 250.0, 1400.0),
    ("business__organic_scale", 1.6, 4.5),
    ("business__effort_scale", 4.0, 25.0),
    ("latents__market_sigma", 1.2, 2.4),
    ("latents__exec_sigma", 0.25, 0.75),
    # How fast venture money burns drives the funded failure rate, so it is
    # fitted rather than asserted (PRD §3.4: do not hardcode a failure rate).
    ("spend__funded_spend_rate", 0.20, 0.65),
    ("exit__offer_prob", 0.08, 0.40),
    # How noisy investors are moves the graduation rates directly (PRD §8).
    ("capital__gate_noise_sigma", 0.10, 0.80),
    ("latents__market_median", 120e6, 700e6),
)


def measure(
    cfg: RunConfig, arms: tuple[str, ...], replicates: int = 1
) -> dict[str, dict[str, float]]:
    """Run the named arms and read the calibration statistics off them.

    Averaged over replicates: a parameter set chosen on a single draw is fitted
    to that draw's sampling noise as much as to the world, and the top-tail
    targets here (1% events) are exactly where a single draw is least reliable.
    """
    totals: dict[str, dict[str, float]] = {name: {} for name in arms}
    for rep in range(replicates):
        lat = draw_latents(cfg, rep)
        noise = draw_noise(cfg, rep)
        for name in arms:
            stats = calibration(run_arm(cfg, lat, noise, BY_NAME[name]), cfg.exit.horizon_years)
            for k, v in stats.items():
                totals[name][k] = totals[name].get(k, 0.0) + v / replicates
    return totals


def score(stats: dict[str, dict[str, float]], targets: tuple[Target, ...] = TARGETS) -> float:
    """Weighted squared log-ratio error. Lower is better, 0 is exact.

    Log-ratio rather than absolute error because the targets span four orders of
    magnitude — a 1% target and a 70% target must not be traded off in raw
    percentage points.
    """
    total = 0.0
    for t in targets:
        got = stats[t.arm].get(t.key, 0.0)
        got = max(got, 1e-4)
        total += t.weight * (np.log(got / t.value)) ** 2
    return float(total)


def report(stats: dict[str, dict[str, float]], targets: tuple[Target, ...] = TARGETS) -> list[dict]:
    """Per-target comparison, with an explicit hit/miss."""
    rows = []
    for t in targets:
        got = stats[t.arm].get(t.key, 0.0)
        rel = abs(got - t.value) / max(t.value, 1e-9)
        rows.append(
            {
                "target": t.key,
                "arm": t.arm,
                "want": t.value,
                "got": float(got),
                "rel_error": float(rel),
                "hit": bool(rel <= t.tolerance),
                "note": t.note,
            }
        )
    return rows


def search(
    base: RunConfig,
    n_trials: int = 200,
    n_founders: int = 2500,
    n_refine: int = 120,
    replicates: int = 2,
    seed: int = 1,
    verbose: bool = True,
) -> tuple[RunConfig, float, list[dict]]:
    """Random search, then local refinement. Returns the best config and score.

    Random rather than grid: nine dimensions at even three levels each is 20,000
    runs to cover the space badly, and random search spends its budget resolving
    whichever dimensions actually matter. The refinement pass then does what
    random search is bad at — the last factor of two.
    """
    rng = rng_for(seed, "calibration_search")
    arms = tuple(sorted({t.arm for t in TARGETS}))
    trial_cfg = base.replace(n_founders=n_founders)
    history: list[dict] = []

    def evaluate(values: dict[str, float], tag: str, i: int) -> float:
        cfg = trial_cfg.replace(**values)
        try:
            s = score(measure(cfg, arms, replicates))
        except Exception as exc:  # pragma: no cover - a bad corner of the space
            history.append({"phase": tag, "trial": i, "error": repr(exc), **values})
            return np.inf
        history.append({"phase": tag, "trial": i, "score": s, **values})
        return s

    best_values = {path: float(np.sqrt(lo * hi)) for path, lo, hi in SEARCH_SPACE}
    best_score = evaluate(best_values, "seed", -1)

    for i in range(n_trials):
        values = {
            path: float(np.exp(rng.uniform(np.log(lo), np.log(hi))))
            for path, lo, hi in SEARCH_SPACE
        }
        s = evaluate(values, "random", i)
        if s < best_score:
            best_values, best_score = values, s
            if verbose:
                print(f"  random {i:3d}  score {s:.4f}")

    # Local refinement: perturb every coordinate by a small lognormal factor and
    # keep improvements. Cheap, and it is where the last factor of two lives.
    for i in range(n_refine):
        scale = 0.25 if i < n_refine // 2 else 0.10
        values = {}
        for path, lo, hi in SEARCH_SPACE:
            v = best_values[path] * float(np.exp(rng.normal(0.0, scale)))
            values[path] = float(np.clip(v, lo, hi))
        s = evaluate(values, "refine", i)
        if s < best_score:
            best_values, best_score = values, s
            if verbose:
                print(f"  refine {i:3d}  score {s:.4f}  " + "  ".join(
                    f"{k.split('__')[1]}={v:.3g}" for k, v in best_values.items()
                ))

    best_cfg = trial_cfg.replace(**best_values).replace(n_founders=base.n_founders)
    return best_cfg, best_score, history


def freeze(cfg: RunConfig, path: str | Path, stats: dict[str, dict[str, float]]) -> None:
    """Write the calibrated config and the fit it achieved, side by side.

    The fit is written next to the parameters on purpose: anyone reading the
    frozen config can see exactly how well it reproduced the world, and any later
    change to it is visible in the diff.
    """
    path = Path(path)
    cfg.to_yaml(path)
    Path(path.with_suffix(".fit.json")).write_text(
        json.dumps(
            {
                "config_hash": cfg.hash(),
                "targets": report(stats),
                "score": score(stats),
                "stats": stats,
            },
            indent=2,
        )
    )
