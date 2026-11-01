"""Per-iteration event stream — the live telemetry of a running refinement.

Same JSONL record style as the history log (a tagged ``record`` field per
line), but a *separate* file: history nodes are ~10 kB immutable checkpoints,
events are one-line heartbeats emitted from inside the least-squares loop.

The hot-loop invariant holds here too: :meth:`EventStream.emit` touches only
plain dicts and ``json.dumps`` — no pydantic anywhere near the residual.
:class:`EventRecord` (pydantic) exists for *reading* the log back with
validation, never for writing.

Event kinds (closed set, versioned with the schema):

* ``fit_start`` / ``fit_end`` — one refinement run (mode, plan, statistics).
  ``fit_start.n_points`` is the **file's** channel count; since WP-1457 the
  **fitted** count, the one every ``stage_start`` carries as its
  ``n_points`` (``project.fitted_mask``: in-range and inside
  ``two_theta_limits``), rides beside it as ``n_fitted``.  Every
  ``stage_end.rwp`` is the Rwp of the model the stage fitted, declared peaks
  included — the same sum ``CompiledModel.evaluate`` makes — so the last one
  equals ``fit_end.rwp`` wherever the final compile rebuilds the stage's model;
* ``stage_start`` / ``stage_end`` — one staged-plan stage (freed paths, costs).
  ``stage_start`` carries ``index`` (**1-based**, so it reads "stage 3 of 5"
  directly), ``n_stages``, and since WP-1113 ``free_paths`` — the stage's full
  ordered free list, which is the alignment key for ``eval.values`` below.
  ``stage_end`` carries ``termination`` (also WP-1113): *which* criterion
  ended the solve (``ftol``/``xtol``/``gtol``… — ``LSQOutcome.termination``'s
  vocabulary), where ``status`` says only whether it converged.  Since WP-1301
  both carry ``held`` — the paths the stage held because the data could not see
  their phase — and ``stage_end`` also ``released``, the ones it let go again.
  Since WP-2047 ``stage_end`` carries ``window_loss``,
  ``StageResult.window_loss`` as soon as the stage ends, so a stream sees a
  stale stage before the fit does.
  A stage that releases **emits a second** ``stage_start`` before it re-solves,
  with the same ``stage``/``index`` and the longer ``free_paths``: ``values``
  aligns with the *most recent* ``stage_start``, the way an indexing run's
  revisable ladder is already read;
* ``eval`` — one residual evaluation inside a least-squares driver, on both of
  them since WP-1113.  ``n_eval`` counts every call this driver made the
  residual measure (function + finite-difference), which is exactly the
  quantity that tracks wall-clock progress.  Since WP-1113 each event also
  carries the trajectory fields the evaluation-count mechanism analysis reads:
  ``accepted`` (did this evaluation become the incumbent), ``step_norm``
  (internal-coordinate L2 distance from the incumbent accepted iterate; absent
  on a solve's first evaluation), ``values`` (the physical value of every free
  parameter at this evaluation, in ``stage_start.free_paths`` order — the
  appended Pawley intensity tail excluded), and on the LM driver ``lam`` (the
  Marquardt λ that produced the step).  The two drivers hook differently and
  it shows: scipy TRF has no per-iteration callback, so the residual closure
  is the hook and ``accepted`` is reconstructed (a trial is accepted exactly
  when its cost is strictly below the incumbent's), while the trust radius is
  scipy-internal and the trial ``step_norm`` sequence is its observable shadow;
  the LM driver reports each *measured trial* through a real callback
  (``on_trial``), so a trial its linear model discards without evaluating the
  residual emits nothing — before WP-1113 the LM stream carried accepted
  points only, an alignment of the emission with this bullet's declared
  meaning, not a change of it;
* ``index_start`` / ``index_end`` — one **indexing** run (WP-1024).  A separate
  pair rather than a reuse of ``fit_start``/``fit_end`` because an indexing run
  has none of what a refinement run has: no mode, no Rwp, no history node.  What
  it *does* have is engines and systems, and those go on the open ``data`` dict —
  the progress in between is emitted as ``stage_start``/``stage_end`` with
  ``index``, ``n_stages``, ``engine`` and ``system``, so ``rietx watch``
  and the GUI's progress reporting need no new case at all.  Since WP-1037 that
  ladder is **flat and per (engine × system)** — plus a unit per dominant-zone
  probe rung and per validation fit — and its ``n_stages`` is **revisable
  mid-run**: probe and validation counts are unknowable at ``index_start``
  (the probe runs only after an empty search, the validation count only after
  consensus), so a consumer treats ``n_stages`` as the current best claim
  rather than a constant.  Revising a field's *value* is not a change of its
  meaning, so the additivity rule below holds and the version does not move.
  WP-1042 rides the same rule: every ladder emission carries
  ``elapsed_seconds`` (+ ``remaining_seconds`` under a declared ceiling), a
  finished search unit's ``stage_end`` carries ``provisional`` cells with no
  confidence field, and each completed system adds a ``consensus:<system>``
  unit whose ``stage_end`` carries the graded shortlist in the WP-1043
  evidence shape — added fields and added *units*, no new kind;

* ``solve_start`` / ``solve_step`` / ``solve_end`` — one **structure-solution**
  run (#562 S2b, WP number pending; ``solve.workflow.solve_structure``).  The
  pair is indexing's for the same reason: a search has no mode, no Rwp and no
  history node.  Its units — a race round of a site-class assignment, a seed,
  a prior-off control seed, and a ``consensus:<space group>`` unit after each
  group — ride ``stage_start``/``stage_end`` with ``index``/``n_stages``
  exactly as indexing's do, so ``rietx watch`` draws the ladder with no new
  case.  ``solve_step`` is the heartbeat **inside** a unit, every
  ``heartbeat_sweeps`` sweeps: the leader (its J and χ²/χ²_floor), whether it
  changed since the previous heartbeat, the sweeps since it last improved,
  and the ladder's move and swap acceptance.  A new kind rather than ``eval``,
  because ``eval`` means one residual evaluation inside a least-squares
  driver and a kind's meaning is what the version guards;

**A joint fit** (``multi.MultiHistogramRefinement``, WP-1341) is one solve
over several histograms, so it emits each kind once per fit, stage or
evaluation, never once per histogram.  A series stamps its index on every
event because each event there is about one pattern; here none is.  What is
about one histogram rides in a ``histograms`` list on ``fit_start``,
``stage_start``, ``stage_end`` and ``fit_end``, one row each stamped with its
``histogram_index``, beside ``n_histograms``.  An ``eval``'s ``values`` align
with combined free paths, ``hist.<h>.``-scoped where a row is one histogram's.
Added keys on existing kinds, so the version does not move.

Every line carries ``t`` (Unix seconds) so a tail of the file doubles as a
progress bar; ``rietx watch`` renders it as the console pane.

**Where one run ends** (WP-1322, #223).  A stream that opens a file writes one
``record: "run"`` line first — :class:`RunHeader`, carrying a fresh ``run`` id
and the open time — and nothing else in the file is one.  The file is still
opened for append, because two things depend on it: a series forwards every
pattern's events through one stream, and ``rietx watch`` tails the file.  What
append cost was a run boundary: a re-run into the same path merged into the
previous log, and a duration derived across the seam was a mixture (10.3 s
reported as 459.0 s, on a timing study).  The header is what a reader
partitions on (:func:`rietx.history.aggregate.summarize_events`); a log
written before it has none and reads as one run.

It is a **record**, not a kind, for three reasons.  ``EventKind`` is closed and
a run's state is deliberately not an event (``runs.py``), and an opened file is
a fact about the file rather than about the fit.  It is **never emitted**: it
goes to the file and to no callback, so ``progress=``, the run recorder, a
series' stamp and the GUI receive exactly what they did before.  And the tag is
the history log's own convention, whose first line is a header record beside
its node records (``history/store.py``).  :func:`read_events` returns events
only, as it always did.

**Adding a field to an existing kind does not bump**
:data:`EVENT_SCHEMA_VERSION`.  ``data`` is an open dict on both sides: readers
render whatever keys arrive (``watch.mjs`` iterates ``Object.entries``) and
:class:`EventRecord` validates the envelope, not the payload — so an older
reader tailing a newer log shows the new key and misses nothing it knew about.
A **new kind**, a **removed or renamed field**, or a change of a field's
*meaning* is what the version is for.  ``stage_start.index``/``n_stages``
(WP-1006) were added under exactly this rule; the note is here because the
reflex is to bump, and a version that moves for additive changes stops being
usable as a compatibility signal.  A cancelled run's ``fit_end`` carries
``status="cancelled"`` and *omits* ``rwp``/``gof`` — there is no fitted result
to report — which is the same rule seen from the reader's side: a consumer
reads ``data`` with ``.get``, never by unpacking a fixed shape.

**Version 2** (WP-1024) is the rule's other half made real:
``index_start``/``index_end`` are new *kinds*, so the constant moves.  WP-1006
declined to add them in advance precisely because a kind nothing emits is an
untested guess about a loop that did not exist; now the loop exists
(``index_pattern``) and emits them.  The per-engine progress inside the run
deliberately reuses ``stage_start``/``stage_end`` with extra ``data`` keys, which
is additive and would not have bumped anything on its own.

**Version 3** (WP-1322): the run header.  Not a kind, but a reader that
validates every line as an :class:`EventRecord` — this module's own
``read_events`` before 1322 — refuses the line, so it is a change a consumer
can observe and the constant moves for it.

**Version 4** (#562 S2b): ``solve_start``/``solve_step``/``solve_end``, new
kinds.  Since then a line's ``v`` is checked against its kind
(:data:`KIND_SINCE`): a kind is refused on a line claiming a version older
than the one that introduced it, since no writer of that version could have
written it, and a ``v`` that is not a whole number is refused outright.  A
newer ``v`` with a known kind is read, the additivity rule's reader side.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from pathlib import Path
from typing import Any, Literal

from pydantic import Field, model_validator

from ..schemas.common import Base

#: Any change a consumer could observe bumps the last component by one, and
#: the comment says what changed — no classification, no digest (WP-1117).
#: ``data`` is an open dict by declaration (module docstring), so a new key in
#: it is not an observable change of the contract; a new kind is.
#: "2" since WP-1024 added the ``index_start``/``index_end`` kinds.
#: "3" since WP-1322 added the run header, a ``record: "run"`` line an
#: ``EventRecord``-validating reader of version 2 refuses.
#: "4" since #562 S2b added the ``solve_start``/``solve_step``/``solve_end``
#: kinds.
EVENT_SCHEMA_VERSION = "4"

#: The ``record`` tag of the one line a stream writes when it opens a file.
RUN_RECORD = "run"

EventKind = Literal["fit_start", "stage_start", "eval", "stage_end", "fit_end",
                    "index_start", "index_end", "solve_start", "solve_step", "solve_end"]

#: The version that introduced each kind (version 1 had the first five).  A
#: meta-test holds it equal to ``EventKind``.
KIND_SINCE: dict[str, int] = {
    "fit_start": 1, "stage_start": 1, "eval": 1, "stage_end": 1, "fit_end": 1,
    "index_start": 2, "index_end": 2,
    "solve_start": 4, "solve_step": 4, "solve_end": 4,
}


class EventRecord(Base):
    """A validated view of one event line — for readers, not the hot loop.

    ``v`` is checked against ``kind`` (:data:`KIND_SINCE`, version 4's rule in
    the module docstring)."""

    record: Literal["event"] = "event"
    v: str = EVENT_SCHEMA_VERSION
    t: float
    kind: EventKind
    data: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _kind_exists_at_version(self) -> EventRecord:
        if not self.v.isdigit():
            raise ValueError(f"event version {self.v!r} is not a whole number")
        if int(self.v) < KIND_SINCE[self.kind]:
            raise ValueError(
                f"a {self.kind!r} event cannot carry version {self.v}: the kind arrived in "
                f"version {KIND_SINCE[self.kind]}")
        return self


class RunHeader(Base):
    """The line a stream writes when it opens a file: where a run begins.

    ``run`` is fresh per opened stream, so two runs appended to one path are
    two headers with two ids.  ``data`` is open, as an event's is.
    """

    record: Literal["run"] = RUN_RECORD
    v: str = EVENT_SCHEMA_VERSION
    t: float
    run: str
    data: dict[str, Any] = Field(default_factory=dict)


def run_header(run_id: str) -> dict:
    """The header line as a plain dict, for a writer that opens its own file.

    Plain, like :meth:`EventStream.emit`'s events: no pydantic on the writing
    side.  ``pid`` tells apart two processes appending to one path.
    """
    return {"record": RUN_RECORD, "v": EVENT_SCHEMA_VERSION, "t": time.time(),
            "run": run_id, "data": {"pid": os.getpid()}}


def new_run_id() -> str:
    """A run id: twelve hex digits, unique enough to tell appended runs apart."""
    return uuid.uuid4().hex[:12]


class EventStream:
    """Append-only JSONL sink (and/or a callback) for refinement events.

    ``path`` — file to append to (created; parent must exist).  Opening one
    writes a :class:`RunHeader` line first, so a reader can tell this run
    from any run appended before it; a callback never receives it.
    ``callback`` — called with each event dict after it is written; exceptions
    in the callback are the caller's problem (they propagate — a monitoring
    hook that crashes the refinement is a bug you want to see, not swallow).
    """

    def __init__(self, path: str | Path | None = None, callback=None):
        self.path = Path(path) if path is not None else None
        self.callback = callback
        # ``newline="\n"``: JSONL, so the line ending is the format's and
        # not the platform's (WP-1439).
        self._fh = (open(self.path, "a", encoding="utf-8", newline="\n")
                    if self.path else None)
        self.n_written = 0
        #: The id this stream's header carries; ``None`` until a header is
        #: written, so a callback-only stream has none.  Not the id
        #: ``rietx watch`` lists a run directory under (``runs.run_id_for``).
        self.header_id: str | None = None
        if self._fh is not None:
            self._write_header()

    def _write_header(self) -> None:
        """Mark where this run begins in the file (WP-1322).

        Written straight to the file, never through :meth:`emit`: it is not an
        event, ``n_written`` does not count it, and no callback sees it.
        """
        self.header_id = new_run_id()
        self._fh.write(json.dumps(run_header(self.header_id)) + "\n")
        self._fh.flush()

    def emit(self, kind: str, **data: Any) -> None:
        event = {"record": "event", "v": EVENT_SCHEMA_VERSION,
                 "t": time.time(), "kind": kind, "data": data}
        if self._fh is not None:
            self._fh.write(json.dumps(event) + "\n")
            self._fh.flush()
        if self.callback is not None:
            self.callback(event)
        self.n_written += 1

    def close(self) -> None:
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    def __enter__(self) -> "EventStream":
        return self

    def __exit__(self, *exc) -> None:
        self.close()


def as_event_stream(events) -> EventStream | None:
    """Normalise the ``events=`` argument of ``Refinement.fit``."""
    if events is None or isinstance(events, EventStream):
        return events
    if callable(events):
        return EventStream(callback=events)
    return EventStream(path=events)


def read_events(path: str | Path) -> list[EventRecord]:
    """Read an event log back, validating each line.

    Events only, of every run in the file, in file order: a run header
    (:class:`RunHeader`) is skipped, so this returns what it returned before
    there were headers.  To read a log per run, use
    :func:`rietx.history.aggregate.summarize_events`.
    """
    out: list[EventRecord] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            record = json.loads(line)
            if record.get("record") == RUN_RECORD:
                RunHeader.model_validate(record)
                continue
            out.append(EventRecord.model_validate(record))
    return out


def progress_writer(sink) -> Any:
    """Turn ``progress=`` into an ``events=`` callback (WP-1302): one text
    line per ``stage_end``, and per pattern under a series (the ``series_*``
    stamp — see :class:`~rietx.sequential._SeriesStream` — arrives on the
    same event, so this needs no series-aware branch of its own).

    Never a second telemetry channel: this reads the exact events a JSONL
    log or a caller's own callback would, so ``rietx watch`` and a progress
    line always agree, by construction, about what happened and when.  Every
    number on the line is read straight off the event's own ``data`` (and its
    own ``t``, against the matching ``stage_start``'s, for elapsed time) —
    this function formats, it never computes.

    ``sink`` is a text stream (``hasattr(sink, "write")``) or a path, opened
    for append — the caller's to close if they passed a stream (untouched
    here), and closed by :func:`_attach_progress` alongside its
    ``EventStream`` if they passed a path, matching how that class treats its
    own file handle. The returned callback carries that file as ``.close``
    when it owns one, which is what ``_attach_progress`` chains onto the
    stream's own ``close``.
    """
    owns_fh = not hasattr(sink, "write")
    # ``newline="\n"``: JSONL again (WP-1439).  A caller who passed their
    # own stream owns its newline translation, as they own its encoding.
    fh = (open(sink, "a", encoding="utf-8", newline="\n")
          if owns_fh else sink)
    #: the *first* stage_start seen for a name, not the most recent — a
    #: WP-1301 phase release emits a second stage_start before re-solving,
    #: and the elapsed time a caller reads on the stage_end wants the whole
    #: named stage's wall clock, both solves included, not just the second's
    #: (unlike ``values``, which does want the most recent alignment; see
    #: this module's docstring — a different question, a different answer).
    first_start: dict[str, float] = {}

    def _write(event: dict) -> None:
        kind = event.get("kind")
        data = event.get("data", {})
        stage = data.get("stage")
        if stage is None:
            return
        if kind == "stage_start":
            first_start.setdefault(stage, event["t"])
            return
        if kind != "stage_end":
            return
        parts = []
        if "series_index" in data and "series_n" in data:
            parts.append(f"[series {data['series_index'] + 1}/{data['series_n']}]")
            if data.get("series_label"):
                parts.append(str(data["series_label"]))
        parts.append(f"stage {stage}")
        parts.append(str(data.get("status", "?")))
        if data.get("rwp") is not None:
            parts.append(f"Rwp {data['rwp']:.4f}")
        start_t = first_start.pop(stage, None)
        if start_t is not None:
            parts.append(f"{event['t'] - start_t:.0f}s")
        fh.write(" ".join(parts) + "\n")
        fh.flush()

    if owns_fh:
        _write.close = fh.close
    return _write


def _attach_progress(stream: EventStream | None, progress) -> EventStream | None:
    """Fold ``progress=`` into an ``events=`` stream as one more callback.

    ``progress`` alone (no ``events=``) gets a bare callback-only
    ``EventStream``, so a caller never has to pass both just to see lines.
    With both, the caller's own callback (if ``events=`` was one) still runs
    — this adds a second subscriber, it does not replace the first.  A
    progress *path* (as opposed to a stream the caller owns) gets its file
    closed alongside the returned stream's own ``close()``, the same way a
    bare ``events=`` path does.
    """
    if progress is None:
        return stream
    writer = progress_writer(progress)
    if stream is None:
        stream = EventStream(callback=writer)
    else:
        prior = stream.callback

        def _combined(event: dict, _prior=prior, _writer=writer) -> None:
            if _prior is not None:
                _prior(event)
            _writer(event)

        stream.callback = _combined
    if hasattr(writer, "close"):
        close_stream = stream.close

        def _close(_close_stream=close_stream, _writer=writer) -> None:
            _close_stream()
            _writer.close()

        stream.close = _close
    return stream
