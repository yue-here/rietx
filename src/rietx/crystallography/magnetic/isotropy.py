"""Isotropy subgroups, candidate magnetic models, and what a powder cannot separate.

:mod:`.irreps` gives the small irreps of the little group of **k**, and
:mod:`.modes` decomposes a site orbit's magnetic representation and projects
its basis vectors.  A magnetic *structure* is a point in one irrep's
order-parameter space; the symmetry of that point is the **isotropy subgroup**
of its direction, and with time reversal in the group that subgroup is a
magnetic space group — the operator list WP-1327 refines under (magnetic-track
decision D-4: the MSG operator list is the refinable object, representation
analysis generates the candidates and their labels).  The kernel/stabiliser
construction is Stokes & Hatch (1988), *Isotropy Subgroups of the 230
Crystallographic Space Groups*; the workflow that turns a parent, an irrep and
an order-parameter direction into a structure is Campbell, Stokes, Tanner &
Hatch (2006), *J. Appl. Cryst.* **39**, 607 (ISODISPLACE), and the magnetic
half of it is Perez-Mato, Gallego, Tasci, Elcoro, de la Flor & Aroyo (2015),
*Annu. Rev. Mater. Res.* **45**, 217.

This module also answers the question a *powder* code actually has to ask:
which of those candidates the data cannot tell apart.  Shirane (1959),
*Acta Cryst.* **12**, 282 states the classic case — a collinear structure in a
cubic group gives a powder intensity independent of the moment direction — and
:func:`equivalence_classes` computes that rather than asserting it.

**Public API — fixed 2026-09-06.**

::

    magnetic_cell(space_group, k)                     -> MagneticCell
    order_parameter_space(basis, *, kind="magnetic")  -> OrderParameterSpace
    isotropy_directions(space)                        -> tuple[OrderParameterDirection, ...]
    candidates(space_group, site_xyz, k, ...)         -> CandidateSet

    compatible_cell(space_group)                      -> (3, 3) row-vector lattice, A
    reflections(lattice, d_min)                       -> ReflectionSet
    structure_factors(candidate, reflections)         -> (n_domains, n_free, n_hkl, 3) complex
    powder_intensities(candidate, amplitudes, ...)    -> (n_shells,) float
    systematic_absences(candidate, ...)               -> AbsenceReport
    determinable_amplitudes(candidate, ...)           -> int
    powder_equivalent(a, b, ...)                      -> bool
    equivalence_classes(candidates, ...)              -> tuple[tuple[int, ...], ...]

Scope: **k = 0 and 2k a reciprocal lattice vector**
--------------------------------------------------
The stabiliser of an order-parameter direction is a subgroup of the *grey*
little group G_k1'.  Turning it into a space group needs the lattice
translations, and a translation t enters the order parameter as
exp(−2πi k·t) — which is ±1, hence a time-reversal sign, only when 2k is a
reciprocal lattice vector.  For any other k (a denominator of 3 or more, or a
centred case like I4₁32 at (½,½,½) where (1,1,1) is not a reciprocal lattice
vector of the body-centred lattice) the order parameter is genuinely complex,
the −k arm of the star is coupled to the +k one, and the isotropy subgroup is
not a subgroup of the grey little group at all.  Those k are **refused by
name** by :func:`candidates`, pointing at the star/multi-k rung.  What already
works for them: :mod:`.irreps` builds the star and the small irreps at every
k it accepts, and :mod:`.modes` builds the basis vectors and counts the real
amplitudes including the k/−k pairing — everything except the translation
subgroup of the candidate and therefore everything downstream of it.

Conventions a caller can get wrong silently
-------------------------------------------
1. **The order-parameter space is real.**  For an irrep with a real gauge (the
   one :func:`~.modes.basis_vectors` already found) it is ℝ^{d_ν}; otherwise
   it is the *realification* ℝ^{2d_ν}, with matrices [[Re D, −Im D], [Im D,
   Re D]], which is the physically irreducible representation and is what makes
   the amplitude count agree with :attr:`~.modes.IrrepBasis.free_real_amplitudes`.
   The realification is only a representation of the same group because Γ_mag
   is real, which is exactly what 2k ∈ L* buys — the same fact the scope fence
   above rests on.

2. **Time reversal acts as −1 on a magnetic order parameter and +1 on a
   displacive one** (``kind``).  With +1 every stabiliser contains 1' and every
   candidate is a grey group, which forbids every ordered moment; that is the
   displacive rule, and using it on a moment is a physics error a dimension
   count cannot see.

3. **A stabiliser is a set of group elements, not of matrices.**  Two grey
   elements can share a matrix (when −1 is already in the image), and it is the
   *element* that carries the time-reversal sign the operator list needs.

4. **The direction label is gauge-dependent; the subgroup is not.**  The irrep
   matrices are canonical only up to a unitary intertwiner (:mod:`.irreps`), so
   which vector of the order-parameter space is called (a, a, 0) depends on the
   gauge :func:`~.modes.basis_vectors` chose.  The set of stabiliser subgroups,
   the operator lists, the identified BNS numbers and the moment families do
   **not**: conjugating the gauge conjugates the fixed subspaces and leaves the
   stabilisers alone.  So the labels here are this package's, not ISODISTORT's,
   and a comparison with a published table must be made on the subgroup.

5. **Moment components are contravariant fractional components** of the cell
   they are stated in — m = m_x·**a** + m_y·**b** + m_z·**c** with a, b, c the
   *cell vectors*, not the unit vectors of magCIF's ``crystalaxis``.  The two
   differ by diag(a, b, c), which matters here and only here in the magnetic
   package, because a candidate is stated in a **supercell** whose axis lengths
   are not the parent's.  :func:`~.operators.moment_to_cartesian` takes the
   ``crystalaxis`` form, so :func:`moment_cartesian` converts first.

What a powder measures, and the domains
---------------------------------------
The magnetic intensity of a reflection is |M⊥|² with
M(h) = Σ_j m_j·exp(2πi h·r_j) over the magnetic cell and M⊥ = M − (M·ĥ)ĥ
(Halpern & Johnson, 1939, *Phys. Rev.* **55**, 898), with a unit form factor
here because the form factor is a per-species scalar that cancels from every
comparison this module makes.  A powder sums that over every reflection at the
same d and over every **domain** — the images of the model under the parent
operations the candidate's own group does not contain.  Summing over a
complete shell makes the domain sum a constant factor (each domain is an
isometry of the shell), which this module computes rather than assumes:
:func:`powder_intensities` builds the domains explicitly and
``tests/test_magnetic_isotropy.py`` measures the ratio.  The arms of the star
of k are domains too, and a domain related to another by a parent operation has
an *identical* powder pattern because a powder average is already an average
over orientations; only domains inside the grey little group are built here,
and the reason is that one.

References
----------
Shirane, G. (1959). *Acta Cryst.* **12**, 282 — the powder magnetic structure
factor and the directions a powder average cannot determine.
Halpern, O. & Johnson, M. H. (1939). *Phys. Rev.* **55**, 898 — the magnetic
interaction vector M⊥.
Gallego, S. V., Tasci, E. S., de la Flor, G., Perez-Mato, J. M. & Aroyo, M. I.
(2012). *J. Appl. Cryst.* **45**, 1236 — MAGNEXT, systematic absences of
magnetic reflections under a magnetic space group.
Stokes, H. T. & Hatch, D. M. (1988). *Isotropy Subgroups of the 230
Crystallographic Space Groups*. Singapore: World Scientific.
Campbell, B. J., Stokes, H. T., Tanner, D. E. & Hatch, D. M. (2006).
*J. Appl. Cryst.* **39**, 607 — ISODISPLACE.
Campbell, B. J., Stokes, H. T., Perez-Mato, J. M. & Rodríguez-Carvajal, J.
(2022). *Acta Cryst.* A**78**, 99 — the UNI magnetic space-group numbering.
Perez-Mato, J. M., Gallego, S. V., Tasci, E. S., Elcoro, L., de la Flor, G. &
Aroyo, M. I. (2015). *Annu. Rev. Mater. Res.* **45**, 217.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass, field, replace
from fractions import Fraction

import numpy as np

from ..wyckoff import _compatible_lattice
from . import irreps as _irreps
from . import modes as _modes
from . import operators as _operators
from .irreps import KVector, LittleGroup, SmallIrrep, as_kvector
from .modes import IrrepBasis, PermutationRepresentation, SiteRepresentation
from .operators import (
    IDENTITY,
    MagneticGroup,
    MagneticOperator,
    MagneticSpaceGroupId,
    _rational_inverse,
    allowed_displacement_basis,
    allowed_moment_basis,
    format_transform,
    identify,
    in_span,
    moment_to_cartesian,
)

#: What :func:`~.operators.identify` can raise when spglib declines a group.
#: It documents a ``ValueError``, and that is what it raises while spglib is in
#: its own default (deprecated) error mode.  **spgrep sets
#: ``spglib.error.OLD_ERROR_HANDLING = False`` at import** (spgrep 0.7.0,
#: ``__init__.py``), after which spglib *raises* where it returned ``None`` and
#: the same call leaks a ``SpglibError`` instead — so anything that catches a
#: refusal has to catch both.  See ``tests/test_magnetic_isotropy.py``, which
#: pins the leak, and the M-7 report.
IDENTIFY_REFUSALS: tuple[type[BaseException], ...] = (ValueError,)
try:  # pragma: no cover - present in every spglib this package supports
    from spglib.error import SpglibError as _SpglibError

    IDENTIFY_REFUSALS = (ValueError, _SpglibError)
except ImportError:  # pragma: no cover - a spglib without the error module
    pass

#: Order-parameter kinds.  ``"magnetic"`` gives time reversal the −1 a moment
#: carries; ``"displacive"`` gives it the +1 a displacement carries.
ORDER_PARAMETER_KINDS = ("magnetic", "displacive")

#: Tolerance on the numerical linear algebra of the order-parameter space —
#: subspace comparisons, fixed-subspace ranks, "this matrix is real".  The
#: irrep matrices come out of an eigendecomposition (:mod:`.irreps`), so this
#: cannot be exact; it is deliberately far above the residuals :mod:`.modes`
#: verifies (1e-14) and far below any real degeneracy.
ISOTROPY_ATOL = 1e-8

#: Relative tolerance on |M⊥|² below which a reflection counts as absent, and
#: on a singular value below which an amplitude counts as undeterminable.
INTENSITY_RTOL = 1e-9

#: Shortest axis of the default compatible cell, Å.  Only ratios of intensities
#: are ever compared, so the scale sets nothing but which reflections fall
#: inside a given d_min.
DEFAULT_CELL_SCALE = 5.0

_LETTERS = "abcdefghijklmnopqrstuvwxyz"


# --------------------------------------------------------------------------
# the magnetic cell
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class MagneticCell:
    """The cell a candidate at ``k`` is stated in, and how it sits in the parent.

    ``basis`` is P with **columns** the magnetic cell's basis vectors in the
    parent's conventional fractional coordinates, so (a', b', c') = (a, b, c)·P
    — magCIF's ``_space_group_magn.transform_BNS_Pp_abc`` sense, which
    :attr:`transform` writes out.  A point with parent fractional coordinates x
    has magnetic fractional coordinates P⁻¹·x, and so does a contravariant
    moment.

    ``translations`` are the coset representatives of the parent lattice modulo
    the magnetic cell's own integer lattice, each with the time-reversal sign
    ε = exp(−2πi k·t) it enters the order parameter with.  For k = 0 the
    magnetic cell **is** the parent's conventional cell and these are the
    parent's centrings, all with ε = +1; for 2k ∈ L* and k ≠ 0 there are two,
    the identity and one **anti-translation**, which is what makes every such
    candidate a type IV magnetic space group.
    """

    k: KVector
    basis: tuple[tuple[Fraction, ...], ...]
    translations: tuple[tuple[KVector, int], ...]
    spacegroup: str | None = None

    @property
    def transform(self) -> str:
        """Parent → magnetic (P, p) in ``transform_BNS_Pp_abc`` form."""
        return format_transform([list(row) for row in self.basis],
                                (Fraction(0), Fraction(0), Fraction(0)))

    @property
    def inverse_transform(self) -> str:
        """(P⁻¹, 0), which is what :meth:`~.operators.MagneticGroup.transformed` takes.

        That method carries a group **into** the setting whose basis vectors are
        the columns of its argument, so reaching a supercell means handing it the
        inverse: ``transformed("a/2,b,c;0,0,0")`` doubles a, and its order guard
        then demands the |det P| = ½ that a doubled cell has.
        """
        return format_transform(_exact_inverse(self.basis),
                                (Fraction(0), Fraction(0), Fraction(0)))

    @property
    def index(self) -> int:
        """|det P| times the number of parent centrings: atoms per parent atom."""
        return len(self.translations)

    @property
    def doubled(self) -> bool:
        """Whether the magnetic lattice is a proper sublattice of the parent's."""
        return any(eps < 0 for _, eps in self.translations)

    def to_magnetic(self, vector) -> np.ndarray:
        """Parent fractional (or contravariant moment) components → magnetic ones."""
        return _fraction_inverse(self.basis) @ np.asarray(vector, dtype=np.float64)


