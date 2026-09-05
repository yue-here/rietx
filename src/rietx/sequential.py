"""Sequential refinement of an ordered series of patterns (WP-0505).

An in-situ ramp, a parametric sweep, a tray of related specimens: N patterns
refined one at a time, each warm-started from its predecessor's converged
state.  **Not** one joint residual — that is :mod:`rietx.multi`, which stacks
histograms that *share* structural parameters.  Here nothing is shared; the
only thing that crosses a pattern boundary is the starting point.

Two consequences shape this module.

*The output is a trajectory.*  a(T), Biso(t), the weight fractions against the
series coordinate — with esds, and with the per-pattern fit status that
produced each point.  :class:`~rietx.schemas.sequential.SeriesResult` is that
object; a ``list[RefinementResult]`` is not, because it leaves the user to
re-derive the axis, the esds and the status by hand.

*A sequential fit is path-dependent by construction.*  Every pattern's answer
depends on its neighbour's, so the method can imprint a trend the data do not
carry: one bad pattern's error is inherited by all its successors, and the
result is a smooth-looking curve.  That is the same failure mode the FitReport
gates exist to prevent, and it gets the same treatment here — three fences,
none of which alters a fitted value:

``SEQUENTIAL_RESEED``
    the warm start was rejected (diverged, or Rwp far above the series median)
    and the pattern was refitted cold, so the chain cannot be poisoned silently.
``SEQUENTIAL_UNRECOVERED``
    the pattern diverged and stayed diverged after every rung of the ladder
    below; it is reported, but it seeded no successor and joined no median.
``SEQUENTIAL_DISCONTINUITY``
    a step much larger than the local trend — the science (a phase transition)
    or a chain failure, and the diagnostic says both.  ``fit(...,
    verify_discontinuities=True)`` re-measures each one by refitting its two
    patterns cold and independently, and records what that pair reproduces as
    the diagnostic's ``value`` (WP-1305).
``SEQUENTIAL_PATH_DEPENDENT``
    with ``direction="both"``, the forward and backward chains disagree by more
    than their esds allow: that parameter's trajectory is an artefact of the
    ordering, not a measurement.

**The fallback is a ladder, and a pattern it cannot rescue is quarantined**
(WP-1051).  A rejected warm fit escalates one rung at a time — collapsed warm
refit → the full staged plan *from the warm state* → the full staged plan cold
(:func:`_ladder`) — each rung run only when the fence still fires on the best
attempt so far, and the best attempt kept whichever rung produced it.  The
middle rung is what the chain used to skip: throwing the warm start away costs
roughly triple (838-904 iterations warm-collapsed, 1623 warm-staged, 2863 cold
on the round-robin series), and it was being paid for a starting point that had
not been shown to be the problem.

Quarantine is the other half, and it is about what the chain *carries* rather
than about what it reports: a fit that came back ``"diverged"`` after the last
rung is not a starting point and not a scale, so the successor warm-starts from
the last **accepted** pattern and the reseed median never sees the failure.
Before WP-1051 a doubly-failed pattern did both — it seeded its neighbour with
garbage and dragged the median that decides every later trigger, so one failure
could quietly raise the bar for the rest of the series.

**What triggers the ladder is deliberately narrow: divergence, or Rwp above
``reseed_factor`` × the median of the accepted patterns** (:func:`_reseed_needed`).
Two candidates were considered and rejected, and the reasons are the rule a new
trigger has to satisfy.  *Guard findings* (``HIGH_CORRELATION``, at-bounds) fire
legitimately on perfectly converged patterns: a correlated pair is a property of
the model and the data, and no rung of this ladder changes either — it would
re-fit every pattern of the series, at triple cost, to reach the same minimum.
*A discontinuity* is a post-hoc property of the whole trajectory (the median
absolute step is not defined until the series has been walked, and needs
:data:`MIN_POINTS_FOR_DISCONTINUITY` of it), so making it a trigger would mean
re-walking a finished chain — a different algorithm, with no guaranteed
fixpoint.  What the two accepted triggers share: each is a property of *this
pattern's own fit*, readable the moment it finishes, and each is something a
different starting point could plausibly fix.

**Telemetry and cancellation are per pattern, stamped with the pattern**
(WP-1016).  ``fit(events=, cancel=)`` reach every pattern's own
:meth:`Refinement.fit`, and each pattern's events are forwarded through
:class:`_SeriesStream`, which adds ``series_index``/``series_label``/
``series_n``/``series_pass`` (and, on a restart, ``series_rung`` plus the
``series_cold`` it has always carried) to the event's ``data``.  Those are
*added fields on existing kinds*, so
:data:`~rietx.history.events.EVENT_SCHEMA_VERSION` does not move — the rule is
in that module, and a series needs nothing more, because "pattern k of N" is
readable off ``fit_start`` and a consumer reads ``data`` with ``.get``.

Cancelling a series **returns** what completed rather than raising, and that is
not the exception to WP-1006's rule but the rule applied one level up: a series
is N *separate* refinements, so the pattern in flight is abandoned by
``Refinement.fit`` itself (no node, no commit, models restored) while patterns
already walked are finished fits with committed nodes.  Raising would throw
those away.  ``SEQUENTIAL_CANCELLED`` says how many of how many were reached, so
a short ``entries`` list is never mistaken for a short series.

Constraining a parameter to a functional form of T across the whole series —
parametric refinement, Stinton & Evans (2007) J. Appl. Cryst. 40, 87 — is a
*joint* fit over the series and is deliberately out of scope; these fences
exist partly so a sequential trajectory is never mistaken for one.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any

import numpy as np

from .backend.api import backend_dtype_note
from .history.events import EventStream, _attach_progress, as_event_stream
from .history.tree import RefinementTree
from .optimize.cancel import RefinementCancelled
from .optimize.least_squares import NFEV_PER_ITERATION, SOLVERS
from .params.vector import ParameterTable
from .refine import (
    _VERSION,
    Refinement,
    _declared_wavelengths,
    _extract_reflections,
    _refuse_without_phases,
    _utcnow,
)
from .report.schemas import THRESHOLDS_VERSION
from .schemas.common import Diagnostic, Mode, Provenance
from .schemas.history import ReflectionState
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.results import RefinementResult
from .schemas.sequential import SeriesEntry, SeriesResult
from .schemas.structure import Structure
from .strategy.staged import RefinementPlan, Stage, resolve_plan

#: Rwp above this multiple of the accepted-so-far **median** triggers a cold
#: refit.  A median rather than the previous value on purpose: one bad pattern
#: must not be able to ratchet the threshold up and let its successors through.
RESEED_FACTOR = 1.25

#: Converged first rungs needed before the chain bounds anything (WP-1127).
#: One sample is not a spread, and the running maximum of a *short* sample is
#: set by whichever pattern happened to be cheapest.  The same reasoning as
#: :data:`MIN_POINTS_FOR_DISCONTINUITY` one fence over, and it was measured the
#: expensive way: at one sample the bound went 2 × 8 = 16 evaluations on the
#: thermal-ramp chain and its third pattern legitimately wanted **17**, a
#: one-evaluation margin that darwin cleared and Linux did not.
FIRST_RUNG_SAMPLES = 3

#: Headroom over the most expensive first rung the chain has already
#: **converged** — :meth:`SequentialRefinement.fit`'s ``first_rung_factor``
#: default (WP-1127).
#:
#: The first rung is a *bet* that the collapsed warm refit suffices, and it is
#: otherwise sized like an answer: :func:`_collapse` takes ``max_iter`` as the
#: maximum over the plan's stages, so a bet that loses spends the plan's largest
#: budget on the widest Jacobian in it and is then thrown away.  A winning bet
#: and a losing one do not overlap: a first rung that is kept costs 27-64
#: evaluations on ``trigger-series`` and 25-107 on ``cpd-series``, while both
#: losing ones ran to ~400, the cap itself.  **The bound only has to land in
#: that gap**, so it is set for margin rather than for tightness.
#:
#: Calibrated on the quantity that decides it: how far a *legitimate* first rung
#: can exceed the running maximum of the converged ones before it.  Measured
#: across three chains — the two harness series and the thermal ramp — that
#: ratio reaches **1.29** once :data:`FIRST_RUNG_SAMPLES` samples are in hand,
#: so 3.0 carries 2.3× margin over the worst case seen anywhere.  It reached
#: 1.89 at a single sample, which is what the minimum is for.
#:
#: Being wrong is cheap and **cannot reach the answer**: a bound that bites
#: costs one escalation, the rung it escalates to is the full staged plan from
#: the same warm state, and :func:`_prefer` refuses to keep the truncated
#: attempt over the completed one.  Measured on both harness cases, every
#: accepted value is bit-identical to the unbounded chain's, because the bound
#: only truncates a rung whose result is discarded and its replacement starts
#: from the warm state rather than from the truncation.
#:
#: What licenses a modest factor is that being wrong is cheap **and cannot reach
#: the answer**: a bound that bites costs one escalation, and the rung it
#: escalates to is the full staged plan from the same warm state, with
#: :func:`_prefer` refusing to keep the truncated attempt over the completed one.
#: Measured on both harness cases, every accepted value is bit-identical to the
#: unbounded chain's — 0 of 1030 and 0 of 392 — because the bound only truncates
#: a rung whose result is discarded, and its replacement starts from the warm
#: state rather than from the truncation.
FIRST_RUNG_FACTOR = 3.0

#: A step is called a discontinuity when it exceeds this multiple of the median
#: absolute step of the same parameter over the series *and* is significant
#: against the two points' combined esds.  Both tests are needed: in a real
#: in-situ ramp with small esds every step is many σ (so σ alone flags
#: everything), while in a flat series the median step is ~0 (so the ratio
#: alone flags noise).
DISCONTINUITY_FACTOR = 5.0
DISCONTINUITY_SIGMA = 3.0

#: Both fences below are *ratio* tests, and a ratio is meaningless once its
#: denominator is floating-point noise.  A parameter the data do not constrain
#: at all — a softplus coefficient sitting on its floor — is where this bites:
#: dp/du → 0 there, so its esd collapses **alongside** its value and the
#: significance leg inverts instead of protecting.  Measured on the synthetic
#: ramp: an unrefinable ``instrument.profile.y`` came back with a median step of
#: 4e-16, one step of 1.3e-11 (29 000× the median) and σ ≈ 4e-55, and the
#: forward/backward chains "disagreed" at 1e16 σ over 1e-60 and 1e-74.  So a
#: step or a between-chain difference is also required to be this large a
#: fraction of the parameter's own magnitude (and never below 1e-9 absolute):
#: below that the trajectory is a constant, whatever the ratios say.
NOISE_FLOOR_REL = 1e-9

#: Forward and backward chains are called to disagree at this many combined σ.
PATH_DEPENDENCE_SIGMA = 3.0

#: A trajectory needs at least this many points before the robust step scale
#: (the median absolute step) means anything.
MIN_POINTS_FOR_DISCONTINUITY = 5

#: A series needs at least this many patterns before "in most of them" is a
#: statement about the series rather than about two or three fits.  The same
#: number as :data:`MIN_POINTS_FOR_DISCONTINUITY` and for the same reason: below
#: it the per-entry diagnostics are the whole story and a summary of three
#: things is not a summary.
MIN_POINTS_FOR_PERSISTENCE = 5

#: ``Diagnostic.level`` as an ordering, so a summary of many occurrences can
#: carry the worst one rather than a fixed level of its own.
_LEVEL_RANK = {"info": 0, "warning": 1, "error": 2}

#: What ``refit=`` and ``direction=`` accept, as data rather than as two literals
#: inside :meth:`SequentialRefinement.fit`.  A caller that has to *offer* the
#: choices (the GUI's series panel, WP-1016) needs the same list this validates
#: against, and a menu that could disagree with the validator would be a second
#: authority — the ``capabilities()`` rule at a smaller scale.
REFIT_MODES = ("single", "stages")
DIRECTIONS = ("forward", "backward", "both")

#: The escalation ladder in order, as names (WP-1051).  ``"warm"`` is the
#: collapsed warm refit, ``"warm_staged"`` the full staged plan from the warm
#: state, ``"cold"`` the full staged plan from the initial models — which is
#: also what the *first* pattern of every chain runs, having no predecessor.
RUNGS = ("warm", "warm_staged", "cold")


class _SeriesStream(EventStream):
    """One pattern's event stream, stamped with its place in the series.

    A subclass rather than a callable because ``Refinement.fit`` normalises its
    ``events=`` argument through
    :func:`~rietx.history.events.as_event_stream`, which passes an
    :class:`EventStream` through untouched — and *that* is what keeps
    ``stream is events`` true inside ``fit``, so the pattern's fit does not close
    the stream the series owns.  It writes no file and holds no callback of its
    own: every event goes to the caller's stream, which is where the path and the
    callback live, so a series run appends to exactly one log.

    The stamp is five added ``data`` keys on existing kinds, never a new kind
    (``history/events.py``'s additivity rule): ``series_index`` is the pattern's
    place in **series** order, not in walk order, so a backward chain's frames
    carry the same index as the forward chain's for the same pattern, and
    ``series_pass`` is what distinguishes them — ``"forward"``, ``"backward"``,
    or ``"verify"`` for a post-walk discontinuity refit (WP-1305), a new *value*
    of an existing key and so not a schema move either.
    """

    def __init__(self, inner: EventStream, **stamp: Any) -> None:
        super().__init__()          # no path, no callback: the inner one has both
        self._inner = inner
        self._stamp = stamp

    def emit(self, kind: str, **data: Any) -> None:
        # the stamp first, so a future event field named ``series_*`` would
        # override it rather than be silently dropped
        self._inner.emit(kind, **{**self._stamp, **data})
        self.n_written += 1


def unique_labels(names: Sequence[str]) -> list[str]:
    """Disambiguate repeated names by their position, in order.

    Split out of :func:`_labels_for` because a caller that *offers* the labels
    before the run needs to show the ones that will actually be used — two files
    with the same basename from two directories is an ordinary series, and a
    panel whose list disagrees with the result's ``entry.label`` would be showing
    a name that names nothing (WP-1016).
    """
    seen: set[str] = set()
    unique = []
    for i, name in enumerate(names):
        if name in seen:
            unique.append(f"{name}_{i}")
        else:
            seen.add(name)
            unique.append(name)
    return unique


def _labels_for(patterns: Sequence[PatternData],
                labels: Sequence[str] | None) -> list[str]:
    """Per-pattern names, unique — they become history file names."""
    if labels is not None:
        out = [str(v) for v in labels]
        if len(out) != len(patterns):
            raise ValueError(f"labels has {len(out)} entries for "
                             f"{len(patterns)} patterns")
    else:
        out = []
        for i, d in enumerate(patterns):
            src = str(d.metadata.get("source_file", "") or "")
            out.append(Path(src).stem if src else f"p{i:03d}")
    return unique_labels(out)


def _collapse(plan: RefinementPlan) -> RefinementPlan:
    """One stage freeing everything the plan would free, in one solve.

    The default ``refit="single"`` strategy: with a converged neighbour as the
    starting point the staged turn-on order has already done its job of keeping
    early stages well conditioned, so re-walking it per pattern is mostly
    overhead.  Measured on the round-robin sample-1 series: 904 iterations
    against 1623 for the staged refit and 2863 unchained, for the same weight
    fractions to three decimals.

    The seeds carry over as the maximum across the plan's stages, so this is
    the compressed plan rather than a different protocol — ``seed_softplus``
    only lifts values *below* the seed, and a carried value that far down the
    softplus floor is indistinguishable from a cold zero.
    """
    turn_on: list[str] = []
    for stage in plan.stages:
        for glob in stage.turn_on:
            if glob not in turn_on:
                turn_on.append(glob)
    return RefinementPlan(
        stages=[Stage("warm_refit", turn_on,
                      max_iter=max((s.max_iter for s in plan.stages), default=100),
                      lebail_cycles=max((s.lebail_cycles for s in plan.stages),
                                        default=3),
                      seed=max((s.seed for s in plan.stages), default=0.0),
                      strain_seed=max((s.strain_seed for s in plan.stages),
                                      default=0.0))],
        correlation_guard=plan.correlation_guard,
        # inert while the collapse is one stage — a lone stage is the last one
        # and takes the solver's own tolerance — and carried anyway, because
        # this is the compressed plan rather than a different protocol, and a
        # collapse that ever produced two stages would otherwise drop the
        # schedule silently (WP-1123)
        intermediate_ftol=plan.intermediate_ftol)


def _ladder(base_plan: RefinementPlan, warm_plan: RefinementPlan
            ) -> list[tuple[str, RefinementPlan, bool]]:
    """``(rung, plan, warm)`` for one warm-startable pattern, in ladder order.

    Three rungs under the default ``refit="single"`` — the collapsed warm refit,
    the full staged plan from the warm state, the full staged plan cold — and
    **two** under ``refit="stages"``, where the first rung already *is* the
    staged warm fit: re-running an identical plan from an identical starting
    point is a deterministic repeat, and charging the series an extra fit for it
    would make ``refit="stages"`` cost more than ``"single"`` for nothing.

    The middle rung is what this ladder exists for.  Measured on the round-robin
    sample-1 series and quoted by :func:`_collapse` and
    :meth:`SequentialRefinement.fit`: 838-904 iterations warm-collapsed, 1623
    warm-staged, 2863 cold.  So the pre-WP-1051 fallback — straight from the
    first rung to the last — paid roughly triple to discard a starting point
    that had not been shown to be the problem.  A rung is reached only when the
    fence still fires on the *best attempt so far*, which is what makes the
    escalation stop at the first one that works: :func:`_better` prefers a
    converged fit and then the lower Rwp, so once any attempt clears the
    threshold the best one does too.
    """
    first = "warm_staged" if warm_plan is base_plan else "warm"
    rungs: list[tuple[str, RefinementPlan, bool]] = [(first, warm_plan, True)]
    if first != "warm_staged":
        rungs.append(("warm_staged", base_plan, True))
    rungs.append(("cold", base_plan, False))
    return rungs


def _first_rung_budget(accepted_first: list[int],
                       factor: float | None) -> int | None:
    """Evaluations the collapsed first rung may spend, or ``None`` for no bound.

    ``factor`` (:data:`FIRST_RUNG_FACTOR`) times the most expensive first rung
    **this chain has already converged**, once :data:`FIRST_RUNG_SAMPLES` of
    them are in hand — the only evidence there is about what a working first
    rung on this model costs, and a short sample of it is set by whichever
    pattern happened to be cheapest.

    "Worked" is convergence, not survival, and both halves of that earn their
    keep.  A rung that *escalated* says nothing about what a working one costs,
    and letting it in would raise the bound by exactly the failure the bound
    exists to cut short.  A rung that was *kept* at the plan's own cap reports
    ``"max_iter"``, and letting it in at full budget would raise the bound to
    twice that cap and switch the whole thing off from there on.

    **The cold fit is not evidence here, and WP-1127 measured that rather than
    assuming it.**  "A warm refit that costs more than the cold fit it started
    from is not a warm refit" is a tempting second bound, needing no constant
    and — unlike this one — available to the first warm pattern.  It is false:
    :func:`_collapse` of a *one-stage* plan is that plan, so the two are then
    the same problem from different starting points, and a warm start from a
    neighbouring pattern can legitimately want more evaluations than a cold
    start from the initial model.  Measured on the test suite's own cheap plan:
    cold **9** evaluations, warm **14**, so the cold bound cut a rung that was
    about to succeed.  It survived both real harness cases only because a
    multi-stage cold fit sums to several times a collapsed rung (252 against
    25-107), which is a property of those plans and not of the rule.
    """
    if factor is None or len(accepted_first) < FIRST_RUNG_SAMPLES:
        return None
    return int(factor * max(accepted_first))


def _bounded_plan(plan: RefinementPlan, budget_nfev: int | None) -> RefinementPlan:
    """``plan`` with its stages' evaluation budget capped at ``budget_nfev``.

    ``Stage.max_iter`` is in *iterations* and the solver caps *evaluations* at
    ``max_iter × NFEV_PER_ITERATION``, so the budget divides before it is
    applied.  Never raises a stage's budget: ``min`` with what the stage
    already declared, so a plan whose stages are already tighter than the bound
    is returned unchanged — as the *same object*, which keeps
    :func:`_ladder`'s ``warm_plan is base_plan`` identity readable.
    """
    if budget_nfev is None:
        return plan
    cap = max(1, -(-budget_nfev // NFEV_PER_ITERATION))
    stages = [replace(s, max_iter=min(s.max_iter, cap)) for s in plan.stages]
    if all(new.max_iter == old.max_iter
           for new, old in zip(stages, plan.stages, strict=True)):
        return plan
    return replace(plan, stages=stages)


def _rung_stamp(rung: str, *, escalation: bool) -> dict[str, Any]:
    """The ladder's event-stamp keys — present only on a **restart**.

    ``series_rung`` names the rung that is running; ``series_cold`` keeps
    exactly the meaning WP-1016 gave it (present, and true, on a cold restart)
    because dropping it would be a *removed field*, which is an
    ``EVENT_SCHEMA_VERSION`` bump — see ``history/events.py``'s additivity rule.
    So the wire carries the fact twice while the code decides it once, here.

    Neither key appears on a pattern's first attempt, and that is the load-
    bearing part: the first pattern of a chain runs the cold rung *without being
    a restart*, so stamping it would relabel an ordinary cold start as a rescue
    — changing what ``series_cold`` means, which is the same version bump by
    another route.  "Was there a restart here?" therefore stays one ``.get``.
    """
    if not escalation:
        return {}
    stamp: dict[str, Any] = {"series_rung": rung}
    if rung == "cold":
        stamp["series_cold"] = True
    return stamp


def _carry_into(structure: Structure, instrument: Instrument,
                source: tuple[Structure, Instrument],
                carry: Sequence[str]) -> None:
    """Overwrite ``structure``/``instrument`` values from a fitted pair, in place.

    Only paths matching one of the ``carry`` globs move; everything else keeps
    the value it came in with (the *initial* model, when this is called from the
    chain).

    The knob is a control, not a tuning parameter — and the measurement says
    so.  It was built expecting that chaining a phase scale across mixtures
    whose composition swings from 1 to 94 wt % would start the next fit further
    from its answer than a cold start; on the round-robin sample-1 series that
    is **not** what happens.  Carrying everything costs 838 iterations against
    904 for a carry that excludes the scales and re-seeds them per pattern,
    with identical Rwp (0.1278) and identical weight fractions.  What matters
    is chaining at all (2863 unchained).  So: default to carrying everything,
    and reach for a narrower glob when a parameter must provably not be chained
    — not on the assumption that a big jump needs one.
    """
    previous = {e.path: e.value
                for e in ParameterTable(source[0], source[1]).entries}
    table = ParameterTable(structure, instrument)
    for e in table.entries:
        value = previous.get(e.path)
        if value is not None and any(fnmatch.fnmatchcase(e.path, g) for g in carry):
            e.value = value
    # Hold everything, then read the affine map back: tied entries (crystal-
    # system cell ties, Wyckoff coordinate DOFs, site-symmetry ADP patterns)
    # are re-derived from whatever their sources now hold, so a narrow carry
    # glob can never leave a tie inconsistent with its source.
    table.set_vary(["*"], False)
    resolved = table.decode(np.zeros(0))
    for e in table.entries:
        e.value = resolved[e.path]
    table.apply_to_models(structure, instrument)


def _value_of(result: RefinementResult, path: str) -> float | None:
    """One path's fitted value on a result, or ``None`` where it has none.

    :meth:`~rietx.schemas.sequential.SeriesEntry.value` for the object an entry
    is built *from*: a result records the parameters the fit determined, so an
    absent path means this fit measured nothing for it (held, or never freed).
    """
    for p in result.parameters:
        if p.path == path:
            return p.value
    return None


def _entry_from_result(index: int, label: str, x: float | None,
                       result: RefinementResult) -> SeriesEntry:
    return SeriesEntry(
        index=index, label=label, x=x,
        status=result.status,
        statistics=result.statistics.model_copy(deep=True),
        parameters=[p.model_copy(deep=True) for p in result.parameters],
        qpa=result.qpa.model_copy(deep=True) if result.qpa is not None else None,
        phase_agreement=[a.model_copy(deep=True) for a in result.phase_agreement],
        diagnostics=list(result.diagnostics),
        n_iterations=sum(s.n_iterations for s in result.stages),
        node_id=result.node_id, tree_id=result.tree_id)


class SequentialRefinement:
    """Refine an ordered series of patterns, each warm-started from the last.

    ``carry`` is a list of dot-path globs (fnmatch, the ``set_vary``
    convention) naming which parameters cross the pattern boundary; the default
    ``["*"]`` carries everything, and anything excluded restarts from the
    *initial* models on every pattern.

    ``history`` accepts ``False`` (default — a long series makes a lot of
    trees), ``True`` for in-memory trees, or a **directory** path, in which case
    each pattern's history is written to ``<dir>/<label>.jsonl``.  There is one
    tree per pattern, never one for the series: a tree is pinned to its pattern
    by ``TreeHeader.data_fingerprint``, and that check is what stops a node
    being replayed against the wrong data.  The chain is recorded instead as
    annotation notes on each tree's root node.

    After :meth:`fit`, :attr:`results_` holds the full per-pattern
    :class:`~rietx.schemas.results.RefinementResult` objects (with curves,
    for plotting) and :attr:`trees_` the per-pattern histories; the returned
    :class:`~rietx.schemas.sequential.SeriesResult` carries the summaries and
    is the serializable one.
    """

    def __init__(self, structure: Structure, instrument: Instrument, *,
                 backend: str = "numpy", solver: str = "trf",
                 carry: Sequence[str] = ("*",),
                 history: bool | str | Path = False):
        if backend != "numpy":
            from .backend import resolve_backend

            try:
                resolve_backend(backend)  # fail fast with the install hint
            except ValueError as exc:
                raise NotImplementedError(str(exc)) from exc
        if solver not in SOLVERS:
            raise ValueError(f"unknown solver {solver!r}; "
                             f"available: {', '.join(SOLVERS)}")
        self._backend = backend
        self._solver = solver
        self.structure = structure.model_copy(deep=True)
        self.instrument = instrument.model_copy(deep=True)
        self.carry = list(carry)
        self._history = history
        self.results_: list[RefinementResult] = []
        self.trees_: list[RefinementTree | None] = []
        self.result_: SeriesResult | None = None
        self.backward_: SeriesResult | None = None
        self._structures: list[Structure] = []
        self._instruments: list[Instrument] = []

    # ------------------------------------------------------------------
    def fit(self, patterns: Sequence[PatternData], *,
            x: Sequence[float] | None = None,
            x_label: str = "index",
            labels: Sequence[str] | None = None,
            mode: Mode = "rietveld",
            plan: RefinementPlan | str = "mccusker_default",
            refit: str = "single",
            two_theta_limits: tuple[float, float] | None = None,
            direction: str = "forward",
            reseed: bool = True,
            reseed_factor: float = RESEED_FACTOR,
            first_rung_factor: float | None = FIRST_RUNG_FACTOR,
            verify_discontinuities: bool = False,
            prepare: Callable[[int, PatternData, Structure, Instrument],
                              None] | None = None,
            on_result: Callable[[int, RefinementResult], None] | None = None,
            events=None, cancel=None, progress=None,
            ) -> SeriesResult:
        """Run the series.

        Parameters
        ----------
        patterns:
            The series, in order.  Each keeps its own σ (file esds when
            present, Poisson fallback); patterns are never pooled.
        x, x_label:
            The series coordinate (temperature, time, pressure …) and its name.
            Without one the pattern index is the axis, and ``x_label`` says so.
        plan, refit:
            ``plan`` runs on the first pattern (cold) and on any reseeded one.
            ``refit="single"`` (default) collapses it into one stage freeing
            the same set for every subsequent pattern; ``refit="stages"``
            re-walks the whole staged plan from the warm state.  Measured on
            the eight round-robin sample-1 mixtures (WP-0505 acceptance): 904
            iterations against 1623 staged and 2863 unchained, with the QPA
            error identical to three decimals (RMS |ΔW| 2.26 vs 2.27 wt %).
            The staged order exists to keep early stages well conditioned from
            a *poor* starting model, and a converged neighbour is not one —
            when it turns out not to be a good one either, the reseed fence
            catches it and escalates one rung at a time (:func:`_ladder`),
            re-walking the staged plan from the warm state before giving the
            warm state up.  ``refit`` therefore sets the ladder's *first* rung,
            not the only plan a pattern can be fitted with.
        direction:
            ``"forward"``, ``"backward"`` (chain from the last pattern), or
            ``"both"``, which runs it each way and reports where the two
            trajectories disagree by more than their esds allow.  The reported
            entries are the forward ones.
        reseed:
            Escalate the ladder when a warm-started fit diverges or lands far
            above the series median Rwp, and keep the best attempt.  Switching
            it off leaves each pattern with its first rung — but **not** without
            the quarantine: a diverged fit still seeds nothing and joins no
            median, because that is about what the chain carries rather than
            about how hard it tried.
        first_rung_factor:
            Bound what the *collapsed* first rung may spend before the ladder
            gives up on it, at this multiple of the most expensive first rung
            the chain has already **converged** (:func:`_first_rung_budget`,
            :data:`FIRST_RUNG_FACTOR`, :data:`FIRST_RUNG_SAMPLES`).  A chain
            bounds nothing until several warm rungs have worked, because until
            then it has no usable evidence about what a working one costs on
            this model.  ``None`` is no bound and
            reproduces every fit before WP-1127 bit for bit — the way back a
            golden declares, as ``intermediate_ftol`` is for WP-1123's
            schedule.

            It buys nothing on a chain where the collapse works, by
            construction: the bound is derived from what working rungs cost, so
            it only binds on one that is not working, and the round-robin
            sample-1 chain runs unchanged to the evaluation.  Where it does
            bind it is worth 1.36× the whole chain's evaluations, because a
            ladder's first rung is a *bet* and the shipped budget sizes it like
            an answer.  A bound that bites costs an escalation and never an
            answer: the rung it escalates to is the full staged plan from the
            same warm state, which the truncation never touched, and
            :func:`_prefer` refuses to keep the truncated attempt over it.
            Inert under ``refit="stages"``, where the first rung is the answer
            plan rather than a bet.
        verify_discontinuities:
            Re-measure every ``SEQUENTIAL_DISCONTINUITY`` by refitting its two
            patterns **cold and independently** — no warm start, no neighbour —
            and record what that pair reproduces as the diagnostic's ``value``:
            the cold step over the chain's, **signed**.  Near 1.0 the step is in
            the data; near 0 the chain made it; negative is a pair that moved
            the other way, which is neither.  It is the check the diagnostic's
            own suggestion asks the reader for, run automatically.

            **Off by default because it is not cheap**, and the flag exists so
            the cost is the caller's decision rather than a surprise: a cold fit
            is the full staged plan from the initial models, roughly triple a
            warm one, and a series flagging s steps pays up to 2s of them (once
            per pattern, since two flagged paths at the same step share a
            refit).  Measured on the 68-pattern thermal ramp, four flagged
            steps over four patterns, the check adds ~5 %: WP-1305's handover
            has the ranges.

            It is a **post-walk check and never a ladder trigger** — the module
            docstring says why one cannot be: the refits are separate
            :class:`~rietx.refine.Refinement` runs writing to their own
            ``<label>.verify`` histories, and no fitted value, entry, ``rung``
            or median in the reported chain moves because of one.
        prepare:
            ``(index, data, structure, instrument) -> None``, called on the
            warmed models just before each pattern's fit.  The hook exists for
            what a `carry` glob cannot express: a parameter that must be
            re-estimated *from this pattern* rather than either carried or left
            at its initial value — a phase scale on a series of different
            mixtures being the case that forced it.  Excluding scales from
            `carry` alone would only fall back to the first pattern's guess.
        events, cancel:
            What they mean on :meth:`Refinement.fit`, per pattern: every event a
            pattern's fit emits is forwarded with its place in the series stamped
            on (see :class:`_SeriesStream`), and a set token stops the chain
            *between* patterns as well as inside the one in flight.  A cancelled
            series **returns** the entries that completed and reports
            ``SEQUENTIAL_CANCELLED`` — see the module docstring for why that is
            WP-1006's rule rather than an exception to it.
        progress:
            A text stream or path — one line per stage boundary per pattern
            (``[series 7/13] 250C stage cell converged Rwp 0.0812 12s``), the
            series stamp making it read one line per pattern here rather than
            per fit.  Same mechanism as ``Refinement.fit``'s ``progress``,
            combining freely with ``events``.
        """
        # Refused here rather than pattern by pattern: every member fit would
        # raise identically, and the ladder would read the first raise as a
        # divergence to escalate against.
        _refuse_without_phases(self.structure, "refine_sequential")
        patterns = list(patterns)
        if not patterns:
            raise ValueError("a sequential refinement needs at least one pattern")
        if refit not in REFIT_MODES:
            raise ValueError(f"refit must be one of {REFIT_MODES}")
        if direction not in DIRECTIONS:
            raise ValueError(f"direction must be one of {DIRECTIONS}")
        if x is not None and len(x) != len(patterns):
            raise ValueError(f"x has {len(x)} entries for {len(patterns)} patterns")
        names = _labels_for(patterns, labels)
        xs = [None] * len(patterns) if x is None else [float(v) for v in x]
        if x is not None and x_label == "index":
            x_label = "x"
        base_plan = resolve_plan(plan, mode)
        warm_plan = base_plan if refit == "stages" else _collapse(base_plan)
        ladder = _ladder(base_plan, warm_plan)

        order = list(range(len(patterns)))
        if direction == "backward":
            order.reverse()
        stream = _attach_progress(as_event_stream(events), progress)
        entries, results, trees, models = self._chain(
            order, patterns, names, xs, mode, base_plan, ladder,
            two_theta_limits, reseed, reseed_factor, prepare, on_result,
            stream=stream, cancel=cancel,
            pass_name="backward" if direction == "backward" else "forward",
            first_rung_factor=first_rung_factor)

        diagnostics = [d for e in entries
                       for d in _reseed_diagnostics(e) + _unrecovered_diagnostics(e)]
        cancelled = cancel is not None and bool(cancel)
        if cancelled:
            diagnostics.append(_cancelled_diagnostic(len(entries), len(patterns)))
        series = SeriesResult(
            mode=mode, entries=entries, x_label=x_label,
            direction=direction,  # type: ignore[arg-type]
            provenance=Provenance(package_version=_VERSION, created_utc=_utcnow(),
                                  backend=self._backend, solver=self._solver,
                                  dtype=backend_dtype_note(self._backend),
                                  report_thresholds_version=THRESHOLDS_VERSION))
        steps = _discontinuity_steps(series)
        diagnostics += [s.diagnostic for s in steps]
        # WP-1305 (c): the check the diagnostic asks the reader for, run here.
        # A cancelled chain gets none — it starts new fits, and a chain that
        # stopped early is not the trajectory the steps were measured on.
        if verify_discontinuities and steps and not cancelled:
            self._verify_discontinuities(
                steps, patterns, names, mode, base_plan, two_theta_limits,
                prepare, stream=stream, cancel=cancel)
        # what the per-pattern diagnostics could not say: "42 of 68" (WP-1110)
        diagnostics += _persistent_diagnostics(series)

        # a cancelled forward chain gets no verification pass: the comparison is
        # between two *complete* chains, and half of one says nothing
        if direction == "both" and not cancelled:
            back_entries, *_ = self._chain(
                list(reversed(order)), patterns, names, xs, mode, base_plan,
                ladder, two_theta_limits, reseed, reseed_factor, prepare,
                None, history_suffix=".backward", stream=stream, cancel=cancel,
                pass_name="backward", first_rung_factor=first_rung_factor)
            back = SeriesResult(mode=mode, entries=back_entries, x_label=x_label,
                                direction="backward")
            if cancel is not None and bool(cancel):
                diagnostics.append(
                    _cancelled_diagnostic(len(back_entries), len(patterns),
                                          pass_name="backward"))
            else:
                diagnostics += _path_dependence_diagnostics(series, back)
            self.backward_ = back
            # …and on the result, so `refine_sequential` — the one-shot API the
            # manual recommends — hands back the trajectory its
            # SEQUENTIAL_PATH_DEPENDENT diagnostics are about (WP-1076)
            series.backward = back

        series.diagnostics = diagnostics
        self.results_ = results
        self.trees_ = trees
        self._structures = [s for s, _ in models]
        self._instruments = [i for _, i in models]
        self.result_ = series
        return series

    # ------------------------------------------------------------------
    def _chain(self, order, patterns, names, xs, mode, base_plan, ladder,
               two_theta_limits, reseed, reseed_factor, prepare, on_result,
               history_suffix: str = "", stream: EventStream | None = None,
               cancel=None, pass_name: str = "forward",
               first_rung_factor: float | None = None):
        """Walk ``order``, warm-starting each fit from the previous accepted one.

        Returns entries in **series** order regardless of the walk direction, so
        a backward chain's trajectory is directly comparable with a forward
        one's.

        Each pattern climbs ``ladder`` (:func:`_ladder`) until an attempt clears
        the reseed fence, and keeps the best attempt by :func:`_better` whichever
        rung produced it; ``previous`` is the last **accepted** pattern, which is
        not always the last one walked (see the quarantine below).

        A cancelled pattern ends the walk.  Cancelled on its *first* attempt it
        is dropped entirely rather than recorded as a half-fit —
        :meth:`Refinement.fit` has already abandoned the stage — while a cancel
        on a later rung keeps the best complete attempt, because a rung that
        never finished cannot be evidence against the one that did.
        """
        entries: dict[int, SeriesEntry] = {}
        results: dict[int, RefinementResult] = {}
        trees: dict[int, RefinementTree | None] = {}
        models: dict[int, tuple[Structure, Instrument]] = {}
        previous: tuple[Structure, Instrument] | None = None
        previous_hkl: list = []
        previous_tag: tuple[str | None, str | None] = (None, None)
        accepted_rwp: list[float] = []
        # WP-1127's sample: what every first rung that was *kept without
        # escalating* cost.  Read only by _first_rung_budget, and it stays
        # empty when no factor was asked for.
        accepted_first: list[int] = []

        n = len(patterns)
        for position, k in enumerate(order):
            data = patterns[k]
            warm = previous is not None
            stamp = {"series_index": k, "series_label": names[k],
                     "series_n": n, "series_pass": pass_name}
            attempts = ladder if warm else [("cold", base_plan, False)]
            # the bound applies to the *collapsed* first rung only: under
            # refit="stages" the first rung already is the answer plan, and
            # capping that would truncate the fit rather than the bet
            budget = (_first_rung_budget(accepted_first, first_rung_factor)
                      if warm and attempts[0][0] == "warm" else None)
            best_ref = best = None
            best_rung = ""
            best_truncated = False
            tried: list[str] = []
            rwps: list[float] = []
            rung_nfev: list[int] = []
            iterations = 0
            bound_hit = False
            cancelled = False

            for rung, rung_plan, rung_warm in attempts:
                # the fence is asked about the *best* attempt, not the last one:
                # a rung that came back worse has not made the pattern worse.
                # A bounded first rung that spent its bound escalates whatever
                # the fence says: it came back "max_iter", which _better reads
                # as merely not-diverged and _reseed_needed does not test at
                # all, so without this the ladder could *accept* a fit that was
                # cut short (WP-1127).
                forced = bound_hit and len(tried) == 1
                if tried and not forced and not (reseed and _reseed_needed(
                        best, accepted_rwp, reseed_factor)):
                    break
                if not tried and budget is not None:
                    rung_plan = _bounded_plan(rung_plan, budget)
                try:
                    ref, result = self._fit_one(
                        data, names[k], previous if rung_warm else None,
                        previous_hkl if rung_warm else [], rung_plan, mode,
                        two_theta_limits, position, previous_tag, prepare, k,
                        history_suffix + ("" if not tried else f".{rung}"),
                        stream=stream, cancel=cancel,
                        stamp={**stamp,
                               **_rung_stamp(rung, escalation=bool(tried))})
                except RefinementCancelled:
                    cancelled = True
                    break
                spent = sum(s.n_iterations for s in result.stages)
                truncated = (not tried and budget is not None
                             and result.status == "max_iter")
                bound_hit = bound_hit or truncated
                tried.append(rung)
                rwps.append(result.statistics.rwp)
                rung_nfev.append(spent)
                iterations += spent
                if _prefer(result, truncated, best, best_truncated):
                    best, best_ref, best_rung = result, ref, rung
                    best_truncated = truncated

            if best is None:      # cancelled on the first attempt: no half-fits
                break
            entry = _entry_from_result(k, names[k], xs[k], best)
            # every rung is charged to the pattern, not only the one kept
            entry.n_iterations = iterations
            entry.rung = best_rung
            entry.rungs_tried = list(tried)
            if len(tried) > 1:
                entry.rwp_warm = rwps[0]
                # only the *cold* rung breaks the chain — a staged refit from
                # the warm state still started at the neighbour's answer
                entry.reseeded = best_rung == "cold"

            entries[k] = entry
            results[k] = best
            trees[k] = best_ref.history
            models[k] = (best_ref.fitted_structure, best_ref.fitted_instrument)
            # Quarantine (WP-1051): a fit that stayed diverged is reported —
            # the pattern was measured — but it is neither a starting point nor
            # a scale, so the chain steps over it.  Its successor warm-starts
            # from the last accepted pattern and the median that decides every
            # later trigger never sees it.
            if entry.status != "diverged":
                previous = models[k]
                previous_hkl = _extract_reflections(best_ref._model)
                previous_tag = (entry.tree_id, entry.node_id)
                if entry.statistics is not None:
                    accepted_rwp.append(entry.statistics.rwp)
                # The sample the first-rung bound is derived from, taken where
                # the quarantine is: a pattern the chain steps over is not
                # evidence about what a working rung costs either (WP-1127).
                # "Worked" is convergence, not survival — a first rung kept at
                # the *plan's* own cap reports "max_iter", and letting it in at
                # full budget would raise the bound to twice the cap and switch
                # the whole thing off from then on.
                if (warm and len(tried) == 1 and rung_nfev
                        and best.status == "converged"):
                    accepted_first.append(rung_nfev[0])
            if on_result is not None:
                on_result(k, best)
            if cancelled:
                break

        keys = sorted(entries)
        return ([entries[k] for k in keys], [results[k] for k in keys],
                [trees[k] for k in keys], [models[k] for k in keys])

    def _fit_one(self, data: PatternData, label: str,
                 previous: tuple[Structure, Instrument] | None,
                 previous_hkl: list[ReflectionState],
                 plan: RefinementPlan, mode: Mode, two_theta_limits,
                 position: int, previous_tag: tuple[str | None, str | None],
                 prepare, index: int, history_suffix: str = "", *,
                 stream: EventStream | None = None,
                 stamp: dict | None = None, cancel=None):
        """One pattern: warm the models from ``previous``, then run ``plan``."""
        structure = self.structure.model_copy(deep=True)
        instrument = self.instrument.model_copy(deep=True)
        if previous is not None:
            _carry_into(structure, instrument, previous, self.carry)
        if prepare is not None:
            prepare(index, data, structure, instrument)
        ref = Refinement(structure, instrument, backend=self._backend,
                         solver=self._solver,
                         history=self._history_spec(label + history_suffix))
        # The wavelength is a property of the beamline, declared once for the
        # whole series — but ``_carry_into`` warm-starts pattern n from pattern
        # n-1's *refined* λ, so the ``Refinement`` just built would snapshot that
        # refined value as its declared reference and its WAVELENGTH_CALIBRATION
        # would report the pattern-to-pattern drift (~0 ppm) instead of the
        # cumulative move from what the beamline actually stated.  The carried
        # value stays the warm start (no fit number moves); only the diagnostic's
        # reference is threaded from the series root, exactly as ``branch()``
        # inherits the root declaration rather than re-declaring a refined λ
        # (WP-1134).  Guarded on the line count so a ``prepare`` hook that swaps
        # the anode (a genuine per-pattern re-declaration) keeps its own snapshot.
        root_declared = _declared_wavelengths(self.instrument)
        if len(root_declared) == len(ref._declared_wavelengths):
            ref._declared_wavelengths = list(root_declared)
        if previous_hkl and mode in ("lebail", "pawley"):
            # Le Bail/Pawley per-hkl intensities are path-dependent state that
            # lives *outside* θ, so `_carry_into` cannot reach them — and a flat
            # re-seed would throw away everything the previous pattern learned,
            # which for an extraction is most of what there is to learn.  This
            # is the same channel a checkout uses to restore a node's
            # ReflectionState, matched by hkl at the first stage's compile.
            ref._pending_reflections = [r.model_copy(deep=True)
                                        for r in previous_hkl]
        result = ref.fit(data, mode=mode, plan=plan,
                         two_theta_limits=two_theta_limits,
                         events=(None if stream is None
                                 else _SeriesStream(stream, **(stamp or {}))),
                         cancel=cancel)
        _link_history(ref, position, label, previous_tag)
        return ref, result

    def _verify_discontinuities(self, steps: list[_FlaggedStep], patterns,
                                names, mode, base_plan, two_theta_limits,
                                prepare, *, stream: EventStream | None = None,
                                cancel=None) -> None:
        """Refit each flagged step's two patterns cold, and record the ratio.

        The measurement the ramp agent ran by hand: a step that survives two
        *independent* fits is in the specimen, and one that does not was made
        by the chain.  Both fits go through :meth:`_fit_one` with no
        ``previous``, which is exactly the ``"cold"`` rung — the same plan from
        the same initial models — so the comparison is against a fit the runner
        already knows how to produce rather than a special one written here.

        Each pattern is refitted **once** however many of its parameters were
        flagged, and the diagnostic is left alone when a cold fit does not
        determine the path (a held phase, a stage that returned nothing for
        it): a ratio needs both ends, and an absent one is not a zero.

        ``cancel`` is the chain's own token, threaded through because these are
        ordinary fits and up to ``2s`` of them: a caller who can stop the walk
        must be able to stop the check.  A cancel here leaves every diagnostic
        it had not reached exactly as the walk wrote it — ``value`` absent, the
        absent-for-cause state — so a stopped check reports nothing about a
        step rather than a half-measured something.
        """
        index_of = {name: i for i, name in enumerate(names)}
        cold: dict[int, RefinementResult] = {}

        def refit(k: int) -> RefinementResult:
            if k not in cold:
                _ref, result = self._fit_one(
                    patterns[k], names[k], None, [], base_plan, mode,
                    two_theta_limits, k, (None, None), prepare, k, ".verify",
                    stream=stream, cancel=cancel,
                    stamp={"series_index": k, "series_label": names[k],
                           "series_n": len(patterns), "series_pass": "verify"})
                cold[k] = result
            return cold[k]

        for s in steps:
            if cancel is not None and bool(cancel):
                return
            a, b = index_of[s.labels[0]], index_of[s.labels[1]]
            try:
                va = _value_of(refit(a), s.path)
                vb = _value_of(refit(b), s.path)
            except RefinementCancelled:
                return
            d = s.diagnostic
            if va is None or vb is None or not s.step:
                d.message += ("; an independent cold refit of both patterns "
                              "does not determine this parameter, so the step "
                              "could not be re-measured")
                continue
            # signed, both sides: a cold pair stepping as far the *other* way
            # is not a reproduction, and two magnitudes divided would call it
            # one (see _FlaggedStep.step)
            cold_step = vb - va
            d.value = cold_step / s.step
            d.message += (f"; refitted cold and independently the two patterns "
                          f"step by {cold_step:.4g}, {d.value:.2f}× the "
                          f"chain's")
            d.suggestion += ("; that check has been run, and a ratio near 1.0 "
                             "means the step is in the data while one near 0 "
                             "means the chain made it — a negative one is a "
                             "cold pair that moved the other way, which is "
                             "neither")

    def _history_spec(self, label: str):
        """Per-pattern history target: a file under the given directory.

        The backward pass of ``direction="both"`` writes to ``<label>.backward``
        so a verification chain never appends its nodes to the reported chain's
        log — the JSONL format is append-only by design, and two headers in one
        file would make the reload ambiguous.

        **Every escalation rung takes a suffix for the same reason**
        (``<label>.warm_staged``, ``<label>.cold``), which before WP-1051 the
        cold restart did not: it reused the warm fit's label, so a reseeded
        pattern wrote two headers and two trees' nodes into one file and
        reloaded as an interleaving of both.  The rungs are separate fits of the
        same data — same ``tree_id``, since that is the data fingerprint — and
        keeping them apart is what lets the kept one be reloaded on its own.
        """
        spec = self._history
        if isinstance(spec, bool):
            return spec
        directory = Path(spec)
        directory.mkdir(parents=True, exist_ok=True)
        return directory / f"{label}.jsonl"

    # ------------------------------------------------------------------
    @property
    def fitted_structures(self) -> list[Structure]:
        """Each pattern's refined structure, in series order."""
        return self._structures

    @property
    def fitted_instruments(self) -> list[Instrument]:
        """Each pattern's refined instrument, in series order."""
        return self._instruments


def _link_history(ref: Refinement, position: int, label: str,
                  previous_tag: tuple[str | None, str | None]) -> None:
    """Record the chain on the tree's root node.

    A history tree is pinned to one pattern by its data fingerprint, so a
    series cannot be one tree and the link cannot be a parent edge.  It goes in
    ``Annotation.notes``, which is append-only and free-form, and it is what
    makes a saved series navigable: given any pattern's log, the note names the
    node its starting values came from.
    """
    tree = ref.history
    if tree is None or tree.root is None:
        return
    notes = {"series_position": str(position), "series_label": label}
    if previous_tag[0] is not None:
        notes["series_warm_start_tree"] = previous_tag[0]
    if previous_tag[1] is not None:
        notes["series_warm_start_node"] = previous_tag[1]
    tree.annotate(tree.root.id, notes=notes)


def _better(a: RefinementResult, b: RefinementResult) -> bool:
    """Is ``a`` the fit to keep?  Convergence first, then Rwp."""
    if (a.status == "diverged") != (b.status == "diverged"):
        return b.status == "diverged"
    return a.statistics.rwp < b.statistics.rwp


def _prefer(result: RefinementResult, truncated: bool,
            best: RefinementResult | None, best_truncated: bool) -> bool:
    """Is ``result`` the attempt to keep, given which of the two was cut short?

    :func:`_better` ranks a diverged fit below a finished one and then goes on
    Rwp, and that is the whole rule while every attempt spent what its own plan
    allowed.  A first rung the WP-1127 bound truncated did not: it reports
    ``"max_iter"`` because *this ladder* stopped it early, so at equal Rwp
    keeping it over a rung that ran to completion would let the bound pick the
    answer — the one route by which a bound could reach one.  Measured: with a
    truncated rung and its rescue at the same Rwp, ``_better`` alone keeps the
    truncated one and the entry comes back ``"max_iter"``.

    So a truncated attempt loses to any untruncated one outright, and
    :func:`_better` decides only between two attempts in the same state.  A
    first rung that hit the *plan's* own budget is untouched by this and is
    still kept if nothing beats it, which is what the ladder has always done.
    """
    if best is None:
        return True
    if truncated != best_truncated:
        return best_truncated
    return _better(result, best)


def _reseed_needed(result: RefinementResult, accepted_rwp: list[float],
                   factor: float) -> bool:
    if result.status == "diverged":
        return True
    if not accepted_rwp:
        return False
    reference = float(np.median(accepted_rwp))
    return result.statistics.rwp > factor * reference


def _reseed_diagnostics(entry: SeriesEntry) -> list[Diagnostic]:
    if not entry.reseeded:
        return []
    warm = entry.rwp_warm
    now = entry.statistics.rwp if entry.statistics else float("nan")
    return [Diagnostic(
        level="warning", code="SEQUENTIAL_RESEED",
        where=[entry.label or str(entry.index)],
        message=(f"pattern {entry.index} ({entry.label}) was refitted from the "
                 f"initial model: warm-starting from its neighbour reached "
                 f"Rwp {warm:.4f} against {now:.4f} cold"),
        suggestion=("this point is a good fit but its starting values did not "
                    "come from its neighbour, so it is not evidence that the "
                    "trajectory is continuous here; check whether the specimen "
                    "or the model changed at this point of the series"),
    )]


def _unrecovered_diagnostics(entry: SeriesEntry) -> list[Diagnostic]:
    """A pattern no rung could rescue: quarantined, and said out loud (WP-1051).

    Derived from the entry rather than recorded when it happened, like every
    other fence here, so a :class:`SeriesResult` reloaded from JSON reports the
    same diagnostics as the run that produced it.  The condition is the fit's
    own ``status``: "diverged after the last rung" and "diverged" are the same
    statement once the ladder has run, so there is no second flag to keep in
    agreement with it.
    """
    if entry.status != "diverged":
        return []
    tried = ", ".join(entry.rungs_tried) or entry.rung
    return [Diagnostic(
        level="warning", code="SEQUENTIAL_UNRECOVERED",
        where=[entry.label or str(entry.index)],
        message=(f"pattern {entry.index} ({entry.label}) diverged and was still "
                 f"diverged after every rung the chain tried ({tried}); it "
                 f"seeded no successor and its Rwp was left out of the series "
                 f"median"),
        suggestion=("the values on this point are not a measurement — read it as "
                    "a failed fit, not as a datum, and do not interpolate across "
                    "it; the chain continued from the last pattern that "
                    "converged, so its neighbours are unaffected.  Fit this "
                    "pattern on its own to find out why: a specimen change the "
                    "model does not have, a bad scan, or a starting model that "
                    "no longer suits this end of the series"),
    )]


def _cancelled_diagnostic(n_done: int, n_total: int, *,
                          pass_name: str = "forward") -> Diagnostic:
    """A short ``entries`` list, said out loud (WP-1016).

    Without it a cancelled series is indistinguishable from a shorter series that
    ran to completion — and every trajectory here is read as a curve over "the
    series", so silence would make the missing tail look like data that stops.
    """
    return Diagnostic(
        level="warning", code="SEQUENTIAL_CANCELLED", where=[],
        message=(f"the {pass_name} chain was cancelled after {n_done} of "
                 f"{n_total} patterns; the pattern in flight was abandoned "
                 "(no node, no commit) and the rest were never started"),
        suggestion=("the entries reported are complete fits and stand on their "
                    "own, but the trajectory is truncated, not finished: "
                    "re-run the series to extend it, and do not read the last "
                    "point as the end of the ramp"),
    )


def _noise_floor(*values) -> float:
    """The smallest change in these values that is not floating-point noise.

    See :data:`NOISE_FLOOR_REL`: relative to the parameter's own magnitude, and
    never below 1e-9 absolute so a parameter that is identically zero does not
    get an infinitely fine floor.
    """
    magnitude = max((float(np.max(np.abs(v))) for v in values if len(v)),
                    default=0.0)
    return NOISE_FLOOR_REL * max(1.0, magnitude)


@dataclass(frozen=True)
class _FlaggedStep:
    """One flagged step, in the form the optional verification pass needs.

    The diagnostic says it in prose; this says *which two patterns* and *how
    big*, so :meth:`SequentialRefinement._verify_discontinuities` re-measures
    the same step rather than re-deriving which one was meant from the
    message (the one-authority rule: the flagging code is the only place that
    knows which pair it flagged).

    ``step`` is the **signed** difference, later minus earlier, and the
    verification ratio is signed with it: two magnitudes divided would report a
    cold pair that stepped the *other way* as 1.00, which reads as the one
    thing the check exists to distinguish it from.  The diagnostic's own
    message keeps the magnitude, which is what a reader compares with the
    median step.
    """

    path: str
    labels: tuple[str, str]
    step: float
    diagnostic: Diagnostic


def _discontinuity_steps(series: SeriesResult) -> list[_FlaggedStep]:
    """Steps far larger than the same parameter's typical step in this series.

    The one authority: every caller takes the diagnostics off these (there is
    no second function returning only the diagnostics, which would be a second
    name for one fact).

    Reported, never smoothed: a jump is either the science (a transition) or a
    chain failure, and nothing here can tell them apart — so the diagnostic
    names both and the trajectory is left exactly as fitted.
    """
    if len(series) < MIN_POINTS_FOR_DISCONTINUITY:
        return []
    out: list[_FlaggedStep] = []
    for path in series.paths(varied_only=False):
        traj = series.trajectory(path)
        if len(traj) < MIN_POINTS_FOR_DISCONTINUITY:
            continue
        xv, value, sd = traj.arrays()
        step = np.abs(np.diff(value))
        scale = float(np.median(step))
        if not np.isfinite(scale) or scale <= _noise_floor(value):
            continue
        combined = np.sqrt(np.nan_to_num(sd[:-1]) ** 2 + np.nan_to_num(sd[1:]) ** 2)
        big = (step > DISCONTINUITY_FACTOR * scale) & (
            step > DISCONTINUITY_SIGMA * combined)
        if not big.any():
            continue
        k = int(np.argmax(step * big))
        out.append(_FlaggedStep(
            path=path, labels=(traj.labels[k], traj.labels[k + 1]),
            step=float(value[k + 1] - value[k]),
            diagnostic=Diagnostic(
                level="info", code="SEQUENTIAL_DISCONTINUITY", where=[path],
                message=(f"{path} steps by {step[k]:.4g} between "
                         f"{traj.labels[k]} and {traj.labels[k + 1]} "
                         f"({traj.x_label} {xv[k]:g} → {xv[k + 1]:g}), "
                         f"{step[k] / scale:.0f}× its median step over the series"),
                suggestion=("either the specimen genuinely changed here (a "
                            "transition, a phase appearing) or the chain failed "
                            "at this point and carried the error onward — check "
                            "this pattern's own fit before reading the jump as "
                            "physics"),
            )))
    return out


def _persistent_diagnostics(series: SeriesResult) -> list[Diagnostic]:
    """``SEQUENTIAL_PERSISTENT_FINDING`` — a per-pattern code that is really
    about the series (WP-1110 item 8).

    A per-pattern diagnostic can only ever say "this pattern". Nothing in a run
    of 68 says **"42 of 68"**, and that is the sentence a caller acts on: one
    `BOUND_HIT` is a pattern that hit a bound, a `BOUND_HIT` in most of them is
    a model whose bound is wrong. The trigger episode is exactly this — 425
    `BOUND_HIT` diagnostics went unread for two hours while
    ``phases.3.cell.c`` was pinned in 42 of 68 patterns and
    ``phases.3.lor_size`` in 44 of 68. The package said so from pattern 1, and
    per-pattern was the only place it said it.

    **The threshold is a change of subject, not a sensitivity.** Above half the
    patterns a finding describes the series rather than some of its members, so
    that is where the series-level line is drawn; below it the per-entry
    diagnostics already say what there is to say, and repeating them here would
    be a second authority on the same fact. Counted per (code, path) so the
    message can name the parameter, and the codes are an open vocabulary — this
    aggregates whatever fired, and needs no edit when a new one lands.
    """
    n = len(series.entries)
    if n < MIN_POINTS_FOR_PERSISTENCE:
        return []
    counts: dict[tuple[str, str], int] = {}
    # The worst level any occurrence carried, and it travels in *both*
    # directions.  A summary must not report an error as a warning because most
    # occurrences were warnings — and it must not promote an `info` either: a
    # deliberate `dispersion=None` fires `DISPERSION_NEGLECTED` on every pattern
    # of a series, and "68 of 68" is worth saying without calling a declared
    # choice a warning.
    levels: dict[tuple[str, str], str] = {}
    for entry in series.entries:
        # once per pattern per (code, path): a code that fires twice in one
        # pattern is one pattern, or the count would measure stages
        seen: set[tuple[str, str]] = set()
        for d in entry.diagnostics:
            for p in (d.where or [""]):
                key = (d.code, p)
                if key not in seen:
                    seen.add(key)
                    counts[key] = counts.get(key, 0) + 1
                # `is None` rather than a default of "info": with a default,
                # an all-info code never satisfies the comparison and the key
                # is never written at all
                worst = levels.get(key)
                if worst is None or _LEVEL_RANK[d.level] > _LEVEL_RANK[worst]:
                    levels[key] = d.level

    out: list[Diagnostic] = []
    for (code, path), count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
        if count * 2 <= n:
            continue
        where = [path] if path else []
        subject = path or "the fit"
        out.append(Diagnostic(
            level=levels[(code, path)], code="SEQUENTIAL_PERSISTENT_FINDING",
            where=where, value=count / n,
            message=(f"{code} fired on {subject} in {count} of {n} patterns "
                     f"({count / n:.0%} of the series)"),
            suggestion=(f"read this as a property of the model rather than of "
                        f"any one pattern: {code} in most of a series is the "
                        f"same finding repeated, and the thing to change is "
                        f"the model or the plan, not the individual fits. The "
                        f"per-pattern diagnostics carry each occurrence"),
        ))
    return out


def _path_dependence_diagnostics(forward: SeriesResult,
                                 backward: SeriesResult) -> list[Diagnostic]:
    """Where the forward and backward chains disagree beyond their esds.

    The one measurement that says whether a sequential trajectory is a
    measurement or an artefact of the ordering.  Two chains that agree are two
    different starting-point sequences reaching the same answer; two that do
    not have found a parameter whose value the data do not determine on their
    own.

    Both restrictions below narrow that claim, and neither is cosmetic: the
    comparison is made **per pattern, between the same pattern in each chain**,
    and only where *both* chains measured an esd for it.  A pattern one chain
    never refined this path in is not compared at all, so a path can be
    reported on for part of a series and be silent for the rest of it — and a
    path the two chains share no measured pattern for is not judged here at
    all.
    """
    out: list[Diagnostic] = []
    for path in forward.paths(varied_only=False):
        f, b = forward.trajectory(path), backward.trajectory(path)
        # Pair the two chains by *pattern label*, not by position.  Equal
        # lengths do not make two trajectories comparable: ``trajectory()``
        # skips patterns where the path is absent, and WP-1301 drops a held
        # structural path from ``RefinedParameter`` rows entirely, so a path
        # held in the forward chain's first pattern and in the backward
        # chain's last yields two seven-long trajectories over *different*
        # patterns.  Subtracting those position by position compares p1
        # against p0 the whole way down and reports a clean, monotonic ramp as
        # tens of sigma of path dependence — with every esd two-sided, so the
        # mask below never sees it.  Intersecting on labels is also what lets
        # the old ``len(f) != len(b)`` gate go: unequal lengths no longer mean
        # the path goes unexamined, only that fewer patterns are comparable.
        first_in_b: dict[str, int] = {}
        for j, label in enumerate(b.labels):
            first_in_b.setdefault(label, j)
        pairs = [(i, first_in_b[label]) for i, label in enumerate(f.labels)
                 if label in first_in_b]
        if not pairs:
            continue
        fi = np.asarray([i for i, _ in pairs], dtype=int)
        bj = np.asarray([j for _, j in pairs], dtype=int)
        labels = [f.labels[i] for i in fi]
        _, vf_all, sf_all = f.arrays()
        _, vb_all, sb_all = b.arrays()
        vf, sf = vf_all[fi], sf_all[fi]
        vb, sb = vb_all[bj], sb_all[bj]
        # Judge a pattern only where *both* chains measured an esd.  A
        # parameter with no esd anywhere cannot be judged this way at all, and
        # neither can a pattern one chain refined and the other held: its esd
        # exists on one side only, and dividing the two values' difference by
        # it reports a significance the held side never earned.  A tied
        # dependent path reaches exactly that state routinely, since
        # ``_build_result`` emits tie rows whether or not their source was
        # refined.  The mask is per pattern rather than per path, so the
        # patterns both chains did measure are still judged.
        comparable = np.isfinite(sf) & np.isfinite(sb)
        combined = np.sqrt(np.nan_to_num(sf) ** 2 + np.nan_to_num(sb) ** 2)
        if not np.any(comparable & (combined > 0.0)):
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            n_sigma = np.abs(vf - vb) / np.where(combined > 0.0, combined, np.nan)
        n_sigma = np.where(np.abs(vf - vb) > _noise_floor(vf, vb), n_sigma, 0.0)
        n_sigma = np.where(comparable, n_sigma, 0.0)
        if not np.any(n_sigma > PATH_DEPENDENCE_SIGMA):
            continue
        k = int(np.nanargmax(n_sigma))
        out.append(Diagnostic(
            level="warning", code="SEQUENTIAL_PATH_DEPENDENT", where=[path],
            message=(f"{path} differs between the forward and backward chains "
                     f"by up to {n_sigma[k]:.1f}σ (at {labels[k]}: "
                     f"{vf[k]:.6g} vs {vb[k]:.6g})"),
            suggestion=("this parameter's trajectory depends on the order the "
                        "series was refined in, so it is not determined by the "
                        "data alone: hold it fixed, restrain it, or report the "
                        "spread between the two directions as its uncertainty "
                        "— its per-pattern esd understates it"),
        ))
    return out


def refine_sequential(patterns: Sequence[PatternData], structure: Structure,
                      instrument: Instrument, *,
                      carry: Sequence[str] = ("*",),
                      backend: str = "numpy", solver: str = "trf",
                      history: bool | str | Path = False,
                      **kw) -> SeriesResult:
    """One-shot functional API for a warm-started series.

    ``refine_sequential(patterns, structure, instrument, x=temperatures)``.
    Keyword arguments beyond ``carry``/``backend``/``solver``/``history`` go to
    :meth:`SequentialRefinement.fit`.
    """
    series = SequentialRefinement(structure, instrument, carry=carry,
                                  backend=backend, solver=solver, history=history)
    return series.fit(patterns, **kw)
