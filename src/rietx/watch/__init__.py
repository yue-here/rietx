"""``rietx watch`` — a window into the refinements under a directory.

With no argument it scans the working directory and lists every run beneath it,
live ones and finished ones together, and opening one shows its plot and its
event log. With a directory argument that *is* a run it opens straight onto
that run, so ``rietx watch live/`` keeps working exactly as it did.

This module is **transport only**, the split ``gui/server.py`` declares for
itself. Finding runs, deciding whether one is still being written and tailing
its log are :mod:`rietx.runs`, which has no HTTP in it and which
``gui/session.py`` can import when it attaches to a foreign run.

**The page is files, in** ``static/`` (WP-1430): an ``index.html``, a
stylesheet and two ES modules, served by :meth:`_Handler._static`. It was a
python string until seven WPs queued up against it, at which point the string
was costing an editor, a unit test and every merge. ``watch-core.mjs`` is the
half that touches no DOM and the suite runs it through ``node --test``;
``watch.mjs`` owns the document. What the page cannot know about this build
travels on the first ``/api/runs`` (:func:`_page_constants`). The picture is
drawn by the chart module every browser page shares, served with its uPlot
out of ``viz/static`` (:data:`rietx.viz.chart.CHART_FILES`, WP-1461).

**The watcher has two verbs** (WP-1405, WP-1428). Everything else reads: it
opens no project and constructs no refinement. ``POST /api/run/<id>/cancel``
writes :data:`~rietx.runs.CANCEL_FILE` into a directory the walk already
offered, and the fit's own token is what acts on it. ``POST
/api/run/<id>/gui`` spawns a GUI on a throwaway copy of the run's project.
``--read-only`` serves without either, for a reader who is not the person who
should be stopping things.

**Neither verb touches the project the fit is writing.** Stopping writes into
the *run* directory. The GUI launch copies the project first and opens the
copy, because there is no read-only way to open one and two appenders on one
``history.jsonl`` is the interleaving WP-1403 separated the run directories to
avoid. The copy is frozen at the click and never follows the fit.

**A click here raises in another process.** That is the sharpest fact in this
module: a fit that did not ask to be cancellable is cancellable, and a script
that does not catch ``RefinementCancelled`` prints a traceback. It is why the
button takes two clicks, why the dialog says so in as many words, and why it
has no keyboard shortcut.

Run the refinement in one process::

    ref.fit(data, events=LiveSession("live/"))

and the viewer in another::

    rietx watch                  # every run under the working directory
    rietx watch live/            # straight onto one
"""

from __future__ import annotations

import functools
import hashlib
import http.server
import json
import os
import subprocess
import sys
import threading
import time
import urllib.parse
from pathlib import Path

from .. import runs as runs_mod
from .._about import DIST_NAME, PROJECT_SUFFIX
from ..viz import theme as theme_mod
from ..viz.chart import CHART_DIR, CHART_FILES

#: The page, as files in the package — ``gui/server.py``'s ``STATIC_DIR`` one
#: rank down (WP-1430). A page quoted inside python is a page no editor lints,
#: no test imports and no merge resolves; this one had reached 90 lines of CSS
#: and 520 of javascript with ``node --check`` as its whole check.
STATIC_DIR = Path(__file__).parent / "static"

#: What the page is made of, and what each file is served as. A fixed table
#: rather than a directory served whole: four names cannot be walked out of,
#: and the static fallback below is rooted at somebody's run directory rather
#: than here.
STATIC_FILES = {
    "index.html": "text/html; charset=utf-8",
    "watch.css": "text/css; charset=utf-8",
    "watch.mjs": "text/javascript; charset=utf-8",
    "watch-core.mjs": "text/javascript; charset=utf-8",
}

#: How long the GUI launch waits for the spawned process to name its port
#: (WP-1428). Three launches on a 48 kB project took 0.58-0.89 s, of which the
#: copy is 1.1 ms and the rest is the interpreter; the ceiling is for a project
#: whose pattern file is large enough that ``copytree`` is the term that
#: matters. Load moves the interpreter term far more than size does: the same
#: launch took 11.7-14.9 s on a Mac at load average 54-91 (WP-2145). An
#: unbounded wait would hold a request thread for the life of the server every
#: time a spawn went wrong.
GUI_BOOT_TIMEOUT = 60.0

