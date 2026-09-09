"""Magnetic space-group operators: magCIF strings, the 1651 groups, moments.

A magnetic (Shubnikov) space group is an ordinary space group whose operations
each carry a **time-reversal sign** ε = ±1.  There are 1651 of them; the modern
statement of what they are and of the two settings they are tabulated in — the
Belov-Neronova-Smirnova (BNS) and the Opechowski-Guccione (OG) — is
Perez-Mato, Gallego, Tasci, Elcoro, de la Flor & Aroyo (2015), *Annu. Rev.
Mater. Res.* **45**, 217.  The sequential numbering this module speaks in is the
UNI numbering of Campbell, Stokes, Perez-Mato & Rodríguez-Carvajal (2022),
*Acta Cryst.* A**78**, 99, which is also what spglib's database is keyed by.

**The operator list is the stored form.**  A magnetic structure reaches this
package as a list of magCIF strings — ``_space_group_symop_magn_operation.xyz``
and ``_space_group_symop_magn_centering.xyz`` (COMCIFS ``magnetic_dic``) — and
never as a symbol, because no dependency here parses Shubnikov symbols and
every tool a user has (MAGNDATA, ISODISTORT, k-SUBGROUPSMAG, the GSAS-II
tutorials) already emits the list.  A UNI/BNS/OG *number* is accepted as an
alternative input and resolved through spglib's database
(Shinohara, Togo & Tanaka, 2023, *Acta Cryst.* A**79**, 390; Togo, Shinohara &
Tanaka, 2024, *Sci. Technol. Adv. Mater.: Methods* **4**, 2384822), whose
tabulated source is Litvin (2013), *Magnetic Group Tables*, IUCr.

Conventions, stated by physics rather than by letter
----------------------------------------------------
* **A moment is an axial vector, so its action is ε·det(R)·R** — the rotation
  **untransposed**, times the determinant, times the time-reversal sign.  The
  root ``CLAUDE.md`` rule ("reciprocal-space symmetry action is Rᵀ") is about
  *hkl*; a moment is a real-space axial vector and takes R.  The transposed set
  is a group too, so the allowed-moment subspace has the **same dimension**
  under the wrong action in every crystal system: only asserting that a known
  moment lies in the *span* can catch it (see ``adp_basis`` for the rank-2 twin
  of the same trap).  Measured on spglib's database: R and Rᵀ give a different
  span for 543 of the (group, site) pairs tested, and **every one of them is in
  a trigonal or hexagonal family** (space groups 149-194) — in an orthorhombic,
  tetragonal or cubic setting every stabiliser rotation is its own transpose on
  the moment subspace, and the wrong action is invisible.
* **Moment components are on the crystal axes, in μ_B**, the magCIF
  ``_atom_site_moment.crystalaxis_*`` convention: "a right-handed basis of unit
  vectors parallel to the unit-cell basis vectors", so |m| = √(mᵀ·G·m) with G
  the *unit-vector* metric (ones on the diagonal, cosines off it).  That basis
  is oblique whenever the cell is, so the magnitude is **not** √(Σmᵢ²) — see
  :func:`moment_magnitude`.  :func:`moment_to_cartesian` is the conversion the
  structure factor needs (decision D-3).
* **The symmetry action is the same in crystal-axis and in fractional
  components**, which is why this module can do the constraint algebra on
  integer matrices without ever seeing a cell: the two bases differ by
  ``diag(1/a, 1/b, 1/c)``, and a symmetry rotation never mixes two axes that
  the setting does not force to be equal in length
  (``symmetry.cell_constraints``), so the diagonal conjugation is the identity.

What this module does not do
----------------------------
* It does not resolve a Shubnikov **symbol** (``P4_2'/mnm'``).  spglib exposes
  UNI, BNS and OG *numbers* and no symbol table, so a symbol is refused by name
  rather than guessed at.
* It cannot emit operators in the **OG setting**.  spglib's database is BNS
  only; an OG number resolves to the same group, but the operators come out in
  the BNS setting and :attr:`MagneticGroup.setting` says so.  OG-setting
  operator lists would need Litvin's or the ISO-MAG tables directly.
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass, field
from fractions import Fraction
from math import lcm

import numpy as np
import spglib

from ..adp import cartesian_basis
from ..lattice import direct_metric_tensor
from ..symmetry import SITE_TOL
from ..wyckoff import _nullspace_int

#: Number of magnetic space groups (Litvin 2013; UNI numbering 1-1651).
N_MAGNETIC_SPACE_GROUPS = 1651

#: UNI numbers whose spglib database entry does not round-trip through
#: :func:`identify` on spglib 2.7.0.  Measured, not inherited: feeding each
#: entry's own operators back to ``get_magnetic_spacegroup_type_from_symmetry``
#: returns 275, nothing, and 277 for 282, 283 and 284 respectively.  282 and
#: 284 are labelled BNS 37.184/37.186 — the Ccc2 family — while their unprimed
#: subgroup identifies as Cmc2_1 (No. 36), which for a **type IV** group is a
#: contradiction: the unprimed subgroup of a type IV group *is* its family
#: space group.  Of the 977 type I/II/IV entries those two are the only ones
#: where the family disagrees, so this is a database defect and not a
#: convention this module should absorb.  Kept as data so the test asserting it
#: fails in both directions when spglib fixes it.
UNI_NOT_IDENTIFIABLE: tuple[int, ...] = (282, 283, 284)

_AXES = ("x", "y", "z")
_ABC = ("a", "b", "c")

# One signed term of a Jones-faithful component.  The denominator is allowed on
# either side of the axis letter because both spellings are in use: an operation
# writes ``x+1/2`` and a basis transform writes ``-a/3`` for the same rational.
_TERM = re.compile(r"(?P<sign>[+-])?(?P<num>\d+)?(?:/(?P<den1>\d+))?"
                   r"(?P<axis>[a-zA-Z])?(?:/(?P<den2>\d+))?")


def _parse_component(text: str, letters: tuple[str, ...]
                     ) -> tuple[list[Fraction], Fraction]:
    """One ``-x+1/2``-style component into (coefficients, constant), exactly."""
    coeff = [Fraction(0), Fraction(0), Fraction(0)]
    const = Fraction(0)
    s = text.replace(" ", "")
    if not s:
        raise ValueError(f"empty component in symmetry operation {text!r}")
    pos = 0
    while pos < len(s):
        m = _TERM.match(s, pos)
        if m is None or m.end() == pos:
            raise ValueError(f"cannot parse {text!r} at offset {pos}")
        pos = m.end()
        sign = -1 if m.group("sign") == "-" else 1
        num = int(m.group("num")) if m.group("num") else None
        d1, d2 = m.group("den1"), m.group("den2")
        if d1 and d2:
            raise ValueError(f"cannot parse {text!r}: two denominators in one term")
        den = int(d1 or d2 or 1)
        axis = m.group("axis")
        if axis is None:
            if num is None:
                raise ValueError(f"cannot parse {text!r}: a term with neither "
                                 f"a number nor an axis")
            const += sign * Fraction(num, den)
        else:
            letter = axis.lower()
            if letter not in letters:
                raise ValueError(f"cannot parse {text!r}: {axis!r} is not one "
                                 f"of {', '.join(letters)}")
            coeff[letters.index(letter)] += sign * Fraction(
                num if num is not None else 1, den)
    return coeff, const


def _format_rational(value: Fraction, letter: str | None) -> str:
    """``2b/3``, ``a``, ``1/2`` — the magnitude of one term, unsigned."""
    mag = abs(Fraction(value))
    if letter is None:
        return (f"{mag.numerator}" if mag.denominator == 1
                else f"{mag.numerator}/{mag.denominator}")
    head = letter if mag.numerator == 1 else f"{mag.numerator}{letter}"
    return head if mag.denominator == 1 else f"{head}/{mag.denominator}"


def _format_component(coeff, const: Fraction, letters: tuple[str, ...]) -> str:
    """The canonical printed form of one component; the inverse of the parser."""
    out = ""
    for value, letter in zip(coeff, letters):
        f = Fraction(value)
        if f == 0:
            continue
        sign = "-" if f < 0 else ("+" if out else "")
        out += f"{sign}{_format_rational(f, letter)}"
    c = Fraction(const)
    if c != 0 or not out:
        sign = "-" if c < 0 else ("+" if out else "")
        out += f"{sign}{_format_rational(c, None)}"
    return out


@dataclass(frozen=True)
class MagneticOperator:
    """One magnetic symmetry operation: (R, t, ε).

    ``rotation`` is an integer 3×3 acting on fractional coordinates,
    ``translation`` an exact rational 3-vector, ``time_reversal`` ε = ±1 with
    −1 marking an *antiunitary* (primed) operation.  The magCIF string form is
    ``-x,y+1/2,-z,-1`` (COMCIFS ``magnetic_dic``,
    ``_space_group_symop_magn_operation.xyz``, whose own examples are
    ``x+1/2,y+1/2,z,-1`` and ``-y,x,z+1/2,+1``).

    The coordinate action is x → R·x + t.  The **moment** action is
    ε·det(R)·R with R untransposed (:meth:`moment_matrix`), because a moment is
    an axial vector; see the module docstring for why a dimension count cannot
    check that.
    """

    rotation: tuple[tuple[int, int, int], ...]
    translation: tuple[Fraction, Fraction, Fraction]
    time_reversal: int

    def __post_init__(self) -> None:
        if self.time_reversal not in (1, -1):
            raise ValueError(
                f"time reversal is +1 or -1, not {self.time_reversal!r}; "
                f"magCIF writes it as the fourth field of the xyz string")

    # -- construction ----------------------------------------------------
    @classmethod
    def build(cls, rotation, translation, time_reversal: int
              ) -> MagneticOperator:
        """From anything array-like, with the translation reduced mod 1."""
        r = np.asarray(rotation)
        rot = tuple(tuple(int(round(float(r[i][j]))) for j in range(3))
                    for i in range(3))
        if not np.allclose(np.asarray(rot, dtype=float), r.astype(float),
                           atol=1e-9):
            raise ValueError(f"rotation part is not integral:\n{r}")
        tran = tuple(_as_fraction(v) % 1 for v in np.asarray(translation).ravel())
        return cls(rot, tran, int(time_reversal))

    @classmethod
    def from_xyz(cls, text: str) -> MagneticOperator:
        """Parse a magCIF ``x,y,z,±1`` operation string.

        The time-reversal field is **required**: a three-field string is an
        ordinary space-group operation and saying so is the caller's job, not
        this parser's guess.
        """
        parts = [p.strip() for p in str(text).split(",")]
        if len(parts) != 4:
            raise ValueError(
                f"magnetic operation {text!r} has {len(parts)} comma-separated "
                f"fields; magCIF gives four — three coordinates and the "
                f"time-reversal sign, e.g. '-x,y+1/2,-z,-1'")
        rows, tran = [], []
        for part in parts[:3]:
            coeff, const = _parse_component(part, _AXES)
            if any(c.denominator != 1 for c in coeff):
                raise ValueError(f"non-integral rotation coefficient in {text!r}")
            rows.append(tuple(int(c) for c in coeff))
            tran.append(const % 1)
        eps = parts[3]
        if eps not in ("+1", "1", "-1"):
            raise ValueError(
                f"time-reversal field of {text!r} is {eps!r}; magCIF writes "
                f"'+1' for an ordinary operation and '-1' for a time-reversed one")
        return cls(tuple(rows), tuple(tran), -1 if eps == "-1" else 1)

    # -- rendering -------------------------------------------------------
    def xyz(self) -> str:
        """The canonical magCIF string.  ``from_xyz(op.xyz()) == op``."""
        body = ",".join(_format_component(self.rotation[i], self.translation[i],
                                          _AXES) for i in range(3))
        return f"{body},{'+1' if self.time_reversal > 0 else '-1'}"

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.xyz()

    # -- algebra ---------------------------------------------------------
    @property
    def matrix(self) -> np.ndarray:
        """The rotation part as an ``(3, 3)`` int64 array."""
        return np.asarray(self.rotation, dtype=np.int64)

    @property
    def determinant(self) -> int:
        """det(R) — +1 for a proper rotation, −1 for an improper one.

        Expanded in integer arithmetic rather than through ``numpy.linalg.det``:
        the value decides a *sign* in :meth:`moment_matrix`, and a float
        determinant of an integer matrix is a rounding question nobody should
        have to ask.
        """
        r = self.rotation
        return (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
                - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
                + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))

    @property
    def is_translation(self) -> bool:
        """True for a (anti)centring: the rotation part is the identity."""
        return self.rotation == ((1, 0, 0), (0, 1, 0), (0, 0, 1))

    def __mul__(self, other: MagneticOperator) -> MagneticOperator:
        """Composition: ``(self * other)`` applies ``other`` first.

        Integer/``Fraction`` arithmetic throughout and no ``build`` call: the
        closure check runs |G|² of these over all 1651 groups, and going
        through numpy for a 3×3 integer product costs more than the whole rest
        of the check.
        """
        a, b, u, v = self.rotation, other.rotation, self.translation, \
            other.translation
        rot = tuple(tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j]
                          + a[i][2] * b[2][j] for j in range(3))
                    for i in range(3))
        tran = tuple((a[i][0] * v[0] + a[i][1] * v[1] + a[i][2] * v[2] + u[i]) % 1
                     for i in range(3))
        return MagneticOperator(rot, tran,
                                self.time_reversal * other.time_reversal)

    def moment_matrix(self) -> np.ndarray:
        """ε·det(R)·R — the action on a moment, an **axial** vector.

        Halpern & Johnson (1939), *Phys. Rev.* **55**, 898 is where the axial
        character enters the magnetic structure factor; the ε factor is the
        magnetic group's own (Perez-Mato et al. 2015).  R is **not**
        transposed: see the module docstring.
        """
        return self.time_reversal * self.determinant * self.matrix

    def act_on_moment(self, moment) -> np.ndarray:
        """Image of a crystal-axis moment under this operation, in μ_B."""
        return self.moment_matrix() @ np.asarray(moment, dtype=np.float64)

    def act_on_site(self, xyz) -> np.ndarray:
        """Image of a fractional position, wrapped into [0, 1)."""
        t = np.array([float(v) for v in self.translation])
        return (self.matrix @ np.asarray(xyz, dtype=np.float64) + t) % 1.0

    def fixes_site(self, xyz, *, tol: float = SITE_TOL) -> bool:
        """Whether this operation maps the site onto itself modulo a lattice."""
        x = np.asarray(xyz, dtype=np.float64)
        t = np.array([float(v) for v in self.translation])
        d = self.matrix @ x + t - x
        return bool(np.all(np.abs(d - np.round(d)) <= tol))


IDENTITY = MagneticOperator(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                            (Fraction(0), Fraction(0), Fraction(0)), 1)
#: The pure time reversal 1'.  Its presence makes a group **grey** (type II),
#: which forbids every ordered moment.
TIME_REVERSAL = MagneticOperator(((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                                 (Fraction(0), Fraction(0), Fraction(0)), -1)


def _as_fraction(value) -> Fraction:
    """Exact Fraction from an int, a Fraction, or a float that is one."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, np.integer)):
        return Fraction(int(value))
    f = Fraction(float(value)).limit_denominator(24)
    if abs(float(f) - float(value)) > 1e-8:
        raise ValueError(
            f"translation component {value!r} is not a rational with a "
            f"denominator dividing 24; crystallographic translations are")
    return f


