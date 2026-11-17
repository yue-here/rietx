"""Planar rings of the drawn bond graph, for a filled-ring figure (WP-1548 D2).

A ring here is a cycle of the sticks a figure draws whose atoms lie in one
plane, and never more than that.  A CIF carries no bond orders as a rule, and
a coordinate-only source cannot tell an aromatic ring from a puckered one with
the same bonds (:mod:`rietx.crystallography.fragments`), so nothing here
claims a ring is aromatic: the test is geometric, a size range and a distance
from the ring's mean plane.

**The graph is keyed by position, never by a bond's ``i`` and ``j``.**  In
the geometry :func:`rietx.gui.structure3d.build` returns, a bond's ``j`` can
name the far end's in-cell representative rather than the image the stick
reaches, so a graph on ``i``/``j`` closes false rings through edges of 6-11 Å
on paracetamol (``docs/wp/1548-measure/rings_probe.py``).  Each stick's two
end positions ``a`` and ``b`` are matched to drawn atoms' ``pos`` instead, and
a stick whose far end is not drawn joins no ring.

A ring a cell edge cuts closes only where its every atom is drawn, so the
default one-cell drawing (the cell plus one bonded shell) closes few of an
organic's rings and a block (``extent=``) closes them.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

import numpy as np

#: The ring sizes a figure fills: five- and six-membered rings, as ChimeraX
#: caps its filled rings at six members (``docs/practice.md`` § Depth cueing,
#: and filled rings and faces).
RING_SIZES = (5, 6)

#: A ring is planar when no atom of it lies further than this, in Å, from the
#: least-squares plane through its atoms (:func:`ring_deviation`).
#:
#: Measured on the drawn bonds of the eight carbon-bearing CIFs in
#: ``tests/data`` (``src/rietx/data`` ships none), each in a 2×2×2 block
#: (WP-1548, ``docs/wp/1548-measure/rings_planarity.txt``): the 396 benzene and
#: pyridine six-rings of five phases sit at most 0.025 Å from their mean plane
#: (acridine, COD 2242872), and the 52 cyclohexane chairs of C₁₆H₂₆ (COD
#: 1550439), the one phase with saturated rings, 0.226-0.235 Å.  No five- or
#: six-ring falls between 0.05 and 0.2 Å.  0.1 Å sits four times above the
#: flat bound and 2.3 times below the puckered one.  In Cremer & Pople's
#: coordinates it turns away a chair puckered by more than Q = 0.245 Å, a boat
#: or twist-boat by more than 0.200 Å and a five-ring by more than 0.166 Å.  A
#: ring bent on purpose, such as a cyclophane's boat-shaped benzene, can fall
#: past it, and none is on disk.
PLANAR_RING_TOLERANCE = 0.1

#: An atom with more drawn bonds than this joins no ring.  The walk that finds
#: the rings (:func:`_cycles_up_to`) visits up to d·(d−1)^(k−2) paths from each
#: atom for a ring of k atoms over neighbours of degree d, so a block of
#: twelve-coordinate metals would cost 11⁴ paths an atom, while a cap of four
#: bounds it at 4·3⁴ = 324.  Measured on every CIF on disk as a 2×2×2 block
#: (WP-1548, ``docs/wp/1548-measure/rings_degree.txt``): no atom of a planar
#: five- or six-ring carries more than three drawn bonds, the cap turns none
#: of the 396 away, and the one 24-bond phase (COD 1000055, 315 atoms) costs
#: 1.90 s without it and nothing with it.  Four leaves room for a metal over a
#: cyclopentadienyl ring, whose carbons carry two ring bonds, a hydrogen and
#: the metal.  A ring through a metal centre (a chelate, a paddlewheel's
#: Cu₂O₄C₂ cage) is turned away by the cap whatever its shape.
MAX_RING_DEGREE = 4

#: Two positions closer than this, in Å, are one drawn atom: a stick's end is
#: a copy of its atom's ``pos``, so the match is exact up to rounding.
_SAME_POSITION = 1e-3


def bond_edges(geometry: Mapping[str, Any]) -> list[tuple[int, int]]:
    """The drawn bond graph: each stick as a sorted pair of indices into
    ``geometry["atoms"]``, once, matched by the stick's end positions.

    A stick whose either end matches no drawn atom (its far end leaves the
    drawing) is dropped, as is a stick from an atom to itself.
    """
    from scipy.spatial import cKDTree

    atoms = geometry.get("atoms") or []
    bonds = geometry.get("bonds") or []
    if not atoms or not bonds:
        return []
    tree = cKDTree(np.array([a["pos"] for a in atoms], dtype=np.float64))
    ends = np.array([[b["a"], b["b"]] for b in bonds], dtype=np.float64).reshape(-1, 3)
    dist, index = tree.query(ends, distance_upper_bound=_SAME_POSITION)
    index = np.where(np.isfinite(dist), index, -1).reshape(-1, 2)
    edges = {(int(min(i, j)), int(max(i, j))) for i, j in index
             if i >= 0 and j >= 0 and i != j}
    return sorted(edges)


def _cycles_up_to(adjacency: Sequence[Sequence[int]], max_size: int) -> list[list[int]]:
    """Every simple cycle of at most ``max_size`` atoms, once each, in order
    round the cycle and starting at its lowest index."""
    out: list[list[int]] = []
    for start in range(len(adjacency)):
        path = [start]
        on_path = {start}

        def extend(node: int) -> None:
            for nxt in adjacency[node]:
                if nxt == start and len(path) >= 3:
                    # each cycle is walked twice, once each way: keep one
                    if path[1] < path[-1]:
                        out.append(list(path))
                elif nxt > start and nxt not in on_path and len(path) < max_size:
                    path.append(nxt)
                    on_path.add(nxt)
                    extend(nxt)
                    path.pop()
                    on_path.discard(nxt)

        extend(start)
    return out


def _edge_mask(cycle: Sequence[int], edge_bit: Mapping[tuple[int, int], int]) -> int:
    mask = 0
    for k, i in enumerate(cycle):
        j = cycle[(k + 1) % len(cycle)]
        mask ^= 1 << edge_bit[(i, j) if i < j else (j, i)]
    return mask


def _reduce(vector: int, basis: dict[int, int]) -> int:
    """``vector`` reduced over GF(2) by a basis keyed on each row's top bit."""
    while vector:
        top = vector.bit_length() - 1
        row = basis.get(top)
        if row is None:
            return vector
        vector ^= row
    return 0


