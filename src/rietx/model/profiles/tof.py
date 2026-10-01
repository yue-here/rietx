"""Time-of-flight peak shape: back-to-back exponentials ⊗ Gaussian / pseudo-Voigt.

A pulsed source delivers each wavelength as a pulse that rises fast and decays
slowly, and a time-of-flight bank records that pulse convolved with the
instrument's resolution.  The pulse is the pair of exponentials of Von Dreele,
Jorgensen & Windsor (1982), *J. Appl. Cryst.* **15**, 581-589, p. 584:

    P(τ) = 2N·exp(+ατ)   τ ≤ 0          2N = αβ/(α+β)
    P(τ) = 2N·exp(−βτ)   τ ≥ 0

(the same function as GSAS's E(τ), Larson & Von Dreele 2004, LAUR 86-748,
GSAS Technical Manual p. 143).  α is a moderator slowing-down rate and β its
storage decay rate (Ikeda & Carpenter 1985, *Nucl. Instrum. Methods* **A239**,
536-544, p. 540-542), which is why α follows 1/d and β is nearly constant.

Conventions, once
-----------------
* ``dt = T(channel) − T(peak)`` in µs: **positive dt is later flight time**.
  VD82 eq. (16), the trailing edge, decays as Δ → +∞, and the manual's p. 144
  writes the offset as ``(T − T_ph)``; its p. 143 prose says the opposite and
  is not followed.  So β < α puts the tail at long flight time.  A caller
  holding ``T_ph − T`` negates it first — nothing here guesses.
* ``T_ph`` is the **junction** of the two exponentials, not the profile
  maximum, which lies at dt > 0 (manual p. 147).
* ``sigma`` is a Gaussian **standard deviation**, ``gamma`` a Lorentzian
  **FWHM**; the combined TCH width Γ is a FWHM too.  Every rate is µs⁻¹.

The two decisions this module carries
-------------------------------------
1. **The Lorentzian argument sign.**  Convolving the pulse with a Lorentzian
   gives ``H_L = (2N/π){Im S(P) − Im S(Q)}`` with ``S(w) = e^w E₁(w)`` and

       P = +α·dt − iαΓ/2,     Q = −β·dt + iβΓ/2

   derived directly from the integral.  The manual's p. 147/148 prints
   ``p = −αΔT + iαγ/2`` for profile function 3 by cross-reference to function
   2, whose Ikeda-Carpenter α term is a *decay*; function 3's α term is a
   *rise*, and the printed form reflects the α wing.  It also breaks the
   exchange symmetry ``H(dt; α, β) = H(−dt; β, α)`` that the pulse forces,
   which the form here satisfies bit for bit.  The printed ``p`` is **not**
   implemented.
2. **The combined-Γ reading of the TCH blend.**  Substituting the
   Thompson-Cox-Hastings pseudo-Voigt (TCH87, *J. Appl. Cryst.* **20**, 79-83,
   eqs. 4-5, as printed on manual p. 146) for the Voigt gives

       H = (1−η)·H_G(dt; α, β, σ_Γ) + η·H_L(dt; α, β, Γ),   σ_Γ = Γ/√(8 ln 2)

   — one width Γ in **both** halves, as TCH's own pV(x) = ηL(x;Γ) + (1−η)G(x;Γ)
   has.  The manual's letters (σ in the Gaussian half, γ in the Lorentzian
   half) read literally are wrong by up to half the peak height against the
   exact back-to-back ⊗ Voigt; the combined reading is within the TCH
   approximation's own ~1 %.  :func:`tof_pseudovoigt_widths` returns σ_Γ so no
   caller can rebuild it as σ.

At γ = 0 the blend is **exactly** the Gaussian shape — Γ = Γ_G, η = 0 and
σ_Γ = σ are set by selection, not computed, so the reduction holds bit for
bit and the Lorentzian branch is never entered when every γ is zero.

Numerics
--------
No ``erfc``/``erfcx``/``E₁`` exists on the backend op set, so:

* ``erfcx(x) = Re w(ix)`` for x ≥ 0 from :func:`~rietx.model.profiles.faddeeva.faddeeva_w`
  (Weideman 1994), reflected for x < 0 through ``erfc(−x) = 2 − erfc(x)``.
  The Gaussian shape is written as ``N·exp(−dt²/2σ²)·[erfcx(y) + erfcx(z)]``
  (VD82 eq. 10) — both exponents of VD82 eq. 13 differ from y², z² by the same
  −dt²/2σ² — and the reflected branch is only ever reached with e^u ≤ 1 or
  e^v ≤ 1, so no intermediate overflows anywhere on the real line.
* :func:`scaled_exp1` evaluates ``e^z E₁(z)`` by the power series
  (Abramowitz & Stegun 5.1.11) in the wedge hugging the negative real axis
  and by the continued fraction (A&S 5.1.22, modified Lentz, Thompson &
  Barnett 1986) everywhere else.

Every function is pure array arithmetic on :mod:`rietx.backend`; the value
returned by each ``*_derivs`` is computed from the same intermediates as the
plain shape and is bit-identical to it.
"""

