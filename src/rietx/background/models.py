"""Refinable background models (evaluation used by the forward model)."""

from __future__ import annotations

import math

import numpy as np


def chebyshev_design_matrix(two_theta: np.ndarray, n_terms: int,
                            tt_min: float, tt_max: float) -> np.ndarray:
    """Design matrix T of shape (n_terms, n_points) of shifted Chebyshev
    polynomials of the first kind on x = 2(2θ−min)/(max−min) − 1.

    The background is linear in its coefficients, y_bkg = cᵀ·T, so these rows
    are also the *exact* Jacobian columns for the coefficients.
    """
    x = 2.0 * (np.asarray(two_theta, dtype=np.float64) - tt_min) / (tt_max - tt_min) - 1.0
    T = np.empty((n_terms, len(x)), dtype=np.float64)
    if n_terms > 0:
        T[0] = 1.0
    if n_terms > 1:
        T[1] = x
    for n in range(2, n_terms):
        T[n] = 2.0 * x * T[n - 1] - T[n - 2]
    return T


def chebyshev_background(two_theta: np.ndarray, coefficients: np.ndarray,
                         tt_min: float, tt_max: float) -> np.ndarray:
    T = chebyshev_design_matrix(two_theta, len(coefficients), tt_min, tt_max)
    return np.asarray(coefficients, dtype=np.float64) @ T


#: How far past the ends of a fixed curve a fitted channel may sit before
#: :func:`interpolate_fixed` refuses, as a multiple of the curve's own median
#: step.  One step, because that is the width of the disagreement two scans of
#: the same range can have and still be the same range: a blank ending at
#: 49.995° under a specimen ending at 49.996° is a grid offset, and a blank
#: ending at 50° under a specimen ending at 70° is twenty degrees of invention.
#: Inside the slack the end value is carried, which is what ``np.interp`` did
#: everywhere before WP-1309.
FIXED_RANGE_SLACK_STEPS = 1.0


def interpolate_fixed(two_theta: np.ndarray, fixed_tt: np.ndarray,
                      fixed_y: np.ndarray) -> np.ndarray:
    """Fixed background curve sampled onto the pattern grid (held, never
    subtracted — it is added inside the model so weights stay correct).

    **A channel the curve does not cover is refused, not invented.**  Bare
    ``np.interp`` clamps to the end values with no warning, so a blank measured
    over 0.5-50° under a specimen scanned to 70° contributes a flat twenty
    degrees of somebody else's counts and nothing says so.  The refusal is the
    ``schemas.project.check_interval`` precedent: a range that does not cover
    the question asked of it is the caller's to fix, by cropping the fit range
    or by measuring a longer blank.  :data:`FIXED_RANGE_SLACK_STEPS` is the
    tolerance, and it exists because two scans of the same nominal range
    disagree at their ends by about one step.

    Two shapes of curve are refused before the range is even asked about,
    because for them ``ft[0]`` and ``ft[-1]`` are not the range and the guard
    above would pass while ``np.interp`` clamped anyway.  A curve of fewer than
    two points has no range at all: ``np.interp`` carries its single value flat
    across the whole pattern, which is the clamp this function exists to
    refuse.  An unsorted curve has a range its endpoints do not name, and
    ``np.interp`` reads every channel off whichever neighbours happen to
    bracket it in array order.  Equal abscissae are allowed — a repeated point
    is a tie ``np.interp`` resolves, not a wrong range.
    """
    tt = np.asarray(two_theta, dtype=np.float64)
    ft = np.asarray(fixed_tt, dtype=np.float64)
    fy = np.asarray(fixed_y, dtype=np.float64)
    if len(ft) < 2:
        raise ValueError(
            f"the fixed background curve has {len(ft)} point(s), so it has no "
            "2θ range to interpolate over and every fitted channel would take "
            "the same value; supply a curve that covers the fit")
    if bool(np.any(np.diff(ft) < 0.0)):
        raise ValueError(
            "the fixed background curve's 2θ values decrease somewhere, so its "
            "first and last points are not its range and each channel would be "
            "read off whichever neighbours bracket it in array order; sort the "
            "curve by 2θ")
    if len(tt):
        slack = FIXED_RANGE_SLACK_STEPS * float(np.median(np.diff(ft)))
        lo, hi = float(ft[0]) - slack, float(ft[-1]) + slack
        tt_lo, tt_hi = float(tt.min()), float(tt.max())
        ends = ([] if tt_lo >= lo else ["below"]) + ([] if tt_hi <= hi else ["above"])
        if ends:
            raise ValueError(
                f"the fixed background curve covers {ft[0]:.4f}-{ft[-1]:.4f}° "
                f"2θ and the fit covers {tt_lo:.4f}-{tt_hi:.4f}°: "
                f"{' and '.join(ends)} its range there is nothing to "
                "interpolate, and carrying the end value would add counts the "
                "curve never measured. Crop the fit range (two_theta_min/"
                "two_theta_max) or supply a curve that covers it")
    return np.interp(tt, ft, fy)


