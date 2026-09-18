"""Small (allowed) irreps of the little group of a propagation vector k.

Representation analysis of a magnetic structure (Bertaut, 1968, *Acta Cryst.*
A**24**, 217) decomposes the magnetic representation of a site orbit into the
small irreps of the little group G_k.  This module builds those irreps; the
decomposition and the projection onto basis vectors are the next rung and are
written against the API below.

**Public API — fixed 2026-09-05.  Everything downstream is briefed against
these names and these conventions.**

::

    KVector = tuple[Fraction, Fraction, Fraction]

    as_kvector(k)                             -> KVector
    canonical_kvector(space_group, k)         -> KVector
    equivalent_kvectors(space_group, k1, k2)  -> bool
    primitive_basis(space_group)              -> tuple[KVector, KVector, KVector]
    primitive_kvector(space_group, k)         -> KVector
    primitive_operations(space_group)         -> (rotations, translations)
    star(space_group, k)                      -> tuple[KVector, ...]
    little_group(space_group, k)              -> LittleGroup
    little_group_from_operations(rotations, translations, k, centrings=...)
                                              -> LittleGroup
    factor_system_exponents(little)           -> (n, n) object array of Fraction
    factor_system(little)                     -> (n, n) complex
    small_irreps(space_group, k)              -> tuple[SmallIrrep, ...]
    small_irreps_of(little, *, factor=None)   -> tuple[SmallIrrep, ...]
    inversion_character(irrep)                -> complex | None
    inversion_parity(irrep)                   -> int | None

``space_group`` is anything :func:`~rietx.crystallography.symmetry.get_spacegroup`
resolves — an H-M symbol, a setting symbol with its ``:`` extension, or a
``gemmi.SpaceGroup``.  ``k`` is a triple of **rationals** (``Fraction``, ``int``,
``"1/2"``, or a float that is exactly a rational of small denominator).

Conventions, all four of which a caller can get wrong silently:

1. **k is in fractional coordinates of the CONVENTIONAL reciprocal cell** — the
   basis a CIF, a Bilbao page and ``_parent_propagation_vector`` all speak.  For
   a centred lattice that is *not* the same as the primitive reciprocal basis,
   and the difference is not cosmetic: the true reciprocal lattice is the
   sublattice of integer *hkl* obeying the centring condition, so in F m -3 m
   the point k = (0, 0, 1) is the X point with a little group of order 16, not
   Γ with order 48.  Reduction of k modulo the reciprocal lattice therefore goes
   through :func:`primitive_basis`, never componentwise modulo 1.
   :func:`little_group_from_operations` is the door for operations already in a
   primitive setting (spglib's, spgrep's): pass ``centrings=()`` and a k in that
   same primitive basis.

2. **The reciprocal-space action is the transposed rotation.**  G_k is the set
   of operations with Rᵀk ≡ k modulo the reciprocal lattice (root ``CLAUDE.md``:
   a real-space x' = Rx + t sends h to Rᵀh).  {Rᵀ} is a group too, so an orbit
   *count* is right either way — the star size and the little-group order are
   identical under R and Rᵀ in every crystal system.  What differs is *which*
   operations are in G_k for a non-cubic setting, hence the irreps.

3. **The translation convention is D({E|a}) = exp(−2πi k·a)·1** (Bradley &
   Cracknell, 1972, ch. 4; Izyumov, Naish & Ozerov, 1991).  It is the same sign
   the permutation representation of a site orbit carries in its return-vector
   phase exp(−2πi k·a_g), so Γ_perm ⊗ Γ_axial decomposes against these irreps
   with no sign fix-up.  spgrep uses the same sign, pinned by a test.

4. **A matrix is attached to an operation, not to a rotation.**  The small
   irreps are projective representations of the little co-group P_k = G_k/T, and
   the projective matrices depend on which coset representative (R, v) each
   rotation is read off.  ``SmallIrrep.matrices[i]`` is therefore D of
   ``(little.rotations[i], little.translations[i])`` — gemmi's own coset
   representatives — and the character is a function on those operations.  Under
   a lattice translation, D(R, v + a) = exp(−2πi k·a) · D(R, v).  Changing the
   representatives is a gauge transformation: it changes the factor system by a
   coboundary and the matrices by phases, and leaves the irrep *set* alone.

**Algorithm.**  Small irreps of G_k ↔ projective irreps of the finite little
co-group P_k with factor system

    ω(g_i, g_j) = exp(−2πi k·a_ij),   a_ij = v_i + R_i v_j − v_l  (R_i R_j = R_l),

where a_ij is a lattice vector — a *centring* vector for a centred group, which
is why the centrings must be carried and not quotiented away.  On the zone
boundary of a non-symmorphic group ω is not a coboundary and the irreps are
genuinely projective (Bradley & Cracknell, 1972, ch. 4 and 7).  The projective
irreps are extracted by splitting the ω-twisted regular representation of P_k,
which has dimension |P_k| and contains each irrep d_α times: a random Hermitian
matrix averaged over the representation lies in its commutant, and each
eigenspace of the average is an irreducible invariant subspace.  This is the
"random" branch of the constructive scheme; Neto (1973, *Acta Cryst.* A**29**,
464) gives the deterministic subgroup-chain alternative, which spgrep
implements as ``method="Neto"`` and which is what the oracle tests compare
against.  Every returned set is verified against the defining relation
D(g_i)D(g_j) = ω(g_i, g_j) D(g_i g_j) before it is handed back.

**What is deterministic and what is not.**  The seed sequence is fixed, so the
number of irreps, their dimensions, their characters and the order they come
back in are reproducible.  The *matrices* are not canonical: an irrep is defined
only up to a unitary intertwiner, and which representative comes out depends on
the eigenvectors LAPACK returns.  So compare characters, never matrices — that
is what the oracle tests do, and what a caller should do too.

**What is exact and what is not.**  k, the translations, the centrings and the
factor-system *exponents* are exact ``Fraction`` arithmetic; ω is exact for the
quarter-turn phases (every k with components in {0, ±1/2} — the whole
zone-boundary set where the projective case lives — gives ω = ±1).  The irrep
matrices come out of a numerical eigendecomposition and carry
:data:`IRREP_ATOL`.

**Labels.**  The labels here are positional (``S1``, ``S2``, … in a
deterministic order: by dimension, then by character) and are **not** CDML
labels.  Mapping to the CDML k-labels and irrep labels (Cracknell, Davies,
Miller & Love, 1979, *Kronecker Product Tables* Vol. 1; Aroyo et al., 2014,
*Acta Cryst.* A**70**, 126) needs the per-Bravais-lattice k-label tables, which
are a data source of their own — deferred, and deliberately not faked by a
made-up naming scheme that would look like CDML and disagree with it.

References
----------
Bertaut, E. F. (1968). *Acta Cryst.* A**24**, 217 — representation analysis of
magnetic structures.
Bradley, C. J. & Cracknell, A. P. (1972). *The Mathematical Theory of Symmetry
in Solids*. Oxford: Clarendon — small irreps by induction from the little
co-group, and the projective case.
Neto, N. (1973). *Acta Cryst.* A**29**, 464 — a constructive algorithm for
small irreps.
Izyumov, Yu. A., Naish, V. E. & Ozerov, R. P. (1991). *Neutron Diffraction of
Magnetic Materials*. New York: Consultants Bureau — the little group, the star,
and the return-translation phase.
"""

