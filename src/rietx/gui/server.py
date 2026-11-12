"""``rietx gui`` — the localhost HTTP surface over a :class:`GuiSession`.

Stdlib ``http.server``, as ``rietx watch`` and ``rietx compare`` already are.
A single-user localhost app with ~30 routes gains nothing from an ASGI stack and
loses the two properties that matter here: a base install with no new
dependencies, and a page that works air-gapped (every script the page runs is
in the committed dist, so a strict-CSP or offline machine needs no exception).
Server-sent events work fine on ``ThreadingHTTPServer``.

**This module is transport only.**  Every route is one line — parse, call a
:class:`~rietx.gui.session.GuiSession` method, serialise — so replacing it
with a Tauri command handler means reimplementing this file and nothing else.
The route table is data for the same reason: ``ROUTES`` and
``session.RESERVED_ROUTES`` together are the complete wire surface, which is what
lets a test assert that no route is silently missing.

Security is the localhost kind and no more: bound to 127.0.0.1, ``Host`` and
``Origin`` checked so a page on another site cannot drive this server through a
DNS-rebinding attack, and export paths confined to the project's ``exports/``.
There is no auth, no TLS and no multi-user story — one user, one machine, one
process, one project.
"""

from __future__ import annotations

import http.server
import json
import math
import shutil
import socket
import sys
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .._about import SERVER_TOKEN, STATE_DIR_ENV, STATE_DIR_NAME
from ..optimize.least_squares import DEFAULT_SOLVER
from ..project import Project
from ..viz.packed import MEDIA_TYPE as PACKED_MEDIA_TYPE
from ..viz.packed import Packed
from .imports import MAX_UPLOAD_BYTES, UPLOAD_KINDS
from .session import EXPORT_DEFAULTS, RESERVED_ROUTES, GuiError, GuiSession

#: ``compare`` owns 8730 and ``watch`` 8899; the GUI takes the next one up.
DEFAULT_PORT = 8731

#: Built frontend assets (WP-1010) land here and are committed, so installing
#: the package never needs node.  Until then the placeholder page below explains
#: itself and the API is fully usable without it.
STATIC_DIR = Path(__file__).parent / "static"
#: The paths that serve the rebuilt GUI's page (WP-2215); ``rietx gui --new``
#: opens the first. Both pages talk to the same routes, so a project open in
#: one is the project in the other.
NEXT_PAGES = ("/next", "/next/")


def _page_file(path: str) -> Path | None:
    """The built page a request path names, or ``None`` when it names none.

    ``/`` is today's GUI; :data:`NEXT_PAGES` the rebuilt one (WP-2214,
    WP-2215), a second page of the same build over the same session, until it
    replaces ``index.html``.
    """
    if path in ("/", "/index.html"):
        return STATIC_DIR / "index.html"
    if path in NEXT_PAGES:
        return STATIC_DIR / "next.html"
    return None

_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "[::1]", "::1"})

_SSE_HEARTBEAT = 15.0  # seconds between ``: keepalive`` comments

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".woff2": "font/woff2",
    ".map": "application/json; charset=utf-8",
}


