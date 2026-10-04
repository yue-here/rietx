"""``render_structure``: the structure viewer's picture as an array (WP-1470).

The geometry is the GUI's (``rietx.gui.structure3d.build``), the scene rules
are the GUI's (:mod:`.scene`, held equal by a corpus), and the drawing is the
GUI's renderer solved on the CPU (:mod:`.raster`).  What this module adds is
what a browser supplied: a view named in crystallographic terms
(:mod:`.views`), a frame fitted to what is drawn, the letters (:mod:`.glyphs`),
and a PNG.

**Everything the GUI sizes in CSS pixels is scaled as the GUI scales an
export** (``gl3d.ts``, device over CSS width): a line of 2 CSS px is
``2 × long side / CANVAS_CSS_PX`` image pixels, so a 3000 px figure for print
has lines three times as wide as a 1000 px one and the same proportions.
"""

from __future__ import annotations

import struct
import zlib
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from ..theme import TOKENS
from . import cut, glyphs, raster, views
from . import report as rp
from . import scene as sc
from .report import FigureReport

#: The CSS width the GUI's pixel sizes are drawn against: an image whose long
#: side is this many pixels has the GUI's on-screen line widths and letters.
#: It is the structure canvas's long side in the GUI's default layout at a
#: 1400 × 900 window (measured 507 × 300 by ``test_structure3d_browser.py``),
#: so a render at ``size=N`` matches the GUI's own export at long side N from
#: that window.  The canvas follows the window, so this is a choice of window.
CANVAS_CSS_PX = 507.0
#: The fitted content leaves this fraction of the frame's width and height on
#: each side, ChimeraX ``view``'s default ``pad``.
FIT_PAD = 0.05
#: The GUI's a, b, c: ``--text-sm``, in CSS px.
LETTER_EM_CSS = 11.5
#: An outline is this wide, in CSS px, when ``outline=True`` (D9).
OUTLINE_CSS = 1.0
#: The default long side: an agent looking at its own picture.
DEFAULT_SIZE = 1000
MAX_SUPERSAMPLE = 4
MODES = ("ball", "ellipsoid")
#: The places tried for a site label, in order, as (right, up) signs: up and
#: to the right first, which is where every label went before #666.
LABEL_ANCHORS = ((1, 1), (1, 0), (0, 1), (-1, 1), (-1, 0), (1, -1), (0, -1), (-1, -1))
#: A label beside the atom on a diagonal has the middle of its near side this
#: many projected radii right or left of the atom's centre and as many above
#: or below it.  On an axis it is this times √2 out, the same distance.
LABEL_OFFSET = 0.72


@dataclass(frozen=True)
class StructureFigure:
    """What :func:`render_structure` drew.

    ``image`` is ``height × width × 4`` ``uint8``, straight alpha;
    ``np.asarray(figure)`` and ``plt.imshow(figure)`` both take it.
    ``rotation`` is the view drawn, rows the screen's right, up and toward the
    viewer in the structure's Cartesian Å: pass it back as ``view=`` for the
    same picture.  ``origin`` is where pixel (0, 0), the top-left corner, sits
    in the view plane, in Å along the first two rows of ``rotation``.
    ``rotation``, ``origin`` and ``pixels_per_angstrom`` make the map
    :meth:`to_px` applies.
    ``atoms`` has one entry per atom drawn, ``letters`` one per a, b, c: where
    each landed, in pixels from the top-left corner, so a caller can annotate
    without re-projecting.  ``path`` is the PNG written, if any.
    ``palette`` is each site label drawn and the colour it is drawn in, as
    ``#rrggbb`` before any dimming of the images outside the cell, for a legend
    drawn beside the figure.  A site recoloured in part
    (:func:`~rietx.viz.recolour`) appears again as ``"<label> (recoloured)"``.

    ``report`` is the numbers a look would give (:class:`~.report.FigureReport`).
    ``candidates`` is empty unless ``view="auto"``, and then the best few views
    the search ranked, each a ``view`` to pass back with the same ``up`` and
    ``turn``, the ``hidden`` share and the ``empty`` share it read at 256 px
    from atoms and bonds alone; the first is the one drawn.  ``recipe`` is the
    call that draws this picture again: ``render_structure(structure,
    **figure.recipe)``, with the same first argument, gives ``image`` bit for
    bit.  It holds every other argument as passed but ``path``,
    JSON-serialisable, with ``view`` the rotation drawn and ``up`` and ``turn``
    folded into it.  The first argument is the caller's to keep.
    """
    image: np.ndarray
    rotation: list[list[float]]
    pixels_per_angstrom: float
    origin: list[float]
    atoms: list[dict]
    letters: list[dict]
    path: str | None = None
    palette: dict[str, str] = field(default_factory=dict)
    report: FigureReport | None = None
    candidates: list[dict] = field(default_factory=list)
    recipe: dict = field(default_factory=dict)

    def __array__(self, dtype=None, copy=None):
        image = self.image if dtype is None else self.image.astype(dtype, copy=False)
        # numpy 2 trusts copy=True to have copied, so np.array(figure) must
        # not hand out the figure's own buffer
        return image.copy() if copy else image

    def to_px(self, points) -> np.ndarray:
        """Where Cartesian points land in ``image``, in pixels.

        ``points`` is in the structure's Cartesian Å, shape ``(3,)`` or
        ``(N, 3)``, the frame of ``build``'s ``pos`` and ``lattice``.  The
        answer is ``(x, y)`` from the top-left corner, x right and y down,
        shape ``(2,)`` or ``(N, 2)``: the map that placed ``atoms``.  Depth
        is dropped, since the projection is parallel.  A direction is
        ``to_px(v) - to_px([0, 0, 0])``, for an axis triad drawn beside the
        figure.
        """
        p = np.asarray(points, dtype=np.float64)
        if p.ndim not in (1, 2) or p.shape[-1] != 3:
            raise ValueError(f"points of shape {p.shape}: give (3,) or (N, 3), in Å")
        r = np.asarray(self.rotation, dtype=np.float64)
        x = (p @ r[0] - self.origin[0]) * self.pixels_per_angstrom
        y = (self.origin[1] - p @ r[1]) * self.pixels_per_angstrom
        return np.stack([x, y], axis=-1)


