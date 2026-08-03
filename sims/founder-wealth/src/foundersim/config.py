"""Configuration objects, YAML loading, and seed derivation (PRD §7 phase 0).

Every run is fully determined by ``(config, root_seed)``. The config hash and the
resolved seed go into every result file so any number can be traced back to the
parameters that produced it.

Parameter provenance is marked in the comments:

    [table]  taken directly from PRD §3.3 — not ours to tune
    [fit]    tuned during calibration (PRD §4), frozen afterwards
    [sweep]  deliberately uncertain; reported as a curve, never a point (METHOD §9)
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Financing stages, in order. Index into this tuple is the "stage" everywhere
# else in the codebase; a company at stage index s has closed rounds 0..s.
STAGES: tuple[str, ...] = ("pre_seed", "seed", "series_a", "series_b", "series_c", "series_d")
N_STAGES = len(STAGES)
STAGE_IX = {name: i for i, name in enumerate(STAGES)}


@dataclass(frozen=True)
class LatentConfig:
    """What is drawn at founding and never observed by anyone (PRD §3.1)."""

    # Lognormal market size. median ~$300M with a heavy right tail: at sigma=1.6
    # the 99th percentile is ~$12B and the 99.9th ~$42B.  [fit]
    market_median: float = 300e6
    market_sigma: float = 1.6

    # Beta(2,5): most ideas are mediocre.  [table]
    fit_a: float = 2.0
    fit_b: float = 5.0

    # Beta(5,5): skill is symmetric around the middle.  [table]
    skill_a: float = 5.0
    skill_b: float = 5.0

    # Annual lognormal shock on customer acquisition — the "luck" that is shared
    # between arms of the counterfactual.  [fit]
    exec_sigma: float = 0.40


@dataclass(frozen=True)
class BusinessConfig:
    """Business dynamics (PRD §3.2). No capital-structure terms appear here."""

    price: float = 12_000.0  # annual contract value  [fit]
    gross_margin: float = 0.78  # SaaS  [table]

    # new_customers = growth_scale * fit * skill * (spend/$1M)^alpha * (1-penetration)
    # growth_scale is customers per $1M of sales spend at fit*skill = 1.  [fit]
    growth_scale: float = 420.0
    spend_alpha: float = 0.80  # concave returns to spend  [table: "f is concave"]

    # Word of mouth: growth that money cannot buy and does not need to.  [fit]
    # new_organic = organic_scale * fit * skill * customers
    organic_scale: float = 2.6

    # Founder effort: customers won by selling rather than by spending. Without
    # this a bootstrapped company cannot start at all, because its growth engine
    # is the founder's time and not its cash. Applies in every arm — a funded
    # founder sells too — so it does not favour one path.  [fit]
    effort_scale: float = 10.0

    # churn = churn_hi - churn_fit_slope * fit, i.e. worse at low fit.  [fit]
    # At the population mean fit (0.286) this is 19.6%; the PRD's 12% headline
    # corresponds to a well-fit company (fit ~ 0.55).
    churn_hi: float = 0.28
    churn_fit_slope: float = 0.30

    # Delivery capacity. revenue_per_head $180k / price $12k = 15 customers/head.
    customers_per_head: float = 15.0  # [table]
    cost_per_head: float = 190_000.0  # fully loaded  [table]

    # Understaffing is how a cash-poor company is punished: it cannot onboard,
    # and the customers it has leave faster. This is the channel through which
    # capital can genuinely *create* value (PRD §8, METHOD §3) — swept.
    understaffing_churn: float = 0.25  # [sweep] extra annual churn at zero capacity
    understaffing_growth: float = 1.00  # [sweep] fraction of new customers lost

    # Unclaimed market decays: what you do not take, a competitor does. This is
    # the speed premium, and the second channel by which capital creates value.
    market_decay: float = 0.06  # [sweep]

    # Companies that have raised a Series A can buy execution: better staff,
    # better tooling. Multiplier on growth_scale. Swept including zero.
    capital_execution_boost: float = 0.15  # [sweep]

    # --- hiring as a growth channel ----------------------------------------
    # The model as calibrated has exactly one way for money to buy growth: sales
    # spend. Employees only add capacity to *serve* customers already won, so a
    # company with four customers needs none, and hiring cannot make it grow
    # faster. That is the wrong shape for the founder who says "I cannot grow
    # because I cannot hire", so the channel is here — defaulted off, because
    # turning it on is an assumption and not a measurement.
    #
    #   growth_hire_share            how much of the money deployed goes to
    #                                people rather than marketing
    #   team_acquisition_efficiency  what a dollar of payroll buys, as a
    #                                fraction of what a dollar of marketing
    #                                buys. 1.0 means a hire is exactly as good
    #                                at winning customers as an ad. 0 means the
    #                                model as calibrated.
    #
    # Both are [sweep]: the honest output is not "hiring pays" but "hiring has
    # to be worth this much before it pays".
    growth_hire_share: float = 0.0  # [sweep]
    team_acquisition_efficiency: float = 0.0  # [sweep]

    founder_savings: float = 50_000.0  # what a bootstrapper starts with  [fit]


@dataclass(frozen=True)
class SpendConfig:
    """How much a company puts into sales each year (PRD §3.2)."""

    # Funded companies spend ahead of revenue: a fraction of cash on hand per year.
    funded_spend_rate: float = 0.35  # [fit]
    # Bootstrappers can only spend what they generate, keeping a reserve.
    boot_reinvest_frac: float = 0.60  # [fit]
    boot_reserve_months: float = 6.0  # [fit]
    # Willingness to run cash down while hiring.
    funded_burn_frac: float = 0.50  # [fit]
    boot_burn_frac: float = 0.10  # [fit]
    # A company with no further rounds coming spends its remaining capital more
    # slowly: it has to reach profitability with it.
    patient_spend_rate: float = 0.18  # [fit]


@dataclass(frozen=True)
class StageTerms:
    """One row of the PRD §3.3 round table.  [table]

    ``pre_money = max(pre_money_base, arr * arr_multiple) * noise`` — early rounds
    are priced off the base (nobody prices a seed off ARR), later ones off metrics.
    ``raise_ratio`` is the round size as a fraction of pre-money, which is what
    keeps dilution roughly constant per stage.
    """

    gate_arr: float
    gate_growth: float  # required YoY revenue multiple; 0 for the first rounds
    raise_ratio: float
    pre_money_base: float
    arr_multiple: float
    pool_refresh: float  # new option pool as a fraction of post-money, created pre-money
    founder_salary: float


# Reproduces the PRD §3.3 table: pre-seed $0.5M on $4M (13% incl. pool), seed
# $3M on $12M (22%), A $12M on $45M (23%), B $35M on $150M (21%), C $80M on
# $500M (15%), D $150M on $1.2B (12%).
DEFAULT_STAGE_TERMS: tuple[StageTerms, ...] = (
    StageTerms(0.0, 0.00, 0.125, 4e6, 12.0, 0.020, 90_000.0),
    StageTerms(150e3, 1.30, 0.250, 12e6, 40.0, 0.020, 150_000.0),
    StageTerms(1.5e6, 2.00, 0.267, 45e6, 30.0, 0.020, 180_000.0),
    StageTerms(6e6, 2.00, 0.233, 150e6, 25.0, 0.020, 220_000.0),
    StageTerms(18e6, 1.70, 0.160, 500e6, 22.0, 0.010, 260_000.0),
    StageTerms(45e6, 1.50, 0.125, 1200e6, 20.0, 0.010, 300_000.0),
)


# The same table for the small-cap world: companies that top out around $50M of
# revenue, where a $100M round does not exist. Grounded in 2025-26 medians
# rather than on the headline venture ladder above.
#
#   pre-seed  $1.0M on $5.0M pre    16.7% + 2% pool = 18.7%   (real: 15-20%)
#   seed      $3.2M on $13.0M pre   19.8% + 2%      = 21.8%   (Carta: ~19.5% + pool)
#   series A  $11M  on $40M pre     21.6% + 2%      = 23.6%   (real: 18-22% + pool)
#   series B  $32M  on $120M pre    21.1% + 2%      = 23.1%   (real: 20-25%)
#
# Series C and D are removed entirely: they are not reachable for these
# companies, and leaving them in was the single biggest source of fantasy in the
# headline configuration.
SMALLCAP_STAGE_TERMS: tuple[StageTerms, ...] = (
    # arr_multiple is 12x rather than 0 on this first row: a pre-seed for a
    # company with no revenue is priced off the base, but a founder who waited
    # and arrived with a business built is not raising at a flat $5M. Leaving it
    # at zero priced a $1M-revenue company as though it had none. This only ever
    # binds for companies that delay their first round — no arm in the
    # calibration reaches this row with revenue, and every calibrated result is
    # bit-identical either way, which a test asserts.
    StageTerms(0.0, 0.00, 0.200, 5e6, 12.0, 0.020, 80_000.0),
    StageTerms(150e3, 1.30, 0.246, 13e6, 35.0, 0.020, 130_000.0),
    StageTerms(1.5e6, 2.00, 0.275, 40e6, 20.0, 0.020, 175_000.0),
    StageTerms(6e6, 1.80, 0.267, 120e6, 16.0, 0.020, 210_000.0),
)


@dataclass(frozen=True)
class CapitalConfig:
    """Rounds, dilution, preferences (PRD §3.3)."""

    stage_terms: tuple[StageTerms, ...] = DEFAULT_STAGE_TERMS

    pref_multiple: float = 1.0  # [sweep] 1x, 1.5x, 2x
    participating: bool = False  # [sweep] rarer but brutal

    # Management carve-out: a share of the proceeds paid to common off the top,
    # ahead of the preference stack. This is the ramp-versus-step lever. The
    # preference *multiple* sets how high the founder's bar is; the carve-out
    # sets whether clearing it is all-or-nothing. v1.0 found those were separate
    # effects, and this is where that claim gets tested in a domain where the
    # step is written into a contract rather than a rulebook.
    carve_out: float = 0.0  # [sweep]

    # Investors are noisier than a metrics threshold (PRD §8). A company clears
    # the gate if arr >= gate_arr * u with u lognormal; sigma 0 recovers a hard
    # threshold.
    gate_noise_sigma: float = 0.35  # [sweep]
    price_noise_sigma: float = 0.35  # [fit] dispersion in round pricing

    # Founder secondary at Series C and later (PRD §3.5).
    secondary_min_stage: int = 4
    secondary_prob: float = 0.35  # [sweep]
    secondary_frac: float = 0.03  # fraction of the company the founder may sell
    secondary_cap: float = 8e6  # dollars

    # Null control (PRD §5.2): raises give cash but no dilution and no preference.
    null_control: bool = False


@dataclass(frozen=True)
class ExitConfig:
    """Liquidity events and how they are valued (PRD §3.4, §3.5)."""

    horizon_years: int = 12  # [table]

    # Revenue multiple: base for a flat company, rising with growth.
    base_revenue_multiple: float = 3.5  # [fit]
    growth_premium: float = 4.0  # [fit] multiple added per 1.0 of YoY growth above flat

    # The multiple also scales with the company, because the buyer pool does. At
    # $1-3M ARR the only bidders are individuals and search funds, and deals
    # clear at 2-4x ARR; by $5-15M, private equity platforms compete and 5-8x is
    # reachable on the same growth rate. Added per base-10 decade of ARR above
    # `scale_pivot_arr`. Zero recovers a size-blind market, which is what the
    # first version of this model assumed and is wrong for small companies.
    #   source: lower-middle-market SaaS multiple surveys, 2025-26
    scale_premium: float = 0.0  # [fit]
    scale_pivot_arr: float = 1e6

    min_revenue_multiple: float = 1.0  # [fit]
    max_revenue_multiple: float = 16.0  # [fit]

    # --- the low end of the market -----------------------------------------
    # Below roughly $10M of enterprise value the market does not price on
    # revenue at all; it prices on earnings, and the multiple it pays climbs
    # steeply with size. IBBA/M&A Source Market Pulse Q3 2025 medians:
    #
    #     < $500K    2.0x        }
    #     $500K-$1M  2.5x        }  of SELLER'S DISCRETIONARY EARNINGS
    #     $1M-$2M    3.0x        }
    #     $2M-$5M    4.0x        }  of EBITDA
    #     $5M-$50M   6.5x        }
    #
    # The break at $2M is a real convention, not a smoothing artefact: below it
    # the buyer is an individual purchasing an owner-operated business, and the
    # quoted earnings figure adds the owner's salary back. Above it the buyer is
    # an institution that will hire a manager, and it does not.
    #
    # Modelled as a log-linear multiple in earnings, which reproduces three of
    # those four points within 0.1x:
    #     multiple = base + slope * log10(earnings / pivot)
    earnings_pivot: float = 250_000.0
    base_earnings_multiple: float = 2.0  # [fit]
    earnings_multiple_slope: float = 3.0  # [fit] per decade of earnings
    min_earnings_multiple: float = 1.5
    max_earnings_multiple: float = 8.0  # [fit]

    # Below this valuation the seller's-discretionary-earnings convention
    # applies and the founder's own salary is added back.
    sde_ceiling: float = 2e6
    exit_noise_sigma: float = 0.45  # [fit]
    regime: float = 1.0  # [sweep] bull/bear multiple regime

    # A company still private and unsold at the horizon has not found a buyer.
    # Marking it at a full multiple would hand every survivor a free liquidity
    # event, which is the most unrealistic thing a fixed-horizon model can do.
    # Applied identically in every arm.
    horizon_illiquidity_discount: float = 0.30  # [sweep]

    # An acquisition offer arrives with this annual probability once a company is
    # material; a company takes it when it is out of gas (growth below the bar it
    # would need to raise again).
    offer_prob: float = 0.18  # [fit]
    offer_min_arr: float = 1e6
    # "Out of gas": growth below this is when a company takes the offer. Applied
    # identically in every arm, so the exit rule cannot favour one of them.
    stall_growth: float = 1.35  # [fit]

    # Founders quit. A business that cannot pay its founder and is not growing
    # gets abandoned after a few years — that is what "the company died" means
    # for a bootstrapper, and it is the mechanism that stops the model producing
    # immortal zero-revenue zombies. Swept, because it moves the answer.
    abandon_income: float = 60_000.0  # [sweep]
    abandon_years: int = 4  # [sweep]
    abandon_growth: float = 1.20  # [sweep] still growing? then they keep going
    # ... but growth from a trivial base is not progress. A founder persists only
    # if the business is both growing fast *and* adding real revenue.

    # Big companies have liquidity events whether or not they have stalled: they
    # go public, or someone buys them mid-flight. Without this every large exit
    # lands on the horizon and the model cannot reproduce a 7-10 year time to
    # exit.
    large_liquidity_prob: float = 0.22  # [fit]
    large_liquidity_arr: float = 25e6  # [fit]

    # Acquihire on death (PRD §3.4): small probability, scaled by team size.
    acquihire_prob_per_head: float = 0.004  # [fit]
    acquihire_prob_cap: float = 0.30
    acquihire_value_per_head: float = 750_000.0  # [fit] returns preference, not much else


@dataclass(frozen=True)
class LedgerConfig:
    """The founder's ledger (PRD §3.5)."""

    discount_rate: float = 0.08  # [fit]
    opportunity_cost: float = 300_000.0  # [sweep] $250-400k/yr forgone salary

    # Founder pay uses one policy in every arm: a market salary that scales with
    # the business, floored at subsistence and capped. A founder who has raised
    # is additionally guaranteed their stage's salary, because that is exactly
    # what investor cash buys — pay before there is revenue to pay from.
    #
    # Two different policies here would be fatal. An earlier version had the
    # bootstrapper take a share of profit while funded founders took a stage
    # salary, and the resulting income gap fed straight into the abandonment
    # rule: identical businesses failed at 80% or at 3% depending only on which
    # policy applied to them. See FINDINGS.md.
    salary_revenue_share: float = 0.10  # [fit]
    salary_floor: float = 40_000.0  # subsistence — taken even when it hurts
    salary_cap: float = 400_000.0

    # Distributions: a profitable, unlevered company pays out surplus cash.
    distribution_frac: float = 0.60
    distribution_reserve_months: float = 6.0

    # What counts as "profitable after paying yourself". A one-person business
    # covering a $40k draw is technically profitable and nobody would call it
    # that, so the test is whether the company can pay the founder a real salary
    # and still be in the black. [sweep] — the answer moves with it.
    profit_test_salary: float = 100_000.0

    tax_rate_income: float = 0.37  # [fit] salary and distributions
    tax_rate_capital: float = 0.20  # [fit] exit and secondary proceeds


