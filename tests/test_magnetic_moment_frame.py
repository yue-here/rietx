"""The moment a fit returns is the moment it fitted, when a cell angle moves (#598).

A moment DOF is a modulus and angles on a frame that is orthonormal in the
magCIF unit-vector metric, and that metric moves with the cell *angles*.  The
parameter table used to build the frame once per ``fit()``, while every stage's
compile built a new one from the cell it started at: on a monoclinic β that
refined 2° before the moment stage, the written-back moment was 9σ from the one
the forward model had fitted and ``fitted_structure`` re-evaluated 1.9 % of the
peak height away from ``y_calc``.  The fixture is the issue's own: P 1 2/m 1,
a = 5, b = 6, c = 7 Å, Mn at the origin under the identity magnetic group
(n = 3), truth m = (2.5, 0, 2.5) at β = 101°, constant-wavelength neutrons at
λ = 2.4 Å with Gaussian counting noise.

What each test can fail on is the point.  ``y(fitted_structure) == y_calc`` is
the structural check — it needs no internal attribute and fails at 9.5e-4 of
the peak height on the 0.1° arm before the fix.  The start-at-truth arm is the
control: there nothing moved before the moment stage, so it held before the
fix, and it is pinned to the numbers it had then.
"""

from __future__ import annotations

import dataclasses

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.moments import (
    dofs_from_moment,
    moment_frame,
    moment_from_dofs,
)
from rietx.crystallography.magnetic.operators import moment_magnitude
from rietx.io.exporters import reflection_table
from rietx.model.forward import WINDOW_AREA_TOL, compile_model, recorded_window_tol
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.structure import Atom, Cell, MagneticSymmetry, Moment, Phase

TRUE_M = (2.5, 0.0, 2.5)
TT = np.arange(8.0, 150.0, 0.04)
BASE = ["phases.*.scale", "instrument.background.c*"]
CELL = ["phases.*.cell.*"]
MOMENT = ["phases.*.atoms.*.moment.dof*"]
#: scale → cell → cell + moment: the angle moves in stage 2, before the moment
PLAN_3 = rx.RefinementPlan(stages=[
    rx.Stage("scale", BASE), rx.Stage("cell", BASE + CELL),
    rx.Stage("moment", BASE + CELL + MOMENT)])
#: scale → cell + moment: the angle moves inside the stage that fits the moment
PLAN_2 = rx.RefinementPlan(stages=[
    rx.Stage("scale", BASE), rx.Stage("cell+moment", BASE + CELL + MOMENT)])


def _atom(label, sp, xyz, biso, moment=None):
    return Atom(label=label, species=sp, x=P(value=xyz[0]), y=P(value=xyz[1]),
                z=P(value=xyz[2]), occ=P(value=1.0), biso=P(value=biso, unit="A^2"),
                moment=moment)


def _phase(beta, *, a=5.0, m=TRUE_M, scale=1.0, lattice="P 1 2/m 1",
           angles=None):
    alpha, gamma = (90.0, 90.0) if angles is None else angles
    return Phase(
        name="mono", space_group=lattice,
        cell=Cell(a=P(value=a), b=P(value=6.0), c=P(value=7.0),
                  alpha=P(value=alpha), beta=P(value=beta), gamma=P(value=gamma)),
        scale=P(value=scale, min=0.0, transform="softplus"),
        atoms=[_atom("Mn", "Mn", (0, 0, 0), 0.3, Moment.from_values(m, "Mn2+", vary=True)),
               _atom("O", "O", (0.5, 0.5, 0.5), 0.4)],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))


def _grid() -> rx.PatternData:
    return rx.PatternData(two_theta=TT.tolist(), intensity=[1.0] * len(TT))


def _redraw(structure, instrument, grid, window_area_tol):
    """``Refinement.predict(grid)`` at a stated window fraction, which it does not take."""
    table = ParameterTable(structure, instrument)
    model = compile_model(structure, instrument, grid,
                          moving_paths=set(table.moving_paths),
                          window_area_tol=window_area_tol)
    return np.asarray(model.evaluate(table.decode(table.x0())), float)


