"""WP-1401 — the ``rietx watch`` app: the run list, and the routes under it.

``watch/`` is transport, so these tests are about what the routes send.
What they send it *about* is :mod:`rietx.runs`, tested next door.

Since WP-1430 the page is four files in ``watch/static/`` rather than a string
in the module, so a test about what the *page* says fetches the file that says
it — the script for anything in the script, the stylesheet for a rule.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from contextlib import contextmanager
from pathlib import Path

import pytest

import rietx as rx
from rietx import runs, watch
from rietx._about import STATE_DIR_ENV
from rietx.watch import main, serve


@contextmanager
def _served(directory: Path, *, allow_cancel: bool = True,
            allow_gui: bool = True):
    server = serve(directory, port=0, block=False,   # port 0 → ephemeral
                   allow_cancel=allow_cancel, allow_gui=allow_gui)
    try:
        yield f"http://127.0.0.1:{server.server_address[1]}"
    finally:
        server.shutdown()
        server.server_close()


def _get(url: str) -> bytes:
    return urllib.request.urlopen(url, timeout=5).read()


def _json(url: str):
    return json.loads(_get(url).decode("utf-8"))


def _post(url: str, headers: dict | None = None, *, timeout: float = 5):
    """POST, and give back ``(status, payload)`` for a refusal as well as a 200.

    The 5 s default suits a route that answers at once. A route that waits on
    something passes a ``timeout`` above that route's own bound, so the test
    reads the route's answer rather than the machine's speed (WP-2145).
    """
    request = urllib.request.Request(url, method="POST", data=b"",
                                     headers=headers or {})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def _post_json(url: str, payload):
    """POST a JSON body, and give back ``(status, answer)`` either way."""
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, method="POST", data=body,
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read().decode("utf-8"))


def _event_line(kind: str, t: float = 1.0, **data) -> str:
    return json.dumps({"record": "event", "v": "2", "t": t, "kind": kind,
                       "data": data}) + "\n"


#: The shape ``viz/snapshot.py`` writes, small enough to read. The route
#: serves bytes and parses nothing, so the fields only have to be the ones a
#: page asks for.
SNAPSHOT = {"schema": 1, "stage": "cell", "weighted": True, "n_points": 9,
            "n_drawn": 4, "two_theta": [10.0, 11.0, 12.0, 13.0],
            "y_obs": [1.0, 9.0, 2.0, 1.0], "y_calc": [1.0, 8.5, 2.0, 1.0],
            "y_bkg": [1.0, 1.0, 1.0, 1.0],
            "delta": [0.0, 0.5, 0.0, 0.0],
            "ticks": {"phase 0": {"two_theta": [11.0], "n_total": 1}},
            "statistics": {"rwp": 0.1, "gof": 1.1, "chi2": 1.2, "rp": 0.08,
                           "n_free": 3}}


def _make_run(directory: Path, *, events: str = "", status: dict | None = None,
              snapshot: bool = False, legacy: bool = False) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / runs.EVENTS_FILE).write_text(events, encoding="utf-8")
    if status is not None:
        (directory / runs.STATUS_FILE).write_text(json.dumps(status),
                                                  encoding="utf-8")
    if snapshot:
        (directory / runs.SNAPSHOT_FILE).write_text(json.dumps(SNAPSHOT),
                                                    encoding="utf-8")
    if legacy:
        # what a run recorded before WP-1402 left behind
        (directory / runs.LEGACY_SNAPSHOT_FILE).write_text(
            "<html>plotly goes here</html>", encoding="utf-8")
    return directory


# ----------------------------------------------------------------------
# the page
# ----------------------------------------------------------------------
def test_index_is_served(tmp_path):
    with _served(tmp_path) as base:
        page = _get(base + "/").decode()
        script = _get(base + "/watch.mjs").decode()
    assert "rietx watch" in page
    assert 'href="watch.css"' in page and 'src="watch.mjs"' in page
    assert "api/runs" in script
    # polling stops when nobody is looking
    assert "document.hidden" in script and "visibilitychange" in script


def test_every_file_the_page_asks_for_is_served_as_itself(tmp_path):
    """A stylesheet sent as ``text/html`` is a page with no styling and no
    error, and a module sent as anything but javascript is refused by the
    browser rather than run (WP-1430)."""
    with _served(tmp_path) as base:
        for name, kind in {**watch.STATIC_FILES, **watch.CHART_FILES}.items():
            response = urllib.request.urlopen(f"{base}/{name}", timeout=5)
            assert response.headers["Content-Type"] == kind, name
            assert response.read()
        # the modules the script imports resolve beside it, not at the root of
        # whatever directory this watcher was pointed at
        assert b"export function deltaRange" in _get(base + "/watch-core.mjs")
        assert b"export function pattern" in _get(base + "/rxplot.mjs")


def test_the_page_reports_the_root_it_scanned(tmp_path):
    """An empty list must not read as "no runs exist"."""
    with _served(tmp_path) as base:
        script = _get(base + "/watch.mjs").decode()
        payload = _json(base + "/api/runs")
    assert "scanned " in script
    assert payload["root"] == str(tmp_path.resolve())
    assert payload["runs"] == []


# ----------------------------------------------------------------------
# /api/runs
# ----------------------------------------------------------------------
def test_api_runs_lists_every_run_with_its_liveness(tmp_path):
    _make_run(tmp_path / "one", events=_event_line("fit_start"),
              status={"stage": "cell", "rwp": 0.11})
    _make_run(tmp_path / "two", events=_event_line("fit_start"))

    with _served(tmp_path) as base:
        payload = _json(base + "/api/runs")

    assert len(payload["runs"]) == 2
    labels = {r["label"] for r in payload["runs"]}
    assert labels == {"one", "two"}
    for row in payload["runs"]:
        assert row["liveness"]["state"] == "unknown"    # legacy, no lock
        assert row["liveness"]["evidence"]              # always says why
        assert row["legacy"] is True


def test_a_project_run_carries_the_gui_command(tmp_path):
    """A command a human copies, not a verb this app performs."""
    _make_run(tmp_path / "sample.rex" / "live",
              events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
    assert row["label"] == "sample.rex"
    assert row["gui_command"] == "rietx gui --scratch sample.rex"


def test_a_nested_project_command_names_the_path_not_the_name(tmp_path):
    """A command a human copies has to work from where they are standing."""
    _make_run(tmp_path / "campaign" / "sample.rex" / "live",
              events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
    # the separator is the platform's, and that is the point of the docstring
    # above: `campaign\sample.rex` is what a reader on Windows pastes into
    # their own shell, and `os.path.relpath` already hands them that (WP-1439).
    nested = os.path.join("campaign", "sample.rex")
    assert row["gui_command"] == f"rietx gui --scratch {nested}"


def test_a_plain_run_offers_no_gui_command(tmp_path):
    _make_run(tmp_path / "live-dir", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
    assert row["gui_command"] is None


def test_a_recorded_project_run_carries_the_gui_command_too(tmp_path):
    """The layout a real project writes, which is not the one above (WP-1428).

    ``Project.fit`` records one run *per fit*, at ``<name>.rex/live/<run id>``.
    The shape above — the run directory being ``live`` itself — is what a
    caller pointing ``LiveSession`` at a project's live directory leaves, and
    what every fixture in this file had been building.

    So the row builder's own test was passing on a layout no recorder produces,
    and the GUI command was ``None`` for every run a project had actually
    recorded. Both layouts are current and :func:`rietx.runs.project_of` is the
    one place that knows them; this is the half that had no writer.
    """
    _make_run(tmp_path / "sample.rex" / "live" / "20260917-120000-1234",
              events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
    assert row["gui_command"] == "rietx gui --scratch sample.rex"


def test_a_directory_that_is_a_run_opens_straight_onto_it(tmp_path):
    """`rietx watch ./live-dir` keeps working unchanged."""
    _make_run(tmp_path, events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        payload = _json(base + "/api/runs")
    assert len(payload["runs"]) == 1
    assert payload["single_run_id"] == payload["runs"][0]["run_id"]


def test_a_scanned_tree_has_no_single_run(tmp_path):
    _make_run(tmp_path / "only", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        payload = _json(base + "/api/runs")
    assert payload["single_run_id"] is None


# ----------------------------------------------------------------------
# /api/run/<id>
# ----------------------------------------------------------------------
def test_one_run_by_id(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"),
              status={"stage": "profile", "rwp": 0.08, "gof": 1.3})
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        one = _json(f"{base}/api/run/{row['run_id']}")
    assert one["label"] == "r"
    assert one["status"]["stage"] == "profile"
    assert one["liveness"]["state"] == "unknown"


def test_an_unknown_id_is_404_not_a_traversal(tmp_path):
    """An id is looked up in what the walk offered, never decoded into a path."""
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        for bogus in ("deadbeef", "..", "%2e%2e%2fetc"):
            with pytest.raises(urllib.error.HTTPError) as excinfo:
                _get(f"{base}/api/run/{bogus}")
            assert excinfo.value.code == 404


def test_an_unknown_subroute_is_404(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _get(f"{base}/api/run/{row['run_id']}/nonsense")
    assert excinfo.value.code == 404


# ----------------------------------------------------------------------
# /api/run/<id>/events
# ----------------------------------------------------------------------
def test_events_tail_is_incremental(tmp_path):
    """The whole-file refetch the old page did is what this replaces."""
    directory = _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        stem = f"{base}/api/run/{row['run_id']}/events"

        first = _json(stem + "?offset=0")
        assert [e["kind"] for e in first["events"]] == ["fit_start"]
        assert first["offset"] > 0 and first["reset"] is False

        again = _json(f"{stem}?offset={first['offset']}&inode={first['inode']}")
        assert again["events"] == []
        assert again["offset"] == first["offset"]

        with open(directory / runs.EVENTS_FILE, "a", encoding="utf-8",
                  newline="\n") as fh:
            fh.write(_event_line("stage_start", stage="cell"))
        more = _json(f"{stem}?offset={first['offset']}&inode={first['inode']}")
        assert [e["kind"] for e in more["events"]] == ["stage_start"]
        assert more["events"][0]["data"]["stage"] == "cell"


def test_a_truncated_log_tells_the_client_to_clear_its_pane(tmp_path):
    directory = _make_run(tmp_path / "r",
                          events=_event_line("fit_start") * 4)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        stem = f"{base}/api/run/{row['run_id']}/events"
        first = _json(stem + "?offset=0")

        # a second run in the same directory: LiveSession truncates the log
        (directory / runs.EVENTS_FILE).write_text(_event_line("stage_start"),
                                                  encoding="utf-8")
        after = _json(f"{stem}?offset={first['offset']}&inode={first['inode']}")
    assert after["reset"] is True
    assert [e["kind"] for e in after["events"]] == ["stage_start"]


def test_a_junk_offset_does_not_break_the_route(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        stem = f"{base}/api/run/{row['run_id']}/events"
        payload = _json(stem + "?offset=banana")
    assert [e["kind"] for e in payload["events"]] == ["fit_start"]


def test_a_bad_line_is_counted_over_the_wire(tmp_path):
    _make_run(tmp_path / "r",
              events=_event_line("fit_start") + "not json\n"
                     + _event_line("fit_end"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        payload = _json(f"{base}/api/run/{row['run_id']}/events?offset=0")
    assert payload["bad_lines"] == 1
    assert len(payload["events"]) == 2


# ----------------------------------------------------------------------
# /api/run/<id>/snapshot
# ----------------------------------------------------------------------
def test_the_snapshot_is_served_as_the_numbers(tmp_path):
    """JSON, not a page: the viewer draws it (WP-1402)."""
    _make_run(tmp_path / "r", events=_event_line("fit_start"), snapshot=True)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        assert row["has_snapshot"] is True
        assert row["has_legacy_snapshot"] is False
        body = _json(f"{base}/api/run/{row['run_id']}/snapshot")
    assert body["two_theta"] == SNAPSHOT["two_theta"]
    assert body["ticks"]["phase 0"]["n_total"] == 1


def test_a_legacy_page_is_still_served(tmp_path):
    """A ``fit.html`` already on disk still opens. Without this the
    back-compat claim in WP-1402 is untested prose."""
    _make_run(tmp_path / "r", events=_event_line("fit_start"), legacy=True)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        assert row["has_snapshot"] is False
        assert row["has_legacy_snapshot"] is True
        assert row["snapshot_mtime"] is not None      # dated off the page
        body = _get(f"{base}/api/run/{row['run_id']}/legacy")
    assert b"plotly goes here" in body


def test_the_page_draws_with_the_vendored_chart(tmp_path):
    """The chart module and its uPlot, out of the package byte for byte
    (WP-1461).

    Air-gapped, and with no optional dependency behind it: plotly needed the
    ``viz`` extra and 4.8 MB, and the page asks for it nowhere now.
    """
    with _served(tmp_path) as base:
        page = _get(base + "/").decode()
        script = _get(base + "/watch.mjs").decode()
        served = {name: _get(f"{base}/{name}") for name in watch.CHART_FILES}
        with pytest.raises(urllib.error.HTTPError) as gone:
            _get(base + "/plotly.js")
    for name, body in served.items():
        assert body == (watch.CHART_DIR / name).read_bytes(), name
    assert 'src="uPlot.iife.min.js"' in page and 'href="uPlot.min.css"' in page
    assert "from './rxplot.mjs'" in script
    assert "plotly" not in page.lower()
    assert gone.value.code == 404


def test_the_row_dates_the_snapshot_so_the_plot_can_be_redrawn(tmp_path):
    """A running fit rewrites its snapshot per stage. Without a date on the row
    the page has nothing to notice, and it shows the picture it opened with for
    the rest of the run."""
    directory = _make_run(tmp_path / "r", events=_event_line("fit_start"),
                          snapshot=True)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        was = row["snapshot_mtime"]
        assert was is not None
        snapshot = directory / runs.SNAPSHOT_FILE
        snapshot.write_text(json.dumps({**SNAPSHOT, "stage": "profile"}),
                            encoding="utf-8")
        os.utime(snapshot, (was + 60, was + 60))
        detail = _json(f"{base}/api/run/{row['run_id']}")
    assert detail["snapshot_mtime"] == was + 60


def test_a_run_with_no_snapshot_dates_nothing(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
    assert row["snapshot_mtime"] is None


def test_a_run_with_no_snapshot_says_so_rather_than_erroring_out(tmp_path):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        assert row["has_snapshot"] is False
        with pytest.raises(urllib.error.HTTPError) as excinfo:
            _get(f"{base}/api/run/{row['run_id']}/snapshot")
    assert excinfo.value.code == 404


# ----------------------------------------------------------------------
# the CLI, and what already linked at the bare names
# ----------------------------------------------------------------------
def test_the_directory_argument_is_optional(monkeypatch, tmp_path):
    """No argument scans the working directory."""
    seen = {}

    def fake_serve(directory, *, port, open_browser, allow_cancel, allow_gui):
        seen.update(directory=directory, port=port, allow_cancel=allow_cancel,
                    allow_gui=allow_gui)

    monkeypatch.setattr("rietx.watch.serve", fake_serve)
    main([])
    assert seen["directory"] is None and seen["port"] == 8899
    # both verbs ship on, and `--read-only` is how a reader declines them
    # (WP-1405 for stop, WP-1428 for the GUI launch)
    assert seen["allow_cancel"] is True and seen["allow_gui"] is True
    main(["somewhere", "--port", "1234"])
    assert seen["directory"] == "somewhere" and seen["port"] == 1234
    main(["--read-only"])
    assert seen["allow_cancel"] is False and seen["allow_gui"] is False


def test_the_module_is_still_runnable_with_dash_m():
    """``python -m rietx.watch`` was an ``if __name__`` guard in a module, and
    a package's ``__init__`` never fires one (WP-1430).

    So the entry moved to ``watch/__main__.py``, which nothing else imports and
    no other test reaches — a new file with no writer named at review is
    exactly WP-1076's shape. ``--help`` exercises every line of it and exits.
    """
    done = subprocess.run([sys.executable, "-m", "rietx.watch", "--help"],
                          capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert "--read-only" in done.stdout


def test_serve_defaults_to_the_working_directory(tmp_path, monkeypatch):
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    monkeypatch.chdir(tmp_path)
    with _served(None) as base:
        payload = _json(base + "/api/runs")
    assert payload["root"] == str(tmp_path.resolve())
    assert len(payload["runs"]) == 1


def test_serve_refuses_a_path_that_is_not_a_directory(tmp_path):
    missing = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        serve(missing, port=0, block=False)


def test_the_bare_static_names_still_resolve(tmp_path):
    """Anything already linking at fit.html or events.jsonl keeps working."""
    _make_run(tmp_path, events=_event_line("fit_start"), legacy=True,
              status={"stage": "cell", "rwp": 0.1})
    with _served(tmp_path) as base:
        assert b"plotly goes here" in _get(base + "/fit.html")
        assert b'"fit_start"' in _get(base + "/events.jsonl")
        assert json.loads(_get(base + "/status.json"))["stage"] == "cell"

# ----------------------------------------------------------------------
# the page's own script
# ----------------------------------------------------------------------
REPO_ROOT = Path(__file__).resolve().parents[1]

#: The node test file for ``watch-core.mjs``. Beside the suite rather than
#: beside the module it imports, because everything under ``src/rietx`` ships
#: in the wheel and a test case is not something to install.
CORE_TESTS = Path(__file__).with_name("watch_core.test.mjs")


def _node() -> str:
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not installed; the gui suite needs it too")
    return node


def test_the_page_files_parse_as_javascript():
    """The page is files now (WP-1430), and this is what it bought.

    A stray escape in the old python string cost the whole page while WP-1402
    was being written: the script threw on load, the run list sat at "scanning"
    forever, and every test in this file still passed, because they all assert
    substrings of a script nobody executed. ``node --check`` is the smallest
    thing that catches it, and it now reads the file the browser is served
    rather than a copy cut out of a string.

    Both modules, and as ESM — ``.mjs`` is what makes ``node --check`` parse
    ``import`` rather than reject it as CommonJS.
    """
    node = _node()
    for name in ("watch.mjs", "watch-core.mjs"):
        done = subprocess.run([node, "--check", str(watch.STATIC_DIR / name)],
                              capture_output=True, text=True, check=False)
        assert done.returncode == 0, done.stderr


def test_the_pure_half_of_the_page_is_unit_tested():
    """``node --test`` over ``watch-core.mjs``, run by the python suite.

    The page had no unit test of any kind until WP-1430, because none of it was
    importable: the Δ/σ ladder, the residual's outlier cut, the "NaN" guard and
    the panel rule were all checked by looking at a browser. Running it from
    here is what keeps it from going quiet — a node test nobody invokes is a
    file, not a check.
    """
    node = _node()
    # the reporter is named rather than inherited: node picks `spec` for a
    # pipe and `tap` for some versions, and the count below is read off it
    done = subprocess.run([node, "--test", "--test-reporter=tap",
                           str(CORE_TESTS)],
                          capture_output=True, text=True, check=False,
                          cwd=REPO_ROOT)
    assert done.returncode == 0, done.stdout + done.stderr
    # ...and it ran something: `node --test` exits 0 on a file of no cases
    match = re.search(r"^# pass (\d+)$", done.stdout, re.MULTILINE)
    assert match is not None, done.stdout
    assert int(match.group(1)) >= 6, done.stdout


#: The two files holding the GUI's drag-arithmetic cases, and the markers
#: bounding the block that has to be the same in both.
GUI_RESIZE_TESTS = REPO_ROOT / "gui/src/lib/resize.test.ts"
PORTED_OPEN = "// --- ported cases:"
PORTED_CLOSE = "// --- end ported cases ---"


def _ported_block(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    start = text.find(PORTED_OPEN)
    end = text.find(PORTED_CLOSE, start)
    assert start >= 0 and end >= 0, f"no ported-case block in {path}"
    return text[start:end + len(PORTED_CLOSE)]


def test_the_ported_drag_arithmetic_keeps_the_guis_cases():
    """`watch-core.mjs`'s `clampSize`/`dragged`/`axisOf` are the GUI's,
    copied because the page cannot import TypeScript (WP-1425).

    A copy that is not pinned is a copy that drifts, and the drift is silent:
    both suites stay green while the two implementations answer differently.
    So the *cases* are one block of text living in `gui/src/lib/resize.test.ts`
    and copied into `tests/watch_core.test.mjs`, and this compares them
    character for character. Editing the GUI's cases fails the page's copy
    until it follows, which is the whole point.

    It is a text comparison rather than a parsed one on purpose: a comment in
    the table says *why* a case is there, and a copy that kept the numbers and
    dropped the reasons would pass a parsed check.
    """
    assert _ported_block(GUI_RESIZE_TESTS) == _ported_block(CORE_TESTS)


#: Ids `watch.mjs` reaches for that `index.html` deliberately does not carry.
#: One entry, and it earns its place: `buildPicture` writes the plot div, the
#: legacy iframe or the no-picture note into `#picture` itself.
RUNTIME_IDS = {"plot"}


def test_every_element_the_script_reaches_for_exists():
    """The failure one page split across two files invites (WP-1430).

    `$('s-where')` against an `index.html` that says `s-path` is ``null``, and
    the page throws at its first poll with every python test in this file still
    green. ``node --check`` cannot see it, because it is not a syntax error,
    and the two defects of this shape before it each needed a real browser
    (WP-1402, WP-1405). The ids are cheap to compare, so compare them.
    """
    script = (watch.STATIC_DIR / "watch.mjs").read_text(encoding="utf-8")
    page = (watch.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    declared = set(re.findall(r'id="([^"]+)"', page))
    wanted = set(re.findall(r"""\$\(['"]([^'"]+)['"]\)""", script))
    # a guard that stops finding its own subject goes quiet rather than red
    assert len(wanted) > 15, f"the id helper moved; this reads $(): {wanted}"
    missing = wanted - declared - RUNTIME_IDS
    assert not missing, f"watch.mjs reaches for ids index.html has not: {missing}"
    # ...and the exception list stays honest: an id the page does declare has
    # no business being named as one the script builds
    assert not (RUNTIME_IDS & declared), RUNTIME_IDS & declared


def test_the_pages_files_reach_a_fresh_clone():
    """``*.html`` in ``.gitignore`` has swallowed a committed file five times
    (its own comments say so), and ``index.html`` was the sixth.

    Ignored, the wheel ships a watcher whose ``/`` is a 500 and every test on
    this machine stays green, because the file exists here. ``--no-index`` is
    what makes git read the rules at all: for a *tracked* file it otherwise
    answers from the index and never consults them (``tests/CLAUDE.md``).
    """
    for name in watch.STATIC_FILES:
        path = (watch.STATIC_DIR / name).relative_to(REPO_ROOT)
        done = subprocess.run(["git", "check-ignore", "--no-index", str(path)],
                              capture_output=True, text=True, check=False,
                              cwd=REPO_ROOT)
        assert done.returncode == 1, f"{path} is gitignored: {done.stdout}"


# ----------------------------------------------------------------------
# the one verb (WP-1405)
# ----------------------------------------------------------------------
def _live_run(directory: Path, **status) -> Path:
    """A run that reads ``running`` here: this process's pid, and no lock file.

    ``liveness_of``'s pid rung, which is the weaker of the two and the one a
    test can stand up without holding a flock for the duration.
    """
    fields = {"state": "running", "pid": os.getpid(),
              "host": socket.gethostname(), "stage": "cell"}
    fields.update(status)
    return _make_run(directory, events=_event_line("fit_start"), status=fields)


def _request_of(run_dir: Path) -> dict:
    return json.loads((run_dir / runs.CANCEL_FILE).read_text(encoding="utf-8"))


def test_a_post_asks_the_run_to_stop(tmp_path):
    """The acceptance, from the route's side: a request lands in the directory.

    Nothing here waits for a fit to notice — the route's whole job is to put
    the request where the recorder polling that directory will find it.
    """
    run_dir = _live_run(tmp_path / "r")
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/cancel")

    assert status == 200 and payload["requested"] is True
    body = _request_of(run_dir)
    assert body["request"] == runs.CANCEL_REQUEST
    # the server names the asker, never the client: a request that could name
    # itself anything would make `cancelled_by` a field the record cannot trust
    assert "watch" in body["who"]


def test_a_get_does_not_cancel(tmp_path):
    """A GET that cancels is one prefetching browser away from a bad day."""
    run_dir = _live_run(tmp_path / "r")
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        with pytest.raises(urllib.error.HTTPError) as err:
            _get(f"{base}/api/run/{row['run_id']}/cancel")

    assert err.value.code == 404
    assert not (run_dir / runs.CANCEL_FILE).exists()


@pytest.mark.parametrize("headers", [
    {"Origin": "https://evil.example"},
    {"Referer": "https://evil.example/page"},
])
def test_another_page_in_the_browser_cannot_stop_a_fit(tmp_path, headers):
    """POST is not enough on its own, and 127.0.0.1 is not either.

    A cross-origin POST with no body needs no preflight, so any page the reader
    has open can send this one, and a domain whose DNS answers ``127.0.0.1``
    reads the run ids too. ``gui/server.py`` has checked ``Origin``/``Referer``
    since it grew verbs; this is the same check on the one verb here.
    """
    run_dir = _live_run(tmp_path / "r")
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/cancel",
                                headers)

    assert status == 403, payload
    assert not (run_dir / runs.CANCEL_FILE).exists()


def test_read_only_refuses_and_says_so_in_the_run_list(tmp_path):
    """``--read-only``: the route refuses *and* the page draws no button.

    Both, because a button that only ever 403s is a worse answer than no
    button — and because the page cannot be the check.
    """
    run_dir = _live_run(tmp_path / "r")
    with _served(tmp_path, allow_cancel=False) as base:
        payload = _json(base + "/api/runs")
        status, body = _post(f"{base}/api/run/{payload['runs'][0]['run_id']}/cancel")

    assert payload["can_cancel"] is False
    assert status == 403 and "read-only" in body["error"]
    assert not (run_dir / runs.CANCEL_FILE).exists()
    with _served(tmp_path) as base:
        assert _json(base + "/api/runs")["can_cancel"] is True


def test_an_unknown_id_cannot_name_a_directory(tmp_path):
    """The id is looked up in what the walk offered, never decoded into a path.

    So the traversal question does not arise for this route the way it would
    for a hand-written one that built a path from the request — which is the
    property WP-1401 established and this verb inherits rather than re-checks.
    """
    _live_run(tmp_path / "r")
    outside = tmp_path.parent / "outside"
    outside.mkdir(exist_ok=True)
    with _served(tmp_path) as base:
        for bogus in ("deadbeef", "../../etc", "..%2f..%2fetc",
                      urllib.parse.quote(str(outside), safe="")):
            status, _ = _post(f"{base}/api/run/{bogus}/cancel")
            assert status == 404, bogus
    assert not (outside / runs.CANCEL_FILE).exists()


@pytest.mark.parametrize("why,status_fields", [
    ("a finished run", {"state": "done"}),
    ("a cancelled run", {"state": "cancelled"}),
    ("another host", {"state": "running", "host": "somebody-elses-laptop"}),
    ("a dead writer", {"state": "running", "pid": 2 ** 22}),
])
def test_only_a_run_being_written_here_is_stoppable(tmp_path, why,
                                                    status_fields):
    """A request into any of these would lie in the directory doing nothing."""
    fields = {"state": "running", "pid": os.getpid(),
              "host": socket.gethostname()}
    fields.update(status_fields)
    run_dir = _make_run(tmp_path / "r", events=_event_line("fit_start"),
                        status=fields)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/cancel")

    assert status == 409, why
    assert payload["state"] in ("done", "cancelled", "unknown", "abandoned")
    assert not (run_dir / runs.CANCEL_FILE).exists()


def test_a_run_that_stopped_recording_is_refused_by_name(tmp_path):
    """A latched recorder still holds its lock and still reads running.

    It is also the thing that would have read the request, so writing one would
    leave a button that did nothing. The refusal carries the reason the
    recorder gave.
    """
    run_dir = _live_run(tmp_path / "r", error="writing an event: OSError: full")
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/cancel")

    assert status == 409 and "stopped recording" in payload["error"]
    assert not (run_dir / runs.CANCEL_FILE).exists()


# ----------------------------------------------------------------------
# the second verb: open a copy in the GUI (WP-1428)

def _project_run(root: Path, name: str = "sample") -> Path:
    """A run in the layout a project records: ``<name>.rex/live/<run id>``."""
    return _make_run(root / f"{name}.rex" / "live" / "20260917-120000-1234",
                     events=_event_line("fit_start"))


def test_only_a_run_inside_a_project_can_be_opened(tmp_path):
    """A bare ``fit()`` has no project to copy, and the snapshot is a picture.

    Building a project out of one is not a thing, so the route says so rather
    than inventing a directory.
    """
    _make_run(tmp_path / "loose", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/gui")
    assert status == 409
    assert "not inside a project" in payload["error"]


def test_read_only_refuses_the_gui_launch_and_says_so_in_the_run_list(tmp_path):
    """Both halves, for the same reason the stop button has both.

    A button that only ever 403s is a worse answer than no button, and the page
    cannot be the check.
    """
    _project_run(tmp_path)
    with _served(tmp_path, allow_cancel=False, allow_gui=False) as base:
        payload = _json(base + "/api/runs")
        status, body = _post(
            f"{base}/api/run/{payload['runs'][0]['run_id']}/gui")
    assert payload["can_open_gui"] is False
    assert status == 403 and "read-only" in body["error"]
    with _served(tmp_path) as base:
        assert _json(base + "/api/runs")["can_open_gui"] is True


def test_an_unknown_id_cannot_name_a_project_to_open(tmp_path):
    """The id is looked up in what the walk offered, never decoded into a path.

    The same property the cancel route has, asserted for the verb that spawns a
    process rather than writing a file — where a path built from the request
    would be a directory this server never chose to serve.
    """
    _project_run(tmp_path)
    outside = tmp_path.parent / "outside.rex"
    (outside / "live").mkdir(parents=True, exist_ok=True)
    with _served(tmp_path) as base:
        for bogus in ("deadbeef", "../../etc", "..%2f..%2fetc",
                      urllib.parse.quote(str(outside), safe="")):
            status, _ = _post(f"{base}/api/run/{bogus}/gui")
            assert status == 404, bogus


def test_the_gui_verb_is_post_only(tmp_path):
    """A GET that spawned a process would be one prefetch per run in the list."""
    _project_run(tmp_path)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        try:
            _get(f"{base}/api/run/{row['run_id']}/gui")
            status = 200
        except urllib.error.HTTPError as err:
            status = err.code
    assert status == 404


def test_a_cross_origin_post_cannot_launch_a_gui(tmp_path):
    """``_origin_ok`` guards both verbs, and it is checked before the route."""
    _project_run(tmp_path)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/gui",
                                {"Host": "evil.example"})
    assert status == 403, payload


def test_the_launch_opens_a_copy_and_leaves_the_project_alone(tmp_path,
                                                              monkeypatch):
    """The acceptance, with the spawn faked so no GUI is started.

    What is asserted is the shape of the command and that the *source* project
    is what is handed to it. ``--scratch`` is the whole safety argument, so its
    absence is the failure this catches; the real spawn is
    ``test_a_real_gui_boots_on_a_scratch_copy`` below.
    """
    run_dir = _project_run(tmp_path)
    project = run_dir.parent.parent
    seen = {}

    def fake_launch(path):
        seen["project"] = path
        return {"url": "http://127.0.0.1:65000/", "port": 65000,
                "project": "/tmp/scratch/sample.rex", "pid": 4321,
                "scratch_of": str(path)}

    monkeypatch.setattr("rietx.watch._launch_gui", fake_launch)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/gui")

    assert status == 200, payload
    assert seen["project"] == project
    assert payload["url"] == "http://127.0.0.1:65000/"
    assert payload["run_id"] == row["run_id"]
    # the row's command and the route open the same thing, by the same flag
    assert row["gui_command"] == "rietx gui --scratch sample.rex"


def test_a_gui_that_will_not_boot_reports_why_it_would_not(tmp_path,
                                                           monkeypatch):
    """``gui.server.main`` prints ``rietx gui: <why>`` and exits 2.

    That sentence names seven different remedies between them, so it is passed
    through rather than replaced by a status code alone.
    """
    _project_run(tmp_path)
    monkeypatch.setattr(
        "rietx.watch._launch_gui",
        lambda path: {"error": "rietx gui: not a project directory"})
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        status, payload = _post(f"{base}/api/run/{row['run_id']}/gui")
    assert status == 502
    assert "not a project directory" in payload["error"]


@pytest.mark.slow
def test_a_real_gui_boots_on_a_scratch_copy_and_the_project_is_untouched(
        tmp_path):
    """The acceptance (WP-1428), with a real project and a real spawn.

    Everything above fakes :func:`~rietx.watch._launch_gui`, so nothing above
    would notice the flag going missing from the command line, the boot line
    changing shape, or the copy being made of the wrong directory. This starts
    the process.

    Three things are asserted and each was a way this could be wrong. The boot
    line names a ``project`` that is **not** the source, which is the copy
    doing its job. The source's ``history.jsonl`` is byte-identical afterwards,
    which is the promise the button makes. And the url serves, so the port in
    the boot line is the port the GUI is on rather than the one it asked for.
    """
    import hashlib

    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    structure, instrument = perturbed_models()
    pattern = _write_xye(tmp_path / "s.xye", synthesize())
    project = rx.Project.create(tmp_path / "sample.rex", pattern=pattern,
                                structure=structure, instrument=instrument)
    log = project.path / "history.jsonl"
    before = hashlib.sha256(log.read_bytes()).hexdigest()
    _make_run(project.live_dir / "20260917-120000-1234",
              events=_event_line("fit_start"))

    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        # The route holds the request until the child prints its boot line,
        # up to `GUI_BOOT_TIMEOUT`, then waits up to 5 s more to reap a child
        # that never did. The client outwaits both, so a slow boot reaches the
        # route's own answer, a 200 or a 502 naming why (WP-2145). A boot took
        # 11.7-14.9 s on a loaded Mac, against the client's old 5 s.
        status, boot = _post(f"{base}/api/run/{row['run_id']}/gui",
                             timeout=watch.GUI_BOOT_TIMEOUT + 10)

    assert status == 200, boot
    try:
        assert boot["url"].startswith("http://127.0.0.1:")
        # the copy, and not the directory the reader is watching
        assert Path(boot["project"]) != project.path
        assert Path(boot["project"]).name == project.path.name
        assert Path(boot["scratch_of"]) == project.path
        # The copy carries the source's history and then grows: `Project.open`
        # appends a head annotation before any verb runs, which is the whole
        # reason a copy has to exist. That the extra bytes are *here* and not
        # in the source is the feature, asserted rather than described.
        copied = (Path(boot["project"]) / "history.jsonl").read_bytes()
        assert copied.startswith(log.read_bytes())
        assert len(copied) > len(log.read_bytes())
        served = urllib.request.urlopen(boot["url"], timeout=20).read()
        assert served
    finally:
        os.kill(boot["pid"], signal.SIGTERM)

    # the whole point: the fit's project is what it was
    assert hashlib.sha256(log.read_bytes()).hexdigest() == before


# ----------------------------------------------------------------------
# what the launch does with the pipe (WP-1428)
#
# `stderr` is merged into the pipe the boot line arrives on, and nothing else
# ever drains it. Both halves of that have been wrong once, so these stand a
# script in for the GUI and drive the three cases a real one cannot be made to
# produce on demand.

def _launch_with(monkeypatch, script: Path, project: Path) -> dict:
    monkeypatch.setattr(watch, "_gui_argv",
                        lambda _project: [sys.executable, str(script)])
    return watch._launch_gui(project)


def test_a_warning_before_the_boot_line_is_not_read_as_a_failure(tmp_path,
                                                                 monkeypatch):
    """A reader that takes the first line and trusts it gets this wrong.

    Whatever the interpreter says before ``serve`` prints — a dependency's
    deprecation warning, anything a site hook emits — arrives on this pipe
    first. The GUI would be serving and the page would report a failure.
    """
    script = tmp_path / "noisy.py"
    script.write_text(
        "import json, sys, time\n"
        "print('DeprecationWarning: something', file=sys.stderr, flush=True)\n"
        "print('and a second line', file=sys.stderr, flush=True)\n"
        "print(json.dumps({'url': 'http://127.0.0.1:65001/', 'port': 65001,"
        " 'project': '/tmp/copy', 'pid': 1, 'scratch_of': '/tmp/src'}),"
        " flush=True)\n"
        "time.sleep(30)\n", encoding="utf-8")
    boot = _launch_with(monkeypatch, script, tmp_path)
    try:
        assert boot.get("url") == "http://127.0.0.1:65001/", boot
        assert boot["port"] == 65001
    finally:
        watch._SPAWNED[-1].kill()


def test_a_gui_that_says_why_it_failed_has_that_passed_through(tmp_path,
                                                               monkeypatch):
    """``gui.server.main`` prints ``rietx gui: <why>`` and exits 2.

    Those refusal messages name seven different remedies between them, so the
    sentence is the useful half of the answer. The *last* line, because a
    traceback's last line is its exception.
    """
    script = tmp_path / "failing.py"
    script.write_text(
        "import sys\n"
        "print('Traceback (most recent call last):', file=sys.stderr,"
        " flush=True)\n"
        "print('  File \"x.py\", line 1', file=sys.stderr, flush=True)\n"
        "print('rietx gui: not a project directory: /nope', flush=True)\n"
        "raise SystemExit(2)\n", encoding="utf-8")
    boot = _launch_with(monkeypatch, script, tmp_path)
    assert "not a project directory" in boot["error"], boot
    assert "url" not in boot


def test_a_gui_that_never_reports_a_port_is_killed_rather_than_left(
        tmp_path, monkeypatch):
    """``start_new_session`` means a stray one outlives the watcher.

    It would hold a port and a scratch copy nobody can find, so the timeout
    reaps it rather than returning and forgetting it.
    """
    script = tmp_path / "silent.py"
    script.write_text("import time\ntime.sleep(120)\n", encoding="utf-8")
    monkeypatch.setattr(watch, "GUI_BOOT_TIMEOUT", 1.0)
    before = list(watch._SPAWNED)
    boot = _launch_with(monkeypatch, script, tmp_path)
    assert "did not report a port" in boot["error"], boot
    (proc,) = [p for p in watch._SPAWNED if p not in before]
    assert proc.poll() is not None, "the silent GUI was left running"


def test_the_closed_dialog_is_not_a_sheet_over_the_page():
    """An id selector outranks the browser's own ``[hidden] {display:none}``.

    Without the override the *closed* dialog is an invisible full-page overlay
    that swallows every click, including the one that opens it. Nothing in
    python can see that and ``node --check`` parses it happily; it took a real
    browser and a real click. This is the cheapest guard that would have.
    """
    css = (watch.STATIC_DIR / "watch.css").read_text(encoding="utf-8")
    assert "#confirm[hidden] { display:none; }" in css


def test_the_dialog_says_what_a_click_does_to_the_other_process():
    """The sharpest fact in the track belongs in the dialog, not a footnote."""
    page = (watch.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    script = (watch.STATIC_DIR / "watch.mjs").read_text(encoding="utf-8")
    assert "RefinementCancelled" in page
    assert "traceback" in page
    # ...and no keyboard shortcut reaches the button. Read off the code and not
    # the comments, which say the same thing in words and would otherwise be
    # what passes this.
    #
    # WP-1425 gave the two grips an ARIA splitter keyboard, so the guard is no
    # longer "this page listens for no key at all". It is the claim that was
    # always meant: no key listener sits anywhere a stray press could reach the
    # stop verb from. A listener on `document` or `window` could; one on a grip,
    # which has to be focused first and whose Enter collapses a pane, could not.
    code = "\n".join(line for line in script.splitlines()
                     if not line.lstrip().startswith("//"))
    listeners = re.findall(r"(\w+)\.addEventListener\('(key\w+)'", code)
    assert listeners, "the guard found no key listener at all to check"
    assert {target for target, _ in listeners} == {"grip"}, listeners
    for shortcut in ("onkeydown", "onkeyup", "onkeypress", "autofocus",
                     ".focus("):
        assert shortcut not in code, shortcut
    assert "autofocus" not in page, "the dialog's buttons take no focus"


def test_the_payload_carries_what_the_page_cannot_know(tmp_path, monkeypatch):
    """The three facts that were ``@TOKEN@`` substitutions until WP-1430.

    A file cannot carry a token, so the page reads them off the ``api/runs``
    it already fetches first. Each comes from its one authority: a literal
    ``.rex`` here would be a second answer, and the literal would read as
    working right up until somebody looked at it.

    Every *curve* colour left in WP-1429 and the reflection rows' followed in
    WP-1438: all of them are custom properties the page reads off its own root
    element, and what rides here in their place is the theme *choice*, the one
    thing here a person changes while the page is open. A colour that stayed
    would be the one this payload was worst at: it carried a single list for
    both themes, so a light page drew its tick rows in the dark set.
    """
    from rietx._about import DIST_NAME, PROJECT_SUFFIX
    from rietx.viz import theme as theme_mod

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    with _served(tmp_path) as base:
        page = _json(base + "/api/runs")["page"]
    assert page == {
        "suffix": PROJECT_SUFFIX, "dist": DIST_NAME, "theme": "system",
        # the control's three, glyph and sentence, so the page draws the
        # GUI's and not a second copy of them (WP-1438)
        "themes": [{"choice": c, "glyph": theme_mod.THEME_GLYPHS[c],
                    "title": theme_mod.THEME_TITLES[c]}
                   for c in theme_mod.THEME_CHOICES]}
    # and no token survived the move into the files
    for name in watch.STATIC_FILES:
        text = (watch.STATIC_DIR / name).read_text(encoding="utf-8")
        for token in ("@SUFFIX@", "@DIST@", "@HUE@"):
            assert token not in text, f"{token} in {name}"


def test_the_page_follows_the_theme_the_gui_stored(tmp_path, monkeypatch):
    """The GUI writes the choice, both Python pages read it (WP-1429).

    One writer per fact: the setting lives in the state directory beside the
    recent list, where it survives the project, the port and the browser
    profile (WP-1044), and nothing here writes it.  Every poll carries it, so a
    choice made in the GUI reaches an open watch page without a reload.
    """
    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text(
        json.dumps({"ui": {"theme": "light", "unrelated": 3}}), encoding="utf-8")
    with _served(tmp_path) as base:
        assert _json(base + "/api/runs")["page"]["theme"] == "light"
        # a hand-mangled file is `system`, never an error: no setting here is
        # worth refusing to draw the page over
        (state / "settings.json").write_text("{not json", encoding="utf-8")
        assert _json(base + "/api/runs")["page"]["theme"] == "system"


def test_the_stylesheet_is_served_out_of_the_package(tmp_path):
    """`tokens.css` is emitted, never read off disk (WP-1429).

    `viz/chart.py` one rank down: a value the wheel has to serve cannot live
    in the GUI workspace, which is a build input and is not installed.  So the
    route renders the emitter and `gui/src/tokens.css` is the generated copy,
    not the source.
    """
    from rietx.viz import theme

    with _served(tmp_path) as base:
        with urllib.request.urlopen(base + theme.CSS_ROUTE, timeout=5) as r:
            body, content_type = r.read(), r.headers["Content-Type"]
    assert body.decode("utf-8") == theme.tokens_css()
    assert content_type == theme.CSS_CONTENT_TYPE
    # the page links it, and before its own stylesheet: `watch.css` reads the
    # tokens and a cascade that has not declared them yet has nothing to read
    page = (watch.STATIC_DIR / "index.html").read_text(encoding="utf-8")
    assert page.index('href="tokens.css"') < page.index('href="watch.css"')


def test_no_colour_literal_is_left_in_the_page(tmp_path):
    """Every colour on this page is a token, or the page is a second answer.

    The exemption is the confirm dialog's scrim, and it is one because a scrim
    *darkens* whatever is under it: black in both themes, as the GUI's own two
    backdrops are (`Browse.svelte`, `Palette.svelte`).  The picture needs no
    exemption: uPlot leaves its canvas transparent, so the page's own
    background shows through, which is what makes the picture part of the page
    rather than a card on it.
    """
    allowed = {"rgba(0,0,0,0.62)"}
    # a *literal* — only digits inside the parentheses.  A `color-mix` over a
    # token is the opposite of a colour this page chose, and a looser pattern
    # would flag the machinery that exists to keep the choice in one place.
    literal = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([\d.,\s%]*\)")
    for name in ("watch.css", "watch.mjs", "watch-core.mjs", "index.html"):
        text = (watch.STATIC_DIR / name).read_text(encoding="utf-8")
        found = set(literal.findall(text))
        assert found <= allowed, f"{name} still declares {sorted(found - allowed)}"


# ----------------------------------------------------------------------
# what a poll costs (WP-1427)
# ----------------------------------------------------------------------
def test_the_tail_route_caps_at_the_limit_the_page_asks_for(tmp_path):
    """The console is a tail over a pane of fixed length, so the page names
    the cap and the route honours it.

    Without it, clicking a job that has been running a few minutes delivers
    every event of it in one response: 60 000 lines parsed and built into
    ``<div>``s to keep 2000 of them.
    """
    events = "".join(_event_line("eval", t=float(i), i=i) for i in range(300))
    _make_run(tmp_path / "r", events=events)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        url = f"{base}/api/run/{row['run_id']}/events?offset=0"
        capped = _json(url + "&limit=25")
        whole = _json(url)

    assert len(capped["events"]) == 25
    assert capped["skipped"] == 275
    assert [e["data"]["i"] for e in capped["events"]] == list(range(275, 300))
    # the offset is the same either way, so a capped poll still reaches the end
    assert capped["offset"] == whole["offset"]
    assert len(whole["events"]) == 300 and whole["skipped"] == 0


@pytest.mark.parametrize("query", ["", "&limit=0", "&limit=-5", "&limit=lots"])
def test_an_absent_or_junk_limit_is_no_cap(tmp_path, query):
    """What this route did before WP-1427, for anything that is not a count."""
    events = "".join(_event_line("eval", t=float(i), i=i) for i in range(40))
    _make_run(tmp_path / "r", events=events)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        tail = _json(f"{base}/api/run/{row['run_id']}/events?offset=0{query}")
    assert len(tail["events"]) == 40
    assert tail["skipped"] == 0



def test_a_cold_open_asks_for_the_end_and_gets_it(tmp_path):
    """`end=1` is the client saying "this is my first ask" (WP-1438).

    The route infers nothing: `offset=0` without it still reads from the start,
    because a reader tailing a run from its beginning is asking for exactly
    that and a route that guessed would make the two requests the same one.

    The log has to be bigger than one read window or there is nothing to seek
    over — `tail_events`' window is 4 MiB and the route does not parameterise
    it, so the fixture is ~4.5 MB of it. The window itself is varied where it
    can be, in `test_runs.py`.
    """
    events = "".join(_event_line("eval", t=float(i), i=i) for i in range(60000))
    assert len(events.encode()) > (4 << 20), "the fixture fits in one window"
    _make_run(tmp_path / "r", events=events)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        stem = f"{base}/api/run/{row['run_id']}/events"
        cold = _json(f"{stem}?offset=0&limit=20&end=1")
        warm = _json(f"{stem}?offset=0&limit=20")
        after = _json(f"{stem}?offset={cold['offset']}&limit=20")

    # the newest twenty, and the offset is the whole file, so the poll after
    # the cold one is an ordinary one that has nothing to catch up on
    assert [e["data"]["i"] for e in cold["events"]] == list(range(59980, 60000))
    assert cold["offset"] == cold["size"]
    assert after["events"] == []
    # ...and it says there is more above without counting what it did not read
    assert cold["skipped_bytes"] > 0

    # the same request without the word starts at the beginning, as it always
    # did: one window of the log, whose newest twenty are nowhere near the end
    assert warm["skipped_bytes"] == 0
    assert warm["events"][-1]["data"]["i"] < 59980
    assert warm["offset"] < warm["size"]


def _server_timing(url: str) -> dict:
    """The response's ``Server-Timing`` marks, as ``{phase: milliseconds}``."""
    with urllib.request.urlopen(url, timeout=5) as response:
        raw = response.headers.get("Server-Timing") or ""
    out = {}
    for part in raw.split(","):
        name, _, dur = part.strip().partition(";dur=")
        if name:
            out[name] = float(dur)
    return out


