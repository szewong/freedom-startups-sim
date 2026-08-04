# Does raising make founders wealthier?

**Founder Wealth Simulator, v0.1.** The question, the answer, and what the answer
will not support.

Everything here comes from `configs/smallcap.yaml` (hash `ace68566bc01d22b`)
unless stated: companies topping out near $50M of revenue, grounded on 2025–26
round sizes and lower-middle-market exit multiples. 5,000 founders × 8
replicates. Every comparison is **paired** — the same founder, the same idea,
the same luck, run down each path — so a difference is financing and nothing
else. The working notebook, with every sweep and every wrong turn, is
[`FINDINGS.md`](FINDINGS.md).

---

## 1. The question, and why a simulation

> Does raising big rounds make founders wealthier than grinding it out alone?

Not "does it build bigger companies" — that answer is known. The question is the
founder's own take-home, after dilution, after liquidation preferences, after
years of below-market salary, and after counting the companies that die.

The counterfactual is unobservable. Nobody can watch the same founder with the
same idea both raise $40M and bootstrap, and observational data is hopelessly
confounded: the companies that raise are the ones that *could* raise. So the
simulation makes the counterfactual free, and protects that pairing above
everything else.

## 2. The answer

**Raising buys a salary. It does not buy a return on your shares.**

| | Median wealth | What the shares paid | Equity paid nothing | Founder kept |
|---|---|---|---|---|
| Bootstrap | −$0.46M | **$0.61M** | **0.0%** | 100% |
| Freedom Startup | −$0.44M | $0.31M | 8.1% | 78.3% |
| Standard venture | −$0.28M | **$0.00M** | 58.7% | 63.6% |
| Maximum venture | −$0.16M | $0.16M | **75.6%** | 55.1% |

Standard venture's median founder ends up $180k ahead of bootstrapping — and
**their shares return exactly zero**, because more than half of them get nothing
at all. Every dollar of the advantage is wages: they draw $0.60M of salary in
present value against the bootstrapper's $0.18M.

Against a null control — the same machinery with dilution and preferences
removed — capital structure costs the median maximum-venture founder **$8.25M**
relative to the same cash on neutral terms. The money helps enormously. The
terms take most of it back, and the more you raise the more they take.

### Three findings that survive every sweep

1. **The advantage is payroll, not ownership.** Standard venture's ownership gap
   against bootstrapping is −$0.02M in the big-ladder world and −$0.03M here.
   It does not move when the preference multiple, the exit regime, the market
   tail, the opportunity cost or the capital-upside parameters move.
2. **A bootstrapper's equity is never cancelled.** 0.0%, in every configuration
   tested, because nothing stands in front of it. The venture figure runs 52–76%.
3. **Seed-and-stop is the worst strategy in the study.** −$0.24M against
   bootstrapping, and 92.5% of those founders get nothing. It takes the whole
   preference stack without the money to grow past it.

## 3. The Freedom Startup

Defined precisely, because the philosophy is easy to state loosely and the
result depends on the details:

> **Bootstrap until the business is profitable while paying the founder a real
> salary *and* has passed $100k of ARR. Then raise at every gate that clears,
> on the same ladder and the same terms as anyone else.**

Two conditions, not one. It is not "raise less" and it is not "stay small". The
company goes up the identical ladder on identical terms — it just arrives later,
with a business already built.

### What it does

Among the **61%** of founders for whom the trigger ever fires:

| | vs bootstrapping the same business |
|---|---|
| Total wealth | **+$0.62M** |
| What the shares paid | **+$0.31M** |
| Founders better off | **73.2%** |

**This is the only strategy in the study with a positive ownership gap.** Every
other venture path's shares are worth *less* than bootstrapping the same
business. Delay flips the sign.

### Why it works, mechanically

Two things, both checkable.

