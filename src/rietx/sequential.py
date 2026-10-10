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
``SEQUENTIAL_RWP_OUTLIER``
    every rung came back above the Rwp fence, so the kept fit is not like its
    neighbours (WP-1469); the pattern is not quarantined, and the steps either
    side of it are left out of the discontinuity scan.
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

Two more belong to the magnetic arm (WP-1329), and they are fences of exactly
the same kind — a series through an ordering transition is a series whose
answer *changes character* part-way along, and warm-starting is how that gets
hidden:

``SEQUENTIAL_MOMENT_HOLD``
    on how many patterns the moment came back unsupported (WP-1327's ratio,
    |m| below :data:`~rietx.report.schemas.MOMENT_SUPPORT_SIGMA` of its own
    esd), and on which of them the successor's modulus was therefore reseeded
    to its floor instead of warm-started from the value before it.  A moment a
    pattern does not support must not become the *starting point* of the next
    pattern, because |F_m|² ∝ m² makes a stale modulus a local minimum the
    next fit has no gradient to leave.
``SEQUENTIAL_MOMENT_ONSET``
    where along the axis the moment stops being supported, as a bracket
    between the last released pattern and the first held one — read off the
    per-pattern verdicts and never off the |m| column, which a warm-started
    chain smooths straight through the transition.  Under ``direction="both"``
    it also carries the other chain's bracket and says whether the two agree;
    disagreement is the signature of a chain that carried a moment across the
    transition in one direction and not the other, which is the one thing a
    single chain cannot see.

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
import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Literal

import numpy as np

from . import runs
from .backend.api import backend_dtype_note
from .history.events import EventStream, _attach_progress, as_event_stream
from .history.tree import RefinementTree
from .optimize.cancel import RefinementCancelled
from .optimize.least_squares import NFEV_PER_ITERATION, SOLVERS
from .params.vector import VAR_PREFIX, ParameterTable
from .refine import (
    _VERSION,
    Refinement,
    _declared_wavelengths,
    _extract_reflections,
    _judge_magnetic_groups,
    _refined_state,
    _refuse_without_phases,
    _utcnow,
)
from .report.schemas import THRESHOLDS_VERSION, MomentEvidence
from .schemas.common import Diagnostic, Mode, Provenance
from .schemas.history import ReflectionState
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.results import RefinementResult
from .schemas.sequential import SeriesEntry, SeriesFailure, SeriesResult, SeriesStep
from .schemas.structure import (
    MOMENT_COMPONENTS,
    MOMENT_FLOOR_MU_B,
    Structure,
)
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

#: Per-pattern codes :func:`_persistent_diagnostics` never aggregates, because
#: they are about how the package *measured* a pattern rather than about the
#: model, so "in most of the series" changes no subject.  The rule for a
#: member: the code would read the same on a series whose model is right.
#: ``FROZEN_COMPILE_STALE`` (#272) says a result was measured on a fresh
#: compile whose χ² sits a fraction from the frozen one; a chain whose every
#: last stage moves the zero and the widths fires it on every pattern (the QPA
#: round-robin sample-1 chain, 1.3-2.1e-2), and promoting it would turn a
#: statement about compile sizing into a warning about the model.
NOT_A_SERIES_FINDING = frozenset({"FROZEN_COMPILE_STALE"})

#: A phase width is called a soak when it reaches this multiple of the first
#: width the series measured **and** the fit's GoF reaches
#: :data:`WIDTH_GROWTH_GOF_FACTOR` × its own at that pattern (WP-1465, issue
#: #451).  3 is the reporter's, and it sits between the two soaks measured: the
#: operando chain's widths were 3.4× their first scan at the onset, and the
#: synthetic's one-phase chain passes 3.65× on its second soaked pattern (2.3×
#: on its first, where GoF had risen 1.9×).  The width ratio does not separate
#: on its own.  The round-robin chain ``tests/test_acceptance_sequential`` runs
#: is a clean one, and its widths wander 4-946× across mixtures because a minor
#: phase's width is barely determined: against each trajectory's first value,
#: growth alone fires on 11 of its 24.  Against the first value the series
#: *measured* (:data:`WIDTH_GROWTH_SIGMA`) it fires on none.
WIDTH_GROWTH_FACTOR = 3.0

#: The misfit half of the soak test: GoF at the flagged pattern over GoF at the
#: reference.  **GoF rather than Rwp**, although the issue said Rwp: Rwp tracks
#: Rexp, which rises as the counts fall, so a series losing intensity raises
#: Rwp under a model that is right.  GoF divides that out, and on the
#: synthetic, whose counts are constant, the two ratios are the same number.
#: The value is set for margin, against the denominator it is applied to: the
#: reference can be any pattern, so the clean bound is the largest GoF_j/GoF_i
#: over every ordered pair of one chain.  Over the 75 multi-pattern series the
#: suite runs that is **1.52**, on the thermal ramp's bounded-first-rung
#: fixtures, whose model is right and some of whose fits stopped early (1.14
#: on the round-robin chain, the one that frees widths).  1.5 would have had
#: no margin.  The synthetic soak reads 3.05 where its width crosses 3×, so 2
#: sits 1.3× clear of the one and 1.5× under the other.  This half is also what
#: keeps a width that grows *for real* silent, and the suite has no such chain,
#: so ``tests/test_sequential.py`` builds one: a correct model over a specimen
#: whose strain grows 5×, GoF flat to within 2 %.
WIDTH_GROWTH_GOF_FACTOR = 2.0

#: How many of its own esds a width must be to serve as the reference, and how
#: many combined esds its growth must be.  The first half is what keeps the
#: ratio a ratio: the round-robin chain's first ``lor_strain`` is 5.85e-5 with
#: an esd of 3e3, so any later value is "946×" it and means nothing.
WIDTH_GROWTH_SIGMA = 3.0

#: The phase widths the soak test reads, and whether each is a width or a
#: variance.  The Gaussian pair are variance coefficients (deg² 2θ), so their
#: ratio is taken on the square root, the width they contribute.  A Stephens
#: block (``phases.i.microstrain.dof.k``) is not here: it has no single width,
#: and while it is declared it locks ``lor_strain``, so a series refining one
#: is not screened.
_WIDTH_SUFFIXES = {".lor_strain": False, ".lor_size": False,
                   ".gauss_strain": True, ".gauss_size": True}

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

#: How ``SequentialRefinement.fit`` reacts to a pattern on which **every
#: rung** of the ladder raised — an uncaught exception out of
#: ``Refinement.fit`` on each attempt, not a fit that converged somewhere the
#: reseed fence rejected (that is ``SeriesEntry.status == "diverged"``, handled
#: by the quarantine below with no policy).  A rung that raises is a rung that
#: lost and the ladder escalates past it (WP-1333), so by the time a policy is
#: consulted the last rung tried was a **cold** fit from the initial models —
#: unless ``reseed=False`` or the pattern was the first walked, which have no
#: ladder — and what failed is the pattern rather than its neighbour's state.
#:
#: ``"carry"`` is the default (WP-1333; ``"raise"`` was, PR #386): the pattern
#: is recorded in ``SeriesResult.failures`` with ``SERIES_PATTERN_FAILED`` and
#: its successor warm-starts from the **last accepted** state, exactly as the
#: WP-1051 quarantine treats a diverged fit — a series is N separate
#: refinements, and one that cannot be fitted is no reason to throw away the
#: others, the same argument that makes a cancelled series *return*.
#: ``"skip"`` records it the same way but fits the successor **cold**, for a
#: caller who reads the failure as evidence against the warm state too.
#: ``"raise"`` ends the chain in the last rung's exception, with the partial
#: results kept: ``SequentialRefinement.results_``/``.failures_`` and the
#: exception's own ``series_results``/``series_failures``/``series_failed``.
#:
#: **A series that measured nothing raises under every policy**: if the
#: reported chain ends with no entry and at least one failure, the last
#: exception is raised with ``series_failures`` attached, because an empty
#: ``SeriesResult`` is not an answer and "a failure raises" is the package's
#: contract.  A cancelled chain is exempt (it *returns*, WP-1016), and so is the
#: ``direction="both"`` backward pass, whose failures cost only the comparison.
ON_ERROR_POLICIES = ("raise", "skip", "carry")

#: The escalation ladder in order, as names (WP-1051).  ``"warm"`` is the
#: collapsed warm refit, ``"warm_staged"`` the full staged plan from the warm
#: state, ``"cold"`` the full staged plan from the initial models — which is
#: also what the *first* pattern of every chain runs, having no predecessor.
RUNGS = ("warm", "warm_staged", "cold")