def _simulate(instrument, seed, window_area_tol=None):
    """The truth at β = 101°, scaled to a 2e4-count peak, on a 50-count floor.

    ``None`` draws it at ``predict``'s windows, the closing stage's (WP-2002).
    """
    truth = rx.Structure(phases=[_phase(101.0)])
    y = _redraw(truth, instrument, _grid(), window_area_tol)
    scale = 2e4 / y.max()
    y = y * scale + 50.0
    yo = y + np.random.default_rng(seed).normal(0.0, np.sqrt(y))
    data = rx.PatternData(two_theta=TT.tolist(), intensity=yo.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0)).tolist())
    return data, scale


@pytest.fixture(scope="module")
def cw():
    instrument = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.25)
    data, scale = _simulate(instrument, seed=7)
    return instrument, data, scale


@pytest.fixture(scope="module")
def cw_declared():
    """``cw`` drawn at the declared stages' windows, as every pattern was before WP-2002."""
    instrument = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.25)
    data, scale = _simulate(instrument, seed=7, window_area_tol=WINDOW_AREA_TOL)
    return instrument, data, scale


def _fit(cw, beta0, plan, *, a0=5.0, intervals=False):
    """``intervals=True`` keeps the fit's automatic profile interval of each
    angle it leaves out (WP-2002).  Off by default, because only the row that
    reads it should pay for it (WP-2019)."""
    instrument, data, scale = cw
    ref = rx.Refinement(rx.Structure(phases=[_phase(beta0, a=a0, scale=scale)]),
                        instrument)
    ref._auto_intervals = intervals
    return ref, ref.fit(data, plan=plan)


def _rel(y, y_ref) -> float:
    y, y_ref = np.asarray(y, float), np.asarray(y_ref, float)
    return float(np.max(np.abs(y - y_ref)) / np.max(np.abs(y_ref)))


def _dof_value(result, k: int) -> float:
    return next(p.value for p in result.parameters
                if p.path == f"phases.0.atoms.0.moment.dof{k}")


def _dof0(result) -> float:
    return _dof_value(result, 0)


def _written_back(ref):
    fs = ref.fitted_structure
    return (np.array(fs.phases[0].atoms[0].moment.values()),
            fs.phases[0].cell.lengths_angles())


# --------------------------------------------------------------------------
# the defect: the angle moves before the moment stage
# --------------------------------------------------------------------------
@pytest.mark.parametrize("beta0", [101.1, 101.5, 103.0])
def test_the_written_back_moment_is_the_fitted_one_after_the_angle_moved(cw, beta0):
    """Δβ = 0.1°, 0.5°, 2° before the moment stage: no shift at any of them.

    On main the written-back |m| sat 0.4σ, 2.2σ and 9σ from the refined
    modulus, scaling with the move, and ``fitted_structure`` re-evaluated
    9.5e-4, 4.8e-3 and 1.9e-2 of the peak height from ``y_calc``.
    """
    ref, result = _fit(cw, beta0, PLAN_3)
    assert result.status == "converged"
    y_back = rx.Refinement(ref.fitted_structure, ref.fitted_instrument).predict(cw[1])
    assert _rel(y_back, result.y_calc) < 1e-12
    assert _rel(ref.predict(), result.y_calc) < 1e-12

    m_back, cell = _written_back(ref)
    row = ref.report().magnetic[0]
    np.testing.assert_allclose(row.crystalaxis, m_back, rtol=0, atol=1e-12)
    assert row.magnitude == pytest.approx(abs(_dof0(result)), abs=1e-12)
    # the last stage moves β by ~0.01° on this plan, so the refined modulus (in
    # the metric that stage started at) and |m| at the fitted cell agree to that
    # order and no better; before the fix the gap was 0.4σ-9σ
    assert abs(moment_magnitude(m_back, cell) - abs(_dof0(result))) < 0.1 * row.magnitude_esd
    np.testing.assert_allclose(moment_magnitude(m_back, cell), 3.1772, atol=5e-4)


