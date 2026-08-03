"""Phase 4: fit the model to the world, then freeze it (PRD §4, METHOD §4).

Do not run this after looking at a counterfactual. That is the whole point of
the phase ordering, and any exception has to be written down in FINDINGS.md.
"""

from __future__ import annotations

import argparse
import json

from foundersim.calibrate import (
    SEARCH_SETS,
    TARGET_SETS,
    freeze,
    measure,
    report,
    score,
    search,
)
from foundersim.config import SMALLCAP_STAGE_TERMS, CapitalConfig, RunConfig


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=250)
    ap.add_argument("--refine", type=int, default=120)
    ap.add_argument("--search-replicates", type=int, default=2)
    ap.add_argument("--founders", type=int, default=2500)
    ap.add_argument("--confirm-founders", type=int, default=10_000)
    ap.add_argument("--out", default="configs/frozen.yaml")
    ap.add_argument("--world", default="default", choices=sorted(TARGET_SETS),
                    help="which world to fit: the headline venture ladder, or small-cap")
    args = ap.parse_args()

    targets = TARGET_SETS[args.world]
    space = SEARCH_SETS[args.world]
    arms = tuple(sorted({t.arm for t in targets}))

    base = RunConfig()
    if args.world == "smallcap":
        # A different ladder, not just different parameters: Series C and D do
        # not exist for these companies.
        base = base.replace(capital__stage_terms=[
            {f: getattr(t, f) for f in CapitalConfig().stage_terms[0].__dataclass_fields__}
            for t in SMALLCAP_STAGE_TERMS
        ])

    print(f"world={args.world}  {args.trials} trials at n={args.founders} over {len(arms)} arms")
    cfg, best, history = search(
        base,
        n_trials=args.trials,
        n_founders=args.founders,
        n_refine=args.refine,
        replicates=args.search_replicates,
        targets=targets,
        space=space,
    )

    # Re-measure the winner on a much larger cohort: a score that only survives
    # at the search size was fitted to sampling noise, not to the world.
    stats = measure(cfg.replace(n_founders=args.confirm_founders), arms, replicates=3)
    print(f"\nbest search score {best:.4f}; at n={args.confirm_founders}: "
          f"{score(stats, targets):.4f}\n")
    for row in report(stats, targets):
        mark = "OK  " if row["hit"] else "MISS"
        print(
            f"  {mark} {row['target']:24s} want {row['want']:>7.3f}  got {row['got']:>7.3f}"
            f"   ({row['note']})"
        )

    freeze(cfg, args.out, stats, targets)
    print(f"\nfrozen -> {args.out}   config hash {cfg.hash()}")
    with open(f"results/calibration_history_{args.world}.json", "w") as fh:
        json.dump(history, fh, indent=2)


if __name__ == "__main__":
    main()
