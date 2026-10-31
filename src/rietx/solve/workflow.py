"""The structure-solution entry point (#562 S2b; WP number pending).

:func:`solve_structure` takes a cost (:class:`~rietx.solve.cost.SolveCost`,
built from a Pawley or Le Bail fit of the verified cell), the phase that fit
used, what the chemist declares, and returns a
:class:`~rietx.solve.solution.SolutionResult`: ranked candidates with the
engine's evidence, never one structure and never a grade.  Every search
setting is the caller's, in the :class:`~rietx.solve.engines.SolveSpec` it
must pass (that module's docstring): the entry point chooses none, and the
result records the spec it ran.

**Units.**  A run is a flat ladder of units, each a ``stage_start``/
``stage_end`` pair on the event stream (``history/events.py``), the way
indexing's (engine × system) units are:

* ``race:<group>:a<i>:r<k>`` — round k of the **assignment race**
  (:func:`race_assignments`), when a composition rather than explicit units
  was declared and its site-class assignments number more than one;
* ``seed:<group>:a<i>:s<k>`` — seed k of parallel tempering on the race's
  winner, polished (:func:`~rietx.solve.tempering.polish`) rung by rung;
* ``control:<group>:a<i>:s<k>`` — seed k with every prior at zero weight, the
  control arm of #562's amendment (c), read by
  :func:`~rietx.solve.cluster.rank`'s ``control=``;
* ``consensus:<group>`` — the clusters of that group's seeds, ranked with
  their evidence, and streamed in the evidence row's shape
  (:func:`~rietx.solve.solution.candidate_evidence`).

Inside a unit, ``solve_step`` is the heartbeat every ``heartbeat_sweeps``
sweeps, when the spec asks for one.  ``solve_start`` and ``solve_end`` bracket the run.

**The race** is successive halving (Karnin, Koren & Somekh 2013, *ICML*,
Sequential Halving; Jamieson & Talwalkar 2016, *AISTATS*): every assignment
runs ``race_sweeps`` sweeps of one seed; the better half by lowest J goes on,
each continuing its own chain from where it stopped for twice the sweeps, until
one is left.  Only the winner gets the seeds.  Nothing in it reads the
deposited structure, so a recovery measured through it is a recovery from the
composition alone.

**Stopping, the ceiling and resuming** (#998).  One token stops everything:
the caller's ``cancel``, watched for a stop request from ``rietx watch`` when
the run is recorded (``runs.attach_cancel``), wrapped in a
:class:`~rietx.indexing.engines.Deadline` when the spec declares a ceiling.  A
stopped run returns what it has — the finished units and the in-flight seed's
polished best-so-far — with ``partial`` set on the result and on every
candidate, and ``units_not_run`` naming the rest.  With
``checkpoint=`` a run writes, atomically (temp file, flush, fsync, rename),
the finished units' records and the in-flight unit's
:class:`~rietx.solve.tempering.TemperState` at the engine's boundaries, at most
every ``checkpoint_every_s`` and always when a unit finishes.  A call with an
existing checkpoint resumes from it and returns the uninterrupted run's
candidates and records, byte for byte
(:meth:`~rietx.solve.solution.SolutionResult.comparable_json`); a checkpoint
of another cost, another spec or another version is refused by name
(:class:`CheckpointMismatch`).

**Seeds as processes.**  :func:`merge_seed_results` takes per-seed results
(``spec.seeds=(k,)``, ``control_seeds=()`` and the reverse) and takes the
consensus again from their records, which is the in-process run's consensus
over the same seeds (``tests/test_solve_entry.py``).

Nothing here is exported from :mod:`rietx`.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, fields, replace
from pathlib import Path
from typing import Literal

import numpy as np

from ..crystallography.site_classes import site_assignments, site_classes
from ..crystallography.symmetry import resolve_group
from . import cluster as cl
from . import tempering as tp
from .engines import SolveSpec, register_engine, unit_seed
from .moves import Clash, FreeSite, Radiation, Scattering, SearchSpace
from .solution import (
    PolishedState,
    RaceRecord,
    RaceRound,
    SearchLayout,
    SolutionResult,
    SolvedAtom,
    SolveProvenance,
    SolveSpecSpec,
    StructureCandidate,
    UnitRecord,
    candidate_evidence,
)

#: The checkpoint's format; a change to what it holds is a new string.
CHECKPOINT_FORMAT = "rietx-solve-checkpoint/1"

#: The order units take in a result's records.
_KIND_ORDER = {"race": 0, "seed": 1, "control": 2}

#: Spec fields a resume may change: they decide when a run writes, talks or
#: stops, never what a unit computes.
_RESUMABLE_FIELDS = ("heartbeat_sweeps", "checkpoint_every_s", "total_budget_seconds")


class CheckpointMismatch(ValueError):
    """A checkpoint written by another run; ``field`` names what differs:
    ``"version"`` (the format or the package), ``"cost"`` (the data, the
    reflections or the radiation) or ``"spec"`` (the settings, the phase, the
    units or the priors)."""

    def __init__(self, field: Literal["version", "cost", "spec"], message: str):
        super().__init__(message)
        self.field = field


class SolveRefused(ValueError):
    """The run cannot start as asked; the message says why."""


# ----------------------------------------------------------------------
# fingerprints and the checkpoint file
# ----------------------------------------------------------------------
def _digest(*parts) -> str:
    h = hashlib.sha256()
    for p in parts:
        if isinstance(p, np.ndarray):
            h.update(str(p.dtype).encode())
            h.update(str(p.shape).encode())
            h.update(np.ascontiguousarray(p).tobytes())
        else:
            h.update(json.dumps(p, sort_keys=True, default=str).encode())
        h.update(b"|")
    return h.hexdigest()


def cost_fingerprint(cost, radiation: Radiation) -> str:
    """The data side of a run: the reflections, the form and the radiation."""
    m0 = cost.M0.tocsr()
    f_anom = (None if radiation.f_anom is None
              else sorted((k, v.real, v.imag) for k, v in radiation.f_anom.items()))
    return _digest(np.asarray(cost.hkl, dtype=np.float64), np.asarray(cost.d),
                   np.asarray(cost.multiplicity, dtype=np.float64), m0.data, m0.indices,
                   m0.indptr, np.asarray(cost.V), np.asarray(cost.b), float(cost.c),
                   float(cost.chi2_floor), bool(radiation.neutron), f_anom)


def _space_digest(space: SearchSpace) -> list:
    out = []
    for b in space.blocks:
        u = b.unit
        if isinstance(u, FreeSite):
            c = u.site_class
            out.append(["site", u.species, u.label, u.occ, u.biso,
                        np.asarray(c.point, dtype=np.float64).tolist(),
                        np.asarray(c.basis, dtype=np.float64).tolist(), int(c.multiplicity)])
        else:
            out.append(["fragment", list(u.fragment.species),
                        np.asarray(u.fragment.xyz, dtype=np.float64).tolist(), list(u.labels),
                        u.occ, u.biso, [[a, b, list(m)] for a, b, m in u.torsions]])
    return out


def spec_fingerprint(spec: SolveSpec, phase, searches, priors) -> str:
    """The settings side: the spec but :data:`_RESUMABLE_FIELDS`, the cell and
    groups, every search's units and the priors."""
    s = {f.name: getattr(spec, f.name) for f in fields(spec) if f.name not in _RESUMABLE_FIELDS}
    cell = [float(getattr(phase.cell, k).value) for k in ("a", "b", "c", "alpha", "beta",
                                                          "gamma")]
    return _digest(s, cell, [[x.group, x.assignment, _space_digest(x.space)] for x in searches],
                   repr(priors))


