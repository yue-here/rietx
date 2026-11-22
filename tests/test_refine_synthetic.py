"""Round-trip: synthesize a LaB6 pattern with known parameters, perturb the
model, refine, and check the truth is recovered."""

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement, build_report
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_schemas import make_lab6

WAVELENGTH = 0.4139
TRUE_A = 4.15660
TRUE_ZERO = 0.008
TRUE_W = 2.5e-4
TRUE_SCALE = 5e-4
TRUE_BKG = [40.0, -6.0, 1.5]


def truth(extra_phases=()):
    """The LaB₆ truth's structure and instrument, plus ``extra_phases`` at the
    values they carry."""
    structure = make_lab6()
    structure.phases[0].cell.a.value = TRUE_A
    structure.phases[0].cell.b.value = TRUE_A
    structure.phases[0].cell.c.value = TRUE_A
    structure.phases[0].scale.value = TRUE_SCALE
    structure.phases.extend(extra_phases)
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = TRUE_ZERO
    ins.profile.w.value = TRUE_W
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in TRUE_BKG])
    return structure, ins


def synthesize(noise_seed: int | None = 7, extra_phases=()) -> PatternData:
    """The LaB₆ truth, plus ``extra_phases`` drawn at the values they carry."""
    structure, ins = truth(extra_phases)
    tt = np.arange(3.0, 24.0, 0.005)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    if noise_seed is not None:
        rng = np.random.default_rng(noise_seed)
        y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


@pytest.fixture(scope="module")
def synthetic_pattern() -> PatternData:
    return synthesize()


def perturbed_models():
    structure = make_lab6()
    structure.phases[0].cell.a.value = TRUE_A + 0.004   # ~0.1% off
    structure.phases[0].cell.b.value = TRUE_A + 0.004
    structure.phases[0].cell.c.value = TRUE_A + 0.004
    structure.phases[0].scale.value = TRUE_SCALE * 1.8
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    ins.zero_shift.value = 0.0
    ins.profile.w.value = TRUE_W * 2.0
    ins.background = BackgroundChebyshev.with_terms(3)
    return structure, ins


