"""Displacive modes of a child structure in Å: complete, and in the reference metric.

A distorted structure (the *child*, group H) is its high-symmetry *parent*
(group G) plus a displacement field, and that field splits into components
that transform by single irreps of G.  This module builds the complete set of
symmetry-adapted modes a stated child admits, in the AMPLIMODES unit, and
decomposes a given child into amplitudes A_τ per (k, irrep, direction).

**Public API — WP-1419 chunk 1, 2026-10-13.**

::

    reference_metric(parent, child, transform, *, reference="average") -> (3, 3) float
    normalise_in_cell(fields, metric, *, lattice_points=1)            -> (m, N, 3) float
    distortion_basis(parent, child, transform, *, reference="average") -> ModeBasis
    mode_amplitudes(parent, child, transform, *, reference="average", tolerance=1.5)
                                                                      -> ModeDecomposition
    displacive_statement(parent, child, transform, *, seed=DISTORTION_SEED,
                         reference="average", tolerance=1.5)        -> DisplaciveStatement
    parent_site_ties(site_map, *, phase_index=0)                     -> tuple of Biso ties

``displacive_statement`` is WP-1419 chunk 3 (2026-10-21): the child as its
parent plus absolute, refinable mode amplitudes (``Phase.distortion_modes``).

``parent`` and ``child`` are :class:`~rietx.schemas.structure.Phase` objects.
``transform`` is (P, p) with r_parent = P·r_child + p: the columns of P are the
child's conventional axes in parent fractions, and p is the child's origin in
the parent cell.  :func:`distortion_basis` reads the child's group and cell
only; :func:`mode_amplitudes` also reads its atoms.

Conventions, each of which a caller can get wrong silently:

1. **The unit.**  A mode is normalised so that Σ mult·|ε|² = 1 over a
   *primitive* cell of the child lattice, with |ε| in Å, and the modes of one
   irrep are orthonormal in the same sum (Perez-Mato, Orobengoa & Aroyo 2010,
   eqs. 3–4, p. 560; Orobengoa et al. 2009, eq. 9, pp. 823–824).  The
   multiplicity is that of the primitive cell, not ITA's for a centred group
   (Orobengoa 2009's footnote): an I-centred child sums over half its
   conventional cell.  Normalising over one *parent* cell instead divides
   every amplitude by √(index), the ratio of the two primitive volumes.
   A_τ = (Σ_m A²_{τ,m})^½ is the norm of the field's projection on the
   irrep's subspace, so it does not depend on the basis chosen inside it
   (eqs. 5–7).  No mass and no occupancy weight enters: a partially occupied
   site counts once.

2. **The metric is the unstrained reference metric**, G_ref = Pᵀ·G_parent·P,
   never the child's own cell.  Orobengoa 2009 § 2.2, p. 822: "for full
   mathematical consistency (orthogonality and completeness of the set of
   symmetry-adapted modes etc.), the symmetry-mode analysis of the distorted
   structure should be performed disregarding the strain component"; the
   strain is a separate Γ-point term.  In the child's strained metric the
   parent point group is not an isometry, the irrep subspaces at one k are not
   orthogonal, and Σ A_τ² ≠ ‖u‖² (0.007 Å on the shipped LaMnO₃ fixture).
   ``reference="average"`` takes G_parent as the parent-symmetric part of the
   child's metric, the Reynolds average ⟨Rᵀ·G·R⟩ over the parent point group
   (the Γ1 part of the strain of Campbell et al. 2006 § 4.5), which is what a
   virtual parent needs: LaMnO₃ at 300 K has no cubic phase to measure.
   ``reference="parent"`` takes the parent phase's own cell, which must then
   be invariant under the parent group.

3. **The uniform translation is not a mode.**  It is the acoustic part of the
   Γ-point polar irrep, and it is exactly flat in the data.  It is removed
   from that irrep's subspace, and a polar child's displacement field is
   shifted to keep the arithmetic centre of the atoms unmoved: "the choice
   that makes this global translation zero" (Perez-Mato 2010 p. 560;
   Orobengoa 2009 p. 831, YMnO₃).  The unweighted mean is removed for every
   child; for a non-polar one it is zero by symmetry.

4. **The basis is complete.**  Every irrep with a non-zero subduction
   frequency under H contributes, primary or secondary, Γ-point ones included
   (Campbell et al. 2006 p. 611; Perez-Mato 2010 p. 561), so Σ_τ n_modes is the
   number of free coordinates of the child.  This is asserted before a basis
   is returned.

5. **Labels are this package's.**  ``irrep`` is the small-irrep label of
   :mod:`.irreps` at the first arm of the star present in the child, not
   Miller–Love's R4+ or M3+; the comparison with a published table is made on
   the isotropy subgroup each component reports, which does not depend on the
   gauge (the convention :mod:`~rietx.crystallography.magnetic.isotropy`
   states for its direction labels).  Mode labels also depend on the parent's
   origin: with the B cation of a perovskite at the origin the octahedral
   tilt is R4+, with the A cation there it is R5+ (Campbell 2006 § 4.7; Perez-Mato
   2010 footnote 8, p. 577).

6. **Scope.**  Every k the child lattice admits is handled, with the arms of
   one star grouped into one irrep by the parent operations that carry one
   arm to another.  Complex irreps (2k not a reciprocal lattice vector) are
   built as the real span of the k and −k fields, which is the physically
   irreducible pair; no case in the tests exercises that path against a
   published table.  A child whose atoms do not pair one to one with the
   parent's (an ordered vacancy, a substitution) is refused.

References
----------
Perez-Mato, J. M., Orobengoa, D. & Aroyo, M. I. (2010). *Acta Cryst.* A**66**,
558 — AMPLIMODES's normalisation (eqs. 3–4, p. 560), the amplitude A_τ
(eqs. 5–7), the polar origin (p. 560), primary and secondary irreps (p. 561),
and the LaMnO₃ decomposition of Table 13, p. 577.
Orobengoa, D., Capillas, C., Aroyo, M. I. & Perez-Mato, J. M. (2009).
*J. Appl. Cryst.* **42**, 820 — eq. (9), the Å unit and the primitive-cell
multiplicity; § 2.2, p. 822, the unstrained reference structure.
Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006).
*J. Appl. Cryst.* **39**, 607 — the strain as a separate term (§ 4.5) and the
complete mode set of a subgroup (p. 611).
"""

from __future__ import annotations

import functools
import itertools
import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from ..species import element_symbol
from ..symmetry import _group_arrays, group_key, resolve_group, site_orbit
from ..wyckoff import SPGLIB_REFUSALS
from .irreps import canonical_kvector, equivalent_kvectors, small_irreps
from .modes import basis_vectors, magnetic_representation

#: Rank and residual tolerance on the projected subspaces.  Every matrix here
#: is an average of permutation-times-rotation matrices in a well-conditioned
#: metric, so true zeros sit at 1e-14 and true ones at 1.
_RANK_TOL = 1e-8

#: How close (in parent or child fractions) two positions must be to count as
#: the same atom.
_POSITION_TOL = 1e-6

#: The order-of-magnitude scale (Å) of the generic displacement used to read a
#: component's isotropy subgroup with spglib, and spglib's tolerance on it.
_PROBE_AMPLITUDE = 0.05
_PROBE_SYMPREC = 1e-3

REFERENCES = ("average", "parent")


