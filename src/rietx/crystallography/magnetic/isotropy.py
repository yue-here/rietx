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
*Acta Cryst.* **12**, 282 states the classic case — a collinear structure of
cubic **configurational** symmetry (his qualifier: the symmetry of the signed
moment arrangement, not of the chemical cell; his MnO example is cubic in the
one and rhombohedral in the other) gives a powder intensity independent of the
moment direction — and :func:`equivalence_classes` computes that rather than
asserting it.

**Public API — fixed 2026-09-06.**

::

    magnetic_cell(space_group, k)                     -> MagneticCell
    order_parameter_space(basis, *, kind="magnetic")  -> OrderParameterSpace
    isotropy_directions(space)                        -> tuple[OrderParameterDirection, ...]
    candidates(space_group, site_xyz, k, ...)         -> CandidateSet

    compatible_cell(space_group)                      -> (3, 3) row-vector lattice, A
    reflections(lattice, d_min)                       -> ReflectionSet
    structure_factors(candidate, reflections)         -> (n_domains, n_free, n_hkl, 3) complex
    gram(factors, shells)                             -> (n_shells, n_free, n_free) float
    powder_intensities(candidate, amplitudes, ...)    -> (n_shells,) float
    systematic_absences(candidate, ...)               -> AbsenceReport
    determinable_amplitudes(candidate, ...)           -> int
    powder_equivalent(a, b, ...)                      -> bool
    equivalence_classes(candidates, ...)              -> tuple[tuple[int, ...], ...]
    powder_relations(candidates, ...)                 -> tuple[PairVerdict, ...]

Scope: **k = 0 and 2k a reciprocal lattice vector**
--------------------------------------------------
The stabiliser of an order-parameter direction is a subgroup of the *grey*
little group G_k1'.  Turning it into a space group needs the lattice
translations, and a translation t acts on the order parameter (the
amplitudes of :mod:`.modes`' basis vectors, which are the coefficients of
exp(+2πi k·R)) as D({E|t}) = exp(−2πi k·t) — which is ±1, hence a
time-reversal sign, only when 2k is a reciprocal lattice vector.  For any other k (a denominator of 3 or more, or a
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
   For a **pseudoreal** irrep (Frobenius–Schur −1) the n_ν realified copies are
   not independent: the real irrep complexifies to D ⊕ D, so they pair up and
   n_ν/2 of them span the real isotypic block of n_ν·d_ν dimensions; only those
   are kept (Bradley & Cracknell, 1972, Def. 1.3.7 p. 20).
   The realification is only a representation of the same group because Γ_mag
   is real, which is exactly what 2k ∈ L* buys — the same fact the scope fence
   above rests on.

2. **Time reversal acts as −1 on a magnetic order parameter and +1 on a
   displacive one** (``kind``).  A displacement does not care about 1', so every
   displacive stabiliser contains both time-reversal signs of each operation
   and every displacive candidate is a grey group, which forbids every ordered
   moment; using that rule on a moment is a physics error a dimension count
   cannot see.  The sign that *does* matter for a displacement is ε(Δ), the
   character the lattice translation Δ of a coset carries (−1 on the
   anti-translation coset of a k ≠ 0 star): the element {R | v + Δ} fixes the
   field only when ε(Δ)·D(R) fixes it, so the child lattice of a displacive
   candidate is the *sub*lattice of the parent's that ε(Δ) = +1 selects, exactly
   as for a moment.

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
   are not the parent's.  Their Cartesian vector is Aᵀ·m in **the lattice's
   own frame** (:func:`moment_cartesian`), the frame :func:`reflections` puts
   ĥ in — never :func:`~.operators.moment_to_cartesian`'s, which rebuilds the
   cell from its six parameters in a standard orientation.  The two frames
   agree only for an axis-aligned cell, and a k ≠ 0 child cell is usually
   rotated or left-handed; M⊥ needs both vectors in one frame (issue #534).

What a powder measures, and the domains
---------------------------------------
The magnetic intensity of a reflection is |M⊥|² with
M(h) = Σ_j m_j·exp(2πi h·r_j) over the magnetic cell and M⊥ = M − (M·ĥ)ĥ
(Halpern & Johnson, 1939, *Phys. Rev.* **55**, 898, eq. (6.22) p. 910 — whose
**q** = **e**(**e**·**κ**) − **κ** is *minus* the perpendicular component; the
sign written here is Rodríguez-Carvajal's (1993) eq. (1), and only |M⊥|² enters
an unpolarised cross section, so no intensity depends on the choice), with a
unit form factor
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

Because M⊥ is linear in the real amplitudes b, a shell's powder intensity is
the quadratic form bᵀ G_s b with one real positive semi-definite matrix per
shell (:func:`gram`).  Every intensity this module evaluates — the ones
:func:`powder_intensities` returns, the Jacobian :func:`determinable_amplitudes`
ranks and the fits :func:`powder_equivalent` runs — goes through that stack,
built from :func:`structure_factors` before any fit starts, so a fit touches
n_shells matrices of n_free² and never the reflections.  It is the same sum
contracted in another order, equal to round-off, and changes no verdict's
definition.

References
----------
Shirane, G. (1959). *Acta Cryst.* **12**, 282 — the powder magnetic structure
factor and the directions a powder average cannot determine.
Halpern, O. & Johnson, M. H. (1939). *Phys. Rev.* **55**, 898 — the magnetic
interaction vector (eq. 6.22, p. 910) and the powder average ⟨q²⟩ = 2/3
(eq. 6.41, p. 911).  **Not** the axial transformation law, which that paper does
not state; for that see Gallego et al. (2012) eq. (3), p. 1239.
Gallego, S. V., Tasci, E. S., de la Flor, G., Perez-Mato, J. M. & Aroyo, M. I.
(2012). *J. Appl. Cryst.* **45**, 1236 — MAGNEXT, systematic absences of
magnetic reflections under a magnetic space group; **and eq. (3), p. 1239, the
axial transformation law** M(R**r** + **t**) = θ·det(R)·R·M(**r**) this module's
domain action uses.
Rodríguez-Carvajal, J. (1993). *Physica B* **192**, 55, eq. (1) — the sign
convention for M⊥ written above.
Vandenberghe, L. & Boyd, S. (1996). *SIAM Rev.* **38**, 49 — weak duality
for semidefinite programs, the Farkas certificate of :class:`Witness`.
Boyd, S. & Vandenberghe, L. (2004). *Convex Optimization*. Cambridge
University Press, §§ 3.1.5 and 8.1 — concavity of λ_min, and the distance to
a convex cone as a dual norm problem.
Householder, A. S. (1958). *J. ACM* **5**, 339 — the reflector behind the
basis of t̂⊥.
Peyrl, H. & Parrilo, P. A. (2008). *Theor. Comput. Sci.* **409**, 269 —
exact rational checks of semidefinite certificates.
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
from dataclasses import dataclass, replace
from fractions import Fraction

import numpy as np

from ..representation import irreps as _irreps
from ..representation import modes as _modes
from ..representation.irreps import KVector, LittleGroup, SmallIrrep, as_kvector
from ..representation.modes import IrrepBasis, PermutationRepresentation, SiteRepresentation
from ..wyckoff import _compatible_lattice
from . import operators as _operators
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
#: carries; ``"displacive"`` gives it the +1 a displacement carries (the
#: coset character ε(Δ) acts on both kinds alike)
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

#: Draws per direction on a pair no certificate settles, when the caller
#: names none (issue #565, decision 3): 12 between two irreps, where 8 % of
#: the cubic pairs that 3 draws called equivalent were refuted by a draw
#: within 12 (0.2 % at 12), and 3 inside one irrep.  On the cubic
#: ``P n -3 m:1`` at (0, 0, ½) the raise is what gives the four classes of
#: the known answer rather than two.  The 3 within an irrep is not measured
#: the same way: the 8 % was counted on cross-irrep pairs only, and the
#: reason the issue gives for 3 — two directions of one irrep are isometric
#: copies — is now the isometry certificate (:class:`Isometry`), which
#: settles the rank-1 copies of one irrep without a draw.  The 3 therefore
#: applies only to two *different* directions of one irrep, which are not
#: copies (a rank-1 direction against the (a,b) plane); 12 there would cost
#: about 4 min more on the known answer (an estimate, not a measurement).
CROSS_IRREP_DRAWS = 12
WITHIN_IRREP_DRAWS = 3

#: The isometry certificate's accept bound (issue #565, part 3): the relative
#: congruence residual max_s ‖QᵀG^B_sQ − G^A_s‖_max / max|G^A| and the
#: orthogonality deviation ‖QᵀQ − I‖₂ of the quoted Q must both be at most
#: this.  Both are printed with the verdict, since an equality certificate
#: is the direction a false answer silently drops a distinguishable model
#: in.  Measured (macOS arm64 and Linux x86-64, d_min 1.5 Å): the rank-1
#: copies of each irrep of the cubic ``P n -3 m:1`` and ``P m -3 m`` at
#: (0, 0, ½) certify at residuals ≤ 3e-14 (the 2026-09-30 spike: 163
#: certificates over six cubic sets at 9.8e-16 to 2.9e-14), while a pair
#: that is not isometric has no intertwiner at all (an empty nullspace, the
#: smallest relative singular value ≥ 7e-2), so the bound separates nothing
#: measured and only fences round-off.
ISOMETRY_RESIDUAL = 1e-12

#: The full-stack guard of a Farkas certificate (issue #565, part 3, the
#: promise made on #772).  The exact check certifies the *projected* stack;
#: on the full float stack the kernel block of M(y) is not sign-definite, so
#: no bound on the kernel residual alone makes M(y) PSD.  What follows
#: instead, for an amplitude b = Pu + Kv (live and kernel components), is
#: bᵀM(y)b ≥ ratio·Λ‖u‖² − r_K·Y·(2‖u‖‖v‖ + ‖v‖²) with ratio the quoted
#: margin, Λ = ‖PᵀM(y)P‖₂, Y = Σ_s |y_s|‖G_s‖₂ and r_K the kernel residual:
#: positive, hence a refutation of I(b) = t, for every b whose kernel
#: component is at most ρ_max = −1 + √(1 + ratio·Λ/(r_K·Y)) times its live
#: one (:func:`_kernel_amplitude_ratio`).  A certificate is issued only when
#: ρ_max is at least this, i.e. the kernel may carry as much amplitude as the
#: live directions do; at the quoted 1e-10 and the measured κ_y = Y/Λ ≤ 14
#: that is r_K ≤ 2.4e-12, 2.6 decades under :data:`INTENSITY_RTOL`.
#: Measured on the 20 kernel certificates of ``P m -3 m`` at (0, 0, ½)
#: (macOS arm64, restarts 4): ρ_max 14.9 to 143, r_K ≤ 1.5e-13.
KERNEL_AMPLITUDE_RATIO = 1.0

#: The Farkas certificate's accept floor (issue #565, decision 2): a draw is
#: certified only when the projected dual's optimum, λ_min/|λ|_max of
#: Σ_s y_s G_s on the kernel-projected stack, is at least this.  Below it no
#: certificate is issued for that draw and the restarts decide it.
#: Measured on this module's own streams at seed 20260906, d_min 1.5 Å,
#: Linux x86-64: the 49 accepted draws of the known answer (17) and of
#: ``P m -3 m`` at (0, 0, ½) (32) have optima 6.4e-10 to 2.0e-5, and the six
#: draws that ended ``sampled-not`` have −3.0e-6 and below, so the floor
#: sits 2.8 decades under the smallest accepted optimum.
FARKAS_FLOOR = 1e-12

#: The projected ratio the quoted certificate is moved inside to: the
#: min-norm point sits on the PSD boundary to rounding (ratios −4e-16 to
#: 2e-16 on the 49 draws above), where an exact check can go either way
#: between machines, so the certificate stored and checked is the nearest
#: point toward the interior with at least this ratio (or half the interior
#: anchor's, when that is lower).  Two decades above :data:`FARKAS_FLOOR`;
#: the per-certificate rounding bound (≤ 3.4e-14 measured) is more than
#: three decades below it.
FARKAS_QUOTE = 1e-10

#: A fit transfer (issue #565, item 6) whose margin μ = λ′/Γ on the target's
#: projected live stack is below this is printed as "proved on the float
#: Gram stack": the cone bound cos(ŷ, I) ≥ μ then sits within a few decades
#: of the rounding allowance ρ, and the step from the float G_s to the exact
#: ones (which no certificate here covers) can be a real share of it.  A
#: label, not a gate: the verdict rests on cos < μ − ρ either way.  Measured
#: on the 246 fit transfers of the six cubic sets (2026-09-30, both
#: machines): μ 1.7e-9 to 3.5e-4, 14 below this, the largest ρ/μ 0.22.
TRANSFER_FLOAT_STACK = 1e-8

#: The restart after which a failed fit is handed to the Farkas dual.  The
#: dual and the minimum-norm solve cost 0.16-0.45 s (medians) per certified
#: draw at 8-36 amplitudes, Linux x86-64; on a draw a later restart
#: reproduces the dual is wasted, and on a certified one it saves every
#: remaining restart.
DUAL_AFTER_RESTART = 1

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
    """Contravariant fractional moment components → Cartesian, in **the lattice's own frame**.

    m = Σᵢ mᵢ·**a**ᵢ = Aᵀ·m with A the row-vector ``lattice`` (module docstring,
    convention 5), so a row of components times the lattice.  The frame is the
    one :func:`reflections` puts q = A⁻¹·h in, and M⊥ = M − (M·ĥ)ĥ takes an
    angle between the two, which needs one frame.

    It used to go through M-5's :func:`~.operators.moment_to_cartesian`, which
    takes only the six cell *parameters* and so places the cell in the
    Cholesky frame of ``adp.cartesian_basis`` (a ∥ x, b in the xy plane).
    That frame and the lattice's differ by an orthogonal matrix, improper when
    the magnetic basis is left-handed, for every k ≠ 0 child cell that is not
    axis-aligned — the MnO-type F m -3 m (½, ½, ½) cell is rotated by 140° —
    and there M⊥ was projected against the wrong ĥ (issue #534).  An
    orthogonal map leaves a norm alone, so the magnitude convention the M-5
    route was kept for (|m| = √(mᵀGm) on unit axes,
    :func:`~.operators.moment_magnitude`) is unchanged, and ``tests/test_magnetic_isotropy.py`` pins the two equal.  The
    refinement path (:mod:`.scattering`) is unaffected: it builds Q and the
    moment from the same cell parameters, so both sit in the Cholesky frame.
    """
    a = np.asarray(lattice, dtype=np.float64)
    return np.atleast_2d(np.asarray(moments, dtype=np.float64)) @ a


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
        """The independent copies: n_ν, or n_ν/2 for a pseudoreal irrep (convention 1)."""
        return int(self.configurations.shape[0])

    @property
    def little(self) -> LittleGroup:
        return self.irrep.little


def order_parameter_space(basis: IrrepBasis, *, kind: str = "magnetic"
                          ) -> OrderParameterSpace:
    """The real order-parameter space of one irrep, with time reversal in the group.

    The grey little group is G_k1' = G_k ∪ G_k·1'.  A **magnetic** order
    parameter changes sign under 1' and a **displacive** one does not.  The
    element (g, ε) acts by ε·D_ν(g) for **both** kinds: ε is the character of
    the coset (the anti-translation of a k ≠ 0 star carries −1 on the order
    parameter, whatever the order parameter is) and for a moment it also
    absorbs the time-reversal sign.  What ``kind`` changes is which group
    :func:`candidates` builds from the stabiliser: a displacive element
    {R | v + Δ} stabilises the field when ε(Δ) = η, with either time-reversal
    sign, since a displacement ignores 1' (Howard & Stokes 1998, *Acta Cryst.*
    B54, 782).  D_ν is taken in the gauge
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
    if not real_gauge and basis.irrep.frobenius_schur == 1:
        raise RuntimeError(
            f"irrep {basis.irrep.label!r} is real (Frobenius-Schur +1) but came without a "
            f"real gauge; its realification is reducible, so the order-parameter space and "
            f"the amplitude count would both be wrong. modes._maybe_real_gauge should have "
            f"found one; this is a bug, not a tolerance")
    n_ops = matrices.shape[0]
    if real_gauge:
        small = matrices.real
        configs = vectors.real
    else:
        small = np.array([np.block([[m.real, -m.imag], [m.imag, m.real]])
                          for m in matrices])
        # m = Σ C ψ + c.c. with C = A + iB gives m = Σ (A·2Reψ − B·2Imψ)
        configs = _independent_copies(
            np.concatenate([2.0 * vectors.real, -2.0 * vectors.imag], axis=1))
    elements: list[GreyElement] = []
    stack: list[np.ndarray] = []
    for i in range(n_ops):
        for eps in (1, -1):
            elements.append((i, eps))
            stack.append(eps * small[i])
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


def _independent_copies(configs: np.ndarray) -> np.ndarray:
    """The realified copies whose moment patterns are independent, in order.

    Each realified copy spans a subspace of moment space carrying the same real
    representation, irreducible for FS = 0 and FS = −1, so a copy either adds
    its whole dimension to the span of those kept or adds nothing.  For FS = 0
    every copy adds; for a pseudoreal irrep half of them do, because the real
    irrep complexifies to D ⊕ D and the n_ν complex copies pair up.  A partial
    increment means the realified copy is reducible, and is refused.
    """
    kept: list[np.ndarray] = []
    rank = 0
    for copy in configs:
        flat = np.concatenate(kept + [copy]).reshape(-1, copy[0].size)
        s = np.linalg.svd(flat, compute_uv=False)
        new_rank = int(np.sum(s > ISOTROPY_ATOL * max(1.0, float(s.max()))))
        if new_rank == rank:
            continue
        if new_rank != rank + copy.shape[0]:
            raise RuntimeError(
                f"a realified copy adds {new_rank - rank} of its {copy.shape[0]} "
                f"dimensions to the span of the others; it is reducible, so the "
                f"order-parameter space would be wrong. This is a bug, not a tolerance")
        kept.append(copy)
        rank = new_rank
    return np.array(kept, dtype=np.float64)


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
    as grey-little-group *elements*.  ``conjugates`` is how many distinct
    stabilisers are conjugate to this one in the grey little group — the
    orientation domains within one arm of the star — which is not the domain
    count (issue #608): see :meth:`CandidateSet.domain_counts`.
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
    Hatch (1988) tabulate and Campbell et al. (2006) drive ISODISPLACE from,
    for moments and — since the coset character ε(Δ) enters both kinds alike —
    for displacements (Howard & Stokes 1998), which a ``+D``-only
    enumeration lacked: it missed every direction whose stabiliser needs an
    element acting as −D.

    With ``conjugacy`` (the default) directions related by an element of the
    grey little group are collapsed to one, and :attr:`OrderParameterDirection.
    conjugates` counts how many were: conjugate stabilisers are the same
    structure in a different **orientation**, so listing all of [100], [010]
    and [001] as candidates would put three copies of one model in the table
    and then discover that a powder cannot tell them apart.  That count is
    [G_k1′ : N(H)], the conjugate directions, and not the number of domains
    [G_k1′ : H] (issue #608): 1′ normalises every H and is in no magnetic one,
    so the time-reversed (180°) domain shares its direction's stabiliser and is
    never counted here — the count is at most half the domains, and 1 for a
    general direction.  :meth:`CandidateSet.domain_counts` gives the domains.  Setting it False gives
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
    family is fixed by every operation of ``group`` and lies in what its
    stabiliser allows, ``False`` when it is not (issue #607:
    :meth:`verification_failure` says which check failed).  A failing
    candidate still appears in the returned :class:`CandidateSet`, with ``verification_reason``
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
        """Whether every pattern this family can carry is fixed by its own MSG.

        True when :meth:`verification_failure` finds nothing; see there for
        the two checks.
        """
        return self.verification_failure(atol=atol) is None

    def verification_failure(self, *, atol: float = 1e-6) -> str | None:
        """Why this family and its operator list disagree, or ``None`` if they do not.

        The two halves of the engine checked against each other, twice.

        1. **The operator list** (issue #607): every operation of
           ``self.group`` — the object that is identified, labelled and handed
           to the supercell builder — with its rotation, translation and
           time-reversal sign, applied to every configuration
           (:func:`_apply_domain`: positions permuted, a moment carried by
           ε·det(R)·R, a displacement by R), must return that configuration
           unchanged.  This is where a missing anti-translation, a wrong
           time-reversal sign on an operator or a wrong relative sign between
           two atoms shows: before #607 nothing read ``self.group`` here, and
           dropping the anti-translation sign in :func:`_candidate_group`
           relabelled all four MnO candidates (167.108 → 166.101, 12.63 →
           12.58, 15.90 → 12.62, 2.7 → 2.4) with every one still verified.
           It tests that the group fixes the family (H ⊆ stabiliser of the
           family), not that the group is the *whole* stabiliser; the
           field-stabiliser oracle in ``tests/test_magnetic_isotropy.py`` is
           the test of equality.
        2. **The stabiliser, atom by atom** (Q22): each atom's moment lies in
           the subspace its own grey stabiliser elements allow, with the
           return-vector phase of :mod:`.modes`.  It reads
           ``self.direction.stabilizer`` and not ``self.group``, so it checks
           the configurations against the isotropy subgroup the direction was
           chosen for; check 1 checks them against the operator list built
           from it.  A wrong vector action or a wrong return-vector phase
           breaks it, and none of them changes any dimension count.

        Which helper check 2 uses depends on ``kind``, because a moment and a
        displacement are different kinds of vector: ``kind="magnetic"`` checks against
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
        vector = "moment" if self.kind == "magnetic" else "displacement"
        for operation in self.group.all_operations():
            try:
                moved = _apply_domain(operation, self.positions, self.configurations,
                                      kind=self.kind)
            except RuntimeError as exc:
                return (f"the operation {operation.xyz()!r} of {self.label}'s own "
                        f"operator list ({self.bns_number}) does not map the site's "
                        f"atoms onto themselves: {exc}")
            worst = float(np.max(np.abs(moved - self.configurations))) \
                if self.configurations.size else 0.0
            if worst > atol:
                return (f"the operation {operation.xyz()!r} of {self.label}'s own "
                        f"operator list ({self.bns_number}) does not leave its {vector} "
                        f"family invariant (largest change {worst:.3g}); the operator "
                        f"list and the configurations disagree")
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
                phase_sign = 1 if phase_c.real > 0 else -1
                # a displacive stabiliser element (i, η) reads R·d = η·phase·d
                # (the coset character ε(Δ) = η), a moment's η rides on the operator
                phases.append(phase_sign * eta if self.kind == "displacive" else phase_sign)
            basis = basis_fn(tuple(ops), phases=tuple(phases))
            for pattern in self.configurations:
                if not in_span(basis, pattern[atom], atol=atol):
                    return (f"the {vector} of atom {atom} in {self.label} leaves the "
                            f"subspace its own stabiliser elements allow (the "
                            f"direction's isotropy subgroup with the return-vector "
                            f"phase); the isotropy subgroup and the basis vectors "
                            f"disagree")
        return None


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
    1972 § 3.7 eqns (3.7.6)–(3.7.8), p. 155) — the P4₂ 4₂-screw squaring to the ordinary 2-fold with the
    "lost" lattice translation folded back in (Q23) is exactly this.  Closing
    here, before :meth:`~.operators.MagneticGroup.from_operations`, is what
    multiplies that translation in; ``from_operations`` keeps its own closure
    check as the assertion that this succeeded.

    Order-preserving (a ``dict`` used as an ordered set, not a plain
    ``set``) for its own sake — reproducible closure steps make a failure
    easier to reproduce and debug — but no longer load-bearing for
    correctness: :meth:`~.operators.MagneticGroup.from_operations` used to
    pick "the first operation met in each coset" as its representative,
    which made a downstream consumer — the site compiler of a later WP-1327
    module, not in this tree — depend on *which* member of a coset that was
    (measured: shuffling this function's seed order with a plain ``set``
    flipped the sign of some declared moments). ``from_operations`` now sorts
    the closed set canonically by ``(rotation, translation, time_reversal)``
    before choosing representatives (small-fixes-20260917, item 1), so its
    output no longer depends on the order this function — or any other caller
    — hands it operations in, which is what ``test_magnetic_operators.py``'s
    sort-stability test measures here.  That later module's own consistency
    check at the point of consumption sits on top of this and guards nothing
    in this tree.
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
                     stabilizer: tuple[GreyElement, ...],
                     kind: str = "magnetic") -> MagneticGroup:
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

    **The displacive group** (the isotropy-group fix).  A displacement is
    invariant under {R | v + Δ} when ε(Δ)·D(R) fixes it, and time reversal does
    nothing to it.  So for ``kind="displacive"`` the element (i, ε) is emitted
    for every lattice vector Δ of the parent with ε(Δ) = η, **with both
    time-reversal signs**; the coset with ε(Δ) ≠ η is dropped, which is what
    makes the child lattice a sublattice of the parent's (a pure parent
    translation {E | Δ} with ε = −1 is *not* a symmetry of the distorted
    structure).  The earlier text of this paragraph argued that a displacive
    stabiliser is "always grey" and therefore right with the parent lattice;
    grey is right, the parent lattice is not.  The groups are checked against
    the stabiliser of the candidate's own field (``tests/
    test_magnetic_isotropy.py::test_every_candidates_declared_group_is_the_
    stabiliser_of_its_own_field``).

    **The Q23 correction, kind-independent.** The seed set built from
    ``stabilizer`` times ``cell.translations`` is not always already closed
    under multiplication: composing two coset representatives of a
    nonsymmorphic little group can add a lattice translation that shows up
    only as a *product*, never as a term any single stabiliser-member-times-Δ
    supplies (the little group's own projective factor system, Bradley &
    Cracknell 1972 § 3.7 eqns (3.7.6)–(3.7.8), p. 155) — the P4₂ 4₂-screw squaring to the ordinary 2-fold
    with the "lost" lattice translation folded back in is exactly this. So the
    seed set is always closed (:func:`_close_operations`) before being
    canonicalised, whichever ``kind`` this is: this is the one asymmetry
    between the two paths (a nonsymmorphic little group's factor system can
    need a lattice-translation correction regardless of kind, and only the
    magnetic path's own η bookkeeping happened to already absorb it every
    time — see :func:`_close_operations` for the measured P4₂ example).  A
    ``kind="displacive"`` stabiliser keeps *both* time-reversal signs of each
    element it emits (a displacement is indifferent to 1', so its group is
    grey/Type-II — ``tests/test_magnetic_isotropy.py::
    test_pnma_sb_displacive_candidates_verify_true``); both signs are genuine,
    independent generators and neither is dropped.
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
            if kind == "displacive":
                # ε(Δ)·D(g_i)·v = v is the symmetry condition of the distorted
                # structure; time reversal does nothing to it, so both signs
                if eps != eta:
                    continue
                for time_reversal in (1, -1):
                    operations.setdefault(
                        MagneticOperator.build(integral, in_cell, time_reversal), None)
                continue
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