def write_checkpoint(path: Path, payload: dict) -> None:
    """Write ``payload`` to ``path`` atomically: a temp file beside it,
    flushed and fsynced, then renamed over it, so a write killed at any point
    leaves the previous checkpoint whole."""
    path = Path(path)
    tmp = path.with_name(f"{path.name}.tmp{os.getpid()}")
    try:
        with open(tmp, "w", encoding="utf-8", newline="\n") as fh:
            json.dump(payload, fh)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def read_checkpoint(path: Path, *, cost_fp: str, spec_fp: str, version: str) -> dict:
    """The checkpoint at ``path``, refused by name unless it is this run's."""
    with open(path, encoding="utf-8") as fh:
        ck = json.load(fh)
    if ck.get("format") != CHECKPOINT_FORMAT or ck.get("package_version") != version:
        raise CheckpointMismatch(
            "version", f"checkpoint {path} was written by {ck.get('format')!r} under rietx "
            f"{ck.get('package_version')!r}; this run is {CHECKPOINT_FORMAT!r} under "
            f"{version!r}. Delete it to start again.")
    if ck.get("cost") != cost_fp:
        raise CheckpointMismatch(
            "cost", f"checkpoint {path} belongs to another cost (its data, reflections or "
            "radiation differ). Delete it to start again.")
    if ck.get("spec") != spec_fp:
        raise CheckpointMismatch(
            "spec", f"checkpoint {path} belongs to another spec (its seeds, sweeps, ladder, "
            "phase, units or priors differ). Delete it to start again.")
    return ck


