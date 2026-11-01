"""WP-1322 — the event log says where one run ends, and ``rietx events`` reads it.

Two halves of one defect (#223, #207).  ``EventStream`` appends, and must keep
appending: a series forwards every pattern's events through one stream, and
``rietx watch`` tails the file.  But with no run marker a re-run into the same
path merged two runs into one log, and every duration derived from it was a
mixture — measured on a timing study as a 10.3 s fit reported as 459.0 s.  So
each opened stream now writes one ``record: "run"`` header line, and the
aggregator partitions on it.

Every log here comes from the package's own emitters, never hand-written JSONL
(the WP's rule): a header-less "old" log is made by the same writer with its
header switched off, so it is byte for byte what a pre-1322 build wrote.
"""

from __future__ import annotations

import json
import time
from collections import Counter

import pytest

import rietx as rx
from rietx import runs
from rietx.history.aggregate import EventsSummary, summarize_events
from rietx.history.events import RUN_RECORD, EventStream, read_events
from tests.test_absent_phase import _absent_phase_inputs
from tests.test_refine_synthetic import perturbed_models, synthesize

PLAN = rx.RefinementPlan(stages=[
    rx.Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"],
             max_iter=30),
    rx.Stage("cell", ["phases.*.cell.*"], max_iter=30),
])


@pytest.fixture(scope="module")
def pattern():
    return synthesize()


def _fit(pattern, events, *, structure_and_instrument=None):
    structure, ins = structure_and_instrument or perturbed_models()
    return rx.Refinement(structure, ins, history=False).fit(
        pattern, plan=PLAN, events=events)


def _lines(path):
    return [json.loads(line) for line in
            path.read_text(encoding="utf-8").splitlines() if line.strip()]


# ---------------------------------------------------------------- the header
def test_an_opened_stream_writes_one_header_and_never_emits_it(tmp_path, pattern):
    """The header is the file's, not the stream's: no callback ever sees it.

    That is what keeps every in-process consumer — ``progress=``, the run
    recorder, a series' stamp, the GUI — exactly as it was: they receive
    events through ``emit`` and the header never passes through it.
    """
    path = tmp_path / "events.jsonl"
    seen: list[dict] = []
    stream = EventStream(path=path, callback=seen.append)
    _fit(pattern, stream)
    stream.close()

    lines = _lines(path)
    assert lines[0]["record"] == RUN_RECORD
    assert lines[0]["run"] == stream.header_id
    assert [r for r in lines if r["record"] == RUN_RECORD] == lines[:1]
    assert all(r["record"] == "event" for r in lines[1:])
    # the callback saw exactly the events, and the header is not one of them
    assert [e["kind"] for e in seen] == [r["kind"] for r in lines[1:]]
    # read_events keeps its contract: events, validated, and nothing else
    assert [e.kind for e in read_events(path)] == [e["kind"] for e in seen]


def test_a_rerun_into_one_path_is_two_runs_with_their_own_durations(
        tmp_path, pattern):
    """The #223 case: the second run's clock no longer starts in the first's.

    A pause between the runs makes a merged reading measurably wrong: the
    whole file spans both fits and the pause, and each run's own wall clock
    must not.  Each run's wall is held to the caller's own clock around its
    fit, the independent check that caught the original 44.67x.
    """
    path = tmp_path / "events.jsonl"
    walls = []
    for _ in range(2):
        t0 = time.time()
        with EventStream(path=path) as stream:
            _fit(pattern, stream)
        walls.append(time.time() - t0)
        time.sleep(0.5)

    summary = summarize_events(path)
    assert summary.n_runs == 2
    assert all(run.header is not None for run in summary.runs)
    assert len({run.header.run for run in summary.runs}) == 2
    file_span = summary.runs[1].t_last - summary.runs[0].t_first
    for run, wall in zip(summary.runs, walls):
        assert run.n_fits == 1 and run.n_fits_ended == 1
        assert 0.0 < run.wall_seconds <= wall
        assert run.fit_seconds <= run.wall_seconds
    # the merged reading the header exists to prevent
    assert file_span > sum(walls) + 0.5 - 0.05
    assert all(run.wall_seconds < file_span - 0.5 for run in summary.runs)


