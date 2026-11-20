"""Peak equations compiled for one stage (WP-2107).

A peak equation (``schemas.peak_equation.PeakEquation``) is evaluated once per
emission line over a phase's frozen reflection list.  This module freezes what
the evaluation needs for the stage and is the one function that evaluates it,
so the compile's window sizing and the forward model cannot disagree about an
equation's value (the probe that scoped this WP measured 1767 on χ² over 5250
points when the compile ignored a width equation).

**What is frozen.**  ``h``, ``k``, ``l`` and ``m`` of every representative,
and, where an equation calls ``orbit_mean``, every image of each reflection's
Laue orbit (``crystallography.symmetry.reflection_orbits``).  ``d``, ``theta``
and ``two_theta`` follow the parameters and are passed in.  A
``harmonic(l, n)`` term keeps its symmetrised coefficients on the real
harmonics of degree l; its value follows the cell through the frame, exactly
as the texture's does (``crystallography.spherical_harmonics``).

**A reflection is an orbit.**  rietx holds one representative per Laue orbit,
so an expression that is not single-valued over the orbit would give an
answer that depends on which image the list happened to hold.
:func:`check_orbits` evaluates every equation on every image, at the stored
coefficients and at seeded trial coefficients, and refuses a disagreement,
naming the first reflection and image that differ.  ``orbit_mean(x)`` is the
way out.  The trial coefficients are why ``if(l == 0, a, b)`` with a equal
to b is refused although it agrees at the start: the fit would split it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from ..backend import get_backend
from ..crystallography.spherical_harmonics import (
    real_harmonics,
    reflection_directions,
    term_name,
    texture_basis,
)
from ..crystallography.symmetry import reflection_orbits
from ..params.expression import Call, Expression
from ..schemas.peak_equation import PeakEquation, _walk, harmonic_args
from .preferred_orientation import orbit_layout

#: the relative disagreement between two images of one reflection above which
#: an equation is refused as not single-valued on the orbit.  An equation that
#: is single-valued agrees to rounding; one that is not differs at the size of
#: its own terms, so the line sits far from both.
ORBIT_RTOL = 1e-9
#: trial coefficient sets :func:`check_orbits` evaluates beside the stored one
ORBIT_TRIALS = 3


@dataclass
class CompiledPeakEquation:
    """One equation, parsed, with the table path of each coefficient."""

    target: str
    expression: Expression
    #: (coefficient name, table path), in the declaration's order
    paths: tuple[tuple[str, str], ...]
    #: the equation's own path, ``{base}.peak_equations.{index}``
    prefix: str = ""

    def coefficient_values(self, values) -> dict:
        return {name: values[path] for name, path in self.paths}

    def key(self, values) -> tuple:
        """The coefficients as plain floats, for a memo key (numpy only)."""
        return tuple(float(values[path]) for _name, path in self.paths)


#: the targets that enter a width, in the order the width block reads them
WIDTH_TARGETS = ("lor_fwhm", "gauss_fwhm", "gauss_fwhm_squared")


def evaluate_angle(eq: CompiledPeakEquation, values, *, theta, two_theta):
    """An instrument-level equation at Bragg ``theta`` (radians) and
    ``two_theta`` (degrees, before the equation acts), on the active backend.

    It reads no reflection, so no frame; the shape is ``theta``'s.
    """
    xp = get_backend()
    bind = {"theta": theta, "two_theta": two_theta}
    bind.update(eq.coefficient_values(values))
    v = eq.expression.evaluate(bind, xp)
    if not np.ndim(v) or np.shape(v) != np.shape(theta):
        v = v + xp.zeros_like(xp.asarray(theta, dtype=np.float64))
    return v


def compile_equation(eq: PeakEquation, base: str, index: int) -> CompiledPeakEquation:
    """``eq`` at ``{base}.peak_equations.{index}``."""
    prefix = f"{base}.peak_equations.{index}"
    return CompiledPeakEquation(
        target=eq.target, expression=Expression(eq.expression),
        paths=tuple((name, f"{prefix}.{name}") for name in eq.coefficients),
        prefix=prefix)


@dataclass
class ReflectionFrame:
    """A phase's frozen reflection integers, and the orbit images when wanted.

    The object :meth:`Expression.evaluate` takes as ``reflection``: it binds
    an ``orbit_mean`` argument to the images and a ``harmonic`` call to the
    reflection's direction.
    """

    hkl: np.ndarray                       # (N, 3) int
    multiplicity: np.ndarray              # (N,) float
    group: object = None
    #: the flattened Laue orbits, ``None`` unless an equation needs them
    members: np.ndarray | None = None     # (M, 3) int
    seg: np.ndarray | None = None         # (M,) intp
    counts: np.ndarray | None = None      # (N,) intp
    #: (l, n) → (frame rule, coefficients on the degree-l real harmonics)
    harmonics: dict = field(default_factory=dict)
    #: the cell the harmonic values below were taken at, and the values
    cell: tuple | None = None
    _images: bool = False

    def bindings(self, d, theta, two_theta) -> dict:
        """The reflection names, bound at the representatives."""
        xp = get_backend()
        f64 = np.float64
        return {"h": xp.asarray(self.hkl[:, 0].astype(f64)),
                "k": xp.asarray(self.hkl[:, 1].astype(f64)),
                "l": xp.asarray(self.hkl[:, 2].astype(f64)),
                "m": xp.asarray(self.multiplicity),
                "d": d, "theta": theta, "two_theta": two_theta}

    # -- the protocol Expression's evaluator reads ----------------------------
    def image_bindings(self, bindings):
        """``bindings`` on the orbit images: the integers per image, every
        other name its reflection's value repeated over the orbit."""
        if self.members is None:  # pragma: no cover - compile builds them
            raise AssertionError("orbit_mean() without frozen orbit images")
        xp = get_backend()
        out = dict(bindings)
        f64 = np.float64
        for i, name in enumerate(("h", "k", "l")):
            out[name] = xp.asarray(self.members[:, i].astype(f64))
        for name in ("m", "d", "theta", "two_theta"):
            v = bindings.get(name)
            if v is not None and np.ndim(v):
                out[name] = v[self.seg]
        return out

    def to_images(self, v):
        """A per-reflection array repeated over the images; a scalar as is."""
        if v is None or isinstance(v, bool) or not np.ndim(v):
            return v
        return v[self.seg]

    def orbit_mean(self, v):
        """Each reflection's mean of the per-image ``v``."""
        if not np.ndim(v):
            return v
        xp = get_backend()
        total = xp.segment_sum(v, self.seg, len(self.counts))
        return total / xp.asarray(self.counts, dtype=np.float64)

    def harmonic(self, degree: int, n: int, images: bool):
        """K_l^n at each representative (or image) under :attr:`cell`."""
        rule, coef = self.harmonics[(degree, n)]
        xp = get_backend()
        hkl = self.members if images else self.hkl
        u = reflection_directions(hkl, rule, self.cell)
        return xp.matmul(real_harmonics(degree, u), xp.asarray(coef, dtype=np.float64))

    def at(self, cell) -> "ReflectionFrame":
        """This frame with its harmonics taken at ``cell``."""
        if not self.harmonics or self.cell is cell:
            return self
        out = ReflectionFrame(self.hkl, self.multiplicity, self.group, self.members,
                              self.seg, self.counts, self.harmonics)
        out.cell = cell
        return out