class _PatternRaised(Exception):
    """A pattern's own :meth:`Refinement.fit` raised; ``original`` is what.

    The wrapper exists to draw one line: **the fit is guarded, the caller's
    hooks are not** (WP-1333).  :meth:`SequentialRefinement._fit_one` runs
    ``prepare`` and ``constrain`` and then the fit, and only the last is a
    rung that can lose.  Before this the ``except Exception`` sat around all
    three, so under ``on_error="skip"``/``"carry"`` a typo in a caller's hook
    was swallowed once per pattern and the series came back empty, while the
    ``constrain`` docstring said a raise there ends the series.  Wrapping at
    the fit, rather than catching the hooks separately, keeps that the
    default: an exception that is not this type is the caller's, and it
    propagates untouched.
    """

    def __init__(self, original: Exception) -> None:
        super().__init__(repr(original))
        self.original = original


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
        # Forwarded by *assignment* rather than by a method, so that
        # ``refine._snapshot_sinks``'s ``hasattr`` test keeps telling the truth:
        # a plain ``EventStream`` inner takes no snapshot, and a wrapper that
        # advertised one anyway would hand it a call it cannot answer.  One
        # snapshot file per series, rewritten as the chain walks, which is what
        # makes ``rietx watch`` show the pattern being fitted right now.
        #
        # The recorder counts as a second place to look, because a caller who
        # passed ``events=`` of their own leaves it *chained* onto that stream
        # rather than being it — and a plain ``EventStream`` inner then answered
        # ``hasattr`` with a no, so a GUI series, and every series with an
        # ``events=`` path, recorded a run with no picture in it.
        target = (inner if hasattr(inner, "write_snapshot")
                  else runs.recorder_of(inner))
        if target is not None:
            self.write_snapshot = target.write_snapshot

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
        intermediate_ftol=plan.intermediate_ftol,
        # the alternation is the protocol's, not a stage's: a collapsed warm
        # refit under mode="lebail" would otherwise run one pass (WP-1323)
        lebail_passes=plan.lebail_passes)


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
                carry: Sequence[str]) -> list[str]:
    """Overwrite ``structure``/``instrument`` values from a fitted pair, in place.

    Only paths matching one of the ``carry`` globs move; everything else keeps
    the value it came in with (the *initial* model, when this is called from the
    chain).

    **A refined coordinate is carried as its site's displacement**, because
    copying the entry carries nothing (WP-1333).  A coordinate is a row
    x = x_stored + Σ Bₖθₖ whose DOF every build rederives to zero, so the DOF
    read off the fitted pair is 0.0 wherever the fit left the atom, and the
    re-derivation below then put the coordinate back at *this* model's stored
    value — while ``cell.a`` beside it carried, and ``carry=["*"]`` said the
    coordinate had too.  :meth:`ParameterTable.displace_anchored_dofs` solves
    for the displacement that reaches the fitted coordinates instead, a site
    at a time, so a glob naming only ``x`` still moves every row the site
    ties to it.  Returns the DOF paths it displaced, which
    :func:`_reanchor_carried` needs once the caller's hook has tied any of
    them.

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

    def named(path: str) -> bool:
        return any(fnmatch.fnmatchcase(path, g) for g in carry)

    for e in table.entries:
        value = previous.get(e.path)
        if value is not None and named(e.path):
            e.value = value
    # a rigid body carries its record, the quaternion and the origin, never
    # its increment (WP-1805): the increment reads zero on a fresh table
    orientations = {f"phases.{ip}.rigid_bodies.{b}": body.orientation
                    for ip, phase in enumerate(source[0].phases)
                    for b, body in enumerate(phase.rigid_bodies)}
    # …and its torsions' angles, the same kind about one axis each (WP-1808)
    torsions = {f"phases.{ip}.rigid_bodies.{b}": [t.angle for t in body.torsions]
                for ip, phase in enumerate(source[0].phases)
                for b, body in enumerate(phase.rigid_bodies)}
    displaced = table.displace_anchored_dofs(previous, named, orientations, torsions)
    # Hold everything, then read the affine map back: tied entries (crystal-
    # system cell ties, Wyckoff coordinate DOFs, site-symmetry ADP patterns)
    # are re-derived from whatever their sources now hold, so a narrow carry
    # glob can never leave a tie inconsistent with its source.
    table.set_vary(["*"], False)
    resolved = table.decode(np.zeros(0))
    for e in table.entries:
        e.value = resolved[e.path]
    table.apply_to_models(structure, instrument)
    return displaced


def _reanchor_carried(ref: Refinement, displaced: Sequence[str],
                      source: tuple[Structure, Instrument],
                      previous_vars: dict[str, float]) -> None:
    """Keep a carried coordinate where it was when the hook ties its DOF.

    :func:`_carry_into`'s coordinate carry meets the ``constrain`` hook here.
    A hook that ties a displacement DOF to a named variable re-declares the
    variable at its start value, and the build that applies the tie rebases
    the anchor on that value (WP-1432).  But the carried coordinate was
    written with the variable at the previous pattern's *fitted* value, so it
    already holds that displacement, and :func:`_carry_variables` warming the
    variable adds it again, once per pattern.  Before the coordinate carried,
    the hook's tie gave the right start by accident, from an anchor the carry
    had never moved; that is why the carry could not land without this.

    So the anchor is rebased against what the source held
    (:meth:`ParameterTable.reanchor_dofs`), and the tied coordinate becomes
    the source's anchor plus whatever the variable starts at.  The variable
    warm-started gives the fitted coordinate exactly.  The variable excluded
    from ``carry`` restarts the coordinate with it, as a narrow glob restarts
    every tie's source.  Runs between the hook and the variable carry, the one
    order in which both the tie and the start value exist.  A DOF the hook
    ties to another DOF contributes zero at both ends, and a hook that ties
    nothing costs one membership test.
    """
    tied = [p for p in displaced if p in ref._ties]
    if not tied:
        return
    absorbed = {e.path: e.value for e in ParameterTable(*source).entries}
    absorbed.update({f"{VAR_PREFIX}{name}": value
                     for name, value in previous_vars.items()})
    table = ref._working_table()
    if table.reanchor_dofs(tied, absorbed):
        ref._write_back(table)


def _carry_variables(ref: Refinement, previous: dict[str, float],
                     carry: Sequence[str]) -> None:
    """Warm this pattern's named variables from the last accepted one.

    :func:`_carry_into`'s other half, and it has to be a second function
    because a variable is reachable by neither of that one's arguments: there
    is no field of ``Structure`` or ``Instrument`` holding one, so the
    ``ParameterTable`` built from a fitted pair has never heard of it.  The
    register on the ``Refinement`` is the variable's only model (WP-1119), and
    a fresh ``Refinement`` per pattern starts that register wherever the
    ``constrain`` hook declared it.  Left alone, a variable would be the one
    parameter ``carry=["*"]`` did not carry (WP-1441, issue #376).

    Runs **after** the hook, which is the only order available: the value
    cannot be written before the name exists.  ``carry`` is matched against
    ``vars.<name>``, the ordinary dot-path the table, ``set_vary`` and
    ``parameters()`` all know it by, so ``carry=["phases.*", "vars.*"]``
    reads the way it looks.

    :meth:`~rietx.refine.Refinement.set_values` rather than a write to the
    register: it refreshes the ties that follow the variable and writes the
    models through, so the stage that compiles next sees a structure agreeing
    with θ.  It records no node here — the pattern's history tree does not
    exist until its ``fit`` fingerprints the data — so the warm start stays a
    starting point rather than an edit, exactly as ``_carry_into`` is.  Its
    refusals come with it: a hook that narrows a variable's bounds per pattern
    until the carried value falls outside them raises here, naming the path and
    the bounds, because a starting point the bounded solver cannot use is the
    caller's to fix and not this function's to clamp.

    One refusal is *not* the caller's, and is why the tied variables are
    dropped rather than offered: a variable may itself be tied to others
    (``tie("vars.total", {"vars.a": 1.0, "vars.b": 1.0})``, the multi-source
    form the manual documents), and ``set_values`` refuses a tied path by
    design.  Carrying one is meaningless anyway — it follows its sources, which
    are carried — so excluding it is the same decision ``_carry_into`` makes
    when it resolves the ties rather than writing through them.
    """
    if not previous:
        return
    values: dict[str, float] = {}
    for name, value in previous.items():
        path = f"{VAR_PREFIX}{name}"
        # a name the hook did not declare on *this* pattern has nothing to be
        # carried into, and ``set_values`` would refuse the whole dict for it;
        # a variable the hook tied to others follows them and is refused too
        if (name in ref._variables and path not in ref._ties
                and any(fnmatch.fnmatchcase(path, g) for g in carry)):
            values[path] = value
    if values:
        ref.set_values(values)


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


#: The modulus DOF of a moment block, which is the only moment path this
#: module reaches: the angles are WP-1327's business (held when the powder
#: average cannot see them, and never carried across a pattern boundary by
#: anything here), and the modulus is the one the series has an opinion about.
_MOMENT_DOF0 = re.compile(r"^phases\.(\d+)\.atoms\.(\d+)\.moment\.dof0$")


def _moment_evidence(ref, result: RefinementResult) -> list[MomentEvidence]:
    """This pattern's moment arm, or ``[]`` when the model carries none.

    :func:`rietx.report.magnetic.analyse_moments` rather than
    ``ref.report()``: a whole Layer-0/1/2 report per pattern would cost more
    than the fits do on a long chain, and this is the one arm a series needs.
    WP-1327's own writer either way — nothing here re-decides ``supported``,
    re-derives the crystal-axis components or re-reads an esd (WP-1076).

    The guard is the compiled model's own frozen magnetic block, so a
    non-magnetic series pays one ``any()`` over the phases and never builds a
    :class:`~rietx.params.vector.ParameterTable` at all.
    """
    model = getattr(ref, "_model", None)
    if model is None or not any(getattr(cp, "magnetic", None) is not None
                                for cp in model.phases):
        return []
    from .report.magnetic import analyse_moments

    table = ParameterTable(ref.structure, ref.instrument)
    # the model reads the moment DOFs in the last stage's frames (#598)
    table.pull_moment_frames(model)
    return analyse_moments(
        model, table.decode(table.x0()), ref.structure,
        held=list(result.stages[-1].held) if result.stages else [],
        esd={p.path: p.stderr for p in result.parameters
             if p.stderr is not None},
        # the same worst-|rho| list ``build_report`` hands it, so a powder-
        # degenerate pair is folded here exactly as on a single pattern
        correlations=(result.identifiability.top_correlations
                      if result.identifiability is not None else None),
        flat_axes=(result.stages[-1].moment_flat_axes if result.stages
                   else None),
        turned=(result.stages[-1].moment_turned if result.stages else None))


def _floor_unsupported_moments(structure: Structure,
                               evidence: Sequence[MomentEvidence]
                               ) -> tuple[Structure, list[str]]:
    """The carry source with every **unsupported** modulus back at its floor.

    WP-1301's rule along the series (WP-1329).  A pattern whose moment came
    back below :data:`~rietx.report.schemas.MOMENT_SUPPORT_SIGMA` of its own
    esd measured *no* moment, and handing that value to the next pattern as a
    starting point is how an unsupported moment becomes a small confident one:
    |F_m|² ∝ m², so a modulus sitting at a stale 2.5 μ_B is a place the next
    fit can stay, and a warm-started chain then prints a smooth |m| column
    straight through an ordering transition.

    **What moves is the starting point, not the answer.**  The pattern's own
    entry keeps the modulus the fit reached and the esd it was judged against
    — that ratio *is* the evidence, and overwriting it with the floor would
    delete the number a reader checks the verdict with.  The floor is applied
    to a copy handed to the successor's warm start.

    **The direction is preserved and the modulus stays free.**  The components
    are scaled, not zeroed, so the angle DOFs the site allows are untouched;
    and nothing here fixes the modulus, because it is the one direction that is
    not flat and it is how a moment legitimately climbs back out on a cooling
    ramp (the argument :func:`rietx.refine._flat_moment_paths` makes for never
    holding it).  Returns the structure unchanged, and no copy, when every site
    is supported.
    """
    from .crystallography.magnetic.operators import moment_magnitude

    # The scan runs on the *incoming* models and decides before anything is
    # copied, so a chain whose every site is supported — and a chain whose
    # unsupported moduli are already at nothing — pays one pass over the
    # evidence and no deep copy at all.
    scales: list[tuple[str, int, int, float]] = []
    for row in evidence:
        # only a *measured* absence: ``None`` is no verdict — a modulus the
        # caller stated and held, or one WP-1301 held with an unseen phase —
        # and flooring it would overwrite a value no fit judged
        if row.supported is not False or not row.path:
            continue
        m = _MOMENT_DOF0.match(row.path)
        if m is None:                            # pragma: no cover - shape
            continue
        ip, ja = int(m.group(1)), int(m.group(2))
        try:
            atom = structure.phases[ip].atoms[ja]
        except IndexError:                       # pragma: no cover - shape
            continue
        if atom.moment is None:
            continue
        magnitude = float(moment_magnitude(
            atom.moment.values(), structure.phases[ip].cell.lengths_angles()))
        # already at or below the floor: there is nothing stale to reseed, and
        # a moment of nothing has no direction to preserve either
        if magnitude <= MOMENT_FLOOR_MU_B:
            continue
        scales.append((row.path, ip, ja, MOMENT_FLOOR_MU_B / magnitude))
    if not scales:
        return structure, []
    out = structure.model_copy(deep=True)
    for _path, ip, ja, scale in scales:
        moment = out.phases[ip].atoms[ja].moment
        for name in MOMENT_COMPONENTS:
            par = getattr(moment, name)
            par.value = float(par.value) * scale
    return out, [path for path, *_rest in scales]


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

    ``carry_hkl_intensities`` decides the same thing for the state a glob
    cannot name: a Le Bail or Pawley pattern's per-hkl intensities, which live
    outside θ.  ``True`` (default) seeds each warm pattern from the last
    accepted pattern's intensities, matched by hkl; ``False`` starts every
    pattern's extraction afresh, exactly as the first pattern's (WP-1459,
    issue #440 — until then the only way was clearing a private attribute in a
    ``constrain`` hook).  No effect in Rietveld mode, which extracts none.

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
                 carry_hkl_intensities: bool = True,
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
        # the caller's statement is judged once, here; each pattern's
        # ``Refinement`` is built from carried (refined) values and is not
        _judge_magnetic_groups(structure)
        self.structure = structure.model_copy(deep=True)
        self.instrument = instrument.model_copy(deep=True)
        self.carry = list(carry)
        self.carry_hkl_intensities = bool(carry_hkl_intensities)
        self._history = history
        self.results_: list[RefinementResult] = []
        self.trees_: list[RefinementTree | None] = []
        self.result_: SeriesResult | None = None
        self.backward_: SeriesResult | None = None
        self._structures: list[Structure] = []
        self._instruments: list[Instrument] = []
        #: every pattern on which every rung raised, populated whether
        #: ``fit`` returns normally or raises (see ``ON_ERROR_POLICIES``) —
        #: read this after catching an exception from ``fit()`` under
        #: ``on_error="raise"``, or from a chain that fitted nothing.
        self.failures_: list[SeriesFailure] = []

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
            constrain: Callable[[int, Refinement], None] | None = None,
            on_result: Callable[[int, RefinementResult], None] | None = None,
            on_error: Literal["raise", "skip", "carry"] = "carry",
            events=None, cancel=None, progress=None, telemetry=None,
            label: str | None = None,
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
            when it turns out not to be a good one either and the pattern's Rwp
            jumps past the chain's median, the reseed fence escalates one rung
            at a time (:func:`_ladder`), re-walking the staged plan from the
            warm state before giving the warm state up.  ``refit`` therefore
            sets the ladder's *first* rung, not the only plan a pattern can be
            fitted with.  **A collapse every pattern shares is not caught**,
            since the median rises with it: under a plan freeing U, V and W the
            round-robin chain sat 1.04-1.29× above ``"stages"`` with no reseed,
            and what named it was ``SEQUENTIAL_PERSISTENT_FINDING`` on
            ``RESOLUTION_UNCONSTRAINED`` for U, V and W (issue #475, WP-1469).
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
        constrain:
            ``(index, ref) -> None``, called on each pattern's
            :class:`~rietx.refine.Refinement` once it is built and warmed,
            just before its fit.  Where a user constraint is declared
            (WP-1441, issue #376)::

                def constrain(index, ref):
                    ref.add_variable("B_site", 0.5, min=0.0, max=5.0)
                    ref.tie_equal(["phases.0.atoms.0.biso",
                                   "phases.0.atoms.1.biso"],
                                  source="vars.B_site")
                    ref.hold("phases.0.cell.*")   # WP-1435, the third

                series.fit(patterns, plan=plan, constrain=constrain)

            A tie, a named variable and a **hold** are the three facts of a
            refinement that live in no model — ``Refinement._ties``,
            ``._variables`` and ``._user_holds`` are the one authority for
            each — so `carry`, which moves values between
            ``Structure``/``Instrument`` pairs, cannot reach any of them, and
            `prepare` runs one line before the ``Refinement`` exists.  Without
            this hook there is no object to declare a constraint on for any
            pattern after the first.

            It is a hook rather than a list of ties because a tie is a verb
            call against a live :class:`~rietx.params.vector.ParameterTable`:
            :meth:`~rietx.refine.Refinement.tie_equal` resolves its globs there
            and nominates the first match in table order as the source.  Each
            pattern has its own table, so re-declaring against it is the only
            spelling that means the same thing on every pattern.

            Every rung of the ladder is a fresh ``Refinement`` and gets the
            hook, as does the cold refit `verify_discontinuities` runs — a
            verification fit that dropped the constraint would not be
            comparing like with like.  The hook is the caller's code and runs
            outside every guard, so a raise in it ends the series, the way a
            raise in `prepare` does.

            A variable's **value** is carried between patterns like any other
            parameter, under the same `carry` globs — ``vars.B_site`` is an
            ordinary dot-path — so a variable declared here warm-starts from
            the last accepted pattern rather than from its declaration.
        on_error:
            What a pattern on which every rung of the ladder raised does to
            the rest of the chain — see :data:`ON_ERROR_POLICIES`.  A rung that
            raises escalates like a diverged one first, so this is consulted
            only once the cold rung has raised too.  The default ``"carry"``
            records the pattern on ``SeriesResult.failures`` (and this
            instance's ``.failures_``) with ``SERIES_PATTERN_FAILED`` and
            warm-starts its successor from the last accepted pattern;
            ``"skip"`` starts the successor cold; ``"raise"`` ends the chain in
            the exception, keeping what completed on ``.results_``/``.trees_``
            and on the exception.  A chain that fitted no pattern at all raises
            whichever is chosen.  The caller's own ``prepare``/``constrain``
            are never guarded: a raise there is the caller's and ends the
            series as itself.
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
        label:
            What the *job* is called (WP-1431).  A series is one run directory
            however many patterns it walks, so this names the chain — the ramp,
            the tray, the sweep — and never a pattern.  A pattern is named by
            ``labels`` above, and ``rietx watch`` prefers that in a row, so the
            job's name is what the row's tooltip and the strip's label slot
            carry.  One letter apart and not interchangeable: passing a
            sequence here raises rather than writing a record that reads back
            as unnamed.
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
        if on_error not in ON_ERROR_POLICIES:
            raise ValueError(f"on_error must be one of {ON_ERROR_POLICIES}")
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
        # **At this level, once.**  A 60-pattern series runs 60 fits, and each
        # gets a fresh ``_SeriesStream`` wrapper — so a recorder attached per
        # fit would make 60 run directories for one job.  ``runs.attach`` looks
        # for its stamp through the ``_inner`` chain, which is what makes every
        # fit below this one decline.
        # ``label`` names the *job* — one series is one run directory, so the
        # name is the chain's, never a pattern's.  A member is named by
        # ``series_label``, which the page prefers over this in a row.
        recorder = runs.attach(stream, events, telemetry=telemetry, label=label)
        if recorder is not None and stream is None:
            stream = recorder
        # The chain's own token, not only each pattern's (WP-1405): ``_run``
        # reads ``bool(cancel)`` to decide the walk ended, so a stop that
        # reached one pattern's ``fit`` and not this variable would abandon that
        # pattern and start the next one.
        # ``recorder_of`` and not ``recorder``, for ``fit``'s reason: ``attach``
        # answers ``None`` when the caller's stream already carries one, and
        # the chain would then never compose a token at all — with ``cancel``
        # unpassed that leaves ``bool(cancel)`` false for the whole walk, which
        # is exactly the failure this line exists to prevent.
        cancel = runs.attach_cancel(runs.recorder_of(stream), cancel)
        try:
            return self._run(
                patterns, names, xs, order, mode, base_plan, ladder,
                two_theta_limits, reseed, reseed_factor, prepare, constrain,
                on_result, stream, cancel, direction, x_label,
                first_rung_factor, verify_discontinuities, recorder, on_error)
        except BaseException:
            if recorder is not None:
                recorder.close("failed")
            raise
        finally:
            if recorder is not None:
                recorder.close()

    def _run(self, patterns, names, xs, order, mode, base_plan, ladder,
             two_theta_limits, reseed, reseed_factor, prepare, constrain,
             on_result, stream, cancel, direction, x_label, first_rung_factor,
             verify_discontinuities, recorder, on_error: str = "raise"):
        """The chain, split out of :meth:`fit` so the recorder has one exit.

        Exactly :meth:`fit`'s body from the first ``_chain`` call onwards, moved
        rather than changed: the recorder's lifetime is a ``try/finally`` beside
        the run, and wrapping the body in place would have re-indented all of it
        for nothing.
        """
        # this run's, or nothing: a chain that raises must not leave a previous
        # fit's answer beside its own partial ``results_``
        self.result_ = None
        self.backward_ = None
        entries, results, trees, models, failures, _, floored = self._chain(
            order, patterns, names, xs, mode, base_plan, ladder,
            two_theta_limits, reseed, reseed_factor, prepare, constrain,
            on_result, stream=stream, cancel=cancel,
            pass_name="backward" if direction == "backward" else "forward",
            first_rung_factor=first_rung_factor, on_error=on_error)
        # The reported chain is final here, so it is published *before* any
        # pass that starts new fits — the discontinuity verification and the
        # backward chain — since nothing either does can take it.  Issue
        # #224's series C is the case — all 125 forward patterns in hand, and
        # a raise in the backward pass that, under on_error="raise",
        # overwrote these attributes with the backward chain's partial state.
        self.results_ = results
        self.trees_ = trees
        self._structures = [s for s, _ in models]
        self._instruments = [i for _, i in models]
        self.failures_ = failures

        before = _inside_before(entries, direction)
        diagnostics = [d for e in entries
                       for d in (_reseed_diagnostics(e) + _unrecovered_diagnostics(e)
                                 + _rwp_outlier_diagnostics(e, before.get(e.index)))]
        diagnostics += [_series_pattern_failed_diagnostic(f) for f in failures]
        cancelled = cancel is not None and bool(cancel)
        if cancelled:
            diagnostics.append(_cancelled_diagnostic(len(entries), len(patterns)))
        series = SeriesResult(
            mode=mode, entries=entries, x_label=x_label,
            direction=direction,  # type: ignore[arg-type]
            failures=failures, n_failed=len(failures),
            provenance=Provenance(package_version=_VERSION, created_utc=_utcnow(),
                                  backend=self._backend, solver=self._solver,
                                  dtype=backend_dtype_note(self._backend),
                                  report_thresholds_version=THRESHOLDS_VERSION))
        relative = _relative_paths(self.structure, self.instrument)
        angles = _angle_paths(self.structure, self.instrument)
        steps = _discontinuity_steps(series, relative, angles)
        diagnostics += [s.diagnostic for s in steps]
        series.discontinuities = [s.record for s in steps]
        # WP-1305 (c): the check the diagnostic asks the reader for, run here.
        # A cancelled chain gets none — it starts new fits, and a chain that
        # stopped early is not the trajectory the steps were measured on.
        if verify_discontinuities and steps and not cancelled:
            self._verify_discontinuities(
                steps, patterns, names, mode, base_plan, two_theta_limits,
                prepare, constrain, stream=stream, cancel=cancel)
        # what the per-pattern diagnostics could not say: "42 of 68" (WP-1110)
        diagnostics += _persistent_diagnostics(series)
        # and a width that grew while the fit got worse (WP-1465)
        diagnostics += _width_growth_diagnostics(series)
        # the moment along the chain: the hold, and the onset it locates.
        # Empty on any series whose entries carry no moment row at all, which
        # is every non-magnetic one (WP-1329).
        diagnostics += _moment_diagnostics(series, floored)

        if direction == "both" and cancelled:
            # a cancelled forward chain gets no verification pass: the
            # comparison is between two *complete* chains, and half of one says
            # nothing — and the result says it did not run, because zero
            # SEQUENTIAL_PATH_DEPENDENT findings is also what a clean series
            # reports (WP-1333)
            diagnostics.append(_path_check_not_run(
                f"the forward chain was cancelled after {len(entries)} of "
                f"{len(patterns)} patterns, so the backward chain was never "
                "started"))
        elif direction == "both":
            try:
                (back_entries, _, _, _, back_failures, back_stop,
                 back_floored) = self._chain(
                    list(reversed(order)), patterns, names, xs, mode, base_plan,
                    ladder, two_theta_limits, reseed, reseed_factor, prepare,
                    constrain, None, history_suffix=".backward",
                    stream=stream, cancel=cancel,
                    pass_name="backward", first_rung_factor=first_rung_factor,
                    on_error=on_error, publish=False)
            except Exception as exc:
                # on_error="raise", or a caller's hook: the verification pass
                # died, and the complete forward chain goes out with the
                # exception rather than being lost to it
                failed = getattr(exc, "series_failed", None)
                where = ("" if failed is None else
                         f" on pattern {failed.index} ({failed.label})")
                diagnostics.append(_path_check_not_run(
                    f"the backward chain raised {exc!r}{where}"))
                series.diagnostics = diagnostics
                self.result_ = series
                exc.series_result = series
                exc.series_results = self.results_
                exc.series_failures = self.failures_
                raise
            back = SeriesResult(mode=mode, entries=back_entries, x_label=x_label,
                                direction="backward", failures=back_failures,
                                n_failed=len(back_failures))
            diagnostics += [_series_pattern_failed_diagnostic(f, pass_name="backward")
                            for f in back_failures]
            back.diagnostics = _moment_diagnostics(back, back_floored)
            if cancel is not None and bool(cancel):
                diagnostics.append(
                    _cancelled_diagnostic(len(back_entries), len(patterns),
                                          pass_name="backward"))
                in_flight = ("" if back_stop is None else
                             f", in flight on pattern {back_stop} "
                             f"({names[back_stop]})")
                diagnostics.append(_path_check_not_run(
                    f"the backward chain was cancelled after "
                    f"{len(back_entries)} of {len(patterns)} patterns"
                    f"{in_flight}"))
            else:
                diagnostics += _path_dependence_diagnostics(series, back, relative,
                                                            angles)
                # the onset in *each direction of the chain*, compared: the one
                # reading a single pass cannot produce (WP-1329)
                diagnostics = _with_onset_agreement(diagnostics, series, back)
            self.backward_ = back
            # …and on the result, so `refine_sequential` — the one-shot API the
            # manual recommends — hands back the trajectory its
            # SEQUENTIAL_PATH_DEPENDENT diagnostics are about (WP-1076)
            series.backward = back

        series.diagnostics = diagnostics
        self.result_ = series
        if recorder is not None:
            # a series has no single ``RefinementResult``; its termination view
            # is the ``SeriesResult``, and ``str`` of it is the same projection
            # rule ``fit`` follows — never ``summary()``, which builds reports
            recorder.write_summary(series)
        return series

    # ------------------------------------------------------------------
    def _chain(self, order, patterns, names, xs, mode, base_plan, ladder,
               two_theta_limits, reseed, reseed_factor, prepare, constrain,
               on_result, history_suffix: str = "",
               stream: EventStream | None = None,
               cancel=None, pass_name: str = "forward",
               first_rung_factor: float | None = None,
               on_error: str = "raise", publish: bool = True):
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

        A rung whose fit raises anything else is a rung that **lost**, and the
        ladder escalates past it as past a diverged one (WP-1333): its
        ``repr`` lands on ``SeriesEntry.rungs_raised``, and the pattern is kept
        if any later rung returns.  Only a pattern on which **every** rung
        raised is a failure, and what the chain does then is ``on_error``'s
        to decide (:data:`ON_ERROR_POLICIES`).  Under ``"raise"`` the last
        rung's exception is re-raised carrying ``series_failed`` (its
        :class:`SeriesFailure`); with ``publish`` — the reported chain, never
        the backward verification pass — the partial ``results``/``trees``/
        ``models``/``failures`` are also written straight onto ``self``, the
        same attributes :meth:`_run` would otherwise set on a normal return,
        because a caller catching the exception has no other way to reach
        what already converged.

        Returns entries, results, trees, models and failures in series order,
        ``stopped_at``: the series index of the pattern in flight when a
        cancel ended the walk, ``None`` when it ran to the end; and the floored
        carries, ``{label: [modulus path, …]}`` for every pattern whose warm
        start received a moment at its floor (WP-1329's hold).
        """
        entries: dict[int, SeriesEntry] = {}
        results: dict[int, RefinementResult] = {}
        trees: dict[int, RefinementTree | None] = {}
        models: dict[int, tuple[Structure, Instrument]] = {}
        failures: dict[int, SeriesFailure] = {}
        #: pattern index → modulus paths whose warm start **this** pattern
        #: received at the floor rather than at its predecessor's unsupported
        #: value (WP-1329's hold).  Keyed by the pattern that was reseeded,
        #: because that is the pattern whose starting point a reader is being
        #: told about; ``pending_floor`` carries it one step through the walk,
        #: so a quarantined pattern in between cannot make it look as though
        #: the reseed came from its neighbour.
        floored: dict[int, list[str]] = {}
        pending_floor: list[str] = []
        previous: tuple[Structure, Instrument] | None = None
        previous_hkl: list = []
        #: the last accepted pattern's named-variable values, by bare name.
        #: Beside ``previous_hkl`` and for its reason: a variable lives outside
        #: the models, so ``_carry_into`` — which reads a ``ParameterTable``
        #: built from a fitted ``Structure``/``Instrument`` pair — cannot see
        #: one, and ``carry``'s default ``["*"]`` would be a claim nothing kept
        #: (WP-1441).
        previous_vars: dict[str, float] = {}
        previous_tag: tuple[str | None, str | None] = (None, None)
        accepted_rwp: list[float] = []
        # WP-1127's sample: what every first rung that was *kept without
        # escalating* cost.  Read only by _first_rung_budget, and it stays
        # empty when no factor was asked for.
        accepted_first: list[int] = []
        #: the series index of the pattern in flight when a cancel ended the
        #: walk, ``None`` when it ran to the end — what
        #: ``SEQUENTIAL_PATH_CHECK_INCOMPLETE`` names as "the pattern it died on"
        stopped_at: int | None = None
        #: the last exception a failed pattern raised, for the one case a
        #: non-raising policy still raises: a chain that fitted nothing
        chain_raise: Exception | None = None

        n = len(patterns)
        for position, k in enumerate(order):
            data = patterns[k]
            warm = previous is not None
            if warm and pending_floor:
                floored[k] = list(pending_floor)
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
            rwp_of: dict[str, float] = {}
            #: every rung that raised rather than returned, with ``repr(exc)``
            #: — the ladder's member for "this rung raised" (WP-1333)
            raised: dict[str, str] = {}
            last_raise: Exception | None = None
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
                if tried:
                    if best is None:
                        # every rung so far raised, so there is nothing to
                        # keep and the next rung is the only move — declined,
                        # like any escalation, when the caller asked for none
                        if not reseed:
                            break
                    elif not forced and not (reseed and _reseed_needed(
                            best, accepted_rwp, reseed_factor)):
                        break
                if not tried and budget is not None:
                    rung_plan = _bounded_plan(rung_plan, budget)
                try:
                    ref, result = self._fit_one(
                        data, names[k], previous if rung_warm else None,
                        previous_hkl if rung_warm else [], rung_plan, mode,
                        two_theta_limits, position, previous_tag, prepare,
                        constrain, k,
                        history_suffix + ("" if not tried else f".{rung}"),
                        previous_vars=previous_vars if rung_warm else {},
                        stream=stream, cancel=cancel,
                        stamp={**stamp,
                               **_rung_stamp(rung, escalation=bool(tried))})
                except RefinementCancelled:
                    cancelled = True
                    break
                except _PatternRaised as exc:
                    # A rung that raised is a rung that **lost** (WP-1333):
                    # the ladder escalates past it exactly as past a
                    # diverged one.  The case that forced this is issue
                    # #224's — a neighbour that *converged* with a runaway
                    # cell, so every warm rung inherits the cell and the
                    # enumerator refuses it at compile, while the cold rung
                    # starts from the initial models and never sees it.
                    # Abandoning every rung together (PR #386) turned one
                    # bad neighbour into a failure of every successor.
                    tried.append(rung)
                    raised[rung] = repr(exc.original)
                    last_raise = exc.original
                    continue
                spent = sum(s.n_iterations for s in result.stages)
                truncated = (not tried and budget is not None
                             and result.status == "max_iter")
                bound_hit = bound_hit or truncated
                tried.append(rung)
                rwp_of[rung] = result.statistics.rwp
                rung_nfev.append(spent)
                iterations += spent
                if _prefer(result, truncated, best, best_truncated):
                    best, best_ref, best_rung = result, ref, rung
                    best_truncated = truncated

            if best is None and raised and not cancelled:
                # Every rung the chain tried raised: the pattern never returned
                # a fit at all — a different failure from "diverged", which is
                # a *result*, handled by the quarantine below with no policy.
                failure = SeriesFailure(index=k, label=names[k],
                                        exception=raised[tried[-1]])
                if on_error == "raise":
                    last_raise.series_failed = failure
                    if publish:
                        keys = sorted(entries)
                        # Written directly onto ``self`` — the same attributes
                        # ``_run`` sets on a normal return — because this
                        # method is about to raise rather than return, and a
                        # caller catching the exception has no other way to
                        # reach what already converged.
                        self.results_ = [results[i] for i in keys]
                        self.trees_ = [trees[i] for i in keys]
                        self._structures = [models[i][0] for i in keys]
                        self._instruments = [models[i][1] for i in keys]
                        self.failures_ = list(failures.values()) + [failure]
                        last_raise.series_results = self.results_
                        last_raise.series_failures = self.failures_
                    raise last_raise
                failures[k] = failure
                chain_raise = last_raise
                if on_error == "skip":
                    # No warm start at all for the next pattern: a fit that
                    # never returned is not evidence the *next* one's warm
                    # state is trustworthy either.
                    previous = None
                    previous_hkl = []
                    previous_tag = (None, None)
                    # and no floored moment either: the next pattern is cold
                    pending_floor = []
                # "carry" leaves ``previous``/``previous_hkl``/``previous_tag``
                # exactly as they were — the next pattern warm-starts from the
                # last good state, precisely the WP-1051 quarantine's own
                # treatment of a diverged fit.  The cold rung has already
                # raised on this pattern, so the state it would carry past is
                # not what failed.
                continue

            if best is None:      # cancelled on the first attempt: no half-fits
                stopped_at = k
                break
            entry = _entry_from_result(k, names[k], xs[k], best)
            # WP-1329: the moment arm, per pattern, from the fit that produced
            # the values — the one place the compiled model and the fitted
            # state are both in hand.  Empty and free on a non-magnetic chain.
            entry.magnetic = _moment_evidence(best_ref, best)
            # every rung that returned is charged to the pattern, not only the
            # one kept; a rung that raised reports no count to charge
            entry.n_iterations = iterations
            entry.rung = best_rung
            entry.rungs_tried = list(tried)
            entry.rungs_raised = dict(raised)
            if len(tried) > 1:
                entry.rwp_warm = rwp_of.get(tried[0])
                # only the *cold* rung breaks the chain — a staged refit from
                # the warm state still started at the neighbour's answer
                entry.reseeded = best_rung == "cold"
            # the limit this pattern was judged against, so the verdict on the
            # kept attempt is readable off the entry (WP-1469)
            entry.rwp_fence = _rwp_fence(accepted_rwp, reseed_factor)

            entries[k] = entry
            results[k] = best
            trees[k] = best_ref.history
            models[k] = (best_ref.fitted_structure, best_ref.fitted_instrument)
            # Quarantine (WP-1051): a fit that stayed diverged is reported —
            # the pattern was measured — but it is neither a starting point nor
            # a scale, so the chain steps over it.  Its successor warm-starts
            # from the last accepted pattern and the median that decides every
            # later trigger never sees it.
            # A pattern above the fence is *not* quarantined (WP-1469): the
            # fence cannot tell a blank frame from a lasting change, and
            # quarantine is the wrong answer for the second.  Measured on a
            # 24-pattern ramp whose counts fall 4× at pattern 6, the model
            # right: quarantined, the median never follows the drop, and every
            # later pattern climbs the ladder (+55 % iterations) and is flagged
            # (18 of 18, not 7); an unmodelled phase from pattern 6, +107 %.
            # What quarantine buys on #481's blank is 2-8 % of the chain, the
            # values identical to the digit either way.
            if entry.status != "diverged":
                # WP-1329's hold along the series: a modulus this pattern did
                # not support is reseeded to its floor before it becomes the
                # next pattern's starting point.  ``models[k]`` — what the
                # caller reads back as ``fitted_structures()`` — keeps the
                # fitted value; only the *carry source* is floored, and on a
                # chain with no unsupported moment it is the same object.
                carried, pending_floor = _floor_unsupported_moments(
                    models[k][0], entry.magnetic)
                previous = (carried, models[k][1])
                previous_hkl = _extract_reflections(best_ref._model)
                previous_vars = {name: prm.value
                                 for name, prm in best_ref._variables.items()}
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
                stopped_at = k
                break

        if (publish and not entries and failures and stopped_at is None
                and chain_raise is not None):
            # A series that measured nothing has no answer to return: the
            # empty SeriesResult a policy would hand back reads as a short
            # series, and "a failure raises" is the contract (ON_ERROR_POLICIES).
            self.results_, self.trees_ = [], []
            self._structures, self._instruments = [], []
            self.failures_ = [failures[i] for i in sorted(failures)]
            chain_raise.series_results = self.results_
            chain_raise.series_failures = self.failures_
            raise chain_raise

        keys = sorted(entries)
        return ([entries[k] for k in keys], [results[k] for k in keys],
                [trees[k] for k in keys], [models[k] for k in keys],
                [failures[k] for k in sorted(failures)], stopped_at,
                {names[k]: v for k, v in floored.items()})

    def _fit_one(self, data: PatternData, label: str,
                 previous: tuple[Structure, Instrument] | None,
                 previous_hkl: list[ReflectionState],
                 plan: RefinementPlan, mode: Mode, two_theta_limits,
                 position: int, previous_tag: tuple[str | None, str | None],
                 prepare, constrain, index: int, history_suffix: str = "", *,
                 previous_vars: dict[str, float] | None = None,
                 stream: EventStream | None = None,
                 stamp: dict | None = None, cancel=None):
        """One pattern: warm the models from ``previous``, then run ``plan``."""
        structure = self.structure.model_copy(deep=True)
        instrument = self.instrument.model_copy(deep=True)
        displaced: list[str] = []
        if previous is not None:
            displaced = _carry_into(structure, instrument, previous, self.carry)
        if prepare is not None:
            prepare(index, data, structure, instrument)
        with _refined_state():
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
        if previous_hkl and mode in ("lebail", "pawley") and self.carry_hkl_intensities:
            # Le Bail/Pawley per-hkl intensities are path-dependent state that
            # lives *outside* θ, so `_carry_into` cannot reach them — and a flat
            # re-seed would throw away everything the previous pattern learned,
            # which for an extraction is most of what there is to learn.  This
            # is the same channel a checkout uses to restore a node's
            # ReflectionState, matched by hkl at the first stage's compile.
            ref._pending_reflections = [r.model_copy(deep=True)
                                        for r in previous_hkl]
        if constrain is not None:
            constrain(index, ref)
            if previous is not None:
                _reanchor_carried(ref, displaced, previous, previous_vars or {})
        _carry_variables(ref, previous_vars or {}, self.carry)
        try:
            result = ref.fit(data, mode=mode, plan=plan,
                             two_theta_limits=two_theta_limits,
                             events=(None if stream is None
                                     else _SeriesStream(stream, **(stamp or {}))),
                             cancel=cancel)
        except RefinementCancelled:
            raise
        except Exception as exc:
            # the fit is the rung; everything above this line is the caller's
            # and propagates as itself (see _PatternRaised)
            raise _PatternRaised(exc) from exc
        _link_history(ref, position, label, previous_tag)
        return ref, result

    def _verify_discontinuities(self, steps: list[_FlaggedStep], patterns,
                                names, mode, base_plan, two_theta_limits,
                                prepare, constrain, *,
                                stream: EventStream | None = None,
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

        ``prepare`` and ``constrain`` are threaded through for the same reason
        the plan and the models are: a cold refit that dropped the caller's own
        constraints would be a different model, and the ratio it reports
        compares the step against a fit nobody asked for.

        ``cancel`` is the chain's own token, threaded through because these are
        ordinary fits and up to ``2s`` of them: a caller who can stop the walk
        must be able to stop the check.  A cancel here leaves every diagnostic
        it had not reached exactly as the walk wrote it — ``value`` absent, the
        absent-for-cause state — so a stopped check reports nothing about a
        step rather than a half-measured something.
        """
        cold: dict[int, RefinementResult | _PatternRaised] = {}

        def refit(k: int) -> RefinementResult:
            if k not in cold:
                try:
                    _ref, cold[k] = self._fit_one(
                        patterns[k], names[k], None, [], base_plan, mode,
                        two_theta_limits, k, (None, None), prepare, constrain,
                        k, ".verify", stream=stream, cancel=cancel,
                        stamp={"series_index": k, "series_label": names[k],
                               "series_n": len(patterns),
                               "series_pass": "verify"})
                except _PatternRaised as exc:
                    cold[k] = exc      # once per pattern, like a result
            if isinstance(cold[k], _PatternRaised):
                raise cold[k]
            return cold[k]

        angles = _angle_paths(self.structure, self.instrument)
        for s in steps:
            if cancel is not None and bool(cancel):
                return
            # the record's own pair, by SeriesEntry.index — the position in
            # ``patterns`` — rather than looked up again from its labels
            (a, b), path, d = s.record.indices, s.record.path, s.diagnostic
            try:
                va = _value_of(refit(a), path)
                vb = _value_of(refit(b), path)
            except RefinementCancelled:
                return
            except _PatternRaised as exc:
                # A check the caller asked for is not worth the finished
                # series it is checking (WP-1333): the step stays unmeasured,
                # ``value`` absent, and the message says why.
                d.message += (f"; an independent cold refit raised "
                              f"{exc.original!r}, so the step could not be "
                              f"re-measured")
                continue
            if va is None or vb is None or not s.record.step:
                d.message += ("; an independent cold refit of both patterns "
                              "does not determine this parameter, so the step "
                              "could not be re-measured")
                continue
            # signed, both sides: a cold pair stepping as far the *other* way
            # is not a reproduction, and two magnitudes divided would call it
            # one (see SeriesStep.step)
            cold_step = vb - va
            if path in angles:
                # measured as the fence measured the step it re-measures (#604)
                cold_step = float(_angle_difference(cold_step))
            d.value = cold_step / s.record.step
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


def _rwp_fence(accepted_rwp: list[float], factor: float) -> float | None:
    """The Rwp above which the fence rejects an attempt, or ``None``.

    ``factor`` × the median of the accepted patterns: a median rather than
    the previous value so one bad pattern cannot ratchet the limit up
    (:data:`RESEED_FACTOR`).  ``None`` until one pattern has been accepted.
    """
    if not accepted_rwp:
        return None
    return factor * float(np.median(accepted_rwp))


def _reseed_needed(result: RefinementResult, accepted_rwp: list[float],
                   factor: float) -> bool:
    if result.status == "diverged":
        return True
    fence = _rwp_fence(accepted_rwp, factor)
    return fence is not None and result.statistics.rwp > fence


def _reseed_diagnostics(entry: SeriesEntry) -> list[Diagnostic]:
    if not entry.reseeded:
        return []
    warm = entry.rwp_warm
    now = entry.statistics.rwp if entry.statistics else float("nan")
    first = entry.rungs_tried[0] if entry.rungs_tried else ""
    # a warm rung that *raised* has no Rwp to quote, and the raise is the
    # better evidence anyway: it says what about the neighbour's state this
    # pattern could not use (WP-1333)
    how = (f"raised {entry.rungs_raised[first]}" if first in entry.rungs_raised
           else f"reached Rwp {warm:.4f} against {now:.4f} cold")
    # a cold rung kept only as the best of several rejected ones is not "a
    # good fit", and calling it one contradicted SEQUENTIAL_RWP_OUTLIER on the
    # same pattern — issue #481's blank frame read exactly that (WP-1469)
    # …and neither is a cold rung kept only as the least diverged of several,
    # which SEQUENTIAL_UNRECOVERED calls a failed fit on the same pattern
    if entry.status == "diverged":
        fit = ("the cold fit is kept only as the best attempt and diverged "
               "too — read SEQUENTIAL_UNRECOVERED on this pattern first — and")
    elif entry.above_fence:
        fit = ("the cold fit is kept only as the best attempt and is still "
               "above the fence — read SEQUENTIAL_RWP_OUTLIER on this pattern "
               "first — and")
    else:
        fit = "this point is a good fit but"
    return [Diagnostic(
        level="warning", code="SEQUENTIAL_RESEED",
        where=[entry.label or str(entry.index)],
        message=(f"pattern {entry.index} ({entry.label}) was refitted from the "
                 f"initial model: warm-starting from its neighbour {how}"),
        suggestion=(f"{fit} its starting values did not "
                    "come from its neighbour, so it is not evidence that the "
                    "trajectory is continuous here; check whether the specimen "
                    "or the model changed at this point of the series"),
    )]


def _inside_before(entries: Sequence[SeriesEntry],
                   direction: str) -> dict[int, SeriesEntry]:
    """For each entry above the fence, the last one before it that was inside.

    "Before" in the order the chain walked, which is what the fence's median
    was taken over.  The comparison :func:`_rwp_outlier_diagnostics` quotes,
    derived from the entries so a reloaded series says the same thing.
    """
    walk = sorted(entries, key=lambda e: e.index,
                  reverse=direction == "backward")
    out: dict[int, SeriesEntry] = {}
    last: SeriesEntry | None = None
    for e in walk:
        if e.above_fence and last is not None:
            out[e.index] = last
        elif e.status != "diverged" and not e.above_fence:
            last = e
    return out


def _rwp_outlier_diagnostics(entry: SeriesEntry,
                             before: SeriesEntry | None) -> list[Diagnostic]:
    """``SEQUENTIAL_RWP_OUTLIER``: every rung came back above the fence (WP-1469).

    The Rwp leg of the fence triggers the ladder, and until issue #481 it was
    never a verdict: the best rung was kept and said nothing, so a blank frame
    fitted to noise read as a point of the trajectory.  Derived from the entry,
    like every fence here (:attr:`SeriesEntry.above_fence`).

    **It reports and does not judge**, because Rwp cannot say why it rose.
    Rwp is GoF × Rexp near a converged fit, and the three measured causes
    split between the two: #481's blank frame had GoF 1.00 against its
    neighbour's 1.06 and Rexp 0.159 against 0.040 (background and noise
    alone, fitted perfectly); a correct model over counts that fell 4× had
    GoF 1.08 against 1.04 and Rexp twice its neighbour's, a sound
    measurement; an unmodelled phase had GoF 16.7 against 1.04.  So the
    message quotes both against ``before``, the last pattern the fence
    accepted, which is the reading that separates them, and calls the point
    neither good nor bad.
    """
    if not entry.above_fence:
        return []
    rwp, fence = entry.statistics.rwp, entry.rwp_fence
    tried = ", ".join(entry.rungs_tried) or entry.rung
    # the cold rung is always the ladder's last, so without it the ladder was
    # not climbed to the end — ``reseed=False``, or a cancel mid-ladder — and
    # "no starting point brought it near" would claim starts nobody tried
    climbed = "cold" in entry.rungs_tried or entry.rung == "cold"
    ratio = rwp / fence if fence > 0 else None
    times = (", above the fence" if ratio is None
             else f", {ratio:.2f}× the fence")
    against = ""
    if before is not None and before.statistics is not None:
        s, r = entry.statistics, before.statistics
        against = (f"; against {before.label or before.index}, the last pattern "
                   f"before it inside the fence: GoF {s.gof:.2f} to its "
                   f"{r.gof:.2f}, Rexp {s.rexp:.4f} to its {r.rexp:.4f}")
    return [Diagnostic(
        level="warning", code="SEQUENTIAL_RWP_OUTLIER",
        where=[entry.label or str(entry.index)], value=ratio,
        message=(f"pattern {entry.index} ({entry.label}) reached Rwp {rwp:.4f} "
                 f"on its best rung{times} at {fence:.4f} "
                 f"(the reseed factor × the median Rwp of the patterns accepted "
                 f"before it), after "
                 + ("every rung the chain tried" if climbed else
                    "the rungs the chain tried before stopping short of its "
                    "cold rung (reseed off, or a cancel)")
                 + f" ({tried}){against}"),
        suggestion=(("no starting point brought this fit near its neighbours', "
                     "so the pattern itself differs from them"
                     if climbed else
                     "the ladder was not climbed, so a cold start may still "
                     "bring this fit near its neighbours'; refit it with "
                     "reseed on before reading it as a difference in the "
                     "pattern")
                    + "; open its own fit "
                    "before reading its values.  GoF says which way: well above "
                    "theirs is a model the pattern has outgrown — a specimen "
                    "change the model lacks, or a bad frame; like theirs, with a "
                    "higher Rexp, is fewer counts — a short or blank frame, a "
                    "weaker beam — where the fit may be sound, so check that each "
                    "phase is still in the pattern (a scale within a few esds of "
                    "zero is one it does not contain).  The fence follows the "
                    "median of the accepted patterns, so a run of these that "
                    "stops is a lasting change the median caught up with, not "
                    "one that went away.  The steps into and out of this pattern "
                    "are left out of the discontinuity scan"),
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


def _path_check_not_run(reason: str) -> Diagnostic:
    """``SEQUENTIAL_PATH_CHECK_INCOMPLETE`` — the comparison never ran (WP-1333).

    ``direction="both"`` exists for one reading, and its absence has the same
    shape as its success: zero ``SEQUENTIAL_PATH_DEPENDENT`` findings.  Issue
    #224's series C had the forward chain whole and the backward chain dead,
    and reported exactly what a clean series reports.  So every way the
    comparison can fail to happen says so, naming the chain that stopped and
    the pattern it stopped on — a forward chain cancelled (the backward one is
    never started), a backward chain cancelled, a backward chain that raised
    under ``on_error="raise"`` — and zero findings with none of these is what
    *checked and clean* means.  ``warning``: the caller asked for this check.
    """
    return Diagnostic(
        level="warning", code="SEQUENTIAL_PATH_CHECK_INCOMPLETE", where=[],
        message=(f"the forward/backward path-dependence comparison did not "
                 f"run: {reason}"),
        suggestion=("zero SEQUENTIAL_PATH_DEPENDENT findings on this series is "
                    "not a clean bill but no reading at all: no trajectory "
                    "here has been shown independent of the order it was "
                    "refined in.  Re-run with direction='both' to completion "
                    "before quoting a trajectory's per-pattern esds as its "
                    "uncertainty"),
    )


def _path_check_coverage(missing: list[tuple[int, str, str]], n_patterns: int,
                         unjudged: list[str]) -> list[Diagnostic]:
    """``SEQUENTIAL_PATH_CHECK_INCOMPLETE`` at ``info`` — the comparison ran,
    on less than the series (WP-1333, issue #269).

    Two narrowings, each one diagnostic.  **Patterns** one chain has no entry
    for — every rung raised there under ``on_error="skip"``/``"carry"`` — are
    not compared at all.  **Paths** no pattern could judge are the #269 case:
    the comparison is per pattern and only where both chains measured an esd
    (``_path_dependence_diagnostics``' ``comparable`` mask), so a path held,
    fixed or tied to an unmeasured source throughout one direction is never
    judged, and before this said so by saying nothing, exactly as an agreed
    path does.  Only a path *some* chain measured is named: one with no esd on
    any pattern of either chain was never a measurement, and naming it would
    fire on every clean series (a tie row off a source never freed, a
    coefficient on its floor — two such on the eight-pattern LaB6 fixture).  ``info``, since a finding that did fire still stands, and a
    failed pattern already carries its own warning; what these add is the
    set a clean result is silent *about*.  The triage's field form (a list on
    ``SeriesResult`` with a per-path count) is the maintainer's to direct and
    is not this.
    """
    out: list[Diagnostic] = []
    if missing:
        named = ", ".join(f"{label} (not fitted in the {chain} chain)"
                          for _, label, chain in missing)
        n_compared = n_patterns - len({i for i, _, _ in missing})
        out.append(Diagnostic(
            level="info", code="SEQUENTIAL_PATH_CHECK_INCOMPLETE",
            where=list(dict.fromkeys(label for _, label, _ in missing)),
            value=float(n_compared),
            message=(f"the path-dependence comparison ran on {n_compared} of "
                     f"{n_patterns} patterns: {named}"),
            suggestion=("a SEQUENTIAL_PATH_DEPENDENT finding still stands, but "
                        "its absence says nothing about the patterns named "
                        "here — they were compared on no path"),
        ))
    if unjudged:
        out.append(Diagnostic(
            level="info", code="SEQUENTIAL_PATH_CHECK_INCOMPLETE",
            where=list(unjudged),
            message=(f"the path-dependence comparison could judge "
                     f"{len(unjudged)} path(s) on no pattern, because no "
                     f"pattern has an esd for it in both chains: "
                     f"{', '.join(unjudged[:6])}"
                     + (" …" if len(unjudged) > 6 else "")),
            suggestion=("silence about these paths is not agreement: a path "
                        "held, fixed or tied to an unmeasured source in either "
                        "chain cannot be compared.  Read its two trajectories "
                        "(result.trajectory(path) and "
                        "result.backward.trajectory(path)) before quoting it as "
                        "independent of the refinement order"),
        ))
    return out


def _series_pattern_failed_diagnostic(failure: "SeriesFailure", *,
                                      pass_name: str = "forward") -> Diagnostic:
    """``SERIES_PATTERN_FAILED`` — a pattern on which every rung raised.

    One per :class:`SeriesFailure`, named the same way ``_cancelled_diagnostic``
    is: without this a gap in the trajectory left by ``on_error="skip"``/
    ``"carry"`` reads as a pattern nobody asked to fit, rather than one that
    could not be.

    ``where`` is the pattern's label, the key every other per-pattern series
    diagnostic uses (``SEQUENTIAL_UNRECOVERED``, ``SEQUENTIAL_RESEED``).  It
    was ``entries[k]`` until WP-1333, and ``entries`` is positional and omits
    the failed pattern, so ``entries[k]`` was pattern k+1 or out of range.

    ``pass_name="backward"`` is the ``direction="both"`` verification chain,
    whose failures were discarded before WP-1333: its entries are not the
    reported ones, so the message says what the failure costs there — one
    fewer pattern the path-dependence comparison can judge.
    """
    if pass_name == "backward":
        consequence = ("in the backward (verification) chain and was never "
                       "fitted there; the reported forward entry stands, and "
                       "the path-dependence comparison cannot judge this "
                       "pattern")
    else:
        consequence = ("and was never fitted; it carries no entry in this "
                       "series")
    return Diagnostic(
        level="warning", code="SERIES_PATTERN_FAILED",
        where=[failure.label or str(failure.index)], value=None,
        message=(f"pattern {failure.index} ({failure.label}) raised "
                 f"{failure.exception} on every rung the chain tried "
                 f"{consequence}"),
        suggestion=("this pattern is missing from the trajectory, not a zero "
                    "or a held value on it.  Unless the series ran with "
                    "reseed=False, or this was the first pattern walked, the "
                    "ladder's last rung was already a cold fit from the "
                    "initial models, so what failed is this pattern rather "
                    "than the state its neighbour handed it: fit it on its own "
                    "and read the exception — a scan the model cannot be "
                    "compiled against, a specimen change the model lacks, or a "
                    "near-singular parameterisation at this point of the "
                    "series"),
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
    """One flagged step: its public record and the diagnostic it explains.

    The diagnostic says it in prose; ``record`` (a
    :class:`~rietx.schemas.sequential.SeriesStep`, on
    ``SeriesResult.discontinuities``) says *which two patterns* and *how big*,
    so :meth:`SequentialRefinement._verify_discontinuities` re-measures the
    same step, and the plot shades it, rather than either re-deriving which
    one was meant (the one-authority rule: the flagging code is the only place
    that knows which pair it flagged).  Until WP-1469 the pair was private
    here, and a caller found it by parsing the message (issue #481).
    """

    record: SeriesStep
    diagnostic: Diagnostic


def _relative_paths(structure: Structure, instrument: Instrument) -> frozenset[str]:
    """The paths of this model whose values are steps, not positions.

    Its displacement DOFs (:attr:`ParameterTable.anchored_dof_paths`): each is
    measured from where its fit began, which in a chain is the neighbour's
    answer (WP-1333).  A rigid body's rotation DOFs too
    (:attr:`ParameterTable.anchored_rotation_paths`, WP-1805), which a commit
    zeroes, so they read the step a fit's last stage took.  The one list every
    judgement across patterns skips — both fences here, and the GUI's
    disagreement column, which must abstain where they do.  Taken from the
    models the chain was handed, since nothing in a ``SeriesEntry`` says a
    path is relative.
    """
    table = ParameterTable(structure, instrument)
    return table.anchored_dof_paths | table.anchored_rotation_paths


def _angle_paths(structure: Structure, instrument: Instrument) -> frozenset[str]:
    """The moment angle DOFs (:attr:`ParameterTable.angle_dof_paths`).

    Their differences across fits are taken modulo a turn
    (:func:`_angle_difference`), by both fences here and by the GUI's
    disagreement column, which must measure what they measure.  Taken from
    the models the chain was handed, as :func:`_relative_paths` is.
    """
    return ParameterTable(structure, instrument).angle_dof_paths


def _angle_difference(delta: np.ndarray) -> np.ndarray:
    """A difference of two angles, in radians, moved by whole turns into (−π, π].

    Issue #604: a moment along −a refined to φ = 3.13 in one pattern and
    −3.14 in the next, and both fences read the 2π between the two numbers as
    a jump in the specimen.  The direction moved by 0.01 rad.
    """
    d = np.asarray(delta, dtype=np.float64)
    return np.pi - np.mod(np.pi - d, 2.0 * np.pi)


def _discontinuity_steps(series: SeriesResult,
                         relative: frozenset[str] = frozenset(),
                         angles: frozenset[str] = frozenset()
                         ) -> list[_FlaggedStep]:
    """Steps far larger than the same parameter's typical step in this series.

    The one authority: every caller takes the diagnostics off these (there is
    no second function returning only the diagnostics, which would be a second
    name for one fact).

    Reported, never smoothed: a jump is either the science (a transition) or a
    chain failure, and nothing here can tell them apart — so the diagnostic
    names both and the trajectory is left exactly as fitted.

    ``relative`` names the paths whose value is measured from where each fit
    began (:attr:`ParameterTable.anchored_dof_paths`), and they are not judged.
    Since WP-1333 a chain starts each pattern where its predecessor ended, so a
    coordinate DOF's trajectory is the step each pattern took rather than a
    position, and its first step (from the model, not from a neighbour) read
    as a jump on every clean series.  The coordinate rows it drives are
    absolute, carry the same esd, and are judged instead.

    ``angles`` names the moment angle DOFs (:func:`_angle_paths`), whose step
    is taken modulo a turn: the chart they are reported in has a cut, and a
    moment sitting on it steps by 2π in value while it does not move (#604).

    **A step into or out of a pattern the fence rejected is not scanned**
    (WP-1469): a ``"diverged"`` entry (``SEQUENTIAL_UNRECOVERED``) or one
    whose best rung is still above the fence (``SEQUENTIAL_RWP_OUTLIER``).
    Each already has its own code naming the pattern, and a step against it
    cannot be read apart from that code.  Scanned, it took the path's one
    flag: on issue #481's ramp a blank frame's cell, fitted to noise, stepped
    33× the median, the verification confirmed it at 1.00 because both cold
    fits reproduce the same noise, and the planted step behind it went
    unreported.  The steps are dropped, **never bridged**: a bridge over a run
    of such patterns spans that many of the series' steps and reads as one
    step of that many medians — a clean ramp flagged "8×" across seven
    patterns whose counts had fallen (measured).
    """
    if len(series) < MIN_POINTS_FOR_DISCONTINUITY:
        return []
    rejected = {i for i, e in enumerate(series.entries)
                if e.status == "diverged" or e.above_fence}
    out: list[_FlaggedStep] = []
    for path in series.paths(varied_only=False):
        if path in relative:
            continue
        traj = series.trajectory(path)
        kept = [pos not in rejected for pos in traj.positions]
        if sum(kept) < MIN_POINTS_FOR_DISCONTINUITY:
            continue
        xv, value, sd = traj.arrays()
        signed = np.diff(value)
        if path in angles:
            signed = _angle_difference(signed)
        step = np.abs(signed)
        judged = np.asarray(kept[:-1]) & np.asarray(kept[1:])
        if not judged.any():
            continue
        scale = float(np.median(step[judged]))
        if not np.isfinite(scale) or scale <= _noise_floor(value[kept]):
            continue
        combined = np.sqrt(np.nan_to_num(sd[:-1]) ** 2 + np.nan_to_num(sd[1:]) ** 2)
        big = judged & (step > DISCONTINUITY_FACTOR * scale) & (
            step > DISCONTINUITY_SIGMA * combined)
        if not big.any():
            continue
        # ``where``, never ``step * big``: a rejected pattern's value may be
        # non-finite, and NaN × False is NaN, which argmax would pick
        k = int(np.argmax(np.where(big, step, -np.inf)))
        pair = (series.entries[traj.positions[k]],
                series.entries[traj.positions[k + 1]])
        out.append(_FlaggedStep(
            record=SeriesStep(
                path=path, labels=(traj.labels[k], traj.labels[k + 1]),
                indices=(pair[0].index, pair[1].index),
                step=float(signed[k])),
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
    aggregates whatever fired, and needs no edit when a new one lands, with one
    declared exception: a code about how a pattern was measured rather than
    about the model (:data:`NOT_A_SERIES_FINDING`) is never aggregated.
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
            if d.code in NOT_A_SERIES_FINDING:
                continue
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


def _width_growth_diagnostics(series: SeriesResult) -> list[Diagnostic]:
    """``SEQUENTIAL_WIDTH_GROWTH``: a phase width that grew while the fit got
    worse (WP-1465, issue #451).

    A phase broadened past what the specimen does turns into something else.
    It becomes a second background, or it stands in for a phase the model
    lacks, and a series is where that happens: the model was right on the
    first patterns and stopped being right.  Each fit still converges, no
    per-pattern code fires until ``STRAIN_UNUSUALLY_LARGE`` trips at 1.5°, and
    a projection of the width onto the background block cannot see it either
    (0.049 clean against 0.053 at a 15× soak, WP-1465 Finding 1).  What sees
    it is the trajectory, which only the series has.

    **A conjunction at one pattern.**  Against the first pattern that measured
    the width, a later pattern must carry the width at
    :data:`WIDTH_GROWTH_FACTOR` × or more, grown by more than
    :data:`WIDTH_GROWTH_SIGMA` combined esds, **and** a GoF at
    :data:`WIDTH_GROWTH_GOF_FACTOR` × or more.  The width may legitimately
    grow (a coarsening specimen, strain building up); what separates that
    from a soak is whether the model keeps up with the data, which is the
    GoF.  So the finding reports and never judges, and its suggestion points
    at the skill's "microstrain evolves" rule rather than past it.

    One finding per trajectory, at its onset, the first pattern where the
    conjunction holds; the message carries the largest ratio after it.  Widths
    tied to one another (``tie_equal("phases.*.lor_strain")``) are one column
    with one trajectory, so they share a finding whose ``where`` lists every
    path, rather than one finding each about the same fact.  Grouped on the
    trajectory itself, since a width driven by a ``vars.`` name is not
    ``vary`` and ``paths(varied_only=True)`` would lose it.
    Quarantined (``"diverged"``) entries are skipped, as they are by every
    other fence here.  An entry above the Rwp fence (``SEQUENTIAL_RWP_OUTLIER``)
    is **read**, although the discontinuity scan leaves it out: a phase
    standing in for a missing one is what lifts a pattern over that fence, and
    every soaked pattern of the fixture in ``tests/test_sequential.py`` is
    above it (WP-1469), so skipping them would leave the finding nothing to
    fire on.  A width no pattern measured has no reference and is not judged.
    """
    out: list[Diagnostic] = []
    by_trajectory: dict[tuple, Diagnostic] = {}
    entries = series.entries
    for path in series.paths():
        if not path.startswith("phases."):
            continue
        suffix = next((s for s in _WIDTH_SUFFIXES if path.endswith(s)), None)
        if suffix is None:
            continue
        variance = _WIDTH_SUFFIXES[suffix]
        traj = series.trajectory(path)
        _, value, sd = traj.arrays()
        points = [(k, pos) for k, pos in enumerate(traj.positions)
                  if entries[pos].status != "diverged"
                  and entries[pos].statistics is not None
                  and np.isfinite(value[k])]
        ref = next(((k, pos) for k, pos in points
                    if np.isfinite(sd[k]) and sd[k] > 0
                    and value[k] > WIDTH_GROWTH_SIGMA * sd[k]), None)
        if ref is None:
            continue
        k0, p0 = ref
        w0 = float(np.sqrt(value[k0]) if variance else value[k0])
        gof0 = entries[p0].statistics.gof
        if not (w0 > 0 and gof0 > 0):
            continue

        def width(k, variance=variance):
            return float(np.sqrt(max(value[k], 0.0)) if variance else value[k])

        flagged: list[tuple[int, int, float]] = []
        for k, pos in points:
            if pos <= p0 or not np.isfinite(sd[k]):
                continue
            ratio = width(k) / w0
            grown = value[k] - value[k0]
            combined = float(np.hypot(sd[k], sd[k0]))
            if (ratio >= WIDTH_GROWTH_FACTOR
                    and grown > WIDTH_GROWTH_SIGMA * combined
                    and entries[pos].statistics.gof
                    >= WIDTH_GROWTH_GOF_FACTOR * gof0):
                flagged.append((k, pos, ratio))
        if not flagged:
            continue
        key = (suffix, tuple(traj.positions), tuple(value.tolist()))
        if key in by_trajectory:
            by_trajectory[key].where.append(path)
            continue
        k1, p1, ratio1 = flagged[0]
        kmax, _, ratio_max = max(flagged, key=lambda f: f[2])
        # the patterns the conjunction could be tested on: one without an esd
        # is skipped by the loop above, so it cannot count against it here
        later = sum(1 for k, pos in points if pos > p1 and np.isfinite(sd[k]))
        s0, s1 = entries[p0].statistics, entries[p1].statistics
        as_width = " (as a width, the square root of the variance)" if variance else ""
        peak = ("" if kmax == k1 else
                f", reaching {ratio_max:.1f}× at {traj.labels[kmax]}")
        by_trajectory[key] = finding = Diagnostic(
            level="warning", code="SEQUENTIAL_WIDTH_GROWTH", where=[path],
            value=ratio1,
            message=(f"{path} grew {ratio1:.1f}×{as_width} from "
                     f"{traj.labels[k0]} to {traj.labels[k1]} "
                     f"({value[k0]:.4g} → {value[k1]:.4g}) while GoF rose "
                     f"{s1.gof / s0.gof:.1f}× (Rwp {s0.rwp:.2%} → "
                     f"{s1.rwp:.2%}); it passes both thresholds on "
                     f"{len(flagged) - 1} of the {later} patterns after "
                     f"it{peak}"),
            suggestion=("a phase width that grows while the fit gets worse is "
                        "usually the phase standing in for something the "
                        "model lacks — a second phase, a diffuse signal, or "
                        "background the function cannot follow — rather "
                        "than broadening that was measured. Fit the pattern "
                        "at the onset with the missing component before "
                        "reading this width, or this phase's scale and cell, "
                        "as physics. A width may grow for real; if the model "
                        "had kept up, GoF would not have risen with it"),
        )
        out.append(finding)
    return out


def _moment_diagnostics(series: SeriesResult,
                        floored: dict[str, list[str]]) -> list[Diagnostic]:
    """``SEQUENTIAL_MOMENT_HOLD`` and ``SEQUENTIAL_MOMENT_ONSET``, per site.

    Both read the per-pattern verdicts on
    :attr:`~rietx.schemas.sequential.SeriesEntry.magnetic` and nothing else.
    That is the WP-1329 rule and the reason it exists: the |m| column of a
    warm-started chain is smooth by construction, since each pattern starts
    from its neighbour's modulus, so a threshold on the values would locate the
    onset wherever the chain happened to relax and a threshold on the verdicts
    locates it where the data stops carrying a moment.

    Empty for every series whose entries carry no moment row — which is every
    non-magnetic one, and is absence for cause rather than "no moment found".
    """
    from .report.schemas import MOMENT_SUPPORT_SIGMA

    out: list[Diagnostic] = []
    for site in series.magnetic_sites():
        traj = series.magnetic_trajectory(site)
        n = len(traj.supported)
        if n == 0:                               # pragma: no cover - shape
            continue
        measured = traj.measured or [True] * n
        n_held = sum(1 for s, m in zip(traj.supported, measured, strict=True)
                     if m and not s)
        blind = [lab for lab, m in zip(traj.labels, measured, strict=True)
                 if not m]
        name = traj.atom or site
        reseeded = [label for label, paths in floored.items() if site in paths]
        if n_held or blind:
            message = (
                f"{name}: the moment is unsupported on {n_held} of {n} pattern(s) "
                f"({100.0 * n_held / n:.0f}% of the series) — |m| at or below "
                f"{MOMENT_SUPPORT_SIGMA:g}× its own esd, which reads as \"not "
                f"distinguishable from none\" and never as \"a small moment\"")
            if blind:
                message += (
                    f"; {len(blind)} more pattern(s) give no verdict at all "
                    f"({', '.join(blind[:4])}{' …' if len(blind) > 4 else ''}"
                    f") — the modulus has no esd there, because it was held "
                    f"or the phase was not seen, or the fit diverged — and "
                    f"are left out of the onset")
            if reseeded:
                message += (
                    f"; the modulus was reseeded to its floor "
                    f"({MOMENT_FLOOR_MU_B:g} μ_B) on {len(reseeded)} successor "
                    f"pattern(s) ({', '.join(sorted(reseeded)[:4])}"
                    f"{' …' if len(reseeded) > 4 else ''}) rather than "
                    f"warm-started from a value the pattern before did not "
                    f"support")
            out.append(Diagnostic(
                level="warning", code="SEQUENTIAL_MOMENT_HOLD", where=[site],
                value=float(n_held), message=message,
                suggestion=(
                    "plot the trajectory from series.magnetic_trajectory(), "
                    "which withholds the esd on exactly these points, and "
                    "quote them as held rather than as small; a held point's "
                    "value is the modulus the fit reached, not zero")))
        onset = traj.onset
        if onset is None:                        # pragma: no cover - shape
            continue
        if onset.x is not None:
            message = (
                f"{name}: the moment stops being supported between "
                f"{onset.bracket_labels[0]} and {onset.bracket_labels[1]} "
                f"({series.x_label} {onset.bracket[0]:g} → "
                f"{onset.bracket[1]:g}), so the onset is "
                f"{onset.x:g} ± {onset.x_esd:g} — a bracket set by the "
                f"spacing of the patterns, not a fitted critical point")
            spans = onset.note.partition(". The bracket spans ")[2]
            if spans:
                message += ". The bracket spans " + spans.partition(". ")[0]
            unquotable = onset.bracket_verdicts_final is False
            if unquotable:
                message += (". Do not quote it: "
                            + onset.note.split(". Do not quote it: ")[-1])
            out.append(Diagnostic(
                level="warning" if unquotable else "info",
                code="SEQUENTIAL_MOMENT_ONSET", where=[site],
                value=float(onset.x), message=message,
                suggestion=_RAISE_MAX_ITER if unquotable else _RUN_BOTH))
        elif not onset.monotone:
            out.append(Diagnostic(
                level="warning", code="SEQUENTIAL_MOMENT_ONSET", where=[site],
                message=f"{name}: {onset.note}",
                suggestion=(
                    "open the patterns either side of each switch: an "
                    "interleaved verdict is usually one pattern the ladder "
                    "rescued cold, or a moment carried across the transition "
                    "by a warm start, and both are visible in that entry's "
                    "rung and its magnetic row")))
    return out


_RAISE_MAX_ITER = (
    "raise the moment stage's max_iter and re-run: a bracket whose supported "
    "side stopped early is not a measurement of an onset")

_RUN_BOTH = (
    "run the series direction='both': one chain's onset is the boundary its "
    "own warm start reached, and the two together are the only check that it "
    "is the data's")

_NO_VERDICT = (
    "read the entries of the chain that gave no verdict (status and magnetic "
    "row): each pattern was held, did not see the phase, or diverged, and "
    "the two chains can only be compared on patterns both gave a verdict on")

_COMPARE_CHAINS = (
    "compare the two chains' magnetic rows pattern by pattern "
    "(series.magnetic_trajectory() against "
    "series.backward.magnetic_trajectory()): the pattern one chain supports "
    "and the other holds is where a warm start carried a moment the data does "
    "not, or where a floor never climbed out to a moment the data does carry")


def _supported_kind(onset) -> tuple[bool, bool]:
    """What a monotone reading with no bracket says: (any supported, any held).

    Everywhere, nowhere, or no verdict at all — three readings that each lack
    a bracket, and two chains disagreeing between them is a disagreement.
    """
    return (onset.n_supported > 0, onset.n_held > 0)


def _no_verdict(onset) -> bool:
    """Not one pattern of the chain gave a verdict: nothing to compare."""
    return onset.n_supported + onset.n_held == 0


def _with_onset_agreement(diagnostics: list[Diagnostic], forward: SeriesResult,
                          back: SeriesResult) -> list[Diagnostic]:
    """Fold the backward chain's onset into the forward ``…_ONSET`` rows.

    "The onset in each direction of the chain" (WP-1329) is one statement about
    two passes, so it is one diagnostic carrying both brackets rather than two
    diagnostics a reader has to notice are about the same thing.  The two
    **agree** when their brackets overlap — which is the WP's "within one
    pattern", since adjacent brackets share an endpoint — and their ``sense``
    is the same, so both read the same side as ordered; a disagreement
    raises the row to ``warning``: a moment carried across the transition by
    one chain's warm start and not the other's is exactly what a single pass
    cannot see, and it is the failure this whole comparison is for.

    A folded row is the *answer* to ``direction="both"``, so it never keeps the
    forward row's advice to run it — and replaces only that advice: an
    unquotable forward bracket keeps its own ("raise the moment stage's
    max_iter"), which the comparison does not address, and so does an
    interleaved forward verdict ("open the patterns either side of each
    switch"), which never asked for the comparison.  A chain that gave no
    verdict on any pattern is said to, with no cause attached: nothing was
    compared, so nothing was found carried or floored.
    """
    by_site = {}
    for site in back.magnetic_sites():
        by_site[site] = back.magnetic_trajectory(site)
    out: list[Diagnostic] = []
    seen: set[str] = set()
    for d in diagnostics:
        back_traj = by_site.get(d.where[0]) if d.where else None
        if d.code != "SEQUENTIAL_MOMENT_ONSET" or back_traj is None:
            out.append(d)
            continue
        seen.add(d.where[0])
        other = back_traj.onset
        mine = forward.magnetic_trajectory(d.where[0]).onset

        def advise(new: str, d=d) -> dict:
            # only the advice to run what just ran is replaced
            return {"suggestion": new} if d.suggestion == _RUN_BOTH else {}

        if _no_verdict(other):
            out.append(d.model_copy(update={
                "level": "warning",
                "message": (f"{d.message}; the backward chain gave no verdict "
                            f"on any pattern ({other.note}), so this reading "
                            f"has not been checked against it"),
                **advise(_NO_VERDICT)}))
            continue
        # three ways of lacking an onset, each blaming the chain that lacks it
        if mine.x is None and other.x is None:
            out.append(d.model_copy(update={
                "level": "warning",
                "message": (f"{d.message}; the backward chain located no "
                            f"single onset either ({other.note}), so neither "
                            f"pass has a bracket to quote"),
                **advise(_COMPARE_CHAINS)}))
            continue
        if mine.x is None:
            out.append(d.model_copy(update={
                "level": "warning",
                "message": (f"{d.message}; the backward chain brackets it "
                            f"{other.bracket[0]:g} → {other.bracket[1]:g} "
                            f"({other.x:g} ± {other.x_esd:g}), so the two "
                            f"passes do not agree on whether there is one "
                            f"onset"), **advise(_COMPARE_CHAINS)}))
            continue
        if other.x is None:
            out.append(d.model_copy(update={
                "level": "warning",
                "message": (f"{d.message}; the backward chain located no "
                            f"{'onset at all' if other.monotone else 'single onset'}"
                            f" ({other.note}), so the two passes do not agree "
                            f"on whether there is one"),
                **advise(_COMPARE_CHAINS)}))
            continue
        overlap = (max(mine.bracket[0], other.bracket[0])
                   <= min(mine.bracket[1], other.bracket[1]))
        text = (f"{d.message}; the backward chain brackets it "
                f"{other.bracket[0]:g} → {other.bracket[1]:g} "
                f"({other.x:g} ± {other.x_esd:g})")
        # agreement can only *keep* the row at info: an unconverged bracket is
        # a separate reason to warn and two chains agreeing about an
        # unconverged bracket is two readings of the same intermediate state
        early = [chain for chain, o in (("forward", mine), ("backward", other))
                 if o.bracket_verdicts_final is False]
        # a bracket in the same place with the ordered side on the other end
        # is not agreement: the two chains disagree about which side it is
        same_side = mine.sense == other.sense
        agrees = overlap and same_side and not early
        if agrees:
            tail = (", which overlaps the forward bracket — the onset is the "
                    "data's, not the ordering's")
            advice = ("quote the bracket, with the pattern spacing as its "
                      "uncertainty: the two chains reaching it from opposite "
                      "ends is the check that it is the data's")
        elif overlap and not same_side:
            side = {"falls": "below", "rises": "above"}
            tail = (f", which overlaps the forward bracket, but the forward "
                    f"chain supports the moment {side[mine.sense]} it and the "
                    f"backward chain {side[other.sense]} it: the two disagree "
                    f"about which side is ordered, so neither bracket is a "
                    f"measurement of the onset")
            advice = _COMPARE_CHAINS
        elif overlap:
            tail = (f", which overlaps the forward bracket, but the "
                    f"{' and the '.join(early)} bracket"
                    f"{' is' if len(early) == 1 else 's are'} not quotable: "
                    f"a supported side stopped early, so the two chains agree "
                    f"about an unfinished fit, not yet about the data")
            advice = _RAISE_MAX_ITER
        else:
            tail = (". The two do NOT overlap: one chain carried a moment "
                    "across the transition that the other never found, so "
                    "this onset is path-dependent and neither bracket is a "
                    "measurement of it")
            advice = _COMPARE_CHAINS
        out.append(d.model_copy(update={
            "level": "info" if agrees else "warning",
            "message": text + tail, **advise(advice)}))
    # The forward pass writes an onset row only for a bracket or an interleaved
    # verdict, so a forward chain that reads "supported everywhere" (a warm
    # start carrying the moment past the transition) wrote nothing to fold the
    # backward bracket into — and that disagreement is the one this comparison
    # exists to catch.  The backward chain's reading gets a row of its own —
    # including a monotone one with no bracket, whenever it is not the forward
    # chain's own kind: "supported everywhere" against "supported nowhere" is
    # the extreme of the disagreement, and no other row on the top level says
    # it (the HOLD row sits on the chain that held; PATH_DEPENDENT divides by a
    # held point's esd and cannot fire).
    for site, back_traj in by_site.items():
        other = back_traj.onset
        if site in seen or other is None:
            continue
        mine = forward.magnetic_trajectory(site).onset
        name = back_traj.atom or site
        if other.x is None and other.monotone:
            if _supported_kind(other) == _supported_kind(mine):
                continue

            def reading(o) -> str:
                n = o.n_supported + o.n_held
                if o.n_supported:
                    return f"supports all {n} pattern(s) it gave a verdict on"
                return f"supports none of the {n} pattern(s)"

            if _no_verdict(other) or _no_verdict(mine):
                silent, spoke = ((("backward", other), ("forward", mine))
                                 if _no_verdict(other) else
                                 (("forward", mine), ("backward", other)))
                out.append(Diagnostic(
                    level="warning", code="SEQUENTIAL_MOMENT_ONSET",
                    where=[site],
                    message=(
                        f"{name}: the {silent[0]} chain gave no verdict on any "
                        f"pattern ({silent[1].note}), while the {spoke[0]} "
                        f"chain {reading(spoke[1])}, so the two passes share "
                        f"no pattern to compare and neither has a bracket to "
                        f"quote"),
                    suggestion=_NO_VERDICT))
                continue

            out.append(Diagnostic(
                level="warning", code="SEQUENTIAL_MOMENT_ONSET", where=[site],
                message=(
                    f"{name}: the backward chain {reading(other)}, while the "
                    f"forward chain {reading(mine)}, so the two passes "
                    f"disagree on every pattern they both judged and neither "
                    f"has a bracket to quote — each chain's verdict followed "
                    f"its own starting value: either one warm start carried "
                    f"a moment the data does not hold, or the other never "
                    f"climbed out of the floor to one the data does carry"),
                suggestion=_COMPARE_CHAINS))
            continue
        found = (f"brackets the onset {other.bracket[0]:g} → "
                 f"{other.bracket[1]:g} ({other.x:g} ± {other.x_esd:g})"
                 if other.x is not None else
                 f"has no single onset ({other.note})")
        if _no_verdict(mine):
            out.append(Diagnostic(
                level="warning", code="SEQUENTIAL_MOMENT_ONSET", where=[site],
                value=None if other.x is None else float(other.x),
                message=(
                    f"{name}: the backward chain {found}, while the forward "
                    f"chain gave no verdict on any pattern ({mine.note}), so "
                    f"this reading has not been checked against it"),
                suggestion=_NO_VERDICT))
            continue
        out.append(Diagnostic(
            level="warning", code="SEQUENTIAL_MOMENT_ONSET", where=[site],
            value=None if other.x is None else float(other.x),
            message=(
                f"{name}: the backward chain {found}, while the forward chain "
                f"located none ({mine.note}), so the two passes do not agree "
                f"on whether there is an onset — a moment one chain's warm "
                f"start carried across the transition reads as supported "
                f"there"),
            suggestion=_COMPARE_CHAINS))
    return out


def _path_dependence_diagnostics(forward: SeriesResult,
                                 backward: SeriesResult,
                                 relative: frozenset[str] = frozenset(),
                                 angles: frozenset[str] = frozenset()
                                 ) -> list[Diagnostic]:
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

    ``relative`` paths are not compared, for :func:`_discontinuity_steps`'
    reason and more sharply: the two chains start a pattern from opposite
    neighbours, so a coordinate DOF's value — the step from that start — has
    opposite signs in the two by construction.  Compared, it named the DOF
    path-dependent on a series whose coordinate agreed in both chains
    (WP-1333).  The coordinate rows are compared instead, and they are what
    the check was asked about.

    ``angles`` paths are compared modulo a turn (:func:`_angle_difference`):
    two chains that end one pattern either side of the azimuth's cut agree on
    the moment and differ by 2π in value (#604).
    """
    out: list[Diagnostic] = []
    # which patterns the comparison can reach at all: a pattern one chain
    # has no entry for is compared on no path (WP-1333)
    fitted = {"forward": {e.index: e.label for e in forward.entries},
              "backward": {e.index: e.label for e in backward.entries}}
    known = {**{f.index: f.label
                for f in (*forward.failures, *backward.failures)},
             **fitted["forward"], **fitted["backward"]}
    missing = [(i, known[i], chain) for i in sorted(known)
               for chain in ("forward", "backward") if i not in fitted[chain]]
    unjudged: list[str] = []
    for path in forward.paths(varied_only=False):
        if path in relative:
            continue
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
        # a path *some* chain measured and the comparison could not reach is
        # the #269 silence; one neither chain measured anywhere (a tie row off
        # a source never freed, a coefficient on its floor) is not a
        # measurement in either, and its trajectory's absent esds already say so
        _, vf_all, sf_all = f.arrays()
        _, vb_all, sb_all = b.arrays()
        measured = bool(np.isfinite(sf_all).any() or np.isfinite(sb_all).any())
        if not pairs:
            if measured:
                unjudged.append(path)
            continue
        fi = np.asarray([i for i, _ in pairs], dtype=int)
        bj = np.asarray([j for _, j in pairs], dtype=int)
        labels = [f.labels[i] for i in fi]
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
        gap = np.abs(_angle_difference(vf - vb) if path in angles else vf - vb)
        if not np.any(comparable & (combined > 0.0)):
            # …nor one whose two chains agree below the noise floor on every
            # shared pattern: the comparison calls that agreement whatever
            # the esds say (the n_sigma floor below), so there was nothing an
            # esd could have changed — a softplus coefficient on its floor,
            # measured on different patterns by each chain, is the case
            if measured and np.any(gap > _noise_floor(vf, vb)):
                unjudged.append(path)
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            n_sigma = gap / np.where(combined > 0.0, combined, np.nan)
        n_sigma = np.where(gap > _noise_floor(vf, vb), n_sigma, 0.0)
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
    return out + _path_check_coverage(missing, len(known), unjudged)


def refine_sequential(patterns: Sequence[PatternData], structure: Structure,
                      instrument: Instrument, *,
                      carry: Sequence[str] = ("*",),
                      carry_hkl_intensities: bool = True,
                      backend: str = "numpy", solver: str = "trf",
                      history: bool | str | Path = False,
                      **kw) -> SeriesResult:
    """One-shot functional API for a warm-started series.

    ``refine_sequential(patterns, structure, instrument, x=temperatures)``.
    Keyword arguments beyond ``carry``/``carry_hkl_intensities``/``backend``/
    ``solver``/``history`` go to :meth:`SequentialRefinement.fit`.
    """
    series = SequentialRefinement(structure, instrument, carry=carry,
                                  carry_hkl_intensities=carry_hkl_intensities,
                                  backend=backend, solver=solver, history=history)
    return series.fit(patterns, **kw)
