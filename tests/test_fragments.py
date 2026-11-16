"""Fragments, declared bonds and the body frame (WP-1802): `crystallography/fragments.py`.

The oracles are geometry built here from ideal symmetry (a D6h benzene and a
D5h cyclopentadienyl, regular rings with radial hydrogens), a dihedral worked
by hand, and distances, angles and torsions measured by formulas written here,
not imported from the module under test.  The bond lengths are round
illustrative values; every assertion is about geometry, not about them.  The
Z-matrix's tangent (WP-1814) is checked against complex step through a
placement written here.
"""

from __future__ import annotations

import math
import re
from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography import fragments as fr

EPS = np.finfo(np.float64).eps


def _angle(a, b, c):
    """Angle a–b–c in degrees, by atan2 (well conditioned at 0° and 180°)."""
    u, v = np.asarray(a) - b, np.asarray(c) - b
    return math.degrees(math.atan2(np.linalg.norm(np.cross(u, v)), u @ v))


def _dihedral(a, b, c, d):
    """Torsion a–b–c–d in degrees: positive when, looking from b to c, the
    bond b–a turns clockwise onto c–d."""
    b1, b2, b3 = np.asarray(b) - a, np.asarray(c) - b, np.asarray(d) - c
    y = np.linalg.norm(b2) * (b1 @ np.cross(b2, b3))
    x = np.cross(b1, b2) @ np.cross(b2, b3)
    return math.degrees(math.atan2(y, x))


def _distances(xyz):
    x = np.asarray(xyz)
    return np.linalg.norm(x[:, None, :] - x[None, :, :], axis=2)


def _ideal_ring(n, cc, ch):
    """Ideal Dnh CnHn from geometry alone: a regular n-gon of side ``cc`` in the
    x–y plane, centred at the origin, each H radial at ``ch`` beyond its C."""
    rc = cc / (2.0 * math.sin(math.pi / n))
    phi = 2.0 * math.pi * np.arange(n) / n
    unit = np.stack([np.cos(phi), np.sin(phi), np.zeros(n)], axis=1)
    xyz = np.vstack([rc * unit, (rc + ch) * unit])
    bonds = [(k, (k + 1) % n) for k in range(n)] + [(k, n + k) for k in range(n)]
    return fr.Fragment(("C",) * n + ("H",) * n, xyz, bonds)


def _ring_zmatrix(ring, n):
    """Z-matrix lines for an n-ring + n H, read off ``ring``'s coordinates.

    References: each ring C from its predecessors along the ring, each H from
    its own C and the next two ring atoms.  The internal coordinates are
    measured here, so a round trip through :func:`fragments.from_zmatrix`
    must return the same geometry.
    """
    x = ring.xyz
    refs = [(), (0,), (1, 0)] + [(k - 1, k - 2, k - 3) for k in range(3, n)]
    refs += [(k, (k + 1) % n, (k + 2) % n) for k in range(n)]
    lines = []
    for i, ref in enumerate(refs):
        line = [ring.species[i]]
        if len(ref) >= 1:
            line += [ref[0], float(np.linalg.norm(x[i] - x[ref[0]]))]
        if len(ref) >= 2:
            line += [ref[1], _angle(x[i], x[ref[0]], x[ref[1]])]
        if len(ref) >= 3:
            line += [ref[2], _dihedral(x[i], x[ref[0]], x[ref[1]], x[ref[2]])]
        lines.append(tuple(line))
    return lines


# --- the fragment and its declared bonds -------------------------------------


def test_an_ideal_d6h_benzene_has_its_symmetry_and_three_rotation_dofs():
    """Built from D6h geometry (no printed coordinates): C–C and C–H uniform,
    every ring and H–C–C angle 120°, planar, and mapped onto itself by C6."""
    cc, ch = 1.39, 1.09
    benzene = _ideal_ring(6, cc, ch)
    x = benzene.xyz
    for i, j in benzene.bonds:
        want = cc if j < 6 else ch
        assert np.linalg.norm(x[i] - x[j]) == pytest.approx(want, rel=1e-14)
    for k in range(6):
        assert _angle(x[(k - 1) % 6], x[k], x[(k + 1) % 6]) == pytest.approx(120.0, abs=1e-12)
        assert _angle(x[6 + k], x[k], x[(k + 1) % 6]) == pytest.approx(120.0, abs=1e-12)
    np.testing.assert_array_equal(x[:, 2], 0.0)
    c6 = np.array([[0.5, -math.sqrt(3) / 2, 0], [math.sqrt(3) / 2, 0.5, 0], [0, 0, 1]])
    turned = x @ c6.T
    for k in range(12):   # each image is an atom of the same species
        j = int(np.argmin(np.linalg.norm(x - turned[k], axis=1)))
        assert np.linalg.norm(x[j] - turned[k]) < 1e-14 and benzene.species[j] == \
            benzene.species[k]
    frame = benzene.body_frame()
    np.testing.assert_allclose(frame.origin, 0.0, atol=1e-15)
    assert frame.rotation_dofs == 3
    np.testing.assert_array_equal(frame.rotation_axes, np.eye(3))


def test_bonds_are_declared_and_never_perceived():
    """WP-1319's rule: two atoms at a bonding distance declare nothing."""
    co = fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1.13]])
    assert co.bonds is None
    assert fr.Fragment(("C", "O"), co.xyz, bonds=()).bonds == ()
    assert fr.Fragment(("C", "O"), co.xyz, bonds=[(1, 0)]).bonds == ((0, 1),)
    # a Z-matrix's distance references are construction, not bonds
    lines = [("C",), ("O", 0, 1.13), ("H", 0, 1.1, 1, 120)]
    assert fr.from_zmatrix(lines).bonds is None
    assert fr.from_zmatrix(lines, bonds=[(0, 1), (0, 2)]).bonds == ((0, 1), (0, 2))


def test_a_fragment_is_frozen_and_validated():
    f = fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1.13]], bonds=[(1, 0)])
    assert f.bonds == ((0, 1),)
    with pytest.raises(ValueError):
        f.xyz[0, 0] = 1.0
    with pytest.raises(AttributeError):
        f.species = ("N", "O")
    with pytest.raises(ValueError, match="one row per species"):
        fr.Fragment(("C", "O"), [[0, 0, 0]])
    with pytest.raises(ValueError, match="distinct atoms"):
        fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1]], bonds=[(0, 2)])
    with pytest.raises(ValueError, match="twice"):
        fr.Fragment(("C", "O"), [[0, 0, 0], [0, 0, 1]], bonds=[(0, 1), (1, 0)])
    with pytest.raises(ValueError, match="non-finite"):
        fr.Fragment(("C",), [[0, 0, float("nan")]])


