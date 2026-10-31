"""Maximal subgroups of a space group, generated from its own operations.

**Public API — WP-1919, PR 1.**

::

    maximal(group, kind="both", max_index=None, *, index=None, supercell=None)
                                              -> tuple[MaximalSubgroup, ...]
    is_maximal(group, symbol, transform)      -> bool

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
from ..wyckoff import SPGLIB_REFUSALS
from .irreps import _row_hnf

__all__ = ["MAX_INDEX", "MaximalSubgroup", "is_maximal", "maximal"]

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
    return _from_pairs((tuple(tuple(int(v) // den for v in row) for row in op.rot),
                        tuple(Fraction(int(t), den) for t in op.tran)) for op in ops)


def _from_pairs(pairs) -> _Group:
    """A :class:`_Group` from exact (W, w) pairs: every operation, centrings included.

    W is an integer 3×3 and w a rational 3-vector in the group's own
    coordinates, whose unit cell is a cell of the group's lattice; a w with
    W = 1 adds a centring to it.
    """
    vectors = [(Fraction(1), Fraction(0), Fraction(0)), (Fraction(0), Fraction(1), Fraction(0)),
               (Fraction(0), Fraction(0), Fraction(1))]
    reps = {}
    for W, w in pairs:
        W = tuple(tuple(int(v) for v in row) for row in W)
        w = tuple(_q(t) for t in w)
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
    return _exact_setting(H, data, H.L, bound, lambda p: _short_origin(p, H))


def _exact_setting(H: _Group, data, cell, bound: int, place=None):
    """(number, symbol, (P, p)) of H from spglib's dataset, checked exactly.

    ``data`` is spglib's answer for a probe of H whose unit cell has the
    columns of ``cell`` as its axes, in H's own coordinates (H's primitive
    lattice for :func:`_standardise`, the magnetic cell for
    ``distortion_candidates``).  spglib's matrix and origin are floats: each
    is snapped to the nearest ratio with a denominator up to ``bound``, and
    ``place`` may then move the origin p (by a translation that leaves the
    subgroup as it is).  The result is accepted only if P⁻¹HP is spglib's
    standard setting of the type exactly, operation list and lattice, in
    ``Fraction`` arithmetic; otherwise this raises.
    """
    std, symbol, number = _standard(int(data.hall_number))
    M = tuple(tuple(Fraction(float(x)).limit_denominator(bound) for x in row)
              for row in data.transformation_matrix)
    o = tuple(Fraction(float(x)).limit_denominator(bound) for x in data.origin_shift)
    P = _mm(_mat(cell), _inv(M))
    p = tuple(-x for x in _mv(P, o))
    if place is not None:
        p = place(p)
    try:
        same = H.transformed(P, p).key() == std.key()
    except _NotIntegral:  # P carries some W of H to a non-integral matrix: no setting of H
        same = False
    if not same:
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
