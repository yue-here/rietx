"""The structure figure as vector shapes: a display list, then SVG (WP-1536).

:func:`display_list` turns :func:`.scene.build_scene`'s scene, seen through a
rotation and fitted into a :class:`.raster.Frame`, into flat primitives in the
PNG's pixel coordinates, each with a depth key; :func:`svg` writes them far to
near.  This is the painter's algorithm, so what the raster gets from its depth
test is bought here by cutting things up (D2):

- **An atom is the ellipse its ellipsoid projects to.**  Under a parallel
  projection that is exact: with ``A`` the top two rows of ``R·M``, the
  outline is the ellipse of shape matrix ``A·Aᵀ`` round the projected centre.
- **A bond half is trimmed where its axis leaves its own atom**, solving
  ``|M⁻¹(p − pos)| = 1`` along the axis, and the rest is **cut into pieces**
  no longer than :data:`piece length <PIECE_FLOOR>`, so a bond passing behind
  a third atom sorts piece by piece.  A piece is the outline an open cylinder
  projects to, a rectangle closed by two half-ellipses.
- **Lines are cut the same way**, so a cell edge behind an atom is hidden
  where it passes behind it and not along its whole length.
- **Of atoms sharing a position** (a mixed site) the one reaching nearer the
  viewer is drawn last, each atom's rings straight after it, and a stick or
  line ending there is trimmed at the largest of them.
- **A polyhedron face is one polygon**: coplanar triangles are merged, and
  each face keys on the centroid of its own corners, so a centre atom sorts
  between its polyhedron's back and front faces.  A filled ring, or a named
  face on one plane, is one polygon too, though its corners lie on that plane
  only to within :data:`.rings.PLANAR_RING_TOLERANCE`; a named face off any
  plane is a hull, drawn face by face as a polyhedron is.

Shading is gradients from ``LOOK`` (D3).  A ball takes a radial gradient whose
focus is the specular highlight, with stops sampled from the raster's formula
along the ray from the focus through the centre; an ellipsoid takes the same
gradient in its own axes, which is approximate (normals transform by M⁻ᵀ).  A
stick takes a linear gradient across its width, which is exact: a cylinder's
shade is constant along every line parallel to its axis.  Depth cueing fades
each primitive by its depth key, so it is per element rather than per pixel.

What is left of the crossing fault (1470's ``mpl_baseline.py``) is
interpenetration: a translucent face cutting a vertex atom, two large
ellipsoids overlapping.  Nothing here splits those (Non-goals).
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping, Sequence
from xml.sax.saxutils import escape

import numpy as np

from .raster import Frame
from .scene import CELL_WIDTH_PX, LOOK, POLY_ALPHA, polyhedron_formula

#: The shortest a stick or line piece is cut to, in Å, whatever the smallest
#: drawn radius: below it a piece is narrower than its own stick.
PIECE_FLOOR = 0.15
#: Stops sampled along a gradient; the raster's shade is smooth, and twelve
#: keep the highlight's peak within a level of its sampled height.
GRADIENT_STOPS = 12
#: Points sampled round a principal ring before its visible runs are kept.
RING_SAMPLES = 96
_EPS = 1e-12


def _unit(v: np.ndarray) -> np.ndarray:
    n = math.sqrt(float(v @ v))
    return v / n if n > _EPS else v


def _light() -> np.ndarray:
    return _unit(np.asarray(LOOK["light"], dtype=np.float64))


def shade(base: Sequence[float], normal: Sequence[float]) -> np.ndarray:
    """The raster's lit colour of a solid (``raster._shade``), for one normal
    in view coordinates (x right, y up, z toward the viewer), clamped to 0..1."""
    light = _light()
    n = np.asarray(normal, dtype=np.float64)
    ndl = float(n @ light)
    d = max(ndl, 0.0)
    rz = -light[2] + 2.0 * ndl * n[2]
    spec = max(rz, 0.0) ** int(LOOK["shininess"])
    k = LOOK["ambient"] + LOOK["diffuse"] * d
    col = np.asarray(base, dtype=np.float64) * k + LOOK["specular"] * spec
    return np.clip(col, 0.0, 1.0)


def highlight() -> np.ndarray:
    """Where a ball's specular peak sits, as a unit-disk offset in image
    directions (x right, y down): the half vector between light and eye."""
    h = _unit(_light() + np.array([0.0, 0.0, 1.0]))
    return np.array([h[0], -h[1]])


def disk_stops(base, frame_axes: np.ndarray, fog_factor: float = 0.0,
               fog_colour=None) -> tuple[tuple[float, float], list[tuple[float, np.ndarray]]]:
    """A ball's radial gradient in its unit disk: the focus and the stops.

    ``frame_axes`` holds the ellipse's axes as rows, unit vectors in image
    directions; a ball's is the identity.  The stops are the shade along the
    ray from the focus through the centre to the far rim, where the focal
    gradient's circle of parameter ``t`` passes, so each stop is exact on that
    ray and the gradient interpolates between rays.
    """
    h = highlight()
    f = frame_axes @ h                       # the focus in the ellipse's axes
    out = []
    away = _unit(-f) if float(f @ f) > _EPS else np.array([1.0, 0.0])
    for k in range(GRADIENT_STOPS):
        t = k / (GRADIENT_STOPS - 1)
        p = f * (1.0 - t) + away * t
        p = p / max(1.0, math.hypot(p[0], p[1]))
        img = frame_axes.T @ p              # back to image directions
        nz = math.sqrt(max(0.0, 1.0 - float(img @ img)))
        col = shade(base, (img[0], -img[1], nz))
        if fog_factor:
            col = col * (1.0 - fog_factor) + np.asarray(fog_colour) * fog_factor
        out.append((t, col))
    return (float(f[0]), float(f[1])), out


def _fog_factor(z: float, fog) -> float:
    """``raster._fogged``'s factor at depth ``z``; 0 without fog."""
    if fog is None:
        return 0.0
    z_start, z_end, f_max, _ = fog
    return f_max * min(max((z_start - z) / (z_start - z_end), 0.0), 1.0)


