"""A phase's change of basis, and the ITA standard setting of its group and cell.

**Public API — structure standardization, chunk S0** (machinery: every step is
public and callable alone; nothing here chooses among descriptions the rules
leave open)::

    change_basis(phase, P, p=(0, 0, 0), *, allow_inversion=False) -> Phase
    standard_setting(phase, *, origin_choice=2, smaller_screw=True,
                     reduce_cell=True)                          -> StandardSetting
    orthorhombic_relabellings(space_group)                      -> tuple[(P, p), ...]
    enantiomorph_partner(number)                                -> int | None

**(P, p), the convention of** :mod:`.representation.subgroups` **and**
:mod:`.representation.distortion`: x = P·x′ + p.  The columns of P are the new
axes in the old fractional coordinates and p is the new origin in the old cell
(ITA A1 eqs. 2.1.3.3–2.1.3.9; Arnold, ITA A 5th ed. § 5.1.3).  So the metric
goes as G′ = PᵀGP, coordinates as x′ = P⁻¹(x − p), Miller indices as h′ = Pᵀh
and the U* form of a displacement tensor as U*′ = P⁻¹U*P⁻ᵀ.

**The rules** are Parthé & Gelato (1984), *Acta Cryst.* A40, 169–183,
pp. 172–173 (page images checked), the setting and
cell half of the standardization behind the standardized data of Pearson's
and the TYPIX-based databases:

- rule 1, right-handed axes: every P here has det P > 0, except the
  enantiomorph's inversion, which is reported;
- rule 2, ITA's standard setting (:func:`~.symmetry.ita_standard_setting`):
  (a) unique axis b, cell choice 1; (b) the obverse triple hexagonal cell of
  an R lattice; (c) origin choice 2 where ITA gives two; (d) of an
  enantiomorphic pair, the member with the smaller screw index, the structure
  then described as its mirror image (p. 174: "print minus signs in front of
  the standardized coordinates and name the true space group"), which
  :attr:`StandardSetting.inverted` records;
- rule 3, the cell: (a) triclinic, the Niggli-reduced cell
  (:func:`rietx.indexing.reduce.reduce_cell`, ε as there); (b) monoclinic P
  without a glide, the "reset" Niggli cell, a and c the shortest translations
  ⊥ b with a ≤ c and β ≥ 90°; monoclinic with a glide or a C lattice (Pc,
  P2/c, P2₁/c, C2, Cm, Cc, C2/m, C2/c), the "best" cell for cell choice 1 of
  Parthé & Gelato (1985), *Acta Cryst.* A41, 142–151 (page images checked): a and c the shortest translations ⊥ b among the
  bases that keep the standard symbol, β non-acute, and no a ≤ c order, since
  interchanging a and c would leave cell choice 1 (their Sc₂FeSi₂ best cell,
  Table 3 p. 151, has a > c); (c) orthorhombic, a ≤ b ≤ c where the affine
  normaliser allows all six relabellings, a ≤ b where it allows the swap,
  computed per group from the normaliser's linear parts
  (:func:`orthorhombic_relabellings`) and applied lexicographically, which is
  the paper's statement where it applies.

**The 1985 rule, as built.**  With a′ = p·a + q·c, b′ = t·b, c′ = r·a + s·c
(the paper's eq. 1, p. 143), the bases that keep the symbol are those of its
Table 1 (p. 146): p odd and r even for Pc, P2/c and P2₁/c (the glide stays a
c glide); q even and s odd for the five C groups (the centring stays C); for
Cc and C2/c also p odd, which q even and |ps − qr| = 1 already imply.  Each
set is a group, so the cell is reached as the paper reaches it (p. 145), by
repeated "first" transformations, each a shorter a′ = a + k·c or c′ = c + m·a
with k, m of the allowed parity: a Gauss reduction in the (a, c) plane whose
steps keep the parity.  It stops where no allowed step shortens a or c,
which is the 1001 field of the paper's Figs. 3(a) and 4(a), bounded by the
lines of its eq. (6) (p. 147); a test checks against a brute-force search
that a and c are then the shortest allowed translations.  Of the sign
choices the paper's note (3), p. 144, takes r, s ≥ 0, so s > 0 here (s is
odd, never 0); then a′ is negated if β′ would be acute, and t is the sign
that makes det P = +1 (rule 1).  For Cc and C2/c a transformation with r odd
needs an origin shift (Table 1: 0, ¼, 0 and ¼, ¼, 0).  It is not tabulated
here but solved exactly: the first shift on the ¼ grid, zero first, that
carries the operation list onto ITA's.  The paper's three demonstrations
(p. 147) and its Sc₂FeSi₂ pair (Table 3) are tests.

The group step reuses the one standardiser of
:mod:`.representation.subgroups` (``_standardise``, Yue on #806): a probe
structure of the phase's own group on its own (symmetrised) metric goes to
spglib with the Hall number of the target setting, and the (P, p) spglib
returns is accepted only if it carries the group onto that setting's
operation list exactly, in ``Fraction`` arithmetic.  spglib is a black box
here; its default Hall number is origin choice 1, which is why the setting is
passed explicitly.
"""

