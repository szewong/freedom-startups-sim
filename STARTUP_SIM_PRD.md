# Founder Wealth Simulator — design document

**Status:** specification only. To be built clean, in its own repository, in a
fresh session. Nothing here shares code with the basketball simulation.

---

## 1. The question

> **Does raising big rounds make founders wealthier than grinding it out alone?**

Not "does it build bigger companies" — that answer is known and uninteresting. The
question is about the **founder's own take-home wealth**, after dilution, after
liquidation preferences, after the years of below-market salary, and after
accounting for the companies that die.

The answer must be a **distribution**, never a mean. Venture outcomes are power-law
and bootstrapped outcomes are not, so a mean comparison is arithmetic that tells
you nothing. What matters is the median founder, the tails, and the probability of
walking away with nothing.

### Why a simulation

The counterfactual is unobservable. We cannot watch the same founder with the same
idea both raise $40M and bootstrap. Observational data is hopelessly confounded:
the companies that raise are the ones that *could* raise, so any comparison of
outcomes measures selection as much as strategy.

A simulation makes the counterfactual free — **the same founder, the same idea,
the same luck, forked at the capital decision.** That pairing is the entire value
of the exercise, and it is the one thing the design must protect.

---

## 2. What the basketball simulation established, and what carries over

Three results from `v1.0-findings` are structural, not sport-specific, and this
model should be built to test whether they survive translation:

1. **A threshold reward buys volatility, not capability.** A liquidation
   preference stack *is* a threshold on founder payoff — below it you receive
   nothing regardless of how good the business is.
2. **Height drives volatility; all-or-nothing shape drives capability collapse.**
   Whether the founder payoff is a step or a ramp should matter more than how high
   the step is.
3. **Given the choice, populations refuse a high bar unless capital makes it pay —
   then convert wholesale.** And the resulting population is capital-*dependent*:
   far better while the money flows, far worse once it stops.

Two methodological rules also carry over, and both were learned the hard way:

- **Nothing is a finding until its spread is examined.** A mean curve that looks
  like a shape is not a result. v1.0 retracted a headline claim for exactly this.
- **A null control is mandatory.** Run the identical machinery with the treatment
  removed, and report effects against *that*, not against zero.

---

## 3. Model

Annual periods. Horizon 12 years. One company per founder; no co-founder politics.

### 3.1 What is drawn at founding, and never observed by anyone

Each company draws a latent quality it cannot see and neither can its investors.
This is the crux of realism: **nobody knows at the start whether the idea is
good.**

| Latent | Distribution | Notes |
|---|---|---|
| `market_size` | lognormal, median ~$300M, heavy right tail to $50B+ | The ceiling on revenue |
| `fit` | Beta(2, 5), so most ideas are mediocre | Converts spend into growth |
| `founder_skill` | Beta(5, 5) | Execution multiplier, mildly heritable across a cohort |

These three, plus luck, determine everything. The capital decision does **not**
change them — that is what makes the fork a clean counterfactual, and it is also
the model's most important simplification (see §8).

### 3.2 Business dynamics

```
new_customers   = fit · founder_skill · f(sales_spend) · (1 − penetration)
                  where f is concave — diminishing returns on spend
revenue         = customers · price
gross_profit    = revenue · gross_margin            (SaaS ≈ 0.78)
opex            = headcount · cost_per_head         (≈ $190k fully loaded)
headcount       = max(founders, revenue / revenue_per_head)   (≈ $180k at scale)
churn           = 12% annual, worse at low fit
cash           += gross_profit − opex − sales_spend + capital_raised
```

`sales_spend` is the company's lever. Bootstrapped companies can only spend what
they generate; funded companies can spend ahead of revenue. That single asymmetry
is most of the difference between the two paths.

### 3.3 Capital, dilution, and the waterfall

This is where the precision matters, because this is where the founder's answer
actually lives.

**Rounds.** Gated on metrics, not granted. A company can raise if it clears the
stage's bar; otherwise it cannot, whatever it wants.

| Stage | Gate (ARR, growth) | Raise | Pre-money | Dilution incl. pool |
|---|---|---|---|---|
| Pre-seed | — | $0.5M | $4M | ~13% |
| Seed | $150k, growing | $3M | $12M | ~22% |
| Series A | $1.5M, >2x YoY | $12M | $45M | ~23% |
| Series B | $6M, >2x YoY | $35M | $150M | ~21% |
| Series C | $18M, >1.7x | $80M | $500M | ~15% |
| Series D+ | $45M, >1.5x | $150M | $1.2B | ~12% |