def _fogged(col, z: float, fog) -> np.ndarray:
    f = _fog_factor(z, fog)
    col = np.asarray(col, dtype=np.float64)
    return col if f == 0.0 else col * (1.0 - f) + np.asarray(fog[3]) * f


def _token(text: str) -> str:
    """A label as one class token."""
    return re.sub(r"\s+", "_", str(text)) or "_"


def projected_ellipse(shape_view: np.ndarray, ppa: float):
    """``(rx, ry, angle)`` of the outline an ellipsoid projects to, in image
    pixels, ``angle`` the image-frame direction of the ``rx`` axis in degrees.

    ``shape_view`` is ``R·M``: a surface point is ``c + (R·M)·u`` with
    ``|u| = 1``, so the outline is the ellipse of shape matrix ``A·Aᵀ`` with
    ``A`` the top two rows, y flipped for the image's downward y.
    """
    a = np.asarray(shape_view, dtype=np.float64)[:2] * ppa
    a[1] = -a[1]
    c = a @ a.T
    vals, vecs = np.linalg.eigh(c)          # ascending
    rx, ry = math.sqrt(max(vals[1], 0.0)), math.sqrt(max(vals[0], 0.0))
    if rx - ry <= 1e-9 * max(rx, _EPS):
        return rx, ry, 0.0
    v = vecs[:, 1]
    angle = math.degrees(math.atan2(v[1], v[0]))
    if angle <= -90.0:
        angle += 180.0
    elif angle > 90.0:
        angle -= 180.0
    return rx, ry, angle


#: Directions round a stick's rim tried when trimming it at its atom.
RIM_SAMPLES = 16


