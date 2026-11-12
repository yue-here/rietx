"""WP-2133: the File menu's routes — copy, rename, move, close, and export elsewhere.

The maintainer's save model A (2026-11-07): work saves itself, so the File
menu acts on the project's *folder*. Each verb is checked over HTTP for what it
does and for each refusal: an existing destination (409, never replaced), a
destination outside the folder browser's roots, a name that is not one folder
name, a folder moved into itself, and a run in flight (409, outranking every
other refusal).

The browsable roots are the home directory and the working directory, which a
pytest ``tmp_path`` is under neither of, so each test narrows them to its own
``tmp_path``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import rietx as rx
from rietx.gui import GuiSession
from tests.test_gui_server import Client, _project, _start


@pytest.fixture
def served(tmp_path, monkeypatch):
    """A served session over a fresh project, its roots confined to ``tmp_path``."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize

    root = tmp_path.resolve()
    monkeypatch.setattr(GuiSession, "_fs_roots", lambda self: [root])
    (root / "data").mkdir()
    data = _write_xye(root / "data" / "synth.xye", synthesize())
    (root / "work").mkdir()
    _project(root / "work" / "sample.rex", data)
    session = GuiSession(state_dir=root / "state")
    session.project_open({"path": str(root / "work" / "sample.rex")})
    httpd = _start(session)
    try:
        yield session, Client(httpd.server_address[1]), root
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()


def _recent_paths(session) -> list[str]:
    return [row["path"] for row in session.recent()]


def test_save_a_copy_copies_the_folder_with_its_history_and_stays(served):
    session, client, root = served
    (root / "copies").mkdir()
    status, payload = client.post("/api/project/copy",
                                  {"directory": str(root / "copies"), "name": "sample copy"})
    assert status == 200, payload
    copy = root / "copies" / "sample copy.rex"
    assert payload["path"] == str(copy)
    original = root / "work" / "sample.rex"
    assert (copy / "history.jsonl").read_bytes() == (original / "history.jsonl").read_bytes()
    # the copy is a project of its own, and the window kept the one it had
    assert rx.Project.open(copy).refinement.structure.phases
    assert session.project.path == original
    assert client.get("/api/project")[1]["path"] == str(original)


def test_a_copy_refuses_an_existing_folder_a_bad_name_and_a_foreign_folder(served, tmp_path_factory):
    session, client, root = served
    (root / "copies" / "taken.rex").mkdir(parents=True)
    marker = root / "copies" / "taken.rex" / "keep.txt"
    marker.write_text("mine", encoding="utf-8")
    status, payload = client.post("/api/project/copy",
                                  {"directory": str(root / "copies"), "name": "taken"})
    assert status == 409 and payload["error"]["code"] == "DESTINATION_EXISTS", payload
    assert marker.read_text(encoding="utf-8") == "mine"      # never replaced

    for name in ("", "  ", "../escape", "a/b", "a\\b", ".hidden"):
        status, payload = client.post("/api/project/copy",
                                      {"directory": str(root / "copies"), "name": name})
        assert status == 400 and payload["error"]["where"] == ["name"], (name, payload)

    elsewhere = tmp_path_factory.mktemp("outside-the-roots")
    status, payload = client.post("/api/project/copy",
                                  {"directory": str(elsewhere), "name": "x"})
    assert status == 400 and payload["error"]["where"] == ["directory"], payload
    assert not list(elsewhere.iterdir())

    status, payload = client.post("/api/project/copy", {
        "directory": str(root / "work" / "sample.rex"), "name": "inside"})
    assert status == 400 and "into itself" in payload["error"]["message"], payload


