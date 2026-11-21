"""Thompson-Cox-Hastings pseudo-Voigt peak profile.

The pseudo-Voigt approximates the Voigt (Gaussian ⊗ Lorentzian) as

    pV(x) = η·L(x; Γ) + (1−η)·G(x; Γ)

with a single FWHM Γ and mixing η computed from the underlying Gaussian and
Lorentzian widths via the Thompson, Cox & Hastings (1987, J. Appl. Cryst. 20,
79) polynomial forms:

    Γ⁵ = Γ_G⁵ + 2.69269 Γ_G⁴Γ_L + 2.42843 Γ_G³Γ_L² + 4.47163 Γ_G²Γ_L³
         + 0.07842 Γ_G Γ_L⁴ + Γ_L⁵                                (TCH eq. 4)

    η  = 1.36603 q − 0.47719 q² + 0.11116 q³,   q = Γ_L/Γ         (TCH eq. 5)

Both component shapes are unit-area normalised so that ∫pV dx = 1 and the
reflection intensity enters purely through the prefactor in the forward model:

    G(x) = (2/Γ)·√(ln2/π)·exp(−4 ln2 · x²/Γ²)
    L(x) = (2/(πΓ)) / (1 + 4x²/Γ²)
"""

from __future__ import annotations

import numpy as np

from ...backend import get_backend

_TCH_GAMMA = (2.69269, 2.42843, 4.47163, 0.07842)
_TCH_ETA = (1.36603, -0.47719, 0.11116)
_4LN2 = 4.0 * np.log(2.0)
#: √(ln2/π) — kept as the bare root so the (2/Γ)·√(ln2/π) grouping (and hence
#: its rounding) is unchanged from the pre-shim expression
_SQRT_LN2_PI = np.sqrt(np.log(2.0) / np.pi)