def _frac(value) -> Fraction:
    """An exact ``Fraction`` with **Python** integers inside it.

    ``Fraction(numpy.int64(1))`` keeps the numpy integer, and hashing such a
    Fraction raises inside CPython's own ``_hash_algorithm``.  Every rational
    that reaches an operator list goes through here.
    """
    if isinstance(value, Fraction):
        return Fraction(int(value.numerator), int(value.denominator))
    if isinstance(value, (int, np.integer)):
        return Fraction(int(value))
    return Fraction(value)


def _fraction_matrix(rows) -> tuple[tuple[Fraction, ...], ...]:
    return tuple(tuple(_frac(v) for v in row) for row in rows)


def _exact_inverse(rows) -> list[list[Fraction]]:
    """P⁻¹ over ``Fraction``.  Reuses :mod:`.operators`' kernel, as M-6(b) reused
    ``wyckoff._compatible_lattice``: one rational-inverse implementation in the
    package is what stops two of them disagreeing about a supercell."""
    return _rational_inverse([[_frac(v) for v in row] for row in rows])


def _fraction_inverse(rows) -> np.ndarray:
    return np.array([[float(v) for v in row] for row in _exact_inverse(rows)])


def _translation_sign(k: KVector, t) -> int:
    """ε = exp(−2πi k·t) = ±1, exactly; raises when 2k·t is not an integer."""
    value = sum(_frac(k[i]) * _frac(t[i]) for i in range(3))
    if (2 * value).denominator != 1:
        raise ValueError(
            f"k = {tuple(str(c) for c in k)} and the lattice translation "
            f"{tuple(str(Fraction(c)) for c in t)} give exp(-2 pi i k.t) = "
            f"exp(-2 pi i {value}), which is not ±1; this module needs 2k in the "
            f"reciprocal lattice (see the module docstring's scope fence)")
    return 1 if value.denominator == 1 else -1


def _reduce_basis(rows, lattice, *, span: int = 2) -> list[tuple[Fraction, ...]]:
    """A short basis of the same lattice, exactly.

    The magnetic sublattice basis that falls out of doubling one primitive
    vector is correct and can be very oblique — for the fcc L point it gives
    rotation matrices with entries of −2 — and spglib's identification then
    fails on a cell no tabulated setting looks like.  So the basis is replaced
    by the shortest one reachable with integer coefficients in
    [−``span``, ``span``], measured in the group's own compatible metric, and
    the replacement is required to be **unimodular** against the original, which
    is what makes it the same lattice rather than a sublattice of it.
    """
    metric = np.asarray(lattice, dtype=np.float64) @ np.asarray(
        lattice, dtype=np.float64).T
    base = [[_frac(v) for v in row] for row in rows]
    pool: list[tuple[float, tuple[int, int, int], tuple[Fraction, ...]]] = []
    for coeffs in itertools.product(range(-span, span + 1), repeat=3):
        if all(c == 0 for c in coeffs):
            continue
        first = next(c for c in coeffs if c != 0)
        if first < 0:
            continue
        vector = tuple(sum(coeffs[j] * base[j][i] for j in range(3)) for i in range(3))
        v = np.array([float(c) for c in vector])
        pool.append((float(v @ metric @ v), coeffs, vector))
    pool.sort(key=lambda item: (item[0], item[1]))
    chosen: list[tuple[int, int, int]] = []
    vectors: list[tuple[Fraction, ...]] = []
    for _, coeffs, vector in pool:
        trial = [*chosen, coeffs]
        matrix = np.array(trial, dtype=np.float64)
        if len(trial) < 3:
            if np.linalg.matrix_rank(matrix) < len(trial):
                continue
        elif abs(round(float(np.linalg.det(matrix)))) != 1:
            continue
        chosen.append(coeffs)
        vectors.append(vector)
        if len(chosen) == 3:
            return vectors
    return [tuple(row) for row in base]  # pragma: no cover - span 2 always suffices


def magnetic_cell(space_group, k) -> MagneticCell:
    """The magnetic cell of ``k`` in ``space_group``, and the parent → magnetic (P, p).

    For k ≡ 0 this is the parent's own conventional cell.  Otherwise it is the
    cell of the sublattice {t : k·t ∈ ℤ}, which has index 2 in the parent
    lattice when 2k is a reciprocal lattice vector — the magnetic supercell.  A
    basis for it is built from :func:`~.irreps.primitive_basis` (never from the
    conventional axes, or a centred lattice would lose its centring vectors),
    so for a primitive parent the answer is the obvious doubling of one axis and
    for a centred one it is a primitive cell of the magnetic lattice.

    Raises ``ValueError`` naming the k when 2k is not a reciprocal lattice
    vector.
    """
    sg = _irreps._resolve(space_group)
    kk = as_kvector(k)
    if not _irreps.equivalent_kvectors(sg, tuple(2 * c for c in kk), (0, 0, 0)):
        raise ValueError(
            f"k = {tuple(str(c) for c in kk)} in {sg.xhm()!r} has 2k outside the "
            f"reciprocal lattice, so a parent lattice translation enters the order "
            f"parameter with a phase that is not ±1 and the isotropy subgroup is not "
            f"a subgroup of the grey little group. This rung covers k = 0 and 2k in "
            f"the reciprocal lattice only; the star and multi-k cases are M-8/M-11")
    centrings = _irreps._centrings(sg)
    if _irreps.equivalent_kvectors(sg, kk, (0, 0, 0)):
        basis = _fraction_matrix(np.eye(3, dtype=int))
        translations = tuple((tuple(_frac(v) for v in c), 1) for c in centrings)
        return MagneticCell(kk, basis, translations, sg.xhm())

    prim = _irreps.primitive_basis(sg)                     # rows: primitive basis
    signs = [_translation_sign(kk, row) for row in prim]
    if all(s > 0 for s in signs):  # pragma: no cover - excluded by k != 0 above
        raise RuntimeError(f"k = {tuple(str(c) for c in kk)} is not zero but every "
                           f"primitive lattice vector enters with ε = +1")
    pivot = signs.index(-1)
    rows: list[tuple[Fraction, ...]] = []
    anti = prim[pivot]
    for i, row in enumerate(prim):
        if i == pivot:
            rows.append(tuple(2 * c for c in row))
        elif signs[i] < 0:
            rows.append(tuple(c + a for c, a in zip(row, anti)))
        else:
            rows.append(tuple(row))
    rows = _reduce_basis(rows, _compatible_lattice(sg))
    # rows are the magnetic basis vectors; P has them as columns
    basis = _fraction_matrix([[rows[j][i] for j in range(3)] for i in range(3)])
    translations = ((tuple(_frac(0) for _ in range(3)), 1),
                    (tuple(_frac(v) for v in anti), -1))
    return MagneticCell(kk, basis, translations, sg.xhm())


def compatible_cell(space_group, *, scale: float = DEFAULT_CELL_SCALE) -> np.ndarray:
    """A cell of the group's own setting, as a ``(3, 3)`` row-vector lattice in Å.

    The Reynolds average :func:`~.modes.crystal_metric` is built from — the same
    ``wyckoff._compatible_lattice`` the nuclear side probes spglib with — scaled
    so the shortest axis is ``scale`` Å.  It follows the *setting*, not the
    crystal system, so a non-standard monoclinic unique axis or a rhombohedral
    setting comes out right with no per-system table.

    It is a placeholder for a real cell and nothing that compares intensities
    depends on the scale; what it does decide is which reflections fall inside a
    given d_min, so a caller with a real cell should pass it instead.
    """
    lattice = np.asarray(_compatible_lattice(_irreps._resolve(space_group)),
                         dtype=np.float64)
    return lattice * (scale / float(np.min(np.linalg.norm(lattice, axis=1))))


def magnetic_lattice(cell: MagneticCell, parent_lattice) -> np.ndarray:
    """The magnetic cell's row-vector lattice, from the parent's.

    (a', b', c') = (a, b, c)·P, so with A the row-vector matrix A' = Pᵀ·A.
    """
    p = np.array([[float(v) for v in row] for row in cell.basis])
    return p.T @ np.asarray(parent_lattice, dtype=np.float64)


def moment_cartesian(moments, lattice) -> np.ndarray:
    """Contravariant fractional moment components → Cartesian, through M-5's conversion.

    :func:`~.operators.moment_to_cartesian` speaks magCIF's ``crystalaxis``
    basis — *unit* vectors along a, b, c — and this module carries contravariant
    components on the cell vectors themselves (module docstring, convention 5),
    so the components are multiplied by the axis lengths first.  Going through
    M-5 rather than writing Aᵀ·m here is deliberate: one conversion in the
    package is what keeps the magnitude convention (|m| = √(mᵀGm) on unit axes)
    from drifting between the two rungs.
    """
    a = np.asarray(lattice, dtype=np.float64)
    lengths = np.linalg.norm(a, axis=1)
    cell = _cell_parameters(a)
    m = np.atleast_2d(np.asarray(moments, dtype=np.float64))
    return np.array([moment_to_cartesian(row * lengths, cell) for row in m])


