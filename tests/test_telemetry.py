"""WP-1403 — a fit nobody asked to record records itself.

The premise is a measurement, not a preference. WP-1322 gave three independent
subagents a benchmarking task and no instructions about how to drive rietx; all
three found and read the packaged skill in full, and all three wrote
``history=False``. Reconstructing timing from their own transcripts afterwards
recovered 2.7-16.6 % coverage and nothing from inside a solve. Documenting the
knob harder is the fix that had already been tried, and an agent cannot switch
off by accident what it never had to switch on.

So the assertions here are mostly about what recording must **never** cost:
a fit that carries on when the directory is read-only, a caller's exception
that still reaches them, and a suite that grows no directories at all. The one
positive claim — the four files land and the watcher lists them — is the
acceptance, and it is asserted through ``runs.discover`` rather than by
building paths, because "the watcher lists it" is the thing that was promised.

Recording is **off** for the suite (``conftest``), so every test that wants it
takes the ``recording`` fixture. ``test_the_suite_itself_records_nothing`` is
the meta-test for the other direction: without it the suite would grow hundreds
of run directories the first time somebody changed the default.
"""

from __future__ import annotations

import json
import os
import sys
import time
import warnings
from contextlib import contextmanager
from pathlib import Path

import pytest

import rietx as rx
from rietx import runs
from rietx._about import RUNS_DIR_NAME, STATE_DIR_NAME, TELEMETRY_ENV
from rietx.history.events import EventStream, read_events
from rietx.model.forward import CompiledModel
from rietx.optimize.cancel import CancelToken, RefinementCancelled
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("telemetry")


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


@pytest.fixture
def recording():
    """Switch recording on for one test, and put it back.

    ``runs.set_enabled`` rather than the environment: it is the seam that
    exists for this, it mirrors ``model.compiled.set_enabled``, and it cannot
    leak into another xdist worker the way an ``os.environ`` write can.
    """
    was = runs.set_enabled(True)
    runs._PRUNED = False
    runs._WARNED = False
    try:
        yield
    finally:
        runs.set_enabled(was)


def _fit(pattern, **kw):
    structure, ins = perturbed_models()
    return rx.Refinement(structure, ins, history=False).fit(pattern, **kw)


# ----------------------------------------------------------------------
# the acceptance
# ----------------------------------------------------------------------
def test_a_plain_fit_in_an_empty_directory_is_a_run_the_watcher_lists(
        tmp_path, monkeypatch, pattern, recording):
    """WP-1403's acceptance, asserted the way it is written."""
    monkeypatch.chdir(tmp_path)
    result = _fit(pattern)

    (run,) = runs.discover(tmp_path)
    assert run.path.parent == tmp_path / STATE_DIR_NAME / RUNS_DIR_NAME
    assert runs.RUN_ID_RE.match(run.path.name)
    assert run.legacy is False

    for name in (runs.EVENTS_FILE, runs.META_FILE, runs.STATUS_FILE,
                 runs.SNAPSHOT_FILE, runs.SUMMARY_FILE):
        assert (run.path / name).is_file(), name

    assert run.meta is not None and run.meta.record == runs.RECORD_TAG
    assert run.meta.cwd == str(tmp_path)
    assert run.status is not None
    assert run.status.state == "done"
    assert run.status.error is None
    assert run.status.pid == os.getpid()
    assert run.status.rwp == pytest.approx(result.statistics.rwp)
    assert runs.liveness_of(run).state == "done"


def test_the_root_hides_itself_from_git(tmp_path, monkeypatch, pattern,
                                        recording):
    """A fit inside somebody's repository does not turn up in their status."""
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    root = tmp_path / STATE_DIR_NAME / RUNS_DIR_NAME
    assert (root / runs.GITIGNORE_FILE).read_text(encoding="utf-8").strip() == "*"


def test_summary_is_the_termination_view_and_not_a_report(
        tmp_path, monkeypatch, pattern, recording):
    """``str(result)``, never ``ref.summary()`` — the expensive half (WP-1335)."""
    monkeypatch.chdir(tmp_path)
    result = _fit(pattern)
    (run,) = runs.discover(tmp_path)
    assert (run.path / runs.SUMMARY_FILE).read_text(encoding="utf-8") == str(result)


def test_the_status_rwp_is_the_last_stage_end_in_the_log(
        tmp_path, monkeypatch, pattern, recording):
    """A projection, never a computation.

    The final ``rwp`` comes off ``fit_end`` — the fitted result's own number —
    and the stage before it off the last ``stage_end``. Both are copied from
    the event that carried them, so the file and the log cannot disagree.
    """
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    (run,) = runs.discover(tmp_path)
    log = read_events(run.path / runs.EVENTS_FILE)
    ends = [e for e in log if e.kind == "fit_end"]
    assert len(ends) == 1
    assert run.status.rwp == pytest.approx(ends[0].data["rwp"])
    assert run.status.gof == pytest.approx(ends[0].data["gof"])

    stage_ends = [e for e in log if e.kind == "stage_end"]
    assert stage_ends, "a staged plan emitted no stage_end"
    assert run.status.stage == stage_ends[-1].data["stage"]


def test_the_stage_number_is_read_off_index_and_never_counted(
        tmp_path, monkeypatch, pattern, recording):
    """WP-1301's trap: a released phase emits a *second* ``stage_start``.

    A counter would say "stage 6 of 5" the first time that happens. This
    asserts the mechanism rather than waiting for a phase release: the status
    agrees with the last ``stage_start``'s own ``index``, whatever the number
    of ``stage_start`` events was.
    """
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    (run,) = runs.discover(tmp_path)
    starts = [e for e in read_events(run.path / runs.EVENTS_FILE)
              if e.kind == "stage_start"]
    assert run.status.index == starts[-1].data["index"]
    assert run.status.n_stages == starts[-1].data["n_stages"]
    assert run.status.index <= run.status.n_stages