def test_every_route_on_the_poll_says_what_it_cost(tmp_path):
    """``Server-Timing``, which is the documented header for exactly this.

    A browser shows it beside the request in the network panel, and this test
    reads the same numbers with no profiler. The phases are named for what they
    do rather than for the function doing it, so a rewrite of :class:`_RunIndex`
    keeps ``walk`` meaning the walk.
    """
    _make_run(tmp_path / "r", events=_event_line("fit_start"), snapshot=True)
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]
        run_id = row["run_id"]
        listing = _server_timing(base + "/api/runs")
        events = _server_timing(f"{base}/api/run/{run_id}/events?offset=0")
        snapshot = _server_timing(f"{base}/api/run/{run_id}/snapshot")

    assert set(listing) == {"walk", "rows", "serialize"}
    assert set(events) == {"walk", "tail", "serialize"}
    assert set(snapshot) == {"walk", "read"}
    # a mark is a duration and not a clock: negative or absent is a bug in the
    # instrument, and this is the only assertion worth making about the value
    assert all(v >= 0.0 for marks in (listing, events, snapshot)
               for v in marks.values())


def test_a_marks_header_is_about_one_request_and_not_the_connection(tmp_path):
    """Keep-alive serves many requests through one handler object.

    The marks list is built per request and must be cleared per request, or the
    second response on a connection carries the first one's numbers as well as
    its own — a header that grows for as long as the browser holds the socket.
    """
    _make_run(tmp_path / "r", events=_event_line("fit_start"))
    with _served(tmp_path) as base:
        host, port = urllib.parse.urlsplit(base).netloc.split(":")
        conn = http.client.HTTPConnection(host, int(port), timeout=5)
        try:
            seen = []
            for _ in range(3):
                conn.request("GET", "/api/runs")
                response = conn.getresponse()
                response.read()
                seen.append(response.headers.get("Server-Timing") or "")
        finally:
            conn.close()
    for header in seen:
        assert [p.split(";")[0].strip() for p in header.split(",")] == [
            "walk", "rows", "serialize"]


