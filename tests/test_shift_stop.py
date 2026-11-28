"""The last stage stops on the undamped shift over its esd (WP-2317 R6).

The driver's half (the reading, the stop, a crawl that does not pass) is
``tests/test_lm_solver.py``'s; the seam that hands the test to the endpoints
alone is ``tests/test_solver_seam.py``'s.  This file holds the plan's half:
the field, its schedule, its refusals, the presets and protocols that keep
1e-9, and what a fit, a hand-run stage and a cherry-pick record.
"""
from __future__ import annotations

import pytest

import rietx as rx
import rietx.optimize.lm as lm
from rietx.optimize.statistics import MAX_SHIFT_CONVERGED
from rietx.schemas.plan import SHIFT_OVER_ESD_TOL, PlanSpec
from rietx.strategy.refit import _collapse
from rietx.strategy.staged import CLOSING_STAGE_NAME
from tests.test_refine_synthetic import perturbed_models, synthesize

SHORT = [
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=40),
    rx.Stage("cell", ["phases.*.cell.*", "phases.*.scale"], max_iter=40),
]


def _plan(**kw) -> rx.RefinementPlan:
    return rx.RefinementPlan(stages=[rx.Stage(**vars(s)) for s in SHORT], **kw)


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture(scope="module")
def fitted(pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    return ref, ref.fit(pattern, plan=_plan())


def test_the_stop_quotes_the_convergence_band_the_report_reads():
    # one number, McCusker et al. (1999) §7, on both sides of the fit
    assert SHIFT_OVER_ESD_TOL == MAX_SHIFT_CONVERGED == 0.1
    assert rx.RefinementPlan(stages=[]).shift_over_esd_tol == SHIFT_OVER_ESD_TOL
    assert PlanSpec().shift_over_esd_tol == SHIFT_OVER_ESD_TOL


def test_the_endpoints_alone_take_the_shift_test():
    # an intermediate stage seeds the next, so it stops on its ftol
    assert _plan().stage_shift_tols() == [None, 0.1]
    # the closing stage is an endpoint too
    closed = _plan(closing_window_tol=1e-3)
    assert [s.name for s in closed.run_stages()][-1] == CLOSING_STAGE_NAME
    assert closed.stage_shift_tols() == [None, 0.1, 0.1]
    # a stage's own ftol is the stop it asked for, and the closing stage copies it
    own = rx.RefinementPlan(stages=[SHORT[0], rx.Stage("cell", SHORT[1].turn_on, ftol=1e-12)],
                            closing_window_tol=1e-3)
    assert own.stage_shift_tols() == [None, None, None]
    assert rx.RefinementPlan(stages=[SHORT[0]]).stage_shift_tols() == [0.1]
    assert _plan(shift_over_esd_tol=None).stage_shift_tols() == [None, None]
    assert _plan(shift_over_esd_tol=0.05).stage_shift_tols() == [None, 0.05]
    # parallel to the other two schedules
    assert len(closed.stage_shift_tols()) == len(closed.stage_ftols()) \
        == len(closed.stage_window_tols())


@pytest.mark.parametrize("bad", [0.0, -0.1, float("nan"), float("inf"), True, "0.1"])
def test_a_shift_that_cannot_be_met_is_refused_where_it_is_read(bad, fitted, pattern):
    with pytest.raises(ValueError, match="shift_over_esd_tol"):
        PlanSpec(stages=[], shift_over_esd_tol=bad)
    with pytest.raises(ValueError, match="shift_over_esd_tol"):
        _plan(shift_over_esd_tol=bad).stage_shift_tols()
    ref, _ = fitted
    with pytest.raises(ValueError, match="shift_over_esd_tol"):
        ref.run_stage(pattern, rx.Stage("polish", ["phases.*.scale"]),
                      shift_over_esd_tol=bad)


def test_the_field_round_trips_and_survives_the_series_collapse():
    for tol in (0.05, None):
        plan = _plan(shift_over_esd_tol=tol)
        spec = PlanSpec.from_plan(plan)
        assert spec.shift_over_esd_tol == tol
        assert PlanSpec.model_validate_json(spec.model_dump_json()).to_plan() == plan
        # a warm series refit is the compressed plan, and stops as it does
        assert _collapse(plan).shift_over_esd_tol == tol


def test_the_calibration_preset_keeps_the_tight_stop():
    # WP-2222's first compounding place: a held instrument carries the
    # calibration's error into every later fit
    assert rx.RefinementPlan.lab_calibrate().shift_over_esd_tol is None
    assert rx.RefinementPlan.mccusker_default().shift_over_esd_tol == SHIFT_OVER_ESD_TOL


def test_a_fit_records_the_stop_each_stage_ran(fitted):
    ref, result = fitted
    assert [s.shift_over_esd_tol for s in result.stages] == [None, 0.1]
    nodes = [n for n in ref.history.nodes.values() if n.action.kind == "stage"]
    assert [n.action.shift_over_esd_tol for n in nodes[-2:]] == [None, 0.1]
    # the default prints nothing, so a plain stage's script line is unchanged
    assert "shift_over_esd_tol" not in nodes[-1].action.api_call()
    # the trials a report runs on the caller's behalf stop as the fit did
    assert ref._plan_settings["shift_over_esd_tol"] == 0.1


def test_run_stage_defaults_to_the_shift_test_and_records_what_it_ran(fitted, pattern):
    ref, _ = fitted
    stage = rx.Stage("polish", ["phases.*.scale"])
    out = ref.run_stage(pattern, stage)
    assert ref.history[out.node_id].action.shift_over_esd_tol == SHIFT_OVER_ESD_TOL

    out = ref.run_stage(pattern, stage, shift_over_esd_tol=None)
    action = ref.history[out.node_id].action
    assert action.shift_over_esd_tol is None
    assert action.api_call().endswith("shift_over_esd_tol=None)")
    assert ref._plan_settings["shift_over_esd_tol"] is None

    # a stage's own ftol switches the test off, and the line says nothing of it
    out = ref.run_stage(pattern, rx.Stage("polish", ["phases.*.scale"], ftol=1e-12))
    action = ref.history[out.node_id].action
    assert action.shift_over_esd_tol is None
    assert "shift_over_esd_tol" not in action.api_call()

    # a cherry-pick replays what the node ran, never the keyword's default
    tight = ref.run_stage(pattern, stage, shift_over_esd_tol=None)
    picked = ref.cherry_pick(tight.node_id, pattern)
    assert ref.history[picked.node_id].action.shift_over_esd_tol is None


def test_a_profile_interval_refits_to_the_solvers_own_stop(fitted, pattern, monkeypatch):
    # the settle test reads chi2 to a hundredth of the threshold, finer than a
    # stop at a tenth of each esd promises, so every refit runs at 1e-9
    ref, _ = fitted
    ref.run_stage(pattern, rx.Stage("cell", SHORT[1].turn_on))
    assert ref._plan_settings["shift_over_esd_tol"] == SHIFT_OVER_ESD_TOL
    seen = []
    original = lm.minimize

    def spy(*args, **kwargs):
        seen.append(kwargs.get("shift_tol"))
        return original(*args, **kwargs)

    monkeypatch.setattr(lm, "minimize", spy)
    interval = ref.profile_interval(pattern, "phases.0.cell.a", max_refits=6)
    assert seen and set(seen) == {None}
    assert interval is not None
