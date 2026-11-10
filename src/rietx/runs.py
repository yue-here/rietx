"""Refinement runs on disk: the reader ``rietx watch`` is built on (WP-1401),
and the recorder that writes one for a fit nobody asked to record (WP-1403).

A *run* is a directory holding an event log. :class:`~rietx.viz.live.LiveSession`
writes one, and so does every GUI project under its ``live/``. This module
discovers them, says whether each is still being written, and tails its log from
a byte offset. :mod:`rietx.watch` is transport over it, the split
``gui/server.py`` already declares for itself.

**The reader constructs nothing.** No ``Project.open``, which appends a head
annotation and is why there is no read-only way to open a project; no
``Refinement``; no ``read_pattern``. Everything a reader needs, a writer
captured. This is a rule and not a preference: a viewer that constructs a
project mutates what it is looking at.

The reader has exactly one verb, added by WP-1405 and named here because it is
the exception: :func:`request_cancel` writes :data:`CANCEL_FILE` into a run
directory, and the fit writing that directory stops at its next evaluation.
Stopping a runaway is the one thing a reader cannot do from the other side, and
the verb still constructs nothing — it writes a request into a directory the
walk already offered, and the fit's own token is what acts on it.

**The two halves share one file contract, which is why they share a module.**
:class:`RunRecorder` writes the names the reader above looks for — ``meta.json``,
``run.lock``, ``status.json`` — and a writer that invented its own would be
invisible to the reader without a single test going red. Splitting them across
two modules would put the halves of one agreement in two files. What does *not*
cross the seam is weight: the recorder imports ``viz.snapshot`` inside the
method that needs it, so a viewer importing this module still pays for nothing
it will not draw.

Every reader field stays optional, because a directory with no sidecars
resolves to a *legacy* run synthesized from its log's mtime. That is what every
run directory written before WP-1403 is, and it is what keeps them all visible
forever.

The state of a run is not an event. ``history/events.py`` states that for one
process: a fit that raises emits no ``fit_end``, and ``EventKind`` is closed, so
a run's status travels beside the stream. Across a process boundary the same
rule needs a channel the operating system maintains, because a dead writer
writes nothing — see :func:`liveness_of`.

Two things this module deliberately has not got (WP-1406). Both are the reflex,
so the refusal is written here rather than lost in a commit message.

**No** ``capabilities()`` **surface flag** for "can this build record runs?".
That question always answers yes, because no optional dependency stands behind
recording. The flag would be a literal ``True`` wearing a predicate's clothes,
which ``capabilities._features`` forbids by construction; and ``_SURFACE_FLAGS``
exists precisely because a *derived* flag rots in silence, ``features``
``["indexing"]`` having been ``False`` for its whole life (WP-1037).

**No seventh versioned contract** for the run layout. The layout is a second
process's contract, which is the argument for giving it one. Against it:
nothing negotiates over it, and WP-1006's own precedent is that a contract
nothing has exercised is an untested guess. So it waits until the layout has
survived a release. ``reference/compatibility.md`` says the same thing to a reader,
which is the promise that has to be kept if this is ever revisited.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import socket
import stat as stat_mod
import sys
import threading
import time
import warnings
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import ConfigDict

from ._about import (
    LIVE_DIR_NAME,
    PROJECT_SUFFIX,
    RUNS_DIR_NAME,
    STATE_DIR_NAME,
    TELEMETRY_ENV,
)
from .history.events import EVENT_SCHEMA_VERSION, EventStream
from .schemas.common import Base

#: The log every run has, and the only file this module needs to find one.
#: Written by :class:`~rietx.history.events.EventStream` (append) and truncated
#: by :class:`~rietx.viz.live.LiveSession` on construction.
EVENTS_FILE = "events.jsonl"

#: Per-stage progress, and the run's own state. Two writers, which is why the
#: schema below is halved: ``LiveSession.write_snapshot`` writes
#: ``stage``/``rwp``/``gof``/``chi2``/``n_free`` from the snapshot payload's own
#: statistics and **no** ``state``; :class:`RunRecorder` writes the rest.
STATUS_FILE = "status.json"

#: The run's own description of itself, written by :class:`RunRecorder`. A run
#: directory without one is *legacy* — every run written before WP-1403, and
#: every directory a ``LiveSession`` makes for itself.
META_FILE = "meta.json"

#: Held flock'd by :class:`RunRecorder` for the writing process's life. See
#: :func:`liveness_of` for why a held lock is the liveness channel and a pid is
#: only the fallback.
LOCK_FILE = "run.lock"

#: The stage's curves, ticks and statistics, rewritten per stage by
#: ``LiveSession.write_snapshot``. Not read here; the run row reports whether
#: it exists so a client can decide whether to draw.
SNAPSHOT_FILE = "snapshot.json"

#: What a run recorded before WP-1402 left behind: a self-contained plotly
#: page, several megabytes of it. Nothing writes one any more and one already
#: on disk still opens, so a run that has only this is still a run with a
#: picture — reported separately, because the two are drawn differently and
#: conflating them would show an empty plot for a legacy run.
LEGACY_SNAPSHOT_FILE = "fit.html"

#: Directory names the walk never descends. Cheap to extend; each is a tree
#: that cannot hold a run and can hold a great many files.
PRUNE_DIRS = frozenset({".git", "node_modules", ".venv", "venv", "__pycache__",
                        "_build", "dist", "build", ".mypy_cache",
                        ".pytest_cache", ".ruff_cache", ".tox", "site-packages",
                        ".claude"})

#: How deep :func:`discover` walks below its root, and how many runs it returns.
#: Both are bounds on a web page's poll, not opinions about a tree's shape.
MAX_DEPTH = 8
MAX_RUNS = 500

#: States a writer declares for itself. ``running`` is the only non-terminal
#: one; :data:`TERMINAL_STATES` is the rest. An **open** vocabulary, the way a
#: ``GuardFinding.code`` is: :attr:`RunStatus.state` is typed ``str`` so a
#: newer writer's member is read rather than refused, and a value not named
#: here falls through :func:`liveness_of` to the lock and the pid.
RUN_STATES = frozenset({"running", "done", "failed", "cancelled"})
TERMINAL_STATES = frozenset({"done", "failed", "cancelled"})

#: WP-1302's termination view, written once by :class:`RunRecorder` after the
#: result exists. ``str(result)`` and never ``ref.summary()``, which builds a
#: whole ``FitReport`` — the expensive half of that call. A run with no result
#: (cancelled, or raised) has none, and that absence is not an error.
SUMMARY_FILE = "summary.txt"

#: The one file a *reader* writes, and the whole cross-process stop mechanism
#: (WP-1405). A file rather than a socket because the two processes already
#: share exactly one thing — this directory — and a second channel would let a
#: watcher reach a fit it cannot see.
#:
#: It is **request-shaped and not a flag**: the body is a JSON object with a
#: ``request`` key, so a later vocabulary (pause, edit a parameter, re-run a
#: stage) is more words in this seam rather than another one. The name is the
#: verb, so an absent or unreadable body still reads as a cancel — ``touch
#: cancel`` is the obvious gesture and it works. A body naming something this
#: version does not know is **declined by name** rather than rounded to the
#: file's name: an old recorder facing a newer watcher's ``pause`` must not
#: stop the fit. :func:`request_cancel` writes it, :meth:`RunRecorder.poll_cancel`
#: consumes it.
CANCEL_FILE = "cancel"

#: The only request :meth:`RunRecorder.poll_cancel` honours. Everything else in
#: that file lands in :attr:`RunStatus.declined`.
CANCEL_REQUEST = "cancel"

#: Written into the runs root on creation, containing ``*``, so a fit inside
#: somebody's repository does not turn up in their ``git status``. The root is
#: telemetry the package chose to write; making the user deal with it in their
#: own index would be the package spending their attention.
GITIGNORE_FILE = ".gitignore"

#: ``meta.json``'s own tag, the way every history and event line carries one.
#: Its second job is a safety interlock: :func:`prune` refuses to delete a
#: directory whose ``meta.json`` does not carry it.
RECORD_TAG = "run"

#: How long :class:`RunRecorder` may leave ``eval`` lines in the handle's
#: buffer. Every other kind flushes immediately, so a stage boundary is on disk
#: the moment it happens and only the fine-grained trajectory is at risk. The
#: durability this trades away is real — a hard kill loses the last fraction of
#: a second — and is exactly why WP-1401's liveness rests on the lock rather
#: than on the log's tail.
FLUSH_INTERVAL_SECONDS = 0.2

#: How old a run must be before :func:`prune` will consider deleting it, and
#: the reason retention is by **age and size and never by count**. "Keep the
#: newest N" is the obvious design and it is wrong here: run 21 of a
#: 200-candidate batch would delete run 1 *while the batch is still running*,
#: and a batch is one of the cases recording exists for
#: (``docs/skill/rietx/references/batch.md``). A week is generous on purpose —
#: everything inside the floor is kept however many there are, and using
#: somebody's disk is a smaller harm than deleting their evidence.
RETENTION_MIN_AGE_SECONDS = 7 * 24 * 3600.0

#: The byte ceiling :func:`prune` brings the runs root back under, oldest
#: terminal run first. At the ~200 kB a synthetic five-stage fit records this is
#: some thousands of runs; a long series' event log is larger, so the honest
#: statement is a ceiling in bytes rather than a count of anything.
RETENTION_MAX_BYTES = 1 << 30      # 1 GiB

#: What :func:`new_run_dir` names a directory, and the first of the three
#: guards :func:`prune` applies before any recursive delete. Anchored at both
#: ends: a pattern that merely *matched* somewhere would accept any name
#: containing a date.
RUN_ID_RE = re.compile(r"^\d{8}-\d{6}-\d+(?:-\d+)?$")

#: What :func:`liveness_of` answers. ``abandoned`` is a third answer and not a
#: rounding of the other two: the writer said it was running and no longer
#: holds its lock. ``unknown`` is a claim we cannot check, which is not the
#: same as a claim that nothing is happening.
LivenessState = Literal["running", "done", "failed", "cancelled", "abandoned",
                        "unknown"]


class _ReaderBase(Base):
    """A schema read off disk, never written by this package's reader.

    ``extra="allow"`` rather than the house ``extra="forbid"``, for the reason
    ``EventRecord.data`` is an open dict: a run directory outlives the version
    that wrote it, so a reader that refuses an unknown key refuses a newer
    writer's file outright. Forbidding extras is right where *this* package is
    the writer and a typo should be loud. Here it would make every future field
    a breaking change for every older reader.
    """

    model_config = ConfigDict(extra="allow", validate_assignment=True,
                              ser_json_inf_nan="strings")


class RunMeta(_ReaderBase):
    """``meta.json`` — what a run says about itself.

    :class:`RunRecorder` writes it, and every field below stays optional
    because a run directory can exist without one. A run without one is legacy,
    and :func:`discover` synthesizes what it can from the log's mtime.
    """

    #: ``"run"`` — :data:`RECORD_TAG`. Declared rather than left to
    #: ``extra="allow"`` because :func:`prune` reads it as one of its three
    #: interlocks, and an undeclared key that a delete depends on is the kind
    #: of claim WP-1076 is about.
    record: str | None = None
    #: Human label for the run row. WP-1403's writer.
    label: str | None = None
    #: Unix time the run started. WP-1403's writer. Falls back to the event
    #: log's mtime for a legacy run.
    created: float | None = None
    #: The package version that wrote the run. WP-1403's writer.
    version: str | None = None
    #: Where the fit was launched, for a human reading a list of runs.
    cwd: str | None = None
    #: How it was launched. WP-1403's writer.
    command: str | None = None


class RunStatus(_ReaderBase):
    """``status.json`` — the writer's last word on progress and state.

    The first five fields are what ``LiveSession.write_snapshot`` writes, once
    per stage. The rest are :class:`RunRecorder`'s, so a file written by one
    writer carries only half of them and every field is optional.

    :attr:`state` has **no substantive default**. A defaulted ``"running"``
    would be WP-1076's field whose empty state reads as an answer, and this one
    would read as an answer about a process that may have died months ago.
    ``None`` is the absence of a claim, and :func:`liveness_of` turns it into
    ``unknown`` rather than into ``running``.

    It is typed ``str`` and not a ``Literal`` for the reason ``extra`` is
    allowed above, and the reason matters more here than on any other field: a
    closed ``Literal`` makes a newer writer's member — a ``"paused"``, say —
    fail validation for the *whole file*, so the row would silently lose the
    stage and the Rwp it has no trouble reading. :data:`RUN_STATES` names the
    vocabulary; anything outside it reads as no claim.
    """

    # written per stage by viz.live.LiveSession.write_snapshot, today
    stage: str | None = None
    rwp: float | None = None
    gof: float | None = None
    chi2: float | None = None
    n_free: int | None = None

    # written by RunRecorder; a LiveSession's own status.json has none of them
    state: str | None = None
    pid: int | None = None
    host: str | None = None
    #: Which stage of how many, **read off** ``stage_start.index`` and never
    #: counted. A counter says "stage 6 of 5" the first time a stage releases a
    #: held phase, because that emits a second ``stage_start`` with the same
    #: index (WP-1301); and ``n_stages`` is revisable mid-run under indexing
    #: (WP-1037), so it is the writer's current claim rather than a constant.
    index: int | None = None
    n_stages: int | None = None
    #: A series member's place in its chain, copied off the ``series_*`` stamp
    #: every event of a series carries (``sequential._SeriesStream``) by
    #: :meth:`RunRecorder._observe` on ``stage_start`` (WP-1423). Absent on a
    #: single fit. Without them a run page says "stage biso" of a ramp and the
    #: one fact that matters about a series, which pattern, is in the log only.
    series_index: int | None = None
    series_n: int | None = None
    series_label: str | None = None
    series_pass: str | None = None
    #: Why the recorder stopped recording, if it did. The failure latch is not
    #: silent (WP-1076): a run that gave up says so here, and a reader seeing a
    #: ``running`` state with an ``error`` is looking at a fit that carried on
    #: perfectly well without its telemetry.
    error: str | None = None
    #: Who asked for the stop, written by :meth:`RunRecorder.poll_cancel` when a
    #: :data:`CANCEL_FILE` request caused it. **Absent is an answer here and a
    #: true one**: the fit cannot tell a human's stop from its own caller's
    #: ``token.cancel()`` and must not, both being the same cooperative read —
    #: so the record says which by whether anything wrote this. A
    #: ``cancelled`` state with no ``cancelled_by`` is the agent's own doing.
    cancelled_by: str | None = None
    #: A request this version does not know, named rather than obeyed and
    #: rather than dropped (WP-1405). The vocabulary in
    #: :data:`CANCEL_FILE` is open forwards, so an older recorder meeting a
    #: newer watcher's word declines it *visibly* — the alternative, rounding
    #: an unknown request to the file's name, would stop a fit over a word it
    #: could not read.
    declined: str | None = None
    #: Unix time of the writer's last touch. **Reported, never decisive** —
    #: see :func:`liveness_of`.
    heartbeat: float | None = None


@dataclass(frozen=True)
class Liveness:
    """Whether a run is still being written, and what says so.

    :attr:`evidence` names the rule that fired, in words, because every answer
    here is an inference and the next reader deserves to know which one.
    :attr:`heartbeat_age` is reported and never decides: an alive process is
    evidence, a clock is not.
    """

    state: LivenessState
    evidence: str
    heartbeat_age: float | None = None


@dataclass(frozen=True)
class Run:
    """One discovered run directory.

    Built only from files a writer left behind. :attr:`legacy` means no
    ``meta.json``, so :attr:`created` came from the event log's mtime.
    """

    run_id: str
    path: Path
    label: str
    created: float
    legacy: bool
    size_bytes: int
    meta: RunMeta | None = None
    status: RunStatus | None = None
    has_snapshot: bool = False
    #: A pre-WP-1402 ``fit.html`` is on disk. Reported beside
    #: :attr:`has_snapshot` rather than folded into it: a client draws the two
    #: differently, and one flag for both would hand a legacy run's page to a
    #: plotting call that wants numbers. The two are independent facts, so a
    #: directory holding both sets both — which of them to draw is the
    #: client's call, and ``rietx watch`` prefers the numbers.
    has_legacy_snapshot: bool = False

    def as_dict(self) -> dict:
        """JSON-ready row, for :mod:`rietx.watch`'s routes."""
        return {
            "run_id": self.run_id,
            "path": str(self.path),
            "label": self.label,
            "created": self.created,
            "legacy": self.legacy,
            "size_bytes": self.size_bytes,
            "has_snapshot": self.has_snapshot,
            "has_legacy_snapshot": self.has_legacy_snapshot,
            "meta": self.meta.model_dump(mode="json") if self.meta else None,
            "status": (self.status.model_dump(mode="json")
                       if self.status else None),
        }