def smallest_rings(edges: Iterable[tuple[int, int]], n_atoms: int,
                   max_size: int = max(RING_SIZES),
                   max_degree: int | None = None) -> list[list[int]]:
    """The smallest rings of a graph up to ``max_size`` atoms, each in order
    round the ring.

    A ring is kept when it is not the sum (the symmetric difference of edge
    sets) of strictly smaller rings: the rings of the smallest set of smallest
    rings (Figueras, J. (1996). Ring perception using breadth-first search.
    *J. Chem. Inf. Comput. Sci.* 36, 986-991), together with every ring of the
    same size a choice between equal rings would leave out, which is the
    union of all minimum cycle bases (Vismara, P. (1997). Union of all the
    minimum cycle bases of a graph. *Electron. J. Combin.* 4, R9).  A figure
    wants that union, since the smallest set keeps five of a cube's six faces
    and which five is arbitrary.  Naphthalene gives its two six-rings and not
    the ten-ring round them, which is their sum.

    Every cycle up to ``max_size`` is enumerated by a bounded depth-first walk,
    which is exact for the rings up to that size (a ring's relevance depends
    only on the strictly smaller ones), and each size class is tested over
    GF(2) against the classes below it.

    ``max_degree`` bounds the walk: an atom with more distinct neighbours than
    that is taken out of the graph first, with its bonds
    (:data:`MAX_RING_DEGREE`).  Relevance is then judged on what is left, so a
    ring that is the sum of smaller rings through a removed atom can be kept.
    ``None`` removes nothing.
    """
    edges = {(i, j) if i < j else (j, i) for i, j in edges if i != j}
    if max_degree is not None:
        degree = [0] * n_atoms
        for i, j in edges:
            degree[i] += 1
            degree[j] += 1
        edges = {(i, j) for i, j in edges
                 if degree[i] <= max_degree and degree[j] <= max_degree}
    adjacency: list[list[int]] = [[] for _ in range(n_atoms)]
    edge_bit: dict[tuple[int, int], int] = {}
    for i, j in sorted(edges):
        edge_bit[(i, j)] = len(edge_bit)
        adjacency[i].append(j)
        adjacency[j].append(i)
    for row in adjacency:
        row.sort()
    by_size: dict[int, list[list[int]]] = {}
    for cycle in _cycles_up_to(adjacency, max_size):
        by_size.setdefault(len(cycle), []).append(cycle)
    kept: list[list[int]] = []
    basis: dict[int, int] = {}
    for size in sorted(by_size):
        masks = [(_edge_mask(c, edge_bit), c) for c in by_size[size]]
        # tested against the strictly smaller rings alone, then added
        relevant = [(m, c) for m, c in masks if _reduce(m, basis)]
        for mask, cycle in relevant:
            kept.append(cycle)
            rest = _reduce(mask, basis)
            if rest:
                basis[rest.bit_length() - 1] = rest
    return kept


def ring_deviation(points: np.ndarray) -> float:
    """The largest distance, in Å, of ``points`` from their least-squares
    plane: the plane through their centroid normal to the direction of least
    spread, the last right singular vector of the centred coordinates
    (Schomaker, V., Waser, J., Marsh, R. E. & Bergman, G. (1959). To fit a
    plane or a line to a set of points by least squares. *Acta Cryst.* 12,
    600-604)."""
    points = np.asarray(points, dtype=np.float64)
    centred = points - points.mean(axis=0)
    _, _, vt = np.linalg.svd(centred)
    return float(np.abs(centred @ vt[-1]).max())


