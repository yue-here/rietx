"""The dichotomy traversal's two exactness claims, on its numpy loop.

WP-1508 built this module to hold a numba traversal to the numpy loop on the
bit.  That traversal left with numba (WP-1940), and two claims remain that the
numpy loop makes alone: the centred replay on a leaf's survivors gives the
verdict the whole set gives (WP-1509), and the batched ordering key is the
scalar one on the bit.  A compiled port of the traversal is held to the numpy
loop leaf by leaf (``src/rietx/indexing/CLAUDE.md``).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.indexing import dichotomy
from rietx.indexing.dichotomy import (
    _centre_volume,
    _centre_volumes,
    _initial_box,
    _test_box,
    search_dichotomy,
)
from rietx.indexing.qspace import metric_basis
from tests.test_indexing_engines import spec_for, synthetic_peaks


def _bits(x) -> bytes:
    return np.asarray(x, dtype=np.float64).tobytes()


@pytest.mark.parametrize("system", ("cubic", "tetragonal", "trigonal",
                                    "orthorhombic"))
def test_the_centred_replay_on_survivors_is_the_whole_set_replay(
        system, monkeypatch):
    """WP-1509: at every leaf, each centring's verdict on the leaf's survivors
    is its verdict on the centring's whole search set, which is what the leaf
    asked before.

    The replay's only output is that verdict, so this is the whole equivalence
    claim.  The four systems are the ones with more than one centring, and a
    P lattice's list refuses most centred replays, so both verdicts occur —
    the last assertion is the vacuity guard.
    """
    original = dichotomy._centred_replay
    verdicts = {True: 0, False: 0}

    def checking(m_full, rows, member, lo, hi, basis, q_hi, det_band, swaps,
                 lo_search, hi_search, n_unindexed):
        got = original(m_full, rows, member, lo, hi, basis, q_hi, det_band,
                       swaps, lo_search, hi_search, n_unindexed)
        want = _test_box(m_full[member], lo, hi, basis, q_hi, det_band, swaps,
                         lo_search, hi_search, n_unindexed) is not None
        assert got == want
        verdicts[got] += 1
        return got

    monkeypatch.setattr(dichotomy, "_centred_replay", checking)
    peaks, _cell = synthetic_peaks(system)
    search_dichotomy(peaks, spec=spec_for(system))
    assert verdicts[True] and verdicts[False], verdicts


def test_the_ordering_key_is_the_scalar_one_on_the_bit():
    """``_centre_volumes`` orders the grid's survivors.

    It replaced a per-cell loop (WP-1508), and it may not move a single bit of
    the key: two cells whose keys differ in the
    last place would swap, and the search would visit them in another order.
    Boxes are drawn over the whole triclinic domain, where most centres are not
    lattices at all, so the ``inf`` branch is exercised beside the finite one.
    """
    rng = np.random.default_rng(15081)
    for system in ("cubic", "hexagonal", "orthorhombic", "monoclinic", "triclinic"):
        basis = metric_basis(system)
        spec = spec_for("monoclinic")
        lo0, hi0 = _initial_box(basis, spec)
        boxes = []
        for _ in range(300):
            a = lo0 + rng.random(len(lo0)) * (hi0 - lo0)
            b = lo0 + rng.random(len(lo0)) * (hi0 - lo0)
            boxes.append((np.minimum(a, b), np.maximum(a, b), None))
        want = [_centre_volume(basis, lo, hi) for lo, hi, _ in boxes]
        got = _centre_volumes(basis, boxes)
        assert _bits(got) == _bits(want), system
        if system == "triclinic":
            assert np.isinf(want).any() and np.isfinite(want).any()
    assert _centre_volumes(metric_basis("cubic"), []) == []
