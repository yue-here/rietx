"""Angular dependence of profile widths — instrument ⊕ sample split.

Gaussian *variance* (variances add under convolution):

    Γ_G²(θ) = (U + Us)·tan²θ + V·tanθ + W + P/cos²θ     [deg² 2θ]

U, V, W are the instrument resolution function (Caglioti, Paoletti & Ricci,
1958, Nucl. Instrum. 3, 223); the sample adds a Gaussian microstrain term
Us·tan²θ and a Gaussian size term P/cos²θ (the GSAS ``P``; Larson & Von
Dreele, 2004, GSAS manual; Thompson, Cox & Hastings, 1987, J. Appl. Cryst.
20, 79).

Lorentzian FWHM (Lorentzian convolution adds FWHMs):

    Γ_L(θ) = (X + Xs)/cosθ + (Y + Ys)·tanθ              [deg 2θ]

The 1/cosθ (and 1/cos²θ variance) terms carry Scherrer crystallite-size
broadening and the tanθ (tan²θ) terms microstrain broadening.  Note the
letter conventions differ between codes (GSAS: X=size, Y=strain; FullProf
swaps them) — this module documents the *physics* via argument names.
"""

from __future__ import annotations

import numpy as np

from ...backend import get_backend

_MIN_GAMMA_G2 = 1e-8  # deg²; keeps Γ_G real when U,V,W make the quadratic dip


def gaussian_fwhm(theta_deg: np.ndarray, u: float, v: float, w: float,
                  gauss_size: float = 0.0, gauss_strain: float = 0.0) -> np.ndarray:
    """Γ_G(θ) from the Caglioti law + sample Gaussian size/strain variances;
    input θ (NOT 2θ) in degrees."""
    xp = get_backend()
    th = xp.radians(theta_deg)
    t = xp.tan(th)
    g2 = (u + gauss_strain) * t * t + v * t + w
    # unconditional (purity (b)): gauss_size = 0 adds an exact ±0, and the
    # variance floor below absorbs any −0.0 sign flip
    c = xp.cos(th)
    g2 = g2 + gauss_size / (c * c)
    return xp.sqrt(xp.maximum(g2, _MIN_GAMMA_G2))


def lorentzian_fwhm(theta_deg: np.ndarray, x_size: float, y_strain: float,
                    aniso_strain=0.0) -> np.ndarray:
    """Γ_L(θ) = x_size/cosθ + (y_strain + aniso_strain)·tanθ; θ in degrees.

    ``aniso_strain`` is Λ(hkl) from the Stephens anisotropic-strain model
    (:mod:`pxrdref.crystallography.stephens`) — a **per-reflection** array in
    the same deg-2θ FWHM units as ``y_strain``, which is why it enters the same
    tanθ slot rather than getting a law of its own.  It defaults to an exact
    ±0, so a phase without a microstrain block is bit-identical.
    """
    xp = get_backend()
    th = xp.radians(theta_deg)
    return x_size / xp.cos(th) + (y_strain + aniso_strain) * xp.tan(th)
