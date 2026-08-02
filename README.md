# Incentive Evolution Simulator

Two leagues of 64 teams start from byte-identical populations and play the same
game under the same physics. One difference: League A rewards any win, League B
only rewards wins by 10 or more. After 600 seasons of selection they have become
different kinds of competitor — markedly more volatile, and slightly *less*
capable.

- **[`PAPER.md`](PAPER.md)** — the write-up, with methods, results, and retractions
- **[`PLAN.md`](PLAN.md)** — design decisions and measured findings
- **[`game.md`](game.md)** — the original brief

---

## 1. Just look at it — no setup

**Open `web/sim.html` in a browser.** Double-click it, or:

```bash
xdg-open web/sim.html      # Linux
open web/sim.html          # macOS
```

That is the whole install. The file is self-contained (37 KB, no network calls)
and simulates live at roughly 150 seasons/second. Press **Run**.

Every control except the seed applies mid-run, which is the interesting part:

| Try this | What you should see |
|---|---|
| Run to season 300, then drag **League B wins by** down to 1 | Both leagues now share a rule; B's aggression decays back toward A's |
| Drag **price of volatility** from 0.9 up to 3 | The volatility gap narrows but survives; the capability gap closes |
| Drop **replaced each season** to 0.05 | Selection gets too weak to find anything and drift swamps the signal |

One run is one sample. The paper's figures average 16 replicates, so a single
browser run wanders considerably more than those confidence intervals suggest.

`web/index.html` is the companion page built from stored results (bracket
playback, evolution charts, the significance tables). It is not committed — build
it with step 4 below.

---

## 2. Run the experiments

Needs Python 3.12+.

```bash
# with uv (fastest)
uv venv && uv pip install -e ".[dev]"

# or with stock tooling
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"

.venv/bin/python -m pytest          # 60 tests, ~4s
```

The headline run — 8.6M simulated games, about 3 minutes on four cores:

```bash
.venv/bin/python -m incentive_sim.experiment \
    --config configs/threshold10.yaml --seasons 600 --replicates 16 \
    --out results/threshold10
```

Then the analyses, each reading the config back from that run's manifest:

```bash
.venv/bin/python scripts/head_to_head.py  results/threshold10   # neutral bracket
.venv/bin/python scripts/payoff_curve.py  results/threshold10   # who is better, at every bar
.venv/bin/python scripts/fatigue_curve.py results/threshold10   # decay across a tournament run
.venv/bin/python scripts/invasion.py      results/threshold10   # whose lineage takes over (~10 min)
```

And the two that decide how strong a claim the results support:

```bash
.venv/bin/python scripts/null_control.py                        # how far identical rules drift apart
.venv/bin/python scripts/vs_null.py results/threshold10         # which effects beat that drift
.venv/bin/python scripts/cost_sweep.py                          # does it survive expensive volatility (~13 min)
```

`vs_null.py` is the one to look at. Testing an effect against zero only says the
two leagues ended up different; testing it against the null control says the
reward function is why. Two effects that look significant fail that test.

Figures land in `figures/`, results in `results/`.

---

## 3. Sanity checks

```bash
.venv/bin/python scripts/probe_mechanism.py   # is the mechanism in the engine at all?
.venv/bin/python scripts/benchmark.py         # games/second, and the 1M/min gate
node scripts/validate_js_engine.cjs           # does the browser engine still agree with Python?
```

The last one matters: `web/engine.js` is a second implementation of the same
model, and two implementations drift. It runs the JS engine at the paper's
baseline and checks its converged statistics against the Python numbers.
Agreement is statistical, not bit-for-bit — NumPy's PCG64 is not reproduced in
the browser.

---

## 4. Rebuild the pages

```bash
.venv/bin/python scripts/build_sim.py                                 # -> web/sim.html
.venv/bin/python scripts/build_site.py results/threshold10 web/index.html
.venv/bin/python scripts/screenshot_site.py                           # needs playwright
```

Both outputs inline everything they need, so they work from `file://` and under
a strict content-security policy.

---

## Layout

```
src/incentive_sim/
  config.py       dataclasses, YAML, seed derivation
  population.py   struct-of-arrays teams, budget-constrained attributes
  match.py        vectorised possession-level engine — reward-blind by test
  reward.py       the one line that differs between leagues
  learning.py     per-team (1+1)-ES on strategy
  evolution.py    between-season selection and reproduction
  tournament.py   regular season + single-elimination bracket
  season.py       the main loop
  headtohead.py   neutral inter-league tournament
  invasion.py     lineage tracing in a combined league
  metrics.py      Parquet output and run manifests
  experiment.py   CLI

web/engine.js     the same model in JavaScript, for the live page
configs/          baseline (threshold 5) and threshold10
tests/            60 tests: engine sanity, bracket correctness, budget
                  invariants, lineage bookkeeping, reproducibility
```

Bulk outputs (`*.parquet`, `*.npz`) and the large site screenshots are
gitignored. The small JSON result summaries **are** committed, so every number in
`PAPER.md` can be checked without re-running an experiment.

---

## Reproducibility

Every result derives from one root seed; runs are byte-identical on re-execution,
and each results directory carries a manifest with the full config, its hash, the
git SHA, and library versions. The match engine is reward-blind by construction —
a test tokenises its source and fails if the executable code mentions a
threshold, a reward, or a league.
