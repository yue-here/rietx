"""WP-1461: the ``rietx compare`` page in chromium, on the chart module.

The server is ``test_compare_ui``'s, with its refinements stubbed, so what is
under test is the page: that it fetches each variant's curves once rather than
on every poll, draws them over one x, hides a variant it is told to, and names
what the pointer is over. Asserted from what the browser holds and drew.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing, as ``tests/test_watch_browser.py``
does.
"""

from __future__ import annotations

import pytest

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_compare_ui import N_FAKE, _fake_record, server  # noqa: E402, F401
from tests.test_rxplot_browser import _frames, _has  # noqa: E402
from tests.test_watch_browser import _chromium  # noqa: E402


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
def page(browser, server, tmp_path, monkeypatch):  # noqa: F811 - the imported fixture
    # the page is stamped with the stored theme, so a test must not read this
    # machine's (and a probe must never write it)
    from rietx._about import STATE_DIR_ENV

    monkeypatch.setenv(STATE_DIR_ENV, str(tmp_path))
    base, _ = server
    page = browser.new_page(viewport={"width": 1200, "height": 900})
    errors: list[str] = []
    page.asked = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("request", lambda r: page.asked.append(r.url.removeprefix(base)))
    page.goto(base + "/")
    page.wait_for_function("document.querySelectorAll('#variants input').length > 0")
    yield page
    page.close()
    assert not errors, errors


def _tick(page, variants: list[str]) -> None:
    """Tick exactly ``variants``, each change announced as a click would be."""
    page.evaluate("""(keys) => { for (const el of document.querySelectorAll('#variants input')) {
        const want = keys.includes(el.value);
        if (el.checked !== want) { el.checked = want; el.dispatchEvent(new Event('change')); } } }""",
                  variants)


def _centre(page, key: str, x: float | None = None) -> list[float]:
    """Pane ``key`` scrolled into view, and a point in it: its middle, or ``x`` at half height."""
    return page.evaluate("""([key, x]) => { const u = document.getElementById('figure').__rx.panes[key];
        u.over.scrollIntoView({block: 'center'});
        const b = u.over.getBoundingClientRect();
        return [b.left + (x === null ? b.width / 2 : u.valToPos(x, 'x')), b.top + b.height / 2]; }""",
                         [key, x])


def _run(page, variants: list[str]) -> None:
    """Tick exactly ``variants``, press Run, and wait for every one to be drawn."""
    _tick(page, variants)
    page.click("#run")
    page.wait_for_function("""(n) => { const f = document.getElementById('figure').__rx;
        return !document.getElementById('run').disabled && f && f.panes.diff.series.length === n + 1; }""",
                           arg=len(variants))
    _frames(page)


def test_the_page_draws_every_variant_over_one_x_and_fetches_its_curves_once(page):
    """D4: the poll carries statistics, and each variant's curves come once."""
    _run(page, ["baseline", "extinction"])
    asked, standard = page.asked, page.input_value("#standard")
    assert [u for u in asked if u.startswith("/api/curves")] == [
        f"/api/curves?standard={standard}&variant=baseline",
        f"/api/curves?standard={standard}&variant=extinction"]
    assert not [u for u in asked if "plotly" in u]
    got = page.evaluate("""(() => { const f = document.getElementById('figure').__rx;
        return { n: f.panes.fit.data[0].length, same: ['cum', 'diff', 'ticks'].every(
                   (k) => f.panes[k].data[0] === f.panes.fit.data[0]),
                 heads: [...document.querySelectorAll('#figure > div:not(.tip)')].map((d) => d.id || 'pane') }; })()""")
    assert got["n"] == N_FAKE and got["same"]
    # each heading stands in front of the pane it explains
    assert got["heads"] == ["head-cum", "pane", "head-diff", "pane", "head-fit", "pane", "pane"]
    # a second run of the same pairs is cached on both sides: nothing refetched
    before = len([u for u in page.asked if u.startswith("/api/curves")])
    page.click("#run")
    page.wait_for_function("!document.getElementById('run').disabled")
    assert len([u for u in page.asked if u.startswith("/api/curves")]) == before


