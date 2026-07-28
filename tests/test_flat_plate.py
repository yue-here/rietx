"""Flat-plate absorption, ITC Vol. C Table 6.3.3.1 cases (2) and (3a) — WP-0508.

The validation strategy is WP-0501's lesson applied where it is cheap: an
absorption expression is checked against **the integral it comes from**, spanning
*both* its arguments, never against another code's transcription.  WP-0501's b₂
coefficient was printed with two digits transposed in the available scan of the
source, and that error was invisible against a constant-θ slice of the paper's
own table.  Here the two expressions are closed-form integrals rather than fits,
so a direct quadrature of the defining path-length integral is an independent
check with no shared constants at all.
"""

import numpy as np
import pytest

from pxrdref.model.absorption import (
    cylinder_absorption,
    equivalent_delta_biso,
    equivalent_delta_biso_from_transmission,
    flat_plate_reflection_absorption,
    flat_plate_transmission_absorption,
    mu_t_identifiable_fraction,
    optimal_transmission_thickness_mm,
)

TWO_THETA = np.linspace(5.0, 140.0, 271)


def _quadrature_reflection(two_theta_deg: np.ndarray, mu_t: float) -> np.ndarray:
    """ITC (2) by adaptive quadrature of the volume integral, normalised.

    A beam of unit cross-section meets the surface at grazing angle θ: the
    illuminated area is 1/sin θ and an element at depth z has total in+out path
    2z/sin θ.  Integrating exp(−µ·T) over the illuminated volume and dividing by
    the thick-specimen limit 1/2µ is the whole derivation, and it shares no
    constant with the implementation.  Written with µ = 1, so z runs over µt.

    ``quad`` rather than a fixed grid on purpose: at low θ the integrand decays
    over a depth ~sin θ/2, so a uniform rule needs absurd resolution to reach
    the 1e-9 this test wants — a trapezoid at 2e5 points is only good to 1e-7
    and, being convex-side, reports A > 1, which would look like a bug in the
    implementation rather than in the check.
    """
    from scipy.integrate import quad
    theta = np.radians(0.5 * np.asarray(two_theta_deg, dtype=np.float64))
    out = np.empty_like(theta)
    for i, th in enumerate(theta):
        val, _err = quad(lambda z, s=np.sin(th): np.exp(-2.0 * z / s) / s,
                         0.0, mu_t, epsabs=1e-14, epsrel=1e-14, limit=200)
        out[i] = val / 0.5                              # ÷ thick limit 1/2µ
    return out


def _quadrature_transmission(two_theta_deg: np.ndarray, mu_t: float) -> np.ndarray:
    """ITC (3a) by adaptive quadrature, normalised at θ = 0.

    The plate normal bisects the beams, so an element at depth z has incident
    path z/cos θ and diffracted path (t − z)/cos θ — a total independent of z —
    over a footprint 1/cos θ.  The z-integral is therefore trivial, which is the
    point: it is a *different* computation from the closed form even though it
    lands on the same number.
    """
    from scipy.integrate import quad
    theta = np.radians(0.5 * np.asarray(two_theta_deg, dtype=np.float64))
    out = np.empty_like(theta)
    for i, th in enumerate(theta):
        c = np.cos(th)
        val, _err = quad(lambda z, c=c: np.exp(-(z + (mu_t - z)) / c) / c,
                         0.0, mu_t, epsabs=1e-13, epsrel=1e-13, limit=200)
        out[i] = val
    return out / (mu_t * np.exp(-mu_t))                 # ÷ the θ = 0 value


@pytest.mark.parametrize("mu_t", [0.05, 0.2, 0.5, 1.0, 2.0, 5.0])
def test_reflection_matches_the_defining_integral(mu_t):
    got = np.asarray(flat_plate_reflection_absorption(TWO_THETA, mu_t))
    want = _quadrature_reflection(TWO_THETA, mu_t)
    assert np.max(np.abs(got - want)) < 1e-9, np.max(np.abs(got - want))


@pytest.mark.parametrize("mu_t", [0.2, 1.0, 3.0])
def test_transmission_matches_the_defining_integral(mu_t):
    got = np.asarray(flat_plate_transmission_absorption(TWO_THETA, mu_t))
    want = _quadrature_transmission(TWO_THETA, mu_t)
    assert np.max(np.abs(got - want)) < 1e-9, np.max(np.abs(got - want))