@dataclass(frozen=True)
class RunConfig:
    """A complete run."""

    n_founders: int = 5_000
    n_replicates: int = 8
    root_seed: int = 20260803

    latents: LatentConfig = field(default_factory=LatentConfig)
    business: BusinessConfig = field(default_factory=BusinessConfig)
    spend: SpendConfig = field(default_factory=SpendConfig)
    capital: CapitalConfig = field(default_factory=CapitalConfig)
    exit: ExitConfig = field(default_factory=ExitConfig)
    ledger: LedgerConfig = field(default_factory=LedgerConfig)

    # ---- serialisation -----------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return _as_plain(asdict(self))

    def to_yaml(self, path: str | Path) -> None:
        Path(path).write_text(yaml.safe_dump(self.to_dict(), sort_keys=True))

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> RunConfig:
        return _build(cls, data)

    @classmethod
    def from_yaml(cls, path: str | Path) -> RunConfig:
        return cls.from_dict(yaml.safe_load(Path(path).read_text()) or {})

    def hash(self) -> str:
        blob = json.dumps(self.to_dict(), sort_keys=True).encode()
        return hashlib.sha256(blob).hexdigest()[:16]

    def replace(self, **kwargs: Any) -> RunConfig:
        """Nested override: ``cfg.replace(business__market_decay=0.0)``."""
        data = self.to_dict()
        for key, value in kwargs.items():
            node = data
            *path, leaf = key.split("__")
            for part in path:
                node = node[part]
            if leaf not in node:
                raise KeyError(f"unknown config field: {key}")
            node[leaf] = value
        return RunConfig.from_dict(data)


