"""``SequentialRefinement`` had no per-pattern exception handling: an uncaught
exception anywhere inside ``_chain`` — deterministic on a genuinely
near-singular warm-carried block, ``numpy.linalg.LinAlgError: SVD did not
converge`` in the trigger case — propagated straight through ``fit()`` and
lost the *entire* chain, including every already-converged earlier pattern.
``on_result`` (a per-pattern callback) had already seen those results; only
the series' own aggregated state (``results_``, ``trees_``, the returned
``SeriesResult``) was empty afterwards.

This is a different failure from ``SeriesEntry.status == "diverged"``: a
diverged fit is a *result* (converged somewhere the reseed fence rejects) and
the WP-1051 quarantine already carries the chain through it with no policy
needed. This module is about a fit that never returns at all.

Reproduction: eight synthetic LaB6 patterns (``tests/test_refine_synthetic``'s
own synthesis routine, reused rather than re-derived), one of which is made
to raise via a monkeypatched ``Refinement.fit`` — the cleanest way to inject a
deterministic, position-independent failure without needing a genuinely
near-singular parameterisation on toy data (the brief's own suggested
alternative). The exception type and message match the real trigger
(``LinAlgError: SVD did not converge for slice = 0``); nothing about *which*
pattern fails or *why* is data from the private series that surfaced this.
"""

from __future__ import annotations

import sys

import numpy as np
import pytest

from rietx import Instrument
from rietx.schemas.pattern import PatternData
from rietx.sequential import ON_ERROR_POLICIES, SequentialRefinement
from tests.test_refine_synthetic import TRUE_A, WAVELENGTH
from tests.test_schemas import make_lab6

pytestmark = pytest.mark.xdist_group("series-error-policy")

N_PATTERNS = 8
FAIL_INDEX = 4  # 0-based -> "pattern 5" in the brief's 1-based telling


def _make_pattern(a: float, noise_seed: int) -> PatternData:
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable

    structure = make_lab6()
    for n in "abc":
        getattr(structure.phases[0].cell, n).value = a
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    tt = np.arange(3.0, 24.0, 0.01)
    pattern = PatternData(two_theta=tt.tolist(), intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, ins, pattern, mode="rietveld")
    table = ParameterTable(structure, ins)
    y = model.evaluate(table.decode(table.x0()))
    rng = np.random.default_rng(noise_seed)
    y = rng.poisson(np.maximum(y, 1.0)).astype(float)
    return PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())


@pytest.fixture(scope="module")
def eight_patterns() -> list[PatternData]:
    return [_make_pattern(TRUE_A + 0.0003 * i, noise_seed=100 + i)
            for i in range(N_PATTERNS)]


def _series() -> SequentialRefinement:
    structure = make_lab6()
    structure.phases[0].cell.a.value = TRUE_A
    structure.phases[0].scale.value = 5e-4
    ins = Instrument.debye_scherrer(wavelength=WAVELENGTH)
    return SequentialRefinement(structure, ins)


@pytest.fixture
def fail_on_pattern(monkeypatch, eight_patterns):
    """Monkeypatch ``Refinement.fit`` to raise ``LinAlgError`` on exactly the
    pattern object at ``FAIL_INDEX`` (matched by identity, not content — a
    series never repeats a ``PatternData`` object), every other pattern
    fitting normally through the real method.

    ``rietx.refine`` is patched via ``sys.modules`` rather than the
    ``rietx.refine`` *attribute*, because ``rietx/__init__.py`` re-exports a
    top-level ``refine()`` convenience function under that same name, which
    shadows the submodule on the package object after import — a plain
    ``import rietx.refine as m`` binds ``m`` to that function, not the module,
    and silently patching the wrong ``Refinement.fit`` (a fresh, unrelated
    class) fits every pattern for real and never reproduces anything.
    """
    import rietx.refine  # noqa: F401  (registers rietx.refine in sys.modules)

    refine_mod = sys.modules["rietx.refine"]
    orig_fit = refine_mod.Refinement.fit
    target = eight_patterns[FAIL_INDEX]

    def patched_fit(self, data, *args, **kwargs):
        if data is target:
            raise np.linalg.LinAlgError("SVD did not converge for slice = 0")
        return orig_fit(self, data, *args, **kwargs)

    monkeypatch.setattr(refine_mod.Refinement, "fit", patched_fit)
    return orig_fit