def test_run_stage_records_a_run_with_a_picture(tmp_path, monkeypatch, pattern,
                                                recording):
    """One stage driven on its own is a run, and it has a snapshot (WP-1402)."""
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    ref.run_stage(pattern, rx.Stage(name="background",
                                    turn_on=["instrument.background.*"]))
    (run,) = runs.discover(tmp_path)
    assert run.has_snapshot is True
    payload = json.loads((run.path / runs.SNAPSHOT_FILE).read_text(encoding="utf-8"))
    assert payload["stage"] == "background"
    assert payload["y_calc"] and payload["two_theta"]


# ----------------------------------------------------------------------
# naming a run (WP-1431)
# ----------------------------------------------------------------------
def test_a_caller_names_its_run_and_the_watcher_shows_that_name(
        tmp_path, monkeypatch, pattern, recording):
    """WP-1431's acceptance: the caller's word wins over the derived one.

    Unnamed, every run driven from one directory is called after that
    directory, so a batch of candidates writes a column of identical names.
    The label goes to ``meta.json`` and comes back through ``read_run``, which
    is the whole path the page reads.
    """
    monkeypatch.chdir(tmp_path)
    _fit(pattern, label="candidate-07 rutile")

    (run,) = runs.discover(tmp_path)
    assert run.label == "candidate-07 rutile"
    assert run.meta is not None and run.meta.label == "candidate-07 rutile"
    assert json.loads((run.path / runs.META_FILE).read_text(
        encoding="utf-8"))["label"] == "candidate-07 rutile"
    # the derived name is what it displaced, and it was the directory's
    assert run.label != tmp_path.name


def test_an_unnamed_run_keeps_the_derived_name(tmp_path, monkeypatch, pattern,
                                               recording):
    """The default is unchanged by the keyword existing."""
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    (run,) = runs.discover(tmp_path)
    assert run.label == tmp_path.name


def test_every_verb_that_records_a_run_can_name_it(tmp_path, monkeypatch,
                                                   pattern, recording):
    """Three ``runs.attach`` call sites, so the keyword is on all of them.

    ``Refinement.fit`` is covered above; this is the rest of the class.
    ``refine`` forwards to ``fit`` and ``Project.fit`` forwards through its
    ``**kw``, so what is asserted here is that the label survives each hop.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()

    stage_dir = tmp_path / "stage"
    rx.Refinement(structure, ins, history=False).run_stage(
        pattern, rx.Stage(name="background", turn_on=["instrument.background.*"]),
        telemetry=str(stage_dir), label="one stage by hand")
    (run,) = runs.discover(stage_dir)
    assert run.label == "one stage by hand"

    shot_dir = tmp_path / "shot"
    rx.refine(pattern, structure, ins, telemetry=str(shot_dir),
              label="the one-shot form")
    (run,) = runs.discover(shot_dir)
    assert run.label == "the one-shot form"


def test_a_project_forwards_the_label_through_its_kw(tmp_path, pattern,
                                                    recording):
    """``Project.fit`` takes no explicit keyword, so this is the hop itself.

    It forwards ``**kw`` to ``Refinement.fit`` after its own setdefaults, and
    the manual and the skill both name it as a verb that takes ``label=``. A
    documented claim with no writer is the class WP-1076 is about, so the hop
    is asserted rather than read off the source. The run lands in the
    project's ``live/``, which is where a project's telemetry goes.
    """
    from tests.test_project import _write_xye

    structure, ins = perturbed_models()
    path = _write_xye(tmp_path / "synth.xye", pattern)
    project = rx.Project.create(tmp_path / "p.rex", pattern=path,
                                structure=structure, instrument=ins)
    project.fit(label="the project's own run")

    (run,) = runs.discover(project.live_dir)
    assert run.label == "the project's own run"
    # and the default it displaced is the project directory, not `live`
    assert run.label != runs.LIVE_DIR_NAME


def test_a_series_names_the_job_and_the_row_still_prefers_the_member(
        tmp_path, monkeypatch, pattern, recording):
    """One series is one run directory, so ``label`` is the chain's name.

    ``labels`` names the members and sits one letter away; the page's
    ``rowName`` prefers the member in a row, so the job's name is what the
    tooltip and the strip's label slot carry. Both facts are in the record at
    once, which is what this asserts.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    series = rx.SequentialRefinement(structure, ins, history=False)
    series.fit([pattern, pattern], x=[300.0, 400.0], x_label="T",
               labels=["300C", "400C"], label="the ramp of 2026-09-16")

    (run,) = runs.discover(tmp_path)
    assert run.label == "the ramp of 2026-09-16"
    assert run.status is not None
    assert run.status.series_label == "400C"


def test_a_label_that_is_not_a_string_is_refused_at_the_call(
        tmp_path, monkeypatch, pattern, recording):
    """The silent alternative costs the record, so this raises.

    ``_write_meta`` writes raw JSON, so a sequence would land in ``meta.json``
    as an array; ``RunMeta`` then refuses the whole file and ``read_run``
    reads a perfectly recorded run back as *legacy*, with a derived name and
    no tooltip. The hazard is one letter wide, ``labels`` being a real keyword
    on the series verb.
    """
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TypeError, match="label must be a string"):
        _fit(pattern, label=["300C", "400C"])
    assert runs.discover(tmp_path) == []


def test_the_label_is_checked_even_when_recording_is_off(tmp_path, monkeypatch,
                                                         pattern):
    """No ``recording`` fixture, deliberately.

    Checked before ``attach``'s switch-off guard, so a caller's suite — which
    runs with telemetry declined, as this one does — catches the mistake that
    would otherwise surface only where recording is on.
    """
    monkeypatch.chdir(tmp_path)
    with pytest.raises(TypeError, match="label must be a string"):
        _fit(pattern, label=Path("not-a-name"))


# ----------------------------------------------------------------------
# declining
# ----------------------------------------------------------------------
def test_telemetry_false_writes_nothing(tmp_path, monkeypatch, pattern,
                                        recording):
    monkeypatch.chdir(tmp_path)
    _fit(pattern, telemetry=False)
    assert list(tmp_path.rglob("*")) == []