def test_the_coordinate_shape_is_checked_before_any_reshape():
    """A transposed (3, n) array has 3n elements too, and is refused, not
    scrambled; so are coordinates without species and a species string."""
    xyz = np.array([[0, 0, 0], [1.4, 0, 0], [2.1, 1.2, 0], [2.8, 1.2, 1.1]])
    assert np.array_equal(fr.Fragment(("C", "N", "O", "S"), xyz).xyz, xyz)
    with pytest.raises(ValueError, match=r"shape \(3, 4\); expected \(4, 3\)"):
        fr.Fragment(("C", "N", "O", "S"), xyz.T)
    with pytest.raises(ValueError, match=r"shape \(12,\); expected \(4, 3\)"):
        fr.Fragment(("C", "N", "O", "S"), xyz.ravel())
    with pytest.raises(ValueError, match=r"shape \(1, 3\); expected \(0, 3\)"):
        fr.Fragment((), [[1, 2, 3]])
    assert len(fr.Fragment((), [])) == 0
    with pytest.raises(ValueError, match="one string"):
        fr.Fragment("Fe", [[0, 0, 0], [0, 0, 1]])


def test_a_non_integer_bond_index_is_refused_not_truncated():
    """As a Z-matrix reference is (``test_z_matrix_lines_are_checked...``)."""
    xyz = [[0, 0, 0], [0, 0, 1.13]]
    assert fr.Fragment(("C", "O"), xyz, bonds=[(np.int64(0), 1.0)]).bonds == ((0, 1),)
    with pytest.raises(ValueError, match="integer atom indices"):
        fr.Fragment(("C", "O"), xyz, bonds=[(0, 1.9)])
    with pytest.raises(ValueError, match="integer atom indices"):
        fr.Fragment(("C", "O"), xyz, bonds=[(0, True)])
    with pytest.raises(ValueError, match="integer atom indices"):
        fr.from_zmatrix([("C",), ("O", 0, 1.13)], bonds=[(0, 1.9)])


# --- the body frame and the DOF count ----------------------------------------


def test_the_body_frame_is_the_centroid_and_the_template_axes():
    """Fragment-internal: the origin is the centroid wherever the template sits,
    and nothing about a cell enters it."""
    ring = _ideal_ring(5, 1.40, 1.08)
    shift = np.array([3.0, -1.5, 0.25])
    moved = fr.Fragment(ring.species, ring.xyz + shift, ring.bonds)
    frame = moved.body_frame()
    np.testing.assert_allclose(frame.origin, shift, atol=1e-15)
    assert frame.rotation_dofs == 3
    # full rank: the template's own axes, not an eigenbasis of I (which for a
    # general fragment is a rotated frame, and within a degeneracy arbitrary)
    skew = fr.Fragment(("C", "N", "O", "S"), [[0, 0, 0], [1.4, 0.2, -0.1],
                                             [-0.3, 1.1, 0.6], [0.5, -0.7, 1.3]])
    np.testing.assert_array_equal(skew.body_frame().rotation_axes, np.eye(3))
    with pytest.raises(ValueError):
        frame.origin[0] = 0.0
    with pytest.raises(ValueError):
        frame.rotation_axes[0, 0] = 0.0


def test_the_rotation_dof_count_is_the_inertia_rank_with_a_near_linear_tolerance():
    atom = fr.Fragment(("Fe",), [[0.3, 0.1, -0.2]])
    co2 = fr.Fragment(("O", "C", "O"), [[0, 0, -1.16], [0, 0, 0], [0, 0, 1.16]],
                      bonds=[(0, 1), (1, 2)])
    assert fr.rotation_dof_count(atom) == 0
    assert fr.rotation_dof_count(co2) == 2
    # linear: the two moving axes are perpendicular to the molecule's axis
    axes = co2.body_frame().rotation_axes
    np.testing.assert_allclose(axes @ [0.0, 0.0, 1.0], 0.0, atol=1e-15)
    np.testing.assert_allclose(axes @ axes.T, np.eye(2), atol=1e-15)
    # the tolerance: 4-decimal rounding stays linear, a 1° bend does not
    rng = np.random.default_rng(20260930)
    noisy = fr.Fragment(co2.species, co2.xyz + rng.uniform(-5e-5, 5e-5, (3, 3)))
    assert fr.rotation_dof_count(noisy) == 2
    t = math.radians(1.0)
    bent = fr.Fragment(co2.species, [[0, 0, 0], [0, 0, 1.16],
                                     [1.16 * math.sin(t), 0, -1.16 * math.cos(t)]])
    assert fr.rotation_dof_count(bent) == 3
    # two coincident atoms have no rotation either
    assert fr.rotation_dof_count(fr.Fragment(("O", "O"), [[1, 1, 1], [1, 1, 1]])) == 0


# --- Z-matrix ----------------------------------------------------------------


@pytest.mark.parametrize("n, cc, ch", [(5, 1.40, 1.08), (6, 1.39, 1.09)])
def test_an_ideal_ring_round_trips_through_its_z_matrix(n, cc, ch):
    """Cartesian → Z-matrix (measured here) → :func:`from_zmatrix` → the same geometry.

    n = 5 is the D5h cyclopentadienyl WP-1802 names; n = 6 is the D6h benzene.
    Every interatomic distance agrees to 1e-12 Å, so the result is the ideal
    ring up to a rigid motion, and it sits where the convention puts it.
    """
    ring = _ideal_ring(n, cc, ch)
    lines = _ring_zmatrix(ring, n)
    got = fr.from_zmatrix(lines, bonds=ring.bonds)
    assert got.species == ring.species and got.bonds == ring.bonds
    assert np.max(np.abs(_distances(got.xyz) - _distances(ring.xyz))) < 1e-12
    x = got.xyz
    assert np.array_equal(x[0], np.zeros(3))
    assert x[1, 0] == 0.0 and x[1, 1] == 0.0 and x[1, 2] > 0.0
    assert x[2, 1] == 0.0 and x[2, 0] > 0.0
    assert fr.rotation_dof_count(got) == 3


