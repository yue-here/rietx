"""Constant-wavelength neutron refinement: the source, the amplitude, the fit.

The tests that matter are the ones that would pass for an X-ray source too if
the radiation were being ignored. So each one below turns on something that is
*different* about neutrons — a Q-independent amplitude, a negative one, K = 1,
an absent dispersion channel — rather than merely checking that a fit runs.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.lattice import d_spacings
from rietx.crystallography.scattering import f0
from rietx.crystallography.structure_factor import (
    compile_phase_sites,
    structure_factors_squared,
)
from rietx.crystallography.symmetry import generate_reflections
from rietx.model.corrections import lorentz_polarization
from rietx.model.profiles.caglioti import _MIN_GAMMA_G2
from rietx.schemas.instrument import (
    TCHZ_BOUNDS,
    TCHZ_CEILING_DEG,
    NeutronSource,
    ProfileTCHZ,
)

CORUNDUM_CELL = (4.758877, 4.758877, 12.992880, 90.0, 90.0, 120.0)


def corundum() -> rx.Phase:
    """Al2O3, the NIST SRM 1976a standard: two sites, both special positions."""
    P = rx.Parameter
    a, _, c, *_ = CORUNDUM_CELL
    return rx.Phase(
        name="Al2O3", space_group="R-3c:H",
        cell=rx.Cell(a=P(value=a), b=P(value=a), c=P(value=c),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=120.0)),
        atoms=[
            rx.Atom(label="Al", species="Al", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.35216), biso=P(value=0.3)),
            rx.Atom(label="O", species="O", x=P(value=0.30642), y=P(value=0.0),
                    z=P(value=0.25), biso=P(value=0.3)),
        ])


# --------------------------------------------------------------- the source ---
def test_neutron_source_pins_the_polarisation_term():
    """K = 1 is the whole reason no new correction code is needed.

    Lp = [K + (1 - K)cos^2 2th]/(sin^2 th cos th) collapses to the bare Lorentz
    factor at K = 1, and that factor is geometry, not radiation.
    """
    source = NeutronSource(wavelength=2.0780)
    assert source.polarization.value == 1.0
    assert not source.polarization.vary

    tt = np.array([10.0, 45.0, 90.0, 140.0])
    bare = 1.0 / (np.sin(np.radians(tt / 2)) ** 2 * np.cos(np.radians(tt / 2)))
    assert lorentz_polarization(tt, 1.0) == pytest.approx(bare, rel=1e-15)
    # and the term is not vacuous: an unpolarised X-ray beam differs materially
    assert not np.allclose(lorentz_polarization(tt, 0.5), bare, rtol=1e-3)


def test_neutron_source_has_no_dispersion_channel():
    source = NeutronSource(wavelength=2.0780)
    assert source.dispersion is None
    assert source.primary_wavelength == pytest.approx(2.0780)
    assert len(source.lines) == 1          # one line, weight structurally 1
    assert not source.lines[0].weight.vary


def test_instrument_union_discriminates_on_kind():
    neutron = rx.Instrument.constant_wavelength_neutron(2.0780)
    xray = rx.Instrument.debye_scherrer(0.4139)
    assert neutron.source.kind == "neutron_cw"
    assert xray.source.kind == "xray_cw"
    # both round-trip through JSON under the discriminated union
    for inst in (neutron, xray):
        again = rx.Instrument.model_validate_json(inst.model_dump_json())
        assert again.source.kind == inst.source.kind


def test_profile_seed_sets_the_gaussian_constant_term_only():
    """Renamed from ``..._sets_both_width_terms``, which pinned the defect.

    It asserted ``w = (fwhm/2)**2`` and ``x = fwhm`` — the seed issue #124 is
    about — so it would have gone red on the fix and green on the bug. The
    behaviour it should have pinned is the promise the argument makes, and
    that is asserted as a *width* two tests below rather than as coefficients
    here.
    """
    inst = rx.Instrument.constant_wavelength_neutron(2.0780, fwhm_deg=0.4)
    default = rx.Instrument.constant_wavelength_neutron(2.0780)
    assert inst.profile.w.value == pytest.approx(0.4 ** 2)
    assert inst.profile.x.value == default.profile.x.value


def test_a_wide_fwhm_deg_builds_under_the_axis_ceiling():
    """The 2026-09-11 fence refused a `fwhm_deg` seeding `w` past its upper
    bound, 8 deg² in the coarse box.  The chosen ceilings went on 2026-10-21
    (WP-2002, the fifth round's Q5), and the fence with them: 3.0° seeds
    w = 9.0 exactly.  The ceiling left is the 2θ axis (the sixth round's Q7)."""
    inst = rx.Instrument.constant_wavelength_neutron(2.0780, fwhm_deg=3.0)
    assert inst.profile.w.value == pytest.approx(3.0 ** 2)
    assert inst.profile.w.max == TCHZ_CEILING_DEG ** 2


def test_a_long_wavelength_line_wider_than_one_degree_builds():
    """Issue #276: D1B at 2.52 Å has a 1.10 deg strongest line, which the
    X-ray-sized box (w <= 1 deg²) made unreachable from this preset."""
    inst = rx.Instrument.constant_wavelength_neutron(2.52, fwhm_deg=1.2)
    assert inst.profile.w.value == pytest.approx(1.44)
    for name, (lo, hi) in TCHZ_BOUNDS.items():
        param = getattr(inst.profile, name)
        assert (param.min, param.max) == (lo, hi)


def test_a_bare_wide_width_refuses_and_names_both_escapes():
    """WP-1312's ruling: a bare width is refused by name, and the message
    names both ways to build one."""
    for kwargs in (dict(u=1.576), dict(u=1.576, v=-0.501, w=0.475)):
        with pytest.raises(ValueError) as exc:
            ProfileTCHZ(**kwargs)
        message = str(exc.value)
        assert "u=1.576" in message
        assert "ProfileTCHZ.coarse" in message
        assert "Parameter(value, min, max)" in message


def test_the_explicit_parameter_escape_builds_a_wide_width():
    profile = ProfileTCHZ(u=rx.Parameter(value=1.576, min=-0.5, max=8.0,
                                         unit="deg^2"))
    assert (profile.u.value, profile.u.max) == (1.576, 8.0)


def test_a_published_d1b_caglioti_model_constructs_through_coarse():
    """Issue #276: the APDW Co3O4 D1B FullProf model, whose V = -0.501 sat
    under the old X-ray floor, built from bare values in the one box every
    preset builds since the floors went (WP-2002, ruled 2026-10-23)."""
    profile = ProfileTCHZ.coarse(u=1.576, v=-0.501, w=0.475)
    assert (profile.u.value, profile.v.value, profile.w.value) == (
        1.576, -0.501, 0.475)
    for name, (lo, hi) in TCHZ_BOUNDS.items():
        param = getattr(profile, name)
        assert (param.min, param.max) == (lo, hi)
    # round-trips with its box
    again = ProfileTCHZ.model_validate_json(profile.model_dump_json())
    assert again == profile
    # U has no chosen floor or ceiling; past the 2θ axis it still refuses,
    # by the Parameter's own message
    assert ProfileTCHZ.coarse(u=-0.6).u.value == -0.6
    assert ProfileTCHZ.coarse(u=9.0).u.value == 9.0
    with pytest.raises(ValueError, match="outside bounds"):
        ProfileTCHZ.coarse(u=-TCHZ_CEILING_DEG ** 2 - 1.0)
    # X keeps its floor: at θ → 0 it is the whole Lorentzian width
    with pytest.raises(ValueError, match="outside bounds"):
        ProfileTCHZ.coarse(x=-0.01)


def test_a_bare_width_inside_the_default_box_refuses_by_name():
    """As on main, a bare number never builds a width; the refusal now names
    the width, the value, the box and both escapes, not pydantic's type."""
    with pytest.raises(ValueError) as exc:
        ProfileTCHZ(u=0.5)
    message = str(exc.value)
    assert "u=0.5" in message
    lo, hi = TCHZ_BOUNDS["u"]
    assert f"[{lo}, {hi}]" in message
    assert "ProfileTCHZ.coarse" in message
    assert "Parameter(value, min, max)" in message


@pytest.mark.parametrize("build", [
    lambda: rx.Instrument.debye_scherrer(0.4139),
    lambda: rx.Instrument.bragg_brentano(),
    lambda: rx.Instrument.flat_plate_transmission(),
])
def test_the_x_ray_profile_box_is_unchanged(build):
    """Every X-ray instrument builds the profile literal for literal.  W's
    floor is the Γ_G² clamp since WP-1938 (D7).  The chosen ceilings went on
    2026-10-21 (WP-2002, the fifth round's Q5); the ceiling left is the 2θ
    axis, 180° and 180² deg² (the sixth round's Q7).  The chosen U, V and Y
    floors went on 2026-10-23, each now the ceiling's mirror image."""
    sq, deg = 180.0 ** 2, 180.0
    expected = {
        "u": dict(value=0.0, min=-sq, max=sq, unit="deg^2"),
        "v": dict(value=0.0, min=-sq, max=sq, unit="deg^2"),
        "w": dict(value=1e-3, min=_MIN_GAMMA_G2, max=sq, unit="deg^2",
                  transform="softplus"),
        "x": dict(value=1e-3, min=0.0, max=deg, unit="deg",
                  transform="softplus"),
        "y": dict(value=0.0, min=-deg, max=deg, unit="deg"),
    }
    profile = build().profile
    for name, kw in expected.items():
        assert getattr(profile, name) == rx.Parameter(**kw)


def test_the_explicit_parameter_escape_hatch_round_trips_with_its_own_bound():
    """Yue's own check: the refusal names an escape hatch. Set
    ``instrument.profile.w`` explicitly, with its own (wider) bounds, to
    declare a genuinely coarser instrument. That bound must survive a JSON
    round trip rather than reverting to the schema default of 1.0."""
    inst = rx.Instrument.constant_wavelength_neutron(2.0780)
    inst.profile.w = rx.Parameter(value=4.0, min=0.0, max=9.0, unit="deg^2",
                                  transform="softplus")
    dumped = inst.model_dump(mode="json")
    again = rx.Instrument(**dumped)
    assert again.profile.w.value == pytest.approx(4.0)
    assert again.profile.w.max == pytest.approx(9.0)


# ------------------------------------------------------------ the amplitude ---
def test_scattering_length_is_frozen_on_the_phase():
    sites = compile_phase_sites(corundum(), neutron=True)
    assert sites.b_coh is not None
    assert sites.b_coh == pytest.approx([3.449, 5.803], abs=5e-4)
    assert compile_phase_sites(corundum()).b_coh is None       # X-ray default


def test_neutron_amplitude_is_q_independent_and_xray_is_not():
    """The discriminating property, tested directly on the amplitudes.

    An X-ray form factor falls off with Q because the electron cloud has
    spatial extent; a nucleus is a point scatterer, so b does not.
    """
    stol = np.linspace(0.05, 0.45, 12)             # s = sin(theta)/lambda
    f_xray = f0("Al", stol)
    assert f_xray[0] > 1.5 * f_xray[-1]            # real falloff across the range
    # b is one number; the module returns it without an s argument at all
    from rietx.crystallography.neutron import b_coh
    assert b_coh("Al") == pytest.approx(3.449, abs=5e-4)


def test_negative_scattering_length_still_gives_positive_intensity():
    """Vanadium: b < 0, and |F|^2 must not go with it."""
    P = rx.Parameter
    cell = (3.024, 3.024, 3.024, 90.0, 90.0, 90.0)
    v = rx.Phase(
        name="V", space_group="Im-3m",
        cell=rx.Cell(a=P(value=cell[0]), b=P(value=cell[1]), c=P(value=cell[2]),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[rx.Atom(label="V", species="V", x=P(value=0.0), y=P(value=0.0),
                       z=P(value=0.0), biso=P(value=0.5))])
    sites = compile_phase_sites(v, neutron=True)
    assert sites.b_coh[0] < 0.0
    refl = generate_reflections("Im-3m", cell, 2.0780, 120.0, 5.0)
    hkl = np.asarray(refl.hkl)
    f2 = structure_factors_squared(
        hkl, d_spacings(hkl, *cell), sites,
        np.zeros((1, 3)), np.array([1.0]), np.array([0.5]))
    assert (f2 >= 0.0).all()
    assert f2.max() > 0.0


def test_neutron_and_anomalous_dispersion_are_mutually_exclusive():
    """Different radiations, different units (fm against electrons)."""
    with pytest.raises(ValueError, match="anomalous dispersion"):
        compile_phase_sites(corundum(), f_anom={"Al": 0j, "O": 0j}, neutron=True)


def test_unknown_species_refuses_at_compile_rather_than_returning_zero():
    P = rx.Parameter
    bogus = rx.Phase(
        name="X", space_group="P1",
        cell=rx.Cell(a=P(value=5.0), b=P(value=5.0), c=P(value=5.0),
                     alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0)),
        atoms=[rx.Atom(label="Q", species="Xx", x=P(value=0.0), y=P(value=0.0),
                       z=P(value=0.0))])
    with pytest.raises(KeyError, match="Xx"):
        compile_phase_sites(bogus, neutron=True)


# -------------------------------------------------------------- the refusals ---
def test_a_dispersion_channel_cannot_be_attached_to_a_neutron_source():
    """Structural, via ``extra="forbid"`` — there is no field to set."""
    from pydantic import ValidationError  # noqa: PLC0415
    with pytest.raises(ValidationError, match="dispersion"):
        NeutronSource(wavelength=2.0780, dispersion=None)
    with pytest.raises(ValidationError, match="lines"):
        NeutronSource(wavelength=2.0780, lines=[])


def test_polarization_is_force_fixed_rather_than_merely_unfree():
    """A free K would not be a dead column, which is what makes this matter.

    Lp(2θ, K) does move the pattern, so a solver handed a free K on a neutron
    fit would buy Rwp by refining a term the physics already fixes. WP-1073's
    rule: force-fixed, so ``set_vary`` cannot reach it.
    """
    structure = rx.Structure(phases=[corundum()])
    neutron = rx.Refinement(structure,
                            rx.Instrument.constant_wavelength_neutron(2.0780))
    row = next(r for r in neutron.parameters()
               if r.path == "instrument.polarization")
    assert row.value == 1.0
    assert not row.refinable
    neutron.set_vary(["instrument.polarization"], True)
    row = next(r for r in neutron.parameters()
               if r.path == "instrument.polarization")
    assert not row.refinable, "set_vary freed a force-fixed polarization"

    # and the lock is conditional on the radiation, not a blanket freeze
    xray = rx.Refinement(structure, rx.Instrument.debye_scherrer(1.5406))
    assert next(r for r in xray.parameters()
                if r.path == "instrument.polarization").refinable


def test_surface_roughness_is_refused_on_a_neutron_source():
    """A µm-penetration correction applied to a cm-penetration beam.

    Refused rather than diagnosed: there is no legitimate reason to set it, and
    a stored roughness block is a claim rather than a default.
    """
    from pydantic import ValidationError  # noqa: PLC0415

    from rietx.schemas.instrument import (  # noqa: PLC0415
        EmissionLine,
        Geometry,
        RoughnessSuortti,
        Source,
    )

    geometry = dict(kind="bragg_brentano", goniometer_radius_mm=240.0,
                    surface_roughness=RoughnessSuortti())
    with pytest.raises(ValidationError, match="X-ray correction"):
        rx.Instrument(source=NeutronSource(wavelength=2.0780),
                      geometry=Geometry(**geometry))
    # the same block on an X-ray source is untouched
    ok = rx.Instrument(source=Source(lines=[EmissionLine(wavelength=1.5406)]),
                       geometry=Geometry(**geometry))
    assert ok.geometry.surface_roughness is not None


# ------------------------------------------------------------------ the fit ---
def _one_species(species: str) -> rx.Structure:
    """A minimal P1 cell carrying one atom of `species`, for the flag below."""
    P = rx.Parameter
    return rx.Structure(phases=[rx.Phase(
        name="probe", space_group="P 1",
        cell=rx.Cell(a=P(value=5.0), b=P(value=5.0), c=P(value=5.0),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=90.0)),
        scale=P(value=1.0),
        atoms=[rx.Atom(label=species, species=species, x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0), biso=P(value=0.5))])])


