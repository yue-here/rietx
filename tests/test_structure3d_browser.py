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


def _serve(tmp_path_factory, cif: str, aniso: bool):
    """A GUI over one CIF and any pattern: the viewer draws the model and
    never reads the data."""
    from tests.test_project import _write_xye
    from tests.test_refine_synthetic import perturbed_models, synthesize

    data = _write_xye(tmp_path_factory.mktemp("viewer-data") / "synth.xye", synthesize())
    _, instrument = perturbed_models()
    structure = structure_from_cif(str(DATA / cif), aniso=aniso)
    project = rx.Project.create(tmp_path_factory.mktemp("viewer") / "phase.rex",
                                pattern=data, instrument=instrument,
                                structure=structure, plan="mccusker_default")
    session = GuiSession(project, state_dir=tmp_path_factory.mktemp("viewer-state"))
    httpd = _start(session)
    try:
        yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    finally:
        httpd.shutdown()


@pytest.fixture(scope="module")
def gui(tmp_path_factory):
    """NAC with the file's anisotropic tensors."""
    yield from _serve(tmp_path_factory, "cod_1000236.cif", aniso=True)


@pytest.fixture(scope="module")
def acridine_gui(tmp_path_factory):
    """Acridine (COD 2242872), whose one-cell drawing closes eight planar
    rings (WP-1548): NAC closes none."""
    yield from _serve(tmp_path_factory, "cod_2242872.cif", aniso=False)


@pytest.fixture(scope="module")
def browser():
    with sync_playwright() as p:
        try:
            handle = p.chromium.launch(executable_path=_chromium() or None)
        except Exception as exc:  # noqa: BLE001 - any launch failure is a skip
            pytest.skip(f"no chromium to drive: {exc}")
        yield handle
        handle.close()


def _open(browser, url: str):
    page = browser.new_page(viewport={"width": 1400, "height": 900}, accept_downloads=True)
    errors: list[str] = []
    asked: list[str] = []
    page.on("pageerror", lambda exc: errors.append(str(exc)))
    page.on("request", lambda r: asked.append(r.url))
    page.goto(url)
    page.get_by_role("button", name="Model", exact=True).click()
    page.wait_for_selector(".viewer canvas")
    _settle(page)
    page.asked = asked
    yield page
    page.close()
    assert not errors, errors


@pytest.fixture
def page(browser, gui):
    yield from _open(browser, gui)


@pytest.fixture
def acridine_page(browser, acridine_gui):
    yield from _open(browser, acridine_gui)


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


def test_the_polyhedra_are_painted_and_give_way_to_their_switch(page, tmp_path):
    """WP-1466: NAC's AlF₆ octahedra are drawn by default in ball mode.

    jsdom sees only the scene the viewer hands over, so a face pass that
    painted nothing would pass every vitest.  The screen cannot tell either:
    the switch also moves the edges and the sticks the faces replace, and
    with the faces' alpha forced to 0 the picture still changed by 1.42
    levels against 2.86.  What only a face makes is a **translucent** pixel
    in the transparent export, where the background is nothing: the switch
    added 61 347 of them (1.15 % of 5.3 Mpx) and, faces broken, 1 400.
    """
    page.get_by_role("button", name="▸ drawing").click()
    page.locator(".drawer label", has_text="transparent PNG").locator("input").check()
    switch = page.locator(".viewer .legend").nth(1).get_by_role("button", name="polyhedra",
                                                               exact=True)

    def translucent(name: str) -> tuple[int, int]:
        with page.expect_download() as download:
            page.locator("section.viewer").get_by_role("button", name="PNG", exact=True).click()
        download.value.save_as(tmp_path / name)
        alpha = np.asarray(imread(tmp_path / name), dtype=float)[..., 3]
        return int(((alpha > 0.3) & (alpha < 0.9)).sum()), alpha.size

    drawn = _picture(page)
    faces, size = translucent("on.png")
    switch.click()
    _settle(page)
    bare, _ = translucent("off.png")
    switch.click()
    _settle(page)
    assert faces - bare > 0.003 * size
    # and the switch gives the picture back as it was
    assert float(np.abs(drawn - _picture(page)).mean() * 255) < 0.5


#: The mean difference, in 8-bit levels, between the viewer's canvas and the
#: Python renderer's picture of the same scene and view (WP-1470).  Measured
#: 1.06 in three runs (headless chromium, SwiftShader, 507 × 300 canvas), 86 %
#: of it on edges; a one-row misalignment of the two scored 4.49.  The bar is
#: about twice the measurement, which that misalignment fails.
PARITY_LEVELS = 2.0


