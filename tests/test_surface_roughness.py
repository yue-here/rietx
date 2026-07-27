"""Surface roughness (WP-0502): Suortti (1972) and Pitschke et al. (1993).

A rough or loosely-packed flat specimen depresses diffracted intensity at low
2theta.  Left uncorrected the depression is absorbed by Biso/ADPs (driving them
toward — and past — zero), by the phase scales and by a flexible background, so
every test here is written twice over: once for the physics, once for the
degeneracy that physics creates.
"""

import math
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

from pxrdref import Instrument, Parameter
from pxrdref.model.corrections import (
    surface_roughness_pitschke,
    surface_roughness_suortti,
)
from pxrdref.params.vector import ParameterTable
from pxrdref.schemas import Geometry, RoughnessPitschke, RoughnessSuortti

TT = np.arange(5.0, 160.0, 0.5)

# -- schema ------------------------------------------------------------------


def test_roughness_blocks_default_to_the_identity():
    """Attaching a block must change nothing until it is deliberately refined."""
    s = RoughnessSuortti()
    assert s.kind == "suortti"
    assert s.b.value == 0.0 and s.b.vary is False
    assert s.b.min == 0.0 and s.b.transform == "softplus"
    # a is strictly interior on purpose: at b = 0 the gradient
    # dR/db = (1-a)(1 - 1/sin(theta)) vanishes identically when a = 1, so a
    # default of 1.0 would make the parameter unable to lift off.
    assert 0.0 < s.a.value < 1.0
    assert s.a.transform == "identity"

    p = RoughnessPitschke()
    assert p.kind == "pitschke"
    assert p.c.value == 0.0 and p.c.vary is False
    assert p.c.min == 0.0 and p.c.transform == "softplus"
    assert 0.0 < p.tau.value < p.tau.max  # interior, same lift-off reason
    assert p.tau.transform == "identity"


def test_roughness_bounds_encode_the_published_regimes():
    # tau < 0.3 is Pitschke's own estimate of the physical upper limit for real
    # powders (its fitted values span 0.005-0.12); c < 4 keeps R > 0 inside the
    # valid range, since max u(1-u) = 1/4.
    p = RoughnessPitschke()
    assert p.tau.max == pytest.approx(0.3)
    assert p.c.max == pytest.approx(4.0)
    # a is a fraction; b is a positive optical depth
    s = RoughnessSuortti()
    assert (s.a.min, s.a.max) == (0.0, 1.0)
    assert s.b.min == 0.0


def test_roughness_requires_a_flat_specimen():
    """A spinning capillary has no illuminated flat surface to roughen."""
    with pytest.raises(ValidationError) as err:
        Geometry(kind="debye_scherrer", surface_roughness=RoughnessSuortti())
    assert "bragg_brentano" in str(err.value)

    # ... and the Bragg-Brentano case is accepted
    g = Geometry(kind="bragg_brentano", goniometer_radius_mm=217.5,
                 surface_roughness=RoughnessSuortti())
    assert g.surface_roughness is not None


def test_roughness_json_round_trip_selects_the_right_kind():
    """The union must survive JSON without collapsing to the wrong model."""
    for block in (RoughnessSuortti(), RoughnessPitschke()):
        ins = Instrument.bragg_brentano()
        ins.geometry.surface_roughness = block
        back = Instrument.model_validate_json(ins.model_dump_json())
        assert back == ins
        assert type(back.geometry.surface_roughness) is type(block)


def test_instrument_presets_carry_no_roughness_block():
    """Off by default: existing refinements must be bit-identical to before."""
    assert Instrument.bragg_brentano().geometry.surface_roughness is None
    assert Instrument.debye_scherrer(wavelength=1.5406).geometry.surface_roughness is None


def test_the_two_models_are_exactly_the_identity_when_off():
    """Not 'approximately 1' — bit-exactly 1.0, so the off state needs no branch.

    Suortti: at b = 0 numerator and denominator reduce to the *identical*
    expression a + (1-a)*1.0, whatever a is.
    Pitschke: at c = 0 the whole correction term is multiplied by zero.
    """
    for a in (0.0, 0.1, 0.5, 0.9, 1.0):
        for two_theta in (5.0, 37.0, 91.0, 150.0):
            s = math.sin(math.radians(two_theta / 2.0))
            r = (a + (1.0 - a) * math.exp(-0.0 / s)) / (a + (1.0 - a) * math.exp(-0.0))
            assert r == 1.0
    for tau in (0.0, 0.05, 0.3):
        for two_theta in (5.0, 37.0, 91.0, 150.0):
            s = math.sin(math.radians(two_theta / 2.0))
            u = tau / s
            assert 1.0 - 0.0 * u * (1.0 - u) == 1.0


# -- physics: the correction functions ---------------------------------------


