"""The two drivers are interchangeable at the entry points (WP-0601).

``solver="lm"`` must reach the same physical answer as the scipy TRF reference
through the *same* residual/Jacobian closures, on both entry points — the
single-histogram one and the joint multi-histogram one, which WP-0308 warned
is a second driver rather than a wrapper.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx import Instrument, MultiHistogramRefinement, Refinement, refine
from rietx.optimize.least_squares import SOLVERS
from tests.test_refine_synthetic import (
    TRUE_A,
    TRUE_ZERO,
    perturbed_models,
    synthesize,
)


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def test_both_solvers_are_offered():
    assert SOLVERS == ("trf", "lm")


@pytest.mark.parametrize("bad", ["lmfit", "TRF", "", "levenberg"])
def test_unknown_solver_is_refused_at_construction(bad):
    structure, ins = perturbed_models()
    with pytest.raises(ValueError, match="unknown solver"):
        Refinement(structure, ins, solver=bad)


def test_lm_reaches_the_same_minimum_as_trf(pattern):
    """Not bit-identical — different path — but the same answer."""
    out = {}
    for solver in SOLVERS:
        structure, ins = perturbed_models()
        ref = Refinement(structure, ins, solver=solver, history=False)
        result = ref.fit(pattern, plan="mccusker_default")
        assert result.status == "converged"
        # WP-0602: which driver ran is provenance, and no cone in this model
        # means the truncation counter must stay at zero on every stage
        assert result.provenance.solver == solver
        assert all(s.n_constraint_truncations == 0 for s in result.stages)
        assert not any(d.code == "CONSTRAINT_ACTIVE" for d in result.diagnostics)
        out[solver] = (ref.fitted_structure.phases[0].cell.a.value,
                       ref.fitted_instrument.zero_shift.value,
                       result.statistics.rwp)

    a_lm, zero_lm, rwp_lm = out["lm"]
    a_trf, zero_trf, rwp_trf = out["trf"]
    assert a_lm == pytest.approx(TRUE_A, abs=5e-5)
    assert a_lm == pytest.approx(a_trf, abs=2e-5)
    assert zero_lm == pytest.approx(TRUE_ZERO, abs=2e-3)
    assert zero_lm == pytest.approx(zero_trf, abs=5e-4)
    assert rwp_lm == pytest.approx(rwp_trf, rel=0.02)


def test_functional_api_takes_the_solver(pattern):
    structure, ins = perturbed_models()
    result = refine(pattern, structure, ins, solver="lm")
    assert result.status == "converged"
    assert result.statistics.rwp < 0.10


def test_branch_carries_the_solver(pattern):
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, solver="lm")
    ref.fit(pattern, plan="mccusker_default")
    assert ref.branch()._solver == "lm"


def test_multi_histogram_entry_point_takes_the_solver(pattern):
    """WP-0308's warning made executable: the joint driver is a second one.

    A solver swap that reached only ``run_least_squares`` would leave this
    path silently on scipy, and nothing else in the suite would notice.
    """
    structure, ins = perturbed_models()
    second = Instrument.debye_scherrer(wavelength=0.4139)
    second.zero_shift.value = 0.0
    second.profile.w.value = ins.profile.w.value
    second.background = ins.background.model_copy(deep=True)

    multi = MultiHistogramRefinement(structure, [ins, second], solver="lm")
    result = multi.fit([pattern, pattern])
    assert result.status in ("converged", "max_iter")
    assert result.statistics.rwp < 0.15
    assert result.provenance.solver == "lm"          # WP-0602 provenance
    assert all(s.n_constraint_truncations == 0 for s in result.stages)

    with pytest.raises(ValueError, match="unknown solver"):
        MultiHistogramRefinement(structure, [ins], solver="nope")


def test_sequential_takes_the_solver(pattern):
    """The series runner builds one Refinement per pattern; the solver must
    survive that construction or a series silently reverts to scipy."""
    from rietx import SequentialRefinement, refine_sequential

    structure, ins = perturbed_models()
    with pytest.raises(ValueError, match="unknown solver"):
        SequentialRefinement(structure, ins, solver="nope")

    series = refine_sequential([pattern, pattern], structure, ins, solver="lm",
                               plan="mccusker_default")
    assert series.provenance is not None
    assert series.provenance.solver == "lm"
    assert all(e.status == "converged" for e in series.entries)


def test_constraint_active_diagnostic_units():
    """`CONSTRAINT_ACTIVE` fires iff the answer-producing stage truncated.

    The counter's semantics: the only signal that a declared linear-inequality
    constraint was *active* rather than merely present (WP-0601 → WP-0602).
    """
    from types import SimpleNamespace

    from rietx.refine import _constraint_diagnostics

    quiet = _constraint_diagnostics("sample_profile", SimpleNamespace(
        n_constraint_truncations=0))
    assert quiet == []

    fired = _constraint_diagnostics("sample_profile", SimpleNamespace(
        n_constraint_truncations=3))
    assert len(fired) == 1
    d = fired[0]
    assert d.code == "CONSTRAINT_ACTIVE"
    assert d.level == "info"           # admissible, not wrong — never a warning
    assert "3 step(s)" in d.message and "sample_profile" in d.message
    assert "Vary the starting seed" in d.suggestion


def test_outcome_records_which_driver_ran(pattern):
    """``LSQOutcome.solver`` is what a benchmark or a record field reads."""
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import run_least_squares
    from rietx.params.vector import ParameterTable

    structure, ins = perturbed_models()
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.scale", "instrument.background.*"], True)

    for solver in SOLVERS:
        outcome = run_least_squares(model, table, max_iter=20, solver=solver)
        assert outcome.solver == solver
        assert outcome.cost_final <= outcome.cost_initial
        assert outcome.n_constraint_truncations == 0   # no cone in this model

    with pytest.raises(ValueError, match="unknown solver"):
        run_least_squares(model, table, solver="banana")


def test_lm_eval_stream_carries_every_measured_trial(pattern):
    """The LM stream carries trials with λ, and its *accepted* run is monotone.

    Before WP-1113 the LM callback reported accepted points only.  The
    evaluation-count work needs the rejected trials and the λ that produced
    them — that is the trajectory distinguishing a crawl from a collapse — so
    the driver now reports each trial the residual measured, ``accepted``
    marking which became the incumbent.  ``eval`` then means the same thing on
    both drivers (one residual evaluation), and the monotonicity pin moves to
    the accepted subset, where it is a property of the algorithm: LM accepts
    only strict decreases.
    """
    seen: list[dict] = []
    structure, ins = perturbed_models()
    ref = Refinement(structure, ins, solver="lm", history=False)
    ref.fit(pattern, plan="mccusker_default", events=seen.append)

    per_stage: dict[str, list[dict]] = {}
    for event in seen:
        if event["kind"] == "eval":
            per_stage.setdefault(event["data"]["stage"], []).append(event["data"])
    assert per_stage, "no eval events emitted"
    # the LM driver names its own termination vocabulary (LMOutcome.termination)
    terminations = [e["data"]["termination"] for e in seen
                    if e["kind"] == "stage_end"]
    assert terminations and all(
        t in {"ftol_runs", "exhausted_fp64", "no_descent", "max_nfev"}
        for t in terminations), terminations
    for stage, evals in per_stage.items():
        assert all(np.isfinite(e["cost"]) for e in evals)
        # WP-1113 trajectory fields, LM flavour: λ on every trial
        assert all({"accepted", "lam", "step_norm", "values"} <= e.keys()
                   for e in evals), f"{stage} eval missing trajectory fields"
        accepted = [e["cost"] for e in evals if e["accepted"]]
        assert accepted == sorted(accepted, reverse=True), \
            f"{stage} accepted cost went back up"


# -- one status vocabulary and one budget for both drivers (WP-1937) ----------

def _scale_and_background_stage(pattern):
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure, ins = perturbed_models()
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.scale", "instrument.background.*"], True)
    return model, table


@pytest.mark.parametrize("solver", SOLVERS)
def test_a_stage_that_starts_at_its_minimum_converges(pattern, solver):
    """The LM driver called this "diverged" until WP-1937, because its first
    outer iteration found nothing downhill; a series quarantines on that word.
    TRF has never said it for a valid input, and neither driver does now."""
    from rietx.optimize.least_squares import run_least_squares

    model, table = _scale_and_background_stage(pattern)
    first = run_least_squares(model, table, solver=solver)
    assert first.status == "converged"
    table.commit(first.theta)
    again = run_least_squares(model, table, solver=solver)
    assert again.status == "converged", again.termination
    assert again.cost_final <= first.cost_final * (1 + 1e-12)


@pytest.mark.parametrize("solver", SOLVERS)
def test_both_drivers_count_and_cap_residual_evaluations(pattern, solver,
                                                         monkeypatch):
    """``n_iterations`` is the residual evaluations a solve made, the initial
    one included, and ``max_iter`` caps it at ``max_iter × NFEV_PER_ITERATION``
    on both drivers.  The LM driver capped *outer iterations* before WP-1937,
    so a stage given the same ``max_iter`` could spend about 4× fewer
    evaluations than under TRF, and a series' first-rung bound (which divides
    an evaluation budget by the same constant) was 4× tighter on it."""
    import rietx.optimize.least_squares as ls
    from rietx.optimize.least_squares import NFEV_PER_ITERATION, run_least_squares

    model, table = _scale_and_background_stage(pattern)
    calls = {"n": 0}
    real = ls._make_residual

    def counting(*args, **kwargs):
        inner = real(*args, **kwargs)

        def residual(theta):
            calls["n"] += 1
            return inner(theta)
        return residual

    monkeypatch.setattr(ls, "_make_residual", counting)
    unbounded = run_least_squares(model, table, solver=solver)
    # run_least_squares measures the start once before handing it over
    assert unbounded.n_iterations == calls["n"] - 1

    model, table = _scale_and_background_stage(pattern)
    capped = run_least_squares(model, table, solver=solver, max_iter=1)
    assert capped.status == "max_iter"
    assert capped.n_iterations == NFEV_PER_ITERATION


@pytest.mark.parametrize("solver", SOLVERS)
def test_the_active_set_names_a_scale_held_by_its_ceiling(pattern, solver):
    """A phase scale capped at half its true value is held there.  Each driver
    reports it in ``active_bounds``, and only that column; the LM driver's
    value sits on the bound exactly."""
    from rietx.model.forward import compile_model
    from rietx.optimize.least_squares import run_least_squares
    from rietx.params.vector import ParameterTable
    from tests.test_refine_synthetic import TRUE_SCALE

    structure, ins = perturbed_models()
    structure.phases[0].scale.value = 0.3 * TRUE_SCALE
    structure.phases[0].scale.max = 0.5 * TRUE_SCALE
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    table.set_vary(["phases.*.scale", "instrument.background.*"], True)
    out = run_least_squares(model, table, solver=solver)

    k = table.free_paths.index("phases.0.scale")
    expected = np.zeros(len(table.free_paths), dtype=np.int8)
    expected[k] = 1
    assert out.active_bounds.tolist() == expected.tolist()
    if solver == "lm":
        assert out.theta[k] == table.bounds()[1][k]
    # a restart from the held value keeps it held: the LM start is not nudged
    # off the bound the way TRF's must be
    table.commit(out.theta)
    again = run_least_squares(model, table, solver=solver)
    assert again.active_bounds.tolist() == expected.tolist()
    if solver == "lm":
        assert again.theta[k] == table.bounds()[1][k]


# -- what the iteration budget means (WP-1109) ----------------------------

def _spy_least_squares(monkeypatch):
    """Record the kwargs every driver call is made with, TRF's and LM's.

    Both drivers take ``max_nfev`` and ``ftol`` from the same place in
    ``run_least_squares``.  Only TRF takes ``xtol`` and ``gtol``, so an LM row
    carries ``None`` there."""
    import scipy.optimize as so

    import rietx.optimize.least_squares as ls
    import rietx.optimize.lm as lm

    calls = []
    original = so.least_squares
    original_lm = lm.minimize

    def spy(*args, **kwargs):
        res = original(*args, **kwargs)
        calls.append({"driver": "trf", "max_nfev": kwargs.get("max_nfev"),
                      "ftol": kwargs.get("ftol"),
                      "xtol": kwargs.get("xtol"), "gtol": kwargs.get("gtol"),
                      "n_par": len(res.x), "nfev": int(res.nfev),
                      "njev": int(res.njev or 0), "status": int(res.status)})
        return res

    def spy_lm(*args, **kwargs):
        res = original_lm(*args, **kwargs)
        calls.append({"driver": "lm", "max_nfev": kwargs.get("max_nfev"),
                      "ftol": kwargs.get("ftol"), "xtol": None, "gtol": None,
                      "n_par": len(res.x), "nfev": int(res.nfev),
                      "njev": int(res.njev), "status": int(res.status)})
        return res

    monkeypatch.setattr(ls, "least_squares", spy)
    monkeypatch.setattr(lm, "minimize", spy_lm)
    return calls


@pytest.mark.parametrize("solver", SOLVERS)
def test_the_budget_counts_iterations_not_parameters(pattern, monkeypatch,
                                                     solver):
    """``max_iter`` prices iterations, and the multiplier that turns it into
    each driver's evaluation cap is a constant.  It used to be ``n_params``, which
    priced a finite-difference Jacobian this package does not build: the same
    stage then got a budget that grew with the model, ~30x looser than the
    name at 42 free parameters.  The claim under test is that the cap no
    longer depends on the parameter count at all."""
    import rietx as rx
    from rietx.optimize.least_squares import NFEV_PER_ITERATION

    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    plan = rx.RefinementPlan.mccusker_default()
    for stage in plan.stages:
        stage.max_iter = 37
    refine(pattern, structure, instrument, plan=plan, solver=solver)

    assert calls and {c["driver"] for c in calls} == {solver}
    assert len({c["n_par"] for c in calls}) > 1, \
        "fixture must span stages of differing size for this to discriminate"
    for c in calls:
        assert c["max_nfev"] == 37 * NFEV_PER_ITERATION


@pytest.mark.parametrize("solver", SOLVERS)
def test_stage_ftol_reaches_the_solver_and_only_its_own_stage(pattern, monkeypatch,
                                                              solver):
    """The three tolerance sources arrive at the solver in precedence order.

    ``Stage.ftol`` (WP-1113) is per-stage and beats everything; every other
    intermediate stage takes the plan's schedule
    (``RefinementPlan.intermediate_ftol``, WP-1123); the last declared stage
    and the closing stage take the runner's default, because they produce the
    answer (WP-2045).  Quoted from the plan rather than restated, so the
    assertion survives the number moving.
    """
    import rietx as rx

    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    plan = rx.RefinementPlan.mccusker_default()
    plan.stages[1].ftol = 1e-4
    refine(pattern, structure, instrument, plan=plan, solver=solver)

    assert {c["driver"] for c in calls} == {solver}
    assert len(calls) == len(plan.run_stages())     # the closing stage is the last
    assert len(plan.stages) > 2, "stage 1 must be an intermediate stage"
    assert calls[1]["ftol"] == 1e-4
    middle = {c["ftol"] for c in calls[:-2] if c["ftol"] != 1e-4}
    assert middle == {plan.intermediate_ftol}
    # the last declared stage and the closing stage, at the runner's default
    assert calls[-2]["ftol"] == calls[-1]["ftol"]
    assert calls[-1]["ftol"] not in (1e-4, plan.intermediate_ftol)


@pytest.mark.parametrize("solver", SOLVERS)
def test_the_exact_schedule_is_one_field_and_reaches_every_stage(
        pattern, monkeypatch, solver):
    """``intermediate_ftol=None`` is the whole way back to the pre-WP-1123
    schedule: every stage then arrives at the solver's own default, which is
    what "bit-identical to the fully-converged plan" rests on."""
    import rietx as rx

    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    plan = rx.RefinementPlan.mccusker_default()
    plan.intermediate_ftol = None
    refine(pattern, structure, instrument, plan=plan, solver=solver)

    assert {c["driver"] for c in calls} == {solver}
    assert len(calls) == len(plan.run_stages())     # the closing stage is the last
    assert len({c["ftol"] for c in calls}) == 1


@pytest.mark.parametrize("solver", SOLVERS)
def test_a_converging_fit_never_feels_the_budget(pattern, monkeypatch, solver):
    """CLAUDE.md's rule for a wall-clock budget applies to this one: a runaway
    guard, never a timer.  Tightening it ~30x is only answer-preserving if no
    converging stage was relying on the slack, so every stage here must both
    reach a convergence status and stop well inside its cap."""
    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    result = refine(pattern, structure, instrument, solver=solver)

    assert result.status == "converged"
    assert calls and {c["driver"] for c in calls} == {solver}
    for c in calls:
        assert c["status"] > 0, f"stage stopped on its budget: {c}"
        assert c["nfev"] < c["max_nfev"], c
        # and with real headroom, not by one evaluation
        assert c["nfev"] < 0.5 * c["max_nfev"], c


def test_the_trf_tolerances_are_the_module_constants(pattern, monkeypatch):
    """xtol/gtol were hardcoded literals at 1e-12 and are now named constants
    at the same value — named so the number has one home and the measurement
    that keeps it has somewhere to live, pinned so it cannot drift back into a
    literal *or* be tidied up to scipy's 1e-8 default.

    WP-1109 tried that tidy-up and put it back: it is a wash on speed (1.25x
    on one shipped protocol, 1.04x slower on another) and it takes the
    Stephens isotropic control past a shipped bar.  The constant's docstring
    carries the numbers."""
    from rietx.optimize.least_squares import GTOL, XTOL

    assert XTOL == GTOL == 1e-12
    calls = _spy_least_squares(monkeypatch)
    structure, instrument = perturbed_models()
    # xtol and gtol are TRF's alone: the LM driver takes neither
    refine(pattern, structure, instrument, solver="trf")
    assert calls and {c["driver"] for c in calls} == {"trf"}
    for c in calls:
        assert c["xtol"] == XTOL and c["gtol"] == GTOL
