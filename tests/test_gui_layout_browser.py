"""WP-2123: no click moves the GUI's layout unless the click asks it to.

The maintainer's interaction rule, ruled 2026-11-07, is that pressing a control
may change what a region shows and never where the regions are. A collapse
button asks for a move, so it is the one exception. jsdom has no layout, so
this file asks chromium: it clicks every other shell control on a fresh page,
with a real mouse click, and compares the boxes of the shell's landmarks
before and after. A landmark that moved by more than a pixel fails, named by
its selector and the control that moved it.

Two starting states are swept: a wide window with the two sides beside each
other, and a narrow one below the one-column threshold, where they stack.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing, as its siblings do. That includes
CI.
"""

from __future__ import annotations

import pytest

from rietx.gui import GuiSession
from tests.test_gui_server import Client, _project, _start, _wait_idle

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_watch_browser import _chromium  # noqa: E402

#: The shell's regions and the controls that stay put inside them. A panel's
#: own content is not here: a tab click is meant to change it.
LANDMARKS = [
    "#app > header", "#app > header > button.toggle", "#app > header > .bar",
    "#app > header .controls > *",
    ".plotcol", ".plotcol > nav.tabs", ".gtitle", ".side", ".side > nav.tabs",
    ".actions", ".actions .segmented", ".actions .go > *", ".console",
]

#: Every landmark's box, keyed by its selector and its place among the matches.
SNAP = """(selectors) => {
  const out = {};
  selectors.forEach((sel) => {
    [...document.querySelectorAll(sel)].forEach((e, i) => {
      if (!e.getClientRects().length) return;
      const r = e.getBoundingClientRect();
      out[`${sel} #${i}`] = [r.x, r.y, r.width, r.height];
    });
  });
  return out;
}"""

#: The controls the sweep presses, each with a label the failure can name.
#: A collapse button asks for the layout to change; Refine runs a fit and has a
#: test of its own; Cancel is disabled while idle.
CONTROLS = """() => [...document.querySelectorAll(
    "#app > header .bar button, .plotcol > nav.tabs button, .side > nav.tabs button, .actions button")]
  .filter((b) => b.getClientRects().length && !b.disabled && !b.classList.contains("refine"))
  .map((b) => (b.getAttribute("aria-label") || b.textContent || "").trim())"""

WIDTHS = {"wide": 1300, "stacked": 700}


def _serve(tmp_path_factory, name: str):
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize

    data = _write_xye(tmp_path_factory.mktemp(f"{name}-data") / "synth.xye", synthesize())
    project = _project(tmp_path_factory.mktemp(name) / "sample.rex", data)
    session = GuiSession(project, state_dir=tmp_path_factory.mktemp(f"{name}-state"))
    httpd = _start(session)
    client = Client(httpd.server_address[1])
    status, run = client.post("/api/run", {"kind": "stage", "stage": {
        "name": "scale", "turn_on": ["phases.*.scale"], "max_iter": 5}})
    assert status == 200, run
    _wait_idle(client)
    return httpd, client


@pytest.fixture(scope="module")
def gui(tmp_path_factory):
    """A project with one fitted stage, served as ``rietx gui`` serves it."""
    httpd, client = _serve(tmp_path_factory, "layout")
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/", client
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


def _open(browser, url: str, width: int):
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    # a dialog left open would hold every later click; none is expected here
    page.on("dialog", lambda dialog: dialog.dismiss())
    page.goto(url)
    page.wait_for_selector(".actions button.refine")
    page.evaluate("document.fonts.ready")
    _frames(page)
    return page


def _frames(page, n: int = 3) -> None:
    """Wait ``n`` animation frames, which is when a paint has happened, never a timer."""
    page.evaluate("n => new Promise(r => { const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(); f(n); })", n)


def _moved(before: dict, after: dict) -> list[str]:
    out = []
    for key, box in before.items():
        if key not in after:
            continue
        delta = [b - a for a, b in zip(box, after[key])]
        if any(abs(d) > 1 for d in delta):
            out.append(f"{key} dx={delta[0]:.0f} dy={delta[1]:.0f} "
                       f"dw={delta[2]:.0f} dh={delta[3]:.0f}")
    return out


def _press(page, label: str) -> None:
    """A real mouse click on the control carrying ``label``, never a scripted one."""
    candidates = page.locator(
        "#app > header .bar button, .plotcol > nav.tabs button, .side > nav.tabs button, .actions button")
    for i in range(candidates.count()):
        button = candidates.nth(i)
        name = (button.get_attribute("aria-label") or button.text_content() or "").strip()
        if name == label and button.is_visible() and button.is_enabled():
            button.click()
            return
    raise AssertionError(f"no enabled control named {label!r}")