def test_suortti_is_bit_exactly_one_when_off():
    """No tolerance: the off state must not perturb a single bit of y_calc."""
    for a in (0.0, 0.1, 0.5, 0.9, 1.0):
        r = surface_roughness_suortti(TT, a, 0.0)
        assert np.array_equal(r, np.ones_like(TT))


def test_pitschke_is_bit_exactly_one_when_off():
    for tau in (0.0, 0.05, 0.3):
        assert np.array_equal(surface_roughness_pitschke(TT, 0.0, tau),
                              np.ones_like(TT))
    for c in (0.0, 1.0, 3.9):
        assert np.array_equal(surface_roughness_pitschke(TT, c, 0.0),
                              np.ones_like(TT))


def test_suortti_only_ever_depresses_and_rises_with_angle():
    """0 < R <= 1 and monotone increasing in theta, for every (a, b) in range.

    Both follow from sin(theta) <= 1 => exp(-b/sin) <= exp(-b): the numerator
    can never exceed the theta=90 denominator, and it grows as sin(theta) does.
    A correction that could *amplify* would be free to imitate a scale factor.
    """
    for a in (0.0, 0.2, 0.5, 0.8, 0.99):
        for b in (0.05, 0.5, 2.0, 9.0):
            r = surface_roughness_suortti(TT, a, b)
            assert np.all(r > 0.0)
            assert np.all(r <= 1.0 + 1e-15)
            assert np.all(np.diff(r) >= -1e-15), f"not monotone at a={a}, b={b}"


def test_one_minus_a_bounds_the_depression():
    """`a` is the depth knob: no (b, theta) may push the depression past 1 - a."""
    for a in (0.1, 0.5, 0.9):
        worst = min(surface_roughness_suortti(TT, a, b).min()
                    for b in np.geomspace(1e-4, 5.0, 400))
        assert 1.0 - worst <= 1.0 - a + 1e-12
        # and the bound is tight — it is approached, not merely respected
        # (measured on this grid: 97% of 1-a at a=0.1, 89% at 0.5, 84% at 0.9)
        assert 1.0 - worst > 0.8 * (1.0 - a)


def test_b_is_bimodal_both_limits_are_the_identity():
    """b -> 0 and b -> infinity both switch the correction off.

    b sets *where in angle* the transition falls, not how deep the depression
    goes: at b -> 0 the depleted layer is transparent, and at b -> infinity it
    is opaque at every angle, so the theta=90 normalisation divides the
    angular dependence back out.  The correction therefore peaks at
    intermediate b, and any given depression is reproducible by two b values.

    This is a genuine refinement hazard (a flat-gradient dead zone the
    optimiser can wander into), which is why the staged plan seeds b near the
    sensitive region and ROUGHNESS_UNCONSTRAINED is defined on the modelled
    depression rather than on b itself.
    """
    a = 0.5
    depth = np.array([1.0 - surface_roughness_suortti(TT, a, b).min()
                      for b in np.geomspace(1e-6, 50.0, 3000)])
    assert depth[0] < 1e-4, "b -> 0 must be the identity"
    assert depth[-1] < 1e-4, "b -> infinity must be the identity too"
    peak = depth.argmax()
    assert 0 < peak < len(depth) - 1
    assert depth[peak] > 0.4
    # strictly unimodal: rises to the peak, falls after it
    assert np.all(np.diff(depth[:peak + 1]) >= -1e-12)
    assert np.all(np.diff(depth[peak:]) <= 1e-12)


def test_the_sensitive_b_moves_out_as_the_lowest_fitted_angle_rises():
    """Data starting at 20 deg is sensitive to a different b than data from 5.

    The staged-plan seed and the ROUGHNESS_UNCONSTRAINED threshold both depend
    on this, so pin it.
    """
    grid = np.geomspace(1e-3, 5.0, 4000)

    def peak_b(two_theta_min):
        tt = np.arange(two_theta_min, 160.0, 0.5)
        depth = [1.0 - surface_roughness_suortti(tt, 0.5, b).min() for b in grid]
        return grid[int(np.argmax(depth))]

    assert peak_b(5.0) < peak_b(15.0) < peak_b(20.3)
    assert 0.1 < peak_b(5.0) < 0.3
    assert 0.3 < peak_b(20.3) < 0.7


