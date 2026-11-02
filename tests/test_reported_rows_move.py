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

from pathlib import Path

import gemmi
import pytest

from rietx import (
    MultiHistogramRefinement,
    Refinement,
    RefinementPlan,
    Stage,
    refine_sequential,
)
from rietx.refine import _build_result
from rietx.schemas.common import Diagnostic
from tests.test_absent_phase import _absent_phase_inputs
from tests.test_multi_histogram import perturbed_inputs
from tests.test_multi_histogram import synthesize as synth_hist
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("reported-rows-move")

OUT = Path(__file__).parent / "output"

CELL_FOLLOWERS = ("cell.b", "cell.c")


def _paths(result) -> set[str]:
    return {p.path for p in result.parameters}


def _every_fixed_row_follows_a_free_one(result) -> None:
    """The membership rule as a property of the answer alone.

    A row reported with ``vary=False`` is there only as a follower, so the
    phase, site or instrument block it belongs to must have a free row
    reported inside it (a coordinate's free DOF is ``….atoms.j.dof.k``).
    Weaker than set-equality with ``moving_paths``, which needs the answer
    stage's table, and enough to fail on the pre-WP-1999 filter.
    """
    free = {p.path for p in result.parameters if p.vary}
    for p in result.parameters:
        if p.vary:
            continue
        block = p.path.rsplit(".", 1)[0] + "."
        assert p.stderr is not None or any(f.startswith(block) for f in free), p.path


# ----------------------------------------------------------------------
# a held phase
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def held_fit():
    """The absent-phase fixture: phase 1 is cubic and its scale floors."""
    structure, ins = _absent_phase_inputs()
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthesize(), plan="mccusker_default")
    OUT.mkdir(exist_ok=True)
    result.plot(OUT / "reported_rows_held_phase.png")
    return result


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
@pytest.fixture(scope="module")
def certified_fit():
    """``lab_calibrate`` on LaB6 with its cell held, as a calibration runs."""
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, history=False)
    ref.hold("phases.0.cell.*")
    result = ref.fit(synthesize(), plan="lab_calibrate")
    OUT.mkdir(exist_ok=True)
    result.plot(OUT / "reported_rows_held_certified_cell.png")
    return ref, result


def test_a_held_certified_cell_reports_no_cell_row(certified_fit):
    """``lab_calibrate`` on a standard whose cell is held: no cell row at all.

    Before WP-1999 ``a`` was absent and ``b`` and ``c`` were present at the
    certified value, which read as if the fit had measured two edges of a
    cubic cell and not the third.
    """
    _ref, result = certified_fit
    assert not [p for p in _paths(result) if ".cell." in p]
    _every_fixed_row_follows_a_free_one(result)


def test_the_cif_still_states_every_row_the_answer_dropped(certified_fit, tmp_path):
    """The CIF writer reads the model, never ``result.parameters``.

    The rows WP-1999 drops are constants, so the refinement CIF must still
    carry every cell length and every coordinate, at the model's value and
    with no standard uncertainty, while a refined row keeps its su.
    """
    ref, result = certified_fit
    reported = _paths(result)
    out = tmp_path / "held_cell.cif"
    ref.write_cif(out)
    block = gemmi.cif.read(str(out)).sole_block()
    phase = ref.fitted_structure.phases[0]
    for n in "abc":
        assert f"phases.0.cell.{n}" not in reported
        text = block.find_value(f"_cell_length_{n}")
        assert text is not None and "(" not in text, (n, text)
        assert float(text) == pytest.approx(getattr(phase.cell, n).value, abs=1e-6)
    sites = block.find("_atom_site_", ["label", "fract_x", "fract_y", "fract_z"])
    by_label = {row[0]: row for row in sites}
    assert set(by_label) == {a.label for a in phase.atoms}
    dropped = 0
    for j, atom in enumerate(phase.atoms):
        for k, axis in enumerate("xyz", start=1):
            text = by_label[atom.label][k]
            assert float(text.split("(")[0]) == pytest.approx(
                getattr(atom, axis).value, abs=1e-6), (atom.label, axis)
            if f"phases.0.atoms.{j}.{axis}" not in reported:
                dropped += 1
                assert "(" not in text, (atom.label, axis, text)
    assert dropped == 6    # no stage of lab_calibrate frees a site DOF
    # a refined quantity still carries its su into the file
    refined = [p for p in result.parameters if p.vary and p.stderr is not None]
    assert refined, "the calibration refined nothing"


@pytest.fixture(scope="module")
def default_fit():
    """LaB6 under ``mccusker_default``: the cell refines, no site DOF does."""
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, history=False)
    result = ref.fit(synthesize(), plan="mccusker_default")
    OUT.mkdir(exist_ok=True)
    result.plot(OUT / "reported_rows_coordinate_default.png")
    return ref, result


def test_a_coordinate_no_stage_freed_is_not_reported(default_fit):
    """A coordinate is tied to its site DOFs, so it moves only when they do."""
    x = "phases.0.atoms.1.x"
    _ref, default = default_fit
    assert x not in _paths(default)
    _every_fixed_row_follows_a_free_one(default)

    structure, ins = perturbed_models()
    structural = Refinement(structure, ins, history=False).fit(
        synthesize(), plan="mccusker_structural")
    OUT.mkdir(exist_ok=True)
    structural.plot(OUT / "reported_rows_coordinate_structural.png")
    row = structural.parameter(x)
    assert row.vary is False and row.stderr is not None


def test_a_tied_row_inherits_a_withheld_esd(default_fit):
    """A ``CELL_RUNAWAY`` cell that stays a free column withholds its esd,
    and a cubic ``b``/``c`` tied to it withhold theirs too.

    A real fit no longer reaches this: a reset cell is held for its stage
    (``test_cell_runaway_safety.py``), so since WP-1999 its followers leave
    the answer with it.  The row build is still the one place the rule
    lives, so the answer is rebuilt here from the fit's own covariance with
    the finding handed in, rather than waiting for a fixture that keeps a
    reset cell free.
    """
    ref, result = default_fit
    kept, table, theta, stderr_internal, correlation = ref._answer_covariance
    assert kept is result

    def rebuild(cell_runaway):
        return _build_result(
            ref._model, table, theta, mode=result.mode, status=result.status,
            stage_results=list(result.stages), diagnostics=[],
            structure=ref.structure, stderr_internal=stderr_internal,
            correlation=correlation, cell_runaway=cell_runaway)

    finding = Diagnostic(level="warning", code="CELL_RUNAWAY",
                         message="injected", where=["phases.0.cell.a"])
    plain, flagged = rebuild([]), rebuild([finding])
    for n in "abc":
        path = f"phases.0.cell.{n}"
        assert plain.parameter(path).stderr is not None, path
        row = flagged.parameter(path)    # still listed: a is a free column
        assert row.stderr is None, path
        assert row.value == plain.parameter(path).value, path
    # the finding names a cell, so nothing outside it loses its esd
    assert flagged.parameter("instrument.zero_shift").stderr == \
        plain.parameter("instrument.zero_shift").stderr


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
    OUT.mkdir(exist_ok=True)
    for h in range(len(patterns)):
        result.for_histogram(h).plot(OUT / f"reported_rows_joint_h{h}.png")
    assert not [p for p in _paths(result) if ".cell." in p]
    assert [p for p in result.parameters if p.vary]
