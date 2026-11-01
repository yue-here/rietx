"""A result's statistics and curves come from a compile at its own values (#272).

A stage's compile freezes its windows and FCJ node counts at the values the
stage *started* from, so a fit whose last stage moves a window-sizing
parameter used to report numbers measured on that start-of-stage compile.
``Refinement._final_compile`` measures the result on one more compile at the
returned values instead, and ``FROZEN_COMPILE_STALE`` says when the two
differ by more than ``FROZEN_COMPILE_CHI2_REL``.

The fixture is synthetic: the LaB6 pattern of ``test_refine_synthetic``, with
``w`` started at a tenth of its truth and the zero at -0.05° (truth 0.008°),
both freed in the last stage, so its windows were sized for lines too narrow
and in the wrong place: 1.65e-2 relative χ², above the 1e-2 threshold.
"""

from __future__ import annotations

import functools

import numpy as np
import pytest

import rietx as rx
import tests.test_refine_synthetic as synthetic
from rietx.model import forward as fwd
from rietx.model.forward import compile_model, recorded_window_tol
from rietx.params.vector import ParameterTable
from rietx.refine import FROZEN_COMPILE_CHI2_REL
from tests.test_refine_synthetic import TRUE_W, perturbed_models, synthesize


def _plan(closing_window_tol: float | None = None) -> rx.RefinementPlan:
    """No closing stage by default here: it starts at the answer, so its frozen
    compile is the result's and the finding below has nothing to say."""
    common = ["phases.*.scale", "instrument.background.*"]
    return rx.RefinementPlan(stages=[
        rx.Stage("scale", common),
        rx.Stage("all", common + ["instrument.profile.w",
                                  "instrument.zero_shift", "phases.*.cell.a"]),
    ], closing_window_tol=closing_window_tol)


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture(scope="module")
def declared_pattern():
    """``synthesize()``'s LaB6, drawn at the declared stages' windows.

    The subject below is a declared last stage's frozen compile, so the data
    carry the windows that stage fits with.  Drawn at the closing stage's 1e-3
    (``synthesize``'s own compile since WP-2002), the tails no declared compile
    models add a floor to both χ², and the finding's ratio falls from 1.65e-2
    to 6.4e-3, under its 1e-2 threshold.
    """
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(synthetic, "compile_model", functools.partial(
            fwd.compile_model, window_area_tol=fwd.WINDOW_AREA_TOL))
        return synthesize()


@pytest.fixture(scope="module")
def narrow_start(declared_pattern):
    structure, instrument = perturbed_models()
    instrument.profile.w.value = TRUE_W / 10
    instrument.zero_shift.value = -0.05
    ref = rx.Refinement(structure, instrument)
    return ref, ref.fit(declared_pattern, plan=_plan())


def _chi2(model, values) -> float:
    r = (model.y_obs - model.evaluate(values)) / model.sigma
    return float(r @ r)


def _rebuild(ref, pattern, result):
    """What a reader does: compile the fitted models, claiming every row the
    result reports as refined or tied as moving, as the last stage did."""
    moving = {p.path for p in result.parameters}
    # and at the windows the answer stage ran at, which the result records:
    # None for a declared stage, which ran at WINDOW_AREA_TOL (WP-2002)
    model = compile_model(
        ref.fitted_structure, ref.fitted_instrument, pattern, moving_paths=moving,
        window_area_tol=recorded_window_tol(result.stages[-1].window_area_tol))
    table = ParameterTable(ref.fitted_structure, ref.fitted_instrument)
    return model, table.decode(table.x0())


def test_the_reported_chi2_is_reproduced_by_a_compile_at_the_result(
        narrow_start, declared_pattern):
    ref, result = narrow_start
    model, values = _rebuild(ref, declared_pattern, result)
    stats = result.statistics
    reported = stats.chi2 * (stats.n_points - stats.n_free_parameters)
    assert _chi2(model, values) == pytest.approx(reported, rel=1e-10)
    np.testing.assert_allclose(result.y_calc, model.evaluate(values),
                               rtol=1e-12, atol=1e-9)


def test_the_finding_names_the_frozen_figure_when_the_windows_mattered(
        narrow_start):
    _, result = narrow_start
    hits = [d for d in result.diagnostics if d.code == "FROZEN_COMPILE_STALE"]
    assert len(hits) == 1
    hit = hits[0]
    assert hit.level == "info"
    assert hit.value > FROZEN_COMPILE_CHI2_REL
    assert "frozen" in hit.message and "chi2" in hit.message


def test_the_history_node_keeps_its_as_optimised_metrics(narrow_start):
    """The node records what the solver saw; only the result is re-measured,
    so the two differ by the finding's own fraction."""
    ref, result = narrow_start
    node = ref.history.nodes[result.node_id]
    frozen = node.metrics.statistics.chi2
    rel = next(d.value for d in result.diagnostics
               if d.code == "FROZEN_COMPILE_STALE")
    # one n and one n_free, so the reduced χ² carry the finding's ratio
    assert abs(result.statistics.chi2 - frozen) / frozen == pytest.approx(
        rel, rel=1e-9)


def test_the_closing_stage_leaves_no_stale_figure(pattern):
    """The same start under the shipped closing stage (WP-2002): it recompiles at
    the answer, so the result's compile and the solve's agree, and the rebuild
    reproduces the result at the windows the result records."""
    structure, instrument = perturbed_models()
    instrument.profile.w.value = TRUE_W / 10
    instrument.zero_shift.value = -0.05
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(pattern, plan=_plan(closing_window_tol=1e-3))
    assert result.stages[-1].window_area_tol == 1e-3
    assert not [d for d in result.diagnostics if d.code == "FROZEN_COMPILE_STALE"]
    model, values = _rebuild(ref, pattern, result)
    stats = result.statistics
    reported = stats.chi2 * (stats.n_points - stats.n_free_parameters)
    assert _chi2(model, values) == pytest.approx(reported, rel=1e-10)


def test_a_result_is_silent_when_the_windows_did_not_matter(pattern):
    """Last stage frees nothing that sizes a window: the two compiles agree."""
    structure, instrument = perturbed_models()
    instrument.profile.w.value = TRUE_W
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.*"])],
        closing_window_tol=None))
    assert not [d for d in result.diagnostics
                if d.code == "FROZEN_COMPILE_STALE"]


def test_run_stage_reports_from_the_fresh_compile_too(pattern):
    structure, instrument = perturbed_models()
    instrument.profile.w.value = TRUE_W / 10
    ref = rx.Refinement(structure, instrument, history=False)
    result = ref.run_stage(pattern, rx.Stage(
        "all", ["phases.*.scale", "instrument.background.*",
                "instrument.profile.w", "instrument.zero_shift",
                "phases.*.cell.a"]))
    model, values = _rebuild(ref, pattern, result)
    stats = result.statistics
    reported = stats.chi2 * (stats.n_points - stats.n_free_parameters)
    assert _chi2(model, values) == pytest.approx(reported, rel=1e-10)
