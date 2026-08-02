# Raising the Bar Does Not Raise the Standard

### How a success threshold reallocates capability into variance in an evolving population

*Computational appendix to* Freedom Startups

---

## Abstract

We ask whether changing the definition of success changes the kind of competitor
a population evolves into. Two leagues of 64 teams are seeded from
byte-identical populations and play an identical game under identical physics.
They differ in exactly one respect: League A rewards any win; League B rewards
only wins by 10 points or more. Both populations then evolve for 600 seasons
under the same selection machinery.

The populations diverge on 9 of 11 measured traits. League B evolves markedly
more volatile competitors — aggression +0.156, margin volatility +2.10 points,
blowout rate +7.8 points. It does **not** evolve stronger ones: both its
offensive and defensive skill end up *lower* than League A's, and against a
common opponent its expected margin is −0.53 points against League A's +0.01.
The volatility effects are large relative to a drift null control (t = 4.8–6.0);
the skill degradation is real but marginal (t = 2.0–2.4) and, as a price-of-
volatility sweep shows, holds only where volatility is cheap.

The trade is not merely lateral but unfavourable. League B gains 0.89 percentage
points at winning by 10+ while giving up 3.42 points at losing by 10+; the
downside tail grows faster than the upside tail at every threshold. In a neutral
bracket League B takes 42.5% of championships, and its per-game win rate decays
from 48.4% to 44.0% across a six-round tournament run as accumulated fatigue
compounds against its high-aggression strategy.

Yet the high-bar population is not simply worse. In a combined league its
lineages take over 74.4% of the time when the league grades on a high bar. What
selection produces is not a better competitor or a worse one, but one *shaped to
a particular bar* — and that shape is invisible from inside a system that scores
only the thing it optimises for.

---

## 1. Introduction

A common intuition in organisational design holds that raising the bar raises the
standard: demand more, and you will get better performers. This paper tests that
intuition in a setting where it can be measured exactly.

The claim is difficult to test in the field because the counterfactual is
unavailable — we cannot observe the same firms, athletes, or founders raised
under a different definition of success. Simulation makes the counterfactual
cheap: we can instantiate two populations that are identical in every respect,
change one term in the reward function, and watch.

The mechanism we expect is a straightforward consequence of thresholding a
random outcome. If a competitor's margin over an opponent is approximately
`Normal(μ, σ)`, then

- reward for any win is `P(margin > 0) = Φ(μ/σ)`, which for `μ > 0` is
  **decreasing in σ**, and
- reward for a win by `k` or more is `P(margin ≥ k) = Φ((μ − k)/σ)`, which for
  `μ < k` is **increasing in σ**.

A competitor whose expected margin falls short of the bar improves its odds by
becoming *less* predictable, not by becoming better. Where raising μ is slow and
constrained and raising σ is cheap, we should expect a high-threshold population
to buy variance.

The contribution here is not the observation that thresholds induce risk-seeking,
which is well understood. It is (i) that the effect survives being made
*evolutionary* rather than merely strategic — no agent reasons about the
threshold, and selection alone finds the volatility route; (ii) that the
resulting population is measurably *worse* at the underlying activity — though
only where volatility is cheaper than skill, which we establish by sweeping that
price; and (iii) that the comparison "which league is better" is shown to be
ill-posed, with a rule-independent replacement offered in its place.

We also report two effects that we initially took to be findings and that a drift
null control subsequently withdrew, on the view that a paper of this kind is more
useful with its retractions visible than with them quietly absent.

---

## 2. Model

### 2.1 Teams

Each team carries five **attributes**, fixed for its lifetime, and six
**strategy** parameters that adapt within its lifetime. All lie in `[0, 1]`.

| Attributes | Strategy |
|---|---|
| offense, defense, risk capacity, adaptability, stamina | aggression, offensive emphasis, defensive emphasis, tempo, margin seeking, endgame conservatism |

Attributes are subject to a hard **budget**: they must sum to 2.5. Without this
constraint every attribute drifts to its maximum and the population has nothing
to trade. With it, evolution must *allocate*, which is what makes "did League B
give up skill to buy risk capacity?" an answerable question.

