"""What varies with wavelength inside one time-of-flight histogram.

The three corrections of T-3 (yue-here/rietx issue #193): the incident spectrum
a GSAS instrument-parameter file declares, and the specimen absorption and
secondary extinction that follow λ across a bank.

**Every fixture here is synthetic and written in this file.**  No real
instrument file is in the repository.
"""

from __future__ import annotations

import math

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.neutron import properties
from rietx.model.absorption import CYLINDER_MU_R_MAX, cylinder_absorption
from rietx.model.extinction import sabine_extinction
from rietx.model.forward_tof import compile_tof_model
from rietx.model.tof_spectrum import (
    COEFFICIENT_COUNTS,
    SPECTRUM_TYPES,
    THERMAL_WAVELENGTH,
    incident_spectrum,
    neutron_attenuation_terms,
    neutron_linear_attenuation,
)
from rietx.params.vector import ParameterTable
from rietx.schemas.instrument import IncidentSpectrum
from rietx.schemas.pattern import PatternData
from rietx.schemas.structure import Atom, Cell, Phase, Structure

P = rx.Parameter

#: A synthetic ``ITYP 1``/``ITYP 2`` coefficient set: eleven numbers of the
#: shape a real moderator fit has (a small constant, then amplitude/rate pairs
#: of decreasing size), invented here so no line of anybody's beamtime file
#: enters the repository.  The fifth pair (P10, P11) is zero here, so the
#: long-hand sum below stops at the T⁴ term; its T⁵ law is pinned separately
#: (GSAS Technical Manual p. 128; Von Dreele, Jorgensen & Windsor 1982
#: eqs. 4-5; the exponent by conformance, ``tof_spectrum``'s docstring).
ELEVEN = [5.0, 800.0, 0.11, 900.0, 4.5e-3, 1000.0, 5.0e-4, -1400.0, 3.4e-4,
          0.0, 0.0]
#: Twelve for the Chebyshev types.
TWELVE = [3.0, 1.4, -0.9, 0.55, -0.3, 0.17, -0.09, 0.05, -0.02, 0.011,
          -0.006, 0.003]

TOF_LO, TOF_HI, TOF_STEP = 8000.0, 45000.0, 20.0
#: mm.  The capillary of the Co absorption control: µR runs 0.13 to 0.63 over
#: this bank, i.e. inside the Rouse domain at both ends and a factor of five
#: apart between them — large enough to bias a displacement parameter and not
#: so large that the control is measuring an extrapolation.
CO_RADIUS_MM = 1.0
PROFILE = dict(alpha1=0.45, beta0=0.055, beta1=0.003, sig1=300.0)


# ---------------------------------------------------------------- the fixtures
def silicon(biso: float = 0.5) -> Structure:
    cell = Cell(a=P(value=5.4311946), b=P(value=5.4311946), c=P(value=5.4311946),
                alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0))
    return Structure(phases=[Phase(
        name="Si", space_group="F d -3 m :2", cell=cell, scale=P(value=1.0),
        atoms=[Atom(label="Si", species="Si", x=P(value=0.125),
                    y=P(value=0.125), z=P(value=0.125), biso=P(value=biso))])])


def bank(*, spectrum: IncidentSpectrum | None = None, two_theta: float = 90.0,
         **geometry):
    ins = rx.Instrument.tof_neutron_bank(
        difc=12000.0, tzero=-5.0, two_theta_bank_deg=two_theta,
        profile=rx.ProfileTOF(**{k: P(value=v) for k, v in PROFILE.items()}),
        **geometry)
    if spectrum is not None:
        ins.source.incident_spectrum = spectrum
    return ins


def blank_pattern(n: int | None = None) -> PatternData:
    grid = np.arange(TOF_LO, TOF_HI + 0.5 * TOF_STEP, TOF_STEP)
    if n is not None:
        grid = grid[:n]
    return PatternData(tof=grid.tolist(), intensity=[1.0] * len(grid))


def values_of(structure, instrument) -> dict[str, float]:
    return {e.path: e.value for e in ParameterTable(structure, instrument).entries}