def test_the_start_at_truth_control_is_unchanged(cw_declared):
    """Nothing moves before the moment stage, so main was right here already.

    Pinned to main's numbers (13520aae): components (2.49970, ±0.09520, 2.49298),
    |m| 3.17716 at the fitted β, written-back and forward-model alike.  So it
    declares the setting they were measured at: the pattern drawn at the
    declared stages' windows and fitted on them, with no closing stage
    (WP-2002).  Drawn and fitted at the default's 1e-3 instead, the b
    component reads 0.09512, 7e-5 from it and nearer the truth's 0.

    The sign of the b component is not a measurement.  Flipping it changes
    the pattern by 4.5e-17 of its maximum, so TRF's −0.09520 and the LM
    driver's +0.09520 are one minimum, their χ² equal to 4e-13 (WP-1938).
    """
    ref, result = _fit(cw_declared, 101.0,
                       dataclasses.replace(PLAN_3, closing_window_tol=None))
    m_back, cell = _written_back(ref)
    np.testing.assert_allclose(m_back * [1.0, np.sign(m_back[1]), 1.0],
                               [2.49970, 0.09520, 2.49298], atol=2e-5)
    assert moment_magnitude(m_back, cell) == pytest.approx(3.17716, abs=2e-5)
    # 1e-5 rather than roundoff, so this arm stays the one that passed before
    # the fix: main's 1.2e-6 here was the in-stage symptom below at the 1e-4°
    # β moves inside the last stage, which the fix takes to 1e-16
    y_back = _redraw(ref.fitted_structure, ref.fitted_instrument, cw_declared[1],
                     recorded_window_tol(result.stages[-1].window_area_tol))
    assert _rel(y_back, result.y_calc) < 1e-5


def test_the_angle_moving_inside_the_moment_stage_reports_the_fitted_curve(cw):
    """The second symptom: the result's own compile at the fitted cell read the
    DOFs in a third frame, so ``y_calc`` and the statistics described a moment
    neither the solve nor the write-back had (1.8e-2 of the peak height)."""
    ref, result = _fit(cw, 103.0, PLAN_2)
    y_back = rx.Refinement(ref.fitted_structure, ref.fitted_instrument).predict(cw[1])
    assert _rel(y_back, result.y_calc) < 1e-12
    assert _rel(ref.predict(), result.y_calc) < 1e-12
    m_back, _ = _written_back(ref)
    row = ref.report().magnetic[0]
    np.testing.assert_allclose(row.crystalaxis, m_back, rtol=0, atol=1e-12)
    assert row.magnitude == pytest.approx(abs(_dof0(result)), abs=1e-12)
    # the reflection table reads the fitted model with a table built afterwards,
    # so it is the third reader that has to agree: against a compile and a
    # table that are both fresh from the written-back structure
    fs, fi = ref.fitted_structure, ref.fitted_instrument
    table = ParameterTable(fs, fi)
    fresh = reflection_table(compile_model(fs, fi, cw[1]), table.decode(table.x0()), fs)
    np.testing.assert_allclose([r.intensity for r in ref.reflection_table()],
                               [r.intensity for r in fresh], rtol=1e-10)


def test_a_series_moment_row_states_the_written_back_moment(cw):
    """``SeriesEntry.magnetic`` is the fourth reader of the fitted model through
    a table built afterwards — the one ``report()`` is, a pattern at a time."""
    instrument, data, scale = cw
    structure = rx.Structure(phases=[_phase(103.0, scale=scale)])
    series = rx.refine_sequential([data], structure, instrument, plan=PLAN_2)
    ref, _ = _fit(cw, 103.0, PLAN_2)
    m_back, _ = _written_back(ref)
    np.testing.assert_allclose(series.entries[0].magnetic[0].crystalaxis, m_back,
                               rtol=0, atol=1e-9)