from __future__ import annotations

import functools
import math
from dataclasses import dataclass
from fractions import Fraction

import gemmi
import numpy as np

from ..symmetry import get_spacegroup

#: A propagation vector: three exact rationals in the basis named by the caller
#: (conventional reciprocal cell for the space-group entry points).
KVector = tuple[Fraction, Fraction, Fraction]

#: Largest denominator :func:`as_kvector` will read out of a float.  A
#: commensurate magnetic structure has a k with a small denominator by
#: definition (it is what makes the magnetic cell finite); 64 admits every
#: supercell anyone refines and still refuses a genuinely irrational component
#: rather than snapping it to a nearby fraction.
K_MAX_DENOMINATOR = 64

#: How far a float k-component may sit from the rational
#: :data:`K_MAX_DENOMINATOR` reads out of it.  1/3 as a float is 1.8e-17 from
#: ``Fraction(1, 3)``, so this is nine orders of slack on the arithmetic and
#: still refuses 0.3123 (nearest denominator-64 rational is 3.9e-4 away).
K_FLOAT_TOL = 1e-9

#: Tolerance on the irrep matrices, which come from an eigendecomposition of a
#: matrix of order |P_k| ≤ 48 built from unit-modulus entries.  Used for the
#: representation identity, unitarity, the irreducibility check and character
#: comparison.  The measured worst residual over the 230-group sweep is far
#: below it (quoted in tests/test_magnetic_irreps.py).
IRREP_ATOL = 1e-8

#: Seeds tried, in order, for the random Hermitian matrix whose commutant
#: average splits the twisted regular representation.  A fixed sequence keeps
#: the output reproducible; more than one is needed only if an accidental
#: eigenvalue coincidence makes two irreducible subspaces inseparable, which
#: the verification step below detects.
_SEEDS = (0, 1, 2, 3, 4, 5, 6, 7)

_ZERO = Fraction(0)
_EYE3 = np.eye(3, dtype=np.int64)


# --------------------------------------------------------------------------
# k vectors, the reciprocal lattice, and the primitive basis
# --------------------------------------------------------------------------

