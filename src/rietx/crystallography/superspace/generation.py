"""The (3+1)D superspace groups from a basic space group and q, and equivalence.

This is the generator route of the scoping report's decision 10: rietx ships
no table of superspace groups (the ISO(3+d)D data files may not be
redistributed), it derives them.  The construction is the one Stokes,
Campbell & van Smaalen (2011), *Acta Cryst.* A**67**, 45, § 3 describe, and
which de Wolff, Janssen & Janner (1981), *Acta Cryst.* A**37**, 625, § 6 did
by hand:

1. **ε and M are fixed by the basic space group and q** (Stokes 2011 eq. (2),
   qR = εq + M).  The incommensurate part of q lies in a subspace V on which
   every point operation acts as a sign, ε(R) = ±1, which is a
   one-dimensional character of the point group; the rational part q_r must
   make M = q_rR − εq_r a reciprocal-lattice vector.  q_r matters only modulo
   V and the reciprocal lattice L* (q → q + H is an equivalence, van Smaalen,
   Campbell & Stokes, 2013, *Acta Cryst.* A**69**, 75, § 3.2).
2. **Only δ is free, and closure fixes it** (Stokes 2011 eq. (8),
   δ_c = M_a·v_b + ε_aδ_b + δ_a mod 1): a set of linear congruences with
   integer coefficients.  Its real solutions are the internal-origin shifts
   alone (ε = −1 operations move by 2c), which one equation fixes (de Wolff
   1981 p. 635: "the τ of the chosen element with ε = −1 can always be taken as
   zero"); what remains is a finite set, enumerated exactly by integer row
   reduction and back-substitution — the d = 1 case of the Smith-normal-form
   solve Stokes 2011 cites (Grosse-Kunstleve, 1999, *Acta Cryst.* A**55**,
   383), which needs no search over a guessed set of shifts.
3. **Solutions are identified under equivalence** (Stokes 2011 eq. (13)):
   affine maps of superspace that normalise the basic space group, together
   with q → −q, q → q + H (H ∈ L*) and internal-origin shifts.  The normaliser
   is found by search over lattice automorphisms with entries in {−1, 0, 1}
   (in the conventional and in a primitive basis) and over origin shifts on a
   1/24 grid; orbits are closed by breadth-first search under those
   generators.  For d = 1 this is the whole of van Smaalen et al. (2013)'s
   equivalence: a change of basic cell, q → q + H and an origin shift (the
   linear recombination of q vectors is a d ≥ 2 equivalence).

Settings: the basic space groups are taken in the Stokes 2011 § 5.1(2)
convention (origin choice 2, hexagonal axes, monoclinic unique axis b and
cell choice 1 for the generator's internal work).  Centrings are lifted with
zero internal component — the "BSG setting" of Stokes 2011 p. 49 — so a
supercentred description (Yamamoto, Janssen, Janner & de Wolff, 1985,
*Acta Cryst.* A**41**, 528, § 2) is brought to that setting by a q → q + H
before comparison.

Pinned counts (``tests/test_superspace.py``): 775 groups from the 230 basic
groups (Yamamoto et al. 1985 p. 529; Stokes 2011 p. 47) and 24 Bravais
classes (Stokes 2011 p. 49).
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

import gemmi
import numpy as np

from .operators import (
    ModulationVector,
    SuperspaceGroup,
    SuperspaceOperator,
    _inverse3,
    _rkey,
)

#: (3+1)D superspace-group types (Yamamoto et al. 1985 p. 529; Stokes 2011
#: p. 47; Stokes & Campbell 2022 Table 6, type-1 row).
N_SUPERSPACE_GROUPS_D1 = 775

#: (3+1)D Bravais classes (de Wolff et al. 1981 § 4; Stokes 2011 p. 49).
N_BRAVAIS_CLASSES_D1 = 24

_E = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
_GRID = 24          # origin-shift grid of the normaliser search, 1/24
_F0 = Fraction(0)


# ---------------------------------------------------------------------------
# basic space groups
# ---------------------------------------------------------------------------
@functools.lru_cache(maxsize=None)
def standard_setting(number: int) -> gemmi.SpaceGroup:
    """The setting the generator works in: ITA's, with origin choice 2,
    hexagonal axes and unique axis b, cell choice 1 (Stokes 2011 § 5.1(2))."""
    entries = [s for s in gemmi.spacegroup_table() if s.number == number]
    if not entries:
        raise ValueError(f"no space group number {number}")
    for want in ("2", "H"):
        for s in entries:
            if s.ext == want:
                return s
    return entries[0]


@dataclass(frozen=True)
class _Basic:
    """A basic space group as coset representatives and centrings, exact."""

    ops: tuple                     # ((R, v), ...), identity first
    centrings: tuple               # (t, ...), zero first

    @functools.cached_property
    def by_r(self) -> dict:
        return {_rkey(r): (r, v) for r, v in self.ops}

    @functools.cached_property
    def rotations(self) -> tuple:
        return tuple(r for r, _ in self.ops)


def _basic_from_gemmi(sg: gemmi.SpaceGroup) -> _Basic:
    go = sg.operations()
    den = gemmi.Op.DEN
    ops = []
    for op in go.sym_ops:
        r = tuple(tuple(x // den for x in row) for row in op.rot)
        v = tuple(Fraction(x, den) % 1 for x in op.tran)
        ops.append((r, v))
    ops.sort(key=lambda rv: (rv[0] != _E, _rkey(rv[0])))
    cen = sorted({tuple(Fraction(x, den) % 1 for x in c) for c in go.cen_ops})
    return _Basic(tuple(ops), tuple(cen))


def _basic_from_ops(ops3) -> _Basic:
    """From (R, v) pairs covering a group modulo ℤ³ (centrings included)."""
    by_r: dict = {}
    cen = set()
    for r, v in ops3:
        r = tuple(tuple(int(x) for x in row) for row in r)
        v = tuple(Fraction(x) % 1 for x in v)
        if r == _E:
            cen.add(v)
        by_r.setdefault(_rkey(r), (r, v))
    ops = sorted(by_r.values(), key=lambda rv: (rv[0] != _E, _rkey(rv[0])))
    ops[0] = (_E, (_F0, _F0, _F0))
    return _Basic(tuple(ops), tuple(sorted(cen)))


def _in_lattice(x, centrings) -> bool:
    return any(all((x[i] - c[i]) % 1 == 0 for i in range(3)) for c in centrings)


def _in_lstar(h, centrings) -> bool:
    """H in the reciprocal lattice: integer, and H·t ∈ ℤ for every centring."""
    if any(Fraction(x).denominator != 1 for x in h):
        return False
    return all(sum(h[i] * c[i] for i in range(3)) % 1 == 0 for c in centrings)


def _matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def _rowmat(row, m):
    return tuple(sum(row[i] * m[i][j] for i in range(3)) for j in range(3))


def _point_generators(rots) -> list:
    """A small generating set of a finite matrix group (highest orders first)."""
    rots = list(rots)
    gens: list = []
    have = {_E}
    for r in sorted(rots, key=lambda r: (-_order(r), _rkey(r))):
        if len(have) == len(rots):
            break
        if r in have:
            continue
        gens.append(r)
        frontier = list(have)
        while frontier:
            nxt = []
            for a in frontier:
                for g in gens:
                    for p in (_matmul(a, g), _matmul(g, a)):
                        if p not in have:
                            have.add(p)
                            nxt.append(p)
            frontier = nxt
    return gens


def _order(r) -> int:
    p, n = r, 1
    while p != _E:
        p = _matmul(p, r)
        n += 1
        if n > 12:
            raise ValueError("not a crystallographic rotation")
    return n


# ---------------------------------------------------------------------------
# q families
# ---------------------------------------------------------------------------
def _characters(basic: _Basic) -> list[tuple[tuple, tuple]]:
    """(axes of V, ε per op) for every one-dimensional character whose
    eigenspace {q : qR = ε(R) q ∀R} is nonzero and axis-aligned.

    Raises if a nonzero eigenspace is not spanned by coordinate axes: the
    generator's settings put every d = 1 modulation direction on an axis.
    """
    rots = basic.rotations
    gens = _point_generators(rots)
    out = []
    for signs in product((1, -1), repeat=len(gens)):
        # V = ∩ {q : q g = s q} for the generators
        rows = []
        for g, s in zip(gens, signs):
            for j in range(3):
                rows.append([Fraction(g[i][j] - (s if i == j else 0)) for i in range(3)])
        basis = _nullspace(rows, 3)
        if not basis:
            continue
        axes = tuple(sorted({i for b in basis for i in range(3) if b[i] != 0}))
        if len(axes) != len(basis) or any(sum(1 for x in b if x) != 1 for b in basis):
            # re-express: a subspace spanned by axes has a one-hot basis
            raise ValueError(
                f"a modulation subspace {basis} is not spanned by coordinate "
                f"axes in this setting; the generator assumes it is")
        eps = []
        for r in rots:
            ax = axes[0]
            q = [0, 0, 0]
            q[ax] = 1
            qr = _rowmat(q, r)
            if qr == tuple(q):
                eps.append(1)
            elif qr == tuple(-x for x in q):
                eps.append(-1)
            else:
                raise AssertionError("character does not act as a sign")
        out.append((axes, tuple(eps)))
    uniq = {}
    for axes, eps in out:
        uniq.setdefault(axes, eps)
    return sorted(uniq.items())


def _nullspace(rows, n):
    m = [r[:] for r in rows]
    piv = []
    rr = 0
    for c in range(n):
        p = next((i for i in range(rr, len(m)) if m[i][c] != 0), None)
        if p is None:
            continue
        m[rr], m[p] = m[p], m[rr]
        inv = m[rr][c]
        m[rr] = [x / inv for x in m[rr]]
        for i in range(len(m)):
            if i != rr and m[i][c] != 0:
                f = m[i][c]
                m[i] = [a - f * b for a, b in zip(m[i], m[rr])]
        piv.append(c)
        rr += 1
    basis = []
    for c in range(n):
        if c in piv:
            continue
        v = [Fraction(0)] * n
        v[c] = Fraction(1)
        for i, pc in enumerate(piv):
            v[pc] = -m[i][c]
        basis.append(v)
    return basis


_QR_COMPONENTS = (Fraction(0), Fraction(1, 2), Fraction(1), Fraction(1, 3),
                  Fraction(2, 3))


@functools.lru_cache(maxsize=None)
def _canon_qr(qr, axes, centrings) -> tuple[tuple, tuple]:
    """(canonical q_r, H): q_r + H reduced modulo V, H ∈ L*, chosen as the
    smallest representative — the class of q_r modulo L* + V."""
    def zero_v(x):
        return tuple(_F0 if i in axes else x[i] for i in range(3))

    best = None
    for h in product(range(-2, 4), repeat=3):
        h = tuple(Fraction(x) for x in h)
        if any(h[i] != 0 for i in axes):
            continue
        if not _in_lstar(h, centrings):
            continue
        r = zero_v(tuple(qr[i] + h[i] for i in range(3)))
        if any(x < 0 or x > 1 for x in r):
            continue
        key = (sum(r), sum(1 for x in r if x), tuple(-x for x in r))
        if best is None or key < best[0]:
            best = (key, r, h)
    if best is None:  # pragma: no cover - the box always holds a representative
        raise AssertionError(f"no canonical representative for q_r = {qr}")
    return best[1], best[2]


def _families(basic: _Basic) -> list[tuple[tuple, tuple, tuple]]:
    """Every q family (axes, ε, canonical q_r) compatible with the group."""
    fams = []
    for axes, eps in _characters(basic):
        others = [i for i in range(3) if i not in axes]
        seen = set()
        for comps in product(_QR_COMPONENTS, repeat=len(others)):
            qr = [_F0, _F0, _F0]
            for i, c in zip(others, comps):
                qr[i] = c
            qr = tuple(qr)
            ok = True
            for (r, _), e in zip(basic.ops, eps):
                m = tuple(_rowmat(qr, r)[j] - e * qr[j] for j in range(3))
                if not _in_lstar(m, basic.centrings):
                    ok = False
                    break
            if not ok:
                continue
            can, _ = _canon_qr(qr, axes, basic.centrings)
            if can in seen:
                continue
            seen.add(can)
            fams.append((axes, eps, can))
    return fams


# ---------------------------------------------------------------------------
# the internal translations: closure as congruences mod 1
# ---------------------------------------------------------------------------
def _m_rows(basic: _Basic, eps, qr) -> list[tuple]:
    out = []
    for (r, _), e in zip(basic.ops, eps):
        qrr = _rowmat(qr, r)
        out.append(tuple(int(qrr[j] - e * qr[j]) for j in range(3)))
    return out


def _solve_deltas(basic: _Basic, eps, qr) -> list[tuple]:
    """Every δ assignment (one per coset representative) that closes, with the
    internal origin fixed by δ = 0 on the first ε = −1 representative.

    Equations: δ(ab) ≡ M_a·v_b + ε_aδ(b) + δ(a) (mod 1) for a in a generating
    set and every b (Stokes 2011 eq. (8)); the centrings carry δ = 0 and
    M·t ∈ ℤ for them because M ∈ L*.
    """
    ops = basic.ops
    n = len(ops)
    index = {_rkey(r): i for i, (r, _) in enumerate(ops)}
    ms = _m_rows(basic, eps, qr)
    gens = _point_generators(basic.rotations)
    rows: list[list[int]] = []
    rhs: list[Fraction] = []
    for g in gens:
        a = index[_rkey(g)]
        for b, (rb, vb) in enumerate(ops):
            c = index[_rkey(_matmul(g, rb))]
            row = [0] * n
            row[c] += 1
            row[b] -= eps[a]
            row[a] -= 1
            rows.append(row)
            rhs.append(sum(ms[a][k] * vb[k] for k in range(3)))
    row0 = [0] * n
    row0[0] = 1
    rows.append(row0)
    rhs.append(_F0)
    neg = [i for i, e in enumerate(eps) if e == -1]
    if neg:
        row = [0] * n
        row[neg[0]] = 1
        rows.append(row)
        rhs.append(_F0)
    return _solve_mod1(rows, rhs, n)


def _solve_mod1(rows, rhs, n) -> list[tuple]:
    """All x ∈ (ℚ/ℤ)ⁿ with A x ≡ b (mod 1): integer row echelon, then
    back-substitution branching over each pivot's residues."""
    a = [list(r) for r in rows]
    b = list(rhs)
    pivots = []
    top = 0
    for c in range(n):
        while True:
            nz = [i for i in range(top, len(a)) if a[i][c] != 0]
            if not nz:
                break
            p = min(nz, key=lambda i: abs(a[i][c]))
            a[top], a[p] = a[p], a[top]
            b[top], b[p] = b[p], b[top]
            done = True
            for i in range(top + 1, len(a)):
                if a[i][c] != 0:
                    k = a[i][c] // a[top][c]
                    a[i] = [x - k * y for x, y in zip(a[i], a[top])]
                    b[i] = b[i] - k * b[top]
                    if a[i][c] != 0:
                        done = False
            if done:
                break
        if any(a[i][c] != 0 for i in range(top, len(a))):
            pivots.append((top, c))
            top += 1
    for i in range(top, len(a)):
        if b[i] % 1 != 0:
            return []
    if len(pivots) != n:
        raise AssertionError(
            "the closure congruences leave a continuous family after the "
            "internal origin is fixed; that contradicts H¹(K, ℝ) = 0")
    sols: list[list[Fraction]] = [[_F0] * n]
    for row_i, c in reversed(pivots):
        piv = a[row_i][c]
        nxt = []
        for x in sols:
            rest = b[row_i] - sum(a[row_i][j] * x[j] for j in range(c + 1, n))
            for k in range(abs(piv)):
                y = list(x)
                y[c] = ((rest + k) / piv) % 1
                nxt.append(y)
        sols = nxt
    return sorted({tuple(x) for x in sols})