@dataclass(frozen=True)
class MagneticSpaceGroupId:
    """What spglib recognised an operator list as.

    ``uni_number`` is the 1-1651 sequential number of Campbell et al. (2022);
    ``bns_number`` and ``og_number`` the two settings' tabulated numbers;
    ``msg_type`` is 1-4 in the usual sense (I colourless, II grey, III
    equi-class, IV black-and-white lattice).
    """

    uni_number: int
    bns_number: str
    og_number: str
    litvin_number: int
    number: int
    msg_type: int


@functools.lru_cache(maxsize=1)
def _number_index() -> tuple[dict[str, int], dict[str, int]]:
    """BNS-number → UNI and OG-number → UNI, built from spglib's own table."""
    bns: dict[str, int] = {}
    og: dict[str, int] = {}
    for uni in range(1, N_MAGNETIC_SPACE_GROUPS + 1):
        t = spglib.get_magnetic_spacegroup_type(uni)
        bns[t.bns_number] = uni
        og[t.og_number] = uni
    return bns, og


@dataclass(frozen=True)
class MagneticGroup:
    """A magnetic space group as the two magCIF loops that state it.

    ``operations`` are coset representatives — the
    ``_space_group_symop_magn_operation.xyz`` loop — and ``centerings`` the
    (anti)centring translations of the
    ``_space_group_symop_magn_centering.xyz`` loop, identity included.  The
    group is the set of products, :meth:`all_operations`.

    ``setting`` records where the operators are expressed; ``uni_number`` and
    the two tabulated numbers are metadata, carried when the group came from
    the database and ``None`` when it came from a user's strings.
    """

    operations: tuple[MagneticOperator, ...]
    centerings: tuple[MagneticOperator, ...] = (IDENTITY,)
    setting: str = "as given"
    uni_number: int | None = None
    bns_number: str | None = None
    og_number: str | None = None
    _cache: dict = field(default_factory=dict, repr=False, compare=False)

    # -- construction ----------------------------------------------------
    @classmethod
    def from_operations(cls, operations, **meta) -> MagneticGroup:
        """Canonicalise a flat operation list into (centerings, cosets).

        Splits off the pure-translation subgroup — which is what magCIF's
        centring loop is — and keeps the first operation met in each of its
        cosets.  Raises ``ValueError`` naming the offending product when the
        list is not closed, when the identity is missing, or when the split
        does not reproduce the input set: those are the three ways a
        hand-written or transformed list stops being a group.
        """
        ops = tuple(dict.fromkeys(operations))          # order-preserving dedup
        if IDENTITY not in ops:
            raise ValueError(
                "the operation list has no identity 'x,y,z,+1'; a magnetic "
                "space group is a group and every magCIF list states it")
        gap = _closure_gap(ops)
        if gap is not None:
            a, b = gap
            raise ValueError(
                f"the operation list is not closed: {a.xyz()!r} * {b.xyz()!r} "
                f"= {(a * b).xyz()!r}, which is not in it. A magnetic space "
                f"group must contain every product; check for a missing centring")
        seen = set(ops)
        centerings = tuple(op for op in ops if op.is_translation)
        reps: list[MagneticOperator] = []
        covered: set[MagneticOperator] = set()
        for op in ops:
            if op in covered:
                continue
            reps.append(op)
            covered.update(op * c for c in centerings)
        if covered != seen:
            raise ValueError(
                "the operation list does not split into centrings times coset "
                "representatives; it is not a union of cosets of its own "
                "translation subgroup")
        return cls(tuple(reps), centerings, **meta)

    @classmethod
    def from_xyz(cls, operations, centerings=None, **meta) -> MagneticGroup:
        """From magCIF strings: the operation loop and the centring loop.

        ``centerings`` may be omitted, in which case the operation list is
        taken to be the whole group (which is how a magCIF without a centring
        loop states one).
        """
        ops = [MagneticOperator.from_xyz(s) for s in operations]
        cent = ([MagneticOperator.from_xyz(s) for s in centerings]
                if centerings is not None else [IDENTITY])
        for c in cent:
            if not c.is_translation:
                raise ValueError(
                    f"{c.xyz()!r} is in the centring loop but its rotation part "
                    f"is not the identity; magCIF requires that of "
                    f"_space_group_symop_magn_centering.xyz")
        return cls.from_operations([c * o for o in ops for c in cent], **meta)

    # -- the group itself ------------------------------------------------
    def all_operations(self) -> tuple[MagneticOperator, ...]:
        """Every operation of the group: centrings times coset representatives."""
        if "all" not in self._cache:
            self._cache["all"] = tuple(dict.fromkeys(
                c * o for o in self.operations for c in self.centerings))
        return self._cache["all"]

    @property
    def order(self) -> int:
        """|G| in the cell the operators are expressed in."""
        return len(self.all_operations())

    @property
    def is_grey(self) -> bool:
        """Whether 1' is in the group (a type II, paramagnetic, group)."""
        return TIME_REVERSAL in self.all_operations()

    def xyz_strings(self) -> tuple[tuple[str, ...], tuple[str, ...]]:
        """The two magCIF loops, ``(operation.xyz, centering.xyz)``."""
        return (tuple(op.xyz() for op in self.operations),
                tuple(op.xyz() for op in self.centerings))

    # -- settings --------------------------------------------------------
    def transformed(self, transform, origin_shift=None) -> MagneticGroup:
        """This group re-expressed in another setting.

        ``transform`` is (P, p) in the sense of magCIF's
        ``_space_group_magn.transform_BNS_Pp_abc``: the basis vectors and
        origin of the **current** setting carried to those of the BNS setting,
        (a', b', c') = (a, b, c)·P with the shift p in the current setting's
        lattice coordinates.  This method goes the way a caller needs — it
        takes a group given in the *BNS* setting and returns it in the setting
        that tag describes — so it is the inverse map: W → P·W·P⁻¹,
        w → P·w + (I − P·W·P⁻¹)·p.

        The lattice is completed as well as conjugated.  When |det P| ≠ 1 the
        two cells hold different numbers of lattice points, so the images of
        the new basis vectors are added to the centring group and the coset
        representatives are re-derived; without that step the result is a
        *subgroup* wearing the right symbol, and its site multiplicities are
        wrong.  Raises ``ValueError`` if any conjugated rotation is not
        integral (the transform does not map this group's lattice to a
        lattice) or if the current cell is not a cell of the group.
        """
        p_matrix, shift = (parse_transform(transform)
                           if isinstance(transform, str)
                           else (_rational_matrix(transform),
                                 _rational_vector(origin_shift
                                                  if origin_shift is not None
                                                  else (0, 0, 0))))
        inv = _rational_inverse(p_matrix)
        moved: list[MagneticOperator] = []
        for op in self.all_operations():
            w = [[Fraction(int(v)) for v in row] for row in op.rotation]
            conj = _matmul(_matmul(p_matrix, w), inv)
            if any(v.denominator != 1 for row in conj for v in row):
                raise ValueError(
                    f"transform {format_transform(p_matrix, shift)!r} sends "
                    f"{op.xyz()!r} to a non-integral rotation; it does not map "
                    f"this group's lattice onto a lattice")
            tran = _matvec(p_matrix, list(op.translation))
            back = _matvec([[c - (i == j) for j, c in enumerate(row)]
                            for i, row in enumerate(conj)], list(shift))
            moved.append(MagneticOperator.build(
                [[int(v) for v in row] for row in conj],
                [tran[i] - back[i] for i in range(3)], op.time_reversal))
        # the new cell may hold lattice points the old one did not: the images
        # of the *old* basis vectors are translations of the group, and modulo
        # the new cell they are the extra centrings
        extra = [MagneticOperator.build(np.eye(3, dtype=int),
                                        [p_matrix[i][j] for i in range(3)], 1)
                 for j in range(3)]
        out = MagneticGroup.from_operations(
            _close(moved + extra),
            setting=f"transformed by {format_transform(p_matrix, shift)}",
            uni_number=self.uni_number, bns_number=self.bns_number,
            og_number=self.og_number)
        # |G| scales with the cell volume, so the two orders pin each other:
        # too few means the lattice was conjugated but not completed, too many
        # means the new cell is not a cell of this group at all (its basis
        # vectors are not lattice vectors), and both are silent otherwise
        det = abs(_rational_determinant(p_matrix))
        if out.order * det != self.order:
            raise ValueError(
                f"transform {format_transform(p_matrix, shift)!r} gives "
                f"{out.order} operations where |det P| = {det} demands "
                f"{Fraction(self.order) / det}; the target cell is not a cell "
                f"of this group")
        return out

    # -- sites and moments ------------------------------------------------
    def site_stabilizer(self, xyz, *, tol: float = SITE_TOL
                        ) -> tuple[MagneticOperator, ...]:
        """Every operation of the group that maps this site onto itself.

        The site-symmetry group of x, with the time-reversal signs kept — those
        are what turns the ordinary stabiliser into the magnetic one, and what
        makes a grey group forbid a moment everywhere.
        """
        return tuple(op for op in self.all_operations()
                     if op.fixes_site(xyz, tol=tol))

    def site_orbit(self, xyz, moment=None, *, tol: float = SITE_TOL):
        """Distinct images of a site, and of a moment carried on it.

        Returns ``(positions, moments)`` with ``moments`` ``None`` when no
        moment was given.  Raises ``ValueError`` naming the site when two
        operations reach the same image with **different** moments — which is
        exactly what a moment outside the allowed subspace does, and is the
        cheapest test that a stated structure is consistent with its own
        symmetry.
        """
        positions: list[np.ndarray] = []
        moments: list[np.ndarray] = []
        m = None if moment is None else np.asarray(moment, dtype=np.float64)
        for op in self.all_operations():
            p = op.act_on_site(xyz)
            mm = None if m is None else op.act_on_moment(m)
            for q, w in zip(positions, moments if m is not None
                            else [None] * len(positions)):
                d = np.abs(p - q)
                if np.all(np.minimum(d, 1.0 - d) <= tol):
                    if mm is not None and not np.allclose(w, mm, atol=1e-8):
                        raise ValueError(
                            f"moment {np.array2string(m, precision=4)} on site "
                            f"{np.array2string(np.asarray(xyz, dtype=float), precision=4)} "
                            f"is not consistent with this group: {op.xyz()!r} "
                            f"sends it to {np.array2string(mm, precision=4)} on "
                            f"an image that already carries "
                            f"{np.array2string(w, precision=4)}. The moment is "
                            f"outside the allowed subspace of the site")
                    break
            else:
                positions.append(p)
                if mm is not None:
                    moments.append(mm)
        return (np.asarray(positions),
                None if m is None else np.asarray(moments))

    def allowed_moment_basis(self, xyz, *, tol: float = SITE_TOL) -> np.ndarray:
        """Integer basis of the moments this group allows on a site, ``(k, 3)``.

        Rows are crystal-axis directions: m(θ) = Σₖ θₖ·rowₖ, in μ_B.  An empty
        ``(0, 3)`` array means the site carries no moment — which is what a grey
        group gives everywhere, and what a site on a 1'-type special position
        gives in any group.

        Same construction as :func:`~rietx.crystallography.wyckoff.adp_basis`
        one tensor rank down: the allowed patterns span ∩ ker(A(op) − I) over
        the site's stabiliser, with A the **axial** action ε·det(R)·R.
        """
        return allowed_moment_basis(self.site_stabilizer(xyz, tol=tol))

    # -- identification ---------------------------------------------------
    def identify(self, lattice=None, *, symprec: float = 1e-5
                 ) -> MagneticSpaceGroupId:
        """Which of the 1651 groups this is (spglib)."""
        return identify(self, lattice=lattice, symprec=symprec)