def test_suortti_matches_an_independent_transcription_of_the_published_form():
    """Scalar transcription of Suortti (1972) as GSAS-II SurfaceRough writes it.

    Written out here from the reference implementation's own algebra so the
    vectorised, xp-routed version cannot drift from the published formula.
    """
    def reference(two_theta_deg: float, sra: float, srb: float) -> float:
        sth = math.sin(math.radians(two_theta_deg / 2.0))
        t1 = math.exp(-srb / sth)
        t2 = sra + (1.0 - sra) * math.exp(-srb)
        return (sra + (1.0 - sra) * t1) / t2

    for a, b in ((0.37, 0.85), (0.5, 0.1), (0.05, 4.0), (0.9, 2.5)):
        got = surface_roughness_suortti(TT, a, b)
        want = np.array([reference(t, a, b) for t in TT])
        assert got == pytest.approx(want, abs=1e-10, rel=1e-10)
    # and the test data actually spans a meaningful depression, or it would
    # pass just as well against a stub returning ones
    assert 1.0 - surface_roughness_suortti(TT, 0.37, 0.85)[0] > 0.3


def test_pitschke_form_matches_the_paper_and_reduces_to_suorttis_shape():
    """Eq (17) with P0 factored out, plus the paper's own quotation of Suortti.

    Pitschke p. 78 quotes Suortti as P_s = C1*[1 - exp(-C2/sin th)].  Feeding
    that into (1 - P) and normalising at theta = 90 reproduces our Suortti
    routine with C1 = 1 - a and C2 = b — two independent sources for one
    formula.  Agreement is to rounding, not bit-for-bit: the two ways of
    writing it group the float operations differently.
    """
    for c, tau in ((1.8, 0.11), (3.75, 0.073), (5.0, 0.003)):
        sth = np.sin(np.radians(TT / 2.0))
        u = tau / sth
        want = 1.0 - c * u * (1.0 - u)
        assert surface_roughness_pitschke(TT, c, tau) == pytest.approx(want)

    for a, b in ((0.37, 0.85), (0.6, 1.4)):
        sth = np.sin(np.radians(TT / 2.0))
        c1, c2 = 1.0 - a, b
        quoted = ((1.0 - c1 * (1.0 - np.exp(-c2 / sth)))
                  / (1.0 - c1 * (1.0 - np.exp(-c2))))
        assert surface_roughness_suortti(TT, a, b) == pytest.approx(
            quoted, rel=1e-14, abs=1e-15)


def test_pitschke_turns_over_and_then_amplifies_outside_its_regime():
    """Pin the known breakdown so the fence that guards it cannot be dropped.

    u(1-u) peaks at u = 1/2 and returns to 0 at u = 1, so R is monotone only
    while sin(theta) >= 2*tau, and *rises above 1* past sin(theta) = tau (the
    paper's Eq 18).  This is not smoothed away: clamping would kink the
    Jacobian, so the model is evaluated unconditionally and the refinement
    raises ROUGHNESS_OUTSIDE_REGIME instead.
    """
    tau, c = 0.2, 1.0
    tt = np.linspace(2.0, 120.0, 4000)
    r = surface_roughness_pitschke(tt, c, tau)
    sth = np.sin(np.radians(tt / 2.0))

    monotone = sth >= 2.0 * tau
    assert np.all(np.diff(r[monotone]) >= -1e-12)
    # inside the paper's validity range the correction depresses ...
    valid = sth >= tau
    assert np.all(r[valid] <= 1.0 + 1e-12)
    # ... and outside it, it amplifies — the thing the fence exists to catch
    assert np.any(r[sth < tau] > 1.0)
    # the turnover is real: somewhere between tau and 2*tau, R stops rising
    band = (sth > tau) & (sth < 2.0 * tau)
    assert band.sum() > 10 and np.any(np.diff(r[band]) < 0.0)


def test_pitschke_stays_positive_inside_its_bounds():
    """c <= 4 is what keeps R > 0 in the valid range, since max u(1-u) = 1/4."""
    for tau in (0.01, 0.1, 0.3):
        sth = np.sin(np.radians(TT / 2.0))
        r = surface_roughness_pitschke(TT, 4.0, tau)
        assert np.all(r[sth >= tau] >= 0.0)


# -- parameter wiring --------------------------------------------------------


def _bb(rough=None) -> Instrument:
    ins = Instrument.bragg_brentano()
    ins.geometry.surface_roughness = rough
    return ins


def test_no_block_means_no_table_entries():
    """Opt-in must be invisible: the table is identical to the pre-WP one."""
    from tests.test_schemas import make_lab6
    table = ParameterTable(make_lab6(), _bb())
    assert not [p for p in table._paths if "surface_roughness" in p]


def test_block_registers_its_own_field_names():
    from tests.test_schemas import make_lab6
    for block, names in ((RoughnessSuortti(), ("a", "b")),
                         (RoughnessPitschke(), ("c", "tau"))):
        table = ParameterTable(make_lab6(), _bb(block))
        got = [p for p in table._paths if "surface_roughness" in p]
        assert got == [f"instrument.geometry.surface_roughness.{n}" for n in names]