def run_id_for(path: Path) -> str:
    """Stable, URL-safe id for a run directory.

    A digest of the resolved path rather than the path itself, for one reason
    that matters: an id is never turned back into a path. A route looks the id
    up in what :func:`discover` returned, so a request cannot name a directory
    the walk did not choose to offer, and ``..`` is not a thing an id can spell.
    """
    return hashlib.sha256(str(path).encode("utf-8")).hexdigest()[:12]


def _read_json(path: Path, model):
    """Parse one optional sidecar; a broken file reads as absent.

    A run row must survive a half-written or hand-edited sidecar, because a
    truncated ``status.json`` is exactly what a crash leaves behind, and losing
    the whole run from the list is a worse answer than losing its progress.
    """
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None
    try:
        return model.model_validate_json(text)
    except Exception:
        return None


def project_of(run_dir: str | Path) -> Path | None:
    """The project directory this run is recorded inside, or ``None``.

    **Two layouts, and both are current** (WP-1428). A recorder writes a run
    per fit at ``<name>.rex/live/<run id>``, which is what ``Project.fit``
    produces. A caller who points ``LiveSession`` straight at a project's live
    directory writes into ``<name>.rex/live`` itself, which is the pre-WP-1403
    shape and still what a hand-built directory looks like.

    One function because three callers had open-coded one branch each and two
    of them had picked different branches: :func:`_label_for` matched the
    second layout, :meth:`RunRecorder._default_label` the first, and the
    watcher's row builder the second — so the GUI command it offers was
    ``None`` for every run a real project had recorded.
    """
    run_dir = Path(run_dir)
    parent = run_dir.parent
    # `<name>.rex/live` — the run directory *is* the project's live directory
    if run_dir.name == LIVE_DIR_NAME and parent.name.endswith(PROJECT_SUFFIX):
        return parent
    # `<name>.rex/live/<run id>` — one run among the several a project recorded
    if (parent.name == LIVE_DIR_NAME
            and parent.parent.name.endswith(PROJECT_SUFFIX)):
        return parent.parent
    return None


def _label_for(run_dir: Path, root: Path) -> str:
    """A human's name for the run.

    A GUI project's log lives under ``<name>.rex/live``, where "live" names
    every project's and so names none of them. The project directory is the
    label there.
    """
    project = project_of(run_dir)
    if project is not None:
        return project.name
    try:
        rel = run_dir.relative_to(root)
    except ValueError:
        return run_dir.name
    return str(rel) if str(rel) != "." else run_dir.name


def _stat(path: Path):
    """``path.stat()`` for a regular file, and ``None`` for anything else.

    Regular-file-ness is checked here rather than by the callers, because every
    one of them is asking a question about a file's *contents*: a directory
    named ``meta.json`` has none, and its ``st_size`` is not a log's length.
    """
    try:
        stat = path.stat()
    except OSError:
        return None
    return stat if stat_mod.S_ISREG(stat.st_mode) else None