# ------------------------------------------------- the transcription, by hand
def test_type_one_is_the_manuals_sum_of_exponentials():
    """PAGE 128 and VD82 eq. (4), term by term, written out here rather than looped.

    The point of writing the terms long-hand is that the loop in
    ``tof_spectrum`` and this assertion can only agree if the *pairing* of
    amplitude with rate and the *power* of T in each term are both right, and
    those are the two things a transcription gets wrong.  The powers 1…4 are
    VD82 eq. (4)'s; the fifth pair's, 5, was established by
    conformance, and is asserted as the term a non-zero pair adds.
    """
    t_us = np.array([8000.0, 17500.0, 26200.0, 38400.0, 45000.0])
    t = t_us / 1000.0  # the manual's argument is milliseconds
    p = ELEVEN
    want = (p[0]
            + p[1] * np.exp(-p[2] * t)
            + p[3] * np.exp(-p[4] * t ** 2)
            + p[5] * np.exp(-p[6] * t ** 3)
            + p[7] * np.exp(-p[8] * t ** 4))
    got = incident_spectrum(1, p, t_us)
    # ``approx`` and not ``array_equal``: this expression sums the five terms
    # onto P1 left to right while the module accumulates them and adds P1 last,
    # so the two differ in the last bit or two by floating-point associativity
    # alone.  Writing the sum in the module's own order would make the test a
    # copy of the code rather than an independent statement of the formula.
    assert got == pytest.approx(want, rel=1e-14)
    # three flight times where the term is 298, 216 and 25 of P10 = 300
    p10, p11 = 300.0, 2e-7
    fifth = p10 * np.exp(-p11 * t[:3] ** 5)
    for itype in (1, 2):
        added = (incident_spectrum(itype, [*p[:9], p10, p11], t_us[:3])
                 - incident_spectrum(itype, p, t_us[:3]))
        assert added == pytest.approx(fifth, rel=1e-9)


def test_type_two_replaces_only_the_first_exponential_with_a_maxwellian():
    """PAGE 128, verbatim: *"The 'ITYP 2' function replaces the second term in
    the above function with a Maxwellian expression"* — the second term of the
    whole expression, i.e. the k = 1 exponential, and nothing else.

    Asserted as a *difference* between the two types rather than as a second
    long-hand formula: what is being pinned is that exactly one term moved.
    """
    t_us = np.linspace(8000.0, 45000.0, 11)
    t = t_us / 1000.0
    p = ELEVEN
    moved = p[1] * np.exp(-p[2] / t ** 2) / t ** 5 - p[1] * np.exp(-p[2] * t)
    assert np.allclose(incident_spectrum(2, p, t_us) - incident_spectrum(1, p, t_us),
                       moved, rtol=0, atol=1e-9 * np.max(np.abs(moved)))


def test_the_chebyshev_types_agree_with_numpys_own_chebyshev():
    """An independent implementation of the recurrence, not a second copy of it.

    ``numpy.polynomial.chebyshev.chebval(x, c)`` is Σ cᵢTᵢ(x) by Clenshaw's
    algorithm, which shares no line with the three-term recurrence in
    ``tof_spectrum``.  Type 3 is exactly that sum over all twelve coefficients;
    type 5 is the same sum with X = T/10; type 4 is the Maxwellian plus the
    same sum with T₀ dropped (its coefficient is already P₁) and the rest
    shifted by three.
    """
    from numpy.polynomial.chebyshev import chebval

    t_us = np.linspace(2000.0, 60000.0, 23)
    t = t_us / 1000.0
    x = 2.0 / t - 1.0

    assert np.allclose(incident_spectrum(3, TWELVE, t_us), chebval(x, TWELVE))
    assert np.allclose(incident_spectrum(5, TWELVE, t_us), chebval(t / 10.0, TWELVE))

    # type 4: P1 + Maxwellian + Σ_{j=4..12} P_j T_{j-3}, i.e. nine terms from T1
    tail = chebval(x, [0.0] + TWELVE[3:])
    maxwellian = TWELVE[1] * np.exp(-TWELVE[2] / t ** 2) / t ** 5
    assert np.allclose(incident_spectrum(4, TWELVE, t_us),
                       TWELVE[0] + maxwellian + tail)


def test_the_chebyshev_argument_lands_where_the_manual_says_it_does():
    """The manual's own consistency check, and the unit trap it catches.

    PAGE 128, verbatim: *"Given that the usual range of TOF is 1 to 100
    millisec … then X ranges from about -1 to +1 that is the orthogonal range
    for this function"*.  True in milliseconds.  In **micro**seconds the same
    expression gives X ∈ [−1, −0.99998], i.e. every channel piled onto one end
    of the orthogonal interval, where T₁₁ is ±1 and the twelve terms carry no
    independent information at all — a spectrum that would fit nothing and
    raise nothing.  This is the whole reason the conversion happens once at
    ``tof_spectrum``'s door.
    """
    t_ms = np.array([1.0, 2.0, 10.0, 100.0])
    x_ms = 2.0 / t_ms - 1.0
    assert x_ms.min() > -1.0 and x_ms.max() <= 1.0

    x_us = 2.0 / (t_ms * 1000.0) - 1.0
    assert x_us.max() < -0.99 and np.ptp(x_us) < 2e-3


def test_the_argument_is_a_flight_time_and_the_public_door_takes_microseconds():
    """One value, three ways of saying it — the conversion is where it claims."""
    one_ms_in_us = 1000.0
    p = ELEVEN
    by_hand = (p[0] + p[1] * math.exp(-p[2]) + p[3] * math.exp(-p[4])
               + p[5] * math.exp(-p[6]) + p[7] * math.exp(-p[8]))
    assert incident_spectrum(1, p, np.array([one_ms_in_us]))[0] == pytest.approx(
        by_hand, rel=1e-14)


