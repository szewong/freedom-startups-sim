"""Why the volatile league wins games but loses tournaments.

The neutral head-to-head turned up a puzzle: B-bred teams are roughly level with
A-bred teams in a single game, yet win far fewer championships. A championship is
six straight wins, so the natural suspect is fatigue.

B teams evolved higher aggression (which amplifies the fatigue cost) and spent
attribute budget on risk capacity rather than stamina. This measures whether that
combination makes them wilt as a bracket run gets deeper.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from incentive_sim.config import load_run_config
from incentive_sim.match import simulate_games
from incentive_sim.population import Population

GAMES_PER_ROUND_PER_REPLICATE = 25_000
ROUND_NAMES = ["Fresh\n(R64)", "R32", "Sweet 16", "Elite 8", "Final 4", "Final"]

A_COLOUR, B_COLOUR = "#2a78d6", "#eb6834"
SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"


def main() -> int:
    run_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "results/threshold10")
    cfg = load_run_config(run_dir)
    data = np.load(run_dir / "final_populations.npz")
    threshold = {lg.name: lg.win_threshold for lg in cfg.leagues}

    pops = {
        name: [
            Population(data[f"{name}_attributes"][i], data[f"{name}_strategy"][i])
            for i in range(data[f"{name}_attributes"].shape[0])
        ]
        for name in ("A", "B")
    }
    n_replicates = len(pops["A"])
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(31337)))

    win_rate, mean_margin = [], []
    for played in range(len(ROUND_NAMES)):
        margins = []
        for r in range(n_replicates):
            merged = Population(
                np.concatenate([pops["A"][r].attributes, pops["B"][r].attributes]),
                np.concatenate([pops["A"][r].strategy, pops["B"][r].strategy]),
            )
            size = pops["A"][r].n_teams
            n = GAMES_PER_ROUND_PER_REPLICATE
            left = rng.integers(0, size, size=n)
            right = size + rng.integers(0, size, size=n)
            legs = np.full(n, float(played))
            score_a, score_b = simulate_games(
                merged, left, right, legs, legs, cfg.match, rng
            )
            margins.append((score_b - score_a).astype(float))  # from B's side

        combined = np.concatenate(margins)
        win_rate.append(float((combined > 0).mean()))
        mean_margin.append(float(combined.mean()))

    print(f"B threshold = {threshold['B']}, both sides equally rested\n")
    print(f"{'bracket round':>16}{'B win rate':>13}{'B mean margin':>15}")
    print("-" * 44)
    for i, name in enumerate(ROUND_NAMES):
        print(f"{name.replace(chr(10), ' '):>16}{win_rate[i]:>13.4f}{mean_margin[i]:>15.3f}")

    decay = (win_rate[0] - win_rate[-1]) * 100
    print(f"\nB win rate falls {decay:.1f} points from fresh legs to the final")

    payload = {
        "threshold_b": threshold["B"],
        "rounds": ROUND_NAMES,
        "b_win_rate": win_rate,
        "b_mean_margin": mean_margin,
        "decay_points": decay,
        "games_per_round": GAMES_PER_ROUND_PER_REPLICATE * n_replicates,
    }
    (run_dir / "fatigue_curve.json").write_text(json.dumps(payload, indent=2))

    render(win_rate, threshold["B"], payload["games_per_round"])
    print(f"wrote {run_dir / 'fatigue_curve.json'} and figures/fatigue_curve.png")
    return 0


def render(win_rate: list[float], threshold_b: int, games: int) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    })
    fig, ax = plt.subplots(figsize=(10.0, 6.4), dpi=200)
    fig.subplots_adjust(left=0.10, right=0.90, top=0.70, bottom=0.16)

    x = np.arange(len(win_rate))
    y = np.array(win_rate) * 100

    ax.axhline(50, color=AXIS, linewidth=1.2, linestyle=(0, (4, 4)), zorder=1)
    ax.annotate("even", xy=(-0.35, 50.25), fontsize=9.5, color=INK_3, va="bottom")

    ax.fill_between(x, y, 50, color=A_COLOUR, alpha=0.14, linewidth=0, zorder=2)
    ax.plot(x, y, color=B_COLOUR, linewidth=2.4, zorder=3)
    ax.plot(x, y, "o", color=B_COLOUR, markersize=7, markeredgecolor=SURFACE,
            markeredgewidth=1.6, zorder=4)

    for i, value in enumerate(y):
        ax.annotate(f"{value:.1f}%", xy=(i, value), xytext=(0, -18),
                    textcoords="offset points", ha="center", fontsize=10.5,
                    color=INK, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(ROUND_NAMES, fontsize=10)
    ax.set_xlim(-0.45, len(x) - 0.55)
    ax.set_ylim(min(y) - 2.2, 52)
    ax.set_xlabel("How deep into the tournament", fontsize=11, color=INK_2)
    ax.set_ylabel("B-bred team's win rate vs an A-bred team", fontsize=11, color=INK_2)

    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_3, labelsize=10, length=0)

    fig.text(0.10, 0.965, "The volatile league runs out of gas.",
             fontsize=17, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.10, 0.885,
             f"League B (only a win by {threshold_b}+ counts) evolved high aggression and spent its\n"
             "attribute budget on risk capacity instead of stamina. Aggression amplifies fatigue.\n"
             "Both sides equally rested at every point — the gap is what a deep run costs B.",
             fontsize=11.5, color=INK_2, ha="left", va="top", linespacing=1.6)

    fig.text(0.10, 0.025,
             f"{games:,} simulated games per round. This is why B wins its share of single games "
             "and almost no championships.",
             fontsize=8.5, color=INK_3, ha="left", va="bottom")

    Path("figures").mkdir(exist_ok=True)
    fig.savefig("figures/fatigue_curve.png", facecolor=SURFACE)


if __name__ == "__main__":
    raise SystemExit(main())
