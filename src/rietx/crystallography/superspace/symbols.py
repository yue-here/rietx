"""(3+1)D superspace-group symbols: print and parse, under Stokes 2011's rules.

A one-line symbol is the basic group's Hermann-Mauguin symbol, the modulation
vector, and one letter per generator of the H-M symbol giving that generator's
**internal intrinsic translation** (IIT): ``Pbnm(00γ)s00``.  The letters are
0, s, t, q, h for 0, ½, ⅓, ¼, ⅙, with a minus for a negative value (de Wolff,
Janssen & Janner, 1981, *Acta Cryst.* A**37**, 625, eqs (4.3)-(4.4)); an
ε = −1 generator always prints 0, its internal translation being fixed by the
internal origin (de Wolff 1981 p. 635).

**A symbol is a label, not a key.**  It is unique only together with q and the
reflection conditions (Yamamoto, Janssen, Janner & de Wolff, 1985, *Acta
Cryst.* A**41**, 528, §§ 2-3): q → q + H changes the letters, and a generator
combined with a lattice translation can change its letter whenever q has a
rational part.  So parsing here goes the safe way round: the symbol's basic
group and q are taken, every group with them is *generated*
(:func:`~rietx.crystallography.superspace.generation.generate`), and the one
whose printed symbol — or, failing that, whose set of admissible symbols —
contains the string is returned.  A string matching no group, or more than
one, is refused by name.

The rules applied when printing (Stokes, Campbell & van Smaalen, 2011,
*Acta Cryst.* A**67**, 45, § 5):

* **Generators** in the orientation of their Table 2 (bars restored by group
  membership; the table's OCR lost them) and, for the unambiguous point
  groups, the obvious one per symbol position.
* **External intrinsic translations strictly match the BSG symbol**
  (§ 5.1(3), step 2): of every lattice translation added to a generator, only
  those whose external intrinsic translation (eq. (14)) is the letter's are
  admitted.
* **The IIT is read in the supercentred setting**, where for d = 1 it is
  τ = δ − q_r·v of the admitted generator (de Wolff 1981 eq. (3.8)) — the
  supercell change of basis rescales the external coordinates only.
* **The nicest symbol** (step 4): fewest negative letters, most zeros,
  smallest largest denominator, then smaller denominators and numerators
  first.

Step 3 of § 5.2 (lifting a residual degeneracy by restricting a later group's
lattice translations) is not implemented; the catalogue test asserts that the
775 printed symbols are distinct without it.  ITC-C's one-line symbols differ
from these rules for eleven groups (Stokes 2011 Table 9, p. 54); those are
data here (:data:`ITC_C_EXCEPTIONS`), and the printer returns ITC-C's
spelling, as Stokes 2011 § 5.2.5 recommends.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from fractions import Fraction
from itertools import product

import gemmi

from .operators import ModulationVector, SuperspaceGroup

#: Stokes 2011 Table 9 (p. 54): the eleven (3+1)D groups whose ITC-C symbol
#: differs from the one Stokes' conventions give.  Keys are the conventions'
#: spelling as this module prints it, values ITC-C's; the group number is the
#: SSG(3+d)D one.  For eight the conventions found a "nicer" symbol, for three
#: ITC-C's needs an external translation that does not strictly match the
#: basic-group symbol (§ 5.2.5).
ITC_C_EXCEPTIONS: dict[str, tuple[str, str]] = {
    "Cmm2(1,0,γ)s00": ("Cmm2(1,0,γ)s0s", "35.1.14.5"),
    "Cmc2_1(1,0,γ)s00": ("Cmc2_1(1,0,γ)s0s", "36.1.14.4"),
    "Ccc2(1,0,γ)s00": ("Ccc2(1,0,γ)s0s", "37.1.14.4"),
    "Fmm2(1,0,γ)s00": ("Fmm2(1,0,γ)s0s", "42.1.18.5"),
    "P4mm(1/2,1/2,γ)00s": ("P4mm(1/2,1/2,γ)0ss", "99.1.20.6"),
    "P4_2cm(1/2,1/2,γ)00s": ("P4_2cm(1/2,1/2,γ)0ss", "101.1.20.4"),
    "P4nc(1/2,1/2,γ)qqs": ("P4nc(1/2,1/2,γ)qq0", "104.1.20.3"),
    "P4_2bc(1/2,1/2,γ)qqs": ("P4_2bc(1/2,1/2,γ)qq0", "106.1.20.3"),
    "P4/mmm(1/2,1/2,γ)000s": ("P4/mmm(1/2,1/2,γ)00ss", "123.1.20.6"),
    "P4/nnc(1/2,1/2,γ)q0qs": ("P4/nnc(1/2,1/2,γ)q0q0", "126.1.20.3"),
    "P4_2/mcm(1/2,1/2,γ)000s": ("P4_2/mcm(1/2,1/2,γ)00ss", "132.1.20.4"),
}

_LETTERS = {Fraction(0): "0", Fraction(1, 2): "s", Fraction(1, 3): "t",
            Fraction(1, 4): "q", Fraction(1, 6): "h"}
_VALUES = {v: k for k, v in _LETTERS.items()}

# Stokes 2011 Table 2 orientations, keyed by (system, position, kind); the
# third tetragonal and hexagonal position takes the [110] two-fold and the
# mirror normal to [1-10] (Table 2's 422 / 4mm rows).
_TETRA = {
    (0, "rot", 4): "-y,x,z", (0, "rot", -4): "y,-x,-z", (0, "mir", 0): "x,y,-z",
    (1, "rot", 2): "x,-y,-z", (1, "mir", 0): "-x,y,z",
    (2, "rot", 2): "y,x,-z", (2, "mir", 0): "y,x,z",
}
_HEXA = {
    (0, "rot", 3): "-y,x-y,z", (0, "rot", -3): "y,-x+y,-z",
    (0, "rot", 6): "x-y,x,z", (0, "rot", -6): "-x+y,-x,-z", (0, "mir", 0): "x,y,-z",
    (1, "rot", 2): "-x,-x+y,-z", (1, "mir", 0): "x,x-y,z",
    (2, "rot", 2): ("y,x,-z", "-y,-x,-z"), (2, "mir", 0): "y,x,z",
}


def _op_matrix(xyz: str):
    op = gemmi.Op(xyz)
    return tuple(tuple(x // gemmi.Op.DEN for x in row) for row in op.rot)


@dataclass(frozen=True)
class _GroupView:
    """The three fields :func:`_candidates` reads, hashable for its cache."""

    q: ModulationVector
    operations: tuple
    centerings: tuple


@dataclass(frozen=True)
class _Position:
    """One letter of the symbol: its generator and the translation it names."""

    rotation: tuple          # the generator's R
    kind: str                # "rot", "mir", "id"
    token: str               # the H-M piece, e.g. "4_2", "n", "2_1", "1"
    axis: tuple              # a lattice vector along the axis / normal


def _tokens(sg: gemmi.SpaceGroup) -> list[str]:
    hm = sg.hm.split(":")[0].strip()
    parts = hm.split()
    return parts[1:]


def _system(sg: gemmi.SpaceGroup) -> str:
    return sg.crystal_system_str()


def _positions(sg: gemmi.SpaceGroup) -> list[_Position]:
    """The symbol's generators in order, from the setting's H-M symbol."""
    system = _system(sg)
    toks = _tokens(sg)
    rots = {tuple(tuple(x // gemmi.Op.DEN for x in row) for row in op.rot)
            for op in sg.operations().sym_ops}
    out: list[_Position] = []

    def add(r, kind, tok, axis):
        if r not in rots:
            raise AssertionError(f"generator {r} for {tok!r} not in {sg.xhm()}")
        out.append(_Position(r, kind, tok, axis))

    def split(tok):
        if "/" in tok:
            a, b = tok.split("/")
            return [("rot", a), ("mir", b)]
        if tok[0] in "-0123456789":
            return [("rot", tok)]
        return [("mir", tok)]

    def rot_order(tok):
        neg = tok.startswith("-")
        n = int(tok.lstrip("-")[0])
        return -n if neg else n

    if system == "triclinic":
        if toks == ["-1"]:
            add(((-1, 0, 0), (0, -1, 0), (0, 0, -1)), "rot", "-1", (0, 0, 0))
        return out
    if system in ("monoclinic", "orthorhombic"):
        for i, tok in enumerate(toks):
            if system == "monoclinic" and tok == "1":
                continue
            e = [0, 0, 0]
            e[i] = 1
            for kind, piece in split(tok):
                if kind == "rot":
                    r = tuple(tuple((1 if a == i else -1) if a == b else 0
                                    for b in range(3)) for a in range(3))
                else:
                    r = tuple(tuple((-1 if a == i else 1) if a == b else 0
                                    for b in range(3)) for a in range(3))
                add(r, kind, piece, tuple(e))
        return out
    table = _TETRA if system == "tetragonal" else _HEXA
    axes = ((0, 0, 1), (1, 0, 0), (1, 1, 0) if system == "tetragonal" else (0, 1, 0))
    for i, tok in enumerate(toks):
        if tok == "1":
            add(((1, 0, 0), (0, 1, 0), (0, 0, 1)), "id", "1", (0, 0, 0))
            continue
        for kind, piece in split(tok):
            key = (i, kind, rot_order(piece) if kind == "rot" else 0)
            if kind == "rot" and abs(key[2]) == 2 and i == 0:
                raise AssertionError(f"unexpected two-fold first in {sg.xhm()}")
            xyz = table.get(key)
            if xyz is None:
                raise ValueError(f"no generator rule for {piece!r} at position "
                                 f"{i + 1} of {sg.xhm()}")
            if isinstance(xyz, tuple):
                xyz = next(x for x in xyz if _op_matrix(x) in rots)
            r = _op_matrix(xyz)
            add(r, kind, piece, _axis(r) if kind == "rot" else axes[i])
    return out


def _axis(r) -> tuple:
    """The primitive lattice vector along a proper rotation's axis (for a
    rotoinversion, along −R's), conventional coordinates."""
    det = (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
           - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
           + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))
    rr = r if det > 0 else tuple(tuple(-x for x in row) for row in r)
    # the positive sense: 4⁺ = (−y, x, z) is a left-handed turn about +c, and a
    # screw 4₁ advances along +c (ITA conventions)
    for u in sorted(product((-1, 0, 1, 2), repeat=3),
                    key=lambda u: (sum(map(abs, u)), tuple(-x for x in u))):
        if any(u) and _matvec(rr, u) == u:
            return u
    raise AssertionError(f"no axis for {r}")


