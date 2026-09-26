"""FitReport Layers 1-2: synthetic misfit injection and confidence calibration.

The design record is explicit that without this suite the confidence numbers
are decorative.  Each test perturbs exactly **one** known cause in a
converged model, rebuilds the report, and asserts the report recovers that
cause — and, just as importantly, that deliberately-collinear setups are
reported as *unresolved* rather than as a confident wrong singleton.
"""

from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.report import (
    apply_strategy_veto,
    build_report,
    delta_bic,
    hamilton_justified,
    predict_then_verify,
)
from rietx.report.schemas import LEBAIL_GAP_NOTABLE, VALIDITY_RADIUS_FWHM
from tests.test_schemas import make_lab6

WAVELENGTH = 1.5405929


# ----------------------------------------------------------------------
# a converged reference state we can perturb one knob at a time
# ----------------------------------------------------------------------
#: Poisson count scaling.  Kept high on purpose: the information that
#: separates a constant zero error from a cosθ displacement lives in the
#: *high-angle* peaks, and at low counts those regions carry no significant
#: misfit, so the report (correctly) refuses to separate the two.  Measured
#: separability ratio at these settings: 1.2 at ×8 counts vs 10 at ×60.
_COUNT_SCALE = 60.0


def _truth(lo=18.0, hi=125.0, step=0.02, seed=17, disp=0.0,
           count_scale=_COUNT_SCALE):
    """A model and the noisy pattern it generates — i.e. a *converged* state.

    The background lives in the instrument (a flat Chebyshev term), not added
    on top of the pattern, so that the unperturbed model reproduces the data
    to within counting noise and Layer 1 has a mature fit to work from.

    ``disp`` puts a sample displacement into the **specimen**, not into a
    starting model: the returned pattern is genuinely displaced, which is the
    one thing the planted-start episodes cannot do.  It is what a rival
    comparison needs to have anything to compare — with ``disp = 0`` the
    zero-only and displacement-only fits describe the same pattern equally
    well and tie exactly (WP-1063; ``tests/eval_report_agent/PROTOCOL.md``
    § Episode validity says the same thing of E2 and E8).  The default is
    ``0.0``, so every other caller's data is unchanged.

    ``count_scale`` multiplies the counts.  Raised, it makes a model misfit
    dominate the counting noise, which is how ``test_compare_freed.py`` gets a
    serially correlated residual.
    """
    from rietx.schemas.instrument import BackgroundChebyshev

    structure = make_lab6()
    structure.phases[0].scale.value = 4e-4
    ins = rx.Instrument.bragg_brentano(monochromator_two_theta=26.6)
    ins.profile.w.value = 4e-3
    ins.profile.u.value = 3e-3
    ins.profile.x.value = 6e-3
    ins.geometry.axial_sl.value = 0.02
    ins.geometry.axial_hl.value = 0.02
    ins.geometry.sample_displacement.value = disp
    ins.background = BackgroundChebyshev(coefficients=[
        rx.Parameter(value=80.0), rx.Parameter(value=0.0),
        rx.Parameter(value=0.0), rx.Parameter(value=0.0)])

    tt = np.arange(lo, hi, step)
    grid = rx.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y_noisy = rng.poisson(np.maximum(y, 1.0) * count_scale) / count_scale
    data = rx.PatternData(two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
                          sigma=np.sqrt(np.maximum(y, 1.0) / count_scale).tolist())
    return structure, ins, data


def _result_for(structure, ins, data):
    """A RefinementResult evaluated at a *given* (unrefined) model state."""
    table = ParameterTable(structure, ins)
    model = compile_model(structure, ins, data, mode="rietveld")
    values = table.decode(table.x0())
    y_calc = model.evaluate(values)
    from rietx.optimize.statistics import compute_statistics
    from rietx.schemas.common import Provenance
    from rietx.schemas.results import RefinementResult

    stats = compute_statistics(model.y_obs, y_calc, model.sigma, n_free=0,
                               y_background=model.background(values))
    ticks = {}
    for ip, cp in enumerate(model.phases):
        cell = tuple(values[f"phases.{ip}.cell.{k}"]
                     for k in ("a", "b", "c", "alpha", "beta", "gamma"))
        pos = np.concatenate([cp.reflections.two_theta(cell, lam)
                              for lam in model.line_wavelengths])
        ticks[structure.phases[ip].name] = sorted(
            float(p) for p in pos if np.isfinite(p))
    result = RefinementResult(
        status="converged", mode="rietveld", parameters=[], statistics=stats,
        provenance=Provenance(package_version="test"),
        two_theta=model.tt.tolist(), y_obs=model.y_obs.tolist(),
        y_calc=y_calc.tolist(), y_background=model.background(values).tolist(),
        sigma=model.sigma.tolist(), ticks=ticks)
    return result, model, values


def _report_for(structure, ins, data, **kw):
    """Build the full report for a *given* (unrefined) model state."""
    result, model, values = _result_for(structure, ins, data)
    return build_report(result, model=model, values=values, **kw)


def _coefficients(report, kind):
    return [c.value for a in report.attribution if a.gates_passed
            for c in a.coefficients if c.kind == kind and c.significant]


def _template(report, observable, name):
    for t in report.trends:
        if t.observable == observable:
            for tpl in t.templates:
                if tpl.name == name:
                    return tpl
    return None


def _kinds(report, *, active_only=True):
    return [a.kind for a in report.suggested_actions if a.active or not active_only]


# ----------------------------------------------------------------------
# baseline: an unperturbed model must not invent causes
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def truth():
    return _truth()


def test_unperturbed_model_reports_no_strong_cause(truth):
    structure, ins, data = truth
    report = _report_for(structure, ins, data)
    assert report.layer1_available, report.abstained_reason
    # noise only: nothing should reach high confidence
    strong = [a for a in report.suggested_actions if a.active and a.confidence > 0.6]
    assert not strong, f"invented causes on a correct model: {[a.kind for a in strong]}"
    # and the position coefficients must be small compared with the FWHM
    shifts = _coefficients(report, "position")
    if shifts:
        assert max(abs(s) for s in shifts) < 0.01


# ----------------------------------------------------------------------
# single-cause injections
# ----------------------------------------------------------------------
def _best_template(report, observable):
    trend = next(t for t in report.trends if t.observable == observable)
    return trend, max(trend.templates, key=lambda t: t.r2)


def test_injected_zero_shift_is_recovered(truth):
    """A pure zero-point error: constant Δ2θ across the whole pattern.

    The injection is deliberately small (0.008° ≈ 0.12·FWHM): the shape basis
    is a *first-order* expansion, and a shift approaching the validity radius
    is recovered with a systematic deficit (measured −0.014 for a 0.020°
    injection).  Large offsets are the validity gate's job, tested separately.
    """
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.008

    report = _report_for(structure, perturbed, data)
    assert report.layer1_available, report.abstained_reason

    shifts = _coefficients(report, "position")
    assert shifts, "no significant position error detected"
    # observed sits 0.008° BELOW where the shifted model puts the peaks
    assert np.median(shifts) == pytest.approx(-0.008, abs=0.002)

    trend, best = _best_template(report, "position")
    assert best.name == "constant", f"a constant shift ranked as {best.name}"
    assert best.coefficient == pytest.approx(-0.008, abs=0.002)
    assert trend.separable, f"ratio={trend.separability_ratio:.2f}"
    assert "refine_zero_shift" in _kinds(report, active_only=False)


def test_injected_displacement_prefers_cos_theta_template(truth):
    """Specimen displacement has a cosθ signature, distinguishable from a
    constant zero error *because* the scan runs to 125° 2θ."""
    structure, ins, data = truth
    # 0.02 mm at R = 217.5 mm is ≈0.010° at low angle — inside the
    # linearisation radius (0.4·FWHM ≈ 0.027°)
    perturbed = ins.model_copy(deep=True)
    perturbed.geometry.sample_displacement.value = -0.02

    report = _report_for(structure, perturbed, data)
    assert report.layer1_available, report.abstained_reason

    trend, best = _best_template(report, "position")
    assert best.name == "cos_theta", f"a cosθ shift ranked as {best.name}"
    assert trend.separable, (
        f"cosθ and constant must separate over 18-125° 2θ "
        f"(ratio={trend.separability_ratio:.2f})")
    assert abs(best.coefficient) > 3 * best.stderr
    assert "refine_sample_displacement" in _kinds(report, active_only=False)


def test_injected_width_error_is_recovered(truth):
    """Peaks too narrow → a positive ΔΓ coefficient everywhere."""
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.profile.w.value = 2.0e-3      # truth is 4e-3

    report = _report_for(structure, perturbed, data)
    assert report.layer1_available, report.abstained_reason
    widths = _coefficients(report, "width")
    assert widths, "no significant width error detected"
    assert np.median(widths) > 0, "model is too narrow; ΔΓ must be positive"
    assert any(k in _kinds(report, active_only=False)
               for k in ("refine_profile_widths", "refine_sample_size_broadening",
                         "refine_sample_strain_broadening"))


