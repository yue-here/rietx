"""Reported flags leave the driven set and stay in the scoring (#934 (c)).

``weak_line`` (#947) is reported, not refused: the line stays in ``usable()``,
so the FoM panel still counts it and a cell may still explain it.  What it may
no longer do is **drive** the search (``engines.search_line_order``): every
driven line is one an accepted cell must index, so a noise line there charges
the truth for missing it (``schemas.indexing.PEAK_UNDRIVEN_FLAGS``).

Interpretation table, written before the tests were run:

====================================  =====================================  =====================================
behaviour                             positive arm (must read)               control arm (must read)
====================================  =====================================  =====================================
flagged lines are not driven          the C4 list (13 cubic P lines + 6      the same list unflagged drives all
                                      mid-gap impurities) with the six       19 lines, as before #934 (c)
                                      flagged ``weak_line`` drives the 13
the pool is drawn from what may       N = 4 over a list whose 5 lowest-Q     --
drive                                 lines are flagged: 4 driven lines,
                                      none flagged (a pool of the 8
                                      lowest lines would hold 3 unflagged)
the floor                             3 unflagged lines + 6 flagged: the     --
                                      driven set is 6, the 3 strongest
                                      flagged lines taken back
an engine is steered right            flagged list, declared count 2: each   the unflagged list under the same
                                      engine ranks the true cell first       count returns no cell at all
the flagged lines are still scored    the truth leaves 0 driven lines and    --
                                      its unindexed residue holds all six
                                      flagged impurities
#916's flat silicon (tuned profile)   cubic, declared count 2: 11 driven     flags stripped (main's driven set):
                                      lines, the truth ranked first          18 driven lines and no cell
====================================  =====================================  =====================================

Synthetic data only: positions from the C4 fixture, and silicon through the
package's own forward model with Poisson noise (#916's flat reproducer,
seed 1, 12.1–60°).
"""

from __future__ import annotations

import numpy as np
import pytest

from rietx.indexing.engines import (
    DRIVEN_MIN_LINES,
    SearchSpec,
    get_engine,
    search_line_order,
)
from rietx.schemas.indexing import PEAK_UNDRIVEN_FLAGS, PeakList
from tests.test_indexing_inliers import IMPURITIES, _is_truth, _peaks, _spec


def _flag(peaks: PeakList, two_theta: np.ndarray) -> PeakList:
    """A copy with ``weak_line`` on the lines at ``two_theta``."""
    out = peaks.model_copy(deep=True)
    for p in out.peaks:
        if np.isclose(p.two_theta, two_theta, atol=1e-6).any():
            p.flags = [*p.flags, "weak_line"]
    return out


def _flagged_impurities() -> PeakList:
    return _flag(_peaks(impurities=True), IMPURITIES)


def test_the_flag_is_the_undriven_set_and_stays_usable():
    assert PEAK_UNDRIVEN_FLAGS == frozenset({"weak_line"})
    peaks = _flagged_impurities()
    assert len(peaks.usable()) == len(peaks.peaks) == 19


def test_flagged_lines_are_not_driven_and_unflagged_ones_all_are():
    spec = _spec()
    flagged = _flagged_impurities()
    driven = flagged.two_theta()[search_line_order(flagged, spec)]
    assert len(driven) == 13
    assert not np.isin(np.round(driven, 2), IMPURITIES).any()
    plain = _peaks(impurities=True)
    assert len(search_line_order(plain, spec)) == 19


def test_the_pool_is_drawn_from_the_lines_that_may_drive():
    plain = _peaks(impurities=False)
    tt = np.sort(plain.two_theta())
    peaks = _flag(plain, tt[:5])
    spec = _spec(n_search_lines=4)
    sel = search_line_order(peaks, spec)
    assert len(sel) == 4
    assert not any("weak_line" in peaks.usable()[k].flags for k in sel)