# ----------------------------------------------------------------------
# serialisation
# ----------------------------------------------------------------------
def _finite(obj: Any) -> Any:
    """Replace every non-finite float with its string spelling, in place of nothing.

    ``json.dumps`` writes bare ``Infinity``/``NaN`` tokens, which are a Python
    extension: **JavaScript's ``JSON.parse`` rejects them outright**, so a single
    ``hi: inf`` bound turns a whole response into a parse error in the browser.
    Every parameter row has one, which is why this was invisible until a client
    read ``/api/params`` (WP-1011) rather than the curves.

    The spelling is not invented here — it is the one the schemas already chose
    (``ser_json_inf_nan="strings"``, CLAUDE.md: "±inf bounds must survive JSON
    round-trip"), so ``"Infinity"`` reads back as ``Number("Infinity")`` in JS and
    as ``float("Infinity")`` in Python.  The GUI server was the one place in this
    package re-serialising already-dumped dicts with stdlib ``json``, and so the
    one place that convention was being lost.
    """
    if isinstance(obj, float):
        return obj if math.isfinite(obj) else repr(obj).replace("nan", "NaN").replace(
            "inf", "Infinity")
    if isinstance(obj, dict):
        return {k: _finite(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_finite(v) for v in obj]
    return obj


def _dumps(payload: Any) -> str:
    """``json.dumps`` that a browser can parse.

    The scan is a substring test on the *output*, so the common response — no
    non-finite value anywhere — pays one C-level search rather than a recursive
    walk of a 4000-point curve payload.
    """
    text = json.dumps(payload, default=str)
    if "Infinity" in text or "NaN" in text:
        text = json.dumps(_finite(payload), default=str)
    return text


# ----------------------------------------------------------------------
# the route table
# ----------------------------------------------------------------------
def _query_float(query: dict, key: str) -> float | None:
    values = query.get(key)
    if not values or values[0] == "":
        return None
    try:
        return float(values[0])
    except ValueError:
        raise GuiError(f"{key}={values[0]!r} is not a number", where=[key]) from None


def _query_int(query: dict, key: str, default: int) -> int:
    values = query.get(key)
    if not values or values[0] == "":
        return default
    try:
        return int(values[0])
    except ValueError:
        raise GuiError(f"{key}={values[0]!r} is not an integer", where=[key]) from None


def _diff(s: GuiSession, q: dict, _body: dict) -> dict:
    a, b = q.get("a", [""])[0], q.get("b", [""])[0]
    if not a or not b:
        raise GuiError("diff needs ?a=<node>&b=<node>", where=["a", "b"])
    return s.history_diff(a, b)


def _compare(s: GuiSession, q: dict, _body: dict) -> dict:
    ids = [i for i in ",".join(q.get("ids", [])).split(",") if i]
    if not ids:
        raise GuiError("compare needs ?ids=n0001,n0002", where=["ids"])
    return s.history_compare(ids)


def _structure3d(s: GuiSession, q: dict, _body: dict) -> dict:
    """Geometry for one phase.  The knobs are *drawing* thresholds, not physics,
    which is why they ride here rather than in a settings document: the
    probability level an ellipsoid is drawn at, the radius-sum slack a bond is
    drawn at, which alternative of a disordered site is drawn and which elements
    a polyhedron is drawn round say nothing about the model, and persisting any
    would make one picture the project's opinion."""
    return s.structure3d(_query_int(q, "phase", 0),
                         probability=_query_float(q, "probability") or 0.5,
                         bond_tolerance=_query_float(q, "bond_tolerance"),
                         disorder=(q.get("disorder") or ["all"])[0],
                         centres=_query_list(q, "centres"),
                         ligands=_query_list(q, "ligands"))


def _query_list(q: dict, name: str) -> list[str] | None:
    """A comma-separated list, ``None`` when the name is absent.  Present and
    empty is an empty list, which is a request for none."""
    if name not in q:
        return None
    return [v.strip() for part in q[name] for v in part.split(",") if v.strip()]


def _series_index(q: dict, what: str) -> int:
    """A series route's ``index``, which is required and is not defaulted to 0:
    a window of "whichever pattern" is not a question anyone asks, and a silent
    default would draw pattern 0 under another one's label."""
    if not q.get("index") or q["index"][0] == "":
        raise GuiError(f"series {what} needs ?index=<pattern>", where=["index"])
    return _query_int(q, "index", 0)


def _series_curves(s: GuiSession, q: dict, _body: dict) -> Packed:
    return s.series_curves(_series_index(q, "curves"))


def _series_history(s: GuiSession, q: dict, _body: dict) -> dict:
    return s.series_history(_series_index(q, "history"))


def _report(s: GuiSession, q: dict, _body: dict) -> dict:
    plan = q.get("plan", [None])[0]
    return s.report(plan=plan or None)


#: ``(method, path) → handler(session, query, body)``.  Exact matches only: the
#: surface has no path parameters (ids travel as query strings or in the body),
#: which keeps this table readable as the wire contract it is.
ROUTES: dict[tuple[str, str], Any] = {
    ("GET", "/api/capabilities"): lambda s, q, b: s.capabilities(),
    ("GET", "/api/version"): lambda s, q, b: s.version(),
    # the help corpus (WP-1202), beside capabilities for the same reason: it is
    # a fact about the build, not about a project, so it needs no project open
    # and is not behind the in-flight 409
    ("GET", "/api/help"): lambda s, q, b: s.help(),
    # what one symbol constrains (WP-1206), beside the two above for the same
    # reason: a fact about a symbol rather than about a model, needed by the
    # wizard's typed-cell step, which runs before any project exists
    ("GET", "/api/spacegroup"):
        lambda s, q, b: s.spacegroup((q.get("space_group") or [""])[0]),

    ("POST", "/api/project/new"): lambda s, q, b: s.project_new(b),
    ("POST", "/api/project/open"): lambda s, q, b: s.project_open(b),
    ("GET", "/api/project"): lambda s, q, b: s.project_doc(),
    ("POST", "/api/project"): lambda s, q, b: s.project_patch(b),
    ("POST", "/api/project/save"): lambda s, q, b: s.project_save(),
    # the File menu (WP-2133): each acts on the project's folder
    ("POST", "/api/project/copy"): lambda s, q, b: s.project_copy(b),
    ("POST", "/api/project/rename"): lambda s, q, b: s.project_rename(b),
    ("POST", "/api/project/move"): lambda s, q, b: s.project_move(b),
    ("POST", "/api/project/close"): lambda s, q, b: s.project_close(),
    ("GET", "/api/recent"): lambda s, q, b: {"recent": s.recent()},
    ("POST", "/api/recent/remove"): lambda s, q, b: s.recent_remove(b),
    ("POST", "/api/recent/clear"): lambda s, q, b: s.recent_clear(),
    # the "Open…" browser's own listing (WP-1205): read-only, confined to the
    # home directory and the process's cwd — see GuiSession.fs
    ("GET", "/api/fs"): lambda s, q, b: s.fs((q.get("path") or [None])[0]),
    # the empty state's other list (WP-1204): example projects shipped in the
    # wheel, built into the state directory on first open
    ("GET", "/api/examples"): lambda s, q, b: s.examples(),
    ("POST", "/api/examples/open"): lambda s, q, b: s.example_open(b),
    ("POST", "/api/examples/reset"): lambda s, q, b: s.example_reset(b),
    # the app's own `ui` keys, beside the recent list because both are the
    # *person's* rather than a project's (WP-1044)
    ("GET", "/api/settings"): lambda s, q, b: s.settings(),
    ("POST", "/api/settings"): lambda s, q, b: s.settings_patch(b),
    # the open project's recovery copy of unapplied edits (WP-2209), in the
    # state directory beside the settings and, like them, not behind the 409
    ("GET", "/api/recovery"): lambda s, q, b: s.recovery(),
    ("PUT", "/api/recovery"): lambda s, q, b: s.recovery_put(b),

    ("GET", "/api/params"): lambda s, q, b: s.params(),
    ("PATCH", "/api/params"): lambda s, q, b: s.params_patch(b),
    ("GET", "/api/plan"): lambda s, q, b: s.plan(),
    ("PUT", "/api/plan"): lambda s, q, b: s.plan_put(b),
    ("GET", "/api/plans"): lambda s, q, b: s.plans(),
    ("GET", "/api/plan/resolve"): lambda s, q, b: s.plan_resolve(),
    ("GET", "/api/structure"): lambda s, q, b: s.structure(),
    ("GET", "/api/structure3d"): _structure3d,
    ("PATCH", "/api/structure"): lambda s, q, b: s.structure_patch(b),
    ("POST", "/api/structure/aniso"): lambda s, q, b: s.structure_aniso(b),
    # a typed coordinate, projected onto the site's DOFs (WP-1215) — a
    # ``set_value`` node rather than a model edit, since a position reaches
    # theta as displacements and changes nothing the table *contains*
    ("POST", "/api/structure/position"): lambda s, q, b: s.structure_position(b),
    # symmetry is three routes rather than one because they are three costs: the
    # GET runs a spglib search per atom (WP-1035), the preview builds a candidate
    # parameter table per atom, and only the last of them writes a history node
    ("GET", "/api/structure/symmetry"):
        lambda s, q, b: s.structure_symmetry(_query_int(q, "phase", 0)),
    ("POST", "/api/structure/symmetry/preview"):
        lambda s, q, b: s.symmetry_preview(b),
    ("POST", "/api/structure/symmetry"): lambda s, q, b: s.symmetry_patch(b),
    # the scan picker's own fetch: the preview's ``scan_count`` says *how many*
    # from the read it already did, and this says what each one **is** — a
    # second walk, so it is paid only when a person opens the control
    ("GET", "/api/upload/pattern/scans"):
        lambda s, q, b: s.upload_scans((q.get("upload") or [""])[0]),
    ("GET", "/api/instrument"): lambda s, q, b: s.instrument(),
    ("PATCH", "/api/instrument"): lambda s, q, b: s.instrument_patch(b),

    ("POST", "/api/run"): lambda s, q, b: s.run(b),
    ("POST", "/api/cancel"): lambda s, q, b: s.cancel(),
    ("GET", "/api/run/state"): lambda s, q, b: s.run_state(),

    ("GET", "/api/result"): lambda s, q, b: s.result(),
    # every channel once, as float64 arrays rather than JSON (WP-1461, D4)
    ("GET", "/api/result/curves"): lambda s, q, b: s.result_curves(),
    # the curves at values nobody has applied, writing nothing (WP-2125)
    ("POST", "/api/preview"): lambda s, q, b: s.preview(b),
    # the background curve and its band from the fit's covariance (WP-2129)
    ("GET", "/api/background"): lambda s, q, b: s.background(),
    ("GET", "/api/report"): _report,
    ("POST", "/api/report/apply"): lambda s, q, b: s.report_apply(b),

    ("GET", "/api/textdoc"): lambda s, q, b: s.textdoc(),
    ("PUT", "/api/textdoc"): lambda s, q, b: s.textdoc_put(b),

    ("GET", "/api/peaks"): lambda s, q, b: s.peaks(),
    ("POST", "/api/peaks"): lambda s, q, b: s.peaks_pick(b),
    ("POST", "/api/peaks/add"): lambda s, q, b: s.peaks_add(b),
    ("POST", "/api/peaks/remove"): lambda s, q, b: s.peaks_remove(b),
    ("POST", "/api/peaks/move"): lambda s, q, b: s.peaks_move(b),
    ("POST", "/api/peaks/flag"): lambda s, q, b: s.peaks_flag(b),
    ("POST", "/api/peaks/refit"): lambda s, q, b: s.peaks_refit(b),
    # /api/index rides the one run state machine: same worker, same 409
    ("POST", "/api/index"): lambda s, q, b: s.run({**b, "kind": "index"}),
    ("GET", "/api/index/result"): lambda s, q, b: s.index_result(),
    # one candidate's predicted positions, for the plot overlay (WP-1211).  Its
    # own route rather than an arm of the answer above, because it is a cost the
    # answer should not carry: hundreds of floats per candidate, wanted for one
    # at a time.  ``?candidate=`` and not a path segment — see this table's own
    # rule above.
    ("GET", "/api/index/ticks"):
        lambda s, q, b: s.index_ticks(_query_int(q, "candidate", 0)),
    ("POST", "/api/index/adopt"): lambda s, q, b: s.index_adopt(b),
    # the extinction screen rides the same machine (WP-1025 served)
    ("POST", "/api/index/extinction"):
        lambda s, q, b: s.run({**b, "kind": "extinction"}),
    ("GET", "/api/index/extinction"): lambda s, q, b: s.index_extinction(),

    # a series is N patterns *outside* the project's single-pattern document
    # (WP-1016), so it is a route family of its own — and its run rides the one
    # run machine, exactly as /api/index does
    ("GET", "/api/series"): lambda s, q, b: s.series(),
    ("PUT", "/api/series"): lambda s, q, b: s.series_put(b),
    ("POST", "/api/series/run"): lambda s, q, b: s.run({**b, "kind": "series"}),
    ("GET", "/api/series/result"): lambda s, q, b: s.series_result(),
    ("GET", "/api/series/curves"): _series_curves,
    ("GET", "/api/series/history"): _series_history,

    ("GET", "/api/history"): lambda s, q, b: s.history(),
    ("GET", "/api/history/diff"): _diff,
    ("GET", "/api/history/compare"): _compare,
    ("POST", "/api/history/checkout"): lambda s, q, b: s.history_checkout(b),
    ("POST", "/api/history/branch"): lambda s, q, b: s.history_branch(b),
    ("POST", "/api/history/tag"): lambda s, q, b: s.history_tag(b),
    ("POST", "/api/history/annotate"): lambda s, q, b: s.history_annotate(b),
}

# From the session's own table rather than a second list of the kinds: this
# file is transport, and a kind it did not know about would be a 404 with no
# way to tell it from a typo.
for _kind in sorted(EXPORT_DEFAULTS):
    ROUTES[("POST", f"/api/export/{_kind}")] = (
        lambda s, q, b, _k=_kind: s.export(_k, b))
del _kind

#: ``(method, path) → upload kind``.  The **only** routes in this surface whose
#: body is not JSON: a file goes up as its own bytes, and its name and options
#: travel in the query string.  Base64 in a JSON envelope was the alternative and
#: buys nothing — it inflates the body by a third and still needs the same cap —
#: while multipart would mean parsing a format the stdlib no longer ships a
#: parser for (``cgi`` is gone in 3.13).  Kept as a third table rather than a
#: branch inside :data:`ROUTES` so "the route table is the wire contract" stays
#: true and a test can assert the three tables are disjoint.
UPLOAD_ROUTES: dict[tuple[str, str], str] = {
    ("POST", f"/api/upload/{kind}"): kind for kind in UPLOAD_KINDS}


def _upload_options(query: dict) -> dict:
    """The reader keywords an upload may carry, off the query string.

    Two vocabularies meet here: ``aniso`` and ``phase_name`` are the CIF
    reader's, while the pattern reader's come from
    :data:`~rietx.io.readers.READER_OPTIONS` rather than a literal list — so a
    format that adds ``scan`` is reachable from this route with no edit here.
    All of them are *re-read* options, which is why they belong on the upload
    route and not only on the commit that follows.  Values stay strings;
    ``reader_options_for`` is the one place that coerces them.
    """
    from ..io.readers import READER_OPTIONS

    options: dict[str, Any] = {}
    if query.get("aniso"):
        options["aniso"] = query["aniso"][0].lower() not in ("", "0", "false")
    for key in ("phase_name", *READER_OPTIONS):
        if query.get(key) and query[key][0]:
            options[key] = query[key][0]
    return options


# ----------------------------------------------------------------------
# the handler
# ----------------------------------------------------------------------
def _handler(session: GuiSession, holder: dict):
    class Handler(http.server.BaseHTTPRequestHandler):
        server_version = "rietx-gui"
        # HTTP/1.0 semantics: no chunked encoding to arrange and a connection
        # that closes when a handler returns, which is what makes the SSE route
        # a plain write loop.
        protocol_version = "HTTP/1.0"

        def log_message(self, *args) -> None:  # the poll traffic would flood
            pass

        # -- plumbing ------------------------------------------------
        def _send(self, body: bytes, content_type: str, code: int = 200) -> None:
            self.send_response(code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def _json(self, payload: Any, code: int = 200) -> None:
            self._send(_dumps(payload).encode("utf-8"),
                       "application/json; charset=utf-8", code)

        def _error(self, exc: GuiError) -> None:
            self._json(exc.payload(), exc.status)

        def _body(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if not length:
                return {}
            raw = self.rfile.read(length)
            try:
                parsed = json.loads(raw or b"{}")
            except ValueError as exc:
                raise GuiError(f"request body is not JSON: {exc}") from None
            if not isinstance(parsed, dict):
                raise GuiError("request body must be a JSON object")
            return parsed

        def _raw_body(self) -> bytes:
            """The body as bytes — the upload routes' half of ``_body``.

            The cap is checked against the *declared* length before a byte is
            read, because reading first and refusing after is how a 4 GB
            ``Content-Length`` becomes this process's memory.
            """
            length = int(self.headers.get("Content-Length") or 0)
            if length > MAX_UPLOAD_BYTES:
                raise GuiError(
                    f"{length} bytes is over the {MAX_UPLOAD_BYTES}-byte upload "
                    "limit", code="UPLOAD_TOO_LARGE", status=413)
            return self.rfile.read(length) if length else b""

        def _origin_ok(self) -> bool:
            """Reject cross-site drivers; a same-origin fetch sends no Origin.

            The check is the one thing standing between a localhost API and any
            page the user happens to have open, since a browser will resolve a
            hostile domain to 127.0.0.1 if its DNS says so (rebinding).  Both
            headers are checked because ``Host`` alone is what rebinding
            defeats.
            """
            for header in ("Origin", "Referer"):
                value = self.headers.get(header)
                if not value:
                    continue
                host = urlparse(value).hostname or ""
                if host not in _ALLOWED_HOSTS:
                    return False
            host = (self.headers.get("Host") or "").rsplit(":", 1)[0]
            return host in _ALLOWED_HOSTS

        # -- dispatch ------------------------------------------------
        def do_GET(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("GET")

        def do_HEAD(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("GET")

        def do_POST(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("POST")

        def do_PATCH(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("PATCH")

        def do_PUT(self) -> None:  # noqa: N802 - stdlib API
            self._dispatch("PUT")

        def _dispatch(self, method: str) -> None:
            if not self._origin_ok():
                self._json({"error": {
                    "code": "FORBIDDEN_HOST",
                    "message": f"{self.headers.get('Host')!r} is not a loopback "
                               "host; rietx gui serves 127.0.0.1 only",
                    "where": []}}, 403)
                return
            parts = urlparse(self.path)
            path = parts.path.rstrip("/") or "/"
            query = parse_qs(parts.query, keep_blank_values=True)
            try:
                if method == "POST" and path == "/api/shutdown":
                    self._shutdown()
                    return
                if method == "GET" and path == "/api/events":
                    self._events(query)
                    return
                kind = UPLOAD_ROUTES.get((method, path))
                if kind is not None:
                    self._json(session.upload(
                        kind, data=self._raw_body(),
                        filename=query.get("filename", [""])[0],
                        token=query.get("upload", [""])[0],
                        options=_upload_options(query)))
                    return
                handler = ROUTES.get((method, path))
                if handler is not None:
                    body = self._body() if method != "GET" else {}
                    answer = handler(session, query, body)
                    if isinstance(answer, Packed):
                        self._send(answer.to_bytes(_dumps), PACKED_MEDIA_TYPE)
                    else:
                        self._json(answer)
                    return
                if (method, path) in RESERVED_ROUTES:
                    owner = RESERVED_ROUTES[(method, path)]
                    self._json({"error": {
                        "code": "NOT_IMPLEMENTED",
                        "message": f"{method} {path} is reserved for {owner}; the "
                                   "path is settled, the behaviour is not here yet",
                        "where": []}}, 404)
                    return
                if method == "GET":
                    self._static(path)
                    return
                self._json({"error": {"code": "NOT_FOUND",
                                      "message": f"no route {method} {path}",
                                      "where": []}}, 404)
            except GuiError as exc:
                self._error(exc)
            except BrokenPipeError:  # pragma: no cover - client went away
                pass
            except Exception as exc:  # noqa: BLE001 — a 500 body beats a traceback
                self._json({"error": {
                    "code": "INTERNAL_ERROR",
                    "message": f"{type(exc).__name__}: {exc}",
                    "where": []}}, 500)

        # -- static --------------------------------------------------
        def _static(self, path: str) -> None:
            page = _page_file(path)
            if page is not None:
                if page.is_file():
                    self._send(page.read_bytes(), "text/html; charset=utf-8")
                else:
                    self._send(_PLACEHOLDER.encode("utf-8"),
                               "text/html; charset=utf-8")
                return
            target = (STATIC_DIR / path.lstrip("/")).resolve()
            root = STATIC_DIR.resolve()
            if not target.is_relative_to(root) or not target.is_file():
                self._json({"error": {
                    "code": "NOT_FOUND",
                    "message": f"no static asset {path} (the built frontend "
                               "lands in WP-1010)", "where": []}}, 404)
                return
            self._send(target.read_bytes(),
                       _CONTENT_TYPES.get(target.suffix, "application/octet-stream"))

        # -- events --------------------------------------------------
        def _events(self, query: dict) -> None:
            since = _query_int(query, "since", 0)
            if query.get("poll"):
                self._json(session.events_since(since))
                return
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Accel-Buffering", "no")  # no proxy buffering
            self.end_headers()
            state_key = ""
            last_beat = time.monotonic()
            try:
                while not session.closed:
                    events, since, frame, state_key = session.follow(
                        since, state_key, timeout=1.0)
                    for event in events:
                        self._frame("event", event, seq=event["seq"])
                    if frame is not None:
                        self._frame("state", frame)
                    if events or frame is not None:
                        last_beat = time.monotonic()
                    elif time.monotonic() - last_beat > _SSE_HEARTBEAT:
                        self.wfile.write(b": keepalive\n\n")
                        self.wfile.flush()
                        last_beat = time.monotonic()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass  # the client closed the tab; nothing to clean up

        def _frame(self, name: str, payload: dict, seq: int | None = None) -> None:
            chunk = "" if seq is None else f"id: {seq}\n"
            # the same encoder the JSON routes use: an event's `data` is an open
            # dict, so a non-finite value in it would break `JSON.parse` in the
            # stream's listener exactly as it would in a response body
            chunk += f"event: {name}\ndata: {_dumps(payload)}\n\n"
            self.wfile.write(chunk.encode("utf-8"))
            self.wfile.flush()

        # -- shutdown ------------------------------------------------
        def _shutdown(self) -> None:
            self._json({"stopping": True})
            session.close()  # release the SSE followers first
            server = holder.get("server")
            if server is not None:
                threading.Thread(target=server.shutdown, daemon=True).start()

    return Handler


# ----------------------------------------------------------------------
# serving
# ----------------------------------------------------------------------
class _Server(http.server.ThreadingHTTPServer):
    # http.server sets allow_reuse_address (SO_REUSEADDR), which on POSIX
    # means "rebind a TIME_WAIT port" — but on Windows it means "bind over a
    # port another process is actively LISTENING on".  With it set there, a
    # busy port binds without an OSError, the fallback below never engages,
    # and two servers silently share :8731 (found by the busy-port test on
    # the first Windows CI run, WP-1003).  Windows has no TIME_WAIT rebind
    # problem for this server, so the flag buys nothing there either.
    allow_reuse_address = sys.platform != "win32"


def build_server(session: GuiSession, *, port: int = DEFAULT_PORT):
    """A bound ``ThreadingHTTPServer``, falling back to an ephemeral port.

    A busy port is the ordinary case, not an error: a second window, or a
    previous run that has not exited yet.  Refusing to start would be the wrong
    answer for a GUI, and the printed URL (or the ``--machine`` line) is where
    the real port is read from anyway.
    """
    holder: dict = {}
    handler = _handler(session, holder)
    try:
        httpd = _Server(("127.0.0.1", port), handler)
    except OSError:
        httpd = _Server(("127.0.0.1", 0), handler)
    httpd.daemon_threads = True
    holder["server"] = httpd
    return httpd


def serve(session: GuiSession, *, port: int = DEFAULT_PORT,
          open_browser: bool = True, machine: bool = False,
          block: bool = True, scratch_of: str | Path | None = None,
          new: bool = False):
    """Serve ``session``; returns the server when ``block=False`` (tests).

    ``scratch_of`` is the project a :func:`scratch_copy` was made *from*, when
    the session is running on one.  The **source**, not the copy: the copy is
    already the boot line's ``project``, and the source is the fact a path
    cannot carry — that whatever happens in here, the directory the person
    named on the command line is not written to.

    ``new`` points the browser and the banner at the rebuilt page, ``/next``
    (WP-2215); the server serves both pages either way.
    """
    httpd = build_server(session, port=port)
    actual = httpd.server_address[1]
    route = NEXT_PAGES[0] if new else "/"
    url = f"http://127.0.0.1:{actual}{route}"
    if machine:
        # one line, first, so a supervising process (Tauri) can read the port
        # without parsing prose
        print(json.dumps({"url": url, "port": actual,
                          "project": session.version()["project"],
                          "pid": session.version()["pid"],
                          "scratch_of": (str(scratch_of) if scratch_of
                                         else None)}),
              flush=True)
    else:
        project = session.version()["project"]
        # flush: redirecting the banner to a log file otherwise buffers it until
        # the process exits, which is exactly when nobody needs to read the port
        print(f"rietx gui — {url}", flush=True)
        print(f"  project: {project or '(none open yet)'}", flush=True)
        if scratch_of is not None:
            print(f"  scratch copy — {scratch_of} is not written to",
                  flush=True)
        if not _page_file(route).is_file():
            print("  frontend: not built — run `npm --prefix gui run build`; "
                  "the HTTP API is live either way", flush=True)
        print("  Ctrl-C to stop", flush=True)
    if open_browser:
        import webbrowser

        webbrowser.open(url)
    if not block:
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        return httpd
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        session.close()
        httpd.server_close()
    return httpd


def scratch_copy(project: str | Path) -> Path:
    """A throwaway copy of a project directory, opened instead of the original.

    There is no read-only way to open a project: **settings persist on the
    verb** (``gui/CLAUDE.md``), and the history log is appended to as the tree
    grows, so a click writes into the ``.rex`` directory it was opened from.
    That is right for the person refining their own data and wrong for anyone
    poking at a project under version control — which is every developer of
    this package, and everyone opening one of the shipped examples.

    The copy is byte-for-byte, so ``DataRef``'s sha256 and its parsed-array
    fingerprint both still match and ``Project.open`` cannot tell the
    difference.  It keeps the source's own directory name, because that name is
    what the GUI's header shows.

    Nothing removes it.  The point of a scratch run is usually to look at what
    happened, and a copy deleted on exit would take the answer with it; the
    temp directory is the operating system's to reap.
    """
    src = Path(project).expanduser()
    if not src.is_dir():
        raise NotADirectoryError(f"not a project directory: {src}")
    root = Path(tempfile.mkdtemp(prefix=f"{SERVER_TOKEN}-scratch-"))
    dest = root / src.name
    shutil.copytree(src, dest)
    return dest


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        prog="rietx gui",
        description="Serve the rietx GUI for a project on localhost.")
    parser.add_argument("project", nargs="?", default=None,
                        help="a .rex project directory to open on boot")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--no-open", action="store_false", dest="open_browser",
                        help="do not open a browser window")
    parser.add_argument("--machine", action="store_true",
                        help="print one JSON boot line (url, port, project, pid, scratch_of)")
    parser.add_argument("--backend", default="numpy",
                        help="Jacobian backend (see rietx.capabilities())")
    parser.add_argument("--solver", default=DEFAULT_SOLVER)
    parser.add_argument("--scratch", action="store_true",
                        help="open a throwaway copy of the project; the "
                             "directory named on the command line is never "
                             "written to")
    parser.add_argument("--new", action="store_true",
                        help="open the rebuilt GUI, served at /next beside "
                             "today's page until it replaces it")
    parser.add_argument("--state-dir", default=None, metavar="PATH",
                        help="where the recent list and the theme are kept "
                             f"(default: ${STATE_DIR_ENV}, else "
                             f"~/{STATE_DIR_NAME})")
    args = parser.parse_args(argv)

    project = None
    scratch_of = None
    if args.project is None:
        if args.scratch:
            # silently ignoring it would start a session that looks scratch and
            # writes to whatever is opened from inside it
            print("rietx gui: --scratch needs a project to copy")
            return 2
    else:
        source = args.project
        if args.scratch:
            try:
                source = scratch_copy(args.project)
            except OSError as exc:
                print(f"rietx gui: {exc}")
                return 2
            scratch_of = args.project
        try:
            project = Project.open(source, backend=args.backend,
                                   solver=args.solver)
        except (OSError, ValueError) as exc:
            # the refusal messages name seven different remedies; printing the
            # one that applies is the whole value of them
            print(f"rietx gui: {exc}")
            return 2
    session = GuiSession(project, backend=args.backend, solver=args.solver,
                         state_dir=args.state_dir)
    if project is None:
        # no project named: return to the last one, as VS Code and JetBrains
        # do, and start on the start screen when there is none (WP-2131)
        session.reopen_last()
    serve(session, port=args.port, open_browser=args.open_browser,
          machine=args.machine, scratch_of=scratch_of, new=args.new)
    return 0


def _free_port() -> int:  # pragma: no cover - helper for scripts and tests
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


# ----------------------------------------------------------------------
_PLACEHOLDER = """<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>rietx gui</title>
<style>
 :root { color-scheme: light dark; }
 body { margin:0; padding:2.5rem clamp(1rem, 5vw, 4rem); max-width:70ch;
        font:14px/1.55 ui-sans-serif, system-ui, sans-serif; }
 h1 { font-size:1.15rem; margin:0 0 .2rem; }
 p.sub { opacity:.7; margin:0 0 1.6rem; }
 code { font:12.5px ui-monospace, Menlo, monospace; }
 li { margin:.15rem 0; }
 .m { display:inline-block; min-width:4.2em; opacity:.65; }
</style></head><body>
<h1>rietx gui — server running, frontend not built</h1>
<p class="sub">The Svelte app is WP-1010. The HTTP API below is live now, and
every route is a method on <code>rietx.gui.GuiSession</code>.</p>
<ul>
 <li><span class="m">GET</span> <code>/api/capabilities</code> — what this build can do</li>
 <li><span class="m">GET</span> <code>/api/project</code> · <code>/api/params</code> ·
     <code>/api/plan</code> · <code>/api/structure</code> · <code>/api/instrument</code></li>
 <li><span class="m">POST</span> <code>/api/run</code> · <code>/api/cancel</code> ·
     <span class="m">GET</span> <code>/api/run/state</code></li>
 <li><span class="m">GET</span> <code>/api/events</code> — SSE (<code>?since=</code> replay,
     <code>?poll=1</code> JSON fallback)</li>
 <li><span class="m">GET</span> <code>/api/result</code> ·
     <code>/api/result/curves</code> · <code>/api/report</code></li>
 <li><span class="m">GET</span> <code>/api/history</code> ·
     <span class="m">POST</span> <code>/api/history/checkout</code></li>
 <li><span class="m">GET</span>/<span class="m">PUT</span> <code>/api/textdoc</code>
     — the project as text (<code>.rxt</code>), compare-and-set on a revision</li>
 <li><span class="m">POST</span> <code>/api/export/{cif,reflections,qpa,html,result_json,instrument_profile}</code></li>
 <li><span class="m">GET</span>/<span class="m">POST</span> <code>/api/peaks</code>
     (+ <code>add/move/remove/flag/refit</code>) ·
     <span class="m">POST</span> <code>/api/index</code> ·
     <span class="m">GET</span> <code>/api/index/result</code> ·
     <code>/api/index/extinction</code> · <span class="m">POST</span>
     <code>/api/index/adopt</code></li>
</ul>
</body></html>
"""