from __future__ import annotations

import itertools
import math
from dataclasses import dataclass
from fractions import Fraction
from functools import lru_cache

import gemmi
import numpy as np

from .representation.subgroups import (
    _columns,
    _frac_part,
    _from_operations,
    _Group,
    _integral,
    _inv,
    _mat,
    _metric,
    _mm,
    _mv,
    _NotIntegral,
    _q,
    _standardise,
)
from .symmetry import _closest_type, ita_standard_setting, resolve_group, unnamed_label

__all__ = ["StandardSetting", "change_basis", "enantiomorph_partner",
           "orthorhombic_relabellings", "standard_setting"]

_I3 = ((1, 0, 0), (0, 1, 0), (0, 0, 1))


# ---------------------------------------------------------------- exact helpers

def _zero() -> tuple:
    return (Fraction(0), Fraction(0), Fraction(0))


def _det(m) -> Fraction:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _floats(m) -> np.ndarray:
    return np.array([[float(x) for x in row] for row in m], dtype=np.float64)


def _compose(P1, p1, P2, p2):
    """x = P1·x1 + p1 and x1 = P2·x2 + p2, as one (P, p) from x2 to x."""
    return _mm(P1, P2), tuple(a + b for a, b in zip(_mv(P1, p2), p1))


def _group_of_phase(phase) -> _Group:
    return _from_operations(resolve_group(phase.space_group, phase.symmetry_operations).operations())


def _phase_metric(phase) -> np.ndarray:
    from .lattice import direct_metric_tensor

    c = phase.cell
    return np.asarray(direct_metric_tensor(c.a.value, c.b.value, c.c.value, c.alpha.value,
                                           c.beta.value, c.gamma.value), dtype=np.float64)


def _symmetrised(G: np.ndarray, group: _Group) -> np.ndarray:
    """The metric averaged over the group's point group: G itself when the cell obeys it."""
    rots = [_floats(W) for W in group.reps]
    return sum(W.T @ G @ W for W in rots) / len(rots)


def _centrings(group: _Group) -> list[tuple]:
    """The group's lattice translations in [0, 1)³: the closure of its lattice basis mod 1."""
    pts = {_zero()}
    cols = [_frac_part(c) for c in _columns(group.L)]
    while True:
        more = {_frac_part(tuple(a + b for a, b in zip(x, c))) for x in pts for c in cols} | pts
        if more == pts:
            return sorted(pts)
        pts = more


def _all_operations(group: _Group) -> list[tuple]:
    """Every (W, w) of one unit cell, centrings expanded, identity first."""
    cen = _centrings(group)
    out = []
    for W, w in group.reps.items():
        for t in cen:
            out.append((W, _frac_part(tuple(a + b for a, b in zip(w, t)))))
    out.sort(key=lambda op: (op[0] != _I3, op[0], op[1]))
    return out


def _gemmi_op(W, w) -> gemmi.Op:
    den = gemmi.Op.DEN
    tran = []
    for x in w:
        v = x * den
        if v.denominator != 1:
            raise ValueError(f"translation {x} is not a multiple of 1/{den}: gemmi cannot state it")
        tran.append(int(v) % den)
    op = gemmi.Op()
    op.rot = [[int(v) * den for v in row] for row in W]
    op.tran = tran
    return op


