"""WP-1538: ambient occlusion measured on the 21 phases of WP-1466.

    .venv/bin/python docs/wp/1538-measure/measure.py [CACHE] [--pairs] [--cost] [--maps]

Run from the repository root.  The phases are ``1466-measure/measure.py``'s,
fetched from the Crystallography Open Database into CACHE once (default:
``rietx-1466-cod`` in the system temp directory, the cache that script
fills), read here with their anisotropic displacements so ellipsoid mode draws
ellipsoids.  Every row is the default scene of ``render_structure`` in the
opening view.

**Darkening.**  Each pixel of a 400 px id plane (``raster.id_plane``, one
sample a pixel) that an atom or a stick holds gets its surface point and
normal, and :func:`raster.occlusion` reads its unoccluded share A from the
scene's maps.  The table quotes 1 − A, the share of ambient light lost, over
atom pixels and over stick pixels: the mean and the 95th percentile.  The
filing's analytic estimate (``ao_probe.py``) is the atom column's.

``--maps`` repeats the atom column at map sizes 256, 512 and 1024 and depth
biases 0.005, 0.01 and 0.02, to choose D2's constants.

``--cost`` times ``render_structure`` in ball mode at 1000 and 3000 px, plain
(the process's path, the wheel where it loaded) and occluded (the maps, then
the numpy path, which is the only one that draws occlusion so far), and the
maps alone.

``--pairs`` writes ``pairs/<phase>.png``: ball mode above ellipsoid mode,
plain on the left and occluded on the right, 320 px each.
"""

from __future__ import annotations

import functools
import importlib.util
import re
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

from rietx.crystallography import cif as cif_module
from rietx.gui import structure3d as s3
from rietx.viz import render_structure
from rietx.viz.figure3d import raster, views
from rietx.viz.figure3d import scene as sc
from rietx.viz.figure3d.render import _png, gui_frame

HERE = Path(__file__).resolve().parent
SIDE = 400


def phases():
    """1466's phase list and loader, reading U_ij."""
    spec = importlib.util.spec_from_file_location(
        "m1466", HERE.parent / "1466-measure" / "measure.py")
    m1466 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m1466)
    m1466.structure_from_cif = functools.partial(cif_module.structure_from_cif, aniso=True)
    return m1466.PHASES, m1466.load


def scene_of(geometry, mode):
    return sc.build_scene(geometry, mode, polyhedra=sc.shown_polyhedra(geometry, mode == "ball"))


def shares(scene, R, maps):
    """1 − A at every atom pixel and every stick pixel of a SIDE px id plane."""
    frame = gui_frame(scene, R, SIDE, SIDE, SIDE)
    pk = raster.pack_ids(raster.scene_arrays(scene), R)
    ids = raster.id_plane(pk, frame).ids
    depth = raster._depths(pk, frame, ids)
    iy, ix = np.nonzero(ids >= 0)
    k = ids[iy, ix].astype(np.int64)
    sx = frame.x0 + (ix + 0.5) / frame.ppa
    sy = frame.y0 - (iy + 0.5) / frame.ppa
    p = np.stack([sx, sy, depth[iy, ix]], axis=1)
    n = np.zeros_like(p)
    na = len(pk["atom_c"])
    on = k < na
    m = pk["atom_m"][k[on]]
    c = pk["atom_c"][k[on]]
    u = np.einsum("nij,nj->ni", m, p[on] - c)            # the point on the unit sphere
    n[on] = np.einsum("nji,nj->ni", m, u)                 # Mᵀu, as _band_numpy shades
    h = k[~on] - na
    a, w = pk["half_a"][h], pk["half_w"][h]
    rel = p[~on] - a
    n[~on] = rel - (rel * w).sum(axis=1)[:, None] * w     # the part off the axis
    n /= np.linalg.norm(n, axis=1)[:, None]
    lost = 1.0 - raster.occlusion(maps, p @ R, n @ R)
    return lost[on], lost[~on]


def stats(x):
    return (f"{100 * x.mean():5.1f} ({100 * np.percentile(x, 95):4.1f})" if len(x)
            else "    -       ")