def _as_fraction(value, *, what: str) -> Fraction:
    """One exact rational from an int, a Fraction, a "p/q" string or a float."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, np.integer)):
        return Fraction(int(value))
    if isinstance(value, str):
        try:
            return Fraction(value)
        except ValueError as exc:
            raise ValueError(f"{what} component {value!r} is not a rational") from exc
    if isinstance(value, (float, np.floating)):
        f = Fraction(float(value)).limit_denominator(K_MAX_DENOMINATOR)
        if abs(float(f) - float(value)) > K_FLOAT_TOL:
            raise ValueError(
                f"{what} component {float(value)!r} is not a rational with denominator "
                f"<= {K_MAX_DENOMINATOR}. Small irreps are defined here for a commensurate "
                "k only; an incommensurate propagation vector needs the superspace route "
                "and is not implemented. Pass an exact Fraction if the value is rational."
            )
        return f
    raise TypeError(f"{what} component of type {type(value).__name__} is not a rational")


def as_kvector(k) -> KVector:
    """Three exact rationals from any accepted spelling of a propagation vector.

    Accepts ints, ``Fraction``s, ``"1/2"``-style strings and floats that are
    exactly a rational of denominator at most :data:`K_MAX_DENOMINATOR`.  A
    float that is not — an incommensurate k — is refused by name: that case is
    a superspace problem, not a small-irrep one.
    """
    items = list(k)
    if len(items) != 3:
        raise ValueError(f"a propagation vector has three components, got {len(items)}")
    return (
        _as_fraction(items[0], what="k"),
        _as_fraction(items[1], what="k"),
        _as_fraction(items[2], what="k"),
    )


def _op_rotation(op: gemmi.Op) -> np.ndarray:
    """Integer rotation part of a gemmi operation (gemmi scales by ``Op.DEN``)."""
    den = gemmi.Op.DEN
    rot = np.asarray(op.rot, dtype=np.int64)
    if np.any(rot % den):
        raise ValueError(f"non-integer rotation in operation {op.triplet()!r}")
    return rot // den


def _op_translation(op: gemmi.Op) -> KVector:
    """Exact rational translation part of a gemmi operation."""
    den = gemmi.Op.DEN
    return tuple(Fraction(int(t), den) for t in op.tran)  # type: ignore[return-value]


def _resolve(space_group):
    """A group object from a symbol, an IT number as a string, or itself.

    An :class:`~rietx.crystallography.symmetry.OperatorGroup` passes through:
    the star of a k and the centring set are read off ``operations()``, which
    such a group has, so a phase carrying its own list can be asked for them.
    """
    from ...crystallography.symmetry import OperatorGroup

    if isinstance(space_group, (gemmi.SpaceGroup, OperatorGroup)):
        return space_group
    if isinstance(space_group, (int, np.integer)):
        return get_spacegroup(str(int(space_group)))
    return get_spacegroup(str(space_group))


def _centrings(sg: gemmi.SpaceGroup) -> tuple[KVector, ...]:
    """Centring translations of the lattice, including (0, 0, 0)."""
    den = gemmi.Op.DEN
    out = []
    for cen in sg.operations().cen_ops:
        out.append(tuple(Fraction(int(c), den) for c in cen))
    return tuple(out)  # type: ignore[return-value]


def _row_hnf(rows: list[list[int]]) -> list[list[int]]:
    """Row-style Hermite normal form of an integer lattice, as its basis rows.

    Deterministic, so the primitive basis a group gets is the same every run.
    """
    m = [list(r) for r in rows]
    pivot_rows: list[int] = []
    r = 0
    for c in range(3):
        while True:
            nz = [i for i in range(r, len(m)) if m[i][c] != 0]
            if len(nz) <= 1:
                break
            nz.sort(key=lambda i: abs(m[i][c]))
            p = nz[0]
            for i in nz[1:]:
                q = m[i][c] // m[p][c]
                m[i] = [a - q * b for a, b in zip(m[i], m[p])]
        nz = [i for i in range(r, len(m)) if m[i][c] != 0]
        if not nz:
            continue
        m[r], m[nz[0]] = m[nz[0]], m[r]
        if m[r][c] < 0:
            m[r] = [-a for a in m[r]]
        # reduce the rows above this pivot, which makes the form canonical
        for i in pivot_rows:
            q = m[i][c] // m[r][c]
            if q:
                m[i] = [a - q * b for a, b in zip(m[i], m[r])]
        pivot_rows.append(r)
        r += 1
    if r != 3:
        raise ValueError("the lattice generators do not span three dimensions")
    return [m[i] for i in range(3)]


_H = Fraction(1, 2)
_T = Fraction(1, 3)
_TT = Fraction(2, 3)

#: The conventional primitive bases, as rows in conventional fractional
#: coordinates: the transposes of the transformation matrices of International
#: Tables A Table 1.5.1.1, i.e. the same primitive cells spglib and every other
#: code names for these centrings.  Used in preference to the Hermite normal
#: form below so that :func:`primitive_operations` returns the operations in the
#: setting a reader (and spgrep's tabulated point groups) expects; a centring
#: that is not one of these, or a setting whose centring vectors these rows do
#: not span, falls back to the HNF, which is correct for any lattice.
_STANDARD_PRIMITIVE_BASIS: dict[str, tuple[KVector, KVector, KVector]] = {
    "A": ((Fraction(1), _ZERO, _ZERO), (_ZERO, _H, _H), (_ZERO, -_H, _H)),
    "B": ((_H, _ZERO, _H), (_ZERO, Fraction(1), _ZERO), (-_H, _ZERO, _H)),
    "C": ((_H, -_H, _ZERO), (_H, _H, _ZERO), (_ZERO, _ZERO, Fraction(1))),
    "I": ((-_H, _H, _H), (_H, -_H, _H), (_H, _H, -_H)),
    "F": ((_ZERO, _H, _H), (_H, _ZERO, _H), (_H, _H, _ZERO)),
    "R": ((_TT, _T, _T), (-_T, _T, _T), (-_T, -_TT, _T)),
}


def _det3(a) -> Fraction:
    return (
        a[0][0] * (a[1][1] * a[2][2] - a[1][2] * a[2][1])
        - a[0][1] * (a[1][0] * a[2][2] - a[1][2] * a[2][0])
        + a[0][2] * (a[1][0] * a[2][1] - a[1][1] * a[2][0])
    )


@functools.lru_cache(maxsize=64)
def _primitive_basis_cached(cens: tuple, letter: str
                            ) -> tuple[KVector, KVector, KVector]:
    """The primitive basis of a lattice given by its centring translations.

    Keyed on the **centrings and the Bravais letter**, not on a symbol, so a
    group carrying its own operation list is served too — its label is not in
    any table, and its lattice may be one no Bravais letter names (a child cell
    holding the parent's half translation: gemmi's ``find_centering`` returns
    no letter for it, the standard shortcut below is skipped, and the Hermite
    normal form answers, which is the general path and always correct).
    """
    standard = _STANDARD_PRIMITIVE_BASIS.get(letter)
    if standard is not None and _det3(standard) == Fraction(1, len(cens)):
        in_lattice = all(
            any(all((x - c).denominator == 1 for x, c in zip(row, cen)) for cen in cens)
            for row in standard
        )
        if in_lattice:
            return standard
    den = 1
    for cen in cens:
        for comp in cen:
            den = den * comp.denominator // math.gcd(den, comp.denominator)
    rows = [[den if i == j else 0 for j in range(3)] for i in range(3)]
    rows += [[int(comp * den) for comp in cen] for cen in cens]
    hnf = _row_hnf(rows)
    return tuple(tuple(Fraction(x, den) for x in row) for row in hnf)  # type: ignore[return-value]


def primitive_basis(space_group) -> tuple[KVector, KVector, KVector]:
    """Primitive lattice vectors of the group's lattice, in conventional fractions.

    Rows of the matrix M with a_primitive = M · a_conventional.  For a P lattice
    this is the identity; for F m -3 m it is a basis of the face-centred lattice,
    whose determinant 1/4 is the number of lattice points the conventional cell
    holds.  The Hermite normal form makes the choice deterministic — any
    primitive basis of the same lattice answers every question this module asks
    of it, so which one is a reproducibility matter, not a physical one.

    A k in conventional fractional reciprocal coordinates converts to the
    primitive reciprocal basis as k_primitive = M · k_conventional, which is
    what makes :func:`canonical_kvector` and the little-group test see the true
    reciprocal lattice rather than the integer *hkl* grid (International Tables
    A, sect. 1.5; the consequence is spelled out in the module docstring).
    """
    sg = _resolve(space_group)
    letter = (sg.xhm()[0] if isinstance(sg, gemmi.SpaceGroup)
              else str(sg.operations().find_centering()))
    return _primitive_basis_cached(_centrings(sg), letter)


def _matmul3(a, b):
    """3×3 by 3×3 over exact rationals."""
    return tuple(
        tuple(sum(a[i][t] * b[t][j] for t in range(3)) for j in range(3)) for i in range(3)
    )


def _matvec3(a, v):
    """3×3 by a 3-vector over exact rationals."""
    return tuple(sum(a[i][j] * v[j] for j in range(3)) for i in range(3))


def _inv3(a):
    """Exact inverse of a rational 3×3 matrix, by the adjugate."""
    det = _det3(a)
    if det == 0:
        raise ValueError("singular matrix")
    cof = [[Fraction(0)] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            r = [x for x in range(3) if x != i]
            c = [y for y in range(3) if y != j]
            minor = a[r[0]][c[0]] * a[r[1]][c[1]] - a[r[0]][c[1]] * a[r[1]][c[0]]
            cof[i][j] = ((-1) ** (i + j)) * minor
    # inverse = adjugate / det, adjugate = transpose of the cofactor matrix
    return tuple(tuple(cof[j][i] / det for j in range(3)) for i in range(3))


def _transpose3(a):
    return tuple(tuple(a[j][i] for j in range(3)) for i in range(3))


def canonical_kvector(space_group, k) -> KVector:
    """``k`` reduced into the first Brillouin cell of the TRUE reciprocal lattice.

    Reduction is componentwise modulo 1 in the *primitive* reciprocal basis and
    then mapped back to conventional coordinates, so two k differing by a
    reciprocal lattice vector return the same triple and two that differ by an
    integer *hkl* the centring forbids do not.  The returned components are in
    conventional fractional coordinates and need not lie in [0, 1): in F m -3 m,
    k = (0, 0, 1) is canonical (it is X), while k = (0, 0, 2) reduces to
    (0, 0, 0).
    """
    sg = _resolve(space_group)
    m = primitive_basis(sg)
    kk = as_kvector(k)
    prim = _matvec3(m, kk)
    prim = tuple(c - Fraction(math.floor(c)) for c in prim)
    return _matvec3(_inv3(m), prim)  # type: ignore[return-value]


def equivalent_kvectors(space_group, k1, k2) -> bool:
    """True when ``k1 − k2`` is a vector of the group's reciprocal lattice."""
    sg = _resolve(space_group)
    m = primitive_basis(sg)
    a, b = as_kvector(k1), as_kvector(k2)
    diff = _matvec3(m, tuple(x - y for x, y in zip(a, b)))
    return all(c.denominator == 1 for c in diff)


