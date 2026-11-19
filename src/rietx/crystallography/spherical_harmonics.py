"""Symmetrised spherical harmonics for a texture correction.

The spherical-harmonics texture correction (Von Dreele, 1997, J. Appl. Cryst.
30, 517, his eq. 2-3 after Bunge, 1982, *Texture Analysis in Materials
Science*, ch. 14) multiplies each reflection's intensity by

    P_h = 1 + Σ_{l = 2, 4, …, L} (4π/(2l+1)) · Σ_n C_l^n · k_l(ψ) · K_l^n(h)

This module owns the crystal half, K_l^n(h): which functions a Laue class
allows, in which frame, and their values at a reflection.

Conventions
-----------
* **Harmonics** are Bunge's (his 14.38-14.39 and 14.61-14.63): real,
  orthonormal over the sphere (∮ K² dΩ = 1), and **without** the
  Condon-Shortley phase, so P̄_1^1 = +(√3/2)·sin φ.  φ is the polar angle and
  β the azimuth of the reflection's reciprocal vector in the frame below.
  For n > 0 the cosine and sine functions are π^(-1/2)·P̄_l^n·cos nβ and
  π^(-1/2)·P̄_l^n·sin nβ, and the n = 0 one is (2π)^(-1/2)·P̄_l^0.
* **Names follow GSAS-II's C(l, n)** (``GSASIIlattice.GenSHCoeffT``), so a
  coefficient maps one to one.  In a class with mirrors, (l, n) is the cosine
  or sine function the operators allow.  In a mirror-free class both are
  allowed, and GSAS-II puts (l, n) on cos nβ + sin nβ and (l, −n) on
  cos nβ − sin nβ.  Those have norm² 2, so this module divides them by √2.
  The coefficient is then GSAS-II's times √2 (WP-1960 § Pinned by Task 1).
  Cubic functions are numbered n = 1, 2, … within each l, as GSAS-II's are.
* **Only even l.**  A powder pattern obeys Friedel's law, so odd l cannot be
  measured (Von Dreele, 1997, §2).  Inversion then acts trivially, and each
  improper operation is replaced by its proper part.

The frame
---------
The polar axis z lies on the principal symmetry axis, and x on the next
cell edge, projected perpendicular to z.  The polar axis is the n-fold axis
of highest order in every class except the cubic and orthorhombic ones,
where it is c, and the triclinic one, where it is c*.  The next cell edge is b
when z lies along a, c when z lies along b, and a otherwise.  So a
c-unique class has z ∥ c* and x ∥ a (Popa, 1992, J. Appl. Cryst. 25, 611,
his eq. 24a, and GSAS-II's ``CrsAng``).  The monoclinic b setting has z ∥ b
and x ∥ c (Popa's second setting), and rhombohedral axes have z ∥ [111].

Symmetry
--------
Miller indices transform as **h' = Rᵀh**, so a reciprocal vector g = M⁻ᵀh
transforms as g' = M⁻ᵀRᵀMᵀ·g, the inverse of the Cartesian rotation M·R·M⁻¹.
Per l, the allowed functions are the range of the Reynolds projector, the
mean over the Laue group of that action on the 2l+1 real harmonics.  The
transposed trap of ``wyckoff.adp_basis`` waits here too: the untransposed
set is also a group, so it gives a subspace of the right dimension in every
class.  Only a test that the true orbit average lies in the span catches it.

A class's canonical functions are checked against the projector rather
than trusted.  A non-cubic candidate is either inside the range or
orthogonal to it.  A frame off a symmetry element mixes cosine and sine and
fails that check.  The cubic classes have no per-n functions, so their
basis is built from the projector, the m-3m functions first.  m-3 therefore
shares m-3m's functions and adds its own (at l = 6, one GSAS-II lacks).
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cache

import numpy as np

from ..backend import get_backend
from .adp import cartesian_basis
from .symmetry import as_group, cell_constraints, group_key, rotation_matrices

#: Tolerance on a projector check.  The projector is built by least squares
#: on exact samples, so a member of its range comes back to about 1e-14.
_TOL = 1e-9


@dataclass(frozen=True)
class TextureTerm:
    """One coefficient: its order ``l``, GSAS-II's index ``n``, and its name."""

    degree: int
    n: int
    name: str