def _colour(value) -> tuple[float, float, float] | None:
    if value is None:
        return None
    if isinstance(value, str):
        hex_ = cut.NAMED_COLOURS.get(value.lower(), value)
        if not sc._HEX.match(hex_):
            raise ValueError(f"background {value!r}: give 'white', 'black', "
                             "'#rrggbb', three channels in 0..1, or None")
        return tuple(sc.rgb(hex_))
    rgb = tuple(float(v) for v in value)
    if len(rgb) != 3 or not all(0.0 <= v <= 1.0 for v in rgb):
        raise ValueError(f"background {value!r}: three channels, each in 0..1")
    return rgb


def _species(geometry: Mapping, names) -> list[str]:
    """The species ``hidden=`` names: a species as the legend spells it
    (``"Na1+"``), or an element, which takes all of its species.  A name the
    phase does not have is refused, since hiding nothing looks like success."""
    if isinstance(names, str):
        names = [names]
    sites = geometry["sites"]
    out: list[str] = []
    for name in names:
        match = [s["species"] for s in sites if name in (s["species"], s["element"])]
        if not match:
            have = sorted({s["species"] for s in sites})
            route = ""
            if any(s["label"] == name for s in sites):
                route = (f"; {name!r} is a site label, and one site is left out by a "
                         f"mask: keep(g, ~select(g, label={name!r}))")
            raise ValueError(f"hidden {name!r}: this phase has no such species or "
                             f"element; its species are {have}{route}")
        out += [m for m in match if m not in out]
    return out


def _site_colours(geometry: Mapping) -> Mapping:
    """The geometry with every site colour as ``#rrggbb``, refused otherwise.

    ``scene.rgb`` draws anything else mid-grey, which is the GUI's rule and
    stays.  Here an edited dict is being drawn, and a colour that changes
    nothing on the screen looks like success, as ``hidden=`` has it.
    """
    colours = []
    for k, site in enumerate(geometry["sites"]):
        try:
            colours.append(cut.site_colour(site["color"]))
        except ValueError as e:
            raise ValueError(f"sites[{k}] ({site['label']}): {e}") from None
    if colours == [s["color"] for s in geometry["sites"]]:
        return geometry
    return {**geometry, "sites": [{**s, "color": c}
                                  for s, c in zip(geometry["sites"], colours)]}


def _palette(geometry: Mapping, scene: dict) -> dict[str, str]:
    drawn = {geometry["atoms"][a["index"]]["site"] for a in scene["atoms"]}
    out: dict[str, str] = {}
    for k in sorted(drawn):
        site = geometry["sites"][k]
        name = base = site["label"]
        n = 1
        while name in out and out[name] != site["color"]:
            n += 1
            name = f"{base} (recoloured)" if n == 2 else f"{base} (recoloured {n - 1})"
        out.setdefault(name, site["color"])
    return out


def _formulas(geometry: Mapping, polyhedra: Mapping) -> dict:
    """``polyhedra=`` as a formula switch, refused when it names a formula the
    phase has no polyhedron for: switching nothing looks like success, as
    ``hidden=`` has it, and ``"AlF6"`` for ``"AlF₆"`` is the easy slip."""
    have = {sc.polyhedron_formula(geometry, p) for p in geometry["polyhedra"]}
    unknown = sorted(set(polyhedra) - have)
    if unknown:
        raise ValueError(f"polyhedra {unknown}: this phase has no such polyhedron; "
                         f"its formulas are {sorted(have)}")
    return dict(polyhedra)


def _label_reach(scene: dict, geometry: Mapping, R: np.ndarray):
    """Points the frame must hold for the atom labels, in Å, and how far past
    them a label reaches, in CSS px, whichever of :data:`LABEL_ANCHORS` it
    takes (:func:`_labels`).

    Every anchor's near side lies within ``LABEL_OFFSET·√2`` projected radii
    of the atom's centre along x and along y, so the four points that far out
    bound them.  Past those a label runs on by at most its width, or by its
    whole height when it sits above or below.
    """
    points, reach = [], 0.0
    full = 2.0 * glyphs.HALF_BOX_UNITS * LETTER_EM_CSS / glyphs.EM_UNITS
    for a in scene["atoms"]:
        record = geometry["atoms"][a["index"]]
        if record["boundary"]:
            continue
        m = R @ np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        r = max(float(np.linalg.norm(m[0])), float(np.linalg.norm(m[1])))
        out = LABEL_OFFSET * np.sqrt(2.0) * r
        c = R @ np.asarray(a["pos"], dtype=np.float64)
        points += [R.T @ (c + step) for step in ([out, 0.0, 0.0], [-out, 0.0, 0.0],
                                                 [0.0, out, 0.0], [0.0, -out, 0.0])]
        text = geometry["sites"][record["site"]]["label"]
        reach = max(reach, glyphs.width(text, LETTER_EM_CSS), full)
    return points, reach


