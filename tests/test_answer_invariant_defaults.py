"""WP-2002 — the defaults the audit table calls answer-invariant change no number.

``rietx._audit`` tiers a default ``invariant`` only where a test shows the
answer does not move with it.  The observation channels of ``fit``,
``run_stage`` and ``refine`` (an event stream, a progress stream, a cancel
token nobody sets, a label, the run recorder, the per-stage reports, a
history tree) are that class: each is switched on here against a fit with
every channel at its default, and the answer is asserted equal to the bit.
So are ``auto_background``'s ``wavelength`` and ``source``, which reach only
the contamination screen of ``diagnose``, a finding the verb does not read.
WP-2003 adds the series seat: ``refine_sequential`` and
``SequentialRefinement.fit``'s channels, ``on_result`` and ``history``, each
switched on against a three-pattern chain.
#562 S2b adds the solve seat: ``solve_structure``'s ``events``, ``cancel``,
``label`` and ``telemetry``, and ``SolveSpec.heartbeat_sweeps``, each switched
on against one run with every channel at its default.
"""

from __future__ import annotations

import io
import warnings

import numpy as np
import pytest

import rietx as rx
from rietx import runs
from rietx._about import RUNS_DIR_NAME, STATE_DIR_NAME
from rietx.model import compiled
from rietx.optimize.cancel import CancelToken
from rietx.strategy.staged import resolve_plan
from tests.test_refine_synthetic import perturbed_models, synthesize
from tests.test_solve_entry import Acr, _spec

pytestmark = pytest.mark.xdist_group("telemetry")

PLAN = "mccusker_default"


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _answer(result):
    return ([(p.path, p.value, p.stderr) for p in result.parameters],
            result.statistics.rwp, np.asarray(result.y_calc))


def _same(a, b):
    assert a[0] == b[0]
    assert a[1] == b[1]
    assert np.array_equal(a[2], b[2])


def _fit(pattern, **kw):
    structure, ins = perturbed_models()
    return _answer(rx.Refinement(structure, ins, history=False).fit(pattern, plan=PLAN, **kw))


def _stage(pattern, **kw):
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    stage = resolve_plan(PLAN, "rietveld").stages[0]
    return _answer(ref.run_stage(pattern, stage, **kw))


@pytest.fixture(scope="module")
def baseline(pattern):
    return _fit(pattern)


