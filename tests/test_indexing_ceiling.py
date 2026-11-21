"""WP-1037 — the whole-run ceiling, the pre-run estimate and honest progress.

Three families, and the epistemics of each are stated where they bite:

* **Deadline / estimate arithmetic** — deterministic, no wall-clock assertions
  at all: the estimate is arithmetic on the spec and the token semantics are
  logic, so nothing here can become a load sensor.
* **The distinction tests** — a *user* cancellation and an *expired ceiling*
  must never read as one another (`cancelled_by_user`), and a cancelled
  validation must never read as a refuted candidate (trap 1 of the WP).  Both
  are driven by pre-set tokens, so they are deterministic too.
* **The one timed test** asserts only what cannot depend on machine load: a
  binding ceiling returns a *complete result* whose claims are internally
  consistent — never which systems happened to be reached, which is exactly the
  claim CLAUDE.md forbids a test to make (a budget in a test is a runaway
  guard, never a timer).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.history.events import EVENT_SCHEMA_VERSION, EventRecord
from rietx.indexing import index_pattern
from rietx.indexing.engines import (
    MODELLED_ENGINES,
    Budget,
    Deadline,
    Progress,
    SearchSpec,
    engine_names,
    estimate_ceiling,
)
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from tests.test_indexing_engines import LAM, synthetic_peaks

pytestmark = pytest.mark.xdist_group("indexing-ceiling")


@pytest.fixture(scope="module")
def cubic_peaks():
    """Exact cubic positions, declared σ — 30 usable lines, enough for the
    quality gate (``synthetic_peaks``'s default 90° range yields 19, one short
    of the 20 the figures of merit are scored on)."""
    peaks, cell = synthetic_peaks("cubic", two_theta_max=150.0)
    assert len(peaks.usable()) >= 20
    return peaks, cell


# ----------------------------------------------------------------------
# Deadline: a clock shaped as a cancel token
# ----------------------------------------------------------------------
def test_deadline_is_a_cancel_token_and_composes_with_one():
    """`bool`, `is_set`, `remaining`, `cancelled_by_user` — and the any-of
    composition with the caller's own token, written once in Budget."""
    token = CancelToken()
    d = Deadline(3600.0, cancel=token)
    assert not bool(d) and not d.is_set() and not d.cancelled_by_user()
    assert 0.0 < d.remaining <= 3600.0

    token.cancel()
    # the user's token fires *through* the deadline, and is attributed to them
    assert bool(d) and d.is_set() and d.cancelled_by_user()


def test_an_expired_deadline_is_not_a_user_cancellation():
    d = Deadline(1e-9)
    assert d.expired() and bool(d) and d.is_set()
    assert d.remaining == 0.0
    assert not d.cancelled_by_user()


def test_an_unbounded_deadline_never_expires_and_reports_inf():
    d = Deadline(0.0)
    assert not bool(d)
    assert d.remaining == float("inf")


def test_the_deadline_nests_under_a_per_system_budget():
    """The whole design in one assertion: engines build
    ``Budget(budget_seconds, cancel)`` and the deadline *is* that cancel, so an
    expired ceiling expires every per-system budget with no engine changes."""
    expired = Deadline(1e-9)
    fresh_budget = Budget(3600.0, cancel=expired)
    assert fresh_budget.expired()

    live = Deadline(3600.0)
    assert not Budget(3600.0, cancel=live).expired()


# ----------------------------------------------------------------------
# estimate_ceiling: arithmetic, not prediction
# ----------------------------------------------------------------------
def test_the_default_ceiling_is_the_arithmetic_the_wp_measured():
    """2 engines × 7 systems × 30 s search, 4 low-DOF systems × 3 rungs × 30 s
    probe — the ~1400 s worst case nothing used to state, against a measured
    typical of well under 200 s.  These are *derived* here from the same
    constants the engines read, so the test fails when a constant moves without
    this arithmetic moving with it."""
    est = estimate_ceiling()
    n_engines = len([n for n in engine_names() if n in MODELLED_ENGINES])
    assert est.search_seconds == n_engines * 7 * 30.0
    assert est.probe_seconds == 4 * 3 * 30.0
    assert est.validation_calls == SearchSpec().max_candidates
    assert est.worst_case_seconds == (
        est.search_seconds + est.probe_seconds
        + est.validation_calls * est.validation_seconds_each[1])
    # the measured claims travel with the arithmetic, in the right order
    assert est.typical_seconds[0] < est.typical_seconds[1]
    assert est.validation_seconds_each[0] < est.validation_seconds_each[1]
    assert est.granularity_seconds > 0.0
    assert est.covers == tuple(engine_names())
    assert est.unmodelled == ()