def test_one_glob_frees_whichever_model_is_attached():
    """Stage plans must not need to know which `kind` the user chose."""
    from tests.test_schemas import make_lab6
    for block in (RoughnessSuortti(), RoughnessPitschke()):
        table = ParameterTable(make_lab6(), _bb(block))
        table.set_vary(["instrument.geometry.surface_roughness.*"], True)
        freed = [p for p in table.free_paths if "surface_roughness" in p]
        assert len(freed) == 2, f"{type(block).__name__}: freed {freed}"


def test_refined_values_survive_the_write_back():
    """Without apply_to_models the value vanishes at the next stage's recompile."""
    from tests.test_schemas import make_lab6
    structure, ins = make_lab6(), _bb(RoughnessSuortti())
    table = ParameterTable(structure, ins)
    for e in table.entries:
        if e.path.endswith("surface_roughness.b"):
            e.value = 0.42
        if e.path.endswith("surface_roughness.a"):
            e.value = 0.31
    table.apply_to_models(structure, ins)
    assert ins.geometry.surface_roughness.b.value == pytest.approx(0.42)
    assert ins.geometry.surface_roughness.a.value == pytest.approx(0.31)


def test_roughness_rides_the_analytic_peak_chain_not_whole_model_fd():
    """A missed prefix here is a silent slowdown, not a failure — so pin it."""
    from pxrdref.model.forward import CompiledModel
    for name in ("a", "b", "c", "tau"):
        path = f"instrument.geometry.surface_roughness.{name}"
        assert CompiledModel.scalar_chain_supported(None, path) is True


def test_roughness_is_per_histogram_by_default():
    """Each histogram is a separate mount, so packing is not a shared property."""
    from pxrdref.params.multi import SharingMap
    sharing = SharingMap()
    for name in ("a", "b", "c", "tau"):
        path = f"instrument.geometry.surface_roughness.{name}"
        assert sharing.is_shared(path) is False


def test_calibration_profiles_never_carry_roughness(tmp_path):
    """Roughness describes how *this* specimen was packed, not the goniometer.

    Saving it into an instrument profile would silently pre-bias the ADPs of
    every later sample measured on that diffractometer.
    """
    from pxrdref.io.instrument_profile import (
        load_instrument_profile,
        save_instrument_profile,
    )
    ins = _bb(RoughnessSuortti(b=Parameter(value=0.4, min=0.0, max=5.0,
                                           transform="softplus")))
    path = tmp_path / "profile.json"
    save_instrument_profile(ins, path)
    assert ins.geometry.surface_roughness is not None, "must not mutate the caller"
    assert load_instrument_profile(path).geometry.surface_roughness is None


# -- forward model -----------------------------------------------------------


def _lab6_bb(rough=None, *, mode="rietveld", two_theta_min=8.0):
    """Compiled LaB6 on a lab Bragg-Brentano instrument, reaching low angle."""
    from pxrdref import PatternData
    from pxrdref.model.forward import compile_model
    from tests.test_schemas import make_lab6

    structure = make_lab6()
    structure.phases[0].scale.value = 5e-3
    ins = _bb(rough)
    ins.profile.w.value = 1e-2
    tt = np.arange(two_theta_min, 120.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode=mode)
    table = ParameterTable(structure, ins)
    return model, table.decode(table.x0())


def test_forward_off_state_is_bit_identical_to_no_block_at_all():
    """The regression that matters most: attaching a block must cost nothing."""
    plain, v_plain = _lab6_bb(None)
    for block in (RoughnessSuortti(), RoughnessPitschke()):
        withb, v_with = _lab6_bb(block)
        for il in range(len(plain.line_wavelengths)):
            assert np.array_equal(plain.phase_peaks(0, v_plain)[il][3],
                                  withb.phase_peaks(0, v_with)[il][3])
        assert np.array_equal(plain.evaluate(v_plain), withb.evaluate(v_with))


def test_forward_roughness_depresses_low_angle_intensity_only():
    """The signature that makes it identifiable — and confusable with an ADP."""
    off, v_off = _lab6_bb(RoughnessSuortti())
    on, v_on = _lab6_bb(RoughnessSuortti(
        a=Parameter(value=0.4, min=0.0, max=1.0),
        b=Parameter(value=0.3, min=0.0, max=5.0, transform="softplus")))

    i_off = off.phase_peaks(0, v_off)[0][3]
    i_on = on.phase_peaks(0, v_on)[0][3]
    pos = off.phase_peaks(0, v_off)[0][0]
    ratio = i_on / np.where(i_off > 0, i_off, 1.0)

    assert np.all(ratio <= 1.0 + 1e-12), "roughness must never amplify"
    lo, hi = pos < 30.0, pos > 90.0
    assert lo.any() and hi.any()
    assert ratio[lo].min() < 0.85, "the low-angle depression should be obvious"
    assert ratio[hi].min() > ratio[lo].max(), "and must fade with angle"


