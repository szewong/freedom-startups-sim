# Freedom Startups — simulations

Computational appendices to *Freedom Startups*. Each simulation asks a different
question and shares no code with the others. What they share is a method, written
down in [`METHOD.md`](METHOD.md).

---

## The simulations

### [`sims/incentive-evolution`](sims/incentive-evolution) — built, closed at v1.0

> **Does changing the definition of success change who succeeds?**

Two leagues of 64 teams, byte-identical at season zero, playing the same game
under the same physics. One difference: what counts as a win. 600 seasons, 16
replicates, 8.6M simulated games.

It found that a success threshold makes a population markedly **more volatile**
without making it **more capable** — and that this splits into two separate
levers. The *height* of a bar drives volatility. Its *all-or-nothing shape*
drives capability collapse, and replacing the step with a ramp removes that
collapse entirely while leaving the volatility untouched.

It also retracted three claims along the way, which are on the record in
[`CLOSEOUT.md`](sims/incentive-evolution/CLOSEOUT.md).

**Start here:** open [`web/sim.html`](sims/incentive-evolution/web/sim.html) in a
browser and press Run. No install — it simulates live.
Then [`PAPER.md`](sims/incentive-evolution/PAPER.md).

### [`sims/founder-wealth`](sims/founder-wealth) — specified, not yet built

> **Does raising big rounds make founders wealthier than grinding it out alone?**

Not "does it build bigger companies" — that answer is known. The question is the
founder's own take-home, after dilution, after liquidation preferences, after
years of below-market salary, and after counting the companies that die.

Design is complete in [`PRD.md`](sims/founder-wealth/PRD.md), including how
failure emerges rather than being asserted, and what would falsify the
hypothesis. To be built clean in its own session.

---

## Why one repository

The two simulations answer different questions and deliberately share no code —
the second is not a version of the first. They sit together because they belong
to one book, and because the method that produced the first is the reason to
believe the second.

Each sim is a self-contained project: its own environment, dependencies, tests
and build scripts. Work on one by `cd`-ing into it.

```bash
cd sims/incentive-evolution
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest          # 60 tests
```

---

## What carries between them

Not code — discipline. [`METHOD.md`](METHOD.md) records the rules the first
simulation learned, several of them the hard way:

- a mean curve is not a finding until its spread is examined
- a null control is mandatory, and effects get reported against it
- a mechanism whose only function is to hurt will always be found to hurt
- calibrate first, then freeze parameters, then run the counterfactual
- publish the retractions

The first simulation retracted a headline claim, a whole mechanism, and two
individual effects. That record is the point, not an embarrassment: a result that
survived those checks is worth more than one that was never checked.