**It skips the most expensive round.** Raise on day one and you enter at the
pre-seed, which costs ~19% of the company for $1M. Arrive with $100k of revenue
and you enter at the seed instead — 92.9% of them do. That single step is where
the wipeout rate falls off a cliff: 58.8% raising on day one, 54.3% at $10k of
ARR, **18.2% at $100k**, **8.1%** once profitability is required too.

**It only takes money when it does not need it.** Companies that reach
profitability fail at **7–17%**, against 30–52% for their cohort as a whole.
That is the largest single effect measured anywhere in this study, and it is the
"infinite runway" argument stated as a number.

And the corollary cuts directly at growth-at-all-cost: **raising reduces how many
companies ever become profitable.** Founders who never raise reach it 61% of the
time, by year 3. Founders who raise on day one reach it 40% of the time, by year
7. Taking money does not merely postpone profitability — fewer companies ever
get there.

### Where it wins, by the thing nobody can see

Founder quality here is product-market fit × execution skill, drawn at founding
and never observed by anyone — including the investors. Median ownership return
by decile of it:

| Quality decile | Bootstrap | **Freedom Startup** | Standard venture | Maximum venture |
|---|---|---|---|---|
| 10–30% | $0.01–0.10M | *identical* | $0.00M | $0.00M |
| 40% | $0.22M | $0.17M | $0.00M | $0.00M |
| 50% | $0.56M | $0.37M | $0.00M | $0.00M |
| 60% | $0.76M | **$0.90M** | $0.28M | $0.63M |
| 70% | $0.96M | **$1.49M** | $1.26M | $0.78M |
| 90% | $1.71M | **$3.75M** | $3.67M | $0.97M |
| 100% | $2.62M | **$6.41M** | $5.69M | $1.13M |

Read the shape rather than the numbers. For the bottom third the Freedom Startup
**is** bootstrapping — the trigger never fires, so the outcome is identical,
founder for founder. From the 60th percentile up it beats bootstrapping *and*
beats standard venture at almost every level. It is the only column that is
never catastrophic and still reaches the top.

### The trade, priced

"Keep the upside without buying the downside" is the natural way to say this and
it is too strong. Measured against standard venture, on the same founders:

| | Bootstrap | **Freedom Startup** | Standard venture |
|---|---|---|---|
| p75 of what the shares paid | $1.31M | $1.96M | $2.83M |
| p90 | $2.36M | $4.58M | $8.10M |
| p99 | $5.75M | $13.47M | $33.16M |
| P(shares > $10M) | 0.1% | 2.2% | 7.9% |
| **P(shares paid nothing)** | **0.0%** | **0.0%** | **52.4%** |

The upside is kept in proportion, and not much more than half of it: **69% at
the 75th percentile, 57% at the 90th, 41% at the 99th.** The further into the
tail, the more of it delay costs you. What you buy is the bottom row — a 52.4%
chance of zero, removed.

Paired founder by founder, **Freedom beats standard venture for 63.1%** and
loses to it for 36.8%. Against bootstrapping it is better for 37.1%, worse for
23.7%, and identical for the 39.2% who never reach the trigger.

So the accurate sentence is: **it roughly halves your best case and removes your
worst case entirely.** That is insurance, and this is its price — a bigger
premium than "keep the upside" implies.

### Why the floor holds: you get paid before the exit

The reason no Freedom founder ends with nothing is not that their exits are
safer. 8.1% of them still have their equity wiped *at the exit*. It is that they
have already been paid something before it arrives:

| | Took distributions along the way | Median |
|---|---|---|
| Bootstrap | 97.6% | $39k |
| **Freedom Startup** | **97.6%** | **$51k** |
| Standard venture | **8.0%** | **$0** |

A company that reaches profitability distributes its surplus. A company that is
always raising the next round never does — it is always spending against a
future event. So the venture founder's entire return depends on one moment that
more than half the time pays them nothing, while the Freedom founder has banked
cash on the way there regardless of how the exit goes.

That is the concrete form of "infinite runway", and it is a stronger claim than
the ownership numbers: it is not about how big the exit is, it is about not
needing one.

