"""The movement slack a stage sizes from what it frees (WP-2317, ruling R7).

``forward.WINDOW_MOVE_FWHM`` gives each window room for the position families
a stage can move, and the staged runner refits a stage once on fresh windows
when its frozen ones dropped more than its window fraction at its answer.
The real-data movement measurements are ``tests/test_window_domain.py``'s.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
import rietx.model.forward as fwd
from rietx.params.vector import ParameterTable
from rietx.schemas.plan import CLOSING_WINDOW_TOL
from tests.test_refine_synthetic import perturbed_models, synthesize

refine_mod = importlib.import_module("rietx.refine")


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _plot(result, name):
    """obs/calc/diff to ``tests/output/`` (``tests/CLAUDE.md``)."""
    from rietx.viz.plots import plot_result
    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / name))
    import matplotlib.pyplot as plt
    plt.close("all")


def _halves(model):
    """Each phase's window half-widths in points, line 0."""
    return [np.asarray(cp.win[0, :, 1] - cp.win[0, :, 0]) for cp in model.phases]


def _compile(pattern, moving, **kw):
    structure, ins = perturbed_models()
    return fwd.compile_model(structure, ins, pattern, moving_paths=moving,
                             window_area_tol=fwd.WINDOW_AREA_TOL, movement_slack=True, **kw)


def test_a_stage_moving_no_position_has_half_a_step_of_slack(pattern):
    """A stage freeing scale and background can move no peak, so its windows
    are k(η)·Γ and half the point step: narrower than the uniform slack's,
    and at most one point a side wider than a declared slack of zero."""
    none = _compile(pattern, {"phases.0.scale"})
    zero = _compile(pattern, {"phases.0.scale"}, window_slack_deg=0.0)
    old = _compile(pattern, None)
    for a, b, c in zip(none.phases, zero.phases, old.phases, strict=True):
        assert a.window_slack_shape is not None and not a.window_slack_shape.any()
        grow = (b.win[..., 0] - a.win[..., 0], a.win[..., 1] - b.win[..., 1])
        assert all(((g >= 0) & (g <= 1)).all() for g in grow)
        assert (a.win[..., 1] - a.win[..., 0]).sum() < (c.win[..., 1] - c.win[..., 0]).sum()


def test_a_compile_making_no_claim_keeps_the_uniform_slack(pattern):
    """``moving_paths=None`` (a plot, a predict) is the old uniform slack."""
    m = _compile(pattern, None)
    u = _compile(pattern, None, window_slack_deg=fwd.WINDOW_MIN_DEG)
    for a, b in zip(m.phases, u.phases, strict=True):
        assert a.window_slack_shape is None
        assert np.array_equal(a.win, b.win)


def test_each_family_follows_its_shape_and_the_sum_is_capped():
    """The zero is flat, displacement goes as cos θ, the cell as tan θ, each
    scaled to 1 at the reflection in range it moves most; the slack is
    WINDOW_MOVE_FWHM·Γ times their sum plus half the point step, never past
    WINDOW_MIN_DEG."""
    theta = np.array([10.0, 30.0, 60.0])
    ok = np.ones(3, dtype=bool)
    assert np.allclose(fwd.window_slack_shape(("zero",), theta, ok), 1.0)
    cos = np.cos(np.radians(theta))
    assert np.allclose(fwd.window_slack_shape(("displacement",), theta, ok), cos / cos[0])
    tan = np.tan(np.radians(theta))
    assert np.allclose(fwd.window_slack_shape(("strain",), theta, ok), tan / tan[-1])
    both = fwd.window_slack_shape(("zero", "strain"), theta, ok)
    assert np.allclose(both, 1.0 + tan / tan[-1])
    gamma = np.array([0.01, 0.05, 0.2])
    half = fwd.grid_half_step(np.array([0.0, 0.01, 0.03]), np.array([0.005, 0.02, 5.0]))
    assert np.allclose(half, [0.005, 0.0075, 0.01])
    slack = fwd.movement_slack_deg(both, gamma, half)
    assert np.allclose(slack, np.minimum(fwd.WINDOW_MIN_DEG,
                                         fwd.WINDOW_MOVE_FWHM * gamma * both + half))
    assert slack[-1] == fwd.WINDOW_MIN_DEG