### 2.2 Match engine

Games are simulated possession by possession so that end-of-game behaviour is
expressible. For a team attacking with per-possession mean `μ` and variance `v`:

```
possessions   P  = 60 + 40 · mean(tempo_i, tempo_j)
per-poss mean μ_i = 1.05 · (1 + 0.55 · (off_i·off_emph_i − def_j·def_emph_j))
                        · (1 − κ · max(0, aggression_i − risk_capacity_i)²)
per-poss var  v_i = 0.65 · (1 + 2.2 · aggression_i)
```

Three levers act on the mean–variance frontier in deliberately non-aligned ways,
so that no single strategy dominates:

- **Aggression** always raises variance. It costs efficiency only above the
  team's risk capacity, quadratically, at price `κ` (baseline 0.9). This is the
  variance purchase, and `κ` is its price.
- **Tempo** raises the possession count. Total mean grows `∝ P` while total
  standard deviation grows `∝ √P`, so higher tempo *reduces relative* variance
  while *increasing absolute* margins.
- **Endgame conservatism** and **margin seeking** act on a leading team in the
  final segment, damping or inflating variance respectively.

**Fatigue** accumulates across a tournament run, amplified by aggression and
damped by the stamina attribute. It applies only inside the bracket.

Critically, the match engine is **reward-blind**. A test tokenises its source and
asserts that its executable code never references a threshold, a reward, or a
league. Any divergence we observe is selection acting on strategy, not a rule
written into the physics.

### 2.3 Reward — the only difference

```python
reward = 1.0 if margin >= threshold else 0.0
```

League A uses `threshold = 1`; League B uses `threshold = 10`. This single
integer is the entire experimental manipulation.

### 2.4 Season structure

Each season runs a 12-game regular season in which every team plays an equal
number of games, then seeds a 64-team single-elimination bracket by each league's
own success metric.

The regular season exists to remove a confound. In a pure knockout the champion
plays six games and half the field plays one, so winners would accumulate far
more learning signal than losers and "the winners learned more" would compete
with the reward function as an explanation for any divergence.

### 2.5 Learning and selection

Two channels operate:

- **Within-lifetime (fast).** Each team runs a (1+1) evolution strategy on its
  strategy vector, alternating between evaluating its incumbent and a mutated
  candidate over 150-game windows.
- **Across generations (slow).** Between seasons the bottom 20% of teams are
  replaced by mutated offspring of the top 20%, inheriting both attributes and
  strategy, with attributes renormalised to the budget.

The fast channel is deliberately modest, and we sized it against a measurement
rather than a guess. A direct probe of the engine (§3.1) shows the reward edge
from buying variance is roughly 3 percentage points, requiring ~1,900 games per
arm for a 2σ read. No practical per-team window reaches that. **Population
selection is therefore the primary driver**: a 3-point edge is invisible to one
team but is a selection coefficient of s ≈ 0.08 across 64 teams, which is strong
and compounds over hundreds of seasons.

---

## 3. Methods

### 3.1 Pre-registered mechanism check

Before any learning code existed, we verified the engine could express the
mechanism at all. Holding a moderate favourite at +1.9 expected margin and
sweeping its aggression from 0.05 to 0.85 with variance free of charge:

| aggression | mean margin | margin sd | P(m≥1) | P(m≥5) |
|---|---|---|---|---|
| 0.05 | +1.90 | 10.21 | 0.5745 | 0.3967 |
| 0.45 | +1.87 | 12.20 | 0.5634 | 0.4157 |
| 0.85 | +1.93 | 13.84 | **0.5585** | **0.4284** |

Buying variance moves the two reward functions in opposite directions
(−1.6 points at threshold 1, +3.2 points at threshold 5) with the expected margin
held flat. The mechanism is present in the physics before any agent adapts.

### 3.2 Identical starting conditions

All randomness derives from a single root seed via `SeedSequence.spawn`. The
initial-population seed depends on the replicate only, **not** on the league, so
at `t = 0` the two leagues hold byte-identical arrays rather than merely
same-distribution draws. Statements of the form "the reward function is the only
difference" are therefore literal.

