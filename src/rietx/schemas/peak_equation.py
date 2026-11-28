"""A peak equation: a term on each reflection's width or position, or a factor on
its intensity, written in the reflection's indices and angle (WP-2107).

``Phase.peak_equations`` and ``Instrument.peak_equations`` hold them.  A phase's
equation may read the reflection (``h``, ``k``, ``l``, ``m``, ``d``) and its
angle (``theta``, ``two_theta``); the instrument's reads the angle alone and
moves every phase's peaks.  The expression is written in the grammar of
:mod:`rietx.params.expression`, and its coefficients are ordinary parameters at
``phases.<i>.peak_equations.<j>.<name>`` and ``instrument.peak_equations.<j>.
<name>``, so they take bounds, holds, ties and esds like any other entry.

The five targets add where the built-in terms add (root ``CLAUDE.md``,
Instrument ⊕ sample profile split): a Lorentzian FWHM adds, a Gaussian FWHM adds
in quadrature, a Gaussian FWHM² adds beside Caglioti's U, V and W, a shift adds
to the position, and an intensity factor multiplies.  Every value is per
reflection, so a reflection is the unit the equation is single-valued on: the
compile evaluates it on every image of the reflection's Laue orbit and refuses
a disagreement (``model.peak_equations``).
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import Field, model_validator

from .._nearmiss import did_you_mean
from .common import Base, Parameter

#: target → the unit its value carries.  ``gauss_fwhm`` adds in quadrature,
#: ``gauss_fwhm_squared`` is a signed term of Γ_G², ``intensity_factor`` is
#: a pure number multiplying the reflection's intensity.
PEAK_TARGETS: dict[str, str] = {
    "lor_fwhm": "deg",
    "gauss_fwhm": "deg",
    "gauss_fwhm_squared": "deg^2",
    "shift": "deg",
    "intensity_factor": "1",
}
PeakTarget = Literal["lor_fwhm", "gauss_fwhm", "gauss_fwhm_squared", "shift",
                     "intensity_factor"]

#: the targets an instrument-level equation may take: it moves every phase's
#: peaks and reads no reflection, so only a position is the instrument's
INSTRUMENT_TARGETS = frozenset({"shift"})

#: the names a peak equation binds to the reflection it is evaluated on:
#: Miller indices, multiplicity, d (Å), the Bragg angle θ in radians, 2θ in
#: degrees where the peak sits before the phase's equations act, and the
#: emission line's λ in Å (WP-2152), so each line's image reads its own
REFLECTION_NAMES = ("h", "k", "l", "m", "d", "theta", "two_theta", "wavelength")
#: the names an instrument-level equation may read.  ``wavelength`` is not one:
#: the instrument's shift is also evaluated at angles no emission line owns
#: (the window the reflections are generated over), so λ has no value there
INSTRUMENT_NAMES = frozenset({"theta", "two_theta"})
#: the names a condition may read: integers frozen for the stage, so the
#: branch a reflection takes cannot change during a solve
CONDITION_NAMES = frozenset({"h", "k", "l", "m"})
#: the grammar's functions that read a reflection's orbit or direction
REFLECTION_FUNCTIONS = frozenset({"orbit_mean", "harmonic"})

_IDENT = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")


def _walk(node):
    """Every node of an expression tree, root first."""
    from ..params import expression as ex
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        if isinstance(n, ex.Neg | ex.Not):
            stack.append(n.arg)
        elif isinstance(n, ex.BinOp | ex.Compare | ex.BoolOp):
            stack.extend((n.right, n.left))
        elif isinstance(n, ex.Call):
            stack.extend(reversed(n.args))


def harmonic_args(call) -> tuple[int, int]:
    """``(l, n)`` of a ``harmonic(l, n)`` call, or raise.

    Both are integer literals, ``n`` may carry a sign, ``l`` is even and at
    least 2, and |n| ≤ l.  An odd degree is odd under inversion, so no powder
    pattern measures it, and degree 0 is a constant.
    """
    from ..params import expression as ex

    degree, n = (ex._int_literal(a) for a in call.args)
    if degree is None or n is None:
        raise ValueError("harmonic(l, n) takes two integer literals, as in "
                         "harmonic(4, 0) or harmonic(4, -4)")
    if degree < 2 or degree % 2 or abs(n) > degree:
        raise ValueError(
            f"harmonic({degree}, {n}): l is even and at least 2, and |n| is at "
            "most l. A powder pattern obeys Friedel's law, so an odd degree "
            "cannot be measured, and degree 0 is a constant")
    return degree, n


class PeakEquation(Base):
    """A term on each reflection's peak, written as an equation.

    ``target`` names what the value is added to, or multiplies:

    * ``lor_fwhm`` (° 2θ) adds to the Lorentzian FWHM, as ``lor_size`` does;
    * ``gauss_fwhm`` (° 2θ) adds to the Gaussian FWHM in quadrature;
    * ``gauss_fwhm_squared`` (deg²) is a signed term added to Γ_G² where
      Caglioti's U, V and W add;
    * ``shift`` (° 2θ) adds to the peak position;
    * ``intensity_factor`` (1) multiplies the reflection's intensity.

    ``expression`` reads the coefficients by name and the reflection through
    ``h``, ``k``, ``l``, ``m`` (multiplicity), ``d`` (Å), ``theta`` (the Bragg
    angle, radians, so ``tan(theta)`` works), ``two_theta`` (degrees, where
    the peak sits before the phase's equations act) and ``wavelength`` (Å, the
    emission line the peak is drawn at).  ``wavelength`` writes a size term
    once, as ``y*wavelength/cos(theta)``, for patterns at several wavelengths.
    ``orbit_mean(x)``
    averages ``x`` over the reflection's Laue orbit, and ``harmonic(l, n)`` is
    the symmetrised spherical harmonic K_l^n of the reflection's direction.  A
    condition inside ``if(...)`` may read only ``h``, ``k``, ``l`` and ``m``,
    which cannot change during a solve.

    ``coefficients`` maps each name the expression reads beyond the reflection
    to its :class:`Parameter`.  A coefficient the expression does not read is
    refused, since it would be a parameter that moves nothing.
    """

    target: PeakTarget
    expression: str
    coefficients: dict[str, Parameter] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _expression_reads_its_coefficients(self) -> "PeakEquation":
        from ..params import expression as ex

        for name in self.coefficients:
            if not _IDENT.fullmatch(name):
                raise ValueError(
                    f"peak equation coefficient {name!r}: a name is letters, "
                    "digits and underscores, starting with a letter")
            if name in REFLECTION_NAMES:
                raise ValueError(
                    f"peak equation coefficient {name!r}: that name is the "
                    f"reflection's ({', '.join(REFLECTION_NAMES)}); call the "
                    "coefficient something else")
            if name == "scale":
                raise ValueError(
                    "peak equation coefficient 'scale': a path ending in "
                    "'.scale' is a phase scale to a joint fit's sharing rule; "
                    "call the coefficient something else")
            if name in ex.RESERVED:
                raise ValueError(
                    f"peak equation coefficient {name!r}: that name is the "
                    "grammar's own; call the coefficient something else")
        try:
            tree = ex.parse(self.expression)
        except ex.ExpressionError as exc:
            raise ValueError(f"peak equation {self.target}: {exc}") from None
        used = ex.names_in(tree)
        known = set(self.coefficients) | set(REFLECTION_NAMES)
        for name in used:
            if name not in known:
                hint = did_you_mean(name, known)
                raise ValueError(
                    f"peak equation {self.target}: {name!r} is neither a "
                    f"coefficient nor a reflection name"
                    + (f"; {hint}" if hint else "")
                    + f". The reflection names are {', '.join(REFLECTION_NAMES)}, "
                    "and a coefficient is declared in `coefficients`")
        unused = [c for c in self.coefficients if c not in used]
        if unused:
            raise ValueError(
                f"peak equation {self.target}: the coefficient"
                f"{'s' if len(unused) > 1 else ''} {', '.join(map(repr, unused))} "
                "is not read by the expression, so it would move nothing")
        for node in _walk(tree):
            if isinstance(node, ex.Compare):
                moving = [n for n in ex.names_in(node) if n not in CONDITION_NAMES]
                calls = [c.func for c in _walk(node) if isinstance(c, ex.Call)
                         and c.func in REFLECTION_FUNCTIONS]
                if moving or calls:
                    what = ", ".join(map(repr, moving + [f"{c}()" for c in calls]))
                    raise ValueError(
                        f"peak equation {self.target}: the condition "
                        f"{ex.to_text(node)!r} reads {what}, which can change "
                        "during a solve and would switch a reflection's branch "
                        "with a jump in the residual. A condition may read only "
                        "h, k, l and m, which are frozen for the stage")
            if isinstance(node, ex.Call) and node.func == "harmonic":
                harmonic_args(node)
            if isinstance(node, ex.Call) and node.func == "orbit_mean":
                inner = [c for c in _walk(node.args[0]) if isinstance(c, ex.Call)
                         and c.func == "orbit_mean"]
                if inner:
                    raise ValueError(
                        f"peak equation {self.target}: orbit_mean() inside "
                        "orbit_mean() averages a value that is already the same "
                        "on every image; write it once")
        return self

    def reads(self) -> tuple[str, ...]:
        """The reflection names the expression reads, in first-use order."""
        from ..params import expression as ex
        return tuple(n for n in ex.names_in(ex.parse(self.expression))
                     if n in REFLECTION_NAMES)

    def functions(self) -> frozenset[str]:
        """The reflection functions the expression calls."""
        from ..params import expression as ex
        return frozenset(n.func for n in _walk(ex.parse(self.expression))
                         if isinstance(n, ex.Call) and n.func in REFLECTION_FUNCTIONS)


def check_level(equations: list[PeakEquation], level: str,
                field_names=()) -> None:
    """Refuse a list a level cannot carry.

    ``level`` is ``"phase"`` or ``"instrument"``.  Each level holds at most
    one equation per target, since a sum goes in one expression.  The
    instrument's takes ``shift`` alone and reads only the angle, because it
    moves every phase's peaks and a reflection's indices belong to a phase.

    ``field_names`` are the level's own fields.  A coefficient named after one
    is refused, because fnmatch's ``*`` crosses dots: a plan's
    ``phases.*.lor_size`` would match ``phases.0.peak_equations.0.lor_size``
    and free the coefficient unasked.  ``scale`` is the case the joint fit's
    sharing rule adds (:class:`PeakEquation`).
    """
    seen: set[str] = set()
    for i, eq in enumerate(equations):
        clash = sorted(set(eq.coefficients) & set(field_names))
        if clash:
            raise ValueError(
                f"{level} peak_equations.{i}: the coefficient {clash[0]!r} is "
                f"named after a {level} field, so a plan's glob for that field "
                f"(as in '{'phases.*' if level == 'phase' else 'instrument'}."
                f"{clash[0]}') would free it too; call it something else")
        if eq.target in seen:
            raise ValueError(
                f"{level} peak_equations: two equations on {eq.target!r}. Each "
                "target takes one equation per level; write a sum as one "
                "expression")
        seen.add(eq.target)
        if level != "instrument":
            continue
        if eq.target not in INSTRUMENT_TARGETS:
            raise ValueError(
                f"instrument peak_equations.{i}: target {eq.target!r} belongs to "
                "a phase. The instrument's equation takes 'shift' only, and a "
                "width or intensity term goes on Phase.peak_equations")
        hkl = [n for n in eq.reads() if n not in INSTRUMENT_NAMES]
        calls = sorted(eq.functions())
        if hkl or calls:
            what = ", ".join([*map(repr, hkl), *(f"{c}()" for c in calls)])
            raise ValueError(
                f"instrument peak_equations.{i}: the expression reads {what}, "
                "which belong to a phase's reflections. The instrument's "
                "equation reads theta and two_theta only; an equation in hkl "
                "or wavelength goes on Phase.peak_equations")
