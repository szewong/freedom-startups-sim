"""Phase 1 exit criteria (PRD §7): the waterfall against hand-worked examples.

Every case below is worked by hand in its docstring. If one of these breaks,
nothing downstream means anything — the whole question is what the founder ends
up holding after the preference stack.
"""

from __future__ import annotations

import numpy as np
import pytest

from foundersim.waterfall import exit_waterfall, founder_proceeds

M = 1e6


def founder_take(exit_value, prefs, pcts, founder_pct, other_common=0.0, participating=False):
    """Single-company convenience wrapper around the vectorised functions."""
    return float(
        founder_proceeds(
            np.array([exit_value], float),
            np.array([prefs], float),
            np.array([pcts], float),
            np.array([founder_pct], float),
            np.array([other_common], float),
            participating=participating,
        )[0]
    )


def payouts(exit_value, prefs, pcts, common_pct, participating=False):
    per_point, inv = exit_waterfall(
        np.array([exit_value], float),
        np.array([prefs], float),
        np.array([pcts], float),
        np.array([common_pct], float),
        participating=participating,
    )
    return float(per_point[0]), inv[0]


# -- No capital --------------------------------------------------------------


def test_unfunded_founder_takes_everything():
    """No investors, no pool: a $10M exit pays the founder $10M."""
    assert founder_take(10 * M, [0.0], [0.0], 1.0) == pytest.approx(10 * M)


def test_pool_dilutes_the_founder_pro_rata():
    """Founder 88%, pool 12%, $10M exit -> founder $8.8M."""
    assert founder_take(10 * M, [0.0], [0.0], 0.88, 0.12) == pytest.approx(8.8 * M)


# -- One round ---------------------------------------------------------------


def test_investor_converts_when_pro_rata_beats_the_preference():
    """$2M for 20%, exit $50M.

    Pro rata 20% x $50M = $10M > the $2M preference, so the investor converts
    and the founder keeps 80% x $50M = $40M.
    """
    assert founder_take(50 * M, [2 * M], [0.20], 0.80) == pytest.approx(40 * M)


def test_investor_takes_the_preference_when_pro_rata_is_worse():
    """$2M for 20%, exit $5M.

    Pro rata would be $1M, so the investor takes the $2M preference. $3M is left
    and the founder is the only common holder, so the founder takes all $3M —
    60% of the exit for 80% of the company.
    """
    per_point, inv = payouts(5 * M, [2 * M], [0.20], 0.80)
    assert inv[0] == pytest.approx(2 * M)
    assert per_point * 0.80 == pytest.approx(3 * M)


def test_exit_below_the_preference_leaves_the_founder_nothing():
    """$2M for 20%, exit $1.5M -> the investor takes all of it."""
    assert founder_take(1.5 * M, [2 * M], [0.20], 0.80) == pytest.approx(0.0)


# -- The case the PRD names --------------------------------------------------


def test_raised_50m_exit_40m_returns_zero_to_the_founder():
    """PRD §3.3: 'a company that raised $50M and exits at $40M returns zero'.

    Series A $12M and Series B $38M. The stack is $50M against $40M of proceeds,
    so nothing reaches common. That is a step function written into the cap
    table, and the founder chose its height every time they raised.
    """
    prefs = [12 * M, 38 * M]
    pcts = [0.25, 0.30]
    assert founder_take(40 * M, prefs, pcts, 0.45) == pytest.approx(0.0)

    # One dollar above the stack, the founder starts to get paid.
    assert founder_take(50 * M + 1000, prefs, pcts, 0.45) == pytest.approx(1000.0, abs=1.0)


def test_preferences_are_paid_in_reverse_order_of_seniority():
    """Exit $40M against A=$12M and B=$38M.

    Last money in is paid first: B takes $38M, A takes what is left ($2M), and
    the earliest investor is nearly wiped out while the latest is made whole.
    """
    _, inv = payouts(40 * M, [12 * M, 38 * M], [0.25, 0.30], 0.45)
    assert inv[1] == pytest.approx(38 * M)
    assert inv[0] == pytest.approx(2 * M)


# -- The joint conversion decision -------------------------------------------


