"""WP-2209: unapplied edits kept across a close or a crash.

The recovery copy lives in the state directory, keyed by the project's
resolved path and apart from the project (the maintainer's ruling of
2026-11-09). These tests hold the server half: the two routes, the refusal of
a write aimed at another project, the copy following an in-app rename and
staying behind on Save a copy, and the retention rule borrowed from
``runs.py`` (by age and size, never by count, three guards before a delete).
"""

from __future__ import annotations

import json
import os
import time

import pytest

from rietx.gui import GuiSession, recovery
from tests.test_gui_file_menu import served  # noqa: F401 - the shared fixture

DRAFT = {"count": 2, "params": {"edits": {"phases.0.cell.a": "5.4312"}},
         "plan": None}


def _project_path(client) -> str:
    return client.get("/api/project")[1]["path"]


def test_a_draft_is_kept_read_back_and_deleted(served):  # noqa: F811
    session, client, root = served
    status, payload = client.get("/api/recovery")
    assert status == 200 and payload == {"draft": None}

    path = _project_path(client)
    head = session.project.refinement._head_id
    status, payload = client.request("PUT", "/api/recovery",
                                     {"project": path, "head": head, "draft": DRAFT})
    assert status == 200, payload
    assert payload["head"] == head

    status, payload = client.get("/api/recovery")
    assert status == 200
    assert payload["draft"] == DRAFT
    assert payload["head"] == payload["head_now"] == head

    # kept apart from the project: in the state directory, never in the folder
    files = list((root / "state" / recovery.RECOVERY_DIR_NAME).glob("*.json"))
    assert len(files) == 1
    record = json.loads(files[0].read_text(encoding="utf-8"))
    assert record["record"] == recovery.RECORD_TAG and record["project"] == path
    project_files = {p.name for p in (root / "work" / "sample.rex").iterdir()}
    assert not any("recover" in name for name in project_files)

    status, payload = client.request("PUT", "/api/recovery", {"project": path, "draft": None})
    assert status == 200 and payload == {"draft": None}
    assert not list((root / "state" / recovery.RECOVERY_DIR_NAME).glob("*.json"))
    assert client.get("/api/recovery")[1] == {"draft": None}


def test_a_draft_survives_a_close_and_a_new_session(served):  # noqa: F811
    session, client, root = served
    path = _project_path(client)
    client.request("PUT", "/api/recovery", {"project": path, "draft": DRAFT})
    status, _ = client.post("/api/project/close", {})
    assert status == 200
    # a crash is a new process: a fresh session over the same state directory
    fresh = GuiSession(state_dir=root / "state")
    try:
        fresh.project_open({"path": path})
        assert fresh.recovery()["draft"] == DRAFT
    finally:
        fresh.close()


def test_a_write_names_its_project_and_needs_a_project_folder(served):  # noqa: F811
    session, client, root = served
    (root / "elsewhere.rex").mkdir()
    status, payload = client.put("/api/recovery",
                                 {"project": str(root / "elsewhere.rex"), "draft": DRAFT})
    assert status == 400 and payload["error"]["where"] == ["project"], payload
    assert client.get("/api/recovery")[1] == {"draft": None}

    path = _project_path(client)
    for body, where in (({"project": path}, "draft"),
                        ({"project": path, "draft": [1]}, "draft"),
                        ({"project": path, "head": 3, "draft": {}}, "head"),
                        ({"project": path, "draft": {}, "extra": 1}, "extra")):
        status, payload = client.request("PUT", "/api/recovery", body)
        assert status == 400 and payload["error"]["where"] == [where], payload

    # the shell's last write for a project it has just left still lands: a
    # close is answered before the shell hears of it
    client.post("/api/project/close", {})
    status, payload = client.request("PUT", "/api/recovery", {"project": path, "draft": DRAFT})
    assert status == 200, payload
    assert recovery.read(root / "state", path)["draft"] == DRAFT


def test_an_oversized_draft_is_refused(served):  # noqa: F811
    session, client, root = served
    big = {"blob": "x" * (recovery.MAX_DRAFT_BYTES + 1)}
    status, payload = client.put("/api/recovery",
                                 {"project": _project_path(client), "draft": big})
    assert status == 400 and payload["error"]["where"] == ["draft"], payload
    assert client.get("/api/recovery")[1] == {"draft": None}


