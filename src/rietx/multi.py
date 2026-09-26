"""Multi-histogram joint refinement (WP-0308).

Refine one shared :class:`~rietx.schemas.structure.Structure` against several
patterns at once — different wavelengths, geometries or temperatures — each with
its own :class:`~rietx.schemas.instrument.Instrument`.  The histograms are
stacked into one residual (Von Dreele, 1997, J. Appl. Cryst. 30, 517): shared
structural parameters (cell, coordinates, occupancies, ADPs …) draw information
from every pattern, while each pattern keeps its own scale, background, zero and
resolution.  See :mod:`rietx.params.multi` for the parameter-sharing map and
:func:`rietx.optimize.least_squares.run_multi_least_squares` for the stacked
solve.

Rietveld mode only: Le Bail / Pawley intensities are per-pattern empirical
extractions, not shared quantities, so a multi-histogram fit of them is just
independent single fits — not the joint-residual point of this module.
"""

from __future__ import annotations

import dataclasses

import numpy as np

from .backend.api import backend_dtype_note
from .crystallography.symmetry import reflection_label_row
from .model.components import EXTRA_TICK_KEY
from .model.forward import PHASE_SUPPORT_SIGMA, compile_model
from .model.microstructure import microstructure_table
from .optimize.least_squares import (
    SOLVERS,
    _longest_line_wavelength,
    run_multi_least_squares,
)
from .optimize.qpa import compute_qpa, microabsorption_diagnostics
from .optimize.statistics import background_absorption, compute_statistics
from .params.multi import (
    SIZE_LAMBDA_POWER,
    MultiParameterTable,
    SharingMap,
    _longest_wavelength,
    _unscoped,
)
from .refine import (
    _VERSION,
    _WAVELENGTH_PINNED_BY_HELD_HISTOGRAM,
    _absorption_diagnostics,
    _absorption_record,
    _capillary_offset_diagnostics,
    _cell_runaway_diagnostic,
    _cell_runaway_withheld,
    _constraint_diagnostics,
    _covariance_diagnostics,
    _declared_wavelengths,
    _degenerate_cell_diagnostics,
    _guard_diagnostics,
    _phase_agreement,
    _phase_support_diagnostics,
    _qpa_unavailable_diagnostics,
    _refuse_without_phases,
    _resolve_specimen_absorption,
    _size_flag_diagnostics,
    _strain_flag_diagnostics,
    _unknown_path_diagnostics,
    _utcnow,
    _wavelength_calibration_diagnostics,
    clamp_cell_runaway,
)
from .report.schemas import THRESHOLDS_VERSION
from .schemas.common import Diagnostic, Provenance
from .schemas.instrument import Instrument
from .schemas.pattern import PatternData
from .schemas.results import (
    HistogramResult,
    RefinedParameter,
    RefinementResult,
    StageResult,
)
from .schemas.structure import Structure
from .strategy.staged import (
    BACKGROUND_ABSORPTION_GUARD,
    PLAN_PRESETS,
    GuardFinding,
    GuardReport,
    RefinementPlan,
    bound_findings,
    check_adp_positive_definite,
    check_hump_width,
)

_CELL_KEYS = ("a", "b", "c", "alpha", "beta", "gamma")


def _normalize_limits(ttl, n: int) -> list[tuple[float, float] | None]:
    if ttl is None:
        return [None] * n
    if (isinstance(ttl, tuple) and len(ttl) == 2
            and all(isinstance(x, (int, float)) for x in ttl)):
        return [ttl] * n  # one range applied to every histogram
    ttl = list(ttl)
    if len(ttl) != n:
        raise ValueError(f"two_theta_limits has {len(ttl)} entries for {n} histograms")
    return ttl


def _joint_unsupported_phases(models, mtable) -> set[int]:
    """Phases below support in **every** histogram (WP-1301).

    The authority ``_freeze_cell_windows_multi`` uses, for its reason: a phase
    invisible in one histogram may be plain in another, and if its cell is
    shared then the data — jointly, which is what a joint refinement fits —
    can see it.
    """
    per_model = [m.phase_support(t.decode(t.x0()))
                 for m, t in zip(models, mtable.tables, strict=True)]
    n_phases = min((len(s) for s in per_model), default=0)
    return {ip for ip in range(n_phases)
            if all(s[ip] < PHASE_SUPPORT_SIGMA for s in per_model)}


def _unsupported_paths_multi(mtable, absent: set[int]) -> list[str]:
    """Free structural paths (scoped) of the phases in ``absent``."""
    if not absent:
        return []
    prefixes = tuple(f"phases.{ip}." for ip in sorted(absent))
    return [p for p in mtable.free_paths
            if _unscoped(p).startswith(prefixes) and not p.endswith(".scale")]


def _joint_unsupported_paths(models, mtable) -> list[str]:
    """Free structural paths (scoped) of every jointly-unsupported phase."""
    return _unsupported_paths_multi(mtable,
                                    _joint_unsupported_phases(models, mtable))


def _hold_unsupported_phases_multi(models, mtable) -> list[str]:
    held = _joint_unsupported_paths(models, mtable)
    if held:
        mtable.set_vary(held, False)
    return held


