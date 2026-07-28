"""Sequential refinement of an ordered series of patterns (WP-0505).

An in-situ ramp, a parametric sweep, a tray of related specimens: N patterns
refined one at a time, each warm-started from its predecessor's converged
state.  **Not** one joint residual — that is :mod:`pxrdref.multi`, which stacks
histograms that *share* structural parameters.  Here nothing is shared; the
only thing that crosses a pattern boundary is the starting point.

Two consequences shape this module.

*The output is a trajectory.*  a(T), Biso(t), the weight fractions against the
series coordinate — with esds, and with the per-pattern fit status that
produced each point.  :class:`~pxrdref.schemas.sequential.SeriesResult` is that
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
``SEQUENTIAL_DISCONTINUITY``
    a step much larger than the local trend — the science (a phase transition)
    or a chain failure, and the diagnostic says both.
``SEQUENTIAL_PATH_DEPENDENT``
    with ``direction="both"``, the forward and backward chains disagree by more
    than their esds allow: that parameter's trajectory is an artefact of the
    ordering, not a measurement.

Constraining a parameter to a functional form of T across the whole series —
parametric refinement, Stinton & Evans (2007) J. Appl. Cryst. 40, 87 — is a
*joint* fit over the series and is deliberately out of scope; these fences
exist partly so a sequential trajectory is never mistaken for one.
"""

from __future__ import annotations

import fnmatch
from collections.abc import Callable, Sequence
from pathlib import Path

import numpy as np

from .backend.api import backend_dtype_note
from .history.tree import RefinementTree
from .params.vector import ParameterTable
from .refine import _VERSION, Refinement, _extract_reflections, _utcnow
from .schemas.common import Diagnostic, Mode, Provenance
from .schemas.history import ReflectionState
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.results import RefinementResult
from .schemas.sequential import SeriesEntry, SeriesResult
from .schemas.structure import Structure
from .strategy.staged import PLAN_PRESETS, RefinementPlan, Stage

#: Rwp above this multiple of the accepted-so-far **median** triggers a cold
#: refit.  A median rather than the previous value on purpose: one bad pattern
#: must not be able to ratchet the threshold up and let its successors through.
RESEED_FACTOR = 1.25

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
    seen: dict[str, int] = {}
    unique = []
    for i, name in enumerate(out):
        if name in seen:
            unique.append(f"{name}_{i}")
        else:
            seen[name] = i
            unique.append(name)
    return unique


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
        correlation_guard=plan.correlation_guard)


def _resolve_plan(plan: RefinementPlan | str, mode: Mode) -> RefinementPlan:
    if not isinstance(plan, str):
        return plan
    name = plan
    if name == "mccusker_default" and mode == "lebail":
        name = "profile_only"
    elif name == "mccusker_default" and mode == "pawley":
        name = "pawley_default"
    try:
        return PLAN_PRESETS[name]()
    except KeyError:
        raise ValueError(f"unknown plan preset {plan!r}; "
                         f"available: {sorted(PLAN_PRESETS)}") from None


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