# ------------------------------------------------------ the refusals (arm F)
def test_type_zero_is_one_and_carries_nothing():
    assert incident_spectrum(0, [], np.linspace(1e3, 4e4, 5)) == 1.0
    with pytest.raises(ValueError, match="ITYP 0 takes no coefficients"):
        incident_spectrum(0, [1.0], np.array([1e4]))
    with pytest.raises(ValueError, match="ITYP 0 takes no coefficients"):
        IncidentSpectrum(itype=0, coefficients=[P(value=1.0)])


def test_an_ityp_the_manual_does_not_define_is_refused_by_number():
    for itype in (6, 7, 99, -1):
        with pytest.raises(ValueError, match=f"ITYP {itype} is not an incident"):
            incident_spectrum(itype, [], np.array([1e4]))
        with pytest.raises(ValueError, match=f"ITYP {itype} is not an incident"):
            IncidentSpectrum(itype=itype)
    # and the five the manual *does* define are all reachable, so the refusal
    # above cannot pass by refusing everything
    assert sorted(SPECTRUM_TYPES) == [0, 1, 2, 3, 4, 5]
    assert sorted(COEFFICIENT_COUNTS) == sorted(SPECTRUM_TYPES)


def test_ityp_ten_is_refused_for_its_own_reason_and_not_as_an_unknown():
    """It exists, and what it needs is a second file — a different complaint."""
    with pytest.raises(ValueError, match="point-by-point"):
        incident_spectrum(10, [], np.array([1e4]))
    with pytest.raises(ValueError, match="point-by-point"):
        IncidentSpectrum(itype=10)


def test_a_coefficient_count_that_disagrees_with_the_type_is_refused_not_padded():
    def block(itype, n):
        return [1.0] * n

    for itype, want in ((1, 11), (2, 11), (3, 12), (4, 12), (5, 12)):
        incident_spectrum(itype, block(itype, want), np.array([1e4]))
        for n in (want - 1, want + 1):
            with pytest.raises(ValueError, match=f"uses {want} coefficients"):
                incident_spectrum(itype, block(itype, n), np.array([1e4]))
            with pytest.raises(ValueError, match=f"uses {want} coefficients"):
                IncidentSpectrum(itype=itype,
                                 coefficients=[P(value=v) for v in block(itype, n)])


def test_the_fitted_window_is_carried_and_checked():
    spec = IncidentSpectrum(itype=1, coefficients=[P(value=v) for v in ELEVEN],
                            tof_min_us=8000.0, tof_max_us=49000.0)
    assert (spec.tof_min_us, spec.tof_max_us) == (8000.0, 49000.0)
    with pytest.raises(ValueError, match="not increasing"):
        IncidentSpectrum(itype=0, tof_min_us=9000.0, tof_max_us=8000.0)
    with pytest.raises(ValueError, match="must be positive"):
        IncidentSpectrum(itype=0, tof_min_us=-1.0)


# ------------------------------------------------ the model applies it, once
def _spectrum(itype: int = 1, coefficients=None) -> IncidentSpectrum:
    coefficients = ELEVEN if coefficients is None else coefficients
    return IncidentSpectrum(
        itype=itype, coefficients=[P(value=v) for v in coefficients],
        tof_min_us=TOF_LO, tof_max_us=TOF_HI)


def test_the_spectrum_multiplies_the_bragg_sum_per_channel_and_not_the_background():
    """The decision the module docstring states, asserted as arithmetic.

    Two claims at once, and they need each other: the factor is the *channel's*
    I_i (not one number per reflection), and the background is untouched.  The
    second is what makes rietx's placement differ from GSAS's — GSAS divides
    the observed counts, which scales the background too, and rietx fits the
    background in the observed space where the spectrum's effect on it is
    already in the coefficients.
    """
    st = silicon()
    plain, with_spec = bank(), bank(spectrum=_spectrum())
    pattern = blank_pattern()
    m0 = compile_tof_model(st, plain, pattern)
    m1 = compile_tof_model(st, with_spec, pattern)

    v0, v1 = values_of(st, plain), values_of(st, with_spec)
    factor = np.asarray(incident_spectrum(1, ELEVEN, m1.tof))
    assert factor.shape == m1.tof.shape and factor.min() > 0.0
    # it really does vary across the bank — a control that could not fail
    # otherwise, since a constant factor is also "per channel"
    assert factor.max() / factor.min() > 100.0

    assert np.allclose(np.asarray(m1.bragg_component(v1)),
                       factor * np.asarray(m0.bragg_component(v0)))
    assert np.array_equal(np.asarray(m1.background(v1)),
                          np.asarray(m0.background(v0)))
    # and y_calc is the sum of the two, i.e. nothing applies it twice
    assert np.allclose(np.asarray(m1.evaluate(v1)),
                       np.asarray(m1.background(v1))
                       + factor * np.asarray(m0.bragg_component(v0)))