@pytest.mark.parametrize("case", ["plain", "depth-cued", "planar-rings"])
def test_the_python_renderer_draws_the_viewers_picture(request, case):
    """WP-1470: one scene and one view drawn by both renderers, and WP-1548's
    depth cue and filled planar rings drawn by both, ticked in the drawer and
    asked of ``draw``.  The rings are acridine's, NAC closing none.

    The Python side takes the GUI's framing (``gui_frame``: its zoom-1 fit
    and centre) and the canvas's clear colour, and the DOM letters are hidden
    on the page, since their font is the browser's.  What is left differs
    where the two antialias: 4 samples a pixel here against MSAA with
    alpha-to-coverage there, and a ring's smoothstep against a threshold.
    """
    from rietx.gui import structure3d as s3
    from rietx.viz.figure3d import raster, rings
    from rietx.viz.figure3d import scene as sc
    from rietx.viz.figure3d.render import _png, gui_frame

    depth_cue, planar = case == "depth-cued", case == "planar-rings"
    page = request.getfixturevalue("acridine_page" if planar else "page")
    cif, aniso = ("cod_2242872.cif", False) if planar else ("cod_1000236.cif", True)
    page.add_style_tag(content=".viewer .letters { display: none; }")
    if depth_cue or planar:
        page.get_by_role("button", name="drawing").click()
        page.get_by_label("depth cue" if depth_cue else "fill planar rings").check()
        # the drawer opened above the canvas and moved it; close it again
        page.get_by_role("button", name="drawing").click()
    _settle(page)
    css_w, css_h, width, height = page.locator(".viewer canvas").evaluate(
        "c => [c.clientWidth, c.clientHeight, c.width, c.height]")
    # the canvas's box can sit at a fractional CSS position, where the
    # element's screenshot gains a row on the side the canvas is not painted;
    # chromium paints it at the rounded position, so clip exactly that
    canvas = page.locator(".viewer canvas")
    canvas.scroll_into_view_if_needed()
    box = canvas.bounding_box()
    png = page.screenshot(clip={"x": round(box["x"]), "y": round(box["y"]),
                                "width": width, "height": height})
    shown = np.asarray(imread(io.BytesIO(png)), dtype=float)[..., :3]
    accent = page.evaluate("getComputedStyle(document.body).getPropertyValue('--accent').trim()")
    geometry = s3.build(structure_from_cif(str(DATA / cif), aniso=aniso))
    fills = rings.ring_fills(geometry) if planar else ()
    scene = sc.build_scene(geometry, "ball", polyhedra=sc.shown_polyhedra(geometry, True),
                           cell=accent, fills=fills)
    rotation = np.asarray(sc.opening_view()).reshape(3, 3)
    frame = gui_frame(scene, rotation, width, height, css_w)
    ground = tuple(float(v) for v in shown[0, 0])
    fog = None
    if depth_cue:
        span = sc.fog_span(scene, sc.opening_view())
        shift = float(rotation[2] @ np.asarray(scene["center"]))
        fog = (span[0] + shift, span[1] + shift, sc.LOOK["fog_max"], ground)
    ours = raster.draw(scene, rotation, frame, supersample=4, background=ground, fog=fog)
    out = Path(__file__).parent / "output" / "figure3d"
    out.mkdir(parents=True, exist_ok=True)
    tag = {"plain": "", "depth-cued": "_cued", "planar-rings": "_rings"}[case]
    _png(out / f"parity_python{tag}.png", ours, None)
    theirs = np.concatenate([np.round(shown * 255), np.full(shown.shape[:2] + (1,), 255)],
                            axis=-1).astype(np.uint8)
    _png(out / f"parity_gui{tag}.png", theirs, None)
    assert shown.shape[:2] == (height, width) == (css_h, css_w)
    levels = float(np.abs(ours[..., :3] / 255 - shown).mean() * 255)
    print(f"parity{tag}: canvas {css_w}x{css_h} css px, mean |Δ| {levels:.2f} levels")
    assert levels < PARITY_LEVELS
    if depth_cue:
        # the fog moves the whole canvas by less than the bar above, most of it
        # being background, so ask also that the viewer fogged: over the drawn
        # pixels it is nearer Python's fogged picture than its plain one
        # (measured 5.9 against 13.8 levels, WP-1548)
        plain = raster.draw(scene, rotation, frame, supersample=4, background=ground)
        ink = np.abs(plain[..., :3] / 255 - plain[0, 0, :3] / 255).sum(axis=2) > 0.06
        near = float(np.abs(ours[..., :3] / 255 - shown)[ink].mean() * 255)
        far = float(np.abs(plain[..., :3] / 255 - shown)[ink].mean() * 255)
        assert near < 0.5 * far, (near, far)
    if planar:
        # likewise the rings: where filling them moved Python's picture, the
        # viewer is nearer the filled picture than the bare one
        bare = raster.draw({**scene, "faces": [f for f in scene["faces"]
                                               if f["kind"] == "polyhedron"]},
                           rotation, frame, supersample=4, background=ground)
        moved = np.abs(ours[..., :3] / 255 - bare[..., :3] / 255).sum(axis=2) > 0.06
        assert moved.sum() > 100
        near = float(np.abs(ours[..., :3] / 255 - shown)[moved].mean() * 255)
        far = float(np.abs(bare[..., :3] / 255 - shown)[moved].mean() * 255)
        print(f"parity{tag}: over the fills {near:.1f} against {far:.1f} levels")
        assert near < 0.5 * far, (near, far)


def test_the_png_is_rendered_again_at_3000_pixels(page, tmp_path):
    with page.expect_download() as download:
        # the viewer's own: the pattern panel beside it has a PNG export too (WP-1461)
        page.locator("section.viewer").get_by_role("button", name="PNG", exact=True).click()
    path = tmp_path / "structure.png"
    download.value.save_as(path)
    image = np.asarray(imread(path), dtype=float)[..., :3]
    assert max(image.shape[:2]) == 3000
    assert _drawn(image) > 0.02
