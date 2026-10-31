"""The solve run's settings and its engine registry (#562 S2b; WP number pending).

:class:`SolveSpec` is the engine-side settings object, as
:class:`~rietx.indexing.engines.SearchSpec` is indexing's; its request chair
is :class:`~rietx.solve.solution.SolveSpecSpec`, and the two convert into
each other exactly (``tests/test_solve_entry.py``).

**The engine chooses no search setting** (yue-here/rietx#1224, as #1153
merged it).  Every field that moves what a run computes is the caller's and
has no default: the engine, the seeds and control seeds, the ladder (replicas,
``span``, ``step``), the move set (``swap_every``, ``exchange``), the length
(``sweeps``, ``race_sweeps``), the random-structure count the top temperature
is measured from (``n_random``, :func:`~rietx.solve.tempering.random_spread`'s
``n``), the clustering tolerance (``cluster_tol``,
:func:`~rietx.solve.cluster.cluster`'s ``tol``), the polish's iteration cap
(``polish_maxiter``) and the base ``seed``.  A missing one is a
``TypeError``; an impossible one is refused here, by name, before any unit
runs.  The three defaulted fields decide only when a run talks, writes or
stops, never what a unit computes, and each default is the off state: no
heartbeat, a checkpoint at every boundary (no throttle), no ceiling.  The
result records the spec it ran (``SolutionResult.spec``).

**Seeds are indices, and a unit's generator is derived, never hashed**
(:func:`unit_seed`): unit k of kind K draws from
``numpy.random.SeedSequence([spec.seed, K, k])``, so seed 2 runs the same chain
in a four-seed run and in a process that runs seed 2 alone, which is what lets
:func:`~rietx.solve.workflow.merge_seed_results` reproduce the in-process
consensus from per-seed results.  Python's ``hash()`` of a name is salted per
process and is never used (indexing's ``SearchSpec.seed`` rule).

**The registry** lists the engines a run may name, each with one line saying
what it suits; ``capabilities().solve_engines`` quotes it live.  One engine
today, ``tempering`` (S2a's parallel tempering); charge flipping is S6's.

Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field, fields

import numpy as np

#: Unit kinds in the derived generator seed (:func:`unit_seed`): the position
#: of each in this tuple is its code, so the tuple is append-only.
UNIT_KINDS = ("seed", "control", "race", "ladder")


@dataclass(frozen=True)
class SolveSpec:
    """What one solve run is asked to do (field meanings: ``help.SOLVE_FIELD_HELP``;
    module docstring for why the search settings have no default).

    ``sweeps`` is each seed's and control seed's length; ``race_sweeps`` the
    first race round's, doubled each round; ``heartbeat_sweeps`` the
    ``solve_step`` cadence, ``None`` for none; ``checkpoint_every_s`` the
    shortest interval between two checkpoint writes at the engine's
    boundaries (a finished unit always writes; 0 writes at every boundary);
    ``total_budget_seconds`` the whole-run ceiling, ``None`` for none."""

    engine: str
    seeds: tuple[int, ...]
    control_seeds: tuple[int, ...]
    replicas: int
    sweeps: int
    race_sweeps: int
    span: float
    step: tuple[float, float]
    swap_every: int
    exchange: float
    n_random: int
    cluster_tol: float
    polish_maxiter: int
    seed: int
    heartbeat_sweeps: int | None = None
    checkpoint_every_s: float = 0.0
    total_budget_seconds: float | None = None

    def __post_init__(self):
        # seed indices are a set: sorted, so a run and its merge name them alike
        object.__setattr__(self, "seeds", tuple(sorted(self.seeds)))
        object.__setattr__(self, "control_seeds", tuple(sorted(self.control_seeds)))
        object.__setattr__(self, "step", tuple(float(x) for x in self.step))
        if len(set(self.seeds)) != len(self.seeds) or len(set(self.control_seeds)) != len(
                self.control_seeds):
            raise ValueError("a seed index appears twice")
        if self.replicas < 2:
            raise ValueError("a ladder needs at least two replicas")
        for name in ("sweeps", "race_sweeps", "polish_maxiter"):
            v = getattr(self, name)
            if not (v >= 1 and int(v) == v):
                raise ValueError(f"{name} {v!r} must be a whole number, at least 1")
        if self.heartbeat_sweeps is not None and not self.heartbeat_sweeps >= 1:
            raise ValueError(f"heartbeat_sweeps {self.heartbeat_sweeps} must be at least 1, "
                             "or None for no heartbeat")
        if not self.span > 1.0:
            raise ValueError(f"span {self.span} must be above 1 (top over bottom temperature)")
        if len(self.step) != 2 or not (self.step[0] > 0.0 and self.step[1] > 0.0):
            raise ValueError(f"step {self.step} must be two positive move sizes (Å)")
        if not (self.swap_every >= 1 and int(self.swap_every) == self.swap_every):
            raise ValueError(f"swap_every {self.swap_every!r} must be a whole number of "
                             "sweeps, at least 1")
        if not 0.0 <= self.exchange <= 1.0:
            raise ValueError(f"exchange {self.exchange} is a probability, in [0, 1]")
        if not self.n_random >= 2:
            raise ValueError(f"n_random {self.n_random} must be at least 2: a spread needs "
                             "two random structures")
        if not self.cluster_tol > 0.0:
            raise ValueError(f"cluster_tol {self.cluster_tol} must be a positive RMSD in Å")
        if not self.checkpoint_every_s >= 0.0:
            raise ValueError(f"checkpoint_every_s {self.checkpoint_every_s} must be 0 or more")

    def to_spec_spec(self):
        from .solution import SolveSpecSpec

        return SolveSpecSpec(**{f.name: (list(getattr(self, f.name))
                                         if isinstance(getattr(self, f.name), tuple)
                                         else getattr(self, f.name))
                                for f in fields(self)})


def unit_seed(spec: SolveSpec, kind: str, index: int) -> int:
    """The generator seed of unit ``index`` of ``kind`` (module docstring)."""
    ss = np.random.SeedSequence([int(spec.seed), UNIT_KINDS.index(kind), int(index)])
    return int(ss.generate_state(1, dtype=np.uint32)[0])


# ----------------------------------------------------------------------
# the registry
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class EngineEntry:
    name: str
    description: str
    run: Callable = field(compare=False)


_REGISTRY: dict[str, EngineEntry] = {}


def register_engine(name: str, run: Callable, description: str) -> Callable:
    _REGISTRY[name] = EngineEntry(name, description, run)
    return run


def engine_names() -> tuple[str, ...]:
    """Registered engines, in registration order."""
    _load()
    return tuple(_REGISTRY)


def engine_descriptions() -> dict[str, str]:
    _load()
    return {k: v.description for k, v in _REGISTRY.items()}


def get_engine(name: str) -> EngineEntry:
    _load()
    if name not in _REGISTRY:
        raise ValueError(f"unknown solve engine {name!r}; registered: {sorted(_REGISTRY)}")
    return _REGISTRY[name]


def _load() -> None:
    from . import workflow  # noqa: F401  (registers the engines)


__all__ = ["UNIT_KINDS", "EngineEntry", "SolveSpec", "engine_descriptions", "engine_names",
           "get_engine", "register_engine", "unit_seed"]
