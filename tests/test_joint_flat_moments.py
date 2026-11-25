"""The joint X-ray + neutron path holds the moment directions a powder cannot see.

Issue #600.  The single-pattern runner holds a moment direction the
calculated pattern does not respond to (WP-1327, ``refine._hold_flat_moments``)
and the joint runner did not: on a cubic collinear ferromagnet — where a
powder cannot see the moment direction at all (Shirane 1959) — a joint fit of
one X-ray and one neutron pattern came back ``converged`` with the polar angle
at ±1.4e9 rad and the azimuth at ±1.5e10 rad, nothing held, and a modulus esd
1.88× the one the same fit gives with the angles held.

The joint rule is the intersection (``joint._flat_moments_multi``): a
direction is held only when **every** pattern that carries it finds it flat,
since a direction one pattern sees is seen by the joint fit.  An X-ray
pattern does not see a moment at all, so it never vetoes the neutron
pattern's answer — and the Pmmm control is what fails a union.

Synthetic, noise-free, small grids: the assertions are about the hold, not
about a specimen.
"""
from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.operators import moment_to_cartesian
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.plan import CLOSING_WINDOW_TOL
from rietx.schemas.structure import MagneticSymmetry, Moment

LAM_X, LAM_N = 1.5406, 2.4
BASE = "phases.0.atoms.0.moment"
CELLS = {"P m -3 m": (4.0, 4.0, 4.0, 90.0, 90.0, 90.0),
         "R -3 m:R": (4.0, 4.0, 4.0, 70.0, 70.0, 70.0),
         "P m m m": (4.0, 4.4, 5.0, 90.0, 90.0, 90.0)}


def _phase(space_group: str, moment, scale: float = 1.0) -> rx.Phase:
    P = rx.Parameter
    a, b, c, al, be, ga = CELLS[space_group]
    return rx.Phase(
        name="M", space_group=space_group,
        cell=rx.Cell(a=P(value=a), b=P(value=b), c=P(value=c),
                     alpha=P(value=al), beta=P(value=be), gamma=P(value=ga)),
        scale=P(value=scale, min=0.0, transform="softplus"),
        atoms=[rx.Atom(label="Mn", species="Mn", x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), occ=P(value=1.0),
                       biso=P(value=0.3, unit="A^2"),
                       moment=Moment.from_values(moment, "Mn2+", vary=True))],
        magnetic_symmetry=MagneticSymmetry(operations=["x,y,z,+1"]))


def _instruments():
    return [rx.Instrument.debye_scherrer(LAM_X),
            rx.Instrument.constant_wavelength_neutron(LAM_N, fwhm_deg=0.3)]


def _grids():
    return [np.arange(10.0, 120.0, 0.05), np.arange(8.0, 150.0, 0.1)]


def _joint(space_group: str, truth, start, *, moment_globs=None):
    """A joint fit of noise-free X-ray + neutron patterns of ``truth``."""
    data = []
    for ins, tt in zip(_instruments(), _grids(), strict=True):
        structure = rx.Structure(phases=[_phase(space_group, truth)])
        blank = rx.PatternData(two_theta=tt.tolist(), intensity=[1.0] * len(tt))
        table = ParameterTable(structure, ins)
        y = np.asarray(compile_model(structure, ins, blank).evaluate(
            table.decode(table.x0())), dtype=np.float64)
        y = 2e4 * y / y.max() + 20.0
        data.append(rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist()))
    base = ["phases.*.scale", "instrument.background.c*"]
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale", base),
        rx.Stage("moment", base + (moment_globs
                                   or ["phases.*.atoms.*.moment.dof*"]))],
        # declared, not inherited: off by default since WP-2222, and the
        # noise-free truth is drawn on compile_model's closing windows
        closing_window_tol=CLOSING_WINDOW_TOL)
    joint = rx.JointRefinement(
        rx.Structure(phases=[_phase(space_group, start)]), _instruments())
    return joint, joint.fit(data, plan=plan)


def _moment_rows(result):
    return {p.path: p for p in result.parameters if ".moment." in p.path}


def test_the_joint_fit_holds_a_cubic_moment_direction():
    """Both angles held, and the modulus esd is the one a caller-held fit gets.

    The issue's case: before the fix nothing was held, both angles carried
    esds of order 1e9 rad, and the modulus esd was inflated by the unheld
    flat columns (0.0301 against 0.0160 on the issue's noisy data).
    """
    _joint_fit, result = _joint("P m -3 m", (3.0, 0.0, 0.0), (2.0, 0.5, 0.5))
    assert set(result.stages[-1].held) == {f"{BASE}.dof1", f"{BASE}.dof2"}, (
        result.stages[-1].held)
    rows = _moment_rows(result)
    assert set(rows) == {f"{BASE}.dof0"}
    assert abs(rows[f"{BASE}.dof0"].value) == pytest.approx(3.0, rel=1e-4)
    # held as a pair, not a combination: nothing to record (#624's fields)
    assert result.stages[-1].moment_flat_axes == {}
    assert result.stages[-1].moment_turned == []
    _f, held_by_caller = _joint("P m -3 m", (3.0, 0.0, 0.0), (2.0, 0.5, 0.5),
                                moment_globs=[f"{BASE}.dof0"])
    assert rows[f"{BASE}.dof0"].stderr == pytest.approx(
        _moment_rows(held_by_caller)[f"{BASE}.dof0"].stderr, rel=1e-3)