def _named(ops: list[tuple]) -> gemmi.SpaceGroup | None:
    return gemmi.find_spacegroup_by_ops(gemmi.GroupOps([_gemmi_op(W, w) for W, w in ops]))


def _abc_text(P, p) -> str:
    """The new basis as combinations of a, b, c, then the origin: ``"b,-a,c;0,0,1/4"``."""
    def comb(col):
        terms = []
        for coef, name in zip(col, "abc"):
            if coef == 0:
                continue
            if coef == 1:
                terms.append(f"+{name}")
            elif coef == -1:
                terms.append(f"-{name}")
            else:
                terms.append(f"{'+' if coef > 0 else '-'}{abs(coef)}{name}")
        text = "".join(terms) or "0"
        return text[1:] if text.startswith("+") else text
    return ",".join(comb(c) for c in _columns(P)) + ";" + ",".join(str(x) for x in p)


# ---------------------------------------------------------------- change of basis

_FRAME_FIELDS = (
    ("preferred_orientation", "a preferred-orientation axis is a direction in the old axes"),
    ("texture", "spherical-harmonic texture coefficients are referred to the old axes"),
    ("microstrain", "Stephens strain coefficients multiply monomials of the old hkl"),
    ("propagation_vector", "a propagation vector is in the old reciprocal axes"),
    ("magnetic_symmetry", "a magnetic group's operations are in the old axes"),
    ("distortion_modes", "mode amplitudes are absolute against a base in the old cell"),
)


def _refuse_frame_dependent(phase) -> None:
    for name, why in _FRAME_FIELDS:
        if getattr(phase, name, None) is not None:
            raise ValueError(
                f"phase {phase.name!r} cannot change basis: it carries {name}, and {why}, "
                f"which change_basis does not transform. Restate the phase without it "
                f"(phase.model_copy(update={{{name!r}: None}})) and set it again in the new axes")
    if phase.rigid_bodies:
        raise ValueError(
            f"phase {phase.name!r} cannot change basis: it carries {len(phase.rigid_bodies)} "
            f"rigid bodies, whose orientations and origins are in the old axes")
    if phase.restraints:
        raise ValueError(
            f"phase {phase.name!r} cannot change basis: it carries {len(phase.restraints)} "
            f"restraints, whose symmetry-operation indices count the old operation list")
    moments = [a.label for a in phase.atoms if a.moment is not None]
    if moments:
        raise ValueError(
            f"phase {phase.name!r} cannot change basis: sites {', '.join(moments[:4])} carry "
            f"moments, whose components are in the old axes")


def _held(parameter, value: float):
    """A transformed number: held, with no esd and no bound, since both were the old axis's."""
    return parameter.model_copy(update={
        "value": float(value), "vary": False, "expr": None, "stderr": None,
        "min": -math.inf, "max": math.inf})


