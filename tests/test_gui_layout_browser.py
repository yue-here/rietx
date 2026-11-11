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
    _keep_no_edits(page)
    page.goto(url)
    page.wait_for_selector(".actions button.refine")
    page.evaluate("document.fonts.ready")
    _frames(page)
    return page


def _keep_no_edits(page) -> None:
    """Answer the recovery route in the page, so no test inherits another's pending edit.

    A fixture here serves one session to many tests, and a test that leaves an
    edit pending leaves a recovery copy (WP-2209). The next page would offer it
    in a modal dialog over every control. Clearing the copy before each page
    races the closing page's own last write, so the route never reaches the
    server. Recovery is tested in ``tests/test_gui_recovery_browser.py``.
    """
    page.route("**/api/recovery", lambda route: route.fulfill(
        status=200, content_type="application/json", body='{"draft": null}'))


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
    value = page.locator(".params .row button.ink").first
    before = page.evaluate(SNAP, LANDMARKS)
    value.click()
    page.keyboard.press("End")
    page.keyboard.type("1")
    page.keyboard.press("Enter")
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
    value = page.locator(".params .row button.ink").first
    before = page.evaluate(SNAP, LANDMARKS)
    value.click()
    page.keyboard.press("ControlOrMeta+a")
    page.keyboard.type("abc")
    page.keyboard.press("Enter")
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


#: The Parameters panel's own pieces (WP-2126). A press on a box, a number or a
#: padlock changes what a row shows and never where any row is.
PANEL_LANDMARKS = [
    ".params > header", ".params .band", ".params .head", ".params .row",
    ".params .fold", ".params .atomtab tr", ".params .ink", ".params .slot",
]

#: Each panel landmark's box in the scroller's content coordinates, so that
#: the scroll a click into view makes is not read as a move.
PANEL_SNAP = """(selectors) => {
  const pane = document.querySelector(".params .scroller");
  const origin = pane.getBoundingClientRect();
  const out = {};
  selectors.forEach((sel) => {
    [...document.querySelectorAll(sel)].forEach((e, i) => {
      if (!e.getClientRects().length) return;
      const r = e.getBoundingClientRect();
      const inside = pane.contains(e);
      const x = inside ? r.x - origin.x + pane.scrollLeft : r.x;
      const y = inside ? r.y - origin.y + pane.scrollTop : r.y;
      out[`${sel} #${i}`] = [x, y, r.width, r.height];
    });
  });
  return out;
}"""

#: The panel's controls. A band, a group heading and a fold line open and
#: close what is under them, so they ask for a move; the rest may not make one.
PANEL_CONTROLS = {
    "box": ".params input[type=checkbox]",
    "number": ".params button.ink",
    "padlock": ".params button.lock",
}
PANEL_DISCLOSURES = {
    "band": ".params .band button.bt",
    "group": ".params .head button.ht",
    "fold": ".params button.fold",
}


@pytest.mark.parametrize("state", list(WIDTHS))
def test_no_parameters_control_moves_the_layout(browser, gui, state):
    """The prototype's layout-shift check, ported: every box, number and
    padlock in the Parameters panel is pressed once, with a real click on a
    fresh page, and no landmark of the shell or the panel may move. A
    disclosure moves what is under it, by request, so only the shell and the
    control itself are held still for it."""
    url, _ = gui
    page = _open(browser, url, WIDTHS[state])
    counts = {name: page.locator(sel).count()
              for name, sel in {**PANEL_CONTROLS, **PANEL_DISCLOSURES}.items()}
    page.close()
    assert counts["box"] >= 5 and counts["number"] >= 5 and counts["group"] >= 3, counts

    failures = []
    for kind, selector in {**PANEL_CONTROLS, **PANEL_DISCLOSURES}.items():
        asked = kind in PANEL_DISCLOSURES
        for i in range(counts[kind]):
            page = _open(browser, url, WIDTHS[state])
            control = page.locator(selector).nth(i)
            if not control.is_visible() or not control.is_enabled():
                page.close()
                continue
            control.scroll_into_view_if_needed()
            _frames(page)
            shell = page.evaluate(SNAP, LANDMARKS)
            panel = page.evaluate(PANEL_SNAP, [f"{selector}"] if asked else PANEL_LANDMARKS)
            control.click()
            _frames(page)
            moved = _moved(shell, page.evaluate(SNAP, LANDMARKS))
            panel_after = page.evaluate(PANEL_SNAP, [f"{selector}"] if asked else PANEL_LANDMARKS)
            moved += _moved({k: v for k, v in panel.items() if not asked or k == f"{selector} #{i}"},
                            panel_after)
            if moved:
                failures.append(f"{kind} {i}: " + "; ".join(moved[:4]))
            # a number's press opens the editor, which floats; close it the
            # way a person does, and the closing may not move anything either
            if kind == "number":
                page.keyboard.press("Escape")
                _frames(page)
                again = _moved(panel, page.evaluate(PANEL_SNAP, PANEL_LANDMARKS))
                if again:
                    failures.append(f"{kind} {i} closed: " + "; ".join(again[:4]))
            assert not page.errors, page.errors
            page.close()
    assert not failures, "\n".join(failures)


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
        page.locator(".plotcol > nav.tabs").get_by_role("button", name="Background", exact=True).click()
        page.wait_for_selector(".term input:not([disabled])")
        page.wait_for_function(
            "document.querySelector('.gtitle .what').textContent === 'Background at the current values'")
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


