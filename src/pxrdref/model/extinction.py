"""Secondary extinction — the Sabine polycrystalline model.

Extinction is the attenuation of a strong reflection because the diffracted
beam is itself re-diffracted back into the incident beam inside a coherently
scattering domain.  It is *not* a peak-shape effect: it removes intensity from
the integrated area of the strongest (usually low-angle, large-|F|)
reflections, so an uncorrected refinement compensates with a spuriously large
Biso and a spuriously small scale.

For a powder Sabine (1988) blends the Bragg (backscattering) and Laue
(forward-scattering) two-beam limits by the fraction of the crystal in each
geometry, which for a random powder is sin²θ and cos²θ respectively:

    E(hkl) = E_B·sin²θ + E_L·cos²θ

    E_B = 1/√(1 + x)                                  Bragg component
    E_L = 1 + Σ_{i=1..6} c_i·x^i        (0 < x ≤ 1)   Laue series
        = √(2/πx)·(1 − 1/8x)           (x > 1)        Laue asymptote
        = 1                            (x ≤ 0)

The dimensionless extinction variable carries the coupling to the structure
and the cell,

    x = ext · |F|² · (λ/V)² · Xpol,     Xpol = 0.079411·(1 + cos²2θ)/2   (X-ray)

with ``ext`` the refinable per-phase coefficient (``Phase.extinction``), |F|²
the calculated structure factor squared *without* multiplicity or Lp, λ the
emission-line wavelength, V the cell volume and Xpol the unpolarised X-ray
prefactor.  ``ext = 0 ⇒ x = 0 ⇒ E ≡ sin²θ + cos²θ = 1`` exactly, so the
correction is the identity when off.

**Convention (documented by physics, not letter).** The *Bragg* component
weights **sin²θ** and the *Laue* component cos²θ — the opposite of the naive
reading, because backscattering (2θ→180°, sin²θ→1) is the Bragg-case limit and
forward scattering (2θ→0°, cos²θ→1) is the Laue-case limit.  This is Sabine's
result and matches GSAS-II ``GetPwdrExt``.

**The two Laue branches do not join continuously at x = 1**: the six-term
series gives E_L(1⁻) ≈ 0.6742 and the two-term asymptote E_L(1⁺) ≈ 0.6981, a
~2% step (the asymptotic expansion is only accurate for x ≫ 1).  This is
inherited verbatim from GSAS-II and is out of reach for real powder data,
where x ≪ 1 keeps every reflection on the smooth series branch; it is *not*
smoothed, because doing so would break the cross-code golden.  E stays
continuous at x = 0 (both branches → 1) so the identity-when-off case is exact.

References
----------
* Sabine, T. M. (1985). *Aust. J. Phys.* 38, 507 — extinction in
  polycrystalline materials.
* Sabine, T. M. (1988). *Acta Cryst.* A44, 368 — reconciliation of the
  Zachariasen and Darwin theories (the sin²θ/cos²θ blend).
* Sabine, Von Dreele & Jørgensen (1988). *Acta Cryst.* A44, 374 — the model
  as used in a Rietveld refinement.

The parameterization (the Xpol constant 0.079411, the Laue-series coefficients,
and the x>1 asymptote kept to two terms) is adopted verbatim from GSAS-II
``GetPwdrExt`` as the cross-code golden target; GSAS-II is a behavioral
reference only and no code is ported (see ATTRIBUTION.md).
"""

from __future__ import annotations

import numpy as np

#: Sabine Laue-series coefficients c₁…c₆ (E_L = 1 + Σ cᵢ xⁱ on 0 < x ≤ 1),
#: the exact values GSAS-II ``GetPwdrExt`` uses.
_LAUE_COEF = np.array(
    [-0.5, 0.25, -0.10416667, 0.036458333, -0.0109375, 2.8497409e-3],
    dtype=np.float64,
)
#: X-ray extinction prefactor constant: Xpol = _XPOL·(1 + cos²2θ)/2.
_XPOL = 0.079411
#: √(2/π) — the leading factor of the x>1 Laue asymptote.
_PI2 = float(np.sqrt(2.0 / np.pi))


