"""A specimen's size and microstrain on a time-of-flight bank (T-3c).

rietx has carried a phase's crystallite size and microstrain since WP-1131,
written as Caglioti coefficients in deg 2θ, and a bank's table force-fixed all
four: the flight-time branch could not read a width in degrees.  It can read
the *specimen*, which is what those coefficients stand for — a bank broadens by

    ΔT = DIFC·(K/L)·d²   (size)      ΔT = DIFC·ε·d   (microstrain)

— so this rung gives the bank its own expression of the same two quantities and
lifts the force-fix.  It is what a later **joint** fit needs — one crystallite
size and one microstrain across a constant-wavelength histogram and a bank —
and that fit, with the unit bridge between the two size spellings, is the
multi-bank cut's; here each arm is tested alone.

Three things this file is careful about, because they are how the rung goes
wrong:

* **What is shared is a quantity, never a coefficient.**  A microstrain
  coefficient is λ-free and is literally the same number on both arms; a size
  coefficient is (180/π)·K·λ/L and is a length only through a wavelength, which
  a white beam has not got.  So a bank holds the size in d-space, K/L in Å⁻¹.
* **Units.**  Å against µm, Δd/d against a strain quoted in 10⁻⁶, a FWHM
  against a variance, a Lorentzian FWHM against a HWHM.  Each is checked
  against the relation it comes from rather than against a remembered factor.
* **The broadening enters γ and σ² before the Thompson-Cox-Hastings mixing.**
  Adding it to the mixed Γ instead would be a width of neither shape, and the
  difference is measurable — it is measured below.

Every fixture here is synthetic.  rietx's own defaults stay at **zero**
broadening, which is a physical statement (an infinite, strain-free crystal)
and no other program's non-zero defaults are adopted.
"""

from __future__ import annotations

import hashlib
import math

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward_tof import compile_tof_model, sample_broadening_terms
from rietx.model.profiles.caglioti import (
    SCHERRER_K,
    apparent_size_from_d_size_coefficient,
    apparent_size_from_size_coefficient,
    d_size_coefficient_for_size,
    size_coefficient_for_size,
    strain_coefficient_for_microstrain,
)
from rietx.model.profiles.tof import (
    tof_gamma,
    tof_pseudovoigt_widths,
    tof_sample_gamma,
    tof_sample_sigma_sq,
    tof_sigma_sq,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter as P
from rietx.schemas.instrument import BackgroundChebyshev, ProfileTOF
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure

# ----------------------------------------------------------------------
# a synthetic bank and a constant-wavelength instrument
# ----------------------------------------------------------------------
#: The generating cell — silicon's, near enough to be recognisable and taken
#: from no certificate: nothing here is compared against one.
A_GEN = 5.4311946

#: ``(difc, tzero, two_theta_bank_deg)`` and the flight-time grid of the bank.
BANK_90 = dict(difc=12000.0, tzero=-5.0, two_theta=90.0)
GRID_90 = (8000.0, 45000.0, 5.0)

CW_LAMBDA = 1.5406


def silicon(a: float = A_GEN) -> Structure:
    """Si, Fd-3m:2, one atom on 8a — no free coordinate, one Biso."""
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2",
        cell=Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                  alpha=P(value=90.0), beta=P(value=90.0),
                  gamma=P(value=90.0)),
        scale=P(value=1.0, min=0.0, transform="softplus"),
        atoms=[Atom(label="Si", species="Si", x=P(value=0.125),
                    y=P(value=0.125), z=P(value=0.125),
                    biso=P(value=0.5, min=0.0, max=5.0))])])


def bank(*, difc: float, tzero: float, two_theta: float, n_background: int = 4,
         **profile) -> rx.Instrument:
    """One synthetic bank with a Chebyshev background."""
    coeffs = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)
    coeffs.update(profile)
    ins = rx.Instrument.tof_neutron_bank(
        difc=difc, tzero=tzero, two_theta_bank_deg=two_theta,
        profile=ProfileTOF(**{k: P(value=v, unit=None)
                              for k, v in coeffs.items()}))
    ins.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(n_background)])
    return ins