@pytest.mark.parametrize("state", list(WIDTHS))
def test_no_shell_control_moves_the_layout(browser, gui, state):
    url, _ = gui
    page = _open(browser, url, WIDTHS[state])
    labels = page.evaluate(CONTROLS)
    page.close()
    assert len(labels) > 15, labels

    failures = []
    for label in labels:
        page = _open(browser, url, WIDTHS[state])
        before = page.evaluate(SNAP, LANDMARKS)
        _press(page, label)
        _frames(page)
        moved = _moved(before, page.evaluate(SNAP, LANDMARKS))
        if moved:
            failures.append(f"{label!r}: " + "; ".join(moved[:4]))
        # the palette is an overlay over a still layout; close it the way a person does
        page.keyboard.press("Escape")
        assert not page.errors, page.errors
        page.close()
    assert not failures, "\n".join(failures)


@pytest.mark.parametrize("state", list(WIDTHS))
def test_a_pending_edit_moves_nothing_in_the_action_bar(browser, gui, state):
    """The first edit adds the pending count and turns Refine into "Apply and
    refine". Both have reserved widths, so neither pushes a neighbour."""
    url, _ = gui
    page = _open(browser, url, WIDTHS[state])
    value = page.locator(".row input.value").first
    before = page.evaluate(SNAP, LANDMARKS)
    value.click()
    page.keyboard.press("End")
    page.keyboard.type("1")
    _frames(page)
    assert "pending" in page.locator(".actions .pending").text_content()
    assert "Apply and refine" in page.locator(".actions button.refine").text_content()
    moved = _moved(before, page.evaluate(SNAP, LANDMARKS))
    page.locator(".actions button", has_text="Revert").click()
    _frames(page)
    assert not page.errors, page.errors
    page.close()
    assert not moved, moved


#: The pending slot's width against its messages' ink, in the slot's own font:
#: what it shows now, and the longest count it can show, "99 pending edits".
SLOT_ROOM = """() => {
  const slot = document.querySelector(".actions .pending");
  const ctx = document.createElement("canvas").getContext("2d");
  ctx.font = getComputedStyle(slot).font;
  const ink = (text) => ctx.measureText(text).width;
  return {room: slot.clientWidth, shown: slot.textContent.trim(),
          ink: ink(slot.textContent.trim()), longest: ink("99 pending edits"),
          title: slot.getAttribute("title") || ""};
}"""


@pytest.mark.parametrize("state", list(WIDTHS))
def test_an_invalid_edit_is_said_in_full_and_moves_nothing(browser, gui, state):
    """The slot says an edit is invalid in words it has room for, the reason
    rides in its tooltip, and nothing in the shell moves to say either."""
    url, _ = gui
    page = _open(browser, url, WIDTHS[state])
    value = page.locator(".row input.value").first
    before = page.evaluate(SNAP, LANDMARKS)
    value.click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("abc")
    _frames(page)
    slot = page.evaluate(SLOT_ROOM)
    moved = _moved(before, page.evaluate(SNAP, LANDMARKS))
    page.locator(".actions button", has_text="Revert").click()
    _frames(page)
    assert not page.errors, page.errors
    page.close()
    assert slot["shown"] == "invalid edit", slot
    assert "not a number" in slot["title"], slot
    assert slot["ink"] <= slot["room"] and slot["longest"] <= slot["room"], slot
    assert not moved, moved


@pytest.mark.parametrize("state", list(WIDTHS))
def test_a_collapse_button_stays_where_it_was(browser, gui, state):
    """Each side's button sits at its own end of the header, and pressing one
    moves the regions as asked while neither button moves."""
    url, _ = gui
    page = _open(browser, url, WIDTHS[state])
    toggles = "#app > header > button.toggle"
    for index in (0, 1):
        before = page.evaluate(SNAP, [toggles])
        page.locator(toggles).nth(index).click()
        _frames(page)
        assert not _moved(before, page.evaluate(SNAP, [toggles])), index
        page.locator(toggles).nth(index).click()
        _frames(page)
        assert not _moved(before, page.evaluate(SNAP, [toggles])), index
    assert not page.errors, page.errors
    page.close()


@pytest.mark.parametrize("state", list(WIDTHS))
def test_refine_stays_on_screen_with_either_side_hidden(browser, gui, state):
    """The action bar ends the model panel, and goes to the foot of the graphs
    while that panel is hidden, so a fit never needs a hidden button."""
    url, _ = gui
    page = _open(browser, url, WIDTHS[state])
    toggles = page.locator("#app > header > button.toggle")
    refine = page.locator(".actions button.refine")
    seen = []
    for index in (0, 1):
        toggles.nth(index).click()
        _frames(page)
        box = refine.bounding_box() if refine.count() == 1 and refine.is_visible() else None
        seen.append(box is not None and box["y"] + box["height"] <= 900
                    and box["x"] + box["width"] <= WIDTHS[state])
        toggles.nth(index).click()
        _frames(page)
    assert not page.errors, page.errors
    page.close()
    assert seen == [True, True], seen