def test_a_resonant_absorber_is_named_rather_than_silently_tabulated():
    """Issue #113 (a) / WP-1312: ``is_resonant_absorber`` had no caller.

    ``b_Sears.dat`` stores the real part of the thermal ``b``, and for these
    nuclides that is incomplete rather than wrong -- near the resonance ``b``
    is complex and wavelength-dependent. At one CW wavelength away from it the
    thermal value is the right number, so this reports and never refuses.
    """
    from rietx.refine import _resonant_absorber_diagnostics  # noqa: PLC0415

    neutron = rx.Instrument.constant_wavelength_neutron(1.5406)
    fired = _resonant_absorber_diagnostics(_one_species("Gd"), neutron)
    assert [d.code for d in fired] == ["NEUTRON_RESONANT_ABSORBER"]
    assert fired[0].level == "warning"          # Gd absorbs 49700 barn
    assert "Gd" in fired[0].message
    assert fired[0].where == ["phases.0.atoms.0"]

    # Yb is the species this issue adds, and it lands as info rather than
    # warning: its *element* absorbs 34.80 barn, and the resonance is in a
    # minority isotope. Before this change it produced nothing at all.
    yb = _resonant_absorber_diagnostics(_one_species("Yb"), neutron)
    assert [d.code for d in yb] == ["NEUTRON_RESONANT_ABSORBER"]
    assert yb[0].level == "info"


