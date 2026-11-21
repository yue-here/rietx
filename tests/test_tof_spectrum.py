"""The TOF intensity corrections: incident spectrum, Lorentz factor, Sabine
extinction and the neutron µ(λ) — each pinned against the published form.

The incident-spectrum fixtures are Von Dreele, Jorgensen & Windsor (1982),
*J. Appl. Cryst.* **15**, 581, Table 1, p. 583 (spectra A-C).  That paper's t
is in **microseconds** (A₂ = 35.59e6 in exp(−A₂/t²) only makes sense for t in
µs), while the GSAS ITYP functions take milliseconds, so the paper's own
formula evaluated in µs is the reference and the coefficients enter
``incident_intensity`` rescaled by 1000ᵏ — which is exactly the unit door the
module claims to have.  Each test names the specification section it pins.
"""

from __future__ import annotations

import math

import numpy as np
import pytest
from numpy.polynomial.chebyshev import chebval

from rietx.crystallography.neutron import properties
from rietx.model.tof_spectrum import (
    COEFFICIENT_COUNTS,
    SABINE_LAUE_ASYMPTOTE_AT_1,
    SABINE_LAUE_SERIES_AT_1,
    SPECTRUM_TYPES,
    THERMAL_WAVELENGTH,
    incident_intensity,
    incident_spectrum,
    moderator_temperature,
    neutron_attenuation_terms,
    neutron_linear_attenuation,
    sabine_extinction,
    sabine_x,
    tof_lorentz,
)

# ------------------------------------------------------------- VD82 Table 1
#: A₀…A₈ as printed (VD82 p. 583), t in µs.  A: BSS vanadium, eq. (5);
#: B: HRPD vanadium, eq. (4); C: HRPD through-beam monitor, eq. (4).
VD82_A = (0.0, 2339.0, 35.59e6, 1.000, 0.2015e-6, -0.592, 0.1421e-9, 0.0, 0.0)
VD82_B = (0.004395, 1.79, 0.3819e-3, -1.000, 0.1136e-6, 0.0, 0.0, 0.0, 0.0)
VD82_C = (0.000289, 0.953, 0.3157e-3, -1.000, 0.1402e-6, 0.266, 0.0501e-9, 0.242,
          0.2561e-12)
#: First channel (TD), channel width (CW) and channel count (N) per spectrum.
VD82_RANGE = {"A": (980.0, 2.0, 4096), "B": (2800.0, 7.0, 4094), "C": (800.0, 10.0, 3604)}


def vd82_eq4(t_us, a):
    return (a[0] + a[1] * np.exp(-a[2] * t_us) + a[3] * np.exp(-a[4] * t_us ** 2)
            + a[5] * np.exp(-a[6] * t_us ** 3) + a[7] * np.exp(-a[8] * t_us ** 4))


def vd82_eq5(t_us, a):
    return (a[0] + a[1] * np.exp(-a[2] / t_us ** 2) / t_us ** 5
            + a[3] * np.exp(-a[4] * t_us ** 2) + a[5] * np.exp(-a[6] * t_us ** 3)
            + a[7] * np.exp(-a[8] * t_us ** 4))


def to_ms_block(a, maxwellian: bool):
    """VD82 µs coefficients → the manual's ms P₁…P₁₁ (t_µs = 1000·T)."""
    p = [a[0]]
    if maxwellian:          # A₁e^{−A₂/t²}/t⁵ = (A₁/1e15)e^{−(A₂/1e6)/T²}/T⁵
        p += [a[1] * 1e-15, a[2] * 1e-6]
    else:                   # A₁e^{−A₂t} = A₁e^{−(1000A₂)T}
        p += [a[1], a[2] * 1e3]
    for k, power in ((3, 2), (5, 3), (7, 4)):
        p += [a[k], a[k + 1] * 1e3 ** power]
    return p + [0.0, 0.0]


def _grid(name):
    td, cw, n = VD82_RANGE[name]
    return td + cw * np.arange(n)


def test_type_zero_is_exactly_one():
    """ITYP 0 returns exactly 1.0 (manual p. 129)."""
    assert incident_intensity(np.linspace(1e3, 4e4, 5), 0, []) == 1.0
    assert incident_intensity(np.linspace(1e3, 4e4, 5), 0, [0.0] * 12) == 1.0
    assert incident_spectrum(0, [], 5000.0) == 1.0


@pytest.mark.parametrize(("name", "coeffs", "itype", "ref"), [
    ("A", VD82_A, 2, vd82_eq5), ("B", VD82_B, 1, vd82_eq4), ("C", VD82_C, 1, vd82_eq4)])
