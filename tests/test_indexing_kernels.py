"""The dichotomy traversal's exactness claims.

WP-1508 built this module to hold a numba traversal to the numpy loop on the
bit.  That traversal left with numba (WP-1940), and two claims remain that the
numpy loop makes alone: the centred replay on a leaf's survivors gives the
verdict the whole set gives (WP-1509), and the batched ordering key is the
scalar one on the bit.

The box test runs compiled again since WP-1959 (``rietx-kernels`` 1.3.0,
``kernels/src/dichotomy.rs``), and the numpy loop is its oracle in three
steps: numpy's row sum has the association the kernel copies, every box a
real search tests gets the same answer from both, and a whole search reaches
the same leaves in the same order.  The pin's floor is 1.3, so they run
wherever the wheel loads, and skip where it was declined: a wheel that
predates the kernel is one, which an install has to go round the resolver to
get.  ``kernels.yml`` runs them against the wheel a pull request builds as
well.
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
from rietx.model import compiled
from tests.test_indexing_engines import spec_for, synthetic_peaks

try:
    import rietx_kernels
except ImportError:            # pragma: no cover - the wheel is a dependency
    rietx_kernels = None

needs_kernel = pytest.mark.skipif(
    not compiled.available(),
    reason=f"the rietx-kernels wheel did not load: {compiled.unavailable()}")


def _bits(x) -> bytes:
    return np.asarray(x, dtype=np.float64).tobytes()


@pytest.mark.parametrize("compiled_path", (False, True))
@pytest.mark.parametrize("system", ("cubic", "tetragonal", "trigonal",
                                    "orthorhombic"))
def test_the_centred_replay_on_survivors_is_the_whole_set_replay(
        system, compiled_path, monkeypatch):
    """WP-1509: at every leaf, each centring's verdict on the leaf's survivors
    is its verdict on the centring's whole search set, which is what the leaf
    asked before.

    The replay's only output is that verdict, so this is the whole equivalence
    claim.  The four systems are the ones with more than one centring, and a
    P lattice's list refuses most centred replays, so both verdicts occur —
    the last assertion is the vacuity guard.  Each path is declared, and the
    whole-set verdict is always the numpy loop's.
    """
    if compiled_path and not compiled.available():
        pytest.skip(f"the rietx-kernels wheel did not load: {compiled.unavailable()}")
    monkeypatch.setattr(compiled, "_ENABLED", compiled_path)
    original = dichotomy._centred_replay
    verdicts = {True: 0, False: 0}

    def checking(m_full, rows, member, lo, hi, basis, q_hi, det_band, swaps,
                 lo_search, hi_search, n_unindexed, anchors=None,
                 box_test=None):
        got = original(m_full, rows, member, lo, hi, basis, q_hi, det_band,
                       swaps, lo_search, hi_search, n_unindexed,
                       anchors=anchors, box_test=box_test)
        want = _test_box(m_full[member], lo, hi, basis, q_hi, det_band, swaps,
                         lo_search, hi_search, n_unindexed,
                         anchors=anchors) is not None
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


def test_numpy_sums_a_rows_terms_left_to_right():
    """The kernel's Q bounds copy ``np.where(...).sum(axis=1)`` term by term,
    left to right, which is numpy's association at the widths a metric has
    (one to six).  A numpy that changed it would move the kernel off the bit,
    and this says so first.  The pairwise check proves the draw can tell the
    two associations apart."""
    rng = np.random.default_rng(1959)
    for n in range(1, 7):
        x = (rng.standard_normal((20_000, n))
             * 10.0 ** rng.integers(-8, 8, (20_000, n)))
        lo = rng.standard_normal(n)
        hi = lo + np.abs(rng.standard_normal(n))
        terms = np.where(x > 0.0, x * lo, x * hi)
        left = terms[:, 0].copy()
        for j in range(1, n):
            left = left + terms[:, j]
        assert _bits(terms.sum(axis=1)) == _bits(left), n
        if n == 4:
            pairwise = (terms[:, 0] + terms[:, 1]) + (terms[:, 2] + terms[:, 3])
            assert _bits(terms.sum(axis=1)) != _bits(pairwise)


class _Enough(Exception):
    pass


def _recorded_boxes(system: str, limit: int) -> tuple[list, list]:
    """``_test_box`` calls and ``_push_children`` children from a real search
    on the numpy loop, up to ``limit`` boxes."""
    boxes, children = [], []
    real_test, real_push = dichotomy._test_box, dichotomy._push_children

    def record_box(m, lo, hi, basis, q_hi, det_band, swaps, lo_s, hi_s,
                 n_unindexed, ids=None, anchors=None):
        boxes.append((np.ascontiguousarray(m), lo.copy(), hi.copy(), basis,
                      q_hi, det_band, swaps, lo_s, hi_s, n_unindexed))
        if len(boxes) >= limit:
            raise _Enough
        return real_test(m, lo, hi, basis, q_hi, det_band, swaps, lo_s, hi_s,
                         n_unindexed, ids=ids, anchors=anchors)

    def push(stack, kids, m, ids, lo_s, hi_s, n_unindexed, depth, anchors=None):
        children.append((np.ascontiguousarray(m), kids, lo_s, hi_s))
        real_push(stack, kids, m, ids, lo_s, hi_s, n_unindexed, depth,
                  anchors=anchors)

    was = compiled.set_enabled(False)
    dichotomy._test_box, dichotomy._push_children = record_box, push
    try:
        peaks, _cell = synthetic_peaks(system)
        search_dichotomy(peaks, spec=spec_for(system))
    except _Enough:
        pass
    finally:
        dichotomy._test_box, dichotomy._push_children = real_test, real_push
        compiled.set_enabled(was)
    return boxes, children


_ID_TYPES = (np.uint8, np.uint16, np.uint32, np.uint64, np.int64)


def _kernel_box(m, lo, hi, basis, q_hi, det_band, swaps, lo_s, hi_s,
                n_unindexed, dtype=np.uint32):
    ids = np.arange(len(m), dtype=dtype)
    return rietx_kernels.dichotomy_box_test(
        m, ids, lo, hi, np.ascontiguousarray(basis.T), q_hi, det_band[0],
        det_band[1], np.asarray(swaps, dtype=np.int64).reshape(-1),
        np.ascontiguousarray(lo_s), np.ascontiguousarray(hi_s), n_unindexed,
        float(dichotomy.MAX_ANGLE_COSINE), True)


def _assert_same_box(want, got, m, label):
    assert (want is None) == (got is None), label
    if want is None:
        return
    pos, width, unique, col_max = got
    assert _bits(m[pos.astype(np.int64)]) == _bits(want[0]), label
    assert _bits(width) == _bits(want[1]), label
    assert unique == want[2], label
    if len(want[0]):
        assert _bits(col_max) == _bits(np.max(np.abs(want[0]), axis=0)), label


@needs_kernel
@pytest.mark.parametrize("system", ("cubic", "hexagonal", "trigonal",
                                    "orthorhombic", "monoclinic"))
def test_the_compiled_box_test_is_the_numpy_one_box_by_box(system):
    """Every box a real search tests, and every child it scores, gets the
    numpy loop's answer on the bit: survival, the surviving rows in their
    order, the width, the stopping rule, each column's largest |m|, and the
    child's (misses, pairs, rows reaching a line).  The row index type cycles
    through every one ``_row_index_type`` can choose, and both verdicts must
    occur."""
    boxes, children = _recorded_boxes(system, 1500)
    verdicts = {True: 0, False: 0}
    for k, (m, lo, hi, basis, q_hi, det_band, swaps, lo_s, hi_s,
            n_unindexed) in enumerate(boxes):
        dtype = _ID_TYPES[k % len(_ID_TYPES)]
        if len(m) > np.iinfo(dtype).max + 1:
            dtype = np.int64
        want = _test_box(m, lo, hi, basis, q_hi, det_band, swaps, lo_s, hi_s,
                         n_unindexed)
        got = _kernel_box(m, lo, hi, basis, q_hi, det_band, swaps, lo_s, hi_s,
                          n_unindexed, dtype)
        _assert_same_box(want, got, m, (system, k))
        verdicts[want is not None] += 1
    assert verdicts[True] and verdicts[False], verdicts
    basis_t = np.ascontiguousarray(metric_basis(system).T)
    for m, kids, lo_s, hi_s in children:
        ids = np.arange(len(m), dtype=np.uint32)
        for child_lo, child_hi in kids:
            q_min, q_max = dichotomy._q_bounds(m, child_lo, child_hi)
            hit = ((q_min[None, :] <= hi_s[:, None])
                   & (q_max[None, :] >= lo_s[:, None]))
            want = (len(hi_s) - int(np.count_nonzero(hit.any(axis=1))),
                    int(hit.sum()), int(np.count_nonzero(hit.any(axis=0))))
            assert rietx_kernels.dichotomy_child_key(
                m, ids, child_lo, child_hi, basis_t, lo_s, hi_s) == want


@needs_kernel
def test_the_compiled_row_free_prunes_are_the_numpy_ones():
    """The cone, obliquity, axis-swap and volume prunes on random monoclinic
    and triclinic boxes, where a synthetic search's first boxes cannot reach
    the obliquity bound.  Every line window spans the whole Q range, so only
    a row-free prune can refuse a box, and the obliquity prune must refuse
    some."""
    from rietx.indexing.dichotomy import _af_interval, _outside_obliquity
    from rietx.indexing.engines import trial_hkl
    from rietx.indexing.qspace import design_matrix

    rng = np.random.default_rng(1959)
    verdicts = {True: 0, False: 0}
    oblique = 0
    for system in ("monoclinic", "triclinic"):
        basis = metric_basis(system)
        n = basis.shape[0]
        m = np.ascontiguousarray(design_matrix(trial_hkl(3, "P")) @ basis.T)
        swaps = [(0, 1), (1, 2)]
        for _case in range(600):
            lo = rng.uniform(0.004, 0.05, size=n)
            hi = lo + rng.uniform(1e-4, 0.02, size=n)
            args = (m, lo, hi, basis, 1e9, (1e-7, 1e-3), swaps,
                    np.array([-1e9]), np.array([1e9]), 0)
            want = _test_box(*args)
            _assert_same_box(want, _kernel_box(*args), m, (system, lo, hi))
            verdicts[want is not None] += 1
            oblique += _outside_obliquity(*_af_interval(basis, lo, hi))
    assert verdicts[True] and verdicts[False] and oblique, (verdicts, oblique)


@needs_kernel
def test_the_compiled_line_count_beyond_a_mask_is_the_numpy_one():
    """Past 64 lines, or with a NaN window edge, the kernel counts lines one
    by one, as the numba twin did.  Both ways are held to numpy on recorded
    orthorhombic boxes with 70 and 40 windows, every other box with one
    window's low edge NaN."""
    boxes, _children = _recorded_boxes("orthorhombic", 400)
    rng = np.random.default_rng(64)
    for k, (m, lo, hi, basis, q_hi, det_band, swaps, _lo_s, _hi_s,
            n_unindexed) in enumerate(boxes):
        q = np.sort(rng.uniform(0.0, q_hi, 70))
        tol = rng.uniform(1e-4, 3e-3, 70)
        wide_lo, wide_hi = q - tol, q + tol
        if k % 2:
            wide_lo[k % 40] = np.nan
        for n_lines in (70, 40):
            args = (m, lo, hi, basis, q_hi, det_band, swaps,
                    wide_lo[:n_lines], wide_hi[:n_lines], n_unindexed + 30)
            _assert_same_box(_test_box(*args), _kernel_box(*args), m,
                             (k, n_lines))


