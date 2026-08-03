"""What a business is worth at the low end of the market.

The multiples here are quoted, not invented: IBBA / M&A Source Market Pulse
Q3 2025 medians by business value. They are the closest thing there is to
transaction data for companies that sell below $10M, which is where most
companies actually sell and where published venture statistics see nothing.

    < $500K    2.0x  |
    $500K-$1M  2.5x  |  of seller's discretionary earnings
    $1M-$2M    3.0x  |
    $2M-$5M    4.0x  |  of EBITDA
    $5M-$50M   6.5x  |
"""

from __future__ import annotations

import numpy as np
import pytest

from foundersim.business import earnings_multiple, enterprise_value
from foundersim.config import ExitConfig

K, M = 1e3, 1e6


def mult(earnings, cfg=None):
    return float(earnings_multiple(np.array([earnings], float), cfg or ExitConfig())[0])


def value(arr, profit, growth=1.0, owner_comp=None, cfg=None):
    cfg = cfg or ExitConfig(exit_noise_sigma=0.0)
    oc = None if owner_comp is None else np.array([owner_comp], float)
    return float(
        enterprise_value(
            np.array([arr], float), np.array([profit], float),
            np.array([growth], float), np.zeros(1), cfg, oc,
        )[0]
    )


# -- the ladder ---------------------------------------------------------------


@pytest.mark.parametrize(
    "earnings,expected,band",
    [
        (250 * K, 2.0, "a $500K business sells for 2x"),
        (1.25 * M, 4.0, "a $5M business sells for 4x"),
        (7.7 * M, 6.5, "a $50M business sells for 6.5x"),
    ],
)
def test_multiple_reproduces_the_published_bands(earnings, expected, band):
    """Three of the four published anchors, within a tenth of a turn."""
    assert mult(earnings) == pytest.approx(expected, abs=0.15), band


def test_the_multiple_climbs_with_size():
    """The buyer pool is the mechanism: a person, then a fund, then an acquirer."""
    ladder = [mult(e) for e in (100 * K, 250 * K, 1 * M, 5 * M, 20 * M)]
    assert ladder == sorted(ladder)
    assert ladder[0] < 2.0 < ladder[-1]


def test_the_multiple_is_bounded_at_both_ends():
    cfg = ExitConfig()
    assert mult(1.0) == pytest.approx(cfg.min_earnings_multiple)
    assert mult(1e12) == pytest.approx(cfg.max_earnings_multiple)


# -- seller's discretionary earnings -----------------------------------------


def test_the_owner_salary_is_added_back_below_the_ceiling():
    """A one-person business earning $100k after paying its owner $150k.

    On EBITDA alone it is worth almost nothing. On the convention the market
    actually uses at that size — earnings plus the owner's pay, because the buyer
    is purchasing the job too — it is a $250k-SDE business worth about $500k.
    """
    cfg = ExitConfig(exit_noise_sigma=0.0, base_revenue_multiple=0.0, min_revenue_multiple=0.0)
    without = value(0.0, 100 * K, cfg=cfg)
    with_addback = value(0.0, 100 * K, owner_comp=150 * K, cfg=cfg)

    assert with_addback == pytest.approx(500 * K, rel=0.1)
    assert with_addback > 3 * without


def test_the_add_back_stops_at_the_ceiling():
    """Above $2M of value the buyer hires a manager, so the salary is a real cost."""
    cfg = ExitConfig(exit_noise_sigma=0.0, base_revenue_multiple=0.0, min_revenue_multiple=0.0)
    big_profit = 2 * M
    with_addback = value(0.0, big_profit, owner_comp=250 * K, cfg=cfg)
    ebitda_only = value(0.0, big_profit, cfg=cfg)
    assert with_addback == pytest.approx(ebitda_only)


def test_a_growing_company_is_still_worth_a_revenue_multiple():
    """The earnings ladder must not price a hypergrowth business off its profit."""
    cfg = ExitConfig(exit_noise_sigma=0.0)
    fast = value(10 * M, 0.0, growth=3.0, cfg=cfg)
    assert fast > 10 * M


def test_a_tiny_unprofitable_company_is_worth_little():
    cfg = ExitConfig(exit_noise_sigma=0.0)
    assert value(300 * K, -50 * K, growth=1.0, owner_comp=40 * K, cfg=cfg) < 2 * M