# ---------------------------------------------------------------------------
# normaliser of the basic group
# ---------------------------------------------------------------------------
def _primitive_basis(centrings) -> tuple:
    """A primitive basis of ℤ³ + centrings, as columns (conventional coords)."""
    vecs = [tuple(Fraction(int(i == j)) for j in range(3)) for i in range(3)]
    vecs += [tuple(c) for c in centrings if any(c)]
    # LLL-free choice: try triples of small lattice vectors with det = 1/|cen|
    target = Fraction(1, len(centrings))
    cands = set()
    for c in centrings:
        for shift in product((-1, 0, 1), repeat=3):
            v = tuple(c[i] + shift[i] for i in range(3))
            if any(v):
                cands.add(v)
    cands = sorted(cands, key=lambda v: (sum(abs(x) for x in v), v))
    for trip in _triples(cands):
        m = [[trip[j][i] for j in range(3)] for i in range(3)]
        d = _det3(m)
        if abs(d) == target:
            if d < 0:
                trip = (trip[0], trip[1], tuple(-x for x in trip[2]))
            return tuple(tuple(trip[j][i] for j in range(3)) for i in range(3))
    raise AssertionError("no primitive basis found")  # pragma: no cover


def _triples(cands):
    n = len(cands)
    for i in range(n):
        for j in range(i + 1, n):
            for k in range(j + 1, n):
                yield (cands[i], cands[j], cands[k])