def _cell_parameters(lattice) -> tuple[float, ...]:
    """(a, b, c, α, β, γ) in Å and degrees from a row-vector lattice."""
    a = np.asarray(lattice, dtype=np.float64)
    lengths = np.linalg.norm(a, axis=1)
    angles = []
    for i, j in ((1, 2), (0, 2), (0, 1)):
        cosine = float(a[i] @ a[j] / (lengths[i] * lengths[j]))
        angles.append(float(np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0)))))
    return (float(lengths[0]), float(lengths[1]), float(lengths[2]), *angles)


# --------------------------------------------------------------------------
# the order-parameter space
# --------------------------------------------------------------------------

#: One element of the grey little group as the order parameter sees it:
#: ``(index into LittleGroup, time-reversal sign)``.
GreyElement = tuple[int, int]


@dataclass(frozen=True, eq=False)
class OrderParameterSpace:
    """The real order-parameter space of one irrep under the grey little group.

    ``matrices[e]`` is the real matrix by which the element ``elements[e]`` acts.
    ``configurations[c, p]`` is the ``(N, 3)`` moment pattern of order-parameter
    coordinate ``p`` in copy ``c``, in the parent's own cell and in contravariant
    fractional components, so a point (amplitudes A) of the family is
    Σ_{c,p} A[c, p]·configurations[c, p].

    ``doubled`` says the irrep had no real gauge and the space is the
    realification, of dimension 2d_ν; :attr:`dimension` is d_ν otherwise.
    """

    irrep: SmallIrrep
    basis: IrrepBasis
    kind: str
    elements: tuple[GreyElement, ...]
    matrices: np.ndarray            # (2n, dim, dim) float
    configurations: np.ndarray      # (n_copies, dim, N, 3) float
    doubled: bool

    @property
    def dimension(self) -> int:
        """Dimension of the real order-parameter space, d_ν or 2·d_ν."""
        return int(self.matrices.shape[1])

    @property
    def copies(self) -> int:
        """n_ν, the multiplicity of the irrep in the site representation."""
        return int(self.configurations.shape[0])

    @property
    def little(self) -> LittleGroup:
        return self.irrep.little


def order_parameter_space(basis: IrrepBasis, *, kind: str = "magnetic"
                          ) -> OrderParameterSpace:
    """The real order-parameter space of one irrep, with time reversal in the group.

    The grey little group is G_k1' = G_k ∪ G_k·1'.  A **magnetic** order
    parameter changes sign under 1' and a **displacive** one does not, so the
    element (g, ε) acts by η·D_ν(g) with η = ε for ``kind="magnetic"`` and
    η = +1 for ``kind="displacive"``.  D_ν is taken in the gauge
    :func:`~.modes.basis_vectors` used for the vectors, so the order-parameter
    coordinates and the moment patterns are in step; where that gauge is not
    real the space is the realification (module docstring, convention 1).

    The construction is Stokes & Hatch (1988): an isotropy subgroup is the
    stabiliser of a point of this space, and turning it into a magnetic space
    group is what :func:`candidates` then does.
    """
    if kind not in ORDER_PARAMETER_KINDS:
        raise ValueError(f"kind must be one of {ORDER_PARAMETER_KINDS}, got {kind!r}")
    if basis.multiplicity == 0:
        raise ValueError(
            f"irrep {basis.irrep.label!r} does not occur in this site representation "
            f"(multiplicity 0), so it has no order-parameter space here")
    matrices = np.asarray(basis.irrep_matrices)
    vectors = np.asarray(basis.vectors)
    real_gauge = float(np.max(np.abs(matrices.imag))) <= ISOTROPY_ATOL
    if real_gauge != bool(basis.real):
        raise RuntimeError(
            f"irrep {basis.irrep.label!r} has real matrices = {real_gauge} but real "
            f"basis vectors = {basis.real}; with a real representation the two are the "
            f"same statement and this module's amplitude count depends on it")
    n_ops = matrices.shape[0]
    if real_gauge:
        small = matrices.real
        configs = vectors.real
    else:
        small = np.array([np.block([[m.real, -m.imag], [m.imag, m.real]])
                          for m in matrices])
        # m = Σ C ψ + c.c. with C = A + iB gives m = Σ (A·2Reψ − B·2Imψ)
        configs = np.concatenate([2.0 * vectors.real, -2.0 * vectors.imag], axis=1)
    elements: list[GreyElement] = []
    stack: list[np.ndarray] = []
    for i in range(n_ops):
        for eps in (1, -1):
            elements.append((i, eps))
            stack.append((eps if kind == "magnetic" else 1) * small[i])
    space = OrderParameterSpace(
        irrep=basis.irrep, basis=basis, kind=kind, elements=tuple(elements),
        matrices=np.array(stack, dtype=np.float64), configurations=configs,
        doubled=not real_gauge)
    expected = basis.free_real_amplitudes
    if space.copies * space.dimension != expected:
        raise RuntimeError(
            f"{basis.irrep.label!r} gives {space.copies}·{space.dimension} real "
            f"order-parameter coordinates against {expected} free real amplitudes "
            f"from modes.basis_vectors; the realification and the amplitude count "
            f"must agree or every parameter count downstream is wrong")
    return space


# --------------------------------------------------------------------------
# the lattice of fixed subspaces
# --------------------------------------------------------------------------

def _nullspace(matrix: np.ndarray, atol: float = ISOTROPY_ATOL) -> np.ndarray:
    """Orthonormal rows spanning ker(matrix)."""
    m = np.atleast_2d(np.asarray(matrix, dtype=np.float64))
    _, s, vt = np.linalg.svd(m)
    scale = max(1.0, float(s.max())) if s.size else 1.0
    rank = int(np.sum(s > atol * scale))
    return vt[rank:]


def _projector(rows: np.ndarray, dim: int) -> np.ndarray:
    if rows.shape[0] == 0:
        return np.zeros((dim, dim))
    q, _ = np.linalg.qr(np.asarray(rows, dtype=np.float64).T)
    return q @ q.T


def _intersect(p: np.ndarray, q: np.ndarray) -> np.ndarray:
    """Projector onto the intersection of two subspaces given by projectors."""
    dim = p.shape[0]
    eye = np.eye(dim)
    return _projector(_nullspace(np.vstack([eye - p, eye - q])), dim)


@dataclass(frozen=True, eq=False)
class OrderParameterDirection:
    """One order-parameter direction, as the subspace its stabiliser fixes pointwise.

    ``subspace`` has orthonormal rows spanning the largest set of
    order-parameter values every element of ``stabilizer`` leaves alone; the
    ISOTROPY-style ``label`` — ``(a, 0, 0)``, ``(a, a, 0)``, ``(a, b, 0)`` — is
    that subspace written as a general vector, and is **gauge-dependent**
    (module docstring, convention 4).  ``stabilizer`` is the isotropy subgroup
    as grey-little-group *elements*.
    """

    label: str
    subspace: np.ndarray            # (r, dim) orthonormal rows
    stabilizer: tuple[GreyElement, ...]
    conjugates: int = 1

    @property
    def rank(self) -> int:
        """Number of independent order-parameter components the direction leaves free."""
        return int(self.subspace.shape[0])


def _rref(rows: np.ndarray) -> np.ndarray:
    """Reduced row echelon form of a float row space, pivots normalised to 1."""
    m = np.array(rows, dtype=np.float64, copy=True)
    n_rows, n_cols = m.shape
    pivot = 0
    for col in range(n_cols):
        if pivot >= n_rows:
            break
        target = pivot + int(np.argmax(np.abs(m[pivot:, col])))
        if abs(m[target, col]) <= 1e-9:
            continue
        m[[pivot, target]] = m[[target, pivot]]
        m[pivot] = m[pivot] / m[pivot, col]
        for r in range(n_rows):
            if r != pivot and abs(m[r, col]) > 0:
                m[r] = m[r] - m[r, col] * m[pivot]
        pivot += 1
    return m[:pivot]


_SIMPLE = [Fraction(n, d) for d in (1, 2, 3, 4, 6) for n in range(-4 * d, 4 * d + 1)]


def _as_simple(value: float) -> Fraction | None:
    for f in _SIMPLE:
        if abs(float(f) - value) < 1e-6:
            return f
    return None


def _direction_label(subspace: np.ndarray) -> str:
    """``(a, a, 0)``-style label for a subspace, or a positional one if it will not fit."""
    rows = _rref(subspace)
    entries: list[list[Fraction]] = []
    for col in range(subspace.shape[1]):
        column = []
        for r in range(rows.shape[0]):
            simple = _as_simple(float(rows[r, col]))
            if simple is None:
                return ""
            column.append(simple)
        entries.append(column)
    parts = []
    for column in entries:
        terms = []
        for q, coeff in enumerate(column):
            if coeff == 0:
                continue
            letter = _LETTERS[q]
            if coeff == 1:
                terms.append(f"+{letter}")
            elif coeff == -1:
                terms.append(f"-{letter}")
            else:
                terms.append(f"{coeff:+}{letter}")
        text = "".join(terms).lstrip("+") if terms else "0"
        parts.append(text)
    return "(" + ",".join(parts) + ")"