#: The Interactive tab's own rows (WP-2128): a drag or a typed value changes a
#: number and a thumb, and never where a row sits.
SLIDER_ROWS = [".side .panel:not(.hidden) .slider", ".side .panel:not(.hidden) .slider .line > *"]

#: Every `rx-preview-redraw` entry's duration, in ms: from the moment a slider's
#: values were set to the second frame after the preview was drawn.
REDRAWS = """() => performance.getEntriesByName("rx-preview-redraw").map((e) => e.duration)"""


def _drag(page, track, frac_from: float, frac_to: float, steps: int = 24) -> None:
    """A real pointer drag along a range input, from one track fraction to another."""
    box = track.bounding_box()
    # the thumb's centre runs from 8 px to 8 px short of the box's ends
    x = lambda f: box["x"] + 8 + (box["width"] - 16) * f  # noqa: E731
    y = box["y"] + box["height"] / 2
    page.mouse.move(x(frac_from), y)
    page.mouse.down()
    for k in range(1, steps + 1):
        page.mouse.move(x(frac_from + (frac_to - frac_from) * k / steps), y)
        _frames(page, 1)
    page.mouse.up()


@pytest.mark.parametrize("state", list(WIDTHS))
def test_a_slider_drag_previews_and_moves_nothing(browser, gui, state):
    """WP-2128: a drag, a typed value, the range pop-up and a peak window's step
    each change what is drawn and never where anything sits. The drag is a real
    pointer drag, so its redraws are what a person would wait for, and their
    latencies are printed as a range."""
    url, _ = gui
    page = _open(browser, url, WIDTHS[state])
    _press(page, "Interactive")
    page.wait_for_selector(".side .panel:not(.hidden) .slider")
    _frames(page)
    marks = LANDMARKS + SLIDER_ROWS
    before = page.evaluate(SNAP, marks)
    failures = []

    track = page.locator('.side .panel:not(.hidden) input[type="range"]').first
    value = int(track.input_value()) / 1000
    _drag(page, track, value, min(1.0, value + 0.3))
    page.wait_for_function(
        "document.querySelector('.gtitle .what').textContent === 'Preview, not refined'")
    _frames(page)
    failures += [f"drag: {m}" for m in _moved(before, page.evaluate(SNAP, marks))]
    assert "pending" in page.locator(".actions .pending").text_content()

    # a typed value: the number is a button, and typing opens over it. The
    # first row's, because a click on a row out of view scrolls the panel, and
    # a scroll moves every row without moving the layout
    page.locator(".side .panel:not(.hidden) button.num").first.click()
    page.wait_for_selector(".side .panel:not(.hidden) input.typed")
    page.wait_for_function("document.activeElement?.classList.contains('typed')")
    # ArrowRight to the end of the selected text. End is a scroll key in a mac
    # text field, and it scrolled the panel 47 px with the caret unmoved
    page.keyboard.press("ArrowRight")
    page.keyboard.type("1")
    page.keyboard.press("Enter")
    _frames(page)
    failures += [f"typed: {m}" for m in _moved(before, page.evaluate(SNAP, marks))]

    # the range pop-up from the parameter's name, closed the way a person does
    page.locator(".side .panel:not(.hidden) button.pname").first.click()
    page.wait_for_selector(".rangepop")
    _frames(page)
    failures += [f"pop-up: {m}" for m in _moved(before, page.evaluate(SNAP, marks))]
    page.keyboard.press("Escape")

    # the Single peaks graph, stepped once while the preview is drawn
    _press(page, "Single peaks")
    page.wait_for_selector(".peakwins canvas")
    page.locator('.peakwins button[aria-label="Next peak"]').first.click()
    _frames(page)
    failures += [f"single peaks: {m}" for m in _moved(before, page.evaluate(SNAP, LANDMARKS))]

    redraws = page.evaluate(REDRAWS)
    page.locator(".actions button", has_text="Revert").click()
    page.wait_for_function("document.querySelector('.gtitle .what').textContent === 'Last fit'")
    assert not page.errors, page.errors
    page.close()
    assert redraws, "no preview was drawn"
    # a runaway guard on one redraw, never a timer: the route answers in tens
    # of ms on this synthetic pattern
    assert max(redraws) < 5000, redraws
    print(f"\n[{state}] {len(redraws)} preview redraws, drag to redraw "
          f"{min(redraws):.0f}-{max(redraws):.0f} ms")
    assert not failures, "\n".join(failures)