def test_a_bank_with_no_spectrum_is_bit_identical_to_the_build_before_this_one():
    """``ITYP 0`` multiplies by nothing, not by ones.

    ``np.array_equal`` rather than ``allclose``: multiplying by an array of
    exact 1.0 would also pass a tolerance test, and the claim is that a bank
    whose reduction already normalised takes the *same* arithmetic it took
    before — which is what makes ISIS GEM, SNS NOMAD and POWGEN unaffected.
    """
    st = silicon()
    ins = bank(spectrum=IncidentSpectrum())
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    assert m.spectrum_itype == 0 and m.incident_spectrum(v) is None
    plain = compile_tof_model(st, bank(), blank_pattern())
    assert np.array_equal(np.asarray(m.evaluate(v)),
                          np.asarray(plain.evaluate(values_of(st, bank()))))


def test_the_coefficients_reach_the_parameter_table_numbered_from_one():
    st, ins = silicon(), bank(spectrum=_spectrum())
    table = ParameterTable(st, ins)
    by_path = {e.path: e for e in table.entries}
    paths = [f"instrument.source.incident_spectrum.p{i}" for i in range(1, 12)]
    assert all(p in by_path for p in paths)
    assert [by_path[p].value for p in paths] == ELEVEN
    assert not any(by_path[p].vary for p in paths)
    # p12 does not exist: type 1 uses eleven
    assert "instrument.source.incident_spectrum.p12" not in by_path

    # the half-wired-parameter check: refined values and esds come back to the
    # container the next stage's recompile will read
    moved = {p: by_path[p].value + 1.0 for p in paths}
    for p, v in moved.items():
        by_path[p].value = v
    esds = {p: 1e-3 * (i + 1) for i, p in enumerate(paths)}
    table.apply_to_models(st, ins, esds)
    stored = ins.source.incident_spectrum.coefficients
    assert [c.value for c in stored] == [moved[p] for p in paths]
    assert [c.stderr for c in stored] == [esds[p] for p in paths]
    again = {e.path: e.value for e in ParameterTable(st, ins).entries}
    assert [again[p] for p in paths] == [moved[p] for p in paths]


def test_a_bank_declaring_no_spectrum_adds_no_rows_at_all():
    """``ITYP 0`` is the default, so a table over a hand-built bank is the one
    it was before this feature — not the one it was plus eleven held rows."""
    st = silicon()
    paths = {e.path for e in ParameterTable(st, bank()).entries}
    assert not any(".incident_spectrum." in p for p in paths)


def test_freeing_the_coefficients_moves_the_pattern_through_the_table():
    """The coefficients are read from ``values`` on every evaluation, so a
    stage that frees one moves it — the property that lets a standard check the
    file's own calibration."""
    st, ins = silicon(), bank(spectrum=_spectrum())
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    base = np.asarray(m.bragg_component(v))
    v2 = dict(v, **{"instrument.source.incident_spectrum.p2": ELEVEN[1] * 2.0})
    assert not np.allclose(np.asarray(m.bragg_component(v2)), base)


# ------------------------------------------------ absorption: µ(λ), the 1/v law
def test_mu_is_affine_in_lambda_and_only_the_absorbing_part_moves():
    """The 1/v law is the whole difference from the X-ray case (WP-1132).

    σ_abs scales as λ and σ_coh + σ_inc do not, so µ(λ) is exactly a straight
    line whose *intercept* is the scattering and whose *slope* is the
    absorption.  Asserted on both halves separately, because a version that got
    the split backwards would still be a straight line.
    """
    counts, volume = {"Si": 8.0}, 5.4311946 ** 3
    a, b = neutron_attenuation_terms(counts, volume)
    row = properties("Si")
    assert b == pytest.approx(8.0 * (row["xs_coh_barn"] + row["xs_inc_barn"])
                              / volume, rel=1e-14)
    assert a == pytest.approx(8.0 * row["xs_abs_barn"]
                              / (THERMAL_WAVELENGTH * volume), rel=1e-14)
    # and the function through it is the line those two describe
    for lam in (0.5, 1.798, 4.0):
        assert neutron_linear_attenuation(counts, volume, lam) == pytest.approx(
            a * lam + b, rel=1e-14)
    # at the tabulation wavelength the absorbing part is exactly its own σ_abs
    assert (neutron_linear_attenuation(counts, volume, THERMAL_WAVELENGTH) - b
            ) == pytest.approx(8.0 * row["xs_abs_barn"] / volume, rel=1e-12)


def test_mu_keeps_the_isotope_where_an_xray_composition_would_not():
    """b and σ depend on the nucleus, so ²H is not H — ``neutron.py``'s own rule.

    The X-ray composition machinery (``optimize.qpa.phase_zmv``) reduces every
    species to an element, which is right for a form factor and wrong here by a
    factor of forty in the incoherent cross-section.  This is why the TOF
    absorption path builds its own species counts instead of reusing that one.
    """
    volume = 100.0
    light = neutron_linear_attenuation({"H": 2.0}, volume, 1.798)
    heavy = neutron_linear_attenuation({"2H": 2.0}, volume, 1.798)
    assert light > 10.0 * heavy
    assert properties("H")["xs_inc_barn"] > 35.0 * properties("2H")["xs_inc_barn"]
    # the ratio, quoted so a table change is visible rather than absorbed by a
    # loose bound: 80.26 barn against 2.05, a factor of 39
    assert properties("H")["xs_inc_barn"] == pytest.approx(80.26, abs=0.01)
    assert properties("2H")["xs_inc_barn"] == pytest.approx(2.05, abs=0.01)