# --------------------------------------------------------------------------
# results
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class IrrepModes:
    """The modes one irrep of the parent contributes to a child.

    ``vectors[m]`` is mode m as ``(N, 3)`` displacements in child fractions
    per Å of amplitude, on :attr:`ModeBasis.positions`; the set is orthonormal
    over the child's primitive cell in the reference metric.  ``k`` is the
    first arm of the star present in the child (parent conventional reciprocal
    coordinates) and ``arms`` all of them.  ``isotropy_group`` is the group of
    a generic displacement inside this irrep's modes (Table 13's subgroup
    column), and ``primary`` says whether that group is the child's own, ``None`` when spglib
    named no group for the probe (nothing was checked, so neither answer is given).
    """

    k: tuple[str, str, str]
    arms: tuple[tuple[str, str, str], ...]
    irrep: str
    isotropy_group: str
    primary: bool | None
    vectors: np.ndarray  # (m, N, 3) child fractions per Å

    @property
    def n_modes(self) -> int:
        return int(self.vectors.shape[0])


@dataclass(frozen=True, eq=False)
class ModeBasis:
    """Every mode a child admits, grouped by irrep, in the reference metric."""

    components: tuple[IrrepModes, ...]
    positions: np.ndarray  # (N, 3) reference positions, child fractions
    species: tuple[str, ...]
    transform: tuple[np.ndarray, np.ndarray]
    metric: np.ndarray  # (3, 3) G_ref in the child frame
    lattice_points: int
    child_group: str
    parent_atoms: np.ndarray  # (N,) index of the parent atom each position is an image of

    @property
    def n_modes(self) -> int:
        return sum(c.n_modes for c in self.components)


@dataclass(frozen=True, eq=False)
class ModeAmplitude:
    """One irrep's share of a child's distortion, in Å."""

    k: tuple[str, str, str]
    irrep: str
    isotropy_group: str
    primary: bool | None
    n_modes: int
    amplitude: float
    mode_amplitudes: tuple[float, ...]


@dataclass(frozen=True, eq=False)
class ModeDecomposition:
    """A child decomposed against its parent into ``A_τ`` per (k, irrep, direction).

    ``total`` is the norm of the displacement field over the child's primitive
    cell in the reference metric, after ``translation`` (the mean
    displacement, child fractions) was removed; ``residual`` is what the modes
    do not reach, which is round-off for a child that has its stated symmetry.
    """

    rows: tuple[ModeAmplitude, ...]
    total: float
    residual: float
    translation: tuple[float, float, float]
    displacements: np.ndarray  # (N, 3) child fractions, translation removed
    basis: ModeBasis


# --------------------------------------------------------------------------
# small helpers
# --------------------------------------------------------------------------

def _value(x) -> float:
    return float(getattr(x, "value", x))


def _cell_metric(cell) -> np.ndarray:
    a, b, c, al, be, ga = (_value(getattr(cell, n))
                           for n in ("a", "b", "c", "alpha", "beta", "gamma"))
    ca, cb, cg = (math.cos(math.radians(v)) for v in (al, be, ga))
    return np.array([[a * a, a * b * cg, a * c * cb],
                     [a * b * cg, b * b, b * c * ca],
                     [a * c * cb, b * c * ca, c * c]], dtype=np.float64)


def _group(phase):
    return resolve_group(phase.space_group, phase.symmetry_operations)


def _operations(group) -> tuple[np.ndarray, np.ndarray]:
    _, rot, tran = _group_arrays(group_key(group))
    return np.rint(rot).astype(np.int64), np.asarray(tran, dtype=np.float64)


def _transform(transform) -> tuple[np.ndarray, np.ndarray]:
    try:
        big, small = transform
    except (TypeError, ValueError):
        raise ValueError("transform must be (P, p): a 3×3 matrix whose columns are the "
                         "child's axes in parent fractions, and the child's origin") from None
    big = np.asarray(big, dtype=np.float64).reshape(3, 3)
    small = np.asarray(small, dtype=np.float64).reshape(3)
    if abs(np.linalg.det(big)) < 1e-9:
        raise ValueError(f"transform P is singular: {big.tolist()}")
    return big, small


def _wrap(x: np.ndarray) -> np.ndarray:
    out = x - np.floor(x + _POSITION_TOL)
    out[np.abs(out) < _POSITION_TOL] = 0.0
    return out


def _is_lattice(delta: np.ndarray, centrings: np.ndarray) -> bool:
    shifted = delta[None, :] - centrings
    return bool(np.any(np.all(np.abs(shifted - np.rint(shifted)) < _POSITION_TOL, axis=1)))


def _orth(columns: np.ndarray) -> np.ndarray:
    """Orthonormal basis (Euclidean) of the span of ``columns``."""
    if columns.size == 0:
        return np.zeros((columns.shape[0], 0))
    u, s, _ = np.linalg.svd(columns, full_matrices=False)
    if s.size == 0 or s[0] == 0.0:
        return np.zeros((columns.shape[0], 0))
    return u[:, s > _RANK_TOL * max(1.0, s[0])]


def _canonical(q: np.ndarray) -> np.ndarray:
    """A basis of span(q) that does not depend on which basis q is.

    An SVD returns an arbitrary rotation of a degenerate subspace, and which
    one depends on the LAPACK build.  The projector q·qᵀ does not, so its
    columns, taken in the natural order (atom 1 along a, atom 1 along b, …)
    and Gram–Schmidted until the rank is reached, give the same vectors on
    every platform: the trial-vector rule of :func:`.modes.basis_vectors`.
    """
    rank = q.shape[1]
    proj = q @ q.T
    scale = float(np.max(np.abs(proj))) if proj.size else 0.0
    out: list[np.ndarray] = []
    for column in proj.T:
        v = column.copy()
        for w in out:
            v -= w * (w @ v)
        norm = float(np.linalg.norm(v))
        if norm > 1e-6 * max(scale, 1e-300):
            out.append(v / norm)
        if len(out) == rank:
            break
    if len(out) != rank:
        raise RuntimeError("could not draw a canonical basis from a mode subspace; this is a bug")
    return np.array(out).T


#: The groups the two caches below were called with, by :func:`group_key`.
_GROUPS: dict = {}


@functools.lru_cache(maxsize=256)
def _small_irreps_cached(key, k):
    return small_irreps(_GROUPS[key], k)


@functools.lru_cache(maxsize=1024)
def _representation_cached(key, xyz, k):
    return magnetic_representation(_GROUPS[key], np.array(xyz), k, kind="polar")


def _irreps_and_representations(group, k, sites):
    """``small_irreps`` and each site's polar representation at ``k``, memoised.

    Both are pure functions of (group, k, site) and cost most of a basis
    (the factor-system checks); the candidates of one parent at one k ask for
    the same ones once per child, so they are computed once per process.
    """
    key = group_key(group)
    _GROUPS.setdefault(key, group)
    k = tuple(k)
    reps = [_representation_cached(key, tuple(float(v) for v in xyz), k) for xyz in sites]
    return _small_irreps_cached(key, k), reps


def _k_text(k) -> tuple[str, str, str]:
    return tuple(str(c) for c in k)  # type: ignore[return-value]


# --------------------------------------------------------------------------
# the metric and the normalisation
# --------------------------------------------------------------------------

def _parent_metric(parent, child, big, reference: str) -> np.ndarray:
    if reference not in REFERENCES:
        raise ValueError(f"reference must be one of {REFERENCES}, got {reference!r}")
    rot, _ = _operations(_group(parent))
    if reference == "parent":
        metric = _cell_metric(parent.cell)
        drift = max(float(np.max(np.abs(r.T @ metric @ r - metric))) for r in rot)
        if drift > 1e-9 * float(np.max(np.abs(metric))):
            raise ValueError(
                "REFERENCE_CELL_NOT_PARENT_SYMMETRIC: the parent phase's cell is not invariant "
                f"under its own group (R^T G R - G up to {drift:.3g} A^2), so it cannot be the "
                "unstrained reference; pass reference='average' to take the parent-symmetric "
                "part of the child's cell")
        return metric
    inv = np.linalg.inv(big)
    child_in_parent = inv.T @ _cell_metric(child.cell) @ inv
    return sum(r.T @ child_in_parent @ r for r in rot) / len(rot)


