"""Weak lines and the indexer's rank of the true cell: WP-2078 task 2's record.

Three synthetic patterns from ``tests/_synthetic_weak_lines.py``, each picked
as ``pick_peaks`` picks it and then cut at 0.5, 1 and 2 % of its strongest
usable line (issue #1291's floor, :func:`~tests._synthetic_weak_lines.floored`).
Every list is searched under ``index_pattern``'s default (``preset="quick"``,
all three engines, the default thresholds) with the truth's crystal system
declared, ``SearchSpec(systems=("cubic",))``, and the truth's rank is read by
:func:`tests.indexing_gallery.rank_of_lattice`.

**Why the system is declared, and why (a) is searched over 12.1-45°.**
Undeclared, the default searches every system under a 120 s whole-run
ceiling, and on the as-picked lists here (29 to 41 usable lines before (a) was narrowed) that ceiling
binds: measured 120-122 s, the trailing systems cut or never reached,
``INDEX_BUDGET_EXHAUSTED``.  A rank read off a cut search is a reading of
machine load (WP-1449), so it cannot be pinned.  With the system declared a
list searches in 2-15 s, except (a) as picked over the full 12.1-60° range,
which took 51 s alone and 122 s under a full-suite run, cut and skipped.  (a)
is therefore drawn over 12.1-45°, where the same search takes about 13 s
alone, a ceiling-to-serial ratio near 9 (the PR's one measurement; the range
keeps the host's four lines and the oxide's 29 picked ones).  Every declared
list is expected to finish; a row whose search the ceiling still cuts skips
rather than reads a load, and says so.  The undeclared default's ranks are in
WP-2078's PR body, with the cut named.

**What the rows say on main** (truth's rank; "—" = absent from the list):

=============================  ==========  ======  ====  ====  ====
fixture                        weak lines  picked  0.5%  1 %   2 %
=============================  ==========  ======  ====  ====  ====
(a) molybdenum + trace MoO₃    foreign     —       1     1     —
(b) ordered double perovskite  structural  1       1     2     3
(c) Si + twelve planted lines  foreign     —       —     —     —
=============================  ==========  ======  ====  ====  ====

* (a) reproduces the failure: molybdenum owns 4 of the 36 picked lines and
  the oxide 29, the count of 2 refuses the host, and the inlier retry
  (WP-1969) cannot accept a cell owning a ninth of the list.  The 0.5 % and
  1 % floors leave the host's four lines (and two or none of the oxide's) and
  the truth comes first.  At 2 % the list is the host's four lines alone,
  which is fewer than five per degree of freedom: ``INDEX_DATA_INSUFFICIENT``
  and no candidate, so the row is ``None`` for want of lines, not of a floor
  that is too high or too low.
* (b) keeps its supercell as picked and at 0.5 %; from 1 % the floor has
  removed all but the two strongest ordering lines and the cubic subcell
  (a/2, primitive) ranks first.  Undeclared, the 1 % list (16 lines, so only
  the systems it supports) still ranked the supercell first; the 2 % list
  ranked it 12th.
* (c) is absent under every floor: the twelve planted lines are 1-5 % of the
  strongest, so the 1 % floor keeps all twelve and the 2 % floor ten, and Si
  owns about half of each list.  The positive arm (no lines planted, 16 Si
  lines) ranks Si first.

A row records ``main`` and is meant to flip: the WP that changes a rank
changes the table and the row together.  The acceptance rows that fail on
``main`` are ``xfail(strict=True)`` naming WP-2078, so a fix turns them into
a failure that must be read, never a silent pass.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

from rietx.indexing import index_pattern
from rietx.indexing.engines import SearchSpec
from rietx.schemas.indexing import PeakList
from tests import _synthetic_weak_lines as W
from tests.indexing_gallery import rank_of_lattice
from tests.test_acceptance_indexing import _skip_unless_finished

BUILDERS = {"a": W.weak_second_phase, "b": W.weak_superlattice,
            "c": W.planted_silicon}
FLOORS = (0.0, 0.005, 0.01, 0.02)

#: the truth's rank on ``main`` per (fixture, floor), ``None`` = absent;
#: measured on 892e05fc0 and 1f4be2972 (the module docstring's table)
RANK_ON_MAIN = {
    ("a", 0.0): None, ("a", 0.005): 1, ("a", 0.01): 1, ("a", 0.02): None,
    ("b", 0.0): 1, ("b", 0.005): 1, ("b", 0.01): 2, ("b", 0.02): 3,
    ("c", 0.0): None, ("c", 0.005): None, ("c", 0.01): None, ("c", 0.02): None,
}
#: rows run in the fast tier: (b) as picked, which the WP's acceptance names
#: (9 s), and (a) at 1 %, the floor the issue proposes (2 s).  (a) as picked
#: takes about 13 s, so it and the rest are ``slow``
FAST_ROWS = {("a", 0.01), ("b", 0.0)}
#: two weak-line positions closer than this are one line (well under a FWHM)
MATCH_DEG = 0.03


@lru_cache(maxsize=None)
def _fixture(key: str) -> W.WeakLineFixture:
    return BUILDERS[key]()


@lru_cache(maxsize=None)
def _search(key: str, floor: float):
    fx = _fixture(key)
    peaks = fx.peaks if floor == 0.0 else W.floored(fx.peaks, floor)
    res = index_pattern(peaks, spec=SearchSpec(systems=("cubic",)))
    ranking = [{"centring": c.centring, "af": [float(v) for v in c.af]}
               for c in res.candidates]
    return res, rank_of_lattice(ranking, fx.cell, fx.centring, 5e-3)


def _finished(res) -> None:
    """Skip a row whose rank would be read off a search the clock cut."""
    if "INDEX_BUDGET_EXHAUSTED" in {d.code for d in res.diagnostics}:
        pytest.skip("the whole-run ceiling cut the search, so its order is a "
                    "reading of machine load (WP-1449)")
    _skip_unless_finished(res)


def _n_weak(fx: W.WeakLineFixture, two_theta) -> int:
    weak = np.asarray(fx.weak_two_theta)
    return int(sum(np.min(np.abs(weak - t)) < MATCH_DEG for t in two_theta))


def _row(key: str, floor: float):
    marks = [pytest.mark.xdist_group(f"weak-lines-{key}")]
    if (key, floor) not in FAST_ROWS:
        marks.append(pytest.mark.slow)
    return pytest.param(key, floor, marks=marks, id=f"{key}-{floor:g}")


# ----------------------------------------------------------------------------
# the builders
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("key", sorted(BUILDERS))
def test_a_builder_draws_the_same_list_every_time(key):
    """Fixed seeds: a second build picks the same lines at the same heights."""
    one, two = BUILDERS[key](), BUILDERS[key]()
    assert np.array_equal(one.peaks.two_theta(), two.peaks.two_theta())
    assert np.array_equal(one.peaks.intensity(), two.peaks.intensity())


@pytest.mark.xdist_group("weak-lines-a")
def test_the_trace_phase_is_on_the_picked_list_and_under_every_floor():
    """(a): the picker keeps 29 lines at the oxide's positions and 0.5 % keeps
    two; 1 % keeps none, and every floor keeps the host's four."""
    fx = _fixture("a")
    host = W._lines(W.MO_CIF, fx.two_theta_range)
    assert len(host) == 4
    assert _n_weak(fx, fx.peaks.two_theta()) == 29
    assert _n_weak(fx, W.floored(fx.peaks, 0.005).two_theta()) == 2
    for floor in FLOORS:
        kept = fx.peaks if floor == 0.0 else W.floored(fx.peaks, floor)
        if floor >= 0.01:
            assert _n_weak(fx, kept.two_theta()) == 0
        on_host = sum(np.min(np.abs(host - t)) < MATCH_DEG
                      for t in kept.two_theta())
        assert on_host == 4, f"the {floor:.1%} floor took one of the host's lines"


