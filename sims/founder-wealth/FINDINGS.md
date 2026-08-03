# Founder Wealth Simulator — findings, v0.1

**Status: first complete run. Provisional.** All seven phases of PRD §7 are
built and have run end to end, including the live explorer at `web/sim.html`. One
calibration target is still missed and one defect was found *by looking at a
counterfactual*, which is recorded below as the p-hacking exposure it is.

Run: 5,000 founders × 8 replicates × 5 strategies, plus the same again as a null
control. Config hash `9fb906b9abdb110e` (`configs/frozen.yaml`), 12-year horizon.
All figures are present value, after tax, **net of $300k/year of forgone salary**
charged for every year the founder was running the company.

---

## 1. The headline

| Strategy | Median net | P10 | P90 | P99 | P(>$10M) | P(equity = 0) | P(worse than a job) |
|---|---|---|---|---|---|---|---|
| Bootstrap | **−$0.40M** | −$0.72M | +$0.91M | +$3.7M | 0.000 | **0.000** | 0.735 |
| Friends & family | −$0.58M | −$0.97M | +$0.82M | +$3.3M | 0.000 | 0.089 | 0.764 |
| Seed and stop | −$0.76M | −$0.95M | −$0.45M | +$1.5M | 0.000 | **0.855** | 0.945 |
| Standard venture | **+$0.10M** | −$0.77M | +$12.4M | +$129M | 0.118 | 0.516 | 0.487 |
| Maximum venture | **+$2.19M** | −$0.70M | +$70.0M | +$276M | 0.237 | 0.602 | 0.370 |

Paired within founder, against bootstrapping the same idea with the same luck:

| Strategy | Median paired difference | Founders better off |
|---|---|---|
| Friends & family | −$0.06M [−0.06, −0.06] | 36% |
| Seed and stop | −$0.45M [−0.45, −0.45] | 8% |
| Standard venture | **+$0.59M** [+0.55, +0.62] | 66% |
| Maximum venture | **+$2.27M** [+2.19, +2.35] | 76% |

Intervals are 95% across the 8 replicates.

### The hypothesis under test did not survive

PRD §9 stated the claim in advance: *raising large rounds does not make the
median founder wealthier*, and set the falsification condition — it is wrong if
the median funded founder's net wealth exceeds the median bootstrapper's **and**
the difference clears the null control.

The first half happened and the second did not. **In this model the median
venture founder ends up ahead**, by $0.6M on standard venture and $2.3M on
maximum venture. So the claim as literally stated is not supported.

But the reason is not the one either side of this argument usually gives, and it
only shows up once the founder's salary is separated from the founder's shares.
That is §2, and it is the finding.

## 2. Take the salary out and standard venture's advantage disappears entirely

The founder's ledger splits exactly in two, and the two halves are answering
different questions:

```
net wealth  =  [ salary − the salary you turned down ]  +  [ distributions + secondary + exit ]
                        labour P&L                                  ownership return
```

The left side is whether you were paid properly for twelve years of work. The
right side is whether owning the company was worth anything. Only the right side
is what "should I raise?" is usually asked about — and the two move in opposite
directions.

Paired within founder, against bootstrapping the same idea:

| Strategy | Total gap | **Ownership gap** | Founders ahead on ownership | **Labour gap** | Founders ahead on wages |
|---|---|---|---|---|---|
| Friends & family | −$0.06M | −$0.10M [−0.10, −0.10] | 25% | +$0.09M | 71% |
| Seed and stop | −$0.45M | −$0.43M [−0.43, −0.42] | 20% | +$0.13M | 67% |
| **Standard venture** | **+$0.58M** | **−$0.02M** [−0.03, −0.02] | **48%** | **+$0.74M** | **83%** |
| Maximum venture | +$2.27M | +$1.39M [+1.30, +1.47] | 60% | +$0.91M | 88% |

**For standard venture, the ownership gap is −$0.02M.** Not small — *negative*,
and tightly bounded away from anything that would matter. Fewer than half of
those founders (47.8%) did better on ownership than they would have
bootstrapping the identical business. Every dollar of the +$0.58M headline
advantage, and slightly more, is wages.

The absolute levels say the same thing. Median ownership return:

| Strategy | Ownership (median) | P90 | P(ownership > $1M) | P(equity paid nothing) |
|---|---|---|---|---|
| Bootstrap | **$0.71M** | $2.0M | 0.338 | **0.000** |
| Friends & family | $0.53M | $1.8M | 0.262 | 0.089 |
| Seed and stop | $0.27M | $0.5M | 0.049 | 0.855 |
| Standard venture | **$0.54M** | $12.5M | 0.459 | 0.516 |
| Maximum venture | $2.41M | $70.2M | 0.585 | 0.602 |

**The median bootstrapper's shares are worth more than the median standard-venture
founder's shares** — $0.71M against $0.54M — despite the venture companies being
several times larger. 51.6% of venture founders receive nothing at all for their
equity; bootstrappers receive nothing **0%** of the time, because there is no
preference stack standing in front of them. Whatever the business is worth, they
own it.

### So where does the venture money actually come from?

Median present value, by source:

| Strategy | Salary | Distributions | Exit + secondary | Salary forgone |
|---|---|---|---|---|
| Bootstrap | $0.19M | $0.04M | $0.66M | −$1.36M |
| Standard venture | $0.63M | $0.00M | $0.23M | −$1.06M |
| Maximum venture | $0.70M | $0.00M | $0.93M | −$0.91M |

Three things fall out of that table. The venture founder is paid **3.3× more
salary**. They lose less to the job they turned down, because they were funded
sooner and quit later. And their median *exit* — the thing the whole exercise is
supposedly about — pays them **$0.23M against the bootstrapper's $0.66M**.

### Only the biggest raisers get a real ownership gain

Maximum venture is the one arm where ownership genuinely pays: +$1.39M over
bootstrapping, on 60% of founders. Even there, 40% of the total advantage is
still wages — and §3 shows what the terms take back out of it.

So the honest summary of the headline is narrower than §1 makes it sound. **If
you are asking whether raising makes your shares worth more, the answer for the
standard path is no.** If you are asking whether it pays you better while you
find out, the answer is emphatically yes.

That distinction is invisible in any observational comparison, because the
founders who raise are not the founders who don't — and it is invisible in a
single wealth number, which is why the ledger is kept in three streams.

## 3. Capital structure costs the median founder $1.4M — $8.3M

The null control (PRD §5.2) runs the identical machinery with raises giving cash
but no dilution and no preference. The difference between the two gaps is the
part attributable to **capital structure** rather than to the money:

| Strategy | Gap vs bootstrap | ... minus the same gap without dilution or preferences |
|---|---|---|
| Friends & family | −$0.06M | **−$0.23M** [−0.23, −0.22] |
| Seed and stop | −$0.45M | **−$0.49M** [−0.50, −0.48] |
| Standard venture | +$0.59M | **−$1.43M** [−1.46, −1.40] |
| Maximum venture | +$2.27M | **−$8.25M** [−8.70, −7.81] |

Read the last column as: on neutral terms, the same cash would have made the
median maximum-venture founder $8.25M *better off than they actually are*. The
cash helps enormously. The terms take most of it back, and the more you raise
the more they take.

Every one of these intervals excludes zero and is measured against the control,
not against zero (METHOD §2).

## 4. Seed-and-stop is the worst thing you can do

−$0.76M median, worse than every other arm including bootstrapping, and **85.5%
of these founders get nothing for their equity**. It is the only strategy that
takes on the full preference stack without taking the money that might grow the
company past it. You have sold the downside protection and not bought the
upside.

If this model has one piece of practical advice in it, it is this row.

## 5. The crossing is in founder quality, not market luck

PRD §9 predicted a crossing, and there is one — but not where the PRD looked for
it. Sorting founders by latent quality (fit × skill), median net wealth,
standard venture vs bootstrap:

| Quality percentile | Venture | Bootstrap | P(venture better) |
|---|---|---|---|
| 0–5 | −$0.87M | −$0.61M | 0.005 |
| 20–25 | −$0.54M | −$0.38M | 0.417 |
| **25–30** | **−$0.49M** | **−$0.38M** | **0.530** ← crossing |
| 50–55 | −$0.00M | −$0.55M | 0.782 |
| 75–80 | +$2.90M | −$0.02M | 0.931 |
| 95–100 | +$9.45M | +$1.69M | 0.971 |

Venture loses below roughly the 27th percentile of founder quality and wins
above it, decisively by the top quartile.