def term_name(degree: int, n: int) -> str:
    """``c4_0``, ``c4_4``, ``c4_neg4``: GSAS-II's C(l, n) with no bracket or comma."""
    return f"c{degree}_{n}" if n >= 0 else f"c{degree}_neg{-n}"


# ----------------------------------------------------------------------
# the real harmonics
# ----------------------------------------------------------------------
def real_harmonics(degree: int, u):
    """The 2l+1 real orthonormal harmonics of unit vectors ``u``, shape (N, 2l+1).

    Column ``l + n`` holds the cosine function for n > 0, the sine function of
    |n| for n < 0, and the n = 0 function at column ``l``.  Built by the
    normalised Legendre recurrence on z with (x + iy)^n carrying sin^n φ·e^(inβ),
    so no angle is computed and the poles are not special.  Every step is an
    array operation, so ``u`` may be any backend's array.
    """
    xp = get_backend()
    u = xp.asarray(u, dtype=np.float64)
    x, y, z = u[:, 0], u[:, 1], u[:, 2]
    # q[n] holds P̄_l^n / sin^n φ for the current l, built column by column.
    cols = [None] * (2 * degree + 1)
    re, im = xp.full_like(x, 1.0), xp.zeros_like(x)  # Re and Im of (x + iy)^n
    q_nn = 1.0 / np.sqrt(2.0)  # P̄_0^0
    for n in range(degree + 1):
        if n > 0:
            q_nn *= np.sqrt((2 * n + 1) / (2 * n))
            re, im = re * x - im * y, im * x + re * y
        # Recurrence in degree at fixed n, from P̄_n^n up to P̄_l^n.
        prev2 = None
        prev = xp.full_like(z, q_nn)
        for j in range(n + 1, degree + 1):
            a = np.sqrt((4 * j * j - 1) / (j * j - n * n))
            if prev2 is None:
                cur = a * z * prev
            else:
                b = np.sqrt(((j - 1) ** 2 - n * n) / (4 * (j - 1) ** 2 - 1))
                cur = a * (z * prev - b * prev2)
            prev2, prev = prev, cur
        if n == 0:
            cols[degree] = prev / np.sqrt(2.0 * np.pi)
        else:
            cols[degree + n] = prev * re / np.sqrt(np.pi)
            cols[degree - n] = prev * im / np.sqrt(np.pi)
    return xp.stack(cols, axis=1)


# ----------------------------------------------------------------------
# the frame
# ----------------------------------------------------------------------
@dataclass(frozen=True)
class FrameRule:
    """Where the frame's z and x sit, read off the operators once.

    ``polar`` is a direct-lattice vector [uvw] for z, or ``None`` for c*.
    ``x_edge`` is the cell edge (0 = a, 1 = b, 2 = c) projected for x.
    ``cubic`` marks the classes whose basis comes from the projector alone.
    """

    polar: tuple[int, int, int] | None
    x_edge: int
    cubic: bool


def _proper_rotations(rotations) -> list[np.ndarray]:
    seen, out = set(), []
    for r in np.asarray(rotations, dtype=np.float64):
        r = np.rint(r).astype(np.int64)
        if round(np.linalg.det(r)) < 0:
            r = -r
        key = tuple(r.ravel())
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _axis(r: np.ndarray) -> tuple[int, int, int]:
    """The rotation's axis as a primitive integer [uvw] with a positive leading entry."""
    w, v = np.linalg.eig(r.astype(np.float64))
    vec = np.real(v[:, np.argmin(np.abs(w - 1.0))])
    vec = vec / np.max(np.abs(vec))
    ints = np.rint(vec * 6).astype(np.int64)
    ints //= np.gcd.reduce(ints[ints != 0])
    if ints[np.nonzero(ints)[0][0]] < 0:
        ints = -ints
    return (int(ints[0]), int(ints[1]), int(ints[2]))


def _order(r: np.ndarray) -> int:
    return {3: 1, -1: 2, 0: 3, 1: 4, 2: 6}[int(round(np.trace(r)))]