def change_basis(phase, P, p=(0, 0, 0), *, allow_inversion: bool = False):
    """The same crystal described in new axes and origin: x = P·x′ + p.

    ``P`` is a 3×3 matrix whose columns are the new axes in the old fractional
    coordinates, ``p`` the new origin in the old cell (the module's
    convention).  Entries may be integers, ``Fraction`` s, ratio strings or
    floats a small-denominator ratio stands for (``subgroups._q``).  Every
    column of P must be a lattice translation of the phase's group (centring
    vectors count), so the new cell is a cell of the crystal: a primitive
    rhombohedral cell of an R lattice, a C cell of an I-centred monoclinic one,
    or a supercell, whose extra translations become centrings.

    What moves and how (ITA A1 § 2.1.3): the cell through G′ = PᵀGP; each
    listed atom's coordinates through x′ = P⁻¹(x − p), wrapped into [0, 1); an
    anisotropic U^ij through U*′ = P⁻¹U*P⁻ᵀ, U* = U^ij·a*ᵢa*ⱼ; the operations
    through W′ = P⁻¹WP, w′ = P⁻¹(w + Wp − p), named from gemmi's table where a
    setting there has exactly that list, and otherwise carried as
    ``symmetry_operations`` under a bracketed label.  Labels, species,
    occupancies, B and the sample-broadening fields are unchanged: none is
    referred to the axes.  The scale is multiplied by (V/V′)², because the
    structure factor sums over the cell, so ``predict()`` is unchanged (the
    rule :func:`~.symmetry.restate_in_hexagonal_axes` states for R → H, which
    this generalises).

    Every transformed number is held, with no esd, expression or bound: a
    coordinate or cell edge that was one parameter may now be a combination of
    several, and the ties that made it so are not stated in the new axes.

    det P < 0 is the mirror image: a phase's cell is right-handed by
    construction (Parthé & Gelato 1984 rule 1), so the result describes the
    *inverted* structure, which is what the enantiomorph rule wants and nothing
    else does; it is refused unless ``allow_inversion`` is asked for by name.
    Powder |F(hkl)|² is the same either way (Friedel; with f″ the powder peak
    is the ±h average already).

    Refused by name: what is referred to the old axes and not transformed here
    (preferred orientation, texture, Stephens strain, propagation vector,
    magnetic group and moments, distortion modes, rigid bodies, restraints).
    """
    from ..schemas.structure import AnisoU
    from .adp import reciprocal_axis_lengths, tensor_from_voigt, voigt_from_tensor

    P = _mat(P)
    p = tuple(_q(x) for x in p)
    det = _det(P)
    if det == 0:
        raise ValueError("P is singular: its columns are not three independent axes")
    if det < 0 and not allow_inversion:
        raise ValueError(
            f"det P = {det} < 0: the new axes are left-handed, so the result would describe "
            f"the mirror image of phase {phase.name!r}. Pass allow_inversion=True to ask for it")
    _refuse_frame_dependent(phase)

    group = _group_of_phase(phase)
    for j, col in enumerate(_columns(P)):
        if not _integral(_mv(group.Linv, col)):
            raise ValueError(
                f"column {j} of P, {tuple(str(x) for x in col)}, is not a lattice translation of "
                f"{phase.space_group!r}: the new axes would not span a cell of the crystal")
    try:
        new_group = group.transformed(P, p)
    except _NotIntegral as exc:  # pragma: no cover - lattice columns keep W integral
        raise ValueError(f"P does not carry {phase.space_group!r} to integer rotations") from exc
    ops = _all_operations(new_group)
    named = _named(ops)

    if phase.symmetry_operations is not None or named is None:
        if phase.symmetry_operations is not None:
            ordered = []
            Q = _inv(P)
            for text in phase.symmetry_operations:
                op = gemmi.Op(text)
                W = tuple(tuple(Fraction(v, op.DEN) for v in row) for row in op.rot)
                w = tuple(Fraction(v, op.DEN) for v in op.tran)
                W2 = tuple(tuple(int(v) for v in row) for row in _mm(_mm(Q, W), P))
                w2 = _frac_part(_mv(Q, tuple(a + b - c for a, b, c in zip(w, _mv(W, p), p))))
                if (W2, w2) not in ordered:
                    ordered.append((W2, w2))
            ordered += [op for op in ops if op not in ordered]
        else:
            ordered = ops
        xyz = [_gemmi_op(W, w).triplet() for W, w in ordered]
    else:
        xyz = None
    if named is not None:
        label = named.xhm()
    else:
        closest = _closest_type(tuple(xyz))
        label = unnamed_label(closest.hm if closest is not None else None,
                              f"unnamed in {_abc_text(P, p)}")

    Pf, Qf = _floats(P), _floats(_inv(P))
    pf = np.array([float(x) for x in p])
    G_old = _phase_metric(phase)
    G_new = Pf.T @ G_old @ Pf
    lengths = np.sqrt(np.diag(G_new))
    angles = [float(np.degrees(np.arccos(np.clip(G_new[m, n] / (lengths[m] * lengths[n]), -1, 1))))
              for m, n in ((1, 2), (0, 2), (0, 1))]
    cell = phase.cell
    new_cell = cell.model_copy(update={
        "a": _held(cell.a, lengths[0]), "b": _held(cell.b, lengths[1]),
        "c": _held(cell.c, lengths[2]), "alpha": _held(cell.alpha, angles[0]),
        "beta": _held(cell.beta, angles[1]), "gamma": _held(cell.gamma, angles[2])})
    old_six = (cell.a.value, cell.b.value, cell.c.value, cell.alpha.value, cell.beta.value,
               cell.gamma.value)
    new_six = (*[float(x) for x in lengths], *angles)
    astar_old = np.asarray(reciprocal_axis_lengths(*old_six), dtype=np.float64)
    astar_new = np.asarray(reciprocal_axis_lengths(*new_six), dtype=np.float64)

    atoms = []
    for atom in phase.atoms:
        x = Qf @ (np.array([atom.x.value, atom.y.value, atom.z.value]) - pf)
        x = x % 1.0
        x[x >= 1.0 - 1e-12] = 0.0
        update = {"x": _held(atom.x, x[0]), "y": _held(atom.y, x[1]), "z": _held(atom.z, x[2])}
        if atom.aniso is not None:
            ustar = np.asarray(tensor_from_voigt(atom.aniso.values())) * np.outer(astar_old, astar_old)
            u_new = voigt_from_tensor((Qf @ ustar @ Qf.T) / np.outer(astar_new, astar_new))
            names = ("u11", "u22", "u33", "u12", "u13", "u23")
            update["aniso"] = AnisoU(**{n: _held(getattr(atom.aniso, n), v)
                                        for n, v in zip(names, np.asarray(u_new).tolist())})
        atoms.append(atom.model_copy(update=update))

    ratio = (math.sqrt(np.linalg.det(G_old)) / math.sqrt(np.linalg.det(G_new))) ** 2
    scale = phase.scale.model_copy(update={
        "value": phase.scale.value * ratio,
        "min": phase.scale.min * ratio, "max": phase.scale.max * ratio,
        "stderr": None, "expr": None})
    return phase.model_copy(update={
        "space_group": label, "symmetry_operations": xyz, "cell": new_cell,
        "atoms": atoms, "scale": scale})


