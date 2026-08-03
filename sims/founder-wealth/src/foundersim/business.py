"""Business dynamics (PRD §3.2). Blind to capital structure.

Nothing in this module may reference dilution, preferences, or which arm of the
counterfactual it is running (METHOD §6). It sees cash, customers and latents,
and it does not care where the cash came from. A test tokenises this file and
fails if the executable code mentions the cap table.

The mechanics, in the order a year happens:

    spend        -> the company's one lever; concave returns
    staffing     -> capacity to onboard and to keep customers
    acquisition  -> paid + organic, throttled by capacity and by headroom
    churn        -> worse at low fit, worse when understaffed
    cash         -> gross profit - opex - spend

Capital creates value here through three channels, all swept rather than
assumed (METHOD §3): it buys staffing (so less churn and more onboarding), it
buys speed (unclaimed market decays, so slow companies lose ceiling
permanently), and above Series A it buys execution outright.
"""

from __future__ import annotations

import numpy as np

from .config import BusinessConfig, ExitConfig


def churn_rate(fit: np.ndarray, cfg: BusinessConfig) -> np.ndarray:
    """Annual churn, worse at low fit."""
    return np.clip(cfg.churn_hi - cfg.churn_fit_slope * fit, 0.02, 0.60)


def gross_new_customers(
    fit: np.ndarray,
    skill: np.ndarray,
    customers: np.ndarray,
    spend: np.ndarray,
    ceiling: np.ndarray,
    execution: np.ndarray,
    boost: np.ndarray,
    cfg: BusinessConfig,
    exec_sigma: float,
) -> np.ndarray:
    """New customers before capacity throttling.

    Three channels. Paid acquisition has concave returns to spend. Organic
    acquisition scales with the installed base and cannot be bought. Founder
    effort is what a company with no money has: the founder sells, and that is
    the engine a bootstrapped company actually runs on.
    """
    headroom = np.clip(1.0 - np.divide(customers, np.maximum(ceiling, 1.0)), 0.0, 1.0)
    quality = fit * skill * (1.0 + boost)

    paid = cfg.growth_scale * quality * np.power(np.maximum(spend, 0.0) / 1e6, cfg.spend_alpha)
    organic = cfg.organic_scale * quality * customers
    effort = cfg.effort_scale * quality

    shock = np.exp(exec_sigma * execution - 0.5 * exec_sigma**2)
    return (paid + organic + effort) * headroom * shock


def employees_needed(customers: np.ndarray, cfg: BusinessConfig) -> np.ndarray:
    """Headcount the book of business requires, excluding the founder."""
    return np.maximum(customers / cfg.customers_per_head - 1.0, 0.0)


def capacity_factor(employees: np.ndarray, customers: np.ndarray, cfg: BusinessConfig) -> np.ndarray:
    """1.0 when fully staffed, falling toward 0 when badly understaffed."""
    served = (employees + 1.0) * cfg.customers_per_head
    return np.clip(np.divide(served, np.maximum(customers, 1.0)), 0.0, 1.0)


def decay_ceiling(ceiling: np.ndarray, customers: np.ndarray, cfg: BusinessConfig) -> np.ndarray:
    """Unclaimed market erodes: what you do not take, a competitor does.

    Only the *unpenetrated* part decays, so a company never loses customers it
    already has — it loses the room it had to grow into.
    """
    unclaimed = np.maximum(ceiling - customers, 0.0)
    return customers + unclaimed * (1.0 - cfg.market_decay)


def revenue_multiple(
    growth: np.ndarray, noise: np.ndarray, cfg: ExitConfig, arr: np.ndarray | None = None
) -> np.ndarray:
    """What an acquirer pays per dollar of ARR.

    Three terms: a base, a premium for growth, and a premium for size. The last
    one exists because the buyer pool does — a business too small for a private
    equity platform is sold to whoever will write a personal cheque, and it
    clears at a fraction of the multiple an identical, larger business would.
    Setting `scale_premium` to zero recovers a size-blind market.
    """
    mult = cfg.base_revenue_multiple + cfg.growth_premium * np.clip(growth - 1.0, 0.0, None)
    if cfg.scale_premium and arr is not None:
        decades = np.log10(np.maximum(arr, 1.0) / cfg.scale_pivot_arr)
        mult = mult + cfg.scale_premium * decades
    mult = np.clip(mult, cfg.min_revenue_multiple, cfg.max_revenue_multiple)
    shock = np.exp(cfg.exit_noise_sigma * noise - 0.5 * cfg.exit_noise_sigma**2)
    return mult * cfg.regime * shock


def earnings_multiple(earnings: np.ndarray, cfg: ExitConfig) -> np.ndarray:
    """What a buyer pays per dollar of earnings, which depends on size.

    A business earning $200k is bought by a person, for about 2x. A business
    earning $8M is bought by an institution, for about 6.5x. That climb is the
    single most important feature of the low end of the market, and treating it
    as one flat multiple — as this model originally did — badly overprices the
    smallest companies and underprices the largest.
    """
    decades = np.log10(np.maximum(earnings, 1.0) / cfg.earnings_pivot)
    mult = cfg.base_earnings_multiple + cfg.earnings_multiple_slope * decades
    return np.clip(mult, cfg.min_earnings_multiple, cfg.max_earnings_multiple)


def enterprise_value(
    arr: np.ndarray,
    profit: np.ndarray,
    growth: np.ndarray,
    noise: np.ndarray,
    cfg: ExitConfig,
    owner_comp: np.ndarray | None = None,
) -> np.ndarray:
    """Exit value: the better of a revenue multiple and an earnings multiple.

    A hypergrowth company is worth a multiple of revenue; a profitable, slow one
    is worth a multiple of its earnings. Taking the maximum is what stops the
    model pricing a profitable bootstrapped business at nothing.

    Two earnings figures, because the market uses two. Under the SDE ceiling the
    quoted earnings add the owner's pay back, since the buyer is purchasing the
    owner's job along with the business; above it they do not. The model takes
    the seller's-discretionary valuation only while it stays under the ceiling,
    which is exactly the convention the published multiples are quoted on.
    """
    rev_value = revenue_multiple(growth, noise, cfg, arr) * arr

    ebitda = np.maximum(profit, 0.0)
    ebitda_value = earnings_multiple(ebitda, cfg) * ebitda

    if owner_comp is not None:
        sde = np.maximum(profit + owner_comp, 0.0)
        sde_value = earnings_multiple(sde, cfg) * sde
        earn_value = np.where(sde_value <= cfg.sde_ceiling, sde_value, ebitda_value)
    else:
        earn_value = ebitda_value

    return np.maximum(rev_value, earn_value)
