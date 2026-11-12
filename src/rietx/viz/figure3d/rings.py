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
                   max_size: int = max(RING_SIZES)) -> list[list[int]]:
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
    """
    adjacency: list[list[int]] = [[] for _ in range(n_atoms)]
    edge_bit: dict[tuple[int, int], int] = {}
    for i, j in edges:
        i, j = (i, j) if i < j else (j, i)
        if (i, j) in edge_bit or i == j:
            continue
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
                 tolerance: float = PLANAR_RING_TOLERANCE) -> list[list[int]]:
    """The planar rings of a drawing: each a list of indices into
    ``geometry["atoms"]`` in order round the ring.

    ``geometry`` is what :func:`rietx.gui.structure3d.build` returns.  A ring
    is one of :func:`smallest_rings` on :func:`bond_edges`, of a size in
    ``sizes``, whose atoms lie within ``tolerance`` Å of their mean plane
    (:func:`ring_deviation`).  Nothing here says a ring is aromatic.
    """
    atoms = geometry.get("atoms") or []
    if not sizes:
        return []
    pos = np.array([a["pos"] for a in atoms], dtype=np.float64).reshape(-1, 3)
    wanted = set(sizes)
    return [ring for ring in smallest_rings(bond_edges(geometry), len(atoms), max(wanted))
            if len(ring) in wanted and ring_deviation(pos[ring]) <= tolerance]
