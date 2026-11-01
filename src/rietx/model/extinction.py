"""Primary extinction — the Sabine polycrystalline model.

Extinction is the attenuation of a strong reflection because the diffracted
beam is itself re-diffracted back into the incident beam inside a coherently
scattering domain, a mosaic block.  That is *primary* extinction, and it is the
only extinction mechanism that operates in a powder (Sabine, Von Dreele &
Jørgensen 1988, p. 375); the powder counterpart of secondary extinction, the
attenuation of the beam by other blocks of the same orientation, is multiple
scattering, which this model does not describe.  ``ext`` is therefore a squared
block size D², in µm², not a secondary-extinction (mosaic-spread) coefficient.
It is *not* a peak-shape effect: it removes intensity from the integrated area
of the strongest (usually low-angle, large-|F|) reflections, so an uncorrected
refinement compensates with a spuriously large Biso and a spuriously small
scale.

Sabine (1988, eq. 17) gives the extinction factor at scattering angle 2θ as
the average of the Laue (forward-scattering) and Bragg (backscattering)
two-beam solutions, weighted cos²θ and sin²θ respectively:

    E(hkl) = E_B·sin²θ + E_L·cos²θ

    E_B = 1/√(1 + x)                                  Bragg component
    E_L = e^(−x)·[I₀(x) + I₁(x)]       (x ≥ 0)        Laue component
        = 1                            (x < 0)

with I₀ and I₁ the modified Bessel functions of the first kind.  The
dimensionless extinction variable carries the coupling to the structure and
the cell,

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

**The Laue component is one function, and the papers print two expansions of
it.**  Sabine, Von Dreele & Jørgensen (1988, eqs 3-4) give E_L as the series
1 − x/2 + x²/4 − 5x³/48 + 7x⁴/192 for x ≤ 1 and the asymptote
√(2/πx)·[1 − 1/8x − 3/128x² − 15/1024x³] above it.  They defer the derivation
to Sabine (1988).  Sabine's chapter in ITC Vol. C (2006, §6.4.5, eqs 6.4.5.3-4)
prints the same pair and states how it was built.  The Laue-case diffracted
fraction ½[1 − exp(−2σD)] of eq. 6.4.4.3, with a Lorentzian σ(k), is integrated
over k and divided by the kinematic intensity.  That integral is

    E_L(x) = (1/πx)·∫ ½[1 − exp(−2x/(1 + u²))] du,   u over the real line,

and it equals e^(−x)·[I₀(x) + I₁(x)].  A quadrature of the integral agrees
with the closed form to 3e-16 relative from x = 0.001 to 100 (WP-2044).  The
closed form is derived here from ITC's stated construction.  Neither source
prints it.  Its Taylor series reproduces the paper's c₁…c₄ and gives
c₅ = −7/640, and its asymptotic series reproduces the paper's four terms.

**Each truncated pair steps at the x = 1 switch.**  The paper's pair steps by
2.2 % (0.68229 to 0.66776).  GSAS-II's six-term series and two-term asymptote
(``GetPwdrExt``, 5.8.4) step by 3.6 % (0.67420 to 0.69815), and rietx carried
that pair until WP-2044.  Real powder data reach the step.  On the QPA guide's
first fit (``examples/guides/qpa.py``: 11-BM NAC with a CaF₂ impurity), CaF₂'s
11 reflections reach x = 6.49 at the answer.  Five of them lie above x = 1, and
one sits at x = 1.0000.  The solver parked extinction on the step there, and
the esd depended on whether the last Jacobian straddled it: CaF₂ came out
3.08 ± 0.21 wt% on GitHub's macOS runner and 3.08 ± 2.24 wt% on Linux.  The closed form
has no step, and E_L(1) = 0.673670022943349.

**GSAS-II is the behavioural reference this departs from.**  Against its two
branches the closed form differs, relative to E_L, by 4e-8 at x = 0.25,
5.6e-6 at 0.5, 7.9e-4 just below x = 1, 3.6e-2 just above it, 9.8e-3 at 2 and
1.1e-3 at 5.  ``tests/test_extinction.py`` holds that band.  The Xpol
constant 0.079411 is GSAS-II's and is unchanged.  No code is ported (see ATTRIBUTION.md).

References
----------
* Sabine, T. M. (1985). *Aust. J. Phys.* 38, 507 — extinction in
  polycrystalline materials.
* Sabine, T. M. (1988). *Acta Cryst.* A44, 368 — reconciliation of extinction
  theories: the Laue and Bragg solutions (eqs 6, 11) and their angular blend
  (eq. 17).
* Sabine, Von Dreele & Jørgensen (1988). *Acta Cryst.* A44, 374 — the model
  as used in a Rietveld refinement; the Laue series and asymptote (eqs 3-4).
* Sabine, T. M. (2006). *International Tables for Crystallography* Vol. C,
  3rd ed., §6.4.5 — the Laue-case fraction (eq. 6.4.4.3) and the construction
  of the Laue expansions from it (eqs 6.4.5.3-4).
"""

from __future__ import annotations

import numpy as np

from ..backend import get_backend

#: X-ray extinction prefactor constant: Xpol = _XPOL·(1 + cos²2θ)/2.
_XPOL = 0.079411
#: 2⁻¹²⁶, the smallest normal fp32 number: the shift that gives autodiff the
#: one-sided Laue slope at x = 0 and moves no fp64 value
#: (see ``_laue_and_deriv``).
_ARG_SHIFT = 2.0 ** -126