**Option pool** is created and refreshed **pre-money**, so founders bear it. This
is not a detail — it is a meaningful share of total founder dilution and is
routinely underestimated.

**Liquidation preference:** 1× non-participating, stacking across rounds. On exit
each investor takes `max(preference, pro-rata share of proceeds)`. Model
participating preferred as a switchable variant — it is rarer but brutal.

**The waterfall** is the single most important function in the codebase and must
be unit-tested against hand-worked examples:

```
exit_value → pay preferences in reverse order of seniority
           → remaining to common, pro rata
           → founder receives their common share
```

The consequence to make visible: a company that raised $50M and exits at $40M
returns **zero** to the founder. That is a step function written into the cap
table, and the founder chose its height every time they raised.

### 3.4 Failure — emergent, not assumed

**Do not hardcode a failure rate.** Failure must fall out of the mechanics, or the
model is assuming its own answer. A company dies when:

1. Cash reaches zero, **and**
2. It cannot clear the gate for the next round, **and**
3. No acquihire offer lands (small probability, scaled by team size — returns
   preference partially, founder typically gets little or nothing)

This produces the right structure for free: funded companies die *later and
harder* (they raised the burn along with the money), bootstrapped ones die
*earlier and cheaper*, and the observed failure rate becomes an **output to
calibrate against** rather than an input to assert.

### 3.5 The founder's ledger

Wealth is not just the exit. Count all four, discounted to present value:

| Component | Bootstrapped | Funded |
|---|---|---|
| Salary | Modest, from profit; rises with the business | ~$150k, rises slowly with stage |
| Distributions | Real and recurring once profitable | Essentially never |
| Exit proceeds | After a small pool, near-full ownership | After dilution and the preference stack |
| Secondary sales | Rare | Possible at later stages — model it, it matters |

**Subtract opportunity cost.** A competent founder forgoes roughly $250–400k/year
in salaried work. Over ten years that is $2.5–4M, and ignoring it flatters both
paths — but flatters the funded path more, because its salaries are lower for
longer. Report wealth both gross and net of it.

---

## 4. Calibration — the discipline that makes this credible

Before running a single counterfactual, the model must reproduce known aggregate
statistics. **Calibrate first, then ask the question.** A model that cannot
reproduce the world it claims to describe has no standing to make claims about it.

| Target | Approximate real value | Source of truth to check against |
|---|---|---|
| VC-backed reaching $1B+ | ~1% | Published cohort analyses |
| VC-backed reaching $100M+ exit | ~10% | " |
| Seed → Series A graduation | ~15–30% | " |
| VC-backed returning < 1× capital | ~65–75% | " |
| Median VC-backed founder outcome | Small or nothing | " |
| Bootstrapped 5-year survival | Much higher; low ceiling | SMB survival data |
| Time to meaningful exit | 7–10 years | " |

Tune the latent distributions and gates until the funded arm reproduces these,
**then freeze them**. Any parameter touched after seeing counterfactual results
must be recorded as such — this is the p-hacking exposure and it should be
policed, not trusted.

---

## 5. Experiment design

### 5.1 The fork

For each of N founders (N ≥ 5,000):

1. Draw `market_size`, `fit`, `founder_skill`, and a fixed random stream.
2. Run the **same** founder down each capital strategy, sharing the same luck
   wherever the paths have not yet diverged (common random numbers).
3. Record the full ledger for each.

Strategies to compare:

| Strategy | Description |
|---|---|
| Bootstrap | Never raise. Growth funded from gross profit. |
| Friends & family | One small round, then self-funded. |
| Seed and stop | Raise seed, then bootstrap to profitability. |
| Standard venture | Raise at every gate cleared. |
| Maximum venture | Raise the largest round available at every gate. |

The paired design is what makes this worth doing. Report **paired differences**,
not two independent distributions.

### 5.2 Null control

Run the identical machinery with the capital mechanism neutered — raises give
cash but no dilution and no preference. Any effect attributed to *capital
structure* must exceed what this control produces. Without this the model cannot
distinguish "raising changed the outcome" from "the paths diverged."

### 5.3 Reporting

Never a mean alone. For each strategy report:

- **Median** founder wealth (the honest headline)
- **P10, P25, P75, P90, P99**
- **P(wealth = 0)** — the most under-reported number in venture
- **P(> $1M)**, **P(> $10M)**, **P(> $100M)**
- **Years to first $1M** of realised, spendable wealth
- All of the above **net of opportunity cost**

