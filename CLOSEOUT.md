# v1.0 — closed

The basketball simulation is finished. This is what it established, what it
retracted, and where everything lives.

**Tag:** `v1.0-findings` on `master`. 60 tests green; JS engine agrees with Python.

---

## What it answers

Two leagues of 64 teams, byte-identical at season zero, same game and same
physics. One difference: what counts as a success. 600 seasons, 16 replicates,
8.6M simulated games.

### Confirmed — survives a drift null control

| Finding | Evidence |
|---|---|
| A success threshold makes a population markedly **more volatile** | aggression +0.156, margin sd +2.10, blowouts +7.8pp (t = 4.8–6.0 vs drift) |
| It does **not** make it more capable | skill marginally *lower* (t = 2.0–2.4) |
| …but only where volatility is cheaper than skill | price sweep, §4.7 — the effect vanishes at high κ |
| The trade is **unfavourable, not lateral** | +0.89pp of blowout wins against +3.42pp of blowout losses |
| The volatile league **wins games but loses tournaments** | win rate decays 48.4% → 44.0% across a six-round run |
| "Which league is better" is **ill-posed** | payoff curves cross at +6 points; the crossing is the answer |
| **Height drives volatility; shape drives collapse** | graded reward at the same bar removes the capability loss entirely (§4.2c) |

The last row is the most actionable. Replacing the step with a ramp — partial
credit toward the same bar — leaves volatility untouched and eliminates the
capability loss. At a bar of 50 a step-rewarded population decays to 0.715 skill
and loses to baseline 90% of the time; a graded population at the *identical* bar
holds 0.933 and plays baseline to a dead heat.

### Retracted — on the record

| Claim | Why it fell |
|---|---|
| League B improves faster early (truncation selection) | Did not survive its error bars: sd 0.184 against a mean of +0.042, ns at every season |
| A purchasable "signal" proxy explains fundraising | Tautological — a parameter whose only function is to be rewarded is a dial labelled *cheat* |
| Tempo and risk-capacity diverge | Not distinguishable from drift (t = 1.10, 1.66) |

Three bugs found late, all by the live simulator disagreeing with the paper: a
non-transitive sort comparator in bracket seeding, correlated RNG streams between
the two leagues, and a pace-contaminated capability metric. Converged statistics
stayed inside tolerance through all three, which is why the validator now checks
trajectories too.

---

## Where things are

| Path | What it is |
|---|---|
| `PAPER.md` | The write-up, with methods, results, retractions |
| `web/sim.html` | Live browser simulator — open it, no build step |
| `web/template.html` | Results site, built by `scripts/build_site.py` |
| `PLAN.md` | Design decisions and the measured findings behind them |
| `README.md` | How to run everything |
| branch `endogenous-bar` | Exploratory: teams choose their own bar. Not part of v1.0. |

The `endogenous-bar` branch also carries `scripts/prototype_masking.py`, a
**sketch** of a different mechanism (money buys away the failures you would have
learned from). It has no tests, no null control, and does not use the match
engine. Its numbers are suggestive and should not be quoted as findings.

---

## What v1.0 cannot answer

The basketball frame was chosen for neutrality and it earned its keep — but it
has no money, no ownership, no time horizon, and no way for a competitor to leave
the game. It therefore cannot speak to:

- whether raising capital makes a *founder* wealthier
- what a liquidation preference does to a payoff
- dilution, salary, or opportunity cost
- failure as running out of cash rather than losing a game

Those need a different simulation, specified in `STARTUP_SIM_PRD.md` and to be
built clean in its own repository.
