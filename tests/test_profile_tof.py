"""The time-of-flight peak shape, pinned against the integrals that define it.

Every reference here is computed in this file from a defining integral or a
published closed form, never from another implementation: adaptive quadrature
of the pulse ⊗ kernel convolution (split at the pulse kink, each half an
exponentially weighted integral over s ≥ 0 so a Lorentzian's slow tails are
never truncated), a contour integral for e^z·E₁(z), and ``scipy.special`` as an
oracle only.  Each test names the specification section it pins; the
tolerances are the ones that section measured.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from scipy.integrate import quad
from scipy.special import erfcx as scipy_erfcx
from scipy.special import exp1 as scipy_exp1
from scipy.special import voigt_profile

import rietx.model.profiles.tof as tof
from rietx.model.profiles.tof import (
    back_to_back_exponential,
    back_to_back_gaussian,
    back_to_back_gaussian_derivs,
    back_to_back_lorentzian,
    back_to_back_pseudovoigt,
    back_to_back_pseudovoigt_derivs,
    d_from_tof,
    scaled_exp1,
    tof_alpha,
    tof_beta,
    tof_from_d,
    tof_gamma,
    tof_pseudovoigt_widths,
    tof_sample_gamma,
    tof_sample_sigma_sq,
    tof_sigma_sq,
)

LN2 = math.log(2.0)


# ---------------------------------------------------------------- references
def _gauss_kernel(sigma):
    return lambda t: np.exp(-t * t / (2.0 * sigma * sigma)) / (sigma * math.sqrt(2.0 * math.pi))


def _lorentz_kernel(fwhm):
    g = 0.5 * fwhm
    return lambda t: (g / math.pi) / (g * g + t * t)


def _voigt_kernel(sigma, fwhm):
    return lambda t: voigt_profile(t, sigma, 0.5 * fwhm)


def conv_quad(dt, alpha, beta, kernel, scale):
    """∫P(τ)K(dt−τ)dτ, split at the kink: 2N[∫e^{−αs}K(dt+s)ds + ∫e^{−βs}K(dt−s)ds].

    ``scale`` is the kernel's width; the breakpoints put the kernel's centre
    and its shoulders inside their own panels so quad resolves them.
    """
    two_n = alpha * beta / (alpha + beta)

    def half(rate, sign):
        centre = -sign * dt          # where the kernel argument dt + sign*s is 0
        pts = sorted({0.0, *(p for p in (centre - 8 * scale, centre, centre + 8 * scale)
                             if p > 0.0)})
        total = 0.0
        edges = pts + [np.inf]
        for a, b in zip(edges[:-1], edges[1:]):
            total += quad(lambda s: math.exp(-rate * s) * kernel(dt + sign * s),
                          a, b, epsabs=0.0, epsrel=1e-12, limit=400)[0]
        return total

    return two_n * (half(alpha, +1.0) + half(beta, -1.0))


# ------------------------------------------------------------- § 1.1 pulse
def test_the_pulse_has_unit_area_and_mirrors_under_the_exchange():
    """P has unit area, peaks at 2N at τ = 0, and P(τ;α,β) = P(−τ;β,α)."""
    a, b = 0.3, 0.07
    area = (quad(lambda t: float(back_to_back_exponential(t, a, b)), -np.inf, 0)[0]
            + quad(lambda t: float(back_to_back_exponential(t, a, b)), 0, np.inf)[0])
    assert area == pytest.approx(1.0, abs=1e-12)
    assert float(back_to_back_exponential(0.0, a, b)) == pytest.approx(a * b / (a + b))
    dt = np.linspace(-500.0, 500.0, 1001)
    assert np.array_equal(back_to_back_exponential(dt, a, b),
                          back_to_back_exponential(-dt, b, a))
    # the clamps: a far wing overflows neither branch
    assert np.all(np.isfinite(back_to_back_exponential(np.array([-1e9, 1e9]), 5.0, 5.0)))


# ------------------------------------------------- § 7.1 quadrature pins
def test_the_gaussian_shape_matches_quadrature_on_the_864_point_grid():
    """back_to_back_gaussian vs the convolution integral,
    α∈{0.05,0.3,1.5}, β∈{0.02,0.2,1.0}, σ∈{2,8,30}, dt∈{−6σ…20σ}: ≤ 1e-8 of peak
    (1.6e-9 measured, the quadrature's own convergence)."""
    worst = 0.0
    for a in (0.05, 0.3, 1.5):
        for b in (0.02, 0.2, 1.0):
            for s in (2.0, 8.0, 30.0):
                fine = np.linspace(-6 * s, 20 * s + 10.0 / b, 20001)
                peak = float(np.max(back_to_back_gaussian(fine, a, b, s)))
                for k in (-6.0, -2.0, -0.5, 0.0, 0.5, 2.0, 6.0, 20.0):
                    dt = k * s
                    ref = conv_quad(dt, a, b, _gauss_kernel(s), s)
                    got = float(back_to_back_gaussian(dt, a, b, s))
                    worst = max(worst, abs(got - ref) / peak)
    assert worst <= 1e-8, worst


LORENTZ_SETS = ((0.3, 0.2, 10.0), (1.5, 0.02, 10.0), (0.05, 1.0, 60.0))
LORENTZ_DT = (-40.0, -10.0, 0.0, 10.0, 40.0, 200.0)


def test_the_lorentzian_half_matches_quadrature():
    """the derived H_L (P = +α·dt − iαγ/2) vs quadrature,
    ≤ 1e-12 of peak (measured 1.1e-14)."""
    worst = 0.0
    for a, b, g in LORENTZ_SETS:
        fine = np.linspace(-200.0, 400.0, 6001)
        peak = float(np.max(back_to_back_lorentzian(fine, a, b, g)))
        for dt in LORENTZ_DT:
            ref = conv_quad(dt, a, b, _lorentz_kernel(g), g)
            worst = max(worst, abs(float(back_to_back_lorentzian(dt, a, b, g)) - ref) / peak)
    assert worst <= 1e-12, worst


def test_the_lorentzian_row_the_spec_tabulates():
    """α = 0.05, β = 1.0, γ = 60 µs, the quadrature column."""
    dt = np.array([-40.0, -10.0, 0.0, 10.0, 40.0])
    want = np.array([6.261003e-03, 8.739432e-03, 7.879649e-03, 6.268414e-03, 2.501083e-03])
    assert np.allclose(back_to_back_lorentzian(dt, 0.05, 1.0, 60.0), want, rtol=1e-6)


def test_the_manuals_printed_p_is_not_the_convolution():
    """Negative control: the manual's p = −αΔT + iαγ/2 reflects
    the α wing and misses the quadrature by ~5e-1 of peak; the derived form does not."""
    a, b, g = 0.05, 1.0, 60.0
    n = a * b / (2.0 * (a + b))

    def manual(dt):
        p = -a * dt + 1j * a * g / 2.0
        q = -b * dt + 1j * b * g / 2.0
        return -(2.0 * n / math.pi) * (scaled_exp1(p).imag + scaled_exp1(q).imag)

    peak = float(np.max(back_to_back_lorentzian(np.linspace(-200, 200, 4001), a, b, g)))
    ref = conv_quad(40.0, a, b, _lorentz_kernel(g), g)
    assert abs(manual(40.0) - ref) / peak > 0.1
    assert abs(float(back_to_back_lorentzian(40.0, a, b, g)) - ref) / peak < 1e-12


PV_SETS = ((0.30, 0.20, 8.0, 4.0), (0.30, 0.20, 8.0, 20.0), (0.30, 0.20, 8.0, 60.0),
           (1.50, 0.02, 2.0, 2.0), (0.05, 1.00, 30.0, 30.0))


def test_the_pseudovoigt_is_within_the_tch_error_of_the_exact_voigt_convolution():
    """the combined-Γ blend vs quadrature of B2B ⊗ Voigt(σ, γ),
    41 dt per set: ≤ 2e-2 of peak (measured 9.4e-3 — the pseudo-Voigt-vs-Voigt
    approximation itself)."""
    worst = 0.0
    for a, b, s, g in PV_SETS:
        width = s + g
        grid = np.linspace(-6 * width - 5.0 / a, 8 * width + 8.0 / b, 41)
        ref = np.array([conv_quad(dt, a, b, _voigt_kernel(s, g), width) for dt in grid])
        got = back_to_back_pseudovoigt(grid, a, b, s, g)
        worst = max(worst, float(np.max(np.abs(got - ref)) / np.max(ref)))
    assert worst <= 2e-2, worst


def test_reading_a_the_manuals_literal_letters_is_rejected():
    """negative control: (1−η)H_G(σ) + ηH_L(γ) misses the exact
    shape by far more than the combined-Γ reading on the first parameter set."""
    a, b, s, g = 0.30, 0.20, 8.0, 20.0
    grid = np.linspace(-60.0, 120.0, 41)
    ref = np.array([conv_quad(dt, a, b, _voigt_kernel(s, g), s + g) for dt in grid])
    _gam, eta, _sg = tof_pseudovoigt_widths(s, g)
    reading_a = (1 - eta) * back_to_back_gaussian(grid, a, b, s) + eta * back_to_back_lorentzian(grid, a, b, g)
    err_a = np.max(np.abs(reading_a - ref)) / np.max(ref)
    err_b = np.max(np.abs(back_to_back_pseudovoigt(grid, a, b, s, g) - ref)) / np.max(ref)
    assert err_a > 0.1 and err_b < 2e-2


# ---------------------------------------------------------------- § 7.2 area
def _area(f, scale, lor_tail=0.0):
    edges = scale * np.concatenate([[0.0], 10.0 ** np.arange(-2.0, 6.01, 0.5)])
    total = 0.0
    for sign in (+1.0, -1.0):
        for lo, hi in zip(edges[:-1], edges[1:]):
            total += quad(lambda t: float(f(sign * t)), lo, hi, epsabs=0.0,
                          epsrel=1e-12, limit=400)[0]
    return total + lor_tail / (math.pi * edges[-1])


@pytest.mark.parametrize(("a", "b", "s", "g"), [
    (0.3, 0.2, 8.0, 0.0), (0.3, 0.2, 8.0, 10.0), (1.5, 0.02, 2.0, 60.0),
    (0.05, 1.0, 30.0, 30.0), (0.3, 0.2, 1.0, 0.5)])
def test_every_shape_has_unit_area(a, b, s, g):
    """∫H = 1 to 1e-8 on geometric panels to 10⁶ widths each side,
    plus the analytic Lorentzian tail η·Γ/(πT) beyond the last panel."""
    big_gamma, eta, _sg = tof_pseudovoigt_widths(s, g)
    scale = float(big_gamma)
    assert _area(lambda t: back_to_back_pseudovoigt(t, a, b, s, g), scale,
                 lor_tail=float(eta * big_gamma)) == pytest.approx(1.0, abs=1e-8)
    assert _area(lambda t: back_to_back_gaussian(t, a, b, s), s) == pytest.approx(1.0, abs=1e-8)
    if g > 0.0:
        assert _area(lambda t: back_to_back_lorentzian(t, a, b, g), g,
                     lor_tail=g) == pytest.approx(1.0, abs=1e-8)


# ------------------------------------------------------------ § 7.3 γ → 0
def test_gamma_zero_is_the_gaussian_bit_for_bit_and_never_enters_the_lorentzian(monkeypatch):
    """at γ = 0 the blend IS the Gaussian shape — equality,
    not tolerance — and scaled_exp1 is not called (its arguments would sit on
    the real axis)."""
    def refuse(_z):
        raise AssertionError("scaled_exp1 was entered at gamma = 0")

    monkeypatch.setattr(tof, "scaled_exp1", refuse)
    dt = np.array([-20.0, -3.0, 0.0, 4.0, 30.0, 400.0])
    for a, b, s in ((0.3, 0.2, 8.0), (1.5, 0.02, 2.0)):
        assert np.array_equal(back_to_back_pseudovoigt(dt, a, b, s, 0.0),
                              back_to_back_gaussian(dt, a, b, s))
        assert np.array_equal(back_to_back_pseudovoigt(dt, a, b, s, np.zeros_like(dt)),
                              back_to_back_gaussian(dt, a, b, s))


def test_gamma_zero_elementwise_is_still_exact():
    """a mixed array selects the Gaussian value where γ = 0."""
    dt = np.array([-20.0, 0.0, 30.0, -20.0, 0.0, 30.0])
    gam = np.array([0.0, 0.0, 0.0, 5.0, 5.0, 5.0])
    got = back_to_back_pseudovoigt(dt, 0.3, 0.2, 8.0, gam)
    assert np.array_equal(got[:3], back_to_back_gaussian(dt[:3], 0.3, 0.2, 8.0))
    assert np.allclose(got[3:], back_to_back_pseudovoigt(dt[3:], 0.3, 0.2, 8.0, 5.0),
                       rtol=0, atol=0)


def test_the_widths_reduce_exactly_at_gamma_zero():
    """Γ = Γ_G, η = 0, σ_Γ = σ exactly (selected, not computed)."""
    s = np.array([1.0, 8.0, 30.0])
    big_gamma, eta, sigma_gamma = tof_pseudovoigt_widths(s, 0.0)
    assert np.array_equal(sigma_gamma, s)
    assert np.array_equal(eta, np.zeros(3))
    assert np.array_equal(big_gamma, tof.SQRT_8LN2 * s)


def test_the_widths_are_tch_at_positive_gamma():
    """Γ⁵ polynomial and η(q) of TCH87 eqs. 4-5, σ_Γ = Γ/√(8 ln2)."""
    s, g = 8.0, 20.0
    gg = math.sqrt(8 * LN2) * s
    g5 = (gg ** 5 + 2.69269 * gg ** 4 * g + 2.42843 * gg ** 3 * g ** 2
          + 4.47163 * gg ** 2 * g ** 3 + 0.07842 * gg * g ** 4 + g ** 5)
    big = g5 ** 0.2
    q = g / big
    big_gamma, eta, sigma_gamma = tof_pseudovoigt_widths(s, g)
    assert float(big_gamma) == pytest.approx(big, rel=1e-15)
    assert float(eta) == pytest.approx(1.36603 * q - 0.47719 * q ** 2 + 0.11116 * q ** 3, rel=1e-14)
    assert float(sigma_gamma) == pytest.approx(big / math.sqrt(8 * LN2), rel=1e-15)


# ---------------------------------------------------------- § 7.4 symmetry
def test_the_exchange_symmetry_holds_exactly_for_the_gaussian():
    """H(dt; α, β, σ) = H(−dt; β, α, σ), bitwise."""
    dt = np.linspace(-300.0, 300.0, 1201)
    for a, b, s in ((1.5, 0.02, 2.0), (0.3, 0.2, 8.0), (0.05, 1.0, 30.0)):
        assert np.array_equal(back_to_back_gaussian(dt, a, b, s),
                              back_to_back_gaussian(-dt, b, a, s))


def test_the_exchange_symmetry_holds_for_the_lorentzian_and_the_blend():
    """≤ 1e-14 relative (the two sides may take
    different scaled_exp1 branches) — the free detector of the manual's p."""
    dt = np.linspace(-300.0, 300.0, 601)
    for a, b, g in LORENTZ_SETS:
        lhs = back_to_back_lorentzian(dt, a, b, g)
        rhs = back_to_back_lorentzian(-dt, b, a, g)
        assert np.max(np.abs(lhs - rhs) / np.abs(lhs)) <= 1e-14
        lhs = back_to_back_pseudovoigt(dt, a, b, 4.0, g)
        rhs = back_to_back_pseudovoigt(-dt, b, a, 4.0, g)
        assert np.max(np.abs(lhs - rhs) / np.abs(lhs)) <= 1e-14


def test_swapping_the_rates_without_reflecting_dt_mirrors_the_profile():
    """the shape is asymmetric."""
    dt = np.array([-20.0, 20.0])
    assert not np.allclose(back_to_back_gaussian(dt, 1.5, 0.02, 2.0),
                           back_to_back_gaussian(dt, 0.02, 1.5, 2.0))


@pytest.mark.parametrize(("a", "b", "s", "peak_at"), [(1.5, 0.02, 2.0, 3.87), (0.3, 0.2, 8.0, 1.115)])
def test_the_maximum_is_on_the_late_side_of_the_junction(a, b, s, peak_at):
    """T_ph is the exponential junction; the maximum lies at
    dt > 0 when β < α (+3.87 µs and +1.115 µs to the quoted digits; a bounded
    maximisation of this closed form, which matches quadrature to 1e-8, puts
    them at +3.86874 and +1.11219 µs, so the pin is ±5e-3)."""
    dt = np.linspace(-20.0, 20.0, 400001)
    top = dt[np.argmax(back_to_back_gaussian(dt, a, b, s))]
    assert top > 0.0
    assert top == pytest.approx(peak_at, abs=5e-3)


# ------------------------------------------------------ § 7.6 where the tail is
def test_the_tail_is_at_long_flight_time_when_beta_is_below_alpha():
    """α=1.5, β=0.02, σ=4 → H(−150) = 2.49e-92, H(+150) = 9.86e-4;
    the swap mirrors it exactly."""
    h = back_to_back_gaussian(np.array([-150.0, 150.0]), 1.5, 0.02, 4.0)
    assert h[0] == pytest.approx(2.49e-92, rel=2e-3)
    assert h[1] == pytest.approx(9.86e-4, rel=1e-3)
    assert h[1] > 1e80 * h[0]
    swapped = back_to_back_gaussian(np.array([150.0, -150.0]), 0.02, 1.5, 4.0)
    assert np.array_equal(swapped, h)


def test_the_trailing_wing_is_von_dreeles_eq_16():
    """far on the dt > 0 side the closed form equals VD82 eq. (16),
    F(Δ) = αβ/(α+β)·exp[(β/2)(βσ² − 2Δ)], to a ratio of 1.000000 at 100, 300,
    1000 µs.  The one test that catches a global dt sign flip."""
    a, b, s = 1.5, 0.02, 4.0
    for dt in (100.0, 300.0, 1000.0):
        eq16 = a * b / (a + b) * math.exp(0.5 * b * (b * s * s - 2.0 * dt))
        assert float(back_to_back_gaussian(dt, a, b, s)) / eq16 == pytest.approx(1.0, abs=5e-7)


# --------------------------------------------------------- § 7.5 derivatives
def _central(f, x, h):
    return (f(x + h) - f(x - h)) / (2.0 * h)


DT5 = np.array([-25.0, -3.0, 0.0, 4.0, 40.0])


def _worst_rel(analytic, numeric):
    scale = np.max(np.abs(analytic))
    return float(np.max(np.abs(analytic - numeric)) / scale)


@pytest.mark.parametrize(("a", "b", "s"), [(0.3, 0.2, 8.0), (1.5, 0.02, 2.0), (0.05, 1.0, 30.0)])
def test_the_gaussian_partials_agree_with_central_differences(a, b, s):
    """≤ 1e-6 relative to each partial's largest magnitude
    over dt ∈ {−25, −3, 0, 4, 40} (measured 4.3e-8); steps 1e-4 of the width
    for dt and 1e-6 of the value for the parameters."""
    h, d_dt, d_a, d_b, d_s = back_to_back_gaussian_derivs(DT5, a, b, s)
    f = back_to_back_gaussian
    assert _worst_rel(d_dt, _central(lambda x: f(x, a, b, s), DT5, 1e-4 * s)) <= 1e-6
    assert _worst_rel(d_a, _central(lambda x: f(DT5, x, b, s), a, 1e-6 * a)) <= 1e-6
    assert _worst_rel(d_b, _central(lambda x: f(DT5, a, x, s), b, 1e-6 * b)) <= 1e-6
    assert _worst_rel(d_s, _central(lambda x: f(DT5, a, b, x), s, 1e-6 * s)) <= 1e-6


@pytest.mark.parametrize(("a", "b", "g"), [(0.3, 0.2, 10.0), (1.5, 0.02, 60.0), (0.05, 1.0, 3.0)])
def test_the_lorentzian_partials_agree_with_central_differences(a, b, g):
    """one S(P), one S(Q) supply all four (measured 6.4e-8)."""
    h, d_dt, d_a, d_b, d_g = tof._lorentz_derivs(DT5, a, b, g)
    f = back_to_back_lorentzian
    assert np.array_equal(h, f(DT5, a, b, g))
    assert _worst_rel(d_dt, _central(lambda x: f(x, a, b, g), DT5, 1e-4 * g)) <= 1e-6
    assert _worst_rel(d_a, _central(lambda x: f(DT5, x, b, g), a, 1e-6 * a)) <= 1e-6
    assert _worst_rel(d_b, _central(lambda x: f(DT5, a, x, g), b, 1e-6 * b)) <= 1e-6
    assert _worst_rel(d_g, _central(lambda x: f(DT5, a, b, x), g, 1e-6 * g)) <= 1e-6


@pytest.mark.parametrize(("a", "b", "s", "g"), [(0.3, 0.2, 8.0, 10.0), (1.5, 0.02, 2.0, 6.0),
                                                (0.05, 1.0, 30.0, 3.0)])
def test_the_pseudovoigt_partials_agree_with_central_differences(a, b, s, g):
    """the chain through Γ, η and σ_Γ."""
    h, d_dt, d_a, d_b, d_s, d_g = back_to_back_pseudovoigt_derivs(DT5, a, b, s, g)
    f = back_to_back_pseudovoigt
    w = float(tof_pseudovoigt_widths(s, g)[0])
    assert _worst_rel(d_dt, _central(lambda x: f(x, a, b, s, g), DT5, 1e-4 * w)) <= 1e-6
    assert _worst_rel(d_a, _central(lambda x: f(DT5, x, b, s, g), a, 1e-6 * a)) <= 1e-6
    assert _worst_rel(d_b, _central(lambda x: f(DT5, a, x, s, g), b, 1e-6 * b)) <= 1e-6
    assert _worst_rel(d_s, _central(lambda x: f(DT5, a, b, x, g), s, 1e-6 * s)) <= 1e-6
    assert _worst_rel(d_g, _central(lambda x: f(DT5, a, b, s, x), g, 1e-6 * g)) <= 1e-6


def test_the_derivs_value_is_the_shape_bit_for_bit():
    """the value a *_derivs call returns is the shape itself."""
    dt = np.linspace(-80.0, 200.0, 281)
    assert np.array_equal(back_to_back_gaussian_derivs(dt, 0.3, 0.2, 8.0)[0],
                          back_to_back_gaussian(dt, 0.3, 0.2, 8.0))
    assert np.array_equal(back_to_back_pseudovoigt_derivs(dt, 0.3, 0.2, 8.0, 10.0)[0],
                          back_to_back_pseudovoigt(dt, 0.3, 0.2, 8.0, 10.0))


def test_a_gamma_derivative_at_gamma_zero_is_refused():
    """the one-sided limit is in no source, so it is refused."""
    with pytest.raises(ValueError, match="strictly positive"):
        back_to_back_pseudovoigt_derivs(DT5, 0.3, 0.2, 8.0, 0.0)


# ------------------------------------------------------ § 7.7 laws and T <-> d
@pytest.mark.parametrize(("difc", "difa", "tzero"), [
    (7476.91, 0.0, -1.44), (7476.91, -1.23, -1.44), (7476.91, 4.7, 12.0), (22580.0, 0.0, 0.0)])
def test_tof_to_d_round_trips(difc, difa, tzero):
    """d → T → d to 1e-15 relative over 0.2-5 Å (measured 1.9e-16)."""
    d = np.linspace(0.2, 5.0, 4801)
    back = d_from_tof(tof_from_d(d, difc, difa, tzero), difc, difa, tzero)
    assert np.max(np.abs(back - d) / d) <= 1e-15


def test_the_stabilised_root_beats_the_naive_one():
    """at DIFA = 1e-10 the naive (−C+√)/2A root is off by
    ~1e-3; the stabilised 2D/(C+√) is not."""
    difc, difa, tzero, d = 7476.91, 1e-10, -1.44, 1.234
    t = float(tof_from_d(d, difc, difa, tzero))
    assert abs(float(d_from_tof(t, difc, difa, tzero)) - d) < 1e-12
    naive = (-difc + math.sqrt(difc ** 2 + 4 * difa * (t - tzero))) / (2 * difa)
    assert abs(naive - d) / d > 1e-6


def test_difb_adds_exactly_its_own_term_and_the_inverse_refuses_it():
    """the fourth term is DIFB/d; d_from_tof refuses DIFB ≠ 0."""
    d = np.array([0.5, 1.0, 2.5])
    three = tof_from_d(d, 12000.0, -2.0, 5.0)
    four = tof_from_d(d, 12000.0, -2.0, 5.0, difb=-24.5)
    assert np.allclose(four - three, -24.5 / d, rtol=0, atol=1e-11)
    with pytest.raises(ValueError, match="difb"):
        d_from_tof(20000.0, 12000.0, 0.0, 0.0, difb=-24.5)


def test_d_from_tof_refuses_what_the_calibration_cannot_answer():
    """DIFC ≤ 0 and a negative discriminant are refused by name."""
    with pytest.raises(ValueError, match="DIFC must be positive"):
        d_from_tof(1000.0, 0.0)
    with pytest.raises(ValueError, match="does not reach"):
        d_from_tof(-1.0e8, 7476.91, 1.0, 0.0)


def test_the_laws_are_the_manuals_and_sigma_sq_is_a_variance():
    """tof_sigma_sq(d, s0, 0, 0) == s0 (not s0²), and the
    four laws term by term."""
    assert tof_sigma_sq(1.7, 49.0, 0.0, 0.0) == 49.0
    d = 2.0
    assert float(tof_alpha(d, 0.1, 0.45)) == pytest.approx(0.1 + 0.45 / 2.0)
    assert float(tof_beta(d, 0.055, 0.003)) == pytest.approx(0.055 + 0.003 / 16.0)
    assert float(tof_sigma_sq(d, 1.0, 300.0, 2.0)) == pytest.approx(1.0 + 1200.0 + 32.0)
    assert float(tof_gamma(d, 1.0, 2.0, 3.0)) == pytest.approx(1.0 + 4.0 + 12.0)
    for law in (tof_alpha, tof_beta):
        with pytest.raises(ValueError, match="d must be positive"):
            law(np.array([1.0, 0.0]), 0.1, 0.2)


def test_the_sample_widths_invert_to_the_manuals_four_formulas():
    """GM p. 153-155's inversions return ε and p, one
    assertion per formula."""
    difc, k, p, eps = 12000.0, 0.9, 850.0, 1.3e-3
    d = np.array([1.0, 2.0])
    # Lorentzian: γ = γ₁d + γ₂d² with γ₁ = C·ε, γ₂ = C·K/p
    g = tof_sample_gamma(d, difc, k / p, eps)
    gam2 = (g[1] - 2.0 * g[0]) / 2.0
    gam1 = g[0] - gam2
    assert gam1 / difc == pytest.approx(eps, rel=1e-12)                 # GM p. 153
    assert difc * k / gam2 == pytest.approx(p, rel=1e-12)               # GM p. 155
    # Gaussian: σ² = σ₁²d² + σ₂²d⁴
    v = tof_sample_sigma_sq(d, difc, (k / p) ** 2, eps ** 2)
    s2sq = (v[1] - 4.0 * v[0]) / 12.0
    s1sq = v[0] - s2sq
    assert math.sqrt(8 * LN2 * s1sq) / difc == pytest.approx(eps, rel=1e-10)   # GM p. 153
    assert difc * k / math.sqrt(8 * LN2 * s2sq) == pytest.approx(p, rel=1e-10)  # GM p. 154


# -------------------------------------------------------------- § 7.8 numerics
def _exp1_oracle(z: complex) -> complex:
    """e^z E₁(z) = ∫₀^∞ e^{−t}/(z+t) dt, the contour rotated ±45° away from the
    pole at t = −z so the integrand stays smooth arbitrarily close to the cut."""
    phi = 0.0 if z.imag == 0.0 else math.copysign(math.pi / 4.0, z.imag)
    w = complex(math.cos(phi), math.sin(phi))

    def f(s):
        return np.exp(-s * w) * w / (z + s * w)

    re = quad(lambda s: f(s).real, 0.0, np.inf, epsabs=0.0, epsrel=2e-14, limit=400)[0]
    im = quad(lambda s: f(s).imag, 0.0, np.inf, epsabs=0.0, epsrel=2e-14, limit=400)[0]
    return complex(re, im)


@pytest.mark.filterwarnings("ignore::scipy.integrate.IntegrationWarning")
def test_scaled_exp1_over_the_complex_plane():
    """220 geometric radii in [1e-4, 3e3] × 121 arguments
    filling (−π, π), against a contour-integral oracle: worst ≤ 1e-11 relative
    (spec measured 8.4e-13)."""
    r = np.geomspace(1e-4, 3e3, 220)
    th = np.linspace(-math.pi, math.pi, 123)[1:-1]
    z = (r[:, None] * np.exp(1j * th[None, :])).ravel()
    got = scaled_exp1(z)
    ref = np.array([_exp1_oracle(complex(v)) for v in z])
    err = np.abs(got - ref) / np.abs(ref)
    assert float(np.max(err)) <= 1e-11, float(np.max(err))


def test_the_continued_fraction_carries_the_as_minus_signs():
    """scaled_exp1(8) is the CF branch; it must equal
    e⁸E₁(8) to 1e-13.  A CF with aₙ = +(n−1)² converges to a number 2e-2 away —
    shown here so the regression test is known to be sensitive."""
    exact = math.exp(8.0) * float(scipy_exp1(8.0))
    got = complex(scaled_exp1(8.0 + 0.0j))
    assert abs(got - exact) / exact < 1e-13

    def backward_cf(z, sign, steps=400):
        # 1/(z+1 + sign·1²/(z+3 + sign·2²/(z+5 + …))), evaluated from the tail
        t = 0.0
        for n in range(steps, 1, -1):
            t = sign * (n - 1) ** 2 / (z + 2 * n - 1 + t)
        return 1.0 / (z + 1 + t)

    assert abs(backward_cf(8.0, -1.0) - exact) / exact < 1e-13
    assert abs(backward_cf(8.0, +1.0) - exact) / exact > 1e-2


def test_scaled_exp1_is_finite_along_both_sides_of_the_cut_and_far_out():
    """the arguments a profile feeds it, |z| up to 1e9."""
    z = np.array([-1e9 + 1e-3j, -1e9 - 1e-3j, 1e9 + 0j, -59.9 + 0.1j, -60.1 + 0.1j,
                  1e-6 - 1e-6j])
    assert np.all(np.isfinite(scaled_exp1(z)))


def test_erfcx_from_the_faddeeva_function():
    """Re w(i|x|) reproduces erfcx on [0, 1e6], and the
    reflection 2e^{x²} − erfcx(|x|) on [−26, 0).  (The spec measured bitwise.)"""
    x = np.concatenate([[0.0], np.geomspace(1e-6, 1e6, 200)])
    assert np.max(np.abs(tof._erfcx_abs(x) - scipy_erfcx(x)) / scipy_erfcx(x)) <= 1e-13
    xn = -np.linspace(26.0, 1e-6, 200)
    reflected = 2.0 * np.exp(xn * xn) - tof._erfcx_abs(xn)
    assert np.max(np.abs(reflected - scipy_erfcx(xn)) / scipy_erfcx(xn)) <= 1e-13


@pytest.mark.parametrize(("a", "b", "s"), [(1.5, 0.02, 2.0), (0.01, 0.005, 60.0), (5.0, 5.0, 0.5)])
def test_no_shape_overflows_anywhere_on_the_line(a, b, s):
    """finite, non-negative over
    dt ∈ [−1e9, 1e9], and H_G ≤ 2N."""
    dt = np.concatenate([-np.geomspace(1e9, 1e-3, 400), [0.0], np.geomspace(1e-3, 1e9, 400)])
    hg = back_to_back_gaussian(dt, a, b, s)
    assert np.all(np.isfinite(hg)) and np.all(hg >= 0.0)
    assert np.all(hg <= a * b / (a + b))
    for g in (0.5, 30.0):
        hp = back_to_back_pseudovoigt(dt, a, b, s, g)
        assert np.all(np.isfinite(hp)) and np.all(hp >= -1e-300)
        derivs = back_to_back_pseudovoigt_derivs(dt, a, b, s, g)
        assert all(np.all(np.isfinite(x)) for x in derivs)
    assert all(np.all(np.isfinite(x)) for x in back_to_back_gaussian_derivs(dt, a, b, s))


def test_the_maximum_against_the_bound():
    """max H = 1.7987e-2 against 2N = 1.9737e-2 for (1.5, 0.02, 2)."""
    dt = np.linspace(-20.0, 40.0, 60001)
    assert float(np.max(back_to_back_gaussian(dt, 1.5, 0.02, 2.0))) == pytest.approx(1.7987e-2, rel=1e-4)


def test_a_traced_backend_agrees_with_the_analytic_partials():
    """the module runs on the traced (jax) op set,
    its values match numpy, and forward-mode autodiff through it — dead
    ``where`` branches, the series and the continued fraction included —
    reproduces the closed-form partials.  An independent check of § 2's
    algebra, and of the clamping discipline: a discarded branch that
    overflowed would poison these columns with NaN."""
    jax = pytest.importorskip("jax")
    from rietx.backend.api import JaxBackend
    from rietx.backend.traced import active

    jnp = jax.numpy
    dt = np.linspace(-60.0, 200.0, 27)
    ref = back_to_back_pseudovoigt_derivs(dt, 0.3, 0.2, 8.0, 10.0)
    ref_g = back_to_back_gaussian_derivs(dt, 0.3, 0.2, 8.0)
    with active(JaxBackend()):
        def pv(th):
            return back_to_back_pseudovoigt(jnp.asarray(dt), th[0], th[1], th[2], th[3])

        def gauss(th):
            return back_to_back_gaussian(jnp.asarray(dt), th[0], th[1], th[2])

        theta = jnp.array([0.3, 0.2, 8.0, 10.0])
        assert np.max(np.abs(np.asarray(pv(theta)) - ref[0])) <= 1e-13 * np.max(ref[0])
        jac = np.asarray(jax.jacfwd(pv)(theta))
        jac_g = np.asarray(jax.jacfwd(gauss)(theta[:3]))
        jac_0 = np.asarray(jax.jacfwd(pv)(jnp.array([0.3, 0.2, 8.0, 0.0])))
    for k in range(4):
        assert _worst_rel(ref[2 + k], jac[:, k]) <= 1e-11
    for k in range(3):
        assert _worst_rel(ref_g[2 + k], jac_g[:, k]) <= 1e-11
    # at γ = 0 the Gaussian value is selected; its α, β, σ columns stay finite
    assert np.all(np.isfinite(jac_0[:, :3]))