def primitive_kvector(space_group, k) -> KVector:
    """``k`` converted from conventional to primitive reciprocal coordinates.

    k_primitive = M · k_conventional with M the row matrix of
    :func:`primitive_basis`.  This is the pairing
    :func:`primitive_operations` needs — the operations and the k must be in
    the same basis, and a k left in conventional coordinates beside primitive
    operations is the centred-lattice error the module docstring names.
    """
    return _matvec3(primitive_basis(space_group), as_kvector(k))  # type: ignore[return-value]


def primitive_operations(space_group):
    """Coset representatives of the group in a PRIMITIVE setting.

    Returns ``(rotations, translations)`` — an ``(n, 3, 3)`` integer array and a
    tuple of exact rational triples — for the same operations
    :func:`little_group` reads, expressed in the primitive basis of
    :func:`primitive_basis`.  This is the form spglib and spgrep speak, and the
    door :func:`little_group_from_operations` takes; a k handed alongside them
    must be in the matching primitive reciprocal basis
    (k_primitive = M · k_conventional).
    """
    sg = _resolve(space_group)
    m = primitive_basis(sg)
    # x_primitive = N · x_conventional with N = (M⁻¹)ᵀ; a rotation conjugates,
    # a translation transforms as a point.
    n_mat = _transpose3(_inv3(m))
    n_inv = _transpose3(m)
    rots, trans = [], []
    for op in sg.operations().sym_ops:
        r = tuple(tuple(Fraction(int(x)) for x in row) for row in _op_rotation(op))
        rp = _matmul3(_matmul3(n_mat, r), n_inv)
        if any(c.denominator != 1 for row in rp for c in row):
            raise ValueError(f"operation {op.triplet()!r} is not integral in the primitive basis")
        tp = _matvec3(n_mat, _op_translation(op))
        rots.append([[int(c) for c in row] for row in rp])
        trans.append(tuple(c - Fraction(math.floor(c)) for c in tp))
    return np.array(rots, dtype=np.int64), tuple(trans)