def allowed_moment_basis(operations, *, transpose: bool = False,
                         use_determinant: bool = True,
                         use_time_reversal: bool = True) -> np.ndarray:
    """Integer basis of the moments invariant under a set of operations.

    ``operations`` is the site's magnetic stabiliser.  A moment is an axial
    vector, so an operation acts on it as ε·det(R)·R (Halpern & Johnson, 1939,
    *Phys. Rev.* **55**, 898, for the axial character; Perez-Mato et al., 2015,
    *Annu. Rev. Mater. Res.* **45**, 217, for ε), and the allowed directions are
    the simultaneous fixed points, ∩ ker(ε·det(R)·R − I).  The algebra is exact
    over ``Fraction`` and the basis is the deterministic smallest-integer one
    ``wyckoff._nullspace_int`` returns, so a test may compare arrays exactly.

    The three keyword flags exist **only** so a test can build the wrong action
    on purpose and show that the span test catches it; nothing in the package
    calls them, and each defaults to the physics.  ``transpose=True`` is the
    Rᵀ trap, and it is invisible outside a trigonal or hexagonal setting.
    """
    rows: list[list[Fraction]] = []
    for op in operations:
        r = op.matrix
        a = (r.T if transpose else r)
        factor = 1
        if use_determinant:
            factor *= op.determinant
        if use_time_reversal:
            factor *= op.time_reversal
        a = factor * a
        for i in range(3):
            rows.append([Fraction(int(a[i][j]) - (i == j)) for j in range(3)])
    if not rows:
        return np.eye(3, dtype=np.int64)
    return _nullspace_int(rows, 3)