def test_cheap_early_investor_converts_while_expensive_later_one_does_not():
    """A: $1M for 20%. B: $30M for 30%. Common 50%. Exit $50M.

    Worked by hand: if B holds its preference it takes $30M, leaving $20M for a
    common base of 50% + A's converted 20% = 70%, so A gets 0.2/0.7 x $20M =
    $5.714M against a $1M preference — A converts. B, converting, would get 30%
    of the whole $50M = $15M, which is worse than its $30M preference, so B does
    not. The founder is left with 0.5/0.7 x $20M = $14.286M.

    This is the case that makes the fixed point necessary: neither investor's
    answer can be worked out without the other's.
    """
    per_point, inv = payouts(50 * M, [1 * M, 30 * M], [0.20, 0.30], 0.50)
    assert inv[0] == pytest.approx(5.7142857 * M, rel=1e-6)
    assert inv[1] == pytest.approx(30 * M)
    assert per_point * 0.50 == pytest.approx(14.2857143 * M, rel=1e-6)
    assert inv.sum() + per_point * 0.50 == pytest.approx(50 * M)


def test_everyone_converts_at_a_large_exit():
    """A: $1M for 10%. B: $20M for 40%. Common 50%. Exit $60M.

    Both preferences are beaten by pro rata, so the exit splits by ownership:
    $6M, $24M, and $30M to the founder.
    """
    per_point, inv = payouts(60 * M, [1 * M, 20 * M], [0.10, 0.40], 0.50)
    assert inv[0] == pytest.approx(6 * M)
    assert inv[1] == pytest.approx(24 * M)
    assert per_point * 0.50 == pytest.approx(30 * M)


# -- Participating preferred -------------------------------------------------


def test_participating_preferred_double_dips():
    """$10M for 30% participating, exit $50M.

    The investor takes the $10M preference *and* 30% of the remaining $40M, so
    $22M against $15M under non-participating terms. The founder's $28M is $7M
    worse for the same business.
    """
    per_point, inv = payouts(50 * M, [10 * M], [0.30], 0.70, participating=True)
    assert inv[0] == pytest.approx(22 * M)
    assert per_point * 0.70 == pytest.approx(28 * M)

    non_part, _ = payouts(50 * M, [10 * M], [0.30], 0.70)
    assert non_part * 0.70 == pytest.approx(35 * M)


# -- Invariants over random cap tables ---------------------------------------


def random_tables(rng, n=4000, r=4):
    """Cap tables that always sum to one, with plausible round sizes."""
    raw = rng.random((n, r)) * 0.25
    keep = rng.random((n, r)) < 0.7
    pcts = raw * keep
    common = 1.0 - pcts.sum(axis=1)
    amounts = pcts * rng.lognormal(np.log(60e6), 1.0, (n, r))
    return pcts, amounts * keep, common


def test_proceeds_are_conserved():
    """Every dollar of an exit is distributed: nothing is created or lost."""
    rng = np.random.default_rng(7)
    pcts, prefs, common = random_tables(rng)
    exits = rng.lognormal(np.log(50e6), 2.0, pcts.shape[0])

    per_point, inv = exit_waterfall(exits, prefs, pcts, common)
    total = inv.sum(axis=1) + per_point * common
    assert np.allclose(total, exits, rtol=1e-9, atol=1e-3)


def test_no_investor_can_improve_by_flipping_its_decision():
    """The conversion set really is a fixed point, not just a stopping point.

    For every investor in every company, flipping that one decision while the
    others hold theirs must not pay the investor more. This is the property the
    iteration claims to deliver, checked directly.
    """
    from foundersim.waterfall import _payouts, solve_conversions

    rng = np.random.default_rng(11)
    pcts, prefs, common = random_tables(rng, n=1500)
    exits = rng.lognormal(np.log(50e6), 2.0, pcts.shape[0])

    converted = solve_conversions(exits, prefs, pcts, common)
    realised, _ = _payouts(exits, prefs, pcts, common, converted, False)

    for c in range(pcts.shape[1]):
        flipped = converted.copy()
        flipped[:, c] = ~flipped[:, c]
        alt, _ = _payouts(exits, prefs, pcts, common, flipped, False)
        assert (alt[:, c] <= realised[:, c] + 1e-3).all()


def test_founder_take_is_monotone_in_exit_value():
    """A bigger exit never pays the founder less."""
    rng = np.random.default_rng(3)
    pcts, prefs, common = random_tables(rng, n=800)
    founder = common * 0.9
    other = common * 0.1

    prev = None
    for scale in (0.1, 0.5, 1.0, 2.0, 5.0, 20.0):
        take = founder_proceeds(
            np.full(pcts.shape[0], 40e6) * scale, prefs, pcts, founder, other
        )
        if prev is not None:
            assert (take >= prev - 1e-6).all()
        prev = take