### 3.3 Statistics

We report 16 independent replicates. Because both leagues share a starting
population within a replicate, we difference **within** replicate before
aggregating, which removes starting-population luck entirely. Confidence
intervals are 95% normal intervals on the paired difference over replicates.
Reported values are means over the final 30 seasons.

### 3.4 Comparing populations without picking a winner's yardstick

"Which league is better?" cannot be answered directly, because every candidate
yardstick is one of the leagues' home rules. Judged by win rate League A wins by
construction; judged by blowout rate League B does.

A direct League A vs League B match also cannot answer it: the contest is
zero-sum, so the margin distribution is symmetric and both populations clear any
bar equally often by construction.

Our replacement is to sweep the entire threshold range against a **common third
opponent** (the evolved League A population), reporting `P(margin ≥ k)` for every
`k`. The output is a curve rather than a verdict, and the location where it
crosses zero is the substantive result.

---

## 4. Results

### 4.1 The populations diverge

Nine of eleven measured traits differ significantly. Paired by replicate:

A confidence interval excluding zero only establishes that the two populations
ended up different. It does not establish that the *reward function* caused it,
because identically rewarded populations also drift apart. We therefore test each
effect against the null control of §5.1 (Welch's t on the per-replicate
differences), and report that as the decisive column.

| Measure | League A | League B | Difference | vs. zero | vs. drift (t) |
|---|---|---|---|---|---|
| Aggression | 0.0865 | 0.2422 | **+0.1557** | yes | **6.02 — survives** |
| Margin volatility | 11.237 | 13.339 | **+2.102** | yes | **5.03 — survives** |
| Close-game rate | 24.16% | 20.17% | **−3.99pp** | yes | **5.11 — survives** |
| Blowout rate | 38.94% | 46.77% | **+7.83pp** | yes | **4.81 — survives** |
| Strategy diversity | 0.0700 | 0.0907 | **+0.0206** | yes | **2.96 — survives** |
| Defensive skill | 0.9327 | 0.9294 | −0.0034 | yes | 2.35 — survives, marginally |
| Offensive skill | 0.9339 | 0.9302 | −0.0037 | yes | 2.05 — survives, marginally |
| Risk capacity | 0.2148 | 0.2930 | +0.0782 | yes | 1.66 — **not distinguishable from drift** |
| Tempo | 0.5439 | 0.7348 | +0.1910 | yes | 1.10 — **not distinguishable from drift** |
| Endgame conservatism | 0.3176 | 0.3131 | −0.0045 | no | — |
| Upset rate | 46.34% | 46.94% | +0.60pp | no | — |

Seven of nine effects survive. Two do not, and we flag them explicitly because
both looked like findings on the naive test:

- **Tempo** (+0.19, CI excluding zero) is not distinguishable from drift
  (t = 1.10). We had initially read this as an emergent discovery — that a league
  facing an *absolute* points bar learns to lengthen games, since more possessions
  scale absolute margins faster than their spread. The mechanism is real in the
  engine, but the population-level effect is not separable from noise at this
  sample size. It is withdrawn.
- **Risk capacity** (+0.078) likewise does not survive (t = 1.66), which
  withdraws the tidier story that League B financed its volatility by
  reallocating attribute budget into risk capacity.

What remains is unambiguous and large: League B became **markedly more volatile**
and **slightly less capable**, with the volatility effects roughly twice the
t-statistic of the capability effects.

### 4.2 The effect scales with the bar

Raising League B's threshold from 5 to 10 amplifies every effect, which is the
strongest available evidence that the mechanism is real rather than incidental:

| Measure | thr 5 (B−A) | thr 10 (B−A) |
|---|---|---|
| Aggression | +0.048 | **+0.156** |
| Risk capacity | +0.036 (ns) | **+0.078 (sig)** |
| Margin volatility | +1.13 | **+2.10** |
| Blowout rate | +4.6pp | **+7.8pp** |
| Offensive skill | −0.0028 | **−0.0037** |
| Defensive skill | −0.0013 (ns) | **−0.0034 (sig)** |

At threshold 5 only offensive skill is significantly degraded; at threshold 10
both attributes are. The harder the bar, the more real capability is traded away.