def test_the_size_template_quotes_the_width_as_a_crystallite_size():
    """The width deficit read in the unit a specimen can be judged in.

    ``inv_cos_theta``'s fitted coefficient *is* a 1/cosθ size coefficient in
    deg 2θ — the same quantity as ``instrument.profile.x + phases.N.lor_size`` —
    so ``caglioti.apparent_size_from_size_coefficient`` inverts it exactly and
    with no reference angle.  0.5 deg is 15.9 nm on Cu Kα and 4.3 nm on 11-BM's
    0.4139 Å: the degrees are the same number and the specimen is not, which is
    why the clause exists.  Pinned against the helper rather than against a
    literal, and asserted on two wavelengths so a dropped λ cannot pass.
    """
    from rietx.model.profiles.caglioti import apparent_size_from_size_coefficient
    from rietx.report.layer2 import suggest_actions
    from rietx.report.schemas import TrendAnalysis, TrendTemplate

    trend = TrendAnalysis(
        observable="width", n_regions_used=8, misfit_share=0.5, separable=True,
        templates=[TrendTemplate(name="inv_cos_theta", coefficient=0.5,
                                 stderr=0.002, r2=0.95),
                   TrendTemplate(name="tan_theta", coefficient=0.0,
                                 stderr=1.0, r2=0.1)])

    def _rationale(wavelength):
        actions = suggest_actions([], [trend], [], rwp=0.1, wavelength=wavelength)
        size = [a for a in actions if a.kind == "refine_sample_size_broadening"]
        assert len(size) == 1, [a.kind for a in actions]
        return size[0].rationale

    for lam in (1.5406, 0.4139090):
        expected = apparent_size_from_size_coefficient(0.5, lam)
        assert f"L ≈ {expected:.0f} Å" in _rationale(lam)
        assert f"λ = {lam:.4f} Å" in _rationale(lam)
    # 159 Å against 43 Å: same degrees, 3.7x the physics
    assert "L ≈ 159 Å" in _rationale(1.5406)
    assert "L ≈ 43 Å" in _rationale(0.4139090)
    # no wavelength is *no claim*, not a size of zero, and the rationale the
    # caller already had is left as it was
    assert "L ≈" not in _rationale(None)
    assert _rationale(1.5406).startswith(_rationale(None))


def test_a_model_broader_than_the_data_gets_no_size_clause():
    """Scherrer read backwards would name a crystallite the specimen has not.

    A **negative** ΔΓ means the calculated peaks are too broad, so there is no
    missing size broadening to attribute — the action still stands (something
    must give the width back) but the size is withheld rather than reported as
    a negative length or a spurious positive one.
    """
    from rietx.report.layer2 import suggest_actions
    from rietx.report.schemas import TrendAnalysis, TrendTemplate

    trend = TrendAnalysis(
        observable="width", n_regions_used=8, misfit_share=0.5, separable=True,
        templates=[TrendTemplate(name="inv_cos_theta", coefficient=-0.5,
                                 stderr=0.002, r2=0.95)])
    actions = suggest_actions([], [trend], [], rwp=0.1, wavelength=1.5406)
    size = [a for a in actions if a.kind == "refine_sample_size_broadening"]
    assert len(size) == 1
    assert "L ≈" not in size[0].rationale


def test_injected_scale_error_is_recovered(truth):
    structure, ins, data = truth
    perturbed = structure.model_copy(deep=True)
    perturbed.phases[0].scale.value = 4e-4 * 0.90   # 10 % too weak

    report = _report_for(perturbed, ins, data)
    assert report.layer1_available, report.abstained_reason
    rel = _coefficients(report, "intensity")
    assert rel, "no significant intensity error detected"
    assert np.median(rel) == pytest.approx(0.10, abs=0.05)
    assert "refine_scale" in _kinds(report, active_only=False)


def test_injected_impurity_peak_is_suggested_as_a_phase(truth):
    structure, ins, data = truth
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    y = y + 900.0 * np.exp(-0.5 * ((tt - 29.35) / 0.06) ** 2)
    doped = rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                           sigma=data.sigma)

    report = _report_for(structure, ins, doped)
    assert any(u.kind == "unmatched_obs" and abs(u.two_theta - 29.35) < 0.15
               for u in report.unmatched)
    assert "add_impurity_phase" in _kinds(report, active_only=False)


# ----------------------------------------------------------------------
# the gates: the report must refuse to over-read
# ----------------------------------------------------------------------
def test_large_offset_trips_the_validity_radius_gate(truth):
    """A cell error that moves peaks many FWHM must NOT be reported as a
    confident small shift — the gate exists precisely for this."""
    structure, ins, data = truth
    perturbed = structure.model_copy(deep=True)
    perturbed.phases[0].cell = rx.Cell.cubic(4.1568 * 1.004)   # 0.4 % off

    report = _report_for(perturbed, ins, data)
    tripped = [a for a in report.attribution
               if any(f.code == "outside_validity_radius"
                      for f in a.gate_failures)]
    assert tripped, "gross peak offsets passed the validity radius unflagged"
    for a in tripped:
        assert not a.gates_passed
        assert abs(next(c.value for c in a.coefficients if c.kind == "position")) \
            > VALIDITY_RADIUS_FWHM * a.mean_fwhm


def test_immature_fit_makes_layer1_abstain():
    """With the model grossly wrong the whole layer must abstain rather than
    attribute the misfit to specific small parameter errors."""
    structure, ins, data = _truth()
    broken = structure.model_copy(deep=True)
    broken.phases[0].cell = rx.Cell.cubic(4.60)      # nowhere near
    broken.phases[0].scale.value = 4e-5

    report = _report_for(broken, ins, data)
    assert not report.layer1_available
    assert report.abstained_reason
    assert "abstained" in report.summary
    # no *parameter-level* claims survive abstention
    assert all(a.kind in ("add_impurity_phase", "reindex_or_recheck_cell")
               for a in report.suggested_actions)
    assert report.trends == []
    # the model-free layer must still work — that is its whole point
    assert report.rwp > 0.2 and report.regions
    assert report.gof > 5.0


def test_short_range_reports_position_templates_as_unseparable():
    """Over a narrow 2θ window constant/cosθ/sin2θ/tanθ are collinear; the
    report must say so instead of picking a confident winner."""
    # 20-56° 2θ gives ~6 LaB6 peak clusters (enough regions to fit the four
    # position templates) but only θ = 10-28°, over which cosθ barely varies:
    # measured template collinearity 0.9995, against 0.979 over the full
    # 18-125° range where the same templates *do* separate.
    structure, ins, data = _truth(lo=20.0, hi=56.0, seed=23)
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.02

    report = _report_for(structure, perturbed, data)
    if not report.layer1_available:
        pytest.skip(f"layer 1 abstained: {report.abstained_reason}")
    trend = next(t for t in report.trends if t.observable == "position")
    assert trend.n_regions_used >= 4
    assert trend.max_template_collinearity > 0.995
    assert trend.separability_ratio < 2.0
    assert not trend.separable
    for action in report.suggested_actions:
        if action.kind in ("refine_zero_shift", "refine_sample_displacement",
                           "refine_sample_transparency", "refine_cell"):
            assert action.confidence <= 0.3, action
            assert action.alternatives, "an unseparable call must list its rivals"


# ----------------------------------------------------------------------
# confidence calibration over an injection ensemble
# ----------------------------------------------------------------------
def test_confidence_calibration_over_injection_ensemble():
    """Design-record criterion: when the report is confident (>0.8) it should
    be right; here we check the weaker, testable version — every confident
    call on a *known* single-cause injection names the true cause among its
    active suggestions, and the top-ranked suggestion is right ≥80 % of the
    time across the ensemble."""
    structure, ins, data = _truth(seed=31)
    cases = []

    # every injection stays inside the linearisation radius — outside it the
    # correct answer is the validity gate, not an attribution
    p = ins.model_copy(deep=True)
    p.zero_shift.value = 0.008
    cases.append(("refine_zero_shift", structure, p))

    p = ins.model_copy(deep=True)
    p.geometry.sample_displacement.value = -0.02
    cases.append(("refine_sample_displacement", structure, p))

    p = ins.model_copy(deep=True)
    p.profile.w.value = 3.0e-3          # truth 4e-3
    cases.append(("refine_profile_widths", structure, p))

    s = structure.model_copy(deep=True)
    s.phases[0].scale.value = 4e-4 * 0.92
    cases.append(("refine_scale", s, ins))

    ranked_first = 0
    for expected, st, ii in cases:
        report = _report_for(st, ii, data)
        assert report.layer1_available, f"{expected}: {report.abstained_reason}"
        kinds = _kinds(report, active_only=False)
        assert kinds, f"{expected}: no suggestions at all"

        # position causes are mutually substitutable when collinear
        family = {
            "refine_zero_shift": {"refine_zero_shift", "refine_sample_displacement",
                                  "refine_sample_transparency", "refine_cell"},
            "refine_sample_displacement": {"refine_sample_displacement",
                                           "refine_zero_shift", "refine_cell"},
            "refine_profile_widths": {"refine_profile_widths",
                                      "refine_sample_size_broadening",
                                      "refine_sample_strain_broadening"},
            "refine_scale": {"refine_scale", "refine_biso"},
        }[expected]
        assert family & set(kinds), f"{expected}: true cause absent, got {kinds}"
        if kinds[0] in family:
            ranked_first += 1

        # any *high-confidence* call must be in the true cause's family
        for a in report.suggested_actions:
            if a.confidence > 0.8:
                assert a.kind in family, (
                    f"{expected}: confident ({a.confidence}) but wrong: {a.kind}")

    assert ranked_first >= 0.8 * len(cases), (
        f"true cause ranked first in only {ranked_first}/{len(cases)} cases")