def test_the_joint_fit_holds_a_flat_rotation_across_two_angles():
    """The #599 combination, jointly: the moment is turned, then the azimuth held.

    R-3m:R is uniaxial about [111], which the n = 3 frame's pole is not.  The
    start (3.0, 0.2, 0.2) is the one where holding the azimuth *without* the
    turn leaves the polar angle unable to reach the truth's angle to [111]
    (measured on the single-pattern path: ψ = 27.84° at ``max_iter``
    against 10.20°), so this is also the joint path's turn.
    """
    truth = (1.5, 2.0, 3.0)
    joint, result = _joint("R -3 m:R", truth, (3.0, 0.2, 0.2))
    assert result.stages[-1].held == [f"{BASE}.dof2"], result.stages[-1].held
    rows = _moment_rows(result)
    assert rows[f"{BASE}.dof1"].stderr is not None
    # the record #624 added, filled on this path too: the flat axis is [111]
    # in crystal-axis components, and the moment was turned onto its meridian
    stage = result.stages[-1]
    site = "phases.0.atoms.0"
    assert set(stage.moment_flat_axes) == {site}
    axis = np.asarray(stage.moment_flat_axes[site])
    # unit in the magCIF unit-vector metric, so the components are not 1/√3
    assert np.allclose(axis, axis[0], atol=1e-3) and abs(axis[0]) > 0.1, axis
    assert stage.moment_turned == [site]

    def to_111(m):
        cell = CELLS["R -3 m:R"]
        v = moment_to_cartesian(np.asarray(m, dtype=np.float64), cell)
        u = moment_to_cartesian(np.ones(3), cell)
        return float(np.degrees(np.arccos(
            abs(v @ u) / np.linalg.norm(v) / np.linalg.norm(u))))

    fitted = joint.fitted_structures[0].phases[0].atoms[0].moment.values()
    assert to_111(fitted) == pytest.approx(to_111(truth), abs=0.01)


def test_the_joint_fit_holds_nothing_a_neutron_pattern_can_see():
    """The control: on Pmmm every direction is measured, and nothing is held.

    The X-ray pattern finds every moment direction flat — it does not see a
    moment — so a joint rule that took the union of the patterns' answers
    instead of the intersection would hold both angles here.
    """
    truth = (1.5, 2.0, 3.0)
    joint, result = _joint("P m m m", truth, (1.0, 1.0, 2.5))
    assert result.stages[-1].held == []
    assert result.stages[-1].moment_flat_axes == {}
    assert result.stages[-1].moment_turned == []
    rows = _moment_rows(result)
    assert all(rows[f"{BASE}.dof{k}"].stderr is not None for k in range(3))
    assert joint.fitted_structures[0].phases[0].atoms[0].moment.values() == (
        pytest.approx(truth, abs=1e-3))


def test_a_turn_after_the_solve_reads_the_answers_angle_not_the_stage_starts():
    """The late turn (review of #655 item 1): decoded from the committed values.

    A combination released or collapsed while solving is turned at the answer,
    after ``mtable.commit`` and before any column rebuild — ``mtable.x0()`` is
    then the cache the stage *started* from.  The turn is an unseen rotation
    about the flat axis, so it keeps the angle to that axis; written from the
    stage-start angles it would hand the answer the start's angle instead.
    """
    from rietx.joint import JointRefinement, _flat_moments_multi, _turn_flat_axes_multi
    from rietx.refine import _direction

    joint = JointRefinement(
        rx.Structure(phases=[_phase("R -3 m:R", (3.0, 0.2, 0.2))]),
        _instruments())
    mtable = joint.mtable
    mtable.set_vary(["*"], False)
    mtable.set_vary([f"{BASE}.dof*"], True)
    mtable.apply_to_models()
    models = [compile_model(s, ins, rx.PatternData(
        two_theta=tt.tolist(), intensity=[1.0] * len(tt)))
        for s, ins, tt in zip(mtable.structures, mtable.instruments, _grids(),
                              strict=True)]
    _held, axes = _flat_moments_multi(models, mtable)
    assert set(axes) == {BASE}
    axis = axes[BASE]

    def psi(values):
        """Angle to the flat axis, in the frame the turn works in."""
        s = _direction(values[f"{BASE}.dof1"], values[f"{BASE}.dof2"])
        return float(np.degrees(np.arccos(min(abs(float(axis @ s)), 1.0))))

    def own(table):
        return table.decode(table.x0())

    stage_start = mtable.x0()
    cols = {p: i for i, p in enumerate(mtable.free_paths)}
    # the solve moves the angles; commit writes them and no rebuild follows
    theta = mtable.x0()
    theta[cols[f"{BASE}.dof1"]] += 0.35
    theta[cols[f"{BASE}.dof2"]] -= 0.4
    mtable.commit(theta)
    assert np.array_equal(mtable.x0(), stage_start), "x0 is the stale cache"
    answer = psi(own(mtable.tables[0]))
    started = psi(mtable.decode(stage_start)[0])
    assert abs(answer - started) > 1.0, "the solve must have moved the angle"

    assert _turn_flat_axes_multi(models, mtable, axes) == ["phases.0.atoms.0"]
    # the turn is an unseen rotation about the axis: it keeps the angle to it
    for table in mtable.tables:
        assert psi(own(table)) == pytest.approx(answer, abs=1e-6)
