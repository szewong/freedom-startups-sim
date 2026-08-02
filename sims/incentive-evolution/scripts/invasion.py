"""Run the invasion experiment and chart it.

    python scripts/invasion.py results/baseline
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np

from incentive_sim.config import load_run_config
from incentive_sim.invasion import build_rules, run_invasion
from incentive_sim.population import Population

SEASONS = 300
# Lineages usually fixate (one ancestry takes the whole league), so a single run
# is close to a coin flip. The quantity with a meaningful confidence interval is
# the *fixation probability*, which needs many independent trials.
TRIALS_PER_REPLICATE = 5

# The two fixed bars keep the league colours, because those rules *are* League A's
# and League B's worlds. The shifting rule takes the next validated slot.
LEAGUE_COLOURS = ("#2a78d6", "#eb6834")
SHIFTING_COLOUR = "#4a3aa7"


def rule_colours(rules: dict) -> dict[str, str]:
    fixed = [k for k in rules if k != "shifting"]
    colours = dict(zip(fixed, LEAGUE_COLOURS))
    colours["shifting"] = SHIFTING_COLOUR
    return colours
SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"


def load_populations(run_dir: Path) -> dict[str, list[Population]]:
    data = np.load(run_dir / "final_populations.npz")
    return {
        name: [
            Population(data[f"{name}_attributes"][i], data[f"{name}_strategy"][i])
            for i in range(data[f"{name}_attributes"].shape[0])
        ]
        for name in ("A", "B")
    }


def main() -> int:
    run_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "results/baseline")
    cfg = load_run_config(run_dir)
    pops = load_populations(run_dir)
    n_replicates = len(pops["A"])

    rules, labels = build_rules(cfg)
    colours = rule_colours(rules)

    print(f"invasion: 32 A-bred + 32 B-bred, {SEASONS} seasons, "
          f"{n_replicates} replicates x {len(rules)} rules\n")

    results: dict[str, np.ndarray] = {}
    fixation: dict[str, dict[str, float]] = {}

    for rule_index, rule in enumerate(rules):
        runs = []
        for r in range(n_replicates):
            for trial in range(TRIALS_PER_REPLICATE):
                rng = np.random.Generator(np.random.PCG64(
                    np.random.SeedSequence([424242, r, trial, rule_index])
                ))
                runs.append(
                    run_invasion(pops["A"][r], pops["B"][r], rule, SEASONS, cfg, rng)
                )
        results[rule] = np.array([run.share_b for run in runs])

        final = results[rule][:, -1]
        b_fixed = int((final == 1.0).sum())
        a_fixed = int((final == 0.0).sum())
        decided = b_fixed + a_fixed
        # Under neutral drift from a 50/50 start, B fixates half the time. Any
        # departure from 0.5 is selection, not luck.
        p_b = b_fixed / decided if decided else float("nan")
        se = np.sqrt(p_b * (1 - p_b) / decided) if decided else float("nan")
        verdict = (
            "dead heat" if abs(p_b - 0.5) < 1.96 * se
            else f"{'B-bred' if p_b > 0.5 else 'A-bred'} take over"
        )
        fixation[rule] = {
            "b_fixed": b_fixed, "a_fixed": a_fixed, "trials": len(runs),
            "p_b_fixation": p_b, "ci": 1.96 * se,
        }
        print(f"{labels[rule]:<52} B takes over {p_b:6.1%} ± {1.96 * se:.1%} "
              f"of decided runs ({decided}/{len(runs)})   {verdict}")

    payload = {
        rule: {
            "label": labels[rule],
            "mean_share_b": results[rule].mean(axis=0).round(5).tolist(),
            "final_share_b": float(results[rule][:, -1].mean()),
            "final_share_b_sd": float(results[rule][:, -1].std(ddof=1)),
            "trials": int(results[rule].shape[0]),
            **fixation[rule],
        }
        for rule in rules
    }
    (run_dir / "invasion.json").write_text(json.dumps(payload, indent=2))

    render(results, labels, colours)
    print(f"\nwrote {run_dir / 'invasion.json'} and figures/invasion.png")
    return 0


def render(results, labels: dict[str, str], colours: dict[str, str]) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    })
    fig, ax = plt.subplots(figsize=(10.0, 6.6), dpi=200)
    fig.subplots_adjust(left=0.10, right=0.72, top=0.72, bottom=0.14)

    seasons = np.arange(next(iter(results.values())).shape[1])

    ax.axhline(50, color=AXIS, linewidth=1.2, linestyle=(0, (4, 4)), zorder=1)
    ax.annotate("even split", xy=(seasons[-1] * 0.02, 51), fontsize=9.5, color=INK_3)

    for rule, colour in colours.items():
        runs = results[rule] * 100
        mean = runs.mean(axis=0)
        se = runs.std(axis=0, ddof=1) / np.sqrt(runs.shape[0])
        ax.fill_between(seasons, mean - 1.96 * se, mean + 1.96 * se,
                        color=colour, alpha=0.14, linewidth=0, zorder=2)
        ax.plot(seasons, mean, color=colour, linewidth=2.2, zorder=3,
                label=labels[rule])
        ax.annotate(f"{mean[-1]:.0f}%", xy=(seasons[-1], mean[-1]),
                    xytext=(9, 0), textcoords="offset points", va="center",
                    fontsize=11.5, fontweight="bold", color=colour)

    ax.set_xlim(0, seasons[-1] * 1.02)
    ax.set_ylim(0, 100)
    ax.set_yticks([0, 25, 50, 75, 100])
    ax.set_yticklabels([f"{v}%" for v in [0, 25, 50, 75, 100]])
    ax.set_xlabel("Seasons in the combined league", fontsize=11, color=INK_2)
    ax.set_ylabel("Share of teams descended from League B", fontsize=11, color=INK_2)

    ax.grid(axis="y", color=GRID, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(AXIS)
    ax.tick_params(colors=INK_3, labelsize=10, length=0)

    fig.text(0.10, 0.965, "Whose descendants take over?",
             fontsize=17, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.10, 0.885,
             "Thirty-two teams from each upbringing, thrown into one league and left to compete.\n"
             "Lineage is traced through reproduction, so this is ancestry, not this season's form.\n"
             "The answer depends on the rule — which is the point.",
             fontsize=11.5, color=INK_2, ha="left", va="top", linespacing=1.6)

    legend = ax.legend(loc="upper left", bbox_to_anchor=(0.0, -0.13), frameon=False,
                       fontsize=10, handlelength=1.8, labelspacing=0.6)
    for text in legend.get_texts():
        text.set_color(INK_2)

    Path("figures").mkdir(exist_ok=True)
    fig.savefig("figures/invasion.png", facecolor=SURFACE, bbox_inches="tight")


if __name__ == "__main__":
    raise SystemExit(main())
