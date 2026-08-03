"""Phase 1 exit criteria (PRD §7): the cap table always sums to one.

Dilution is arithmetic, so these tests are exact rather than statistical. The
PRD's round table (§3.3) is reproduced number for number — if the implementation
drifts from it, these fail.
"""

from __future__ import annotations

import numpy as np
import pytest

from foundersim.captable import CapTable, apply_round, price_round, sell_secondary
from foundersim.config import DEFAULT_STAGE_TERMS, N_STAGES, CapitalConfig

M = 1e6


def single(n=1):
    return CapTable.initial(n)


def close(table, stage, pre, amount, cfg=None, who=None):
    cfg = cfg or CapitalConfig()
    who = np.ones(table.n, bool) if who is None else who
    apply_round(table, who, stage, np.full(table.n, pre), np.full(table.n, amount), cfg)


def test_founder_starts_with_everything():
    t = single()
    assert t.founder_pct[0] == 1.0
    assert t.total()[0] == pytest.approx(1.0)


@pytest.mark.parametrize(
    "stage,pre,amount,expected_dilution",
    [
        (0, 4 * M, 0.5 * M, 0.131),  # pre-seed: 11.1% + 2% pool ~ 13%
        (1, 12 * M, 3 * M, 0.220),  # seed:     20.0% + 2%      ~ 22%
        (2, 45 * M, 12 * M, 0.231),  # series A: 21.1% + 2%      ~ 23%
        (3, 150 * M, 35 * M, 0.209),  # series B: 18.9% + 2%      ~ 21%
        (4, 500 * M, 80 * M, 0.148),  # series C: 13.8% + 1%      ~ 15%
        (5, 1200 * M, 150 * M, 0.121),  # series D: 11.1% + 1%      ~ 12%
    ],
)
def test_dilution_reproduces_the_prd_table(stage, pre, amount, expected_dilution):
    """PRD §3.3's 'dilution incl. pool' column, to the nearest tenth of a point."""
    t = single()
    close(t, stage, pre, amount)
    assert 1.0 - t.founder_pct[0] == pytest.approx(expected_dilution, abs=0.001)
    assert t.total()[0] == pytest.approx(1.0)


def test_the_option_pool_is_created_pre_money_so_the_founder_bears_it():
    """The new investor gets exactly amount/post; the pool comes out of everyone else.

    Series A: $12M on $45M pre. The investor's 21.05% is untouched by the 2%
    pool, so the founder's dilution is 23.1% and not 21.1%. Two points of the
    founder's company, at every round, routinely underestimated.
    """
    t = single()
    close(t, 2, 45 * M, 12 * M)
    assert t.inv_pct[0, 2] == pytest.approx(12 / 57, abs=1e-9)
    assert t.other_common[0] == pytest.approx(0.02)
    assert t.founder_pct[0] == pytest.approx(1.0 - 12 / 57 - 0.02, abs=1e-9)


def test_the_full_ladder_leaves_the_founder_about_a_third():
    """Pre-seed through Series D at the table's terms.

    Compounding six rounds of ~13-23% dilution leaves the founder near 35% —
    which is why the preference stack, not the ownership percentage, is where
    the founder's downside actually lives.
    """
    t = single()
    for stage, terms in enumerate(DEFAULT_STAGE_TERMS):
        pre = terms.pre_money_base
        close(t, stage, pre, pre * terms.raise_ratio)

    assert t.total()[0] == pytest.approx(1.0)
    assert 0.30 < t.founder_pct[0] < 0.40
    assert t.raised()[0] == pytest.approx(280.465 * M)


def test_prior_investors_are_diluted_by_later_rounds():
    t = single()
    close(t, 1, 12 * M, 3 * M)
    seed_at_seed = t.inv_pct[0, 1]
    close(t, 2, 45 * M, 12 * M)
    assert t.inv_pct[0, 1] < seed_at_seed
    assert t.inv_pct[0, 1] == pytest.approx(seed_at_seed * (1 - 12 / 57 - 0.02), abs=1e-9)


def test_only_the_selected_companies_raise():
    t = single(4)
    who = np.array([True, False, True, False])
    close(t, 1, 12 * M, 3 * M, who=who)
    assert (t.founder_pct[~who] == 1.0).all()
    assert (t.founder_pct[who] < 1.0).all()
    assert np.allclose(t.total(), 1.0)


def test_pricing_uses_arr_once_it_is_material():
    """Early rounds are priced off a base; later ones off metrics."""
    cfg = CapitalConfig(price_noise_sigma=0.0)
    zero = np.zeros(3)

    pre_seed, _ = price_round(0, np.zeros(3), cfg, zero)
    assert pre_seed == pytest.approx(4 * M)

    # Series A at $3M ARR: 30x beats the $45M base.
    pre_a, amount_a = price_round(2, np.full(3, 3 * M), cfg, zero)
    assert pre_a == pytest.approx(90 * M)
    assert amount_a == pytest.approx(90 * M * 0.267)

    # ... but a company scraping over the gate is priced off the base.
    pre_a_small, _ = price_round(2, np.full(3, 1.5 * M), cfg, zero)
    assert pre_a_small == pytest.approx(45 * M)


def test_secondary_moves_shares_to_common_without_leaving_the_table():
    cfg = CapitalConfig()
    t = single()
    close(t, 4, 500 * M, 80 * M, cfg)
    before = t.founder_pct[0]

    proceeds = sell_secondary(t, np.array([True]), np.array([580 * M]), cfg)
    assert t.total()[0] == pytest.approx(1.0)
    # The dollar cap binds before the percentage does: 3% of $580M would be
    # $17.4M, so the founder sells only the 1.38% that fits under the $8M cap.
    sold = cfg.secondary_cap / (580 * M)
    assert sold < cfg.secondary_frac
    assert t.founder_pct[0] == pytest.approx(before - sold)
    assert proceeds[0] == pytest.approx(cfg.secondary_cap, rel=1e-9)


def test_null_control_gives_cash_without_dilution():
    """PRD §5.2: the control that separates capital structure from divergence."""
    cfg = CapitalConfig(null_control=True)
    t = single()
    close(t, 2, 45 * M, 12 * M, cfg)
    assert t.founder_pct[0] == pytest.approx(1.0)
    assert t.inv_pct[0].sum() == pytest.approx(0.0)
    assert (t.preference(cfg) == 0).all()
    # The money still shows up as raised, so the arm is still identifiable.
    assert t.raised()[0] == pytest.approx(12 * M)


def test_preference_scales_with_the_multiple():
    t = single()
    close(t, 2, 45 * M, 12 * M)
    assert t.preference(CapitalConfig())[0, 2] == pytest.approx(12 * M)
    assert t.preference(CapitalConfig(pref_multiple=2.0))[0, 2] == pytest.approx(24 * M)


def test_cap_table_stays_normalised_under_random_ladders():
    rng = np.random.default_rng(4)
    cfg = CapitalConfig()
    t = single(2000)
    for stage in range(N_STAGES):
        who = rng.random(2000) < 0.6
        terms = DEFAULT_STAGE_TERMS[stage]
        pre = np.full(2000, terms.pre_money_base) * rng.lognormal(0, 0.4, 2000)
        apply_round(t, who, stage, pre, pre * terms.raise_ratio, cfg)
        assert np.allclose(t.total(), 1.0, atol=1e-12)
        assert (t.founder_pct >= 0).all()