# ----------------------------------------------------------------------
# the crash itself, unmodified
# ----------------------------------------------------------------------
def test_an_invalid_policy_is_refused_by_name():
    series = _series()
    with pytest.raises(ValueError, match="on_error"):
        series.fit([_make_pattern(TRUE_A, 1)], on_error="ignore")


def test_the_reproduction_still_raises_the_trigger_error(
        eight_patterns, fail_on_pattern):
    """Confirms the monkeypatch actually reaches ``SequentialRefinement`` —
    the failure this whole module is about."""
    series = _series()
    with pytest.raises(np.linalg.LinAlgError, match="SVD did not converge"):
        series.fit(eight_patterns, on_error="raise")


# ----------------------------------------------------------------------
# on_error="raise" (the default until WP-1333): still raises, but nothing
# already converged is lost with it
# ----------------------------------------------------------------------
def test_raise_still_raises_but_keeps_the_partial_results(
        eight_patterns, fail_on_pattern):
    series = _series()
    seen: list[int] = []
    with pytest.raises(np.linalg.LinAlgError) as excinfo:
        series.fit(eight_patterns, on_result=lambda k, r: seen.append(k),
                   on_error="raise")

    # what on_result already knew before the crash — the four converged
    # patterns preceding the one that failed
    assert seen == [0, 1, 2, 3]

    # before this fix this was empty: the whole chain was lost with the
    # exception, even though four patterns had already converged
    assert len(series.results_) == 4
    assert len(series.trees_) == 4
    assert len(series._structures) == 4 and len(series._instruments) == 4
    assert len(series.failures_) == 1
    assert series.failures_[0].index == FAIL_INDEX

    # attached to the exception too, so a caller need not hold a reference
    # to the SequentialRefinement instance to read what completed
    assert excinfo.value.series_results is series.results_
    assert excinfo.value.series_failures is series.failures_


# ----------------------------------------------------------------------
# on_error="skip": the chain continues, cold after the failure
# ----------------------------------------------------------------------
def test_skip_returns_seven_results_and_one_recorded_failure(
        eight_patterns, fail_on_pattern):
    series = _series()
    seen: list[int] = []
    result = series.fit(eight_patterns, on_result=lambda k, r: seen.append(k),
                        on_error="skip")

    assert len(result.entries) == N_PATTERNS - 1
    assert result.n_failed == 1
    assert len(result.failures) == 1
    failure = result.failures[0]
    assert failure.index == FAIL_INDEX
    assert "SVD did not converge" in failure.exception
    # the failed index is simply absent, not present with a placeholder
    assert FAIL_INDEX not in [e.index for e in result.entries]
    assert seen == [0, 1, 2, 3, 5, 6, 7]
    assert len(series.results_) == N_PATTERNS - 1
    assert len(series.failures_) == 1


def test_skip_fits_the_next_pattern_cold(eight_patterns, fail_on_pattern):
    """"skip"'s documented difference from "carry": no warm start survives
    a pattern that never returned."""
    series = _series()
    result = series.fit(eight_patterns, on_error="skip")
    successor = next(e for e in result.entries if e.index == FAIL_INDEX + 1)
    assert successor.rung == "cold"
    assert successor.rungs_tried == ["cold"]


def test_skip_reports_series_pattern_failed(eight_patterns, fail_on_pattern):
    series = _series()
    result = series.fit(eight_patterns, on_error="skip")
    fired = [d for d in result.diagnostics if d.code == "SERIES_PATTERN_FAILED"]
    assert len(fired) == 1
    assert fired[0].level == "warning"
    assert "SVD did not converge" in fired[0].message
    assert str(FAIL_INDEX) in fired[0].message


