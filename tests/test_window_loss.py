"""What a stage's frozen windows drop at its answer (WP-2047).

A stage sizes its peak windows when it compiles, so a peak that moves or
broadens during the solve spills past them.  ``forward.window_loss`` measures
the share of the Bragg intensity the frozen windows drop against windows sized
at the answer (``forward.rewindow``, no compile), each stage records it in
``StageResult.window_loss`` and its node's metrics, and ``STAGE_WINDOWS_STALE``
reports a stage past its own window tolerance.  The QPA round-robin chain
that ran away before WP-2045 is ``tests/test_acceptance_sequential.py``'s.
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import (
    CLOSING_WINDOW_TOL,
    WINDOW_AREA_TOL,
    compile_model,
    rewindow,
    window_loss,
)
from rietx.params.vector import ParameterTable
from rietx.refine import _window_loss_diagnostics
from rietx.schemas.results import StageResult
from rietx.strategy.staged import CLOSING_STAGE_NAME
from tests.test_refine_synthetic import perturbed_models, synthesize


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _axial(sl: float):
    structure, ins = perturbed_models()
    ins.geometry.axial_sl.value = sl
    ins.geometry.axial_hl.value = sl
    return structure, ins


def _values(structure, ins):
    t = ParameterTable(structure, ins)
    return t.decode(t.x0())


def _fresh_lost(model, structure, ins, pattern):
    """The authority: a full compile at the moved values."""
    v = _values(structure, ins)
    fresh = compile_model(structure, ins, pattern,
                          window_area_tol=model.window_area_tol, moving_paths=set())
    yf = np.asarray(model.bragg_component(v)).sum()
    yn = np.asarray(fresh.bragg_component(v)).sum()
    return 1.0 - yf / yn, v


@pytest.mark.parametrize("sl", [0.0, 0.03])
def test_rewindow_at_the_compiles_own_values_drops_nothing_new(pattern, sl):
    structure, ins = _axial(sl)
    model = compile_model(structure, ins, pattern, window_area_tol=WINDOW_AREA_TOL,
                          moving_paths=set())
    v = _values(structure, ins)
    assert abs(window_loss(model, v)) < 1e-4
    again = rewindow(model, v)
    # a new frozen model on the same reflections; the original is untouched
    assert again is not model and again.phases[0].reflections is model.phases[0].reflections
    assert again.phases[0].win is not model.phases[0].win


@pytest.mark.parametrize(("path", "to"), [
    ("instrument.profile.w", 2.0),      # every peak broadens past the slack
    ("instrument.geometry.axial_sl", 0.3),   # the axial tail, the documented sink
])
def test_a_grown_width_is_measured_as_a_fresh_compile_measures_it(pattern, path, to):
    structure, ins = _axial(0.03)
    model = compile_model(structure, ins, pattern, window_area_tol=WINDOW_AREA_TOL,
                          moving_paths=set())
    t = ParameterTable(structure, ins)
    t.entries[t._paths[path]].value = to
    t.refresh_ties()
    t.apply_to_models(structure, ins)
    lost, v = _fresh_lost(model, structure, ins, pattern)
    loss = window_loss(model, v)
    assert loss > WINDOW_AREA_TOL
    assert loss == pytest.approx(lost, abs=1e-3)


def _stage(loss, tol=None, name="s"):
    return StageResult(name=name, status="converged", n_iterations=1,
                       cost_initial=1.0, cost_final=1.0, window_area_tol=tol,
                       window_loss=loss)


@pytest.mark.parametrize(("loss", "tol", "fires"), [
    (0.03, None, True), (0.015, None, False), (None, None, False), (-0.2, None, False),
    (2e-3, CLOSING_WINDOW_TOL, True), (5e-4, CLOSING_WINDOW_TOL, False)])
def test_the_code_fires_past_the_stages_own_tolerance(loss, tol, fires):
    fired = _window_loss_diagnostics([_stage(loss, tol)])
    assert [d.value for d in fired] == ([loss] if fires else [])
    assert all(d.code == "STAGE_WINDOWS_STALE" and d.level == "warning"
               and d.suggestion for d in fired)


def test_only_the_stages_whose_answer_reaches_the_result_are_reported():
    """An earlier stage is refitted on fresh windows by every stage after it,
    so its loss is recorded and not reported; the last declared stage, which
    only the closing stage refits, is."""
    closing = _stage(0.0, CLOSING_WINDOW_TOL, name=CLOSING_STAGE_NAME)
    early = [_stage(0.12, name="sample_profile"), _stage(0.0, name="biso")]
    assert _window_loss_diagnostics([*early, closing]) == []
    last = [_stage(0.0, name="profile"), _stage(0.73, name="warm")]
    assert [d.value for d in _window_loss_diagnostics([*last, closing])] == [0.73]
    # without a closing stage, the last stage alone
    assert [d.value for d in _window_loss_diagnostics(last)] == [0.73]
    assert _window_loss_diagnostics(early) == []


def test_a_fit_records_each_stages_loss_and_its_node_carries_it(pattern):
    structure, ins = _axial(0.03)
    ref = rx.Refinement(structure, ins)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=40),
        rx.Stage("cell", ["phases.*.cell.*", "phases.*.scale"], max_iter=40)])
    result = ref.fit(pattern, plan=plan)
    losses = [s.window_loss for s in result.stages]
    assert len(losses) == 3 and all(x is not None for x in losses)
    assert all(abs(x) < WINDOW_AREA_TOL for x in losses)
    assert "STAGE_WINDOWS_STALE" not in {d.code for d in result.diagnostics}
    nodes = [n for n in ref.history.nodes.values() if n.action.kind == "stage"]
    assert [n.metrics.window_loss for n in nodes] == losses
    # and a hand-run stage records it the same way
    out = ref.run_stage(pattern, rx.Stage("again", ["phases.*.scale"]))
    assert out.stages[-1].window_loss is not None
    assert ref.history[out.node_id].metrics.window_loss == out.stages[-1].window_loss


@pytest.mark.parametrize("closing", [False, True])
@pytest.mark.parametrize(("sl", "hl"), [(0.02, 0.02), (0.05, 0.0), (0.3, 0.1), (0.0, 0.0)])
def test_the_vectorised_node_count_is_the_compiles(sl, hl, closing):
    """``fcj_node_counts`` (rewindow's) gives the integers ``fcj_node_count``
    (the compile's) gives, over 2θ from 5 to 160° and FWHM from 0.005 to 2°,
    the ceiling and the skip test included."""
    from rietx.model.profiles.fcj import fcj_node_count, fcj_node_counts
    tt, fw = np.meshgrid(np.linspace(5.0, 160.0, 97), np.geomspace(0.005, 2.0, 41))
    got = fcj_node_counts(tt.ravel(), fw.ravel(), sl, hl, closing=closing)
    want = [fcj_node_count(float(a), float(b), sl, hl, closing=closing)
            for a, b in zip(tt.ravel(), fw.ravel(), strict=True)]
    assert got.tolist() == want


@pytest.mark.parametrize("tol", [WINDOW_AREA_TOL, 1e-2, CLOSING_WINDOW_TOL, 5e-5])
def test_the_tabled_window_multiple_is_the_compiles(tol):
    """``window_fwhm_mult_interp`` (rewindow's) is within 2e-5 of
    ``window_fwhm_mult`` (the compile's), relative, over η uniform on [0, 1]
    and log-uniform down to 1e-9, where k turns at η ~ tol (WP-2051)."""
    from rietx.model.forward import window_fwhm_mult, window_fwhm_mult_interp
    rng = np.random.default_rng(0)
    eta = np.concatenate([rng.random(2000), 10.0 ** rng.uniform(-9.0, 0.0, 2000),
                          [0.0, 1.0]])
    want = window_fwhm_mult(eta, tol)
    assert np.max(np.abs(window_fwhm_mult_interp(eta, tol) / want - 1.0)) < 2e-5
