"""The metric of a child cell: the parent's cell carried through P, plus the Γ strains.

A child of a parent structure (a superstructure, a distortion, a magnetic
supercell) is stated in a cell whose basis is P in the parent's,
(a′, b′, c′) = (a, b, c)·P, and whose metric is therefore

    G′ = Pᵀ·(G_parent + Δ)·P,

where G_parent is invariant under the parent's point group and Δ is the
**lattice strain** the lower symmetry allows.  The strain is a Γ-point
order parameter of its own: a polar symmetrised second-rank tensor
(Campbell, Stokes, Tanner & Hatch 2006, *J. Appl. Cryst.* 39, 607, § 4.5,
p. 611), present in the child exactly when it is invariant under the child's
point group H and absent from the parent, i.e. in

    S = {Δ : RᵀΔR = Δ for every R in H} ∩ ker ⟨·⟩_parent,

where ⟨Δ⟩_parent = (1/|K|) Σ_{R∈K} RᵀΔR is the Reynolds average over the
parent's point group K.  ⟨·⟩_parent fixes every parent-invariant metric and
maps the H-invariant ones onto them, so the H-invariant metric subspace is
exactly the parent-invariant one ⊕ S, and the split is unique: a parent cell
and a set of strain amplitudes name every metric the child's symmetry allows,
once.  That is the "metric subspace" #293 asked for, in the form #746 settled
on (the parent's cell refined under its own constraints, the child's derived,
a strain freed only where the data show one), the convention TOPAS's
mode-amplitude refinement uses (Campbell, Evans, Perselli & Stokes 2007,
*IUCr Comput. Comm. Newsl.* 8, 81).

**The strain is dimensionless and exact.**  Δ = 2·L·E·L with L = diag(a, b, c)
of the parent and E = Σⱼ sⱼ·Eⱼ.  For a parent whose cell angles its symmetry
fixes, M·L⁻¹ is a constant frame N (unit-length columns), so
E_cart = N⁻ᵀ·E·N⁻¹ and G′ = Pᵀ·Mᵀ(I + 2E_cart)M·P: E_cart is the
Green–Lagrange strain of the parent's Cartesian frame (x ∥ a, z ∥ a × b),
exactly, at any size — the definition E = ½(FᵀF − I) with FᵀF read off the
metric, no linearisation.  The basis Eⱼ is orthonormal in that frame
(Σ_ik E_ik² = 1), so sⱼ is a strain amplitude.  For a parent with a free
angle (monoclinic, triclinic, rhombohedral axes) the frame N moves with the
angle, so the basis is orthonormalised at 90° in the free angle(s) and sⱼ is
the length-normalised metric change; the map stays exact either way.

**Why the length scaling is legitimate.**  L·S·L = S needs every parent
rotation to mix only axes of equal length, and in a tabulated setting it does
(signed permutations among tied axes; the hexagonal a–b block, where L is a·I).
:func:`strain_basis` checks it rather than assumes it.  Because the scaling is
by the parent's *current* lengths, the basis Eⱼ is a constant of the group and
the transform, never of the cell: a rebuild at a moved cell reproduces the
same child metric from the same amplitudes.
"""

from __future__ import annotations

from fractions import Fraction
from itertools import product

import numpy as np

from .wyckoff import _VOIGT, _nullspace_int, adp_basis

#: |cos| this close to an exact value a lattice symmetry can force (0, ±½) is
#: snapped onto it — see :func:`cell_from_metric`.
COSINE_SNAP = 1e-12


def rotations_of(group) -> list[np.ndarray]:
    """The distinct integer rotation matrices of a group's operations."""
    seen: dict[tuple[int, ...], np.ndarray] = {}
    for op in group.operations():
        rot = np.array([[int(round(v / op.DEN)) for v in row] for row in op.rot],
                       dtype=np.int64)
        seen.setdefault(tuple(rot.ravel()), rot)
    return list(seen.values())