def _fingerprint(stat) -> tuple | None:
    """What a file would have to change for a cached read to be wrong.

    Inode, size and modification time to the nanosecond — the make-style
    staleness test, and its one failure mode is a filesystem whose timestamps
    are coarser than two writes of the same length. APFS and ext4 both store
    nanoseconds, so the window is not reachable by a writer flushing a status
    file. It is stated rather than hidden because a caller on some other
    filesystem inherits it.
    """
    if stat is None:
        return None
    return (stat.st_ino, stat.st_size, stat.st_mtime_ns)


def read_run(run_dir: Path, *, root: Path | None = None,
             cache: dict | None = None) -> Run | None:
    """Read one run directory, or ``None`` if it holds no event log.

    Opens **exactly two files**: ``meta.json`` and ``status.json``. The event
    log is stat'd, never opened — :func:`tail_events` opens it, on demand, from
    an offset. That budget is asserted by ``tests/test_runs.py``, because a web
    page polls this.

    ``cache`` makes that two files per **changed** run (WP-1427). A viewer
    polls, so most of a walk re-reads what it read a second ago: on a root of
    500 finished runs the two reads and their two ``model_validate_json`` calls
    were 21.8 ms of a 34.7 ms walk, once a second, about nothing. The key is
    :func:`_fingerprint` over the three files whose contents this function
    reflects, so a cached row cannot outlive a write to any of them. The
    caller owns the dict, because the caller knows when to throw it away.
    """
    run_dir = Path(run_dir)
    events_stat = _stat(run_dir / EVENTS_FILE)
    meta_path = run_dir / META_FILE
    meta_stat = _stat(meta_path)
    if events_stat is None and meta_stat is None:
        # no log: a run only if a writer left a meta.json behind
        return None
    status_stat = _stat(run_dir / STATUS_FILE)
    has_snapshot = (run_dir / SNAPSHOT_FILE).is_file()
    has_legacy = (run_dir / LEGACY_SNAPSHOT_FILE).is_file()

    signature = (_fingerprint(events_stat), _fingerprint(meta_stat),
                 _fingerprint(status_stat), has_snapshot, has_legacy,
                 None if root is None else str(root))
    if cache is not None:
        found = cache.get(run_dir)
        if found is not None and found[0] == signature:
            return found[1]

    meta = _read_json(meta_path, RunMeta)
    status = _read_json(run_dir / STATUS_FILE, RunStatus)

    created = None
    if meta is not None and meta.created is not None:
        created = float(meta.created)
    elif events_stat is not None:
        created = float(events_stat.st_mtime)
    if created is None:
        created = time.time()

    label = (meta.label if meta is not None and meta.label
             else _label_for(run_dir, root if root is not None else run_dir))
    run = Run(
        run_id=run_id_for(run_dir),
        path=run_dir,
        label=label,
        created=created,
        legacy=meta is None,
        size_bytes=events_stat.st_size if events_stat is not None else 0,
        meta=meta,
        status=status,
        has_snapshot=has_snapshot,
        has_legacy_snapshot=has_legacy,
    )
    if cache is not None:
        cache[run_dir] = (signature, run)
    return run


def _is_run_dir(entry_path: Path) -> bool:
    return ((entry_path / EVENTS_FILE).is_file()
            or (entry_path / META_FILE).is_file())


def _collect_runs(holder: Path, root: Path, out: list[Run],
                  max_runs: int, cache: dict | None = None) -> None:
    """Add every run *at* ``holder`` and every run one level inside it.

    Two directories in this package hold runs rather than being one: a
    project's ``live/`` and the ``.rietx/runs`` root. Both are reached by name
    from a parent the walk recognises, so neither needs the general descent,
    and both want the same two questions asked.

    *At* and *inside*, because the two shapes coexist on disk and must both
    stay visible. Before WP-1403 a project's ``live/`` **was** the run —
    ``LiveSession`` wrote its log straight into it — and those directories are
    still there. A recorder writes ``live/<run id>/`` instead, so that a human
    with the GUI open and an agent fitting the same project do not interleave
    one log. Asking only the second question would orphan every run written
    before this WP.
    """
    if _is_run_dir(holder) and len(out) < max_runs:
        run = read_run(holder, root=root, cache=cache)
        if run is not None:
            out.append(run)
    try:
        entries = sorted(os.scandir(holder), key=lambda e: e.name)
    except OSError:
        return
    for entry in entries:
        if len(out) >= max_runs:
            return
        try:
            if not entry.is_dir(follow_symlinks=False):
                continue
        except OSError:
            continue
        child = Path(entry.path)
        if not _is_run_dir(child):
            continue
        run = read_run(child, root=root, cache=cache)
        if run is not None:
            out.append(run)


def discover(root: str | Path, *, max_depth: int = MAX_DEPTH,
             max_runs: int = MAX_RUNS, cache: dict | None = None) -> list[Run]:
    """Every run under ``root``, newest first.

    Bounded in depth and in count, never following a symlink, pruning the
    directories in :data:`PRUNE_DIRS`. A ``*.rex`` project is descended only as
    far as its ``live/``: the rest of a project is history and exports, and
    walking it is work that can find nothing.

    A run directory is not descended either. One run is one directory, and
    anything below it belongs to that run.

    **A dotted directory is skipped, with one name excepted.** The blanket skip
    is what keeps the walk out of ``.git`` and every cache beside it, and it
    would otherwise hide the whole of :func:`run_root` — ``.rietx/runs``, where
    a fit records itself when nobody named a directory. So
    :data:`~rietx._about.STATE_DIR_NAME` is recognised by name and its
    ``runs/`` collected, exactly as ``*.rex`` is recognised and its ``live/``
    collected. Without this the acceptance of WP-1403 cannot hold: a fit in an
    empty directory would write a run that ``rietx watch``, whose default root
    is the working directory, could not list.

    ``cache`` is passed through to :func:`read_run` and **pruned here**, to the
    runs this walk found: a viewer polling a directory where runs come and go
    would otherwise hold every run it had ever seen. The walk itself is not
    cached, because the thing a walk is for is noticing a directory that was
    not there before.
    """
    root = Path(root)
    out: list[Run] = []
    # (directory, depth), walked iteratively so a deep tree cannot recurse us
    # into a stack overflow and so the count bound can stop the walk dead.
    stack: list[tuple[Path, int]] = [(root, 0)]
    seen: set[tuple[int, int]] = set()

    if _is_run_dir(root):
        run = read_run(root, root=root, cache=cache)
        if run is not None:
            return [run]

    while stack and len(out) < max_runs:
        current, depth = stack.pop()
        try:
            # a symlinked directory can point back up the tree; identity, not
            # the path, is what closes the loop
            st = current.stat()
            key = (st.st_dev, st.st_ino)
            if key in seen:
                continue
            seen.add(key)
            entries = list(os.scandir(current))
        except OSError:
            continue

        for entry in entries:
            try:
                if not entry.is_dir(follow_symlinks=False):
                    continue
            except OSError:
                continue
            child = Path(entry.path)

            if entry.name == STATE_DIR_NAME:
                # before the dot-skip below, which would otherwise hide every
                # run a fit recorded unasked
                _collect_runs(child / RUNS_DIR_NAME, root, out, max_runs,
                              cache)
                if len(out) >= max_runs:
                    break
                continue

            if entry.name in PRUNE_DIRS or entry.name.startswith("."):
                continue

            if _is_run_dir(child):
                run = read_run(child, root=root, cache=cache)
                if run is not None:
                    out.append(run)
                    if len(out) >= max_runs:
                        break
                continue

            if child.name.endswith(PROJECT_SUFFIX):
                # descend a project exactly one level, to its live/
                _collect_runs(child / LIVE_DIR_NAME, root, out, max_runs, cache)
                if len(out) >= max_runs:
                    break
                continue

            if depth < max_depth:
                stack.append((child, depth + 1))

    if cache is not None:
        alive = {run.path for run in out}
        for gone in [key for key in cache if key not in alive]:
            del cache[gone]

    out.sort(key=lambda r: r.created, reverse=True)
    return out


def _probe_lock(path: Path) -> Literal["held", "free", "unavailable"]:
    """Is another process holding ``path`` flock'd?

    ``unavailable`` is a real third answer, and conflating it with ``free`` is
    the bug worth avoiding: no lock file means no writer ever made the claim,
    while a free lock file means a writer made it and is gone.

    The probe takes a **shared** lock, and the writer's is exclusive. Two
    readers must not see each other: an exclusive probe is itself a held lock
    for as long as it runs, so two ``rietx watch`` tabs — or two threads of one
    server answering ``/api/runs`` — would each report the other's probe as a
    live writer. A shared probe conflicts with the writer and with nobody else.

    Opened read-only for the same reason it is opened at all: ``flock`` needs
    an open descriptor and not a writable one, and asking for write access
    loses the answer on a lock file this user cannot write.
    """
    if not path.is_file():
        return "unavailable"
    try:
        # by name, so JupyterLite's empty fcntl mock reads as Windows (WP-1966)
        from fcntl import LOCK_NB, LOCK_SH, LOCK_UN, flock
    except ImportError:      # pragma: no cover - Windows
        return "unavailable"
    try:
        # binary: the file's bytes are never read, only its lock, so there is
        # no text here to have an encoding
        fh = open(path, "rb")
    except OSError:
        return "unavailable"
    try:
        try:
            flock(fh.fileno(), LOCK_SH | LOCK_NB)
        except OSError:
            # somebody holds it exclusively; the kernel releases it however
            # they die
            return "held"
        flock(fh.fileno(), LOCK_UN)
        return "free"
    finally:
        fh.close()


#: ``ERROR_INVALID_PARAMETER``, what ``OpenProcess`` returns for a pid no
#: process has, which is the answer POSIX spells ``ProcessLookupError``.
_WINDOWS_NO_SUCH_PID = 87
#: ``ERROR_ACCESS_DENIED``: a process that exists and is somebody else's.
_WINDOWS_ACCESS_DENIED = 5
#: ``PROCESS_QUERY_LIMITED_INFORMATION``, the least a handle can ask for and
#: still open against a process this user does not own.
_WINDOWS_QUERY_LIMITED = 0x1000
#: The exit code ``GetExitCodeProcess`` reports for a process still running.
#: A process that really exited *with* 259 reads alive, which is the documented
#: ambiguity of this API and costs one heartbeat of staleness, never a wrong
#: ``abandoned``.
_WINDOWS_STILL_ACTIVE = 259