# ----------------------------------------------------------------------
# one search: a (space group × assignment) problem with its control
# ----------------------------------------------------------------------
@dataclass
class _Search:
    group: str
    assignment: int | None
    sites: list
    space: SearchSpace
    problem: tp.SearchProblem
    control: tp.SearchProblem
    ladder: tp.Ladder
    control_ladder: tp.Ladder

    def layout(self) -> SearchLayout:
        sp = self.space
        return SearchLayout(space_group=self.group, assignment=self.assignment,
                            sites=[(s, int(c)) for s, c in self.sites],
                            atoms=[SolvedAtom(label=lab, species=s, occ=float(o), biso=float(b))
                                   for lab, s, o, b in zip(sp.labels, sp.species, sp.occ,
                                                           sp.biso, strict=True)])


def _group_phase(phase, group: str):
    if group == phase.space_group:
        return phase
    return phase.model_copy(update={"space_group": group, "symmetry_operations": None},
                            deep=True)


def _ladder(problem: tp.SearchProblem, spec: SolveSpec, index: int) -> tp.Ladder:
    rng = np.random.default_rng(unit_seed(spec, "ladder", index))
    t_top, _ = tp.random_spread(problem, rng, n=spec.n_random)
    return tp.Ladder.planned(t_top, problem.space.n_par, spec.replicas, span=spec.span,
                             step=spec.step)


def _searches(cost, phase, instrument, priors, groups, composition, units, spec,
              biso: float) -> list[_Search]:
    out = []
    for gi, g in enumerate(groups):
        ph = _group_phase(phase, g)
        if units is not None:
            sets = [(None, [], list(units))]
        else:
            classes = site_classes(resolve_group(ph.space_group, ph.symmetry_operations))
            assigns = site_assignments(classes, composition)
            if not assigns:
                raise SolveRefused(f"the composition has no placement on the site classes of "
                                   f"{g}")
            sets = []
            for ai, a in enumerate(assigns):
                count: dict[str, int] = {}
                us = []
                for sp, ci in a.sites:
                    count[sp] = count.get(sp, 0) + 1
                    us.append(FreeSite(sp, classes[ci], f"{sp.rstrip('+-0123456789')}"
                                       f"{count[sp]}", 1.0, biso))
                sets.append((ai, list(a.sites), us))
        for ai, sites, us in sets:
            space = SearchSpace(us, ph)
            sc = Scattering(space, cost.hkl, cost.d,
                            Radiation.from_instrument(instrument, space.species))
            problem = tp.SearchProblem(space, sc, cost, Clash.build(space, priors))
            control = tp.SearchProblem(space, sc, cost, Clash.build(space, priors.control()))
            key = 1000 * gi + (ai or 0)
            out.append(_Search(g, ai, sites, space, problem, control, _ladder(problem, spec, key),
                               _ladder(control, spec, 500 + key)))
    return out


# ----------------------------------------------------------------------
# the run's state: records, checkpoint, stream
# ----------------------------------------------------------------------
class _Run:
    def __init__(self, spec, stream, progress, token, deadline, floor, ck_path, header,
                 resumed_from):
        self.spec = spec
        self.stream = stream
        self.progress = progress
        self.token = token
        self.deadline = deadline
        self.floor = floor
        self.ck_path = ck_path
        self.header = header
        self.finished: dict[str, dict] = dict((resumed_from or {}).get("finished", {}))
        cur = (resumed_from or {}).get("current")
        self.current: tuple[str, dict] | None = (cur["unit"], cur["state"]) if cur else None
        self.last_write = time.monotonic()
        self.timings: dict[str, float] = {}
        self.stopped = False
        self.not_run: list[str] = []

    def save(self, current: tuple[str, dict] | None, *, force: bool) -> None:
        if self.ck_path is None:
            return
        now = time.monotonic()
        if not force and now - self.last_write < self.spec.checkpoint_every_s:
            return
        payload = dict(self.header)
        payload.update({"finished": self.finished,
                        "current": None if current is None
                        else {"unit": current[0], "state": current[1]}})
        write_checkpoint(self.ck_path, payload)
        self.last_write = now

    def emit(self, kind: str, **data) -> None:
        if self.stream is not None:
            self.stream.emit(kind, **data)