def test_roughness_is_ignored_outside_rietveld_mode():
    """Le Bail/Pawley intensities are extracted from the data, so they would
    absorb any smooth theta-dependent factor and leave it unidentifiable."""
    for mode in ("lebail", "pawley"):
        model, _ = _lab6_bb(RoughnessSuortti(), mode=mode)
        assert model.roughness is None
    assert _lab6_bb(RoughnessSuortti())[0].roughness == "suortti"
    assert _lab6_bb(RoughnessPitschke())[0].roughness == "pitschke"


# -- the hidden-Jacobian guard -----------------------------------------------


@pytest.mark.parametrize("block", [
    RoughnessSuortti(a=Parameter(value=0.4, min=0.0, max=1.0),
                     b=Parameter(value=0.35, min=0.0, max=5.0,
                                 transform="softplus")),
    RoughnessPitschke(c=Parameter(value=1.2, min=0.0, max=4.0,
                                  transform="softplus"),
                      tau=Parameter(value=0.06, min=0.0, max=0.3)),
])
def test_every_analytic_column_matches_fd_with_roughness_on(block):
    """The analytic dof/adp/March columns bypass phase_peaks, so they must fold
    the roughness factor in by hand.  Omitting it there is the hidden-Jacobian
    bug WP-0506 and WP-0307 both pinned, and it is invisible with the
    correction off — hence a deliberately strong block here.
    """
    from pxrdref import PatternData
    from pxrdref.model.forward import compile_model
    from pxrdref.optimize.least_squares import _make_jacobian, _make_residual
    from pxrdref.schemas import PreferredOrientation
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    structure.phases[0].scale.value = 1e-3
    structure.phases[0].preferred_orientation = PreferredOrientation(axis=(0, 0, 1))
    ins = _bb(block)
    ins.profile.w.value = 1e-2
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())

    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    free = ["phases.0.scale", "phases.0.cell.a",
            "phases.0.atoms.1.dof.0", "phases.0.atoms.0.adp.0",
            "phases.0.atoms.0.adp.1", "phases.0.atoms.1.adp.0",
            "phases.0.preferred_orientation.r",
            "instrument.geometry.surface_roughness."
            + ("b" if block.kind == "suortti" else "c"),
            "instrument.geometry.surface_roughness."
            + ("a" if block.kind == "suortti" else "tau")]
    for p in free:
        assert table.set_vary([p], True), p
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    values = table.decode(table.x0())

    # the correction must genuinely bite, or the test cannot discriminate
    tt0 = model.phases[0].reflections.two_theta(
        tuple(values[f"phases.0.cell.{k}"]
              for k in ("a", "b", "c", "alpha", "beta", "gamma")),
        model.line_wavelengths[0])
    rough = model._roughness_factor(tt0, values)
    assert (1.0 - rough).max() > 0.05, "roughness too weak to discriminate"

    theta = table.x0()
    jac = _make_jacobian(model, table)(theta)
    residual = _make_residual(model, table)
    r0 = residual(theta)
    for c, path in enumerate(table.free_paths):
        h = 1e-6 * max(1.0, abs(theta[c]))
        tp = theta.copy()
        tp[c] += h
        col_fd = (residual(tp) - r0) / h
        scale = np.linalg.norm(col_fd)
        assert scale > 0, f"{path}: dead FD column"
        err = np.linalg.norm(jac[:, c] - col_fd) / scale
        assert err < 5e-3, f"{path}: analytic vs FD mismatch ({err:.2e})"


# -- staged plans ------------------------------------------------------------


def test_roughness_refines_last_in_every_plan_that_carries_it():
    """After biso, extinction and preferred orientation — everything it is
    degenerate with must be allowed to settle before it is freed."""
    from pxrdref.strategy.staged import RefinementPlan

    for name in ("mccusker_structural", "lab_bragg_brentano", "lab_sample_refine"):
        stages = [s.name for s in getattr(RefinementPlan, name)().stages]
        assert stages[-1] == "roughness", f"{name}: {stages}"
    structural = [s.name for s in RefinementPlan.mccusker_structural().stages]
    for earlier in ("biso", "preferred_orientation", "extinction"):
        assert structural.index(earlier) < structural.index("roughness")


def test_calibration_plan_never_frees_roughness():
    """A certified standard measures the goniometer, not the mount."""
    from pxrdref.strategy.staged import RefinementPlan

    globs = [g for s in RefinementPlan.lab_calibrate().stages for g in s.turn_on]
    assert not any("surface_roughness" in g for g in globs)


def test_the_roughness_stage_is_inert_without_a_block():
    """The glob must match nothing when no block is attached, so the stage can
    live in shared plans without changing existing refinements."""
    from tests.test_schemas import make_lab6

    table = ParameterTable(make_lab6(), _bb())
    assert table.set_vary(["instrument.geometry.surface_roughness.*"], True) == []