def _extent(scene: dict, R: np.ndarray, with_labels: bool, extra=()):
    """The drawn content's box in view coordinates, Å: (x0, x1, y0, y1).
    ``extra`` is further points, in the structure's Å, the box must hold."""
    xs, ys = [], []
    for a in scene["atoms"]:
        c = R @ np.asarray(a["pos"], dtype=np.float64)
        m = R @ np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        hx, hy = float(np.linalg.norm(m[0])), float(np.linalg.norm(m[1]))
        xs += [c[0] - hx, c[0] + hx]
        ys += [c[1] - hy, c[1] + hy]
    for h in scene["halves"]:
        for p in (h["from"], h["to"]):
            c = R @ np.asarray(p, dtype=np.float64)
            xs += [c[0] - h["radius"], c[0] + h["radius"]]
            ys += [c[1] - h["radius"], c[1] + h["radius"]]
    points = [p for line in scene["lines"] for p in (line["a"], line["b"])]
    points += [f["triangles"][k:k + 3] for f in scene["faces"]
               for k in range(0, len(f["triangles"]), 3)]
    if with_labels:
        points += [label["pos"] for label in scene["labels"]]
    points += list(extra)
    for p in points:
        c = R @ np.asarray(p, dtype=np.float64)
        xs.append(c[0])
        ys.append(c[1])
    if not xs:
        return -1.0, 1.0, -1.0, 1.0
    return min(xs), max(xs), min(ys), max(ys)


def _fit(extent, size, margin_css: float) -> raster.Frame:
    """Scale and place the content box in the frame (D12, D13).

    ``size`` is the long side, the other following the content, or
    ``(width, height)`` with the content fitted inside.  ``margin_css`` is
    what pixel-sized things (a line's half-width, a letter) add beyond the
    box, in CSS px.
    """
    x0, x1, y0, y1 = extent
    bw, bh = max(x1 - x0, 1e-6), max(y1 - y0, 1e-6)
    keep = 1.0 - 2.0 * FIT_PAD
    if isinstance(size, (tuple, list)):
        if len(size) != 2:
            raise ValueError(f"size {size!r}: the long side, or (width, height)")
        width, height = (int(v) for v in size)
        if width < 1 or height < 1:
            raise ValueError(f"size {size!r}: both sides at least one pixel")
        scale = max(width, height) / CANVAS_CSS_PX
        m = margin_css * scale
        ppa = min((width * keep - 2 * m) / bw, (height * keep - 2 * m) / bh)
    else:
        long = int(size)
        if long < 16:
            raise ValueError(f"size {size!r}: at least 16 pixels")
        scale = long / CANVAS_CSS_PX
        m = margin_css * scale
        ppa = (long * keep - 2 * m) / max(bw, bh)
        other = max(1, round((min(bw, bh) * ppa + 2 * m) / keep))
        width, height = (long, other) if bw >= bh else (other, long)
    if not ppa > 0:
        raise ValueError(f"size {size!r} leaves no room for the structure")
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    return raster.Frame(width=width, height=height, x0=cx - width / (2 * ppa),
                        y0=cy + height / (2 * ppa), ppa=ppa, px_scale=scale)


def gui_frame(scene: dict, R, width: int, height: int, css_width: float) -> raster.Frame:
    """The GUI's framing for one canvas: ``pixelsPerAngstrom`` at zoom 1, no
    pan, centred on the scene's centre.  The browser parity row draws with it,
    because the fitted frame is tighter and would otherwise be what it
    measured."""
    R = np.asarray(R, dtype=np.float64)
    ppa = min(width, height) / (2 * scene["radius"])
    c = R @ np.asarray(scene["center"], dtype=np.float64)
    return raster.Frame(width=width, height=height, x0=c[0] - width / (2 * ppa),
                        y0=c[1] + height / (2 * ppa), ppa=ppa, px_scale=width / css_width)


def _drawn_shapes(scene: dict, arrays: dict, R, frame: raster.Frame) -> dict:
    """The atoms and bond halves as drawn, projected to image pixels: what a
    label is kept clear of and counted against.

    An atom is the ellipse its ellipsoid projects to.  With ``A`` the first
    two rows of its axes in the view, in pixels, ``S = AAᵀ`` and the ellipse
    is zᵀS⁻¹z ≤ 1 about its centre.  A ball's is a disc.  A bond half is the
    segment it projects to, widened by its stick radius on every side.
    ``arrays`` is :func:`.raster.scene_arrays` of ``scene``, which leaves out
    an atom with no inverse, as the drawing does.
    """
    R = np.asarray(R, dtype=np.float64)
    c = arrays["pos"] @ R.T
    m = np.einsum("ij,njk->nik", R[:2], arrays["shape"]) * frame.ppa
    s = m @ m.transpose(0, 2, 1)
    a = arrays["from"] @ R.T
    b = arrays["to"] @ R.T

    def u(x):
        return (x - frame.x0) * frame.ppa

    def v(y):
        return (frame.y0 - y) * frame.ppa

    sxx, syy = s[:, 0, 0], s[:, 1, 1]
    px, py, qx, qy = u(a[:, 0]), v(a[:, 1]), u(b[:, 0]), v(b[:, 1])
    r = arrays["radius"] * frame.ppa
    return {"index": arrays["index"], "cx": u(c[:, 0]), "cy": v(c[:, 1]),
            # image y runs down, which turns the sign of the cross term
            "sxx": sxx, "syy": syy, "sxy": -s[:, 0, 1],
            "hx": np.sqrt(sxx), "hy": np.sqrt(syy),
            "px": px, "py": py, "qx": qx, "qy": qy, "r": r,
            "lx": np.minimum(px, qx) - r, "ux": np.maximum(px, qx) + r,
            "ly": np.minimum(py, qy) - r, "uy": np.maximum(py, qy) + r,
            "bond": np.array([h["bond"] for h in scene["halves"]], dtype=np.int64)}


