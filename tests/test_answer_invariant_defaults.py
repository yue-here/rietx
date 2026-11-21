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
switched on against a three-pattern chain, and the axis and pattern names
(``x``, ``x_label``, ``labels``), the names compared blind.
"""

from __future__ import annotations

import io
import warnings

import numpy as np
import pytest

import rietx as rx
from rietx import runs
from rietx._about import RUNS_DIR_NAME, STATE_DIR_NAME
from rietx.optimize.cancel import CancelToken
from rietx.strategy.staged import resolve_plan
from tests.test_refine_synthetic import perturbed_models, synthesize

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


def _chain(ramp, sink=None, **kw):
    from tests.test_sequential import _start_models, chain_answer

    structure, ins = _start_models()
    series = rx.refine_sequential(ramp, structure, ins, plan=PLAN, **kw)
    if sink is not None:
        sink.append(series)
    return chain_answer(series)


@pytest.fixture(scope="module")
def series_baseline(ramp):
    return _chain(ramp)


@pytest.mark.parametrize("channel", ["events", "progress", "cancel", "label",
                                     "on_result", "history", "x", "x_label"])
def test_a_series_observed_is_the_series_unobserved(ramp, series_baseline, tmp_path,
                                                    channel):
    """``x`` and ``x_label`` name the series axis (WP-2003 C11): no fitted value
    reads them, so they join the channels."""
    seen = []
    kw = {"events": tmp_path / "events.jsonl", "progress": io.StringIO(),
          "cancel": CancelToken(), "label": "observed",
          "on_result": lambda k, result: seen.append(k), "history": True,
          "x": [300.0, 350.0, 400.0], "x_label": "T (K)"}
    sink = []
    assert _chain(ramp, sink, **{channel: kw[channel]}) == series_baseline
    if channel == "on_result":
        assert seen == [0, 1, 2], "the callback ran, once a pattern"
    # the axis reached the record, or this compares two default chains
    (series,) = sink
    if channel == "x":
        assert [e.x for e in series.entries] == kw["x"]
    if channel == "x_label":
        assert series.x_label == kw["x_label"]


def _label_blind(answer):
    """``chain_answer`` with every pattern label taken out: the entries' own
    and each step's pair, which carry the names and nothing else."""
    entries, codes, steps = answer
    return ([entry[1:] for entry in entries], codes,
            [step.model_copy(update={"labels": ("", "")}) for step in steps])


def _gaps(series):
    """Every direction gap with its label taken out, in the record's order."""
    return [gap.model_copy(update={"label": ""}) for gap in series.direction_gaps]


@pytest.mark.parametrize("direction", ["forward", "both"])
def test_a_series_named_is_the_series_unnamed(ramp, series_baseline, direction):
    """``labels`` names each pattern, its history file and the pairing of the
    two chains (WP-2003 C11), so a compare blind to the names is the
    invariance claim; the names themselves must still be the ones given.
    Under ``direction="both"`` the gaps, which pair the chains by label, are
    compared too."""
    labels = ["first", "second", "third"]
    named, unnamed = [], []
    answer = _chain(ramp, named, labels=labels, direction=direction)
    baseline = (series_baseline if direction == "forward" else
                _chain(ramp, unnamed, direction=direction))
    assert [entry[0] for entry in answer[0]] == labels, "the labels reached the record"
    assert [entry[0] for entry in baseline[0]] != labels
    assert _label_blind(answer) == _label_blind(baseline)
    if direction == "both":
        assert named[0].direction_gaps, "the two chains were paired"
        assert [g.label for g in named[0].direction_gaps if g.label] and all(
            g.label in labels for g in named[0].direction_gaps)
        assert _gaps(named[0]) == _gaps(unnamed[0])


def test_a_recorded_series_is_the_series_unrecorded(ramp, series_baseline, tmp_path,
                                                    recording):
    assert _chain(ramp) == series_baseline
    assert _recorded(tmp_path) == 1, "one run directory for one job"