def test_a_non_planar_chain_round_trips_with_its_dihedral_signs():
    """The ring round trip compares distances, which a mirror image keeps, and a
    planar ring's torsions are 0° or 180°, whose sign is moot.  This chain is
    chiral: its torsions are about +60°, −90° and +150° (measured, not typed),
    and the rebuilt chain must have the same signed tetrahedral volumes, which
    a mirror image negates."""
    x = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [2.0, 1.4, 0.0],
                  [3.4, 1.6, 0.9], [3.9, 0.4, 1.8], [2.9, -0.6, 2.4],
                  [3.3, -2.0, 1.9]])
    lines = [("C",), ("C", 0, float(np.linalg.norm(x[1] - x[0])))]
    lines.append(("C", 1, float(np.linalg.norm(x[2] - x[1])), 0, _angle(x[2], x[1], x[0])))
    torsions = []
    for k in range(3, len(x)):
        tor = _dihedral(x[k], x[k - 1], x[k - 2], x[k - 3])
        torsions.append(tor)
        lines.append(("C", k - 1, float(np.linalg.norm(x[k] - x[k - 1])),
                      k - 2, _angle(x[k], x[k - 1], x[k - 2]), k - 3, tor))
    assert any(t > 20 for t in torsions) and any(t < -20 for t in torsions)
    got = fr.from_zmatrix(lines).xyz
    assert np.max(np.abs(_distances(got) - _distances(x))) < 1e-12

    def volumes(y):
        return np.array([np.linalg.det(np.array([y[j] - y[i] for j in q]))
                         for i in range(len(y)) for q in
                         [(a, b, c) for a in range(i + 1, len(y))
                          for b in range(a + 1, len(y)) for c in range(b + 1, len(y))]])

    vx = volumes(x)
    assert np.min(np.abs(vx)) > 0.0
    np.testing.assert_allclose(volumes(got), vx, rtol=0, atol=1e-11)
    for k in range(3, len(x)):
        assert _dihedral(*got[k - 3:k + 1][::-1]) == pytest.approx(torsions[k - 3],
                                                                   abs=1e-10)


def test_the_third_atom_is_in_the_xz_plane_on_the_positive_side():
    """The plane convention, pinned for a third atom bonded to either earlier atom.

    Bonded to the second atom at 120°, the third atom has z ≠ 0, so the "x–y
    plane" reading of the keyword page has no place for it.
    """
    to_first = fr.from_zmatrix([("O",), ("C", 0, 1.2), ("N", 0, 1.3, 1, 120)])
    to_second = fr.from_zmatrix([("O",), ("C", 0, 1.2), ("N", 1, 1.3, 0, 120)])
    for f in (to_first, to_second):
        assert f.xyz[2, 1] == 0.0 and f.xyz[2, 0] > 0.0
    assert to_second.xyz[2, 2] == pytest.approx(1.2 + 1.3 * 0.5, rel=1e-15)


def test_the_dihedral_sign_on_a_hand_worked_point():
    """D = 0, C on +z, B on +x from C, A at 90° with dihedral A–B–C–D = +90°.

    Worked by hand: the thumb C → B is +x; D − C = (0, 0, −1) rotated
    right-handed by 90° about +x is (0, 1, 0), so A = B + (0, 1, 0) = (1, 1, 1).
    Looking from B to C, B–A turns clockwise onto C–D: a positive torsion.
    """
    f = fr.from_zmatrix([("D",), ("C", 0, 1.0), ("B", 1, 1.0, 0, 90),
                         ("A", 2, 1.0, 1, 90, 0, 90)])
    np.testing.assert_allclose(f.xyz, [[0, 0, 0], [0, 0, 1], [1, 0, 1], [1, 1, 1]],
                               rtol=0, atol=1e-15)
    assert _dihedral(*f.xyz[::-1]) == pytest.approx(90.0, abs=1e-12)


def test_a_collinear_reference_triple_is_refused_naming_it():
    """Three atoms on the z axis cannot define a dihedral for a fourth.

    Bending the triple off the line is accepted, and so is a dummy point off
    the line used as the dihedral reference: the refusal is about the
    geometry, not the atoms.  A on the line B–C (a 180° bond angle) is not
    refused.
    """
    lines = [("C",), ("C", 0, 1.2), ("C", 1, 1.2, 0, 180),
             ("H", 2, 1.0, 1, 109.5, 0, 0)]
    with pytest.raises(ValueError, match=r"line 3 \(H\): reference atoms "
                       r"2 \(C\), 1 \(C\), 0 \(C\) are collinear"):
        fr.from_zmatrix(lines)
    bent = list(lines)
    bent[2] = ("C", 1, 1.2, 0, 170)
    assert len(fr.from_zmatrix(bent)) == 4
    X = fr.DUMMY
    fixed = fr.from_zmatrix([("C",), ("C", 0, 1.2), (X, 1, 1.0, 0, 90),
                             ("C", 1, 1.2, 0, 180, 2, 0),
                             ("H", 3, 1.0, 1, 109.5, 2, 0)],
                            bonds=[(0, 1), (1, 3), (3, 4)])
    assert fixed.species == ("C", "C", "C", "H")
    assert fixed.bonds == ((0, 1), (1, 2), (2, 3))
    np.testing.assert_allclose(fixed.xyz[2], [0.0, 0.0, 2.4], atol=1e-15)
    with pytest.raises(ValueError, match="dummy"):
        fr.from_zmatrix([("C",), ("C", 0, 1.2), (X, 1, 1.0, 0, 90)], bonds=[(1, 2)])


def test_acetylene_needs_no_dummy():
    """H–C≡C–H, every angle 180°: from the fourth line the reference triple is
    collinear, and a 180° angle makes the dihedral inert, so nothing is
    refused (module docstring, "Collinearity").  An angle short of 180° with
    the same collinear triple is still refused."""
    lines = [("H",), ("C", 0, 1.06), ("C", 1, 1.2, 0, 180),
             ("H", 2, 1.06, 1, 180, 0, 0)]
    f = fr.from_zmatrix(lines, bonds=[(0, 1), (1, 2), (2, 3)])
    np.testing.assert_allclose(f.xyz, [[0, 0, 0], [0, 0, 1.06], [0, 0, 2.26],
                                       [0, 0, 3.32]], rtol=0, atol=1e-15)
    assert fr.rotation_dof_count(f) == 2
    # the dihedral really is inert: any value gives the same molecule
    spun = list(lines)
    spun[3] = ("H", 2, 1.06, 1, 180, 0, 73.0)
    assert np.array_equal(fr.from_zmatrix(spun).xyz, f.xyz)
    # 0°: A folds back onto the C side of B
    back = fr.from_zmatrix(lines[:3] + [("H", 2, 0.5, 1, 0, 0, 0)])
    np.testing.assert_allclose(back.xyz[3], [0, 0, 1.76], rtol=0, atol=1e-15)
    bent = list(lines)
    bent[3] = ("H", 2, 1.06, 1, 179.0, 0, 0)
    with pytest.raises(ValueError, match="collinear"):
        fr.from_zmatrix(bent)