@dataclass
class PhasePeakEquations:
    """One phase's equations by target, and the frame they are evaluated on."""

    equations: dict
    frame: ReflectionFrame

    def has(self, *targets: str) -> bool:
        return any(t in self.equations for t in targets)

    def key(self, values, targets) -> tuple:
        """The coefficients of ``targets`` as plain floats, for a memo key."""
        return tuple(self.equations[t].key(values) for t in targets
                     if t in self.equations)


def compile_frame(group, refl, cell, equations: list[CompiledPeakEquation]
                  ) -> ReflectionFrame:
    """The frame ``equations`` need over the reflection list ``refl``.

    The orbit images are built when an equation calls ``orbit_mean`` and
    always for :func:`check_orbits`, which is why this takes the group.  A
    ``harmonic(l, n)`` the Laue class does not allow is refused here, naming
    the ones of that degree it does.
    """
    hkl = np.asarray(refl.hkl, dtype=np.int64)
    frame = ReflectionFrame(hkl=hkl,
                            multiplicity=np.asarray(refl.multiplicity, dtype=np.float64),
                            group=group)
    if len(hkl):
        frame.members, frame.seg, frame.counts = orbit_layout(
            reflection_orbits(group, hkl))
    wanted: set[tuple[int, int]] = set()
    for eq in equations:
        for node in _walk(eq.expression.tree):
            if isinstance(node, Call) and node.func == "harmonic":
                wanted.add(harmonic_args(node))
    for degree, n in sorted(wanted):
        basis = texture_basis(group, degree, cell)
        allowed = [(t, c) for t, c in zip(basis.terms, basis.coefficients, strict=True)
                   if t.degree == degree]
        match = [c for t, c in allowed if t.n == n]
        if not match:
            names = ", ".join(f"harmonic({t.degree}, {t.n})" for t, _ in allowed)
            raise ValueError(
                f"harmonic({degree}, {n}) is not symmetric under the Laue class "
                f"of this phase, so it would differ between the images of one "
                f"reflection. Of degree {degree} the class allows "
                + (names if names else "none")
                + f" ({term_name(degree, n)} in the texture's naming)")
        frame.harmonics[(degree, n)] = (basis.rule, match[0])
    frame.cell = cell
    return frame