def cw_instrument(wavelength: float = CW_LAMBDA,
                  n_background: int = 4) -> rx.Instrument:
    ins = rx.Instrument.debye_scherrer(wavelength=wavelength)
    ins.background = BackgroundChebyshev(
        coefficients=[P(value=0.0) for _ in range(n_background)])
    ins.profile.u.value, ins.profile.v.value = 0.02, -0.01
    ins.profile.w.value = 0.008
    return ins


def _poisson_from(model, structure, instrument, seed: int) -> np.ndarray:
    table = ParameterTable(structure, instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64)
    return np.random.default_rng(seed).poisson(
        np.maximum(y, 0.0)).astype(np.float64)


def tof_pattern(ins: rx.Instrument, grid: tuple[float, float, float], *,
                seed: int, scale: float = 12.0,
                background=(40.0, -8.0)) -> PatternData:
    """A bank generated from the model it will be refined against.

    ``intensity_basis="counts"`` throughout: that is what a LANSCE ``TIME_MAP``
    bank and a Mantid ``SaveGSS`` export declare, so the channel-width factor is
    in both the generating model and the fitted one.  Poisson noise on the
    compiled curve, so χ² ≈ 1 is a real bar rather than a coincidence.
    """
    from rietx.model.forward_tof import compile_tof_model

    lo, hi, step = grid
    x = np.arange(lo, hi + 0.5 * step, step)
    blank = PatternData(tof=x.tolist(), intensity=[1.0] * len(x),
                        intensity_basis="counts")
    gen = ins.model_copy(deep=True)
    for k, v in enumerate(background):
        gen.background.coefficients[k].value = v
    structure = silicon()
    structure.phases[0].scale.value = scale
    y = _poisson_from(compile_tof_model(structure, gen, blank), structure, gen,
                      seed)
    return PatternData(tof=x.tolist(), intensity=y.tolist(),
                       intensity_basis="counts")



#: The four paths this rung is about.
WIDTHS = ("lor_size", "gauss_size", "lor_strain", "gauss_strain")

DIFC = 12000.0          # µs/Å, the 90° synthetic bank's


def broadened(*, lor_size=0.0, lor_strain=0.0, gauss_size=0.0,
              gauss_strain=0.0):
    s = silicon()
    ph = s.phases[0]
    for name, v in (("lor_size", lor_size), ("lor_strain", lor_strain),
                    ("gauss_size", gauss_size),
                    ("gauss_strain", gauss_strain)):
        setattr(ph, name, P(value=v, min=0.0, transform="softplus"))
    return s


@pytest.fixture(scope="module")
def tof_data():
    return tof_pattern(bank(**BANK_90), GRID_90, seed=31)


# ----------------------------------------------------------------------
# 1. the two laws, and the units they are written in
# ----------------------------------------------------------------------
def test_the_two_laws_are_the_powers_of_d_the_physics_gives():
    """Size goes as d², microstrain as d¹ — and *which* is which is the whole
    content of the term.

    Derived rather than asserted from memory: microstrain is a constant Δd/d,
    and T = DIFC·d, so ΔT = DIFC·d·(Δd/d) is linear.  Size is a constant
    ΔQ = 2πK/L; Q = 2π/d makes that Δd/d = (K/L)·d, so ΔT picks up one more
    power.  Getting them the wrong way round is the negative control of this
    rung's acceptance and it is the failure a bank cannot see at one d.
    """
    d = np.array([1.0, 2.0, 4.0])
    size = tof_sample_gamma(d, DIFC, size_per_a=1e-4, strain=0.0)
    strain = tof_sample_gamma(d, DIFC, size_per_a=0.0, strain=1e-3)
    assert size[1] / size[0] == pytest.approx(4.0)      # d²
    assert size[2] / size[1] == pytest.approx(4.0)
    assert strain[1] / strain[0] == pytest.approx(2.0)  # d¹
    assert strain[2] / strain[1] == pytest.approx(2.0)
    # and they add, because Lorentzian FWHMs do
    both = tof_sample_gamma(d, DIFC, size_per_a=1e-4, strain=1e-3)
    assert both == pytest.approx(size + strain)


