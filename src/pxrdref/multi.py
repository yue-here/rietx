"""Multi-histogram joint refinement (WP-0308).

Refine one shared :class:`~pxrdref.schemas.structure.Structure` against several
patterns at once — different wavelengths, geometries or temperatures — each with
its own :class:`~pxrdref.schemas.instrument.Instrument`.  The histograms are
stacked into one residual (Von Dreele, 1997, J. Appl. Cryst. 30, 517): shared
structural parameters (cell, coordinates, occupancies, ADPs …) draw information
from every pattern, while each pattern keeps its own scale, background, zero and
resolution.  See :mod:`pxrdref.params.multi` for the parameter-sharing map and
:func:`pxrdref.optimize.least_squares.run_multi_least_squares` for the stacked
solve.

Rietveld mode only: Le Bail / Pawley intensities are per-pattern empirical
extractions, not shared quantities, so a multi-histogram fit of them is just
independent single fits — not the joint-residual point of this module.
"""

from __future__ import annotations

import numpy as np

from .backend.api import backend_dtype_note
from .model.forward import compile_model
from .optimize.least_squares import run_multi_least_squares
from .optimize.qpa import compute_qpa, microabsorption_diagnostics
from .optimize.statistics import background_absorption, compute_statistics
from .params.multi import MultiParameterTable, SharingMap
from .refine import (
    _VERSION,
    _absorption_diagnostics,
    _absorption_record,
    _guard_diagnostics,
    _resolve_capillary_mu_r,
    _utcnow,
)
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
    GuardReport,
    RefinementPlan,
    check_adp_positive_definite,
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