def test_reflection_is_the_identity_in_the_thick_limit():
    """(2) → 1 as µt → ∞: the continuity check with the case this package
    already assumes (ITC (1a), A = 1/2µ, no θ)."""
    for mu_t, tol in [(3.0, 1e-2), (5.0, 1e-4), (10.0, 1e-8), (25.0, 1e-20)]:
        a = np.asarray(flat_plate_reflection_absorption(TWO_THETA, mu_t))
        assert np.all(a <= 1.0)
        assert np.max(1.0 - a) < tol, (mu_t, np.max(1.0 - a))


def test_reflection_depresses_the_high_angle_and_transmission_the_low():
    """The two cases lean opposite ways, which is what makes their Biso biases
    opposite in sign.  Getting either backwards (the A vs A* = 1/A trap) would
    invert the θ-dependence, and an identity test cannot see that."""
    a_refl = np.asarray(flat_plate_reflection_absorption(TWO_THETA, 0.3))
    assert np.all(np.diff(a_refl) < 0.0), "finite-thickness reflection must fall with 2θ"

    a_trans = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 0.1))
    assert np.all(np.diff(a_trans) > 0.0), "a thin transmission plate must rise with 2θ"
    # …and turn over once absorption beats the sec θ footprint growth
    thick = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 3.0))
    assert np.all(np.diff(thick) < 0.0)


def test_transmission_is_pure_footprint_at_zero_absorption():
    """µt = 0 leaves sec θ, and that is physics: the beam's footprint on a
    tilted plate grows as sec θ, so the diffracting volume does too."""
    a = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 0.0))
    theta = np.radians(0.5 * TWO_THETA)
    assert np.allclose(a, 1.0 / np.cos(theta), rtol=0.0, atol=1e-15)


def test_optimal_thickness_maximises_the_unnormalised_intensity():
    """t = 1/µ, checked by brute force on the ITC (3a) expression itself."""
    mu_cm = 250.0
    t_opt = optimal_transmission_thickness_mm(mu_cm)
    assert t_opt == pytest.approx(10.0 / mu_cm)
    grid = np.linspace(0.1 * t_opt, 4.0 * t_opt, 20_001)          # mm
    intensity = grid * np.exp(-mu_cm / 10.0 * grid)               # θ = 0, sec = 1
    assert grid[int(np.argmax(intensity))] == pytest.approx(t_opt, rel=1e-3)


def test_projected_delta_biso_reproduces_the_cylinder_closed_form():
    """The general projection and WP-0501's closed form must agree exactly.

    ln A for the Rouse cylinder is *exactly* affine in sin²θ, so the
    least-squares projection has zero residual and its slope is the analytic c.
    This is the test that ties the flat-plate ΔBiso — which has no closed form —
    to a case whose answer is known independently.
    """
    for mu_r in (0.1, 0.5, 1.0):
        a = np.asarray(cylinder_absorption(TWO_THETA, mu_r))
        delta, unabsorbed = equivalent_delta_biso_from_transmission(
            TWO_THETA, a, 1.5406)
        assert delta == pytest.approx(equivalent_delta_biso(mu_r, 1.5406), rel=1e-12)
        assert unabsorbed < 1e-12, "the cylinder must be exactly reparameterisable"


def test_flat_plate_delta_biso_has_the_right_sign_and_is_large():
    """Both biases, and the fact that they are an order of magnitude larger than
    the capillary's — which is what makes flat-plate absorption worth having
    even though its geometry is the one people call 'thick'."""
    for mu_t in (0.2, 0.5):
        a = np.asarray(flat_plate_reflection_absorption(TWO_THETA, mu_t))
        delta, unabsorbed = equivalent_delta_biso_from_transmission(
            TWO_THETA, a, 1.5406)
        # a thin plate loses high-angle intensity ⇒ Biso refined without the
        # correction comes back too *large* ⇒ the recovery is negative
        assert delta < 0.0
        assert abs(delta) > 0.5, f"µt={mu_t} bias {delta:.3f} Å² unexpectedly small"
        # unlike the cylinder, part of it is genuinely not a scale × Biso
        assert unabsorbed > 0.01

    a = np.asarray(flat_plate_transmission_absorption(TWO_THETA, 0.2))
    delta, _ = equivalent_delta_biso_from_transmission(TWO_THETA, a, 1.5406)
    assert delta > 0.0, "a thin transmission plate biases Biso the other way"