def test_the_resonant_flag_is_silent_where_it_should_be():
    """Three negatives, because a flag that fires on everything says nothing.

    An ordinary species; a moderate absorber that is *not* classified resonant
    (Nd, which this campaign's own planning notes wrongly called one); and an
    X-ray source, where the analogue is ``DISPERSION_NEGLECTED`` and this
    would be answering a question about the wrong radiation.
    """
    from rietx.refine import _resonant_absorber_diagnostics  # noqa: PLC0415

    neutron = rx.Instrument.constant_wavelength_neutron(1.5406)
    xray = rx.Instrument.debye_scherrer(1.5406)

    assert _resonant_absorber_diagnostics(_one_species("O"), neutron) == []
    assert _resonant_absorber_diagnostics(_one_species("Nd"), neutron) == []
    assert _resonant_absorber_diagnostics(_one_species("Gd"), xray) == []


def test_the_resonant_flag_reaches_a_real_refinement_result():
    """The diagnostic is wired into the result, not merely importable.

    A private helper that no code path calls is what this issue was about in
    the first place, so the flag is asserted where a caller meets it.

    The plan frees the background alone.  This diagnostic is a statement about
    the *species*, so it needs a fit to have happened and nothing more, while
    the ``profile_only`` preset drags in something unrelated: its ``cell``
    stage frees ``phases.*.cell.*``, and those parameters carry declared
    bounds of (-inf, inf).  Against this deliberately featureless pattern the
    trust region therefore *probes* cells with angles up to 180.1 deg, whose
    reciprocal metric is not positive definite, and ``d_spacings`` answers
    each one with NaN and a bare ``RuntimeWarning`` -- 3430 of them in one
    fit.  The search rejects those points and the returned cell is correct,
    so this is noise and a missing bound rather than a wrong answer; it is
    also pre-existing and not this test's subject, so the test stays out of
    it.
    """
    tt = np.arange(20.0, 60.0, 0.2)
    data = rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.ones_like(tt).tolist())
    inst = rx.Instrument.constant_wavelength_neutron(1.5406, fwhm_deg=0.3)
    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="bkg", turn_on=["instrument.background.*"])])

    ref = rx.Refinement(_one_species("Gd"), inst)
    result = ref.fit(data, plan=plan, mode="lebail")
    assert "NEUTRON_RESONANT_ABSORBER" in {d.code for d in result.diagnostics}

    # and it is absent from the same fit on an ordinary species, so the
    # assertion above is about Gd and not about every result
    ref_o = rx.Refinement(_one_species("O"), inst)
    plain = ref_o.fit(data, plan=plan, mode="lebail")
    assert "NEUTRON_RESONANT_ABSORBER" not in {d.code for d in plain.diagnostics}


def test_xray_only_diagnostic_stays_quiet_for_neutrons():
    """DISPERSION_NEGLECTED would advise restoring a correction that does not
    exist for this radiation."""
    from rietx.refine import _dispersion_diagnostics  # noqa: PLC0415

    structure = rx.Structure(phases=[corundum()])
    neutron = rx.Instrument.constant_wavelength_neutron(2.0780)
    xray = rx.Instrument.debye_scherrer(1.5406)
    xray = xray.model_copy(update={
        "source": xray.source.model_copy(update={"dispersion": None})})

    assert _dispersion_diagnostics(structure, neutron) == []
    # and the diagnostic is not simply dead: declining it on an X-ray source
    # still says so, which is what makes the neutron silence a decision
    codes = {d.code for d in _dispersion_diagnostics(structure, xray)}
    assert "DISPERSION_NEGLECTED" in codes


def _tchz_fwhm(profile, two_theta_deg: float) -> float:
    """Total TCHZ FWHM in deg 2theta, from the stored coefficients.

    Caglioti for the Gaussian half, Gamma_L = X/cos(theta) + Y*tan(theta) for
    the Lorentzian, combined by Thompson-Cox-Hastings' fifth-order rule.
    Computed here rather than read off the model so the assertion is about
    the seeded *coefficients*, which is what issue #124 is about.
    """
    th = math.radians(two_theta_deg / 2.0)
    g_g = math.sqrt(max(profile.u.value * math.tan(th) ** 2
                        + profile.v.value * math.tan(th)
                        + profile.w.value, 0.0))
    g_l = profile.x.value / math.cos(th) + profile.y.value * math.tan(th)
    return (g_g ** 5 + 2.69269 * g_g ** 4 * g_l + 2.42843 * g_g ** 3 * g_l ** 2
            + 4.47163 * g_g ** 2 * g_l ** 3 + 0.07842 * g_g * g_l ** 4
            + g_l ** 5) ** 0.2


@pytest.mark.parametrize("fwhm_deg", [0.15, 0.30, 0.50])
def test_the_seeded_width_is_the_width_you_asked_for_at_every_angle(fwhm_deg):
    """Issue #124: the seed promised an observed peak width and delivered
    3.93x it at 150 deg.

    ``fwhm_deg`` used to seed ``w = (fwhm/2)**2`` *and* ``x = fwhm``. ``x`` is
    the Lorentzian Scherrer term, Gamma_L = X/cos(theta), so the seed both
    double-counted the width and climbed with angle -- worst over exactly the
    high-angle peaks a CW neutron cell refinement leans on hardest, and the
    frozen per-stage windows are sized from it.

    Measured on the old seed at ``fwhm_deg=0.3``: 0.369 deg at 2theta 20
    (1.23x), 0.405 at 60, 0.474 at 90, 0.637 at 120, **1.179 at 150 (3.93x)**.

    The assertion is deliberately across 20-150 deg rather than at one angle,
    because the defect was invisible at low angle: a test that checked only
    2theta 20 would have passed at 1.23x.
    """
    inst = rx.Instrument.constant_wavelength_neutron(1.5406, fwhm_deg=fwhm_deg)
    for two_theta in (20.0, 60.0, 90.0, 120.0, 150.0):
        got = _tchz_fwhm(inst.profile, two_theta)
        # 2 % covers the default Lorentzian X = 0.001 deg, which the seed
        # deliberately leaves alone: it contributes at most 1.4 % here, at the
        # narrowest seed and the highest angle. It is far tighter than the
        # defect, which reached 1.23x even at 2theta 20 and 3.93x at 150.
        assert got == pytest.approx(fwhm_deg, rel=0.02), (
            f"seeded FWHM {got:.4f} deg at 2theta {two_theta} against the "
            f"{fwhm_deg} deg asked for ({got / fwhm_deg:.2f}x)")


def test_the_seed_leaves_the_lorentzian_terms_alone():
    """The other half of #124, asserted on the coefficients rather than the
    width, so it cannot be satisfied by two wrong terms cancelling.

    ``x`` and ``y`` are sample-broadening terms -- Scherrer size and strain --
    and an instrument constructor has no business claiming either. Seeding
    ``w`` alone is also the right *shape*: a real CW resolution function is
    narrowest near the focusing angle and widens either side (Caglioti,
    Paoletti & Ricci 1958), so a flat seed is an honest zeroth order while a
    monotonically climbing one is not a coarse version of that curve.
    """
    default = rx.Instrument.constant_wavelength_neutron(1.5406)
    seeded = rx.Instrument.constant_wavelength_neutron(1.5406, fwhm_deg=0.30)

    assert seeded.profile.w.value == pytest.approx(0.30 ** 2)
    assert seeded.profile.x.value == default.profile.x.value
    assert seeded.profile.y.value == default.profile.y.value
    assert seeded.profile.u.value == default.profile.u.value
    assert seeded.profile.v.value == default.profile.v.value

    # …and the seed really moved w, so the four assertions above are not all
    # passing because `fwhm_deg` was ignored altogether.
    assert seeded.profile.w.value != default.profile.w.value


