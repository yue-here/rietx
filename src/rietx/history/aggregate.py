"""What an event log says, per run: the post-hoc view ``rietx events`` prints.

WP-1322 (#207).  ``rietx watch`` serves a run while it is going; this answers
afterwards, in a terminal or a CI job, from the log alone: fits and stages
counted, wall clock per stage, which criterion ended each solve, which paths
the data could not see, and the first and last Rwp.

**Per run, partitioned on the header.**  A stream that opens a file writes a
``record: "run"`` line first (:class:`~rietx.history.events.RunHeader`), and a
re-run into the same path appends a second one, so every number here is a
run's own and no duration spans the seam between two runs — the mixture that
reported a 10.3 s fit as 459.0 s (#223).  A log written before the header
existed has none and is read as **one** run, which the summary says rather
than assumes.

**Read through the watcher's tail** (:func:`rietx.runs.tail_events`), not a
second reader: a corrupt line is counted rather than raised on, and the half
line a live writer has not finished is left unparsed, so a running job can be
summarised.

**It counts and subtracts; it never re-derives.**  Every number is a count of
records or a difference of their own ``t``; the vocabulary is the events'
(``termination`` is ``LSQOutcome.termination``'s, ``held`` is WP-1301's
``StageResult.held``), so this view and the series scrubber (WP-1317) name the
same things the same way.  A stage's seconds run from the **first**
``stage_start`` of its name to its ``stage_end``, because a stage that releases
a held phase emits a second ``stage_start`` before re-solving, and the wall
clock that matters is the whole named stage's — ``progress_writer``'s rule.
A fit's cost is ``fit_start`` to ``fit_end``: a sum of stage spans leaves out
whatever runs between stages (a stage report, a recompile), which can be most
of it.  The stage reports' own share is counted, because ``fit_end`` carries
``stage_report_seconds`` when a fit built them (WP-1335).
"""

from __future__ import annotations

import time
from collections import Counter
from pathlib import Path

from pydantic import Field

from ..schemas.common import Base
from .events import RUN_RECORD, RunHeader, StageClock

#: Lines read per pass of the tail.  A bound on memory per pass, not on the log.
_CHUNK_BYTES = 16 << 20

#: How many held paths the text view names; ``--json`` carries all of them.
TEXT_HELD_ROWS = 5


class StageTiming(Base):
    """One stage name within one run: how often it ended, and its clock."""

    stage: str
    #: ``stage_end`` events of this name.
    count: int
    #: Σ over its occurrences of first ``stage_start`` → ``stage_end``.
    seconds: float
    #: ``eval`` events carrying this stage name.
    n_evals: int


class RunSummary(Base):
    """One run of an event log, counted from its own records."""

    #: ``None`` for a log written before WP-1322: the whole file is one run.
    header: RunHeader | None = None
    #: First and last ``t`` in the run, the header's included.
    t_first: float | None = None
    t_last: float | None = None
    wall_seconds: float = 0.0
    n_events: int = 0
    n_fits: int = 0
    n_fits_ended: int = 0
    #: Σ ``fit_start`` → ``fit_end`` over the run's completed fits.
    fit_seconds: float = 0.0
    #: Σ ``fit_end.stage_report_seconds``: the share of ``fit_seconds`` spent
    #: building ``stage_reports=True`` rungs, which no stage span holds
    #: (WP-1335).  ``None`` when no fit in the run built one.
    stage_report_seconds: float | None = None
    n_stage_starts: int = 0
    n_stage_ends: int = 0
    n_evals: int = 0
    #: In order of first appearance.
    stages: list[StageTiming] = Field(default_factory=list)
    #: ``stage_end.termination`` → count; ``"(absent)"`` where a stage_end
    #: carries none (an indexing unit, a log from before WP-1113).
    terminations: dict[str, int] = Field(default_factory=dict)
    #: ``stage_end.held`` path → count, most held first.
    held: dict[str, int] = Field(default_factory=dict)
    #: Rwp of the first and last ``stage_end``/``fit_end`` that carries one.
    first_rwp: float | None = None
    last_rwp: float | None = None

    def __str__(self) -> str:
        lines = []
        if self.header is None:
            lines.append("  header: none")
        fit = (f", {self.fit_seconds:.2f} s fit_start→fit_end"
               if self.n_fits_ended else "")
        if self.n_fits_ended and self.stage_report_seconds is not None:
            fit += f", {self.stage_report_seconds:.2f} s of it stage reports"
        lines.append(f"  fits {self.n_fits} ({self.n_fits_ended} ended{fit})"
                     f"   stages {self.n_stage_ends} ended "
                     f"({self.n_stage_starts} started)   evals {self.n_evals}")
        if self.first_rwp is not None:
            lines.append(f"  Rwp first {self.first_rwp:.4f}   "
                         f"last {self.last_rwp:.4f}")
        if self.stages:
            width = max(12, *(len(s.stage) for s in self.stages))
            lines.append(f"  {'stage':<{width}}  {'n':>4}  {'seconds':>9}  "
                         f"{'evals':>6}")
            for s in self.stages:
                lines.append(f"  {s.stage:<{width}}  {s.count:>4}  "
                             f"{s.seconds:>9.2f}  {s.n_evals:>6}")
        if self.terminations:
            lines.append("  termination: " + ", ".join(
                f"{k} {v}" for k, v in self.terminations.items()))
        if self.held:
            shown = list(self.held.items())[:TEXT_HELD_ROWS]
            more = len(self.held) - len(shown)
            lines.append("  most held: " + ", ".join(
                f"{k} ({v})" for k, v in shown)
                + (f", and {more} more" if more else ""))
        return "\n".join(lines)


