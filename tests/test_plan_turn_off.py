"""A plan stage that fixes as well as frees (WP-2208).

``Stage.turn_off`` lists globs a stage fixes after it frees its ``turn_on``,
the flags carry, and the closing stage re-solves the declared stages' end
state.  The maintainer's case (ruled 2026-11-09): a Pawley fit settles the
profile, and a Rietveld plan then refines the structure with it fixed.
"""

from __future__ import annotations

import json

import pytest

import rietx as rx
from rietx.schemas.plan import PlanSpec, StageSpec
from rietx.strategy.staged import fixed_at_end
from tests.test_refine_synthetic import perturbed_models, synthesize

PROFILE = "instrument.profile.*"


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _profile(ref):
    return {r.path: r.value for r in ref.parameters()
            if r.path.startswith("instrument.profile.")}


# ------------------------------------------------------------- the replay
def test_the_last_glob_to_match_a_path_decides_it():
    stages = [rx.Stage("a", ["x.*"]),
              rx.Stage("b", [], turn_off=["x.b", "x.c"]),
              rx.Stage("c", ["x.b"])]
    # x.b was fixed and freed again; x.c stays fixed; y.a no glob reaches
    assert fixed_at_end(stages, ["x.a", "x.b", "x.c", "y.a"]) == ["x.c"]
    # within one stage the fix comes after the free
    assert fixed_at_end([rx.Stage("d", ["x.*"], turn_off=["x.a"])],
                        ["x.a", "x.b"]) == ["x.a"]
    # a joint table's row under two names: either name matches
    assert fixed_at_end([rx.Stage("e", ["*"], turn_off=["instrument.zero_shift"])],
                        [("hist.1.instrument.zero_shift", "instrument.zero_shift")]
                        ) == ["hist.1.instrument.zero_shift"]


def test_a_plan_that_never_fixes_closes_as_it_did():
    plan = rx.RefinementPlan.mccusker_default()
    for closing in (plan.closing_stage(), plan.closing_stage(["phases.0.scale"])):
        assert closing.turn_off == []
        assert closing.turn_on == list(dict.fromkeys(
            g for s in plan.stages for g in s.turn_on))


def test_the_closing_stage_fixes_the_paths_the_plan_left_fixed():
    plan = rx.RefinementPlan(stages=[
        rx.Stage("one", ["phases.*.scale", PROFILE]),
        rx.Stage("two", ["phases.*.cell.*"], turn_off=[PROFILE])])
    paths = ["phases.0.scale", "phases.0.cell.a", "instrument.profile.u",
             "instrument.profile.w"]
    assert plan.closing_stage(paths).turn_off == ["instrument.profile.u",
                                                  "instrument.profile.w"]
    # without paths, the declared globs
    assert plan.closing_stage().turn_off == [PROFILE]


# --------------------------------------------------------------- the schema
def test_the_field_round_trips_and_an_old_stage_reads_without_it():
    old = StageSpec.model_validate({"name": "cell", "turn_on": ["phases.*.cell.*"]})
    assert old.turn_off == []
    stage = rx.Stage("s", ["phases.*"], turn_off=["phases.*.atoms.*.biso"])
    spec = StageSpec.model_validate(stage)
    assert spec.turn_off == ["phases.*.atoms.*.biso"]
    assert spec.to_stage() == stage
    plan = PlanSpec(stages=[spec])
    again = PlanSpec.model_validate(json.loads(plan.model_dump_json()))
    assert again.stages[0].turn_off == ["phases.*.atoms.*.biso"]
    assert StageSpec.from_stage(stage) == spec


# ------------------------------------------------------------------ the fits
def test_a_pawley_profile_stays_fixed_through_a_rietveld_plan(pattern):
    """The maintainer's case: the closing stage keeps the fix too."""
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    ref.fit(pattern, mode="pawley", plan=rx.RefinementPlan(stages=[
        rx.Stage("pawley", ["instrument.background.*", "phases.*.cell.*",
                            "instrument.profile.w"], max_iter=30)]))
    settled = _profile(ref)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("everything but the profile",
                 ["phases.*.scale", "instrument.background.*", "phases.*.cell.*",
                  "instrument.*"], turn_off=[PROFILE], max_iter=30)])
    result = ref.fit(pattern, mode="rietveld", plan=plan)
    assert _profile(ref) == settled
    declared, closing = result.stages
    assert closing.name == "closing"
    for stage in (declared, closing):
        assert not any(p.startswith("instrument.profile.") for p in stage.freed)
        assert "instrument.profile.w" in stage.fixed
    assert "phases.0.cell.a" in closing.freed
    rows = {r.path: r for r in ref.parameters()}
    assert not rows["instrument.profile.w"].vary


