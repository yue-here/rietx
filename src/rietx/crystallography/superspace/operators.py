"""(3+1)-dimensional superspace operators and groups: the algebra, nothing else.

A one-dimensionally modulated crystal is periodic in a four-dimensional
superspace, and its symmetry is a (3+1)D superspace group (de Wolff, Janssen &
Janner, 1981, *Acta Cryst.* A**37**, 625).  This module carries one operation
of such a group and a group as the list of its operations.  It knows nothing
about atoms, modulation functions, structure factors or satellites: those are
later work packages, and an operator list is what all of them consume.

The coordinates and the matrix
------------------------------
Everything here is in the **lattice basis of Stokes, Campbell & van Smaalen
(2011)**, *Acta Cryst.* A**67**, 45, § 2: three external coordinates x and one
internal coordinate x₄ such that the superspace lattice is ℤ⁴ (plus any
centring vectors), with x₄ the *argument of the modulation function*,
x₄ = q·x + t for the section t.  An operation is the augmented matrix of their
eq. (1),

    A(g) = [[R, 0, v],
            [M, ε, δ],
            [0, 0, 1]],

R the 3×3 integer point operation, v its translation, ε = ±1 the action on
the internal axis, M the integer row of eq. (2), **qR = εq + M**, and δ the
internal translation.  The equivalent statements are de Wolff (1981) eq. (3.4)
(εq − qR a reciprocal-lattice vector), Perez-Mato, Ribeiro, Petříček & Aroyo
(2012), *J. Phys.: Condens. Matter* **24**, 163201, eqs (4) and (8)
(R_s = [[R, 0], [H_R, R_I]], H_R = M) and Petříček, Fuksa & Dušek (2010),
*Acta Cryst.* A**66**, 649, eq. (12).

Two consequences of using x₄ rather than the section phase t:

* **A lattice translation n does not touch x₄** (the lattice is ℤ⁴), so an
  operation is reduced modulo 1 in all four translation components
  independently.  In the phase t the same translation reads t′ = t − q·n
  (de Wolff 1981 eq. (4.2)); the two descriptions are one affine change apart.
* **The section phase moves as t′ = εt + δ − q·v** (de Wolff 1981 eq. (3.2),
  t′ = εt + δ − q·s).  :meth:`SuperspaceOperator.internal_shift` returns
  δ − q·v for a rational q.

Composition is the matrix product (Stokes 2011 eqs (3)-(8)):
R_c = R_aR_b, ε_c = ε_aε_b, M_c = M_aR_b + ε_aM_b, v_c = R_av_b + v_a and
**δ_c = M_a·v_b + ε_aδ_b + δ_a**, the last being the only one with content.

What a group is here
--------------------
A :class:`SuperspaceGroup` is its modulation vector, one operation per point
operation of the basic space group (coset representatives) and its centring
translations, which may carry an internal component (the "supercentred"
lattices of Stokes 2011 § 3; Yamamoto, Janssen, Janner & de Wolff, 1985,
*Acta Cryst.* A**41**, 528, § 2).  **The operator list is the primary datum**:
a superspace-group symbol is unique only together with its q and its
reflection conditions (Yamamoto et al. 1985 §§ 2-3), so groups are compared as
operator lists under equivalence (:mod:`.generation`), never as strings — van
Smaalen, Campbell & Stokes (2013), *Acta Cryst.* A**69**, 75, conclusions.

The modulation vector is a *family*: q = q_r + Σ λ_j f_j with q_r an exact
rational vector and the λ_j free (incommensurate) parameters along integer
directions f_j (de Wolff 1981 eqs (3.5)-(3.6)).  An operation must map every
member of the family to ±itself modulo the reciprocal lattice, which holds
exactly when f_jR = εf_j for every free direction and M = q_rR − εq_r.

Time reversal (magnetic superspace groups)
------------------------------------------
An operation carries θ = ±1, −1 for time reversal (1′), as the fifth field of
the magCIF form ``x1,x2,x3,x4,-1`` (Perez-Mato, Ribeiro, Petříček & Aroyo
2012 eq. (3); Petříček et al. 2010 eq. (1)).  θ composes as θ₁θ₂ (Perez-Mato
2012 eq. (9)) and acts on nothing in superspace: it is a sign on time-odd
quantities, so a moment transforms as θ det(R) R and a displacement as R
(Petříček et al. 2010 eq. (2); Perez-Mato 2012 eqs (6)-(7)).  Every nuclear
operation has θ = +1, which is the default, so a non-magnetic group is the
θ = +1 case of the same object.  Pure time reversal and the anti-translations
{1′|v} (Stokes & Campbell 2022 types 2 and 4) have the identity rotation and
are carried among a group's *centrings*, as the magCIF centring loop carries
them; {1′|0000} and {1′|000½} are distinct operations (Perez-Mato 2012 p. 17).

Not built here, refused by name
-------------------------------
* **d > 1** (two or more modulation vectors): a fifth coordinate is refused.
* Atoms, waves, the structure factor and the satellite list (N-W3 onward).
"""

from __future__ import annotations

import functools
import re
from dataclasses import dataclass
from fractions import Fraction
from itertools import product
from math import lcm

import numpy as np

_IDENTITY_R = ((1, 0, 0), (0, 1, 0), (0, 0, 1))
_ZERO3 = (Fraction(0), Fraction(0), Fraction(0))

#: Coordinate letters accepted in an operation string: the msCIF/magCIF
#: ``x1,x2,x3,x4`` form and the Stokes ``x,y,z,t`` form.
_LETTERS = {"x1": 0, "x2": 1, "x3": 2, "x4": 3, "x": 0, "y": 1, "z": 2, "t": 3}
_TERM = re.compile(
    r"(?P<sign>[+-])?(?P<num>\d+)?(?:/(?P<den1>\d+))?"
    r"(?P<axis>x[1-9]\d*|[xyzt])?(?:/(?P<den2>\d+))?")

_REFUSE_D = (
    "superspace operations are built here for one modulation vector (d = 1) "
    "only; a fifth coordinate means d > 1, which is not implemented")
_THETA_FIELD = re.compile(r"^[+-]?\d+$")
_PRIMES = ("'", "′")


def as_fraction(value) -> Fraction:
    """Exact ``Fraction`` from an int, a ``Fraction``, a ``"1/2"`` string or a
    float that is a rational of denominator dividing 144."""
    if isinstance(value, Fraction):
        return value
    if isinstance(value, (int, np.integer)):
        return Fraction(int(value))
    if isinstance(value, str):
        return Fraction(value.strip())
    f = Fraction(float(value)).limit_denominator(144)
    if abs(float(f) - float(value)) > 1e-9:
        raise ValueError(
            f"{value!r} is not an exact rational; pass a Fraction or a "
            f"'p/q' string for a translation or a rational q component")
    return f


def _parse_affine(text: str) -> tuple[list[Fraction], Fraction]:
    """``x1-x4+1/2`` → ([1, 0, 0, -1], 1/2), exactly."""
    s = str(text).replace(" ", "").lower()
    if not s:
        raise ValueError("empty component in a superspace operation")
    coeff = [Fraction(0)] * 4
    const = Fraction(0)
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
                                 f"a number nor a coordinate")
            const += sign * Fraction(num, den)
            continue
        if axis not in _LETTERS:
            raise ValueError(f"{text!r} names coordinate {axis!r}: {_REFUSE_D}")
        coeff[_LETTERS[axis]] += sign * Fraction(num if num is not None else 1, den)
    return coeff, const


