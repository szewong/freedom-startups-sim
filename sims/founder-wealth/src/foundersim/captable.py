"""Rounds, dilution, and the option pool (PRD §3.3).

A cap table is four arrays over a cohort:

    founder_pct   (n,)          the founder's common
    other_common  (n,)          option pool + shares sold in secondary
    inv_pct       (n, n_stages) each round's as-converted ownership
    inv_amount    (n, n_stages) dollars invested, which sets the preference

The invariant ``founder + other_common + sum(inv) == 1`` is checked by the tests
and holds after every operation.

Pricing. ``pre_money = max(base, arr * multiple) * noise``: early rounds are not
priced off ARR because there is no ARR to price off, later ones are. The round
size is a fixed fraction of pre-money, which is what makes per-stage dilution
roughly constant — the PRD's table is internally consistent with exactly this
(pre-seed 11.1% + 2% pool = 13%, seed 20% + 2% = 22%, A 21.1% + 2% = 23%, and so
on), so the table is reproduced rather than approximated.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import N_STAGES, CapitalConfig


@dataclass
class CapTable:
    """Cohort cap tables, mutated in place across the run."""

    founder_pct: np.ndarray  # (n,)
    other_common: np.ndarray  # (n,)  pool + secondary buyers
    inv_pct: np.ndarray  # (n, N_STAGES)
    inv_amount: np.ndarray  # (n, N_STAGES)

    @classmethod
    def initial(cls, n: int) -> CapTable:
        """Founder owns everything before anyone else is involved."""
        return cls(
            founder_pct=np.ones(n),
            other_common=np.zeros(n),
            inv_pct=np.zeros((n, N_STAGES)),
            inv_amount=np.zeros((n, N_STAGES)),
        )

    @property
    def n(self) -> int:
        return self.founder_pct.shape[0]

    def total(self) -> np.ndarray:
        return self.founder_pct + self.other_common + self.inv_pct.sum(axis=1)

    def preference(self, cfg: CapitalConfig) -> np.ndarray:
        """Dollar liquidation preference per round."""
        if cfg.null_control:
            return np.zeros_like(self.inv_amount)
        return self.inv_amount * cfg.pref_multiple

    def raised(self) -> np.ndarray:
        return self.inv_amount.sum(axis=1)


def price_round(
    stage: int,
    arr: np.ndarray,
    cfg: CapitalConfig,
    price_noise: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Pre-money valuation and round size for companies raising at ``stage``.

    ``price_noise`` is a standard normal, shared across arms (common random
    numbers): the same founder gets the same investor enthusiasm in every arm
    where they reach the same stage in the same year.
    """
    terms = cfg.stage_terms[stage]
    noise = np.exp(cfg.price_noise_sigma * price_noise - 0.5 * cfg.price_noise_sigma**2)
    pre = np.maximum(terms.pre_money_base, arr * terms.arr_multiple) * noise
    amount = pre * terms.raise_ratio
    return pre, amount


def apply_round(
    table: CapTable,
    raising: np.ndarray,
    stage: int,
    pre_money: np.ndarray,
    amount: np.ndarray,
    cfg: CapitalConfig,
) -> None:
    """Close a round for the companies in ``raising``, in place.

    The option pool is created and refreshed **pre-money**, so the founder and
    the existing investors bear it and the new investor does not. That is a
    meaningful share of total founder dilution and is routinely underestimated
    (PRD §3.3).
    """
    if not raising.any():
        return

    terms = cfg.stage_terms[stage]
    post = pre_money + amount
    new_inv = np.divide(amount, post, out=np.zeros_like(post), where=post > 0)
    pool_add = np.full_like(new_inv, terms.pool_refresh)

    if cfg.null_control:
        # Cash without consequence: the control that separates "raising changed
        # the outcome" from "the paths diverged" (PRD §5.2).
        new_inv = np.zeros_like(new_inv)
        pool_add = np.zeros_like(pool_add)

    keep = 1.0 - new_inv - pool_add
    m = raising

    table.founder_pct[m] *= keep[m]
    table.other_common[m] = table.other_common[m] * keep[m] + pool_add[m]
    table.inv_pct[m, :] *= keep[m, None]
    table.inv_pct[m, stage] = new_inv[m]
    table.inv_amount[m, stage] = amount[m]


def sell_secondary(
    table: CapTable,
    selling: np.ndarray,
    post_money: np.ndarray,
    cfg: CapitalConfig,
) -> np.ndarray:
    """Founder sells common at the round price (PRD §3.5). Returns proceeds.

    The buyer holds common, so the shares move from ``founder_pct`` into
    ``other_common`` rather than leaving the table.
    """
    proceeds = np.zeros(table.n)
    if not selling.any():
        return proceeds

    frac = np.minimum(cfg.secondary_frac, table.founder_pct)
    frac = np.minimum(frac, np.divide(cfg.secondary_cap, np.maximum(post_money, 1.0)))
    frac = np.where(selling, frac, 0.0)

    proceeds = frac * post_money
    table.founder_pct -= frac
    table.other_common += frac
    return proceeds
