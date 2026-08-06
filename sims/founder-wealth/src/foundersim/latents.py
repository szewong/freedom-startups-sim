"""What is drawn at founding, and the luck that arrives later (PRD §3.1, §5.1).

Two things live here, and the distinction between them is the whole design:

* **Latents** — market size, product/market fit, founder skill. Drawn once per
  founder, never observed by the founder or their investors, and *identical
  across every arm of the counterfactual*.
* **Noise** — the annual shocks. Also drawn once per founder-year and reused by
  every arm, so the same founder meets the same luck in the same year whichever
  financing path they took (common random numbers, METHOD §5).

Nothing here knows which strategy is being run. That is what makes the fork a
clean counterfactual rather than two independent simulations.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import RunConfig, rng_for


@dataclass(frozen=True)
class Latents:
    """(n,) arrays, one entry per founder."""

    market_size: np.ndarray  # dollars of annual revenue the market can hold
    fit: np.ndarray  # Beta(2,5) — converts spend into growth
    skill: np.ndarray  # Beta(5,5) — execution multiplier

    @property
    def n(self) -> int:
        return self.market_size.shape[0]


@dataclass(frozen=True)
class Noise:
    """(n, years) arrays of shared luck. Every arm reads the same values."""

    execution: np.ndarray  # normal: shock on customer acquisition
    gate_arr: np.ndarray  # normal: how demanding investors are on revenue
    gate_growth: np.ndarray  # normal: ... and on growth
    price: np.ndarray  # normal: round pricing enthusiasm
    offer: np.ndarray  # uniform: does an acquisition offer arrive
    exit_multiple: np.ndarray  # normal: what the acquirer pays
    acquihire: np.ndarray  # uniform: does a soft landing appear
    secondary: np.ndarray  # uniform: is founder secondary allowed in the round


def draw_latents(cfg: RunConfig, replicate: int) -> Latents:
    lc = cfg.latents
    n = cfg.n_founders

    rng = rng_for(cfg.root_seed, replicate, "market_size")
    mu = np.log(lc.market_median)
    market = np.exp(rng.normal(mu, lc.market_sigma, n))

    rng = rng_for(cfg.root_seed, replicate, "fit")
    fit = rng.beta(lc.fit_a, lc.fit_b, n)

    rng = rng_for(cfg.root_seed, replicate, "skill")
    skill = rng.beta(lc.skill_a, lc.skill_b, n)

    return Latents(market_size=market, fit=fit, skill=skill)


def draw_noise(cfg: RunConfig, replicate: int) -> Noise:
    n, t = cfg.n_founders, cfg.exit.horizon_years
    shape = (n, t)

    def normal(label: str) -> np.ndarray:
        return rng_for(cfg.root_seed, replicate, label).normal(0.0, 1.0, shape)

    def uniform(label: str) -> np.ndarray:
        return rng_for(cfg.root_seed, replicate, label).random(shape)

    return Noise(
        execution=normal("execution"),
        gate_arr=normal("gate_arr"),
        gate_growth=normal("gate_growth"),
        price=normal("price"),
        offer=uniform("offer"),
        exit_multiple=normal("exit_multiple"),
        acquihire=uniform("acquihire"),
        secondary=uniform("secondary"),
    )
