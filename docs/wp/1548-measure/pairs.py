"""WP-1548 task 6: before-and-after sheets for the depth cue and the filled rings.

Each phase gets one sheet of four tiles drawn by ``render_structure`` at the
opening view, ball mode and its default polyhedra: as shipped, with
``depth_cue=True``, with ``planar_rings=True``, and with both.  A phase with
rings is drawn as a block, since the one-cell drawing closes no ring a cell
edge cuts.  Then the four look questions get a sheet each:

* ``fog_max``: 0.5, 0.7 (the provisional value) and 0.9 on one phase;
* D6: the cue on a white and a black ground beside the boundary shade;
* D5: the grey default against a colour given and the carbon colour;
* D3: the refusal, written out, of a transparent ground.

The 21 phases are WP-1466's set (``docs/wp/1466-measure/measure.py``), 18 of
them COD entries fetched into ``--cache``; an entry the network refuses is
listed and skipped, never drawn from a stand-in.  Paracetamol and the other
organic CIFs in ``tests/data`` are added for the rings.

    .venv/bin/python docs/wp/1548-measure/pairs.py [--cache=DIR]

writes ``docs/wp/1548-measure/pairs/*.png`` and prints one line a sheet.
"""

from __future__ import annotations

import importlib.util
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.viz import render_structure
from rietx.viz.figure3d import rings
from rietx.viz.figure3d import scene as sc
from rietx.viz.figure3d.render import _png

warnings.simplefilter("ignore")
HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
OUT = HERE / "pairs"
TILE = 420
GAP = 8

#: the organic phases on disk, drawn as a block so their rings close
ORGANIC = {
    "paracetamol": "cod_2104364.cif",
    "acridine": "cod_2242872.cif",
    "C16H26 (chairs)": "cod_1550439.cif",
    "cod_1567181": "cod_1567181.cif",
    "cod_7252065": "cod_7252065.cif",
    "HKUST-1": "cod_4002052.cif",
}
BLOCK = ((0, 2), (0, 2), (0, 2))


def _measure_module():
    spec = importlib.util.spec_from_file_location(
        "measure_1466", REPO / "docs" / "wp" / "1466-measure" / "measure.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sheet(tiles: list[np.ndarray]) -> np.ndarray:
    h = max(t.shape[0] for t in tiles)
    w = sum(t.shape[1] for t in tiles) + GAP * (len(tiles) - 1)
    out = np.full((h, w, 4), 255, dtype=np.uint8)
    x = 0
    for t in tiles:
        out[:t.shape[0], x:x + t.shape[1]] = t
        x += t.shape[1] + GAP
    return out


def _slug(name: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in name).strip("_").lower()


def four(name: str, drawn) -> str:
    """Shipped, cued, rings, both: one sheet."""
    kw = dict(size=TILE, view="opening")
    tiles = [render_structure(drawn, **kw).image,
             render_structure(drawn, depth_cue=True, **kw).image,
             render_structure(drawn, planar_rings=True, **kw).image,
             render_structure(drawn, depth_cue=True, planar_rings=True, **kw).image]
    _png(OUT / f"{_slug(name)}.png", _sheet(tiles), None)
    geometry = drawn if isinstance(drawn, dict) else s3.build(drawn)
    return f"{name}: {len(geometry['atoms'])} atoms, {len(rings.planar_rings(geometry))} planar rings"


def main(cache: Path) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    measure = _measure_module()
    cache.mkdir(parents=True, exist_ok=True)
    refused = []
    for name in measure.PHASES:
        try:
            structure = measure.load(name, cache)
        except Exception as exc:  # noqa: BLE001 - the network is reported, not hidden
            refused.append(f"{name} ({type(exc).__name__})")
            continue
        print(four(name, structure))
    blocks = {}
    for name, cif in ORGANIC.items():
        blocks[name] = s3.build(structure_from_cif(str(REPO / "tests" / "data" / cif)),
                                extent=BLOCK, max_atoms=6000)
        print(four(name, blocks[name]))

    para = blocks["paracetamol"]
    kw = dict(size=TILE, view="opening")
    # fog_max: the provisional 0.7 between a lighter and a heavier ramp
    tiles, was = [], sc.LOOK["fog_max"]
    try:
        for f in (0.5, 0.7, 0.9):
            sc.LOOK["fog_max"] = f
            tiles.append(render_structure(para, depth_cue=True, **kw).image)
    finally:
        sc.LOOK["fog_max"] = was
    _png(OUT / "q_fog_max_0.5_0.7_0.9.png", _sheet(tiles), None)
    # D6: the cue and the boundary shade on both grounds, NAC in one cell
    nac = structure_from_cif(str(REPO / "tests" / "data" / "cod_1000236.cif"))
    tiles = [render_structure(nac, background=bg, depth_cue=cue, **kw).image
             for bg in ("white", "black") for cue in (False, True)]
    _png(OUT / "q_d6_white_black_plain_cued.png", _sheet(tiles), None)
    # D5: grey, a given colour, and carbon's own colour
    carbon = next(s["color"] for s in para["sites"] if s["element"] == "C")
    tiles = [render_structure(para, planar_rings=c, **kw).image
             for c in (True, "#3a7d44", carbon)]
    _png(OUT / "q_d5_grey_green_carbon.png", _sheet(tiles), None)
    print("questions: fog_max, D6, D5 sheets written")
    try:
        render_structure(para, depth_cue=True, background=None, size=60)
    except ValueError as exc:
        print(f"D3, background=None with the cue: refused: {exc}")
    if refused:
        print(f"not drawn, the fetch refused: {len(refused)}: {', '.join(refused)}")


if __name__ == "__main__":
    args = [a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--cache=")]
    main(Path(args[0]) if args else Path(tempfile.gettempdir()) / "rietx-1548-cod")