def test_the_gaussian_pair_add_as_variances_not_as_widths():
    """The size and strain Gaussian variances add, with the squares taken on the
    coefficients so no square root of a refined parameter reaches the residual.

    The quadrature is not a convention: two independent Gaussian broadenings
    convolve, and variances are what add under convolution.  Adding the widths
    would over-broaden by up to √2.
    """
    from rietx.model.profiles.voigt import GAUSS_FWHM_TO_SIGMA

    d = np.array([1.0, 2.5])
    size_c, strain_c = 1e-4, 1e-3
    var = tof_sample_sigma_sq(d, DIFC, size_var=size_c ** 2,
                              strain_var=strain_c ** 2)
    w_size = DIFC * size_c * d ** 2
    w_strain = DIFC * strain_c * d
    # written out rather than through the package constant: ``ateln2`` is the
    # factor most easily applied upside down, and a test that reused the name
    # would agree with the code whichever way round it was
    assert var == pytest.approx(
        (w_size ** 2 + w_strain ** 2) / (8.0 * math.log(2.0)))
    # …and *not* the square of the summed widths
    assert not np.allclose(
        var, (w_size + w_strain) ** 2 / (8.0 * math.log(2.0)))
    # the package's constant is Γ_G/σ, so a variance *divides* by its square
    assert GAUSS_FWHM_TO_SIGMA ** 2 == pytest.approx(8.0 * math.log(2.0))


def test_a_crystallite_gives_the_same_delta_d_over_d_on_both_arms():
    """The units control, and the sharpest statement the rung makes.

    A 100 nm crystallite is 100 nm however it was measured, so the *fractional*
    d-spacing broadening it causes at a given d must be one number — computed
    on a bank from K/L, and on a constant-wavelength scan from a coefficient in
    degrees at the angle where that d is measured.  The constant-wavelength
    route goes through Bragg's law twice (λ = 2d sinθ to find the angle, then
    Δ2θ = 2·tanθ·Δd/d to read the width back), so an agreement here is the two
    conversions closing rather than one of them repeated.
    """
    lam, size_a = 1.5406, 1000.0                # 100 nm
    x_cw = size_coefficient_for_size(size_a, lam, SCHERRER_K)      # deg
    s_tof = d_size_coefficient_for_size(size_a, SCHERRER_K)        # Å⁻¹
    for d in (0.9, 1.4, 2.6):
        theta = math.asin(min(lam / (2.0 * d), 1.0))
        # the constant-wavelength Lorentzian size law, x/cosθ, as a Δd/d
        width_deg = x_cw / math.cos(theta)
        dd_cw = math.radians(width_deg) / (2.0 * math.tan(theta))
        dd_tof = s_tof * d
        assert dd_cw == pytest.approx(dd_tof, rel=1e-12)
    # and both invert to the size that generated them
    assert apparent_size_from_size_coefficient(x_cw, lam, SCHERRER_K) == (
        pytest.approx(size_a))
    assert apparent_size_from_d_size_coefficient(s_tof, SCHERRER_K) == (
        pytest.approx(size_a))