# ----------------------------------------------------------------------
# Layer 2 machinery
# ----------------------------------------------------------------------
def test_strategy_veto_marks_planned_actions_inactive(truth):
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.02
    plan = rx.RefinementPlan.lab_bragg_brentano()

    report = _report_for(structure, perturbed, data, plan=plan)
    zero = report.action("refine_zero_shift")
    assert not zero.active, "the plan already refines zero — must be vetoed"
    assert zero.vetoed_by and "staged plan" in zero.vetoed_by


def test_veto_by_already_free_parameters(truth):
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.02
    report = _report_for(structure, perturbed, data,
                         free_paths=["instrument.zero_shift"])
    zero = report.action("refine_zero_shift")
    assert not zero.active
    assert "already free" in (zero.vetoed_by or "")


def test_predict_then_verify_accepts_a_real_improvement(truth):
    """Verification must accept an action that genuinely helps, and the
    rollback must leave the parent state untouched."""
    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.02

    ref = rx.Refinement(structure, start)
    ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"])]))
    chi2_before = ref.result_.statistics.chi2

    action = rx.SuggestedAction(kind="refine_zero_shift", confidence=0.9,
                                rationale="test", parameter_paths=["instrument.zero_shift"])
    outcome = predict_then_verify(ref, data, action)
    assert outcome.accepted, outcome.reason
    assert outcome.observed_delta_chi2 > 0
    # the parent refinement is untouched: verification ran on a branch
    assert ref.result_.statistics.chi2 == chi2_before
    # the pair rides beside the verdict (WP-1417): measured from where the
    # restricted fit held the zero
    [freed] = outcome.comparison.freed
    assert freed.path == "instrument.zero_shift" and freed.held_at == 0.02
    assert abs(freed.t_ratio) > 10 and outcome.comparison.delta_bic > 10


def test_predict_then_verify_rejects_a_useless_action(truth):
    structure, ins, data = truth
    ref = rx.Refinement(structure, ins.model_copy(deep=True))
    ref.fit(data, plan="lab_bragg_brentano")

    useless = rx.SuggestedAction(
        kind="refine_sample_transparency", confidence=0.2, rationale="test",
        parameter_paths=["instrument.geometry.sample_transparency"])
    outcome = predict_then_verify(ref, data, useless)
    assert not outcome.accepted
    assert "rolled back" in outcome.reason
    [freed] = outcome.comparison.freed
    assert freed.path == "instrument.geometry.sample_transparency"
    assert abs(freed.t_ratio) < 3 and outcome.comparison.delta_bic < 0


def test_veto_helper_is_pure_annotation():
    actions = [rx.SuggestedAction(kind="refine_cell", confidence=0.9,
                                  rationale="x", parameter_paths=["phases.*.cell.*"])]
    out = apply_strategy_veto(actions, rx.RefinementPlan.mccusker_default())
    assert len(out) == 1                    # never dropped, only annotated
    assert not out[0].active
    assert out[0].confidence == 0.9         # and the reasoning is preserved


# ----------------------------------------------------------------------
# texture → typed action (the WP-0307 orphan, claimed by WP-0602)
# ----------------------------------------------------------------------
def _texture(detected=True, r2=0.82, runner_r2=0.1, **kw):
    from rietx.report import TextureAnalysis

    # best_axis is always populated since WP-1054 (evidence, not a verdict);
    # ``detected`` alone decides whether an action is emitted
    base = dict(phase_index=0, best_axis=(0, 0, 1),
                march_coefficient=0.71, r2=r2, n_reflections_used=17,
                detected=detected, runner_up_axis=(1, 1, 0),
                runner_up_r2=runner_r2)
    base.update(kw)
    return TextureAnalysis(**base)


def test_texture_action_emitted_only_when_detected():
    from rietx.report import texture_actions

    assert texture_actions([]) == []
    assert texture_actions([_texture(detected=False)]) == []

    (action,) = texture_actions([_texture()])
    assert action.kind == "refine_preferred_orientation"
    assert action.parameter_paths == ["phases.0.preferred_orientation.r"]
    assert action.confidence == pytest.approx(0.82, abs=1e-6)
    assert "(0, 0, 1)" in action.rationale and "r=0.710" in action.rationale
    # the linear-model Δχ² covers gated regions, not this per-reflection score
    assert action.expected_delta_chi2 is None


def test_texture_action_ambiguous_axis_caps_confidence():
    from rietx.report import texture_actions

    (action,) = texture_actions([_texture(runner_r2=0.75)])
    assert action.confidence <= 0.4
    assert "not cleanly resolved" in action.rationale
    assert "(1, 1, 0)" in action.rationale        # runner-up named, per §6


def test_texture_action_is_vetoed_by_a_plan_that_frees_r():
    from rietx.report import texture_actions

    actions = texture_actions([_texture()])
    out = apply_strategy_veto(actions, rx.RefinementPlan.mccusker_structural())
    assert not out[0].active                       # plan already frees r
    out = apply_strategy_veto(texture_actions([_texture()]),
                              rx.RefinementPlan.mccusker_default())
    assert out[0].active                           # profile-only plan does not


# ----------------------------------------------------------------------
# statistical justification for new parameters
# ----------------------------------------------------------------------
def test_hamilton_test_and_bic_agree_on_a_real_improvement():
    # χ² here is the raw Σw·Δ², so a well-scaled fit has χ² ≈ N − P.
    # A 200-unit drop for one added parameter over 5000 points is decisive.
    assert hamilton_justified(5000.0, 4800.0, n_points=5000,
                              n_free_restricted=10, n_added=1)
    assert delta_bic(5000.0, 4800.0, n_points=5000, n_added=1) > 0


def test_hamilton_test_rejects_a_cosmetic_improvement():
    # under the null each added parameter absorbs ~1 unit of χ² by itself,
    # so a drop of 1 is exactly what noise buys — F ≈ 1, not significant
    assert not hamilton_justified(5000.0, 4999.0, n_points=5000,
                                  n_free_restricted=10, n_added=1)
    assert delta_bic(5000.0, 4999.0, n_points=5000, n_added=1) < 0


def test_plot_for_vlm_writes_png_only(tmp_path, truth):
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.008
    report = _report_for(structure, perturbed, data)

    # rebuild the bare result for plotting
    from rietx.viz.plots import plot_for_vlm
    ref = rx.Refinement(structure, perturbed, history=False)
    result = ref.fit(data, plan=rx.RefinementPlan(stages=[
        rx.Stage("bkg", ["instrument.background.*"])]))

    with pytest.raises(ValueError, match="PNG"):
        plot_for_vlm(result, report, path=str(tmp_path / "montage.jpg"))
    out = tmp_path / "montage.png"
    plot_for_vlm(result, report, path=str(out))
    assert out.exists() and out.stat().st_size > 20_000
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_hamilton_rejects_degenerate_inputs():
    assert not hamilton_justified(100.0, 100.0, n_points=10,
                                  n_free_restricted=9, n_added=5)
    assert not hamilton_justified(100.0, 0.0, n_points=500,
                                  n_free_restricted=5, n_added=1)


# ----------------------------------------------------------------------
# WP-1054 — Layer-2 honesty on the abstained branch
# ----------------------------------------------------------------------
_OUT = Path(__file__).parent / "output"


def _plot_state(structure, ins, data, stem):
    """obs/calc/diff PNGs to tests/output/ (gitignored), full range + a
    low-angle zoom — house convention: Rwp hides locally-bad fits."""
    from rietx.viz.plots import plot_result

    result, _, _ = _result_for(structure, ins, data)
    _OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(_OUT / f"{stem}.png"))
    plot_result(result, path=str(_OUT / f"{stem}_zoom.png"),
                two_theta_range=(18.0, 45.0))


