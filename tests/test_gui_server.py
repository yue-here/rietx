"""WP-1008 — the GUI session model and its HTTP surface.

Against a **real** server on an ephemeral port, because the things that break in
a server are the things a direct call to the session cannot see: header checks,
query parsing, status codes, a streaming response that never ends.  One real
refinement runs in the module fixture (a synthetic LaB6 pattern under the real
``mccusker_default`` preset, well under a second) and everything that needs a
fitted state shares it.

The **state machine** is tested with the refinement stubbed instead, and that is
deliberate: "does a mutating verb 409 while a stage is in flight" is a question
about the session's lock and its worker, and answering it against a real fit
would mean racing a solver — a test that passes because it won a race is not a
test.  Cancellation *of a real fit* is WP-1006's ground (``test_run_control``);
what is new here is that the HTTP verb reaches the token and the run record says
what the run left behind.
"""

from __future__ import annotations

import json
import threading
import time
from http.client import HTTPConnection
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.gui import ROUTES, UPLOAD_ROUTES, GuiSession, build_server
from rietx.gui.imports import UPLOAD_DIR_PREFIX
from rietx.gui.session import RESERVED_ROUTES, GuiError
from rietx.history.events import read_events
from tests.test_project import _write_xye
from tests.test_refine_synthetic import perturbed_models, synthesize

pytestmark = pytest.mark.xdist_group("gui-server")

OUT = Path(__file__).parent / "output"


# ----------------------------------------------------------------------
# fixtures
# ----------------------------------------------------------------------
@pytest.fixture(scope="module")
def pattern_file(tmp_path_factory):
    return _write_xye(tmp_path_factory.mktemp("gui-data") / "synth.xye", synthesize())


@pytest.fixture(scope="module")
def poisson_pattern_file(tmp_path_factory):
    """The same synthetic pattern with its esd column withheld.

    ``_write_xye``'s esds are 1.3× the Poisson fallback on purpose, so a fit of
    this file is distinguishable from a fit of ``pattern_file`` rather than
    merely differently labelled.
    """
    return _write_xye(tmp_path_factory.mktemp("gui-poisson") / "no_esd.xye",
                      synthesize(), with_sigma=False)


@pytest.fixture(scope="module")
def state_dir(tmp_path_factory):
    """A recent-projects store that is never the user's real home."""
    return tmp_path_factory.mktemp("gui-state")


def _project(root: Path, pattern_file: Path, **kw) -> rx.Project:
    structure, ins = perturbed_models()
    return rx.Project.create(root, pattern=pattern_file, structure=structure,
                            instrument=ins, plan="mccusker_default", **kw)


def _open(session: GuiSession, root: Path, pattern_file: Path, **kw) -> rx.Project:
    """Create a project and open it in ``session``, returning **its** object.

    Returning ``session.project`` rather than what ``create`` handed back is the
    point: ``open`` re-reads the directory, so the created object is a second,
    immediately stale view of the same files — and asserting against it passes by
    accident for as long as the two agree.
    """
    _project(root, pattern_file, **kw)
    session.project_open({"path": str(root)})
    return session.project


def _start(session: GuiSession):
    """Serve ``session`` on an ephemeral port; the poll interval is the teardown
    cost, and 0.5 s × every fixture in this module would dominate its runtime."""
    httpd = build_server(session, port=0)
    threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.02},
                     daemon=True).start()
    return httpd


class Client:
    """A tiny HTTP client: returns ``(status, payload)`` and keeps no state."""

    def __init__(self, port: int) -> None:
        self.port = port

    def request(self, method: str, path: str, body: dict | None = None,
                headers: dict | None = None) -> tuple[int, dict]:
        conn = HTTPConnection("127.0.0.1", self.port, timeout=60)
        payload = None if body is None else json.dumps(body).encode()
        head = {"Host": f"127.0.0.1:{self.port}"}
        if payload is not None:
            head["Content-Type"] = "application/json"
        head.update(headers or {})
        try:
            conn.request(method, path, body=payload, headers=head)
            response = conn.getresponse()
            raw = response.read()
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, {"raw": raw.decode("utf-8", "replace")}
        finally:
            conn.close()

    def get(self, path, **kw):
        return self.request("GET", path, **kw)

    def post(self, path, body=None, **kw):
        return self.request("POST", path, body or {}, **kw)

    def patch(self, path, body):
        return self.request("PATCH", path, body)

    def put(self, path, body):
        return self.request("PUT", path, body)

    def upload(self, kind: str, data: bytes | None = None, *, declared: int | None
               = None, **query) -> tuple[int, dict]:
        """``POST /api/upload/<kind>`` — the one body in this surface that is
        not JSON.  ``declared`` lies about ``Content-Length`` on purpose, which
        is the only way to test the cap without sending 64 MB."""
        from urllib.parse import urlencode

        conn = HTTPConnection("127.0.0.1", self.port, timeout=60)
        head = {"Host": f"127.0.0.1:{self.port}",
                "Content-Type": "application/octet-stream",
                "Content-Length": str(len(data or b"") if declared is None
                                      else declared)}
        path = f"/api/upload/{kind}"
        if "token" in query:            # the wire name for a staged upload
            query["upload"] = query.pop("token")
        if query:
            path += "?" + urlencode({k: v for k, v in query.items()
                                     if v is not None})
        try:
            conn.request("POST", path, body=data or b"", headers=head)
            response = conn.getresponse()
            raw = response.read()
            try:
                return response.status, json.loads(raw)
            except ValueError:
                return response.status, {"raw": raw.decode("utf-8", "replace")}
        finally:
            conn.close()


@pytest.fixture
def blank(state_dir):
    """A server with no project open — the state the app boots in."""
    session = GuiSession(state_dir=state_dir)
    httpd = _start(session)
    try:
        yield session, Client(httpd.server_address[1])
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


@pytest.fixture(scope="module")
def fitted(tmp_path_factory, pattern_file, state_dir):
    """One real refinement driven end-to-end over HTTP, shared by the readers."""
    project = _project(tmp_path_factory.mktemp("gui-fit") / "sample.rex", pattern_file)
    session = GuiSession(project, state_dir=state_dir)
    httpd = _start(session)
    client = Client(httpd.server_address[1])

    status, run = client.post("/api/run", {"kind": "fit"})
    assert status == 200, run
    assert run["state"] == "running"
    _wait_idle(client)
    state = client.get("/api/run/state")[1]
    assert state["run"]["status"] == "converged", state
    # the visual gate the numbers cannot be (CLAUDE.md, Tests)
    OUT.mkdir(exist_ok=True)
    project.refinement.result_.plot(path=str(OUT / "gui_server_fit.png"))
    try:
        yield session, client, project
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


def _wait_idle(client: Client, timeout: float = 120.0) -> dict:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        state = client.get("/api/run/state")[1]
        if state["state"] == "idle":
            return state
        time.sleep(0.02)
    raise AssertionError("run did not finish")


# ----------------------------------------------------------------------
# the surface itself
# ----------------------------------------------------------------------
def test_capabilities_is_the_package_answer_verbatim(blank):
    """One authority: the route must not paraphrase ``rietx.capabilities()``."""
    _, client = blank
    status, payload = client.get("/api/capabilities")
    assert status == 200
    assert payload == rx.capabilities().model_dump(mode="json")


def test_version_and_recent_work_without_a_project(blank):
    _, client = blank
    status, payload = client.get("/api/version")
    assert status == 200 and payload["package_version"] == rx.capabilities(
    ).package_version
    assert payload["project"] is None
    assert client.get("/api/recent")[0] == 200


@pytest.fixture
def app_settings(tmp_path):
    """A server whose **app** state directory is this test's own.

    The settings store is a file in that directory and the module's ``blank``
    shares one across the whole module — so a test that asserts an empty store
    over it would be asserting test *order*, which ``pytest-randomly`` falsifies
    sooner or later.  Its own directory is the fix that does not depend on
    anyone remembering to clean up.
    """
    session = GuiSession(state_dir=tmp_path / "state")
    httpd = _start(session)
    try:
        yield session, Client(httpd.server_address[1])
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


def test_app_settings_are_the_persons_and_outlive_the_project(app_settings, tmp_path,
                                                              pattern_file):
    """WP-1044 — `/api/settings` is a second `ui` dict, at app scope.

    The line between the two is what the key is *about*: a column width is a
    fact about a project (it has four phases), a theme is a fact about the
    person.  Putting the theme in ``ProjectDoc.ui`` made ``readUi`` re-read it
    per project, so choosing dark and opening a second project came back
    ``system`` — measured in a browser, which is where it was reported.
    """
    session, client = app_settings
    assert client.get("/api/settings") == (200, {"ui": {}})

    status, payload = client.post("/api/settings", {"ui": {"theme": "dark"}})
    assert status == 200 and payload == {"ui": {"theme": "dark"}}
    # merges at the top level and persists on the verb, exactly as the
    # project's own `ui` does — one grammar for both scopes
    assert client.post("/api/settings", {"ui": {"other": 1}})[1] == {
        "ui": {"theme": "dark", "other": 1}}
    assert client.post("/api/settings", {"ui": {"other": None}})[1] == {
        "ui": {"theme": "dark"}}

    # …and it is the *store* that holds it, not this session: opening a project
    # in a fresh session over the same state directory still answers dark
    _project(tmp_path / "settings.rex", pattern_file)
    other = GuiSession(state_dir=session.state_dir)
    other.project_open({"path": str(tmp_path / "settings.rex")})
    assert other.settings() == {"ui": {"theme": "dark"}}
    assert other.project_doc()["doc"]["ui"] == {}       # and the project has no say
    other.close()

    status, payload = client.post("/api/settings", {"theme": "dark"})
    assert status == 400 and payload["error"]["where"] == ["theme"]


def test_app_settings_survive_an_unreadable_store(app_settings):
    """A mangled or unwritable file is an empty setting, never a boot failure."""
    session, client = app_settings
    session.state_dir.mkdir(parents=True, exist_ok=True)
    (session.state_dir / "settings.json").write_text("{not json", encoding="utf-8")
    assert client.get("/api/settings") == (200, {"ui": {}})
    # a list where a dict belongs is the same answer, not a 500
    (session.state_dir / "settings.json").write_text('{"ui": []}', encoding="utf-8")
    assert client.get("/api/settings") == (200, {"ui": {}})
    assert client.post("/api/settings", {"ui": {"theme": "light"}})[1] == {
        "ui": {"theme": "light"}}


def test_project_verbs_refuse_before_a_project_is_open(blank):
    """``NO_PROJECT`` rather than a 500 or an empty table."""
    _, client = blank
    for method, path in (("GET", "/api/params"), ("GET", "/api/plan"),
                         ("GET", "/api/history"), ("GET", "/api/result"),
                         ("POST", "/api/run"), ("GET", "/api/project")):
        status, payload = client.request(method, path, {} if method == "POST" else None)
        assert status == 409, (path, status, payload)
        assert payload["error"]["code"] == "NO_PROJECT"


def test_host_header_is_checked(blank):
    """A page on another origin must not be able to drive this server."""
    _, client = blank
    status, payload = client.get("/api/version",
                                 headers={"Host": "rietx.example.com"})
    assert status == 403
    assert payload["error"]["code"] == "FORBIDDEN_HOST"
    # …and the rebinding case, where Host *is* loopback but the page is not
    status, payload = client.get("/api/version",
                                 headers={"Origin": "http://evil.example"})
    assert status == 403


def test_the_reserved_routes_all_came_live(blank):
    """WP-1027 filled in the last reserved family; the table is empty.

    The routes it owned now answer as live verbs — a blank session refuses
    with its own 409 (``NO_PROJECT``), never with ``NOT_IMPLEMENTED`` — and
    the mechanism stays for the next reserved surface.
    """
    assert RESERVED_ROUTES == {}
    _, client = blank
    for method, path in (("GET", "/api/peaks"), ("POST", "/api/index"),
                         ("GET", "/api/index/result"),
                         ("POST", "/api/index/adopt")):
        status, payload = client.request(method, path, body={})
        assert status == 409, (method, path, payload)
        assert payload["error"]["code"] == "NO_PROJECT", (method, path)


def test_no_route_is_declared_twice(blank):
    """A path may be live, reserved or an upload — never two of the three.

    Three tables now, because an upload's body is bytes rather than JSON
    (WP-1014); together they are still the complete wire surface, which is the
    property this asserts.
    """
    assert not set(ROUTES) & set(RESERVED_ROUTES)
    assert not set(UPLOAD_ROUTES) & set(ROUTES)
    assert not set(UPLOAD_ROUTES) & set(RESERVED_ROUTES)


def test_the_built_app_is_served_and_so_is_plotly(blank):
    """With the committed dist present (WP-1010), ``/`` is the real app."""
    _, client = blank
    status, payload = client.get("/")
    assert status == 200
    assert 'src="/assets/app.js"' in payload["raw"]
    assert client.get("/assets/app.js")[0] == 200
    assert client.get("/assets/app.css")[0] == 200
    status, payload = client.get("/plotly.js")
    assert status == 200 and len(payload["raw"]) > 1000
    assert client.get("/assets/nope.js")[0] == 404


def test_the_placeholder_explains_itself_when_the_dist_is_absent(blank, tmp_path,
                                                                monkeypatch):
    """A checkout without the built assets must still say what is going on."""
    from rietx.gui import server as server_module

    _, client = blank
    monkeypatch.setattr(server_module, "STATIC_DIR", tmp_path / "nothing-here")
    status, payload = client.get("/")
    assert status == 200 and "rietx gui" in payload["raw"]
    assert "WP-1010" in payload["raw"]


def test_asset_paths_cannot_escape_the_static_directory(blank):
    _, client = blank
    status, _ = client.get("/../../../../etc/passwd")
    assert status in (400, 404)


# ----------------------------------------------------------------------
# project lifecycle
# ----------------------------------------------------------------------
def test_new_open_and_recent_round_trip(blank, tmp_path, pattern_file):
    session, client = blank
    structure, ins = perturbed_models()
    root = tmp_path / "made_over_http.rex"
    status, payload = client.post("/api/project/new", {
        "path": str(root), "pattern": str(pattern_file),
        "structure": structure.model_dump(mode="json"),
        "instrument": ins.model_dump(mode="json"),
        "plan": "mccusker_default", "ui": {"disclosure": "simple"}})
    assert status == 200, payload
    assert payload["data"]["has_sigma"] is True      # the file's esds, not Poisson
    assert payload["doc"]["ui"] == {"disclosure": "simple"}
    assert payload["n_nodes"] == 1 and payload["head"] == "n0000"

    # a fresh session opens what the first one wrote, and remembers it
    other = GuiSession(state_dir=session.state_dir)
    assert other.project_open({"path": str(root)})["path"] == str(root)
    assert str(root) in [entry["path"] for entry in other.recent()]

    status, payload = client.post("/api/project/open", {"path": str(tmp_path)})
    assert status == 400 and payload["error"]["code"] == "PROJECT_ERROR"