def test_the_seed_lifts_the_strength_parameter_into_its_sensitive_band():
    """A softplus parameter at exactly 0 has a dead internal gradient, and for
    Suortti b a token 1e-3 seed would be dead in the *physics* too: both b -> 0
    and b -> infinity are the identity, so the seed has to land near the
    measured sensitivity peak (b ~ 0.17 at 5 deg, ~ 0.46 at 20 deg)."""
    from pxrdref.params.transforms import dphys_dinternal, to_internal
    from pxrdref.strategy.staged import RefinementPlan
    from tests.test_schemas import make_lab6

    stage = RefinementPlan.lab_sample_refine().stages[-1]
    assert stage.name == "roughness"
    assert 0.1 < stage.seed < 0.6

    assert dphys_dinternal(to_internal(0.0, "softplus"), "softplus") < 1e-6
    assert dphys_dinternal(to_internal(stage.seed, "softplus"), "softplus") > 0.1

    table = ParameterTable(make_lab6(), _bb(RoughnessSuortti()))
    freed = table.set_vary(stage.turn_on, True)  # seed_softplus takes paths
    table.seed_softplus(freed, stage.seed)
    seeded = {e.path: e.value for e in table.entries}
    assert seeded["instrument.geometry.surface_roughness.b"] == pytest.approx(stage.seed)
    # ... and the seed leaves the identity-transform shape parameter alone
    assert seeded["instrument.geometry.surface_roughness.a"] == pytest.approx(0.5)


# -- the roughness <-> ADP degeneracy guard ----------------------------------


def _big_cell_structure():
    """A 10 A cubic cell, so reflections reach down to ~9 deg 2theta.

    LaB6 is useless for this: its first Cu-Kalpha reflection is at 21.4 deg, so
    lowering the fit limit adds empty grid and no information.  Roughness is
    constrained by low-angle *reflections*, not by low-angle points.
    """
    from pxrdref import Structure
    from pxrdref.schemas import Atom, Cell, Phase
    return Structure(phases=[Phase(
        name="big", space_group="P m -3 m", cell=Cell.cubic(10.0),
        atoms=[Atom(label="Zr", species="Zr", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0)),
               Atom(label="O", species="O", x=Parameter(value=0.5),
                    y=Parameter(value=0.5), z=Parameter(value=0.5))])])


def _absorption_at(two_theta_min: float):
    """roughness_absorption for a fit starting at `two_theta_min`."""
    from pxrdref import PatternData
    from pxrdref.model.forward import compile_model
    from pxrdref.optimize.least_squares import _make_jacobian
    from pxrdref.optimize.statistics import roughness_absorption
    from pxrdref.schemas.instrument import BackgroundChebyshev

    structure = _big_cell_structure()
    structure.phases[0].scale.value = 5e-3
    ins = _bb(RoughnessSuortti(
        a=Parameter(value=0.5, min=0.0, max=1.0),
        b=Parameter(value=0.3, min=0.0, max=5.0, transform="softplus")))
    ins.profile.w.value = 1e-2
    ins.background = BackgroundChebyshev.with_terms(4, vary=True)
    tt = np.arange(two_theta_min, 120.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.ones_like(tt).tolist())

    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for p in ("phases.0.scale", "instrument.background.*",
              "phases.0.atoms.*.biso", "instrument.geometry.surface_roughness.*"):
        table.set_vary([p], True)
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    jac = _make_jacobian(model, table)(table.x0())
    return roughness_absorption(jac, table.free_paths), table, jac


def test_roughness_is_identifiable_when_the_fit_reaches_low_angle():
    """The negative control: the guard must not cry wolf on usable data."""
    from pxrdref.strategy.staged import ROUGHNESS_ABSORPTION_GUARD

    r2, _, _ = _absorption_at(7.0)
    b = r2["instrument.geometry.surface_roughness.b"]
    assert b < 0.5, f"b should keep its own signature here, got R²={b:.3f}"
    assert max(r2.values()) < 1.0
    assert b < ROUGHNESS_ABSORPTION_GUARD


def test_roughness_becomes_degenerate_once_the_low_angle_reflections_are_gone():
    """And the positive control: it must fire when the data cannot separate them."""
    from pxrdref.strategy.staged import ROUGHNESS_ABSORPTION_GUARD

    wide = _absorption_at(7.0)[0]["instrument.geometry.surface_roughness.b"]
    narrow = _absorption_at(30.0)[0]["instrument.geometry.surface_roughness.b"]
    assert narrow > wide, "losing the low-angle reflections must cost separability"
    assert narrow > ROUGHNESS_ABSORPTION_GUARD, f"got R²={narrow:.3f}"


