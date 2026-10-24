"""The termination view (WP-1302): ``str(result)``, ``Refinement.summary()``,
``SeriesResult.summary()``.

A projection of fields the objects already carry, so these tests check
*shape and presence*, never a re-derivation of the numbers — those are
covered where they are computed (statistics, the report, data_support).
"""

from __future__ import annotations

import numpy as np
import pytest

import rietx as rx
from rietx import Instrument, PatternData
from rietx.model.forward import compile_model
from rietx.params.vector import ParameterTable
from rietx.schemas.common import Parameter
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import synthesize
from tests.test_schemas import make_lab6


def _instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(4)
    return ins


def _fit(plan=None) -> tuple[rx.Refinement, rx.RefinementResult]:
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    result = ref.fit(synthesize(), plan=plan or rx.RefinementPlan.mccusker_default())
    return ref, result


def _clean_fit() -> tuple[rx.Refinement, rx.RefinementResult]:
    """A protocol tuned to raise no diagnostic at all (WP-1302's acceptance:
    the three stop-condition lines survive an empty diagnostics list)."""
    structure = make_lab6()
    structure.phases[0].cell.a.value = 4.1566
    structure.phases[0].cell.b.value = 4.1566
    structure.phases[0].cell.c.value = 4.1566
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.geometry.goniometer_radius_mm = 217.5
    ins.profile.w.value = 5e-3
    ins.background = BackgroundChebyshev(
        coefficients=[Parameter(value=v) for v in [40.0, -6.0, 1.5]])

    tt = np.arange(3.0, 24.0, 0.005)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(3).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())

    ref = rx.Refinement(structure, ins, history=False)
    plan = rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"]),
        rx.Stage("zero", ["instrument.zero_shift"]),
        rx.Stage("cell", ["phases.*.cell.*"]),
        rx.Stage("profile_w", ["instrument.profile.w"]),
    ])
    return ref, ref.fit(data, plan=plan)


# --------------------------------------------------------------- __str__
def test_str_result_has_one_section_per_stage_and_no_more():
    _ref, result = _fit()
    text = str(result)
    lines = text.splitlines()
    assert lines[0].startswith("RefinementResult:")
    for stage in result.stages:
        assert f"stage {stage.name}: {stage.status}" in text
    assert "max|Δθ|/esd=" in text  # last stage only
    assert text.count("max|Δθ|/esd=") == 1


def test_str_result_diagnostics_line_present_even_at_zero():
    _ref, result = _clean_fit()
    assert not result.diagnostics
    assert "diagnostics: none" in str(result)


def test_str_result_names_every_diagnostic_by_substring():
    """No deliverable, so an error prints in full and every other row as one
    line naming its code (WP-2037); the reading rule closes the section."""
    from rietx.schemas.results import DIAGNOSTICS_READING_RULE

    _ref, result = _fit()
    assert result.diagnostics, "fixture stopped producing any — pick another"
    text = str(result)
    for d in result.diagnostics:
        if d.level == "error":
            assert f"{d.level}[{d.code}]: {d.message}" in text
        else:
            assert f"\n    {d.code}" in text and d.message not in text
    assert f"    {DIAGNOSTICS_READING_RULE}\n" in text


def test_str_result_ends_with_provenance_then_agreement():
    _ref, result = _fit()
    lines = [ln for ln in str(result).splitlines() if ln.strip()]
    assert lines[-2].strip().startswith("provenance:")
    assert lines[-1].strip().startswith("Rwp ")


def test_str_result_is_a_pointer_not_an_alias_still_holds():
    """The new __str__ must not disturb Base.__getattr__'s own pinned
    behaviour (tests/test_schemas.py) — same object, two independent uses."""
    _ref, result = _fit()
    assert not hasattr(result, "rwp")
    str(result)  # must not raise, must not add anything to __dict__
    assert not hasattr(result, "rwp")


# ------------------------------------------------------- Refinement.summary
def _next_line(text: str) -> str:
    return next(ln for ln in text.splitlines() if ln.startswith("  next:"))


def test_summary_default_prints_the_three_stop_conditions_only():
    ref, _result = _fit()
    text = ref.summary()
    assert "diagnostics:" in text
    assert "  report:" in text
    assert _next_line(text)
    assert "deliverable:" not in text


def test_summary_the_three_stop_condition_lines_survive_zero_diagnostics():
    ref, result = _clean_fit()
    assert not result.diagnostics
    text = ref.summary()
    assert "diagnostics: none" in text
    assert "  report:" in text
    assert _next_line(text)


