"""λ/n monochromator harmonics: the schema, the two shared facts, the fit.

The fast tests here are the ones that would pass for a source with *any* second
emission line, so each turns on something that is specific to a **harmonic** —
that its wavelength is derived rather than stored, that the reflection list has
to be generated for it and not for the fundamental, that one |F|² still serves
both lines, and that declaring none leaves the model bit-identical.

The real-data case is the **published** histogram: the λ/2 second-order
contribution on the NIST BT-1 Cu(311) monochromator is stated in the paper's
own experimental section — "a Cu(311) monochromator was used, with a constant
wavelength of λ = 1.5402(2) Å and a second-order contribution at λ/2"
(Gaultois et al., *J. Phys.: Condens. Matter*, 2013) — so the contamination is
a cited property of this exact measurement rather than something inferred from
the fit that models it.  Its evidence is **GoF**, never Rwp: the λ/2 peaks are
extra intensity where the model puts none, which GoF sees against σ and Rwp
(dominated by the strong peaks) does not.

The negative control is **synthetic** on purpose.  A second real histogram from
a harmonic-free monochromator would still rest on believing that it is
harmonic-free; a simulated single-wavelength pattern is one where the absence is
a fact of construction.  So the control declares a λ/2 line on a pattern that
provably contains no λ/2 intensity and requires the weight to refine to nothing
— which is the failure mode that would matter, a line that buys χ² from the
background whenever it is offered.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.capabilities import capabilities
from rietx.crystallography.lattice import d_spacings
from rietx.crystallography.structure_factor import (
    compile_phase_sites,
    structure_factors_squared,
)
from rietx.crystallography.symmetry import generate_reflections
from rietx.model.forward import WINDOW_AREA_TOL, compile_model
from rietx.params.vector import ParameterTable
from rietx.refine import HARMONIC_ABSENT_FRAC
from rietx.schemas.instrument import (
    BackgroundChebyshev,
    EmissionLine,
    Harmonic,
    NeutronSource,
    Source,
)
from rietx.schemas.pattern import PatternData

DATA = Path(__file__).parent / "data"

#: The published BT-1 Cu(311) histogram, with the wavelength its instrument file
#: declares.  The paper quotes λ = 1.5402(2) Å as the nominal; 1.54040 is what
#: the ``.inst`` states, and that is what a refinement of this file must use.
#: Committed by the ``refinable-wavelength`` branch, which owns the data row.
CU311 = ("mg090.Cu311.gsas", 1.54040)

CELL = 10.34
LIMITS = (5.0, 155.0)

#: The real-data cases **self-skip** while that branch has not landed, the same
#: way ``test_cross_backend``'s rows skip without their backend: the correction
#: itself is covered by the fast tests and by the synthetic control, so a
#: missing dataset must not read as a failing feature.  The synthetic negative
#: control needs no file and never skips.
needs_cu311 = pytest.mark.skipif(
    not (DATA / CU311[0]).exists(),
    reason=f"{CU311[0]} is committed by the refinable-wavelength branch")


# ------------------------------------------------------------------ fixtures ---
def nd2ru2o7(a: float = CELL) -> rx.Structure:
    """Pyrochlore Nd₂Ru₂O₇, Fd-3m:2 — Nd 16d, Ru 16c, O 48f, O' 8b."""
    P = rx.Parameter
    cell = rx.Cell(a=P(value=a), b=P(value=a), c=P(value=a),
                   alpha=P(value=90.0), beta=P(value=90.0), gamma=P(value=90.0))
    return rx.Structure(phases=[rx.Phase(
        name="Nd2Ru2O7", space_group="Fd-3m:2", cell=cell,
        atoms=[
            rx.Atom(label="Nd", species="Nd", x=P(value=0.5), y=P(value=0.5),
                    z=P(value=0.5), biso=P(value=0.5)),
            rx.Atom(label="Ru", species="Ru", x=P(value=0.0), y=P(value=0.0),
                    z=P(value=0.0), biso=P(value=0.3)),
            rx.Atom(label="O1", species="O", x=P(value=0.33), y=P(value=0.125),
                    z=P(value=0.125), biso=P(value=0.5)),
            rx.Atom(label="O2", species="O", x=P(value=0.375), y=P(value=0.375),
                    z=P(value=0.375), biso=P(value=0.5)),
        ])])


