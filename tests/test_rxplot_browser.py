"""WP-1461: the chart module's drawing half, in chromium.

``tests/rxplot_page.html`` loads the vendored uPlot and ``rxplot.mjs`` the way a
page does, and mounts three linked panes on synthetic data. Each case here is a
behaviour the spike found a way to get wrong (the WP's § What the spike found),
asserted from what the browser drew or holds rather than from what was asked.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing. That includes CI, as for
``tests/test_watch_browser.py``, whose chromium lookup this borrows.
"""

from __future__ import annotations

import http.server
import math
import threading
from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_watch_browser import _chromium  # noqa: E402

STATIC = Path(__file__).resolve().parents[1] / "src" / "rietx" / "viz" / "static"
HARNESS = Path(__file__).with_name("rxplot_page.html")

#: What the harness fetches, from where, as what.
FILES = {
    "/index.html": (HARNESS, "text/html; charset=utf-8"),
    "/rxplot.mjs": (STATIC / "rxplot.mjs", "text/javascript; charset=utf-8"),
    "/uPlot.iife.min.js": (STATIC / "uPlot.iife.min.js", "text/javascript; charset=utf-8"),
    "/uPlot.min.css": (STATIC / "uPlot.min.css", "text/css; charset=utf-8"),
    "/svgcanvas.esm.js": (STATIC / "svgcanvas.esm.js", "text/javascript; charset=utf-8"),
}


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        found = FILES.get(self.path)
        if found is None:
            self.send_error(404)
            return
        body = found[0].read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", found[1])
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture(scope="module")
def url():
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}/index.html"
    server.shutdown()


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
def page(browser, url):
    page = browser.new_page(viewport={"width": 900, "height": 600})
    errors: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.goto(url)
    page.wait_for_function("window.ready === true")
    page.evaluate("mount()")
    yield page
    page.close()
    assert not errors, errors


def _frames(page, n: int = 2) -> None:
    """Wait ``n`` animation frames, which is when a paint has happened, never a timer."""
    page.evaluate("n => new Promise(r => { const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(); f(n); })", n)


def _box(page, key: str) -> dict:
    return page.evaluate("k => { const b = G.panes[k].over.getBoundingClientRect();"
                         " return {x: b.left, y: b.top, w: b.width, h: b.height}; }", key)


def _drag(page, key: str, x0: float, y0: float, x1: float, y1: float, *, alt=False) -> None:
    """A drag in pane ``key``, corners as fractions of its plot area."""
    b = _box(page, key)
    if alt:
        page.keyboard.down("Alt")
    page.mouse.move(b["x"] + x0 * b["w"], b["y"] + y0 * b["h"])
    page.mouse.down()
    page.mouse.move(b["x"] + x1 * b["w"], b["y"] + y1 * b["h"], steps=12)
    page.mouse.up()
    if alt:
        page.keyboard.up("Alt")
    _frames(page)


def _x(page, key: str) -> list[float]:
    return page.evaluate("k => [G.panes[k].scales.x.min, G.panes[k].scales.x.max]", key)


def _y(page, key: str) -> list[float]:
    return page.evaluate("k => [G.panes[k].scales.y.min, G.panes[k].scales.y.max]", key)


def test_a_select_drag_reports_once_from_its_own_pane(page):
    """Finding 1. Synced, a drag selected in every pane and the handler ran in each."""
    page.evaluate("G.setMode('select')")
    before = _x(page, "main")
    _drag(page, "main", 0.2, 0.5, 0.4, 0.52)
    _drag(page, "resid", 0.6, 0.5, 0.7, 0.5)
    selects = page.evaluate("G.selects")
    assert [s[2] for s in selects] == ["main", "resid"]
    assert all(lo < hi for lo, hi, _ in selects)
    # a select zooms nothing, and leaves no rectangle behind in any pane
    assert _x(page, "main") == before
    assert page.evaluate("Object.values(G.panes).every(u => u.select.width === 0)")


def test_a_flat_drag_zooms_x_in_every_pane_and_paints_each_once(page):
    """Findings 10 and 12: one x, copied by value, one paint a pane."""
    page.evaluate("mount({main: Array.from(X)})")   # a ramp, so y has to follow x
    _frames(page)
    page.evaluate("paints = {}")
    y_before = _y(page, "main")
    _drag(page, "main", 0.3, 0.5, 0.5, 0.51)
    lo, hi = _x(page, "main")
    assert 5 < lo < hi < 60
    assert _x(page, "ticks") == [lo, hi] and _x(page, "resid") == [lo, hi]
    assert page.evaluate("paints") == {"main": 1, "ticks": 1, "resid": 1}
    # an x-only zoom re-ranges y to the window rather than holding the old range
    assert _y(page, "main") != y_before