def test_unticking_a_variant_hides_it_and_keeps_the_zoom(page):
    """The variant list is the legend: unticking hides the variant in every
    pane at once, and the figure is not rebuilt, so the reader's zoom holds."""
    _run(page, ["baseline", "extinction"])
    page.evaluate("document.getElementById('figure').__rx.setX(20, 30)")
    page.uncheck("#variants input[value=extinction]")
    _frames(page)
    got = page.evaluate("""(() => { const f = document.getElementById('figure').__rx;
        return { x: [f.panes.diff.scales.x.min, f.panes.diff.scales.x.max],
                 shown: f.panes.diff.series.slice(1).map((s) => s.show) }; })()""")
    assert got["x"] == [20, 30]
    assert got["shown"] == [True, False]


def test_the_reference_is_what_the_delta_chi2_subtracts(page):
    _run(page, ["baseline", "extinction"])
    want = _fake_record("corundum", "extinction").cumulative_chi2[-1] \
        - _fake_record("corundum", "baseline").cumulative_chi2[-1]
    ends = page.evaluate("""document.getElementById('figure').__rx.panes.cum.data
        .slice(1).map((s) => s[s.length - 1])""")
    assert ends == pytest.approx([0.0, want], abs=1e-12)
    page.select_option("#reference", "extinction")
    _frames(page)
    ends = page.evaluate("""document.getElementById('figure').__rx.panes.cum.data
        .slice(1).map((s) => s[s.length - 1])""")
    assert ends == pytest.approx([-want, 0.0], abs=1e-12)


def test_the_pointer_reads_each_variant_and_names_a_reflection(page):
    """What plotly's hover box said, as a line over the figure: each drawn
    variant's value in the pane under the pointer, and in the tick band the
    reflection's phase, Miller index and 2θ (WP-1438)."""
    _run(page, ["baseline", "extinction"])
    page.mouse.move(*_centre(page, "diff"))
    _frames(page)
    text = page.inner_text("#readout")
    assert text.startswith("2θ ") and "Baseline" in text and "+ secondary extinction" in text, text
    page.mouse.move(*_centre(page, "ticks", 35.5))
    _frames(page)
    assert page.is_visible("#tip")
    assert page.inner_text("#tip").split("\n") == ["corundum", "(1 0 4)", "35.5000°"]


def test_a_failed_variant_is_a_row_not_a_broken_page(page):
    """A failed fit's statistics poll as ``null`` (``RunRecord.summary``), so
    the page reads them, shows the error on the variant's row, and draws the
    variants that fitted."""
    page.evaluate("""(() => { const box = document.getElementById('variants'),
        lab = document.createElement('label');
        lab.innerHTML = '<input type="checkbox" value="fails" checked>';
        box.appendChild(lab); })()""")
    _tick(page, ["baseline", "fails"])
    page.click("#run")
    page.wait_for_function("!document.getElementById('run').disabled")
    _frames(page)
    assert "RuntimeError: x < y & worse" in page.inner_text("#stats")
    assert page.evaluate("document.getElementById('figure').__rx.panes.diff.series.length") == 2
    # and what is drawn is the fit, in its own ink
    pixels = page.evaluate("""(() => { const u = document.getElementById('figure').__rx.panes.fit,
        b = u.bbox, out = [], img = u.ctx.getImageData(b.left, b.top, b.width, b.height).data;
        for (let i = 0; i < img.length; i += 4 * 97) out.push(Array.from(img.slice(i, i + 4)));
        return out; })()""")
    assert _has(pixels, [0x1f, 0x5f, 0xa8], alpha=100)


def test_the_figure_exports_what_is_drawn(page):
    """D6. Before a run there is nothing to export and the page says so. After
    one, the SVG loads svgcanvas from the page's own server, and the file is
    named after the standard."""
    page.click("#exports button:text-is('SVG')")
    page.wait_for_function("document.getElementById('export-said').textContent !== ''")
    assert page.text_content("#export-said") == "SVG failed: nothing is drawn yet"
    _run(page, ["baseline", "extinction"])
    with page.expect_download() as download:
        page.click("#exports button:text-is('SVG')")
    assert download.value.suggested_filename == f"compare-{page.input_value('#standard')}.svg"
    assert "/svgcanvas.esm.js" in page.asked
    svg = download.value.path().read_text(encoding="utf-8")
    # the three panes and the tick band, inside the one document
    assert svg.count("<svg") == 5