def test_the_stored_coefficients_read_as_the_specimen_quantities():
    """``sample_broadening_terms`` is the seam between the two, and the Gaussian
    pair are variances on both sides of it."""
    eps, eps_g = 2.0e-3, 5.0e-4
    s = broadened(lor_size=3e-3, gauss_size=4e-6,
                  lor_strain=strain_coefficient_for_microstrain(eps),
                  gauss_strain=strain_coefficient_for_microstrain(eps_g) ** 2)
    values = {f"phases.0.{n}": getattr(s.phases[0], n).value for n in WIDTHS}
    size_l, strain_l, size_var, strain_var = sample_broadening_terms(0, values)
    assert size_l == pytest.approx(3e-3)
    assert strain_l == pytest.approx(eps)
    assert size_var == pytest.approx(4e-6)          # (K/L)², Å⁻²
    assert math.sqrt(strain_var) == pytest.approx(eps_g)
    # a dict that mentions none of them is a phase that declares none
    assert sample_broadening_terms(0, {}) == (0.0, 0.0, 0.0, 0.0)


# ----------------------------------------------------------------------
# 2. where it enters the profile
# ----------------------------------------------------------------------
def test_the_broadening_enters_gamma_and_sigma_before_the_tch_mixing(tof_data):
    """Into the two shapes' own widths, not onto the mixed one.

    The Thompson-Cox-Hastings construction is not linear in γ, so "add the
    sample width to Γ" and "add it to γ and re-mix" are different peaks —
    measurably, which is what makes this a test rather than a comment.
    """
    ins = bank(**BANK_90)
    s = broadened(lor_size=2e-3, lor_strain=0.2)
    model = compile_tof_model(s, ins, tof_data)
    table = ParameterTable(s, ins)
    values = table.decode(table.x0())
    d = np.array([1.0, 2.0])

    _a, _b, sigma, gamma = model.shape_parameters(d, values, 0)
    _a2, _b2, sigma0, gamma0 = model.shape_parameters(d, values)
    p = "instrument.source.profile_tof."
    delta = tof_sample_gamma(d, values["instrument.source.difc"],
                             *sample_broadening_terms(0, values)[:2])
    assert gamma == pytest.approx(gamma0 + delta)
    assert gamma0 == pytest.approx(
        tof_gamma(d, values[p + "gam0"], values[p + "gam1"], values[p + "gam2"]))
    assert sigma == pytest.approx(sigma0)          # no Gaussian term declared

    right, _eta, _s = tof_pseudovoigt_widths(sigma, gamma)
    wrong, _eta2, _s2 = tof_pseudovoigt_widths(sigma0, gamma0)
    assert not np.allclose(right, wrong + delta, rtol=1e-6)
    # the mixing is sub-linear in γ, so "add to Γ" over-broadens — by 1.8 % at
    # the short-d end of this bank, which is the size of the mistake
    assert np.all(right < wrong + delta)
    # and the peak the model actually makes is wider than the instrument's
    assert np.all(model.peak_fwhm(_a, _b, sigma, gamma)
                  > model.peak_fwhm(_a, _b, sigma0, gamma0))


def test_a_broadened_phase_makes_broader_peaks(tof_data):
    """End to end: the same model with and without a specimen width, on the
    fitted grid.  A broadening that never reached the curve would pass every
    unit test above."""
    ins = bank(**BANK_90)
    plain = silicon()
    wide = broadened(lor_size=4e-3, lor_strain=0.3)
    ys = []
    for s in (plain, wide):
        model = compile_tof_model(s, ins, tof_data)
        table = ParameterTable(s, ins)
        ys.append(np.asarray(model.phase_component(0, table.decode(table.x0()))))
    lo, hi = ys
    assert hi.max() < 0.75 * lo.max()              # spread out, so lower
    # …and the area is kept to within the frozen windows' own tail discard,
    # which is the 2·TOF_WINDOW_AREA_TOL per side a broader peak pays twice
    assert hi.sum() == pytest.approx(lo.sum(), rel=2e-2)
    assert hi.sum() < lo.sum()