def test_new_refuses_an_instrument_it_would_have_to_guess(blank, tmp_path,
                                                          pattern_file):
    """A default anode would put a wavelength nobody chose into every cell."""
    _, client = blank
    structure, _ = perturbed_models()
    status, payload = client.post("/api/project/new", {
        "path": str(tmp_path / "no_instrument.rex"),
        "pattern": str(pattern_file),
        "structure": structure.model_dump(mode="json")})
    assert status == 400
    assert payload["error"]["where"] == ["instrument"]


def test_open_surfaces_the_binding_message_it_refused_on(blank, tmp_path,
                                                          pattern_file):
    """Seven refusals, seven remedies — the GUI is where one gets read."""
    _, client = blank
    root = tmp_path / "edited.rex"
    _project(root, pattern_file)
    copied = root / pattern_file.name
    copied.write_text(copied.read_text(encoding="utf-8") + "90.0 1.0 1.0\n",
                      encoding="utf-8")
    status, payload = client.post("/api/project/open", {"path": str(root)})
    assert status == 400
    assert "has changed since the project was created" in payload["error"]["message"]
    assert "sha256" in payload["error"]["message"]


# ----------------------------------------------------------------------
# uploads and the import flow (WP-1014)
# ----------------------------------------------------------------------
DATA = Path(__file__).parent / "data"


@pytest.mark.parametrize("source, sent_as, reader, has_sigma", [
    # the .xye written by the module fixture — three columns, esd in the third
    (None, "synth.xye", "xy", True),
    # GSAS is recognised by its BANK record, so the suffix is free to lie: the
    # WP's own note is that ``.XRA`` has no parser and reads through this sniff
    (DATA / "11BM_NAC.fxye", "11BM_NAC.fxye", "gsas", True),
    (DATA / "11BM_NAC.fxye", "mystery.dat", "gsas", True),
    (DATA / "FAP.XRA", "FAP.XRA", "gsas", False),
    # pdCIF is the one format dispatched on its suffix, and the only one with
    # a reader *option*
    (DATA / "nist_srm660c_100a.cif", "nist.cif", "pdcif", True),
    # a vendor XML, claimed by its root element rather than its name; raw counts,
    # so no σ and the Poisson fallback is the correct answer
    (DATA / "panalytical_powder.xrdml", "renamed.txt", "xrdml", False),
    # the same format with a *derived* σ — one point behind a 188× attenuator,
    # whose σ genuinely could not come from the fallback
    (DATA / "panalytical_attenuator.xrdml", "panalytical_attenuator.xrdml",
     "xrdml", True),
    # two zip containers, told apart by their manifests rather than by the magic
    # bytes they share — and one of them uploaded under the other's extension
    (DATA / "rigaku_powder.rasx", "rigaku_powder.rasx", "rasx", False),
    (DATA / "bruker_absorber.brml", "mystery.rasx", "brml", True),
])
def test_an_upload_is_claimed_by_content_not_by_extension(
        blank, pattern_file, source, sent_as, reader, has_sigma):
    _, client = blank
    raw = (pattern_file if source is None else source).read_bytes()
    status, payload = client.upload("pattern", raw, filename=sent_as)
    assert status == 200, payload
    assert payload["format"]["name"] == reader
    assert payload["has_sigma"] is has_sigma
    assert payload["n_points"] > 100
    lo, hi = payload["two_theta_range"]
    assert lo < hi
    # the reader's own words travel, so a UI never restates the dispatch rule
    assert payload["format"]["sniff"]
    # …and a preview curve, so the file can be *looked at* before it is committed
    curve = payload["curve"]
    assert len(curve["two_theta"]) == len(curve["intensity"]) == curve["n_returned"]
    assert curve["n_returned"] <= payload["n_points"]
    assert payload["sha256"] == __import__("hashlib").sha256(raw).hexdigest()


@pytest.mark.parametrize("name,body,expect", [
    # a peak list is recognised in order to be declined (WP-1047)
    ("quartz.dif", b"Q\n D-SPACING INTENSITY H K L\n 4.2 16.0 1 0 0\n"
                   b" 3.3 100.0 1 0 1\n 2.4 9.0 1 1 0\n", "peak list"),
    # a binary file no longer reaches a decoder and dies as a codec error
    ("scan.png", b"\x89PNG\r\n\x1a\n" + bytes(range(256)) * 8,
     "not a powder pattern"),
    # a *Bruker* binary is now read (WP-1047 task 13), so a broken one is
    # refused by its own reader — a better message, and the case the matrix
    # used to stand in for with a fake RAW4 header
    ("d8.raw", b"RAW4.00\x00" + bytes(range(256)) * 8, "truncated"),
    # …and one this build knows the version of but does not read is named
    ("legacy.raw", b"RAW2" + bytes(4000), "RAW version 2"),
])
def test_a_file_this_build_cannot_honestly_read_is_refused_by_name(
        blank, name, body, expect):
    """The upload route is where a stranger's file arrives, so it is where
    "we know what this is and it is the wrong kind of file" has to be a
    sentence rather than a 500."""
    _, client = blank
    status, payload = client.upload("pattern", body, filename=name)
    assert status == 400, payload
    assert expect in payload["error"]["message"]
    assert name in payload["error"]["message"]


def test_a_staged_pdcif_is_re_read_for_another_block_without_re_uploading(blank):
    """``block`` is why the *reader call* is part of a data reference (WP-1005).

    The certification file carries a measured and a calculated block with
    identical tags; picking one is a decision the wizard makes after seeing the
    preview, and re-sending 300 kB to change a radio button would be absurd.
    """
    _, client = blank
    raw = (DATA / "nist_srm660c_100a.cif").read_bytes()
    status, first = client.upload("pattern", raw, filename="nist.cif")
    assert status == 200 and first["metadata"]["block"].endswith("_meas")
    status, second = client.upload("pattern", token=first["upload"], block="calc")
    assert status == 200, second
    assert second["upload"] == first["upload"]     # the same staged bytes
    assert second["metadata"]["block"].endswith("_calc")
    assert second["reader_options"] == {"block": "calc"}


def test_the_preview_carries_what_the_reader_repaired(blank):
    """The wizard is where a human should see a repair — before the file
    becomes a project and its point order becomes everything downstream."""
    _, client = blank
    raw = b"30 3\n20 2\n10 1\n"
    status, preview = client.upload("pattern", raw, filename="down.xy")
    assert status == 200, preview
    assert [d["code"] for d in preview["diagnostics"]] == ["PATTERN_SCAN_REVERSED"]
    assert preview["two_theta_range"] == [10.0, 30.0]


def test_the_aniso_checkbox_is_offered_only_when_the_cif_carries_a_loop(blank):
    """The opt-in mirrors an invariant, so the UI has to know if it is inert."""
    _, client = blank
    plain = client.upload("cif", (DATA / "cod_1000055.cif").read_bytes(),
                          filename="lab6.cif")[1]
    assert plain["aniso_available"] is False
    assert plain["aniso"] is False
    assert plain["phases"][0]["n_aniso"] == 0
    assert plain["phases"][0]["space_group"] == "P m -3 m"

    status, off = client.upload("cif", (DATA / "cod_1000236.cif").read_bytes(),
                                filename="cryolite.cif")
    assert status == 200, off
    # the file *has* a loop and the default read still ignores it — reading a
    # file must not silently change what a plan frees (CLAUDE.md)
    assert off["aniso_available"] is True
    assert off["phases"][0]["n_aniso"] == 0
    assert all(atom["aniso"] is None for atom in off["structure"]["phases"][0]["atoms"])

    on = client.upload("cif", token=off["upload"], aniso="1")[1]
    assert on["aniso"] is True and on["phases"][0]["n_aniso"] > 0
    assert on["upload"] == off["upload"]


def test_an_uploaded_pattern_and_cif_commit_into_a_project(blank, tmp_path):
    """The second phase: tokens become a project, and the bytes are the ones sent."""
    session, client = blank
    pattern = (DATA / "11BM_NAC.fxye").read_bytes()
    pat = client.upload("pattern", pattern, filename="nac.fxye")[1]
    cif = client.upload("cif", (DATA / "cod_1000055.cif").read_bytes(),
                        filename="lab6.cif")[1]

    root = tmp_path / "imported.rex"
    status, payload = client.post("/api/project/new", {
        "path": str(root),
        "pattern": {"upload": pat["upload"]},
        "structure": {"upload": cif["upload"]},
        # the wizard sends a decision, not a wavelength: the package supplies
        # the physics (WP-0507's scale lives in one place)
        "instrument": {"preset": "debye_scherrer", "wavelength": 0.413909}})
    assert status == 200, payload
    assert payload["data"]["reader"] == "gsas"
    assert payload["data"]["n_points"] == pat["n_points"]
    # copied byte-for-byte, which is what makes the reader's esd column the
    # contract rather than a re-serialisation (WP-1005)
    assert (root / "nac.fxye").read_bytes() == pattern
    assert session.project.refinement.instrument.source.lines[0].wavelength.value == 0.413909
    assert session.project.refinement.structure.phases[0].space_group == "P m -3 m"


def test_a_file_that_does_not_parse_leaves_nothing_behind(blank, tmp_path):
    """Two-phase means the failure is a message, not a directory to clean up."""
    _, client = blank
    status, payload = client.upload("cif", b"this is not a CIF\n",
                                    filename="notes.cif")
    assert status == 400, payload
    assert payload["error"]["code"] == "UPLOAD_INVALID"
    # the parser's own complaint, with its line and column…
    assert "expected block header" in payload["error"]["message"]
    # …and the staging path replaced by the name the client sent
    assert "notes.cif" in payload["error"]["message"]
    # the real prefix, imported rather than spelled: a copy of it here would go
    # quiet — not red — the day the prefix changes (WP-1062)
    assert f"/{UPLOAD_DIR_PREFIX}" not in payload["error"]["message"]

    status, payload = client.upload("pattern", b"\x00\x01\x02\x03", filename="x.xye")
    assert status == 400 and payload["error"]["code"] == "UPLOAD_INVALID"
    assert not list(tmp_path.iterdir())


def test_uploads_refuse_a_filename_that_is_a_path_and_a_body_that_is_a_claim(blank):
    _, client = blank
    raw = (DATA / "cod_1000055.cif").read_bytes()
    # a filename is data: reduced to its leaf rather than trusted
    payload = client.upload("cif", raw, filename="../../../etc/lab6.cif")[1]
    assert payload["filename"] == "lab6.cif"
    assert client.upload("cif", raw, filename="..")[0] == 400
    assert client.upload("cif", raw)[0] == 400            # no filename at all
    assert client.upload("cif", b"")[0] == 400            # no body and no token
    assert client.upload("nonsense", raw, filename="a.cif")[0] == 404

    # the cap is checked against the *declared* length, before a byte is read
    status, payload = client.upload("cif", raw, declared=99 * 1024 * 1024,
                                    filename="huge.cif")
    assert status == 413 and payload["error"]["code"] == "UPLOAD_TOO_LARGE"

    # a token is typed: a pattern's token is not a structure
    pat = client.upload("pattern", (DATA / "11BM_NAC.fxye").read_bytes(),
                        filename="nac.fxye")[1]
    status, payload = client.upload("cif", token=pat["upload"])
    assert status == 400 and "staged as a pattern" in payload["error"]["message"]
    assert client.upload("cif", token="deadbeef")[0] == 404


def test_an_instrument_profile_uploads_frozen_and_patches_in(blank, tmp_path,
                                                             pattern_file):
    """`load_instrument_profile`'s contract, unchanged by crossing the wire."""
    session, client = blank
    _open(session, tmp_path / "profile.rex", pattern_file)

    calibrated = session.project.refinement.instrument.model_copy(deep=True)
    calibrated.profile.u.value = 0.0123
    calibrated.profile.u.vary = True          # a calibration is data…
    path = tmp_path / "lab.instprm.json"
    rx.save_instrument_profile(calibrated, path)

    status, payload = client.upload("instrument", path.read_bytes(),
                                    filename="lab.instprm.json")
    assert status == 200, payload
    assert payload["instrument"]["profile"]["u"]["value"] == 0.0123
    assert payload["instrument"]["profile"]["u"]["vary"] is False   # …not a guess
    assert payload["frozen"] is True
    assert payload["summary"]["geometry"] == calibrated.geometry.kind

    status, patched = client.patch("/api/instrument",
                                   {"instrument": {"upload": payload["upload"]},
                                    "label": "lab profile"})
    assert status == 200, patched
    assert patched["instrument"]["profile"]["u"]["value"] == 0.0123
    assert session.project.history[patched["node_id"]].action.kind == "edit_model"

    assert client.upload("instrument", b'{"not": "a profile"}',
                         filename="x.json")[0] == 400


def test_an_instrument_preset_supplies_the_wavelengths_it_is_not_given(blank):
    from rietx.gui.imports import instrument_from_preset

    _, client = blank
    anodes = {a["name"] for a in client.get("/api/capabilities")[1]["anodes"]}
    assert "CuKa" in anodes and "MoKa" in anodes

    doublet = instrument_from_preset({"preset": "bragg_brentano",
                                      "radiation": "CuKa"})
    assert [line.wavelength.value for line in doublet.source.lines] == [1.5405929,
                                                                    1.5444274]
    assert doublet.geometry.kind == "bragg_brentano"

    with pytest.raises(ValueError, match="unknown radiation"):
        instrument_from_preset({"preset": "bragg_brentano", "radiation": "UnobtaniumKa"})
    with pytest.raises(ValueError, match="does not take"):
        instrument_from_preset({"preset": "debye_scherrer", "wavelength": 1.0,
                                "radiation": "CuKa"})
    with pytest.raises(ValueError, match="needs a wavelength"):
        instrument_from_preset({"preset": "debye_scherrer"})
    with pytest.raises(ValueError, match="unknown instrument preset"):
        instrument_from_preset({"preset": "neutron_tof"})


def test_every_instrument_preset_argument_is_the_constructors_own():
    """The registry a form is built from, pinned to the classmethod it calls.

    Same rule as every other registry here: an argument added to
    ``Instrument.bragg_brentano`` either reaches the import form or fails this,
    never sits silently unreachable.

    The same list is written out for the *frontend* to be held to, exactly as
    WP-1011's glob corpus is: the wizard renders one input per argument, and a
    field it offers that the constructor does not take is a control whose only
    outcome is a 400.  Committed, because vitest runs on machines that never
    installed this package.
    """
    import inspect

    from rietx.gui.imports import INSTRUMENT_PRESETS
    from rietx.schemas.instrument import Instrument

    for name, declared in INSTRUMENT_PRESETS.items():
        signature = inspect.signature(getattr(Instrument, name))
        expected = tuple(p for p in signature.parameters if p != "cls")
        assert set(declared) == set(expected), name

    fixture = Path(__file__).parent / "data" / "gui" / "instrument_presets.json"
    text = json.dumps({name: sorted(args)
                       for name, args in sorted(INSTRUMENT_PRESETS.items())},
                      indent=2) + "\n"
    if not fixture.is_file() or fixture.read_text(encoding="utf-8") != text:
        fixture.parent.mkdir(parents=True, exist_ok=True)
        fixture.write_text(text, encoding="utf-8")
        raise AssertionError(
            f"{fixture.relative_to(Path(__file__).parent.parent)} was stale and "
            "has been regenerated; re-run `npm --prefix gui test` and commit it")


