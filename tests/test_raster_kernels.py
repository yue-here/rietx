"""The ``rietx_kernels`` rasteriser draws its numpy oracle's bits.

``kernels/src/raster.rs`` holds the structure figure's two kernels,
``render_rows`` and ``id_plane`` (WP-1940, ``rietx-kernels`` 1.1.0), and
``render_rows_cued``, ``render_rows`` with depth cueing (WP-1548, 1.5.0).  Their
oracle is :mod:`rietx.viz.figure3d.raster`'s ``_band_numpy`` and
``_ids_numpy``.  Neither calls a library function, so the bar is the bit on
every platform.

Each comparison runs inside a real render.  The oracle draws a band or an id
frame, and the wheel draws the same one from the same arrays beside it.  So
every render here runs with the compiled tier switched off, which makes the
oracle the path that draws.  The
renders are chosen so that every arm of ``render_rows`` runs, and the test
asserts that each one did: atoms with and without rings, bond halves, the
outline, cell and polyhedron lines, faces, letters, and both an opaque and a
transparent background.  The cued kernel is held to the same oracle drawing
with its ``fog``, over renders reaching every arm that fogs: atoms, bond
halves, lines, the outline and faces, under letters that it must not fog.

The second half is the refusals, built as in ``test_rietx_kernels.py``: one
well-formed call taken from a real render, then one defect at a time.

``kernels.yml`` runs this file on each wheel platform.  Under a wheel older
than 1.1.0 it skips, and its cued half under one older than 1.5.0.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from rietx.crystallography.cif import structure_from_cif
from rietx.model import compiled
from rietx.viz import render_structure
from rietx.viz.figure3d import raster

rk = pytest.importorskip("rietx_kernels")
if not hasattr(rk, "render_rows"):
    pytest.skip(f"rietx_kernels {rk.__version__} predates the rasteriser",
                allow_module_level=True)

DATA = Path(__file__).parent / "data"

needs_cued = pytest.mark.skipif(not hasattr(rk, "render_rows_cued"),
                                reason=f"rietx_kernels {rk.__version__} predates "
                                       "render_rows_cued")


@pytest.fixture(scope="module")
def nac():
    return structure_from_cif(str(DATA / "cod_1000236.cif"), aniso=True)


@pytest.fixture(autouse=True)
def oracle_path():
    """The numpy path for every render, so ``_band_numpy`` and ``_ids_numpy``
    run and the wheel is called beside them."""
    was = compiled.set_enabled(False)
    yield
    compiled.set_enabled(was)


def _wheel_band(r0, r1, s, frame, pk, alpha, bg, outline, out, fog=None):
    """``render_rows``, or ``render_rows_cued`` given a fog, called with
    ``_band_numpy``'s arguments."""
    ow, otau, ocol = outline
    args = (r0, r1, s, frame.height, frame.x0, frame.y0, frame.ppa * s, frame.width,
            pk["look"], alpha, None if bg is None else np.asarray(bg, dtype=np.float64),
            ow, otau, ocol, pk["atom"], pk["half"], pk["line"], pk["tri"], pk["text"])
    if fog is None:
        rk.render_rows(*args, out)
    else:
        rk.render_rows_cued(*args, *fog, out)


def _wheel_ids(pk, frame, atom_box, half_box, ids, seen):
    """``id_plane`` called with ``_ids_numpy``'s arguments."""
    rk.id_plane(frame.y0, frame.x0, frame.ppa,
                (pk["atom_c"], pk["atom_m"], pk["atom_a"], atom_box),
                (pk["half_a"], pk["half_w"], pk["half_len"], pk["half_e"], pk["half_ea"],
                 pk["half_r"], half_box), ids, seen)