class MultiHistogramRefinement:
    """Joint Rietveld refinement of a shared structure against several patterns.

    ``instruments`` is one instrument per pattern; ``sharing`` (a
    :class:`~pxrdref.params.multi.SharingMap`) overrides the default
    instrument-vs-sample split.  After :meth:`fit`, :attr:`fitted_structures`
    and :attr:`fitted_instruments` hold the per-histogram refined models (their
    shared parameters are identical; scale, background, zero and resolution
    differ).
    """

    def __init__(self, structure: Structure, instruments: list[Instrument], *,
                 sharing: SharingMap | None = None, backend: str = "numpy"):
        if backend != "numpy":
            from .backend import resolve_backend

            try:
                resolve_backend(backend)  # fail fast with the install hint
            except ValueError as exc:
                raise NotImplementedError(str(exc)) from exc
        self._backend = backend
        instruments = list(instruments)
        if len(instruments) < 1:
            raise ValueError("multi-histogram needs at least one instrument")
        self.mtable = MultiParameterTable(structure, instruments, sharing=sharing)
        # Resolve each histogram's capillary µR from composition, exactly as the
        # single-histogram path does.  Without this a user who set
        # ``capillary_radius_mm`` here would silently get no absorption
        # correction and no diagnostic saying so — the failure mode WP-0501's
        # reporting exists to prevent.  µR is per *instrument* (each histogram
        # may be a different wavelength, hence a different µ) but the structure
        # is shared, which is what makes one loop correct.
        resolved = [_resolve_capillary_mu_r(structure, ins)
                    for ins in self.mtable.instruments]
        self._mu_r_source: list[str] = [src for src, _ in resolved]
        self._mu_r_skipped: list[str | None] = [why for _, why in resolved]
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
        models = None
        outcome = None
        for stage in plan.stages:
            freed = self.mtable.set_vary(stage.turn_on, True)
            if stage.seed:
                self.mtable.seed_softplus(freed, stage.seed)
            self.mtable.apply_to_models()
            models = [
                compile_model(s, ins, d, mode="rietveld", two_theta_limits=lim,
                              free_paths=set(tab.free_paths))
                for s, ins, d, lim, tab in zip(
                    self.mtable.structures, self.mtable.instruments, data, limits,
                    self.mtable.tables, strict=True)]
            outcome = run_multi_least_squares(models, self.mtable, weights=weights,
                                              max_iter=stage.max_iter,
                                              backend=self._backend)
            self.mtable.commit(outcome.theta)
            self.mtable.apply_to_models()
            stage_results.append(StageResult(
                name=stage.name, status=outcome.status,
                n_iterations=outcome.n_iterations,
                cost_initial=outcome.cost_initial, cost_final=outcome.cost_final,
                freed=freed))

        assert models is not None and outcome is not None
        self._models = models
        self.result_ = self._build_result(models, outcome, weights, plan.correlation_guard,
                                           stage_results)
        return self.result_

    # ------------------------------------------------------------------
    def _ticks(self, model, structure, values) -> dict[str, list[float]]:
        ticks: dict[str, list[float]] = {}
        for ip, cp in enumerate(model.phases):
            name = structure.phases[ip].name
            cell = tuple(values[f"phases.{ip}.cell.{k}"] for k in _CELL_KEYS)
            rows = [cp.reflections.two_theta(cell, lam) + values["instrument.zero_shift"]
                    for lam in model.line_wavelengths]
            pos = np.concatenate(rows) if rows else np.array([])
            ticks[name] = sorted(float(p) for p in pos if np.isfinite(p))
        return ticks

    def _build_result(self, models, outcome, weights, correlation_guard,
                      stage_results) -> RefinementResult:
        mt = self.mtable
        n = mt.n_histograms
        thetas = mt.split(outcome.theta)
        stderr = outcome.stderr_internal
        corr = outcome.correlation
        n_data = [len(m.tt) for m in models]
        data_off = np.concatenate([[0], np.cumsum(n_data)]).astype(int)

        # per-histogram slices ---------------------------------------------------
        per_values, per_ycalc, per_ybkg = [], [], []
        histograms: list[HistogramResult] = []
        top_bg: list[str] = []
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

            n_free_h = mt.n_shared + len(mt.per_hist_paths[h])
            stats = compute_statistics(model.y_obs, y_calc, model.sigma,
                                       n_free=n_free_h, y_background=y_bkg)
            qpa = self._histogram_qpa(h, model, struct, values, thetas[h], s_h, corr_h)

            diags: list[Diagnostic] = []
            j0, j1 = data_off[h], data_off[h] + n_data[h]
            if outcome.jac is not None and len(table.free_paths) > 1:
                jh = np.asarray(outcome.jac)[j0:j1][:, cm]
                for path, r2 in sorted(background_absorption(jh, table.free_paths).items(),
                                       key=lambda kv: -kv[1]):
                    if r2 > BACKGROUND_ABSORPTION_GUARD:
                        top_bg.append(f"hist.{h}.{path} (R²={r2:.2f})")
                        diags.extend(_guard_diagnostics(GuardReport(
                            background_correlations=[f"hist.{h}.{path} (R²={r2:.2f})"])))
            if qpa is not None:
                diags.extend(microabsorption_diagnostics(qpa))
            # specimen absorption, per histogram — each may sit at its own
            # wavelength and geometry, hence its own µR/µt.  Only the failure
            # modes are surfaced here; the applied value lives on
            # ``fitted_instruments[h]``.
            absorption = _absorption_record(model, self._mu_r_source[h],
                                            self._mu_r_skipped[h], values)
            if absorption is not None:
                diags.extend(_absorption_diagnostics(absorption))

            histograms.append(HistogramResult(
                label=model.meta.get("label", "") or f"hist{h}",
                weight=float(weights[h]), statistics=stats,
                two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
                y_calc=y_calc.tolist(), y_background=y_bkg.tolist(),
                sigma=model.sigma.tolist(),
                ticks=self._ticks(model, struct, values), qpa=qpa, diagnostics=diags))

        # pooled combined statistics (reported, never quoted alone) --------------
        combined = compute_statistics(
            np.concatenate([m.y_obs for m in models]),
            np.concatenate(per_ycalc),
            np.concatenate([m.sigma for m in models]),
            n_free=len(mt.free_paths),
            y_background=np.concatenate(per_ybkg))

        parameters = self._parameters(thetas, stderr, corr)
        diagnostics = self._top_diagnostics(outcome, correlation_guard, top_bg)

        weight_note = ("unit (each point's esd governs)"
                       if all(w == 1.0 for w in weights)
                       else ", ".join(f"hist{h}={w:g}" for h, w in enumerate(weights)))
        provenance = Provenance(
            package_version=_VERSION, created_utc=_utcnow(),
            backend=self._backend, dtype=backend_dtype_note(self._backend),
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
            qpa=histograms[0].qpa, histograms=histograms)

    def _histogram_qpa(self, h, model, struct, values, theta_h, s_h, corr_h):
        scale_paths = [f"phases.{ip}.scale" for ip in range(len(struct.phases))]
        scale_cov = (self.mtable.tables[h].physical_covariance(theta_h, s_h, corr_h,
                                                               scale_paths)
                     if s_h is not None else None)
        mult = [[len(op[0]) for op in cp.sites.ops] for cp in model.phases]
        wavelength = model.line_wavelengths[0] if model.line_wavelengths else None
        return compute_qpa(struct, values, scale_cov, mult, wavelength=wavelength)

    def _parameters(self, thetas, stderr, corr) -> list[RefinedParameter]:
        mt = self.mtable
        params: list[RefinedParameter] = []
        # shared parameters reported once, from histogram 0's covariance (its
        # diagonal esd is the true combined marginal — cross-terms with the
        # other histograms' columns do not enter a single path's variance).
        cm0 = mt.col_map(0)
        esd0 = (mt.tables[0].stderr_physical(thetas[0], stderr[cm0],
                                             corr[np.ix_(cm0, cm0)] if corr is not None else None)
                if stderr is not None else {})
        for e in mt.tables[0].entries:
            if mt.sharing.is_shared(e.path) and (e.vary or e.tie is not None):
                params.append(RefinedParameter(path=e.path, value=e.value,
                                               vary=e.vary, stderr=esd0.get(e.path)))
        for h, table in enumerate(mt.tables):
            cm = mt.col_map(h)
            esd = (table.stderr_physical(thetas[h], stderr[cm],
                                         corr[np.ix_(cm, cm)] if corr is not None else None)
                   if stderr is not None else {})
            for e in table.entries:
                if not mt.sharing.is_shared(e.path) and (e.vary or e.tie is not None):
                    params.append(RefinedParameter(path=f"hist.{h}.{e.path}",
                                                   value=e.value, vary=e.vary,
                                                   stderr=esd.get(e.path)))
        return params

    def _top_diagnostics(self, outcome, correlation_guard, bg_scoped) -> list[Diagnostic]:
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
                            f"{free[i]} ~ {free[j]} (ρ={c[i, j]:+.3f})")
        lo, hi = mt.bounds()
        for k, path in enumerate(free):
            t = outcome.theta[k]
            span = hi[k] - lo[k]
            tol = 1e-8 * (span if np.isfinite(span) else 1.0)
            if ((np.isfinite(lo[k]) and t - lo[k] <= tol)
                    or (np.isfinite(hi[k]) and hi[k] - t <= tol)):
                report.at_bounds.append(path)
        return _guard_diagnostics(report)


def refine_multi(data: list[PatternData], structure: Structure,
                 instruments: list[Instrument], *,
                 plan: RefinementPlan | str = "mccusker_default",
                 sharing: SharingMap | None = None,
                 two_theta_limits=None,
                 weights: list[float] | None = None) -> RefinementResult:
    """One-shot joint refinement of ``structure`` against several ``data``/
    ``instruments`` pairs.  Functional wrapper over
    :class:`MultiHistogramRefinement`."""
    ref = MultiHistogramRefinement(structure, instruments, sharing=sharing)
    return ref.fit(data, plan=plan, two_theta_limits=two_theta_limits, weights=weights)