def evaluate(eq: CompiledPeakEquation, values, frame: ReflectionFrame, *, d, theta,
             two_theta, coefficients: dict | None = None, images: bool = False):
    """The equation's value at every reflection (or image), on the active backend.

    ``theta`` is the Bragg angle in **radians**, ``two_theta`` the position in
    degrees before the phase's equations act, ``d`` in Å.  ``coefficients``
    overrides the values read off ``values`` (the orbit check's trials).
    The result has the shape of ``theta``.
    """
    xp = get_backend()
    bind = frame.bindings(d, theta, two_theta)
    bind.update(eq.coefficient_values(values) if coefficients is None else coefficients)
    if images:
        bind = frame.image_bindings(bind)
    v = eq.expression.evaluate(bind, xp, reflection=frame, images=images)
    shape_of = bind["theta"]
    return v + xp.zeros_like(shape_of) if not np.ndim(v) or np.shape(v) != np.shape(
        shape_of) else v


def gradient(eq: CompiledPeakEquation, values, frame: ReflectionFrame, *, d, theta,
             two_theta) -> tuple[np.ndarray, list[np.ndarray]]:
    """The value and ∂/∂coefficient for each coefficient, numpy, exact."""
    bind = frame.bindings(d, theta, two_theta)
    bind.update(eq.coefficient_values(values))
    v, parts = eq.expression.gradient(bind, [name for name, _ in eq.paths],
                                      reflection=frame)
    shape = np.shape(theta)
    return (np.broadcast_to(v, shape).astype(np.float64),
            [np.broadcast_to(p, shape).astype(np.float64) for p in parts])


def check_orbits(eq: CompiledPeakEquation, values, frame: ReflectionFrame, *, d,
                 theta, two_theta, where: str) -> None:
    """Refuse an equation that differs between the images of one reflection.

    Evaluated at the stored coefficients and at :data:`ORBIT_TRIALS` seeded
    trial sets, since a condition whose branches agree at the start can split
    during the fit.  Numpy, at compile.
    """
    if frame.members is None or not len(frame.hkl):
        return
    rng = np.random.default_rng(20_107)
    stored = eq.coefficient_values(values)
    trials = [stored]
    for _ in range(ORBIT_TRIALS):
        trials.append({name: float(v) + rng.uniform(0.5, 1.5) * (1.0 + abs(float(v)))
                       * (1 if rng.uniform() < 0.5 else -1)
                       for name, v in stored.items()})
    for coefficients in trials:
        with np.errstate(all="ignore"):
            rep = np.asarray(evaluate(eq, values, frame, d=d, theta=theta,
                                      two_theta=two_theta, coefficients=coefficients),
                             dtype=np.float64)
            img = np.asarray(evaluate(eq, values, frame, d=d, theta=theta,
                                      two_theta=two_theta, coefficients=coefficients,
                                      images=True), dtype=np.float64)
        ref = rep[frame.seg]
        both_nan = np.isnan(ref) & np.isnan(img)
        scale = np.maximum(np.abs(ref), np.abs(img))
        bad = ~both_nan & ~(np.abs(img - ref) <= ORBIT_RTOL * np.maximum(scale, 1e-300))
        bad &= ~((ref == img))
        if bad.any():
            j = int(np.flatnonzero(bad)[0])
            k = int(frame.seg[j])
            h0 = tuple(int(x) for x in frame.hkl[k])
            h1 = tuple(int(x) for x in frame.members[j])
            raise ValueError(
                f"{where}: {eq.expression.text!r} is not single-valued over the "
                f"orbit of reflection {h0}: it gives {ref[j]:.6g} there and "
                f"{img[j]:.6g} on its symmetry image {h1}"
                + ("" if coefficients is stored else
                   " (at trial coefficients, so a fit would split them)")
                + ". A powder peak holds every image, so the equation must give "
                "them one value. Write it symmetrically, or average it with "
                "orbit_mean(...)")