#: Every GUI this watcher spawned. Held only so the :class:`subprocess.Popen`
#: is not collected, which would close the pipe under a child that is still
#: running. Nothing reaps them: a spawned GUI outlives the watcher on purpose
#: (``start_new_session``), the same way a scratch copy outlives its GUI.
_SPAWNED: list[subprocess.Popen] = []


def _page_constants() -> dict:
    """What the page cannot know about the build serving it.

    These were ``@TOKEN@`` substitutions into the page's text while the page
    was a python string, which a file cannot carry. A literal ``.rex`` in the
    page would be invisible to every test in the suite (``_about.py``).

    ``theme`` is the *choice* and not a resolved answer, and it rides here
    rather than being read once at boot because it is the one thing on this
    page a person changes while the page is open: the GUI writes it
    (WP-1044), every poll carries it, and the page re-stamps without a reload
    (WP-1429).  Every colour a *curve* is drawn in left this payload with that
    WP — those are custom properties the page reads off its own root element,
    so one stylesheet answers for all three surfaces.

    ``ticks`` rode here too until WP-1438 and no longer does.  The question
    that kept it was what a shared *categorical* palette should be, the
    `--plot-*` tokens each naming one role; the answer is four Okabe-Ito
    colours in `--phase-0…3`, which this page now reads off its root element
    like every other colour.  The payload could not have answered it well in
    any case: it sent one list whatever the theme, so a light page drew its
    tick rows in the dark set.
    """
    return {"suffix": PROJECT_SUFFIX, "dist": DIST_NAME,
            "theme": theme_mod.theme_choice(),
            # the three the page draws its control from, so the glyph and the
            # sentence under the pointer are the GUI's and not a second copy
            "themes": [{"choice": choice,
                        "glyph": theme_mod.THEME_GLYPHS[choice],
                        "title": theme_mod.THEME_TITLES[choice]}
                       for choice in theme_mod.THEME_CHOICES]}


#: How long a walk's result stands before the next request pays for another.
#: Shorter than the page's poll, so an open tab still sees a new run within a
#: poll or two, and short enough that a human refreshing by hand never waits.
INDEX_TTL_SECONDS = 1.0

#: The hosts a request carrying the one verb may claim to come from — the same
#: set ``gui/server.py`` keeps, and kept separately for the same reason the two
#: servers are separate modules. Binding ``127.0.0.1`` is not on its own enough:
#: any page the reader happens to have open can send a cross-origin ``POST``
#: with no preflight, and a hostile domain whose DNS answers ``127.0.0.1``
#: becomes same-origin, at which point the run ids are readable too.
_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})


class _RunIndex:
    """One walk shared by the requests that arrive together.

    The detail page asks for the run and then for its events, so an uncached
    :func:`~rietx.runs.discover` would walk the whole tree twice per poll, per
    open tab — and the walk is the expensive half of every route here. One
    shared result behind a lock is also what stops a burst of parallel requests
    on :class:`~http.server.ThreadingHTTPServer` from starting a walk each.
    """

    def __init__(self, root: Path, ttl: float = INDEX_TTL_SECONDS):
        self.root = root
        self.ttl = ttl
        self._lock = threading.Lock()
        self._runs: list | None = None
        self._at = 0.0
        # Runs already read, keyed on what their files say about themselves
        # (WP-1427). The TTL above bounds how often the tree is *walked*; this
        # bounds what each walk re-reads, which is the larger half: on 500
        # finished runs the two sidecar reads and their two parses were 21.8 ms
        # of a 34.7 ms walk, once a second, about nothing. `discover` prunes it
        # to what the walk found, so a run that goes away leaves no entry.
        self._cache: dict = {}

    def runs(self) -> list:
        with self._lock:
            now = time.monotonic()
            if self._runs is None or now - self._at >= self.ttl:
                self._runs = runs_mod.discover(self.root, cache=self._cache)
                self._at = now
            return self._runs


