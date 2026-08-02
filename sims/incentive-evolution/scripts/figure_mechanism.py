"""Figure: the incentive mechanism, measured in the match engine alone.

This is a Phase 1 artefact, not the headline result. No team learns anything
here and no population evolves — a single moderate favourite has its aggression
dialled up by hand, and we measure what that does to each league's reward.

Renders figures/mechanism.png.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from incentive_sim.config import ATTR_IX, N_ATTRIBUTES, N_STRATEGY, STRAT_IX, MatchConfig
from incentive_sim.match import simulate_games
from incentive_sim.population import Population

N_GAMES = 400_000
AGGRESSION = np.linspace(0.05, 0.90, 13)
CAPACITY = 0.95  # variance is free in this range, isolating the pure effect
FAVOURITE_OFFENSE = 0.585  # tuned for an expected margin between the two thresholds

# dataviz reference palette, light surface. Validated: normal-vision ΔE 33.6,
# worst CVD ΔE 24.7 (protan) — both clear of the floors.
SERIES = {1: "#2a78d6", 5: "#eb6834"}
SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
INK_MUTED = "#898781"
GRID = "#e1e0d9"
AXIS = "#c3c2b7"


def build_population(aggression: float) -> Population:
    """A favourite at `aggression` versus a passive, identical-skill opponent."""
    attributes = np.full((2, N_ATTRIBUTES), 0.5)
    strategy = np.full((2, N_STRATEGY), 0.5)

    attributes[:, ATTR_IX["risk_capacity"]] = CAPACITY
    attributes[0, ATTR_IX["offense"]] = FAVOURITE_OFFENSE
    strategy[0, STRAT_IX["aggression"]] = aggression
    strategy[1, STRAT_IX["aggression"]] = 0.05

    return Population(attributes, strategy)


def measure() -> tuple[np.ndarray, dict[int, np.ndarray], np.ndarray]:
    rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence(4242)))
    idx_a, idx_b = np.zeros(N_GAMES, int), np.ones(N_GAMES, int)
    fresh = np.zeros(N_GAMES)

    rewards = {t: [] for t in SERIES}
    mean_margin = []

    for aggression in AGGRESSION:
        pop = build_population(aggression)
        score_a, score_b = simulate_games(
            pop, idx_a, idx_b, fresh, fresh, MatchConfig(), rng
        )
        margin = score_a - score_b
        mean_margin.append(margin.mean())
        for threshold in SERIES:
            rewards[threshold].append((margin >= threshold).mean())

    return (
        AGGRESSION,
        {t: np.asarray(v) for t, v in rewards.items()},
        np.asarray(mean_margin),
    )


def render(x, rewards, mean_margin) -> Path:
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["DejaVu Sans"],
            "figure.facecolor": SURFACE,
            "axes.facecolor": SURFACE,
        }
    )

    fig, ax = plt.subplots(figsize=(10.0, 6.5), dpi=200)
    fig.subplots_adjust(left=0.10, right=0.80, top=0.74, bottom=0.14)

    labels = {
        1: "League A  ·  a win is a win",
        5: "League B  ·  only win by 5+ counts",
    }

    for threshold, color in SERIES.items():
        y = rewards[threshold] * 100
        ax.plot(x, y, color=color, linewidth=2.0, zorder=3, label=labels[threshold])
        # Markers are the measured points, ringed in the surface colour so
        # overlapping marks stay separable.
        ax.plot(
            x, y, "o", color=color, markersize=5,
            markeredgecolor=SURFACE, markeredgewidth=1.4, zorder=4,
        )
        ax.annotate(
            f"{y[-1]:.1f}%",
            xy=(x[-1], y[-1]),
            xytext=(10, 0),
            textcoords="offset points",
            va="center",
            fontsize=11,
            fontweight="bold",
            color=INK,
        )
        delta = (y[-1] - y[0])
        ax.annotate(
            f"{delta:+.1f} pts",
            xy=(x[-1], y[-1]),
            xytext=(10, -15),
            textcoords="offset points",
            va="center",
            fontsize=10,
            color=INK_SECONDARY,
        )

    ax.set_xlim(0.0, 0.95)
    ax.set_ylim(38.0, 60.0)
    ax.set_yticks([40, 45, 50, 55, 60])
    ax.set_yticklabels([f"{v}%" for v in [40, 45, 50, 55, 60]])
    ax.set_xticks([0.05, 0.25, 0.45, 0.65, 0.90])

    ax.set_xlabel("Team's aggression  (variance bought)", fontsize=11, color=INK_SECONDARY)
    ax.set_ylabel("Share of games that count as a success", fontsize=11, color=INK_SECONDARY)

    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
        ax.spines[side].set_linewidth(1.0)
    ax.tick_params(colors=INK_MUTED, labelsize=10, length=0)

    fig.text(
        0.10, 0.965,
        "Same team. Same games. Opposite incentives.",
        fontsize=17, fontweight="bold", color=INK, ha="left", va="top",
    )
    fig.text(
        0.10, 0.885,
        "One moderate favourite dials up its volatility. Its expected margin never moves\n"
        f"(held at {mean_margin.mean():+.1f} points) — but the two leagues score it in opposite directions.",
        fontsize=11.5, color=INK_SECONDARY, ha="left", va="top", linespacing=1.6,
    )

    # Legend sits in the empty band between the two lines — identity is never
    # carried by colour alone, and it costs no vertical space.
    legend = ax.legend(
        loc="center left", frameon=False, fontsize=10.5,
        handlelength=1.8, labelspacing=0.8,
    )
    for text in legend.get_texts():
        text.set_color(INK_SECONDARY)

    fig.text(
        0.10, 0.025,
        f"Match engine only — no learning, no evolution. {N_GAMES:,} simulated games per point; "
        "±0.15pp Monte Carlo error.",
        fontsize=8.5, color=INK_MUTED, ha="left", va="bottom",
    )

    out = Path("figures/mechanism.png")
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, facecolor=SURFACE)
    return out


def main() -> None:
    x, rewards, mean_margin = measure()
    path = render(x, rewards, mean_margin)

    print(f"mean margin: {mean_margin.mean():+.2f} (sd across sweep {mean_margin.std():.2f})")
    for threshold, y in rewards.items():
        print(f"threshold {threshold}: {y[0] * 100:.2f}% -> {y[-1] * 100:.2f}%")
    print(f"wrote {path}")


if __name__ == "__main__":
    main()