def _det3(m):
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


@functools.lru_cache(maxsize=None)
def _automorphism_candidates(centrings: tuple) -> np.ndarray:
    """Lattice automorphisms with small entries, conventional coordinates:
    {−1,0,1} matrices in the conventional basis and in a primitive basis.
    Returned as float arrays (N, 3, 3) with their inverses' integrality
    checked by the caller."""
    vals = np.array(list(product((-1, 0, 1), repeat=9)), dtype=float).reshape(-1, 3, 3)
    dets = np.round(np.linalg.det(vals))
    unimod = vals[np.abs(dets) == 1]
    mats = [unimod]
    if len(centrings) > 1:
        c = np.array([[float(x) for x in row] for row in _primitive_basis(centrings)])
        ci = np.linalg.inv(c)
        mats.append(np.einsum("ij,njk,kl->nil", c, unimod, ci))
    allm = np.concatenate(mats)
    allm = np.round(allm * 6) / 6
    keys = {}
    for m in allm:
        keys.setdefault(tuple(np.round(m * 6).astype(int).ravel()), m)
    allm = np.array(list(keys.values()))
    # keep those mapping the lattice (ℤ³ + centrings) onto itself
    cen = np.array([[float(x) for x in t] for t in centrings])

    def in_lat(x):  # x: (N, k, 3)
        ok = np.zeros(x.shape[:2], dtype=bool)
        for t in cen:
            d = x - t
            ok |= np.all(np.abs(d - np.round(d)) < 1e-9, axis=-1)
        return ok

    inv = np.linalg.inv(allm)
    good = np.ones(len(allm), dtype=bool)
    for m in (allm, inv):
        cols = np.swapaxes(m, 1, 2)                       # basis images
        good &= in_lat(cols).all(axis=1)
        imgs = np.einsum("nij,kj->nki", m, cen)           # centring images
        good &= in_lat(imgs).all(axis=1)
    return allm[good]


def _key9(m) -> tuple:
    return tuple(int(round(x)) for x in np.asarray(m).ravel())