class _Handler(http.server.SimpleHTTPRequestHandler):
    """Routes, and a static fallback rooted at the scanned directory.

    The fallback is what keeps ``rietx watch live/`` working for anything that
    already links at ``fit.html`` or ``events.jsonl`` by their bare names — a
    run recorded before WP-1402 included.
    """

    def __init__(self, *args, scan_root: Path, index: _RunIndex,
                 allow_cancel: bool = True, allow_gui: bool = True, **kwargs):
        # set before super().__init__, which handles the request inline
        self.scan_root = scan_root
        self.index = index
        self.allow_cancel = allow_cancel
        # A second flag rather than a second reading of the first, because the
        # two verbs are not the same act: one raises in somebody else's fit,
        # the other starts a window onto a copy. `--read-only` clears both
        # today, which is what a reader who should not be stopping things
        # wants, and the names stay true if that ever stops being one flag.
        self.allow_gui = allow_gui
        self._marks: list[tuple[str, float]] = []
        super().__init__(*args, **kwargs)

    def _timed(self, name: str, call):
        """Run ``call``, and remember what it cost this request.

        The marks go out as ``Server-Timing``, which is the documented header
        for exactly this (MDN). A browser shows it in the network panel beside
        the request it belongs to, and a python test reads it off the response
        with no profiler and no clock of its own. That second reader is why the
        phases are named for what they do rather than for the function that
        does it: ``walk`` stays ``walk`` when :class:`_RunIndex` changes shape.
        """
        started = time.perf_counter()
        try:
            return call()
        finally:
            self._marks.append((name, (time.perf_counter() - started) * 1e3))

    def _send(self, body: bytes, content_type: str, status: int = 200,
              etag: str | None = None) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if etag is not None:
            self.send_header("ETag", etag)
        if self._marks:
            self.send_header("Server-Timing", ", ".join(
                f"{name};dur={ms:.3f}" for name, ms in self._marks))
        self.end_headers()
        self.wfile.write(body)

    def _json_or_304(self, payload) -> None:
        """``/api/runs``'s answer, or the two header lines saying it has not
        moved (WP-1427).

        The ``ETag`` is a digest of the body, so the walk and the rows are paid
        for either way: what a 304 saves is the wire and the page's own parse
        and patch, once a second for as long as a tab is open. On a batch of
        200 finished runs that is 229 kB a poll, which is 6.6 GB over an
        overnight watch.

        The header is read here rather than left to the browser because
        ``no-store`` is right for this route and forbids the browser keeping
        the copy it would revalidate. Reading it ourselves also lets the page
        see the 304 and skip patching, which a transparent revalidation would
        not: fetch would hand it the stored body and the page would do the work
        again.
        """
        body = self._timed(
            "serialize", lambda: json.dumps(payload).encode("utf-8"))
        etag = f'"{hashlib.sha256(body).hexdigest()[:32]}"'
        if self.headers.get("If-None-Match") == etag:
            self._send(b"", "application/json; charset=utf-8", status=304,
                       etag=etag)
            return
        self._send(body, "application/json; charset=utf-8", etag=etag)

    def _static(self, name: str) -> None:
        """One of the page's own files or its chart's, out of the installed package.

        Read per request: the seven of them are 188 kB and a page fetches
        each once, so nothing here is on a path that runs per stage.
        ``no-store`` comes from :meth:`_send` and is wanted — a reader who
        restarts the watcher after an upgrade must not be served the old
        script out of their own cache.
        """
        if name in CHART_FILES:
            self._send((CHART_DIR / name).read_bytes(), CHART_FILES[name])
            return
        self._send((STATIC_DIR / name).read_bytes(), STATIC_FILES[name])

    def _json(self, payload, status: int = 200, *, etag: bool = False) -> None:
        if etag:
            self._json_or_304(payload)
            return
        body = self._timed(
            "serialize", lambda: json.dumps(payload).encode("utf-8"))
        self._send(body, "application/json; charset=utf-8", status)

    def _origin_ok(self) -> bool:
        """Whether a write may be honoured — ``gui/server.py``'s check, here.

        Only the verb asks. Reading is served to whoever reaches the port, as
        it was before WP-1405, and the reason this exists is that the verb
        raises in another process: without it, any page the reader has open
        could ``POST`` ``/api/run/<id>/cancel`` and stop an overnight
        refinement. A same-origin fetch sends no ``Origin``, so an absent
        header is not a failure; ``Host`` is checked as well because ``Host``
        alone is what DNS rebinding defeats.
        """
        for header in ("Origin", "Referer"):
            value = self.headers.get(header)
            if not value:
                continue
            if (urllib.parse.urlparse(value).hostname or "") not in _ALLOWED_HOSTS:
                return False
        host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
        return host in _ALLOWED_HOSTS

    def handle_one_request(self):  # noqa: D102 - http.server API
        # A keep-alive connection serves many requests through one handler
        # object, and the header is a fact about one of them.
        self._marks = []
        super().handle_one_request()

    def _runs(self) -> list:
        return self._timed("walk", self.index.runs)

    def _find(self, run_id: str):
        """An id is looked up in what the walk offered, never decoded into a
        path. That is why a request cannot name a directory we did not choose
        to serve."""
        for run in self._runs():
            if run.run_id == run_id:
                return run
        return None

    def _row(self, run) -> dict:
        live = runs_mod.liveness_of(run)
        row = run.as_dict()
        # `heartbeat_age` is not here, and its absence is the point (WP-1427).
        # It is `now - status.heartbeat`, so it moved on every poll and made
        # every idle answer a different one — which is the whole of what an
        # `ETag` on this route has to decide. Nothing read it: not this page,
        # not the GUI. The heartbeat it derives from is in `status` already,
        # and a client wanting an age can subtract.
        row["liveness"] = {"state": live.state, "evidence": live.evidence}
        # the picture is rewritten per stage, so the page needs to know when to
        # redraw rather than sit on the one it opened with.  The mtime is of
        # whichever file this run actually has: a legacy run's is its page's.
        name = (runs_mod.SNAPSHOT_FILE if run.has_snapshot
                else runs_mod.LEGACY_SNAPSHOT_FILE)
        try:
            row["snapshot_mtime"] = (run.path / name).stat().st_mtime
        except OSError:
            row["snapshot_mtime"] = None
        # the command a reader would type, beside the button that saves them
        # typing it. Non-null is also the page's test for whether this run can
        # be opened at all, so it is one question asked once.
        project = runs_mod.project_of(run.path)
        row["gui_command"] = None
        if project is not None:
            # the path as typed from where the scan started, not the bare name:
            # a project one directory down is not `rietx gui sample.rex` from
            # here
            try:
                where = os.path.relpath(project, self.scan_root)
            except ValueError:                      # pragma: no cover - Windows
                where = str(project)
            # `--scratch`, always: the run this row is about is *writing* that
            # project, and there is no read-only way to open one — `Project.open`
            # appends a head annotation before any verb runs (WP-1428). Without
            # the flag this row hands a reader the one command that puts a
            # second appender on a `history.jsonl` a fit is still growing.
            row["gui_command"] = f"{DIST_NAME} gui --scratch {where}"
        return row

    def do_GET(self):  # noqa: N802 - http.server API
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        query = urllib.parse.parse_qs(parsed.query)

        if path in ("/", "/index.html"):
            self._static("index.html")
            return

        # the page's own files, before the fallback: a run directory holding a
        # `watch.css` of its own does not get to replace the page's
        name = path.lstrip("/")
        if name in STATIC_FILES or name in CHART_FILES:
            self._static(name)
            return

        if path == theme_mod.CSS_ROUTE:
            # generated rather than served off disk: `viz/theme.py` is the
            # authority and `gui/src/tokens.css` is the copy, not the reverse
            self._send(theme_mod.tokens_css().encode("utf-8"),
                       theme_mod.CSS_CONTENT_TYPE)
            return

        if path == "/api/runs":
            found = self._runs()
            single = (found[0].run_id
                      if len(found) == 1 and found[0].path == self.scan_root
                      else None)
            self._json({"root": str(self.scan_root),
                        "single_run_id": single,
                        # the page draws no button under --read-only; the route
                        # refuses anyway, and a button that only ever 403s
                        # would be a worse answer than no button
                        "can_cancel": self.allow_cancel,
                        # the same courtesy for the other verb. Whether a
                        # *given* run can be opened is `gui_command` on its own
                        # row, which is non-null exactly for a run in a
                        # project's live directory (WP-1428).
                        "can_open_gui": self.allow_gui,
                        # read once, at boot, and 299 B of every poll after
                        # that — 1 % of a 41-run answer, whose rows are 735 B
                        # each. A route of its own would save that and make a
                        # second authority for what this server is.
                        "page": _page_constants(),
                        "runs": self._timed(
                            "rows", lambda: [self._row(r) for r in found])},
                       etag=True)
            return

        parts = [p for p in path.split("/") if p]
        if len(parts) >= 3 and parts[0] == "api" and parts[1] == "run":
            run = self._find(parts[2])
            if run is None:
                self._json({"error": "no such run"}, status=404)
                return
            rest = parts[3] if len(parts) > 3 else ""
            if rest == "":
                self._json(self._row(run))
                return
            if rest == "events":
                def _int(name):
                    try:
                        return int(query.get(name, [""])[0])
                    except (TypeError, ValueError):
                        return None

                def _limit():
                    value = _int("limit")
                    return value if value is not None and value > 0 else None
                # the cap is the page's, passed in rather than known here:
                # `MAX_LINES` lives in `watch.mjs` beside the pane it bounds,
                # and a second copy of it in python is a second authority for
                # how many lines a console keeps. An absent or junk `limit` is
                # no cap, which is what this route did before WP-1427.
                #
                # `end=1` is a *cold open*, and it is the client's to ask for
                # rather than this route's to infer (WP-1438): `offset=0` on a
                # run being tailed from its start is a legitimate request, and
                # a route that quietly seeked instead would make the two
                # indistinguishable. What it changes is where the read starts,
                # never what an offset means — the answer carries the offset
                # it reached, and the next poll is an ordinary one.
                from_end = (query.get("end", [""])[0] or "") == "1"
                tail = self._timed("tail", lambda: runs_mod.tail_events(
                    run.path / runs_mod.EVENTS_FILE,
                    _int("offset") or 0, inode=_int("inode"),
                    max_events=_limit(), from_end=from_end))
                self._json({"events": tail.events, "offset": tail.offset,
                            "inode": tail.inode, "reset": tail.reset,
                            "bad_lines": tail.bad_lines, "size": tail.size,
                            "skipped": tail.skipped,
                            "skipped_bytes": tail.skipped_bytes})
                return
            if rest in ("snapshot", "legacy"):
                # served as bytes, never parsed here: the reader constructs
                # nothing, and a half-written file is the writer's to make
                # atomic (it does)
                name = (runs_mod.SNAPSHOT_FILE if rest == "snapshot"
                        else runs_mod.LEGACY_SNAPSHOT_FILE)
                kind = ("application/json; charset=utf-8" if rest == "snapshot"
                        else "text/html; charset=utf-8")
                try:
                    body = self._timed("read",
                                       (run.path / name).read_bytes)
                except OSError:
                    self._send(b"no snapshot yet", "text/plain; charset=utf-8",
                               status=404)
                    return
                self._send(body, kind)
                return
            self._json({"error": "no such route"}, status=404)
            return

        super().do_GET()

    def do_POST(self):  # noqa: N802 - http.server API
        """The three verbs: ``/api/run/<id>/cancel`` (WP-1405),
        ``/api/run/<id>/gui`` (WP-1428) and ``/api/theme`` (WP-1438).

        POST and never GET. A GET that cancels is one prefetching browser, one
        link preview or one crawler away from stopping somebody's overnight
        refinement, and the static fallback below serves GET to a whole tree.
        The GUI verb takes the same door for the weaker version of the same
        reason: it starts a process, and a prefetch that started one per run in
        the list would be a surprise of its own.

        ``SimpleHTTPRequestHandler`` has no ``do_POST`` at all, so defining one
        means every other POST is answered here rather than by a 501 from the
        base class.

        POST is not enough on its own, which is what :meth:`_origin_ok` is for:
        a cross-origin POST with no body needs no preflight, so a page the
        reader has open in another tab can send this one. Binding
        ``127.0.0.1`` does not help there, and DNS rebinding hands that page
        the run ids as well.
        """
        # drained before anything is written back, or a keep-alive connection
        # reads the unread body as the next request line
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            length = 0
        body = b""
        if length > 0:
            capped = min(length, 1 << 16)
            body = self.rfile.read(capped)
            if capped < length:
                # the cap stops a declared gigabyte becoming this process's
                # memory, and then the connection has to go: the rest of that
                # body is still in the socket, and reusing the connection would
                # parse it as the next request — the desync this drain exists
                # to prevent
                self.close_connection = True

        if not self._origin_ok():
            self._json({"error": "this request did not come from the page "
                                 f"{DIST_NAME} watch serves"}, status=403)
            return

        parts = [p for p in urllib.parse.urlparse(self.path).path.split("/")
                 if p]
        if len(parts) == 4 and parts[:2] == ["api", "run"]:
            if parts[3] == "cancel":
                self._cancel(parts[2])
                return
            if parts[3] == "gui":
                self._open_gui(parts[2])
                return
        if parts == ["api", "theme"]:
            self._set_theme(body)
            return
        self._json({"error": "no such route"}, status=404)

    def _set_theme(self, body: bytes) -> None:
        """Store the theme this page is already drawn in (WP-1438).

        **Not under** ``allow_cancel``/``allow_gui``. Those two fence the
        *run* — an exception raised in somebody's fit, a process started on
        this machine — and ``--read-only`` is a promise about the directory
        being watched, which is what its own message says: "no stop button, no
        GUI launch". A theme is a fact about the reader and the room they are
        in, it is stored in the reader's own state directory, and a page that
        could not be made legible by the person reading it would be a strange
        thing to call read-only.

        The refusal is :func:`~rietx.viz.theme.set_theme_choice`'s, reported
        as a 400 rather than swallowed: a page asking to be a theme that does
        not exist is a bug in the page, and answering 200 to it would hide
        that behind a theme that silently stayed put.
        """
        try:
            payload = json.loads(body.decode("utf-8") or "{}")
            choice = payload["theme"]
        except (UnicodeDecodeError, ValueError, KeyError, TypeError):
            self._json({"error": "expected a JSON body naming a theme"},
                       status=400)
            return
        try:
            stored = theme_mod.set_theme_choice(choice)
        except ValueError as error:
            self._json({"error": str(error)}, status=400)
            return
        except (OSError, RuntimeError) as error:
            # the state directory is somebody else's filesystem, and a theme
            # is not worth a traceback in a served page's log. `RuntimeError`
            # is `Path.home()` on a machine with no home to find, which is the
            # one `theme_choice` answers `system` for: the read repairs it and
            # the write has to say it could not.
            self._json({"error": f"the choice could not be stored: {error}"},
                       status=500)
            return
        self._json({"theme": stored})

    def _cancel(self, run_id: str) -> None:
        """Ask one run to stop, or say why not.

        The id is looked up in what the walk offered (:meth:`_find`), so this
        route inherits WP-1401's property rather than restating it: a run id is
        never decoded into a path, and a request can only ever name a directory
        this server chose to serve. ``SimpleHTTPRequestHandler`` handles
        traversal for static files and a hand-written JSON route does not get
        that for free, which is why the lookup is the mechanism and not a
        check bolted beside one.

        Only a run that is **running here** is stoppable. ``unknown`` covers
        both another host and a writer that keeps no lock, and a request into
        either would lie in the directory until somebody deleted it.
        """
        if not self.allow_cancel:
            self._json({"error": "this watcher is serving read-only"},
                       status=403)
            return
        run = self._find(run_id)
        if run is None:
            self._json({"error": "no such run"}, status=404)
            return
        live = runs_mod.liveness_of(run)
        if live.state != "running":
            self._json({"error": f"this run reads {live.state} — "
                                 f"{live.evidence}", "state": live.state},
                       status=409)
            return
        # A latched recorder is still holding its lock and still reads running,
        # and it is the thing that would have read the request. Refusing says
        # so; writing the file would leave a button that did nothing.
        if run.status is not None and run.status.error:
            self._json({"error": "this run stopped recording, so nothing is "
                                 "reading requests: " + run.status.error,
                        "state": live.state}, status=409)
            return
        try:
            runs_mod.request_cancel(run.path, who=f"{DIST_NAME} watch")
        except OSError as exc:
            self._json({"error": f"could not write the request: {exc}"},
                       status=500)
            return
        self._json({"requested": True, "run_id": run_id, "state": live.state})

    def _open_gui(self, run_id: str) -> None:
        """Start a GUI on a throwaway copy of this run's project (WP-1428).

        A **copy**, and never the project itself. There is no read-only way to
        open one: ``Project.open`` appends a head annotation before any verb
        runs, every verb after that appends more, and the fit is appending to
        the same ``history.jsonl`` at every stage. Two appenders on one log is
        the interleaving WP-1403 separated the run directories to avoid, and
        this log has no such separation. So the copy is the whole safety
        argument, and ``--scratch`` is not a convenience here.

        The copy is frozen at the click. It cannot follow the fit — the GUI's
        live panel reads an in-process ring, which is why ``rietx watch``
        exists — so what it is for is the parameter table, the report, the 3D
        structure, and branching a strategy from the head the fit had reached.
        The button and the manual say so in those words.

        Whether a copy can tear was measured (WP-1428): the window is one flush
        of a record too large for python's 8192 B write buffer, about 0.24 µs
        per append, and at a real fit's rate a click meets it about once in a
        million. It is *not* handled here. ``rietx gui --scratch`` makes the
        copy in the spawned process, and a failure comes back as its boot
        line's error, which is the reader's cue to click again — the second
        copy is measured to open.

        The id is looked up in what the walk offered (:meth:`_find`), so this
        route inherits the property the cancel route does rather than restating
        it: a request can only ever name a directory this server chose to
        serve.
        """
        if not self.allow_gui:
            self._json({"error": "this watcher is serving read-only"},
                       status=403)
            return
        run = self._find(run_id)
        if run is None:
            self._json({"error": "no such run"}, status=404)
            return
        project = runs_mod.project_of(run.path)
        if project is None:
            # a bare `fit()` records under the runs directory and has no
            # project to copy. Building one from the run's snapshot is not a
            # thing: the snapshot is a picture.
            self._json({"error": "this run is not inside a project, so there "
                                 "is nothing to open"}, status=409)
            return
        try:
            boot = _launch_gui(project)
        except OSError as exc:
            self._json({"error": f"could not start the {DIST_NAME} GUI: "
                                 f"{exc}"}, status=500)
            return
        if "error" in boot:
            self._json(boot, status=502)
            return
        boot["run_id"] = run_id
        self._json(boot)

    def log_message(self, *args):  # quiet: polling floods the terminal
        pass