def _format_affine(coeff, const, letters=("x1", "x2", "x3", "x4")) -> str:
    out = ""
    for value, letter in zip(coeff, letters):
        f = Fraction(value)
        if f == 0:
            continue
        mag = abs(f)
        head = letter if mag == 1 else (
            f"{mag.numerator}{letter}" if mag.denominator == 1
            else f"{mag.numerator}{letter}/{mag.denominator}")
        out += ("-" if f < 0 else ("+" if out else "")) + head
    c = Fraction(const)
    if c != 0 or not out:
        mag = abs(c)
        txt = (f"{mag.numerator}" if mag.denominator == 1
               else f"{mag.numerator}/{mag.denominator}")
        out += ("-" if c < 0 else ("+" if out else "")) + txt
    return out


@dataclass(frozen=True)
class SuperspaceOperator:
    """One (3+1)D superspace operation (R, v; M, ε, δ), Stokes 2011 eq. (1).

    ``rotation`` R and ``m`` M are integers, ``translation`` v and ``delta``
    δ exact ``Fraction``s reduced to [0, 1) (the superspace lattice is ℤ⁴ in
    these coordinates; module docstring).  ``epsilon`` is ε = ±1, the action on
    the internal coordinate (de Wolff's ε, Perez-Mato's R_I).

    The string form is the msCIF/magCIF one, ``"-x1,x2,-x3+1/2,x1-x4+1/2"``:
    four components, the fourth carrying M as x1..x3 terms, ε as ±x4 and δ.

    ``theta`` is the time-reversal sign θ = ±1 (Perez-Mato et al. 2012
    eq. (3)), −1 for a primed operation; the magCIF string then carries it as
    a fifth field, ``"x1,x2,x3,x4+1/2,-1"``.  Its default +1 is the nuclear
    case, and every N-W1 caller leaves it there.  θ = −1 is set by three
    writers only: the string parser (:meth:`from_xyz`), :meth:`prime`, and
    the magnetic-group builders (:meth:`SuperspaceGroup.with_anti_translation`
    and :mod:`.magnetic`'s enumerator).
    """

    rotation: tuple[tuple[int, int, int], ...]
    translation: tuple[Fraction, Fraction, Fraction]
    epsilon: int
    m: tuple[int, int, int]
    delta: Fraction
    theta: int = 1

    def __post_init__(self) -> None:
        if self.epsilon not in (1, -1):
            raise ValueError(f"epsilon is +1 or -1, not {self.epsilon!r}")
        if self.theta not in (1, -1):
            raise ValueError(
                f"theta (the time-reversal sign) is +1 or -1, not {self.theta!r}")

    # -- construction ----------------------------------------------------
    @classmethod
    def build(cls, rotation, translation, epsilon: int = 1, m=(0, 0, 0),
              delta=0, theta: int = 1) -> SuperspaceOperator:
        """From anything array-like; translations reduced mod 1."""
        r = np.asarray(rotation)
        rot = tuple(tuple(int(round(float(r[i][j]))) for j in range(3))
                    for i in range(3))
        if not np.allclose(np.asarray(rot, dtype=float), r.astype(float)):
            raise ValueError(f"rotation part is not integral:\n{r}")
        mm = tuple(int(round(float(x))) for x in m)
        if not np.allclose(np.asarray(mm, dtype=float),
                           np.asarray(m, dtype=float)):
            raise ValueError(f"the M row {m!r} is not integral (Stokes 2011 eq. (2))")
        tran = tuple(as_fraction(x) % 1 for x in translation)
        return cls(rot, tran, int(epsilon), mm, as_fraction(delta) % 1, int(theta))

    @classmethod
    def from_xyz(cls, text: str) -> SuperspaceOperator:
        """Parse ``"x1,x2,x3,x4"``-style text (or ``x,y,z,t``).

        A fifth field that is an integer is the time-reversal sign θ, the
        magCIF ``_space_group_symop_magn_ssg_operation.algebraic`` form
        (``"x1,x2,x3,x4+1/2,-1"``); a trailing prime is the same thing in
        the notation of Stokes & Campbell (2022), *Acta Cryst.* A**78**, 364,
        Fig. 4 (``"(x+1/2,-y,-z,-t)'"``).  Refused by name: a θ other than
        ±1, and a fifth *coordinate* (d > 1).
        """
        s = str(text).strip()
        primed = s.endswith(_PRIMES)
        if primed:
            s = s[:-1].strip()
        if s.startswith("(") and s.endswith(")"):
            s = s[1:-1]
        parts = [p.strip() for p in s.split(",")]
        theta = -1 if primed else 1
        if len(parts) == 5 and _THETA_FIELD.match(parts[4].replace(" ", "")):
            value = int(parts[4])
            if value not in (1, -1):
                raise ValueError(
                    f"{text!r}: the time-reversal field is +1 or -1, not {value}")
            if primed:
                raise ValueError(f"{text!r} gives time reversal twice (a prime "
                                 f"and a fifth field)")
            theta = value
            parts = parts[:4]
        if len(parts) > 4:
            raise ValueError(f"{text!r} has {len(parts)} components: {_REFUSE_D}")
        if len(parts) != 4:
            raise ValueError(
                f"{text!r} has {len(parts)} components; a (3+1)D operation "
                f"has four, e.g. 'x1,-x2,x3+1/2,-x4'")
        rows, tran = [], []
        for part in parts[:3]:
            coeff, const = _parse_affine(part)
            if coeff[3] != 0:
                raise ValueError(
                    f"{text!r}: an external component depends on x4, which no "
                    f"superspace operation does (the upper-right block of "
                    f"Stokes 2011 eq. (1) is zero)")
            if any(c.denominator != 1 for c in coeff):
                raise ValueError(f"non-integral rotation coefficient in {text!r}")
            rows.append(tuple(int(c) for c in coeff[:3]))
            tran.append(const % 1)
        coeff, const = _parse_affine(parts[3])
        if any(c.denominator != 1 for c in coeff):
            raise ValueError(f"non-integral coefficient in the x4 component of {text!r}")
        if coeff[3] not in (1, -1):
            raise ValueError(
                f"{text!r}: the x4 component must carry x4 with coefficient "
                f"+1 or -1 (that is epsilon), found {coeff[3]}")
        return cls(tuple(rows), tuple(tran), int(coeff[3]),
                   tuple(int(c) for c in coeff[:3]), const % 1, theta)

    # -- rendering -------------------------------------------------------
    def xyz(self, magnetic: bool | None = None) -> str:
        """The canonical string; ``from_xyz(op.xyz()) == op``.

        The time-reversal field ``,+1``/``,-1`` is printed when ``magnetic``
        is true (every operation of a magnetic group, the magCIF form), never
        when it is false, and when it is ``None`` only for θ = −1, so a
        nuclear operation prints as N-W1 printed it.
        """
        if magnetic is False and self.theta == -1:
            raise ValueError("a primed operation has no non-magnetic string form")
        ext = [_format_affine(list(self.rotation[i]) + [0], self.translation[i])
               for i in range(3)]
        internal = _format_affine(list(self.m) + [self.epsilon], self.delta)
        out = ",".join(ext + [internal])
        if magnetic or (magnetic is None and self.theta == -1):
            out += ",+1" if self.theta == 1 else ",-1"
        return out

    def __str__(self) -> str:  # pragma: no cover - convenience
        return self.xyz()

    # -- algebra ---------------------------------------------------------
    @property
    def matrix(self) -> np.ndarray:
        """The 5×5 augmented matrix of Stokes 2011 eq. (1), as float."""
        a = np.zeros((5, 5))
        a[:3, :3] = self.rotation
        a[:3, 4] = [float(x) for x in self.translation]
        a[3, :3] = self.m
        a[3, 3] = self.epsilon
        a[3, 4] = float(self.delta)
        a[4, 4] = 1.0
        return a

    @property
    def is_translation(self) -> bool:
        """A lattice or centring translation: identity point part, θ = +1."""
        return (self.rotation == _IDENTITY_R and self.epsilon == 1
                and self.m == (0, 0, 0) and self.theta == 1)

    @property
    def is_anti_translation(self) -> bool:
        """{1′|v}: identity point part with time reversal (Stokes & Campbell
        2022 p. 366), {1′|0000} itself included."""
        return (self.rotation == _IDENTITY_R and self.epsilon == 1
                and self.m == (0, 0, 0) and self.theta == -1)

    def prime(self) -> SuperspaceOperator:
        """The same operation combined with time reversal: θ → −θ."""
        return SuperspaceOperator(self.rotation, self.translation, self.epsilon,
                                  self.m, self.delta, -self.theta)

    def unprimed(self) -> SuperspaceOperator:
        """The operation with θ = +1: Stokes & Campbell (2022)'s family
        function F applied to one operation (p. 365)."""
        if self.theta == 1:
            return self
        return SuperspaceOperator(self.rotation, self.translation, self.epsilon,
                                  self.m, self.delta, 1)

    @property
    def determinant(self) -> int:
        r = self.rotation
        return (r[0][0] * (r[1][1] * r[2][2] - r[1][2] * r[2][1])
                - r[0][1] * (r[1][0] * r[2][2] - r[1][2] * r[2][0])
                + r[0][2] * (r[1][0] * r[2][1] - r[1][1] * r[2][0]))

    def __mul__(self, other: SuperspaceOperator) -> SuperspaceOperator:
        """Composition: ``self * other`` applies ``other`` first.

        Stokes 2011 eqs (4)-(8), reduced mod 1.  δ_c = M_a·v_b + ε_aδ_b + δ_a is
        the product's internal translation; de Wolff 1981 § 6 writes the same
        rule in the intrinsic form τ₃ = τ₁ + ε₁τ₂.  θ_c = θ_aθ_b (Perez-Mato et
        al. 2012 eq. (9)).
        """
        a, b = self.rotation, other.rotation
        rot = tuple(tuple(a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j]
                          for j in range(3)) for i in range(3))
        v = other.translation
        tran = tuple((a[i][0] * v[0] + a[i][1] * v[1] + a[i][2] * v[2]
                      + self.translation[i]) % 1 for i in range(3))
        ma = self.m
        m = tuple(ma[0] * b[0][j] + ma[1] * b[1][j] + ma[2] * b[2][j]
                  + self.epsilon * other.m[j] for j in range(3))
        delta = (ma[0] * v[0] + ma[1] * v[1] + ma[2] * v[2]
                 + self.epsilon * other.delta + self.delta) % 1
        return SuperspaceOperator(rot, tran, self.epsilon * other.epsilon, m, delta,
                                  self.theta * other.theta)

    def inverse(self) -> SuperspaceOperator:
        """The inverse operation: R⁻¹, ε, M′ = −εMR⁻¹, v′ = −R⁻¹v,
        δ′ = −M′·v − εδ (the identity block of A(g)⁻¹A(g)), and the same θ.

        A(g) is the augmented matrix of Stokes, Campbell & van Smaalen
        (2011), *Acta Cryst.* A**67**, 45, eq. (1); the inverse is its matrix
        inverse, written out in the blocks of their eqs (3)-(8).
        """
        r = [[Fraction(x) for x in row] for row in self.rotation]
        inv = _inverse3(r)
        rinv = tuple(tuple(int(inv[i][j]) for j in range(3)) for i in range(3))
        if any(inv[i][j].denominator != 1 for i in range(3) for j in range(3)):
            raise ValueError("rotation part is not unimodular")
        e = self.epsilon
        m2 = tuple(-e * sum(self.m[k] * rinv[k][j] for k in range(3)) for j in range(3))
        v2 = tuple(-sum(rinv[i][k] * self.translation[k] for k in range(3))
                   for i in range(3))
        d2 = -sum(m2[k] * self.translation[k] for k in range(3)) - e * self.delta
        return SuperspaceOperator(rinv, tuple(x % 1 for x in v2), e, m2, d2 % 1,
                                  self.theta)

    def act(self, x, x4):
        """Image of the superspace point (x, x₄): (Rx + v, M·x + εx₄ + δ).

        The augmented matrix of Stokes, Campbell & van Smaalen (2011),
        *Acta Cryst.* A**67**, 45, eq. (1) applied to (x, x₄, 1).
        """
        xv = np.asarray(x, dtype=float)
        r = np.asarray(self.rotation, dtype=float)
        x_new = r @ xv + np.array([float(t) for t in self.translation])
        x4_new = float(np.dot(self.m, xv)) + self.epsilon * float(x4) + float(self.delta)
        return x_new, x4_new

    def internal_shift(self, q) -> Fraction:
        """δ − q·v: the section-phase increment, t′ = εt + δ − q·v (de Wolff
        1981 eq. (3.2)), for an exact rational q.  It depends on the lattice
        representative of v, which is the origin of symbol ambiguity
        (Yamamoto et al. 1985 § 3)."""
        qq = [as_fraction(c) for c in q]
        return self.delta - sum(qq[i] * self.translation[i] for i in range(3))

    def order(self) -> int:
        """Order of the point part (R, ε, θ): the smallest n with R^n = 1
        and θ^n = 1."""
        p = self
        for n in range(1, 13):
            if (p.rotation == _IDENTITY_R and p.epsilon == 1 and p.m == (0, 0, 0)
                    and p.theta == 1):
                return n
            p = p * self
        raise ValueError("point part has no finite order <= 12")

    def basic(self) -> tuple[tuple[tuple[int, ...], ...], tuple[Fraction, ...]]:
        """The basic-space-group operation (R, v): the external block."""
        return self.rotation, self.translation

    def harmonic_factor(self, n: int, *, kind: str) -> complex:
        """The factor this operation puts on the n-th harmonic of a
        modulation function at a site it leaves in place.

        Defined for an operation whose external part is the identity modulo
        the lattice (R = E, ε = +1, M = 0, v ∈ ℤ³): an internal translation
        or time reversal combined with one, such as {1′|000½}.  Such an
        operation maps the modulation function A(x₄) of every site onto
        Transf·A(x₄ − δ) (Perez-Mato et al. 2012 eqs (5)-(7)), so the
        coefficient T_n of exp(−2πi n x₄) is multiplied by
        Transf·exp(2πi n δ), and an invariant structure has T_n = 0 unless the
        factor is 1.  ``kind`` names Transf, with the vocabulary of
        :data:`rietx.crystallography.representation.order_parameter.ORDER_PARAMETER_KINDS`:
        ``"magnetic"`` (a moment, time-odd, θ det(R) R = θ) or
        ``"displacive"`` (a displacement, time-even, R = 1).  For {1′|000½}
        the factor is θ·e^{iπn} = −(−1)ⁿ on a moment and (−1)ⁿ on a
        displacement: only odd moment harmonics and even displacive ones
        survive (Perez-Mato 2012 p. 17; Petříček et al. 2010 § 4.2).
        """
        if kind not in ("magnetic", "displacive"):
            raise ValueError(f"kind is 'magnetic' or 'displacive', not {kind!r}")
        if not (self.rotation == _IDENTITY_R and self.epsilon == 1
                and self.m == (0, 0, 0) and all(t == 0 for t in self.translation)):
            raise ValueError(
                f"{self.xyz()!r} moves the site; the harmonic factor of a single "
                f"site is defined for an internal translation (R = E, ε = +1, "
                f"v ∈ ℤ³) only")
        sign = self.theta if kind == "magnetic" else 1
        phase = (int(n) * self.delta) % 1
        exact = {Fraction(0): 1 + 0j, Fraction(1, 2): -1 + 0j,
                 Fraction(1, 4): 1j, Fraction(3, 4): -1j}
        value = exact.get(phase)
        if value is None:
            value = complex(np.exp(2j * np.pi * float(phase)))
        return sign * value