def test_z_matrix_lines_are_checked_before_they_are_placed():
    with pytest.raises(ValueError, match="line 1 .* takes 3"):
        fr.from_zmatrix([("C",), ("C", 0)])
    with pytest.raises(ValueError, match="not an earlier line"):
        fr.from_zmatrix([("C",), ("C", 1, 1.5)])
    with pytest.raises(ValueError, match="more than once"):
        fr.from_zmatrix([("C",), ("C", 0, 1.5), ("C", 1, 1.5, 1, 90)])
    with pytest.raises(ValueError, match="outside"):
        fr.from_zmatrix([("C",), ("C", 0, 1.5), ("C", 1, 1.5, 0, 190)])
    with pytest.raises(ValueError, match="integer line indices"):
        fr.from_zmatrix([("C",), ("C", 0.5, 1.5)])
    with pytest.raises(ValueError, match="not positive"):
        fr.from_zmatrix([("C",), ("C", 0, 0.0)])
    with pytest.raises(ValueError, match="not in the Z-matrix"):
        fr.from_zmatrix([("C",), ("C", 0, 1.5)], bonds=[(0, 2)])


# --- the Z-matrix's exact tangent (WP-1814 C2a) -------------------------------
#
# The oracle is complex step: for an analytic f, f′(x) = Im f(x + ih)/h with
# no subtractive cancellation, so at h = 1e-30 it is exact to rounding.  It is taken through a placement written
# here from the geometry (A = B + r·(−cos θ·û + sin θ·(cos φ·p̂ + sin φ·û×p̂)),
# the module docstring's convention, which the tests above pin), batched over
# the perturbed copies, never through the module under test.  The steps are in
# the stored units, Å and degrees, so a lost π/180 fails it.

_CS_H = 1e-30


def _cs_unit(v):
    return v / np.sqrt(np.sum(v * v, axis=-1, keepdims=True))


def _cs_place(b, c, d, r, th_deg, ph_deg):
    """The placement, complex-safe and batched: b, c, d (K, 3); r, θ, φ (K,)."""
    u = _cs_unit(b - c)
    w = d - c
    p = _cs_unit(w - np.sum(w * u, axis=-1, keepdims=True) * u)
    n = np.cross(u, p)
    th, ph = (np.asarray(th_deg) * (math.pi / 180.0))[:, None], \
        (np.asarray(ph_deg) * (math.pi / 180.0))[:, None]
    return b + np.asarray(r)[:, None] * (-np.cos(th) * u + np.sin(th) * (
        np.cos(ph) * p + np.sin(ph) * n))


def _cs_points(refs, values):
    """Every line's position for K value sets at once: values[i] is (K, len).

    At an angle of exactly 0° or 180° over a collinear B, C, D the line is
    B − r·cos θ·û, the only placement defined there; otherwise the general
    formula, whose θ-derivative at 0°/180° is the one-sided one inside [0, 180].
    """
    k = len(values[1]) if len(values) > 1 else 1
    pos = []
    for i, (ref, val) in enumerate(zip(refs, values, strict=True)):
        if i == 0:
            pos.append(np.zeros((k, 3), dtype=complex))
        elif i == 1:
            pos.append(np.stack([0 * val[:, 0], 0 * val[:, 0], val[:, 0]], axis=1))
        elif i == 2:
            b, c = pos[ref[0]], pos[ref[1]]
            pos.append(_cs_place(b, c, c + np.array([1.0, 0.0, 0.0]),
                                 val[:, 0], val[:, 1], 0 * val[:, 0]))
        else:
            b, c, d = (pos[j] for j in ref)
            th = float(val[0, 1].real)
            cb, cd = (b[0] - c[0]).real, (d[0] - c[0]).real
            sine = np.linalg.norm(np.cross(cb, cd)) / np.linalg.norm(cb) / np.linalg.norm(cd)
            if th in (0.0, 180.0) and sine < fr.COLLINEAR_TOL:
                cos_t = np.cos(val[:, 1] * (math.pi / 180.0))[:, None]
                pos.append(b - val[:, 0][:, None] * cos_t * _cs_unit(b - c))
            else:
                pos.append(_cs_place(b, c, d, val[:, 0], val[:, 1], val[:, 2]))
    return np.stack(pos, axis=1)                      # (K, n, 3)


def _cs_tangent(refs, values):
    """(m, n, 3) by complex step: copy j steps internal j by i·h."""
    flat = [v for val in values for v in val]
    m = len(flat)
    batched, col = [], 0
    for val in values:
        a = np.tile(np.asarray(val, dtype=complex), (m, 1))
        for q in range(len(val)):
            a[col + q, q] += 1j * _CS_H
        col += len(val)
        batched.append(a)
    return _cs_points(refs, batched).imag / _CS_H


def _split(lines):
    """Z-matrix lines → (species, refs, values) as :func:`zmatrix_points` takes them."""
    return ([ln[0] for ln in lines], [tuple(int(k) for k in ln[1::2]) for ln in lines],
            [tuple(float(v) for v in ln[2::2]) for ln in lines])


# The 8-atom fragment of #759: references that are not a chain (line 4 from
# 0, 1, 2; line 5 through 4), a 180° dihedral and a methyl pair.
_BRANCHED = [("C",), ("C", 0, 1.51), ("O", 1, 1.43, 0, 109.5),
             ("C", 1, 1.50, 0, 112.7, 2, 122.5), ("O", 0, 1.27, 1, 117.4, 2, 10.0),
             ("O", 0, 1.27, 1, 117.4, 4, 180.0), ("H", 3, 0.96, 1, 109.5, 0, 180.0),
             ("H", 3, 0.96, 1, 109.5, 0, -60.0)]
# A dummy, and two lines at exactly 180° whose reference triple is open.
_DUMMY_180 = [("C",), ("C", 0, 1.20), (fr.DUMMY, 1, 1.0, 0, 90.0),
              ("H", 1, 1.06, 0, 180.0, 2, 0.0), ("H", 0, 1.06, 1, 180.0, 2, 37.0),
              ("O", 1, 1.4, 2, 95.0, 0, -100.0)]