def _seeded_width(inst: rx.Instrument, fwhm_deg: float) -> rx.Instrument:
    """Same profile on both instruments, so only the amplitude differs.

    Mirrors ``constant_wavelength_neutron``'s own seed and must keep mirroring
    it: the comparison below is only about scattering amplitude if the two
    instruments carry an identical profile, so a divergence here would be
    invisible and would quietly change what that test measures.
    """
    profile = inst.profile.model_copy(update={
        "w": inst.profile.w.model_copy(update={"value": fwhm_deg ** 2}),
    })
    return inst.model_copy(update={"profile": profile})


def _y_calc(structure: rx.Structure, instrument: rx.Instrument,
            two_theta: np.ndarray) -> np.ndarray:
    """y_calc at the stored values, through the same seam a fit uses."""
    from rietx.model.forward import compile_model  # noqa: PLC0415
    from rietx.params.vector import ParameterTable  # noqa: PLC0415

    pattern = rx.PatternData(two_theta=two_theta.tolist(),
                             intensity=np.ones_like(two_theta).tolist())
    model = compile_model(structure, instrument, pattern)
    table = ParameterTable(structure, instrument)
    return model.evaluate(table.decode(table.x0()))


def test_neutron_intensities_are_not_the_xray_ones():
    """The test that would fail if the radiation were being ignored.

    For corundum the two amplitudes rank the atoms in *opposite* order —
    f_Al(0) = 13 > f_O(0) = 8 electrons, while b_Al = 3.449 fm < b_O = 5.803 fm
    — so oxygen dominates a neutron pattern and aluminium an X-ray one. The
    relative intensities must therefore reorder, not merely rescale.
    """
    tt = np.arange(15.0, 100.0, 0.02)
    structure = rx.Structure(phases=[corundum()])
    n = _y_calc(structure, rx.Instrument.constant_wavelength_neutron(
        1.5406, fwhm_deg=0.3), tt)
    x = _y_calc(structure, _seeded_width(
        rx.Instrument.debye_scherrer(1.5406), 0.3), tt)

    assert np.isfinite(n).all() and (n >= 0.0).all()
    assert n.max() > 0.0
    # same wavelength and same profile, so the peaks sit at the same 2theta;
    # what changes is which of them is tallest
    assert np.argmax(n) != np.argmax(x), (
        "neutron and X-ray patterns peak on the same reflection — the "
        "scattering amplitude is not reaching the structure factor")


def test_hexagonal_cell_ties_survive_a_neutron_source():
    """The cell constraints come from the space group, not the radiation."""
    ref = rx.Refinement(rx.Structure(phases=[corundum()]),
                        rx.Instrument.constant_wavelength_neutron(2.0780))
    paths = {row.path for row in ref.parameters()}
    assert "phases.0.cell.a" in paths
    # b follows a in a hexagonal setting, so it is tied rather than free
    b_row = next(r for r in ref.parameters() if r.path == "phases.0.cell.b")
    assert not b_row.refinable
    gamma = next(r for r in ref.parameters() if r.path == "phases.0.cell.gamma")
    assert math.isclose(gamma.value, 120.0)


# ------------------------------------------------- specimen absorption ---
# The constructor accepting a bare float, the neutron estimate reading the
# neutron table (WP-1132), the fence still declining for a kind with no
# table, and the X-ray control proving the X-ray path is unchanged.
def test_a_declared_mu_r_reaches_the_geometry_as_a_plain_float():
    """``mu_r`` is a float on ``Geometry``, deliberately, and this constructor
    wrapped it in a ``Parameter`` — so *every* call passing one raised.

    The Rouse expression factors exactly into a Debye-Waller shape, so a free
    µR would be an exactly singular direction beside the phase scale and Biso;
    that is why the field is a plain float and not refinable.  Nothing caught
    the wrong type because no test passed ``mu_r`` to this constructor at all.
    """
    inst = rx.Instrument.constant_wavelength_neutron(
        2.0780, capillary_radius_mm=0.4, mu_r=0.5)
    assert inst.geometry.mu_r == 0.5
    assert isinstance(inst.geometry.mu_r, float)


def test_a_neutron_capillary_is_estimated_from_the_neutron_table():
    """Since WP-1132 a neutron capillary with a radius gets a µR — the
    **neutron** one, never the X-ray number the fence used to keep out.

    ``crystallography.attenuation`` is X-ray photoabsorption; neutron σ_abs
    scales as λ (1/v) where X-ray µ/ρ rises roughly as λ³ (falls as E⁻³)
    and has edges.  So the value written onto the geometry is asserted equal
    to the Sears-table estimate and **unequal** to the X-ray one for the same
    arguments: an implementation that wired the X-ray table back in fails the
    second line.
    """
    from rietx.optimize.qpa import estimate_capillary_mu_r
    from rietx.params.vector import ParameterTable
    from rietx.refine import _resolve_specimen_absorption, estimate_mu_r

    struct = rx.Structure(phases=[corundum()])
    inst = rx.Instrument.constant_wavelength_neutron(
        2.0780, capillary_radius_mm=0.4)
    assert inst.geometry.mu_r is None

    table = ParameterTable(struct, inst)
    values = table.decode(table.x0())
    neutron, _ = estimate_capillary_mu_r(struct, values, 2.0780, 0.4, 0.6,
                                         source_kind="neutron_cw")
    xray, _ = estimate_capillary_mu_r(struct, values, 2.0780, 0.4, 0.6)
    assert neutron is not None and xray is not None
    assert xray > 10.0 * neutron          # corundum: ≈ 0.0092 against ≈ 7.3

    assert estimate_mu_r(struct, inst) == pytest.approx(neutron, rel=1e-12)
    source, reason = _resolve_specimen_absorption(struct, inst)
    assert (source, reason) == ("estimated", None)
    assert inst.geometry.mu_r == pytest.approx(neutron, rel=1e-12)


def test_a_source_kind_with_no_table_still_declines(monkeypatch):
    """The fence stays for every source without a table (time-of-flight).

    No such kind is constructible in this tree yet, so the table entry for
    neutrons is removed for the duration of the test: what is asserted is the
    *mechanism* — a kind missing from ``LINEAR_ATTENUATION_BY_SOURCE``
    declines with the fence's reason and leaves the field untouched, in both
    geometries and in ``estimate_mu_r`` — which is what a TOF source will
    meet when it lands.
    """
    from rietx.optimize import qpa
    from rietx.refine import _resolve_specimen_absorption, estimate_mu_r

    monkeypatch.delitem(qpa.LINEAR_ATTENUATION_BY_SOURCE, "neutron_cw")
    struct = rx.Structure(phases=[corundum()])
    inst = rx.Instrument.constant_wavelength_neutron(
        2.0780, capillary_radius_mm=0.4)
    assert estimate_mu_r(struct, inst) is None
    source, reason = _resolve_specimen_absorption(struct, inst)
    assert source == "estimated"
    assert reason is not None and "no attenuation table" in reason
    assert inst.geometry.mu_r is None

    plate = rx.Instrument(
        source=inst.source,
        geometry=rx.Geometry(kind="bragg_brentano", goniometer_radius_mm=240.0,
                             thickness_mm=1.0))
    source, reason = _resolve_specimen_absorption(struct, plate)
    assert reason is not None and "no attenuation table" in reason
    assert plate.geometry.mu_t is None


def test_declaring_mu_r_still_applies_the_correction_on_a_neutron_source():
    """The fence is on the *table*, not on the correction.

    Rouse's cylinder absorption is geometry, not radiation, so a µR the user
    measured is honoured exactly as it is for an X-ray capillary.
    """
    from rietx.refine import _resolve_specimen_absorption

    struct = rx.Structure(phases=[corundum()])
    inst = rx.Instrument.constant_wavelength_neutron(
        2.0780, capillary_radius_mm=0.4, mu_r=0.6)
    source, reason = _resolve_specimen_absorption(struct, inst)
    assert (source, reason) == ("given", None)
    assert inst.geometry.mu_r == 0.6