IDENTITY = SuperspaceOperator(_IDENTITY_R, _ZERO3, 1, (0, 0, 0), Fraction(0))

#: {1′|0000}: pure time reversal, the operation that makes a group grey
#: (Stokes & Campbell 2022 type 2).
IDENTITY_PRIME = SuperspaceOperator(_IDENTITY_R, _ZERO3, 1, (0, 0, 0), Fraction(0), -1)


def _inverse3(m):
    det = (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
           - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
           + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))
    if det == 0:
        raise ValueError("singular 3x3 matrix")
    cof = [[Fraction(0)] * 3 for _ in range(3)]
    for i in range(3):
        for j in range(3):
            mi = [[m[r][c] for c in range(3) if c != j] for r in range(3) if r != i]
            cof[j][i] = (-1 if (i + j) % 2 else 1) * (
                mi[0][0] * mi[1][1] - mi[0][1] * mi[1][0]) / Fraction(det)
    return cof


# ---------------------------------------------------------------------------
# the modulation vector, as a family
# ---------------------------------------------------------------------------
_GREEK = ("α", "β", "γ")
_UNICODE_FRACTIONS = {"½": "1/2", "⅓": "1/3", "⅔": "2/3", "¼": "1/4", "¾": "3/4",
                      "⅙": "1/6", "⅚": "5/6"}
