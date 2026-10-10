"""WP-1470 — a structure figure drawn in Python, without a browser.

Two halves.  The **scene corpus** holds the Python copy of the structure
viewer's scene rules equal to the TypeScript original: this module writes
``tests/data/gui/scene_cases.json`` from :mod:`rietx.viz.figure3d.scene` and
``gui/src/lib/structure3d.test.ts`` replays every case against ``buildScene``,
``shownPolyhedra``, ``lookFrom`` and ``axisView``.  The fixture is committed
because vitest runs where this package is not installed, so the check here is
``test_gui_fnmatch.py``'s one step removed: replay the rules over the committed
payloads, compare, and fail naming the file.
"""

from __future__ import annotations

import functools
import json
import struct
import zlib
from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.schemas.structure import AnisoU, Atom, Cell, Phase, Structure
from rietx.viz import component, keep, recolour, render_structure, select
from rietx.viz.figure3d import glyphs, raster, render, views
from rietx.viz.figure3d import report as rp
from rietx.viz.figure3d import scene as sc
from rietx.viz.figure3d.render import _png
from rietx.viz.theme import TOKENS
from tests.test_structure3d import MEASURED, measured

DATA = Path(__file__).parent / "data"
FIXTURE = DATA / "gui" / "scene_cases.json"
OUTPUT = Path(__file__).parent / "output" / "figure3d"


def _p(value: float) -> dict:
    return {"value": value}


def _monoclinic(**atom_kw) -> Structure:
    """P2₁/c, β = 110°: axes not orthogonal, a general position and a centre."""
    cell = Cell(a=_p(5.0), b=_p(9.0), c=_p(7.0),
                alpha=_p(90.0), beta=_p(110.0), gamma=_p(90.0))
    atoms = [Atom(label="C1", species="C", x=_p(0.12), y=_p(0.23), z=_p(0.34), **atom_kw),
             Atom(label="O1", species="O", x=_p(0.0), y=_p(0.0), z=_p(0.0))]
    return Structure(phases=[Phase(name="mono", space_group="P 1 21/c 1",
                                   cell=cell, atoms=atoms)])


def _rutile() -> Structure:
    """P4₂/mnm with an anisotropic Ti: octahedra, most of them centred on an
    image outside the cell, at 28 kB of payload against LaB6's 64."""
    cell = Cell(a=_p(4.594), b=_p(4.594), c=_p(2.959),
                alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0))
    atoms = [Atom(label="Ti1", species="Ti", x=_p(0.0), y=_p(0.0), z=_p(0.0),
                  aniso=AnisoU.from_values([0.006, 0.006, 0.004, 0.0005, 0.0, 0.0])),
             Atom(label="O1", species="O", x=_p(0.3049), y=_p(0.3049), z=_p(0.0))]
    return Structure(phases=[Phase(name="rutile", space_group="P 42/m n m",
                                   cell=cell, atoms=atoms)])


@functools.cache
def _payloads() -> dict[str, dict]:
    """Four payloads, chosen for the rules each one reaches, and small.
    Built once a process and shared, so a caller reads them and never edits.

    Rutile has images outside the cell, anisotropic rings and polyhedra drawn
    by default; at a bond tolerance of 0.8 it has no bonds and 34 atoms that
    are there only as a polyhedron's vertices.  The two monoclinic cells have
    one and two axes that are not positive, which reach both branches of
    ``drawable``'s floor.
    """
    one_bad = AnisoU.from_values([0.02, 0.03, -0.01, 0.0, 0.0, 0.004])
    two_bad = AnisoU.from_values([0.02, -0.01, -0.01, 0.0, 0.0, 0.0])
    return {
        "rutile": s3.build(_rutile()),
        "rutile_vertex_only": s3.build(_rutile(), bond_tolerance=0.8),
        "mono_one_flat": s3.build(_monoclinic(aniso=one_bad)),
        "mono_two_flat": s3.build(_monoclinic(aniso=two_bad)),
    }


def _round(value):
    """Twelve significant figures: the replay compares at 1e-9, and the file
    is a third the size of one written at seventeen."""
    if isinstance(value, float):
        return float(f"{value:.12g}")
    if isinstance(value, list):
        return [_round(v) for v in value]
    if isinstance(value, dict):
        return {k: _round(v) for k, v in value.items()}
    return value


def _cases(payloads: dict[str, dict]) -> tuple[list, list]:
    scenes, shown = [], []
    for name, geo in payloads.items():
        species = sorted({site["species"] for site in geo["sites"]})
        default = sc.shown_polyhedra(geo, True)
        everything = list(range(len(geo["polyhedra"])))
        formulas = sorted({sc.polyhedron_formula(geo, p) for p in geo["polyhedra"]})
        options = [
            {"mode": "ball", "polyhedra": default},
            {"mode": "ball", "polyhedra": everything},
            {"mode": "ellipsoid", "exaggeration": 1.7, "cell": "#3a7d44"},
            {"mode": "ball", "hidden": species[:1], "showBoundary": False,
             "polyhedra": sc.shown_polyhedra(geo, True, hidden=species[:1],
                                             show_boundary=False)},
        ]
        # a thinner stick (WP-1533), on the payloads that draw one: without
        # bonds the case is the atoms again
        if geo["bonds"]:
            options.append({"mode": "ellipsoid", "stick": 0.5})
        # rutile draws every polyhedron by default, and a repeated case is
        # 40 kB that tests nothing new
        options = [o for k, o in enumerate(options) if o not in options[:k]]
        for opt in options:
            scene = sc.build_scene(
                geo, opt["mode"], hidden=opt.get("hidden", ()),
                show_boundary=opt.get("showBoundary", True),
                exaggeration=opt.get("exaggeration", 1.0),
                polyhedra=opt.get("polyhedra", ()), cell=opt.get("cell", sc.CELL_INK),
                stick=opt.get("stick", 1.0))
            scenes.append({"payload": name, "options": opt, "scene": scene})
        toggles = [{"on": True}, {"on": False},
                   {"on": True, "hidden": species[:1]},
                   {"on": True, "showBoundary": False}]
        if formulas:
            toggles.append({"on": True, "formulas": {formulas[0]: not
                            any(p["drawn_by_default"] for p in geo["polyhedra"]
                                if sc.polyhedron_formula(geo, p) == formulas[0])}})
        for t in toggles:
            shown.append({"payload": name, **t, "shown": sc.shown_polyhedra(
                geo, t["on"], t.get("formulas"), t.get("hidden", ()),
                t.get("showBoundary", True))})
    return scenes, shown


def _views(payloads: dict[str, dict]) -> dict:
    pairs = [((1, 0, 0), (0, 0, 1)), ((0, 0, 1), (0, 1, 0)), ((1, 2, 3), (0, 0, 1)),
             ((-2, 0.5, 1), (1, 1, 0)), ((0, 0, 1), (0, 0, 1))]   # up ∥ eye: degenerate
    return {
        "look_from": [{"eye": list(e), "up": list(u), "rotation": sc.look_from(e, u)}
                      for e, u in pairs],
        "opening": sc.opening_view(),
        "axis": [{"payload": name, "axis": k, "rotation": sc.axis_view(geo, k)}
                 for name, geo in payloads.items() for k in range(3)],
    }


def _corpus(payloads: dict[str, dict] | None = None) -> dict:
    """The corpus over ``payloads``, or over fresh ones rounded as the file
    holds them, so the scenes written are the scenes the file's payloads give."""
    payloads = _round(_payloads()) if payloads is None else payloads
    scenes, shown = _cases(payloads)
    return _round({
        "note": ("Written by tests/test_render_structure.py from "
                 "rietx.viz.figure3d.scene; replayed by "
                 "gui/src/lib/structure3d.test.ts.  Do not edit."),
        "constants": {
            "LOOK": sc.LOOK, "STICK_RADIUS": sc.STICK_RADIUS,
            "STICK_OF_SEMI_AXIS": sc.STICK_OF_SEMI_AXIS, "STICK_FLOOR": sc.STICK_FLOOR,
            "FLAT_AXIS": sc.FLAT_AXIS, "CELL_WIDTH_PX": sc.CELL_WIDTH_PX,
            "EDGE_WIDTH_PX": sc.EDGE_WIDTH_PX, "POLY_ALPHA": sc.POLY_ALPHA,
        },
        "payloads": payloads,
        "scenes": scenes,
        "shown": shown,
        "views": _views(payloads),
    })


