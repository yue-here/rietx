"""WP-1462: the structure viewer's WebGL2 renderer, read in chromium.

jsdom has no WebGL, so ``gui/src/App.test.ts`` asserts the viewer over a
stand-in that records each scene and view (``gui/src/test-gl3d.ts``). This file
asks the browser what it painted, by comparing pictures and counting inks —
never by hashing a screenshot, since a WebGL re-render may differ by a pixel.

Driven through playwright, which is not a dependency, so the module skips where
the package or a cached chromium is missing, as its siblings do. That includes
CI. Headless chromium draws with SwiftShader, a CPU rasteriser.
"""

from __future__ import annotations

import io
from pathlib import Path

import numpy as np
import pytest

import rietx as rx
from rietx.crystallography.cif import structure_from_cif
from rietx.gui import GuiSession
from tests.test_gui_server import _start

playwright = pytest.importorskip("playwright")
imread = pytest.importorskip("matplotlib.image").imread
from playwright.sync_api import sync_playwright  # noqa: E402

from tests.test_watch_browser import _chromium  # noqa: E402

DATA = Path(__file__).parent / "data"

#: the project and the browser are module fixtures every test here shares
pytestmark = pytest.mark.xdist_group("structure3d-browser")


@pytest.fixture(scope="module")
def gui(tmp_path_factory):
    """NAC with the file's anisotropic tensors, over any pattern: the viewer
    draws the model and never reads the data."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    data = _write_xye(tmp_path_factory.mktemp("viewer-data") / "synth.xye", synthesize())
    _, instrument = perturbed_models()
    structure = structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)
    project = rx.Project.create(tmp_path_factory.mktemp("viewer") / "nac.rex",
                                pattern=data, instrument=instrument,
                                structure=structure, plan="mccusker_default")
    session = GuiSession(project, state_dir=tmp_path_factory.mktemp("viewer-state"))
    httpd = _start(session)
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
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
    page = browser.new_page(viewport={"width": 1400, "height": 900}, accept_downloads=True)
    errors: list[str] = []
    asked: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("request", lambda r: asked.append(r.url))
    page.goto(gui)
    page.get_by_role("button", name="Model", exact=True).click()
    page.wait_for_selector(".viewer canvas")
    _settle(page)
    page.asked = asked
    yield page
    page.close()
    assert not errors, errors


def _settle(page, frames: int = 4) -> None:
    """Wait a few animation frames, which is when a paint has happened."""
    page.evaluate("n => new Promise(r => { const f = k => k ? requestAnimationFrame(() => f(k - 1)) : r(); f(n); })",
                  frames)


def _centre(page) -> tuple[float, float]:
    """The canvas's centre in the viewport, scrolled into view first: in a
    narrow window the model pane stacks and the viewer sits below the fold,
    where a screenshot still finds it and the mouse does not."""
    canvas = page.locator(".viewer canvas")
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    return box["x"] + box["width"] / 2, box["y"] + box["height"] / 2


def _picture(page) -> np.ndarray:
    """The canvas as the page shows it, RGB floats in 0..1."""
    png = page.locator(".viewer canvas").screenshot()
    return np.asarray(imread(io.BytesIO(png)), dtype=float)[..., :3]


def _drawn(picture: np.ndarray) -> float:
    """The fraction of the canvas that is not its background (the corner pixel)."""
    return float((np.abs(picture - picture[0, 0]).sum(axis=2) > 0.06).mean())


def _dark_green(picture: np.ndarray) -> int:
    """Pixels in the ring ink a fluorine wears: green-dominant and dark."""
    r, g, b = picture[..., 0], picture[..., 1], picture[..., 2]
    return int(((g < 0.30) & (g > 1.6 * r) & (g > 1.6 * b)).sum())


def test_the_viewer_draws_the_structure_and_asks_for_no_plotly(page):
    assert _drawn(_picture(page)) > 0.05
    assert not [url for url in page.asked if "plotly" in url]


def test_a_redraw_keeps_the_view_the_user_rotated_to(page):
    x, y = _centre(page)
    page.mouse.move(x, y)
    page.mouse.down()
    for k in range(1, 16):
        page.mouse.move(x + 6 * k, y + 2 * k)
    page.mouse.up()
    _settle(page)
    rotated = _picture(page)
    # a round trip through the other mode rebuilds the scene twice
    page.get_by_role("button", name="ellipsoids", exact=True).click()
    _settle(page)
    page.get_by_role("button", name="balls", exact=True).click()
    _settle(page)
    back = _picture(page)
    assert np.abs(back - rotated).mean() < 0.002
    # …and the drag did move the picture, or the comparison proves nothing
    page.get_by_role("button", name="reset", exact=True).click()
    _settle(page)
    assert np.abs(_picture(page) - rotated).mean() > 0.01


def test_an_anisotropic_site_shows_its_principal_ellipses(page):
    # four times the 50 % surface and zoomed in, so a ring is pixels wide
    page.get_by_role("button", name="ellipsoids", exact=True).click()
    page.get_by_role("button", name="▸ drawing").click()
    size = page.locator('.drawer input[type="range"][max="4"]')
    size.evaluate("el => { el.value = '4'; el.dispatchEvent(new Event('input', { bubbles: true })); }")
    page.mouse.move(*_centre(page))
    page.mouse.wheel(0, -600)
    _settle(page)
    rings = _dark_green(_picture(page))
    # the same picture in ball mode wears no ring ink
    page.get_by_role("button", name="balls", exact=True).click()
    _settle(page)
    # measured 18 104 against 675 in headless chromium (SwiftShader)
    assert rings > 2000
    assert _dark_green(_picture(page)) < rings / 10


def test_the_png_is_rendered_again_at_3000_pixels(page, tmp_path):
    with page.expect_download() as download:
        # the viewer's own: the pattern panel beside it has a PNG export too (WP-1461)
        page.locator("section.viewer").get_by_role("button", name="PNG", exact=True).click()
    path = tmp_path / "structure.png"
    download.value.save_as(path)
    image = np.asarray(imread(path), dtype=float)[..., :3]
    assert max(image.shape[:2]) == 3000
    assert _drawn(image) > 0.02