def in_span(basis: np.ndarray, vector, *, atol: float = 1e-6) -> bool:
    """Whether a moment lies in the span of a constraint basis.

    **The test to write, in place of a dimension count.**  A wrong symmetry
    action keeps the dimension of the allowed subspace right in every crystal
    system (root ``CLAUDE.md``, the Rᵀ trap; ``wyckoff.adp_basis`` and
    ``indexing.qspace.metric_basis`` carry the same warning), so only asking
    whether a *known* moment lies in the span can fail.
    """
    v = np.asarray(vector, dtype=np.float64).reshape(3)
    b = np.asarray(basis, dtype=np.float64).reshape(-1, 3)
    if len(b) == 0:
        return bool(np.all(np.abs(v) <= atol))
    coeff, *_ = np.linalg.lstsq(b.T, v, rcond=None)
    return bool(np.allclose(b.T @ coeff, v, atol=atol))


# ---------------------------------------------------------------------------
# the database
# ---------------------------------------------------------------------------
def magnetic_group(spec, *, hall_number: int = 0) -> MagneticGroup:
    """The magnetic space group named by a UNI, BNS or OG number.

    ``spec`` is a UNI number as an ``int`` (1-1651), or a number *string*: a
    BNS number ``"136.499"``, an OG number ``"136.7.1159"``, or a UNI number
    ``"1159"``.  A Shubnikov **symbol** is refused by name — spglib publishes
    no symbol table and guessing one is how a fit ends up under the wrong
    group.

    The operators come back in spglib's database setting, which is the **BNS**
    setting of Litvin's tables for the default ``hall_number``; an OG number
    resolves to the same group but *not* to OG-setting operators.
    :attr:`MagneticGroup.setting` records which it was.  Carry a file's own
    ``_space_group_magn.transform_BNS_Pp_abc`` through
    :meth:`MagneticGroup.transformed` to reach the setting a magCIF is written
    in.
    """
    uni = _resolve_uni(spec)
    data = spglib.get_magnetic_symmetry_from_database(uni, hall_number)
    if data is None:  # pragma: no cover - spglib returns None only on bad input
        raise ValueError(f"spglib has no magnetic space group for UNI {uni}")
    t = spglib.get_magnetic_spacegroup_type(uni)
    ops = [MagneticOperator.build(r, [Fraction(int(round(v * 24)), 24)
                                      for v in tr], -1 if e else 1)
           for r, tr, e in zip(data["rotations"], data["translations"],
                               data["time_reversals"])]
    setting = ("BNS standard setting (spglib magnetic database, "
               "Litvin 2013 tables)" if hall_number == 0
               else f"spglib magnetic database, Hall number {hall_number}")
    return MagneticGroup.from_operations(
        ops, setting=setting, uni_number=uni, bns_number=t.bns_number,
        og_number=t.og_number)