def isotropy_directions(space: OrderParameterSpace, *, limit: int = 512,
                        conjugacy: bool = True) -> tuple[OrderParameterDirection, ...]:
    """Every order-parameter direction with a distinct stabiliser, one per stabiliser.

    The fixed subspace of each element of the image is computed, the lattice of
    their intersections is closed, and each non-zero subspace V is replaced by
    the largest subspace with the same pointwise stabiliser S(V) = {h : h·v = v
    ∀ v ∈ V} — so the representatives and the isotropy subgroups are in
    bijection.  The whole space (the kernel of the representation, ISOTROPY's
    "general direction") is always among them.  This is the enumeration Stokes &
    Hatch (1988) tabulate and Campbell et al. (2006) drive ISODISPLACE from.

    With ``conjugacy`` (the default) directions related by an element of the
    grey little group are collapsed to one, and :attr:`OrderParameterDirection.
    conjugates` counts how many were: conjugate stabilisers are the same
    structure in a different **domain**, so listing all of [100], [010] and
    [001] as candidates would put three copies of one model in the table and
    then discover that a powder cannot tell them apart.  Setting it False gives
    every distinct stabiliser, which is what a domain census wants.

    For a one-dimensional irrep there is exactly one direction, whatever the
    group.  ``limit`` guards the intersection closure, which is finite but has
    no useful *a priori* bound.
    """
    dim = space.dimension
    eye = np.eye(dim)
    fixed = [(_projector(_nullspace(m - eye), dim), m) for m in space.matrices]
    lattice = [eye]
    frontier = [eye]
    while frontier:
        current = frontier.pop()
        for p, _ in fixed:
            candidate = _intersect(current, p)
            if float(np.trace(candidate)) < 0.5:
                continue
            if any(np.allclose(candidate, seen, atol=1e-7) for seen in lattice):
                continue
            lattice.append(candidate)
            frontier.append(candidate)
            if len(lattice) > limit:
                raise RuntimeError(
                    f"the lattice of fixed subspaces of {space.irrep.label!r} passed "
                    f"{limit} members in dimension {dim}; this is a guard, not a "
                    f"tolerance — raise `limit` deliberately if a real case needs it")
    by_stabilizer: dict[tuple[GreyElement, ...], np.ndarray] = {}
    for p in lattice:
        stabilizer = tuple(
            element for element, (_, m) in zip(space.elements, fixed)
            if np.max(np.abs((m - eye) @ p)) <= 1e-7)
        maximal = eye
        for element, (q, _) in zip(space.elements, fixed):
            if element in stabilizer:
                maximal = _intersect(maximal, q)
        if stabilizer not in by_stabilizer:
            by_stabilizer[stabilizer] = maximal
    items = [(stabilizer, _projector_rows(projector))
             for stabilizer, projector in by_stabilizer.items()]
    groups: list[list[int]] = []
    if conjugacy:
        projectors = [_projector(rows, dim) for _, rows in items]
        assigned: dict[int, int] = {}
        for i in range(len(items)):
            if i in assigned:
                continue
            members = [i]
            assigned[i] = len(groups)
            for h in space.matrices:
                moved = _projector(items[i][1] @ h.T, dim)
                for j in range(len(items)):
                    if j in assigned:
                        continue
                    if np.allclose(moved, projectors[j], atol=1e-7):
                        assigned[j] = len(groups)
                        members.append(j)
            groups.append(members)
    else:
        groups = [[i] for i in range(len(items))]
    out: list[OrderParameterDirection] = []
    for members in groups:
        stabilizer, rows = items[members[0]]
        out.append(OrderParameterDirection(
            label=_direction_label(rows) or f"(rank {rows.shape[0]})",
            subspace=rows, stabilizer=stabilizer, conjugates=len(members)))
    out.sort(key=lambda d: (d.rank, -len(d.stabilizer), d.label))
    # a gauge that is not axis-aligned gives several directions the same
    # fallback label; number them so a table row still names one candidate
    seen: dict[str, int] = {}
    for i, direction in enumerate(out):
        seen[direction.label] = seen.get(direction.label, 0) + 1
    running: dict[str, int] = {}
    numbered = []
    for direction in out:
        if seen[direction.label] == 1:
            numbered.append(direction)
            continue
        running[direction.label] = running.get(direction.label, 0) + 1
        numbered.append(OrderParameterDirection(
            label=f"{direction.label}#{running[direction.label]}",
            subspace=direction.subspace, stabilizer=direction.stabilizer,
            conjugates=direction.conjugates))
    return tuple(numbered)


def _projector_rows(projector: np.ndarray) -> np.ndarray:
    """Orthonormal rows spanning the image of a projector, in a stable orientation."""
    dim = projector.shape[0]
    rank = int(round(float(np.trace(projector))))
    if rank == 0:
        return np.zeros((0, dim))
    values, vectors = np.linalg.eigh(projector)
    rows = vectors[:, -rank:].T
    rows = _rref(rows)
    # normalise each row so the comparison and the label are deterministic
    for i in range(rows.shape[0]):
        pivot = rows[i][np.argmax(np.abs(rows[i]) > 1e-9)]
        if pivot < 0:
            rows[i] = -rows[i]
    q, _ = np.linalg.qr(rows.T)
    return q.T if rank > 1 else rows / np.linalg.norm(rows, axis=1, keepdims=True)


# --------------------------------------------------------------------------
# the candidates
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class MagneticCandidate:
    """One candidate magnetic model: an MSG, a cell, and a family of moment patterns.

    ``group`` is the operator list in the cell ``cell`` describes, ready for
    WP-1327; ``identification`` is what spglib recognises it as.  ``positions``
    are the magnetic-cell fractional coordinates of the site's atoms, and
    ``configurations[p]`` is the ``(N, 3)`` moment pattern of free amplitude p,
    in the same cell and in contravariant fractional components.
    ``permutation``/``parent_atoms`` (Q22) are what :meth:`in_allowed_span`
    needs for each atom's own return-vector phase: :mod:`.modes`'s own
    little-group permutation-and-phase table (built once, independently
    verified — :attr:`~.modes.PermutationRepresentation.permutations`/
    ``phases`` already handle a centred parent lattice correctly, which a
    from-scratch recomputation in the magnetic cell cannot, see the method),
    and which **parent**-orbit atom (an index into that table, not
    ``positions``' own row) each row of ``positions`` is a copy of.

    ``verified`` is the outcome of :meth:`in_allowed_span` when
    :func:`candidates` was called with ``verify=True`` — ``None`` when it
    was not run (``verify=False``), ``True`` when this *one* candidate's own
    family passed, ``False`` when it did not.  A failing candidate still
    appears in the returned :class:`CandidateSet`, with ``verification_reason``
    stating why (Q-21): one bad candidate no longer hides the rest of its
    site's passing ones, which is what raising on the first failure used to
    do.  A caller that wants only verified candidates filters on this field;
    :func:`candidates` itself still raises when *every* candidate of a site
    fails, which is the "this is a bug" case with nothing left to fall back
    on.

    ``space_group`` is :func:`candidates`'s own resolved group object (a
    ``gemmi.SpaceGroup``, or the ``OperatorGroup``
    :func:`~rietx.crystallography.symmetry.resolve_group` builds for an
    unnamed parent) rather than its bare label — stage3 D2: every consumer
    that reads this field hands it straight back to
    :func:`~.irreps.little_group`/``_irreps._resolve``, which already accepts
    either, and the label alone would have lost the operator list an unnamed
    group needs to be resolved again at all.
    """

    space_group: object  # gemmi.SpaceGroup | rietx.crystallography.symmetry.OperatorGroup
    site: tuple[float, float, float]
    k: KVector
    kind: str
    irrep_label: str
    direction: OrderParameterDirection
    cell: MagneticCell
    group: MagneticGroup
    identification: MagneticSpaceGroupId | None
    positions: np.ndarray           # (N, 3)
    configurations: np.ndarray      # (n_free, N, 3)
    permutation: PermutationRepresentation
    parent_atoms: np.ndarray        # (N,) int, index into permutation.positions/phases
    verified: bool | None = None
    verification_reason: str | None = None
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    @property
    def free_amplitudes(self) -> int:
        """Real amplitudes the family has before any data is looked at."""
        return int(self.configurations.shape[0])

    @property
    def bns_number(self) -> str:
        return "unidentified" if self.identification is None \
            else self.identification.bns_number

    @property
    def msg_type(self) -> int | None:
        return None if self.identification is None else self.identification.msg_type

    @property
    def label(self) -> str:
        return f"{self.irrep_label}{self.direction.label}"

    def moments(self, amplitudes) -> np.ndarray:
        """The ``(N, 3)`` moment pattern of an amplitude vector."""
        a = np.asarray(amplitudes, dtype=np.float64).reshape(-1)
        if a.size != self.free_amplitudes:
            raise ValueError(
                f"{self.label} has {self.free_amplitudes} free amplitudes, got {a.size}")
        return np.tensordot(a, self.configurations, axes=(0, 0))

    def in_allowed_span(self, *, atol: float = 1e-6) -> bool:
        """Whether every pattern this family can carry is allowed by its own MSG.

        The two halves of the engine agreeing: :mod:`.modes` builds the pattern
        from the irrep, this module derives the operator list from the
        stabiliser, and the allowed-span helper derives the allowed subspace
        back from that operator list.  A wrong vector action, a wrong
        return-vector phase or a missing anti-translation each break it, and
        none of them changes any dimension count.

        Which helper depends on ``kind``, because a moment and a displacement
        are different kinds of vector: ``kind="magnetic"`` checks against
        :func:`~.operators.allowed_moment_basis`, the **axial** action
        ε·det(R)·R.  ``kind="displacive"`` checks against
        :func:`~.operators.allowed_displacement_basis`, the **polar** action
        R alone — a displacement is a real-space vector that time reversal
        does not touch and that an improper rotation does not flip the sign
        of.  Using the axial basis on a displacive candidate is exactly the
        physics error the module docstring's convention 2 warns about, and a
        dimension count cannot catch it.

        **The rule (Q22).** A stabiliser element is a **grey element**
        (i, η) — a little-group index and its own time-reversal sign — from
        ``self.direction.stabilizer``, not an operator of ``self.group``:
        ``_candidate_group`` additionally folds in the magnetic cell's own
        coset sign (:attr:`MagneticCell.translations`) when it builds that
        group, because relating one magnetic-cell atom's moment to *another*
        atom's needs it (that is what makes the whole family one consistent
        MSG) — but a single atom's *own* allowed subspace does not: it is a
        fact about ``self.parent_atoms[atom]`` and the grey element alone,
        and folding in the coset sign here was the bug (measured: it flips
        the required eigenspace of every operator uniformly for the *other*
        parent-lattice coset's copy of the very same atom, which cannot be
        right — the two copies carry the same allowed line, only their
        chosen point on it differs in sign, and :func:`_expand_configurations`
        is where that sign is applied).

        What a single atom's own check is still missing is a further,
        atom-specific phase: the little-group element {R_i|v_i} can return
        this atom to itself only via a lattice vector Δ, and the order
        parameter carries an *extra* exp(−2πi k·Δ) for that Δ — the same
        return-vector phase :mod:`.modes` computes independently, atom by
        atom and little-group element by little-group element, as
        ``SiteRepresentation.permutation.phases`` (:attr:`permutation`,
        already correct for a centred parent lattice via its own centring
        loop), and which a family's own *construction* is already built from
        (Q21 measured this directly — the construction was already right,
        even where this check was not).

        The joint requirement at atom j, for a grey element (i, η) whose
        little-group action fixes j's own parent atom
        (``permutation.permutations[i, j] == j``), is therefore
        ``phase(i, j)·η·det(R_i)·R_i·m = m`` for a moment and
        ``phase(i, j)·R_i·d = d`` for a displacement — the allowed subspace
        is the eigenvalue-1 space of that product, not of η·det(R)·R or R
        alone.  :func:`~.operators.allowed_moment_basis`/:func:`~.operators.
        allowed_displacement_basis`'s ``phases`` argument is exactly
        ``phase(i, j)``, multiplied in on top of the η the operator's own
        ``time_reversal`` carries (moment) or ignores entirely (displacement,
        which never depended on time reversal — ``phase(i, j)`` is not one,
        it is a spatial return-vector fact both kinds need).
        """
        basis_fn = (allowed_moment_basis if self.kind == "magnetic"
                    else allowed_displacement_basis)
        inverse = _exact_inverse(self.cell.basis)
        forward = [[_frac(v) for v in row] for row in self.cell.basis]
        little = self.permutation.little
        for atom in range(self.positions.shape[0]):
            parent_atom = int(self.parent_atoms[atom])
            ops: list[MagneticOperator] = []
            phases: list[int] = []
            for index, eta in self.direction.stabilizer:
                if int(self.permutation.permutations[index, parent_atom]) != parent_atom:
                    continue  # this grey element does not fix this atom's own orbit atom
                phase_c = self.permutation.phases[index, parent_atom]
                if abs(phase_c.imag) > 1e-6 or abs(abs(phase_c.real) - 1) > 1e-6:
                    raise RuntimeError(  # pragma: no cover - the module's own scope fence
                        f"permutation.phases[{index}, {parent_atom}] = {phase_c!r} is "
                        f"not ±1; this needs 2k in the reciprocal lattice (module "
                        f"docstring's scope fence)")
                integral = _rotation_in_cell(little.rotations[index], inverse, forward,
                                             label=little.triplets[index])
                ops.append(MagneticOperator.build(
                    integral, (Fraction(0), Fraction(0), Fraction(0)), eta))
                phases.append(1 if phase_c.real > 0 else -1)
            basis = basis_fn(tuple(ops), phases=tuple(phases))
            for pattern in self.configurations:
                if not in_span(basis, pattern[atom], atol=atol):
                    return False
        return True


