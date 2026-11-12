"""The structure viewer's scene rules and views, ported from TypeScript (WP-1470).

``gui/src/lib/structure3d.ts`` turns the geometry ``rietx.gui.structure3d.build``
returns into the ``Scene`` the GUI's renderer draws, and builds the ``View`` it
draws it from.  :func:`render_structure` draws the same picture without a
browser, so it needs the same two answers, and this module is their second
copy.  A second copy of a rule is a drift hazard with no natural alarm, so the
two are held equal case by case: ``tests/test_render_structure.py`` writes
``tests/data/gui/scene_cases.json`` from the functions here, and
``structure3d.test.ts`` replays every case against ``buildScene``, ``lookFrom``
and ``axisView``.  Python owns the rules and TypeScript proves it states them.

So every function here is a line-for-line port of the one it names, down to
its rounding (``Math.round`` rounds a half up, where python's ``round`` rounds
it to even) and its degenerate branches.  A change to a rule is made in both
files in one commit, and the corpus fails until it is.

The scene is plain lists and dicts with the TypeScript field names, so the
corpus is the scene itself.  The renderer packs it into arrays.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

#: Half a bond is 0.08 Å thick in ball mode (``STICK_RADIUS``).
STICK_RADIUS = 0.08
#: How much of the smallest drawn semi-axis a stick may take in ellipsoid mode.
STICK_OF_SEMI_AXIS = 0.5
#: Below this a stick is a hairline at any zoom, so it stops shrinking.
STICK_FLOOR = 0.02
#: A drawn semi-axis below this is drawn at this, in Å: the ray-caster solves
#: through M⁻¹, which a zero column of a non-positive tensor does not have.
FLAT_AXIS = 1e-3
#: The cell frame's width and a polyhedron edge's, in CSS pixels.
CELL_WIDTH_PX = 2
EDGE_WIDTH_PX = 1.25
#: A polyhedron's faces are drawn at this opacity in the centre's colour.
POLY_ALPHA = 0.55
#: An image outside the cell is its colour scaled toward black by this, and a
#: polyhedron's edges are their face colour scaled by the second.
DIM_BOUNDARY = 0.62
DIM_EDGE = 0.5
#: The a, b, c letters clear the largest ball by this much, in Å.
LABEL_CLEARANCE = 0.35
#: The cell frame's ink when no theme supplies one (``buildScene``'s default).
CELL_INK = "#1f5fa8"

#: How every solid is lit and inked, the GUI's ``LOOK`` (``gl3d.ts``'s shaders
#: read it).  One key light fixed to the camera, in view space (x right, y up,
#: z toward the viewer).  An atom or a stick is shaded
#: ``base·(ambient + diffuse·d) + specular·s^shininess``; a polyhedron face
#: ``base·(ambient + face_diffuse·d)``, lit from whichever side it shows.  A
#: principal ring is where the smallest unit-frame coordinate is under
#: ``ring_width``, inked lighter (``ring_lighten`` toward white) on an atom
#: whose luminance is under ``ring_dark`` and darker (``ring_darken``) on the
#: rest.  ``luma`` is Rec. 709's.  Depth cueing (WP-1548 D1, off unless asked)
#: fades each surface toward the background linearly in depth: from nothing at
#: ``fog_start`` of the drawn atoms' depth span, measured from the front, to
#: ``fog_max`` at ``fog_end`` (:func:`fog_span`).  The start and end are
#: ChimeraX's defaults for its ramp; ``fog_max`` is below 1 so the back layer
#: stays legible (``docs/practice.md`` § Depth cueing).
LOOK: dict[str, Any] = {
    "light": [-0.40, 0.55, 0.73],
    "ambient": 0.45,
    "diffuse": 0.60,
    "specular": 0.16,
    "shininess": 40,
    "face_diffuse": 0.55,
    "ring_width": 0.035,
    "ring_dark": 0.33,
    "ring_lighten": 0.6,
    "ring_darken": 0.3,
    "luma": [0.2126, 0.7152, 0.0722],
    "fog_start": 0.5,
    "fog_end": 1.0,
    "fog_max": 0.7,
}

#: The opening view's eye and up, before ``look_from`` (``openingView``).
OPENING_EYE = (1.35, 1.35, 0.95)
OPENING_UP = (0.0, 0.0, 1.0)

_HEX = re.compile(r"^#[0-9a-f]{6}$", re.IGNORECASE)
_SUBSCRIPT = "₀₁₂₃₄₅₆₇₈₉"


def _js_round(x: float) -> int:
    """``Math.round``: a half rounds up, never to even."""
    return math.floor(x + 0.5)


def dim(color: str, factor: float = DIM_BOUNDARY) -> str:
    """``dim``: a colour scaled toward black; anything not ``#rrggbb`` unchanged."""
    if not _HEX.match(color):
        return color
    return "#" + "".join(f"{_js_round(int(color[at:at + 2], 16) * factor):02x}"
                         for at in (1, 3, 5))


