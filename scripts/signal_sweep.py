"""When does a population optimise the proxy instead of the thing?

The claim under test: where *looking* successful is cheaper than *being*
successful, populations evolve to look successful and get worse at the activity.

A model built to confirm that would be worthless — make the proxy cheap and
rewarded, and of course you get proxy-optimisers. So this sweeps the two
governing parameters and asks where the boundary actually falls:

  signal_cost (c)    how much real performance a unit of signalling costs
  signal_weight (w)  how much of the score the world takes from the proxy

If proxy-optimisation happens everywhere, the model is rigged and we should say
so. If it happens in a bounded region, that region *is* the claim, and it is
specific enough to argue about.

Both leagues use threshold 1, so this isolates the proxy mechanism from the
variance mechanism studied earlier.
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

COSTS = [0.05, 0.10, 0.20, 0.40, 0.70]
WEIGHTS = [0.10, 0.20, 0.30, 0.50]
SEASONS = 400
REPLICATES = 8
TAIL = 30

SURFACE = "#fcfcfb"
INK, INK_2, INK_3 = "#0b0b0b", "#52514e", "#898781"
GRID, AXIS = "#e1e0d9", "#c3c2b7"


def one_cell(cost: float, weight: float) -> dict[str, float]:
    """Run a results league and a proxy league side by side at these settings."""
    cfg = RunConfig(
        name=f"c{cost}_w{weight}",
        seasons=SEASONS,
        replicates=REPLICATES,
        leagues=(
            LeagueConfig("A", 1, signal_weight=0.0),      # results only
            LeagueConfig("B", 1, signal_weight=weight),   # results + purchasable proxy
        ),
        match=MatchConfig(signal_cost=cost),
    )

    per_league: dict[str, list[dict[str, float]]] = {"A": [], "B": []}
    for replicate in range(REPLICATES):
        for history in run_replicate(cfg, replicate):
            tail = history.rows[-TAIL:]
            per_league[history.league].append({
                "signal_effort": float(np.mean([r["signal_effort"] for r in tail])),
                "true_strength": float(np.mean([r["true_strength"] for r in tail])),
                "reward_rate": float(np.mean([r["reward_rate"] for r in tail])),
            })

    a = {k: np.array([r[k] for r in per_league["A"]]) for k in per_league["A"][0]}
    b = {k: np.array([r[k] for r in per_league["B"]]) for k in per_league["B"][0]}

    strength_delta = b["true_strength"] - a["true_strength"]
    se = strength_delta.std(ddof=1) / np.sqrt(strength_delta.size)

    return {
        "signal_effort_b": float(b["signal_effort"].mean()),
        "signal_effort_a": float(a["signal_effort"].mean()),
        # The number that matters: real capability lost, as a percentage.
        "strength_loss_pct": float(
            100.0 * (b["true_strength"].mean() / a["true_strength"].mean() - 1.0)
        ),
        "strength_delta": float(strength_delta.mean()),
        "strength_delta_ci": float(1.96 * se),
        "significant": bool(abs(strength_delta.mean()) > 1.96 * se),
        # What the proxy league's own scoreboard reports about itself.
        "reward_rate_b": float(b["reward_rate"].mean()),
        "reward_rate_a": float(a["reward_rate"].mean()),
    }


def main() -> int:
    print(f"signal sweep: {len(COSTS)}x{len(WEIGHTS)} cells, "
          f"{SEASONS} seasons x {REPLICATES} replicates\n")
    print(f"{'cost':>6}{'weight':>8}{'signal effort':>15}{'real capability':>17}{'':>4}")
    print("-" * 54)

    start = time.perf_counter()
    grid: dict[str, dict[str, float]] = {}
    for cost in COSTS:
        for weight in WEIGHTS:
            cell = one_cell(cost, weight)
            grid[f"{cost}|{weight}"] = cell
            flag = "" if cell["significant"] else "  (ns)"
            print(f"{cost:>6.2f}{weight:>8.2f}{cell['signal_effort_b']:>15.3f}"
                  f"{cell['strength_loss_pct']:>16.2f}%{flag}")
        print(f"   ... {time.perf_counter() - start:.0f}s")

    out_dir = Path("results/signal_sweep")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "signal_sweep.json").write_text(json.dumps({
        "costs": COSTS, "weights": WEIGHTS,
        "seasons": SEASONS, "replicates": REPLICATES, "grid": grid,
    }, indent=2))

    render(grid)
    print(f"\nwrote {out_dir / 'signal_sweep.json'} and figures/signal_sweep.png")
    return 0


def render(grid: dict) -> None:
    mpl.rcParams.update({
        "font.family": "sans-serif", "font.sans-serif": ["DejaVu Sans"],
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
    })
    fig, axes = plt.subplots(1, 2, figsize=(12.5, 5.8), dpi=200)
    fig.subplots_adjust(left=0.09, right=0.97, top=0.68, bottom=0.14, wspace=0.28)

    effort = np.array([[grid[f"{c}|{w}"]["signal_effort_b"] for w in WEIGHTS] for c in COSTS])
    loss = np.array([[grid[f"{c}|{w}"]["strength_loss_pct"] for w in WEIGHTS] for c in COSTS])
    sig = np.array([[grid[f"{c}|{w}"]["significant"] for w in WEIGHTS] for c in COSTS])

    panels = [
        (axes[0], effort, "Effort spent on the proxy", "Blues", "{:.2f}", None),
        (axes[1], loss, "Real capability lost (%)", "Oranges_r", "{:.1f}%", sig),
    ]

    for ax, data, title, cmap, fmt, mask in panels:
        im = ax.imshow(data, cmap=cmap, aspect="auto", origin="lower")
        ax.set_xticks(range(len(WEIGHTS)))
        ax.set_xticklabels([f"{w:g}" for w in WEIGHTS])
        ax.set_yticks(range(len(COSTS)))
        ax.set_yticklabels([f"{c:g}" for c in COSTS])
        ax.set_xlabel("How much the world scores the proxy  (w)", fontsize=10.5, color=INK_2)
        ax.set_ylabel("Price of the proxy  (c)", fontsize=10.5, color=INK_2)
        ax.set_title(title, fontsize=12.5, color=INK, loc="left", pad=10, fontweight="bold")

        for i in range(data.shape[0]):
            for j in range(data.shape[1]):
                faded = mask is not None and not mask[i, j]
                ax.text(j, i, fmt.format(data[i, j]) + ("" if not faded else "\nns"),
                        ha="center", va="center", fontsize=9.5,
                        color=INK_3 if faded else INK,
                        fontweight="normal" if faded else "bold")

        for side in ax.spines.values():
            side.set_visible(False)
        ax.tick_params(colors=INK_3, labelsize=10, length=0)
        fig.colorbar(im, ax=ax, fraction=0.045, pad=0.03).outline.set_visible(False)

    fig.text(0.09, 0.965, "Where does chasing the proxy actually take over?",
             fontsize=16, fontweight="bold", color=INK, ha="left", va="top")
    fig.text(0.09, 0.885,
             "Two leagues, identical except that League B's score is part results and part a proxy it can\n"
             "buy with effort diverted from the game. Sweeping the proxy's price and its weight maps the\n"
             "region where the population abandons the activity for the appearance — and where it does not.",
             fontsize=11, color=INK_2, ha="left", va="top", linespacing=1.6)

    Path("figures").mkdir(exist_ok=True)
    fig.savefig("figures/signal_sweep.png", facecolor=SURFACE)


if __name__ == "__main__":
    raise SystemExit(main())