def _on_atoms(box: np.ndarray, sh: dict, k: np.ndarray) -> np.ndarray:
    """Which of atoms ``k`` each box ``(x0, x1, y0, y1)`` meets, as a
    boxes × atoms mask.

    About the atom's centre the ellipse is zᵀ adj(S) z ≤ det S.  The form is
    convex, so over a box not holding the centre its least value lies on an
    edge, where it is a parabola whose minimum is clamped to the edge's span.
    """
    x0 = box[:, None, 0] - sh["cx"][k]
    x1 = box[:, None, 1] - sh["cx"][k]
    y0 = box[:, None, 2] - sh["cy"][k]
    y1 = box[:, None, 3] - sh["cy"][k]
    sxx, syy, sxy = sh["sxx"][k], sh["syy"][k], sh["sxy"][k]
    det = sxx * syy - sxy * sxy
    sy = np.divide(sxy, sxx, out=np.zeros_like(sxx), where=sxx > 0)
    sx = np.divide(sxy, syy, out=np.zeros_like(syy), where=syy > 0)

    def form(x, y):
        return syy * x * x - 2.0 * sxy * x * y + sxx * y * y

    # the two upright edges, then the two level ones
    xs, ys = np.stack([x0, x1]), np.stack([y0, y1])
    least = np.minimum(form(xs, np.clip(sy * xs, y0, y1)).min(axis=0),
                       form(np.clip(sx * ys, x0, x1), ys).min(axis=0))
    inside = (x0 < 0.0) & (0.0 < x1) & (y0 < 0.0) & (0.0 < y1)
    return (inside | (least < det)) & (det > 0.0)


def _on_halves(box: np.ndarray, sh: dict, k: np.ndarray) -> np.ndarray:
    """Which of bond halves ``k`` each box meets, as a boxes × halves mask.

    A widened segment meets a box when the segment crosses it, or passes
    within its stick radius of it.  The segment crosses the box when no axis
    separates them, of the three that could: x, y and the segment's normal.
    Apart, two convex shapes are nearest at a corner of one, so the distance
    is the least of the segment's ends to the box and the box's corners to
    the segment.
    """
    x0, x1 = box[:, None, 0], box[:, None, 1]
    y0, y1 = box[:, None, 2], box[:, None, 3]
    px, py, qx, qy = sh["px"][k], sh["py"][k], sh["qx"][k], sh["qy"][k]
    dx, dy = qx - px, qy - py
    crossing = ((np.minimum(px, qx) <= x1) & (x0 <= np.maximum(px, qx))
                & (np.minimum(py, qy) <= y1) & (y0 <= np.maximum(py, qy))
                & (np.abs(dx * ((y0 + y1) / 2 - py) - dy * ((x0 + x1) / 2 - px))
                   <= (np.abs(dy) * (x1 - x0) + np.abs(dx) * (y1 - y0)) / 2))
    ex, ey = np.stack([px, qx])[:, None], np.stack([py, qy])[:, None]
    gx = np.maximum(np.maximum(x0 - ex, ex - x1), 0.0)
    gy = np.maximum(np.maximum(y0 - ey, ey - y1), 0.0)
    near = (gx * gx + gy * gy).min(axis=0)
    cx, cy = np.stack([x0, x0, x1, x1]), np.stack([y0, y1, y0, y1])
    length2 = dx * dx + dy * dy
    along = (cx - px) * dx + (cy - py) * dy
    t = np.clip(np.divide(along, length2, out=np.zeros_like(along), where=length2 > 0.0),
                0.0, 1.0)
    fx, fy = px + t * dx - cx, py + t * dy - cy
    near = np.minimum(near, (fx * fx + fy * fy).min(axis=0))
    r = sh["r"][k]
    return crossing | (near < r * r)


def _hits(box: np.ndarray, own: int, sh: dict) -> tuple[np.ndarray, np.ndarray]:
    """For each label box ``(x0, x1, y0, y1)``, how many drawn atoms other
    than atom ``own`` it meets, and how many bonds.  A bond counts once
    however many of its halves the box meets.  Only the shapes whose bounding
    boxes meet the boxes' union are tested, so a label costs what is near it.
    """
    lo_x, hi_x = box[:, 0].min(), box[:, 1].max()
    lo_y, hi_y = box[:, 2].min(), box[:, 3].max()
    a = np.flatnonzero((sh["cx"] - sh["hx"] < hi_x) & (lo_x < sh["cx"] + sh["hx"])
                       & (sh["cy"] - sh["hy"] < hi_y) & (lo_y < sh["cy"] + sh["hy"])
                       & (sh["index"] != own))
    h = np.flatnonzero((sh["lx"] < hi_x) & (lo_x < sh["ux"])
                       & (sh["ly"] < hi_y) & (lo_y < sh["uy"]))
    atoms = _on_atoms(box, sh, a).sum(axis=1) if len(a) else np.zeros(len(box), np.int64)
    if not len(h):
        return atoms, np.zeros(len(box), np.int64)
    # a bond's halves are drawn one after the other, so its halves are a run
    bond = sh["bond"][h]
    runs = np.flatnonzero(np.r_[True, bond[1:] != bond[:-1]])
    bonds = np.logical_or.reduceat(_on_halves(box, sh, h), runs, axis=1).sum(axis=1)
    return atoms, bonds


