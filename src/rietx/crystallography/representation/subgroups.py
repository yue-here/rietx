"""Maximal subgroups of a space group and Wyckoff splittings, generated from its own operations.

**Public API — WP-1919.**

::

    maximal(group, kind="both", max_index=None, *, index=None, supercell=None)
                                              -> tuple[MaximalSubgroup, ...]
    is_maximal(group, symbol, transform)      -> bool
    wyckoff_positions(group)                  -> WyckoffPositions
    wyckoff_splitting(group, sub)             -> WyckoffSplitting

``group`` is any symbol gemmi resolves, a ``gemmi.SpaceGroup``, or an
:class:`~rietx.crystallography.symmetry.OperatorGroup`, in any setting.
Nothing is read from a printed or online table of subgroups: every list is
built from the group's operations by the theory of ITA A1 (Wondratschek &
Müller 2011), and every member is checked exactly.

**The method** (A1 ch. 1.2, 2.1; restated in the manual's *Maximal
subgroups* section, with sources):

- A maximal subgroup H < G is either *translationengleiche* (t: same
  translations, smaller point group) or *klassengleiche* (k: same point
  group, fewer translations), by Hermann's theorem (A1 Lemma 1.2.8.1.3).
- **t.**  H ⊇ T(G), so H/T(G) is a subgroup of G/T(G) ≅ P, the point group.
  The maximal t-subgroups are exactly one per maximal subgroup of P, their
  coset representatives those of G.
- **k.**  H keeps P on a P-invariant sublattice L' < L.  H is maximal exactly
  when no P-invariant lattice lies strictly between L' and L, so pL ⊆ L' for
  one prime p and L/L' is an irreducible F_p[P]-module; the index is p, p²
  or p³ (A1 Lemma 1.2.8.2.1).  The maximal invariant subspaces U of F_p³
  give L' = pL + U.  On one L' the subgroups are the complements of L/L' in
  G/L': each assigns a shift x_g ∈ L/L' to every generator g of P, closure
  is a linear system over F_p, and every solution is one subgroup, so the
  list is complete by construction.
- **Index ≤ 4** holds every maximal subgroup that is not isomorphic to G
  (A1 Lemma 1.2.8.2.2), which is why :data:`MAX_INDEX` is 4.  Isomorphic
  ones exist at every prime index (A1 § 2.1.5) and come on demand, by
  ``index=`` or ``supercell=``.
- **Conjugacy.**  Classes are closures under conjugation by G's generators
  and lattice translations (translational and orientational conjugation,
  A1 § 3.1.5, both fall out).

**(P, p), the convention of** :mod:`.distortion` **and**
``distortion_candidates``: r_parent = P·r_child + p, the columns of P are the
child's conventional axes in parent fractions and p is the child's origin in
the parent cell, A1 eqs. (2.1.3.3)–(2.1.3.9).  The standard setting is the
one spglib returns for the subgroup's type (Togo, Shinohara & Tanaka 2024),
found from a probe structure, and P⁻¹HP is then checked against that setting's
operations exactly, in ``Fraction`` arithmetic, so a wrong (P, p) cannot
pass.  **The (P, p) is spglib's standardisation and no published table's.**
A1 picks one (P, p) out of the set the affine normaliser of H relates
(A1 § 2.1.2.5), and spglib's choice can differ from A1's or change with the
spglib version or the move to moyo (#426).  Compare two transformations by
the subgroup they describe (:meth:`MaximalSubgroup.describes`), never
entry by entry.  Two-origin types come out in spglib's default, origin
choice 1, and rhombohedral ones on hexagonal axes.

**Wyckoff positions** (Souvignier et al. 2016, ITA A § 1.4.4.2; A1 ch. 3.1) are the
classes of points whose site-symmetry groups are conjugate in G, found on the
1/24 grid of a Hall setting's conventional cell and joined by an exact test
(a point is on a position when an image of it lies on the fixed component of
the site-symmetry group of a point of that position's orbit); 1731 over the
230 types.  The letters are spglib's, read through spglib's own frame, and
belong to the setting and (P, p) the result names.  A **splitting**
decomposes the G-orbit of a generic point of each G position into H-orbits,
maps each by (P, p) into H's setting and identifies it there exactly.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

import gemmi
import numpy as np
import spglib

from ..magnetic.operators import _rational_determinant, _rational_inverse
from ..symmetry import as_group
from ..wyckoff import SPGLIB_REFUSALS, coordinate_basis
from .irreps import _row_hnf

__all__ = ["MAX_INDEX", "MaximalSubgroup", "WyckoffPosition", "WyckoffPositions",
           "WyckoffSplitting", "is_maximal", "maximal", "wyckoff_positions",
           "wyckoff_splitting"]

#: The largest index :func:`maximal` lists by default.  Every maximal subgroup
#: of a space group that is not isomorphic to it has index 2, 3 or 4
#: (Wondratschek 2011, ITA A1 Lemma 1.2.8.2.2, p. 23), so the list at index
#: ≤ 4 is complete for the non-isomorphic ones; the isomorphic ones, infinite
#: in number, are asked for by ``index=`` or ``supercell=``.
MAX_INDEX = 4

#: spglib's tolerance on the probe structure.  The probe's coordinates are
#: exact rationals and the answer is checked exactly afterwards, so this
#: decides only whether spglib names a group, never which (P, p) passes.
_PROBE_SYMPREC = 1e-5

_I3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))

#: Generic points for the probe: two H-orbits of these, each its own species,
#: pin spglib's answer to H itself.  Any point off every special position
#: would do; the exact check is what accepts the result.
_PROBE_POINTS = (
    (Fraction(1234, 10007), Fraction(5678, 10009), Fraction(9137, 10037)),
    (Fraction(821, 10007), Fraction(3179, 10009), Fraction(4317, 10037)),
)

#: spglib's matrix and origin come back as floats; the bound on the denominator that
#: recovers each is the larger of the floor (every t-subgroup, index <= 4) and
#: the per-index factor times the subgroup's index (12p leaves room above a hexagonal
#: origin at 3p and an inversion centre's half of it).
_PROBE_DENOMINATOR_FLOOR = 48
_PROBE_DENOMINATOR_PER_INDEX = 12

#: A generic metric, averaged over G's point group into one G preserves.
_GENERIC_METRIC = ((1.0, 0.13, 0.07), (0.13, 1.21, 0.11), (0.07, 0.11, 1.43))


# ---------------------------------------------------------------- exact algebra

#: A float entry of a (P, p) is snapped to the nearest ratio with a denominator up to this
#: (every ITA origin and cell is 1/2, 1/3, 1/4, 1/6, 1/8, 1/12 or 1/24 of a lattice
#: vector), and refused when it lies farther than ``_FLOAT_SNAP_TOL`` from any.
_FLOAT_DENOMINATOR_MAX = 48
_FLOAT_SNAP_TOL = 1e-9

def _q(value) -> Fraction:
    """A ``Fraction`` with Python integers inside (numpy ints break hashing)."""
    if isinstance(value, Fraction):
        return Fraction(int(value.numerator), int(value.denominator))
    if isinstance(value, (int, np.integer)):
        return Fraction(int(value))
    if isinstance(value, (float, np.floating)):
        # a float is its nearest binary fraction, so 1/3 arrives as 6004799503160661/2**54
        # and would match nothing: snap to the nearest ratio with a small denominator,
        # and refuse a number that is none (a 0.123456 typed for a quarter)
        snapped = Fraction(float(value)).limit_denominator(_FLOAT_DENOMINATOR_MAX)
        if abs(float(snapped) - float(value)) > _FLOAT_SNAP_TOL:
            raise ValueError(f"{value!r} is not a rational with denominator <= "
                             f"{_FLOAT_DENOMINATOR_MAX}; pass a Fraction or a ratio of integers")
        return snapped
    return Fraction(value)


def _mat(rows):
    return tuple(tuple(_q(v) for v in row) for row in rows)


def _mm(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def _mv(a, v):
    return tuple(sum(a[i][k] * v[k] for k in range(3)) for i in range(3))


def _add(a, b):
    return tuple(x + y for x, y in zip(a, b))


def _sub(a, b):
    return tuple(x - y for x, y in zip(a, b))


def _inv(a):
    return tuple(tuple(_q(v) for v in row) for row in _rational_inverse([list(r) for r in a]))


class _NotIntegral(ValueError):
    """A matrix that must be integral is not: the object it came from is not a group element."""


def _int_mat(a):
    """``a`` as a tuple of int tuples; raises when an entry is not integral."""
    out = []
    for row in a:
        r = []
        for v in row:
            v = _q(v)
            if v.denominator != 1:
                raise _NotIntegral(f"{a} is not an integer matrix")
            r.append(int(v))
        out.append(tuple(r))
    return tuple(out)


def _frac_part(v):
    return tuple(x - (x.numerator // x.denominator) for x in v)


def _integral(v) -> bool:
    return all(x.denominator == 1 for x in v)


def _lattice(vectors):
    """A canonical basis (columns) of the lattice the rational ``vectors`` span."""
    den = 1
    for v in vectors:
        for x in v:
            den = den * x.denominator // math.gcd(den, x.denominator)
    rows = _row_hnf([[int(x * den) for x in v] for v in vectors if any(v)])
    return tuple(tuple(Fraction(rows[j][i], den) for j in range(3)) for i in range(3))


def _columns(m):
    return [tuple(m[i][j] for i in range(3)) for j in range(3)]


def _reduce(v, basis, inverse):
    """``v`` modulo the lattice with column basis ``basis``."""
    return _mv(basis, _frac_part(_mv(inverse, v)))


# ---------------------------------------------------------------- the group

class _Group:
    """A space group as one coset representative (W, w) per point-group element.

    ``L`` holds the columns of a primitive basis of the full translation
    lattice, centrings included, in the group's own fractional coordinates,
    and every w is reduced modulo it.
    """

    __slots__ = ("L", "Linv", "reps", "_key")

    def __init__(self, reps, L):
        self.L = _lattice(_columns(L))
        self.Linv = _inv(self.L)
        self.reps = {}
        for W, w in reps:
            self.reps[W] = _reduce(tuple(_q(x) for x in w), self.L, self.Linv)
        self._key = None

    @property
    def order(self) -> int:
        return len(self.reps)

    def key(self):
        """Canonical identity: the HNF lattice plus the reduced representatives."""
        if self._key is None:
            self._key = (self.L, tuple(sorted(self.reps.items())))
        return self._key

    def contains(self, W, w) -> bool:
        if W not in self.reps:
            return False
        return _integral(_mv(self.Linv, _sub(w, self.reps[W])))

    def translations_in(self, other: _Group) -> bool:
        return all(_integral(_mv(other.Linv, col)) for col in _columns(self.L))

    def is_subgroup_of(self, other: _Group) -> bool:
        return (self.translations_in(other)
                and all(other.contains(W, w) for W, w in self.reps.items()))

    def transformed(self, P, p) -> _Group:
        """The same group in the coordinates x' = P⁻¹(x − p), A1 eqs. (2.1.3.8–9)."""
        Q = _inv(P)
        reps = []
        for W, w in self.reps.items():
            W2 = _int_mat(_mm(_mm(Q, W), P))
            reps.append((W2, _mv(Q, _add(w, _sub(_mv(W, p), p)))))
        return _Group(reps, _mm(Q, self.L))

    def conjugate(self, A, a) -> _Group:
        """g·H·g⁻¹ for g = (A, a), in the same coordinates."""
        Ai = _int_mat(_inv(A))
        reps = []
        for W, w in self.reps.items():
            W2 = _int_mat(_mm(_mm(A, W), Ai))
            reps.append((W2, _sub(_add(a, _mv(A, w)), _mv(W2, a))))
        return _Group(reps, _mm(A, self.L))