def test_the_partial_projection_is_what_makes_the_guard_work():
    """Without projecting out scale+background the statistic carries no signal.

    Roughness is a multiplicative correction, so against a block containing the
    phase scale it scores high whatever the data — which says only that both
    rescale the pattern.  The test is not that the naive number is *large* but
    that it is nearly *constant*: it barely moves between data that determines
    roughness and data that cannot, while the partial number moves across most
    of its range.  Pinned because 'simplifying' the nuisance projection away
    would silently disable the guard rather than break anything.
    """
    from pxrdref.optimize.statistics import block_projection_r2

    def both(two_theta_min, name):
        _, table, jac = _absorption_at(two_theta_min)
        free = table.free_paths
        rough = [k for k, p in enumerate(free)
                 if p.endswith(f"surface_roughness.{name}")]
        disp = [(k, p) for k, p in enumerate(free) if p.endswith(".biso")]
        nuis = [k for k, p in enumerate(free)
                if p.endswith(".scale") or p.startswith("instrument.background.")]
        naive = block_projection_r2(jac, [k for k, _ in disp] + nuis,
                                    [(k, free[k]) for k in rough])
        partial = block_projection_r2(jac, [k for k, _ in disp],
                                      [(k, free[k]) for k in rough], nuis)
        return next(iter(naive.values())), next(iter(partial.values()))

    # `a` is the clearest case: measured 0.961 -> 0.990 naive (blind) against
    # 0.586 -> 0.907 partial (informative) as the low-angle reflections go.
    naive_good, partial_good = both(7.0, "a")
    naive_bad, partial_bad = both(45.0, "a")
    assert naive_good > 0.9 and naive_bad > 0.9, "naive saturates either way"
    assert naive_bad - naive_good < 0.1, "and barely moves — no signal in it"
    assert partial_bad - partial_good > 0.25, "the partial statistic tracks it"


def test_the_guard_reports_both_directions():
    """'roughness is unidentifiable' and 'Biso is hiding in roughness' are
    different findings and both must reach the user."""
    r2, _, _ = _absorption_at(30.0)
    assert any("surface_roughness" in k for k in r2)
    assert any(k.endswith(".biso") for k in r2)


def test_guard_report_carries_roughness_and_the_diagnostic_is_actionable():
    """The measurement is only useful if it reaches the RefinementResult."""
    from types import SimpleNamespace

    from pxrdref.refine import _guard_diagnostics
    from pxrdref.strategy.staged import check_guards

    _, table, jac = _absorption_at(30.0)
    outcome = SimpleNamespace(correlation=None, jac=jac, theta=table.x0())
    guard = check_guards(table, outcome, threshold=0.98)
    assert guard.roughness_correlations, "the degenerate case must be reported"

    diags = _guard_diagnostics(guard)
    rough = [d for d in diags if d.code == "ROUGHNESS_ABSORPTION"]
    assert rough
    for d in rough:
        assert d.level == "warning" and d.where and d.suggestion
    # both directions get their own wording, not one generic sentence
    msgs = " ".join(d.message for d in rough)
    assert "not separable" in msgs or "hiding in it" in msgs


def test_unconstrained_roughness_is_flagged_rather_than_reported_as_measured():
    """Both dead branches of the Suortti model must trip the same fence: a
    large b is exactly as inert as a zero one, so a test on the parameter would
    catch only half the cases."""
    from pxrdref.refine import ROUGHNESS_MIN_DEPRESSION, _roughness_regime_diagnostics

    for b in (1e-6, 60.0):
        model, values = _lab6_bb(RoughnessSuortti(
            a=Parameter(value=0.5, min=0.0, max=1.0),
            b=Parameter(value=b, min=0.0, max=100.0, transform="softplus")))
        codes = [d.code for d in _roughness_regime_diagnostics(model, values)]
        assert "ROUGHNESS_UNCONSTRAINED" in codes, f"b={b} is inert but unflagged"

    # ... and a correction that genuinely bites is not flagged
    model, values = _lab6_bb(RoughnessSuortti(
        a=Parameter(value=0.4, min=0.0, max=1.0),
        b=Parameter(value=0.3, min=0.0, max=5.0, transform="softplus")))
    diags = _roughness_regime_diagnostics(model, values)
    assert not [d for d in diags if d.code == "ROUGHNESS_UNCONSTRAINED"]
    assert ROUGHNESS_MIN_DEPRESSION == pytest.approx(0.01)