def _rehold_multi(models, mtable, held: list[str],
                  start_values: list[dict[str, float]]
                  ) -> tuple[list[str], list[str]]:
    """The post-solve half of the rule, for the joint path.

    Same two answers as the single-histogram runner: a held phase that has
    appeared is released, and one that collapsed while solving is put back
    where the stage found it and held.  One extra solve covers both, and there
    is never a third.
    """
    # one measurement, two questions — the release and the collapse are
    # complementary readings of the same joint support test
    absent = _joint_unsupported_phases(models, mtable)
    prefixes = tuple(f"phases.{ip}." for ip in sorted(absent))
    held_set = set(held)
    released = [p for p in held
                if not (prefixes and _unscoped(p).startswith(prefixes))]
    collapsed = [p for p in _unsupported_paths_multi(mtable, absent)
                 if p not in held_set]
    if collapsed:
        for h, table in enumerate(mtable.tables):
            by_path = {e.path: e for e in table.entries}
            for scoped in collapsed:
                bare = mtable._unscope(h, scoped)
                if bare is not None and bare in by_path:
                    by_path[bare].value = start_values[h][bare]
            table.refresh_ties()
        mtable.set_vary(collapsed, False)
    if released:
        mtable.set_vary(released, True)
    return released, collapsed


def _clamp_cell_runaway_multi(mtable, start_values: list[dict[str, float]]
                              ) -> list[tuple[str, float, float]]:
    """:func:`~rietx.refine.clamp_cell_runaway`, extended to the joint runner
    (review of #385 finding 2): same shape as :func:`_rehold_multi` above,
    called the same way, after the same ``mtable.commit``.

    A shared cell parameter is a genuinely separate :class:`Entry` in every
    histogram's own :class:`~rietx.params.vector.ParameterTable` —
    :meth:`~rietx.params.multi.MultiParameterTable.commit` writes the same
    combined-θ value into each one, never a single shared object — so every
    table's own entries must be clamped and its own ties refreshed
    individually, exactly as the single-histogram runner does for one table.
    What changes for the *report*: a shared path's escaped/clamped values are
    identical in every histogram by construction (same start value, same
    committed value, same window), so it is named once under its bare
    (shared) path rather than once per histogram; a per-histogram path is
    scoped (``hist.h.…``) and is never shared with another table, so it is
    never deduplicated.
    """
    seen: dict[str, tuple[str, float, float]] = {}
    for h, table in enumerate(mtable.tables):
        clamped = clamp_cell_runaway(table, start_values[h])
        if clamped:
            table.refresh_ties()
        for path, old, new in clamped:
            scoped = mtable._canonical(h, path)
            seen[scoped] = (scoped, old, new)
    return list(seen.values())