@pytest.fixture
def recording(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    was = runs.set_enabled(True)
    try:
        yield
    finally:
        runs.set_enabled(was)


def _recorded(tmp_path):
    """How many runs the recorder wrote under the working directory: a test
    whose recorder never ran would compare two unrecorded fits and pass."""
    root = tmp_path / STATE_DIR_NAME / RUNS_DIR_NAME
    return len(list(root.glob(f"*/{runs.META_FILE}")))


@pytest.mark.parametrize("channel", ["events", "progress", "cancel", "label",
                                     "stage_reports"])
def test_a_fit_observed_is_the_fit_unobserved(pattern, baseline, tmp_path, channel):
    kw = {"events": tmp_path / "events.jsonl", "progress": io.StringIO(),
          "cancel": CancelToken(), "label": "observed", "stage_reports": True}
    _same(_fit(pattern, **{channel: kw[channel]}), baseline)


def test_a_recorded_fit_is_the_fit_unrecorded(pattern, baseline, tmp_path, recording):
    _same(_fit(pattern), baseline)
    assert _recorded(tmp_path) == 1


def test_a_stage_observed_is_the_stage_unobserved(pattern, tmp_path, recording):
    plain = _stage(pattern, telemetry=False)
    assert _recorded(tmp_path) == 0
    _same(_stage(pattern, events=tmp_path / "events.jsonl", cancel=CancelToken(),
                 label="observed"), plain)
    assert _recorded(tmp_path) == 1


def test_refine_observed_with_a_history_tree_is_refine_without(pattern, baseline,
                                                               tmp_path, recording):
    structure, ins = perturbed_models()
    _same(_answer(rx.refine(pattern, structure, ins, plan=PLAN, history=True,
                            events=tmp_path / "events.jsonl", cancel=CancelToken(),
                            label="observed")), baseline)
    assert _recorded(tmp_path) == 1


@pytest.mark.parametrize("kind", ["pspline", "chebyshev"])
def test_auto_background_chooses_alike_with_the_beam_declared(kind):
    """The model and every score beside it are the same with ``wavelength``
    and ``source`` as without them (WP-2002, B12).  The pattern carries a Kβ
    leak the screen finds, so the two calls' diagnostics do differ."""
    from rietx.background import diagnose
    from tests.test_background_auto import (
        WAVELENGTH,
        _dope_ghost,
        _flat_bkg,
        _peaky_pattern,
    )

    data, _ = _dope_ghost(_peaky_pattern(background=_flat_bkg, scale=3e-3),
                          WAVELENGTH, 1.3922340)
    assert diagnose(data, wavelength=WAVELENGTH).contamination
    assert not diagnose(data).contamination
    source = rx.Instrument.bragg_brentano(radiation="CuKa").source
    with warnings.catch_warnings():
        # a Chebyshev scan that reaches its cap says so on each call
        warnings.simplefilter("ignore", UserWarning)
        bare = rx.auto_background(data, kind=kind)
        declared = rx.auto_background(data, kind=kind, source=source,
                                      wavelength=WAVELENGTH)
    assert declared.model_dump() == bare.model_dump()


# -- the series seat (WP-2003) ------------------------------------------------
#
# ``refine_sequential`` and ``SequentialRefinement.fit`` carry the same
# observation channels, plus ``on_result`` (a callback handed each kept fit)
# and ``history`` (one tree per pattern).  A chain is switched on against the
# same chain with every channel at its default: three patterns of the
# thermal ramp under the default plan, so a cold fit and two warm rungs run.


@pytest.fixture(scope="module")
def ramp():
    from tests.test_sequential import A0, RAMP, _simulate

    return [_simulate(A0 * (1.0 + RAMP * k), seed=11 + k) for k in range(3)]


def _chain(ramp, **kw):
    from tests.test_sequential import _start_models, chain_answer

    structure, ins = _start_models()
    return chain_answer(rx.refine_sequential(ramp, structure, ins, plan=PLAN, **kw))


@pytest.fixture(scope="module")
def series_baseline(ramp):
    return _chain(ramp)


@pytest.mark.parametrize("channel", ["events", "progress", "cancel", "label",
                                     "on_result", "history"])
def test_a_series_observed_is_the_series_unobserved(ramp, series_baseline, tmp_path,
                                                    channel):
    seen = []
    kw = {"events": tmp_path / "events.jsonl", "progress": io.StringIO(),
          "cancel": CancelToken(), "label": "observed",
          "on_result": lambda k, result: seen.append(k), "history": True}
    assert _chain(ramp, **{channel: kw[channel]}) == series_baseline
    if channel == "on_result":
        assert seen == [0, 1, 2], "the callback ran, once a pattern"


def test_a_recorded_series_is_the_series_unrecorded(ramp, series_baseline, tmp_path,
                                                    recording):
    assert _chain(ramp) == series_baseline
    assert _recorded(tmp_path) == 1, "one run directory for one job"


# ===================================================================================
# the solve seat (#562 S2b)
# ===================================================================================
@pytest.fixture(scope="module")
def solver():
    """One synthetic acridine problem, solved under a declared compiled tier
    (a bit-identity assertion says which path produced its bytes)."""
    was = compiled.set_enabled(True)
    try:
        yield Acr()
    finally:
        compiled.set_enabled(was)


#: One seed, no control seed, 1 000 sweeps: a run short enough to repeat per
#: channel, long enough to cross a rebuild boundary and polish a state.
def _solved(solver, heartbeat=None, **kw):
    spec = _spec(seeds=(0,), control_seeds=(), sweeps=1000, heartbeat_sweeps=heartbeat)
    return solver.solve(spec, **kw)


def _solve_answer(res):
    """Every field but what a run's own bookkeeping owns, and the spec: the
    heartbeat is a field of it, so the spec cannot be compared across it."""
    return res.model_dump_json(exclude={"timings", "provenance", "resumed", "spec"})


@pytest.fixture(scope="module")
def solve_baseline(solver):
    return _solve_answer(_solved(solver))


@pytest.mark.parametrize("channel", ["events", "cancel", "label", "heartbeat"])
def test_a_solve_observed_is_the_solve_unobserved(solver, solve_baseline, channel):
    got: list[dict] = []
    kw = {"events": {"events": got.append}, "cancel": {"cancel": CancelToken()},
          "label": {"label": "observed"}, "heartbeat": {"heartbeat": 250, "events": got.append}}
    res = _solved(solver, **kw[channel])
    assert _solve_answer(res) == solve_baseline
    if channel in ("events", "heartbeat"):
        assert got, "the channel under test never received a line"
    if channel == "heartbeat":
        assert any(e["kind"] == "solve_step" for e in got)


def test_a_recorded_solve_is_the_solve_unrecorded(solver, solve_baseline, tmp_path):
    was = runs.set_enabled(True)
    try:
        res = _solved(solver, telemetry=tmp_path, label="recorded")
    finally:
        runs.set_enabled(was)
    assert _solve_answer(res) == solve_baseline
    assert len(runs.discover(tmp_path)) == 1