def _acridine_lines():
    """Acridine (COD 2242872, ``tests/data/README.md``) as a Z-matrix.

    The fixture's own construction, not the module's: bonds are read off the
    deposited distances here (heavy–heavy < 1.6 Å, X–H < 1.2 Å) to grow a
    breadth-first spanning tree, and each line's internals are measured with
    this file's ``_angle`` and ``_dihedral``.  Returns the lines and the
    deposited Cartesian atoms in line order.
    """
    from rietx.crystallography.cif import structure_from_cif
    from rietx.params.derived import cartesian_frame

    path = Path(__file__).parent / "data" / "cod_2242872.cif"
    phase = structure_from_cif(str(path)).phases[0]
    m = np.asarray(cartesian_frame(phase.cell.lengths_angles()))
    sp = [a.species for a in phase.atoms]
    x = np.array([m @ [a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    dist = _distances(x)
    heavy = [i for i, s in enumerate(sp) if not s.startswith("H")]

    def bonded(i, j):
        h = sp[i].startswith("H") or sp[j].startswith("H")
        return i != j and dist[i, j] < (1.2 if h else 1.6)

    parent, order = {heavy[0]: -1}, [heavy[0]]
    for i in order:                                   # grows while it walks
        for j in range(len(x)):
            if j not in parent and bonded(i, j):
                parent[j] = i
                order.append(j)
    line_of, lines = {}, []
    for i in order:
        k = len(lines)
        line_of[i] = k
        if k == 0:
            lines.append((sp[i],))
            continue
        b = parent[i]
        r = float(np.linalg.norm(x[i] - x[b]))
        if k == 1:
            lines.append((sp[i], line_of[b], r))
            continue
        placed = [j for j in order[:k] if j != b]
        c = parent[b] if parent[b] >= 0 else placed[0]
        ang = _angle(x[i], x[b], x[c])
        if k == 2:
            lines.append((sp[i], line_of[b], r, line_of[c], ang))
            continue
        d = next(j for j in placed if j != c and np.linalg.norm(np.cross(
            x[b] - x[c], x[j] - x[c])) / np.linalg.norm(x[b] - x[c])
            / np.linalg.norm(x[j] - x[c]) > 0.1)
        lines.append((sp[i], line_of[b], r, line_of[c], ang, line_of[d],
                      _dihedral(x[i], x[b], x[c], x[d])))
    return lines, x[order]


def _states(lines, rng, n):
    """The anchor, then ``n`` random states: r ± 0.05 Å, angles and dihedrals
    ± 5°, an angle kept inside (1°, 179°) unless it sits on 0° or 180°."""
    _, refs, values = _split(lines)
    yield values
    for _ in range(n):
        out = []
        for val in values:
            v = list(val)
            if v:
                v[0] += rng.normal(scale=0.05)
            if len(v) > 1 and v[1] not in (0.0, 180.0):
                v[1] = float(np.clip(v[1] + rng.normal(scale=5.0), 1.0, 179.0))
            if len(v) > 2:
                v[2] += rng.normal(scale=5.0)
            out.append(tuple(v))
        yield out


def test_zmatrix_placement_partials_match_complex_step():
    """The six closed-form partials of one placement against complex step,
    on 100 random draws: < 1e-12 on every block (WP-1814's first bar)."""
    rng = np.random.default_rng(20261109)
    worst = dict.fromkeys(("B", "C", "D", "r", "angle", "dihedral"), 0.0)
    draws = 0
    while draws < 100:
        b, c, d = (rng.normal(size=3) * 1.5 for _ in range(3))
        if np.linalg.norm(np.cross(b - c, d - c)) / np.linalg.norm(b - c) \
                / np.linalg.norm(d - c) < 1e-3:
            continue
        draws += 1
        r, th, ph = rng.uniform(0.9, 2.2), rng.uniform(5.0, 175.0), rng.uniform(-180, 180)
        got = dict(zip(worst, fr._place_partials(b, c, d, r, th, ph), strict=True))
        a = fr._place(b, c, d, r, th, ph)
        assert np.max(np.abs(a - _cs_place(b[None], c[None], d[None], [r], [th],
                                           [ph])[0].real)) < 1e-14
        # 12 copies: B, C, D's three components, then r, θ, φ
        args = [np.tile(np.asarray(v, dtype=complex), (12, 1)) for v in (b, c, d)]
        args += [np.full(12, complex(v)) for v in (r, th, ph)]
        for q in range(9):
            args[q // 3][q, q % 3] += 1j * _CS_H
        for q in range(3):
            args[3 + q][9 + q] += 1j * _CS_H
        cs = _cs_place(*args).imag / _CS_H                # (12, 3)
        want = {"B": cs[0:3].T, "C": cs[3:6].T, "D": cs[6:9].T,
                "r": cs[9], "angle": cs[10], "dihedral": cs[11]}
        for key in worst:
            worst[key] = max(worst[key], float(np.max(np.abs(got[key] - want[key]))))
    assert max(worst.values()) < 1e-12, worst


def test_zmatrix_placement_partials_on_a_hand_worked_point():
    """D = 0, C on +z, B on +x from C, A = (1, 1, 1): the angle A–B–C is 90°
    and the dihedral +90° (the hand-worked point above).  By hand: r moves A
    along B → A, (0, 1, 0); opening the angle turns B → A away from B → C =
    −x, towards +x; the dihedral turns A right-handed about C → B = +x, so
    x̂ × (0, 1, 0) = +z.  Per degree, both angles carry π/180."""
    b, c, d = np.array([1.0, 0, 1]), np.array([0.0, 0, 1]), np.zeros(3)
    *_, d_r, d_th, d_ph = fr._place_partials(b, c, d, 1.0, 90.0, 90.0)
    deg = math.pi / 180.0
    np.testing.assert_allclose(d_r, [0, 1, 0], rtol=0, atol=1e-15)
    np.testing.assert_allclose(d_th, [deg, 0, 0], rtol=0, atol=1e-17)
    np.testing.assert_allclose(d_ph, [0, 0, deg], rtol=0, atol=1e-17)


@pytest.mark.parametrize("name", ["branched", "dummy_180", "acridine"])
def test_zmatrix_tangent_matches_complex_step(name):
    """The whole template's tangent against complex step, < 1e-12·max|J|, at
    the anchor and at 50 random states; the positions are
    :func:`from_zmatrix`'s, bit for bit, on every line it keeps.

    Branched references, a dummy with two lines at exactly 180° (the angle's
    column there is the one-sided derivative inside [0, 180]), and acridine,
    23 atoms and 63 internals."""
    lines = {"branched": _BRANCHED, "dummy_180": _DUMMY_180}.get(name)
    if lines is None:
        lines, deposited = _acridine_lines()
        assert len(lines) == 23
        # the fixture is acridine: every distance of the rebuilt template
        assert np.max(np.abs(_distances(fr.from_zmatrix(lines).xyz)
                             - _distances(deposited))) < 1e-10
    species, refs, _ = _split(lines)
    keep = [i for i, s in enumerate(species) if s != fr.DUMMY]
    rng = np.random.default_rng(1814)
    worst = 0.0
    for values in _states(lines, rng, 50):
        pos, tan = fr.zmatrix_points(refs, values, tangents=True)
        assert tan.shape == (sum(len(v) for v in values), len(lines), 3)
        typed = [(s, *[x for pair in zip(rf, v, strict=True) for x in pair])
                 for s, rf, v in zip(species, refs, values, strict=True)]
        assert np.array_equal(pos[keep], fr.from_zmatrix(typed).xyz)
        want = _cs_tangent(refs, values)
        worst = max(worst, float(np.max(np.abs(tan - want)) / np.max(np.abs(want))))
    assert worst < 1e-12, worst


def test_zmatrix_tangent_over_a_collinear_triple_at_180():
    """H–C≡C–H: from line 3 the triple is collinear and only 180° is
    admissible, so the angle's and the dihedral's columns are zero and the
    line follows B and C alone; the r columns are complex step's."""
    lines = [("H",), ("C", 0, 1.06), ("C", 1, 1.2, 0, 180.0),
             ("H", 2, 1.06, 1, 180.0, 0, 0.0)]
    _, refs, values = _split(lines)
    pos, tan = fr.zmatrix_points(refs, values, tangents=True)
    np.testing.assert_array_equal(pos, fr.from_zmatrix(lines).xyz)
    np.testing.assert_array_equal(tan[[4, 5], 3], 0.0)   # line 3's angle, dihedral
    np.testing.assert_allclose(tan, _cs_tangent(refs, values), rtol=0, atol=1e-15)
    # every r column moves the far H along the axis by exactly one Å per Å
    np.testing.assert_allclose(tan[[0, 1, 3], 3], [[0, 0, 1]] * 3, rtol=0, atol=1e-15)


@pytest.mark.parametrize("name", ["branched", "dummy_180", "acridine"])
def test_zmatrix_reach_covers_every_line_the_tangent_moves(name):
    """A column is zero outside its line's reach, at the anchor and 20
    random states; on the branched fragment the reach is checked by hand."""
    lines = {"branched": _BRANCHED, "dummy_180": _DUMMY_180}.get(name)
    if lines is None:
        lines, _ = _acridine_lines()
    _, refs, _ = _split(lines)
    reach = fr.zmatrix_reach(refs)
    owner = [i for i, ref in enumerate(refs) for _ in ref]
    for values in _states(lines, np.random.default_rng(7), 20):
        _, tan = fr.zmatrix_points(refs, values, tangents=True)
        moved = np.any(tan != 0.0, axis=2)               # (m, n)
        for j, i in enumerate(owner):
            assert set(np.flatnonzero(moved[j])) <= reach[i], (j, i)
    if name == "branched":
        assert reach == (frozenset(), frozenset(range(1, 8)), frozenset(range(2, 8)),
                         frozenset({3, 6, 7}), frozenset({4, 5}), frozenset({5}),
                         frozenset({6}), frozenset({7}))


def test_zmatrix_points_refuses_by_line_with_or_without_names():
    """Without names the refusal says the line and the indices; with them it
    is :func:`from_zmatrix`'s, word for word."""
    refs = [(), (0,), (1, 0), (2, 1, 0)]
    values = [(), (1.2,), (1.2, 180.0), (1.0, 109.5, 0.0)]
    with pytest.raises(ValueError, match=r"^Z-matrix line 3: reference atoms 2, 1, 0 "
                       r"are collinear"):
        fr.zmatrix_points(refs, values)
    with pytest.raises(ValueError, match=r"line 3 \(H\): reference atoms 2 \(C\), "
                       r"1 \(C\), 0 \(C\) are collinear"):
        fr.zmatrix_points(refs, values, names=["C", "C", "C", "H"])
    with pytest.raises(ValueError, match="line 2 has 2 references and 1 values"):
        fr.zmatrix_points(refs, [(), (1.2,), (1.2,), (1.0, 109.5, 0.0)])
    with pytest.raises(ValueError, match="3 reference rows for 2 value rows"):
        fr.zmatrix_points(refs[:3], values[:2])
    assert fr.zmatrix_points([], []).shape == (0, 3)
    pos, tan = fr.zmatrix_points([()], [()], tangents=True)
    assert pos.shape == (1, 3) and tan.shape == (0, 1, 3)


# --- XYZ read (WP-1813) -------------------------------------------------------


def _xyz_text(fragment, comment="a comment line, ignored"):
    """The bare XYZ text of ``fragment``, written here at repr precision."""
    rows = [f"{s} {x!r} {y!r} {z!r}" for s, (x, y, z) in
            zip(fragment.species, fragment.xyz.tolist(), strict=True)]
    return "\n".join([str(len(fragment)), comment, *rows]) + "\n"


def test_an_ideal_benzene_round_trips_through_xyz_with_its_bonds_declared(tmp_path):
    """The file's coordinates come back bit for bit, in file order; its bonds
    are the caller's, and a read without them declares none."""
    ring = _ideal_ring(6, 1.39, 1.09)
    path = tmp_path / "benzene.xyz"
    path.write_text(_xyz_text(ring) + "\n\n", encoding="utf-8")
    back = fr.read_xyz(path, bonds=ring.bonds)
    assert back.species == ring.species
    assert np.array_equal(back.xyz, ring.xyz)
    assert back.bonds == ring.bonds
    assert fr.read_xyz(path).bonds is None
    assert fr.from_xyz(_xyz_text(ring)).body_frame().rotation_dofs == 3


def test_an_xyz_element_reads_as_its_standard_symbol():
    """An atomic number or a symbol in any case is stored as the standard
    spelling; CRLF line ends and a byte-order mark read like plain ones."""
    f = fr.from_xyz("\ufeff3\r\n\r\n8 0 0 0\r\n1 0.96 0 0\r\nh -.24 +.93 0e0\r\n")
    assert f.species == ("O", "H", "H")
    assert fr.from_xyz("1\nc\nfe 1.5E-1 0. 0\n").species == ("Fe",)
    assert fr.from_xyz("1\nc\nCA 0 0 0\n").species == ("Ca",)
    assert fr.from_xyz("0\nempty\n").xyz.shape == (0, 3)


@pytest.mark.parametrize("text, match", [
    ("", r"^XYZ text: line 1 must hold the atom count; it is empty"),
    ("two\nc\n", r"line 1 must hold the atom count, a non-negative integer; "
                 r"it reads 'two'"),
    ("-1\nc\n", r"non-negative integer; it reads '-1'"),
    ("3\nc\nC 0 0 0\nC 1 0 0\n", r"line 1 counts 3 atoms but the file has 2 atom lines"),
    ("1\nc\nC 0 0\n", r"line 3: an atom line holds an element and three coordinates "
                      r"\(4 fields\); it has 3"),
    ("1\nc\nC 0 0 0 0.5\n", r"line 3: .* it has 5"),
    ("1\nc\nC 0 zero 0\n", r"line 3: a coordinate is not a decimal number"),
    ("1\nc\nC 0 inf 0\n", r"line 3: a coordinate is not a decimal number"),
    ("1\nc\nC 0 nan 0\n", r"line 3: a coordinate is not a decimal number"),
    ("1\nc\nC 1_0 0 0\n", r"line 3: a coordinate is not a decimal number"),
    ("1\nc\nC 1.0D0 0 0\n", r"line 3: a coordinate is not a decimal number"),
    ("1_0\nc\n", r"non-negative integer; it reads '1_0'"),
    ("1\nc\nC 1e400 0 0\n", r"line 3: a coordinate overflows a double"),
    ("1\nc\nC1 0 0 0\n", r"line 3: 'C1' is not an element symbol"),
    # gemmi reads a token's leading letters, so each of these would be an
    # element (Ca, Ni, Fe, Cl, Ca, He, Na) if the whole token went unchecked
    *[(f"1\nc\n{tok} 0 0 0\n", rf"line 3: '{re.escape(tok)}' is not an element symbol")
      for tok in ("Carbon", "Nitrogen", "Fe3", "Cl1", "Ca2", "He2+", "Na+")],
    ("1\nc\nX 0 0 0\n", r"line 3: 'X' is not an element symbol \(it is the Z-matrix dummy\)"),
    ("1\nc\n119 0 0 0\n", r"line 3: atomic number 119 is not 1–118"),
    ("1\nc\n0 0 0 0\n", r"line 3: atomic number 0 is not 1–118"),
    ("1\nc\nC 0 0 0\n1\nc\nC 1 0 0\n", r"line 4: text after the 1 atoms of line 1's "
                                       r"count .* this reader takes one frame"),
])
def test_an_xyz_file_that_is_not_one_bare_frame_is_refused_by_line(text, match):
    with pytest.raises(ValueError, match=match):
        fr.from_xyz(text)


def test_an_xyz_refusal_names_the_file(tmp_path):
    bom = tmp_path / "bom.xyz"
    bom.write_text("1\nc\nC 0 0 0\n", encoding="utf-8-sig")
    assert fr.read_xyz(bom).species == ("C",)
    path = tmp_path / "short.xyz"
    path.write_text("2\nc\nC 0 0 0\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"short\.xyz: line 1 counts 2 atoms"):
        fr.read_xyz(path)


# --- Z-matrix write (WP-1813) -------------------------------------------------


def _volumes(y):
    """Signed volumes of every ordered quadruple i < a < b < c; a mirror image
    negates all of them, a rigid motion keeps them."""
    y = np.asarray(y)
    n = len(y)
    return np.array([np.linalg.det(np.array([y[a] - y[i], y[b] - y[i], y[c] - y[i]]))
                     for i in range(n) for a in range(i + 1, n)
                     for b in range(a + 1, n) for c in range(b + 1, n)])


def _rotated(xyz, seed):
    """``xyz`` under a random proper rotation and shift, so no line of the
    written Z-matrix can lean on the template's own frame."""
    q, r = np.linalg.qr(np.random.default_rng(seed).normal(size=(3, 3)))
    q = q @ np.diag(np.sign(np.diag(r)))
    if np.linalg.det(q) < 0:
        q[:, 0] = -q[:, 0]
    return np.asarray(xyz) @ q.T + np.array([3.1, -0.7, 12.4])


def _chiral_chain():
    """The non-planar chain of the round-trip test above, torsions +60°, −90°
    and +150°, with two hydrogens on its second carbon to branch it."""
    x = np.array([[0.0, 0.0, 0.0], [1.5, 0.0, 0.0], [2.0, 1.4, 0.0],
                  [3.4, 1.6, 0.9], [3.9, 0.4, 1.8], [2.9, -0.6, 2.4],
                  [3.3, -2.0, 1.9], [1.9, -0.5, -0.9], [1.6, -0.6, 0.9]])
    bonds = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 6), (1, 7), (1, 8)]
    return fr.Fragment(("C",) * 7 + ("H", "H"), x, bonds)


@pytest.mark.parametrize("make", [lambda: _ideal_ring(6, 1.39, 1.09),
                                  lambda: _ideal_ring(5, 1.40, 1.08), _chiral_chain],
                         ids=["benzene", "cyclopentadienyl", "chiral-chain"])
@pytest.mark.parametrize("with_bonds", [True, False])
def test_a_fragment_round_trips_through_its_written_z_matrix(make, with_bonds):
    """to_zmatrix → from_zmatrix rebuilds the fragment up to a proper rigid
    motion: every distance to 1e-12 Å and every signed volume to 1e-11 Å³
    (a mirror image would negate them), from a frame the writer never saw."""
    f = make()
    moved = fr.Fragment(f.species, _rotated(f.xyz, 3), f.bonds if with_bonds else None)
    lines = fr.to_zmatrix(moved)
    assert [line[0] for line in lines] == list(f.species)
    assert [len(line) for line in lines] == [1, 3, 5] + [7] * (len(f) - 3)
    back = fr.from_zmatrix(lines, bonds=moved.bonds)
    assert back.bonds == moved.bonds
    assert np.max(np.abs(_distances(back.xyz) - _distances(f.xyz))) < 1e-12
    np.testing.assert_allclose(_volumes(back.xyz), _volumes(f.xyz), rtol=0, atol=1e-11)


def test_the_written_internals_are_the_ones_read():
    """from_zmatrix(lines) → to_zmatrix with the same references returns the
    same internal coordinates: the angle and the dihedral sign are the
    reader's convention, not a mirror of it."""
    lines = [("N",), ("C", 0, 1.47), ("C", 1, 1.53, 0, 110.0),
             ("O", 2, 1.21, 1, 121.0, 0, -37.5), ("O", 2, 1.31, 1, 113.0, 3, 179.0),
             ("H", 0, 1.01, 1, 109.0, 2, 62.0), ("H", 0, 1.01, 1, 109.0, 5, -118.0)]
    f = fr.from_zmatrix(lines)
    refs = [tuple(line[1::2]) for line in lines]
    got = fr.to_zmatrix(f, refs=refs)
    for want, have in zip(lines, got, strict=True):
        assert have[0] == want[0] and have[1::2] == want[1::2]
        np.testing.assert_allclose(have[2::2], want[2::2], rtol=0, atol=1e-10)


def test_declared_bonds_choose_the_references():
    """With bonds declared, each benzene H is written from its own carbon even
    where another atom is nearer in index; without them the nearest earlier
    atom is chosen, which for a ring H is its carbon too."""
    ring = _ideal_ring(6, 1.39, 1.09)
    for f in (ring, fr.Fragment(ring.species, ring.xyz, None)):
        lines = fr.to_zmatrix(f)
        assert [line[1] for line in lines[6:]] == [0, 1, 2, 3, 4, 5]
    # an ordering where the nearest earlier atom is not the bonded one
    x = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.5, 0.9, 0.0], [0.3, 0.2, 1.4]])
    near = fr.to_zmatrix(fr.Fragment(("C", "C", "C", "H"), x))
    far = fr.to_zmatrix(fr.Fragment(("C", "C", "C", "H"), x, [(0, 1), (1, 2), (2, 3)]))
    assert near[3][1] == 0 and far[3][1] == 2


