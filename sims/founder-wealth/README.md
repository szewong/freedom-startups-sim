# Founder Wealth Simulator

> **Does raising big rounds make founders wealthier than grinding it out alone?**

Not "does it build bigger companies" — that answer is known. The question is the
founder's own take-home, after dilution, after liquidation preferences, after
years of below-market salary, and after counting the companies that die.

The counterfactual is unobservable: nobody can watch the same founder with the
same idea both raise $40M and bootstrap. So the model makes it free — **the same
founder, the same idea, the same luck, forked at the capital decision** — and
protects that pairing above everything else.

Design: [`PRD.md`](PRD.md). Method it inherits: [`../../METHOD.md`](../../METHOD.md).
Results, caveats and retractions: [`FINDINGS.md`](FINDINGS.md).

---

## Status

| Phase | Deliverable | State |
|---|---|---|
| 0 | Config, seeded RNG, ledger types | done |
| 1 | Cap table + waterfall | done — hand-worked tests, including the raised-$50M-exit-$40M zero case |
| 2 | Business dynamics | done |
| 3 | Rounds, gates, dilution, death | done — failure emerges, no NaNs, cap tables sum to 1 |
| 4 | **Calibration** | done, with misses recorded in `configs/frozen.yaml.fit.json` |
| 5 | Paired counterfactual | done |
| 6 | Null control and sweeps | done |
| 7 | Write-up and interactive explorer | write-up in FINDINGS.md; explorer not built |

## Run it

```bash
cd sims/founder-wealth
uv venv && uv pip install -e ".[dev]"
.venv/bin/python -m pytest                   # the whole suite

.venv/bin/python scripts/calibrate.py        # phase 4 — refits and re-freezes
.venv/bin/python scripts/counterfactual.py   # phase 5-6 — the fork + null control
.venv/bin/python scripts/sweeps.py           # phase 6 — every uncertain knob as a curve
```

`scripts/calibrate.py` overwrites `configs/frozen.yaml`. Do not run it after
looking at a counterfactual result (METHOD §4); if you do, it goes in FINDINGS.md
as a p-hacking exposure.

## How it works

```
src/foundersim/
  config.py     dataclasses, YAML, named seed streams; every parameter tagged
                [table] (observed, not ours to tune), [fit] (calibrated, then
                frozen) or [sweep] (uncertain, reported as a curve)
  latents.py    market size, fit, skill, and the annual luck — drawn once and
                reused by every arm, which is what makes the fork clean
  business.py   growth, churn, staffing, cash. Blind to capital structure, and a
                test tokenises the file to keep it that way
  captable.py   rounds, dilution, the pre-money option pool
  waterfall.py  exit proceeds -> founder take. The one that has to be exact
  strategy.py   the five capital strategies and the spend policies they imply
  cohort.py     the year loop and the paired counterfactual runner
  ledger.py     salary, distributions, secondary, exit, opportunity cost -> PV
  metrics.py    distributions, paired differences, replicate intervals, crossings
  calibrate.py  fit to the PRD §4 targets, then freeze
```

### The five strategies

| Strategy | Description |
|---|---|
| `bootstrap` | Never raise. Growth funded from gross profit. |
| `friends_family` | One small round, then self-funded. |
| `seed_and_stop` | Raise seed, then bootstrap to profitability. |
| `standard_venture` | Raise at every gate cleared. |
| `max_venture` | Raise the largest round available at every gate. |

### What the model refuses to assume

**No hardcoded failure rate.** A company dies when it runs out of cash and
cannot raise, or when the founder gives up on a business that cannot pay them
and is not growing. The observed failure rate is an *output* to calibrate
against, not an input to assert.

**Capital is allowed to help.** A mechanism whose only function is to hurt will
always be found to hurt (METHOD §3), so capital creates real value through three
channels — it buys staffing, it buys speed in a market whose unclaimed share
decays, and above Series A it buys execution outright. All three are swept,
including to zero.

**The engine cannot see the arm.** `business.py` never learns whether the money
came from an investor, and a test tokenises its source to prove it. Two
strategies with identical terms and different names produce byte-identical runs.

**Nothing is reported as a mean alone.** Venture outcomes are power-law and
bootstrapped outcomes are not, so a mean comparison is arithmetic that tells you
nothing.

Sibling simulation, already closed: [`../incentive-evolution`](../incentive-evolution).