def _extinction_x(f2: np.ndarray, wavelength: float, volume: float,
                  two_theta_deg: np.ndarray, ext: float
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(x, sin²θ, cos²θ) for the Sabine variable x = ext·|F|²·(λ/V)²·Xpol.

    x is per reflection (|F|², 2θ arrays) and per emission line (λ enters as
    (λ/V)²), which is why the caller evaluates this inside the line loop.
    """
    f2 = np.asarray(f2, dtype=np.float64)
    theta = np.radians(0.5 * np.asarray(two_theta_deg, dtype=np.float64))
    sth2 = np.sin(theta) ** 2
    cos2th = 1.0 - 2.0 * sth2  # cos 2θ = 1 − 2 sin²θ
    xpol = _XPOL * (1.0 + cos2th ** 2) / 2.0
    x = ext * f2 * (wavelength / volume) ** 2 * xpol
    return x, sth2, 1.0 - sth2


def _laue_and_deriv(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """E_L(x) and dE_L/dx over the three Sabine regimes (branchless select).

    The series (a polynomial) is safe to evaluate everywhere; the x>1
    asymptote is evaluated on a clamped ``xsafe`` so its 1/x terms never
    divide by zero in the discarded branch.  At x ≤ 0 the Laue factor is 1 and
    its reported derivative is 0 (GSAS-II's convention — the value is
    continuous there, the derivative has a step of c₁ that is harmless because
    the chain factor multiplies it by x → 0).
    """
    x = np.asarray(x, dtype=np.float64)
    series = np.ones_like(x)
    dseries = np.zeros_like(x)
    for i in range(6):
        series = series + _LAUE_COEF[i] * x ** (i + 1)
        dseries = dseries + (i + 1) * _LAUE_COEF[i] * x ** i
    xsafe = np.where(x > 0.0, x, 1.0)
    inv_sqrt = 1.0 / np.sqrt(xsafe)
    asym = _PI2 * (1.0 - 0.125 / xsafe) * inv_sqrt
    dasym = _PI2 * inv_sqrt * (-0.5 / xsafe + 0.1875 / xsafe ** 2)
    el = np.where(x <= 0.0, 1.0, np.where(x <= 1.0, series, asym))
    dl = np.where(x <= 0.0, 0.0, np.where(x <= 1.0, dseries, dasym))
    return el, dl


def sabine_extinction(f2: np.ndarray, wavelength: float, volume: float,
                      two_theta_deg: np.ndarray, ext: float) -> np.ndarray:
    """Extinction multiplier E(hkl) per reflection (Sabine 1988).

    Forward-only path used inside ``CompiledModel.phase_peaks``; the intensity
    is multiplied by this.  ``ext = 0`` returns exactly 1.
    """
    x, sth2, cth2 = _extinction_x(f2, wavelength, volume, two_theta_deg, ext)
    eb = np.where(x > -1.0, 1.0 / np.sqrt(np.where(x > -1.0, 1.0 + x, 1.0)), 1.0)
    el, _ = _laue_and_deriv(x)
    return eb * sth2 + el * cth2


def sabine_extinction_and_dx(f2: np.ndarray, wavelength: float, volume: float,
                             two_theta_deg: np.ndarray, ext: float
                             ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(E, dE/dx, x) — the Jacobian-support path.

    ``dE/dx`` is the derivative w.r.t. the extinction variable x (not ext).
    Because x ∝ |F|², a structural parameter p that moves |F|² changes both
    the |F|² prefactor and x, and the exact chain factor for the analytic
    coordinate/ADP columns is ``G = E + x·dE/dx`` (see
    ``CompiledModel._structural_intensity_grad``).  The ``scale``/``occ``/
    ``biso``/``cell``/``extinction`` columns need nothing from here — they go
    through the finite-difference-of-``phase_peaks`` chain, which already sees
    the folded-in E.
    """
    x, sth2, cth2 = _extinction_x(f2, wavelength, volume, two_theta_deg, ext)
    onepx = np.where(x > -1.0, 1.0 + x, 1.0)
    eb = np.where(x > -1.0, 1.0 / np.sqrt(onepx), 1.0)
    deb = np.where(x > -1.0, -0.5 / (onepx * np.sqrt(onepx)), 0.0)
    el, dl = _laue_and_deriv(x)
    return eb * sth2 + el * cth2, deb * sth2 + dl * cth2, x
