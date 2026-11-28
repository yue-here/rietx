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
#: Olivero & Longbothum (1977)'s two coefficients (a, b) in
#: Γ_V ≈ a·Γ_L + √(b·Γ_L² + Γ_G²) — the combined width :func:`voigt_fwhm` reports
_OLIVERO_FWHM = (0.5346, 0.2166)


def voigt_fwhm(gamma_g: np.ndarray, gamma_l: np.ndarray) -> np.ndarray:
    """FWHM of the exact Voigt from its component FWHMs Γ_G, Γ_L.

    Γ_V ≈ 0.5346·Γ_L + √(0.2166·Γ_L² + Γ_G²), Olivero & Longbothum (1977),
    J. Quant. Spectrosc. Radiat. Transfer 17, 233.  Measured against a
    bisected Faddeeva FWHM across the mixing range it is within 0.024 % worst,
    near Γ_L ≈ 0.28·Γ_G (``tests/test_voigt.py``); exact in the Gaussian limit
    and 3.1e-6 above exact in the Lorentzian one (0.5346 + √0.2166).

    The *reported* width of the opt-in ``shape="voigt"``
    (:meth:`~rietx.model.forward.CompiledModel.peak_fwhm`).  It is not the TCH
    quintic (``pseudovoigt.tch_gamma_eta``, 0.43 % worst), which stays what
    window sizing and FCJ node counts read under either shape: those are
    frozen per stage and approximate by design, and a reported width is not.
    """
    a, b = _OLIVERO_FWHM
    gl = np.asarray(gamma_l, dtype=np.float64)
    gg = np.asarray(gamma_g, dtype=np.float64)
    return a * gl + np.sqrt(b * gl * gl + gg * gg)


def fwhm_to_voigt_params(gamma_g: np.ndarray, gamma_l: np.ndarray
                         ) -> tuple[np.ndarray, np.ndarray]:
    """(σ, γ) for :func:`voigt` from component FWHMs Γ_G, Γ_L.

    The Voigt analogue of ``pseudovoigt.tch_gamma_eta`` — it consumes the exact
    same Gaussian/Lorentzian FWHMs, so a phase's size/strain split and the
    instrument U,V,W,X,Y feed both shapes identically.

    **Both widths change measure across this call, and only one changes name.**
    The arguments are *full* widths at half maximum, the package's width
    convention everywhere; the second return is the Lorentzian *half* width, as
    the Voigt form of the module docstring requires.  So ``gamma_l`` and the
    returned γ differ by a factor of two while sharing a letter, which is why
    the local below is spelled out.  A caller reading the return as a FWHM gets
    a peak half the width it asked for.
    """
    xp = get_backend()
    sigma = xp.asarray(gamma_g, dtype=np.float64) / GAUSS_FWHM_TO_SIGMA
    gamma_hwhm = xp.asarray(gamma_l, dtype=np.float64) / 2.0
    return sigma, gamma_hwhm


def voigt(x: np.ndarray, sigma: np.ndarray, gamma: np.ndarray) -> np.ndarray:
    """Unit-area Voigt at offsets ``x`` (same units as σ, γ).

    ``sigma`` is the Gaussian standard deviation, ``gamma`` the Lorentzian
    HWHM.  Broadcasts like ``pseudovoigt.pseudo_voigt``: ``x`` may be (..., N)
    with σ/γ scalars or matching shapes.
    """
    z = (x + 1j * gamma) / (sigma * _SQRT2)
    return get_backend().real(faddeeva_w(z)) / (sigma * _SQRT2PI)


def _reduced(x: np.ndarray, sigma: float, gamma: float):
    """(1/(σ√2), 1/(σ√(2π)), z, w(z)) — the shared front half.

    :func:`voigt_basis` and :func:`voigt_derivs` build the same Ω for the same
    Jacobian, so they must agree to the last bit and not merely to the last
    significant figure; writing the reduction once is what makes that true by
    construction.  :func:`voigt` divides where this multiplies by a reciprocal
    and so lands ~1 ulp away — see :func:`voigt_basis`.
    """
    inv = 1.0 / (sigma * _SQRT2)
    z = (x + 1j * gamma) * inv
    return inv, 1.0 / (sigma * _SQRT2PI), z, faddeeva_w(z)


def voigt_basis(x: np.ndarray, sigma: float, gamma: float) -> np.ndarray:
    """V alone, in ``voigt_derivs``' own arithmetic — the Voigt-shape twin of
    ``pseudovoigt.pseudo_voigt_basis``, and not a synonym for :func:`voigt`.
    """
    _inv, p, _z, wz = _reduced(x, sigma, gamma)
    return get_backend().real(wz) * p


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
    inv, p, z, wz = _reduced(x, sigma, gamma)
    wp = -2.0 * z * wz + 2j * _INV_SQRT_PI       # w'(z)
    v = xp.real(wz) * p
    d_dx = xp.real(wp) * (inv * p)
    d_dgamma = -xp.imag(wp) * (inv * p)
    d_dsigma = -(1.0 / sigma) * (v + p * xp.real(z * wp))
    return v, d_dx, d_dsigma, d_dgamma
