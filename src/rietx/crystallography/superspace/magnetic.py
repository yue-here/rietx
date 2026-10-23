"""(3+1)D magnetic superspace groups: generated over a superspace group, compared,
named.

A magnetic superspace group (MSSG) is a superspace group whose operations
carry a time-reversal sign θ = ±1 (Perez-Mato, Ribeiro, Petříček & Aroyo,
2012, *J. Phys.: Condens. Matter* **24**, 163201, §§ 2-3).  This module is
the magnetic half of :mod:`.generation`: the same rule — rietx ships no table
(the ISO(3+d)D files may not be redistributed) and derives the groups — with
the construction of Stokes & Campbell (2022), *Acta Cryst.* A**78**, 364, § 3
(pp. 366-367):

* **the two functions of their § 2** (p. 365): the family group F drops θ
  from every operation (:func:`family`), the maximal non-magnetic subgroup X
  drops every primed operation (:func:`maximal_subgroup`);
* **types 1 and 3** (M = D + (F − D)1′, D = F for type 1): take a superspace
  group as F, prime its point generators in all 2ⁿ ways, drop the
  assignments that are not homomorphisms ("none"), deduplicate under
  equivalence;
* **types 2 and 4** (M = D + D{1′|v}): take it as X, add an anti-translation
  {1′|v} for every v with 2v a superspace lattice vector — the sixteen classes
  of ½Λ/Λ, counted in a primitive basis of the (3+1)D lattice Λ (their
  Table 3 note) — drop those that add translations X lacks ("none"),
  deduplicate;
* **equivalence** is van Smaalen, Campbell & Stokes (2013)'s, the one
  :func:`.generation.equivalent` implements, with θ compared on every
  operation (Stokes & Campbell 2022 p. 367).  The orbit search runs on the
  family's (types 1/3) or the maximal subgroup's (types 2/4) node with the
  primes or the anti-translation carried along, so q → −q, q → q + H, a
  change of basic cell and an origin shift move them exactly as they move the
  operators.

**Type 1 is the superspace group's own operator list.**  A type-1 MSSG has no
primed operation, so as a set of operators it *is* its family group; only
its label (``P222.1(0,0,γ)000``) says the structure is magnetic.  The
enumerator returns it as that group with that label, and
:attr:`~.operators.SuperspaceGroup.magnetic_type` returns ``None`` for it.

**Symbols** (Stokes & Campbell 2022 p. 366): the UNI symbol of the basic
magnetic group (Campbell, Stokes, Perez-Mato & Rodríguez-Carvajal, 2022,
*Acta Cryst.* A**78**, 99, § 3) merged with the superspace symbol of the
family (types 1-3) or the maximal subgroup (types 2 and 4), the phase string
gaining **one letter for 1′** in types 2 and 4: ``P22'2'(0,0,γ)000``,
``P222.1'(0,0,γ)000s``, ``P222.1'_I(0,0,γ)00s0``.  A symbol is a label; the
operator list is the primary datum (van Smaalen et al. 2013, conclusions).

Numbers: no writer.  The six-part MSSG number is table data, so a group's
``number`` stays whatever its caller wrote.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import lcm

from .operators import (
    _IDENTITY_R,
    SuperspaceGroup,
    SuperspaceOperator,
    _inverse3,
    _op_key,
    _rkey,
)

_F0 = Fraction(0)
_HALF = Fraction(1, 2)

#: (3+1)D magnetic superspace-group types, Stokes & Campbell (2022), *Acta
#: Cryst.* A**78**, 364, Table 6 (p. 369), d = 1 row: types 1-4 and their sum.
#: The generator here reproduces types 1-3 and finds 4 651 of type 4
#: (WP-1992; ``tests/test_magnetic_superspace.py`` keeps the gap visible).
N_MAGNETIC_SUPERSPACE_TYPES_D1 = (775, 775, 3100, 4653)
N_MAGNETIC_SUPERSPACE_GROUPS_D1 = 9303

#: The anti-translation subscripts of the UNI symbol (Campbell et al. 2022
#: § 3.1), in the order a lattice-equivalent choice is made: lower case first
#: (I222.1'_a, not _A; their Table 3 spelling), the centred vectors after.
_SUBSCRIPTS = (
    ("a", (_HALF, _F0, _F0)), ("b", (_F0, _HALF, _F0)), ("c", (_F0, _F0, _HALF)),
    ("A", (_F0, _HALF, _HALF)), ("B", (_HALF, _F0, _HALF)), ("C", (_HALF, _HALF, _F0)),
    ("I", (_HALF, _HALF, _HALF)),
)


# ---------------------------------------------------------------------------
# F and X
# ---------------------------------------------------------------------------
def family(group: SuperspaceGroup) -> SuperspaceGroup:
    """F: the group with θ dropped from every operation, the operations kept
    (Stokes & Campbell 2022 p. 365, the "non-magnetic family group").  An
    anti-translation becomes a lattice translation, so F of a type-4 group
    has a finer lattice (F of P222.1′_I is I222)."""
    ops = tuple(o.unprimed() for o in group.operations)
    cen = tuple(sorted({c.unprimed() for c in group.centerings}, key=_op_key))
    return SuperspaceGroup(group.q, ops, cen)


def maximal_subgroup(group: SuperspaceGroup) -> SuperspaceGroup:
    """X: the operations without time reversal (Stokes & Campbell 2022
    p. 365, the "non-magnetic maximal subgroup").  For types 2 and 4 it has
    every point operation (each occurs with both signs, so an unprimed
    representative is chosen), for type 3 half of them."""
    anti = next((c for c in group.centerings if c.is_anti_translation), None)
    ops = []
    for o in group.operations:
        if o.theta == 1:
            ops.append(o)
        elif anti is not None:
            ops.append(o * anti)
    cen = tuple(c for c in group.centerings if c.theta == 1)
    return SuperspaceGroup(group.q, tuple(ops), cen)


def construct_type(group: SuperspaceGroup) -> int:
    """1-4 (Stokes & Campbell 2022 p. 366); a group with no primed operation
    is type 1 here, the reading of a caller who declares it magnetic."""
    return group.magnetic_type or 1


# ---------------------------------------------------------------------------
# the candidates over one superspace group
# ---------------------------------------------------------------------------
def _rot_mul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def _theta_closure(rotations, assignment: dict):
    """θ(R) for every R of a point group from θ on generators, or ``None``
    when the assignment is not a homomorphism (Stokes & Campbell 2022 Table 1,
    "none")."""
    rots = set(rotations)
    theta = {_IDENTITY_R: 1}
    frontier = [_IDENTITY_R]
    gens = list(assignment.items())
    while frontier:
        nxt = []
        for r in frontier:
            for g, tg in gens:
                p = _rot_mul(g, r)
                if p not in rots:  # pragma: no cover - generators of this group
                    raise AssertionError("a generator leaves the point group")
                t = tg * theta[r]
                old = theta.get(p)
                if old is None:
                    theta[p] = t
                    nxt.append(p)
                elif old != t:
                    return None
        frontier = nxt
    # every product, not only left multiplication by generators
    for a, ta in theta.items():
        for b, tb in theta.items():
            if theta[_rot_mul(a, b)] != ta * tb:
                return None
    return theta


def symbol_generators(group: SuperspaceGroup) -> tuple:
    """The point generators priming acts on: those of the basic group's
    Hermann-Mauguin symbol where it has one (P222: the three two-folds, "a
    larger-than-minimal set", Stokes & Campbell 2022 p. 367), else a small
    generating set."""
    from .generation import _point_generators
    from .symbols import _positions, _setting_of

    sg = _setting_of(group)
    rots = []
    if sg is not None:
        try:
            rots = [p.rotation for p in _positions(sg) if p.kind != "id"]
        except (AssertionError, ValueError):
            rots = []
    rots = list(dict.fromkeys(rots))
    if not rots:
        rots = _point_generators([o.rotation for o in group.operations])
    return tuple(rots)


def primed_candidates(group: SuperspaceGroup):
    """Types 1 and 3 over ``group`` taken as the family group: one entry per
    way of priming its symbol generators, ``(primes, group or None)``, in the
    order of Stokes & Campbell 2022 Table 1 (``primes`` a tuple of ±1 per
    generator; ``None`` where the primes do not form a group)."""
    if group.is_magnetic:
        raise ValueError("the family group carries no time reversal")
    gens = symbol_generators(group)
    rotations = [o.rotation for o in group.operations]
    out = []
    for signs in product((1, -1), repeat=len(gens)):
        theta = _theta_closure(rotations, dict(zip(gens, signs)))
        if theta is None:
            out.append((signs, None))
            continue
        ops = tuple(o if theta[o.rotation] == 1 else o.prime() for o in group.operations)
        out.append((signs, SuperspaceGroup(group.q, ops, group.centerings)))
    return out


def _hnf(rows, ncols):
    """Row Hermite normal form of an integer lattice, its basis rows."""
    m = [list(r) for r in rows]
    r = 0
    for c in range(ncols):
        while True:
            nz = [i for i in range(r, len(m)) if m[i][c] != 0]
            if len(nz) <= 1:
                break
            nz.sort(key=lambda i: abs(m[i][c]))
            p = nz[0]
            for i in nz[1:]:
                k = m[i][c] // m[p][c]
                m[i] = [a - k * b for a, b in zip(m[i], m[p])]
        nz = [i for i in range(r, len(m)) if m[i][c] != 0]
        if not nz:
            continue
        m[r], m[nz[0]] = m[nz[0]], m[r]
        if m[r][c] < 0:
            m[r] = [-a for a in m[r]]
        r += 1
    return [m[i] for i in range(r)]


def lattice_basis(group: SuperspaceGroup) -> tuple:
    """A basis of the (3+1)D lattice Λ = ℤ⁴ + centrings (anti-translations
    excluded), as four exact rows in the group's coordinates."""
    return _basis_of_centrings([tuple(c.translation) + (c.delta,)
                                for c in group.centerings if c.theta == 1])


def _basis_of_centrings(vecs) -> tuple:
    vecs = [tuple(v) + (_F0,) * (4 - len(v)) for v in vecs]
    den = lcm(*(x.denominator for v in vecs for x in v), 1)
    rows = [[den * int(i == j) for j in range(4)] for i in range(4)]
    rows += [[int(x * den) for x in v] for v in vecs]
    basis = _hnf(rows, 4)
    return tuple(tuple(Fraction(x, den) for x in row) for row in basis)


def half_lattice_vectors(group: SuperspaceGroup) -> tuple:
    """The sixteen classes of ½Λ/Λ: every v with 2v ∈ Λ, as v = ½Σnᵢbᵢ over
    a primitive basis bᵢ of Λ, reduced mod ℤ⁴ (Stokes & Campbell 2022 p. 367
    and Table 3, columns 1 and 2)."""
    return _halves(lattice_basis(group))


def _halves(basis) -> tuple:
    out = []
    for n in product((0, 1), repeat=4):
        v = tuple(sum(_HALF * n[i] * basis[i][j] for i in range(4)) % 1 for j in range(4))
        out.append(v)
    return tuple(out)


def anti_translation_candidates(group: SuperspaceGroup):
    """Types 2 and 4 over ``group`` taken as the maximal subgroup: one entry
    per v of :func:`half_lattice_vectors`, ``(v, group or None)``; ``None``
    where adding {1′|v} adds translations ``group`` lacks (Table 3,
    "none")."""
    out = []
    for v in half_lattice_vectors(group):
        try:
            out.append((v, group.with_anti_translation(v)))
        except ValueError:
            out.append((v, None))
    return out


def magnetic_superspace_groups(group: SuperspaceGroup, *, types=(1, 2, 3, 4)
                               ) -> list[SuperspaceGroup]:
    """Every magnetic superspace group whose family group (types 1 and 3) or
    maximal subgroup (types 2 and 4) is ``group``, one per equivalence class.

    The construction of Stokes & Campbell (2022), *Acta Cryst.* A**78**,
    364, § 3 (module docstring); groups are compared as operator lists under
    equivalence with θ (:func:`magnetic_canonical_key`), never as strings.
    Each comes back in ``group``'s own coordinates with its symbol as a label
    (:func:`magnetic_symbol`); type 1 is ``group``'s own operator list.
    """
    classes: dict = {}

    def keep(g, rank):
        key = magnetic_canonical_key(g) if g.is_magnetic else ("type1",)
        old = classes.get(key)
        if old is None or rank < old[0]:
            classes[key] = (rank, g)

    if 1 in types or 3 in types:
        for signs, g in primed_candidates(group):
            if g is not None and construct_type(g) in types:
                # the representative: fewest primes, the primes on the later
                # generators (Table 1 lists P22'2', not P2'22')
                keep(g, (0, tuple(-s for s in signs)))
    if 2 in types or 4 in types:
        for v, g in anti_translation_candidates(group):
            if g is not None and construct_type(g) in types:
                keep(g, (1, v[3] != 0, _subscript_rank(g), v))
    out = []
    for rank, g in sorted(classes.values(), key=lambda rg: rg[0]):
        try:
            text = magnetic_symbol(g, magnetic=True)
        except ValueError:
            text = None
        out.append(SuperspaceGroup(g.q, g.operations, g.centerings, symbol=text))
    return out


def _subscript_rank(group: SuperspaceGroup) -> int:
    """Order of the UNI subscript a, b, c, A, B, C, I (0 = none, grey 3D)."""
    if any(c.is_anti_translation and not any(c.translation) for c in group.centerings):
        return 0
    try:
        name, _ = _uni_subscript(maximal_subgroup(group),
                                 next(c for c in group.centerings if c.is_anti_translation))
    except ValueError:
        return 99
    return 1 + [n for n, _ in _SUBSCRIPTS].index(name)


# ---------------------------------------------------------------------------
# equivalence
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _MState:
    """A node of the family (types 1/3) or maximal subgroup (types 2/4) and
    what the magnetic group adds: θ per standard representative, or the
    anti-translation (v₁, v₂, v₃, v₄) modulo the lattice."""

    node: object
    data: tuple


def _reduce_v(sp, v) -> tuple:
    """The smallest representative of v modulo ℤ⁴ and the centrings (whose
    internal parts are zero in the standard setting)."""
    best = None
    for t in sp.basic.centrings:
        w = tuple((v[i] + t[i]) % 1 for i in range(3)) + (v[3] % 1,)
        if best is None or w < best:
            best = w
    return best


@functools.lru_cache(maxsize=4096)
def _p_matrix(p_inv) -> tuple:
    inv = _inverse3([list(r) for r in p_inv])
    return tuple(tuple(inv[i][j] for j in range(3)) for i in range(3))


def _canonical_state(sp, raw, data, kind) -> _MState:
    """:meth:`_Space.canonical` on the raw node, the anti-translation moved
    by the same q → q + H (δ₄ += H·v)."""
    from .generation import _canon_qr

    axes, qr, d = raw
    node = sp.canonical(axes, qr, d)
    if kind == "v":
        _, h = _canon_qr(tuple(qr), axes, sp.basic.centrings)
        v = data
        if any(h):
            v = v[:3] + (v[3] + sum(h[k] * v[k] for k in range(3)),)
        data = _reduce_v(sp, v)
    return _MState(node, data)


def _neighbours(sp, st: _MState, kind):
    node, data = st.node, st.data
    for el in sp.elements:
        raw = sp.element_raw(node, el)
        if kind == "t":
            new = [None] * len(data)
            for i, j in enumerate(el.perm):
                new[j] = data[i]
            nd = tuple(new)
        else:
            p = _p_matrix(el.p_inv)
            ext = tuple(sum(p[i][k] * data[k] for k in range(3)) for i in range(3))
            nd = ext + (data[3],)
        yield _canonical_state(sp, raw, nd, kind)
    raw = sp.minus_q_raw(node)
    nd = data if kind == "t" else data[:3] + (-data[3],)
    yield _canonical_state(sp, raw, nd, kind)
    for h in sp.lstar_basis:
        raw = sp.shift_q_raw(node, h)
        nd = data if kind == "t" else \
            data[:3] + (data[3] + sum(h[k] * data[k] for k in range(3)),)
        yield _canonical_state(sp, raw, nd, kind)


def _orbit(sp, start: _MState, kind) -> set:
    orbit = {start}
    frontier = [start]
    while frontier:
        nxt = []
        for st in frontier:
            for nb in _neighbours(sp, st, kind):
                if nb not in orbit:
                    orbit.add(nb)
                    nxt.append(nb)
        frontier = nxt
    return orbit


def _state_key(st: _MState) -> tuple:
    return (st.node.key(), st.data)


def _start_state(group: SuperspaceGroup):
    """(space, kind, state) for a magnetic group, in its standard setting."""
    from .generation import _apply_transforms, _raw_node, _standard_transforms

    t = group.magnetic_type
    if t in (2, 4):
        base, kind = maximal_subgroup(group), "v"
    else:
        base, kind = family(group), "t"
    sp, transforms = _standard_transforms(base)
    std = _apply_transforms(base, transforms)
    raw = _raw_node(sp, std)
    mstd = _apply_transforms(group, transforms)
    if kind == "t":
        by_r = {_rkey(o.rotation): o.theta for o in mstd.operations}
        data = tuple(by_r[_rkey(r)] for r, _ in sp.basic.ops)
    else:
        anti = next(c for c in mstd.centerings if c.is_anti_translation)
        data = tuple(anti.translation) + (anti.delta,)
    return sp, kind, _canonical_state(sp, raw, data, kind)


def magnetic_canonical_key(group: SuperspaceGroup) -> tuple:
    """A key equal for two magnetic groups iff they are equivalent: the
    equivalence of :func:`.generation.canonical_key` with θ on every
    operation compared (Stokes & Campbell 2022 p. 367).  The smallest state of
    the orbit of (the family's or maximal subgroup's node, the primes or the
    anti-translation) under q → −q, q → q + H and the basic group's
    normaliser."""
    if not group.is_magnetic:
        raise ValueError("not a magnetic group; use generation.canonical_key")
    sp, kind, start = _start_state(group)
    best = min(_orbit(sp, start, kind), key=_state_key)
    return ("magnetic", kind, sp.number, _state_key(best))


# ---------------------------------------------------------------------------
# the count over every superspace group (opt-in; Stokes & Campbell 2022 Table 6)
# ---------------------------------------------------------------------------
def _space_counts(number: int) -> dict[int, int]:
    """Types 1-4 over every (3+1)D superspace-group type with basic group
    ``number``, from the generator's nodes."""
    from .generation import _point_generators, _space

    sp = _space(number)
    counts = {1: 0, 2: 0, 3: 0, 4: 0}
    rots = sp.basic.rotations
    gens = _point_generators(rots)
    index = {_rkey(r): i for i, r in enumerate(rots)}
    cen = sp.basic.centrings
    halves = _halves(_basis_of_centrings(cen))
    for orb in sp.orbits():
        node = orb[0]
        # types 1 and 3: characters θ of the point group
        seen: set = set()
        for signs in product((1, -1), repeat=len(gens)):
            theta = _theta_closure(rots, dict(zip(gens, signs)))
            if theta is None:
                continue
            data = tuple(theta[r] for r in rots)
            st = _MState(node, data)
            if st in seen:
                continue
            seen |= _orbit(sp, st, "t")
            counts[1 if all(x == 1 for x in data) else 3] += 1
        # types 2 and 4: anti-translations
        ms = sp.ms(node.axes, node.qr)
        eps = sp.eps(node.axes)
        seen = set()
        for v in halves:
            ok = True
            for (r, _), m, e in zip(sp.basic.ops, ms, eps):
                if index[_rkey(r)] == 0:
                    continue
                rv = tuple(sum(r[i][k] * v[k] for k in range(3)) for i in range(3))
                diff = tuple(rv[i] - v[i] for i in range(3)) + (
                    sum(m[k] * v[k] for k in range(3)) + (e - 1) * v[3],)
                if not any(all((diff[i] - t[i]) % 1 == 0 for i in range(3))
                           and diff[3] % 1 == 0 for t in cen):
                    ok = False
                    break
            if not ok:
                continue
            st = _canonical_state(sp, (node.axes, node.qr, node.deltas), v, "v")
            if st in seen:
                continue
            seen |= _orbit(sp, st, "v")
            counts[2 if not any(st.data) else 4] += 1
    return counts


def count_magnetic_superspace_groups(numbers=range(1, 231)) -> dict[int, dict[int, int]]:
    """Types 1-4 per basic space group; summed over the 230 they are Stokes &
    Campbell (2022) Table 6's d = 1 row (p. 369)."""
    return {n: _space_counts(n) for n in numbers}


# ---------------------------------------------------------------------------
# symbols
# ---------------------------------------------------------------------------
def _uni_subscript(group: SuperspaceGroup, anti: SuperspaceOperator) -> tuple[str, tuple]:
    """(subscript, external part) of an anti-translation for the UNI symbol
    (Campbell et al. 2022 § 3.1): the first of a, b, c, A, B, C, I equal to its
    external part modulo the maximal subgroup's lattice; I for an F lattice
    (their Case 2)."""
    cen = [c.translation for c in group.centerings if c.theta == 1]
    v = anti.translation
    hits = [(name, vec) for name, vec in _SUBSCRIPTS
            if any(all((v[i] - t[i] - vec[i]) % 1 == 0 for i in range(3)) for t in cen)]
    if not hits:
        raise ValueError(f"the anti-translation {anti.xyz()!r} has no UNI subscript "
                         f"(its external part is not half a conventional vector)")
    if len(cen) == 4 and any(n == "I" for n, _ in hits):
        return next(h for h in hits if h[0] == "I")
    return hits[0]


def _primed_hm(sg, theta_of) -> str:
    """The Hermann-Mauguin text of :func:`.symbols._hm_text` with a prime on
    every piece whose generator is primed."""
    from .symbols import _positions, _tokens

    positions = iter(_positions(sg))
    out = sg.hm.split()[0]
    system = sg.crystal_system_str()
    for tok in _tokens(sg):
        pieces = []
        for piece in tok.split("/"):
            text = piece[0] + "_" + piece[1:] if piece[0] in "0123456789" and len(piece) > 1 \
                else piece
            skip = piece == "1" and system in ("monoclinic", "triclinic")
            if not skip:
                pos = next(positions)
                if pos.kind != "id" and theta_of.get(pos.rotation, 1) == -1:
                    text += "'"
            pieces.append(text)
        out += "/".join(pieces)
    return out


def magnetic_symbol(group: SuperspaceGroup, *, magnetic: bool | None = None) -> str:
    """The MSSG symbol of Stokes & Campbell (2022) p. 366 (module docstring).

    ``magnetic=True`` on a group with no primed operation prints it as type
    1 (``P222.1(0,0,γ)000``); a group with primes is magnetic whatever
    ``magnetic`` says.
    """
    from .symbols import _letter, _setting_of
    from .symbols import symbol as ssg_symbol

    t = group.magnetic_type
    if t is None:
        if not magnetic:
            raise ValueError("not a magnetic group; pass magnetic=True for type 1")
        text = ssg_symbol(group)
        hm, rest = text.split("(", 1)
        return f"{hm}.1({rest}"
    if t == 3:
        f = family(group)
        text = ssg_symbol(f)
        _, rest = text.split("(", 1)
        sg = _setting_of(f)
        theta_of = {o.rotation: o.theta for o in group.operations}
        return f"{_primed_hm(sg, theta_of)}({rest}"
    x = maximal_subgroup(group)
    text = ssg_symbol(x)
    hm, rest = text.split("(", 1)
    anti = next(c for c in group.centerings if c.is_anti_translation)
    qr = x.q.rational
    free = {next(i for i in range(3) if f[i]) for f in x.q.free} if x.q.axis_aligned() else set()
    qr_eff = tuple(_F0 if i in free else qr[i] for i in range(3))
    internal = sorted((c for c in group.centerings
                       if c.is_anti_translation and not any(c.translation)), key=_op_key)
    if internal:
        # the BMSG is grey (v ≡ 0 in 3D, Stokes & Campbell 2022 p. 367): no
        # subscript, the 1′ letter is the internal component alone
        head = f"{hm}.1'"
        tau = internal[0].delta
    else:
        name, vext = _uni_subscript(x, anti)
        head = f"{hm}.1'_{name}"
        # the representative whose external part is vext: shift by the
        # centring that takes the anti-translation there
        for c in x.centerings:
            w = tuple((anti.translation[i] + c.translation[i]) % 1 for i in range(3))
            if w == tuple(x_ % 1 for x_ in vext):
                d4 = anti.delta + c.delta
                break
        else:  # pragma: no cover - _uni_subscript found one
            raise AssertionError("no representative of the anti-translation")
        tau = (d4 - sum(qr_eff[i] * vext[i] for i in range(3))) % 1
    return f"{head}({rest}{_letter(tau)}"


#: A grey or type-4 head: ``….1'`` or ``….1'_a``; without the period
#: (``Pnma1'``) only after a letter, since ``P2221'`` would also read as a
#: primed 2₁ of ``P222_1``.
_MAG_HEAD = re.compile(
    r"^(?P<hm>.*?)(?P<grey>(?:\.1|(?<=[A-Za-z])1)['′](?:_(?P<sub>[abcABCI]))?)$")


def _split_primes(hm: str) -> tuple[str, list[int]]:
    """(the H-M text without primes, the character offsets after which a
    prime stood, in the unprimed compact text)."""
    out, marks = "", []
    for ch in hm:
        if ch in "'′":
            marks.append(len(out.replace("_", "").replace(" ", "")))
        else:
            out += ch
    return out, marks


def _piece_spans(sg, compact: str):
    """(position index or None, end offset) per piece of the setting's H-M
    symbol, aligned on ``compact`` (the caller's text without primes,
    underscores and spaces), the monoclinic "1"s dropped when the caller
    dropped them."""
    from .symbols import _tokens

    system = sg.crystal_system_str()
    letter = sg.hm.split()[0]
    for drop_ones in (False, True):
        spans, text, pos_i = [], letter, 0
        for tok in _tokens(sg):
            for k, piece in enumerate(tok.split("/")):
                one = piece == "1" and system in ("monoclinic", "triclinic")
                if one and drop_ones:
                    continue
                if k:
                    text += "/"
                text += piece
                if one:
                    spans.append((None, len(text)))
                else:
                    spans.append((pos_i, len(text)))
                    pos_i += 1
        if text.replace("-", "") == compact.replace("-", "") or text == compact:
            return spans
    return None


def parse_magnetic_symbol(text: str) -> SuperspaceGroup:
    """The magnetic superspace group a symbol names (:func:`_parse_magnetic`).

    A trailing ``1'`` after a digit with no period (``P11'(αβγ)0s``, Gallego
    et al. 2016 Fig. 6) reads either as the grey generator or as a primed
    last generator; both readings are built, and the string is accepted only
    when exactly one of them is a group, refused as ambiguous otherwise.
    """
    m = re.match(r"^\s*(?P<hm>[^(]+?)\s*\(", str(text))
    hm = m.group("hm") if m else ""
    if m and re.search(r"\d1['′]$", hm) and not hm.endswith((".1'", ".1′")):
        readings = []
        for candidate in (text.replace(hm, hm[:-2] + ".1'", 1), text):
            try:
                readings.append(_parse_magnetic(candidate))
            except (ValueError, NotImplementedError):
                continue
        if len(readings) == 1:
            return readings[0]
        if len(readings) > 1:
            raise ValueError(f"{text!r} reads both as a grey group and as a primed "
                             f"generator; write the grey one as '.1'' (Campbell et "
                             f"al. 2022 § 3.4)")
    return _parse_magnetic(text)


def _parse_magnetic(text: str) -> SuperspaceGroup:
    """The magnetic superspace group a symbol names: ``P22'2'(0,0,γ)000``
    (type 3), ``P222.1(0,0,γ)000`` (type 1), ``P222.1'(0,0,γ)000s`` (type 2
    or 4 with {1′|000½}), ``P222.1'_I(0,0,γ)00s0`` (type 4).

    Built, not matched: the superspace part is read by
    :func:`.symbols.parse_symbol`, then the primes, or the anti-translation
    from the UNI subscript and the **extra phase letter for 1′**, are put on
    its operators (Stokes & Campbell 2022 p. 366; Campbell et al. 2022 § 3).
    A type-2/4 symbol has one letter per generator plus one: "000s" is
    {1′|000½} over P222(0,0,γ)000, never P222(0,0,γ)000 + {1′|0000}, and a
    string with one letter too few is refused rather than read the other way.
    ``.1'`` without a period (``Pnma1'(00γ)0sss``, the ITC-C-style grey
    spelling of Petříček et al. 2010 § 4.2) reads the same.
    """
    from .symbols import _SYMBOL, _letters, _normal_hm, _positions, _settings_named, parse_symbol

    m = _SYMBOL.match(str(text))
    if m is None:
        raise ValueError(f"{text!r} has no modulation vector in parentheses; a superspace "
                         f"symbol is ambiguous without its q (Yamamoto et al. 1985)")
    hm, q, tail = m.group("hm").strip(), m.group("q"), m.group("tail")
    head = _MAG_HEAD.match(hm)
    if head is not None and ("'" in head.group("grey") or "′" in head.group("grey")):
        base_hm = head.group("hm")
        if "'" in base_hm or "′" in base_hm:
            raise ValueError(f"{text!r}: a type-4 symbol primes only 1' (Campbell et "
                             f"al. 2022 § 3.2), not its spatial generators")
        letters = _letters(tail)
        if not letters:
            raise ValueError(f"{text!r} has no phase letters")
        settings = _settings_named(base_hm)
        n_pos = len(_positions(settings[0])) if settings else None
        if n_pos == 0 and len(letters) == 2 and letters[0] == 0:
            # P1's identity spelt with a letter (Gallego et al. 2016 Fig. 6,
            # "P11'(αβγ)0s"); Stokes 2011's P1 symbol has none
            letters = letters[1:]
        if n_pos is not None and len(letters) != n_pos + 1:
            raise ValueError(
                f"{text!r} has {len(letters)} phase letters; a type-2/4 symbol over "
                f"{base_hm} has one per generator plus one for 1' ({n_pos + 1}), "
                f"Stokes & Campbell 2022 p. 366")
        x = parse_symbol(f"{base_hm}({q})" + _letters_text(tail, n_pos))
        tau = letters[-1]
        sub = head.group("sub")
        vext = dict(_SUBSCRIPTS)[sub] if sub else (_F0, _F0, _F0)
        qr = x.q.rational
        free = {next(i for i in range(3) if f[i]) for f in x.q.free} if x.q.axis_aligned() \
            else set()
        qr_eff = tuple(_F0 if i in free else qr[i] for i in range(3))
        v4 = (tau + sum(qr_eff[i] * vext[i] for i in range(3))) % 1
        g = x.with_anti_translation(vext + (v4,))
        return SuperspaceGroup(g.q, g.operations, g.centerings, symbol=magnetic_symbol(g))
    if hm.endswith(".1"):
        g = parse_symbol(f"{hm[:-2]}({q}){tail}")
        return SuperspaceGroup(g.q, g.operations, g.centerings,
                               symbol=magnetic_symbol(g, magnetic=True))
    # type 3: primes on the spatial generators
    base_hm, marks = _split_primes(hm)
    if not marks:
        raise ValueError(f"{text!r} is not a magnetic symbol")
    f = parse_symbol(f"{base_hm}({q}){tail}")
    from .symbols import _setting_of

    sg = _setting_of(f)
    spans = _piece_spans(sg, _normal_hm(base_hm))
    if spans is None:
        raise ValueError(f"cannot align the primes of {text!r} with {sg.xhm()}")
    positions = _positions(sg)
    assign = {}
    for pos_i, end in spans:
        if pos_i is None:
            continue
        primed = end in marks
        rot = positions[pos_i].rotation
        if positions[pos_i].kind == "id":
            if primed:
                raise ValueError(f"{text!r} primes a '1'")
            continue
        sign = -1 if primed else 1
        if assign.get(rot, sign) != sign:
            raise ValueError(f"{text!r} gives one generator both signs")
        assign[rot] = sign
    stray = set(marks) - {end for _, end in spans}
    if stray:
        raise ValueError(f"cannot place every prime of {text!r} on a generator")
    theta = _theta_closure([o.rotation for o in f.operations], assign)
    if theta is None:
        raise ValueError(f"the primes of {text!r} do not form a group (Stokes & "
                         f"Campbell 2022 Table 1, 'none')")
    ops = tuple(o if theta[o.rotation] == 1 else o.prime() for o in f.operations)
    g = SuperspaceGroup(f.q, ops, f.centerings)
    return SuperspaceGroup(g.q, g.operations, g.centerings, symbol=magnetic_symbol(g))


def _letters_text(tail: str, n: int | None) -> str:
    """The first ``n`` phase letters of ``tail``, as text (the superspace
    part of a type-2/4 symbol)."""
    from .symbols import _LETTER_TOKEN

    t = tail.replace(" ", "")
    pos, out = 0, ""
    count = 0
    while pos < len(t) and (n is None or count < n):
        m = _LETTER_TOKEN.match(t, pos)
        if m is None:
            break
        out += m.group(0)
        pos = m.end()
        count += 1
    return out


def anti_translation_of(group: SuperspaceGroup) -> tuple | None:
    """(v₁, v₂, v₃, v₄) of one anti-translation of a type-2/4 group (the
    smallest), or ``None``."""
    anti = sorted((c for c in group.centerings if c.is_anti_translation), key=_op_key)
    if not anti:
        return None
    a = anti[0]
    return tuple(a.translation) + (a.delta,)


def theta_of(group: SuperspaceGroup) -> dict:
    """θ per point operation R of a type-1/3 group."""
    if any(c.is_anti_translation for c in group.centerings):
        raise ValueError("every point operation of a type-2/4 group occurs with both signs")
    return {o.rotation: o.theta for o in group.operations}


__all__ = [
    "anti_translation_candidates",
    "anti_translation_of",
    "construct_type",
    "count_magnetic_superspace_groups",
    "family",
    "half_lattice_vectors",
    "lattice_basis",
    "magnetic_canonical_key",
    "magnetic_superspace_groups",
    "magnetic_symbol",
    "maximal_subgroup",
    "parse_magnetic_symbol",
    "primed_candidates",
    "symbol_generators",
    "theta_of",
]