def bspline_design_matrix(two_theta: np.ndarray, breakpoints: np.ndarray
                          ) -> np.ndarray:
    """Clamped cubic B-spline design matrix, shape (n_breaks + 2, n_points).

    Knot vector t = [b₀]*3 + breakpoints + [b_m]*3 (de Boor); the background
    is linear in the coefficients, so these rows are exact Jacobian columns —
    the same property the Chebyshev design has.  Points outside the
    breakpoint span are clamped to the ends (flat extrapolation of the basis)
    so a cropped fit range never errors.
    """
    x = np.asarray(two_theta, dtype=np.float64)
    b = np.asarray(breakpoints, dtype=np.float64)
    from scipy.interpolate import BSpline

    t = np.concatenate([[b[0]] * 3, b, [b[-1]] * 3])
    eps = 1e-12 * max(b[-1] - b[0], 1.0)
    xc = np.clip(x, b[0], b[-1] - eps)
    design = BSpline.design_matrix(xc, t, 3).toarray().T  # (n_basis, n_points)
    return np.ascontiguousarray(design)


def second_difference_matrix(n: int) -> np.ndarray:
    """The (n−2, n) second-difference operator D₂ used by the P-spline
    penalty rows √λ·D₂·c (Eilers & Marx, 1996, Stat. Sci. 11, 89)."""
    d = np.zeros((max(n - 2, 0), n), dtype=np.float64)
    for i in range(n - 2):
        d[i, i:i + 3] = (1.0, -2.0, 1.0)
    return d


def pspline_penalty_scale(sigma: np.ndarray, n_coef: int) -> float:
    """√(m)/σ̄, the factor that makes the P-spline's λ a pure number.

    The penalty rows are √λ·D₂c (Eilers & Marx, 1996, Stat. Sci. 11, 89),
    with c in intensity units, while every data row is divided by its σ.  So
    λ on its own carries units of inverse intensity squared: multiply y and σ
    by k and the data rows do not move while the penalty's effective weight
    moves by k² (WP-1454 measured an 8-knot background go from unpenalised to
    a straight line on a unit change alone).  Dividing the rows by σ̄, the
    median σ over the fitted channels, removes the units.  Multiplying them by
    √m, with m the fitted channels per coefficient, removes the sampling
    density: the data's own weight on one coefficient grows as m/σ̄², so this
    measures λ against it, and a 0.001° synchrotron scan and a 0.02° lab scan
    of one curve at one knot spacing take the same λ to mean the same thing.

    Derived, not measured: a background feature of width W then costs about
    λ·(h/W)⁴ of the fit it buys, with h the knot spacing, so λ = 1 suppresses
    features narrower than about one knot spacing and leaves wider ones to the
    data.  The O(1) constant in that is not computed.  Both inputs are frozen
    at stage compile, like σ itself.  m counts every coefficient, so it holds
    as stated only while the knots span the fitted channels, which
    ``auto_background(two_theta_limits=…)`` arranges.  Knots past the fitted
    range make the penalty weaker than λ says on the coefficients that do see
    data.
    """
    sigma = np.asarray(sigma, dtype=np.float64)
    return float(np.sqrt(sigma.size / n_coef) / np.median(sigma))