from __future__ import annotations

import math

import numpy as np

from ...backend import get_backend
from .faddeeva import faddeeva_w
from .pseudovoigt import _TCH_ETA, _TCH_GAMMA, tch_gamma_eta

#: √(8 ln 2): Gaussian FWHM = √(8 ln 2)·σ (manual p. 146, Γ_G² = 8 ln2·σ²).
SQRT_8LN2 = math.sqrt(8.0 * math.log(2.0))
_SQRT2 = math.sqrt(2.0)
_SQRT_2_OVER_PI = math.sqrt(2.0 / math.pi)
#: Euler-Mascheroni γ_E (A&S 5.1.11).
_EULER_GAMMA = 0.5772156649015328606

#: The :func:`scaled_exp1` switch (series where |z| + Re z ≤ 8 and |z| ≤ 60,
#: continued fraction elsewhere), and the fixed term / step budgets that
#: cover each side of it to ~1e-13.
_SERIES_WEDGE = 8.0
_SERIES_RADIUS = 60.0
_SERIES_TERMS = 130
_LENTZ_STEPS = 200
_LENTZ_TOL = 1e-15
_LENTZ_TINY = 1e-300


def _concrete(x):
    """``x`` as a numpy array when it is plainly a value, else ``None``.

    Refusals need a value; a traced backend hands over tracers, for which the
    check is skipped (never forced) so the function stays traceable.
    """
    if isinstance(x, (int, float, np.ndarray, np.generic, list, tuple)):
        return np.asarray(x)
    return None