def trim_length(inverse: np.ndarray, axis: np.ndarray, radius: float = 0.0) -> float:
    """How far along the unit ``axis`` from an ellipsoid's centre a tube of
    ``radius`` round it first leaves the surface: the least ``t`` over the rim
    with ``|M⁻¹·(t·axis + radius·d)| = 1``, ``d`` perpendicular to the axis.

    At ``radius=0`` it is where the axis itself leaves.  Past the returned
    ``t`` some of the rim is outside, so a stick cut there leaves no gap
    against its ball; a rim wider than the ellipsoid is never inside, and 0
    is returned.  Exact for a sphere, √(R² − r²).
    """
    minv = np.asarray(inverse, dtype=np.float64).reshape(3, 3)
    w = np.asarray(axis, dtype=np.float64)
    a = minv @ w
    aa = float(a @ a)
    if aa < _EPS:
        return 0.0
    if radius <= 0.0:
        return 1.0 / math.sqrt(aa)
    e1 = _unit(np.cross(w, [1.0, 0.0, 0.0] if abs(w[0]) < 0.9 else [0.0, 1.0, 0.0]))
    e2 = np.cross(w, e1)
    best = math.inf
    for k in range(RIM_SAMPLES):
        phi = 2.0 * math.pi * k / RIM_SAMPLES
        b = minv @ (radius * (math.cos(phi) * e1 + math.sin(phi) * e2))
        ab, bb = float(a @ b), float(b @ b)
        disc = ab * ab - aa * (bb - 1.0)
        if disc < 0.0:
            return 0.0                      # this side of the rim is never inside
        best = min(best, (-ab + math.sqrt(disc)) / aa)
    return max(best, 0.0)


def _at(pos) -> tuple:
    """A position as a key, to a thousandth of a picometre."""
    return tuple(round(float(v), 8) for v in pos)


def _trim_at(by_pos: Mapping, point, axis: np.ndarray, radius: float) -> float:
    """Where a stick or line from ``point`` along ``axis`` leaves the atoms
    drawn there: the largest :func:`trim_length` of them, since every one of
    a mixed site's atoms sits at the one position; 0 where none is drawn."""
    return max((trim_length(a["inverse"], axis, radius) for a in by_pos.get(_at(point), ())),
               default=0.0)


def _site_of(geometry: Mapping, index: int) -> str:
    return _token(geometry["sites"][geometry["atoms"][index]["site"]]["label"])


def piece_length(scene: Mapping) -> float:
    """The longest a stick or line piece may be, in Å: the smallest drawn
    semi-axis, so a piece behind an atom is never longer than the atom is
    wide, floored at :data:`PIECE_FLOOR`."""
    smallest = []
    for a in scene["atoms"]:
        if a["inverse"] is None:
            continue
        s = np.linalg.svd(np.asarray(a["shape"], dtype=np.float64).reshape(3, 3),
                          compute_uv=False)
        smallest.append(float(s.min()))
    return max(min(smallest, default=PIECE_FLOOR), PIECE_FLOOR)


def _hull(points: np.ndarray) -> np.ndarray:
    """The 2D convex hull, counter-clockwise in a y-up frame (monotone chain)."""
    pts = sorted(set(map(tuple, np.round(points, 9))))
    if len(pts) <= 2:
        return np.asarray(pts)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower, upper = [], []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)
    return np.asarray(lower[:-1] + upper[:-1])