def test_a_negative_or_zero_cell_volume_is_refused():
    with pytest.raises(ValueError, match="volume must be positive"):
        neutron_attenuation_terms({"Si": 8.0}, 0.0)


# ---------------------------------------- absorption: the model applies it
def test_absorption_is_per_reflection_at_that_reflections_own_wavelength():
    """The claim, in three parts, each of which can fail on its own.

    µR rises with λ (the 1/v law, seen through the model); the transmission
    factor is the constant-wavelength :func:`cylinder_absorption` evaluated at
    the *bank's* angle and that µR, to the last bit; and the intensity
    ``phase_peaks`` reports carries it.
    """
    st = silicon()
    ins = bank(capillary_radius_mm=3.0)
    m = compile_tof_model(st, ins, blank_pattern())
    assert m.absorption_terms is not None
    a, b = m.absorption_terms

    d = np.array([3.135, 1.92, 1.357, 1.045])
    lam = np.asarray(m.wavelength_of(d))
    assert np.all(np.diff(lam) < 0.0)                      # λ falls with d
    mu_r = a * lam + b
    assert np.all(np.diff(mu_r) < 0.0) and mu_r.min() > 0.0
    assert np.array_equal(np.asarray(m.absorption(d)),
                          np.asarray(cylinder_absorption(90.0, mu_r)))

    # and it reaches the reported intensity: the same model with no radius is
    # the same numbers divided by exactly this factor
    plain = compile_tof_model(st, bank(), blank_pattern())
    v = values_of(st, ins)
    i_with = np.asarray(m.phase_peaks(0, v)[0][-1])
    i_without = np.asarray(plain.phase_peaks(0, values_of(st, bank()))[0][-1])
    d_all = np.asarray(m.phase_peaks(0, v)[0][0])
    assert i_with.shape == i_without.shape and len(d_all) > 5
    assert np.all(i_with < i_without)
    assert np.allclose(i_with / i_without,
                       np.asarray(m.absorption(
                           np.asarray(plain.phases[0].reflections.d_spacing)
                           if hasattr(plain.phases[0].reflections, "d_spacing")
                           else _d_of(plain, 0, values_of(st, bank())))),
                       rtol=1e-12)


def _d_of(model, ip, values):
    from rietx.crystallography.lattice import d_spacings
    cell = tuple(values[f"phases.{ip}.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    return d_spacings(model.phases[ip].reflections.hkl, *cell)


def test_no_capillary_radius_means_no_correction_at_all():
    """"Nobody asked" is the off state, and it is bit-identical.

    The same gate the constant-wavelength path uses: ``mu_r`` is estimated only
    when a specimen dimension was declared.  A bank with no radius must be the
    arithmetic it was before this commit, not that arithmetic times an array of
    numbers very close to one.
    """
    st = silicon()
    m = compile_tof_model(st, bank(), blank_pattern())
    assert m.absorption_terms is None
    assert m.absorption(np.array([2.0, 1.0])) is None


def test_a_scalar_mu_r_is_refused_because_a_bank_has_many_wavelengths():
    st = silicon()
    with pytest.raises(ValueError, match="absorption \\*\\*at one wavelength\\*\\*|at one wavelength"):
        compile_tof_model(st, bank(mu_r=0.4), blank_pattern())
    # mu_t never reaches the compiled model through a capillary: Geometry's own
    # validator refuses a flat-specimen quantity on a cylinder first, and that
    # is the right door for it.  The compile refusal below is for the geometry
    # where mu_t *is* legal.
    with pytest.raises(ValueError, match="flat-specimen quantity"):
        ins = bank()
        ins.geometry.mu_t = 0.3
    flat = bank()
    flat.geometry = rx.Geometry(kind="flat_plate_transmission",
                                thickness_mm=0.5, mu_t=0.3)
    with pytest.raises(ValueError, match="flat-specimen absorption"):
        compile_tof_model(st, flat, blank_pattern())


def test_the_reported_mu_r_range_is_a_pair_and_rises_with_wavelength():
    """The statement a constant-wavelength µR cannot make.

    The Rouse fit's domain is 0 ≤ µR ≤ 1 and the correction is an
    extrapolation past it — but on a bank that can be true at one end and
    false at the other, because µ rises with λ.  So the model carries both
    ends, and it is a *report*, not a fence: the constant-wavelength path
    warns at the same threshold rather than refusing, and a Gd or Cd specimen
    really is that absorbing.
    """
    st = silicon()
    m = compile_tof_model(st, bank(capillary_radius_mm=3.0), blank_pattern())
    lo, hi = m.mu_r_range
    assert 0.0 < lo < hi < 0.1                       # Si is barely absorbing
    # the invariant worth pinning is not how the two ends were derived but what
    # they promise: every reflection the model will evaluate has its µR inside
    # them.  A range taken from the wrong d limits would break this and a range
    # recomputed the same wrong way in the test would not.
    a, b = m.absorption_terms
    d = _d_of(m, 0, values_of(st, bank(capillary_radius_mm=3.0)))
    mu_r = a * np.asarray(m.wavelength_of(d)) + b
    assert mu_r.min() >= lo and mu_r.max() <= hi

    # scale the specimen up until the long-wavelength end leaves the domain
    # while the short-wavelength end is still inside it — the case the pair
    # exists for, and one a single number cannot express
    big = compile_tof_model(st, bank(capillary_radius_mm=135.0), blank_pattern())
    lo2, hi2 = big.mu_r_range
    assert lo2 < CYLINDER_MU_R_MAX < hi2
    assert big.absorption_terms is not None           # still compiles



def test_a_species_the_neutron_table_does_not_carry_is_refused_by_name():
    st = silicon()
    st.phases[0].atoms[0].species = "Xx"
    with pytest.raises(Exception):
        compile_tof_model(st, bank(capillary_radius_mm=3.0), blank_pattern())


# ------------------------------------------- absorption: the negative control
def cobalt(biso: float = 0.5) -> Structure:
    """fcc Co — a real, strongly absorbing, **non-resonant** neutron scatterer.

    σ_abs = 37.18 barn at 1.798 Å against Si's 0.171, so a capillary of it
    absorbs where Si does not, and it is not in
    :data:`~rietx.crystallography.neutron.RESONANT_ABSORBERS`, where the
    thermal cross-section would be incomplete rather than merely large and the
    whole comparison would rest on a number the table cannot give.
    """
    a = 3.5447
    cell = Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0))
    return Structure(phases=[Phase(
        name="Co", space_group="F m -3 m", cell=cell, scale=P(value=1.0),
        atoms=[Atom(label="Co", species="Co", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.0), biso=P(value=biso))])])


