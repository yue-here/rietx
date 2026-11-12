"""WP-1548 D2: planar rings of the drawn bond graph (``viz.figure3d.rings``).

A ring is a smallest ring of the sticks a figure draws, keyed by the sticks'
end positions, whose atoms lie within ``PLANAR_RING_TOLERANCE`` of their mean
plane.  The tolerance's measurement is ``docs/wp/1548-measure/rings_planarity.txt``.
"""

from __future__ import annotations

import pathlib
import warnings

import numpy as np
import pytest

from rietx.crystallography.cif import structure_from_cif
from rietx.gui import structure3d as s3
from rietx.viz.figure3d import rings

DATA = pathlib.Path(__file__).resolve().parent / "data"
BLOCK = ((0, 2), (0, 2), (0, 2))


def _drawn(name: str, extent=BLOCK) -> dict:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return s3.build(structure_from_cif(str(DATA / name)), extent=extent, max_atoms=5000)


def _positions(geometry: dict) -> np.ndarray:
    return np.array([a["pos"] for a in geometry["atoms"]], dtype=np.float64)


def _edges_round(ring):
    return [(ring[k], ring[(k + 1) % len(ring)]) for k in range(len(ring))]


@pytest.fixture(scope="module")
def paracetamol():
    return _drawn("cod_2104364.cif")


# --- the graph alone ------------------------------------------------------

def _hexagon(start: int) -> list[tuple[int, int]]:
    return [(start + k, start + (k + 1) % 6) for k in range(6)]


def test_fused_rings_give_the_two_rings_never_their_sum():
    """Naphthalene's two six-rings, never the ten-ring round them."""
    edges = [(0, 1), (1, 2), (2, 3), (3, 4), (4, 5), (5, 0),
             (4, 6), (6, 7), (7, 8), (8, 9), (9, 5)]
    found = rings.smallest_rings(edges, 10, max_size=10)
    assert sorted(sorted(r) for r in found) == [[0, 1, 2, 3, 4, 5], [4, 5, 6, 7, 8, 9]]


def test_equal_rings_are_all_kept():
    """A cube's six faces, where the smallest set of smallest rings keeps five."""
    corners = [(x, y, z) for x in (0, 1) for y in (0, 1) for z in (0, 1)]
    edges = [(i, j) for i in range(8) for j in range(i + 1, 8)
             if sum(a != b for a, b in zip(corners[i], corners[j])) == 1]
    found = rings.smallest_rings(edges, 8, max_size=6)
    assert len(found) == 6 and all(len(r) == 4 for r in found)


def test_a_ring_comes_back_in_order_round_it():
    edges = set(_hexagon(0)) | {(0, 6), (6, 7)}
    (ring,) = rings.smallest_rings(sorted(edges), 8)
    assert sorted(ring) == list(range(6))
    for i, j in _edges_round(ring):
        assert (min(i, j), max(i, j)) in {(min(a, b), max(a, b)) for a, b in edges}


def _geometry(points, bonds) -> dict:
    return {"atoms": [{"pos": list(map(float, p)), "site": 0} for p in points],
            "bonds": [{"i": i, "j": j, "a": list(map(float, a)), "b": list(map(float, b))}
                      for i, j, a, b in bonds]}


def _ring_points(z):
    angle = np.arange(6) * np.pi / 3
    return np.c_[1.4 * np.cos(angle), 1.4 * np.sin(angle), z]


def test_planarity_keeps_a_flat_ring_and_turns_a_chair_away():
    flat = _ring_points(np.zeros(6))
    chair = _ring_points(0.25 * (-1.0) ** np.arange(6))
    for points, kept in ((flat, 1), (chair, 0)):
        bonds = [(i, j, points[i], points[j]) for i, j in _hexagon(0)]
        assert len(rings.planar_rings(_geometry(points, bonds))) == kept
    assert rings.ring_deviation(chair) == pytest.approx(0.25)


def test_a_stick_whose_far_end_is_not_drawn_joins_no_ring():
    points = _ring_points(np.zeros(6))
    bonds = [(i, j, points[i], points[j]) for i, j in _hexagon(0)]
    # one stick names atom 0 as its far end but reaches an image that is not drawn
    bonds[-1] = (5, 0, points[5], points[0] + [9.0, 0.0, 0.0])
    geometry = _geometry(points, bonds)
    assert len(rings.bond_edges(geometry)) == 5
    assert rings.planar_rings(geometry) == []


# --- drawn structures -----------------------------------------------------

def test_paracetamol_in_a_block_gives_its_benzene_rings(paracetamol):
    found = rings.planar_rings(paracetamol)
    assert found
    pos = _positions(paracetamol)
    for ring in found:
        elements = {paracetamol["sites"][paracetamol["atoms"][k]["site"]]["element"]
                    for k in ring}
        assert len(ring) == 6 and elements == {"C"}
        assert rings.ring_deviation(pos[ring]) < 0.05


def test_every_ring_edge_is_a_drawn_bond(paracetamol):
    """The i/j trap: a bond's ``j`` can be the far end's in-cell
    representative, so an i/j graph closes rings through edges of several Å.
    Each consecutive pair of a ring is a stick the figure draws."""
    pos = _positions(paracetamol)
    sticks = {tuple(sorted((tuple(np.round(b["a"], 6)), tuple(np.round(b["b"], 6)))))
              for b in paracetamol["bonds"]}
    longest = max(float(np.linalg.norm(np.subtract(b["a"], b["b"])))
                  for b in paracetamol["bonds"])
    for ring in rings.planar_rings(paracetamol):
        for i, j in _edges_round(ring):
            assert np.linalg.norm(pos[i] - pos[j]) <= longest
            assert tuple(sorted((tuple(np.round(pos[i], 6)), tuple(np.round(pos[j], 6))))) in sticks


def test_the_one_cell_drawing_closes_no_false_ring():
    """Paracetamol's one-cell drawing: its i/j graph closes rings through
    edges of over 6 Å, and the position graph closes none, since the cell
    adds one bonded shell and cuts every benzene ring an edge crosses."""
    geometry = _drawn("cod_2104364.cif", extent=None)
    pos = _positions(geometry)
    ij = sorted({(min(b["i"], b["j"]), max(b["i"], b["j"])) for b in geometry["bonds"]
                 if b["i"] != b["j"]})
    false = rings.smallest_rings(ij, len(pos))
    assert false and max(np.linalg.norm(pos[i] - pos[j])
                         for r in false for i, j in _edges_round(r)) > 6.0
    assert rings.planar_rings(geometry) == []


def test_cyclohexane_chairs_are_rings_the_planarity_test_turns_away():
    """C16H26 (COD 1550439): its six-rings are found, and every one is a chair."""
    geometry = _drawn("cod_1550439.cif")
    found = [r for r in rings.smallest_rings(rings.bond_edges(geometry),
                                             len(geometry["atoms"])) if len(r) == 6]
    assert found
    pos = _positions(geometry)
    assert min(rings.ring_deviation(pos[r]) for r in found) > 2 * rings.PLANAR_RING_TOLERANCE
    assert rings.planar_rings(geometry) == []


def test_a_structure_with_no_rings_gives_none():
    """C4H2 (COD 1577467): chains, and no cycle of any size on its sticks."""
    geometry = _drawn("cod_1577467.cif")
    assert rings.bond_edges(geometry)
    assert rings.smallest_rings(rings.bond_edges(geometry), len(geometry["atoms"])) == []
    assert rings.planar_rings(geometry) == []