def _conditional(base: str, etag: str | None = None):
    """``GET /api/runs``, optionally conditional. Returns status, body, ETag."""
    headers = {"If-None-Match": etag} if etag else {}
    request = urllib.request.Request(base + "/api/runs", headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=5) as response:
            return response.status, response.read(), response.headers.get("ETag")
    except urllib.error.HTTPError as err:
        return err.code, err.read(), err.headers.get("ETag")


def test_a_poll_where_nothing_changed_is_two_header_lines(tmp_path):
    """``ETag``/``If-None-Match``, which is the documented mechanism.

    The walk and the rows are paid for either way — the digest is of the body,
    so the body has to exist. What a 304 saves is the wire and the page's own
    parse and patch, which measured 3.1 ms of main thread and 222 kB an idle
    poll on 200 runs, once a second for as long as a tab is open (WP-1427).
    """
    _make_run(tmp_path / "r", events=_event_line("fit_start"),
              status={"state": "done", "stage": "cell", "rwp": 0.1})
    with _served(tmp_path) as base:
        status, body, etag = _conditional(base)
        assert status == 200 and etag
        again, empty, same = _conditional(base, etag)

    assert again == 304
    assert empty == b""
    assert same == etag


def test_a_run_that_moved_invalidates_the_tag(tmp_path):
    """A 304 must mean *this list*, not *a list*."""
    run = _make_run(tmp_path / "r", events=_event_line("fit_start"),
                    status={"state": "running", "stage": "cell", "rwp": 0.4})
    with _served(tmp_path) as base:
        _, _, etag = _conditional(base)
        assert _conditional(base, etag)[0] == 304

        # a different length from the first write: ``read_run`` caches on
        # (inode, size, mtime_ns), and a Linux mtime ticks only every few ms,
        # so a same-length rewrite inside one tick reads back as the old row
        (run / runs.STATUS_FILE).write_text(
            json.dumps({"state": "running", "stage": "microstrain", "rwp": 0.2}),
            encoding="utf-8")
        # past the index TTL, which is what bounds how soon a write is seen;
        # the tag is about the payload and the TTL is about the walk
        time.sleep(watch.INDEX_TTL_SECONDS + 0.05)
        status, body, moved = _conditional(base, etag)

    assert status == 200
    assert moved != etag
    assert json.loads(body)["runs"][0]["status"]["stage"] == "microstrain"


