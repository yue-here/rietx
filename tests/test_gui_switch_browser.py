"""WP-2242: another project opened in the same window shows its own data, by real clicks.

Node ids repeat across projects (``n0000``, ``n0001``, …), so two fresh projects
share a head. A panel that reloaded on the head alone kept the last project's
rows after an open, on both pages. Here projects A and B stand at the same
head and differ in their cell, and each page opens A, then B from its own
menus, and reads B's cell in the Parameters panel and B's name in the Text
buffer. Every click is a mouse click and every key a keyboard press
(gui-checks-use-real-clicks).

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing. That includes CI.
"""

from __future__ import annotations

import pytest

from rietx.gui import GuiSession
from tests.test_gui_server import _project, _start

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_watch_browser import _chromium  # noqa: E402

CELL = '[data-path="phases.0.cell.a"]'


@pytest.fixture
def served(tmp_path):
    """Projects ``a`` (a = 4.1 Å) and ``b`` (a = 4.3 Å), both at their root
    node, with ``a`` open and ``b`` on the recent list."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    data = _write_xye(tmp_path / "synth.xye", synthesize())
    paths = {}
    for name, a in (("b", 4.3), ("a", 4.1)):
        structure, _ = perturbed_models()
        cell = structure.phases[0].cell
        cell.a.value = cell.b.value = cell.c.value = a
        paths[name] = _project(tmp_path / f"{name}.rex", data, structure=structure).path
    session = GuiSession(state_dir=tmp_path / "state")
    session.project_open({"path": str(paths["b"])})
    session.project_open({"path": str(paths["a"])})
    assert session.project.refinement._head_id == "n0000"
    httpd = _start(session)
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
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


def _page(browser, url: str, ready: str):
    page = browser.new_page(viewport={"width": 1400, "height": 900})
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    page.goto(url)
    page.wait_for_selector(ready)
    page.evaluate("document.fonts.ready")
    return page


def _cell(page, scope: str) -> str:
    """The number as one string: the panel draws it in several spans."""
    return "".join(page.locator(f"{scope} {CELL}").first.text_content().split())


def _text_buffer(page, tab, name: str) -> str:
    """The Text buffer once it names project ``name``: a wait on any project
    line would pass on a buffer still loading, or on the last project's."""
    tab.click()
    page.wait_for_selector(".cm-content")
    page.wait_for_function(
        "(want) => (document.querySelector('.cm-content')?.textContent ?? '').includes(want)",
        arg=f'project "{name}"')
    return page.locator(".cm-content").first.inner_text()


def test_todays_page_shows_the_next_project_after_an_open(served, browser):
    page = _page(browser, served, ".actions button.refine")
    page.wait_for_selector(f".params {CELL}")
    assert "4.1" in _cell(page, ".params")
    text_tab = page.get_by_role("button", name="Text", exact=True)
    assert 'project "a"' in _text_buffer(page, text_tab, "a")

    # the palette's "Open or create a project" lays the start screen over the
    # project, and b's row opens it in place
    page.get_by_role("button", name="Parameters", exact=True).click()
    page.keyboard.press("Meta+k")
    page.get_by_role("button", name="Open or create a project").click()
    page.locator('.start button.row[title$="/b.rex"]').click()
    page.wait_for_selector(".start", state="detached")
    page.wait_for_function(
        "() => (document.querySelector('.params " + CELL.replace('"', '\\"')
        + "')?.textContent ?? '').includes('4.3')")
    assert "4.3" in _cell(page, ".params")
    assert 'project "b"' in _text_buffer(page, text_tab, "b")
    assert not page.errors, page.errors
    page.close()


def test_the_rebuilt_page_shows_the_next_project_after_an_open(served, browser):
    page = _page(browser, served + "next", "section.model")
    page.wait_for_selector(f"section.model {CELL}")
    assert "4.1" in _cell(page, "section.model")
    text_tab = page.locator('section.model [role="tab"]', has_text="Text")
    assert 'project "a"' in _text_buffer(page, text_tab, "a")
    page.locator('section.model [role="tab"]', has_text="Parameters").click()

    # File › Open recent › b, from the project's name in the top bar
    page.locator("header .proj button").first.click()
    page.get_by_role("menuitem", name="Open recent").click()
    page.get_by_role("menuitem", name="b", exact=True).click()
    page.wait_for_function(
        "() => (document.querySelector('section.model " + CELL.replace('"', '\\"')
        + "')?.textContent ?? '').includes('4.3')")
    assert "4.3" in _cell(page, "section.model")
    assert 'project "b"' in _text_buffer(page, text_tab, "b")
    assert not page.errors, page.errors
    page.close()
