"""The structure figure as a scene for a ray tracer: POV-Ray and glTF (WP-1537).

:func:`render_structure` hands these writers what it drew the PNG from: the
scene (:func:`.scene.build_scene`, every atom and stick an exact quadric in
Å), the view rotation ``R``, the fitted :class:`.raster.Frame` and the
letters as strokes in image pixels.  Each writer carries the figure's camera
and its one key light, so the file opens framed as the PNG is.

**Handedness.**  rietx's Cartesian frame and its view frame (x right, y up, z
toward the viewer) are right-handed, as is glTF.  POV-Ray is left-handed: its
camera looks along +z.  The POV-Ray scene keeps the atoms in Cartesian Å and
draws them through ``RIETX_VIEW``, which is ``diag(1, 1, -1)·R``: the view
rotation, then the mirror that turns a right-handed view frame into POV-Ray's.
Without it the picture is the enantiomer, which a centrosymmetric phase cannot
show.

**Matrices take columns.**  An atom's ``shape`` M is row-major, and its
surface is ``pos + M·u`` with ``|u| = 1``.  POV-Ray's ``matrix`` lists the
images of x, y and z in turn, so its first three numbers are M's first
column; written row by row it would draw Mᵀ, a different ellipsoid whenever M
is not symmetric.

**Colour.**  The PNG shades its sRGB values directly, as the GUI's shader
does.  A ray tracer shades in linear light, so POV-Ray is given each colour as
``srgb`` and glTF its linear value, and an unlit line or letter comes out the
PNG's colour exactly while a lit surface's midtones do not.

What neither format draws: ``outline`` and ``depth_cue``, which are the
CPU renderer's (POV-Ray's ``fog`` and Blender's mist do the second), and a
glTF background, which glTF has no field for.
"""

from __future__ import annotations

import json
import math
import struct
from collections.abc import Sequence

import numpy as np

from .scene import LOOK, POLY_ALPHA

#: Segments round the unit cylinder that a glTF stick, line or stroke is.
CYLINDER_SEGMENTS = 24
#: Steps along each octant's edge of the glTF unit sphere, and across a ring.
SPHERE_STEPS = 12
RING_STEPS = 2
#: glTF's metallic-roughness model has no Phong exponent: a satin dielectric
#: stands in for ``LOOK``'s highlight.  A look value, not a conversion.
GLTF_ROUGHNESS = 0.5
#: Lumens per watt at 540 THz, the SI candela's definition: Blender's glTF
#: importer reads a directional light's lux through it.
LUMENS_PER_WATT = 683.0

_MIRROR = np.diag([1.0, 1.0, -1.0])


# ----------------------------------------------------------------------
# what both writers share
# ----------------------------------------------------------------------

class _View:
    """The camera both formats carry, in view coordinates (Å): the frame's
    centre ``cx, cy``, its size ``w × h``, the plane the letters lie in
    (``z_text``, in front of everything) and the camera's ``z_eye``."""

    def __init__(self, scene: dict, R: np.ndarray, frame) -> None:
        self.R = np.asarray(R, dtype=np.float64)
        self.frame = frame
        self.w = frame.width / frame.ppa
        self.h = frame.height / frame.ppa
        self.cx = frame.x0 + self.w / 2
        self.cy = frame.y0 - self.h / 2
        # ``depth`` reaches past every atom from ``center``, frame corners too
        zc = float(self.R[2] @ np.asarray(scene["center"], dtype=np.float64))
        self.reach = float(scene["depth"])
        self.z_centre = zc
        self.z_text = zc + self.reach
        self.z_eye = zc + 2.0 * self.reach

    def view_point(self, u: float, v: float) -> np.ndarray:
        """An image pixel (u right, v down) on the letters' plane, in view Å."""
        f = self.frame
        return np.array([f.x0 + u / f.ppa, f.y0 - v / f.ppa, self.z_text])

    def strokes(self, text: Sequence) -> list[tuple[np.ndarray, np.ndarray, float, list]]:
        """The letters' strokes as view-space segments ``(a, b, radius, colour)``."""
        out = []
        for (u0, v0, u1, v1), half, colour in text:
            out.append((self.view_point(u0, v0), self.view_point(u1, v1),
                        half / self.frame.ppa, list(colour)))
        return out