def test_an_unknown_scattering_species_is_refused_where_it_is_typed(blank, tmp_path,
                                                                    pattern_file):
    """It would otherwise fail at stage compile, far from the field it was typed in."""
    session, client = blank
    _open(session, tmp_path / "species.rex", pattern_file)
    structure = client.get("/api/structure")[1]["structure"]
    structure["phases"][0]["atoms"][0]["species"] = "Xx"
    status, payload = client.patch("/api/structure", {"structure": structure})
    assert status == 400, payload
    assert payload["error"]["code"] == "UNKNOWN_SPECIES"
    assert payload["error"]["where"] == ["phases.0.atoms.0.species"]
    assert "Xx" in payload["error"]["message"]
    # an ion the table lacks is *not* refused: it falls back to the neutral atom
    structure["phases"][0]["atoms"][0]["species"] = "La7+"
    assert client.patch("/api/structure", {"structure": structure})[0] == 200


def test_structure_says_what_site_symmetry_allows_each_atom(blank, tmp_path,
                                                            pattern_file):
    """The arm an editor renders read-only from, derived where θ derives it."""
    session, client = blank
    _open(session, tmp_path / "sites.rex", pattern_file)
    status, payload = client.get("/api/structure")
    assert status == 200
    sites = {row["path"]: row for row in payload["sites"]}
    free = {row.path for row in session.project.parameters()}

    la = sites["phases.0.atoms.0"]          # La at 1a: m-3m, nothing to move
    assert la["dof_paths"] == [] and la["special"] is True
    assert la["site_symmetry_order"] == 48
    b = sites["phases.0.atoms.1"]           # B at 6f (x, ½, ½): one DOF, along x
    assert b["dof_paths"] == ["phases.0.atoms.1.dof.0"]
    assert b["dof_directions"] == [[1, 0, 0]]
    assert b["site_symmetry_order"] == 8
    # every path this arm names is a path the parameter table has
    for row in payload["sites"]:
        assert set(row["dof_paths"]) <= free
        assert set(row["adp_paths"]) <= free


def test_structure3d_serves_geometry_the_model_dump_cannot(blank, tmp_path,
                                                           pattern_file):
    """The route earns its place beside ``/api/structure`` (WP-1008's test).

    Everything in it is something a ``Structure`` dump does not say: the
    symmetry orbit, the bonds, and the cell frame.  The two knobs are drawing
    thresholds and ride on the query string, which is also what keeps them out
    of ``ProjectDoc`` — a probability level is not a fact about the sample.
    The geometry itself is ``tests/test_structure3d.py``'s ground.
    """
    session, client = blank
    _open(session, tmp_path / "viewer.rex", pattern_file)
    status, payload = client.get("/api/structure3d")
    assert status == 200, payload
    assert [s["path"] for s in payload["sites"]] == ["phases.0.atoms.0",
                                                     "phases.0.atoms.1"]
    assert len(payload["edges"]) == 12
    assert payload["probability"] == 0.5
    assert payload["bond_tolerance"] == pytest.approx(1.15)

    tuned = client.get("/api/structure3d?probability=0.9&bond_tolerance=1.05")[1]
    assert tuned["scale"] > payload["scale"]            # 2.5003 against 1.5382
    assert len(tuned["bonds"]) < len(payload["bonds"])

    assert client.get("/api/structure3d?phase=4")[0] == 404
    assert client.get("/api/structure3d?probability=2")[0] == 400

    # …and it follows the model rather than a cached read: an edit moves it
    before = payload["cell"][0]
    client.patch("/api/params", {"values": {"phases.0.cell.a": before + 0.1}})
    assert client.get("/api/structure3d")[1]["cell"][0] == pytest.approx(before + 0.1)


def test_the_aniso_toggle_seeds_and_unseeds_through_the_metric(blank, tmp_path,
                                                               pattern_file):
    """Both directions are physics, which is why the client does not compute them."""
    import math

    session, client = blank
    _open(session, tmp_path / "aniso.rex", pattern_file)
    before = client.get("/api/params")[1]["parameters"]
    assert not [r for r in before if r["path"].startswith("phases.0.atoms.0.adp")]

    status, payload = client.post("/api/structure/aniso",
                                  {"path": "phases.0.atoms.0", "on": True})
    assert status == 200, payload
    assert payload["changed"] is True
    atom = payload["structure"]["phases"][0]["atoms"][0]
    uiso = 0.5 / (8.0 * math.pi ** 2)                 # the seed Biso, as Uiso
    assert atom["aniso"]["u11"]["value"] == pytest.approx(uiso)
    assert atom["aniso"]["u12"]["value"] == pytest.approx(0.0)   # cubic: no shear
    site = next(s for s in payload["sites"] if s["path"] == "phases.0.atoms.0")
    assert site["adp_paths"] == ["phases.0.atoms.0.adp.0"]       # m-3m: one pattern

    # the table's shape moved with it: the DOF exists and biso is now locked
    rows = {r["path"]: r for r in client.get("/api/params")[1]["parameters"]}
    assert "phases.0.atoms.0.adp.0" in rows
    assert rows["phases.0.atoms.0.biso"]["locked"] is True
    assert session.project.history[payload["node_id"]].action.kind == "edit_model"

    # …and back, with biso restored from U_eq rather than from memory
    payload = client.post("/api/structure/aniso",
                          {"path": "phases.0.atoms.0", "on": False})[1]
    atom = payload["structure"]["phases"][0]["atoms"][0]
    assert atom["aniso"] is None
    assert atom["biso"]["value"] == pytest.approx(0.5)
    # a second toggle in the same direction is a no-op, not a node
    assert client.post("/api/structure/aniso",
                       {"path": "phases.0.atoms.0", "on": False})[1]["changed"] is False
    assert client.post("/api/structure/aniso", {"path": "phases.0"})[0] == 400
    assert client.post("/api/structure/aniso",
                       {"path": "phases.0.atoms.9"})[0] == 404


# ----------------------------------------------------------------------
# symmetry, surfaced and editable (WP-1035)
# ----------------------------------------------------------------------
def test_symmetry_rides_free_on_the_structure_route_and_names_its_effects(
        blank, tmp_path, pattern_file):
    """The free tier: one gemmi lookup per phase, and the causes it explains.

    The parameter table already says a row is tied or locked; ``held_because``
    says "structurally fixed by symmetry or by the model", which is a sentence
    with no subject.  What is asserted here is that every held row symmetry is
    responsible for now has one — and that the arm names the **setting**, not the
    crystal system, which is the distinction 79 of gemmi's 564 settings were
    served wrong on before WP-1036 while every degrees-of-freedom count was right.
    """
    session, client = blank
    _open(session, tmp_path / "sym.rex", pattern_file)
    payload = client.get("/api/structure")[1]
    facts = payload["symmetry"][0]
    assert facts["xhm"] == "P m -3 m" and facts["number"] == 221
    assert facts["crystal_system"] == "cubic" and facts["laue_class"] == "m-3m"
    assert facts["centring"] == "P" and facts["centrosymmetric"] is True
    assert facts["ties"] == {"b": "a", "c": "a"}
    assert facts["fixed_angles"] == {"alpha": 90.0, "beta": 90.0, "gamma": 90.0}

    causes = payload["causes"]
    rows = {r["path"]: r for r in client.get("/api/params")[1]["parameters"]}
    # every cell row the table holds has a named cause, and it names the symbol
    for path in ("phases.0.cell.b", "phases.0.cell.c", "phases.0.cell.alpha"):
        assert not rows[path]["vary"]
        assert "P m -3 m is cubic" in causes[path]
    assert "b follows a" in causes["phases.0.cell.b"]
    assert "β is fixed at 90°" in causes["phases.0.cell.beta"]
    assert "fully fixed special position" in causes["phases.0.atoms.0.x"]
    assert "dof.*" in causes["phases.0.atoms.1.x"]
    # …and it stays silent where symmetry is not the subject: the line-0 emission
    # weight and a mode-fixed row are held by something else entirely
    assert "instrument.source.lines.0.weight" not in causes
    # every cause names a path the table actually has
    assert set(causes) <= set(rows)

    # the same, over the branch with the most keys — an aniso site contributes a
    # sentence per U^ij component plus the biso the tensor displaces
    client.post("/api/structure/aniso", {"path": "phases.0.atoms.0", "on": True})
    payload = client.get("/api/structure")[1]
    rows = {r["path"] for r in client.get("/api/params")[1]["parameters"]}
    causes = payload["causes"]
    assert set(causes) <= rows
    assert "U12 to zero" in causes["phases.0.atoms.0.u12"]        # cubic: no shear
    assert "U11 follows phases.0.atoms.0.adp.*" in causes["phases.0.atoms.0.u11"]
    assert "anisotropic tensor" in causes["phases.0.atoms.0.biso"]


def test_the_wyckoff_letter_is_bought_on_a_route_that_was_opened_for_it(
        blank, tmp_path, pattern_file):
    """The measured half of WP-1035's split.

    ``site_constraints`` runs spglib per atom — 1.8-8.7 ms an atom on the machine
    this was written on — so it may not ride on ``/api/structure``, which
    refetches on every head move including one a ``set_vary`` made.  What the
    extra route buys is the *oriented* site-symmetry symbol, which is why the
    causes it serves are strictly better sentences than the free tier's.
    """
    session, client = blank
    _open(session, tmp_path / "wyckoff.rex", pattern_file)
    assert "letters" not in client.get("/api/structure")[1]     # not on that route

    status, payload = client.get("/api/structure/symmetry?phase=0")
    assert status == 200, payload
    letters = {row["path"]: row for row in payload["letters"]}
    assert letters["phases.0.atoms.0"]["wyckoff"] == "1a"       # La
    assert letters["phases.0.atoms.0"]["site_symmetry"] == "m-3m"
    assert letters["phases.0.atoms.1"]["wyckoff"] == "6f"       # B at (x, ½, ½)
    assert letters["phases.0.atoms.1"]["site_symmetry"] == "4m.m"
    assert payload["causes"]["phases.0.atoms.1.x"].startswith(
        "Wyckoff 6f, site symmetry 4m.m")
    assert client.get("/api/structure/symmetry?phase=7")[0] == 404


def test_a_symmetry_change_is_previewed_out_of_the_rules_that_would_refuse_it(
        blank, tmp_path, pattern_file):
    """The preview is a diff of two parameter tables, and duplicates no rule.

    Each assertion below is something the *candidate table* said, not something
    this module recomputed: which entries lose a tie, which DOFs appear, and —
    for a refusal — the package's own sentence with the nearest allowed tensor
    it had already computed.
    """
    session, client = blank
    _open(session, tmp_path / "preview.rex", pattern_file)

    # cubic → tetragonal: c stops following a, and nothing else moves
    status, out = client.post("/api/structure/symmetry/preview",
                              {"phase": 0, "space_group": "P 4/m m m"})
    assert status == 200, out
    assert out["blocked"] is False and out["changed"] is True
    assert out["to"]["crystal_system"] == "tetragonal"
    assert out["entries"]["untied"] == ["phases.0.cell.c"]
    assert out["entries"]["added"] == [] and out["entries"]["removed"] == []
    b = next(s for s in out["sites"] if s["atom"] == 1)
    assert (b["from"]["order"], b["to"]["order"]) == (8, 4)

    # cubic → triclinic: every coordinate becomes free, in DOFs that did not exist
    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P 1"})[1]
    assert out["entries"]["added"] == ["phases.0.atoms.0.dof.0",
                                       "phases.0.atoms.0.dof.1",
                                       "phases.0.atoms.0.dof.2",
                                       "phases.0.atoms.1.dof.1",
                                       "phases.0.atoms.1.dof.2"]
    assert "phases.0.cell.alpha" in out["entries"]["unlocked"]

    # a cell that cannot carry the symbol is refused in check_cell_angles' words
    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "R -3 c"})[1]
    assert out["blocked"] is True
    assert out["refusals"][0]["where"] == "phases.0.cell"
    assert "fixes gamma at 120.0°" in out["refusals"][0]["message"]
    # …and a refused change is given no *consequences*: the browser pass read
    # "the cell would hold 198 atoms" here, computed by applying R -3 c's
    # operators to a cell whose γ is 90° — a number about nothing
    assert [n["kind"] for n in out["notes"]
            if n["kind"] in ("multiplicity_change", "centring_change")] == []

    # an unresolvable symbol is a refusal addressed to the field it was typed in
    status, payload = client.post("/api/structure/symmetry/preview",
                                  {"phase": 0, "space_group": "not a group"})
    assert status == 400
    assert payload["error"]["where"] == ["space_group"]
    assert client.post("/api/structure/symmetry/preview",
                       {"phase": 9, "space_group": "P 1"})[0] == 404


def test_the_preview_reports_every_bad_atom_not_only_the_first(blank, tmp_path,
                                                               pattern_file):
    """A table stops at the first refusal; a user fixing four atoms one 500 at a
    time is not being told what is wrong.  The per-atom probe is a *real* table
    each time, which is why the message carries the nearest allowed tensor."""
    session, client = blank
    _open(session, tmp_path / "everybad.rex", pattern_file)
    for path in ("phases.0.atoms.0", "phases.0.atoms.1"):
        assert client.post("/api/structure/aniso", {"path": path, "on": True})[0] == 200
    structure = client.get("/api/structure")[1]["structure"]
    for atom in structure["phases"][0]["atoms"]:
        atom["aniso"]["u12"]["value"] = 0.004        # shear no cubic site allows
    assert client.patch("/api/structure", {"structure": structure})[0] == 400
    # …so put it there through the path that does not check, to set the scene
    session.project.refinement.structure.phases[0].atoms[0].aniso.u12.value = 0.004
    session.project.refinement.structure.phases[0].atoms[1].aniso.u12.value = 0.004

    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P m -3 m"})[1]
    assert [r["where"] for r in out["refusals"]] == ["phases.0.atoms.0",
                                                     "phases.0.atoms.1"]
    for refusal in out["refusals"]:
        assert "nearest allowed tensor" in refusal["message"]
        # the probe is numbered from zero; the path quoted is the caller's
        assert refusal["message"].startswith(refusal["where"] + ":")
    # the diff is empty rather than wrong when the candidate cannot build
    assert out["entries"]["added"] == []


def test_the_three_silent_failures_are_previewed_rather_than_discovered(
        blank, tmp_path, pattern_file):
    """None of these raises today, and the table diff cannot see any of them."""
    session, client = blank
    project = _open(session, tmp_path / "silent.rex", pattern_file)

    # (1) a setting change: same group, other axes, every coordinate reinterpreted
    project.refinement.structure.phases[0].space_group = "P 1 21/c 1"
    project.refinement.structure.phases[0].cell.b.value = 5.0
    project.refinement.structure.phases[0].cell.c.value = 6.0
    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P 1 1 21/b"})[1]
    note = next(n for n in out["notes"] if n["kind"] == "setting_change")
    assert "same space group (No. 14)" in note["message"]
    assert "unique axis b" in note["message"] and "unique axis c" in note["message"]

    # (3) …and the free set: a dof path that vanishes, and one that survives with
    #     a different direction behind it — the second warns nowhere at all today
    client.patch("/api/params", {"vary": {"phases.*.atoms.*.dof.*": True}})
    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P 1 2/m 1"})[1]
    kinds = {n["kind"]: n for n in out["notes"]}
    assert kinds["free_paths_dropped"]["where"] == ["phases.0.atoms.1.dof.2"]
    assert kinds["free_paths_renumbered"]["where"] == ["phases.0.atoms.1.dof.1"]
    assert "positional" in kinds["free_paths_renumbered"]["message"]