# ---------------------------------------------------------------- the group's standard setting

@lru_cache(maxsize=None)
def _hall_number(xhm: str) -> int:
    """spglib's Hall number for gemmi's setting ``xhm``, matched by operation list."""
    import spglib

    sg = gemmi.find_spacegroup_by_name(xhm)
    want = _from_operations(sg.operations()).key()
    for hall in range(1, 531):
        kind = spglib.get_spacegroup_type(hall)
        if int(kind.number) != sg.number:
            continue
        ops = gemmi.symops_from_hall(kind.hall_symbol)
        if _from_operations(ops).key() == want:
            return hall
    raise RuntimeError(f"spglib has no Hall setting with the operations of {xhm!r}")  # pragma: no cover


def _screw_index(number: int) -> int:
    """The subscript of the first screw axis in the symbol (4 of P 4₃ 2 2 → 3), 0 if none."""
    for token in ita_standard_setting(number).hm.split()[1:]:
        if len(token) == 2 and token.isdigit():
            return int(token[1])
    return 0


def _type_number(group: _Group, G: np.ndarray) -> int:
    named = _named(_all_operations(group))
    if named is not None:
        return int(named.number)
    return int(_standardise(group, G)[0])


@lru_cache(maxsize=None)
def enantiomorph_partner(number: int) -> int | None:
    """The other member of an enantiomorphic pair of space-group types, or ``None``.

    Computed, not listed: the mirror image of the type's ITA setting (each
    operation (W, w) conjugated by the inversion, (W, −w)) is named by type.  The
    eleven pairs this finds are ITA's (P4₁/P4₃, P4₁22/P4₃22, P4₁2₁2/P4₃2₁2,
    P3₁/P3₂, P3₁12/P3₂12, P3₁21/P3₂21, P6₁/P6₅, P6₂/P6₄, P6₁22/P6₅22,
    P6₂22/P6₄22, P4₃32/P4₁32), which a test holds it to.
    """
    group = _from_operations(ita_standard_setting(number).operations())
    mirror = group.transformed(tuple(tuple(-v for v in row) for row in _I3), _zero())
    other = _type_number(mirror, _metric(mirror))
    return None if other == number else other