def test_a_row_carries_no_clock_of_its_own(tmp_path):
    """``heartbeat_age`` is ``now - heartbeat``, so it moved on every poll and
    made every idle answer a different one — which is the whole of what the
    tag above has to decide. Nothing read it (WP-1427). The heartbeat it came
    from is in ``status`` already, so nothing was lost.
    """
    _make_run(tmp_path / "r", events=_event_line("fit_start"),
              status={"state": "running", "pid": os.getpid(),
                      "host": socket.gethostname(), "heartbeat": 1.0})
    with _served(tmp_path) as base:
        (row,) = _json(base + "/api/runs")["runs"]

    assert set(row["liveness"]) == {"state", "evidence"}
    assert row["status"]["heartbeat"] == 1.0


def test_the_two_local_servers_allow_the_same_hosts():
    """One security rule, written twice, so pin the copies together.

    ``watch/`` cannot import ``gui/server.py``: that module reaches
    ``gui/session.py`` and the whole refinement graph behind it, and a viewer
    importing the watcher pays for nothing it will not draw. So the host set is
    duplicated on purpose. What must not happen is one of them being tightened
    and the other left, which is the ordinary way a repeated rule rots.
    """
    from rietx.gui import server as gui_server

    assert watch._ALLOWED_HOSTS == gui_server._ALLOWED_HOSTS


