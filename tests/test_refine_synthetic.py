"""Round-trip: synthesize a LaB6 pattern with known parameters, perturb the
model, refine, and check the truth is recovered."""

from pathlib import Path

import numpy as np
import pytest

from rietx import Instrument, PatternData, Refinement, build_report
from rietx.model.forward import WINDOW_AREA_TOL, compile_model, recorded_window_tol
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from rietx.schemas.plan import CLOSING_WINDOW_TOL
from tests.test_schemas import make_lab6

WAVELENGTH = 0.4139
TRUE_A = 4.15660
TRUE_ZERO = 0.008
TRUE_W = 2.5e-4
TRUE_SCALE = 5e-4
TRUE_BKG = [40.0, -6.0, 1.5]


def synthesize(noise_seed: int | None = 7, extra_phases=()) -> PatternData:
    """The LaB₆ truth, plus ``extra_phases`` drawn at the values they carry."""
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


@pytest.mark.parametrize(("mode", "history"),
                         [("rietveld", False), ("rietveld", True), ("lebail", False)])
def test_predict_on_the_fit_grid_returns_the_fit_curve(synthetic_pattern, mode, history):
    """After a default fit a grid compiles at the fit's peak cut (WP-2235,
    ruling A), so both forms of ``predict`` return ``y_calc`` bit for bit.
    An edit keeps the cut: the object has still fitted.

    A never-fitted twin carrying the fitted models still compiles at
    ``compile_model``'s default cut, so it returns that compile's array and
    differs from the fit's curve by the tails the fit's windows leave out.
    """
    structure, ins = perturbed_models()
    fitted = Refinement(structure, ins, history=history)
    result = fitted.fit(synthetic_pattern, mode=mode)
    tt = np.asarray(result.two_theta)
    y_calc = np.asarray(result.y_calc)

    cut = recorded_window_tol(result.stages[-1].window_area_tol)
    assert cut == WINDOW_AREA_TOL
    # the answer's compile, the record and the reading predict takes agree
    assert fitted._model.window_area_tol == cut
    assert fitted._peak_cut()["window_area_tol"] == cut
    assert np.array_equal(fitted.predict(), y_calc)
    assert np.array_equal(fitted.predict(tt), y_calc)
    assert np.array_equal(fitted.predict(PatternData(
        two_theta=tt.tolist(), intensity=[0.0] * len(tt))), y_calc)
    from rietx.viz.plots import plot_result

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    plot_result(result, path=str(out / f"predict_fit_grid_{mode}_{history}.png"))
    if mode != "rietveld":
        return  # a Le Bail twin has no intensities to evaluate
    # an edit that changes no value drops the result, never the fit's cut
    scale = fitted.structure.phases[0].scale.value
    fitted.set_values({"phases.0.scale": scale})
    assert fitted.result_ is None
    assert np.array_equal(fitted.predict(tt), y_calc)

    twin = Refinement(fitted.structure.model_copy(deep=True),
                      fitted.instrument.model_copy(deep=True), history=False)
    y_twin = twin.predict(tt)
    table = ParameterTable(twin.structure, twin.instrument)
    grid = PatternData(two_theta=tt.tolist(), intensity=[0.0] * len(tt))
    default = compile_model(twin.structure, twin.instrument, grid,
                            moving_paths=set(table.moving_paths))
    assert default.window_area_tol == CLOSING_WINDOW_TOL
    assert np.array_equal(y_twin, default.evaluate(table.decode(table.x0())))
    assert not np.array_equal(y_twin, y_calc)


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


# ------------------------------------- the model read at its values (WP-1947)
_EMPTY_STAGE = "evaluate"


def _with_background():
    """The perturbed models over a non-zero background, so that a background
    curve which came back as zeros could not pass for one that was read."""
    structure, ins = perturbed_models()
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in (35.0, -4.0, 1.0)])
    return structure, ins


def _empty_stage_fit(data, mode):
    """The spelling the three calls replace: one stage that frees nothing."""
    from rietx import RefinementPlan, Stage

    ref = Refinement(*_with_background())
    result = ref.fit(data, mode=mode, telemetry=False,
                     plan=RefinementPlan(stages=[Stage(_EMPTY_STAGE, [])]))
    return ref, result


def _state(ref):
    """What a call that reads the model must leave as it found it."""
    return ([(p.path, p.value, p.vary) for p in ref.parameters()],
            None if ref.history is None else len(ref.history),
            ref.result_, ref._model)