def harmonic_plan() -> rx.RefinementPlan:
    """``mccusker_structural`` plus the harmonic weight, freed **last**.

    The order is the strategy claim, not a convenience: the harmonic weight is a
    small fraction that correlates with the background, so it is freed only once
    the profile and the scale have settled.  No shipped preset frees it — the
    ``instrument.source.lines.*.weight`` glob also matches a Kα2 ratio, so
    adding it to a preset would change what every lab X-ray fit refines.
    """
    base = rx.RefinementPlan.mccusker_structural()
    return rx.RefinementPlan(
        stages=[*base.stages,
                rx.Stage("harmonic", ["instrument.source.lines.*.weight"])])


def fit_pattern(pattern, lam: float, *, harmonics: bool, a: float = CELL):
    inst = rx.Instrument.constant_wavelength_neutron(
        lam, fwhm_deg=0.30, harmonics=harmonics)
    ref = rx.Refinement(structure=nd2ru2o7(a), instrument=inst, history=False)
    res = ref.fit(pattern,
                  plan=harmonic_plan() if harmonics else "mccusker_structural",
                  two_theta_limits=LIMITS)
    return ref, res


def fit(name: str, lam: float, *, harmonics: bool):
    return fit_pattern(rx.read_pattern(str(DATA / name)), lam,
                       harmonics=harmonics)


def clean_neutron_pattern(seed: int = 11):
    """A single-wavelength neutron pattern with **no** λ/2 component in it.

    Built rather than measured, because that is what makes it a control: the
    absence of a harmonic is a fact about how the array was constructed, not a
    claim about a beamline.  Poisson noise so σ is honest and GoF means
    something; the structure and the profile are the same ones the real fit
    uses, so a λ/2 line offered here has exactly the same freedom it has there.
    """
    lam = 1.54040
    struct = nd2ru2o7()
    struct.phases[0].scale.value = 2.0e-3
    inst = rx.Instrument.constant_wavelength_neutron(lam, fwhm_deg=0.30)
    inst.background = BackgroundChebyshev(
        coefficients=[rx.Parameter(value=v) for v in (600.0, -40.0, 12.0)])
    tt = np.arange(LIMITS[0], LIMITS[1] + 1e-9, 0.05)
    blank = PatternData(two_theta=tt.tolist(),
                           intensity=np.zeros_like(tt).tolist())
    model = compile_model(struct, inst, blank, mode="rietveld")
    table = ParameterTable(struct, inst)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(seed).poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist()), lam


# -------------------------------------------------------------- the schema ---
def test_the_order_is_the_callers_and_the_block_is_general_in_n():
    """Which orders pass is a fact about the monochromator's crystal (a Ge(733)
    beam carries no λ/2), so the package picks none (WP-2002, the eighth
    round's item 4)."""
    with pytest.raises(ValueError, match="order"):
        Harmonic()
    with pytest.raises(ValueError, match=r"harmonics=\[3\] for Si\(111\)"):
        rx.Instrument.constant_wavelength_neutron(1.5, harmonics=True)
    # general in n: nothing about the block is specific to the second order
    for n in (2, 3, 4, 7):
        h = Harmonic(order=n)
        assert h.wavelength_factor == pytest.approx(1.0 / n)


def test_harmonic_wavelength_is_derived_never_stored():
    """λ/n is exactly the fundamental divided by n, and cannot drift from it."""
    src = NeutronSource(wavelength=1.54040,
                        harmonics=[Harmonic(order=2), Harmonic(order=3)])
    lams = [line.wavelength.value for line in src.lines]
    assert lams[0] == 1.54040
    assert lams[1] == 1.54040 / 2.0
    assert lams[2] == 1.54040 / 3.0
    # the source has no field holding 0.7702, so no edit can put the two out of
    # step -- changing the fundamental moves the harmonics with it
    src.wavelength = 2.0
    assert [line.wavelength.value for line in src.lines] == [2.0, 1.0, 2.0 / 3.0]
    # ...including when the fundamental is *refined* rather than assigned, which
    # is the case a stored λ/n would silently get wrong
    src.wavelength.value = 3.0
    assert [line.wavelength.value for line in src.lines] == [3.0, 1.5, 1.0]
    # and a derived line is never free: it is λ/n by construction, so a second
    # free handle on it would be a second name for one number
    assert [line.wavelength.vary for line in src.lines] == [False, False, False]