_PARAM_ALIASES = {"α": 0, "a": 0, "alpha": 0, "β": 1, "b": 1, "beta": 1,
                  "γ": 2, "g": 2, "gamma": 2}


@dataclass(frozen=True)
class ModulationVector:
    """q = q_r + Σ_j λ_j f_j: the rational part and the free directions.

    ``rational`` is q_r in the conventional reciprocal basis, exact.  ``free``
    is one integer direction per incommensurate parameter λ_j; the familiar
    spellings are one-hot, ``(0, 0, γ)`` being ``rational=(0,0,0)``,
    ``free=((0,0,1),)``.  Equality is literal (it compares the spelling), so
    ``(0,0,γ)`` and ``(0,0,1-γ)`` differ here and are compared as groups by
    :func:`~rietx.crystallography.superspace.generation.equivalent`.
    """

    rational: tuple[Fraction, Fraction, Fraction]
    free: tuple[tuple[int, int, int], ...]

    def __post_init__(self) -> None:
        if len(self.rational) != 3:
            raise ValueError("a modulation vector has three components")
        if not self.free:
            raise ValueError(
                "a superspace group needs at least one incommensurate "
                "component in q; a fully rational q is a commensurate "
                "*section* of a superspace group (SuperspaceGroup.section)")
        if len(self.free) > 3:
            raise ValueError("at most three free components")
        if np.linalg.matrix_rank(np.asarray(self.free, dtype=float)) != len(self.free):
            raise ValueError(f"the free directions {self.free} are not independent")

    @classmethod
    def parse(cls, text) -> ModulationVector:
        """``"(1/2,1/2,γ)"``, ``"0,0,g"``, ``"(1-γ,0,0)"``, ``"(α,β,0)"``.

        Each component is a rational plus ± one parameter letter; the letter
        names the parameter (α, β, γ or a, b, g), so ``"(α,α,0)"`` is one free
        direction (1, 1, 0).  Two vectors, ``"(...)(...)"``, are d = 2 and are
        refused.
        """
        if isinstance(text, ModulationVector):
            return text
        if not isinstance(text, str):
            return cls.from_components(text)
        s = text.strip()
        if s.count("(") > 1:
            raise ValueError(f"{text!r} gives more than one modulation vector: {_REFUSE_D}")
        s = s.strip("()")
        for k, v in _UNICODE_FRACTIONS.items():
            s = s.replace(k, v if "," in s else f"[{v}]")
        if "," in s:
            parts = [p.strip() for p in s.split(",")]
        else:
            # the compact ITC-C spelling, one token per component: "00γ", "½½γ"
            parts = re.findall(r"-?(?:\[[^\]]+\]|\d|[αβγabg])", s.replace(" ", ""))
            if "".join(parts) != s.replace(" ", ""):
                raise ValueError(f"cannot read {text!r} as three components; "
                                 f"separate them with commas")
            parts = [p.replace("[", "").replace("]", "") for p in parts]
        if len(parts) != 3:
            raise ValueError(f"{text!r}: a modulation vector has three components")
        rational: list[Fraction] = []
        coeffs: dict[int, list[int]] = {}
        for i, part in enumerate(parts):
            r, terms = _parse_q_component(part, text)
            rational.append(r)
            for name, c in terms:
                coeffs.setdefault(name, [0, 0, 0])[i] += c
        free = tuple(tuple(coeffs[k]) for k in sorted(coeffs))
        return cls(tuple(rational), free)

    @classmethod
    def from_components(cls, comps) -> ModulationVector:
        """From a 3-sequence of rationals and parameter letters,
        e.g. ``(Fraction(1, 2), 0, "γ")``."""
        return cls.parse("(" + ",".join(str(c) for c in comps) + ")")

    @property
    def dimension(self) -> int:
        """Number of free (incommensurate) parameters."""
        return len(self.free)

    def axis_aligned(self) -> bool:
        return all(sum(1 for x in f if x) == 1 for f in self.free)

    def label(self, ascii: bool = False) -> str:
        """``(1/2,1/2,γ)``; ``ascii=True`` spells the parameters a, b, g."""
        names = ("a", "b", "g") if ascii else _GREEK
        used = []
        for f in self.free:
            lead = next(i for i, x in enumerate(f) if x)
            used.append(lead)
        if len(set(used)) != len(used):
            used = list(range(len(self.free)))
        comps = []
        for i in range(3):
            r = self.rational[i]
            txt = "" if r == 0 else (f"{r.numerator}" if r.denominator == 1
                                     else f"{r.numerator}/{r.denominator}")
            for f, name_i in zip(self.free, used):
                c = f[i]
                if c == 0:
                    continue
                term = names[name_i] if abs(c) == 1 else f"{abs(c)}{names[name_i]}"
                txt += ("-" if c < 0 else ("+" if txt else "")) + term
            comps.append(txt or "0")
        return "(" + ",".join(comps) + ")"

    def value(self, *params) -> tuple[Fraction, Fraction, Fraction]:
        """The vector at given parameter values (exact for rational input)."""
        if len(params) != len(self.free):
            raise ValueError(f"{len(self.free)} parameter value(s) needed")
        out = list(self.rational)
        for lam, f in zip(params, self.free):
            lv = as_fraction(lam)
            for i in range(3):
                out[i] += lv * f[i]
        return tuple(out)

    def contains(self, q) -> tuple[Fraction, ...] | None:
        """Parameter values λ with q = q_r + Σλ_j f_j, or ``None``."""
        qq = [as_fraction(c) for c in q]
        d = [qq[i] - self.rational[i] for i in range(3)]
        k = len(self.free)
        rows = [[Fraction(self.free[j][i]) for j in range(k)] + [d[i]] for i in range(3)]
        sol = _solve_exact(rows, k)
        return None if sol is None else tuple(sol)