def test_the_env_switch_writes_nothing_and_outranks_the_keyword(
        tmp_path, monkeypatch, pattern):
    """There is deliberately no ``telemetry=`` that argues back.

    Somebody who set the variable wants their disk left alone everywhere, so a
    library call that could override them would make the switch a suggestion.
    """
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv(TELEMETRY_ENV, "0")
    monkeypatch.setattr(runs, "_ENABLED", None)
    assert runs.enabled() is False
    _fit(pattern, telemetry=str(tmp_path / "named"))
    assert list(tmp_path.rglob("*")) == []


def test_the_suite_itself_records_nothing(tmp_path, monkeypatch, pattern):
    """The meta-test conftest's ``setdefault`` exists for.

    Without it the suite grows a run directory per fit — in whatever directory
    pytest was launched from — the first time somebody changes the default.
    This deliberately takes **no** ``recording`` fixture: it asserts the
    suite's own environment.
    """
    assert os.environ.get(TELEMETRY_ENV) == "0"
    monkeypatch.chdir(tmp_path)
    _fit(pattern)
    assert list(tmp_path.rglob("*")) == [], (
        "a fit under the suite's environment left files behind")


# ----------------------------------------------------------------------
# composition: the caller keeps everything they asked for
# ----------------------------------------------------------------------
def test_a_callers_path_still_gets_a_complete_log_and_the_recorder_its_own(
        tmp_path, monkeypatch, pattern, recording):
    """Two logs, both complete, neither one a truncation of the other."""
    monkeypatch.chdir(tmp_path)
    mine = tmp_path / "mine.jsonl"
    _fit(pattern, events=mine)

    (run,) = runs.discover(tmp_path)
    theirs = [e.kind for e in read_events(mine)]
    ours = [e.kind for e in read_events(run.path / runs.EVENTS_FILE)]
    assert theirs[0] == "fit_start" and theirs[-1] == "fit_end"
    assert ours == theirs, "the two logs recorded different runs"
    assert "eval" in ours


def test_a_callers_event_stream_keeps_its_identity(tmp_path, monkeypatch,
                                                   pattern, recording):
    """``fit`` closes its stream only ``if stream is not events``.

    That identity test is why ``sequential._SeriesStream`` is a subclass, and
    nothing here may disturb it: a caller who passed a stream still owns it,
    and still finds it open afterwards.
    """
    monkeypatch.chdir(tmp_path)
    seen = []
    stream = EventStream(callback=seen.append)
    _fit(pattern, events=stream)
    assert stream._fh is None          # never had a file; never closed by us
    assert [e["kind"] for e in seen][0] == "fit_start"
    assert [e["kind"] for e in seen][-1] == "fit_end"

    (run,) = runs.discover(tmp_path)
    ours = [e.kind for e in read_events(run.path / runs.EVENTS_FILE)]
    assert ours == [e["kind"] for e in seen]


def test_a_callers_callback_exception_still_propagates(tmp_path, monkeypatch,
                                                       pattern, recording):
    """``events.py``'s rule is untouched: a monitoring hook that crashes the
    refinement is a bug you want to see, not swallow.

    Direction one of two. The recorder is attached unasked and latches its own
    failures; a callback reached through ``events=`` is the caller's code and
    runs outside every try block in the recorder.
    """
    monkeypatch.chdir(tmp_path)

    class Boom(RuntimeError):
        pass

    def hostile(event):
        if event["kind"] == "stage_end":
            raise Boom("the caller's hook")

    with pytest.raises(Boom):
        _fit(pattern, events=hostile)


def test_a_latched_recorder_still_runs_the_callers_callback(
        tmp_path, monkeypatch, pattern, recording):
    """Direction two: the recorder giving up costs the caller nothing."""
    monkeypatch.chdir(tmp_path)
    seen = []
    stream = EventStream(callback=seen.append)
    recorder = runs.attach(stream, stream, telemetry=str(tmp_path / "t"))
    assert recorder is not None
    recorder._latch(OSError("disk went away"), "testing")
    assert recorder.error is not None

    stream.emit("fit_start", mode="rietveld")
    stream.emit("fit_end", status="converged")
    assert [e["kind"] for e in seen] == ["fit_start", "fit_end"]


@contextmanager
def _a_directory_this_user_cannot_write(tmp_path):
    """The measured provocation: a read-only working directory (WP-1403).

    POSIX only. ``chmod`` on Windows reaches the read-only *attribute* and
    nothing a directory's writability is decided by, so the ``mkdir`` below
    would simply succeed there and the fit would record happily.
    """
    blocked = tmp_path / "blocked"
    blocked.mkdir()
    blocked.chmod(0o500)
    try:
        yield str(blocked / "runs")
    finally:
        blocked.chmod(0o700)


@contextmanager
def _a_root_whose_parent_is_a_file(tmp_path):
    """The same boundary, provoked by a fact no permission model can vary.

    ``new_run_dir`` opens with ``root.mkdir(parents=True, exist_ok=True)``, and
    a path component that is a regular file defeats that on every platform.
    Still a real filesystem failure rather than a patched-in one, which is what
    keeps this test about ``attach`` and not about the mock.
    """
    occupied = tmp_path / "occupied"
    occupied.write_text("a file, where a directory would have to be\n",
                        encoding="utf-8")
    yield str(occupied / "runs")