@lru_cache(maxsize=None)
def orthorhombic_relabellings(space_group: str) -> tuple[tuple, ...]:
    """The axis relabellings an orthorhombic group's affine normaliser allows, as (P, p).

    One entry per permutation of the axes the normaliser contains, identity
    first: P a signed permutation matrix with det P = +1 (rule 1), and p the
    origin shift that, with it, carries the group's operation list onto itself
    exactly.  Six entries are the cubic affine normalisers of Parthé & Gelato
    (1984) rule 3(c) (and Burzlaff & Zimmermann (1980), *Z. Kristallogr.* 153, 151–179), where a ≤ b ≤ c is
    reachable; two (identity and a ↔ b) the tetragonal ones, where a ≤ b is;
    one, a symbol that fixes its axes; three, the cyclic permutations of a
    normaliser like Pbca's.

    The shift is searched exactly on the grid 1/(2D), D the least common
    denominator of the group's translations and centrings: an orthorhombic
    operation's rotation is diagonal with entries ±1, so (W − 1)p ≡ δ fixes
    each component of p modulo ½ from a δ on the 1/D grid, and the grid holds
    every solution.
    """
    sg = gemmi.find_spacegroup_by_name(space_group)
    if sg is None or not 16 <= sg.number <= 74:
        raise ValueError(f"{space_group!r} is not an orthorhombic space group gemmi tabulates")
    group = _from_operations(sg.operations())
    key = group.key()
    den = 1
    for W, w in _all_operations(group):
        for x in w:
            den = den * x.denominator // math.gcd(den, x.denominator)
    step = Fraction(1, 2 * den)
    grid = [step * k for k in range(2 * den)]
    found = []
    for perm in itertools.permutations(range(3)):
        hit = None
        for signs in itertools.product((1, -1), repeat=3):
            A = [[0] * 3 for _ in range(3)]
            for j in range(3):
                A[perm[j]][j] = signs[j]
            A = _mat(A)
            if _det(A) != 1 or group.transformed(A, _zero()).L != group.L:
                continue  # left-handed, or the centring is not kept: no shift can help
            for t in itertools.product(grid, repeat=3):
                try:
                    if group.transformed(A, t).key() == key:
                        hit = (A, tuple(t))
                        break
                except _NotIntegral:  # pragma: no cover - a signed permutation keeps W integral
                    break
            if hit:
                break
        if hit:
            found.append(hit)
    return tuple(found)


# ---------------------------------------------------------------- the cell

def _eps(G: np.ndarray) -> float:
    """Rule 3's tolerance, the Niggli reduction's: ε = NIGGLI_EPS_RELATIVE·V^(1/3)."""
    from ..indexing.reduce import NIGGLI_EPS_RELATIVE

    return NIGGLI_EPS_RELATIVE * float(np.linalg.det(G)) ** (1.0 / 6.0)


def _niggli(G: np.ndarray):
    from ..indexing.reduce import _basis_change, _cell_from_metric, reduce_cell

    red = reduce_cell(_cell_from_metric(G), "P")
    M = np.rint(_basis_change(red.change_of_basis)).astype(int)  # reduced rows = M · input rows
    P = _mat(M.T.tolist())
    if _det(P) < 0:  # -P is the same metric; for P1 and P-1 the same operation list
        P = tuple(tuple(-v for v in row) for row in P)
    return P


def _reset_monoclinic(G: np.ndarray):
    """a, c the shortest translations ⊥ b (Gauss reduction in that plane), a ≤ c, β ≥ 90°."""
    eps = _eps(G)
    a, c = np.array([1, 0, 0]), np.array([0, 0, 1])

    def dot(u, v):
        return float(u @ G @ v)

    while True:
        if dot(c, c) < dot(a, a) - eps:
            a, c = c, a
        m = round(dot(a, c) / dot(a, a))
        if m == 0:
            break
        c = c - m * a
    if dot(a, c) > eps:
        c = -c
    b = np.array([0, 1, 0])
    P = np.column_stack([a, b, c])
    if round(np.linalg.det(P)) < 0:
        P[:, 1] = -P[:, 1]
    return _mat(P.tolist())