# ----------------------------------------------------------------------
# on_error="carry": the chain continues, warm from the last good state
# ----------------------------------------------------------------------
def test_carry_also_returns_seven_results_and_one_failure(
        eight_patterns, fail_on_pattern):
    series = _series()
    result = series.fit(eight_patterns, on_error="carry")
    assert len(result.entries) == N_PATTERNS - 1
    assert result.n_failed == 1
    assert result.failures[0].index == FAIL_INDEX


def test_carry_fits_the_next_pattern_warm(eight_patterns, fail_on_pattern):
    series = _series()
    result = series.fit(eight_patterns, on_error="carry")
    successor = next(e for e in result.entries if e.index == FAIL_INDEX + 1)
    assert successor.rung != "cold"
    assert "warm" in successor.rung


# ----------------------------------------------------------------------
# bit-identity: a chain that never fails is untouched by any of this
# ----------------------------------------------------------------------
def test_a_chain_with_no_failures_is_unaffected_by_the_new_parameter(
        eight_patterns):
    series = _series()
    result = series.fit(eight_patterns)  # the default policy
    assert len(result.entries) == N_PATTERNS
    assert result.n_failed == 0
    assert result.failures == []
    assert not any(d.code == "SERIES_PATTERN_FAILED" for d in result.diagnostics)
    assert series.failures_ == []


def test_on_error_policies_is_the_one_vocabulary_the_validator_uses():
    assert ON_ERROR_POLICIES == ("raise", "skip", "carry")


def test_the_default_carries_past_a_failed_pattern(eight_patterns,
                                                   fail_on_pattern):
    """WP-1333's goal, as the default: one pattern that cannot be fitted costs
    that pattern, and the chain returns what it measured."""
    import inspect

    from rietx.sequential import SequentialRefinement as SR

    assert inspect.signature(SR.fit).parameters["on_error"].default == "carry"
    series = _series()
    result = series.fit(eight_patterns)
    assert len(result.entries) == N_PATTERNS - 1
    assert [f.index for f in result.failures] == [FAIL_INDEX]
    successor = next(e for e in result.entries if e.index == FAIL_INDEX + 1)
    assert successor.rung == "warm"


@pytest.mark.parametrize("policy", ["skip", "carry"])
def test_a_series_that_measured_nothing_raises(eight_patterns, monkeypatch,
                                               policy):
    """An empty ``SeriesResult`` is not an answer: a chain that fitted no
    pattern raises the last exception under every policy, with every failure
    attached."""
    targets = {id(p) for p in eight_patterns[:3]}
    import rietx.refine  # noqa: F401

    refine_mod = sys.modules["rietx.refine"]

    def always_fails(self, data, *args, **kwargs):
        assert id(data) in targets
        raise np.linalg.LinAlgError("SVD did not converge for slice = 0")

    monkeypatch.setattr(refine_mod.Refinement, "fit", always_fails)
    series = _series()
    with pytest.raises(np.linalg.LinAlgError) as excinfo:
        series.fit(eight_patterns[:3], on_error=policy)
    assert [f.index for f in excinfo.value.series_failures] == [0, 1, 2]
    assert excinfo.value.series_results == []
    assert series.failures_ == excinfo.value.series_failures


# ----------------------------------------------------------------------
# WP-1333: a rung that raises is a rung that lost
# ----------------------------------------------------------------------
def _poison(monkeypatch, target, *, fails):
    """Patch ``Refinement.fit`` so fitting ``target`` raises on the calls
    ``fails(n)`` selects, ``n`` counting that pattern's fits from 1 across
    every rung and pass; every other fit runs for real."""
    import rietx.refine  # noqa: F401  (see fail_on_pattern for why sys.modules)

    refine_mod = sys.modules["rietx.refine"]
    orig_fit = refine_mod.Refinement.fit
    calls = {"n": 0}

    def patched_fit(self, data, *args, **kwargs):
        if data is target:
            calls["n"] += 1
            if fails(calls["n"]):
                raise ValueError("refusing to enumerate reflections for cell "
                                 "a=-347.644 (a stand-in for issue #224)")
        return orig_fit(self, data, *args, **kwargs)

    monkeypatch.setattr(refine_mod.Refinement, "fit", patched_fit)
    return calls


