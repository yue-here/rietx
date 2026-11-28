"""Draw a scene from a view into an RGBA array, on the CPU (WP-1470 D1, D5-D7).

The scene is :func:`.scene.build_scene`'s, the GUI's own, and the drawing is
the GUI's renderer (``gui/src/lib/gl3d.ts``) solved per sample instead of per
fragment: every atom an exact ellipsoid, every bond half an open cylinder, the
cell frame and polyhedron edges as segments with a width in pixels, all
depth-tested; then the polyhedron faces, blended back to front and writing no
depth; then the letters, over everything.  The GUI's `LEQUAL` depth test is
kept, so of two surfaces at one depth the later drawn wins.

**Antialiasing is supersampling** (D5): ``s × s`` samples a pixel, a box
filter, rounding to the nearest level.  The GUI's analytic edge coverage does
not compose in a z-buffer, where the surface behind an edge may be drawn later.

**The output is straight alpha over nothing** until a background is asked for
(D7).  Every sample holds premultiplied colour and coverage; a pixel's alpha is
the mean coverage and its colour the mean over what covered it, so an edge on a
transparent background carries no fringe of any background colour.  With a
background the same sums are composited over it, which is the same picture the
GUI draws on an opaque canvas.

**Two paths, one picture.**  The wheel's ``render_rows``
(``kernels/src/raster.rs``, ``rietx-kernels`` from 1.1.0) draws a band of rows,
and the bands spread over the compiled tier's shared pool; a fogged picture
calls its twin ``render_rows_cued`` (from 1.5.0, WP-1548) the same way.
:func:`_band_numpy` is the same arithmetic vectorised over each primitive's box.  It is the oracle
the kernel is held to, and the path wherever the wheel did not load.  Neither
calls a library function: ``sqrt`` is an IEEE operation, the specular power is
repeated squaring, and the box filter adds the samples in one order.  So the
bar is the bit, and ``tests/test_raster_kernels.py`` asserts it inside real
renders, for this function and :func:`_ids_numpy` alike.  Which path runs is
``model.compiled.enabled()``, one path a process, and ``RIETX_COMPILED=0`` is
the switch.  A numba kernel held this place until WP-1940.

**An id pass** (:func:`id_plane`, WP-1503) runs the same two tests over a small
frame and writes which atom or bond half is in front at each pixel, for the
figure's report of what it hides.  It packs its own arrays, vectorised
(:func:`pack_ids`), because ``_pack``'s per-primitive loop costs more than the
pass and a view search runs the pass a hundred times.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from ...model import compiled
from .scene import LOOK, POLY_ALPHA

#: A band holds at most this many samples, so a 3000 px render at 4×4 never
#: holds its 12000 px sample plane (D5); about 40 MB of band buffers a thread.
BAND_SAMPLES = 1 << 20


def _kernel(name: str):
    """The wheel's kernel ``name``, or ``None`` for the numpy path.

    The path is the process's, :func:`~rietx.model.compiled.enabled`, and a
    test switches it with :func:`~rietx.model.compiled.set_enabled`.  Forced on
    where the wheel did not load, it runs numpy, as the model's entry points do.
    """
    kernels = compiled._kernels() if compiled.enabled() else None
    return None if kernels is None else kernels[name]


@dataclass
class Frame:
    """Where the image sits in the view: ``x0``, ``y0`` are the view
    coordinates (Å) of its top-left corner, ``ppa`` its pixels per Å, and
    ``px_scale`` how many image pixels one of the GUI's CSS pixels is."""
    width: int
    height: int
    x0: float
    y0: float
    ppa: float
    px_scale: float


def _box(lo_x, hi_x, lo_y, hi_y, hs, ws):
    """Sample rows and columns ``[iy0, iy1) × [ix0, ix1)`` a primitive may
    reach, one sample wider than its exact extent on every side."""
    return (max(math.floor(lo_y) - 1, 0), min(math.ceil(hi_y) + 1, hs),
            max(math.floor(lo_x) - 1, 0), min(math.ceil(hi_x) + 1, ws))


def _segments(points, halves, colors, depths, hs, ws):
    """Pack segments given in sample coordinates (u right, v down)."""
    n = len(points)
    p = np.zeros((n, 4))
    half = np.zeros(n)
    direction = np.zeros((n, 2))
    length = np.zeros(n)
    z = np.zeros((n, 2))
    col = np.zeros((n, 3))
    box = np.zeros((n, 4), dtype=np.int64)
    for i, ((au, av, bu, bv), h) in enumerate(zip(points, halves)):
        du, dv = bu - au, bv - av
        d = math.hypot(du, dv)
        # the GUI's fallback for a segment seen end on: a square
        direction[i] = (du / d, dv / d) if d > 1e-6 else (1.0, 0.0)
        length[i] = d if d > 1e-6 else 0.0
        p[i] = (au, av, bu, bv)
        half[i] = h
        z[i] = depths[i]
        col[i] = colors[i]
        box[i] = _box(min(au, bu) - h, max(au, bu) + h, min(av, bv) - h,
                      max(av, bv) + h, hs, ws)
    return p, half, direction, length, z, col, box