A useful summary: at what percentile of luck does raising overtake bootstrapping?
If it only wins above the 90th percentile, that is the finding, and it is a very
different claim from "raising pays."

---

## 6. Sweeps worth running

| Sweep | Question |
|---|---|
| Preference multiple (1×, 1.5×, 2×, participating) | How much of the founder's downside is the term sheet rather than the business? |
| Market-size distribution tail | Does raising only pay for founders in genuinely huge markets? |
| Exit multiple regime (bull vs bear) | Is the answer regime-dependent? Almost certainly. |
| Salary level | How much of the bootstrapper's advantage is simply being paid? |
| Secondary availability | Does partial liquidity change the calculus materially? |
| Graded vs step payoff | Direct test of v1.0 §4.2c in a domain where it matters |

---

## 7. Build phases

| Phase | Deliverable | Exit criteria |
|---|---|---|
| 0 | Repo, config, seeded RNG, ledger types | Config round-trips; seeded runs reproduce byte-for-byte |
| 1 | Cap table + **waterfall** | Unit tests against hand-worked examples, including the raised-$50M-exit-$40M zero case |
| 2 | Business dynamics, no capital | A bootstrapped company grows and plateaus plausibly |
| 3 | Rounds, gates, dilution, death | Failure emerges; no NaNs; cap tables always sum to 1 |
| 4 | **Calibration** | Funded arm reproduces §4 targets; parameters then frozen |
| 5 | Paired counterfactual across strategies | Distributions, not means |
| 6 | Null control and sweeps | Effects reported against the control |
| 7 | Write-up and an interactive explorer | — |

Phase 4 is the gate. Do not run a counterfactual before the model can reproduce
the world, and do not adjust parameters after seeing one.

---

## 8. Threats to validity — write these down before building

**The fork is not really clean.** Raising money changes what you build, who you
hire, and which market you attack. The model holds the idea fixed and varies only
the financing, which is the cleanest comparison and also a fiction. This is the
single biggest limitation and it should be stated in the abstract, not buried.

**Capital may genuinely improve the business.** Money buys speed, talent, and
market share in winner-take-most categories. If the model does not let capital
*create* value it will trivially conclude that raising is bad. It must include a
real, tunable upside — and that upside must be swept, not assumed. *(v1.0 learned
this twice: a mechanism whose only function is to hurt will always be found to
hurt.)*

**Gates encode a theory of investors.** Whether a company "can raise" is modelled
as a metrics threshold. Real investors are noisier, more herd-driven, and more
founder-biased than that. Consider adding noise to the gate and testing whether
the conclusion is sensitive to it.

**Survivorship in the calibration targets.** Published startup statistics are
themselves selected — they mostly describe companies that got far enough to be
counted. Calibrating to them imports that bias.

**The bootstrapper's ceiling is a modelling choice.** How much a self-funded
company can grow is set by parameters, and the answer is sensitive to them. Sweep
it rather than defending one value.

---

## 9. What would falsify the hypothesis

State this before running anything.

The claim under test is that **raising large rounds does not make the median
founder wealthier**. It is **wrong** if, in the paired comparison, the median
funded founder's net-of-opportunity-cost wealth exceeds the median bootstrapped
founder's, and the difference clears the null control.

It is **uninteresting** if the answer is entirely driven by the preference stack
— that would make it an arithmetic result about term sheets rather than a finding
about strategy. Test this by running the sweep with preferences removed; if the
result vanishes, say so plainly.

The most likely honest outcome, given v1.0, is a **crossing**: bootstrapping wins
below some percentile of market luck and venture wins above it. If so, the
location of that crossing is the answer, and "which is better" was the wrong
question — exactly as it was for the two leagues.

---

## 10. Suggested repository layout

```
founder-wealth-sim/
├── PRD.md                  this document
├── src/foundersim/
│   ├── config.py           dataclasses, YAML, seed derivation
│   ├── latents.py          market size, fit, skill draws
│   ├── business.py         growth, churn, headcount, cash
│   ├── captable.py         rounds, dilution, option pool
│   ├── waterfall.py        exit proceeds -> founder take   <-- test hardest
│   ├── strategy.py         the capital strategies being compared
│   ├── ledger.py           salary, distributions, secondary, opportunity cost
│   ├── cohort.py           the paired counterfactual runner
│   └── calibrate.py        fit parameters to the §4 targets
├── tests/                  waterfall cases first, then invariants
└── analysis/               distributions, crossings, sweeps
```

Vectorise across founders as v1.0 did — 5,000 founders × 12 years × several
strategies is small, and speed buys replicates, which buys honest error bars.