def test_mu_t_identifiability_is_small_but_not_zero():
    """The measurement behind ``Geometry.mu_t`` being a plain float.

    Unlike µR — whose derivative lies *identically* in span{1, sin²θ}, so
    refining it would be an exactly singular direction — a flat-plate µt keeps a
    few per cent to tens of per cent of its signature.  The design choice is
    therefore backed by a measurement plus the argument that µt is knowable from
    the specimen, not by an identity; this test pins the measurement so a future
    session revisiting the choice starts from numbers.
    """
    tt = np.linspace(10.0, 90.0, 400)
    transmission = mu_t_identifiable_fraction(tt, 0.3, "flat_plate_transmission")
    assert 0.01 < transmission < 0.15, transmission
    # transmission's ∂lnA/∂µt is an amplitude: the fraction cannot depend on µt
    assert mu_t_identifiable_fraction(tt, 3.0, "flat_plate_transmission") == \
        pytest.approx(transmission, rel=1e-12)

    for mu_t in (0.1, 0.3, 1.0):
        assert 0.01 < mu_t_identifiable_fraction(tt, mu_t, "bragg_brentano") < 0.4

    # and the µR comparison that motivates the whole distinction
    from pxrdref.model.absorption import mu_r_identifiable_fraction
    assert mu_r_identifiable_fraction(tt, 0.5) < 1e-12


def test_intensity_fraction_peaks_at_one_absorption_length():
    from pxrdref.model.absorption import transmission_intensity_fraction

    assert transmission_intensity_fraction(1.0) == pytest.approx(1.0)
    for mu_t in (0.05, 0.4, 2.0, 5.0):
        assert transmission_intensity_fraction(mu_t) < 1.0
    # both a too-thin and a too-thick plate lose, but not symmetrically in µt:
    # 0.4 and 2.0 straddle the optimum yet give 0.7288 and 0.7358
    assert transmission_intensity_fraction(0.4) == pytest.approx(0.7288, abs=1e-4)
    assert transmission_intensity_fraction(2.0) == pytest.approx(0.7358, abs=1e-4)
    assert transmission_intensity_fraction(0.1) == pytest.approx(0.2460, abs=1e-4)


# -- the schema seam ----------------------------------------------------


@pytest.mark.parametrize("kwargs,match", [
    (dict(kind="debye_scherrer", mu_t=0.3), "flat-specimen quantity"),
    (dict(kind="debye_scherrer", thickness_mm=0.2), "flat-specimen quantity"),
    (dict(kind="bragg_brentano", goniometer_radius_mm=217.5, mu_t=0.0),
     "zero thickness"),
    (dict(kind="bragg_brentano", goniometer_radius_mm=217.5, mu_t=-0.1),
     "non-negative"),
    (dict(kind="flat_plate_transmission", thickness_mm=0.0), "must be positive"),
    (dict(kind="flat_plate_transmission", mu_r=0.5), "only to debye_scherrer"),
])
def test_geometry_validators(kwargs, match):
    from pydantic import ValidationError

    from pxrdref.schemas.instrument import Geometry
    with pytest.raises(ValidationError, match=match):
        Geometry(**kwargs)


def test_zero_mu_t_is_legal_in_transmission_and_is_pure_footprint():
    """The asymmetry between the two flat cases, pinned.

    µt = 0 is a *specimen* under transmission (a non-absorbing plate still has
    a sec θ footprint) and a contradiction under reflection (no specimen at
    all), so the two cannot share the "0 means off" convention.
    """
    from pxrdref.schemas.instrument import Geometry

    geom = Geometry(kind="flat_plate_transmission", mu_t=0.0)
    assert geom.mu_t == 0.0


def test_geometry_round_trips_through_json():
    from pxrdref.schemas.instrument import Geometry

    geom = Geometry(kind="flat_plate_transmission", mu_t=0.42, thickness_mm=0.15,
                    packing_fraction=0.45)
    assert Geometry.model_validate_json(geom.model_dump_json()) == geom


def test_specimen_absorption_is_stripped_from_an_instrument_profile(tmp_path):
    """µt describes the mount, not the diffractometer.

    Saving it into an instrument profile would silently pre-bias the ADPs of
    every later sample measured on that instrument — the exact bias the
    correction exists to remove.  Same rule as surface roughness (WP-0502).
    """
    from pxrdref import Instrument
    from pxrdref.io.instrument_profile import (
        load_instrument_profile,
        save_instrument_profile,
    )

    ins = Instrument.bragg_brentano(mu_t=0.4, thickness_mm=0.02)
    path = tmp_path / "profile.json"
    save_instrument_profile(ins, path)
    assert ins.geometry.mu_t == 0.4, "must not mutate the caller"
    loaded = load_instrument_profile(path)
    assert loaded.geometry.mu_t is None
    assert loaded.geometry.thickness_mm is None


