"""WP-2048 — a solve that meets a non-finite model ends its stage at the start.

The nightly's raise (``ValueError: array must not contain infs or NaNs`` out
of ``Refinement.fit``) came from two places a driver has no step left to
shorten: a Jacobian that is not finite at a point the driver accepted, and a
residual that is not finite where a solve begins.  Both are injected here, so
each row runs on every platform; the real trajectory that reaches them is a
rounding lottery (the slow row in ``test_cell_runaway_safety.py``).
"""

from __future__ import annotations

import dataclasses
import sys

import numpy as np
import pytest

import rietx.optimize.least_squares as lsq
from rietx import Refinement
from rietx.multi import MultiHistogramRefinement
from rietx.optimize.least_squares import run_least_squares, run_multi_least_squares
from rietx.schemas.instrument import BackgroundChebyshev, Instrument
from rietx.schemas.pattern import PatternData
from rietx.strategy.staged import RefinementPlan, Stage
from tests.test_cell_runaway_safety import (
    _LEBAIL_STAGES,
    ESCAPE,
    ESCAPED,
    _cubic_pair,
    _cubic_pair_pattern,
)
from tests.test_issue_283_cell_bounds import (
    _compile_alpha_only,
    _joint_alpha_only,
    _rhombohedral_boundary_cell,
)

SOLVERS = ("trf", "lm")
#: the residual builder as imported, before any row patches the seat
_REAL_MAKE_RESIDUAL = lsq._make_residual


def _nan_column_jacobian(after: int = 1):
    """A ``_jacobian_for`` whose closure returns the real Jacobian, then from
    call ``after`` on the same matrix with column 0 NaN."""
    real = lsq._jacobian_for

    def factory(model, table, backend, *args, **kwargs):
        inner = real(model, table, backend, *args, **kwargs)
        calls = {"n": 0}

        def jac(theta):
            j = np.array(inner(theta), dtype=np.float64)
            calls["n"] += 1
            if calls["n"] > after:
                j[:, 0] = np.nan
            return j
        return jac
    return factory


def _nan_residual(model, table, *args, **kwargs):
    """A ``_make_residual`` whose every evaluation is NaN."""
    inner = _REAL_MAKE_RESIDUAL(model, table, *args, **kwargs)

    def residual(theta):
        r = np.array(inner(theta), dtype=np.float64)
        r[0] = np.nan
        return r
    return residual


@pytest.mark.parametrize("solver", SOLVERS)
def test_a_non_finite_jacobian_stops_the_solve_at_its_start(monkeypatch, solver):
    """The second Jacobian, at a point the driver accepted, holds a NaN
    column: the solve hands back its own start and names the column."""
    structure = _rhombohedral_boundary_cell()
    structure.phases[0].cell.alpha.value = 119.0
    model, table = _compile_alpha_only(structure)
    x0 = table.x0().copy()
    monkeypatch.setattr(lsq, "_jacobian_for", _nan_column_jacobian(after=0))
    outcome = run_least_squares(model, table, max_iter=5, solver=solver)
    stop = outcome.non_finite
    assert stop is not None and stop.kind == "jacobian"
    assert stop.columns == ("phases.0.cell.alpha",)
    assert stop.free == tuple(table.free_paths)
    assert outcome.status == "diverged"
    assert outcome.termination == "non_finite_jacobian"
    assert np.array_equal(outcome.theta, x0)
    assert outcome.cost_final == outcome.cost_initial
    assert outcome.jac is None and outcome.stderr_internal is None