def in_parent_basis(p_matrix, rotations) -> list[list[list[Fraction]]]:
    """Each child rotation in the parent's basis, P·R·P⁻¹, exactly.

    x_parent = P·x_child + p, so a child operation x_c ↦ R·x_c is
    x_p ↦ P·R·P⁻¹·x_p on the parent's coordinates.
    """
    p = [[Fraction(v) for v in row] for row in p_matrix]
    det = (p[0][0] * (p[1][1] * p[2][2] - p[1][2] * p[2][1])
           - p[0][1] * (p[1][0] * p[2][2] - p[1][2] * p[2][0])
           + p[0][2] * (p[1][0] * p[2][1] - p[1][1] * p[2][0]))
    if det == 0:
        raise ValueError("the transform's P is singular")
    inv = [[(p[(j + 1) % 3][(i + 1) % 3] * p[(j + 2) % 3][(i + 2) % 3]
             - p[(j + 1) % 3][(i + 2) % 3] * p[(j + 2) % 3][(i + 1) % 3]) / det
            for j in range(3)] for i in range(3)]

    def mul(x, y):
        return [[sum(x[i][t] * y[t][j] for t in range(3)) for j in range(3)]
                for i in range(3)]

    return [mul(mul(p, [[Fraction(int(v)) for v in row] for row in r]), inv)
            for r in rotations]


def invariant_metric_basis(rotations) -> np.ndarray:
    """Integer basis of the direct metrics a rotation set leaves invariant, (m, 6).

    Rows are (G11, G22, G33, G12, G13, G23) *values*.  A rotation acting on
    fractional coordinates, x′ = R·x, preserves lengths when RᵀGR = G — the
    **transposed** action on a direct-space tensor.  ``adp_basis`` solves
    R·U·Rᵀ = U, so it is handed Rᵀ (the root CLAUDE.md's Rᵀ trap: the
    untransposed set is a group too and gives a subspace of the right
    dimension and the wrong orientation, which only a span test catches).
    """
    return adp_basis([np.asarray(r, dtype=np.int64).T for r in rotations])


def _sym(v) -> list[list]:
    """A Voigt 6-vector of values as the symmetric 3×3 it stands for."""
    m = [[0] * 3 for _ in range(3)]
    for value, (i, j) in zip(v, _VOIGT, strict=True):
        m[i][j] = m[j][i] = value
    return m


def _voigt(m) -> list:
    return [m[i][j] for i, j in _VOIGT]


def _congruence(r, m) -> list[list]:
    """Rᵀ·M·R, exactly (integer or Fraction entries)."""
    return [[sum(r[k][i] * m[k][ll] * r[ll][j] for k in range(3) for ll in range(3))
             for j in range(3)] for i in range(3)]


def _reynolds(parent_rotations, v) -> list[Fraction]:
    """⟨RᵀGR⟩ over the parent's point group, of a Voigt value vector."""
    total = [[Fraction(0)] * 3 for _ in range(3)]
    m = _sym([Fraction(x) for x in v])
    for r in parent_rotations:
        c = _congruence([[int(x) for x in row] for row in r], m)
        total = [[total[i][j] + c[i][j] for j in range(3)] for i in range(3)]
    n = len(parent_rotations)
    return [x / n for x in _voigt(total)]


def strain_basis(parent_rotations, child_rotations, fixed_angles=None
                 ) -> np.ndarray:
    """The Γ strains a child group allows and its parent does not, (n, 3, 3).

    ``parent_rotations`` is the parent's point group, ``child_rotations`` the
    child's, both **in the parent's basis** (R_parent = P·R_child·P⁻¹).
    Returns n symmetric matrices Eⱼ spanning S of the module docstring,
    orthonormal in the parent's Cartesian frame and signed so that each one's
    first component above 1e-12 is positive, in a deterministic order (the
    exact rational basis, Gram–Schmidt in natural order — the platform rule of
    ``representation.distortion``).  ``fixed_angles`` maps ``"alpha"`` …
    ``"gamma"`` to the angle the parent's symmetry fixes (``cell_constraints``);
    an angle it does not fix is taken at 90° for the orthonormalisation only.

    Refuses a child rotation that is not a parent rotation, and a parent
    rotation that mixes axes whose lengths its symmetry does not tie (the
    length scaling would then not preserve S; see the module docstring).
    """
    parent = [np.asarray(r, dtype=np.int64) for r in parent_rotations]
    keys = {tuple(r.ravel()) for r in parent}
    child = []
    for r in child_rotations:
        rr = np.asarray([[float(v) for v in row] for row in r], dtype=np.float64)
        ri = np.rint(rr).astype(np.int64)
        exact = all(Fraction(v).denominator == 1 for row in r for v in row)
        if not exact or tuple(ri.ravel()) not in keys:
            raise ValueError(
                "strain_basis(): a rotation of the child group, carried into the "
                f"parent's basis, is {rr.tolist()}, which is not a rotation of the "
                "parent's point group: the child is not a subgroup of this parent "
                "under this transform")
        child.append(ri)
    for r in parent:
        for i, j in product(range(3), repeat=2):
            if i != j and r[i, j] != 0 and not _axes_tied(i, j, parent):
                raise ValueError(
                    f"strain_basis(): the parent rotation {r.tolist()} mixes axes "
                    f"{'abc'[i]} and {'abc'[j]}, whose lengths its symmetry does "
                    "not make equal, so the strain cannot be scaled by the "
                    "parent's lengths; state the parent in a tabulated setting")
    invariant = invariant_metric_basis(child)
    if len(invariant) == 0:
        return np.zeros((0, 3, 3))
    # the combinations c of the H-invariant rows that the parent average kills
    images = [_reynolds(parent, row) for row in invariant]
    rows = [[images[t][q] for t in range(len(invariant))] for q in range(6)]
    coeffs = _nullspace_int(rows, len(invariant))
    if len(coeffs) == 0:
        return np.zeros((0, 3, 3))
    exact = [np.array(_sym(c @ invariant), dtype=np.float64) for c in coeffs]
    frame = _normalised_frame(fixed_angles or {})
    inv = np.linalg.inv(frame)
    out: list[np.ndarray] = []
    for d in exact:
        # Gram–Schmidt in the Cartesian frame, E_cart = N⁻ᵀ·E·N⁻¹
        e = d.copy()
        for q in out:
            e = e - _inner(inv, e, q) * q
        e = e / np.sqrt(_inner(inv, e, e))
        flat = e[[i for i, _ in _VOIGT], [j for _, j in _VOIGT]]
        first = flat[np.abs(flat) > 1e-12][0]
        out.append(e if first > 0 else -e)
    return np.array(out)