def _matvec(m, v):
    return tuple(sum(m[i][k] * v[k] for k in range(3)) for i in range(3))


def _matmul(a, b):
    return tuple(tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3))
                 for i in range(3))


def _eit(r, v) -> tuple:
    """External intrinsic translation (1/n)Σ_{m=1..n} R^m v mod 1 (Stokes
    2011 eq. (14))."""
    return tuple(x % 1 for x in _eit_exact(r, v))


def _eit_exact(r, v) -> tuple:
    """The same, not reduced: step 3 compares these exactly."""
    proj = _projector(r)
    return tuple(proj[i][0] * v[0] + proj[i][1] * v[1] + proj[i][2] * v[2]
                 for i in range(3))


@functools.lru_cache(maxsize=None)
def _projector(r) -> tuple:
    """(1/n)Σ_{m=1..n} R^m, the map from a translation to its intrinsic part."""
    e = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
    acc = [[0] * 3 for _ in range(3)]
    p, n = r, 0
    while True:
        n += 1
        for i in range(3):
            for j in range(3):
                acc[i][j] += p[i][j]
        if p == e:
            break
        p = _matmul(p, r)
    return tuple(tuple(Fraction(acc[i][j], n) for j in range(3)) for i in range(3))


def _expected(pos: _Position, eit: tuple, centrings) -> bool:
    """Whether an external intrinsic translation strictly matches the letter."""
    tok = pos.token
    zero = all(x == 0 for x in eit)
    if pos.kind == "id":
        return zero
    if pos.kind == "rot":
        body = tok.lstrip("-")
        if tok.startswith("-") or len(body) == 1:
            return zero
        n, k = int(body[0]), int(body[1:])
        want = tuple((Fraction(k, n) * a) % 1 for a in pos.axis)
        return eit == want
    # mirrors and glides
    if tok == "m":
        return zero
    halves = {"a": (Fraction(1, 2), 0, 0), "b": (0, Fraction(1, 2), 0),
              "c": (0, 0, Fraction(1, 2))}
    if tok in halves:
        return eit == tuple(Fraction(x) for x in halves[tok])
    if tok == "n":
        nz = sum(1 for x in eit if x != 0)
        return all(x in (0, Fraction(1, 2)) for x in eit) and nz >= 2
    if tok == "d":
        return all((4 * x).denominator == 1 for x in eit) and any(
            x in (Fraction(1, 4), Fraction(3, 4)) for x in eit)
    if tok == "e":
        return eit in {tuple(Fraction(x) for x in h) for h in halves.values()}
    raise ValueError(f"unknown glide letter {tok!r}")