def _pid_alive_windows(pid: int) -> bool | None:
    """The pid rung where there is no ``kill`` (WP-1439).

    ``os.kill(pid, 0)`` does not ask this question on Windows. ``0`` **is**
    ``signal.CTRL_C_EVENT`` there, so the call goes to
    ``GenerateConsoleCtrlEvent``, which delivers a Ctrl+C to a console process
    group -- a reader interrupting the very fit it came to look at -- and
    otherwise fails ``ERROR_INVALID_PARAMETER`` for every pid that is not one
    of those groups, alive and dead alike. Reading that one winerror as "gone"
    therefore reports a running fit as ``abandoned``.

    ``OpenProcess`` is the question, and a handle plus ``GetExitCodeProcess``
    is the answer; it is what ``psutil`` asks. Every unexpected failure is
    ``None``, so the rung declines rather than guessing, exactly as the POSIX
    half does.
    """
    import ctypes
    try:
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        open_process = kernel32.OpenProcess
        # a handle is a pointer: the default ``c_int`` restype truncates it on
        # 64-bit, and a truncated handle is both a wrong answer and a leak
        open_process.restype = ctypes.c_void_p
        open_process.argtypes = [ctypes.c_ulong, ctypes.c_int, ctypes.c_ulong]
        handle = open_process(_WINDOWS_QUERY_LIMITED, 0, pid)
        if not handle:
            err = ctypes.get_last_error()
            if err == _WINDOWS_NO_SUCH_PID:
                return False
            if err == _WINDOWS_ACCESS_DENIED:
                return True      # exists, owned by somebody else
            return None
        try:
            get_exit_code = kernel32.GetExitCodeProcess
            get_exit_code.argtypes = [ctypes.c_void_p,
                                      ctypes.POINTER(ctypes.c_ulong)]
            code = ctypes.c_ulong()
            if not get_exit_code(handle, ctypes.byref(code)):
                return None
            return code.value == _WINDOWS_STILL_ACTIVE
        finally:
            close_handle = kernel32.CloseHandle
            close_handle.argtypes = [ctypes.c_void_p]
            close_handle(handle)
    except (OSError, AttributeError, ValueError):
        return None


def _pid_alive(pid: int) -> bool | None:
    """``None`` where the question cannot be answered rather than a guess.

    Subject to pid reuse, which is why this is the fallback and the held lock
    is the rule.
    """
    if pid <= 0:
        return None
    if os.name == "nt":      # pragma: no cover - POSIX
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True      # exists, owned by somebody else
    except OSError:
        return None
    return True


def liveness_of(run: Run, *, now: float | None = None) -> Liveness:
    """Whether ``run`` is still being written, by the first rule that answers.

    The order, and why each rung is where it is:

    1. **A terminal state wins.** The writer's own last word outranks every
       inference below it.
    2. **A different host reads unknown.** A claim we cannot check is not a
       claim, and a pid on another machine names one of our own processes.
    3. **The lock decides.** The writer holds ``run.lock`` flock'd for its
       life, and the kernel releases it however the writer dies, ``kill -9``
       included. Immune to pid reuse, and needing no heartbeat contract.
    4. **A free lock under a running status reads abandoned.** A third answer,
       not a rounding of the other two.
    5. **``os.kill(pid, 0)`` is the fallback** where no lock file exists.

    The heartbeat age is carried on the answer and never decides it. An alive
    process is evidence; a clock is not.

    Opens at most one file, the lock, and only when one exists. :func:`discover`
    deliberately does not call this, so a caller that wants a list pays two
    opens a run and no more.
    """
    now = time.time() if now is None else now
    st = run.status
    age = None
    if st is not None and st.heartbeat is not None:
        age = max(0.0, now - float(st.heartbeat))

    if st is not None and st.state in TERMINAL_STATES:
        return Liveness(st.state, f"the run recorded itself {st.state}", age)

    if st is not None and st.host and st.host != socket.gethostname():
        return Liveness("unknown", f"written on {st.host}, another host", age)

    probe = _probe_lock(run.path / LOCK_FILE)
    if probe == "held":
        return Liveness("running", "a process holds the run lock", age)
    if probe == "free":
        if st is not None and st.state == "running":
            return Liveness("abandoned",
                            "the status says running and the lock is free", age)
        return Liveness("unknown", "the run lock is free and no state was "
                                   "recorded", age)

    # no lock file, or no flock on this platform
    if st is not None and st.pid is not None:
        alive = _pid_alive(int(st.pid))
        if alive is True:
            return Liveness("running", f"pid {st.pid} is alive, with no lock "
                                       f"to check it against", age)
        if alive is False:
            return Liveness("abandoned", f"pid {st.pid} is gone", age)
    if run.legacy:
        return Liveness("unknown", "a legacy run: no meta.json, and no lock or "
                                   "pid to check", age)
    return Liveness("unknown", "nothing recorded a state, a lock or a pid", age)


@dataclass(frozen=True)
class EventTail:
    """A slice of an event log, and where to ask from next.

    :attr:`reset` means the log this came from is not the one the caller's
    offset counted into — truncated, or a different inode. A client clears its
    pane on it rather than renumbering silently, which is why it is a field and
    not an exception.
    """

    events: list[dict]
    offset: int
    inode: int | None
    reset: bool = False
    bad_lines: int = 0
    size: int = 0
    #: How many complete events were read and then dropped to honour a
    #: caller's ``max_events``. Zero whenever nothing was dropped, so a client
    #: that ignores it sees the field it always saw. It counts only events this
    #: call parsed: bytes beyond ``max_bytes`` are not read, and their events
    #: are not guessed at.
    skipped: int = 0
    #: Bytes between where the caller asked to read and where this read began,
    #: which is ``0`` for every ordinary call and the seek distance under
    #: ``from_end``. It is how a client says "there is more log above this"
    #: without a count of *lines*: the events in those bytes were never read,
    #: so counting them would mean reading the file to say how much of it went
    #: unread (WP-1438). It is deliberately not the absolute start, which an
    #: ordinary poll of a long log also has and which says nothing.
    skipped_bytes: int = 0


def tail_events(path: str | Path, offset: int = 0, *, inode: int | None = None,
                max_bytes: int = 4 << 20, max_events: int | None = None,
                from_end: bool = False) -> EventTail:
    """Read an event log from a byte offset, carrying a torn line forward.

    A trailing fragment is left **unparsed** and the returned offset stops
    before it, so the next call sees the line whole: a writer flushes per event,
    but a flush is not an atomic write and the last line on disk can be half of
    one. It is load-bearing rather than defensive since :class:`RunRecorder`
    started buffering ``eval`` lines (:data:`FLUSH_INTERVAL_SECONDS`).

    A bad line is counted, never raised on. One corrupt line in a log must not
    cost a viewer the other ten thousand.

    ``max_events`` keeps the **newest** that many and reports the rest in
    :attr:`EventTail.skipped`. The offset still advances over everything read,
    so a capped call loses events and never loops. It defaults to ``None``,
    which is no cap and is what every caller but a tailing viewer wants: a cap
    that dropped events by default would be this module deciding what somebody
    else's log says. The one caller that sets it is ``watch``'s console, which
    is a tail over a pane of a fixed number of lines, and where without it a
    single poll built 60 000 ``<div>``s to keep 2000 of them (997 ms on the
    main thread, WP-1427).

    ``from_end`` starts at the **end** of the log rather than at ``offset``,
    which is what a reader opening a run that has been going for a while wants
    and what every log viewer does (``kubectl logs --tail``, ``less +G``,
    CloudWatch's live tail).  Without it a cold open walks forward one
    ``max_bytes`` a poll: measured on a 7.35 MB log, the first line painted at
    0.64 s showed events 42 s old and the tail arrived at 1.99 s, and a log
    grows 1.8-4.5 MB a minute of series fitting, so an hour-long job is 27 to
    67 polls of walking (WP-1438).  It reads the last ``max_bytes`` and drops
    the partial line it lands in, so the events are whole and the returned
    offset is the end — the next poll continues from there as any other would.
    It never seeks *behind* ``offset``: a log shorter than ``max_bytes`` is
    read from where the caller already is, so the flag can only ever skip
    forward and never resend.
    """
    path = Path(path)
    try:
        stat = path.stat()
    except OSError:
        return EventTail([], offset, None, reset=False)

    reset = False
    if offset > stat.st_size:
        reset = True                      # truncated under us
    if inode is not None and inode != stat.st_ino:
        reset = True                      # replaced under us
    start = 0 if reset else max(0, int(offset))
    asked = start
    if from_end:
        # never *behind* what was asked for: a short log seeks nowhere, and a
        # seek that went back past the caller's offset would resend events it
        # already has and report a negative `skipped_bytes`
        start = max(start, stat.st_size - max_bytes)

    try:
        with open(path, "rb") as fh:
            fh.seek(start)
            chunk = fh.read(max_bytes)
    except OSError:
        return EventTail([], offset, stat.st_ino, reset=reset,
                         size=stat.st_size)

    if start > asked:
        # the seek landed mid-line, and half an event is not an event. The
        # trailing fragment is carried forward by the offset below; this one
        # belongs to a line whose start is behind us and is dropped. Only
        # where the seek actually moved: `asked` is a line boundary a previous
        # read handed back, so dropping a line there would drop a whole event.
        head = chunk.find(b"\n")
        if head == -1:
            return EventTail([], stat.st_size, stat.st_ino, reset=reset,
                             size=stat.st_size,
                             skipped_bytes=stat.st_size - asked)
        start, chunk = start + head + 1, chunk[head + 1:]

    cut = chunk.rfind(b"\n")
    if cut == -1:
        # nothing complete yet; hold the offset where it was
        return EventTail([], start, stat.st_ino, reset=reset,
                         size=stat.st_size, skipped_bytes=start - asked)
    complete, _fragment = chunk[:cut + 1], chunk[cut + 1:]

    lines = [raw for raw in complete.split(b"\n") if raw.strip()]
    skipped = 0
    if max_events is not None and len(lines) > max_events:
        # dropped before parsing, which is where the cost is: 60 000 lines of
        # JSON to keep 2000 of them is 58 000 parses nobody asked for
        skipped = len(lines) - max_events
        lines = lines[skipped:]

    events: list[dict] = []
    bad = 0
    for raw in lines:
        try:
            events.append(json.loads(raw.decode("utf-8")))
        except (ValueError, UnicodeDecodeError):
            bad += 1
    return EventTail(events, start + cut + 1, stat.st_ino, reset=reset,
                     bad_lines=bad, size=stat.st_size, skipped=skipped,
                     skipped_bytes=start - asked)


