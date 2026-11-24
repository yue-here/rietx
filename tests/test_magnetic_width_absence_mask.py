"""The separate magnetic-width family covers only the rows the magnetic group lets scatter.

A phase whose magnetic width is active (``CompiledModel.mag_split``, WP-1343)
draws its magnetic component on a second frozen family of windows.  That family
is built only on rows where some member of the row's Laue orbit is allowed a
non-zero M(h) by the magnetic space group
(:func:`rietx.crystallography.magnetic.scattering.magnetic_family_rows`, from
the exact :func:`rietx.crystallography.magnetic.operators.magnetically_allowed`).
A dropped row has F_⊥ = 0 identically, so the profile does not move.

Interpretation table (written before the test bodies)
-----------------------------------------------------
=====================================  ==========================================
test                                   if it fails, it means
=====================================  ==========================================
orbit rule                             the representative alone decides a row (a
                                       domain or arm with intensity is dropped)
k = 0, coincident lines                a ``nuclear_mask == 0`` rule crept in
zero F_⊥, symmetry-allowed             an amplitude rule (``systematic_absences``
                                       or a tolerance on |F_⊥|) crept in
no intensity is lost                   a row with magnetic intensity lost its
                                       window
same profile                           dropping rows moved the pattern beyond
                                       summation order
k = (0 0 ½)                            the nuclear rows still cost a magnetic
                                       window (the speed the rule exists for)
=====================================  ==========================================
"""

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.magnetic.operators import (
    MagneticGroup,
    magnetically_allowed,
)
from rietx.crystallography.magnetic.scattering import magnetic_family_rows
from rietx.model import forward
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from tests import _synthetic_crsbr as G
from tests.test_magnetic_width import SIZE, _mnf2, _state


def _covered(model, ip=0):
    win = model.phases[ip].win_mag
    return np.any(win[..., 1] > win[..., 0], axis=0)


def _magnetic_intensity(model, values, ip=0):
    return np.asarray(model.phase_peaks(ip, values, component=1)[0][3])


def test_a_row_is_kept_when_any_member_of_its_orbit_is_allowed():
    """P_a1: the anti-translation (½ 0 0)′ forbids h·t integer, allows h·t half-integer."""
    group = MagneticGroup.from_xyz(["x,y,z,+1"], ["x,y,z,+1", "x+1/2,y,z,-1"])
    assert magnetically_allowed(group, [[1, 0, 0], [0, 1, 0], [0, 0, 1]]).tolist() == [
        True, False, False]
    # row 0 lists the forbidden (0 1 0) first and the allowed (1 0 0) second;
    # row 1 has no allowed member
    members = np.array([[0, 1, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]])
    seg = np.array([0, 0, 1, 1])
    assert magnetic_family_rows(group, members, seg, 2).tolist() == [True, False]


def test_k0_rows_where_nuclear_and_magnetic_lines_coincide_keep_their_window():
    """MnF₂ (k = 0): magnetic intensity on nuclear rows is kept."""
    model, _t, v = _state(_mnf2(size=SIZE))
    nuclear = np.asarray(model.phases[0].nuclear_mask) == 1.0
    intensity = _magnetic_intensity(model, v)
    shared = nuclear & (intensity > 1e-6 * intensity.max())
    assert shared.sum() >= 2                       # (1 1 1), (2 1 0) measured
    assert np.all(_covered(model)[shared])


def test_a_symmetry_allowed_row_with_zero_perpendicular_moment_is_kept():
    """MnF₂ (0 0 1): the group allows M ∥ c there, and Q ∥ m makes F_⊥ exactly zero."""
    model, _t, v = _state(_mnf2(size=SIZE))
    hkl = [tuple(int(c) for c in h) for h in model.phases[0].reflections.hkl]
    row = hkl.index((0, 0, 1))
    assert _magnetic_intensity(model, v)[row] == 0.0
    assert _covered(model)[row]


def test_no_row_with_magnetic_intensity_loses_its_window():
    for phase in (_mnf2(size=SIZE), G.child_phase(size=G.SIZE)):
        st = rx.Structure(phases=[phase])
        if phase.name == "MnF2":
            model, _t, v = _state(phase)
        else:
            model = compile_model(st, G.instrument(), G.blank())
            table = ParameterTable(st, G.instrument())
            v = table.decode(table.x0())
        intensity = _magnetic_intensity(model, v)
        assert np.all(_covered(model)[intensity > 1e-12 * intensity.max()])


def test_dropping_the_forbidden_rows_leaves_the_profile_unchanged(monkeypatch):
    masked, _t, v = _state(_mnf2(size=SIZE))
    assert (~_covered(masked)).sum() == 2           # (2 0 0), (0 0 2)
    y_masked = np.asarray(masked.evaluate(v))
    monkeypatch.setattr(forward, "magnetic_family_rows",
                        lambda group, members, seg, n: np.ones(n, dtype=bool))
    every, _t2, v2 = _state(_mnf2(size=SIZE))
    assert _covered(every).all()
    y_every = np.asarray(every.evaluate(v2))
    assert np.max(np.abs(y_masked - y_every)) <= 1e-12 * np.max(np.abs(y_every))


def test_at_k_half_the_parent_lattice_rows_leave_the_magnetic_family():
    """CrSBr k = (0 0 ½), stated in the doubled cell: the anti-translation (0 0 ½)′
    forbids every row with l even, the parent's reciprocal lattice.

    Measured: 45 of 90 rows dropped, and ``nuclear_mask`` is 1 on all 90 (the
    phase's group is P m m n in the child cell), so a ``nuclear_mask == 0`` rule
    would have built the family on none of the magnetic rows.
    """
    st = rx.Structure(phases=[G.child_phase(size=G.SIZE)])
    model = compile_model(st, G.instrument(), G.blank())
    cp = model.phases[0]
    odd_l = cp.reflections.hkl[:, 2] % 2 == 1
    assert np.array_equal(cp.mag_rows, odd_l)
    assert np.array_equal(_covered(model), odd_l)
    assert int(odd_l.sum()) == 45 and len(odd_l) == 90
    assert np.all(np.asarray(cp.nuclear_mask) == 1.0)


@pytest.mark.parametrize("hkl", [[1, 0, 0], [0, 0, 1], [1, 1, 1]])
def test_the_decision_needs_no_floating_point(hkl, monkeypatch):
    """Exactness, structurally: the decision runs with numpy's float exp and SVD unusable."""
    def refuse(*_a, **_k):
        raise AssertionError("a floating-point route was taken")

    monkeypatch.setattr(np, "exp", refuse)
    monkeypatch.setattr(np.linalg, "svd", refuse)
    group = MagneticGroup.from_xyz(["x,y,z,+1"], ["x,y,z,+1", "x+1/2,y,z,-1"])
    assert magnetically_allowed(group, [hkl])[0] == (hkl[0] % 2 == 1)


def test_the_cached_power_residues_cannot_be_written_into():
    """The array is lru_cached and shared: a write by one caller would change every later answer."""
    from rietx.crystallography.magnetic.operators import _power_residues

    rows = _power_residues(6)
    assert not rows.flags.writeable
    with pytest.raises(ValueError):
        rows[0, 0] = 99