def test_rename_moves_the_folder_and_the_history_follows(served):
    session, client, root = served
    old = root / "work" / "sample.rex"
    status, payload = client.post("/api/project/rename", {"name": "renamed"})
    assert status == 200, payload
    new = root / "work" / "renamed.rex"
    assert payload["path"] == str(new) and not old.exists()
    assert _recent_paths(session) == [str(new)]
    # a later node is appended to the log where it now lives
    before = len((new / "history.jsonl").read_text(encoding="utf-8").splitlines())
    status, _ = client.patch("/api/params", {"vary": {"phases.*.scale": True}})
    assert status == 200
    after = len((new / "history.jsonl").read_text(encoding="utf-8").splitlines())
    assert after > before
    assert rx.Project.open(new).refinement.structure.phases
    # the same name is no change and no error; ".rex" typed or not is one name
    assert client.post("/api/project/rename", {"name": "renamed.rex"})[0] == 200


def test_rename_refuses_an_existing_folder_and_a_bad_name(served):
    session, client, root = served
    (root / "work" / "other.rex").mkdir()
    status, payload = client.post("/api/project/rename", {"name": "other"})
    assert status == 409 and payload["error"]["code"] == "DESTINATION_EXISTS", payload
    for name in ("../up", "a/b", ".dot", ""):
        status, payload = client.post("/api/project/rename", {"name": name})
        assert status == 400, (name, payload)
    assert session.project.path == root / "work" / "sample.rex"


def test_move_keeps_the_name_and_refuses_what_it_must(served, tmp_path_factory):
    session, client, root = served
    (root / "moved").mkdir()
    status, payload = client.post("/api/project/move", {"directory": str(root / "moved")})
    assert status == 200, payload
    new = root / "moved" / "sample.rex"
    assert payload["path"] == str(new) and (new / "project.json").is_file()
    assert _recent_paths(session) == [str(new)]

    (root / "busy" / "sample.rex").mkdir(parents=True)
    status, payload = client.post("/api/project/move", {"directory": str(root / "busy")})
    assert status == 409 and payload["error"]["code"] == "DESTINATION_EXISTS", payload

    status, payload = client.post("/api/project/move", {"directory": str(new / "exports")})
    assert status == 400, payload

    status, payload = client.post("/api/project/move",
                                  {"directory": str(tmp_path_factory.mktemp("not-a-root"))})
    assert status == 400 and payload["error"]["where"] == ["directory"], payload
    assert session.project.path == new


def test_move_keeps_a_folder_name_without_the_suffix(served):
    """A project the Python API made may lack ``.rex``; a move must not rename it."""
    session, client, root = served
    plain = root / "work" / "plain"
    _project(plain, root / "data" / "synth.xye")
    session.project_open({"path": str(plain)})
    (root / "moved").mkdir()
    status, payload = client.post("/api/project/move", {"directory": str(root / "moved")})
    assert status == 200, payload
    assert payload["path"] == str(root / "moved" / "plain")
    assert (root / "moved" / "plain" / "project.json").is_file()


def test_a_case_only_rename_is_not_refused_as_an_existing_folder(served):
    session, client, root = served
    probe = root / "work" / "SAMPLE.rex"
    if not probe.exists():
        pytest.skip("a case-sensitive volume: the two names are two folders")
    draft = {"edits": {"phases.0.cell.a": 4.2}}
    client.request("PUT", "/api/recovery",
                   {"project": str(root / "work" / "sample.rex"), "draft": draft})
    status, payload = client.post("/api/project/rename", {"name": "Sample"})
    assert status == 200, payload
    assert Path(payload["path"]).name == "Sample.rex"
    assert [p.name for p in (root / "work").iterdir()] == ["Sample.rex"]
    # the pending edits follow the folder (WP-2143)
    assert client.get("/api/recovery")[1]["draft"] == draft


def test_project_doc_path_is_absolute_for_a_relative_open(served, monkeypatch):
    """`rietx gui sample.rex` opens a relative path, and the File menu reads
    the folder a copy starts in off this string."""
    session, client, root = served
    monkeypatch.chdir(root / "work")
    session.project_open({"path": "sample.rex"})
    assert client.get("/api/project")[1]["path"] == str(root / "work" / "sample.rex")