# ---------------------------------------------------------------------------
# WP-2127: the Plan tab
# ---------------------------------------------------------------------------

#: The plan bar and every stage row, beside the shell's landmarks.
PLAN_BAR = ["section[aria-label=plan] > header", "section[aria-label=plan] > header > *"]
PLAN_LANDMARKS = LANDMARKS + PLAN_BAR + ["section[aria-label=plan] li.stage"]

#: The Plan tab's controls, each with a label the failure can name and whether
#: pressing it asks for the layout to change. Adding or removing a stage or a
#: glob, opening a stage's path list and opening its fix row (`+ Fix`, WP-2208)
#: ask; the rest move nothing. A stage's
#: run button starts a fit, which the shell's refine test already covers.
PLAN_CONTROLS = """() => {
  const plan = document.querySelector("section[aria-label=plan]");
  const out = [];
  plan.querySelectorAll("button, [data-handle], summary, input, select").forEach((e, i) => {
    if (!e.getClientRects().length || e.disabled) return;
    const text = (e.getAttribute("aria-label") || e.textContent || e.tagName).trim();
    if (text === "Run this stage") return;
    const asks = e.tagName === "SUMMARY" || text === "+ Stage" || text === "+ Fix"
      || /^Remove /.test(text);
    out.push({index: i, text, asks});
  });
  return out;
}"""

#: Mark one control so a locator can find it, after scrolling it clear of the
#: sticky plan bar: the click itself is playwright's, a real one.
PLAN_MARK = """(index) => {
  const plan = document.querySelector("section[aria-label=plan]");
  const e = plan.querySelectorAll("button, [data-handle], summary, input, select")[index];
  e.scrollIntoView({block: "center"});
  e.setAttribute("data-press", "1");
  return null;
}"""


def _open_plan(browser, url: str, width: int):
    page = _open(browser, url, width)
    page.locator(".side > nav.tabs").get_by_role("button", name="Plan", exact=True).click()
    page.wait_for_selector("section[aria-label=plan] li.stage .rung summary")
    _frames(page)
    return page


@pytest.mark.parametrize("state", list(WIDTHS))
def test_no_plan_control_moves_the_layout_unless_it_asks(browser, gui, state):
    """Every Plan control clicked with a real mouse on a fresh page. None may
    move the shell or the plan bar; one that does not ask for a change may not
    move a stage row either."""
    url, _ = gui
    page = _open_plan(browser, url, WIDTHS[state])
    controls = page.evaluate(PLAN_CONTROLS)
    page.close()
    assert len(controls) > 10, controls

    failures = []
    for control in controls:
        page = _open_plan(browser, url, WIDTHS[state])
        page.evaluate(PLAN_MARK, control["index"])
        # Hovering first lets playwright scroll the control clear of the sticky
        # plan bar, as it does before a click, so the boxes are read after any
        # scroll the harness makes and before anything the page does. Stacked,
        # the panel shows little more than one stage, and that scroll measured
        # 20-24 px.
        target = page.locator("[data-press]")
        target.hover()
        _frames(page)
        watched = LANDMARKS + PLAN_BAR if control["asks"] else PLAN_LANDMARKS
        before = page.evaluate(SNAP, watched)
        target.click()
        _frames(page)
        moved = _moved(before, page.evaluate(SNAP, watched))
        if moved:
            failures.append(f"{control['text']!r}: " + "; ".join(moved[:4]))
        page.keyboard.press("Escape")
        assert not page.errors, page.errors
        page.close()
    assert not failures, "\n".join(failures)


def _names(page) -> list[str]:
    return page.locator("section[aria-label=plan] li.stage input.name").evaluate_all(
        "els => els.map(e => e.value)")