def request_cancel(run_dir: str | Path, *, who: str) -> Path:
    """Ask the fit writing ``run_dir`` to stop. Returns the file written.

    The reader's **one** verb (WP-1405), and the only write anything on this
    side of the module makes. ``rietx watch`` otherwise reads: it opens no
    project, constructs no refinement, and a user cannot click what is not
    there. Stopping a runaway is the exception, because it is the one thing a
    reader cannot do from the other side.

    Written to a sibling and renamed, for :meth:`RunRecorder._write_status`'s
    reason read backwards: the poller reads this file on a cadence and a torn
    read would be a request nobody made.

    ``who`` is the *asker*, and the server fills it rather than the client:
    a request that could name itself anything would make
    :attr:`RunStatus.cancelled_by` a field the record cannot trust.

    Writing this is not the same as it being honoured. Nothing here waits, and
    a run whose writer has already gone leaves the file lying in the directory
    doing nothing, which is why :class:`RunRecorder` deletes a stale one at
    start.
    """
    path = Path(run_dir) / CANCEL_FILE
    payload = {"request": CANCEL_REQUEST, "who": who, "t": time.time()}
    tmp = path.with_name(CANCEL_FILE + ".tmp")
    tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
    tmp.replace(path)
    return path


# ---------------------------------------------------------------------------
# The writer (WP-1403) — a fit records itself, having not been asked to
# ---------------------------------------------------------------------------

#: ``None`` means "ask the environment", which is what every fit does. Set only
#: by :func:`set_enabled`, and deliberately not a cache of the env read: one
#: ``os.environ`` lookup per *fit* is free, and a cached one would make the
#: switch depend on whether some earlier import had already asked.
_ENABLED: bool | None = None

#: One warning a process, not one a run. A batch of two hundred candidates on a
#: read-only directory would otherwise emit two hundred identical warnings, and
#: the second one tells the reader nothing the first did not.
_WARNED = False


def _off_by_env() -> bool:
    return os.environ.get(TELEMETRY_ENV, "").strip().lower() in {
        "0", "off", "no", "false"}


def enabled() -> bool:
    """Will the next fit record itself?

    Read once per *run*, never per event. The environment outranks every
    keyword, which is the whole point of :data:`~rietx._about.TELEMETRY_ENV`:
    someone who switched recording off wants it off everywhere, so there is no
    ``telemetry=True`` that argues back.
    """
    if _ENABLED is not None:
        return _ENABLED
    return not _off_by_env()


def set_enabled(flag: bool | None) -> bool | None:
    """Force recording on or off for this process; ``None`` re-reads the
    environment. Returns the previous setting, so a caller can restore it.

    Mirrors ``model.compiled.set_enabled``, and exists for the same two
    reasons: a suite needs to exercise both sides, and a caller who has hit a
    difference wants to say which side they are on.
    """
    global _ENABLED
    was, _ENABLED = _ENABLED, flag
    return was


def run_root(base: str | Path | None = None) -> Path:
    """``<base or the working directory>/.rietx/runs``, created.

    Creates the root and drops a ``.gitignore`` of ``*`` into it, so a fit
    inside somebody's repository does not turn up in their ``git status``, and
    prunes it once per process (:func:`prune`). All three only for the root *this
    package chose*: a caller who passed ``telemetry=`` named their own
    directory, and neither writing an ignore file into it nor deleting anything
    out of it is a decision this package gets to make there.
    """
    global _PRUNED
    root = (Path.cwd() if base is None else Path(base)) / STATE_DIR_NAME / RUNS_DIR_NAME
    root.mkdir(parents=True, exist_ok=True)
    marker = root / GITIGNORE_FILE
    if not marker.exists():
        marker.write_text("*\n", encoding="utf-8")
    if not _PRUNED:
        _PRUNED = True
        try:
            prune(root)
        except Exception:      # retention is telemetry; it breaks no fit
            pass
    return root


def new_run_dir(root: str | Path) -> Path:
    """Create and return a fresh run directory under ``root``.

    The name is ``<date>-<time>-<pid>``, matching :data:`RUN_ID_RE`, with a
    counter appended on the collision two fits in one second in one process
    would otherwise cause. ``exist_ok=False`` is what makes the loop correct:
    the directory is claimed by creating it, so two processes racing for the
    same second cannot both think they won it.
    """
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    stamp = f"{time.strftime('%Y%m%d-%H%M%S')}-{os.getpid()}"
    for n in range(1, 1000):
        candidate = root / (stamp if n == 1 else f"{stamp}-{n}")
        try:
            candidate.mkdir(exist_ok=False)
            return candidate
        except FileExistsError:
            continue
    raise OSError(f"no free run directory under {root} for {stamp}")


def _package_version() -> str | None:
    """The version every result is stamped with, read from its one authority.

    ``refine._VERSION``, never a second ``importlib.metadata`` lookup: this one
    stamped 887 run records 1.4.0 over 1.6.0.dev0 code where the fix to
    ``_VERSION`` alone would not have reached (WP-1456).  Imported late because
    ``refine`` imports this module, and a recorder only exists inside a fit.
    """
    try:
        from .refine import _VERSION
    except Exception:
        return None
    return _VERSION


def _warn_once(message: str) -> None:
    global _WARNED
    if _WARNED:
        return
    _WARNED = True
    warnings.warn(message, RuntimeWarning, stacklevel=3)


class _WatchedToken:
    """A cancel token that also reads :data:`CANCEL_FILE`, on a cadence.

    Duck-typed at the three verbs every consumer in the package uses —
    ``is_set()`` for the solver, ``bool()`` for ``sequential``, ``cancel()``
    and ``reset()`` for a caller — which is the same contract
    ``indexing.Deadline`` satisfies without inheriting anything either.

    **Where the probe hangs, and why it is not the event stream.** The recorder
    only gets control when something calls it, so a probe "once per cadence"
    would really be once per cadence *at an event* — and WP-1403's thinning and
    WP-1404's stage-boundary configuration both take the ``eval`` stream away,
    which would leave the probe firing once a **stage**. On the long runs this
    button exists for that is minutes. So it hangs here, on the unthinned
    evaluation boundary the solver already reads a token at, and it survives
    whatever gets written. Latency is then the cadence plus the residual
    evaluation in flight, which on a large pattern is the larger term anyway.

    **It sets the caller's token where it can, and its own where it cannot.**
    One authority per run for "stop" means the object the caller holds is the
    one that ends up set, so a GUI session whose own button and whose watcher
    both stop the same fit agree afterwards. But a token is only duck-typed
    here: ``indexing.Deadline`` answers ``is_set()`` and has no ``cancel()`` at
    all, and calling one that is not there would latch the recorder instead of
    stopping the fit. Hence the fallback event, which is never the *only*
    mechanism where a real token was passed.
    """

    __slots__ = ("_recorder", "_inner", "_event", "_next_probe")

    def __init__(self, recorder: "RunRecorder", inner=None):
        self._recorder = recorder
        self._inner = inner
        self._event = threading.Event()
        self._next_probe = 0.0

    def _probe(self) -> None:
        # monotonic, and its own clock rather than the recorder's flush time:
        # they share the *interval*, which is the constant that names this
        # cadence, and not the variable, which moves with the event stream
        now = time.monotonic()
        if now < self._next_probe:
            return
        self._next_probe = now + max(self._recorder.flush_interval, 0.0)
        self._recorder.poll_cancel()

    def stop(self) -> None:
        """Set whatever will be read — used by the recorder, not by a caller."""
        cancel = getattr(self._inner, "cancel", None)
        if callable(cancel):
            cancel()
        else:
            self._event.set()

    # -- the token surface -------------------------------------------------

    def is_set(self) -> bool:
        self._probe()
        return self._event.is_set() or (self._inner is not None
                                        and self._inner.is_set())

    def cancel(self) -> None:
        self.stop()

    def reset(self) -> None:
        self._event.clear()
        reset = getattr(self._inner, "reset", None)
        if callable(reset):
            reset()

    def __bool__(self) -> bool:
        return self.is_set()

    def __repr__(self) -> str:
        return (f"_WatchedToken(cancelled={self.is_set()}, "
                f"dir={self._recorder.dir})")


def attach_cancel(recorder: "RunRecorder | None", cancel):
    """The token a recorded fit stops through — the caller's, watched.

    ``cancel`` unchanged when nothing is recording, which is what keeps
    ``_abandon_on_cancel``'s short circuit alive for a fit that declined
    telemetry. Otherwise the run's one token, made on first ask and handed
    back to every later one — a series asks once for the chain and once per
    pattern, and both must be the same object or the chain would end and the
    next pattern start.

    **This is what ends "an ordinary fit pays nothing"**, and the price was
    measured before it was paid (WP-1405): a token makes ``_abandon_on_cancel``
    take two ``model_copy(deep=True)`` a stage, 132 µs at 2 atoms and 19.3 ms
    at 1024, plus 37 ns a residual evaluation for the wrapper the solver then
    installs. On the three-stage synthetic fit that is 1.002-1.004×, and the
    bound at 1024 atoms over ten stages is 0.19 s against a fit whose
    evaluations alone run to minutes. Lazy attachment was the alternative and
    it buys a fraction of a percent for a token that cannot be attached
    mid-stage anyway.
    """
    if recorder is None:
        return cancel
    return recorder.cancel_token(cancel)