def _record(uid, kind, search, idx, rng_seed, run: tp.SeedRun, sweeps, polished, round_):
    return UnitRecord(
        unit=uid, kind=kind, space_group=search.group, assignment=search.assignment,
        seed_index=idx, rng_seed=rng_seed, round=round_, sweeps=run.sweeps,
        sweeps_planned=sweeps, moves=run.moves, t_top=float(run.ladder.record["t_top"]),
        temperatures=[float(t) for t in run.ladder.temperatures],
        move_acceptance=[float(x) for x in run.move_accept],
        swap_attempts=[int(x) for x in run.swap_attempts],
        swap_accepts=[int(x) for x in run.swap_accepts], drift=float(run.drift),
        stopped=run.stopped, compiled=bool(sum(run.compiled.values())),
        best_j=[float(v.j) for v in run.best],
        polished=[PolishedState(xyz=search.space.xyz(v.u[None])[0].tolist(), j=v.j, chi2=v.chi2,
                                clash=v.clash) for v in polished])


def _tag(assignment: int | None) -> str:
    return "" if assignment is None else f"a{assignment}:"


def _run_unit(run: _Run, search: _Search, kind: str, idx: int, sweeps: int, *,
              round_: int | None = None, start_state: dict | None = None):
    """One unit, or its record from the checkpoint.  Returns (record, the last
    boundary state as JSON or None, finished)."""
    if kind == "race":
        uid = f"race:{search.group}:a{search.assignment}:r{round_}"
        rng_seed = unit_seed(run.spec, "race", search.assignment or 0)
    else:
        uid = f"{kind}:{search.group}:{_tag(search.assignment)}s{idx}"
        rng_seed = unit_seed(run.spec, kind, idx)
    if uid in run.finished:
        got = run.finished[uid]
        return UnitRecord.model_validate(got["record"]), got.get("end_state"), True
    problem, ladder = ((search.control, search.control_ladder) if kind == "control"
                       else (search.problem, search.ladder))
    resume = None
    if run.current is not None and run.current[0] == uid:
        resume = run.current[1]
    elif start_state is not None:
        resume = start_state
    last = {"state": resume}
    run.progress.start(uid, unit_kind=kind, space_group=search.group,
                       assignment=search.assignment, seed=idx, sweeps_planned=sweeps,
                       resumed_at=None if resume is None else resume["done"])
    floor = run.floor

    def boundary(st: tp.TemperState) -> None:
        last["state"] = st.to_json()
        run.save((uid, last["state"]), force=False)

    def beat(info: dict) -> None:
        run.emit("solve_step", unit=uid, unit_kind=kind, sweep=info["sweep"], sweeps=info["sweeps"],
                 moves=info["moves"], leader_j=info["leader_j"],
                 leader_chi2_ratio=info["leader_chi2"] / floor,
                 leader_changed=info["leader_changed"],
                 sweeps_since_improvement=info["sweeps_since_improvement"],
                 replica_temperatures=[float(t) for t in ladder.temperatures],
                 replica_acceptance=info["replica_acceptance"],
                 swap_acceptance=info["swap_acceptance"])

    t0 = time.perf_counter()
    seed_run = tp.temper(problem, ladder, seed=rng_seed, sweeps=sweeps,
                         swap_every=run.spec.swap_every, exchange=run.spec.exchange,
                         cancel=run.token,
                         heartbeat=None if run.spec.heartbeat_sweeps is None else beat,
                         heartbeat_sweeps=run.spec.heartbeat_sweeps, on_boundary=boundary,
                         resume=None if resume is None else tp.TemperState.from_json(resume))
    polished = ([] if kind == "race" else
                [tp.polish(problem, v, maxiter=run.spec.polish_maxiter) for v in seed_run.best])
    run.timings[uid] = round(time.perf_counter() - t0, 3)
    record = _record(uid, kind, search, idx, rng_seed, seed_run, sweeps, polished, round_)
    done = seed_run.stopped is None
    if done:
        run.finished[uid] = {"record": record.model_dump(mode="json"),
                             "end_state": last["state"] if kind == "race" else None}
        run.current = None
        run.save(None, force=True)
    else:
        run.stopped = True
    top = sorted(record.polished, key=lambda p: p.j)[:3]
    run.progress.end(uid, unit_kind=kind, space_group=search.group, assignment=search.assignment,
                     seed=idx, moves_done=record.moves, moves_planned=sweeps * run.spec.replicas,
                     search_complete=done, best_j=min(record.best_j),
                     provisional=[{"j": p.j, "chi2_ratio": p.chi2 / floor, "provisional": True}
                                  for p in top])
    return record, last["state"], done


