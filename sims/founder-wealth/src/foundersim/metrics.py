"""Reporting (PRD §5.3) and calibration diagnostics (PRD §4).

Never a mean alone. Venture outcomes are power-law and bootstrapped outcomes are
not, so a mean comparison is arithmetic that tells you nothing (PRD §1).

Paired differences, never two independent distributions: the arms share a founder,
so the difference is taken *within* a founder before anything is aggregated
(METHOD §5). The confidence interval is over replicates, which is the only level
at which the runs are independent.
"""

from __future__ import annotations

import numpy as np

from .cohort import ArmResult
from .ledger import Wealth

PERCENTILES = (10, 25, 50, 75, 90, 99)


def distribution(values: np.ndarray) -> dict[str, float]:
    """Percentiles and threshold probabilities for a wealth array."""
    out = {f"p{p}": float(np.percentile(values, p)) for p in PERCENTILES}
    out["mean"] = float(values.mean())  # reported, never the headline
    out["p_gt_1m"] = float((values > 1e6).mean())
    out["p_gt_10m"] = float((values > 10e6).mean())
    out["p_gt_100m"] = float((values > 100e6).mean())
    out["p_negative"] = float((values < 0).mean())
    return out


def summarise(w: Wealth) -> dict[str, float]:
    """Everything PRD §5.3 asks for, for one arm."""
    out = {f"net_{k}": v for k, v in distribution(w.net).items()}
    out |= {f"gross_{k}": v for k, v in distribution(w.gross).items()}
    out["p_equity_zero"] = float(w.equity_zero.mean())
    out["p_died"] = float(w.died.mean())
    out["years_to_million_median"] = float(np.median(w.years_to_million))
    out["p_never_million"] = float((w.years_to_million > w.years_active.max()).mean())
    out["median_years_active"] = float(np.median(w.years_active))
    out["median_founder_pct"] = float(np.median(w.founder_pct))
    out["mean_raised"] = float(w.raised.mean())
    return out


def calibration(arm: ArmResult, horizon: int) -> dict[str, float]:
    """The PRD §4 targets, measured on an arm so they can be checked.

    These are outputs, not inputs. Nothing in the model asserts a failure rate;
    it is read off here and compared with the world (PRD §3.4).

    The published statistics describe **seed-funded** cohorts, so the ones that
    correspond to them are conditioned on having closed a seed round rather than
    on the whole arm. Getting that denominator wrong is the easiest way to
    "calibrate" a model to the wrong world.
    """
    cohort = arm.max_stage >= 1  # closed a seed round: the VC-backed cohort
    n_cohort = max(int(cohort.sum()), 1)
    share = lambda mask: float(mask.sum() / n_cohort)

    survived_5y = ~(arm.died & (arm.exit_year < 5))
    return {
        "n": float(arm.n),
        "share_seed_funded": float(cohort.mean()),
        "p_died": float(arm.died.mean()),
        "p_abandoned": float(arm.abandoned.mean()),
        "p_died_cohort": float(arm.died[cohort].mean()) if cohort.any() else 0.0,
        "p_exit_gt_1b": share(cohort & (arm.exit_value > 1e9)),
        "p_exit_gt_100m": share(cohort & (arm.exit_value > 100e6)),
        "p_below_1x_capital": share(cohort & (arm.exit_value < arm.raised)),
        "seed_to_a_graduation": _graduation(arm, 1, 2),
        "preseed_to_seed_graduation": _graduation(arm, 0, 1),
        "a_to_b_graduation": _graduation(arm, 2, 3),
        "median_exit_value_cohort": (
            float(np.median(arm.exit_value[cohort])) if cohort.any() else 0.0
        ),
        "median_founder_gross_cohort": (
            float(np.median(arm.founder_gross[cohort])) if cohort.any() else 0.0
        ),
        "median_exit_year": (
            float(np.median(arm.exit_year[arm.exited])) if arm.exited.any() else -1.0
        ),
        "median_exit_year_big": (
            float(np.median(arm.exit_year[arm.exit_value > 100e6]))
            if (arm.exit_value > 100e6).any()
            else -1.0
        ),
        "p_survive_5y": float(survived_5y.mean()),
        "mean_raised_cohort": float(arm.raised[cohort].mean()) if cohort.any() else 0.0,
        "horizon": float(horizon),
    }


def _graduation(arm: ArmResult, frm: int, to: int) -> float:
    """Share of companies that closed round ``frm`` and went on to close ``to``."""
    reached_from = arm.max_stage >= frm
    if not reached_from.any():
        return 0.0
    return float((arm.max_stage[reached_from] >= to).mean())


def paired_difference(a: np.ndarray, b: np.ndarray) -> dict[str, float]:
    """Difference taken within a founder, then summarised.

    ``a - b`` per founder. The median of the paired difference is not the
    difference of the medians, and for skewed outcomes it is the more honest
    number: it answers "for what share of founders was this the better choice".
    """
    d = a - b
    return {
        "median_diff": float(np.median(d)),
        "mean_diff": float(d.mean()),
        "p_a_better": float((d > 0).mean()),
        "p10_diff": float(np.percentile(d, 10)),
        "p90_diff": float(np.percentile(d, 90)),
    }


def replicate_interval(values: list[float] | np.ndarray) -> dict[str, float]:
    """Mean and a normal interval across replicates.

    Replicates are the only independent unit here: 5,000 founders inside one
    replicate share a parameter set and a seed, so an interval computed across
    founders would be far too tight (METHOD §1).
    """
    v = np.asarray(values, dtype=float)
    n = v.size
    mean = float(v.mean())
    if n < 2:
        return {"mean": mean, "sem": 0.0, "lo": mean, "hi": mean, "n": float(n)}
    sem = float(v.std(ddof=1) / np.sqrt(n))
    return {"mean": mean, "sem": sem, "lo": mean - 1.96 * sem, "hi": mean + 1.96 * sem, "n": float(n)}


def luck_crossing(
    a: np.ndarray, b: np.ndarray, luck: np.ndarray, n_bins: int = 20
) -> list[dict[str, float]]:
    """Median wealth of each arm by percentile of luck (PRD §5.3).

    "At what percentile of luck does raising overtake bootstrapping?" If the
    answer is "above the 90th", that is the finding, and it is a very different
    claim from "raising pays".
    """
    order = np.argsort(luck)
    bins = np.array_split(order, n_bins)
    rows = []
    for i, ix in enumerate(bins):
        rows.append(
            {
                "bin": float(i),
                "pct_lo": float(100.0 * i / n_bins),
                "pct_hi": float(100.0 * (i + 1) / n_bins),
                "median_a": float(np.median(a[ix])),
                "median_b": float(np.median(b[ix])),
                "p_a_better": float((a[ix] > b[ix]).mean()),
            }
        )
    return rows