def test_harmonic_weight_is_the_stored_parameter_by_reference():
    """The write-back path reaches the declaration, or a refined value is lost.

    ``ParameterTable.write_back`` walks ``instrument.source.lines.i.weight``,
    and on a neutron source those lines are *derived*.  A copied Parameter would
    make every refinement silently discard the fitted harmonic weight.
    """
    src = NeutronSource(wavelength=1.5, harmonics=[Harmonic(order=2)])
    assert src.lines[1].weight is src.harmonics[0].weight
    src.lines[1].weight.value = 0.0731
    assert src.harmonics[0].weight.value == pytest.approx(0.0731)


def test_the_fundamental_stays_structurally_locked():
    """Line 0's weight is degenerate with the phase scales, harmonic or not."""
    inst = rx.Instrument.constant_wavelength_neutron(1.5, harmonics=[2])
    table = ParameterTable(rx.Structure(phases=nd2ru2o7().phases), inst)
    freed = table.set_vary(["instrument.source.lines.*.weight"], True)
    assert "instrument.source.lines.0.weight" not in freed
    assert "instrument.source.lines.1.weight" in freed


def test_harmonic_weight_seeds_fixed_and_low():
    """A correction must not open at the answer it is meant to measure."""
    h = Harmonic(order=2)
    assert not h.weight.vary          # freed by a stage, never by declaration
    assert h.weight.min == 0.0        # zero is the off state and is reachable
    assert h.weight.max == math.inf   # no ceiling since WP-2002's B9 ruling
    # far below every reported value, so the fit has to travel to reach one
    assert h.weight.value < 0.02


# -------------------------------------------------------------- refusals ---
@pytest.mark.parametrize("order", [1, 0, -2])
def test_order_below_two_is_refused(order):
    """n = 1 *is* the fundamental; n <= 0 is not a diffraction order."""
    with pytest.raises(ValueError):
        Harmonic(order=order)


def test_duplicate_orders_are_refused_naming_the_flat_direction():
    with pytest.raises(ValueError, match="duplicate harmonic order n = 2"):
        NeutronSource(wavelength=1.5,
                      harmonics=[Harmonic(order=2), Harmonic(order=2)])


def test_xray_harmonics_are_refused_naming_dispersion_and_the_way_round():
    """The refusal has to say *why*, or it is pydantic's 'extra inputs'."""
    with pytest.raises(ValueError) as exc:
        Source(lines=[EmissionLine(wavelength=1.5406)], harmonics=[Harmonic(order=2)])
    msg = str(exc.value)
    assert "f'" in msg                       # names the shared quantity
    assert "1 % of Z" in msg                 # names the guard that would fire
    assert "neutron source" in msg           # names the supported route
    assert "dispersion = None" in msg        # names the X-ray route that works


def test_the_xray_escape_route_the_refusal_names_actually_works():
    """A λ/2 line declared by hand, with f real, is admissible and exact.

    The refusal points at this; if it did not work the message would be wrong.
    With ``dispersion=None`` there is nothing wavelength-dependent left in the
    structure factor, so one |F|² serves both lines exactly.
    """
    src = Source(lines=[EmissionLine(wavelength=1.5406),
                        EmissionLine(wavelength=1.5406 / 2)],
                 dispersion=None)
    assert [line.wavelength.value for line in src.lines] == [1.5406, 0.7703]