def _labels(scene: dict, geometry: Mapping, R, frame: raster.Frame, arrays: dict, *,
            axis_labels: bool, atom_labels: bool) -> list[tuple]:
    """Every string drawn, as ``(text, x, y, is_axis, half_height, atoms,
    bonds)`` centred on image pixel ``(x, y)``, ``half_height`` in pixels.

    a, b and c sit at their anchors.  Each site label is tried at the places
    :data:`LABEL_ANCHORS` names, in order, and takes the first whose box meets
    no drawn atom but its own, no bond and no string already placed.  Where
    every place meets something it takes the one meeting fewest, the earlier
    on a tie, so the same scene gives the same picture.  ``atoms`` and
    ``bonds`` are how many of each the string's box meets where it was put,
    by :func:`_hits`, which is the test the placement made.  ``arrays`` is
    :func:`.raster.scene_arrays` of ``scene``.
    """
    R = np.asarray(R, dtype=np.float64)
    em = LETTER_EM_CSS * frame.px_scale
    half = glyphs.HALF_BOX_UNITS * em / glyphs.EM_UNITS
    if not (axis_labels or atom_labels):
        return []
    sh = _drawn_shapes(scene, arrays, R, frame)

    def at(p):
        c = R @ np.asarray(p, dtype=np.float64)
        return (c[0] - frame.x0) * frame.ppa, (frame.y0 - c[1]) * frame.ppa

    out = []
    placed = np.empty((len(scene["labels"]) + len(scene["atoms"]), 4))
    if axis_labels:
        for label in scene["labels"]:
            x, y = at(label["pos"])
            w = glyphs.width(label["text"], em)
            placed[len(out)] = (x - w / 2, x + w / 2, y - half, y + half)
            atoms, bonds = _hits(placed[len(out):len(out) + 1], -1, sh)
            out.append((label["text"], x, y, True, half, int(atoms[0]), int(bonds[0])))
    if not atom_labels:
        return out
    signs = np.asarray(LABEL_ANCHORS, dtype=np.float64)
    diagonal = (signs[:, 0] != 0.0) & (signs[:, 1] != 0.0)
    level = signs[:, 1] == 0.0
    for a in scene["atoms"]:
        if geometry["atoms"][a["index"]]["boundary"]:
            continue
        text = geometry["sites"][geometry["atoms"][a["index"]]["site"]]["label"]
        m = R @ np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        r = max(float(np.linalg.norm(m[0])), float(np.linalg.norm(m[1]))) * frame.ppa
        x, y = at(a["pos"])
        w = glyphs.width(text, em)
        # the middle of the label's near side sits d right or left of the
        # centre and d above or below it on a diagonal, and d·√2 out on an axis
        d = LABEL_OFFSET * r
        far = d * np.sqrt(2.0)
        xs = x + signs[:, 0] * (np.where(diagonal, d, far) + w / 2)
        ys = y - signs[:, 1] * np.where(diagonal, d, np.where(level, 0.0, far + half))
        boxes = np.stack([xs - w / 2, xs + w / 2, ys - half, ys + half], axis=1)
        atoms, bonds = _hits(boxes, a["index"], sh)
        q = placed[:len(out)]
        letters = ((boxes[:, None, 0] < q[None, :, 1]) & (q[None, :, 0] < boxes[:, None, 1])
                   & (boxes[:, None, 2] < q[None, :, 3])
                   & (q[None, :, 2] < boxes[:, None, 3])).sum(axis=1)
        k = int(np.argmin(atoms + bonds + letters))
        placed[len(out)] = boxes[k]
        out.append((text, float(xs[k]), float(ys[k]), False, half, int(atoms[k]), int(bonds[k])))
    return out


def text_strokes(labels: list[tuple], frame: raster.Frame, *, accent: str, ink: str):
    """The letters :func:`_labels` placed, as strokes, and where each a, b
    and c landed."""
    em = LETTER_EM_CSS * frame.px_scale
    strokes, letters = [], []
    for text, x, y, is_axis, *_ in labels:
        strokes += glyphs.strokes(text, x, y, em, sc.rgb(accent if is_axis else ink))
        if is_axis:
            letters.append({"text": text, "x": x, "y": y})
    return strokes, letters


def _label_overlaps(labels, frame: raster.Frame) -> int:
    """Pairs of drawn strings whose boxes intersect, the box being the string's
    advance wide and the font's box tall."""
    em = LETTER_EM_CSS * frame.px_scale
    box = np.array([[x - glyphs.width(t, em) / 2, x + glyphs.width(t, em) / 2, y - h, y + h]
                    for t, x, y, _, h, *_ in labels], dtype=np.float64).reshape(-1, 4)
    n, total = len(box), 0
    for start in range(0, n, 512):
        c = box[start:start + 512]
        hit = ((c[:, None, 0] < box[None, :, 1]) & (box[None, :, 0] < c[:, None, 1])
               & (c[:, None, 2] < box[None, :, 3]) & (box[None, :, 2] < c[:, None, 3]))
        later = np.arange(start, start + len(c))[:, None] < np.arange(n)[None, :]
        total += int((hit & later).sum())
    return total