def test_the_frozen_windows_hold_the_broadened_peak(tof_data):
    """The window is cut at compile time from the widths the stage starts at,
    so a phase that declares a broadening must get a wider window — otherwise
    the term is added and then truncated away."""
    ins = bank(**BANK_90)
    narrow = compile_tof_model(silicon(), ins, tof_data)
    wide = compile_tof_model(broadened(lor_size=4e-3, lor_strain=0.3), ins,
                             tof_data)
    n = narrow.phases[0].win[0]
    w = wide.phases[0].win[0]
    assert np.all((w[:, 1] - w[:, 0]) >= (n[:, 1] - n[:, 0]))
    assert (w[:, 1] - w[:, 0]).sum() > 1.2 * (n[:, 1] - n[:, 0]).sum()


def test_a_lorentzian_sample_width_compiles_the_pseudovoigt_branch(tof_data):
    """``profile_kind`` is a structural decision made from "can γ move off
    zero this stage".  A phase's Lorentzian width is a γ, so it decides it too
    — and a stage that frees the path decides it even at a value of zero."""
    ins = bank(**BANK_90)                       # gam0 = gam1 = gam2 = 0
    assert compile_tof_model(silicon(), ins, tof_data).profile_kind == "gaussian"
    assert compile_tof_model(broadened(lor_size=1e-4), ins,
                             tof_data).profile_kind == "pseudovoigt"
    assert compile_tof_model(
        silicon(), ins, tof_data,
        moving_paths={"phases.0.lor_strain"}).profile_kind == "pseudovoigt"
    # a Gaussian-only sample width does not: it is a σ², not a γ
    assert compile_tof_model(broadened(gauss_size=1e-8), ins,
                             tof_data).profile_kind == "gaussian"


# ----------------------------------------------------------------------
# 3. the table — the widths are free on both arms
# ----------------------------------------------------------------------
def test_the_four_widths_are_free_on_a_bank_and_still_free_on_a_scan():
    """The force-fix lift, both arms.  On a constant-wavelength table nothing
    changes at all, which is the control: this rung must not touch that arm."""
    for ins in (bank(**BANK_90), cw_instrument()):
        table = ParameterTable(silicon(), ins)
        by = {e.path: e for e in table.entries}
        for name in WIDTHS:
            assert not by[f"phases.0.{name}"].locked, (name, ins.source.kind)
    # an X-ray histogram is untouched in every respect the table can show
    xray = ParameterTable(silicon(), rx.Instrument.bragg_brentano())
    for name in WIDTHS:
        e = {x.path: x for x in xray.entries}[f"phases.0.{name}"]
        assert not e.locked and not e.vary and e.lo == 0.0


def test_the_microstructure_block_reads_a_bank_rather_than_abstaining():
    """WP-1131's reporting half, on the arm that used to say ``no_wavelength``.

    L in Å and Δd/d are axis-free, so all four rows read; the block's own
    ``wavelength`` stays ``None``, because a bank still has none and this
    module must not invent one to report a size with.
    """
    from rietx.model.microstructure import microstructure_table

    size_a, eps = 620.0, 8.0e-4
    s = broadened(lor_size=d_size_coefficient_for_size(size_a, SCHERRER_K),
                  lor_strain=strain_coefficient_for_microstrain(eps))
    values = {f"phases.0.{n}": getattr(s.phases[0], n).value for n in WIDTHS}
    block, = microstructure_table(s, values, wavelength=None, tof=True)
    assert block.wavelength is None
    assert block.term("lor_size").value == pytest.approx(size_a)
    assert block.term("lor_strain").value == pytest.approx(eps)
    # the row reads: what is missing is only its esd, which no covariance was
    # handed here — and *not* the wavelength this arm used to abstain over
    assert block.term("lor_size").unavailable == "not_measured"
    # the same numbers read as a constant-wavelength table abstain, correctly:
    # that coefficient is a length only through a λ
    cw, = microstructure_table(s, values, wavelength=None, tof=False)
    assert cw.term("lor_size").unavailable == "no_wavelength"
    assert cw.term("lor_strain").value == pytest.approx(eps)