def _broad_truth(lor_size, seed=17):
    """The `_truth` recipe with Lorentzian size broadening in the *data*, so
    the unperturbed model matches the broad peaks exactly."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure, ins, _ = _truth(seed=seed)
    structure = structure.model_copy(deep=True)
    structure.phases[0].lor_size.value = lor_size
    tt = np.arange(18.0, 125.0, 0.02)
    grid = rx.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(structure, ins, grid, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y_noisy = rng.poisson(np.maximum(y, 1.0) * _COUNT_SCALE) / _COUNT_SCALE
    data = rx.PatternData(
        two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
        sigma=np.sqrt(np.maximum(y, 1.0) / _COUNT_SCALE).tolist())
    return structure, ins, data


def _doped(data, two_theta=29.35, height=900.0, width=0.06):
    """The impurity doping recipe: one foreign Gaussian on top of the data."""
    tt = np.asarray(data.two_theta)
    y = np.asarray(data.intensity, dtype=float)
    y = y + height * np.exp(-0.5 * ((tt - two_theta) / width) ** 2)
    return rx.PatternData(two_theta=tt.tolist(), intensity=y.tolist(),
                          sigma=data.sigma)


def test_wrong_cell_abstained_leads_with_reindex(truth):
    """The WP-1054 headline state: a +0.4 % cell error abstains (correctly)
    and its displaced peaks read as 32 unmatched lines — before the WP the
    only surviving action was ``add_impurity_phase`` at 0.9, the phantom-phase
    invitation an on-haiku consumer quoted verbatim in WP-1053's pilot.  Now
    the abstained branch leads with the position-family pointer and the
    impurity call is capped, evidence intact on both."""
    from rietx.report.schemas import IMPURITY_SHIFT_CAP

    structure, ins, data = truth
    perturbed = structure.model_copy(deep=True)
    perturbed.phases[0].cell = rx.Cell.cubic(4.1568 * 1.004)

    report = _report_for(perturbed, ins, data)
    assert report.abstained_reason, "a 0.4 % cell error must abstain"

    # Layer-0 evidence is untouched: those peaks *are* unmatched
    strong = [u for u in report.unmatched
              if u.kind == "unmatched_obs" and u.height_over_sigma > 8.0]
    assert len(strong) >= 20, len(strong)

    # the verdict layer: reindex tops the active set, carrying the whole
    # position family — never a confident reindex singleton
    active = [a for a in report.suggested_actions if a.active]
    assert active and active[0].kind == "reindex_or_recheck_cell", (
        [a.kind for a in active])
    assert active[0].confidence <= 0.5, active[0]
    assert set(active[0].alternatives) == {"refine_zero_shift",
                                           "refine_sample_displacement"}
    assert "have not chosen" in active[0].rationale
    assert "lower bound" in active[0].rationale     # saturated-fit honesty

    impurity = report.action("add_impurity_phase")
    assert impurity.confidence <= IMPURITY_SHIFT_CAP, impurity
    assert impurity.alternatives[0] == "reindex_or_recheck_cell", impurity
    assert f"all {len(strong)} unmatched" in impurity.rationale
    assert "re-check the cell" in impurity.rationale

    _plot_state(perturbed, ins, data, "wp1054_cell_wrong_abstained")


def test_abstained_branch_actions_carry_execution_too(truth):
    """The ``execution`` stamp is on both exits of ``build_report`` (WP-1106) —
    abstention included, where the actions matter most (WP-1054's point)."""
    from rietx.report.apply import RECIPES

    structure, ins, data = truth
    perturbed = structure.model_copy(deep=True)
    perturbed.phases[0].cell = rx.Cell.cubic(4.1568 * 1.004)
    report = _report_for(perturbed, ins, data)
    assert report.abstained_reason and report.suggested_actions
    for action in report.suggested_actions:
        assert action.execution == RECIPES[action.kind].how, action.kind


def test_broad_peak_lobes_cap_impurity_without_reindex():
    """The broad-peak variant: residual lobes of 0.66°-wide peaks under a
    0.05° zero error read as unmatched (the 0.08° matching tolerance is tiny
    against the peak), and pre-WP they bought ``add_impurity_phase`` at 0.7.
    They all sit within a fraction of a FWHM of a calculated position, so the
    call is capped — and *no* reindex pointer is emitted, because the
    validity failures here are saturated-fit artefacts (4 of 12 misfitting
    regions, below the widespread-failure fraction; the true shift is inside
    the validity radius of these broad peaks)."""
    from rietx.report.schemas import IMPURITY_SHIFT_CAP

    structure, ins, data = _broad_truth(0.6)
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.05

    report = _report_for(structure, perturbed, data)
    assert report.abstained_reason, "the lobes must abstain the report"
    strong = [u for u in report.unmatched
              if u.kind == "unmatched_obs" and u.height_over_sigma > 8.0]
    assert strong, "the residual lobes must still appear as unmatched"

    impurity = report.action("add_impurity_phase")
    assert impurity.confidence <= IMPURITY_SHIFT_CAP, impurity
    assert impurity.alternatives[0] == "reindex_or_recheck_cell", impurity
    assert "reindex_or_recheck_cell" not in [a.kind
                                             for a in report.suggested_actions]

    _plot_state(structure, perturbed, data, "wp1054_broad_zero_lobes")


def test_impurity_no_longer_outranked_by_manufactured_texture(truth):
    """A pure impurity injection once leaked into the per-reflection
    extraction and manufactured a (1,0,1) texture detection at R²=0.66 that
    outranked the impurity call 0.66 vs 0.40 (measured 2026-08-11; WP-1054
    then capped the verdict).  WP-1112's area-criterion windows cut the leak
    at its root — the foreign line at 29.35° no longer falls inside any
    calculated neighbour's window, and the same injection measures R² ≈ 0.01
    — so the pin is now the stronger claim: no texture is detected at all
    and the impurity call stands alone.  The capping verdict layer keeps its
    own regression in ``test_texture_crosstalk_cap_is_pinned_directly``."""
    structure, ins, data = truth
    doped = _doped(data)

    report = _report_for(structure, ins, doped)
    impurity = report.action("add_impurity_phase")
    assert impurity.confidence >= 0.4
    kinds = [a.kind for a in report.suggested_actions]
    assert "refine_preferred_orientation" not in kinds

    tex = report.texture[0]
    assert not tex.detected
    assert tex.r2 < 0.1        # the manufactured 0.66 is gone at the root
    assert tex.caveat is None  # nothing to annotate when nothing is detected

    _plot_state(structure, ins, doped, "wp1054_impurity_texture")


def test_texture_crosstalk_cap_is_pinned_directly():
    """The verdict layer of WP-1054's third sighting, exercised directly.

    WP-1112's windows cut the end-to-end leak on the injection fixtures
    around this test, so the coincidence the cap guards — a texture
    detection beside a strong unmatched observed peak — is constructed here
    rather than manufactured: the detection cannot outrank the impurity
    action that likely feeds it, the mechanism is stated in both the action
    and the analysis, and the evidence itself is preserved untouched."""
    from rietx.report import cap_texture_crosstalk
    from rietx.report.layer2 import IMPURITY_SIGMA
    from rietx.report.schemas import (
        TEXTURE_IMPURITY_MARGIN,
        SuggestedAction,
        TextureAnalysis,
        UnmatchedPeak,
    )

    tex = TextureAnalysis(phase_index=0, best_axis=(1, 0, 1),
                          march_coefficient=0.7, r2=0.66,
                          n_reflections_used=12, detected=True)
    actions = [
        SuggestedAction(kind="add_impurity_phase", confidence=0.4,
                        rationale="unmatched line at 29.34"),
        SuggestedAction(kind="refine_preferred_orientation", confidence=0.66,
                        rationale="texture detected"),
    ]
    unmatched = [UnmatchedPeak(two_theta=29.34,
                               height_over_sigma=IMPURITY_SIGMA + 20.0,
                               kind="unmatched_obs")]
    out = cap_texture_crosstalk(actions, [tex], unmatched)
    po = next(a for a in out if a.kind == "refine_preferred_orientation")
    imp = next(a for a in out if a.kind == "add_impurity_phase")
    assert po.confidence == pytest.approx(
        imp.confidence - TEXTURE_IMPURITY_MARGIN)
    assert po.alternatives[0] == "add_impurity_phase"
    assert "manufacture" in po.rationale
    assert tex.caveat and "manufacture" in tex.caveat
    assert tex.r2 == 0.66 and tex.best_axis == (1, 0, 1)  # evidence untouched


def test_double_injection_keeps_the_impurity_call(truth):
    """The regression control: a 0.05° zero error *and* a genuine foreign
    line at 29.34°.  The report abstains and the position evidence is
    widespread (10 of 14 misfitting regions beyond the radius), yet the
    foreign line pairs with nothing — nearest missing calculated line 1.18°
    away, outside the 1.0° pairing window — so the impurity call keeps its
    full strength beside the reindex pointer instead of drowning in it."""
    structure, ins, data = truth
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.05
    doped = _doped(data)

    report = _report_for(structure, perturbed, doped)
    assert report.abstained_reason

    impurity = report.action("add_impurity_phase")
    assert impurity.confidence == pytest.approx(0.4, abs=1e-6), impurity
    assert "29.34" in impurity.rationale     # the genuine line, named
    kinds = [a.kind for a in report.suggested_actions]
    assert "reindex_or_recheck_cell" in kinds
    # no manufactured texture arises to cap: the WP-1112 windows cut the
    # extraction leak at its root (the test above measures it)
    assert "refine_preferred_orientation" not in kinds

    _plot_state(structure, perturbed, doped, "wp1054_double_injection")


# ----------------------------------------------------------------------
# WP-1057: purpose-grade evidence — the Le Bail gap, the resolution-limited
# abstention flavour, and the contents-type intensity clause
# ----------------------------------------------------------------------
def _pore_proxy_data(seed=17):
    """Data from LaB₆ + a guest scatterer (O at the 1b site, occ 0.6,
    Biso 2.0) — the WP-1057 pore-content proxy.  The returned host model
    never contains the guest, so its intensity model is wrong in the
    interference-coupled way real pore contents are: at (½,½,½) the guest's
    phase factor is (−1)^(h+k+l), so per-reflection errors alternate in sign
    by parity — never a scale, ADP or texture signature."""
    structure, ins, _ = _truth(seed=seed)
    doped = structure.model_copy(deep=True)
    doped.phases[0].atoms.append(rx.Atom(
        label="Oguest", species="O",
        x=rx.Parameter(value=0.5), y=rx.Parameter(value=0.5),
        z=rx.Parameter(value=0.5),
        occ=rx.Parameter(value=0.6), biso=rx.Parameter(value=2.0)))
    tt = np.arange(18.0, 125.0, 0.02)
    grid = rx.PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    model = compile_model(doped, ins, grid, mode="rietveld")
    table = ParameterTable(doped, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(seed)
    y_noisy = rng.poisson(np.maximum(y, 1.0) * _COUNT_SCALE) / _COUNT_SCALE
    data = rx.PatternData(
        two_theta=model.tt.tolist(), intensity=y_noisy.tolist(),
        sigma=np.sqrt(np.maximum(y, 1.0) / _COUNT_SCALE).tolist())
    return structure, ins, data


def test_pore_proxy_gap_and_contents_clause():
    """The WP-1057 headline scenario: a converged host fit over data whose
    scattering contents it lacks.  Measured (2026-08-12): Rwp 0.0405,
    GoF 2.97, partition Rwp 0.0170 → ratio 2.38; intensity carries 83 % of
    the misfit in 8 gated regions split 5+/3−, best angular template
    R² = 0.011.  The report must carry the gap and name the contents
    signature — and still invent no action, because none applies."""
    structure, ins, data = _pore_proxy_data()
    ref = rx.Refinement(structure, ins)
    result = ref.fit(data, plan="mccusker_default")
    report = ref.report()

    assert report.layer1_available, report.abstained_reason
    gap = report.lebail_gap
    assert gap is not None
    assert gap.rwp_rietveld == pytest.approx(result.statistics.rwp, rel=1e-6)
    assert gap.rwp_lebail < gap.rwp_rietveld
    assert gap.ratio > 2.0, gap                    # measured 2.38
    assert "Le Bail partition" in report.summary
    assert "intensity model carries the misfit" in report.summary

    # the contents-type clause names the pattern; the evidence stays where
    # it always was, in the gated per-region coefficients
    assert "alternate in sign" in report.summary
    assert "un-modelled scattering contents" in report.summary
    sig = [c.value for a in report.attribution if a.gates_passed
           for c in a.coefficients if c.kind == "intensity" and c.significant]
    assert sum(1 for v in sig if v > 0) >= 2, sig
    assert sum(1 for v in sig if v < 0) >= 2, sig

    # honest silence preserved: naming the inference must not manufacture
    # actions the closed vocabulary cannot express
    assert not [a for a in report.suggested_actions if a.active]

    _plot_state(ref.fitted_structure, ref.fitted_instrument, data,
                "wp1057_pore_proxy")


def test_broad_abstention_is_resolution_limited():
    """The broad-peak abstention names the data's resolution, not model
    error: gram failures dominate the tally (measured 12 of 12 failing
    regions, 5 failing nothing else at median local R² 0.957) and the gap
    stays flat (measured ratio 1.00 — the partition's peaks are displaced
    identically, so position misfit can never masquerade as an intensity
    story)."""
    structure, ins, data = _broad_truth(0.6)
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.05

    report = _report_for(structure, perturbed, data)
    assert report.abstained_reason
    assert report.abstained_kind == "resolution_limited"
    assert "Resolution-limited" in report.abstained_reason
    assert "not evidence the model is wrong" in report.abstained_reason
    assert "indistinguishable" in report.abstained_reason

    assert report.lebail_gap is not None
    assert report.lebail_gap.ratio < LEBAIL_GAP_NOTABLE, report.lebail_gap
    assert "Le Bail partition" not in report.summary

    _plot_state(structure, perturbed, data, "wp1057_broad_resolution_limited")


def test_resolution_limited_abstention_emits_collect_better_data():
    """``collect_better_data``'s one writer, firing (WP-1106).

    On the resolution-limited abstention the data, not the model, is what the
    report ran out of — so the data-quality reading leads the list, above the
    shift-capped phantom-impurity call (0.5 against 0.3 measured here), with
    the instrument-vs-specimen fork stated in its rationale rather than
    resolved by fiat.  The other candidate writer, a
    ``PATTERN_UNDERSAMPLED``-conditioned emission, was measured and rejected:
    every bundled synthetic fixture trips that diagnostic beside converged
    GoF ≈ 1.01 fits (the E2 loop test's ``suggested_actions == []`` on such a
    fixture is the standing pin), so it would have stamped this action onto
    reports whose data supported the whole refinement.
    """
    from rietx.report.schemas import COLLECT_DATA_CONFIDENCE, IMPURITY_SHIFT_CAP

    structure, ins, data = _broad_truth(0.6)
    perturbed = ins.model_copy(deep=True)
    perturbed.zero_shift.value = 0.05

    report = _report_for(structure, perturbed, data)
    assert report.abstained_kind == "resolution_limited"
    top = report.suggested_actions[0]
    assert top.kind == "collect_better_data"
    assert top.confidence == COLLECT_DATA_CONFIDENCE > IMPURITY_SHIFT_CAP
    assert top.execution == "advice" and top.parameter_paths == []
    assert "no re-measurement sharpens it" in top.rationale
    assert "narrower receiving slit" in top.rationale

    # the sharp converged reference stays silent — the writer is the
    # abstention flavour, not the breadth of the peaks
    sharp = _report_for(*_truth())
    assert "collect_better_data" not in [a.kind for a in sharp.suggested_actions]


def test_sharp_converged_reference_stays_silent(truth):
    """The no-noise control: a converged correct model gets the gap field
    (measured ratio 1.00 — the partition is not a noise-floor estimator, so
    ≲ 1 is the healthy reading) and neither summary clause, and no
    abstention kind."""
    structure, ins, data = truth
    report = _report_for(structure, ins, data)

    assert report.layer1_available and report.abstained_kind is None
    gap = report.lebail_gap
    assert gap is not None
    assert gap.ratio < LEBAIL_GAP_NOTABLE, gap
    assert "Le Bail partition" not in report.summary
    assert "alternate in sign" not in report.summary

    _plot_state(structure, ins, data, "wp1057_sharp_reference")


def test_wrong_cell_abstentions_classify_as_model_error(truth):
    """The classifier must never read a wrong cell as resolution-limited.
    The +0.4 % state fails the Gram gate in 8 of its 10 failing regions too
    — which is why gram dominance alone cannot separate the flavours — and
    classifies "immature" on the Rwp arm (0.72); a milder +0.1 % state
    (Rwp 0.33) abstains via the explained-fraction clause with widespread
    validity failures and defers to the position family: "unreadable", the
    reindex pointer leading, no resolution wording."""
    structure, ins, data = truth

    p = structure.model_copy(deep=True)
    p.phases[0].cell = rx.Cell.cubic(4.1568 * 1.004)
    report = _report_for(p, ins, data)
    assert report.abstained_kind == "immature"

    p2 = structure.model_copy(deep=True)
    p2.phases[0].cell = rx.Cell.cubic(4.1568 * 1.001)
    report2 = _report_for(p2, ins, data)
    assert report2.abstained_kind == "unreadable"
    assert "Resolution-limited" not in (report2.abstained_reason or "")
    assert any(a.kind == "reindex_or_recheck_cell"
               for a in report2.suggested_actions)


# ----------------------------------------------------------------------
# WP-1055 — background evidence (the failure-mode fixtures live in
# test_background_auto.py, beside the guard whose measurement they carry)
# ----------------------------------------------------------------------
def test_converged_reference_publishes_the_background_section_and_stays_quiet(
        truth):
    """The clean control: the section is always there, the summary is not.

    Also the ``None`` case for the absorption table — this report is built
    from a hand-assembled result with no fit behind it, so nothing measured a
    Jacobian.  ``absorption is None`` must read as "not measured here", which
    is why it is None rather than an empty dict that would look like a clean
    bill of health.
    """
    structure, ins, data = truth
    report = _report_for(structure, ins, data)
    bg = report.background

    assert bg is not None
    assert bg.absorption is None and bg.worst_absorption == 0.0
    assert bg.rwp == pytest.approx(report.rwp)
    assert bg.rwp_background_subtracted > bg.rwp        # measured 0.049 vs 0.014
    assert bg.background_share > 0.5                    # measured 0.89
    assert bg.off_region_durbin_watson == pytest.approx(2.0, abs=0.2)
    assert bg.off_region_chi2_reduced == pytest.approx(1.0, abs=0.3)

    assert "background" not in report.summary
    assert not [a for a in report.suggested_actions
                if a.kind.endswith("_background_flexibility")]


def test_lebail_gap_mechanics(truth):
    """The partition borrows the caller's model: mode and per-hkl buffers
    are flipped and must come back bit-exact (the model keeps serving the
    session).  In Le Bail mode the gap is absent for cause — None, never a
    fabricated 1.0."""
    from rietx.report import lebail_gap

    structure, ins, data = truth
    result, model, values = _result_for(structure, ins, data)
    y_before = model.evaluate(values)
    gap = lebail_gap(model, values, rwp_rietveld=result.statistics.rwp)
    assert gap is not None and gap.rwp_lebail > 0
    assert model.mode == "rietveld"
    assert all(cp.hkl_intensity is None for cp in model.phases)
    assert np.array_equal(model.evaluate(values), y_before)

    lb = compile_model(structure, ins, data, mode="lebail")
    assert lebail_gap(lb, values, rwp_rietveld=0.1) is None


# ----------------------------------------------------------------------
# WP-1056 — identifiability: is the converged answer the only one?
# ----------------------------------------------------------------------
def _fit_and_report(structure, start_ins, data, stem, plan="mccusker_default",
                    zoom=(18.0, 45.0)):
    """One staged fit to convergence, its report, and the house PNGs."""
    from rietx.viz.plots import plot_result

    ref = rx.Refinement(structure, start_ins)
    result = ref.fit(data, plan=plan)
    report = ref.report()
    _OUT.mkdir(exist_ok=True)
    plot_result(result, path=str(_OUT / f"{stem}.png"))
    plot_result(result, path=str(_OUT / f"{stem}_zoom.png"),
                two_theta_range=zoom)
    return ref, result, report


def _exchange(report, held):
    for row in report.identifiability.exchanges or []:
        if row.held == held:
            return row
    raise AssertionError(f"no exchange row for {held}: "
                         f"{report.identifiability.exchanges}")


def _assert_exchange_clause_shape(summary):
    """The three properties the exchange clause must keep (WP-1063), asserted
    as *shape* rather than as a second copy of the sentence.

    A pin holding a duplicate of a string that lives in the source is the
    guard that goes quiet (``tests/CLAUDE.md`` § Guards that go quiet): it
    passes while the two drift apart.  What is load-bearing here is not the
    wording but that the sentence (1) claims about this **fit** and not about
    the data, (2) names the forbidden action beside the sanctioned one, since
    naming only the degeneracy is what invited seven of twenty WP-1059 cells
    onto the ridge, and (3) says which value the held rival takes in the
    experiment — 1003's "held with the rival free" was underspecified, and the
    lazy converged state is not one of the two rivals.

    WP-1065 adds (4): the sentence says what the experiment's outcome
    *licenses*, on both branches, quoting the strength grade from
    ``RIVAL_DECISIVE_MIN_CHI2_RATIO`` rather than restating it — round 3's
    solvable control went 0/7 valid because agents ran the swap, won it, and
    had nowhere to read that winning it is an answer — and it does so without
    smuggling a verdict token; the verdict stays the reader's.
    """
    from rietx.report import RIVAL_DECISIVE_MIN_CHI2_RATIO

    assert "this fit cannot tell" in summary          # the claim's level
    assert "never by freeing both" in summary         # the forbidden action
    assert "ridge" in summary
    assert "held at its null" in summary              # which value
    assert "compare χ²" in summary                    # the experiment
    # the follow-through (WP-1065): what the outcome licenses, both branches,
    # with the strength grade quoted live from the named constant
    assert f"≥ {RIVAL_DECISIVE_MIN_CHI2_RATIO - 1:.0%}" in summary
    assert "data has chosen" in summary               # the decisive license
    assert "without caveat" in summary
    assert "not chosen" in summary                    # the tie branch stated
    assert "ambiguous" not in summary                 # no smuggled verdict
    assert "compare_rivals" not in summary            # not the API
    assert "the data cannot tell" not in summary      # the pre-0.8 claim


def test_position_templates_and_actions_agree_geometry_by_geometry():
    """Every action has a template, and every template an action — except the
    two flat-plate-transmission shapes withdrawn on purpose.

    The two tables are keyed by geometry separately (evidence in
    ``layer1.POSITION_TEMPLATES``, actions in
    ``layer2._POSITION_ACTIONS_BY_GEOMETRY``), and the failure they can have is
    silent in both directions: a template with no action goes unexplained where
    an action was meant, and an action with no template is unreachable code
    that reads as coverage.  The geometry keys are checked against the
    ``Geometry.kind`` Literal rather than listed, so a fourth geometry cannot
    ship with no position vocabulary (WP-1073).

    ``flat_plate_transmission`` is the ruled exception (WP-1003):
    ``cos_theta``/``sin_2theta`` stay offered as evidence — the diagnosis is
    right there, a flat specimen off the axis — and map to no action, because
    both would name parameters the table force-fixes.  The gap is asserted
    *exactly*, so a template dropped or an action added by accident still
    fails.
    """
    import typing

    from rietx.report.layer1 import POSITION_TEMPLATES
    from rietx.report.layer2 import _POSITION_ACTIONS_BY_GEOMETRY
    from rietx.schemas.instrument import Geometry

    kinds = set(typing.get_args(Geometry.model_fields["kind"].annotation))
    assert set(POSITION_TEMPLATES) == kinds
    assert set(_POSITION_ACTIONS_BY_GEOMETRY) == kinds
    for geometry, names in POSITION_TEMPLATES.items():
        offered = set(names)
        acted = set(_POSITION_ACTIONS_BY_GEOMETRY[geometry])
        assert acted <= offered, geometry     # no unreachable action anywhere
        expected_gap = ({"cos_theta", "sin_2theta"}
                        if geometry == "flat_plate_transmission" else set())
        assert offered - acted == expected_gap, geometry
    # and in *every* geometry each suggested path is one that geometry's own
    # table can free — the defect that motivated the keying was a capillary
    # fit being told to refine ``sample_displacement``, which ParameterTable
    # force-fixes there, and the flat-plate rows repeated it (WP-1003).
    # Asked of a real table rather than of a second list, because a list would
    # be the same claim written twice.
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import Instrument

    instruments = {
        "bragg_brentano": Instrument.bragg_brentano(),
        "debye_scherrer": Instrument.debye_scherrer(wavelength=1.5406,
                                                    goniometer_radius_mm=200.0),
        "flat_plate_transmission": Instrument.flat_plate_transmission(),
    }
    assert set(instruments) == kinds
    for geometry, ins in instruments.items():
        table = ParameterTable(make_lab6(), ins)
        for _name, (kind, path) in _POSITION_ACTIONS_BY_GEOMETRY[
                geometry].items():
            assert table.set_vary([path], True), (
                f"{kind} names an unfreeable {path} on {geometry}")


def test_exchange_candidate_families_are_pinned():
    """The scan's family list and null table are protocol, not tuning: a
    session that widens them changes what every report can say, so both are
    pinned here (WP-1056 'family list documented and pinned by test')."""
    from rietx.optimize.identifiability import EXCHANGE_CANDIDATE_GLOBS, NULL_IDENTITY

    assert EXCHANGE_CANDIDATE_GLOBS == [
        "instrument.zero_shift",
        "instrument.geometry.sample_displacement",
        "instrument.geometry.sample_transparency",
        "instrument.geometry.capillary_offset_along_beam",
        "instrument.geometry.capillary_offset_across_beam",
        "phases.*.cell.*",
        "phases.*.scale",
        "phases.*.atoms.*.biso",
        "instrument.profile.u",
        "instrument.profile.v",
        "instrument.profile.w",
        "instrument.profile.x",
        "instrument.profile.y",
    ]
    # nulls exist exactly for the aberration corrections (identity at zero);
    # a cell edge or a scale has no null, so no exchange sentence can rest
    # on one — the report-side half of the two-condition discriminator
    assert NULL_IDENTITY == {
        "instrument.zero_shift": 0.0,
        "instrument.geometry.sample_displacement": 0.0,
        "instrument.geometry.sample_transparency": 0.0,
        "instrument.geometry.capillary_offset_along_beam": 0.0,
        "instrument.geometry.capillary_offset_across_beam": 0.0,
    }
    # every family carrying a null is an aberration, and every aberration in
    # the model has a family: the two lists cannot drift on the half that
    # matters, which is the one the discriminator reads
    assert set(NULL_IDENTITY) <= set(EXCHANGE_CANDIDATE_GLOBS)


def test_final_jacobian_is_undamped(truth):
    """Watkin (2008) §3.8: correlations are honest only if the final-cycle
    normal matrix is undamped.  Both drivers return the Jacobian evaluated at
    the accepted solution — asserted against a fresh evaluation at
    ``outcome.theta``, which a Marquardt-damped or stale-iterate matrix would
    not reproduce."""
    from rietx.optimize.least_squares import _make_jacobian, run_least_squares

    structure, ins, data = _truth()
    structure = structure.model_copy(deep=True)
    ins = ins.model_copy(deep=True)
    table = ParameterTable(structure, ins)
    table.set_vary(["*"], False)
    table.set_vary(["instrument.zero_shift", "phases.*.cell.*",
                    "phases.*.scale"], True)
    model = compile_model(structure, ins, data, mode="rietveld")
    outcome = run_least_squares(model, table)
    fresh = np.asarray(_make_jacobian(model, table)(outcome.theta))
    assert outcome.jac is not None
    assert np.allclose(outcome.jac, fresh, rtol=1e-12, atol=0.0), (
        np.max(np.abs(outcome.jac - fresh)))


def test_e2_converged_report_names_the_exchange(truth):
    """The WP-1053 E2 miss, closed: the baseline preset absorbs a planted
    −0.02 mm displacement into a compensating zero (χ²_red ≈ 1.01, spike
    table in the WP handover) and before this WP the *converged* report
    carried no trace of it.  Now the summary names the pair and the row
    carries the evidence: R² = 0.9999 with the partner 128σ from its null."""
    from rietx.report import is_exchangeable
    from rietx.report.schemas import EXCHANGE_PARTNER_MIN_SIGNIFICANCE, EXCHANGEABLE_MIN_R2

    structure, ins, data = truth
    start = ins.model_copy(deep=True)
    start.geometry.sample_displacement.value = -0.02
    ref, result, report = _fit_and_report(structure, start, data, "wp1056_e2")
    assert ref.fitted_instrument.geometry.sample_displacement.value == -0.02

    row = _exchange(report, "instrument.geometry.sample_displacement")
    assert row.r2 > EXCHANGEABLE_MIN_R2                    # measured 0.9999
    assert row.partner == "instrument.zero_shift"
    assert row.partner_significance > 20 * EXCHANGE_PARTNER_MIN_SIGNIFICANCE
    assert row.exchangeable and is_exchangeable(row.r2, row.partner_significance)
    # the loadings name the compensators: zero first, then the cell edge
    assert abs(row.partners["instrument.zero_shift"]) > 1.0
    assert "exchangeable with the held instrument.geometry.sample_displacement" \
        in report.summary
    _assert_exchange_clause_shape(report.summary)
    assert "ambiguous" not in report.summary  # the verdict is the reader's
    # transparency rides the same fitted zero — honest multiplicity, in the
    # table (measured R² 0.97) while the summary names only the worst row
    assert _exchange(report, "instrument.geometry.sample_transparency").exchangeable
    # the same sentence beside the numbers (WP-1108): one render, two writes,
    # pinned as the exact appended substring — the shim projection's needle
    clause = result.statistics.identifiability_clause
    assert clause is not None and ("; " + clause) in report.summary


def test_clean_reference_stays_quiet_and_delta_r_calibrates(truth):
    """The acceptance's negative control *and* the reason the discriminator
    has two conditions: the clean fit measures the same R² = 0.9999 as E2
    (a design-matrix property of the window), and only the partner's 1.6σ
    keeps it quiet.  δR on Gaussian noise: slope ≈ 1, intercept ≈ 0
    (measured 1.004 / −0.0004)."""
    structure, ins, data = truth
    ref, result, report = _fit_and_report(structure, ins.model_copy(deep=True),
                                          data, "wp1056_clean")
    ev = report.identifiability
    assert ev is not None
    row = _exchange(report, "instrument.geometry.sample_displacement")
    assert row.r2 > 0.99                     # same design matrix as E2 …
    assert row.partner_significance < 5.0    # … nothing riding it (1.6σ)
    assert not any(e.exchangeable for e in ev.exchanges)
    assert "exchangeable" not in report.summary
    assert "unconstrained" not in report.summary   # softest mode 1.2e-02
    # no clause, no license field: None is the honest empty state (WP-1108)
    assert result.statistics.identifiability_clause is None
    assert min(m.eigenvalue for m in ev.soft_modes) > 3e-3
    # the esd-qualifying trio is quoted together, raw
    assert ev.chi2_reduced == pytest.approx(result.statistics.chi2)
    assert ev.esd_inflation == pytest.approx(result.statistics.esd_inflation)
    assert ev.durbin_watson == pytest.approx(result.statistics.durbin_watson)
    assert ev.delta_r_slope == pytest.approx(1.0, abs=0.05)
    assert ev.delta_r_intercept == pytest.approx(0.0, abs=0.02)


def test_e8_short_window_reports_the_collinear_triangle():
    """The WP-1053 E8 miss, closed at the state that produced it: on 20–56°
    a plan that frees displacement instead of the planted zero converges
    (χ²_red 0.95, Rwp 0.0127) with displacement +0.037 against a truth of 0.
    The report now carries the whole triangle: fitted displacement 119σ from
    null but exchangeable with the held zero (R² = 1.0000), the
    displacement↔cell soft mode, and the u/v/w combination below comment
    threshold — the evidence for ``ambiguous`` in a *converged* report."""
    from rietx.strategy.staged import RefinementPlan, Stage

    structure, ins, data = _truth(lo=20.0, hi=56.0, seed=23)
    start = ins.model_copy(deep=True)
    start.zero_shift.value = 0.02          # planted cause, held by this plan
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("disp", ["instrument.geometry.sample_displacement"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
        Stage("profile", ["instrument.profile.u", "instrument.profile.v",
                          "instrument.profile.x", "instrument.profile.y"]),
    ])
    ref, result, report = _fit_and_report(structure, start, data,
                                          "wp1056_e8_short", plan=plan,
                                          zoom=(20.0, 35.0))
    assert ref.fitted_instrument.zero_shift.value == 0.02
    assert abs(ref.fitted_instrument.geometry.sample_displacement.value) > 0.02

    row = _exchange(report, "instrument.zero_shift")
    assert row.r2 > 0.999                                  # measured 0.99999
    assert row.partner == "instrument.geometry.sample_displacement"
    assert row.exchangeable
    assert "exchangeable with the held instrument.zero_shift" in report.summary
    _assert_exchange_clause_shape(report.summary)

    ev = report.identifiability
    triangle = [m for m in ev.soft_modes
                if {"instrument.geometry.sample_displacement",
                    "phases.0.cell.a"} <= set(m.loadings)]
    assert triangle and triangle[0].eigenvalue < 0.1       # measured 5.8e-02
    # the u/v/w family combination is below comment level on this window
    # (measured 6.7e-04 against 1.2e-02 full-range) and earns the sentence
    assert min(m.eigenvalue for m in ev.soft_modes) < 3e-3
    assert "unconstrained at" in report.summary
    # **The identity of the worst pair is platform-robust; its magnitude is
    # not**, and the pre-WP-1110 bar of 0.99 sat inside the spread.  Measured
    # |rho| for u~v: 0.992821 on darwin/arm64, 0.983761 on CI's linux x86-64 —
    # 9.1e-3 apart, which is where TRF stopped and not physics.  Both the old
    # 0.99 and the package's own `correlation_guard` default of 0.98 are inside
    # that, so neither is an assertion about this fit; they are load sensors,
    # the numeric twin tests/CLAUDE.md names.  What *is* stable is which pair
    # comes first and the soft-mode eigenvalue asserted above, which is computed
    # on the unit-column normal matrix and therefore carries no conditioning.
    assert ev.top_correlations, "no correlations measured at all"
    worst = max(ev.top_correlations, key=lambda c: abs(c.rho))
    assert {worst.path_a, worst.path_b} == {"instrument.profile.u",
                                            "instrument.profile.v"}, (
        "worst pair = " + ", ".join(f"{c.path_a}~{c.path_b} {c.rho:+.6f}"
                                    for c in ev.top_correlations))
    assert abs(worst.rho) > 0.9, f"{worst.rho:+.6f}"


def test_identifiability_carrier_is_additive(truth):
    """A pre-1056 carrier (background table only) still validates, and the
    new fields round-trip through JSON — the additive-field rule the class
    docstring pins to SCHEMA_VERSION staying put."""
    from rietx.schemas.results import CorrelationPair, ExchangeRow, Identifiability, SoftMode

    old = Identifiability(background_absorption={"phases.0.scale": 0.1})
    assert old.top_correlations == [] and old.exchangeability == []

    full = Identifiability(
        background_absorption={},
        top_correlations=[CorrelationPair(path_a="a", path_b="b", rho=-0.97)],
        soft_modes=[SoftMode(eigenvalue=1e-3, loadings={"a": 0.8, "b": -0.6})],
        exchangeability=[ExchangeRow(held="h", r2=0.995,
                                     partners={"a": -1.1})])
    again = Identifiability.model_validate_json(full.model_dump_json())
    assert again == full


# ----------------------------------------------------------------------
# WP-1108 — the license beside the numbers: the statistics placement
# ----------------------------------------------------------------------
def test_license_rides_statistics_and_summary_from_one_render(truth):
    """The identifiability clause is delivered twice from one render
    (WP-1108): ``build_report`` appends it to the summary for that string's
    readers and writes the same object to
    ``result.statistics.identifiability_clause`` — the block measured agent
    consumers grep back out of a piped response (protocol 2.2: in context
    4/4 there against 3/4 in the summary, the v1.1 appendix).  A copy is
    legal only as one authority rendering once, so the pair is pinned
    bit-identical and the field is pinned to the renderer's own answer."""
    from rietx.report import identifiability_clause
    from rietx.schemas.results import ExchangeRow, Identifiability, RefinedParameter

    structure, ins, data = truth
    result, _model, _values = _result_for(structure, ins, data)
    # a firing exchange, hand-planted the way a fit would have screened it:
    # the carrier holds the row, the parameters hold the partner's value/esd
    result.identifiability = Identifiability(exchangeability=[
        ExchangeRow(held="instrument.geometry.sample_displacement", r2=0.9999,
                    partners={"instrument.zero_shift": -1.4})])
    result.parameters = [RefinedParameter(
        path="instrument.zero_shift", value=0.0317, stderr=0.0005)]
    assert result.statistics.identifiability_clause is None  # no writer yet

    report = build_report(result)
    clause = result.statistics.identifiability_clause
    assert clause is not None
    assert report.summary.endswith("; " + clause)         # bit-identical pair
    assert clause == identifiability_clause(report.identifiability)
    # the license is in the statistics block: the grep an agent runs on the
    # serialized document returns the sentence itself, not a pointer
    dumped = result.model_dump(mode="json")
    assert dumped["statistics"]["identifiability_clause"] == clause
    assert "data has chosen" in dumped["statistics"]["identifiability_clause"]
    # idempotent: a second build re-renders the same answer, and its own
    # fresh summary carries the same appended substring
    report2 = build_report(result)
    assert result.statistics.identifiability_clause == clause
    assert report2.summary.endswith("; " + clause)


def test_license_field_stays_none_when_nothing_fires(truth):
    """``None`` is the honest empty state (WP-1076) and covers both causes —
    no report built, and nothing crossed a comment threshold — never a
    verdict about the fit."""
    structure, ins, data = truth
    result, model, values = _result_for(structure, ins, data)
    assert result.statistics.identifiability_clause is None
    build_report(result, model=model, values=values)
    assert result.statistics.identifiability_clause is None
    dumped = result.model_dump(mode="json")
    assert dumped["statistics"]["identifiability_clause"] is None


def test_a_serialized_answer_delivers_the_license_beside_the_numbers():
    """The acceptance pin: a real serialized answer carries the field inside
    ``result.statistics``, bit-identical to what the 2.2 ``report_stat`` arm
    delivered — the clause the answer's *own* report evidence renders, which
    is exactly the shim projection's equivalence check
    (``run_refine._project_license_placement``) satisfied by the package
    itself.  The summary keeps its copy: the placement decision moved nothing
    out (the WP-1108 design note).

    It was one ``refine_json`` call until WP-1303; the response it validated
    is assembled here from the two dumps it wrapped, so what the shim's
    projection is held to is unchanged.
    """
    from rietx.report import identifiability_clause
    from rietx.report.schemas import IdentifiabilityEvidence
    from rietx.schemas.plan import PlanSpec

    structure, ins, data = _truth(disp=-0.10)      # the R1 shape: a genuinely
    start = ins.model_copy(deep=True)              # displaced specimen, fitted
    start.geometry.sample_displacement.value = 0.0  # the lazy way (zero free)
    plan = PlanSpec.model_validate({"stages": [
        {"name": "scale_bkg",
         "turn_on": ["phases.*.scale", "instrument.background.*"]},
        {"name": "zero", "turn_on": ["instrument.zero_shift"]},
        {"name": "cell", "turn_on": ["phases.*.cell.*"]},
        {"name": "profile_w", "turn_on": ["instrument.profile.w"]},
    ]})
    ref = rx.Refinement(structure, start)
    result = ref.fit(data, plan=plan)
    # the report is built *before* the result is dumped, because building it is
    # what writes the clause into ``result.statistics`` (WP-1108's declared
    # write) — the envelope did the same two steps in the same order
    report = ref.report(plan=plan)
    response = {"result": result.model_dump(mode="json"),
                "report": report.model_dump(mode="json")}
    clause = response["result"]["statistics"]["identifiability_clause"]
    assert clause is not None
    assert clause == identifiability_clause(IdentifiabilityEvidence
                                            .model_validate(
                                                response["report"]
                                                ["identifiability"]))
    assert ("; " + clause) in response["report"]["summary"]
    assert "data has chosen" in clause             # the license, greppable


# ----------------------------------------------------------------------
# WP-1063 — the swap the clause names, run on demand
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def displaced():
    """A genuinely displaced specimen (−0.10 mm in the *data*), fitted the
    lazy way: zero free, displacement held at 0.  R1's shape, which no
    planted-start episode has — E2 and E8 move the starting model and leave
    the pattern undisplaced, so their rivals tie exactly."""
    from rietx.strategy.staged import RefinementPlan, Stage

    structure, ins, data = _truth(disp=-0.10)
    start = ins.model_copy(deep=True)
    start.geometry.sample_displacement.value = 0.0
    ref = rx.Refinement(structure, start)
    ref.fit(data, plan=RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        Stage("zero", ["instrument.zero_shift"]),
        Stage("cell", ["phases.*.cell.*"]),
        Stage("profile_w", ["instrument.profile.w"]),
    ]))
    return ref, data, ref.report()