class MultiHistogramRefinement:
    """Joint Rietveld refinement of a shared structure against several patterns.

    ``instruments`` is one instrument per pattern; ``sharing`` (a
    :class:`~rietx.params.multi.SharingMap`) overrides the default
    instrument-vs-sample split.  After :meth:`fit`, :attr:`fitted_structures`
    and :attr:`fitted_instruments` hold the per-histogram refined models (their
    shared parameters are identical; scale, background, zero and resolution
    differ).
    """

    def __init__(self, structure: Structure, instruments: list[Instrument], *,
                 sharing: SharingMap | None = None, backend: str = "numpy",
                 solver: str = "trf"):
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
        instruments = list(instruments)
        if len(instruments) < 1:
            raise ValueError("multi-histogram needs at least one instrument")
        self.mtable = MultiParameterTable(structure, instruments, sharing=sharing)
        # Resolve each histogram's specimen absorption (capillary µR or
        # flat-plate µt) from composition, exactly as the single-histogram path
        # does.  Without this a user who set ``capillary_radius_mm`` or
        # ``thickness_mm`` here would silently get no absorption correction and
        # no diagnostic saying so — the failure mode WP-0501's reporting exists
        # to prevent.  The dimensionless product is per *instrument* (each
        # histogram may be a different wavelength and geometry, hence a
        # different µ) but the structure is shared, which is what makes one loop
        # correct.
        resolved = [_resolve_specimen_absorption(structure, ins)
                    for ins in self.mtable.instruments]
        self._mu_r_source: list[str] = [src for src, _ in resolved]
        self._mu_r_skipped: list[str | None] = [why for _, why in resolved]
        #: λ per line as *declared*, per histogram, taken before any stage runs.
        #: The ``WAVELENGTH_CALIBRATION`` diagnostic reports the refined value
        #: against this, and it has to be snapshotted here: ``mtable`` writes
        #: refined values back into its own instrument copies at every stage, so
        #: by the time the result is built there is nothing left to compare to.
        self._declared_wavelengths: list[list[float]] = [
            _declared_wavelengths(ins) for ins in self.mtable.instruments]
        self.result_: RefinementResult | None = None
        self._models = None

    @property
    def n_histograms(self) -> int:
        return self.mtable.n_histograms

    @property
    def fitted_structures(self) -> list[Structure]:
        return self.mtable.structures

    @property
    def fitted_instruments(self) -> list[Instrument]:
        return self.mtable.instruments

    # ------------------------------------------------------------------
    def fit(self, data: list[PatternData], *, mode: str = "rietveld",
            plan: RefinementPlan | str = "mccusker_default",
            two_theta_limits=None, weights: list[float] | None = None
            ) -> RefinementResult:
        _refuse_without_phases(self.mtable.structures[0], "refine_multi")
        data = list(data)
        n = self.n_histograms
        if len(data) != n:
            raise ValueError(f"{len(data)} patterns for {n} instruments")
        if mode != "rietveld":
            raise NotImplementedError(
                "multi-histogram refinement is Rietveld-only in v0.3; Le Bail / "
                "Pawley intensities are per-pattern extractions, not shared, so a "
                "joint fit of them is just independent single-pattern fits")
        if isinstance(plan, str):
            try:
                plan = PLAN_PRESETS[plan]()
            except KeyError:
                raise ValueError(
                    f"unknown plan preset {plan!r}; available: {sorted(PLAN_PRESETS)}"
                ) from None
        limits = _normalize_limits(two_theta_limits, n)
        weights = [1.0] * n if weights is None else list(weights)
        if len(weights) != n or any(w <= 0 for w in weights):
            raise ValueError("weights must be one positive number per histogram")

        # staged plan, cumulative like the single-histogram runner: start all
        # fixed, free each stage's globs across every histogram, recompile each
        # histogram (⇒ per-histogram frozen discreteness) and joint-solve.
        self.mtable.set_vary(["*"], False)
        stage_results: list[StageResult] = []
        # one CELL_RUNAWAY diagnostic per stage that fired, exactly as the
        # single-histogram runner builds one per _run_stage call (review of
        # #385 finding 2) — collected here and folded into the run-level
        # diagnostics once the loop ends, since a stage here has no
        # StageReport of its own to carry it on.
        cell_runaway_diags: list[Diagnostic] = []
        # the last stage's alone, which is what the result withholds esds on
        # — ``refine._run_plan``'s ``answer_runaway``, for its reason
        answer_runaway: list[Diagnostic] = []
        models = None
        outcome = None
        carried_hold: list[str] = []
        for stage, ftol in zip(plan.stages, plan.stage_ftols(), strict=True):
            freed = self.mtable.set_vary(stage.turn_on, True)
            # what the stage asked for and did not get (WP-1414): a literal
            # no histogram has, and — the joint fit's own case — a histogram
            # the stage's globs reached nothing of while reaching another's
            unknown_paths = self.mtable.unknown_literals(stage.turn_on)
            unreached = self.mtable.unreached_histograms(stage.turn_on)
            if carried_hold:
                # lift the previous stage's hold before this one decides its
                # own — the single-histogram runner's rule (``_run_stage``),
                # and for its reason: a phase invisible then may be plain now,
                # and a cumulative plan need not name its cell again
                self.mtable.set_vary(carried_hold, True)
                carried_hold = []
            if stage.seed:
                self.mtable.seed_softplus(freed, stage.seed)
            self.mtable.apply_to_models()
            models = [
                compile_model(s, ins, d, mode="rietveld", two_theta_limits=lim,
                              moving_paths=set(tab.moving_paths))
                for s, ins, d, lim, tab in zip(
                    self.mtable.structures, self.mtable.instruments, data, limits,
                    self.mtable.tables, strict=True)]
            stage_ftol = {} if ftol is None else {"ftol": ftol}
            # A phase the data cannot see is flat here too, and "the data" is
            # every histogram (WP-1301): the rule is the one
            # ``_freeze_cell_windows_multi`` already applies, since a phase
            # invisible in one pattern and plain in another *is* seen by the
            # joint fit that shares its cell.
            # ``freed`` is derived from this whenever the hold moves, so the
            # record's ``freed``/``held`` stay disjoint however the stage ends
            # — the single-histogram runner's rule (``_run_stage``)
            declared_freed = list(freed)
            held = _hold_unsupported_phases_multi(models, self.mtable)
            if held:
                held_set = set(held)
                freed = [p for p in declared_freed if p not in held_set]
            start_values = self.mtable.decode(self.mtable.x0())
            outcome = run_multi_least_squares(models, self.mtable, weights=weights,
                                              max_iter=stage.max_iter,
                                              backend=self._backend,
                                              solver=self._solver, **stage_ftol)
            self.mtable.commit(outcome.theta)
            # A phase's own support can stay above PHASE_SUPPORT_SIGMA in
            # every histogram and its shared cell still walk to nonsense — the
            # single-histogram runner's own joint-degeneracy gap
            # (CELL_SAFETY_FRACTION's docstring), unaffected by which runner
            # is asking.  Checked and corrected once, on the outcome, never as
            # a bound the solver saw (review of #385 finding 2).
            cell_runaway = _clamp_cell_runaway_multi(self.mtable, start_values)
            if cell_runaway:
                self.mtable._rebuild_columns()
                outcome = dataclasses.replace(outcome, theta=self.mtable.x0())
            released, collapsed = _rehold_multi(models, self.mtable, held,
                                                start_values)
            if released or collapsed:
                released_set = set(released)
                held = [p for p in held + collapsed if p not in released_set]
                held_set = set(held)
                freed = [p for p in declared_freed if p not in held_set]
                second = run_multi_least_squares(
                    models, self.mtable, weights=weights,
                    max_iter=stage.max_iter, backend=self._backend,
                    solver=self._solver, **stage_ftol)
                self.mtable.commit(second.theta)
                second_runaway = _clamp_cell_runaway_multi(self.mtable, start_values)
                if second_runaway:
                    self.mtable._rebuild_columns()
                    cell_runaway = cell_runaway + second_runaway
                    second = dataclasses.replace(second, theta=self.mtable.x0())
                outcome = dataclasses.replace(
                    second, cost_initial=outcome.cost_initial,
                    n_iterations=outcome.n_iterations + second.n_iterations,
                    n_constraint_truncations=(outcome.n_constraint_truncations
                                              + second.n_constraint_truncations),
                    # summed for the same reason the truncations are: the stage
                    # ran twice and the count is a fact about its whole search
                    n_degenerate_cell_probes=(outcome.n_degenerate_cell_probes
                                              + second.n_degenerate_cell_probes))
            runaway_diag = _cell_runaway_diagnostic(cell_runaway)
            answer_runaway = [] if runaway_diag is None else [runaway_diag]
            if runaway_diag is not None:
                cell_runaway_diags.append(runaway_diag)
            self.mtable.apply_to_models()
            carried_hold = list(held)
            stage_results.append(StageResult(
                name=stage.name, status=outcome.status,
                n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed,
                n_constraint_truncations=outcome.n_constraint_truncations,
                n_degenerate_cell_probes=outcome.n_degenerate_cell_probes,
                ftol=ftol, held=held, released=released,
                unknown_paths=unknown_paths, unreached_histograms=unreached))

        assert models is not None and outcome is not None
        self._models = models
        self.result_ = self._build_result(models, outcome, weights, plan.correlation_guard,
                                           stage_results, cell_runaway_diags,
                                           answer_runaway)
        return self.result_

    # ------------------------------------------------------------------
    def _ticks(self, model, structure, values
               ) -> tuple[dict[str, list[float]], dict[str, list[list[int]]]]:
        """Positions per phase, and which reflection each of them is.

        Both, from one walk.  This is the second builder CLAUDE.md warns
        about — ``refine._build_result`` has the other — and a joint fit whose
        ticks carried no Miller indices would be the one surface where
        pointing at a tick told the reader nothing (WP-1438).
        """
        ticks: dict[str, list[float]] = {}
        tick_hkl: dict[str, list[list[int]]] = {}
        for ip, cp in enumerate(model.phases):
            name = structure.phases[ip].name
            cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_KEYS)
            rows = [cp.reflections.two_theta(cell, lam) + values["instrument.zero_shift"]
                    for lam in model.line_wavelengths]
            pos = np.concatenate(rows) if rows else np.array([])
            # one reflection list per emission line, in the same order each
            # time, so the index list is that list tiled
            # (H, m), not H: a satellite is labelled by its order (WP-1326)
            hkl = (np.tile(cp.reflections.hklm, (len(rows), 1)) if rows
                   else np.zeros((0, 4), dtype=np.int64))
            keep = np.isfinite(pos)
            pos, hkl = pos[keep], hkl[keep]
            order = np.argsort(pos, kind="stable")
            ticks[name] = [float(v) for v in pos[order]]
            tick_hkl[name] = [reflection_label_row(r) for r in hkl[order]]
        # Declared sharp peaks are ticks here too (WP-1103, the member
        # contract's clause 2).  A joint fit's Layer 0 reads *this* list, so
        # without the row every declared peak comes back as an unindexed
        # impurity on every histogram — the single-histogram failure
        # ``refine._build_result`` writes the same key to prevent.  The
        # positions come from the compiled model rather than from a second
        # loop, so the two surfaces cannot drift.
        extra = model.extra_peak_tick_positions(values)
        if extra:
            # no `tick_hkl` row: a peak declared by centre has no Miller
            # index, and an empty list would claim it had none of its own
            ticks[EXTRA_TICK_KEY] = extra
        return ticks, tick_hkl

    def _build_result(self, models, outcome, weights, correlation_guard,
                      stage_results, cell_runaway_diags=(),
                      answer_runaway=()) -> RefinementResult:
        mt = self.mtable
        n = mt.n_histograms
        thetas = mt.split(outcome.theta)
        stderr = outcome.stderr_internal
        corr = outcome.correlation
        n_data = [len(m.tt) for m in models]
        data_off = np.concatenate([[0], np.cumsum(n_data)]).astype(int)

        # per-histogram slices ---------------------------------------------------
        per_values, per_ycalc, per_ybkg, per_esds = [], [], [], []
        histograms: list[HistogramResult] = []
        top_bg: list[GuardFinding] = []
        for h in range(n):
            table = mt.tables[h]
            model = models[h]
            struct = mt.structures[h]
            values = table.decode(thetas[h])
            y_calc = model.evaluate(values)
            y_bkg = model.background(values)
            per_values.append(values)
            per_ycalc.append(y_calc)
            per_ybkg.append(y_bkg)

            cm = mt.col_map(h)
            s_h = stderr[cm] if stderr is not None else None
            corr_h = corr[np.ix_(cm, cm)] if corr is not None else None
            esd_h = (table.stderr_physical(thetas[h], s_h, corr_h)
                     if s_h is not None else {})
            per_esds.append(esd_h)

            n_free_h = mt.n_shared + len(mt.per_hist_paths[h])
            stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                       n_free=n_free_h, y_background=y_bkg)
            qpa = self._histogram_qpa(h, model, struct, values, thetas[h], s_h, corr_h)

            diags: list[Diagnostic] = []
            j0, j1 = data_off[h], data_off[h] + n_data[h]
            if outcome.jac is not None and len(table.free_paths) > 1:
                jh = np.asarray(outcome.jac)[j0:j1][:, cm]
                for path, r2 in sorted(background_absorption(
                        jh, table.free_paths,
                        model.peak_component_prefixes()).items(),
                                       key=lambda kv: -kv[1]):
                    if r2 > BACKGROUND_ABSORPTION_GUARD:
                        # ``hist.h.<path>`` is this surface's own addressing —
                        # the same prefix ``RefinedParameter.path`` uses for a
                        # per-histogram parameter — so the finding's paths stay
                        # resolvable against the result a client is holding.
                        finding = GuardFinding.background_absorption(
                            f"hist.{h}.{path}", r2)
                        top_bg.append(finding)
                        diags.extend(_guard_diagnostics(
                            GuardReport(background_correlations=[finding])))
            if qpa is not None:
                diags.extend(microabsorption_diagnostics(qpa))
            else:
                diags.extend(_qpa_unavailable_diagnostics(struct, values))
            # specimen absorption, per histogram — each may sit at its own
            # wavelength and geometry, hence its own µR/µt.  Only the failure
            # modes are surfaced here; the applied value lives on
            # ``fitted_instruments[h]``.
            absorption = _absorption_record(model, self._mu_r_source[h],
                                            self._mu_r_skipped[h], values)
            if absorption is not None:
                diags.extend(_absorption_diagnostics(absorption))
            # A joint fit's shared cell draws from every histogram, so a
            # capillary that could not express its eq (4) offsets folds them
            # into that one cell — the misreading WP-1073 exists to name, at its
            # worst when several radius-less capillaries pool into one number.
            # Per histogram, like the absorption and wavelength diagnostics
            # above: each has its own geometry and locked-entry table.
            diags.extend(_capillary_offset_diagnostics(model, table))
            # A declared background peak narrowing toward the resolution is a
            # disguised Bragg peak here exactly as in a single fit — and the
            # joint path is the only one that never ran the check.  Per
            # histogram (each keeps its own background and peaks), reported
            # through this histogram's diagnostics like everything else the
            # joint fit measures per pattern (HUMP_TOO_NARROW).
            narrow = check_hump_width(table, model)
            if narrow:
                diags.extend(_guard_diagnostics(
                    GuardReport(narrow_humps=narrow)))
            diags.extend(_wavelength_calibration_diagnostics(
                self._declared_wavelengths[h], table, values, esd_h,
                pinned_by=_WAVELENGTH_PINNED_BY_HELD_HISTOGRAM, h=h))
            # The two tier-2 flags, per histogram — without which a joint fit
            # gets the tier-1 bound (``_freeze_strain_cap_multi`` /
            # ``_freeze_size_cap_multi``) and none of the interpretation the
            # two-tier split exists for.  Per histogram rather than once,
            # because each reads this histogram's own copy against this
            # histogram's own λ.  Since WP-1131 that is a *check* rather than a
            # discrepancy: the shared column is normalised by λ, so the size
            # flag reads the same crystallite in every pattern and a
            # disagreement between two histograms' rows would mean the
            # normalisation had come undone.  Before it, one shared ``lor_size``
            # was a different apparent size in each pattern and a single reading
            # would have quoted one histogram's λ about all of them.
            # The strain flag is λ-free and repeats per histogram for the same
            # reason the absorption and wavelength rows above do — a caller
            # reads one histogram's diagnostics and must not have to know that
            # this one row lives somewhere else.
            diags.extend(_strain_flag_diagnostics(model, values, struct))
            diags.extend(_size_flag_diagnostics(model, values, struct))

            histograms.append(HistogramResult(
                label=model.meta.get("label", "") or f"hist{h}",
                weight=float(weights[h]), statistics=stats,
                two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
                y_calc=y_calc.tolist(), y_background=y_bkg.tolist(),
                sigma=model.sigma.tolist(),
                **dict(zip(("ticks", "tick_hkl"),
                           self._ticks(model, struct, values))),
                qpa=qpa,
                # per histogram, like the QPA and the absorption record above:
                # the partition is of *this* pattern's counts, so a joint fit
                # has one structure R per histogram, not a pooled one
                phase_agreement=_phase_agreement(model, values, struct),
                diagnostics=diags))

        # pooled combined statistics (reported, never quoted alone) --------------
        combined = compute_statistics(
            np.concatenate([m.y_obs for m in models]),
            np.concatenate(per_ycalc),
            np.concatenate([m.sigma for m in models]),
            n_free=len(mt.free_paths),
            y_background=np.concatenate(per_ybkg))

        # one bound test, two consumers: the rows' at_bound flag and the
        # BOUND_HIT diagnostics (WP-1076)
        at_bounds = bound_findings(
            mt.bounds(), mt.free_paths, outcome.theta,
            cos=outcome.residual_cosine, esd=outcome.stderr_internal)
        # Histogram 0's physical esds, built once in the loop above and read by
        # two consumers (WP-1131): the shared rows of ``_parameters``, and the
        # microstructure block, which reads histogram 0 because its value scale
        # is exactly 1.0.  With a correlation matrix this is a dense n x n, so
        # a second build here would double the cost for the same dict.
        esd_hist0 = per_esds[0] if per_esds else {}
        parameters = self._parameters(thetas, stderr, corr, at_bounds, esd_hist0,
                                      answer_runaway)
        diagnostics = self._top_diagnostics(outcome, correlation_guard, top_bg,
                                            at_bounds)
        if stage_results:
            diagnostics = diagnostics + _constraint_diagnostics(
                stage_results[-1].name, outcome)
            # the answer-producing stage only: its covariance is the one every
            # reported esd is read off (WP-1333)
            diagnostics = diagnostics + _covariance_diagnostics(
                stage_results[-1].name, outcome, answer=True)
        # Every stage, not only the last one, exactly as the single-histogram
        # path sums it (``refine._degenerate_cell_diagnostics``): a degenerate
        # probe is a fact about the search and not about the final point.
        diagnostics = diagnostics + _degenerate_cell_diagnostics(
            [(sr.name, sr.n_degenerate_cell_probes) for sr in stage_results])
        # What a stage asked for and did not get (WP-1414), read off the
        # records.  The near-miss draws on both spellings a glob can match
        # here, so a bare typo is answered bare and a scoped one scoped.
        diagnostics = diagnostics + _unknown_path_diagnostics(
            stage_results, sorted(mt.known_paths()),
            listing="[e.path for t in ref.mtable.tables for e in t.entries]")
        diagnostics = diagnostics + _unreached_histogram_diagnostics(
            stage_results, [h.label for h in histograms])
        # one CELL_RUNAWAY per stage that fired the joint clamp above,
        # collected during the loop since there is no per-stage StageReport
        # here to carry it on (review of #385 finding 2)
        diagnostics = diagnostics + cell_runaway_diags
        # A phase the joint fit cannot see, and what the run did about it
        # (WP-1301).  Once for the fit rather than once per histogram, because
        # the statement is joint: the support is the phase's **strongest**
        # showing across the histograms, the line count its total, and the
        # range the union of theirs.  Before this the joint path was the only
        # one that never said it at all.
        #
        # ``max``, quoting ``_joint_unsupported_phases`` — a phase is one the
        # joint fit cannot see only when it is below support in *every*
        # histogram, and that is exactly ``max(support) < σ``.  The weakest
        # showing would fire this on a phase invisible in one pattern and plain
        # in another, which is a phase the joint fit measures and never holds:
        # a warning on a healthy phase teaches a consumer to ignore the code.
        per_support = np.array([m.phase_support(v)
                                for m, v in zip(models, per_values, strict=True)])
        per_lines = np.array([m.phase_line_counts() for m in models])
        diagnostics = diagnostics + _phase_support_diagnostics(
            per_support.max(axis=0), per_lines.sum(axis=0),
            (min(m.tt_min for m in models), max(m.tt_max for m in models)),
            [_unscoped(p) for p in mt.free_paths],
            self.mtable.structures[0], stage_results)

        weight_note = ("unit (each point's esd governs)"
                       if all(w == 1.0 for w in weights)
                       else ", ".join(f"hist{h}={w:g}" for h, w in enumerate(weights)))
        provenance = Provenance(
            package_version=_VERSION, created_utc=_utcnow(),
            backend=self._backend, dtype=backend_dtype_note(self._backend),
            solver=self._solver, report_thresholds_version=THRESHOLDS_VERSION,
            notes={"n_histograms": str(n), "histogram_weights": weight_note})

        return RefinementResult(
            status=outcome.status, mode="rietveld",
            parameters=parameters, statistics=combined,
            stages=stage_results, diagnostics=diagnostics, provenance=provenance,
            # top-level arrays mirror histogram 0 so .plot() and existing
            # consumers keep working; the real per-pattern data is in histograms.
            two_theta=histograms[0].two_theta, y_obs=histograms[0].y_obs,
            y_calc=histograms[0].y_calc, y_background=histograms[0].y_background,
            sigma=histograms[0].sigma, ticks=histograms[0].ticks,
            qpa=histograms[0].qpa,
            # WP-1131: one block per phase, read off **histogram 0** — the
            # reference wavelength, whose value scale is exactly 1.0, so its
            # coefficients *are* the shared column and the size behind them is
            # the specimen's one number.  Reading any other histogram would
            # give the same size from a different coefficient; reading none
            # would leave every joint fit reporting an empty list, which says
            # "no microstructure" about the fits this correction exists for.
            microstructure=microstructure_table(
                mt.structures[0], per_values[0],
                wavelength=_longest_line_wavelength(models[0]),
                esds=esd_hist0),
            histograms=histograms)

    def _histogram_qpa(self, h, model, struct, values, theta_h, s_h, corr_h):
        scale_paths = [f"phases.{ip}.scale" for ip in range(len(struct.phases))]
        scale_cov = (self.mtable.tables[h].physical_covariance(theta_h, s_h, corr_h,
                                                               scale_paths)
                     if s_h is not None else None)
        mult = [[len(op[0]) for op in cp.sites.ops] for cp in model.phases]
        wavelength = model.line_wavelengths[0] if model.line_wavelengths else None
        return compute_qpa(struct, values, scale_cov, mult, wavelength=wavelength)

    def _parameters(self, thetas, stderr, corr, at_bounds, esd0,
                    answer_runaway=()) -> list[RefinedParameter]:
        mt = self.mtable
        params: list[RefinedParameter] = []
        # The single-histogram rule (``refine._build_result``): a cell the
        # answer-producing stage's CELL_RUNAWAY names has its esd withheld,
        # and so does every path tied to it — asked of each histogram's own
        # table, because the ties are per table.  The finding scopes a
        # per-histogram path ``hist.h.…`` and names a shared one bare
        # (``_clamp_cell_runaway_multi``), so each table reads its own names.
        named = [p for d in answer_runaway for p in d.where]
        withheld = []
        for h, table in enumerate(mt.tables):
            prefix = f"hist.{h}."
            local = [p[len(prefix):] if p.startswith(prefix) else p for p in named
                     if p.startswith(prefix) or not p.startswith("hist.")]
            withheld.append(_cell_runaway_withheld(table, local))
        # The row path is the combined path — shared rows unprefixed,
        # per-histogram rows `hist.h.…` — which is exactly how
        # `MultiParameterTable.free_paths` spells them, so the projection keys
        # on the row path and needs no second naming convention (WP-1076).
        tested = set(mt.free_paths)
        on_bound = {p for f in at_bounds for p in f.paths}
        # shared parameters reported once, from histogram 0's covariance (its
        # diagonal esd is the true combined marginal — cross-terms with the
        # other histograms' columns do not enter a single path's variance).
        for e in mt.tables[0].entries:
            if mt.sharing.is_shared(e.path) and (e.vary or e.tie is not None):
                params.append(RefinedParameter(
                    path=e.path, value=e.value, vary=e.vary,
                    stderr=None if e.path in withheld[0] else esd0.get(e.path),
                    at_bound=(e.path in on_bound) if e.path in tested else None))
        for h, table in enumerate(mt.tables):
            cm = mt.col_map(h)
            esd = (table.stderr_physical(thetas[h], stderr[cm],
                                         corr[np.ix_(cm, cm)] if corr is not None else None)
                   if stderr is not None else {})
            for e in table.entries:
                if not mt.sharing.is_shared(e.path) and (e.vary or e.tie is not None):
                    row = f"hist.{h}.{e.path}"
                    params.append(RefinedParameter(
                        path=row, value=e.value, vary=e.vary,
                        stderr=None if e.path in withheld[h] else esd.get(e.path),
                        at_bound=(row in on_bound) if row in tested else None))
        return params

    def _top_diagnostics(self, outcome, correlation_guard, bg_scoped,
                         at_bounds) -> list[Diagnostic]:
        mt = self.mtable
        free = mt.free_paths
        report = GuardReport(background_correlations=bg_scoped)
        # the shared structure is the same object across histograms → check once
        report.nonpositive_adps = check_adp_positive_definite(mt.tables[0])
        if outcome.correlation is not None and len(free) > 1:
            c = np.asarray(outcome.correlation)
            for i in range(len(free)):
                for j in range(i + 1, len(free)):
                    if abs(c[i, j]) > correlation_guard:
                        report.high_correlations.append(
                            GuardFinding.correlation(free[i], free[j], c[i, j]))
        report.at_bounds = at_bounds
        return _guard_diagnostics(report) + _size_sharing_diagnostics(mt)