def tch_gamma_eta(gamma_g: np.ndarray, gamma_l: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Combined FWHM Γ and mixing η from component FWHMs (TCH 1987)."""
    xp = get_backend()
    gg = xp.asarray(gamma_g, dtype=np.float64)
    gl = xp.asarray(gamma_l, dtype=np.float64)
    c1, c2, c3, c4 = _TCH_GAMMA
    gamma5 = (gg**5 + c1 * gg**4 * gl + c2 * gg**3 * gl**2
              + c3 * gg**2 * gl**3 + c4 * gg * gl**4 + gl**5)
    gamma = gamma5 ** 0.2
    q = xp.where(gamma > 0.0, gl / xp.where(gamma > 0.0, gamma, 1.0), 0.0)
    e1, e2, e3 = _TCH_ETA
    eta = e1 * q + e2 * q**2 + e3 * q**3
    return gamma, eta


def tch_gamma_eta_partials(gamma_g: np.ndarray, gamma_l: np.ndarray
                           ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(∂Γ/∂Γ_G, ∂Γ/∂Γ_L, ∂η/∂Γ_G, ∂η/∂Γ_L) of :func:`tch_gamma_eta`, numpy.

    Differentiated from TCH eq. 4 and 5 (Thompson, Cox & Hastings, 1987,
    J. Appl. Cryst. 20, 79): 5Γ⁴·dΓ = dP for the quintic P, q = Γ_L/Γ so
    dq = (dΓ_L − q·dΓ)/Γ, and dη = (e₁ + 2e₂q + 3e₃q²)·dq.  Zero where Γ is
    zero, as the forward's q is.  The analytic peak-equation columns chain
    through it (WP-2107); ``tests/test_peak_equations.py`` holds it to a
    complex step.
    """
    gg = np.asarray(gamma_g, dtype=np.float64)
    gl = np.asarray(gamma_l, dtype=np.float64)
    c1, c2, c3, c4 = _TCH_GAMMA
    gamma5 = (gg**5 + c1 * gg**4 * gl + c2 * gg**3 * gl**2
              + c3 * gg**2 * gl**3 + c4 * gg * gl**4 + gl**5)
    dp_dg = (5.0 * gg**4 + 4.0 * c1 * gg**3 * gl + 3.0 * c2 * gg**2 * gl**2
             + 2.0 * c3 * gg * gl**3 + c4 * gl**4)
    dp_dl = (c1 * gg**4 + 2.0 * c2 * gg**3 * gl + 3.0 * c3 * gg**2 * gl**2
             + 4.0 * c4 * gg * gl**3 + 5.0 * gl**4)
    gamma = gamma5 ** 0.2
    live = gamma > 0.0
    g_safe = np.where(live, gamma, 1.0)
    d_gamma_g = np.where(live, dp_dg / (5.0 * g_safe**4), 0.0)
    d_gamma_l = np.where(live, dp_dl / (5.0 * g_safe**4), 0.0)
    q = np.where(live, gl / g_safe, 0.0)
    e1, e2, e3 = _TCH_ETA
    de_dq = e1 + 2.0 * e2 * q + 3.0 * e3 * q * q
    d_eta_g = np.where(live, de_dq * (-q * d_gamma_g) / g_safe, 0.0)
    d_eta_l = np.where(live, de_dq * (1.0 - q * d_gamma_l) / g_safe, 0.0)
    return d_gamma_g, d_gamma_l, d_eta_g, d_eta_l


def pseudo_voigt(x: np.ndarray, gamma: np.ndarray, eta: np.ndarray) -> np.ndarray:
    """Unit-area pseudo-Voigt evaluated at offsets ``x`` (same units as Γ).

    Broadcasts: x may be (..., N) with gamma/eta scalars or matching shapes.
    """
    xp = get_backend()
    g = xp.asarray(gamma, dtype=np.float64)
    lorentz = (2.0 / (xp.pi * g)) / (1.0 + 4.0 * (x / g) ** 2)
    gauss = (2.0 / g) * _SQRT_LN2_PI * xp.exp(-_4LN2 * (x / g) ** 2)
    return eta * lorentz + (1.0 - eta) * gauss


def _components(x: np.ndarray, gamma: float):
    """(u, L, G) — the two normalised components and the reduced offset.

    Written once because :func:`pseudo_voigt_basis` and
    :func:`pseudo_voigt_derivs` must agree **to the last bit**, not merely to
    the last significant figure: they build the same Ω for the same Jacobian,
    and a 1-ulp disagreement between them is a real difference in where a
    least-squares run lands.  Note that neither agrees bitwise with
    :func:`pseudo_voigt`, which spells the same algebra as ``(x/Γ)**2`` — see
    that function.
    """
    xp = get_backend()
    u = x / gamma
    lor = (2.0 / (xp.pi * gamma)) / (1.0 + 4.0 * u * u)
    gau = (2.0 / gamma) * _SQRT_LN2_PI * xp.exp(-_4LN2 * u * u)
    return u, lor, gau


def pseudo_voigt_basis(x: np.ndarray, gamma: float, eta: float) -> np.ndarray:
    """pV alone, in ``pseudo_voigt_derivs``' own arithmetic.

    For a Jacobian caller that wants Ω and none of the partials.  It is *not*
    a synonym for :func:`pseudo_voigt`: the two spell u² differently and land
    1-2 ulp apart, and the analytic bases have always been built from this
    one.  Calling the plain form here would move a converged fit in the last
    few digits — measured, and the reason this function exists at all.
    """
    _u, lor, gau = _components(x, gamma)
    return eta * lor + (1.0 - eta) * gau


def pseudo_voigt_derivs(x: np.ndarray, gamma: float, eta: float
                        ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """(pV, ∂pV/∂x, ∂pV/∂Γ, ∂pV/∂η) — closed forms for the analytic Jacobian.

    Both components are homogeneous, (1/Γ)·f(x/Γ), so with u = x/Γ:

        ∂L/∂x = −L · (8u/Γ)/(1 + 4u²)          ∂L/∂Γ = (L/Γ)·(8u²/(1+4u²) − 1)
        ∂G/∂x = −G · 8ln2·u/Γ                  ∂G/∂Γ = (G/Γ)·(8ln2·u² − 1)
        ∂pV/∂η = L − G
    """
    u, lor, gau = _components(x, gamma)
    pv = eta * lor + (1.0 - eta) * gau
    dl_dx = -lor * (8.0 * u / gamma) / (1.0 + 4.0 * u * u)
    dg_dx = -gau * (2.0 * _4LN2 * u / gamma)
    d_dx = eta * dl_dx + (1.0 - eta) * dg_dx
    dl_dgamma = (lor / gamma) * (8.0 * u * u / (1.0 + 4.0 * u * u) - 1.0)
    dg_dgamma = (gau / gamma) * (2.0 * _4LN2 * u * u - 1.0)
    d_dgamma = eta * dl_dgamma + (1.0 - eta) * dg_dgamma
    return pv, d_dx, d_dgamma, lor - gau
