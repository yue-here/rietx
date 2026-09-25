"""WP-1461: the inks the GUI's pattern panel paints, read in chromium.

jsdom has no canvas, so ``gui/src/App.test.ts`` asserts the chart over a
stand-in that records what each pane was asked to show
(``gui/src/test-uplot.ts``). This file asks the browser instead. An init script
records the style of every stroke and fill on each canvas at the moment it is
made, which is the ink on the canvas rather than the ink a series was handed:
under plotly a tick row declared one colour and painted another (WP-1438). The
script is ``test_watch_browser.py``'s, which reads the watcher's picture the
same way.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing, as its two siblings do. That
includes CI.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from rietx.gui import GuiSession
from tests.test_gui_server import Client, _project, _start, _wait_idle

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

# every stroke and fill on every canvas, with the style it was made in
from tests.test_watch_browser import RECORD, _chromium  # noqa: E402

#: The panel's plot tokens, each normalised the way a canvas normalises a
#: colour it is given, so a token and a recorded style compare as strings.
TOKENS = """() => {
  const ctx = document.createElement("canvas").getContext("2d"), style = getComputedStyle(document.body);
  const out = {};
  for (const name of ["obs", "calc", "bkg", "diff", "zero", "mask", "peak", "peakfit"]) {
    ctx.fillStyle = "#000000";
    ctx.fillStyle = style.getPropertyValue(`--plot-${name}`).trim();
    out[name] = ctx.fillStyle;
  }
  ctx.fillStyle = style.getPropertyValue("--muted").trim();
  out.edge = ctx.fillStyle;
  return out;
}"""

#: What each of the pattern's three panes painted since the record was last
#: cleared, as sets of [op, style, dashed].
PANES = """() => {
  const panes = [...document.querySelectorAll(".plot canvas")].map((c) => window.__canvasId(c));
  return panes.map((id) => window.__ink.filter((m) => m.canvas === id)
    .map((m) => [m.op, m.style, m.dash, m.alpha]));
}"""


@pytest.fixture(scope="module")
def gui(tmp_path_factory):
    """A project fitted over a 3° exclusion, served as ``rietx gui`` serves it."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import synthesize

    data = _write_xye(tmp_path_factory.mktemp("gui-browser-data") / "synth.xye", synthesize())
    project = _project(tmp_path_factory.mktemp("gui-browser") / "sample.rex", data)
    session = GuiSession(project, state_dir=tmp_path_factory.mktemp("gui-browser-state"))
    httpd = _start(session)
    client = Client(httpd.server_address[1])
    assert client.post("/api/project", {"excluded_regions": [[13.0, 16.0]]})[0] == 200
    status, run = client.post("/api/run", {"kind": "stage", "stage": {
        "name": "scale", "turn_on": ["phases.*.scale"], "max_iter": 5}})
    assert status == 200, run
    _wait_idle(client)
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


@pytest.fixture
def page(browser, gui):
    url, _ = gui
    page = browser.new_page(viewport={"width": 1300, "height": 900})
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.add_init_script(RECORD)
    page.goto(url)
    page.wait_for_function("document.querySelectorAll('.plot canvas').length >= 3")
    _frames(page)
    yield page
    page.close()
    assert not errors, errors


def _frames(page, n: int = 3) -> None:
    """Wait ``n`` animation frames, which is when a paint has happened, never a timer."""
    page.evaluate("n => new Promise(r => { const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(); f(n); })", n)


def _has(marks, op, style, *, dash=None, alpha=None) -> bool:
    return any(m[0] == op and m[1] == style and (dash is None or m[2] == dash)
               and (alpha is None or abs(m[3] - alpha) < 1e-6) for m in marks)