You cannot know your decile in advance — nobody in this model can, investors
included — so the strategy's value is precisely that it does not require you to.

## 4. What the model will not support

The claims above are the ones that survived. These did not, and stating them is
the point of the exercise.

**It does not make the median founder rich.** −$0.41M, still worse than a
salaried job. No strategy in this study produces a positive median.

**Its overall ownership gap is zero, not positive.** 39% of founders never reach
the trigger, so for the median founder the strategy changes nothing. The +$0.91M
is real but it is conditional on the trigger firing, and you cannot know in
advance that it will.

**It is worse than bootstrapping in the fourth and fifth deciles** — $0.17M
against $0.22M, $0.37M against $0.56M. Founders who scrape over the bar, raise,
dilute, and never reach the upside are made worse off by it. About a fifth of
all founders land there.

**Its failure rate is better than bootstrapping but worse than venture's.** 39.0%
against bootstrapping's 45.2% and standard venture's 36.5%. Waiting for
profitability *alone*, without the revenue condition, is the most dangerous
strategy tested at 52.3% — half the cohort never gets there and dies trying.

**Delay is not monotonically good.** Past roughly $500k of ARR the effect
reverses: those companies enter the ladder higher, clear the later gates
immediately, and end up taking *more* capital in total.

**Stopping early is the wrong half of the idea.** Raising at $100k and capping
at seed gives −$0.62M, worse than never raising. The gain comes from delaying
the start, not from limiting the finish.

## 5. What would change the answer

Stated so it cannot be chosen after the fact:

- **The cost of being understaffed** is the single largest unmeasured parameter.
  At zero, venture wins by $2.18M; at 0.5, by $0.08M. Nobody has measured it.
- **How noisy investors are.** A hard funding threshold gives venture +$0.44M; a
  realistically noisy one gives +$3.83M. No conclusion here is robust to it.
- **Which job you turned down.** At $300k forgone, 72.5% of bootstrappers end up
  worse off; at $100k, only 33.7% do. "Founding is worse than a job" is a claim
  about a $300k job.
- **The `<1× capital` calibration target still misses** in the big-ladder world
  (49.7% against ~70%), in the direction that flatters venture.

## 6. Retractions

Kept on the record, because a result that survived them is worth more than one
never examined.

- **A first counterfactual was run, inspected, and withdrawn.** The two arms used
  different founder-salary policies, so identical businesses failed at 79% or 3%
  depending only on which applied. Fixed, recalibrated from scratch, re-run. It
  is a violation of the calibrate-then-freeze rule and it is recorded as one.
- **The Freedom headline was over-claimed.** "+$1.13M, beats 73%" was a
  conditional median reported without its spread. The distribution shows the
  ownership curves crossing at the 62nd percentile, 38% of raisers *losing*
  ownership, and the median founder's total-wealth gain being wages again.
- **Five model defects were found and fixed**, every one of which had made a
  venture path look better than it was: size-blind exit multiples, one flat
  earnings multiple at every scale, an unpriced pre-seed, "intends to raise"
  read as "money is coming", and the salary policy above.

## 7. How to check it

```bash
cd sims/founder-wealth
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest                 # 71 tests
node scripts/validate_js_engine.cjs        # the browser engine vs the Python one

.venv/bin/python scripts/freedom.py        # every number in §3
.venv/bin/python scripts/delay_curve.py    # the full delay sweep
.venv/bin/python scripts/counterfactual.py # the headline, with the null control
```

The browser engine at [`web/sim.html`](web/sim.html) is a second, independent
implementation. It agrees with the Python to within $58k on a $1.39M median, and
`validate_js_engine.cjs` fails if the two ever drift apart. That is weaker
evidence than a disagreement would have been informative — one engine was
written from the other, so it rules out transcription errors and not shared
misconceptions — but it means the interactive page and this document come from
the same model.

**This is a simulation, not data.** Its value is the counterfactual, which no
observational study can produce, because the founders who raise are not the
founders who don't.