def line_rule(rotation, q: ModulationVector) -> tuple[int, tuple[Fraction, Fraction, Fraction]] | None:
    """The exact line rule: (ε, M) for a point operation R on the family q,
    or ``None`` when R does not map the family to ±itself.

    R keeps the line iff f R = ε f for every free direction f with one sign
    ε = ±1 (the λ_j are rationally independent, so each direction must map
    alone), and then **M = q_r R − ε q_r** exactly (row vectors, i.e. Rᵀ on
    a column k; Stokes, Campbell & van Smaalen 2011 eq. (2); de Wolff,
    Janssen & Janner 1981 eq. (3.4)).  Whether M is a reciprocal-lattice
    vector is the caller's test, because the lattice is: a superspace
    operation carries M as its integer row (:meth:`SuperspaceGroup._check_q`),
    the little group of a line point asks M ∈ L* with the centrings
    (:func:`rietx.crystallography.representation.irreps.little_group_on_line`).
    One criterion read by both, never restated.
    """
    r = rotation
    eps = None
    for f in q.free:
        fr = tuple(sum(f[i] * r[i][j] for i in range(3)) for j in range(3))
        if fr == tuple(f):
            e = 1
        elif fr == tuple(-x for x in f):
            e = -1
        else:
            return None
        if eps is not None and e != eps:
            return None
        eps = e
    qr = q.rational
    m = tuple(sum(qr[i] * int(r[i][j]) for i in range(3)) - eps * qr[j] for j in range(3))
    return eps, m


def _parse_q_component(part: str, whole: str) -> tuple[Fraction, list[tuple[int, int]]]:
    s = part.replace(" ", "").replace("−", "-")
    if not s:
        raise ValueError(f"empty component in {whole!r}")
    toks = re.findall(r"[+-]?[^+-]+", s)
    r = Fraction(0)
    terms: list[tuple[int, int]] = []
    for tok in toks:
        sign = -1 if tok.startswith("-") else 1
        body = tok.lstrip("+-")
        m = re.fullmatch(r"(\d*)(α|β|γ|alpha|beta|gamma|a|b|g)", body)
        if m:
            c = int(m.group(1)) if m.group(1) else 1
            terms.append((_PARAM_ALIASES[m.group(2)], sign * c))
            continue
        try:
            r += sign * Fraction(body)
        except ValueError:
            raise ValueError(f"cannot read the q component {part!r} of {whole!r}") from None
    return r, terms


def _solve_exact(rows, k):
    """Solve an overdetermined rational system [A | b] (rows) for k unknowns,
    returning the unique solution or ``None`` if inconsistent."""
    m = [r[:] for r in rows]
    piv_cols = []
    rr = 0
    for c in range(k):
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
        piv_cols.append(c)
        rr += 1
    if any(all(x == 0 for x in row[:k]) and row[k] != 0 for row in m):
        return None
    if len(piv_cols) < k:
        return None
    sol = [Fraction(0)] * k
    for i, c in enumerate(piv_cols):
        sol[c] = m[i][k]
    return sol


# ---------------------------------------------------------------------------
# the group
# ---------------------------------------------------------------------------
def _rkey(r) -> tuple:
    return tuple(x for row in r for x in row)