@pytest.mark.parametrize("solver", SOLVERS)
def test_a_non_finite_residual_at_the_start_stops_the_solve(monkeypatch, solver):
    """Both drivers refused this start with a ``ValueError``; the solve now
    returns it, unevaluated past the one residual."""
    structure = _rhombohedral_boundary_cell()
    structure.phases[0].cell.alpha.value = 119.0
    model, table = _compile_alpha_only(structure)
    x0 = table.x0().copy()
    monkeypatch.setattr(lsq, "_make_residual", _nan_residual)
    outcome = run_least_squares(model, table, max_iter=5, solver=solver)
    assert outcome.non_finite is not None
    assert outcome.non_finite.kind == "residual"
    assert outcome.non_finite.columns == ()
    assert outcome.termination == "non_finite_residual"
    assert outcome.n_iterations == 1
    assert np.array_equal(outcome.theta, x0)


@pytest.mark.parametrize("solver", SOLVERS)
def test_the_joint_solve_stops_the_same_way(monkeypatch, solver):
    """``run_multi_least_squares`` wires the same guard on the stacked
    Jacobian, and the same start check on the stacked residual."""
    structure = _rhombohedral_boundary_cell()
    structure.phases[0].cell.alpha.value = 119.0
    models, mtable = _joint_alpha_only(structure)
    x0 = mtable.x0().copy()
    real = lsq._multi_closures

    def closures(*args, **kwargs):
        residual, jacobian, n_data = real(*args, **kwargs)

        def jac(theta):
            j = np.array(jacobian(theta), dtype=np.float64)
            j[:, 0] = np.nan
            return j
        return residual, jac, n_data

    monkeypatch.setattr(lsq, "_multi_closures", closures)
    outcome = run_multi_least_squares(models, mtable, max_iter=5, backend="numpy",
                                      solver=solver)
    assert outcome.non_finite is not None
    assert outcome.non_finite.kind == "jacobian"
    assert outcome.non_finite.columns == ("phases.0.cell.alpha",)
    assert outcome.jacobian_layout is not None
    assert np.array_equal(outcome.theta, x0)


def _lebail_fit(solve_patch, stages=None):
    """``_cubic_pair`` under the Le Bail stages, with ``refine``'s solve seat
    replaced by ``solve_patch(real, model, table, **kwargs)`` and WP-1301's
    collapse patched off, as ``_fit_with_injected_escape`` does."""
    refine_module = sys.modules["rietx.refine"]
    real = refine_module.run_least_squares
    starts: list[tuple[str, dict[str, float], list[str]]] = []

    def solve(model, table, **kwargs):
        starts.append((kwargs.get("stage"), table.decode(table.x0()),
                       list(table.free_paths)))
        return solve_patch(real, model, table, **kwargs)

    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(3)
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(refine_module, "run_least_squares", solve)
        mp.setattr(refine_module, "_unsupported_phase_paths", lambda *a, **k: [])
        ref = Refinement(_cubic_pair(), ins, history=False)
        result = ref.fit(_cubic_pair_pattern(), mode="lebail",
                         plan=RefinementPlan(stages=list(stages or _LEBAIL_STAGES[:3]),
                                             closing_window_tol=None))
    return result, starts


def test_a_stage_whose_jacobian_is_not_finite_ends_at_its_start():
    """Through ``fit``: the ``cell`` stage meets a NaN column, comes back
    ``diverged`` with ``STAGE_NOT_FINITE``, and the next stage starts from the
    cell the ``cell`` stage started from."""
    def patch(real, model, table, **kwargs):
        if kwargs.get("stage") != "cell":
            return real(model, table, **kwargs)
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(lsq, "_jacobian_for", _nan_column_jacobian(after=1))
            return real(model, table, **kwargs)

    result, starts = _lebail_fit(patch)
    by_stage = {s.name: s for s in result.stages}
    assert by_stage["cell"].status == "diverged"
    found = [d for d in result.diagnostics if d.code == "STAGE_NOT_FINITE"]
    assert len(found) == 1
    stop = found[0]
    assert stop.level == "warning"
    assert "'cell'" in stop.message and "Jacobian column" in stop.message
    cell_free = next(free for name, _, free in starts if name == "cell")
    assert stop.where == cell_free
    assert stop.value == float(len(cell_free))
    before = next(v for name, v, _ in starts if name == "cell")
    after = next(v for name, v, _ in starts if name == "widths")
    for path in ("phases.0.cell.a", "phases.1.cell.a"):
        assert after[path] == before[path]
    assert np.isfinite(result.statistics.rwp)
    _plot(result, "non_finite_stage_jacobian")