def display_list(scene: Mapping, geometry: Mapping, rotation, frame: Frame, *,
                 labels: Sequence[tuple] = (), em: float = 0.0,
                 accent=(0.0, 0.0, 0.0), ink=(0.0, 0.0, 0.0), fog=None) -> list[dict]:
    """Every primitive of the picture, sorted far to near.

    Each is a dict with ``kind`` (``atom``, ``ring``, ``stick``, ``line``,
    ``face`` or ``text``), ``depth`` (view z, toward the viewer; text sorts
    last), ``cls`` (D5's class) and the shape in image pixels.  ``labels``
    are ``render._labels``' strings and ``em`` their size in pixels; their
    ``accent``/``ink`` colours are rgb triples.  ``fog`` is the raster's
    ``(z_start, z_end, f_max, colour)`` or ``None``.
    """
    R = np.asarray(rotation, dtype=np.float64).reshape(3, 3)
    ppa = frame.ppa

    def px(c):
        return ((float(c[0]) - frame.x0) * ppa, (frame.y0 - float(c[1])) * ppa)

    items: list[dict] = []
    fog_colour = None if fog is None else tuple(fog[3])
    by_pos: dict[tuple, list] = {}
    for order, a in enumerate(scene["atoms"]):
        if a["inverse"] is None:
            continue
        by_pos.setdefault(_at(a["pos"]), []).append(a)
        c = R @ np.asarray(a["pos"], dtype=np.float64)
        shape = np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        sv = R @ shape
        rx, ry, angle = projected_ellipse(sv, ppa)
        t = math.radians(angle)
        axes = np.array([[math.cos(t), math.sin(t)], [-math.sin(t), math.cos(t)]])
        site = _site_of(geometry, a["index"])
        cx, cy = px(c)
        # a tie in depth goes to the atom reaching nearer the viewer, so of two
        # sites sharing a position (a mixed site) the larger along the line of
        # sight is drawn last, near enough what the raster's depth test shows
        # (which sees 1/|M⁻¹ẑ| on the centre ray, not this support); each
        # atom's rings follow it, so a larger atom drawn later covers them
        reach = math.sqrt(float(sv[2] @ sv[2]))
        tie = (reach, order)
        items.append({"kind": "atom", "depth": float(c[2]), "tie": (*tie, 0),
                      "cls": f"atom {site}",
                      "cx": cx, "cy": cy, "rx": rx, "ry": ry, "angle": angle,
                      "axes": axes, "color": tuple(a["color"]),
                      "fog": _fog_factor(float(c[2]), fog), "fog_colour": fog_colour})
        if a["rings"]:
            items += _rings(a, R, shape, c, px, ppa, site, fog, (*tie, 1))

    step = piece_length(scene)
    for h in scene["halves"]:
        items += _stick_pieces(h, geometry, by_pos, R, px, ppa, step, fog)

    for line in scene["lines"]:
        # a line ending at an atom (a polyhedron's vertex, a cell corner) is
        # trimmed at its surface, as a stick is, or its pieces near the
        # centre would sort in front of the ball they pass inside
        a = np.asarray(line["a"], dtype=np.float64)
        b = np.asarray(line["b"], dtype=np.float64)
        length = math.sqrt(float((b - a) @ (b - a)))
        if length < 1e-9:
            continue
        w = (b - a) / length
        half_width = 0.5 * line["width"] * frame.px_scale / ppa
        lo = _trim_at(by_pos, a, w, half_width)
        hi = _trim_at(by_pos, b, -w, half_width)
        if lo + hi >= length:
            continue
        A, B = R @ (a + w * lo), R @ (b - w * hi)
        n = max(1, math.ceil((length - lo - hi) / step))
        cls = "cell" if line["width"] == CELL_WIDTH_PX else "edge"
        for k in range(n):
            p, q = A + (B - A) * (k / n), A + (B - A) * ((k + 1) / n)
            z = float(p[2] + q[2]) / 2
            items.append({"kind": "line", "depth": z, "cls": cls, "a": px(p), "b": px(q),
                          "width": line["width"] * frame.px_scale,
                          "color": tuple(_fogged(line["color"], z, fog))})

    light = _light()
    polys = geometry.get("polyhedra", [])
    for face in scene["faces"]:
        if face["kind"] == "polyhedron":
            cls = f"face {_token(polyhedron_formula(geometry, polys[face['index']]))}"
        else:
            cls = f"fill {face['kind']}"
        items += _faces(face, R, px, light, cls, fog)

    for text, x, y, is_axis, *_ in labels:
        # a site label's text is its site's label, so it carries the site's
        # class as every other element of the site does (D5)
        items.append({"kind": "text", "depth": math.inf, "cls": "label axis" if is_axis
                      else f"label {_token(text)}", "x": float(x), "y": float(y),
                      "text": str(text),
                      "em": float(em), "color": tuple(accent if is_axis else ink)})
    # stable: equal keys keep the scene's order, as the GUI's LEQUAL test does
    items.sort(key=lambda it: (it["depth"], it.get("tie", (0.0, 0, 0))))
    return items