def _gui_argv(project: Path) -> list[str]:
    """The command a launch runs, as its own function so a test can replace it.

    What :func:`_launch_gui` does with the pipe is the part that has been wrong
    twice, and standing a script in for the GUI is the only way to drive the
    cases that matter: a warning arriving before the boot line, a child that
    says why it failed, and a child that never speaks at all.
    """
    return [sys.executable, "-m", f"{__package__.split('.')[0]}.cli", "gui",
            "--scratch", str(project), "--no-open", "--machine"]


def _launch_gui(project: Path) -> dict:
    """Spawn ``rietx gui --scratch`` on ``project`` and read where it landed.

    Returns the boot line's fields, or a dict with ``error`` when the GUI said
    why it could not start. Raises :class:`OSError` only when the spawn itself
    failed.

    ``sys.executable -m rietx.cli`` rather than the ``rietx`` console script:
    the watcher is running in *some* interpreter, and that one has the package
    the reader is watching with. A bare ``rietx`` is whatever is first on
    ``PATH``, which in a worktree is routinely another checkout's.

    ``--machine`` is the flag that prints the JSON boot line, and it exists
    for this caller. It is not necessarily the *first* line on this pipe:
    ``stderr`` is merged in, so the read below looks for the line carrying a
    ``url`` rather than trusting the one that arrives first.

    ``--no-open`` because the page opens the tab, having asked for the launch.
    No ``--port``: ``gui.server.build_server`` already falls
    back to an ephemeral port when the default is busy, so a second window
    needs nothing from here, and three launches on one project were measured
    landing on 8731, 63972 and 63973.

    ``start_new_session`` puts the GUI in its own session, so Ctrl-C in the
    watcher's terminal does not reach it. A spawned GUI outliving the watcher
    is the intent, the same way a scratch copy outlives its GUI.
    """
    proc = subprocess.Popen(
        _gui_argv(project),
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        start_new_session=True)
    _SPAWNED.append(proc)

    # The read is on a thread with a deadline. `readline` on a pipe has no
    # timeout, and a GUI that never printed would hold this request thread for
    # the life of the server.
    #
    # It reads *lines*, not one line, for two reasons. `stderr` is merged into
    # this pipe, so whatever the interpreter says before `serve` prints — a
    # warning, a `-W` setting's output, a dependency's deprecation — would
    # otherwise be read as the boot line and a GUI that is serving reported as
    # a failure. And nothing else ever drains this pipe: a child that fills its
    # 64 kB buffer blocks in `write` for good, so the thread keeps reading to
    # EOF after the boot line has been found.
    boot: list[dict] = []
    said: list[str] = []
    booted = threading.Event()

    def _read() -> None:
        try:
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                line = line.strip()
                if not line or boot:
                    continue
                try:
                    parsed = json.loads(line)
                except ValueError:
                    said.append(line)
                    continue
                # `url` is what makes it the boot line, rather than some other
                # JSON the child happened to print
                if isinstance(parsed, dict) and parsed.get("url"):
                    boot.append(parsed)
                    booted.set()
                else:
                    said.append(line)
        except (OSError, ValueError):               # pragma: no cover - race
            pass
        finally:
            booted.set()          # EOF is an answer too: it will never boot

    reader = threading.Thread(target=_read, daemon=True)
    reader.start()
    booted.wait(GUI_BOOT_TIMEOUT)
    if boot:
        found = boot[0]
        return {"url": found.get("url"), "port": found.get("port"),
                "project": found.get("project"), "pid": found.get("pid"),
                "scratch_of": found.get("scratch_of")}

    # No boot line, so this process is not going to serve anything. It is
    # killed rather than left: `start_new_session` means a stray one outlives
    # the watcher, holding a port and a scratch copy nobody can find.
    exited = proc.poll() is not None
    if not exited:
        proc.kill()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:               # pragma: no cover - race
        pass
    if said:
        # `gui.server.main` prints `rietx gui: <why>` and exits 2 when the
        # project will not open — a torn copy among them (WP-1428). That
        # sentence is the useful half of the answer, so it is passed through
        # rather than replaced with a status code. The *last* line, because a
        # traceback's last line is its exception.
        return {"error": said[-1]}
    if exited:
        return {"error": f"the {DIST_NAME} GUI exited without saying why"}
    return {"error": f"the {DIST_NAME} GUI did not report a port within "
                     f"{GUI_BOOT_TIMEOUT:.0f} s"}