def test_summary_next_line_is_the_suggest_probe_read_as_delta_bic():
    """WP-1305 b: the third stop condition is a number, not an instruction to
    go and get one — and it is *that* probe's number, run on the channels the
    fit ran on, rather than a second opinion computed some other way."""
    ref, _result = _fit()
    line = _next_line(ref.summary())
    s = ref.suggest(synthesize())          # the same pattern, same channels
    if not s.groups:
        assert "nothing to free" in line
    else:
        top = s.groups[0]
        assert f"{top.delta_bic:+.1f}" in line
        assert ("free " in line) if top.delta_bic > 0 else ("refuses it" in line)
        # WP-1417: the line names the count the ΔBIC was charged at (#270)
        assert s.n_effective is not None
        assert f"at N_eff {s.n_effective:.0f}" in line


@pytest.mark.parametrize("deliverable", ["phase_id", "qpa", "structure"])
def test_summary_deliverable_adds_its_own_section(deliverable):
    ref, _result = _fit()
    text = ref.summary(deliverable=deliverable)
    assert f"deliverable: {deliverable}" in text


def test_summary_unknown_deliverable_raises():
    ref, _result = _fit()
    with pytest.raises(ValueError, match="unknown deliverable"):
        ref.summary(deliverable="not_a_real_one")


@pytest.mark.parametrize("mode", ["lebail", "pawley"])
def test_summary_next_line_survives_the_extraction_modes(mode):
    """The `next:` probe compiles in the fit's own mode and carries its
    extracted intensities, so Le Bail and Pawley reach `suggest` by a different
    path from Rietveld — and a termination view that raised there would raise
    only after the fit had been paid for."""
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    ref.fit(synthesize(), mode=mode, plan=rx.RefinementPlan(stages=[
        rx.Stage("scale_bkg", ["instrument.background.*"]),
        rx.Stage("cell", ["phases.*.cell.*"])]))
    assert _next_line(ref.summary())


def test_summary_plot_writes_the_file_and_names_it(tmp_path):
    ref, _result = _fit()
    path = tmp_path / "fit.png"
    text = ref.summary(plot=str(path))
    assert path.exists()
    assert str(path) in text


def test_summary_without_plot_names_the_call_instead():
    ref, _result = _fit()
    text = ref.summary()
    assert "plot_for_vlm" in text or "summary(plot=" in text


def test_summary_before_fit_raises():
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    with pytest.raises(RuntimeError, match="call fit"):
        ref.summary()


def test_summary_reuses_a_report_passed_in(monkeypatch):
    """Issue #251: a caller wanting the text and the structured report builds
    one report, not two.  Counted at ``build_report``, the seam both routes
    share, so the pin is on the number of builds and not on any text."""
    import rietx.report as report_mod

    ref, _result = _fit()
    report = ref.report()
    builds: list[int] = []
    orig = report_mod.build_report

    def counted(*args, **kwargs):
        builds.append(1)
        return orig(*args, **kwargs)

    monkeypatch.setattr(report_mod, "build_report", counted)
    reused = ref.summary(deliverable="qpa", report=report)
    assert builds == []
    fresh = ref.summary(deliverable="qpa")
    assert builds == [1]
    assert reused == fresh


def test_summary_refuses_a_plan_beside_a_report():
    ref, _result = _fit()
    report = ref.report()
    with pytest.raises(ValueError, match="not both"):
        ref.summary(plan=rx.RefinementPlan.mccusker_default(), report=report)


def test_summary_leaves_the_result_as_it_found_it(tmp_path):
    """The evidence behind the ``Refinement.summary`` seat's answer-invariant
    rows in ``rietx._audit``: every option of the view reads a finished fit
    and moves nothing in it.  The one field it writes is the report's
    declared cross-document write, ``Statistics.identifiability_clause``
    (WP-1108), a sentence and no fitted number."""
    def answer(res):
        return res.model_dump(mode="json", exclude={"statistics": {"identifiability_clause"}})

    ref, result = _fit()
    before = answer(result)
    # any code will do for the override; the fit need raise no warning
    first = next((d.code for d in result.diagnostics), "FLOOR_HIT")
    ref.summary(deliverable="qpa", plot=str(tmp_path / "fit.png"),
                plan=rx.RefinementPlan.mccusker_default(), levels={first: "deny"})
    ref.summary(report=ref.report())
    assert answer(ref.result_) == before


def test_summary_levels_denies_a_warning_and_says_who_set_it():
    """WP-2037 clause 4: a caller's ``deny`` prints a warning in full as an
    error, and the header says the caller set it."""
    ref, result = _fit()
    warned = [d.code for d in result.diagnostics if d.level == "warning"]
    assert warned, "the fixture fit must raise a warning for deny to act on"
    first = warned[0]
    text = ref.summary(levels={first: "deny"})
    assert f"error[{first}]" in text
    assert "1 set by levels=" in text


def test_summary_levels_refuses_an_unknown_code_before_building_the_report(monkeypatch):
    ref, _result = _fit()
    monkeypatch.setattr(ref, "report", lambda **_: pytest.fail("the report was built"))
    with pytest.raises(ValueError, match="unknown diagnostic code"):
        ref.summary(levels={"FLOOR_HITT": "allow"})