def test_a_second_solve_starting_non_finite_puts_the_whole_stage_back():
    """The nudged start's second raise: the ``cell`` stage's first solve
    escapes (injected), the reset puts the cell back and buys a second solve,
    and that solve's start is not finite (injected).  Every path the first
    solve moved goes back to the stage's start, and both findings are said."""
    solves: dict[str, int] = {}

    def patch(real, model, table, **kwargs):
        stage = kwargs.get("stage")
        if stage != "cell":
            return real(model, table, **kwargs)
        solves[stage] = solves.get(stage, 0) + 1
        if solves[stage] == 1:
            outcome = real(model, table, **kwargs)
            table.commit(outcome.theta)
            entry = table.entries[table._paths[ESCAPED]]
            entry.value = ESCAPE * entry.value
            table.refresh_ties()
            return dataclasses.replace(outcome, theta=table.x0())
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(lsq, "_make_residual", _nan_residual)
            return real(model, table, **kwargs)

    result, starts = _lebail_fit(patch)
    assert solves["cell"] == 2, "the reset never bought a second solve"
    codes = {d.code for d in result.diagnostics}
    assert {"STAGE_NOT_FINITE", "CELL_RUNAWAY"} <= codes
    stop = next(d for d in result.diagnostics if d.code == "STAGE_NOT_FINITE")
    assert "where a solve began" in stop.message
    before = next(v for name, v, _ in starts if name == "cell")
    after = next(v for name, v, _ in starts if name == "widths")
    assert set(before) == set(after)
    moved = {p for p in before if after[p] != before[p]}
    assert not moved, sorted(moved)
    assert next(s for s in result.stages if s.name == "cell").status == "diverged"
    _plot(result, "non_finite_stage_second_solve")


def test_a_joint_stage_whose_jacobian_is_not_finite_ends_at_its_start(monkeypatch):
    """``multi.py``'s twin, through ``MultiHistogramRefinement.fit``."""
    structure = _rhombohedral_boundary_cell()
    structure.phases[0].cell.alpha.value = 119.0
    structure.phases[0].scale.value = 1e-3
    instruments, patterns = [], []
    for lam, lo, hi in ((1.5406, 10.0, 90.0), (0.7107, 5.0, 45.0)):
        ins = Instrument.debye_scherrer(wavelength=lam)
        ins.profile.w.value = 1e-2
        instruments.append(ins)
        tt = np.arange(lo, hi, 0.05)
        patterns.append(PatternData(two_theta=tt.tolist(),
                                    intensity=np.ones_like(tt).tolist()))
    real = lsq._multi_closures

    def closures(*args, **kwargs):
        residual, jacobian, n_data = real(*args, **kwargs)

        def jac(theta):
            j = np.array(jacobian(theta), dtype=np.float64)
            j[:, 0] = np.nan
            return j
        return residual, jac, n_data

    monkeypatch.setattr(lsq, "_multi_closures", closures)
    plan = RefinementPlan(stages=[
        Stage(name="cell", turn_on=["phases.0.cell.alpha"], max_iter=3)],
        closing_window_tol=None)
    result = MultiHistogramRefinement(structure, instruments).fit(patterns, plan=plan)
    assert result.stages[0].status == "diverged"
    stop = next(d for d in result.diagnostics if d.code == "STAGE_NOT_FINITE")
    assert "'cell'" in stop.message
    alpha = next(p for p in result.parameters if p.path == "phases.0.cell.alpha")
    assert alpha.value == 119.0


def _plot(result, name: str) -> None:
    """The fit's picture for inspection (tests/output/, gitignored)."""
    from pathlib import Path

    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / f"{name}.png"))