def _rings(atom, R, shape, c, px, ppa, site, fog, tie) -> list[dict]:
    """The visible runs of an ellipsoid's three principal rings, as polylines,
    sorting at the atom's own depth straight after it (``tie``)."""
    inverse = np.asarray(atom["inverse"], dtype=np.float64).reshape(3, 3)
    base = np.asarray(atom["color"], dtype=np.float64)
    lum = float(np.asarray(LOOK["luma"]) @ base)
    mid = base * (LOOK["ambient"] + 0.5 * LOOK["diffuse"])
    ink = (mid + LOOK["ring_lighten"] * (1.0 - mid) if lum < LOOK["ring_dark"]
           else mid * LOOK["ring_darken"])
    ink = _fogged(np.clip(ink, 0.0, 1.0), float(c[2]), fog)
    phi = np.linspace(0.0, 2.0 * math.pi, RING_SAMPLES, endpoint=False)
    out = []
    for k in range(3):
        i, j = [m for m in range(3) if m != k]
        u = np.zeros((RING_SAMPLES, 3))
        u[:, i], u[:, j] = np.cos(phi), np.sin(phi)
        pts = c + (R @ shape @ u.T).T
        nz = (R @ inverse.T @ u.T).T[:, 2]  # the normal's view z, M⁻ᵀ·u
        seen = nz > 0.0
        if not seen.any():
            continue
        width = max(2.0 * LOOK["ring_width"] * ppa
                    * math.hypot(*(R @ shape[:, k])[:2]), 0.5)
        for run in _runs(seen):
            out.append({"kind": "ring", "depth": float(c[2]), "tie": tie, "cls": f"ring {site}",
                        "points": [px(pts[m]) for m in run], "width": width,
                        "color": tuple(ink)})
    return out


def _runs(mask: np.ndarray) -> list[list[int]]:
    """The cyclic runs of ``True`` in ``mask``, each a list of indices."""
    n = len(mask)
    if mask.all():
        return [list(range(n)) + [0]]
    start = int(np.argmin(mask))            # a False: no run wraps past it
    runs, cur = [], []
    for s in range(1, n + 1):
        m = (start + s) % n
        if mask[m]:
            cur.append(m)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return [r for r in runs if len(r) >= 2]


