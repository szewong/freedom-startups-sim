"""The paired counterfactual runner (PRD §5.1).

The same founder, the same idea, the same luck, forked at the capital decision.
``run_arm`` takes latents and noise that were drawn *before* any strategy was
chosen and runs one strategy over them; ``run_fork`` runs every strategy over the
identical draws. Differences between arms are therefore differences in financing
and nothing else, which is the entire value of the exercise.

A year, in order:

    1. raise, if the strategy allows it and the gate clears
    2. decide sales spend
    3. plan staffing; understaffing is what a cash-poor company suffers
    4. acquire and churn customers
    5. book revenue, gross profit, opex, cash
    6. pay the founder; distribute surplus if no more rounds are coming
    7. rescue round if cash went negative; otherwise die (with an acquihire draw)
    8. take an acquisition offer if one arrived and the company is out of gas
    9. the unclaimed market decays

At the horizon every survivor has a terminal liquidity event, so the ledger is
complete for every founder.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from . import business, waterfall
from .captable import CapTable, apply_round, price_round, sell_secondary
from .config import N_STAGES, RunConfig
from .latents import Latents, Noise
from .strategy import Strategy, clears_gate, plan_spend


@dataclass
class ArmResult:
    """One strategy's outcome for a whole cohort. All arrays are (n,) or (n, T)."""

    strategy: str
    income_cash: np.ndarray  # (n, T) after-tax salary + distributions
    capital_cash: np.ndarray  # (n, T) after-tax secondary + exit proceeds
    active: np.ndarray  # (n, T) bool: the founder is running the company
    exit_value: np.ndarray  # (n,) enterprise value at the liquidity event
    exit_year: np.ndarray  # (n,) year the story ended; ``died`` says how
    died: np.ndarray  # (n,) the company failed
    abandoned: np.ndarray  # (n,) ... specifically, the founder gave up on it
    exited: np.ndarray  # (n,)
    max_stage: np.ndarray  # (n,) highest round closed, -1 = none
    raised: np.ndarray  # (n,) total capital raised
    founder_pct: np.ndarray  # (n,) founder common at the liquidity event
    final_arr: np.ndarray  # (n,) ARR at the liquidity event
    founder_gross: np.ndarray  # (n,) pre-tax founder proceeds from the exit

    @property
    def n(self) -> int:
        return self.exit_value.shape[0]


