"""``progress=`` (WP-1302): a text line per stage boundary, read off events.

The one property worth pinning is the seam's own promise — ``progress`` is
an ``events=`` consumer, never a second telemetry channel — so every test
here captures the raw events alongside the text and checks the line's
numbers against the event's own fields, not against an independently
recomputed value.
"""

from __future__ import annotations

import io
import re

import rietx as rx
from rietx import Instrument, RefinementPlan, Stage
from rietx.schemas.instrument import BackgroundChebyshev
from tests.test_refine_synthetic import synthesize
from tests.test_schemas import make_lab6

LINE = re.compile(
    r"^(?:\[series (?P<idx>\d+)/(?P<n>\d+)\] (?P<label>\S+) )?"
    r"stage (?P<stage>\S+) (?P<status>\S+)"
    r"(?: Rwp (?P<rwp>[\d.]+))?(?: (?P<elapsed>\d+)s)?$")


def _instrument() -> Instrument:
    ins = Instrument.debye_scherrer(wavelength=0.4139)
    ins.background = BackgroundChebyshev.with_terms(4)
    return ins


def _short_plan() -> RefinementPlan:
    return RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=5),
        Stage("zero", ["instrument.zero_shift"], max_iter=5),
    ])


def test_one_line_per_stage_boundary_and_the_numbers_match_the_events():
    events = []
    buf = io.StringIO()
    plan = _short_plan()
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    ref.fit(synthesize(), plan=plan, progress=buf, events=events.append)

    stage_ends = [e for e in events if e["kind"] == "stage_end"]
    lines = buf.getvalue().splitlines()
    assert len(lines) == len(stage_ends) == len(plan.run_stages())

    stage_starts = {e["data"]["stage"]: e["t"] for e in events if e["kind"] == "stage_start"}
    for line, event in zip(lines, stage_ends, strict=True):
        m = LINE.match(line)
        assert m, line
        data = event["data"]
        assert m["stage"] == data["stage"]
        assert m["status"] == data["status"]
        assert float(m["rwp"]) == round(data["rwp"], 4)
        assert int(m["elapsed"]) == round(event["t"] - stage_starts[data["stage"]])


def test_progress_alone_needs_no_events_argument():
    buf = io.StringIO()
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    ref.fit(synthesize(), plan=_short_plan(), progress=buf)
    assert buf.getvalue().count("\n") == len(_short_plan().run_stages())


def test_progress_to_a_path_writes_and_is_closed(tmp_path):
    path = tmp_path / "progress.log"
    ref = rx.Refinement(make_lab6(), _instrument(), history=False)
    ref.fit(synthesize(), plan=_short_plan(), progress=str(path))
    text = path.read_text(encoding="utf-8")
    assert text.count("\n") == len(_short_plan().run_stages())
    assert "stage scale_bkg" in text and "stage zero" in text


def test_a_series_line_carries_the_series_stamp_and_the_numbers_still_match():
    events = []
    buf = io.StringIO()
    patterns = [synthesize(noise_seed=1), synthesize(noise_seed=2)]
    plan = RefinementPlan(stages=[
        Stage("scale_bkg", ["phases.*.scale", "instrument.background.*"], max_iter=5),
    ])
    result = rx.refine_sequential(
        patterns, make_lab6(), _instrument(), labels=["250C", "300C"],
        plan=plan, progress=buf, events=events.append)
    assert result.entries  # the fit ran, not just the plumbing

    stage_ends = [e for e in events if e["kind"] == "stage_end"]
    lines = buf.getvalue().splitlines()
    assert len(lines) == len(stage_ends)

    for i, (line, event) in enumerate(zip(lines, stage_ends, strict=True)):
        m = LINE.match(line)
        assert m, line
        data = event["data"]
        assert m["idx"] == str(data["series_index"] + 1)
        assert m["n"] == str(data["series_n"])
        assert m["label"] == data["series_label"]
        # each pattern's stages, the closing stage included, carry its label
        assert m["label"] == ["250C", "300C"][i // len(plan.run_stages())]
        assert float(m["rwp"]) == round(data["rwp"], 4)


def test_elapsed_time_covers_a_release_and_re_solve_not_just_the_second():
    """A WP-1301 phase release emits a second ``stage_start`` for the same
    name before re-solving (``history/events.py``'s own docstring). The
    printed elapsed time must cover the whole named stage, not just the
    solve that happened to be running when it last saw a start — found by
    code review, not by the acceptance fit (no fixture here reliably
    triggers a release), so this drives the writer directly off synthetic
    events instead.
    """
    from rietx.history.events import progress_writer

    buf = io.StringIO()
    write = progress_writer(buf)
    write({"t": 0.0, "kind": "stage_start", "data": {"stage": "cell"}})
    write({"t": 5.0, "kind": "stage_start", "data": {"stage": "cell"}})  # release, re-solve
    write({"t": 8.0, "kind": "stage_end",
          "data": {"stage": "cell", "status": "converged", "rwp": 0.05}})
    line = buf.getvalue().strip()
    assert line.endswith("8s"), line  # 8 - 0, not 8 - 5