def _generated(structure, instrument, seed: int) -> PatternData:
    """A pattern generated *from* the compiled model, with Poisson noise.

    The scale and the flat background are set here rather than on the fixture
    so the counting statistics are a property of this arm: a control that
    compares two Biso values needs their esds to be small against the effect it
    is looking for, and a pattern of a few counts a channel has esds that
    swallow it.
    """
    grid = np.arange(TOF_LO, TOF_HI + 0.5 * TOF_STEP, TOF_STEP)
    blank = PatternData(tof=grid.tolist(), intensity=[1.0] * len(grid))
    structure.phases[0].scale.value = 2.0e4
    instrument.background.coefficients[0].value = 200.0
    model = compile_tof_model(structure, instrument, blank)
    table = ParameterTable(structure, instrument)
    y = np.asarray(model.evaluate(table.decode(table.x0())), dtype=np.float64)
    rng = np.random.default_rng(seed)
    return PatternData(tof=grid.tolist(),
                       intensity=rng.poisson(np.maximum(y, 0.0)).astype(
                           np.float64).tolist())


def _refit(structure, instrument, data):
    ref = rx.Refinement(structure, instrument, history=False)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.c*"]),
        rx.Stage("late", ["phases.*.cell.a", "phases.*.atoms.*.biso"]),
    ])
    plan.intermediate_ftol = None
    return ref.fit(data, plan=plan)


def test_leaving_out_a_real_absorber_biases_biso_and_costs_rwp():
    """The negative control the correction has to earn its place against.

    A pattern is **generated** from a strongly absorbing capillary of Co with
    the correction on, then refined twice: once with the same radius declared,
    once with it cleared.  The second is the model this arm had before this
    commit, and it must be visibly worse *and* wrong in the same direction
    every time — the transmission factor suppresses the long-d end (long λ on a
    fixed-angle bank) while the Debye-Waller factor suppresses the short-d end,
    so a fit with no absorption can only compensate by moving Biso, and it
    moves it **down**.

    Generated from the model rather than measured, so the answer is known: with
    the correction in place the fit must return the Biso it was generated with.
    """
    absorbing = bank(capillary_radius_mm=CO_RADIUS_MM)
    generated_biso = 0.5
    data = _generated(cobalt(generated_biso), absorbing, seed=20260906)

    span = compile_tof_model(cobalt(), bank(capillary_radius_mm=CO_RADIUS_MM),
                             blank_pattern()).mu_r_range
    # the arm is only a control if the correction is actually large here, and
    # only a *time-of-flight* control if it is large by a different amount at
    # the two ends of the bank
    assert 0.1 < span[0] and span[1] > 4.0 * span[0]

    with_it = _refit(cobalt(1.0), bank(capillary_radius_mm=CO_RADIUS_MM), data)
    without = _refit(cobalt(1.0), bank(), data)

    b_with = {p.path: p for p in with_it.parameters}["phases.0.atoms.0.biso"]
    b_without = {p.path: p for p in without.parameters}["phases.0.atoms.0.biso"]

    # recovered where the correction is in the model, biased low where it is not
    assert abs(b_with.value - generated_biso) < 3.0 * b_with.stderr
    assert b_without.value < generated_biso - 0.1
    assert without.statistics.rwp > 1.2 * with_it.statistics.rwp