@pytest.mark.parametrize("provoke", [
    pytest.param(_a_directory_this_user_cannot_write, id="unwritable-directory",
                 marks=[
                     pytest.mark.skipif(
                         os.name == "nt",
                         reason="chmod does not make a directory unwritable here"),
                     pytest.mark.skipif(
                         hasattr(os, "geteuid") and os.geteuid() == 0,
                         reason="root is not refused by a directory's mode; "
                                "parent-is-a-file covers this boundary for every user"),
                 ]),
    pytest.param(_a_root_whose_parent_is_a_file, id="parent-is-a-file"),
])
def test_a_root_it_cannot_create_declines_and_the_fit_still_returns(
        tmp_path, monkeypatch, pattern, recording, provoke):
    """The whole point. A fit that dies over a directory nobody requested is
    the package breaking a working call for its own convenience.

    This is the failure *before* a recorder exists — choosing the root and
    making the directory happen in ``attach``, where no latch can reach them.
    The first version of this test found exactly that hole: the
    ``PermissionError`` propagated and took the fit with it.

    Two provocations, because the measured one is not portable and the
    portable one is not what was measured (WP-1439). Both land in the same
    ``except BaseException`` in ``attach``, which is the thing under test.
    """
    monkeypatch.chdir(tmp_path)
    with provoke(tmp_path) as telemetry:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            result = _fit(pattern, telemetry=telemetry)

    assert result.status == "converged"
    assert result.statistics.rwp < 0.2
    messages = [str(w.message) for w in caught
                if str(w.message).startswith("telemetry ")]
    assert len(messages) == 1, messages          # one a process, not one a run
    assert TELEMETRY_ENV in messages[0]          # and it says how to stop it


def test_a_recorder_that_breaks_mid_run_latches_and_says_why(
        tmp_path, monkeypatch, pattern, recording):
    """The failure *after* the directory exists: the latch proper.

    Its reason reaches ``status.json``, because a latch that went quiet would
    be WP-1076's field whose empty state reads as an answer — a run that
    stopped recording would look like one that recorded everything.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)

    stream = EventStream()
    recorder = runs.attach(stream, stream, telemetry=str(tmp_path / "t"))
    assert recorder is not None
    recorder._fh = None                      # what a vanished mount looks like
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        result = ref.fit(pattern, events=stream)
        recorder.close()

    assert result.status == "converged"
    assert recorder.error is not None
    status = json.loads((recorder.dir / runs.STATUS_FILE).read_text(encoding="utf-8"))
    assert status["error"] == recorder.error
    assert status["state"] == "running"      # it never got to say otherwise


# ----------------------------------------------------------------------
# attach exactly once
# ----------------------------------------------------------------------
def test_a_series_records_one_run_and_not_one_per_pattern(
        tmp_path, monkeypatch, pattern, recording):
    """A 60-pattern series would otherwise make 60 directories for one job.

    Each pattern's fit is handed a **fresh** ``_SeriesStream`` wrapping the one
    stream the series owns, so the stamp has to be looked for through the
    ``_inner`` chain rather than on the object handed in.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    series = rx.SequentialRefinement(structure, ins, history=False)
    series.fit([pattern, pattern, pattern], x=[300.0, 400.0, 500.0], x_label="T")

    found = runs.discover(tmp_path)
    assert len(found) == 1, [str(r.path) for r in found]
    starts = [e for e in read_events(found[0].path / runs.EVENTS_FILE)
              if e.kind == "fit_start"]
    assert len(starts) == 3
    assert [e.data["series_index"] for e in starts] == [0, 1, 2]


def test_the_status_says_which_pattern_a_series_is_on(
        tmp_path, monkeypatch, pattern, recording):
    """Read off the stamp on ``stage_start``, never counted (WP-1423).

    A run page for a sixty-pattern ramp otherwise says "stage biso" and
    nothing else, with the pattern's name in the console tail only.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    series = rx.SequentialRefinement(structure, ins, history=False)
    series.fit([pattern, pattern, pattern], x=[300.0, 400.0, 500.0], x_label="T")

    (run,) = runs.discover(tmp_path)
    status = run.status
    assert (status.series_index, status.series_n) == (2, 3)
    assert status.series_pass == "forward"
    starts = [e for e in read_events(run.path / runs.EVENTS_FILE)
              if e.kind == "stage_start"]
    assert status.series_label == starts[-1].data["series_label"]
    # and a single fit claims nothing about a chain it is not in
    rx.Refinement(*perturbed_models()).fit(pattern)
    single = [r for r in runs.discover(tmp_path) if r.run_id != run.run_id]
    assert len(single) == 1
    assert single[0].status.series_index is None


class _Wrapper(EventStream):
    """A stream wrapping another, the shape ``_SeriesStream`` has."""

    def __init__(self, inner):
        super().__init__()
        self._inner = inner


def test_the_stamp_is_found_through_any_depth_of_wrapper():
    """The walk, on its own, without a fit to produce a stamp."""
    outer = EventStream()
    assert runs._already_recorded(outer) is False
    assert runs._already_recorded(_Wrapper(outer)) is False

    setattr(outer, runs._STAMP, object())
    assert runs._already_recorded(outer) is True
    assert runs._already_recorded(_Wrapper(outer)) is True
    assert runs._already_recorded(_Wrapper(_Wrapper(outer))) is True

    assert runs._already_recorded(EventStream()) is False
    assert runs._already_recorded(None) is False


def test_attach_stamps_the_stream_and_then_declines_it(tmp_path, recording):
    """Two calls, one directory. The second finds the first's stamp."""
    stream = EventStream()
    first = runs.attach(stream, stream, telemetry=str(tmp_path / "runs"))
    assert first is not None
    assert runs._already_recorded(stream) is True

    assert runs.attach(stream, stream, telemetry=str(tmp_path / "runs")) is None
    assert runs.attach(_Wrapper(stream), stream,
                       telemetry=str(tmp_path / "runs")) is None
    first.close()
    assert len(list((tmp_path / "runs").iterdir())) == 1


def test_the_chain_walk_survives_a_cycle():
    """Telemetry must never hang a fit, and a cycle here would."""
    a, b = EventStream(), EventStream()
    a._inner, b._inner = b, a
    assert runs._already_recorded(a) is False