def test_a_box_drag_holds_its_y_range_until_a_double_click(page):
    """y-zoom: the pane dragged in, and no other, keeps the range across x zooms."""
    full_x, main_y, resid_y = _x(page, "main"), _y(page, "main"), _y(page, "resid")
    _drag(page, "main", 0.2, 0.2, 0.6, 0.6)
    boxed = _y(page, "main")
    assert boxed != main_y and _y(page, "resid") == resid_y
    b = _box(page, "main")
    page.mouse.move(b["x"] + 0.5 * b["w"], b["y"] + 0.5 * b["h"])
    page.mouse.wheel(0, -200)
    _frames(page)
    assert _x(page, "main") != full_x
    assert _y(page, "main") == boxed
    page.mouse.dblclick(b["x"] + 0.5 * b["w"], b["y"] + 0.5 * b["h"])
    _frames(page)
    assert _x(page, "main") == full_x and _x(page, "resid") == full_x
    assert _y(page, "main") == main_y


def test_the_wheel_zooms_about_the_pointer_and_shift_or_alt_pans(page):
    b = _box(page, "resid")
    page.mouse.move(b["x"] + 0.25 * b["w"], b["y"] + 0.5 * b["h"])
    at = page.evaluate("G.panes.resid.posToVal(G.panes.resid.cursor.left, 'x')")
    page.mouse.wheel(0, -300)
    _frames(page)
    lo, hi = _x(page, "main")
    assert lo < at < hi and hi - lo < 55
    width = hi - lo
    page.keyboard.down("Shift")
    page.mouse.wheel(0, 200)
    page.keyboard.up("Shift")
    _frames(page)
    lo2, hi2 = _x(page, "main")
    assert lo2 > lo and abs((hi2 - lo2) - width) < 1e-9
    _drag(page, "main", 0.6, 0.5, 0.4, 0.5, alt=True)
    lo3, hi3 = _x(page, "resid")
    assert lo3 > lo2 and abs((hi3 - lo3) - width) < 1e-9


def test_the_readout_comes_from_the_pane_under_the_pointer(page):
    b = _box(page, "main")
    for f in (0.2, 0.4, 0.6):
        page.mouse.move(b["x"] + f * b["w"], b["y"] + 0.5 * b["h"])
    _frames(page)
    hits = page.evaluate("G.cursors")
    assert hits and all(h is not None and h["key"] == "main" for h in hits)
    assert hits[-1]["idx"] > hits[0]["idx"]
    page.mouse.move(b["x"] + 0.5 * b["w"], b["y"] - 40)
    _frames(page)
    assert page.evaluate("G.cursors.at(-1)") is None


def test_the_pointers_line_is_solid_in_the_pages_ink_and_follows_it(page):
    """WP-1213's rule, owned by the module since WP-1461's task 10. Each page
    restated it in its own stylesheet until then, and ``rietx compare`` had
    none, so its line was uPlot's dashed grey-blue. A theme switch restyles
    it, since the line reads the token rather than its value."""
    b = _box(page, "main")
    page.mouse.move(b["x"] + 0.5 * b["w"], b["y"] + 0.5 * b["h"])
    _frames(page)
    read = """() => [...document.querySelectorAll('.u-cursor-x')].map((el) => {
        const s = getComputedStyle(el);
        return [s.borderRightStyle, s.borderRightWidth, s.borderRightColor]; })"""
    lines = page.evaluate(read)
    assert lines and all(line == ["solid", "1px", "rgb(27, 27, 27)"] for line in lines), lines
    page.evaluate("document.documentElement.style.setProperty('--fg', '#e6e6e2')")
    assert {line[2] for line in page.evaluate(read)} == {"rgb(230, 230, 226)"}


def test_a_live_update_keeps_the_readers_zoom(page):
    """``setData``: new numbers for a pane, the window the reader chose kept."""
    _drag(page, "main", 0.3, 0.2, 0.6, 0.7)
    window, y = _x(page, "main"), _y(page, "main")
    page.evaluate("G.setData('main', [Array.from(X, x => 100 + 40 * Math.cos(x))])")
    _frames(page)
    assert _x(page, "main") == window and _y(page, "main") == y
    assert page.evaluate("G.panes.main.data[1][0]") == 100 + 40 * math.cos(5)


def _pixel(page, key: str, x: float, y: float) -> list[int]:
    """The RGBA the pane's canvas holds at data point (x, y)."""
    return page.evaluate("""([k, x, y]) => {
        const u = G.panes[k];
        const px = Math.round(u.valToPos(x, 'x', true)), py = Math.round(u.valToPos(y, 'y', true));
        return Array.from(u.ctx.getImageData(px, py, 1, 1).data);
    }""", [key, x, y])


def test_a_theme_switch_repaints_in_the_new_colour(page):
    """Finding 5: colours are functions read at each draw, so one redraw restyles."""
    page.evaluate("mount({main: new Array(X.length).fill(100)})")
    assert _pixel(page, "main", 30, 100) == [0xc2, 0x3b, 0x22, 255]
    page.evaluate("document.documentElement.style.setProperty('--plot-calc', '#1f77b4');"
                  " G.redraw()")
    _frames(page)
    assert _pixel(page, "main", 30, 100) == [0x1f, 0x77, 0xb4, 255]


