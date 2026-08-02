"""Prototype: does money buy away the failures you would have learned from?

First attempt gave capital no real upside — death rates were flat across every
funding level, so money could only blind and the answer was foregone. This version
makes capital genuinely useful, so the net effect has to be earned.

A team has `fit` (being right about the customer) and `cash`.

    outcome  = fit + efficiency * spend + noise      spending buys demand
    revenue  = outcome
    cash    += revenue - cost - spend

Spending is **individually profitable**: efficiency > 1, so a dollar of demand-gen
returns more than a dollar. It also keeps a weak team alive that would otherwise
burn out. Capital is therefore genuinely valuable on two counts.

The learning rule is the hypothesis:

    fit improves only in a period where the outcome visibly falls short.

Failure is the diagnostic, and money buys away failures. So capital simultaneously
buys survival (good) and buys silence (bad), and which dominates is a question
rather than an assumption.

The test: sweep starting capital, and measure what the population is actually
worth — its fit, and whether it can stand up unfunded.
"""

from __future__ import annotations

import numpy as np

N_TEAMS = 300
PERIODS = 400

FIT_START = 0.30
NOISE = 0.15

SPEND = 0.20            # demand-gen per period, if affordable
EFFICIENCY = 1.6        # a dollar of demand-gen returns 1.6 — genuinely profitable
COST = 0.55             # fixed operating cost per period
SHORTFALL = 0.62        # an outcome below this looks like a problem worth fixing
LEARN = 0.030           # how much of the remaining gap a visible failure closes
FIT_MUTATION = 0.025

CAPITALS = [0.0, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]


def run(capital: float, rng: np.random.Generator, can_spend: bool = True) -> dict[str, float]:
    fit = np.clip(rng.normal(FIT_START, 0.07, N_TEAMS), 0.02, 1.0)
    cash = np.full(N_TEAMS, capital)
    deaths = 0
    learned = 0

    for _ in range(PERIODS):
        spend = np.where(can_spend & (cash >= SPEND), SPEND, 0.0)
        outcome = fit + EFFICIENCY * spend + rng.normal(0, NOISE, N_TEAMS)
        cash = cash + outcome - COST - spend

        # You only fix what you can see is broken.
        visible = outcome < SHORTFALL
        learned += int(visible.sum())
        fit = np.clip(fit + visible * LEARN * (1.0 - fit), 0.0, 1.0)

        dying = np.flatnonzero(cash < 0.0)
        if dying.size:
            deaths += dying.size
            survivors = np.flatnonzero(cash >= 0.0)
            if survivors.size == 0:
                return {"fit": float(fit.mean()), "fit_sd": 0.0, "unfunded_viable": 0.0,
                        "deaths_per_100": 100.0, "learning_events": 0.0, "extinct": 1.0}
            parents = rng.choice(survivors, size=dying.size)
            fit[dying] = np.clip(
                fit[parents] + rng.normal(0, FIT_MUTATION, dying.size), 0.0, 1.0)
            cash[dying] = capital

    # Could this population stand on its own, with no money to spend?
    unfunded = fit - COST
    return {
        "fit": float(fit.mean()),
        "fit_sd": float(fit.std()),
        "unfunded_viable": float((unfunded > 0).mean()),
        "deaths_per_100": 100.0 * deaths / (N_TEAMS * PERIODS),
        "learning_events": learned / (N_TEAMS * PERIODS),
        "extinct": 0.0,
    }


def main() -> int:
    print(f"{N_TEAMS} teams, {PERIODS} periods, 8 seeds per level")
    print(f"spending is profitable (efficiency {EFFICIENCY}) and keeps weak teams alive\n")
    print(f"{'capital':>9}{'final fit':>12}{'viable unfunded':>18}"
          f"{'deaths/100':>13}{'learning/period':>17}")
    print("-" * 70)

    results = {}
    for capital in CAPITALS:
        runs = [run(capital, np.random.Generator(np.random.PCG64(
            np.random.SeedSequence([11, int(capital * 10), s])))) for s in range(8)]
        avg = {k: float(np.mean([r[k] for r in runs])) for k in runs[0]}
        results[capital] = avg
        print(f"{capital:>9.1f}{avg['fit']:>12.4f}{avg['unfunded_viable']:>17.1%}"
              f"{avg['deaths_per_100']:>13.2f}{avg['learning_events']:>17.3f}")

    best = max(results, key=lambda k: results[k]["fit"])
    interior = best not in (CAPITALS[0], CAPITALS[-1])
    print(f"\nbest fit at capital {best} ({results[best]['fit']:.4f})")
    print(f"  none: {results[CAPITALS[0]]['fit']:.4f}   most: {results[CAPITALS[-1]]['fit']:.4f}")

    # The counterfactual that isolates masking from survival: same capital, but
    # the team cannot convert it into demand.
    print(f"\n{'capital':>9}{'fit, can spend':>17}{'fit, cannot spend':>20}{'difference':>13}")
    print("-" * 60)
    for capital in CAPITALS:
        with_spend = results[capital]["fit"]
        no_spend = float(np.mean([run(capital, np.random.Generator(np.random.PCG64(
            np.random.SeedSequence([11, int(capital * 10), s]))), can_spend=False)["fit"]
            for s in range(8)]))
        print(f"{capital:>9.1f}{with_spend:>17.4f}{no_spend:>20.4f}{with_spend - no_spend:>13.4f}")

    print(f"\n{'INTERIOR OPTIMUM' if interior else 'MONOTONE — no interior optimum'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