def _dump(corpus: dict) -> str:
    return json.dumps(corpus, separators=(",", ":"), ensure_ascii=False) + "\n"


#: A tenth of the replay's bar: ``structure3d.test.ts`` compares at 1e-9 of
#: max(1, |value|).  The committed file sits 5.5e-12 from its own replay, which
#: is the rounding of its payloads to twelve figures.
DRIFT = 1e-10


def _fields(value, where: str = "") -> set[str]:
    """Every field name ``value`` carries, by path, with a list's elements pooled."""
    if isinstance(value, dict):
        return {p for k, v in value.items()
                for p in {f"{where}.{k}"} | _fields(v, f"{where}.{k}")}
    if isinstance(value, list):
        return {p for v in value for p in _fields(v, f"{where}[]")}
    return set()


def _drift(ours, theirs, where: str = "corpus") -> str | None:
    """The first place two corpora differ, where floats within :data:`DRIFT` agree."""
    if isinstance(theirs, float) and isinstance(ours, float):
        if abs(ours - theirs) <= DRIFT * max(1.0, abs(theirs)):
            return None
    elif isinstance(theirs, list) and isinstance(ours, list) and len(ours) == len(theirs):
        return next(filter(None, (_drift(a, b, f"{where}[{k}]")
                                  for k, (a, b) in enumerate(zip(ours, theirs)))), None)
    elif isinstance(theirs, dict) and isinstance(ours, dict) and ours.keys() == theirs.keys():
        return next(filter(None, (_drift(ours[k], v, f"{where}.{k}")
                                  for k, v in theirs.items())), None)
    elif ours == theirs:
        return None
    return f"{where}: {str(ours)[:60]} against {str(theirs)[:60]}"


def test_the_committed_scene_corpus_is_current():
    """The rules replayed over the committed payloads, never over rebuilt ones.

    The payloads are the corpus's inputs.  ``structure3d.build`` breaks ties in
    distance on the last bit, and rutile's octahedron is all ties, so its vertex
    and face order moves with the platform while the picture does not.  Rebuilt,
    the file matched on the Mac that wrote it and failed on every Linux job.
    Over a fixed payload the rules are pure python.  A new case or a new payload
    field still rewrites the file, through the field names, which do not move.
    """
    committed = json.loads(FIXTURE.read_text(encoding="utf-8")) if FIXTURE.is_file() else {}
    payloads = committed.get("payloads", {})
    if _fields(payloads) != _fields(_payloads()):
        where = "corpus.payloads: a case or a field was added or removed"
        rewrite = _corpus()
    else:
        # a rule moved and the payloads did not: keep the committed ones, or
        # the rewrite carries this platform's vertex order as well
        rewrite = _corpus(payloads)
        where = _drift(json.loads(_dump(rewrite)), committed)
    if where:
        FIXTURE.write_text(_dump(rewrite), encoding="utf-8")
        raise AssertionError(
            f"{FIXTURE.relative_to(DATA.parent.parent)} was stale at {where}, and has "
            "been rewritten; commit it, and run `npm --prefix gui test` (the vitest "
            "replay reads the committed copy, and node never runs this suite)")


def test_the_corpus_reaches_every_rule_it_exists_for():
    """A corpus that never hides a species or floors an axis proves nothing
    about the code that does."""
    corpus = json.loads(FIXTURE.read_text(encoding="utf-8"))
    scenes = [c["scene"] for c in corpus["scenes"]]
    payloads = corpus["payloads"]
    assert any(a.get("vertex_only") for g in payloads.values() for a in g["atoms"])
    # rutile's two Ti outside the cell, and their sticks (WP-1529)
    assert any(a.get("outside_centre") for g in payloads.values() for a in g["atoms"])
    assert any(b.get("outside_centre") for g in payloads.values() for b in g["bonds"])
    assert any(a["npd"] for g in payloads.values() for a in g["atoms"])
    # a floored axis is FLAT_AXIS long, in both of drawable's branches: one
    # flat axis (mono_one_flat) and two (mono_two_flat)
    floored = {case["payload"] for case in corpus["scenes"] for a in case["scene"]["atoms"]
               for c in range(3)
               if abs(sum(a["shape"][3 * r + c] ** 2 for r in range(3)) ** 0.5
                      - sc.FLAT_AXIS) < 1e-12}
    assert {"mono_one_flat", "mono_two_flat"} <= floored
    assert any(s["faces"] for s in scenes)
    assert any(a["rings"] for s in scenes for a in s["atoms"])
    # a stick scaled off its default, on a scene that draws one (WP-1533)
    assert any(case["options"].get("stick", 1.0) != 1.0 and case["scene"]["halves"]
               for case in corpus["scenes"])
    shown = [c["shown"] for c in corpus["shown"] if c["on"]]
    whole = [len(corpus["payloads"][c["payload"]]["polyhedra"]) for c in corpus["shown"]
             if c["on"]]
    assert any(0 < len(s) < n for s, n in zip(shown, whole))   # a strict subset
    assert any(len(s) == n > 0 for s, n in zip(shown, whole))
    assert any(not s and n for s, n in zip(shown, whole))       # all switched off


@pytest.mark.parametrize("axis, up", [(0, 2), (1, 2), (2, 1)])
def test_an_axis_view_keeps_c_up_unless_it_looks_down_c(axis, up):
    """D12's convention: c up down a and down b, b up down c."""
    geo = _payloads()["mono_one_flat"]
    rotation = sc.axis_view(geo, axis)
    lattice = geo["lattice"]
    screen_y = rotation[3:6]
    toward = rotation[6:9]
    norm = sum(v * v for v in lattice[axis]) ** 0.5
    assert all(abs(toward[i] - lattice[axis][i] / norm) < 1e-12 for i in range(3))
    assert sum(screen_y[i] * lattice[up][i] for i in range(3)) > 0


# ----------------------------------------------------------------------
# the renderer
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def nac():
    return structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)


def _save(fig, name):
    """Every picture a test draws is written for looking at (tests/CLAUDE.md)."""
    OUTPUT.mkdir(parents=True, exist_ok=True)
    _png(OUTPUT / f"{name}.png", fig.image, None)


def _one_atom(payload: dict) -> dict:
    """A payload's first atom alone: no bonds, no frame, no polyhedra.  A dict
    edited and handed back is the customisation route D10 promises."""
    geo = dict(payload)
    geo["atoms"] = [dict(payload["atoms"][0], boundary=False)]
    geo["bonds"], geo["polyhedra"], geo["edges"] = [], [], []
    return geo


def _general_ellipsoid() -> dict:
    return s3.build(_monoclinic(
        aniso=AnisoU.from_values([0.03, 0.012, 0.02, 0.004, -0.003, 0.006])))


@pytest.mark.parametrize("kw", [
    {"mode": "ball", "polyhedra": True, "atom_labels": True},
    {"mode": "ellipsoid", "background": None, "outline": True},
])
def test_a_band_boundary_moves_no_bit(nac, kw, monkeypatch):
    """The picture is drawn a band of rows at a time, and where the bands
    break moves nothing: the outline reads across a boundary through its
    halo."""
    whole = render_structure(nac, size=240, **kw).image
    monkeypatch.setattr(raster, "BAND_SAMPLES", 2000)      # dozens of bands
    banded = render_structure(nac, size=240, **kw).image
    assert np.array_equal(whole, banded)
    assert (whole[..., 3] > 0).sum() > 5000