def _entry_from_result(index: int, label: str, x: float | None,
                       result: RefinementResult) -> SeriesEntry:
    return SeriesEntry(
        index=index, label=label, x=x,
        status=result.status,
        statistics=result.statistics.model_copy(deep=True),
        parameters=[p.model_copy(deep=True) for p in result.parameters],
        qpa=result.qpa.model_copy(deep=True) if result.qpa is not None else None,
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
    :class:`~pxrdref.schemas.results.RefinementResult` objects (with curves,
    for plotting) and :attr:`trees_` the per-pattern histories; the returned
    :class:`~pxrdref.schemas.sequential.SeriesResult` carries the summaries and
    is the serializable one.
    """

    def __init__(self, structure: Structure, instrument: Instrument, *,
                 backend: str = "numpy",
                 carry: Sequence[str] = ("*",),
                 history: bool | str | Path = False):
        if backend != "numpy":
            from .backend import resolve_backend

            try:
                resolve_backend(backend)  # fail fast with the install hint
            except ValueError as exc:
                raise NotImplementedError(str(exc)) from exc
        self._backend = backend
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
            prepare: Callable[[int, PatternData, Structure, Instrument],
                              None] | None = None,
            on_result: Callable[[int, RefinementResult], None] | None = None,
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
            catches it and refits cold with the full staged plan.
        direction:
            ``"forward"``, ``"backward"`` (chain from the last pattern), or
            ``"both"``, which runs it each way and reports where the two
            trajectories disagree by more than their esds allow.  The reported
            entries are the forward ones.
        reseed:
            Refit a pattern cold when its warm-started fit diverged or landed
            far above the series median Rwp, and keep the better of the two.
        prepare:
            ``(index, data, structure, instrument) -> None``, called on the
            warmed models just before each pattern's fit.  The hook exists for
            what a `carry` glob cannot express: a parameter that must be
            re-estimated *from this pattern* rather than either carried or left
            at its initial value — a phase scale on a series of different
            mixtures being the case that forced it.  Excluding scales from
            `carry` alone would only fall back to the first pattern's guess.
        """
        patterns = list(patterns)
        if not patterns:
            raise ValueError("a sequential refinement needs at least one pattern")
        if refit not in ("stages", "single"):
            raise ValueError("refit must be 'stages' or 'single'")
        if direction not in ("forward", "backward", "both"):
            raise ValueError("direction must be 'forward', 'backward' or 'both'")
        if x is not None and len(x) != len(patterns):
            raise ValueError(f"x has {len(x)} entries for {len(patterns)} patterns")
        names = _labels_for(patterns, labels)
        xs = [None] * len(patterns) if x is None else [float(v) for v in x]
        if x is not None and x_label == "index":
            x_label = "x"
        base_plan = _resolve_plan(plan, mode)
        warm_plan = base_plan if refit == "stages" else _collapse(base_plan)

        order = list(range(len(patterns)))
        if direction == "backward":
            order.reverse()
        entries, results, trees, models = self._chain(
            order, patterns, names, xs, mode, base_plan, warm_plan,
            two_theta_limits, reseed, reseed_factor, prepare, on_result)

        diagnostics = [d for e in entries for d in _reseed_diagnostics(e)]
        series = SeriesResult(
            mode=mode, entries=entries, x_label=x_label,
            direction=direction,  # type: ignore[arg-type]
            provenance=Provenance(package_version=_VERSION, created_utc=_utcnow(),
                                  backend=self._backend,
                                  dtype=backend_dtype_note(self._backend)))
        diagnostics += _discontinuity_diagnostics(series)

        if direction == "both":
            back_entries, *_ = self._chain(
                list(reversed(order)), patterns, names, xs, mode, base_plan,
                warm_plan, two_theta_limits, reseed, reseed_factor, prepare,
                None)
            back = SeriesResult(mode=mode, entries=back_entries, x_label=x_label,
                                direction="backward")
            diagnostics += _path_dependence_diagnostics(series, back)
            self.backward_ = back

        series.diagnostics = diagnostics
        self.results_ = results
        self.trees_ = trees
        self._structures = [s for s, _ in models]
        self._instruments = [i for _, i in models]
        self.result_ = series
        return series

    # ------------------------------------------------------------------
    def _chain(self, order, patterns, names, xs, mode, base_plan, warm_plan,
               two_theta_limits, reseed, reseed_factor, prepare, on_result):
        """Walk ``order``, warm-starting each fit from the previous accepted one.

        Returns entries in **series** order regardless of the walk direction, so
        a backward chain's trajectory is directly comparable with a forward
        one's.
        """
        entries: dict[int, SeriesEntry] = {}
        results: dict[int, RefinementResult] = {}
        trees: dict[int, RefinementTree | None] = {}
        models: dict[int, tuple[Structure, Instrument]] = {}
        previous: tuple[Structure, Instrument] | None = None
        previous_hkl: list = []
        previous_tag: tuple[str | None, str | None] = (None, None)
        accepted_rwp: list[float] = []

        for position, k in enumerate(order):
            data = patterns[k]
            warm = previous is not None
            ref, result = self._fit_one(
                data, names[k], previous, previous_hkl,
                warm_plan if warm else base_plan,
                mode, two_theta_limits, position, previous_tag, prepare, k)
            entry = _entry_from_result(k, names[k], xs[k], result)

            if warm and reseed and _reseed_needed(result, accepted_rwp,
                                                  reseed_factor):
                cold_ref, cold = self._fit_one(
                    data, names[k], None, [], base_plan, mode, two_theta_limits,
                    position, previous_tag, prepare, k)
                if _better(cold, result):
                    entry = _entry_from_result(k, names[k], xs[k], cold)
                    entry.reseeded = True
                    entry.rwp_warm = result.statistics.rwp
                    entry.n_iterations += sum(s.n_iterations for s in result.stages)
                    ref, result = cold_ref, cold
                else:
                    # the warm fit was flagged but is still the better of the
                    # two: keep it, and say the cold restart did not rescue it
                    entry.rwp_warm = result.statistics.rwp
                    entry.n_iterations += sum(s.n_iterations for s in cold.stages)

            entries[k] = entry
            results[k] = result
            trees[k] = ref.history
            models[k] = (ref.fitted_structure, ref.fitted_instrument)
            previous = models[k]
            previous_hkl = _extract_reflections(ref._model)
            previous_tag = (entry.tree_id, entry.node_id)
            if entry.statistics is not None:
                accepted_rwp.append(entry.statistics.rwp)
            if on_result is not None:
                on_result(k, result)

        keys = sorted(entries)
        return ([entries[k] for k in keys], [results[k] for k in keys],
                [trees[k] for k in keys], [models[k] for k in keys])

    def _fit_one(self, data: PatternData, label: str,
                 previous: tuple[Structure, Instrument] | None,
                 previous_hkl: list[ReflectionState],
                 plan: RefinementPlan, mode: Mode, two_theta_limits,
                 position: int, previous_tag: tuple[str | None, str | None],
                 prepare, index: int):
        """One pattern: warm the models from ``previous``, then run ``plan``."""
        structure = self.structure.model_copy(deep=True)
        instrument = self.instrument.model_copy(deep=True)
        if previous is not None:
            _carry_into(structure, instrument, previous, self.carry)
        if prepare is not None:
            prepare(index, data, structure, instrument)
        ref = Refinement(structure, instrument, backend=self._backend,
                         history=self._history_spec(label))
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
                         two_theta_limits=two_theta_limits)
        _link_history(ref, position, label, previous_tag)
        return ref, result

    def _history_spec(self, label: str):
        """Per-pattern history target: a file under the given directory."""
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