@pytest.fixture
def shadow(monkeypatch):
    """Run the wheel beside the oracle on every band and id frame a render
    draws; record each disagreement and which arms the bands reached."""
    seen = {"bands": 0, "frames": 0, "differ": [], "arms": set()}
    band, ids = raster._band_numpy, raster._ids_numpy

    def band_twice(r0, r1, s, frame, pk, alpha, bg, outline, out, fog=None):
        band(r0, r1, s, frame, pk, alpha, bg, outline, out,
             **({} if fog is None else {"fog": fog}))
        mine = np.zeros_like(out)
        _wheel_band(r0, r1, s, frame, pk, alpha, bg, outline, mine, fog)
        seen["bands"] += 1
        if not np.array_equal(mine[r0:r1], out[r0:r1]) or mine[:r0].any() or mine[r1:].any():
            seen["differ"].append(("band", r0, r1))
        _, _, _, _, lum, ring, _ = pk["atom"]
        arms = {"atom": len(lum) > 0, "half": len(pk["half"][0]) > 0,
                "line": len(pk["line"][0]) > 0, "tri": len(pk["tri"][0]) > 0,
                "text": len(pk["text"][0]) > 0, "outline": outline[0] > 0,
                "opaque": bg is not None, "transparent": bg is None,
                "ring lightens": bool((ring & (lum < pk["look"][9])).any()),
                "ring darkens": bool((ring & ~(lum < pk["look"][9])).any()),
                "fog": fog is not None}
        seen["arms"] |= {k for k, v in arms.items() if v}

    def ids_twice(pk, frame, atom_box, half_box, ids_, seen_):
        ids(pk, frame, atom_box, half_box, ids_, seen_)
        mine, mine_seen = np.full_like(ids_, -1), np.zeros_like(seen_)
        _wheel_ids(pk, frame, atom_box, half_box, mine, mine_seen)
        seen["frames"] += 1
        if not (np.array_equal(mine, ids_) and np.array_equal(mine_seen, seen_)):
            seen["differ"].append(("frame", seen["frames"]))

    monkeypatch.setattr(raster, "_band_numpy", band_twice)
    monkeypatch.setattr(raster, "_ids_numpy", ids_twice)
    return seen


ALL_ARMS = {"atom", "half", "line", "tri", "text", "outline", "opaque", "transparent",
            "ring lightens", "ring darkens"}


def test_every_band_is_the_oracles_bits(nac, shadow):
    """Whole renders, then the same scenes cut into dozens of bands, so the
    outline's halo crosses band boundaries."""
    for kw in ({"mode": "ball", "polyhedra": True, "atom_labels": True},
               {"mode": "ellipsoid", "background": None, "outline": True, "polyhedra": True,
                "atom_labels": True}):
        render_structure(nac, size=240, **kw)
        whole = shadow["bands"]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(raster, "BAND_SAMPLES", 2000)
            render_structure(nac, size=240, **kw)
        assert shadow["bands"] - whole > 10
    assert shadow["differ"] == []
    assert shadow["arms"] == ALL_ARMS


@needs_cued
def test_every_cued_band_is_the_oracles_bits(nac, shadow):
    """``render_rows_cued`` against ``_band_numpy`` drawing with the fog
    ``render_structure(depth_cue=True)`` computes, the span the drawn atoms
    cover: atoms, halves, cell and polyhedron lines, the outline and the faces
    all fog, under letters that do not; whole, then in dozens of bands."""
    for kw in ({"mode": "ball", "polyhedra": True, "atom_labels": True, "outline": True},
               {"mode": "ellipsoid", "polyhedra": True, "outline": True,
                "background": "black", "atom_labels": True}):
        render_structure(nac, size=240, depth_cue=True, **kw)
        whole = shadow["bands"]
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(raster, "BAND_SAMPLES", 2000)
            render_structure(nac, size=240, depth_cue=True, **kw)
        assert shadow["bands"] - whole > 10
    assert shadow["differ"] == []
    assert shadow["arms"] == ALL_ARMS - {"transparent"} | {"fog"}