def _line_radius(line: dict, frame) -> float:
    """A line's half-width in Å: ``width`` is CSS px, ``ppa`` per image pixel."""
    return 0.5 * line["width"] * frame.px_scale / frame.ppa


def _ring_ink(colour: Sequence[float]) -> list[float]:
    """A principal ring's colour, from the atom's: lighter on a dark atom,
    darker on the rest (``LOOK``).  The PNG applies it to the lit colour; a
    ray tracer lights the pigment, so it is applied before lighting here."""
    c = np.asarray(colour, dtype=np.float64)
    lum = float(np.dot(LOOK["luma"], c))
    if lum < LOOK["ring_dark"]:
        c = c + LOOK["ring_lighten"] * (1.0 - c)
    else:
        c = c * LOOK["ring_darken"]
    return [float(v) for v in c]


def _linear(colour: Sequence[float]) -> list[float]:
    """sRGB to linear light (IEC 61966-2-1), for glTF's colour factors."""
    return [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
            for v in (float(min(max(c, 0.0), 1.0)) for c in colour)]


# ----------------------------------------------------------------------
# POV-Ray 3.7
# ----------------------------------------------------------------------

def _n(v: float) -> str:
    v = float(v) + 0.0          # no "-0"
    text = f"{v:.12g}"
    return "0" if text == "-0" else text


def _vec(v: Sequence[float]) -> str:
    return "<" + ", ".join(_n(x) for x in v) + ">"


def _srgb(colour: Sequence[float], transmit: float | None = None) -> str:
    if transmit is None:
        return "color srgb " + _vec(colour)
    return "color srgbt " + _vec([*colour, transmit])


def _columns(m: np.ndarray, t: Sequence[float] = (0.0, 0.0, 0.0)) -> str:
    """POV-Ray's ``matrix``: the images of x, y and z, then the translation."""
    m = np.asarray(m, dtype=np.float64)
    return "matrix " + _vec([*m[:, 0], *m[:, 1], *m[:, 2], *t])