Sorted by **market size** instead, the curve is nearly flat — venture is ahead by
about the same amount in the smallest markets as the largest. The PRD asked
"does raising only pay for founders in genuinely huge markets?" In this model:
no. Market luck barely moves the founder's own outcome compared with how good
they are at building the thing. That is a result about the model, and worth
holding loosely, but it is a clean one.

## 6. The sweeps, and what they do to the answer

Every uncertain parameter is reported as a curve (METHOD §9). Median paired gap,
standard venture vs bootstrap, unless noted:

| Sweep | Range | Effect on the gap |
|---|---|---|
| **Investor gate noise** | hard threshold → σ=0.70 | **+$0.44M → +$3.83M** |
| **Understaffing penalty** | 0 → 0.5 | **+$2.18M → +$0.08M** |
| **Preference multiple** | 1× → 3× | **+$0.61M → +$0.03M** |
| Exit regime | 0.5× → 2.5× | +$0.45M → +$1.91M |
| Bootstrapper growth ceiling | organic 1.8 → 3.4 | +$0.18M → +$0.65M |
| Carve-out (payoff shape) | 0% → 20% | +$0.61M → +$0.73M |
| Speed premium (market decay) | 0 → 30%/yr | +$0.62M → +$0.38M |
| Market tail | σ 1.2 → 2.4 | +$0.61M → +$0.47M |
| Capital execution upside | 0 → 0.80 | +$0.57M → +$0.80M |
| Secondary availability | none → generous | +$0.57M → +$0.65M |
| Founder patience | quit after 2y → 6y | +$0.25M → +$0.76M |
| Opportunity cost | $150k → $400k | +$0.56M → +$0.68M |

Three of these are large enough to matter more than the headline:

**The theory of investors is the biggest single lever.** Making the funding gate
noisier — closer to how investors actually behave — multiplies the venture
advantage nearly ninefold. Noise hands marginal companies a free option: a
salary and a lottery ticket whose downside is already zero. The frozen config
sits at σ=0.21, near the conservative end, so the headline is not being flattered
by this. But no conclusion here is robust to how investors are modelled, and the
PRD flagged exactly this (§8).

**How much being lean hurts nearly determines the answer.** Understaffing is the
main channel through which capital buys quality. Turn it off and venture wins by
$2.18M; turn it up and the advantage vanishes to $0.08M. This is a parameter
nobody has measured and it is doing most of the work.

**Opportunity cost is not where the bootstrapper's story lives.** Sweeping it
from $150k to $400k moves both arms together and changes the gap by less than
$0.12M. It changes the *level* enormously — at $150k the median bootstrapper is
finally positive — but not the comparison.

## 7. Did the incentive-evolution results survive translation?

PRD §2 carried three results over from the basketball simulation and asked
whether they hold in a domain where the threshold is written into a contract
rather than a rulebook.

**1. "A threshold reward buys volatility, not capability." Survived.** The
preference stack is a threshold on founder payoff, and it behaves like one.
Adding it takes the share of founders who receive nothing for their equity from
0% (bootstrap, no stack) to 52% (standard venture) and 60% (maximum venture),
while simultaneously stretching the top of the distribution from a $3.7M P99 to
$276M. More variance, and — per §3 — a median that capital structure makes
worse, not better, than the same cash on neutral terms.

**2. "Height drives volatility; all-or-nothing shape drives capability
collapse." Did not survive, and came closer to reversing.** Here the height of
the bar is the preference multiple and its shape is the management carve-out that
turns the step into a ramp. For standard venture, raising the height from 1x to
3x destroys 95% of the venture advantage (+$0.61M -> +$0.03M), while flattening
the shape with a 20% carve-out adds only 20% (+$0.61M -> +$0.73M). For maximum
venture the two are comparable: height -83% (+$2.32M -> +$0.40M), shape +97%
(+$2.32M -> +$4.56M).

So in this domain **height dominates**, and it dominates most for the founders
who raised least. That is a clean negative and it is worth more than a
confirmation would have been: the v1.0 finding was about a population evolving
its strategy against a bar, and nothing here evolves. Which leads to —

**3. "Populations refuse a high bar unless capital makes it pay, then convert
wholesale." Untested.** This model has no adaptation in it at all: the five
strategies are fixed and assigned, not chosen, learned, or selected for. Testing
it would need founders who observe outcomes and update — a different model, and
the obvious next one to build.

## 8. The small-cap world: same machinery, opposite answer