@functools.lru_cache(maxsize=1)
def _halls_by_number() -> dict[int, tuple[tuple[int, str, str], ...]]:
    """Space-group number → the Hall settings spglib's tables hold for it."""
    out: dict[int, list[tuple[int, str, str]]] = {}
    for hall in range(1, 531):
        t = spglib.get_spacegroup_type(hall)
        out.setdefault(int(t.number), []).append(
            (hall, str(t.international_short), str(t.choice)))
    return {k: tuple(v) for k, v in out.items()}


@dataclass(frozen=True)
class DatabaseSetting:
    """One setting spglib's magnetic database can serve a group in."""

    hall_number: int
    symbol: str
    choice: str
    is_default: bool


def database_settings(spec) -> tuple[DatabaseSetting, ...]:
    """Which settings :func:`magnetic_group` can produce this group in.

    The magnetic twin of :func:`~rietx.crystallography.symmetry.setting_alternatives`,
    and it exists for the same reason: **the default is a choice, and a
    published structure is often in the other one**.  Measured on
    Cd₂Os₂O₇ (BNS 227.131, Fd-3m'): spglib's default is origin choice 1, the
    published structure is origin choice 2, and the Os moment along [111] is
    *allowed* at (0,0,0) in choice 2 and **forbidden** there in choice 1 — the
    site symmetry is -3m in one and -43m in the other.  Nothing in the round
    trip catches that (spglib identifies its own output either way); only the
    moment does, which is why :meth:`MagneticGroup.site_orbit` raises rather
    than averaging when a moment does not fit its site.

    ``is_default`` marks the setting ``hall_number=0`` gives.
    """
    uni = _resolve_uni(spec)
    number = int(spglib.get_magnetic_spacegroup_type(uni).number)
    default = magnetic_group(uni).all_operations()
    out: list[DatabaseSetting] = []
    for hall, symbol, choice in _halls_by_number().get(number, ()):
        data = spglib.get_magnetic_symmetry_from_database(uni, hall)
        if data is None:
            continue
        same = set(magnetic_group(uni, hall_number=hall).all_operations()) == \
            set(default)
        out.append(DatabaseSetting(hall, symbol, choice, same))
    return tuple(out)