def test_close_empties_the_session_and_the_next_launch_starts_on_the_start_screen(served):
    session, client, root = served
    path = str(root / "work" / "sample.rex")
    status, payload = client.post("/api/project/close")
    assert status == 200 and payload == {"closed": path}
    status, payload = client.get("/api/project")
    assert status == 409 and payload["error"]["code"] == "NO_PROJECT"
    assert session.recent()[0]["closed"] is True

    again = GuiSession(state_dir=root / "state")
    assert again.reopen_last() is None and again.project is None
    # opening it again clears the mark, so a quit with it open reopens it
    again.project_open({"path": path})
    third = GuiSession(state_dir=root / "state")
    assert third.reopen_last() == path
    for s in (again, third):
        s.close()


def test_clear_the_recent_list(served):
    session, client, _ = served
    assert session.recent()
    status, payload = client.post("/api/recent/clear")
    assert status == 200 and payload == {"recent": []}
    assert session.recent() == []
    assert session.project is not None      # the list only


def test_export_into_a_chosen_folder_asks_before_replacing(served, tmp_path_factory):
    session, client, root = served
    status, payload = client.post("/api/export/instrument_profile", {
        "directory": str(root / "data"), "filename": "lab.json"})
    assert status == 200, payload
    target = root / "data" / "lab.json"
    assert payload["path"] == str(target) and target.is_file()

    target.write_text("{}", encoding="utf-8")
    status, payload = client.post("/api/export/instrument_profile", {
        "directory": str(root / "data"), "filename": "lab.json"})
    assert status == 409 and payload["error"]["code"] == "DESTINATION_EXISTS", payload
    assert payload["error"]["where"] == ["filename"]
    assert target.read_text(encoding="utf-8") == "{}"
    status, _ = client.post("/api/export/instrument_profile", {
        "directory": str(root / "data"), "filename": "lab.json", "overwrite": True})
    assert status == 200 and target.read_text(encoding="utf-8") != "{}"

    for filename in ("../up.json", ".hidden", "a/b.json"):
        status, payload = client.post("/api/export/instrument_profile", {
            "directory": str(root / "data"), "filename": filename})
        assert status == 400 and payload["error"]["where"] == ["filename"], (filename, payload)
    status, payload = client.post("/api/export/instrument_profile", {
        "directory": str(tmp_path_factory.mktemp("not-a-root")), "filename": "x.json"})
    assert status == 400 and payload["error"]["where"] == ["directory"], payload
    # a write the folder refuses is a refusal the dialog shows, never a 500
    (root / "data" / "taken.json").mkdir()
    status, payload = client.post("/api/export/instrument_profile", {
        "directory": str(root / "data"), "filename": "taken.json", "overwrite": True})
    assert status == 400 and payload["error"]["where"] == ["directory"], payload
    # without a folder it goes to exports/ as before, replacing its namesake
    assert client.post("/api/export/instrument_profile")[0] == 200
    assert client.post("/api/export/instrument_profile")[0] == 200


def test_every_file_menu_verb_refuses_while_a_run_is_in_flight(served):
    """The 409 contract, which outranks body validation: each body here is
    invalid, so a 400 would mean the state check came second."""
    session, client, root = served
    session._state = "running"
    try:
        for path, body in (("/api/project/copy", {}), ("/api/project/rename", {}),
                           ("/api/project/move", {}), ("/api/project/close", None),
                           ("/api/export/instrument_profile", {"directory": "/nowhere"})):
            status, payload = client.post(path, body)
            assert status == 409, (path, status, payload)
            assert payload["error"]["code"] == "RUN_IN_FLIGHT", (path, payload)
    finally:
        session._state = "idle"
    assert session.project.path == root / "work" / "sample.rex"


def test_the_menus_export_kinds_are_the_servers():
    """`lib/filemenu.ts` names each export kind with its default file name. A
    kind the server adds, or a default it renames, fails here until the menu
    follows, since the menu cannot import Python."""
    import re

    from rietx.gui.session import EXPORT_DEFAULTS

    text = (Path(__file__).parents[1] / "gui" / "src" / "lib" / "filemenu.ts").read_text(
        encoding="utf-8")
    kinds = dict(re.findall(r'kind: "(\w+)",[^}]*?file: "([^"]+)"', text))
    assert kinds == EXPORT_DEFAULTS