def _rotation_in_cell(rotation, inverse, forward, *, label=None
                      ) -> tuple[tuple[int, ...], ...]:
    """A parent-cell rotation conjugated into another cell: P⁻¹·R·P, exact.

    ``inverse``/``forward`` are P⁻¹/P as ``Fraction`` matrices (``cell.basis``
    and :func:`_exact_inverse` of it).  Shared by :func:`_candidate_group`
    (whose target is the magnetic cell) and
    :meth:`MagneticCandidate.in_allowed_span` (Q22): the same conjugation,
    reused rather than re-derived, is what keeps the two from silently
    disagreeing about which cell a rotation acts in.  Raises
    ``RuntimeError`` naming the rotation when the target cell does not carry
    it to an integral matrix.
    """
    rot = [[_frac(int(v)) for v in row] for row in rotation]
    moved = [[sum(inverse[i][a] * rot[a][b] * forward[b][j]
                  for a in range(3) for b in range(3)) for j in range(3)]
             for i in range(3)]
    if any(v.denominator != 1 for row in moved for v in row):
        raise RuntimeError(
            f"the target cell does not carry the rotation {label or rotation!r} "
            f"to an integral matrix; the lattice is not invariant under it")
    return tuple(tuple(int(v) for v in row) for row in moved)


#: Guard for :func:`_close_operations`: every crystallographic (little group x
#: lattice index) case this module builds is far under this, so reaching it
#: is a bug in the seed list, not a tolerance to raise.
_CLOSURE_LIMIT = 4096


def _close_operations(seed) -> tuple[MagneticOperator, ...]:
    """The group generated by ``seed`` under :class:`~.operators.MagneticOperator`
    multiplication (Q23).

    A stabiliser's seed operators need not already be closed: composing two
    coset representatives of a nonsymmorphic little group can add a lattice
    translation that shows up only as a *product*, never as a term any single
    stabiliser-member-times-Δ can supply (the little group's own projective
    factor system carrying that translation's k-phase, Bradley & Cracknell
    1972 ch. 7) — the P4₂ 4₂-screw squaring to the ordinary 2-fold with the
    "lost" lattice translation folded back in (Q23) is exactly this.  Closing
    here, before :meth:`~.operators.MagneticGroup.from_operations`, is what
    multiplies that translation in; ``from_operations`` keeps its own closure
    check as the assertion that this succeeded.

    Order-preserving (a ``dict`` used as an ordered set, not a plain
    ``set``) for its own sake — reproducible closure steps make a failure
    easier to reproduce and debug — but no longer load-bearing for
    correctness: :meth:`~.operators.MagneticGroup.from_operations` used to
    pick "the first operation met in each coset" as its representative,
    which made a downstream consumer (``compile_magnetic_sites``) depend on
    *which* member of a coset that was (measured: shuffling this function's
    seed order with a plain ``set`` flipped the sign of some declared
    moments). ``from_operations`` now sorts the closed set canonically by
    ``(rotation, translation, time_reversal)`` before choosing
    representatives (small-fixes-20260917, item 1), so its output no longer
    depends on the order this function — or any other caller — hands it
    operations in; :func:`~.scattering._axial_matrices` also gained its own
    consistency check at the point of consumption, on top of that, rather
    than relying solely on this function's order.
    """
    closed: dict[MagneticOperator, None] = {}
    for op in seed:
        closed.setdefault(op, None)
    closed.setdefault(IDENTITY, None)
    changed = True
    while changed:
        changed = False
        for a in list(closed):
            for b in list(closed):
                product = a * b
                if product not in closed:
                    closed[product] = None
                    changed = True
                    if len(closed) > _CLOSURE_LIMIT:
                        raise RuntimeError(
                            f"operator closure passed {_CLOSURE_LIMIT} elements "
                            f"starting from {len(seed)} seeds; this is a guard, "
                            f"not a tolerance — the seed list is not generating a "
                            f"finite crystallographic group")
    return tuple(closed)


def _candidate_group(little: LittleGroup, cell: MagneticCell,
                     stabilizer: tuple[GreyElement, ...]) -> MagneticGroup:
    """Operator list of one isotropy subgroup, in the magnetic cell.

    An operation of the parent is {R_i | v_i + Δ} with Δ a lattice vector; it
    acts on the order parameter as ε·exp(−2πi k·Δ)·D_ν(R_i), so the element of
    the grey little group it corresponds to is (i, ε·ε(Δ)) and the
    time-reversal sign the operator must carry to sit in the stabiliser is
    ε = η·ε(Δ).  That is the whole translation rule: for k = 0 every ε(Δ) is
    +1 and the candidate keeps the parent's lattice, and for 2k ∈ L* with
    k ≠ 0 the coset with ε(Δ) = −1 makes an **anti-translation**, which is what
    a type IV magnetic space group is.

    This ε is the group's own, atom-independent bookkeeping and stays exactly
    this — Q22 does not change it.  It is not, by itself, the whole phase a
    *specific* atom needs: see :meth:`MagneticCandidate.in_allowed_span` for
    the atom-level return-vector phase this construction cannot carry.

    **The Q23 correction, kind-independent.** The seed set built from
    ``stabilizer`` times ``cell.translations`` is not always already closed
    under multiplication: composing two coset representatives of a
    nonsymmorphic little group can add a lattice translation that shows up
    only as a *product*, never as a term any single stabiliser-member-times-Δ
    supplies (the little group's own projective factor system, Bradley &
    Cracknell 1972 ch. 7) — the P4₂ 4₂-screw squaring to the ordinary 2-fold
    with the "lost" lattice translation folded back in is exactly this. So the
    seed set is always closed (:func:`_close_operations`) before being
    canonicalised, whichever ``kind`` this is: this is the one asymmetry
    between the two paths (a nonsymmorphic little group's factor system can
    need a lattice-translation correction regardless of kind, and only the
    magnetic path's own η bookkeeping happened to already absorb it every
    time — see :func:`_close_operations` for the measured P4₂ example).  A
    ``kind="displacive"`` stabiliser legitimately keeps *both* grey signs of
    an index that stabilises it (:func:`order_parameter_space` gives η = +1
    regardless of ε there, so a displacement's own stabiliser is always
    grey/Type-II — ``tests/test_magnetic_isotropy.py::
    test_pnma_sb_displacive_candidates_verify_true`` asserts exactly this and
    is unchanged by Q23); both signs are genuine, independent generators and
    neither is dropped.
    """
    inverse = _exact_inverse(cell.basis)
    forward = [[_frac(v) for v in row] for row in cell.basis]
    operations: dict[MagneticOperator, None] = {}
    for index, eta in stabilizer:
        integral = _rotation_in_cell(little.rotations[index], inverse, forward,
                                     label=little.triplets[index])
        base = little.translations[index]
        for shift, eps in cell.translations:
            translation = [base[i] + shift[i] for i in range(3)]
            in_cell = [sum(inverse[i][j] * translation[j] for j in range(3))
                       for i in range(3)]
            operations.setdefault(
                MagneticOperator.build(integral, in_cell, eta * eps), None)
    return MagneticGroup.from_operations(_close_operations(operations))


def grey_little_group(space_group, k, cell: MagneticCell | None = None) -> MagneticGroup:
    """G_k1', the grey little group, as an operator list in the magnetic cell.

    Built the other way round from :func:`candidates`: the group is assembled in
    the **parent's** cell — the little group's rotations with every lattice
    translation, each operation present with both time-reversal signs — and then
    carried across by :meth:`~.operators.MagneticGroup.transformed`, whose
    lattice completion supplies the translations the larger cell holds and whose
    order guard (|G| × |det P| against the source order) refuses a target cell
    that is not a cell of the group.  The two constructions agree operation for
    operation, and ``tests/test_magnetic_isotropy.py`` asserts that they do: a
    supercell is exactly where a candidate list goes quietly wrong.

    It is the **little** group and not the whole parent because the magnetic
    lattice is only invariant under the operations that fix k; the rest take the
    model to another arm of the star, and ``transformed`` says so by refusing.
    """
    sg = _irreps._resolve(space_group)
    if cell is None:
        cell = magnetic_cell(sg, k)
    little = _irreps.little_group(sg, cell.k)
    operations = []
    for index in range(little.order):
        rotation = little.rotations[index]
        translation = little.translations[index]
        for centring in _irreps._centrings(sg):
            shifted = [translation[i] + centring[i] for i in range(3)]
            for eps in (1, -1):
                operations.append(MagneticOperator.build(rotation, shifted, eps))
    grey = MagneticGroup.from_operations(operations)
    if all(eps > 0 for _, eps in cell.translations):
        return grey
    return grey.transformed(cell.inverse_transform)


def _lattice_basis(vectors) -> list[list[Fraction]]:
    """A ℤ-basis of the lattice generated by ``vectors`` and ℤ³, exactly."""
    rows = [[_frac(v) for v in vector] for vector in vectors]
    rows += [[_frac(int(i == j)) for j in range(3)] for i in range(3)]
    den = 1
    for row in rows:
        for value in row:
            den = den * value.denominator // np.gcd(den, value.denominator)
    integral = [[int(value * den) for value in row] for row in rows]
    hnf = [row for row in _irreps._row_hnf(integral) if any(row)]
    if len(hnf) != 3:  # pragma: no cover - three generators always span
        raise RuntimeError(f"the translation lattice has rank {len(hnf)}, not 3")
    return [[Fraction(value, den) for value in row] for row in hnf]