def test_acetylene_is_written_at_exactly_180_degrees():
    """A linear molecule in a tilted frame: every angle is written as exactly
    180° (the sine is ~1e-16, under COLLINEAR_TOL), which from_zmatrix accepts
    with an inert dihedral, so the round trip needs no dummy."""
    x = _rotated([[0, 0, 0], [0, 0, 1.06], [0, 0, 2.26], [0, 0, 3.32]], 5)
    lines = fr.to_zmatrix(fr.Fragment(("H", "C", "C", "H"), x))
    assert lines[2][4] == 180.0 and lines[3][4] == 180.0 and lines[3][6] == 0.0
    back = fr.from_zmatrix(lines)
    np.testing.assert_allclose(back.xyz[:, 2], [0, 1.06, 2.26, 3.32], rtol=0, atol=1e-12)


def test_the_writer_refuses_what_from_zmatrix_cannot_read():
    """An atom off a line every earlier atom lies on has no dihedral reference
    without a dummy; a dummy species would be dropped on the way back; a
    given reference that is collinear or not earlier is refused with the
    placement's words."""
    line_then_off = fr.Fragment(("C", "C", "C", "H"),
                                [[0, 0, 0], [0, 0, 1.2], [0, 0, 2.4], [1.0, 0, 2.6]])
    with pytest.raises(ValueError, match=r"atom 3 \(H\) is off the line that atoms "
                       r"0–2 lie on"):
        fr.to_zmatrix(line_then_off)
    # the same atoms with the off-line atom earlier write and read back
    reordered = fr.Fragment(("C", "H", "C", "C"),
                            line_then_off.xyz[[0, 3, 1, 2]])
    back = fr.from_zmatrix(fr.to_zmatrix(reordered))
    assert np.max(np.abs(_distances(back.xyz) - _distances(reordered.xyz))) < 1e-12
    with pytest.raises(ValueError, match=r"atom 1 has species 'X', the Z-matrix dummy"):
        fr.to_zmatrix(fr.Fragment(("C", fr.DUMMY), [[0, 0, 0], [0, 0, 1]]))
    with pytest.raises(ValueError, match=r"line 3 \(H\): reference atoms 2 \(C\), "
                       r"1 \(C\), 0 \(C\) are collinear"):
        fr.to_zmatrix(line_then_off, refs=[(), (0,), (1, 0), (2, 1, 0)])
    with pytest.raises(ValueError, match=r"line 2 \(C\) takes 2 earlier atom indices"):
        fr.to_zmatrix(line_then_off, refs=[(), (0,), (1, 2), (2, 1, 0)])
    with pytest.raises(ValueError, match=r"line 1 \(C\) takes 1 earlier atom indices"):
        fr.to_zmatrix(line_then_off, refs=[(), (None,), (1, 0), (2, 1, 0)])
    for k in (float("inf"), float("nan")):
        with pytest.raises(ValueError, match=r"line 3 \(H\) takes 3 earlier atom indices"):
            fr.to_zmatrix(line_then_off, refs=[(), (0,), (1, 0), (2, 1, k)])
    with pytest.raises(ValueError, match="3 reference rows for 4 atoms"):
        fr.to_zmatrix(line_then_off, refs=[(), (0,), (1, 0)])
    assert fr.to_zmatrix(fr.Fragment((), np.zeros((0, 3)))) == []