def test_two_renders_are_identical(nac):
    a = render_structure(nac, size=200, mode="ellipsoid").image
    b = render_structure(nac, size=200, mode="ellipsoid").image
    assert np.array_equal(a, b)


def test_a_balls_silhouette_is_its_radius_in_pixels():
    geo = _one_atom(_general_ellipsoid())
    fig = render_structure(geo, size=400, axis_labels=False, background=None)
    _save(fig, "one_ball")
    r = geo["ball_fraction"] * geo["sites"][0]["radius"] * fig.pixels_per_angstrom
    area = (fig.image[..., 3] >= 128).sum()
    assert abs(np.sqrt(area / np.pi) - r) < 0.5


def test_an_ellipsoids_silhouette_is_the_exact_projected_ellipse():
    """Its half-extents are the norms of the first two rows of R·k·T, and its
    area π·√det of that 2 × 3 block times its transpose."""
    geo = _one_atom(_general_ellipsoid())
    fig = render_structure(geo, mode="ellipsoid", view=[1, 2, 3], size=400,
                           axis_labels=False, background=None)
    _save(fig, "one_ellipsoid")
    M = np.asarray(fig.rotation) @ (np.asarray(geo["atoms"][0]["ellipsoid"]) * geo["scale"])
    ppa = fig.pixels_per_angstrom
    inside = fig.image[..., 3] >= 128
    ys, xs = np.nonzero(inside)
    assert abs((xs.max() - xs.min() + 1) - 2 * np.linalg.norm(M[0]) * ppa) < 1.5
    assert abs((ys.max() - ys.min() + 1) - 2 * np.linalg.norm(M[1]) * ppa) < 1.5
    A = M[:2]
    assert abs(inside.sum() / (np.pi * np.sqrt(np.linalg.det(A @ A.T)) * ppa ** 2) - 1) < 0.01