#: How a :class:`PairVerdict` was decided.  ``proved-*`` rests on a
#: certificate that holds for almost every model of the family, on the Gram
#: stack as floating point builds it; ``sampled-*`` on a number of random
#: models of it; ``unresolved`` on nothing at all.
RELATION_STATUSES = ("proved-contained", "proved-not", "sampled-contained",
                     "sampled-not", "unresolved")

#: The certificates a ``proved-*`` :class:`PairVerdict` can rest on in this
#: release: ``absence``, ``subspace``, ``isometry`` and ``span`` hold for a
#: whole family, ``farkas`` for one stored draw (its :class:`Witness`),
#: ``propagated`` carries any of them from an isometric copy (``via``),
#: ``containment`` carries a witness along a proved containment, and
#: ``transfer`` is the sign-free fit transfer of a witness to a third family
#: that reproduces it (:class:`Transfer`).
RELATION_CERTIFICATES = ("absence", "subspace", "isometry", "farkas", "propagated",
                         "span", "containment", "transfer")

#: Why an ``unresolved`` :class:`PairVerdict` was not decided: ``settled``,
#: its pair was already decided distinct by the other direction; ``joined``,
#: its two candidates were already in one class through other pairs, so no
#: draw was spent on it (the certificates still ran, and none applied).
UNRESOLVED_REASONS = ("settled", "joined")


@dataclass(frozen=True)
class Witness:
    """A Farkas certificate that one draw of ``a`` is out of ``b``'s reach, stored so it can be re-checked without the generator.

    I_s(x) = xᵀ G_s x = tr(G_s xxᵀ), so every intensity vector ``b`` can
    produce is (tr G_s X)_s for some X ⪰ 0.  A vector y with
    M(y) = Σ_s y_s G_s ⪰ 0 and y·t < 0 then proves that no X ⪰ 0, hence no
    amplitude vector of ``b``, gives t, since y·(tr G_s X)_s = tr(M(y) X) ≥ 0
    (weak duality; Vandenberghe & Boyd 1996, *SIAM Rev.* **38**, 49).
    Everything is on ``b``'s live shells, with the common kernel of ``b``'s
    stack projected out first (:func:`_live_projection`).

    * ``draw`` — 1-based index of the draw in its direction's stream.
    * ``t`` — the draw's intensity vector on every shell of the reflection
      set, as drawn (unit total moment).
    * ``live`` — the shells y is on: those ``b`` can light and the fit kept.
    * ``y`` — the quoted certificate on ``live``, normalised to y·t̂ = −1
      with t̂ the unit (weighted) target on ``live``.
    * ``weights`` — the per-shell weights the certificate was solved with,
      on every shell, or None.
    * ``kernel_dim``, ``kernel_residual`` — the common kernel's dimension
      and r_K = max_s ‖G_s K‖₂/‖G_s‖₂ on it (≤ :data:`INTENSITY_RTOL`).  The
      exact check is a proof on the *projected* stack, with the kernel taken
      as structural (every G_s annihilating it); ``kernel_residual`` records
      how far the float stack departs from that, and
      ``kernel_amplitude_ratio`` is what that departure still leaves proved
      on the full stack.
    * ``kernel_amplitude_ratio`` — ρ_max (:data:`KERNEL_AMPLITUDE_RATIO`,
      :func:`_kernel_amplitude_ratio`): on the full float stack of the live
      shells, no amplitude vector of ``b`` whose component along the kernel
      is at most ρ_max times its component along the live directions
      reproduces ``t``.  Infinite when there is no kernel or r_K = 0, where
      the full-stack claim is unconditional; at least
      :data:`KERNEL_AMPLITUDE_RATIO` on every stored witness, since a smaller
      one issues none.  On the exact stack (r_K = 0) the claim covers every
      amplitude vector; the kernel block of M(y) is not sign-definite, so no
      guard makes M(y) itself PSD on the full stack, and this is the claim
      that *does* follow.
    * ``ratio`` — λ_min/|λ|_max of M_P(y) on the projected stack, at least
      :data:`FARKAS_QUOTE` or half the interior anchor's.
    * ``rounding_bound`` — n ε + S ε κ_y with κ_y = Σ_s |y_s|‖G_s‖₂/‖M(y)‖₂:
      how far rounding in forming M(y) can move ``ratio``.  At most 3.4e-14
      on every measured case, more than three decades below
      :data:`FARKAS_QUOTE`.
    * ``exact`` — the exact LDLᵀ of M_P(y), built in rationals from the
      float y and the float projected stack (:func:`_exact_psd`): exact for
      the projected stack; the full stack is covered by
      ``kernel_amplitude_ratio`` to the amplitude bound it states.  A stored
      witness always has True: a False issues none.
    * ``d`` — (lower, upper) on the relative L2 distance from t̂ to ``b``'s
      image.  Lower: 1/‖y‖, since for every point k of the relaxed cone
      ‖t̂ − k‖·‖y‖ ≥ y·(k − t̂) ≥ 1, with equality at the minimum-norm y
      (Boyd & Vandenberghe 2004, *Convex Optimization*, § 8.1).  Upper: the
      smallest relative L2 residual ‖I(x) − t‖₂/‖t‖₂ on ``live`` among the
      restarts actually made, which is one on a certified draw, so the
      bracket is loose there.  With ``weights``, both are of the weighted
      vectors.
    * ``interior`` — the unit direction ŷ of the projected dual's maximiser
      (:func:`_farkas_dual`), the vector the fit transfer reads
      (:func:`_fit_transfer`, issue #565 item 6).  For any ŷ with
      M(ŷ) = Σ_s ŷ_s G_s ≻ 0 on the projected live stack, every intensity
      vector I in ``b``'s image, and in its relaxation, has
      ŷ·I = xᵀM(ŷ)x ≥ λ_min‖x‖² and ‖I‖ ≤ Γ‖x‖², Γ = (Σ_s‖G_s‖₂²)^½, hence
      cos(ŷ, I) ≥ λ_min/Γ: the whole of ``b``'s image lies inside one
      cone round ŷ.  The maximiser is kept rather than the quoted ``y``
      because the margin is scale-free in y (the drift of the unbounded
      dual is harmless) and the quoted point sits a step inside the PSD
      boundary by construction, where λ_min, and with it the margin, is
      four decades smaller (measured on the ``F -4 3 m`` Γ witness: 8.4e-7
      against 2.2e-10).
    * ``margin`` — μ = λ′/Γ for ``interior`` on the stack it was issued on,
      λ′ = λ_min(M(ŷ)) − n ε |λ|_max (LAPACK Users' Guide § 4.7): the cone's
      cosine bound, recomputed from the stack wherever it is read.
    """

    draw: int
    t: tuple[float, ...]
    live: tuple[int, ...]
    y: tuple[float, ...]
    weights: tuple[float, ...] | None
    kernel_dim: int
    kernel_residual: float
    kernel_amplitude_ratio: float
    ratio: float
    rounding_bound: float
    exact: bool
    d: tuple[float, float]
    interior: tuple[float, ...]
    margin: float


@dataclass(frozen=True)
class Isometry:
    """An orthogonal Q with QᵀG^B_sQ = G^A_s on every shell: ``a`` and ``b`` have the same powder image, proved.

    I_A(x) = xᵀG^A_sx = (Qx)ᵀG^B_s(Qx) = I_B(Qx) for every amplitude vector
    x, and Q is invertible, so every pattern of either family is a pattern
    of the other: the two are powder-equivalent to this d limit, for every
    model and with no draw.  Because Qᵀ = Q⁻¹ the congruence is the linear
    condition G^B_sQ = QG^A_s, so Q is found in the nullspace of the
    (S·n², n²) intertwiner operator by one SVD (:func:`_intertwiners`) and
    then checked; the proof is the two residuals below, not the nullspace
    cut (:data:`ISOMETRY_RESIDUAL`).  Orthogonality is not decoration: the
    congruence alone gives image(A) ⊆ image(B), the reverse needs Q
    invertible, and a *singular* intertwiner exists exactly when B's image
    is the larger one.  Stored so that :func:`_verify_isometry` can re-check
    the certificate against both stacks without the SVD; the stacks are in
    the canonical amplitude bases (:func:`_canonical_basis`).

    * ``q`` — Q, row by row, acting on ``a``'s amplitudes.
    * ``residual`` — max_s ‖QᵀG^B_sQ − G^A_s‖_max / max_s‖G^A_s‖_max, so
      |I_A(x) − I_B(Qx)| ≤ n_a · residual · max|G^A| · ‖x‖² on every shell
      (|xᵀΔx| ≤ n_a‖Δ‖_max‖x‖² for a max-entry norm, n_a the amplitudes of
      ``a``).
    * ``orthogonality`` — ‖QᵀQ − I‖₂.
    * ``dimension`` — the intertwiner space's dimension; 1 for the rank-1
      copies of one irrep, where Q is unique up to sign.
    * ``driver`` — the LAPACK driver that gave the nullspace: ``"gesdd"``,
      or ``"gesvd"`` where gesdd did not converge (:func:`_svd_rows`).
    """

    q: tuple[tuple[float, ...], ...]
    residual: float
    orthogonality: float
    dimension: int
    driver: str


@dataclass(frozen=True)
class Containment:
    """A matrix E with G^A_s = c·EᵀG^B_sE on every shell: every pattern of ``a`` is a pattern of ``b`` up to one scale, proved.

    I_A(x) = xᵀG^A_sx = c·(Ex)ᵀG^B_s(Ex) = c·I_B(Ex) for every amplitude
    vector x of ``a``, so ``b``'s model Ex (times √c, which the fit's free
    scale absorbs) reproduces every powder pattern of ``a``: image(A) lies
    inside the cone of image(B), and ``a`` → ``b`` is ``proved-contained``
    (certificate ``span``, issue #565 part 4).  E is *found* from the moment
    patterns (``a``'s configurations written in ``b``'s, by least squares,
    against each domain image of ``b``'s patterns in turn, because
    conjugate directions are collapsed to one candidate and a rank-1
    direction can sit inside a conjugate of the rank-2 one) and *proved* by
    the Gram congruence residual alone, at :data:`ISOMETRY_RESIDUAL`: a
    least-squares E that does not reproduce the patterns can still satisfy
    the congruence (the domain average makes the Gram stack blind to how
    the patterns sit in moment space), and then the statement
    I_A(x) = c·I_B(Ex) holds just the same.  The isometry
    (:class:`Isometry`) is the case E orthogonal, c = 1 after trace
    scaling, proved both ways; it runs first and is not re-labelled.  A
    containment is an equality-type certificate, the direction a false
    answer silently drops a distinguishable model in, so the residual is
    printed with every such verdict and :func:`_verify_containment`
    re-checks the record against both stacks.

    * ``e`` — E, row by row, ``(n_b, n_a)``: x_b = E·x_a in the canonical
      amplitude bases (:func:`_canonical_basis`).
    * ``scale`` — c = tr Σ_s G^A_s / tr Σ_s EᵀG^B_sE.
    * ``residual`` — max_s ‖G^A_s − c·EᵀG^B_sE‖_max / max_s ‖G^A_s‖_max, so
      |I_A(x) − c·I_B(Ex)| ≤ n_a · residual · max|G^A| · ‖x‖² on every shell
      (|xᵀΔx| ≤ n_a‖Δ‖_max‖x‖² for a max-entry norm, n_a the amplitudes of
      ``a``).
    * ``pattern_residual`` — ‖C_A − EᵀC_B‖/‖C_A‖ of the moment patterns E
      was fitted on (zero when ``a``'s patterns lie in ``b``'s span, as a
      rank-1 direction's do in its (a,b) plane's); diagnostic only.
    * ``domain`` — the index, in :func:`_domain_operations` order, of the
      domain operation of ``b`` whose image of ``b``'s patterns E was fitted
      against; 0 is the identity.
    """

    e: tuple[tuple[float, ...], ...]
    scale: float
    residual: float
    pattern_residual: float
    domain: int


@dataclass(frozen=True)
class Transfer:
    """The sign-free fit transfer of a :class:`Witness` to a third family ``c`` (issue #565, item 6): c ⊄ b, proved.

    With ŷ the witness's ``interior`` on ``b``'s projected live stack,
    every point of ``b``'s image and relaxation has cos(ŷ, I) ≥ λ′/Γ = μ
    (:class:`Witness`).  ``c`` was fitted to the witness draw t and reached
    it; its fitted amplitudes, kernel-projected first (x_c⊥ = PPᵀx_c on
    ``c``'s own common kernel, :func:`_common_kernel`), give the *exact*
    image point I_c = I_C(x_c⊥) of ``c``, whatever the fit's residual, and
    if cos(ŷ, Î_c) < μ − ρ that point is outside ``b``'s cone, so c ⊄ b.
    ρ = 4Sε + S√n_b ε + 2(n_c + 1) ε κ_c covers the rounding of the cosine
    (S live shells), of the summation of M(ŷ), and of the float evaluation
    of I_c, κ_c = Γ_c‖x_c⊥‖²/‖I_c‖ being its conditioning; the kernel
    projection is what keeps κ_c small — the least-squares fit leaves the
    start's component along ``c``'s kernel untouched, which changes I_c not
    at all and ‖x_c‖² by up to 1e5 (measured on the ``F m -3 m`` Γ refits,
    2026-09-30), and on the ``F -4 3 m`` Γ witness a kernel component of
    1e3 takes ρ to 8.8 μ and nothing fires.  **The sign of ŷ·I_c is never
    read**: at ‖y‖ ≥ 1e12 it is rounding (1/‖y‖ below ε), and it flipped
    between two machines on one pair; here it is +9e-16 on one machine and
    the transfer fires on the margin.  A transfer that does not fire is
    undecided, never "equal".  Every number is recomputed from the stacks
    by :func:`_fit_transfer`, which :func:`_verify_transfer` calls on the
    stored ``x``.

    * ``x`` — x_c⊥, ``c``'s kernel-projected fitted amplitudes, canonical basis.
    * ``cos`` — cos(ŷ, Î_c) on ``b``'s live shells (weighted as the witness was).
    * ``mu`` — μ = λ′/Γ, recomputed on ``b``'s projected live stack.
    * ``rho`` — the rounding allowance above.
    * ``lambda_prime``, ``gamma`` — λ′ and Γ on that stack, scaled to max 1.
    * ``kappa`` — κ_c.
    * ``n_b``, ``n_c`` — amplitudes of the projected stack of ``b`` and of ``c``.
    * ``shells`` — S, the live shells.
    * ``fit`` — ‖Î_c − t̂‖₂, how closely ``c`` reached the draw (relative).
    * ``float_stack`` — μ < :data:`TRANSFER_FLOAT_STACK`, printed as
      "proved on the float Gram stack".
    * ``kernel_dim``, ``kernel_residual`` — the dimension of ``b``'s common
      kernel and its r_K.  Where r_K > 0, ``lambda_prime``, ``gamma`` and
      ``mu`` are those of :func:`_transfer_margin`: the cone then covers
      ``b``'s amplitudes with a kernel component up to
      :data:`KERNEL_AMPLITUDE_RATIO` times the live one, not only the live
      directions (a kernel-free stack, or r_K = 0, is unconditional and
      unchanged).
    """

    x: tuple[float, ...]
    cos: float
    mu: float
    rho: float
    lambda_prime: float
    gamma: float
    kappa: float
    n_b: int
    n_c: int
    shells: int
    fit: float
    float_stack: bool
    kernel_dim: int
    kernel_residual: float