@dataclass(frozen=True)
class SuperspaceGroup:
    """A (3+1)D superspace group: q, coset representatives, centrings.

    ``operations`` has one operation per point operation (R, ε) of the group,
    identity first; ``centerings`` are its pure translations modulo ℤ⁴,
    identity included, and may carry an internal component.  Construction
    validates the group: every operation is consistent with q (fR = εf on each
    free direction, M = q_rR − εq_r), the centrings are translations, and the
    set closes under composition modulo the lattice.

    ``symbol`` and ``number`` are labels only; nothing reads them back.
    ``number`` has one writer, the caller: :meth:`from_operations` (or the
    constructor) stores a four-part number (the numbering of Stokes, Campbell
    & van Smaalen (2011), *Acta Cryst.* A**67**, 45, p. 47) verbatim and
    unchecked.  Nothing in this package sets it — the generator does not
    reproduce that numbering (:func:`~.generation.superspace_groups`), and
    :func:`~.symbols.parse_symbol` and :meth:`transformed` leave it ``None`` —
    so ``None`` means "not given", never "not numbered".

    **Magnetic groups are the same class** (decision of WP-1992 commit A):
    an operation's θ is part of the operation, so a magnetic superspace group
    is a superspace group whose operator list carries θ = −1 somewhere, and
    :attr:`is_magnetic` and :attr:`magnetic_type` are *derived* from that list
    rather than declared beside it.  ``operations`` stays one per point
    operation R; the anti-translations {1′|v} — pure time reversal {1′|0000}
    included — have R = E and sit in ``centerings`` beside the translations,
    as magCIF's centring loop holds them, so (g, θ = +1) and (g, θ = −1)
    differ by a centring and the closure test compares θ.
    """

    q: ModulationVector
    operations: tuple[SuperspaceOperator, ...]
    centerings: tuple[SuperspaceOperator, ...] = (IDENTITY,)
    symbol: str | None = None
    number: str | None = None

    def __post_init__(self) -> None:
        ops = tuple(self.operations)
        if not ops:
            raise ValueError("a superspace group has at least the identity")
        cen = tuple(dict.fromkeys(self.centerings))
        if IDENTITY not in cen:
            cen = (IDENTITY,) + cen
        for c in cen:
            if not (c.is_translation or c.is_anti_translation):
                raise ValueError(f"centering {c.xyz()!r} is not a pure translation "
                                 f"or an anti-translation {{1'|v}}")
        object.__setattr__(self, "centerings", cen)
        keys = [(_rkey(o.rotation), o.epsilon) for o in ops]
        if len(set(_rkey(o.rotation) for o in ops)) != len(ops):
            raise ValueError("operations must be one per point operation R "
                             "(coset representatives modulo the lattice); an "
                             "operation present both with and without time "
                             "reversal means the group holds 1', which goes "
                             "in centerings")
        if keys[0] != (_rkey(_IDENTITY_R), 1):
            # identity first, so equality and printing are deterministic
            idx = next((i for i, k in enumerate(keys)
                        if k == (_rkey(_IDENTITY_R), 1)), None)
            if idx is None:
                raise ValueError("the identity is missing from the operations")
            ops = (ops[idx],) + ops[:idx] + ops[idx + 1:]
            object.__setattr__(self, "operations", ops)
        if ops[0].theta != 1:
            raise ValueError("the identity's representative carries time "
                             "reversal; 1' and the anti-translations {1'|v} "
                             "go in centerings")
        self._check_q()
        gap = self.closure_gap()
        if gap is not None:
            a, b = gap
            raise ValueError(
                f"the operations do not close: {a.xyz()!r} * {b.xyz()!r} is not "
                f"in the group modulo its lattice (Stokes 2011 eq. (8))")

    # -- validation ------------------------------------------------------
    def _check_q(self) -> None:
        for op in self.operations + self.centerings:
            rule = line_rule(op.rotation, self.q)
            if rule is None or rule[0] != op.epsilon:
                raise ValueError(
                    f"{op.xyz()!r} does not map the free directions "
                    f"{self.q.free} of q = {self.q.label()} to epsilon times "
                    f"themselves; an incommensurate q must satisfy qR = εq + M "
                    f"(Stokes 2011 eq. (2))")
            mexp = rule[1]
            if tuple(Fraction(x) for x in op.m) != mexp:
                raise ValueError(
                    f"{op.xyz()!r} carries M = {op.m}, but q = {self.q.label()} "
                    f"requires M = q_r R - ε q_r = "
                    f"({', '.join(str(x) for x in mexp)})")

    def _reduce(self, op: SuperspaceOperator) -> SuperspaceOperator | None:
        """The coset representative for ``op``'s R, if ``op`` is in the group.

        ``op`` = c · rep for a centring c, θ included: θ_op = θ_c θ_rep, so a
        primed and an unprimed operation with the same (R, v, δ) are never
        merged (a centring with the right translation but the wrong θ does
        not reduce)."""
        rep = self._by_rotation.get(_rkey(op.rotation))
        if rep is None or rep.epsilon != op.epsilon or rep.m != op.m:
            return None
        diff = (op.translation[0] - rep.translation[0],
                op.translation[1] - rep.translation[1],
                op.translation[2] - rep.translation[2],
                op.delta - rep.delta)
        # op = c * rep for a centering c iff (v_op - v_rep, δ_op - δ_rep) ≡ c
        # (the centring is a pure translation, so the product is additive)
        want = op.theta * rep.theta
        for c in self.centerings:
            if c.theta == want \
                    and all((diff[i] - c.translation[i]) % 1 == 0 for i in range(3)) \
                    and (diff[3] - c.delta) % 1 == 0:
                return rep
        return None

    @functools.cached_property
    def _by_rotation(self) -> dict:
        return {_rkey(o.rotation): o for o in self.operations}

    def closure_gap(self):
        """The first pair (a, b) whose product is not in the group, or ``None``.

        Checks the coset representatives against each other and against the
        centrings, and the centrings among themselves — which is the whole
        group modulo ℤ⁴.
        """
        gens = self.operations + self.centerings
        for a in gens:
            for b in gens:
                if self._reduce(a * b) is None:
                    return a, b
        return None

    # -- views -----------------------------------------------------------
    def all_operations(self) -> tuple[SuperspaceOperator, ...]:
        """Every operation modulo ℤ⁴: centring × representative."""
        return tuple(c * op for op in self.operations for c in self.centerings)

    def __len__(self) -> int:
        return len(self.operations) * len(self.centerings)

    @property
    def is_magnetic(self) -> bool:
        """Whether any operation carries time reversal (θ = −1)."""
        return any(o.theta == -1 for o in self.operations + self.centerings)

    @property
    def magnetic_type(self) -> int | None:
        """The construct type 1-4 of Stokes & Campbell (2022), *Acta Cryst.*
        A**78**, 364, p. 366 (Campbell et al. 2022 § 2.4 for the 3D case), or
        ``None`` for a non-magnetic group.

        Read off the operator list: 2 when {1′|0000} is an operation (grey),
        4 when an anti-translation {1′|v} with v ≢ 0 is (so every operation
        occurs with both signs and none is grey), 3 when some point
        operation is primed and no anti-translation exists, 1 for a group
        of θ = +1 operations declared magnetic, which this class cannot tell
        from a non-magnetic one — so ``None`` here; :mod:`.magnetic` writes
        type 1 explicitly.
        """
        anti = [c for c in self.centerings if c.is_anti_translation]
        if anti:
            zero = any(all(x == 0 for x in c.translation) and c.delta == 0 for c in anti)
            return 2 if zero else 4
        if any(o.theta == -1 for o in self.operations):
            return 3
        return None

    def epsilon_of(self, rotation) -> int:
        return self._by_rotation[_rkey(rotation)].epsilon

    def basic_operations(self) -> tuple[tuple[tuple, tuple], ...]:
        """The basic space group's operations (R, v), centrings included.

        θ is dropped, so for a magnetic group these are the operations of the
        basic group of its family (Stokes & Campbell 2022's B∘F), each once."""
        return tuple(dict.fromkeys(o.basic() for o in self.all_operations()))

    def basic_xyz(self) -> tuple[str, ...]:
        """The basic space group as ``x,y,z`` strings (e.g. for
        :class:`~rietx.crystallography.symmetry.OperatorGroup`)."""
        letters = ("x", "y", "z")
        return tuple(
            ",".join(_format_affine(list(r[i]) + [0], v[i], letters + ("t",))
                     for i in range(3))
            for r, v in self.basic_operations())

    def xyz(self) -> tuple[str, ...]:
        """Every operation as an ``x1,x2,x3,x4`` string; for a magnetic group
        every one carries its time-reversal field (``x1,x2,x3,x4,+1``)."""
        mag = self.is_magnetic
        return tuple(op.xyz(magnetic=mag) for op in self.all_operations())

    def label(self) -> str:
        return self.symbol or f"<superspace group, q = {self.q.label()}>"

    # -- construction from a list ----------------------------------------
    @classmethod
    def from_operations(cls, q, operations, *, symbol=None, number=None,
                        limit: int = 4096) -> SuperspaceGroup:
        """Close a set of generators (strings or operators) into a group.

        Pure translations among them become centrings; everything is reduced
        modulo ℤ⁴.  Refuses a set whose closure gives one rotation two
        inequivalent internal parts (it is not a superspace group).
        """
        qv = ModulationVector.parse(q)
        gens = [SuperspaceOperator.from_xyz(g) if isinstance(g, str) else g
                for g in operations]
        found = _close(gens, limit=limit)
        cen = [o for o in found if o.rotation == _IDENTITY_R]
        for o in cen:
            if o.epsilon != 1 or o.m != (0, 0, 0):
                raise ValueError(
                    f"{o.xyz()!r} has the identity rotation but acts on x4 "
                    f"(epsilon or M nontrivial); q = {qv.label()} is not "
                    f"compatible with these operations")
        by_r: dict = {}
        # an unprimed representative where the group has one (it has one for
        # every R exactly when it holds an anti-translation)
        for o in sorted(found, key=lambda o: o.theta != 1):
            by_r.setdefault(_rkey(o.rotation), o)
        reps = sorted(by_r.values(), key=lambda o: (o.rotation != _IDENTITY_R,
                                                     _rkey(o.rotation)))
        ident = next(o for o in reps if o.rotation == _IDENTITY_R)
        if ident != IDENTITY:
            reps = [IDENTITY if o is ident else o for o in reps]
        return cls(qv, tuple(reps), tuple(sorted(cen, key=_op_key)),
                   symbol=symbol, number=number)

    # -- time reversal ------------------------------------------------------
    def with_anti_translation(self, v, *, symbol=None) -> SuperspaceGroup:
        """D + D{1′|v}: this group with the anti-translation {1′|v} added.

        ``v`` has four components (v₁, v₂, v₃, v₄), the last internal, exact
        rationals in this group's coordinates.  This is the type-2/4
        construction of Stokes & Campbell (2022), *Acta Cryst.* A**78**, 364,
        § 3 p. 367 (v = 0 gives the grey group, type 2).  Refused, by name:
        a v with 2v outside the superspace lattice ({1′|v}² = {1|2v}, their
        p. 367), and a v the operations do not map onto itself modulo the
        lattice — both would add translations this group does not have (the
        "none" rows of their Table 3).  This group must carry no time reversal
        already.
        """
        if self.is_magnetic:
            raise ValueError("this group already carries time reversal; add the "
                             "anti-translation to its maximal non-magnetic subgroup")
        vv = tuple(as_fraction(x) for x in v)
        if len(vv) != 4:
            raise ValueError("an anti-translation in (3+1)D has four components")
        anti = SuperspaceOperator(_IDENTITY_R, tuple(x % 1 for x in vv[:3]), 1,
                                  (0, 0, 0), vv[3] % 1, -1)
        lattice = {(c.translation, c.delta) for c in self.centerings}
        sq = anti * anti
        if (sq.translation, sq.delta) not in lattice:
            raise ValueError(
                f"{{1'|{', '.join(str(x) for x in vv)}}}² = {{1|2v}} with 2v = "
                f"({', '.join(str(2 * x) for x in vv)}) not a lattice vector of "
                f"this group: not an anti-translation of it (Stokes & Campbell "
                f"2022 p. 367)")
        for op in self.operations:
            img = op * anti * op.inverse()
            if (img.translation, img.delta) not in {
                    ((c * anti).translation, (c * anti).delta) for c in self.centerings}:
                raise ValueError(
                    f"{op.xyz()!r} maps the anti-translation {anti.xyz()!r} to "
                    f"{img.xyz()!r}, which differs from it by a translation this "
                    f"group lacks; adding it would change the lattice (Stokes & "
                    f"Campbell 2022 Table 3, 'none')")
        cen = tuple(self.centerings) + tuple(c * anti for c in self.centerings)
        return SuperspaceGroup(self.q, self.operations, tuple(sorted(cen, key=_op_key)),
                               symbol=symbol)

    def grey(self) -> SuperspaceGroup:
        """G + {1′|0000}G, the grey (type-2) group (Perez-Mato et al. 2012
        eq. (12) in superspace; Stokes & Campbell 2022 p. 366)."""
        return self.with_anti_translation((0, 0, 0, 0))

    def with_time_reversal_shift(self) -> SuperspaceGroup:
        """Ω = G + {1′|000½}G, the magnetic superspace group of a single-k
        incommensurate magnetic phase (Perez-Mato, Ribeiro, Petříček & Aroyo
        2012, *J. Phys.: Condens. Matter* **24**, 163201, eq. (20)).

        {1′|000½} is carried in the operator list as a centring, never as a
        flag, and is distinct from both {1′|0000} and {1|000½}.
        """
        return self.with_anti_translation((0, 0, 0, Fraction(1, 2)))

    # -- transformation ----------------------------------------------------
    def transformed(self, transform: SuperspaceTransform) -> SuperspaceGroup:
        """The group S g S⁻¹ for every g, and q in the new coordinates.

        See :class:`SuperspaceTransform` for what S does to q.
        """
        qn = transform.apply_to_q(self.q)
        det = _det_rational(transform.p_matrix)
        if abs(det) == 1:
            # a unimodular basis change maps coset representatives to coset
            # representatives and centrings to centrings: no closure needed
            reps = tuple(transform.conjugate(o) for o in self.operations)
            cen = tuple(transform.conjugate(c) for c in self.centerings)
            if len({_rkey(o.rotation) for o in reps}) == len(reps):
                return SuperspaceGroup(qn, reps, cen)
        ops = [transform.conjugate(o) for o in self.all_operations()]
        # a cell change of |det| ≠ 1 turns lattice translations of the old
        # cell into centrings of the new one; they are group elements the
        # coset list does not hold, so their images join the closure
        for i in range(3):
            unit = tuple(Fraction(int(i == j)) for j in range(3))
            ops.append(transform.conjugate(
                SuperspaceOperator(_IDENTITY_R, unit, 1, (0, 0, 0), Fraction(0))))
        return SuperspaceGroup.from_operations(qn, ops, symbol=None)

    # -- the commensurate section ----------------------------------------
    def section(self, q, t0) -> Section:
        """The 3D space group of the real-space section t = t₀ at rational q.

        Orlov, Palatinus & Chapuis (2008), *J. Appl. Cryst.* **41**, 1182,
        eq. (1): an operation survives iff
        s₄ + l₄ − (s₃ + l₃)·q + (ε − 1)t₀ = 0 for some lattice vector
        (l₃, l₄), and becomes the 3D operation {R | s₃ + l₃} (their eq. (2)
        then expresses it in the supercell).  In these coordinates s₄ is δ and
        the test reads δ − q·(v + l₃) + (ε − 1)t₀ ∈ ℤ (van Smaalen, 1987,
        *Acta Cryst.* A**43**, 202, eq. (3.3); Petříček et al. 2010 eq. (14)).
        The ε = +1 operations survive at every t₀ or at none; the ε = −1 ones
        at a discrete set of sections (Orlov § 2 (i)), so t₀ is a model
        parameter at rational q.

        ``q`` must be a rational member of this group's q family; ``t0`` is
        exact.  The result names the section's space-group type through
        spglib (Togo, Shinohara & Tanaka 2024) and keeps the operations in the
        supercell basis diag(N₁, N₂, N₃) of Orlov eq. (2).
        """
        if self.is_magnetic:
            raise ValueError(
                "the section of a magnetic superspace group is a magnetic space "
                "group, which this method does not build (it would drop θ); "
                "take the section of the non-magnetic family or maximal subgroup")
        qq = tuple(as_fraction(c) for c in q)
        if self.q.contains(qq) is None:
            raise ValueError(
                f"q = ({', '.join(str(c) for c in qq)}) is not a member of this "
                f"group's family {self.q.label()}")
        t = as_fraction(t0)
        n = [c.denominator for c in qq]
        # supercell translations: the conventional lattice (centrings
        # included) restricted to q·l ∈ ℤ, plus the lifted centrings
        ops3: dict = {}
        for op in self.all_operations():
            for l3 in product(*(range(ni) for ni in n)):
                v = tuple(op.translation[i] + l3[i] for i in range(3))
                phase = op.delta - sum(qq[i] * v[i] for i in range(3)) \
                    + (op.epsilon - 1) * t
                if phase.denominator == 1:
                    vs = tuple((v[i] / n[i]) % 1 for i in range(3))
                    r = op.rotation
                    rs = tuple(tuple(Fraction(r[i][j] * n[j], n[i]) for j in range(3))
                               for i in range(3))
                    if any(x.denominator != 1 for row in rs for x in row):
                        raise ValueError(
                            f"the diagonal supercell diag{tuple(n)} is not "
                            f"invariant under {op.xyz()!r}; this section "
                            f"needs a non-diagonal supercell, not built here")
                    rs_i = tuple(tuple(int(x) for x in row) for row in rs)
                    ops3[(rs_i, vs)] = None
        return Section(tuple(qq), t, tuple(n), tuple(ops3))