# ---------------------------------------------------------------------------
# flight time <-> d
# ---------------------------------------------------------------------------
def tof_from_d(d, difc, difa=0.0, tzero=0.0, difb=0.0):
    """Flight time in µs of a reflection at d-spacing ``d`` (Å).

    ``T = DIFC·d + DIFA·d² + ZERO`` (Larson & Von Dreele 2004, GSAS Technical
    Manual p. 141), plus ``DIFB/d``: a documented GSAS-II calibration
    coefficient (the TOF calibration tutorial's ``TOF = Cd + Ad² + B/d + Z``)
    with no physical interpretation given in the published documentation;
    refine only against a standard.  Units: DIFC µs/Å, DIFA µs/Å², ZERO µs,
    DIFB µs·Å.  ``difb`` defaults to 0, which is exactly the three-term
    relation.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return difc * dd + difa * dd ** 2 + tzero + difb / dd


def d_from_tof(tof, difc, difa=0.0, tzero=0.0, difb=0.0):
    """d-spacing in Å of flight time ``tof`` (µs) — the physical quadratic root.

    With ``D = tof − ZERO`` the manual's relation (p. 141) is
    ``DIFA·d² + DIFC·d − D = 0``.  The ``+`` root is the one that tends to
    D/DIFC as DIFA → 0, for either sign of DIFA, and is evaluated in the
    cancellation-free form ``d = 2D / (DIFC + √(DIFC² + 4·DIFA·D))``, exact at
    DIFA = 0.

    Refused by name: ``DIFC ≤ 0``; a negative discriminant (the bank's
    calibration does not reach that flight time); and ``difb ≠ 0``, because
    with a DIFB term the relation is a cubic with no single documented branch.
    """
    if difb != 0.0:
        raise ValueError(
            f"d_from_tof(): difb = {difb} makes TOF = C·d + A·d² + B/d + Z a "
            f"cubic in d with no documented branch; it is refused rather than "
            f"approximated")
    c = _concrete(difc)
    if c is not None and np.any(c <= 0.0):
        raise ValueError(f"d_from_tof(): DIFC must be positive, got {difc}")
    xp = get_backend()
    big_d = xp.asarray(tof, dtype=np.float64) - tzero
    disc = difc * difc + 4.0 * difa * big_d
    dc = _concrete(disc)
    if dc is not None and np.any(dc < 0.0):
        raise ValueError(
            f"d_from_tof(): DIFC² + 4·DIFA·(T − ZERO) is negative for "
            f"DIFC = {difc}, DIFA = {difa}, ZERO = {tzero}: this bank's "
            f"calibration does not reach that flight time")
    return 2.0 * big_d / (difc + xp.sqrt(disc))


# ---------------------------------------------------------------------------
# the d-dependence laws
# ---------------------------------------------------------------------------
def _require_positive_d(d, where: str):
    dd = _concrete(d)
    if dd is not None and np.any(dd <= 0.0):
        raise ValueError(f"{where}(): d must be positive (the law is singular "
                         f"at d = 0), got min d = {float(np.min(dd))}")


def tof_alpha(d, alpha0, alpha1):
    """Rise rate α = α₀ + α₁/d in µs⁻¹ (VD82 eq. 17; manual p. 144).

    ``alpha0`` µs⁻¹, ``alpha1`` µs⁻¹·Å.  GSAS profile function 3 has no α₀
    term (manual p. 148, α = α₁/d), so a function-3 calibration supplies
    ``alpha0 = 0``.  d must be positive.
    """
    _require_positive_d(d, "tof_alpha")
    xp = get_backend()
    return alpha0 + alpha1 / xp.asarray(d, dtype=np.float64)


def tof_beta(d, beta0, beta1):
    """Decay rate β = β₀ + β₁/d⁴ in µs⁻¹ (VD82 eq. 18; manual p. 144, 148).

    ``beta0`` µs⁻¹, ``beta1`` µs⁻¹·Å⁴.  d must be positive.
    """
    _require_positive_d(d, "tof_beta")
    xp = get_backend()
    return beta0 + beta1 / xp.asarray(d, dtype=np.float64) ** 4


def tof_sigma_sq(d, sig0, sig1, sig2):
    """Gaussian **variance** σ² = sig0 + sig1·d² + sig2·d⁴ in µs².

    The manual's variance law (p. 144, 148), not VD82 eq. 19's width law
    σ = σ₀ + σ₁d, which is a different function; VD82-era σ₀, σ₁ values need
    converting before they come here.  The three arguments **are** the
    variance coefficients — the quantity a file calls ``sig-1`` is σ₁²
    (manual p. 144), so it is used as written and never squared.  Units µs²,
    µs²/Å², µs²/Å⁴.  Polynomial, no guard; a caller clamps σ² ≥ 0.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return sig0 + sig1 * dd ** 2 + sig2 * dd ** 4


def tof_gamma(d, gam0, gam1, gam2):
    """Lorentzian FWHM γ = gam0 + gam1·d + gam2·d² in µs (manual p. 148).

    The isotropic part of the function-3 law; its cos φ and γ_L terms belong
    with the microstructure machinery.  Units µs, µs/Å, µs/Å².  A caller
    clamps γ ≥ 0.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return gam0 + gam1 * dd + gam2 * dd ** 2


def tof_sample_gamma(d, difc, size_per_a, strain):
    """The **sample's** Lorentzian FWHM in µs: ``DIFC·(ε·d + (K/p)·d²)``.

    A strain broadens Δd/d = ε, so ΔT = DIFC·ε·d (linear in d, manual
    p. 153); a crystallite size broadens Δd* = K/p, so ΔT = DIFC·(K/p)·d²
    (quadratic in d, manual p. 154).  Inverting term by term gives the
    manual's own γ₁ = DIFC·ε → S = γ₁/C (p. 153) and γ₂ = DIFC·K/p →
    p = CK/γ₂ (p. 155).  ``strain`` is the fractional FWHM microstrain (not
    per cent), ``size_per_a`` is K/p in Å⁻¹ with the Scherrer K the caller's
    choice.  Add to the instrument γ (Lorentzian FWHMs add).
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return difc * (strain * dd + size_per_a * dd ** 2)


