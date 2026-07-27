"""Geometric intensity corrections for constant-wavelength powder data."""

from __future__ import annotations

import numpy as np

from ..backend import get_backend


def lorentz_polarization(two_theta_deg: np.ndarray, polarization: float) -> np.ndarray:
    """Combined Lorentz-polarisation factor for CW powder diffraction.

        Lp(θ) = [K + (1 − K)·cos²2θ] / (sin²θ · cosθ)

    The 1/(sin²θ cosθ) Lorentz part is the standard CW powder factor
    (single-crystal rotation Lorentz × powder-ring statistics; International
    Tables C §6.2, Klug & Alexander).  K is the σ-polarised beam fraction —
    see :class:`pxrdref.schemas.instrument.Source` (K = 0.5 unpolarised lab
    beam; K ≈ 0.99 synchrotron vertical-plane diffraction).
    """
    xp = get_backend()
    tt = xp.radians(xp.asarray(two_theta_deg, dtype=np.float64))
    th = 0.5 * tt
    pol = polarization + (1.0 - polarization) * xp.cos(tt) ** 2
    return pol / (xp.sin(th) ** 2 * xp.cos(th))


def surface_roughness_suortti(two_theta_deg: np.ndarray, a: float, b: float
                              ) -> np.ndarray:
    """Bragg-Brentano surface-roughness intensity multiplier, Suortti (1972).

        R(θ) = [a + (1 − a)·exp(−b/sinθ)] / [a + (1 − a)·exp(−b)]

    normalised so R(90°) = 1.  A rough or loosely-packed flat specimen has a
    packing-density deficit in its top layer; at low θ the beam crosses that
    layer at grazing incidence over a long path, so intensity is depressed,
    increasingly so as θ → 0.  Suortti, P. (1972), *J. Appl. Cryst.* **5**,
    325–331.  Physics, not letters: ``a`` is the intensity fraction surviving at
    grazing incidence, so **1 − a bounds the depression**; ``b`` is the depleted
    layer's dimensionless optical depth, which sets **where in angle** the
    transition falls — *not* how deep it goes.  Same parameterisation as GSAS-II
    ``SurfaceRough`` (a = SRA, b = SRB) — see
    :class:`pxrdref.schemas.instrument.RoughnessSuortti`, which documents the
    non-monotonic (bimodal) dependence on ``b`` that follows from this.

    ``b = 0`` returns exactly 1.0: the numerator and the denominator become the
    *identical* float expression, so the off state is bit-identical with no
    branch (the residual stays smooth for FD/autodiff Jacobians).  For b ≥ 0 the
    result is bounded 0 < R ≤ 1 — the correction only ever depresses intensity,
    since sinθ ≤ 1 ⇒ exp(−b/sinθ) ≤ exp(−b).
    """
    xp = get_backend()
    theta = xp.radians(0.5 * xp.asarray(two_theta_deg, dtype=np.float64))
    # sinθ = 0 only at 2θ = 0, which no measured grid contains; a reflection
    # pushed off the sphere arrives here as NaN and is zeroed by the caller's
    # isfinite mask, exactly as it is for Lp.
    num = a + (1.0 - a) * xp.exp(-b / xp.sin(theta))
    den = a + (1.0 - a) * xp.exp(-b)
    return num / den


def surface_roughness_pitschke(two_theta_deg: np.ndarray, c: float, tau: float
                               ) -> np.ndarray:
    """Bragg-Brentano surface-roughness intensity multiplier, Pitschke (1993).

        R(θ) = 1 − c·u·(1 − u),        u = τ/sinθ

    Pitschke, W., Hermann, H. & Mattern, N. (1993), *Powder Diffr.* **8**,
    74–83, Eqs (13)–(18).  The paper's multiplier is (1 − P) with
    P = P₀ + C·u(1 − u); the angle-independent P₀ is factored out here because
    it is exactly degenerate with the phase scale, leaving c = C/(1 − P₀) as the
    identifiable strength and τ = t₀/β as the dimensionless roughness parameter.

    ``c = 0`` (or ``τ = 0``) returns exactly 1.0.

    **This model has a validity range and does not police it** — the caller
    does, via the ``ROUGHNESS_OUTSIDE_REGIME`` diagnostic, because the fence
    depends on the fitted 2θ range and not on the parameters alone.  u(1 − u)
    peaks at u = ½ and returns to 0 at u = 1, so R is monotone in θ only while
    sinθ ≥ 2τ; between 2τ and τ the depression turns back over (empirical, no
    geometric meaning — the paper says so); and beyond sinθ = τ, its Eq (18),
    R exceeds 1 and the "correction" would amplify intensity.  Evaluated
    unconditionally regardless, so the residual stays smooth: clamping here
    would put a kink in the Jacobian.
    """
    xp = get_backend()
    theta = xp.radians(0.5 * xp.asarray(two_theta_deg, dtype=np.float64))
    u = tau / xp.sin(theta)
    return 1.0 - c * u * (1.0 - u)


def displacement_shift_deg(theta_deg: np.ndarray, s_mm: float,
                           radius_mm: float) -> np.ndarray:
    """Bragg-Brentano sample-displacement peak shift, in degrees 2θ.

        Δ2θ = −(2·s/R)·cosθ   [radians]

    for a flat specimen whose surface sits a distance ``s`` off the goniometer
    axis (positive toward the source/detector side of the focusing circle),
    R = goniometer radius.  Wilson (1963), *Mathematical Theory of X-ray
    Powder Diffractometry*, ch. 4; Klug & Alexander (1974), ch. 5.  The cosθ
    dependence is what separates it from a constant zero-point error.
    """
    xp = get_backend()
    th = xp.radians(xp.asarray(theta_deg, dtype=np.float64))
    return xp.degrees(-2.0 * (s_mm / radius_mm) * xp.cos(th))


def transparency_shift_deg(two_theta_deg: np.ndarray, t_coef: float) -> np.ndarray:
    """Bragg-Brentano sample-transparency peak shift, in degrees 2θ.

        Δ2θ = −t·sin2θ   [radians],   t = 1/(2·μ_eff·R)

    finite beam penetration puts the effective diffracting surface below the
    physical one, pulling peaks to lower angle with a sin2θ signature
    (thick-sample limit; Klug & Alexander, 1974, ch. 5; Wilson, 1963).
    ``t_coef`` is the dimensionless coefficient t ≥ 0; for strongly absorbing
    samples t → 0 and the correction vanishes.
    """
    xp = get_backend()
    tt = xp.radians(xp.asarray(two_theta_deg, dtype=np.float64))
    return xp.degrees(-t_coef * xp.sin(tt))