def test_compare_rivals_answers_the_clause_it_is_named_by(displaced):
    """The R1 shape, decided: the fit absorbed a real −0.10 mm displacement
    into the zero and reports the pair as exchangeable at R² = 0.9999 — and
    the swap separates them by a factor of ~3 in χ², recovering the planted
    displacement to five digits.  Which is the point of the reworded clause:
    'this fit cannot tell' is true, 'the data cannot tell' was not."""
    from rietx.report import compare_rivals

    ref, data, report = displaced
    finding = _exchange(report, "instrument.geometry.sample_displacement")
    assert finding.exchangeable and finding.partner == "instrument.zero_shift"

    comparison = compare_rivals(ref, data, finding)
    held_freed, partner_freed = comparison.rivals
    assert held_freed.freed_path == "instrument.geometry.sample_displacement"
    assert held_freed.held_path == "instrument.zero_shift"
    assert held_freed.held_at == 0.0                     # the null, not −0.02
    assert partner_freed.freed_path == "instrument.zero_shift"
    assert partner_freed.held_at == 0.0
    # the displaced specimen is what the data says it is (measured −0.09999)
    assert held_freed.freed_value == pytest.approx(-0.10, abs=1e-3)
    assert held_freed.freed_esd is not None and held_freed.freed_esd > 0
    assert held_freed.chi2 < partner_freed.chi2          # measured 1.05 / 2.99
    assert not hasattr(comparison, "decisive")           # numbers, no verdict