def tof_sample_sigma_sq(d, difc, size_var, strain_var):
    """The **sample's** Gaussian variance in µs²: ``DIFC²/(8 ln2)·(ε²d² + (K/p)²d⁴)``.

    The Gaussian twin of :func:`tof_sample_gamma`, stated as a variance so it
    adds to the instrument's σ² (Gaussian variances add).  Inverting gives the
    manual's σ₁² = DIFC²ε²/(8 ln2) → S = (1/C)√(8 ln2·σ₁²) (p. 153) and
    σ₂² = DIFC²(K/p)²/(8 ln2) → p = CK/√(8 ln2·σ₂²) (p. 154).  Both arguments
    are **squared** quantities — ``strain_var`` = ε² and ``size_var`` =
    (K/p)² in Å⁻² — which is what the ``_var`` suffix says.
    """
    xp = get_backend()
    dd = xp.asarray(d, dtype=np.float64)
    return (difc * difc / (8.0 * math.log(2.0))) * (
        strain_var * dd ** 2 + size_var * dd ** 4)


# ---------------------------------------------------------------------------
# special functions on the op set
# ---------------------------------------------------------------------------
def _erfcx_abs(x):
    """erfcx(|x|) = exp(x²)·erfc(|x|) = Re w(i|x|) — bounded in (0, 1]."""
    xp = get_backend()
    return xp.real(faddeeva_w(1j * xp.abs(x)))


def scaled_exp1(z):
    """``e^z·E₁(z)`` for complex ``z`` off the negative real axis.

    Never ``E₁`` alone: ``e^z`` overflows for Re z ≳ 709 while the product is
    O(1/z) there.  Two evaluations, both written so the exponential never
    stands alone:

    * power series, Abramowitz & Stegun 5.1.11,
      ``E₁(z) = −γ_E − ln z + Σ (−1)^{n+1} zⁿ/(n·n!)``, 130 terms by running
      product, used where ``|z| + Re z ≤ 8`` and ``|z| ≤ 60`` — the wedge
      along the negative real axis, where its cancellation is small;
    * continued fraction, A&S 5.1.22,
      ``1/(z+1−) 1²/(z+3−) 2²/(z+5−) …`` — the minus signs belong to the
      fraction, so the partial numerators are ``a₁ = 1``,
      ``aₙ = −(n−1)²`` and the denominators ``bₙ = z + 2n − 1``; evaluated by
      modified Lentz (Thompson & Barnett 1986) to |Δ − 1| < 1e-15, used
      everywhere else, where it converges in tens of steps at most.

    Both branches run on clamped inputs and are selected with ``where``, so
    a discarded branch can never overflow into the result or its gradient.
    Each element stops updating once its own fraction has converged, so a
    value never depends on the other elements it was batched with.
    """
    xp = get_backend()
    z = xp.asarray(z, dtype=np.complex128)
    absz = xp.abs(z)
    use_series = (absz + xp.real(z) <= _SERIES_WEDGE) & (absz <= _SERIES_RADIUS)

    # --- series, on z inside its domain and a harmless 1 elsewhere
    zs = xp.where(use_series, z, 1.0 + 0.0j)
    term = zs
    acc = zs
    for n in range(2, _SERIES_TERMS + 1):
        term = -term * zs / n
        acc = acc + term / n
    series = xp.exp(zs) * (-_EULER_GAMMA - xp.log(zs) + acc)

    # --- continued fraction, on z outside the wedge and a fast 100 inside it
    # With b₀ = 0 the first Lentz step is exactly f₁ = D₁ = 1/b₁ and C₁ = ∞
    # (so C₂ = b₂); starting there rather than from f₀ = tiny keeps a 1/tiny
    # out of the arithmetic, whose derivative would overflow to inf·0 = NaN
    # in a traced Jacobian.
    zc = xp.where(use_series, 100.0 + 0.0j, z)
    dd = 1.0 / (zc + 1.0)
    f = dd
    c = None
    done = absz < 0.0
    numpy_backend = getattr(xp, "name", "numpy") == "numpy"
    for n in range(2, _LENTZ_STEPS + 1):
        a = -float((n - 1) * (n - 1))
        b = zc + float(2 * n - 1)
        dd = b + a * dd
        dd = xp.where(dd == 0.0, _LENTZ_TINY + 0.0j, dd)
        c = b if c is None else b + a / c
        c = xp.where(c == 0.0, _LENTZ_TINY + 0.0j, c)
        dd = 1.0 / dd
        delta = c * dd
        f = xp.where(done, f, f * delta)
        done = done | (xp.abs(delta - 1.0) < _LENTZ_TOL)
        if numpy_backend and bool(np.all(done)):
            break
    return xp.where(use_series, series, f)