Everything above describes the headline venture ladder — rounds up to $150M on a
$1.2B pre-money, exits into the hundreds of millions. That is not the world most
founders are in, and it is not the world this project cares about most. So the
model was re-grounded on published 2025-26 figures and re-run.

### What the real numbers say

**Rounds** (2025-26 medians):

| | Round | Post-money | Dilution |
|---|---|---|---|
| Pre-seed | $1.0M | $4-6M | 15-20% |
| Seed | $3.2M (Carta) | $12-15M | 19-25% |
| Series A | $10-15M | $40-55M | 18-22% |
| Series B | $30-40M | $120-160M | 20-25% |

**Exits.** Over 80% of US tech startups are acquired for under $50M. The median
*disclosed* exit is $71M, but disclosure is exactly the bias: in most small deals
the buyer never says what they paid.

**The low end, where most companies actually sell.** Published venture statistics
see nothing below about $10M, so the numbers have to come from the people who
broker those deals. IBBA / M&A Source Market Pulse, Q3 2025 medians:

| Business value | Multiple | Of what |
|---|---|---|
| < $500K | **2.0x** | seller's discretionary earnings |
| $500K - $1M | **2.5x** | " |
| $1M - $2M | **3.0x** | " |
| $2M - $5M | **4.0x** | EBITDA |
| $5M - $50M | **6.5x** | EBITDA |

Two things in that table matter more than the numbers:

1. **The multiple climbs steeply with size, because the buyer pool does.** A
   business earning $200k is bought by a person; one earning $8M is bought by an
   institution. Same business, three times the multiple.
2. **The break at $2M is a change of convention, not a smooth curve.** Below it
   the market quotes *seller's discretionary earnings* — profit with the owner's
   salary added back, because the buyer is purchasing the owner's job along with
   the business. Above it, the buyer will hire a manager and does not add it back.

Acquire.com's marketplace data agrees on the mechanism: bootstrapped SaaS sold at
a median **3.9x TTM profit** in both 2024 and 2025, and the market there "has
decisively shifted from revenue-based to profit-based valuations for bootstrapped
startups under $10M in enterprise value". Deals close in about 81 days.

**Graduation.** Seed to Series A: 30.6% for the 2018 cohort, ~15% for 2022, and
slower — 39% now take 3+ years against 19% in 2019. Of 4,369 US startups founded
in 2018, 61.9% have closed.

Sources in §14.

### What changed in the model

Four things. The second and third were errors, not re-parameterisations:

1. **Series C and D deleted.** Not reachable for these companies, and leaving
   them in was the largest single piece of fantasy in the headline configuration.
2. **The exit multiple now scales with company size.** The original model paid a
   $2M-ARR business the same multiple as a $30M-ARR business at the same growth
   rate.
3. **The earnings multiple is a ladder, not a constant**, and the
   seller's-discretionary convention applies below $2M — the founder's own salary
   is added back, because that is what the quoted multiples are quoted on. The
   model previously used one flat 6x EBITDA at every size, which overpriced the
   smallest companies and underpriced the largest.
4. **Markets shrunk** so revenue tops out where it really does.

`configs/smallcap.yaml`, hash `e9c960d0ef5d76f7`. **Six of seven targets hit** —
the best fit this model has achieved in either world: a median exit of $10.3M
against a $10M target, 8.8% clearing $50M, seed-to-A at 23.6%, an exit over $10M
arriving at year 8 exactly, bootstrapped five-year survival at 60.9%. Revenue
tops out at $29.8M rather than $50M, which is the one miss and is conservative.

Worth noting which target that fixed. `< 1x capital` had missed in *every*
previous calibration, in both worlds, by the same 20 points. Adding the earnings
ladder fixed it without being aimed at it. Overpricing small companies was what
had been making too many of them look like they returned their investors' money.

### The result flips

Median paired difference against bootstrapping the same idea, same founder, same
luck:

| Strategy | Headline world | **Small-cap world** |
|---|---|---|
| Standard venture — total | +$0.59M | **+$0.10M** |
| Standard venture — ownership | −$0.02M | **−$0.03M** |
| Maximum venture — total | +$2.27M | **−$0.03M** |
| Maximum venture — ownership | +$1.39M | **−$0.08M** |

And the levels:

| Strategy | Median net | Ownership (median) | Equity paid nothing | Raised | Median exit |
|---|---|---|---|---|---|
| Bootstrap | −$0.46M | **$0.61M** | **0.0%** | $0 | $1.68M |
| Friends & family | −$0.63M | $0.45M | 30.0% | ~$1M | — |
| Seed and stop | −$0.89M | $0.27M | 92.5% | ~$3M | — |
| Standard venture | −$0.28M | **$0.00M** | 58.7% | $9.5M | $2.51M |
| Maximum venture | −$0.16M | $0.16M | **75.6%** | $29.7M | $1.84M |

**No venture strategy beats bootstrapping on ownership in this world.** Every
ownership gap is negative. The median standard-venture founder's shares return
**exactly zero**, because more than half of them get nothing at all.

Raising the largest round available stops paying entirely: it was the best
strategy by a distance in the headline world, and here it is no better than never
raising. The mechanism is arithmetic and it is the PRD's own example — maximum
venture raises **$29.7M on average into a world where its median company exits at
$1.84M.** The stack swamps the outcome. Standard venture raises a third as much
and does better on almost every measure.

Two things did not change between the worlds. Bootstrapped founders are paid
something for their equity **100%** of the time, and standard venture's ownership
gap is about −$0.03M in both: whatever the ladder looks like, the shares are not
where the median venture founder's money is.

### The practical reading

If your companies top out near $50M of revenue and a realistic exit is $10M, this
model says the amount to raise has an optimum and it is low. Raising enough to
buy a salary and some runway is marginally better than bootstrapping, and it is
better *only* as salary. Raising everything on offer is worse than bootstrapping,
because you cannot grow into a preference stack that a small exit market will
never clear.

### A defect this exposed in the headline configuration

Refitting the headline world after the valuation change produced **byte-identical
parameters**, which is the wrong kind of stable. The reason is that its revenue
multiple is size-blind (`scale_premium = 0`), so a $0.7M-ARR business is still
priced at 3.5x revenue and the earnings ladder never binds for it. The headline
configuration therefore continues to overprice small outcomes, and the small-cap
configuration is the more trustworthy of the two.

The direction matters: overpricing small exits flatters the venture arms, which
are the arms that win in that world. Every headline-world number in §1-§6 should
be read as generous to venture, and the fix — fitting `scale_premium` in both
worlds — has not been run.

## 9. The second implementation agrees

METHOD §7 asks for two implementations, because the browser port of the sibling
simulation caught three defects the Python had carried for hours. The port is at
`web/engine.js` and `scripts/validate_js_engine.cjs` compares the two engines at
both frozen configurations.

They agree. Across 24,000 founders per world, the largest disagreement on any
headline statistic was **$58k on a $1.39M median** — well inside sampling noise,
and the structural invariants (a bootstrapper's equity is never cancelled;
raising more leaves the founder owning less; the ledger decomposes exactly) hold
in both. The tolerances are set at roughly four times the disagreement actually
observed, so a real divergence fails the check rather than passing quietly.

This is weaker evidence than a disagreement would have been informative. It rules
out transcription and arithmetic errors in the model as written; it cannot rule
out the model being wrong in the same way twice, since one engine was written
from the other. What it does buy is confidence that the interactive page and the
numbers above come from the same model.

The port also differs structurally in a way worth noting: the Python runs
vectorised across founders one arm at a time, while the JavaScript runs one
founder at a time through every arm. The common random numbers that make the fork
a clean counterfactual are therefore guaranteed by the loop structure in one and
by careful array reuse in the other — and they still agree, which is the specific
thing that would have broken had the pairing been wrong.

## 10. "Failed" means two different things, and the word was hiding it

A reader looking at the live page asked whether they had read the failure rate
correctly — 45.7% of bootstrapped companies. They had, and the number was
correct, but the label was doing far too much work. In the small-cap world:

| | Failed | …founder gave up | …ran out of money | Founder got nothing | Typical year | Sold for |
|---|---|---|---|---|---|---|
| Bootstrap | 45.7% | **45.7%** | 0.0% | **0.0%** | year 4 | $111k |
| Friends & family | 6.4% | 6.4% | 0.0% | **6.4%** | year 4 | $161k |
| Standard venture | 37.4% | 2.1% | **35.3%** | 36.5% | year 10 | $0 |
| Maximum venture | 29.9% | 1.4% | **28.6%** | 29.0% | year 10 | $0 |