def _axes_tied(i: int, j: int, rotations) -> bool:
    """Whether the point group maps axis i onto ±axis j (so their lengths tie)."""
    # an axis is carried onto a combination of others by some rotation; when
    # the group makes |a_i| = |a_j| by symmetry, the metric's invariant
    # subspace has G_ii = G_jj on every row
    basis = invariant_metric_basis(rotations)
    return bool(np.all(basis[:, i] == basis[:, j]))


def _inner(inv, e1, e2) -> float:
    a = inv.T @ e1 @ inv
    b = inv.T @ e2 @ inv
    return float(np.sum(a * b))


def _normalised_frame(fixed_angles) -> np.ndarray:
    """M·L⁻¹ at unit lengths, the parent's fixed angles and 90° for a free one."""
    from .adp import cartesian_basis

    angles = [float(fixed_angles.get(n, 90.0)) for n in ("alpha", "beta", "gamma")]
    return np.asarray(cartesian_basis(1.0, 1.0, 1.0, *angles), dtype=np.float64)


def child_metric(parent_cell, p_matrix, strains=None, basis=None) -> np.ndarray:
    """G′ = Pᵀ·(G_parent + 2·L·E·L)·P, numpy, angles in degrees.

    With no strain (``strains`` ``None`` or all zero) the sum adds an exact
    zero, so G′ is bit-for-bit what ``magnetic_supercell`` has always built
    from the parent's cell.
    """
    from .lattice import direct_metric_tensor

    g = np.asarray(direct_metric_tensor(*(float(v) for v in parent_cell)),
                   dtype=np.float64)
    if strains is not None and len(strains):
        lengths = np.asarray([float(v) for v in parent_cell[:3]], dtype=np.float64)
        e = np.tensordot(np.asarray(strains, dtype=np.float64), basis, axes=1)
        g = g + 2.0 * np.outer(lengths, lengths) * e
    p = np.asarray(p_matrix, dtype=np.float64)
    return p.T @ g @ p


def cell_from_metric(g) -> tuple[float, ...]:
    """(a, b, c, α, β, γ) of a direct metric, the cosines snapped (degrees).

    The *cosine* is snapped onto the exact values a lattice symmetry can force
    (0, ±½) within :data:`COSINE_SNAP`: a hexagonal γ comes out of
    ``arccos(-0.5000000000000001)`` as 119.999999999999986, and a cell whose γ
    is not 120 is a cell whose space-group constraint the refinement has to
    re-impose.  The snap is far below any physical departure and far above the
    rounding it removes.
    """
    g = np.asarray(g, dtype=np.float64)
    lengths = np.sqrt(np.diag(g))
    angles = []
    for i, j in ((1, 2), (0, 2), (0, 1)):
        cosine = float(g[i, j] / (lengths[i] * lengths[j]))
        for exact in (0.0, 0.5, -0.5):
            if abs(cosine - exact) <= COSINE_SNAP:
                cosine = exact
                break
        angles.append(float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))))
    return (float(lengths[0]), float(lengths[1]), float(lengths[2]), *angles)