@needs_kernel
def test_the_compiled_box_test_refuses_what_it_cannot_serve():
    """Every argument is checked before the GIL is released, and a refusal is
    a ``ValueError`` naming it, never a panic or a wrong answer."""
    basis = metric_basis("orthorhombic")
    m = np.ones((5, 3))
    lo, hi = np.full(3, 0.01), np.full(3, 0.02)
    edges = np.array([0.01]), np.array([0.02])

    def call(ids=None, basis_t=basis.T, swaps=(), rows=m):
        ids = np.arange(5, dtype=np.uint16) if ids is None else ids
        return rietx_kernels.dichotomy_box_test(
            rows, ids, lo, hi, np.ascontiguousarray(basis_t), 1.0, 0.0, 1.0,
            np.asarray(swaps, dtype=np.int64), *edges, 0, 0.8, False)

    call()
    with pytest.raises(ValueError, match="row 5 is outside m"):
        call(ids=np.arange(6, dtype=np.uint16))
    with pytest.raises(ValueError, match="ids must be"):
        call(ids=np.arange(5, dtype=np.float64))
    with pytest.raises(ValueError, match="basis_t"):
        call(basis_t=metric_basis("monoclinic").T)
    with pytest.raises(ValueError, match="swaps"):
        call(swaps=(0, 6))
    with pytest.raises(ValueError, match="C-contiguous"):
        call(rows=np.ones((3, 5)).T)
    with pytest.raises(ValueError, match="basis_t"):
        rietx_kernels.dichotomy_box_test(
            np.ones((5, 0)), np.arange(5, dtype=np.uint16), np.empty(0),
            np.empty(0), np.ones((6, 0)), 1.0, 0.0, 1.0,
            np.empty(0, dtype=np.int64), *edges, 0, 0.8, False)