def test_von_dreeles_table_1_spectra_are_reproduced(name, coeffs, itype, ref):
    """ITYP 1 and 2 are VD82 eqs. (4) and (5); at the
    tabulated coefficients over each spectrum's own channels they reproduce
    the paper's formula evaluated in its own µs units."""
    t = _grid(name)
    got = incident_intensity(t, itype, to_ms_block(coeffs, itype == 2))
    want = ref(t, coeffs)
    assert np.max(np.abs(got - want)) <= 1e-12 * np.max(np.abs(want))


def test_the_maxwellian_form_extrapolates_monotonically():
    """VD82 p. 583's reason for eq. (5) — beyond the fitted
    range spectrum A falls smoothly and stays positive."""
    td, cw, n = VD82_RANGE["A"]
    beyond = np.linspace(td + cw * n, 40000.0, 2000)
    i = incident_intensity(beyond, 2, to_ms_block(VD82_A, True))
    assert np.all(i > 0.0)
    assert np.all(np.diff(i) < 0.0)


def test_the_millisecond_conversion_happens_exactly_once():
    """1000 µs behaves as T = 1 ms.  (The block [0, 1, 1, 0, …] is e⁻¹
    alone, and P₁ = 1 gives 1 + e⁻¹ — both asserted.)"""
    assert incident_intensity(1000.0, 1, [0, 1, 1] + [0] * 9) == pytest.approx(math.exp(-1), rel=1e-15)
    assert incident_intensity(1000.0, 1, [1, 1, 1] + [0] * 9) == pytest.approx(1 + math.exp(-1), rel=1e-15)
    # and a µs argument read as ms would be e^{-1000}, i.e. nothing
    assert incident_intensity(1.0, 1, [0, 1, 1] + [0] * 9) == pytest.approx(math.exp(-1e-3))


def test_type_three_and_type_five_differ_only_in_x():
    """X = 2/T − 1 (ITYP 3) against X = T/10 (ITYP 5).  At
    the T where the two maps agree, T² + 10T − 20 = 0, the same coefficients
    give the same value; elsewhere they do not."""
    c = [0.7, -0.2, 0.05, 0.3, -0.1, 0.02, 0.01, -0.03, 0.004, 0.002, -0.001, 0.0005]
    t_ms = -5.0 + math.sqrt(45.0)
    assert 2.0 / t_ms - 1.0 == pytest.approx(t_ms / 10.0, rel=1e-15)
    assert incident_intensity(1000.0 * t_ms, 3, c) == pytest.approx(
        incident_intensity(1000.0 * t_ms, 5, c), rel=1e-13)
    assert incident_intensity(5000.0, 3, c) != pytest.approx(incident_intensity(5000.0, 5, c))


def test_the_chebyshev_types_are_chebyshev_series():
    """ITYP 3/5 are Σ P_j T_{j−1}(X); ITYP 4 is P₁ + Maxwellian +
    Σ_{j=4}^{12} P_j T_{j−3}(X) with ITYP 3's X (manual p. 128-129).  Checked
    against numpy's Clenshaw evaluation, which shares no code with the
    recurrence."""
    c = [0.7, -0.2, 0.05, 0.3, -0.1, 0.02, 0.01, -0.03, 0.004, 0.002, -0.001, 0.0005]
    t_us = np.linspace(1500.0, 90000.0, 37)
    t = t_us / 1000.0
    x = 2.0 / t - 1.0
    assert np.allclose(incident_intensity(t_us, 3, c), chebval(x, c), rtol=1e-13, atol=1e-15)
    assert np.allclose(incident_intensity(t_us, 5, c), chebval(t / 10.0, c), rtol=1e-13, atol=1e-15)
    want4 = c[0] + c[1] / t ** 5 * np.exp(-c[2] / t ** 2) + chebval(x, [0.0] + c[3:])
    assert np.allclose(incident_intensity(t_us, 4, c), want4, rtol=1e-13, atol=1e-15)


def test_the_fifth_pair_is_p10_exp_minus_p11_t_to_the_fifth():
    """The sixth term of ITYP 1 and 2 is P₁₀·exp(−P₁₁·T⁵), T in ms — the
    exponent established by conformance against GSAS-II 5.8.2's computed
    spectrum (``tof_spectrum``'s docstring).  Asserted as the difference the
    pair makes, at three flight times where the term is neither ≈ P₁₀ nor ≈ 0,
    against the closed form."""
    base = [1.0, 2.0, 0.3, 0.5, 0.01, 0.25, 1e-3, 0.1, 1e-4]
    p10, p11 = 5.0, 1e-3
    t_us = np.array([2500.0, 3500.0, 4500.0])
    want = p10 * np.exp(-p11 * (t_us / 1000.0) ** 5)
    assert np.all((want > 0.5) & (want < 4.75))
    for itype in (1, 2):
        got = (incident_spectrum(itype, base + [p10, p11], t_us)
               - incident_spectrum(itype, base + [0.0, 0.0], t_us))
        assert got == pytest.approx(want, rel=1e-12)