def rgb(color: str) -> list[float]:
    """``rgb``: ``#rrggbb`` as three channels in 0..1; anything else mid-grey."""
    if not _HEX.match(color):
        return [0.5, 0.5, 0.5]
    return [int(color[at:at + 2], 16) / 255 for at in (1, 3, 5)]


def _hypot3(v: Sequence[float]) -> float:
    return math.hypot(v[0], v[1], v[2])


def _cross(u: Sequence[float], v: Sequence[float]) -> list[float]:
    return [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
            u[0] * v[1] - u[1] * v[0]]


def fog_span(scene: Mapping, rotation: Sequence[float]) -> list[float] | None:
    """``fogSpan``: where depth cueing starts and ends, as view-space depths.

    ``rotation`` is row-major, nine numbers, as :func:`look_from` returns it.
    Depths are the GUI's, ``R·(p − center)``'s third component, z toward the
    viewer; the raster's view coordinates are ``R·p`` and add ``(R·center)``'s.
    The span is the drawn atoms' centres along the line of sight, front to back.  The fog starts ``fog_start`` of
    the way from the front and reaches ``fog_max`` ``fog_end`` of the way, so it
    follows the picture as it turns, as ChimeraX's ramp follows its clip planes
    (WP-1548 D1).  ``None`` where the atoms span no depth, one atom or a layer
    seen edge on, since then there is nothing to cue.
    """
    r, c = rotation[6:9], scene["center"]
    depths = [r[0] * (a["pos"][0] - c[0]) + r[1] * (a["pos"][1] - c[1])
              + r[2] * (a["pos"][2] - c[2]) for a in scene["atoms"]]
    if not depths:
        return None
    front, back = max(depths), min(depths)
    if not front > back:
        return None
    span = front - back
    return [front - LOOK["fog_start"] * span, front - LOOK["fog_end"] * span]


def atom_transform(geometry: Mapping, atom: Mapping, mode: str,
                   exaggeration: float = 1.0) -> list[list[float]]:
    """``atomTransform``: the matrix an atom's unit sphere is drawn through.

    Columns are axes.  ``ball`` is isotropic even for an anisotropic site: the
    two modes answer different questions.
    """
    if mode == "ellipsoid":
        k = geometry["scale"] * exaggeration
        return [[value * k for value in row] for row in atom["ellipsoid"]]
    r = geometry["ball_fraction"] * geometry["sites"][atom["site"]]["radius"]
    return [[r, 0.0, 0.0], [0.0, r, 0.0], [0.0, 0.0, r]]


def stick_radius(geometry: Mapping, mode: str, exaggeration: float = 1.0,
                 stick: float = 1.0) -> float:
    """``stickRadius``: half a bond's thickness, in Å, for the mode drawn.

    ``stick`` multiplies the mode's own rule, and the floor stays a hairline.
    """
    if mode != "ellipsoid":
        return STICK_RADIUS * stick
    semi = [v for atom in geometry["atoms"] for v in atom["rms"] if v > 0]
    if not semi:
        return STICK_RADIUS * stick
    smallest = min(semi) * geometry["scale"] * exaggeration
    return max(STICK_FLOOR, min(STICK_RADIUS * stick, STICK_OF_SEMI_AXIS * stick * smallest))