def test_a_series_on_part_of_the_grid_draws_only_there(page):
    """Finding 10: one x array, and a null is a gap uPlot leaves undrawn."""
    page.evaluate("""mount({main: rx.scatter(X.length,
        Int32Array.from({length: X.length / 2}, (_, i) => X.length / 2 + i),
        new Array(X.length / 2).fill(100))})""")
    assert page.evaluate("G.panes.main.data[1].length === X.length")
    # a grid line may cross the gap, but the series does not
    assert _pixel(page, "main", 15, 100) != [0xc2, 0x3b, 0x22, 255]
    assert _pixel(page, "main", 50, 100) == [0xc2, 0x3b, 0x22, 255]


def _labels(page, key: str) -> list[str]:
    return page.evaluate("k => G.panes[k].axes[1]._values", key)


def test_a_sqrt_axis_prints_several_labels(page):
    """Finding 2, through ``setY``, which rebuilds the pane at the same x."""
    page.evaluate("mount({main: Array.from(X, x => (x - 5) * 200)})")
    _drag(page, "main", 0.2, 0.5, 0.8, 0.51)
    window = _x(page, "main")
    page.evaluate("G.setY('main', 'sqrt')")
    _frames(page)
    assert _x(page, "main") == window
    labels = [s for s in _labels(page, "main") if s]
    assert len(labels) >= 4, labels


def test_a_narrow_range_prints_labels_that_differ(page):
    """Finding 3: a parameter spanning 1e-4 printed one number five times."""
    page.evaluate("mount({main: Array.from(X, x => 10.2510 + 0.0008 * (x - 5) / 55)})")
    labels = [s for s in _labels(page, "main") if s]
    assert len(labels) >= 3 and len(set(labels)) == len(labels), labels


def test_a_resize_shows_in_the_next_frame_with_no_timer(page):
    """The ResizeObserver path: uPlot has no autosize of its own."""
    page.evaluate("document.getElementById('host').style.width = '520px'")
    _frames(page, 2)
    assert page.evaluate("Object.values(G.panes).map(u => u.width)") == [520, 520, 520]
    assert page.evaluate("G.panes.main.ctx.canvas.width") == 520 * page.evaluate("devicePixelRatio")


def test_a_click_that_jitters_zooms_and_selects_nothing(page):
    """A press that moves a pixel or two is a click, as plotly's is below 8 px.

    uPlot's ``uni`` forces a drag under the threshold onto one axis, and the
    other spans the whole plot, so a select check on both sizes let it through
    and a 1 px move zoomed x to a 1 px window.
    """
    x, y = _x(page, "main"), _y(page, "main")
    _drag(page, "main", 0.5, 0.5, 0.502, 0.5)
    _drag(page, "main", 0.5, 0.5, 0.5, 0.505)
    assert _x(page, "main") == x and _y(page, "main") == y
    page.evaluate("G.setMode('select')")
    _drag(page, "main", 0.5, 0.5, 0.502, 0.5)
    assert page.evaluate("G.selects") == []


def test_a_live_update_follows_the_data_where_the_reader_chose_no_y(page):
    """``setData`` with no y zoom re-ranges y, or new numbers draw off the pane."""
    page.evaluate("G.setData('main', [Array.from(X, x => 1000 + 500 * Math.sin(x))])")
    _frames(page)
    lo, hi = _y(page, "main")
    assert lo <= 500 and hi >= 1500


# ------------------------------------------------------------------ the pattern
def _near(page, key: str, x: float, y: float | None = None, r: int = 3) -> list[list[int]]:
    """The RGBA pixels around data point (x, y) on pane ``key``, or down the whole
    plot-area column at ``x`` when ``y`` is None."""
    return page.evaluate("""([k, x, y, r]) => {
        const u = G.panes[k], b = u.bbox, px = Math.round(u.valToPos(x, 'x', true));
        const top = y == null ? b.top : Math.round(u.valToPos(y, 'y', true)) - r;
        const h = y == null ? b.height : 2 * r + 1;
        const img = u.ctx.getImageData(px - r, top, 2 * r + 1, h).data, out = [];
        for (let i = 0; i < img.length; i += 4) out.push(Array.from(img.slice(i, i + 4)));
        return out;
    }""", [key, x, y, r])


def _has(pixels, rgb, alpha=200, tol=40) -> bool:
    return any(p[3] >= alpha and all(abs(p[i] - rgb[i]) <= tol for i in range(3)) for p in pixels)