def _size_sharing_diagnostics(mtable) -> list[Diagnostic]:
    """``SIZE_NORMALISED_ACROSS_WAVELENGTHS`` — what a joint fit did to a size.

    An **info** row, and the WP-1076 shape is why it exists at all: before
    WP-1131 a joint fit of histograms at different wavelengths served one
    ``lor_size`` column to all of them, which is one specimen wearing as many
    crystallite sizes as it has wavelengths — the fit reported ``converged``,
    the cell came back right, and nothing named the cause.  Now the shared
    column is the coefficient at the reference wavelength and each histogram
    carries its own, so the finding is no longer a defect to warn about; it is
    an action to *state*, exactly as ``PHASE_UNCONSTRAINED`` states what was
    held.  A reader who does not know the coefficient was rescaled would read
    ``phases.0.lor_size`` as the number their second pattern shows.

    Silent unless there is something to say: no scaling declared (one
    histogram, equal wavelengths, or a source with no declared line), or every
    scaled term still sitting at zero, where the correction is 0.0 either way
    and naming it would be noise on every joint fit that never freed a width.
    """
    scales = getattr(mtable, "value_scales", None)
    if not scales or not any(scales):
        return []
    lams = [_longest_wavelength(ins) for ins in mtable.instruments]
    out: list[Diagnostic] = []
    ref = lams[0]
    for path in sorted(set().union(*(set(s) for s in scales))):
        values = [t.entries[t._paths[path]].value for t in mtable.tables
                  if path in t._paths]
        if not any(v != 0.0 for v in values):
            continue
        factors = [s.get(path, 1.0) for s in scales]
        term = path.rsplit(".", 1)[-1]
        power = "λ" if SIZE_LAMBDA_POWER[term] == 1.0 else "λ²"
        out.append(Diagnostic(
            level="info", code="SIZE_NORMALISED_ACROSS_WAVELENGTHS",
            where=[path], value=float(max(factors) / min(factors)),
            message=(
                f"{path} is a size term, which goes as {power}, and this joint "
                f"fit spans λ = {min(lams):.5g}-{max(lams):.5g} Å. The shared "
                f"column is therefore the coefficient at λ = {ref:.5g} Å "
                f"(histogram 0), and each histogram's own copy carries "
                f"{', '.join(f'{f:.4g}' for f in factors)}× it respectively: "
                f"{', '.join(f'{v:.6g}' for v in values)} deg"
                f"{'²' if term.startswith('gauss') else ''}. The specimen "
                f"quantity being shared is the crystallite size, not the "
                f"number of degrees — one number, {len(values)} coefficients"),
            suggestion=(
                "nothing to do: this is what makes one specimen one size across "
                "wavelengths, and a joint fit that shared the degrees instead "
                "would land the two histograms' implied sizes a factor "
                f"{max(lams) / min(lams):.4g} apart. Read the size rather than "
                "the coefficient (rietx.model.profiles.caglioti."
                "apparent_size_from_size_coefficient with each histogram's own "
                "λ — they agree by construction). To refine an independent size "
                "per histogram instead, say so: "
                'SharingMap(per_histogram=["phases.*.lor_size", '
                '"phases.*.gauss_size"])'),
        ))
    return out


