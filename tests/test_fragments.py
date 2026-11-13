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