def reference_metric(parent, child, transform, *, reference: str = "average") -> np.ndarray:
    """G_ref = Pᵀ·G_parent·P, the unstrained metric the modes live in (child frame).

    ``reference="average"`` takes G_parent as the Reynolds average ⟨Rᵀ·G·R⟩
    of the child's metric over the parent point group, at the child's own
    scale; ``"parent"`` takes the parent phase's cell, refused when that cell
    is not invariant under the parent group.  Orobengoa et al. (2009) § 2.2,
    p. 822.
    """
    big, _ = _transform(transform)
    return big.T @ _parent_metric(parent, child, big, reference) @ big


def normalise_in_cell(fields, metric, *, lattice_points: int = 1) -> np.ndarray:
    """Orthonormalise displacement fields over a primitive cell, in Å.

    ``fields`` is ``(m, N, 3)``: m fields on the N atoms of one conventional
    cell, in fractions of the cell ``metric`` belongs to.  The inner product is
    ⟨u, v⟩ = Σ_n u_nᵀ·G·v_n / ``lattice_points``, which is Perez-Mato et al.
    (2010) eq. (3) over the primitive cell when ``lattice_points`` counts the
    lattice points of the conventional cell (2 for I, 4 for F).  Gram–Schmidt
    in the given order, dependent fields dropped; the span is unchanged.
    """
    fields = np.asarray(fields, dtype=np.float64)
    if fields.ndim != 3 or fields.shape[2] != 3:
        raise ValueError(f"fields must be (m, N, 3), got {fields.shape}")
    if lattice_points < 1:
        raise ValueError(f"lattice_points must be >= 1, got {lattice_points}")
    chol = np.linalg.cholesky(np.asarray(metric, dtype=np.float64))
    flat = np.einsum("mni,ij->mnj", fields, chol).reshape(len(fields), -1)
    flat = flat / math.sqrt(lattice_points)
    kept: list[np.ndarray] = []
    out: list[np.ndarray] = []
    scale = max((float(np.linalg.norm(f)) for f in flat), default=0.0)
    for raw, f in zip(fields, flat):
        g = f.copy()
        coeffs = []
        for q in kept:
            c = float(q @ g)
            g -= c * q
            coeffs.append(c)
        norm = float(np.linalg.norm(g))
        if norm <= _RANK_TOL * max(scale, 1.0):
            continue
        # rebuild the field from the earlier outputs so it stays in fractions
        field = raw.copy()
        for c, prev in zip(coeffs, out):
            field = field - c * prev
        kept.append(g / norm)
        out.append(field / norm)
    return np.array(out).reshape(len(out), fields.shape[1], 3)


# --------------------------------------------------------------------------
# the reference structure in the child cell
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class _Reference:
    child_frac: np.ndarray      # (N, 3) in [0, 1)
    parent_frac: np.ndarray     # (N, 3) = P·child + p
    species: tuple[str, ...]
    site: np.ndarray            # (N,) index of the parent atom it is an image of
    sites: tuple[np.ndarray, ...]  # the parent sites' positions


def _refuse_shared_sites(parent) -> None:
    """Refuse a parent whose atoms share a site: the modes carry no occupancy weight."""
    group = _group(parent)
    sites: list[np.ndarray] = []
    for atom in parent.atoms:
        xyz = np.array([_value(atom.x), _value(atom.y), _value(atom.z)])
        orbit = site_orbit(group, xyz)
        for t, other in enumerate(sites):
            d = np.asarray(orbit.images) - other[None, :]
            if np.any(np.all(np.abs(d - np.rint(d)) < _POSITION_TOL, axis=1)):
                raise ValueError(
                    f"parent atoms {parent.atoms[t].label!r} and {atom.label!r} share one site; "
                    "a mixed-occupancy site is not handled, so give the site one atom (the "
                    "modes carry no occupancy weight)")
        sites.append(orbit.position)


def _reference(parent, big, small) -> _Reference:
    _refuse_shared_sites(parent)
    group = _group(parent)
    inv = np.linalg.inv(big)
    corners = np.array([big @ np.array(c, float) + small
                        for c in itertools.product((0, 1), repeat=3)])
    lo = np.floor(corners.min(axis=0)).astype(int) - 1
    hi = np.ceil(corners.max(axis=0)).astype(int) + 1
    shifts = np.array(list(itertools.product(*(range(a, b + 1) for a, b in zip(lo, hi)))),
                      dtype=np.float64)
    child, parent_pos, species, site, sites = [], [], [], [], []
    n_conv = 0
    for s, atom in enumerate(parent.atoms):
        xyz = np.array([_value(atom.x), _value(atom.y), _value(atom.z)])
        orbit = site_orbit(group, xyz)
        sites.append(orbit.position)
        n_conv += orbit.multiplicity
        for image in orbit.images:
            cands = ((image[None, :] + shifts) - small) @ inv.T
            inside = np.all((cands > -_POSITION_TOL) & (cands < 1 - _POSITION_TOL), axis=1)
            for c in cands[inside]:
                c = _wrap(c)
                child.append(c)
                parent_pos.append(big @ c + small)
                species.append(element_symbol(atom.species))
                site.append(s)
    expected = n_conv * abs(np.linalg.det(big))
    if abs(len(child) - expected) > 1e-6:
        raise ValueError(
            f"the child cell holds {len(child)} parent atoms but should hold {expected:.4g} "
            "(parent atoms per cell x |det P|): the transform does not describe a supercell of "
            "the parent lattice")
    return _Reference(np.array(child), np.array(parent_pos), tuple(species),
                      np.array(site, dtype=np.int64), tuple(sites))


def _permutation(rot, tran, ref: _Reference, inv, small) -> np.ndarray:
    """perm[n'] = n with g⁻¹·r_{n'} ≡ r_n modulo the child lattice."""
    rinv = np.linalg.inv(rot)
    back = (ref.parent_frac - tran[None, :]) @ rinv.T
    child = _wrap((back - small[None, :]) @ inv.T)
    perm = np.empty(len(child), dtype=np.int64)
    for i, c in enumerate(child):
        d = c[None, :] - ref.child_frac
        d -= np.rint(d)
        hit = np.flatnonzero(np.all(np.abs(d) < 1e-5, axis=1))
        if len(hit) != 1:
            raise RuntimeError("a parent operation did not map the reference structure onto "
                               "itself modulo the child lattice; this is a bug")
        perm[i] = hit[0]
    return perm


def _action(rot, perm, chol_t, chol_t_inv) -> np.ndarray:
    """The 3N × 3N matrix of (g·u)_{n'} = R·u_{perm(n')}, in whitened coordinates."""
    n = len(perm)
    block = chol_t @ rot @ chol_t_inv
    out = np.zeros((3 * n, 3 * n))
    for i, j in enumerate(perm):
        out[3 * i:3 * i + 3, 3 * j:3 * j + 3] = block
    return out


# --------------------------------------------------------------------------
# the basis
# --------------------------------------------------------------------------

def _child_operations(child, big, small, parent_group):
    """H's operations restated in the parent frame, checked to lie in G."""
    rot_h, tran_h = _operations(_group(child))
    rot_g, tran_g = _operations(parent_group)
    cen_g = tran_g[np.all(rot_g == np.eye(3, dtype=np.int64), axis=(1, 2))]
    inv = np.linalg.inv(big)
    out = []
    for r, t in zip(rot_h, tran_h):
        rp = big @ r @ inv
        if np.max(np.abs(rp - np.rint(rp))) > 1e-6:
            raise ValueError(
                "CHILD_NOT_A_SUBGROUP: a child rotation is not a parent rotation under this "
                f"transform (P r P^-1 = {np.round(rp, 4).tolist()})")
        rp = np.rint(rp).astype(np.int64)
        tp = big @ t + small - rp @ small
        match = [tg for rg, tg in zip(rot_g, tran_g) if np.array_equal(rg, rp)]
        if not any(_is_lattice(tp - tg, cen_g) for tg in match):
            raise ValueError(
                "CHILD_NOT_A_SUBGROUP: a child operation is not an operation of the parent "
                "under this transform; check P, the origin shift p, and the parent's setting")
        out.append((rp, tp))
    return out