### 4.2b Retracted: an early-lead effect that does not survive its own error bars

An earlier version of this paper reported that League B improves *faster* for the
first hundred seasons — offensive skill peaking at +0.042 over League A around
season 25 — and explained it by truncation selection. **That claim is withdrawn.**

The means do trace that shape, but the per-replicate spread swamps it:

| Season | Mean gap (B−A) | SD | 95% CI |
|---|---|---|---|
| 5 | +0.0216 | 0.061 | [−0.008, +0.051] |
| 25 | +0.0423 | 0.184 | [−0.048, +0.132] |
| 50 | +0.0157 | 0.170 | [−0.068, +0.099] |
| 100 | +0.0008 | 0.104 | [−0.050, +0.051] |

Not significant at any season. Early trajectories are far noisier than converged
ones — the spread at season 25 is three times the converged spread — so a mean
curve computed over 16 replicates traces a shape that individual runs do not
share. A faithful reimplementation of the model in JavaScript fails to reproduce
the effect across three independent seed families, which is what prompted the
check.

Testing the hypothesis properly would need roughly 150 replicates to bring the
interval below the effect size. We have not run that, so the question is open
rather than answered. We record the episode because it is the same error the
null control in §5.1 was built to catch, committed by the same authors one
section later: **a mean curve is not a finding until its spread is examined.**

---

### 4.3 The trade is unfavourable, not merely lateral

Against a common opponent, 1.92M games per population:

| | A-bred | B-bred | Difference |
|---|---|---|---|
| Expected margin | +0.006 | **−0.526** | −0.532 |
| P(win) | 50.01% | 48.34% | −1.67pp |
| P(win by 5+) | 34.35% | 34.16% | −0.19pp |
| P(win by 10+) | 19.55% | 20.44% | **+0.89pp** |
| P(lose by 5+) | 34.30% | 37.29% | **+2.98pp** |
| P(lose by 10+) | 19.50% | 22.92% | **+3.42pp** |

League B is ahead at exactly one thing — clearing the bar it was selected on —
and the downside tail grows roughly four times faster than the upside tail. The
survival curves cross at **+6 points**: below that bar A-bred teams are better,
above it B-bred teams are.

This crossing is the honest answer to "which league is better." It is a location,
not a verdict.

### 4.4 Volatility does not democratise outcomes

A natural expectation is that a more volatile league produces more upsets and
more varied champions. It does not: upset rate +0.60pp (ns) and mean champion
seed +1.67 (ns).

The reason is that volatility rose *population-wide*. When every competitor
becomes noisier together, relative ordering survives. Variance only redistributes
outcomes when it is asymmetric — underdogs volatile, favourites steady. An arms
race in risk-taking adds noise without changing who wins.

### 4.5 The volatile league wins games but loses tournaments

In a neutral 64-team bracket seeded and scored under plain win/loss, League A
takes **57.5%** of championships against League B's 42.5% (95% CI on B's share
38.7–46.3%). Yet the per-game gap is much smaller (51.7% / 48.3% over 640,000
games).

A championship requires six consecutive wins, and the discrepancy is fatigue.
League B evolved high aggression, and aggression amplifies the fatigue cost.
(Our initial account also credited a budget shift out of stamina and into risk
capacity; neither attribute effect survives the null control, so the attribution
rests on aggression alone, which does.) Measured directly with both sides equally
rested at each depth:

| Bracket round | Fresh | R32 | Sweet 16 | Elite 8 | Final 4 | Final |
|---|---|---|---|---|---|---|
| B win rate | 48.4% | 47.6% | 46.8% | 45.7% | 45.0% | **44.0%** |

The high-variance strategy cannot sustain a long campaign. No part of the model
was designed to produce this; it falls out of the attribute budget interacting
with fatigue.

### 4.6 Selection still favours the specialist — in worlds with a high bar

We seeded combined leagues with 32 teams from each upbringing and traced lineage
through reproduction to fixation (300 seasons, 80 trials per rule):