@needs_kernel
@pytest.mark.parametrize("system", ("cubic", "tetragonal", "hexagonal",
                                    "trigonal", "orthorhombic"))
def test_the_compiled_search_reaches_the_numpy_loops_leaves(system,
                                                            monkeypatch):
    """A whole search on each path: the same leaves in the same order, each
    with the same surviving rows, centred-replay verdicts and refinement
    starts, and the same box count and answer.  Box counts alone cannot see
    an order, so the leaves are compared one by one."""
    real_replay, real_accept = dichotomy._centred_replay, dichotomy._accept
    trace: list = []

    def replay(m_full, rows, member, lo, hi, *a, **kw):
        got = real_replay(m_full, rows, member, lo, hi, *a, **kw)
        trace.append(("leaf", _bits(lo), _bits(hi), rows.tobytes(), got))
        return got

    def accept(basis, system_, centring, spec, theta, *a, **kw):
        # a[-3] is the leaf's width
        trace.append(("accept", centring, _bits(theta), _bits(a[-3])))
        return real_accept(basis, system_, centring, spec, theta, *a, **kw)

    monkeypatch.setattr(dichotomy, "_centred_replay", replay)
    monkeypatch.setattr(dichotomy, "_accept", accept)
    peaks, _cell = synthetic_peaks(system)
    runs = []
    for flag in (False, True):
        trace.clear()
        was = compiled.set_enabled(flag)
        try:
            assert (compiled.dichotomy_kernels() is not None) == flag
            result = search_dichotomy(peaks, spec=spec_for(system))
        finally:
            compiled.set_enabled(was)
        runs.append((list(trace), result.stats[f"{system}.boxes"],
                     [(_bits(c.cell), c.n_indexed) for c in result.candidates]))
    assert runs[0][0], "no leaf was reached"
    assert runs[0] == runs[1]


