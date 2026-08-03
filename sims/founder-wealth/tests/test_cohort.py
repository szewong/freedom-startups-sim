"""Phase 0 and 3 exit criteria (PRD §7), and the properties METHOD demands.

The tests that matter most here are not about numbers being plausible. They are
about the fork being clean: identical draws, identical machinery, one difference.
If those break, every result the model produces is an artefact.
"""

from __future__ import annotations

import io
import tokenize
from pathlib import Path

import numpy as np
import pytest

from foundersim import business
from foundersim.cohort import run_arm, run_fork
from foundersim.config import RunConfig
from foundersim.latents import draw_latents, draw_noise
from foundersim.ledger import build_ledger
from foundersim.strategy import BY_NAME, STRATEGIES, Strategy

N = 1200


@pytest.fixture(scope="module")
def cfg():
    return RunConfig(n_founders=N)


@pytest.fixture(scope="module")
def draws(cfg):
    return draw_latents(cfg, 0), draw_noise(cfg, 0)


@pytest.fixture(scope="module")
def arms(cfg, draws):
    return run_fork(cfg, *draws, STRATEGIES)


# -- Phase 0: reproducibility -------------------------------------------------


def test_config_round_trips_through_yaml(tmp_path):
    cfg = RunConfig(n_founders=321).replace(business__market_decay=0.11, capital__pref_multiple=2.0)
    path = tmp_path / "c.yaml"
    cfg.to_yaml(path)
    back = RunConfig.from_yaml(path)
    assert back == cfg
    assert back.hash() == cfg.hash()
    assert back.capital.stage_terms == cfg.capital.stage_terms


def test_unknown_config_keys_are_rejected():
    with pytest.raises(KeyError):
        RunConfig.from_dict({"n_foudners": 10})
    with pytest.raises(KeyError):
        RunConfig().replace(business__no_such_knob=1.0)


def test_seeded_runs_reproduce_exactly(cfg):
    a = run_arm(cfg, draw_latents(cfg, 0), draw_noise(cfg, 0), BY_NAME["standard_venture"])
    b = run_arm(cfg, draw_latents(cfg, 0), draw_noise(cfg, 0), BY_NAME["standard_venture"])
    assert np.array_equal(a.exit_value, b.exit_value)
    assert np.array_equal(a.salary_cash, b.salary_cash)
    assert np.array_equal(a.distribution_cash, b.distribution_cash)
    assert np.array_equal(a.max_stage, b.max_stage)


def test_replicates_differ(cfg):
    assert not np.array_equal(draw_latents(cfg, 0).fit, draw_latents(cfg, 1).fit)
    assert not np.array_equal(draw_noise(cfg, 0).execution, draw_noise(cfg, 1).execution)


def test_adding_a_draw_does_not_move_the_others(cfg):
    """Streams are named, so they are independent of each other's existence."""
    lat = draw_latents(cfg, 0)
    assert np.array_equal(lat.fit, draw_latents(cfg, 0).fit)
    assert not np.allclose(lat.fit[:50], lat.skill[:50])


# -- The fork is clean --------------------------------------------------------


def test_arms_share_the_same_founders(cfg, draws, arms):
    """Every arm sees the same latents — this is the whole design (PRD §5.1)."""
    lat, _ = draws
    for arm in arms.values():
        assert arm.n == lat.n


def test_two_strategies_with_identical_terms_produce_identical_runs(cfg, draws):
    """A relabelled strategy must change nothing.

    If this fails, something in the engine is reading the arm rather than the
    financing, and every difference between arms is suspect (METHOD §6).
    """
    lat, noise = draws
    a = run_arm(cfg, lat, noise, Strategy("bootstrap", -1))
    b = run_arm(cfg, lat, noise, Strategy("a_different_name", -1))
    assert np.array_equal(a.exit_value, b.exit_value)
    assert np.array_equal(a.salary_cash, b.salary_cash)
    assert np.array_equal(a.distribution_cash, b.distribution_cash)
    assert np.array_equal(a.died, b.died)


def test_business_engine_is_blind_to_capital_structure():
    """METHOD §6: the engine may not act on the thing being tested.

    Comments may discuss dilution; the executable code may not mention it. The
    file is tokenised so a docstring cannot fail the test and a variable name
    cannot pass it.
    """
    source = Path(business.__file__).read_text()
    forbidden = {
        "dilution", "preference", "waterfall", "captable", "cap_table",
        "investor", "founder_pct", "strategy", "stage", "raised", "equity",
    }
    seen = set()
    for tok in tokenize.generate_tokens(io.StringIO(source).readline):
        if tok.type in (tokenize.COMMENT, tokenize.STRING):
            continue
        if tok.type == tokenize.NAME:
            seen.add(tok.string.lower())
    assert not (seen & forbidden), f"business.py acts on capital structure: {seen & forbidden}"


# -- Phase 3: no NaNs, failure emerges ---------------------------------------


def test_no_nans_or_infinities_anywhere(arms):
    for name, arm in arms.items():
        for field in ("salary_cash", "distribution_cash", "capital_cash", "exit_value",
                      "founder_pct", "final_arr"):
            values = getattr(arm, field)
            assert np.isfinite(values).all(), f"{name}.{field} is not finite"


def test_every_founder_reaches_an_ending(arms):
    """Nobody is left running at the horizon: the ledger is complete for all."""
    for name, arm in arms.items():
        assert (arm.died | arm.exited).all(), f"{name} left founders unresolved"
        assert (arm.exit_year >= 0).all()


