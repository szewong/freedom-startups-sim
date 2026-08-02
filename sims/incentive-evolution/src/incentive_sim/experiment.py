"""Experiment runner: replicates, storage, and the web trace export.

    python -m incentive_sim.experiment --config configs/baseline.yaml --replicates 12
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import numpy as np

from .config import RunConfig, load_config
from .metrics import summarise, write_manifest, write_seasons
from .season import run_replicate

# Metrics the website plots. Everything else lives in the Parquet table.
WEB_SERIES = (
    "strat_aggression",
    "strat_margin_seeking",
    "strat_endgame_conservatism",
    "attr_offense",
    "attr_defense",
    "attr_risk_capacity",
    "margin_sd",
    "blowout_rate",
    "close_rate",
    "upset_rate",
    "sd_aggression",
    "reward_rate",
)

MAX_WEB_POINTS = 240


def checkpoint_seasons(seasons: int, count: int = 6) -> list[int]:
    """Checkpoints spaced so early, fast change is not compressed away."""
    if seasons <= count:
        return list(range(seasons))
    fractions = np.geomspace(1, seasons, count)
    picks = sorted({0, seasons - 1} | {int(round(f)) - 1 for f in fractions})
    return [p for p in picks if 0 <= p < seasons][:count]


def _downsample(values: list[float], limit: int = MAX_WEB_POINTS) -> list[float]:
    if len(values) <= limit:
        return [round(v, 5) for v in values]
    idx = np.linspace(0, len(values) - 1, limit).round().astype(int)
    return [round(values[i], 5) for i in idx]


def build_web_payload(
    cfg: RunConfig,
    rows: list[dict[str, Any]],
    traces: dict[str, list],
    checkpoints: list[int],
) -> dict[str, Any]:
    """Everything the site needs, in one JSON blob."""
    season_index = _downsample([float(s) for s in range(cfg.seasons)])

    series: dict[str, Any] = {}
    for league in (lg.name for lg in cfg.leagues):
        series[league] = {
            metric: {
                key: _downsample(values)
                for key, values in summarise(rows, metric, league, cfg.seasons).items()
            }
            for metric in WEB_SERIES
        }

    brackets: dict[str, Any] = {}
    for league, league_traces in traces.items():
        brackets[league] = [
            {
                "season": trace.season,
                "seeds": trace.seeds,
                "champion": trace.champion,
                "games": trace.games,
                "aggression": trace.aggression,
                "offense": trace.offense,
            }
            for trace in league_traces
        ]

    return {
        "meta": {
            "name": cfg.name,
            "seasons": cfg.seasons,
            "replicates": cfg.replicates,
            "n_teams": cfg.tournament.n_teams,
            "regular_season_games": cfg.tournament.regular_season_games,
            "config_hash": cfg.hash(),
            "leagues": [
                {"name": lg.name, "threshold": lg.win_threshold} for lg in cfg.leagues
            ],
        },
        "season_index": [int(s) for s in season_index],
        "checkpoints": checkpoints,
        "series": series,
        "brackets": brackets,
    }


def run(cfg: RunConfig, out_dir: Path, quiet: bool = False) -> dict[str, Any]:
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoints = checkpoint_seasons(cfg.seasons)

    rows: list[dict[str, Any]] = []
    # Bracket traces come from replicate 0 only -- one representative run to
    # animate. The charts average over every replicate.
    traces: dict[str, list] = {}
    # Final populations are kept so the neutral head-to-head (PLAN.md D4) can run
    # without re-simulating 600 seasons of evolution.
    finals: dict[str, list[np.ndarray]] = {}

    start = time.perf_counter()
    for replicate in range(cfg.replicates):
        histories = run_replicate(
            cfg, replicate, checkpoints=set(checkpoints) if replicate == 0 else None
        )
        for history in histories:
            for row in history.rows:
                rows.append({"replicate": replicate, **row})
            if replicate == 0:
                traces[history.league] = history.traces
            final = history.final_population
            finals.setdefault(f"{history.league}_attributes", []).append(final.attributes)
            finals.setdefault(f"{history.league}_strategy", []).append(final.strategy)

        if not quiet:
            elapsed = time.perf_counter() - start
            done = replicate + 1
            eta = elapsed / done * (cfg.replicates - done)
            print(
                f"  replicate {done}/{cfg.replicates}  "
                f"{elapsed:6.1f}s elapsed  ~{eta:5.1f}s left"
            )

    write_seasons(rows, out_dir / "seasons.parquet")
    np.savez_compressed(
        out_dir / "final_populations.npz", **{k: np.stack(v) for k, v in finals.items()}
    )
    payload = build_web_payload(cfg, rows, traces, checkpoints)
    (out_dir / "web_data.json").write_text(json.dumps(payload, separators=(",", ":")))

    games = cfg.replicates * len(cfg.leagues) * cfg.seasons * (
        cfg.tournament.regular_season_games * cfg.tournament.n_teams // 2
        + cfg.tournament.n_teams - 1
    )
    write_manifest(
        cfg,
        out_dir / "manifest.json",
        {"wall_clock_seconds": round(time.perf_counter() - start, 2), "games_simulated": games},
    )

    if not quiet:
        print(f"\n{games:,} games in {time.perf_counter() - start:.1f}s -> {out_dir}")

    return payload


def report(cfg: RunConfig, rows: list[dict[str, Any]]) -> None:
    """Headline comparison, printed so a run is readable without the website."""
    tail = max(1, cfg.seasons // 20)
    print(f"\nfinal {tail} seasons, mean across {cfg.replicates} replicates")
    print(f"{'metric':<26}" + "".join(f"{lg.name:>12}" for lg in cfg.leagues))
    print("-" * (26 + 12 * len(cfg.leagues)))

    for metric in ("strat_aggression", "attr_offense", "margin_sd", "blowout_rate",
                   "close_rate", "upset_rate", "sd_aggression"):
        line = f"{metric:<26}"
        for lg in cfg.leagues:
            values = [
                row[metric] for row in rows
                if row["league"] == lg.name and row["season"] >= cfg.seasons - tail
            ]
            line += f"{np.mean(values):12.4f}"
        print(line)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run an incentive-evolution experiment")
    parser.add_argument("--config", type=Path, default=Path("configs/baseline.yaml"))
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--seasons", type=int, default=None)
    parser.add_argument("--replicates", type=int, default=None)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    cfg = load_config(args.config)
    overrides = {}
    if args.seasons is not None:
        overrides["seasons"] = args.seasons
    if args.replicates is not None:
        overrides["replicates"] = args.replicates
    if overrides:
        cfg = RunConfig(**(cfg.to_dict() | overrides | {
            "leagues": cfg.leagues,
            "match": cfg.match,
            "learning": cfg.learning,
            "evolution": cfg.evolution,
            "tournament": cfg.tournament,
        }))

    out_dir = args.out or Path(cfg.output_dir) / cfg.name
    print(f"{cfg.name}: {cfg.seasons} seasons x {cfg.replicates} replicates x "
          f"{len(cfg.leagues)} leagues")

    run(cfg, out_dir, quiet=args.quiet)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