def pov(scene: dict, R, frame, text: Sequence = (), background=(1.0, 1.0, 1.0)) -> str:
    """A POV-Ray 3.7 scene of the figure, framed as the PNG is.

    Render it at the frame's size, ``povray +W<width> +H<height> file.pov``
    (the header names both), and with ``+UA`` for a transparent background.
    Every number a user is likely to change is a ``#declare`` at the top:
    the light, the finish and ``RIETX_RADIOSITY``, POV-Ray's global
    illumination, off as written.
    """
    v = _View(scene, R, frame)
    view = _MIRROR @ v.R
    f = frame
    out = [
        "// rietx structure figure: a POV-Ray 3.7 scene (WP-1537)",
        f"// render: povray +W{f.width} +H{f.height} +A <this file>"
        + ("   (+UA keeps the transparent background)" if background is None else ""),
        "// lengths are in angstrom; atoms sit in Cartesian coordinates, drawn",
        "// through RIETX_VIEW: the figure's rotation, then the mirror into",
        "// POV-Ray's left-handed frame",
        "#version 3.7;",
        "",
        "#declare RIETX_RADIOSITY = off;   // on: global illumination",
        f"#declare RIETX_AMBIENT = {_n(LOOK['ambient'])};",
        f"#declare RIETX_DIFFUSE = {_n(LOOK['diffuse'])};",
        f"#declare RIETX_PHONG = {_n(LOOK['specular'])};",
        f"#declare RIETX_PHONG_SIZE = {_n(LOOK['shininess'])};",
        f"#declare RIETX_FACE_DIFFUSE = {_n(LOOK['face_diffuse'])};",
        f"#declare RIETX_VIEW = transform {{ {_columns(view)} }}",
        "",
        "global_settings {",
        "  assumed_gamma 1.0",
        "  ambient_light rgb 1",
        "  #if (RIETX_RADIOSITY)",
        "    radiosity { pretrace_start 0.08 pretrace_end 0.01 count 150",
        "                recursion_limit 2 nearest_count 10 error_bound 0.5 }",
        "  #end",
        "}",
        "#if (RIETX_RADIOSITY)",
        "  #declare RIETX_LIT = finish { ambient 0 emission 0 diffuse RIETX_DIFFUSE",
        "                                phong RIETX_PHONG phong_size RIETX_PHONG_SIZE }",
        "  #declare RIETX_FACE = finish { ambient 0 emission 0 diffuse RIETX_FACE_DIFFUSE }",
        "#else",
        "  #declare RIETX_LIT = finish { ambient RIETX_AMBIENT diffuse RIETX_DIFFUSE",
        "                                phong RIETX_PHONG phong_size RIETX_PHONG_SIZE }",
        "  #declare RIETX_FACE = finish { ambient RIETX_AMBIENT diffuse RIETX_FACE_DIFFUSE }",
        "#end",
        "#declare RIETX_INK = finish { ambient 0 emission 1 diffuse 0 }",
        "",
        ("background { rgbt <1, 1, 1, 1> }" if background is None
         else f"background {{ {_srgb(background)} }}"),
        "",
        "camera {",
        "  orthographic",
        f"  location {_vec([v.cx, v.cy, -v.z_eye])}",
        "  direction <0, 0, 1>",
        f"  right {_vec([v.w, 0.0, 0.0])}",
        f"  up {_vec([0.0, v.h, 0.0])}",
        "}",
        "",
    ]
    light = np.asarray(LOOK["light"], dtype=np.float64)
    light = light / np.linalg.norm(light)
    centre = np.array([v.cx, v.cy, -v.z_centre])
    toward = _MIRROR @ light
    out += [
        "// the GUI's key light, fixed to the camera (LOOK['light'], view space)",
        "light_source {",
        f"  {_vec(centre + 10.0 * v.reach * toward)}",
        "  color rgb 1",
        f"  parallel point_at {_vec(centre)}",
        "}",
        "",
        "union {",
    ]
    ring_w = LOOK["ring_width"]
    for a in scene["atoms"]:
        if a.get("inverse") is None:
            continue
        m = np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        if a.get("rings"):
            ink = _srgb(_ring_ink(a["color"]))
            base = _srgb(a["color"])
            pigment = ("pigment { function { min(abs(x), min(abs(y), abs(z))) }\n"
                       f"      color_map {{ [0 {ink}] [{_n(ring_w)} {ink}]\n"
                       f"                  [{_n(ring_w)} {base}] [1 {base}] }} }}")
        else:
            pigment = f"pigment {{ {_srgb(a['color'])} }}"
        out += [f"  sphere {{ 0, 1  // atom {a['index']}",
                f"    texture {{ {pigment} finish {{ RIETX_LIT }} }}",
                f"    {_columns(m, a['pos'])}",
                "  }"]
    for h in scene["halves"]:
        if math.dist(h["from"], h["to"]) < 1e-9:
            continue
        out.append(f"  cylinder {{ {_vec(h['from'])}, {_vec(h['to'])}, {_n(h['radius'])} open"
                   f" texture {{ pigment {{ {_srgb(h['color'])} }} finish {{ RIETX_LIT }} }} }}")
    for line in scene["lines"]:
        if math.dist(line["a"], line["b"]) < 1e-9:
            continue
        out.append(f"  cylinder {{ {_vec(line['a'])}, {_vec(line['b'])}, "
                   f"{_n(_line_radius(line, frame))} no_shadow"
                   f" texture {{ pigment {{ {_srgb(line['color'])} }} finish {{ RIETX_INK }} }} }}")
    for face in scene["faces"]:
        tri = np.asarray(face["triangles"], dtype=np.float64).reshape(-1, 3)
        out += [f"  mesh2 {{  // {face['kind']} {face['index']}",
                f"    vertex_vectors {{ {len(tri)}, "
                + ", ".join(_vec(p) for p in tri) + " }",
                f"    face_indices {{ {len(tri) // 3}, "
                + ", ".join(f"<{3 * k}, {3 * k + 1}, {3 * k + 2}>" for k in range(len(tri) // 3))
                + " }",
                f"    texture {{ pigment {{ {_srgb(face['color'], 1.0 - POLY_ALPHA)} }}"
                " finish { RIETX_FACE } }",
                "  }"]
    out += ["  transform RIETX_VIEW", "}", ""]
    strokes = v.strokes(text)
    if strokes:
        # the letters lie in the camera's plane, in front of everything, so
        # they are written in POV-Ray's own frame: view x, y and -z
        inks: dict = {}
        for *_, colour in strokes:
            inks.setdefault(tuple(colour), f"RIETX_TEXT_{len(inks)}")
        out += [f"#declare {name} = texture {{ pigment {{ {_srgb(colour)} }} "
                "finish { RIETX_INK } }" for colour, name in inks.items()]
        out.append("union {  // the letters, Hershey strokes rounded at each end")
        for a, b, r, colour in strokes:
            pa, pb = _MIRROR @ a, _MIRROR @ b
            tex = f"texture {{ {inks[tuple(colour)]} }}"
            if math.dist(pa, pb) > 1e-9:
                out.append(f"  cylinder {{ {_vec(pa)}, {_vec(pb)}, {_n(r)} {tex} }}")
            out.append(f"  sphere {{ {_vec(pa)}, {_n(r)} {tex} }}")
            out.append(f"  sphere {{ {_vec(pb)}, {_n(r)} {tex} }}")
        out += ["  no_shadow", "}", ""]
    return "\n".join(out)


# ----------------------------------------------------------------------
# glTF 2.0, binary
# ----------------------------------------------------------------------

def _orient(triangles: list[tuple[int, int, int]], pts: np.ndarray) -> list[tuple[int, int, int]]:
    """Wind every triangle of a mesh round the origin counter-clockwise seen
    from outside, as glTF's front faces are."""
    out = []
    for a, b, c in triangles:
        n = np.cross(pts[b] - pts[a], pts[c] - pts[a])
        out.append((a, b, c) if n @ (pts[a] + pts[b] + pts[c]) >= 0 else (a, c, b))
    return out


def ring_sphere(steps: int = SPHERE_STEPS, ring_steps: int = RING_STEPS):
    """The unit sphere as ``(points, band, rest)``: its principal rings and
    what lies between them, as two triangle lists over one set of points.

    A ring is where the smallest of ``|x|``, ``|y|``, ``|z|`` is under
    ``LOOK['ring_width']``, the shader's own rule, so the triangles are laid
    on its edges: each octant's patch has every edge on a circle
    ``|coordinate| = w``, and the rings are strips across the three
    coordinate planes with a small cap at each of the six axis poles.
    Every point is on the sphere, so the point is its own normal.
    """
    w = float(LOOK["ring_width"])
    pts: list[list[float]] = []

    def add(p) -> int:
        pts.append([float(x) for x in p])
        return len(pts) - 1

    def lift(lam: np.ndarray, floor: np.ndarray) -> np.ndarray:
        # floor + t·lam on the unit sphere, t ≥ 0
        a = float(lam @ lam)
        b = float(floor @ lam)
        c = float(floor @ floor) - 1.0
        return floor + (-b + math.sqrt(b * b - a * c)) / a * lam

    rest: list[tuple[int, int, int]] = []
    band: list[tuple[int, int, int]] = []
    n, m = int(steps), int(ring_steps)
    for signs in np.array(np.meshgrid([1, -1], [1, -1], [1, -1], indexing="ij")).reshape(3, -1).T:
        grid = {}
        for i in range(n + 1):
            for j in range(n + 1 - i):
                lam = np.array([i, j, n - i - j], dtype=np.float64) / n
                grid[i, j] = add(signs * lift(lam, np.full(3, w)))
        for i in range(n):
            for j in range(n - i):
                rest.append((grid[i, j], grid[i + 1, j], grid[i, j + 1]))
                if i + j < n - 1:
                    rest.append((grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]))
    nu = np.linspace(-1.0, 1.0, m + 1)
    for axis in range(3):
        b, c = (axis + 1) % 3, (axis + 2) % 3
        for sb in (1.0, -1.0):
            for sc_ in (1.0, -1.0):
                grid = {}
                for i in range(n + 1):
                    mu = i / n
                    for k, z in enumerate(nu):
                        lam = np.zeros(3)
                        lam[b], lam[c] = mu, 1.0 - mu
                        floor = np.zeros(3)
                        floor[axis], floor[b], floor[c] = z * w, w, w
                        # floor + t·lam with the axis coordinate held at z·w
                        p = lift(lam, floor)
                        p[b] *= sb
                        p[c] *= sc_
                        grid[i, k] = add(p)
                for i in range(n):
                    for k in range(m):
                        band.append((grid[i, k], grid[i + 1, k], grid[i + 1, k + 1]))
                        band.append((grid[i, k], grid[i + 1, k + 1], grid[i, k + 1]))
        for sa in (1.0, -1.0):
            grid = {}
            for i, x in enumerate(nu):
                for k, y in enumerate(nu):
                    p = np.zeros(3)
                    p[b], p[c] = x * w, y * w
                    p[axis] = sa * math.sqrt(1.0 - p[b] ** 2 - p[c] ** 2)
                    grid[i, k] = add(p)
            for i in range(m):
                for k in range(m):
                    band.append((grid[i, k], grid[i + 1, k], grid[i + 1, k + 1]))
                    band.append((grid[i, k], grid[i + 1, k + 1], grid[i, k + 1]))
    points = np.asarray(pts, dtype=np.float64)
    return points, _orient(band, points), _orient(rest, points)


def unit_cylinder(segments: int = CYLINDER_SEGMENTS):
    """An open cylinder of radius 1 from y = 0 to y = 1: ``(points, normals,
    triangles)``, wound outward."""
    theta = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
    ring = np.stack([np.cos(theta), np.zeros_like(theta), np.sin(theta)], axis=1)
    points = np.concatenate([ring, ring + [0.0, 1.0, 0.0]])
    normals = np.concatenate([ring, ring])
    tris = []
    for k in range(segments):
        k1 = (k + 1) % segments
        tris += [(k, k + segments, k1), (k1, k + segments, k1 + segments)]
    mid = points.copy()
    mid[:, 1] = 0.0
    out = []
    for a, b, c in tris:
        n = np.cross(points[b] - points[a], points[c] - points[a])
        out.append((a, b, c) if n @ (mid[a] + mid[b] + mid[c]) >= 0 else (a, c, b))
    return points, normals, out


def _quaternion(q: np.ndarray) -> list[float]:
    """A proper rotation matrix as glTF's ``[x, y, z, w]``."""
    m = q
    tr = m[0, 0] + m[1, 1] + m[2, 2]
    if tr > 0:
        s = 2.0 * math.sqrt(tr + 1.0)
        out = [(m[2, 1] - m[1, 2]) / s, (m[0, 2] - m[2, 0]) / s, (m[1, 0] - m[0, 1]) / s,
               0.25 * s]
    elif m[0, 0] > m[1, 1] and m[0, 0] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[0, 0] - m[1, 1] - m[2, 2])
        out = [0.25 * s, (m[0, 1] + m[1, 0]) / s, (m[0, 2] + m[2, 0]) / s,
               (m[2, 1] - m[1, 2]) / s]
    elif m[1, 1] > m[2, 2]:
        s = 2.0 * math.sqrt(1.0 + m[1, 1] - m[0, 0] - m[2, 2])
        out = [(m[0, 1] + m[1, 0]) / s, 0.25 * s, (m[1, 2] + m[2, 1]) / s,
               (m[0, 2] - m[2, 0]) / s]
    else:
        s = 2.0 * math.sqrt(1.0 + m[2, 2] - m[0, 0] - m[1, 1])
        out = [(m[0, 2] + m[2, 0]) / s, (m[1, 2] + m[2, 1]) / s, 0.25 * s,
               (m[1, 0] - m[0, 1]) / s]
    norm = math.sqrt(sum(x * x for x in out))
    return [float(x / norm) for x in out]