def test_a_drag_on_the_handle_reorders_the_stages(browser, gui):
    """A real pointer drag on the three-line handle lifts a stage and drops it
    where its centre crossed; the edit is one pending edit in the action bar,
    and the bar's Revert puts the plan back. A press with no drag moves nothing."""
    url, _ = gui
    page = _open_plan(browser, url, WIDTHS["wide"])
    names = _names(page)
    assert len(names) >= 3, names

    box = page.locator('[data-handle="2"]').bounding_box()
    x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
    before = page.evaluate(SNAP, PLAN_LANDMARKS)
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.up()
    _frames(page)
    assert _names(page) == names
    assert not _moved(before, page.evaluate(SNAP, PLAN_LANDMARKS))

    top = page.locator('[data-handle="0"]').bounding_box()
    page.mouse.move(x, y)
    page.mouse.down()
    page.mouse.move(x, top["y"] - 12, steps=8)
    page.mouse.up()
    _frames(page)
    assert _names(page) == [names[2], names[0], names[1], *names[3:]]
    assert page.locator(".actions .pending").text_content() == "1 pending edit"

    # the arrow keys move the focused handle, and ⌘Z takes the move back
    page.locator('[data-handle="0"]').focus()
    page.keyboard.press("ArrowDown")
    _frames(page)
    assert _names(page)[:2] == [names[0], names[2]]
    page.keyboard.press("ControlOrMeta+z")
    _frames(page)
    assert _names(page)[:3] == [names[2], names[0], names[1]]

    page.locator(".actions button", has_text="Revert").click()
    _frames(page)
    assert _names(page) == names
    assert page.locator(".actions .pending").text_content() == ""
    assert not page.errors, page.errors
    page.close()


@pytest.mark.parametrize("state", list(WIDTHS))
def test_a_plan_edit_moves_nothing(browser, gui, state):
    """Typing a stage's name is an edit: the bar counts it and turns Refine into
    "Apply and refine" in reserved slots, and no row or landmark moves."""
    url, _ = gui
    page = _open_plan(browser, url, WIDTHS[state])
    name = page.locator("section[aria-label=plan] li.stage input.name").first
    # the click is the sweep's question; this one is about the typing after it
    name.click()
    _frames(page)
    before = page.evaluate(SNAP, PLAN_LANDMARKS)
    # no End key: on macOS it scrolls the scroller rather than moving the caret
    page.keyboard.type("x")
    _frames(page)
    assert page.locator(".actions .pending").text_content() == "1 pending edit"
    assert "Apply and refine" in page.locator(".actions button.refine").text_content()
    moved = _moved(before, page.evaluate(SNAP, PLAN_LANDMARKS))
    page.locator(".actions button", has_text="Revert").click()
    _frames(page)
    assert not page.errors, page.errors
    page.close()
    assert not moved, moved


def test_a_fix_typed_into_a_stage_lands_in_its_own_row(browser, gui):
    """WP-2208: `+ Fix` opens a stage's fix row with the cursor in its field;
    a glob typed there and entered becomes a chip in that row, the frees row
    keeps its chips, the edit is one pending edit, and nothing above the stage
    moves."""
    url, _ = gui
    page = _open_plan(browser, url, WIDTHS["wide"])
    stage = page.locator("section[aria-label=plan] li.stage").nth(1)
    frees = stage.locator(".frees:not(.fixing) .chip").all_text_contents()
    assert stage.locator(".fixing").count() == 0
    above = ["section[aria-label=plan] li.stage:first-child", *LANDMARKS, *PLAN_BAR]
    before = page.evaluate(SNAP, above)
    stage.get_by_role("button", name="+ Fix", exact=True).click()
    _frames(page)
    assert page.evaluate("document.activeElement.matches('input.add.fix')")
    page.keyboard.type("instrument.zero_shift")
    page.keyboard.press("Enter")
    _frames(page)
    assert stage.locator(".fixing .chip").all_text_contents() == ["instrument.zero_shift"]
    assert stage.locator(".frees:not(.fixing) .chip").all_text_contents() == frees
    assert page.locator(".actions .pending").text_content() == "1 pending edit"
    moved = _moved(before, page.evaluate(SNAP, above))
    page.locator(".actions button", has_text="Revert").click()
    _frames(page)
    assert stage.locator(".fixing").count() == 0
    assert not page.errors, page.errors
    page.close()
    assert not moved, moved


# -- WP-2131: the start screen and the New project dialog ---------------------

#: The start screen's own landmarks: its two columns, their headings and rows.
START_LANDMARKS = [".start .left > *", ".start .right h2", ".start li", ".start .row"]

#: The dialog's rows and their label column.
DIALOG_LANDMARKS = ['[role="dialog"]', ".nrow", ".nlabel"]

#: Each instrument-form label's ink, its column's width, and the gap from the
#: ink to its control.
LABEL_ROOM = """() => [...document.querySelectorAll(".iform .fld")]
  .filter((f) => f.getClientRects().length)
  .map((f) => {
    const label = f.firstElementChild, control = f.lastElementChild;
    const range = document.createRange();
    range.selectNodeContents(label);
    const ink = range.getBoundingClientRect();
    return {label: label.textContent.trim(), room: label.getBoundingClientRect().width,
            ink: ink.width, gap: control.getBoundingClientRect().left - ink.right};
  })"""