def test_capabilities_reports_support_from_the_same_authority():
    """The arm cannot claim a support the validator denies."""
    caps = capabilities()
    by_kind = {r.kind: r for r in caps.radiations}
    assert by_kind["neutron_cw"].harmonic_contamination is True
    assert by_kind["xray_cw"].harmonic_contamination is False
    # both read Source.harmonics_supported, which is what makes them agree
    assert NeutronSource.harmonics_supported is True
    assert Source.harmonics_supported is False
    # a source that can carry λ/n is no longer a one-line source
    assert by_kind["neutron_cw"].max_emission_lines is None


# ------------------------------------------------- off is off, exactly ---
def test_declaring_no_harmonic_is_byte_identical():
    """The ``restraints``/``microstrain`` idiom: absent means untouched."""
    plain = rx.Instrument.constant_wavelength_neutron(1.54040, fwhm_deg=0.30)
    explicit = rx.Instrument.constant_wavelength_neutron(
        1.54040, fwhm_deg=0.30, harmonics=False)
    assert plain.model_dump_json() == explicit.model_dump_json()
    assert plain.source.harmonics == []
    assert len(plain.source.lines) == 1
    # and it round-trips: an old document with no harmonics key still loads
    doc = plain.model_dump()
    doc["source"].pop("harmonics")
    again = rx.Instrument.model_validate(doc)
    assert again.source.harmonics == []
    assert again.model_dump_json() == plain.model_dump_json()


@needs_cu311
def test_no_harmonic_leaves_the_calculated_pattern_bit_identical():
    """Empty harmonics must not perturb a single double of the forward model."""
    name, lam = CU311
    pattern = rx.read_pattern(str(DATA / name))
    struct = nd2ru2o7()
    ys = []
    for explicit in (False, True):
        inst = rx.Instrument.constant_wavelength_neutron(lam, fwhm_deg=0.30)
        if explicit:
            inst.source.harmonics = []      # declared empty, not merely absent
        model = compile_model(struct, inst, pattern, two_theta_limits=LIMITS)
        table = ParameterTable(struct, inst)
        ys.append(model.evaluate(table.decode(table.x0())))
        assert model.harmonic_orders == {}
    assert np.array_equal(ys[0], ys[1])


# --------------------------------------- the two facts the design rests on ---
@needs_cu311
def test_the_reflection_list_is_generated_for_the_shortest_wavelength():
    """λ/2 reaches reflections the fundamental cannot, and must not lose them.

    This is the fact most likely to be quietly wrong: with the list generated
    at the primary λ the harmonic's high-angle reflections are silently missing,
    and the correction would look like one that does not help.
    """
    cell = (CELL,) * 3 + (90.0,) * 3
    n_fund = len(generate_reflections("Fd-3m:2", cell, 1.54040,
                                     two_theta_max=155.0, two_theta_min=5.0))
    n_harm = len(generate_reflections("Fd-3m:2", cell, 1.54040 / 2,
                                     two_theta_max=155.0, two_theta_min=5.0))
    assert n_harm > 5 * n_fund, "λ/2 must reach far more reflections"

    pattern = rx.read_pattern(str(DATA / CU311[0]))
    struct = nd2ru2o7()
    inst = rx.Instrument.constant_wavelength_neutron(
        CU311[1], fwhm_deg=0.30, harmonics=[2])
    # the declared stages' windows, which generate over the limits alone; a
    # compile at the closing windows reaches past them by its widest window
    # (WP-2002)
    model = compile_model(struct, inst, pattern, two_theta_limits=LIMITS,
                          window_area_tol=WINDOW_AREA_TOL)
    # the compiled list is the λ/2 list, not the fundamental's
    assert len(model.phases[0].reflections) == n_harm
    assert model.harmonic_orders == {1: 2}


