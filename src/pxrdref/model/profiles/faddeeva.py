"""The Faddeeva function w(z) via the Weideman rational approximation.

    w(z) = exp(−z²)·erfc(−iz)          (Im z ≥ 0)

is the complex error (plasma dispersion) function; its real part on the line
z = (x + iγ)/(σ√2) *is* the unit-area Voigt profile (see ``voigt.py``).  This
module implements it once, on the WP-0401 backend op set, so every backend
(numpy today, jax/torch later) computes identical values *and gradients* — the
whole reason WP-0405 refuses each backend's native ``wofz``.

Algorithm — Weideman (1994), J. Numer. Anal. 31, 1497, "Computation of the
complex error function".  With the conformal map of the upper half-plane onto
the unit disc

    Z = (L + iz)/(L − iz),      L = ⁴√(1/2)·√N   (his optimal scaling),

w(z) is an N-term power series in Z whose coefficients are a single FFT of a
sampled, decaying function — computed *once* at import in plain numpy (the
compile-time discipline of ``backend/api.py``).  The per-``z`` evaluation is
then just Horner over those real coefficients plus two complex divisions:

    w(z) = 2·p(Z)/(L − iz)² + (1/√π)/(L − iz).

Why this algorithm (WP-0405 design record):

* **Branchless.**  It is one rational form over the whole upper half-plane —
  no region partition (Humlíček w4) and no continued-fraction/series switch
  (Zaghloul & Ali 2011).  That keeps the residual smooth for finite-difference
  and autodiff Jacobians (the frozen-per-stage differentiability invariant)
  and avoids ``where``-mask gymnastics the op set would otherwise force.
* **Upper half-plane only is enough.**  The Voigt argument has
  Im z = γ_L/(σ√2) ≥ 0 always (Lorentzian HWHM and Gaussian σ are both
  non-negative), so the reflection formula w(−z) = 2e^{−z²} − w(z) is never
  needed — the branchlessness is real, not hidden behind a mask.
* **Op-set native.**  The hot path uses only Python operators (``+ − * /``,
  already backend-polymorphic) and complex construction via ``1j`` — no
  ``scipy.special``, no new named op added to ``backend/api.py`` (each such op
  is a per-backend maintenance liability; WP-0401 left room but implemented
  none).  N=32 reaches ≈1e-13 over the relevant range (verified against
  ``scipy.special.wofz`` in ``tests/test_voigt.py``).

The derivative identity ``w'(z) = −2z·w(z) + 2i/√π`` (Abramowitz & Stegun
7.1.20) gives the Voigt partials in ``voigt.py`` from the same ``w`` call,
with no separate approximation to keep in sync.
"""

from __future__ import annotations

import numpy as np

#: Weideman expansion order — a documented module constant.  32 terms give
#: ~fp64 accuracy over the upper half-plane (Weideman 1994, Table 1); higher
#: N buys nothing the Voigt profile can use and each term is a Horner step.
WEIDEMAN_N = 32


def _weideman_coeffs(n: int) -> tuple[float, np.ndarray]:
    """(L, aₖ) for the ``n``-term expansion — compile-time, plain numpy.

    Follows Weideman (1994) §2 exactly: sample f(t) = e^{−t²}(L² + t²) on the
    tan-half-angle grid, FFT, and keep the first ``n`` real Fourier
    coefficients reordered highest-degree-first for Horner/``polyval``.
    """
    m = 2 * n
    m2 = 2 * m
    k = np.arange(-m + 1, m)                       # 2m−1 sample points
    L = np.sqrt(n / np.sqrt(2.0))                  # optimal scaling (Weideman)
    theta = k * np.pi / m
    t = L * np.tan(theta / 2.0)
    f = np.exp(-(t**2)) * (L**2 + t**2)
    f = np.concatenate([[0.0], f])                 # length 2m
    a = np.real(np.fft.fft(np.fft.fftshift(f))) / m2
    a = a[1 : n + 1][::-1]                          # a₀ = highest degree
    return float(L), a.astype(np.float64)


_WEIDEMAN_L, _WEIDEMAN_A = _weideman_coeffs(WEIDEMAN_N)
_INV_SQRT_PI = 1.0 / np.sqrt(np.pi)


def faddeeva_w(z):
    """w(z) = exp(−z²)·erfc(−iz) for Im(z) ≥ 0, Weideman N=32 (Weideman 1994).

    ``z`` is any backend complex array; returns w(z) on the same backend.  The
    real coefficients are frozen at import, so this is pure hot-path op-set
    arithmetic — Horner over ``_WEIDEMAN_A`` plus two complex divisions, valid
    across the whole upper half-plane without a branch.  Backend dispatch is
    automatic: every operation below is a Python operator on ``z``, so it runs
    on whichever backend produced ``z`` (numpy / jax) — no ``get_backend``
    lookup, no new named op in ``backend/api.py``.
    """
    lm = _WEIDEMAN_L - 1j * z
    zdisc = (_WEIDEMAN_L + 1j * z) / lm            # conformal map to unit disc
    # Horner in Z over the real coefficients (a₀ = highest degree)
    p = _WEIDEMAN_A[0] * zdisc + _WEIDEMAN_A[1]
    for c in _WEIDEMAN_A[2:]:
        p = p * zdisc + c
    return 2.0 * p / (lm * lm) + _INV_SQRT_PI / lm
