"""Configuration objects, YAML loading, and seed derivation.

Every run is fully determined by (config, root_seed). The config hash and the
resolved seed go into the run manifest so any figure can be traced back to the
exact parameters that produced it (PLAN.md §8).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field, fields, is_dataclass
from pathlib import Path
from typing import Any

import numpy as np
import yaml

# Attribute and strategy vectors are stored as plain 2-D float arrays; these
# name the columns. Order is part of the on-disk format — append, never reorder.
ATTRIBUTES: tuple[str, ...] = (
    "offense",
    "defense",
    "risk_capacity",
    "adaptability",
    "stamina",
)

STRATEGY: tuple[str, ...] = (
    "aggression",
    "off_emphasis",
    "def_emphasis",
    "tempo",
    "margin_seeking",
    "endgame_conservatism",
)

ATTR_IX = {name: i for i, name in enumerate(ATTRIBUTES)}
STRAT_IX = {name: i for i, name in enumerate(STRATEGY)}

N_ATTRIBUTES = len(ATTRIBUTES)
N_STRATEGY = len(STRATEGY)


@dataclass(frozen=True)
class MatchConfig:
    """Parameters of the possession-level match engine (PLAN.md §5).

    The engine is reward-blind: nothing here may reference a win threshold.
    """

    # Possessions per game: base + tempo_scale * mean(tempo of both teams).
    base_possessions: float = 60.0
    tempo_scale: float = 40.0

    # Per-possession expected points. `skill_scale` converts an offense-vs-defense
    # skill differential into a multiplier on `base_points`.
    base_points: float = 1.05
    skill_scale: float = 0.55

    # Aggression beyond a team's risk_capacity costs efficiency, quadratically.
    # This is the price of buying variance.
    overreach_penalty: float = 0.90  # kappa

    # Aggression always inflates per-possession variance, linearly.
    base_variance: float = 0.65  # v0
    variance_gain: float = 2.20  # gamma

    # Game is split into segments so endgame behaviour is expressible.
    n_segments: int = 4

    # In the final segment, a leading team may damp variance (endgame_conservatism)
    # or keep pressing (margin_seeking). Both act on the variance multiplier.
    endgame_variance_damp: float = 0.55
    endgame_mean_cost: float = 0.06
    margin_seek_variance_gain: float = 0.35

    # Fatigue accumulates across a tournament run. Aggression amplifies the cost;
    # the stamina attribute damps it.
    fatigue_per_game: float = 0.030
    fatigue_aggression_gain: float = 0.55
    fatigue_stamina_damp: float = 0.80


@dataclass(frozen=True)
class LeagueConfig:
    """A league differs from another *only* by `win_threshold`."""

    name: str
    win_threshold: int


@dataclass(frozen=True)
class LearningConfig:
    """Fast channel: (1+1)-ES on the strategy vector (PLAN.md §5).

    Sized against a measured constraint, not a guess. `scripts/probe_mechanism.py`
    shows the aggression edge under a threshold-5 reward is ~3 percentage points,
    which needs ~1,900 games per arm for a 2-sigma read. No practical per-team
    window gets there, so this channel is a fine-tuner; population selection is
    the primary driver of divergence (PLAN.md §5, Phase 1 findings).
    """

    # Reward is binary and noisy, so a candidate is judged over many games --
    # roughly ten seasons' worth, spanning season boundaries.
    eval_window: int = 150
    # Mutation step, scaled per-team by the adaptability attribute.
    step_size: float = 0.06
    step_adaptability_gain: float = 1.5


@dataclass(frozen=True)
class EvolutionConfig:
    """Slow channel: between-season selection and reproduction (PLAN.md §5).

    `attr_mutation` vs `strategy_mutation` is the skill-cost / variance-cost knob
    that H3 turns on.
    """

    replace_fraction: float = 0.20
    attr_mutation: float = 0.02
    strategy_mutation: float = 0.04
    # sum(attributes) is renormalised to this after every mutation, so evolution
    # must allocate rather than accumulate (PLAN.md D2).
    attribute_budget: float = 2.50
    attr_min: float = 0.05
    attr_max: float = 0.95


@dataclass(frozen=True)
class TournamentConfig:
    """Regular season (equal games for all) then a single-elimination bracket."""

    n_teams: int = 64
    regular_season_games: int = 12


@dataclass(frozen=True)
class RunConfig:
    """A complete experiment: N seasons x N replicate seeds x M leagues."""

    name: str = "baseline"
    seasons: int = 500
    replicates: int = 30
    root_seed: int = 20260801
    leagues: tuple[LeagueConfig, ...] = (
        LeagueConfig("A", 1),
        LeagueConfig("B", 5),
    )
    match: MatchConfig = field(default_factory=MatchConfig)
    learning: LearningConfig = field(default_factory=LearningConfig)
    evolution: EvolutionConfig = field(default_factory=EvolutionConfig)
    tournament: TournamentConfig = field(default_factory=TournamentConfig)
    output_dir: str = "results"

    def __post_init__(self) -> None:
        t = self.tournament
        if t.n_teams < 2 or (t.n_teams & (t.n_teams - 1)) != 0:
            raise ValueError(f"n_teams must be a power of two, got {t.n_teams}")
        if not self.leagues:
            raise ValueError("at least one league is required")
        names = [lg.name for lg in self.leagues]
        if len(set(names)) != len(names):
            raise ValueError(f"league names must be unique, got {names}")
        e = self.evolution
        if not 0.0 < e.replace_fraction < 0.5:
            raise ValueError("replace_fraction must be in (0, 0.5)")
        if not e.attr_min * N_ATTRIBUTES <= e.attribute_budget <= e.attr_max * N_ATTRIBUTES:
            raise ValueError(
                f"attribute_budget {e.attribute_budget} is unreachable given "
                f"attr bounds [{e.attr_min}, {e.attr_max}] over {N_ATTRIBUTES} attributes"
            )

    # -- serialisation -------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        return _to_plain(self)

    def hash(self) -> str:
        """Stable content hash, used to tie results back to their config."""
        blob = json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(blob.encode()).hexdigest()[:16]


_NESTED: dict[str, type] = {
    "match": MatchConfig,
    "learning": LearningConfig,
    "evolution": EvolutionConfig,
    "tournament": TournamentConfig,
}


def _to_plain(obj: Any) -> Any:
    if is_dataclass(obj) and not isinstance(obj, type):
        return {f.name: _to_plain(getattr(obj, f.name)) for f in fields(obj)}
    if isinstance(obj, (list, tuple)):
        return [_to_plain(v) for v in obj]
    return obj


def _check_keys(cls: type, data: dict[str, Any]) -> None:
    known = {f.name for f in fields(cls)}
    unknown = set(data) - known
    if unknown:
        raise ValueError(f"unknown key(s) for {cls.__name__}: {sorted(unknown)}")


def run_config_from_dict(data: dict[str, Any]) -> RunConfig:
    """Build a RunConfig from a plain dict, rejecting unknown keys.

    Silent typo-tolerance in a config loader means a swept parameter can quietly
    fail to apply, so unknown keys are an error.
    """
    data = dict(data)
    _check_keys(RunConfig, data)

    for key, cls in _NESTED.items():
        if key in data:
            sub = data[key]
            if not isinstance(sub, dict):
                raise ValueError(f"'{key}' must be a mapping, got {type(sub).__name__}")
            _check_keys(cls, sub)
            data[key] = cls(**sub)

    if "leagues" in data:
        leagues = data["leagues"]
        if not isinstance(leagues, list):
            raise ValueError("'leagues' must be a list")
        parsed = []
        for lg in leagues:
            _check_keys(LeagueConfig, lg)
            parsed.append(LeagueConfig(**lg))
        data["leagues"] = tuple(parsed)

    return RunConfig(**data)


def load_config(path: str | Path) -> RunConfig:
    with open(path) as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: top level must be a mapping")
    return run_config_from_dict(data)


def load_run_config(run_dir: str | Path) -> RunConfig:
    """Recover the exact config a results directory was produced with.

    Analysis scripts must never assume which config a run used — reading it back
    from the manifest is what keeps a figure tied to the run it came from.
    """
    manifest = json.loads((Path(run_dir) / "manifest.json").read_text())
    return run_config_from_dict(manifest["config"])


def dump_config(cfg: RunConfig, path: str | Path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as fh:
        yaml.safe_dump(cfg.to_dict(), fh, sort_keys=False)


# -- seeding -----------------------------------------------------------------
#
# All randomness derives from a single root seed via SeedSequence.spawn_key, so
# a run is reproducible and no component ever touches the global RNG.
#
# Crucially, the *initial population* seed depends on the replicate only -- not
# on the league. Both leagues therefore start from byte-identical arrays, which
# is what makes "the reward function is the only difference" literally true
# rather than merely statistically true (PLAN.md §8).


def population_seed(cfg: RunConfig, replicate: int) -> np.random.SeedSequence:
    """Seed for initial population creation. Deliberately league-independent."""
    return np.random.SeedSequence([cfg.root_seed, replicate, 0])


def league_seed(cfg: RunConfig, replicate: int, league_index: int) -> np.random.SeedSequence:
    """Seed for a league's simulation stream (matches, learning, evolution)."""
    return np.random.SeedSequence([cfg.root_seed, replicate, 1, league_index])


def rng(seed: np.random.SeedSequence) -> np.random.Generator:
    return np.random.Generator(np.random.PCG64(seed))