# ---------------------------------------------------------------------------
# the shapes
# ---------------------------------------------------------------------------
def back_to_back_exponential(dt, alpha, beta):
    """The unit-area moderator pulse P(dt) (VD82 p. 584; manual p. 143).

    ``2N·exp(α·dt)`` for dt ≤ 0 and ``2N·exp(−β·dt)`` for dt ≥ 0,
    2N = αβ/(α+β).  Each branch's argument is clamped so the unselected one
    cannot overflow.  Obeys ``P(dt; α, β) = P(−dt; β, α)``.
    """
    xp = get_backend()
    dt = xp.asarray(dt, dtype=np.float64)
    two_n = alpha * beta / (alpha + beta)
    return two_n * xp.where(dt <= 0.0, xp.exp(alpha * xp.minimum(dt, 0.0)),
                            xp.exp(-beta * xp.maximum(dt, 0.0)))


def _gauss_parts(dt, alpha, beta, sigma):
    """``(N, A, B, g)`` with ``H_G = N·(A + B)``; A = e^u erfc y, B = e^v erfc z.

    VD82 eqs. (10)-(15) / manual p. 143-144 with y = (ασ² + dt)/(σ√2),
    z = (βσ² − dt)/(σ√2), u = (α/2)(ασ² + 2dt), v = (β/2)(βσ² − 2dt).  Since
    u − y² = v − z² = −dt²/2σ², A = g·erfcx(y) with g = exp(−dt²/2σ²); for
    y < 0 the reflection A = 2e^u − g·erfcx(|y|) is used, reached only where
    u < 0 (the exponent is clamped at 0 for the unselected branch).  The
    expressions are written α↔β, dt↔−dt symmetric term by term, so the
    exchange symmetry holds bit for bit.
    """
    xp = get_backend()
    dt = xp.asarray(dt, dtype=np.float64)
    s2 = sigma * sigma
    rt = sigma * _SQRT2
    y = (alpha * s2 + dt) / rt
    z = (beta * s2 - dt) / rt
    u = 0.5 * alpha * (alpha * s2 + 2.0 * dt)
    v = 0.5 * beta * (beta * s2 - 2.0 * dt)
    g = xp.exp(-(dt * dt) / (2.0 * s2))
    gy = g * _erfcx_abs(y)
    gz = g * _erfcx_abs(z)
    a_term = xp.where(y >= 0.0, gy, 2.0 * xp.exp(xp.minimum(u, 0.0)) - gy)
    b_term = xp.where(z >= 0.0, gz, 2.0 * xp.exp(xp.minimum(v, 0.0)) - gz)
    norm = alpha * beta / (2.0 * (alpha + beta))
    return norm, a_term, b_term, g


def back_to_back_gaussian(dt, alpha, beta, sigma):
    """Back-to-back exponentials ⊗ Gaussian — GSAS TOF profile function 1.

    ``H_G(dt) = N·exp(−dt²/2σ²)·[erfcx(y) + erfcx(z)]``, N = αβ/(2(α+β)) —
    VD82 eq. (10), equal to VD82 eq. (13) and the manual's
    ``N[e^u erfc y + e^v erfc z]`` (p. 143-144).  Unit area, finite and
    non-negative for every real dt, bounded by 2N.  ``sigma`` is the Gaussian
    standard deviation in µs; dt = channel − peak.
    """
    norm, a_term, b_term, _g = _gauss_parts(dt, alpha, beta, sigma)
    return norm * (a_term + b_term)


