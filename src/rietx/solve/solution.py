"""The answer of a structure-solution run (#562 S2b; WP number pending).

**A solution is a list.**  :class:`SolutionResult` mirrors
:class:`~rietx.schemas.indexing.IndexingResult`: ranked
:class:`StructureCandidate`\\ s, each with the engine's evidence, and **no**
``structure`` of its own — the indexing answer carries no ``cell`` for the
same reason (root CLAUDE.md, the four answers are different types).  It
carries **no grade and no singleton accessor** either: which candidate to
believe is a heuristic over this evidence, and lands in its own PR after this
machinery (yue-here/rietx#1224).  The evidence is what
:func:`~rietx.solve.cluster.rank` returns — χ²_data and its ratio to the
Pawley floor, the seeds that reached the cluster and their spread, the margin
to the next candidate, and the leader's distance from the prior-off control
arm's best with that leader's χ²_data — plus ``partial``, a fact about the
run that produced it.

**The evidence row** (:class:`SolveEvidence`, :func:`candidate_evidence`) is
one shape, read by the final answer's :meth:`SolutionResult.evidence` and by
the ``consensus:<space group>`` unit the run streams, never forked
(``schemas.indexing.candidate_evidence``'s rule).

**Records beside candidates.**  :attr:`SolutionResult.records` holds what
every unit did — the race rounds, the seeds and the prior-off control seeds —
and the polished states each seed contributed, so the consensus can be taken
again from the records alone (:func:`~rietx.solve.workflow.merge_seed_results`,
seeds run as separate processes).  Wall-clock time is not a record: it rides
in :attr:`SolutionResult.timings` and :attr:`SolutionResult.provenance`, so two
runs of one seed serialise to the same records and candidates byte for byte
whatever the machine was doing (#998's acceptance).

Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from ..schemas.common import Base
from ..schemas.structure import Phase, Structure

UnitKind = Literal["race", "seed", "control"]
SolveStatus = Literal["done", "cancelled", "budget"]


class SolveSpecSpec(Base):
    """The run's settings as data: the request chair of
    :class:`~rietx.solve.engines.SolveSpec` (``to_spec()`` and
    ``SolveSpec.to_spec_spec()`` are each other's inverse, by test).

    ``seeds`` and ``control_seeds`` are seed *indices*: unit k's generator is
    drawn from ``(seed, kind, k)``, so seed 2 is the same chain in a four-seed
    run and in a process that runs seed 2 alone.  Every search setting is
    required, as on ``SolveSpec`` (``solve.engines``' docstring)."""

    engine: Literal["tempering"]
    seeds: list[int]
    control_seeds: list[int]
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

    def to_spec(self):
        from ..solve.engines import SolveSpec

        return SolveSpec(**{name: (tuple(getattr(self, name))
                                   if isinstance(getattr(self, name), list)
                                   else getattr(self, name))
                            for name in type(self).model_fields})


class SolvedAtom(Base):
    """One atom of a search: what a candidate's structure is built from."""

    label: str
    species: str
    occ: float
    biso: float


class SearchLayout(Base):
    """The atoms one (space group × assignment) search places, in the order
    every coordinate array of its records uses.  ``assignment`` is the index
    into ``site_assignments`` (``None`` when the caller declared the units),
    ``sites`` its (species, class index) pairs."""

    space_group: str
    assignment: int | None
    sites: list[tuple[str, int]] = Field(default_factory=list)
    atoms: list[SolvedAtom]


class PolishedState(Base):
    """A rung's lowest state after the polish, its terms apart."""

    xyz: list[list[float]]
    j: float
    chi2: float
    clash: float


class UnitRecord(Base):
    """What one unit did — deterministic for its seed, so no wall clock here.

    ``stopped`` is ``None`` for a unit that ran its sweeps, ``"cancelled"`` or
    ``"wall_seconds"`` otherwise.  ``best_j`` is each rung's lowest J; a seed or
    control unit also carries its rungs' polished states (``polished``)."""

    unit: str
    kind: UnitKind
    space_group: str
    assignment: int | None
    seed_index: int
    rng_seed: int
    round: int | None = None
    sweeps: int
    sweeps_planned: int
    moves: int
    t_top: float
    temperatures: list[float]
    move_acceptance: list[float]
    swap_attempts: list[int]
    swap_accepts: list[int]
    drift: float
    stopped: str | None = None
    compiled: bool
    best_j: list[float]
    polished: list[PolishedState] = Field(default_factory=list)


class RaceRound(Base):
    """One round of the assignment race: the assignments it ran, each one's
    lowest J, and the ones that went on."""

    round: int
    sweeps: int
    ran: list[int]
    best_j: list[float]
    kept: list[int]


class RaceRecord(Base):
    """The race over one space group's site-class assignments
    (:func:`~rietx.solve.workflow.race_assignments`)."""

    space_group: str
    n_assignments: int
    rounds: list[RaceRound] = Field(default_factory=list)
    winner: int | None = None


class StructureCandidate(Base):
    """One distinct solution: the leader of a cluster, with its evidence.

    ``structure`` is the input phase with the leader's atoms, ready for the
    Rietveld path; it is a candidate's, and the result has none.  ``seeds``
    are the seed indices whose polished states joined the cluster, so
    ``n_finders`` is how many independent starts reached it, and
    ``finder_rmsd`` the largest member's RMSD from the leader after alignment
    (Å).  ``chi2_ratio`` is χ²_data/χ²_floor.  ``control_rmsd_ang`` is the
    leader's RMSD (Å) from the prior-off control arm's best leader and
    ``control_chi2_data`` that leader's χ²_data, both ``None`` when the run
    had no control seeds (:class:`~rietx.solve.cluster.RankedSolution`).
    ``partial`` is true when the run stopped before its units finished."""

    rank: int
    space_group: str
    assignment: int | None
    labels: list[str]
    species: list[str]
    xyz: list[list[float]]
    structure: Structure
    chi2_data: float
    chi2_ratio: float
    clash_raw: float
    j: float
    seeds: list[int]
    n_finders: int
    finder_rmsd: float
    n_members: int
    margin_to_next: float | None
    control_rmsd_ang: float | None
    control_chi2_data: float | None
    partial: bool


class SolveEvidence(Base):
    """The evidence row of one candidate (module docstring)."""

    index: int
    rank: int
    space_group: str
    assignment: int | None
    chi2_data: float
    chi2_ratio: float
    n_finders: int
    finder_rmsd: float
    margin_to_next: float | None
    control_rmsd_ang: float | None
    control_chi2_data: float | None
    partial: bool


def candidate_evidence(index: int, c: StructureCandidate) -> SolveEvidence:
    """The one evidence shape, for the stream and for :meth:`SolutionResult.evidence`."""
    return SolveEvidence(index=index, rank=c.rank, space_group=c.space_group,
                         assignment=c.assignment, chi2_data=c.chi2_data,
                         chi2_ratio=c.chi2_ratio, n_finders=c.n_finders,
                         finder_rmsd=c.finder_rmsd, margin_to_next=c.margin_to_next,
                         control_rmsd_ang=c.control_rmsd_ang,
                         control_chi2_data=c.control_chi2_data, partial=c.partial)


class SolveProvenance(Base):
    """Who ran it and when: kept apart from the records, which are a function
    of the seed alone."""

    package_version: str
    created_utc: str | None = None
    compiled: bool | None = None


class SolutionResult(Base):
    """A structure-solution run's answer (module docstring).

    ``status`` is ``"done"``, ``"cancelled"`` (the caller's token) or
    ``"budget"`` (the run's ceiling); in the last two ``partial`` is true on
    the result and on every candidate, and ``units_not_run``
    names what the run did not reach.  ``search_complete`` says per unit
    whether it ran all its sweeps."""

    candidates: list[StructureCandidate] = Field(default_factory=list)
    engines_run: list[str] = Field(default_factory=list)
    space_groups_searched: list[str] = Field(default_factory=list)
    races: list[RaceRecord] = Field(default_factory=list)
    layouts: list[SearchLayout] = Field(default_factory=list)
    records: list[UnitRecord] = Field(default_factory=list)
    search_complete: dict[str, bool] = Field(default_factory=dict)
    seeds_run: list[int] = Field(default_factory=list)
    control_seeds_run: list[int] = Field(default_factory=list)
    units_not_run: list[str] = Field(default_factory=list)
    status: SolveStatus = "done"
    partial: bool = False
    resumed: bool = False
    spec: SolveSpecSpec
    phase: Phase
    n_reflections: int
    chi2_floor: float
    timings: dict[str, float] = Field(default_factory=dict)
    provenance: SolveProvenance

    def evidence(self) -> list[SolveEvidence]:
        """Every candidate's evidence row, computed on each call."""
        return [candidate_evidence(i, c) for i, c in enumerate(self.candidates)]

    def comparable_json(self) -> str:
        """The serialisation two runs of one seed must agree on byte for byte:
        everything but :attr:`timings`, :attr:`provenance` and :attr:`resumed`
        (#998's acceptance compares this string)."""
        return self.model_dump_json(exclude={"timings", "provenance", "resumed"})


__all__ = ["PolishedState", "RaceRecord", "RaceRound", "SearchLayout", "SolutionResult",
           "SolveEvidence", "SolveProvenance", "SolveSpecSpec", "SolvedAtom",
           "StructureCandidate", "UnitRecord", "candidate_evidence"]