def test_the_ceiling_scales_with_the_spec_not_with_hope():
    spec = SearchSpec(systems=("cubic", "monoclinic"), budget_seconds=10.0)
    est = estimate_ceiling(spec, engines=("dichotomy",), validate=False)
    assert est.search_seconds == 1 * 2 * 10.0
    assert est.probe_seconds == 0.0          # the probe is trial_error's
    assert est.validation_calls == 0

    both = estimate_ceiling(spec, engines=("dichotomy", "trial_error"))
    # only cubic is probe-eligible (METRIC_DOF ≤ 2); rungs cap at the caller's
    # own budget when it is below the probe's
    assert both.probe_seconds == 1 * 3 * 10.0


def test_an_unmodelled_engine_is_named_not_silently_free():
    est = estimate_ceiling(engines=("dichotomy", "montecarlo_v2"))
    assert est.covers == ("dichotomy",)
    assert est.unmodelled == ("montecarlo_v2",)


# ----------------------------------------------------------------------
# the honest states: user cancel vs ceiling, validated vs refuted
# ----------------------------------------------------------------------
def test_a_pre_set_user_token_reports_nothing_as_a_budget_statement(
        cubic_peaks):
    """A cancelled run has empty claims — and no ``INDEX_BUDGET_EXHAUSTED``,
    because a user cancellation says nothing about the budget.  Engines claim a
    system only when they start it, so nothing is reported as a zero-second
    'search'."""
    peaks, _cell = cubic_peaks
    token = CancelToken()
    token.cancel()
    res = index_pattern(peaks, spec=SearchSpec(systems=("cubic",)),
                        cancel=token)
    assert res.engines_run == []
    assert res.systems_searched == []
    assert res.search_complete == {}
    assert "INDEX_BUDGET_EXHAUSTED" not in {d.code for d in res.diagnostics}


def test_a_cancelled_validation_raises_rather_than_refuting(tiny_pattern):
    """Trap 1 of the WP: ``RefinementCancelled`` must re-raise *before* the
    generic handler.  Swallowed, it becomes ``status="failed"`` — which the
    gate reads as ``validation_failed``, a **refuting** caveat — for a cell the
    run merely ran out of time on."""
    from rietx.indexing.workflow import validate_by_lebail
    from rietx.schemas.indexing import CellCandidate

    data, instrument, a = tiny_pattern
    cand = CellCandidate(cell=(a, a, a, 90.0, 90.0, 90.0),
                         cell_esd=(1e-4,) * 6, system="cubic")
    token = CancelToken()
    token.cancel()
    with pytest.raises(RefinementCancelled):
        validate_by_lebail(cand, data, instrument, cancel=token)


def test_a_validation_stopped_mid_loop_caps_and_never_refutes(
        cubic_peaks, tiny_pattern, monkeypatch):
    """The loop half of trap 1: the token fires after the first validation, the
    run still returns, and the unreached candidates read ``not_validated``
    (capping) — ``validation_failed`` (refuting) appears nowhere.

    A claim about the validation loop, so one engine reporting two candidates
    carries it: one validated, one the token stops.  The ambiguity sweep over a
    full report, which nothing here reads, was most of this test (WP-2019)."""
    import rietx.indexing.workflow as workflow

    peaks, _cell = cubic_peaks
    data, instrument, _a = tiny_pattern
    token = CancelToken()
    real = workflow.validate_by_lebail
    calls = []

    def cancel_after_first(*args, **kwargs):
        if calls:
            # the second call sees a set token exactly as a mid-fit expiry
            # would: at the first eval boundary, as RefinementCancelled
            raise RefinementCancelled("cancelled")
        calls.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(workflow, "validate_by_lebail", cancel_after_first)
    res = index_pattern(peaks, data=data, instrument=instrument,
                        spec=SearchSpec(systems=("cubic",), max_candidates=2),
                        engines=("dichotomy",), cancel=token)
    assert len(calls) == 1 and len(res.candidates) == 2
    assert res.validated
    caveats = {c for cand in res.candidates for c in cand.confidence_caveats}
    assert "validation_failed" not in caveats
    assert any(cand.lebail is None and "not_validated" in
               cand.confidence_caveats for cand in res.candidates)