def test_the_writer_never_takes_a_triple_its_own_write_made_collinear():
    """Atom 2 is 0.8e-6 of a radian off the line 0–1 at atom 0, so it is
    written at exactly 0°, onto that line.  The triple 0, 2, 1 has a sine of
    1.2e-6 at atom 2 on the positions as given, but is collinear as written:
    the chooser must not take it for atom 3, and with no other triple it
    refuses with advice to_zmatrix can follow (no dummy, which it refuses).
    The same atoms with the H first write and read back."""
    x = np.array([[0, 0, 0], [0, 0, 3], [8e-7, 0, 1], [0.9, 0.5, -0.2]])
    f = fr.Fragment(("C", "C", "C", "H"), x)
    with pytest.raises(ValueError, match=r"atom 3 \(H\) is off the line that atoms "
                       r"0–2 lie on.*earlier in the order$"):
        fr.to_zmatrix(f)
    # the triple given by hand is refused by the placement, with the writer's advice
    with pytest.raises(ValueError, match=r"^to_zmatrix: Z-matrix line 3 \(H\): "
                       r"reference atoms 0 \(C\), 2 \(C\), 1 \(C\) are collinear.*"
                       r"pass refs .* or put an atom off that line earlier in the order$"):
        fr.to_zmatrix(f, refs=[(), (0,), (0, 1), (0, 2, 1)])
    first = fr.Fragment(("H", "C", "C", "C"), x[[3, 0, 1, 2]])
    back = fr.from_zmatrix(fr.to_zmatrix(first))
    assert np.max(np.abs(_distances(back.xyz) - _distances(first.xyz))) < 1e-12