def test_preference_multiple_never_helps_the_founder():
    """A 2x stack cannot pay the founder more than a 1x stack on the same exit."""
    rng = np.random.default_rng(5)
    pcts, prefs, common = random_tables(rng, n=1500)
    founder, other = common, np.zeros_like(common)
    exits = rng.lognormal(np.log(80e6), 1.5, pcts.shape[0])

    one_x = founder_proceeds(exits, prefs, pcts, founder, other)
    two_x = founder_proceeds(exits, prefs * 2.0, pcts, founder, other)
    assert (two_x <= one_x + 1e-6).all()


# -- The carve-out: shape rather than height ---------------------------------


def test_carve_out_pays_the_founder_below_the_preference_stack():
    """The same failed exit, with and without a 10% carve-out.

    Raised $50M, exits at $40M. With a pure step the founder gets nothing. With
    10% off the top they get $4M x their share of common — the business did not
    change, only the shape of the payoff did.
    """
    prefs, pcts = [12 * M, 38 * M], [0.25, 0.30]
    step = founder_take(40 * M, prefs, pcts, 0.45)
    ramp = float(
        founder_proceeds(
            np.array([40 * M]), np.array([prefs]), np.array([pcts]),
            np.array([0.45]), np.array([0.0]), carve_out=0.10,
        )[0]
    )
    assert step == pytest.approx(0.0)
    assert ramp == pytest.approx(4 * M)


def test_carve_out_never_costs_the_founder():
    rng = np.random.default_rng(21)
    pcts, prefs, common = random_tables(rng, n=1200)
    exits = rng.lognormal(np.log(60e6), 1.6, pcts.shape[0])
    zero = np.zeros_like(common)

    step = founder_proceeds(exits, prefs, pcts, common, zero)
    for carve in (0.05, 0.10, 0.20):
        ramp = founder_proceeds(exits, prefs, pcts, common, zero, carve_out=carve)
        assert (ramp >= step - 1e-6).all()


# -- A second implementation (METHOD §7) -------------------------------------


def brute_force_conversions(exit_value, prefs, pcts, common):
    """Enumerate every conversion subset and return the equilibrium payouts.

    Deliberately written a different way from the solver: no iteration, no best
    response, just all 2^r possibilities checked exhaustively for the property
    "no investor would rather have chosen otherwise". Slow, obviously correct,
    and the only reason to trust the fast one.
    """
    from foundersim.waterfall import _payouts

    n, r = prefs.shape
    out = np.full((n, r), np.nan)
    subsets = [np.array([(k >> j) & 1 for j in range(r)], bool) for k in range(2**r)]

    payoff_by_subset = np.stack(
        [
            _payouts(exit_value, prefs, pcts, common, np.tile(sub, (n, 1)), False)[0]
            for sub in subsets
        ]
    )  # (2^r, n, r)

    for k, sub in enumerate(subsets):
        stable = np.ones(n, bool)
        for c in range(r):
            flipped = sub.copy()
            flipped[c] = ~flipped[c]
            other = _index_of(subsets, flipped)
            stable &= payoff_by_subset[k, :, c] >= payoff_by_subset[other, :, c] - 1e-6
        take = stable & np.isnan(out[:, 0])
        out[take] = payoff_by_subset[k][take]
    return out


def _index_of(subsets, target):
    for i, s in enumerate(subsets):
        if np.array_equal(s, target):
            return i
    raise AssertionError("subset not found")


def test_iterative_solver_agrees_with_brute_force_enumeration():
    """The fast fixed point must land on the same payouts as exhaustive search."""
    rng = np.random.default_rng(31)
    pcts, prefs, common = random_tables(rng, n=600, r=3)
    exits = rng.lognormal(np.log(40e6), 2.2, pcts.shape[0])

    _, fast = exit_waterfall(exits, prefs, pcts, common)
    slow = brute_force_conversions(exits, prefs, pcts, common)

    assert not np.isnan(slow).any(), "some cap table had no equilibrium at all"
    assert np.allclose(fast, slow, rtol=1e-6, atol=1e-2)