def frame_rule(rotations) -> FrameRule:
    """The :class:`FrameRule` the operators imply (module docstring, § The frame)."""
    axes: dict[tuple[int, int, int], int] = {}
    for r in _proper_rotations(rotations):
        order = _order(r)
        if order > 1:
            ax = _axis(r)
            axes[ax] = max(axes.get(ax, 0), order)
    threefold = [ax for ax, order in axes.items() if order == 3]
    top = max(axes.values(), default=1)
    if len(threefold) > 1:
        polar, cubic = (0, 0, 1), True
    elif top >= 3:
        (polar,) = [ax for ax, order in axes.items() if order == top]
        cubic = False
    elif len(axes) == 1:
        (polar,) = axes
        cubic = False
    elif len(axes) == 3:
        polar, cubic = (0, 0, 1), False
    else:
        polar, cubic = None, False
    edge = {(1, 0, 0): 1, (0, 1, 0): 2}.get(polar, 0)
    return FrameRule(polar, edge, cubic)


def _frame_rows(rule: FrameRule, m, m_inv, xp):
    """Rows x, y, z of the texture frame, from M and M⁻¹ in array namespace ``xp``.

    M holds the direct lattice vectors as columns and M⁻¹ the reciprocal ones
    as rows, so c* is the third row of M⁻¹.  The cross product is written out
    because no backend op provides it.
    """
    if rule.polar is None:
        z = m_inv[2]
    else:
        z = xp.matmul(m, xp.asarray(rule.polar, dtype=np.float64))
    z = z / xp.sqrt(xp.sum(z * z))
    edge = m[:, rule.x_edge]
    x = edge - xp.sum(edge * z) * z
    x = x / xp.sqrt(xp.sum(x * x))
    y = xp.stack([z[1] * x[2] - z[2] * x[1],
                  z[2] * x[0] - z[0] * x[2],
                  z[0] * x[1] - z[1] * x[0]])
    return xp.stack([x, y, z])


def frame_matrix(rule: FrameRule, cell) -> np.ndarray:
    """Rows x, y, z of the texture frame in the cell's Cartesian frame.

    The Cartesian frame is ``adp.cartesian_basis``'s (x ∥ a, z ∥ c*).
    """
    m = np.asarray(cartesian_basis(*cell), dtype=np.float64)
    return _frame_rows(rule, m, np.linalg.inv(m), np)


def reflection_directions(hkl, rule: FrameRule, cell):
    """Unit reciprocal vectors of ``hkl`` in the texture frame, shape (N, 3).

    The frame follows the cell, so a refined cell turns it.  Built on the
    closed-form ``params.derived.cartesian_frame`` and its inverse (the frame
    ``adp.cartesian_basis`` builds by Cholesky), so every step is an array
    operation of the active backend and the traced twin takes it unchanged.
    """
    from ..params.derived import cartesian_frame, fractional_frame

    xp = get_backend()
    m, m_inv = cartesian_frame(cell), fractional_frame(cell)
    g = xp.matmul(xp.asarray(hkl, dtype=np.float64), m_inv)
    g = xp.einsum("ni,ki->nk", g, _frame_rows(rule, m, m_inv, xp))
    return g / xp.sqrt(xp.sum(g * g, axis=1))[:, None]


def frame_rotations(rotations, rule: FrameRule, cell) -> list[np.ndarray]:
    """The Laue group's action on reciprocal vectors, in the texture frame.

    h → Rᵀh sends g = M⁻ᵀh to (M·R·M⁻¹)ᵀ·g.  Improper operations enter as their
    proper part, which acts identically on even-l harmonics.
    """
    m = cartesian_basis(*cell)
    m_inv = np.linalg.inv(m)
    f = frame_matrix(rule, cell)
    out = []
    for r in _proper_rotations(rotations):
        q = (m @ r @ m_inv).T
        if not np.allclose(q @ q.T, np.eye(3), atol=1e-8):
            raise ValueError("the cell does not have the symmetry of the operators")
        out.append(f @ q @ f.T)
    return out


# ----------------------------------------------------------------------
# the projector and the basis
# ----------------------------------------------------------------------
@cache
def _sample_points(degree: int) -> np.ndarray:
    """Fibonacci points on the sphere, three per harmonic: an exact least-squares fit."""
    return sphere_points(3 * (2 * degree + 1) + 8)


@cache
def sphere_points(n: int) -> np.ndarray:
    """``n`` near-uniform unit vectors on the sphere (a Fibonacci lattice), (n, 3)."""
    k = np.arange(n) + 0.5
    z = 1.0 - 2.0 * k / n
    phi = np.pi * (1.0 + 5.0**0.5) * k
    s = np.sqrt(1.0 - z * z)
    return np.column_stack([s * np.cos(phi), s * np.sin(phi), z])