def _resolve_uni(spec) -> int:
    """UNI number from a UNI int, or a UNI/BNS/OG number string."""
    if isinstance(spec, (int, np.integer)) and not isinstance(spec, bool):
        uni = int(spec)
        if not 1 <= uni <= N_MAGNETIC_SPACE_GROUPS:
            raise ValueError(
                f"UNI number {uni} is outside 1-{N_MAGNETIC_SPACE_GROUPS}; "
                f"there are {N_MAGNETIC_SPACE_GROUPS} magnetic space groups")
        return uni
    text = str(spec).strip()
    if not re.fullmatch(r"\d+(\.\d+)*", text):
        raise ValueError(
            f"{text!r} is not a magnetic space-group number. This package takes "
            f"a UNI number (1-{N_MAGNETIC_SPACE_GROUPS}), a BNS number "
            f"('136.499') or an OG number ('136.7.1159'), never a Shubnikov "
            f"symbol: spglib publishes no symbol table, so a symbol cannot be "
            f"resolved here. Give the number, or give the operator list")
    bns, og = _number_index()
    dots = text.count(".")
    if dots == 1 and text in bns:
        return bns[text]
    if dots == 2 and text in og:
        return og[text]
    if dots == 0:
        return _resolve_uni(int(text))
    kind = {1: "BNS", 2: "OG"}.get(dots, "magnetic space-group")
    raise ValueError(f"{text!r} is not a {kind} number in spglib's table")