def _stick_pieces(h, geometry, by_pos, R, px, ppa, step, fog) -> list[dict]:
    """A bond half, trimmed at its atom's surface and cut into pieces."""
    # a half's end is its atom's centre, or an image of it the bond reaches
    # across a cell face: the site is the bond's, the atom whatever is drawn there
    bond = geometry["bonds"][h["bond"]]
    own = bond["i"] if list(h["from"]) == list(bond["a"]) else bond["j"]
    A = np.asarray(h["from"], dtype=np.float64)
    B = np.asarray(h["to"], dtype=np.float64)
    length = math.sqrt(float((B - A) @ (B - A)))
    if length < 1e-9:
        return []
    w = (B - A) / length
    start = _trim_at(by_pos, A, w, h["radius"])
    if start >= length:
        return []                           # wholly inside its own atom
    Av, Bv = R @ (A + w * start), R @ B
    wv = R @ w
    side = np.array([wv[1], -wv[0], 0.0])  # across the axis, in the screen
    if float(side @ side) < 1e-18:
        return []                           # seen end on: its atom covers it
    side = side / math.sqrt(float(side @ side))
    r = h["radius"] * ppa
    n = max(1, math.ceil((length - start) / step))
    site = _site_of(geometry, own)
    mid = (Av + Bv) / 2
    centre = px(mid)
    across = np.array([side[0], -side[1]])  # image directions
    g0 = (centre[0] - across[0] * r, centre[1] - across[1] * r)
    g1 = (centre[0] + across[0] * r, centre[1] + across[1] * r)
    f = (np.array([0.0, 0.0, 1.0]) - wv[2] * wv)
    f = _unit(f)
    stops = []
    for k in range(GRADIENT_STOPS):
        s = -1.0 + 2.0 * k / (GRADIENT_STOPS - 1)
        normal = s * side + math.sqrt(max(0.0, 1.0 - s * s)) * f
        stops.append((k / (GRADIENT_STOPS - 1), shade(h["color"], normal)))
    # each piece but the first reaches back half a pixel over the one before,
    # and the last half a pixel past the bond's middle, so no antialiased seam
    # shows where two pieces or two halves meet
    lap = wv * (0.5 / (ppa * max(math.hypot(wv[0], wv[1]), 1e-9)))
    out = []
    for k in range(n):
        p, q = Av + (Bv - Av) * (k / n), Av + (Bv - Av) * ((k + 1) / n)
        z = float(p[2] + q[2]) / 2
        out.append({"kind": "stick", "depth": z, "cls": f"stick {site}",
                    "a": px(p - lap if k else p), "b": px(q + lap), "r": r, "across": (float(across[0]),
                                                                float(across[1])),
                    "minor": r * abs(float(wv[2])), "gradient": (g0, g1, stops),
                    "half": id(h), "fog": _fog_factor(z, fog),
                    "fog_colour": None if fog is None else tuple(fog[3])})
    return out


def _faces(face, R, px, light, cls, fog) -> list[dict]:
    """A face entry's triangles, merged into one polygon per plane.

    A fill (a ring, or a named face) whose triangles all face one way is an
    open fan over a convex polygon (:func:`.rings.ring_fills`,
    :func:`.rings.face_fill`) and is one polygon whatever its deviation from
    a plane; a closed hull always holds triangles facing apart, and is split
    by plane as a polyhedron is."""
    tri = np.asarray(face["triangles"], dtype=np.float64).reshape(-1, 3, 3)
    nrm = np.asarray(face["normals"], dtype=np.float64).reshape(-1, 3)
    base = np.asarray(face["color"], dtype=np.float64)
    planes: dict[tuple, list[int]] = {}
    if face["kind"] != "polyhedron" and len(nrm) and bool((nrm @ nrm[0] > 0.0).all()):
        planes[()] = list(range(len(nrm)))
    else:
        for t, n in enumerate(nrm):
            key = (*np.round(n, 6), round(float(n @ tri[t, 0]), 6))
            planes.setdefault(key, []).append(t)
    out = []
    for members in planes.values():
        # each corner once: a fan repeats its first vertex in every triangle
        verts = np.unique(np.round(tri[members].reshape(-1, 3), 9), axis=0) @ R.T
        nv = R @ _unit(nrm[members].sum(axis=0))
        if abs(nv[2]) < 1e-12:
            continue                        # seen edge on
        if nv[2] < 0.0:
            nv = -nv                        # lit from the side it shows
        d = max(float(nv @ light), 0.0)
        col = base * (LOOK["ambient"] + LOOK["face_diffuse"] * d)
        z = float(verts[:, 2].mean())
        hull = _hull(verts[:, :2])
        if len(hull) < 3:
            continue
        out.append({"kind": "face", "depth": z, "cls": cls,
                    "points": [px(p) for p in hull],
                    "color": tuple(_fogged(np.clip(col, 0.0, 1.0), z, fog))})
    return out


# ----------------------------------------------------------------------
# the SVG
# ----------------------------------------------------------------------

def _attr(text: str) -> str:
    """Text for a double-quoted attribute: a CIF label may hold a quote."""
    return escape(text, {'"': "&quot;"})


def _num(v: float) -> str:
    """A coordinate to a hundredth of a pixel, without trailing zeros."""
    text = f"{v:.2f}".rstrip("0").rstrip(".")
    return "0" if text in ("-0", "") else text