# --------------------------------------------------------------------------
# the little group and the star
# --------------------------------------------------------------------------

def _is_reciprocal_lattice_vector(diff: KVector, centrings: tuple[KVector, ...]) -> bool:
    """True when ``diff`` is a vector of the reciprocal lattice.

    A lattice L containing the conventional cell plus centring vectors has a
    reciprocal lattice that is the *sublattice* of integer hkl with h·c integral
    for every centring vector c — the F lattice's reciprocal is body-centred,
    not the full integer grid.
    """
    if any(c.denominator != 1 for c in diff):
        return False
    for cen in centrings:
        if sum(d * c for d, c in zip(diff, cen)).denominator != 1:
            return False
    return True


@dataclass(frozen=True, eq=False)
class LittleGroup:
    """Coset representatives of G_k = {g ∈ G : Rᵀk ≡ k mod the reciprocal lattice}.

    One entry per coset of the lattice translation group, in the order the
    parent group lists them, so ``rotations[i]``/``translations[i]`` is the
    operation ``SmallIrrep.matrices[i]`` belongs to.  ``indices`` gives each
    one's position in the parent operation list, which is what a caller needs
    to line these up with a site orbit or with an oracle's own list.
    """

    k: KVector
    rotations: np.ndarray  # (n, 3, 3) int64
    translations: tuple[KVector, ...]
    indices: tuple[int, ...]
    centrings: tuple[KVector, ...]
    spacegroup: str | None = None

    @property
    def order(self) -> int:
        """|G_k / T|, the order of the little co-group P_k."""
        return len(self.indices)

    @property
    def triplets(self) -> tuple[str, ...]:
        """The operations as ``x,y,z`` strings, for messages and reports."""
        out = []
        for r, t in zip(self.rotations, self.translations):
            op = gemmi.Op("x,y,z")
            op.rot = [[int(x) * gemmi.Op.DEN for x in row] for row in r]
            op.tran = [int(c * gemmi.Op.DEN) for c in t]
            out.append(op.triplet())
        return tuple(out)

    @functools.cached_property
    def composition(self) -> tuple[np.ndarray, tuple[tuple[KVector, ...], ...]]:
        """``(table, shifts)``: the P_k multiplication table and its lattice shifts.

        ``table[i, j] = l`` with R_i·R_j = R_l, and ``shifts[i][j]`` is the
        lattice vector a_ij = v_i + R_i v_j − v_l the composition leaves over.
        The whole factor system is that shift read through exp(−2πi k·a).
        """
        n = self.order
        rots = self.rotations
        key = {tuple(r.flatten().tolist()): i for i, r in enumerate(rots)}
        table = np.empty((n, n), dtype=np.int64)
        shifts: list[tuple[KVector, ...]] = []
        for i in range(n):
            row: list[KVector] = []
            ri = rots[i]
            vi = self.translations[i]
            for j in range(n):
                prod = ri @ rots[j]
                idx = key.get(tuple(prod.flatten().tolist()))
                if idx is None:
                    raise ValueError("the little-group rotations are not closed under products")
                table[i, j] = idx
                rvj = tuple(
                    sum(Fraction(int(ri[a][b])) * self.translations[j][b] for b in range(3))
                    for a in range(3)
                )
                vl = self.translations[idx]
                row.append(tuple(vi[a] + rvj[a] - vl[a] for a in range(3)))  # type: ignore[arg-type]
            shifts.append(tuple(row))
        return table, tuple(shifts)

    @property
    def multiplication_table(self) -> np.ndarray:
        """``table[i, j] = l`` with R_i·R_j = R_l."""
        return self.composition[0]

    @property
    def inversion_index(self) -> int | None:
        """Position of the operation whose rotation is −1, if G_k holds one."""
        for i, r in enumerate(self.rotations):
            if np.array_equal(r, -_EYE3):
                return i
        return None

    @property
    def has_minus_k(self) -> bool:
        """True when 2k is a reciprocal lattice vector, i.e. −k ≡ k."""
        return _is_reciprocal_lattice_vector(
            tuple(2 * c for c in self.k), self.centrings  # type: ignore[arg-type]
        )