def test_a_rename_takes_the_draft_and_a_copy_does_not(served):  # noqa: F811
    session, client, root = served
    client.request("PUT", "/api/recovery", {"project": _project_path(client), "draft": DRAFT})
    status, payload = client.post("/api/project/rename", {"name": "renamed"})
    assert status == 200, payload
    assert client.get("/api/recovery")[1]["draft"] == DRAFT
    assert len(list((root / "state" / recovery.RECOVERY_DIR_NAME).glob("*.json"))) == 1
    assert recovery.read(root / "state", root / "work" / "sample.rex") is None

    (root / "copies").mkdir()
    status, payload = client.post("/api/project/copy",
                                  {"directory": str(root / "copies"), "name": "copy"})
    assert status == 200, payload
    assert recovery.read(root / "state", payload["path"]) is None


def test_a_move_keys_the_old_copy_by_the_path_it_was_given(tmp_path):
    """Windows resolves a case-only rename's old name to the new folder (WP-2143).

    A symlink at the old name makes it resolve there on every platform, so a
    move that re-resolved its source would find no copy and leave the edits
    under a key nothing reads.
    """
    work = tmp_path.resolve() / "work"
    source, target = work / "sample.rex", work / "Sample2.rex"
    source.mkdir(parents=True)
    state = tmp_path / "state"
    recovery.write(state, source, DRAFT, "n1")
    source.rename(target)
    try:
        source.symlink_to(target, target_is_directory=True)
    except OSError:
        pytest.skip("this volume cannot make a symlink")
    assert recovery.move(state, source, target)
    assert recovery.read(state, target)["draft"] == DRAFT
    assert len(list(recovery.root(state).glob("*.json"))) == 1


def test_the_routes_are_not_behind_the_run_409(served, monkeypatch):  # noqa: F811
    session, client, root = served
    monkeypatch.setattr(session, "_state", "running")
    path = _project_path(client)
    status, payload = client.request("PUT", "/api/recovery", {"project": path, "draft": DRAFT})
    assert status == 200, payload
    assert client.get("/api/recovery")[1]["draft"] == DRAFT


def test_a_copy_names_its_project_whatever_its_file_is_called(tmp_path):
    a, b = tmp_path / "a.rex", tmp_path / "b.rex"
    recovery.write(tmp_path, a, DRAFT, "n1")
    # a's record copied under b's name is still a's
    recovery.path_for(tmp_path, b).write_bytes(recovery.path_for(tmp_path, a).read_bytes())
    assert recovery.read(tmp_path, b) is None
    assert recovery.read(tmp_path, a)["draft"] == DRAFT


def _aged(path, days):
    stamp = time.time() - days * 86400
    os.utime(path, (stamp, stamp))


def test_retention_is_by_age_and_size_never_by_count(tmp_path):
    folder = recovery.root(tmp_path)
    copies = [recovery.path_for(tmp_path, recovery.write(
        tmp_path, tmp_path / f"p{i}.rex", {"i": i, "pad": "x" * 1000}, None)["project"])
              for i in range(6)]
    for i, path in enumerate(copies):
        _aged(path, 30 - i)         # p0 the oldest

    size = copies[0].stat().st_size
    # under the ceiling, however many: nothing goes
    assert recovery.prune(folder, max_bytes=size * 6) == []
    # over it: oldest first, only as many as bring it under
    removed = recovery.prune(folder, max_bytes=size * 4)
    assert removed == copies[:2]
    assert all(p.exists() for p in copies[2:])


def test_retention_warns_and_keeps_what_is_young(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "_warned", False)
    folder = recovery.root(tmp_path)
    for i in range(3):
        recovery.write(tmp_path, tmp_path / f"p{i}.rex", {"pad": "x" * 1000}, None)
    with pytest.warns(UserWarning, match="Keeping them"):
        assert recovery.prune(folder, max_bytes=10) == []
    assert len(list(folder.glob("*.json"))) == 3


def test_a_delete_asks_its_three_guards(tmp_path, monkeypatch):
    monkeypatch.setattr(recovery, "_warned", False)
    folder = recovery.root(tmp_path)
    folder.mkdir(parents=True)
    # a file with a recovery name but no record tag is never deleted
    stranger = folder / ("0" * 64 + ".json")
    stranger.write_text(json.dumps({"draft": {}}), encoding="utf-8")
    # a file of another name, though it carries the tag
    other = folder / "notes.json"
    other.write_text(json.dumps({"record": recovery.RECORD_TAG, "draft": {}}),
                     encoding="utf-8")
    for path in (stranger, other):
        _aged(path, 30)
    with pytest.warns(UserWarning, match="Keeping them"):
        assert recovery.prune(folder, max_bytes=0) == []
    assert stranger.exists() and other.exists()
    # and a tagged copy outside the recovery folder is not one to delete
    outside = tmp_path / ("1" * 64 + ".json")
    outside.write_text(json.dumps({"record": recovery.RECORD_TAG, "draft": {}}),
                       encoding="utf-8")
    assert recovery._guarded_unlink(outside, tmp_path) is False
    assert outside.exists()