@pytest.fixture(scope="module")
def start(tmp_path_factory):
    """A session with no project whose recent list holds one, and a pattern file."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize

    data = _write_xye(tmp_path_factory.mktemp("start-data") / "synth.xye", synthesize())
    project = _project(tmp_path_factory.mktemp("start") / "sample.rex", data)
    state = tmp_path_factory.mktemp("start-state")
    # one session opens it, which is what writes the recent list
    first = _start(GuiSession(state_dir=state))
    try:
        status, _ = Client(first.server_address[1]).post(
            "/api/project/open", {"path": str(project.path)})
        assert status == 200
    finally:
        first.shutdown()
    httpd = _start(GuiSession(state_dir=state))
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/", data
    finally:
        httpd.shutdown()


def _open_start(browser, url: str, width: int):
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    page.goto(url)
    page.wait_for_selector(".start .row")
    page.evaluate("document.fonts.ready")
    _frames(page)
    return page


@pytest.mark.parametrize("state", list(WIDTHS))
def test_the_start_screen_holds_still_under_its_menus(browser, start, state):
    """A row's ⋯ appears on hover and opens a menu over the list, so neither
    the hover nor the menu moves a row (WP-2131)."""
    url, _ = start
    page = _open_start(browser, url, WIDTHS[state])
    assert page.locator(".start h2").all_text_contents() == ["Recent", "Examples"]
    before = page.evaluate(SNAP, START_LANDMARKS)
    row = page.locator(".start li").first
    row.hover()
    _frames(page)
    row.locator("button.more").click()
    _frames(page)
    items = row.locator('[role="menuitem"]').all_text_contents()
    moved = _moved(before, page.evaluate(SNAP, START_LANDMARKS))
    page.keyboard.press("Escape")
    _frames(page)
    closed = row.locator('[role="menu"]').count() == 0
    assert not page.errors, page.errors
    page.close()
    assert items == ["Open", "Remove from list"], items
    assert closed
    assert not moved, moved


def test_the_new_project_dialog_holds_still_and_its_labels_fit(browser, start):
    """The dialog's rows stay put as its menu opens, and each instrument-form
    label has room beside its control (round 9's Wavelength fix: a 6.5em
    label column)."""
    url, data = start
    page = _open_start(browser, url, WIDTHS["wide"])
    page.get_by_role("button", name="New project…").click()
    page.wait_for_selector('[role="dialog"]')
    _frames(page)
    page.locator('.slot input[type="file"]').set_input_files(str(data))
    page.wait_for_selector(".spark path")
    _frames(page)
    before = page.evaluate(SNAP, DIALOG_LANDMARKS)
    page.get_by_role("button", name="Add phase").click()
    _frames(page)
    items = page.locator('[role="menuitem"]').count()
    moved = _moved(before, page.evaluate(SNAP, DIALOG_LANDMARKS))
    page.keyboard.press("Escape")
    _frames(page)
    still_open = page.locator('[role="dialog"]').count() == 1   # Escape closed the menu only

    page.get_by_role("button", name="Change…").click()
    _frames(page)
    page.locator(".iform select").first.select_option("debye_scherrer")
    _frames(page)
    rows = page.evaluate(LABEL_ROOM)
    assert not page.errors, page.errors
    page.close()
    assert items == 2 and still_open
    assert not moved, moved
    assert {"Geometry", "wavelength (Å)", "radius (mm)"} <= {r["label"] for r in rows}, rows
    for r in rows:
        assert r["ink"] <= r["room"] + 0.5 and r["gap"] > 0, r


def test_the_start_screen_and_dialog_never_scroll_sideways(browser, start):
    """At phone width the start screen stacks its columns and the dialog takes
    the window less its gutter, so neither needs a wider window."""
    url, _ = start
    page = _open_start(browser, url, 420)
    overflow = "document.documentElement.scrollWidth - document.documentElement.clientWidth"
    on_start = page.evaluate(overflow)
    page.get_by_role("button", name="New project…").click()
    page.wait_for_selector('[role="dialog"]')
    _frames(page)
    on_dialog = page.evaluate(overflow)
    width = page.locator('[role="dialog"]').bounding_box()["width"]
    assert not page.errors, page.errors
    page.close()
    assert on_start <= 0 and on_dialog <= 0, (on_start, on_dialog)
    assert width <= 420 - 32 + 1, width


@pytest.fixture
def filemenu(tmp_path_factory):
    """A project of its own, since this test renames its folder."""
    httpd, client = _serve(tmp_path_factory, "filemenu")
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/", client
    finally:
        httpd.shutdown()


@pytest.mark.parametrize("state", list(WIDTHS))
def test_the_file_menu_moves_nothing(browser, filemenu, state):
    """The File menu on the project name (WP-2133): the menu, both submenus,
    the Save a copy dialog and the rename box are overlays, so walking through
    them with the mouse moves no landmark, and a rename lands in place."""
    url, client = filemenu
    page = _open(browser, url, WIDTHS[state])
    before = page.evaluate(SNAP, LANDMARKS)
    moved: dict[str, list[str]] = {}

    def look(step: str) -> None:
        _frames(page)
        hit = _moved(before, page.evaluate(SNAP, LANDMARKS))
        if hit:
            moved[step] = hit[:4]

    name = page.locator("header .fm-name")
    name.click()
    look("open the menu")
    menu = page.locator(".fm-menu").first
    labels = menu.locator("button.item .label").all_text_contents()
    menu.get_by_role("menuitem", name="Open recent").hover()
    look("hover Open recent")
    menu.get_by_role("menuitem", name="Export").hover()
    look("hover Export")
    kinds = page.locator(".fm-sub button.item .label").all_text_contents()
    menu.get_by_role("menuitem", name="Save a copy…").click()
    page.wait_for_selector('[aria-labelledby="fm-title"]')
    look("Save a copy dialog")
    fields = page.locator('[aria-labelledby="fm-title"] input').evaluate_all(
        "els => els.map((e) => e.value)")
    page.locator('[aria-labelledby="fm-title"]').get_by_role("button", name="Cancel").click()
    look("cancel the dialog")

    name.click()
    page.locator(".fm-menu").get_by_role("menuitem", name="Rename…").click()
    box = page.locator("header input.fm-rename")
    box.wait_for()
    look("rename box")
    box.fill("sample2")
    box.press("Enter")
    page.wait_for_selector("header .fm-name:text('sample2')")
    look("renamed")
    status, doc = client.get("/api/project")
    assert not page.errors, page.errors
    page.close()

    assert labels == ["New project…", "Open…", "Open recent", "Save a copy…", "Rename…",
                      "Move to…", "Export", "Close project"], labels
    assert len(kinds) == 6, kinds
    assert fields[0] == "sample copy", fields
    assert status == 200 and doc["path"].endswith("sample2.rex"), doc
    assert not moved, moved


#: The rebuilt page's frame (WP-2215): its bars, its two columns and their tab
#: strips. A pane's own content is not here: a later piece fills it.
NEXT_LANDMARKS = [
    "header.topbar", "header.topbar > *", "section.graphs", "section.graphs > .tabs",
    "section.model", "section.model > .tabs", "footer.statusbar", "footer.statusbar > *",
]


def _open_next(browser, url: str, width: int):
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    # /next mounts Parameters and its recovery offer (WP-2216), so a copy another
    # test left would hold every click behind the offer's backdrop
    _keep_no_edits(page)
    page.goto(url + "next")
    page.wait_for_selector("section.graphs .tabs button")
    page.evaluate("document.fonts.ready")
    _frames(page)
    return page


def test_no_frame_control_moves_the_rebuilt_layout(browser, gui):
    """Every tab, menu and dialog of the rebuilt frame, pressed with a real click (WP-2215).

    Choosing a workflow that is not built yet swaps the model panel's tab strip for its
    steps, so it is pressed too: the strip must keep its height. The workflow
    button is as wide as the workflow's name, as the prototype's is, so a new
    workflow moves the project name beside it and only the bars are held there.
    """
    url, _ = gui
    failures = []

    def pressing(label, act, close=None, landmarks=NEXT_LANDMARKS):
        page = _open_next(browser, url, 1300)
        before = page.evaluate(SNAP, landmarks)
        act(page)
        _frames(page)
        moved = _moved(before, page.evaluate(SNAP, landmarks))
        if moved:
            failures.append(f"{label!r}: " + "; ".join(moved[:4]))
        if close:
            close(page)
        assert not page.errors, page.errors
        page.close()

    page = _open_next(browser, url, 1300)
    tabs = page.locator("section .tabs button").all_text_contents()
    page.close()
    assert len(tabs) == 8, tabs
    for name in tabs:
        pressing(name, lambda p, n=name: p.locator("section .tabs button", has_text=n).first.click())

    def escape(p):
        p.keyboard.press("Escape")

    def series(p):
        p.locator("button.mbtn.wf").click()
        p.get_by_role("menuitemradio", name="Series · not built yet").click()

    pressing("workflow menu", lambda p: p.locator("button.mbtn.wf").click(), escape)
    pressing("File menu", lambda p: p.locator("header .fm-name").click(), escape)
    pressing("Settings", lambda p: p.get_by_role("button", name="Settings", exact=True).click(),
             escape)
    pressing("Series workflow", series, landmarks=[
        s for s in NEXT_LANDMARKS if s != "header.topbar > *"] + [
        "header.topbar > button.ib"])
    assert not failures, "\n".join(failures)


def test_a_frame_toggle_stays_where_it_was(browser, gui):
    """A collapse toggle asks for a move, and is itself never moved by it (WP-2215)."""
    url, _ = gui
    page = _open_next(browser, url, 1300)
    toggles = {"graphs": "header.topbar > button.ib >> nth=0",
               "model": "header.topbar > button.ib >> nth=-1",
               "console": "footer.statusbar > button.console"}
    boxes = {k: page.locator(sel).bounding_box() for k, sel in toggles.items()}
    moved = []
    for press in ("graphs", "graphs", "model", "model", "console", "console"):
        page.locator(toggles[press]).click()
        _frames(page)
        for k, sel in toggles.items():
            box = page.locator(sel).bounding_box()
            if any(abs(box[c] - boxes[k][c]) > 1 for c in ("x", "y", "width", "height")):
                moved.append(f"{k} after pressing {press}: {box} from {boxes[k]}")
    assert not page.errors, page.errors
    page.close()
    assert not moved, moved


#: The refinement window's own places (WP-2216): the graph's title line and its
#: controls, the plot, the legend gutter, the action bar and the status bar.
WINDOW_LANDMARKS = NEXT_LANDMARKS + [
    ".ghead", ".gctl", ".gctl > *", ".plot", ".plot .host", ".gutter",
    ".actions", ".actions .segmented", ".actions .go > *", "footer.statusbar .right",
]


def _open_window(browser, url: str):
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    page.errors = []
    page.on("pageerror", lambda exc: page.errors.append(str(exc)))
    _keep_no_edits(page)
    page.goto(url + "next")
    page.wait_for_selector(".gutter .gut")
    page.evaluate("document.fonts.ready")
    _frames(page)
    return page


def _regions(client) -> list:
    return client.get("/api/project")[1]["doc"].get("excluded_regions") or []


def test_no_pattern_control_moves_the_refinement_window(browser, gui):
    """The view menu, a legend label and each axis's menu and choices, each
    pressed with a real click, move no place in the window (WP-2216)."""
    url, _ = gui
    page = _open_window(browser, url)
    before = page.evaluate(SNAP, WINDOW_LANDMARKS)
    failures = []

    def check(label):
        _frames(page)
        moved = _moved(before, page.evaluate(SNAP, WINDOW_LANDMARKS))
        if moved:
            failures.append(f"{label!r}: " + "; ".join(moved[:4]))

    page.get_by_role("button", name="View", exact=True).click()
    check("view menu")
    page.keyboard.press("Escape")
    background = page.locator(".gutter .gut", has_text="Background")
    background.click()
    check("a legend label")
    assert background.get_attribute("aria-pressed") == "false"
    background.click()
    for axis, choices in (("Intensity scale", ("Linear", "Log", "Square root")),
                          ("Difference axis", ("Difference in counts (Δ)", "Cumulative χ²",
                                               "Difference in esd (Δ/σ)"))):
        page.get_by_role("button", name=axis, exact=True).click()
        check(f"{axis} menu")
        page.keyboard.press("Escape")
        _frames(page)
        assert not page.locator(".rx-menu").count(), f"Esc left the {axis} menu open"
        for choice in choices:
            page.get_by_role("button", name=axis, exact=True).click()
            page.get_by_role("menuitemradio", name=choice, exact=True).click()
            check(choice)
    assert not page.errors, page.errors
    page.close()
    assert not failures, "\n".join(failures)


def test_a_region_is_drawn_selected_and_deleted_in_place(browser, gui):
    """An excluded region is an object on the plot (WP-2216): armed from the
    context menu, dragged, selected with a click, deleted with a key. The
    selection bar floats over the plot, so the window does not move."""
    url, client = gui
    page = _open_window(browser, url)
    before = page.evaluate(SNAP, WINDOW_LANDMARKS)
    box = page.locator(".plot .host .u-over").first.bounding_box()
    page.mouse.click(box["x"] + box["width"] * 0.5, box["y"] + 40, button="right")
    page.get_by_role("menuitem", name="Exclude a region…").click()
    x0, x1 = box["x"] + box["width"] * 0.70, box["x"] + box["width"] * 0.76
    y = box["y"] + box["height"] * 0.5
    page.mouse.move(x0, y)
    page.mouse.down()
    for k in range(1, 13):
        page.mouse.move(x0 + (x1 - x0) * k / 12, y)
    page.mouse.up()
    for _ in range(60):
        if _regions(client):
            break
        _frames(page)
    assert len(_regions(client)) == 1, _regions(client)
    # the page learns of the region from the verb's answer, a moment after
    # the server holds it, so the select click is repeated until it lands
    for _ in range(20):
        page.mouse.click((x0 + x1) / 2, y)
        _frames(page)
        if page.locator(".selbar").count():
            break
    assert "channels" in page.locator(".selbar").inner_text()
    moved = _moved(before, page.evaluate(SNAP, WINDOW_LANDMARKS))
    page.keyboard.press("Delete")
    for _ in range(60):
        if not _regions(client):
            break
        _frames(page)
    assert not page.errors, page.errors
    page.close()
    assert _regions(client) == []
    assert not moved, moved


def test_the_hover_readout_takes_the_status_bar_and_gives_it_back(browser, gui):
    """The status bar's right half reads the pointer while it is over the plot
    and the findings count at rest (Yue's ruling, WP-2216), moving nothing."""
    url, _ = gui
    page = _open_window(browser, url)
    right = page.locator("footer.statusbar .right")
    rest = right.inner_text().strip()
    assert rest.endswith(("finding", "findings")), rest
    before = page.evaluate(SNAP, WINDOW_LANDMARKS)
    box = page.locator(".plot .host .u-over").first.bounding_box()
    page.mouse.move(box["x"] + box["width"] * 0.4, box["y"] + box["height"] * 0.5)
    _frames(page)
    reading = right.inner_text()
    # the legend's words, as ruled on 2026-11-11 ("try b")
    assert "°" in reading and "Observed" in reading and "Last fit" in reading, reading
    moved = _moved(before, page.evaluate(SNAP, WINDOW_LANDMARKS))
    page.mouse.move(box["x"] + box["width"] * 0.4, 5)
    _frames(page)
    assert right.inner_text().strip() == rest
    assert not page.errors, page.errors
    page.close()
    assert not moved, moved


def test_a_pending_edit_moves_nothing_in_the_rebuilt_action_bar(browser, gui):
    """The first Parameters edit fills the pending slot and renames Refine,
    both reserved, so nothing moves (WP-2216, today's rule on the new bar)."""
    url, _ = gui
    page = _open_window(browser, url)
    page.locator("section.model .tabs button", has_text="Parameters").first.click()
    _frames(page)
    before = page.evaluate(SNAP, WINDOW_LANDMARKS)
    page.locator(".params .row button.ink").first.click()
    page.keyboard.press("End")
    page.keyboard.type("1")
    page.keyboard.press("Enter")
    _frames(page)
    assert "pending" in page.locator(".actions .pending").text_content()
    assert "Apply and refine" in page.locator(".actions button.refine").text_content()
    moved = _moved(before, page.evaluate(SNAP, WINDOW_LANDMARKS))
    page.locator(".actions button", has_text="Revert").click()
    _frames(page)
    assert not page.errors, page.errors
    page.close()
    assert not moved, moved


def test_the_structural_menus_and_axis_hints_move_nothing(browser, gui):
    """The filter row's ⋯, a phase band's ⋯, an atom row's context menu and a
    hover on the σ hint each float over the window (WP-2216, ruling 1 on
    #1529 and the axis ruling of 2026-11-11): nothing moves, and Esc closes
    each menu."""
    url, _ = gui
    page = _open_window(browser, url)
    page.locator("section.model .tabs button", has_text="Parameters").first.click()
    page.wait_for_selector("tr[data-atom]")
    _frames(page)
    before = page.evaluate(SNAP, WINDOW_LANDMARKS)
    failures = []

    def check(label):
        _frames(page)
        moved = _moved(before, page.evaluate(SNAP, WINDOW_LANDMARKS))
        if moved:
            failures.append(f"{label!r}: " + "; ".join(moved[:4]))

    def closes(label):
        page.keyboard.press("Escape")
        _frames(page)
        if page.locator(".rx-menu").count():
            failures.append(f"Esc left the {label} open")

    def items():
        return [i.strip() for i in page.locator(".rx-menu [role^=menuitem]").all_text_contents()]

    page.get_by_role("button", name="Free or fix", exact=True).click()
    assert [i.split()[0] for i in items()] == ["Free", "Fix"], items()
    check("filter menu")
    closes("filter menu")
    page.locator(".band button.ib").first.click()
    assert items() == ["Rename…", "Change space group…", "Add atom…", "Replace from CIF…"], items()
    check("phase menu")
    closes("phase menu")
    page.locator("tr[data-atom]").first.click(button="right")
    assert items() == ["Rename…", "Change species…", "Anisotropic ADPs", "Delete"], items()
    check("atom menu")
    closes("atom menu")
    page.get_by_role("button", name="Difference axis", exact=True).hover()
    page.wait_for_selector("#axis-tip")
    assert "σ from the file." in page.locator("#axis-tip").inner_text()
    check("σ hint hover")
    assert not page.errors, page.errors
    page.close()
    assert not failures, "\n".join(failures)