@pytest.mark.xdist_group("weak-lines-b")
def test_the_ordering_lines_thin_out_floor_by_floor():
    """(b): all twelve ordering lines are picked; each floor keeps fewer."""
    fx = _fixture("b")
    assert len(fx.weak_two_theta) == 12
    kept = [_n_weak(fx, (fx.peaks if f == 0.0 else W.floored(fx.peaks, f))
                    .two_theta()) for f in FLOORS]
    assert kept == [12, 5, 2, 1]


@pytest.mark.xdist_group("weak-lines-c")
def test_the_planted_lines_survive_the_floors():
    """(c): the twelve planted lines are picked, and a 2 % floor keeps ten."""
    fx = _fixture("c")
    kept = [_n_weak(fx, (fx.peaks if f == 0.0 else W.floored(fx.peaks, f))
                    .two_theta()) for f in FLOORS]
    assert kept == [12, 12, 12, 10]


@pytest.mark.xdist_group("weak-lines-a")
def test_a_floor_removes_nothing_from_a_position_only_list():
    """``from_positions`` gives every line weight 1, so no floor bites."""
    fx = _fixture("a")
    flat = PeakList.from_positions(fx.peaks.two_theta(), fx.peaks.wavelength)
    assert len(W.floored(flat, 0.02).usable()) == len(flat.usable())


# ----------------------------------------------------------------------------
# the record: the truth's rank on main
# ----------------------------------------------------------------------------
@pytest.mark.parametrize("key, floor", [_row(k, f) for k in sorted(BUILDERS)
                                        for f in FLOORS])
def test_truth_rank_on_main(key, floor):
    """The truth's rank as ``main`` gives it.  A change that moves one updates
    :data:`RANK_ON_MAIN` and the module docstring's table with it."""
    res, rank = _search(key, floor)
    _finished(res)
    assert rank == RANK_ON_MAIN[(key, floor)], (
        f"{key} at {floor:.1%}: truth rank {rank}, recorded "
        f"{RANK_ON_MAIN[(key, floor)]}; first: "
        + ", ".join(f"{c.system} {c.centring} {c.cell[0]:.4f}"
                    for c in res.candidates[:3]))


@pytest.mark.slow
@pytest.mark.xdist_group("weak-lines-c")
def test_silicon_without_planted_lines_ranks_first():
    """(c)'s positive arm: the same pattern with nothing planted."""
    fx = W.planted_silicon(n_planted=0)
    res = index_pattern(fx.peaks, spec=SearchSpec(systems=("cubic",)))
    _finished(res)
    ranking = [{"centring": c.centring, "af": [float(v) for v in c.af]}
               for c in res.candidates]
    assert rank_of_lattice(ranking, fx.cell, fx.centring, 5e-3) == 1


# ----------------------------------------------------------------------------
# WP-2078's acceptance, as main fails or meets it
# ----------------------------------------------------------------------------
@pytest.mark.slow
@pytest.mark.xdist_group("weak-lines-a")
@pytest.mark.xfail(strict=True, reason=(
    "WP-2078: on main the count of 2 refuses molybdenum among its oxide's "
    "lines and the inlier retry cannot accept a cell owning 4 of 36"),
    raises=AssertionError)
def test_a_trace_second_phase_leaves_the_truth_first():
    res, rank = _search("a", 0.0)
    _finished(res)
    assert rank == 1


@pytest.mark.xdist_group("weak-lines-b")
def test_a_superlattice_keeps_its_supercell_first():
    res, rank = _search("b", 0.0)
    _finished(res)
    assert rank == 1