def test_rietveld_round_trip(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    result = ref.fit(synthetic_pattern, plan="mccusker_default")

    assert result.status == "converged"
    assert result.statistics.rwp < 0.10
    # GoF ≈ 1 against Poisson noise when the model is right
    assert result.statistics.gof < 2.0

    a = ref.fitted_structure.phases[0].cell.a.value
    a_err = result.parameter("phases.0.cell.a").stderr or 1e-4
    assert a == pytest.approx(TRUE_A, abs=max(5 * a_err, 5e-5))

    zero = ref.fitted_instrument.zero_shift.value
    assert zero == pytest.approx(TRUE_ZERO, abs=2e-3)

    # tied cubic cell: b and c must track a exactly
    assert ref.fitted_structure.phases[0].cell.b.value == pytest.approx(a, rel=1e-12)


def test_lebail_round_trip(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    result = ref.fit(synthetic_pattern, mode="lebail")

    assert result.status == "converged"
    # Le Bail should fit at least as well as Rietveld (free intensities)
    assert result.statistics.rwp < 0.10
    a = ref.fitted_structure.phases[0].cell.a.value
    assert a == pytest.approx(TRUE_A, abs=2e-4)


def test_fit_report_layer0(synthetic_pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    result = ref.fit(synthetic_pattern)
    report = build_report(result)
    assert report.rwp == pytest.approx(result.statistics.rwp)
    assert report.n_regions_total > 3
    assert abs(sum(r.chi2_share for r in report.regions) - 1.0) < 1.0
    assert report.summary


def test_max_shift_over_esd_measures_convergence(synthetic_pattern):
    """McCusker §7's quantity on both of its branches (WP-1106).

    The 0.1 band is quoted from the paper and gates nothing; the value's
    information is which side a solve landed on and by how much.  A converged
    TRF solve at ftol 1e-9 satisfies the criterion a fortiori (measured here
    ≈3e-4), while the same stage starved to one iteration stops mid-flight
    (measured ≈14 — the magnitude, not the status, says *how* unconverged).
    Margins are >100× on both sides, so neither assertion can turn into a
    solver-termination sensor.
    """
    from rietx import Stage
    from rietx.optimize.statistics import MAX_SHIFT_CONVERGED

    turn_on = ["phases.*.scale", "instrument.background.*",
               "phases.*.cell.*", "instrument.zero_shift"]

    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    converged = ref.run_stage(synthetic_pattern, Stage("all", turn_on=turn_on))
    assert converged.status == "converged"
    assert converged.statistics.max_shift_over_esd is not None
    assert converged.statistics.max_shift_over_esd < MAX_SHIFT_CONVERGED

    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    starved = ref.run_stage(synthetic_pattern,
                            Stage("starved", turn_on=turn_on, max_iter=1))
    assert starved.status == "max_iter"
    assert starved.statistics.max_shift_over_esd is not None
    assert starved.statistics.max_shift_over_esd > MAX_SHIFT_CONVERGED

    # the number is a copy of the solver's, and it travels the JSON contract
    dumped = starved.model_dump(mode="json")["statistics"]["max_shift_over_esd"]
    assert dumped == pytest.approx(starved.statistics.max_shift_over_esd)


def test_impurity_peak_detected(synthetic_pattern):
    # inject an unmodelled peak and check Layer-0 flags it
    tt = np.asarray(synthetic_pattern.two_theta)
    y = np.asarray(synthetic_pattern.intensity, dtype=float)
    y += 3000.0 * np.exp(-0.5 * ((tt - 9.7) / 0.01) ** 2)
    doped = PatternData(two_theta=tt.tolist(), intensity=y.tolist())

    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)
    result = ref.fit(doped)
    report = build_report(result)
    hits = [u for u in report.unmatched if u.kind == "unmatched_obs"
            and abs(u.two_theta - 9.7) < 0.1]
    assert hits, "injected impurity peak was not flagged"


# ------------------------------------------------------- the evaluate-only path
def test_predict_needs_no_fit(synthetic_pattern):
    """Evaluating a model is not refining it (WP-1110 item 6).

    ``predict`` refused both its forms with ``call fit() first`` until
    WP-1110, so an agent that wanted y_calc at known parameters in order to
    redraw a figure ended up calling ``set_values`` and then *re-refining* a
    one-stage plan as a "replot".  The parameters are read off the structure
    and instrument as they stand, whoever put them there.
    """
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins)

    y = ref.predict(synthetic_pattern)
    assert y.shape == (len(synthetic_pattern.two_theta),)
    assert np.all(np.isfinite(y))
    assert y.max() > 0.0
    # a PatternData and its own 2θ column are the same request
    assert np.array_equal(y, ref.predict(np.asarray(synthetic_pattern.two_theta)))


def test_predict_at_the_fitted_values_needs_no_fit_either(synthetic_pattern):
    """The equivalence bar: a fit is a way to *set* the parameters, not to
    license evaluating them.

    A never-fitted `Refinement` carrying the fitted models must return exactly
    what the fitted one returns for the same grid — bit-identical, not close,
    since it is the same compile of the same values.
    """
    structure, ins = perturbed_models()
    fitted = Refinement(structure, ins)
    fitted.fit(synthetic_pattern, plan="profile_only")

    twin = Refinement(fitted.structure.model_copy(deep=True),
                      fitted.instrument.model_copy(deep=True))
    assert np.array_equal(twin.predict(synthetic_pattern),
                          fitted.predict(synthetic_pattern))


def test_predict_with_no_grid_still_needs_one(synthetic_pattern):
    """The one form that genuinely needs a fit, refusing by naming the other."""
    structure, ins = perturbed_models()
    with pytest.raises(RuntimeError, match=r"ref\.predict\(data\)"):
        Refinement(structure, ins).predict()


def test_a_zero_stage_plan_is_refused_before_it_costs_anything(synthetic_pattern,
                                                               tmp_path):
    """It raised a bare ``AssertionError`` from the end of the run (WP-1110).

    Refused now at the top of ``fit``, so nothing is created on the way to the
    failure, and the message names ``predict`` — because wanting the model
    evaluated rather than refined is what sends someone here.
    """
    from rietx import RefinementPlan

    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, history=tmp_path / "h.jsonl")
    with pytest.raises(ValueError, match=r"predict\(pattern\)"):
        ref.fit(synthetic_pattern, plan=RefinementPlan(stages=[]))
    assert ref.result_ is None
    assert not (tmp_path / "h.jsonl").exists(), "refused before anything was written"