def test_a_phone_width_window_never_scrolls_sideways(browser, gui):
    """Below the threshold the sides stack, so nothing needs a wider window."""
    url, _ = gui
    page = _open(browser, url, 420)
    assert page.locator(".panes.stacked").count() == 1
    overflow = page.evaluate(
        "document.documentElement.scrollWidth - document.documentElement.clientWidth")
    assert not page.errors, page.errors
    page.close()
    assert overflow <= 0, f"{overflow} px of horizontal scroll at 420 px"


def test_a_refine_moves_nothing_while_it_runs_or_after(browser, tmp_path_factory):
    """Refine starts a run, which changes the pill, the title line and the
    statistics. Each has its place, so the layout holds through the run."""
    httpd, client = _serve(tmp_path_factory, "layout-refine")
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    try:
        page = _open(browser, url, WIDTHS["wide"])
        page.locator(".actions button", has_text="One cycle").click()
        _frames(page)
        before = page.evaluate(SNAP, LANDMARKS)
        page.locator(".actions button.refine").click()
        # The fixture already fitted a stage, so "Last fit" and an idle server
        # are both true before the click. Wait for the console's echo, which
        # the page writes once the server has taken the run, and only then for
        # the run to end, or the test passes without a run having happened.
        page.wait_for_function(
            "document.querySelector('.console')?.textContent"
            ".includes('ref.run_stage(Stage(\"cycle\"')")
        _wait_idle(client)
        page.wait_for_selector('.pill[data-state="idle"]')
        page.wait_for_function("document.querySelector('.gtitle .what').textContent === 'Last fit'")
        _frames(page)
        moved = _moved(before, page.evaluate(SNAP, LANDMARKS))
        assert not page.errors, page.errors
        page.close()
    finally:
        httpd.shutdown()
    assert not moved, moved


#: The Background tab's own controls, beside the shell's landmarks (WP-2129).
BACKGROUND_LANDMARKS = LANDMARKS + [
    "section[aria-label=background] .host", "section[aria-label=background] .knobs",
    "section[aria-label=background] .knobs > *", ".term",
]


def test_the_background_tab_holds_still_under_a_hold_and_a_band_press(
        browser, tmp_path_factory):
    """WP-2129. Holding a term moves the head and refetches the band; pressing
    ×5 redraws it. Neither asks for a layout change, so no landmark moves, the
    tab's own controls included. A project of its own: the hold is written."""
    from pathlib import Path

    httpd, client = _serve(tmp_path_factory, "layout-background")
    url = f"http://127.0.0.1:{httpd.server_address[1]}/"
    try:
        # the fixture's stage freed the scale alone; free the terms, or no band
        status, body = client.patch("/api/params", {"vary": {"instrument.background.*": True}})
        assert status == 200, body
        page = _open(browser, url, WIDTHS["wide"])
        page.locator(".plotcol > nav.tabs button", has_text="Background").click()
        page.wait_for_selector(".term input:not([disabled])")
        page.wait_for_function(
            "document.querySelector('.gtitle .what').textContent === 'Background at the last fit'")
        page.wait_for_selector(".band .segmented button:not([disabled])")
        _frames(page)
        out = Path(__file__).parent / "output"
        out.mkdir(exist_ok=True)
        page.screenshot(path=str(out / "gui_background_tab.png"))
        before = page.evaluate(SNAP, BACKGROUND_LANDMARKS)

        head = client.get("/api/project")[1]["head"]
        page.locator(".term", has_text="c1").locator("input").click()
        page.wait_for_function(
            "document.querySelector('.console')?.textContent"
            ".includes('ref.hold(\"instrument.background.c1\")')")
        page.wait_for_selector(".term input:checked:not([disabled])")
        _frames(page)
        assert client.get("/api/project")[1]["head"] != head
        held = page.evaluate(SNAP, BACKGROUND_LANDMARKS)

        page.locator(".band .segmented button", has_text="×5").click()
        _frames(page)
        page.screenshot(path=str(out / "gui_background_tab_x5.png"))
        pressed = page.evaluate(SNAP, BACKGROUND_LANDMARKS)
        assert not page.errors, page.errors
        page.close()
    finally:
        httpd.shutdown()
    assert not _moved(before, held), _moved(before, held)
    assert not _moved(before, pressed), _moved(before, pressed)