def invert3(m: Sequence[float]) -> list[float] | None:
    """``invert3``: the inverse of a row-major 3×3, ``None`` when singular."""
    a, b, c, d, e, f, g, h, i = m
    A, B, C = e * i - f * h, -(d * i - f * g), d * h - e * g
    det = a * A + b * B + c * C
    if not math.isfinite(det) or abs(det) < 1e-300:
        return None
    return [A / det, -(b * i - c * h) / det, (b * f - c * e) / det,
            B / det, (a * i - c * g) / det, -(a * f - c * d) / det,
            C / det, -(a * h - b * g) / det, (a * e - b * d) / det]


def _drawable(m: Sequence[Sequence[float]]) -> list[float]:
    """``drawable``: a shape, row-major, with every column at least ``FLAT_AXIS``."""
    out = [m[0][0], m[0][1], m[0][2], m[1][0], m[1][1], m[1][2],
           m[2][0], m[2][1], m[2][2]]
    for c in range(3):
        if math.hypot(out[c], out[3 + c], out[6 + c]) >= FLAT_AXIS:
            continue
        # a zero column has no direction left, so a flat axis takes the one
        # the other two leave free
        c1, c2 = (c + 1) % 3, (c + 2) % 3
        u = [out[c1], out[3 + c1], out[6 + c1]]
        v = [out[c2], out[3 + c2], out[6 + c2]]
        n = _cross(u, v)
        nn = _hypot3(n)
        if not nn > 0:
            # a neighbour is zero too: the Cartesian axis least along the
            # column that is left, made perpendicular to it
            w = u if _hypot3(u) > 0 else v
            wn = _hypot3(w)
            k = 0
            for j in range(3):
                if abs(w[j]) < abs(w[k]):
                    k = j
            n = [(1.0 if j == k else 0.0) - ((w[k] * w[j]) / (wn * wn) if wn > 0 else 0.0)
                 for j in range(3)]
            nn = _hypot3(n)
        n = [x / nn for x in n]
        out[c], out[3 + c], out[6 + c] = FLAT_AXIS * n[0], FLAT_AXIS * n[1], FLAT_AXIS * n[2]
    return out


def polyhedron_formula(geometry: Mapping, polyhedron: Mapping) -> str:
    """``polyhedronFormula``: the centre, then its ligands by count, most first."""
    counts: dict[str, int] = {}
    for v in polyhedron["vertices"]:
        element = geometry["sites"][geometry["atoms"][v]["site"]]["element"]
        counts[element] = counts.get(element, 0) + 1
    ligands = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    text = "".join(element + ("".join(_SUBSCRIPT[int(d)] for d in str(n)) if n > 1 else "")
                   for element, n in ligands)
    return geometry["sites"][polyhedron["site"]]["element"] + text


def shown_polyhedra(geometry: Mapping, on: bool,
                    formulas: Mapping[str, bool] | None = None,
                    hidden: Iterable[str] = (), show_boundary: bool = True) -> list[int]:
    """``shownPolyhedra``: which polyhedra are drawn, as indices.

    ``formulas`` switches a formula on or off; one it does not name takes the
    server's ``drawn_by_default``.  A polyhedron goes with its centre's species
    when that is hidden, and with its centre when the images are hidden.
    """
    if not on:
        return []
    formulas = formulas or {}
    hidden = set(hidden)
    out = []
    for i, p in enumerate(geometry["polyhedra"]):
        if geometry["sites"][p["site"]]["species"] in hidden:
            continue
        if not show_boundary and geometry["atoms"][p["center"]]["boundary"]:
            continue
        if formulas.get(polyhedron_formula(geometry, p), p["drawn_by_default"]):
            out.append(i)
    return out


def axis_labels(geometry: Mapping) -> list[dict]:
    """``axisLabels``: a, b, c just beyond the far end of the three cell edges."""
    largest = max([0.0, *(site["radius"] for site in geometry["sites"])])
    clear = LABEL_CLEARANCE + geometry["ball_fraction"] * largest
    corners = geometry["corners"]
    origin = corners[0] if corners else [0.0, 0.0, 0.0]
    out = []
    for k, text in enumerate("abc"):
        v = geometry["lattice"][k]
        length = _hypot3(v) or 1.0
        out.append({"text": text,
                    "pos": [origin[i] + v[i] * (1 + clear / length) for i in range(3)]})
    return out