# ----------------------------------------------------------------------
# what the review pass found, one guard each
# ----------------------------------------------------------------------
def test_a_series_stays_running_until_the_whole_chain_is_done(
        tmp_path, monkeypatch, pattern, recording):
    """One job is one run, so one `fit_end` is not the end of it.

    A series emits a `fit_end` per pattern into the one recorder it attached,
    and reading a terminal state off the first of them told every reader the
    run had finished after pattern 1. `liveness_of`'s first rule is that a
    terminal state wins, so a live ramp showed as done, and `close` could not
    correct it afterwards — it applies a state only when nothing has claimed
    one.
    """
    monkeypatch.chdir(tmp_path)
    seen = []

    def watch(event):
        if event["kind"] == "fit_end":
            found = runs.discover(tmp_path)
            seen.append(found[0].status.state if found and found[0].status
                        else None)

    structure, ins = perturbed_models()
    rx.SequentialRefinement(structure, ins, history=False).fit(
        [pattern, pattern, pattern], x=[300.0, 400.0, 500.0], x_label="T",
        events=watch)

    assert len(seen) == 3
    assert seen[:2] == ["running", "running"], seen
    (run,) = runs.discover(tmp_path)
    assert run.status.state == "done"


def test_a_trial_the_package_runs_is_not_a_run(tmp_path, monkeypatch, pattern,
                                               recording):
    """A verify trial runs a stage whose result is thrown away, and a recorder
    on it wrote a run directory per candidate action.

    The line that decides it: a trial whose **result is discarded** records
    nothing, and a fit whose result a caller **reads** records. So the five
    internal sites pass ``telemetry=False`` while ``viz/compare.py`` — whose
    answer is the thing a user reads — does not.

    It drives ``predict_then_verify`` directly rather than through
    ``ref.report()``, which was the first shape of this test and was **blind**:
    the report does not itself run a trial, so reverting the fix left the test
    green. Found by breaking the fix on purpose (``tests/CLAUDE.md`` § Guards
    that go quiet).
    """
    from rietx.report import predict_then_verify
    from rietx.report.schemas import SuggestedAction

    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    ref.fit(pattern)
    assert len(runs.discover(tmp_path)) == 1

    action = SuggestedAction(
        kind="refine_zero_shift", confidence=0.9,
        rationale="a trial, for the telemetry guard",
        parameter_paths=["instrument.zero_shift"])
    predict_then_verify(ref, pattern, action)

    found = runs.discover(tmp_path)
    assert len(found) == 1, [str(r.path) for r in found]


def test_a_run_stage_that_raises_records_failed(tmp_path, monkeypatch, pattern,
                                                recording):
    """`run_stage`'s inner `finally` closed the recorder before the result
    existed, so a stage that raised on the way out recorded itself done."""
    monkeypatch.chdir(tmp_path)
    refine_mod = sys.modules["rietx.refine"]

    class Boom(RuntimeError):
        pass

    def exploding(*a, **kw):
        raise Boom("after the solve")

    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    real = refine_mod._build_result
    refine_mod._build_result = exploding
    try:
        with pytest.raises(Boom):
            ref.run_stage(pattern, rx.Stage(name="bg",
                                            turn_on=["instrument.background.*"]))
    finally:
        refine_mod._build_result = real

    (run,) = runs.discover(tmp_path)
    assert run.status.state == "failed"


def test_two_fits_on_one_stream_get_two_clean_runs(tmp_path, monkeypatch,
                                                   pattern, recording):
    """`attach` mutated the caller's stream and nothing undid it.

    The second fit then recorded nothing, and its events reached the *closed*
    first recorder, which latched an error into a finished run's status and
    warned about telemetry that never failed.
    """
    monkeypatch.chdir(tmp_path)
    seen = []
    stream = EventStream(callback=seen.append)
    for _ in range(2):
        structure, ins = perturbed_models()
        rx.Refinement(structure, ins, history=False).fit(pattern, events=stream)

    found = runs.discover(tmp_path)
    assert len(found) == 2, [str(r.path) for r in found]
    assert [r.status.state for r in found] == ["done", "done"]
    assert [r.status.error for r in found] == [None, None]
    assert len([e for e in seen if e["kind"] == "fit_end"]) == 2
    assert runs.recorder_of(stream) is None      # put back as it was found


