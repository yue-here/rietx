"""What a figure says about itself, and the view that says least against it (WP-1503).

An agent pays for each look at a picture: about width × height / 750 tokens, a
turn, and a picture seen three turns ago may be gone after a compaction.  The
numbers a look would give are computed here instead, from the scene and a small
**id pass** (:func:`.raster.id_plane`): which atom or bond half is in front at
each pixel of a 256 px frame.  A projected disc misses the stick that hides an
atom, and the id pass does not.

There is no quality score.  A single number would be the mechanical rule the
package's agent-first design argues against, so the figure reports evidence and
the caller judges.  ``view="auto"`` (:func:`choose_view`) ranks low-index
directions by the same two numbers the report carries and returns the
runners-up, so the second choice is a lookup and not a search.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field

import numpy as np
from scipy.spatial import cKDTree

from . import raster, views

#: The id pass's long side, in pixels.
ID_SIZE = 256
#: An atom is hidden when more than this share of the samples it would cover
#: have something in front of them.
HIDDEN_SHARE = 0.8
#: A hidden atom is stacked behind its own site when an atom of that site lies
#: in front within this share of its projected radius (WP-1533).
STACKED_REACH = 0.25
#: ``view="auto"`` tries every primitive direction [u, v, w] whose indices are at
#: most this many in magnitude, and the opening view.
SEARCH_INDEX = 2
#: How many of the ranked views ``candidates`` carries.
N_CANDIDATES = 5
OPENING = "opening"


@dataclass(frozen=True)
class FigureReport:
    """The numbers a look at the figure would give.

    ``hidden`` is the share of the atoms drawn inside the cell (not the images
    outside it) that are covered over more than 80 % by an atom or bond in
    front, at a long side of 256 px, and ``hidden_atoms`` their indices into the
    geometry's ``atoms``.  An atom under one sample at that size is left out of
    both.  ``stacked`` is the part of ``hidden`` that sits behind an atom of
    its own site, within a quarter of its projected radius: a projection down
    a symmetry or lattice direction stacks a site's copies by construction, and
    the one in front draws what the one behind holds.  ``hidden - stacked`` is
    what the view occludes.  Down a cell axis HKUST-1 reads 0.53 hidden and
    0.53 stacked, ZSM-5 0.52 and 0.50, YBa₂Cu₃O₇ 1.00 and 1.00 (WP-1533).
    ``dangling_bonds`` counts bond halves whose far atom is not drawn:
    the stubs ``hidden=`` leaves, and the bonds a trimmed cell leaves ending
    on an atom the geometry does not hold.  ``label_overlaps`` counts pairs
    of drawn strings whose boxes intersect, a box being the string's width and
    the font's height.  ``label_atom_overlaps`` counts (string, atom) pairs
    whose shapes meet, an atom being the ellipse it projects to and a site
    label never counting its own atom.  ``label_bond_overlaps`` counts
    (string, bond) pairs, a bond being its drawn halves as segments widened by
    the stick radius.  All three count a, b and c too.  Each site label takes
    the first of eight places around its atom that this test finds clear of
    atoms, bonds and the strings placed before it, so a count left above zero
    is a site label with no clear place, or a, b or c, which stay where they
    are.  ``empty`` is the share of the picture's pixels with nothing drawn,
    read off the image.

    ``cut`` counts what the figure lost before it was drawn.  ``atoms`` is the
    cell's images ``build``'s atom cap left out, ``neighbours`` the bonded
    neighbours outside the cell it left out, and ``segments`` the bond
    segments past its bond cap.  ``bonds`` and ``polyhedra`` are what
    :func:`~rietx.viz.keep` dropped from a kept atom, running over successive
    cuts, and ``polyhedra`` adds those the atom cap left out.  ``note`` is the
    geometry's own note, the same losses in words.  ``warnings`` are
    sentences, and one says so when either cap trimmed the cell.
    """
    hidden: float
    hidden_atoms: list[int]
    stacked: float
    dangling_bonds: int
    label_overlaps: int
    label_atom_overlaps: int
    label_bond_overlaps: int
    empty: float
    cut: dict[str, int]
    note: str
    warnings: list[str] = field(default_factory=list)


@dataclass
class Probe:
    """What the id pass needs of a scene, built once and read for every view."""
    arrays: dict
    boundary: np.ndarray
    points: np.ndarray
    size: object
    margin: float
    fit: Callable


@dataclass
class Look:
    """One view through the id pass."""
    hidden: float
    hidden_atoms: list[int]
    empty: float
    unjudged: int


def probe(scene: dict, geometry: Mapping, size, margin: float, fit: Callable,
          axis_labels: bool) -> Probe:
    """The scene's arrays, which packed atoms lie outside the cell, the points
    the frame must hold beyond the atoms and bonds, and the small frame's size.

    ``fit(extent, size, margin)`` is the renderer's own
    (:func:`.render._fit`); ``margin`` is what pixel-sized things add beyond
    the box, in CSS px.
    """
    arrays = raster.scene_arrays(scene)
    boundary = np.array([bool(geometry["atoms"][k]["boundary"]) for k in arrays["index"]],
                        dtype=bool)
    points = [p for line in scene["lines"] for p in (line["a"], line["b"])]
    for face in scene["faces"]:
        points += np.asarray(face["triangles"], dtype=np.float64).reshape(-1, 3).tolist()
    if axis_labels:
        points += [label["pos"] for label in scene["labels"]]
    if isinstance(size, (tuple, list)):
        k = min(1.0, ID_SIZE / max(size))
        small = (max(1, round(size[0] * k)), max(1, round(size[1] * k)))
    else:
        small = min(int(size), ID_SIZE)
    return Probe(arrays=arrays, boundary=boundary,
                 points=np.asarray(points, dtype=np.float64).reshape(-1, 3),
                 size=small, margin=margin, fit=fit)


def look(p: Probe, R) -> Look:
    """The figure seen from rotation ``R`` through a small id pass."""
    R = np.asarray(R, dtype=np.float64)
    pk = raster.pack_ids(p.arrays, R)
    boxes = [pk["atom_reach"], pk["half_reach"]]
    if len(p.points):
        v = p.points @ R.T
        boxes.append(np.stack([v[:, 0], v[:, 0], v[:, 1], v[:, 1]], axis=1))
    box = np.concatenate([b for b in boxes if len(b)]) if any(len(b) for b in boxes) else None
    if box is None:
        extent = (-1.0, 1.0, -1.0, 1.0)
    else:
        extent = (float(box[:, 0].min()), float(box[:, 1].max()),
                  float(box[:, 2].min()), float(box[:, 3].max()))
    frame = p.fit(extent, p.size, p.margin)
    plane = raster.id_plane(pk, frame)
    judged = ~p.boundary & (plane.seen > 0)
    covered = judged & (plane.front < (1.0 - HIDDEN_SHARE) * plane.seen)
    n = int(judged.sum())
    return Look(hidden=float(covered.sum()) / n if n else 0.0,
                hidden_atoms=[int(k) for k in plane.index[covered]],
                empty=float((plane.ids < 0).mean()),
                unjudged=int((~p.boundary & (plane.seen == 0)).sum()))


def stacked(scene: dict, geometry: Mapping, R, look: Look) -> float:
    """The share of the judged atoms hidden behind an atom of their own site
    at their own place in the picture (:data:`STACKED_REACH`).

    A site is the asymmetric-unit atom, ``sites[k]["index"]``, so a copy made
    by a rotation counts as well as one made by a translation: in one cell of
    HKUST-1 down a, 24 of the 328 hidden atoms are behind a translate of
    themselves and all 328 behind an atom of their own site.
    """
    if not look.hidden_atoms:
        return 0.0
    R = np.asarray(R, dtype=np.float64)
    drawn = np.array([a["index"] for a in scene["atoms"]], dtype=np.int64)
    view = np.array([a["pos"] for a in scene["atoms"]], dtype=np.float64).reshape(-1, 3) @ R.T
    shape = np.array([a["shape"] for a in scene["atoms"]], dtype=np.float64).reshape(-1, 3, 3)
    reach = np.linalg.norm(np.einsum("ij,njk->nik", R[:2], shape), axis=2).max(axis=1)
    sites, atoms = geometry["sites"], geometry["atoms"]
    site = np.array([sites[atoms[k]["site"]]["index"] for k in drawn], dtype=np.int64)
    at = {int(k): n for n, k in enumerate(drawn)}
    rows = np.array([at[k] for k in look.hidden_atoms], dtype=np.int64)
    # the tree finds the candidates within reach (≤); the strict test then
    # decides, so the count is the one an all-pairs scan gives
    found = cKDTree(view[:, :2]).query_ball_point(view[rows, :2], STACKED_REACH * reach[rows])
    count = 0
    for n, near in zip(rows, found):
        near = np.asarray(near, dtype=np.int64)
        near = near[(np.hypot(view[near, 0] - view[n, 0], view[near, 1] - view[n, 1])
                     < STACKED_REACH * reach[n])]
        count += bool(((view[near, 2] > view[n, 2]) & (site[near] == site[n])).any())
    return look.hidden * count / len(look.hidden_atoms)


def directions(limit: int = SEARCH_INDEX) -> list[list[int]]:
    """Every primitive [u, v, w] with indices of magnitude at most ``limit``,
    smallest indices first, then fewest minus signs, then the first index
    positive.

    A direction and its opposite leave the same share of the frame empty, and
    often hide the same atoms, so the signs decide those ties: sorted by ``d``
    alone, [-2, -2, -1] came before [2, 2, 1] and [-1, 1, 0] before [1, -1, 0].
    """
    span = range(-limit, limit + 1)
    out = [[u, v, w] for u in span for v in span for w in span
           if (u, v, w) != (0, 0, 0) and math.gcd(math.gcd(abs(u), abs(v)), abs(w)) == 1]
    return sorted(out, key=lambda d: (sum(abs(x) for x in d), max(abs(x) for x in d),
                                      sum(x < 0 for x in d), next(x for x in d if x) < 0, d))


def choose_view(geometry: Mapping, p: Probe, up, turn):
    """The low-index view with the least hidden, then the least empty.

    Each candidate is a direction [u, v, w] toward the viewer with the
    convention's up (``up=`` if given) and ``turn`` applied, plus the opening
    view, so the answer is never worse than it on these two numbers.  Ties go
    to the smaller indices, so the search is deterministic and the rotation it
    returns is what the recipe pins.  Returns the chosen ``view`` for
    :func:`.views.resolve` and the top :data:`N_CANDIDATES` as dicts of
    ``view``, ``hidden`` and ``empty``, the numbers the search read at
    :data:`ID_SIZE` from atoms and bonds alone.
    """
    tried, refused = [], None
    for rank, view in enumerate([*directions(), OPENING]):
        try:
            R = views.resolve(geometry, view, up, turn)
        except ValueError as exc:   # an up= along this direction cannot be up
            refused = refused or exc
            continue
        seen = look(p, R)
        tried.append((seen.hidden, seen.empty, rank, view))
    if not tried:
        raise refused
    tried.sort(key=lambda t: t[:3])
    return tried[0][3], [{"view": v, "hidden": h, "empty": e}
                         for h, e, _, v in tried[:N_CANDIDATES]]
