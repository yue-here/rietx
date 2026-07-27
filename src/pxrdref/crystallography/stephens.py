"""Stephens anisotropic strain broadening: the rank-4 S_HKL invariants.

Peak widths in the Caglioti/TCH laws (``model/profiles/caglioti.py``) depend on
hkl only through θ.  Real strained powders break that — (00l) and (hk0) can
differ threefold at the same 2θ — and Stephens' phenomenological model
(Stephens, 1999, J. Appl. Cryst. 32, 281) recovers it by letting every
crystallite carry its own lattice metric.  The spread of a *quadratic form's*
coefficients makes the variance of

    M_hkl ≡ 1/d²_hkl = h·G*·hᵀ                                       [Å⁻²]

a homogeneous **quartic** in (h, k, l):

    σ²(M) = 10⁻¹² · Σ_{H+K+L=4} S_HKL · h^H k^K l^L                     (1)

Fifteen monomials, hence at most fifteen coefficients.  Since
2θ = 2·arcsin(λ√M/2) gives d(2θ)/dM = tanθ/M, the contribution to the width in
the deg-2θ FWHM units the Lorentzian strain term already uses is

    Λ(hkl) = (180/π)·10⁻⁶·d²_hkl·√(Σ_HKL S_HKL h^H k^K l^L)          [deg]  (2)

Conventions (documented by physics, per the CLAUDE.md rule — codes differ)
-------------------------------------------------------------------------
* ``√(Σ S·monomial)·d²·10⁻⁶`` is the **FWHM** of the ΔM/M = 2·Δd/d
  distribution, *not* its standard deviation: no √(8 ln 2) appears anywhere.
  This is the practical convention of the implementing codes; the difference
  is one constant rescaling of every S_HKL.
* S_HKL are carried **in units of 10⁻¹² Å⁻⁴** — the 10⁻¹² of (1) and the 10⁻⁶
  of (2) are one convention seen twice.  It makes the isotropic limit read
  directly in ppm (:func:`isotropic_coefficients`) and it is *load-bearing
  numerically*: the shared finite-difference step in
  ``optimize/least_squares._peak_chain_column`` is ``1e-6·max(1, |θ|)``, i.e.
  absolute below 1, so a coefficient at its physical ~10⁻⁸ Å⁻⁴ magnitude would
  be differenced with a step 100× its own value.  Do not "tidy" these to
  physical Å⁻⁴.
* S_HKL multiply the **literal monomials** of (1).  Other codes fold symmetry
  multiplicities into their templates (writing the cubic S220 term as
  ``3·(h²k² + h²l² + k²l²)``, say), so their printed values differ from these
  by small integer factors as well as by their unit convention.  Never
  transfer a literature S_HKL without checking numerically.

Symmetry
--------
σ²(M) must be invariant under the Laue group.  Miller indices transform as
**h' = Rᵀh** (the reciprocal-space action; see ``symmetry.generate_reflections``),
which induces a 15×15 integer action on the monomial coefficients; the allowed
S_HKL span ∩ ker(A(R) − I).  That is the rank-4 twin of the rank-2 construction
``wyckoff.adp_basis`` uses for U^ij (Peterse & Palm, 1966, Acta Cryst. 20, 147),
so it shares that module's exact-rational nullspace kernel and needs no
per-Laue-class lookup table.  Degree 4 is inversion-even, so the point group
and its Laue class give the same subspace and no Laue classification is needed.

The derived dimensions reproduce Stephens' Table 1: m-3m 2, 6/mmm and 6/m 3,
-3m1 and -31m 4, -3 5, 4/mmm 4, 4/m 5, mmm 6, 2/m 9, -1 15.
"""

from __future__ import annotations

from fractions import Fraction

import numpy as np

from ..backend import get_backend
from .lattice import reciprocal_metric_tensor
from .symmetry import get_spacegroup, rotation_matrices

# The exact-rational nullspace is the same kernel the rank-2 ADP basis uses;
# importing it keeps the two constructions from drifting apart.
from .wyckoff import _nullspace_int

#: Exponent triples (H, K, L) of the fifteen quartic monomials h^H k^K l^L,
#: in descending lexicographic order — the storage order everywhere.
S_EXPONENTS: tuple[tuple[int, int, int], ...] = tuple(
    (h, k, 4 - h - k) for h in range(4, -1, -1) for k in range(4 - h, -1, -1)
)

#: Component names in :data:`S_EXPONENTS` order (``s400``, ``s310``, …).
S_NAMES: tuple[str, ...] = tuple(f"s{h}{k}{ll}" for h, k, ll in S_EXPONENTS)

_S_INDEX = {e: i for i, e in enumerate(S_EXPONENTS)}

#: σ²(M) floor in the scaled units of (1).  Real coefficients put Σ at 10⁰-10⁶,
#: so this is unreachably small; its job is to keep the √ real and — through
#: ``maximum``'s zero subgradient below the floor — to make an all-zero block a
#: *dead* column rather than the infinite one √ has at the origin.  Freeing an
#: all-zero block is rejected upstream (``params.vector``), not papered over.
_MIN_SIGMA2 = 1e-20

_DEG_PER_RAD = 180.0 / np.pi


# ----------------------------------------------------------------------
# symmetry-allowed subspace
# ----------------------------------------------------------------------
def _substitute(exponents: tuple[int, int, int], rot_t: np.ndarray
                ) -> dict[tuple[int, int, int], Fraction]:
    """Expand h^H k^K l^L after the substitution h → Rᵀh, as a monomial dict."""
    poly: dict[tuple[int, int, int], Fraction] = {(0, 0, 0): Fraction(1)}
    for comp, power in enumerate(exponents):
        for _ in range(power):
            grown: dict[tuple[int, int, int], Fraction] = {}
            for exps, coeff in poly.items():
                for j in range(3):
                    c = int(rot_t[comp][j])
                    if c == 0:
                        continue
                    e = list(exps)
                    e[j] += 1
                    key = (e[0], e[1], e[2])
                    grown[key] = grown.get(key, Fraction(0)) + coeff * c
            poly = grown
    return poly