def _harmonics_np(degree: int, u: np.ndarray) -> np.ndarray:
    return np.asarray(real_harmonics(degree, u), dtype=np.float64)


def projector(degree: int, frame_rots) -> np.ndarray:
    """The Reynolds projector on the 2l+1 real harmonics of order ``l``.

    For a rotation Q, f(Q·u) has coefficients T(Q)·c when f(u) has c; T(Q) is
    read off by least squares from points where both sides are exact.  The
    projector is the mean of T over the group, symmetric and idempotent.
    """
    u = _sample_points(degree)
    y = _harmonics_np(degree, u)
    rotated = np.hstack([_harmonics_np(degree, u @ q.T) for q in frame_rots])
    mats = np.linalg.lstsq(y, rotated, rcond=None)[0]
    return mats.reshape(y.shape[1], len(frame_rots), y.shape[1]).mean(axis=1)


def _cos_index(degree: int, n: int) -> int:
    return degree + n


def _sin_index(degree: int, n: int) -> int:
    return degree - n


def _unit(degree: int, i: int) -> np.ndarray:
    e = np.zeros(2 * degree + 1)
    e[i] = 1.0
    return e


def _in_range(p: np.ndarray, v: np.ndarray, what: str) -> bool:
    image = p @ v
    if np.linalg.norm(image - v) < _TOL:
        return True
    if np.linalg.norm(image) < _TOL:
        return False
    raise ValueError(f"{what} is neither allowed nor forbidden by the operators: "
                     "the frame does not sit on a symmetry element")


def _non_cubic_terms(degree: int, p: np.ndarray) -> list[tuple[int, np.ndarray]]:
    terms: list[tuple[int, np.ndarray]] = []
    if _in_range(p, _unit(degree, degree), f"(l={degree}, n=0)"):
        terms.append((0, _unit(degree, degree)))
    for n in range(1, degree + 1):
        c, s = _unit(degree, _cos_index(degree, n)), _unit(degree, _sin_index(degree, n))
        has_c = _in_range(p, c, f"cos {n}β at l={degree}")
        has_s = _in_range(p, s, f"sin {n}β at l={degree}")
        if has_c and has_s:
            terms += [(n, (c + s) / np.sqrt(2.0)), (-n, (c - s) / np.sqrt(2.0))]
        elif has_c:
            terms.append((n, c))
        elif has_s:
            terms.append((n, s))
    return sorted(terms, key=lambda t: t[0])


def _canonical(span: np.ndarray, degree: int, against: list[np.ndarray]) -> list[np.ndarray]:
    """Orthonormal functions of ``span`` outside ``against``, in a fixed order.

    Candidates are tried cosine first by n ≡ 0 (mod 4), then the other cosines,
    then the sines, each projected and Gram-Schmidt reduced.  The sign makes
    the first n > 0 cosine coefficient positive, which is the sign GSAS-II's
    cubic functions carry (``tests/test_spherical_harmonics.py`` checks it).
    """
    order = ([_cos_index(degree, n) for n in range(0, degree + 1, 4)]
             + [_cos_index(degree, n) for n in range(0, degree + 1) if n % 4]
             + [_sin_index(degree, n) for n in range(1, degree + 1)])
    found = list(against)
    out = []
    for i in order:
        v = span @ (span.T @ _unit(degree, i))
        for w in found:
            v = v - (w @ v) * w
        if np.linalg.norm(v) < 1e-6:
            continue
        v = v / np.linalg.norm(v)
        lead = [v[_cos_index(degree, n)] for n in range(1, degree + 1)
                if abs(v[_cos_index(degree, n)]) > _TOL]
        if (lead[0] if lead else v[np.argmax(np.abs(v) > _TOL)]) < 0:
            v = -v
        found.append(v)
        out.append(v)
    return out


def _range(p: np.ndarray) -> np.ndarray:
    w, v = np.linalg.eigh((p + p.T) / 2.0)
    return v[:, w > 0.5]


def _rank(p: np.ndarray) -> int:
    return int(np.sum(np.linalg.eigvalsh((p + p.T) / 2.0) > 0.5))


#: The 4-fold about z that turns m-3 into m-3m, in the cubic texture frame.
_C4Z = np.array([[0.0, -1.0, 0.0], [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]])