def _from_operations(ops) -> _Group:
    """A :class:`_Group` from gemmi operations (all of them, centrings included)."""
    den = gemmi.Op.DEN
    vectors = [(Fraction(1), Fraction(0), Fraction(0)), (Fraction(0), Fraction(1), Fraction(0)),
               (Fraction(0), Fraction(0), Fraction(1))]
    reps = {}
    for op in ops:
        W = tuple(tuple(int(v) // den for v in row) for row in op.rot)
        w = tuple(Fraction(int(t), den) for t in op.tran)
        if W == _I3:
            vectors.append(w)
        reps.setdefault(W, w)
    return _Group(list(reps.items()), _lattice(vectors))


def _group_of(spec) -> _Group:
    sg = as_group(spec)
    return _from_operations(sg.operations())


@lru_cache(maxsize=None)
def _standard(hall_number: int):
    """spglib's standard setting of a type: (group, gemmi symbol, ITA number)."""
    kind = spglib.get_spacegroup_type(hall_number)
    sg = gemmi.find_spacegroup_by_ops(gemmi.symops_from_hall(kind.hall_symbol))
    if sg is None:  # pragma: no cover - every default Hall setting is in gemmi's table
        raise RuntimeError(f"gemmi has no table entry for Hall symbol {kind.hall_symbol!r}")
    return _from_operations(sg.operations()), sg.xhm(), int(kind.number)


@lru_cache(maxsize=None)
def _standard_of_symbol(symbol: str):
    sg = as_group(symbol)
    return _from_operations(sg.operations()), sg.xhm(), int(sg.number)


# ---------------------------------------------------------------- point groups

def _close(elements, table) -> frozenset:
    found = set(elements)
    frontier = list(found)
    while frontier:
        new = []
        for a in frontier:
            for b in list(found):
                for c in (table[a][b], table[b][a]):
                    if c not in found:
                        found.add(c)
                        new.append(c)
        frontier = new
    return frozenset(found)


@lru_cache(maxsize=None)
def _maximal_point_subgroups(elements: frozenset) -> tuple[frozenset, ...]:
    """The maximal proper subgroups of a finite matrix group, by closure."""
    items = sorted(elements)
    index = {W: i for i, W in enumerate(items)}
    table = [[index[_int_mat(_mm(a, b))] for b in items] for a in items]
    identity = index[_I3]
    subgroups = {frozenset([identity])}
    frontier = list(subgroups)
    while frontier:
        new = []
        for s in frontier:
            for g in range(len(items)):
                if g not in s:
                    t = _close(s | {g}, table)
                    if t not in subgroups:
                        subgroups.add(t)
                        new.append(t)
        frontier = new
    whole = frozenset(range(len(items)))
    proper = [s for s in subgroups if s != whole]
    tops = [s for s in proper if not any(s < t for t in proper)]
    return tuple(sorted((frozenset(items[i] for i in s) for s in tops), key=sorted))


def _generators(elements) -> list:
    """A short generating set, large cyclic subgroups first (deterministic)."""
    def cyclic(W):
        seen, cur = {_I3}, W
        while cur not in seen:
            seen.add(cur)
            cur = _int_mat(_mm(cur, W))
        return len(seen)

    items = sorted(elements, key=lambda W: (-cyclic(W), W))
    gens: list = []
    span = {_I3}
    for W in items:
        if W in span:
            continue
        gens.append(W)
        span = set(_closure_of(gens))
        if len(span) == len(elements):
            break
    return gens


def _closure_of(gens) -> frozenset:
    found = {_I3}
    frontier = [_I3]
    while frontier:
        new = []
        for a in frontier:
            for g in gens:
                c = _int_mat(_mm(g, a))
                if c not in found:
                    found.add(c)
                    new.append(c)
        frontier = new
    return frozenset(found)


# ---------------------------------------------------------------- F_p algebra

def _rref(rows, p):
    a = [[x % p for x in r] for r in rows]
    pivots, r = [], 0
    ncols = len(a[0]) if a else 0
    for c in range(ncols):
        hit = next((i for i in range(r, len(a)) if a[i][c]), None)
        if hit is None:
            continue
        a[r], a[hit] = a[hit], a[r]
        inv = pow(a[r][c], -1, p)
        a[r] = [(x * inv) % p for x in a[r]]
        for i in range(len(a)):
            if i != r and a[i][c]:
                f = a[i][c]
                a[i] = [(x - f * y) % p for x, y in zip(a[i], a[r])]
        pivots.append(c)
        r += 1
        if r == len(a):
            break
    return a[:r], pivots


def _solve(a, b, p):
    """All x with a·x = b over F_p, as (particular, nullspace basis), or None."""
    if not a or not a[0]:  # P1: no generators, no unknowns, one subgroup per lattice
        return ([], []) if all(v % p == 0 for v in b) else None
    n = len(a[0])
    reduced, pivots = _rref([list(r) + [v] for r, v in zip(a, b)], p)
    if n in pivots:
        return None
    x0 = [0] * n
    for i, c in enumerate(pivots):
        x0[c] = reduced[i][n] % p
    null = []
    for f in (c for c in range(n) if c not in pivots):
        v = [0] * n
        v[f] = 1
        for i, c in enumerate(pivots):
            v[c] = (-reduced[i][f]) % p
        null.append(v)
    return x0, null


def _subspaces(p):
    """The lines and planes of F_p³, each as a reduced basis (tuple of rows)."""
    lines = [((v,)) for v in itertools.product(range(p), repeat=3)
             if any(v) and v[next(i for i in range(3) if v[i])] == 1]
    planes = []
    for (f,) in lines:  # the plane is the kernel of the linear form f
        k = next(i for i in range(3) if f[i])
        basis = []
        for j in range(3):
            if j != k:
                v = [0, 0, 0]
                v[j] = 1
                v[k] = (-f[j] * pow(f[k], -1, p)) % p
                basis.append(v)
        reduced, _ = _rref(basis, p)
        planes.append(tuple(tuple(r) for r in reduced))
    return [tuple(tuple(v) for v in line) for line in lines], planes


def _within(vectors, basis, p) -> bool:
    """Whether every vector lies in the F_p span of ``basis`` (rank test, no p^d vectors held)."""
    if not basis:
        return not any(any(c % p for c in v) for v in vectors)
    rows, _ = _rref([list(b) for b in basis], p)
    rank = len(rows)
    return all(len(_rref(rows + [list(v)], p)[0]) == rank for v in vectors)


def _invariant(basis, mats, p) -> bool:
    return _within([[sum(M[i][k] * u[k] for k in range(3)) % p for i in range(3)]
                    for M in mats for u in basis], basis, p)


@lru_cache(maxsize=32)
def _invariant_subspaces(mats: tuple, p: int):
    """The bases of every proper P-invariant subspace of F_p³ (the zero space, ``()``, included).

    Bases only: a plane's span is p² vectors, and a cache of them for every
    plane would hold 2 863 × 2 809 vectors at p = 53.
    """
    lines, planes = _subspaces(p)
    return [()] + [basis for basis in lines + planes if _invariant(basis, mats, p)]


def _below(small, large, p) -> bool:
    """Whether the subspace with basis ``small`` lies strictly inside the one with ``large``."""
    return len(small) < len(large) and _within(small, large, p)


def _maximal_invariant(mats: tuple, p: int):
    found = _invariant_subspaces(mats, p)
    return [b for b in found if not any(_below(b, other, p) for other in found)]


# ---------------------------------------------------------------- generation

def _t_subgroups(G: _Group) -> list[tuple[_Group, int, int | None]]:
    out = []
    for S in _maximal_point_subgroups(frozenset(G.reps)):
        out.append((_Group([(W, G.reps[W]) for W in S], G.L), G.order // len(S), None))
    return out


def _k_subgroups(G: _Group, p: int, dims, keep=None) -> list[tuple[_Group, int, int]]:
    """Maximal k-subgroups for one prime, with index p^d for d in ``dims``.

    ``keep`` filters the subspaces U (in L's primitive coordinates) before the
    complements are solved, which is how ``supercell=`` stays cheap.
    """
    L, Linv = G.L, G.Linv
    elements = sorted(G.reps)
    ms = {W: _int_mat(_mm(_mm(Linv, W), L)) for W in elements}
    gens = _generators(elements)
    # each element e = g·e0 along a word in the generators, with the translation
    # v_e the product of the representatives carries (not reduced)
    order = [_I3]
    word = {_I3: None}
    v = {_I3: (Fraction(0), Fraction(0), Fraction(0))}
    i = 0
    while i < len(order):
        e = order[i]
        for gi, g in enumerate(gens):
            ge = _int_mat(_mm(g, e))
            if ge not in word:
                word[ge] = (gi, e)
                v[ge] = _add(G.reps[g], _mv(g, v[e]))
                order.append(ge)
        i += 1
    mats = tuple(sorted(ms[g] for g in gens))
    out = []
    for U in _maximal_invariant(mats, p):
        m = 3 - len(U)
        if m not in dims or (keep is not None and not keep(U, p)):
            continue
        if U:
            reduced, pivots = _rref([list(u) for u in U], p)
            cvecs = [[int(k == c) for k in range(3)] for c in range(3) if c not in pivots]
            basis = [list(r) for r in reduced] + cvecs
            inverse = _inverse_mod([[basis[r][c] for r in range(3)] for c in range(3)], p)
            A = [inverse[len(U) + j] for j in range(m)]
        else:
            cvecs = [list(r) for r in _I3]
            A = cvecs
        rho = {W: [[sum(A[a][k] * sum(ms[W][k][q] * cvecs[b][q] for q in range(3))
                        for k in range(3)) % p for b in range(m)] for a in range(m)]
               for W in elements}
        nun = m * len(gens)

        def pi(vec):
            c = _mv(Linv, vec)
            return [sum(A[a][k] * int(c[k]) for k in range(3)) % p for a in range(m)]

        C = {_I3: [[0] * nun for _ in range(m)]}
        for e in order[1:]:
            gi, e0 = word[e]
            g = gens[gi]
            Ce = [[sum(rho[g][a][k] * C[e0][k][j] for k in range(m)) % p for j in range(nun)]
                  for a in range(m)]
            for a in range(m):
                Ce[a][gi * m + a] = (Ce[a][gi * m + a] + 1) % p
            C[e] = Ce
        rows, rhs = [], []
        for gi, g in enumerate(gens):
            for e in order:
                ge = _int_mat(_mm(g, e))
                n = _sub(_add(G.reps[g], _mv(g, v[e])), v[ge])
                pn = pi(n)
                for a in range(m):
                    row = [0] * nun
                    row[gi * m + a] += 1
                    for j in range(nun):
                        row[j] += sum(rho[g][a][k] * C[e][k][j] for k in range(m)) - C[ge][a][j]
                    rows.append([x % p for x in row])
                    rhs.append((-pn[a]) % p)
        solution = _solve(rows, rhs, p)
        if solution is None:
            continue
        x0, null = solution
        sub_lattice = _mm(L, _lattice([tuple(Fraction(p * int(k == j)) for k in range(3))
                                       for j in range(3)]
                                      + [tuple(Fraction(x) for x in u) for u in U]))
        for coeffs in itertools.product(range(p), repeat=len(null)):
            x = [(x0[j] + sum(c * nv[j] for c, nv in zip(coeffs, null))) % p for j in range(nun)]
            reps = []
            for e in order:
                tau = [sum(C[e][a][j] * x[j] for j in range(nun)) % p for a in range(m)]
                lift = tuple(Fraction(sum(tau[j] * cvecs[j][k] for j in range(m)))
                             for k in range(3))
                reps.append((e, _add(v[e], _mv(L, lift))))
            out.append((_Group(reps, sub_lattice), p ** m, p))
    return out


def _inverse_mod(M, p):
    n = len(M)
    reduced, pivots = _rref([list(M[i]) + [int(i == j) for j in range(n)] for i in range(n)], p)
    if pivots[:n] != list(range(n)):  # pragma: no cover - the basis is a basis
        raise RuntimeError("singular basis over F_p; this is a bug")
    return [r[n:] for r in reduced]


# ---------------------------------------------------------------- conjugacy

def _classes(G: _Group, subgroups) -> tuple[list[int], list[int]]:
    """Class id and class size per subgroup, by closure under G's generators."""
    movers = [(W, G.reps[W]) for W in _generators(list(G.reps))]
    movers += [(_I3, col) for col in _columns(G.L)]
    position = {H.key(): i for i, H in enumerate(subgroups)}
    cls = [-1] * len(subgroups)
    sizes: list[int] = []
    for i, H in enumerate(subgroups):
        if cls[i] >= 0:
            continue
        seen = {H.key()}
        frontier = [H]
        while frontier:
            new = []
            for K in frontier:
                for A, a in movers:
                    K2 = K.conjugate(A, a)
                    if K2.key() not in seen:
                        seen.add(K2.key())
                        new.append(K2)
            frontier = new
        for key in seen:
            if key in position:
                cls[position[key]] = len(sizes)
        sizes.append(len(seen))
    return cls, sizes


# ---------------------------------------------------------------- standardisation

def _metric(G: _Group) -> np.ndarray:
    """A metric every W of G preserves: a generic one averaged over the point group."""
    base = np.array(_GENERIC_METRIC)
    rots = [np.array(W, dtype=float) for W in G.reps]
    return sum(W.T @ base @ W for W in rots) / len(rots)


def _probe(H: _Group, metric: np.ndarray, points):
    lattice_frac = np.array([[float(x) for x in col] for col in _columns(H.L)])
    # rows of the Cholesky factor C (C·Cᵀ = metric) are the Cartesian a, b, c
    cell = lattice_frac @ np.linalg.cholesky(metric)  # rows: H's primitive vectors
    positions, numbers = [], []
    for species, x0 in enumerate(points):
        for W, w in H.reps.items():
            y = _frac_part(_mv(H.Linv, _add(_mv(W, x0), w)))
            positions.append([float(c) for c in y])
            numbers.append(species + 1)
    return cell, positions, numbers


def _standardise(H: _Group, metric: np.ndarray, index: int = 1):
    """(number, symbol, (P, p)) of H, checked exactly against spglib's setting.

    spglib returns floats; the rational each stands for has a denominator that
    grows with H's index in G (an inversion centre at a/2 of a p-fold
    supercell is 1/2p in H's own axes, a hexagonal origin 1/3p), so the bound
    that recovers it does too.  The exact comparison below accepts or raises.
    """
    bound = max(_PROBE_DENOMINATOR_FLOOR, _PROBE_DENOMINATOR_PER_INDEX * index)
    cell, positions, numbers = _probe(H, metric, _PROBE_POINTS)
    try:
        data = spglib.get_symmetry_dataset((cell, positions, numbers), symprec=_PROBE_SYMPREC)
    except SPGLIB_REFUSALS:
        data = None
    if data is None:
        raise RuntimeError("no exact standard setting for a subgroup: spglib names no group "
                           "for the probe; this is a bug")
    std, symbol, number = _standard(int(data.hall_number))
    M = tuple(tuple(Fraction(float(x)).limit_denominator(bound) for x in row)
              for row in data.transformation_matrix)
    o = tuple(Fraction(float(x)).limit_denominator(bound) for x in data.origin_shift)
    P = _mm(H.L, _inv(M))
    p = _short_origin(tuple(-x for x in _mv(P, o)), H)
    if H.transformed(P, p).key() != std.key():
        raise RuntimeError(f"no exact standard setting for a subgroup: spglib's {symbol!r} under "
                           f"P = {_text(P)}, p = {_text(p)} is not the subgroup's operation "
                           "list; this is a bug")
    return number, symbol, (P, p)


def _short_origin(p, H: _Group):
    """The shortest of p + L(H), non-negative components preferred.

    Moving the child's origin by one of H's own translations describes the
    same H, so this changes how p reads and never which subgroup it names.
    """
    base = _reduce(p, H.L, H.Linv)
    cols = _columns(H.L)
    best = None
    for c in itertools.product((-1, 0, 1), repeat=3):
        q = tuple(base[i] + sum(c[j] * cols[j][i] for j in range(3)) for i in range(3))
        key = (max(abs(x) for x in q), sum(abs(x) for x in q), tuple(x < 0 for x in q), q)
        if best is None or key < best[0]:
            best = (key, q)
    return best[1]


def _text(x) -> str:
    if isinstance(x[0], tuple):
        return "[" + "; ".join(" ".join(str(v) for v in row) for row in x) + "]"
    return "(" + ", ".join(str(v) for v in x) + ")"


def _pull_back(std: _Group, P, p) -> _Group:
    """The group whose standard description is ``std`` under (P, p), in parent coordinates."""
    Q = _inv(P)
    return std.transformed(Q, tuple(-x for x in _mv(Q, p)))


# ---------------------------------------------------------------- public API

@dataclass(frozen=True)
class MaximalSubgroup:
    """One maximal subgroup H of a space group G, with its standard setting.

    ``transform`` is (P, p) with r_parent = P·r_child + p (A1 eqs.
    2.1.3.3–2.1.3.9; the convention of :mod:`.distortion`): the columns of P
    are H's conventional axes in G's fractions, p is H's origin in G's cell.
    ``symbol`` is the gemmi symbol of spglib's standard setting of H's type,
    and P⁻¹HP equals that setting's operations exactly.  The (P, p) is one
    of the set H's affine normaliser relates; it is spglib's choice, not
    necessarily A1's (module docstring).

    ``kind`` is ``"t"`` (same translations, A1's translationengleiche) or
    ``"k"`` (same point group, A1's klassengleiche), ``prime`` the p of a
    k-subgroup's index p^d.  ``conjugacy_class`` numbers the classes in the
    order the result lists them; ``class_size`` is the number of subgroups
    conjugate to this one in G, which a filtered result (``supercell=``) may
    hold only some of.
    """

    kind: str
    index: int
    number: int
    symbol: str
    transform: tuple[tuple[tuple[Fraction, ...], ...], tuple[Fraction, ...]]
    conjugacy_class: int
    class_size: int
    prime: int | None = None

    @property
    def basis(self) -> str:
        """H's axes as sums of G's, A1's notation: ``"a,b,2c"``."""
        P = self.transform[0]
        return ",".join(_combination([P[i][j] for i in range(3)], "abc") for j in range(3))

    @property
    def origin(self) -> str:
        """H's origin in G's fractions: ``"0,0,1/4"``."""
        return ",".join(str(x) for x in self.transform[1])

    def describes(self, symbol: str, transform) -> bool:
        """Whether ``symbol`` under (P, p) = ``transform`` is this same subgroup of G.

        Both are rebuilt in G's coordinates and compared as operation sets
        with their lattices, exactly, so two transformations the affine
        normaliser of H relates (A1's and spglib's, say) agree, and a wrong
        origin or a transposed axis does not.  A (P, p) under which ``symbol``'s
        operations are not integral in G's axes (a wrong basis) describes no
        subgroup of G, so the answer is ``False``.
        """
        try:
            return _rebuild(symbol, transform).key() == _rebuild(self.symbol, self.transform).key()
        except _NotIntegral:
            return False

    def __str__(self) -> str:
        return (f"[{self.index}] {self.kind} {self.symbol} ({self.number})  "
                f"{self.basis}  origin {self.origin}")


def _combination(column, names) -> str:
    out = ""
    for c, name in zip(column, names):
        if c == 0:
            continue
        sign = "-" if c < 0 else "+"
        mag = abs(c)
        out += sign + ("" if mag == 1 else str(mag)) + name
    out = out.lstrip("+")
    return out or "0"


def _rebuild(symbol: str, transform) -> _Group:
    """The subgroup ``symbol`` under (P, p), in the parent's coordinates."""
    std = _standard_of_symbol(symbol)[0]
    P, p = _mat(transform[0]), tuple(_q(x) for x in transform[1])
    return _pull_back(std, P, p)


def _prime_power(n: int) -> tuple[int, int] | None:
    if n < 2:
        return None
    p = next(q for q in range(2, n + 1) if n % q == 0)
    d = 0
    while n % p == 0:
        n //= p
        d += 1
    return (p, d) if n == 1 else None


def _primes(n: int) -> list[int]:
    out, q = [], 2
    while q * q <= n:
        if n % q == 0:
            out.append(q)
            while n % q == 0:
                n //= q
        q += 1
    if n > 1:
        out.append(n)
    return out


def maximal(group, kind: str = "both", max_index: int | None = None, *,
            index: int | None = None, supercell=None) -> tuple[MaximalSubgroup, ...]:
    """Every maximal subgroup of ``group`` asked for, with its class and (P, p).

    By default, every maximal subgroup of index ≤ ``max_index``: at the
    default (:data:`MAX_INDEX`, 4) that is every non-isomorphic one (A1 Lemma 1.2.8.2.2) and the
    isomorphic ones of index 2, 3 and 4.  ``index=n`` gives exactly those of
    index n, isomorphic ones of any prime-power index included.
    ``supercell=P`` (columns in ``group``'s fractions, integer combinations of
    its lattice) gives every maximal subgroup that keeps the translations of
    the cell P: the t-subgroups, and each k-subgroup whose lattice contains
    P's columns, at whatever index that implies.  ``kind`` is ``"t"``,
    ``"k"`` or ``"both"``.  ``max_index`` bounds only the default search, so
    giving it with ``index=`` or ``supercell=`` raises, as does an ``index``
    that is not a positive integer.

    The method is the module docstring's (ITA A1, Wondratschek & Müller
    2011, ch. 1.2 and 2.1); the (P, p) is spglib's standard setting (Togo,
    Shinohara & Tanaka 2024), checked exactly.  The result is sorted t before
    k, then by index, then by decreasing space-group number (A1's order,
    § 2.1.2.4), conjugates together.
    """
    if kind not in ("t", "k", "both"):
        raise ValueError(f"kind must be 't', 'k' or 'both', not {kind!r}")
    if index is not None:
        if isinstance(index, bool) or not isinstance(index, (int, np.integer)) or index < 1:
            raise ValueError(f"index must be a positive integer, not {index!r}")
        index = int(index)
    if max_index is not None and (index is not None or supercell is not None):
        raise ValueError("max_index bounds the default search only; it cannot be combined "
                         "with index= or supercell=")
    if max_index is None:
        max_index = MAX_INDEX
    G = _group_of(group)
    found: list[tuple[str, _Group, int, int | None]] = []
    want_t = kind in ("t", "both")
    want_k = kind in ("k", "both")

    if supercell is not None:
        P = _mat(supercell)
        rel = _mm(G.Linv, P)
        if not all(v.denominator == 1 for row in rel for v in row):
            raise ValueError(f"the supercell {_text(P)} has a column that is not a lattice "
                             "vector of the group")
        size = abs(_rational_determinant(rel))
        if size == 0:
            raise ValueError(f"the supercell {_text(P)} is singular")
        cols = [tuple(int(rel[i][j]) for i in range(3)) for j in range(3)]

        def keep(U, p):
            return _within(cols, U, p)

        if want_t:
            found += [("t", H, n, pr) for H, n, pr in _t_subgroups(G)]
        if want_k:
            for p in _primes(int(size)):
                found += [("k", H, n, pr) for H, n, pr in _k_subgroups(G, p, (1, 2, 3), keep)]
        if index is not None:
            found = [f for f in found if f[2] == index]
    elif index is not None:
        if want_t and index in (2, 3, 4):
            found += [("t", H, n, pr) for H, n, pr in _t_subgroups(G) if n == index]
        power = _prime_power(int(index))
        if want_k and power is not None and power[1] <= 3:
            p, d = power
            found += [("k", H, n, pr) for H, n, pr in _k_subgroups(G, p, (d,))]
    else:
        if want_t:
            found += [("t", H, n, pr) for H, n, pr in _t_subgroups(G) if n <= max_index]
        if want_k:
            for p in _primes_up_to(max_index):
                dims = tuple(d for d in (1, 2, 3) if p ** d <= max_index)
                found += [("k", H, n, pr) for H, n, pr in _k_subgroups(G, p, dims)]

    subgroups = [H for _, H, _, _ in found]
    cls, sizes = _classes(G, subgroups)
    metric = _metric(G)
    rows = []
    for (k, H, n, pr), c in zip(found, cls):
        number, symbol, transform = _standardise(H, metric, n)
        rows.append((k, n, number, symbol, transform, c, sizes[c], pr, H.key()))
    first = {}
    rows.sort(key=lambda r: (r[0] != "t", r[1], -r[2], r[5], r[8]))
    for r in rows:
        first.setdefault(r[5], len(first))
    return tuple(MaximalSubgroup(kind=k, index=n, number=number, symbol=symbol,
                                 transform=transform, conjugacy_class=first[c],
                                 class_size=size, prime=pr)
                 for k, n, number, symbol, transform, c, size, pr, _ in rows)


def _primes_up_to(n: int) -> list[int]:
    return [q for q in range(2, n + 1) if all(q % r for r in range(2, q))]


def is_maximal(group, symbol: str, transform) -> bool:
    """Whether the subgroup ``symbol`` under (P, p) = ``transform`` is maximal in ``group``.

    The subgroup is rebuilt from its own symbol and (P, p) alone (r_parent =
    P·r_child + p), so this is an independent route to any result of
    :func:`maximal`, and the test a walk down a group–subgroup tree applies to
    a candidate it did not generate.  Raises ``ValueError`` when the rebuilt
    group is not a subgroup of ``group`` at all.

    Decided by A1's theory (Wondratschek 2011, ch. 1.2): a maximal subgroup
    is t or k (Lemma 1.2.8.1.3); a t-subgroup is maximal when its point group
    is maximal in G's; a k-subgroup when no lattice invariant under the point
    group lies strictly between its lattice and G's (Lemma 1.2.8.2.1), which
    over F_p means its image U in L/pL is a maximal invariant subspace.
    """
    G = _group_of(group)
    where = (f"{symbol} under P = {_text(_mat(transform[0]))}, "
             f"p = {_text(tuple(_q(x) for x in transform[1]))}")
    try:
        H = _rebuild(symbol, transform)
    except _NotIntegral:  # a wrong basis: its operations are not integral in G's axes
        raise ValueError(f"{where} is not a subgroup of the group") from None
    if not H.is_subgroup_of(G):
        raise ValueError(f"{where} is not a subgroup of the group")
    same_lattice = G.translations_in(H)
    same_points = set(H.reps) == set(G.reps)
    if same_lattice and same_points:
        return False  # H is G
    if same_lattice:
        return frozenset(H.reps) in _maximal_point_subgroups(frozenset(G.reps))
    if not same_points:
        return False  # H < H·T(G) < G
    rel = _int_mat(_mm(G.Linv, H.L))
    size = abs(int(_rational_determinant(tuple(tuple(Fraction(v) for v in r) for r in rel))))
    power = _prime_power(size)
    if power is None:
        return False
    p, _ = power
    cols = [tuple(rel[i][j] for i in range(3)) for j in range(3)]
    # pL ⊆ L' is needed for L/L' to be an F_p-module at all
    Hinv = _inv(tuple(tuple(Fraction(v) for v in r) for r in rel))
    if not all(_integral(_mv(Hinv, tuple(Fraction(p * int(i == j)) for i in range(3))))
               for j in range(3)):
        return False
    image = _rref([[c % p for c in col] for col in cols], p)[0]
    mats = tuple(sorted(_int_mat(_mm(_mm(G.Linv, W), G.L))
                        for W in _generators(list(G.reps))))
    U = tuple(tuple(r) for r in image)
    if any(_below(U, other, p) for other in _invariant_subspaces(mats, p)):
        return False
    return True


# ---------------------------------------------------------------- Wyckoff positions

#: The grid the positions are found on.  Every fixed coordinate of a special
#: position in the ITA settings is a multiple of 1/24 (the finest are the
#: eighths of the d-glide groups and the twelfths of the hexagonal ones), so
#: the 1/24 grid of the conventional cell meets every Wyckoff position of a
#: group in an ITA setting; the 1731 positions of the 230 types are the check.
_WYCKOFF_GRID = 24

#: Free-parameter values of a generic point of a position: rationals whose
#: denominators are primes far from the 1/24 grid, so no free parameter lands
#: on a special value and the point's site symmetry is the position's own
#: (asserted where it is used).
_GENERIC_VALUES = (Fraction(137, 1009), Fraction(271, 1013), Fraction(419, 1019))


@dataclass(frozen=True)
class WyckoffPosition:
    """One Wyckoff position of a space group, in the group's own setting.

    ``letter`` and ``site_symmetry`` (the oriented symbol) are spglib's, for
    the setting :attr:`WyckoffPositions.standard` names; ``multiplicity`` is
    the number of points of one orbit in the group's conventional cell,
    ``site_order`` the order of the site-symmetry group.  ``point`` is the
    first point of the conventional cell's 1/24 grid whose site symmetry is
    exactly the position's, **not ITA's representative**: it sits off zero
    wherever zero has higher symmetry (on ``P m m m`` the line 2i gives
    ``(1/24, 0, 0)``, since ``(0, 0, 0)`` is 1a).  ``directions`` are the
    integer directions the free parameters move it along, so the position is
    the orbit of ``point + Σ θ_j · directions[j]`` at the θ_j that keep the
    site symmetry exactly the position's; θ = 0 generally does not.
    """

    letter: str
    multiplicity: int
    site_symmetry: str
    site_order: int
    point: tuple[Fraction, Fraction, Fraction]
    directions: tuple[tuple[int, int, int], ...]

    @property
    def label(self) -> str:
        """Multiplicity and letter, ITA's Wyckoff symbol: ``"4f"``."""
        return f"{self.multiplicity}{self.letter}"


@dataclass(frozen=True)
class WyckoffPositions:
    """The Wyckoff positions of a space group, found from its operations.

    The positions themselves come from the group's operations alone: points
    whose site-symmetry groups are conjugate in G form one position
    (Souvignier et al. 2016, ITA A § 1.4.4.2).  The letters are ITA's labelling convention,
    not theory, and are spglib's for the setting ``standard`` (Togo,
    Shinohara & Tanaka 2024).  When the group is given in one of spglib's 530
    Hall settings that is its own setting and ``transform`` is the identity;
    otherwise the group is standardised to spglib's default setting and
    ``transform`` = (P, p), with r_group = P·r_standard + p, is the
    transformation the letters belong to.  A different (P, p) related by the
    affine normaliser can permute letters within a Wyckoff set (A1
    § 3.1.1.6.5).
    """

    symbol: str
    number: int
    standard: str
    transform: tuple[tuple[tuple[Fraction, ...], ...], tuple[Fraction, ...]]
    positions: tuple[WyckoffPosition, ...]

    def __str__(self) -> str:
        return (f"{self.symbol} ({self.number}): "
                + " ".join(w.label for w in self.positions))


@dataclass(frozen=True)
class WyckoffSplitting:
    """How each Wyckoff position of G splits into positions of a subgroup H.

    ``rows`` pairs each of G's labels with the labels of the H-orbits one
    G-orbit splits into, ``(("2d", ("2c", "2d")), …)``, in G's letter order.
    H's labels belong to ``transform``, the (P, p) with r_G = P·r_H + p that
    states H (A1 § 3.1.1.6.5: another (P, p) can permute them within a Wyckoff
    set); G's labels belong to ``group_transform``, the identity when G is in
    one of spglib's Hall settings (:class:`WyckoffPositions`).  Every row
    satisfies Σ m_H = m_G·|det P|.
    """

    group: str
    subgroup: str
    transform: tuple[tuple[tuple[Fraction, ...], ...], tuple[Fraction, ...]]
    group_transform: tuple[tuple[tuple[Fraction, ...], ...], tuple[Fraction, ...]]
    rows: tuple[tuple[str, tuple[str, ...]], ...]

    def __getitem__(self, label: str) -> tuple[str, ...]:
        for g, h in self.rows:
            if g == label:
                return h
        raise KeyError(f"{label!r} is not a Wyckoff position of {self.group}")

    def __str__(self) -> str:
        lines = [f"{self.group} > {self.subgroup}  P = {_text(self.transform[0])}, "
                 f"p = {_text(self.transform[1])}"]
        if self.group_transform != _IDENTITY:  # G's own labels belong to this (P, p)
            lines.append(f"  {self.group}'s labels: P = {_text(self.group_transform[0])}, "
                         f"p = {_text(self.group_transform[1])}")
        lines += [f"  {g} -> {'; '.join(h)}" for g, h in self.rows]
        return "\n".join(lines)


_IDENTITY = (tuple(tuple(Fraction(int(i == j)) for j in range(3)) for i in range(3)),
             (Fraction(0), Fraction(0), Fraction(0)))


def _conventional_ops(G: _Group):
    """Every operation of G modulo Z³: the representatives times the centrings."""
    centrings = _coset_vectors(G.L, _IDENTITY[0])  # the lattice points in the unit cell
    ops = sorted({(W, _frac_part(_add(w, c))) for W, w in G.reps.items() for c in centrings})
    return ops, len(centrings)


class _Table:
    """The positions of one group in its own coordinates, with what identifies them.

    ``classes`` holds, per position: (letter, symbol, multiplicity, site order,
    anchor point, directions); ``components`` holds, per position, the
    fixed-point equations N·x = c of the site-symmetry group of every point
    of the anchor's orbit, keyed by its rotation set.
    """

    def __init__(self, G: _Group, letters):
        self.G = G
        self.ops, self.centrings = _conventional_ops(G)
        self.classes = []
        self.components = []
        for anchor, stab in _grid_orbits(self.ops):
            if len(stab) == 1 and any(c[3] == 1 for c in self.classes):
                continue  # every point with trivial site symmetry is on the general position
            if self._hits(anchor, frozenset(stab)):
                continue  # an orbit of a position already found
            self._add(anchor, stab)
        letters(self)  # fills each class's letter and site-symmetry symbol
        order = sorted(range(len(self.classes)),
                       key=lambda i: (self.classes[i][0].isupper(), self.classes[i][0]))
        self.classes = [self.classes[i] for i in order]
        self.components = [self.components[i] for i in order]

    def _add(self, anchor, stab):
        rots = [np.array(W, dtype=np.int64) for W in stab]
        directions = tuple(tuple(int(v) for v in row) for row in coordinate_basis(rots))
        self.classes.append([None, None, len(self.ops) // len(stab), len(stab),
                             anchor, directions])
        # the site-symmetry group of each point of the anchor's orbit, by
        # conjugating the anchor's own: g·(R, s)·g⁻¹ fixes g·anchor
        own = [(W, _sub(anchor, _mv(W, anchor))) for W in stab]
        comps: dict = {}
        seen = set()
        for W, w in self.ops:
            z = _frac_part(_add(_mv(W, anchor), w))
            if z in seen:
                continue
            seen.add(z)
            shift = _sub(z, _add(_mv(W, anchor), w))  # z = g·anchor + an integer vector
            Wi = _int_mat(_inv(W))
            rots2, N, c = [], [], []
            for R, s in own:
                R2 = _int_mat(_mm(_mm(W, R), Wi))
                s2 = _sub(_add(_add(_mv(W, s), w), shift), _mv(R2, _add(w, shift)))
                rots2.append(R2)
                for r in range(3):
                    N.append(tuple(R2[r][k] - (r == k) for k in range(3)))
                    c.append(-s2[r])
            comps.setdefault(frozenset(rots2), []).append((tuple(N), tuple(c)))
        self.components.append(comps)

    def _stabiliser(self, x):
        """(rotation set, N, c): the affine site-symmetry group of x as N·y = c."""
        rots, N, c = [], [], []
        for W, w in self.ops:
            d = _sub(_add(_mv(W, x), w), x)
            if _integral(d):
                rots.append(W)
                s = _sub(x, _mv(W, x))  # the full translation of the operation fixing x
                for i in range(3):
                    N.append(tuple(W[i][k] - (i == k) for k in range(3)))
                    c.append(-s[i])
        return frozenset(rots), tuple(N), tuple(c)

    def _hits(self, x, key=None) -> list[int]:
        """The positions found so far whose fixed components hold x, modulo Z³.

        ``key`` is x's site-symmetry rotation set when the caller has it already.
        """
        if key is None:
            key = self._stabiliser(x)[0]
        hits = []
        for i, comps in enumerate(self.components):
            if self.classes[i][3] != len(key) or key not in comps:
                continue
            for N, c in comps[key]:
                rhs = tuple(ci - sum(N[r][k] * x[k] for k in range(3)) for r, ci in enumerate(c))
                if _integer_solvable(N, rhs):
                    hits.append(i)
                    break
        return hits

    def identify(self, x) -> int:
        """Index of the position holding the point ``x`` (exact).

        x is on a position exactly when some image of x lies on the fixed
        component of the site-symmetry group of a point of that position's
        orbit with no larger site symmetry; images under G are the components
        listed, images under Z³ the integer solution of N·(x + u) = c.
        """
        hits = self._hits(x)
        if len(hits) != 1:
            raise RuntimeError(f"the point {_text(x)} lies on {len(hits)} Wyckoff positions "
                               "of the table; this is a bug")
        return hits[0]

    def generic(self, i):
        """A point of position ``i`` with generic free parameters, its site symmetry checked."""
        anchor, directions = self.classes[i][4], self.classes[i][5]
        x = anchor
        for value, d in zip(_GENERIC_VALUES, directions):
            x = _add(x, tuple(value * v for v in d))
        if len(self._stabiliser(x)[0]) != self.classes[i][3]:
            raise RuntimeError("a generic point of a Wyckoff position has a larger site "
                               "symmetry than the position; this is a bug")
        return x


def _integer_solvable(N, rhs) -> bool:
    """Whether N·u = rhs has an integer solution u (N integer, rhs rational).

    Column operations bring N to lower echelon form one row at a time (the
    columns stay an integer basis of the same image lattice), and each pivot
    fixes one coordinate of u, which must come out an integer.
    """
    if any(v.denominator != 1 for v in rhs):
        return False
    A = [list(row) for row in N]
    b = [int(v) for v in rhs]
    col = 0
    for i in range(len(A)):
        if col < 3:
            while True:
                nz = [j for j in range(col, 3) if A[i][j]]
                if len(nz) <= 1:
                    break
                j0 = min(nz, key=lambda j: abs(A[i][j]))
                for row in A:
                    row[col], row[j0] = row[j0], row[col]
                for j in range(col + 1, 3):
                    q = A[i][j] // A[i][col]
                    if q:
                        for row in A:
                            row[j] -= q * row[col]
            nz = [j for j in range(col, 3) if A[i][j]]
            if nz:
                j0 = nz[0]
                for row in A:
                    row[col], row[j0] = row[j0], row[col]
                if b[i] % A[i][col]:
                    return False
                v = b[i] // A[i][col]
                for r in range(len(A)):
                    b[r] -= v * A[r][col]
                col += 1
                continue
        if b[i]:
            return False
    return True


def _grid_orbits(ops):
    """(first point, stabiliser rotations) per orbit of the 1/24 grid, in point order.

    The orbits are joined into positions by :meth:`_Table.identify`'s exact
    test, never by comparing grid points: two pieces of one fixed line can
    meet the cell as two segments a lattice translation apart.
    """
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    D = _WYCKOFF_GRID
    if any((v * D).denominator != 1 for _, w in ops for v in w):
        raise RuntimeError("a Hall setting's translations are not multiples of 1/24; "
                           "this is a bug")
    R = np.array([W for W, _ in ops], dtype=np.int32)
    t = np.array([[int(v * D) for v in w] for _, w in ops], dtype=np.int32)
    g = np.stack(np.meshgrid(np.arange(D), np.arange(D), np.arange(D), indexing="ij"),
                 -1).reshape(-1, 3).astype(np.int32)
    n_points = len(g)
    images = (np.einsum("kij,nj->nki", R, g) + t[None]) % D  # (point, op, axis)
    fixed = (images == g[:, None, :]).all(-1)
    flat = (images[..., 0] * D + images[..., 1]) * D + images[..., 2]
    rows = np.repeat(np.arange(n_points), len(ops))
    graph = coo_matrix((np.ones(len(rows), dtype=np.int8), (rows, flat.ravel())),
                       shape=(n_points, n_points))
    _, label = connected_components(graph, directed=False)
    # the grid is in lexicographic order, so each orbit's first index is its first point
    _, first = np.unique(label, return_index=True)
    out = []
    for i in sorted(first):
        anchor = tuple(Fraction(int(v), D) for v in g[i])
        out.append((anchor, [ops[k][0] for k in np.nonzero(fixed[i])[0]]))
    return out


@lru_cache(maxsize=None)
def _hall_group(hall: int) -> _Group:
    return _from_operations(gemmi.symops_from_hall(spglib.get_spacegroup_type(hall).hall_symbol))


@lru_cache(maxsize=None)
def _halls_by_number() -> dict[int, tuple[int, ...]]:
    """Every type's Hall numbers, from one pass over the 530 settings."""
    out: dict[int, list[int]] = {}
    for h in range(1, 531):
        out.setdefault(int(spglib.get_spacegroup_type(h).number), []).append(h)
    return {n: tuple(hs) for n, hs in out.items()}


def _halls_of(number: int) -> tuple[int, ...]:
    return _halls_by_number().get(number, ())


def _hall_of(G: _Group, number: int) -> int | None:
    """spglib's Hall number of the setting G is in, or None when G is in none of them."""
    key = G.key()
    return next((h for h in _halls_of(number) if _hall_group(h).key() == key), None)


@lru_cache(maxsize=None)
def _hall_table(hall: int) -> _Table:
    """The positions of a Hall setting, lettered by spglib in that setting."""
    return _Table(_hall_group(hall), lambda table: _spglib_letters(table, hall))


def _spglib_letters(table: _Table, hall: int) -> None:
    """Give each position spglib's letter for this Hall setting, through spglib's own frame.

    spglib names an atom in *its* standardised frame, x_std = M·x + o, which
    can differ from the input frame by an element of the affine normaliser
    even when the input is already in the setting asked for, so the letter it
    gives an atom belongs to the position holding the atom's *image*.  (M, o)
    is checked to map the group onto itself exactly before it is used.
    """
    G = table.G
    metric = _metric(G)
    cell = np.linalg.cholesky(metric)  # rows: the conventional a, b, c (Cartesian)
    positions, numbers, first = [], [], []
    generics = [table.generic(species) for species in range(len(table.classes))]
    for species, x in enumerate(generics):
        orbit = sorted({_frac_part(_add(_mv(W, x), w)) for W, w in table.ops})
        first.append(len(positions))
        positions += [[float(v) for v in y] for y in orbit]
        numbers += [species + 1] * len(orbit)
    # two generic orbits more, as in the subgroup probe: one atom alone would be P-1
    for extra, x in enumerate(_PROBE_POINTS):
        orbit = sorted({_frac_part(_add(_mv(W, x), w)) for W, w in table.ops})
        positions += [[float(v) for v in y] for y in orbit]
        numbers += [len(table.classes) + extra + 1] * len(orbit)
    try:
        data = spglib.get_symmetry_dataset((cell, positions, numbers), symprec=_PROBE_SYMPREC,
                                           hall_number=hall)
    except SPGLIB_REFUSALS:
        data = None
    if data is None or int(data.hall_number) != hall:
        raise RuntimeError(f"spglib does not name Hall setting {hall} for its own probe; "
                           "this is a bug")
    M = tuple(tuple(Fraction(float(v)).limit_denominator(_PROBE_DENOMINATOR_FLOOR) for v in row)
              for row in data.transformation_matrix)
    o = tuple(Fraction(float(v)).limit_denominator(_PROBE_DENOMINATOR_FLOOR)
              for v in data.origin_shift)
    P = _inv(M)
    p = tuple(-v for v in _mv(P, o))
    if G.transformed(P, p).key() != G.key():
        raise RuntimeError(f"spglib's frame for Hall setting {hall} is not a normaliser "
                           "element of the group; this is a bug")
    for species, cls in enumerate(table.classes):
        image = _add(_mv(M, generics[species]), o)
        target = table.classes[table.identify(image)]
        if target[0] is not None:
            raise RuntimeError(f"spglib's frame maps two positions of Hall setting {hall} "
                               "onto one; this is a bug")
        target[0] = str(data.wyckoffs[first[species]])
        target[1] = str(data.site_symmetry_symbols[first[species]])


class _Positions:
    """A group's positions in its own coordinates: a Hall table, possibly through (P, p)."""

    def __init__(self, G: _Group):
        self.G = G
        number, symbol, transform = _standardise(G, _metric(G))
        hall = _hall_of(G, number)
        if hall is None:  # not a Hall setting: letters through spglib's standardisation
            self.transform = transform
            self.table = _hall_table(_hall_of(_standard_of_symbol(symbol)[0], number))
            self.standard = symbol
        else:
            self.transform = _IDENTITY
            self.table = _hall_table(hall)
            self.standard = _xhm_of_hall(hall)
        self.number = number
        P, p = self.transform
        self.scale = abs(_rational_determinant(P))  # standard cell volume / this cell's
        self._Q = _inv(P)

    def to_standard(self, x):
        return _mv(self._Q, _sub(x, self.transform[1]))

    def position(self, i) -> WyckoffPosition:
        letter, site, mult, order, anchor, directions = self.table.classes[i]
        P, p = self.transform
        point = _add(_mv(P, anchor), p)
        dirs = []
        for d in directions:
            v = _mv(P, tuple(Fraction(x) for x in d))
            den = 1
            for x in v:
                den = den * x.denominator // math.gcd(den, x.denominator)
            v = [int(x * den) for x in v]
            g = math.gcd(*v)
            dirs.append(tuple(x // g for x in v))
        if (mult / self.scale).denominator != 1:  # pragma: no cover - a cell holds whole orbits
            raise RuntimeError("a Wyckoff multiplicity is not whole in this cell; this is a bug")
        return WyckoffPosition(letter=letter, multiplicity=int(mult / self.scale),
                               site_symmetry=site, site_order=order,
                               point=_frac_part(point), directions=tuple(dirs))

    def label(self, i) -> str:
        return self.position(i).label


def _xhm_of_hall(hall: int) -> str:
    sg = gemmi.find_spacegroup_by_ops(gemmi.symops_from_hall(
        spglib.get_spacegroup_type(hall).hall_symbol))
    return sg.xhm() if sg is not None else spglib.get_spacegroup_type(hall).international_full


def wyckoff_positions(group) -> WyckoffPositions:
    """The Wyckoff positions of ``group``, found from its operations alone.

    ``group`` is any symbol gemmi resolves, a ``gemmi.SpaceGroup`` or an
    :class:`~rietx.crystallography.symmetry.OperatorGroup`, in any setting.
    The positions are the classes of points whose site-symmetry groups are
    conjugate in the group (Souvignier et al. 2016, ITA A § 1.4.4.2), found on the
    1/24 grid of the conventional cell and identified exactly; over the 230
    types they number 1731, ITA's total.  The letters are spglib's (Togo,
    Shinohara & Tanaka 2024), stated as belonging to the setting and (P, p)
    the result names (A1 § 3.1.1.6.5).  Positions come in letter order, the
    general position last.
    """
    pos = _Positions(_group_of(group))
    return WyckoffPositions(symbol=as_group(group).xhm(), number=pos.number, standard=pos.standard,
                            transform=pos.transform,
                            positions=tuple(pos.position(i)
                                            for i in range(len(pos.table.classes))))


def _letter_at(group, xyz, site_order: int, tol: float) -> str | None:
    """The letter :func:`wyckoff_positions` gives the position holding ``xyz``, or None.

    ``xyz`` is a float fractional point with ``site_order`` operations in its
    site-symmetry group (``wyckoff.site_constraints`` has both), ``tol`` its
    distance to a special position.  The test is :meth:`_Table._hits`' (an
    image of the point solves N·(x + u) = c over the integers), made on floats
    with ``tol``: a point with a free parameter has no exact rational form on
    a line like x + y = 1/2.  None when the point lies on no single position
    or on one whose site symmetry is not ``site_order``; the caller keeps its
    own letter, as the tolerance, not the table, would be at fault.
    """
    pos = _Positions(_group_of(group))
    table = pos.table
    x = np.array([float(v) for v in pos.to_standard(tuple(Fraction(float(v)) for v in xyz))])
    shifts = np.array(list(itertools.product(range(-3, 4), repeat=3)), dtype=np.float64)
    hits = set()
    for i, comps in enumerate(table.components):
        if table.classes[i][3] != site_order:
            continue
        for N, c in (nc for ncs in comps.values() for nc in ncs):
            Nf = np.array(N, dtype=np.float64)
            res = Nf @ x - np.array([float(v) for v in c]) + shifts @ Nf.T
            if (np.abs(res).max(axis=1) < tol).any():
                hits.add(i)
                break
    return table.classes[hits.pop()][0] if len(hits) == 1 else None


def _subgroup_of(sub):
    """(symbol, (P, p)) of a :class:`MaximalSubgroup` or a ``(symbol, transform)`` pair."""
    if isinstance(sub, MaximalSubgroup):
        return sub.symbol, sub.transform
    symbol, transform = sub
    return symbol, (_mat(transform[0]), tuple(_q(x) for x in transform[1]))


def _coset_vectors(L, sub_L):
    """Representatives of the lattice L modulo its sublattice ``sub_L`` (both column bases)."""
    sub_inv = _inv(sub_L)
    zero = (Fraction(0), Fraction(0), Fraction(0))
    found = {zero}
    frontier = [zero]
    while frontier:
        new = []
        for v in frontier:
            for col in _columns(L):
                u = _reduce(_add(v, col), sub_L, sub_inv)
                if u not in found:
                    found.add(u)
                    new.append(u)
        frontier = new
    return sorted(found)


def wyckoff_splitting(group, sub) -> WyckoffSplitting:
    """How every Wyckoff position of ``group`` splits in the subgroup ``sub``.

    ``sub`` is a :class:`MaximalSubgroup` of ``group`` (from :func:`maximal`)
    or any subgroup as a pair ``(symbol, (P, p))``, r_group = P·r_sub + p,
    maximal or not.  For each position of G a generic point's G-orbit is
    decomposed into H-orbits, each mapped by (P, p) into H's setting and
    identified there exactly (Müller 2011, ITA A1 ch. 3.1; the procedure
    Aroyo, Perez-Mato, Capillas & Wondratschek 2011 describe in A1 § 1.7.4).  The result carries the (P, p)
    H's labels belong to (A1 § 3.1.1.6.5), and every row is checked against
    Σ m_H = m_G·|det P|.  Raises ``ValueError`` when ``sub`` is not a
    subgroup of ``group``.
    """
    G = _group_of(group)
    symbol, transform = _subgroup_of(sub)
    where = f"{symbol} under P = {_text(transform[0])}, p = {_text(transform[1])}"
    try:
        H = _rebuild(symbol, transform)
    except _NotIntegral:
        raise ValueError(f"{where} is not a subgroup of the group") from None
    if not H.is_subgroup_of(G):
        raise ValueError(f"{where} is not a subgroup of the group")
    P, p = transform
    Q = _inv(P)
    det_P = abs(_rational_determinant(P))
    g_pos = _Positions(G)
    h_pos = _Positions(_standard_of_symbol(symbol)[0])
    cosets = _coset_vectors(G.L, H.L)
    rows = []
    for i in range(len(g_pos.table.classes)):
        g_label = g_pos.label(i)
        P0, p0 = g_pos.transform
        x = _add(_mv(P0, g_pos.table.generic(i)), p0)  # a generic point, in G's coordinates
        orbit = {_reduce(_add(_add(_mv(W, x), w), t), H.L, H.Linv)
                 for W, w in G.reps.items() for t in cosets}
        seen: set = set()
        found = []
        for z in sorted(orbit):
            if z in seen:
                continue
            h_orbit = {_reduce(_add(_mv(W, z), w), H.L, H.Linv) for W, w in H.reps.items()}
            seen |= h_orbit
            j = h_pos.table.identify(h_pos.to_standard(_mv(Q, _sub(z, p))))
            pos = h_pos.position(j)
            if pos.multiplicity * abs(_rational_determinant(H.L)) != len(h_orbit) * det_P:
                raise RuntimeError(f"an orbit of {len(h_orbit)} points of {symbol} was "
                                   f"identified as {pos.label}; this is a bug")
            found.append((j, pos))
        if sum(pos.multiplicity for _, pos in found) \
                != g_pos.position(i).multiplicity * det_P:  # pragma: no cover - implied above
            raise RuntimeError("Σ m_H ≠ m_G·|det P|; this is a bug")
        rows.append((g_label, tuple(pos.label for _, pos in sorted(found, key=lambda f: f[0]))))
    return WyckoffSplitting(group=as_group(group).xhm(),
                            subgroup=symbol, transform=(P, p),
                            group_transform=g_pos.transform, rows=tuple(rows))