def test_summary_protocol_names_the_plan_and_held_reasons():
    ref, _result = _fit()
    text = ref.summary()
    assert "plan: scale_bkg, zero, cell, profile_w, profile" in text
    assert "held:" in text
    assert "σ source:" in text


def test_summary_under_120_lines_on_a_five_stage_plan():
    ref, _result = _fit()
    text = ref.summary(deliverable="qpa")
    assert len(text.splitlines()) < 120


def test_str_result_under_80_lines():
    _ref, result = _fit()
    assert len(str(result).splitlines()) < 80


# ---------------------------------------------------------- SeriesResult
def test_series_summary_shows_every_entry_under_the_cap():
    patterns = [synthesize(noise_seed=i) for i in (1, 2, 3)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(), labels=["a", "b", "c"],
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    text = res.summary()
    for label in ("a", "b", "c"):
        assert f"] {label} " in text
    assert "…" not in text


def test_series_summary_truncates_a_long_series():
    patterns = [synthesize(noise_seed=i) for i in range(8)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    text = res.summary(max_entries=2)
    assert "[1/8]" in text and "[8/8]" in text
    assert "[4/8]" not in text
    assert "4 more" in text


def test_series_str_is_summary():
    patterns = [synthesize(noise_seed=1)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    assert str(res) == res.summary()


def test_series_summary_diagnostics_line_present_even_at_zero():
    patterns = [synthesize(noise_seed=1)]
    res = rx.refine_sequential(
        patterns, make_lab6(), _instrument(),
        plan=rx.RefinementPlan(stages=[
            rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
                    max_iter=5)]))
    if not res.diagnostics:
        assert "diagnostics: none" in res.summary()


# ------------------------------------------- the series deliverable (WP-1305)
def _series_result(**kw) -> rx.SeriesResult:
    """A SeriesResult with no fitting: these rows are a projection of fields."""
    from rietx.schemas.results import RefinedParameter
    from rietx.schemas.sequential import SeriesEntry

    kw.setdefault("entries", [
        SeriesEntry(index=k, label=f"p{k}", x=float(k), parameters=[
            RefinedParameter(path="phases.0.cell.a", value=4.15 + 1e-4 * k,
                             stderr=1e-5)])
        for k in range(3)])
    return rx.SeriesResult(**kw)


def test_series_deliverable_prints_every_deciding_row():
    text = _series_result().summary(deliverable="series")
    assert "deliverable: series" in text
    for row in ("ordering artefact:", "persistent findings:",
                "widths grown with a worsening fit:", "steps:",
                "phase support:", "2θ-scale anchor:", "precision vs accuracy:",
                "good enough:"):
        assert row in text, row


def test_series_deliverable_quotes_a_width_that_grew_with_the_misfit():
    """WP-1465: the finding's own message, under its count, never a
    paraphrase of it."""
    from rietx.schemas.results import Diagnostic

    growth = Diagnostic(
        level="warning", code="SEQUENTIAL_WIDTH_GROWTH",
        where=["phases.0.lor_strain"], value=3.6,
        message="phases.0.lor_strain grew 3.6× from p0 to p2")
    text = _series_result(diagnostics=[growth]).summary(deliverable="series")
    assert "widths grown with a worsening fit: 1" in text
    assert "phases.0.lor_strain grew 3.6× from p0 to p2" in text
    assert ("widths grown with a worsening fit: 0"
            in _series_result().summary(deliverable="series"))


def test_a_series_that_predates_the_width_check_says_not_measured():
    """A series stamped before thresholds 1.9 never ran the check, so its zero
    would read as "checked, none" — the ordering-artefact row's rule."""
    from rietx.schemas.common import Provenance

    old = _series_result(provenance=Provenance(
        package_version="1.5.0", report_thresholds_version="1.8"))
    text = old.summary(deliverable="series")
    assert "widths grown with a worsening fit: NOT measured" in text
    new = _series_result(provenance=Provenance(
        package_version="1.6.0", report_thresholds_version="1.9"))
    assert ("widths grown with a worsening fit: 0"
            in new.summary(deliverable="series"))


def test_series_deliverable_says_a_one_way_chain_did_not_measure_ordering():
    """The absence of a SEQUENTIAL_PATH_DEPENDENT row is not evidence: a
    forward-only chain never ran the comparison that produces one."""
    assert "NOT measured" in _series_result().summary(deliverable="series")
    both = _series_result(direction="both", backward=_series_result())
    assert "measured both ways" in both.summary(deliverable="series")


def test_series_deliverable_will_not_call_a_cancelled_both_run_measured():
    """`direction` is what was asked for, not what ran.  A cancel takes the
    reverse chain out — never started, or started and never compared — and an
    empty SEQUENTIAL_PATH_DEPENDENT list then means silence, not agreement."""
    never_started = _series_result(direction="both")
    assert "NOT measured" in never_started.summary(deliverable="series")

    stopped = _series_result(
        direction="both", backward=_series_result(),
        diagnostics=[rx.Diagnostic(level="warning", code="SEQUENTIAL_CANCELLED",
                                   message="cancelled after 2 of 3")])
    assert "NOT measured" in stopped.summary(deliverable="series")


def test_series_deliverable_reads_the_comparisons_own_record():
    """WP-1333: a backward pass that *raised* is not a cancel, and the row
    quotes the record's reason rather than guessing one; a comparison that ran
    on less than the series says so beside the count."""
    raised = _series_result(direction="both", diagnostics=[rx.Diagnostic(
        level="warning", code="SEQUENTIAL_PATH_CHECK_INCOMPLETE",
        message="the forward/backward path-dependence comparison did not run: "
                "the backward chain raised ValueError('x') on pattern 1 (p1)")])
    text = raised.summary(deliverable="series")
    assert "NOT measured" in text and "backward chain raised" in text
    assert "cancelled" not in text

    partial = _series_result(
        direction="both", backward=_series_result(),
        diagnostics=[rx.Diagnostic(
            level="info", code="SEQUENTIAL_PATH_CHECK_INCOMPLETE", where=["p1"],
            message="the path-dependence comparison ran on 2 of 3 patterns")])
    text = partial.summary(deliverable="series")
    assert "measured both ways" in text
    assert "but the path-dependence comparison ran on 2 of 3 patterns" in text


def test_series_deliverable_reads_a_steps_verification_state():
    unverified = _series_result(diagnostics=[rx.Diagnostic(
        level="info", code="SEQUENTIAL_DISCONTINUITY",
        where=["phases.0.cell.a"], message="m")])
    assert "not verified" in unverified.summary(deliverable="series")

    verified = _series_result(diagnostics=[rx.Diagnostic(
        level="info", code="SEQUENTIAL_DISCONTINUITY",
        where=["phases.0.cell.a"], message="m", value=0.05)])
    assert "reproduces 0.05×" in verified.summary(deliverable="series")


def test_series_deliverable_refuses_a_per_pattern_purpose_by_name():
    """WP-1302's rule: the error is the documentation.  A QPA is decided on
    one pattern's own fit, and saying so is more useful than 'unknown'."""
    res = _series_result()
    with pytest.raises(ValueError, match="decided on one pattern"):
        res.summary(deliverable="qpa")
    with pytest.raises(ValueError, match="unknown deliverable"):
        res.summary(deliverable="not_a_real_one")


def test_refinement_summary_series_deliverable_points_one_rank_up():
    ref, _result = _fit()
    text = ref.summary(deliverable="series")
    assert "SeriesResult.summary(deliverable='series')" in text
    assert "2θ-scale anchor" in text


# ------------------------------------------- parametric coefficients (WP-1325)
def _coefficients() -> list:
    """Two terms of one declaration, in user units at T = 750 K: the shape
    ``MultiHistogramRefinement._build_result`` writes, built by hand because
    these rows are a projection of the field."""
    from rietx import ParametricCoefficient

    common = dict(equation="a_T", target="phases.0.cell.a", vary=True,
                  reference={"T": 750.0})
    return [
        ParametricCoefficient(term="1", path="vars.a_T_0", value=4.17531,
                              esd=1.6e-6, unit="Å", **common),
        ParametricCoefficient(term="T", path="vars.a_T_1", value=2.0783e-5,
                              esd=2.1e-9, unit="Å/K", **common),
    ]


def test_str_result_prints_parametric_coefficients_at_the_reference():
    _ref, result = _fit()
    assert "parametric coefficients" not in str(result)  # None: none declared
    text = str(result.model_copy(update={"parametric": _coefficients()}))
    assert "a_T: phases.0.cell.a at T=750" in text
    assert "[1] 4.1753100(16) Å" in text
    assert "[T] " in text and "Å/K" in text
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[-2].strip().startswith("provenance:")


def test_series_deliverable_says_the_functional_form_was_not_measured():
    text = _series_result().summary(deliverable="series")
    assert "functional form: NOT measured" in text
    assert "parametric=" in text


def test_series_summary_prints_a_joint_fits_coefficients_beside_the_trajectory():
    _ref, result = _fit()
    joint = result.model_copy(update={"parametric": _coefficients()})
    text = _series_result().summary(deliverable="series", parametric=joint)
    assert text.index("trajectory") < text.index("parametric coefficients")
    assert "functional form: measured jointly (a_T; coefficients above)" in text
    with pytest.raises(ValueError, match="declared none"):
        _series_result().summary(parametric=result)