Bootstrapped companies do not run out of money — there is no burn to run out of.
They end when the founder gives up, typically in year 4, and they are almost
always **sold**, for a median of $111k that the founder keeps in full. Venture
companies end by exhausting their capital around year 10, and 97% of those
founders receive nothing.

The friends & family row is the sharpest illustration of the whole model. Those
companies fail rarely, and sell for *more* than the bootstrapped ones — $161k
against $111k — and yet **every one of those founders receives nothing**, because
a $1M preference sits in front of a $161k sale. A better business, a better
price, and a worse outcome for the person who built it.

The table on the live page now splits these rather than summing them under one
word.

### Two things this exposed that are not fixed

**Bootstrapped failures cluster at exactly the give-up parameter.** The median is
year 4 because `abandon_years` is 4: any founder starving from year 0 quits at
the first moment the rule allows, so the *timing* of bootstrapped failure is set
by a parameter rather than emerging from the business. The level is calibrated
(five-year survival 60.9% against a 60% target) but the shape is not.

**The failure rate hinges on two constants sitting either side of a threshold.**
A bootstrapper who cannot pay themselves draws the salary floor, $40k. A founder
who raised a pre-seed draws that stage's salary, $80k. The give-up rule fires
below $60k. So 45.7% versus 6.4% is, mechanically, $40k being under $60k and $80k
being over it. All three numbers are model choices, and the middle one is swept —
but a reader should know that this particular contrast is more fragile than the
ownership results, which survive every sweep in §6.

## 11. Retractions and exposures

Kept on the record, per METHOD §10.

### The counterfactual was run once before the model was fixed. That run is withdrawn.

A first counterfactual was run, inspected, and then a defect was found in it: the
two arms used **structurally different founder-salary policies**. Bootstrappers
took a share of profit (which collapsed to the $40k floor for almost everyone,
because the formula deducted staff the company never hired), while anyone who had
raised took their stage's salary. The abandonment rule then read that policy
difference as failure: **identical businesses failed at 79% or at 3% depending
only on which policy applied to them.**

The fix was to give every arm one salary policy — a market rate that scales with
the business, with the guarantee of a stage salary being the genuine thing
investor cash buys. Bootstrap failure fell from 79% to 44%. Calibration was
re-run from scratch and every number above comes from after the fix.

This is a METHOD §4 violation and it is recorded as one: **the defect was found
by looking at counterfactual output.** In mitigation, the change removes an
arm-asymmetric artefact rather than tuning a parameter, and it moves the result
*against* the hypothesis being tested — it made bootstrapping look better, and
the hypothesis was that bootstrapping wins. But a reader should discount
accordingly, and the right way to close this out is a fresh confirmatory run
under a seed and a target set fixed in advance.

### One calibration target is still missed

| Target | Want | Got | |
|---|---|---|---|
| VC-backed reaching $1B+ | 1.0% | 0.43% | ok (within tolerance) |
| VC-backed reaching $100M+ | 10% | 13.4% | ok |
| Seed → Series A graduation | 22% | 28.8% | ok |
| **Returning < 1× capital** | **70%** | **49.7%** | **missed** |
| Time to a real exit | 8 yrs | 6.7 yrs | ok |
| Bootstrapped 5-year survival | 60% | 71.6% | ok |

The model produces too few companies that return less than the capital they
raised. The direction of that bias matters: it makes venture-backed outcomes
look *better* than they are, which flatters the funded arm — the arm that won.
The headline result is therefore, if anything, understated in favour of
bootstrapping. It should still be treated as an open defect rather than a
comfort.

Also unmodelled and uncalibrated: pre-seed → seed graduation comes out at 96%,
against a real figure closer to 30–40%. The model lets almost everyone raise a
seed, so the "venture" arms include founders who in reality would never have
been funded. This inflates the pool over which the venture advantage is measured.

### Several fitted parameters railed against their search bounds

`growth_scale`, `effort_scale`, `exec_sigma`, `funded_spend_rate` and
`market_sigma` all landed on a bound. `market_sigma` hit the *top* of the range
in one search and the *bottom* in another with a similar score, which says the
calibration targets do not identify it. Any claim that depends on the market
size distribution should be treated as unresolved — which is one more reason to
read §5's flat market-size curve carefully.

## 12. What is not modelled

Beyond the PRD §8 list, which stands:

- **One founder, no co-founders**, so no founder-vs-founder dilution or conflict.
- **No follow-on founders.** A failed founder in this model goes back to a job;
  in reality they often start again, and venture failure buys a second at-bat
  that bootstrapped failure does not.
