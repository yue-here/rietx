"""The Console's script, end to end in a real browser (WP-2212).

A session at ``/next`` sets a value and refines as ticked on one copy of a
project; File › Export › Console as a Python script writes the session; the
script runs on a second copy, made before the session started. The two heads
must then hold the same parameter values, which is what "the session as a
script" promises. A script that echoed a call it did not run, or missed one
it did, lands on other values.

Driven with real clicks and keys (the GUI's checks use real clicks). Skips
without playwright, as every browser file does, so CI never runs it.
"""
from __future__ import annotations

import shutil
import subprocess
import sys

import pytest

import rietx as rx
from rietx.gui import GuiSession
from tests.test_gui_server import Client, _project, _start, _wait_idle

pytest.importorskip("playwright")

from tests.test_gui_layout_browser import _frames, _keep_no_edits, browser  # noqa: E402, F401

PATH = "instrument.zero_shift"


def test_the_exported_script_repeats_the_session_on_a_copy(browser, tmp_path,  # noqa: F811
                                                          monkeypatch):
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize

    root = tmp_path.resolve()
    monkeypatch.setattr(GuiSession, "_fs_roots", lambda self: [root])
    data = _write_xye(root / "synth.xye", synthesize())
    (root / "a").mkdir()
    _project(root / "a" / "sample.rex", data)
    shutil.copytree(root / "a" / "sample.rex", root / "copy.rex")
    session = GuiSession(state_dir=root / "state")
    session.project_open({"path": str(root / "a" / "sample.rex")})
    httpd = _start(session)
    client = Client(httpd.server_address[1])
    try:
        page = browser.new_page(viewport={"width": 1440, "height": 900})
        page.errors = []
        page.on("pageerror", lambda exc: page.errors.append(str(exc)))
        _keep_no_edits(page)
        page.goto(f"http://127.0.0.1:{httpd.server_address[1]}/next")
        page.wait_for_selector(".actions button.refine")
        page.evaluate("document.fonts.ready")
        _frames(page)

        # a value typed into the Parameters panel
        page.locator("section.model .tabs").get_by_role("tab", name="Parameters", exact=True).click()
        # and the scale freed, so the cycle has something to refine
        page.locator(".params .row", has=page.locator(
            'button.ink[data-path="phases.0.scale"]')).locator("input.vary").click()
        cell = page.locator(f'.params .row button.ink[data-path="{PATH}"]')
        cell.scroll_into_view_if_needed()
        cell.click()
        page.locator("input.editor").wait_for()
        page.keyboard.press("ControlOrMeta+a")
        page.keyboard.type("0.012")
        page.keyboard.press("Enter")
        _frames(page)

        # As ticked, which applies the pending edit first, with the Console open
        page.locator("footer button.console").click()
        head = client.get("/api/project")[1]["head"]
        page.locator(".actions button", has_text="As ticked").click()
        page.locator(".actions button.refine").click()
        page.wait_for_function(
            "document.querySelector('section.console')?.textContent.includes('p.run_stage')")
        while client.get("/api/project")[1]["head"] == head:
            page.wait_for_timeout(50)
        _wait_idle(client)
        # the page hears the run end on the stream: Refine comes back
        page.wait_for_selector(".actions button.refine:not([disabled])")
        _frames(page)
        out = root.parent / "console-shots"
        out.mkdir(exist_ok=True)
        page.screenshot(path=str(out / "console.png"))

        # File › Export › Console as a Python script, into the folder beside the project
        page.locator("header .fm-name").click()
        page.locator(".fm-menu").first.get_by_role("menuitem", name="Export").hover()
        page.locator(".fm-sub").get_by_role("menuitem", name="Console as a Python script…").click()
        dialog = page.locator('[aria-labelledby="fm-title"]')
        dialog.wait_for()
        assert dialog.locator("h2").text_content() == "Export console as a Python script"
        dialog.get_by_role("button", name="Export").click()
        script = root / "a" / "sample.py"
        page.wait_for_function("!document.querySelector('[aria-labelledby=\"fm-title\"]')")
        assert script.is_file()
        text = script.read_text(encoding="utf-8")
        for call in ("ref.set_values(", 'ref.set_vary("phases.0.scale", True)', "p.run_stage("):
            assert call in text, (call, text)
        assert not page.errors, page.errors
        page.close()
    finally:
        session.close()
        httpd.shutdown()
        httpd.server_close()

    def values(path):
        project = rx.Project.open(path)
        return {r.path: r.value for r in project.parameters()}

    start = values(root / "copy.rex")
    run = subprocess.run([sys.executable, str(script), str(root / "copy.rex")],
                         capture_output=True, text=True, timeout=300, cwd=root)
    assert run.returncode == 0, run.stderr[-2000:]
    session_values = values(root / "a" / "sample.rex")
    script_values = values(root / "copy.rex")
    # the session moved the value it typed, so agreeing is not both standing still
    assert session_values[PATH] != start[PATH]
    assert session_values["phases.0.scale"] != start["phases.0.scale"]
    assert script_values.keys() == session_values.keys()
    differ = {k: (session_values[k], script_values[k]) for k in session_values
              if abs(session_values[k] - script_values[k]) > 1e-9 * max(1.0, abs(session_values[k]))}
    assert not differ, differ