| Rule the combined league runs | B-bred takes over | Verdict |
|---|---|---|
| Bar 1 (League A's rule) | 41.9% ± 11.2% | dead heat |
| Bar 10 (League B's rule) | 74.4% ± 9.7% | B-bred take over |
| Bar redrawn each season, 1–10 | 72.7% ± 9.9% | B-bred take over |

Our pre-registered prediction — that the conservative upbringing would dominate
under an unpredictable bar — was **wrong**. What decides the shifting case is not
the uncertainty but the *average height* of the bars in the draw: sampling
uniformly from 1 to 10 places nine of ten worlds at a high bar. Narrowing that
range toward 1 would reverse the result. We record this because the uniform range
was a design choice, not a discovery, and any claim resting on that row inherits
it.

The correct reading is that a population becomes good at the game it is graded
on, and if the world grades on that game it wins — while remaining objectively
weaker at the underlying activity.

### 4.7 The price of volatility — and the limit of the claim

The most serious objection to everything above is that our engine makes
volatility cheap: aggression buys variance for free below a team's risk capacity
and only costs efficiency above it, at price κ. "High bars make you buy variance"
could then be a restatement of "we made variance cheap."

We sweep κ from 0 (free at any level) to 3.6 (punishing), 600 seasons × 12
replicates each:

| κ | Aggression gap (B−A) | Offensive skill gap (B−A) | Margin volatility gap |
|---|---|---|---|
| 0.0 | +0.446 ± 0.182 | −0.0027 ± 0.0024 | +4.95 |
| 0.45 | +0.127 ± 0.071 | −0.0041 ± 0.0038 | +2.34 |
| 0.9 *(baseline)* | +0.147 ± 0.055 | −0.0032 ± 0.0015 | +2.23 |
| 1.8 | +0.092 ± 0.047 | −0.0017 ± 0.0023 | +2.19 |
| 3.6 | +0.055 ± 0.036 | −0.0013 ± 0.0028 | +1.82 |

Two things follow, and they cut in opposite directions.

**The volatility result is robust.** The aggression gap attenuates by roughly 8×
across the sweep but never reverses and never vanishes; the margin-volatility gap
remains large (+1.82 points) even where volatility is most expensive. A high bar
pushes a population toward variance at every price we tested.

**The skill result is not robust — it is conditional.** The offensive skill gap
shrinks toward zero as volatility gets expensive and is no longer distinguishable
from zero at κ ≥ 1.8. Notably it also never turns *positive*: expensive
volatility does not make the high-bar league genuinely better, it merely stops
making it worse.

The defensible claim is therefore narrower than "raising the bar makes you worse."
It is:

> **Raising the bar reliably makes a population more volatile. It makes the
> population worse at the underlying activity only when volatility is cheaper
> than skill.**

That conditional is not a weakness of the result; it is the operative variable.
It says where to look in any real system — not at the height of the bar, but at
the relative price of looking good versus being good.

---

## 5. Threats to validity

### 5.1 Drift (null control)

Some portion of any observed gap is drift and RNG-stream luck rather than
selection. We ran the identical machinery with the reward held *equal* in both
leagues — both at threshold 1, same seeds, same starting populations, differing
only in RNG stream — for 600 seasons × 16 replicates.

Identically rewarded populations do drift apart, and unevenly: the drift gap in
tempo has a 95% half-width of ±0.149 and in margin volatility ±0.435, while
offensive skill drifts only ±0.0014. One of nine measures (close-game rate)
showed a nominally significant "effect" from drift alone, which is unremarkable
at nine tests and α = 0.05.

This is why §4.1 reports effects against the drift distribution rather than
against zero, and why two effects that looked significant on the naive test are
withdrawn. We recommend the same discipline for any comparison of this kind: with
a high-variance trait and 16 replicates, a CI excluding zero is weak evidence.

### 5.2 The price of volatility is a modelling choice

In our engine, aggression buys variance for free below a team's risk capacity and
only costs efficiency above it. §4.7 sweeps that price directly and resolves the
objection *partially*: the volatility effect survives at every price, but the
skill-degradation effect does not. We therefore state the skill claim
conditionally throughout, and treat the relative price of volatility versus skill
as the governing parameter rather than an incidental one.

### 5.3 Skill saturates

Offensive and defensive skill both sit near their ceiling (≈0.93 of a 0.95
maximum) in both leagues, compressed by the attribute budget. The skill
differences we report are therefore small in absolute terms — statistically
robust, but operating in a narrow band. A design with more headroom in skill
would give the "get genuinely better" route more room to compete.

### 5.4 One game, not the world

The match engine is a stylised contest, not a model of any real sport, market, or
firm. The claim transfers only insofar as the target domain shares the structural
features: a thresholded reward, a mean–variance frontier, a constrained
capability budget, and selection over repeated trials.

### 5.5 A measurement error worth recording

Our first head-to-head statistic sampled 1,024 direct games and reported a 52%
edge for League B — the opposite sign of the truth. At 640,000 games the same
statistic reads 48.3%. For an effect of ~2 percentage points, small-sample noise
is readily mistaken for a finding, and we flag it as a caution rather than
silently correcting it.

---

## 6. Discussion

The result contradicts the intuition that a higher bar produces better
performers, and it does so through a mechanism that requires no bad faith,
gaming, or misunderstanding on anyone's part. No agent in this simulation reasons
about the reward function. No team decides to sandbag or gamble. Selection alone,
operating on a population that simply reproduces what scores well, finds the
volatility route because the volatility route is cheaper than the skill route.

Three features of the outcome seem worth carrying into the organisational case.

**Capability is reallocated, not created.** Under a constrained budget, a
population cannot simply become better at everything. The high-bar league ended
up slightly worse at both offense and defense while becoming much more volatile.
We cannot say cleanly *which* attribute financed the volatility — the tidy story
that it bought risk capacity did not survive the null control — but the
directional trade is there, and it is only visible because the budget forbids
improving at everything at once. Any organisation with finite attention faces the
same constraint, and raising a bar does not relax it.

**The costs land where the metric cannot see them.** League B's degradation shows
up in blowout losses, in close-game frequency, and in an inability to sustain a
six-round run — none of which its own reward function measures. A system that
scores only the thing it optimises for will not register the bill.

**The specialisation is invisible from inside.** League B's teams are not failing
by their own lights; they are succeeding, and their peers are succeeding the same
way. Nothing in their experience signals that they have become worse at the
underlying activity, because nothing they are graded on measures it.

### The founder case, stated precisely

The translation to founders is more specific than a general warning about
incentives, and it turns on one observation: **a funding round is a variance
purchase.**

Consider two things a company can do. Signing a first customer is a *mean*
improvement — it raises the expected outcome, modestly and reliably. Raising a
large round is a *variance* purchase — it takes capital and spends it to widen
the distribution of outcomes: a bigger burn, a bigger swing, a higher probability
of both zero and something enormous. It does not, by itself, make the company
better at anything.

Now apply §1. If the ecosystem scores outcomes above a high bar — a very large
exit, not a good business — then a competitor whose expected outcome falls short
of that bar improves its odds by raising σ, not μ. Under `P(outcome ≥ k)` with
`μ < k`, the variance purchase is worth more than the mean improvement.

So celebrating the round over the first deal is not vanity and not irrationality.
**It is correct play for the game being scored.** That is what makes it hard to
argue anyone out of, and it is why the behaviour persists among sophisticated
people who can all do the arithmetic.

The model then says what that choice costs, and each item is measured rather than
asserted:

- **You do not get better at the underlying activity.** Both capability measures
  came out slightly *lower* in the high-bar population (§4.1).
- **The downside grows faster than the upside.** +0.89 points of blowout wins
  against +3.42 points of blowout losses (§4.3). The tails are not symmetric, and
  the wrong one is fatter.
- **You lose the ability to sustain a long campaign.** Win rate decays 48.4% →
  44.0% across a six-round run (§4.5). In the founder frame this is the one that
  reads least like an analogy and most like a description.
- **The arms race does not even redistribute the winners.** Upset rate and
  champion seed were both unaffected (§4.4). When everyone raises variance
  together, relative ordering survives; the population simply becomes noisier for
  no change in who succeeds.

And §4.7 supplies the condition. Capability degrades only where volatility is
cheaper than skill — which, for a startup, is precisely when **capital is
abundant**. Cheap capital is cheap volatility. The regime in which chasing a high
bar actively erodes company-building capability is therefore a bull market, and
the mechanism predicts that the damage should be visible afterwards rather than
during.

We should be explicit that this mapping is an interpretation, not a simulated
result. The simulation ran a stylised contest, not a startup ecosystem. What
transfers is the structure — a thresholded reward, a mean–variance frontier, a
constrained capability budget, selection over repeated trials — and the reader
should judge the transfer on whether those four features are present, not on the
strength of the analogy.

A note on what we deliberately did *not* model. An earlier draft added a
purchasable "signal" — an activity that earns reward without contributing to
performance — to represent fundraising as a proxy metric. We discarded it. A
parameter whose only function is to be rewarded is a dial labelled *cheat*, and
demonstrating that populations pull it restates the definition of an incentive
rather than discovering anything. The variance account above requires no such
device: it explains the same behaviour using a mechanism that had to survive a
null control and a price sweep.

The claim is not that high bars are wrong. §4.6 shows the specialist wins in
worlds that grade on a high bar, and many worlds do. Nor is it that high bars
always degrade capability — §4.7 shows that holds only where volatility is
cheaper than skill. The claim is narrower and more uncomfortable:

> **The bar is doing the selecting. It does so whether or not anyone intends it,
> the bill arrives in currencies the bar does not measure, and from inside the
> system it is very hard to see.**

The practical corollary is a question worth asking of any incentive system before
adopting it: *in this environment, is looking successful cheaper than being
successful?* Where the answer is yes, a higher bar will buy volatility rather
than quality, and the system's own metrics will not report it.

---

## Figures

Generated into `figures/` by the commands in §7:

| File | Shows |
|---|---|
| `mechanism.png` | The reward gradient in the engine alone, before any learning (§3.1) |
| `payoff_curve.png` | Difference in games clearing each bar; the crossing at +6 (§4.3) |
| `fatigue_curve.png` | League B's win rate decaying across a tournament run (§4.5) |
| `invasion.png` | Lineage share over time in a combined league (§4.6) |
| `cost_sweep.png` | Aggression and skill gaps versus the price of volatility (§4.7) |
| `site-light.png` / `site-dark.png` | The interactive companion, full page |

An interactive version — scrubable seasons and a playable bracket — is built by
`scripts/build_site.py` into `web/index.html`.

---

## 7. Reproducibility

Every result derives from a single root seed. Runs are byte-identical on re-execution,
and each results directory carries a manifest recording the full configuration, its
hash, the git SHA, and library versions.

```bash
python -m incentive_sim.experiment --config configs/threshold10.yaml \
    --seasons 600 --replicates 16 --out results/threshold10
python scripts/head_to_head.py  results/threshold10
python scripts/payoff_curve.py  results/threshold10
python scripts/fatigue_curve.py results/threshold10
python scripts/invasion.py      results/threshold10
python scripts/cost_sweep.py
python scripts/null_control.py
python scripts/build_site.py    results/threshold10 web/index.html
```

The full design is ~8.6M simulated games per configuration and completes in about
three minutes on four cores. The engine sustains 92M games/minute in batched
form; a 60-test suite covers engine sanity, bracket correctness, budget
invariants, lineage bookkeeping, and reproducibility.

---

## Appendix: what the engine is not allowed to know

The strongest single guarantee in this design is negative. The following test
tokenises the match engine's source and fails if its executable code contains any
reference to a threshold, a reward, or a league:

```python
def test_engine_never_references_rewards_or_thresholds():
    forbidden = ("threshold", "reward", "league", "margin_target")
    for module in (match, population):
        code_tokens = [
            tok.string.lower()
            for tok in tokenize.generate_tokens(io.StringIO(source).readline)
            if tok.type not in (tokenize.COMMENT, tokenize.STRING, ...)
        ]
        ...
```

Comments and docstrings may discuss the design; the code may not act on it.
Without this guarantee, any divergence reported above would be an artefact we
built rather than a result we found.