def test_the_families_are_read_off_moving_paths():
    """A free cell is its own phase's strain, a free wavelength every phase's,
    and an aberration counts only on its own geometry."""
    fam = fwd.moving_position_families
    assert fam(None, 0, "bragg_brentano") is None
    assert fam(set(), 0, "bragg_brentano") == ()
    assert fam({"phases.1.cell.a"}, 0, "bragg_brentano") == ()
    assert fam({"phases.0.cell.a"}, 0, "bragg_brentano") == ("strain",)
    assert fam({"instrument.source.lines.0.wavelength"}, 3, "bragg_brentano") == ("strain",)
    assert fam({"instrument.zero_shift", "instrument.geometry.sample_displacement"},
               0, "bragg_brentano") == ("zero", "displacement")
    assert fam({"instrument.geometry.sample_displacement"}, 0, "debye_scherrer") == ()


def test_a_shift_equation_keeps_the_uniform_slack(pattern):
    """A peak a shift equation moves has a reach the families do not describe."""
    structure, ins = perturbed_models()
    ins.peak_equations = [rx.PeakEquation(target="shift", expression="c0",
                                          coefficients={"c0": rx.Parameter(value=0.0)})]
    m = fwd.compile_model(structure, ins, pattern, moving_paths={"phases.0.scale"},
                          movement_slack=True)
    assert all(cp.window_slack_shape is None for cp in m.phases)


def test_rewindow_reapplies_the_compiles_rule(pattern):
    """``window_sizing`` at the compile's own values reproduces its windows."""
    structure, ins = perturbed_models()
    moving = {"instrument.zero_shift", "phases.0.cell.a"}
    m = fwd.compile_model(structure, ins, pattern, moving_paths=moving,
                          window_area_tol=fwd.WINDOW_AREA_TOL, movement_slack=True)
    t = ParameterTable(structure, ins)
    loss = fwd.window_loss(m, t.decode(t.x0()))
    assert loss is not None and abs(loss) < 1e-3


def test_a_stage_past_its_window_tolerance_refits_once(pattern, monkeypatch):
    """The first solve's loss passes the tolerance, so the stage solves once
    more on fresh windows and records the loss that triggered it; the record
    is one stage with both solves' iterations, and one ``stage_end``."""
    real = refine_mod.window_loss
    calls = []

    def first_stale(model, values):
        calls.append(1)
        return 0.5 if len(calls) == 1 else real(model, values)

    monkeypatch.setattr(refine_mod, "window_loss", first_stale)
    solves = []
    real_lsq = refine_mod.run_least_squares

    def counting(*a, **k):
        out = real_lsq(*a, **k)
        solves.append(out.n_iterations)
        return out

    monkeypatch.setattr(refine_mod, "run_least_squares", counting)
    ends = []
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    res = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell", ["phases.*.scale", "phases.*.cell.*"], max_iter=40)]),
        events=lambda e: ends.append(e["data"]) if e["kind"] == "stage_end" else None)
    _plot(res, "window_slack_refit_once.png")
    (stage,) = res.stages
    assert stage.window_refit_loss == 0.5
    assert stage.window_loss is not None and stage.window_loss < 0.5
    assert len(solves) == 2 and stage.n_iterations == sum(solves)
    assert len(ends) == 1 and ends[0]["window_refit_loss"] == 0.5


def test_a_declared_slack_is_never_refitted(pattern, monkeypatch):
    """A caller's ``window_slack_deg`` keeps the caller's windows."""
    monkeypatch.setattr(refine_mod, "window_loss", lambda model, values: 0.5)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    res = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell", ["phases.*.scale", "phases.*.cell.*"], max_iter=40,
                 window_slack_deg=0.3)]))
    _plot(res, "window_slack_declared.png")
    assert res.stages[0].window_refit_loss is None