# ----------------------------------------------------------------------
# the race
# ----------------------------------------------------------------------
def _race_plan(n: int) -> list[int]:
    """How many assignments run in each round of a race over ``n``."""
    plan = []
    while n > 1:
        plan.append(n)
        n = math.ceil(n / 2)
    return plan


def race_assignments(run: _Run, searches: list[_Search]) -> tuple[RaceRecord, list[UnitRecord],
                                                                    int | None]:
    """Successive halving over one group's assignments (module docstring):
    (the race's record, its units' records, the winner's index into
    ``searches`` or ``None`` when the run stopped first)."""
    spec = run.spec
    rec = RaceRecord(space_group=searches[0].group, n_assignments=len(searches))
    records: list[UnitRecord] = []
    alive = list(range(len(searches)))
    states: dict[int, dict | None] = {}
    k = 0
    while len(alive) > 1:
        sweeps = spec.race_sweeps * 2 ** k
        best = []
        for i in alive:
            if run.stopped or (run.token is not None and run.token.is_set()):
                run.stopped = True
                run.not_run.append(f"race:{searches[i].group}:a{searches[i].assignment}:r{k}")
                continue
            r, state, done = _run_unit(run, searches[i], "race", 0, sweeps, round_=k,
                                       start_state=states.get(i))
            records.append(r)
            states[i] = state
            if done:
                best.append(min(r.best_j))
        if run.stopped:
            return rec, records, None
        keep = sorted(range(len(alive)), key=lambda m: (best[m], alive[m]))[
            :math.ceil(len(alive) / 2)]
        kept = sorted(alive[m] for m in keep)
        rec.rounds.append(RaceRound(round=k, sweeps=sweeps,
                                    ran=[searches[i].assignment for i in alive],
                                    best_j=best, kept=[searches[i].assignment for i in kept]))
        alive = kept
        k += 1
    rec.winner = searches[alive[0]].assignment
    return rec, records, alive[0]


# ----------------------------------------------------------------------
# the consensus, from records alone
# ----------------------------------------------------------------------
def _candidate_structure(phase, group: str, layout: SearchLayout, xyz):
    from ..schemas.common import Parameter
    from ..schemas.structure import Atom, Structure

    ph = _group_phase(phase, group)
    atoms = [Atom(label=a.label, species=a.species, x=Parameter(value=float(x[0] % 1.0)),
                  y=Parameter(value=float(x[1] % 1.0)), z=Parameter(value=float(x[2] % 1.0)),
                  occ=Parameter(value=a.occ), biso=Parameter(value=a.biso))
             for a, x in zip(layout.atoms, xyz, strict=True)]
    return Structure(phases=[ph.model_copy(update={"atoms": atoms, "rigid_bodies": []},
                                           deep=True)])


def _equivalence(phase, group: str):
    ph = _group_phase(phase, group)
    from ..model.restraints import _metric_g

    cell = tuple(float(getattr(ph.cell, k).value) for k in ("a", "b", "c", "alpha", "beta",
                                                            "gamma"))
    return cl.equivalences(resolve_group(ph.space_group, ph.symmetry_operations),
                           np.asarray(_metric_g(cell), dtype=np.float64))


def _consensus(phase, group: str, layout: SearchLayout, records: list[UnitRecord],
               floor: float, tol: float) -> list[cl.RankedSolution]:
    def sols(kind):
        return [cl.Solution(np.array(p.xyz), p.j, p.chi2, p.clash, r.seed_index)
                for r in records if r.kind == kind and r.space_group == group
                and r.assignment == layout.assignment for p in r.polished]

    on, off = sols("seed"), sols("control")
    if not on:
        return []
    eq = _equivalence(phase, group)
    species = [a.species for a in layout.atoms]
    labels = [a.label for a in layout.atoms]
    clusters = cl.cluster(on, eq, species, tol=tol)
    control = cl.cluster(off, eq, species, tol=tol) if off else None
    return cl.rank(clusters, floor=floor, labels=labels, species=species, control=control,
                   eq=eq)