def test_a_series_with_a_callers_events_still_gets_a_picture(
        tmp_path, monkeypatch, pattern, recording):
    """`_SeriesStream` looked for `write_snapshot` on its inner stream only.

    A caller who passes `events=` leaves the recorder *chained* onto that
    stream rather than being it, so a plain `EventStream` inner answered no and
    the run recorded no picture. Every GUI series was in that case.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    rx.SequentialRefinement(structure, ins, history=False).fit(
        [pattern, pattern], x=[300.0, 400.0], x_label="T",
        events=str(tmp_path / "mine.jsonl"))
    (run,) = runs.discover(tmp_path)
    assert run.has_snapshot is True


def test_collect_runs_honours_the_cap_it_is_handed(tmp_path):
    """`_collect_runs` appended its holder without checking the count.

    Asserted on the helper and **not** through `discover`, because `discover`
    cannot reach it: its entry loop breaks on the cap immediately after every
    call, so the helper is never entered with the list already full. Measured
    by reverting the check and sweeping `max_runs` 1-11 over a tree of loose
    runs, a project whose `live/` is itself a run, and a state dir the same
    shape — no overflow at any cap. So this is a local invariant of the helper
    rather than a defect that was reachable, and a test routed through
    `discover` would be one that cannot fail (`tests/CLAUDE.md` § Guards that
    go quiet).
    """
    holder = tmp_path / "holder"
    _stub_run(tmp_path, "holder", created=NOW)
    _stub_run(holder, "20260101-120000-1", created=NOW)

    full: list = ["already", "at", "the", "cap"]
    runs._collect_runs(holder, tmp_path, full, max_runs=len(full))
    assert len(full) == 4, "the holder was appended past the cap"

    room: list = []
    runs._collect_runs(holder, tmp_path, room, max_runs=10)
    assert len(room) == 2      # the holder and its one child


# ----------------------------------------------------------------------
# stopping a run from outside the process (WP-1405)
# ----------------------------------------------------------------------
def _fit_and_ask(tmp_path, pattern, *, cancel=None, at=4, body=None,
                 plan=None):
    """Run a recorded fit that asks itself to stop, part way through.

    The request is written from inside an ``events=`` callback rather than from
    another thread, so the test is deterministic: the file exists from a known
    evaluation onwards, and how long the fit then takes to notice is the thing
    under test.
    """
    structure, ins = perturbed_models()
    ref = rx.Refinement(structure, ins, history=False)
    seen = {"n": 0, "asked": False, "at": None}

    def ask(event):
        if event["kind"] != "eval":
            return
        seen["n"] += 1
        if seen["n"] < at or seen["asked"]:
            return
        seen["asked"] = True
        seen["at"] = seen["n"]
        (run,) = runs.discover(tmp_path)
        if body is None:
            runs.request_cancel(run.path, who="a test")
        else:
            (run.path / runs.CANCEL_FILE).write_text(json.dumps(body),
                                                     encoding="utf-8")

    raised = None
    try:
        ref.fit(pattern, plan=plan or "profile_only", events=ask, cancel=cancel)
    except RefinementCancelled as exc:
        raised = exc
    (run,) = runs.discover(tmp_path)
    status = json.loads((run.path / runs.STATUS_FILE).read_text(encoding="utf-8"))
    return raised, status, run, seen


def test_a_recorded_fit_with_no_caller_token_stops(tmp_path, monkeypatch,
                                                   pattern, recording):
    """WP-1405's acceptance: a fit nobody made cancellable is cancellable.

    The caller passed no ``cancel=``, so before this the only ``CancelToken``
    in the package was the GUI's own. The exception that comes out is the one
    the caller would have got had they asked for it, which is the point: a
    human's stop and an agent's own ``token.cancel()`` are indistinguishable
    downstream.
    """
    monkeypatch.chdir(tmp_path)
    exc, status, run, _ = _fit_and_ask(tmp_path, pattern)

    assert exc is not None, "the request did not reach the fit"
    assert status["state"] == "cancelled"
    assert status["cancelled_by"] == "a test"
    assert runs.liveness_of(run).state == "cancelled"
    # consumed, not left lying: a request read twice is a request that stops
    # the next fit into this directory as well
    assert not (run.path / runs.CANCEL_FILE).exists()
    # ...and no summary, because there is no result to write one from
    assert not (run.path / runs.SUMMARY_FILE).exists()


def test_the_request_sets_the_callers_own_token_and_not_a_second_one(
        tmp_path, monkeypatch, pattern, recording):
    """One authority per run for "stop".

    A GUI session holds its token and reads it back; a second flag set
    somewhere else would leave the two disagreeing about a fit they both
    stopped.
    """
    monkeypatch.chdir(tmp_path)
    token = CancelToken()
    exc, status, _, _ = _fit_and_ask(tmp_path, pattern, cancel=token)

    assert exc is not None
    assert token.is_set() and bool(token)
    assert status["cancelled_by"] == "a test"


def test_a_request_this_version_does_not_know_is_declined_by_name(
        tmp_path, monkeypatch, pattern, recording):
    """An old recorder meeting a newer watcher's word must not stop the fit.

    The vocabulary in the request file is open forwards. Rounding an unknown
    word to the file's *name* would make every future verb a cancel on every
    older install, which is the one way this seam could become dangerous.
    """
    monkeypatch.chdir(tmp_path)
    exc, status, run, _ = _fit_and_ask(
        tmp_path, pattern, body={"request": "pause", "who": "a newer watcher"})

    assert exc is None, "an unknown request stopped the fit"
    assert status["state"] == "done"
    assert status["declined"] == "pause"
    assert status.get("cancelled_by") is None
    # consumed even so, or it is re-read and re-declined every cadence
    assert not (run.path / runs.CANCEL_FILE).exists()


def test_a_request_with_no_body_is_still_a_cancel(tmp_path, monkeypatch,
                                                  pattern, recording):
    """``touch cancel`` is the obvious gesture, and the file's name is the verb."""
    monkeypatch.chdir(tmp_path)
    exc, status, _, _ = _fit_and_ask(tmp_path, pattern, body={})

    assert exc is not None
    assert status["state"] == "cancelled"
    assert status["cancelled_by"] == "unknown"


def test_the_probe_needs_no_event_at_all(tmp_path):
    """The probe hangs on the token, not on the stream — and this is why.

    WP-1403's thinning and WP-1404's stage-boundary configuration both take the
    ``eval`` stream away. A probe that rode the events would then fire once a
    **stage**, which on the long runs this button exists for is minutes. Here
    no event is recorded at all and the token still comes back set, within one
    cadence of the request being written.
    """
    recorder = runs.RunRecorder(tmp_path / "run", flush_interval=0.01)
    token = recorder.cancel_token()
    assert not token.is_set()

    runs.request_cancel(recorder.dir, who="a test")
    time.sleep(0.02)                       # one cadence, so the probe fires
    assert token.is_set()
    assert recorder.n_written == 0, "no event was needed"
    recorder.close()


def test_the_probe_is_rate_limited_to_the_cadence(tmp_path):
    """A stat per residual evaluation is the syscall problem the flush avoids."""
    recorder = runs.RunRecorder(tmp_path / "run", flush_interval=30.0)
    token = recorder.cancel_token()
    assert not token.is_set()              # the first read probes

    runs.request_cancel(recorder.dir, who="a test")
    for _ in range(50):
        assert not token.is_set(), "the probe ran again inside one cadence"
    assert (recorder.dir / runs.CANCEL_FILE).exists()
    recorder.close()


def test_a_stale_request_does_not_stop_the_next_fit(tmp_path):
    """Impossible in the run-id layout, reachable the moment anything reuses a
    directory — and there it would cancel instantly, blaming a watcher that had
    gone home."""
    directory = tmp_path / "run"
    directory.mkdir()
    runs.request_cancel(directory, who="a watcher that has gone home")

    recorder = runs.RunRecorder(directory, flush_interval=0.0)
    assert not (directory / runs.CANCEL_FILE).exists()
    assert not recorder.cancel_token().is_set()
    recorder.close()