def test_one_squared_structure_factor_serves_both_lines():
    """|F|² is a function of the reflection, never of which λ diffracts it.

    It looks wrong at first glance — the harmonic's λ is half the primary's —
    and it is right: the form factors and the Debye-Waller factor are evaluated
    at sinθ/λ = 1/2d, so the argument is d.  Asserted on the *signature* and on
    the values, because a future λ argument would be the regression.
    """
    assert "lam" not in structure_factors_squared.__code__.co_varnames
    assert "wavelength" not in structure_factors_squared.__code__.co_varnames

    cell = (CELL,) * 3 + (90.0,) * 3
    phase = nd2ru2o7().phases[0]
    sites = compile_phase_sites(phase, neutron=True)
    refl = generate_reflections("Fd-3m:2", cell, 1.54040 / 2,
                                two_theta_max=155.0, two_theta_min=5.0)
    d = d_spacings(refl.hkl, *cell)
    xyz = np.array([[a.x.value, a.y.value, a.z.value] for a in phase.atoms])
    occ = np.array([a.occ.value for a in phase.atoms])
    biso = np.array([a.biso.value for a in phase.atoms])
    f2 = structure_factors_squared(refl.hkl, d, sites, xyz, occ, biso, cell)
    assert np.all(f2 >= 0.0)
    # the same call with the same reflections is the same answer whatever λ the
    # caller had in mind -- there is nowhere to put one
    again = structure_factors_squared(refl.hkl, d, sites, xyz, occ, biso, cell)
    assert np.array_equal(f2, again)


def test_the_harmonic_peaks_sit_below_the_fundamentals():
    """λ/n from one hkl lands at *lower* 2θ, which is the whole signature."""
    cell = (CELL,) * 3 + (90.0,) * 3
    refl = generate_reflections("Fd-3m:2", cell, 1.54040 / 2,
                                two_theta_max=155.0, two_theta_min=5.0)
    tt_fund = refl.two_theta(cell, 1.54040)
    tt_harm = refl.two_theta(cell, 1.54040 / 2)
    both = np.isfinite(tt_fund) & np.isfinite(tt_harm)
    assert both.any()
    assert np.all(tt_harm[both] < tt_fund[both])
    # and the ratio is the Bragg condition, not an offset: sinθ scales with λ
    s_fund = np.sin(np.radians(tt_fund[both] / 2))
    s_harm = np.sin(np.radians(tt_harm[both] / 2))
    assert np.allclose(s_harm / s_fund, 0.5, rtol=1e-12)


def test_a_monochromators_own_extinction_decides_whether_a_harmonic_exists():
    """Whether λ/n exists at all is arithmetic on the monochromator's structure.

    Not incidental to this correction — it is what tells a user whether to
    declare a harmonic before ever fitting one, and it is why the refusal in
    :class:`~rietx.schemas.instrument.Harmonic` is worded "whose reflection is
    not extinct".  Copper is face-centred cubic with one atom per lattice point
    and no cancellation, so **Cu(311) doubles to the fully allowed (622)** and
    the second order passes.  A diamond-structure crystal cut on all-odd indices
    cancels its own second order, because the doubled indices are all even and
    1 + exp[2πi(h+k+l)/4] vanishes unless h+k+l ≡ 0 (mod 4).
    """
    def diamond(h, k, l):            # noqa: E741 - hkl is the domain spelling
        if len({h % 2, k % 2, l % 2}) != 1:
            return 0.0               # F-centring kills mixed parity
        return abs(1.0 + math.e ** (2j * math.pi * (h + k + l) / 4.0))

    def fcc(h, k, l):                # noqa: E741
        return 0.0 if len({h % 2, k % 2, l % 2}) != 1 else 4.0

    # the monochromator this correction is validated against passes its own
    # second order, which is why the histogram is contaminated
    assert fcc(3, 1, 1) > 0.0                       # Cu(311) reflects
    assert fcc(6, 2, 2) > 0.0                       # so does (622) = 2x(311)
    # an all-odd diamond cut does not, for any all-odd cut
    for h, k, l in ((1, 1, 1), (3, 1, 1), (7, 3, 3), (5, 3, 1)):  # noqa: E741
        assert diamond(h, k, l) > 0.0
        assert diamond(2 * h, 2 * k, 2 * l) < 1e-12