def _hex(col) -> str:
    c = np.clip(np.asarray(col, dtype=np.float64), 0.0, 1.0)
    return "#" + "".join(f"{int(math.floor(v * 255.0 + 0.5)):02x}" for v in c)


def svg(items: Sequence[dict], frame: Frame, *, background=None, dpi: float | None = None,
        outline=None) -> str:
    """The display list as an SVG document, far to near.

    User units are the PNG's pixels, so ``StructureFigure.atoms`` and
    ``letters`` hold for both.  ``background`` is an rgb triple or ``None``
    for transparent; ``dpi`` sets the physical width and height, as it sets
    the PNG's ``pHYs``; ``outline`` is ``(width_px, _, rgb)``, the raster's
    tuple, and inks each atom's rim and each stick's sides.  Every element
    carries D5's class, so selecting one ``Ca1`` selects them all.
    """
    w, h = frame.width, frame.height
    if dpi is not None:
        size = f'width="{w / float(dpi):.4f}in" height="{h / float(dpi):.4f}in"'
    else:
        size = f'width="{w}" height="{h}"'
    head = [f'<svg xmlns="http://www.w3.org/2000/svg" {size} viewBox="0 0 {w} {h}">',
            "<title>rietx structure figure</title>"]
    defs: list[str] = []
    body: list[str] = []
    if background is not None:
        body.append(f'<rect class="background" width="{w}" height="{h}" '
                    f'fill="{_hex(background)}"/>')
    rim = ""
    if outline is not None:
        rim = f' stroke="{_hex(outline[2])}" stroke-width="{_num(outline[0])}"'
    gradients: dict[tuple, str] = {}
    half_gradient: dict[tuple, str] = {}

    def gradient(key, build) -> str:
        if key not in gradients:
            gid = f"g{len(gradients)}"
            gradients[key] = gid
            defs.append(build(gid))
        return gradients[key]

    for it in items:
        kind = it["kind"]
        if kind == "atom":
            focus, stops = disk_stops(it["color"], it["axes"], it["fog"], it["fog_colour"])
            key = ("atom", _hex(it["color"]), round(focus[0], 3), round(focus[1], 3),
                   round(it["fog"], 3))
            gid = gradient(key, lambda gid, f=focus, s=stops: (
                f'<radialGradient id="{gid}" cx="0.5" cy="0.5" r="0.5" '
                f'fx="{0.5 + 0.5 * f[0]:.4f}" fy="{0.5 + 0.5 * f[1]:.4f}">'
                + "".join(f'<stop offset="{t:.4f}" stop-color="{_hex(c)}"/>' for t, c in s)
                + "</radialGradient>"))
            rot = (f' transform="rotate({_num(it["angle"])} {_num(it["cx"])} {_num(it["cy"])})"'
                   if it["angle"] else "")
            body.append(f'<ellipse class="{_attr(it["cls"])}" cx="{_num(it["cx"])}" '
                        f'cy="{_num(it["cy"])}" rx="{_num(it["rx"])}" ry="{_num(it["ry"])}"'
                        f'{rot} fill="url(#{gid})"{rim}/>')
        elif kind == "ring":
            pts = " ".join(f"{_num(x)},{_num(y)}" for x, y in it["points"])
            body.append(f'<polyline class="{_attr(it["cls"])}" points="{pts}" fill="none" '
                        f'stroke="{_hex(it["color"])}" stroke-width="{_num(it["width"])}" '
                        'stroke-linecap="round" stroke-linejoin="round"/>')
        elif kind == "stick":
            g0, g1, stops = it["gradient"]
            # one gradient a half, unless depth cueing fades its pieces apart
            hid = (it["half"], round(it["fog"], 3))
            if hid not in half_gradient:
                fogged = stops
                if it["fog"]:
                    colour = np.asarray(it["fog_colour"], dtype=np.float64)
                    fogged = [(t, c * (1.0 - it["fog"]) + colour * it["fog"])
                              for t, c in stops]
                gid = f"g{len(gradients)}"
                gradients[("stick", hid)] = gid
                defs.append(
                    f'<linearGradient id="{gid}" gradientUnits="userSpaceOnUse" '
                    f'x1="{_num(g0[0])}" y1="{_num(g0[1])}" x2="{_num(g1[0])}" '
                    f'y2="{_num(g1[1])}">'
                    + "".join(f'<stop offset="{t:.4f}" stop-color="{_hex(c)}"/>'
                              for t, c in fogged)
                    + "</linearGradient>")
                half_gradient[hid] = gid
            body.append(_stick_path(it, half_gradient[hid], outline))
        elif kind == "line":
            (ax, ay), (bx, by) = it["a"], it["b"]
            body.append(f'<line class="{_attr(it["cls"])}" x1="{_num(ax)}" y1="{_num(ay)}" '
                        f'x2="{_num(bx)}" y2="{_num(by)}" stroke="{_hex(it["color"])}" '
                        f'stroke-width="{_num(it["width"])}" stroke-linecap="square"/>')
        elif kind == "face":
            pts = " ".join(f"{_num(x)},{_num(y)}" for x, y in it["points"])
            body.append(f'<polygon class="{_attr(it["cls"])}" points="{pts}" '
                        f'fill="{_hex(it["color"])}" fill-opacity="{POLY_ALPHA}"/>')
        elif kind == "text":
            body.append(f'<text class="{_attr(it["cls"])}" x="{_num(it["x"])}" '
                        f'y="{_num(it["y"])}" font-family="Helvetica, Arial, sans-serif" '
                        f'font-size="{_num(it["em"])}" text-anchor="middle" '
                        f'dominant-baseline="central" fill="{_hex(it["color"])}">'
                        f'{escape(it["text"])}</text>')
    parts = head
    if defs:
        parts += ["<defs>", *defs, "</defs>"]
    return "\n".join([*parts, *body, "</svg>", ""])


