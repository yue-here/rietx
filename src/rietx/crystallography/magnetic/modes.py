"""Decomposition of a site orbit's magnetic representation, and its basis vectors.

Representation analysis of a magnetic structure (Bertaut, 1968, *Acta Cryst.*
A**24**, 217) takes a site orbit and a propagation vector k, builds the
magnetic representation

    Γ_mag = Γ_perm ⊗ Γ_axial

of the little group G_k on the 3N moment components of the N orbit atoms in
one primitive cell, decomposes it into the small irreps :mod:`.irreps`
computes, and projects out the basis vectors — the candidate moment
arrangements a refinement varies the amplitudes of.  The same code with
Γ_polar in place of Γ_axial gives the displacive modes, which is the only
difference between a magnetic mode and a displacement mode at this level
(Campbell, Stokes, Tanner & Hatch, 2006, *J. Appl. Cryst.* **39**, 607).

**Public API — fixed 2026-09-06.**

::

    vector_representation(rotations, kind="axial"|"polar") -> (n, 3, 3) float
    crystal_metric(space_group)                            -> (3, 3) float
    orbit_positions(space_group, site_xyz)                 -> (N, 3) float

    permutation_representation(space_group, site_xyz, k)   -> PermutationRepresentation
    magnetic_representation(space_group, site_xyz, k, kind="axial")
                                                           -> SiteRepresentation
    decompose(rep, irreps)                                 -> Decomposition
    basis_vectors(rep, irrep)                              -> IrrepBasis
    mode_table(rep, irreps)                                -> ModeTable

``space_group`` and ``k`` are whatever :mod:`.irreps` accepts, and ``k`` is in
fractional coordinates of the **conventional** reciprocal cell, reduced modulo
the true reciprocal lattice — :mod:`.irreps` convention 1.  ``site_xyz`` is one
fractional position of the site; its orbit comes from
:func:`~rietx.crystallography.symmetry.site_orbit`, which derives the
multiplicity as |G|/|stabiliser| rather than counting coincidences.

Conventions, each of which a caller can get wrong silently:

1. **The orbit is the atoms of one PRIMITIVE cell.**  ``site_orbit`` expands in
   the conventional cell, so on a centred lattice its images come in centring
   families that are one atom repeated by a lattice translation.  Those are
   collapsed here, because a lattice translation is already carried by the
   e^{−2πi k·R} factor and counting it twice would inflate 3N and every
   multiplicity with it.  ``Σ n_ν·d_ν = 3N`` is asserted against the collapsed
   count.

2. **The return-vector phase is exp(−2πi k·a) with a = g·r_j − r_{π(j)}**, the
   lattice vector the image had to be brought back by.  Taking g = {E|a} gives
   D({E|a}) = exp(−2πi k·a)·1, which is :mod:`.irreps` convention 3, so
   Γ_perm ⊗ Γ_vec restricted to gemmi's coset representatives carries *exactly*
   the factor system ω(i, j) = exp(−2πi k·a_ij) that the small irreps were
   built from, with no sign fix-up.  The opposite sign is hard to see and the
   decomposition never sees it: it is *identical* wherever every return phase
   is real — the whole {0,½}³ zone-boundary set of a primitive lattice — and
   where the phases are complex the character inner products come back the
   same anyway, because the character set is closed under conjugation.  What
   sees it is D(i)D(j) = ω(i,j)·D(i·j), which
   :func:`magnetic_representation` checks before returning, and the
   equivariance of the projected vectors, which :func:`basis_vectors` checks.
   Both are measured against a deliberately conjugated representation in
   ``tests/test_magnetic_modes.py``.

3. **The vector action is a REAL-space action: R untransposed.**  Root
   ``CLAUDE.md``'s Rᵀ rule is about *hkl*; a moment sitting at a site is a
   direct-space quantity and transforms with R.  For a polar vector the matrix
   is R itself; for an axial vector (a moment, a rotation) it is det(R)·R
   (Bertaut, 1968).

4. **Moment components are in the conventional crystal-axis basis** — the
   contravariant components of m = m_x·**a** + m_y·**b** + m_z·**c**, which is
   what magCIF stores and what decision D-3 of the magnetic track fixes.  In
   that basis the axial action really is det(R)·R with R the *integer*
   fractional rotation, independent of the cell: writing R_cart = A R A⁻¹ for
   the Cartesian frame whose rows are the cell vectors gives det(R_cart) =
   det(R) and A⁻¹·det(R_cart)R_cart·A = det(R)R.  To move a basis vector to
   Cartesian, multiply by the transpose of the row-vector cell matrix
   (m_cart = Aᵀ·m); :func:`crystal_metric` returns G = A·Aᵀ, the metric that
   makes the fractional action orthogonal.

**Why a metric enters at all.**  The fractional rotation R is an integer matrix
of finite order but is *not* orthogonal — a hexagonal 3-fold is
[[0,−1,0],[1,−1,0],[0,0,1]] — so Γ_mag is a representation by non-unitary
matrices, and "the basis vectors are orthonormal and the isotypic components
are orthogonal" is false in the naive Euclidean product on fractional
components.  It is true in the cell metric, under which every R is orthogonal
(RᵀGR = G).  :func:`crystal_metric` supplies a metric compatible with the
group's *setting* — the Reynolds average ⟨RᵀG₀R⟩ that
:func:`rietx.crystallography.wyckoff._compatible_lattice` already builds for
its spglib probe cell, reused rather than rewritten so the two cannot
disagree.  **The spans of the projectors do not depend on this choice**; only
which orthonormal representatives are drawn from a multi-dimensional space
does, in the same way the copy index is arbitrary.  A caller holding a real
cell can re-orthonormalise with its own metric and gets the same subspaces.

**Algorithm.**  With Γ the representation and D_ν a small irrep, both carrying
the same factor system ω, the projection operator is

    W^ν_{lm} = (d_ν/|P_k|) · Σ_g conj(D_ν(g)_{lm}) · Γ(g)

(Izyumov, Naish & Ozerov, 1991; the two forms and the unitarity they assume are
laid out by Davies & Wills, 2016, arXiv:1610.00472).  The ω factors cancel
between conj(D_ν) and Γ, so the great orthogonality relation applies unchanged
and W^ν_{lm}·ψ^λ_p = δ_{mp}·ψ^λ_l.  W^ν_{11} is therefore the projector onto
the row-1 subspace, whose rank is the multiplicity n_ν; its columns in the
natural order — the trial vectors "atom 1 along a, atom 1 along b, …", which is
what BasIreps and SARAh project — are Gram–Schmidted in the metric to give the
n_ν basis sets, and W^ν_{l1} generates each set's remaining rows.  Taking
exactly n_ν trial vectors is what stops the *over-generation* Davies & Wills
(2016) describe: three trial vectors at one atom project to at most n_ν
independent row-1 vectors, and the surplus are linear combinations.

**Real where possible.**  Γ_mag is a real matrix exactly when every return
phase is real, i.e. when 2k is a reciprocal lattice vector (``little.has_minus_k``).
There, an irrep with Frobenius–Schur indicator +1 is equivalent to a real
representation, and this module finds the unitary C with C†D(g)C real (Autonne–
Takagi factorisation of the symmetric unitary intertwiner between D and D*) and
projects with that gauge, so the basis vectors come out real.  The three cases
that stay complex are named in :class:`IrrepBasis.reality` and each says what
pairing makes a real moment arrangement:

* 2k ≢ 0 — D* is a small irrep at −k, not at k.  The physically irreducible
  representation is D_k ⊕ D*_{−k} and the moment is
  m_j(R) = Σ C·ψ_j·e^{−2πi k·R} + c.c., with 2·n_ν·d_ν free real amplitudes.
* 2k ≡ 0 with FS = 0 — D* is an inequivalent small irrep at the *same* k; the
  physically irreducible representation is D ⊕ D*, same amplitude count.
* 2k ≡ 0 with FS = −1 (pseudoreal) — D ≅ D* but only through an antisymmetric
  intertwiner, so no real gauge exists and the real form is D ⊕ D.

The conjugate partner carries no information the returned vectors do not, which
is why it is described rather than duplicated into the returned array.

**What is deterministic and what is not.**  The orbit order, the multiplicities
and the number of basis sets are deterministic.  The vectors within one irrep
are canonical only up to the intertwiner freedom :mod:`.irreps` already
documents, plus the choice of metric and the arbitrary ordering of degenerate
basis sets: *compare spans and characters, never components*.  What is asserted
before anything is returned is the equivariance relation
Γ(g)·ψ^λ_l = Σ_m D_ν(g)_{ml}·ψ^λ_m, orthonormality in the metric, and
Σ n_ν·d_ν = 3N.

References
----------
Bertaut, E. F. (1968). *Acta Cryst.* A**24**, 217 — Γ_mag = Γ_perm ⊗ Γ_axial,
the decomposition by characters, the basis vectors by projection, and the
F/G/C/A modes of a four-atom orbit.
Izyumov, Yu. A., Naish, V. E. & Ozerov, R. P. (1991). *Neutron Diffraction of
Magnetic Materials*. New York: Consultants Bureau — projection operators for
every row of a multi-dimensional irrep, the return-translation phase, and the
physically irreducible combinations of complex-conjugate irreps.
Wills, A. S. (2000). *Physica B* **276–278**, 680 — SARAh: basis vectors as the
refinable coordinates of a magnetic structure.
Davies, Z. & Wills, A. S. (2016). *arXiv*:1610.00472 (preprint) — over- and
under-generation of basis vectors, and the basis-set view of the projector's
row and column indices.
Bradley, C. J. & Cracknell, A. P. (1972). *The Mathematical Theory of Symmetry
in Solids*. Oxford: Clarendon — the projective case and the reality classes.
Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006). *J. Appl.
Cryst.* **39**, 607 — the mode-amplitude view of a distorted structure, which
is the displacive twin of the magnetic decomposition here.
Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55 — BasIreps and the
FullProf convention m_j(R) = Σ_k S_kj·exp(−2πi k·R) these vectors are the S_kj
of.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from fractions import Fraction

import numpy as np

from ..symmetry import site_orbit
from ..wyckoff import _compatible_lattice
from .irreps import (
    KVector,
    LittleGroup,
    SmallIrrep,
    _centrings,
    _resolve,
    as_kvector,
    factor_system,
    little_group,
)

#: Tolerance on the projected quantities.  The projectors are group averages of
#: matrices whose entries are roots of unity times small integers, and the
#: orthonormalisation is a Gram–Schmidt in a well-conditioned metric, so the
#: measured worst residual over the 230-group sweep is far below this (quoted
#: in ``tests/test_magnetic_modes.py``).  Used for the equivariance identity,
#: orthonormality, the integrality of a multiplicity and the realness test.
MODE_ATOL = 1e-9

#: How far an orbit image may sit from the lattice translate of another before
#: the two are refused as unmatched.  ``site_orbit`` returns positions already
#: snapped onto their special position, and the arithmetic here is one matrix
#: product away from them, so the true residual is at roundoff; this is six
#: orders of slack on that and still far tighter than any site separation.
POSITION_ATOL = 1e-6

#: The vector representations this module knows.  ``"axial"`` is a magnetic
#: moment (Γ_mag); ``"polar"`` is a displacement (Γ_disp).  Naming them by the
#: physics rather than by a letter is the house rule — codes disagree on
#: letters, and "Γ_V" means the polar one in some papers and either in others.
VECTOR_KINDS = ("axial", "polar")


# --------------------------------------------------------------------------
# the vector representation, and the metric that makes it orthogonal
# --------------------------------------------------------------------------

def vector_representation(rotations, kind: str = "axial") -> np.ndarray:
    """The 3×3 matrices by which a vector property transforms, one per rotation.

    ``rotations`` is an ``(n, 3, 3)`` stack of **fractional** rotation parts —
    ``LittleGroup.rotations``, or any integer rotations in the conventional
    crystal-axis basis.  ``kind="polar"`` returns R itself (a displacement);
    ``kind="axial"`` returns det(R)·R (a magnetic moment, or any pseudovector),
    because a pseudovector picks up the determinant under an improper operation
    — Bertaut (1968).

    This is a **real-space** action, so R is untransposed.  Root ``CLAUDE.md``'s
    "reciprocal-space symmetry action is Rᵀ" governs *hkl* and does not apply
    here; the transposed set is a group too, so a degrees-of-freedom count is
    identical either way and only the identity of the invariant directions
    differs.

    The matrices act on the **contravariant components in the conventional
    crystal-axis basis** — m = m_x·**a** + m_y·**b** + m_z·**c**, the magCIF
    ``_atom_site_moment_crystalaxis_*`` convention and this package's stored
    form.  The same expression serves every cell: with A the row-vector cell
    matrix, R_cart = A·R·A⁻¹ has the same determinant as R and
    A⁻¹·(det(R_cart)·R_cart)·A = det(R)·R.  To read a component triple in
    Cartesian axes, take Aᵀ·m.

    The returned matrices are generally **not orthogonal** — a fractional
    3-fold in a hexagonal setting is not — so the natural inner product on
    moment space is the cell metric's, not the Euclidean one on the components.
    :func:`crystal_metric` is that metric.

    ``rietx.crystallography.magnetic`` M-5 builds the same axial action for
    magnetic operators, where it is composed with time reversal; the two are
    the same three lines and are meant to be pointed at one another when the
    branches meet.
    """
    if kind not in VECTOR_KINDS:
        raise ValueError(f"kind must be one of {VECTOR_KINDS}, got {kind!r}")
    rots = np.asarray(rotations, dtype=np.float64)
    if rots.ndim != 3 or rots.shape[1:] != (3, 3):
        raise ValueError("rotations must have shape (n, 3, 3)")
    if kind == "polar":
        return rots.copy()
    dets = np.linalg.det(rots)
    return dets[:, None, None] * rots


def crystal_metric(space_group) -> np.ndarray:
    """A cell metric G compatible with the group's setting: RᵀGR = G for every R.

    The Reynolds average ⟨RᵀG₀R⟩ of a generic positive-definite metric, which
    is positive definite because a congruence of a positive-definite matrix is,
    and which follows whatever setting the operators are written in — hexagonal
    axes, rhombohedral axes, a non-standard monoclinic unique axis — with no
    per-system table.  Read off
    :func:`rietx.crystallography.wyckoff._compatible_lattice`, the same average
    that module builds for its spglib probe cell, so the two cannot drift
    apart.

    It is a **choice**, not a measurement: a real cell has its own metric, and
    any of them makes the fractional rotations orthogonal.  Nothing this module
    returns *spans* depends on which one — the projectors are built from Γ
    alone — but which orthonormal vectors are drawn out of a degenerate
    subspace does, exactly as the copy index does.
    """
    lattice = _compatible_lattice(_resolve(space_group))
    return lattice @ lattice.T


# --------------------------------------------------------------------------
# the orbit, collapsed onto one primitive cell
# --------------------------------------------------------------------------

def _is_lattice_vector(delta: np.ndarray, centrings: tuple[KVector, ...]) -> bool:
    """True when ``delta`` is a vector of the group's lattice.

    That lattice is the integer triples plus the centring translations, which
    is what makes two conventional-cell orbit images "the same atom of the
    primitive cell" — the question :func:`orbit_positions` asks.
    """
    for cen in centrings:
        shifted = delta - np.array([float(c) for c in cen])
        if np.all(np.abs(shifted - np.rint(shifted)) < POSITION_ATOL):
            return True
    return False


def orbit_positions(space_group, site_xyz) -> np.ndarray:
    """The site's orbit as the atoms of ONE PRIMITIVE cell, ``(N, 3)``.

    :func:`~rietx.crystallography.symmetry.site_orbit` expands in the
    conventional cell, where a centred lattice repeats every atom once per
    centring vector.  Those repeats are the *same* atom seen through a lattice
    translation — the phase factor e^{−2πi k·R} already carries them — so they
    are collapsed here and the returned count is the conventional multiplicity
    divided by the number of centring vectors.  A lattice translation cannot
    fix a point, so the division is exact; it is asserted rather than assumed.

    Positions are conventional fractional coordinates wrapped into [0, 1), in
    ``site_orbit``'s own order, and that order is what every basis vector's
    component triples are indexed by.  Carry it with the vectors: the F/G/C/A
    mode names of a four-atom orbit are meaningless without it (Bertaut, 1968).
    """
    sg = _resolve(space_group)
    orbit = site_orbit(sg, np.asarray(site_xyz, dtype=np.float64))
    centrings = _centrings(sg)
    kept: list[np.ndarray] = []
    for image in orbit.images:
        if not any(_is_lattice_vector(image - other, centrings) for other in kept):
            kept.append(image)
    if len(kept) * len(centrings) != orbit.multiplicity:
        raise ValueError(
            f"ORBIT_NOT_A_PRIMITIVE_CELL: site {np.array2string(np.asarray(site_xyz), precision=6)} "
            f"in {sg.xhm()!r} has conventional multiplicity {orbit.multiplicity} but collapses to "
            f"{len(kept)} atoms against {len(centrings)} centring vectors. A centring translation "
            "cannot fix a point, so the orbit must split into equal families; it did not, which "
            "means the positions are not consistent with this setting's lattice"
        )
    return np.array(kept, dtype=np.float64).reshape(len(kept), 3)


# --------------------------------------------------------------------------
# the permutation representation
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class PermutationRepresentation:
    """Γ_perm of a site orbit under the little group of k.

    ``matrices[g][i, j]`` is exp(−2πi k·a) when operation ``g`` sends orbit
    atom ``j`` to atom ``i`` and zero otherwise, with a = g·r_j − r_i the
    lattice vector the image was brought back by.  ``permutations[g, j] = i``
    and ``phases[g, j]`` are the same content unpacked, which is what a caller
    building a structure factor wants rather than an N×N matrix that is one
    non-zero per column.

    ``little.rotations[g]``/``little.translations[g]`` is the operation each
    index belongs to — the same coset representatives ``SmallIrrep.matrices``
    uses, which is what lets the two be multiplied together without a gauge
    fix-up (:mod:`.irreps` convention 4).
    """

    little: LittleGroup
    positions: np.ndarray  # (N, 3) conventional fractional, one primitive cell
    permutations: np.ndarray  # (n, N) int64
    phases: np.ndarray  # (n, N) complex
    matrices: np.ndarray  # (n, N, N) complex
    lattice_shifts: np.ndarray  # (n, N, 3) int64 numerators of a = g·r_j − r_{π(j)}
    shift_denominator: int  # a = lattice_shifts / shift_denominator, exactly
    spacegroup: str | None = None

    def shift(self, g: int, atom: int) -> KVector:
        """The exact lattice vector a = g·r_atom − r_{π(atom)}, as ``Fraction``s.

        Kept as integer numerators over one denominator rather than as objects
        because the phase it feeds is built from them by integer arithmetic —
        a float here would put a rounding error inside exp(−2πi k·a), which is
        the one place in this module where roundoff would be indistinguishable
        from the wrong convention.
        """
        return tuple(  # type: ignore[return-value]
            Fraction(int(n), self.shift_denominator) for n in self.lattice_shifts[g, atom]
        )

    @property
    def n_atoms(self) -> int:
        """N, the orbit atoms in one primitive cell."""
        return int(self.positions.shape[0])

    @property
    def characters(self) -> np.ndarray:
        """χ_perm(g) — the phase sum over the atoms the operation leaves in place."""
        return np.einsum("gii->g", self.matrices)

    @property
    def orbits(self) -> tuple[tuple[int, ...], ...]:
        """The atom indices grouped into orbits **of the little group**.

        G_k need not act transitively on a crystallographic orbit: at
        k = (½,½,½) in I 4₁ 32 the sixteen-fold site's eight primitive-cell
        atoms fall into two G_k orbits of four, and a published basis-vector
        table is written for one of them (Davies & Wills, 2016).  The
        representation is block diagonal over these, which is what
        :meth:`SiteRepresentation.restrict` uses.
        """
        n_atoms = self.n_atoms
        label = [-1] * n_atoms
        groups: list[list[int]] = []
        for start in range(n_atoms):
            if label[start] >= 0:
                continue
            members = [start]
            label[start] = len(groups)
            stack = [start]
            while stack:
                j = stack.pop()
                for g in range(self.little.order):
                    i = int(self.permutations[g, j])
                    if label[i] < 0:
                        label[i] = label[start]
                        members.append(i)
                        stack.append(i)
            groups.append(sorted(members))
        return tuple(tuple(m) for m in groups)


def permutation_representation(space_group, site_xyz, k) -> PermutationRepresentation:
    """Γ_perm: how the little group of ``k`` permutes a site orbit, with phases.

    For each operation g = (R, v) of G_k and each orbit atom r_j, the image
    R·r_j + v is another orbit atom r_{π(j)} plus a lattice vector
    a = R·r_j + v − r_{π(j)}, and the matrix entry is exp(−2πi k·a) — the
    return-vector phase (Izyumov, Naish & Ozerov, 1991; Bertaut, 1968).

    That sign is the whole risk in this function.  Setting g = {E|a} makes the
    entry exp(−2πi k·a), which is :mod:`.irreps`'s D({E|a}) = exp(−2πi k·a), so
    the two carry the *same* factor system and multiply without a fix-up.  The
    opposite sign is a representation too — of the *conjugate* factor system —
    and it decomposes into the same multiplicities, measured, at every k tried,
    which is why :func:`magnetic_representation` checks the factor system
    explicitly instead of inferring it from a decomposition that closes.

    The orbit is the primitive-cell one (:func:`orbit_positions`), and the
    operations are gemmi's coset representatives in
    :class:`~.irreps.LittleGroup` order.
    """
    sg = _resolve(space_group)
    little = little_group(sg, k)
    kk = as_kvector(k)
    centrings = _centrings(sg)
    positions = orbit_positions(sg, site_xyz)
    n_ops, n_atoms = little.order, int(positions.shape[0])

    # Everything that reaches the phase is integer arithmetic over one common
    # denominator: k = k_num/k_den, a = shift_num/shift_den, and the exponent
    # −k·a is an integer over k_den·shift_den.  A float dot product here would
    # put roundoff inside exp(−2πi k·a), where it is indistinguishable from the
    # wrong sign convention that this module's whole verification is about.
    k_den = math.lcm(*(c.denominator for c in kk))
    k_num = np.array([int(c * k_den) for c in kk], dtype=np.int64)
    shift_den = math.lcm(*(c.denominator for cen in centrings for c in cen))
    centring_num = np.array(
        [[int(c * shift_den) for c in cen] for cen in centrings], dtype=np.int64)
    centring_f = centring_num.astype(np.float64) / shift_den

    permutations = np.full((n_ops, n_atoms), -1, dtype=np.int64)
    shift_num = np.zeros((n_ops, n_atoms, 3), dtype=np.int64)
    for g in range(n_ops):
        rot = little.rotations[g].astype(np.float64)
        tran = np.array([float(t) for t in little.translations[g]])
        images = positions @ rot.T + tran                       # (N, 3)
        for c, cen in enumerate(centring_f):
            delta = images[None, :, :] - positions[:, None, :] - cen  # (i, j, 3)
            whole = np.rint(delta)
            hit = np.all(np.abs(delta - whole) < POSITION_ATOL, axis=2)
            rows, cols = np.nonzero(hit)
            if np.any(permutations[g, cols] >= 0):
                raise ValueError(
                    f"ORBIT_NOT_DISTINCT: two orbit atoms of {sg.xhm()!r} differ by a lattice "
                    "vector, so they are one atom of the primitive cell counted twice"
                )
            permutations[g, cols] = rows
            shift_num[g, cols] = (whole[rows, cols].astype(np.int64) * shift_den
                                  + centring_num[c])
        if np.any(permutations[g] < 0):
            missing = int(np.flatnonzero(permutations[g] < 0)[0])
            raise ValueError(
                f"ORBIT_NOT_CLOSED: operation {little.triplets[g]!r} of the little group of "
                f"k = {tuple(str(c) for c in kk)} sends orbit atom {missing} of "
                f"{sg.xhm()!r} off the orbit. A space-group operation maps a crystallographic "
                "orbit onto itself, so this is a coordinate/setting mismatch, not a tolerance"
            )
    denominator = k_den * shift_den
    exponents = (-(shift_num @ k_num)) % denominator            # (n, N) integer
    phases = _phases(exponents, denominator)
    matrices = np.zeros((n_ops, n_atoms, n_atoms), dtype=np.complex128)
    columns = np.arange(n_atoms)
    for g in range(n_ops):
        matrices[g, permutations[g], columns] = phases[g]
    return PermutationRepresentation(
        little=little,
        positions=positions,
        permutations=permutations,
        phases=phases,
        matrices=matrices,
        lattice_shifts=shift_num,
        shift_denominator=shift_den,
        spacegroup=sg.xhm(),
    )


def _phases(numerators: np.ndarray, denominator: int) -> np.ndarray:
    """exp(2πi·n/d) elementwise, exact where the quarter turns make it so.

    Every zone-boundary k — the whole set where the factor system is
    projective — gives n/d in {0, ¼, ½, ¾}, and those four are written down
    rather than evaluated so that a phase which must be ±1 or ±i is, bit for
    bit.  Everything else goes through ``exp``.
    """
    out = np.exp(2j * np.pi * numerators / denominator)
    for turn, value in ((Fraction(0), 1 + 0j), (Fraction(1, 4), 1j),
                        (Fraction(1, 2), -1 + 0j), (Fraction(3, 4), -1j)):
        scaled = turn * denominator
        if scaled.denominator == 1:
            out[numerators == int(scaled)] = value
    return out


def _phase(exponent: Fraction) -> complex:
    """exp(2πi·exponent), exact for the quarter turns (the zone-boundary set)."""
    exact = {Fraction(0): 1 + 0j, Fraction(1, 2): -1 + 0j,
             Fraction(1, 4): 1j, Fraction(3, 4): -1j}
    if exponent in exact:
        return exact[exponent]
    return complex(np.exp(2j * np.pi * float(exponent)))


# --------------------------------------------------------------------------
# the magnetic (or displacive) representation
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class SiteRepresentation:
    """Γ_perm ⊗ Γ_vec of a site orbit, the 3N-dimensional object to decompose.

    Components are ordered atom-major: index 3·j + c is component c of atom j,
    so ``matrices[g].reshape(N, 3, N, 3)`` and a basis vector's
    ``reshape(N, 3)`` both mean what they look like.  ``positions[j]`` is the
    atom each triple belongs to, and it travels with every result because a
    mode name (F, G, C, A …) is a statement about an atom ordering.
    """

    little: LittleGroup
    kind: str
    permutation: PermutationRepresentation
    vector: np.ndarray  # (n, 3, 3) float
    matrices: np.ndarray  # (n, 3N, 3N) complex
    metric: np.ndarray  # (3, 3) float
    spacegroup: str | None = None

    @property
    def positions(self) -> np.ndarray:
        """``(N, 3)`` conventional fractional positions of the orbit atoms."""
        return self.permutation.positions

    @property
    def n_atoms(self) -> int:
        return self.permutation.n_atoms

    @property
    def dimension(self) -> int:
        """3N."""
        return int(self.matrices.shape[1])

    @property
    def characters(self) -> np.ndarray:
        """χ(g) = χ_perm(g)·χ_vec(g), the only part the decomposition needs."""
        return np.einsum("gii->g", self.matrices)

    @property
    def orbits(self) -> tuple[tuple[int, ...], ...]:
        """Atom indices grouped into little-group orbits; see the peer property."""
        return self.permutation.orbits

    @property
    def inner_product(self) -> np.ndarray:
        """``(3N, 3N)`` real S with ⟨u, v⟩ = u†·S·v — the cell metric per atom.

        Γ is unitary in this product and in no other natural one, which is what
        makes "the isotypic components are orthogonal" a true statement rather
        than an approximation that happens to hold for orthorhombic cells.
        """
        return np.kron(np.eye(self.n_atoms), self.metric)

    def restrict(self, atoms) -> "SiteRepresentation":
        """The sub-representation carried by a subset of the orbit atoms.

        ``atoms`` must be closed under the little group — one of
        :attr:`orbits`, normally — because the representation is block diagonal
        over those and over nothing finer.  Use it to compare against a
        published table written for a single G_k orbit.
        """
        keep = tuple(sorted({int(a) for a in atoms}))
        chosen = set(keep)
        if not chosen or any(chosen & set(o) not in (set(), set(o)) for o in self.orbits):
            raise ValueError(
                "restrict() needs a non-empty set of atoms closed under the little group — a "
                f"union of SiteRepresentation.orbits, which are {self.orbits}. The "
                "representation is block diagonal over those and a finer split is not a "
                "representation at all"
            )
        perm_index = {a: i for i, a in enumerate(keep)}
        n_ops = self.little.order
        sub_perm = np.array(
            [[perm_index[int(self.permutation.permutations[g, j])] for j in keep]
             for g in range(n_ops)], dtype=np.int64)
        sub_phase = self.permutation.phases[:, keep]
        n_atoms = len(keep)
        sub_mat = np.zeros((n_ops, n_atoms, n_atoms), dtype=np.complex128)
        for g in range(n_ops):
            sub_mat[g, sub_perm[g], np.arange(n_atoms)] = sub_phase[g]
        sub = PermutationRepresentation(
            little=self.little,
            positions=self.positions[list(keep)],
            permutations=sub_perm,
            phases=sub_phase,
            matrices=sub_mat,
            lattice_shifts=self.permutation.lattice_shifts[:, keep, :],
            shift_denominator=self.permutation.shift_denominator,
            spacegroup=self.spacegroup,
        )
        return SiteRepresentation(
            little=self.little,
            kind=self.kind,
            permutation=sub,
            vector=self.vector,
            matrices=np.array([np.kron(sub_mat[g], self.vector[g]) for g in range(n_ops)]),
            metric=self.metric,
            spacegroup=self.spacegroup,
        )


def magnetic_representation(space_group, site_xyz, k, kind: str = "axial"
                            ) -> SiteRepresentation:
    """Γ_perm ⊗ Γ_vec of a site orbit under the little group of ``k``.

    ``kind="axial"`` gives the magnetic representation Γ_mag of Bertaut (1968);
    ``kind="polar"`` gives the displacive one, which is the same construction
    with R in place of det(R)·R and is what a symmetry-mode refinement of a
    nuclear distortion decomposes (Campbell et al., 2006).

    The result is verified before it is returned: the matrices must satisfy
    D(i)·D(j) = ω(i, j)·D(i·j) with ω the *irreps module's* factor system, to
    :data:`MODE_ATOL`.  That identity, and the equivariance
    :func:`basis_vectors` checks, are the only two things that tell a correct
    return-vector phase from a conjugated one — the decomposition cannot, and
    the check is cheap (:func:`_factor_system_residual` works on the tensor
    factors, not on the 3N × 3N product).
    """
    if kind not in VECTOR_KINDS:
        raise ValueError(f"kind must be one of {VECTOR_KINDS}, got {kind!r}")
    sg = _resolve(space_group)
    perm = permutation_representation(sg, site_xyz, k)
    vector = vector_representation(perm.little.rotations, kind)
    matrices = np.array(
        [np.kron(perm.matrices[g], vector[g]) for g in range(perm.little.order)],
        dtype=np.complex128,
    )
    rep = SiteRepresentation(
        little=perm.little,
        kind=kind,
        permutation=perm,
        vector=vector,
        matrices=matrices,
        metric=crystal_metric(sg),
        spacegroup=sg.xhm(),
    )
    residual = _factor_system_residual(rep)
    if residual > MODE_ATOL:
        raise RuntimeError(
            f"the {kind} representation of {sg.xhm()!r} at k = "
            f"{tuple(str(c) for c in perm.little.k)} breaks D(i)D(j) = w(i,j)D(ij) by "
            f"{residual:.2e}. The return-vector phase or the translation convention "
            "disagrees with the small irreps' D({E|a}) = exp(-2*pi*i*k.a); this is a bug, "
            "not a tolerance to widen"
        )
    return rep


def _factor_system_residual(rep: SiteRepresentation) -> float:
    """Worst violation of D(i)D(j) = ω(i,j)·D(i·j) over the little co-group.

    Checked on the two tensor factors separately, and not on the 3N × 3N
    product, because the 3N form costs |P_k|²·(3N)³ — 7·10⁹ complex multiplies
    for a cubic general position — while the factors cost |P_k|²·N and
    |P_k|²·27, and the identity for a tensor product follows from the identity
    for its factors.  The permutation factor is checked in its *unpacked* form,
    which is also the sharper statement: the composed permutation must be the
    permutation of the composed operation, and the phases must multiply to
    ω(i, j) times the composed phase — a matrix product would hide a
    compensating pair of errors that a phase comparison cannot.
    """
    omega = factor_system(rep.little)
    table = rep.little.multiplication_table
    permutations = rep.permutation.permutations
    phases = rep.permutation.phases

    composed = np.take(permutations, permutations, axis=1)      # [i, j, m] = π_i(π_j(m))
    if not np.array_equal(composed, permutations[table]):
        return float("inf")
    left = np.take(phases, permutations, axis=1) * phases[None, :, :]
    right = omega[:, :, None] * phases[table]
    permutation_error = float(np.max(np.abs(left - right)))

    vector = rep.vector
    vector_error = float(np.max(np.abs(
        np.einsum("iab,jbc->ijac", vector, vector) - vector[table])))
    return max(permutation_error, vector_error)


# --------------------------------------------------------------------------
# the decomposition
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class Decomposition:
    """Γ = Σ_ν n_ν·Γ^ν — the multiplicities, and the check that they close."""

    representation: SiteRepresentation
    irreps: tuple[SmallIrrep, ...]
    multiplicities: tuple[int, ...]
    residual: float  # worst |n_ν − round(n_ν)|

    @property
    def total(self) -> int:
        """Σ n_ν·d_ν, which must be 3N."""
        return sum(n * ir.dimension for n, ir in zip(self.multiplicities, self.irreps))

    @property
    def active(self) -> tuple[tuple[SmallIrrep, int], ...]:
        """The (irrep, multiplicity) pairs with n_ν > 0, in irrep order."""
        return tuple((ir, n) for ir, n in zip(self.irreps, self.multiplicities) if n)

    def __str__(self) -> str:
        parts = [f"{n}*{ir.label}" if n != 1 else ir.label for ir, n in self.active]
        k = ", ".join(str(c) for c in self.representation.little.k)
        return (f"Gamma_{self.representation.kind} = " + " + ".join(parts)
                + f"   [{self.representation.spacegroup}, k = ({k}), "
                  f"{self.representation.n_atoms} atoms, dim {self.total}]")


def decompose(rep: SiteRepresentation, irreps) -> Decomposition:
    """Multiplicities of the small irreps in a site representation.

    n_ν = (1/|P_k|)·Σ_g conj(χ_ν(g))·χ(g), the character inner product over the
    little co-group.  Both characters carry the same factor system ω, so the ω
    cancels in the product and the ordinary orthogonality relation applies
    unchanged (Bradley & Cracknell, 1972, ch. 4); the sum is over the *coset
    representatives*, one per element of P_k, which is what makes it finite.

    Two things are refused loudly rather than rounded away, because both are
    wrong-convention detectors and neither is a tolerance question:

    * a multiplicity that is not a non-negative integer — the characters do not
      belong to this representation's little group, or the factor systems
      differ;
    * Σ n_ν·d_ν ≠ 3N — the irrep set is incomplete, or the orbit was counted in
      the conventional cell rather than the primitive one.

    Note that Σ n_ν·d_ν = 3N holds for the polar action as well as the axial
    one: dropping det(R) gives a different but equally valid representation of
    the same group, so this check does **not** catch a missing determinant.
    What catches that is comparing the decomposition itself — at a site with
    inversion the axial modes are the even irreps and the polar ones the odd.
    """
    irreps = tuple(irreps)
    if not irreps:
        raise ValueError("decompose() needs at least one small irrep")
    for ir in irreps:
        _check_same_little_group(rep, ir)
    chi = rep.characters
    order = rep.little.order
    raw = np.array([np.vdot(ir.characters, chi) / order for ir in irreps])
    rounded = np.rint(raw.real).astype(int)
    residual = float(np.max(np.abs(raw - rounded))) if len(raw) else 0.0
    if residual > MODE_ATOL or np.any(rounded < 0):
        bad = ", ".join(f"{ir.label}: {complex(v):.6g}" for ir, v in zip(irreps, raw))
        raise RuntimeError(
            f"the multiplicities of {rep.spacegroup!r} at k = "
            f"{tuple(str(c) for c in rep.little.k)} are not non-negative integers ({bad}). "
            "A multiplicity is a count of subspaces; a non-integer means the irreps and the "
            "representation do not share a factor system or a little group. This is a bug, "
            "not a tolerance to widen"
        )
    total = int(sum(int(n) * ir.dimension for n, ir in zip(rounded, irreps)))
    if total != rep.dimension:
        raise RuntimeError(
            f"sum of n*dim is {total} but the {rep.kind} representation of {rep.spacegroup!r} "
            f"at k = {tuple(str(c) for c in rep.little.k)} has dimension {rep.dimension} "
            f"({rep.n_atoms} atoms x 3). The irrep set is incomplete, or the orbit was taken "
            "in the conventional cell instead of one primitive cell. This is a bug, not a "
            "tolerance to widen"
        )
    return Decomposition(
        representation=rep,
        irreps=irreps,
        multiplicities=tuple(int(n) for n in rounded),
        residual=residual,
    )


def _check_same_little_group(rep: SiteRepresentation, irrep: SmallIrrep) -> None:
    """Refuse an irrep of a different k, group or coset gauge."""
    mine, theirs = rep.little, irrep.little
    if mine is theirs:
        return
    if (mine.k != theirs.k or mine.order != theirs.order
            or not np.array_equal(mine.rotations, theirs.rotations)
            or mine.translations != theirs.translations):
        raise ValueError(
            f"irrep {irrep.label!r} belongs to the little group of k = "
            f"{tuple(str(c) for c in theirs.k)} in {theirs.spacegroup!r}, and the "
            f"representation to k = {tuple(str(c) for c in mine.k)} in {mine.spacegroup!r}. "
            "A small irrep's matrices are attached to particular coset representatives, so "
            "the two lists must be the same operations in the same order"
        )


# --------------------------------------------------------------------------
# projection onto basis vectors
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class IrrepBasis:
    """The basis vectors projected out of one irrep, grouped into basis sets.

    ``vectors[j, i]`` is the basis vector ψ^ν_{i+1, j+1} of SARAh's notation
    (Wills, 2000; Davies & Wills, 2016): **j indexes the basis set** — the copy
    of the irrep, 1…n_ν — and **i the row within it**, 1…d_ν.  Varying the row
    moves within one basis set, along the irrep matrices; varying the basis set
    moves between independent copies.  Each vector is stored as ``(N, 3)``
    moment component triples, one per orbit atom, in :attr:`positions` order
    and in the conventional crystal-axis basis.

    ``irrep_matrices`` are the matrices these vectors actually transform by —
    equal to the small irrep's, except where a real gauge was found and applied
    (see :attr:`reality`).  The equivariance relation they satisfy, verified to
    :data:`MODE_ATOL` before this object exists, is

        Γ(g)·ψ_{i,j} = Σ_m irrep_matrices[g][m, i]·ψ_{m,j}.
    """

    representation: SiteRepresentation
    irrep: SmallIrrep
    multiplicity: int
    vectors: np.ndarray  # (n_v, d_v, N, 3) complex — [basis set, row, atom, component]
    irrep_matrices: np.ndarray  # (n, d, d) complex — the gauge the vectors use
    real: bool
    reality: str
    pairing: str
    equivariance_residual: float
    orthonormality_residual: float

    @property
    def positions(self) -> np.ndarray:
        """``(N, 3)`` orbit positions the component triples belong to."""
        return self.representation.positions

    @property
    def free_real_amplitudes(self) -> int:
        """Real amplitudes a refinement varies for this irrep.

        n_ν·d_ν when the basis vectors are real, twice that when the physical
        moment needs a complex amplitude and its conjugate partner — the
        distinction :attr:`pairing` spells out.
        """
        count = self.multiplicity * self.irrep.dimension
        return count if self.real else 2 * count

    def labels(self) -> tuple[tuple[int, int, str], ...]:
        """``(basis_set, row, label)`` for every vector, in storage order."""
        return tuple(
            (j + 1, i + 1, f"psi^{self.irrep.label}_{i + 1}{j + 1}")
            for j in range(self.multiplicity)
            for i in range(self.irrep.dimension)
        )


def basis_vectors(rep: SiteRepresentation, irrep: SmallIrrep) -> IrrepBasis:
    """Project the basis vectors of one small irrep out of a site representation.

    The projector is W^ν_{lm} = (d_ν/|P_k|)·Σ_g conj(D_ν(g)_{lm})·Γ(g)
    (Izyumov, Naish & Ozerov, 1991, § on projection operators; Davies & Wills,
    2016, eq. 6).  W^ν_{11} projects onto the row-1 subspace, whose rank is the
    multiplicity n_ν; its columns are the trial vectors "atom 1 along **a**",
    "atom 1 along **b**", … in orbit order, which is the trial set BasIreps and
    SARAh use, and they are Gram–Schmidted **in the cell metric** until n_ν
    independent ones are found.  Taking exactly n_ν of them is what avoids the
    over-generation Davies & Wills (2016) describe: three trial vectors at one
    atom project into a space of dimension n_ν, and any surplus is a linear
    combination nobody can see by inspection.  W^ν_{l1} then fills in the rest
    of each basis set.

    Where the representation is real (2k a reciprocal lattice vector) and the
    irrep has Frobenius–Schur indicator +1, the irrep is first moved to a real
    gauge, so the returned vectors are real; the three cases where that is
    impossible are named in the result's ``reality`` and ``pairing``.  Returns
    a basis with ``multiplicity == 0`` and an empty ``vectors`` array when the
    irrep does not occur.

    Everything is verified before it is returned — the equivariance relation,
    orthonormality in the metric, and the rank — because a projector built from
    a mismatched gauge produces a plausible-looking set of vectors that
    transform by nothing.
    """
    _check_same_little_group(rep, irrep)
    order = rep.little.order
    dim = rep.dimension
    d = irrep.dimension
    chi = rep.characters
    raw = np.vdot(irrep.characters, chi) / order
    multiplicity = int(round(float(raw.real)))
    if abs(raw - multiplicity) > MODE_ATOL or multiplicity < 0:
        raise RuntimeError(
            f"multiplicity of {irrep.label!r} is {complex(raw):.6g}, not a non-negative "
            "integer; see decompose() for what that means. This is a bug, not a tolerance"
        )

    matrices, real_gauge = _maybe_real_gauge(rep, irrep)
    reality, pairing = _reality_and_pairing(rep, irrep, real_gauge)
    if multiplicity == 0:
        return IrrepBasis(
            representation=rep, irrep=irrep, multiplicity=0,
            vectors=np.zeros((0, d, rep.n_atoms, 3), dtype=np.complex128),
            irrep_matrices=matrices, real=True, reality=reality, pairing=pairing,
            equivariance_residual=0.0, orthonormality_residual=0.0,
        )

    projectors = np.einsum("gm,gab->mab", np.conj(matrices[:, :, 0]), rep.matrices) * (d / order)

    # ⟨u, v⟩ = u†·(I ⊗ metric)·v = (W·u)†(W·v) with W = I ⊗ cholᵀ, so the
    # Gram–Schmidt below is an ordinary one in W coordinates.  Both W and its
    # inverse are built from the 3 × 3 factor rather than from the 3N × 3N
    # matrix: it is the same matrix and it is exactly block diagonal.
    chol = np.linalg.cholesky(rep.metric)          # metric = chol·cholᵀ
    eye_atoms = np.eye(rep.n_atoms)
    weight = np.kron(eye_atoms, chol.T)
    weight_inv = np.kron(eye_atoms, np.linalg.inv(chol.T))
    columns = weight @ projectors[0]
    scale = float(np.max(np.abs(columns)))
    if scale == 0.0:
        raise RuntimeError(f"the row-1 projector of {irrep.label!r} is identically zero "
                           f"although its multiplicity is {multiplicity}")
    seeds: list[np.ndarray] = []
    for column in columns.T:
        candidate = column.copy()
        for taken in seeds:
            candidate -= taken * np.vdot(taken, candidate)
        norm = float(np.linalg.norm(candidate))
        if norm > MODE_ATOL * scale:
            seeds.append(candidate / norm)
        if len(seeds) == multiplicity:
            break
    if len(seeds) != multiplicity:
        raise RuntimeError(
            f"the row-1 subspace of {irrep.label!r} has rank {len(seeds)} but its "
            f"multiplicity is {multiplicity}; the projector and the character disagree, "
            "which is a bug, not a tolerance to widen"
        )

    vectors = np.zeros((multiplicity, d, dim), dtype=np.complex128)
    for j, seed in enumerate(seeds):
        first = weight_inv @ seed
        for i in range(d):
            vectors[j, i] = projectors[i] @ first
    _fix_phases(vectors)

    equivariance = _equivariance_residual(rep, matrices, vectors)
    orthonormality = _orthonormality_residual(rep, vectors)
    if equivariance > MODE_ATOL or orthonormality > MODE_ATOL:
        raise RuntimeError(
            f"the basis vectors of {irrep.label!r} in {rep.spacegroup!r} at k = "
            f"{tuple(str(c) for c in rep.little.k)} break equivariance by {equivariance:.2e} "
            f"and orthonormality by {orthonormality:.2e}. A projector built from a mismatched "
            "gauge returns vectors that transform by nothing; this is a bug, not a tolerance"
        )
    real = bool(np.max(np.abs(vectors.imag)) <= MODE_ATOL)
    if real:
        vectors = vectors.real.astype(np.complex128)
    return IrrepBasis(
        representation=rep,
        irrep=irrep,
        multiplicity=multiplicity,
        vectors=vectors.reshape(multiplicity, d, rep.n_atoms, 3),
        irrep_matrices=matrices,
        real=real,
        reality=reality,
        pairing=pairing,
        equivariance_residual=equivariance,
        orthonormality_residual=orthonormality,
    )


def _fix_phases(vectors: np.ndarray) -> None:
    """One global phase per basis set, so a real answer looks real.

    Scaling a whole basis set leaves the equivariance relation exact — it is
    the amplitude the refinement carries — while a per-vector phase would not,
    so the phase is chosen from the set's first row and applied to all of them.
    """
    for j in range(vectors.shape[0]):
        flat = vectors[j].reshape(-1)
        magnitudes = np.abs(flat)
        cut = magnitudes.max() * 1e-6
        index = int(np.argmax(magnitudes > cut))
        pivot = flat[index]
        vectors[j] *= np.conj(pivot) / abs(pivot)


def _maybe_real_gauge(rep: SiteRepresentation, irrep: SmallIrrep):
    """The irrep matrices to project with, and whether a real gauge was applied.

    A small irrep is fixed only up to a unitary intertwiner (:mod:`.irreps`),
    and which representative comes back is not canonical, so an irrep that *is*
    equivalent to a real representation can still arrive complex.  When Γ
    itself is real — every return phase ±1, i.e. 2k a reciprocal lattice vector
    — and the Frobenius–Schur indicator is +1, a real gauge exists, and
    projecting in it makes the basis vectors real, which is what a refinement
    and every published table want.

    The construction is the Autonne–Takagi factorisation of the intertwiner:
    U = Σ_g conj(D(g))·X·D(g)† satisfies conj(D(h))·U = U·D(h) for a random X
    (Schur), is symmetric and unitary for indicator +1, hence U = X + iY with X,
    Y commuting real symmetric matrices, simultaneously diagonalised by a real
    orthogonal Q as U = Q·diag(e^{iφ})·Qᵀ; then C = Q·diag(e^{−iφ/2})·Qᵀ gives
    C†·D(g)·C real.  Verified, and abandoned (leaving the irrep's own matrices)
    rather than forced if it does not come out real — the complex answer is
    correct, only less convenient.
    """
    if not rep.little.has_minus_k or irrep.frobenius_schur != 1:
        return irrep.matrices, False
    if float(np.max(np.abs(rep.matrices.imag))) > MODE_ATOL:
        return irrep.matrices, False
    d = irrep.dimension
    for seed in (0, 1, 2, 3):
        rng = np.random.default_rng(seed)
        probe = rng.normal(size=(d, d)) + 1j * rng.normal(size=(d, d))
        u = np.einsum("gab,bc,gdc->ad", np.conj(irrep.matrices), probe,
                      np.conj(irrep.matrices))
        norm = float(np.linalg.norm(u))
        if norm < 1e-8:
            continue
        u = u / norm * math.sqrt(d)
        if (float(np.max(np.abs(u - u.T))) > 1e-6
                or float(np.max(np.abs(u @ u.conj().T - np.eye(d)))) > 1e-6):
            continue
        _, q = np.linalg.eigh(u.real + 0.6180339887498949 * u.imag)
        diagonal = q.T @ u @ q
        if float(np.max(np.abs(diagonal - np.diag(np.diag(diagonal))))) > 1e-6:
            continue
        c = q @ np.diag(np.exp(-0.5j * np.angle(np.diag(diagonal)))) @ q.T
        real_matrices = np.einsum("ab,gbc,cd->gad", c.conj().T, irrep.matrices, c)
        if float(np.max(np.abs(real_matrices.imag))) < 1e-8:
            return real_matrices.real.astype(np.complex128), True
    return irrep.matrices, False


def _reality_and_pairing(rep: SiteRepresentation, irrep: SmallIrrep, real_gauge: bool):
    """The reality class of the irrep and the sentence that says what pairs with it."""
    if not rep.little.has_minus_k:
        return irrep.reality, (
            "2k is not a reciprocal lattice vector, so the conjugate small irrep lives at "
            "-k. The physically irreducible representation is D_k + D*_-k and the moment is "
            "m_j(R) = sum_l C_l psi_lj exp(-2*pi*i*k.R) + c.c., with complex amplitudes C_l"
        )
    if irrep.frobenius_schur == 1:
        return "real", (
            "2k is a reciprocal lattice vector and the irrep is real, so the amplitudes are "
            "real and m_j(R) = sum_l C_l psi_lj exp(-2*pi*i*k.R) is already real"
            + ("" if real_gauge else
               "; the vectors are still complex because no real gauge of the irrep was found")
        )
    if irrep.frobenius_schur == 0:
        return "complex", (
            "the conjugate small irrep is an inequivalent irrep at the same k; the physically "
            "irreducible representation is D + D* and the amplitudes are complex"
        )
    return "pseudoreal", (
        "the irrep is pseudoreal: D is equivalent to D* only through an antisymmetric "
        "intertwiner, so no real gauge exists and the physically irreducible representation "
        "is D + D with complex amplitudes"
    )


def _equivariance_residual(rep: SiteRepresentation, matrices: np.ndarray,
                           vectors: np.ndarray) -> float:
    """Worst violation of Γ(g)·ψ_{i,j} = Σ_m D(g)_{mi}·ψ_{m,j}."""
    if vectors.shape[0] == 0:
        return 0.0
    stack = np.moveaxis(vectors, 1, 2)                     # (n_v, dim, d)
    got = np.einsum("gab,jbi->gjai", rep.matrices, stack)
    want = np.einsum("jam,gmi->gjai", stack, matrices)
    return float(np.max(np.abs(got - want)))


def _orthonormality_residual(rep: SiteRepresentation, vectors: np.ndarray) -> float:
    """Deviation of the Gram matrix from the identity, in the cell metric."""
    flat = vectors.reshape(-1, rep.dimension)
    if flat.shape[0] == 0:
        return 0.0
    gram = flat.conj() @ rep.inner_product @ flat.T
    return float(np.max(np.abs(gram - np.eye(flat.shape[0]))))


# --------------------------------------------------------------------------
# the printable table
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class ModeTable:
    """The classic representation-analysis table for one site orbit and one k.

    Printing it gives the decomposition line, the orbit with its atom numbering
    — without which no mode name means anything — and, per irrep, one row per
    basis vector with the component triple at every atom.
    """

    decomposition: Decomposition
    bases: tuple[IrrepBasis, ...]

    @property
    def representation(self) -> SiteRepresentation:
        return self.decomposition.representation

    @property
    def total_free_real_amplitudes(self) -> int:
        """Real mode amplitudes over the physically irreducible representations.

        A genuinely complex irrep and its complex conjugate are **one**
        physically irreducible representation: the realification of either
        already spans the whole real isotypic block, so a conjugate pair is
        counted once.  Measured (M-7, 2026-09-06) on P4 at Γ with a general
        site: summing every irrep gives 3 + 6 + 6 + 3 = 18 against 3N = 12; with
        the pair collapsed the total equals 3N on all 230 standard settings.
        Self-conjugate irreps (real characters, which includes every pseudoreal
        one) are always counted.
        """
        total = 0
        kept: list[np.ndarray] = []
        for b in self.bases:
            chi = np.asarray(b.irrep.characters)
            if not np.allclose(chi, np.conj(chi), atol=1e-8) and any(
                    np.allclose(np.conj(other), chi, atol=1e-8) for other in kept):
                continue
            kept.append(chi)
            total += b.free_real_amplitudes
        return total

    def __str__(self) -> str:  # pragma: no cover - exercised by a formatting test
        rep = self.representation
        lines = [str(self.decomposition), ""]
        lines.append("atoms (conventional fractional, one primitive cell):")
        for j, position in enumerate(rep.positions):
            lines.append(f"  {j + 1}  ({position[0]:8.5f}, {position[1]:8.5f}, "
                         f"{position[2]:8.5f})")
        for basis in self.bases:
            if not basis.multiplicity:
                continue
            lines.append("")
            lines.append(f"{basis.irrep.label}: dim {basis.irrep.dimension}, "
                         f"multiplicity {basis.multiplicity}, {basis.reality}, "
                         f"{'real' if basis.real else 'complex'} vectors, "
                         f"{basis.free_real_amplitudes} real amplitudes")
            for j, i, label in basis.labels():
                triples = basis.vectors[j - 1, i - 1]
                cells = "  ".join(_format_triple(t) for t in triples)
                lines.append(f"  {label:>16s}  {cells}")
        return "\n".join(lines)


def _format_triple(triple: np.ndarray) -> str:
    """One atom's component triple, real-only when it is real."""
    if np.max(np.abs(triple.imag)) <= MODE_ATOL:
        return "(" + " ".join(f"{v:6.3f}" for v in triple.real) + ")"
    return "(" + " ".join(f"{v.real:6.3f}{v.imag:+6.3f}i" for v in triple) + ")"


def mode_table(rep: SiteRepresentation, irreps) -> ModeTable:
    """Decompose a site representation and project every irrep that occurs.

    The one call a caller normally wants: it is :func:`decompose` followed by
    :func:`basis_vectors` for each irrep with n_ν > 0, packaged so that the
    atom ordering travels with the vectors.
    """
    decomposition = decompose(rep, irreps)
    bases = tuple(basis_vectors(rep, ir) for ir, n in zip(decomposition.irreps,
                                                          decomposition.multiplicities) if n)
    return ModeTable(decomposition=decomposition, bases=bases)