def test_a_headerless_log_reads_as_one_run_and_says_so(tmp_path, pattern,
                                                       monkeypatch):
    """A log written before WP-1322 still reads, as one run, flagged.

    The writer with its header switched off is the pre-1322 writer, so this
    log is what every existing ``events.jsonl`` on disk looks like.
    """
    monkeypatch.setattr(EventStream, "_write_header", lambda self: None)
    path = tmp_path / "events.jsonl"
    for _ in range(2):
        with EventStream(path=path) as stream:
            _fit(pattern, stream)
    assert all(r["record"] == "event" for r in _lines(path))

    summary = summarize_events(path)
    assert summary.n_runs == 1
    (run,) = summary.runs
    assert run.header is None
    # two fits in one header-less run: counted, and the text says why it
    # cannot split them
    assert run.n_fits == 2
    text = str(summary)
    assert "header: none" in text
    assert len(read_events(path)) == len(_lines(path))


# ---------------------------------------------------------------- the numbers
def test_the_aggregate_reconciles_with_the_emitting_runs_own_records(
        tmp_path, pattern):
    """Counts, terminations, held paths, Rwp and stage clocks, each exact.

    The absent-phase fixture makes the cell stage hold the invisible phase's
    structural paths (WP-1301), so the held-path histogram has something real
    to count.  Every expectation is computed from the events the callback
    received — the same dicts the file holds — never from the aggregator's own
    code path.
    """
    path = tmp_path / "events.jsonl"
    seen: list[dict] = []
    with EventStream(path=path, callback=seen.append) as stream:
        _fit(pattern, stream, structure_and_instrument=_absent_phase_inputs())

    (run,) = summarize_events(path).runs
    ends = [e for e in seen if e["kind"] == "stage_end"]
    starts = [e for e in seen if e["kind"] == "stage_start"]

    assert run.n_events == len(seen)
    assert run.n_fits == 1 and run.n_fits_ended == 1
    assert run.n_stage_ends == len(ends)
    assert run.n_stage_starts == len(starts)
    assert run.n_evals == sum(e["kind"] == "eval" for e in seen)
    assert run.terminations == dict(Counter(
        e["data"].get("termination") or "(absent)" for e in ends))
    held = Counter(p for e in ends for p in e["data"].get("held", []))
    assert held, "the fixture must hold something, or this counts nothing"
    assert run.held == dict(held.most_common())

    rwps = [e["data"]["rwp"] for e in seen
            if e["kind"] in ("stage_end", "fit_end") and "rwp" in e["data"]]
    assert run.first_rwp == rwps[0] and run.last_rwp == rwps[-1]

    # per stage: the first stage_start of a name to its stage_end, so a
    # released phase's second start is inside the same span (progress_writer's
    # rule), and the sum over names covers every stage_end
    by_name = {s.stage: s for s in run.stages}
    assert set(by_name) == {e["data"]["stage"] for e in ends}
    for name, timing in by_name.items():
        first = min(e["t"] for e in starts if e["data"]["stage"] == name)
        end = max(e["t"] for e in ends if e["data"]["stage"] == name)
        assert timing.count == sum(e["data"]["stage"] == name for e in ends)
        assert timing.seconds == pytest.approx(end - first, abs=1e-9)
    fit_start = next(e["t"] for e in seen if e["kind"] == "fit_start")
    fit_end = next(e["t"] for e in seen if e["kind"] == "fit_end")
    assert run.fit_seconds == pytest.approx(fit_end - fit_start, abs=1e-9)


def test_a_series_through_one_stream_is_one_run(tmp_path, pattern):
    """Append stays load-bearing: a series' patterns share one stream, one run."""
    path = tmp_path / "events.jsonl"
    structure, ins = perturbed_models()
    with EventStream(path=path) as stream:
        rx.SequentialRefinement(structure, ins).fit(
            [pattern, pattern], plan=PLAN, events=stream)

    summary = summarize_events(path)
    assert summary.n_runs == 1
    assert summary.runs[0].n_fits == 2


def test_a_corrupt_line_is_counted_and_a_torn_tail_is_left_alone(tmp_path,
                                                                 pattern):
    """The aggregator reads through the watcher's tolerant tail (WP-1401).

    A corrupt line costs a count, never the summary, and the half line a live
    writer has not finished is not parsed — so a running job can be summarised.
    """
    path = tmp_path / "events.jsonl"
    with EventStream(path=path) as stream:
        _fit(pattern, stream)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("{not json\n")
        fh.write('{"record": "event", "v": "3", "t": 1')   # torn, no newline
    summary = summarize_events(path)
    assert summary.bad_lines == 1
    assert summary.runs[0].n_fits_ended == 1