def _signed(x: Fraction) -> Fraction:
    x = x % 1
    return x - 1 if x > Fraction(1, 2) else x


def _letter(x: Fraction) -> str:
    s = _signed(x)
    base = _LETTERS.get(abs(s))
    if base is None:
        raise ValueError(f"internal translation {x} has no superspace letter "
                         f"(0, s, t, q, h)")
    return ("-" + base) if s < 0 else base


def _candidates(group: SuperspaceGroup, positions, *, exact: bool = False
                ) -> list[list[Fraction]]:
    """Per position, every IIT an admitted lattice variant of its generator
    gives (Stokes 2011 § 5.2 steps 1-2).

    ``exact``: step 3's restriction to the generator's base variant alone —
    the strictly matching one with the smallest translation (§ 5.1(3): "keep
    the absolute values of the translational components as small as
    possible") — since Stokes 2011's Example 3 (p. 53) admits there only
    "translations that have all-zero external components".
    """
    return _candidates_cached(group.q, group.operations, group.centerings,
                              tuple(positions), exact)


@functools.lru_cache(maxsize=8192)
def _candidates_cached(q, operations, centerings, positions, exact):
    group = _GroupView(q, operations, centerings)
    qr = group.q.rational
    free_axes = {next(i for i in range(3) if f[i]) for f in group.q.free} \
        if group.q.axis_aligned() else set()
    qr_eff = tuple(Fraction(0) if i in free_axes else qr[i] for i in range(3))
    reps = {op.rotation: op for op in group.operations}
    if not any(qr_eff):
        # τ = δ for every variant; one strictly matching variant is enough
        box = [range(-1, 2)] * 3
    else:
        box = [range(-max(2, c.denominator), max(2, c.denominator) + 1) for c in qr_eff]
    out = []
    for pos in positions:
        op = reps.get(pos.rotation)
        if op is None:
            raise ValueError("the group lacks a generator its symbol names")
        if op.epsilon == -1:
            out.append([Fraction(0)])
            continue
        found = []
        for c in group.centerings:
            for n in product(*box):
                v = tuple(op.translation[i] + c.translation[i] + n[i] for i in range(3))
                eit = _eit_exact(op.rotation, v)
                if not _expected(pos, tuple(x % 1 for x in eit), None):
                    continue
                d = op.delta + c.delta
                tau = (d - sum(qr_eff[i] * v[i] for i in range(3))) % 1
                found.append((max(abs(x) for x in v), sum(abs(x) for x in v), v, eit, tau))
        if not found:
            raise ValueError(f"no lattice variant of the {pos.token!r} generator "
                             f"matches its symbol letter")
        if exact:
            vals = {min(found)[4]}
        else:
            vals = {f[4] for f in found}
        out.append(tuple(sorted(vals)))
    return tuple(out)