#: −4 ln 2, the Gaussian's FWHM normalisation, as one named constant so the
#: numpy and traced evaluations cannot spell it two ways.  The association is
#: fixed too: ``FOUR_LN2_NEG * (u * u)`` with u = (2θ − 2θ₀)/Γ, one spelling,
#: because unlike the Bragg profile there is no second caller with a reason to
#: reproduce a different one (root CLAUDE.md → Conventions, the two-Ω rule:
#: the point is that each caller owns *which* spelling it reproduces, and here
#: there is only one to own).
FOUR_LN2_NEG = -4.0 * math.log(2.0)


def hump_curve(two_theta, position, height, fwhm, xp):
    """One explicit broad background Gaussian, evaluated on the whole grid.

        y(2θ) = h · exp[ −4 ln2 · ((2θ − 2θ₀)/Γ)² ]

    The evaluator for :class:`rietx.schemas.instrument.HumpComponent`, and the
    **only** one: :meth:`rietx.model.forward.CompiledModel.background` calls it
    for the numpy path and, through ``get_backend()``, for every traced backend,
    so there is no twin to drift (``backend/traced.py``'s reason for existing,
    satisfied by having nothing to copy).  Its derivative has a second spelling,
    :func:`hump_partials`, which the numpy Jacobian reads.  A change to the form
    here changes that function too, and a complex-step test in
    ``tests/test_extra_components.py`` fails until it does.

    Empirical basis function, not a peak shape — see
    :class:`~rietx.schemas.instrument.HumpComponent` for the citation of the
    *practice* and the note that no physical derivation is claimed.

    ``two_theta`` must already be lifted onto ``xp`` by the caller: it is a
    frozen constant and ``position`` is θ-derived, so a bare ndarray here would
    be a frozen numpy constant on the left of a python operator against a traced
    value (root CLAUDE.md → Conventions: raises on torch, mis-routes under
    functorch).  ``height`` and ``fwhm`` are 0-d traced scalars; ``fwhm`` is
    floored away from zero by the schema, so the division has no pole.

    Whole-grid, no frozen window — the term is broad *by declaration*, which is
    what makes it a background feature, so a window would be the whole grid.
    """
    u = (two_theta - position) / fwhm
    return height * xp.exp(FOUR_LN2_NEG * (u * u))


def hump_partials(two_theta: np.ndarray, position: float, height: float,
                  fwhm: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The three partial derivatives of :func:`hump_curve`, in field order.

    Returns ``(∂y/∂2θ₀, ∂y/∂h, ∂y/∂Γ)``, the order of
    :data:`~rietx.schemas.instrument.HUMP_FIELDS`.  With
    u = (2θ − 2θ₀)/Γ and g = exp(−4 ln2 · u²), so that y = h·g:

        ∂y/∂h   = g
        ∂y/∂2θ₀ = h·g · 8 ln2 · u/Γ
        ∂y/∂Γ   = h·g · 8 ln2 · u²/Γ

    The last two follow from ∂u/∂2θ₀ = −1/Γ and ∂u/∂Γ = −u/Γ, each multiplied
    by ∂g/∂u = −8 ln2 · u · g.  They are differentiated here rather than
    copied from a source, and ``tests/test_extra_components.py`` checks them
    against a complex-step derivative of :func:`hump_curve`, which is exact
    to rounding.

    The analytic Jacobian reads these for a hump column (WP-2116), so a
    column costs one exponential on the grid and no Bragg evaluation.  numpy
    only: the traced backends differentiate :func:`hump_curve` themselves.
    ``u`` and ``g`` are spelled as :func:`hump_curve` spells them.
    """
    u = (np.asarray(two_theta, dtype=np.float64) - position) / fwhm
    g = np.exp(FOUR_LN2_NEG * (u * u))
    slope = (-2.0 * FOUR_LN2_NEG) * (height * g) / fwhm
    return slope * u, g, slope * (u * u)