@functools.lru_cache(maxsize=None)
def _normaliser(basic: _Basic) -> tuple:
    """Generators (P, p) of the affine normaliser modulo the group itself,
    the lattice and the polar (continuous) origin shifts.

    P: lattice automorphism with P K P⁻¹ = K, one per coset K·P; p: every
    origin shift on the 1/24 grid with P g P⁻¹ ∈ G for the generators g,
    reduced modulo the lattice and with polar components zeroed.

    These are the external blocks (S_R, S_v) of the equivalence map of
    Stokes, Campbell & van Smaalen (2011), *Acta Cryst.* A**67**, 45,
    eq. (13), restricted to maps that normalise the basic space group — the
    change of basic cell of van Smaalen, Campbell & Stokes (2013),
    *Acta Cryst.* A**69**, 75, § 3.1 and conclusions.
    """
    rots = basic.rotations
    rk = {_key9(r) for r in rots}
    cand = _automorphism_candidates(basic.centrings)
    inv = np.linalg.inv(cand)
    gens = _point_generators(rots)
    ok = np.ones(len(cand), dtype=bool)
    for g in gens:
        conj = np.einsum("nij,jk,nkl->nil", cand, np.asarray(g, float), inv)
        rnd = np.round(conj)
        integral = np.all(np.abs(conj - rnd) < 1e-9, axis=(1, 2))
        member = np.array([_key9(x) in rk for x in rnd], dtype=bool)
        ok &= integral & member
    cand, inv = cand[ok], inv[ok]
    # one P per coset K·P
    reps = {}
    for p_m in cand:
        key = min(_key9(np.asarray(r, float) @ p_m * 6) for r in rots)
        reps.setdefault(key, p_m)
    # polar subspace: axes fixed by every rotation
    polar = [i for i in range(3)
             if all(r[j][i] == (1 if j == i else 0) and r[i][j] == (1 if j == i else 0)
                    for r in rots for j in range(3))]
    axes_ranges = [(0,) if i in polar else range(_GRID) for i in range(3)]
    grid = np.array(list(product(*axes_ranges)), dtype=float) / _GRID
    cen = np.array([[float(x) for x in t] for t in basic.centrings])
    out = []
    for p_m in reps.values():
        p_inv = np.linalg.inv(p_m)
        good = np.ones(len(grid), dtype=bool)
        for g in gens:
            v = np.array([float(x) for x in basic.by_r[_rkey(g)][1]])
            rprime = np.round(p_m @ np.asarray(g, float) @ p_inv)
            target = np.array([float(x) for x in basic.by_r[_key9(rprime)][1]])
            res = ((np.eye(3) - rprime) @ grid.T).T - (target - p_m @ v)
            inl = np.zeros(len(grid), dtype=bool)
            for t in cen:
                d = res - t
                inl |= np.all(np.abs(d - np.round(d)) < 1e-9, axis=1)
            good &= inl
        ps = np.round(grid[good] * _GRID).astype(int)
        if len(ps) == 0:
            continue
        # reduce modulo the lattice: the smallest representative over centrings
        cen_i = np.round(cen * _GRID).astype(int)
        reps_p = np.stack([(ps - c) % _GRID for c in cen_i])      # (C, N, 3)
        codes = (reps_p[..., 0] * _GRID + reps_p[..., 1]) * _GRID + reps_p[..., 2]
        best = codes.min(axis=0)
        pm_frac = tuple(tuple(Fraction(x).limit_denominator(6) for x in row) for row in p_m)
        for code in np.unique(best):
            c = int(code)
            pv = (Fraction(c // (_GRID * _GRID), _GRID), Fraction((c // _GRID) % _GRID, _GRID),
                  Fraction(c % _GRID, _GRID))
            out.append((pm_frac, pv))
    return tuple(out)


# ---------------------------------------------------------------------------
# nodes: one concrete superspace group over a fixed basic group
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Node:
    axes: tuple
    qr: tuple
    deltas: tuple

    def key(self) -> tuple:
        return (self.axes, self.qr, self.deltas)


@dataclass(frozen=True)
class _Element:
    """A normaliser element (P, p) prepared for repeated use on nodes."""

    perm: tuple          # coset index i → index of P R_i P⁻¹
    p_inv: tuple         # P⁻¹, exact
    w: tuple             # P⁻¹ p, so that δ′ = δ − M_i·(P⁻¹p)
    axis_image: tuple    # axis → axis under the row action q ↦ qP⁻¹, or None


class _Space:
    """The superspace groups over one basic group, and the maps between them."""

    def __init__(self, basic: _Basic, number: int | None = None):
        self.basic = basic
        self.number = number
        self.index = {_rkey(r): i for i, (r, _) in enumerate(basic.ops)}
        self.chars = dict(_characters(basic))
        self.lstar_basis = _lstar_basis(basic.centrings)
        self._ms: dict = {}

    def eps(self, axes) -> tuple:
        return self.chars[axes]

    def ms(self, axes, qr) -> list:
        key = (axes, qr)
        got = self._ms.get(key)
        if got is None:
            got = self._ms[key] = _m_rows(self.basic, self.eps(axes), qr)
        return got

    @functools.cached_property
    def elements(self) -> tuple:
        norm = _normaliser(self.basic)
        if not norm:
            return ()
        pm = np.array([[[float(x) for x in row] for row in p_m] for p_m, _ in norm])
        pv = np.array([[float(x) for x in p] for _, p in norm])
        pinv = np.linalg.inv(pm)
        rots = np.array([r for r, _ in self.basic.ops], dtype=float)
        conj = np.rint(np.einsum("nij,rjk,nkl->nril", pm, rots, pinv)).astype(int)
        code = {tuple(int(x) for row in r for x in row): i
                for i, (r, _) in enumerate(self.basic.ops)}
        w = np.einsum("nij,nj->ni", pinv, pv)
        cache: dict = {}

        def frac(x):
            k = round(float(x) * 144)
            f = cache.get(k)
            if f is None:
                f = cache[k] = Fraction(k, 144)
            return f

        out = []
        for n in range(len(norm)):
            perm = tuple(code[tuple(conj[n, r].ravel())] for r in range(len(rots)))
            p_inv = tuple(tuple(frac(x) for x in row) for row in pinv[n])
            img = []
            for ax in range(3):
                nz = np.nonzero(np.abs(pinv[n][ax]) > 1e-9)[0]
                img.append(int(nz[0]) if len(nz) == 1 else None)
            out.append(_Element(perm, p_inv, tuple(frac(x) for x in w[n]), tuple(img)))
        return tuple(out)

    def canonical(self, axes, qr, deltas) -> _Node:
        """Reduce q_r to its canonical representative (an S_M = H ∈ L*) and
        fix the internal origin (δ = 0 on the first ε = −1 operation)."""
        eps = self.eps(axes)
        can, h = _canon_qr(tuple(qr), axes, self.basic.centrings)
        d = list(deltas)
        if any(h):
            for i, (_, v) in enumerate(self.basic.ops):
                d[i] = (d[i] + h[0] * v[0] + h[1] * v[1] + h[2] * v[2]) % 1
        neg = [i for i, e in enumerate(eps) if e == -1]
        if neg:
            c = d[neg[0]]
            if c:
                for i in neg:
                    d[i] = (d[i] - c) % 1
        return _Node(axes, can, tuple(d))

    def apply_element(self, node: _Node, el: _Element) -> _Node:
        """Conjugate by a basic-group normaliser element (P, p):
        R′ = PRP⁻¹, v′ = Pv + p − R′p, M′ = MP⁻¹, δ′ = δ − M′·p."""
        return self.canonical(*self.element_raw(node, el))

    def element_raw(self, node: _Node, el: _Element) -> tuple:
        """:meth:`apply_element` before :meth:`canonical`: (axes, q_r, δ)."""
        ms = self.ms(node.axes, node.qr)
        w = el.w
        new_d = [None] * len(node.deltas)
        for i, j in enumerate(el.perm):
            m = ms[i]
            new_d[j] = (node.deltas[i] - (m[0] * w[0] + m[1] * w[1] + m[2] * w[2])) % 1
        if len(node.axes) == 3:
            axes_new = node.axes
        else:
            imgs = [el.axis_image[a] for a in node.axes]
            if None in imgs:
                # a shear inside V keeps V; check the span instead
                rows = [_rowmat([int(k == a) for k in range(3)], el.p_inv) for a in node.axes]
                support = sorted({k for r in rows for k in range(3) if r[k] != 0})
                if len(support) != len(node.axes):
                    raise AssertionError("normaliser element moved V off the axes")
                imgs = support
            axes_new = tuple(sorted(imgs))
        qr_new = _rowmat(node.qr, el.p_inv)
        return axes_new, qr_new, new_d

    def apply_minus_q(self, node: _Node) -> _Node:
        """q → −q: M → −M, δ → −δ (S_ε = −1)."""
        return self.canonical(*self.minus_q_raw(node))

    def minus_q_raw(self, node: _Node) -> tuple:
        return (node.axes, tuple(-x for x in node.qr),
                tuple((-x) % 1 for x in node.deltas))

    def apply_shift_q(self, node: _Node, h) -> _Node:
        """q → q + H, H ∈ L*: δ → δ + H·v (S_M = H)."""
        return self.canonical(*self.shift_q_raw(node, h))

    def shift_q_raw(self, node: _Node, h) -> tuple:
        d = tuple((node.deltas[i] + sum(h[k] * v[k] for k in range(3))) % 1
                  for i, (_, v) in enumerate(self.basic.ops))
        return node.axes, tuple(node.qr[k] + h[k] for k in range(3)), d

    def neighbours(self, node: _Node):
        for el in self.elements:
            yield self.apply_element(node, el)
        yield self.apply_minus_q(node)
        for h in self.lstar_basis:
            yield self.apply_shift_q(node, h)

    def nodes(self) -> list[_Node]:
        out = []
        for axes, eps, qr in _families(self.basic):
            for d in _solve_deltas(self.basic, eps, qr):
                out.append(self.canonical(axes, qr, d))
        return sorted(set(out), key=_Node.key)

    def orbit(self, start: _Node) -> set:
        orbit = {start}
        frontier = [start]
        while frontier:
            nxt = []
            for nd in frontier:
                for nb in self.neighbours(nd):
                    if nb not in orbit:
                        orbit.add(nb)
                        nxt.append(nb)
            frontier = nxt
        return orbit

    def orbits(self) -> list[list[_Node]]:
        nodes = self.nodes()
        pool = set(nodes)
        seen: set = set()
        orbits = []
        for start in nodes:
            if start in seen:
                continue
            orb = self.orbit(start)
            stray = orb - pool
            if stray:
                raise AssertionError(
                    f"an equivalence left the solved set ({len(stray)} nodes); "
                    f"the family or closure enumeration is incomplete")
            seen |= orb
            orbits.append(sorted(orb, key=_preferred))
        return orbits

    def group(self, node: _Node) -> SuperspaceGroup:
        eps = self.eps(node.axes)
        ms = self.ms(node.axes, node.qr)
        ops = tuple(SuperspaceOperator(r, v, e, m, d)
                    for (r, v), e, m, d in zip(self.basic.ops, eps, ms, node.deltas))
        cen = tuple(SuperspaceOperator(_E, t, 1, (0, 0, 0), _F0)
                    for t in self.basic.centrings)
        free = tuple(tuple(int(i == ax) for i in range(3)) for ax in node.axes)
        return SuperspaceGroup(ModulationVector(node.qr, free), ops, cen)


def _preferred(node: _Node) -> tuple:
    """Presentation order inside an orbit: q along c, then b, then a; fewest
    rational components; smallest internal translations."""
    pref_axes = tuple(-a for a in node.axes)
    return (len(node.axes), pref_axes, sum(1 for x in node.qr if x), node.qr,
            sum(1 for x in node.deltas if x), node.deltas)


def _lstar_basis(centrings) -> tuple:
    """A basis of the reciprocal lattice L*, as exact rows."""
    if len(centrings) == 1:
        return tuple(tuple(Fraction(int(i == j)) for j in range(3)) for i in range(3))
    prim = _primitive_basis(centrings)
    # the reciprocal basis rows are the rows of the inverse of the column matrix
    inv = _inverse3([list(r) for r in prim])
    return tuple(tuple(inv[i][j] for j in range(3)) for i in range(3))


@functools.lru_cache(maxsize=None)
def _space(number: int) -> _Space:
    return _Space(_basic_from_gemmi(standard_setting(number)), number)


# ---------------------------------------------------------------------------
# public: generation
# ---------------------------------------------------------------------------
def superspace_groups(space_group) -> list[SuperspaceGroup]:
    """Every (3+1)D superspace-group type over a basic space group, one
    representative each, in the generator's standard setting of that group
    (:func:`standard_setting`).

    ``space_group`` is an International Tables number or anything
    :func:`gemmi.find_spacegroup_by_name` reads; only its type is used.  The
    groups carry no number: Stokes 2011's four-part numbering orders them by
    Bravais class and ITC-C index, which is table data this generator does
    not reproduce.
    """
    sp = _space(_sg_number(space_group))
    return [sp.group(orb[0]) for orb in sp.orbits()]


def generate(space_group, q) -> list[SuperspaceGroup]:
    """Every inequivalent (3+1)D superspace group with this basic space group
    *in this setting* and this q, each with q exactly as given.

    ``space_group`` is a gemmi-readable symbol (any ITA setting, e.g.
    ``"P b n m"``) or a :class:`gemmi.SpaceGroup`; ``q`` a
    :class:`ModulationVector` or its text, e.g. ``"(0,0,γ)"``.  The internal
    translations are solved from closure (Stokes 2011 eq. (8)) and the
    solutions identified under equivalence (module docstring).  Of the
    equivalent descriptions in this setting and with this q, the one with the
    nicest symbol is returned (Stokes 2011 § 5.2 step 4); ITC-C sometimes lists
    another, equivalent one, which :func:`equivalent` identifies.  An empty
    list means q is not compatible with the group.
    """
    return [min(members, key=_symbol_rank) for members in family_orbits(space_group, q)]


def family_orbits(space_group, q) -> list[list[SuperspaceGroup]]:
    """The equivalence classes of :func:`generate`, each as *every*
    description it has in this setting with this q (the members differ by
    q → −q, q → q + H or a normaliser element that keeps q's family)."""
    sg = _as_gemmi(space_group)
    basic = _basic_from_gemmi(sg)
    qv = ModulationVector.parse(q)
    if not qv.axis_aligned():
        raise ValueError(
            f"q = {qv.label()} has a free direction off the coordinate axes; "
            f"the generator takes q along axes (choose the setting so it is)")
    axes = tuple(sorted(next(i for i in range(3) if f[i]) for f in qv.free))
    chars = dict(_characters(basic))
    if axes not in chars:
        return []
    eps = chars[axes]
    qr = tuple(Fraction(0) if i in axes else qv.rational[i] for i in range(3))
    for (r, _), e in zip(basic.ops, eps):
        m = tuple(_rowmat(qr, r)[j] - e * qr[j] for j in range(3))
        if not _in_lstar(m, basic.centrings):
            return []
    sp = _Space(basic)
    nodes = sorted({sp.canonical(axes, qr, d) for d in _solve_deltas(basic, eps, qr)},
                   key=_Node.key)
    can_qr, h_can = _canon_qr(qr, axes, basic.centrings)
    out = []
    seen: set = set()
    for start in nodes:
        if start in seen:
            continue
        orbit = sp.orbit(start)
        seen |= orbit
        members = sorted((nd for nd in orbit if nd.axes == axes and nd.qr == can_qr),
                         key=_Node.key)
        out.append([_respell(sp.group(nd), qv, h_can) for nd in members])
    return out


def _respell(g: SuperspaceGroup, qv: ModulationVector, h) -> SuperspaceGroup:
    """``g`` (at the canonical q_r) with q spelt as the caller gave it: the
    q → q − H back from the canonical representative (H ∈ L*), the part of the
    spelling along the free directions being a label only."""
    ops = []
    for op in g.operations:
        hr = _rowmat(h, op.rotation)
        ops.append(SuperspaceOperator(
            op.rotation, op.translation, op.epsilon,
            tuple(int(op.m[j] - hr[j] + op.epsilon * h[j]) for j in range(3)),
            (op.delta - sum(h[k] * op.translation[k] for k in range(3))) % 1))
    return SuperspaceGroup(qv, tuple(ops), g.centerings)


def _symbol_rank(g: SuperspaceGroup) -> tuple:
    """Order among equivalent descriptions in one setting: the nicest symbol
    (Stokes 2011 § 5.2 step 4), then the operators."""
    from .symbols import _symbol_key

    try:
        key = _symbol_key(g)
    except ValueError:
        key = (99,)
    return (key, tuple(o.delta for o in g.operations))


def _sg_number(space_group) -> int:
    if isinstance(space_group, (int, np.integer)):
        return int(space_group)
    return _as_gemmi(space_group).number


def _as_gemmi(space_group) -> gemmi.SpaceGroup:
    if isinstance(space_group, gemmi.SpaceGroup):
        return space_group
    if isinstance(space_group, (int, np.integer)):
        return standard_setting(int(space_group))
    sg = gemmi.find_spacegroup_by_name(str(space_group))
    if sg is None:
        raise ValueError(f"unknown space group {space_group!r}")
    return sg


def count_superspace_groups(numbers=range(1, 231)) -> dict[int, int]:
    """Number of (3+1)D superspace-group types per basic space group."""
    return {n: len(_space(n).orbits()) for n in numbers}


# ---------------------------------------------------------------------------
# public: equivalence and standardisation
# ---------------------------------------------------------------------------
def _identify_basic(basic: _Basic) -> int:
    import spglib

    rots, trans = [], []
    for r, v in basic.ops:
        for t in basic.centrings:
            rots.append(r)
            trans.append([float((v[i] + t[i]) % 1) for i in range(3)])
    rots = np.array(rots, dtype=np.intc)
    g = sum(r.T @ r for r in rots.astype(float))
    lat = np.linalg.cholesky(g)
    t = spglib.get_spacegroup_type_from_symmetry(rots, np.array(trans), lattice=lat,
                                                 symprec=1e-5)
    if t is None:  # pragma: no cover
        raise ValueError("spglib could not identify the basic space group")
    return int(t.number)


def _to_standard(basic: _Basic, target: _Basic, free=()):
    """An affine (P, p) with P G P⁻¹ = G_std, by the normaliser search's
    candidates, keeping q's free directions on the coordinate axes (the
    generator's families are axis-aligned); ``None`` if no small-entry P
    does it."""
    rk = {_key9(r) for r in target.rotations}
    cand = _automorphism_candidates_between(basic.centrings, target.centrings)
    gens = _point_generators(basic.rotations)
    inv = np.linalg.inv(cand)
    ok = np.ones(len(cand), dtype=bool)
    for g in gens:
        conj = np.einsum("nij,jk,nkl->nil", cand, np.asarray(g, float), inv)
        rnd = np.round(conj)
        ok &= np.all(np.abs(conj - rnd) < 1e-9, axis=(1, 2))
        ok &= np.array([_key9(x) in rk for x in rnd], dtype=bool)
    if free:
        f = np.asarray(free, dtype=float)
        rows = np.einsum("fi,nij->nfj", f, inv)                 # q ↦ q P⁻¹
        support = (np.abs(rows) > 1e-9).any(axis=1).sum(axis=1)
        ok &= support == len(free)
    grid = np.array(list(product(range(_GRID), repeat=3)), dtype=float) / _GRID
    cen = np.array([[float(x) for x in t] for t in target.centrings])
    for p_m in cand[ok]:
        p_inv = np.linalg.inv(p_m)
        good = np.ones(len(grid), dtype=bool)
        for g in gens:
            v = np.array([float(x) for x in basic.by_r[_rkey(g)][1]])
            rprime = np.round(p_m @ np.asarray(g, float) @ p_inv)
            tv = np.array([float(x) for x in target.by_r[_key9(rprime)][1]])
            res = ((np.eye(3) - rprime) @ grid.T).T - (tv - p_m @ v)
            inl = np.zeros(len(grid), dtype=bool)
            for t in cen:
                d = res - t
                inl |= np.all(np.abs(d - np.round(d)) < 1e-9, axis=1)
            good &= inl
        if good.any():
            p = grid[np.argmax(good)]
            return (tuple(tuple(Fraction(x).limit_denominator(6) for x in row)
                          for row in p_m),
                    tuple(Fraction(int(round(x * _GRID)), _GRID) for x in p))
    return None


@functools.lru_cache(maxsize=None)
def _automorphism_candidates_between(src: tuple, dst: tuple) -> np.ndarray:
    """Small basis changes mapping the lattice ℤ³+src onto ℤ³+dst."""
    vals = np.array(list(product((-1, 0, 1), repeat=9)), dtype=float).reshape(-1, 3, 3)
    dets = np.round(np.linalg.det(vals))
    unimod = vals[np.abs(dets) == 1]
    mats = [unimod]
    if len(src) > 1 and len(dst) > 1:
        cs = np.array([[float(x) for x in row] for row in _primitive_basis(src)])
        cd = np.array([[float(x) for x in row] for row in _primitive_basis(dst)])
        mats.append(np.einsum("ij,njk,kl->nil", cd, unimod, np.linalg.inv(cs)))
    allm = np.concatenate(mats)
    srcc = np.array([[float(x) for x in t] for t in src])
    dstc = np.array([[float(x) for x in t] for t in dst])

    def in_lat(x, cen):
        ok = np.zeros(x.shape[:2], dtype=bool)
        for t in cen:
            d = x - t
            ok |= np.all(np.abs(d - np.round(d)) < 1e-9, axis=-1)
        return ok

    inv = np.linalg.inv(allm)
    good = in_lat(np.swapaxes(allm, 1, 2), dstc).all(axis=1)
    good &= in_lat(np.einsum("nij,kj->nki", allm, srcc), dstc).all(axis=1)
    good &= in_lat(np.swapaxes(inv, 1, 2), srcc).all(axis=1)
    good &= in_lat(np.einsum("nij,kj->nki", inv, dstc), srcc).all(axis=1)
    return allm[good]


def _node_of(group: SuperspaceGroup):
    """(space, node) for ``group`` brought to its basic group's standard
    setting, centrings without internal parts."""
    sp, transforms = _standard_transforms(group)
    return sp, sp.canonical(*_raw_node(sp, _apply_transforms(group, transforms)))


def _apply_transforms(group: SuperspaceGroup, transforms) -> SuperspaceGroup:
    for t in transforms:
        group = group.transformed(t)
    return group


def _standard_transforms(group: SuperspaceGroup):
    """(space, transforms): the space of ``group``'s basic group and the
    coordinate changes, applied in order, that take ``group`` to its standard
    setting with centrings free of internal parts."""
    if group.is_magnetic:
        raise ValueError("a magnetic group is brought to the standard setting "
                         "through its family or maximal subgroup (.magnetic)")
    basic_in = _basic_from_ops(group.basic_operations())
    number = _identify_basic(basic_in)
    sp = _space(number)
    if basic_in == sp.basic:
        found = (tuple(tuple(Fraction(int(i == j)) for j in range(3)) for i in range(3)),
                 (_F0, _F0, _F0))
    else:
        found = _to_standard(basic_in, sp.basic, group.q.free)
    if found is None:
        raise ValueError(
            f"no small basis change takes this basic group to the standard "
            f"setting of No. {number}; compare it in a standard or nearby "
            f"setting")
    from .operators import SuperspaceTransform
    p_m, p = found
    transforms = [SuperspaceTransform.build(p_m, p)]
    g = group.transformed(transforms[0])
    # remove internal parts of the centrings with an integer S_M
    if any(c.delta for c in g.centerings):
        h = _clear_centrings(g)
        transforms.append(SuperspaceTransform.build(s_m=h))
    return sp, transforms


def _raw_node(sp: _Space, g: SuperspaceGroup) -> tuple:
    """(axes, q_r, δ per standard representative) of a group already in the
    standard setting of ``sp``, before :meth:`_Space.canonical`."""
    # the family is the span of the free directions; it must be a span of axes
    axes = tuple(sorted({i for f in g.q.free for i in range(3) if f[i]}))
    if len(axes) != len(g.q.free):
        raise ValueError(f"q = {g.q.label()} is off the axes in the standard setting")
    qr = tuple(Fraction(0) if i in axes else g.q.rational[i] for i in range(3))
    # δ per standard coset representative
    d = []
    for (r, v) in sp.basic.ops:
        op = g._by_rotation[_rkey(r)]
        # bring op's translation to the representative v: a lattice shift
        diff = tuple(op.translation[i] - v[i] for i in range(3))
        if not _in_lattice(diff, sp.basic.centrings):
            raise AssertionError("standardised group off the standard representatives")
        # a centring shift with δ_c = 0 leaves δ unchanged
        d.append(op.delta)
    return axes, qr, d


def _clear_centrings(g: SuperspaceGroup) -> tuple:
    for h in product(range(0, 3), repeat=3):
        if all((sum(h[i] * c.translation[i] for i in range(3)) + c.delta) % 1 == 0
               for c in g.centerings):
            return tuple(Fraction(x) for x in h)
    raise ValueError("the centrings' internal parts cannot be removed by q → q + H")


def canonical_key(group: SuperspaceGroup) -> tuple:
    """A key equal for two groups iff they are equivalent (Stokes 2011
    eq. (13)): the basic group's type and the smallest node of the orbit.

    A magnetic group's key is :func:`.magnetic.magnetic_canonical_key`'s,
    which compares θ as well (Stokes & Campbell 2022 p. 367)."""
    if group.is_magnetic:
        from .magnetic import magnetic_canonical_key

        return magnetic_canonical_key(group)
    sp, node = _node_of(group)
    orbit = sp.orbit(node)
    best = min(orbit, key=_Node.key)
    return (sp.number, best.key())


def equivalent(a: SuperspaceGroup, b: SuperspaceGroup) -> bool:
    """Whether two (3+1)D superspace groups are equivalent as operator lists:
    related by a change of basic cell and origin, q → ±q + H and an
    internal-origin shift (Stokes 2011 eq. (13); van Smaalen et al. 2013).
    Never a string comparison (Yamamoto et al. 1985 §§ 2-3).  For magnetic
    groups the time-reversal sign of every operation is compared too
    (Stokes & Campbell 2022 p. 367)."""
    return canonical_key(a) == canonical_key(b)


def standardised(group: SuperspaceGroup) -> SuperspaceGroup:
    """The equivalent group in the generator's standard setting, with the
    preferred q and the internal origin fixed (δ = 0 on the first ε = −1
    representative, de Wolff 1981 p. 635)."""
    sp, node = _node_of(group)
    orbit = sp.orbit(node)
    return sp.group(min(orbit, key=_preferred))


_HOLOHEDRY = {
    "triclinic": "P -1", "trigonal": "P 6/m m m", "hexagonal": "P 6/m m m",
}


def _holohedry(sg: gemmi.SpaceGroup) -> gemmi.SpaceGroup:
    """The symmorphic holohedral group of ``sg``'s lattice, same axes."""
    system = sg.crystal_system_str()
    c = sg.hm[0]
    if system == "trigonal" and c == "R":
        name = "R -3 m:H"
    elif system in _HOLOHEDRY:
        name = _HOLOHEDRY[system]
    elif system == "monoclinic":
        name = f"{c} 1 2/m 1"
    elif system == "orthorhombic":
        name = f"{c} m m m"
    elif system == "tetragonal":
        name = f"{c} 4/m m m"
    else:
        name = f"{c} m -3 m"
    hol = gemmi.find_spacegroup_by_name(name)
    if hol is None:  # pragma: no cover - every lattice above is tabulated
        raise AssertionError(f"no holohedry {name!r}")
    return hol


def bravais_classes() -> list[str]:
    """The (3+1)D Bravais classes, one label each (24 for d = 1; de Wolff
    et al. 1981 § 4 and Table 1; Stokes 2011 p. 49).

    Derived, not listed: every q family of every basic group is lifted to the
    symmorphic superspace group of its lattice's holohedry restricted to the
    operations that keep q (de Wolff 1981 p. 629: "pairs (R, ε) leaving the
    lattice invariant"), and those are compared under equivalence.  A label is
    the holohedral group's symbol in the generator's standard setting with
    its canonical q.
    """
    from .symbols import _hm_text

    seen: dict = {}
    for n in range(1, 231):
        sp = _space(n)
        sg = standard_setting(n)
        hol = _basic_from_gemmi(_holohedry(sg))
        for axes, _, qr in _families(sp.basic):
            key = (hol.centrings, hol.rotations, axes, qr)
            if key in seen:
                continue
            seen[key] = _bravais_group(hol, axes, qr)
    labels = {}
    for g in seen.values():
        ck = canonical_key(g)
        if ck not in labels:
            std = standardised(g)
            ssg = gemmi.find_spacegroup_by_ops(
                gemmi.GroupOps([gemmi.Op(x) for x in std.basic_xyz()]))
            labels[ck] = _hm_text(ssg) + std.q.label()
    return sorted(labels.values())


def _bravais_group(hol: _Basic, axes, qr) -> SuperspaceGroup:
    """The symmorphic group of (R, ε) in the lattice holohedry keeping q."""
    ops = []
    for r, _ in hol.ops:
        for e in (1, -1):
            ok = True
            for ax in axes:
                f = tuple(int(i == ax) for i in range(3))
                if _rowmat(f, r) != tuple(e * x for x in f):
                    ok = False
                    break
            if not ok:
                continue
            m = tuple(_rowmat(qr, r)[j] - e * qr[j] for j in range(3))
            if not _in_lstar(m, hol.centrings):
                continue
            ops.append(SuperspaceOperator(r, (_F0, _F0, _F0), e,
                                          tuple(int(x) for x in m), _F0))
            break
    cen = tuple(SuperspaceOperator(_E, t, 1, (0, 0, 0), _F0) for t in hol.centrings)
    free = tuple(tuple(int(i == ax) for i in range(3)) for ax in axes)
    return SuperspaceGroup(ModulationVector(qr, free), tuple(ops), cen)


def _presentation_transform(group: SuperspaceGroup):
    """The ITC-C presentation of a standard-setting group: q along c for the
    orthorhombic groups (−cba for q ∥ a, a−cb for q ∥ b, the settings of
    Yamamoto et al. 1985 Table 2's I2cm, Icmm, Acam and Ac2m, Ac2a) and unique
    axis c for the monoclinic ones (de Wolff 1981 Table 1)."""
    from .operators import SuperspaceTransform

    sg = gemmi.find_spacegroup_by_ops(
        gemmi.GroupOps([gemmi.Op(x) for x in group.basic_xyz()]))
    system = sg.crystal_system_str() if sg is not None else None
    axes = tuple(sorted(next(i for i in range(3) if f[i]) for f in group.q.free))
    if system == "orthorhombic" and axes == (0,):
        t = ((0, 0, 1), (0, 1, 0), (-1, 0, 0))      # (a', b', c') = (−c, b, a)
    elif (system == "orthorhombic" and axes == (1,)) or system == "monoclinic":
        t = ((1, 0, 0), (0, 0, 1), (0, -1, 0))      # (a', b', c') = (a, −c, b)
    else:
        return None
    tinv = _inverse3([[Fraction(x) for x in row] for row in t])
    return SuperspaceTransform.build(tinv)


def catalogue(numbers=range(1, 231)) -> list[SuperspaceGroup]:
    """Every (3+1)D superspace-group type, one representative each, in the
    ITC-C presentation (:func:`_presentation_transform`) with its symbol.

    775 for the 230 basic groups.  Of the equivalent descriptions of a type,
    the one kept has q along the axis the presentation rotates onto c first
    (c, then a, then b), then the smallest rational part, then the nicest
    symbol (Stokes 2011 § 5.2 step 4, after step 3 against the other groups
    over the same basic group and q).
    """
    from .symbols import _symbol_key, symbol, to_tabulated

    out = []
    for n in numbers:
        sp = _space(n)
        for orbit in sp.orbits():
            best = None
            for nd in orbit:
                g = presented(sp.group(nd))
                try:
                    g = to_tabulated(g)
                    sk = _symbol_key(g)
                except ValueError:
                    continue
                pref = {(2,): 0, (0,): 1, (1,): 2}.get(nd.axes, 0)
                qr = g.q.rational
                key = (pref, sum(qr), tuple(-x for x in qr), sk, nd.key())
                if best is None or key < best[0]:
                    best = (key, g)
            if best is None:  # pragma: no cover - every type has a symbol
                raise AssertionError(f"no presentable description in No. {n}")
            g = best[1]
            out.append(SuperspaceGroup(g.q, g.operations, g.centerings, symbol=symbol(g)))
    return out


def presented(group: SuperspaceGroup) -> SuperspaceGroup:
    """``group`` (standard setting) in the ITC-C presentation, with the
    rational part of q brought to its smallest non-negative representative
    by a q → q + H, H ∈ L*."""
    from .operators import SuperspaceTransform

    tr = _presentation_transform(group)
    g = group.transformed(tr) if tr is not None else group
    axes = tuple(sorted(next(i for i in range(3) if f[i]) for f in g.q.free))
    qr = tuple(_F0 if i in axes else g.q.rational[i] for i in range(3))
    cen = tuple(sorted({c.translation for c in g.centerings}))
    _, h = _canon_qr(qr, axes, cen)
    if any(h):
        g = g.transformed(SuperspaceTransform.build(s_m=h))
    # a free direction's sign is a label (fR = εf holds for −f too)
    free = tuple(f if next(x for x in f if x) > 0 else tuple(-x for x in f)
                 for f in g.q.free)
    if free != g.q.free:
        g = SuperspaceGroup(ModulationVector(g.q.rational, free), g.operations,
                            g.centerings)
    return g


__all__ = [
    "N_BRAVAIS_CLASSES_D1",
    "N_SUPERSPACE_GROUPS_D1",
    "bravais_classes",
    "canonical_key",
    "catalogue",
    "count_superspace_groups",
    "equivalent",
    "family_orbits",
    "presented",
    "generate",
    "standard_setting",
    "standardised",
    "superspace_groups",
]