def test_a_supergroup_that_moves_no_parameter_still_says_the_cell_doubled(
        blank, tmp_path, pattern_file):
    """Found by driving the real page, and invisible to every diff that existed.

    Real NAC, ``I 21 3`` → ``I 41 3 2``: every stabiliser keeps its order, every
    site keeps its DOF count, the cell ties are the same and the centring is the
    same — so the entry diff is *empty* and the panel read "no parameter gains or
    loses a tie".  What actually happens is that every orbit doubles (12→24,
    8→16, 24→48), the cell holds twice as many atoms, and the phase scale means
    something else.  The multiplicity is the only thing that says so.
    """
    from rietx.crystallography.cif import structure_from_cif

    session, client = blank
    project = _open(session, tmp_path / "supergroup.rex", pattern_file)
    nac = structure_from_cif(str(Path(__file__).parent / "data" / "cod_1000236.cif"))
    project.refinement.structure = nac
    assert nac.phases[0].space_group == "I 21 3"

    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "I 41 3 2"})[1]
    assert out["blocked"] is False
    assert out["entries"] == {"added": [], "removed": [], "tied": [], "untied": [],
                              "locked": [], "unlocked": []}
    note = next(n for n in out["notes"] if n["kind"] == "multiplicity_change")
    assert "168 atoms instead of 84" in note["message"]    # 12+8+8+24+24+8, ×2
    sites = {s["label"]: s for s in out["sites"]}
    assert sites["Ca1"]["from"]["order"] == sites["Ca1"]["to"]["order"] == 2
    assert (sites["Ca1"]["from"]["multiplicity"],
            sites["Ca1"]["to"]["multiplicity"]) == (12, 24)
    assert (sites["F1"]["from"]["multiplicity"],
            sites["F1"]["to"]["multiplicity"]) == (24, 48)


def test_an_orbit_collision_blocks_only_when_the_occupancies_say_it_is_one(
        blank, tmp_path, pattern_file):
    """``select_orbit_ops`` dedups *within* one atom's orbit, so two
    asymmetric-unit atoms a higher symmetry maps together are counted twice — and
    nothing in the package checks it.  A *mixed* site is the same geometry and is
    not a bug, so the criterion is the shared occupancy rather than a guess."""
    from rietx.schemas.structure import Atom

    session, client = blank
    project = _open(session, tmp_path / "orbit.rex", pattern_file)
    phase = project.refinement.structure.phases[0]
    # distinct under P 4/m m m (z is the unique axis); one orbit under P m -3 m
    phase.space_group = "P 4/m m m"
    phase.atoms.append(Atom(label="X1", species="B", x={"value": 0.3},
                            y={"value": 0.0}, z={"value": 0.0}))
    phase.atoms.append(Atom(label="X2", species="B", x={"value": 0.0},
                            y={"value": 0.0}, z={"value": 0.3}))

    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P m -3 m"})[1]
    note = next(n for n in out["notes"] if n["kind"] == "orbit_collision")
    assert note["where"] == ["phases.0.atoms.2", "phases.0.atoms.3"]
    assert "occupancies sum to 2" in note["message"]
    assert out["blocked"] is True and not out["refusals"]

    head = client.get("/api/history")[1]["head"]
    status, payload = client.post("/api/structure/symmetry",
                                  {"phase": 0, "space_group": "P m -3 m"})
    assert status == 400
    assert payload["error"]["code"] == "SYMMETRY_REFUSED"
    assert client.get("/api/history")[1]["head"] == head

    # halve them and the same geometry is a legal mixed site: a note, not a gate
    for atom in phase.atoms[2:]:
        atom.occ.value = 0.5
    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P m -3 m"})[1]
    assert out["blocked"] is False
    assert [n["kind"] for n in out["notes"] if n["kind"].startswith("orbit")] \
        == ["orbit_collision_shared"]


def test_a_shared_site_is_judged_as_a_group_and_never_as_pairs(blank, tmp_path,
                                                               pattern_file):
    """Three atoms at occ 0.4 are 1.2 on one site; no *pair* of them exceeds 1.

    Coincidence is transitive — A with B and B with C means all three are one
    site — and the verdict is a sum over the site, so reading it pairwise is not
    a coarser answer but a wrong one.  It also decides the wording: "keep one
    atom of the 3" is advice a pairwise message cannot give.
    """
    from rietx.schemas.structure import Atom

    session, client = blank
    project = _open(session, tmp_path / "triple.rex", pattern_file)
    phase = project.refinement.structure.phases[0]
    phase.space_group = "P 4/m m m"
    # three points a 4-fold about z leaves distinct and P m -3 m's 3-folds merge
    for label, xyz in (("X1", (0.3, 0.0, 0.0)), ("X2", (0.0, 0.0, 0.3)),
                       ("X3", (0.0, 0.3, 0.0))):
        phase.atoms.append(Atom(label=label, species="B",
                                x={"value": xyz[0]}, y={"value": xyz[1]},
                                z={"value": xyz[2]}, occ={"value": 0.4}))

    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P m -3 m"})[1]
    note = next(n for n in out["notes"] if n["kind"] == "orbit_collision")
    assert note["where"] == ["phases.0.atoms.2", "phases.0.atoms.3",
                             "phases.0.atoms.4"]
    assert "X1, X2 and X3" in note["message"]
    assert "occupancies sum to 1.2" in note["message"]
    assert "one atom of the 3" in note["message"]
    assert out["blocked"] is True

    # …and the same three at 1/3 each are a legal three-way mixed site
    for atom in phase.atoms[2:]:
        atom.occ.value = 1.0 / 3.0
    out = client.post("/api/structure/symmetry/preview",
                      {"phase": 0, "space_group": "P m -3 m"})[1]
    assert out["blocked"] is False
    assert [n["kind"] for n in out["notes"] if n["kind"].startswith("orbit")] \
        == ["orbit_collision_shared"]


def test_an_incompatible_model_is_refused_before_any_history_node_is_written(
        blank, tmp_path, pattern_file):
    """The regression this WP exists for, and it was never about the space group.

    Measured before the fix: ``PATCH /api/structure`` with an aniso tensor no
    longer allowed **succeeded**, recorded an ``edit_model`` node, and then
    surfaced as a 500 ``INTERNAL_ERROR`` on the panel's next ``GET /api/params``
    — because a ``ValueError`` out of ``ParameterTable`` is not a ``GuiError``.
    The head then stood at a state whose table cannot build and a history
    checkout was the only way out.  The gate is in ``_edit``, so it covers every
    whole-model verb, and it is on the *candidate*, so an edit that repairs a
    broken head still passes.
    """
    session, client = blank
    project = _open(session, tmp_path / "gate.rex", pattern_file)
    client.post("/api/structure/aniso", {"path": "phases.0.atoms.0", "on": True})
    head = client.get("/api/history")[1]["head"]

    structure = client.get("/api/structure")[1]["structure"]
    structure["phases"][0]["atoms"][0]["aniso"]["u12"]["value"] = 0.004
    status, payload = client.patch("/api/structure", {"structure": structure})
    assert status == 400, payload
    assert payload["error"]["code"] == "MODEL_REFUSED"
    assert payload["error"]["where"] == ["phases.0.atoms.0"]
    assert "nearest allowed tensor" in payload["error"]["message"]

    assert client.get("/api/history")[1]["head"] == head      # nothing committed
    assert client.get("/api/params")[0] == 200                # and still readable

    # the escape hatch has to keep working: put the model into the state the old
    # bug left behind, and the verb that repairs it must not be gated by it
    project.refinement.structure.phases[0].atoms[0].aniso.u12.value = 0.004
    assert client.get("/api/params")[0] == 500                # the 500 of record
    assert client.post("/api/structure/symmetry/preview",
                       {"phase": 0, "space_group": "P 1"})[0] == 200
    status, payload = client.post("/api/structure/symmetry",
                                  {"phase": 0, "space_group": "P 1"})
    assert status == 200, payload
    assert payload["node_id"] is not None
    assert client.get("/api/params")[0] == 200


def test_the_symmetry_verb_commits_one_node_and_says_what_it_did(blank, tmp_path,
                                                                 pattern_file):
    """One ``edit_model`` node, through the same path every model edit takes."""
    session, client = blank
    _open(session, tmp_path / "apply.rex", pattern_file)
    before = client.get("/api/params")[1]["parameters"]
    assert {r["path"] for r in before if r["path"] == "phases.0.cell.c"}

    status, payload = client.post("/api/structure/symmetry",
                                  {"phase": 0, "space_group": "P 4/m m m"})
    assert status == 200, payload
    assert payload["changed"] is True
    assert session.project.history[payload["node_id"]].action.kind == "edit_model"
    assert payload["structure"]["phases"][0]["space_group"] == "P 4/m m m"
    assert payload["symmetry"][0]["crystal_system"] == "tetragonal"
    # the tie really went: c is now its own row, and the causes say so for b only
    rows = {r["path"]: r for r in client.get("/api/params")[1]["parameters"]}
    assert rows["phases.0.cell.c"]["tie"] is None
    causes = client.get("/api/structure")[1]["causes"]
    assert "phases.0.cell.c" not in causes and "phases.0.cell.b" in causes

    # the same symbol again is a no-op rather than a second node
    payload = client.post("/api/structure/symmetry",
                          {"phase": 0, "space_group": "P 4/m m m"})[1]
    assert payload["changed"] is False and payload["node_id"] is None


def test_settings_persist_without_anyone_pressing_save(blank, tmp_path,
                                                       pattern_file):
    """The close dialog has nothing to confirm, so a settings verb must save."""
    session, client = blank
    root = tmp_path / "settings.rex"
    _open(session, root, pattern_file)

    status, payload = client.post("/api/project", {
        "mode": "lebail", "two_theta_limits": [5.0, 20.0],
        "excluded_regions": [[8.0, 8.5]], "ui": {"panel": "params"}})
    assert status == 200, payload
    assert payload["doc"]["mode"] == "lebail"
    assert payload["doc"]["excluded_regions"] == [[8.0, 8.5]]

    on_disk = json.loads((root / "project.json").read_text(encoding="utf-8"))
    assert on_disk["mode"] == "lebail"
    assert on_disk["two_theta_limits"] == [5.0, 20.0]
    assert on_disk["ui"] == {"panel": "params"}
    # the mask reached the pattern too, not just the document
    assert session.project.data.excluded_regions == [(8.0, 8.5)]

    # a ui key set to null is dropped rather than stored as null
    assert client.post("/api/project", {"ui": {"panel": None}})[1]["doc"]["ui"] == {}
    assert client.post("/api/project", {"nonsense": 1})[0] == 400


def test_the_masked_channels_have_one_authority_and_three_readers(blank, tmp_path,
                                                                  pattern_file):
    """WP-1033: what is drawn, what is documented and what is fitted agree.

    The three readers are the project document's ``n_fitted``, the ``.rxt``
    document's ``limits``/``excluded`` lines, and the plot's payloads — and the
    thing they must agree about is a *set of channels*, which is why the
    assertion is a count against ``Project.fitted_mask`` rather than a
    re-derivation of the intersection here.
    """
    session, client = blank
    root = tmp_path / "masked.rex"
    project = _open(session, root, pattern_file)
    n_points = project.data_ref.n_points
    assert client.get("/api/project")[1]["data"]["n_fitted"] == n_points

    status, payload = client.post("/api/project", {
        "two_theta_limits": [8.0, 19.0], "excluded_regions": [[13.0, 16.0]]})
    assert status == 200, payload
    n_fitted = payload["data"]["n_fitted"]
    assert n_fitted == int(session.project.fitted_mask().sum()) < n_points

    # the text document renders the same two facts, in its own grammar
    text = client.get("/api/textdoc")[1]["text"]
    assert "limits 8 19" in text
    assert "excluded 13 16" in text

    # and one typed *into* the document comes back out of the settings route
    # inside the limits, or it would remove nothing that was there
    edited = text.replace("excluded 13 16", "excluded 13 16  17 18")
    status, payload = client.put("/api/textdoc", {"text": edited,
                                                  "base_revision": None})
    assert status == 200, payload
    doc = client.get("/api/project")[1]
    assert doc["doc"]["excluded_regions"] == [[13.0, 16.0], [17.0, 18.0]]
    assert doc["data"]["n_fitted"] < n_fitted


def test_an_inverted_range_is_refused_in_one_sentence_by_every_surface(
        blank, tmp_path, pattern_file):
    """One authority for the words, three surfaces quoting them (WP-1033)."""
    from pydantic import ValidationError

    session, client = blank
    root = tmp_path / "inverted.rex"
    project = _open(session, root, pattern_file)

    status, payload = client.post("/api/project", {"two_theta_limits": [60.0, 20.0]})
    assert status == 400
    assert payload["error"]["message"] == (
        "two_theta_limits must run low to high: (60.0, 20.0) is inverted")
    assert payload["error"]["where"] == ["two_theta_limits"]
    assert client.post("/api/project", {"excluded_regions": [[5.0, 5.0]]})[1][
        "error"]["message"].endswith("(5.0, 5.0) is empty")
    # refused, so nothing moved — neither the document nor the pattern
    assert project.doc.two_theta_limits is None
    assert project.data.excluded_regions == []

    # the document itself refuses a bare assignment, which is what makes a
    # hand-edited project.json refuse to load too
    with pytest.raises(ValidationError):
        project.doc.two_theta_limits = (60.0, 20.0)

    # and the text document says the same thing with a line number attached
    text = client.get("/api/textdoc")[1]["text"].replace("limits none",
                                                         "limits 60 20")
    status, payload = client.put("/api/textdoc", {"text": text,
                                                  "base_revision": None})
    assert status == 400
    detail = payload["error"]["details"][0]
    assert detail["message"] == (
        "limits must run low to high: (60.0, 20.0) is inverted")
    assert detail["line"] > 0