def run_arm(cfg: RunConfig, lat: Latents, noise: Noise, strat: Strategy) -> ArmResult:
    n = lat.n
    horizon = cfg.exit.horizon_years
    b, sp, cap, ex, led = cfg.business, cfg.spend, cfg.capital, cfg.exit, cfg.ledger

    table = CapTable.initial(n)
    customers = np.zeros(n)
    cash = np.full(n, b.founder_savings)
    ceiling = lat.market_size / b.price  # customers the market can hold
    arr = np.zeros(n)  # ARR at the end of the previous year
    arr_prior = np.zeros(n)
    stage = np.full(n, -1, dtype=int)
    alive = np.ones(n, dtype=bool)
    settled = np.zeros(n, dtype=bool)  # died or exited: the story is over

    income_cash = np.zeros((n, horizon))
    capital_cash = np.zeros((n, horizon))
    active_log = np.zeros((n, horizon), dtype=bool)
    exit_value = np.zeros(n)
    exit_year = np.full(n, -1, dtype=int)
    died = np.zeros(n, dtype=bool)
    abandoned = np.zeros(n, dtype=bool)
    exited = np.zeros(n, dtype=bool)
    starving_years = np.zeros(n, dtype=int)
    founder_at_exit = table.founder_pct.copy()
    final_arr = np.zeros(n)
    founder_gross = np.zeros(n)

    base_churn = business.churn_rate(lat.fit, b)
    stage_salary = np.array([term.founder_salary for term in cap.stage_terms])
    profit = np.zeros(n)

    def growth_of(current: np.ndarray, prior: np.ndarray) -> np.ndarray:
        """YoY revenue multiple, guarded against a zero base."""
        return current / np.maximum(prior, b.price)

    def attempt_rounds(eligible: np.ndarray, t: int, growth: np.ndarray) -> None:
        """Close at most one round for every eligible company whose gate clears."""
        already = np.zeros(n, dtype=bool)
        for s in range(N_STAGES):
            if s > strat.max_stage:
                break
            take = eligible & ~already & (stage == s - 1)
            if not take.any():
                continue
            take &= clears_gate(s, arr, growth, cap, noise.gate_arr[:, t], noise.gate_growth[:, t])
            if not take.any():
                continue

            pre, amount = price_round(s, arr, cap, noise.price[:, t])
            amount = amount * strat.raise_multiple
            apply_round(table, take, s, pre, amount, cap)
            cash[take] += amount[take]
            stage[take] = s
            already |= take

            if s >= cap.secondary_min_stage:
                selling = take & (noise.secondary[:, t] < cap.secondary_prob)
                proceeds = sell_secondary(table, selling, pre + amount, cap)
                capital_cash[:, t] += proceeds * (1.0 - led.tax_rate_capital)

    def liquidate(who: np.ndarray, value: np.ndarray, t: int) -> None:
        """Run the waterfall and close the company's books."""
        if not who.any():
            return
        take = waterfall.founder_proceeds(
            value,
            table.preference(cap),
            table.inv_pct,
            table.founder_pct,
            table.other_common,
            participating=cap.participating,
            carve_out=cap.carve_out,
        )
        founder_gross[who] = take[who]
        capital_cash[who, t] += take[who] * (1.0 - led.tax_rate_capital)
        exit_value[who] = value[who]
        exit_year[who] = t
        founder_at_exit[who] = table.founder_pct[who]
        final_arr[who] = arr[who]
        settled[who] = True
        alive[who] = False

    for t in range(horizon):
        running = alive & ~settled
        if not running.any():
            break
        active_log[:, t] = running

        growth = growth_of(arr, arr_prior)
        more_rounds_ahead = stage < strat.max_stage

        # 1. Rounds -----------------------------------------------------------
        attempt_rounds(running & more_rounds_ahead, t, growth)
        more_rounds_ahead = stage < strat.max_stage  # a round closed may exhaust it

        # 2. Spend ------------------------------------------------------------
        expected_revenue = np.maximum(arr, customers * b.price)
        expected_gp = expected_revenue * b.gross_margin
        planned_employees = business.employees_needed(customers, b)
        expected_opex = planned_employees * b.cost_per_head + led.salary_floor
        spend = plan_spend(cash, expected_gp, expected_opex, more_rounds_ahead, sp)
        spend = np.where(running, spend, 0.0)

        # 3. Staffing ---------------------------------------------------------
        boost = np.where(stage >= 2, b.capital_execution_boost, 0.0)
        potential_new = business.gross_new_customers(
            lat.fit, lat.skill, customers, spend, ceiling,
            noise.execution[:, t], boost, b, cfg.latents.exec_sigma,
        )
        projected = customers * (1.0 - base_churn) + potential_new
        desired_employees = business.employees_needed(projected, b)

        # One salary policy for every arm: a market rate that scales with the
        # business. Having raised guarantees the stage salary on top, which is
        # the genuine asymmetry — investor cash pays a founder before revenue can.
        market_salary = np.clip(
            led.salary_revenue_share * expected_revenue, led.salary_floor, led.salary_cap
        )
        salary_target = np.where(
            stage >= 0,
            np.maximum(market_salary, stage_salary[np.clip(stage, 0, N_STAGES - 1)]),
            market_salary,
        )
        # The founder is paid what the company can pay, which is often nothing.
        # A bootstrapper with no revenue does not draw a salary and does not go
        # bankrupt for trying; they simply earn zero, and the ledger says so.
        burn_frac = np.where(more_rounds_ahead, sp.funded_burn_frac, sp.boot_burn_frac)
        affordable = np.maximum(cash * burn_frac + expected_gp - spend, 0.0)
        salary = np.where(running, np.minimum(salary_target, affordable), 0.0)

        staff_budget = np.maximum(cash * burn_frac + expected_gp - spend - salary, 0.0)
        employees = np.minimum(desired_employees, staff_budget / b.cost_per_head)
        employees = np.where(running, employees, 0.0)

        # 4. Customers --------------------------------------------------------
        capacity = business.capacity_factor(employees, np.maximum(projected, 1.0), b)
        churn = np.clip(base_churn + b.understaffing_churn * (1.0 - capacity), 0.0, 0.95)
        new_customers = potential_new * (1.0 - b.understaffing_growth * (1.0 - capacity))
        opening = customers
        customers = np.where(running, opening * (1.0 - churn) + new_customers, customers)

        # 5. Cash -------------------------------------------------------------
        revenue = 0.5 * (opening + customers) * b.price
        gross_profit = revenue * b.gross_margin
        opex = employees * b.cost_per_head + salary
        cash = np.where(running, cash + gross_profit - opex - spend, cash)

        arr_prior = arr
        arr = np.where(running, customers * b.price, arr)
        profit = gross_profit - opex

        # 6. The founder gets paid -------------------------------------------
        reserve = opex * led.distribution_reserve_months / 12.0
        payable = np.minimum(np.maximum(cash - reserve, 0.0), np.maximum(profit, 0.0))
        distributing = running & ~more_rounds_ahead & (payable > 0)
        distribution = np.where(distributing, led.distribution_frac * payable, 0.0)
        cash -= distribution
        income = salary + distribution * table.founder_pct
        income_cash[:, t] += np.where(running, income * (1.0 - led.tax_rate_income), 0.0)

        # 7. Out of cash: rescue round, acquihire, or death --------------------
        broke = running & (cash < 0)
        if broke.any():
            attempt_rounds(broke & (stage < strat.max_stage), t, growth_of(arr, arr_prior))
            still_broke = broke & (cash < 0)
            if still_broke.any():
                p_acquihire = np.minimum(
                    employees * ex.acquihire_prob_per_head, ex.acquihire_prob_cap
                )
                soft = still_broke & (noise.acquihire[:, t] < p_acquihire)
                value = np.where(soft, employees * ex.acquihire_value_per_head, 0.0)
                # A hard death still runs the waterfall — on nothing. That keeps
                # one code path for every ending.
                liquidate(still_broke, value, t)
                died[still_broke] = True
                alive[still_broke] = False

        # 7b. The founder gives up --------------------------------------------
        # A business that cannot pay its founder and is not growing gets
        # abandoned. This is what failure looks like when there is no burn rate
        # to run out of, and without it the model produces immortal zombies.
        running = alive & ~settled
        progressing = (growth_of(arr, arr_prior) >= ex.abandon_growth) & (
            arr - arr_prior >= ex.abandon_income
        )
        starving = running & (income < ex.abandon_income) & ~progressing
        starving_years = np.where(starving, starving_years + 1, 0)
        quitting = running & (starving_years >= ex.abandon_years)
        if quitting.any():
            value = business.enterprise_value(
                arr, profit, growth_of(arr, arr_prior), noise.exit_multiple[:, t], ex
            )
            liquidate(quitting, value, t)
            died[quitting] = True
            abandoned[quitting] = True

        # 8. Acquisition offers ----------------------------------------------
        running = alive & ~settled
        stalled = growth_of(arr, arr_prior) < ex.stall_growth
        offered = running & (
            # out of gas: an offer arrives and there is no reason to refuse it
            ((arr >= ex.offer_min_arr) & stalled & (noise.offer[:, t] < ex.offer_prob))
            # or big enough to go public or be bought mid-flight
            | ((arr >= ex.large_liquidity_arr) & (noise.offer[:, t] < ex.large_liquidity_prob))
        )
        if offered.any():
            value = business.enterprise_value(
                arr, profit, growth_of(arr, arr_prior), noise.exit_multiple[:, t], ex
            )
            liquidate(offered, value, t)
            exited[offered] = True

        # 9. The market moves on ---------------------------------------------
        ceiling = np.where(running, business.decay_ceiling(ceiling, customers, b), ceiling)

    # Terminal liquidity event for every survivor.
    last = horizon - 1
    survivors = alive & ~settled
    if survivors.any():
        value = business.enterprise_value(
            arr, profit, growth_of(arr, arr_prior), noise.exit_multiple[:, last], ex
        )
        # No buyer was found in twelve years; the position is illiquid and marked
        # down accordingly, in every arm alike.
        value = value * (1.0 - ex.horizon_illiquidity_discount)
        liquidate(survivors, value, last)
        exited[survivors] = True

    return ArmResult(
        strategy=strat.name,
        income_cash=income_cash,
        capital_cash=capital_cash,
        active=active_log,
        exit_value=exit_value,
        exit_year=exit_year,
        died=died,
        abandoned=abandoned,
        exited=exited,
        max_stage=stage,
        raised=table.raised(),
        founder_pct=founder_at_exit,
        final_arr=final_arr,
        founder_gross=founder_gross,
    )


def run_fork(
    cfg: RunConfig,
    lat: Latents,
    noise: Noise,
    strategies: tuple[Strategy, ...],
) -> dict[str, ArmResult]:
    """Run every strategy over identical draws — the fork itself (PRD §5.1)."""
    return {s.name: run_arm(cfg, lat, noise, s) for s in strategies}
