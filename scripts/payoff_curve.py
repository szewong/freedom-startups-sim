"""Is one league's product actually *better*? Measured against a common opponent.

A direct A-vs-B match cannot answer this: it is zero-sum, so the margin
distribution is symmetric and both populations clear any bar equally often by
construction. To compare two populations you need a **common third opponent**.

Reference opponent here is the evolved League A population — so both curves
answer the same question: "playing the same opposition, what does an A-bred team's
outcome distribution look like versus a B-bred team's?"

The output is a survival curve, P(margin >= k), swept across every bar k. The
point is not which curve is higher; it is that they **cross**.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from incentive_sim.config import MatchConfig, load_run_config
from incentive_sim.match import simulate_games
from incentive_sim.population import Population

GAMES_PER_REPLICATE = 120_000
BARS = np.arange(-25, 26)

SERIES = {"A": "#2a78d6", "B": "#eb6834"}
SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"


def margins_against(
    challenger: Population, reference: Population, rng: np.random.Generator, n: int
) -> np.ndarray:
    """Margins for `challenger` teams playing `reference` teams, fresh legs."""
    merged = Population(
        np.concatenate([challenger.attributes, reference.attributes]),
        np.concatenate([challenger.strategy, reference.strategy]),
    )
    size = challenger.n_teams
    left = rng.integers(0, size, size=n)
    right = size + rng.integers(0, reference.n_teams, size=n)
    fresh = np.zeros(n)

    score_l, score_r = simulate_games(merged, left, right, fresh, fresh, MatchConfig(), rng)
    return (score_l - score_r).astype(float)


def main() -> int:
    run_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "results/baseline")
    cfg = load_run_config(run_dir)
    data = np.load(run_dir / "final_populations.npz")

    pops = {
        name: [
            Population(data[f"{name}_attributes"][i], data[f"{name}_strategy"][i])
            for i in range(data[f"{name}_attributes"].shape[0])
        ]
        for name in ("A", "B")
    }
    n_replicates = len(pops["A"])

    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(20260801)))
    collected: dict[str, list[np.ndarray]] = {"A": [], "B": []}

    for r in range(n_replicates):
        reference = pops["A"][r]  # common opponent for both challengers
        for name in ("A", "B"):
            collected[name].append(
                margins_against(pops[name][r], reference, rng, GAMES_PER_REPLICATE)
            )

    margins = {name: np.concatenate(v) for name, v in collected.items()}

    # -- headline numbers ----------------------------------------------------
    def stats(m: np.ndarray) -> dict[str, float]:
        return {
            "mean_margin": float(m.mean()),
            "sd_margin": float(m.std()),
            "win": float((m >= 1).mean()),
            "win_by_5": float((m >= 5).mean()),
            "win_by_10": float((m >= 10).mean()),
            "lose_by_5": float((m <= -5).mean()),
            "lose_by_10": float((m <= -10).mean()),
        }

    summary = {name: stats(m) for name, m in margins.items()}

    print(f"vs a common opponent (evolved League A), {len(margins['A']):,} games each\n")
    labels = [
        ("mean_margin", "Expected margin", "{:+.3f}"),
        ("sd_margin", "Margin volatility", "{:.2f}"),
        ("win", "P(win)", "{:.4f}"),
        ("win_by_5", "P(win by 5+)", "{:.4f}"),
        ("win_by_10", "P(win by 10+)", "{:.4f}"),
        ("lose_by_5", "P(LOSE by 5+)", "{:.4f}"),
        ("lose_by_10", "P(LOSE by 10+)", "{:.4f}"),
    ]
    print(f"{'':<22}{'A-bred':>12}{'B-bred':>12}{'diff':>12}")
    print("-" * 58)
    for key, label, fmt in labels:
        a, b = summary["A"][key], summary["B"][key]
        print(f"{label:<22}{fmt.format(a):>12}{fmt.format(b):>12}{b - a:+12.4f}")

    # -- survival curves -----------------------------------------------------
    curves = {
        name: np.array([(m >= k).mean() for k in BARS]) for name, m in margins.items()
    }
    gap = curves["B"] - curves["A"]
    crossings = [
        int(BARS[i]) for i in range(1, len(BARS)) if gap[i - 1] <= 0 < gap[i] or gap[i - 1] >= 0 > gap[i]
    ]
    print(f"\ncurves cross at bar(s): {crossings}")

    payload = {
        "summary": summary,
        "bars": BARS.tolist(),
        "curves": {k: v.tolist() for k, v in curves.items()},
        "crossings": crossings,
        "games_per_population": len(margins["A"]),
    }
    (run_dir / "payoff_curve.json").write_text(json.dumps(payload, indent=2))

    render(curves, summary, run_dir)
    print(f"wrote {run_dir / 'payoff_curve.json'} and figures/payoff_curve.png")
    return 0


def render(curves, summary, run_dir) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    })
    fig, ax = plt.subplots(figsize=(10.0, 6.6), dpi=200)
    fig.subplots_adjust(left=0.11, right=0.94, top=0.70, bottom=0.15)

    # The two survival curves differ by ~1 point on a 0–100 scale — invisible if
    # plotted raw. The difference between them is the entire finding, so plot that.
    gap = (curves["B"] - curves["A"]) * 100

    ax.axhline(0, color=INK, linewidth=1.2, zorder=4)
    ax.fill_between(BARS, 0, gap, where=(gap >= 0), color=SERIES["B"],
                    alpha=0.22, zorder=2, linewidth=0, interpolate=True)
    ax.fill_between(BARS, 0, gap, where=(gap < 0), color=SERIES["A"],
                    alpha=0.22, zorder=2, linewidth=0, interpolate=True)
    ax.plot(BARS, gap, color=INK, linewidth=2.0, zorder=5)

    span = float(np.abs(gap).max())
    ax.set_xlim(-25, 25)
    ax.set_ylim(-span * 1.45, span * 1.45)

    ax.annotate("B-bred teams clear\nthis bar MORE often",
                xy=(14, span * 0.95), fontsize=11, color=SERIES["B"],
                ha="center", linespacing=1.45, fontweight="bold")
    ax.annotate("B-bred teams clear\nthis bar LESS often",
                xy=(-14, -span * 1.28), fontsize=11, color=SERIES["A"],
                ha="center", va="top", linespacing=1.45, fontweight="bold")

    ax.set_xlabel("Bar the team is judged against  (margin of victory, points)",
                  fontsize=11, color=INK_2)
    ax.set_ylabel("B-bred minus A-bred  (percentage points)", fontsize=11, color=INK_2)

    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_3, labelsize=10, length=0)

    fig.text(0.11, 0.965, "Neither league built a better team.",
             fontsize=17, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.11, 0.885,
             "Both populations played the same opponent. Chasing the higher bar bought League B a\n"
             "fatter right tail and an equally fat left one — at an expected margin of "
             f"{summary['B']['mean_margin']:+.2f} vs {summary['A']['mean_margin']:+.2f} points.\n"
             "Every gain at a high bar is paid for by a loss at a low one.",
             fontsize=11.5, color=INK_2, ha="left", va="top", linespacing=1.6)

    fig.text(0.11, 0.025,
             "Common opponent: the evolved League A population. A direct A-vs-B match is zero-sum "
             "and cannot answer this question.",
             fontsize=8.5, color=INK_3, ha="left", va="bottom")

    Path("figures").mkdir(exist_ok=True)
    fig.savefig("figures/payoff_curve.png", facecolor=SURFACE)


if __name__ == "__main__":
    raise SystemExit(main())
