"""Exit proceeds -> founder take (PRD §3.3).

The single most important function in the codebase, and the one the PRD says to
test hardest. Everything else can be approximately right; this has to be exactly
right, because the whole question is what the founder ends up holding.

Rules implemented
-----------------
1. **1x non-participating preferred, stacking.** Each investor takes the greater
   of their preference and their pro-rata share of the proceeds as common.
2. **Seniority.** When proceeds cannot cover every preference, they are paid in
   reverse order of investment: the last money in is paid first, and the earliest
   investors can receive nothing.
3. **Participating preferred** (switchable variant): the investor takes the
   preference *and* shares the residual pro rata. No cap is modelled.

The conversion decision is a joint one — whether it pays an investor to convert
depends on who else converts — so it is solved by best-response iteration to a
fixed point, vectorised across companies. Six rounds converge in a handful of
passes; the loop asserts it has settled.

Everything is in dollars, and every array is (n_companies, ...) so a whole cohort
is valued at once.
"""

from __future__ import annotations

import numpy as np

MAX_ITERATIONS = 24


def _payouts(
    exit_value: np.ndarray,
    preference: np.ndarray,
    ownership: np.ndarray,
    common_pct: np.ndarray,
    converted: np.ndarray,
    participating: bool,
) -> tuple[np.ndarray, np.ndarray]:
    """Value the waterfall for a *given* set of conversion choices.

    Args:
        exit_value: (n,) proceeds available to the cap table.
        preference: (n, r) dollar preference of each round; 0 where no round.
        ownership: (n, r) as-converted ownership fraction of each round.
        common_pct: (n,) fraction held as common — founder, pool, secondary buyers.
        converted: (n, r) bool, True where the investor takes common instead.
        participating: whether preferred also shares the residual.

    Returns:
        (investor_payout (n, r), residual_per_common_point (n,))
    """
    takes_pref = ~converted & (preference > 0)

    # Preferences are paid last-round-first. ``junior_due`` is the total
    # preference owed to rounds more senior in the payment queue (higher index).
    due = np.where(takes_pref, preference, 0.0)
    total_due = due.sum(axis=1)
    junior_due = np.cumsum(due[:, ::-1], axis=1)[:, ::-1] - due  # owed to later rounds

    available_to_round = np.maximum(exit_value[:, None] - junior_due, 0.0)
    pref_paid = np.minimum(due, available_to_round)

    residual = np.maximum(exit_value - np.minimum(total_due, exit_value), 0.0)

    # Who shares the residual: common, converted investors, and — under the
    # participating variant — everyone still holding preferred.
    shares_residual = converted | (participating & (preference > 0))
    common_total = common_pct + np.where(shares_residual, ownership, 0.0).sum(axis=1)
    per_point = np.divide(residual, common_total, out=np.zeros_like(residual), where=common_total > 0)

    payout = pref_paid + np.where(shares_residual, ownership, 0.0) * per_point[:, None]
    return payout, per_point


def solve_conversions(
    exit_value: np.ndarray,
    preference: np.ndarray,
    ownership: np.ndarray,
    common_pct: np.ndarray,
) -> np.ndarray:
    """Which investors convert to common, as a best-response fixed point.

    Whether it pays an investor to convert depends on who else converts — a
    conversion enlarges the residual but dilutes the share of it — so the set is
    solved by iterating best responses until nobody wants to move. Exposed so
    the tests can check the fixed point directly.
    """
    n, r = preference.shape
    converted = np.zeros((n, r), dtype=bool)
    payout, _ = _payouts(exit_value, preference, ownership, common_pct, converted, False)

    for _ in range(MAX_ITERATIONS):
        changed = False
        for c in range(r):
            flipped = converted.copy()
            flipped[:, c] = ~flipped[:, c]
            alt, _ = _payouts(exit_value, preference, ownership, common_pct, flipped, False)
            # Strictly better only, so ties do not oscillate.
            better = alt[:, c] > payout[:, c] + 1e-6
            if better.any():
                changed = True
                converted[better, c] = flipped[better, c]
                payout, _ = _payouts(
                    exit_value, preference, ownership, common_pct, converted, False
                )
        if not changed:
            break
    else:  # pragma: no cover - defensive
        raise RuntimeError("waterfall conversion did not reach a fixed point")

    return converted


def exit_waterfall(
    exit_value: np.ndarray,
    preference: np.ndarray,
    ownership: np.ndarray,
    common_pct: np.ndarray,
    *,
    participating: bool = False,
) -> tuple[np.ndarray, np.ndarray]:
    """Distribute ``exit_value`` across the cap table.

    Returns ``(common_proceeds_per_point, investor_payout)`` where the first is
    the dollars accruing to each point of common ownership — multiply by the
    founder's common fraction to get the founder's take.
    """
    exit_value = np.asarray(exit_value, dtype=float)
    preference = np.atleast_2d(np.asarray(preference, dtype=float))
    ownership = np.atleast_2d(np.asarray(ownership, dtype=float))
    common_pct = np.asarray(common_pct, dtype=float)

    if participating:
        # No conversion decision to make: participating preferred takes both.
        converted = np.zeros(preference.shape, dtype=bool)
    else:
        converted = solve_conversions(exit_value, preference, ownership, common_pct)

    payout, per_point = _payouts(
        exit_value, preference, ownership, common_pct, converted, participating
    )
    return per_point, payout


def founder_proceeds(
    exit_value: np.ndarray,
    preference: np.ndarray,
    ownership: np.ndarray,
    founder_pct: np.ndarray,
    other_common_pct: np.ndarray,
    *,
    participating: bool = False,
    carve_out: float = 0.0,
) -> np.ndarray:
    """The founder's dollars out of an exit.

    ``other_common_pct`` is the option pool plus any shares sold in secondary —
    common that is not the founder's, and that dilutes what the founder receives
    from the residual.

    ``carve_out`` is the share of proceeds paid to common ahead of the stack. At
    zero the founder payoff is a step: nothing at all until the preferences are
    covered. Above zero it becomes a ramp, and the founder is paid something on
    every dollar of a sale. Nothing else about the deal changes, which is what
    makes it a clean test of shape against height.
    """
    exit_value = np.asarray(exit_value, dtype=float)
    common_pct = founder_pct + other_common_pct
    founder_share_of_common = np.divide(
        founder_pct, common_pct, out=np.zeros_like(founder_pct), where=common_pct > 0
    )

    carved = carve_out * exit_value
    per_point, _ = exit_waterfall(
        exit_value - carved,
        preference,
        ownership,
        common_pct,
        participating=participating,
    )
    return carved * founder_share_of_common + per_point * founder_pct