@dataclass(frozen=True)
class PairVerdict:
    """Whether candidate ``b`` can reproduce every powder pattern of candidate ``a``, and how that is known.

    One record per ordered pair of a :class:`CandidateSet`, ``a`` and ``b``
    indexing its ``candidates``; :func:`powder_relations` builds them and
    :func:`analyse` stores them as ``relations``.  A pair is
    powder-equivalent when both of its directions are contained.

    ``status`` is one of :data:`RELATION_STATUSES`:

    * ``proved-contained`` — ``a`` has no powder pattern to this d limit
      (every shell is a systematic absence), so ``b``'s zero model
      reproduces all of it (``certificate`` ``"absence"``); or ``a`` and
      ``b`` have the same image, by an orthogonal congruence of their Gram
      stacks (``"isometry"``, both directions at once, no draw made); or
      every pattern of ``a`` is a pattern of ``b`` up to one scale, by an
      injection congruence (``"span"``, this direction only, not drawn);
      or the verdict is carried from an isometric copy (``"propagated"``).
    * ``proved-not`` — no model of ``b`` reproduces almost any model of
      ``a``, for a reason that holds for the whole family, and no draw is
      made; or (``farkas``) no model of ``b`` reproduces one drawn model of
      ``a`` to ``rtol``, and ``draws`` is that draw's index
      (``certificate``, below); or carried from an isometric copy
      (``propagated``, ``draws`` 0 unless it was drawn first); or carried
      along a proved containment (``containment``) or transferred to a
      third family by the sign-free bound (``transfer``), either of which
      keeps the draws the direction had consumed.
    * ``sampled-contained`` — every one of ``draws`` random models of ``a``
      was reproduced by a fit of ``b`` to ``rtol``.  A statement about those
      draws, not about the family (:func:`powder_equivalent`, mechanism B).
    * ``sampled-not`` — a draw was not reproduced by any restart of the fit,
      and no Farkas certificate cleared the gate for it.  ``draws`` counts
      the draws made, that last one included, and ``undecided_draws`` is 1:
      a fit's failure is not a proof (mechanism A).  ``dual`` is the
      projected dual's optimum on that draw: negative means no certificate
      exists for it (the relaxation is feasible: a rank gap or a fit that
      failed).
    * ``unresolved`` — nothing decided this direction: no certificate
      applied and no draw was made, for the ``reason``
      :data:`UNRESOLVED_REASONS` names (``draws`` is 0).

    **"Proved" means proved on the Gram stack built in floating point, to
    this module's tolerances, for almost every model of** ``a`` — not of
    the exact stack, and not of every model — **or, for** ``farkas``, **for
    the one stored model of** ``a`` **its** :class:`Witness` **holds**.
    The thresholds each certificate reads are stated with it below, with
    the gap measured around each.

    ``certificate`` is one of :data:`RELATION_CERTIFICATES`, or ``None`` for
    a status that is not proved:

    * ``absence`` — ``a`` lights a shell ``b`` cannot: G_s of ``b`` is below
      :data:`INTENSITY_RTOL` of ``b``'s own largest (:func:`_dark_shells`,
      scale-free), while ``a``'s is not below ``a``'s, so ``a``'s intensity
      there is non-zero for almost every model and ``b``'s is negligible for
      every one.  Exact for a G_s identically zero.  For a silent ``a``
      (:func:`_silent`) it is the proof of containment instead.
    * ``subspace`` — the linear span of ``a``'s shell-intensity vectors is
      not inside ``b``'s.  I_s(x) = xᵀ G_s x = tr(G_s xxᵀ), and the rank-one
      xxᵀ span the symmetric matrices, so the span of a family's image is
      V = {(tr G_s X)_s : X symmetric}, the column space of the stack with
      each G_s written as a vector.  ``b``'s image lies in V_b; if V_a ⊄ V_b
      the models of ``a`` whose intensity vector falls in V_b are a proper
      algebraic subset, of measure zero, and every other one is out of
      ``b``'s reach.  Two thresholds: the rank cut at
      :data:`INTENSITY_RTOL` of the largest singular value, and the leak at
      :data:`ISOTROPY_ATOL`.  Measured on this module's cases, the kept
      relative singular values are ≥ 2.5e-2 and the dropped ones ≤ 2.5e-15,
      and in-span sines are ≤ 1.3e-14 against separating ones ≥ 0.21; a
      stack with a singular value inside (1e-12, 1e-6) of its largest has
      no gap to cut at and gives no subspace certificate
      (:func:`_intensity_span`).
    * ``farkas`` — one draw t of ``a`` is out of ``b``'s reach, by a
      vector y with Σ_s y_s G_s ⪰ 0 and y·t < 0 on ``b``'s live shells
      (:class:`Witness`, which is stored as ``witness`` and states the
      argument).  A statement about that draw, and so about ``a``'s family
      only in that it contains it: ``a`` ⊄ ``b``.  Tried on a draw whose
      first fit failed (:data:`DUAL_AFTER_RESTART`).  Thresholds: the
      common-kernel cut at :data:`INTENSITY_RTOL` of the largest eigenvalue
      of Σ_s G_s, with the kernel residual pre-screened at the same value
      (nothing is solved above it); the accept floor :data:`FARKAS_FLOOR`
      on the projected dual; the quoted point at :data:`FARKAS_QUOTE`; the
      exact LDLᵀ of the quoted point as arbiter (:func:`_exact_psd`, which
      at that margin cannot disagree with the float eigenvalue, and which
      certifies the *projected* stack, the kernel being taken as
      structural); the full-stack guard :data:`KERNEL_AMPLITUDE_RATIO`,
      tied to the quoted margin, under which the certificate holds on the
      full float stack for every amplitude of ``b`` whose kernel component
      is at most ``kernel_amplitude_ratio`` times its live one (and for
      every amplitude on the exact stack); and the ``rtol`` gate below.
      Measured at d_min 1.5 Å, general site, Linux x86-64: over 145
      families of six cubic sets, kept kernel eigenvalues ≥ 2.8e-7 of the
      largest, dropped ones ≤ 8.2e-16 and kernel residuals ≤ 2.7e-13; on
      the known answer and ``P m -3 m`` at (0, 0, ½), accepted dual optima
      6.4e-10 to 2.0e-5, refused ones on the draws that ended
      ``sampled-not`` ≤ −3.0e-6, rounding bounds ≤ 3.4e-14, and ρ_max 14.9
      to 143 on the 20 certificates against a family with a kernel.  ``d``
      is the witness's bracket on the relative L2 distance from the draw to
      ``b``'s image.
    * ``isometry`` — ``a`` and ``b`` have the same number of amplitudes and
      an orthogonal Q with QᵀG^B_sQ = G^A_s on every shell, so
      I_A(x) = I_B(Qx) and the two images coincide (:class:`Isometry`,
      stored as ``isometry`` with its residuals; both directions are
      ``proved-contained`` at once).  Thresholds: the nullspace cut at
      :data:`INTENSITY_RTOL`, which the proof does not rest on, and
      :data:`ISOMETRY_RESIDUAL` on the congruence and orthogonality
      residuals, which it does.  The rank-1 copies of one irrep are the
      measured case (residuals ≤ 3e-14); two irreps' copies have an empty
      intertwiner space and get no certificate.  Equality is the direction
      a false certificate silently drops a distinguishable model in, so the
      residual is printed with every such verdict.
    * ``propagated`` — ``a`` ≅ ``a′`` and ``b`` ≅ ``b′`` by isometry, and
      the direction ``a′`` → ``b′`` was proved; ``via`` names that pair and
      ``status``, ``d``, ``witness`` and ``dual`` are its.  Exact: the two
      images are the same sets, so every statement about one holds of the
      other, and a stored witness re-verifies against ``b``'s own stack
      (a congruence preserves M(y) ⪰ 0 and y·t).  Only a proved verdict is
      carried; a sampled one stays where it was drawn, and a direction
      with a propagated verdict is not drawn once the proof arrives
      (``draws`` 0), keeping the draws it had consumed if it was drawn first.
    * ``span`` — an (n_b × n_a) matrix E with G^A_s = c·EᵀG^B_sE on every
      shell, so I_A(x) = c·I_B(Ex) and every pattern of ``a`` is one of
      ``b`` with the amplitudes mapped and the scale absorbed
      (:class:`Containment`, stored as ``containment`` with its residual;
      a rank-1 direction inside its irrep's (a,b) plane is the measured
      case, E the embedding of the line in the plane and c = ½).  Found
      from the moment patterns, against each domain image of ``b``'s, and
      proved by the congruence residual at :data:`ISOMETRY_RESIDUAL`
      (measured ≤ 1.4e-14 on 54 containments of two cubic sets, none
      across two irreps).  The other direction is drawn as usual; a pair
      contained both ways by ``span`` is equal in image, which the isometry
      may not prove (images can coincide without an orthogonal
      congruence), and is joined by the two verdicts.
    * ``containment`` — carried along a proved containment, exact, issue
      #565 item 5: a verdict a → b that rests on a point of ``a``'s image
      outside ``b``'s cone (a ``farkas`` witness, or a ``transfer``'s I_c)
      gives a′ ⊄ b for every a ⊆ a′ (the point is a′'s too; ``witness``,
      ``d`` and ``dual`` carry whole and re-verify against ``b``), and
      a ⊄ c for every c ⊆ b (the point is outside the smaller cone; the
      witness is carried as evidence on ``b``'s stack, ``via`` naming it —
      it verifies against the b of ``via``, the stack it was issued on, not
      against the verdict's own b — and ``d`` is (lower, 1), the zero model
      bounding the distance).  ⊆ is
      read from ``proved-contained`` verdicts only, never from a sampled
      one.
    * ``transfer`` — the sign-free fit transfer, issue #565 item 6: a
      family ``c`` reproduces a witness draw of ``a`` → ``b``, and its
      exact image point I_c, formed from the kernel-projected fitted
      amplitudes, has cos(ŷ, Î_c) < μ − ρ for the witness's interior ŷ on
      ``b``'s projected live stack, so c ⊄ b (:class:`Transfer`, stored as
      ``transfer`` with every number; ``via`` names the witness's pair,
      ``witness`` is that witness, ``d`` the draw's bracket moved by the
      fit residual).  Thresholds: none beyond the stack's own
      (λ′ > 0 is the dual's floor), and the label
      :data:`TRANSFER_FLOAT_STACK` on μ.  The sign of ŷ·I_c is never read.
      Tried only where the draws said ``c`` reproduces ``a``
      (``sampled-contained`` or ``unresolved`` a → c) and c → b is not yet
      proved; what does not fire is undecided.  Measured on the
      ``F -4 3 m`` Γ seed-2 witness against S4(rank 1)#1 (macOS arm64):
      cos −4.4e-14 against μ − ρ = 8.4e-7, ρ/μ 9e-6; the same point with a
      kernel component of 1e3 added before the projection, ρ/μ 8.8 and no
      transfer; S5(rank 2)#1's own draws and those of its sub-families at
      cos ≥ 2e5 μ.

    **The two directions of proof are not equally safe.**  A false
    separation costs one extra refinement; a false containment silently
    drops a distinguishable model.  So a containment certificate needs an
    exact arbiter or a printed relative residual, and a separation
    certificate needs a measured gap between its threshold and the values
    it cuts.  The two containments in this release: the silent family,
    which is exact, and the isometry, which is gated on a tolerance and
    therefore prints its residual relative to the stack it was measured on
    (:class:`Isometry`).

    The absence and subspace certificates do not say by how much two
    patterns differ, only that they differ.  The Farkas certificate does:
    ``d`` = (lower, upper) brackets the relative L2 distance from its draw
    to ``b``'s image, lower = 1/‖y‖, upper = the best relative residual of
    the restarts made (one, on a certified draw, so the upper end is loose).

    **A family-level certificate does not read** ``rtol``.  The draws call
    a model of ``a`` reproduced when the fit of ``b`` agrees to ``rtol``
    (default 1e-4); the absence and subspace cuts are fixed.  Such a
    certificate and the draws can therefore disagree on a pair whose ``a``
    is above the cut and below ``rtol``: for absence, ``a``'s largest
    relative Gram block on the shells ``b`` is dark at; for subspace, the
    leak sine.  Measured over every ``proved-not`` pair of five sets
    (``P m -3 m`` at four sites and ``P n m a`` at one, d_min 1.5 Å), the
    smallest such margin was 4.1e-2, so at the default nothing moves.  A
    caller passing an ``rtol`` above about 4e-2 gets certificates that split
    pairs the draws would have joined.  That is the cheap direction (one
    extra refinement), and the margin is not checked against ``rtol``.

    **The Farkas certificate is the exception: it is gated on** ``rtol``.
    Over the S_live shells it is on, every model I of ``b`` has
    max_s |I_s − t_s|/max|t| ≥ ‖I_live − t_live‖₂/(√S_live·max|t|)
    ≥ d_lo·‖t_live‖₂/(√S_live·max|t|), so a certificate with
    **d_lo ≥ rtol·√S_live·max|t|/‖t_live‖₂** proves that no restart could
    reproduce the draw to ``rtol``: ``proved-not`` is then the module's own
    definition at the caller's ``rtol``, and a draw a later restart would
    reproduce can never be certified.  Below the gate the certificate is
    still a proof that the draw is out of ``b``'s exact reach; it is stored
    as ``witness`` with its ``d``, and the restarts decide the status.  With
    ``weights`` the gate reads the unweighted bound derived from the same
    certificate (:func:`_certify_draw`).

    **What is left for part 5 of issue #565:** the consistency rule and the
    split.  A transferred separation that lands inside a class union-find
    joined is named by the printed table; the class is not yet split.

    ``d``, ``witness`` and ``dual`` are set only by the draws, or carried:
    ``proved-not``/``farkas`` carries all three, and so do a
    ``propagated``, ``containment`` or ``transfer`` verdict whose source
    does; ``sampled-not`` carries ``dual`` when the dual ran on its last
    draw, and a witness below the gate when one was found;
    ``sampled-contained`` carries a witness only when a draw was certified
    below the gate and then reproduced to ``rtol``.  ``isometry`` is set
    on an ``isometry`` verdict, ``containment`` on a ``span`` one and
    ``transfer`` on a ``transfer`` one, and on a ``propagated`` or
    ``containment`` one whose source has it (the record is the source's: its
    ``x`` is in the amplitude basis of the source's c, ``via[0]`` of a
    propagated verdict, and verifies against that family's stack, not the
    copy's); ``via`` on a ``propagated``, ``containment`` or ``transfer`` one.  Everything is a
    tuple, so the record stays hashable.
    """

    a: int
    b: int
    status: str
    certificate: str | None = None
    draws: int = 0
    undecided_draws: int = 0
    reason: str | None = None
    d: tuple[float, float] | None = None
    witness: Witness | None = None
    dual: float | None = None
    isometry: Isometry | None = None
    via: tuple[int, int] | None = None
    containment: Containment | None = None
    transfer: Transfer | None = None

    @property
    def proved(self) -> bool:
        """Whether the verdict rests on a certificate rather than on draws (see the class docstring for what that proves)."""
        return self.status.startswith("proved")

    @property
    def contained(self) -> bool | None:
        """Whether ``b`` reproduces ``a``, or None if nothing decided it."""
        if self.status == "unresolved":
            return None
        return self.status.endswith("contained")