# --------------------------------------------------------------------------
# the joint path builds its tables once too (params/multi.py)
# --------------------------------------------------------------------------
def test_the_joint_path_writes_back_the_moment_it_fitted():
    instruments = [rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.25),
                   rx.Instrument.constant_wavelength_neutron(1.8, fwhm_deg=0.25)]
    sims = [_simulate(ins, seed) for ins, seed in zip(instruments, (7, 11), strict=True)]
    data = [d for d, _ in sims]
    structure = rx.Structure(phases=[_phase(103.0, scale=sims[0][1])])
    ref = rx.MultiHistogramRefinement(structure, instruments)
    result = ref.fit(data, plan=PLAN_3)
    dofs = [_dof_value(result, k) for k in range(3)]
    for h in range(len(data)):
        # the joint path has no result-time compile (#272 is single-histogram),
        # so ``y_calc`` is the last stage's frozen model and differs from a fresh
        # compile by its windows alone; the moment is compared directly instead:
        # the one the stage's model read the refined DOFs as, against the one
        # written back
        fitted = moment_from_dofs(ref._models[h].phases[0].magnetic.frames[0], dofs)
        m_back = ref.fitted_structures[h].phases[0].atoms[0].moment.values()
        np.testing.assert_allclose(m_back, fitted, rtol=0, atol=1e-12, err_msg=str(h))
    m0 = ref.fitted_structures[0].phases[0].atoms[0].moment.values()
    m1 = ref.fitted_structures[1].phases[0].atoms[0].moment.values()
    np.testing.assert_array_equal(m0, m1)
    # and the frame is the stage's cell's, not the declared one's: handing the
    # compile the table's frames alone makes the two readings agree, but in a
    # frame orthonormal at β = 103°, where the modulus is not |m|
    esd = next(p.stderr for p in result.parameters
               if p.path == "phases.0.atoms.0.moment.dof0")
    cell = ref.fitted_structures[0].phases[0].cell.lengths_angles()
    assert abs(moment_magnitude(m0, cell) - abs(dofs[0])) < 0.1 * esd


# --------------------------------------------------------------------------
# the table's own contract
# --------------------------------------------------------------------------
def _table(beta, m=TRUE_M, **kw):
    structure = rx.Structure(phases=[_phase(beta, m=m, **kw)])
    instrument = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.25)
    return structure, ParameterTable(structure, instrument)


def _components(table):
    by = {e.path: e.value for e in table.entries}
    return np.array([by[f"phases.0.atoms.0.moment.{n}"]
                     for n in ("crystalaxis_x", "crystalaxis_y", "crystalaxis_z")])


def _dofs(table):
    by = {e.path: e.value for e in table.entries}
    return np.array([by[f"phases.0.atoms.0.moment.dof{k}"] for k in range(3)])


def test_reframe_keeps_the_components_and_moves_the_dofs():
    structure, table = _table(103.0)
    before = _components(table)
    structure.phases[0].cell.beta.value = 101.0
    assert table.reframe_moments(structure) == ["phases.0.atoms.0"]
    cell = structure.phases[0].cell.lengths_angles()
    frame = table.moment_frames()["phases.0.atoms.0"]
    np.testing.assert_array_equal(
        frame, moment_frame(np.eye(3, dtype=int), cell))
    np.testing.assert_allclose(_components(table), before, atol=1e-14)
    np.testing.assert_allclose(moment_from_dofs(frame, _dofs(table)), before, atol=1e-14)
    np.testing.assert_allclose(_dofs(table), dofs_from_moment(frame, cell, before),
                               atol=1e-14)
    # and the free vector carries the new DOFs, which is what the solve starts from
    table.set_vary(["phases.*.atoms.*.moment.dof*"], True)
    np.testing.assert_allclose(table.x0(), _dofs(table), atol=0)


def test_reframe_is_a_no_op_where_the_metric_cannot_move():
    """An orthogonal cell's frame does not depend on its lengths, so a length
    move rebuilds nothing and every such fit stays bit-identical."""
    structure, table = _table(90.0, lattice="P m m m")
    dofs = _dofs(table).copy()
    structure.phases[0].cell.a.value = 5.3
    assert table.reframe_moments(structure) == []
    np.testing.assert_array_equal(_dofs(table), dofs)


def test_reframe_keeps_a_zero_moment_s_angles():
    """Components that are all zero carry no direction, so the DOFs stay put."""
    structure, table = _table(103.0)
    for e in table.entries:
        if e.path == "phases.0.atoms.0.moment.dof0":
            e.value = 0.0
    table._rebuild()
    angles = _dofs(table)[1:].copy()
    structure.phases[0].cell.beta.value = 101.0
    assert table.reframe_moments(structure) == ["phases.0.atoms.0"]
    np.testing.assert_array_equal(_dofs(table)[1:], angles)