def _commensurate_kvectors(group, big, child_centrings) -> list:
    """Every k of the parent that is a reciprocal vector of the child lattice."""
    rot_g, tran_g = _operations(group)
    n_cen = int(np.sum(np.all(rot_g == np.eye(3, dtype=np.int64), axis=(1, 2))))
    det = abs(np.linalg.det(big))
    denominators = [Fraction(float(v)).limit_denominator(48).denominator for v in big.ravel()]
    q = math.lcm(*denominators)
    box = max(1, int(round(n_cen * det * q ** 3)))
    inv = np.linalg.inv(big)
    gens = [big[:, i] for i in range(3)] + [big @ c for c in child_centrings]
    found: dict = {}
    limit = 4 * max(1, int(round(det * q ** 3))) * n_cen + 8
    for m in itertools.product(range(min(box, 64)), repeat=3):
        k = np.array(m, float) @ inv
        if any(abs(k @ g - round(k @ g)) > 1e-6 for g in gens):
            continue
        kf = tuple(Fraction(float(v)).limit_denominator(limit) for v in k)
        canon = canonical_kvector(group, kf)
        found.setdefault(canon, None)
    child_points = len(child_centrings)
    expected = det * n_cen / child_points
    if abs(len(found) - expected) > 1e-6:
        raise RuntimeError(
            f"found {len(found)} k-vectors commensurate with the child lattice but the volume "
            f"ratio says {expected:.4g}; this is a bug")
    return sorted(found, key=lambda k: (any(c != 0 for c in k), k))


def _find_star(group, k, stars: list) -> int | None:
    """The index of the star in ``stars`` that holds ``k``, or ``None``."""
    rot_g, _ = _operations(group)
    for i, rep in enumerate(stars):
        for r in rot_g:
            arm = tuple(sum(Fraction(int(r[a][b])) * rep[a] for a in range(3)) for b in range(3))
            if equivalent_kvectors(group, arm, k):
                return i
    return None


def _star_key(group, k, stars: list) -> int:
    found = _find_star(group, k, stars)
    if found is not None:
        return found
    stars.append(k)
    return len(stars) - 1


def _isotropy(field_frac, ref: _Reference, metric) -> tuple[str, int | None, int | None]:
    """spglib's name, space-group number and operation count of the reference displaced by ``field_frac``.

    Name ``"unidentified"`` and both numbers ``None`` when spglib refuses.  The
    operation count alone cannot tell a group from its supergroup, since spglib
    lists only the operations that preserve the input cell.
    """
    import spglib

    lattice = np.linalg.cholesky(metric)
    types = {s: i + 1 for i, s in enumerate(sorted(set(ref.species)))}
    cell = (lattice, _wrap(ref.child_frac + field_frac), [types[s] for s in ref.species])
    try:
        data = spglib.get_symmetry_dataset(cell, symprec=_PROBE_SYMPREC)
    except SPGLIB_REFUSALS:  # the same refusal in spglib's other error mode
        data = None
    if data is None:
        return "unidentified", None, None
    return f"{data.international} ({data.number})", int(data.number), len(data.rotations)


def distortion_basis(parent, child, transform, *, reference: str = "average") -> ModeBasis:
    """Every symmetry-adapted mode a child of ``parent`` admits, in Å.

    The modes are the displacement fields of the parent structure, periodic
    on the child lattice and invariant under the child's group H, split by
    the irreps of the parent group G: for each k of the parent that is a
    reciprocal vector of the child lattice, the polar representation of each
    parent site is projected onto the small irreps (:mod:`.modes`), the arms
    of one star are grouped into one irrep by the parent operations that
    carry one arm to another, the uniform translation is taken out at Γ, and
    the H-invariant part of each irrep's subspace is kept.  Primary and
    secondary irreps are both returned, so the basis is complete: Σ n_modes is
    the child's number of free coordinates, which is asserted.  Each mode is
    normalised over the child's primitive cell in the reference metric
    (Perez-Mato, Orobengoa & Aroyo 2010, eqs. 3–4; module docstring).
    """
    return _distortion_basis(parent, child, transform, reference)[0]