def test_the_window_carries_the_channels_the_result_dropped(fitted):
    """WP-1033: a band needs something to shade, and a range needs an outside.

    Measured before it was designed: ``compile_model`` masks first, so a result
    carries only the surviving channels and the plot's axis autoranges *inside*
    the fit range — on this fixture a 3–24° pattern came back as 8.005–18.990°,
    with zero points inside a 3° exclusion.  Shading alone would have drawn a
    band over a hole.
    """
    session, client, project = fitted
    try:
        status, before = client.get("/api/result/window")
        assert status == 200
        assert before["n_excluded"] == 0 and before["stale"] is False

        assert client.post("/api/project",
                           {"excluded_regions": [[13.0, 16.0]]})[0] == 200
        window = client.get("/api/result/window")[1]
        # the masked points are here, and in no residual
        assert window["n_excluded"] == int((~project.fitted_mask()).sum()) > 0
        assert window["excluded"]["two_theta"]
        assert min(window["excluded"]["two_theta"]) >= 13.0
        # …and the curves on screen predate the change, which the route says
        # rather than leaving the client to compare counts
        assert window["stale"] is True
        assert any(13.0 <= tt <= 16.0 for tt in window["two_theta"])

        # the raw peak view is masked by the same document and carries the
        # same arm — it is the only view a project has before its first fit
        session.peaks_pick({})
        pattern = client.get("/api/peaks")[1]["pattern"]
        assert pattern["n_excluded"] == window["n_excluded"]
        assert not any(13.0 <= tt <= 16.0 for tt in pattern["two_theta"])
    finally:
        # a module fixture: give the next reader the pattern it expects
        client.post("/api/project", {"excluded_regions": []})


def test_a_refit_makes_the_channel_count_the_fit_agree_with_the_document(
        blank, tmp_path, pattern_file):
    """The pin behind the whole feature: ``fitted_mask`` and ``compile_model``.

    ``Project.fitted_mask`` is the GUI's authority for which channels are in
    the residual and ``compile_model``'s first act is the fit's — two lines,
    one fact, and nothing but this test stops them drifting.  The count is also
    the acceptance check: a band drawn over points still in the residual is
    worse than no band at all.
    """
    session, client = blank
    project = _open(session, tmp_path / "channels.rex", pattern_file)
    assert client.post("/api/project", {"two_theta_limits": [8.0, 19.0],
                                        "excluded_regions": [[13.0, 16.0]]})[0] == 200
    status, run = client.post("/api/run", {"kind": "stage", "stage": {
        "name": "scale", "turn_on": ["phases.*.scale"], "max_iter": 5}})
    assert status == 200, run
    _wait_idle(client)

    result = project.refinement.result_
    assert len(result.two_theta) == int(project.fitted_mask().sum())
    assert client.get("/api/result/window")[1]["stale"] is False


def test_plan_selection_and_the_preset_it_matches(blank, tmp_path, pattern_file):
    session, client = blank
    _open(session, tmp_path / "plan.rex", pattern_file)
    status, payload = client.get("/api/plan")
    assert status == 200
    assert payload["preset"] == "mccusker_default"   # derived, not stored
    assert payload["selected"] is True
    n_stages = len(payload["plan"]["stages"])

    status, payload = client.put("/api/plan", {"preset": "profile_only"})
    assert status == 200 and payload["preset"] == "profile_only"

    edited = payload["plan"]
    edited["stages"] = edited["stages"][:1]
    status, payload = client.put("/api/plan", {"plan": edited})
    assert status == 200
    assert payload["preset"] is None and len(payload["plan"]["stages"]) == 1
    assert n_stages > 1

    assert client.put("/api/plan", {"preset": "no_such_plan"})[0] == 400
    assert client.put("/api/plan", {"plan": {"stages": []}})[0] == 400
    assert client.get("/api/plans")[1]["plans"][0]["when_to_use"]


# ----------------------------------------------------------------------
# parameters
# ----------------------------------------------------------------------
def test_params_exposes_why_each_held_row_is_held(fitted):
    _, client, project = fitted
    status, payload = client.get("/api/params")
    assert status == 200
    rows = {r["path"]: r for r in payload["parameters"]}
    assert len(rows) == len(project.refinement.parameters())
    assert payload["live"] is False and payload["n_free"] > 0

    # the three reasons a row can be held, each spelled out in the payload
    tied = [r for r in rows.values() if r["tie"] is not None]
    locked = [r for r in rows.values() if r["locked"]]
    assert tied and locked
    for row in (*tied, *locked):
        assert row["refinable"] is False and row["held_because"]
    # …and esds from the fit are merged into the same listing
    assert any(r["esd"] for r in rows.values())


def test_every_response_is_json_a_browser_can_parse(fitted):
    """WP-1011: ``JSON.parse`` rejects Python's bare ``Infinity``/``NaN``.

    ``json.dumps`` emits them by default, and a parameter row carries an infinite
    bound almost always — so the whole of ``/api/params`` was unparseable in a
    browser while every Python test read it back happily, because ``json.loads``
    accepts the extension its own dumper writes.  The bytes are therefore checked
    with ``parse_constant`` wired to raise, which is what "strict JSON" means, and
    the round trip is checked too: the spelling has to be the schemas'
    (``ser_json_inf_nan="strings"``), not ``null``, or ±inf stop being
    distinguishable.
    """
    _, client, _ = fitted

    def strict(raw: bytes) -> object:
        def reject(token):
            raise AssertionError(f"bare {token!r} is not JSON; JSON.parse would refuse it")

        return json.loads(raw.decode("utf-8"), parse_constant=reject)

    for path in ("/api/params", "/api/result", "/api/result/window?max_points=200",
                 "/api/plan", "/api/report", "/api/history", "/api/capabilities"):
        conn = HTTPConnection("127.0.0.1", client.port, timeout=60)
        try:
            conn.request("GET", path, headers={"Host": f"127.0.0.1:{client.port}"})
            payload = strict(conn.getresponse().read())
        finally:
            conn.close()
        assert payload, path

    rows = client.get("/api/params")[1]["parameters"]
    unbounded = [r for r in rows if r["hi"] == "Infinity"]
    assert unbounded, "no row had an infinite bound; this test would prove nothing"
    assert float(unbounded[0]["hi"]) == float("inf")
    assert any(r["lo"] == "-Infinity" for r in rows)   # the sign survives


def test_editing_a_tied_path_is_refused_by_naming_its_sources(fitted):
    """WP-1004's rule, now over HTTP: ``b`` follows ``a`` on a cubic cell."""
    _, client, _ = fitted
    status, payload = client.patch("/api/params",
                                   {"values": {"phases.0.cell.b": 4.2}})
    assert status == 400
    assert "phases.0.cell.a" in payload["error"]["message"]
    assert payload["error"]["where"] == ["phases.0.cell.b"]


def test_values_and_vary_commit_their_own_history_nodes(blank, tmp_path,
                                                        pattern_file):
    session, client = blank
    project = _open(session, tmp_path / "edits.rex", pattern_file)
    before = len(project.history)

    status, payload = client.patch("/api/params", {
        "values": {"phases.0.cell.a": 4.163},
        "vary": {"phases.*.cell.*": True, "phases.0.cell.a": False}})
    assert status == 200, payload
    assert payload["changed"]["values"] == ["phases.0.cell.a"]
    assert payload["changed"]["vary"]["phases.0.cell.a"] == ["phases.0.cell.a"]

    rows = {r["path"]: r for r in payload["parameters"]}
    assert rows["phases.0.cell.a"]["value"] == pytest.approx(4.163)
    # a cubic tie followed the edit (WP-1004's refresh_ties)
    assert rows["phases.0.cell.c"]["value"] == pytest.approx(4.163)
    assert rows["phases.0.cell.a"]["vary"] is False

    kinds = [n.action.kind for n in project.history.nodes.values()]
    assert kinds[before:] == ["set_value", "set_vary", "set_vary"]
    # every one of them is on disk already — saving is about settings
    reopened = rx.Project.open(project.path)
    assert len(reopened.history) == len(project.history)
    assert reopened.refinement.structure.phases[0].cell.a.value == pytest.approx(4.163)


def test_a_bulk_glob_is_one_round_trip_and_one_history_node(blank, tmp_path,
                                                            pattern_file):
    """WP-1011: the table sends the *glob*, not the paths it previewed.

    That is what keeps a "free every cell parameter" click to one node instead of
    one per parameter — and it is why the client-side matcher can only ever be a
    preview: this call is where the matching that counts happens.
    """
    session, client = blank
    project = _open(session, tmp_path / "bulk.rex", pattern_file)
    before = len(project.history)

    status, payload = client.patch("/api/params", {"vary": {"instrument.profile.*": True}})
    assert status == 200, payload
    freed = payload["changed"]["vary"]["instrument.profile.*"]
    assert len(freed) > 1 and all(p.startswith("instrument.profile.") for p in freed)
    assert len(project.history) == before + 1          # one glob, one node

    # a locked or tied entry never matches, however broad the glob — which is
    # exactly what the table's `freeable` count promises the user.  On this cubic
    # cell that leaves `a` alone out of six paths
    status, payload = client.patch("/api/params", {"vary": {"phases.*.cell.*": True}})
    assert status == 200
    assert payload["changed"]["vary"]["phases.*.cell.*"] == ["phases.0.cell.a"]
    rows = {r["path"]: r for r in payload["parameters"]}
    assert rows["phases.0.cell.b"]["vary"] is False      # tied to a
    assert rows["phases.0.cell.alpha"]["vary"] is False  # locked by symmetry
    assert len(project.history) == before + 2

    # …and the same glob back off is another single node
    status, payload = client.patch("/api/params", {"vary": {"instrument.profile.*": False}})
    assert status == 200 and payload["changed"]["vary"]["instrument.profile.*"] == freed
    assert len(project.history) == before + 3

    # a glob nobody matches is not an error: it changed nothing, and says so
    status, payload = client.patch("/api/params", {"vary": {"nothing.at.all": True}})
    assert status == 200 and payload["changed"]["vary"]["nothing.at.all"] == []
    assert len(project.history) == before + 4   # …but it is still a recorded move


def test_a_whole_model_patch_records_an_edit_node(blank, tmp_path, pattern_file):
    session, client = blank
    project = _open(session, tmp_path / "edit_model.rex", pattern_file)
    instrument = client.get("/api/instrument")[1]["instrument"]
    instrument["zero_shift"]["value"] = 0.02
    status, payload = client.patch("/api/instrument", {"instrument": instrument,
                                                       "label": "zero guess"})
    assert status == 200, payload
    assert payload["instrument"]["zero_shift"]["value"] == 0.02
    node = project.history[payload["node_id"]]
    assert node.action.kind == "edit_model" and node.label == "zero guess"

    status, payload = client.patch("/api/structure", {"structure": {"phases": []}})
    assert status == 400 and payload["error"]["where"]