def test_a_series_is_stopped_at_the_chain_and_not_one_pattern(
        tmp_path, monkeypatch, pattern, recording):
    """A series attaches one recorder for the whole job.

    So the token has to be composed at the chain as well as inside each
    pattern's ``fit``: ``_run`` reads ``bool(cancel)`` to decide the walk
    ended, and a stop that reached one pattern and not that variable would
    abandon that pattern and start the next one.
    """
    monkeypatch.chdir(tmp_path)
    structure, ins = perturbed_models()
    series = rx.SequentialRefinement(structure, ins, history=False)
    asked = {"done": False}

    def ask(event):
        if event["kind"] == "eval" and not asked["done"]:
            asked["done"] = True
            (run,) = runs.discover(tmp_path)
            runs.request_cancel(run.path, who="a test")

    result = series.fit([pattern] * 4, x=[300.0, 400.0, 500.0, 600.0],
                        x_label="T", plan="profile_only", events=ask)

    assert len(result.entries) < 4, "the chain ran on past the stop"
    assert any(d.code == "SEQUENTIAL_CANCELLED" for d in result.diagnostics)


def test_recording_does_not_move_the_answer(tmp_path, monkeypatch, pattern,
                                            recording):
    """Attaching a token to every recorded fit must not change one.

    ``test_an_unset_token_costs_nothing_semantically`` makes this claim for a
    token the *caller* passed. WP-1405 attaches one to every recorded fit, so
    the claim now has to hold for a fit that asked for neither.
    """
    monkeypatch.chdir(tmp_path)
    recorded = _fit(pattern, plan="profile_only")
    plain = _fit(pattern, plan="profile_only", telemetry=False)

    assert recorded.statistics.rwp == plain.statistics.rwp
    assert [p.value for p in recorded.parameters] == [p.value
                                                      for p in plain.parameters]


# ----------------------------------------------------------------------
# what recording costs, counted (WP-1404)
# ----------------------------------------------------------------------
#
# WP-1404 prices the default-on recorder, and its wall-clock numbers live in
# prose: a budget in a test is a runaway guard, never a timer.  What belongs
# here is the half that is machine-independent — the counts.  A ratio is only
# a ratio of one fit if the fit did the same work in both arms, so these are
# what licenses every number that WP's handover quotes.
_FORWARDS = ("evaluate", "bragg_component", "background")


@pytest.fixture
def forwards(monkeypatch):
    """Count calls into the compiled forward, by name.

    The three names are not interchangeable, and that is the point.
    ``evaluate`` is a whole y_calc, ``bragg_component`` the peak sum inside it,
    ``background`` the background pass — so a telemetry path that adds one
    ``evaluate`` a stage is doing something different from one that adds two
    ``background``s, and only a per-name count can say which.  WP-1404 was
    drafted expecting "one extra forward evaluation" a stage; the truth is
    three different numbers, and the one it guessed is the smallest.
    """
    counts: dict[str, int] = dict.fromkeys(_FORWARDS, 0)
    for name in _FORWARDS:
        original = getattr(CompiledModel, name)

        def wrapper(self, *a, _name=name, _orig=original, **kw):
            counts[_name] += 1
            return _orig(self, *a, **kw)

        monkeypatch.setattr(CompiledModel, name, wrapper)
    return counts


def test_recording_adds_no_residual_evaluation(tmp_path, monkeypatch, pattern,
                                               recording):
    """The solve is untouched: the same stages, the same nfev in each.

    ``test_recording_does_not_move_the_answer`` makes the *value* half of this
    claim, and this is the cost half.  It is the half that would go wrong
    silently: a fit reaching the same answer through a different number of
    evaluations would make every ratio WP-1404 measures a ratio between two
    different fits, and the answer would still look right.
    """
    monkeypatch.chdir(tmp_path)
    plain = _fit(pattern, plan="profile_only", telemetry=False)
    recorded = _fit(pattern, plan="profile_only")

    assert [s.n_iterations for s in recorded.stages] == [
        s.n_iterations for s in plain.stages]
    assert sum(s.n_iterations for s in recorded.stages) > 0
    assert [s.name for s in recorded.stages] == [s.name for s in plain.stages]


def test_what_a_recorded_stage_costs_in_forward_evaluations(
        tmp_path, monkeypatch, pattern, forwards, recording):
    """Per stage and per name, with the caller's own stream in between.

    The middle arm is what makes this a decomposition rather than a total: a
    caller who passes ``events=`` once paid the real ``stage_end.rwp`` on top
    of an unrecorded fit, and since ``StageResult.rwp`` (WP-1334) every fit
    pays it, so the caller's stream now costs nothing in forwards.  What the
    recorder adds is its per-stage picture, which is the same forward
    work a ``LiveSession`` has always done — measured identical, 2026-09-15.
    The news in WP-1403 is therefore not that a picture costs a forward, but
    that it is now taken unasked.
    """
    monkeypatch.chdir(tmp_path)

    def take(**kw):
        for name in _FORWARDS:
            forwards[name] = 0
        result = _fit(pattern, plan="profile_only", **kw)
        return dict(forwards), len(result.stages)

    plain, n = take(telemetry=False)
    caller, n_caller = take(telemetry=False, events=tmp_path / "caller.jsonl")
    recorded, n_recorded = take()
    assert n == n_caller == n_recorded > 1

    # the stage Rwp, one background pass and one Bragg sum a stage, is paid
    # whether or not anyone listens, because ``StageResult.rwp`` carries it
    # (WP-1334): a caller's own stream adds no forward work at all
    assert caller == plain

    # the recorder adds its snapshot on top: one whole ``evaluate`` a stage,
    # which is a second Bragg sum and a second background, plus the background
    # curve the snapshot carries in its own right
    assert recorded["evaluate"] - plain["evaluate"] == n
    assert recorded["bragg_component"] - plain["bragg_component"] == n
    assert recorded["background"] - plain["background"] == 2 * n