def _as_plain(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _as_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_as_plain(v) for v in obj]
    if isinstance(obj, (np.floating, np.integer)):
        return obj.item()
    return obj


# ``from __future__ import annotations`` turns field types into strings, so the
# nesting is declared here by name rather than recovered by introspection.
_NESTED: dict[str, type] = {
    "latents": LatentConfig,
    "business": BusinessConfig,
    "spend": SpendConfig,
    "capital": CapitalConfig,
    "exit": ExitConfig,
    "ledger": LedgerConfig,
}


def _build(cls: type, data: dict[str, Any]) -> Any:
    """Rebuild a nested dataclass tree from plain dicts."""
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise KeyError(f"unknown config fields for {cls.__name__}: {sorted(unknown)}")

    kwargs: dict[str, Any] = {}
    for name, value in data.items():
        if name in _NESTED and isinstance(value, dict):
            sub = dict(value)
            if name == "capital" and sub.get("stage_terms"):
                terms = sub["stage_terms"]
                if isinstance(terms[0], dict):
                    sub["stage_terms"] = tuple(StageTerms(**t) for t in terms)
                else:
                    sub["stage_terms"] = tuple(terms)
            kwargs[name] = _NESTED[name](**sub)
        else:
            kwargs[name] = value
    return cls(**kwargs)


def seed_for(root_seed: int, *labels: Any) -> int:
    """Derive an independent stream seed from a root seed and a label path.

    Every random draw in the codebase names its purpose, so adding a new draw
    cannot shift the numbers an existing one produces.
    """
    key = "|".join(str(x) for x in labels).encode()
    digest = hashlib.sha256(key + b"::" + str(root_seed).encode()).digest()
    return int.from_bytes(digest[:8], "big") % (2**63 - 1)


def rng_for(root_seed: int, *labels: Any) -> np.random.Generator:
    return np.random.default_rng(seed_for(root_seed, *labels))