def _pack(scene: dict, rotation: np.ndarray, frame: Frame, s: int,
          text: list | None = None) -> dict:
    """The arrays both paths draw from, computed once, in float64.

    Positions are in view coordinates, ``R·p``, whose x is right, y up and z
    toward the viewer.  Per atom: its centre, ``M⁻¹`` in the view frame (the
    scene's inverse times ``Rᵀ``), ``a = |M⁻¹ẑ|²``, its colour, luminance and
    ring flag.  Per bond half: its start, unit axis, length, the ray direction
    with its part along the axis removed and that vector's square, radius and
    colour.  Per segment (a line or a letter's stroke): its ends in sample
    coordinates, half-width in samples, unit direction, length and the two
    depths.  Per face triangle, in drawing order: its corners in view
    coordinates wound counter-clockwise on screen, twice its area, which of its
    edges own the samples lying exactly on them (the top-left rule, so two
    triangles sharing an edge never paint a sample twice), and its colour,
    already lit, since a face is flat.
    """
    R = np.asarray(rotation, dtype=np.float64)
    hs, ws = frame.height * s, frame.width * s
    pxs = frame.ppa * s
    x0, y0 = frame.x0, frame.y0

    def su(x):
        return (x - x0) * pxs

    def sv(y):
        return (y0 - y) * pxs

    light = np.asarray(LOOK["light"], dtype=np.float64)
    light = light / math.sqrt(float(light @ light))
    look = np.array([*light, LOOK["ambient"], LOOK["diffuse"], LOOK["specular"],
                     LOOK["shininess"], LOOK["face_diffuse"], LOOK["ring_width"],
                     LOOK["ring_dark"], LOOK["ring_lighten"], LOOK["ring_darken"]],
                    dtype=np.float64)
    luma = LOOK["luma"]

    atoms = [a for a in scene["atoms"] if a["inverse"] is not None]
    na = len(atoms)
    atom_c = np.zeros((na, 3))
    atom_m = np.zeros((na, 3, 3))
    atom_a = np.zeros(na)
    atom_col = np.zeros((na, 3))
    atom_lum = np.zeros(na)
    atom_ring = np.zeros(na, dtype=np.bool_)
    atom_box = np.zeros((na, 4), dtype=np.int64)
    for i, a in enumerate(atoms):
        c = R @ np.asarray(a["pos"], dtype=np.float64)
        shape = R @ np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        minv = np.asarray(a["inverse"], dtype=np.float64).reshape(3, 3) @ R.T
        e = minv[:, 2]
        hx = math.sqrt(float(shape[0] @ shape[0]))
        hy = math.sqrt(float(shape[1] @ shape[1]))
        atom_c[i] = c
        atom_m[i] = minv
        atom_a[i] = e[0] * e[0] + e[1] * e[1] + e[2] * e[2]
        atom_col[i] = a["color"]
        atom_lum[i] = luma[0] * a["color"][0] + luma[1] * a["color"][1] + luma[2] * a["color"][2]
        atom_ring[i] = a["rings"]
        atom_box[i] = _box(su(c[0] - hx), su(c[0] + hx), sv(c[1] + hy), sv(c[1] - hy), hs, ws)

    halves = []
    for h in scene["halves"]:
        A = R @ np.asarray(h["from"], dtype=np.float64)
        B = R @ np.asarray(h["to"], dtype=np.float64)
        length = math.sqrt(float((B - A) @ (B - A)))
        if length < 1e-9:
            continue
        w = (B - A) / length
        e = np.array([0.0, 0.0, 1.0]) - w[2] * w
        ea = float(e @ e)
        if ea < 1e-9:                      # looking straight down the bond
            continue
        halves.append((A, B, w, length, e, ea, h["radius"], h["color"]))
    nh = len(halves)
    half_a = np.zeros((nh, 3))
    half_w = np.zeros((nh, 3))
    half_len = np.zeros(nh)
    half_e = np.zeros((nh, 3))
    half_ea = np.zeros(nh)
    half_r = np.zeros(nh)
    half_col = np.zeros((nh, 3))
    half_box = np.zeros((nh, 4), dtype=np.int64)
    for i, (A, B, w, length, e, ea, r, color) in enumerate(halves):
        half_a[i], half_w[i], half_len[i], half_e[i], half_ea[i] = A, w, length, e, ea
        half_r[i] = r
        half_col[i] = color
        half_box[i] = _box(su(min(A[0], B[0]) - r), su(max(A[0], B[0]) + r),
                           sv(max(A[1], B[1]) + r), sv(min(A[1], B[1]) - r), hs, ws)

    points, widths, colors, depths = [], [], [], []
    for line in scene["lines"]:
        A = R @ np.asarray(line["a"], dtype=np.float64)
        B = R @ np.asarray(line["b"], dtype=np.float64)
        points.append((su(A[0]), sv(A[1]), su(B[0]), sv(B[1])))
        widths.append(0.5 * line["width"] * frame.px_scale * s)
        colors.append(line["color"])
        depths.append((A[2], B[2]))
    lines = _segments(points, widths, colors, depths, hs, ws)

    # faces: whole polyhedra back to front by centroid, each one's back faces
    # before its front, as the GUI orders them (a stable sort, like JS's)
    faces = sorted(scene["faces"], key=lambda f: float(R[2] @ np.asarray(f["centroid"])))
    tris = []
    for face in faces:
        tv = np.asarray(face["triangles"], dtype=np.float64).reshape(-1, 3, 3) @ R.T
        tn = np.asarray(face["normals"], dtype=np.float64).reshape(-1, 3) @ R.T
        base = np.asarray(face["color"], dtype=np.float64)
        for front in (False, True):
            for v, n in zip(tv, tn):
                area = ((v[1, 0] - v[0, 0]) * (v[2, 1] - v[0, 1])
                        - (v[1, 1] - v[0, 1]) * (v[2, 0] - v[0, 0]))
                if area == 0.0 or (area > 0.0) != front:
                    continue
                if not front:                   # wind it counter-clockwise
                    v, area, n = v[[0, 2, 1]], -area, -n
                d = max(float(n @ light), 0.0)
                tris.append((v, area, base * (LOOK["ambient"] + LOOK["face_diffuse"] * d)))
    nt = len(tris)
    tri_v = np.zeros((nt, 3, 3))
    tri_area = np.zeros(nt)
    tri_tie = np.zeros((nt, 3), dtype=np.bool_)
    tri_col = np.zeros((nt, 3))
    tri_box = np.zeros((nt, 4), dtype=np.int64)
    for i, (v, area, color) in enumerate(tris):
        tri_v[i], tri_area[i], tri_col[i] = v, area, color
        # an edge owns its on-edge samples if it is a left edge (going down
        # the screen) or a top edge (level, going left), for a
        # counter-clockwise triangle with y up
        for k, (p, q) in enumerate(((1, 2), (2, 0), (0, 1))):
            dx, dy = v[q, 0] - v[p, 0], v[q, 1] - v[p, 1]
            tri_tie[i, k] = dy < 0.0 or (dy == 0.0 and dx < 0.0)
        tri_box[i] = _box(su(v[:, 0].min()), su(v[:, 0].max()),
                          sv(v[:, 1].max()), sv(v[:, 1].min()), hs, ws)

    text = text or []
    letters = _segments([tuple(v * s for v in t[0]) for t in text], [t[1] * s for t in text],
                        [t[2] for t in text], [(0.0, 0.0)] * len(text), hs, ws)
    return {
        "look": look,
        "atom": (atom_c, atom_m, atom_a, atom_col, atom_lum, atom_ring, atom_box),
        "half": (half_a, half_w, half_len, half_e, half_ea, half_r, half_col, half_box),
        "line": lines,
        "tri": (tri_v, tri_area, tri_tie, tri_col, tri_box),
        "text": letters,
    }