def test_the_pattern_puts_the_fit_on_its_channels_and_nowhere_else(page):
    """Finding 10 for the whole figure: the model lands by ``fitted`` and is null
    elsewhere, and the observed points split by ``kept``."""
    page.evaluate("mountPattern()")
    _frames(page)
    got = page.evaluate("""(() => { const d = G.panes.main.data, c = curves(), k = c.arrays.kept;
        const at = (i) => [d[1][i], d[2][i], d[3][i]];
        return { inside: at(k[0]), outside: at(0), n: d[0].length }; })()""")
    assert got["n"] == 1100
    obs, masked, calc = got["inside"]
    assert obs is not None and masked is None and calc == obs + 5
    obs, masked, calc = got["outside"]
    assert obs is None and masked is not None and calc is None
    # and nothing of the model is drawn over the masked channels
    assert not _has(_near(page, "main", 50), [255, 0, 0])
    assert _has(_near(page, "main", 25), [255, 0, 0], alpha=100)


def test_a_thinned_column_still_paints_its_highest_and_lowest_point(page):
    """D5: each pixel column paints only its extremes, so a peak top one channel
    wide survives a view of 20 or more channels a pixel, and so does the lowest
    point beside it. Striding would drop both."""
    page.evaluate("""(() => { const c = curves(20000), i = c.arrays.kept[3000];
        c.arrays.y_obs[i] = 400; c.arrays.y_obs[i + 1] = -200;
        window.spike = [c.arrays.two_theta[i], c.arrays.two_theta[i + 1]];
        return mountPattern({hidden: ['calc', 'bkg']}, c); })()""")
    _frames(page)
    top, low = page.evaluate("spike")
    assert page.evaluate("G.panes.main.data[0].length / G.panes.main.bbox.width") > 20
    assert _has(_near(page, "main", top, 400), [0, 0, 0])
    assert _has(_near(page, "main", low, -200), [0, 0, 0])


def test_the_panes_fill_the_host_and_follow_it(page):
    """Panes sized by ``share`` take what the fixed tick band leaves, and a host
    whose height the page changes is filled again in the next frame."""
    page.evaluate("mountPattern()")
    _frames(page)
    heights = page.evaluate("Object.values(G.panes).map(u => u.height)")
    assert heights[1] == page.evaluate("rx.tickHeight(2)")
    assert 488 <= sum(heights) <= 490
    page.evaluate("document.getElementById('host').style.height = '600px'")
    _frames(page, 2)
    assert 598 <= sum(page.evaluate("Object.values(G.panes).map(u => u.height)")) <= 600


def test_a_new_payload_keeps_the_view_only_when_asked(page):
    """``setCurves``: a run landing keeps the reader's window; a new pattern resets."""
    page.evaluate("mountPattern()")
    _frames(page)
    _drag(page, "main", 0.3, 0.5, 0.5, 0.51)
    window = _x(page, "main")
    page.evaluate("G.setCurves(curves(), true)")
    _frames(page)
    assert _x(page, "main") == window == _x(page, "resid")
    page.evaluate("G.setCurves(curves(1100, 3), false)")
    _frames(page)
    assert _x(page, "main") == [8.0, 63.0] == _x(page, "resid")


def test_a_residual_switch_draws_the_new_numbers_and_forgets_its_y(page):
    page.evaluate("mountPattern()")
    _frames(page)
    _drag(page, "resid", 0.3, 0.3, 0.6, 0.6)
    boxed = _y(page, "resid")
    page.evaluate("G.setResidual('delta')")
    _frames(page)
    got = page.evaluate("(() => { const c = curves(), i = c.arrays.kept[3];"
                        " return [G.panes.resid.data[1][i], c.arrays.delta_raw[3]]; })()")
    assert got[0] == got[1]
    assert _y(page, "resid") != boxed
    lo, hi = _y(page, "resid")
    assert lo <= -2.9 and hi >= 2.9


def test_a_log_scale_keeps_the_view_and_hides_curves_by_id(page):
    page.evaluate("mountPattern()")
    _frames(page)
    _drag(page, "main", 0.3, 0.5, 0.5, 0.51)
    window = _x(page, "main")
    page.evaluate("G.setY('log')")
    _frames(page)
    assert _x(page, "main") == window
    assert page.evaluate("G.panes.main.scales.y.distr") == 3
    page.evaluate("G.setHidden(['calc', 'diff'])")
    _frames(page)
    shown = page.evaluate("[G.panes.main.series.map(s => s.show), G.panes.resid.series[1].show]")
    assert shown == [[True, True, True, False, True], False]


def test_a_one_phase_band_gives_its_row_the_room_it_was_sized_for(page):
    """``tickHeight`` sizes the band at 16 px a row over its bare x axis, and
    uPlot's automatic top padding took 17 px of a one-phase band's 22, leaving
    a 5 px row and ticks 2.5 px tall. Found drawing ``rietx compare``; the GUI,
    the watcher and the Series panel drew theirs the same way."""
    page.evaluate("""(() => { const c = curves(); c.header.ticks = { a: [12, 20, 30] };
        return mountPattern({}, c); })()""")
    _frames(page)
    got = page.evaluate("""(() => { const u = G.panes.ticks;
        return [u.bbox.height / devicePixelRatio, rx.tickHeight(1) - 6]; })()""")
    assert got[0] == got[1]