def test_pitschke_outside_its_regime_is_flagged_not_clamped():
    """The paper's Eq (18) fence: past sin(theta) = tau the model amplifies."""
    from pxrdref.refine import _roughness_regime_diagnostics

    # data from 8 deg 2theta => sin(theta_min) ~ 0.070, so tau = 0.15 is past it
    model, values = _lab6_bb(RoughnessPitschke(
        c=Parameter(value=1.0, min=0.0, max=4.0, transform="softplus"),
        tau=Parameter(value=0.15, min=0.0, max=0.3)), two_theta_min=8.0)
    diags = [d for d in _roughness_regime_diagnostics(model, values)
             if d.code == "ROUGHNESS_OUTSIDE_REGIME"]
    assert diags and diags[0].level == "warning"
    assert "amplifies" in diags[0].message

    # the forward model is *not* clamped — clamping would kink the Jacobian
    factor = model._roughness_factor(model.tt, values)
    assert np.max(factor) > 1.0, "the breakdown is reported, not hidden"

    # comfortably inside the regime: no warning
    model, values = _lab6_bb(RoughnessPitschke(
        c=Parameter(value=1.0, min=0.0, max=4.0, transform="softplus"),
        tau=Parameter(value=0.02, min=0.0, max=0.3)), two_theta_min=8.0)
    assert not [d for d in _roughness_regime_diagnostics(model, values)
                if d.code == "ROUGHNESS_OUTSIDE_REGIME"]


def test_background_absorption_numbers_are_unchanged_by_the_refactor():
    """block_projection_r2 was extracted from background_absorption; the
    background guard's measured behaviour must not have moved."""
    from pxrdref.optimize.statistics import background_absorption, block_projection_r2

    _, table, jac = _absorption_at(7.0)
    free = table.free_paths
    bg = [k for k, p in enumerate(free) if p.startswith("instrument.background.")]
    targets = [(k, p) for k, p in enumerate(free)
               if p.endswith((".biso", ".scale", ".occ")) or ".adp." in p]
    assert background_absorption(jac, free) == block_projection_r2(jac, bg, targets)


# -- end-to-end recovery -----------------------------------------------------

OUT = Path(__file__).parent / "output"


def _synthesize_rough(block, *, noise_seed: int = 7, two_theta_min: float = 7.0):
    """A large-cell lab pattern carrying a known roughness + Poisson noise."""
    from pxrdref import PatternData
    from pxrdref.model.forward import compile_model

    structure = _big_cell_structure()
    structure.phases[0].scale.value = 2e-2
    ins = _bb(block)
    ins.profile.w.value = 8e-3
    tt = np.arange(two_theta_min, 120.0, 0.02)
    pattern = PatternData(two_theta=tt.tolist(),
                          intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0())) + 40.0  # flat background floor
    rng = np.random.default_rng(noise_seed)
    return PatternData(two_theta=model.tt.tolist(),
                       intensity=rng.poisson(np.maximum(y, 1.0)).astype(float).tolist())


def test_injected_roughness_is_recovered_and_is_resolved_not_merely_fitted():
    """Inject a known Suortti depression, start from the identity, recover it.

    Biso is held at its (correct) value so the recovery isolates roughness from
    the displacement parameters it competes with — the co-refined case is what
    the block-R² guard above is for, and the does-no-harm side is checked
    against real data in the acceptance tests.
    """
    from pxrdref import Refinement
    from pxrdref.strategy.staged import RefinementPlan, Stage
    from pxrdref.viz.plots import plot_result

    b_true = 0.35
    truth = RoughnessSuortti(
        a=Parameter(value=0.45, min=0.0, max=1.0),
        b=Parameter(value=b_true, min=0.0, max=5.0, transform="softplus"))
    pattern = _synthesize_rough(truth)

    structure = _big_cell_structure()
    structure.phases[0].scale.value = 1.6e-2
    ins = _bb(RoughnessSuortti(          # starts at the identity: b = 0
        a=Parameter(value=0.45, vary=False, min=0.0, max=1.0),
        b=Parameter(value=0.0, min=0.0, max=5.0, transform="softplus")))
    ins.profile.w.value = 9e-3

    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("roughness", ["instrument.geometry.surface_roughness.b"], seed=0.3),
    ])
    result = Refinement(structure, ins, history=False).fit(pattern, plan=plan)
    assert result.status == "converged"

    b = result.parameter("instrument.geometry.surface_roughness.b")
    assert b.stderr is not None and b.stderr > 0
    assert b.value == pytest.approx(b_true, abs=max(4 * b.stderr, 0.05 * b_true)), \
        f"recovered b={b.value:.4f}±{b.stderr:.4f}, truth {b_true}"
    # resolved, not merely fitted: several esds off the identity it started at
    assert b.value > 5 * b.stderr

    OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(OUT / "roughness_recovery.png"))
    plot_result(result, path=str(OUT / "roughness_recovery_lowangle.png"),
                two_theta_range=(7.0, 40.0))  # where the depression lives
    import matplotlib.pyplot as plt
    plt.close("all")