def _candidates(phase, group, layout, ranked, partial: bool) -> list[StructureCandidate]:
    return [StructureCandidate(
        rank=r.rank, space_group=group, assignment=layout.assignment, labels=list(r.labels),
        species=list(r.species), xyz=r.xyz.tolist(),
        structure=_candidate_structure(phase, group, layout, r.xyz),
        chi2_data=r.chi2_data, chi2_ratio=r.chi2_ratio, clash_raw=r.clash_raw, j=r.j,
        seeds=list(r.seeds), n_finders=len(r.seeds), finder_rmsd=r.spread_ang,
        n_members=r.n_members, margin_to_next=r.margin_to_next,
        control_rmsd_ang=r.control_rmsd_ang, control_chi2_data=r.control_chi2_data,
        partial=partial) for r in ranked]


def _sort_records(records: list[UnitRecord], groups: list[str]) -> list[UnitRecord]:
    return sorted(records, key=lambda r: (groups.index(r.space_group), _KIND_ORDER[r.kind],
                                          -1 if r.assignment is None else r.assignment,
                                          -1 if r.round is None else r.round, r.seed_index))


def _assemble(*, phase, spec: SolveSpec, n_reflections: int, floor: float,
              groups: list[str], races: list[RaceRecord], layouts: list[SearchLayout],
              records: list[UnitRecord], status: str, units_not_run: list[str],
              timings: dict, resumed: bool, provenance: SolveProvenance,
              progress=None) -> SolutionResult:
    records = _sort_records(records, groups)
    partial = status != "done"
    winners = {r.space_group: r.winner for r in races}
    candidates: list[StructureCandidate] = []
    for g in groups:
        lay = [x for x in layouts if x.space_group == g
               and (g not in winners or x.assignment == winners[g])]
        if not lay:
            continue
        ranked = _consensus(phase, g, lay[0], records, floor, spec.cluster_tol)
        got = _candidates(phase, g, lay[0], ranked, partial)
        if progress is not None:
            label = f"consensus:{g}"
            progress.start(label, space_group=g, consensus=True)
            progress.end(label, space_group=g, consensus=True, n_candidates=len(got),
                         candidates=[candidate_evidence(i, c).model_dump(mode="json")
                                     for i, c in enumerate(got)])
        candidates.extend(got)
    candidates.sort(key=lambda c: (c.chi2_data, groups.index(c.space_group), c.rank))
    candidates = [c.model_copy(update={"rank": i + 1}) for i, c in enumerate(candidates)]
    return SolutionResult(
        candidates=candidates, engines_run=[spec.engine], space_groups_searched=list(groups),
        races=races, layouts=layouts, records=records,
        search_complete={r.unit: r.stopped is None for r in records},
        seeds_run=sorted({r.seed_index for r in records if r.kind == "seed"}),
        control_seeds_run=sorted({r.seed_index for r in records if r.kind == "control"}),
        units_not_run=units_not_run, status=status, partial=partial, resumed=resumed,
        spec=spec.to_spec_spec(), phase=phase, n_reflections=n_reflections,
        chi2_floor=floor, timings=timings,
        provenance=provenance)