# ----------------------------------------------------------------------
# running
# ----------------------------------------------------------------------
def test_a_real_run_streams_its_events_to_disk_and_to_followers(fitted):
    """The GUI and ``rietx watch`` are two views of one stream."""
    session, client, project = fitted
    log = project.live_dir / "events.jsonl"
    assert log.is_file()
    kinds = [record.kind for record in read_events(log)]
    assert kinds[0] == "fit_start" and kinds[-1] == "fit_end"
    assert "stage_start" in kinds and "eval" in kinds

    # the ring buffer replayed the same run, seq-numbered and monotone
    status, payload = client.get("/api/events?poll=1&since=0")
    assert status == 200
    seqs = [e["seq"] for e in payload["events"]]
    assert seqs == sorted(seqs) and payload["next"] == seqs[-1]
    assert payload["oldest"] == seqs[0]
    assert [e["kind"] for e in payload["events"]][-1] == "fit_end"

    # …and ?since= is a real replay cursor, not a hint
    half = seqs[len(seqs) // 2]
    later = client.get(f"/api/events?poll=1&since={half}")[1]["events"]
    assert [e["seq"] for e in later] == [s for s in seqs if s > half]


def test_result_carries_no_curves_and_the_window_serves_them(fitted):
    _, client, project = fitted
    status, payload = client.get("/api/result")
    assert status == 200
    result = payload["result"]
    assert "two_theta" not in result and "y_obs" not in result
    assert result["statistics"]["rwp"] < 0.2
    n_points = result["curves"]["n_points"]
    assert n_points == len(project.data.two_theta)

    status, window = client.get("/api/result/window")
    assert status == 200
    assert window["n_total"] == n_points
    # max_points is a budget, not a ceiling: three curves' per-bucket extrema
    # over max_points//2 buckets can exceed it, and n_returned is the truth
    assert 0 < window["n_returned"] <= 3 * (window["max_points"] // 2) + 2
    assert len(window["two_theta"]) == window["n_returned"]
    assert len(window["delta"]) == window["n_returned"]

    lo, hi = 8.0, 12.0
    zoom = client.get(f"/api/result/window?lo={lo}&hi={hi}&max_points=200")[1]
    assert zoom["n_total"] < n_points
    assert lo <= zoom["two_theta"][0] and zoom["two_theta"][-1] <= hi
    # ticks are clipped to the window, and every emission line is in them
    assert all(lo <= t <= hi for ticks in zoom["ticks"].values() for t in ticks)
    assert zoom["ticks"]

    empty = client.get("/api/result/window?lo=200&hi=210")[1]
    assert empty["n_returned"] == 0 and empty["two_theta"] == []


def test_the_result_says_when_a_fit_is_past_the_point_of_being_a_fit(fitted):
    """WP-1029 item (c): one honest signal, in the report's own vocabulary."""
    from rietx.report.schemas import MATURITY_MAX_RWP

    session, client, project = fitted
    maturity = client.get("/api/result")[1]["result"]["maturity"]
    # the threshold is *quoted*, not copied: a client comparing against its own
    # 0.35 would be a second authority on a number the report owns
    assert maturity["max_rwp"] == MATURITY_MAX_RWP
    # this fixture converges, so it is not immature and says nothing
    assert maturity["immature"] is False
    assert maturity["message"] == ""

    # …and a hopeless one says so, without touching `status`, which still reads
    # `converged` — that vocabulary is WP-1028's, and two owners would disagree
    result = project.refinement.result_
    result.statistics.rwp = 0.963
    hopeless = client.get("/api/result")[1]["result"]
    assert hopeless["maturity"]["immature"] is True
    assert "96.3%" in hopeless["maturity"]["message"]
    assert "same specimen" in hopeless["maturity"]["message"]
    assert hopeless["status"] == "converged"


def test_the_window_carries_three_residuals_and_one_is_not_derivable(fitted):
    """WP-1029: Δ, Δ/σ and cumulative χ² — the third accumulated before decimation."""
    _, client, project = fitted
    result = project.refinement.result_

    window = client.get("/api/result/window")[1]
    n = window["n_returned"]
    assert len(window["delta"]) == len(window["delta_raw"]) == n
    assert len(window["cumulative_chi2"]) == n
    # this project's pattern brings σ, so Δ/σ is a different curve from Δ, and
    # the flag is what lets a client label its axis without guessing
    assert window["weighted"] is True
    assert window["delta"] != window["delta_raw"]

    # the whole point of accumulating server-side: the last value is the
    # window's *true* χ², over every point, not over the decimated subset
    delta = (np.asarray(result.y_obs) - np.asarray(result.y_calc)) / result.sig()
    assert window["cumulative_chi2"][-1] == pytest.approx(float((delta**2).sum()))
    # …and summing what came back would understate it, which is the mistake
    # this field exists to prevent
    assert sum(d**2 for d in window["delta"]) < window["cumulative_chi2"][-1]
    # monotone, so no bucket can miss a peak of it
    assert all(b >= a for a, b in zip(window["cumulative_chi2"],
                                      window["cumulative_chi2"][1:]))

    # a zoom's cumulative starts from that window rather than from the pattern
    zoom = client.get("/api/result/window?lo=8&hi=12&max_points=200")[1]
    assert zoom["cumulative_chi2"][-1] < window["cumulative_chi2"][-1]


def test_the_weighted_residual_has_exactly_one_authority(fitted):
    """WP-1029 (s): the PNG and the GUI cannot draw different Δ/σ.

    ``viz/plots.py`` and ``gui/session.py`` each open-coded σ and landed on main
    hours apart.  They agreed only by luck — the divergence (a Poisson fallback
    against a raw Δ) sat in a branch that fires solely on a pre-v0.2 result — and
    nothing held them together, which is the second-authority-on-one-picture the
    conventions forbid.  Both now divide by :meth:`RefinementResult.sig`.

    This compares what matplotlib actually **drew** against what the route
    actually **sent**, rather than two re-derivations of one formula: a test that
    recomputes the residual itself would pass while both drawers were wrong.
    """
    import matplotlib.pyplot as plt

    _, client, project = fitted
    result = project.refinement.result_

    fig = result.plot(weighted=True)
    try:
        # weighted mode puts Δ/σ alone on the lower axes; the ±3σ band is a patch
        drawn = np.asarray(fig.axes[1].lines[0].get_ydata())
    finally:
        plt.close(fig)

    window = client.get("/api/result/window")[1]
    # the window is decimated and the PNG is not, so match on 2θ, not position
    idx = np.searchsorted(np.asarray(result.two_theta),
                          np.asarray(window["two_theta"]))
    # elementwise ops on the same arrays: equal to the bit, not to a tolerance
    np.testing.assert_array_equal(np.asarray(window["delta"]), drawn[idx])

    # and the third drawer, the plotly export, divides by the same σ
    from rietx.viz.html import figure_from_arrays
    figure = figure_from_arrays(
        np.asarray(result.two_theta), np.asarray(result.y_obs),
        np.asarray(result.y_calc), None, result.ticks, sigma=result.sig(),
        max_points=10 * len(result.two_theta))
    trace = next(t for t in figure.data if t.name == "Δ/σ")
    np.testing.assert_array_equal(np.asarray(trace.y), drawn)


def test_a_poisson_project_still_gets_a_weighted_residual(
        blank, tmp_path, poisson_pattern_file):
    """WP-1029 (s): no esd column means an **assumed** σ, not no σ.

    This is the branch the fix changed.  ``weighted`` used to be
    ``bool(result.sigma)``, which is True for every result this GUI can make, so
    the flag was a constant and the client's own no-esd path was unreachable —
    a Poisson fit got the axis of a measured one.
    """
    session, client = blank
    project = _open(session, tmp_path / "poisson.rex", poisson_pattern_file)
    assert project.data_ref.has_sigma is False
    client.post("/api/run", {"kind": "stage",
                             "stage": {"name": "s", "turn_on": ["phases.*.scale"]}})
    _wait_idle(client)

    window = client.get("/api/result/window")[1]
    assert window["weighted"] is False       # the σ was assumed, and says so
    # …and is still divided through, because Δ/σ is what the fit minimised —
    # the flag changes the axis title, never which curve is drawn
    assert window["delta"] != window["delta_raw"]

    # the assumption is Poisson exactly, not the file's absent 1.3× esds
    result = project.refinement.result_
    np.testing.assert_array_equal(
        result.sig(), np.sqrt(np.maximum(np.asarray(result.y_obs), 1.0)))


def test_report_and_history_read_the_fitted_session(fitted):
    session, client, project = fitted
    status, payload = client.get("/api/report")
    assert status == 200
    report = payload["report"]
    assert report["summary"] and report["thresholds_version"]
    assert report["rwp"] == pytest.approx(
        project.refinement.result_.statistics.rwp)
    # WP-1012: what applies travels beside what is suggested, one arm per action
    assert len(payload["apply"]) == len(report["suggested_actions"])

    status, payload = client.get("/api/history")
    assert status == 200
    assert payload["head"] == project.refinement._head_id
    assert payload["n_nodes"] == len(project.history)
    stage_nodes = [n for n in payload["nodes"] if n["kind"] == "stage"]
    assert stage_nodes and all(n["rwp"] is not None for n in stage_nodes)
    # a node's equivalent API call travels with it, so the log doubles as a script
    assert stage_nodes[0]["api_call"].startswith("ref.run_stage(")
    # …and no node ships its ~10 kB of structure/instrument state
    assert "state" not in payload["nodes"][0]

    ids = [n["id"] for n in payload["nodes"]][:2]
    rows = client.get(f"/api/history/compare?ids={','.join(ids)}")[1]["rows"]
    assert [r["id"] for r in rows] == ids
    diff = client.get(f"/api/history/diff?a={ids[0]}&b={ids[1]}")[1]["diff"]
    assert diff and all(len(pair) == 2 for pair in diff.values())
    assert client.get("/api/history/diff?a=n0000")[0] == 400
    assert client.get("/api/history/diff?a=n0000&b=nope")[0] == 404


def test_two_text_writers_race_and_the_second_is_refused_whole(
        blank, tmp_path, pattern_file):
    """The text pane's conflict story, over the wire and with two *writers*.

    WP-1013's sync engine treats a 409 ``STALE_REVISION`` and a re-render arriving
    mid-edit as the same event, because they are: the buffer descends from a
    rendering the project has moved past. What the session tests could not show is
    the case that actually produces it — two clients holding the same revision,
    which is one browser tab and one `rietx` REPL, or two tabs. The second writer
    must be refused **whole**: not a merge, not a partial apply, and not a refusal
    that leaves half the delta in.

    The 409 is also the only reason the pane's re-read button exists, so the
    recovery is asserted here too: re-read, re-apply, and the second edit lands.
    """
    session, client = blank
    project = _open(session, tmp_path / "race.rex", pattern_file)

    status, doc = client.get("/api/textdoc")
    assert status == 200
    revision = doc["revision"]

    def edit(text: str, path: str, replacement: str) -> str:
        out = [replacement if line.strip().startswith(path) else line
               for line in text.splitlines()]
        assert replacement in out, f"no line starts with {path!r}"
        return "\n".join(out) + "\n"

    # both writers rendered the same document and both are editing a different row
    first = edit(doc["text"], "cell.a", "  cell.a        @ 4.15678")
    second = edit(doc["text"], "scale", "  scale         @ 0.00123  min 0  softplus")

    status, applied = client.put("/api/textdoc",
                                 {"text": first, "base_revision": revision})
    assert status == 200, applied
    assert applied["applied"] and applied["revision"] != revision
    assert project.refinement.structure.phases[0].cell.a.value == 4.15678

    status, refused = client.put("/api/textdoc",
                                 {"text": second, "base_revision": revision})
    assert status == 409
    assert refused["error"]["code"] == "STALE_REVISION"
    # the *whole* second document was refused — including the row it shares with
    # the winner, which is what "all-or-nothing" has to mean when the loser's
    # text also carries the winner's old values
    assert project.refinement.structure.phases[0].cell.a.value == 4.15678
    assert project.refinement.structure.phases[0].scale.value != 0.00123
    # and a validate_only call is refused on the same grounds, before it parses:
    # a pane that keeps validating against a dead revision would report a stale
    # document as valid right up until Apply
    assert client.put("/api/textdoc", {"text": second, "base_revision": revision,
                                       "validate_only": True})[0] == 409

    # the recovery the refusal names: re-read, re-apply.  There is no merge —
    # the document is regenerated from state, so re-applying the *old* text would
    # be re-asserting the values the winner just replaced
    fresh = client.get("/api/textdoc")[1]
    assert fresh["revision"] == applied["revision"]
    again = edit(fresh["text"], "scale", "  scale         @ 0.00123  min 0  softplus")
    status, out = client.put("/api/textdoc",
                             {"text": again, "base_revision": fresh["revision"]})
    assert status == 200, out
    assert project.refinement.structure.phases[0].scale.value == 0.00123
    assert project.refinement.structure.phases[0].cell.a.value == 4.15678


def test_checkout_moves_the_working_state_and_branch_names_the_fork(
        blank, tmp_path, pattern_file):
    """Its own project, because a checkout discards the result — see below."""
    session, client = blank
    project = _open(session, tmp_path / "checkout.rex", pattern_file)
    for turn_on in (["phases.*.scale", "instrument.background.*"],
                    ["instrument.zero_shift"]):
        client.post("/api/run", {"kind": "stage",
                                 "stage": {"name": "s", "turn_on": turn_on}})
        _wait_idle(client)
    head_before = project.refinement._head_id
    root = project.history.root.id
    assert client.get("/api/result")[0] == 200

    status, payload = client.post("/api/history/checkout", {"node_id": root})
    assert status == 200 and payload["head"] == root
    assert project.refinement._head_id == root
    # …and the fitted curves went with it: they described the values a checkout
    # just replaced, so a GUI must re-run before it can export or report again
    assert client.get("/api/result")[1]["error"]["code"] == "NO_RESULT"
    assert client.get("/api/report")[0] == 409

    status, payload = client.post("/api/history/branch",
                                  {"node_id": head_before, "name": "best-so-far"})
    assert status == 200
    assert payload["head"] == head_before and payload["name"] == "best-so-far"
    assert project.history.refs["best-so-far"] == head_before
    tagged = [n for n in client.get("/api/history")[1]["nodes"]
              if "best-so-far" in n["tags"]]
    assert [n["id"] for n in tagged] == [head_before]

    status, payload = client.post("/api/history/annotate",
                                  {"node_id": head_before, "label": "keeper",
                                   "notes": {"why": "lowest Rwp"}})
    assert status == 200
    assert project.history[head_before].notes == {"why": "lowest Rwp"}
    assert client.post("/api/history/checkout", {"node_id": "n9999"})[0] == 404


def test_exports_land_in_the_project_and_cannot_escape_it(fitted, tmp_path):
    _, client, project = fitted
    for kind, suffix in (("cif", ".cif"), ("reflections", ".csv"),
                         ("html", ".html"), ("result_json", ".json")):
        status, payload = client.post(f"/api/export/{kind}")
        assert status == 200, (kind, payload)
        written = Path(payload["path"])
        assert written.parent == project.exports_dir
        assert written.suffix == suffix and payload["bytes"] > 0

    # Le Bail has no weight fractions; saying so beats writing an empty table
    status, payload = client.post("/api/export/qpa")
    assert status in (200, 409)

    status, payload = client.post("/api/export/cif",
                                  {"filename": "../../escaped.cif"})
    assert status == 400 and payload["error"]["where"] == ["filename"]
    assert not (tmp_path / "escaped.cif").exists()
    assert client.post("/api/export/nonsense")[0] == 404


# ----------------------------------------------------------------------
# the run state machine (refinement stubbed — see the module docstring)
# ----------------------------------------------------------------------
@pytest.fixture
def blocked(blank, tmp_path, pattern_file, monkeypatch):
    """A session whose "fit" blocks until the test releases it."""
    session, client = blank
    _open(session, tmp_path / "blocked.rex", pattern_file)
    started, release = threading.Event(), threading.Event()
    seen: dict = {}

    def fake_fit(*, plan=None, events=None, cancel=None, **kw):
        seen["cancel"] = cancel
        events.emit("fit_start", mode="rietveld", stages=["stub"], n_points=1)
        events.emit("stage_start", stage="stub", index=1, n_stages=1)
        started.set()
        while not release.wait(0.01):
            if cancel is not None and cancel.is_set():
                raise rx.RefinementCancelled(
                    "cancelled", stage="stub", completed_stages=[],
                    node_id=session.project.refinement._head_id)
        raise RuntimeError("stub blew up")

    monkeypatch.setattr(session.project, "fit", fake_fit)
    yield session, client, started, release, seen
    release.set()


def test_mutating_verbs_refuse_while_a_run_is_in_flight(blocked):
    session, client, started, release, _ = blocked
    assert client.post("/api/run", {"kind": "fit"})[1]["state"] == "running"
    assert started.wait(5)

    for method, path, body in (
            ("PATCH", "/api/params", {"values": {"phases.0.cell.a": 4.16}}),
            ("PATCH", "/api/params", {"vary": {"phases.*.cell.*": True}}),
            ("POST", "/api/project", {"mode": "lebail"}),
            # a settings-only patch is no exception: an exclusion changes which
            # channels the *compiled* model was built from (WP-1033)
            ("POST", "/api/project", {"excluded_regions": [[8.0, 8.5]]}),
            ("PUT", "/api/plan", {"preset": "profile_only"}),
            ("POST", "/api/run", {"kind": "fit"}),
            ("POST", "/api/history/checkout", {"node_id": "n0000"}),
            # deliberately an *invalid* body: the state refusal has to outrank
            # the body complaint, or the user debugs the wrong thing
            ("PATCH", "/api/structure", {"structure": {"phases": []}}),
            ("POST", "/api/export/cif", {}),
            ("GET", "/api/report", None),
            # …and the state refusal outranks "there is no result to apply to",
            # which is the complaint this one would otherwise answer with
            ("POST", "/api/report/apply", {"kind": "refine_cell"})):
        status, payload = client.request(method, path, body)
        assert status == 409, (path, status, payload)
        assert payload["error"]["code"] == "RUN_IN_FLIGHT", (path, payload)

    # reads stay open, and say the values are mid-run
    params = client.get("/api/params")[1]
    assert params["live"] is True
    assert client.get("/api/history")[0] == 200

    # The app's own settings are **not** among them (WP-1044), and that is the
    # finding WP-1029 recorded and could not fix from inside `POST /api/project`:
    # a theme is not model state, so refusing it mid-run with "this verb would
    # change the model a compiled stage was built from" was both a refusal
    # nobody needed and a sentence that was not true.  It is out of the locked
    # route entirely now — the project's other `ui` keys still ride it, so the
    # freeze question 1003 inherited is smaller rather than gone.
    assert client.post("/api/settings", {"ui": {"theme": "dark"}}) == (
        200, {"ui": {"theme": "dark"}})
    assert client.get("/api/settings")[0] == 200

    release.set()
    _wait_idle(client)
    # …and now the same verb goes through
    assert client.post("/api/project", {"mode": "rietveld"})[0] == 200


def test_a_failed_run_ends_the_state_machine_and_says_why(blocked):
    session, client, started, release, _ = blocked
    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)
    release.set()
    state = _wait_idle(client)
    assert state["run"]["status"] == "failed"
    assert state["run"]["error"]["code"] == "RUN_FAILED"
    assert "stub blew up" in state["run"]["error"]["message"]
    # a failure emits no fit_end, which is exactly why the state travels beside
    # the events rather than as one of them
    events = client.get("/api/events?poll=1")[1]["events"]
    assert [e["kind"] for e in events] == ["fit_start", "stage_start"]
    assert events[-1]["data"]["index"] == 1


def test_cancel_reaches_the_token_and_the_record_says_where_state_stands(blocked):
    session, client, started, _release, seen = blocked
    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)

    status, payload = client.post("/api/cancel")
    assert status == 200 and payload["state"] == "cancelling"
    assert seen["cancel"].is_set()
    state = _wait_idle(client)
    assert state["run"]["status"] == "cancelled"
    assert state["run"]["stage"] == "stub"
    # the node the working state stands at — what a "resume" button checks out
    assert state["run"]["node_id"] == session.project.refinement._head_id
    assert client.post("/api/cancel")[1]["error"]["code"] == "NOT_RUNNING"


