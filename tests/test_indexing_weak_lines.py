"""Weak lines and the indexer's rank of the true cell: WP-2078's record.

Three synthetic patterns from ``tests/_synthetic_weak_lines.py``, each picked
as ``pick_peaks`` picks it and then cut at 0.5, 1 and 2 % of its strongest
usable line (issue #1291's floor, :func:`~tests._synthetic_weak_lines.floored`).
Every list is searched under ``index_pattern``'s default (``preset="quick"``,
all three engines, the default thresholds) with the truth's crystal system
declared, ``SearchSpec(systems=("cubic",))``, and the truth's rank is read by
:func:`tests.indexing_gallery.rank_of_lattice`.

**Why the system is declared, and why (a) is searched over 12.1-55°.**
Undeclared, the default searches every system under a 120 s whole-run
ceiling, and on the as-picked lists here (29 to 41 usable lines before (a) was
narrowed) that ceiling binds: measured 120-122 s, the trailing systems cut or
never reached, ``INDEX_BUDGET_EXHAUSTED``.  A rank read off a cut search is a
reading of machine load (WP-1449), so it cannot be pinned.  With the system
declared a list searches in 2-15 s, except (a) as picked over the full
12.1-60° range, which took 51 s alone and 122 s under a full-suite run, cut and
skipped.  (a) is therefore drawn over 12.1-55°, where the as-picked search
took 17 s on a quiet machine and 30 s on a loaded one (maintainer's
measurements; 44 s here on a heavily loaded one), a ceiling-to-serial ratio
near 7.  The range keeps six of the host's lines, one above the five a cubic
search needs, and the oxide's 29 picked ones.  Over 12.1-45° the host had
four, and the 1 % row was decided by a picker shoulder sitting at the minimum.
A CI leg runs 3-4× slower than a laptop, so a search that finishes here sits
nearer the ceiling there; a row whose search the ceiling still cuts skips
rather than reads a load, and says so, and the first Linux nightly is the first
read of the slow rows.  The undeclared default's ranks are in WP-2078's PR
body, with the cut named.

**What the rows say** (truth's rank; "—" = absent from the list).  The
"picked" column is the default search, weak-line retry included; the floored
columns search the floored list as given:

=============================  ==========  ======  ====  ====  ====
fixture                        weak lines  picked  0.5%  1 %   2 %
=============================  ==========  ======  ====  ====  ====
(a) molybdenum + trace MoO₃    foreign     1       1     1     1
(b) ordered double perovskite  structural  1       1     2     3
(c) Si + twelve planted lines  foreign     —       —     —     —
=============================  ==========  ======  ====  ====  ====

* (a) reproduced the failure until the weak-line retry: molybdenum owns 6 of
  the 38 picked lines and the oxide 29, the count of 2 refuses the host, and
  the inlier retry (WP-1969) cannot accept a cell owning a sixth of the list.
  With no lattice two engines agree on, the search runs again on the lines at
  or above 5 % of the strongest (``INDEX_WEAK_LINE_RETRY``) and ranks the
  truth first; before WP-2078 built it the column read "—".  Every floor leaves all six
  of the host's lines, with two of the oxide's at 0.5 % and none from 1 %, and
  the truth comes first.  At 2 % the list is the host's six lines alone, one
  above the five a cubic search needs, so the row is decided by the floor and
  not by the picker's shoulders (over 12.1-45° it was four lines,
  ``INDEX_DATA_INSUFFICIENT``, and ``None``).
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
changes the table and the row together.  An acceptance row that fails on
``main`` is ``xfail(strict=True)`` naming its WP, so a fix turns it into a
failure that must be read, never a silent pass; (a)'s flipped with the
weak-line retry.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pytest

from rietx.indexing import index_pattern
from rietx.indexing.engines import SearchSpec, weak_line_floor
from rietx.schemas.indexing import PeakList
from tests import _synthetic_weak_lines as W
from tests.indexing_gallery import OUTPUT, rank_of_lattice
from tests.test_acceptance_indexing import _skip_unless_finished

BUILDERS = {"a": W.weak_second_phase, "b": W.weak_superlattice,
            "c": W.planted_silicon}
FLOORS = (0.0, 0.005, 0.01, 0.02)

#: the truth's rank on ``main`` per (fixture, floor), ``None`` = absent;
#: measured on 892e05fc0 and 1f4be2972 (the module docstring's table); (a) as
#: picked moved from absent to 1 with the weak-line retry (WP-2078)
RANK_ON_MAIN = {
    ("a", 0.0): 1, ("a", 0.005): 1, ("a", 0.01): 1, ("a", 0.02): 1,
    ("b", 0.0): 1, ("b", 0.005): 1, ("b", 0.01): 2, ("b", 0.02): 3,
    ("c", 0.0): None, ("c", 0.005): None, ("c", 0.01): None, ("c", 0.02): None,
}
#: rows run in the fast tier: (b) as picked, which the WP's acceptance names
#: (9 s), and (a) at 1 %, the floor the issue proposes (2 s).  (a) as picked
#: takes 17-30 s here and 3-4× that on a CI leg, so it and the rest are ``slow``
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


def _draw(key: str, res) -> None:
    """The ranked ticks and the leading cell's obs/calc/diff fit, to
    ``tests/output/`` for looking at (not a gallery row: the scoreboard counts
    real patterns only)."""
    import matplotlib.pyplot as plt

    from rietx.indexing.workflow import validate_by_lebail
    from rietx.viz.indexing import plot_indexing

    fx = _fixture(key)
    kept = weak_line_floor(fx.peaks) if any(
        d.code == "INDEX_WEAK_LINE_RETRY" for d in res.diagnostics) else fx.peaks
    pair = (validate_by_lebail(res.candidates[0], fx.data, fx.instrument,
                               peaks=kept, with_result=True)
            if res.candidates else None)
    OUTPUT.mkdir(exist_ok=True)
    for name, fig in plot_indexing(res, kept, data=fx.data, n=5,
                                   validation=pair).items():
        fig.savefig(OUTPUT / f"weak_lines_{key}_{name}.png")
        plt.close(fig)


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
    two; 1 % keeps none, and every floor keeps the host's six."""
    fx = _fixture("a")
    host = W._lines(W.MO_CIF, fx.two_theta_range)
    assert len(host) == 6
    assert _n_weak(fx, fx.peaks.two_theta()) == 29
    assert _n_weak(fx, W.floored(fx.peaks, 0.005).two_theta()) == 2
    for floor in FLOORS:
        kept = fx.peaks if floor == 0.0 else W.floored(fx.peaks, floor)
        if floor >= 0.01:
            assert _n_weak(fx, kept.two_theta()) == 0
        on_host = sum(np.min(np.abs(host - t)) < MATCH_DEG
                      for t in kept.two_theta())
        assert on_host == 6, f"the {floor:.1%} floor took one of the host's lines"


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
    """``from_positions`` gives every line weight 1, so no floor bites, the
    weak-line retry's included: such a list never sets a line aside."""
    fx = _fixture("a")
    flat = PeakList.from_positions(fx.peaks.two_theta(), fx.peaks.wavelength)
    assert len(W.floored(flat, 0.02).usable()) == len(flat.usable())
    assert len(weak_line_floor(flat).usable()) == len(flat.usable())


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
def test_a_trace_second_phase_leaves_the_truth_first():
    """The weak-line retry: the full list gives no lattice two engines agree
    on, the lines under 5 % of the strongest are set aside, and the search on
    the rest ranks molybdenum first.  The diagnostic names every set-aside
    line, and the candidates count the kept lines only."""
    fx = _fixture("a")
    res, rank = _search("a", 0.0)
    _finished(res)
    _draw("a", res)
    assert rank == 1
    retry = [d for d in res.diagnostics if d.code == "INDEX_WEAK_LINE_RETRY"]
    assert len(retry) == 1 and "the candidates are that search's" in retry[0].message
    n_set_aside = len(fx.peaks.usable()) - len(weak_line_floor(fx.peaks).usable())
    assert f"its {n_set_aside} line(s)" in retry[0].message
    assert res.n_usable_lines == len(weak_line_floor(fx.peaks).usable())


@pytest.mark.xdist_group("weak-lines-b")
def test_a_superlattice_keeps_its_supercell_first():
    """Two engines agree on the supercell from the full list, so the weak-line
    retry never runs and its twelve ordering lines all score."""
    res, rank = _search("b", 0.0)
    _finished(res)
    assert rank == 1
    assert "INDEX_WEAK_LINE_RETRY" not in {d.code for d in res.diagnostics}