def _unreached_histogram_diagnostics(stage_results: list[StageResult],
                                     labels: list[str]) -> list[Diagnostic]:
    """``STAGE_FREED_NOTHING`` — a histogram a stage's globs passed over.

    Issue #265's comment: on a joint fit, a plan written with
    ``instrument.profile.*`` freed four rows on the one constant-wavelength
    histogram and none on any bank, and the joint result said ``converged``
    at Rwp 0.115 where globs naming the banks' own rows gave 0.066. Nothing a
    single-histogram fit reports could have said it, because each bank's miss
    is only a miss *beside* the histogram the same glob did reach.

    ``info``, and read off ``StageResult.unreached_histograms``, which already
    excludes the deliberate cases (a scoped glob, a declined row) and the
    healthy one (a glob matching nowhere).  What remains can still be true and
    intended — a hump declared on one histogram is reached on one side only —
    so this states what the stage did and leaves the verdict to the caller.

    One diagnostic per **histogram**, naming every stage that passed it over
    and the globs that reached elsewhere, for :func:`_hold_diagnostics`'
    reason: a cumulative plan says the same thing stage after stage. ``where``
    is those globs, the thing a caller edits; ``value`` is the histogram's
    index.
    """
    by_hist: dict[int, dict[str, list[str]]] = {}
    for sr in stage_results:
        for h, globs in (sr.unreached_histograms or {}).items():
            by_hist.setdefault(h, {})[sr.name] = list(globs)
    out: list[Diagnostic] = []
    for h in sorted(by_hist):
        stages = by_hist[h]
        where = list(dict.fromkeys(g for globs in stages.values() for g in globs))
        label = labels[h] if h < len(labels) else f"hist{h}"
        names = ", ".join(repr(s) for s in stages)
        out.append(Diagnostic(
            level="info", code="STAGE_FREED_NOTHING",
            where=where, value=float(h),
            message=(f"stage{'' if len(stages) == 1 else 's'} {names} freed "
                     f"nothing in histogram {h} ({label}): "
                     f"{', '.join(where)} matched rows of another histogram "
                     "and none of this one, so its instrument parameters for "
                     "those stages kept their starting values"),
            suggestion=("if this histogram declares no such component, "
                        "nothing is wrong. Otherwise its parameters go by "
                        "other names: list them with "
                        f"[e.path for e in ref.mtable.tables[{h}].entries] "
                        "and add a glob that reaches them, or "
                        "scope the stage (hist.<k>.…) if one histogram was "
                        "the intent"),
        ))
    return out


def refine_multi(data: list[PatternData], structure: Structure,
                 instruments: list[Instrument], *,
                 plan: RefinementPlan | str = "mccusker_default",
                 sharing: SharingMap | None = None,
                 two_theta_limits=None,
                 weights: list[float] | None = None,
                 backend: str = "numpy", solver: str = "trf") -> RefinementResult:
    """One-shot joint refinement of ``structure`` against several ``data``/
    ``instruments`` pairs.  Functional wrapper over
    :class:`MultiHistogramRefinement`."""
    ref = MultiHistogramRefinement(structure, instruments, sharing=sharing,
                                   backend=backend, solver=solver)
    return ref.fit(data, plan=plan, two_theta_limits=two_theta_limits, weights=weights)