def test_chi2_ratio_orientation_is_held_over_partner(displaced):
    """Below 1 means the parameter the fit *held* explains the pattern better
    than the one it refined — the direction a caller acts on, so it is pinned
    rather than left to the field order."""
    from rietx.report import compare_rivals

    ref, data, report = displaced
    comparison = compare_rivals(
        ref, data, _exchange(report, "instrument.geometry.sample_displacement"))
    assert comparison.chi2_ratio == pytest.approx(
        comparison.rivals[0].chi2 / comparison.rivals[1].chi2)
    assert comparison.chi2_ratio < 1.0                   # measured 0.35


def test_both_rivals_refine_the_same_number_of_parameters(displaced):
    """The fairness the docstring claims, published so it can be checked: the
    two fits differ by *which* member of the pair is free, never by how many
    parameters are — which is what lets raw χ² be compared without an
    information criterion."""
    from rietx.report import compare_rivals

    ref, data, report = displaced
    comparison = compare_rivals(
        ref, data, _exchange(report, "instrument.geometry.sample_displacement"))
    assert comparison.rivals[0].n_free == comparison.rivals[1].n_free
    assert comparison.rivals[0].n_points == comparison.rivals[1].n_points


def test_the_comparison_leaves_the_caller_where_it_found_it(displaced):
    """Two branch fits: the working state still stands on the converged fit
    that asked the question."""
    from rietx.report import compare_rivals

    ref, data, report = displaced
    before = ref.fitted_instrument.zero_shift.value
    compare_rivals(ref, data,
                   _exchange(report, "instrument.geometry.sample_displacement"))
    assert ref.fitted_instrument.zero_shift.value == before
    assert ref.fitted_instrument.geometry.sample_displacement.value == 0.0


