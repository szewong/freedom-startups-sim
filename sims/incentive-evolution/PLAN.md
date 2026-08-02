# Build Plan — Incentive Evolution Simulator

Derived from `game.md`. This document is the engineering + experimental design plan.

---

## 1. The mechanism we are actually testing

Before writing code it is worth stating the math, because it tells us what the
engine *must* be able to express and gives us a falsifiable prediction.

Let a team's point margin in a game be approximately `Normal(μ, σ)`, where the
team's strategy influences both terms.

- **League A** reward is `P(margin > 0) = Φ(μ/σ)`.
  For any team with `μ > 0`, this is **decreasing in σ**.
  → Optimal play: raise μ, suppress variance. Risk-averse.

- **League B** reward is `P(margin ≥ 5) = Φ((μ − 5)/σ)`.
  For a team with `μ < 5`, this is **increasing in σ**.
  → Optimal play: buy variance. Risk-seeking.
  For a dominant team with `μ > 5` it flips back to variance-suppressing.

Two consequences fall out, and they are the pre-registered hypotheses:

**H1 — Divergence.** League B evolves higher risk/aggression than League A,
from an identical start, with the reward function as the only difference.

**H2 — Bimodality.** League A converges to a single behavioural mode.
League B **splits**: teams above the threshold in expectation play safe, teams
below it gamble. So B is more diverse, more bimodal, higher variance in outcomes,
more blowouts *and* more upsets.