def test_the_xray_control_still_estimates():
    """The fence must not be "estimation never happens" — the X-ray path is
    unchanged, which is the only thing that makes the test above mean anything.
    """
    from rietx.refine import _resolve_specimen_absorption

    struct = rx.Structure(phases=[corundum()])
    inst = rx.Instrument.debye_scherrer(wavelength=1.5406,
                                        capillary_radius_mm=0.4)
    assert inst.geometry.mu_r is None
    source, reason = _resolve_specimen_absorption(struct, inst)
    assert source == "estimated"
    assert reason is None, f"X-ray estimate unexpectedly declined: {reason}"
    assert isinstance(inst.geometry.mu_r, float) and inst.geometry.mu_r > 0.0


def test_a_declared_mu_r_reaches_the_absorption_record():
    """Past the schema and into the record — the field is not the correction.

    ``test_a_declared_mu_r_reaches_the_geometry_as_a_plain_float`` pins the
    type; this pins that a µR declared on a *neutron* capillary actually
    produces a Rouse correction with the right λ, and that the off state
    reports nothing rather than zero.

    The λ² claim is asserted as a **ratio measured against the X-ray case**
    rather than against a hard-coded Å², so the test states the physics — the
    bias is c(µR)·λ²/2, so the same specimen costs a 2.078 Å neutron fit
    (2.078/1.5406)² ≈ 1.82× what it costs at Cu Kα — instead of pinning a
    number whose provenance a later reader could not check.
    """
    from rietx.model.forward import compile_model
    from rietx.refine import _absorption_record

    tt = np.arange(15.0, 100.0, 0.05)
    pattern = rx.PatternData(two_theta=tt.tolist(),
                             intensity=np.ones_like(tt).tolist())
    structure = rx.Structure(phases=[corundum()])

    def record_for(inst):
        ref = rx.Refinement(structure.model_copy(deep=True), inst)
        model = compile_model(ref.structure, ref.instrument, pattern)
        return _absorption_record(model, ref._mu_r_source, ref._mu_r_skipped)

    neutron = rx.Instrument.constant_wavelength_neutron(
        2.0780, mu_r=0.5, fwhm_deg=0.3)
    rec = record_for(neutron)
    assert rec is not None, "a declared µR applied no correction"
    assert rec.method == "rouse_cylinder"
    assert rec.mu_r == pytest.approx(0.5)
    # declared, not estimated — and no radius was given, so none could be made
    assert rec.mu_r_source == "given"
    assert rec.wavelength == pytest.approx(2.0780)

    # the λ² scaling, measured: same µR, same specimen, X-ray wavelength
    xray = rx.Instrument.debye_scherrer(wavelength=1.5406, mu_r=0.5)
    rec_x = record_for(xray)
    assert rec_x is not None
    assert rec.equivalent_delta_biso / rec_x.equivalent_delta_biso == \
        pytest.approx((2.0780 / 1.5406) ** 2, rel=1e-9)

    # µR = 0 is the off state (A ≡ 1), which reports nothing rather than zero
    assert record_for(rx.Instrument.constant_wavelength_neutron(
        2.0780, mu_r=0.0, fwhm_deg=0.3)) is None


# ------------------------------------------------------- isotopes reach it ---
@pytest.mark.parametrize("species,expect_b", [
    ("H", -3.739), ("D", 6.671), ("2H", 6.671), ("7Li", -2.220),
    ("157Gd", -1.140),
])
def test_an_isotope_label_survives_the_species_normaliser(species, expect_b):
    """The isotope convention was implemented one line below where it was lost.

    ``compile_phase_sites`` normalised every species through the **X-ray**
    normaliser before branching on ``neutron``, and that normaliser validates
    against Waasmaier-Kirfel coefficients — which no isotope has, and which a
    neutron phase never needs, because it resolves ``b_coh`` instead and
    reaches ``f0`` nowhere.  So ``D``, ``2H`` and ``7Li`` raised "no
    Waasmaier-Kirfel coefficients" while the shipped Sears table has had
    b(²H) = +6.671 fm all along.  The headline neutron case, and no test
    covered it.

    ``D`` and ``2H`` must give the *same* answer — the alias is the convention,
    not a second entry — and it must differ in **sign** from ``H``, which is
    the whole reason anyone deuterates a sample for neutrons.
    """
    from rietx.crystallography.structure_factor import compile_phase_sites

    P = rx.Parameter
    phase = rx.Phase(
        name="one-site", space_group="P 1",
        cell=rx.Cell(a=P(value=5.0), b=P(value=5.0), c=P(value=5.0),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=90.0)),
        atoms=[rx.Atom(label="A", species=species, x=P(value=0.0),
                       y=P(value=0.0), z=P(value=0.0))])
    sites = compile_phase_sites(phase, neutron=True)
    assert sites.b_coh is not None
    assert sites.b_coh[0] == pytest.approx(expect_b, abs=1e-3)


def test_deuterium_and_hydrogen_differ_in_sign():
    """Asserted on its own because it is the reason the case matters.

    b(H) is negative and b(²H) positive, so an H/D substitution inverts that
    site's contribution to every structure factor.  A test that only checked
    "an isotope does not raise" would pass on a table that returned b(H) for D.
    """
    from rietx.crystallography.neutron import b_coh

    assert b_coh("H") < 0.0 < b_coh("D")
    assert b_coh("D") == b_coh("2H")


# ------------------------------------------ neutron attenuation (WP-1132) ---
def test_neutron_attenuation_of_a_vanadium_cell_by_hand():
    """µ from the Sears row for V, worked by hand, pinning the **unit**.

    Sears (1992) / ITC C Table 4.4.4.1, as ``b_Sears.dat`` carries them:
    V σ_abs = 5.08, σ_coh = 0.0184, σ_inc = 5.08 barn.  A synthetic bcc cell,
    a = 3.03 Å, two atoms, V_cell = 3.03³ = 27.818127 Å³.

    At λ = 1.798 Å (where σ_abs is quoted) the 1/v factor is 1:
        σ_tot = 5.08 + 0.0184 + 5.08 = 10.1784 barn
        µ     = 2 × 10.1784 / 27.818127 = 0.731782 cm⁻¹
    At λ = 2.4067 Å, σ_abs × 2.4067/1.798 = 6.799798 barn:
        σ_tot = 6.799798 + 0.0184 + 5.08 = 11.898198 barn
        µ     = 2 × 11.898198 / 27.818127 = 0.855428 cm⁻¹

    barn/Å³ = 10⁻²⁴ cm² / 10⁻²⁴ cm³ = 1/cm, the unit
    ``attenuation.packed_mu_r`` takes; a factor of 10⁸ or 10⁻⁸ here would be
    the Å/cm slip, and a result near 0.73 rules both out.
    """
    from rietx.crystallography.neutron import linear_attenuation_neutron

    v_cell = 3.03 ** 3
    assert linear_attenuation_neutron({"V": 2.0}, v_cell, 1.798) == \
        pytest.approx(0.731782, abs=2e-6)
    assert linear_attenuation_neutron({"V": 2.0}, v_cell, 2.4067) == \
        pytest.approx(0.855428, abs=2e-6)


@pytest.mark.parametrize("species", ["H", "D", "O", "Ni"])
def test_the_scattering_cross_sections_are_the_bound_values(species):
    """σ_coh = 4π·b_coh² with the table's own *bound* b, so the attenuation
    reads bound-atom cross-sections, as the docstring and manual say.

    The free-atom σ is (A/(A+1))² of the bound one — 0.25 for H, 0.44 for D —
    so a *mixed* table, bound b beside free-atom σ, would fail this by a
    factor of four on hydrogen (82.0 barn bound against 20.5 free).  A table
    free-atom throughout is self-consistent and passes here; the bound values
    themselves are pinned elsewhere: b_H = −3.739 fm by
    ``test_an_isotope_label_survives_the_species_normaliser``, and H's σ_tot
    at 1.798 Å (82.35 b) by
    ``test_deuteration_is_an_isotope_not_an_element_for_attenuation``.
    """
    from rietx.crystallography.neutron import properties

    row = properties(species)
    assert row["xs_coh_barn"] == pytest.approx(
        4.0 * np.pi * row["b_coh_fm"] ** 2 / 100.0, rel=5e-3)


