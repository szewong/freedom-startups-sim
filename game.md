# Product Requirements Document (PRD)

# Incentive Evolution Simulator
### Exploring How Success Metrics Shape Long-Term Performance

---

# Vision

Build a simulation that demonstrates a simple but powerful idea:

> **The way success is measured changes how competitors evolve.**

Two groups begin with identical abilities.

The only difference is how "winning" is defined.

Over thousands of simulated games and seasons, we observe whether different reward systems produce fundamentally different competitors.

This becomes an empirical demonstration for *Freedom Startups*:

> **Your definition of success determines who you become.**

---

# Core Hypothesis

Imagine two leagues.

### League A

A win is a win.

Winning by one point counts exactly the same as winning by twenty.

Reward:

```
Reward = 1 if Win
Reward = 0 if Loss
```

---

### League B

Winning is NOT enough.

Only victories by **5 points or more** count.

Winning by 1–4 points is treated exactly like a loss.

Reward:

```
Reward = 1 if Margin >= 5
Reward = 0 otherwise
```

---

Question:

After thousands of games...

Do these two leagues produce different kinds of teams?

If so...

How?

---

# Simulation Goals

The simulation should answer questions like:

- Does a higher success threshold create stronger competitors?
- Does it create riskier competitors?
- Does it increase variance?
- Does it create more champions?
- Does it create more failures?
- Which system wins more tournaments?
- Which produces more consistent success?

---

# Team Model

Each team has a fixed set of core attributes.

Every attribute ranges from **0.0–1.0**.

Example:

### Offensive Skill

Ability to score.

---

### Defensive Skill

Ability to prevent scoring.

---

### Risk Appetite

Preference for aggressive strategies.

Higher values:

- more aggressive
- more volatility
- larger wins
- larger losses

---

### Adaptability

How quickly the team changes strategy after each game.

---

### Stamina

Ability to maintain performance through a tournament.

---

# Strategy Variables

Separate from core abilities.

Strategy evolves over time.

Possible strategy parameters:

- Aggressiveness
- Offensive emphasis
- Defensive emphasis
- Tempo
- Margin-seeking
- End-game conservatism
- Risk tolerance

These are what the learning algorithm modifies.

---

# Match Engine

Each game should simulate a realistic contest.

Inputs:

- Team attributes
- Current strategy
- Random variance

Outputs:

- Final score
- Winner
- Victory margin

The exact scoring model can be simple.

The goal is believable dynamics, not sports realism.

---

# Learning Engine

After every game:

Each team updates its strategy.

Simple reinforcement learning is sufficient.

Possible approaches:

- heuristic adjustments
- hill climbing
- policy gradient
- evolutionary mutation

The important idea:

Strategies that increase reward become more common.

---

# Tournament Engine

Each season:

- 64 teams
- Single elimination bracket

Repeat:

10,000+

tournaments.

All teams continue learning between tournaments.

---

# Initial Conditions

Both populations begin identical.

Same distributions.

Same skills.

Same randomness.

Only one variable changes:

**Reward Function**

Everything else stays equal.

---

# Metrics to Track

## Individual Metrics

- Win rate
- Loss rate
- Average score
- Average margin
- Tournament wins

---

## Population Metrics

Average:

- Offensive skill
- Defensive skill
- Risk
- Adaptability
- Strategy parameters

---

## Evolution Metrics

Track how strategies drift over time.

Questions:

Do aggressive teams emerge?

Do conservative teams disappear?

Does one population converge?

Does one remain diverse?

---

## Tournament Metrics

- Championships
- Final Four appearances
- Average elimination round
- Upset frequency
- Blowout frequency
- Close-game frequency

---

# Visualizations

Charts should include:

### Strategy Evolution

Line charts over time.

---

### Attribute Drift

How populations change.

---

### Margin Distribution

Histogram.

---

### Win Rate Distribution

Across all teams.

---

### Risk Distribution

Watch risk evolve.

---

### Tournament Success

Compare both populations.

---

# Experimental Controls

Run with:

- Different random seeds
- Different reward thresholds
- Different tournament sizes

Examples:

Win by:

- 2
- 3
- 5
- 10

See whether higher thresholds create different evolutionary behavior.

---

# Future Experiments

## Phase 2

Coach personalities.

Examples:

- Conservative coach
- Aggressive coach
- Adaptive coach

Observe interactions between incentives and leadership style.

---

## Phase 3

Startup Simulator

Replace sports teams with founders.

Core traits:

- Technical ability
- Sales ability
- Persistence
- Risk tolerance
- Adaptability

Reward Function A:

> Build a profitable company.

Reward Function B:

> Build a unicorn.

Run thousands of simulated founders.

Measure:

- Founder wealth
- Founder freedom
- Company survival
- Burnout
- Probability of exit
- Ownership retained
- Time to profitability

This becomes a computational analogy for the central thesis of **Freedom Startups**.

---

# Success Criteria

The project succeeds if:

1. Two identical populations evolve into meaningfully different competitors.
2. The only cause of divergence is the reward function.
3. The results are reproducible across many simulations.
4. The findings generate intuitive visualizations suitable for presentations and the *Freedom Startups* book.

---

# Key Insight

This project is not about basketball.

It is about evolution.

It asks one question:

> **If you change the definition of winning, do you eventually change the kind of people who win?**

That question sits at the heart of *Freedom Startups*.

Founders are not just choosing a business model.

They are choosing the game they will spend the next decade optimizing for.