def _noise_floor(*values) -> float:
    """The smallest change in these values that is not floating-point noise.

    See :data:`NOISE_FLOOR_REL`: relative to the parameter's own magnitude, and
    never below 1e-9 absolute so a parameter that is identically zero does not
    get an infinitely fine floor.
    """
    magnitude = max((float(np.max(np.abs(v))) for v in values if len(v)),
                    default=0.0)
    return NOISE_FLOOR_REL * max(1.0, magnitude)


def _discontinuity_diagnostics(series: SeriesResult) -> list[Diagnostic]:
    """Steps far larger than the same parameter's typical step in this series.

    Reported, never smoothed: a jump is either the science (a transition) or a
    chain failure, and nothing here can tell them apart — so the diagnostic
    names both and the trajectory is left exactly as fitted.
    """
    if len(series) < MIN_POINTS_FOR_DISCONTINUITY:
        return []
    out: list[Diagnostic] = []
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
        out.append(Diagnostic(
            level="info", code="SEQUENTIAL_DISCONTINUITY", where=[path],
            message=(f"{path} steps by {step[k]:.4g} between "
                     f"{traj.labels[k]} and {traj.labels[k + 1]} "
                     f"({traj.x_label} {xv[k]:g} → {xv[k + 1]:g}), "
                     f"{step[k] / scale:.0f}× its median step over the series"),
            suggestion=("either the specimen genuinely changed here (a "
                        "transition, a phase appearing) or the chain failed at "
                        "this point and carried the error onward — check this "
                        "pattern's own fit before reading the jump as physics"),
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
    """
    out: list[Diagnostic] = []
    for path in forward.paths(varied_only=False):
        f, b = forward.trajectory(path), backward.trajectory(path)
        if len(f) != len(b) or not len(f):
            continue
        _, vf, sf = f.arrays()
        _, vb, sb = b.arrays()
        combined = np.sqrt(np.nan_to_num(sf) ** 2 + np.nan_to_num(sb) ** 2)
        # A parameter with no esd anywhere cannot be judged this way; skip it
        # rather than declare agreement it has not earned.
        if not np.any(combined > 0.0):
            continue
        with np.errstate(divide="ignore", invalid="ignore"):
            n_sigma = np.abs(vf - vb) / np.where(combined > 0.0, combined, np.nan)
        n_sigma = np.where(np.abs(vf - vb) > _noise_floor(vf, vb), n_sigma, 0.0)
        if not np.any(n_sigma > PATH_DEPENDENCE_SIGMA):
            continue
        k = int(np.nanargmax(n_sigma))
        out.append(Diagnostic(
            level="warning", code="SEQUENTIAL_PATH_DEPENDENT", where=[path],
            message=(f"{path} differs between the forward and backward chains "
                     f"by up to {n_sigma[k]:.1f}σ (at {f.labels[k]}: "
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
                      backend: str = "numpy",
                      history: bool | str | Path = False,
                      **kw) -> SeriesResult:
    """One-shot functional API for a warm-started series.

    ``refine_sequential(patterns, structure, instrument, x=temperatures)``.
    Keyword arguments beyond ``carry``/``backend``/``history`` go to
    :meth:`SequentialRefinement.fit`.
    """
    series = SequentialRefinement(structure, instrument, carry=carry,
                                  backend=backend, history=history)
    return series.fit(patterns, **kw)