def test_a_line_rings_none_of_its_points_however_far_the_view_zooms(page):
    """uPlot rings each point of a series once its points sit far enough apart,
    which a zoom always reaches, and a ringed calculated curve reads as
    observed points. plotly drew these as lines, and so does the chart."""
    page.evaluate("mountPattern()")
    page.evaluate("G.setX(20, 21)")
    _frames(page)
    rings = page.evaluate("""['main', 'resid'].flatMap((k) => { const u = G.panes[k];
        return u.series.slice(1).map((s, i) => typeof s.points.show === 'function'
            ? s.points.show(u, i + 1) : s.points.show); })""")
    assert rings and not any(rings), rings


def test_each_phase_ticks_in_its_own_row_and_ink(page):
    """Two phases, two rows, two inks; a hidden row draws nothing."""
    page.evaluate("mountPattern()")
    _frames(page)
    rows = page.evaluate("""(() => { const u = G.panes.ticks, b = u.bbox;
        return [b.top + b.height / 4, b.top + 3 * b.height / 4].map(Math.round); })()""")

    def row_has(x, row, rgb):
        pixels = page.evaluate("""([x, y]) => { const u = G.panes.ticks;
            const px = Math.round(u.valToPos(x, 'x', true));
            return Array.from({length: 5}, (_, i) => Array.from(u.ctx.getImageData(px - 2 + i, y, 1, 1).data)); }""",
                               [x, row])
        return _has(pixels, rgb, alpha=100)

    assert row_has(12, rows[0], [0, 0xa0, 0xa0]) and not row_has(12, rows[1], [0xa0, 0, 0xa0])
    assert row_has(15, rows[1], [0xa0, 0, 0xa0])
    page.evaluate("G.setHidden(['ticks:b'])")
    _frames(page)
    assert not row_has(15, rows[1], [0xa0, 0, 0xa0])


def test_a_pages_layers_run_under_the_grid_and_over_the_curves(page):
    page.evaluate("mountPattern()")
    _frames(page)
    page.evaluate("layers.length = 0; G.redraw()")
    _frames(page)
    assert page.evaluate("layers") == ["under", "over"]


def test_a_zoom_rebases_the_cumulative_chi2_to_the_view(page):
    """The window route summed Σχ² over its own window, so a zoom's curve began at
    zero. The payload sums once over every fitted channel, and each x zoom draws
    ``cum − chi2Base``: the curve starts at zero at the view's left edge and ends
    at the view's own χ². A reset draws the whole sum again."""
    page.evaluate("mountPattern({residual: 'cumulative'})")
    _frames(page)
    assert page.evaluate("G.chi2Base()") == 0
    _drag(page, "main", 0.3, 0.5, 0.5, 0.51)
    got = page.evaluate("""(() => { const a = curves().arrays, lo = G.panes.resid.scales.x.min;
        const fitTT = Array.from(a.fitted, (i) => a.two_theta[i]);
        const q = rx.lower(fitTT, lo), i = a.fitted[q];
        return { base: G.chi2Base(), before: a.cumulative_chi2[q - 1],
                 drawn: G.panes.resid.data[1][i], sum: a.cumulative_chi2[q] }; })()""")
    assert got["base"] == got["before"] > 0
    assert got["drawn"] == got["sum"] - got["base"]
    # the y range follows the re-based numbers, not the pattern's whole sum
    lo, hi = _y(page, "resid")
    assert lo < got["drawn"] < hi < got["base"]
    b = _box(page, "main")
    page.mouse.dblclick(b["x"] + b["w"] / 2, b["y"] + b["h"] / 2)
    _frames(page)
    assert page.evaluate("G.chi2Base()") == 0
    assert page.evaluate("(() => { const a = curves().arrays, i = a.fitted[5];"
                         " return G.panes.resid.data[1][i] === a.cumulative_chi2[5]; })()")


def test_a_payload_without_a_fit_draws_the_residual_the_page_supplies(page):
    """The raw view has no model, so the GUI draws its peak groups' own residual in
    the lower pane. ``rawResidual`` is read at each data build, and
    ``refreshResidual`` takes new numbers without touching the reader's y."""
    page.evaluate("""(() => { const a = curves().arrays;
        window.raw = { header: { fit: false, weighted: true },
                       arrays: { two_theta: a.two_theta, y_obs: a.y_obs, kept: a.kept } };
        window.strip = new Array(a.two_theta.length).fill(null);
        for (let i = 400; i < 500; i++) strip[i] = 3 * Math.sin(i / 10);
        return mountPattern({ rawResidual: () => strip }, raw); })()""")
    _frames(page)
    assert page.evaluate("G.panes.resid.data[1][450] === strip[450]"
                         " && G.panes.resid.data[1][10] === null")
    x = page.evaluate("G.panes.resid.data[0][450]")
    assert _has(_near(page, "resid", x), [255, 0, 255], alpha=100)
    page.evaluate("strip = strip.map((v) => (v == null ? null : v + 1)); G.refreshResidual()")
    _frames(page)
    assert page.evaluate("G.panes.resid.data[1][450] === strip[450]")