@dataclass(frozen=True, eq=False)
class CandidateSet:
    """Every candidate magnetic model for one (parent, site, k), and their classes.

    ``__str__`` prints the classic table: irrep, direction, BNS number, MSG
    type, the domain counts of :meth:`domain_counts` (within one arm of the
    star, and over all of them), free amplitudes, the amplitudes a powder can
    determine, absences and the powder-equivalence class, marked **P** when every relation that
    bounds the class is proved and **S** when one of them is sampled, followed
    by every sampled pair with its draw counts.

    ``relations`` holds one :class:`PairVerdict` per ordered pair of
    candidates, as :func:`analyse` measured it; ``classes`` are the
    connected components of its equivalent pairs.

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
    relations: tuple[PairVerdict, ...] = ()

    def __len__(self) -> int:
        return len(self.candidates)

    def __iter__(self):
        return iter(self.candidates)

    def __getitem__(self, index):
        return self.candidates[index]

    def domain_counts(self) -> tuple[tuple[int, int], ...]:
        """Per candidate, the number of domains within one arm and over the whole star.

        A domain is an image of the model under a parent operation its own group
        H does not contain, time reversal included, so the domains within one
        arm of the star of k are the cosets of H in the grey little group,
        [G_k1′ : H] — the same cosets :func:`_domain_operations` builds for the
        powder sums, counted here as an order ratio — and over the whole star
        there are [G1′ : H] = [G1′ : G_k1′]·[G_k1′ : H], the first factor being
        the number of arms (Izyumov, Naish & Ozerov, 1991).  Both are exact
        integers.  Neither enters an intensity: a powder averages over the
        domains already.

        This is not :attr:`OrderParameterDirection.conjugates`, which counts
        conjugate *directions* and leaves out the 180° (time-reversed) domain
        (issue #608): for MnF₂ 136.499 it is 1 against 2 domains, for MnO 15.90
        3 against 6 within one arm and 24 over the four arms.
        """
        if not self.candidates:
            return ()
        little = self.candidates[0].permutation.little
        grey = _candidate_group(little, self.cell,
                                tuple((i, eps) for i in range(little.order)
                                      for eps in (1, -1)),
                                ).order
        arms = len(_irreps.star(self.space_group, self.k))
        out = []
        for candidate in self.candidates:
            order = candidate.group.order
            if grey % order:
                raise RuntimeError(  # pragma: no cover - a subgroup always divides
                    f"{candidate.label} has order {order}, which does not divide the "
                    f"grey little group's {grey}; it is not a subgroup of it")
            out.append((grey // order, grey // order * arms))
        return tuple(out)

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
        ``classes``/``determinable``/``absences``/``relations`` are dropped
        rather than reindexed, since they are computed by :func:`analyse`
        against the *positions* of ``self.candidates`` and would silently
        point at the wrong row once any candidate is removed; call
        :func:`analyse` again on the filtered set if those are needed.
        """
        kept = tuple(c for c in self.candidates if c.verified is not False)
        return replace(self, candidates=kept, classes=(), determinable=(), absences=(),
                       relations=())

    def _class_proved(self, index: int) -> bool | None:
        """Whether a class's boundary is proved, or None if :func:`analyse` has not run.

        True when every pair inside class ``index`` is proved contained both
        ways and every pair between it and another class has a direction
        proved not contained; one sampled or unresolved relation on either
        side makes it False.  Issue #565's part 5 changes what ``classes``
        means, and this rule, the ``__str__`` legend and the ``classes``
        docstring are to be rewritten there together.
        """
        if not self.relations:
            return None
        members = set(self.classes[index])
        verdicts: dict[tuple[int, int], PairVerdict] = {
            (v.a, v.b): v for v in self.relations}
        for i in members:
            for j in range(len(self.candidates)):
                if j == i:
                    continue
                there, back = verdicts[(i, j)], verdicts[(j, i)]
                if j in members:
                    if not (there.status == back.status == "proved-contained"):
                        return False
                elif "proved-not" not in (there.status, back.status):
                    return False
        return True

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
        cols = ("irrep", "direction", "BNS", "type", "domains/arm", "domains",
                "free", "determinable", "absences", "class")
        widths = [7, 14, 10, 5, 11, 8, 5, 13, 9, 6]
        domains = self.domain_counts()
        lines.append("  ".join(name.ljust(w) for name, w in zip(cols, widths)))
        marks = [self._class_proved(c) for c in range(len(self.classes))]
        for i, candidate in enumerate(self.candidates):
            klass = self.class_of(i)
            mark = "" if klass is None or marks[klass] is None else \
                (" P" if marks[klass] else " S")
            row = (candidate.irrep_label,
                   candidate.direction.label,
                   candidate.bns_number,
                   str(candidate.msg_type or "-"),
                   str(domains[i][0]),
                   str(domains[i][1]),
                   str(candidate.free_amplitudes),
                   "-" if not self.determinable else str(self.determinable[i]),
                   "-" if not self.absences else str(self.absences[i]),
                   "-" if klass is None else f"{klass}{mark}")
            lines.append("  ".join(str(v).ljust(w) for v, w in zip(row, widths)))
        arms = len(_irreps.star(self.space_group, self.k))
        lines.append(f"domains/arm: [G_k1' : H], the domains within one arm of the star "
                     f"of k; domains: over all {arms} arm(s)")
        if self.relations:
            lines.extend(self._relation_lines())
        return "\n".join(lines)

    def _separation_lines(self) -> list[str]:
        """Every isometry and containment with its residual, every Farkas certificate with its d bracket and what it was carried or transferred to, then the classes that hold a proved separation."""
        label = [c.label for c in self.candidates]
        isometric = [v for v in self.relations if v.certificate == "isometry" and v.a < v.b]
        spans = [v for v in self.relations if v.certificate == "span"]
        proved = [v for v in self.relations if v.certificate == "farkas"]
        carried = [v for v in self.relations
                   if v.certificate == "propagated" and v.status == "proved-not"]
        contained = [v for v in self.relations if v.certificate == "containment"]
        transferred = [v for v in self.relations if v.certificate == "transfer"]
        below = [v for v in self.relations if v.certificate is None and v.witness is not None]
        lines = []
        if isometric:
            lines.append("proved equal (isometry), congruence residual:")
            lines += [f"  {label[v.a]} ≅ {label[v.b]}  residual {v.isometry.residual:.1e}"
                      for v in isometric]
        if spans:
            lines.append("proved contained (span), every pattern of the first is one of the "
                         "second up to a scale, congruence residual:")
            lines += [f"  {label[v.a]} ⊆ {label[v.b]}  residual {v.containment.residual:.1e}"
                      for v in spans]
        if proved:
            lines.append("proved separations (farkas), d ∈ [1/‖y‖, best fit residual]:")
            lines += [f"  {label[v.a]} ⊄ {label[v.b]}  d ∈ [{v.d[0]:.2g}, {v.d[1]:.2g}]"
                      f"  draw {v.draws}" for v in proved]
        if carried:
            lines.append("proved separations carried by isometry (propagated):")
            lines += [f"  {label[v.a]} ⊄ {label[v.b]}  via {label[v.via[0]]} ⊄ {label[v.via[1]]}"
                      + (f"  d ∈ [{v.d[0]:.2g}, {v.d[1]:.2g}]" if v.d is not None else "")
                      for v in carried]
        if contained:
            lines.append("proved separations carried by containment (containment):")
            lines += [f"  {label[v.a]} ⊄ {label[v.b]}  via {label[v.via[0]]} ⊄ {label[v.via[1]]}"
                      + (f"  d ∈ [{v.d[0]:.2g}, {v.d[1]:.2g}]" if v.d is not None else "")
                      for v in contained]
        if transferred:
            lines.append("proved separations by fit transfer (transfer), cos(ŷ, I_c) < μ − ρ:")
            lines += [f"  {label[v.a]} ⊄ {label[v.b]}  via {label[v.via[0]]} ⊄ {label[v.via[1]]}"
                      f"  cos {v.transfer.cos:+.1e} < {v.transfer.mu - v.transfer.rho:.1e}"
                      + (f"  d ∈ [{v.d[0]:.2g}, {v.d[1]:.2g}]" if v.d is not None else "")
                      + ("  proved on the float Gram stack" if v.transfer.float_stack else "")
                      for v in transferred]
        if below:
            lines.append("certificates below the rtol gate (the draws decide), d ∈ [1/‖y‖, best fit residual]:")
            lines += [f"  {label[v.a]} ⊄ {label[v.b]}  d ∈ [{v.d[0]:.2g}, {v.d[1]:.2g}]"
                      f"  {v.status}" for v in below]
        holding = [c for c, members in enumerate(self.classes)
                   if any(v.status == "proved-not" and v.a in members and v.b in members
                          for v in self.relations)]
        if holding:
            lines.append("classes holding a proved separation (part 5 of issue #565 splits them): "
                         + ", ".join(str(c) for c in holding))
        return lines

    def _relation_lines(self) -> list[str]:
        """The pair counts by provenance, then every sampled pair with its draws."""
        verdicts = {(v.a, v.b): v for v in self.relations}
        n = len(self.candidates)
        pairs = [(verdicts[(i, j)], verdicts[(j, i)])
                 for i in range(n) for j in range(i + 1, n)]
        proved = [p for p in pairs if any(v.status == "proved-not" for v in p)
                  or all(v.status == "proved-contained" for v in p)]
        sampled = [p for p in pairs if p not in proved
                   and any(v.status.startswith("sampled") for v in p)]
        untested = len(pairs) - len(proved) - len(sampled)
        # a pair is counted once, under the first certificate that settles it
        first = [next((v.certificate for v in p if v.status == "proved-not"), p[0].certificate)
                 for p in proved]
        by = {c: first.count(c) for c in RELATION_CERTIFICATES}
        lines = ["", f"pairs: {len(pairs)}; proved {len(proved)} ("
                 + ", ".join(f"{c} {by[c]}" for c in RELATION_CERTIFICATES)
                 + f"); sampled {len(sampled)}; joined, not drawn {untested}"]
        lines.append("class P: every relation bounding the class is proved; "
                     "S: one rests on draws or on nothing")
        lines.extend(self._separation_lines())
        if sampled:
            lines.append("sampled pairs, n = draws a → b, b → a:")
        for there, back in sampled:
            equal = there.contained and back.contained
            counts = ", ".join(
                "-" if v.status == "unresolved" else
                f"{v.draws}" + (f" ({v.undecided_draws} not reproduced)"
                                if v.undecided_draws else "")
                + (f" ({v.certificate})" if v.proved else "")
                for v in (there, back))
            lines.append(f"  {self.candidates[there.a].label} {'~' if equal else '|'} "
                         f"{self.candidates[there.b].label}  "
                         f"{'equal' if equal else 'distinct'}  n = {counts}")
        return lines


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

    ``kind="displacive"`` builds the isotropy group of a *displacement* field:
    time reversal acts as +1, so the group is grey, and its lattice is the
    sublattice of the parent's on which the coset character ε(Δ) is +1 (the
    same sublattice as a moment's, but with both time-reversal signs).  Its
    consumers are :func:`magnetic_supercell` and the structural-distortion
    work; on a magnetic order parameter it is also the control that produces
    grey stabilisers, which forbid every moment.  Before the isotropy-group fix
    the displacive group carried the parent translation as a pure translation
    at every k ≠ 0, lacked the operations needing the anti-translation, and the
    enumeration missed rank-2 directions.

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
            group = _candidate_group(little, mcell, direction.stabilizer, kind=kind)
            configurations = _expand_configurations(
                space, direction, inverse, sign_array, parent_index)
            # ``identification`` is the *non-raising* authority (Q-17): an
            # isotropy subgroup spglib will not name is still a group, still
            # the refinable object, and still buildable.  29 (group, k) cases
            # of the all-group sweep reached one on spglib 2.7.0, and none
            # does on 2.8.0 (``MagneticIdentification``).  The reduced-cell
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
                failure = candidate.verification_failure()
                reason = None if failure is None else (
                    f"{candidate.label} in {sg.xhm()!r} at k = "
                    f"{tuple(str(c) for c in kk)}: {failure}. This is a bug, not a "
                    f"tolerance")
                candidate = replace(candidate, verified=failure is None,
                                    verification_reason=reason)
            out.append(candidate)
    if verify and out and all(c.verified is False for c in out):
        names = ", ".join(c.label for c in out)
        raise RuntimeError(
            f"every candidate of the site {tuple(float(v) for v in site_xyz)} in "
            f"{sg.xhm()!r} at k = {tuple(str(c) for c in kk)} ({names}) fails "
            f"verification — its family is not fixed by its own operator list, or "
            f"leaves what its stabiliser allows — with nothing left to fall back on "
            f"(first: {out[0].verification_reason}). This is a bug, not a tolerance")
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

    A ``d_min`` past the longest cell edge admits nothing, and the empty set is
    shaped ``(0, 3)`` — ``np.array([], dtype=np.int64)`` is ``(0,)``, which the
    next consumer dies on inside numpy rather than at a name (Yue's review of
    #389 §4).  Whether an empty set is *usable* is the consumer's question:
    :func:`analyse` refuses it, quoting the ``d_min`` and the cell.
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
    hkl = np.array(rows, dtype=np.int64).reshape(-1, 3)[order]
    q = np.array(qs, dtype=np.float64).reshape(-1, 3)[order]
    d = np.asarray(ds, dtype=np.float64).reshape(-1)[order]
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
                  configurations: np.ndarray, *, kind: str = "magnetic",
                  tol: float = 1e-5):
    """One domain's positions and patterns, reindexed onto the same atom order.

    ``kind`` decides the action, and the two are genuinely different matrices:
    a moment is an **axial** vector and transforms by ε·det(R)·R (Gallego et
    al., 2012, eq. (3), p. 1239), a displacement is a **polar** one and
    transforms by plain
    R — no determinant, and no time-reversal sign, because time reversal does
    not move an atom.  They differ by det(R)·ε, so an improper operation is
    exactly where using the wrong one is invisible in magnitude and wrong in
    sign: on a displacive ``P n m a`` (0, 0, ½) candidate the inversion
    ``-x,-y,-z,+1`` needs diag(−1, −1, −1) and the axial matrix gives
    diag(+1, +1, +1), while the other domain operation ``-x,y+1/2,-z,+1`` is
    unaffected — so the two images stopped carrying consistent relative signs
    (Yue's review of #389 §3).  This is the physics
    :func:`~.operators.allowed_displacement_basis` was added in this WP to get
    right on the other half of the engine.
    """
    if kind not in ORDER_PARAMETER_KINDS:
        raise ValueError(f"kind must be one of {ORDER_PARAMETER_KINDS}, got {kind!r}")
    moved = np.array([op.act_on_site(p) for p in positions])
    action = (op.moment_matrix() if kind == "magnetic" else op.matrix).astype(np.float64)
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

    **Magnetic candidates only**, and a ``kind="displacive"`` one is refused by
    name (Yue's review of #389 §3).  Every quantity here is magnetic neutron
    intensity: the moments are taken to Cartesian μ_B, the perpendicular
    projection is Halpern & Johnson's magnetic cross-section geometry, and a
    magnetic form factor is the thing deliberately set to one.  A *displacement*
    reaches a nuclear reflection through the scalar h·u, not through a
    perpendicular-projected vector, so the whole expression — and with it
    :func:`powder_intensities`, :func:`systematic_absences`,
    :func:`determinable_amplitudes`, :func:`powder_equivalent` and
    :func:`analyse`, which all route through here — would be a plausible number
    that means nothing.  Displacive candidates exist for the control described
    at :func:`candidates` and for WP-1327's displacive half to build on; the
    intensity of one is that WP's to write.
    """
    if candidate.kind != "magnetic":
        raise ValueError(
            f"structure_factors computes magnetic neutron intensity (M⊥, Halpern & "
            f"Johnson 1939) and {candidate.label!r} is a {candidate.kind!r} candidate: "
            f"a displacement reaches a reflection through h·u, not through a "
            f"perpendicular-projected moment, so this number would be meaningless")
    lattice = refl.lattice
    if little is None:
        little = _irreps.little_group(candidate.space_group, candidate.k)
    ops = _domain_operations(candidate, little) if domains else (
        MagneticOperator.build(np.eye(3, dtype=int), (0, 0, 0), 1),)
    phase = np.exp(2j * np.pi * (refl.hkl.astype(np.float64) @ candidate.positions.T))
    unit = refl.q / np.linalg.norm(refl.q, axis=1)[:, None]
    out = np.zeros((len(ops), candidate.free_amplitudes, len(refl), 3), dtype=np.complex128)
    for o, op in enumerate(ops):
        patterns = _apply_domain(op, candidate.positions, candidate.configurations,
                                 kind=candidate.kind)
        for p, pattern in enumerate(patterns):
            cartesian = moment_cartesian(pattern, lattice)
            total = phase @ cartesian                      # (n_hkl, 3)
            out[o, p] = total - unit * np.sum(total * unit, axis=1)[:, None]
    return out


def gram(factors: np.ndarray, shells) -> np.ndarray:
    """One real PSD matrix per shell, ``(n_shells, n_free, n_free)``: I_s(b) = bᵀ G_s b.

    With f the :func:`structure_factors` tensor, the powder intensity of shell s
    is Σ_{dom, h∈s, c} |Σ_q b_q f[dom, q, h, c]|², and expanding the square
    gives G_s[q, r] = Re Σ_{dom, h∈s, c} conj(f[dom, q, h, c])·f[dom, r, h, c]
    — real because b is real, symmetric and positive semi-definite because it
    is a sum of outer products.  That is an exact reformulation, not an
    approximation: the tensor path contracts the same sums in another order,
    and the two agree to round-off (``tests/test_magnetic_isotropy.py`` holds
    them to 1e-12 on the module's cases).  What it buys is that the tensor is
    contracted **once** per candidate: an evaluation is then n_shells matrix
    products of n_free², the gradient is 2·G_s·b, and nothing of size n_hkl is
    touched inside a fit (a cubic ``P n -3 m:1`` candidate at d_min = 1.5 Å:
    an (8, 36, 320, 3) complex tensor against 21 matrices of 36 × 36).
    """
    f = np.asarray(factors)
    n = f.shape[1]
    out = np.empty((len(shells), n, n), dtype=np.float64)
    for s, members in enumerate(shells):
        block = np.moveaxis(f[:, :, list(members), :], 1, 0).reshape(n, -1)
        g = block.real @ block.real.T + block.imag @ block.imag.T
        out[s] = 0.5 * (g + g.T)
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
    Evaluated as the quadratic form bᵀ G_s b of :func:`gram`.
    """
    f = structure_factors(candidate, refl, little=little,
                          domains=domains) if factors is None else factors
    a = np.asarray(amplitudes, dtype=np.float64).reshape(-1)
    return (gram(f, refl.shells) @ a) @ a


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
    grams = gram(f, refl.shells)
    rng = np.random.default_rng(seed)
    best = 0
    for _ in range(draws):
        a = rng.normal(size=candidate.free_amplitudes)
        rows = 2.0 * (grams @ a).T                         # dI_s/da_q = 2 (G_s a)_q
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


def _canonical_basis(candidate: MagneticCandidate) -> MagneticCandidate:
    """The candidate with its amplitude basis replaced by one fixed by the span alone.

    :attr:`MagneticCandidate.configurations` spans the family's moment
    patterns, but for a multi-copy or multi-dimensional family the basis
    *within* that span is whatever the linear algebra that built it returned,
    and two LAPACKs return two bases an orthogonal rotation apart (issue #455:
    span projectors agree to 1.5e-15 between Accelerate and OpenBLAS, basis
    elements differ by up to 1.4).  :func:`powder_equivalent` draws amplitudes
    in that basis, so one seeded stream meant different moment patterns on the
    two machines.  Here the flattened patterns are reduced to row echelon form
    with unit pivots — unique for a given row space, so the input basis no
    longer matters — and then Gram-Schmidt orthonormalised in that order with
    each row's component along its own echelon row positive, the treatment
    :func:`_projector_rows` gives an order-parameter direction's subspace.
    The family is unchanged; only which draw a seed picks is.
    """
    n = candidate.free_amplitudes
    if n == 0:
        return candidate
    flat = candidate.configurations.reshape(n, -1)
    # an orthonormal basis of the row space first, so the echelon form's
    # pivot tolerance is on a unit scale whatever the input's
    _, s, vt = np.linalg.svd(flat, full_matrices=False)
    rank = int(np.sum(s > ISOTROPY_ATOL * max(float(s.max()), 1e-300)))
    rows = _rref(vt[:rank])
    q, r = np.linalg.qr(rows.T)
    q = q * np.where(np.diag(r) < 0.0, -1.0, 1.0)
    return replace(candidate, configurations=q.T.reshape(
        (rows.shape[0],) + candidate.configurations.shape[1:]))


def _dark_shells(grams: np.ndarray, *, floor: float = 1.0) -> np.ndarray:
    """The shells a family can never light: G_s below :data:`INTENSITY_RTOL` of the stack's largest.

    The largest is taken as at least ``floor``.  :func:`_fit_residual` uses
    the default 1.0, an absolute floor it has always had; the certificates
    use ``floor=1e-300`` (:func:`_certificate_dark`), which makes the test
    scale-free, as every other comparison in this module is.  The two
    differ only on a family whose whole stack is below 1 and that is not
    silent (|F|max above :data:`INTENSITY_RTOL`, :func:`_silent`): the fit
    counts every one of its shells dark, and the certificate compares its
    shells with each other.  That window is not empty: a site 10⁻⁴ off a
    special position of ``P m -3 m`` puts 21 of its 28 families in it, with
    stack maxima from 1e-11 to 3e-3.  There a draw of the family is still
    tested by the fit, which reports it not reproduced by the floor: the
    fit's floor can cost a sampled verdict there, and a proved one comes
    from the scale-free test alone.
    """
    size = np.max(np.abs(grams), axis=(1, 2), initial=0.0)
    return size <= INTENSITY_RTOL * max(float(np.max(size, initial=0.0)), floor)


def _certificate_dark(grams: np.ndarray, silent: bool) -> np.ndarray:
    """The dark shells the absence certificate reads: scale-free, and every shell of a silent family."""
    if silent:
        return np.ones(grams.shape[0], dtype=bool)
    return _dark_shells(grams, floor=1e-300)


def _intensity_span(grams: np.ndarray) -> np.ndarray | None:
    """Orthonormal columns spanning V = {(tr G_s X)_s : X symmetric}, the span of a family's image.

    Each G_s is written as its upper triangle with the off-diagonal entries
    scaled by √2, which makes X ↦ (tr G_s X)_s an inner product with the same
    vector, so V is the column space of that (n_shells, n(n+1)/2) matrix;
    its rank is taken on :data:`INTENSITY_RTOL` of the largest singular
    value, the tolerance an undeterminable amplitude is taken on.

    None when a relative singular value lies inside (1e-12, 1e-6), three
    decades either side of that cut: the rank is then a choice of the
    tolerance, not a property of the stack, and :func:`_certify` gives no
    subspace certificate on it, so the pair goes to the draws.  On the
    module's measured cases the kept values are ≥ 2.5e-2 and the dropped
    ones ≤ 2.5e-15, so no case there reaches this.
    """
    n = grams.shape[1]
    upper = np.triu_indices(n)
    weight = np.where(upper[0] == upper[1], 1.0, np.sqrt(2.0))
    rows = grams[:, upper[0], upper[1]] * weight
    if rows.size == 0:
        return np.zeros((grams.shape[0], 0))
    u, s, _ = np.linalg.svd(rows, full_matrices=False)
    relative = s / max(float(s.max()), 1e-300)
    if np.any((relative > _SPAN_GAP[0]) & (relative < _SPAN_GAP[1])):
        return None
    rank = int(np.sum(relative > INTENSITY_RTOL))
    return u[:, :rank]


#: The relative singular values :func:`_intensity_span` must have none of.
_SPAN_GAP = (1e-12, 1e-6)


def _span_leak(span_a: np.ndarray, span_b: np.ndarray) -> float:
    """The largest sine between a direction of V_a and V_b; 0 when V_a ⊆ V_b."""
    if span_a.shape[1] == 0:
        return 0.0
    rest = span_a - span_b @ (span_b.T @ span_a)
    return float(np.linalg.norm(rest, 2))


def _certify(a: int, b: int, dark: list[np.ndarray], spans: list[np.ndarray],
             silent: list[bool]) -> PairVerdict | None:
    """The proved verdict on ``a`` → ``b`` from the family-level certificates, or None.

    In order: ``a`` with no pattern at all is contained in anything
    (absence); ``a`` lighting a shell ``b`` is dark at is not (absence);
    V_a ⊄ V_b is not (subspace), unless either span has no gap to be cut
    at (None).  ``dark`` is :func:`_certificate_dark`'s.
    :class:`PairVerdict` states each argument.
    """
    if silent[a]:
        return PairVerdict(a, b, "proved-contained", "absence")
    if bool(np.any(dark[b] & ~dark[a])):
        return PairVerdict(a, b, "proved-not", "absence")
    if spans[a] is not None and spans[b] is not None \
            and _span_leak(spans[a], spans[b]) > ISOTROPY_ATOL:
        return PairVerdict(a, b, "proved-not", "subspace")
    return None


# --------------------------------------------------------------------------
# the isometry certificate (issue #565, part 3)

def _svd_rows(rows: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
    """Singular values and right singular vectors of ``rows``, (s, vt, driver): gesdd, and gesvd where gesdd does not converge.

    numpy's divide-and-conquer driver (gesdd) failed to converge on the
    7290 × 729 intertwiner operator of two ``F m -3 m`` Γ families in the
    2026-09-30 sweep; LAPACK's QR-iteration driver (gesvd), the same
    decomposition by another route, did not.  The driver that answered is
    recorded on the certificate (:attr:`Isometry.driver`).
    """
    try:
        _, s, vt = np.linalg.svd(rows, full_matrices=False)
        return s, vt, "gesdd"
    except np.linalg.LinAlgError:
        from scipy.linalg import svd

        _, s, vt = svd(rows, full_matrices=False, lapack_driver="gesvd")
        return s, vt, "gesvd"


def _spectra_agree(ga: np.ndarray, gb: np.ndarray) -> bool:
    """Whether every shell's eigenvalues agree to :data:`INTENSITY_RTOL` of max|G^A|: necessary for a congruence, and cheap.

    An orthogonal congruence is a similarity, so it preserves each shell's
    spectrum; by Weyl's inequality a congruence with residual r moves no
    eigenvalue by more than n·r·max|G^A|, which at :data:`ISOMETRY_RESIDUAL`
    is three decades under this cut for any n this module meets.  A pair
    that fails here gets no SVD; one that passes is not yet proved.
    """
    scale = max(float(np.max(np.abs(ga))), 1e-300)
    for a, b in zip(ga, gb):
        if float(np.max(np.abs(np.linalg.eigvalsh(a) - np.linalg.eigvalsh(b)))) > INTENSITY_RTOL * scale:
            return False
    return True


def _intertwiners(ga: np.ndarray, gb: np.ndarray) -> tuple[np.ndarray, str]:
    """An orthonormal basis of {Q : G^B_sQ = QG^A_s for every s}, as (d, n, n), and the SVD driver that gave it.

    In column-major vec, vec(G^B_sQ − QG^A_s) = (I ⊗ G^B_s − G^A_sᵀ ⊗ I)·vec(Q),
    so the intertwiner space is the nullspace of that (S·n², n²) operator,
    cut at :data:`INTENSITY_RTOL` of its largest singular value.  The
    stacks arrive scaled by :func:`_isometry`, so the cut is scale-free;
    the proof never rests on it (:class:`Isometry`).  The operator holds
    S·n⁴ doubles (282 MB at S = 21, n = 36), the largest array this module
    builds.
    """
    n = ga.shape[1]
    eye = np.eye(n)
    rows = np.concatenate([np.kron(eye, gb[s]) - np.kron(ga[s].T, eye) for s in range(ga.shape[0])])
    s, vt, driver = _svd_rows(rows)
    rank = int(np.sum(s > INTENSITY_RTOL * max(float(s[0]), 1e-300)))
    null = vt[rank:]
    if null.shape[0] == 0:
        return np.zeros((0, n, n)), driver
    return np.stack([v.reshape(n, n, order="F") for v in null]), driver


def _orthogonal_in_span(basis: np.ndarray) -> tuple[np.ndarray | None, float]:
    """An orthogonal matrix in span(basis), as (Q, ‖QᵀQ − I‖₂), or (None, inf) for an empty span.

    One dimension: Q₀ is unique up to scale, and the only candidate is
    Q₀/√c with c = tr(Q₀ᵀQ₀)/n; its orthogonality deviation says whether
    Q₀ᵀQ₀ was cI at all.  More: alternating projection between the span
    and the orthogonal group (the polar factor UVᵀ is the nearest
    orthogonal matrix), from 20 seeded starts, up to 500 steps each,
    keeping the polar factor whose distance to the span is smallest.  That
    factor is orthogonal to rounding, and whether it is an intertwiner is
    what :func:`_congruence_residual` then measures.  Any orthogonal
    element of the span proves the same statement, so which one a platform
    lands on changes nothing.
    """
    if basis.shape[0] == 0:
        return None, np.inf
    n = basis.shape[1]
    eye = np.eye(n)
    if basis.shape[0] == 1:
        q0 = basis[0]
        c = float(np.trace(q0.T @ q0)) / n
        if c <= 0.0:
            return None, np.inf
        q = q0 / np.sqrt(c)
        return q, float(np.linalg.norm(q.T @ q - eye, 2))
    flat = basis.reshape(basis.shape[0], -1).T              # (n², d), orthonormal columns
    rng = np.random.default_rng(0)
    best, best_gap = None, np.inf
    for _ in range(20):
        q = (flat @ rng.normal(size=flat.shape[1])).reshape(n, n)
        for _ in range(500):
            u, _, vt = np.linalg.svd(q)
            polar = u @ vt
            step = (flat @ (flat.T @ polar.ravel())).reshape(n, n)
            moved = float(np.linalg.norm(step - q, 2))
            q = step
            if moved <= 1e-15:
                break
        u, _, vt = np.linalg.svd(q)
        polar = u @ vt
        gap = float(np.linalg.norm(q - polar, 2))
        if gap < best_gap:
            best, best_gap = polar, gap
    return best, float(np.linalg.norm(best.T @ best - eye, 2))


def _congruence_residual(ga: np.ndarray, gb: np.ndarray, q: np.ndarray) -> float:
    """max_s ‖QᵀG^B_sQ − G^A_s‖_max relative to max|G^A|: the certificate's own check."""
    image = np.einsum("ki,skl,lj->sij", q, gb, q)
    return float(np.max(np.abs(image - ga))) / max(float(np.max(np.abs(ga))), 1e-300)


def _trace_scaled(grams_a: np.ndarray, grams_b: np.ndarray) -> tuple[np.ndarray, np.ndarray] | None:
    """Both stacks divided by their own Σ_s tr G_s, an orthogonal invariant, or None when either is zero.

    A scale factor is refinable, so two families whose images agree up to
    one overall intensity scale are one model to a powder; dividing each
    stack by its total trace puts such a pair at exactly the same scale,
    where max|G| (not invariant under Q) would not.
    """
    ta, tb = float(np.einsum("sii->", grams_a)), float(np.einsum("sii->", grams_b))
    if ta <= 0.0 or tb <= 0.0:
        return None
    return grams_a / ta, grams_b / tb


def _isometry(grams_a: np.ndarray, grams_b: np.ndarray) -> Isometry | None:
    """The isometry certificate of two Gram stacks, or None: an orthogonal Q with QᵀG^B_sQ = G^A_s on every shell.

    None when the amplitude counts differ, when either stack is zero
    (the silent family is the absence certificate's), when a shell's
    spectra differ (:func:`_spectra_agree`, no SVD then), when the
    intertwiner space is empty, or when the orthogonal element found fails
    either residual at :data:`ISOMETRY_RESIDUAL`.  Both stacks are
    trace-scaled first (:func:`_trace_scaled`), so the residual is of the
    scaled stacks and the certificate reads "the same image up to one
    intensity scale".
    """
    if grams_a.shape != grams_b.shape or grams_a.shape[1] == 0:
        return None
    scaled = _trace_scaled(grams_a, grams_b)
    if scaled is None:
        return None
    ga, gb = scaled
    if not _spectra_agree(ga, gb):
        return None
    basis, driver = _intertwiners(ga, gb)
    q, orthogonality = _orthogonal_in_span(basis)
    if q is None or orthogonality > ISOMETRY_RESIDUAL:
        return None
    residual = _congruence_residual(ga, gb, q)
    if residual > ISOMETRY_RESIDUAL:
        return None
    return Isometry(q=tuple(tuple(float(v) for v in row) for row in q), residual=residual,
                    orthogonality=orthogonality, dimension=int(basis.shape[0]), driver=driver)


def _verify_isometry(grams_a: np.ndarray, grams_b: np.ndarray, record: Isometry
                     ) -> tuple[bool, float, float]:
    """Re-check a stored :class:`Isometry` against the two stacks: (holds, congruence residual, orthogonality).

    No SVD: the stored Q is trace-scaled against the stacks and the two
    residuals recomputed, each required at :data:`ISOMETRY_RESIDUAL`.
    """
    q = np.asarray(record.q, dtype=np.float64)
    scaled = None if grams_a.shape != grams_b.shape else _trace_scaled(grams_a, grams_b)
    if scaled is None or q.shape != grams_a.shape[1:]:
        return False, np.inf, np.inf
    ga, gb = scaled
    orthogonality = float(np.linalg.norm(q.T @ q - np.eye(q.shape[0]), 2))
    residual = _congruence_residual(ga, gb, q)
    holds = residual <= ISOMETRY_RESIDUAL and orthogonality <= ISOMETRY_RESIDUAL
    return bool(holds), residual, orthogonality


# --------------------------------------------------------------------------
# the span-containment certificate (issue #565, part 4)

def _congruence_scale(grams_a: np.ndarray, grams_b: np.ndarray, e: np.ndarray
                      ) -> tuple[float, float]:
    """(c, residual) of G^A_s ≈ c·EᵀG^B_sE over every shell: c from the traces, the residual relative to max|G^A|."""
    pulled = np.einsum("ki,skl,lj->sij", e, grams_b, e)
    scale = float(np.trace(grams_a.sum(axis=0))) / max(float(np.trace(pulled.sum(axis=0))), 1e-300)
    residual = float(np.max(np.abs(grams_a - scale * pulled))) \
        / max(float(np.max(np.abs(grams_a))), 1e-300)
    return scale, residual


def _domain_patterns(candidate: MagneticCandidate, little: LittleGroup) -> list[np.ndarray]:
    """``candidate``'s moment patterns under each of its domain operations, the identity first, flattened to ``(n_free, 3N)``."""
    out = []
    for index, op in enumerate(_domain_operations(candidate, little)):
        patterns = candidate.configurations if index == 0 else \
            _apply_domain(op, candidate.positions, candidate.configurations, kind=candidate.kind)
        out.append(patterns.reshape(candidate.free_amplitudes, -1))
    return out


def _containment(a: MagneticCandidate, grams_a: np.ndarray, grams_b: np.ndarray,
                 patterns_b: list[np.ndarray]) -> Containment | None:
    """image(A) ⊆ cone image(B) by an injection congruence G^A_s = c·EᵀG^B_sE, or None (:class:`Containment`).

    E is fitted by least squares so that ``a``'s moment patterns are
    written in ``b``'s, C_A = EᵀC_B, first against ``b``'s own patterns and
    then against their image under each further domain operation of ``b``
    (``patterns_b``, :func:`_domain_patterns`, built once per candidate):
    the candidates stand for conjugacy classes of directions, and ``a``
    may sit inside a conjugate of ``b`` rather than in ``b`` as written.
    Each E is then *checked* on the Gram
    stacks over every shell, and the first one whose congruence residual
    is at most :data:`ISOMETRY_RESIDUAL` is the certificate; the pattern
    fit is where E comes from, never what proves it.  Measured on the
    ``F -4 3 m`` Γ general-site set (38 containments among 17 families,
    macOS arm64): residuals 1.8e-15 to 1.4e-14, 23 of them with the
    patterns in span (pattern residual ≤ 1e-15) and 15 through a least
    squares E that reproduces the stack and not the patterns; on the
    known answer, 16 at ≤ 4.7e-15; no congruence across two irreps on
    either set.
    """
    n_a = a.free_amplitudes
    if n_a == 0 or not patterns_b or patterns_b[0].shape[0] == 0:
        return None
    flat_a = a.configurations.reshape(n_a, -1)
    norm_a = max(float(np.linalg.norm(flat_a)), 1e-300)
    for index, flat_b in enumerate(patterns_b):
        e = np.linalg.lstsq(flat_b.T, flat_a.T, rcond=None)[0]
        scale, residual = _congruence_scale(grams_a, grams_b, e)
        if residual <= ISOMETRY_RESIDUAL and scale > 0.0:
            pattern = float(np.linalg.norm(flat_a.T - flat_b.T @ e)) / norm_a
            return Containment(e=tuple(tuple(float(v) for v in row) for row in e),
                               scale=scale, residual=residual, pattern_residual=pattern,
                               domain=index)
    return None


def _verify_containment(grams_a: np.ndarray, grams_b: np.ndarray, record: Containment
                        ) -> tuple[bool, float]:
    """Re-check a stored :class:`Containment` against the two stacks: (holds, congruence residual)."""
    e = np.asarray(record.e, dtype=np.float64)
    if e.shape != (grams_b.shape[1], grams_a.shape[1]):
        return False, float("inf")
    scale, residual = _congruence_scale(grams_a, grams_b, e)
    return bool(residual <= ISOMETRY_RESIDUAL and scale > 0.0
                and abs(scale / record.scale - 1.0) <= 1e-9), residual


def _fit_residual(target: np.ndarray, grams: np.ndarray, rng, *,
                  restarts: int = 32, rtol: float | None = None) -> float:
    """Smallest ‖I(b) − target‖∞ a family reaches over random starts, relative to max target.

    ``grams`` is that family's :func:`gram` stack, so I_s(b) = bᵀ G_s b and the
    fit is a small non-linear least squares with the exact Jacobian 2·G_s·b.
    Several restarts because a quadratic-form fit has sign and permutation
    symmetries, and a start can sit on a saddle or roll into a
    local minimum: on the five non-cubic cases of issue #455, measured with
    #534's frame fix, 48 % of single restarts on a pair known to be
    equivalent reached the global minimum (367 of 768), and the failures
    cluster by draw: 34 of 192 draws had all of their first four restarts
    fail, where independent restarts predict 14, and one draw reached it
    only 6 times in 512 restarts.  With ``rtol`` the loop
    **stops at the first restart that reaches it**, since the question asked
    is "can B reproduce this?" and one reproduction answers it; so an
    equivalent draw costs one or two fits and only a draw that *cannot* be
    reproduced pays the whole ``restarts``.  Without ``rtol`` every restart
    runs and the smallest residual is returned.

    **A shell the family cannot light is settled before the fit.**  Where
    G_s is below :data:`INTENSITY_RTOL` of the stack's largest (the same
    tolerance :func:`systematic_absences` calls absent), I_s(b) is zero for
    every b.  If the target is zero there too, the row is identically zero
    and is dropped: it moves neither the minimiser nor, beyond that
    tolerance, the ∞-norm.  If
    the target is *not* zero there, its residual is |t_s| whatever b is, so
    with ``rtol`` given and |t_s| above it of the target's largest, the
    family **provably** cannot reproduce the target and that floor is
    returned without a fit — an absence the other family fills is the
    strongest evidence of distinguishability there is.  "Provably" is exact
    for G_s ≡ 0 only: a shell counted dark at the tolerance can still reach
    |t_s| for a large enough ‖b‖, though every live shell then grows as
    ‖b‖² too, which is why it is not expected to matter at ``rtol`` = 1e-4.
    Below ``rtol`` the row stays in the fit, where it is a constant.

    The driver is ``"trf"`` whenever there are fewer live shells than amplitudes,
    because ``"lm"`` *refuses* that problem rather than solving it badly
    (``ValueError: Method 'lm' doesn't work when the number of residuals is
    less than the number of variables``).  A refusal is not a measurement: a
    swallowed one leaves ``best`` at ``inf`` and makes :func:`powder_equivalent`
    report a candidate as distinguishable from itself at a coarse ``d_min``,
    which is the failure direction this module exists to avoid.  Nothing else
    is caught here — a solver raising for any other reason is a defect and
    surfaces (Yue's review of #389, 2026-09-18).
    """
    target = np.asarray(target, dtype=np.float64)
    if rtol is not None:
        floor = _absence_floor(target, grams)
        if floor > rtol:
            return floor
    return _restarts(target, grams, rng, restarts=restarts, rtol=rtol)[0]


def _absence_floor(target: np.ndarray, grams: np.ndarray) -> float:
    """The largest target on a shell the fit counts dark, relative to max target: a residual no amplitude can lower."""
    scale = float(np.max(np.abs(target))) or 1.0
    return float(np.max(np.abs(target[_dark_shells(grams)]), initial=0.0)) / scale


def _fit_rows(target: np.ndarray, grams: np.ndarray) -> np.ndarray:
    """The shells :func:`_fit_residual` fits: all but those dark for the family and zero in the target."""
    scale = float(np.max(np.abs(target))) or 1.0
    return ~(_dark_shells(grams) & (np.abs(target) <= INTENSITY_RTOL * scale))


def _restarts(target: np.ndarray, grams: np.ndarray, rng, *, restarts: int,
              rtol: float | None, rows: np.ndarray | None = None,
              weights: np.ndarray | None = None) -> tuple[float, float, np.ndarray]:
    """The restart loop of :func:`_fit_residual`: (smallest ‖I − t‖∞ relative to max t, smallest relative L2 residual, the amplitudes of the first).

    The first is :func:`_fit_residual`'s return value, with its early stop at
    ``rtol``.  The second is min over the restarts made of
    ‖w∘(I(x) − t)‖₂/‖w∘t‖₂ on ``rows`` (every fitted shell when None, unit
    ``weights`` when None), the upper end of a :class:`Witness`'s ``d``.
    The third is the amplitude vector of the restart that gave the first,
    which the fit transfer reads (:func:`_transfer_fit`); zeros when no
    shell was fitted.  All draw on ``rng`` exactly as :func:`_fit_residual`
    always has, one normal vector per restart, so splitting the loop in two
    consumes the same stream as running it whole.
    """
    from scipy.optimize import least_squares

    scale = float(np.max(np.abs(target))) or 1.0
    keep = _fit_rows(target, grams)
    if not np.any(keep):
        return 0.0, 0.0, np.zeros(grams.shape[1])
    g, t = grams[keep], target[keep]
    rows = keep if rows is None else rows
    w = np.ones(len(target)) if weights is None else np.asarray(weights, dtype=np.float64)
    wt = w[rows] * target[rows]
    wt_norm = float(np.linalg.norm(wt)) or 1.0

    def residual(b):
        return (g @ b) @ b - t

    def jacobian(b):
        return 2.0 * (g @ b)

    best, best_l2 = np.inf, np.inf
    n = grams.shape[1]
    best_x = np.zeros(n)
    method = "lm" if t.size >= n else "trf"
    for _ in range(restarts):
        start = rng.normal(size=n) * np.sqrt(scale / max(n, 1))
        fit = least_squares(residual, start, jac=jacobian, method=method,
                            xtol=1e-14, ftol=1e-14, gtol=1e-14, max_nfev=4000)
        r_inf = float(np.max(np.abs(fit.fun)))
        if r_inf < best:
            best, best_x = r_inf, fit.x
        model = (grams[rows] @ fit.x) @ fit.x
        best_l2 = min(best_l2, float(np.linalg.norm(w[rows] * model - wt)) / wt_norm)
        if rtol is not None and best / scale <= rtol:
            break
    return best / scale, best_l2, best_x


# --------------------------------------------------------------------------
# the Farkas certificate of one draw (issue #565, part 2)

def _householder_complement(u: np.ndarray) -> np.ndarray:
    """Orthonormal columns spanning u⊥, for a unit vector u: columns 2… of one Householder reflector.

    H = I − 2vvᵀ/vᵀv with v = u − αe₁, α = −sign(u₁), maps u to αe₁, and H
    is symmetric and orthogonal, so its first column is u/α and the others
    are an orthonormal basis of u⊥ (Householder 1958, *J. ACM* **5**, 339).
    No SVD: the basis is a closed form of u.
    """
    m = u.shape[0]
    alpha = -1.0 if u[0] >= 0.0 else 1.0
    v = u.astype(np.float64).copy()
    v[0] -= alpha
    vv = float(v @ v)
    h = np.eye(m)
    if vv > 0.0:
        h -= (2.0 / vv) * np.outer(v, v)
    return h[:, 1:]


def _spectrum_ratio(grams: np.ndarray, y: np.ndarray) -> float:
    """λ_min/|λ|_max of M(y) = Σ_s y_s G_s."""
    w = np.linalg.eigvalsh(np.einsum("s,sij->ij", y, grams))
    return float(w[0] / max(float(np.max(np.abs(w))), 1e-300))


def _live_projection(grams: np.ndarray) -> tuple[np.ndarray, int, float]:
    """The stack with its common kernel projected out: (PᵀG_sP scaled to max 1, kernel dimension, kernel residual).

    One ``eigh`` of Σ_s G_s (stack scaled to max 1): directions with
    eigenvalue ≤ :data:`INTENSITY_RTOL` of the largest are the common kernel
    K, since every G_s is PSD and Σ_s G_s u = 0 forces G_s u = 0.  On K every
    M(y) vanishes, so M(y) ⪰ 0 exactly when PᵀM(y)P ⪰ 0 for P the
    orthonormal complement, and a strict certificate becomes possible where
    the full M(y) has a structural zero eigenvalue.  The cut errs toward
    keeping a direction: a kept near-kernel direction only weakens the
    certificate, a dropped live one would make it invalid, which is what the
    kernel residual r_K = max_s ‖G_s K‖₂/‖G_s‖₂ guards (the caller refuses a
    certificate above :data:`INTENSITY_RTOL`).  Measured on 145 families of
    six cubic sets at the general site, d_min 1.5 Å (Linux x86-64): dropped
    relative eigenvalues ≤ 8.2e-16, kept ones ≥ 2.8e-7, r_K ≤ 2.7e-13.
    """
    g = grams / max(float(np.max(np.abs(grams))), 1e-300)
    k, p, residual = _common_kernel(g)
    kernel = k.shape[1]
    if kernel:
        g = np.einsum("ki,skl,lj->sij", p, g, p)
        g = g / max(float(np.max(np.abs(g))), 1e-300)
    return g, kernel, residual


def _common_kernel(g: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """The common kernel of a stack scaled to max 1: (K, P, r_K), orthonormal kernel and complement, and max_s ‖g_sK‖₂/‖g_s‖₂.

    One ``eigh`` of Σ_s g_s; the cut is :func:`_live_projection`'s, which
    is built on this, as is :func:`_kernel_amplitude_ratio`, so the two
    read one kernel.
    """
    w, v = np.linalg.eigh(g.sum(axis=0))
    kernel = int(np.sum(w <= INTENSITY_RTOL * max(float(w[-1]), 1e-300)))
    k, p = v[:, :kernel], v[:, kernel:]
    residual = 0.0
    if kernel:
        residual = max(float(np.linalg.norm(x @ k, 2)) / max(float(np.linalg.norm(x, 2)), 1e-300)
                       for x in g)
    return k, p, residual


def _kernel_amplitude_ratio(grams: np.ndarray, y: np.ndarray) -> float:
    """ρ_max = −1 + √(1 + ratio·Λ/(r_K·Y)): the amplitude bound along the kernel under which y refutes the draw on the full stack.

    On the live stack scaled to max 1, g_s, with K its common kernel, P the
    complement, M = Σ_s y_s g_s and b = Pu + Kv,

        bᵀMb ≥ ratio·Λ‖u‖² − r_K·Y·(2‖u‖‖v‖ + ‖v‖²),

    since ‖PᵀMK‖₂ and ‖KᵀMK‖₂ are each at most Σ_s |y_s|‖g_sK‖₂ ≤ r_K·Y,
    with Λ = ‖PᵀMP‖₂, ratio = λ_min(PᵀMP)/Λ, Y = Σ_s |y_s|‖g_s‖₂ and r_K
    :func:`_common_kernel`'s residual.  The right side is positive for
    every u ≠ 0 and ‖v‖ ≤ ρ‖u‖ exactly when r_K·Y·(2ρ + ρ²) < ratio·Λ, and
    then y·I(b) = bᵀMb > 0 > y·t refutes I(b) = t; ρ_max is the largest
    such ρ.  Infinite when the stack has no kernel or r_K = 0 (the claim is
    then unconditional), 0 when PᵀMP is not positive definite.
    :data:`KERNEL_AMPLITUDE_RATIO` is the least ρ_max a certificate is
    issued at.
    """
    g = grams / max(float(np.max(np.abs(grams))), 1e-300)
    k, p, residual = _common_kernel(g)
    if k.shape[1] == 0 or residual <= 0.0:
        return float("inf")
    w = np.linalg.eigvalsh(p.T @ np.einsum("s,sij->ij", y, g) @ p)
    lam = float(np.max(np.abs(w)))
    ratio = float(w[0]) / max(lam, 1e-300)
    if ratio <= 0.0:
        return 0.0
    big_y = float(np.sum(np.abs(np.asarray(y)) * np.linalg.norm(g, 2, axis=(1, 2))))
    return float(-1.0 + np.sqrt(1.0 + ratio * lam / (residual * big_y)))


def _cone_margin(grams: np.ndarray, y_hat: np.ndarray) -> tuple[float, float, float]:
    """(λ′, Γ, μ) of a unit direction ŷ on a projected live stack scaled to max 1: every image point has cos(ŷ, I) ≥ μ.

    λ′ = λ_min(M(ŷ)) − n ε |λ|_max is the eigenvalue after its backward
    error (LAPACK Users' Guide § 4.7, p(n) = n); Γ = (Σ_s ‖G_s‖₂²)^½ bounds
    ‖I(x)‖ by Γ‖x‖²; so ŷ·I(x) = xᵀM(ŷ)x ≥ λ′‖x‖² ≥ (λ′/Γ)‖I(x)‖ for every x
    (and tr(M(ŷ)X) ≥ λ′ tr X for every X ⪰ 0 of the relaxation).  μ ≤ 0
    means ŷ bounds nothing.
    """
    w = np.linalg.eigvalsh(np.einsum("s,sij->ij", y_hat, grams))
    eps = float(np.finfo(np.float64).eps)
    lam = float(w[0]) - grams.shape[1] * eps * float(np.max(np.abs(w)))
    gamma = float(np.sqrt(np.sum(np.linalg.norm(grams, 2, axis=(1, 2)) ** 2)))
    return lam, gamma, lam / max(gamma, 1e-300)


def _transfer_margin(g: np.ndarray, y_hat: np.ndarray) -> tuple[float, float, float, int, float]:
    """(λ′, Γ, μ, kernel dimension, r_K) of ŷ on ``b``'s certificate stack: every image point of ``b`` has cos(ŷ, I) ≥ μ.

    On a stack without a kernel, or with an exact one (r_K = 0), this is
    :func:`_cone_margin` on the projected stack, whose claim is
    unconditional.  Where r_K > 0 the projected stack covers only
    amplitudes along the live directions, and a model of ``b`` is
    b = Pu + Kv: on the stack scaled to max 1, g_s, with M = Σ_s ŷ_s g_s
    and Y = Σ_s |ŷ_s|‖g_s‖₂,

        ŷ·I(b) = bᵀMb ≥ (λ′_P − r_K·Y·(2ρ + ρ²))‖u‖²,   ‖I(b)‖ ≤ Γ(1 + ρ²)‖u‖²,

    for ‖v‖ ≤ ρ‖u‖ (the cross and kernel blocks of M are each at most r_K·Y
    in 2-norm, as in :func:`_kernel_amplitude_ratio`), λ′_P the projected
    eigenvalue after its backward error and Γ = (Σ_s ‖g_s‖₂²)^½ on the full
    stack.  The cone then holds for every amplitude of ``b`` whose kernel
    component is at most ρ = :data:`KERNEL_AMPLITUDE_RATIO` times its live
    one, the same statement a Farkas witness makes (``kernel_amplitude_ratio``),
    and the returned Γ is Γ(1 + ρ²), so that μ = λ′/Γ as in the record.
    The margins read against this go down to 1.7e-9 and r_K is accepted up
    to :data:`INTENSITY_RTOL`, so the term is not negligible where the
    transfer is tightest.
    """
    projected, kernel, residual = _live_projection(g)
    if kernel == 0 or residual <= 0.0:
        return (*_cone_margin(projected, y_hat), kernel, residual)
    g1 = g / max(float(np.max(np.abs(g))), 1e-300)
    _, p, _ = _common_kernel(g1)
    w = np.linalg.eigvalsh(p.T @ np.einsum("s,sij->ij", y_hat, g1) @ p)
    eps = float(np.finfo(np.float64).eps)
    norms = np.linalg.norm(g1, 2, axis=(1, 2))
    ratio = KERNEL_AMPLITUDE_RATIO
    lam = float(w[0]) - g1.shape[1] * eps * float(np.max(np.abs(w))) \
        - residual * float(np.sum(np.abs(y_hat) * norms)) * (2.0 * ratio + ratio ** 2)
    gamma = float(np.sqrt(np.sum(norms ** 2))) * (1.0 + ratio ** 2)
    return lam, gamma, lam / max(gamma, 1e-300), kernel, residual


def _farkas_dual(grams: np.ndarray, t_hat: np.ndarray) -> tuple[float, np.ndarray]:
    """max λ_min(Σ_s y_s G_s) over y·t̂ = −1, as (λ_min/|λ|_max at the maximiser, y).

    λ_min is concave and the constraint affine (Boyd & Vandenberghe 2004,
    § 3.1.5), so a local ascent finds the optimum.  y = −t̂ + N z with N the
    :func:`_householder_complement` of t̂; BFGS on the smooth concave
    surrogate −τ log tr exp(−M/τ), within τ log n of λ_min, at τ = 10⁻¹ …
    10⁻⁶ from z = 0; one exact eigenvalue at the end.  One live shell leaves
    the single point −t̂.  ``grams`` is scaled to max 1, as
    :func:`_live_projection` returns it.
    """
    from scipy.optimize import minimize
    from scipy.special import logsumexp, softmax

    y0 = -t_hat
    n_shells = t_hat.shape[0]
    z = np.zeros(n_shells - 1)
    if n_shells > 1:
        basis = _householder_complement(t_hat)

        def surrogate(tau):
            def f(z):
                w, v = np.linalg.eigh(np.einsum("s,sij->ij", y0 + basis @ z, grams))
                p = softmax(-w / tau)
                grad = np.einsum("sij,ik,jk,k->s", grams, v, v, p)
                return tau * logsumexp(-w / tau), -(basis.T @ grad)
            return f

        for tau in (1e-1, 1e-2, 1e-3, 1e-4, 1e-5, 1e-6):
            z = minimize(surrogate(tau), z, jac=True, method="BFGS",
                         options={"gtol": 1e-12, "maxiter": 2000}).x
        y = y0 + basis @ z
    else:
        y = y0
    return _spectrum_ratio(grams, y), y


def _min_norm_certificate(grams: np.ndarray, t_hat: np.ndarray,
                          y_dual: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """The minimum-norm certificate, min ‖y‖ on M(y) ⪰ 0 and y·t̂ = −1, and an interior anchor: (y_mn, anchor).

    1/‖y_mn‖ is the distance from t̂ to the cone of (tr G_s X)_s, X ⪰ 0
    (Boyd & Vandenberghe 2004, § 8.1), and any feasible y bounds it from
    below.  ``y_dual`` is :func:`_farkas_dual`'s maximiser, strictly
    feasible and usually of enormous norm (the dual is unbounded when a
    certificate exists).  The anchor is on the ray from −t̂ through it, at
    twice where the ratio first exceeds min(10⁻⁹, half the maximiser's)
    (bisection), a moderate-norm interior point.  From there a barrier
    method (Boyd & Vandenberghe 2004, § 11.3): ‖y‖² − μ log det M(y) on
    y = −t̂ + N z, each μ centred by Newton steps with the exact Hessian
    2I + μ[tr(M⁻¹G_s M⁻¹G_r)] and a backtracking line search that keeps
    M(y) ≻ 0 (a Cholesky factor must exist), μ divided by 10 from ‖anchor‖²
    until n μ ≤ 10⁻¹² ‖y‖², which bounds ‖y‖² above its minimum by that.
    The centred points are unique, so y_mn depends neither on the
    maximiser's drift nor on the platform's rounding beyond the tolerance
    (measured: d agrees to 1e-11 between macOS arm64 and Linux x86-64, where
    a BFGS barrier stopped on "precision loss" at points 3.7× apart in d).
    One live shell: both are −t̂.
    """
    y0 = -t_hat
    if t_hat.shape[0] == 1:
        return y0, y0
    basis = _householder_complement(t_hat)
    z_dual = basis.T @ (y_dual - y0)
    threshold = min(1e-9, _spectrum_ratio(grams, y_dual) / 2)
    lo, hi = 0.0, 1.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if _spectrum_ratio(grams, y0 + mid * (basis @ z_dual)) > threshold:
            hi = mid
        else:
            lo = mid
    z = z_dual
    for factor in (2.0, 1.0):
        if _spectrum_ratio(grams, y0 + basis @ (factor * hi * z_dual)) > 0.0:
            z = factor * hi * z_dual
            break
    anchor = y0 + basis @ z
    n = grams.shape[1]

    def barrier(z, mu):
        """(value, M⁻¹) at z, or (inf, None) where M(y) is not positive definite."""
        y = y0 + basis @ z
        m = np.einsum("s,sij->ij", y, grams)
        try:
            chol = np.linalg.cholesky(m)
            inverse = np.linalg.inv(m)
        except np.linalg.LinAlgError:       # not positive definite, or singular to rounding
            return np.inf, None
        value = float(y @ y) - 2.0 * mu * float(np.sum(np.log(np.diag(chol))))
        if not np.isfinite(value):
            return np.inf, None
        return value, 0.5 * (inverse + inverse.T)

    mu = float(anchor @ anchor)
    for _ in range(64):
        value, inverse = barrier(z, mu)
        for _ in range(100):
            y = y0 + basis @ z
            b = np.einsum("ij,sjk->sik", inverse, grams)          # M⁻¹ G_s
            grad = basis.T @ (2.0 * y - mu * np.einsum("sii->s", b))
            hess = basis.T @ (2.0 * np.eye(len(y)) + mu * np.einsum("sij,rji->sr", b, b)) @ basis
            step = -np.linalg.solve(hess, grad)
            decrement = -float(grad @ step)
            if decrement <= 1e-14 * float(y @ y):
                break
            s = 1.0
            for _ in range(60):
                trial, trial_inverse = barrier(z + s * step, mu)
                if trial <= value - 0.25 * s * decrement:
                    break
                s *= 0.5
            else:
                break
            z, value, inverse = z + s * step, trial, trial_inverse
        y = y0 + basis @ z
        if n * mu <= 1e-12 * float(y @ y):
            break
        mu /= 10.0
    return y0 + basis @ z, anchor


def _quote_inside(grams: np.ndarray, y_mn: np.ndarray, anchor: np.ndarray) -> np.ndarray:
    """The certificate to quote: the point of the segment y_mn → anchor nearest y_mn with ratio ≥ min(:data:`FARKAS_QUOTE`, anchor's/2), the target floored at :data:`FARKAS_FLOOR`.

    λ_min of M(y) is concave along the segment and y·t̂ = −1 holds on all of
    it, so a bisection on the fraction finds the point.  d moves by at most
    0.7 % (d_q/d_mn ≥ 0.9934 over the 49 witnesses of the known answer and
    ``P m -3 m`` at (0, 0, ½)).  An anchor whose own ratio is under the
    floor ends the bisection at the anchor, which is then under it too, and
    the caller refuses it (review of #772, round 2).
    """
    target = max(FARKAS_FLOOR, min(FARKAS_QUOTE, _spectrum_ratio(grams, anchor) / 2))
    if _spectrum_ratio(grams, y_mn) >= target:
        return y_mn
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if _spectrum_ratio(grams, (1 - mid) * y_mn + mid * anchor) >= target:
            hi = mid
        else:
            lo = mid
    return (1 - hi) * y_mn + hi * anchor


def _exact_psd(grams: np.ndarray, y) -> bool:
    """Whether Σ_s y_s G_s is PSD in exact arithmetic, for the float y and the float stack.

    The matrix is built in :class:`fractions.Fraction` from the floats and
    reduced by LDLᵀ without pivoting: PSD iff every pivot is ≥ 0 and a zero
    pivot has a zero remaining row (Peyrl & Parrilo 2008, *Theor. Comput.
    Sci.* **409**, 269, on rational certificates).  Exact for the stack as
    floating point holds it, not for the stack exact arithmetic would build,
    and the stack here is the *projected* one: the caller passes PᵀG_sP, so
    the proof concerns the full stack only to the extent that every G_s
    annihilates the common kernel K, which the kernel is *taken* to do.  The
    float stack departs from that by the kernel residual r_K ≤
    :data:`INTENSITY_RTOL`, recorded in :attr:`Witness.kernel_residual` and
    not covered by this check; what the full float stack still proves under
    that residual is :attr:`Witness.kernel_amplitude_ratio`
    (:func:`_kernel_amplitude_ratio`).
    At the quoted margin (:data:`FARKAS_QUOTE`, more than three decades
    above the rounding bound) it cannot disagree with the float eigenvalue:
    it is the arbiter by decision, and assurance in practice.
    """
    n_shells, n, _ = grams.shape
    yf = [Fraction(float(v)) for v in y]
    gf = [[[Fraction(float(grams[s, i, j])) for j in range(n)] for i in range(n)]
          for s in range(n_shells)]
    a = [[sum((yf[s] * gf[s][i][j] for s in range(n_shells)), Fraction(0)) if j >= i
          else Fraction(0) for j in range(n)] for i in range(n)]
    for i in range(n):
        for j in range(i):
            a[i][j] = a[j][i]          # the float G_s are symmetric only to rounding
    for k in range(n):
        pivot = a[k][k]
        if pivot < 0:
            return False
        if pivot == 0:
            if any(a[k][j] != 0 for j in range(k + 1, n)):
                return False
            continue
        for i in range(k + 1, n):
            if a[k][i] == 0:
                continue
            f = a[k][i] / pivot
            for j in range(i, n):
                a[i][j] -= f * a[k][j]
    return True


def _certificate_stack(grams_live: np.ndarray, target_live: np.ndarray,
                       weights_live: np.ndarray | None) -> tuple[np.ndarray, np.ndarray]:
    """The (weighted) live stack and unit target a certificate is solved on: (w_s G_s, w∘t/‖w∘t‖)."""
    if weights_live is None:
        return grams_live, target_live / float(np.linalg.norm(target_live))
    g = grams_live * weights_live[:, None, None]
    t = weights_live * target_live
    return g, t / float(np.linalg.norm(t))


def _farkas_certificate(grams_live: np.ndarray, target_live: np.ndarray,
                        weights_live: np.ndarray | None = None) -> tuple[float | None, dict | None]:
    """The projected dual's optimum and, when it clears :data:`FARKAS_FLOOR`, the quoted certificate: (dual, parts).

    ``parts`` holds y (quoted, on the live shells, y·t̂ = −1), the projected
    stack's kernel data, the full-stack amplitude bound ρ_max
    (:func:`_kernel_amplitude_ratio`), ratio, rounding bound and the exact
    check; None when the dual is below the floor, the kernel residual is
    above :data:`INTENSITY_RTOL` (dual None too: nothing is solved), the
    quoted ratio is below the floor, the exact check fails, or ρ_max is
    below :data:`KERNEL_AMPLITUDE_RATIO` (the guard tied to the quoted
    margin: solved, and refused).
    """
    g, t_hat = _certificate_stack(grams_live, target_live, weights_live)
    projected, kernel, residual = _live_projection(g)
    if residual > INTENSITY_RTOL:
        return None, None
    dual, y_dual = _farkas_dual(projected, t_hat)
    if dual < FARKAS_FLOOR:
        return dual, None
    y_mn, anchor = _min_norm_certificate(projected, t_hat, y_dual)
    y = _quote_inside(projected, y_mn, anchor)
    ratio = _spectrum_ratio(projected, y)
    if ratio < FARKAS_FLOOR or not _exact_psd(projected, y):
        return dual, None
    rho = _kernel_amplitude_ratio(g, y)
    if rho < KERNEL_AMPLITUDE_RATIO:
        return dual, None
    eps = float(np.finfo(np.float64).eps)
    m = np.einsum("s,sij->ij", y, projected)
    kappa = float(np.sum(np.abs(y) * np.array([np.linalg.norm(x, 2) for x in projected]))) \
        / max(float(np.linalg.norm(m, 2)), 1e-300)
    n_shells, n = projected.shape[:2]
    interior = y_dual / float(np.linalg.norm(y_dual))
    margin = _cone_margin(projected, interior)[2]
    return dual, {"y": y, "kernel_dim": kernel, "kernel_residual": residual,
                  "kernel_amplitude_ratio": rho, "ratio": ratio,
                  "rounding_bound": n * eps + n_shells * eps * kappa, "exact": True,
                  "interior": interior, "margin": margin}


def _gate(rtol: float, target: np.ndarray, live: np.ndarray) -> float:
    """g = rtol·√S_live·max|t|/‖t_live‖₂: a certificate with d_lo ≥ g proves no restart can reach ``rtol``.

    For every model I of ``b`` the fit's residual is
    r_∞ = max_s |I_s − t_s|/max|t| over the fitted shells, which include
    ``live``, so r_∞ ≥ ‖I_live − t_live‖₂/(√S_live·max|t|)
    ≥ d_lo·‖t_live‖₂/(√S_live·max|t|).  d_lo ≥ g then gives r_∞ ≥ rtol for
    every model: the draw is not reproduced at the caller's own ``rtol``.
    """
    scale = float(np.max(np.abs(target)))
    return rtol * float(np.sqrt(np.count_nonzero(live))) * scale \
        / float(np.linalg.norm(target[live]))


def _verify_witness(grams_b: np.ndarray, witness: Witness) -> tuple[bool, float, float]:
    """Re-check a stored :class:`Witness` against ``b``'s stack: (holds, projected ratio, |y·t̂ + 1|).

    Rebuilds the (weighted) live stack from ``grams_b`` and the stored t,
    projects out its common kernel afresh, and requires |y·t̂ + 1| ≤ 1e-9,
    projected ratio ≥ :data:`FARKAS_FLOOR`, the exact LDLᵀ, the
    full-stack guard ρ_max ≥ :data:`KERNEL_AMPLITUDE_RATIO`, and that the
    stored ``interior`` is a unit vector whose M(ŷ) clears the same floor
    on the projected stack (what the fit transfer rests on).  The stored
    t is an intensity vector, so a change of either family's amplitude basis
    leaves the check intact (M(y) and y·t move by congruence and not at
    all) — which is also why a witness carried to an isometric copy of
    ``b`` re-verifies against that copy's own stack.
    """
    live = np.asarray(witness.live, dtype=np.int64)
    t = np.asarray(witness.t, dtype=np.float64)[live]
    w = None if witness.weights is None else np.asarray(witness.weights)[live]
    g, t_hat = _certificate_stack(grams_b[live], t, w)
    projected, _, residual = _live_projection(g)
    y = np.asarray(witness.y, dtype=np.float64)
    off = abs(float(y @ t_hat) + 1.0)
    ratio = _spectrum_ratio(projected, y)
    interior = np.asarray(witness.interior, dtype=np.float64)
    holds = (residual <= INTENSITY_RTOL and off <= 1e-9 and ratio >= FARKAS_FLOOR
             and _exact_psd(projected, y)
             and _kernel_amplitude_ratio(g, y) >= KERNEL_AMPLITUDE_RATIO
             and interior.shape == y.shape
             and abs(float(np.linalg.norm(interior)) - 1.0) <= 1e-9
             and _spectrum_ratio(projected, interior) >= FARKAS_FLOOR)
    return bool(holds), ratio, off


def _certify_draw(target: np.ndarray, grams_b: np.ndarray, dark_b: np.ndarray, rng, *,
                  restarts: int, rtol: float, draw: int,
                  weights: np.ndarray | None = None
                  ) -> tuple[bool, bool, Witness | None, float | None]:
    """One draw of ``a`` against ``b``: (reproduced, proved not, witness, dual).

    :func:`_fit_residual`'s loop, with the Farkas dual after restart
    :data:`DUAL_AFTER_RESTART`: the absence floor first, then that many
    restarts; if none reproduces the draw to ``rtol``, the certificate is
    solved on ``b``'s live shells (lit for ``b`` by the scale-free test,
    ``dark_b``, and fitted).  A certificate that passes the exact check and
    the gate (:func:`_gate`: d_lo ≥ g, with d_lo from the unweighted bound
    when ``weights`` are given) ends the draw proved, with no more restarts;
    otherwise the remaining restarts run as before and decide it, and a
    certificate below the gate rides along as the witness.  The generator is
    consumed exactly as :func:`_fit_residual` consumes it up to the point the
    draw is decided.

    With ``weights`` the certificate is solved on w_s G_s and w∘t, so d is
    the weighted distance; its unweighted bound is
    y_u = (w∘y_w)·‖t‖/‖w∘t‖, which has y_u·t̂ = −1 and M(y_u) a positive
    multiple of the weighted M(y_w), so it is a certificate for the
    unweighted problem and the gate reads 1/‖y_u‖.  The fit and its ``rtol``
    stay unweighted.
    """
    if _absence_floor(target, grams_b) > rtol:
        return False, False, None, None
    first = min(DUAL_AFTER_RESTART, restarts)
    keep = _fit_rows(target, grams_b)
    live = keep & ~dark_b
    w = None if weights is None else np.asarray(weights, dtype=np.float64)
    r_inf, r_l2, _ = _restarts(target, grams_b, rng, restarts=first, rtol=rtol,
                               rows=live, weights=w)
    if r_inf <= rtol:
        return True, False, None, None
    witness, dual = None, None
    if np.any(live) and float(np.linalg.norm(target[live])) > 0.0:
        dual, parts = _farkas_certificate(grams_b[live], target[live],
                                          None if w is None else w[live])
        if parts is not None:
            y = parts["y"]
            d_lo = 1.0 / float(np.linalg.norm(y))
            if w is None:
                d_gate = d_lo
            else:
                tw = w[live] * target[live]
                y_u = w[live] * y * float(np.linalg.norm(target[live])) / float(np.linalg.norm(tw))
                d_gate = 1.0 / float(np.linalg.norm(y_u))
            witness = Witness(
                draw=draw, t=tuple(float(v) for v in target),
                live=tuple(int(s) for s in np.flatnonzero(live)),
                y=tuple(float(v) for v in y),
                weights=None if w is None else tuple(float(v) for v in w),
                kernel_dim=parts["kernel_dim"], kernel_residual=parts["kernel_residual"],
                kernel_amplitude_ratio=parts["kernel_amplitude_ratio"],
                ratio=parts["ratio"], rounding_bound=parts["rounding_bound"],
                exact=parts["exact"], d=(d_lo, r_l2),
                interior=tuple(float(v) for v in parts["interior"]), margin=parts["margin"])
            if d_gate >= _gate(rtol, target, live):
                return False, True, witness, dual
    more_inf, more_l2, _ = _restarts(target, grams_b, rng, restarts=restarts - first,
                                     rtol=rtol, rows=live, weights=w)
    if witness is not None and more_l2 < witness.d[1]:
        witness = replace(witness, d=(witness.d[0], more_l2))
    return more_inf <= rtol, False, witness, dual


# --------------------------------------------------------------------------
# the transfers (issue #565, part 4)

def _transfer_fit(target: np.ndarray, grams_c: np.ndarray, rng, *, restarts: int,
                  rtol: float) -> np.ndarray | None:
    """``c``'s amplitudes that reproduce a witness draw to ``rtol``, or None.

    :func:`_fit_residual`'s loop on the draw: the absence floor first (a
    shell ``c`` cannot light that the draw does settles it without a fit),
    then up to ``restarts`` starts with the early stop; the amplitudes of
    the best are returned when it reached ``rtol``.  A draw not reached is
    not a verdict of any kind — the transfer is then simply not made.
    """
    if _absence_floor(target, grams_c) > rtol:
        return None
    r_inf, _, x = _restarts(target, grams_c, rng, restarts=restarts, rtol=rtol)
    return x if r_inf <= rtol else None


def _fit_transfer(witness: Witness, grams_b: np.ndarray, dark_b: np.ndarray,
                  grams_c: np.ndarray, x_c) -> tuple[bool, Transfer | None]:
    """The sign-free bound of :class:`Transfer` on ``c``'s amplitudes ``x_c``: (fires, record).

    Everything is recomputed from the stacks: the witness's ``interior`` ŷ
    gives (λ′, Γ, μ) on ``b``'s projected (weighted) live stack
    (:func:`_cone_margin`); ``x_c`` is projected onto the complement of
    ``c``'s common kernel; I_c = I_C(x_c⊥) is formed on every shell and
    refused (None) if it lights a shell ``b`` is dark at — such a point is
    outside ``b`` by absence, which is another certificate's statement —
    or if ``b``'s stack has no strict direction (μ ≤ 0); then cos(ŷ, Î_c),
    κ_c and ρ on the live shells, and the verdict cos < μ − ρ.  The record
    is returned whether or not it fires, so a negative control can show
    its numbers.
    """
    live = np.asarray(witness.live, dtype=np.int64)
    t = np.asarray(witness.t, dtype=np.float64)
    w = None if witness.weights is None else np.asarray(witness.weights, dtype=np.float64)
    w_live = None if w is None else w[live]
    g, t_hat = _certificate_stack(grams_b[live], t[live], w_live)
    projected, kernel, residual = _live_projection(g)
    if residual > INTENSITY_RTOL:
        return False, None
    y_hat = np.asarray(witness.interior, dtype=np.float64)
    lam, gamma, mu, _, _ = _transfer_margin(g, y_hat)
    if mu <= 0.0:
        return False, None
    gc = grams_c / max(float(np.max(np.abs(grams_c))), 1e-300)
    _, p, _ = _common_kernel(gc)
    x = p @ (p.T @ np.asarray(x_c, dtype=np.float64))
    intensity = (grams_c @ x) @ x
    scale = float(np.max(np.abs(intensity)))
    if scale <= 0.0 or float(np.max(np.abs(intensity[dark_b]), initial=0.0)) > INTENSITY_RTOL * scale:
        return False, None
    i_live = intensity[live] if w is None else w_live * intensity[live]
    norm_i = float(np.linalg.norm(i_live))
    if norm_i <= 0.0:
        return False, None
    cos = float(y_hat @ i_live) / norm_i
    gc_live = grams_c[live] if w is None else grams_c[live] * w_live[:, None, None]
    gamma_c = float(np.sqrt(np.sum(np.linalg.norm(gc_live, 2, axis=(1, 2)) ** 2)))
    kappa = gamma_c * float(x @ x) / norm_i
    eps = float(np.finfo(np.float64).eps)
    shells, n_b = projected.shape[:2]
    n_c = grams_c.shape[1]
    rho = 4.0 * shells * eps + shells * np.sqrt(n_b) * eps + 2.0 * (n_c + 1) * eps * kappa
    fit = float(np.linalg.norm(i_live / norm_i - t_hat))
    record = Transfer(x=tuple(float(v) for v in x), cos=cos, mu=mu, rho=rho, lambda_prime=lam,
                      gamma=gamma, kappa=kappa, n_b=int(n_b), n_c=int(n_c), shells=int(shells),
                      fit=fit, float_stack=bool(mu < TRANSFER_FLOAT_STACK),
                      kernel_dim=int(kernel), kernel_residual=float(residual))
    return bool(cos < mu - rho), record


def _verify_transfer(witness: Witness, grams_b: np.ndarray, dark_b: np.ndarray,
                     grams_c: np.ndarray, record: Transfer) -> bool:
    """Re-check a stored :class:`Transfer` from its ``x`` against the two stacks: fires again, with the same numbers to 1e-9."""
    fires, again = _fit_transfer(witness, grams_b, dark_b, grams_c, record.x)
    if not fires or again is None:
        return False
    close = all(abs(getattr(again, name) - getattr(record, name)) <= 1e-9 * max(1.0, abs(getattr(record, name)))
                for name in ("cos", "mu", "rho", "kappa"))
    return bool(close and (again.n_b, again.n_c, again.shells) == (record.n_b, record.n_c, record.shells))


def _transfer_distance(source: PairVerdict, record: Transfer) -> tuple[float, float]:
    """The d bracket of a fit transfer: the source draw's bracket moved by the fit residual δ (triangle inequality), the lower end also by the cone.

    Î_c is within δ of t̂, so dist(Î_c, cone B) is within δ of dist(t̂,
    cone B); and Î_c is outside the cone {cos(ŷ, I) ≥ μ − ρ} that holds
    cone B by the angle arccos(cos) − arccos(μ − ρ), whose sine is a
    distance too.  The zero model bounds the relative distance by 1.
    """
    lower, upper = (0.0, 1.0) if source.d is None else source.d
    bound = max(float(min(record.mu - record.rho, 1.0)), -1.0)
    angle = float(np.arccos(max(min(record.cos, 1.0), -1.0)) - np.arccos(bound))
    cone = float(np.sin(min(max(angle, 0.0), np.pi / 2)))
    return (max(lower - record.fit, cone, 0.0), min(upper + record.fit, 1.0))


def _settle(target: tuple[int, int], new: PairVerdict,
            verdicts: dict[tuple[int, int], PairVerdict], copies: list[int], n: int) -> bool:
    """Record a transferred proof on ``target`` unless it is already proved: a proof the other way raises, as in :func:`_propagate`."""
    current = verdicts.get(target)
    if current is not None and current.proved:
        if current.status != new.status:
            raise RuntimeError(
                f"two certificates disagree: pair {target} is {current.status} by "
                f"{current.certificate}, while a {new.certificate} via {new.via} makes it "
                f"{new.status}; one of the two certificates is wrong")
        return False
    spent = current.draws if current is not None else 0
    verdicts[target] = replace(new, draws=spent, undecided_draws=0)
    _propagate(verdicts[target], verdicts, copies, n)
    return True


def _transfers(verdicts: dict[tuple[int, int], PairVerdict], copies: list[int],
               grams: list[np.ndarray], dark: list[np.ndarray], silent: list[bool], *,
               n: int, seed: int, rtol: float, restarts: int) -> None:
    """Carry every proved separation as far as the proved containments and the fit transfers take it (issue #565, items 5 and 6).

    Repeated to a fixed point, each new proof handed to :func:`_propagate`
    at once.  **Containment**, exact, reading ⊆ only from
    ``proved-contained`` verdicts (``span``, ``isometry``, a silent family,
    or those carried): for a ``proved-not`` a → b that rests on a point of
    ``a``'s image outside ``b``'s cone (a witness draw, or a transfer's
    I_c), A ⊆ A′ gives A′ ⊄ B with the same witness and bracket, and
    C ⊆ B gives A ⊄ C with the witness carried as evidence on ``b``'s
    stack and the bracket (d_lo, 1): the point is at least as far from
    the smaller cone, and the zero model bounds the distance by one.
    **Fit transfer**: for a verdict carrying a witness whose live shells
    are ``b``'s own, every ``c`` that the draws said reproduces ``a``
    (``sampled-contained`` or ``unresolved`` a → c) and whose c → b is not
    yet proved is fitted to the witness draw on a generator seeded
    (``seed``, a, b, c), once per witness and ``c``, and
    :func:`_fit_transfer` decides c ⊄ b or nothing.  A ``c`` proved not to
    contain ``a`` is not tried: a generic draw of ``a`` is then out of its
    reach by the certificate, or expected to be; a ``c`` proved to be
    inside ``b`` is not tried either, since nothing of its image can be
    outside ``b``.  Nothing sampled is ever read as a containment, and
    nothing is upgraded without a certificate: a direction a transfer
    refutes keeps the draws it had consumed, as a propagated proof does.
    Every productive pass settles at least one of the n(n − 1) directions
    for good, so the loop is bounded by that count; a pass that is still
    moving beyond it means a proof was overwritten, and raises rather than
    spin.
    """
    fits: dict[tuple[int, int], np.ndarray | None] = {}
    for _ in range(n * (n - 1) + 1):
        moved = False
        contained = [(v.a, v.b) for v in verdicts.values() if v.status == "proved-contained"]
        for key in sorted(verdicts):
            v = verdicts[key]
            if v.status != "proved-not" or (v.witness is None and v.transfer is None):
                continue
            for x, y in contained:
                if x == v.a and y != v.b:        # A ⊆ A′: the point is A′'s too
                    moved |= _settle((y, v.b), PairVerdict(
                        y, v.b, "proved-not", "containment", d=v.d, witness=v.witness,
                        dual=v.dual, transfer=v.transfer, via=(v.a, v.b)), verdicts, copies, n)
                elif y == v.b and x != v.a:      # C ⊆ B: the point is outside C's cone too
                    moved |= _settle((v.a, x), PairVerdict(
                        v.a, x, "proved-not", "containment",
                        d=None if v.d is None else (v.d[0], 1.0), witness=v.witness,
                        dual=v.dual, transfer=v.transfer, via=(v.a, v.b)), verdicts, copies, n)
        for key in sorted(verdicts):
            v = verdicts[key]
            if v.status != "proved-not" or v.witness is None or v.transfer is not None:
                continue
            a, b = v.a, v.b
            t = np.asarray(v.witness.t, dtype=np.float64)
            live_b = np.flatnonzero(_fit_rows(t, grams[b]) & ~dark[b])
            if tuple(int(s) for s in live_b) != tuple(v.witness.live):
                continue
            for c in range(n):
                if c in (a, b) or silent[c] or verdicts[(c, b)].proved \
                        or verdicts[(a, c)].status not in ("sampled-contained", "unresolved"):
                    continue
                fit_key = (id(v.witness), c)
                if fit_key not in fits:
                    fits[fit_key] = _transfer_fit(
                        t, grams[c], np.random.default_rng([seed, a, b, c]),
                        restarts=restarts, rtol=rtol)
                if fits[fit_key] is None:
                    continue
                fires, record = _fit_transfer(v.witness, grams[b], dark[b], grams[c], fits[fit_key])
                if fires:
                    moved |= _settle((c, b), PairVerdict(
                        c, b, "proved-not", "transfer", d=_transfer_distance(v, record),
                        witness=v.witness, dual=v.dual, transfer=record, via=(a, b)),
                        verdicts, copies, n)
        if not moved:
            return
    raise RuntimeError("the transfer pass did not settle within n(n - 1) rounds: a proved "
                       "verdict was replaced, which no certificate may do")


def powder_equivalent(a: MagneticCandidate, b: MagneticCandidate,
                      refl: ReflectionSet, *, draws: int | None = None, seed: int = 20260906,
                      rtol: float = 1e-4, restarts: int = 32,
                      little: LittleGroup | None = None, weights=None) -> bool:
    """Whether a powder pattern to ``refl``'s d limit can tell two candidates apart.

    **The definition, taken here.**  A and B are *powder-equivalent* when each
    can reproduce the other's powder intensity vector: for random amplitude
    draws of A — normalised to unit total moment, so a scale is never the
    discriminator — a least-squares fit of B's amplitudes reproduces A's
    intensities at every shell to ``rtol`` of A's largest, and the same with A
    and B exchanged.  It is a relation between *families*, not between points,
    which is why both directions are needed: a family with more amplitudes can
    imitate a smaller one without the reverse being true.

    This is Shirane's rule (1959) made mechanical.  For a collinear structure of
    cubic **configurational** symmetry the powder intensity does not depend on
    the moment direction, so the [100], [110] and [111] isotropy subgroups of
    one irrep come out equivalent, and a uniaxial one — where the angle to c
    *is* measurable — does not.  The qualifier is Shirane's own and is not
    decoration: his p. 285 example is MnO, cubic in its *chemical* cell and
    rhombohedral in its configurational symmetry, where the direction **is**
    measurable.  This function computes the classes from the intensities and so
    never has to decide which group the rule is about.

    **The boolean does not say how it was decided, and with the
    certificates in this release "equivalent" is sampled.**  Before any
    draw the pair goes through the certificates :class:`PairVerdict`
    states: a shell one family lights and the other cannot, or an intensity
    span not inside the other's, proves the pair *distinct* for almost
    every model, and then nothing is drawn.  During the draws, a draw no
    restart reproduces can be **proved** out of the other family's reach
    by a Farkas certificate (``farkas``, :class:`Witness`), at the caller's
    ``rtol``; then "distinct" is proved too, of that stored draw.  The
    equalities the certificates prove are two: two families with no
    pattern at all, and two whose Gram stacks are orthogonally congruent
    (``isometry``, :class:`Isometry`: the rank-1 copies of one irrep), so
    any other ``True`` rests on the draws below,
    and so does a ``False`` no certificate gave;
    :func:`powder_relations` returns which, direction by direction, with the
    number of draws each made.

    ``weights``, optional, is one positive number per shell of ``refl``
    (σ⁻¹ or f²·L, say): the Farkas certificate is then solved on the
    weighted stack, so its ``d`` is the weighted relative distance.  It
    changes which point is quoted and what ``d`` reads, not what is
    proved: the gate and the fit's ``rtol`` stay unweighted.

    **Both sampled verdicts are statistical, for different reasons** (issue #455).
    What is exact: a family with no powder pattern at this d limit is
    equivalent to anything (below), and the verdict no longer depends on the
    amplitude basis a candidate arrived in, beyond round-off, since
    :func:`_canonical_basis` fixes it from the span before any draw.
    Round-off is not always small here: on the cubic ``P n -3 m:1`` at
    (0,0,½), canonical bases agreeing to 9.2e-16 across three rotations
    still gave a partition that moved with the rotation at each of three
    seeds (2 to 4 classes over the nine runs).  What is not exact:

    * **"Distinguishable" can be a failure to fit** (mechanism A), where no
      certificate proved it.  It is returned when, for one draw, all
      ``restarts`` random starts of the other family's fit stop above
      ``rtol`` and the Farkas dual finds no certificate above the gate.  The fit's global minimum is
      zero whenever the answer should be "equivalent", but a restart can
      stop in a local minimum, and restarts on one draw are not independent
      trials: they share the draw, and some draws have a dominant wrong
      basin.  So no failure probability follows from ``restarts`` alone.
      On the five non-cubic cases of issue #455, measured with #534's frame
      fix, 21 of 32 equivalent pair-runs came out distinguishable at 4
      restarts.  At 32 with the early stop in :func:`_fit_residual` each case
      gives one partition across three seeds and three basis rotations, but
      2 of the same 192 equivalent draws were still not reproduced in 32
      restarts (both ``P 62 2 2``, pair 4-5), so 32 is usually enough there
      and not a margin.  More ``draws`` make this error *more* likely, not
      less.
    * **"Equivalent" can be a lucky set of draws** (mechanism B).  It is
      returned when every one of ``draws`` draws in each direction is
      reproduced.  The draws are independent, so if B reproduces only a
      fraction 1 − f of A's draws (it converges to a real non-zero minimum
      on the rest), the pair passes with probability (1 − f)^draws: 0.42 at
      f = ¼ and 3 draws, 0.03 at the 12 a pair across irreps now takes by
      default.  More restarts do not help.  Issue
      #455's example, ``P a -3`` at (½,½,½), was measured before #534's
      frame fix; with it that case gives one partition in 9 of 9 seed and
      basis runs.  Issue #565 measured B on six cubic cases instead: 8 % of
      their cross-irrep pairs were equivalent at 3 draws per direction and
      refuted by a draw within 12.  How small an f should still count as
      "distinguishable", and what the draws to detect it cost, are open
      (WP-1418), and this function does not settle them.

    A class count built on these verdicts is therefore a function of
    ``seed``, ``draws`` and ``restarts``, and across machines agrees only as
    far as the fits' floating point does.
    """
    weights = _shell_weights(weights, refl)
    if little is None:
        little = _irreps.little_group(a.space_group, a.k)
    a, b = _canonical_basis(a), _canonical_basis(b)
    fa = structure_factors(a, refl, little=little)
    fb = structure_factors(b, refl, little=little)
    return _powder_equivalent(a, b, fa, fb, gram(fa, refl.shells), gram(fb, refl.shells),
                              refl, draws=_draws_for(a, b, draws), seed=seed, rtol=rtol,
                              restarts=restarts, weights=weights)


def _powder_equivalent(a: MagneticCandidate, b: MagneticCandidate,
                       fa: np.ndarray, fb: np.ndarray, ga: np.ndarray, gb: np.ndarray,
                       refl: ReflectionSet, *,
                       draws: int, seed: int, rtol: float, restarts: int,
                       weights: np.ndarray | None = None) -> bool:
    """:func:`powder_equivalent` on canonical candidates whose factors and grams are built.

    ``ga``/``gb`` are ``gram(fa, refl.shells)``/``gram(fb, refl.shells)``, the
    only form the certificates, the draws and the fits read, so each is built
    once per candidate rather than once per draw.
    """
    silent = [_silent(fa), _silent(fb)]
    dark = [_certificate_dark(ga, silent[0]), _certificate_dark(gb, silent[1])]
    spans = [_intensity_span(ga), _intensity_span(gb)]
    decided = _isometry_verdicts(0, 1, ga, gb, dark, spans, silent)
    if not decided:
        little = _irreps.little_group(a.space_group, a.k)
        images = {}

        def patterns(index: int) -> list[np.ndarray]:
            if index not in images:
                images[index] = _domain_patterns((a, b)[index], little)
            return images[index]

        decided = _containment_verdicts(0, 1, (a, b), (ga, gb), dark, spans, silent, patterns)
    there, back = _pair_verdicts(0, 1, (a, b), (ga, gb), silent, dark, spans, refl,
                                 draws=draws, seed=seed, rtol=rtol, restarts=restarts,
                                 weights=weights, decided=decided)
    return bool(there.contained and back.contained)


def _isometry_verdicts(i: int, j: int, grams_i: np.ndarray, grams_j: np.ndarray, dark, spans,
                       silent) -> dict[tuple[int, int], PairVerdict]:
    """Both directions of the isometry certificate on one pair, or an empty dict.

    Tried only on a pair the family-level certificates leave open: an
    isometric pair has the same dark shells and the same intensity span, so
    an absence or subspace verdict on either direction rules it out, and a
    silent family is the absence certificate's.
    """
    if _certify(i, j, dark, spans, silent) is not None or \
            _certify(j, i, dark, spans, silent) is not None:
        return {}
    record = _isometry(grams_i, grams_j)
    if record is None:
        return {}
    # Q acts on a's amplitudes (QᵀG^j Q = G^i), so the (j, i) record is its transpose,
    # with the two residuals re-measured on the reversed stacks
    back = replace(record, q=tuple(zip(*record.q)))
    _, residual, orthogonality = _verify_isometry(grams_j, grams_i, back)
    back = replace(back, residual=residual, orthogonality=orthogonality)
    return {(i, j): PairVerdict(i, j, "proved-contained", "isometry", isometry=record),
            (j, i): PairVerdict(j, i, "proved-contained", "isometry", isometry=back)}


def _containment_verdicts(i: int, j: int, canonical, grams, dark, spans, silent,
                          patterns) -> dict[tuple[int, int], PairVerdict]:
    """The span-containment certificate on each direction of one pair the family-level certificates leave open.

    A direction with an absence or subspace verdict is not tried (a
    contained ``a`` lights nothing ``b`` is dark at and spans nothing
    outside V_b, so such a verdict already refutes it, and a silent ``a``
    is contained by absence).  Tried after the isometry: an isometric pair
    is contained both ways and keeps that label.
    """
    out = {}
    for a, b in ((i, j), (j, i)):
        if _certify(a, b, dark, spans, silent) is not None:
            continue
        record = _containment(canonical[a], grams[a], grams[b], patterns(b))
        if record is not None:
            out[(a, b)] = PairVerdict(a, b, "proved-contained", "span", containment=record)
    return out


def _shell_weights(weights, refl: ReflectionSet) -> np.ndarray | None:
    """``weights`` as one positive finite float per shell of ``refl``, or None; anything else is refused by name."""
    if weights is None:
        return None
    w = np.asarray(weights, dtype=np.float64).reshape(-1)
    if w.shape[0] != len(refl.shells):
        raise ValueError(f"weights has {w.shape[0]} entries and the reflection set has "
                         f"{len(refl.shells)} shells: one weight per shell, in refl.shells order")
    if not np.all(np.isfinite(w)) or not np.all(w > 0.0):
        raise ValueError("weights must be positive and finite on every shell: a zero weight "
                         "would drop a shell from the certificate, not down-weight it")
    return w


def _draws_for(a: MagneticCandidate, b: MagneticCandidate, draws: int | None) -> int:
    """Draws per direction for one pair: the caller's, or :data:`CROSS_IRREP_DRAWS`/:data:`WITHIN_IRREP_DRAWS`."""
    if draws is not None:
        return draws
    return WITHIN_IRREP_DRAWS if a.irrep_label == b.irrep_label else CROSS_IRREP_DRAWS


def _silent(factors: np.ndarray) -> bool:
    """Whether a family's M⊥ vanishes at every reflection of the set: no powder pattern at all.

    Nothing can then be distinguished from it — every shell is a systematic
    absence — and a draw would be fitting round-off (|F|max = 6.1e-16 for
    S4(a) of ``candidates("P n m a", (0, 0, 0.5), (0, 0, 0))`` at d_min =
    5.2).  Exact because M⊥ is linear in the amplitudes, and on the same
    tolerance as :func:`systematic_absences`, the authority for "this
    reflection is absent".  Yue's review of #389 found the coarse-d_min
    failure through the ``lm`` refusal in :func:`_fit_residual`; this is its
    second cause.
    """
    return float(np.max(np.abs(factors))) <= INTENSITY_RTOL


def _pair_verdicts(i: int, j: int, canonical, grams, silent, dark, spans,
                   refl: ReflectionSet, *, draws: int, seed: int, rtol: float,
                   restarts: int, weights: np.ndarray | None = None,
                   decided: dict[tuple[int, int], PairVerdict] | None = None
                   ) -> tuple[PairVerdict, PairVerdict]:
    """The two directed verdicts of one pair: certificates first, then the draws.

    ``decided`` holds verdicts settled before this pair was reached, by
    the isometry certificate or by propagation from an isometric copy
    (:func:`_classify`); a direction the family-level certificates leave
    open takes its entry there, and is not drawn.
    A pair a family-level certificate settles distinct is not drawn at all,
    and its other direction is recorded ``unresolved`` (``reason="settled"``)
    unless a certificate settles that too.  Otherwise each direction not
    proved contained is sampled, i → j first, on one generator seeded with
    ``seed`` — the stream, draw for draw, that this pair's test consumed
    before the certificates existed, so a pair no certificate settles gets
    the verdict it always had.  Each draw goes through
    :func:`_certify_draw`: a draw its Farkas certificate proves out of reach
    at ``rtol`` ends the direction ``proved-not`` (``farkas``, ``draws`` =
    that draw's index, the :class:`Witness` and its ``d`` attached), and
    the other direction is ``settled``.  The draws stop at the first one not
    reproduced, certified or not, as they always did; an uncertified one is
    ``sampled-not`` with the dual's optimum in ``dual`` (negative: no
    certificate exists for that draw) and any certificate below the gate as
    its witness.  ``draws`` on the verdict counts every draw taken from the
    generator: one whose pattern is zero everywhere is counted as
    reproduced, since ``b``'s zero model reproduces it, and is not fitted.
    """
    decided = decided or {}
    proved = {key: _certify(*key, dark, spans, silent) or decided.get(key)
              for key in ((i, j), (j, i))}
    if any(v is not None and v.status == "proved-not" for v in proved.values()):
        return tuple(proved[key] or PairVerdict(*key, "unresolved", reason="settled")
                     for key in ((i, j), (j, i)))
    rng = np.random.default_rng(seed)
    out: list[PairVerdict] = []
    for a, b in ((i, j), (j, i)):
        if proved[(a, b)] is not None:
            out.append(proved[(a, b)])
            continue
        if out and out[0].status in ("sampled-not", "proved-not"):
            out.append(PairVerdict(a, b, "unresolved", reason="settled"))
            continue
        made = 0
        verdict = None
        below_gate = None
        for _ in range(draws):
            amplitudes = _normalised_draw(canonical[a], refl.lattice, rng)
            made += 1
            target = (grams[a] @ amplitudes) @ amplitudes
            if float(np.max(np.abs(target))) <= 0.0:
                continue
            reproduced, certified, witness, dual = _certify_draw(
                target, grams[b], dark[b], rng, restarts=restarts, rtol=rtol, draw=made,
                weights=weights)
            if certified:
                verdict = PairVerdict(a, b, "proved-not", "farkas", made, 0,
                                      d=witness.d, witness=witness, dual=dual)
                break
            if not reproduced:
                verdict = PairVerdict(a, b, "sampled-not", None, made, 1,
                                      d=None if witness is None else witness.d,
                                      witness=witness, dual=dual)
                break
            below_gate = below_gate or witness
        out.append(verdict or PairVerdict(
            a, b, "sampled-contained", None, made, 0,
            d=None if below_gate is None else below_gate.d, witness=below_gate))
    return out[0], out[1]


def _classify(candidate_set: CandidateSet, refl: ReflectionSet, *, draws: int | None,
              seed: int, rtol: float, restarts: int, weights=None
              ) -> tuple[tuple[tuple[int, ...], ...], tuple[PairVerdict, ...]]:
    """:func:`equivalence_classes` and :func:`powder_relations` from one pass over the pairs.

    Four passes, the first two cheap.  (1) The family-level certificates
    on every ordered pair, and on every pair they leave open the isometry
    certificate and, where that fails, the span containment on each
    direction; isometric candidates are grouped (union-find over the
    isometry verdicts, ``copies``), and every proved verdict is carried to
    the pairs of copies (:func:`_propagate`).  (2) The pair loop as before,
    i < j in order, each direction drawn only if nothing has decided it;
    a Farkas proof is carried to the copies the moment it is found, so a
    later pair of copies is not drawn.  Union-find over the equivalent
    pairs joins as it always did, on the pair's own two verdicts.  (3) The
    transfers (:func:`_transfers`): every proved separation is carried
    along the proved containments and, by the sign-free bound, to the
    families that reproduce its witness, to a fixed point, each new proof
    propagated at once.  (4) The classes are read off.  A proof that lands
    on a pair an earlier sampled join made replaces the sampled verdict
    and leaves the join (the table names the class, part 5 splits it).
    Nothing sampled is carried.
    """
    weights = _shell_weights(weights, refl)
    little = _irreps.little_group(candidate_set.space_group, candidate_set.k)
    n = len(candidate_set)
    canonical = [_canonical_basis(c) for c in candidate_set]
    factors = [structure_factors(c, refl, little=little) for c in canonical]
    grams = [gram(f, refl.shells) for f in factors]
    silent = [_silent(f) for f in factors]
    dark = [_certificate_dark(g, quiet) for g, quiet in zip(grams, silent)]
    spans = [_intensity_span(g) for g in grams]
    parent = list(range(n))
    copies = list(range(n))
    images: dict[int, list[np.ndarray]] = {}

    def patterns(index: int) -> list[np.ndarray]:
        # a candidate's domain images, built once, on the first pair that needs them
        if index not in images:
            images[index] = _domain_patterns(canonical[index], little)
        return images[index]

    def find(i: int, tree: list[int] = parent) -> int:
        while tree[i] != i:
            tree[i] = tree[tree[i]]
            i = tree[i]
        return i

    verdicts: dict[tuple[int, int], PairVerdict] = {}
    certified = {(i, j): _certify(i, j, dark, spans, silent)
                 for i in range(n) for j in range(n) if i != j}
    for i in range(n):
        for j in range(i + 1, n):
            both = _isometry_verdicts(i, j, grams[i], grams[j], dark, spans, silent)
            if both:
                verdicts.update(both)
                copies[find(j, copies)] = find(i, copies)
            else:
                verdicts.update(_containment_verdicts(i, j, canonical, grams, dark, spans,
                                                      silent, patterns))
    for v in certified.values():
        if v is not None:
            _propagate(v, verdicts, copies, n)
    for i in range(n):
        for j in range(i + 1, n):
            decided = {key: verdicts[key] for key in ((i, j), (j, i)) if key in verdicts}
            if find(i) == find(j):
                # joined through other pairs: the certificates still run, since
                # a proof is not transitive the way a join is and a later rule
                # reads every one; only the draws are skipped
                proved = {key: certified[key] or decided.get(key) for key in ((i, j), (j, i))}
                reason = "settled" if any(v is not None and v.status == "proved-not"
                                          for v in proved.values()) else "joined"
                for key, v in proved.items():
                    verdicts[key] = v or PairVerdict(*key, "unresolved", reason=reason)
                continue
            there, back = _pair_verdicts(i, j, canonical, grams, silent, dark, spans, refl,
                                         draws=_draws_for(canonical[i], canonical[j], draws),
                                         seed=seed, rtol=rtol, restarts=restarts,
                                         weights=weights, decided=decided)
            verdicts[(i, j)], verdicts[(j, i)] = there, back
            for v in (there, back):
                if v.certificate == "farkas":
                    _propagate(v, verdicts, copies, n)
            if there.contained and back.contained:
                parent[find(j)] = find(i)
    _transfers(verdicts, copies, grams, dark, silent, n=n, seed=seed, rtol=rtol,
               restarts=restarts)
    groups: dict[int, list[int]] = {}
    for i in range(n):
        groups.setdefault(find(i), []).append(i)
    classes = tuple(tuple(members) for members in
                    sorted(groups.values(), key=lambda m: m[0]))
    return classes, tuple(verdicts[key] for key in sorted(verdicts))


def _propagate(source: PairVerdict, verdicts: dict[tuple[int, int], PairVerdict],
               copies: list[int], n: int) -> None:
    """Carry a proved verdict to every ordered pair of isometric copies of its two ends (issue #565, part 3).

    ``copies`` is the union-find forest over the isometry verdicts; a and
    b are copies when they share a root.  For every (a, b) with a ≅
    ``source.a`` and b ≅ ``source.b``, other than the source itself: a
    direction already proved must agree with the source (two proofs that
    disagree are a defect in a certificate, and raise rather than pick);
    anything else — undecided, sampled, unresolved — is replaced by the
    source's status under certificate ``propagated``, ``via`` the source
    pair, with its ``d``, ``witness``, ``dual`` and ``transfer`` (the witness is
    about the draw and a stack congruent to b's, so it re-verifies against
    b's own; a transfer's ``x`` stays in the amplitude basis of the *source's*
    c, ``via[0]``, and verifies against that family's stack).
    A sampled source carries nothing: only a ``proved-*`` status is read.
    """
    if not source.proved or source.certificate == "propagated":
        return

    def root(i: int) -> int:
        while copies[i] != i:
            copies[i] = copies[copies[i]]
            i = copies[i]
        return i

    ra, rb = root(source.a), root(source.b)
    for a in range(n):
        if root(a) != ra:
            continue
        for b in range(n):
            if b == a or root(b) != rb or (a, b) == (source.a, source.b):
                continue
            current = verdicts.get((a, b))
            if current is not None and current.proved:
                if current.status != source.status:
                    raise RuntimeError(
                        f"two certificates disagree: pair ({a}, {b}) is {current.status} by "
                        f"{current.certificate}, while its isometric copy "
                        f"({source.a}, {source.b}) is {source.status} by {source.certificate}; "
                        f"one of the two certificates is wrong")
                continue
            # a direction already drawn keeps the draws it consumed: the proof
            # replaces its verdict, not the count of what was spent on it
            spent = current.draws if current is not None else 0
            verdicts[(a, b)] = PairVerdict(a, b, source.status, "propagated", spent, 0,
                                           d=source.d, witness=source.witness,
                                           dual=source.dual, transfer=source.transfer,
                                           via=(source.a, source.b))


def equivalence_classes(candidate_set: CandidateSet, refl: ReflectionSet, *,
                        draws: int | None = None, seed: int = 20260906, rtol: float = 1e-4,
                        restarts: int = 32, weights=None) -> tuple[tuple[int, ...], ...]:
    """Connected components of :func:`powder_equivalent` over a candidate set.

    Members of one class are models a powder pattern to this d limit cannot
    separate; WP-1327's report names them, and M-9's workflow refines one
    representative per class rather than one per candidate.

    Each pair is settled by a certificate where one applies — a shell one
    family lights and the other cannot, or an intensity span not inside the
    other's (:class:`PairVerdict`) — and by :func:`powder_equivalent`'s
    draws otherwise, where a draw no fit reproduces can itself be proved
    out of reach (``farkas``).  The certificates prove two candidates
    *distinct*, or two equal when one has no pattern at all or the two are
    isometric copies (``isometry``), or one contained in the other
    (``span``); a proof carries to every pair of isometric copies
    (``propagated``), along every proved containment (``containment``) and,
    through a fit of the witness draw, to a third family that reproduces
    it (``transfer``), so every other join here rests on
    draws, and union-find carries each sampled verdict further: one false
    "equivalent" joins two classes, and one false "distinguishable" splits
    a class only if no other chain of pairs joins it.  Read the count as
    measured at this ``seed``, ``draws`` and ``restarts``, not as a
    property of the group; :func:`powder_relations` says which pair rests
    on what.  A proved separation can therefore sit inside a class that
    sampled pairs joined (``S7`` ⊄ ``S8`` with ``S7`` ~ ``S10`` ~ ``S8``):
    the printed table names such classes, and issue #565's part 5 splits
    them.  Each candidate's basis is made canonical and its structure
    factors and :func:`gram` stack built once, rather than once per pair or
    per draw.
    Cost: an equivalent pair mostly stops at its first restart, while a
    distinguishable one no family-level certificate settles pays one
    restart and a Farkas dual when the draw is certified, and the full
    ``restarts`` once when it is not.  ``weights`` is
    :func:`powder_equivalent`'s.

    ``draws`` is per direction.  Left at ``None`` it is
    :data:`CROSS_IRREP_DRAWS` for a pair of two irreps and
    :data:`WITHIN_IRREP_DRAWS` for two directions of one; an integer applies
    to every pair.  On the cubic ``P n -3 m:1`` at (0, 0, ½), general site,
    3 draws everywhere gives two classes (S1 ∪ S2 and S3 ∪ S4, each joined by
    lucky draws) and the default gives the four of the known answer, at
    1.7× the wall time (78.3 and 78.4 s against 134.9 and 135.6 s, one
    Linux x86-64 core per run, measured twice each, beside 3-7 other
    single-process tasks).
    """
    return _classify(candidate_set, refl, draws=draws, seed=seed, rtol=rtol,
                     restarts=restarts, weights=weights)[0]


def powder_relations(candidate_set: CandidateSet, refl: ReflectionSet, *,
                     draws: int | None = None, seed: int = 20260906, rtol: float = 1e-4,
                     restarts: int = 32, weights=None) -> tuple[PairVerdict, ...]:
    """Every directed verdict behind :func:`equivalence_classes`, with how each was decided.

    One :class:`PairVerdict` per ordered pair (a, b), sorted: proved by a
    certificate, sampled with the number of draws actually made, or
    unresolved where nothing tested that direction, with its ``reason``.
    The certificates run on every ordered pair; the draws are skipped on a
    pair union-find has already joined, on a direction proved contained
    (``span``) and on a direction a proof reached through an isometric
    copy (``propagated``); the transfers run after the draws and may
    replace a sampled verdict by a proof (``containment``, ``transfer``),
    which keeps the draws it had consumed.  The same pass, the same
    generator streams and the same partition as :func:`equivalence_classes`
    with these arguments.  A family-level certificate does not read
    ``rtol``; the Farkas one is gated on it (:class:`PairVerdict` states
    both).  A ``farkas`` verdict carries its :class:`Witness` and ``d``;
    ``weights`` is :func:`powder_equivalent`'s.
    """
    return _classify(candidate_set, refl, draws=draws, seed=seed, rtol=rtol,
                     restarts=restarts, weights=weights)[1]


def analyse(candidate_set: CandidateSet, *, d_min: float = 1.5,
            draws: int | None = None, seed: int = 20260906, rtol: float = 1e-4,
            restarts: int = 32, weights=None) -> CandidateSet:
    """Fill in the absences, the determinable amplitudes, the equivalence classes and their relations.

    Returns a new :class:`CandidateSet` whose ``__str__`` prints the whole
    classic table.  The reflection list is the magnetic cell's own to ``d_min``,
    on the cell the set was built with.

    ``weights``, when given, has one entry per shell of
    ``reflections(candidate_set.lattice, d_min)`` (see
    :func:`powder_equivalent`).

    Every column it fills is magnetic neutron intensity, so a
    ``kind="displacive"`` set is refused by name rather than given plausible
    numbers — see :func:`structure_factors`, which is where all three columns
    are computed.
    """
    if candidate_set.kind != "magnetic":
        raise ValueError(
            f"analyse fills in magnetic absences, determinable amplitudes and powder "
            f"equivalence classes, and this is a {candidate_set.kind!r} candidate set "
            f"for {candidate_set.site} of "
            f"{getattr(candidate_set.space_group, 'xhm', lambda: candidate_set.space_group)()}"
            f": see structure_factors, which every column goes through")
    refl = reflections(candidate_set.lattice, d_min)
    if len(refl) == 0:
        edges = ", ".join(f"{v:.4g}" for v in
                          np.linalg.norm(candidate_set.lattice, axis=1))
        raise ValueError(
            f"no reflection of the magnetic cell has d >= {d_min} Å, so there is "
            f"nothing to analyse: the cell edges are {edges} Å and d_min must be "
            f"below the longest of them")
    little = _irreps.little_group(candidate_set.space_group, candidate_set.k)
    determinable, absences = [], []
    for candidate in candidate_set:
        factors = structure_factors(candidate, refl, little=little)
        determinable.append(determinable_amplitudes(
            # determinable_amplitudes' own default, not a pair budget
            candidate, refl, draws=3 if draws is None else draws, seed=seed,
            little=little, factors=factors))
        absences.append(systematic_absences(candidate, refl, little=little).total)
    classes, relations = _classify(candidate_set, refl, draws=draws, seed=seed,
                                   rtol=rtol, restarts=restarts, weights=weights)
    return CandidateSet(
        space_group=candidate_set.space_group, site=candidate_set.site,
        k=candidate_set.k, kind=candidate_set.kind, cell=candidate_set.cell,
        lattice=candidate_set.lattice, representation=candidate_set.representation,
        candidates=candidate_set.candidates, classes=classes,
        determinable=tuple(determinable), absences=tuple(absences),
        relations=relations)