def _grid(box, ext0, he):
    """The sample indices of a box clipped to a band, as float arrays."""
    iy0, iy1 = max(box[0], ext0), min(box[1], ext0 + he)
    if iy0 >= iy1 or box[2] >= box[3]:
        return None
    iy = np.arange(iy0, iy1, dtype=np.float64)[:, None]
    ix = np.arange(box[2], box[3], dtype=np.float64)[None, :]
    return iy0, iy1, iy, ix


def _fogged(col, z, fog):
    """``col`` blended toward the fog colour by its depth ``z`` (WP-1548 D1).

    ``fog`` is ``(z_start, z_end, f_max, colour)`` in view coordinates, z
    toward the viewer: the factor is 0 in front of ``z_start``, rises linearly
    to ``f_max`` at ``z_end`` and stays there behind it.  The blend is GLSL's
    ``mix(col, colour, f)``, ``col·(1 − f) + colour·f``, spelled as the GUI's
    shader spells it.  ``None`` returns ``col`` itself, so a picture without
    fog runs no arithmetic it did not run before.
    """
    if fog is None:
        return col
    z_start, z_end, f_max, colour = fog
    f = f_max * np.minimum(np.maximum((z_start - z) / (z_start - z_end), 0.0), 1.0)
    return col * (1.0 - f)[..., None] + colour * f[..., None]


def _flat_numpy(seg, depth, ext0, he, zb, pm, al, fog=None):
    p, half, direction, length, z, col, box = seg
    for i in range(len(p)):
        g = _grid(box[i], ext0, he)
        if g is None:
            continue
        iy0, iy1, iy, ix = g
        h = half[i]
        v = iy + 0.5 - p[i, 1]
        u = ix + 0.5 - p[i, 0]
        along = u * direction[i, 0] + v * direction[i, 1]
        across = v * direction[i, 0] - u * direction[i, 1]
        hit = ~((np.abs(across) > h) | (along < -h) | (along > length[i] + h))
        rows = slice(iy0 - ext0, iy1 - ext0)
        cols = slice(box[i, 2], box[i, 3])
        ink = col[i]
        if depth:
            zz = z[i, 0] + (z[i, 1] - z[i, 0]) * ((along + h) / (length[i] + 2.0 * h))
            hit &= ~(zz < zb[rows, cols])
            zb[rows, cols] = np.where(hit, zz, zb[rows, cols])
            ink = _fogged(ink, zz, fog)
        pm[rows, cols] = np.where(hit[..., None], ink, pm[rows, cols])
        al[rows, cols] = np.where(hit, 1.0, al[rows, cols])


def _ipow(x, n):
    out = np.ones_like(x)
    base = x
    while n > 0:
        if n & 1:
            out = out * base
        base = base * base
        n >>= 1
    return out


def _shade(base, n0, n1, n2, look, occ=None):
    """``base·(ambient + diffuse·d) + specular·s^shininess``; with ``occ``,
    the unoccluded share of ambient light at each sample, the ambient term
    is ``ambient·occ`` (WP-1538 D3) and the key light keeps its own."""
    ndl = n0 * look[0] + n1 * look[1] + n2 * look[2]
    d = np.maximum(ndl, 0.0)
    rz = -look[2] + 2.0 * ndl * n2
    spec = _ipow(np.maximum(rz, 0.0), int(look[6]))
    k = look[3] + look[4] * d if occ is None else look[3] * occ + look[4] * d
    return np.stack([base[0] * k + look[5] * spec, base[1] * k + look[5] * spec,
                     base[2] * k + look[5] * spec], axis=-1)


def _outline_numpy(ext0, sr0, hs, ws, total, ow, otau, ocol, zb, pm, fog=None):
    """The Rust kernel's ``draw_outline`` in numpy: one shifted comparison per offset in the disc."""
    rows = slice(sr0 - ext0, sr0 - ext0 + hs)
    core = zb[rows]
    edge = np.zeros(core.shape, dtype=bool)
    for dy in range(-ow, ow + 1):
        ys = np.arange(sr0, sr0 + hs) + dy
        okr = (ys >= 0) & (ys < total)
        for dx in range(-ow, ow + 1):
            if dx * dx + dy * dy > ow * ow:
                continue
            # the neighbour of core sample (iy, ix) is (iy + dy, ix + dx),
            # skipped where it falls outside the image
            xs = np.arange(ws) + dx
            okc = (xs >= 0) & (xs < ws)
            q = zb[np.clip(ys - ext0, 0, zb.shape[0] - 1)][:, np.clip(xs, 0, ws - 1)]
            edge |= okr[:, None] & okc[None, :] & (q < core - otau)
    edge &= core != -np.inf
    # the ink fades with the surface it is drawn over
    ink = ocol if fog is None else _fogged(ocol, np.where(edge, core, 0.0), fog)
    pm[rows] = np.where(edge[..., None], ink, pm[rows])


def _occluded(occ, R, iy, ix, pxs, x0, y0, z, n0, n1, n2, hit):
    """The unoccluded share at each hit sample of a box (:func:`occlusion`),
    1 elsewhere: the sample's point and normal taken back from the view
    frame to the structure's by ``Rᵀ``."""
    share = np.ones(hit.shape)
    if not hit.any():
        return share
    sy = np.broadcast_to(y0 - (iy + 0.5) / pxs, hit.shape)[hit]
    sx = np.broadcast_to(x0 + (ix + 0.5) / pxs, hit.shape)[hit]
    view_p = np.stack([sx, sy, z[hit]], axis=1)
    view_n = np.stack([n0[hit], n1[hit], n2[hit]], axis=1)
    share[hit] = occlusion(occ, view_p @ R, view_n @ R)
    return share