- **No debt, no revenue-based financing, no bootstrapping-then-raising**, which
  is what a great many real founders actually do.
- **Taxes are two flat rates.** QSBS alone would move the funded arm materially.
- **Distributions come out thinner than the PRD expects.** The design doc has
  them "real and recurring once profitable" for a bootstrapper; the model
  delivers a median present value of $0.04M, because a company only pays out
  once it is profitable, past its cash reserve, and out of the range of further
  rounds. Since distributions are ownership income, this understates the
  bootstrapper's ownership return — the side that already won in §2.
- **The horizon is a wall.** Companies still growing at year 12 are marked at a
  30% illiquidity discount and stopped. Venture outcomes have longer tails than
  that, so the top of the funded distribution is cut off.

## 13. What would change the answer

Stated in advance of the next run, so it cannot be chosen afterwards:

1. Fixing the `< 1× capital` miss should shrink the venture advantage. If it
   shrinks past zero, §1 flips.
2. Modelling realistic seed graduation (30–40%, not 96%) removes the weakest
   founders from the venture arms, which should *increase* the measured venture
   advantage while making it apply to far fewer people.
3. If the understaffing penalty is genuinely nearer 0.5 than 0.25, the venture
   advantage is inside the noise.
4. A richer distribution policy would raise the bootstrapper's ownership return
   and push the standard-venture ownership gap in §2 further negative. The
   sweeps do not currently cover it, and they should.


---

## 14. Sources for the real-world figures

Round sizes, valuations and dilution:

- [Carta, State of Private Markets Q1 2025](https://carta.com/data/state-of-private-markets-q1-2025/)
- [Carta, State of Pre-Seed 2025](https://carta.com/data/state-of-pre-seed-2025/)
- [Average pre-seed, seed & Series A round sizes: 2026 medians](https://valueaddvc.com/blog/startup-funding-rounds-in-2025-whats-normal-at-pre-seed-seed-a-and-b)
- [Seed valuations 2026, on Carta data](https://www.flowjam.com/blog/seed-round-valuation-2025-complete-founders-guide)

The low end of the market (below ~$10M, where published venture data sees nothing):

- [IBBA / M&A Source Market Pulse, Q3 2025 highlights](https://www.ibba.org/wp-content/uploads/2025/11/market-pulse-highlights-q3-2025.pdf) — median multiples by deal-size band, SDE below $2M and EBITDA above
- [IBBA / M&A Source Market Pulse Q3 2025 survey results](https://www.prnewswire.com/news-releases/the-ibba-and-ma-source-announce-the-results-of-the-market-pulse-q3-2025-survey-302617915.html)
- [Acquire.com biannual acquisition multiples report, Jan 2026](https://blog.acquire.com/acquire-com-biannual-acquisition-multiples-report-jan-2026/) — bootstrapped SaaS at a median 3.9x TTM profit, 2024 and 2025
- [Acquire.com acquisition multiples report, 2025 findings](https://blog.acquire.com/acquisition-multiples-report-2025-findings-webinar-recap/)

Exit sizes and multiples:

- [SaaS ARR multiples 2026 by band](https://saasvaluationmultiple.com/arr-multiples)
- [SaaS valuation multiples 2015-2026, Aventis Advisors](https://aventis-advisors.com/saas-valuation-multiples/)
- [SaaS multiples: the real private range](https://www.l40.com/insights/saas-multiples)
- [Startup exit statistics, 2026](https://www.zabella.net/blog/startup-exit-statistics)
- [How much do startups sell for? — They Got Acquired](https://theygotacquired.com/resources/how-much-do-startups-sell-for/)

Graduation and failure rates:

- [Carta, graduation rate from seed to Series A](https://carta.com/data/newsletter-graduation-rate-from-seed-to-series-a/)
- [Update on venture graduation rates, Incisive Ventures](https://incisive.vc/2025/06/10/update-on-venture-graduation-rates/)
- [The Series A crunch, Chronograph](https://www.chronograph.pe/current-trends-in-the-series-a-and-seed-venture-markets/)

A caution that applies to all of the exit figures: small acquisitions are
systematically under-reported, because buyers rarely disclose what they paid.
Every published median is therefore biased upward, and calibrating to it imports
that bias — the same problem PRD §8 flags for survivorship.