def _best_monoclinic(G: np.ndarray, centred: bool):
    """Parthé & Gelato (1985)'s best cell for cell choice 1 of a glide or C group (module docstring).

    a′ = a + k·c with k even for a C lattice (q even), any k for a c glide;
    c′ = c + m·a with m even for a c glide (r even), any m for a C lattice.
    Each step takes the allowed multiple nearest the projection, which is the
    shortest of that kind, and is kept only if it shortens by more than ε.
    """
    eps = _eps(G)
    step_a, step_c = (2, 1) if centred else (1, 2)
    a, c = np.array([1, 0, 0]), np.array([0, 0, 1])

    def dot(u, v):
        return float(u @ G @ v)

    def nearest(x: float, step: int) -> int:
        return step * round(x / step)

    while True:
        moved = False
        k = nearest(dot(a, c) / dot(c, c), step_a)
        if k and dot(a - k * c, a - k * c) < dot(a, a) - eps:
            a, moved = a - k * c, True
        m = nearest(dot(a, c) / dot(a, a), step_c)
        if m and dot(c - m * a, c - m * a) < dot(c, c) - eps:
            c, moved = c - m * a, True
        if not moved:
            break
    if c[2] < 0:  # note (3), p. 144: r, s >= 0; s is odd, so s > 0
        c = -c
    if dot(a, c) > eps:  # beta' non-acute
        a = -a
    P = np.column_stack([a, np.array([0, 1, 0]), c])
    if round(np.linalg.det(P)) < 0:
        P[:, 1] = -P[:, 1]
    return _mat(P.tolist())


@lru_cache(maxsize=None)
def _setting_group(xhm: str) -> _Group:
    return _from_operations(gemmi.find_spacegroup_by_name(xhm).operations())


def _origin_keeping(xhm: str, P) -> tuple:
    """The first shift p on the ¼ grid (zero first) with (P, p) carrying ``xhm``'s operation list onto itself.

    A monoclinic operation's rotation is diagonal with entries ±1 in the b-unique
    setting and its translations lie on the ½ grid, so (W − 1)p ≡ δ fixes p
    modulo ½ from a δ on that grid, and the ¼ grid holds a solution whenever one
    exists (the paper's Table 1 shifts, 0, ¼, 0 and ¼, ¼, 0, are on it).
    """
    group = _setting_group(xhm)
    key = group.key()
    grid = [Fraction(k, 4) for k in range(4)]
    for t in itertools.product(grid, repeat=3):
        if group.transformed(P, t).key() == key:
            return tuple(t)
    raise RuntimeError(f"no origin keeps {xhm!r} under the best-cell basis; this is a bug")  # pragma: no cover


def _ordered(G: np.ndarray, relabellings) -> tuple:
    """The relabelling whose lengths are lexicographically smallest, ties (within ε) to the earlier."""
    eps = _eps(G)
    best, best_len = relabellings[0], None
    for P, p in relabellings:
        Pf = _floats(P)
        lengths = np.diag(Pf.T @ G @ Pf)
        if best_len is None:
            best, best_len = (P, p), lengths
            continue
        for mine, theirs in zip(lengths, best_len):
            if mine < theirs - eps:
                best, best_len = (P, p), lengths
                break
            if mine > theirs + eps:
                break
    return best


def _primitive_without_glide(number: int) -> bool:
    """A P lattice and no glide in the ITA symbol (P2, P2₁, Pm, P2/m, P2₁/m): rule 3(b)'s first case."""
    hm = ita_standard_setting(number).hm
    return hm.startswith("P") and not any(ch in "abcden" for ch in hm[1:])


def _cell_rule(number: int, xhm: str, G: np.ndarray):
    """(P, p, rule) of rule 3 for a group already in its ITA setting with metric G."""
    if number <= 2:
        return _niggli(G), _zero(), "R3a: Niggli-reduced cell"
    if number <= 15:
        if _primitive_without_glide(number):
            return _reset_monoclinic(G), _zero(), "R3b: reset Niggli cell (a ≤ c, β ≥ 90°)"
        P = _best_monoclinic(G, centred=xhm.startswith("C"))
        return P, _origin_keeping(xhm, P), ("R3b: best cell for cell choice 1 (Parthé & Gelato 1985): "
                                            "a, c the shortest the symbol allows, β ≥ 90°")
    if number <= 74:
        P, p = _ordered(G, orthorhombic_relabellings(xhm))
        return P, p, "R3c: a ≤ b ≤ c over the affine normaliser's relabellings"
    return _mat(_I3), _zero(), "R2: the cell is fixed by the setting"


