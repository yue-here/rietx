"""Constant-wavelength neutron refinement: the source, the amplitude, the fit.

The tests that matter are the ones that would pass for an X-ray source too if
the radiation were being ignored. So each one below turns on something that is
*different* about neutrons — a Q-independent amplitude, a negative one, K = 1,
an absent dispersion channel — rather than merely checking that a fit runs.
"""

from __future__ import annotations

import math

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
from rietx.schemas.instrument import NeutronSource

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


def test_profile_seed_helper_sets_both_width_terms():
    inst = rx.Instrument.constant_wavelength_neutron(2.0780, fwhm_deg=0.4)
    assert inst.profile.w.value == pytest.approx((0.4 / 2) ** 2)
    assert inst.profile.x.value == pytest.approx(0.4)


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
    k = np.linspace(0.05, 0.45, 12)                # sin(theta)/lambda
    f_xray = f0("Al", k)
    assert f_xray[0] > 1.5 * f_xray[-1]            # real falloff across the range
    # b is one number; the module returns it without a k argument at all
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


def _seeded_width(inst: rx.Instrument, fwhm_deg: float) -> rx.Instrument:
    """Same profile on both instruments, so only the amplitude differs."""
    profile = inst.profile.model_copy(update={
        "w": inst.profile.w.model_copy(update={"value": (fwhm_deg / 2) ** 2}),
        "x": inst.profile.x.model_copy(update={"value": fwhm_deg}),
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
# Three tests, none of which would pass for an X-ray source: the constructor
# accepting a bare float, the estimator declining, and the X-ray control that
# proves the fence is not simply "estimating never happens".
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


def test_the_xray_composition_estimator_declines_on_a_neutron_source():
    """It is the wrong *quantity*, not a coarse estimate, so it must not run.

    ``crystallography.attenuation`` is X-ray photoabsorption; neutron σ_abs
    scales as λ (1/v) where X-ray µ/ρ falls as ~λ⁻³ and has edges.  Writing an
    X-ray µR onto a neutron capillary would be a confidently wrong correction
    applied in silence.
    """
    from rietx.refine import _resolve_specimen_absorption, estimate_mu_r

    struct = rx.Structure(phases=[corundum()])
    inst = rx.Instrument.constant_wavelength_neutron(
        2.0780, capillary_radius_mm=0.4)
    assert inst.geometry.mu_r is None

    assert estimate_mu_r(struct, inst) is None

    source, reason = _resolve_specimen_absorption(struct, inst)
    assert source == "estimated"
    assert reason is not None and "neutron" in reason
    # and it declined rather than guessing: the field is untouched
    assert inst.geometry.mu_r is None


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