def little_group_from_operations(rotations, translations, k, *, centrings=((0, 0, 0),),
                                 space_group: str | None = None) -> LittleGroup:
    """The little group of ``k`` inside an explicit operation list.

    ``rotations``/``translations`` are coset representatives of the lattice
    translation group — one per rotation, no centring copies — and ``k`` is in
    the reciprocal basis matching whatever direct basis they are written in.
    For operations already in a primitive setting (spglib's, spgrep's) pass
    ``centrings=()``; for the conventional setting of a centred group pass its
    centring vectors, or use :func:`little_group`, which does.

    The membership test is Rᵀk ≡ k modulo the reciprocal lattice, not R k
    (root ``CLAUDE.md``: reciprocal space carries the transposed rotation).
    """
    rots = np.asarray(rotations, dtype=np.int64)
    if rots.ndim != 3 or rots.shape[1:] != (3, 3):
        raise ValueError("rotations must have shape (n, 3, 3)")
    trans = tuple(as_kvector(t) for t in translations)
    if len(trans) != len(rots):
        raise ValueError("rotations and translations must have the same length")
    kk = as_kvector(k)
    cens = tuple(as_kvector(c) for c in centrings)
    keep, keep_rot, keep_tran = [], [], []
    for i, r in enumerate(rots):
        rt_k = tuple(
            sum(Fraction(int(r[a][b])) * kk[a] for a in range(3)) for b in range(3)
        )  # (Rᵀk)_b = Σ_a R_ab k_a
        if _is_reciprocal_lattice_vector(
            tuple(x - y for x, y in zip(rt_k, kk)), cens  # type: ignore[arg-type]
        ):
            keep.append(i)
            keep_rot.append(r)
            keep_tran.append(trans[i])
    return LittleGroup(
        k=kk,
        rotations=np.array(keep_rot, dtype=np.int64).reshape(len(keep), 3, 3),
        translations=tuple(keep_tran),
        indices=tuple(keep),
        centrings=cens,
        spacegroup=space_group,
    )


def little_group(space_group, k) -> LittleGroup:
    """The little group of ``k`` in the conventional setting of ``space_group``.

    ``k`` is in fractional coordinates of the **conventional** reciprocal cell.
    The operations are gemmi's coset representatives (``sym_ops``); the centring
    translations are carried separately and enter both the reciprocal-lattice
    test and the factor system, which is where a centred lattice would otherwise
    go wrong (module docstring, convention 1).
    """
    sg = _resolve(space_group)
    ops = sg.operations().sym_ops
    rots = np.array([_op_rotation(op) for op in ops], dtype=np.int64)
    trans = tuple(_op_translation(op) for op in ops)
    return little_group_from_operations(
        rots, trans, k, centrings=_centrings(sg), space_group=sg.xhm()
    )


def star(space_group, k) -> tuple[KVector, ...]:
    """The distinct arms Rᵀk of the star of ``k``, canonicalised and sorted.

    Its length times the little-group order is the order of the point group, so
    it is also the index [G : G_k] the full space-group irrep is induced over
    (Izyumov, Naish & Ozerov, 1991).
    """
    sg = _resolve(space_group)
    kk = as_kvector(k)
    seen: dict[KVector, None] = {}
    for op in sg.operations().sym_ops:
        r = _op_rotation(op)
        arm = tuple(sum(Fraction(int(r[a][b])) * kk[a] for a in range(3)) for b in range(3))
        seen[canonical_kvector(sg, arm)] = None
    return tuple(sorted(seen))


# --------------------------------------------------------------------------
# the factor system
# --------------------------------------------------------------------------

def factor_system_exponents(little: LittleGroup) -> np.ndarray:
    """Exact exponents of the factor system: ``(n, n)`` of ``Fraction`` in [0, 1).

    Entry (i, j) is (−k·a_ij) mod 1 with a_ij the lattice vector left over by
    R_i·R_j, so ω(i, j) = exp(2πi · exponent).  Kept exact and public because
    "the factor system is trivial" is a claim a test must be able to falsify:
    an all-zero table is the linear case, and on the zone boundary of a
    non-symmorphic group it must not be.
    """
    _, shifts = little.composition
    n = little.order
    out = np.empty((n, n), dtype=object)
    for i in range(n):
        for j in range(n):
            phase = -sum(kc * ac for kc, ac in zip(little.k, shifts[i][j]))
            out[i, j] = phase - Fraction(math.floor(phase))
    return out


def _phase(exponent: Fraction) -> complex:
    """exp(2πi · exponent), exact for the quarter turns."""
    exact = {Fraction(0): 1 + 0j, Fraction(1, 2): -1 + 0j,
             Fraction(1, 4): 1j, Fraction(3, 4): -1j}
    if exponent in exact:
        return exact[exponent]
    return complex(np.exp(2j * np.pi * float(exponent)))