def _nicest_key(vals) -> tuple:
    signed = [_signed(v) for v in vals]
    return (sum(1 for s in signed if s < 0), -sum(1 for s in signed if s == 0),
            max((s.denominator for s in signed), default=1),
            tuple(s.denominator for s in signed),
            tuple(abs(s.numerator) for s in signed))


def _hm_text(sg: gemmi.SpaceGroup) -> str:
    """``P4_2/mcm``: the setting's H-M symbol, compact, subscripts with _."""
    letter = sg.hm.split()[0]
    out = letter
    for tok in _tokens(sg):
        def sub(t):
            if t[0] in "0123456789" and len(t) > 1:
                return t[0] + "_" + t[1:]
            return t
        out += "/".join(sub(p) for p in tok.split("/"))
    return out


def _setting_of(group: SuperspaceGroup) -> gemmi.SpaceGroup | None:
    """The tabulated setting whose H-M symbol names this basic group: an exact
    match of the operations, or else one with the same rotations and centring
    that an origin shift reaches (the letters are origin-invariant: ε = −1
    ones print 0, and an ε = +1 internal translation does not move under an
    origin shift, de Wolff 1981 p. 628)."""
    xyz = group.basic_xyz()
    return _setting_of_xyz(tuple(sorted(xyz)))