def _det_rational(m) -> Fraction:
    return (m[0][0] * (m[1][1] * m[2][2] - m[1][2] * m[2][1])
            - m[0][1] * (m[1][0] * m[2][2] - m[1][2] * m[2][0])
            + m[0][2] * (m[1][0] * m[2][1] - m[1][1] * m[2][0]))


def _op_key(o: SuperspaceOperator) -> tuple:
    return (_rkey(o.rotation), o.epsilon, o.m, o.translation, o.delta, -o.theta)


def _close(gens, *, limit: int = 4096) -> list[SuperspaceOperator]:
    found = list(dict.fromkeys([IDENTITY] + list(gens)))
    seen = set(found)
    frontier = list(found)
    while frontier:
        new = []
        for a in frontier:
            for b in list(found):
                for p in (a * b, b * a):
                    if p not in seen:
                        seen.add(p)
                        new.append(p)
        found.extend(new)
        if len(found) > limit:
            raise ValueError(
                f"closing these operations passed {limit} elements modulo ℤ⁴; "
                f"they do not generate a superspace group (an internal "
                f"translation of unbounded denominator, or q incompatible)")
        frontier = new
    return found


@dataclass(frozen=True)
class SuperspaceTransform:
    """An affine change of superspace coordinates (Stokes 2011 eq. (13)):

        x′ = P x + p,        x₄′ = s_m·x + s_eps x₄ + s_delta.

    P is the 3D basis change acting on fractional coordinates (columns), p an
    origin shift, s_eps = ±1 (q → −q), s_m an integer row (q → q + H) and
    s_delta an internal origin shift.  q transforms as
    q′ = (s_eps q + s_m) P⁻¹ (row vectors).  A pure relabelling q → q + H with
    H outside the reciprocal lattice gives the centrings internal components
    (Yamamoto et al. 1985 § 2), which the group then carries explicitly.
    """

    p_matrix: tuple[tuple[Fraction, ...], ...] = tuple(
        tuple(Fraction(int(i == j)) for j in range(3)) for i in range(3))
    origin: tuple[Fraction, Fraction, Fraction] = _ZERO3
    s_m: tuple[Fraction, Fraction, Fraction] = _ZERO3
    s_eps: int = 1
    s_delta: Fraction = Fraction(0)

    @classmethod
    def build(cls, p_matrix=None, origin=(0, 0, 0), s_m=(0, 0, 0), s_eps=1,
              s_delta=0) -> SuperspaceTransform:
        pm = ((1, 0, 0), (0, 1, 0), (0, 0, 1)) if p_matrix is None else p_matrix
        return cls(tuple(tuple(as_fraction(x) for x in row) for row in pm),
                   tuple(as_fraction(x) for x in origin),
                   tuple(as_fraction(x) for x in s_m), int(s_eps),
                   as_fraction(s_delta))

    def augmented(self) -> list[list[Fraction]]:
        a = [[Fraction(0)] * 5 for _ in range(5)]
        for i in range(3):
            for j in range(3):
                a[i][j] = self.p_matrix[i][j]
            a[i][4] = self.origin[i]
        a[3][:3] = list(self.s_m)
        a[3][3] = Fraction(self.s_eps)
        a[3][4] = self.s_delta
        a[4][4] = Fraction(1)
        return a

    def apply_to_q(self, q: ModulationVector) -> ModulationVector:
        pinv = _inverse3([list(r) for r in self.p_matrix])
        row = [self.s_eps * q.rational[i] + self.s_m[i] for i in range(3)]
        rat = tuple(sum(row[i] * pinv[i][j] for i in range(3)) for j in range(3))
        free = []
        for f in q.free:
            fr = [sum(self.s_eps * f[i] * pinv[i][j] for i in range(3)) for j in range(3)]
            den = lcm(*(x.denominator for x in fr))
            fi = [int(x * den) for x in fr]
            free.append(tuple(fi))
        return ModulationVector(rat, tuple(free))

    def conjugate(self, op: SuperspaceOperator) -> SuperspaceOperator:
        """S · A(op) · S⁻¹, reduced mod ℤ⁴.

        The equivalence map of Stokes, Campbell & van Smaalen (2011),
        *Acta Cryst.* A**67**, 45, eq. (13), applied to one operator; van
        Smaalen, Campbell & Stokes (2013), *Acta Cryst.* A**69**, 75, § 2.1
        state equivalence as the same map on the (3+d+1) augmented matrices.
        """
        s = self.augmented()
        sinv = _inverse_n(s)
        g = _op_augmented(op)
        out = _matmul_n(_matmul_n(s, g), sinv)
        rot = [[out[i][j] for j in range(3)] for i in range(3)]
        mrow = out[3][:3]
        if any(x.denominator != 1 for row in rot for x in row) \
                or any(x.denominator != 1 for x in mrow) or out[3][3] not in (1, -1):
            raise ValueError(
                "this transformation does not map the superspace lattice onto "
                "itself for this operation (non-integral R or M after it)")
        return SuperspaceOperator(
            tuple(tuple(int(x) for x in row) for row in rot),
            tuple(out[i][4] % 1 for i in range(3)),
            int(out[3][3]), tuple(int(x) for x in mrow), out[3][4] % 1, op.theta)