def _distortion_basis(parent, child, transform, reference: str
                      ) -> tuple[ModeBasis, _Reference]:
    """:func:`distortion_basis`, with the reference structure it was built on."""
    big, small = _transform(transform)
    inv = np.linalg.inv(big)
    group = _group(parent)
    g_parent = _parent_metric(parent, child, big, reference)
    g_ref = big.T @ g_parent @ big
    ref = _reference(parent, big, small)
    n_atoms = len(ref.species)
    chol_t = np.linalg.cholesky(g_parent).T  # whitening: |chol_t·u|² = uᵀ G u
    chol_t_inv = np.linalg.inv(chol_t)
    whiten = np.kron(np.eye(n_atoms), chol_t)

    h_ops = _child_operations(child, big, small, group)
    child_centrings = [np.linalg.solve(big, t) for r, t in h_ops
                       if np.array_equal(r, np.eye(3, dtype=np.int64))]
    child_centrings = [_wrap(c) for c in child_centrings]
    lattice_points = len(child_centrings)
    if lattice_points < 1:
        raise RuntimeError("the child's group has no identity; this is a bug")

    # the parent's operations, one per rotation, and their actions on the child cell
    rot_g, tran_g = _operations(group)
    cen_g = tran_g[np.all(rot_g == np.eye(3, dtype=np.int64), axis=(1, 2))]
    coset: dict = {}
    for r, t in zip(rot_g, tran_g):
        coset.setdefault(r.tobytes(), (r, t))
    g_ops = list(coset.values())
    g_actions = [_action(r.astype(float), _permutation(r, t, ref, inv, small), chol_t, chol_t_inv)
                 for r, t in g_ops]
    h_actions = [_action(r.astype(float), _permutation(r, t, ref, inv, small), chol_t, chol_t_inv)
                 for r, t in h_ops]
    fix_h = sum(h_actions) / len(h_actions)

    # one real subspace per (k, small irrep), from every parent site
    items: list[tuple[int, tuple, str, np.ndarray]] = []
    stars: list = []
    for k in _commensurate_kvectors(group, big, child_centrings):
        # a complex irrep is the real span of the k and -k fields: when no parent
        # operation takes k to -k the two are separate stars, and the first already
        # spans both, so the second would be counted twice.  The skip is per star:
        # a -k that is an arm of k's own star is kept, since the arms of one star
        # are merged below
        minus_k = tuple(-c for c in k)
        if (_find_star(group, k, stars) is None
                and _find_star(group, minus_k, stars) is not None):
            continue
        star = _star_key(group, k, stars)
        kk = np.array([float(c) for c in k])
        fields: dict[str, list[np.ndarray]] = {}
        irreps, reps = _irreps_and_representations(group, k, ref.sites)
        for s, rep in enumerate(reps):
            orbit = rep.positions
            members = np.flatnonzero(ref.site == s)
            where = []
            for n in members:
                for j, q in enumerate(orbit):
                    if _is_lattice(ref.parent_frac[n] - q, cen_g):
                        where.append((n, j, ref.parent_frac[n] - q))
                        break
                else:
                    raise RuntimeError("a reference atom is not an image of its own orbit")
            for ir in irreps:
                bv = basis_vectors(rep, ir)
                if bv.multiplicity == 0:
                    continue
                for vec in bv.vectors.reshape(-1, rep.n_atoms, 3):
                    field = np.zeros((n_atoms, 3), dtype=np.complex128)
                    for n, j, t in where:
                        field[n] = vec[j] * np.exp(2j * np.pi * float(kk @ t))
                    flat = whiten @ field.reshape(-1)
                    fields.setdefault(ir.label, []).extend((flat.real, flat.imag))
        for label, cols in fields.items():
            q = _orth(np.array(cols).T)
            if q.shape[1]:
                items.append((star, k, label, q))

    # group the arms of one star into one irrep of G
    parent_of = list(range(len(items)))

    def root(i: int) -> int:
        while parent_of[i] != i:
            parent_of[i] = parent_of[parent_of[i]]
            i = parent_of[i]
        return i

    for i, j in itertools.combinations(range(len(items)), 2):
        if items[i][0] != items[j][0] or root(i) == root(j):
            continue
        ki, kj = items[i][1], items[j][1]
        minus = tuple(-c for c in kj)
        for (r, _), act in zip(g_ops, g_actions):
            rinv = np.rint(np.linalg.inv(r)).astype(np.int64)
            image = tuple(sum(Fraction(int(rinv[a][b])) * ki[a] for a in range(3))
                          for b in range(3))
            if not (equivalent_kvectors(group, image, kj)
                    or equivalent_kvectors(group, image, minus)):
                continue
            overlap = np.linalg.norm(items[j][3].T @ act @ items[i][3]) ** 2
            if overlap > 0.5 * min(items[i][3].shape[1], items[j][3].shape[1]):
                parent_of[root(j)] = root(i)
                break

    groups: dict[int, list[int]] = {}
    for i in range(len(items)):
        groups.setdefault(root(i), []).append(i)

    translation = _orth(np.array([whiten @ np.tile(e, n_atoms) for e in np.eye(3)]).T)
    spaces = []
    for members in groups.values():
        q = _orth(np.hstack([items[i][3] for i in members]))
        star_k = items[members[0]][1]
        if all(c == 0 for c in star_k):
            q = _orth(q - translation @ (translation.T @ q))
        if q.shape[1]:
            spaces.append((members, q))

    total_dim = sum(q.shape[1] for _, q in spaces)
    expected = 3 * n_atoms // lattice_points - 3
    if total_dim != expected:
        raise RuntimeError(
            f"the irrep subspaces span {total_dim} dimensions but the fields periodic on the "
            f"child lattice, less the translations, span {expected}; this is a bug")

    probes = []
    for members, q in spaces:
        modes = _orth(fix_h @ q)
        if not modes.shape[1]:
            continue
        modes = _canonical(modes)
        first = items[members[0]]
        arms = tuple(dict.fromkeys(_k_text(items[i][1]) for i in members))
        fields_frac = np.array([(chol_t_inv @ m.reshape(n_atoms, 3).T).T
                                for m in modes.T])  # parent fractions
        fields_child = np.einsum("ij,mnj->mni", inv, fields_frac)
        vectors = normalise_in_cell(fields_child, g_ref, lattice_points=lattice_points)
        generic = np.tensordot(_PROBE_AMPLITUDE * (1.0 + 0.618 * np.arange(len(vectors))),
                               vectors, axes=1)
        probes.append((first, arms, vectors, generic))

    # the child's own group, read the way each component's is: a generic field invariant
    # under H has exactly H for its group
    _, child_number, n_child_ops = _isotropy(sum(p[3] for p in probes), ref, g_ref)
    components = []
    for first, arms, vectors, generic in probes:
        name, number, n_ops = _isotropy(generic, ref, g_ref)
        # the operation count alone passes a supergroup whose extra operations do not
        # preserve the child's cell, so the group itself is compared (#1002)
        primary = (None if n_ops is None or child_number is None
                   else n_ops == n_child_ops and number == child_number)
        components.append(IrrepModes(
            k=_k_text(first[1]), arms=arms, irrep=first[2], isotropy_group=name,
            primary=primary, vectors=vectors))

    n_modes = sum(c.n_modes for c in components)
    fixed_translations = _orth(fix_h @ translation).shape[1]
    free = _orth(fix_h).shape[1] - fixed_translations
    if n_modes != free:
        raise RuntimeError(
            f"the modes number {n_modes} but the child has {free} free coordinates; "
            "the basis is incomplete, which is a bug")

    return ModeBasis(
        components=tuple(components),
        positions=ref.child_frac,
        species=ref.species,
        transform=(big, small),
        metric=g_ref,
        lattice_points=lattice_points,
        child_group=str(child.space_group),
        parent_atoms=ref.site,
    ), ref


# --------------------------------------------------------------------------
# the decomposition of a given child
# --------------------------------------------------------------------------

def _child_atoms(child) -> tuple[np.ndarray, tuple[str, ...]]:
    group = _group(child)
    pos, species = [], []
    for atom in child.atoms:
        xyz = np.array([_value(atom.x), _value(atom.y), _value(atom.z)])
        for image in site_orbit(group, xyz).images:
            pos.append(_wrap(np.asarray(image, dtype=np.float64)))
            species.append(element_symbol(atom.species))
    return np.array(pos), tuple(species)


def mode_amplitudes(parent, child, transform, *, reference: str = "average",
                    tolerance: float = 1.5) -> ModeDecomposition:
    """Decompose a child structure into ``A_τ`` per (k, irrep, direction), in Å.

    The child's atoms are paired one to one with the parent's images in the
    child cell (same element, nearest in the reference metric, at most
    ``tolerance`` Å apart), the mean displacement is removed (the polar
    origin of Perez-Mato et al. 2010 p. 560), and the field is projected on
    :func:`distortion_basis`'s modes.  A_τ is the norm of each projection
    over the child's primitive cell (eqs. 5–7), so Σ A_τ² equals the field's
    own squared norm and no A_τ depends on the basis inside its irrep.
    """
    from scipy.optimize import linear_sum_assignment

    basis = distortion_basis(parent, child, transform, reference=reference)
    positions, species = _child_atoms(child)
    ref_pos, ref_species = basis.positions, basis.species
    if len(positions) != len(ref_pos) or sorted(species) != sorted(ref_species):
        raise ValueError(
            f"CHILD_ATOMS_UNPAIRED: the child cell holds {len(positions)} atoms "
            f"({_count(species)}) and the parent's image of it {len(ref_pos)} "
            f"({_count(ref_species)}); a mode decomposition needs the same atoms, one to one")
    chol = np.linalg.cholesky(basis.metric)
    disp = np.zeros_like(ref_pos)
    for element in sorted(set(ref_species)):
        rows = [i for i, s in enumerate(ref_species) if s == element]
        cols = [i for i, s in enumerate(species) if s == element]
        delta = positions[cols][None, :, :] - ref_pos[rows][:, None, :]
        delta -= np.rint(delta)
        cost = np.linalg.norm(delta @ chol, axis=2)
        r_idx, c_idx = linear_sum_assignment(cost)
        worst = float(cost[r_idx, c_idx].max())
        if worst > tolerance:
            raise ValueError(
                f"CHILD_ATOMS_UNPAIRED: a {element} atom of the child sits {worst:.3f} A from "
                f"the nearest free parent image, beyond tolerance={tolerance} A; check the "
                "transform and the origin shift")
        for r, c in zip(r_idx, c_idx):
            disp[rows[r]] = delta[r, c]

    shift = disp.mean(axis=0)
    disp = disp - shift[None, :]
    lp = basis.lattice_points

    def inner(u, v) -> float:
        return float(np.einsum("ni,ij,nj->", u, basis.metric, v)) / lp

    rows_out = []
    reached = np.zeros_like(disp)
    for comp in basis.components:
        amps = np.array([inner(v, disp) for v in comp.vectors])
        reached += np.tensordot(amps, comp.vectors, axes=1)
        rows_out.append(ModeAmplitude(
            k=comp.k, irrep=comp.irrep, isotropy_group=comp.isotropy_group,
            primary=comp.primary, n_modes=comp.n_modes,
            amplitude=float(np.linalg.norm(amps)),
            mode_amplitudes=tuple(float(a) for a in amps)))
    total = math.sqrt(max(inner(disp, disp), 0.0))
    left = disp - reached
    residual = math.sqrt(max(inner(left, left), 0.0))
    return ModeDecomposition(
        rows=tuple(rows_out), total=total, residual=residual,
        translation=tuple(float(v) for v in shift), displacements=disp, basis=basis)