def _stick_path(it: dict, gid: str, outline) -> str:
    """A piece's outline: its sides, closed at each end by the outer half of
    the ellipse its circular section projects to."""
    (ax, ay), (bx, by) = it["a"], it["b"]
    nx, ny = it["across"]
    r, minor = it["r"], it["minor"]
    angle = _num(math.degrees(math.atan2(ny, nx)))
    p0 = (ax + nx * r, ay + ny * r)
    p1 = (bx + nx * r, by + ny * r)
    p2 = (bx - nx * r, by - ny * r)
    p3 = (ax - nx * r, ay - ny * r)
    # in the image's y-down frame sweep 1 turns from +n toward (−n_y, n_x), so
    # one flag bulges the end at b away from a and the end at a away from b
    dx, dy = bx - ax, by - ay
    sweep = 1 if (nx * dy - ny * dx) > 0 else 0
    d = (f"M{_num(p0[0])},{_num(p0[1])} L{_num(p1[0])},{_num(p1[1])} "
         f"A{_num(r)},{_num(minor)} {angle} 0 {sweep} {_num(p2[0])},{_num(p2[1])} "
         f"L{_num(p3[0])},{_num(p3[1])} "
         f"A{_num(r)},{_num(minor)} {angle} 0 {sweep} {_num(p0[0])},{_num(p0[1])} Z")
    out = f'<path class="{_attr(it["cls"])}" d="{d}" fill="url(#{gid})"/>'
    if outline is not None:
        sides = (f"M{_num(p0[0])},{_num(p0[1])} L{_num(p1[0])},{_num(p1[1])} "
                 f"M{_num(p2[0])},{_num(p2[1])} L{_num(p3[0])},{_num(p3[1])}")
        out += (f'<path class="{_attr(it["cls"])} outline" d="{sides}" fill="none" '
                f'stroke="{_hex(outline[2])}" stroke-width="{_num(outline[0])}"/>')
    return out
