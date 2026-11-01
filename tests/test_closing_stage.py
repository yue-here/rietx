"""A plan's closing stage (WP-2002, the sixth round's Q1 and Q2, ruled 2026-10-21).

Every stage freezes its peak windows at the values it starts from, and drops
``forward.WINDOW_AREA_TOL`` (2 %) of each peak's area.  So a plan ends with one
more stage: recompiled at the answer, with windows dropping
``RefinementPlan.closing_window_tol`` (1e-3), and solved with every glob the
plan freed.  ``None`` runs the declared stages alone.  These tests pin the
plumbing: which stages run, at which tolerances, what the record says, and
that every surface that reruns a stage reruns it at its windows.  What the
closing stage buys in accuracy is ``tests/test_window_domain.py``'s.
"""

from __future__ import annotations

import pytest

import rietx as rx
from rietx.model.forward import WINDOW_AREA_TOL
from rietx.refine import replay
from rietx.schemas.plan import CLOSING_WINDOW_TOL, PlanSpec
from rietx.sequential import _collapse
from rietx.strategy.staged import CLOSING_STAGE_NAME
from tests.test_refine_synthetic import perturbed_models, synthesize

SHORT = [
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=40),
    rx.Stage("cell", ["phases.*.cell.*", "phases.*.scale"], max_iter=40,
             restraint_weight_scale=0.5, window_slack_deg=0.4),
]


def _plan(**kw) -> rx.RefinementPlan:
    return rx.RefinementPlan(stages=[rx.Stage(**vars(s)) for s in SHORT], **kw)


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture(scope="module")
def closed(pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    return ref, ref.fit(pattern, plan=_plan())


@pytest.fixture(scope="module")
def unclosed(pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    return ref, ref.fit(pattern, plan=_plan(closing_window_tol=None))


def test_a_plan_runs_its_stages_then_one_freeing_every_glob_at_tight_windows():
    plan = _plan()
    assert plan.closing_window_tol == CLOSING_WINDOW_TOL == 1e-3
    names = [s.name for s in plan.run_stages()]
    assert names == ["scale_bkg", "cell", CLOSING_STAGE_NAME]
    closing = plan.closing_stage()
    # every glob once, in first-seen order
    assert closing.turn_on == ["phases.*.scale", "instrument.background.*",
                               "phases.*.cell.*"]
    # the last declared stage's discrete settings, and no seed
    last = plan.stages[-1]
    assert (closing.max_iter, closing.restraint_weight_scale, closing.window_slack_deg,
            closing.ftol) == (last.max_iter, last.restraint_weight_scale,
                              last.window_slack_deg, last.ftol)
    assert closing.seed == 0.0 and closing.strain_seed == 0.0
    # the last declared stage still converges, so the closing stage is handed
    # an answer rather than a frozen-window plateau (WP-2045); the closing
    # stage converges to the solver's own tolerance at its own windows
    assert plan.stage_ftols() == [1e-6, None, None]
    assert plan.stage_window_tols() == [None, None, 1e-3]
    # the declared list is untouched
    assert [s.name for s in plan.stages] == ["scale_bkg", "cell"]


def test_none_runs_the_declared_stages_alone():
    plan = _plan(closing_window_tol=None)
    assert plan.closing_stage() is None
    assert [s.name for s in plan.run_stages()] == ["scale_bkg", "cell"]
    assert plan.stage_ftols() == [1e-6, None]
    assert plan.stage_window_tols() == [None, None]
    assert rx.RefinementPlan(stages=[]).run_stages() == []


@pytest.mark.parametrize("bad", [0.0, 1.0, -1e-3, float("nan"), float("inf"), True])
def test_a_fraction_outside_zero_to_one_is_refused_where_it_is_read(bad):
    with pytest.raises(ValueError, match="closing_window_tol"):
        PlanSpec(stages=[], closing_window_tol=bad)
    with pytest.raises(ValueError, match="closing_window_tol"):
        _plan(closing_window_tol=bad).run_stages()


def test_the_setting_round_trips_through_the_mirror_and_the_series_collapse():
    plan = _plan(closing_window_tol=2e-3)
    spec = PlanSpec.from_plan(plan)
    assert spec.closing_window_tol == 2e-3
    assert PlanSpec.model_validate_json(spec.model_dump_json()).to_plan() == plan
    assert PlanSpec().closing_window_tol == CLOSING_WINDOW_TOL
    # a warm series refit is the compressed plan, and keeps its closing stage
    for tol in (2e-3, None):
        assert _collapse(_plan(closing_window_tol=tol)).closing_window_tol == tol


def test_a_fit_records_the_closing_stage_and_its_windows(closed, unclosed):
    ref, result = closed
    assert [s.name for s in result.stages] == ["scale_bkg", "cell", CLOSING_STAGE_NAME]
    assert [s.ftol for s in result.stages] == [1e-6, None, None]
    nodes = [n for n in ref.history.nodes.values() if n.action.kind == "stage"]
    assert [n.action.window_area_tol for n in nodes] == [None, None, 1e-3]
    # each line replays what ran: run_stage's own default is the closing
    # fraction, so the closing node names no window and a declared one its 2 %
    assert "window_area_tol" not in nodes[-1].action.api_call()
    assert nodes[0].action.api_call().endswith("window_area_tol=0.02)")
    # the trials a report runs on the caller's behalf compare χ² with this
    # fit's, so they inherit its answer windows
    assert ref._plan_settings["window_area_tol"] == 1e-3

    ref_u, result_u = unclosed
    assert [s.name for s in result_u.stages] == ["scale_bkg", "cell"]
    assert all(n.action.window_area_tol is None
               for n in ref_u.history.nodes.values() if n.action.kind == "stage")
    # resolved, since a trial hands it to run_stage, whose None is the closing
    # fraction: a 2 % fit's trials refit at 2 %
    assert ref_u._plan_settings["window_area_tol"] == WINDOW_AREA_TOL
    # the closing stage moves the answer, if only a little, on this fixture
    assert result.statistics.chi2 != result_u.statistics.chi2


def test_replay_and_cherry_pick_rerun_the_closing_stage_at_its_windows(closed, pattern):
    ref, result = closed
    node = ref.history[result.node_id]
    assert node.action.name == CLOSING_STAGE_NAME
    # replay draws the node on the windows it was solved on, which is the
    # compile the result was measured on
    again = replay(ref.history, node.id, pattern)
    assert again.statistics.chi2 == pytest.approx(result.statistics.chi2, rel=1e-9)
    picked = ref.cherry_pick(node.id, pattern)
    assert ref.history[picked.node_id].action.window_area_tol == 1e-3


def test_run_stage_takes_a_window_fraction_and_refuses_a_bad_one(closed, pattern):
    ref, _ = closed
    stage = rx.Stage("polish", ["phases.*.scale"])
    out = ref.run_stage(pattern, stage, window_area_tol=5e-3)
    assert ref.history[out.node_id].action.window_area_tol == 5e-3
    assert ref._plan_settings["window_area_tol"] == 5e-3
    with pytest.raises(ValueError, match="window_area_tol is the fraction"):
        ref.run_stage(pattern, stage, window_area_tol=1.5)