# ------------------------------------------------------------- acceptance ---
@needs_cu311
@pytest.mark.slow
@pytest.mark.xdist_group("harmonics-cu311")
class TestPublishedCu311Histogram:
    """The published BT-1 Cu(311) histogram, fitted with and without λ/2.

    The evidence is **GoF**, not Rwp — and here that is not merely a house rule
    but the only reading that works: the λ/2 peaks are intensity in places the
    uncorrected model puts none, which GoF measures against σ while Rwp,
    dominated by the strong peaks, barely notices.

    The contamination itself is *cited*, not inferred: the paper's experimental
    section states that this monochromator delivered "a second-order
    contribution at λ/2".  So this is a test of whether the model recovers a
    documented feature of the beam, rather than an argument that the feature is
    there because modelling it helps.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def fits():
        return {"off": fit(*CU311, harmonics=False),
                "on": fit(*CU311, harmonics=[2])}

    def test_the_uncorrected_fit_has_the_gof_of_a_missing_component(self, fits):
        """GoF well above 1 while Rwp looks respectable — the signature."""
        _, off = fits["off"]
        assert off.statistics.gof == pytest.approx(1.657, abs=0.02)
        assert off.statistics.rwp == pytest.approx(0.0628, abs=0.002)

    def test_the_harmonic_improves_the_gof(self, fits):
        _, off = fits["off"]
        _, on = fits["on"]
        assert on.statistics.gof < off.statistics.gof
        assert on.statistics.gof == pytest.approx(1.472, abs=0.02)

    def test_the_refined_fraction_is_a_few_per_cent_with_an_esd(self, fits):
        ref, res = fits["on"]
        weight = ref.instrument.source.harmonics[0].weight
        row = next(r for r in res.parameters
                   if r.path == "instrument.source.lines.1.weight")
        # the harmonic's λ is exactly half, never a fitted second wavelength
        assert ref.instrument.source.lines[1].wavelength.value == \
            pytest.approx(CU311[1] / 2)
        assert 100 * weight.value == pytest.approx(1.05, abs=0.15)
        # measured, and resolved from zero by ~5.6σ
        assert row.stderr is not None
        assert 100 * row.stderr == pytest.approx(0.19, abs=0.08)
        assert weight.value > 3 * row.stderr
        assert row.at_bound is False           # parked on neither bound
        assert "HARMONIC_FRACTION" in {d.code for d in res.diagnostics}

    def test_the_displacement_parameters_all_fall(self, fits):
        """The accuracy statement, and it is invisible in Rwp.

        Unmodelled λ/2 intensity has to be absorbed by whatever can raise the
        calculated pattern where the model is short, and the displacement
        parameters are the cheapest such direction — lowering every Biso raises
        the high-angle intensity.  Once the harmonic carries that intensity
        instead, the bias is released, so every Biso should fall.  A correction
        that only moved Rwp would leave this untouched.
        """
        off = [a.biso.value for a in fits["off"][0].structure.phases[0].atoms]
        on = [a.biso.value for a in fits["on"][0].structure.phases[0].atoms]
        assert all(b_on < b_off for b_off, b_on in zip(off, on)), \
            f"Biso did not fall: {off} -> {on}"
        # and by an amount that matters against a typical neutron Biso esd
        assert max(b_off - b_on for b_off, b_on in zip(off, on)) > 0.03

    def test_the_positions_are_untouched_by_the_declaration_alone(self, fits):
        """A harmonic changes intensities, so the cell must not chase it far."""
        a_off = fits["off"][0].structure.phases[0].cell.a.value
        a_on = fits["on"][0].structure.phases[0].cell.a.value
        assert abs(a_on - a_off) < 1e-3

    def test_the_half_wavelength_image_keeps_the_low_angle_boundary(self, fits):
        """``LOW_ANGLE_UNMODELLED``'s boundary is judged per reflection over
        every line image (WP-1458): the λ/2 (111) at 7.36° carries 0.095σ on
        its own, but its primary carries 2.86σ, so it still bounds the region
        at 6.76° and the warning keeps firing.  Judged image by image it was
        dropped and the region's ratio fell from 5.92 to 2.66."""
        _, on = fits["on"]
        found = [d for d in on.diagnostics if d.code == "LOW_ANGLE_UNMODELLED"]
        assert len(found) == 1
        assert "(7.36° − 2×FWHM = 6.76°)" in found[0].message


