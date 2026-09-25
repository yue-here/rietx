"""WP-1461, task 10: the file ``write_html`` writes, opened in chromium from disk.

What is under test is what the other suites cannot see: that the file draws
with nothing but itself, that its inlined script and module share one document
without a clash, and what the page adds over the chart module, which is the
band, the legend and the readout. Asserted from what the browser holds and
drew.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing, as ``tests/test_watch_browser.py``
does.
"""

from __future__ import annotations

from pathlib import Path

import pytest

playwright = pytest.importorskip("playwright")
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_events_viz_history import perturbed_models  # noqa: E402
from tests.test_refine_synthetic import synthesize  # noqa: E402
from tests.test_rxplot_browser import _frames  # noqa: E402
from tests.test_watch_browser import RECORD, _chromium  # noqa: E402


@pytest.fixture(scope="module")
def written(tmp_path_factory):
    """One fit, written both ways."""
    import rietx as rx
    from rietx.viz.html import write_html

    structure, ins = perturbed_models()
    result = rx.Refinement(structure, ins, history=False).fit(synthesize())
    out = tmp_path_factory.mktemp("html")
    files = {}
    for weighted in (False, True):
        files[weighted] = out / f"fit-{'weighted' if weighted else 'raw'}.html"
        write_html(result, str(files[weighted]), weighted=weighted)
    return result, files


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            handle = p.chromium.launch(executable_path=_chromium() or None)
        except Exception as exc:  # noqa: BLE001 - any launch failure is a skip
            pytest.skip(f"no chromium to drive: {exc}")
        yield handle
        handle.close()


@pytest.fixture(params=[False, True], ids=["raw", "weighted"])
def page(request, browser, written):
    _, files = written
    page = browser.new_page(viewport={"width": 1100, "height": 700})
    errors: list[str] = []
    page.asked = []
    page.weighted = request.param
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
    page.on("request", lambda r: page.asked.append(r.url))
    page.add_init_script(RECORD)
    page.goto(files[request.param].as_uri())
    page.wait_for_function("document.getElementById('plot').__rx")
    _frames(page)
    yield page
    page.close()
    assert not errors, errors


def _box(page, key: str) -> dict:
    return page.evaluate("""k => { const b = document.getElementById('plot').__rx.panes[k]
        .over.getBoundingClientRect(); return {x: b.left, y: b.top, w: b.width, h: b.height}; }""", key)


def test_the_file_draws_every_channel_from_itself_alone(page, written):
    """No request but the file's own, and every channel of the fit on one x."""
    result, files = written
    assert page.asked == [files[page.weighted].as_uri()]
    got = page.evaluate("""(() => { const f = document.getElementById('plot').__rx;
        return Object.fromEntries(Object.entries(f.panes).map(([k, u]) => [k, u.data[0].length])); })()""")
    assert got == {"main": len(result.two_theta), "ticks": len(result.two_theta),
                   "resid": len(result.two_theta)}


def test_only_the_weighted_file_draws_the_3_sigma_band(page):
    """The band is Δ/σ's absolute scale, so a raw difference in counts has none."""
    band = page.evaluate("JSON.parse(document.getElementById('spec').textContent).colors.band")
    resid = page.evaluate("""() => { const u = document.getElementById('plot').__rx.panes.resid,
        id = window.__canvasId(u.ctx.canvas);
        return window.__ink.filter(m => m.canvas === id && m.op === 'fillRect').map(m => [m.style, m.alpha]); }""")
    assert ([band, 0.15] in resid) is page.weighted


def test_the_legend_hides_the_curve_it_names_and_brings_it_back(page):
    button = page.locator(".legend button", has_text="calculated")
    shown = "document.getElementById('plot').__rx.panes.main.series[3].show"
    assert page.evaluate(shown) is True
    button.click()
    _frames(page)
    assert page.evaluate(shown) is False
    assert button.get_attribute("aria-pressed") == "false"
    button.click()
    _frames(page)
    assert page.evaluate(shown) is True


def test_the_readout_reads_the_channel_and_names_the_reflection(page, written):
    """Over the curves it reads the channel under the pointer. Over the tick
    band it names the nearest reflection, by its Miller index."""
    result, _ = written
    main = _box(page, "main")
    page.mouse.move(main["x"] + main["w"] / 2, main["y"] + main["h"] / 2)
    _frames(page)
    text = page.text_content("#readout")
    assert text.startswith("2θ ") and ("Δ/σ" if page.weighted else "Δ ") in text

    phase = next(iter(result.ticks))
    at, hkl = result.ticks[phase][3], result.tick_hkl[phase][3]
    x = page.evaluate("x => document.getElementById('plot').__rx.panes.ticks.valToPos(x, 'x')", at)
    band = _box(page, "ticks")
    page.mouse.move(band["x"] + x, band["y"] + band["h"] / 2)
    _frames(page)
    label = "(" + " ".join(str(v).replace("-", "−") for v in hkl) + ")"
    assert page.text_content("#readout") == f"{phase}  {label}  2θ {at:.4f}°"


def test_the_four_exports_work_from_a_file_on_disk(page, written):
    """D6, with no server: svgcanvas is inlined, and each file is named after the page."""
    _, files = written
    stem = files[page.weighted].stem
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    for label, ext in (("PNG", "png"), ("SVG", "svg")):
        with page.expect_download() as download:
            page.get_by_role("button", name=label, exact=True).click()
        assert download.value.suggested_filename == f"{stem}.{ext}"
    svg = Path(download.value.path()).read_text(encoding="utf-8")
    assert svg.startswith("<svg") and svg.count("<svg") == 4
    page.get_by_role("button", name="copy data").click()
    page.wait_for_function("document.getElementById('readout').textContent.startsWith('copied')")
    text = page.evaluate("navigator.clipboard.readText()")
    assert text.split("\n")[0].endswith("delta_over_sigma" if page.weighted else "obs_minus_calc")