def test_the_correction_is_reported_when_it_runs_and_absent_when_it_does_not():
    """A correction applied and not reported is the worst of the three states.

    ``AbsorptionCorrection`` carries one µR at one wavelength and a bank has
    neither, so ``result.absorption`` stays ``None`` here and the diagnostic is
    the only thing that says the correction ran.  Its absence is equally a
    statement: no radius declared, no correction.
    """
    absorbing = bank(capillary_radius_mm=CO_RADIUS_MM)
    data = _generated(cobalt(0.5), absorbing, seed=20260906)

    on = _refit(cobalt(1.0), bank(capillary_radius_mm=CO_RADIUS_MM), data)
    codes = [d.code for d in on.diagnostics]
    assert "SPECIMEN_ABSORPTION_TOF" in codes
    said = next(d for d in on.diagnostics if d.code == "SPECIMEN_ABSORPTION_TOF")
    assert said.level == "info" and "per reflection" in said.message
    assert on.absorption is None

    off = _refit(cobalt(1.0), bank(), data)
    assert "SPECIMEN_ABSORPTION_TOF" not in [d.code for d in off.diagnostics]


def test_a_bank_outside_the_rouse_domain_warns_at_the_long_wavelength_end():
    huge = bank(capillary_radius_mm=8.0)
    data = _generated(cobalt(0.5), huge, seed=20260906)
    res = _refit(cobalt(0.5), bank(capillary_radius_mm=8.0), data)
    warned = [d for d in res.diagnostics
              if d.code == "ABSORPTION_MU_R_OUT_OF_RANGE"]
    assert len(warned) == 1 and warned[0].level == "warning"
    assert "long-wavelength end" in warned[0].message
    # and the small capillary of the same specimen does not warn — the control
    # that stops this passing on a warning that always fires
    small = bank(capillary_radius_mm=CO_RADIUS_MM)
    quiet = _refit(cobalt(0.5), bank(capillary_radius_mm=CO_RADIUS_MM),
                   _generated(cobalt(0.5), small, 20260906))
    assert not [d for d in quiet.diagnostics
                if d.code == "ABSORPTION_MU_R_OUT_OF_RANGE"]


# ---------------------------------------------------- extinction per reflection
#: The extinction coefficient the arm below uses.  Larger than the 0.004-2.0 of
#: the constant-wavelength tests by four orders, and that is a **unit**
#: statement rather than a physical one: Sabine's x carries |F|², and a neutron
#: |F|² is in fm² where an X-ray one is in electrons², so the same physical
#: amount of extinction is a different number in ``phases.*.extinction``.  At
#: this value E runs 0.60 to 1.00 across the bank, which is what makes the
#: control below able to fail.
TOF_EXT = 100.0


def _f2_and_volume(model, values):
    """|F|² and the cell volume the model itself is using, for an oracle."""
    from rietx.crystallography.lattice import cell_volume
    from rietx.crystallography.structure_factor import structure_factors_squared

    cell = tuple(values[f"phases.0.cell.{k}"]
                 for k in ("a", "b", "c", "alpha", "beta", "gamma"))
    cp = model.phases[0]
    d = _d_of(model, 0, values)
    f2 = structure_factors_squared(cp.reflections.hkl, d, cp.sites,
                                   *model._site_values(0, values, cell))
    return np.asarray(f2), float(cell_volume(*cell)), np.asarray(d)


def test_extinction_is_the_constant_wavelength_function_at_each_reflections_lambda():
    """No new physics, and this is the assertion that says so.

    ``sabine_extinction`` is called with an **array** of wavelengths where the
    constant-wavelength model passes one scalar per emission line, because λ
    enters only as (λ/V)² and that expression is arithmetic.  So the
    per-reflection factor must equal the constant-wavelength function evaluated
    one reflection at a time at the same λ — asserted with ``array_equal``,
    because "the same function" is a stronger claim than "within a tolerance".
    """
    st = silicon()
    st.phases[0].extinction = TOF_EXT
    ins = bank()
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    f2, volume, d = _f2_and_volume(m, v)
    lam = np.asarray(m.wavelength_of(d))

    batched = np.asarray(sabine_extinction(f2, lam, volume, 90.0, TOF_EXT))
    one_at_a_time = np.array([
        float(sabine_extinction(np.array([f2[k]]), float(lam[k]), volume,
                                90.0, TOF_EXT)[0])
        for k in range(len(f2))])
    assert np.array_equal(batched, one_at_a_time)

    # and it reaches the reported intensity: the ratio to the ext = 0 model is
    # exactly this factor
    plain = compile_tof_model(silicon(), bank(), blank_pattern())
    i_ext = np.asarray(m.phase_peaks(0, v)[0][-1])
    i_none = np.asarray(plain.phase_peaks(0, values_of(silicon(), bank()))[0][-1])
    assert np.allclose(i_ext / i_none, batched, rtol=1e-12)
    assert batched.min() < 0.7 and batched.max() > 0.99   # a real λ trend