# ----------------------------------------------------------------------
# the entry point
# ----------------------------------------------------------------------
def solve_structure(cost, phase, *, instrument, priors, spec: SolveSpec | SolveSpecSpec,
                    composition: Mapping[str, int] | None = None,
                    units: Sequence | None = None, space_groups: Sequence[str] | None = None,
                    biso: float | None = None, events=None, cancel=None, telemetry=None,
                    label: str | None = None,
                    checkpoint: str | Path | None = None) -> SolutionResult:
    """Solve a structure on a verified cell (module docstring).

    ``cost`` is the :class:`~rietx.solve.cost.SolveCost` of ``phase``'s
    Pawley or Le Bail fit; ``instrument`` decides the radiation.  Declare
    either ``composition`` (atoms per cell by species, placed on every
    site-class assignment and raced) or ``units`` (free sites and rigid
    fragments, used as given).  ``priors`` is a
    :class:`~rietx.solve.chemistry.SolvePriors`, with no default: its σ,
    radius fraction and weights are the caller's (#1016).  ``spec`` is a
    :class:`~rietx.solve.engines.SolveSpec` (or its request chair), with no
    default: every search setting is the caller's.  ``space_groups``
    defaults to ``phase``'s own.  ``biso`` is every placed free site's B
    (Å²), required with ``composition=`` (declared units carry their own).
    ``events``, ``cancel``, ``telemetry`` and ``label`` are ``fit``'s.
    ``checkpoint`` is a path: written as the run goes, resumed when it
    exists."""
    from .. import runs
    from ..history.events import as_event_stream
    from ..indexing.engines import Deadline, Progress
    from ..refine import _VERSION, _utcnow

    if (composition is None) == (units is None):
        raise SolveRefused("declare exactly one of composition= and units=")
    if biso is None and composition is not None:
        raise SolveRefused("composition= places free sites: declare their biso= (Å²)")
    if isinstance(spec, SolveSpecSpec):
        spec = spec.to_spec()
    if not isinstance(spec, SolveSpec):
        raise SolveRefused(f"spec must be a SolveSpec or a SolveSpecSpec, not "
                           f"{type(spec).__name__}")
    if spec.engine != "tempering":
        raise SolveRefused(f"engine {spec.engine!r} is not built yet; registered: tempering")
    if spec.race_sweeps % tp.REFRESH_EVERY:
        raise SolveRefused(f"race_sweeps ({spec.race_sweeps}) must be a multiple of "
                           f"{tp.REFRESH_EVERY}, the boundary a race round continues from")
    groups = list(space_groups) if space_groups else [phase.space_group]
    if units is not None and any(g != phase.space_group for g in groups):
        raise SolveRefused("declared units sit on one group's site classes: search other "
                           "groups through composition=")
    searches = _searches(cost, phase, instrument, priors, groups, composition, units, spec,
                         biso)
    floor = float(cost.chi2_floor)
    cost_fp = cost_fingerprint(cost, Radiation.from_instrument(
        instrument, sorted({sp for x in searches for sp in x.space.species})))
    spec_fp = spec_fingerprint(spec, phase, searches, priors)
    header = {"format": CHECKPOINT_FORMAT, "package_version": _VERSION, "cost": cost_fp,
              "spec": spec_fp}
    ck_path = None if checkpoint is None else Path(checkpoint)
    resumed_from = None
    if ck_path is not None and ck_path.exists():
        resumed_from = read_checkpoint(ck_path, cost_fp=cost_fp, spec_fp=spec_fp,
                                       version=_VERSION)

    stream = as_event_stream(events)
    recorder = runs.attach(stream, events, telemetry=telemetry, label=label)
    if recorder is not None and stream is None:
        stream = recorder
    token = runs.attach_cancel(runs.recorder_of(stream), cancel)
    deadline = None
    if spec.total_budget_seconds is not None:
        deadline = Deadline(spec.total_budget_seconds, cancel=token)
        token = deadline
    by_group = {g: [s for s in searches if s.group == g] for g in groups}
    total = sum((sum(_race_plan(len(by_group[g]))) if composition is not None else 0)
                + len(spec.seeds) + len(spec.control_seeds) + 1 for g in groups)
    progress = Progress(stream, total=total, deadline=deadline)
    run = _Run(spec, stream, progress, token, deadline, floor, ck_path, header, resumed_from)
    try:
        run.emit("solve_start", engine=spec.engine, space_groups=groups,
                 n_assignments={g: len(by_group[g]) for g in groups},
                 seeds=list(spec.seeds), control_seeds=list(spec.control_seeds),
                 replicas=spec.replicas, sweeps=spec.sweeps, race_sweeps=spec.race_sweeps,
                 span=spec.span, step=list(spec.step), swap_every=spec.swap_every,
                 exchange=spec.exchange, n_random=spec.n_random, cluster_tol=spec.cluster_tol,
                 polish_maxiter=spec.polish_maxiter, heartbeat_sweeps=spec.heartbeat_sweeps,
                 total_budget_seconds=spec.total_budget_seconds,
                 n_reflections=int(len(cost.d)), chi2_floor=floor,
                 resumed=resumed_from is not None, n_stages=total)
        races: list[RaceRecord] = []
        records: list[UnitRecord] = []
        for g in groups:
            ss = by_group[g]
            chosen: _Search | None = ss[0]
            if len(ss) > 1:
                rec, recs, win = race_assignments(run, ss)
                races.append(rec)
                records.extend(recs)
                chosen = None if win is None else ss[win]
            elif composition is not None:
                races.append(RaceRecord(space_group=g, n_assignments=1, winner=ss[0].assignment))
            for kind, idxs in (("seed", spec.seeds), ("control", spec.control_seeds)):
                for k in idxs:
                    name = f"{kind}:{g}:{_tag(None if chosen is None else chosen.assignment)}s{k}"
                    if chosen is None or run.stopped or (token is not None and token.is_set()):
                        run.stopped = True
                        run.not_run.append(name)
                        continue
                    r, _state, _done = _run_unit(run, chosen, kind, k, spec.sweeps)
                    records.append(r)
        if not run.stopped:
            status = "done"
        elif deadline is not None and deadline.expired() and not deadline.cancelled_by_user():
            status = "budget"
        else:
            status = "cancelled"
        out = _assemble(
            phase=phase, spec=spec, n_reflections=int(len(cost.d)),
            floor=floor, groups=groups, races=races, layouts=[s.layout() for s in searches],
            records=records, status=status, units_not_run=run.not_run, timings=run.timings,
            resumed=resumed_from is not None,
            provenance=SolveProvenance(package_version=_VERSION,
                                       created_utc=_utcnow(),
                                       compiled=any(r.compiled for r in records) or None),
            progress=progress)
        run.emit("solve_end", status=status, partial=out.partial,
                 n_candidates=len(out.candidates), units_not_run=len(out.units_not_run))
        return out
    except BaseException:
        if recorder is not None:
            recorder.close("failed")
        raise
    finally:
        if stream is not None and stream is not events:
            stream.close()
        if recorder is not None:
            recorder.close()