def identify(group, lattice=None, *, symprec: float = 1e-5
             ) -> MagneticSpaceGroupId:
    """Identify an operator list as one of the 1651 groups (spglib).

    ``group`` is a :class:`MagneticGroup` or any iterable of
    :class:`MagneticOperator`.  ``lattice`` (row vectors, Å) is the metric
    spglib measures ``symprec`` against; the default unit cell is fine for an
    exact operator list, which is what this module produces.

    Uses ``spglib.get_magnetic_spacegroup_type_from_symmetry``
    (Shinohara, Togo & Tanaka, 2023, *Acta Cryst.* A**79**, 390), so it needs no
    atomic configuration — the operators alone decide.  Raises ``ValueError``
    naming the group order when spglib does not match: on spglib 2.7.0 that
    happens for the database's own entries :data:`UNI_NOT_IDENTIFIABLE`, so a
    refusal here is not necessarily the caller's fault.
    """
    ops = (group.all_operations() if isinstance(group, MagneticGroup)
           else tuple(group))
    rotations = np.array([op.rotation for op in ops], dtype="intc")
    translations = np.array([[float(v) for v in op.translation] for op in ops],
                            dtype="double")
    time_reversals = np.array([op.time_reversal < 0 for op in ops], dtype="intc")
    t = spglib.get_magnetic_spacegroup_type_from_symmetry(
        rotations, translations, time_reversals,
        lattice=None if lattice is None else np.asarray(lattice, dtype="double"),
        symprec=symprec)
    if t is None:
        raise ValueError(
            f"spglib did not match this list of {len(ops)} operations to any of "
            f"the {N_MAGNETIC_SPACE_GROUPS} magnetic space groups. Either the "
            f"list is not a magnetic space group in a crystallographic setting, "
            f"or it is one of the database entries spglib cannot match to "
            f"itself (UNI {', '.join(map(str, UNI_NOT_IDENTIFIABLE))} on 2.7.0)")
    return MagneticSpaceGroupId(
        uni_number=int(t.uni_number), bns_number=str(t.bns_number),
        og_number=str(t.og_number), litvin_number=int(t.litvin_number),
        number=int(t.number), msg_type=int(t.type))


# ---------------------------------------------------------------------------
# the (P, p) transform string
# ---------------------------------------------------------------------------
def parse_transform(text: str):
    """``"-a/3-2b/3-2c/3,-a,a/3+2b/3-c/3;0,1/2,0"`` → (P, p), exactly.

    The magCIF ``_space_group_magn.transform_BNS_Pp_abc`` form (COMCIFS
    ``magnetic_dic``; the Jones-faithful notation of coreCIF's
    ``_space_group.transform_Pp_abc`` with the point and translation parts
    separated by a semicolon).  The three comma-separated expressions before
    the semicolon are the **new** basis vectors as combinations of the current
    ones, so they are the *columns* of P; the three after it are the origin
    shift in the current setting's lattice coordinates.
    """
    raw = str(text).strip()
    if ";" not in raw:
        raise ValueError(
            f"transform {text!r} has no ';'; magCIF's transform_BNS_Pp_abc "
            f"separates the basis part from the origin shift with one, as in "
            f"'a,b,c;0,0,0'")
    basis, shift = raw.split(";", 1)
    cols = [p.strip() for p in basis.split(",")]
    offs = [p.strip() for p in shift.split(",")]
    if len(cols) != 3 or len(offs) != 3:
        raise ValueError(
            f"transform {text!r} needs three basis expressions and three "
            f"origin components, got {len(cols)} and {len(offs)}")
    p_matrix = [[Fraction(0)] * 3 for _ in range(3)]
    for j, col in enumerate(cols):
        coeff, const = _parse_component(col, _ABC)
        if const != 0:
            raise ValueError(
                f"basis expression {col!r} in {text!r} carries a constant; a "
                f"basis vector is a combination of a, b and c only")
        for i in range(3):
            p_matrix[i][j] = coeff[i]
    origin: list[Fraction] = []
    for o in offs:
        coeff, const = _parse_component(o, _ABC)
        if any(c != 0 for c in coeff):
            raise ValueError(
                f"origin component {o!r} in {text!r} mentions a basis vector; "
                f"an origin shift is three numbers")
        origin.append(const)
    if _rational_determinant(p_matrix) == 0:
        raise ValueError(f"transform {text!r} is singular: |P| = 0")
    return p_matrix, tuple(origin)


def format_transform(p_matrix, origin) -> str:
    """The inverse of :func:`parse_transform`; ``parse(format(P, p))`` is (P, p)."""
    cols = [_format_component([p_matrix[i][j] for i in range(3)], Fraction(0),
                              _ABC) for j in range(3)]
    offs = [_format_component([Fraction(0)] * 3, Fraction(v), _ABC)
            for v in origin]
    return f"{','.join(cols)};{','.join(offs)}"


# ---------------------------------------------------------------------------
# moments: crystal axes ⇄ Cartesian
# ---------------------------------------------------------------------------
def _crystalaxis_to_cartesian_matrix(cell) -> np.ndarray:
    """M·N, the matrix taking crystal-axis moment components to Cartesian Å-free."""
    a, b, c = float(cell[0]), float(cell[1]), float(cell[2])
    return cartesian_basis(*cell) @ np.diag([1.0 / a, 1.0 / b, 1.0 / c])


def moment_to_cartesian(moment, cell) -> np.ndarray:
    """Crystal-axis moment components (μ_B) → Cartesian components (μ_B).

    The magCIF ``_atom_site_moment.crystalaxis_*`` basis is "a right-handed
    basis of **unit vectors** parallel to the unit-cell basis vectors"
    (COMCIFS ``magnetic_dic``), so the conversion is the direct-lattice matrix
    with each column normalised: m_cart = (a/|a|, b/|b|, c/|c|)·m.  The
    Cartesian frame is ``adp.cartesian_basis``'s, the same Cholesky convention
    the ADP code uses, and the orientation cancels in every reported quantity.

    This is the conversion the magnetic structure factor needs (decision D-3:
    crystal axes stored, Cartesian for the physics).
    """
    return _crystalaxis_to_cartesian_matrix(cell) @ np.asarray(
        moment, dtype=np.float64)