def test_below_the_floor_the_strongest_flagged_lines_come_back():
    plain = _peaks(impurities=False)
    tt = plain.two_theta()
    keep = np.sort(tt)[:3]
    peaks = _flag(plain, tt[~np.isin(tt, keep)][:6])
    peaks = PeakList(peaks=[p for p in peaks.peaks
                            if np.isin(p.two_theta, keep) or "weak_line" in p.flags],
                     wavelength=peaks.wavelength,
                     two_theta_min=peaks.two_theta_min,
                     two_theta_max=peaks.two_theta_max, source=peaks.source)
    assert len(peaks.usable()) == 9
    sel = search_line_order(peaks, _spec())
    assert len(sel) == DRIVEN_MIN_LINES == 6
    back = [k for k in sel if "weak_line" in peaks.usable()[k].flags]
    weak = [k for k, p in enumerate(peaks.usable()) if "weak_line" in p.flags]
    strongest = sorted(weak, key=lambda k: -peaks.intensity()[k])[:3]
    assert sorted(back) == sorted(strongest)


@pytest.mark.parametrize("engine", ["dichotomy", "trial_error", "svd"])
def test_a_flagged_line_no_longer_refuses_the_true_cell(engine):
    spec = _spec(n_unindexed=2)
    found = get_engine(engine)(_flagged_impurities(), spec=spec).candidates
    assert found and _is_truth(found[0])
    # the control: the same lines driven, the absolute count of two refuses
    plain = get_engine(engine)(_peaks(impurities=True), spec=spec).candidates
    assert not any(_is_truth(c) for c in plain)


def test_the_flagged_lines_are_still_scored():
    from rietx.indexing import index_pattern
    res = index_pattern(_flagged_impurities(), spec=_spec(n_unindexed=2),
                        preset="full")
    truth = next(c for c in res.candidates if _is_truth(c))
    assert res.candidates[0] is truth
    assert truth.n_search_unindexed == 0
    assert np.isin(IMPURITIES, np.round(truth.unindexed_two_theta, 2)).all()


def test_916s_flat_silicon_is_driven_by_its_own_lines(tmp_path):
    import rietx as rx
    from rietx.indexing import index_pattern
    from rietx.model.forward import WINDOW_AREA_TOL
    from tests.test_peak_fdr import LAM, RANGE, _silicon

    ins = rx.Instrument.debye_scherrer(wavelength=LAM)
    ins.profile.w.value, ins.profile.u.value, ins.profile.x.value = 3e-4, 5e-4, 5e-3
    # Drawn at the declared stages' 2 % windows, where the control below was
    # measured.  At the closing windows ``predict`` now uses (WP-2002) the
    # pattern has full tails, the picker finds three fewer weak components, and
    # the stripped set (15 lines) indexes: 4 candidates, so the control would
    # no longer show the rule is needed on this pattern.
    peaks = rx.pick_peaks(_silicon(tmp_path, steep=False, hi=62.0,
                                   window_area_tol=WINDOW_AREA_TOL), ins,
                          two_theta_range=RANGE)
    spec = SearchSpec(systems=("cubic",), n_unindexed=2)

    def truth_rank(res):
        return next((i for i, c in enumerate(res.candidates, 1)
                     if c.centring == "F"
                     and abs(float(c.cell[0]) - 5.4311) < 5e-3), None)

    res = index_pattern(peaks, spec=spec, preset="full")
    assert len(search_line_order(peaks, spec)) == 11
    assert truth_rank(res) == 1
    # the control: main's driven set, every weak_line component in it
    stripped = peaks.model_copy(deep=True)
    for p in stripped.peaks:
        p.flags = [f for f in p.flags if f != "weak_line"]
    assert len(search_line_order(stripped, spec)) == 18
    assert not index_pattern(stripped, spec=spec, preset="full").candidates


def test_a_residue_misfit_line_is_scored_and_never_driven_even_below_the_floor():
    """``residue_misfit`` (index_residue) is the one flag the
    ``DRIVEN_MIN_LINES`` floor does not take back."""
    from rietx.schemas.indexing import PEAK_NEVER_DRIVEN_FLAGS

    assert PEAK_NEVER_DRIVEN_FLAGS == frozenset({"residue_misfit"})
    plain = _peaks(impurities=False)
    tt = plain.two_theta()
    keep = np.sort(tt)[:3]
    peaks = plain.model_copy(deep=True)
    peaks.peaks = [p for p in peaks.peaks if np.isin(p.two_theta, np.sort(tt)[:9])]
    for p in peaks.peaks:
        if not np.isin(p.two_theta, keep):
            p.flags = [*p.flags, "residue_misfit"]
    assert len(peaks.usable()) == 9               # scored
    sel = search_line_order(peaks, _spec())
    assert sorted(sel) == [0, 1, 2]               # never driven: no refill