def _count(species) -> str:
    counts: dict[str, int] = {}
    for s in species:
        counts[s] = counts.get(s, 0) + 1
    return ", ".join(f"{n} {s}" for s, n in sorted(counts.items()))


# --------------------------------------------------------------------------
# the statement: a child as its parent plus refinable amplitudes (WP-1419 C3)
# --------------------------------------------------------------------------

#: The norm (Å, in the AMPLIMODES unit) of the seed :func:`displacive_statement`
#: puts on a child that sits exactly at its parent.  The pattern is invariant
#: under every lost parent operation's action on the amplitude vector, so at
#: A = 0 every amplitude outside the identity irrep has an exactly zero
#: gradient (#286, 2026-09-16; Perez-Mato, Orobengoa & Aroyo 2010 § 7), and a
#: fit has to start off it.  The magnitude is ours: small and non-zero, never
#: tuned toward an answer (``moments.SEED_TILT``'s rule for moments), here a
#: largest per-atom move of about 0.005 Å on NaTaO₃.  Measured on two
#: perovskites (synthetic NaTaO₃ P4/mbm and LaMnO₃ Pnma) at 0.003, 0.01 and
#: 0.03 Å; untested beyond them.
DISTORTION_SEED = 0.01


@dataclass(frozen=True, eq=False)
class DisplaciveStatement:
    """A child phase stated as its parent plus mode amplitudes (WP-1419).

    ``phase`` is the child with ``Phase.distortion_modes`` set and the
    coordinates of every moved atom written as ``base + Σ A·v``; it refines on
    the amplitudes (``phases.*.distortion_modes.modes.*.amplitude``).
    ``basis`` is the :class:`ModeBasis` the modes come from and ``transform``
    the (P, p) it was built with.  ``site_map[j]`` is the index in
    ``parent.atoms`` of the parent atom child atom j is an image of, and
    ``biso_ties`` ties every child Biso to the first child atom of its parent
    site (:func:`parent_site_ties`), as ``(path, source, coefficient,
    constant)`` for ``Refinement.tie``.  ``seed`` maps each amplitude path to
    the value the statement seeded it with, and is empty when the child was
    already distorted (it starts at its own decomposition and is never
    re-seeded).  Paths assume the phase is ``phases.0``.
    """

    phase: object
    basis: ModeBasis
    transform: tuple[np.ndarray, np.ndarray]
    site_map: tuple[int, ...]
    biso_ties: tuple[tuple[str, str, float, float], ...]
    seed: dict[str, float]


def parent_site_ties(site_map, *, phase_index: int = 0
                     ) -> tuple[tuple[str, str, float, float], ...]:
    """Tie every child Biso to the Biso of the first child atom of its parent atom.

    ``site_map[j]`` is the parent atom child atom j comes from.  One
    displacement parameter per parent site is what a child refined against its
    parent can measure: free child Biso alone can manufacture the superstructure
    intensity the model is being tested for (WP-1419 § The problem).
    Written once (Yue, #724, 2026-10-05), for ``solve_magnetic``'s
    ``tie_to_parent`` and for :func:`displacive_statement`.
    """
    first: dict[int, int] = {}
    ties = []
    for i, parent_atom in enumerate(site_map):
        if parent_atom not in first:
            first[parent_atom] = i
            continue
        ties.append((f"phases.{phase_index}.atoms.{i}.biso",
                     f"phases.{phase_index}.atoms.{first[parent_atom]}.biso", 1.0, 0.0))
    return tuple(ties)


def _format_transform(big, small) -> str:
    """(P, p) as ``transform_BNS_Pp_abc`` text: the child's axes, then its origin."""
    def frac(v: float) -> Fraction:
        f = Fraction(float(v)).limit_denominator(96)
        if abs(float(f) - float(v)) > 1e-9:
            raise ValueError(f"transform entry {v!r} is not a simple rational")
        return f

    def term(f: Fraction, letter: str | None) -> str:
        mag = abs(f)
        if letter is None:
            return f"{mag.numerator}" if mag.denominator == 1 else f"{mag.numerator}/{mag.denominator}"
        head = letter if mag.numerator == 1 else f"{mag.numerator}{letter}"
        return head if mag.denominator == 1 else f"{head}/{mag.denominator}"

    def component(coeff, const) -> str:
        out = ""
        for f, letter in zip(coeff, "abc"):
            if f == 0:
                continue
            out += ("-" if f < 0 else ("+" if out else "")) + term(f, letter)
        if const != 0 or not out:
            out += ("-" if const < 0 else ("+" if out else "")) + term(const, None)
        return out

    cols = [component([frac(big[i][j]) for i in range(3)], Fraction(0)) for j in range(3)]
    offs = [component([Fraction(0)] * 3, frac(v)) for v in small]
    return f"{','.join(cols)};{','.join(offs)}"


def _cell_of(metric: np.ndarray) -> tuple[float, ...]:
    """(a, b, c, α, β, γ) of a metric tensor, Å and degrees."""
    a, b, c = (math.sqrt(float(metric[i, i])) for i in range(3))
    angle = [math.degrees(math.acos(max(-1.0, min(1.0, float(metric[i, j]) / (x * y)))))
             for (i, j), (x, y) in (((1, 2), (b, c)), ((0, 2), (a, c)), ((0, 1), (a, b)))]
    return (a, b, c, *angle)


def _child_images(child):
    """Every atom of the child cell, with the index of the listed atom it images.

    Also the image that *is* each listed atom (the one nearest its stored
    position, modulo the lattice), so the representative's displacement can be
    read off the paired field.
    """
    group = _group(child)
    pos, species, owner, rep = [], [], [], []
    for j, atom in enumerate(child.atoms):
        xyz = np.array([_value(atom.x), _value(atom.y), _value(atom.z)])
        images = [_wrap(np.asarray(im, dtype=np.float64))
                  for im in site_orbit(group, xyz).images]
        d = np.array(images) - xyz[None, :]
        d -= np.rint(d)
        rep.append(len(pos) + int(np.argmin(np.abs(d).max(axis=1))))
        for im in images:
            pos.append(im)
            species.append(element_symbol(atom.species))
            owner.append(j)
    return np.array(pos), tuple(species), np.array(owner), rep


