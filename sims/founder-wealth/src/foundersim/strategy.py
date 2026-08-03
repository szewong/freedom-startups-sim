"""The capital strategies being compared (PRD §5.1), and the policies they imply.

A strategy is only three things: how far up the round ladder the founder is
willing to go, how big a round they take when they get there, and — as a
consequence of those two — how freely the company spends. Everything else about
the company is identical across arms.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import CapitalConfig, SpendConfig


@dataclass(frozen=True)
class Strategy:
    name: str
    max_stage: int  # highest stage index the founder will raise; -1 = never raise
    raise_multiple: float = 1.0  # round size relative to the stage's standard
    label: str = ""

    # The founder's own bar, distinct from the investors'. Zero means "raise as
    # soon as anyone will fund you", which is what every venture arm above does
    # and which in practice means raising at $0 of revenue on day one. A positive
    # threshold is a founder saying: prove it first, then decide.
    #
    # This is not the same as raising less. The company still goes up the same
    # ladder on the same terms — it just arrives later, with revenue, and skips
    # whichever early rounds it has already outgrown.
    min_arr_to_raise: float = 0.0

    # Override the size and price of the *first* round only. A founder raising
    # $250k to hire two people is not raising the ladder's pre-seed, and pricing
    # it as one would flatter the strategy by handing them a $5M valuation for a
    # company doing a few thousand a month.
    entry_amount: float | None = None
    entry_pre_money: float | None = None


STRATEGIES: tuple[Strategy, ...] = (
    Strategy("bootstrap", -1, label="Never raise. Growth funded from gross profit."),
    Strategy("friends_family", 0, label="One small round, then self-funded."),
    Strategy("seed_and_stop", 1, label="Raise seed, then bootstrap to profitability."),
    Strategy("standard_venture", 5, label="Raise at every gate cleared."),
    Strategy("max_venture", 5, 1.4, label="Raise the largest round available at every gate."),
    Strategy(
        "freedom",
        5,
        label="Bootstrap to $100k ARR, then raise at every gate cleared.",
        min_arr_to_raise=100_000.0,
    ),
)

BY_NAME = {s.name: s for s in STRATEGIES}


def clears_gate(
    stage: int,
    arr: np.ndarray,
    growth: np.ndarray,
    cfg: CapitalConfig,
    gate_arr_noise: np.ndarray,
    gate_growth_noise: np.ndarray,
) -> np.ndarray:
    """Can these companies raise round ``stage``?

    The bar is not a clean threshold: real investors are noisier, more herd-driven
    and more founder-biased than a metrics test (PRD §8), so each company faces a
    lognormally jittered bar. ``gate_noise_sigma = 0`` recovers a hard threshold,
    which is how the sensitivity of the result to this choice gets tested.
    """
    terms = cfg.stage_terms[stage]
    s = cfg.gate_noise_sigma
    arr_bar = terms.gate_arr * np.exp(s * gate_arr_noise - 0.5 * s**2)
    growth_bar = terms.gate_growth * np.exp(s * gate_growth_noise - 0.5 * s**2)
    return (arr >= arr_bar) & (growth >= growth_bar)


def plan_spend(
    cash: np.ndarray,
    expected_gross_profit: np.ndarray,
    expected_opex: np.ndarray,
    more_rounds_ahead: np.ndarray,
    cfg: SpendConfig,
) -> np.ndarray:
    """Sales spend for the year.

    Two components, and the asymmetry between them is most of the difference
    between the two paths (PRD §3.2): every company reinvests part of what it
    earns, and a company sitting on capital spends that down as well — fast if it
    expects to raise again, patiently if this is the last money it will see.
    """
    reserve = expected_opex * cfg.boot_reserve_months / 12.0
    from_profit = cfg.boot_reinvest_frac * np.maximum(expected_gross_profit - expected_opex, 0.0)
    rate = np.where(more_rounds_ahead, cfg.funded_spend_rate, cfg.patient_spend_rate)
    from_cash = rate * np.maximum(cash - reserve, 0.0)
    return from_profit + from_cash