def back_to_back_gaussian_derivs(dt, alpha, beta, sigma):
    """``(H, ∂H/∂dt, ∂H/∂α, ∂H/∂β, ∂H/∂σ)`` for :func:`back_to_back_gaussian`.

    Closed forms, with A, B, g, N as in the shape (the ∂/∂dt erfc terms cancel
    identically, and for ∂/∂σ they collapse through N(α+β) = αβ/2):

        ∂H/∂dt = N(αA − βB)
        ∂H/∂σ  = N(α²σA + β²σB) − (αβ/2)·√(2/π)·g
        ∂H/∂α  = β²/(2(α+β)²)·(A+B) + N(ασ² + dt)A − Nσ√(2/π)·g
        ∂H/∂β  = α²/(2(α+β)²)·(A+B) + N(βσ² − dt)B − Nσ√(2/π)·g

    The value is built from the same intermediates as the shape and equals
    it bit for bit.
    """
    xp = get_backend()
    dt = xp.asarray(dt, dtype=np.float64)
    norm, a_term, b_term, g = _gauss_parts(dt, alpha, beta, sigma)
    h = norm * (a_term + b_term)
    s2 = sigma * sigma
    ab = a_term + b_term
    ssum2 = 2.0 * (alpha + beta) * (alpha + beta)
    gauss_tail = norm * sigma * _SQRT_2_OVER_PI * g
    d_dt = norm * (alpha * a_term - beta * b_term)
    d_sigma = (norm * (alpha * alpha * sigma * a_term + beta * beta * sigma * b_term)
               - 0.5 * alpha * beta * _SQRT_2_OVER_PI * g)
    d_alpha = (beta * beta / ssum2) * ab + norm * (alpha * s2 + dt) * a_term - gauss_tail
    d_beta = (alpha * alpha / ssum2) * ab + norm * (beta * s2 - dt) * b_term - gauss_tail
    return h, d_dt, d_alpha, d_beta, d_sigma


def _lorentz_parts(dt, alpha, beta, width):
    """``(N, P, Q, S(P), S(Q))`` for the Lorentzian half at FWHM ``width``.

    P = α·dt − iα·width/2 and Q = −β·dt + iβ·width/2 — the signs the
    convolution integral gives (module docstring, decision 1).
    """
    xp = get_backend()
    dt = xp.asarray(dt, dtype=np.float64)
    half = 0.5 * width
    p = alpha * dt - 1j * (alpha * half)
    q = -beta * dt + 1j * (beta * half)
    norm = alpha * beta / (2.0 * (alpha + beta))
    return norm, p, q, scaled_exp1(p), scaled_exp1(q)


def _lorentz_value(norm, sp, sq):
    xp = get_backend()
    return (2.0 * norm / math.pi) * (xp.imag(sp) - xp.imag(sq))


def back_to_back_lorentzian(dt, alpha, beta, gamma):
    """Back-to-back exponentials ⊗ Lorentzian of FWHM ``gamma`` (µs, > 0).

    ``H_L(dt) = (2N/π){Im[e^P E₁(P)] − Im[e^Q E₁(Q)]}`` with
    ``P = α·dt − iαγ/2`` and ``Q = −β·dt + iβγ/2``, derived by splitting the
    convolution with L(t) = (γ/2π)/((γ/2)² + t²) (manual p. 145) at the pulse
    kink and using ∫₀^∞ e^{−as}/(s + w) ds = e^{aw}E₁(aw) (A&S § 5.1).  Not the
    manual's printed p (p. 147/148) — see the module docstring.  Undefined at
    γ = 0, where P and Q reach the real axis.
    """
    norm, _p, _q, sp, sq = _lorentz_parts(dt, alpha, beta, gamma)
    return _lorentz_value(norm, sp, sq)