def _pair(positions, species, basis: ModeBasis, tolerance: float) -> tuple[np.ndarray, np.ndarray]:
    """Pair the child's atoms with the parent's images: (raw field, partner).

    ``partner[i]`` is the reference atom child atom i is paired with and
    ``field[n]`` the minimal-image displacement of reference atom n, child
    fractions; same element, nearest in the reference metric, at most
    ``tolerance`` Å apart.
    """
    from scipy.optimize import linear_sum_assignment

    ref_pos, ref_species = basis.positions, basis.species
    if len(positions) != len(ref_pos) or sorted(species) != sorted(ref_species):
        raise ValueError(
            f"CHILD_ATOMS_UNPAIRED: the child cell holds {len(positions)} atoms "
            f"({_count(species)}) and the parent's image of it {len(ref_pos)} "
            f"({_count(ref_species)}); a mode decomposition needs the same atoms, one to one")
    chol = np.linalg.cholesky(basis.metric)
    disp = np.zeros_like(ref_pos)
    partner = np.empty(len(positions), dtype=np.int64)
    for element in sorted(set(ref_species)):
        rows = [i for i, s in enumerate(ref_species) if s == element]
        cols = [i for i, s in enumerate(species) if s == element]
        delta = positions[cols][None, :, :] - ref_pos[rows][:, None, :]
        delta -= np.rint(delta)
        cost = np.linalg.norm(delta @ chol, axis=2)
        r_idx, c_idx = linear_sum_assignment(cost)
        worst = float(cost[r_idx, c_idx].max())
        if worst > tolerance:
            raise ValueError(
                f"CHILD_ATOMS_UNPAIRED: a {element} atom of the child sits {worst:.3f} A from "
                f"the nearest free parent image, beyond tolerance={tolerance} A; check the "
                "transform and the origin shift")
        for r, c in zip(r_idx, c_idx):
            disp[rows[r]] = delta[r, c]
            partner[cols[c]] = rows[r]
    return disp, partner


def _whitener(basis: ModeBasis) -> np.ndarray:
    """Lᵀ/√lattice_points with L·Lᵀ = G_ref: |Lᵀ·u|² / lp is the AMPLIMODES norm."""
    return np.linalg.cholesky(basis.metric).T / math.sqrt(basis.lattice_points)


def _site_modes(comp: IrrepModes, ref: _Reference, labels, whiten) -> list[tuple[str, np.ndarray]]:
    """One irrep's modes re-based so that each moves one parent orbit.

    The parent's orbits are G-invariant, so each irrep's H-invariant subspace
    splits into its intersections with the fields on one orbit (the per-orbit
    modes AMPLIMODES tabulates, Orobengoa et al. 2009 § 2.3).  The split is
    orthogonal, so the modes stay orthonormal in the AMPLIMODES unit.  Where
    the global translation was removed at Γ, part of a polar irrep couples
    several orbits and cannot be split; that part keeps one basis, labelled
    with every orbit it moves.  Each piece takes :func:`_canonical`'s basis,
    so the result does not depend on the LAPACK build.
    """
    inv_w = np.linalg.inv(whiten)
    n_atoms = len(ref.species)
    q = np.array([(v @ whiten.T).reshape(-1) for v in comp.vectors]).T  # (3N, m)
    taken = np.zeros((q.shape[0], q.shape[0]))
    out: list[tuple[str, np.ndarray]] = []

    def unwhiten(cols: np.ndarray) -> list[np.ndarray]:
        # a component the symmetry zeroes comes back at 1e-17, and a true zero
        # is what tells the table a coordinate is not moved (held, as a fixed
        # special position's is), so round-off is taken to it
        out = []
        for c in cols.T:
            v = c.reshape(n_atoms, 3) @ inv_w.T
            v[np.abs(v) < _RANK_TOL * float(np.abs(v).max())] = 0.0
            out.append(v)
        return out

    for s, label in enumerate(labels):
        rows = np.repeat(ref.site == s, 3)
        if not rows.any():
            continue
        outside = q[~rows]
        if outside.size:
            _, sv, vt = np.linalg.svd(outside, full_matrices=True)
            rank = int(np.sum(sv > _RANK_TOL * max(1.0, sv[0] if sv.size else 0.0)))
            null = vt[rank:].T
        else:
            null = np.eye(q.shape[1])
        if null.shape[1] == 0:
            continue
        piece = _canonical(_orth(q @ null))
        taken += piece @ piece.T
        out.extend((label, v) for v in unwhiten(piece))
    rest = q @ q.T - taken
    left = _orth(rest)
    if left.shape[1]:
        piece = _canonical(left)
        moved = sorted({int(ref.site[n]) for n in range(n_atoms)
                        if np.abs(piece.reshape(n_atoms, 3, -1)[n]).max() > _RANK_TOL})
        label = "+".join(labels[s] for s in moved)
        out.extend((label, v) for v in unwhiten(piece))
    if len(out) != comp.n_modes:
        raise RuntimeError("the per-orbit split lost or gained a mode; this is a bug")
    return out


def _lost_translations(big) -> list[np.ndarray]:
    """The parent lattice vectors inside one child cell, one per coset of the child lattice."""
    inv = np.linalg.inv(big)
    corners = np.array([big @ np.array(c, float) for c in itertools.product((0, 1), repeat=3)])
    lo = np.floor(corners.min(axis=0)).astype(int)
    hi = np.ceil(corners.max(axis=0)).astype(int)
    seen: dict[tuple, np.ndarray] = {}
    for t in itertools.product(*(range(a, b + 1) for a, b in zip(lo, hi))):
        c = _wrap(inv @ np.array(t, float))
        key = tuple(np.round(c, 6))
        seen.setdefault(key, np.array(t, float))
    if abs(len(seen) - abs(np.linalg.det(big))) > 1e-6:
        raise RuntimeError("the parent lattice vectors in the child cell miscount; this is a bug")
    return list(seen.values())


def _parent_actions(parent, ref: _Reference, big, small) -> list[tuple[np.ndarray, np.ndarray]]:
    """Every operation of G modulo the child lattice, as (child-frame R, permutation).

    (g·u)_{n'} = R·u_{perm(n')}: the whole parent group, its lost translations
    included, acting on a field over the child cell.
    """
    inv = np.linalg.inv(big)
    rot_g, tran_g = _operations(_group(parent))
    lost_all = _lost_translations(big)
    seen: dict[tuple, tuple[np.ndarray, np.ndarray]] = {}
    for r, t in zip(rot_g, tran_g):
        rc = inv @ r.astype(float) @ big
        for lost in lost_all:
            perm = _permutation(r, t + lost, ref, inv, small)
            seen.setdefault((r.tobytes(), perm.tobytes()), (rc, perm))
    return list(seen.values())


def _act(action, field: np.ndarray) -> np.ndarray:
    rc, perm = action
    return field[perm] @ rc.T


def _stabiliser_order(field: np.ndarray, actions) -> int:
    """How many of ``actions`` leave ``field`` unchanged, to round-off."""
    scale = max(float(np.abs(field).max()), 1e-300)
    return sum(1 for a in actions if float(np.abs(_act(a, field) - field).max())
               <= _RANK_TOL * scale)