def rotation_of(quaternion: Sequence[float]) -> np.ndarray:
    """glTF's ``[x, y, z, w]`` as a rotation matrix (the inverse of the
    writer's, for reading a node back)."""
    x, y, z, w = quaternion
    return np.array([
        [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
        [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
        [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def trs(m: np.ndarray, tolerance: float = 1e-9):
    """``m`` as glTF's rotation and scale, or ``None`` when it does not
    decompose: glTF allows no shear.  An ellipsoid's columns are its
    principal axes times its semi-axes, so they are orthogonal; where they
    make a left-handed set, the first is negated, which leaves the ellipsoid
    and its rings, both symmetric under it, where they were."""
    m = np.asarray(m, dtype=np.float64)
    scale = np.linalg.norm(m, axis=0)
    if not (scale > 0).all():
        return None
    q = m / scale
    if np.abs(q.T @ q - np.eye(3)).max() > tolerance:
        return None
    if np.linalg.det(q) < 0:
        q = q.copy()
        q[:, 0] *= -1.0
    return _quaternion(q), [float(s) for s in scale]


def _frame_of(axis: np.ndarray) -> np.ndarray:
    """A proper rotation whose second column is the unit ``axis``."""
    y = axis / np.linalg.norm(axis)
    helper = np.eye(3)[int(np.argmin(np.abs(y)))]
    x = np.cross(y, helper)
    x /= np.linalg.norm(x)
    z = np.cross(x, y)
    return np.stack([x, y, z], axis=1)


class _Glb:
    """The JSON document and its one binary buffer, filled as nodes are added."""

    def __init__(self) -> None:
        self.bin = bytearray()
        self.doc: dict = {
            "asset": {"version": "2.0", "generator": "rietx render_structure (WP-1537)"},
            "scene": 0, "scenes": [{"name": "rietx figure", "nodes": []}],
            "nodes": [], "meshes": [], "materials": [], "accessors": [],
            "bufferViews": [], "buffers": [],
        }
        self.materials: dict = {}

    def view(self, data: bytes, target: int | None) -> int:
        while len(self.bin) % 4:
            self.bin.append(0)
        entry = {"buffer": 0, "byteOffset": len(self.bin), "byteLength": len(data)}
        if target is not None:
            entry["target"] = target
        self.bin += data
        self.doc["bufferViews"].append(entry)
        return len(self.doc["bufferViews"]) - 1

    def accessor(self, array: np.ndarray, kind: str) -> int:
        if kind == "SCALAR":
            data = np.asarray(array, dtype=np.uint32).reshape(-1)
            entry = {"componentType": 5125, "count": int(data.size), "type": "SCALAR",
                     "bufferView": self.view(data.astype("<u4").tobytes(), 34963)}
        else:
            data = np.asarray(array, dtype=np.float32).reshape(-1, 3)
            entry = {"componentType": 5126, "count": int(len(data)), "type": "VEC3",
                     "bufferView": self.view(data.astype("<f4").tobytes(), 34962),
                     "min": [float(x) for x in data.min(axis=0)],
                     "max": [float(x) for x in data.max(axis=0)]}
        self.doc["accessors"].append(entry)
        return len(self.doc["accessors"]) - 1

    def material(self, colour: Sequence[float], kind: str) -> int:
        key = (tuple(round(float(c), 12) for c in colour), kind)
        if key in self.materials:
            return self.materials[key]
        base = _linear(colour)
        if kind == "lit":
            entry = {"pbrMetallicRoughness": {"baseColorFactor": [*base, 1.0],
                                              "metallicFactor": 0.0,
                                              "roughnessFactor": GLTF_ROUGHNESS}}
        elif kind == "face":
            entry = {"pbrMetallicRoughness": {"baseColorFactor": [*base, POLY_ALPHA],
                                              "metallicFactor": 0.0, "roughnessFactor": 1.0},
                     "alphaMode": "BLEND", "doubleSided": True}
        else:                                   # ink: a line or a letter
            entry = {"pbrMetallicRoughness": {"baseColorFactor": [*base, 1.0],
                                              "metallicFactor": 0.0, "roughnessFactor": 1.0},
                     "extensions": {"KHR_materials_unlit": {}}}
        hexed = "".join(f"{round(255 * min(max(c, 0.0), 1.0)):02x}" for c in colour)
        entry["name"] = f"{kind} #{hexed}"
        self.doc["materials"].append(entry)
        self.materials[key] = len(self.doc["materials"]) - 1
        return self.materials[key]

    def mesh(self, name: str, primitives: list[tuple[int, int, int, int]]) -> int:
        """``primitives`` are ``(position, normal, indices, material)`` accessors."""
        self.doc["meshes"].append({"name": name, "primitives": [
            {"attributes": {"POSITION": p, "NORMAL": n}, "indices": i, "material": mat}
            for p, n, i, mat in primitives]})
        return len(self.doc["meshes"]) - 1

    def node(self, entry: dict, parent: list | None) -> int:
        self.doc["nodes"].append(entry)
        k = len(self.doc["nodes"]) - 1
        (self.doc["scenes"][0]["nodes"] if parent is None else parent).append(k)
        return k

    def bytes(self) -> bytes:
        while len(self.bin) % 4:
            self.bin.append(0)
        self.doc["buffers"] = [{"byteLength": len(self.bin)}]
        for node in self.doc["nodes"]:
            if node.get("children") == []:
                del node["children"]
        doc = {k: v for k, v in self.doc.items() if v != []}
        text = json.dumps(doc, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        text += b" " * (-len(text) % 4)
        total = 12 + 8 + len(text) + 8 + len(self.bin)
        return b"".join([
            struct.pack("<III", 0x46546C67, 2, total),
            struct.pack("<II", len(text), 0x4E4F534A), text,
            struct.pack("<II", len(self.bin), 0x004E4942), bytes(self.bin)])


def glb(scene: dict, R, frame, text: Sequence = ()) -> bytes:
    """A glTF 2.0 binary of the figure, with its camera and its key light.

    One unit is one ångström (glTF's unit is the metre, so an importer that
    honours it draws the cell a few metres wide).  Every atom and stick is a
    node over one shared unit sphere or unit cylinder; a ringed atom's sphere
    is two primitives, the ring band in the ring's colour and the rest in the
    atom's.  An atom whose ``shape`` does not decompose into rotation and
    scale, which glTF requires, gets its own mesh with the matrix applied to
    the points.  The camera is orthographic with ``xmag``/``ymag`` half the
    frame in Å, and the light is ``KHR_lights_punctual``'s directional light,
    pointed as ``LOOK['light']`` is from the camera.  Lines and letters are
    thin cylinders under ``KHR_materials_unlit``.
    """
    v = _View(scene, R, frame)
    g = _Glb()
    sphere_pts, band, rest = ring_sphere()
    sp = g.accessor(sphere_pts, "VEC3")
    s_band = g.accessor(np.asarray(band), "SCALAR")
    s_rest = g.accessor(np.asarray(rest), "SCALAR")
    s_all = g.accessor(np.asarray(band + rest), "SCALAR")
    cyl_pts, cyl_n, cyl_tri = unit_cylinder()
    cp = g.accessor(cyl_pts, "VEC3")
    cn = g.accessor(cyl_n, "VEC3")
    ci = g.accessor(np.asarray(cyl_tri), "SCALAR")
    meshes: dict = {}

    def sphere_mesh(colour, ringed: bool) -> int:
        key = ("sphere", tuple(colour), ringed)
        if key not in meshes:
            lit = g.material(colour, "lit")
            prims = ([(sp, sp, s_band, g.material(_ring_ink(colour), "lit")),
                      (sp, sp, s_rest, lit)] if ringed else [(sp, sp, s_all, lit)])
            meshes[key] = g.mesh("ringed atom" if ringed else "atom", prims)
        return meshes[key]

    def cylinder_mesh(colour, kind: str) -> int:
        key = ("cylinder", tuple(colour), kind)
        if key not in meshes:
            meshes[key] = g.mesh("stick" if kind == "lit" else "line",
                                 [(cp, cn, ci, g.material(colour, kind))])
        return meshes[key]

    def segment(a, b, r, mesh: int, parent: list, name: str) -> None:
        a, b = np.asarray(a, dtype=np.float64), np.asarray(b, dtype=np.float64)
        length = float(np.linalg.norm(b - a))
        if length < 1e-9:
            return
        g.node({"name": name, "mesh": mesh, "translation": [float(x) for x in a],
                "rotation": _quaternion(_frame_of(b - a)), "scale": [r, length, r]}, parent)

    structure: list[int] = []
    g.node({"name": "structure", "children": structure}, None)
    for a in scene["atoms"]:
        if a.get("inverse") is None:
            continue
        m = np.asarray(a["shape"], dtype=np.float64).reshape(3, 3)
        ringed = bool(a.get("rings"))
        name = f"atom {a['index']}"
        split = trs(m)
        if split is not None:
            rotation, scale = split
            g.node({"name": name, "mesh": sphere_mesh(a["color"], ringed),
                    "translation": [float(x) for x in a["pos"]],
                    "rotation": rotation, "scale": scale}, structure)
            continue
        # sheared: the points carry the matrix, the normals its inverse transpose
        pts = sphere_pts @ m.T
        normals = sphere_pts @ np.linalg.inv(m)
        normals /= np.linalg.norm(normals, axis=1)[:, None]
        p, n = g.accessor(pts, "VEC3"), g.accessor(normals, "VEC3")
        lit = g.material(a["color"], "lit")
        prims = ([(p, n, s_band, g.material(_ring_ink(a["color"]), "lit")),
                  (p, n, s_rest, lit)] if ringed else [(p, n, s_all, lit)])
        g.node({"name": name, "mesh": g.mesh(name, prims),
                "translation": [float(x) for x in a["pos"]]}, structure)
    for h in scene["halves"]:
        segment(h["from"], h["to"], float(h["radius"]), cylinder_mesh(h["color"], "lit"),
                structure, f"bond {h['bond']}")
    for line in scene["lines"]:
        segment(line["a"], line["b"], _line_radius(line, frame),
                cylinder_mesh(line["color"], "ink"), structure, "line")
    for face in scene["faces"]:
        tri = np.asarray(face["triangles"], dtype=np.float64).reshape(-1, 3)
        normals = np.repeat(np.asarray(face["normals"], dtype=np.float64).reshape(-1, 3), 3,
                            axis=0)
        mesh = g.mesh(f"{face['kind']} {face['index']}", [(
            g.accessor(tri, "VEC3"), g.accessor(normals, "VEC3"),
            g.accessor(np.arange(len(tri)), "SCALAR"), g.material(face["color"], "face"))])
        g.node({"name": f"{face['kind']} {face['index']}", "mesh": mesh}, structure)
    to_world = v.R.T                       # view coordinates to Cartesian
    strokes = v.strokes(text)
    if strokes:
        letters: list[int] = []
        g.node({"name": "letters", "children": letters}, None)
        for a, b, r, colour in strokes:
            segment(to_world @ a, to_world @ b, r, cylinder_mesh(colour, "ink"), letters,
                    "stroke")
    eye = to_world @ np.array([v.cx, v.cy, v.z_eye])
    g.doc["cameras"] = [{"type": "orthographic", "name": "rietx figure",
                         "orthographic": {"xmag": v.w / 2, "ymag": v.h / 2,
                                          "znear": 0.01, "zfar": 4.0 * v.reach}}]
    # a glTF camera looks down its own -z with +y up: the view frame exactly
    g.node({"name": "camera", "camera": 0, "translation": [float(x) for x in eye],
            "rotation": _quaternion(to_world)}, None)
    light = np.asarray(LOOK["light"], dtype=np.float64)
    toward = to_world @ (light / np.linalg.norm(light))
    # the light shines down its own -z, so its +z is the way to the light
    pose = _frame_of(toward)[:, [2, 0, 1]]
    # a diffuse term of LOOK's ``diffuse``·base on a Lambertian surface needs
    # an irradiance of diffuse·π W/m²; glTF gives a directional light in lux
    lux = LOOK["diffuse"] * math.pi * LUMENS_PER_WATT
    g.doc["extensionsUsed"] = ["KHR_lights_punctual", "KHR_materials_unlit"]
    g.doc["extensions"] = {"KHR_lights_punctual": {"lights": [
        {"type": "directional", "name": "rietx key light", "color": [1.0, 1.0, 1.0],
         "intensity": lux}]}}
    g.node({"name": "key light", "rotation": _quaternion(pose),
            "translation": [float(x) for x in eye],
            "extensions": {"KHR_lights_punctual": {"light": 0}}}, None)
    return g.bytes()