def _cubic_terms(degree: int, frame_rots, p: np.ndarray) -> list[tuple[int, np.ndarray]]:
    group = list(frame_rots)
    oh = group + [_C4Z @ q for q in group]
    full = _canonical(_range(projector(degree, oh)), degree, [])
    rest = _canonical(_range(p), degree, full)
    return [(k + 1, v) for k, v in enumerate(full + rest)]


@dataclass(frozen=True)
class TextureBasis:
    """The allowed functions to a declared order, frozen per stage.

    ``coefficients[i]`` holds term i's coefficients on :func:`real_harmonics`
    of its degree.  The values at a reflection follow the cell through the
    frame, so they are evaluated per cell (:meth:`at_reflections`).
    """

    order: int
    rule: FrameRule
    terms: tuple[TextureTerm, ...]
    coefficients: tuple[np.ndarray, ...]

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(t.name for t in self.terms)

    def evaluate(self, directions):
        """K for each term at unit vectors in the texture frame, shape (N, n_terms)."""
        xp = get_backend()
        cols = []
        for degree in sorted({t.degree for t in self.terms}):
            y = real_harmonics(degree, directions)
            for term, coef in zip(self.terms, self.coefficients):
                if term.degree == degree:
                    cols.append(y @ xp.asarray(coef, dtype=np.float64))
        return xp.stack(cols, axis=1)

    def at_reflections(self, hkl, cell) -> np.ndarray:
        """K for each term at each reflection of ``hkl`` under ``cell``."""
        return np.asarray(self.evaluate(reflection_directions(hkl, self.rule, cell)))


def _symmetric_cell(group, cell) -> tuple[float, ...]:
    """``cell`` with the setting's ties and fixed angles applied exactly.

    ``ParameterTable`` accepts a fixed angle up to
    ``symmetry.SYMMETRY_ANGLE_TOL_DEG`` from its value and a tied length up to
    ``symmetry.SYMMETRY_LENGTH_RTOL`` from its source, while
    :func:`frame_rotations` and the projector check
    hold to about 1e-9.  The coefficients do not depend on the free values, so
    the basis is built on the cell the symmetry demands.
    """
    names = ("a", "b", "c", "alpha", "beta", "gamma")
    values = dict(zip(names, (float(v) for v in cell), strict=True))
    constraints = cell_constraints(group)
    values.update(constraints.fixed_angles)
    for dependent, source in constraints.ties.items():
        values[dependent] = values[source]
    return tuple(values[n] for n in names)


def texture_basis(space_group, order: int, cell) -> TextureBasis:
    """Every function the Laue class allows from l = 2 to ``order``.

    ``order`` must be even and at least 2.  ``cell`` fixes the frame's
    Cartesian axes.  Its tied lengths and fixed angles are taken at the values
    the symmetry demands, and the coefficients do not depend on its free
    values.
    """
    if order < 2 or order % 2:
        raise ValueError(f"texture order {order}: it must be even and at least 2")
    group = as_group(space_group)
    rotations = rotation_matrices(group)
    rule = frame_rule(rotations)
    rots = frame_rotations(rotations, rule, _symmetric_cell(group, cell))
    terms, coefs = [], []
    for degree in range(2, order + 1, 2):
        p = projector(degree, rots)
        found = _cubic_terms(degree, rots, p) if rule.cubic else _non_cubic_terms(degree, p)
        if len(found) != _rank(p):
            raise AssertionError(f"l={degree}: {len(found)} functions against a projector "
                                 f"of rank {_rank(p)}")
        for n, v in found:
            terms.append(TextureTerm(degree, n, term_name(degree, n)))
            coefs.append(v)
    return TextureBasis(order, rule, tuple(terms), tuple(coefs))


_NAMES: dict[tuple, tuple[str, ...]] = {}


def texture_names(space_group, order: int, cell) -> tuple[str, ...]:
    """:attr:`TextureBasis.names`, cached on the group and the order.

    The names do not depend on the cell's free values, and ``ParameterTable``
    asks for them on every build, so the first cell asked with serves the
    rest.
    """
    group = as_group(space_group)
    key = (group_key(group), order)
    if key not in _NAMES:
        _NAMES[key] = texture_basis(group, order, cell).names
    return _NAMES[key]


def lowest_order(space_group) -> int:
    """The lowest even order with at least one allowed term: 4 for a cubic class, else 2."""
    return 4 if frame_rule(rotation_matrices(as_group(space_group))).cubic else 2