class RunRecorder(EventStream):
    """Records a run into a directory, and never breaks the fit doing it.

    **Who asked is the whole design.** ``history/events.py`` says a callback's
    exception propagates — "a monitoring hook that crashes the refinement is a
    bug you want to see, not swallow" — and this class says a telemetry failure
    must never break a fit. Both are right, and the boundary between them is
    who asked for the code that failed:

    * a callback reached through ``events=`` is the **caller's** code, so its
      exception is theirs to see. It is invoked outside this class's try
      blocks, in :meth:`emit` and in the chain :func:`attach` builds, so this
      recorder can neither swallow it nor hold it back;
    * this recorder is code the package attached **unasked**. A fit that dies
      over a directory nobody requested is the package breaking a working call
      for its own convenience.

    So every method here runs inside one ``except BaseException`` that sets a
    one-shot latch, after which :meth:`emit` is a single attribute test. The
    latch is **not silent** (WP-1076): it records its reason in ``status.json``
    and warns once per process. ``KeyboardInterrupt`` and ``SystemExit`` are
    re-raised rather than latched, because neither is a telemetry failure — one
    is the person at the keyboard asking the fit to stop, and eating it would
    make Ctrl-C occasionally not work.

    **Buffering, and what it costs.** ``eval`` lines sit in the handle's own
    buffer and reach the disk on a :data:`FLUSH_INTERVAL_SECONDS` cadence;
    every other kind flushes as it is written. So a stage boundary is durable
    the moment it happens and a hard kill loses at most the last fraction of a
    second of the trajectory. ``EventStream.emit`` is untouched by this: a
    caller who passed a path asked for a durable log and keeps today's
    behaviour byte for byte.
    """

    def __init__(self, directory: str | Path, *, label: str | None = None,
                 command: str | None = None,
                 flush_interval: float = FLUSH_INTERVAL_SECONDS):
        super().__init__(path=None, callback=None)
        self.dir = Path(directory)
        self.flush_interval = float(flush_interval)
        #: The latch. ``None`` while recording; a sentence once it has stopped.
        self.error: str | None = None
        self._lock_fh = None
        self._last_flush = 0.0
        self._closed = False
        #: The stream :func:`attach` chained this onto, the callback it
        #: replaced, and the chain it installed — all three so that
        #: :meth:`close` can put the caller's object back the way it found it.
        self._host = None
        self._prior_callback = None
        self._chain = None
        #: This run's one token, made by :meth:`cancel_token` on the first ask.
        self._token: _WatchedToken | None = None
        # Everything but ``state`` starts absent rather than defaulted: a zero
        # Rwp reads as an answer about a fit nothing has measured (WP-1076).
        self._status: dict = {"state": "running", "pid": os.getpid(),
                              "host": socket.gethostname()}
        try:
            self.dir.mkdir(parents=True, exist_ok=True)
            self.path = self.dir / EVENTS_FILE
            # ``newline="\n"``: this is JSONL, so the line ending is the
            # format's and not the platform's (WP-1439).
            self._fh = open(self.path, "a", encoding="utf-8",
                            newline="\n")
            # the run header, as ``EventStream`` writes one for a path it
            # opens (WP-1322); one run directory is one run, but a
            # ``LiveSession``-style directory reused by name is not
            self._write_header()
            self._take_lock()
            self._clear_stale_cancel()
            self._write_meta(label, command)
            self._write_status()
        except BaseException as exc:
            self._latch(exc, "opening the run directory")

    # -- the latch ---------------------------------------------------------

    def _latch(self, exc: BaseException, what: str) -> None:
        """Stop recording, say why, and let the fit carry on."""
        if isinstance(exc, (KeyboardInterrupt, SystemExit)):
            raise exc
        if self.error is not None:
            return
        self.error = f"{what}: {type(exc).__name__}: {exc}"
        try:
            self._fh = None
            self._status["error"] = self.error
            self._write_status()
        except Exception:
            pass       # the status file is where we would have said it
        _warn_once(
            f"telemetry stopped recording this run ({self.dir}): {self.error}. "
            f"The fit is unaffected. Set {TELEMETRY_ENV}=0 to switch recording "
            f"off, or pass telemetry=False to this call.")

    # -- writing -----------------------------------------------------------

    def _take_lock(self) -> None:
        """Hold ``run.lock`` exclusively for this process's life.

        The kernel releases it however the writer dies, ``kill -9`` included,
        which is what makes ``abandoned`` a distinct answer from ``done``
        (:func:`liveness_of`) without any heartbeat contract. Failing to take
        it is not an error: a caller who pointed two fits at one directory gets
        the pid fallback instead, which is weaker and still true.
        """
        try:
            # by name, so JupyterLite's empty fcntl mock reads as Windows (WP-1966)
            from fcntl import LOCK_EX, LOCK_NB, flock
        except ImportError:      # pragma: no cover - Windows
            return
        fh = open(self.dir / LOCK_FILE, "w", encoding="utf-8",
                  newline="\n")
        try:
            flock(fh.fileno(), LOCK_EX | LOCK_NB)
        except OSError:
            fh.close()
            return
        self._lock_fh = fh

    def _default_label(self) -> str:
        """What a run is called when nobody named it.

        The working directory's name, except under a project, where it is the
        project's: ``<name>.rex/live/<run id>`` is one project among several a
        caller may drive from one directory, and the working directory names
        all of them and so names none of them. This is ``_label_for``'s rule
        for a legacy directory, applied by the writer that now supplies the
        label ``_label_for`` used to have to infer.
        """
        project = project_of(self.dir)
        return project.name if project is not None else Path.cwd().name

    def _write_meta(self, label: str | None, command: str | None) -> None:
        payload = {
            "record": RECORD_TAG,
            "label": label or self._default_label(),
            "created": time.time(),
            "version": _package_version(),
            "cwd": str(Path.cwd()),
            "command": command if command is not None else " ".join(sys.argv),
        }
        (self.dir / META_FILE).write_text(json.dumps(payload, indent=1),
                                          encoding="utf-8")

    def _write_status(self, now: float | None = None) -> None:
        """Rewrite ``status.json`` atomically.

        Written to a sibling and renamed, because a reader polls this file
        while it is being replaced and a torn read would lose the run's
        progress for that poll. The reader survives a broken sidecar anyway;
        this costs one syscall and means it never has to.
        """
        self._status["heartbeat"] = time.time() if now is None else now
        payload = {k: v for k, v in self._status.items() if v is not None}
        tmp = self.dir / (STATUS_FILE + ".tmp")
        tmp.write_text(json.dumps(payload, indent=1), encoding="utf-8")
        tmp.replace(self.dir / STATUS_FILE)

    # -- stopping (WP-1405) ------------------------------------------------

    def _clear_stale_cancel(self) -> None:
        """Delete a leftover request before this run can read it.

        Unreachable in the run-id layout, where :func:`new_run_dir` claims a
        directory by creating it. Reachable the moment anything writes two runs
        into one directory — which ``LiveSession`` does by name — and there a
        request nobody withdrew would stop the *next* fit within a cadence of
        its first evaluation, with the record blaming a watcher that had gone
        home. The insurance is one ``unlink``.
        """
        (self.dir / CANCEL_FILE).unlink(missing_ok=True)

    def cancel_token(self, inner=None) -> _WatchedToken:
        """The token this run stops through. One per run, whoever asks.

        ``inner`` is the caller's own token when they passed one, and the first
        ask is the one that binds it: a series asks once for the chain and then
        once inside every pattern's ``fit``, handing back what it was given, so
        memoising is what keeps the chain and its members reading one flag.
        """
        if self._token is None:
            self._token = _WatchedToken(self, inner)
        return self._token

    def poll_cancel(self) -> None:
        """Read :data:`CANCEL_FILE` if it is there; honour it or decline it.

        Latched like every other method here: a request the recorder cannot
        read is telemetry failing, and telemetry does not get to break a fit.
        The request is **consumed** either way — an unknown one left in place
        would be re-read and re-declined every cadence for the rest of the run.
        """
        if self.error is not None or self._closed or self._token is None:
            return
        try:
            path = self.dir / CANCEL_FILE
            if not path.exists():
                return                      # the answer on every other probe
            try:
                body = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, ValueError, UnicodeDecodeError):
                body = None                 # the name is the verb; see below
            path.unlink(missing_ok=True)
            request = (body.get("request") if isinstance(body, dict)
                       else CANCEL_REQUEST)
            if request not in (None, CANCEL_REQUEST):
                # declined by name, and said out loud: rounding an unread word
                # to the file's name would stop a fit over a request from a
                # newer watcher that this version cannot carry out
                self._status["declined"] = str(request)
                self._write_status()
                return
            who = body.get("who") if isinstance(body, dict) else None
            # The stop first, the record of it second. The request has already
            # been consumed, so a ``_write_status`` that raises here would latch
            # the recorder over a request nobody can write again — and a full
            # disk is one of the reasons somebody reaches for this button. The
            # latch below still records the reason it could not say who asked.
            self._token.stop()
            self._status["cancelled_by"] = str(who) if who else "unknown"
            self._write_status()
        except BaseException as exc:
            self._latch(exc, "reading a cancel request")

    def _observe(self, event: dict) -> None:
        """Project one event onto the status, copying and never computing.

        Every number here is read off the event that carried it, the way
        ``progress_writer`` "formats, it never computes". Two traps this
        deliberately avoids: the stage number comes off ``index`` and is never
        counted, since a stage that releases a held phase emits a *second*
        ``stage_start`` with the same index (WP-1301) and a counter would say
        "stage 6 of 5"; and ``n_stages`` is a revisable claim rather than a
        constant (WP-1037).
        """
        kind = event.get("kind")
        data = event.get("data") or {}
        if kind == "stage_start":
            if data.get("stage") is not None:
                self._status["stage"] = data["stage"]
            if data.get("index") is not None:
                self._status["index"] = int(data["index"])
            if data.get("n_stages") is not None:
                self._status["n_stages"] = int(data["n_stages"])
            # a series member's place, off the stamp and never counted: a
            # rung restart repeats a pattern, and a `both` chain visits each
            # one twice
            for key, cast in (("series_index", int), ("series_n", int),
                              ("series_label", str), ("series_pass", str)):
                if data.get(key) is not None:
                    self._status[key] = cast(data[key])
        elif kind == "stage_end":
            if data.get("stage") is not None:
                self._status["stage"] = data["stage"]
            if data.get("rwp") is not None:
                self._status["rwp"] = float(data["rwp"])
        elif kind in ("fit_end", "index_end", "solve_end"):
            for key in ("rwp", "gof"):
                if data.get(key) is not None:
                    self._status[key] = float(data[key])
            # **A series member's fit_end ends a pattern, not the run.** One
            # job is one run directory, so a 60-pattern series emits 60
            # ``fit_end``s into one recorder, and reading "done" off the first
            # of them told every reader the run had finished after pattern 1 —
            # ``liveness_of``'s first rule is that a terminal state wins, so
            # ``rietx watch`` showed a live ramp as done, and ``close`` cannot
            # correct it afterwards (it applies a state only when nothing has
            # claimed one). The ``series_*`` stamp is on the event already, so
            # this is still read off the data and never counted. A cancel is
            # the exception: it ends the *chain*, not just this pattern.
            if data.get("status") == "cancelled":
                self._status["state"] = "cancelled"
            elif "series_index" not in data and "lebail_pass" not in data:
                # a Le Bail alternation's pass ends a pass, as a series'
                # member ends a pattern (WP-1323); ``close`` says "done"
                self._status["state"] = "done"

    def _write(self, event: dict) -> None:
        self._fh.write(json.dumps(event) + "\n")
        self._observe(event)
        now = event.get("t") or time.time()
        if event.get("kind") != "eval" or now - self._last_flush >= self.flush_interval:
            self._fh.flush()
            self._write_status(now)
            self._last_flush = now
        if (event.get("kind") != "eval"
                and self._status.get("state") not in TERMINAL_STATES):
            # A stage boundary is the one place no residual is being evaluated,
            # so the token's own probe cannot fire — and recompiling a large
            # model, or building a stage report, is where a fit sits longest
            # looking like it has ignored the button. There are a handful of
            # these events in a fit, against thousands of ``eval``.
            #
            # Never once the run has claimed a terminal state, which
            # ``_observe`` does above on this same event: a request landing in
            # the last cadence of a fit that finished would otherwise set the
            # *caller's* token — the one a GUI session holds and reuses, so
            # their next fit would raise ``RefinementCancelled`` at its first
            # evaluation — and write ``cancelled_by`` beside a ``done``. A
            # series member's ``fit_end`` leaves the state ``running`` on
            # purpose (see ``_observe``), so the chain still stops here.
            self.poll_cancel()

    # -- the EventStream surface ------------------------------------------

    def emit(self, kind: str, **data) -> None:
        """Record one event, then run the caller's callback outside the guard."""
        event = {"record": "event", "v": EVENT_SCHEMA_VERSION,
                 "t": time.time(), "kind": kind, "data": data}
        if self.error is None:
            try:
                self._write(event)
            except BaseException as exc:
                self._latch(exc, "writing an event")
        # Outside, and deliberately: a callback reached through ``events=`` is
        # the caller's code and its exception is theirs to see.
        if self.callback is not None:
            self.callback(event)
        self.n_written += 1

    def record(self, event: dict) -> None:
        """Take an event somebody else's stream already emitted.

        This is the chained form :func:`attach` uses when the caller passed an
        ``events=`` of their own: their stream writes their file, and this
        writes ours. The dict arrives built, so there is no second ``t`` and
        the two logs agree about when everything happened.
        """
        if self.error is not None or self._closed:
            return
        try:
            self._write(event)
        except BaseException as exc:
            self._latch(exc, "writing an event")

    def write_snapshot(self, model, table, outcome, stage_name: str) -> None:
        """The per-stage picture, as ``viz.snapshot`` writes it for a live view.

        Imported here rather than at module scope so a viewer importing this
        module pays nothing for numbers it is not going to draw.

        This is also where WP-1402's open question is answered. ``refine.py``
        runs ``for sink in sinks: sink.write_snapshot(...)`` unguarded, which is
        right for a sink the *caller* passed — a live view they asked for should
        fail loudly — and wrong for this one. The two need no separate code
        path, because the latch covers this method like every other: the
        recorder absorbs its own full disk, and that loop does not move.
        """
        if self.error is not None:
            return
        try:
            from .viz.snapshot import write_snapshot as _write_snapshot
            payload = _write_snapshot(self.dir, model, table, outcome, stage_name)
            # from the payload, never recomputed: one stage has one Rwp, and a
            # second computation of it is a second answer waiting to disagree
            stats = payload["statistics"]
            self._status.update(stage=payload["stage"], rwp=stats["rwp"],
                                gof=stats["gof"], chi2=stats["chi2"],
                                n_free=stats["n_free"])
            self._write_status()
        except BaseException as exc:
            self._latch(exc, "writing a stage snapshot")

    def write_summary(self, result) -> None:
        """WP-1302's termination view, once, after the result exists.

        ``str(result)`` and never ``ref.summary()``: that call builds a whole
        ``FitReport``, which is the expensive half of it and WP-1335's subject.
        A cancelled or failed run has no result and so gets no summary, and
        that absence is not an error.
        """
        if self.error is not None or result is None:
            return
        try:
            (self.dir / SUMMARY_FILE).write_text(str(result), encoding="utf-8")
        except BaseException as exc:
            self._latch(exc, "writing the termination view")

    def close(self, state: str | None = None) -> None:
        """Flush, record a terminal state, and release the lock. Idempotent.

        ``state`` is applied only if nothing has claimed one yet, so a caller's
        ``close("failed")`` in an exception path cannot overwrite the
        ``cancelled`` a ``fit_end`` already recorded. Idempotence is what lets
        the exception path and the ``finally`` both call this.
        """
        if self._closed:
            return
        self._closed = True
        try:
            if self._status.get("state") == "running":
                self._status["state"] = state or "done"
            if self._fh is not None:
                self._fh.flush()
                self._fh.close()
                self._fh = None
            if self.error is None:
                self._write_status()
        except BaseException as exc:
            self._latch(exc, "closing the run")
        finally:
            if self._lock_fh is not None:
                try:
                    self._lock_fh.close()      # the kernel drops the flock
                except Exception:
                    pass
                self._lock_fh = None
            self._detach()

    def _detach(self) -> None:
        """Put the stream :func:`attach` chained this onto back as it was.

        A recorder outlives its run only as a reference on somebody else's
        object, and leaving it there costs twice: the stamp makes the *next*
        fit on that stream decline to record at all, and the chained callback
        feeds that fit's events to a closed recorder, which latches an error
        into the finished run's ``status.json`` and warns about telemetry that
        never failed. Both were reachable from one ordinary shape — a caller
        reusing one ``EventStream`` for two fits.
        """
        host, chain, prior = self._host, self._chain, self._prior_callback
        self._host = self._chain = self._prior_callback = None
        if host is None:
            return
        if getattr(host, _STAMP, None) is self:
            try:
                delattr(host, _STAMP)
            except AttributeError:      # pragma: no cover - a class attribute
                pass
        if getattr(host, "callback", None) is chain:
            host.callback = prior


