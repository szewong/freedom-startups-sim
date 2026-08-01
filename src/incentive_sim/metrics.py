"""Result storage: Parquet tables plus a run manifest.

Per-season aggregates are kept at full fidelity (cheap); per-game detail is
sampled. Every run writes a manifest so any figure traces back to the exact
config, seed, and code that produced it (PLAN.md §6, §8).
"""

from __future__ import annotations

import json
import platform
import subprocess
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from .config import RunConfig


def _git_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=5
        )
        return out.stdout.strip() or "uncommitted"
    except Exception:
        return "unknown"


def write_manifest(cfg: RunConfig, path: Path, extra: dict[str, Any] | None = None) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    manifest = {
        "config_hash": cfg.hash(),
        "config": cfg.to_dict(),
        "git_sha": _git_sha(),
        "numpy": np.__version__,
        "python": platform.python_version(),
    }
    if extra:
        manifest |= extra
    path.write_text(json.dumps(manifest, indent=2))


def write_seasons(rows: list[dict[str, Any]], path: Path) -> None:
    """Per-season aggregates, one row per (replicate, league, season)."""
    if not rows:
        raise ValueError("no rows to write")
    path.parent.mkdir(parents=True, exist_ok=True)
    columns = {key: [row[key] for row in rows] for key in rows[0]}
    pq.write_table(pa.table(columns), path, compression="zstd")


def summarise(
    rows: list[dict[str, Any]], metric: str, league: str, seasons: int
) -> dict[str, list[float]]:
    """Mean and 95% CI across replicates, per season, for one league."""
    by_season: list[list[float]] = [[] for _ in range(seasons)]
    for row in rows:
        if row["league"] == league:
            by_season[row["season"]].append(row[metric])

    mean, lo, hi = [], [], []
    for values in by_season:
        arr = np.asarray(values, dtype=float)
        m = float(arr.mean())
        se = float(arr.std(ddof=1) / np.sqrt(arr.size)) if arr.size > 1 else 0.0
        mean.append(m)
        lo.append(m - 1.96 * se)
        hi.append(m + 1.96 * se)

    return {"mean": mean, "lo": lo, "hi": hi}