# ----------------------------------------------------------------------
# seeds as processes
# ----------------------------------------------------------------------
def merge_seed_results(results: Sequence[SolutionResult | str | Path]) -> SolutionResult:
    """One answer from per-seed results (module docstring).  Every result must
    share the phase, the cost (its floor and reflection count), the spec but
    its seed lists, the layouts and the races; their records are pooled and
    the consensus taken again, as the in-process run takes it."""
    got = []
    for r in results:
        if not isinstance(r, SolutionResult):
            r = SolutionResult.model_validate_json(Path(r).read_text(encoding="utf-8"))
        got.append(r)
    if not got:
        raise ValueError("no results to merge")
    first = got[0]

    def shared(r: SolutionResult) -> str:
        spec = r.spec.model_dump(exclude={"seeds", "control_seeds", *_RESUMABLE_FIELDS})
        return json.dumps([spec, r.phase.model_dump(mode="json"), r.chi2_floor,
                           r.n_reflections, [x.model_dump(mode="json") for x in r.layouts],
                           [x.model_dump(mode="json") for x in r.races],
                           r.space_groups_searched], sort_keys=True)

    want = shared(first)
    for r in got[1:]:
        if shared(r) != want:
            raise ValueError("these results are not seeds of one run: their phase, cost, "
                             "spec, layouts or races differ")
    records: dict[str, UnitRecord] = {}
    for r in got:
        for rec in r.records:
            if rec.unit in records and records[rec.unit] != rec:
                raise ValueError(f"two results disagree about unit {rec.unit}")
            records[rec.unit] = rec
    status = ("done" if all(r.status == "done" for r in got)
              else "budget" if any(r.status == "budget" for r in got) else "cancelled")
    spec = replace(first.spec.to_spec(),
                   seeds=tuple(sorted({k for r in got for k in r.spec.seeds})),
                   control_seeds=tuple(sorted({k for r in got for k in r.spec.control_seeds})))
    timings: dict[str, float] = {}
    for r in got:
        timings.update(r.timings)
    return _assemble(
        phase=first.phase, spec=spec, n_reflections=first.n_reflections,
        floor=first.chi2_floor, groups=list(first.space_groups_searched), races=first.races,
        layouts=first.layouts, records=list(records.values()), status=status,
        units_not_run=sorted({u for r in got for u in r.units_not_run}), timings=timings,
        resumed=any(r.resumed for r in got),
        provenance=SolveProvenance(package_version=first.provenance.package_version,
                                   created_utc=first.provenance.created_utc,
                                   compiled=first.provenance.compiled))


def _tempering_engine(*args, **kwargs):
    """The ``tempering`` engine: one unit of parallel tempering
    (:func:`~rietx.solve.tempering.temper`), polished rung by rung."""
    return tp.temper(*args, **kwargs)


register_engine("tempering", _tempering_engine,
                "Parallel tempering in direct space over free sites on the Wyckoff classes "
                "and rigid fragments (S2a): suits a known composition or known fragments.")

__all__ = ["CHECKPOINT_FORMAT", "CheckpointMismatch", "SolveRefused", "cost_fingerprint",
           "merge_seed_results", "race_assignments", "read_checkpoint", "solve_structure",
           "spec_fingerprint", "write_checkpoint"]