def serve(directory: str | Path | None = None, *, port: int = 8899,
          open_browser: bool = False, block: bool = True,
          allow_cancel: bool = True, allow_gui: bool = True):
    """Serve the runs under ``directory`` (default: the working directory).

    Returns the server when ``block=False``. A directory that is itself a run
    is served as one and the page opens straight onto it.

    ``allow_cancel=False`` serves without the stop verb, and the page draws no
    button (``--read-only``). ``allow_gui=False`` does the same for the GUI
    launch (WP-1428); ``--read-only`` clears both.

    **Stopping is on by default, and that was the decision** (WP-1405). The
    argument for the other way is real: a click here raises in a process the
    reader cannot see, and making that a deliberate act by requiring a flag is
    cheap. Three things settled it the other way. The server binds
    ``127.0.0.1``, so the only person who can click is the person at the
    machine the fit is running on — who can already reach it with Ctrl-C, which
    raises in that process too. A flag you have to have set *in advance* is not
    there when a runaway starts, and killing the watcher to restart it with the
    flag is the moment you needed it. And the dialog already makes it a
    deliberate act, twice over. ``--read-only`` covers the case the argument is
    really about: a reader who is not the person who should be stopping things,
    which is a situation you know about beforehand.
    """
    directory = Path.cwd() if directory is None else Path(directory)
    if not directory.is_dir():
        raise FileNotFoundError(f"{directory} is not a directory")
    directory = directory.resolve()

    # `directory` is the static-file root SimpleHTTPRequestHandler wants;
    # `scan_root` is what the routes walk. Per instance, so two servers in one
    # process (the tests run several) cannot take each other's root.
    index = _RunIndex(directory)
    handler = functools.partial(_Handler, directory=str(directory),
                                scan_root=directory, index=index,
                                allow_cancel=allow_cancel,
                                allow_gui=allow_gui)
    server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
    url = f"http://127.0.0.1:{server.server_address[1]}/"
    found = index.runs()
    print(f"rietx watch: {len(found)} run(s) under {directory}")
    print(f"             {url}  (Ctrl-C to stop)")
    # Read off both flags, because they are two. `--read-only` clears the pair
    # and this line then reads as it always did; a caller that declines one of
    # them gets a banner that is true rather than one that names the other.
    withheld = ([] if allow_cancel else ["no stop button"]) + \
               ([] if allow_gui else ["no GUI launch"])
    if withheld:
        print("             read-only: " + ", ".join(withheld))
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    if not block:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return server


def main(argv: list[str] | None = None) -> None:
    import argparse

    parser = argparse.ArgumentParser(
        prog="rietx watch",
        description="list and watch the refinement runs under a directory")
    parser.add_argument("directory", nargs="?", default=None,
                        help="directory to scan (default: the working "
                             "directory); a directory that is itself a run "
                             "opens straight onto it")
    parser.add_argument("--port", type=int, default=8899)
    parser.add_argument("--open", action="store_true", help="open a browser")
    parser.add_argument("--read-only", action="store_true",
                        help="serve without the two verbs: the page offers no "
                             "way to cancel a running fit and no way to open "
                             "one in the GUI, and both routes refuse")
    args = parser.parse_args(argv)
    serve(args.directory, port=args.port, open_browser=args.open,
          allow_cancel=not args.read_only, allow_gui=not args.read_only)