# ----------------------------------------------------------------------
# the theme is settable from here too (WP-1438)
# ----------------------------------------------------------------------
def test_a_choice_is_stored_and_read_back_through_one_function(monkeypatch,
                                                               tmp_path):
    """WP-1429 made the GUI the one writer, and the consequence was measured
    on this machine: ``settings.json`` held ``light``, and a person running a
    fit from a script and watching it here had no way to change it without
    opening an application they were not using.
    """
    from rietx.viz import theme as theme_mod

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    assert theme_mod.theme_choice() == "system"
    for choice in theme_mod.THEME_CHOICES:
        assert theme_mod.set_theme_choice(choice) == choice
        assert theme_mod.theme_choice() == choice


def test_a_theme_that_does_not_exist_is_refused_rather_than_stored(monkeypatch,
                                                                   tmp_path):
    """A read repairs somebody's file; a write performs somebody's verb.

    Storing it would leave ``settings.json`` saying something every reader
    turns back into ``system``.
    """
    from rietx.viz import theme as theme_mod

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    theme_mod.set_theme_choice("dark")
    with pytest.raises(ValueError, match="not a theme"):
        theme_mod.set_theme_choice("neon")
    assert theme_mod.theme_choice() == "dark"


def test_the_rest_of_the_settings_file_survives_a_theme(monkeypatch, tmp_path):
    """`ui` is an open dict and the file may carry keys beside it.

    This module knows about one key of one of them, so everything else in the
    file is somebody else's and comes back byte for byte.
    """
    from rietx.viz import theme as theme_mod

    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text(json.dumps(
        {"recent": ["/a.rex", "/b.rex"],
         "ui": {"theme": "light", "simple": True}}), encoding="utf-8")
    theme_mod.set_theme_choice("dark")
    stored = json.loads((state / "settings.json").read_text(encoding="utf-8"))
    assert stored == {"recent": ["/a.rex", "/b.rex"],
                      "ui": {"theme": "dark", "simple": True}}