def _op_augmented(op: SuperspaceOperator) -> list[list[Fraction]]:
    a = [[Fraction(0)] * 5 for _ in range(5)]
    for i in range(3):
        for j in range(3):
            a[i][j] = Fraction(op.rotation[i][j])
        a[i][4] = op.translation[i]
    a[3][:3] = [Fraction(x) for x in op.m]
    a[3][3] = Fraction(op.epsilon)
    a[3][4] = op.delta
    a[4][4] = Fraction(1)
    return a


def _matmul_n(a, b):
    n = len(a)
    return [[sum(a[i][k] * b[k][j] for k in range(n)) for j in range(n)]
            for i in range(n)]


def _inverse_n(a):
    n = len(a)
    m = [list(row) + [Fraction(int(i == j)) for j in range(n)]
         for i, row in enumerate(a)]
    for c in range(n):
        p = next(i for i in range(c, n) if m[i][c] != 0)
        m[c], m[p] = m[p], m[c]
        inv = m[c][c]
        m[c] = [x / inv for x in m[c]]
        for i in range(n):
            if i != c and m[i][c] != 0:
                f = m[i][c]
                m[i] = [x - f * y for x, y in zip(m[i], m[c])]
    return [row[n:] for row in m]


@dataclass(frozen=True)
class Section:
    """A commensurate section: the 3D group at rational q and phase t₀.

    ``operations`` are (R, v) in the supercell basis diag(``supercell``)
    (Orlov et al. 2008 eq. (2)), centring translations included.
    """

    q: tuple[Fraction, Fraction, Fraction]
    t0: Fraction
    supercell: tuple[int, int, int]
    operations: tuple

    @functools.cached_property
    def _type(self):
        import spglib

        rots = np.array([r for r, _ in self.operations], dtype=np.intc)
        trans = np.array([[float(x) for x in v] for _, v in self.operations])
        # an invariant metric in the supercell basis, so spglib's lattice
        # argument is consistent with the operations
        g = sum(r.T @ r for r in rots.astype(float))
        lat = np.linalg.cholesky(g).T
        t = spglib.get_spacegroup_type_from_symmetry(rots, trans, lattice=lat,
                                                     symprec=1e-5)
        if t is None:  # pragma: no cover - spglib's old error mode
            raise ValueError("spglib could not identify the section's group")
        return t

    @property
    def number(self) -> int:
        """International space-group number of the section."""
        return int(self._type.number)

    @property
    def international(self) -> str:
        """spglib's short symbol for the type, in its standard setting."""
        return str(self._type.international_short)