@dataclass(frozen=True)
class StandardSetting:
    """A phase restated in ITA's standard setting, with the transformation that did it.

    ``phase`` is :func:`change_basis` of the input under (``P``, ``p``) (the
    module's convention, exact ``Fraction`` s).  ``number`` and ``symbol`` are
    the standard setting's type and gemmi symbol.  ``inverted`` is True when
    the input's type was the larger-screw member of an enantiomorphic pair, so
    the result describes its mirror image in the partner group (Parthé &
    Gelato 1984 p. 174: the true structure is −x of the standardized one, in
    the input's type).  ``cell_rule`` names the rule-3 step taken.
    """

    phase: object
    P: tuple
    p: tuple
    number: int
    symbol: str
    inverted: bool
    cell_rule: str

    @property
    def transform_text(self) -> str:
        """(P, p) as ``"a',b',c' in a,b,c;origin"``, e.g. ``"b,-a,c;0,0,1/4"``."""
        return _abc_text(self.P, self.p)


def standard_setting(phase, *, origin_choice: int = 2, smaller_screw: bool = True,
                     reduce_cell: bool = True) -> StandardSetting:
    """The phase in ITA's standard setting and the rule-3 cell (Parthé & Gelato 1984).

    Rule 2: the type's ITA setting (:func:`~.symmetry.ita_standard_setting`):
    unique axis b, cell choice 1; hexagonal axes for R; origin choice
    ``origin_choice`` (2, the paper's rule 2(c), unless 1 is asked for).  With
    ``smaller_screw`` (rule 2(d)) a larger-screw enantiomorph is restated as
    the mirror image in its partner, ``inverted`` reporting it.  With
    ``reduce_cell`` (rule 3), the cell step of the module docstring, with
    Parthé & Gelato (1985)'s best cell for the monoclinic centred and glide
    groups.  Rules 4-6 (representative triplets, Γ,
    atom order) are not applied: the atom list is the input's, each atom moved
    to the new axes.

    The group step goes through spglib with the target setting's Hall number,
    checked exactly (the module docstring); a phase already in the target
    setting is not moved by it.
    """
    group = _group_of_phase(phase)
    G0 = _symmetrised(_phase_metric(phase), group)
    number = _type_number(group, G0)
    inverted = False
    target_number = number
    if smaller_screw:
        partner = enantiomorph_partner(number)
        if partner is not None and _screw_index(partner) < _screw_index(number):
            target_number, inverted = partner, True
    target = ita_standard_setting(target_number, origin_choice)
    target_key = _from_operations(target.operations()).key()

    P, p = _mat(_I3), _zero()
    if inverted:
        P = tuple(tuple(-v for v in row) for row in _I3)
        P = _mat(P)
    work = group.transformed(P, p)
    if work.key() != target_key:
        Pf = _floats(P)
        _, _, (P2, p2) = _standardise(work, Pf.T @ G0 @ Pf, 1, hall_number=_hall_number(target.xhm()))
        P, p = _compose(P, p, P2, p2)
    if group.transformed(P, p).key() != target_key:  # pragma: no cover - _standardise checked it
        raise RuntimeError(f"no exact standard setting for {phase.space_group!r}; this is a bug")

    rule = "R2: setting only (reduce_cell=False)"
    if reduce_cell:
        Pf = _floats(P)
        P3, p3, rule = _cell_rule(target_number, target.xhm(), Pf.T @ G0 @ Pf)
        P, p = _compose(P, p, P3, p3)
        if group.transformed(P, p).key() != target_key:  # pragma: no cover - checked per rule
            raise RuntimeError(f"rule 3 left the setting of {phase.space_group!r}; this is a bug")

    out = change_basis(phase, P, p, allow_inversion=inverted)
    if out.space_group != target.xhm():  # pragma: no cover - the key equality above
        raise RuntimeError(f"{out.space_group!r} is not {target.xhm()!r}; this is a bug")
    return StandardSetting(phase=out, P=P, p=p, number=target_number, symbol=target.xhm(),
                           inverted=inverted, cell_rule=rule)