def _band_numpy(r0, r1, s, frame, pk, alpha, bg, outline, out, fog=None, occ=None):
    """Rows ``r0`` to ``r1`` of ``out``: each primitive's per-sample
    expressions, evaluated over its whole box at once.  ``occ`` is
    ``(maps, rotation)`` for ambient occlusion (WP-1538), or ``None``."""
    hs, ws, sr0 = (r1 - r0) * s, frame.width * s, r0 * s
    total = frame.height * s
    ow, otau, ocol = outline
    ext0, ext1 = max(sr0 - ow, 0), min(sr0 + hs + ow, total)
    he = ext1 - ext0
    pxs, x0, y0 = frame.ppa * s, frame.x0, frame.y0
    look = pk["look"]
    zb = np.full((he, ws), -np.inf)
    pm = np.zeros((he, ws, 3))
    al = np.zeros((he, ws))
    atom_c, atom_m, atom_a, atom_col, atom_lum, atom_ring, atom_box = pk["atom"]
    for i in range(len(atom_c)):
        g = _grid(atom_box[i], ext0, he)
        if g is None:
            continue
        iy0, iy1, iy, ix = g
        m = atom_m[i]
        e0, e1, e2 = m[0, 2], m[1, 2], m[2, 2]
        y = y0 - (iy + 0.5) / pxs - atom_c[i, 1]
        x = x0 + (ix + 0.5) / pxs - atom_c[i, 0]
        q0 = m[0, 0] * x + m[0, 1] * y
        q1 = m[1, 0] * x + m[1, 1] * y
        q2 = m[2, 0] * x + m[2, 1] * y
        b = q0 * e0 + q1 * e1 + q2 * e2
        cc = q0 * q0 + q1 * q1 + q2 * q2 - 1.0
        disc = b * b - atom_a[i] * cc
        hit = ~(disc < 0.0)
        t = (-b + np.sqrt(np.where(hit, disc, 0.0))) / atom_a[i]
        z = atom_c[i, 2] + t
        rows = slice(iy0 - ext0, iy1 - ext0)
        cols = slice(atom_box[i, 2], atom_box[i, 3])
        hit &= ~(z < zb[rows, cols])
        u0 = q0 + t * e0
        u1 = q1 + t * e1
        u2 = q2 + t * e2
        n0 = m[0, 0] * u0 + m[1, 0] * u1 + m[2, 0] * u2
        n1 = m[0, 1] * u0 + m[1, 1] * u1 + m[2, 1] * u2
        n2 = e0 * u0 + e1 * u1 + e2 * u2
        nn = np.sqrt(n0 * n0 + n1 * n1 + n2 * n2)
        nn = np.where(hit, nn, 1.0)
        share = None if occ is None else _occluded(
            occ[0], occ[1], iy, ix, pxs, x0, y0, z, n0 / nn, n1 / nn, n2 / nn, hit)
        col = _shade(atom_col[i], n0 / nn, n1 / nn, n2 / nn, look, share)
        if atom_ring[i]:
            ring = np.minimum(np.abs(u0), np.minimum(np.abs(u1), np.abs(u2))) < look[8]
            ink = col + look[10] * (1.0 - col) if atom_lum[i] < look[9] else col * look[11]
            col = np.where(ring[..., None], ink, col)
        col = _fogged(np.minimum(np.maximum(col, 0.0), 1.0), z, fog)
        zb[rows, cols] = np.where(hit, z, zb[rows, cols])
        pm[rows, cols] = np.where(hit[..., None], col, pm[rows, cols])
        al[rows, cols] = np.where(hit, 1.0, al[rows, cols])
    half_a, half_w, half_len, half_e, half_ea, half_r, half_col, half_box = pk["half"]
    for i in range(len(half_a)):
        g = _grid(half_box[i], ext0, he)
        if g is None:
            continue
        iy0, iy1, iy, ix = g
        w0, w1, w2 = half_w[i]
        f0, f1, f2 = half_e[i]
        a, r = half_ea[i], half_r[i]
        o1 = y0 - (iy + 0.5) / pxs - half_a[i, 1]
        o0 = x0 + (ix + 0.5) / pxs - half_a[i, 0]
        o2 = -half_a[i, 2]
        oa = o0 * w0 + o1 * w1 + o2 * w2
        q0 = o0 - oa * w0
        q1 = o1 - oa * w1
        q2 = o2 - oa * w2
        b = q0 * f0 + q1 * f1 + q2 * f2
        disc = b * b - a * (q0 * q0 + q1 * q1 + q2 * q2 - r * r)
        hit = ~(disc < 0.0)
        z = (-b + np.sqrt(np.where(hit, disc, 0.0))) / a
        along = oa + z * w2
        hit &= ~((along < 0.0) | (along > half_len[i]))
        rows = slice(iy0 - ext0, iy1 - ext0)
        cols = slice(half_box[i, 2], half_box[i, 3])
        hit &= ~(z < zb[rows, cols])
        n0 = q0 + z * f0
        n1 = q1 + z * f1
        n2 = q2 + z * f2
        nn = np.sqrt(n0 * n0 + n1 * n1 + n2 * n2)
        nn = np.where(hit, nn, 1.0)
        share = None if occ is None else _occluded(
            occ[0], occ[1], iy, ix, pxs, x0, y0, z, n0 / nn, n1 / nn, n2 / nn, hit)
        col = _fogged(np.minimum(np.maximum(_shade(half_col[i], n0 / nn, n1 / nn, n2 / nn,
                                                   look, share), 0.0), 1.0), z, fog)
        zb[rows, cols] = np.where(hit, z, zb[rows, cols])
        pm[rows, cols] = np.where(hit[..., None], col, pm[rows, cols])
        al[rows, cols] = np.where(hit, 1.0, al[rows, cols])
    if ow > 0:
        _outline_numpy(ext0, sr0, hs, ws, total, ow, otau, ocol, zb, pm, fog)
    _flat_numpy(pk["line"], True, ext0, he, zb, pm, al, fog)
    tri_v, tri_area, tri_tie, tri_col, tri_box = pk["tri"]
    for i in range(len(tri_v)):
        g = _grid(tri_box[i], ext0, he)
        if g is None:
            continue
        iy0, iy1, iy, ix = g
        (ax, ay, az), (bx, by, bz), (qx, qy, qz) = tri_v[i]
        y = y0 - (iy + 0.5) / pxs
        x = x0 + (ix + 0.5) / pxs
        ea = (qx - bx) * (y - by) - (qy - by) * (x - bx)
        eb = (ax - qx) * (y - qy) - (ay - qy) * (x - qx)
        ec = (bx - ax) * (y - ay) - (by - ay) * (x - ax)
        hit = np.ones(ea.shape, dtype=bool)
        for e, tie in ((ea, tri_tie[i, 0]), (eb, tri_tie[i, 1]), (ec, tri_tie[i, 2])):
            hit &= ~((e < 0.0) | ((e == 0.0) & (not tie)))
        z = (ea * az + eb * bz + ec * qz) / tri_area[i]
        rows = slice(iy0 - ext0, iy1 - ext0)
        cols = slice(tri_box[i, 2], tri_box[i, 3])
        hit &= ~(z < zb[rows, cols])
        pm[rows, cols] = np.where(hit[..., None],
                                  alpha * _fogged(tri_col[i], z, fog)
                                  + (1.0 - alpha) * pm[rows, cols],
                                  pm[rows, cols])
        al[rows, cols] = np.where(hit, alpha + (1.0 - alpha) * al[rows, cols], al[rows, cols])
    _flat_numpy(pk["text"], False, ext0, he, zb, pm, al)
    # the box filter, in render_rows' order
    acc = np.zeros((r1 - r0, frame.width, 3))
    acc_a = np.zeros((r1 - r0, frame.width))
    core = slice(sr0 - ext0, sr0 - ext0 + hs)
    for dy in range(s):
        for dx in range(s):
            acc = acc + pm[core][dy::s, dx::s]
            acc_a = acc_a + al[core][dy::s, dx::s]
    n = float(s * s)
    acc = acc / n
    acc_a = acc_a / n
    if bg is not None:
        rgb = acc + (1.0 - acc_a)[..., None] * np.asarray(bg, dtype=np.float64)
        a = np.ones_like(acc_a)
    else:
        safe = np.where(acc_a > 0.0, acc_a, 1.0)
        rgb = np.where((acc_a > 0.0)[..., None], acc / safe[..., None], 0.0)
        a = acc_a
    rgba = np.concatenate([rgb, a[..., None]], axis=-1)
    out[r0:r1] = np.floor(np.minimum(np.maximum(rgba, 0.0), 1.0) * 255.0 + 0.5).astype(np.uint8)