def test_a_raised_warm_rung_escalates_and_the_cold_rung_rescues_it(
        eight_patterns, monkeypatch):
    """Issue #224's shape: every *warm* rung inherits what broke it, and only
    the cold rung starts somewhere else.  Before WP-1333 the whole pattern was
    abandoned at the first raise, and under ``"carry"`` every successor then
    warm-started from the same state and raised in turn."""
    _poison(monkeypatch, eight_patterns[FAIL_INDEX], fails=lambda n: n <= 2)
    series = _series()
    result = series.fit(eight_patterns, on_error="raise")

    assert len(result.entries) == N_PATTERNS
    assert result.n_failed == 0
    entry = next(e for e in result.entries if e.index == FAIL_INDEX)
    assert entry.rung == "cold" and entry.reseeded
    assert entry.rungs_tried == ["warm", "warm_staged", "cold"]
    assert set(entry.rungs_raised) == {"warm", "warm_staged"}
    assert "refusing to enumerate" in entry.rungs_raised["warm"]
    # a warm attempt that raised reached no Rwp, and the record says so
    assert entry.rwp_warm is None
    reseed = [d for d in result.diagnostics if d.code == "SEQUENTIAL_RESEED"]
    assert [d.where for d in reseed] == [[entry.label or str(FAIL_INDEX)]]
    assert "raised ValueError" in reseed[0].message
    # the rescued pattern seeds its successor like any accepted one
    successor = next(e for e in result.entries if e.index == FAIL_INDEX + 1)
    assert successor.rung == "warm" and not successor.rungs_raised


def test_a_pattern_is_a_failure_only_when_every_rung_raised(
        eight_patterns, fail_on_pattern):
    series = _series()
    result = series.fit(eight_patterns, on_error="carry")
    assert result.n_failed == 1
    fired = [d for d in result.diagnostics if d.code == "SERIES_PATTERN_FAILED"]
    assert "on every rung the chain tried" in fired[0].message
    # keyed on the label like every other per-pattern series diagnostic; it was
    # ``entries[4]``, and ``entries`` omits the failed pattern
    assert fired[0].where == [result.failures[0].label or str(FAIL_INDEX)]
    # rungs that returned elsewhere recorded no raise
    assert all(not e.rungs_raised for e in result.entries)


def test_reseed_false_declines_the_escalation_a_raise_would_take(
        eight_patterns, monkeypatch):
    calls = _poison(monkeypatch, eight_patterns[FAIL_INDEX], fails=lambda n: n == 1)
    series = _series()
    result = series.fit(eight_patterns, on_error="carry", reseed=False)
    assert calls["n"] == 1                 # one rung, no ladder
    assert [f.index for f in result.failures] == [FAIL_INDEX]


def test_a_raise_in_the_callers_hook_is_the_callers(eight_patterns):
    """``constrain``/``prepare`` run outside the guard: the fit is the rung,
    the hook is the caller's code, and a typo in it must not be swallowed
    once per pattern into an empty series."""
    def constrain(index, ref):
        if index == FAIL_INDEX:
            raise KeyError("a typo in the caller's hook")

    series = _series()
    with pytest.raises(KeyError, match="typo"):
        series.fit(eight_patterns, on_error="carry", constrain=constrain)


# ----------------------------------------------------------------------
# WP-1333: the backward pass cannot take the forward chain with it, and an
# unrun comparison is not a clean one
# ----------------------------------------------------------------------
def _fails_after_the_forward_pass(n: int) -> bool:
    # the forward chain fits the target once (its warm rung returns); every
    # fit of it after that is the backward chain's
    return n > 1