def test_every_id_frame_is_the_oracles(nac, shadow):
    """``view="auto"`` runs the id pass once a candidate view."""
    render_structure(nac, size=160, view="auto")
    assert shadow["frames"] > 50
    assert shadow["differ"] == []


# --- the refusals ------------------------------------------------------


def _first_band(nac, monkeypatch, **kw):
    """The first band of a render reaching every primitive, as a call by
    keyword drawn into a fresh picture, and the fog it was drawn under."""
    got = []

    def keep(r0, r1, s, frame, pk, alpha, bg, outline, out, fog=None):
        got.append((dict(r0=r0, r1=r1, s=s, height=frame.height, x0=frame.x0, y0=frame.y0,
                         pxs=frame.ppa * s, width=frame.width, look=pk["look"], alpha=alpha,
                         bg=np.asarray(bg, dtype=np.float64), ow=outline[0], otau=outline[1],
                         ocol=outline[2], atom=pk["atom"], half=pk["half"], line=pk["line"],
                         tri=pk["tri"], text=pk["text"], out=np.zeros_like(out)), fog))

    monkeypatch.setattr(raster, "_band_numpy", keep)
    render_structure(nac, size=64, polyhedra=True, atom_labels=True, outline=True, **kw)
    return got[0]


@pytest.fixture
def call(nac, monkeypatch):
    """A well-formed ``render_rows`` call by keyword."""
    return _first_band(nac, monkeypatch)[0]


@pytest.fixture
def cued_call(nac, monkeypatch):
    """A well-formed ``render_rows_cued`` call by keyword, its fog the one
    ``render_structure(depth_cue=True)`` drew the band under."""
    c, fog = _first_band(nac, monkeypatch, depth_cue=True)
    z_start, z_end, f_max, colour = fog
    return {**c, "z_start": z_start, "z_end": z_end, "f_max": f_max, "fog_colour": colour}


def _with(group, k, a):
    """``call``'s ``group`` tuple with its ``k``-th array replaced."""
    def apply(c):
        t = list(c[group])
        t[k] = a(t[k])
        c[group] = tuple(t)
    return apply


def _bg_in_out(c):
    """``bg`` as a view of the picture's own bytes."""
    c["bg"] = c["out"].reshape(-1).view(np.float64)[:3]


RENDER_DEFECTS = {
    "out misshapen": (lambda c: c.update(out=np.zeros((c["height"], c["width"] + 1, 4),
                                                      dtype=np.uint8)), "out has shape"),
    "read-only out": (lambda c: c["out"].setflags(write=False), "out must be writeable"),
    "rows past the picture": (lambda c: c.update(r1=c["height"] + 1), "rows 0"),
    "no samples": (lambda c: c.update(s=0), "s must be at least 1"),
    "samples past the planes": (lambda c: c.update(s=1 << 40), "overflows its sample planes"),
    "an outline past 2^30": (lambda c: c.update(ow=1 << 30), "past 2"),
    "look short": (lambda c: c.update(look=c["look"][:-1].copy()), "look has 11"),
    "background of two": (lambda c: c.update(bg=np.ones(2)), "bg has 2"),
    "bg inside out": (_bg_in_out, "shares memory"),
    "an atom array short": (_with("atom", 1, lambda a: a[:-1].copy()),
                            "atom: atom_m has"),
    "a half box of three": (_with("half", 7, lambda a: a[:, :3].copy()),
                            "half_box has shape"),
    "Fortran-ordered faces": (_with("tri", 2, np.asfortranarray),
                              "tri_tie must be C-contiguous"),
    "a letter array short": (_with("text", 4, lambda a: a[:-1].copy()), "text: z has"),
}


def _fog_colour_in_out(c):
    """``fog_colour`` as a view of the picture's own bytes."""
    c["fog_colour"] = c["out"].reshape(-1).view(np.float64)[:3]