def draw(scene: dict, rotation, frame: Frame, *, supersample: int = 2,
         background=(1.0, 1.0, 1.0), text: list | None = None,
         outline: tuple | None = None, fog: tuple | None = None,
         occlusion: OcclusionMaps | None = None) -> np.ndarray:
    """The picture, ``frame.height × frame.width × 4`` ``uint8``, straight alpha.

    ``background`` is three channels in 0..1, or ``None`` for transparent.
    ``text`` is strokes drawn over everything: ``((u0, v0, u1, v1), half-width,
    colour)`` in image pixels.  ``outline`` is ``(radius in image pixels,
    depth step in Å, colour)``, or ``None``.  ``fog`` is ``(z_start, z_end,
    f_max, colour)`` in view coordinates (:func:`_fogged`), or ``None``.

    Fog runs on whichever path the process runs: the wheel's
    ``render_rows_cued`` (``rietx-kernels`` from 1.5.0, WP-1548) is
    ``render_rows`` with the fog, held to :func:`_band_numpy`'s bits like it,
    and a picture without fog calls ``render_rows`` as before.

    ``occlusion`` is the scene's :func:`occlusion_maps`, for ambient
    occlusion (WP-1538), or ``None``.  No kernel draws it yet, so a picture
    with it runs :func:`_band_numpy` on either path; the maps themselves are
    built by :func:`id_plane`, on the process's path.
    """
    s = int(supersample)
    pk = _pack(scene, rotation, frame, s, text)
    out = np.zeros((frame.height, frame.width, 4), dtype=np.uint8)
    if outline is None:
        ow, otau, ocol = 0, 0.0, np.zeros(3)
    else:
        ow = max(1, round(outline[0] * s))
        otau, ocol = float(outline[1]), np.asarray(outline[2], dtype=np.float64)
    rows = max(1, BAND_SAMPLES // (frame.width * s * s))
    if fog is not None:
        z_start, z_end, f_max, colour = fog
        if not z_start > z_end:
            raise ValueError(f"fog starts at z = {z_start!r}, which is not in front of "
                             f"where it ends, z = {z_end!r}")
        colour = np.ascontiguousarray(colour, dtype=np.float64)
        # the wheel's refusal too, so both paths refuse one colour alike
        if colour.shape != (3,):
            raise ValueError(f"fog colour has {colour.size} entries, not 3")
        fog = (float(z_start), float(z_end), float(f_max), colour)
    kernel = (None if occlusion is not None
              else _kernel("render_rows" if fog is None else "render_rows_cued"))
    if kernel is None:
        cue = {} if fog is None else {"fog": fog}
        if occlusion is not None:
            cue["occ"] = (occlusion, np.asarray(rotation, dtype=np.float64))
        for r0 in range(0, frame.height, rows):
            _band_numpy(r0, min(frame.height, r0 + rows), s, frame, pk, POLY_ALPHA,
                        background, (ow, otau, ocol), out, **cue)
        return out
    bg = None if background is None else np.asarray(background, dtype=np.float64)
    # render_rows_cued takes the fog between the primitives and the picture
    args = (s, frame.height, frame.x0, frame.y0, frame.ppa * s, frame.width, pk["look"],
            POLY_ALPHA, bg, ow, otau, ocol, pk["atom"], pk["half"], pk["line"], pk["tri"],
            pk["text"], *(() if fog is None else fog), out)
    pool = compiled._pool()
    workers = compiled._POOL_WORKERS     # the pool's own count, as ``_spread`` reads it
    if workers <= 1:
        for r0 in range(0, frame.height, rows):
            kernel(r0, min(frame.height, r0 + rows), *args)
        return out
    # at least one band a worker, or a 1000 px render is four bands and leaves
    # the rest of the pool idle; the bits do not depend on banding
    rows = min(rows, max(1, -(-frame.height // workers)))
    for f in [pool.submit(kernel, r0, min(frame.height, r0 + rows), *args)
              for r0 in range(0, frame.height, rows)]:
        f.result()
    return out


@dataclass
class IdPlane:
    """Which primitive is in front at each pixel of a small frame.

    ``ids`` is ``height × width`` ``int32``: ``-1`` for nothing, ``k`` for the
    ``k``-th packed atom, ``n_atoms + k`` for the ``k``-th bond half.  ``seen``
    is each packed atom's samples it would cover were nothing in front of it,
    and ``front`` the samples it does cover; ``index`` maps a packed atom to
    its place in the scene's ``atoms``.
    """
    ids: np.ndarray
    seen: np.ndarray
    front: np.ndarray
    index: np.ndarray


def scene_arrays(scene: dict) -> dict:
    """The scene's atoms and bond halves as arrays, in the structure's Å: what
    :func:`pack_ids` rotates.  An atom with no inverse is left out, as
    :func:`_pack` leaves it."""
    atoms = [a for a in scene["atoms"] if a["inverse"] is not None]
    halves = scene["halves"]
    return {
        "index": np.array([a["index"] for a in atoms], dtype=np.int64),
        "pos": np.array([a["pos"] for a in atoms], dtype=np.float64).reshape(-1, 3),
        "shape": np.array([a["shape"] for a in atoms], dtype=np.float64).reshape(-1, 3, 3),
        "inverse": np.array([a["inverse"] for a in atoms], dtype=np.float64).reshape(-1, 3, 3),
        "from": np.array([h["from"] for h in halves], dtype=np.float64).reshape(-1, 3),
        "to": np.array([h["to"] for h in halves], dtype=np.float64).reshape(-1, 3),
        "radius": np.array([h["radius"] for h in halves], dtype=np.float64),
    }


def pack_ids(arrays: dict, rotation) -> dict:
    """:func:`_pack`'s atom and bond-half arrays for one view, vectorised.

    The same quantities :func:`_pack` computes (its docstring names them) in
    the same order of operations, to the last bit or one ulp off, which an id
    pass does not see.  A half seen end on, or of no length, is dropped.
    """
    R = np.asarray(rotation, dtype=np.float64)
    c = arrays["pos"] @ R.T
    shape = np.einsum("ij,njk->nik", R, arrays["shape"])
    hx = np.sqrt((shape[:, 0, :] ** 2).sum(axis=1))
    hy = np.sqrt((shape[:, 1, :] ** 2).sum(axis=1))
    minv = np.ascontiguousarray(arrays["inverse"] @ R.T)
    e = minv[:, :, 2]
    A = arrays["from"] @ R.T
    B = arrays["to"] @ R.T
    d = B - A
    length = np.sqrt((d * d).sum(axis=1))
    w = d / np.where(length > 0.0, length, 1.0)[:, None]
    f = np.array([0.0, 0.0, 1.0]) - w[:, 2:3] * w
    ea = (f * f).sum(axis=1)
    keep = (length >= 1e-9) & (ea >= 1e-9)
    r = arrays["radius"]
    lo = np.minimum(A, B)
    hi = np.maximum(A, B)
    return {
        "index": arrays["index"],
        "atom_c": np.ascontiguousarray(c), "atom_m": minv,
        "atom_a": np.ascontiguousarray((e * e).sum(axis=1)),
        "atom_reach": np.stack([c[:, 0] - hx, c[:, 0] + hx, c[:, 1] - hy, c[:, 1] + hy], axis=1),
        "half_a": np.ascontiguousarray(A[keep]), "half_w": np.ascontiguousarray(w[keep]),
        "half_len": np.ascontiguousarray(length[keep]), "half_e": np.ascontiguousarray(f[keep]),
        "half_ea": np.ascontiguousarray(ea[keep]), "half_r": np.ascontiguousarray(r[keep]),
        "half_reach": np.stack([lo[:, 0] - r, hi[:, 0] + r, lo[:, 1] - r, hi[:, 1] + r],
                               axis=1)[keep],
    }


def _boxes(reach: np.ndarray, frame: Frame) -> np.ndarray:
    """:func:`_box` for every primitive at once, one sample a pixel."""
    lo_x = (reach[:, 0] - frame.x0) * frame.ppa
    hi_x = (reach[:, 1] - frame.x0) * frame.ppa
    lo_y = (frame.y0 - reach[:, 3]) * frame.ppa
    hi_y = (frame.y0 - reach[:, 2]) * frame.ppa
    return np.stack([np.maximum(np.floor(lo_y) - 1, 0), np.minimum(np.ceil(hi_y) + 1, frame.height),
                     np.maximum(np.floor(lo_x) - 1, 0), np.minimum(np.ceil(hi_x) + 1, frame.width)],
                    axis=1).astype(np.int64)


def _ids_numpy(pk: dict, frame: Frame, atom_box, half_box, ids, seen) -> None:
    """:func:`id_plane`'s sample loop, in numpy: ``_band_numpy``'s atom and
    half tests without the shading, writing an index where they win."""
    pxs, x0, y0 = frame.ppa, frame.x0, frame.y0
    zb = np.full(ids.shape, -np.inf)
    atom_c, atom_m, atom_a = pk["atom_c"], pk["atom_m"], pk["atom_a"]
    na = len(atom_c)
    for i in range(na):
        g = _grid(atom_box[i], 0, frame.height)
        if g is None:
            continue
        iy0, iy1, iy, ix = g
        m = atom_m[i]
        e0, e1, e2 = m[0, 2], m[1, 2], m[2, 2]
        y = y0 - (iy + 0.5) / pxs - atom_c[i, 1]
        x = x0 + (ix + 0.5) / pxs - atom_c[i, 0]
        q0 = m[0, 0] * x + m[0, 1] * y
        q1 = m[1, 0] * x + m[1, 1] * y
        q2 = m[2, 0] * x + m[2, 1] * y
        b = q0 * e0 + q1 * e1 + q2 * e2
        cc = q0 * q0 + q1 * q1 + q2 * q2 - 1.0
        disc = b * b - atom_a[i] * cc
        hit = ~(disc < 0.0)
        z = atom_c[i, 2] + (-b + np.sqrt(np.where(hit, disc, 0.0))) / atom_a[i]
        rows = slice(iy0, iy1)
        cols = slice(atom_box[i, 2], atom_box[i, 3])
        seen[i] = int(hit.sum())
        hit &= ~(z < zb[rows, cols])
        zb[rows, cols] = np.where(hit, z, zb[rows, cols])
        ids[rows, cols] = np.where(hit, i, ids[rows, cols])
    for i in range(len(pk["half_a"])):
        g = _grid(half_box[i], 0, frame.height)
        if g is None:
            continue
        iy0, iy1, iy, ix = g
        w0, w1, w2 = pk["half_w"][i]
        f0, f1, f2 = pk["half_e"][i]
        a, r = pk["half_ea"][i], pk["half_r"][i]
        o1 = y0 - (iy + 0.5) / pxs - pk["half_a"][i, 1]
        o0 = x0 + (ix + 0.5) / pxs - pk["half_a"][i, 0]
        o2 = -pk["half_a"][i, 2]
        oa = o0 * w0 + o1 * w1 + o2 * w2
        q0 = o0 - oa * w0
        q1 = o1 - oa * w1
        q2 = o2 - oa * w2
        b = q0 * f0 + q1 * f1 + q2 * f2
        disc = b * b - a * (q0 * q0 + q1 * q1 + q2 * q2 - r * r)
        hit = ~(disc < 0.0)
        z = (-b + np.sqrt(np.where(hit, disc, 0.0))) / a
        along = oa + z * w2
        hit &= ~((along < 0.0) | (along > pk["half_len"][i]))
        rows = slice(iy0, iy1)
        cols = slice(half_box[i, 2], half_box[i, 3])
        hit &= ~(z < zb[rows, cols])
        zb[rows, cols] = np.where(hit, z, zb[rows, cols])
        ids[rows, cols] = np.where(hit, na + i, ids[rows, cols])


def id_plane(pk: dict, frame: Frame) -> IdPlane:
    """Which atom or bond half is in front at each pixel of ``frame``, for the
    arrays :func:`pack_ids` built (WP-1503).

    One sample a pixel, atoms and bond halves only: a cell-frame line is a
    pixel wide and a polyhedron face writes no depth, so neither hides an atom.
    The depth test and the ray arithmetic are :func:`draw`'s, and so is the
    choice of path.
    """
    atom_box, half_box = _boxes(pk["atom_reach"], frame), _boxes(pk["half_reach"], frame)
    ids = np.full((frame.height, frame.width), -1, dtype=np.int32)
    seen = np.zeros(len(atom_box), dtype=np.int64)
    kernel = _kernel("id_plane")
    if kernel is None:
        _ids_numpy(pk, frame, atom_box, half_box, ids, seen)
    else:
        kernel(frame.y0, frame.x0, frame.ppa,
               (pk["atom_c"], pk["atom_m"], pk["atom_a"], atom_box),
               (pk["half_a"], pk["half_w"], pk["half_len"], pk["half_e"], pk["half_ea"],
                pk["half_r"], half_box), ids, seen)
    front = np.bincount(ids[ids >= 0], minlength=len(atom_box) + len(half_box))[:len(atom_box)]
    return IdPlane(ids=ids, seen=seen, front=front, index=pk["index"])


# ----------------------------------------------------------------------
# ambient occlusion (WP-1538)
# ----------------------------------------------------------------------

#: Ambient occlusion's constants (WP-1538 D2), ``scene.LOOK``'s and so the
#: GUI's: how many directions the ambient light comes from, the side of each
#: direction's depth map in texels, and the depth bias as a share of the map's
#: width.  ChimeraX's are 64, 1024 and 0.01 (its ``lighting`` documentation);
#: 512 texels gave the 1024 map's mean darkening to 0.1 % on the 21 phases
#: (``docs/wp/1538-measure/results.txt``) at a quarter of its memory.
OCCLUSION_DIRECTIONS = LOOK["occlusion_directions"]
OCCLUSION_MAP_SIZE = LOOK["occlusion_map_size"]
OCCLUSION_BIAS = LOOK["occlusion_bias"]

#: Samples looked up in one go: :func:`occlusion` holds about seven
#: (samples × directions) float64 arrays at once, some 60 MB at this size.
_OCCLUSION_CHUNK = 1 << 14


def occlusion_directions(n: int = OCCLUSION_DIRECTIONS) -> np.ndarray:
    """``n`` unit vectors spread evenly over the sphere: the Fibonacci
    lattice, ``z = 1 − (2i + 1)/n`` and a turn of the golden angle
    ``π(3 − √5)`` from one to the next, in the structure's Cartesian frame."""
    i = np.arange(n, dtype=np.float64)
    z = 1.0 - (2.0 * i + 1.0) / n
    r = np.sqrt(1.0 - z * z)
    phi = i * (math.pi * (3.0 - math.sqrt(5.0)))
    return np.stack([r * np.cos(phi), r * np.sin(phi), z], axis=1)


def _light_basis(d: np.ndarray) -> np.ndarray:
    """A rotation whose third row is ``d``: the view looking back along a
    light from direction ``d``, so a depth map's z grows toward the light.
    Its first row is ``x̂ × d`` normalised, or ``ŷ × d`` where ``d`` is within
    about 25° of the x axis, and its second ``d ×`` the first."""
    helper = np.array([1.0, 0.0, 0.0]) if abs(d[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    u = np.cross(helper, d)
    u = u / math.sqrt(float(u @ u))
    v = np.cross(d, u)
    return np.stack([u, v, d])


@dataclass
class OcclusionMaps:
    """A scene's depth maps from every ambient direction (WP-1538 D1, D5).

    ``depth[k]`` is the depth toward the light of what is nearest it at each
    texel of direction ``k``'s map, in Å, ``-inf`` where nothing is.
    ``basis[k]`` is that direction's rotation (:func:`_light_basis`) and
    ``origin[k]`` the map's top-left corner in its view coordinates, the
    maps being ``size`` texels a side at ``ppa`` texels per Å.  ``bias`` is
    the depth bias in Å.  Nothing here depends on the view or the framing.
    """
    directions: np.ndarray
    basis: np.ndarray
    origin: np.ndarray
    ppa: float
    size: int
    bias: float
    depth: np.ndarray


def _depths(pk: dict, frame: Frame, ids: np.ndarray) -> np.ndarray:
    """The depth of the primitive in front at each pixel of an id plane,
    from :func:`_ids_numpy`'s own ray arithmetic, ``-inf`` where it is empty.

    Computed from the ids rather than kept from the pass, so the maps are the
    same on either path: the wheel's ``id_plane`` returns ids alone, and they
    are the numpy path's to the bit."""
    out = np.full(ids.shape, -np.inf)
    iy, ix = np.nonzero(ids >= 0)
    k = ids[iy, ix].astype(np.intp)
    na = len(pk["atom_c"])
    y_px = frame.y0 - (iy + 0.5) / frame.ppa
    x_px = frame.x0 + (ix + 0.5) / frame.ppa
    on = k < na
    if on.any():
        i = k[on]
        m, c, a = pk["atom_m"][i], pk["atom_c"][i], pk["atom_a"][i]
        e0, e1, e2 = m[:, 0, 2], m[:, 1, 2], m[:, 2, 2]
        y = y_px[on] - c[:, 1]
        x = x_px[on] - c[:, 0]
        q0 = m[:, 0, 0] * x + m[:, 0, 1] * y
        q1 = m[:, 1, 0] * x + m[:, 1, 1] * y
        q2 = m[:, 2, 0] * x + m[:, 2, 1] * y
        b = q0 * e0 + q1 * e1 + q2 * e2
        cc = q0 * q0 + q1 * q1 + q2 * q2 - 1.0
        disc = np.maximum(b * b - a * cc, 0.0)
        out[iy[on], ix[on]] = c[:, 2] + (-b + np.sqrt(disc)) / a
    off = ~on
    if off.any():
        i = k[off] - na
        A, w, f = pk["half_a"][i], pk["half_w"][i], pk["half_e"][i]
        a, r = pk["half_ea"][i], pk["half_r"][i]
        o1 = y_px[off] - A[:, 1]
        o0 = x_px[off] - A[:, 0]
        o2 = -A[:, 2]
        oa = o0 * w[:, 0] + o1 * w[:, 1] + o2 * w[:, 2]
        q0 = o0 - oa * w[:, 0]
        q1 = o1 - oa * w[:, 1]
        q2 = o2 - oa * w[:, 2]
        b = q0 * f[:, 0] + q1 * f[:, 1] + q2 * f[:, 2]
        disc = np.maximum(b * b - a * (q0 * q0 + q1 * q1 + q2 * q2 - r * r), 0.0)
        out[iy[off], ix[off]] = (-b + np.sqrt(disc)) / a
    return out


def occlusion_maps(scene: dict, *, directions: int = OCCLUSION_DIRECTIONS,
                   size: int = OCCLUSION_MAP_SIZE, bias: float = OCCLUSION_BIAS
                   ) -> OcclusionMaps:
    """The depth maps ambient occlusion reads, one a direction (WP-1538).

    Each is an :func:`id_plane` of the scene's atoms and bond halves seen
    along the light, orthographic, over the square of side ``2·depth`` round
    ``scene["center"]`` (``depth`` bounds every atom the scene can draw, so
    every caster falls inside each map).  The cell
    frame and the polyhedron faces cast nothing (D4, D5): a frame line's
    width is in CSS px, so in Å it would follow the framing, and a face at
    ``POLY_ALPHA`` would darken its own centre atom.  The maps hold no view,
    so one set serves every view of a scene; anything that rebuilds the scene
    builds them again.
    """
    arrays = scene_arrays(scene)
    dirs = occlusion_directions(directions)
    center = np.asarray(scene["center"], dtype=np.float64)
    reach = float(scene["depth"])
    ppa = size / (2.0 * reach)
    basis = np.stack([_light_basis(d) for d in dirs])
    origin = np.zeros((directions, 2))
    depth = np.empty((directions, size, size), dtype=np.float32)
    for k in range(directions):
        R = basis[k]
        x0 = float(R[0] @ center) - reach
        y0 = float(R[1] @ center) + reach
        origin[k] = (x0, y0)
        frame = Frame(width=size, height=size, x0=x0, y0=y0, ppa=ppa, px_scale=1.0)
        pk = pack_ids(arrays, R)
        depth[k] = _depths(pk, frame, id_plane(pk, frame).ids)
    return OcclusionMaps(directions=dirs, basis=basis, origin=origin, ppa=ppa, size=size,
                         bias=bias * 2.0 * reach, depth=depth)


def occlusion(maps: OcclusionMaps, points: np.ndarray, normals: np.ndarray) -> np.ndarray:
    """The unoccluded share of ambient light at each of ``points`` (Å, the
    structure's Cartesian frame) with unit outward ``normals``.

    Each direction above a point's tangent plane is weighed by its cosine
    with the normal, as a light from it would be, and counts where the
    point's depth toward it, plus the bias, is no nearer the light than its
    map's texel (nearest texel).  The share is the lit weight over the whole
    weight, so a surface nothing else faces is 1 everywhere, its own far side
    being below the tangent plane of every point it would shadow.
    """
    out = np.ones(len(points))
    d, B, o = maps.directions, maps.basis, maps.origin
    last = maps.size - 1
    for s0 in range(0, len(points), _OCCLUSION_CHUNK):
        p = points[s0:s0 + _OCCLUSION_CHUNK]
        n = normals[s0:s0 + _OCCLUSION_CHUNK]
        w = np.maximum(n @ d.T, 0.0)                              # (m, k)
        pu = p @ B[:, 0, :].T
        pv = p @ B[:, 1, :].T
        pz = p @ B[:, 2, :].T
        col = np.clip(np.floor((pu - o[:, 0]) * maps.ppa), 0, last).astype(np.intp)
        row = np.clip(np.floor((o[:, 1] - pv) * maps.ppa), 0, last).astype(np.intp)
        k = np.broadcast_to(np.arange(len(d)), col.shape)
        lit = ~(pz + maps.bias < maps.depth[k, row, col])
        total = w.sum(axis=1)
        out[s0:s0 + len(p)] = np.where(total > 0.0, (w * lit).sum(axis=1)
                                       / np.where(total > 0.0, total, 1.0), 1.0)
    return out