def _invariance_rows(rot_t: np.ndarray) -> list[list[Fraction]]:
    """Rows of A(Rᵀ) − I on the fifteen quartic monomial coefficients."""
    n = len(S_EXPONENTS)
    action = [[Fraction(0)] * n for _ in range(n)]
    for a, exps in enumerate(S_EXPONENTS):
        for image, coeff in _substitute(exps, rot_t).items():
            action[_S_INDEX[image]][a] += coeff
    return [[action[b][a] - (Fraction(1) if a == b else Fraction(0)) for a in range(n)]
            for b in range(n)]


def strain_basis(rotations) -> np.ndarray:
    """Integer basis of allowed S_HKL patterns, shape (m, 15).

    ``rotations`` are the *real-space* integer rotation parts (as
    ``symmetry.rotation_matrices`` returns them); the reciprocal-space action
    Rᵀ is taken here, matching ``symmetry.reflection_orbits``.  Rows are
    smallest-integer and RREF-deterministic, so tests may compare them exactly:
    S(θ) = Σₖ θₖ·row_k.
    """
    rows: list[list[Fraction]] = []
    seen: set[tuple[int, ...]] = set()
    for r in np.asarray(rotations, dtype=np.float64):
        rot_t = np.rint(r.T).astype(np.int64)
        key = tuple(rot_t.ravel().tolist())
        if key in seen:  # centring translations repeat the rotation parts
            continue
        seen.add(key)
        rows.extend(_invariance_rows(rot_t))
    return _nullspace_int(rows, len(S_EXPONENTS))


def stephens_basis(space_group: str) -> np.ndarray:
    """:func:`strain_basis` for a space-group symbol gemmi resolves."""
    return strain_basis(rotation_matrices(get_spacegroup(space_group)))


# ----------------------------------------------------------------------
# evaluation
# ----------------------------------------------------------------------
def monomial_matrix(hkl: np.ndarray) -> np.ndarray:
    """(N, 15) matrix of h^H k^K l^L — σ²(M) is ``M @ s`` in the units of (1).

    Frozen per stage: the hkl list does not change inside a least-squares run,
    so this is built once at compile and reused for every residual evaluation.
    """
    h = np.asarray(hkl, dtype=np.float64)
    return np.column_stack([h[:, 0] ** e[0] * h[:, 1] ** e[1] * h[:, 2] ** e[2]
                            for e in S_EXPONENTS])


def sigma2_m(monomials: np.ndarray, s: np.ndarray) -> np.ndarray:
    """Σ_HKL S_HKL h^H k^K l^L per reflection — σ²(M) in the units of (1).

    Unfloored on purpose: a negative value means the coefficients have left the
    physical cone (σ² of a real distribution cannot be negative), which is what
    the ``STEPHENS_STRAIN_NOT_POSITIVE`` guard tests for.  The width function
    floors its own copy.
    """
    return get_backend().asarray(monomials, dtype=np.float64) @ s


def strain_width_deg(monomials: np.ndarray, s: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Λ(hkl) of equation (2): the tanθ coefficient, deg 2θ FWHM.

    ``d`` moves with the cell, so this is evaluated per residual call rather
    than cached; ``monomials`` is the frozen compile-time matrix.
    """
    xp = get_backend()
    sigma2 = xp.maximum(sigma2_m(monomials, s), _MIN_SIGMA2)
    return (_DEG_PER_RAD * 1e-6) * d * d * xp.sqrt(sigma2)


# ----------------------------------------------------------------------
# the isotropic limit — an exact point of the allowed subspace
# ----------------------------------------------------------------------
def isotropic_coefficients(cell: tuple[float, float, float, float, float, float],
                           microstrain: float) -> np.ndarray:
    """S_HKL giving σ(M)/M ≡ ``microstrain``·10⁻⁶ for every reflection.

    M is itself a Laue invariant, so **M² is a quartic that always lies in the
    allowed subspace**: expanding (h·G*·hᵀ)² and scaling by the strain squared
    reaches the isotropic limit *exactly*, whatever the symmetry.  That makes it
    the natural starting point for a refinement (the rank-4 analogue of
    ``adp.isotropic_u6``), and the units of (1) make the algebra cancel — with
    the strain given in ppm the coefficients are simply ``microstrain²·[M²]``.

    Starting from it is not optional in practice: at S ≡ 0 the √ of (2) has
    infinite slope, so a refinement started from zero takes a garbage first
    step, and σ²(M) > 0 for every hkl is guaranteed only inside the cone this
    ray sits at the centre of.
    """
    gstar = np.asarray(reciprocal_metric_tensor(*cell), dtype=np.float64)
    quad: dict[tuple[int, int, int], float] = {}
    for i in range(3):
        for j in range(3):
            e = [0, 0, 0]
            e[i] += 1
            e[j] += 1
            key = (e[0], e[1], e[2])
            quad[key] = quad.get(key, 0.0) + float(gstar[i, j])
    out = np.zeros(len(S_EXPONENTS), dtype=np.float64)
    for ea, ca in quad.items():
        for eb, cb in quad.items():
            out[_S_INDEX[(ea[0] + eb[0], ea[1] + eb[1], ea[2] + eb[2])]] += ca * cb
    return float(microstrain) ** 2 * out
