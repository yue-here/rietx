"""Wyckoff identification and site-symmetry constraint bases.

Two independent jobs, deliberately split between two libraries:

* **Naming** — the Wyckoff letter and oriented site-symmetry symbol come from
  spglib (Togo, Shinohara & Tanaka, 2024, Sci. Technol. Adv. Mater. Meth. 4,
  2384822; BSD-3), which gemmi does not expose.  spglib identifies symmetry
  from an explicit atomic configuration, so a probe cell is built from the
  site's orbit plus one general-position orbit of a dummy species — the
  generic orbit pins the found group to exactly the requested one.
* **Constraint math** — the free-parameter bases are derived here from the
  gemmi operators by exact rational (``fractions.Fraction``) linear algebra,
  with no floating-point tolerance in the algebra itself:

  - Coordinates: a displacement δ of a site fixed by operations {(R, t)}
    must satisfy R·δ = δ; the basis spans ∩ ker(R − I) (International
    Tables A, sect. 8.3.2).
  - ADPs: the dimensionless U^ij tensor (CIF convention, reciprocal-basis
    representation) transforms as U → R·U·Rᵀ under a rotation R acting on
    fractional coordinates, so the allowed pattern spans the invariant
    subspace of that action on symmetric 3×3 matrices (Peterse & Palm, 1966,
    Acta Cryst. 20, 147; cross-check tables in Grosse-Kunstleve & Adams,
    2002, J. Appl. Cryst. 35, 477 — the cctbx implementation).

Both bases are returned as smallest-integer row vectors in a deterministic
(RREF-derived) form, e.g. an ``x,x,z`` site gives ``[[1, 1, 0], [0, 0, 1]]``
and a hexagonal 3-fold site gives ``U11=U22=2·U12`` as ``[2, 2, 0, 1, 0, 0]``.

ADP component order throughout: **(U11, U22, U33, U12, U13, U23)**.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd, lcm

import gemmi
import numpy as np
import spglib

from .symmetry import (
    SITE_TOL,
    OperatorGroup,
    as_group,
    expand_positions,
    site_orbit,
)

#: Index pairs of the symmetric-tensor components in storage order.
_VOIGT: tuple[tuple[int, int], ...] = ((0, 0), (1, 1), (2, 2), (0, 1), (0, 2), (1, 2))


@dataclass(frozen=True)
class SiteConstraints:
    """Symmetry constraints for one crystallographic site.

    ``coord_basis`` rows are free displacement directions in fractional
    coordinates: x(θ) = x₀ + Σₖ θₖ·row_k.  An empty (0, 3) array means the
    position is fully fixed.  ``adp_basis`` rows are allowed U-tensor
    patterns in (U11, U22, U33, U12, U13, U23) order: U(θ) = Σₖ θₖ·row_k.
    """

    wyckoff: str  # multiplicity + letter, e.g. "8g"
    site_symmetry: str  # oriented symbol from spglib, e.g. ".3m"
    multiplicity: int
    coord_basis: np.ndarray  # (n_free, 3) int
    adp_basis: np.ndarray  # (n_adp_free, 6) int


def stabilizer_rotations(sg: gemmi.SpaceGroup, xyz, *,
                         tol: float = SITE_TOL) -> list[np.ndarray]:
    """Integer rotation parts of every operation fixing ``xyz`` (mod 1).

    The stabilizer (site-symmetry group) of x is {(R, t) : R·x + t ≡ x mod 1};
    only the rotation parts matter for the constraint algebra because a
    displacement transforms without the translation.

    Read off :func:`~rietx.crystallography.symmetry.site_orbit` rather than
    recomputed, so the constraint bases below and the site multiplicity the
    forward model freezes are derived from the *same* set of operations.  Taken
    separately they can disagree: a threshold applied to each operation on its
    own admits a set that is not a subgroup, and then the allowed directions
    and the orbit length are answers to two different questions (issue #215).
    """
    return list(site_orbit(sg, xyz, tol=tol).stabilizer)


def _nullspace_int(rows: list[list[Fraction]], n_cols: int) -> np.ndarray:
    """Smallest-integer basis of the nullspace of a rational matrix.

    Exact Gauss-Jordan over ``Fraction`` (the inputs are integer matrices, so
    no tolerance enters), then each RREF-derived basis vector is scaled to
    coprime integers with its first nonzero entry positive.  The result is
    deterministic, which lets tests compare arrays exactly.
    """
    m = [row[:] for row in rows]
    pivots: list[int] = []
    r = 0
    for c in range(n_cols):
        pivot = next((i for i in range(r, len(m)) if m[i][c] != 0), None)
        if pivot is None:
            continue
        m[r], m[pivot] = m[pivot], m[r]
        inv = m[r][c]
        m[r] = [v / inv for v in m[r]]
        for i in range(len(m)):
            if i != r and m[i][c] != 0:
                f = m[i][c]
                m[i] = [a - f * b for a, b in zip(m[i], m[r])]
        pivots.append(c)
        r += 1
    free_cols = [c for c in range(n_cols) if c not in pivots]
    basis: list[list[int]] = []
    for c in free_cols:
        v = [Fraction(0)] * n_cols
        v[c] = Fraction(1)
        for i, pc in enumerate(pivots):
            v[pc] = -m[i][c]
        mult = lcm(*(f.denominator for f in v)) if v else 1
        ints = [int(f * mult) for f in v]
        g = gcd(*ints)
        ints = [a // max(g, 1) for a in ints]
        first = next((a for a in ints if a != 0), 1)
        if first < 0:
            ints = [-a for a in ints]
        basis.append(ints)
    return np.array(basis, dtype=np.int64).reshape(len(basis), n_cols)


def coordinate_basis(rotations: list[np.ndarray]) -> np.ndarray:
    """Integer basis of site-symmetry-invariant displacements, shape (k, 3).

    Solves R·δ = δ for every stabilizer rotation simultaneously: the stacked
    system (R − I)·δ = 0 over the rationals.
    """
    rows = [[Fraction(int(r[i][j]) - (i == j)) for j in range(3)]
            for r in rotations for i in range(3)]
    return _nullspace_int(rows, 3)


def adp_basis(rotations: list[np.ndarray]) -> np.ndarray:
    """Integer basis of allowed U^ij patterns, shape (m, 6).

    The linear action of a rotation on the 6 independent components of a
    symmetric tensor, A(R)[U] = R·U·Rᵀ, is built component-wise; the allowed
    patterns span ∩ ker(A(R) − I) (Peterse & Palm, 1966).
    """
    rows: list[list[Fraction]] = []
    for r in rotations:
        for a, (i, j) in enumerate(_VOIGT):
            # (R U Rᵀ)_ij = Σ_kl R_ik R_jl U_kl ; fold symmetric partners
            coeff = [0] * 6
            for b, (k, ll) in enumerate(_VOIGT):
                c = int(r[i][k]) * int(r[j][ll])
                if k != ll:
                    c += int(r[i][ll]) * int(r[j][k])
                coeff[b] = c
            rows.append([Fraction(coeff[b] - (a == b)) for b in range(6)])
    return _nullspace_int(rows, 6)


def _compatible_lattice(sg: gemmi.SpaceGroup) -> np.ndarray:
    """Row-vector lattice whose metric is invariant under the group.

    Averaging a generic metric over the point group, G = ⟨Rᵀ·G₀·R⟩, yields a
    metric compatible with whatever setting the operators are in (hexagonal
    axes, rhombohedral axes, non-standard monoclinic …) with no per-system
    case table; the Cholesky factor turns it into lattice row vectors for
    spglib.  Positive-definiteness survives the average (congruences of a
    positive-definite G₀).
    """
    g0 = np.array([[1.00, 0.05, 0.02],
                   [0.05, 1.21, 0.03],
                   [0.02, 0.03, 1.44]])
    rots = [np.array(op.rot, dtype=np.float64) / gemmi.Op.DEN for op in sg.operations()]
    g = sum(r.T @ g0 @ r for r in rots) / len(rots)
    return np.linalg.cholesky(g)


def site_constraints(space_group, xyz, *, tol: float = SITE_TOL) -> SiteConstraints:
    """Wyckoff letter, oriented site symmetry, and constraint bases for a site.

    ``space_group`` is any symbol gemmi resolves, or a group object from
    :func:`~rietx.crystallography.symmetry.resolve_group`; ``xyz`` is the
    fractional position of the site (values within ``tol`` of a special
    position count as on it).  Raises ``RuntimeError`` if spglib does not
    recover the requested group from the probe cell — that indicates
    coordinates given in a setting inconsistent with the operators, not a
    tolerance issue.  **The Wyckoff letter is spglib's**, so it is available
    only for a group spglib names; an
    :class:`~rietx.crystallography.symmetry.OperatorGroup` gets the constraint
    bases, the site symmetry and the multiplicity — which are all read off its
    own operations — and an empty letter.
    """
    sg = as_group(space_group)
    x = np.asarray(xyz, dtype=np.float64)

    # one expansion, so the constraint bases and the multiplicity below are
    # the same operations read two ways rather than two independent answers
    orbit = site_orbit(sg, x, tol=tol)
    rots = list(orbit.stabilizer)
    coord = coordinate_basis(rots)
    adp = adp_basis(rots)

    site_positions = [p for p in orbit.images]
    if isinstance(sg, OperatorGroup):
        # A group with no symbol has no Wyckoff *letter*: the letters are a
        # property of the tabulated type in its own setting, and spglib would
        # answer for the type it identifies from the probe cell — which for a
        # child cell whose glide translation is a quarter is the type, not the
        # setting, so the letter it returned would name a position of a
        # different cell.  Everything else here is read off this group's own
        # operations and is unaffected, so the letter and the oriented symbol
        # are left empty rather than filled with a plausible wrong one.
        return SiteConstraints(
            wyckoff="", site_symmetry="", multiplicity=orbit.multiplicity,
            coord_basis=coord, adp_basis=adp)
    # the dummy general-position orbit pins the probe cell's symmetry to
    # exactly this group; if the site itself sits near the first probe point,
    # fall back to the second so no two probe atoms coincide
    for generic in (np.array([0.1234, 0.5678, 0.9137]),
                    np.array([0.0821, 0.3179, 0.4317])):
        dummy_orbit = expand_positions(sg, generic, tol=1e-8)
        sep = min(np.max(np.abs(((p - q + 0.5) % 1.0) - 0.5))
                  for p in site_positions for q in dummy_orbit)
        if sep > 1e-3:
            break
    positions = list(site_positions) + [p for p in dummy_orbit]
    numbers = [1] * len(site_positions) + [2] * len(dummy_orbit)

    dataset = spglib.get_symmetry_dataset(
        (_compatible_lattice(sg), positions, numbers), symprec=1e-5)
    if dataset is None or dataset.number != sg.number:
        found = None if dataset is None else dataset.number
        raise RuntimeError(
            f"spglib identified space group {found}, expected {sg.number} "
            f"({sg.xhm()}): the coordinates are not consistent with this "
            "group's setting")

    return SiteConstraints(
        wyckoff=f"{orbit.multiplicity}{dataset.wyckoffs[0]}",
        site_symmetry=dataset.site_symmetry_symbols[0],
        multiplicity=orbit.multiplicity,
        coord_basis=coord,
        adp_basis=adp,
    )