def _lorentz_derivs(dt, alpha, beta, width):
    """``(H_L, ∂/∂dt, ∂/∂α, ∂/∂β, ∂/∂width)`` from one S(P), one S(Q).

    With S′(w) = S(w) − 1/w:

        ∂H_L/∂dt = (2N/π)·Im[α(S(P) − 1/P) + β(S(Q) − 1/Q)]
        ∂H_L/∂Γ  = −(N/π)·Re[α(S(P) − 1/P) + β(S(Q) − 1/Q)]
        ∂H_L/∂α  = (2/π)·β²/(2(α+β)²)·Im[S(P) − S(Q)] + (2N/(πα))·Im[P·S(P)]
        ∂H_L/∂β  = (2/π)·α²/(2(α+β)²)·Im[S(P) − S(Q)] − (2N/(πβ))·Im[Q·S(Q)]
    """
    xp = get_backend()
    norm, p, q, sp, sq = _lorentz_parts(dt, alpha, beta, width)
    h = _lorentz_value(norm, sp, sq)
    dsp = sp - 1.0 / p
    dsq = sq - 1.0 / q
    comb = alpha * dsp + beta * dsq
    diff_im = xp.imag(sp) - xp.imag(sq)
    ssum2 = 2.0 * (alpha + beta) * (alpha + beta)
    d_dt = (2.0 * norm / math.pi) * xp.imag(comb)
    d_width = -(norm / math.pi) * xp.real(comb)
    d_alpha = ((2.0 / math.pi) * (beta * beta / ssum2) * diff_im
               + (2.0 * norm / (math.pi * alpha)) * xp.imag(p * sp))
    d_beta = ((2.0 / math.pi) * (alpha * alpha / ssum2) * diff_im
              - (2.0 * norm / (math.pi * beta)) * xp.imag(q * sq))
    return h, d_dt, d_alpha, d_beta, d_width


def tof_pseudovoigt_widths(sigma, gamma):
    """``(Γ, η, σ_Γ)``: the TCH combined FWHM, mixing, and the σ it implies.

    Γ_G = √(8 ln2)·σ; Γ and η from the TCH polynomials (TCH87 eqs. 4-5; manual
    p. 146) through :func:`~rietx.model.profiles.pseudovoigt.tch_gamma_eta`,
    whose coefficients are the ones this module uses; σ_Γ = Γ/√(8 ln2) is the
    standard deviation of a Gaussian of FWHM Γ, which is what the Gaussian
    half of the blend takes (module docstring, decision 2).  All three are
    returned because a caller given only (Γ, η) would rebuild σ_Γ as σ.

    Where γ = 0 the values are **selected**, not computed: Γ = Γ_G, σ_Γ = σ
    exactly and η = 0, so the blend reduces to the Gaussian shape bit for
    bit rather than to within the rounding of (Γ_G⁵)^{1/5}.
    """
    xp = get_backend()
    sig = xp.asarray(sigma, dtype=np.float64)
    gam = xp.asarray(gamma, dtype=np.float64)
    gamma_g = SQRT_8LN2 * sig
    big_gamma, eta = tch_gamma_eta(gamma_g, gam)
    off = gam == 0.0
    big_gamma = xp.where(off, gamma_g, big_gamma)
    eta = xp.where(off, 0.0, eta)
    sigma_gamma = xp.where(off, sig, big_gamma / SQRT_8LN2)
    return big_gamma, eta, sigma_gamma


def _all_zero(gamma) -> bool:
    g = _concrete(gamma)
    return g is not None and bool(np.all(g == 0.0))


def back_to_back_pseudovoigt(dt, alpha, beta, sigma, gamma):
    """Back-to-back exponentials ⊗ TCH pseudo-Voigt — GSAS TOF profile function 3.

    ``H = (1−η)·H_G(dt; α, β, σ_Γ) + η·H_L(dt; α, β, Γ)`` with (Γ, η, σ_Γ)
    from :func:`tof_pseudovoigt_widths` — the combined-Γ reading (module
    docstring, decision 2).  ``sigma`` is the Gaussian standard deviation and
    ``gamma`` the Lorentzian FWHM, both in µs.

    γ = 0 is exactly :func:`back_to_back_gaussian`: when every γ is a plain
    zero the Lorentzian branch is not evaluated at all, and element-wise the
    Gaussian value is selected where γ = 0.
    """
    xp = get_backend()
    if _all_zero(gamma):
        return back_to_back_gaussian(dt, alpha, beta, sigma)
    gam = xp.asarray(gamma, dtype=np.float64)
    big_gamma, eta, sigma_gamma = tof_pseudovoigt_widths(sigma, gam)
    norm, a_term, b_term, _g = _gauss_parts(dt, alpha, beta, sigma_gamma)
    h_g = norm * (a_term + b_term)
    width = xp.where(big_gamma > 0.0, big_gamma, 1.0)
    lnorm, _p, _q, sp, sq = _lorentz_parts(dt, alpha, beta, width)
    h_l = _lorentz_value(lnorm, sp, sq)
    blend = (1.0 - eta) * h_g + eta * h_l
    return xp.where(gam == 0.0, h_g, blend)