def _dir_size(path: Path) -> int:
    """Bytes in one run directory, one level deep. Unreadable reads as zero."""
    total = 0
    try:
        for entry in os.scandir(path):
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry.stat(follow_symlinks=False).st_size
            except OSError:
                continue
    except OSError:
        return 0
    return total


def _is_prunable(child: Path, root: Path, now: float,
                 min_age_seconds: float) -> float | None:
    """The run's ``created`` time if it may be deleted, else ``None``.

    Four questions, and every one of them can only ever *withhold* permission:

    * the name is a run id this package wrote (:data:`RUN_ID_RE`);
    * ``meta.json`` is there and carries :data:`RECORD_TAG`. **A legacy
      directory is never pruned** — nobody agreed to the deletion of a run
      written before there was a writer to agree on their behalf;
    * the run reached a terminal state. A ``running`` status, or none at all,
      is a run that may still be being written;
    * it is older than ``min_age_seconds``.
    """
    if not RUN_ID_RE.match(child.name):
        return None
    if child.parent != root:
        return None
    meta = _read_json(child / META_FILE, RunMeta)
    if meta is None or meta.record != RECORD_TAG or meta.created is None:
        return None
    status = _read_json(child / STATUS_FILE, RunStatus)
    if status is None or status.state not in TERMINAL_STATES:
        return None
    if (now - float(meta.created)) < min_age_seconds:
        return None
    return float(meta.created)