def main(cache: Path, pairs: bool, cost: bool, maps_study: bool) -> None:
    table, load = phases()
    cache.mkdir(parents=True, exist_ok=True)
    print("1 - A in %, mean (p95), over a 400 px id plane of the opening view")
    print(f"{'phase':28s} {'ball atoms':>13s} {'ball sticks':>13s} "
          f"{'ell. atoms':>13s} {'ell. sticks':>13s}")
    costs = []
    for name in table:
        structure = load(name, cache)
        geometry = s3.build(structure)
        R = views.resolve(geometry, "opening", None, None)
        row = []
        for mode in ("ball", "ellipsoid"):
            scene = scene_of(geometry, mode)
            atoms, sticks = shares(scene, R, raster.occlusion_maps(scene))
            row += [stats(atoms), stats(sticks)]
        print(f"{name:28s} " + " ".join(f"{v:>13s}" for v in row), flush=True)
        if maps_study:
            scene = scene_of(geometry, "ball")
            cells = []
            for size, bias in ((256, 0.01), (512, 0.01), (1024, 0.01), (512, 0.005),
                               (512, 0.02)):
                atoms, _ = shares(scene, R, raster.occlusion_maps(scene, size=size, bias=bias))
                cells.append(f"{size}/{bias}: {100 * atoms.mean():4.1f}")
            print(f"{'':28s} ball atoms by map size/bias  " + "  ".join(cells), flush=True)
        if pairs:
            rows = []
            for mode in ("ball", "ellipsoid"):
                plain = render_structure(structure, mode=mode, size=320).image
                lit = render_structure(structure, mode=mode, size=320,
                                       ambient_occlusion=True).image
                h = max(plain.shape[0], lit.shape[0])
                w = plain.shape[1] + lit.shape[1]
                both = np.full((h, w, 4), 255, dtype=np.uint8)
                both[:plain.shape[0], :plain.shape[1]] = plain
                both[:lit.shape[0], plain.shape[1]:] = lit
                rows.append(both)
            w = max(r.shape[1] for r in rows)
            out = np.full((sum(r.shape[0] for r in rows), w, 4), 255, dtype=np.uint8)
            y = 0
            for r in rows:
                out[y:y + r.shape[0], :r.shape[1]] = r
                y += r.shape[0]
            (HERE / "pairs").mkdir(exist_ok=True)
            slug = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_")
            _png(HERE / "pairs" / f"{slug}.png", out, None)
        if cost:
            render_structure(structure, size=200)             # compile, warm caches
            line = []
            for size in (1000, 3000):
                t = time.perf_counter()
                render_structure(structure, size=size)
                plain = time.perf_counter() - t
                t = time.perf_counter()
                render_structure(structure, size=size, ambient_occlusion=True)
                lit = time.perf_counter() - t
                line.append((plain, lit))
            t = time.perf_counter()
            raster.occlusion_maps(scene_of(geometry, "ball"))
            line.append(time.perf_counter() - t)
            costs.append((name, line))
            print(f"{'':28s} cost: 1000 px {line[0][0]:.2f} s plain, {line[0][1]:.2f} s "
                  f"occluded; 3000 px {line[1][0]:.2f} s, {line[1][1]:.2f} s; "
                  f"maps {line[2]:.2f} s", flush=True)
    if costs:
        for k, size in ((0, 1000), (1, 3000)):
            plain = [c[1][k][0] for c in costs]
            lit = [c[1][k][1] for c in costs]
            print(f"{size} px: plain {min(plain):.2f}-{max(plain):.2f} s, occluded "
                  f"{min(lit):.2f}-{max(lit):.2f} s")
        maps = [c[1][2] for c in costs]
        print(f"maps: {min(maps):.2f}-{max(maps):.2f} s")


if __name__ == "__main__":
    flags = {a for a in sys.argv[1:] if a.startswith("--")}
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    main(Path(args[0]) if args else Path(tempfile.gettempdir()) / "rietx-1466-cod",
         "--pairs" in flags, "--cost" in flags, "--maps" in flags)
