"""Build the self-contained site from a completed run.

    python scripts/build_site.py results/baseline web/index.html

Everything is inlined — the page makes no network requests, so it works opened
from disk and works under a strict content-security policy.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq

# Metrics reported in the significance table, with display precision.
STAT_ROWS = [
    ("strat_aggression", "Aggression", 4),
    ("attr_offense", "Offensive skill", 4),
    ("attr_defense", "Defensive skill", 4),
    ("attr_risk_capacity", "Risk capacity", 4),
    ("strat_tempo", "Tempo", 4),
    ("strat_endgame_conservatism", "Endgame conservatism", 4),
    ("margin_sd", "Margin volatility (points)", 3),
    ("blowout_rate", "Blowout rate (10+ points)", 4),
    ("close_rate", "Close-game rate (within 3)", 4),
    ("upset_rate", "Upset rate", 4),
    ("sd_aggression", "Strategy diversity", 4),
]

TAIL_SEASONS = 30


def paired_stats(parquet: Path, leagues: list[str]) -> list[dict]:
    """Per-replicate paired differences between the two leagues.

    Pairing matters: both leagues share a starting population within a seed, so
    differencing within a seed removes starting-population luck entirely.
    """
    table = pq.read_table(parquet).to_pydict()
    n = len(table["season"])
    max_season = max(table["season"])
    cutoff = max_season - TAIL_SEASONS + 1
    replicates = sorted(set(table["replicate"]))

    index: dict[tuple[str, int], list[int]] = {}
    for i in range(n):
        if table["season"][i] >= cutoff:
            index.setdefault((table["league"][i], table["replicate"][i]), []).append(i)

    rows = []
    for metric, label, decimals in STAT_ROWS:
        values = {
            league: np.array(
                [np.mean([table[metric][i] for i in index[(league, r)]]) for r in replicates]
            )
            for league in leagues
        }
        delta = values[leagues[1]] - values[leagues[0]]
        se = delta.std(ddof=1) / np.sqrt(delta.size) if delta.size > 1 else 0.0
        lo, hi = delta.mean() - 1.96 * se, delta.mean() + 1.96 * se

        rows.append(
            {
                "metric": metric,
                "label": label,
                "decimals": decimals,
                "a": float(values[leagues[0]].mean()),
                "b": float(values[leagues[1]].mean()),
                "delta": float(delta.mean()),
                "lo": float(lo),
                "hi": float(hi),
                "significant": bool(lo * hi > 0),
            }
        )
    return rows


def main() -> int:
    run_dir = Path(sys.argv[1] if len(sys.argv) > 1 else "results/baseline")
    out_path = Path(sys.argv[2] if len(sys.argv) > 2 else "web/index.html")
    template = Path("web/template.html")

    data = json.loads((run_dir / "web_data.json").read_text())
    leagues = [lg["name"] for lg in data["meta"]["leagues"]]

    def optional(name: str):
        path = run_dir / name
        return json.loads(path.read_text()) if path.exists() else None

    h2h = optional("head_to_head.json")
    payoff = optional("payoff_curve.json")
    fatigue = optional("fatigue_curve.json")
    invasion = optional("invasion.json")

    stats = paired_stats(run_dir / "seasons.parquet", leagues)

    # A CI excluding zero is not enough: identically rewarded populations drift
    # apart too. Where a null control exists, its verdict is the decisive one.
    vs_null = optional("vs_null.json") or {}
    for row in stats:
        verdict = vs_null.get(row["metric"])
        if verdict:
            row["survives_null"] = verdict["survives_null_control"]
            row["t_vs_null"] = verdict["t"]

    html = template.read_text()
    for placeholder, payload in (
        ("/*__DATA__*/ null", data),
        ("/*__H2H__*/ null", h2h),
        ("/*__STATS__*/ null", stats),
        ("/*__PAYOFF__*/ null", payoff),
        ("/*__FATIGUE__*/ null", fatigue),
        ("/*__INVASION__*/ null", invasion),
    ):
        if placeholder not in html:
            raise ValueError(f"placeholder missing from template: {placeholder}")
        html = html.replace(placeholder, json.dumps(payload, separators=(",", ":")), 1)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(html)

    significant = sum(1 for row in stats if row["significant"])
    print(f"wrote {out_path} ({len(html) / 1024:.0f} KB)")
    print(f"{significant}/{len(stats)} measures significantly different")
    for label, blob, script in (
        ("head-to-head", h2h, "scripts/head_to_head.py"),
        ("payoff curve", payoff, "scripts/payoff_curve.py"),
        ("fatigue curve", fatigue, "scripts/fatigue_curve.py"),
        ("invasion", invasion, "scripts/invasion.py"),
    ):
        print(f"  {label:<14} {'included' if blob else f'MISSING — run {script}'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