def test_progress_needs_no_bookkeeping_beyond_the_events(blocked):
    """``stage_start`` carries 1-based ``index``/``n_stages`` (WP-1006)."""
    session, client, started, release, _ = blocked
    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)
    state = client.get("/api/run/state")[1]
    assert state["run"]["stage"] == "stub"
    assert state["run"]["stage_index"] == 1 and state["run"]["n_stages"] == 1
    assert state["run"]["elapsed"] >= 0.0
    release.set()
    _wait_idle(client)


def test_sse_delivers_events_then_the_terminal_state(blocked):
    """A follower learns the run ended even though nothing emitted ``fit_end``."""
    session, client, started, release, _ = blocked
    conn = HTTPConnection("127.0.0.1", client.port, timeout=30)
    conn.request("GET", "/api/events?since=0",
                 headers={"Host": f"127.0.0.1:{client.port}"})
    response = conn.getresponse()
    assert response.status == 200
    assert response.headers["Content-Type"].startswith("text/event-stream")

    client.post("/api/run", {"kind": "fit"})
    assert started.wait(5)
    release.set()

    names, payloads = [], []
    deadline = time.monotonic() + 30
    try:
        while time.monotonic() < deadline:
            line = response.fp.readline().decode()
            if line.startswith("event: "):
                names.append(line[7:].strip())
            elif line.startswith("data: "):
                payloads.append(json.loads(line[6:]))
                if names[-1] == "state" and payloads[-1].get("state") == "idle" \
                        and payloads[-1]["run"]["status"]:
                    break
    finally:
        conn.close()

    assert "event" in names and "state" in names
    kinds = [p["kind"] for p, n in zip(payloads, names) if n == "event"]
    assert kinds[:2] == ["fit_start", "stage_start"]
    assert payloads[-1]["run"]["status"] == "failed"


def test_a_single_stage_run_goes_through_the_same_machinery(blank, tmp_path,
                                                            pattern_file):
    session, client = blank
    project = _open(session, tmp_path / "one_stage.rex", pattern_file)
    status, payload = client.post("/api/run", {
        "kind": "stage",
        "stage": {"name": "scale_bkg",
                  "turn_on": ["phases.*.scale", "instrument.background.*"]}})
    assert status == 200, payload
    assert payload["run"]["kind"] == "stage" and payload["run"]["n_stages"] == 1
    state = _wait_idle(client)
    assert state["run"]["status"] in ("converged", "max_iter")
    assert state["run"]["rwp"] is not None
    assert project.history[state["run"]["node_id"]].action.kind == "stage"
    assert client.post("/api/run", {"kind": "wander"})[0] == 400
    assert client.post("/api/run", {"kind": "stage"})[0] == 400


def test_shutdown_stops_the_server(state_dir):
    session = GuiSession(state_dir=state_dir)
    httpd = build_server(session, port=0)
    thread = threading.Thread(target=httpd.serve_forever,
                              kwargs={"poll_interval": 0.02}, daemon=True)
    thread.start()
    client = Client(httpd.server_address[1])
    assert client.post("/api/shutdown")[1]["stopping"] is True
    thread.join(timeout=10)
    assert not thread.is_alive()
    httpd.server_close()


def test_a_busy_port_falls_back_instead_of_refusing_to_start(state_dir):
    """A second window is the ordinary case, not an error."""
    first = build_server(GuiSession(state_dir=state_dir), port=0)
    port = first.server_address[1]
    try:
        second = build_server(GuiSession(state_dir=state_dir), port=port)
        try:
            assert second.server_address[1] != port
        finally:
            second.server_close()
    finally:
        first.server_close()


# ----------------------------------------------------------------------
# the series (WP-1016)
# ----------------------------------------------------------------------
#: One stage freeing what a three-pattern chain over a cell ramp actually needs.
#: A cheap plan on purpose: what is under test is the *surface* — the staged
#: list, the events, the trajectory payload — and the chain's own behaviour is
#: ``test_sequential``'s ground, driven there without an HTTP round trip.
SERIES_PLAN = {"stages": [{"name": "quick",
                           "turn_on": ["phases.*.scale",
                                       "instrument.background.*",
                                       "instrument.zero_shift",
                                       "phases.*.cell.*"],
                           "max_iter": 25}]}


@pytest.fixture(scope="module")
def series_files(tmp_path_factory):
    """Three patterns of a cell ramp, as files — 0.05 % a step.

    The ramp matters: a series of three *identical* patterns has a flat
    trajectory, so every assertion about a trajectory would pass against an
    implementation that returned the first pattern's values three times.
    """
    from tests.test_sequential import A0, RAMP, _simulate

    root = tmp_path_factory.mktemp("gui-series")
    return [_write_xye(root / f"ramp{i}.xye", _simulate(A0 * (1 + RAMP * i),
                                                        seed=300 + i))
            for i in range(3)]


@pytest.fixture(scope="module")
def series(tmp_path_factory, series_files, state_dir):
    """A project with the three ramp patterns staged and one chain run.

    The project's own pattern is the ramp's first, so the series' protocol and
    the project's are demonstrably the same one.
    """
    project = _project(tmp_path_factory.mktemp("gui-series-proj") / "ramp.rex",
                       series_files[0])
    session = GuiSession(project, state_dir=state_dir)
    httpd = _start(session)
    client = Client(httpd.server_address[1])

    tokens = []
    for path in series_files:
        status, staged = client.upload("pattern", path.read_bytes(),
                                       filename=path.name)
        assert status == 200, staged
        tokens.append(staged["upload"])
    status, setup = client.put("/api/series", {
        "patterns": [{"upload": t, "x": 300.0 + 100 * i, "label": f"T{300 + 100 * i}"}
                     for i, t in enumerate(tokens)],
        "x_label": "T", "direction": "both"})
    assert status == 200, setup

    status, run = client.post("/api/series/run", {"plan": SERIES_PLAN})
    assert status == 200, run
    assert run["run"]["kind"] == "series"
    _wait_idle(client)
    state = client.get("/api/run/state")[1]
    assert state["run"]["status"] == "completed", state
    try:
        yield session, client, tokens
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


def test_the_series_setup_answers_before_anything_is_staged(blank, tmp_path,
                                                            pattern_file, state_dir):
    """An empty list plus the defaults *is* the empty state."""
    session, client = blank
    _open(session, tmp_path / "empty.rex", pattern_file)
    status, setup = client.get("/api/series")
    assert status == 200, setup
    assert setup["patterns"] == [] and setup["n_patterns"] == 0
    # the defaults are WP-0505's measured results, and the choices come from
    # ``sequential``'s own tuples — a menu that could offer a value the chain
    # refuses would be a second authority
    from rietx.sequential import DIRECTIONS, REFIT_MODES

    assert setup["settings"] == setup["defaults"]
    assert setup["settings"]["refit"] == "single"
    assert setup["choices"] == {"refit": list(REFIT_MODES),
                                "direction": list(DIRECTIONS)}
    # the protocol is the project's, quoted rather than re-derived
    assert setup["protocol"]["mode"] == "rietveld"
    assert setup["protocol"]["plan"] == "mccusker_default"
    assert not setup["has_result"] and not setup["running"]
    # …and there is nothing to report on yet
    status, payload = client.get("/api/series/result")
    assert status == 409 and payload["error"]["code"] == "NO_SERIES_RESULT"


def test_a_series_of_one_pattern_is_refused_as_a_fit(blank, tmp_path,
                                                      pattern_file, state_dir):
    """One pattern is a fit, and every fence a series has needs a neighbour."""
    session, client = blank
    _open(session, tmp_path / "one.rex", pattern_file)
    status, staged = client.upload("pattern", pattern_file.read_bytes(),
                                   filename=pattern_file.name)
    assert status == 200, staged
    assert client.put("/api/series",
                      {"patterns": [{"upload": staged["upload"]}]})[0] == 200
    status, payload = client.post("/api/series/run")
    assert status == 409, payload
    assert payload["error"]["code"] == "NO_SERIES"
    assert "at least two patterns" in payload["error"]["message"]


def test_the_series_refuses_a_setting_the_chain_would(blank, tmp_path,
                                                       pattern_file, state_dir):
    """Same words, because ``REFIT_MODES``/``DIRECTIONS`` are one list."""
    session, client = blank
    _open(session, tmp_path / "settings.rex", pattern_file)
    # …and the refusal names the *field*, because a form highlights what to
    # retype: a bad `refit` reported as `patterns` sends the user to the wrong
    # control
    for body, where in (({"refit": "staged"}, "refit"),
                        ({"direction": "sideways"}, "direction"),
                        ({"carry": []}, "carry"),
                        ({"patterns": [{"x": 3}]}, "patterns.0.upload"),
                        ({"patterns": "nope"}, "patterns")):
        status, payload = client.put("/api/series", body)
        assert status == 400, (body, payload)
        assert payload["error"]["where"] == [where], body
    # an unknown key names itself and says where the setting really lives
    status, payload = client.put("/api/series", {"mode": "lebail"})
    assert status == 400 and payload["error"]["where"] == ["mode"]
    assert "the project's" in payload["error"]["message"]
    # …and an upload token that was never staged is the store's own refusal
    status, payload = client.put("/api/series", {"patterns": [{"upload": "nope"}]})
    assert status == 404, payload
    assert "no staged upload" in payload["error"]["message"]


def test_a_staged_series_is_described_by_reading_it(blank, tmp_path,
                                                     series_files, state_dir):
    """Every file is read at PUT time — WP-1014's two-phase property, N files.

    And the labels a repeat produces are the ones the *run* will use: the server
    disambiguates by position, so a panel showing what it typed would be showing
    a name that names nothing.
    """
    session, client = blank
    _open(session, tmp_path / "described.rex", series_files[0])
    tokens = []
    for path in series_files[:2]:
        tokens.append(client.upload("pattern", path.read_bytes(),
                                    filename=path.name)[1]["upload"])
    status, setup = client.put("/api/series", {
        "patterns": [{"upload": t, "label": "ramp"} for t in tokens]})
    assert status == 200, setup
    assert [m["label"] for m in setup["patterns"]] == ["ramp", "ramp_1"]
    first = setup["patterns"][0]
    assert first["reader"] == "xy" and first["n_points"] == 4200
    assert first["has_sigma"] is True and not setup["sigma_mixed"]
    assert not setup["has_x"]           # no coordinate: the index is the axis

    # the same files with one esd column withheld → a mixed-weighting series,
    # which is a correctness property invisible once the files are read
    no_sigma = _write_xye(tmp_path / "bare.xye",
                          rx.read_pattern(str(series_files[1])),
                          with_sigma=False)
    tokens.append(client.upload("pattern", no_sigma.read_bytes(),
                                filename=no_sigma.name)[1]["upload"])
    status, setup = client.put("/api/series", {
        "patterns": [{"upload": t} for t in tokens]})
    assert status == 200 and setup["sigma_mixed"] is True


def test_a_coordinate_is_all_or_nothing_and_the_axis_says_which(blank, tmp_path,
                                                                series_files,
                                                                state_dir):
    """An axis whose values are indices may not be labelled ``T``.

    ``SequentialRefinement.fit`` only renames the axis in the other direction (a
    given ``x`` promotes a default ``"index"`` to ``"x"``), so a user who typed a
    label and then cleared one temperature would get a trajectory whose x values
    mean something other than what the label says.
    """
    session, client = blank
    _open(session, tmp_path / "axis.rex", series_files[0])
    tokens = [client.upload("pattern", path.read_bytes(),
                            filename=path.name)[1]["upload"]
              for path in series_files[:2]]
    body = {"patterns": [{"upload": t, "x": 300.0 + 100 * i}
                         for i, t in enumerate(tokens)], "x_label": "T"}
    assert client.put("/api/series", body)[1]["has_x"] is True
    assert session._series.axis_label == "T"

    # clear one coordinate: the setting stands, the axis does not
    body["patterns"][1].pop("x")
    setup = client.put("/api/series", body)[1]
    assert setup["has_x"] is False
    assert setup["settings"]["x_label"] == "T"     # what the user typed, kept
    assert session._series.x is None
    assert session._series.axis_label == "index"   # what the run will be told


def test_a_series_runs_and_its_trajectories_are_the_series_result(series):
    """The payload's trajectories must be ``SeriesResult``'s, not a second copy."""
    session, client, _ = series
    status, payload = client.get("/api/series/result")
    assert status == 200, payload
    result = payload["result"]
    assert len(result["entries"]) == 3
    assert result["x_label"] == "T" and result["direction"] == "both"
    assert [e["label"] for e in result["entries"]] == ["T300", "T400", "T500"]
    assert [e["x"] for e in result["entries"]] == [300.0, 400.0, 500.0]

    # …and every trajectory is the library's own, path by path
    live = session._series_run["result"]
    served = {t["path"]: t for t in payload["trajectories"]}
    for path in live.paths(varied_only=False):
        traj = live.trajectory(path)
        assert served[path]["x"] == list(traj.x), path
        assert served[path]["value"] == list(traj.value), path
        assert served[path]["stderr"] == list(traj.stderr), path
        assert served[path]["labels"] == list(traj.labels), path
        assert served[path]["x_label"] == "T"
    # the ramp is in the answer rather than three copies of one fit
    cell = served["phases.0.cell.a"]
    assert cell["value"][0] < cell["value"][1] < cell["value"][2]
    assert payload["n_iterations"] == live.n_iterations
    assert payload["curves"] == [True, True, True]


def test_the_backward_chain_travels_as_a_number_not_a_footnote(series):
    """``direction="both"`` ran, so every trajectory carries the other chain.

    The magnitude matters and no ``Diagnostic`` carries one (WP-1012's wall), so
    it is recomputed from the two chains with the fence's own arithmetic — which
    is what lets a panel rank by disagreement without a schema change.
    """
    session, client, _ = series
    payload = client.get("/api/series/result")[1]
    assert payload["has_backward"] is True
    from rietx.sequential import PATH_DEPENDENCE_SIGMA

    assert payload["path_dependence_sigma"] == PATH_DEPENDENCE_SIGMA
    served = {t["path"]: t for t in payload["trajectories"]}
    backward = session._series_run["backward"]
    assert backward is not None
    for path, row in served.items():
        if path.startswith("qpa."):
            continue
        assert row["backward"] == list(backward.trajectory(path).value), path
        # a flagged path is one the library flagged, never this layer's judgement
        assert row["path_dependent"] == (path in payload["path_dependent"]), path
        if row["path_dependent"]:
            assert row["n_sigma"] > PATH_DEPENDENCE_SIGMA, path
    assert payload["path_dependent"] == sorted(
        {d["where"][0] for d in payload["result"]["diagnostics"]
         if d["code"] == "SEQUENTIAL_PATH_DEPENDENT"})