@needs_kernel
@pytest.mark.slow
def test_the_compiled_search_reaches_the_numpy_loops_leaves_where_boxes_are_oblique(
        monkeypatch):
    """The leaf-by-leaf comparison on a monoclinic search, the only kind in
    the fast set where the obliquity prune fires: #780's 61 lines over a
    narrow domain, 196 101 boxes and 30 leaves on either path, the prune
    refusing ~7 300 boxes on the numpy loop.  Slow because the numpy side
    takes ~10 s; ``kernels.yml`` runs it on every wheel a pull request
    builds."""
    from rietx.indexing.engines import SearchSpec
    from tests.repro_780 import peaks as peaks_780

    real_replay, real_accept = dichotomy._centred_replay, dichotomy._accept
    real_outside = dichotomy._outside_obliquity
    trace: list = []
    oblique = [0]

    def replay(m_full, rows, member, lo, hi, *a, **kw):
        got = real_replay(m_full, rows, member, lo, hi, *a, **kw)
        trace.append(("leaf", _bits(lo), _bits(hi), rows.tobytes(), got))
        return got

    def accept(basis, system_, centring, spec, theta, *a, **kw):
        trace.append(("accept", centring, _bits(theta), _bits(a[-3])))
        return real_accept(basis, system_, centring, spec, theta, *a, **kw)

    def outside(af_lo, af_hi):
        refused = real_outside(af_lo, af_hi)
        oblique[0] += refused
        return refused

    monkeypatch.setattr(dichotomy, "_centred_replay", replay)
    monkeypatch.setattr(dichotomy, "_accept", accept)
    monkeypatch.setattr(dichotomy, "_outside_obliquity", outside)
    spec = SearchSpec(systems=("monoclinic",), min_d_axis=4.0, max_d_axis=11.0,
                      max_volume=300.0, shift_allowance_deg=1e-9,
                      budget_seconds=600.0)
    runs = []
    for flag in (False, True):
        trace.clear()
        monkeypatch.setattr(compiled, "_ENABLED", flag)
        result = search_dichotomy(peaks_780(), spec=spec)
        assert result.search_complete["monoclinic"]
        runs.append((list(trace), result.stats["monoclinic.boxes"],
                     [(_bits(c.cell), c.n_indexed) for c in result.candidates]))
        if not flag:
            assert oblique[0] > 1000, "the domain no longer reaches the bound"
    assert runs[0][0], "no leaf was reached"
    assert runs[0] == runs[1]