def test_diff_hides_the_fits_residual_and_never_the_pages(page):
    """``hidden: ['diff']`` is the fit's residual switched off. A page's own
    residual has its own toggle, so a reader who hid Δ/σ and then checked out
    to a state with no fit still sees the peak groups' strip, and a fit landing
    after that hides it again."""
    page.evaluate("""(() => { const a = curves().arrays;
        window.raw = { header: { fit: false, weighted: true },
                       arrays: { two_theta: a.two_theta, y_obs: a.y_obs, kept: a.kept } };
        window.strip = new Array(a.two_theta.length).fill(null);
        strip[450] = 1;
        return mountPattern({ hidden: ['diff'], rawResidual: () => strip }, raw); })()""")
    _frames(page)
    assert page.evaluate("G.panes.resid.series[1].show") is True
    page.evaluate("G.setCurves(curves(), true)")
    _frames(page)
    assert page.evaluate("G.panes.resid.series[1].show") is False
    page.evaluate("G.setCurves(raw, true)")
    _frames(page)
    assert page.evaluate("G.panes.resid.series[1].show") is True


# ---------------------------------------------------------------- the trajectory
TONE, WARN = [0, 0, 255], [255, 128, 0]

#: A probe this many CSS px above a point clears its 3 px dot and its ring,
#: and lands inside a 0.01 whisker, which is ~17 px each way on this loop.
ABOVE = 11


def _above(page, x: float, v: float, px: int = ABOVE) -> list[list[int]]:
    """The pixels ``px`` CSS px above the point (x, v) on the trajectory pane."""
    dy = page.evaluate("([v, px]) => { const u = G.panes.traj;"
                       " return u.posToVal(u.valToPos(v, 'y') - px, 'y'); }", [v, px])
    return _near(page, "traj", x, dy, r=1)


def test_a_trajectory_comes_back_along_its_own_x_in_chain_order(page):
    """D8: a heat-then-cool series is joined in the order it was refined, never
    in x order. Sorted by x, the two points at 300 would be joined by a vertical
    stroke that the chain never makes."""
    page.evaluate("mountTrajectory()")
    _frames(page)
    # up, then back down along the same x
    assert _has(_near(page, "traj", 375, 1.15, r=2), TONE)
    assert _has(_near(page, "traj", 375, 1.175, r=2), TONE)
    # and never the x-sorted join between the first and the last point
    assert not _has(_near(page, "traj", 300.4, 1.025, r=1), TONE, alpha=100)


def test_a_point_with_no_esd_has_no_whisker(page):
    """A zero-length whisker would claim the value was measured exactly, so a
    point the fit gave no esd has none at all, while its neighbour at the same
    x has one."""
    page.evaluate("mountTrajectory({ rings: [], crosses: [] })")
    _frames(page)
    assert _has(_above(page, 350, 1.15), TONE)        # point 3, esd 0.01
    assert not _has(_above(page, 350, 1.1), TONE, alpha=60)   # point 1, none


def test_a_reseeded_point_is_ringed_and_an_unrecovered_one_crossed(page):
    """Both stay in the chain, in the warning ink: a gap reads as data nobody
    collected. 7 px straight above a point is the ring's top edge, and above
    where the cross's 2.2 px arms end (6 px, measured), so it is inked by the
    ring alone."""
    page.evaluate("mountTrajectory({ hidden: ['esd'] })")
    _frames(page)
    ring = _above(page, 350, 1.1, px=7)
    cross = _above(page, 350, 1.15, px=7)
    assert _has(ring, WARN) and not _has(cross, WARN, alpha=60)
    # the cross's arm, on the diagonal
    diag = page.evaluate("""() => { const u = G.panes.traj, X = u.valToPos(350, 'x', true),
        Y = u.valToPos(1.15, 'y', true), d = Math.round(3.5 * devicePixelRatio);
        return Array.from(u.ctx.getImageData(Math.round(X) + d - 1, Math.round(Y) + d - 1, 3, 3).data); }""")
    assert any(abs(diag[i] - 255) < 40 and abs(diag[i + 1] - 128) < 40 and diag[i + 3] > 150
               for i in range(0, len(diag), 4)), diag
    # and hiding them hides them
    page.evaluate("G.setHidden(['esd', 'rings', 'crosses'])")
    _frames(page)
    assert not _has(_above(page, 350, 1.1, px=7), WARN, alpha=60)