def _extinction_x(f2: np.ndarray, wavelength: float, volume: float,
                  two_theta_deg: np.ndarray, ext: float
                  ) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(x, sin²θ, cos²θ) for the Sabine variable x = ext·|F|²·(λ/V)²·Xpol.

    x is per reflection (|F|², 2θ arrays) and per emission line (λ enters as
    (λ/V)²), which is why the caller evaluates this inside the line loop.
    """
    xp = get_backend()
    f2 = xp.asarray(f2, dtype=np.float64)
    theta = xp.radians(0.5 * xp.asarray(two_theta_deg, dtype=np.float64))
    sth2 = xp.sin(theta) ** 2
    cos2th = 1.0 - 2.0 * sth2  # cos 2θ = 1 − 2 sin²θ
    xpol = _XPOL * (1.0 + cos2th ** 2) / 2.0
    x = ext * f2 * (wavelength / volume) ** 2 * xpol
    return x, sth2, 1.0 - sth2


def _laue_and_deriv(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """E_L(x) and dE_L/dx, from the modified Bessel functions (branchless select).

    In code E_L = i0e(x) + i1e(x), the exponentially scaled I₀ and I₁, and
    dE_L/dx = −i1e(x)/x, which tends to −1/2 at x → 0.  Both are finite for
    every x ≥ 0.  The scaling keeps them finite at large x too, where I₀ and I₁
    alone overflow past x ≈ 713.

    At x < 0 the Laue factor is 1 and its reported derivative is 0 (GSAS-II's
    convention).  The value is continuous there.  The derivative steps by −1/2,
    which is harmless because the chain factor multiplies it by x → 0.  At
    x = 0 itself the Bessel arm is selected.  Its value there is exactly 1, so
    no number moves, and its slope is −1/2, the derivative from inside the
    ``ext ≥ 0`` floor.  Selected as the constant, x = 0 handed autodiff a slope
    of 0, and jax's extinction column on a coefficient at its floor read 0.78
    from the analytic one (WP-1938).

    **The argument is shifted by 2⁻¹²⁶ (``_ARG_SHIFT``) so that autodiff takes
    the one-sided slope at x = 0.**  The scaled functions carry e^(−|x|), so jax
    and torch differentiate i0e through sign(x), and sign(0) = 0.  Unshifted,
    both backends return +1/2 for dE_L/dx at x = 0 exactly, the wrong sign
    (measured, WP-2044).  2⁻¹²⁶ is the smallest normal fp32 number, so the shift
    survives on the fp32 device too.  It moves no fp64 value: x + 2⁻¹²⁶ equals x
    for every x ≥ 2⁻⁷², and below that E_L rounds to exactly 1 either way
    (checked on 2·10⁵ values from 1e-323 to 1e3).  It also removes the 0/0 of
    i1e(x)/x at x = 0.

    **The argument is clamped at 0 from below**, because a branchless select
    computes the Bessel arm at every x and discards it on x < 0.  Unclamped, the
    shift turns x = −2⁻¹²⁶ into a 0/0 in i1e(x)/x, and numpy raises a
    RuntimeWarning from a value that is then thrown away.  The clamp is the
    identity wherever the arm is selected.  It is a ``where`` rather than a
    ``maximum``, because jax splits a ``maximum`` tie's tangent in half at x = 0.

    A coefficient collapse can still put x in the denormal window: a trial step
    down a degenerate intensity direction (scale ⊗ emission-line weight ⊗
    extinction) can land ``ext`` there on its way to the exact zero that
    switches the correction off (measured before WP-1938, when its solver
    coordinate was unbounded below).  The shift keeps every value there finite
    and warning-free.
    """
    xp = get_backend()
    x = xp.asarray(x, dtype=np.float64)
    xs = xp.where(x >= 0.0, x, 0.0) + _ARG_SHIFT
    i1 = xp.i1e(xs)
    el = xp.where(x < 0.0, 1.0, xp.i0e(xs) + i1)
    dl = xp.where(x < 0.0, 0.0, -i1 / xs)
    return el, dl


def sabine_extinction(f2: np.ndarray, wavelength: float, volume: float,
                      two_theta_deg: np.ndarray, ext: float) -> np.ndarray:
    """Extinction multiplier E(hkl) per reflection (Sabine 1988).

    Forward-only path used inside ``CompiledModel.phase_peaks``; the intensity
    is multiplied by this.  ``ext = 0`` returns exactly 1.
    """
    xp = get_backend()
    x, sth2, cth2 = _extinction_x(f2, wavelength, volume, two_theta_deg, ext)
    eb = xp.where(x > -1.0, 1.0 / xp.sqrt(xp.where(x > -1.0, 1.0 + x, 1.0)), 1.0)
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
    xp = get_backend()
    x, sth2, cth2 = _extinction_x(f2, wavelength, volume, two_theta_deg, ext)
    onepx = xp.where(x > -1.0, 1.0 + x, 1.0)
    eb = xp.where(x > -1.0, 1.0 / xp.sqrt(onepx), 1.0)
    deb = xp.where(x > -1.0, -0.5 / (onepx * xp.sqrt(onepx)), 0.0)
    el, dl = _laue_and_deriv(x)
    return eb * sth2 + el * cth2, deb * sth2 + dl * cth2, x
