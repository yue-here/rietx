"""WP-1999 — a reported row is one the fit could move.

``RefinementResult.parameters`` lists what a fit measured.  A tied row is in it
while a source of its tie is free, because the tie carries that column to it;
a tied row whose every source is fixed, or held for the stage (WP-1301), is a
constant no column reached, and it leaves with its source.

Before WP-1999 the filter was "varied or tied", so a cubic ``b`` and ``c``
stayed in the answer beside an absent ``a``: at its carried value, with no
esd, and as a trajectory point where the series had measured nothing.  The
same filter kept every coordinate row whose site DOF no stage freed — 16 of
the 44 rows of the 11-BM NAC walkthrough.
"""

from __future__ import annotations

import pytest

from rietx import (
    MultiHistogramRefinement,
    Refinement,
    RefinementPlan,
    Stage,
    refine_sequential,
)
from tests.test_absent_phase import _absent_phase_inputs
from tests.test_multi_histogram import perturbed_inputs
from tests.test_multi_histogram import synthesize as synth_hist
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("reported-rows-move")

CELL_FOLLOWERS = ("cell.b", "cell.c")


def _paths(result) -> set[str]:
    return {p.path for p in result.parameters}


def _every_fixed_row_follows_a_free_one(result) -> None:
    """The membership rule as a property of the answer alone.

    A row reported with ``vary=False`` is there only as a follower, so the
    phase or instrument block it belongs to must have a free row reported
    beside it.  Weaker than set-equality with ``moving_paths``, which needs
    the answer stage's table, and enough to fail on the pre-WP-1999 filter.
    """
    free = {p.path for p in result.parameters if p.vary}
    for p in result.parameters:
        if p.vary:
            continue
        assert p.stderr is not None or any(
            f.rsplit(".", 1)[0] == p.path.rsplit(".", 1)[0] for f in free), p.path


# ----------------------------------------------------------------------
# a held phase
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def held_fit():
    """The absent-phase fixture: phase 1 is cubic and its scale floors."""
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    return ref.fit(synthesize(), plan="mccusker_default")


def test_a_held_cells_followers_leave_with_it(held_fit):
    held = {p for stage in held_fit.stages for p in stage.held}
    assert "phases.1.cell.a" in held
    reported = _paths(held_fit)
    for name in CELL_FOLLOWERS:
        assert f"phases.1.{name}" not in reported
    # the visible phase's cell refined, so its followers stay, esd and all
    for name in CELL_FOLLOWERS:
        row = held_fit.parameter(f"phases.0.{name}")
        assert row.vary is False and row.stderr is not None


def test_a_held_phase_leaves_no_trajectory_point():
    """The series view of the same leak: no point where nothing was measured."""
    structure, ins = _absent_phase_inputs()
    series = refine_sequential([synthesize(), synthesize(noise_seed=8)],
                               structure, ins, plan="mccusker_default")
    for name in ("cell.a", *CELL_FOLLOWERS):
        assert series.trajectory(f"phases.1.{name}").value == [], name
        assert len(series.trajectory(f"phases.0.{name}").value) == 2, name


# ----------------------------------------------------------------------
# a source the caller fixed
# ----------------------------------------------------------------------
def test_a_held_certified_cell_reports_no_cell_row():
    """``lab_calibrate`` on a standard whose cell is held: no cell row at all.

    Before WP-1999 ``a`` was absent and ``b`` and ``c`` were present at the
    certified value, which read as if the fit had measured two edges of a
    cubic cell and not the third.
    """
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, history=False)
    ref.hold("phases.0.cell.*")
    result = ref.fit(synthesize(), plan="lab_calibrate")
    assert not [p for p in _paths(result) if ".cell." in p]
    _every_fixed_row_follows_a_free_one(result)


def test_a_coordinate_no_stage_freed_is_not_reported():
    """A coordinate is tied to its site DOFs, so it moves only when they do."""
    x = "phases.0.atoms.1.x"
    structure, ins = perturbed_models()
    default = Refinement(structure, ins, history=False).fit(
        synthesize(), plan="mccusker_default")
    assert x not in _paths(default)
    _every_fixed_row_follows_a_free_one(default)

    structure, ins = perturbed_models()
    structural = Refinement(structure, ins, history=False).fit(
        synthesize(), plan="mccusker_structural")
    row = structural.parameter(x)
    assert row.vary is False and row.stderr is not None


# ----------------------------------------------------------------------
# the joint fit builds its own rows
# ----------------------------------------------------------------------
def test_the_joint_fit_reports_the_same_membership():
    """``multi.py`` keeps a second row builder, so it carries the rule too.

    A plan that never frees the cell leaves every cell row, shared or per
    histogram, out of the answer; before WP-1999 ``b`` and ``c`` stayed.
    """
    patterns = [
        synth_hist(0.41390, 3.0, 24.0, scale=5e-4, zero=0.006,
                   bkg=[40.0, -6.0, 1.5], seed=1),
        synth_hist(0.71070, 6.0, 46.0, scale=9e-4, zero=-0.010,
                   bkg=[70.0, 5.0, -2.0], seed=2),
    ]
    structure, instruments = perturbed_inputs()
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*",
                            "instrument.zero_shift"]),
    ])
    result = MultiHistogramRefinement(structure, instruments).fit(patterns, plan=plan)
    assert not [p for p in _paths(result) if ".cell." in p]
    assert [p for p in result.parameters if p.vary]