def test_a_later_stage_frees_a_fixed_path_again(pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", ["phases.*.scale", "instrument.background.*",
                           "phases.*.cell.*"], max_iter=20),
        rx.Stage("hold the cell", ["instrument.profile.w"],
                 turn_off=["phases.*.cell.*"], max_iter=20),
        rx.Stage("cell again", ["phases.*.cell.*"], max_iter=20)])
    result = ref.fit(pattern, plan=plan)
    first, second, third, closing = result.stages
    assert "phases.0.cell.a" in second.fixed
    assert "phases.0.cell.a" not in second.freed
    assert "phases.0.cell.a" in third.freed
    # the end state has the cell free, so the closing stage leaves it free
    assert closing.fixed == []
    assert "phases.0.cell.a" in closing.freed


def test_the_node_records_the_fix_and_its_call_runs(pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("free all", ["phases.*.scale", "instrument.background.*",
                              "phases.*.cell.*"], turn_off=["phases.*.cell.*"],
                 max_iter=20)], closing_window_tol=None)
    ref.fit(pattern, plan=plan)
    node = ref.history[ref.history.order[-1]]
    assert node.action.kind == "stage"
    assert node.action.turn_off == ["phases.*.cell.*"]
    call = node.action.api_call()
    assert "turn_off=['phases.*.cell.*']" in call
    # the rendered call is a stage that fixes the cell again
    stage = eval(call.split("run_stage(data, ", 1)[1].split(")", 1)[0] + ")",  # noqa: S307
                 {"rx": rx})
    assert stage.turn_off == ["phases.*.cell.*"]


def test_a_hold_does_not_report_what_the_stage_fixes(pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    ref.hold(["instrument.zero_shift"])
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("s", ["phases.*.scale", "instrument.background.*",
                       "instrument.zero_shift"],
                 turn_off=["instrument.zero_shift"], max_iter=20)],
        closing_window_tol=None))
    assert result.stages[0].blocked_by_hold == []


def test_a_typo_in_a_fix_is_reported(pattern):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins)
    result = ref.fit(pattern, plan=rx.RefinementPlan(stages=[
        rx.Stage("s", ["phases.*.scale", "instrument.background.*"],
                 turn_off=["instrument.zero_shfit"], max_iter=20)],
        closing_window_tol=None))
    assert result.stages[0].unknown_paths == ["instrument.zero_shfit"]


# --------------------------------------------------------------- the series
def test_a_series_refits_a_plan_that_fixes_stage_by_stage(pattern):
    structure, ins = perturbed_models()
    plan = rx.RefinementPlan(stages=[
        rx.Stage("one", ["phases.*.scale", "instrument.background.*"], max_iter=20),
        rx.Stage("two", ["phases.*.cell.*", "instrument.zero_shift",
                         "instrument.profile.w"], max_iter=20),
        rx.Stage("three", ["phases.*.atoms.*.biso"],
                 turn_off=["instrument.profile.w"], max_iter=20)])
    series = rx.refine_sequential([pattern, pattern], structure, ins, plan=plan)
    # the warm pattern's first rung is the staged plan, never the collapse
    assert series.entries[1].rungs_tried[0] == "warm_staged"
    assert series.entries[1].rung == "warm_staged"


# ------------------------------------------------------------- the joint fit
def test_a_joint_fit_fixes_and_closes_on_the_fix():
    from rietx.multi import MultiHistogramRefinement
    from tests.test_multi_histogram import perturbed_inputs
    from tests.test_multi_histogram import synthesize as synthesize_joint

    patterns = [synthesize_joint(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                                 bkg=[40.0, -6.0, 1.5], seed=1),
                synthesize_joint(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                                 bkg=[70.0, 5.0, -2.0], seed=2)]
    structure, instruments = perturbed_inputs()
    start = [ins.zero_shift.value for ins in instruments]
    result = MultiHistogramRefinement(structure, instruments).fit(
        patterns, plan=rx.RefinementPlan(stages=[
            rx.Stage("all", ["phases.*.scale", "instrument.background.*",
                             "phases.*.cell.*", "instrument.zero_shift"],
                     turn_off=["instrument.zero_shift"], max_iter=30)]))
    declared, closing = result.stages
    for stage in (declared, closing):
        assert not any(p.endswith("zero_shift") for p in stage.freed)
        assert any(p.endswith("zero_shift") for p in stage.fixed)
    zeros = [r.value for r in result.parameters
             if r.path.endswith("instrument.zero_shift")]
    assert zeros == [] or zeros == start