def planar_rings(geometry: Mapping[str, Any], *, sizes: Sequence[int] = RING_SIZES,
                 tolerance: float = PLANAR_RING_TOLERANCE,
                 max_degree: int | None = MAX_RING_DEGREE) -> list[list[int]]:
    """The planar rings of a drawing: each a list of indices into
    ``geometry["atoms"]`` in order round the ring.

    ``geometry`` is what :func:`rietx.gui.structure3d.build` returns.  A ring
    is one of :func:`smallest_rings` on :func:`bond_edges`, of a size in
    ``sizes``, whose atoms lie within ``tolerance`` Å of their mean plane
    (:func:`ring_deviation`), through no atom of more than ``max_degree``
    drawn bonds (:data:`MAX_RING_DEGREE`).  Nothing here says a ring is
    aromatic.
    """
    atoms = geometry.get("atoms") or []
    if not sizes:
        return []
    pos = np.array([a["pos"] for a in atoms], dtype=np.float64).reshape(-1, 3)
    wanted = set(sizes)
    return [ring for ring in smallest_rings(bond_edges(geometry), len(atoms), max(wanted),
                                            max_degree)
            if len(ring) in wanted and ring_deviation(pos[ring]) <= tolerance]


# ----------------------------------------------------------------------
# fills: what the scene draws for a ring or a named face (WP-1548 D4)

def _fan(n: int) -> list[list[int]]:
    """A convex polygon's triangles as a fan from its first vertex."""
    return [[0, k, k + 1] for k in range(1, n - 1)]


def ring_fills(geometry: Mapping[str, Any], *, color: str | None = None,
               **found: Any) -> list[dict]:
    """Each planar ring of a drawing as a fill the scene draws
    (:func:`rietx.viz.figure3d.scene.build_scene`'s ``fills``): ``kind``
    ``"ring"``, ``vertices`` the ring's atom indices in order round it, and
    ``faces`` its triangles as index triples into ``vertices``, a fan from the
    first.  A five- or six-ring within :data:`PLANAR_RING_TOLERANCE` of its
    plane is convex, so the fan covers it once.  ``color`` is ``#rrggbb``, or
    ``None`` for the scene's :data:`~rietx.viz.figure3d.scene.FILL_COLOR`;
    ``found`` passes to :func:`planar_rings`.
    """
    return [{"kind": "ring", "vertices": ring, "faces": _fan(len(ring)), "color": color}
            for ring in planar_rings(geometry, **found)]


def face_fill(geometry: Mapping[str, Any], atoms: Iterable[int], *,
              color: str | None = None,
              tolerance: float = PLANAR_RING_TOLERANCE) -> dict:
    """The fill a named face draws over the atoms ``atoms``, indices into
    ``geometry["atoms"]`` (WP-1548 D4).

    A set within ``tolerance`` Å of its mean plane (:func:`ring_deviation`) is
    drawn as the convex polygon round it, a fan from its first corner, and an
    atom inside the polygon is no corner.  Any other set is drawn as its convex
    hull, like a polyhedron with no centre, each triangle wound outward
    (Barber, C. B., Dobkin, D. P. & Huhdanpaa, H. (1996). The Quickhull
    algorithm for convex hulls. *ACM Trans. Math. Softw.* 22, 469-483).  Fewer
    than three atoms, or a set on one line, raises.
    """
    from scipy.spatial import ConvexHull

    index = sorted({int(k) for k in atoms})
    if len(index) < 3:
        raise ValueError(f"a face needs three atoms or more; it names {len(index)}")
    every = geometry.get("atoms") or []
    pos = np.array([every[k]["pos"] for k in index], dtype=np.float64)
    centred = pos - pos.mean(axis=0)
    _, spread, vt = np.linalg.svd(centred)
    if spread[1] <= 1e-9 * spread[0]:
        raise ValueError("the face's atoms lie on one line, which bounds no area")
    if float(np.abs(centred @ vt[-1]).max()) <= tolerance:
        corners = [int(k) for k in ConvexHull(centred @ vt[:2].T).vertices]
        return {"kind": "face", "vertices": [index[k] for k in corners],
                "faces": _fan(len(corners)), "color": color}
    hull = ConvexHull(pos)
    used = sorted({int(v) for simplex in hull.simplices for v in simplex})
    local = {v: k for k, v in enumerate(used)}
    centre = pos[used].mean(axis=0)
    faces = []
    for simplex in hull.simplices:
        a, b, c = (int(v) for v in simplex)
        if np.cross(pos[b] - pos[a], pos[c] - pos[a]) @ (pos[a] - centre) < 0:
            b, c = c, b
        faces.append([local[a], local[b], local[c]])
    return {"kind": "face", "vertices": [index[v] for v in used], "faces": faces,
            "color": color}
