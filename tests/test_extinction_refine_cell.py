"""``determine_extinction_symbol(refine_cell=...)``: #726's two arms.

SRM 676a corundum from the IUCr round robin (public, ``tests/data/qarr``), at the
certified cell and at the cell scaled by 1.0012: the held-cell screen
(``refine_cell=False``) refuted the true class at the scaled one; the default,
which Le Bail-refines the cell in a cell-free prefit before screening, does not.
Since WP-2076 the held screen returns the true class there too: the refutation
came from the Le Bail fits the screen compared, which were not χ² minima.
"""

from __future__ import annotations

import pytest

from rietx.indexing.extinction import determine_extinction_symbol

SCALE = 1.0012


def _scaled(cell, factor):
    return tuple(v * factor for v in cell[:3]) + tuple(cell[3:])


@pytest.fixture(scope="module")
def inputs():
    from tests.test_extinction_symbol import (
        CORUNDUM_CELL,
        CORUNDUM_RANGE,
        _candidate,
        corundum_inputs,
    )

    data, _cand, instrument = corundum_inputs.__wrapped__()
    return (data, instrument, CORUNDUM_RANGE,
            _candidate(_scaled(CORUNDUM_CELL, SCALE), "trigonal", "R"),
            CORUNDUM_CELL)


def test_a_cell_off_by_a_tenth_of_a_percent_returns_the_true_class_held_or_refined(
        inputs):
    """#726's held arm refuted ``R - c -`` here under the Le Bail screen.  Under
    the nested Pawley screen (WP-2076) the held cell returns it at every factor
    scanned from ×0.995 to ×1.002, so both arms now answer alike."""
    data, instrument, limits, candidate, certified = inputs

    held = determine_extinction_symbol(data, candidate, instrument,
                                       two_theta_limits=limits,
                                       refine_cell=False)
    best = held.best_or_none()
    assert best is not None and best.symbol == "R - c -", [
        (c.symbol, round(c.delta_bic, 1), c.refuted_reason) for c in held.candidates]
    assert held.cell == pytest.approx(candidate.cell)
    assert held.prefit_rwp is None

    refined = determine_extinction_symbol(data, candidate, instrument,
                                          two_theta_limits=limits)
    best = refined.best_or_none()
    assert best is not None, [(c.symbol, c.refuted_reason)
                              for c in refined.candidates]
    assert best.symbol == "R - c -"
    assert best.space_groups == ["R 3 c:H", "R -3 c:H"]
    # the screen says which cell it used, and it moved back toward the certified one
    assert refined.cell != pytest.approx(candidate.cell)
    assert abs(refined.cell[0] / certified[0] - 1) < abs(candidate.cell[0] / certified[0] - 1)
    assert refined.prefit_rwp is not None


@pytest.mark.parametrize("factor", [0.9992, 1.0004, 1.0008, 1.002, 1.005, 1.01])
def test_the_prefit_basin_holds_either_side_of_wp_1910s_acceptance_case(inputs, factor):
    """WP-1910's case is x1.0008 (``R - - -`` under a held cell before WP-2076); the
    prefit has no ``window_slack_deg``, so the margin either side is measured
    rather than assumed: the true class returns across -0.08 % to +1 %."""
    from tests.test_extinction_symbol import CORUNDUM_CELL, _candidate

    data, instrument, limits, _scaled_candidate, _certified = inputs
    cand = _candidate(_scaled(CORUNDUM_CELL, factor), "trigonal", "R")
    screen = determine_extinction_symbol(data, cand, instrument,
                                         two_theta_limits=limits)
    best = screen.best_or_none()
    assert best is not None and best.symbol == "R - c -", (
        factor, screen.status, [c.symbol for c in screen.candidates[:3]])
