"""Fast channel: per-team (1+1) evolution strategy on the strategy vector.

Each team alternates between evaluating its **incumbent** strategy and a mutated
**candidate**, ``eval_window`` games each. Whichever scores higher becomes the
new incumbent, and a fresh candidate is drawn.

This channel is deliberately modest. The measured reward edge from buying
variance is ~3 percentage points, which needs ~1,900 games per arm for a 2-sigma
read (`scripts/probe_mechanism.py`), so no realistic window makes a single team a
reliable optimiser. Population selection in `evolution.py` is the primary driver;
this is a fine-tuner that adds within-lifetime adaptation without pretending to
more precision than the signal supports.
"""

from __future__ import annotations

import numpy as np

from .config import N_STRATEGY, STRAT_IX, LearningConfig
from .population import Population

_EVALUATING_INCUMBENT = 0
_EVALUATING_CANDIDATE = 1


class Learner:
    """Per-team (1+1)-ES state. Writes the active strategy into the population."""

    def __init__(self, pop: Population, cfg: LearningConfig, rng: np.random.Generator):
        n = pop.n_teams
        self.cfg = cfg
        self.rng = rng

        self.incumbent = pop.strategy.copy()
        self.candidate = self._mutate(self.incumbent, pop)

        self.phase = np.zeros(n, dtype=np.int8)
        self.games = np.zeros(n, dtype=np.int64)
        self.reward = np.zeros(n, dtype=np.float64)

        # Score of the incumbent from its last completed evaluation. Seeded
        # negative so the first completed incumbent window always registers.
        self.incumbent_score = np.full(n, -1.0)

        self._apply(pop)

    # -- internals -----------------------------------------------------------

    def _step_size(self, pop: Population) -> np.ndarray:
        """Adaptable teams take bigger exploratory steps."""
        adaptability = pop.attr("adaptability")[:, None]
        return self.cfg.step_size * (1.0 + self.cfg.step_adaptability_gain * adaptability)

    def _mutate(self, base: np.ndarray, pop: Population) -> np.ndarray:
        step = self._step_size(pop)
        return np.clip(base + self.rng.normal(0.0, 1.0, size=base.shape) * step, 0.0, 1.0)

    def _apply(self, pop: Population) -> None:
        """Push the strategy currently under evaluation into the population."""
        active = np.where(
            (self.phase == _EVALUATING_INCUMBENT)[:, None], self.incumbent, self.candidate
        )
        pop.strategy[:] = active

    # -- public API ----------------------------------------------------------

    def record(self, teams: np.ndarray, rewards: np.ndarray) -> None:
        """Accumulate game outcomes. A team may appear more than once per batch."""
        np.add.at(self.reward, teams, rewards)
        np.add.at(self.games, teams, 1)

    def settle(self, pop: Population) -> None:
        """Close out any completed evaluation windows and advance the search."""
        done = self.games >= self.cfg.eval_window
        if not done.any():
            return

        score = np.divide(
            self.reward, self.games, out=np.zeros_like(self.reward), where=self.games > 0
        )

        # An incumbent window just re-measures the incumbent (its reward rate
        # drifts as opponents evolve, so a stale score would be misleading).
        finished_incumbent = done & (self.phase == _EVALUATING_INCUMBENT)
        self.incumbent_score = np.where(finished_incumbent, score, self.incumbent_score)

        # A candidate window is a decision point: adopt only on a strict win.
        finished_candidate = done & (self.phase == _EVALUATING_CANDIDATE)
        adopt = finished_candidate & (score > self.incumbent_score)
        self.incumbent = np.where(adopt[:, None], self.candidate, self.incumbent)
        self.incumbent_score = np.where(adopt, score, self.incumbent_score)

        # Draw a fresh candidate for every team that just finished a candidate run.
        fresh = self._mutate(self.incumbent, pop)
        self.candidate = np.where(finished_candidate[:, None], fresh, self.candidate)

        self.phase = np.where(done, 1 - self.phase, self.phase).astype(np.int8)
        self.games = np.where(done, 0, self.games)
        self.reward = np.where(done, 0.0, self.reward)

        self._apply(pop)

    def reset_teams(self, teams: np.ndarray, strategy: np.ndarray, pop: Population) -> None:
        """Re-seed learner state for teams replaced by reproduction."""
        if teams.size == 0:
            return
        self.incumbent[teams] = strategy
        self.candidate[teams] = np.clip(
            strategy + self.rng.normal(0.0, 1.0, size=strategy.shape)
            * self._step_size(pop)[teams],
            0.0,
            1.0,
        )
        self.phase[teams] = _EVALUATING_INCUMBENT
        self.games[teams] = 0
        self.reward[teams] = 0.0
        self.incumbent_score[teams] = -1.0
        self._apply(pop)
