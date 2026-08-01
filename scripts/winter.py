"""The regime-change test: what happens when the world stops paying for the proxy.

This is the strongest available check on the claim, because it makes a prediction
about something a proxy-optimising population's own scoreboard never reported.

Two leagues evolve side by side for a boom period. League A is scored purely on
results. League B's score is part results, part a proxy it can buy with effort
diverted from the game. Then the rule changes: the proxy stops counting for
everyone, and both leagues are scored identically from that point on.

Three things are worth measuring, and only the third is trivially implied by the
setup:

1. **During the boom, did League B's own scoreboard show any warning?** If its
   reward rate looks fine or better while its real capability erodes, that is the
   Goodhart signature — and it is not built in, since the proxy bonus has to
   actually outweigh the results it costs.
2. **How far does it fall when the rule changes?**
3. **How long does it take to recover?**
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from incentive_sim.config import (
    LeagueConfig,
    MatchConfig,
    RunConfig,
    league_seed,
    population_seed,
    rng as make_rng,
)
from incentive_sim.population import initial_population
from incentive_sim.season import run_league

BOOM_SEASONS = 400
WINTER_SEASONS = 250
REPLICATES = 10
SIGNAL_WEIGHT = 0.30
SIGNAL_COST = 0.10  # the regime the sweep flags as dangerous: a cheap proxy

A_COLOUR, B_COLOUR = "#2a78d6", "#eb6834"
SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"


def run_one(replicate: int, weight: float) -> dict[str, list[float]]:
    """Boom then winter for a single league, returning its per-season history."""
    boom_cfg = RunConfig(
        name="boom", seasons=BOOM_SEASONS, replicates=1,
        leagues=(LeagueConfig("X", 1, signal_weight=weight),),
        match=MatchConfig(signal_cost=SIGNAL_COST),
    )
    winter_cfg = RunConfig(
        name="winter", seasons=WINTER_SEASONS, replicates=1,
        leagues=(LeagueConfig("X", 1, signal_weight=0.0),),
        match=MatchConfig(signal_cost=SIGNAL_COST),
    )

    pop = initial_population(
        boom_cfg.tournament.n_teams,
        make_rng(population_seed(boom_cfg, replicate)),
        boom_cfg.evolution,
    )
    rng = make_rng(league_seed(boom_cfg, replicate, 0))

    boom = run_league(boom_cfg, boom_cfg.leagues[0], pop, rng)
    # The population carries over; only the rule changes. A fresh learner is
    # created for the second phase, which is a discontinuity we accept —
    # everyone re-plans when the rules change.
    winter = run_league(winter_cfg, winter_cfg.leagues[0], boom.final_population, rng)

    rows = boom.rows + winter.rows
    return {
        "reward_rate": [r["reward_rate"] for r in rows],
        "true_strength": [r["true_strength"] for r in rows],
        "signal_effort": [r["signal_effort"] for r in rows],
    }


def main() -> int:
    saved = Path("results/winter/winter.json")
    if "--render-only" in sys.argv and saved.exists():
        blob = json.loads(saved.read_text())
        render({
            label: {k: np.array([v]) for k, v in d.items()}
            for label, d in blob["series"].items()
        })
        print("re-rendered figures/winter.png from saved results")
        return 0

    print(f"winter test: {BOOM_SEASONS} boom + {WINTER_SEASONS} winter seasons, "
          f"{REPLICATES} replicates")
    print(f"proxy weight {SIGNAL_WEIGHT}, proxy cost {SIGNAL_COST}\n")

    start = time.perf_counter()
    series: dict[str, dict[str, np.ndarray]] = {}
    for label, weight in (("A", 0.0), ("B", SIGNAL_WEIGHT)):
        runs = [run_one(r, weight) for r in range(REPLICATES)]
        series[label] = {
            key: np.array([run[key] for run in runs]) for key in runs[0]
        }
        print(f"  league {label} done ({time.perf_counter() - start:.0f}s)")

    boom_slice = slice(BOOM_SEASONS - 30, BOOM_SEASONS)
    winter_end = slice(-30, None)

    def mean(label, key, sl):
        return float(series[label][key][:, sl].mean())

    report = {
        "boom": {
            "reward_a": mean("A", "reward_rate", boom_slice),
            "reward_b": mean("B", "reward_rate", boom_slice),
            "strength_a": mean("A", "true_strength", boom_slice),
            "strength_b": mean("B", "true_strength", boom_slice),
            "signal_effort_b": mean("B", "signal_effort", boom_slice),
        },
        "winter_end": {
            "reward_a": mean("A", "reward_rate", winter_end),
            "reward_b": mean("B", "reward_rate", winter_end),
            "strength_a": mean("A", "true_strength", winter_end),
            "strength_b": mean("B", "true_strength", winter_end),
        },
    }

    boom, end = report["boom"], report["winter_end"]
    print(f"\n{'':<34}{'League A':>12}{'League B':>12}")
    print("-" * 58)
    print(f"{'BOOM  scoreboard says':<34}{boom['reward_a']:>12.4f}{boom['reward_b']:>12.4f}")
    print(f"{'BOOM  actually worth':<34}{boom['strength_a']:>12.4f}{boom['strength_b']:>12.4f}")
    print(f"{'BOOM  effort on the proxy':<34}{0.0:>12.4f}{boom['signal_effort_b']:>12.4f}")
    print(f"{'WINTER-END scoreboard says':<34}{end['reward_a']:>12.4f}{end['reward_b']:>12.4f}")
    print(f"{'WINTER-END actually worth':<34}{end['strength_a']:>12.4f}{end['strength_b']:>12.4f}")

    # Did the boom-time scoreboard warn anyone?
    scoreboard_gap = boom["reward_b"] - boom["reward_a"]
    reality_gap = 100.0 * (boom["strength_b"] / boom["strength_a"] - 1.0)
    print(f"\nDuring the boom League B's scoreboard read {scoreboard_gap:+.4f} vs League A,")
    print(f"while it was actually {reality_gap:+.2f}% weaker.")
    report["boom_scoreboard_gap"] = scoreboard_gap
    report["boom_reality_gap_pct"] = reality_gap

    # How long to recover after the rule changes?
    b_strength = series["B"]["true_strength"].mean(axis=0)
    a_strength = series["A"]["true_strength"].mean(axis=0)
    recovered = np.flatnonzero(
        (np.arange(len(b_strength)) >= BOOM_SEASONS) & (b_strength >= a_strength * 0.999)
    )
    seasons_to_recover = int(recovered[0] - BOOM_SEASONS) if recovered.size else None
    report["seasons_to_recover"] = seasons_to_recover
    print("Seasons to recover after the rule changed: "
          f"{seasons_to_recover if seasons_to_recover is not None else 'not within ' + str(WINTER_SEASONS)}")

    out_dir = Path("results/winter")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "winter.json").write_text(json.dumps({
        "config": {
            "boom_seasons": BOOM_SEASONS, "winter_seasons": WINTER_SEASONS,
            "replicates": REPLICATES, "signal_weight": SIGNAL_WEIGHT,
            "signal_cost": SIGNAL_COST,
        },
        "report": report,
        "series": {
            label: {key: arr.mean(axis=0).round(5).tolist() for key, arr in d.items()}
            for label, d in series.items()
        },
    }, indent=2))

    render(series)
    print(f"\nwrote {out_dir / 'winter.json'} and figures/winter.png")
    return 0


def render(series: dict) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    })
    fig, axes = plt.subplots(2, 1, figsize=(10.0, 8.6), dpi=200, sharex=True)
    fig.subplots_adjust(left=0.11, right=0.95, top=0.74, bottom=0.09, hspace=0.26)

    panels = [
        ("reward_rate", "What the scoreboard says", "League's own score"),
        ("true_strength", "What the teams are actually worth", "Real scoring ability"),
    ]

    for ax, (key, title, ylabel) in zip(axes, panels):
        seasons = np.arange(series["A"][key].shape[1])
        for label, colour in (("A", A_COLOUR), ("B", B_COLOUR)):
            runs = series[label][key]
            mean = runs.mean(axis=0)
            if runs.shape[0] > 1:
                se = runs.std(axis=0, ddof=1) / np.sqrt(runs.shape[0])
                ax.fill_between(seasons, mean - 1.96 * se, mean + 1.96 * se,
                                color=colour, alpha=0.15, linewidth=0, zorder=2)
            ax.plot(seasons, mean, color=colour, linewidth=2.0, zorder=3,
                    label="League A — results only" if label == "A"
                    else "League B — part results, part proxy")

        ax.axvline(BOOM_SEASONS, color=INK, linewidth=1.4, linestyle=(0, (4, 3)), zorder=4)
        ax.annotate("the proxy stops counting", xy=(BOOM_SEASONS, ax.get_ylim()[1]),
                    xytext=(8, -14), textcoords="offset points",
                    fontsize=10, color=INK, va="top", fontweight="bold")

        ax.set_ylabel(ylabel, fontsize=10.5, color=INK_2)
        ax.set_title(title, fontsize=12.5, color=INK, loc="left", pad=8, fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=INK_3, labelsize=10, length=0)

    axes[-1].set_xlabel("Season", fontsize=11, color=INK_2)
    legend = axes[0].legend(loc="lower right", frameon=False, fontsize=10, handlelength=1.8)
    for text in legend.get_texts():
        text.set_color(INK_2)

    fig.text(0.11, 0.965, "The scoreboard said fine. The teams were not fine.",
             fontsize=16.5, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.11, 0.885,
             "League B's score is part results, part a proxy it can buy with effort taken from the game.\n"
             "For four hundred seasons its scoreboard climbs steadily clear of League A's, while its real\n"
             "ability stalls below. Then the proxy stops counting, and the gap comes due all at once.",
             fontsize=11, color=INK_2, ha="left", va="top", linespacing=1.6)

    Path("figures").mkdir(exist_ok=True)
    fig.savefig("figures/winter.png", facecolor=SURFACE)


if __name__ == "__main__":
    raise SystemExit(main())