#: GSAS-II 5.8.2's own incident spectrum for one synthetic ICOFF block, read
#: off as I_i = Y₀/Yobs from a flat pattern (Y₀ = 1000) it imported as a black
#: box on 2026-09-23 (the ``lansce_iparm`` module docstring has the run):
#: ``(X µs, Yobs)`` at three of its bin centres.  Block: P₁ = 1, P₁₀ = 5,
#: P₁₁ = 1e-3, the rest zero — ITYP 1 and ITYP 2 gave the same numbers.
ORACLE_FIFTH_PAIR_BLOCK = [1.0] + [0.0] * 8 + [5.0, 1e-3]
ORACLE_FIFTH_PAIR_POINTS = [(2500.8517, 180.69954374067368),
                            (3500.35645, 252.7589305502936),
                            (4499.1497, 558.259330610657)]


def test_the_six_term_sum_is_gsas2s_computed_spectrum():
    """The whole ITYP 1/2 sum, fifth pair included, equals the spectrum
    GSAS-II computed from the same block, to 1e-12 relative."""
    x = np.array([p[0] for p in ORACLE_FIFTH_PAIR_POINTS])
    oracle = 1000.0 / np.array([p[1] for p in ORACLE_FIFTH_PAIR_POINTS])
    for itype in (1, 2):
        got = incident_spectrum(itype, ORACLE_FIFTH_PAIR_BLOCK, x)
        assert got == pytest.approx(oracle, rel=1e-12)


def test_refusals_by_name_and_by_value():
    """ITYP 10 refused by name, an undefined ITYP by value,
    a wrong coefficient count and a non-zero unused slot refused."""
    with pytest.raises(ValueError, match="point-by-point"):
        incident_intensity(5000.0, 10, [])
    for bad in (6, 7, -1, 99):
        with pytest.raises(ValueError, match=f"ITYP {bad} is not an incident"):
            incident_intensity(5000.0, bad, [])
    with pytest.raises(ValueError, match="ITYP 0 takes no coefficients"):
        incident_spectrum(0, [1.0], 5000.0)
    for itype, want in COEFFICIENT_COUNTS.items():
        if want:
            with pytest.raises(ValueError, match=f"uses {want} coefficients"):
                incident_spectrum(itype, [0.0] * (want + 1), 5000.0)
    with pytest.raises(ValueError, match="P12 = 0.7"):
        incident_intensity(5000.0, 1, [1.0] + [0.0] * 10 + [0.7])
    assert sorted(SPECTRUM_TYPES) == sorted(COEFFICIENT_COUNTS) == [0, 1, 2, 3, 4, 5]


def test_the_moderator_temperature_is_the_manuals_expression():
    """t = 2.374e-4·C²/(P₃·sin 2Θ) (manual p. 128)."""
    assert moderator_temperature(35.59, 12000.0, 90.0) == pytest.approx(
        2.374e-4 * 12000.0 ** 2 / 35.59)


# ------------------------------------------------------------ Lorentz factor
def test_the_tof_lorentz_factor_is_d4_sin_theta():
    """L = d⁴·sin Θ (manual p. 140), Θ the bank's Bragg angle, in
    degrees (the package convention)."""
    d = np.array([0.8, 1.6, 3.2])
    got = tof_lorentz(d, 45.0)
    assert np.allclose(got, d ** 4 * math.sin(math.radians(45.0)), rtol=1e-15)
    assert got[1] / got[0] == pytest.approx(16.0)


# ------------------------------------------------------------ Sabine
def test_the_laue_series_carries_the_published_digits():
    """1 − x/2 + x²/4 − 5x³/48 + 7x⁴/192 (x ≤ 1) and
    (2/πx)^½[1 − 1/(8x) − 3/(128x²) − 15/(1024x³)] (x > 1), S88 eqs. 3-4.
    θ = 0 isolates E_L, θ = 90° isolates E_B = (1+x)^−½; θ in degrees."""
    x = 0.5
    assert float(sabine_extinction(x, 0.0)) == pytest.approx(
        1 - x / 2 + x ** 2 / 4 - 5 * x ** 3 / 48 + 7 * x ** 4 / 192, rel=1e-15)
    x = 4.0
    assert float(sabine_extinction(x, 0.0)) == pytest.approx(
        math.sqrt(2 / (math.pi * x)) * (1 - 1 / (8 * x) - 3 / (128 * x ** 2)
                                        - 15 / (1024 * x ** 3)), rel=1e-15)
    assert float(sabine_extinction(3.0, 90.0)) == pytest.approx(0.5, rel=1e-15)
    theta = math.radians(30.0)
    x = 0.3
    el = float(sabine_extinction(x, 0.0))
    assert float(sabine_extinction(x, 30.0)) == pytest.approx(
        el * math.cos(theta) ** 2 + (1 + x) ** -0.5 * math.sin(theta) ** 2, rel=1e-15)