def test_the_extinction_deficit_goes_as_lambda_squared_and_not_lambda_to_the_fourth():
    """The trend, measured, because "λ⁴-ish" is the folklore.

    Sabine's variable is x = ext·|F|²·(λ/V)²·X_pol, so in the weak-extinction
    limit 1 − E ≈ x/2 and the deficit goes as **λ²** at fixed |F|².  Measured
    here as the log-log slope of (1 − E)/|F|² against λ over a whole
    reflection list: **1.99**, not 4.  The λ⁴ that a reader is remembering is
    the *Lorentz* factor on this arm (d⁴ sin θ_bank), which multiplies the
    intensity beside the extinction factor and is a different thing.
    """
    st = silicon()
    st.phases[0].extinction = 1.0
    ins = bank()
    m = compile_tof_model(st, ins, blank_pattern())
    v = values_of(st, ins)
    f2, volume, d = _f2_and_volume(m, v)
    lam = np.asarray(m.wavelength_of(d))
    deficit = 1.0 - np.asarray(sabine_extinction(f2, lam, volume, 90.0, 1.0))
    ok = (deficit > 1e-14) & (f2 > 1e-6)
    assert ok.sum() > 20
    slope = np.polyfit(np.log(lam[ok]), np.log(deficit[ok] / f2[ok]), 1)[0]
    assert slope == pytest.approx(2.0, abs=0.05)


def test_extinction_is_refinable_on_a_bank_and_zero_is_skipped_not_multiplied():
    """Two halves of one contract.

    It is refinable — T-1b force-fixed it here because ``compile_tof_model``
    refused a declared one, and that refusal is gone — and the off state is a
    **structural skip**, so a phase that cannot move it off zero this stage
    takes the arithmetic it took before, not that arithmetic times ones.
    """
    st, ins = silicon(), bank()
    st.phases[0].extinction = 0.0  # declared: opt-in since WP-1944
    by_path = {e.path: e for e in ParameterTable(st, ins).entries}
    row = by_path["phases.0.extinction"]
    assert not row.locked, "extinction is refinable on a bank since T-3"

    assert compile_tof_model(st, ins, blank_pattern()).phases[0].skip_extinction
    # a stage that *can* move it off zero compiles the chain in, even though
    # the stored value is still exactly zero — structural, from what can change
    moving = compile_tof_model(st, ins, blank_pattern(),
                               moving_paths={"phases.0.extinction"})
    assert not moving.phases[0].skip_extinction
    # and with the chain in but the value still zero, the pattern is unchanged
    v = values_of(st, ins)
    assert np.array_equal(
        np.asarray(moving.evaluate(v)),
        np.asarray(compile_tof_model(st, ins, blank_pattern()).evaluate(v)))


def test_leaving_out_a_real_extinction_biases_the_strongest_reflections():
    """The negative control: generated with it on, refined with it off.

    Extinction takes intensity out of the strong, long-wavelength reflections
    and leaves the weak ones alone, which is a shape neither the scale nor
    Biso reproduces — so a fit with the coefficient held at zero pays for it in
    Rwp and in a displacement parameter, in that order.
    """
    ext_bank = bank()
    generated_biso = 0.5
    st_gen = silicon(generated_biso)
    st_gen.phases[0].extinction = TOF_EXT
    data = _generated(st_gen, ext_bank, seed=20260906)

    def start(ext):
        s = silicon(1.0)
        s.phases[0].extinction = ext
        s.phases[0].scale.value = 2.0e4
        return s

    def fit(structure, free_ext):
        ins = bank()
        ins.background.coefficients[0].value = 200.0
        ref = rx.Refinement(structure, ins, history=False)
        late = ["phases.*.cell.a", "phases.*.atoms.*.biso"]
        stages = [rx.Stage("scale_bkg",
                           ["phases.*.scale", "instrument.background.c*"]),
                  rx.Stage("late", late + (["phases.*.extinction"]
                                           if free_ext else []))]
        plan = rx.RefinementPlan(stages=stages)
        plan.intermediate_ftol = None
        return ref.fit(data, plan=plan)

    with_it = fit(start(TOF_EXT), free_ext=True)
    without = fit(start(0.0), free_ext=False)

    b_with = {p.path: p for p in with_it.parameters}["phases.0.atoms.0.biso"]
    b_without = {p.path: p for p in without.parameters}["phases.0.atoms.0.biso"]
    assert abs(b_with.value - generated_biso) < 5.0 * b_with.stderr
    assert abs(b_without.value - generated_biso) > 10.0 * b_without.stderr
    assert without.statistics.rwp > 1.5 * with_it.statistics.rwp
