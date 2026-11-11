"""WP-2209: unapplied edits survive a closed tab and a restarted server, by real clicks.

The maintainer ruled on 2026-11-09 that pending edits follow the software
field's practice: a recovery copy in rietx's state directory, keyed by the
project's path and apart from the project, as VS Code's hot exit keeps its
backups. Reopening offers the edits, and the person restores or discards them.

Each test types a value into the Parameters panel the way a person does, then
loses the page: a tab closed, or a new server process over the same state
directory standing in for a crash. The next page must offer the edit, and
Restore must put it back as pending while Discard deletes the copy. Escape
closes the offer and keeps the copy, which the next open offers again (the
maintainer's ruling of 2026-11-10). Every click is a mouse click and every key
a keyboard press (gui-checks-use-real-clicks).

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing. That includes CI.
"""

from __future__ import annotations

import time

import pytest

from rietx.gui import GuiSession, recovery
from tests.test_gui_server import _project, _start

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_watch_browser import _chromium  # noqa: E402

PATH = "phases.0.cell.a"


@pytest.fixture
def served(tmp_path):
    """A project and a state directory of its own, and a way to serve them.

    ``serve()`` starts a fresh session each call, which is what a restarted
    server is: nothing survives in memory, only the state directory.
    """
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize

    data = _write_xye(tmp_path / "synth.xye", synthesize())
    project = _project(tmp_path / "sample.rex", data)
    state = tmp_path / "state"
    started = []

    def serve() -> str:
        session = GuiSession(state_dir=state)
        session.project_open({"path": str(project.path)})
        httpd = _start(session)
        started.append((session, httpd))
        return f"http://127.0.0.1:{httpd.server_address[1]}/"

    try:
        yield serve, state, project.path
    finally:
        for session, httpd in started:
            session.close()
            httpd.shutdown()
            httpd.server_close()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            handle = p.chromium.launch(executable_path=_chromium() or None)
        except Exception as exc:  # noqa: BLE001 - any launch failure is a skip
            pytest.skip(f"no chromium to drive: {exc}")
        yield handle
        handle.close()


def _page(browser, url: str):
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    page.goto(url)
    page.wait_for_selector(".actions button.refine")
    page.evaluate("document.fonts.ready")
    return page


def _type_value(page, text: str) -> None:
    """Press the number, type into the editor floating over it, press Enter."""
    number = page.locator(f'.params .ink[data-path="{PATH}"]')
    number.evaluate("e => e.scrollIntoView({block: 'center'})")
    number.click()
    page.wait_for_selector("input.editor")
    page.keyboard.press("Meta+A")
    page.keyboard.type(text)
    page.keyboard.press("Enter")
    page.wait_for_function(
        "() => document.querySelector('.actions .pending')?.textContent === '1 pending edit'")


def _until(predicate, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if predicate():
            return True
        time.sleep(0.05)
    return predicate()


def _kept(state, project):
    record = recovery.read(state, project)
    return None if record is None else record["draft"]


def test_an_edit_survives_a_restarted_server_and_restores(served, browser):
    serve, state, project = served
    page = _page(browser, serve())
    assert page.locator(".rc-dialog").count() == 0
    _type_value(page, "5.5")
    assert _until(lambda: _kept(state, project) is not None)
    assert _kept(state, project)["params"]["edits"] == {PATH: "5.5"}
    assert not any("recover" in p.name for p in project.iterdir())
    page.close()

    # a crash: a new process over the same state directory
    page = _page(browser, serve())
    dialog = page.locator(".rc-dialog")
    dialog.wait_for()
    assert dialog.locator("h2").inner_text() == "Unapplied edits"
    assert "1 edit from" in dialog.inner_text()
    dialog.get_by_role("button", name="Restore", exact=True).click()
    dialog.wait_for(state="detached")
    assert page.locator(".actions .pending").inner_text() == "1 pending edit"
    number = page.locator(f'.params .ink[data-path="{PATH}"]')
    # the number is drawn in slots, one element a part
    assert "".join(number.inner_text().split()) == "5.5"

    # Revert is a discard: the copy goes with the edit
    page.locator(".actions").get_by_role("button", name="Revert", exact=True).click()
    assert _until(lambda: _kept(state, project) is None)
    assert page.errors == []
    page.close()


def test_a_closed_tab_keeps_an_edit_and_discard_deletes_it(served, browser):
    serve, state, project = served
    url = serve()
    page = _page(browser, url)
    _type_value(page, "5.6")
    # closed before the half-second timer: the page's own pagehide sends it
    page.close(run_before_unload=True)
    assert _until(lambda: _kept(state, project) is not None)

    page = _page(browser, url)
    dialog = page.locator(".rc-dialog")
    dialog.wait_for()
    dialog.get_by_role("button", name="Discard", exact=True).click()
    dialog.wait_for(state="detached")
    assert _until(lambda: _kept(state, project) is None)
    assert page.locator(".actions .pending").inner_text() == ""
    assert page.errors == []
    page.close()


def test_escape_keeps_the_copy_and_the_next_open_offers_it(served, browser):
    serve, state, project = served
    url = serve()
    page = _page(browser, url)
    _type_value(page, "5.7")
    assert _until(lambda: _kept(state, project) is not None)
    page.close()

    page = _page(browser, url)
    dialog = page.locator(".rc-dialog")
    dialog.wait_for()
    page.keyboard.press("Escape")
    dialog.wait_for(state="detached")
    # neither restored nor discarded
    assert page.locator(".actions .pending").inner_text() == ""
    time.sleep(1.0)  # past the writer's half second
    assert _kept(state, project)["params"]["edits"] == {PATH: "5.7"}

    # close the project from the File menu, and open it again from the list
    page.locator("header .fm-name").click()
    page.locator(".fm-menu button.item").filter(
        has=page.locator(".label").get_by_text("Close project", exact=True)).click()
    row = page.locator(".start li").filter(
        has=page.locator(".name").get_by_text("sample", exact=True))
    row.locator("button.row").click()
    dialog.wait_for()
    assert dialog.locator("h2").inner_text() == "Unapplied edits"
    assert _kept(state, project)["params"]["edits"] == {PATH: "5.7"}
    assert page.errors == []
    page.close()