def drawn_with(geometry: Mapping, polyhedra: Iterable[int]):
    """``drawnWith``: whether a payload atom is drawn while ``polyhedra`` are.

    An atom in the payload only as a polyhedron's vertex is drawn only while
    one of its polyhedra is.  An atom outside the cell whose site centres a
    polyhedron (``outside_centre``) is drawn only while no drawn polyhedron is
    centred on its site, and so is a flagged bond to one, both halves: VESTA
    adds no centre outside the boundary (its manual, § 8.2.1; WP-1529).
    Returns a test on an index into ``atoms``, whose ``bond`` is the same test
    on an index into ``bonds``; :func:`build_scene` reads it for the atoms and
    bonds it draws and for its zoom fit.

    A site is the asymmetric-unit atom it was built from, ``sites[k]["index"]``,
    because :func:`~rietx.viz.recolour` points some images of a site at a copy:
    keyed on ``atoms[k]["site"]``, dimming fluorapatite's images drew its 4 bare
    P again.
    """
    atoms, sites = geometry["atoms"], geometry["sites"]
    polys = list(polyhedra)
    corners = {v for i in polys for v in geometry["polyhedra"][i]["vertices"]}
    centred = {sites[atoms[geometry["polyhedra"][i]["center"]]["site"]]["index"]
               for i in polys}

    def drawn(index: int) -> bool:
        atom = atoms[index]
        return ((not atom.get("vertex_only") or index in corners)
                and not (atom.get("outside_centre")
                         and sites[atom["site"]]["index"] in centred))

    def bond(index: int) -> bool:
        b = geometry["bonds"][index]
        return not (b.get("outside_centre")
                    and sites[atoms[b["j"]]["site"]]["index"] in centred)

    drawn.bond = bond
    return drawn


