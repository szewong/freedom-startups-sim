"""How does the result depend on the price of volatility? (PLAN.md H3)

The headline claim — a higher bar makes populations buy variance rather than
skill — is only interesting if it survives making variance expensive. In this
engine the price is `overreach_penalty` (kappa): aggression beyond a team's risk
capacity costs efficiency quadratically. At kappa = 0 volatility is free at any
level; at high kappa it is punishing.

Sweeping kappa turns the main threat to validity into a result. The prediction is
that as volatility gets expensive the aggression gap shrinks and the skill gap
closes — and if the skill gap ever turns *positive*, that is the regime where a
high bar genuinely does make competitors better.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from incentive_sim.config import LeagueConfig, MatchConfig, RunConfig
from incentive_sim.season import run_replicate

KAPPAS = [0.0, 0.45, 0.9, 1.8, 3.6]
SEASONS = 600
REPLICATES = 12
TAIL = 30

TRACKED = ("strat_aggression", "attr_offense", "attr_defense", "margin_sd",
           "attr_risk_capacity")

A_COLOUR, B_COLOUR = "#2a78d6", "#eb6834"
SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"


def paired_gap(kappa: float) -> dict[str, tuple[float, float]]:
    """Mean B-A difference per metric, with a 95% CI, at this price of volatility."""
    cfg = RunConfig(
        name=f"kappa_{kappa}",
        seasons=SEASONS,
        replicates=REPLICATES,
        leagues=(LeagueConfig("A", 1), LeagueConfig("B", 10)),
        match=MatchConfig(overreach_penalty=kappa),
    )

    per_league: dict[str, list[dict[str, float]]] = {"A": [], "B": []}
    for replicate in range(REPLICATES):
        for history in run_replicate(cfg, replicate):
            tail = history.rows[-TAIL:]
            per_league[history.league].append(
                {key: float(np.mean([row[key] for row in tail])) for key in TRACKED}
            )

    out = {}
    for key in TRACKED:
        a = np.array([r[key] for r in per_league["A"]])
        b = np.array([r[key] for r in per_league["B"]])
        delta = b - a
        se = delta.std(ddof=1) / np.sqrt(delta.size)
        out[key] = (float(delta.mean()), float(1.96 * se))
    return out


def main() -> int:
    out_json = Path("results/cost_sweep/cost_sweep.json")
    if "--render-only" in sys.argv and out_json.exists():
        saved = json.loads(out_json.read_text())
        results = {
            float(k): {m: tuple(v) for m, v in g.items()}
            for k, g in saved["gaps"].items()
        }
        render(results)
        print("re-rendered figures/cost_sweep.png from saved results")
        return 0

    print(f"cost sweep: kappa in {KAPPAS}, {SEASONS} seasons x {REPLICATES} replicates\n")
    start = time.perf_counter()

    results = {}
    for kappa in KAPPAS:
        results[kappa] = paired_gap(kappa)
        gaps = results[kappa]
        print(
            f"kappa {kappa:<5} aggression {gaps['strat_aggression'][0]:+.4f}"
            f" ±{gaps['strat_aggression'][1]:.4f}   "
            f"offense {gaps['attr_offense'][0]:+.5f} ±{gaps['attr_offense'][1]:.5f}   "
            f"margin sd {gaps['margin_sd'][0]:+.3f}   "
            f"({time.perf_counter() - start:.0f}s)"
        )

    out_dir = Path("results/cost_sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    payload = {
        "kappas": KAPPAS,
        "seasons": SEASONS,
        "replicates": REPLICATES,
        "gaps": {str(k): {m: list(v) for m, v in g.items()} for k, g in results.items()},
    }
    (out_dir / "cost_sweep.json").write_text(json.dumps(payload, indent=2))

    render(results)
    print(f"\nwrote {out_dir / 'cost_sweep.json'} and figures/cost_sweep.png")
    return 0


def render(results: dict) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    })
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 8.4), dpi=200, sharex=True)
    fig.subplots_adjust(left=0.13, right=0.95, top=0.70, bottom=0.09, hspace=0.30)

    x = np.arange(len(KAPPAS))

    panels = [
        ("strat_aggression", "Aggression gap  (B − A)", B_COLOUR,
         "Volatility League B bought"),
        ("attr_offense", "Offensive skill gap  (B − A)", A_COLOUR,
         "Skill League B gave up"),
    ]

    for ax, (metric, ylabel, colour, title) in zip(axes, panels):
        means = np.array([results[k][metric][0] for k in KAPPAS])
        cis = np.array([results[k][metric][1] for k in KAPPAS])

        ax.axhline(0, color=INK, linewidth=1.2, zorder=3)
        ax.fill_between(x, means - cis, means + cis, color=colour, alpha=0.18,
                        linewidth=0, zorder=2)
        ax.plot(x, means, color=colour, linewidth=2.4, zorder=4)
        ax.plot(x, means, "o", color=colour, markersize=6, markeredgecolor=SURFACE,
                markeredgewidth=1.5, zorder=5)

        ax.set_ylabel(ylabel, fontsize=10.5, color=INK_2)
        ax.set_title(title, fontsize=12, color=INK, loc="left", pad=8, fontweight="bold")
        ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
        ax.set_axisbelow(True)
        for side in ("top", "right"):
            ax.spines[side].set_visible(False)
        for side in ("left", "bottom"):
            ax.spines[side].set_color(AXIS)
        ax.tick_params(colors=INK_3, labelsize=10, length=0)

    axes[-1].set_xticks(x)
    axes[-1].set_xticklabels([f"{k:g}" for k in KAPPAS])
    axes[-1].set_xlabel("Price of volatility  (κ — cost of aggression beyond risk capacity)",
                        fontsize=11, color=INK_2)

    fig.text(0.13, 0.965, "Does the result survive making volatility expensive?",
             fontsize=16, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.13, 0.905,
             "League B needs to win by 10+. When volatility is cheap it buys volatility and gives up\n"
             "skill. The question is what happens when volatility stops being cheap — the one\n"
             "parameter that could reverse the finding.",
             fontsize=11, color=INK_2, ha="left", va="top", linespacing=1.6)

    Path("figures").mkdir(exist_ok=True)
    fig.savefig("figures/cost_sweep.png", facecolor=SURFACE)


if __name__ == "__main__":
    raise SystemExit(main())