@pytest.mark.slow
@pytest.mark.xdist_group("harmonics-synthetic")
class TestSyntheticNegativeControl:
    """A λ/2 line offered a pattern that provably has none must take nothing.

    This matters more than the positive result.  A correction with a free
    parameter and a plausible story will usually improve χ² somewhere; the
    question is whether it declines to when there is nothing there.  Built
    rather than measured so the absence is a property of the array, not a claim
    about a beamline.
    """

    @staticmethod
    @pytest.fixture(scope="class")
    def clean():
        pattern, lam = clean_neutron_pattern()
        return {"pattern": pattern, "lam": lam,
                "off": fit_pattern(pattern, lam, harmonics=False),
                "on": fit_pattern(pattern, lam, harmonics=[2])}

    def test_the_harmonic_refines_to_nothing(self, clean):
        ref, res = clean["on"]
        weight = ref.instrument.source.harmonics[0].weight
        assert weight.value < HARMONIC_ABSENT_FRAC
        codes = {d.code for d in res.diagnostics}
        assert "HARMONIC_ABSENT" in codes
        assert "HARMONIC_FRACTION" not in codes

    def test_offering_the_line_costs_the_clean_fit_nothing(self, clean):
        """No χ² bought from the background by a line with nothing to fit."""
        _, off = clean["off"]
        _, on = clean["on"]
        assert on.statistics.gof == pytest.approx(off.statistics.gof, abs=0.02)

    def test_a_held_weight_is_reported_as_an_assumption(self, clean):
        """Declared but never freed: the value is the caller's, not measured."""
        inst = rx.Instrument.constant_wavelength_neutron(
            clean["lam"], fwhm_deg=0.30, harmonics=[2])
        ref = rx.Refinement(structure=nd2ru2o7(), instrument=inst, history=False)
        res = ref.fit(clean["pattern"], plan="mccusker_structural",
                      two_theta_limits=LIMITS)
        codes = {d.code for d in res.diagnostics}
        assert "HARMONIC_HELD" in codes
        assert "HARMONIC_FRACTION" not in codes
        assert "HARMONIC_ABSENT" not in codes


def test_a_derived_harmonic_follows_a_refining_fundamental():
    """The residual's λ/n, not the schema's — a different question.

    ``test_harmonic_wavelength_is_derived_never_stored`` shows the *schema*
    rebuilds λ/n from ``self.wavelength``.  The forward model reads λ from θ
    per line, and a derived harmonic deliberately has **no θ row** — freeing
    one would be a second name for one number.  So ``line_lambdas`` could only
    ever hand back the frozen compile-time λ/n, which goes stale the instant
    the fundamental refines.  A stored λ/n and that code differ only in *when*
    they go stale.

    Measured before the fix, at +0.2 % on the fundamental: the pair read
    (1.5404, 0.7702) where tracking gives (1.5434808, 0.7717404).  At the
    +258 ppm the acceptance suite finds on this instrument, a stale λ/2
    misplaces the harmonic peaks by up to 0.11° at 2θ = 150° — about a third of
    the 0.30° FWHM the seed assumes — and nothing raised, because the Jacobian
    column agreed with the residual.
    """
    lam = 1.5404
    structure = nd2ru2o7()
    ins = rx.Instrument.constant_wavelength_neutron(
        lam, fwhm_deg=0.30, harmonics=[2])
    tt = np.arange(*LIMITS, 0.05)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.ones_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")

    assert model.harmonic_orders == {1: 2}
    # with nothing in θ, both lines are the compile-time values
    assert model.line_lambdas({}) == pytest.approx([lam, lam / 2.0])

    moved = lam * 1.002
    got = model.line_lambdas(
        {"instrument.source.lines.0.wavelength": moved})
    assert got[0] == pytest.approx(moved)
    assert got[1] == pytest.approx(moved / 2.0), (
        "the derived harmonic did not follow the fundamental — it is reading "
        "its frozen compile-time λ/n")
    # and the ratio is exact, not merely close: λ/n is a construction
    assert got[0] / got[1] == pytest.approx(2.0, rel=1e-15)