def test_an_undisplaced_specimen_ties(truth):
    """The control for the test above, and the reason a synthetic
    planted-start episode cannot answer this question: with nothing displaced
    in the data, both rivals describe it equally well and the ratio is 1."""
    from rietx.report import compare_rivals

    structure, ins, data = truth
    ref = rx.Refinement(structure, ins.model_copy(deep=True))
    ref.fit(data, plan="mccusker_default")
    comparison = compare_rivals(
        ref, data, ("instrument.geometry.sample_displacement",
                    "instrument.zero_shift"))
    assert comparison.chi2_ratio == pytest.approx(1.0, abs=0.02)


def test_a_pair_member_with_no_null_is_refused_by_name(displaced):
    """A cell edge has no value the data could be accused of failing to
    distinguish it from, so there is no swap — and the message says what to
    do instead rather than returning an empty answer."""
    from rietx.report import compare_rivals

    ref, data, _ = displaced
    with pytest.raises(ValueError, match="no null identity"):
        compare_rivals(ref, data,
                       ("phases.0.cell.a", "instrument.zero_shift"))


def test_pawley_mode_is_refused_by_name(truth):
    """Mirrors ``exchangeability_scan``'s own fence: there the fitted span
    includes the per-hkl intensity block."""
    from rietx.report import compare_rivals

    structure, ins, data = truth
    ref = rx.Refinement(structure, ins.model_copy(deep=True))
    ref.fit(data, mode="pawley", plan="mccusker_default")
    with pytest.raises(ValueError, match="Pawley"):
        compare_rivals(ref, data, ("instrument.zero_shift",
                                   "instrument.geometry.sample_displacement"))