# --------------------------------------------------------------------- the CLI
def test_rietx_events_prints_per_run_and_json_round_trips(tmp_path, pattern,
                                                          capsys):
    from rietx.cli import main

    path = tmp_path / "events.jsonl"
    for _ in range(2):
        with EventStream(path=path) as stream:
            _fit(pattern, stream)

    assert main(["events", str(path)]) == 0
    text = capsys.readouterr().out
    assert "2 runs" in text and "run 1" in text and "run 2" in text
    assert "termination" in text

    assert main(["events", str(path), "--json"]) == 0
    raw = capsys.readouterr().out
    assert EventsSummary.model_validate_json(raw) == summarize_events(path)

    assert main(["events"]) == 2
    assert main(["events", str(tmp_path / "missing.jsonl")]) == 2


# ------------------------------------------------- the readers stay as they were
def test_watch_and_the_recorder_read_a_headed_log(tmp_path, pattern):
    """``rietx watch``'s tail and a ``LiveSession`` run are unaffected.

    The tail hands lines through as dicts and counts nothing it can parse as
    bad, so the header arrives as one more line with its own ``record`` tag;
    the run's row and its status still come from the sidecars.
    """
    from rietx.viz.live import LiveSession

    live = tmp_path / "live"
    _fit(pattern, LiveSession(live))
    tail = runs.tail_events(live / runs.EVENTS_FILE)
    assert tail.bad_lines == 0
    assert tail.events[0]["record"] == RUN_RECORD
    assert {e["record"] for e in tail.events[1:]} == {"event"}
    assert tail.events[-1]["kind"] == "fit_end"
    row = runs.read_run(live)
    assert row.status is not None and row.status.stage == "closing"


def test_a_recorded_run_directory_starts_with_its_header(tmp_path, pattern):
    """The recorder opens its own file, so it writes its own header."""
    was = runs.set_enabled(True)
    try:
        structure, ins = perturbed_models()
        rx.Refinement(structure, ins, history=False).fit(
            pattern, plan=PLAN, telemetry=tmp_path)
    finally:
        runs.set_enabled(was)
    (log,) = tmp_path.glob(f"*/{runs.EVENTS_FILE}")
    lines = _lines(log)
    assert lines[0]["record"] == RUN_RECORD
    assert [r["record"] for r in lines[1:]] == ["event"] * (len(lines) - 1)
    assert summarize_events(log).runs[0].n_fits_ended == 1


# ------------------------------------------------------------- review of #902
def _stamped(monkeypatch):
    """Emit with a clock the test sets, so durations are exact."""
    now = [0.0]
    monkeypatch.setattr("rietx.history.events.time.time", lambda: now[0])
    return now


def test_a_stage_that_raised_does_not_lend_its_start_to_the_next_fit(
        tmp_path, monkeypatch):
    """A failed stage emits no ``stage_end``; the next fit's same-named stage
    must be timed from its own start, not the dead one's."""
    now = _stamped(monkeypatch)
    path = tmp_path / "events.jsonl"
    with EventStream(path=path) as stream:
        for t, kind, data in [
                (0.0, "fit_start", {}),
                (1.0, "stage_start", {"stage": "cell"}),    # raises: no end
                (100.0, "fit_start", {}),
                (101.0, "stage_start", {"stage": "cell"}),
                (103.0, "stage_end", {"stage": "cell"}),
                (103.0, "fit_end", {})]:
            now[0] = t
            stream.emit(kind, **data)
    (run,) = summarize_events(path).runs
    (cell,) = run.stages
    assert cell.seconds == pytest.approx(2.0)

    # the positive arm: within one fit a release's second start keeps the span
    path2 = tmp_path / "second.jsonl"
    with EventStream(path=path2) as stream:
        for t, kind in [(0.0, "fit_start"), (1.0, "stage_start"),
                        (2.0, "stage_start"), (4.0, "stage_end")]:
            now[0] = t
            stream.emit(kind, stage="cell")
    assert summarize_events(path2).runs[0].stages[0].seconds == \
        pytest.approx(3.0)


def test_header_id_exists_only_where_a_header_was_written(tmp_path):
    assert EventStream(callback=lambda e: None).header_id is None
    path = tmp_path / "events.jsonl"
    with EventStream(path=path) as stream:
        pass
    assert stream.header_id == _lines(path)[0]["run"]
    assert not hasattr(stream, "run_id")


def test_json_that_is_not_an_object_is_a_bad_line_not_a_crash(tmp_path,
                                                              pattern):
    path = tmp_path / "events.jsonl"
    with EventStream(path=path) as stream:
        _fit(pattern, stream)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write("[]\nnull\n3\n")
    summary = summarize_events(path)
    assert summary.bad_lines == 3
    assert summary.runs[0].n_fits_ended == 1
