"""WP-2130: the Peaks panel's indexing answer, driven in chromium with real clicks.

Two of the gaps the GUI overhaul's design rounds found in today's panel. The
search's coverage (the systems searched, the ones it did not finish, and the
run-level diagnostics naming the systems never reached) was shown only when no
candidate came back, against WP-1042's rule that what was not reached is said
loudly. And Adopt followed the gate, so on fluorapatite, where nothing reaches
``high``, no cell could be adopted. Yue ruled on 2026-11-08 that any candidate
may be adopted, and that a row the gate did not pick shows its grade and caveats
beside Adopt. The panel prints that sentence under the row's grade, because in
the Adopt column it widened the table past the side panel.

The answer is set on the session directly, as ``tests/test_gui_peaks.py`` does,
because a real search costs minutes and the panel is what is under test. Every
click is a mouse click on the element a person would press, and the shell's
landmarks (the layout test's) must not move for any of them.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing. That includes CI.
"""

from __future__ import annotations

import pytest

from rietx.gui import GuiSession
from tests.test_gui_server import _project, _start

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_gui_layout_browser import LANDMARKS, SNAP, _frames, _moved  # noqa: E402
from tests.test_watch_browser import _chromium  # noqa: E402

WHY_LOW = ("not best_or_none()'s pick: grade 'low' "
           "(fom_panel_disagrees, search_incomplete)")


def _answer():
    """Two cells from a search the ceiling stopped: one the gate picks, one not.

    The coverage is FAP's default search as the workshop measured it: cubic,
    hexagonal and trigonal searched, trigonal stopped early, the three lower
    systems never reached.
    """
    from rietx import __version__
    from rietx.schemas.common import Diagnostic, Provenance
    from rietx.schemas.indexing import CellCandidate, IndexingResult

    def cell(a: float, confidence: str, caveats: list[str]) -> CellCandidate:
        return CellCandidate(
            cell=(a, a, a, 90.0, 90.0, 90.0), cell_esd=(1e-4,) * 3 + (0.0,) * 3,
            system="cubic", centring="P", lattice_group="P m -3 m",
            volume=a ** 3, n_indexed=20, n_lines=20,
            confidence=confidence, confidence_caveats=caveats)

    exhausted = Diagnostic(
        level="warning", code="INDEX_BUDGET_EXHAUSTED",
        message="The run hit its declared ceiling of 120 s, so the answer "
                "covers what was reached.",
        where=["truncated: trigonal",
               "not reached: orthorhombic, monoclinic, triclinic"])
    return IndexingResult(
        candidates=[cell(4.1568, "high", []),
                    cell(8.3136, "low", ["fom_panel_disagrees", "search_incomplete"])],
        engines_run=["dichotomy", "trial_error"],
        systems_searched=["cubic", "hexagonal", "trigonal"],
        search_complete={"cubic": True, "hexagonal": True, "trigonal": False},
        validated=True, wavelength=1.5406, n_usable_lines=20,
        diagnostics=[exhausted],
        provenance=Provenance(package_version=__version__,
                              created_utc="2026-11-09T00:00:00Z"))


@pytest.fixture(scope="module")
def gui(tmp_path_factory):
    """A project whose session holds an indexing answer, served as ``rietx gui`` serves it."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize

    data = _write_xye(tmp_path_factory.mktemp("peaks-data") / "synth.xye", synthesize())
    project = _project(tmp_path_factory.mktemp("peaks") / "sample.rex", data)
    session = GuiSession(project, state_dir=tmp_path_factory.mktemp("peaks-state"))
    httpd = _start(session)
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/", session
    finally:
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


def _peaks_tab(browser, url: str, width: int = 1300):
    """A fresh page on the Peaks tab, reached by clicking it."""
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    page.goto(url)
    page.wait_for_selector(".actions button.refine")
    page.evaluate("document.fonts.ready")
    page.locator(".side > nav.tabs").get_by_role("button", name="Peaks", exact=True).click()
    page.wait_for_selector(".coverage")
    _frames(page)
    return page


def test_the_coverage_is_said_beside_the_candidates(browser, gui):
    url, session = gui
    with session._cond:
        session._index_result = _answer()
    page = _peaks_tab(browser, url)
    coverage = page.locator(".coverage").inner_text()
    assert "Searched: cubic, hexagonal, trigonal" in coverage
    assert "Search incomplete in trigonal" in coverage
    assert "INDEX_BUDGET_EXHAUSTED" in coverage
    assert "not reached: orthorhombic, monoclinic, triclinic" in coverage
    # the coverage sits above the list, not under a disclosure
    table = page.locator("table.candidates").bounding_box()
    assert page.locator(".coverage").bounding_box()["y"] < table["y"]
    assert page.locator(".coverage").is_visible()
    assert not page.errors, page.errors
    page.close()


def test_every_row_can_be_adopted_and_an_unpicked_one_says_why(browser, gui):
    url, session = gui
    with session._cond:
        session._index_result = _answer()
    page = _peaks_tab(browser, url)
    rows = page.locator("table.candidates tbody tr:not(.detail)")
    assert rows.count() == 2
    adopt = [rows.nth(i).get_by_role("button", name="Adopt", exact=True) for i in (0, 1)]
    assert all(a.is_enabled() for a in adopt)

    # the gate's pick wears its name as a badge and nothing more; the other row
    # says, under its grade, the sentence its adoption will record
    assert rows.nth(0).locator(".chip", has_text="best_or_none()").count() == 1
    assert rows.nth(0).locator(".why").count() == 0
    assert rows.nth(1).locator(".chip", has_text="best_or_none()").count() == 0
    assert rows.nth(1).locator(".why").inner_text() == WHY_LOW
    # and the sentence is on screen whole: its box ends inside the side panel,
    # where a sentence in the Adopt column pushed the table past it (WP-2130)
    why = rows.nth(1).locator(".why").bounding_box()
    side = page.locator(".side").bounding_box()
    assert why["x"] + why["width"] <= side["x"] + side["width"], (why, side)

    # opening a row is content inside the panel and moves no shell landmark
    before = page.evaluate(SNAP, LANDMARKS)
    rows.nth(1).locator("button.ghost").first.click()
    _frames(page)
    assert page.locator("tr.detail").count() == 1
    assert not _moved(before, page.evaluate(SNAP, LANDMARKS))

    # adopt the row the gate did not pick, with a real click
    head = session.project.refinement._head_id
    before = page.evaluate(SNAP, LANDMARKS)
    adopt[1].scroll_into_view_if_needed()
    adopt[1].click()
    page.wait_for_function(
        "document.querySelector('.console')?.textContent.includes('adopt_candidate(1)')")
    _frames(page)
    node_id = session.project.refinement._head_id
    assert node_id != head
    node = session.project.history.nodes[node_id]
    assert node.action.kind == "edit_model"
    assert node.label.endswith(f"; {WHY_LOW}")
    assert not _moved(before, page.evaluate(SNAP, LANDMARKS))
    assert not page.errors, page.errors
    page.close()