def test_a_backward_raise_keeps_the_complete_forward_chain(
        eight_patterns, monkeypatch):
    """Issue #224's series C: the forward chain whole, the backward chain dead.
    Under ``"raise"`` that used to overwrite ``results_`` with the *backward*
    chain's partial state; now the forward chain is published first and goes
    out with the exception, and says the comparison never ran."""
    _poison(monkeypatch, eight_patterns[FAIL_INDEX],
            fails=_fails_after_the_forward_pass)
    series = _series()
    with pytest.raises(ValueError, match="refusing to enumerate") as excinfo:
        series.fit(eight_patterns, direction="both", on_error="raise")

    assert len(series.results_) == N_PATTERNS
    assert series.failures_ == []
    forward = series.result_
    assert forward is excinfo.value.series_result
    assert len(forward.entries) == N_PATTERNS
    assert forward.backward is None and series.backward_ is None
    not_run = [d for d in forward.diagnostics
               if d.code == "SEQUENTIAL_PATH_CHECK_NOT_RUN"]
    assert len(not_run) == 1 and not_run[0].level == "warning"
    assert "did not run: the backward chain raised" in not_run[0].message
    assert f"on pattern {FAIL_INDEX}" in not_run[0].message
    assert forward.direction_gaps is None


def test_a_backward_failure_is_recorded_and_narrows_the_comparison(
        eight_patterns, monkeypatch):
    """Under ``"carry"`` the backward chain's failures were discarded, so the
    comparison ran on seven patterns and said nothing about the eighth."""
    _poison(monkeypatch, eight_patterns[FAIL_INDEX],
            fails=_fails_after_the_forward_pass)
    series = _series()
    result = series.fit(eight_patterns, direction="both", on_error="carry")

    assert len(result.entries) == N_PATTERNS and result.n_failed == 0
    assert [f.index for f in result.backward.failures] == [FAIL_INDEX]
    assert result.backward.n_failed == 1
    failed = [d for d in result.diagnostics if d.code == "SERIES_PATTERN_FAILED"]
    assert len(failed) == 1 and "backward (verification) chain" in failed[0].message

    label = result.backward.failures[0].label or str(FAIL_INDEX)
    partial = [d for d in result.diagnostics
               if d.code == "SEQUENTIAL_PATH_CHECK_INCOMPLETE"
               and d.where == [label]]
    assert len(partial) == 1 and partial[0].level == "info"
    assert partial[0].value == N_PATTERNS - 1
    assert f"ran on {N_PATTERNS - 1} of {N_PATTERNS} patterns" in partial[0].message
    assert "not fitted in the backward chain" in partial[0].message


def test_a_cancelled_backward_chain_reports_the_comparison_as_not_run(
        eight_patterns):
    from rietx.optimize.cancel import CancelToken

    token = CancelToken()
    stop_after = N_PATTERNS - 3            # the backward chain walks 7, 6, 5, …

    def watch(event):
        data = event["data"]
        if (event["kind"] == "fit_end" and data.get("series_pass") == "backward"
                and data.get("series_index") == stop_after):
            token.cancel()

    series = _series()
    result = series.fit(eight_patterns, direction="both", events=watch,
                        cancel=token)

    assert len(result.entries) == N_PATTERNS
    assert result.direction_gaps is None
    not_run = [d for d in result.diagnostics
               if d.code == "SEQUENTIAL_PATH_CHECK_NOT_RUN"]
    assert len(not_run) == 1 and not_run[0].level == "warning"
    assert "backward chain was cancelled after 3 of 8 patterns" in not_run[0].message


def test_a_clean_both_way_series_reports_the_check_as_run(eight_patterns):
    """Zero findings means *checked and clean* only if nothing else fires on a
    clean series — measured here, where a tie row off a never-freed source and
    a coefficient on its floor were the two paths a naive "unjudged" list
    named on every run."""
    series = _series()
    result = series.fit(eight_patterns, direction="both")
    assert not any(d.code in ("SEQUENTIAL_PATH_CHECK_INCOMPLETE",
                              "SEQUENTIAL_PATH_CHECK_NOT_RUN")
                   for d in result.diagnostics)
    assert result.direction_gaps
    assert result.backward is not None and result.backward.n_failed == 0