class EventsSummary(Base):
    """An event log, run by run: what :func:`summarize_events` returns."""

    path: str
    n_runs: int
    #: Lines that did not parse as JSON, counted and skipped.
    bad_lines: int = 0
    runs: list[RunSummary] = Field(default_factory=list)

    def __str__(self) -> str:
        noun = "run" if self.n_runs == 1 else "runs"
        bad = f", {self.bad_lines} unreadable line(s) skipped" if self.bad_lines else ""
        out = [f"{self.path}: {self.n_runs} {noun}{bad}"]
        for i, run in enumerate(self.runs, start=1):
            if run.header is not None:
                opened = time.strftime("%Y-%m-%d %H:%M:%S",
                                       time.localtime(run.header.t))
                head = f"run {i}  header {run.header.run}  opened {opened}"
            else:
                head = f"run {i}"
            out.append(f"{head}   wall {run.wall_seconds:.2f} s")
            out.append(str(run))
        return "\n".join(out)


def _read_lines(path: Path) -> tuple[list[dict], int]:
    """Every whole line of the log as a dict, through the watcher's tail."""
    from ..runs import tail_events  # runs imports this package

    records: list[dict] = []
    bad = 0
    offset = 0
    while True:
        tail = tail_events(path, offset, max_bytes=_CHUNK_BYTES)
        # a line that is JSON but not an object is as unreadable as torn text
        records.extend(e for e in tail.events if isinstance(e, dict))
        bad += tail.bad_lines + sum(not isinstance(e, dict)
                                    for e in tail.events)
        if tail.offset <= offset:
            return records, bad
        offset = tail.offset


def _segment(records: list[dict]) -> list[tuple[dict | None, list[dict]]]:
    """Split on run headers; anything before the first is a header-less run."""
    runs: list[tuple[dict | None, list[dict]]] = []
    for record in records:
        if record.get("record") == RUN_RECORD:
            runs.append((record, []))
        elif not runs:
            runs.append((None, [record]))
        else:
            runs[-1][1].append(record)
    return runs


def _summarize_run(header: dict | None, events: list[dict]) -> RunSummary:
    times = [r["t"] for r in ([header] if header else []) + events
             if isinstance(r.get("t"), (int, float))]
    n_fits = n_fits_ended = n_starts = n_ends = n_evals = 0
    fit_seconds = 0.0
    report_seconds: float | None = None
    fit_open: float | None = None
    clock = StageClock()  # the rule progress_writer reads too (WP-2031)
    stage_count: Counter = Counter()
    stage_seconds: dict[str, float] = {}
    stage_evals: Counter = Counter()
    order: list[str] = []
    terminations: Counter = Counter()
    held: Counter = Counter()
    rwps: list[float] = []

    for event in events:
        if event.get("record") != "event":
            continue
        kind = event.get("kind")
        data = event.get("data") or {}
        t = event.get("t")
        stage = data.get("stage")
        elapsed = clock.observe(kind, stage, t, resumed="released" in data)
        if kind == "fit_start":
            n_fits += 1
            fit_open = t
        elif kind == "fit_end":
            n_fits_ended += 1
            if fit_open is not None and t is not None:
                fit_seconds += t - fit_open
            fit_open = None
            if isinstance(data.get("stage_report_seconds"), (int, float)):
                report_seconds = ((report_seconds or 0.0)
                                  + float(data["stage_report_seconds"]))
        elif kind == "stage_start":
            n_starts += 1
            if stage is not None:
                if stage not in stage_seconds:
                    order.append(stage)
                    stage_seconds[stage] = 0.0
        elif kind == "stage_end":
            n_ends += 1
            terminations[data.get("termination") or "(absent)"] += 1
            held.update(data.get("held") or [])
            if stage is not None:
                if stage not in stage_seconds:
                    order.append(stage)
                    stage_seconds[stage] = 0.0
                stage_count[stage] += 1
                if elapsed is not None:
                    stage_seconds[stage] += elapsed
        elif kind == "eval":
            n_evals += 1
            if stage is not None:
                stage_evals[stage] += 1
        if kind in ("stage_end", "fit_end") and data.get("rwp") is not None:
            rwps.append(float(data["rwp"]))

    return RunSummary(
        header=RunHeader.model_validate(header) if header else None,
        t_first=min(times) if times else None,
        t_last=max(times) if times else None,
        wall_seconds=(max(times) - min(times)) if times else 0.0,
        n_events=sum(r.get("record") == "event" for r in events),
        n_fits=n_fits, n_fits_ended=n_fits_ended, fit_seconds=fit_seconds,
        stage_report_seconds=report_seconds,
        n_stage_starts=n_starts, n_stage_ends=n_ends, n_evals=n_evals,
        stages=[StageTiming(stage=s, count=stage_count[s],
                            seconds=stage_seconds[s], n_evals=stage_evals[s])
                for s in order],
        terminations=dict(terminations),
        held=dict(held.most_common()),
        first_rwp=rwps[0] if rwps else None,
        last_rwp=rwps[-1] if rwps else None,
    )


def summarize_events(path: str | Path) -> EventsSummary:
    """Summarise an ``events.jsonl`` per run (the function under ``rietx events``).

    ``path`` is the log, or a run directory holding one.  Raises
    ``FileNotFoundError`` when there is no log there.
    """
    from ..runs import EVENTS_FILE

    p = Path(path)
    if p.is_dir():
        p = p / EVENTS_FILE
    if not p.is_file():
        raise FileNotFoundError(f"no event log at {p}")
    records, bad = _read_lines(p)
    runs = [_summarize_run(header, events)
            for header, events in _segment(records)]
    return EventsSummary(path=str(p), n_runs=len(runs), bad_lines=bad,
                         runs=runs)