@functools.lru_cache(maxsize=4096)
def _setting_of_xyz(xyz: tuple) -> gemmi.SpaceGroup | None:
    ops = gemmi.GroupOps([gemmi.Op(x) for x in xyz])
    found = gemmi.find_spacegroup_by_ops(ops)
    if found is not None:
        return found
    den = gemmi.Op.DEN
    mine = {}
    cen = set()
    for op in ops:
        r = tuple(tuple(x // den for x in row) for row in op.rot)
        t = tuple(x % den for x in op.tran)
        mine.setdefault(r, set()).add(t)
        if r == ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
            cen.add(t)
    for sg in gemmi.spacegroup_table():
        theirs = {}
        for op in sg.operations():
            r = tuple(tuple(x // den for x in row) for row in op.rot)
            theirs.setdefault(r, set()).add(tuple(x % den for x in op.tran))
        if set(theirs) != set(mine) or len(next(iter(theirs.values()))) != len(cen):
            continue
        if _origin_shift(mine, theirs, den) is not None:
            return sg
    return None


def to_tabulated(group: SuperspaceGroup) -> SuperspaceGroup:
    """The same group with its origin moved onto the tabulated setting whose
    symbol names it (:func:`_setting_of`), so its operations are that
    setting's exactly; ``group`` itself when they already are."""
    from .operators import SuperspaceTransform

    sg = _setting_of(group)
    if sg is None:
        raise ValueError("the basic group is not in a tabulated setting")
    den = gemmi.Op.DEN
    ops = gemmi.GroupOps([gemmi.Op(x) for x in group.basic_xyz()])
    mine: dict = {}
    for op in ops:
        r = tuple(tuple(x // den for x in row) for row in op.rot)
        mine.setdefault(r, set()).add(tuple(x % den for x in op.tran))
    theirs: dict = {}
    for op in sg.operations():
        r = tuple(tuple(x // den for x in row) for row in op.rot)
        theirs.setdefault(r, set()).add(tuple(x % den for x in op.tran))
    p = _origin_shift(mine, theirs, den)
    if p is None or not any(p):
        return group
    return group.transformed(SuperspaceTransform.build(
        origin=tuple(Fraction(x, den) for x in p)))


def _letters_key(text: str) -> tuple:
    """The step-4 key of a printed symbol's letters."""
    m = _SYMBOL.match(text)
    return _nicest_key(_letters(m.group("tail")))


def _origin_shift(mine: dict, theirs: dict, den: int):
    """p (in 1/den) with v + (E − R)p ∈ their translations for every op."""
    for p in product(range(den), repeat=3):
        ok = True
        for r, ts in mine.items():
            t0 = next(iter(ts))
            rp = tuple(sum(r[i][k] * p[k] for k in range(3)) for i in range(3))
            moved = tuple((t0[i] + p[i] - rp[i]) % den for i in range(3))
            if moved not in theirs[r]:
                ok = False
                break
        if ok:
            return p
    return None


def symbol_candidates(group: SuperspaceGroup) -> tuple[str, list[str]]:
    """(the printed symbol under Stokes 2011's rules, every admissible one).

    "Admissible" = some choice of strictly matching lattice variants per
    generator gives it (steps 1-2); the printed one is the nicest (step 4),
    before :data:`ITC_C_EXCEPTIONS` is applied.  Needs the basic group in a
    tabulated setting and centrings without internal parts (the BSG setting).
    """
    sg = _setting_of(group)
    if sg is None:
        raise ValueError("the basic group is not in a tabulated setting, so "
                         "it has no Hermann-Mauguin symbol to print")
    if any(c.delta for c in group.centerings):
        raise ValueError(
            "a centring carries an internal translation (a supercentred "
            "description); symbols are printed in the BSG setting, whose "
            "centrings have none (Stokes 2011 p. 49) — apply q → q + H first")
    positions = _positions(sg)
    cands = _candidates(group, positions)
    head = _hm_text(sg) + group.q.label()
    best = min(product(*cands), key=_nicest_key)
    allsyms = sorted({head + "".join(_letter(v) for v in combo)
                      for combo in product(*cands)})
    return head + "".join(_letter(v) for v in best), allsyms


def _symbol_key(group: SuperspaceGroup) -> tuple:
    sg = _setting_of(group)
    if sg is None:
        raise ValueError("untabulated setting")
    cands = _candidates(group, _positions(sg))
    return _nicest_key(min(product(*cands), key=_nicest_key))


def _exact_symbol(group: SuperspaceGroup) -> str:
    sg = _setting_of(group)
    cands = _candidates(group, _positions(sg), exact=True)
    best = min(product(*cands), key=_nicest_key)
    return _hm_text(sg) + group.q.label() + "".join(_letter(v) for v in best)


@dataclass(frozen=True)
class _Entry:
    group: SuperspaceGroup
    printed: str          # step 4
    admissible: tuple     # steps 1-2
    assigned: str         # after step 3


@functools.lru_cache(maxsize=1024)
def _family_table(xhm: str, q_label: str) -> tuple:
    """Every description of every group over this setting and q, each with
    its symbol after Stokes 2011 § 5.2 step 3: when inequivalent groups share
    the nicest symbol, the one that reaches it with its base variants keeps
    it and the others are printed with the restricted (exact) variants."""
    from .generation import family_orbits

    sg = gemmi.find_spacegroup_by_name(xhm)
    orbits = family_orbits(sg, ModulationVector.parse(q_label))
    rows = []
    for k, members in enumerate(orbits):
        for g in members:
            printed, alls = symbol_candidates(g)
            rows.append((k, g, printed, tuple(alls)))
    by_printed: dict = {}
    for k, g, printed, _ in rows:
        by_printed.setdefault(printed, set()).add(k)
    exact_cache: dict = {}

    def exact(g):
        key = g.operations
        if key not in exact_cache:
            exact_cache[key] = _exact_symbol(g)
        return exact_cache[key]

    table = []
    for k, g, printed, alls in rows:
        orbits_sharing = by_printed[printed]
        if len(orbits_sharing) == 1:
            assigned = printed
        else:
            owners = {kk for kk, gg, pp, _ in rows
                      if pp == printed and exact(gg) == printed}
            assigned = printed if owners == {k} else exact(g)
        table.append((k, _Entry(g, printed, alls, assigned)))
    return tuple(table)


def _entry_of(group: SuperspaceGroup):
    sg = _setting_of(group)
    if sg is None or not group.q.axis_aligned() or any(c.delta for c in group.centerings):
        return None
    try:
        table = _family_table(sg.xhm(), group.q.label())
    except ValueError:
        return None
    mine = set(group.all_operations())
    for _, e in table:
        if set(e.group.all_operations()) == mine:
            return e
    return None


def symbol(group: SuperspaceGroup) -> str:
    """The one-line symbol, under Stokes 2011 § 5.2 steps 1-4 (step 3 against
    the other groups over the same basic group and q), with ITC-C's spelling
    where Stokes 2011 Table 9 says it differs from the conventions.

    A magnetic group gets its magnetic superspace symbol
    (:func:`.magnetic.magnetic_symbol`; Stokes & Campbell 2022 p. 366)."""
    if group.is_magnetic:
        from .magnetic import magnetic_symbol

        return magnetic_symbol(group)
    e = _entry_of(group)
    printed = e.assigned if e is not None else symbol_candidates(group)[0]
    return ITC_C_EXCEPTIONS.get(printed, (printed,))[0]


# ---------------------------------------------------------------------------
# parsing
# ---------------------------------------------------------------------------
_SYMBOL = re.compile(r"^\s*(?P<hm>[^(]+?)\s*\((?P<q>[^)]*)\)\s*(?P<tail>.*?)\s*$")
_LETTER_TOKEN = re.compile(r"(-|¯)?([0stqh])(̄|̅)?")


def _normal_hm(text: str) -> str:
    s = text.replace("_", "").replace(" ", "")
    s = re.sub(r"(\d)[̄̅]", r"-\1", s)
    return s


def _letters(tail: str) -> list[Fraction]:
    out = []
    pos = 0
    t = tail.replace(" ", "")
    while pos < len(t):
        m = _LETTER_TOKEN.match(t, pos)
        if m is None:
            raise ValueError(f"cannot read the internal-translation letters {tail!r}")
        v = _VALUES[m.group(2)]
        if m.group(1) or m.group(3):
            v = -v
        out.append(v % 1)
        pos = m.end()
    return out


def parse_symbol(text: str) -> SuperspaceGroup:
    """The superspace group a one-line symbol names, e.g. ``"Pbnm(00γ)s00"``.

    The basic group is read in the setting the symbol names (origin choice 2
    where ITA offers two, hexagonal axes); the group is found among those
    :func:`~rietx.crystallography.superspace.generation.generate` derives for
    that basic group and q (module docstring).  A magnetic symbol — primes, a
    ``.1``, or a ``.1'`` with its extra phase letter — is read by
    :func:`.magnetic.parse_magnetic_symbol`.  Refused by name: a second
    modulation vector (d > 1), a symbol with no q (ambiguous, Yamamoto et
    al. 1985), and a symbol matching no group or several.
    """

    m = _SYMBOL.match(str(text))
    if m is None:
        raise ValueError(
            f"{text!r} has no modulation vector in parentheses; a superspace "
            f"symbol is ambiguous without its q (Yamamoto et al. 1985), so a "
            f"symbol alone is refused")
    tail = m.group("tail")
    if "(" in tail:
        raise ValueError(f"{text!r} gives a second modulation vector: superspace "
                         f"groups are built here for d = 1 only")
    hm = m.group("hm")
    if "'" in hm or "′" in hm or hm.rstrip().endswith(".1"):
        from .magnetic import parse_magnetic_symbol

        return parse_magnetic_symbol(text)
    q = ModulationVector.parse(m.group("q"))
    want = _letters(tail)
    settings = _settings_named(hm)
    if not settings:
        raise ValueError(f"unknown basic space group {hm!r} in {text!r}")
    errors = []
    for sg in settings:
        try:
            return _match_in(sg, q, want, text)
        except ValueError as exc:
            errors.append(exc)
    raise errors[0]


def _settings_named(hm: str) -> list:
    """The settings a printed H-M symbol may name: as read (origin choice 2,
    hexagonal axes), and for a short monoclinic symbol each unique axis, c
    first, as ITC-C's (3+1)D tables use it (de Wolff 1981 Table 1)."""
    base = _normal_hm(hm)
    out = []
    for ext in (":2", ":H", ""):
        sg = gemmi.find_spacegroup_by_name(base + ext)
        if sg is not None:
            out.append(sg)
            break
    short = re.fullmatch(r"([PABCIF])(-?\d+/?[a-z]?|[a-z])", base)
    if short and (not out or out[0].crystal_system_str() == "monoclinic"):
        letter, tok = short.groups()
        for name in (f"{letter}11{tok}", f"{letter}{tok}11", f"{letter}1{tok}1"):
            sg = gemmi.find_spacegroup_by_name(name)
            if (sg is not None and sg.crystal_system_str() == "monoclinic"
                    and all(sg.xhm() != o.xhm() for o in out)):
                out.append(sg)
        out.sort(key=lambda sg: sg.hm.split()[3:4] == ["1"])
    return out


def _match_in(sg, q, want, text) -> SuperspaceGroup:
    table = _family_table(sg.xhm(), q.label())
    if not table:
        raise ValueError(f"q = {q.label()} is not compatible with {sg.xhm()}")
    n_pos = len(_positions(sg))
    if len(want) != n_pos:
        raise ValueError(
            f"{text!r} has {len(want)} internal-translation letters; "
            f"{_hm_text(sg)} has {n_pos} symbol generators")
    head = _hm_text(sg) + q.label()
    given = head + "".join(_letter(v) for v in want)
    target = next((k for k, (itc, _) in ITC_C_EXCEPTIONS.items() if itc == given),
                  given)
    exact = {k: e.group for k, e in table if e.assigned == target}
    loose = {k: e.group for k, e in table
             if k not in exact and (target in e.admissible or given in e.admissible)}
    hits = list(exact.values()) or list(loose.values())
    if len(hits) == 1:
        g = hits[0]
        return SuperspaceGroup(g.q, g.operations, g.centerings,
                               symbol=symbol(g), number=None)
    if not hits:
        raise ValueError(
            f"no superspace group over {sg.xhm()} with q = {q.label()} has the "
            f"symbol {text!r}; its descriptions there print as "
            f"{sorted({e.assigned for _, e in table})}")
    raise ValueError(
        f"{text!r} is admissible for {len(hits)} inequivalent groups (a "
        f"degenerate symbol, Stokes 2011 § 5); give the operator list instead")