def test_the_pointer_names_the_point_nearest_in_the_plane(page):
    """Two points share x = 350, one per leg of the loop, so a lookup by x alone
    (`nearest`) could name the wrong one. The trajectory's is by distance in the
    plane (`nearestXY`)."""
    page.evaluate("mountTrajectory()")
    _frames(page)
    b = _box(page, "traj")
    for v, want in ((1.1, 1), (1.15, 3)):
        at = page.evaluate("([x, v]) => { const u = G.panes.traj;"
                           " return [u.valToPos(x, 'x'), u.valToPos(v, 'y')]; }", [350, v])
        page.mouse.move(b["x"] + at[0], b["y"] + at[1] + 2)
        _frames(page)
        assert page.evaluate("G.points.at(-1)") == {"i": want, "chain": "forward"}
    # and far from every point, nothing
    page.mouse.move(b["x"] + 5, b["y"] + b["h"] - 5)
    _frames(page)
    assert page.evaluate("G.points.at(-1)") is None


def test_a_trajectory_zooms_like_every_other_chart(page):
    """The gestures are the pane group's: the wheel narrows x, and y follows
    the points still in view, whiskers included."""
    page.evaluate("mountTrajectory()")
    _frames(page)
    before = _y(page, "traj")
    b = _box(page, "traj")
    page.mouse.move(b["x"] + 0.05 * b["w"], b["y"] + b["h"] / 2)
    page.mouse.wheel(0, -400)
    _frames(page)
    lo, hi = _x(page, "traj")
    assert 300 <= lo < hi < 400
    assert _y(page, "traj")[1] < before[1], "y did not follow the view"


# ---------------------------------------------------------------- the overlay
def test_the_overlay_takes_its_delta_chi2_by_subtraction_against_the_reference(page):
    """D8 for `rietx compare`: every fit shares one x, so the Δχ² pane is each
    fit's cumulative χ² less the reference's, channel for channel, where the
    plotly page interpolated. The reference draws flat at zero, and a new
    reference is new numbers for that pane alone."""
    page.evaluate("mountOverlay()")
    _frames(page)
    got = page.evaluate("""(() => { const f = fits(), d = G.panes.cum.data, n = f.x.length - 1;
        return { ends: [1, 2, 3].map((s) => d[s][n]), cums: f.fits.map((x) => x.cum[n]) }; })()""")
    a, b, c = got["cums"]
    assert got["ends"] == [0, b - a, c - a]
    page.evaluate("G.setReference('c')")
    _frames(page)
    assert page.evaluate("G.panes.cum.data.slice(1).map((s) => s[s.length - 1])") == [a - c, b - c, 0]
    # a reference with no fit here draws nothing rather than another fit's Δχ²
    page.evaluate("G.setReference('pending')")
    _frames(page)
    assert page.evaluate("G.panes.cum.data.slice(1).every((s) => s.every((v) => v === null))")


def test_the_overlay_hides_a_fit_in_every_pane(page):
    page.evaluate("mountOverlay()")
    _frames(page)
    assert _has(_near(page, "diff", 20), [0, 0, 255], alpha=100)
    page.evaluate("G.setHidden(['b'])")
    _frames(page)
    shown = page.evaluate("""['cum', 'diff', 'fit'].map((k) =>
        G.panes[k].series.slice(k === 'fit' ? 2 : 1).map((s) => s.show))""")
    assert shown == [[True, False, True]] * 3
    assert not _has(_near(page, "diff", 20), [0, 0, 255], alpha=100)
    # the observed points are not a fit, and stay
    assert page.evaluate("G.panes.fit.series[1].show")


def test_the_overlay_zooms_every_pane_and_its_band_carries_the_ticks(page):
    """One x for the three panes and the band, whichever pane the drag starts
    in, and the band's rows in their phases' inks at the tick positions."""
    page.evaluate("mountOverlay()")
    _frames(page)
    _drag(page, "diff", 0.25, 0.5, 0.75, 0.5)
    ranges = [_x(page, k) for k in ("cum", "diff", "fit", "ticks")]
    assert all(r == ranges[0] for r in ranges) and ranges[0][1] - ranges[0][0] < 30
    page.evaluate("G.reset()")
    _frames(page)
    rows = page.evaluate("""(() => { const b = G.panes.ticks.bbox;
        return [b.top + b.height / 4, b.top + 3 * b.height / 4].map(Math.round); })()""")
    pixels = page.evaluate("""([x, y]) => { const u = G.panes.ticks;
        const px = Math.round(u.valToPos(x, 'x', true));
        return Array.from({length: 5}, (_, i) => Array.from(u.ctx.getImageData(px - 2 + i, y, 1, 1).data)); }""",
                           [20, rows[0]])
    assert _has(pixels, [0, 0xa0, 0xa0], alpha=100)