def _dangling(geometry: Mapping, scene: dict) -> int:
    """Bond halves drawn toward an atom that is not: the half ends in mid-air.

    A half left by ``hidden=`` counts too.  The legend's switch takes a
    species' own halves and leaves its neighbours' pointing at it, and round B
    printed this count as 0 on a calcite covered in O stubs, which is what an
    agent reading the report rather than the picture was told (WP-1529).

    So does a bond whose far end is not in the geometry at all, as ``build``'s
    atom cap leaves it: HKUST-1's cell trimmed to 400 atoms drew 96 such
    sticks while this count read 0, because every atom it held was drawn
    (#665).
    """
    if not scene["halves"]:
        return 0
    drawn = {a["index"] for a in scene["atoms"]}
    atoms, bonds = geometry["atoms"], geometry["bonds"]
    far = cut._far(geometry, missing=-1)
    if len(drawn) == len(atoms) and (far >= 0).all():
        return 0
    count = 0
    for h in scene["halves"]:
        bond = bonds[h["bond"]]
        end = int(far[h["bond"]]) if list(bond["a"]) == h["from"] else bond["i"]
        count += end not in drawn
    return count


def _plain(value):
    """``value`` with tuples and arrays as lists and numpy scalars as numbers,
    which is what JSON keeps of them."""
    if isinstance(value, np.ndarray):
        value = value.tolist()
    elif isinstance(value, np.generic):
        return value.item()
    return [_plain(v) for v in value] if isinstance(value, (tuple, list)) else value


def _empty(image: np.ndarray, bg) -> float:
    """The share of pixels nothing was drawn on: transparent, or the
    background colour exactly."""
    # one 32-bit compare a pixel: the four bytes read as a little-endian word,
    # alpha the top one
    word = np.ascontiguousarray(image).view("<u4")[..., 0]
    if bg is None:
        return float(((word >> 24) == 0).mean())
    r, g, b = (int(v) for v in np.floor(np.asarray(bg) * 255.0 + 0.5))
    return float((word == (r | g << 8 | b << 16 | 255 << 24)).mean())


def _png(path: Path, image: np.ndarray, dpi: float | None) -> None:
    """RGBA, 8 bits, straight alpha as the PNG standard has it, with an
    ``sRGB`` chunk and, when ``dpi`` is given, a ``pHYs`` chunk (D7, D13)."""
    height, width, _ = image.shape

    def chunk(kind: bytes, data: bytes) -> bytes:
        return (struct.pack(">I", len(data)) + kind + data
                + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF))

    raw = b"".join(b"\x00" + image[y].tobytes() for y in range(height))
    parts = [b"\x89PNG\r\n\x1a\n",
             chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)),
             chunk(b"sRGB", b"\x00")]
    if dpi is not None:
        per_metre = round(float(dpi) / 0.0254)
        parts.append(chunk(b"pHYs", struct.pack(">IIB", per_metre, per_metre, 1)))
    parts += [chunk(b"IDAT", zlib.compress(raw, 6)), chunk(b"IEND", b"")]
    path.write_bytes(b"".join(parts))