def test_transmission_preset_defaults_to_a_monochromated_beam():
    from pxrdref import Instrument

    ins = Instrument.flat_plate_transmission(mu_t=0.3)
    assert ins.geometry.kind == "flat_plate_transmission"
    assert len(ins.source.lines) == 1, "Kα1-only by default (focusing mono)"
    assert ins.geometry.mu_t == 0.3
    doublet = Instrument.flat_plate_transmission(radiation="CuKa", mu_t=0.3)
    assert len(doublet.source.lines) == 2


# -- the forward-model seam, and the hidden-Jacobian hazard -------------


def _flat_plate_model(mu_t: float, kind: str):
    """A compiled aniso-rutile model with every analytic-column path live.

    Mirrors ``test_absorption._capillary_model`` deliberately: the guard below
    is the same guard, and the two must not drift apart.
    """
    from pxrdref import Instrument, PatternData
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    structure.phases[0].scale.value = 1e-3
    structure.phases[0].extinction.value = 2.0
    if kind == "flat_plate_transmission":
        ins = Instrument.flat_plate_transmission(radiation="CuKa1", mu_t=mu_t)
    else:
        ins = Instrument.bragg_brentano(radiation="CuKa1", mu_t=mu_t)
    ins.profile.w.value = 1e-2
    grid = np.arange(10.0, 90.0, 0.02)
    pattern = PatternData(two_theta=grid.tolist(),
                          intensity=np.zeros_like(grid).tolist())
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    for p in ("phases.0.atoms.1.dof.0", "phases.0.atoms.0.adp.0",
              "phases.0.atoms.0.adp.1", "phases.0.atoms.1.adp.0",
              "phases.0.scale", "phases.0.cell.a", "phases.0.cell.c",
              "phases.0.extinction"):
        assert table.set_vary([p], True), p
    model = compile_model(structure, ins, pattern, mode="rietveld",
                          free_paths=set(table.free_paths))
    return model, table


@pytest.mark.parametrize("kind,mu_t", [
    ("bragg_brentano", 0.15),
    ("flat_plate_transmission", 3.0),
])
def test_every_analytic_column_carries_the_flat_plate_factor(kind, mu_t):
    """The hidden-Jacobian guard, for the two new geometries.

    A multiplies the same product ``_structural_intensity_grad`` and
    ``po_intensity_grad`` rebuild by hand.  Omit it in either and those columns
    are wrong by A while the finite-difference columns stay right: the fit still
    converges, to the wrong structure.  The µt values are chosen so A swings by
    more than half across the pattern — the pre-assert below is what stops this
    passing vacuously, exactly as in ``test_absorption.py``.
    """
    from pxrdref.optimize.least_squares import _make_jacobian, _make_residual

    model, table = _flat_plate_model(mu_t, kind)
    a = np.asarray(model._absorption(model.tt))
    assert a.max() / a.min() > 1.5, "correction too weak — test would not discriminate"

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


def test_the_thick_specimen_default_leaves_the_forward_model_untouched():
    """Every flat-plate result this package shipped before WP-0508 is unchanged.

    Not a formality: the *reflection* correction's identity is µt → ∞, so an
    implementation that treated a missing thickness as µt = 0 would multiply
    every intensity by zero.  ``mu_t is None`` has to mean "thick", and this is
    what pins it.
    """
    model_off, table = _flat_plate_model(0.4, "bragg_brentano")
    object.__setattr__(model_off, "mu_t", None)
    assert model_off._absorption(model_off.tt) == 1.0
    values = table.decode(table.x0())
    y_thick = model_off.evaluate(values)
    assert np.all(np.isfinite(y_thick)) and y_thick.max() > 0.0

    model_on, _ = _flat_plate_model(0.4, "bragg_brentano")
    y_thin = model_on.evaluate(values)
    # the thin specimen has lost high-angle intensity relative to low
    top = model_on.tt > 70.0
    bottom = model_on.tt < 25.0
    assert y_thin[top].max() / y_thick[top].max() \
        < y_thin[bottom].max() / y_thick[bottom].max()