def factor_system(little: LittleGroup) -> np.ndarray:
    """``(n, n)`` complex factor system ω(i, j) of the little co-group.

    D(g_i) D(g_j) = ω(i, j) D(g_i g_j) for every small irrep.  ω = 1
    identically exactly when the small irreps are ordinary (linear)
    representations of P_k; where it is not, dropping it changes the irrep count
    and the dimensions — Bradley & Cracknell (1972) ch. 4.
    """
    exps = factor_system_exponents(little)
    n = little.order
    out = np.empty((n, n), dtype=np.complex128)
    for i in range(n):
        for j in range(n):
            out[i, j] = _phase(exps[i, j])
    return out


# --------------------------------------------------------------------------
# projective irreps of a finite group
# --------------------------------------------------------------------------

def _twisted_regular(omega: np.ndarray, table: np.ndarray) -> np.ndarray:
    """The ω-twisted regular representation, ``(n, n, n)``.

    Δ(g_i) e_j = ω(i, j) e_{i·j}.  It is unitary (a permutation matrix with
    unit-modulus entries), it satisfies the same factor system, and it contains
    each ω-irrep exactly d_α times — so Σ d_α² = n, the Burnside identity for
    the twisted group algebra.
    """
    n = table.shape[0]
    reg = np.zeros((n, n, n), dtype=np.complex128)
    for i in range(n):
        reg[i, table[i], np.arange(n)] = omega[i]
    return reg


def _split_once(reg: np.ndarray, seed: int) -> list[np.ndarray]:
    """Irreducible invariant subspaces of ``reg``, as matrix stacks, for one seed."""
    n = reg.shape[0]
    rng = np.random.default_rng(seed)
    a = rng.normal(size=(n, n)) + 1j * rng.normal(size=(n, n))
    herm = a + a.conj().T
    averaged = np.einsum("gij,jk,glk->il", reg, herm, reg.conj())
    averaged = (averaged + averaged.conj().T) / 2
    evals, evecs = np.linalg.eigh(averaged)
    spread = float(evals[-1] - evals[0]) if n > 1 else 0.0
    gap = max(1e-7, 1e-6 * spread)
    blocks: list[np.ndarray] = []
    start = 0
    for i in range(1, n + 1):
        if i == n or evals[i] - evals[i - 1] > gap:
            v = evecs[:, start:i]
            blocks.append(np.einsum("ji,gjk,kl->gil", v.conj(), reg, v))
            start = i
    return blocks


def _character_key(chars: np.ndarray) -> tuple:
    """Rounded character, for deduplication and for a deterministic sort order."""
    return tuple((round(float(c.real), 6) + 0.0, round(float(c.imag), 6) + 0.0) for c in chars)


def _projective_irreps(omega: np.ndarray, table: np.ndarray,
                       *, atol: float = IRREP_ATOL) -> list[np.ndarray]:
    """All inequivalent irreducible projective reps with factor system ``omega``.

    Returned as ``(n, d, d)`` complex stacks, one per irrep, sorted by dimension
    then by character.  Verified before return: each is unitary, irreducible
    (Σ|χ|² = n), obeys D(i)D(j) = ω(i,j)D(i·j), and the set satisfies
    Σ d² = n (Burnside for the twisted group algebra).
    """
    n = table.shape[0]
    reg = _twisted_regular(omega, table)
    last_error = "no seed tried"
    for seed in _SEEDS:
        found: dict[tuple, np.ndarray] = {}
        ok = True
        for block in _split_once(reg, seed):
            chars = np.einsum("gii->g", block)
            if abs(float(np.vdot(chars, chars).real) - n) > 1e-4 * n:
                ok = False  # not irreducible: an eigenvalue coincidence merged two subspaces
                last_error = "the commutant average did not separate the irreducible subspaces"
                break
            found.setdefault(_character_key(chars), block)
        if not ok:
            continue
        blocks = list(found.values())
        total = sum(b.shape[1] ** 2 for b in blocks)
        if total != n:
            last_error = f"sum of squared dimensions is {total}, expected {n}"
            continue
        bad = _verification_error(blocks, omega, table, atol=atol)
        if bad is not None:
            last_error = bad
            continue
        blocks.sort(key=lambda b: (b.shape[1], _character_key(np.einsum("gii->g", b))))
        return blocks
    raise RuntimeError(
        "could not split the twisted regular representation into irreps "
        f"({last_error}); this is a bug, not a tolerance to widen"
    )


def _verification_error(blocks, omega, table, *, atol: float) -> str | None:
    """``None`` if every block is a unitary rep with the given factor system."""
    n = table.shape[0]
    for b in blocks:
        d = b.shape[1]
        eye = np.eye(d)
        for i in range(n):
            if not np.allclose(b[i] @ b[i].conj().T, eye, atol=atol):
                return f"a {d}-dimensional block is not unitary at operation {i}"
        prod = np.einsum("iab,jbc->ijac", b, b)
        want = omega[:, :, None, None] * b[table]
        err = float(np.max(np.abs(prod - want)))
        if err > atol:
            return f"a {d}-dimensional block breaks D(i)D(j) = w(i,j)D(ij) by {err:.2e}"
    return None