def moment_from_cartesian(moment, cell) -> np.ndarray:
    """Cartesian moment components (μ_B) → crystal-axis components (μ_B)."""
    return np.linalg.solve(_crystalaxis_to_cartesian_matrix(cell),
                           np.asarray(moment, dtype=np.float64))


def moment_magnitude(moment, cell) -> float:
    """|m| in μ_B from crystal-axis components — **not** √(Σmᵢ²).

    The crystal-axis basis is oblique whenever the cell is, so the magnitude is
    √(mᵀ·G·m) with G the *unit-vector* metric — ones on the diagonal, cos γ,
    cos β, cos α off it — exactly as the COMCIFS ``magnetic_dic`` definition of
    ``_atom_site_moment.crystalaxis`` states it.  On a hexagonal cell a moment
    (1, 1, 0) is 1 μ_B, not √2.
    """
    a, b, c = float(cell[0]), float(cell[1]), float(cell[2])
    g = direct_metric_tensor(*cell) / np.outer([a, b, c], [a, b, c])
    m = np.asarray(moment, dtype=np.float64)
    return float(np.sqrt(m @ g @ m))


# ---------------------------------------------------------------------------
# exact rational helpers (kept local; the package's only other exact-linear-
# algebra kernel is wyckoff._nullspace_int, which this module reuses)
# ---------------------------------------------------------------------------
def _rational_matrix(values) -> list[list[Fraction]]:
    rows = [[Fraction(v) if not isinstance(v, float) else _as_fraction(v)
             for v in row] for row in values]
    if len(rows) != 3 or any(len(r) != 3 for r in rows):
        raise ValueError("a basis transform is a 3×3 matrix")
    return rows


def _rational_vector(values) -> tuple[Fraction, Fraction, Fraction]:
    v = tuple(Fraction(x) if not isinstance(x, float) else _as_fraction(x)
              for x in values)
    if len(v) != 3:
        raise ValueError("an origin shift is three components")
    return v


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)]
            for i in range(3)]


def _matvec(a, v):
    return [sum(a[i][k] * v[k] for k in range(3)) for i in range(3)]


def _rational_determinant(m) -> Fraction:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _rational_inverse(m):
    det = _rational_determinant(m)
    if det == 0:
        raise ValueError("singular basis transform")
    cof = [[Fraction(0)] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            minor = [[m[r][c] for c in range(3) if c != j]
                     for r in range(3) if r != i]
            sign = -1 if (i + j) % 2 else 1
            cof[j][i] = sign * (minor[0][0] * minor[1][1]
                                - minor[0][1] * minor[1][0]) / det
    return cof


#: Largest code an int64 mixed-radix key may reach before :func:`_closure_gap`
#: gives up on the vectorised form.  2⁶² leaves a factor of two of headroom
#: under int64, and every crystallographic case is ~10⁹.
_MAX_CODE = 1 << 62


def _closure_gap(ops):
    """The first pair whose product is missing from ``ops``, or ``None``.

    The whole |G|² product table at once, as int64 mixed-radix codes.  The
    obvious ``for a in ops: for b in ops:`` form is the same check and costs
    34 s over the 1651-group database against 1.4 s for this one — the
    closure guard runs on every group this module builds, so it has to be the
    cheap kind of guard.
    """
    n = len(ops)
    rot = np.array([op.rotation for op in ops], dtype=np.int64)
    den = 1
    for op in ops:
        for t in op.translation:
            den = lcm(den, t.denominator)
    tran = np.array([[int(t * den) for t in op.translation] for op in ops],
                    dtype=np.int64)
    eps = np.array([op.time_reversal for op in ops], dtype=np.int64)

    prod_rot = np.einsum("aik,bkj->abij", rot, rot).reshape(n * n, 9)
    prod_tran = ((np.einsum("aik,bk->abi", rot, tran) + tran[:, None, :])
                 % den).reshape(n * n, 3)
    prod_eps = (eps[:, None] * eps[None, :]).ravel()

    base = int(max(np.abs(prod_rot).max(initial=1), np.abs(rot).max(initial=1)))
    if (2 * base + 1) ** 9 * den ** 3 * 2 >= _MAX_CODE:  # pragma: no cover
        have = {(op.rotation, op.translation, op.time_reversal) for op in ops}
        for i, a in enumerate(ops):
            for b in ops:
                p = a * b
                if (p.rotation, p.translation, p.time_reversal) not in have:
                    return a, b
        return None

    def code(r9, t3, e):
        out = np.zeros(len(r9), dtype=np.int64)
        for j in range(9):
            out = out * (2 * base + 1) + (r9[:, j] + base)
        for j in range(3):
            out = out * den + t3[:, j]
        return out * 2 + (e > 0)

    have = code(rot.reshape(n, 9), tran, eps)
    missing = ~np.isin(code(prod_rot, prod_tran, prod_eps), have)
    if not missing.any():
        return None
    k = int(np.argmax(missing))
    return ops[k // n], ops[k % n]


def _close(operations, *, limit: int = 4096) -> list[MagneticOperator]:
    """Close a set of operations under composition, modulo lattice translations."""
    found = list(dict.fromkeys(operations))
    if IDENTITY not in found:
        found.insert(0, IDENTITY)
    seen = set(found)
    frontier = list(found)
    while frontier:
        new: list[MagneticOperator] = []
        for a in frontier:
            for b in found:
                for prod in (a * b, b * a):
                    if prod not in seen:
                        seen.add(prod)
                        new.append(prod)
        found.extend(new)
        if len(found) > limit:
            raise ValueError(
                f"closing this operation set passed {limit} operations; the "
                f"input is not a magnetic space group in this cell")
        frontier = new
    return found
