"""What a stage lifts before solving, and how the record says so.

``Stage.seed`` starts each row the stage frees that sits exactly on a floor of
0 or above at the seed (``ParameterTable.seed_floored``), and
``StageResult.seeded`` records each such row with its start in column units.

The row these tests lift is ``instrument.profile.y`` with a floor of 0 the
caller states (:func:`_models`): Y has no floor of its own since 2026-10-23
(WP-2002), so its zero is not a floor and no seed lifts it.

WP-1930's floor seed lived here too: it started a freed softplus row sitting
on its floor at a size per unit, because its column there was twelve orders
below its neighbours and rounding chose whether it ever left (issue #832).
WP-1938 refines every row in its own units, so that column is the physical
one, and the floor seed and its ``SOFTPLUS_FREED_AT_FLOOR`` report went.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.params.vector import ParameterTable
from tests import test_multi_histogram as tm
from tests.test_refine_synthetic import perturbed_models, synthesize

OUT = Path(__file__).parent / "output"

PROFILE = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=10),
    rx.Stage("profile", ["instrument.profile.x", "instrument.profile.y"], max_iter=10),
])


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _models():
    """The synthetic models with Y floored at 0 by the caller."""
    structure, ins = perturbed_models()
    ins.profile.y.min = 0.0
    return structure, ins


def test_the_stage_seed_selects_rows_by_their_bounds():
    """WP-1938: a row qualifies by its lower bound, never a transform word."""
    structure, ins = _models()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    freed = table.set_vary(["instrument.profile.x", "instrument.profile.y",
                            "instrument.zero_shift"], True)
    assert ins.zero_shift.value == 0.0 and ins.profile.x.value == 1e-3
    # y sits on its floor of 0 and is lifted; x is above the seed; the zero
    # shift can go negative, so its zero is not a floor
    assert table.seed_floored(freed, 1e-4) == ["instrument.profile.y"]
    values = {e.path: e.value for e in table.entries}
    assert values["instrument.profile.y"] == 1e-4
    assert values["instrument.profile.x"] == 1e-3
    assert values["instrument.zero_shift"] == 0.0
    # a row the stage did not free keeps the value a caller gave it
    assert table.seed_floored(["phases.0.extinction"], 1e-3) == []
    # Y's own box has no floor at 0, so its zero is not lifted
    structure, ins = perturbed_models()
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    freed = table.set_vary(["instrument.profile.y"], True)
    assert table.seed_floored(freed, 1e-4) == []


def test_a_fit_records_what_each_stage_seeded(pattern):
    """A plan with no seed lifts nothing, and each stage says so with ``{}``.

    The synthetic truth has ``y`` = 0, so the freed width may stay on its
    floor; what it may not do is leave its box."""
    structure, ins = perturbed_models()
    result = rx.Refinement(structure, ins, history=False).fit(pattern, plan=PROFILE)
    assert [s.seeded for s in result.stages] == [{}] * len(PROFILE.run_stages())
    assert ins.profile.y.min <= result.parameter("instrument.profile.y").value \
        <= ins.profile.y.max
    OUT.mkdir(exist_ok=True)
    result.plot(path=str(OUT / "floor_seed_profile.png"))
    import matplotlib.pyplot as plt

    plt.close("all")


def test_a_stage_seed_is_recorded_too(pattern):
    """``Stage.seed`` lifts a freed row on its floor and nothing else: ``x``
    starts above 0 and below the seed, and keeps the start it was given
    (#499)."""
    structure, ins = _models()
    plan = rx.RefinementPlan(stages=[
        PROFILE.stages[0],
        rx.Stage("profile", ["instrument.profile.x", "instrument.profile.y"],
                 max_iter=10, seed=0.01)])
    result = rx.Refinement(structure, ins, history=False).fit(pattern, plan=plan)
    assert result.stages[1].seeded == {"instrument.profile.y": 0.01}


def test_run_stage_records_its_seed_too(pattern):
    """``run_stage`` builds its own ``StageResult``: the second call site."""
    structure, ins = _models()
    ref = rx.Refinement(structure, ins, history=False)
    result = ref.run_stage(pattern, rx.Stage(
        "y", ["instrument.profile.y"], max_iter=5, seed=1e-3))
    assert result.stages[-1].seeded == {"instrument.profile.y": 1e-3}


def test_a_joint_fit_seeds_each_histograms_row():
    """The third call site: one row per histogram, each at the seed."""
    patterns = [
        tm.synthesize(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                      bkg=[40.0, -6.0, 1.5], seed=1),
        tm.synthesize(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                      bkg=[70.0, 5.0, -2.0], seed=2)]
    structure, instruments = tm.perturbed_inputs()
    for ins in instruments:
        ins.profile.y.min = 0.0
    plan = rx.RefinementPlan(stages=[
        PROFILE.stages[0],
        rx.Stage("profile", ["instrument.profile.x", "instrument.profile.y"],
                 max_iter=10, seed=1e-4)])
    result = rx.refine_multi(patterns, structure, instruments, plan=plan)
    seeded = result.stages[1].seeded
    assert len(seeded) == 2, seeded
    assert all(p.endswith("instrument.profile.y") for p in seeded)
    assert set(seeded.values()) == {1e-4}


def test_a_stored_stage_record_says_nobody_looked():
    """WP-1076's rule: a result from before the field may have seeded a row,
    so the default is ``None`` rather than an empty answer."""
    old = rx.StageResult.model_validate_json(
        '{"name": "cell", "status": "converged", "n_iterations": 3, '
        '"cost_initial": 2.0, "cost_final": 1.0}')
    assert old.seeded is None


def test_a_record_from_the_floor_seed_still_opens():
    """A result stored while the floor seed existed carries
    ``floor_unseeded``; it opens, and the retired field is dropped (WP-1938)."""
    old = rx.StageResult.model_validate_json(
        '{"name": "hump", "status": "converged", "n_iterations": 3, '
        '"cost_initial": 2.0, "cost_final": 1.0, '
        '"seeded": {}, "floor_unseeded": ["instrument.extra_components.0.height"]}')
    assert old.seeded == {}
    assert "floor_unseeded" not in old.model_dump()