# --------------------------------------------------------------------------
# small irreps
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class SmallIrrep:
    """One small (allowed) irrep of a little group.

    ``matrices[i]`` is D of the operation ``little.rotations[i]``,
    ``little.translations[i]``; for the same rotation with a lattice translation
    a added, multiply by exp(−2πi k·a).  ``characters`` is its trace.

    ``reality`` is the Frobenius–Schur class of the small irrep D as a
    representation of G_k: ``"real"`` (ν = +1, D is equivalent to a real
    representation), ``"pseudoreal"`` (ν = −1, D ≅ D* but only through an
    antisymmetric intertwiner) or ``"complex"`` (ν = 0, D ≇ D*).  When 2k is not
    a reciprocal lattice vector, D* is a small irrep at −k rather than at k and
    the class is ``"complex"`` for that reason; forming a physically irreducible
    (real) representation then pairs the k and −k arms of the star, which is the
    decomposition rung's job, not this one's.
    """

    label: str
    dimension: int
    matrices: np.ndarray  # (n, d, d) complex
    characters: np.ndarray  # (n,) complex
    reality: str
    frobenius_schur: int
    little: LittleGroup


def _frobenius_schur(matrices: np.ndarray, little: LittleGroup) -> tuple[int, str]:
    """Frobenius–Schur indicator of a small irrep, and its reality class.

    ν = (1/|P_k|) Σ_i tr(D(g_i)²) over the coset representatives.  The summand
    picks up exp(−4πi k·a) when a representative moves by a lattice vector a, so
    the sum is well defined exactly when 2k ≡ 0 — which is also exactly when D*
    is a representation at the same k.  Wigner's three cases (1959, ch. 26);
    Bradley & Cracknell (1972) ch. 7 states them for the space-group setting.
    """
    if not little.has_minus_k:
        return 0, "complex"
    n = little.order
    nu = sum(np.trace(matrices[i] @ matrices[i]) for i in range(n)) / n
    value = int(round(float(nu.real)))
    if abs(nu - value) > 1e-6 or value not in (-1, 0, 1):
        raise RuntimeError(f"Frobenius-Schur indicator is not -1, 0 or 1 but {nu!r}")
    return value, {1: "real", 0: "complex", -1: "pseudoreal"}[value]


def small_irreps_of(little: LittleGroup, *, factor: np.ndarray | None = None
                    ) -> tuple[SmallIrrep, ...]:
    """The small irreps of a little group already built.

    ``factor`` overrides the factor system.  It exists so that a test can ask
    for the ORDINARY (linear) representations of the little co-group by passing
    ``numpy.ones((n, n))`` and assert that they differ from the projective ones
    — on the zone boundary of a non-symmorphic group they must, and a change
    that "simplified" the factor system away would otherwise pass silently.
    Nothing but a test should pass it.
    """
    table = little.multiplication_table
    omega = factor_system(little) if factor is None else np.asarray(factor, dtype=np.complex128)
    if omega.shape != (little.order, little.order):
        raise ValueError(f"factor system must be ({little.order}, {little.order})")
    blocks = _projective_irreps(omega, table)
    out = []
    for idx, block in enumerate(blocks):
        chars = np.einsum("gii->g", block)
        nu, reality = _frobenius_schur(block, little)
        out.append(SmallIrrep(
            label=f"S{idx + 1}",
            dimension=int(block.shape[1]),
            matrices=block,
            characters=chars,
            reality=reality,
            frobenius_schur=nu,
            little=little,
        ))
    return tuple(out)


def small_irreps(space_group, k) -> tuple[SmallIrrep, ...]:
    """The small (allowed) irreps of the little group of ``k``.

    ``k`` is in conventional reciprocal fractional coordinates (module
    docstring, convention 1).  The number of irreps and their dimensions obey
    Σ d² = |G_k / T|; on the zone boundary of a non-symmorphic group the
    factor system is non-trivial and the dimensions are larger than any
    ordinary irrep of the same point group — Bertaut's (1968) two-dimensional
    P n m a irreps at k = (0, 0, 1/2) are the worked case.
    """
    return small_irreps_of(little_group(space_group, k))


def inversion_character(irrep: SmallIrrep) -> complex | None:
    """χ of the operation whose rotation is −1, or ``None`` if G_k holds none.

    A moment is an axial vector, so its behaviour under inversion is the
    argument that decides which irreps can carry it (Bertaut, 1968).  Inversion
    is in G_k only when 2k is a reciprocal lattice vector.
    """
    idx = irrep.little.inversion_index
    return None if idx is None else complex(irrep.characters[idx])


def inversion_parity(irrep: SmallIrrep) -> int | None:
    """+1 if the irrep is even under −1, −1 if odd, ``None`` if neither applies.

    ``None`` means either that G_k contains no inversion, or that D(−1) is not
    ±1 — which happens when the factor system makes −1 non-central in the
    projective sense, and then the irrep has no inversion parity at all rather
    than an unknown one.  Reporting that honestly is the point: the
    axial-vector parity argument does not apply at such a k.
    """
    chi = inversion_character(irrep)
    if chi is None:
        return None
    ratio = chi / irrep.dimension
    if abs(ratio - 1) < 1e-6:
        return 1
    if abs(ratio + 1) < 1e-6:
        return -1
    return None