def _identify_in_a_reduced_cell(group: MagneticGroup, metric) -> MagneticSpaceGroupId:
    """Identify a group after moving it to a short primitive cell of its own lattice.

    spglib 2.7.0 identifies an *ordinary* space group from a far-from-standard
    setting and its **magnetic** twin sometimes does not: a monoclinic magnetic
    group written in the body-centred cubic cell of its cubic parent comes back
    unmatched from
    ``get_magnetic_spacegroup_type_from_symmetry`` while
    ``get_spacegroup_type_from_symmetry`` on the same rotations returns C2.  The
    remedy is a cell, not a tolerance: the unprimed translations are collected
    into a primitive basis, that basis is shortened, and the group is carried
    there by :meth:`~.operators.MagneticGroup.transformed` — which leaves the
    magnetic space-group *type*, the only thing being asked for, alone.
    """
    unprimed = [op.translation for op in group.centerings if op.time_reversal > 0]
    rows = _reduce_basis(_lattice_basis(unprimed), metric)
    columns = [[rows[j][i] for j in range(3)] for i in range(3)]
    if columns == [[Fraction(int(i == j)) for j in range(3)] for i in range(3)]:
        raise ValueError("the cell is already primitive; nothing to retry")
    spec = format_transform(_rational_inverse(columns),
                            (Fraction(0), Fraction(0), Fraction(0)))
    return identify(group.transformed(spec))