def test_the_flush_count_is_bounded_by_the_events_and_the_cadence(
        tmp_path, monkeypatch, pattern, recording):
    """``eval`` lines are buffered, so flushes are the other events plus a rate.

    Structural, not a budget.  Every non-``eval`` event flushes as it is
    written, and the buffered ones can flush at most once per
    ``FLUSH_INTERVAL_SECONDS`` of the run's own duration, so a slower machine
    allows *more* flushes and this can only fail by the cadence breaking.  That
    is what separates it from a timer: there is no box on which a correct
    implementation fails it.

    The handle is wrapped rather than the method, because the flush happens
    inside ``_write`` and is not visible from outside it.
    ``examples/bench_refinement.py`` wraps the same handle for a different
    purpose — it wants the number, this wants the bound — and neither is the
    other's authority.
    """
    monkeypatch.chdir(tmp_path)
    flushes = {"n": 0}

    class _Handle:
        def __init__(self, fh):
            self._fh = fh

        def flush(self):
            flushes["n"] += 1
            self._fh.flush()

        def __getattr__(self, name):
            return getattr(self._fh, name)

    class _Counted(runs.RunRecorder):
        def __init__(self, *a, **kw):
            super().__init__(*a, **kw)
            if getattr(self, "_fh", None) is not None:
                self._fh = _Handle(self._fh)

    monkeypatch.setattr(runs, "RunRecorder", _Counted)
    started = time.perf_counter()
    _fit(pattern, plan="profile_only")
    duration = time.perf_counter() - started

    (found,) = runs.discover(tmp_path)
    events = read_events(found.path / runs.EVENTS_FILE)
    non_eval = [e for e in events if e.kind != "eval"]
    assert any(e.kind == "eval" for e in events), "nothing was buffered"

    # every non-``eval`` event flushes, and ``close`` flushes once more
    assert flushes["n"] >= len(non_eval)
    cadence = duration / runs.FLUSH_INTERVAL_SECONDS
    assert flushes["n"] <= len(non_eval) + cadence + 2, (
        f"{flushes['n']} flushes for {len(non_eval)} non-eval events over "
        f"{duration:.2f} s — the eval lines are not being buffered")


# ----------------------------------------------------------------------
# retention
# ----------------------------------------------------------------------
def _stub_run(root: Path, name: str, *, created: float, state="done",
              meta=True, size=1000) -> Path:
    d = root / name
    d.mkdir(parents=True)
    (d / runs.EVENTS_FILE).write_text("x" * size, encoding="utf-8")
    if meta:
        (d / runs.META_FILE).write_text(
            json.dumps({"record": runs.RECORD_TAG, "created": created}),
            encoding="utf-8")
    if state is not None:
        (d / runs.STATUS_FILE).write_text(json.dumps({"state": state}),
                                          encoding="utf-8")
    return d


NOW = 1_800_000_000.0
DAY = 86400.0


def test_retention_takes_the_oldest_terminal_runs_until_it_is_under(tmp_path):
    root = tmp_path / "runs"
    made = [_stub_run(root, f"2026010{i + 1}-120000-{i}",
                      created=NOW - 30 * DAY + i) for i in range(5)]
    removed = runs.prune(root, max_bytes=3500, now=NOW)
    assert [p.name for p in removed] == [made[0].name, made[1].name]
    assert sorted(p.name for p in root.iterdir()) == [m.name for m in made[2:]]


def test_a_batch_still_running_loses_nothing(tmp_path):
    """The design this rule exists for.

    "Keep the newest N" would delete run 1 of a 200-candidate batch while the
    batch was still running, and a batch is one of the cases recording exists
    for.
    """
    root = tmp_path / "runs"
    for i in range(200):
        _stub_run(root, f"20260101-1200{i:02d}-{i}", created=NOW - 60,
                  size=10_000)
    assert runs.prune(root, max_bytes=1000, now=NOW) == []
    assert len(list(root.iterdir())) == 200


def test_a_root_over_the_ceiling_with_nothing_old_enough_warns_and_keeps(
        tmp_path):
    root = tmp_path / "runs"
    for i in range(3):
        _stub_run(root, f"2026010{i + 1}-120000-{i}", created=NOW - 60)
    runs._WARNED = False
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        assert runs.prune(root, max_bytes=1, now=NOW) == []
    assert len(list(root.iterdir())) == 3
    assert len(caught) == 1 and "Keeping it" in str(caught[0].message)


@pytest.mark.parametrize("why,kw,name", [
    ("legacy: no meta.json", {"meta": False}, "20260101-120000-1"),
    ("still running", {"state": "running"}, "20260102-120000-2"),
    ("no state recorded", {"state": None}, "20260103-120000-3"),
    ("not a run-id name", {}, "important-data"),
])
def test_what_is_never_pruned(tmp_path, why, kw, name):
    """Each of these survives a ceiling of one byte and a month of age."""
    root = tmp_path / "runs"
    spared = _stub_run(root, name, created=NOW - 30 * DAY, **kw)
    doomed = _stub_run(root, "20251201-120000-9", created=NOW - 60 * DAY)
    runs._WARNED = False
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        removed = runs.prune(root, max_bytes=1, now=NOW)
    assert spared.exists(), why
    assert not doomed.exists(), "the prune did not run at all"
    assert [p.name for p in removed] == [doomed.name]


def test_a_meta_without_the_record_tag_is_never_pruned(tmp_path):
    """The interlock the tag is declared for."""
    root = tmp_path / "runs"
    spared = _stub_run(root, "20260101-120000-1", created=NOW - 30 * DAY)
    (spared / runs.META_FILE).write_text(json.dumps({"created": NOW - 30 * DAY}),
                                         encoding="utf-8")
    runs._WARNED = False
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        runs.prune(root, max_bytes=1, now=NOW)
    assert spared.exists()


def test_a_run_one_level_deeper_is_out_of_reach(tmp_path):
    """The direct-child guard, which is what bounds the blast radius."""
    root = tmp_path / "runs"
    nested = _stub_run(root / "sub", "20260101-120000-1", created=NOW - 30 * DAY)
    runs._WARNED = False
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        runs.prune(root, max_bytes=1, now=NOW)
    assert nested.exists()