def test_comparing_before_a_fit_is_refused(truth):
    from rietx.report import compare_rivals

    structure, ins, data = truth
    ref = rx.Refinement(structure, ins.model_copy(deep=True))
    with pytest.raises(RuntimeError, match="run a fit"):
        compare_rivals(ref, data, ("instrument.zero_shift",
                                   "instrument.geometry.sample_displacement"))


def test_an_exchange_row_with_no_partner_is_refused_by_name():
    """``ExchangeFinding.partner`` is None when no loading names a nulled
    parameter; that row can never be ``exchangeable``, and it has no swap."""
    from rietx.report.layer2 import _rival_pair
    from rietx.report.schemas import ExchangeFinding

    with pytest.raises(ValueError, match="names no partner"):
        _rival_pair(ExchangeFinding(held="phases.0.cell.a", r2=0.99,
                                    partners={"phases.0.scale": 1.0}))


def test_building_a_report_performs_no_fits(monkeypatch, displaced):
    """The pull, stated as an invariant: ``compare_rivals`` is solve-bearing
    and nothing in the report build may reach it, or a caller that merely
    asked what the fit says would pay for two more.

    Spying on the solver rather than on ``compare_rivals`` is deliberate — it
    catches any future section that decides to measure something, not just
    this one.
    """
    import importlib

    # by name: the package re-exports the ``refine`` *function* over its own
    # module, so ``rietx.refine`` is not the module here
    refine_mod = importlib.import_module("rietx.refine")

    def refuse(*args, **kw):
        raise AssertionError("a report build ran the solver")

    monkeypatch.setattr(refine_mod, "run_least_squares", refuse)
    ref, data, _ = displaced
    report = ref.report()
    assert report.identifiability is not None      # it did build the section
    assert report.summary