@dataclass(frozen=True, eq=False)
class CandidateSet:
    """Every candidate magnetic model for one (parent, site, k), and their classes.

    ``__str__`` prints the classic table: irrep, direction, BNS number, magnetic
    cell, free amplitudes, the amplitudes a powder can determine, absences and
    the powder-equivalence class.

    ``space_group`` is :func:`candidates`'s own resolved group object, exactly
    as :attr:`MagneticCandidate.space_group` — see that field's docstring
    (stage3 D2).
    """

    space_group: object  # gemmi.SpaceGroup | rietx.crystallography.symmetry.OperatorGroup
    site: tuple[float, float, float]
    k: KVector
    kind: str
    cell: MagneticCell
    lattice: np.ndarray
    representation: SiteRepresentation
    candidates: tuple[MagneticCandidate, ...]
    classes: tuple[tuple[int, ...], ...] = ()
    determinable: tuple[int, ...] = ()
    absences: tuple[int, ...] = ()

    def __len__(self) -> int:
        return len(self.candidates)

    def __iter__(self):
        return iter(self.candidates)

    def __getitem__(self, index):
        return self.candidates[index]

    def class_of(self, index: int) -> int | None:
        """Which powder-equivalence class a candidate is in, or None if not computed."""
        for c, members in enumerate(self.classes):
            if index in members:
                return c
        return None

    def verified_only(self) -> "CandidateSet":
        """This set with every ``verified is False`` candidate dropped (Q-21).

        A caller that wants only verified candidates — a ranking, a sweep, a
        direction lookup by label — filters here rather than re-deriving the
        same test.  A candidate with ``verified is None`` (``verify=False``
        was used to build this set) is kept: nothing has said it fails.
        ``classes``/``determinable``/``absences`` are dropped rather than
        reindexed, since they are computed by :func:`analyse` against the
        *positions* of ``self.candidates`` and would silently point at the
        wrong row once any candidate is removed; call :func:`analyse` again
        on the filtered set if those are needed.
        """
        kept = tuple(c for c in self.candidates if c.verified is not False)
        return replace(self, candidates=kept, classes=(), determinable=(), absences=())

    def __str__(self) -> str:
        # ``space_group`` is the resolved group object (stage3 D2), not a
        # bare label — ``.xhm()`` is the gemmi-shaped surface every such
        # object (gemmi.SpaceGroup and OperatorGroup alike) already exposes.
        label = self.space_group.xhm() if hasattr(self.space_group, "xhm") \
            else str(self.space_group)
        header = (f"{label}  site {tuple(round(float(v), 5) for v in self.site)}"
                  f"  k = ({', '.join(str(c) for c in self.k)})  [{self.kind}]")
        lines = [header,
                 f"magnetic cell: {self.cell.transform}"
                 f"  ({self.cell.index} parent lattice coset(s), "
                 f"{'anti-translation' if self.cell.doubled else 'no anti-translation'})",
                 ""]
        cols = ("irrep", "direction", "BNS", "type", "domains", "free",
                "determinable", "absences", "class")
        widths = [7, 14, 10, 5, 8, 5, 13, 9, 6]
        lines.append("  ".join(name.ljust(w) for name, w in zip(cols, widths)))
        for i, candidate in enumerate(self.candidates):
            klass = self.class_of(i)
            row = (candidate.irrep_label,
                   candidate.direction.label,
                   candidate.bns_number,
                   str(candidate.msg_type or "-"),
                   str(candidate.direction.conjugates),
                   str(candidate.free_amplitudes),
                   "-" if not self.determinable else str(self.determinable[i]),
                   "-" if not self.absences else str(self.absences[i]),
                   "-" if klass is None else str(klass))
            lines.append("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))
        return "\n".join(lines)


def candidates(space_group, site_xyz, k, *, kind: str = "magnetic", cell=None,
               identify_groups: bool = True, verify: bool = True) -> CandidateSet:
    """Every candidate magnetic model for a parent group, a site and a k.

    For each small irrep with a non-zero multiplicity in the site's magnetic
    representation, every order-parameter direction with a distinct stabiliser
    gives one candidate: an MSG operator list in the magnetic cell, the parent →
    magnetic transform, the irrep label and direction, and the family of moment
    patterns the direction produces.  This is the magnetic half of the
    parent + irrep + direction → structure workflow of Campbell et al. (2006),
    with time reversal in the group (Perez-Mato et al., 2015) and the
    stabiliser construction of Stokes & Hatch (1988).

    ``kind="displacive"`` gives time reversal the +1 a displacement carries and
    is here for the control it makes possible: on a magnetic order parameter it
    produces grey stabilisers, which forbid every moment.

    ``verify`` runs :meth:`MagneticCandidate.in_allowed_span` on every
    candidate — the two halves of the engine checking each other — and marks
    each one's :attr:`~MagneticCandidate.verified` and
    :attr:`~MagneticCandidate.verification_reason` with the result (Q-21).  A
    failing candidate is **not** dropped or allowed to hide the rest of its
    site's candidates behind a raised exception: it stays in the returned set,
    flagged, so a caller that wants only verified models filters on
    ``verified``.  The one case that still raises is every candidate of the
    site failing at once — nothing to fall back on, and the "this is a bug"
    case the flag alone cannot express.  Only a sweep that has already made
    the per-candidate check elsewhere should turn ``verify`` off entirely.

    Raises ``ValueError`` naming the k when 2k is not a reciprocal lattice
    vector; see the module docstring's scope fence.
    """
    if kind not in ORDER_PARAMETER_KINDS:
        raise ValueError(f"kind must be one of {ORDER_PARAMETER_KINDS}, got {kind!r}")
    sg = _irreps._resolve(space_group)
    mcell = magnetic_cell(sg, k)
    kk = mcell.k
    little = _irreps.little_group(sg, kk)
    representation = _modes.magnetic_representation(
        sg, site_xyz, kk, kind="axial" if kind == "magnetic" else "polar")
    small = _irreps.small_irreps(sg, kk)
    inverse = _fraction_inverse(mcell.basis)
    parent_lattice = (compatible_cell(sg) if cell is None
                      else np.asarray(cell, dtype=np.float64))
    lattice = magnetic_lattice(mcell, parent_lattice)

    positions: list[np.ndarray] = []
    signs: list[int] = []
    parents: list[int] = []
    for atom, position in enumerate(representation.positions):
        for shift, eps in mcell.translations:
            moved = inverse @ (position + np.array([float(c) for c in shift]))
            positions.append(moved % 1.0)
            signs.append(eps)
            parents.append(atom)
    site_positions = np.array(positions)
    sign_array = np.array(signs, dtype=np.float64)
    parent_index = np.array(parents)

    out: list[MagneticCandidate] = []
    kept: list[SmallIrrep] = []
    for irrep in small:
        if _is_conjugate_of_a_kept_irrep(irrep, kept):
            continue
        basis = _modes.basis_vectors(representation, irrep)
        if basis.multiplicity == 0:
            continue
        kept.append(irrep)
        space = order_parameter_space(basis, kind=kind)
        for direction in isotropy_directions(space):
            group = _candidate_group(little, mcell, direction.stabilizer)
            configurations = _expand_configurations(
                space, direction, inverse, sign_array, parent_index)
            # ``identification`` is the *non-raising* authority (Q-17): an
            # isotropy subgroup spglib will not name is still a group, still
            # the refinable object, and still buildable — 29 (group, k) cases
            # of the all-group sweep reach one, every one a c- or n-glide group
            # doubled along the glide's own translation.  The reduced-cell
            # retry stays: it is a *setting* remedy and often turns an unnamed
            # answer into a named one.
            found = None
            if identify_groups:
                result = _operators.identification(group, lattice=lattice)
                found = result.group_id
                if found is None:
                    try:
                        found = _identify_in_a_reduced_cell(group, lattice)
                    except IDENTIFY_REFUSALS:
                        found = None
            candidate = MagneticCandidate(
                space_group=sg, site=tuple(float(v) for v in site_xyz), k=kk,
                kind=kind, irrep_label=irrep.label, direction=direction, cell=mcell,
                group=group, identification=found,
                positions=site_positions, configurations=configurations,
                permutation=representation.permutation, parent_atoms=parent_index)
            if verify:
                ok = candidate.in_allowed_span()
                reason = None if ok else (
                    f"the moment family of {candidate.label} in {sg.xhm()!r} at "
                    f"k = {tuple(str(c) for c in kk)} leaves the allowed subspace of its "
                    f"own magnetic space group ({candidate.bns_number}). The isotropy "
                    f"subgroup and the basis vectors disagree; this is a bug, not a "
                    f"tolerance")
                candidate = replace(candidate, verified=ok, verification_reason=reason)
            out.append(candidate)
    if verify and out and all(c.verified is False for c in out):
        names = ", ".join(c.label for c in out)
        raise RuntimeError(
            f"every candidate of the site {tuple(float(v) for v in site_xyz)} in "
            f"{sg.xhm()!r} at k = {tuple(str(c) for c in kk)} ({names}) leaves the "
            f"allowed subspace of its own magnetic space group; the isotropy "
            f"subgroup and the basis vectors disagree for all of them, with "
            f"nothing left to fall back on. This is a bug, not a tolerance")
    return CandidateSet(space_group=sg,
                        site=tuple(float(v) for v in site_xyz), k=kk, kind=kind,
                        cell=mcell, lattice=lattice, representation=representation,
                        candidates=tuple(out))


def _is_conjugate_of_a_kept_irrep(irrep: SmallIrrep, kept) -> bool:
    """Whether this irrep is the complex conjugate of one already used.

    A genuinely complex irrep and its conjugate are **one** physically
    irreducible representation: the realification of either spans the same real
    subspace of moment space, so taking both would generate the same candidates
    twice and double the amplitude count.  Measured on P4 at Γ with a general
    site: S2 and S3 are a conjugate pair, each realifying to six real
    amplitudes, and 3 + 6 + 6 + 3 = 18 against 3N = 12 — the sum only closes
    when one of the pair is dropped.  Self-conjugate irreps (real characters,
    which includes every pseudoreal one) are never dropped.
    """
    chi = np.asarray(irrep.characters)
    if np.allclose(chi, np.conj(chi), atol=ISOTROPY_ATOL):
        return False
    return any(np.allclose(np.conj(np.asarray(other.characters)), chi,
                           atol=ISOTROPY_ATOL) for other in kept)


def _expand_configurations(space: OrderParameterSpace,
                           direction: OrderParameterDirection,
                           inverse: np.ndarray, signs: np.ndarray,
                           parent_index: np.ndarray) -> np.ndarray:
    """The direction's moment patterns, in the magnetic cell.

    A basis vector's pattern is stated on the parent's primitive-cell orbit; the
    atom in the lattice coset Δ carries it times exp(−2πi k·Δ) = ±1, which is
    :attr:`MagneticCell.translations`' sign, and the components are carried into
    the magnetic cell by P⁻¹ because a contravariant moment transforms like a
    position.
    """
    out = []
    for copy in range(space.copies):
        for row in direction.subspace:
            pattern = np.tensordot(row, space.configurations[copy], axes=(0, 0))
            expanded = signs[:, None] * pattern[parent_index]
            out.append(expanded @ inverse.T)
    return np.array(out, dtype=np.float64)


# --------------------------------------------------------------------------
# the cell, the reflections, and the magnetic intensity
# --------------------------------------------------------------------------

@dataclass(frozen=True, eq=False)
class ReflectionSet:
    """The reflections of one cell to a d limit, grouped into powder shells.

    ``hkl`` are the cell's own integer indices, ``q`` the Cartesian scattering
    vectors in Å⁻¹ and ``d`` the spacings.  ``shells`` groups indices with the
    same d: that grouping **is** the powder average, because a powder measures
    the sum of every reflection at one d and nothing finer.  Friedel mates are
    both present, so a shell's size is the multiplicity.
    """

    lattice: np.ndarray
    hkl: np.ndarray                 # (n, 3) int
    q: np.ndarray                   # (n, 3) float, Å⁻¹
    d: np.ndarray                   # (n,) float, Å
    shells: tuple[tuple[int, ...], ...]

    def __len__(self) -> int:
        return int(self.hkl.shape[0])

    @property
    def shell_d(self) -> np.ndarray:
        """The d of each shell, in the shells' own order."""
        return np.array([float(self.d[members[0]]) for members in self.shells])


def reflections(lattice, d_min: float) -> ReflectionSet:
    """Every reflection of ``lattice`` with d ≥ ``d_min``, in complete shells.

    The index bound is |h_i| ≤ |a_i|/d_min, which is exact — h_i = Q·a_i and
    |Q| ≤ 1/d_min — so every shell inside d_min is **complete**.  That
    completeness is what makes the domain average a constant factor rather than
    a reweighting (module docstring), so it is a correctness property and not
    an optimisation.
    """
    a = np.asarray(lattice, dtype=np.float64)
    if not np.isfinite(d_min) or d_min <= 0:
        raise ValueError(f"d_min must be a positive length in Å, got {d_min!r}")
    bounds = np.floor(np.linalg.norm(a, axis=1) / d_min + 1e-9).astype(int)
    ranges = [range(-int(b), int(b) + 1) for b in bounds]
    inverse = np.linalg.inv(a)
    rows, qs, ds = [], [], []
    for h in itertools.product(*ranges):
        if h == (0, 0, 0):
            continue
        q = inverse @ np.array(h, dtype=np.float64)
        norm = float(np.linalg.norm(q))
        if norm == 0.0 or 1.0 / norm < d_min - 1e-12:
            continue
        rows.append(h)
        qs.append(q)
        ds.append(1.0 / norm)
    order = np.argsort(-np.asarray(ds))
    hkl = np.array(rows, dtype=np.int64)[order]
    q = np.array(qs, dtype=np.float64)[order]
    d = np.asarray(ds, dtype=np.float64)[order]
    shells: list[tuple[int, ...]] = []
    start = 0
    for i in range(1, len(d) + 1):
        if i == len(d) or abs(d[i] - d[start]) > 1e-9 * d[start]:
            shells.append(tuple(range(start, i)))
            start = i
    return ReflectionSet(lattice=a, hkl=hkl, q=q, d=d, shells=tuple(shells))


def _domain_operations(candidate: MagneticCandidate,
                       little: LittleGroup) -> tuple[MagneticOperator, ...]:
    """Coset representatives of the grey little group modulo the candidate's own group.

    These are the domains: the images of the model under parent operations the
    candidate's symmetry does not contain.  Operations outside the little group
    take the model to another **arm** of the star, which is a domain too, but a
    domain related to another by a parent operation has an identical powder
    pattern — a powder average is already an average over orientations — so
    those need not be built (module docstring).
    """
    grey = _candidate_group(little, candidate.cell,
                            tuple((i, eps) for i in range(little.order)
                                  for eps in (1, -1)))
    inside = set(candidate.group.all_operations())
    reps: list[MagneticOperator] = []
    covered: set[MagneticOperator] = set()
    for op in grey.all_operations():
        if op in covered:
            continue
        reps.append(op)
        covered.update(op * s for s in inside)
    if len(reps) * len(inside) != grey.order:
        raise RuntimeError(
            f"{candidate.label} has order {len(inside)} inside a grey little group of "
            f"order {grey.order}, and the cosets do not tile it ({len(reps)} found); "
            f"the candidate is not a subgroup of the grey little group")
    return tuple(reps)


def _apply_domain(op: MagneticOperator, positions: np.ndarray,
                  configurations: np.ndarray, *, tol: float = 1e-5):
    """One domain's positions and moment patterns, reindexed onto the same atom order."""
    moved = np.array([op.act_on_site(p) for p in positions])
    action = op.moment_matrix().astype(np.float64)
    index = np.full(positions.shape[0], -1, dtype=int)
    for j in range(moved.shape[0]):
        delta = np.abs(positions - moved[j])
        hit = np.flatnonzero(np.all(np.minimum(delta, 1.0 - delta) <= tol, axis=1))
        if hit.size != 1:
            raise RuntimeError(
                f"the domain operation {op.xyz()!r} sends orbit atom {j} onto "
                f"{hit.size} atoms of the same orbit; the atom set is not invariant")
        index[j] = int(hit[0])
    out = np.zeros_like(configurations)
    out[:, index, :] = configurations @ action.T
    return out


def structure_factors(candidate: MagneticCandidate, refl: ReflectionSet, *,
                      little: LittleGroup | None = None,
                      domains: bool = True) -> np.ndarray:
    """M⊥ per domain, per free amplitude, per reflection: ``(n_dom, n_free, n_hkl, 3)``.

    M(h) = Σ_j m_j·exp(2πi h·r_j) over the magnetic cell with a **unit form
    factor**, and M⊥ = M − (M·ĥ)ĥ with ĥ the unit scattering vector in Cartesian
    coordinates (Halpern & Johnson, 1939).  The form factor is a per-species
    scalar multiplying every term of one site's sum, so it cancels from every
    ratio this module reports and is left out rather than guessed at; WP-1327's
    refinement puts it back (⟨j₀⟩ + (2/g − 1)⟨j₂⟩, ITC Vol. C).

    The result is linear in the amplitudes on purpose: the intensity is then a
    quadratic form, so "absent for every amplitude" and "how many amplitudes a
    powder determines" are exact statements about a matrix rather than a
    conclusion drawn from random draws.
    """
    lattice = refl.lattice
    if little is None:
        little = _irreps.little_group(candidate.space_group, candidate.k)
    ops = _domain_operations(candidate, little) if domains else (
        MagneticOperator.build(np.eye(3, dtype=int), (0, 0, 0), 1),)
    phase = np.exp(2j * np.pi * (refl.hkl.astype(np.float64) @ candidate.positions.T))
    unit = refl.q / np.linalg.norm(refl.q, axis=1)[:, None]
    out = np.zeros((len(ops), candidate.free_amplitudes, len(refl), 3), dtype=np.complex128)
    for o, op in enumerate(ops):
        patterns = _apply_domain(op, candidate.positions, candidate.configurations)
        for p, pattern in enumerate(patterns):
            cartesian = moment_cartesian(pattern, lattice)
            total = phase @ cartesian                      # (n_hkl, 3)
            out[o, p] = total - unit * np.sum(total * unit, axis=1)[:, None]
    return out


def powder_intensities(candidate: MagneticCandidate, amplitudes,
                       refl: ReflectionSet, *, factors: np.ndarray | None = None,
                       little: LittleGroup | None = None,
                       domains: bool = True) -> np.ndarray:
    """The powder magnetic intensity of one amplitude vector, one value per shell.

    Σ over the domains and over every reflection of the shell of |M⊥|², which is
    the multiplicity-weighted orbit average WP-1327's structure factor needs and
    the thing Shirane (1959) observed is blind to a cubic collinear structure's
    moment direction.  ``factors`` reuses a :func:`structure_factors` result.
    """
    f = structure_factors(candidate, refl, little=little,
                          domains=domains) if factors is None else factors
    a = np.asarray(amplitudes, dtype=np.float64).reshape(-1)
    total = np.tensordot(a, f, axes=(0, 1))                # (n_dom, n_hkl, 3)
    per_hkl = np.sum(np.abs(total) ** 2, axis=(0, 2))
    return np.array([float(np.sum(per_hkl[list(members)])) for members in refl.shells])


@dataclass(frozen=True, eq=False)
class AbsenceReport:
    """Which reflections a candidate can never give intensity at, whatever the amplitudes.

    ``hkl`` are the magnetic cell's indices of the absent reflections and
    ``shells`` the indices of the shells with no intensity at all.  ``rule``
    names the anti-translation rule when the candidate has one — the type IV
    absence MAGNEXT (Gallego et al., 2012) prints for such a group.
    """

    hkl: np.ndarray
    shells: tuple[int, ...]
    total: int
    rule: str

    def __len__(self) -> int:
        return int(self.hkl.shape[0])


def systematic_absences(candidate: MagneticCandidate, refl: ReflectionSet, *,
                        perpendicular: bool = True,
                        little: LittleGroup | None = None,
                        domains: bool = False) -> AbsenceReport:
    """Reflections whose intensity vanishes for every value of the free amplitudes.

    Because M⊥ is linear in the amplitudes, this is exact: a reflection is
    absent when *every* amplitude basis vector gives zero there, not when a few
    random draws happen to.  ``perpendicular=False`` tests M itself, which is
    what a symmetry-only absence rule such as MAGNEXT's (Gallego et al., 2012,
    *J. Appl. Cryst.* **45**, 1236) states; the extra reflections M⊥ kills are
    the ones where the whole moment happens to lie along Q, which is a property
    of the candidate rather than of its group.

    The rule quoted for a type IV group is derivable and is the one this module
    tests against: with an anti-translation t the moment at r + t is −m(r), so
    M(h) picks up a factor (1 − exp(2πi h·t)) and **every reflection with h·t an
    integer is magnetically absent**.
    """
    if little is None:
        little = _irreps.little_group(candidate.space_group, candidate.k)
    f = structure_factors(candidate, refl, little=little, domains=domains)
    if not perpendicular:
        phase = np.exp(2j * np.pi * (refl.hkl.astype(np.float64) @ candidate.positions.T))
        f = np.zeros_like(f)
        for p, pattern in enumerate(candidate.configurations):
            f[0, p] = phase @ moment_cartesian(pattern, refl.lattice)
    magnitude = np.max(np.abs(f), axis=(0, 1, 3))          # (n_hkl,)
    scale = float(np.max(magnitude)) if magnitude.size else 0.0
    absent = magnitude <= INTENSITY_RTOL * max(scale, 1.0)
    shells = tuple(s for s, members in enumerate(refl.shells)
                   if bool(np.all(absent[list(members)])))
    anti = [op for op in candidate.group.centerings if op.time_reversal < 0]
    rule = ("" if not anti else
            "type IV: h·t = integer is absent for the anti-translation t = "
            + ", ".join("(" + ",".join(str(c) for c in op.translation) + ")"
                        for op in anti))
    return AbsenceReport(hkl=refl.hkl[absent], shells=shells,
                         total=int(np.sum(absent)), rule=rule)


def group_absences(group: MagneticGroup, refl: ReflectionSet) -> np.ndarray:
    """Reflections a magnetic space group forbids, from the operator list alone.

    The MAGNEXT computation (Gallego, Tasci, de la Flor, Perez-Mato & Aroyo,
    2012, *J. Appl. Cryst.* **45**, 1236), derived rather than tabulated.  For
    an operation (R, t, ε) the magnetic structure factor obeys

        M(h) = ε·det(R)·R·exp(2πi h·t)·M(Rᵀh),

    so every operation with Rᵀh = h constrains M(h) to the eigenvalue-1 subspace
    of ε·det(R)·R·exp(2πi h·t); where those constraints leave only zero, the
    reflection is **magnetically absent whatever the structure**.

    That is a weaker statement than
    :func:`systematic_absences`, which knows the candidate's own site and moment
    family and therefore forbids at least as much.  The two are computed by
    different routes — a group here, a configuration there — and one containing
    the other is the check.

    Returns a boolean mask over ``refl.hkl``.
    """
    ops = group.all_operations()
    rotations = np.array([op.rotation for op in ops], dtype=np.int64)
    signs = np.array([op.time_reversal * op.determinant for op in ops], dtype=np.float64)
    shifts = np.array([[float(v) for v in op.translation] for op in ops])
    mask = np.zeros(len(refl), dtype=bool)
    for i, h in enumerate(refl.hkl):
        rows: list[np.ndarray] = []
        for g in range(len(ops)):
            if not np.array_equal(rotations[g].T @ h, h):
                continue
            phase = np.exp(2j * np.pi * float(h @ shifts[g]))
            rows.append(signs[g] * phase * rotations[g].astype(np.float64) - np.eye(3))
        if not rows:
            continue
        _, s, _ = np.linalg.svd(np.vstack(rows))
        mask[i] = bool(np.all(s > 1e-9))
    return mask


def determinable_amplitudes(candidate: MagneticCandidate, refl: ReflectionSet, *,
                            draws: int = 3, seed: int = 20260906,
                            little: LittleGroup | None = None,
                            factors: np.ndarray | None = None) -> int:
    """Rank of ∂(powder intensity)/∂(amplitudes) — the amplitudes a powder can determine.

    The deficit against :attr:`MagneticCandidate.free_amplitudes` is WP-1327's
    "undeterminable direction" column, computed rather than asserted: a flat
    direction of the intensity vector is a column no refinement can move, which
    is the shape WP-1301 gives such a parameter (held, reported as unmeasured,
    never bounded).  The rank is taken at several random amplitude points and
    the largest is kept, because a *particular* point can be more degenerate
    than the family is.
    """
    if little is None:
        little = _irreps.little_group(candidate.space_group, candidate.k)
    f = structure_factors(candidate, refl, little=little) if factors is None else factors
    rng = np.random.default_rng(seed)
    best = 0
    for _ in range(draws):
        a = rng.normal(size=candidate.free_amplitudes)
        total = np.tensordot(a, f, axes=(0, 1))            # (n_dom, n_hkl, 3)
        # dI/da_q = 2 Re Σ_dom Σ_c conj(total)·f[dom, q]
        grad = 2.0 * np.real(np.einsum("dhc,dqhc->qh", np.conj(total), f))
        rows = np.array([[float(np.sum(grad[q, list(members)]))
                          for members in refl.shells]
                         for q in range(candidate.free_amplitudes)])
        s = np.linalg.svd(rows, compute_uv=False)
        scale = float(s.max()) if s.size else 0.0
        best = max(best, int(np.sum(s > 1e-7 * max(scale, 1e-300))))
    return best


# --------------------------------------------------------------------------
# the classes a powder cannot separate
# --------------------------------------------------------------------------

def _normalised_draw(candidate: MagneticCandidate, lattice, rng) -> np.ndarray:
    """A random amplitude vector scaled to unit total Cartesian moment.

    Normalising the moment magnitude is what keeps a *scale* from ever being
    the discriminator between two candidates: a model that is another model
    times two is the same model as far as a powder pattern with a refinable
    scale factor is concerned.
    """
    a = rng.normal(size=candidate.free_amplitudes)
    moments = moment_cartesian(candidate.moments(a), lattice)
    total = float(np.sqrt(np.sum(moments ** 2)))
    if total <= 0.0:  # pragma: no cover - a zero draw has measure zero
        return a
    return a / total


def _fit_residual(target: np.ndarray, factors: np.ndarray, shells,
                  rng, *, restarts: int = 4) -> float:
    """Smallest ‖I(b) − target‖∞ a family can reach, over several starts.

    ``factors`` is that family's :func:`structure_factors`; the intensity is a
    quadratic form in b, so the fit is a small non-linear least squares with an
    exact Jacobian.  Several restarts because a quadratic-form fit has sign and
    permutation symmetries and a single start can sit on a saddle.
    """
    from scipy.optimize import least_squares

    members = [list(m) for m in shells]

    def model(b):
        total = np.tensordot(b, factors, axes=(0, 1))      # (n_dom, n_hkl, 3)
        per_hkl = np.sum(np.abs(total) ** 2, axis=(0, 2))
        return np.array([float(np.sum(per_hkl[m])) for m in members]), total

    def residual(b):
        return model(b)[0] - target

    def jacobian(b):
        total = model(b)[1]
        grad = 2.0 * np.real(np.einsum("dhc,dqhc->hq", np.conj(total), factors))
        return np.array([grad[m].sum(axis=0) for m in members])

    scale = float(np.max(np.abs(target))) or 1.0
    best = np.inf
    n = factors.shape[1]
    for _ in range(restarts):
        start = rng.normal(size=n) * np.sqrt(scale / max(n, 1))
        try:
            fit = least_squares(residual, start, jac=jacobian, method="lm",
                                xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=4000)
        except Exception:  # pragma: no cover - scipy declining a start
            continue
        best = min(best, float(np.max(np.abs(fit.fun))))
    return best / scale


def powder_equivalent(a: MagneticCandidate, b: MagneticCandidate,
                      refl: ReflectionSet, *, draws: int = 3, seed: int = 20260906,
                      rtol: float = 1e-4, restarts: int = 4,
                      little: LittleGroup | None = None) -> bool:
    """Whether a powder pattern to ``refl``'s d limit can tell two candidates apart.

    **The definition, taken here.**  A and B are *powder-equivalent* when each
    can reproduce the other's powder intensity vector: for random amplitude
    draws of A — normalised to unit total moment, so a scale is never the
    discriminator — a least-squares fit of B's amplitudes reproduces A's
    intensities at every shell to ``rtol`` of A's largest, and the same with A
    and B exchanged.  It is a relation between *families*, not between points,
    which is why both directions are needed: a family with more amplitudes can
    imitate a smaller one without the reverse being true.

    This is Shirane's rule (1959) made mechanical.  For a collinear structure in
    a cubic group the powder intensity does not depend on the moment direction,
    so the [100], [110] and [111] isotropy subgroups of one irrep come out
    equivalent, and a uniaxial parent — where the angle to c *is* measurable —
    does not.
    """
    if little is None:
        little = _irreps.little_group(a.space_group, a.k)
    fa = structure_factors(a, refl, little=little)
    fb = structure_factors(b, refl, little=little)
    rng = np.random.default_rng(seed)
    for source, factors in ((a, fb), (b, fa)):
        other = fa if factors is fb else fb
        for _ in range(draws):
            amplitudes = _normalised_draw(source, refl.lattice, rng)
            target = powder_intensities(source, amplitudes, refl, factors=other)
            if float(np.max(np.abs(target))) <= 0.0:
                continue
            if _fit_residual(target, factors, refl.shells, rng,
                             restarts=restarts) > rtol:
                return False
    return True


def equivalence_classes(candidate_set: CandidateSet, refl: ReflectionSet, *,
                        draws: int = 3, seed: int = 20260906, rtol: float = 1e-4,
                        restarts: int = 4) -> tuple[tuple[int, ...], ...]:
    """Connected components of :func:`powder_equivalent` over a candidate set.

    Members of one class are models a powder pattern to this d limit cannot
    separate; WP-1327's report names them, and M-9's workflow refines one
    representative per class rather than one per candidate.
    """
    little = _irreps.little_group(candidate_set.space_group, candidate_set.k)
    n = len(candidate_set)
    parent = list(range(n))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for i in range(n):
        for j in range(i + 1, n):
            if find(i) == find(j):
                continue
            if powder_equivalent(candidate_set[i], candidate_set[j], refl,
                                 draws=draws, seed=seed, rtol=rtol,
                                 restarts=restarts, little=little):
                parent[find(j)] = find(i)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    return tuple(tuple(members) for members in
                 sorted(groups.values(), key=lambda m: m[0]))


def analyse(candidate_set: CandidateSet, *, d_min: float = 1.5,
            draws: int = 3, seed: int = 20260906, rtol: float = 1e-4,
            restarts: int = 4) -> CandidateSet:
    """Fill in the absences, the determinable amplitudes and the equivalence classes.

    Returns a new :class:`CandidateSet` whose ``__str__`` prints the whole
    classic table.  The reflection list is the magnetic cell's own to ``d_min``,
    on the cell the set was built with.
    """
    refl = reflections(candidate_set.lattice, d_min)
    little = _irreps.little_group(candidate_set.space_group, candidate_set.k)
    determinable, absences = [], []
    for candidate in candidate_set:
        factors = structure_factors(candidate, refl, little=little)
        determinable.append(determinable_amplitudes(
            candidate, refl, draws=draws, seed=seed, little=little, factors=factors))
        absences.append(systematic_absences(candidate, refl, little=little).total)
    classes = equivalence_classes(candidate_set, refl, draws=draws, seed=seed,
                                  rtol=rtol, restarts=restarts)
    return CandidateSet(
        space_group=candidate_set.space_group, site=candidate_set.site,
        k=candidate_set.k, kind=candidate_set.kind, cell=candidate_set.cell,
        lattice=candidate_set.lattice, representation=candidate_set.representation,
        candidates=candidate_set.candidates, classes=classes,
        determinable=tuple(determinable), absences=tuple(absences))