def test_the_published_step_at_x_equal_one_is_kept():
    """E_L(1⁻) = 0.68229, E_L(1⁺) = 0.66774 — a 2.2 % step in
    the published formulas, pinned so a later 'fix' cannot smooth it away.
    (The quoted 0.66774 is 0.79788 × 0.8369 rounded; the exact value of S88
    eq. 4 at x = 1 is √(2/π)·0.8369140625 = 0.667761, hence abs=3e-5.)"""
    below = float(sabine_extinction(1.0, 0.0))
    above = float(sabine_extinction(np.nextafter(1.0, 2.0), 0.0))
    assert below == pytest.approx(0.68229, abs=5e-6) == SABINE_LAUE_SERIES_AT_1
    assert above == pytest.approx(0.66774, abs=3e-5)
    assert above == pytest.approx(SABINE_LAUE_ASYMPTOTE_AT_1, rel=1e-14)
    assert (below - above) / below == pytest.approx(0.0213, abs=1e-3)


def test_sabine_is_finite_at_zero_and_far_out():
    """both branches evaluated on clamped arguments."""
    x = np.array([0.0, 1e-12, 1.0, 1e6, 1e300])
    e = sabine_extinction(x, 23.0)
    assert np.all(np.isfinite(e)) and float(e[0]) == 1.0


def test_ext_is_the_squared_block_size_s88_table_1():
    """x = (K·N_c·λ·F·D)² (S88 eq. 6) equals E_x(λF/V)² with
    E_x = (K·D)²; S88 Table 1's EXT = 75.4 and 140.2 µm² against D = 8.7(1) and
    11.8(1) µm for a cube (K = 1)."""
    lam, f_fm, vol = 1.4, 43.0, 74.7
    for ext, d_um in ((75.4, 8.7), (140.2, 11.8)):
        assert math.sqrt(ext) == pytest.approx(d_um, abs=0.1)
        d_a = math.sqrt(ext) * 1e4                    # µm → Å
        direct = (1.0 * (1.0 / vol) * lam * (f_fm * 1e-5) * d_a) ** 2
        assert sabine_x(ext, lam, f_fm, vol) == pytest.approx(direct, rel=1e-13)


# ------------------------------------------------------------ µ(λ)
def test_mu_is_affine_in_lambda_with_the_absorption_as_its_slope():
    """µ(λ) = Σn[σ_abs·λ/1.798 + σ_coh + σ_inc]/V — the caller contract of
    ``forward_tof`` (WP-1132's formula over Sears 1992)."""
    counts, vol = {"Si": 8.0}, 5.4311946 ** 3
    a, b = neutron_attenuation_terms(counts, vol)
    row = properties("Si")
    assert b == pytest.approx(8.0 * (row["xs_coh_barn"] + row["xs_inc_barn"]) / vol, rel=1e-14)
    assert a == pytest.approx(8.0 * row["xs_abs_barn"] / (THERMAL_WAVELENGTH * vol), rel=1e-14)
    assert neutron_linear_attenuation(counts, vol, 2.5) == pytest.approx(2.5 * a + b, rel=1e-15)
    with pytest.raises(ValueError, match="volume must be positive"):
        neutron_attenuation_terms(counts, 0.0)
    with pytest.raises(KeyError):
        neutron_attenuation_terms({"Xx": 1.0}, vol)


def test_the_schema_accepts_a_non_zero_fifth_pair():
    """ITYP 1/2's P10, P11 carry the conformance-established fifth term, so a
    non-zero pair is a legal spectrum, and a stored one evaluates."""
    from rietx.schemas.common import Parameter  # noqa: PLC0415
    from rietx.schemas.instrument import IncidentSpectrum  # noqa: PLC0415

    base = [5.0, 800.0, 0.11, 900.0, 4.5e-3, 1000.0, 5.0e-4, -1400.0, 3.4e-4,
            0.0, 0.0]
    for itype in (1, 2):
        IncidentSpectrum(itype=itype,
                         coefficients=[Parameter(value=v) for v in base])
        vals = base[:9] + [5.0, 1e-3]
        sp = IncidentSpectrum(itype=itype,
                              coefficients=[Parameter(value=v) for v in vals])
        assert [c.value for c in sp.coefficients][9:] == [5.0, 1e-3]
        assert np.isfinite(incident_spectrum(
            itype, [c.value for c in sp.coefficients], 3000.0))
    # the Chebyshev types: slots 10 and 11 are ordinary coefficients
    IncidentSpectrum(itype=3, coefficients=[Parameter(value=0.1)] * 12)