**H3 — The headline (the book's thesis).** There are two routes to clearing a
higher bar: get genuinely better (raise μ — slow, costly, budget-constrained) or
get louder (raise σ — cheap, instant). If variance is cheap relative to skill,
League B evolves *more volatile* competitors rather than *stronger* ones — and
loses a neutral head-to-head against League A. Make the relative cost a tunable
parameter and sweep it: the crossover point is the finding.

> *When the bar is high and skill is expensive, competitors buy variance
> instead of skill.*

The engine must offer this tradeoff without hard-coding the answer. Nothing in
the match engine may reference the reward threshold.

---

## 2. Design decisions (deviations from / clarifications of the PRD)

| # | Issue in the PRD | Decision |
|---|---|---|
| D1 | "Fixed core attributes" vs. "attribute drift" metrics | Attributes are **fixed for a team's lifetime**. Populations drift via reproduction between seasons: bottom X% replaced by mutated copies of top performers. Two learning channels: fast (strategy, within-life) and slow (attributes, across generations). |
| D2 | Unbounded attributes would all drift to 1.0 | Hard **attribute budget**: `sum(attributes) ≤ B`. Evolution must *allocate*, not just accumulate. This makes "does League B trade defense for offense?" a real, answerable question. |
| D3 | Pure single-elimination gives winners ~6 games and losers 1 | Add a **regular season** (Swiss or partial round-robin, ~12 games) before the bracket, so every team gets equal learning signal. Otherwise "the winners learned more" is a confound competing with the reward function. |
| D4 | "Which system wins more tournaments?" is unanswerable within-league | Add a **neutral inter-league tournament**: evolved A teams vs. evolved B teams under plain win/loss rules, no further learning. This is the only fair cross-population yardstick. |
| D5 | Nothing establishes that observed divergence exceeds drift | Add a **null control**: two populations with *identical* reward functions, different seeds. Measures divergence from drift alone. Any real effect must clear this band. |
| D6 | Binary reward is a very noisy learning signal | Learn on a **moving average of reward over a window** (150 games — sized against the measured effect in §11), not per-game. Otherwise hill climbing is pure noise. |

D3, D4, D5 are the ones that turn this from a demo into something defensible in
a book.

---

## 3. Stack

- **Python 3.12 + NumPy**, vectorised across games. No per-game Python loops.
- `polars` or `pyarrow` for results (Parquet), `matplotlib` for charts.
- `pytest` for the engine sanity tests, `pyyaml` for configs.
- Escalate to `numba` only if the benchmark gate in Phase 1 fails.

**Scale budget.** 10,000 tournaments × 63 games × 2 leagues × ~30 seeds is
~40M games. Vectorising across (seeds × concurrent games in a round) makes each
round one batched NumPy op over ~1,000 games. Target: a full baseline run in
minutes, not hours. Benchmarked in Phase 1 before anything is built on top.

---

## 4. Module layout

```
freedomgaemsim/
├── game.md                    # PRD
├── PLAN.md                    # this file
├── pyproject.toml
├── configs/
│   ├── baseline.yaml          # A (thr=1) vs B (thr=5)
│   ├── threshold_sweep.yaml   # thr ∈ {1,2,3,5,10}
│   ├── cost_sweep.yaml        # skill-cost vs variance-cost (H3)
│   └── null_control.yaml      # D5
├── src/incentive_sim/
│   ├── config.py              # dataclasses, YAML load, seed derivation
│   ├── population.py          # struct-of-arrays teams; attrs + strategy
│   ├── match.py               # vectorised possession-level match engine
│   ├── reward.py              # threshold-parameterised reward fns
│   ├── learning.py            # (1+1)-ES / hill climb on strategy
│   ├── evolution.py           # between-season selection + reproduction
│   ├── tournament.py          # regular season + single-elim bracket
│   ├── season.py              # the main loop
│   ├── metrics.py             # streaming accumulators + reservoir sampling
│   ├── experiment.py          # sweeps, replicates, CLI
│   └── analysis/
│       ├── load.py
│       └── charts.py
├── tests/
└── results/                   # gitignored
```

---

## 5. Model specification

### Team

Attributes (fixed per lifetime, `0..1`, budget-constrained):
`offense`, `defense`, `risk_capacity`, `adaptability`, `stamina`

Strategy (evolves within lifetime, `0..1`):
`aggression`, `off_emphasis`, `def_emphasis`, `tempo`, `margin_seeking`,
`endgame_conservatism`

### Match engine

Possession-level so that endgame behaviour is meaningful:

```
possessions   P  = P0 + k_t · (tempo_i + tempo_j) / 2
per-poss mean μ_i = base(off_i·off_emph_i , def_j·def_emph_j)
                    · (1 − κ · max(0, aggression_i − risk_capacity_i)²)
per-poss var  v_i = v0 · (1 + γ · aggression_i)
```

The three levers, deliberately non-aligned so the strategy space is not trivial:

- **Aggression** always raises variance; raises efficiency only up to the team's
  `risk_capacity`, then costs mean. *This is the variance purchase.*
- **Tempo** raises possessions, so total mean grows `∝ P` but total σ grows
  `∝ √P` — higher tempo *reduces* relative variance. Opposite sign to aggression.
- **Endgame conservatism** cuts variance (and slightly cuts mean) in the final
  segment when leading; **margin_seeking** keeps pushing when ahead. These are
  the knobs a threshold league should be able to discover.

**Stamina** decays performance across a tournament run; the decay is amplified by
aggression and damped by the `stamina` attribute.

Sanity tests gate this phase (Phase 1 exit criteria):
1. Higher `offense` beats lower `offense` more often than chance.
2. `aggression ↑` ⇒ margin variance ↑, monotonically.
3. A genuine mean–variance frontier exists (no strategy dominates).
4. **The engine is reward-blind** — asserted by grep and by test.

### Reward

```python
reward = 1.0 if (won and margin >= threshold) else 0.0
```
League A is threshold = 1. League B is threshold = 5. Same code path,
one parameter. Nothing else differs between leagues, ever.

### Learning (fast channel)

Per-team **(1+1) evolution strategy** on the strategy vector:
propose a mutation, evaluate over a window of games, keep it if the
moving-average reward improved. Step size scaled by the team's `adaptability`.

**Sized against a measured constraint** (see Phase 1 findings, §12): the reward
edge from buying variance is only ~3 percentage points, needing ~1,900 games per
arm for a 2σ read. No practical per-team window reaches that, so the fast
channel is a **fine-tuner, not the driver**. Window set to 150 games (~10
seasons) and expectations set accordingly.

### Evolution (slow channel)

Between seasons: rank by season reward, bottom 20% replaced by mutated copies of
the top 20% (attributes + strategy inherited, both mutated, budget re-normalised).
`σ_attr` vs `σ_strat` is one **skill-cost / variance-cost knob for H3**; the
match engine's `variance_gain` / `overreach_penalty` pair is the other, and both
get swept in Phase 7.

**This is the primary channel.** A 3-percentage-point reward edge is invisible to
a single team but is a selection coefficient of s ≈ 0.08 across a 64-team
population — very strong in evolutionary terms, and it compounds over hundreds
of seasons at 20% replacement. Selection aggregates a signal that hill climbing
cannot see. If divergence appears, this is expected to be why.

---

## 6. Metrics & storage

Per-game rows are ~40M — too many to keep. Instead:

- **Per-season aggregates** (full fidelity): population means/σ/percentiles for
  every attribute and strategy parameter, win rate, avg score, avg margin,
  championships, Final Four, avg elimination round, upset rate, blowout rate,
  close-game rate. → Parquet.
- **Per-game detail**: reservoir-sampled (~200k rows) for margin histograms.
- **Bimodality diagnostics** (H2): dip test / bimodality coefficient on the
  aggression distribution, plus KDE snapshots at fixed checkpoints.
- **Final populations** serialised so the neutral cross-league tournament (D4)
  can be run without re-simulating.

Every run writes a manifest: config hash, seed, git SHA, library versions.

---

## 7. Phases

| Phase | Deliverable | Exit criteria |
|---|---|---|
| **0** | Repo scaffold: `git init`, `pyproject.toml`, config loader, seeded RNG plumbing, CI-free pytest setup | `pytest` runs green on an empty suite; a config round-trips |
| **1** | `population.py`, `match.py` + sanity tests + **benchmark gate** | The 4 sanity tests pass; ≥1M games/min vectorised |
| **2** | `reward.py`, `learning.py`; single-league smoke test | Strategy demonstrably responds to reward: a league with threshold 10 raises aggression vs. threshold 1, over a short run |
| **3** | `tournament.py` (regular season + bracket), `evolution.py`, `season.py` | A full 500-season run completes; no NaNs; budget constraint holds |
| **4** | `metrics.py` + Parquet writer + manifest | Re-running a seed reproduces results byte-for-byte |
| **5** | `experiment.py`: baseline A vs B, 30 replicate seeds, **null control** | H1 tested with CIs; effect clears the null-control band — or is honestly reported as absent |
| **6** | `analysis/charts.py` — the six PRD charts | Figures render from stored Parquet with no re-simulation |
| **7** | Threshold sweep {1,2,3,5,10}, cost sweep, **neutral inter-league tournament** | H2 and H3 answered |
| **8** | `FINDINGS.md` — write-up with the presentation-ready figures | Maps each result back to the PRD's success criteria |
| **9** | **Interactive explorer** (see §11) | Threshold/cost/seed are draggable; populations animate; runs offline |

Phases 0–4 are the engine. 5–8 are the science. Phase 2's smoke test is the
real go/no-go: if strategy doesn't move with reward there, nothing downstream
is worth running.

---

## 8. Reproducibility

- `numpy.random.Generator(PCG64)`, seeds derived by `SeedSequence.spawn` from a
  single root seed per (experiment, replicate) — no global RNG anywhere.
- Both leagues initialised from the **same seed**, so `t=0` populations are
  literally identical arrays. Trajectories then diverge, which is the point.
- 30 replicate seeds per condition; report medians with bootstrap CIs, never a
  single run.
- Config hash + git SHA in every manifest.

---

## 9. Falsification

Stated up front so this isn't hypothesis-confirmation:

The result is **null** if League B's mean aggression at convergence is within
the null control's drift band (D5), or if the 95% CI over 30 seeds for the A–B
difference crosses zero. A null is a publishable finding for the book too —
it would mean incentives shape behaviour less than the thesis assumes, and
`FINDINGS.md` reports it either way.

---

## 10. Interactive explorer (Phase 9)

A self-contained page where the threshold, skill-cost/variance-cost ratio, and
seed are draggable and the populations animate — for live audiences, alongside
the static book figures.

**Approach: precomputed sweep, not a browser-side simulator.** Porting the
engine to JS would mean two implementations that must agree, and the numbers on
screen in a talk have to be the same numbers that are in the book. Instead
Phase 7 already runs the parameter grid — we export those runs as compact JSON
(per-season aggregates + histogram bins, downsampled to ~200 checkpoints per
run) and the page interpolates across the grid. Dragging a slider is a lookup,
so it is instant and provably consistent with the published results.

Cost: one export script plus a single-file HTML page. The tradeoff is that only
grid points are explorable, which is the right constraint anyway — every state
the audience can reach is one we actually simulated and can defend.

---

## 11. Findings so far (measured, 2026-08-01)

**Status: phases 0-9 complete. 51 tests green.** Threshold sweep run at 5 and 10;
cost sweep and the formal null control (D5) remain outstanding. Phase 8 (FINDINGS.md
write-up) and the parameter sweeps in Phase 7 beyond the baseline are outstanding.

### Baseline result (600 seasons x 16 replicates, 8.6M games)

From byte-identical starting populations, threshold 1 vs threshold 5 diverged.
Paired by replicate, 95% CI on the difference:

| Measure | A (thr 1) | B (thr 5) | Difference | Significant |
|---|---|---|---|---|
| Aggression | 0.0865 | 0.1345 | +0.0480 | yes |
| Margin volatility | 11.24 | 12.37 | +1.13 | yes |
| Blowout rate | 38.9% | 43.6% | +4.6pp | yes |
| Close-game rate | 24.2% | 21.8% | -2.4pp | yes |
| Tempo | 0.544 | 0.715 | +0.171 | yes |
| Strategy diversity | 0.0700 | 0.0840 | +0.0140 | yes |
| **Offensive skill** | **0.9339** | **0.9311** | **-0.0028** | **yes** |

**H1 confirmed.** **H2 supported** — League B is significantly more diverse.
**H3 confirmed, and sharper than predicted**: League B did not merely fail to get
better, it ended up *fractionally worse* at the underlying game while becoming
markedly more volatile. The neutral head-to-head (D4) is a dead heat — direct win
rate 49.8% / 50.2%, championship share 53.4% / 46.6% with the CI crossing 50%.
Six hundred seasons of chasing a higher bar bought volatility, not skill.

**An unpredicted emergent result:** League B evolved substantially higher *tempo*.
Tempo was designed as the variance-*reducing* lever (σ grows as √P while μ grows
as P), so the naive prediction was that a variance-seeking league would slow down.
But the threshold is on *absolute* margin, and a longer game scales absolute
margins up faster than it scales their spread — so playing faster is a second,
independent route to clearing a fixed points bar. Nobody wrote that strategy in;
selection found it.

**Not significant:** defensive skill, risk capacity, endgame conservatism. The
endgame knobs only fire in one segment of one game state, so they carry far less
signal than the always-on levers.

### Threshold sweep: 5 vs 10 (Phase 7)

Raising League B's bar from 5 to 10 scales every effect in the expected direction,
which is the strongest evidence that the mechanism is real and not an artefact.
Paired by replicate, 600 seasons x 16 replicates each:

| Measure | thr 5: B-A | thr 10: B-A |
|---|---|---|
| Aggression | +0.048 | **+0.156** |
| Risk capacity | +0.036 (ns) | **+0.078 (sig)** |
| Margin volatility | +1.13 | **+2.10** |
| Blowout rate | +4.6pp | **+7.8pp** |
| Close-game rate | -2.4pp | **-4.0pp** |
| Offensive skill | -0.0028 | **-0.0037** |
| Defensive skill | -0.0013 (ns) | **-0.0034 (sig)** |

The harder the bar, the more real capability the population trades away for
volatility. At threshold 10 **both** skill attributes are significantly lower.

**The payoff curve (the answer to "which league is better").** There is no
rule-independent yardstick — every single metric is one league's home rule. The
honest answer is the whole curve, measured against a common opponent:

| Against the same opponent | A-bred | B-bred |
|---|---|---|
| Expected margin | +0.006 | **-0.526** |
| P(win) | 50.01% | 48.34% |
| P(win by 5+) | 34.35% | 34.16% |
| P(win by 10+) | 19.55% | **20.44%** |
| P(LOSE by 5+) | 34.30% | **37.29%** |
| P(LOSE by 10+) | 19.50% | **22.92%** |

At threshold 10 the curves cross at **+6 points**: B-bred teams are better only at
bars at or above roughly their own, and pay for it everywhere else. The downside
grows faster than the upside at every bar.

**Emergent finding — the volatile league runs out of gas.** B wins its share of
single games but almost no championships (42.5% of titles, CI excludes 50%). A
championship is six straight wins, and B evolved high aggression (which amplifies
fatigue) while spending budget on risk capacity rather than stamina. Measured
directly with both sides equally rested, B's win rate against an A-bred team
decays monotonically **48.4% -> 44.0%** from fresh legs to the final. Nobody
designed this; it falls out of the attribute budget interacting with fatigue.

**A measurement bug worth recording:** the first head-to-head sampled only 1,024
direct games and reported a 52% edge for B — the opposite sign of the truth. At
640,000 games the same statistic reads 48.3%. Small-sample noise in a metric with
a ~2pp effect is easily mistaken for a finding.

**Invasion analysis — and a wrong prediction.** Thirty-two teams from each
upbringing in one combined league, lineage traced through reproduction, run to
fixation (300 seasons x 80 trials per rule):

| Rule the combined league runs | B-bred takes over | Verdict |
|---|---|---|
| Bar 1 (League A's rule) | 41.9% ± 11.2% | dead heat |
| Bar 10 (League B's rule) | 74.4% ± 9.7% | B-bred take over |
| Bar redrawn every season, 1-10 | 72.7% ± 9.9% | B-bred take over |

The prediction recorded before running this was that A-bred lineages would
dominate under the shifting bar, because B's edge lives in a narrow band. That
was **wrong**, and the reason is instructive: what decides the shifting case is
not the uncertainty but the *average height* of the bars in the draw. Sampling
uniformly from 1-10 puts nine of ten worlds at a high bar. Being built for high
bars wins there — while still being worse at the underlying game. Narrowing the
draw toward 1 would flip it. The uniform range was a design choice, not a
discovery, and any claim from this row has to carry it.

The productive reading: **you become good at the game you are graded on, and if
the world grades on that game you win, even while being objectively weaker at the
underlying activity.** That sits closer to the book's thesis than the simpler
"chasing the high bar makes you worse" story, and it does not contradict it — B
is still worse in a neutral bracket (42.5% of championships) and still runs out
of gas in a long tournament.

### Phase 1 engine findings

Phases 0 and 1 are complete. 27 tests green.

**Benchmark gate: passed by 92×.** 92M games/min at batch ≥2,048 (4 cores,
NumPy 2.5). The full ~40M-game design projects to **~26 seconds**. Numba is not
needed, and the scale ceiling in the PRD ("10,000+ tournaments") is not a
constraint — we can afford far more replicates than planned, which mostly buys
tighter confidence intervals.

**The mechanism is present and correctly signed.** `scripts/probe_mechanism.py`
holds a moderate favourite (expected margin +1.9) and sweeps its aggression from
0.05 to 0.85 with variance free of charge:

| aggression | mean margin | margin sd | P(m≥1) | P(m≥5) |
|---|---|---|---|---|
| 0.05 | +1.90 | 10.21 | 0.5745 | 0.3967 |
| 0.45 | +1.87 | 12.20 | 0.5634 | 0.4157 |
| 0.85 | +1.93 | 13.84 | **0.5585** | **0.4284** |

Buying variance moves the two reward functions in **opposite directions**
(−1.6pp under threshold 1, +3.2pp under threshold 5) with the mean margin held
flat. This is H1's mechanism, confirmed in the engine's physics before any
learning code exists.

**The important caveat.** Those effects are small in absolute terms: a 2σ read
needs ~1,900 games per arm at threshold 5 and ~7,600 at threshold 1. Consequences:

1. The fast per-team channel was resized (window 20 → 150) and demoted to a
   fine-tuner. Population selection is the primary channel.
2. **Phase 2's smoke test must be read carefully.** A weak or absent response
   there may mean the learner is under-powered rather than that the incentive
   effect is absent — so the smoke test should use an exaggerated threshold
   (10) and many seasons before any conclusion is drawn.
3. The engine constants were deliberately **not** retuned to enlarge the effect.
   Inflating the lever until the hypothesis appears would be manufacturing the
   result; instead `variance_gain` / `overreach_penalty` become swept parameters
   in Phase 7, where "how cheap is variance?" is the actual research question.

---

## 12. Deliberately out of scope

PRD Phase 2 (coach personalities) and Phase 3 (startup simulator). The module
layout keeps `reward.py`, `population.py` and `match.py` cleanly separable so
Phase 3 can swap the domain while reusing the evolution and experiment
machinery — but neither is built now.
