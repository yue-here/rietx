"""WP-2243: the series workflow at ``/next``, driven in chromium with real clicks.

The Patterns step loads three files of a cell ramp through the file chooser
Add files… opens, takes a typed coordinate for each, sorts them by it and sets
the walk; the Run step then runs the chain and fills its table as the fits
land. Every click is a mouse click on the element a person would press, and no
edit in the step moves the frame's landmarks (`gui/STYLE.md` principle 4).

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing. That includes CI.
"""

from __future__ import annotations

import pytest

from rietx.gui import GuiSession
from tests.test_gui_server import _project, _start

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_gui_layout_browser import (  # noqa: E402
    NEXT_LANDMARKS,
    SNAP,
    _frames,
    _moved,
    _open_next,
)
from tests.test_watch_browser import _chromium  # noqa: E402


@pytest.fixture(scope="module")
def files(tmp_path_factory):
    """Three patterns of a cell ramp, 0.05 % a step, as files."""
    from tests.test_project import _write_xye
    from tests.test_sequential import A0, RAMP, _simulate

    root = tmp_path_factory.mktemp("series-browser")
    return [_write_xye(root / f"ramp{i}.xye", _simulate(A0 * (1 + RAMP * i), seed=300 + i))
            for i in range(3)]


@pytest.fixture(scope="module")
def gui(tmp_path_factory, files):
    """A project on the ramp's first pattern, served as ``rietx gui`` serves it."""
    project = _project(tmp_path_factory.mktemp("series-proj") / "ramp.rex", files[0])
    session = GuiSession(project, state_dir=tmp_path_factory.mktemp("series-state"))
    httpd = _start(session)
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/", session
    finally:
        session.close()
        httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            handle = p.chromium.launch(executable_path=_chromium() or None)
        except Exception as exc:  # noqa: BLE001 - any launch failure is a skip
            pytest.skip(f"no chromium to drive: {exc}")
        yield handle
        handle.close()


def _rows(page) -> list[list[str]]:
    return page.locator("table.rows tbody tr").evaluate_all(
        "trs => trs.map(tr => [...tr.cells].map(td =>"
        " (td.querySelector('input')?.value ?? td.textContent).trim()))")


def test_a_series_is_loaded_sorted_walked_and_run(browser, gui, files):
    url, session = gui
    page = _open_next(browser, url, 1440)
    page.locator("button.mbtn.wf").click()
    page.get_by_role("menuitemradio", name="Series", exact=True).click()
    page.wait_for_selector(".wfsteps .empty")
    assert page.locator("nav.steps button.step").all_inner_texts() == [
        "1\nPatterns", "2\nFirst fit", "3\nRun", "4\nResults"]

    # many files at once, through the chooser a person's click opens
    with page.expect_file_chooser() as chooser:
        page.get_by_role("button", name="Add files…").click()
    chooser.value.set_files([str(f) for f in reversed(files)])
    page.wait_for_function("document.querySelectorAll('table.rows tbody tr').length === 3")
    assert [r[1] for r in _rows(page)] == ["ramp2.xye", "ramp1.xye", "ramp0.xye"]
    assert page.locator(".wfsteps h3").first.inner_text().startswith("Patterns3 files · ")

    # typing a coordinate and choosing the walk move nothing in the frame
    before = page.evaluate(SNAP, NEXT_LANDMARKS)
    for i, t in enumerate(("500", "400", "300")):
        box = page.locator("input.coord").nth(i)
        box.click()
        box.fill(t)
        box.press("Tab")
        page.wait_for_function(
            "([i, t]) => document.querySelectorAll('input.coord')[i]?.value === t", arg=[i, t])
    page.get_by_role("button", name="Both, and compare").click()
    page.wait_for_function("document.querySelector('.foot .muted')?.textContent.includes('two walks')")
    _frames(page)
    assert not _moved(before, page.evaluate(SNAP, NEXT_LANDMARKS))

    sort = page.get_by_role("button", name="Sort by index")
    sort.click()
    page.wait_for_function(
        "document.querySelector('table.rows tbody tr td.fname')?.textContent === 'ramp0.xye'")
    assert [r[2] for r in _rows(page)] == ["300", "400", "500"]
    assert sort.is_disabled()
    assert [m["label"] for m in session.series()["patterns"]] == ["ramp0", "ramp1", "ramp2"]
    assert session.series()["settings"]["direction"] == "both"

    # Run series moves the strip to Run, and the table fills from the events
    page.get_by_role("button", name="Run series").click()
    page.wait_for_selector("nav.steps button.step[aria-current=step] >> text=Run")
    page.wait_for_selector(".wfsteps .foot >> text=See results", timeout=180_000)
    status = page.locator(".wfsteps .status").inner_text()
    assert status.startswith("Finished · "), status
    rows = _rows(page)
    assert [r[1] for r in rows] == ["ramp0", "ramp1", "ramp2"]
    assert all(r[3] for r in rows), rows                      # every Rwp landed
    assert rows[0][4] == "model" and rows[1][4].startswith("previous"), rows
    # the second walk's Rwp, followed live, so every one landed as a number
    assert all(r[5] not in ("", "✓", "…") and float(r[5]) > 0 for r in rows), rows
    assert page.locator(".gauge").get_attribute("aria-valuenow") == "100"
    assert not page.errors, page.errors
    page.close()

    # a page opened after the run reads the same table off the record
    page = _open_next(browser, url, 1440)
    page.locator("button.mbtn.wf").click()
    page.get_by_role("menuitemradio", name="Series", exact=True).click()
    page.locator("nav.steps button.step", has_text="Run").click()
    page.wait_for_selector(".wfsteps .status >> text=Finished")
    assert [r[3] for r in _rows(page)] == [r[3] for r in rows]
    assert [r[5] for r in _rows(page)] == ["✓", "✓", "✓"]
    assert page.locator(".gauge").get_attribute("aria-valuenow") == "100"
    assert not page.errors, page.errors
    page.close()
