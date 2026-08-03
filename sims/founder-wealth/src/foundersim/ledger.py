"""The founder's ledger (PRD §3.5).

Wealth is not the exit. It is salary, distributions, secondary sales and exit
proceeds, discounted to present value — minus the salaried job the founder did
not take, which is charged for every year they were running the company and
stops the day it ends.

Reporting both gross and net of opportunity cost is not decoration. Ignoring it
flatters both paths, and flatters the funded path more, because its salaries are
lower for longer.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .cohort import ArmResult
from .config import RunConfig


@dataclass(frozen=True)
class Wealth:
    """Per-founder outcome for one arm. All arrays are (n,), all in dollars."""

    strategy: str
    gross: np.ndarray  # PV of everything the founder received, after tax
    net: np.ndarray  # ... minus the PV of the forgone salary
    from_salary: np.ndarray
    from_equity: np.ndarray  # secondary + exit
    opportunity_cost: np.ndarray
    years_active: np.ndarray
    years_to_million: np.ndarray  # nominal cumulative cash; horizon+1 if never
    equity_zero: np.ndarray  # bool: the equity paid nothing
    died: np.ndarray
    max_stage: np.ndarray
    raised: np.ndarray
    exit_value: np.ndarray
    founder_pct: np.ndarray


def discount_factors(cfg: RunConfig) -> np.ndarray:
    """Mid-year discounting: cash arriving in year t is discounted t+0.5 years."""
    years = np.arange(cfg.exit.horizon_years) + 0.5
    return (1.0 + cfg.ledger.discount_rate) ** (-years)


def build_ledger(cfg: RunConfig, arm: ArmResult) -> Wealth:
    df = discount_factors(cfg)
    opp_after_tax = cfg.ledger.opportunity_cost * (1.0 - cfg.ledger.tax_rate_income)

    from_salary = (arm.income_cash * df).sum(axis=1)
    from_equity = (arm.capital_cash * df).sum(axis=1)
    gross = from_salary + from_equity

    years_active = arm.active.sum(axis=1).astype(float)
    opportunity = (arm.active * opp_after_tax * df).sum(axis=1)

    nominal = np.cumsum(arm.income_cash + arm.capital_cash, axis=1)
    reached = nominal >= 1e6
    horizon = cfg.exit.horizon_years
    years_to_million = np.where(reached.any(axis=1), reached.argmax(axis=1) + 1, horizon + 1)

    return Wealth(
        strategy=arm.strategy,
        gross=gross,
        net=gross - opportunity,
        from_salary=from_salary,
        from_equity=from_equity,
        opportunity_cost=opportunity,
        years_active=years_active,
        years_to_million=years_to_million.astype(float),
        equity_zero=arm.founder_gross <= 0.0,
        died=arm.died,
        max_stage=arm.max_stage,
        raised=arm.raised,
        exit_value=arm.exit_value,
        founder_pct=arm.founder_pct,
    )