# ----------------------------------------------------------------------
# 4. negative controls
# ----------------------------------------------------------------------
def _phase_hash(structure, ins, pattern) -> str:
    model = compile_tof_model(structure, ins, pattern)
    table = ParameterTable(structure, ins)
    y = np.asarray(model.phase_component(0, table.decode(table.x0())),
                   dtype=np.float64)
    h = hashlib.sha256(y.tobytes())
    h.update(np.asarray(model.phases[0].win, dtype=np.int64).tobytes())
    h.update(model.profile_kind.encode())
    return h.hexdigest()


def test_an_infinite_strain_free_crystal_is_the_tree_without_this_rung(tof_data):
    """rietx's defaults are zero broadening, and zero must mean *absent* rather
    than *evaluated to zero*: every term added by this rung is an exact ±0
    there, so the curve, the frozen windows and the shape branch are the ones a
    build without the term produces.

    Hashed rather than compared with a tolerance, because the claim is
    bit-identity and a tolerance would pass on a term that was merely small.
    An explicit zero and a phase that never mentions the widths must give the
    same bytes, which is the statement a reader of the acceptance numbers
    needs: none of T-3b's, T-5's or the integration rung's numbers can move.
    """
    ins = bank(**BANK_90)
    absent = _phase_hash(silicon(), ins, tof_data)
    explicit = _phase_hash(broadened(), ins, tof_data)
    assert absent == explicit
    # and the shape branch is the pre-rung one
    assert compile_tof_model(silicon(), ins, tof_data).profile_kind == "gaussian"
    # a size of 10 µm and a strain of 10⁻⁶ are *not* zero, and must not hash
    # equal — the control that the hash above can fail at all
    assert _phase_hash(broadened(lor_size=d_size_coefficient_for_size(1e5),
                                 lor_strain=strain_coefficient_for_microstrain(
                                     1e-6)), ins, tof_data) != absent


def test_the_size_term_at_the_wrong_power_of_d_is_a_different_model(tof_data):
    """The acceptance's negative control, in miniature.

    Reading the bank's size coefficient through λ_eff = 2·d·sinθ_bank — the
    obvious way to reuse a deg-2θ coefficient on a bank — turns the d² law into
    a d¹ one, which is the *strain* law wearing the size's name.  At a single d
    the two are indistinguishable by construction, so the test is that they
    disagree across the fitted range, and by how much.
    """
    d = np.array([0.8, 1.6, 3.2])
    right = tof_sample_gamma(d, DIFC, size_per_a=2e-3, strain=0.0)
    wrong = DIFC * 2e-3 * d                     # the d¹ mistake
    scale = right[1] / wrong[1]                 # matched at the middle d
    assert right[0] / (scale * wrong[0]) == pytest.approx(0.5)
    assert right[2] / (scale * wrong[2]) == pytest.approx(2.0)


def test_the_instrument_only_shape_is_unchanged_by_the_new_argument(tof_data):
    """``shape_parameters`` grew a phase argument; without it, it is the
    function T-1b wrote.  The four returned arrays must be the instrument's
    own laws, evaluated in the order they always were."""
    ins = bank(**BANK_90)
    s = broadened(lor_size=5e-3, lor_strain=0.4)   # a broadening it must ignore
    model = compile_tof_model(s, ins, tof_data)
    table = ParameterTable(s, ins)
    values = table.decode(table.x0())
    d = np.array([1.0, 2.0, 3.0])
    p = "instrument.source.profile_tof."
    _a, _b, sigma, gamma = model.shape_parameters(d, values)
    assert gamma == pytest.approx(
        tof_gamma(d, values[p + "gam0"], values[p + "gam1"], values[p + "gam2"]))
    assert sigma ** 2 == pytest.approx(
        tof_sigma_sq(d, values[p + "sig0"], values[p + "sig1"],
                     values[p + "sig2"]))