def test_a_cubic_cell_seen_down_c_is_a_square():
    lab6 = structure_from_cif(str(DATA / "cod_1000055.cif"))
    fig = render_structure(lab6, view="c", hidden=["La", "B"], axis_labels=False,
                           size=300, background=None)
    _save(fig, "lab6_frame_down_c")
    ys, xs = np.nonzero(fig.image[..., 3] > 0)
    assert abs((xs.max() - xs.min()) - (ys.max() - ys.min())) <= 1
    h, w = fig.image.shape[:2]
    assert fig.image[h // 2, w // 2, 3] == 0            # a frame, not a filled square


def test_a_transparent_background_is_straight_alpha_with_no_fringe(nac):
    """Alpha is zero outside the structure, and the transparent picture
    composited over white is the white picture, to a level (D7)."""
    clear = render_structure(nac, size=240, background=None, polyhedra=True).image
    white = render_structure(nac, size=240, polyhedra=True).image
    assert clear[0, 0, 3] == 0 and clear[-1, -1, 3] == 0
    assert (clear[..., :3][clear[..., 3] == 0] == 0).all()
    a = clear[..., 3:].astype(float) / 255
    over = clear[..., :3].astype(float) * a + 255 * (1 - a)
    # the straight colour and the alpha each round to a level, and the white
    # picture rounds once more
    assert np.abs(over - white[..., :3]).max() <= 1.5
    assert (white[..., 3] == 255).all()


def test_a_polyhedron_leaves_a_translucent_pixel():
    fig = render_structure(s3.build(_rutile()), hidden=["O"], size=300, background=None,
                           axis_labels=False)
    _save(fig, "rutile_faces")
    # a pixel inside a closed polyhedron sees a back face and a front face
    alpha = fig.image[..., 3].astype(int)
    level = round((1 - (1 - sc.POLY_ALPHA) ** 2) * 255)
    assert ((alpha > level - 3) & (alpha < level + 3)).sum() > 500


def test_a_non_positive_tensor_draws_no_nan():
    geo = s3.build(_monoclinic(aniso=AnisoU.from_values([0.02, -0.01, -0.01, 0.0, 0.0, 0.0])))
    with np.errstate(invalid="raise", divide="raise"):
        fig = render_structure(geo, mode="ellipsoid", size=200, background=None)
    assert (fig.image[..., 3] > 0).sum() > 200


def test_the_png_carries_its_chunks_and_the_array(tmp_path, nac):
    fig = render_structure(nac, size=120, background=None, path=tmp_path / "nac.png", dpi=300)
    data = (tmp_path / "nac.png").read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    chunks, at, order = {}, 8, []
    while at < len(data):
        n = struct.unpack(">I", data[at:at + 4])[0]
        kind = data[at + 4:at + 8]
        body = data[at + 8:at + 8 + n]
        # a wrong CRC is a file every decoder refuses
        assert struct.unpack(">I", data[at + 8 + n:at + 12 + n])[0] \
            == zlib.crc32(kind + body) & 0xFFFFFFFF, kind
        chunks[kind] = chunks.get(kind, b"") + body
        order.append(kind)
        at += 12 + n
    assert order[0] == b"IHDR" and order[-1] == b"IEND"
    w, h, depth, colour = struct.unpack(">IIBB", chunks[b"IHDR"][:10])
    assert (w, h, depth, colour) == (fig.image.shape[1], fig.image.shape[0], 8, 6)
    assert chunks[b"sRGB"] == b"\x00"
    assert struct.unpack(">IIB", chunks[b"pHYs"]) == (11811, 11811, 1)   # 300 dpi
    rows = np.frombuffer(zlib.decompress(chunks[b"IDAT"]), dtype=np.uint8).reshape(h, 1 + 4 * w)
    assert (rows[:, 0] == 0).all()
    assert np.array_equal(rows[:, 1:].reshape(h, w, 4), fig.image)
    assert fig.path == str(tmp_path / "nac.png")


def test_a_jpeg_is_refused(tmp_path, nac):
    with pytest.raises(ValueError, match="PNG only"):
        render_structure(nac, path=tmp_path / "nac.jpg")


def test_a_switch_that_switches_nothing_is_refused(nac):
    """A formula the phase lacks, like ``hidden=``'s unknown species, would
    look like success; so would a dpi of zero in the file."""
    with pytest.raises(ValueError, match="AlF₆"):
        render_structure(nac, size=100, polyhedra={"AlF6": False})
    with pytest.raises(ValueError, match="dpi"):
        render_structure(nac, size=100, dpi=0)


# ----------------------------------------------------------------------
# views (D12)
# ----------------------------------------------------------------------

def test_the_rotation_drawn_round_trips(nac):
    fig = render_structure(nac, view=[1, 2, 0], turn="20y,-10x", size=160)
    again = render_structure(nac, view=fig.rotation, size=160)
    assert np.array_equal(fig.image, again.image)


def test_down_001_and_the_001_normal_on_a_cubic_cell_are_the_c_view(nac):
    """Compared as rotations: NAC's lattice carries 6e-16 Å off the diagonal,
    so c* leans 6e-17 from c and a bit-identical image would be luck."""
    c = render_structure(nac, view="c", size=160).rotation
    for view in ([0, 0, 1], {"hkl": (0, 0, 1)}):
        assert np.allclose(render_structure(nac, view=view, size=160).rotation, c,
                           rtol=0, atol=1e-12)


def test_a_turn_is_ases_rotation_about_the_screen():
    """'90x' tips the top toward the viewer: down c with b up becomes b toward
    the viewer with c down (``ase.utils.rotate``'s signs)."""
    geo = _payloads()["rutile"]
    R = views.resolve(geo, "c", turn="90x")
    b = np.asarray(geo["lattice"][1]) / np.linalg.norm(geo["lattice"][1])
    c = np.asarray(geo["lattice"][2]) / np.linalg.norm(geo["lattice"][2])
    assert np.allclose(R @ b, [0, 0, 1], atol=1e-12)
    assert np.allclose(R @ c, [0, -1, 0], atol=1e-12)
    assert not np.allclose(views.ase_rotation("50x,40z"), views.ase_rotation("40z,50x"))


def test_the_default_up_is_c_and_never_the_view():
    geo = _payloads()["mono_one_flat"]
    R = views.resolve(geo, [1, 1, 0])
    assert R[1] @ np.asarray(geo["lattice"][2]) > 0
    R = views.resolve(geo, [0.1, 0, 1])                   # nearest c: b up
    assert R[1] @ np.asarray(geo["lattice"][1]) > 0
    with pytest.raises(ValueError, match="parallel"):
        views.resolve(geo, "a", up=[2, 0, 0])
    with pytest.raises(ValueError, match="view= takes"):
        views.resolve(geo, "down the middle")
    with pytest.raises(ValueError, match="rotation"):
        views.resolve(geo, [[1, 0, 0], [0, 1, 0], [0, 0, -1]])


# ----------------------------------------------------------------------
# output and options
# ----------------------------------------------------------------------

def test_size_is_the_long_side_or_the_frame(nac):
    assert max(render_structure(nac, size=300).image.shape[:2]) == 300
    assert render_structure(nac, size=(320, 180)).image.shape[:2] == (180, 320)
    with pytest.raises(ValueError, match="supersample"):
        render_structure(nac, supersample=5)
    with pytest.raises(ValueError, match="mode"):
        render_structure(nac, mode="wireframe")


def test_the_anchors_say_where_each_atom_and_letter_landed(nac):
    fig = render_structure(_one_atom(_general_ellipsoid()), size=300, background=None)
    (atom,) = fig.atoms
    assert fig.image[round(atom["y"]), round(atom["x"]), 3] == 255
    fig = render_structure(nac, size=300)
    assert [letter["text"] for letter in fig.letters] == ["a", "b", "c"]
    h, w = fig.image.shape[:2]
    assert all(0 <= t["x"] < w and 0 <= t["y"] < h for t in fig.letters)


def test_to_px_is_the_map_that_placed_the_atoms(nac):
    """WP-1533: four of twelve promo scripts fitted this map by least squares
    from ``atoms``.  It is the one the renderer used, on a view down no axis of
    a monoclinic cell, with the frame left out so the fit moves."""
    geometry = s3.build(_monoclinic())
    fig = render_structure(geometry, view=[1, 2, 3], turn="20y", size=300, cell=False)
    pos = np.array([geometry["atoms"][a["index"]]["pos"] for a in fig.atoms])
    drawn = np.array([[a["x"], a["y"]] for a in fig.atoms])
    assert len(drawn) > 1 and fig.to_px(pos).shape == drawn.shape
    np.testing.assert_allclose(fig.to_px(pos), drawn, rtol=0, atol=1e-9)
    np.testing.assert_allclose(fig.to_px(pos[0]), drawn[0], rtol=0, atol=1e-9)
    with pytest.raises(ValueError, match=r"\(N, 3\)"):
        fig.to_px(pos[:, :2])
    # down c of a cubic cell with b up, a points right and b up the page
    fig = render_structure(nac, view="c", size=200)
    a, b, _ = np.asarray(s3.build(nac)["lattice"])
    zero = fig.to_px(np.zeros(3))
    np.testing.assert_allclose((fig.to_px(a) - zero) / fig.pixels_per_angstrom,
                               [np.linalg.norm(a), 0.0], atol=1e-9)
    np.testing.assert_allclose((fig.to_px(b) - zero) / fig.pixels_per_angstrom,
                               [0.0, -np.linalg.norm(b)], atol=1e-9)


def test_the_options_reach_the_picture(nac):
    base = render_structure(nac, size=200)
    no_na = render_structure(nac, size=200, hidden=["Na"]).atoms
    assert no_na and not any(a["species"].startswith("Na") for a in no_na)
    assert render_structure(nac, size=200, hidden="Na1+").atoms == no_na
    with pytest.raises(ValueError, match="no such species"):
        render_structure(nac, size=200, hidden=["Nb"])
    assert not any(a["boundary"] for a in render_structure(nac, size=200,
                                                           boundary=False).atoms)
    off = render_structure(nac, size=200, polyhedra=False)
    assert not np.array_equal(off.image, base.image)
    assert np.array_equal(render_structure(nac, size=200, polyhedra={"AlF₆": False}).image,
                          off.image)
    assert tuple(render_structure(nac, size=200, background="black").image[0, 0]) \
        == (0, 0, 0, 255)
    outlined = render_structure(nac, size=200, outline=True)
    assert (outlined.image[..., :3].sum(-1) < base.image[..., :3].sum(-1)).sum() > 500
    # the outline marks surfaces: the frame keeps its accent (it once went black)
    accent = np.asarray(sc.rgb(TOKENS["light"]["--accent"])) * 255

    def framed(img):
        return (np.abs(img[..., :3].astype(float) - accent).max(-1) < 10).sum()

    assert framed(outlined.image) > 0.9 * framed(base.image) > 50
    # a larger surface covers more of the frame, whether by probability or by
    # a drawing scale
    ink = [(render_structure(nac, size=200, mode="ellipsoid", axis_labels=False,
                             background=None, **kw).image[..., 3] > 0).sum()
           for kw in ({}, {"probability": 0.9}, {"exaggeration": 1.5})]
    assert ink[1] > ink[0] and ink[2] > ink[0]
    with pytest.raises(ValueError, match="build the geometry"):
        render_structure(s3.build(nac), probability=0.9)


# ----------------------------------------------------------------------
# letters (D8)
# ----------------------------------------------------------------------

def test_the_font_ships_with_its_acknowledgement():
    from importlib import resources

    doc = json.loads(resources.files("rietx.data").joinpath("hershey_simplex.json")
                     .read_text(encoding="utf-8"))
    assert "Hershey" in doc["acknowledgement"] and "NTIS" in doc["licence"]
    assert len(doc["glyphs"]) == 95


def test_the_letters_are_drawn_in_the_accent_at_their_anchors(nac):
    fig = render_structure(nac, size=600)
    accent = np.asarray(sc.rgb(TOKENS["light"]["--accent"])) * 255
    for letter in fig.letters:
        x, y = round(letter["x"]), round(letter["y"])
        # a negative start would wrap to the far edge
        patch = fig.image[max(y - 8, 0):y + 9, max(x - 8, 0):x + 9, :3]
        patch = patch.reshape(-1, 3).astype(float)
        assert (np.abs(patch - accent).max(axis=1) < 12).any(), letter
    bare = render_structure(nac, size=600, axis_labels=False)
    assert bare.letters == [] and not np.array_equal(bare.image, fig.image)
    # the labels widen the frame to hold them, so count their ink rather than
    # differencing two frames
    labelled = render_structure(nac, size=600, atom_labels=True)
    ink = np.asarray(sc.rgb(TOKENS["light"]["--fg"])) * 255

    def inked(image):
        return int((np.abs(image[..., :3].astype(float) - ink).max(axis=-1) < 12).sum())

    assert inked(labelled.image) - inked(fig.image) > 1000
    _save(labelled, "nac_atom_labels")


# ----------------------------------------------------------------------
# the figure reports on itself (WP-1503)
# ----------------------------------------------------------------------

def _stack(z_near: float = 0.75, z_far: float = 0.25, **atom_kw) -> dict:
    """Two carbon atoms one behind the other along c, in a cubic P1 cell with
    no bonds: looking down c the far one is covered, looking down a it is not."""
    cell = Cell(a=_p(6.0), b=_p(6.0), c=_p(6.0), alpha=_p(90.0), beta=_p(90.0), gamma=_p(90.0))
    atoms = [Atom(label="C1", species="C", x=_p(0.5), y=_p(0.5), z=_p(z_near), **atom_kw),
             Atom(label="C2", species="C", x=_p(0.5), y=_p(0.5), z=_p(z_far), **atom_kw)]
    return s3.build(Structure(phases=[Phase(name="stack", space_group="P 1",
                                            cell=cell, atoms=atoms)]))


def test_an_atom_behind_another_is_hidden_and_one_beside_it_is_not():
    geometry = _stack()
    behind = render_structure(geometry, view="c", size=300)
    (index,) = behind.report.hidden_atoms
    assert geometry["atoms"][index]["frac"][2] == pytest.approx(0.25)
    assert behind.report.hidden == 0.5
    beside = render_structure(geometry, view="a", size=300)
    assert beside.report.hidden == 0.0 and beside.report.hidden_atoms == []


def test_the_empty_share_is_what_the_image_leaves_blank():
    geometry = _stack()
    fig = render_structure(geometry, size=300, background=None)
    assert fig.report.empty == (fig.image[..., 3] == 0).mean()
    white = render_structure(geometry, size=300)
    assert white.report.empty == (white.image[..., :3] == 255).all(axis=-1).mean()
    # two balls and a cell frame in a frame fitted to them: most of it is air
    assert 0.3 < white.report.empty < 0.99
    # a frame asked to be wider than the content is emptier
    wide = render_structure(geometry, size=(900, 300), background=None)
    assert wide.report.empty > fig.report.empty


def test_a_bond_toward_an_atom_that_is_not_drawn_dangles(nac):
    geometry = s3.build(nac)
    assert render_structure(geometry, size=200).report.dangling_bonds == 0
    bare = render_structure(geometry, size=200, boundary=False)
    # counted by position, not by the bond's atom indices the report reads: a
    # half whose bond's other end has no drawn atom on it
    scene = sc.build_scene(geometry, "ball", show_boundary=False,
                           polyhedra=sc.shown_polyhedra(geometry, True, None, [], False))
    drawn = np.array([a["pos"] for a in scene["atoms"]])
    want = 0
    for h in scene["halves"]:
        bond = geometry["bonds"][h["bond"]]
        other = bond["b"] if list(bond["a"]) == h["from"] else bond["a"]
        want += bool(np.linalg.norm(drawn - np.asarray(other), axis=1).min() > 1e-6)
    assert want > 0 and bare.report.dangling_bonds == want
    # a species the caller took away leaves its neighbours' halves, which dangle
    species = geometry["sites"][0]["species"]
    asked = render_structure(geometry, size=200, hidden=[species])
    assert asked.report.dangling_bonds > 0


@pytest.mark.parametrize("name, element", [("calcite CaCO3", "Ca"), ("LaB6", "La")])
def test_the_stubs_hidden_leaves_are_the_stubs_the_report_counts(name, element):
    """Round B's calcite under ``hidden=("Ca",)`` was covered in O stubs while
    the report read 0 (WP-1529).  The count is each half the scene draws
    toward a hidden atom, and ``keep`` takes the species with its bonds whole,
    which draws none."""
    geometry = s3.build(measured(next(r for r in MEASURED if r["name"] == name)))
    fig = render_structure(geometry, size=200, hidden=(element,))
    species = sorted({s["species"] for s in geometry["sites"] if s["element"] == element})
    scene = sc.build_scene(geometry, "ball", hidden=species, polyhedra=sc.shown_polyhedra(
        geometry, True, None, species, True))
    toward = 0
    for h in scene["halves"]:
        bond = geometry["bonds"][h["bond"]]
        other = bond["b"] if list(bond["a"]) == h["from"] else bond["a"]
        toward += any(geometry["sites"][a["site"]]["element"] == element
                      and np.allclose(a["pos"], other) for a in geometry["atoms"])
    assert toward > 0 and fig.report.dangling_bonds == toward
    cut = keep(geometry, ~select(geometry, element=element))
    clean = render_structure(cut, size=400)
    assert clean.report.dangling_bonds == 0
    _save(render_structure(geometry, size=400, hidden=(element,)), f"stubs_{element}_hidden")
    _save(clean, f"stubs_{element}_kept")


@pytest.mark.parametrize("name", ["rutile TiO2", "fluorapatite", "calcite CaCO3"])
def test_the_round_b_phases_draw_no_bare_centre(name):
    """The pictures WP-1529 looks at: polyhedra on, no centre outside the cell
    without its polyhedron; the scene test is test_structure3d's."""
    geometry = s3.build(measured(next(r for r in MEASURED if r["name"] == name)))
    fig = render_structure(geometry, size=500)
    _save(fig, "bare_centres_" + name.split()[0])
    shown = sc.shown_polyhedra(geometry, True, None, [], True)
    centred = {geometry["atoms"][geometry["polyhedra"][i]["center"]]["site"] for i in shown}
    drawn = [geometry["atoms"][a["index"]] for a in fig.atoms]
    assert not any(a["outside_centre"] and a["site"] in centred for a in drawn)


def test_a_recoloured_image_is_still_a_centre_of_its_site():
    """``recolour`` points the masked images at a copy of their site, so a
    test keyed on ``atoms[k]["site"]`` lost them: dimming fluorapatite's
    images drew its 4 P outside the cell bare again."""
    geometry = s3.build(measured(next(r for r in MEASURED if r["name"] == "fluorapatite")))
    dimmed = recolour(geometry, select(geometry, boundary=True), "#cccccc")
    for g in (geometry, dimmed):
        scene = sc.build_scene(g, polyhedra=sc.shown_polyhedra(g, True))
        bare = [g["sites"][g["atoms"][a["index"]]["site"]]["element"] for a in scene["atoms"]
                if g["atoms"][a["index"]]["outside_centre"]]
        assert "P" not in bare


def test_labels_that_share_a_place_overlap(monkeypatch):
    """Two atoms one behind the other: their labels would share a place, and
    the second takes another (#666).  Held to the first place, the rule
    before, they overlap, and each sits on the other's atom."""
    geometry = _stack()
    down = render_structure(geometry, view="c", size=400, atom_labels=True)
    across = render_structure(geometry, view="a", size=400, atom_labels=True)
    assert down.report.label_overlaps == 0
    assert across.report.label_overlaps == 0
    assert render_structure(geometry, view="c", size=400).report.label_overlaps == 0
    monkeypatch.setattr(render, "LABEL_ANCHORS", render.LABEL_ANCHORS[:1])
    held = render_structure(geometry, view="c", size=400, atom_labels=True)
    assert (held.report.label_overlaps, held.report.label_atom_overlaps) == (1, 2)


# ----------------------------------------------------------------------
# site labels clear of atoms and bonds (#666, WP-1531)
# ----------------------------------------------------------------------

@functools.cache
def _paracetamol() -> dict:
    """One whole paracetamol molecule (COD 2104364), cut from a block of cells
    as issue #666 cut it, without the cell edges.  Built once a process and
    shared, so a caller reads it and never edits."""
    block = s3.build(structure_from_cif(str(DATA / "cod_2104364.cif"), aniso=True),
                     extent=((-1, 2), (-1, 2), (-1, 2)), max_atoms=4000)
    pos = np.array([a["pos"] for a in block["atoms"]])
    nitrogen = [i for i, a in enumerate(block["atoms"])
                if block["sites"][a["site"]]["element"] == "N"]
    middle = min(nitrogen, key=lambda i: float(np.linalg.norm(pos[i] - pos.mean(axis=0))))
    return {**keep(block, component(block, middle)), "edges": []}


def _label_counts(fig) -> tuple[int, int, int]:
    r = fig.report
    return r.label_overlaps, r.label_atom_overlaps, r.label_bond_overlaps


#: (label_overlaps, label_atom_overlaps, label_bond_overlaps) on the molecule
#: at 800 px.  The rule before #666 put every label up and to the right of its
#: atom, and measured (1, 2, 15) in ball mode and (0, 3, 14) in ellipsoid mode.
#: The bond left in ellipsoid mode is C9's: four bonds leave it, and every
#: place around it meets one.
PARACETAMOL_LABELS = {"ball": (0, 0, 0), "ellipsoid": (0, 0, 1)}


@pytest.mark.parametrize("mode", ["ball", "ellipsoid"])
def test_site_labels_are_placed_clear_of_atoms_and_bonds(mode):
    molecule = _paracetamol()
    fig = render_structure(molecule, mode=mode, atom_labels=True, axis_labels=False, size=800)
    _save(fig, f"labels_paracetamol_{mode}")
    assert len(fig.atoms) == 20
    assert _label_counts(fig) == PARACETAMOL_LABELS[mode]
    again = render_structure(molecule, **json.loads(json.dumps(fig.recipe)))
    assert np.array_equal(again.image, fig.image) and again.report == fig.report


@pytest.mark.parametrize("mode", ["ball", "ellipsoid"])
def test_the_counts_see_the_old_placement_land_on_bonds(mode, monkeypatch):
    """Held to the first place, the rule before #666, the labels land where
    the issue saw them: O8 on H92, H7 on N7, and across bonds."""
    monkeypatch.setattr(render, "LABEL_ANCHORS", render.LABEL_ANCHORS[:1])
    fig = render_structure(_paracetamol(), mode=mode, atom_labels=True, axis_labels=False,
                           size=800)
    _save(fig, f"labels_paracetamol_{mode}_one_place")
    assert _label_counts(fig) == {"ball": (1, 2, 15), "ellipsoid": (0, 3, 14)}[mode]


def test_a_label_with_no_clear_place_is_counted_on_what_it_meets():
    """The far atom of two, drawn at four times the near one's radius: every
    place around the near atom lies on it.  The near label keeps the first
    place and is counted once; the far one's first place is clear."""
    geometry = _stack()
    far = next(k for k, s in enumerate(geometry["sites"]) if s["label"] == "C2")
    sites = [dict(s, radius=4 * s["radius"]) if k == far else s
             for k, s in enumerate(geometry["sites"])]
    fig = render_structure({**geometry, "sites": sites}, view="c", size=400,
                           axis_labels=False, atom_labels=True)
    _save(fig, "labels_no_clear_place")
    assert _label_counts(fig) == (0, 1, 0)


@pytest.mark.parametrize("anchor", range(len(render.LABEL_ANCHORS)))
def test_a_label_in_any_place_is_inside_the_frame(anchor, monkeypatch):
    """The frame is fitted before the labels are placed, so it holds a label
    in whichever place it takes.  The frame's padding is taken away, or it
    would hide a bound that falls short.  A one-letter label is narrower than
    it is tall, which is the case the label's width alone does not bound."""
    placed = []

    def spy(*args, **kw):
        out = labels(*args, **kw)
        placed.extend(out)
        return out

    labels = render._labels
    monkeypatch.setattr(render, "_labels", spy)
    monkeypatch.setattr(render, "LABEL_ANCHORS", render.LABEL_ANCHORS[anchor:anchor + 1])
    monkeypatch.setattr(render, "FIT_PAD", 0.0)
    molecule = _paracetamol()
    letters = {**molecule, "sites": [dict(s, label=s["element"]) for s in molecule["sites"]]}
    for geometry in (molecule, letters):
        placed.clear()
        fig = render_structure(geometry, atom_labels=True, axis_labels=False, size=300)
        height, width = fig.image.shape[:2]
        em = render.LETTER_EM_CSS * 300 / render.CANVAS_CSS_PX
        assert len(placed) == 20
        for text, x, y, _, half, *_ in placed:
            w = glyphs.width(text, em)
            assert 0.0 <= x - w / 2 and x + w / 2 <= width, text
            assert 0.0 <= y - half and y + half <= height, text


def test_the_label_shape_tests_agree_with_sampling():
    """The label tests are exact, and a grid of points in a box can only miss
    a sliver.  So a box a grid point of which lies in a shape meets it, and a
    box that meets a shape has a grid point in it once grown by 2 px.  The
    ellipses are no flatter than 4 to 20, so a sliver is wider than the
    grid's 0.5 px."""
    rng = np.random.default_rng(666)
    n = 30
    a, b, phi = rng.uniform(4, 20, n), rng.uniform(4, 20, n), rng.uniform(0, np.pi, n)
    c, s = np.cos(phi), np.sin(phi)
    shapes = {"cx": rng.uniform(0, 120, n), "cy": rng.uniform(0, 120, n),
              "sxx": (a * c) ** 2 + (b * s) ** 2, "syy": (a * s) ** 2 + (b * c) ** 2,
              "sxy": (a * a - b * b) * c * s,
              "px": rng.uniform(0, 120, n), "py": rng.uniform(0, 120, n),
              "r": rng.uniform(1.5, 6, n)}
    length = np.where(np.arange(n) % 10 == 0, 0.0, rng.uniform(5, 60, n))  # some are dots
    turn = rng.uniform(0, 2 * np.pi, n)
    shapes["qx"] = shapes["px"] + length * np.cos(turn)
    shapes["qy"] = shapes["py"] + length * np.sin(turn)
    x0, y0 = rng.uniform(0, 120, 60), rng.uniform(0, 120, 60)
    boxes = np.stack([x0, x0 + rng.uniform(2, 40, 60), y0, y0 + rng.uniform(2, 20, 60)], axis=1)
    # three boxes each holding a whole ellipse, which no edge of theirs meets
    held = [[shapes["cx"][k] - 25, shapes["cx"][k] + 25, shapes["cy"][k] - 25,
             shapes["cy"][k] + 25] for k in range(3)]
    boxes = np.concatenate([boxes, held])
    every = np.arange(n)
    exact = {"atoms": render._on_atoms(boxes, shapes, every),
             "halves": render._on_halves(boxes, shapes, every)}

    def sampled(box, grow):
        # no wider apart than 0.5 px, and never past the box's edges
        xs = np.linspace(box[0] - grow, box[1] + grow, int((box[1] - box[0] + 2 * grow) * 2) + 2)
        ys = np.linspace(box[2] - grow, box[3] + grow, int((box[3] - box[2] + 2 * grow) * 2) + 2)
        gx, gy = (g.ravel()[:, None] for g in np.meshgrid(xs, ys))
        ux, uy = gx - shapes["cx"], gy - shapes["cy"]
        det = shapes["sxx"] * shapes["syy"] - shapes["sxy"] ** 2
        form = shapes["syy"] * ux * ux - 2 * shapes["sxy"] * ux * uy + shapes["sxx"] * uy * uy
        dx, dy = shapes["qx"] - shapes["px"], shapes["qy"] - shapes["py"]
        along = (gx - shapes["px"]) * dx + (gy - shapes["py"]) * dy
        t = np.clip(np.divide(along, dx * dx + dy * dy, out=np.zeros_like(along),
                              where=(dx * dx + dy * dy) > 0), 0.0, 1.0)
        gap = np.hypot(shapes["px"] + t * dx - gx, shapes["py"] + t * dy - gy)
        return {"atoms": (form <= det).any(axis=0), "halves": (gap <= shapes["r"]).any(axis=0)}

    for i, box in enumerate(boxes):
        inner, outer = sampled(box, 0.0), sampled(box, 2.0)
        for kind in ("atoms", "halves"):
            assert not (inner[kind] & ~exact[kind][i]).any(), (kind, i)
            assert not (exact[kind][i] & ~outer[kind]).any(), (kind, i)
    for kind in ("atoms", "halves"):
        assert 20 < exact[kind].sum() < exact[kind].size - 20, kind


def test_keep_says_what_it_cut_and_the_report_repeats_it(nac):
    geometry = s3.build(nac)
    assert render_structure(geometry, size=200).report.cut == {"atoms": 0, "neighbours": 0, "segments": 0, "polyhedra": 0, "bonds": 0}
    from rietx.viz import keep, select
    species = geometry["sites"][0]["species"]
    some = keep(geometry, select(geometry, species=species))
    whole = keep(some, np.ones(len(some["atoms"]), dtype=bool))
    twice = keep(some, select(some, boundary=False))
    first = render_structure(some, size=200).report.cut
    assert first["bonds"] > 0
    # a cut that loses nothing adds nothing, and counts run over successive cuts
    assert render_structure(whole, size=200).report.cut == first
    both = render_structure(twice, size=200).report.cut
    assert both["bonds"] >= first["bonds"] and both["polyhedra"] >= first["polyhedra"]
    assert render_structure(twice, size=200).report.note == twice.get("note", "")


# ----------------------------------------------------------------------
# a cell past the atom cap (#665)
# ----------------------------------------------------------------------

@pytest.fixture(scope="module")
def hkust():
    """HKUST-1, Fm-3m at a = 26.27 Å: 648 atoms in the cell with its face
    copies, past the viewer's 400."""
    return structure_from_cif(str(DATA / "cod_4002052.cif"))


def test_a_trimmed_cell_is_counted_in_the_report(hkust):
    """``build``'s one cell trims to its cap, and the report counts what that
    cost.  It read ``cut {'polyhedra': 0, 'bonds': 0}``, ``dangling_bonds 0``
    and no warning over a picture of broken linkers; only ``note`` said it."""
    geometry = s3.build(hkust)
    assert geometry["n_cell"] == s3.MAX_ATOMS
    assert geometry["cut"] == {"atoms": 248, "neighbours": 96, "segments": 0, "polyhedra": 0}
    fig = render_structure(geometry, size=400)
    _save(fig, "cap_hkust1_trimmed")
    assert fig.report.cut["atoms"] == 248
    # the 96 neighbours outside the cell the cap left no room for: each bond
    # to one is drawn whole and ends on nothing
    assert fig.report.dangling_bonds == 96
    assert any("atom cap" in w and "248" in w and "max_atoms" in w
               for w in fig.report.warnings)
    # keep carries the cap's count through a cut of its own
    inside = keep(geometry, select(geometry, boundary=False))
    assert inside["cut"]["atoms"] == 248 and inside["cut"]["bonds"] > 0
    assert render_structure(inside, size=200).report.cut["atoms"] == 248


def test_polyhedra_the_cap_turned_away_are_a_warning(nac):
    """NAC's 90 atoms fit under 175, and some of its polyhedra's ligands do not."""
    small = s3.build(nac, max_atoms=175)
    assert small["cut"]["atoms"] == 0 and small["polyhedra_dropped"]
    warnings = render_structure(small, size=200).report.warnings
    n = len(small["polyhedra_dropped"])
    assert any(f"{n} coordination polyhedra" in w and "max_atoms" in w for w in warnings)


def test_a_cell_past_the_cap_raises_and_names_its_count(hkust):
    """From a structure the cell is drawn whole or not at all, the rule
    ``build(extent=...)`` keeps for a block."""
    with pytest.raises(ValueError, match="648 atoms.*max_atoms=400.*max_atoms=648"):
        render_structure(hkust, size=100)
    with pytest.raises(ValueError, match="max_atoms=647"):
        render_structure(hkust, size=100, max_atoms=647)


def test_a_cell_drawn_whole_has_no_stubs_and_replays(hkust):
    fig = render_structure(hkust, size=400, max_atoms=648)
    _save(fig, "cap_hkust1_whole")
    assert fig.report.cut == {"atoms": 0, "neighbours": 0, "segments": 0, "polyhedra": 0, "bonds": 0}
    assert fig.report.dangling_bonds == 0 and fig.report.warnings == []
    # the cap bounds the cell's own atoms; its bonded neighbours are drawn past it
    assert len(fig.atoms) > 648
    assert sum(not a["boundary"] for a in fig.atoms) == sum(
        s["multiplicity"] for s in s3.build(hkust, max_atoms=648)["sites"])
    assert fig.recipe["max_atoms"] == 648
    again = render_structure(hkust, **json.loads(json.dumps(fig.recipe)))
    assert np.array_equal(again.image, fig.image)


@pytest.mark.parametrize("value", [0, -5, 2.5, True, "648"])
def test_max_atoms_is_a_positive_whole_number(nac, value):
    with pytest.raises(ValueError, match="max_atoms"):
        render_structure(nac, size=100, max_atoms=value)


def test_max_atoms_is_refused_with_a_dict(nac):
    with pytest.raises(ValueError, match="max_atoms"):
        render_structure(s3.build(nac), size=100, max_atoms=1000)


def test_a_flat_ellipsoid_is_a_warning():
    geo = s3.build(_monoclinic(aniso=AnisoU.from_values([0.02, -0.01, -0.01, 0.0, 0.0, 0.0])))
    flat = render_structure(geo, mode="ellipsoid", size=200)
    assert any("C1" in w and "flat" in w for w in flat.report.warnings)
    assert render_structure(geo, mode="ball", size=200).report.warnings == []


def test_the_search_is_deterministic_and_returns_what_it_drew(nac):
    geometry = s3.build(nac)
    one = render_structure(geometry, view="auto", size=300)
    two = render_structure(geometry, view="auto", size=300)
    assert one.candidates == two.candidates and np.array_equal(one.image, two.image)
    assert len(one.candidates) == rp.N_CANDIDATES
    best = one.candidates[0]
    # the first candidate is the picture, and each is a view to pass back
    assert np.array_equal(render_structure(geometry, view=best["view"], size=300).image,
                          one.image)
    ranked = [(c["hidden"], c["empty"]) for c in one.candidates]
    assert ranked == sorted(ranked)
    assert render_structure(geometry, size=300).candidates == []
    with pytest.raises(ValueError, match="needs the scene"):
        views.resolve(geometry, "auto")


def test_of_a_direction_and_its_opposite_the_plainer_is_tried_first():
    """The two leave the same share empty and often hide the same atoms, so the
    order decides: fewer minus signs, then the first index positive."""
    order = [tuple(d) for d in rp.directions()]
    assert len(order) == 98 and order[:3] == [(0, 0, 1), (0, 1, 0), (1, 0, 0)]
    for k, d in enumerate(order):
        minus, other = sum(x < 0 for x in d), sum(x > 0 for x in d)
        plainer = minus < other or (minus == other and next(x for x in d if x) > 0)
        assert (order.index(tuple(-x for x in d)) > k) == plainer, d


@pytest.mark.parametrize("row", MEASURED, ids=[row["name"] for row in MEASURED])
def test_auto_never_hides_more_than_the_opening_view(row):
    """The search includes the opening view, and reads the numbers the report
    reads, so this is exact and not a tolerance."""
    geometry = s3.build(measured(row))
    opening = render_structure(geometry, view="opening", size=256)
    auto = render_structure(geometry, view="auto", size=256)
    assert auto.report.hidden <= opening.report.hidden
    assert auto.report.hidden == auto.candidates[0]["hidden"]


@pytest.mark.parametrize("kw", [
    {}, {"view": "auto"}, {"view": [1, 1, 0], "up": [0, 0, 1], "turn": "20x,-10y"},
    {"view": {"hkl": (1, 0, 0)}, "size": (300, 200), "background": (0.9, 0.9, 0.5)},
    {"mode": "ellipsoid", "hidden": "Na", "polyhedra": False, "supersample": 1},
    {"atom_labels": True, "outline": True, "background": None, "exaggeration": 1.5},
    {"stick": 0.5, "outline": True}])
def test_the_recipe_draws_the_same_picture_through_json(nac, kw):
    geometry = s3.build(nac)
    kw = dict(kw)
    fig = render_structure(geometry, size=kw.pop("size", 300), **kw)
    recipe = json.loads(json.dumps(fig.recipe))
    again = render_structure(geometry, **recipe)
    assert np.array_equal(again.image, fig.image)
    assert again.recipe == fig.recipe and again.report == fig.report
    assert "path" not in fig.recipe


@pytest.mark.parametrize("kw", [{"phase": 1}, {"mode": "ellipsoid", "probability": 0.9},
                                {"bond_tolerance": 0.05, "polyhedra": False}])
def test_the_recipe_redraws_from_a_structure_what_its_arguments_built(nac, kw):
    """From a structure, the phase and the geometry's two knobs are in the
    call; left out, the recipe drew phase 0 at the defaults.  Rutile's sticks
    all lie inside its octahedra, so the bond knob shows with them off."""
    rutile = _rutile()
    two = Structure(phases=[rutile.phases[0], nac.phases[0]])
    fig = render_structure(two, size=200, **kw)
    # the argument matters: without it the picture is another
    plain = render_structure(two, size=200, mode=kw.get("mode", "ball"),
                             polyhedra=kw.get("polyhedra"))
    assert not np.array_equal(plain.image, fig.image)
    again = render_structure(two, **json.loads(json.dumps(fig.recipe)))
    assert np.array_equal(again.image, fig.image)


def test_the_automatic_view_beside_the_opening_view():
    """The pictures the WP asks for, in tests/output/figure3d."""
    for name, geometry in (("rutile", s3.build(_rutile())),
                           ("fluorapatite", s3.build(structure_from_cif(
                               str(DATA / "fluorapatite.cif")))),
                           ("nac", s3.build(structure_from_cif(
                               str(DATA / "cod_1000236.cif"), aniso=True)))):
        opening = render_structure(geometry, view="opening", size=500)
        auto = render_structure(geometry, view="auto", size=500)
        _save(opening, f"report_{name}_opening")
        _save(auto, f"report_{name}_auto")
        assert auto.report.hidden <= opening.report.hidden


def test_hidden_may_be_a_generator_and_the_recipe_keeps_it(nac):
    """``hidden=`` read once for the recipe must still reach ``_species``."""
    listed = render_structure(nac, size=200, hidden=["Na"])
    lazy = render_structure(nac, size=200, hidden=(x for x in ["Na"]))
    assert lazy.recipe["hidden"] == ["Na"]
    assert len(lazy.atoms) == len(listed.atoms)
    assert np.array_equal(lazy.image, listed.image)


@pytest.mark.parametrize("kw, words", [({"turn": "30q"}, "turn term"),
                                       ({"up": "zzz"}, "unknown direction")])
def test_auto_names_a_bad_up_or_turn_as_the_plain_view_does(nac, kw, words):
    with pytest.raises(ValueError, match=words):
        render_structure(nac, view="auto", size=200, **kw)


# ----------------------------------------------------------------------
# the frame has a switch (WP-1533)
# ----------------------------------------------------------------------

def test_a_figure_without_its_frame_is_fitted_to_the_atoms(hkust):
    """Trial 1 of the promo take cut a 22 Å sphere from HKUST-1's 26 Å cell,
    and it drew at about a third of the frame until the script cleared
    ``edges`` by hand."""
    from rietx.viz import sphere

    g = s3.build(hkust, max_atoms=1000)
    middle = np.asarray(g["lattice"], dtype=np.float64).sum(axis=0) / 2
    ball = keep(g, sphere(g, middle.tolist(), 11.0))
    framed = render_structure(ball, size=400)
    bare = render_structure(ball, size=400, cell=False)
    _save(framed, "cell_hkust1_sphere_framed")
    _save(bare, "cell_hkust1_sphere_bare")
    accent = np.asarray(sc.rgb(TOKENS["light"]["--accent"])) * 255

    def ink(img):
        return (np.abs(img[..., :3].astype(float) - accent).max(-1) < 10).sum()

    assert ink(framed.image) > 200 and ink(bare.image) == 0
    assert bare.letters == [] and framed.letters
    # 8.5 against 16.4 px/Å, measured: the sphere fills the frame without its cell
    assert bare.pixels_per_angstrom > 1.8 * framed.pixels_per_angstrom
    assert bare.report.empty < framed.report.empty
    assert bare.recipe["cell"] is False
    again = render_structure(ball, **bare.recipe)
    assert np.array_equal(again.image, bare.image)


# ----------------------------------------------------------------------
# the stick has a width argument (WP-1533)
# ----------------------------------------------------------------------

def test_stick_one_is_the_default_bit_for_bit():
    molecule = _paracetamol()
    for mode in ("ball", "ellipsoid"):
        plain = render_structure(molecule, mode=mode, size=300, axis_labels=False)
        ones = render_structure(molecule, mode=mode, size=300, axis_labels=False, stick=1.0)
        assert np.array_equal(ones.image, plain.image)
        assert plain.recipe["stick"] == 1.0


def test_a_thinner_stick_halves_the_radius_and_replays():
    """At 100 K paracetamol's 50 % ellipsoids are small, and the promo take
    set ``scene.STICK_OF_SEMI_AXIS = 0.25`` by hand to thin the sticks, which
    a recipe could not carry.  ``stick=0.5`` is that setting."""
    molecule = _paracetamol()
    # 0.0723 Å against 0.0361 Å, measured: half the smallest drawn semi-axis
    # (0.1445 Å), and then half of that
    assert sc.stick_radius(molecule, "ellipsoid") == pytest.approx(0.07227, abs=1e-5)
    assert sc.stick_radius(molecule, "ellipsoid", stick=0.5) == (
        0.5 * sc.stick_radius(molecule, "ellipsoid"))
    assert sc.stick_radius(molecule, "ball", stick=0.5) == 0.5 * sc.STICK_RADIUS
    thick = render_structure(molecule, mode="ellipsoid", size=600, axis_labels=False)
    thin = render_structure(molecule, mode="ellipsoid", size=600, axis_labels=False,
                            stick=0.5)
    _save(thick, "stick_paracetamol_ellipsoid_1")
    _save(thin, "stick_paracetamol_ellipsoid_0.5")
    # the atoms and the frame are the same, so every pixel lost is a stick's
    assert thin.pixels_per_angstrom == thick.pixels_per_angstrom
    assert thin.atoms == thick.atoms

    def inked(img):
        return int((img[..., :3] != 255).any(-1).sum())

    assert inked(thin.image) < inked(thick.image)
    assert thin.recipe["stick"] == 0.5
    again = render_structure(molecule, **json.loads(json.dumps(thin.recipe)))
    assert np.array_equal(again.image, thin.image) and again.report == thin.report


@pytest.mark.parametrize("value", [0, -0.5, float("nan"), float("inf"), True, "0.5"])
def test_stick_is_a_positive_finite_number(value):
    with pytest.raises(ValueError, match="stick"):
        render_structure(_paracetamol(), size=100, stick=value)


# ----------------------------------------------------------------------
# an axis view stacks a site behind itself, and the report says so (WP-1533)
# ----------------------------------------------------------------------

def test_an_axis_view_stacks_rather_than_hides(hkust, nac):
    """The skill's rule sent an agent asked for an axis view to ``auto``,
    because ``hidden`` counts an atom behind a copy of its own site.  Down a
    cell axis that is the projection, and the copy in front draws it."""
    ybco = structure_from_cif(str(DATA / "cod_9007744.cif"))
    down_b = render_structure(ybco, view="b", size=400)
    assert down_b.report.hidden == down_b.report.stacked == 1.0
    down_a = render_structure(hkust, view="a", size=400, max_atoms=1000)
    _save(down_a, "stacked_hkust1_down_a")
    assert down_a.report.hidden > 0.5
    assert down_a.report.stacked == pytest.approx(down_a.report.hidden)
    # an oblique view of NAC hides atoms behind other sites: occlusion, not stacking
    opening = render_structure(nac, size=400)
    assert 0.0 <= opening.report.stacked < opening.report.hidden
    for fig in (down_b, down_a, opening):
        assert 0.0 <= fig.report.stacked <= fig.report.hidden