def prune(root: str | Path, *, max_bytes: int = RETENTION_MAX_BYTES,
          min_age_seconds: float = RETENTION_MIN_AGE_SECONDS,
          now: float | None = None) -> list[Path]:
    """Bring the runs root under ``max_bytes``, oldest terminal run first.

    Returns the directories removed. **By age and size, never by count** — see
    :data:`RETENTION_MIN_AGE_SECONDS` for the batch this rule exists to
    survive.

    The root's whole size decides *whether* to prune, including directories
    that may not be deleted; only :func:`_is_prunable` decides *what*. So a root
    filled with runs too young to touch **warns and keeps**: using somebody's
    disk is better than deleting their evidence, and a silent cap on either
    would be worse than both.

    Every ``rmtree`` here is guarded three times over, because a recursive
    delete is the one thing in this track that can destroy data and the guards
    are cheap. Two of the three are re-asked immediately before the call rather
    than trusted from the scan, since the scan and the delete are not one
    atomic act.
    """
    root = Path(root)
    now = time.time() if now is None else now
    try:
        entries = [Path(e.path) for e in os.scandir(root)
                   if e.is_dir(follow_symlinks=False)]
    except OSError:
        return []

    sizes = {child: _dir_size(child) for child in entries}
    total = sum(sizes.values())
    if total <= max_bytes:
        return []

    candidates = []
    for child in entries:
        created = _is_prunable(child, root, now, min_age_seconds)
        if created is not None:
            candidates.append((created, child))
    candidates.sort()

    removed: list[Path] = []
    for _, child in candidates:
        if total <= max_bytes:
            break
        if _guarded_rmtree(child, root):
            total -= sizes.get(child, 0)
            removed.append(child)

    if total > max_bytes:
        _warn_once(
            f"the run directory {root} holds {total} bytes, over the "
            f"{max_bytes}-byte retention ceiling, and nothing in it is both "
            f"finished and older than {min_age_seconds / 86400:.0f} days. "
            f"Keeping it: deleting a run somebody may still want is worse than "
            f"using the disk. Delete what you do not need, or raise the "
            f"ceiling.")
    return removed


def _guarded_rmtree(child: Path, root: Path) -> bool:
    """Delete one run directory, or refuse and say nothing happened.

    The three guards, asked here and not only at the scan: the name is a run id
    this package wrote, the directory is a **direct child** of the root the
    recorder itself chose, and it carries a ``meta.json`` with
    :data:`RECORD_TAG`. Nothing else in this package deletes a tree, so these
    are written where the call is rather than anywhere they could drift from
    it.
    """
    import shutil

    if not RUN_ID_RE.match(child.name):
        return False
    if child.parent != root:
        return False
    if child.is_symlink() or not child.is_dir():
        return False
    meta = _read_json(child / META_FILE, RunMeta)
    if meta is None or meta.record != RECORD_TAG:
        return False
    try:
        shutil.rmtree(child)
    except OSError:
        return False
    return True


#: Has this process already pruned its derived root? Once, not once per fit: a
#: batch of two hundred candidates in one process should pay the walk once.
#: Measured on ``[dev]`` / macOS arm64 over six-file run directories: 0.2 ms at
#: 10 runs, 2.2 ms at 100, 27.6 ms at 1000 (197 MB) — so the walk stays under a
#: tenth of a second right up to the ceiling, and a fit pays it once.
_PRUNED = False


#: Marks a stream as already carrying a recorder. One job is one run directory,
#: and a 60-pattern series runs 60 fits for one job, so the series runner
#: attaches at its own level and every fit below it finds this stamp and
#: declines.
_STAMP = "_rietx_run_recorder"


def recorder_of(stream) -> "RunRecorder | None":
    """The recorder attached anywhere in ``stream``'s chain, or ``None``.

    **The stamp has to be looked for through wrappers, not only on the object
    handed in.** ``sequential`` builds a *fresh* ``_SeriesStream`` per pattern
    around the one stream the series owns, so a check on identity alone would
    see an unstamped object sixty times and make sixty run directories for one
    job. The walk follows ``_inner``, which is the wrapping convention in this
    package, and carries a seen-set because a cycle here would hang a fit —
    which is the one thing telemetry must never do.

    It answers the recorder rather than a yes, because the second caller wants
    the object: a wrapper that forwards ``write_snapshot`` has to reach the
    recorder chained onto its inner stream, or a series whose caller passed an
    ``events=`` path records a run with no picture in it.
    """
    seen: set[int] = set()
    while stream is not None and id(stream) not in seen:
        found = getattr(stream, _STAMP, None)
        if found is not None:
            return found
        seen.add(id(stream))
        stream = getattr(stream, "_inner", None)
    return None


def _already_recorded(stream) -> bool:
    return recorder_of(stream) is not None


def attach(stream, events, *, telemetry=None, project_hint=None,
           label: str | None = None) -> "RunRecorder | None":
    """Give a run a recorder, or answer ``None`` and leave the fit alone.

    ``None`` when recording is switched off, when the caller passed
    ``telemetry=False``, or when ``stream`` already carries one.

    The three composition cases, and the identity that must survive all of
    them — ``fit`` closes its stream only ``if stream is not events``, which is
    why ``sequential._SeriesStream`` is a *subclass* and not a wrapper:

    ==============================  ====================================
    the caller passed               what happens here
    ==============================  ====================================
    nothing                         the recorder *is* the stream
    a path or a callable            chained onto the normalised stream's
                                    ``.callback``, exactly as
                                    ``_attach_progress`` chains
                                    ``progress_writer``
    an ``EventStream``              the same, with the caller's object
                                    handed back untouched by identity
    ==============================  ====================================

    Where the directory comes from, first hit winning: an explicit
    ``telemetry=``; a ``project_hint`` (what ``Project.fit`` sets, and the
    derived fallback for a bare ``fit()`` on a project-built ``Refinement``);
    else :func:`run_root` under the working directory. Each is a *root*, and
    the run is a fresh ``<run id>`` directory inside it — which is what keeps an
    agent fitting a project and a human with the GUI open on it from
    interleaving one log.

    The recorder goes **first** in the callback chain. It cannot raise, having
    a latch, so a caller's hook still runs immediately after; and a caller's
    hook that *does* raise then leaves a complete log behind rather than
    costing the run the telemetry it was recording. That ordering is this
    function's choice and not a contract.

    ``label`` names the run, and is the one thing here a **caller** supplies
    (WP-1431), so it is the one thing that can arrive as the wrong type. It is
    checked at this funnel and raises, which "telemetry never breaks a fit"
    does not cover: that rule is about the *environment* — an unwritable
    directory, a full disk — and this is a programming error at the call, in
    the same place and for the same reason the root and the directory are
    chosen outside the recorder's latch. Left unchecked it is silent and
    costs the record: ``_write_meta`` writes raw JSON, so a list lands in
    ``meta.json`` as an array, ``RunMeta`` then refuses the whole file, and
    ``read_run`` reads the run back as *legacy* — a derived name and no
    tooltip, from a run that recorded perfectly. The hazard is real and one
    letter wide: ``SequentialRefinement.fit`` has a ``labels=`` too, the
    series members' names, beside this ``label=`` for the job.

    Checked **before** the switch-off guard below, so a caller's suite running
    with ``RIETX_TELEMETRY=0`` catches the mistake that would otherwise
    surface only on a machine where recording is on.
    """
    if label is not None and not isinstance(label, str):
        raise TypeError(
            f"label must be a string naming this run, not "
            f"{type(label).__name__}. (A series names its *members* with "
            f"labels=, a sequence; label= names the whole job.)")
    if not enabled() or telemetry is False:
        return None
    if _already_recorded(stream):
        return None
    # **Inside the guard, all of it.** Choosing the root and making the
    # directory happen before a ``RunRecorder`` exists, so its latch cannot
    # cover them — and a read-only working directory raises here, which would
    # break a fit over telemetry nobody asked for. Measured: without this,
    # ``telemetry=`` pointing anywhere unwritable took the fit down with it.
    try:
        root = (Path(telemetry) if telemetry is not None
                else Path(project_hint) if project_hint is not None
                else run_root())
        directory = new_run_dir(root)
    except (KeyboardInterrupt, SystemExit):
        raise
    except BaseException as exc:
        _warn_once(
            f"telemetry could not open a run directory "
            f"({type(exc).__name__}: {exc}). The fit is unaffected. Set "
            f"{TELEMETRY_ENV}=0 to switch recording off, or pass "
            f"telemetry=False to this call.")
        return None
    recorder = RunRecorder(directory, label=label)
    if stream is None:
        setattr(recorder, _STAMP, recorder)
        return recorder

    prior = stream.callback

    def _combined(event: dict, _prior=prior, _rec=recorder) -> None:
        _rec.record(event)
        if _prior is not None:
            _prior(event)

    stream.callback = _combined
    setattr(stream, _STAMP, recorder)
    # remembered so ``close`` can undo exactly this, and only while it is
    # still what is there — see :meth:`RunRecorder._detach`
    recorder._host = stream
    recorder._prior_callback = prior
    recorder._chain = _combined
    return recorder


def _format_table(runs: list[Run], root: Path) -> str:
    """The text twin of the ``rietx watch`` list, and it answers the same two
    questions the same way (WP-1424).

    An R factor is a percentage wherever a person reads one, here as on the
    page and in the GUI; the fraction is the report layers' form, because they
    are quoted into prose. And a run is named by what tells it from its
    neighbours: a batch driven from one directory gives every run the same
    label, so the series label goes in the column where there is one. The page
    does this in ``rowName`` (``watch/static/watch-core.mjs``). The rule is
    stated twice because a process boundary runs through it — the page gets
    these rows as JSON and cannot import python — so a change to one is a
    change to both.
    """
    rows = [("STATE", "RUN", "STAGE", "RWP", "SIZE", "ID")]
    for run in runs:
        live = liveness_of(run)
        st = run.status
        series = st.series_label if st else None
        rows.append((
            live.state,
            series or run.label,
            (st.stage if st and st.stage else "—"),
            (f"{st.rwp * 100:.2f}%" if st and st.rwp is not None else "—"),
            f"{run.size_bytes / 1024:.0f}k",
            run.run_id,
        ))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    lines = ["  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
             for row in rows]
    head = f"scanned {root}"
    tail = f"{len(runs)} run(s)" if runs else "no runs found"
    return "\n".join([head, "", *lines, "", tail])


def main(argv: list[str] | None = None) -> int:
    """``python -m rietx.runs [DIR]`` — the walk, without a browser."""
    args = list(sys.argv[1:] if argv is None else argv)
    root = Path(args[0]).resolve() if args else Path.cwd()
    runs = discover(root)
    print(_format_table(runs, root))
    return 0


if __name__ == "__main__":       # pragma: no cover - module entry point
    raise SystemExit(main())
