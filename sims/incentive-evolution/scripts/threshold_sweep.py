"""How high does the bar have to be — and can it be too high?

A calibration question with a real edge to it. In this engine the average winning
margin is ~9 points, so "win by 10+" clears only about 39% of wins. It restricts
plenty, but it is not draconian, and the paper's phrasing makes it sound harsher
than it is.

Raising the bar further should amplify the effect — the 5-to-10 comparison already
showed that. But it cannot do so indefinitely: at a high enough threshold almost
nobody is ever rewarded, the per-season ranking becomes nearly random, and
selection has nothing to act on. We expect an inverted U, and the peak is the
interesting number.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from incentive_sim.config import LeagueConfig, RunConfig
from incentive_sim.season import run_replicate

THRESHOLDS = [1, 3, 5, 10, 15, 20, 25]
SEASONS = 500
REPLICATES = 10
TAIL = 30

TRACKED = ("strat_aggression", "attr_offense", "margin_sd", "reward_rate", "blowout_rate")

A_COLOUR, B_COLOUR = "#2a78d6", "#eb6834"
SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"


def one_threshold(threshold: int) -> dict[str, tuple[float, float]]:
    cfg = RunConfig(
        name=f"thr_{threshold}",
        seasons=SEASONS,
        replicates=REPLICATES,
        leagues=(LeagueConfig("A", 1), LeagueConfig("B", threshold)),
    )

    per_league: dict[str, list[dict[str, float]]] = {"A": [], "B": []}
    for replicate in range(REPLICATES):
        for history in run_replicate(cfg, replicate):
            tail = history.rows[-TAIL:]
            per_league[history.league].append(
                {k: float(np.mean([r[k] for r in tail])) for k in TRACKED}
            )

    out = {}
    for key in TRACKED:
        a = np.array([r[key] for r in per_league["A"]])
        b = np.array([r[key] for r in per_league["B"]])
        delta = b - a
        se = delta.std(ddof=1) / np.sqrt(delta.size)
        out[key] = (float(delta.mean()), float(1.96 * se))
    out["reward_rate_b"] = (float(np.mean([r["reward_rate"] for r in per_league["B"]])), 0.0)
    return out


def main() -> int:
    print(f"threshold sweep: {THRESHOLDS}, {SEASONS} seasons x {REPLICATES} replicates\n")
    print(f"{'bar':>5}{'aggression gap':>18}{'margin sd gap':>16}{'B reward rate':>16}")
    print("-" * 56)

    start = time.perf_counter()
    results = {}
    for threshold in THRESHOLDS:
        results[threshold] = one_threshold(threshold)
        g = results[threshold]
        print(f"{threshold:>5}{g['strat_aggression'][0]:>12.4f} ±{g['strat_aggression'][1]:.4f}"
              f"{g['margin_sd'][0]:>16.3f}{g['reward_rate_b'][0]:>16.3f}"
              f"   ({time.perf_counter() - start:.0f}s)")

    out_dir = Path("results/threshold_sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "threshold_sweep.json").write_text(json.dumps({
        "thresholds": THRESHOLDS, "seasons": SEASONS, "replicates": REPLICATES,
        "gaps": {str(t): {k: list(v) for k, v in g.items()} for t, g in results.items()},
    }, indent=2))

    render(results)
    print(f"\nwrote {out_dir / 'threshold_sweep.json'} and figures/threshold_sweep.png")
    return 0


def render(results: dict) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    })
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 8.2), dpi=200, sharex=True)
    fig.subplots_adjust(left=0.13, right=0.95, top=0.72, bottom=0.09, hspace=0.28)

    x = np.arange(len(THRESHOLDS))
    means = np.array([results[t]["strat_aggression"][0] for t in THRESHOLDS])
    cis = np.array([results[t]["strat_aggression"][1] for t in THRESHOLDS])
    rewards = np.array([results[t]["reward_rate_b"][0] for t in THRESHOLDS])

    ax = axes[0]
    ax.axhline(0, color=INK, linewidth=1.2, zorder=3)
    ax.fill_between(x, means - cis, means + cis, color=B_COLOUR, alpha=0.18, linewidth=0, zorder=2)
    ax.plot(x, means, color=B_COLOUR, linewidth=2.4, zorder=4)
    ax.plot(x, means, "o", color=B_COLOUR, markersize=6, markeredgecolor=SURFACE,
            markeredgewidth=1.5, zorder=5)
    ax.set_ylabel("Aggression gap  (B − A)", fontsize=10.5, color=INK_2)
    ax.set_title("How much volatility the bar buys", fontsize=12, color=INK,
                 loc="left", pad=8, fontweight="bold")

    ax = axes[1]
    ax.plot(x, rewards * 100, color=A_COLOUR, linewidth=2.4, zorder=4)
    ax.plot(x, rewards * 100, "o", color=A_COLOUR, markersize=6, markeredgecolor=SURFACE,
            markeredgewidth=1.5, zorder=5)
    ax.set_ylabel("Share of games League B rewards (%)", fontsize=10.5, color=INK_2)
    ax.set_title("How much signal selection has left to work with", fontsize=12, color=INK,
                 loc="left", pad=8, fontweight="bold")
    ax.set_xlabel("League B must win by (points)", fontsize=11, color=INK_2)

    for ax in axes:
        ax.set_xticks(x)
        ax.set_xticklabels([str(t) for t in THRESHOLDS])
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=INK_3, labelsize=10, length=0)

    fig.text(0.13, 0.965, "A bar can be too high to select for anything.",
             fontsize=16, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.13, 0.895,
             "The average winning margin here is about 9 points, so “win by 10+” already discards\n"
             "roughly 61% of wins. Pushing the bar higher amplifies the effect — until so few games\n"
             "are rewarded that the season ranking is nearly random and selection has nothing to act on.",
             fontsize=11, color=INK_2, ha="left", va="top", linespacing=1.6)

    Path("figures").mkdir(exist_ok=True)
    fig.savefig("figures/threshold_sweep.png", facecolor=SURFACE)


if __name__ == "__main__":
    raise SystemExit(main())