def test_each_curve_is_painted_in_its_own_token(page):
    """The observed points, the model, the background, the residual and its zero
    line, the masked channels and the protocol's shading, each in the token the
    theme gives it. A series handed one colour and painted in another is the
    WP-1438 defect, and only the canvas can show it."""
    ink = page.evaluate(TOKENS)
    main, ticks, resid = page.evaluate(PANES)

    # the thinned markers are filled paths, the model and background stroked
    assert _has(main, "fill", ink["obs"], alpha=1)
    assert _has(main, "stroke", ink["calc"], dash=False)
    assert _has(main, "stroke", ink["bkg"], dash=True)
    # the masked channels are the edge's ink, recessive
    assert _has(main, "fill", ink["edge"], alpha=0.45)
    assert _has(resid, "stroke", ink["diff"], dash=False)
    assert _has(resid, "stroke", ink["zero"])
    # one phase takes the observed points' neutral, not the first phase colour
    assert _has(ticks, "stroke", ink["obs"])
    # the exclusion: a wash and its two dotted edges, in every pane
    for pane in (main, ticks, resid):
        assert _has(pane, "fillRect", ink["mask"])
        assert _has(pane, "stroke", ink["edge"], dash=True)


def test_the_pointers_line_is_solid_in_the_pages_ink(page):
    """The line under the pointer carries no quantity, so it is chrome (WP-1213).
    uPlot draws it dashed in #607d8b, which is the dotted edge an excluded region
    leaves, near enough that the pointer drew a protocol boundary."""
    main = page.locator(".plot .u-over").first.bounding_box()
    page.mouse.move(main["x"] + main["width"] / 2, main["y"] + main["height"] / 2)
    _frames(page)
    line = page.evaluate("""() => {
      const probe = document.createElement("i");
      probe.style.color = getComputedStyle(document.body).getPropertyValue("--fg");
      document.body.appendChild(probe);
      const fg = getComputedStyle(probe).color;
      probe.remove();
      return [...document.querySelectorAll(".plot .u-cursor-x")].map((el) => {
        const s = getComputedStyle(el);
        return [s.borderRightStyle, s.borderRightColor === fg, s.display];
      });
    }""")
    # one per pane, all three shown at the pointer by the cursor sync
    assert line == [["solid", True, "block"]] * 3


def test_the_peak_layer_is_painted_on_the_peaks_tab_in_its_own_two_inks(page, gui):
    """The markers and the dashed group profile (WP-1210), which a click on the
    Peaks tab puts on the plot and nothing else does."""
    _, client = gui
    assert client.post("/api/peaks", {})[0] == 200
    page.reload()
    page.wait_for_function("document.querySelectorAll('.plot canvas').length >= 3")
    _frames(page)
    ink = page.evaluate(TOKENS)
    main, _, _ = page.evaluate(PANES)
    assert not _has(main, "fill", ink["peak"])

    page.evaluate("window.__ink.length = 0")
    page.get_by_role("button", name="Peaks", exact=True).click()
    _frames(page)
    main, _, _ = page.evaluate(PANES)
    assert _has(main, "fill", ink["peak"])
    assert _has(main, "stroke", ink["peakfit"], dash=True)


def test_the_pattern_exports_as_drawn_and_fetches_svgcanvas_only_then(page):
    """D6 in the pattern panel. svgcanvas is a chunk of its own, fetched on the
    first SVG and not at boot, and the table copied is the fit's channels in
    view with the residual the panel is drawing."""
    asked: list[str] = []
    page.on("request", lambda r: asked.append(r.url))
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    row = page.get_by_role("group", name="export").first
    assert not [u for u in asked if "svgcanvas" in u]
    with page.expect_download() as download:
        row.get_by_role("button", name="SVG", exact=True).click()
    assert download.value.suggested_filename == "pattern.svg"
    assert [u for u in asked if u.endswith("/assets/vendor-svgcanvas.js")]
    svg = Path(download.value.path()).read_text(encoding="utf-8")
    assert svg.count("<svg") == 4
    row.get_by_role("button", name="copy data").click()
    page.wait_for_function("[...document.querySelectorAll('.exports .said')]"
                           ".some((e) => e.textContent.startsWith('copied'))")
    head = page.evaluate("navigator.clipboard.readText()").split("\n")[0]
    assert head.split("\t")[:3] == ["two_theta", "y_obs", "excluded"]