def test_neutron_absorption_scales_linearly_in_wavelength():
    """The 1/v law is the whole difference from the X-ray case.

    σ_tot(λ) − σ_scatt must be *proportional* to λ with slope σ_abs/1.798:
    equal steps in λ give equal steps in σ, and doubling λ doubles the
    absorption part.  An X-ray µ/ρ rises roughly as λ³ (falls as E⁻³)
    between edges, so the X-ray total fails the same check — asserted too, so
    this test cannot pass on a table that has the wrong λ dependence.
    """
    from rietx.crystallography.attenuation import total_cross_section
    from rietx.crystallography.neutron import (
        properties,
        total_cross_section_neutron,
    )

    row = properties("W")
    scatt = row["xs_coh_barn"] + row["xs_inc_barn"]
    lams = [1.0, 1.5, 2.0, 2.5, 3.0]
    absorbed = [total_cross_section_neutron("W", lam) - scatt for lam in lams]
    for lam, a in zip(lams, absorbed):
        assert a == pytest.approx(row["xs_abs_barn"] * lam / 1.798, rel=1e-12)
    steps = np.diff(absorbed)
    assert np.allclose(steps, steps[0], rtol=1e-12)
    assert absorbed[2] == pytest.approx(2.0 * absorbed[0], rel=1e-12)

    # the X-ray table rises with λ roughly as λ³, far faster than linearly
    # (O: no edge in this range to confuse the ratio, which W's L edges near
    # 1.1 Å would); the exponent is the one the docstring states
    xray = [total_cross_section("O", lam) for lam in (1.0, 2.0)]
    assert 2.5 < np.log2(xray[1] / xray[0]) < 3.5


def _h_share(attenuation, lam: float) -> float:
    """Fraction of brucite's µ that its hydrogen carries, under ``attenuation``.

    Mg(OH)₂ on a synthetic P-3m1 cell (a = 3.142, c = 4.766 Å), one formula
    unit per cell, compared with the same cell stripped of its H.
    """
    v = 3.142 ** 2 * math.sin(math.radians(120.0)) * 4.766
    with_h = attenuation({"Mg": 1.0, "O": 2.0, "H": 2.0}, v, lam)
    without = attenuation({"Mg": 1.0, "O": 2.0}, v, lam)
    return (with_h - without) / with_h


def test_hydrogen_dominates_neutron_attenuation_and_not_xray():
    """The hydrogen row of WP-1132's table, with the arm that catches a
    mis-wiring built in.

    Sears: H σ_inc = 80.26 barn (the shipped table's digit; the WP's text says
    80.27), σ_coh = 1.7568, σ_abs = 0.3326 — against Mg σ_coh 3.631,
    σ_inc 0.08, σ_abs 0.063 and O 4.232, 0.0008, 0.00019.  Per brucite
    formula unit at 2.4067 Å the two H carry 2 × (80.26 + 1.7568 + 0.4452)
    = 164.9 barn of 177.2, so **≈ 93 %** of µ.  Under the X-ray table the
    same two H carry well under 1 %: hydrogen has one electron.

    The WP phrases this as "far more attenuating than the X-ray estimator
    says for the same cell", which is not true in absolute terms at a common
    wavelength — X-ray µ for brucite at 2.4067 Å is ≈ 206 cm⁻¹ against the
    neutron ≈ 4.35 — so the claim is asserted as the **share hydrogen
    carries**, which is the property that makes an X-ray number wrong in
    kind.  The negative arm runs the identical predicate on the X-ray
    function and requires it to fail, so wiring the X-ray table into the
    neutron path cannot pass this test.
    """
    from rietx.crystallography.attenuation import linear_attenuation
    from rietx.crystallography.neutron import linear_attenuation_neutron

    for lam in (1.5406, 2.4067):
        assert _h_share(linear_attenuation_neutron, lam) > 0.9
        # the negative arm: the same predicate on the X-ray table must fail
        assert _h_share(linear_attenuation, lam) < 0.01


def test_deuteration_is_an_isotope_not_an_element_for_attenuation():
    """``D`` resolves to ²H (σ_inc 2.05 barn), not to H (80.26).

    The QPA composition keeps ``D`` as its own key, and the neutron path must
    read it as the nuclide it names: a table that folded D into H would make
    a deuterated specimen look ≈ 20× as attenuating as it is.
    """
    from rietx.crystallography.neutron import total_cross_section_neutron

    h = total_cross_section_neutron("H", 1.798)
    d = total_cross_section_neutron("D", 1.798)
    assert h == pytest.approx(0.3326 + 1.7568 + 80.26, rel=1e-12)
    assert d == pytest.approx(0.000519 + 5.592 + 2.05, rel=1e-12)
    assert h / d > 10.0


def test_neutron_attenuation_names_an_untabulated_species():
    """A missing or ``---`` row raises naming the species, never returns 0."""
    from rietx.crystallography.neutron import total_cross_section_neutron

    with pytest.raises(KeyError, match="Xx"):
        total_cross_section_neutron("Xx", 1.798)
    with pytest.raises(KeyError, match="83Kr"):
        total_cross_section_neutron("83Kr", 1.798)
    with pytest.raises(ValueError, match="positive"):
        total_cross_section_neutron("O", 0.0)


@pytest.mark.parametrize("species", ["Gd", "Yb", "Cd", "Sm", "Eu"])
def test_a_resonant_absorber_refuses_the_neutron_estimate(species):
    """The neutron twin of the X-ray "straddles an edge" refusal (WP-1132
    item 4): the thermal σ_abs scaled by 1/v is wrong in principle near a
    resonance, and with how near a resonance matters not modelled, every listed
    absorber refuses — Yb, whose element absorbs only 34.8 barn, included.

    A mass-numbered nuclide (``157Gd``) refuses at the cross-section too, and
    since #543 a *structure* carrying one reaches that refusal: the QPA
    composition reads a mass number (``qpa.element_symbol``) instead of
    declining first with a parse error of its own.
    """
    from rietx.crystallography.neutron import total_cross_section_neutron
    from rietx.refine import _resolve_specimen_absorption

    with pytest.raises(ValueError, match="resonant neutron absorber"):
        total_cross_section_neutron(species, 2.4067)

    inst = rx.Instrument.constant_wavelength_neutron(
        2.4067, capillary_radius_mm=2.5)
    source, reason = _resolve_specimen_absorption(_one_species(species), inst)
    assert source == "estimated"
    assert reason is not None and "resonant neutron absorber" in reason
    assert inst.geometry.mu_r is None       # declined, not guessed


def test_a_resonant_nuclide_refuses_as_a_resonance_not_as_a_parse_error():
    """Before #543 the composition could not read ``157Gd`` and declined with
    "cannot parse an element"; now the nuclide reaches the Sears table and the
    refusal is the resonance's, which is the reason that is true."""
    from rietx.crystallography.neutron import total_cross_section_neutron
    from rietx.refine import _resolve_specimen_absorption

    with pytest.raises(ValueError, match="resonant neutron absorber"):
        total_cross_section_neutron("157Gd", 2.4067)
    inst = rx.Instrument.constant_wavelength_neutron(
        2.4067, capillary_radius_mm=2.5)
    _, reason = _resolve_specimen_absorption(_one_species("157Gd"), inst)
    assert reason is not None and "157Gd" in reason
    assert "resonant neutron absorber" in reason
    assert "cannot parse" not in reason
    assert inst.geometry.mu_r is None


def test_the_resonant_refusal_is_about_resonance_not_about_absorbing():
    """Nd and B absorb strongly (50.5 and 767 barn) and are not resonant,
    so they estimate; an explicit µR on a Gd specimen is still honoured."""
    from rietx.refine import _resolve_specimen_absorption

    for species in ("Nd", "B"):
        inst = rx.Instrument.constant_wavelength_neutron(
            2.4067, capillary_radius_mm=2.5)
        assert _resolve_specimen_absorption(_one_species(species), inst) == \
            ("estimated", None)
        assert inst.geometry.mu_r > 0.0
    given = rx.Instrument.constant_wavelength_neutron(
        2.4067, capillary_radius_mm=2.5, mu_r=1.2)
    assert _resolve_specimen_absorption(_one_species("Gd"), given) == \
        ("given", None)


