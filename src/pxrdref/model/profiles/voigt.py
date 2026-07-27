"""The true Voigt peak profile (Gaussian ⊗ Lorentzian) via the Faddeeva w(z).

The Voigt profile is the exact convolution of a Gaussian and a Lorentzian —
what the Thompson-Cox-Hastings pseudo-Voigt (``pseudovoigt.py``) approximates
as a linear blend.  It is an *opt-in* shape (``Instrument.profile.shape =
"voigt"``); TCHZ stays the default.  Its unit-area form is

    V(x; σ, γ) = Re[w(z)] / (σ√(2π)),      z = (x + iγ)/(σ√2)

with w the Faddeeva function (``faddeeva.py``; Weideman 1994).  Here σ is the
Gaussian standard deviation and γ the Lorentzian *half*-width at half maximum,
recovered from the same component FWHMs the Caglioti/sample machinery already
computes (``caglioti.py``; the instrument ⊕ sample width split is untouched):

    σ = Γ_G / (2√(2 ln 2)),      γ = Γ_L / 2.

Both limits are exact and recovered branchlessly by w(z):

* γ → 0:  z is real, Re[w] = e^{−z²}, so V → the unit Gaussian of FWHM Γ_G;
* σ → 0:  |z| → ∞, w(z) → i/(√π z), so V → the unit Lorentzian of FWHM Γ_L.

Reference for the profile and the convolution identity: Armstrong (1967),
J. Quant. Spectrosc. Radiat. Transfer 7, 61; the w(z) algorithm is Weideman
(1994), J. Numer. Anal. 31, 1497.
"""

from __future__ import annotations

import numpy as np

from ...backend import get_backend
from .faddeeva import _INV_SQRT_PI, faddeeva_w

#: Γ_G = 2√(2 ln 2)·σ  — Gaussian FWHM ↔ standard deviation
GAUSS_FWHM_TO_SIGMA = 2.0 * np.sqrt(2.0 * np.log(2.0))
_SQRT2 = np.sqrt(2.0)
_SQRT2PI = np.sqrt(2.0 * np.pi)


def fwhm_to_voigt_params(gamma_g: np.ndarray, gamma_l: np.ndarray
                         ) -> tuple[np.ndarray, np.ndarray]:
    """(σ, γ) for :func:`voigt` from component FWHMs Γ_G, Γ_L.

    The Voigt analogue of ``pseudovoigt.tch_gamma_eta`` — it consumes the exact
    same Gaussian/Lorentzian FWHMs, so a phase's size/strain split and the
    instrument U,V,W,X,Y feed both shapes identically.
    """
    xp = get_backend()
    sigma = xp.asarray(gamma_g, dtype=np.float64) / GAUSS_FWHM_TO_SIGMA
    gamma = xp.asarray(gamma_l, dtype=np.float64) / 2.0
    return sigma, gamma


def voigt(x: np.ndarray, sigma: np.ndarray, gamma: np.ndarray) -> np.ndarray:
    """Unit-area Voigt at offsets ``x`` (same units as σ, γ).

    ``sigma`` is the Gaussian standard deviation, ``gamma`` the Lorentzian
    HWHM.  Broadcasts like ``pseudovoigt.pseudo_voigt``: ``x`` may be (..., N)
    with σ/γ scalars or matching shapes.
    """
    z = (x + 1j * gamma) / (sigma * _SQRT2)
    return get_backend().real(faddeeva_w(z)) / (sigma * _SQRT2PI)


def voigt_derivs(x: np.ndarray, sigma: float, gamma: float
                 ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(V, ∂V/∂x, ∂V/∂σ, ∂V/∂γ) — closed forms for the analytic Jacobian.

    From w'(z) = −2z·w(z) + 2i/√π (Abramowitz & Stegun 7.1.20) and
    z = (x + iγ)/(σ√2) with the σ-dependent prefactor P = 1/(σ√(2π)):

        ∂z/∂x = 1/(σ√2)        ∂z/∂γ = i/(σ√2)        ∂z/∂σ = −z/σ

        ∂V/∂x = Re[w']·(1/(σ√2))·P
        ∂V/∂γ = −Im[w']·(1/(σ√2))·P
        ∂V/∂σ = −(1/σ)·(V + P·Re[z·w'])

    Slots into the ``(pV, ∂/∂x, ∂/∂w₁, ∂/∂w₂)`` contract of
    ``pseudovoigt.pseudo_voigt_derivs`` (w₁ = σ, w₂ = γ here), so the forward
    model's peak-chain Jacobian is shape-agnostic.
    """
    xp = get_backend()
    inv = 1.0 / (sigma * _SQRT2)
    z = (x + 1j * gamma) * inv
    wz = faddeeva_w(z)
    wp = -2.0 * z * wz + 2j * _INV_SQRT_PI       # w'(z)
    p = 1.0 / (sigma * _SQRT2PI)
    v = xp.real(wz) * p
    d_dx = xp.real(wp) * (inv * p)
    d_dgamma = -xp.imag(wp) * (inv * p)
    d_dsigma = -(1.0 / sigma) * (v + p * xp.real(z * wp))
    return v, d_dx, d_dsigma, d_dgamma