def _generic_seed(n: int) -> list[np.ndarray]:
    """Directions to try for the seed, generic first: no two coefficients equal.

    Unit vectors; the first coefficient is positive in each (the driving
    mode's sign is a domain choice, Perez-Mato 2010 § 7).
    """
    base = 1.0 + 0.618 * np.arange(n)
    out = []
    for signs in (np.ones(n), np.array([(-1.0) ** (i * (i - 1) // 2) for i in range(n)])):
        c = base * signs
        out.append(c / np.linalg.norm(c))
    return out


def displacive_statement(parent, child, transform, *, seed: float = DISTORTION_SEED,
                         reference: str = "average",
                         tolerance: float = 1.5) -> DisplaciveStatement:
    """State ``child`` as ``parent`` plus refinable mode amplitudes (WP-1419).

    The child's coordinates become x_j = base_j + Σ_ν A_ν·v_νj, with one
    absolute amplitude A_ν (Å) per symmetry-adapted mode of
    :func:`distortion_basis`, so a fit refines the amplitudes and the
    coordinates follow (Perez-Mato, Orobengoa & Aroyo 2010, *Acta Cryst.* A66,
    558, eqs. 3–7).  Any stated child is accepted: a single-k isotropy
    subgroup, a multi-k child such as LaMnO₃'s Pnma, or a P1 supercell
    carrying every mode.  Its group is kept as stated, so the phase's one
    operator list is the full child group H, and every consumer — reflections,
    multiplicities, the cell, the orbit expansion of the mode field — reads it.
    The statement checks that this is safe: every operation of H carries each
    mode's representative vectors onto the mode's own field at the image
    atoms, with sign +1 (milestone row D).

    **The modes are re-based per parent orbit** (:func:`_site_modes`), so each
    carries the label of the parent atom it moves, and they come with the
    primary irreps first.  The amplitudes are the child's own decomposition
    (as :func:`mode_amplitudes` reads it, round-off below ``_RANK_TOL`` taken
    as zero); the record's ``base`` carries a polar child's global translation,
    which is not a mode.

    **The seed.**  A lost parent operation maps the child to a domain-related
    structure with the same powder pattern, so χ²(D(g)·A) = χ²(A) for the
    action D(g) of every parent operation on the amplitude vector, and its
    gradient at A = 0 lies in the identity irrep's subspace:
    every other amplitude has an exactly zero column at the parent (#286,
    2026-09-16, measured; Perez-Mato 2010 § 7 for the domains).  So when every
    amplitude outside the identity irrep is zero, the statement sets them to a
    vector of norm ``seed`` (Å), along a direction whose stabiliser in G is
    exactly H, checked on the parent operations' actions: a seed along one
    basis mode can sit on a higher-symmetry sub-direction and leave the other
    modes at a stationary point of the residual symmetry (``moments.SEED_TILT``
    records that shape for moments).  The first mode's sign is positive, which
    chooses a domain; the relative signs are the generic direction's, recorded
    in ``seed`` and never tuned.  A child already distorted is never
    re-seeded.  ``seed=0`` states the child at the parent unseeded, which a fit
    then refuses to free (``ParameterTable``).

    A mixed-occupancy parent site is refused (two parent atoms on one site,
    ``_reference``), as are atoms that do not pair one to one
    (``CHILD_ATOMS_UNPAIRED``).  The cell is the child's own, under its own
    group's constraints.
    """
    from ...schemas.common import Parameter
    from ...schemas.structure import DistortionMode, DistortionModes

    basis, ref = _distortion_basis(parent, child, transform, reference)
    big, small = basis.transform
    labels = [a.label for a in parent.atoms]
    whiten = _whitener(basis)

    # the modes, per parent orbit, primary irreps first
    order = sorted(range(len(basis.components)),
                   key=lambda i: basis.components[i].primary is not True)
    actions = _parent_actions(parent, ref, big, small)
    modes: list[tuple[IrrepModes, int, str, bool, np.ndarray]] = []
    for i in order:
        comp = basis.components[i]
        for index, (label, v) in enumerate(_site_modes(comp, ref, labels, whiten)):
            invariant = all(float(np.abs(_act(a, v) - v).max()) <= _RANK_TOL * max(
                float(np.abs(v).max()), 1e-300) for a in actions)
            modes.append((comp, index, label, invariant, v))

    # the child's own field, paired with the reference
    positions, species, owner, reps = _child_images(child)
    raw, partner = _pair(positions, species, basis, tolerance)
    shift = raw.mean(axis=0)
    disp = raw - shift[None, :]

    def inner(u, v) -> float:
        return float(np.einsum("ni,ij,nj->", u, basis.metric, v)) / basis.lattice_points

    amps = np.array([inner(v, disp) for *_, v in modes])
    amps[np.abs(amps) < _RANK_TOL] = 0.0
    fields = np.array([v for *_, v in modes]) if modes else np.zeros((0, len(ref.species), 3))
    left = disp - np.tensordot(amps, fields, axes=1)
    if math.sqrt(max(inner(left, left), 0.0)) > _POSITION_TOL:
        raise ValueError(
            "the child's displacement field is not reached by its own modes (residual "
            f"{math.sqrt(inner(left, left)):.3g} A): its atoms do not have the symmetry "
            "its group states")

    # row D made concrete: the declared group carries each mode onto itself
    rot_h, tran_h = _operations(_group(child))
    for comp, index, label, _, v in modes:
        for r, t in zip(rot_h, tran_h):
            image = _wrap(basis.positions @ r.T.astype(float) + t[None, :])
            for n, pos in enumerate(image):
                d = basis.positions - pos[None, :]
                d -= np.rint(d)
                hit = np.flatnonzero(np.all(np.abs(d) < 1e-5, axis=1))
                if len(hit) != 1 or float(np.abs(r @ v[n] - v[hit[0]]).max()) > (
                        _RANK_TOL * max(float(np.abs(v).max()), 1e-300) + 1e-12):
                    raise RuntimeError(
                        f"mode {comp.irrep} #{index} ({label}) is not carried onto itself by "
                        "an operation of the child's group; the phase's operator list and "
                        "the mode field's stabiliser differ, which is a bug")

    # the seed
    broken = [i for i, (*_, inv_, _v) in enumerate(modes) if not inv_]
    seeded: dict[str, float] = {}
    if seed > 0.0 and broken and not np.any(amps[broken]):
        n_h = len(rot_h)
        for direction in _generic_seed(len(broken)):
            trial = amps.copy()
            trial[broken] = seed * direction
            if _stabiliser_order(np.tensordot(trial, fields, axes=1), actions) == n_h:
                amps = trial
                seeded = {f"phases.0.distortion_modes.modes.{i}.amplitude": float(amps[i])
                          for i in broken}
                break
        else:
            raise ValueError(
                f"no seed direction in the child's modes has exactly the child's group "
                f"{child.space_group!r} as its stabiliser in the parent group: a generic "
                "distortion of the parent in this cell has more symmetry than the stated "
                "child, so the child is not an isotropy subgroup of its displacements; "
                "state it in the group a generic distortion reaches")

    # the record and the coordinates it derives
    placed = np.tensordot(amps, fields, axes=1) if len(modes) else np.zeros_like(disp)
    atoms = []
    base_rows = []
    for j, atom in enumerate(child.atoms):
        i = reps[j]
        n = int(partner[i])
        xyz = np.array([_value(atom.x), _value(atom.y), _value(atom.z)])
        origin = ref.child_frac[n] + shift
        origin = origin + np.rint(xyz - origin)
        base_rows.append(tuple(float(c) for c in origin))
        moved = any(np.any(v[n] != 0.0) for *_, v in modes)
        if not moved:
            atoms.append(atom)
            continue
        new = origin + placed[n]
        atoms.append(atom.model_copy(update={
            c: getattr(atom, c).model_copy(update={"value": float(new[k]), "vary": False})
            for k, c in enumerate("xyz")}))
    site_map = tuple(int(ref.site[partner[reps[j]]]) for j in range(len(child.atoms)))
    record = DistortionModes(
        parent_space_group=str(parent.space_group),
        transform=_format_transform(big, small),
        reference_cell=_cell_of(basis.metric),
        base=base_rows,
        modes=[DistortionMode(
            irrep=comp.irrep, k=comp.k, isotropy_group=comp.isotropy_group, index=index,
            site=label, parent_invariant=invariant,
            vectors=[tuple(float(x) for x in v[partner[reps[j]]])
                     for j in range(len(child.atoms))],
            amplitude=Parameter(value=float(a), unit="A"))
            for (comp, index, label, invariant, v), a in zip(modes, amps, strict=True)])
    phase = child.model_copy(update={"atoms": atoms, "distortion_modes": record})
    return DisplaciveStatement(
        phase=phase, basis=basis, transform=(big, small), site_map=site_map,
        biso_ties=parent_site_ties(site_map), seed=seeded)