def test_the_writer_takes_the_best_conditioned_dihedral_reference():
    """Atom 4 sits 1e-6 of a radian off the line 1–0 and is written at exactly
    180°, which moves it ~1e-6 Å; the triple 2, 3, 4 is then barely off its
    line (sine ~1e-6), so a dihedral measured from it would turn by O(1) on the
    way back (0.22 Å in the distances).  The chooser takes the triple furthest
    from a line, and the round trip keeps only the write's own ~r·1e-6 Å."""
    h, a = 0.99e-6, 3.05e-6
    x = np.array([[-2, 0, -h], [-1, 0, -h], [0, -1.5, 0], [0, -3, 0], [a, 0, 0],
                  [0.3, -1.2, 1.1]])
    f = fr.Fragment(("C",) * 6, x)
    lines = fr.to_zmatrix(f)
    assert lines[4][4] == 180.0
    back = fr.from_zmatrix(lines)
    assert np.max(np.abs(_distances(back.xyz) - _distances(x))) < 5 * fr.COLLINEAR_TOL
    # the same line written from the ill-conditioned triple, as a caller may
    refs = [tuple(line[1::2]) for line in lines]
    refs[5] = (2, 3, 4)
    bad = fr.from_zmatrix(fr.to_zmatrix(f, refs=refs))
    assert np.max(np.abs(_distances(bad.xyz) - _distances(x))) > 0.1