def test_dofs_in_frame_needs_no_cell():
    """Solved on the frame's rows, so a frame built at another cell is read right."""
    from rietx.crystallography.magnetic.moments import dofs_in_frame

    cell = (5.0, 6.0, 7.0, 90.0, 103.0, 90.0)
    frame = moment_frame(np.eye(3, dtype=int), cell)
    m = np.array([2.5885, 0.0951, 2.5114])
    np.testing.assert_allclose(dofs_in_frame(frame, m), dofs_from_moment(frame, cell, m),
                               atol=1e-13)
    np.testing.assert_allclose(moment_from_dofs(frame, dofs_in_frame(frame, m)), m,
                               atol=1e-13)


def test_an_angle_the_data_cannot_see_stops_its_interval_at_half_a_turn(cw):
    """WP-2002: the automatic profile interval of a left-out moment angle.

    This fit ends with the magnetic scale at 0.013(15), so every angle column
    vanishes and the stationary test leaves both angles out.  Before the
    half-turn stop each side doubled out to ±1e12 rad and spent its whole
    refit budget, 120 refits an angle (0.08 s of fit, 15.9 s of interval).
    An angle repeats every 2π, so a side still under the threshold half a
    turn away has no end, and says so."""
    _ref, result = _fit(cw, 103.0, PLAN_2, intervals=True)
    intervals = [p.interval for p in result.parameters if p.interval is not None]
    assert intervals, "the stationary test left no angle out on this fit"
    for interval in intervals:
        stops = {interval.lower_stop, interval.upper_stop}
        assert stops <= {"period", "threshold", "bound"}, (interval.path, stops)
        assert interval.n_refits < 120, (interval.path, interval.n_refits)


# --------------------------------------------------------------------------
# review of #615, round 1
# --------------------------------------------------------------------------
def _two_site_table(beta, ties=False):
    from rietx.params.vector import AffineTie

    phase = _phase(beta)
    phase.atoms.insert(1, _atom("Mn", "Mn", (0.5, 0.0, 0.5), 0.3,
                                Moment.from_values((1.0, 0.5, -2.0), "Mn2+", vary=True)))
    structure = rx.Structure(phases=[phase])
    instrument = rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.25)
    table = ParameterTable(structure, instrument)
    if ties:
        table.set_tie("phases.0.atoms.1.moment.dof0",
                      AffineTie(terms=(("phases.0.atoms.0.moment.dof0", 1.0),)))
    return structure, table


def test_reframe_leaves_a_tied_moment_dof_to_its_source():
    """Two sites with tied moduli, and a β that moves: the tied entry follows its
    source, so the write-back and the compile hold one moment for it."""
    structure, table = _two_site_table(103.0, ties=True)
    table.set_vary(["phases.0.atoms.0.moment.dof*"], True)
    structure.phases[0].cell.beta.value = 98.0
    assert len(table.reframe_moments(structure)) == 2
    by = {e.path: e.value for e in table.entries}
    mu_a = by["phases.0.atoms.0.moment.dof0"]
    assert by["phases.0.atoms.1.moment.dof0"] == mu_a
    # the components written back are those the compile decodes: B's frame, its
    # re-seeded angles and the *source's* modulus
    decoded = table.decode(table.x0())
    for base in ("phases.0.atoms.0", "phases.0.atoms.1"):
        dofs = [decoded[f"{base}.moment.dof{k}"] for k in range(3)]
        expect = moment_from_dofs(table.moment_frames()[base], dofs)
        got = [by[f"{base}.moment.crystalaxis_{n}"] for n in "xyz"]
        np.testing.assert_allclose(got, expect, rtol=0, atol=1e-12)


def test_a_shared_moment_over_a_per_histogram_cell_is_refused():
    instruments = [rx.Instrument.constant_wavelength_neutron(2.4, fwhm_deg=0.25),
                   rx.Instrument.constant_wavelength_neutron(1.8, fwhm_deg=0.25)]
    structure = rx.Structure(phases=[_phase(103.0)])
    from rietx.params.multi import MultiParameterTable, SharingMap

    with pytest.raises(ValueError, match="moment of phases.0.atoms.0 is shared"):
        MultiParameterTable(structure, instruments,
                            sharing=SharingMap(per_histogram=["phases.*.cell.*"]))
    # positive arms: the moment per-histogram as well, or the default sharing
    MultiParameterTable(structure, instruments, sharing=SharingMap(
        per_histogram=["phases.*.cell.*", "phases.*.atoms.*.moment.*"]))
    MultiParameterTable(structure, instruments)