# ------------------------------------------------------------------ exports (D6)
#: The SVG export of `G`, read back: each nested pane's place and paths, the
#: text drawn in each, the inks, and whether the two globals it swaps are back.
SVG = """async () => {
  const text = await G.svg(() => import('/svgcanvas.esm.js'));
  const doc = new DOMParser().parseFromString(text, 'image/svg+xml');
  const root = doc.documentElement, panes = [...root.children].filter((e) => e.tagName === 'svg');
  return { errors: doc.querySelectorAll('parsererror').length,
           height: +root.getAttribute('height'), ground: root.querySelector('rect').getAttribute('fill'),
           panes: panes.map((e) => [+e.getAttribute('y'), +e.getAttribute('height'),
                                    e.querySelectorAll('path').length]),
           texts: panes.map((e) => [...e.querySelectorAll('text')].map((s) => s.textContent)),
           strokes: [...new Set([...root.querySelectorAll('path')].map((e) => e.getAttribute('stroke')))],
           native: String(Path2D).includes('native code')
             && String(HTMLCanvasElement.prototype.getContext).includes('native code') };
}"""


def test_the_panes_export_as_one_png_and_one_svg_of_the_view(page):
    """D6. The PNG stacks the panes' canvases over the ground, at the device's
    resolution. The SVG redraws each pane once through svgcanvas, as vectors,
    at the reader's zoom, and puts ``Path2D`` and ``getContext`` back
    (finding 6). The live figure is untouched by either."""
    page.evaluate("mountPattern()")
    page.evaluate("G.setX(20, 30)")
    _frames(page)
    png = page.evaluate("""async () => { const b = await createImageBitmap(await G.png());
        const us = Object.values(G.panes);
        return [b.width, b.height, us[0].ctx.canvas.width,
                us.reduce((s, u) => s + u.ctx.canvas.height, 0)]; }""")
    assert png[0] == png[2] and png[1] == png[3]
    got = page.evaluate(SVG)
    assert got["errors"] == 0 and got["native"]
    heights = page.evaluate("Object.values(G.panes).map((u) => u.height)")
    assert [h for _, h, _ in got["panes"]] == heights
    assert [y for y, _, _ in got["panes"]] == [sum(heights[:i]) for i in range(len(heights))]
    assert got["height"] == sum(heights) and all(n > 0 for _, _, n in got["panes"])
    # the view the reader chose, not the whole pattern: 20-30 labelled, 5 not
    resid = got["texts"][-1]
    assert "2θ (°)" in resid and "25" in resid and "5" not in resid
    # the calculated curve in its own ink, over the page's ground
    assert "#ff0000" in got["strokes"]
    assert got["ground"] == page.evaluate("getComputedStyle(document.body).backgroundColor")
    # the live figure kept its view and still moves
    assert _x(page, "main") == [20, 30]
    page.evaluate("G.setX(10, 40)")
    _frames(page)
    assert _x(page, "main") == [10, 40]


def test_a_y_range_the_reader_chose_is_the_one_the_svg_draws(page):
    """An export chart takes the live pane's y range, so a box zoom exports as seen."""
    page.evaluate("mountPattern()")
    _drag(page, "main", 0.3, 0.2, 0.6, 0.7)
    live = page.evaluate("G.panes.main.axes[1]._values.filter(Boolean)")
    got = page.evaluate(SVG)
    assert live and set(live) <= set(got["texts"][0])


def test_each_figure_tabulates_what_is_in_view(page):
    """``tsv``: every channel in view with each curve as drawn, a gap empty."""
    page.evaluate("mountPattern()")
    page.evaluate("G.setX(8, 12)")
    lines = page.evaluate("G.tsv()").split("\n")
    assert lines[0].split("\t") == ["two_theta", "y_obs", "excluded", "y_calc", "y_background",
                                     "delta_over_sigma"]
    rows = [line.split("\t") for line in lines[1:]]
    xs = page.evaluate("Array.from(curves().arrays.two_theta).filter((x) => x >= 8 && x <= 12)")
    assert [float(r[0]) for r in rows] == xs
    # the fit kept 10-40°: under 10 a channel is excluded and has no model
    below = [r for r in rows if float(r[0]) < 10]
    assert below and all(r[2] == "1" and r[3] == "" and r[5] == "" for r in below)
    above = [r for r in rows if float(r[0]) >= 10]
    assert above and all(r[2] == "0" and r[3] != "" for r in above)

    page.evaluate("mountOverlay({hidden: ['b']})")
    page.evaluate("G.setX(20, 21)")
    lines = page.evaluate("G.tsv()").split("\n")
    assert lines[0].split("\t") == ["two_theta", "y_obs", "a:y_calc", "a:delta_over_sigma",
                                     "a:delta_chi2", "c:y_calc", "c:delta_over_sigma", "c:delta_chi2"]
    # the reference's Δχ² is zero against itself
    assert {line.split("\t")[4] for line in lines[1:]} == {"0"}

    page.evaluate("mountTrajectory()")
    lines = page.evaluate("G.tsv()").split("\n")
    # the chain in its own order, and the esd a fit did not give left empty
    assert lines == ["pattern\tx\tvalue\tesd", "0\t300\t1\t0.01", "1\t350\t1.1\t",
                     "2\t400\t1.2\t0.01", "3\t350\t1.15\t0.01", "4\t300\t1.05\t0.01"]