def test_only_a_stage_a_later_one_refits_sizes_its_slack(pattern, monkeypatch):
    """The answer stage keeps the uniform slack, whose tail room is in the
    esds a result reports; every earlier stage sizes it from what it frees.
    A fresh compile at the answer never does."""
    real = refine_mod.compile_model
    asked = []

    def recording(*a, **k):
        # only a stage compile names the flag; every other compile omits it
        asked.append(k.get("movement_slack"))
        return real(*a, **k)

    monkeypatch.setattr(refine_mod, "compile_model", recording)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    res = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale"], max_iter=20),
        rx.Stage("cell", ["phases.*.scale", "phases.*.cell.*"], max_iter=40)]))
    _plot(res, "window_slack_two_stages.png")
    stage_compiles = [x for x in asked if x is not None]
    assert stage_compiles[0] is True and stage_compiles[-1] is False
    assert stage_compiles.count(False) == 1


def test_a_stage_a_later_turn_off_leaves_final_keeps_the_uniform_slack(pattern, monkeypatch):
    """A later stage existing is not a later stage refitting: here the second
    stage fixes the cell the first freed, so the first stage's cell is the
    answer, and its windows keep the uniform slack's tail room."""
    real = refine_mod.compile_model
    asked = []

    def recording(*a, **k):
        asked.append(k.get("movement_slack"))
        return real(*a, **k)

    monkeypatch.setattr(refine_mod, "compile_model", recording)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=True)
    res = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell", ["phases.*.scale", "phases.*.cell.*"], max_iter=40),
        rx.Stage("scale", ["phases.*.scale"], turn_off=["phases.*.cell.*"],
                 max_iter=20)]))
    _plot(res, "window_slack_turned_off.png")
    stage_compiles = [x for x in asked if x is not None]
    assert stage_compiles and not any(stage_compiles)
    # and the history says so, so a replay compiles the same windows
    actions = [ref.history.nodes[i].action for i in ref.history.order]
    assert [a.movement_slack for a in actions if a.kind == "stage"] == [False, False]


@pytest.mark.parametrize("fix_cell, expected", [
    (False, [True, True, False]),
    # the closing stage fixes what a declared turn_off left fixed at the end,
    # so the cell stage's answer for the cell is final there too
    (True, [False, True, False]),
])
def test_the_closing_stage_refits_what_the_plan_leaves_free(pattern, monkeypatch,
                                                          fix_cell, expected):
    real = refine_mod.compile_model
    asked = []

    def recording(*a, **k):
        asked.append(k.get("movement_slack"))
        return real(*a, **k)

    monkeypatch.setattr(refine_mod, "compile_model", recording)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    res = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell", ["phases.*.scale", "phases.*.cell.*"], max_iter=40),
        rx.Stage("scale", ["phases.*.scale"], max_iter=20,
                 turn_off=["phases.*.cell.*"] if fix_cell else [])],
        closing_window_tol=CLOSING_WINDOW_TOL))
    assert len(res.stages) == 3
    assert [x for x in asked if x is not None] == expected


def test_a_stage_no_better_on_fresh_windows_is_not_re_solved(pattern, monkeypatch):
    """An answer that fits the data no better than the stage's start, each on
    windows sized there, fitted its windows' loss: the stage keeps it and its
    loss rather than polishing the walk (the Le Bail +2 % start's runaway)."""
    monkeypatch.setattr(refine_mod, "window_loss", lambda model, values: 0.5)
    monkeypatch.setattr(refine_mod, "_improved_on_fresh_windows",
                        lambda model, found, answer: False)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    res = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell", ["phases.*.scale", "phases.*.cell.*"], max_iter=40)]))
    (stage,) = res.stages
    assert stage.window_refit_loss is None and stage.window_loss == 0.5


def test_the_fresh_window_test_reads_the_start_on_its_own_windows(pattern):
    """The real test, both ways, on the synthetic fit: a cell answer is better
    than the perturbed start, and the start is not better than itself."""
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    table = ParameterTable(structure, ins)
    start = table.decode(table.x0())
    model = refine_mod.compile_model(structure, ins, pattern)
    res = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("cell", ["phases.*.scale", "phases.*.cell.*"], max_iter=40)]))
    answer = dict(start, **{p.path: p.value for p in res.parameters})
    assert refine_mod._improved_on_fresh_windows(model, start, answer)
    assert not refine_mod._improved_on_fresh_windows(model, start, start)