def build_scene(geometry: Mapping, mode: str = "ball", *,
                hidden: Iterable[str] = (), show_boundary: bool = True,
                exaggeration: float = 1.0, polyhedra: Sequence[int] = (),
                cell: str = CELL_INK, stick: float = 1.0) -> dict:
    """``buildScene``: everything the renderer draws, in Å.

    ``hidden`` is the species switched off, and a bond half belongs to its
    atom.  ``stick`` multiplies every half's radius (:func:`stick_radius`).
    ``polyhedra`` is the indices drawn (:func:`shown_polyhedra`); a
    drawn polyhedron takes away its centre's sticks to its own vertices,
    brings the atoms only it needs, and hides its site's centres outside the
    cell with their sticks (:func:`drawn_with`).  ``center`` and ``radius`` are the fit the
    GUI zooms to, and ``depth`` holds every atom the payload can draw.
    """
    hidden = set(hidden)
    polys = geometry["polyhedra"]
    sites = geometry["sites"]
    payload_atoms = geometry["atoms"]
    replaced = {b for i in polyhedra for b in polys[i]["bonds"]}
    drawn = drawn_with(geometry, polyhedra)
    atoms = []
    for index, atom in enumerate(payload_atoms):
        site = sites[atom["site"]]
        if site["species"] in hidden:
            continue
        if atom["boundary"] and not show_boundary:
            continue
        if not drawn(index):
            continue
        shape = _drawable(atom_transform(geometry, atom, mode, exaggeration))
        atoms.append({
            "index": index,
            "pos": list(atom["pos"]),
            "shape": shape,
            "inverse": invert3(shape),
            "color": rgb(dim(site["color"]) if atom["boundary"] else site["color"]),
            "rings": mode == "ellipsoid" and bool(site["aniso"]),
        })
    radius = stick_radius(geometry, mode, exaggeration, stick)
    halves = []
    for index, bond in enumerate(geometry["bonds"]):
        if index in replaced or not drawn.bond(index):
            continue
        mid = [(bond["a"][k] + bond["b"][k]) / 2 for k in range(3)]
        for frm, at in ((bond["a"], bond["i"]), (bond["b"], bond["j"])):
            site = sites[payload_atoms[at]["site"]]
            if site["species"] in hidden:
                continue
            halves.append({"bond": index, "from": list(frm), "to": mid,
                           "radius": radius, "color": rgb(site["color"])})
    ink = rgb(cell)
    lines = [{"a": list(geometry["corners"][a]), "b": list(geometry["corners"][b]),
              "color": ink, "width": CELL_WIDTH_PX} for a, b in geometry["edges"]]
    faces = []
    for index in polyhedra:
        p = polys[index]
        site = sites[p["site"]]
        color = dim(site["color"]) if payload_atoms[p["center"]]["boundary"] else site["color"]
        at = [payload_atoms[v]["pos"] for v in p["vertices"]]
        for i, j in p["edges"]:
            lines.append({"a": list(at[i]), "b": list(at[j]),
                          "color": rgb(dim(color, DIM_EDGE)), "width": EDGE_WIDTH_PX})
        triangles: list[float] = []
        normals: list[float] = []
        for face in p["faces"]:
            a, b, c = (at[v] for v in face)
            u = [b[0] - a[0], b[1] - a[1], b[2] - a[2]]
            w = [c[0] - a[0], c[1] - a[1], c[2] - a[2]]
            n = _cross(u, w)
            length = _hypot3(n) or 1.0
            triangles.extend([*a, *b, *c])
            normals.extend([n[0] / length, n[1] / length, n[2] / length])
        centroid = [sum(q[k] for q in at) / len(at) for k in range(3)]
        faces.append({"index": index, "triangles": triangles, "normals": normals,
                      "color": rgb(color), "centroid": centroid})
    # the fit reads positions and ball sizes only, over the atoms the default
    # picture can draw
    by_default = drawn_with(geometry, [i for i, p in enumerate(polys) if p["drawn_by_default"]])
    points = [*geometry["corners"],
              *(a["pos"] for k, a in enumerate(payload_atoms) if by_default(k))]
    lo = [min(p[k] for p in points) for k in range(3)]
    hi = [max(p[k] for p in points) for k in range(3)]
    center = [(lo[k] + hi[k]) / 2 for k in range(3)]
    half = math.hypot(hi[0] - lo[0], hi[1] - lo[1], hi[2] - lo[2]) / 2
    ball = geometry["ball_fraction"] * max([0.0, *(s["radius"] for s in sites)])
    reach = max([ball, *(max(math.hypot(a["shape"][c], a["shape"][3 + c], a["shape"][6 + c])
                             for c in range(3)) for a in atoms)])
    far = max([half, *(math.hypot(a["pos"][0] - center[0], a["pos"][1] - center[1],
                                  a["pos"][2] - center[2]) for a in payload_atoms)])
    return {"atoms": atoms, "halves": halves, "lines": lines, "faces": faces,
            "labels": axis_labels(geometry), "center": center,
            "radius": max(half + ball, 1.0), "depth": far + reach + 1}


# ----------------------------------------------------------------------
# the view
# ----------------------------------------------------------------------

def look_from(eye: Sequence[float], up: Sequence[float]) -> list[float]:
    """``lookFrom``: the rotation looking from ``eye`` toward the centre, ``up`` up.

    Row-major; its rows are the screen's x (right), y (up) and z (toward the
    viewer) in the scene's Å.  ``up`` is Gram-Schmidted against the view.
    """
    def unit(v):
        n = _hypot3(v) or 1.0
        return [v[0] / n, v[1] / n, v[2] / n]

    z = unit(eye)
    along = up[0] * z[0] + up[1] * z[1] + up[2] * z[2]
    y = unit([up[0] - along * z[0], up[1] - along * z[1], up[2] - along * z[2]])
    x = _cross(y, z)
    return [*x, *y, *z]


def opening_view() -> list[float]:
    """``openingView``'s rotation: down the body diagonal, Cartesian z up."""
    return look_from(OPENING_EYE, OPENING_UP)


def up_axis(axis: int) -> int:
    """The lattice vector kept up when looking down lattice vector ``axis``.

    The convention (WP-1470 D12): c up, unless the view is down c, and then b.
    """
    return 1 if axis == 2 else 2


def axis_view(geometry: Mapping, axis: int) -> list[float]:
    """``axisView``'s rotation: looking down one lattice vector, which points
    at the viewer, with :func:`up_axis` up."""
    return look_from(geometry["lattice"][axis], geometry["lattice"][up_axis(axis)])