@pytest.mark.parametrize("ceiling", [600.0, None])
def test_under_a_ceiling_validation_runs_cheapest_first(
        cubic_peaks, tiny_pattern, monkeypatch, ceiling):
    """Under a declared ceiling the validation fits run in order of the
    reflections each refines, the order that finishes the most fits by a
    common deadline (WP-2011); with no ceiling they run in rank order, as
    they always did.  Each fit runs on the run's clock, with no slice."""
    import importlib

    import rietx.indexing.workflow as workflow

    consensus = importlib.import_module("rietx.indexing.consensus")
    peaks, _cell = cubic_peaks
    data, instrument, _a = tiny_pattern
    real_fit, real_checked = workflow.validate_by_lebail, consensus.checked_indices
    ranked, seen = [], []

    def checked(candidates, *args, **kwargs):
        out = real_checked(candidates, *args, **kwargs)
        if not seen:    # the list validation visits; ambiguity asks again after
            ranked[:] = [candidates[i] for i in out]
        return out

    def record(cand, *args, **kwargs):
        seen.append((cand, kwargs["cancel"]))
        return real_fit(cand, *args, **kwargs)

    monkeypatch.setattr(consensus, "checked_indices", checked)
    monkeypatch.setattr(workflow, "validate_by_lebail", record)
    # no ceiling is preset "full": under the default "quick" a None is filled
    index_pattern(peaks, data=data, instrument=instrument,
                  spec=SearchSpec(systems=("cubic",), max_candidates=3,
                                  total_budget_seconds=ceiling),
                  engines=("dichotomy",),
                  preset="full" if ceiling is None else None)
    visited = [c for c, _ in seen]
    assert len(visited) == len(ranked) >= 2
    if ceiling is None:
        assert visited == ranked
        assert all(token is None for _, token in seen)
    else:
        size = {id(c): workflow.validation_size(c, peaks.wavelength, data)
                for c in ranked}
        assert visited == sorted(ranked, key=lambda c: size[id(c)])
        # the order is not the rank order here, so the sort is what put it so
        assert visited != ranked
        # one token, the run's own: no fit draws a slice of it
        assert len({id(token) for _, token in seen}) == 1


@pytest.fixture(scope="module")
def tiny_pattern():
    """A small forward-modelled cubic pattern — just enough for a Le Bail
    validation to have something to fit."""
    from rietx.model.forward import compile_model
    from rietx.params.vector import ParameterTable
    from rietx.schemas.instrument import Instrument
    from rietx.schemas.pattern import PatternData
    from rietx.schemas.structure import (
        Atom,
        Cell,
        Parameter,
        Phase,
        Structure,
    )

    a = 4.1566
    structure = Structure(phases=[Phase(
        name="cube", space_group="P m -3 m",
        cell=Cell(a=Parameter(value=a), b=Parameter(value=a),
                  c=Parameter(value=a), alpha=Parameter(value=90.0),
                  beta=Parameter(value=90.0), gamma=Parameter(value=90.0)),
        atoms=[Atom(label="X", species="C", x=Parameter(value=0.0),
                    y=Parameter(value=0.0), z=Parameter(value=0.0))])])
    instrument = Instrument.debye_scherrer(wavelength=LAM)
    tt = np.arange(15.0, 60.0, 0.02)
    blank = PatternData(two_theta=tt.tolist(),
                        intensity=np.zeros_like(tt).tolist())
    model = compile_model(structure, instrument, blank, mode="rietveld")
    table = ParameterTable(structure, instrument)
    y = model.evaluate(table.decode(table.x0()))
    y = np.random.default_rng(7).poisson(np.maximum(y, 1.0)).astype(float)
    data = PatternData(two_theta=model.tt.tolist(), intensity=y.tolist())
    return data, instrument, a


# ----------------------------------------------------------------------
# a binding ceiling: complete result, three states, internal consistency
# ----------------------------------------------------------------------
def test_a_binding_ceiling_returns_a_complete_and_consistent_result(
        cubic_peaks):
    """The ceiling is a **runaway guard in this test too**: nothing here
    asserts *which* systems were reached — that is machine load — only that
    whatever was reached is claimed consistently and whatever was not is named.
    The requested set always partitions exactly into searched ∪ not-reached."""
    peaks, _cell = cubic_peaks
    requested = ("cubic", "tetragonal", "orthorhombic", "monoclinic")
    res = index_pattern(peaks, spec=SearchSpec(
        systems=requested, total_budget_seconds=2.0))

    codes = {d.code for d in res.diagnostics}
    assert "INDEX_BUDGET_EXHAUSTED" in codes, (
        "a 2 s ceiling on a four-system search must bind")
    # three states, no overlap, nothing lost
    searched = set(res.systems_searched)
    assert searched <= set(requested)
    assert set(res.search_complete) == searched, (
        "a claimed system carries a completion verdict, an unclaimed one "
        "carries nothing")
    exhausted = next(d for d in res.diagnostics
                     if d.code == "INDEX_BUDGET_EXHAUSTED")
    not_reached = set()
    for entry in exhausted.where:
        if entry.startswith("not reached: "):
            not_reached = set(entry.removeprefix("not reached: ").split(", "))
    assert searched | not_reached == set(requested)
    assert searched & not_reached == set()
    # the run returned an answer object, not an exception — and its notes
    # record the ceiling it ran under
    assert res.provenance.notes["total_budget_seconds"] == "2"