def test_the_resonant_refusal_reaches_a_real_refinement_result():
    """The refusal is surfaced as ``ABSORPTION_ESTIMATE_UNAVAILABLE`` with the
    resonance named in the message — the same channel the X-ray edge refusal
    uses — and the fit runs with no absorption correction rather than a
    wrong one."""
    tt = np.arange(20.0, 60.0, 0.2)
    data = rx.PatternData(two_theta=tt.tolist(),
                          intensity=np.ones_like(tt).tolist())
    inst = rx.Instrument.constant_wavelength_neutron(
        1.5406, fwhm_deg=0.3, capillary_radius_mm=2.5)
    plan = rx.RefinementPlan(stages=[
        rx.Stage(name="bkg", turn_on=["instrument.background.*"])])
    result = rx.Refinement(_one_species("Gd"), inst).fit(data, plan=plan)
    hits = [d for d in result.diagnostics
            if d.code == "ABSORPTION_ESTIMATE_UNAVAILABLE"]
    assert len(hits) == 1 and "resonant neutron absorber" in hits[0].message


# --------------------------- Brindley microabsorption on a neutron fit (#543) ---
#: #543's synthetic specimen: NaCl + W, both at 5 µm, on HB-2A's λ.
_BRINDLEY_LAM = 2.4067


def _nacl_w(radius_um: float | None = 5.0, na: str = "Na") -> rx.Structure:
    P = rx.Parameter

    def atom(label, species, xyz, b=0.5):
        return rx.Atom(label=label, species=species, x=P(value=xyz[0]),
                       y=P(value=xyz[1]), z=P(value=xyz[2]), biso=P(value=b))

    nacl = rx.Phase(name="NaCl", space_group="F m -3 m",
                    cell=rx.Cell.cubic(5.6402, vary=True),
                    atoms=[atom("Na", na, (0, 0, 0)),
                           atom("Cl", "Cl", (0.5, 0.5, 0.5))],
                    particle_radius_um=radius_um)
    w = rx.Phase(name="W", space_group="I m -3 m",
                 cell=rx.Cell.cubic(3.1652, vary=True),
                 atoms=[atom("W", "W", (0, 0, 0), 0.3)],
                 particle_radius_um=radius_um)
    nacl.scale.value, w.scale.value = 3e-4, 2e-4
    return rx.Structure(phases=[nacl, w])


def _qpa_at_start(structure, source_kind, wavelength=_BRINDLEY_LAM):
    """``compute_qpa`` at the stored values: the seam without a fit."""
    from rietx.optimize.qpa import compute_qpa
    from rietx.params.vector import ParameterTable

    table = ParameterTable(structure, rx.Instrument.constant_wavelength_neutron(
        wavelength, fwhm_deg=0.3))
    return compute_qpa(structure, table.decode(table.x0()),
                       wavelength=wavelength, source_kind=source_kind)


#: µ (1/cm) by hand from the Sears (1992) rows in ``b_Sears.dat``
#: (σ_abs·λ/1.798 + σ_coh + σ_inc, barn) at the stored cells.
#: NaCl, 4 Na + 4 Cl in 5.6402³ Å³: Na 0.53, 1.66, 1.62; Cl 33.5, 11.5257, 5.3.
#: W, 2 atoms in 3.1652³ Å³: 18.3, 2.97, 1.63.
_NEUTRON_MU_BY_HAND = {
    "NaCl": 4 * ((0.53 + 33.5) * _BRINDLEY_LAM / 1.798
                 + 1.66 + 1.62 + 11.5257 + 5.3) / 5.6402 ** 3,
    "W": 2 * (18.3 * _BRINDLEY_LAM / 1.798 + 2.97 + 1.63) / 3.1652 ** 3,
}


def test_brindley_on_a_neutron_fit_reads_the_neutron_table():
    """Issue #543, its own reproduction: a negligible neutron correction.

    At λ = 2.4067 Å and R = 5 µm the neutron µR is ≈ 1e-3, inside Brindley's
    regime, so ``weight_fraction_corrected`` must sit on ``weight_fraction``.
    Before the fix the path read the X-ray table on every source: µ = 578.6
    and 10290 cm⁻¹, and NaCl moved from 0.887 to 0.002 under a
    ``BRINDLEY_OUTSIDE_REGIME`` that blamed the particle size.

    The positive arm: the X-ray µ of the same cells is more than 100× the
    neutron one, so a path that read it would fail every assertion below.
    """
    from rietx.crystallography.attenuation import linear_attenuation
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    s = _nacl_w()
    ins = rx.Instrument.constant_wavelength_neutron(_BRINDLEY_LAM, fwhm_deg=0.3)
    tt = np.arange(10.0, 150.0, 0.05)
    grid = rx.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    m = compile_model(s, ins, grid, mode="rietveld")
    t = ParameterTable(s, ins)
    y = np.random.default_rng(3).poisson(
        np.maximum(m.evaluate(t.decode(t.x0())), 1.0)).astype(float)
    data = rx.PatternData(two_theta=m.tt.tolist(), intensity=y.tolist())
    r = rx.Refinement(s, ins, history=False).fit(
        data, plan=rx.RefinementPlan(stages=[rx.Stage("scale", ["phases.*.scale"])]))

    assert r.qpa.microabsorption_skipped is None
    assert r.qpa.microabsorption is not None
    xray = {"NaCl": linear_attenuation({"Na": 4, "Cl": 4}, 5.6402 ** 3,
                                       _BRINDLEY_LAM),
            "W": linear_attenuation({"W": 2}, 3.1652 ** 3, _BRINDLEY_LAM)}
    for p in r.qpa.phases:
        assert p.mu_cm == pytest.approx(_NEUTRON_MU_BY_HAND[p.name], rel=1e-9)
        assert xray[p.name] > 100.0 * p.mu_cm          # the arm that can fail
        assert p.mu_r < 1e-2
        assert abs(p.weight_fraction_corrected - p.weight_fraction) < 1e-3
    assert "BRINDLEY_OUTSIDE_REGIME" not in {d.code for d in r.diagnostics}


def test_brindley_on_an_xray_source_still_reads_mcmaster():
    """The control: the same specimen on ``xray_cw`` keeps the X-ray µ, so the
    fix routes the table rather than switching the correction off."""
    from rietx.crystallography.attenuation import linear_attenuation

    q = _qpa_at_start(_nacl_w(), "xray_cw")
    mu = {p.name: p.mu_cm for p in q.phases}
    assert mu["NaCl"] == pytest.approx(
        linear_attenuation({"Na": 4, "Cl": 4}, 5.6402 ** 3, _BRINDLEY_LAM),
        rel=1e-12)
    assert mu["W"] == pytest.approx(
        linear_attenuation({"W": 2}, 3.1652 ** 3, _BRINDLEY_LAM), rel=1e-12)
    assert q.phases[0].weight_fraction_corrected < 0.01    # #543's X-ray number


def test_brindley_declines_on_a_source_with_no_table():
    """A kind missing from ``LINEAR_ATTENUATION_BY_SOURCE`` skips with that
    reason, as the specimen-absorption estimators do, and never borrows."""
    q = _qpa_at_start(_nacl_w(), "no_such_source")
    assert q.microabsorption is None
    assert "no attenuation table" in q.microabsorption_skipped
    assert "no_such_source" in q.microabsorption_skipped
    assert all(p.weight_fraction_corrected is None for p in q.phases)
    assert all(p.weight_fraction is not None for p in q.phases)


@pytest.mark.parametrize("species, element, weight", [
    ("Fe3+", "Fe", 55.845), ("Cval", "C", 12.0107), ("Dy", "Dy", 162.5),
    ("D", "H", 2.0141), ("2H", "H", 2.0141), ("D1", "H", 2.0141),
    ("T", "H", 3.0), ("7Li", "Li", 7.0), ("157Gd", "Gd", 157.0),
])
def test_a_nuclide_reads_as_its_element_and_weighs_as_itself(
        species, element, weight):
    """#556 follow-up 1: ``qpa.element_symbol`` read ``D`` as its own symbol
    (no McMaster row) and could not read ``7Li`` at all.  The element answers
    an element's question; the mass is the nuclide's — gemmi's 2.0141 for ²H,
    the mass number otherwise (within 0.26 % of the NIST mass above A = 4)."""
    from rietx.optimize.qpa import atomic_weight, element_symbol

    assert element_symbol(species) == element
    assert atomic_weight(species) == pytest.approx(weight, abs=1e-4)


def test_a_nuclide_in_the_structure_no_longer_breaks_the_fit():
    """``7Li`` compiles on a neutron source (WP-1134), and until #543 the QPA
    composition then raised "cannot parse an element" and took the whole
    result with it."""
    q = _qpa_at_start(_nacl_w(na="7Li"), "neutron_cw")
    nacl = q.phases[0]
    assert nacl.cell_mass == pytest.approx(4 * (7.0 + 35.453), rel=1e-6)
    assert nacl.weight_fraction_corrected is not None