def test_debye_scherrer_ignores_mu_t_and_flat_plate_ignores_mu_r():
    """The geometry gate, from the forward model's side rather than the schema's."""
    model, _ = _flat_plate_model(0.3, "bragg_brentano")
    assert model.mu_r == 0.0
    assert not np.isscalar(model._absorption(model.tt))

    from pxrdref import Instrument
    ins = Instrument.debye_scherrer(wavelength=1.5406, mu_r=0.5)
    assert ins.geometry.mu_t is None


# -- the result record and its diagnostics ------------------------------


def _fit_flat_plate(kind: str, **geometry):
    """A tiny end-to-end Rietveld fit against a self-generated pattern."""
    import pxrdref as pr
    from tests.test_aniso_adp import make_aniso_rutile

    structure = make_aniso_rutile()
    structure.phases[0].scale.value = 1e-3
    if kind == "flat_plate_transmission":
        ins = pr.Instrument.flat_plate_transmission(radiation="CuKa1", **geometry)
    else:
        ins = pr.Instrument.bragg_brentano(radiation="CuKa1", **geometry)
    ins.profile.w.value = 1e-2
    grid = np.arange(15.0, 90.0, 0.05)
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins,
                          pr.PatternData(two_theta=grid.tolist(),
                                         intensity=np.ones_like(grid).tolist()),
                          mode="rietveld", free_paths=set())
    y = np.asarray(model.evaluate(table.decode(table.x0())))
    data = pr.PatternData(two_theta=grid.tolist(),
                          intensity=(y + 1.0).tolist())
    ref = pr.Refinement(structure, ins, history=False)
    return ref.fit(data, plan=pr.RefinementPlan(
        stages=[pr.Stage("scale", ["phases.*.scale"])]))


def test_record_reports_the_bias_and_the_part_that_is_not_a_reparameterisation():
    result = _fit_flat_plate("bragg_brentano", mu_t=0.2)
    record = result.absorption
    assert record is not None
    assert record.method == "flat_plate_reflection"
    assert record.mu_r == pytest.approx(0.2)
    assert record.mu_r_source == "given"
    # a thin reflection specimen biases Biso *high*, so the recovery is negative
    assert record.equivalent_delta_biso < 0.0
    # …and, unlike the cylinder, the correction is not purely a scale × Biso
    assert record.unabsorbed_fraction > 0.01
    assert record.identifiable_fraction > 0.0
    assert record.intensity_fraction_of_optimal is None
    assert not record.out_of_range, "out_of_range belongs to the Rouse fit only"

    codes = {d.code for d in result.diagnostics}
    assert "ABSORPTION_THICKNESS_MATTERS" in codes


def test_transmission_record_carries_the_thickness_advice():
    result = _fit_flat_plate("flat_plate_transmission", mu_t=0.1)
    record = result.absorption
    assert record.method == "flat_plate_transmission"
    assert record.intensity_fraction_of_optimal == pytest.approx(
        0.1 * np.exp(0.9), rel=1e-9)
    codes = {d.code for d in result.diagnostics}
    assert "ABSORPTION_PLATE_THICKNESS" in codes, "a 0.1 µt plate wastes counts"

    # at the optimum the advice is silent
    at_optimum = _fit_flat_plate("flat_plate_transmission", mu_t=1.0)
    assert "ABSORPTION_PLATE_THICKNESS" not in {
        d.code for d in at_optimum.diagnostics}