def test_full_means_no_ceiling_and_quick_is_what_default_means(cubic_peaks):
    """Since WP-1042 the default **is** a ceiling (`quick`), so the no-ceiling
    state is a declaration: `preset="full"` writes no `total_budget_seconds`
    note — the absence is the record — while a default run writes quick's.

    A claim about the record, so one engine reporting one candidate carries
    it.  Each run's cost was the ambiguity sweep over the reported list (~19 s
    a run over twelve candidates, which one engine alone makes larger, since
    each of its candidates is then "found by every engine" and checked), and
    nothing here reads it (WP-2019)."""
    peaks, _cell = cubic_peaks
    spec = SearchSpec(systems=("cubic",), max_candidates=1)
    res = index_pattern(peaks, spec=spec, preset="full", engines=("dichotomy",))
    assert res.preset == "full"
    assert "total_budget_seconds" not in res.provenance.notes
    assert "INDEX_BUDGET_EXHAUSTED" not in {d.code for d in res.diagnostics}

    quick = index_pattern(peaks, spec=spec, engines=("dichotomy",))
    assert quick.preset == "quick"
    assert "total_budget_seconds" in quick.provenance.notes


# ----------------------------------------------------------------------
# progress: one flat ladder on the existing kinds
# ----------------------------------------------------------------------
def test_progress_is_one_flat_ladder_on_the_existing_kinds(cubic_peaks):
    """Per (engine × system) units with a monotone 1-based index, the
    per-engine pair *replaced* (trap 2: two ladders on one kind is what made a
    progress bar jump), and — asserted, per the WP — no
    ``EVENT_SCHEMA_VERSION`` bump: the ladder adds fields and revises
    ``n_stages``, neither of which is a new kind.  The constant was "3" from
    WP-1322's run header, a record and not a kind, and is "4" since #562 S2b's
    solve kinds; the indexing ladder never moved it.

    Every engine runs, because the claim is that every engine feeds the ladder.
    One candidate is reported: the ambiguity sweep over a full report runs after
    the ladder, emits nothing on it, and was ~12 s of this test (WP-2019)."""
    assert EVENT_SCHEMA_VERSION == "4"

    peaks, _cell = cubic_peaks
    events = []
    res = index_pattern(peaks, spec=SearchSpec(systems=("cubic", "tetragonal"),
                                               max_candidates=1),
                        events=events.append)
    assert res.systems_searched == ["cubic", "tetragonal"]

    starts = [e["data"] for e in events if e["kind"] == "stage_start"]
    ends = [e["data"] for e in events if e["kind"] == "stage_end"]
    assert len(starts) == len(ends) and starts
    # the replaced per-engine pair must not come back beside the ladder
    assert all(not d["stage"].startswith("engine:") for d in starts)
    # every search unit names its engine and system; indices are 1-based and
    # monotone; n_stages never claims less than the units already done
    assert [d["index"] for d in starts] == list(range(1, len(starts) + 1))
    for d in starts:
        assert d["n_stages"] >= d["index"]
    search_units = {(d.get("engine"), d.get("system")) for d in starts
                    if not d.get("probe") and not d.get("validation")
                    and not d.get("consensus")}
    # quoted from the **live registry**, never spelled out: a fourth engine that
    # forgot to feed ``progress`` must fail this row rather than be absent from
    # the expectation it is meant to satisfy (the WP-0602 meta-test pattern, and
    # what let WP-1040's third engine land without touching this assertion)
    assert search_units == {(e, s) for e in engine_names()
                            for s in ("cubic", "tetragonal")}
    # every event line is a valid record of the *current* schema
    for e in events:
        EventRecord.model_validate(e)


def test_progress_with_no_stream_is_a_working_no_op(cubic_peaks):
    """Direct engine calls in unit tests pass no stream and must not change
    behaviour — the counter still counts, nothing emits."""
    p = Progress(None, total=2)
    p.start("dichotomy:cubic")
    p.end("dichotomy:cubic")
    p.add(1)
    assert (p.done, p.total) == (1, 3)

    peaks, _cell = cubic_peaks
    from rietx.indexing.dichotomy import search_dichotomy
    res = search_dichotomy(peaks, spec=SearchSpec(systems=("cubic",)))
    assert res.systems_searched == ("cubic",)
