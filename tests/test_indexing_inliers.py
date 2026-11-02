"""Search acceptance by inliers (indexing chunk C4): the cap becomes an output.

A search accepts a cell only if it indexes all but ``n_unindexed`` (2) of the
lines it was driven by, an **absolute** budget.  A list carrying more
off-lattice lines than that loses its true cell: an exhaustive search
*completes* and says "no cell", or returns only single-engine cells that
explain the foreign lines by having a line everywhere.  The inlier rule is
RANSAC's acceptance (Fischler & Bolles 1981): at least
``max(n_dof + 4, ⌈0.6 N⌉)`` of the N driven lines indexed, the five strongest
among them, with what a cell leaves reported on the candidate.  A default run
keeps the count of two and retries under the inlier rule only when no lattice
two engines agree on came back, because the rule changes the pool the panel's
Borda count ranks (``engines.INLIER_FRACTION`` has the SRM 660c measurement).

Interpretation table, written before the tests were run:

==================================  =====================================  =====================================
behaviour                           positive arm (must read)               negative / control arm (must read)
==================================  =====================================  =====================================
inliers replace the cap             6 mid-gap impurities among 19 driven   the same list under the count of 2
                                    lines: every engine under              returns nothing at all (the pre-1.9
                                    ``"inliers"`` returns the true cubic   failure, which a declared int keeps)
                                    P cell first
the default retries on no agreement the impurity list: ``index_pattern``   the clean 13-line list: no retry, and
                                    reports ``INDEX_INLIER_RETRY`` and     the ranked cells are exactly those of
                                    ranks the truth first                  a declared count of 2
the anchor                          a cell indexing 14 of 20 driven lines  the same cell with the anchor line
                                    but missing one of the 5 strongest     indexed is accepted; a position-only
                                    is refused                             list (one intensity) has no anchor
                                                                           and keeps the absolute count of 2
the budget arithmetic               ``"inliers"``: 20 driven lines → 8     the default and a short triclinic
                                    left for every system                  list leave 2 and 0; a declared count
                                                                           is returned verbatim
the outputs                         the truth reports 6 driven lines left  the clean list's truth reports 0 and
                                    and every impurity in its residue      an empty residue
==================================  =====================================  =====================================

Synthetic positions only (``PeakList.from_positions``), exact, with declared
σ and intensities: an engine that cannot recover a cell from perfect
positions has an *acceptance* problem, which is the thing under test.
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.crystallography.symmetry import generate_reflections
from rietx.indexing.engines import SearchSpec, corroborated, get_engine
from rietx.schemas.indexing import PeakList

LAM = 1.5405929
A_TRUE = 4.1566
#: mid-gap and mutually incommensurate, checked against the cubic P line list
#: and its 2a supercell: an "impurity" on a real line is a duplicate, not an
#: impurity (the trap ``test_dichotomy_tolerates_impurity_lines`` records)
IMPURITIES = np.array([25.13, 34.22, 46.31, 58.74, 70.06, 81.42])
IMPURITY_INTENSITY = 8.0


def _truth_positions() -> np.ndarray:
    refl = generate_reflections("P m -3 m", (A_TRUE,) * 3 + (90.0,) * 3, LAM,
                                90.0)
    tt = np.degrees(2.0 * np.arcsin(LAM / (2.0 * np.asarray(refl.d))))
    return np.unique(np.round(tt, 8))


def _peaks(impurities: bool) -> PeakList:
    tt = _truth_positions()
    inten = np.linspace(100.0, 20.0, len(tt))
    if impurities:
        tt = np.concatenate([tt, IMPURITIES])
        inten = np.concatenate([inten, np.full(len(IMPURITIES),
                                               IMPURITY_INTENSITY)])
    order = np.argsort(tt)
    return PeakList.from_positions(tt[order], LAM, intensity=inten[order],
                                   two_theta_esd=0.005)


def _spec(**over) -> SearchSpec:
    # σ_sys declared ~0: exact positions, so the assumed real-data allowance is
    # looseness here (``test_indexing_engines.spec_for``'s reason)
    kw = dict(systems=("cubic",), min_d_axis=2.0, max_d_axis=12.0,
              max_volume=1500.0, shift_allowance_deg=1e-9, budget_seconds=60.0)
    kw.update(over)
    return SearchSpec(**kw)


def _is_truth(c) -> bool:
    return c.centring == "P" and abs(float(c.cell[0]) - A_TRUE) < 1e-3


@pytest.mark.parametrize("engine", ["dichotomy", "trial_error", "svd"])
def test_impurity_lines_past_the_old_cap_no_longer_refuse_the_true_cell(engine):
    """Six foreign lines among 19 driven: the inlier rule finds the truth first
    on every engine, the count of 2 finds nothing."""
    peaks = _peaks(impurities=True)
    found = get_engine(engine)(peaks, spec=_spec(n_unindexed="inliers"))
    assert found.candidates, f"{engine}: the inlier rule found nothing"
    assert _is_truth(found.candidates[0]), (
        engine, [(c.centring, c.cell[0]) for c in found.candidates[:3]])
    assert found.search_complete["cubic"]

    capped = get_engine(engine)(peaks, spec=_spec(n_unindexed=2))
    assert not any(_is_truth(c) for c in capped.candidates), (
        f"{engine}: a declared cap of 2 should still refuse the truth here — "
        "if it does not, this list no longer tests the cap")


def test_the_default_retries_under_inliers_only_when_no_two_engines_agree():
    from rietx.indexing import index_pattern

    dirty = index_pattern(_peaks(impurities=True), spec=_spec(), preset="full")
    assert any(d.code == "INDEX_INLIER_RETRY" for d in dirty.diagnostics)
    assert _is_truth(dirty.candidates[0])
    assert len(dirty.candidates[0].found_by) == 3

    clean = index_pattern(_peaks(impurities=False), spec=_spec(),
                          preset="full")
    assert not any(d.code == "INDEX_INLIER_RETRY" for d in clean.diagnostics)
    declared = index_pattern(_peaks(impurities=False),
                             spec=_spec(n_unindexed=2), preset="full")
    assert _is_truth(clean.candidates[0])
    assert [c.cell for c in clean.candidates] == [c.cell for c in
                                                  declared.candidates]


def test_the_budget_is_a_fraction_of_the_driven_lines():
    assert SearchSpec().miss_budget(20, "cubic") == 2
    spec = SearchSpec(n_unindexed="inliers")
    for system in ("cubic", "tetragonal", "hexagonal", "trigonal",
                   "orthorhombic", "monoclinic", "triclinic"):
        assert spec.miss_budget(20, system) == 8, system
    assert spec.miss_budget(20) == 8
    # a short list: n_dof + 4 binds, and never past the list itself
    assert spec.miss_budget(10, "cubic") == 4
    assert spec.miss_budget(0, "cubic") == 2
    # never below what a default run tolerates (#951): the DOF term alone would
    # leave 0 at triclinic N = 10, 1 at monoclinic N = 9, 0 at cubic N = 5
    assert spec.miss_budget(10, "triclinic") == 2
    assert spec.miss_budget(9, "monoclinic") == 2
    assert spec.miss_budget(5, "cubic") == 2
    # a declared count is the caller's statement, returned verbatim
    assert SearchSpec(n_unindexed=3).miss_budget(20, "cubic") == 3
    # and a list with no anchor (one intensity) keeps the absolute count
    assert spec.miss_budget(20, "cubic", anchored=False) == 2


def test_a_cell_missing_one_of_the_strongest_lines_is_refused():
    from rietx.indexing.engines import indexes_the_search_lines

    search = np.arange(20)
    anchors = np.array([2, 5, 7, 11, 13])
    hits = np.setdiff1d(search, [0, 1, 3, 4, 6, 8])          # 14 of 20, ≥ 12
    assert indexes_the_search_lines(hits, search, 8, anchors)
    missing_anchor = np.setdiff1d(hits, [11])                # 13, an anchor gone
    assert not indexes_the_search_lines(missing_anchor, search, 8, anchors)
    # and the count still binds: 11 of 20 with every anchor is refused
    few = np.array([2, 5, 7, 11, 13, 14, 15, 16, 17, 18, 19])
    assert not indexes_the_search_lines(few, search, 8, anchors)


def test_the_anchors_are_the_strongest_driven_lines_and_need_intensities():
    from rietx.indexing.engines import search_anchors, search_line_order

    peaks = _peaks(impurities=True)
    spec = _spec(n_unindexed="inliers")
    search = search_line_order(peaks, spec)
    anchors = search_anchors(peaks, search, spec)
    inten = peaks.intensity()
    assert len(anchors) == 5
    assert inten[anchors].min() >= np.sort(inten[search])[-5]
    assert not np.isin(np.round(peaks.two_theta()[anchors], 2),
                       IMPURITIES).any()
    # an absolute count — declared, or the default's first pass — has none
    assert not len(search_anchors(peaks, search, _spec(n_unindexed=2)))
    assert not len(search_anchors(peaks, search, _spec()))
    # one intensity everywhere is no measurement of "strongest"
    flat = PeakList.from_positions(peaks.two_theta(), LAM, two_theta_esd=0.005)
    assert not len(search_anchors(flat, search_line_order(flat, spec), spec))


def test_the_candidate_reports_what_it_left_unindexed():
    from rietx.indexing import index_pattern

    dirty = index_pattern(_peaks(impurities=True), spec=_spec(),
                          preset="full")
    truth = next(c for c in dirty.candidates if _is_truth(c))
    assert truth.n_search_unindexed == len(IMPURITIES)
    residue = np.asarray(truth.unindexed_two_theta)
    assert len(residue) == len(IMPURITIES)
    assert np.allclose(np.sort(residue), IMPURITIES, atol=1e-6)

    clean = index_pattern(_peaks(impurities=False), spec=_spec(),
                          preset="full")
    truth = next(c for c in clean.candidates if _is_truth(c))
    assert truth.n_search_unindexed == 0
    assert truth.unindexed_two_theta == []


def test_the_anchor_prune_is_the_whole_set_replay_at_every_leaf(monkeypatch):
    """The anchor is a prune inside the exhaustive engine, so it must keep the
    property every prune there has (WP-1509): at each leaf, a centring's
    verdict on the leaf's survivors equals its verdict on its whole search set
    — now with the anchor rows in both.  The cubic impurity list has
    intensities, so the anchor is live; the last line is the vacuity guard."""
    from rietx.indexing import dichotomy
    from rietx.indexing.dichotomy import _test_box, search_dichotomy

    original = dichotomy._centred_replay
    seen = {"anchored": 0, True: 0, False: 0}

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
        seen[got] += 1
        seen["anchored"] += anchors is not None and len(anchors) > 0
        return got

    monkeypatch.setattr(dichotomy, "_centred_replay", checking)
    search_dichotomy(_peaks(impurities=True), spec=_spec(n_unindexed="inliers"))
    assert seen["anchored"] and seen[True], seen


def test_a_list_without_intensities_is_not_searched_twice():
    """One intensity everywhere: the inlier rule has no anchor and *is* the count
    of two, so a run with no agreement is not repeated for nothing."""
    from rietx.indexing import index_pattern

    p = _peaks(impurities=True)
    flat = PeakList.from_positions(p.two_theta(), LAM, two_theta_esd=0.005)
    res = index_pattern(flat, spec=_spec(), preset="full")
    # the trigger held — no lattice two engines agree on — so the silence of
    # the retry is the anchor rule's, not the trigger's
    assert not any(corroborated(c) for c in res.candidates)
    assert not any(d.code == "INDEX_INLIER_RETRY" for d in res.diagnostics)


def test_the_retry_adds_to_the_first_pass_and_never_removes_from_it(monkeypatch):
    """A first pass whose only finder of the truth is one engine has no lattice
    two engines agree on, so the retry runs, and its answer must still hold that
    candidate.  Measured on a lab pattern (#951's baseline): main's rank 1, a
    dichotomy-only true cell, left the list entirely when the retry replaced the
    first pass, while its a/2 subcell took rank 1.  Here svd finds the truth
    alone on the first pass and nothing under the inlier rule; the other two
    engines find nothing either way."""
    from rietx.indexing import engines, index_pattern
    from rietx.indexing.engines import EngineResult

    real = engines.get_engine

    def stubbed(name):
        def run(peaks, *, spec, **kw):
            if name == "svd" and not spec.inliers:
                return real(name)(peaks, spec=spec, **kw)
            return EngineResult(engine=name, systems_searched=(),
                                search_complete={})
        return run

    monkeypatch.setattr(engines, "get_engine", stubbed)
    res = index_pattern(_peaks(impurities=False), spec=_spec(), preset="full")
    assert any(d.code == "INDEX_INLIER_RETRY" for d in res.diagnostics)
    assert any(_is_truth(c) for c in res.candidates), (
        [(c.centring, c.cell[0], c.found_by) for c in res.candidates[:3]])


def test_a_retried_run_streams_a_ladder_that_never_overruns():
    """The retry runs every (engine × system) unit again, so the ladder's total
    grows with it: ``stage N of M`` never has N > M (#951 review, item 2)."""
    from rietx.indexing import index_pattern

    events = []
    res = index_pattern(_peaks(impurities=True), spec=_spec(), preset="full",
                        events=events.append)
    assert any(d.code == "INDEX_INLIER_RETRY" for d in res.diagnostics)
    starts = [e["data"] for e in events if e["kind"] == "stage_start"]
    assert starts and all(d["n_stages"] >= d["index"] for d in starts)


def test_a_retry_cut_short_keeps_what_the_first_pass_found(monkeypatch):
    """The retry may be cut off before it reaches an engine (deadline, or the
    person stopping the run): that engine's first-pass result, and the systems
    it searched, stay in the answer (#951 review, item 1).  Here svd alone finds
    the truth on the first pass, and the token trips when the first retry unit
    starts, so svd has no retry unit at all."""
    from rietx.indexing import engines, index_pattern
    from rietx.indexing.engines import EngineResult
    from rietx.optimize.cancel import CancelToken

    real = engines.get_engine
    token = CancelToken()

    def stubbed(name):
        def run(peaks, *, spec, **kw):
            if spec.inliers:
                token.cancel()
                return EngineResult(engine=name, systems_searched=(),
                                    search_complete={})
            if name == "svd":
                return real(name)(peaks, spec=spec, **kw)
            return EngineResult(engine=name, systems_searched=(),
                                search_complete={})
        return run

    monkeypatch.setattr(engines, "get_engine", stubbed)
    res = index_pattern(_peaks(impurities=False), spec=_spec(), preset="full",
                        cancel=token)
    assert any(_is_truth(c) for c in res.candidates)
    assert "cubic" in res.systems_searched


def test_the_panel_trim_accepts_the_inlier_string():
    """``spec.n_unindexed`` handed straight through is ``"inliers"`` under a
    declared inlier search: the trim is 0, not ``int("inliers")`` (#951 review,
    item 4)."""
    from rietx.indexing.engines import rank_candidates, to_cell_candidate

    peaks = _peaks(impurities=False)
    spec = _spec(n_unindexed="inliers")
    res = get_engine("dichotomy")(peaks, spec=spec)
    assert res.candidates
    assert rank_candidates(res.candidates, peaks,
                           n_unindexed=spec.n_unindexed)
    assert to_cell_candidate(res.candidates[0], peaks,
                             n_unindexed=spec.n_unindexed) is not None


def test_the_panel_trim_keeps_a_numpy_integer():
    """A numpy integer is a declared count, as ``int(n or 0)`` once read it
    (#951 round 2, follow-up)."""
    import numpy as np

    from rietx.indexing.engines import _panel_trim

    assert _panel_trim(np.int64(3)) == 3
    assert _panel_trim(3) == 3
    assert _panel_trim(None) == 0
    assert _panel_trim("inliers") == 0