def test_a_neglected_thickness_lands_in_biso_and_the_prediction_is_a_lower_bound():
    """The end-to-end version of the claim, and the honest limit of it.

    Everything else here tests the projection *arithmetic*.  This one generates
    patterns from a known structure **through** the correction, refits them
    without declaring the thickness, and asks where the difference went — which
    is the failure this correction exists to prevent, and the only test that
    would catch a sign error in the ΔBiso the result reports.

    Two results, and the second is why ``unabsorbed_fraction`` is on the record
    next to ``equivalent_delta_biso`` rather than buried:

    1. Declaring the true thickness recovers the true Biso **exactly** (5e-4),
       and omitting it inflates Biso by Å²-scale amounts — 1.8 Å² at µt = 0.15
       on a B = 0.8 structure.
    2. The reported ΔBiso is a **lower bound**, not the answer. The projection
       is an unweighted fit of ln A onto {1, sin²θ}; the refinement finds a
       *weighted* least-squares compromise, and the two agree only insofar as
       the correction is genuinely a {scale, Biso} direction. Measured, the
       ratio of actual to predicted bias tracks ``unabsorbed_fraction``:

       ====================  =====  =====  =====
       µt                    0.15   0.3    0.6
       unabsorbed_fraction   0.263  0.201  0.080
       actual / predicted    ~1.5   ~1.3   ~1.06
       ====================  =====  =====  =====

       For the cylinder ``unabsorbed_fraction`` is zero to rounding and the
       predicted shift is exact to seven decimals on real data
       (``test_acceptance_capillary``). That contrast is the whole point.
    """
    import pxrdref as pr
    from pxrdref.model.forward import compile_model
    from pxrdref.params.vector import ParameterTable
    from tests.test_aniso_adp import make_aniso_rutile

    b_true = 0.8
    grid = np.arange(15.0, 130.0, 0.02)
    plan = pr.RefinementPlan(stages=[
        pr.Stage("scale", ["phases.*.scale"]),
        pr.Stage("biso", ["phases.*.atoms.*.biso"]),
    ])

    def build(mu_t):
        structure = make_aniso_rutile()
        phase = structure.phases[0]
        phase.scale.value = 1e-3
        for atom in phase.atoms:      # isotropic, so Biso is the only sink
            atom.aniso = None
            atom.biso = pr.Parameter(value=b_true, min=0.0, max=5.0)
        ins = pr.Instrument.bragg_brentano(radiation="CuKa1", mu_t=mu_t)
        ins.profile.w.value = 1e-2
        return structure, ins

    measured = []
    for mu_t in (0.15, 0.6):
        truth, ins_true = build(mu_t)
        table = ParameterTable(truth, ins_true)
        model = compile_model(truth, ins_true,
                              pr.PatternData(two_theta=grid.tolist(),
                                             intensity=np.ones_like(grid).tolist()),
                              mode="rietveld", free_paths=set())
        y = np.asarray(model.evaluate(table.decode(table.x0())))
        # no background offset: the plan frees only the scale and Biso, so an
        # unmodelled constant would be absorbed by the parameters under test
        data = pr.PatternData(two_theta=grid.tolist(), intensity=y.tolist(),
                              sigma=np.sqrt(np.maximum(y, 1.0)).tolist())

        fits = {}
        for declared in (mu_t, None):
            structure, ins = build(declared)
            for atom in structure.phases[0].atoms:
                atom.biso.value = 0.5      # start away from the truth either way
            ref = pr.Refinement(structure, ins, history=False)
            result = ref.fit(data, plan=plan)
            assert result.status == "converged"
            fits[declared] = (ref, result)

        ref_on, result_on = fits[mu_t]
        ref_off, _ = fits[None]
        # 1. declaring the true thickness recovers the true Biso
        for atom in ref_on.fitted_structure.phases[0].atoms:
            assert atom.biso.value == pytest.approx(b_true, abs=5e-4), atom.label

        record = result_on.absorption
        assert record.equivalent_delta_biso < 0.0
        for on, off in zip(ref_on.fitted_structure.phases[0].atoms,
                           ref_off.fitted_structure.phases[0].atoms):
            shift = off.biso.value - on.biso.value
            assert shift > 0.4, f"B({on.label}) barely moved ({shift:.4f} Å²)"
            ratio = shift / -record.equivalent_delta_biso
            # 2. a lower bound: never an overestimate, and never wild
            assert 1.0 <= ratio < 2.0, f"B({on.label}) ratio {ratio:.3f}"
            measured.append((record.unabsorbed_fraction, ratio))

    # …and the error tracks how much of ln A a free {scale, Biso} cannot absorb,
    # which is exactly what makes that field worth reporting alongside the bias
    (unabs_hi, ratio_hi), (unabs_lo, ratio_lo) = measured[0], measured[-1]
    assert unabs_hi > unabs_lo
    assert ratio_hi > ratio_lo + 0.2


def test_thick_specimen_produces_no_record_at_all():
    """No thickness ⇒ nothing was corrected ⇒ nothing to report, rather than a
    record full of zeros that reads as "we applied something"."""
    assert _fit_flat_plate("bragg_brentano").absorption is None


def test_mu_t_is_estimated_from_thickness_and_composition():
    result = _fit_flat_plate("bragg_brentano", thickness_mm=0.02)
    record = result.absorption
    assert record is not None and record.mu_r_source == "estimated"
    # TiO2 at Cu Kα1: µ ≈ 500 /cm, so 20 µm at 0.6 packing lands near µt ≈ 0.6
    assert 0.2 < record.mu_r < 1.5, record.mu_r
