"""Surface roughness (WP-0502): Suortti (1972) and Pitschke et al. (1993).

A rough or loosely-packed flat specimen depresses diffracted intensity at low
2theta.  Left uncorrected the depression is absorbed by Biso/ADPs (driving them
toward — and past — zero), by the phase scales and by a flexible background, so
every test here is written twice over: once for the physics, once for the
degeneracy that physics creates.
"""

import math

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