def test_the_series_events_say_which_pattern_they_came_from(series):
    """Per-pattern telemetry on the one stream, and no new ``EventKind``.

    The series' progress is "pattern k of N" and it reaches the run record
    through the *existing* three fields, which is the same reuse an indexing run
    makes of ``stage_start``.
    """
    from rietx.history.events import EVENT_SCHEMA_VERSION

    session, client, _ = series
    events = client.get("/api/events?poll=1&since=0")[1]["events"]
    starts = [e for e in events if e["kind"] == "fit_start"]
    # three patterns each way: the backward pass is a second walk of the same
    # patterns, and `series_pass` is what distinguishes them from a restart
    assert len(starts) == 6
    assert [(e["data"]["series_index"], e["data"]["series_pass"]) for e in starts] == [
        (0, "forward"), (1, "forward"), (2, "forward"),
        (2, "backward"), (1, "backward"), (0, "backward")]
    assert {e["data"]["series_n"] for e in starts} == {3}
    assert [e["data"]["series_label"] for e in starts[:3]] == ["T300", "T400", "T500"]
    # every kind is one the closed vocabulary already had…
    assert {e["kind"] for e in events} <= {"fit_start", "stage_start", "eval",
                                            "stage_end", "fit_end"}
    # …so the schema version did not move for any of it
    assert {e["v"] for e in events} == {EVENT_SCHEMA_VERSION}
    # and the same stream landed in the log `rietx watch` tails
    logged = read_events(session.project.live_dir / "events.jsonl")
    assert sum(1 for e in logged if e.kind == "fit_start"
               and "series_index" in e.data) == 6

    # the run record read it as the chain's progress
    state = client.get("/api/run/state")[1]
    assert state["run"]["n_stages"] == 3
    assert state["run"]["completed_stages"] == ["T300", "T400", "T500"]


def test_the_progress_pill_names_the_pass_and_the_rung():
    """A pattern is fitted more than once by design, so the pill has to say why.

    Two of them on one counter: ``direction="both"`` walks every pattern again
    in reverse, and a rejected one climbs up to three rungs of the escalation
    ladder (WP-1051).  The rung is read off ``series_rung``, which rides on a
    **restart** only — so a pattern's first attempt is unsuffixed, the first
    pattern of a chain included, even though the rung it runs *is* the cold one.
    """
    from rietx.gui.session import _series_stage_name

    assert _series_stage_name({"series_label": "T300"}, 0) == "T300"
    assert _series_stage_name({"series_label": "T300",
                               "series_pass": "backward"}, 0) == "T300 (backward)"
    assert _series_stage_name(
        {"series_label": "T300", "series_rung": "warm_staged"},
        0) == "T300 (staged restart)"
    assert _series_stage_name(
        {"series_label": "T300", "series_rung": "cold", "series_cold": True},
        0) == "T300 (cold restart)"
    # no label at all: the index is the name, and nothing is claimed about rungs
    assert _series_stage_name({}, 2) == "2"


def test_a_series_window_is_the_project_plot_arithmetic(series):
    """``curve_window`` is shared, so the two panels cannot draw two σ policies."""
    from rietx.gui.session import curve_window

    session, client, _ = series
    status, payload = client.get("/api/series/window?index=1")
    assert status == 200, payload
    assert payload["index"] == 1 and payload["label"] == "T400"
    assert payload["x"] == 400.0
    result = session._series_run["runner"].results_[1]
    assert payload["n_total"] == len(result.two_theta)
    expected = curve_window(result, None, None, 4000, weighted=True)
    for key in ("two_theta", "y_obs", "y_calc", "delta", "cumulative_chi2"):
        assert payload[key] == expected[key], key
    # σ was measured (the file's esd column), which is what the flag is about
    assert payload["weighted"] is True
    # the mask travels beside the fitted channels, as it does for the project's
    # own plot — an unmasked series member has an empty arm rather than no arm
    assert payload["excluded"] == {"two_theta": [], "y_obs": []}
    assert payload["n_excluded"] == 0
    # …and it is pinned to what this member's fit actually kept, which is
    # WP-1033's `len(result.two_theta)` assertion one rank down: the mask is
    # rebuilt from the limits *this run* used, through the same function
    # `Project.fitted_mask` calls, so it cannot drift from the curves beside it
    from rietx.project import fitted_mask

    entry = session._series_run
    keep = fitted_mask(entry["data"][1], entry["limits"])
    assert int(keep.sum()) == len(result.two_theta)

    # a *later* exclusion moves the document and must not move this band: the
    # curves are the run's, and a series member cannot be re-fitted without
    # replacing the whole answer
    assert client.post("/api/project", {"excluded_regions": [[8.0, 12.0]]})[0] == 200
    try:
        again = client.get("/api/series/window?index=1")[1]
        assert again["n_excluded"] == 0, "the band followed a setting, not the fit"
        assert again["n_total"] == payload["n_total"]
    finally:
        client.post("/api/project", {"excluded_regions": []})

    # the index is required rather than defaulted: a window of "whichever
    # pattern" would draw one member's curves under another's label
    assert client.get("/api/series/window")[0] == 400
    status, payload = client.get("/api/series/window?index=9")
    assert status == 404 and payload["error"]["where"] == ["index"]


def test_a_series_member_history_is_its_own_tree_and_read_only(series):
    """One tree per pattern, pinned to its data — so its nodes are not checkouts."""
    from rietx.gui.session import tree_payload

    session, client, _ = series
    status, payload = client.get("/api/series/history?index=2")
    assert status == 200, payload
    assert payload["label"] == "T500" and payload["checkout"] is False
    tree = session._series_run["runner"].trees_[2]
    assert payload["nodes"] == tree_payload(tree)["nodes"]
    # a different tree from the project's, which is the whole reason a node here
    # cannot be restored into it
    assert payload["tree_id"] != client.get("/api/history")[1]["tree_id"]
    # the chain is recorded on the root node's notes — that is what makes a
    # series navigable, since a tree cannot have a parent edge into another
    root = next(n for n in payload["nodes"] if not n["parents"])
    assert root["notes"]["series_label"] == "T500"
    assert root["notes"]["series_position"] == "2"
    assert root["notes"]["series_warm_start_node"]


def test_the_series_is_not_in_the_project_document(series):
    """``ProjectDoc.patterns`` stays length 1, and ``Project.open`` still refuses
    more — the series lives beside the project, not inside it."""
    session, client, _ = series
    doc = client.get("/api/project")[1]
    assert len(doc["doc"]["patterns"]) == 1
    assert doc["doc"]["patterns"][0]["filename"] == "ramp0.xye"
    # nothing about the series reached the document's ui keys either
    assert "series" not in json.dumps(doc["doc"])
    # and the project's own history is untouched by three chained fits
    assert doc["n_nodes"] == 1


def test_a_series_run_holds_the_same_409_as_every_other(series, monkeypatch):
    """A mutating verb during a series is the one refusal, and the run machine is
    single-slot — a second run kind cannot start beside it."""
    session, _, _ = series
    session._state = "running"
    try:
        for verb, args in ((session.series_put, ({"carry": ["*"]},)),
                           (session.params_patch, ({"vary": {"*": False}},)),
                           (session.run, ({"kind": "series"},))):
            with pytest.raises(GuiError) as excinfo:
                verb(*args)
            assert excinfo.value.status == 409
            assert excinfo.value.code == "RUN_IN_FLIGHT"
    finally:
        session._state = "idle"


def _series_pair(forward_a, backward_a, esd=1e-4):
    """Two chains over one parameter, disagreeing by whatever is asked for.

    Built rather than fitted because the clean ramp above **agrees** — measured:
    every parameter's between-chain distance is under 5e-4 σ, which is the right
    answer for a series a warm start can legitimately walk, and it leaves the
    flagged branch unexercised.  A hand-built pair is the only way to pin the
    served magnitude against the fence that fires on it.
    """
    from rietx.schemas.results import RefinedParameter, Statistics
    from rietx.schemas.sequential import SeriesEntry, SeriesResult

    def chain(values):
        return SeriesResult(x_label="T", direction="forward", entries=[
            SeriesEntry(index=i, label=f"T{300 + 100 * i}", x=300.0 + 100 * i,
                        statistics=Statistics(rwp=0.1, rp=0.08, rexp=0.09,
                                              chi2=1.0, gof=1.0, n_points=10,
                                              n_free_parameters=1),
                        parameters=[RefinedParameter(
                            path="phases.0.cell.a", value=v, stderr=esd,
                            vary=True)])
            for i, v in enumerate(values)])

    return chain(forward_a), chain(backward_a)


def test_the_served_disagreement_is_the_fences_own_arithmetic():
    """``n_sigma`` must be the number ``SEQUENTIAL_PATH_DEPENDENT`` fired on.

    It is served at all because a ``Diagnostic`` carries ``where`` and no
    magnitude (the wall WP-1012 hit, left to WP-1003 as a freeze question): both
    chains' trajectories are in hand, so the answer is to recompute the distance
    rather than to grow the schema.
    """
    from rietx.gui import series as series_mod
    from rietx.sequential import (
        PATH_DEPENDENCE_SIGMA,
        _path_dependence_diagnostics,
    )

    forward, backward = _series_pair([4.1560, 4.1580, 4.1600],
                                     [4.1560, 4.1580, 4.1607])
    forward.diagnostics = _path_dependence_diagnostics(forward, backward)
    assert [d.code for d in forward.diagnostics] == ["SEQUENTIAL_PATH_DEPENDENT"]

    row, = series_mod.trajectories(forward, backward)
    assert row["path_dependent"] is True
    assert row["backward"] == [4.1560, 4.1580, 4.1607]
    # 0.0007 Å over √2·1e-4 σ ≈ 4.95, and the fence's own message quotes it
    assert row["n_sigma"] == pytest.approx(4.95, abs=0.01)
    assert f"{row['n_sigma']:.1f}σ" in forward.diagnostics[0].message
    assert row["n_sigma"] > PATH_DEPENDENCE_SIGMA

    payload = series_mod.result_payload(forward, backward, running=False,
                                        curves=[True, True, True])
    assert payload["path_dependent"] == ["phases.0.cell.a"]
    assert payload["path_dependence_sigma"] == PATH_DEPENDENCE_SIGMA


def test_an_unjudgeable_parameter_gets_no_disagreement_rather_than_zero():
    """Where the fence abstains, the number does too.

    A parameter with no esd in either chain cannot be judged this way, and
    reporting 0 would read as agreement it has not earned — which is exactly
    where a panel ranking by disagreement would file it.
    """
    from rietx.gui import series as series_mod

    forward, backward = _series_pair([4.156, 4.158, 4.160],
                                     [4.156, 4.158, 4.171], esd=None)
    row, = series_mod.trajectories(forward, backward)
    assert row["n_sigma"] is None
    assert row["path_dependent"] is False       # no fence fired either
    assert row["backward"] == [4.156, 4.158, 4.171]


# --------------------------------------------------------------------------- #
# What the pattern file already knows (WP-1047 tasks 15-16)
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("metadata,expected", [
    # the plain case: a name and a wavelength that agree
    ({"anode": "Cu", "wavelength": "1.540598"},
     {"preset": "bragg_brentano", "radiation": "CuKa"}),
    # the weighted mean, which is what .uxd and older exports actually write.
    # 1.5418 against Kα1 is 7.8e-4 relative — outside the tolerance — so without
    # the mean as a candidate the commonest lab value in existence would read as
    # a contradiction and suppress the hint entirely
    ({"anode": "Cu", "wavelength": "1.5418", "goniometer_radius_mm": "250.0"},
     {"preset": "bragg_brentano", "radiation": "CuKa",
      "goniometer_radius_mm": 250.0}),
    # Kα2 recorded as zero is the file saying the doublet was not used
    ({"anode": "Cu", "wavelength": "1.5406", "wavelength_alpha2": "0.0"},
     {"preset": "bragg_brentano", "radiation": "CuKa1"}),
    # …and a real Kα2 is the doublet
    ({"anode": "Cu", "wavelength": "1.5406", "wavelength_alpha2": "1.5444"},
     {"preset": "bragg_brentano", "radiation": "CuKa"}),
    # a name alone still resolves
    ({"anode": "Mo"}, {"preset": "bragg_brentano", "radiation": "MoKa"}),
    # a wavelength that is no Kα line is the synchrotron case, and the one where
    # the file knows better than any preset
    ({"wavelength": "0.4139090"},
     {"preset": "debye_scherrer", "wavelength": 0.413909}),
])
def test_the_instrument_hint_reads_the_file_rather_than_asking(metadata, expected):
    from rietx.gui.imports import suggest_instrument

    hint = suggest_instrument(metadata)
    assert hint is not None and {k: hint.get(k) for k in expected} == expected
    assert hint["why"]                      # never a bare answer


@pytest.mark.parametrize("metadata", [
    {"anode": "Cu", "wavelength": "0.4139090"},   # a name and a λ that disagree
    {"anode": "Cu", "wavelength": "0.70932"},     # …disagreeing by being Mo's
    {},                                           # nothing to go on
])
def test_a_header_that_contradicts_itself_gets_no_hint_rather_than_a_guess(metadata):
    """A wrong pre-fill is worse than an empty form: it looks like it was read.

    The contradiction is judged *after* the weighted mean is a candidate, so a
    convention difference is never mistaken for one.
    """
    from rietx.gui.imports import suggest_instrument

    assert suggest_instrument(metadata) is None


def test_the_preview_carries_the_hint_and_the_scan_count(blank):
    _, client = blank
    body = (Path(__file__).parent / "data" / "bruker_raw4_scrambled.raw").read_bytes()

    status, payload = client.upload("pattern", body, filename="d8.raw")
    assert status == 200, payload
    assert payload["metadata"]["scan_count"] == "1"
    # Kα2 = 0 with the Kα mean equal to Kα1: three fields agreeing that the
    # doublet was not used, which is the branch a real file reaches
    assert payload["instrument_hint"]["radiation"] == "CuKa1"


def test_the_scan_picker_fetches_labels_on_its_own_route(blank):
    """Separate from the preview on purpose: ``scan_count`` rides along on the
    read that already happened, and *labelling* the scans costs a second walk of
    the ranges — so it is paid when a person opens the control, not on every
    upload of a 60 MB file."""
    _, client = blank
    body = (Path(__file__).parent / "data" / "rigaku_multiscan.ras").read_bytes()
    status, payload = client.upload("pattern", body, filename="two.ras")
    assert status == 200, payload
    assert payload["metadata"]["scan_count"] == "2"

    status, listing = client.get(
        f"/api/upload/pattern/scans?upload={payload['upload']}")
    assert status == 200, listing
    assert [s["index"] for s in listing["scans"]] == [0, 1]
    # a label a picker can show: never "scan 1", which tells nobody anything
    assert all(s["label"] and s["n_points"] for s in listing["scans"])


def test_listing_the_scans_of_a_format_that_has_none_is_refused_by_name(blank):
    _, client = blank
    status, payload = client.upload("pattern", b"10 1\n20 2\n30 3\n",
                                    filename="plain.xy")
    assert status == 200, payload

    status, refusal = client.get(
        f"/api/upload/pattern/scans?upload={payload['upload']}")
    assert status == 400
    assert "one measurement per file" in refusal["error"]["message"]