@pytest.mark.parametrize("mode", ["rietveld", "lebail", "pawley"])
def test_evaluate_is_the_empty_stage_and_changes_nothing(synthetic_pattern, mode,
                                                         tmp_path, monkeypatch):
    """#890: the statistics at the start values are one documented call.

    The answer is the empty-stage fit's, field for field on what a caller
    reads, and under Le Bail and Pawley the extraction at the start values
    still runs.  The refinement it was called on gains no history node, no run
    directory and no ``result_``: recording is switched on for the test and
    the working directory is empty, so a run directory would be seen.
    """
    from rietx import runs
    from rietx._about import STATE_DIR_NAME

    ref = Refinement(*_with_background(), history=tmp_path / "h.jsonl")
    before = _state(ref)
    monkeypatch.chdir(tmp_path)
    was = runs.set_enabled(True)
    try:
        result = ref.evaluate(synthetic_pattern, mode=mode)
    finally:
        runs.set_enabled(was)
    assert _state(ref) == before
    # no tree is made for it either (the caller has none before a first fit;
    # a fitted caller's tree is checked by the test after this one)
    assert not (tmp_path / "h.jsonl").exists(), "an evaluation is not a fit"
    assert not (tmp_path / STATE_DIR_NAME).exists(), "and records no run"

    _, fitted = _empty_stage_fit(synthetic_pattern, mode)
    assert result.status == fitted.status == "converged"
    assert result.mode == mode
    assert result.statistics == fitted.statistics
    assert result.y_calc == fitted.y_calc
    assert result.y_background == fitted.y_background
    assert result.ticks == fitted.ticks
    assert [d.code for d in result.diagnostics] == [d.code for d in fitted.diagnostics]
    assert [s.n_iterations for s in result.stages] == \
        [s.n_iterations for s in fitted.stages]
    # nothing refined: no row carries an esd, and under Rietveld nothing is free
    assert all(p.esd is None for p in result.parameters)
    if mode == "rietveld":
        assert result.statistics.n_free_parameters == 0
        assert all(s.n_iterations == 0 for s in result.stages)

    if mode == "rietveld":
        _draw_evaluation(result, synthetic_pattern)


def _draw_evaluation(result, data):
    """obs/calc/diff of the evaluated pattern, to look at (WP-1947)."""
    from pathlib import Path

    out = Path(__file__).parent / "output"
    out.mkdir(exist_ok=True)
    result.plot(out / "evaluate_before_any_fit.png")


def test_evaluate_after_a_fit_leaves_its_answer_alone(synthetic_pattern):
    """On a fitted refinement the evaluation is at the fitted values and the
    fit's own result, model and history stay the caller's: no node joins its
    tree.  Unasked, it reads the refinement in the mode it was fitted in."""
    ref = Refinement(*_with_background())
    fitted = ref.fit(synthetic_pattern, plan="profile_only", telemetry=False)
    before = _state(ref)
    result = ref.evaluate(synthetic_pattern)
    assert _state(ref) == before
    assert ref.result_ is fitted
    assert result is not fitted
    assert result.y_calc == pytest.approx(fitted.y_calc, rel=1e-12, abs=1e-9)

    lebail = Refinement(*_with_background())
    lebail.fit(synthetic_pattern, mode="lebail", plan="profile_only",
               telemetry=False)
    assert lebail.evaluate(synthetic_pattern).mode == "lebail"
    assert lebail.evaluate(synthetic_pattern, mode="rietveld").mode == "rietveld"


@pytest.mark.parametrize("mode", ["rietveld", "lebail", "pawley"])
def test_reflections_before_a_fit_are_the_empty_stage_rows(synthetic_pattern, mode):
    """#891: the rows before a fit equal the rows of an empty-stage fit, so a
    tick list needs no second extinction test, and nothing is written."""
    ref = Refinement(*_with_background())
    before = _state(ref)
    rows = ref.reflection_table(synthetic_pattern, mode=mode)
    assert _state(ref) == before

    fitted_ref, _ = _empty_stage_fit(synthetic_pattern, mode)
    assert rows == fitted_ref.reflection_table()
    assert rows and {(r.h, r.k, r.l) for r in rows} >= {(1, 0, 0), (1, 1, 0)}


def test_reflections_without_a_pattern_still_need_a_fit(synthetic_pattern):
    ref = Refinement(*_with_background())
    with pytest.raises(RuntimeError, match=r"ref\.reflection_table\(data\)"):
        ref.reflection_table()
    # the evaluation's keywords describe an evaluation, so they need its pattern
    with pytest.raises(ValueError, match="need the pattern"):
        ref.reflection_table(mode="lebail")


def test_background_without_mutation(synthetic_pattern):
    """#894: the background alone is one call that touches nothing.

    It equals the two workarounds it replaces: the scale-zero ``predict``
    (which writes two ``set_value`` nodes) and a phase-free twin's
    ``predict``.  After a fit, the no-grid form is ``result.y_background``.
    """
    from rietx import Structure

    ref = Refinement(*_with_background())
    before = _state(ref)
    background = ref.background(synthetic_pattern)
    assert _state(ref) == before
    assert background.max() > 0.0
    assert np.array_equal(background,
                          ref.background(np.asarray(synthetic_pattern.two_theta)))

    workaround = Refinement(*_with_background())
    workaround.set_values({"phases.0.scale": 0.0})
    assert np.array_equal(background, workaround.predict(synthetic_pattern))
    phase_free = Refinement(Structure(phases=[]), ref.instrument)
    assert np.array_equal(background, phase_free.predict(synthetic_pattern))

    # after a fit, in every mode, the no-grid form is the result's curve and
    # the grid form compiles the same background
    for mode in ("rietveld", "lebail", "pawley"):
        fitted_ref, fitted = _empty_stage_fit(synthetic_pattern, mode)
        assert np.array_equal(fitted_ref.background(),
                              np.asarray(fitted.y_background))
        assert np.array_equal(fitted_ref.background(synthetic_pattern), background)

    with pytest.raises(RuntimeError, match=r"ref\.background\(data\)"):
        ref.background()