#: The cued kernel's own arguments, refused by name, a fog ending in front of
#: its start as ``raster.draw`` refuses it.
FOG_DEFECTS = {
    "fog colour of two": (lambda c: c.update(fog_colour=np.ones(2)), "fog_colour has 2"),
    "fog colour strided": (lambda c: c.update(fog_colour=np.ones(6)[::2]),
                           "fog_colour must be C-contiguous"),
    "fog colour inside out": (_fog_colour_in_out, "shares memory"),
    "fog ending in front": (lambda c: c.update(z_end=c["z_start"] + 1.0),
                            "not in front of"),
    "fog of no depth": (lambda c: c.update(z_end=c["z_start"]), "not in front of"),
    "fog starting at NaN": (lambda c: c.update(z_start=float("nan")), "not in front of"),
}


def test_the_well_formed_call_writes_its_rows_and_no_others(call):
    rk.render_rows(**call)
    out, r0, r1 = call["out"], call["r0"], call["r1"]
    assert out[r0:r1, :, 3].any()
    assert not out[:r0].any() and not out[r1:].any()


@needs_cued
def test_the_cued_call_fogs_its_rows_and_at_no_fog_draws_render_rows(cued_call):
    """The same band three ways: fogged, which moves it; at ``f_max = 0``,
    which is ``render_rows``' picture to the bit; and touching no other row."""
    plain = {k: v for k, v in cued_call.items()
             if k not in ("z_start", "z_end", "f_max", "fog_colour")}
    plain["out"] = np.zeros_like(cued_call["out"])
    rk.render_rows(**plain)
    rk.render_rows_cued(**cued_call)
    out, r0, r1 = cued_call["out"], cued_call["r0"], cued_call["r1"]
    assert out[r0:r1, :, 3].any()
    assert not out[:r0].any() and not out[r1:].any()
    assert not np.array_equal(out, plain["out"])
    clear = {**cued_call, "f_max": 0.0, "out": np.zeros_like(out)}
    rk.render_rows_cued(**clear)
    assert np.array_equal(clear["out"], plain["out"])


@pytest.mark.parametrize("defect", RENDER_DEFECTS)
def test_one_defect_is_refused_by_name(call, defect):
    assert len(call["tri"][0]) > 1 and len(call["text"][0]) > 1
    apply, says = RENDER_DEFECTS[defect]
    apply(call)
    with pytest.raises(ValueError, match=says):
        rk.render_rows(**call)


@needs_cued
@pytest.mark.parametrize("defect", [*RENDER_DEFECTS, *FOG_DEFECTS])
def test_one_defect_is_refused_by_name_when_cued(cued_call, defect):
    """The cued kernel shares ``render_rows``' checks and adds its fog's."""
    assert len(cued_call["tri"][0]) > 1 and len(cued_call["text"][0]) > 1
    apply, says = {**RENDER_DEFECTS, **FOG_DEFECTS}[defect]
    apply(cued_call)
    with pytest.raises(ValueError, match=says):
        rk.render_rows_cued(**cued_call)


def test_the_id_pass_refuses_a_count_or_an_order_it_cannot_index(nac, monkeypatch):
    got = []
    monkeypatch.setattr(raster, "_ids_numpy", lambda *a: got.append(a))
    render_structure(nac, size=64, view="auto")
    pk, frame, atom_box, half_box, ids, seen = got[0]
    _wheel_ids(pk, frame, atom_box, half_box, ids, seen)
    assert (ids >= 0).any() and seen.any()
    with pytest.raises(ValueError, match="seen has"):
        _wheel_ids(pk, frame, atom_box, half_box, ids, seen[:-1].copy())
    with pytest.raises(ValueError, match="ids must be C-contiguous"):
        _wheel_ids(pk, frame, atom_box, half_box, np.asfortranarray(ids), seen)
    with pytest.raises(ValueError, match="half: half_r has"):
        pk = {**pk, "half_r": pk["half_r"][:-1].copy()}
        _wheel_ids(pk, frame, atom_box, half_box, ids, seen)