def back_to_back_pseudovoigt_derivs(dt, alpha, beta, sigma, gamma):
    """``(H, ∂H/∂dt, ∂H/∂α, ∂H/∂β, ∂H/∂σ, ∂H/∂γ)`` for the function-3 shape.

    Chain rule through Γ(Γ_G(σ), γ), η(γ/Γ) and σ_Γ = Γ/√(8 ln2):

        ∂H/∂dt,α,β = (1−η)·∂H_G + η·∂H_L        (α, β enter neither Γ nor η)
        ∂H/∂σ = (1−η)·∂H_G/∂σ_Γ·∂σ_Γ/∂σ + η·∂H_L/∂Γ·∂Γ/∂σ + η′·∂q/∂σ·(H_L − H_G)
        ∂H/∂γ = (1−η)·∂H_G/∂σ_Γ·∂σ_Γ/∂γ + η·∂H_L/∂Γ·∂Γ/∂γ + η′·∂q/∂γ·(H_L − H_G)

    with q = γ/Γ and the TCH polynomial's own partials.  **γ must be strictly
    positive**: at γ = 0 the γ-derivative would need a one-sided limit no
    source gives, so it is refused (a fit seeds γ at a small positive value
    instead).  The returned value is the same arithmetic as
    :func:`back_to_back_pseudovoigt` at γ > 0.
    """
    xp = get_backend()
    g_val = _concrete(gamma)
    if g_val is not None and np.any(g_val <= 0.0):
        raise ValueError(
            "back_to_back_pseudovoigt_derivs(): gamma must be strictly positive "
            "when a γ-derivative is requested — at γ = 0 it needs a one-sided "
            "limit no source gives; seed γ at a small positive value, or use "
            "back_to_back_gaussian_derivs for a purely Gaussian shape")
    sig = xp.asarray(sigma, dtype=np.float64)
    gam = xp.asarray(gamma, dtype=np.float64)
    big_gamma, eta, sigma_gamma = tof_pseudovoigt_widths(sig, gam)
    h_g, g_dt, g_da, g_db, g_ds = back_to_back_gaussian_derivs(
        dt, alpha, beta, sigma_gamma)
    h_l, l_dt, l_da, l_db, l_dw = _lorentz_derivs(dt, alpha, beta, big_gamma)
    one_m = 1.0 - eta
    h = one_m * h_g + eta * h_l

    c1, c2, c3, c4 = _TCH_GAMMA
    e1, e2, e3 = _TCH_ETA
    gg = SQRT_8LN2 * sig
    den = 5.0 * big_gamma ** 4
    dgam_dgg = (5.0 * gg ** 4 + 4.0 * c1 * gg ** 3 * gam + 3.0 * c2 * gg ** 2 * gam ** 2
                + 2.0 * c3 * gg * gam ** 3 + c4 * gam ** 4) / den
    dgam_dgl = (c1 * gg ** 4 + 2.0 * c2 * gg ** 3 * gam + 3.0 * c3 * gg ** 2 * gam ** 2
                + 4.0 * c4 * gg * gam ** 3 + 5.0 * gam ** 4) / den
    dgam_dsig = dgam_dgg * SQRT_8LN2
    q = gam / big_gamma
    deta_dq = e1 + 2.0 * e2 * q + 3.0 * e3 * q * q
    dq_dsig = -(gam / (big_gamma * big_gamma)) * dgam_dsig
    dq_dgam = 1.0 / big_gamma - (gam / (big_gamma * big_gamma)) * dgam_dgl
    lg = h_l - h_g

    d_dt = one_m * g_dt + eta * l_dt
    d_alpha = one_m * g_da + eta * l_da
    d_beta = one_m * g_db + eta * l_db
    d_sigma = (one_m * g_ds * (dgam_dsig / SQRT_8LN2) + eta * l_dw * dgam_dsig
               + deta_dq * dq_dsig * lg)
    d_gamma = (one_m * g_ds * (dgam_dgl / SQRT_8LN2) + eta * l_dw * dgam_dgl
               + deta_dq * dq_dgam * lg)
    return h, d_dt, d_alpha, d_beta, d_sigma, d_gamma