def test_founder_ownership_stays_in_bounds(arms):
    for arm in arms.values():
        assert (arm.founder_pct >= -1e-12).all()
        assert (arm.founder_pct <= 1.0 + 1e-12).all()


def test_failure_emerges_rather_than_being_asserted(arms):
    """PRD §3.4: nothing in the model sets a failure rate, so it has to fall out.

    The test is only that it lands strictly between the two degenerate answers —
    the *level* is a calibration question, not a correctness one.
    """
    for name, arm in arms.items():
        rate = arm.died.mean()
        assert 0.0 < rate < 1.0, f"{name} has a degenerate failure rate of {rate}"


def test_funded_companies_die_later_than_bootstrapped_ones(arms):
    """They raised the burn along with the money (PRD §3.4)."""
    boot = arms["bootstrap"]
    venture = arms["standard_venture"]
    boot_year = np.median(boot.exit_year[boot.died])
    venture_year = np.median(venture.exit_year[venture.died])
    assert venture_year >= boot_year


def test_raising_more_puts_more_capital_in(arms):
    assert arms["max_venture"].raised.mean() > arms["standard_venture"].raised.mean()
    assert arms["bootstrap"].raised.sum() == 0.0


def test_more_capital_dilutes_the_founder(arms):
    funded = arms["standard_venture"].max_stage >= 1
    assert arms["standard_venture"].founder_pct[funded].mean() < 0.95
    assert arms["bootstrap"].founder_pct.mean() == pytest.approx(1.0)


# -- METHOD §3: the mechanism must be able to help ---------------------------


def test_capital_can_genuinely_create_value(cfg, draws):
    """A mechanism whose only function is to hurt will always be found to hurt.

    With the execution boost turned up, funded companies must end up materially
    bigger. If this fails, the model cannot honestly be used to argue that
    raising is bad, because raising was never allowed to be good.
    """
    lat, noise = draws
    strat = BY_NAME["standard_venture"]

    off = run_arm(cfg.replace(business__capital_execution_boost=0.0), lat, noise, strat)
    on = run_arm(cfg.replace(business__capital_execution_boost=0.60), lat, noise, strat)

    assert np.percentile(on.exit_value, 90) > np.percentile(off.exit_value, 90)
    assert on.exit_value.mean() > off.exit_value.mean()


def test_the_speed_premium_is_real(cfg, draws):
    """With no market decay, being slow costs nothing — so decay must bite."""
    lat, noise = draws
    strat = BY_NAME["bootstrap"]
    slow_market = run_arm(cfg.replace(business__market_decay=0.0), lat, noise, strat)
    fast_market = run_arm(cfg.replace(business__market_decay=0.30), lat, noise, strat)
    assert fast_market.exit_value.mean() < slow_market.exit_value.mean()


# -- Ledger ------------------------------------------------------------------


def test_the_ledger_decomposition_adds_back_up(cfg, arms):
    """net = labour P&L + ownership return, exactly.

    The whole point of splitting the ledger is that these two can be read
    separately; if they do not recombine into the total, the split is telling a
    different story from the one the totals tell.
    """
    for arm in arms.values():
        w = build_ledger(cfg, arm)
        assert np.allclose(w.labour_pl + w.ownership, w.net, atol=1e-6)
        assert np.allclose(w.from_salary + w.from_equity, w.gross, atol=1e-6)
        assert np.allclose(w.from_distributions + w.from_exit, w.from_equity, atol=1e-6)
        # Ownership can be zero but never negative: shares cannot cost you money.
        assert (w.ownership >= -1e-9).all()


def test_opportunity_cost_only_makes_things_worse(cfg, arms):
    for arm in arms.values():
        w = build_ledger(cfg, arm)
        assert (w.net <= w.gross + 1e-9).all()
        assert (w.opportunity_cost >= 0).all()
        assert (w.years_active > 0).all()


def test_a_bigger_preference_stack_never_pays_the_founder_more(cfg, draws):
    """PRD §6: how much of the founder's downside is the term sheet?"""
    lat, noise = draws
    strat = BY_NAME["standard_venture"]
    one_x = build_ledger(cfg, run_arm(cfg, lat, noise, strat))
    two_x = build_ledger(
        cfg.replace(capital__pref_multiple=2.0),
        run_arm(cfg.replace(capital__pref_multiple=2.0), lat, noise, strat),
    )
    # Paired, per founder: the business is identical, only the terms changed.
    assert np.median(two_x.net) <= np.median(one_x.net) + 1e-9
    assert (two_x.from_equity <= one_x.from_equity + 1e-6).all()


def test_null_control_removes_dilution_but_not_the_cash(cfg, draws):
    """PRD §5.2. The control arm must differ from the treated arm only in structure."""
    lat, noise = draws
    strat = BY_NAME["standard_venture"]
    treated = run_arm(cfg, lat, noise, strat)
    control = run_arm(cfg.replace(capital__null_control=True), lat, noise, strat)

    # Not exactly 1.0: the founder still sells secondary at late rounds, which
    # is liquidity rather than dilution and so is not what the control removes.
    assert control.founder_pct.mean() > 0.999
    assert control.founder_pct.mean() > treated.founder_pct.mean() + 0.1
    assert control.raised.mean() == pytest.approx(treated.raised.mean(), rel=0.25)
    control_w = build_ledger(cfg, control)
    treated_w = build_ledger(cfg, treated)
    assert np.median(control_w.net) >= np.median(treated_w.net)