def render_structure(structure, phase: int = 0, *, mode: str = "ball", view="opening",
                     up=None, turn: str | None = None, size=DEFAULT_SIZE,
                     supersample: int = 2, probability: float | None = None,
                     bond_tolerance: float | None = None, max_atoms: int | None = None,
                     exaggeration: float = 1.0, stick: float = 1.0,
                     hidden=(), boundary: bool = True, cell: bool = True, polyhedra=None,
                     axis_labels: bool = True, atom_labels: bool = False,
                     outline: bool = False, background="white", path=None,
                     dpi: float | None = None) -> StructureFigure:
    """Draw one phase of a structure as the GUI's structure viewer draws it.

    ``structure`` is a :class:`~rietx.Structure`, or the dict
    ``rietx.gui.structure3d.build`` returns, edited as you like (a colour, a
    radius, a hidden site): the renderer draws what the dict says (D10).

    From a structure the cell is drawn whole or not at all.  ``max_atoms``
    (default ``rietx.gui.structure3d.MAX_ATOMS``, 400) bounds the cell's own
    atoms with their copies on its faces, and a cell past it raises naming its
    count, as ``build(extent=...)`` raises on a block.  The bonded neighbours
    and polyhedron vertices drawn outside the cell are not counted against it.
    A dict says what was built, so ``probability``, ``bond_tolerance`` and
    ``max_atoms`` are refused with one; the report's ``cut`` counts what its
    atom cap left out.

    ``mode`` is ``"ball"`` or ``"ellipsoid"``; ``probability`` the ellipsoids'
    level (default 50 %) and ``exaggeration`` a drawing scale on top of it,
    which is not a probability.  ``stick`` multiplies the mode's stick radius.
    That radius is 0.08 Å in ball mode.  In ellipsoid mode it is half the
    smallest drawn semi-axis, from 0.02 Å to 0.08 Å, and the 0.02 Å floor does
    not scale.  At ``stick ≤ 1`` every ball stays wider than its stick.  Every
    stick's rim also stays inside the ellipsoid it ends in, because a rim no
    wider than half the smallest semi-axis lies inside the inscribed sphere.
    A larger ``stick`` may poke through.  ``bond_tolerance`` is the bond
    threshold as a multiple of rᵢ + rⱼ.  ``hidden`` is species to leave out,
    with their bond halves; the other half of each bond stays, as a stub the
    report counts in ``dangling_bonds``, and ``keep`` with a mask removes a
    species with its bonds whole.  ``boundary=False`` leaves out the images
    outside the cell, or outside an ``extent`` block; the bonds that reach
    them stay, as stubs the report counts in ``dangling_bonds``.
    ``cell=False`` leaves out the cell's frame, and the a, b and c that label
    its edges go with it, so the view is fitted to the atoms alone.
    ``polyhedra`` is ``None`` for the mode's default (on for balls, off for
    ellipsoids), ``True``/``False``, or ``{formula: bool}`` switching formulas
    as the GUI's legend does (``{"AlF₆": False}``).

    ``view``, ``up`` and ``turn`` say where it is seen from
    (:func:`rietx.viz.figure3d.views.resolve`): ``"opening"``, ``"a"``,
    ``"b"``, ``"c"``, ``[u, v, w]``, ``{"hkl": (h, k, l)}`` or a rotation,
    with ``up`` defaulting to c up (b up when looking down c) and ``turn``
    ASE's ``"30y,-15x"``.  Every view is fitted to the frame.  ``"auto"``
    draws the low-index direction (indices to 2, or the opening view) that
    hides the fewest atoms and then leaves the least of the frame empty, and
    returns the runners-up in ``candidates``; the figure's ``report`` says
    what is still hidden, for ``turn=`` to work on.

    ``size`` is the long side in pixels, or ``(width, height)``;
    ``supersample`` the antialiasing, 1 to 4 samples a side.  ``background``
    is ``"white"``, ``"black"``, ``"#rrggbb"``, three channels in 0..1, or
    ``None`` for transparent.  ``outline=True`` inks silhouettes, off by
    default because the GUI draws none.  ``atom_labels=True`` writes each site
    label beside its atom, in the first of eight places around it clear of
    atoms, bonds and the labels before it.  The report counts what each label
    still meets.  ``path`` writes a PNG, with ``dpi`` only in its ``pHYs``
    chunk.
    """
    from ...gui import structure3d as s3

    if mode not in MODES:
        raise ValueError(f"mode {mode!r}: give one of {MODES}")
    s = int(supersample)
    if not 1 <= s <= MAX_SUPERSAMPLE:
        raise ValueError(f"supersample {supersample!r}: 1 to {MAX_SUPERSAMPLE}")
    if path is not None and Path(path).suffix.lower() != ".png":
        raise ValueError("render_structure writes PNG only: JPEG's block artifacts "
                         "smear the thin rings and lines a structure figure is read by")
    if dpi is not None and not 0 < float(dpi) < 1e6:
        raise ValueError(f"dpi {dpi!r}: a positive resolution, in dots per inch")
    if (isinstance(stick, bool) or not isinstance(stick, (int, float, np.integer, np.floating))
            or not 0 < stick < np.inf):
        raise ValueError(f"stick {stick!r}: a positive, finite multiple of the mode's "
                         "stick radius (1 draws the default)")
    if max_atoms is not None and (not isinstance(max_atoms, (int, np.integer))
                                  or isinstance(max_atoms, bool) or max_atoms < 1):
        raise ValueError(f"max_atoms {max_atoms!r}: a whole number of atoms, at least 1")
    if isinstance(structure, Mapping):
        if probability is not None or bond_tolerance is not None or max_atoms is not None:
            raise ValueError("probability=, bond_tolerance= and max_atoms= build the "
                             "geometry; a geometry dict has already been built with its own")
        geometry = structure
    else:
        # the cell is held to the cap, the rule build(extent=...) keeps for a
        # block: a trimmed cell draws broken bonds that read as a wrong
        # structure (#665).  Built at the cap first, so a large cell raises
        # after 400 atoms' work, and again uncapped only where the cap kept
        # out the neighbours or polyhedra past the cell, which it does not bound
        cap = s3.MAX_ATOMS if max_atoms is None else int(max_atoms)
        built = dict(
            probability=s3.DEFAULT_PROBABILITY if probability is None else probability,
            bond_tolerance=s3.BOND_TOLERANCE if bond_tolerance is None else bond_tolerance)
        geometry = s3.build(structure, phase, max_atoms=cap, **built)
        lost = geometry["cut"]
        if lost["atoms"]:
            n_cell = cap + lost["atoms"]
            raise ValueError(f"phase {phase}: {n_cell} atoms in the cell with its face "
                             f"copies, past max_atoms={cap}; pass max_atoms={n_cell} or "
                             "more to draw it whole")
        if lost["neighbours"] or lost["polyhedra"]:
            geometry = s3.build(structure, phase, max_atoms=s3._UNCAPPED, **built)
    geometry = _site_colours(geometry)
    bg = _colour(background)
    dark = bg is not None and sum(w * v for w, v in zip(sc.LOOK["luma"], bg)) < 0.5
    tokens = TOKENS["dark" if dark else "light"]
    hidden_asked = [hidden] if isinstance(hidden, str) else list(hidden)
    hidden = _species(geometry, hidden_asked)
    if polyhedra is None:
        on, formulas = mode == "ball", None
    elif isinstance(polyhedra, Mapping):
        on, formulas = True, _formulas(geometry, polyhedra)
    else:
        on, formulas = bool(polyhedra), None
    shown = sc.shown_polyhedra(geometry, on, formulas, hidden, boundary)
    # the frame is the payload's ``edges``; the fit reads what the scene
    # draws, so a frame left out stops holding the view open (WP-1533)
    scene = sc.build_scene(geometry if cell else {**geometry, "edges": []}, mode,
                           hidden=hidden, show_boundary=boundary,
                           exaggeration=exaggeration, polyhedra=shown,
                           cell=tokens["--accent"], stick=float(stick))
    asked_axis_labels, axis_labels = axis_labels, bool(axis_labels) and bool(cell)
    margin = max([0.5 * line["width"] for line in scene["lines"]] + [0.0])
    if axis_labels:
        margin = max(margin, 0.6 * LETTER_EM_CSS)
    probe = rp.probe(scene, geometry, size, margin + 1.0, _fit, axis_labels)
    candidates: list[dict] = []
    if isinstance(view, str) and view == "auto":
        view, candidates = rp.choose_view(geometry, probe, up, turn)
    R = views.resolve(geometry, view, up, turn)
    extra = ()
    if atom_labels:
        extra, reach = _label_reach(scene, geometry, R)
        margin = max(margin, reach, 0.6 * LETTER_EM_CSS)
    frame = _fit(_extent(scene, R, axis_labels, extra), size, margin + 1.0)
    labels = _labels(scene, geometry, R, frame, probe.arrays, axis_labels=axis_labels,
                     atom_labels=atom_labels)
    strokes, letters = text_strokes(labels, frame, accent=tokens["--accent"],
                                    ink=tokens["--fg"])
    ol = None
    if outline:
        step = sc.stick_radius(geometry, mode, exaggeration, float(stick))
        ol = (OUTLINE_CSS * frame.px_scale, step, sc.rgb(tokens["--fg"]))
    image = raster.draw(scene, R, frame, supersample=s, background=bg, text=strokes,
                        outline=ol)
    atoms = []
    for a in scene["atoms"]:
        c = R @ np.asarray(a["pos"], dtype=np.float64)
        record = geometry["atoms"][a["index"]]
        site = geometry["sites"][record["site"]]
        atoms.append({"index": a["index"], "site": record["site"], "label": site["label"],
                      "species": site["species"], "boundary": record["boundary"],
                      "x": (c[0] - frame.x0) * frame.ppa, "y": (frame.y0 - c[1]) * frame.ppa,
                      "depth": float(c[2])})
    written = None
    if path is not None:
        target = Path(path)
        _png(target, image, dpi)
        written = str(target)
    seen = rp.look(probe, R)
    warnings = []
    if mode == "ellipsoid":
        flat = sorted({geometry["sites"][geometry["atoms"][a["index"]]["site"]]["label"]
                       for a in scene["atoms"]
                       if geometry["sites"][geometry["atoms"][a["index"]]["site"]]["npd"]})
        warnings += [f"{label}: its displacement tensor is not positive definite, so its "
                     "ellipsoid is drawn flat" for label in flat]
    if seen.unjudged:
        long_side = max(probe.size) if isinstance(probe.size, tuple) else probe.size
        warnings.append(f"{seen.unjudged} atoms cover less than one sample at {long_side} px "
                        "and are not counted in hidden")
    cuts = {"atoms": 0, "neighbours": 0, "segments": 0, "polyhedra": 0, "bonds": 0,
            **geometry.get("cut", {})}
    capped = [f"{n} {what}" for n, what in (
        (cuts["atoms"], "of the cell's atoms"),
        (cuts["neighbours"], "bonded neighbours outside it"),
        (len(geometry.get("polyhedra_dropped", [])), "coordination polyhedra")) if n]
    if capped:
        warnings.append(f"build's atom cap trimmed this cell, leaving out "
                        f"{' and '.join(capped)}; build it again with a larger max_atoms")
    if cuts["segments"]:
        warnings.append(f"{cuts['segments']} bond segments past build's cap of "
                        f"{s3.MAX_BONDS} are not drawn; lower bond_tolerance")
    report = rp.FigureReport(
        hidden=seen.hidden, hidden_atoms=seen.hidden_atoms,
        stacked=rp.stacked(scene, geometry, R, seen),
        dangling_bonds=_dangling(geometry, scene),
        label_overlaps=_label_overlaps(labels, frame),
        label_atom_overlaps=sum(label[5] for label in labels),
        label_bond_overlaps=sum(label[6] for label in labels), empty=_empty(image, bg),
        cut=cuts, note=geometry.get("note", ""), warnings=warnings)
    # every argument but the first and path: phase, probability, bond_tolerance
    # and max_atoms pick and build the geometry from a structure, and left out
    # they redraw phase 0 at the defaults with nothing said
    recipe = {k: _plain(v) for k, v in {
        "phase": phase, "mode": mode, "view": views.as_list(R), "size": size,
        "supersample": s, "probability": probability, "bond_tolerance": bond_tolerance,
        "max_atoms": max_atoms, "exaggeration": exaggeration, "stick": stick,
        "hidden": hidden_asked, "boundary": boundary, "cell": cell, "polyhedra": polyhedra,
        "axis_labels": asked_axis_labels, "atom_labels": atom_labels, "outline": outline,
        "background": background, "dpi": dpi}.items()}
    return StructureFigure(image=image, rotation=views.as_list(R),
                           pixels_per_angstrom=frame.ppa, origin=[float(frame.x0), float(frame.y0)],
                           atoms=atoms, letters=letters,
                           path=written, palette=_palette(geometry, scene), report=report,
                           candidates=candidates, recipe=recipe)