def test_an_unreadable_settings_file_is_replaced_rather_than_fatal(monkeypatch,
                                                                   tmp_path):
    """The grounds :func:`theme_choice` answers ``system`` for one, the other
    way round: refusing to record a preference because of an unrelated
    corruption is the worse failure.
    """
    from rietx.viz import theme as theme_mod

    state = tmp_path / "state"
    state.mkdir()
    monkeypatch.setenv(STATE_DIR_ENV, str(state))
    (state / "settings.json").write_text("{not json", encoding="utf-8")
    assert theme_mod.set_theme_choice("dark") == "dark"
    assert theme_mod.theme_choice() == "dark"


def test_the_route_stores_a_theme_and_says_what_it_stored(monkeypatch,
                                                          tmp_path):
    from rietx.viz import theme as theme_mod

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    with _served(tmp_path) as base:
        status, answer = _post_json(base + "/api/theme", {"theme": "dark"})
    assert (status, answer) == (200, {"theme": "dark"})
    assert theme_mod.theme_choice() == "dark"


def test_the_route_refuses_a_theme_that_is_not_one(monkeypatch, tmp_path):
    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    with _served(tmp_path) as base:
        bad, answer = _post_json(base + "/api/theme", {"theme": "neon"})
        empty = _post_json(base + "/api/theme", {})[0]
    assert bad == 400 and "not a theme" in answer["error"]
    assert empty == 400


def test_read_only_still_lets_the_reader_choose_a_theme(monkeypatch, tmp_path):
    """``--read-only`` fences the *run*: no stop button, no GUI launch, which
    is what its own message says. A theme is a fact about the reader and the
    room they are in, it is stored in the reader's own state directory, and a
    page that could not be made legible by the person reading it would be a
    strange thing to call read-only.
    """
    from rietx.viz import theme as theme_mod

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path / "state"))
    with _served(tmp_path, allow_cancel=False, allow_gui=False) as base:
        status, answer = _post_json(base + "/api/theme", {"theme": "dark"})
    assert (status, answer) == (200, {"theme": "dark"})
    assert theme_mod.theme_choice() == "dark"