def test_deuterium_is_hydrogen_to_xrays_and_itself_to_neutrons():
    """The two tables read the composition by their own identity: an X-ray µ
    is the same for ¹H and ²H (the McMaster estimate on a deuterated specimen
    used to decline, "no attenuation data for element 'D'"), a neutron µ is
    not (σ_inc 80.26 barn against 2.05)."""
    from rietx.optimize.qpa import estimate_capillary_mu_r
    from rietx.params.vector import ParameterTable

    def mu_r(h, kind):
        s = _one_species(h)
        table = ParameterTable(s, rx.Instrument.constant_wavelength_neutron(1.5))
        got, reason = estimate_capillary_mu_r(
            s, table.decode(table.x0()), 1.5, 1.0, 0.6, source_kind=kind)
        assert reason is None, reason
        return got

    assert mu_r("D", "xray_cw") == mu_r("H", "xray_cw")
    assert mu_r("2H", "xray_cw") == mu_r("H", "xray_cw")
    assert mu_r("D", "neutron_cw") == mu_r("2H", "neutron_cw")
    assert mu_r("H", "neutron_cw") > 10.0 * mu_r("D", "neutron_cw")


# ------------------------------------ the Cr₂WO₆ HB-2A specimen (WP-1132) ---
DATA = Path(__file__).parent / "data"


def _cr2wo6_trirutile() -> rx.Structure:
    """Cr₂WO₆ on the ideal trirutile start ``test_acceptance_magnetic`` uses
    (P4₂/mnm, a = 4.58, c = 8.85 Å; W 2a, Cr 4e, O 4f + 8j: Cr₄W₂O₁₂ per
    cell) — the tutorial's CIF is an ICSD entry and is not vendored."""
    P = rx.Parameter

    def atom(label, species, x, y, z):
        return rx.Atom(label=label, species=species, x=P(value=x),
                       y=P(value=y), z=P(value=z), biso=P(value=0.5))

    return rx.Structure(phases=[rx.Phase(
        name="Cr2WO6", space_group="P 42/m n m",
        cell=rx.Cell(a=P(value=4.58), b=P(value=4.58), c=P(value=8.85),
                     alpha=P(value=90.0), beta=P(value=90.0),
                     gamma=P(value=90.0)),
        atoms=[atom("W1", "W", 0.0, 0.0, 0.0),
               atom("Cr1", "Cr", 0.0, 0.0, 1.0 / 3.0),
               atom("O1", "O", 0.3, 0.3, 0.0),
               atom("O2", "O", 0.3, 0.3, 1.0 / 3.0)])])


#: **Assumed**, not measured: neither the vendored HB-2A files
#: (``gsas2_hb2a_cr2wo6.prm``, ``gsas2_hb2a_cr2wo6_{4K,150K}.dat``) nor their
#: provenance rows state a can or a sample radius, so this is a round number
#: for a neutron powder can, and the packing is ``Geometry``'s default 0.6.
CR2WO6_ASSUMED_RADIUS_MM = 3.0


def test_the_cr2wo6_hb2a_estimate_matches_the_sears_table_by_hand():
    """WP-1132 item 5, as far as the tree can take it honestly.

    λ = 2.4067 Å is read from the vendored GSAS ``.prm`` (``ICONS``), so the
    instrument half is the real diffractometer's; the radius is the
    **assumption** above.  By hand, from ``b_Sears.dat`` (barn: σ_abs, σ_coh,
    σ_inc — Cr 3.05, 1.66, 1.83; W 18.3, 2.97, 1.63; O 0.00019, 4.232,
    0.0008), λ/1.798 = 1.3385428:

        Cr  4 × (3.05 × 1.3385428 + 1.66 + 1.83)     =  30.290222
        W   2 × (18.3 × 1.3385428 + 2.97 + 1.63)     =  58.190668
        O  12 × (0.00019 × 1.3385428 + 4.232 + 0.0008) = 50.796652
        Σ = 139.277542 barn,  V = 4.58² × 8.85 = 185.641140 Å³
        µ  = 139.277542 / 185.641140 = 0.750251 cm⁻¹
        µR = 0.6 × 0.750251 × 0.30 cm = 0.135045

    What this does **not** do is validate µR against a measurement.  No
    measured µR or radius is in the tree, and a fit cannot supply one: the
    Rouse factor is exactly a reparameterisation of scale ⊗ Biso
    (``model/absorption.py``), so Rwp on this pattern cannot move with µR.
    The number's consequence is the ΔBiso it implies, ≈ 0.034 Å² here.
    """
    from rietx.model.absorption import equivalent_delta_biso
    from rietx.refine import _resolve_specimen_absorption, estimate_mu_r

    inst = rx.read_gsas_prm(DATA / "gsas2_hb2a_cr2wo6.prm")
    assert inst.source.kind == "neutron_cw"
    assert inst.source.primary_wavelength == pytest.approx(2.4067)
    inst.geometry.capillary_radius_mm = CR2WO6_ASSUMED_RADIUS_MM

    structure = _cr2wo6_trirutile()
    mu_r = estimate_mu_r(structure, inst)
    assert mu_r == pytest.approx(0.135045, abs=2e-6)

    # the fit-time path writes the same number onto the geometry
    source, reason = _resolve_specimen_absorption(structure, inst)
    assert (source, reason) == ("estimated", None)
    assert inst.geometry.mu_r == pytest.approx(mu_r, rel=1e-12)
    assert equivalent_delta_biso(mu_r, 2.4067) == pytest.approx(0.0342, abs=5e-4)


def test_every_resonant_absorber_has_a_resonance_energy():
    """WP-1312 task 2: the flag says *that* a species is resonant, and each
    member of ``RESONANT_ABSORBERS`` now also says *where*.  Crossed both ways,
    so a new member without an energy fails here and an energy for a nuclide
    that is not flagged does too."""
    from rietx.crystallography.neutron import (  # noqa: PLC0415
        NEUTRON_LAMBDA_EV_ANGSTROM,
        RESONANCE_ENERGY_EV,
        RESONANT_ABSORBERS,
        SIGMA_ABS_REFERENCE_WAVELENGTH,
        resonance_wavelengths,
    )

    assert set(RESONANCE_ENERGY_EV) <= RESONANT_ABSORBERS
    from rietx.crystallography.neutron import _RESONANCE_CARRIERS  # noqa: PLC0415
    assert set(_RESONANCE_CARRIERS) <= RESONANT_ABSORBERS
    assert {n for ns in _RESONANCE_CARRIERS.values() for n in ns} == set(RESONANCE_ENERGY_EV)
    for species in RESONANT_ABSORBERS:
        where = resonance_wavelengths(species)
        assert where, species
        for nuclide, (e_ev, lam) in where.items():
            assert nuclide in RESONANCE_ENERGY_EV
            assert lam == pytest.approx(NEUTRON_LAMBDA_EV_ANGSTROM / e_ev ** 0.5)
    assert resonance_wavelengths("Al") == {}
    assert set(resonance_wavelengths("Gd")) == {"155Gd", "157Gd"}
    # the constant reproduces the 2200 m/s wavelength this package already uses
    assert NEUTRON_LAMBDA_EV_ANGSTROM / 0.0253 ** 0.5 == pytest.approx(
        SIGMA_ABS_REFERENCE_WAVELENGTH, abs=1e-3)


def test_the_resonant_flag_says_where_the_resonance_is():
    """The message carries the lowest resonance as an energy and a wavelength,
    beside the source's own, and the level is unchanged by it."""
    from rietx.refine import _resonant_absorber_diagnostics  # noqa: PLC0415

    neutron = rx.Instrument.constant_wavelength_neutron(1.7)
    gd = _resonant_absorber_diagnostics(_one_species("Gd"), neutron)[0]
    assert gd.level == "warning"
    assert "155Gd 0.0268 eV = 1.75 A" in gd.message
    assert "157Gd 0.0314 eV = 1.61 A" in gd.message
    assert "wavelength is 1.7 A" in gd.message
    yb = _resonant_absorber_diagnostics(_one_species("Yb"), neutron)[0]
    assert yb.level == "info"
    assert "168Yb 0.597 eV = 0.37 A" in yb.message
