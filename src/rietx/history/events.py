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
  ``fit_start.n_points`` is the **fitted** channel count, the one every
  ``stage_start`` carries (``project.fitted_mask``: in-range and inside
  ``two_theta_limits``); since WP-1457 the file's own count rides beside it as
  ``n_points_file``, where before it *was* ``n_points``.  Every
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

Every line carries ``t`` (Unix seconds) so a tail of the file doubles as a
progress bar; ``rietx watch`` renders it as the console pane.

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
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Literal

from pydantic import Field

from ..schemas.common import Base

#: Any change a consumer could observe bumps the last component by one, and
#: the comment says what changed — no classification, no digest (WP-1117).
#: ``data`` is an open dict by declaration (module docstring), so a new key in
#: it is not an observable change of the contract; a new kind is.
#: "2" since WP-1024 added the ``index_start``/``index_end`` kinds.
EVENT_SCHEMA_VERSION = "2"

EventKind = Literal["fit_start", "stage_start", "eval", "stage_end", "fit_end",
                    "index_start", "index_end"]


class EventRecord(Base):
    """A validated view of one event line — for readers, not the hot loop."""

    record: Literal["event"] = "event"
    v: str = EVENT_SCHEMA_VERSION
    t: float
    kind: EventKind
    data: dict[str, Any] = Field(default_factory=dict)


class EventStream:
    """Append-only JSONL sink (and/or a callback) for refinement events.

    ``path`` — file to append to (created; parent must exist).
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
    """Read an event log back, validating each line."""
    out: list[EventRecord] = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(EventRecord.model_validate_json(line))
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
